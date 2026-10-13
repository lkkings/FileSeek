//! Licensing against the self-hosted Keygate server: activate, check, deactivate.
//!
//! Without a valid license the app shows only the activation screen: no runtime download,
//! no backend. Local checks are a speed bump, not a lock — the binary is the user's. What
//! cannot be faked is a token signed by Keygate's key for this device, and the activation
//! count Keygate keeps. See the `licensing-*` specs in
//! `openspec/changes/commercial-licensing-and-updates`.
//!
//! ```text
//! no license.json / token does not verify ------------------------> unlicensed
//! now < exp ------------------------------------------------------> licensed (offline)
//! now >= exp (or the clock was turned back) -> POST /verify
//!     200                 -> save the new token ----------------> licensed
//!     404                 -> delete the license ----------------> unlicensed (revoked)
//!     unreachable / 5xx   -> now < exp + 7 days ? licensed (offline grace) : unlicensed
//! ```

pub mod client;
pub mod device;
pub mod status;
pub mod store;
#[cfg(test)]
mod test_server;
pub mod token;

use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};

use chrono::{DateTime, Utc};
use serde::Serialize;
use tauri::{Emitter, Manager};

use client::{ClientError, LicenseClient};
use status::{Entitlement, Reason};
use store::{Loaded, Saved, Store};
use token::{TokenError, TokenVerifier};

/// Why activating or deactivating did not work, in the categories the UI words.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum ActivationError {
    /// Nothing typed.
    EmptyKey,
    /// `LICENSE_NOT_FOUND`.
    NotFound,
    /// `ACTIVATION_LIMIT`; the counts when the server gave them.
    ActivationLimit {
        current: Option<u64>,
        max: Option<u64>,
    },
    Expired,
    Suspended,
    Revoked,
    Canceled,
    /// `LOCKED_OUT` / 429: too many attempts from this network.
    LockedOut,
    /// No answer from the server.
    Network,
    /// The server accepted, but its token does not verify for this device and product.
    BadToken,
    /// Another refusal; the code is kept for the log.
    Server {
        code: String,
    },
    /// The OS gives no machine id.
    NoDevice,
    /// Deactivating with nothing activated.
    NotActivated,
    Io {
        detail: String,
    },
}

impl From<ClientError> for ActivationError {
    fn from(error: ClientError) -> ActivationError {
        match error {
            ClientError::Unreachable(_) => ActivationError::Network,
            ClientError::Rejected {
                code, activations, ..
            } => match code.as_str() {
                "LICENSE_NOT_FOUND" => ActivationError::NotFound,
                "ACTIVATION_LIMIT" | "MAX_ACTIVATIONS_REACHED" => {
                    ActivationError::ActivationLimit {
                        current: activations.map(|(current, _)| current),
                        max: activations.map(|(_, max)| max),
                    }
                }
                "LICENSE_EXPIRED" => ActivationError::Expired,
                "LICENSE_SUSPENDED" | "SUSPENDED" => ActivationError::Suspended,
                "LICENSE_REVOKED" | "REVOKED" => ActivationError::Revoked,
                "LICENSE_CANCELED" | "CANCELED" => ActivationError::Canceled,
                "LOCKED_OUT" | "RATE_LIMIT_EXCEEDED" => ActivationError::LockedOut,
                _ => ActivationError::Server { code },
            },
        }
    }
}

pub struct LicenseService {
    store: Store,
    verifier: TokenVerifier,
    client: LicenseClient,
    /// This machine's identifier; `None` when the OS gives no machine id.
    device: Option<String>,
    /// Debug builds skip licensing unless `FILESEEK_LICENSE_ENFORCE=1`.
    enforce: bool,
    clock: Box<dyn Fn() -> DateTime<Utc> + Send + Sync>,
    /// One check, activation or deactivation at a time: they all rewrite the license file.
    lock: Mutex<()>,
    /// The last result, for `get_entitlement` without touching the network.
    last: Mutex<Option<Entitlement>>,
}

impl LicenseService {
    pub fn new(
        dir: PathBuf,
        verifier: TokenVerifier,
        client: LicenseClient,
        device: Option<String>,
        enforce: bool,
        clock: Box<dyn Fn() -> DateTime<Utc> + Send + Sync>,
    ) -> LicenseService {
        LicenseService {
            store: Store::new(dir),
            verifier,
            client,
            device,
            enforce,
            clock,
            lock: Mutex::new(()),
            last: Mutex::new(None),
        }
    }

