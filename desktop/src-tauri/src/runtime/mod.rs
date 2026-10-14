//! What the first run downloads: the model, checked against the sha256s compiled into the
//! app. The backend itself is compiled (`backend/build_nuitka.py`) and ships inside it.

pub mod download;
pub mod install;
pub mod manifest;
pub mod prepare;
#[cfg(test)]
pub(crate) mod test_server;

/// The target triple this app was compiled for; model source lists are keyed by it.
pub const RUNTIME_TARGET: &str = env!("FILESEEK_RUNTIME_TARGET");
