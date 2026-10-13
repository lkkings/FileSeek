//! The backend runtime's identity, shared between `build.rs` and the crate.
//!
//! Mirrors `release/runtime_id.py`: `rt-` + the first 16 hex digits of
//! sha256(uv.lock with CRLF folded to LF, NUL, python version, NUL, pbs release).
//! Both sides assert the same fixed sample, so a change to one that is not made to the
//! other fails a test instead of silently making every app download the wrong runtime.

use sha2::{Digest, Sha256};

// Called by `build.rs`, which includes this file; the crate itself only tests it.
#[allow(dead_code)]
pub fn compute_runtime_id(lock: &[u8], python_version: &str, pbs_release: &str) -> String {
    let mut normalized = Vec::with_capacity(lock.len());
    let mut i = 0;
    while i < lock.len() {
        if lock[i] == b'\r' && lock.get(i + 1) == Some(&b'\n') {
            i += 1;
            continue;
        }
        normalized.push(lock[i]);
        i += 1;
    }

    let mut hasher = Sha256::new();
    hasher.update(&normalized);
    hasher.update(b"\0");
    hasher.update(python_version.as_bytes());
    hasher.update(b"\0");
    hasher.update(pbs_release.as_bytes());
    let digest = hasher.finalize();
    let hex: String = digest.iter().take(8).map(|b| format!("{b:02x}")).collect();
    format!("rt-{hex}")
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Same sample and expected value as `release/tests/test_runtime_id.py`.
    #[test]
    fn matches_the_python_implementation() {
        let id = compute_runtime_id(b"version = 1\n[[package]]\n", "3.12.15", "20261001");
        assert_eq!(id, "rt-d33d847dcabf2a87");
    }

    #[test]
    fn crlf_and_lf_lockfiles_get_the_same_id() {
        let lf = compute_runtime_id(b"a\nb\n", "3.12.15", "20261001");
        let crlf = compute_runtime_id(b"a\r\nb\r\n", "3.12.15", "20261001");
        assert_eq!(lf, crlf);
    }

    #[test]
    fn python_version_changes_the_id() {
        let a = compute_runtime_id(b"x", "3.12.15", "20261001");
        let b = compute_runtime_id(b"x", "3.12.16", "20261001");
        assert_ne!(a, b);
    }
}
