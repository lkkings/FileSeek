//! Where the model lives on disk, and how it gets there.
//!
//! ```text
//! <data_dir>/models/<model_id>/   model files, `.complete` once all present
//! <data_dir>/models/current.json  the model the backend runs with
//! <data_dir>/runtime/             left by versions that downloaded a Python runtime; removed
//! ```
//!
//! Checking whether the model is installed reads `.complete` and file sizes only, so an
//! installed app starts without a network connection.

use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};

use super::download::sha256_file;
use super::manifest::ModelSet;

const COMPLETE: &str = ".complete";
/// Free space beyond the computed need, so the disk is not filled to the last byte.
const SPACE_MARGIN_PERCENT: u64 = 10;

#[derive(Debug, Clone)]
pub struct Layout {
    pub data_dir: PathBuf,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
struct InstalledModel {
    files: Vec<(String, u64)>,
}

impl Layout {
    pub fn new(data_dir: PathBuf) -> Layout {
        Layout { data_dir }
    }

    pub fn model_dir(&self, model_id: &str) -> PathBuf {
        self.data_dir.join("models").join(model_id)
    }

    /// Where versions before the compiled backend installed their Python runtime.
    pub fn legacy_runtime_dir(&self) -> PathBuf {
        self.data_dir.join("runtime")
    }

    /// Whether every model file recorded at install time is present at its size.
    pub fn model_installed(&self, model_id: &str) -> bool {
        let dir = self.model_dir(model_id);
        let Some(record) = std::fs::read(dir.join(COMPLETE))
            .ok()
            .and_then(|bytes| serde_json::from_slice::<InstalledModel>(&bytes).ok())
        else {
            return false;
        };
        record.files.iter().all(|(path, size)| {
            std::fs::metadata(dir.join(path))
                .map(|m| m.len() == *size)
                .unwrap_or(false)
        })
    }
}

/// Records that every model file is in place. Call once all of them downloaded.
pub fn mark_model_installed(layout: &Layout, model: &ModelSet) -> std::io::Result<()> {
    let record = InstalledModel {
        files: model
            .files
            .iter()
            .map(|f| (f.path.clone(), f.size))
            .collect(),
    };
    write_atomically(
        &layout.model_dir(&model.id).join(COMPLETE),
        &serde_json::to_vec(&record).unwrap(),
    )
}

/// Makes the next start check the model again: forgets that it is installed and deletes
/// every file whose contents no longer match its pin, so only those are downloaded again.
///
/// The download step trusts a file already in place, so dropping the marker alone would
/// not replace a damaged file. Hashing is slow on the 834 MB model, but repair is rare and
/// cheaper than downloading it all again.
pub fn repair_model(layout: &Layout, model: &ModelSet) -> std::io::Result<()> {
    let dir = layout.model_dir(&model.id);
    remove_file_if_present(&dir.join(COMPLETE))?;
    for file in &model.files {
        let path = dir.join(&file.path);
        match sha256_file(&path) {
            Ok(sha256) if sha256 == file.sha256 => {}
            Ok(_) => std::fs::remove_file(&path)?,
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
            Err(error) => return Err(error),
        }
    }
    Ok(())
}

/// Deletes the Python runtime an earlier version downloaded. Nothing uses it any more.
pub fn remove_legacy_runtime(layout: &Layout) -> std::io::Result<()> {
    match std::fs::remove_dir_all(layout.legacy_runtime_dir()) {
        Err(error) if error.kind() != std::io::ErrorKind::NotFound => Err(error),
        _ => Ok(()),
    }
}

fn write_atomically(path: &Path, bytes: &[u8]) -> std::io::Result<()> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let tmp = path.with_extension("tmp");
    std::fs::write(&tmp, bytes)?;
    std::fs::rename(tmp, path)
}

fn remove_file_if_present(path: &Path) -> std::io::Result<()> {
    match std::fs::remove_file(path) {
        Err(error) if error.kind() != std::io::ErrorKind::NotFound => Err(error),
        _ => Ok(()),
    }
}