    /// The app's: `<config_dir>/license/`, the Keygate server and key this build was
    /// configured with, and this machine's identifier.
    pub fn for_app(config_dir: &Path) -> LicenseService {
        let enforce = !cfg!(debug_assertions)
            || std::env::var("FILESEEK_LICENSE_ENFORCE").as_deref() == Ok("1");
        LicenseService::new(
            config_dir.join("license"),
            TokenVerifier::for_build(),
            LicenseClient::for_build(),
            device::identifier(),
            enforce,
            Box::new(Utc::now),
        )
    }

    fn purchase_url(&self) -> String {
        self.client.purchase_url()
    }

    /// Set after the server said the license is gone, so the activation screen can say
    /// "no longer valid" instead of "not activated" across restarts. Cleared on activation.
    fn revoked_marker(&self) -> PathBuf {
        self.store.dir().join("revoked")
    }

    fn remember(&self, entitlement: Entitlement) -> Entitlement {
        *self.last.lock().unwrap() = Some(entitlement.clone());
        entitlement
    }

    /// The last result of [`check`](Self::check), activation or deactivation; checks if
    /// there is none yet.
    pub fn entitlement(&self) -> Entitlement {
        let last = self.last.lock().unwrap().clone();
        last.unwrap_or_else(|| self.check())
    }

    /// Decides whether this device is licensed, asking the server only once the token's
    /// `exp` has passed (or the clock looks turned back).
    pub fn check(&self) -> Entitlement {
        let _guard = self.lock.lock().unwrap();
        if !self.enforce {
            return self.remember(Entitlement::development(&self.purchase_url()));
        }
        let Some(device) = self.device.clone() else {
            return self.remember(Entitlement::unlicensed(
                Reason::NoDevice,
                &self.purchase_url(),
            ));
        };
        let now = (self.clock)();
        let last_seen = self.store.last_seen_at();
        self.store.touch(now);

        let saved = match self.store.load(now) {
            Loaded::Saved(saved) => saved,
            Loaded::Damaged => {
                return self.remember(Entitlement::unlicensed(
                    Reason::Invalid,
                    &self.purchase_url(),
                ))
            }
            Loaded::None => {
                let reason = if self.revoked_marker().exists() {
                    Reason::Revoked
                } else {
                    Reason::None
                };
                return self.remember(Entitlement::unlicensed(reason, &self.purchase_url()));
            }
        };
        let claims = match self.verifier.verify(&saved.token, &device) {
            Ok(claims) => claims,
            Err(_) => {
                return self.remember(Entitlement::unlicensed(
                    Reason::Invalid,
                    &self.purchase_url(),
                ))
            }
        };

        let rolled_back = status::clock_turned_back(now, last_seen, Some(claims.issued_at));
        if now < claims.check_by && !rolled_back {
            return self.remember(Entitlement::licensed(
                &claims,
                saved.plan_name.clone(),
                &self.purchase_url(),
            ));
        }

        match self.client.verify(&saved.license_key, &device) {
            Ok(verified) => match self.verifier.verify(&verified.token, &device) {
                Ok(fresh) => {
                    let _ = self.store.save(&Saved {
                        license_key: saved.license_key,
                        token: verified.token,
                        plan_name: verified.plan_name.clone().or(saved.plan_name),
                    });
                    let entitlement =
                        Entitlement::licensed(&fresh, verified.plan_name, &self.purchase_url());
                    self.remember(entitlement)
                }
                // The server answered with something this build cannot trust: keep what
                // is saved and treat it like not being able to ask.
                Err(_) => self.offline(&claims, saved.plan_name, rolled_back, now),
            },
            Err(ClientError::Rejected { status: 404, .. }) => {
                let _ = self.store.remove();
                let _ = std::fs::write(self.revoked_marker(), now.to_rfc3339());
                self.remember(Entitlement::unlicensed(
                    Reason::Revoked,
                    &self.purchase_url(),
                ))
            }
            Err(_) => self.offline(&claims, saved.plan_name, rolled_back, now),
        }
    }

