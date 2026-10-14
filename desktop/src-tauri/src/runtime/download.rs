//! Resumable, verified downloads.
//!
//! Every file is written to `<dest>.part` and renamed to `<dest>` only once its sha256
//! matches the one pinned in the app. A file may have several URLs (its official source
//! and mirrors of it); they are tried in turn, and a partial download from one continues
//! from another, since the bytes are the same wherever they come from. The backend's model cache checks files for existence only
//! (`shared/utils/model_cache.py`), so a half-written file under the final name would be
//! loaded as if it were complete.

use std::fs::{File, OpenOptions};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Duration;

use sha2::{Digest, Sha256};

const CONNECT_TIMEOUT: Duration = Duration::from_secs(15);
/// No bytes for this long counts as a failed attempt. There is deliberately no overall
/// timeout: a slow connection may need a long time for the runtime pack.
const READ_TIMEOUT: Duration = Duration::from_secs(30);
const CHUNK: usize = 256 * 1024;

/// One file to fetch.
#[derive(Debug, Clone)]
pub struct FileSpec {
    /// Tried in order; each round of retries goes through all of them.
    pub urls: Vec<String>,
    pub dest: PathBuf,
    pub size: u64,
    pub sha256: String,
}

/// How many rounds to try, and how long to wait before each new round.
#[derive(Debug, Clone)]
pub struct RetryPolicy {
    /// Waits before the 2nd, 3rd, ... round through the URLs; the number of retries is its
    /// length.
    pub backoff: Vec<Duration>,
}

impl Default for RetryPolicy {
    /// One round, then three more after 1s, 2s and 4s.
    fn default() -> Self {
        RetryPolicy {
            backoff: vec![
                Duration::from_secs(1),
                Duration::from_secs(2),
                Duration::from_secs(4),
            ],
        }
    }
}

#[derive(Debug)]
pub enum DownloadError {
    Cancelled,
    Http(String),
    Io(std::io::Error),
    /// The finished file's sha256 did not match; the partial file has been discarded.
    ChecksumMismatch {
        expected: String,
        actual: String,
    },
    /// The server sent more or fewer bytes than the manifest says the file has.
    SizeMismatch {
        expected: u64,
        actual: u64,
    },
}

impl std::fmt::Display for DownloadError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            DownloadError::Cancelled => write!(f, "download cancelled"),
            DownloadError::Http(detail) => write!(f, "network error: {detail}"),
            DownloadError::Io(error) => write!(f, "could not write the download: {error}"),
            DownloadError::ChecksumMismatch { expected, actual } => {
                write!(f, "checksum mismatch (expected {expected}, got {actual})")
            }
            DownloadError::SizeMismatch { expected, actual } => {
                write!(f, "size mismatch (expected {expected} bytes, got {actual})")
            }
        }
    }
}

impl std::error::Error for DownloadError {}

impl From<std::io::Error> for DownloadError {
    fn from(error: std::io::Error) -> Self {
        DownloadError::Io(error)
    }
}

pub fn part_path(dest: &Path) -> PathBuf {
    let mut name = dest.file_name().unwrap_or_default().to_os_string();
    name.push(".part");
    dest.with_file_name(name)
}

/// Bytes already on disk for `spec`: the whole file if it is in place, else the partial.
pub fn bytes_present(spec: &FileSpec) -> u64 {
    if spec.dest.is_file() {
        return spec.size;
    }
    std::fs::metadata(part_path(&spec.dest))
        .map(|m| m.len().min(spec.size))
        .unwrap_or(0)
}

pub fn sha256_file(path: &Path) -> std::io::Result<String> {
    let mut file = File::open(path)?;
    let mut hasher = Sha256::new();
    let mut buffer = vec![0u8; 1 << 20];
    loop {
        let n = file.read(&mut buffer)?;
        if n == 0 {
            break;
        }
        hasher.update(&buffer[..n]);
    }
    Ok(hasher
        .finalize()
        .iter()
        .map(|b| format!("{b:02x}"))
        .collect())
}

/// Downloads `spec` with retries. `on_progress` receives the bytes of this file on disk.
///
/// Leaves `<dest>` in place on success. A file already at `<dest>` is trusted: it can only
/// have got there through this function's checksum check.
#[cfg(test)]
pub fn download(
    spec: &FileSpec,
    retry: &RetryPolicy,
    cancel: &AtomicBool,
    on_progress: &mut dyn FnMut(u64),
) -> Result<(), DownloadError> {
    download_with_phases(spec, retry, cancel, on_progress, &mut |_| {})
}

