//! What licensing keeps on disk, in `<config_dir>/license/`:
//!
//! - `license.json`: `{license_key, token, plan_name}`. Plain text: the token's integrity
//!   is its signature, and a copied key only lets someone else use up the license's
//!   activations, which Keygate caps.
//! - `last_seen_at.txt`: the latest time the app has seen, never moved backwards, to tell
//!   a clock turned back from a real one.
//!
//! A `license.json` that cannot be parsed is moved aside to `license.json.bad-<time>`.

use std::path::{Path, PathBuf};

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Saved {
    pub license_key: String,
    pub token: String,
    /// From the last `verify`; activation does not return it.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub plan_name: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Loaded {
    None,
    Saved(Saved),
    /// Unparseable; moved aside.
    Damaged,
}

pub struct Store {
    dir: PathBuf,
}

impl Store {
    pub fn new(dir: PathBuf) -> Store {
        Store { dir }
    }

    pub fn dir(&self) -> &Path {
        &self.dir
    }

    fn license_file(&self) -> PathBuf {
        self.dir.join("license.json")
    }

    fn last_seen_file(&self) -> PathBuf {
        self.dir.join("last_seen_at.txt")
    }

    pub fn load(&self, now: DateTime<Utc>) -> Loaded {
        let path = self.license_file();
        let Ok(bytes) = std::fs::read(&path) else {
            return Loaded::None;
        };
        match serde_json::from_slice::<Saved>(&bytes) {
            Ok(saved) => Loaded::Saved(saved),
            Err(_) => {
                let stamp = now.format("%Y%m%dT%H%M%S");
                let _ = std::fs::rename(&path, self.dir.join(format!("license.json.bad-{stamp}")));
                Loaded::Damaged
            }
        }
    }

    /// Written to a temporary file and renamed, so a crash never leaves half a license.
    pub fn save(&self, saved: &Saved) -> std::io::Result<()> {
        std::fs::create_dir_all(&self.dir)?;
        let tmp = self.dir.join("license.json.tmp");
        std::fs::write(&tmp, serde_json::to_vec_pretty(saved).unwrap())?;
        restrict_to_owner(&tmp);
        std::fs::rename(&tmp, self.license_file())
    }

    pub fn remove(&self) -> std::io::Result<()> {
        match std::fs::remove_file(self.license_file()) {
            Err(error) if error.kind() != std::io::ErrorKind::NotFound => Err(error),
            _ => Ok(()),
        }
    }

    pub fn last_seen_at(&self) -> Option<DateTime<Utc>> {
        std::fs::read_to_string(self.last_seen_file())
            .ok()?
            .trim()
            .parse()
            .ok()
    }

    /// Moves `last_seen_at` forward to `now`; never back.
    pub fn touch(&self, now: DateTime<Utc>) {
        if self.last_seen_at().is_none_or(|seen| now > seen) {
            let _ = std::fs::create_dir_all(&self.dir);
            let _ = std::fs::write(self.last_seen_file(), now.to_rfc3339());
        }
    }
}

/// The key is a credential: other users of the machine have no business reading it.
#[cfg(unix)]
fn restrict_to_owner(path: &Path) {
    use std::os::unix::fs::PermissionsExt;
    let _ = std::fs::set_permissions(path, std::fs::Permissions::from_mode(0o600));
}

#[cfg(not(unix))]
fn restrict_to_owner(_path: &Path) {
    // `%APPDATA%` is per-user already.
}

#[cfg(test)]
mod tests {
    use super::*;

    fn at(text: &str) -> DateTime<Utc> {
        text.parse().unwrap()
    }

    fn saved() -> Saved {
        Saved {
            license_key: "KG-1".into(),
            token: "p.s".into(),
            plan_name: None,
        }
    }

    #[test]
    fn saves_and_loads() {
        let dir = tempfile::tempdir().unwrap();
        let store = Store::new(dir.path().join("license"));
        assert_eq!(store.load(at("2026-10-01T00:00:00Z")), Loaded::None);

        store.save(&saved()).unwrap();

        assert_eq!(
            store.load(at("2026-10-01T00:00:00Z")),
            Loaded::Saved(saved())
        );
        store.remove().unwrap();
        assert_eq!(store.load(at("2026-10-01T00:00:00Z")), Loaded::None);
        store.remove().unwrap();
    }

    #[cfg(unix)]
    #[test]
    fn the_license_file_is_private() {
        use std::os::unix::fs::PermissionsExt;
        let dir = tempfile::tempdir().unwrap();
        let store = Store::new(dir.path().to_owned());

        store.save(&saved()).unwrap();

        let mode = std::fs::metadata(dir.path().join("license.json"))
            .unwrap()
            .permissions()
            .mode();
        assert_eq!(mode & 0o777, 0o600);
    }

    #[test]
    fn a_damaged_file_is_moved_aside() {
        let dir = tempfile::tempdir().unwrap();
        let store = Store::new(dir.path().to_owned());
        std::fs::write(dir.path().join("license.json"), b"{trunc").unwrap();

        assert_eq!(store.load(at("2026-10-01T08:30:00Z")), Loaded::Damaged);

        assert!(dir.path().join("license.json.bad-20261001T083000").exists());
        assert_eq!(store.load(at("2026-10-01T08:30:00Z")), Loaded::None);
    }

    #[test]
    fn last_seen_only_moves_forward() {
        let dir = tempfile::tempdir().unwrap();
        let store = Store::new(dir.path().to_owned());

        store.touch(at("2026-10-05T00:00:00Z"));
        store.touch(at("2026-10-01T00:00:00Z"));

        assert_eq!(store.last_seen_at(), Some(at("2026-10-05T00:00:00Z")));
    }
}
