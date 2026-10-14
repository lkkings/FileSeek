//! Every file the first run downloads, compiled into the app (`build.rs` includes
//! `runtime-sources/<target>.json`, made by `release/build_sources.py`).
//!
//! Only the model: the backend is compiled and ships inside the app. Nothing is rehosted:
//! the model is the pinned Hugging Face revision, each file listing its official source
//! and mirrors of it; which one serves it does not matter, because its sha256 is pinned
//! here, inside the signed app.

use serde::Deserialize;

/// The source list format this build reads.
const VERSION: u32 = 3;

#[derive(Debug, Clone, Deserialize, PartialEq, Eq)]
pub struct Manifest {
    pub v: u32,
    pub target: String,
    pub model: ModelSet,
}

#[derive(Debug, Clone, Deserialize, PartialEq, Eq)]
pub struct ModelSet {
    pub id: String,
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
    /// The compiled-in list does not parse: a build problem.
    Malformed(String),
}

impl std::fmt::Display for ManifestError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ManifestError::Unsupported(target) => {
                write!(f, "no model download is available for this platform ({target})")
            }
            ManifestError::Malformed(detail) => write!(f, "the model source list is invalid: {detail}"),
        }
    }
}

impl std::error::Error for ManifestError {}

/// The source list compiled into this build; empty for a platform without one.
const BUILT_IN: &str = include_str!(env!("FILESEEK_RUNTIME_SOURCES"));

/// Parses a source list, refusing one in another format than this build reads
/// (`release/build_sources.py` was not re-run).
pub fn parse(text: &str, target: &str) -> Result<Manifest, ManifestError> {
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
    Ok(manifest)
}

/// This build's source list.
pub fn built_in() -> Result<Manifest, ManifestError> {
    parse(BUILT_IN, super::RUNTIME_TARGET)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_built_in_list_is_for_this_build() {
        let manifest = built_in().expect("re-run release/build_sources.py");

        assert_eq!(manifest.target, crate::runtime::RUNTIME_TARGET);
        assert!(!manifest.model.files.is_empty());
        for file in &manifest.model.files {
            assert!(file.urls.iter().all(|u| u.starts_with("https://")), "{:?}", file.urls);
            assert!(file.urls.iter().all(|u| u.contains("/resolve/")), "{:?}", file.urls);
        }
    }

    #[test]
    fn every_file_lists_the_official_source() {
        let manifest = built_in().unwrap();

        for file in &manifest.model.files {
            assert!(file.urls.iter().any(|u| u.starts_with("https://huggingface.co/")));
        }
    }

    #[test]
    fn a_list_in_another_format_is_refused() {
        let text = BUILT_IN.replacen("\"v\": 3", "\"v\": 2", 1);

        assert!(matches!(parse(&text, "t"), Err(ManifestError::Malformed(_))));
    }

    #[test]
    fn no_list_means_unsupported() {
        assert_eq!(parse("", "riscv64"), Err(ManifestError::Unsupported("riscv64".into())));
    }
}