/// Which part of an attempt is running, for a caller that shows them as separate steps.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Phase {
    Fetching,
    Verifying,
}

/// As [`download`], also reporting each switch between fetching and hashing.
pub fn download_with_phases(
    spec: &FileSpec,
    retry: &RetryPolicy,
    cancel: &AtomicBool,
    on_progress: &mut dyn FnMut(u64),
    on_phase: &mut dyn FnMut(Phase),
) -> Result<(), DownloadError> {
    if spec.dest.is_file() {
        on_progress(spec.size);
        return Ok(());
    }
    if let Some(parent) = spec.dest.parent() {
        std::fs::create_dir_all(parent)?;
    }

    if spec.urls.is_empty() {
        return Err(DownloadError::Http("no source for this file".into()));
    }
    let mut round = 0;
    loop {
        let mut last_error = None;
        for url in &spec.urls {
            match attempt_once(spec, url, cancel, on_progress, on_phase) {
                Ok(()) => return Ok(()),
                Err(DownloadError::Cancelled) => return Err(DownloadError::Cancelled),
                Err(error) => last_error = Some(error),
            }
        }
        let Some(wait) = retry.backoff.get(round) else {
            return Err(last_error.expect("at least one URL was tried"));
        };
        round += 1;
        sleep_unless_cancelled(*wait, cancel)?;
    }
}

fn sleep_unless_cancelled(wait: Duration, cancel: &AtomicBool) -> Result<(), DownloadError> {
    let step = Duration::from_millis(50);
    let mut waited = Duration::ZERO;
    while waited < wait {
        if cancel.load(Ordering::SeqCst) {
            return Err(DownloadError::Cancelled);
        }
        std::thread::sleep(step.min(wait - waited));
        waited += step;
    }
    Ok(())
}

fn attempt_once(
    spec: &FileSpec,
    url: &str,
    cancel: &AtomicBool,
    on_progress: &mut dyn FnMut(u64),
    on_phase: &mut dyn FnMut(Phase),
) -> Result<(), DownloadError> {
    let part = part_path(&spec.dest);
    let mut have = std::fs::metadata(&part).map(|m| m.len()).unwrap_or(0);
    if have > spec.size {
        // Cannot be a prefix of the right file.
        std::fs::remove_file(&part)?;
        have = 0;
    }

    on_phase(Phase::Fetching);
    if have < spec.size {
        fetch_into(spec, url, &part, have, cancel, on_progress)?;
    }

    on_phase(Phase::Verifying);
    let actual_size = std::fs::metadata(&part)?.len();
    if actual_size != spec.size {
        return Err(DownloadError::SizeMismatch {
            expected: spec.size,
            actual: actual_size,
        });
    }
    let actual = sha256_file(&part)?;
    if !actual.eq_ignore_ascii_case(&spec.sha256) {
        // Some byte is wrong and there is no telling which: start over next attempt.
        std::fs::remove_file(&part)?;
        on_progress(0);
        return Err(DownloadError::ChecksumMismatch {
            expected: spec.sha256.clone(),
            actual,
        });
    }
    std::fs::rename(&part, &spec.dest)?;
    on_progress(spec.size);
    Ok(())
}