/// Free space needed under `data_dir` to finish downloading, margin included.
pub fn required_space(download_remaining: u64) -> u64 {
    download_remaining + download_remaining * SPACE_MARGIN_PERCENT / 100
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct InsufficientSpace {
    pub path: PathBuf,
    pub required: u64,
    pub available: u64,
}

/// Free space on the volume `path` is on (or will be on, once created).
pub fn available_space(path: &Path) -> std::io::Result<u64> {
    let existing = path
        .ancestors()
        .find(|p| p.exists())
        .unwrap_or_else(|| Path::new("/"));
    fs4::available_space(existing)
}

pub fn check_space(path: &Path, required: u64, available: u64) -> Result<(), InsufficientSpace> {
    if available >= required {
        Ok(())
    } else {
        Err(InsufficientSpace {
            path: path.to_owned(),
            required,
            available,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::runtime::manifest::ModelFile;
    use crate::runtime::test_server::sha256_hex;

    fn model_with(files: &[(&str, &[u8])]) -> ModelSet {
        ModelSet {
            id: "m".into(),
            files: files
                .iter()
                .map(|(path, bytes)| ModelFile {
                    path: (*path).into(),
                    urls: vec!["u".into()],
                    size: bytes.len() as u64,
                    sha256: sha256_hex(bytes),
                })
                .collect(),
        }
    }

    fn put(layout: &Layout, path: &str, bytes: &[u8]) -> PathBuf {
        let file = layout.model_dir("m").join(path);
        std::fs::create_dir_all(file.parent().unwrap()).unwrap();
        std::fs::write(&file, bytes).unwrap();
        file
    }

    #[test]
    fn model_is_installed_only_while_every_file_is_present_at_its_size() {
        let dir = tempfile::tempdir().unwrap();
        let layout = Layout::new(dir.path().to_owned());
        let model = model_with(&[("tokenizer/t.json", b"abc")]);
        let file = put(&layout, "tokenizer/t.json", b"abc");
        assert!(!layout.model_installed("m"), "no marker yet");

        mark_model_installed(&layout, &model).unwrap();
        assert!(layout.model_installed("m"));

        std::fs::write(&file, b"ab").unwrap();
        assert!(!layout.model_installed("m"));
    }

    #[test]
    fn repair_deletes_only_the_files_that_no_longer_match() {
        let dir = tempfile::tempdir().unwrap();
        let layout = Layout::new(dir.path().to_owned());
        let model = model_with(&[("good.bin", b"good"), ("bad.bin", b"fine")]);
        let good = put(&layout, "good.bin", b"good");
        let bad = put(&layout, "bad.bin", b"rot!");
        mark_model_installed(&layout, &model).unwrap();
        assert!(layout.model_installed("m"), "same sizes: looks installed");

        repair_model(&layout, &model).unwrap();

        assert!(!layout.model_installed("m"));
        assert!(good.is_file());
        assert!(!bad.exists());
    }

    #[test]
    fn repair_tolerates_missing_files() {
        let dir = tempfile::tempdir().unwrap();
        let layout = Layout::new(dir.path().to_owned());

        repair_model(&layout, &model_with(&[("gone.bin", b"x")])).unwrap();
    }

    #[test]
    fn the_legacy_runtime_is_removed_and_its_absence_is_fine() {
        let dir = tempfile::tempdir().unwrap();
        let layout = Layout::new(dir.path().to_owned());
        let python = layout.legacy_runtime_dir().join("rt-1/python/bin/python3");
        std::fs::create_dir_all(python.parent().unwrap()).unwrap();
        std::fs::write(&python, b"#!/bin/sh\n").unwrap();

        remove_legacy_runtime(&layout).unwrap();
        assert!(!layout.legacy_runtime_dir().exists());

        remove_legacy_runtime(&layout).unwrap();
    }

    #[test]
    fn space_check_counts_what_is_left_to_download() {
        const MB: u64 = 1_000_000;
        let required = required_space(834 * MB);
        assert_eq!(required, 834 * MB + 834 * MB / 10);

        assert_eq!(
            check_space(Path::new("/data"), required, 800 * MB),
            Err(InsufficientSpace {
                path: "/data".into(),
                required,
                available: 800 * MB
            })
        );
        assert_eq!(required_space(0), 0, "model installed: nothing to fetch");
    }

    #[test]
    fn available_space_works_for_a_path_that_does_not_exist_yet() {
        let dir = tempfile::tempdir().unwrap();
        assert!(available_space(&dir.path().join("not/yet/created")).unwrap() > 0);
    }
}