    /// The server could not be asked: licensed while the offline grace lasts, which a
    /// turned-back clock forfeits (otherwise turning it back would buy time forever).
    fn offline(
        &self,
        claims: &token::Claims,
        plan_name: Option<String>,
        rolled_back: bool,
        now: DateTime<Utc>,
    ) -> Entitlement {
        let days_left = (!rolled_back)
            .then(|| status::offline_days_left(claims.check_by, now))
            .flatten();
        let entitlement = match days_left {
            Some(days) => {
                let mut entitlement =
                    Entitlement::licensed(claims, plan_name, &self.purchase_url());
                entitlement.offline_days_left = Some(days);
                entitlement
            }
            None => {
                let mut entitlement =
                    Entitlement::unlicensed(Reason::OfflineExpired, &self.purchase_url());
                entitlement.clock_anomaly = rolled_back;
                entitlement
            }
        };
        self.remember(entitlement)
    }

    /// Trades a license key for a token bound to this device and saves both.
    pub fn activate(&self, license_key: &str, label: &str) -> Result<Entitlement, ActivationError> {
        let _guard = self.lock.lock().unwrap();
        let license_key = license_key.trim();
        if license_key.is_empty() {
            return Err(ActivationError::EmptyKey);
        }
        let device = self.device.clone().ok_or(ActivationError::NoDevice)?;
        // One key for this attempt and its retry, so a timeout that did reach the server
        // cannot take a second activation.
        let idempotency_key = client::idempotency_key();
        let mut result = self
            .client
            .activate(license_key, &device, label, &idempotency_key);
        if matches!(result, Err(ClientError::Unreachable(_))) {
            result = self
                .client
                .activate(license_key, &device, label, &idempotency_key);
        }
        let activated = result?;
        let claims = self
            .verifier
            .verify(&activated.token, &device)
            .map_err(|_: TokenError| ActivationError::BadToken)?;
        self.store
            .save(&Saved {
                license_key: license_key.to_owned(),
                token: activated.token,
                plan_name: None,
            })
            .map_err(|e| ActivationError::Io {
                detail: e.to_string(),
            })?;
        let _ = std::fs::remove_file(self.revoked_marker());
        self.store.touch((self.clock)());
        Ok(self.remember(Entitlement::licensed(&claims, None, &self.purchase_url())))
    }

    /// Frees this device's activation, then deletes the local license. Without an answer
    /// from the server the license stays: deleting it would lose the activation for good.
    pub fn deactivate(&self) -> Result<Entitlement, ActivationError> {
        let _guard = self.lock.lock().unwrap();
        let device = self.device.clone().ok_or(ActivationError::NoDevice)?;
        let Loaded::Saved(saved) = self.store.load((self.clock)()) else {
            return Err(ActivationError::NotActivated);
        };
        self.client.deactivate(&saved.license_key, &device)?;
        self.store.remove().map_err(|e| ActivationError::Io {
            detail: e.to_string(),
        })?;
        let _ = std::fs::remove_file(self.revoked_marker());
        Ok(self.remember(Entitlement::unlicensed(Reason::None, &self.purchase_url())))
    }

    /// The saved license key, for the update feed's `X-License-Key` header.
    pub fn license_key(&self) -> Option<String> {
        let _guard = self.lock.lock().unwrap();
        match self.store.load((self.clock)()) {
            Loaded::Saved(saved) => Some(saved.license_key),
            _ => None,
        }
    }
}

pub const ENTITLEMENT_EVENT: &str = "entitlement";
/// How often a running app checks again. Only calls the server once `exp` has passed.
const CHECK_INTERVAL: std::time::Duration = std::time::Duration::from_secs(24 * 60 * 60);

pub type SharedLicense = Arc<LicenseService>;

/// This computer's name, sent as the activation's label so the user can tell their
/// devices apart in the customer portal.
pub fn device_name() -> String {
    #[cfg(unix)]
    {
        let mut buffer = [0u8; 256];
        // SAFETY: the buffer is writable for its whole length, which is passed along.
        let ok = unsafe { libc::gethostname(buffer.as_mut_ptr().cast(), buffer.len()) } == 0;
        if ok {
            let end = buffer.iter().position(|&b| b == 0).unwrap_or(buffer.len());
            let name = String::from_utf8_lossy(&buffer[..end])
                .trim_end_matches(".local")
                .to_owned();
            if !name.is_empty() {
                return name;
            }
        }
    }
    std::env::var("COMPUTERNAME").unwrap_or_else(|_| "FileSeek".to_owned())
}

