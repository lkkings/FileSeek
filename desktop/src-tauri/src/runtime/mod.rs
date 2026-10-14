//! What the first run downloads: the interpreter, dependency wheels, and model, checked
//! against the sha256s compiled into the app. The protected backend ships inside it.

pub mod download;
pub mod install;
pub mod manifest;
pub mod prepare;
pub mod runtime_id;
#[cfg(test)]
pub(crate) mod test_server;

/// The target triple this app was compiled for; model source lists are keyed by it.
pub const RUNTIME_TARGET: &str = env!("FILESEEK_RUNTIME_TARGET");
/// The runtime identity this app expects, computed by `build.rs`.
pub const EXPECTED_RUNTIME_ID: &str = env!("FILESEEK_EXPECTED_RUNTIME_ID");
