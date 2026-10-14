//! Every file the first run downloads, compiled into the app (`build.rs` includes
//! `runtime-sources/<target>.json`, made by `release/build_sources.py`).
//!
//! Nothing is rehosted: the interpreter comes from python-build-standalone, the backend's
//! dependencies are the exact wheels `backend/uv.lock` pins, and the model is the pinned
//! Hugging Face revision. Each file lists its official source and mirrors; which one
//! serves it does not matter, because its sha256 is pinned here, inside the signed app.

use serde::Deserialize;

/// The source list format this build reads.
const VERSION: u32 = 4;

#[derive(Debug, Clone, Deserialize, PartialEq, Eq)]
pub struct Manifest {
    pub v: u32,
    pub runtime_id: String,
    pub target: String,
    pub python: PythonArchive,
    pub wheels: Vec<Wheel>,
    /// Estimate of the installed size, for the free-space check.
    pub unpacked_size: u64,
    pub model: ModelSet,
}

/// A python-build-standalone `install_only_stripped` archive (`.tar.gz`).
#[derive(Debug, Clone, Deserialize, PartialEq, Eq)]
pub struct PythonArchive {
    pub file: String,
    pub size: u64,
    pub sha256: String,
    /// Tried in order.
    pub urls: Vec<String>,
    /// The interpreter, relative to the unpacked archive's root.
    pub interpreter: String,
}

#[derive(Debug, Clone, Deserialize, PartialEq, Eq)]
pub struct Wheel {
    pub file: String,
    pub size: u64,
    pub sha256: String,
    pub urls: Vec<String>,
}

#[derive(Debug, Clone, Deserialize, PartialEq, Eq)]
pub struct ModelSet {
    /// Content-defined identity; changes when a file hash, path, or size changes.
    pub id: String,
    /// Stable human-readable model name.
    pub name: String,
    pub files: Vec<ModelFile>,
}

#[derive(Debug, Clone, Deserialize, PartialEq, Eq)]
pub struct ModelFile {
    /// Where the file goes, relative to the model's directory.
    pub path: String,
    pub size: u64,
    pub sha256: String,
    pub urls: Vec<String>,
}

#[derive(Debug, PartialEq, Eq)]
pub enum ManifestError {
    /// This build has no source list: the platform is not supported.
    Unsupported(String),
    /// The compiled-in list does not parse, or is for another runtime: a build problem.
    Malformed(String),
}

impl std::fmt::Display for ManifestError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ManifestError::Unsupported(target) => {
                write!(f, "no runtime is available for this platform ({target})")
            }
            ManifestError::Malformed(detail) => {
                write!(f, "the runtime source list is invalid: {detail}")
            }
        }
    }
}

impl std::error::Error for ManifestError {}

/// The source list compiled into this build; empty for a platform without one.
const BUILT_IN: &str = include_str!(env!("FILESEEK_RUNTIME_SOURCES"));

/// Parses a source list, refusing one made for another runtime than this build expects.
pub fn parse(
    text: &str,
    expected_runtime_id: &str,
    target: &str,
) -> Result<Manifest, ManifestError> {
    if text.trim().is_empty() {
        return Err(ManifestError::Unsupported(target.to_owned()));
    }
    let manifest: Manifest =
        serde_json::from_str(text).map_err(|e| ManifestError::Malformed(e.to_string()))?;
    if manifest.v != VERSION {
        return Err(ManifestError::Malformed(format!(
            "version {}, this build reads {VERSION}: re-run release/build_sources.py",
            manifest.v
        )));
    }
    if manifest.runtime_id != expected_runtime_id {
        return Err(ManifestError::Malformed(format!(
            "made for {}, this build runs {expected_runtime_id}: re-run release/build_sources.py",
            manifest.runtime_id
        )));
    }
    Ok(manifest)
}

/// This build's source list.
pub fn built_in() -> Result<Manifest, ManifestError> {
    parse(BUILT_IN, super::EXPECTED_RUNTIME_ID, super::RUNTIME_TARGET)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_built_in_list_is_for_this_build() {
        let manifest = built_in().expect("re-run release/build_sources.py");

        assert_eq!(manifest.runtime_id, crate::runtime::EXPECTED_RUNTIME_ID);
        assert_eq!(manifest.target, crate::runtime::RUNTIME_TARGET);
        assert!(!manifest.wheels.is_empty());
        assert!(manifest
            .python
            .urls
            .iter()
            .all(|url| url.starts_with("https://")));
        for file in &manifest.model.files {
            assert!(
                file.urls.iter().all(|url| url.contains("/resolve/")),
                "{:?}",
                file.urls
            );
        }
    }

    #[test]
    fn every_file_lists_the_official_source() {
        let manifest = built_in().unwrap();

        assert!(manifest
            .python
            .urls
            .iter()
            .any(|url| url.starts_with("https://github.com/astral-sh/")));
        for wheel in &manifest.wheels {
            assert!(
                wheel
                    .urls
                    .iter()
                    .any(|url| url.starts_with("https://files.pythonhosted.org/")),
                "{}",
                wheel.file
            );
        }
        for file in &manifest.model.files {
            assert!(file
                .urls
                .iter()
                .any(|url| url.starts_with("https://huggingface.co/")));
        }
    }

    #[test]
    fn a_list_for_another_runtime_is_refused() {
        let text = BUILT_IN.replace(crate::runtime::EXPECTED_RUNTIME_ID, "rt-other");

        assert!(matches!(
            parse(&text, crate::runtime::EXPECTED_RUNTIME_ID, "t"),
            Err(ManifestError::Malformed(_))
        ));
    }

    #[test]
    fn a_list_in_another_format_is_refused() {
        let text = BUILT_IN.replacen("\"v\": 4", "\"v\": 3", 1);

        assert!(matches!(
            parse(&text, crate::runtime::EXPECTED_RUNTIME_ID, "t"),
            Err(ManifestError::Malformed(_))
        ));
    }

    #[test]
    fn no_list_means_unsupported() {
        assert_eq!(
            parse("", "rt", "riscv64"),
            Err(ManifestError::Unsupported("riscv64".into()))
        );
    }
}