/// Tells the UI, and the readiness supervisor: licensed starts the backend, unlicensed
/// stops it and shows the activation screen.
fn publish(app: &tauri::AppHandle, entitlement: &Entitlement) {
    let _ = app.emit(ENTITLEMENT_EVENT, entitlement);
    if let Some(readiness) = app.try_state::<crate::readiness::Readiness>() {
        readiness.send(if entitlement.is_licensed() {
            crate::readiness::Command::Licensed
        } else {
            crate::readiness::Command::Unlicensed
        });
    }
}

/// Checks again every 24 hours while the app runs; the launch check is the readiness
/// supervisor's. Speaks up only when licensed-or-not changes.
pub fn start_checker(service: SharedLicense, app: tauri::AppHandle) {
    std::thread::Builder::new()
        .name("fileseek-license-check".into())
        .spawn(move || loop {
            std::thread::sleep(CHECK_INTERVAL);
            let before = service.entitlement().is_licensed();
            let now = service.check();
            if now.is_licensed() != before {
                publish(&app, &now);
            } else {
                // Offline days left and the like still change.
                let _ = app.emit(ENTITLEMENT_EVENT, &now);
            }
        })
        .expect("could not start the license check thread");
}

/// Runs `work` off the async runtime (it waits on the network), then publishes the
/// entitlement it leaves behind.
async fn blocking(
    service: &SharedLicense,
    app: &tauri::AppHandle,
    work: impl FnOnce(&LicenseService) -> Result<Entitlement, ActivationError> + Send + 'static,
) -> Result<Entitlement, ActivationError> {
    let service = service.clone();
    let entitlement = tauri::async_runtime::spawn_blocking(move || work(&service))
        .await
        .map_err(|e| ActivationError::Io {
            detail: e.to_string(),
        })??;
    publish(app, &entitlement);
    Ok(entitlement)
}

#[tauri::command]
pub fn get_entitlement(service: tauri::State<'_, SharedLicense>) -> Entitlement {
    service.entitlement()
}

#[tauri::command]
pub async fn activate_license(
    key: String,
    service: tauri::State<'_, SharedLicense>,
    app: tauri::AppHandle,
) -> Result<Entitlement, ActivationError> {
    blocking(&service, &app, move |s| s.activate(&key, &device_name())).await
}

#[tauri::command]
pub async fn deactivate_license(
    service: tauri::State<'_, SharedLicense>,
    app: tauri::AppHandle,
) -> Result<Entitlement, ActivationError> {
    blocking(&service, &app, |s| s.deactivate()).await
}

/// "Retry" on the activation screen when the license could not be checked online.
#[tauri::command]
pub async fn recheck_license(
    service: tauri::State<'_, SharedLicense>,
    app: tauri::AppHandle,
) -> Result<Entitlement, ActivationError> {
    blocking(&service, &app, |s| Ok(s.check())).await
}

/// The library directory, where the user's files stay readable without a license. The
/// backend's `lib_root` (`LIB_ROOT`, default `~/FileSeekLibrary`); asked here because
/// without a license the backend is not running to say.
pub fn library_dir() -> PathBuf {
    std::env::var_os("LIB_ROOT")
        .filter(|value| !value.is_empty())
        .map(PathBuf::from)
        .unwrap_or_else(|| dirs::home_dir().unwrap_or_default().join("FileSeekLibrary"))
}

/// "Open the library folder" on the activation screen.
#[tauri::command]
pub fn open_library_folder(app: tauri::AppHandle) -> Result<(), String> {
    use tauri_plugin_opener::OpenerExt;
    let dir = library_dir();
    if !dir.is_dir() {
        return Err(format!("{} does not exist", dir.display()));
    }
    app.opener()
        .open_path(dir.to_string_lossy(), None::<&str>)
        .map_err(|e| e.to_string())
}

#[cfg(test)]
mod tests {
    use super::test_server::ScriptedServer;
    use super::token::testing::{sign_json, token, verifier, DEVICE, PRODUCT};
    use super::*;
    use serde_json::json;
    use std::sync::atomic::{AtomicI64, Ordering};

    const T0: i64 = 1_790_000_000; // 2026-09-21
    const DAY: i64 = 86_400;
    const ACTIVATE: &str = "/api/v1/license/activate";
    const VERIFY: &str = "/api/v1/license/verify";
    const DEACTIVATE: &str = "/api/v1/license/deactivate";

    struct Fixture {
        dir: tempfile::TempDir,
        server: ScriptedServer,
        now: Arc<AtomicI64>,
        service: LicenseService,
    }

    fn fixture() -> Fixture {
        fixture_with(Some(DEVICE.into()), true)
    }

