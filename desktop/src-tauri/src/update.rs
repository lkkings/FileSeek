//! App updates through `tauri-plugin-updater` from the self-hosted Keygate's feed, plus
//! the runtime they may need.
//!
//! - **Feed**: `{keygate}/api/v1/releases/{slug}/upgrade.json?platform={{target}}-{{arch}}`,
//!   with the license key in the `X-License-Key` header (never the URL: it would end up in
//!   proxy and CDN logs). Keygate signs every artifact; the plugin checks it with
//!   Keygate's "Public key for Tauri". Whether the feed needs a license, and which
//!   versions a license's update period covers, Keygate decides: anything but an update
//!   (204, 401, 404) reads as "nothing new".
//! - **Required update**: Keygate adds `minimum_supported_version` and
//!   `minimum_supported_message` to the response. Below it, the UI shows a banner that
//!   cannot be closed. Nothing is disabled.
//! - **Runtime**: Keygate carries the app's own code only. A version whose dependencies
//!   changed downloads them from their official sources on its first start, through the
//!   same setup screen as a first install; one whose dependencies did not change starts
//!   straight away.
//!
//! Checks run only while licensed: the backend is not running otherwise either.

use std::io::Write as _;
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Duration;

use serde::Serialize;
use tauri::{AppHandle, Emitter};
use tauri_plugin_updater::UpdaterExt;