fn fetch_into(
    spec: &FileSpec,
    url: &str,
    part: &Path,
    have: u64,
    cancel: &AtomicBool,
    on_progress: &mut dyn FnMut(u64),
) -> Result<(), DownloadError> {
    let agent = ureq::AgentBuilder::new()
        .timeout_connect(CONNECT_TIMEOUT)
        .timeout_read(READ_TIMEOUT)
        .build();
    let mut request = agent.get(url);
    if have > 0 {
        request = request.set("Range", &format!("bytes={have}-"));
    }
    let response = request
        .call()
        .map_err(|e| DownloadError::Http(e.to_string()))?;

    // 206 continues the partial file; anything else is the whole body from byte 0, which
    // is what a server that ignores `Range` sends.
    let resumed = have > 0 && response.status() == 206;
    let mut file = if resumed {
        OpenOptions::new().append(true).open(part)?
    } else {
        File::create(part)?
    };
    let mut written = if resumed { have } else { 0 };
    on_progress(written);

    let mut body = response.into_reader().take(spec.size - written + 1);
    let mut buffer = vec![0u8; CHUNK];
    loop {
        if cancel.load(Ordering::SeqCst) {
            file.flush()?;
            return Err(DownloadError::Cancelled);
        }
        let n = body
            .read(&mut buffer)
            .map_err(|e| DownloadError::Http(e.to_string()))?;
        if n == 0 {
            break;
        }
        file.write_all(&buffer[..n])?;
        written += n as u64;
        on_progress(written.min(spec.size));
    }
    file.flush()?;
    if written < spec.size {
        return Err(DownloadError::Http(format!(
            "connection closed after {written} of {} bytes",
            spec.size
        )));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::runtime::test_server::{Behaviour, TestServer};

    fn body(len: usize) -> Vec<u8> {
        (0..len).map(|i| (i % 251) as u8).collect()
    }

    fn sha(bytes: &[u8]) -> String {
        Sha256::digest(bytes)
            .iter()
            .map(|b| format!("{b:02x}"))
            .collect()
    }

    fn no_wait(retries: usize) -> RetryPolicy {
        RetryPolicy {
            backoff: vec![Duration::ZERO; retries],
        }
    }

    fn spec(server: &TestServer, dir: &Path, name: &str, data: &[u8]) -> FileSpec {
        FileSpec {
            urls: vec![server.url(name)],
            dest: dir.join(name),
            size: data.len() as u64,
            sha256: sha(data),
        }
    }

    #[test]
    fn downloads_and_renames_a_verified_file() {
        let server = TestServer::start();
        let data = body(600_000);
        server.put("a.bin", data.clone());
        let dir = tempfile::tempdir().unwrap();
        let spec = spec(&server, dir.path(), "a.bin", &data);

        let mut last = 0;
        download(&spec, &no_wait(0), &AtomicBool::new(false), &mut |n| {
            last = n
        })
        .unwrap();

        assert_eq!(std::fs::read(&spec.dest).unwrap(), data);
        assert!(!part_path(&spec.dest).exists());
        assert_eq!(last, data.len() as u64);
    }

    #[test]
    fn resumes_a_partial_download_with_a_range_request() {
        let server = TestServer::start();
        let data = body(600_000);
        server.put("a.bin", data.clone());
        let dir = tempfile::tempdir().unwrap();
        let spec = spec(&server, dir.path(), "a.bin", &data);
        // As left behind by an app that was closed mid-download.
        std::fs::write(part_path(&spec.dest), &data[..250_000]).unwrap();

        download(&spec, &no_wait(0), &AtomicBool::new(false), &mut |_| {}).unwrap();

        assert_eq!(server.ranges(), vec![Some(250_000)]);
        assert_eq!(std::fs::read(&spec.dest).unwrap(), data);
    }

    #[test]
    fn interrupted_transfer_is_resumed_on_the_next_attempt() {
        let server = TestServer::start();
        let data = body(600_000);
        server.put("a.bin", data.clone());
        server.set_behaviour("a.bin", Behaviour::CutAfter(100_000));
        let dir = tempfile::tempdir().unwrap();
        let spec = spec(&server, dir.path(), "a.bin", &data);

        let first = download(&spec, &no_wait(0), &AtomicBool::new(false), &mut |_| {});
        assert!(matches!(first, Err(DownloadError::Http(_))));
        assert_eq!(
            bytes_present(&spec),
            100_000,
            "partial bytes are kept for resuming"
        );

        server.set_behaviour("a.bin", Behaviour::Normal);
        download(&spec, &no_wait(0), &AtomicBool::new(false), &mut |_| {}).unwrap();

        assert_eq!(server.ranges().last(), Some(&Some(100_000)));
        assert_eq!(std::fs::read(&spec.dest).unwrap(), data);
    }

    #[test]
    fn starts_over_when_the_server_ignores_range() {
        let server = TestServer::start();
        let data = body(300_000);
        server.put("a.bin", data.clone());
        server.set_behaviour("a.bin", Behaviour::IgnoreRange);
        let dir = tempfile::tempdir().unwrap();
        let spec = spec(&server, dir.path(), "a.bin", &data);
        std::fs::write(part_path(&spec.dest), &data[..100_000]).unwrap();

        download(&spec, &no_wait(0), &AtomicBool::new(false), &mut |_| {}).unwrap();

        // Appending the full 200 body to the partial file would have produced 400k bytes.
        assert_eq!(std::fs::read(&spec.dest).unwrap(), data);
    }

    #[test]
    fn checksum_mismatch_discards_the_file_and_downloads_again() {
        let server = TestServer::start();
        let good = body(200_000);
        let mut bad = good.clone();
        bad[123] ^= 0xff;
        server.put("a.bin", bad);
        let dir = tempfile::tempdir().unwrap();
        let spec = spec(&server, dir.path(), "a.bin", &good);

        let result = download(&spec, &no_wait(2), &AtomicBool::new(false), &mut |_| {});

        assert!(matches!(
            result,
            Err(DownloadError::ChecksumMismatch { .. })
        ));
        // One attempt plus two retries, each from scratch.
        assert_eq!(server.ranges(), vec![None, None, None]);
        assert!(!spec.dest.exists());
        assert!(!part_path(&spec.dest).exists());
    }

    #[test]
    fn a_failing_mirror_falls_through_to_the_next_source() {
        let server = TestServer::start();
        let data = body(200_000);
        server.put("official/a.bin", data.clone());
        let dir = tempfile::tempdir().unwrap();
        let spec = FileSpec {
            urls: vec![server.url("mirror/a.bin"), server.url("official/a.bin")],
            dest: dir.path().join("a.bin"),
            size: data.len() as u64,
            sha256: sha(&data),
        };

        download(&spec, &no_wait(0), &AtomicBool::new(false), &mut |_| {}).unwrap();

        assert_eq!(std::fs::read(&spec.dest).unwrap(), data);
        assert_eq!(
            server.request_count(),
            2,
            "the mirror once, then the official source"
        );
    }

    #[test]
    fn a_mirror_serving_other_bytes_is_not_trusted() {
        let server = TestServer::start();
        let data = body(50_000);
        let mut tampered = data.clone();
        tampered[100] ^= 0xff;
        server.put("mirror/a.bin", tampered);
        server.put("official/a.bin", data.clone());
        let dir = tempfile::tempdir().unwrap();
        let spec = FileSpec {
            urls: vec![server.url("mirror/a.bin"), server.url("official/a.bin")],
            dest: dir.path().join("a.bin"),
            size: data.len() as u64,
            sha256: sha(&data),
        };

        download(&spec, &no_wait(0), &AtomicBool::new(false), &mut |_| {}).unwrap();

        assert_eq!(std::fs::read(&spec.dest).unwrap(), data);
    }

    #[test]
    fn gives_up_after_the_configured_retries() {
        let server = TestServer::start();
        let dir = tempfile::tempdir().unwrap();
        let spec = FileSpec {
            urls: vec![server.url("missing.bin")],
            dest: dir.path().join("missing.bin"),
            size: 10,
            sha256: sha(b"0123456789"),
        };

        let result = download(
            &spec,
            &RetryPolicy::default_without_waiting(),
            &AtomicBool::new(false),
            &mut |_| {},
        );

        assert!(matches!(result, Err(DownloadError::Http(_))));
        assert_eq!(server.request_count(), 4, "one attempt and three retries");
    }

    #[test]
    fn a_file_already_in_place_is_not_downloaded_again() {
        let server = TestServer::start();
        let data = body(1000);
        let dir = tempfile::tempdir().unwrap();
        let spec = spec(&server, dir.path(), "a.bin", &data);
        std::fs::write(&spec.dest, &data).unwrap();

        download(&spec, &no_wait(0), &AtomicBool::new(false), &mut |_| {}).unwrap();

        assert_eq!(server.request_count(), 0);
    }

    #[test]
    fn cancelling_keeps_the_partial_file() {
        let server = TestServer::start();
        let data = body(2_000_000);
        server.put("a.bin", data.clone());
        let dir = tempfile::tempdir().unwrap();
        let spec = spec(&server, dir.path(), "a.bin", &data);
        let cancel = AtomicBool::new(false);

        let result = download(&spec, &no_wait(0), &cancel, &mut |n| {
            if n > 0 {
                cancel.store(true, Ordering::SeqCst);
            }
        });

        assert!(matches!(result, Err(DownloadError::Cancelled)));
        assert!(bytes_present(&spec) > 0);
        assert!(!spec.dest.exists());
    }

    impl RetryPolicy {
        /// The default number of retries with no waiting, so the test stays fast.
        fn default_without_waiting() -> Self {
            RetryPolicy {
                backoff: vec![Duration::ZERO; RetryPolicy::default().backoff.len()],
            }
        }
    }
}