    fn fixture_with(device: Option<String>, enforce: bool) -> Fixture {
        let dir = tempfile::tempdir().unwrap();
        let server = ScriptedServer::start();
        let now = Arc::new(AtomicI64::new(T0));
        let clock = now.clone();
        let service = LicenseService::new(
            dir.path().join("license"),
            verifier(),
            LicenseClient {
                base_url: server.base.clone(),
                product_slug: "fileseek".into(),
                app_version: "1.0.0".into(),
            },
            device,
            enforce,
            Box::new(move || DateTime::from_timestamp(clock.load(Ordering::SeqCst), 0).unwrap()),
        );
        Fixture {
            dir,
            server,
            now,
            service,
        }
    }

    impl Fixture {
        fn at(&self, seconds: i64) {
            self.now.store(seconds, Ordering::SeqCst);
        }
        fn ok(&self, path: &str, token: &str) {
            self.server.route(
                "POST",
                path,
                200,
                json!({"success": true, "data": {"status": "active", "plan_name": "Pro", "token": token}}),
            );
        }
        fn error(&self, path: &str, status: u16, code: &str) {
            self.server.route(
                "POST",
                path,
                status,
                json!({"success": false, "error": {"code": code, "message": "x"}}),
            );
        }
        fn activated(&self, exp: i64) {
            self.ok(ACTIVATE, &token(T0, exp));
            self.service.activate("KG-KEY", "Mac").unwrap();
        }
        fn calls(&self, path: &str) -> usize {
            self.server
                .requests()
                .iter()
                .filter(|r| r.path == path)
                .count()
        }
    }

    #[test]
    fn nothing_saved_is_not_activated() {
        let fx = fixture();

        let entitlement = fx.service.check();

        assert_eq!(entitlement.state, status::State::Unlicensed);
        assert_eq!(entitlement.reason, Some(Reason::None));
        assert!(entitlement.purchase_url.ends_with("/buy/fileseek"));
        assert!(fx.server.requests().is_empty());
    }

    #[test]
    fn activation_saves_the_key_and_token_and_licenses() {
        let fx = fixture();
        fx.ok(ACTIVATE, &token(T0, T0 + 7 * DAY));

        let entitlement = fx.service.activate("  KG-KEY \n", "Mac").unwrap();

        assert!(entitlement.is_licensed());
        assert_eq!(entitlement.license_id.as_deref(), Some("lic_1"));
        let body = &fx.server.requests()[0].body;
        assert_eq!(body["license_key"], "KG-KEY");
        assert_eq!(body["identifier"], DEVICE);
        assert_eq!(fx.service.license_key().as_deref(), Some("KG-KEY"));
    }

    #[test]
    fn before_exp_the_server_is_not_asked() {
        let fx = fixture();
        fx.activated(T0 + 7 * DAY);
        fx.at(T0 + 3 * DAY);

        assert!(fx.service.check().is_licensed());
        assert_eq!(fx.calls(VERIFY), 0);
    }

    #[test]
    fn after_exp_a_new_token_is_fetched_and_saved() {
        let fx = fixture();
        fx.activated(T0 + 7 * DAY);
        fx.at(T0 + 8 * DAY);
        fx.ok(VERIFY, &token(T0 + 8 * DAY, T0 + 15 * DAY));

        let entitlement = fx.service.check();

        assert!(entitlement.is_licensed());
        assert_eq!(entitlement.plan_name.as_deref(), Some("Pro"));
        // Saved: the next check before the new exp stays offline.
        fx.at(T0 + 10 * DAY);
        assert!(fx.service.check().is_licensed());
        assert_eq!(fx.calls(VERIFY), 1);
    }

    #[test]
    fn not_found_on_verify_deletes_the_license() {
        let fx = fixture();
        fx.activated(T0 + 7 * DAY);
        fx.at(T0 + 8 * DAY);
        fx.error(VERIFY, 404, "LICENSE_NOT_FOUND");

        let entitlement = fx.service.check();

        assert_eq!(entitlement.reason, Some(Reason::Revoked));
        assert_eq!(fx.service.license_key(), None);
        // Still says "no longer valid", not "not activated", on the next launch.
        assert_eq!(fx.service.check().reason, Some(Reason::Revoked));
    }