pub const EVENT_NAME: &str = "update";
const FIRST_CHECK_DELAY: Duration = Duration::from_secs(30);
const CHECK_INTERVAL: Duration = Duration::from_secs(24 * 60 * 60);

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Phase {
    /// A debug build: `tauri dev` is never an installed copy.
    Disabled,
    Idle,
    Checking,
    UpToDate,
    Available,
    Downloading,
    /// Downloaded and verified; restart to install.
    Ready,
    Failed,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct UpdateInfo {
    pub version: String,
    pub notes: Option<String>,
    /// This version is below Keygate's minimum supported version: the banner cannot be
    /// closed until the update is installed.
    pub required: bool,
    /// Keygate's message for a required update.
    pub required_message: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct UpdateStatus {
    pub current_version: String,
    pub phase: Phase,
    pub update: Option<UpdateInfo>,
    pub done: u64,
    pub total: Option<u64>,
    pub error: Option<String>,
}

/// Reads Keygate's required-update fields from the plugin's raw JSON. A missing or
/// unparseable minimum makes it a normal update: a bad field never locks anyone in.
pub fn describe(
    version: &str,
    notes: Option<String>,
    raw: &serde_json::Value,
    current: &str,
) -> UpdateInfo {
    let minimum = raw
        .get("minimum_supported_version")
        .and_then(|v| v.as_str())
        .and_then(|v| semver::Version::parse(v.trim_start_matches('v')).ok());
    let required = match (minimum, semver::Version::parse(current)) {
        (Some(minimum), Ok(current)) => current < minimum,
        _ => false,
    };
    let required_message = raw
        .get("minimum_supported_message")
        .and_then(|v| v.as_str())
        .filter(|m| required && !m.trim().is_empty())
        .map(str::to_owned);
    UpdateInfo {
        version: version.to_owned(),
        notes,
        required,
        required_message,
    }
}

/// Asks whether the app is licensed and for the key to send. `None`: not licensed.
pub type LicenseKey = Box<dyn Fn() -> Option<String> + Send + Sync>;

/// Keygate's Tauri feed. `{{target}}-{{arch}}` is filled in by the plugin
/// (`darwin-aarch64`, `windows-x86_64`, ...), which Keygate accepts.
pub fn feed_url(base_url: &str, slug: &str) -> String {
    format!(
        "{}/api/v1/releases/{slug}/upgrade.json?platform={{{{target}}}}-{{{{arch}}}}",
        base_url.trim_end_matches('/')
    )
}

/// One line of `update.log`.
pub fn log_line(
    at: chrono::DateTime<chrono::Utc>,
    current: &str,
    target: Option<&str>,
    event: &str,
) -> String {
    format!(
        "{} current={current} target={} {event}\n",
        at.to_rfc3339(),
        target.unwrap_or("-")
    )
}

pub struct Updates {
    app: AppHandle,
    status: Mutex<UpdateStatus>,
    /// The checked update and, once downloaded, its verified bytes.
    pending: tokio::sync::Mutex<Option<(tauri_plugin_updater::Update, Option<Vec<u8>>)>>,
    cancel: Arc<AtomicBool>,
    log: PathBuf,
    license_key: LicenseKey,
}

pub type SharedUpdates = Arc<Updates>;

impl Updates {
    pub fn new(app: AppHandle, log: PathBuf, license_key: LicenseKey, enabled: bool) -> Updates {
        Updates {
            app,
            status: Mutex::new(UpdateStatus {
                current_version: env!("CARGO_PKG_VERSION").to_owned(),
                phase: if enabled {
                    Phase::Idle
                } else {
                    Phase::Disabled
                },
                update: None,
                done: 0,
                total: None,
                error: None,
            }),
            pending: tokio::sync::Mutex::new(None),
            cancel: Arc::new(AtomicBool::new(false)),
            log,
            license_key,
        }
    }

    pub fn status(&self) -> UpdateStatus {
        self.status.lock().unwrap().clone()
    }

    fn set(&self, change: impl FnOnce(&mut UpdateStatus)) {
        let snapshot = {
            let mut status = self.status.lock().unwrap();
            change(&mut status);
            status.clone()
        };
        let _ = self.app.emit(EVENT_NAME, snapshot);
    }

    /// The plugin's updater, pointed at Keygate's feed with the license key in a header.
    /// The address and key are build-time (see `build.rs`), so `tauri.conf.json` carries
    /// neither.
    fn updater(
        &self,
        license_key: &str,
    ) -> tauri_plugin_updater::Result<tauri_plugin_updater::Updater> {
        let endpoint = feed_url(env!("KEYGATE_BASE_URL"), env!("KEYGATE_PRODUCT_SLUG"))
            .parse()
            .map_err(|_| tauri_plugin_updater::Error::EmptyEndpoints)?;
        self.app
            .updater_builder()
            .endpoints(vec![endpoint])?
            .header("X-License-Key", license_key)?
            .build()
    }

    fn record(&self, event: &str) {
        let status = self.status();
        let target = status.update.as_ref().map(|u| u.version.as_str());
        let line = log_line(chrono::Utc::now(), &status.current_version, target, event);
        if let Some(dir) = self.log.parent() {
            let _ = std::fs::create_dir_all(dir);
        }
        if let Ok(mut file) = std::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.log)
        {
            let _ = file.write_all(line.as_bytes());
        }
    }

    fn fail(&self, error: String) {
        self.set(|s| {
            s.phase = Phase::Failed;
            s.error = Some(error.clone());
        });
        self.record(&format!("failed: {error}"));
    }

    pub async fn check(&self) {
        if self.status().phase == Phase::Disabled {
            return;
        }
        let Some(license_key) = (self.license_key)() else {
            // The next round, or the user's "check now" once activated, tries again.
            return;
        };
        // Do not throw away a download in progress or one waiting for a restart.
        if matches!(self.status().phase, Phase::Downloading | Phase::Ready) {
            return;
        }
        self.set(|s| {
            s.phase = Phase::Checking;
            s.error = None;
        });
        let result = match self.updater(&license_key) {
            Ok(updater) => updater.check().await,
            Err(error) => Err(error),
        };
        match result {
            Ok(Some(update)) => {
                let info = describe(
                    &update.version,
                    update.body.clone(),
                    &update.raw_json,
                    env!("CARGO_PKG_VERSION"),
                );
                *self.pending.lock().await = Some((update, None));
                self.set(|s| {
                    s.phase = Phase::Available;
                    s.update = Some(info);
                });
                self.record("available");
            }
            Ok(None) => {
                self.set(|s| {
                    s.phase = Phase::UpToDate;
                    s.update = None;
                });
                self.record("up to date");
            }
            // Keygate answered something other than an update (401 without a license, 404
            // for a key it does not know): there is nothing to install.
            Err(tauri_plugin_updater::Error::ReleaseNotFound) => {
                self.set(|s| {
                    s.phase = Phase::UpToDate;
                    s.update = None;
                });
                self.record("no release offered");
            }
            // Unreachable server and the like: logged, otherwise quiet; the next round retries.
            Err(error) => {
                self.set(|s| {
                    s.phase = Phase::Idle;
                    s.error = Some(error.to_string());
                });
                self.record(&format!("check failed: {error}"));
            }
        }
    }

    /// Downloads the app update.
    pub async fn download(&self) {
        self.cancel.store(false, Ordering::SeqCst);
        if self.status().update.is_none() {
            return;
        };

        if self.cancel.load(Ordering::SeqCst) {
            return self.cancelled();
        }
        self.set(|s| {
            s.phase = Phase::Downloading;
            s.done = 0;
            s.total = None;
        });
        self.record("downloading");
        let mut pending = self.pending.lock().await;
        let Some((update, bytes)) = pending.as_mut() else {
            return self.fail("no update to download".into());
        };
        let cancel = self.cancel.clone();
        let progress = |done: u64, total: Option<u64>| {
            self.set(|s| {
                s.done = done;
                s.total = total;
            })
        };
        let mut done = 0u64;
        let download = update.download(
            |chunk, total| {
                done += chunk as u64;
                progress(done, total);
            },
            || {},
        );
        // The plugin's download has no cancel; racing it against the flag drops it.
        let cancelled = async {
            while !cancel.load(Ordering::SeqCst) {
                tokio::time::sleep(Duration::from_millis(200)).await;
            }
        };
        tokio::select! {
            result = download => match result {
                Ok(downloaded) => {
                    *bytes = Some(downloaded);
                    drop(pending);
                    self.set(|s| s.phase = Phase::Ready);
                    self.record("downloaded and verified");
                }
                Err(error) => {
                    drop(pending);
                    self.fail(error.to_string());
                }
            },
            () = cancelled => {
                drop(pending);
                self.cancelled();
            }
        }
    }

    fn cancelled(&self) {
        self.set(|s| {
            s.phase = Phase::Available;
            s.done = 0;
            s.total = None;
        });
        self.record("download cancelled");
    }

    /// Only during the download: once installing, there is no going back halfway.
    pub fn cancel(&self) {
        self.cancel.store(true, Ordering::SeqCst);
    }

    /// Installs the downloaded update and restarts into it.
    pub async fn install(&self) {
        let pending = self.pending.lock().await;
        let Some((update, Some(bytes))) = pending.as_ref() else {
            drop(pending);
            return self.fail("the update has not been downloaded".into());
        };
        self.record("installing");
        if let Err(error) = update.install(bytes) {
            drop(pending);
            return self.fail(error.to_string());
        }
        drop(pending);
        self.record("installed, restarting");
        self.app.restart();
    }
}

/// Checks 30 seconds after launch, then every 24 hours.
pub fn start_checking(updates: SharedUpdates) {
    tauri::async_runtime::spawn(async move {
        tokio::time::sleep(FIRST_CHECK_DELAY).await;
        loop {
            updates.check().await;
            tokio::time::sleep(CHECK_INTERVAL).await;
        }
    });
}

#[tauri::command]
pub fn get_update_status(updates: tauri::State<'_, SharedUpdates>) -> UpdateStatus {
    updates.status()
}

#[tauri::command]
pub async fn check_for_updates(
    updates: tauri::State<'_, SharedUpdates>,
) -> Result<UpdateStatus, String> {
    updates.check().await;
    Ok(updates.status())
}

#[tauri::command]
pub async fn download_update(updates: tauri::State<'_, SharedUpdates>) -> Result<(), String> {
    let updates = updates.inner().clone();
    tauri::async_runtime::spawn(async move { updates.download().await });
    Ok(())
}

#[tauri::command]
pub fn cancel_update_download(updates: tauri::State<'_, SharedUpdates>) {
    updates.cancel();
}

#[tauri::command]
pub async fn install_update(updates: tauri::State<'_, SharedUpdates>) -> Result<(), String> {
    updates.install().await;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn below_the_minimum_supported_version_is_required() {
        let raw =
            json!({"minimum_supported_version": "1.3.0", "minimum_supported_message": "安全修复"});

        let info = describe("1.4.0", None, &raw, "1.2.0");

        assert!(info.required);
        assert_eq!(info.required_message.as_deref(), Some("安全修复"));
    }

    #[test]
    fn at_or_above_the_minimum_is_a_normal_update() {
        let raw = json!({"minimum_supported_version": "1.2.0", "minimum_supported_message": "x"});

        let info = describe("1.4.0", None, &raw, "1.2.0");

        assert!(!info.required);
        assert_eq!(info.required_message, None);
    }

    #[test]
    fn a_missing_or_unparseable_minimum_is_a_normal_update() {
        assert!(!describe("1.4.0", None, &json!({}), "1.2.0").required);
        assert!(
            !describe(
                "1.4.0",
                None,
                &json!({"minimum_supported_version": "soon"}),
                "1.2.0"
            )
            .required
        );
        assert!(
            describe(
                "1.4.0",
                None,
                &json!({"minimum_supported_version": "v1.3.0"}),
                "1.2.0"
            )
            .required
        );
    }

    #[test]
    fn the_feed_is_keygates_tauri_feed_with_the_platform_left_to_the_plugin() {
        assert_eq!(
            feed_url("https://licenses.example.com/", "fileseek"),
            "https://licenses.example.com/api/v1/releases/fileseek/upgrade.json?platform={{target}}-{{arch}}"
        );
        let built = feed_url(env!("KEYGATE_BASE_URL"), env!("KEYGATE_PRODUCT_SLUG"));
        assert!(
            !built.contains("license_key") && !built.contains("license_token"),
            "the key travels in a header, not the URL"
        );
    }

    /// The plugin refuses to start without a parseable `plugins.updater` section, so the
    /// placeholder in `tauri.conf.json` must stay valid.
    #[test]
    fn the_placeholder_updater_config_parses() {
        let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("tauri.conf.json");
        let conf: serde_json::Value =
            serde_json::from_slice(&std::fs::read(path).unwrap()).unwrap();
        let config: tauri_plugin_updater::Config =
            serde_json::from_value(conf["plugins"]["updater"].clone()).unwrap();
        assert!(
            config.endpoints.is_empty(),
            "the endpoint is Keygate's, set at run time"
        );
        assert!(
            config.pubkey.is_empty(),
            "the key comes from keygate.json through build.rs"
        );
    }

    #[test]
    fn log_lines_carry_time_and_both_versions() {
        let line = log_line(
            "2026-10-02T09:00:00Z".parse().unwrap(),
            "0.1.0",
            Some("0.2.0"),
            "failed: signature",
        );
        assert_eq!(
            line,
            "2026-10-02T09:00:00+00:00 current=0.1.0 target=0.2.0 failed: signature\n"
        );
        assert!(log_line(chrono::Utc::now(), "0.1.0", None, "up to date").contains("target=-"));
    }

    /// Against the real Keygate feed: a key it does not know gets no release, which the
    /// plugin reports as not found. Network access; `cargo test -- --ignored keygate_feed`.
    #[test]
    #[ignore]
    fn keygate_feed_offers_nothing_to_an_unknown_key() {
        let url = feed_url(env!("KEYGATE_BASE_URL"), env!("KEYGATE_PRODUCT_SLUG"))
            .replace("{{target}}-{{arch}}", "darwin-aarch64");
        let status = match ureq::get(&url).set("X-License-Key", "KG-TEST0000").call() {
            Ok(response) => response.status(),
            Err(ureq::Error::Status(status, _)) => status,
            Err(error) => panic!("{error}"),
        };
        assert!(matches!(status, 204 | 401 | 404), "HTTP {status}");
    }
}
