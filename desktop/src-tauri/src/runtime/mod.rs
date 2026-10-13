//! The backend runtime: a relocatable Python with the backend's dependencies installed,
//! downloaded on first run instead of shipped in the installer (see the
//! `backend-runtime` spec in `openspec/changes/commercial-licensing-and-updates`).

pub mod download;
pub mod install;
pub mod manifest;
pub mod prepare;
pub mod runtime_id;
#[cfg(test)]
pub(crate) mod test_server;

/// The runtime this build of the app runs the backend on, computed by `build.rs`.
pub const EXPECTED_RUNTIME_ID: &str = env!("FILESEEK_RUNTIME_ID");

/// The target triple this app was compiled for; runtime packs are keyed by it.
pub const RUNTIME_TARGET: &str = env!("FILESEEK_RUNTIME_TARGET");

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn baked_id_matches_the_lockfile_in_the_repo() {
        let repo = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
        let lock = std::fs::read(repo.join("backend/uv.lock")).unwrap();
        let config: serde_json::Value =
            serde_json::from_slice(&std::fs::read(repo.join("release/runtime.json")).unwrap())
                .unwrap();
        let id = runtime_id::compute_runtime_id(
            &lock,
            config["python_version"].as_str().unwrap(),
            config["pbs_release"].as_str().unwrap(),
        );
        assert_eq!(EXPECTED_RUNTIME_ID, id);
    }
}
