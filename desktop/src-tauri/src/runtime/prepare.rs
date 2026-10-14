//! Gets the model onto disk: the download half of the readiness flow.
//!
//! [`installed`] answers from disk alone. Only when something is missing does [`prepare`]
//! go to the network: it checks space, then downloads the model files from their sources
//! (each checked against the sha256 compiled into the app), reporting each step.

use std::path::PathBuf;
use std::sync::atomic::AtomicBool;

use serde::{Deserialize, Serialize};

use super::download::{self, DownloadError, FileSpec, Phase, RetryPolicy};
use super::install::{self, InsufficientSpace, Layout};
use super::manifest::{Manifest, ManifestError};

/// What the backend needs from an installed model.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Ready {
    pub model_cache_dir: PathBuf,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Step {
    SpaceCheck,
    Downloading,
    Verifying,
    /// Writing the files that record the model as installed.
    Installing,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
pub struct Progress {
    pub step: Step,
    /// Bytes on disk across everything this run downloads, out of `total`.
    pub done: u64,
    pub total: u64,
}

#[derive(Debug)]
pub enum PrepareError {
    Manifest(ManifestError),
    Space(InsufficientSpace),
    Download(DownloadError),
    Io(std::io::Error),
}

impl PrepareError {
    /// The step to show as failed.
    pub fn step(&self) -> Step {
        match self {
            PrepareError::Space(_) => Step::SpaceCheck,
            PrepareError::Download(DownloadError::ChecksumMismatch { .. }) => Step::Verifying,
            PrepareError::Io(_) | PrepareError::Manifest(_) => Step::Installing,
            PrepareError::Download(_) => Step::Downloading,
        }
    }
}

impl std::fmt::Display for PrepareError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            PrepareError::Manifest(error) => error.fmt(f),
            PrepareError::Space(space) => write!(
                f,
                "not enough disk space at {}: {} bytes needed, {} available",
                space.path.display(),
                space.required,
                space.available
            ),
            PrepareError::Download(error) => error.fmt(f),
            PrepareError::Io(error) => error.fmt(f),
        }
    }
}

impl std::error::Error for PrepareError {}

impl From<std::io::Error> for PrepareError {
    fn from(error: std::io::Error) -> Self {
        PrepareError::Io(error)
    }
}

#[derive(Debug, Serialize, Deserialize)]
struct CurrentModel {
    id: String,
}

fn current_model_file(layout: &Layout) -> PathBuf {
    layout.data_dir.join("models").join("current.json")
}

/// The model, if it is already installed. Reads the disk only.
pub fn installed(layout: &Layout) -> Option<Ready> {
    let model: CurrentModel =
        serde_json::from_slice(&std::fs::read(current_model_file(layout)).ok()?).ok()?;
    layout.model_installed(&model.id).then(|| Ready {
        model_cache_dir: layout.model_dir(&model.id),
    })
}