    #[test]
    fn offline_after_exp_is_licensed_for_seven_days() {
        let fx = fixture();
        fx.activated(T0 + 7 * DAY);
        fx.error(VERIFY, 503, "UNAVAILABLE");

        fx.at(T0 + 9 * DAY);
        let entitlement = fx.service.check();
        assert!(entitlement.is_licensed());
        assert_eq!(entitlement.offline_days_left, Some(5));

        fx.at(T0 + 15 * DAY);
        let entitlement = fx.service.check();
        assert_eq!(entitlement.reason, Some(Reason::OfflineExpired));
        // Not deleted: connecting again restores it.
        assert_eq!(fx.service.license_key().as_deref(), Some("KG-KEY"));
        fx.ok(VERIFY, &token(T0 + 15 * DAY, T0 + 22 * DAY));
        assert!(fx.service.check().is_licensed());
    }

    #[test]
    fn turning_the_clock_back_forces_a_verify() {
        let fx = fixture();
        fx.activated(T0 + 7 * DAY);
        fx.at(T0 + 20 * DAY);
        fx.error(VERIFY, 503, "UNAVAILABLE");
        assert!(!fx.service.check().is_licensed());

        // Back before exp, and offline.
        fx.at(T0 + DAY);
        let entitlement = fx.service.check();

        assert_eq!(entitlement.reason, Some(Reason::OfflineExpired));
        assert!(entitlement.clock_anomaly);
        assert_eq!(fx.calls(VERIFY), 2);
    }

    #[test]
    fn an_edited_token_is_invalid() {
        let fx = fixture();
        fx.activated(T0 + 7 * DAY);
        let path = fx.dir.path().join("license/license.json");
        let mut saved: serde_json::Value =
            serde_json::from_slice(&std::fs::read(&path).unwrap()).unwrap();
        let forged = token(T0, T0 + 999 * DAY);
        let (payload, _) = forged.split_once('.').unwrap();
        let (_, signature) = saved["token"].as_str().unwrap().split_once('.').unwrap();
        saved["token"] = format!("{payload}.{signature}").into();
        std::fs::write(&path, serde_json::to_vec(&saved).unwrap()).unwrap();

        assert_eq!(fx.service.check().reason, Some(Reason::Invalid));
    }

    #[test]
    fn a_license_copied_from_another_machine_is_invalid() {
        let fx = fixture();
        fx.activated(T0 + 7 * DAY);
        let other = fixture_with(Some("another-machine".into()), true);
        let copied = fx.dir.path().join("license/license.json");
        std::fs::create_dir_all(other.dir.path().join("license")).unwrap();
        std::fs::copy(copied, other.dir.path().join("license/license.json")).unwrap();

        assert_eq!(other.service.check().reason, Some(Reason::Invalid));
    }

    #[test]
    fn a_token_for_another_product_is_refused_at_activation() {
        let fx = fixture();
        fx.ok(
            ACTIVATE,
            &sign_json(
                &json!({"lid": "x", "pid": "other", "did": DEVICE, "iat": T0, "exp": T0 + DAY}),
            ),
        );

        assert_eq!(
            fx.service.activate("KG-KEY", "Mac"),
            Err(ActivationError::BadToken)
        );
        assert_eq!(fx.service.license_key(), None);
        let _ = PRODUCT;
    }

    #[test]
    fn activation_errors_are_categorised() {
        let fx = fixture();
        fx.server.route(
            "POST",
            ACTIVATE,
            409,
            json!({"success": false, "error": {"code": "ACTIVATION_LIMIT", "message": "x",
                   "details": {"current": 2, "max": 2}}}),
        );
        assert_eq!(
            fx.service.activate("KG-KEY", "Mac"),
            Err(ActivationError::ActivationLimit {
                current: Some(2),
                max: Some(2)
            })
        );
        for (status, code, expected) in [
            (404, "LICENSE_NOT_FOUND", ActivationError::NotFound),
            (403, "LICENSE_EXPIRED", ActivationError::Expired),
            (403, "LICENSE_SUSPENDED", ActivationError::Suspended),
            (403, "LICENSE_REVOKED", ActivationError::Revoked),
            (403, "LICENSE_CANCELED", ActivationError::Canceled),
            (429, "LOCKED_OUT", ActivationError::LockedOut),
        ] {
            fx.error(ACTIVATE, status, code);
            assert_eq!(
                fx.service.activate("KG-KEY", "Mac"),
                Err(expected),
                "{code}"
            );
        }
        assert_eq!(
            fx.service.activate("  ", "Mac"),
            Err(ActivationError::EmptyKey)
        );
        assert_eq!(fx.service.license_key(), None);
    }