/// Downloads whatever of the model is missing.
///
/// Safe to call again after any failure: finished files are kept, partial ones resume.
pub fn prepare(
    layout: &Layout,
    manifest: &Manifest,
    retry: &RetryPolicy,
    cancel: &AtomicBool,
    on_progress: &mut dyn FnMut(Progress),
) -> Result<Ready, PrepareError> {
    let model_dir = layout.model_dir(&manifest.model.id);
    let specs: Vec<FileSpec> = if layout.model_installed(&manifest.model.id) {
        Vec::new()
    } else {
        manifest
            .model
            .files
            .iter()
            .map(|file| FileSpec {
                urls: file.urls.clone(),
                dest: model_dir.join(&file.path),
                size: file.size,
                sha256: file.sha256.clone(),
            })
            .collect()
    };

    // Space.
    on_progress(Progress {
        step: Step::SpaceCheck,
        done: 0,
        total: 0,
    });
    let remaining: u64 = specs
        .iter()
        .map(|spec| spec.size - download::bytes_present(spec))
        .sum();
    let required = install::required_space(remaining);
    let available = install::available_space(&layout.data_dir)?;
    install::check_space(&layout.data_dir, required, available).map_err(PrepareError::Space)?;

    // Downloads, counted together so the bar moves once from 0 to the total.
    let total: u64 = specs.iter().map(|spec| spec.size).sum();
    let mut finished_before = 0;
    for spec in &specs {
        // Shared by both callbacks: the phase callback switches it, and every progress
        // report after that carries it.
        let step = std::cell::Cell::new(Step::Downloading);
        let last_done = std::cell::Cell::new(finished_before);
        let progress = std::cell::RefCell::new(&mut *on_progress);
        download::download_with_phases(
            spec,
            retry,
            cancel,
            &mut |bytes| {
                last_done.set(finished_before + bytes);
                (progress.borrow_mut())(Progress {
                    step: step.get(),
                    done: last_done.get(),
                    total,
                });
            },
            &mut |phase| {
                step.set(match phase {
                    Phase::Fetching => Step::Downloading,
                    Phase::Verifying => Step::Verifying,
                });
                (progress.borrow_mut())(Progress {
                    step: step.get(),
                    done: last_done.get(),
                    total,
                });
            },
        )
        .map_err(PrepareError::Download)?;
        finished_before += spec.size;
    }

    if !specs.is_empty() {
        on_progress(Progress {
            step: Step::Installing,
            done: total,
            total,
        });
        install::mark_model_installed(layout, &manifest.model)?;
    }
    let current = serde_json::to_vec(&CurrentModel {
        id: manifest.model.id.clone(),
    })
    .unwrap();
    std::fs::create_dir_all(model_dir.parent().unwrap())?;
    std::fs::write(current_model_file(layout), current)?;

    installed(layout).ok_or_else(|| {
        PrepareError::Io(std::io::Error::other(
            "model still not installed after preparing",
        ))
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::runtime::manifest::{ModelFile, ModelSet};
    use crate::runtime::test_server::{sha256_hex, Behaviour, TestServer};

    /// A source list pointing at files served by `server`, with a mirror that has none of
    /// them listed first: every file falls through to its "official" URL.
    fn serve(server: &TestServer) -> Manifest {
        let onnx = vec![7u8; 50_000];
        let tokenizer = b"{\"tokenizer\": true}".to_vec();
        server.put("official/model_quantized.onnx", onnx.clone());
        server.put("official/tokenizer.json", tokenizer.clone());
        let urls = |name: &str| vec![server.url(&format!("mirror/{name}")), server.url(&format!("official/{name}"))];

        Manifest {
            v: 3,
            target: "test".into(),
            model: ModelSet {
                id: "m".into(),
                files: vec![
                    ModelFile {
                        path: "model_quantized.onnx".into(),
                        size: onnx.len() as u64,
                        sha256: sha256_hex(&onnx),
                        urls: urls("model_quantized.onnx"),
                    },
                    ModelFile {
                        path: "tokenizer/tokenizer.json".into(),
                        size: tokenizer.len() as u64,
                        sha256: sha256_hex(&tokenizer),
                        urls: urls("tokenizer.json"),
                    },
                ],
            },
        }
    }

    fn run(layout: &Layout, manifest: &Manifest, steps: &mut Vec<Progress>) -> Result<Ready, PrepareError> {
        prepare(
            layout,
            manifest,
            &RetryPolicy { backoff: vec![] },
            &AtomicBool::new(false),
            &mut |p| steps.push(p),
        )
    }

    #[test]
    fn installs_the_model_from_nothing() {
        let server = TestServer::start();
        let manifest = serve(&server);
        let dir = tempfile::tempdir().unwrap();
        let layout = Layout::new(dir.path().to_owned());
        assert_eq!(installed(&layout), None);

        let mut steps = Vec::new();
        let ready = run(&layout, &manifest, &mut steps).unwrap();

        assert_eq!(ready.model_cache_dir, dir.path().join("models/m"));
        // The layout `ensure_model_cached` looks for.
        assert!(ready.model_cache_dir.join("model_quantized.onnx").is_file());
        assert!(ready.model_cache_dir.join("tokenizer/tokenizer.json").is_file());
        assert_eq!(installed(&layout), Some(ready));

        let order: Vec<Step> = steps.iter().map(|p| p.step).fold(Vec::new(), |mut acc, s| {
            if acc.last() != Some(&s) {
                acc.push(s);
            }
            acc
        });
        assert_eq!(order[0], Step::SpaceCheck);
        assert!(order.contains(&Step::Verifying));
        let last = steps.last().unwrap();
        assert_eq!(last.done, last.total);
    }

    #[test]
    fn a_second_run_downloads_nothing() {
        let server = TestServer::start();
        let manifest = serve(&server);
        let dir = tempfile::tempdir().unwrap();
        let layout = Layout::new(dir.path().to_owned());
        run(&layout, &manifest, &mut Vec::new()).unwrap();
        let requests = server.request_count();

        run(&layout, &manifest, &mut Vec::new()).unwrap();

        assert_eq!(server.request_count(), requests);
    }

    #[test]
    fn a_failed_run_resumes_where_it_stopped() {
        let server = TestServer::start();
        let manifest = serve(&server);
        server.set_behaviour("official/model_quantized.onnx", Behaviour::CutAfter(20_000));
        let dir = tempfile::tempdir().unwrap();
        let layout = Layout::new(dir.path().to_owned());

        let error = run(&layout, &manifest, &mut Vec::new()).unwrap_err();
        assert_eq!(error.step(), Step::Downloading);
        assert_eq!(installed(&layout), None);

        server.set_behaviour("official/model_quantized.onnx", Behaviour::Normal);
        run(&layout, &manifest, &mut Vec::new()).unwrap();

        assert!(server.ranges().contains(&Some(20_000)), "the model resumed from its partial file");
        assert!(installed(&layout).is_some());
    }

    #[test]
    fn a_file_that_does_not_match_its_pin_is_not_installed() {
        let server = TestServer::start();
        let mut manifest = serve(&server);
        manifest.model.files[1].sha256 = "0".repeat(64);
        let dir = tempfile::tempdir().unwrap();
        let layout = Layout::new(dir.path().to_owned());

        let error = run(&layout, &manifest, &mut Vec::new()).unwrap_err();

        assert_eq!(error.step(), Step::Verifying);
        assert_eq!(installed(&layout), None);
    }

    #[test]
    fn after_repair_only_the_damaged_file_is_downloaded_again() {
        let server = TestServer::start();
        let manifest = serve(&server);
        let dir = tempfile::tempdir().unwrap();
        let layout = Layout::new(dir.path().to_owned());
        let ready = run(&layout, &manifest, &mut Vec::new()).unwrap();
        let tokenizer = ready.model_cache_dir.join("tokenizer/tokenizer.json");
        let len = std::fs::metadata(&tokenizer).unwrap().len() as usize;
        std::fs::write(&tokenizer, vec![b'x'; len]).unwrap();
        let before = server.request_count();

        install::repair_model(&layout, &manifest.model).unwrap();
        run(&layout, &manifest, &mut Vec::new()).unwrap();

        // The mirror misses first, then the official URL serves it: two requests.
        assert_eq!(server.request_count(), before + 2);
        assert_eq!(std::fs::read(&tokenizer).unwrap(), b"{\"tokenizer\": true}");
    }
}