    #[test]
    fn a_retried_activation_reuses_its_idempotency_key() {
        let fx = fixture();
        fx.server.route("POST", ACTIVATE, 502, json!("bad gateway"));

        assert_eq!(
            fx.service.activate("KG-KEY", "Mac"),
            Err(ActivationError::Network)
        );

        let keys: Vec<_> = fx
            .server
            .requests()
            .iter()
            .map(|r| r.header("idempotency-key").unwrap())
            .collect();
        assert_eq!(keys.len(), 2);
        assert_eq!(keys[0], keys[1]);
    }

    #[test]
    fn deactivation_frees_the_device_and_deletes_the_license() {
        let fx = fixture();
        fx.activated(T0 + 7 * DAY);
        fx.server.route(
            "POST",
            DEACTIVATE,
            200,
            json!({"success": true, "data": {"status": "deactivated"}}),
        );

        let entitlement = fx.service.deactivate().unwrap();

        assert_eq!(entitlement.reason, Some(Reason::None));
        assert_eq!(fx.service.license_key(), None);
        let request = fx.server.requests().into_iter().last().unwrap();
        assert_eq!(request.body["license_key"], "KG-KEY");
    }

    #[test]
    fn deactivation_offline_keeps_the_license() {
        let fx = fixture();
        fx.activated(T0 + 7 * DAY);
        fx.server.route("POST", DEACTIVATE, 503, json!("down"));

        assert_eq!(fx.service.deactivate(), Err(ActivationError::Network));
        assert_eq!(fx.service.license_key().as_deref(), Some("KG-KEY"));
    }

    #[test]
    fn without_a_machine_id_nothing_is_sent() {
        let fx = fixture_with(None, true);

        assert_eq!(fx.service.check().reason, Some(Reason::NoDevice));
        assert_eq!(
            fx.service.activate("KG-KEY", "Mac"),
            Err(ActivationError::NoDevice)
        );
        assert!(fx.server.requests().is_empty());
    }

    #[test]
    fn development_builds_are_licensed_without_asking() {
        let fx = fixture_with(Some(DEVICE.into()), false);

        assert!(fx.service.check().is_licensed());
        assert!(fx.server.requests().is_empty());
    }

    /// Against the real Keygate server: a key that does not exist cannot activate, and
    /// nothing is saved. Network access; run with `cargo test -- --ignored keygate`.
    #[test]
    #[ignore]
    fn keygate_refuses_an_unknown_key() {
        let dir = tempfile::tempdir().unwrap();
        let service = LicenseService::new(
            dir.path().to_owned(),
            TokenVerifier::for_build(),
            LicenseClient::for_build(),
            Some("0".repeat(64)),
            true,
            Box::new(Utc::now),
        );

        assert_eq!(
            service.activate("KG-TEST0000-TEST0000-TEST0000-TEST0000", "FileSeek test"),
            Err(ActivationError::NotFound)
        );
        assert_eq!(service.license_key(), None);
    }

    /// Against the real Keygate server with a real key: activate, verify, deactivate.
    /// Takes one activation for the length of the test. Set `FILESEEK_TEST_LICENSE_KEY`
    /// and run with `cargo test -- --ignored keygate_round_trip`.
    #[test]
    #[ignore]
    fn keygate_round_trip() {
        let Ok(key) = std::env::var("FILESEEK_TEST_LICENSE_KEY") else {
            eprintln!("FILESEEK_TEST_LICENSE_KEY is not set; skipped");
            return;
        };
        let dir = tempfile::tempdir().unwrap();
        // A fixed identifier of its own, so the test never takes this machine's place.
        let device = "f11e5eec".repeat(8);
        let service = LicenseService::new(
            dir.path().to_owned(),
            TokenVerifier::for_build(),
            LicenseClient::for_build(),
            Some(device.clone()),
            true,
            Box::new(Utc::now),
        );

        let activated = service.activate(&key, "FileSeek integration test").unwrap();
        assert!(activated.is_licensed(), "{activated:?}");
        let verified = service.client.verify(&key, &device).unwrap();
        let claims = service.verifier.verify(&verified.token, &device).unwrap();
        eprintln!(
            "pid in the token: {:?} (keygate.json product_id)",
            claims.product_id
        );
        service.deactivate().unwrap();
        assert_eq!(service.license_key(), None);
    }
}
