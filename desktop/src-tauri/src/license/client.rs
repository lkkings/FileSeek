//! Keygate's license API (`{base}/api/v1/license/...`, all `POST` with JSON):
//!
//! ```text
//! activate    {license_key, identifier, identifier_type, label}  + Idempotency-Key
//!             200 {success, data: {status: activated | already_activated, license_id, token}}
//! verify      {license_key, identifier}
//!             200 {success, data: {status, plan_name, valid_until?, updates_until?, token, ...}}
//!             404 LICENSE_NOT_FOUND for every reason it is no longer valid here
//! deactivate  {license_key, identifier}
//!             200 {success, data: {status: deactivated}}
//! errors      {success: false, error: {code, message, details?}}
//! ```
//!
//! The license key is a credential: it goes in request bodies only, never in a URL or a
//! log line.

use std::time::Duration;

use serde::Deserialize;
use serde_json::json;

const TIMEOUT: Duration = Duration::from_secs(20);

#[derive(Debug, Clone)]
pub struct LicenseClient {
    pub base_url: String,
    pub product_slug: String,
    pub app_version: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ClientError {
    /// The server answered no, with Keygate's error code (`ACTIVATION_LIMIT`, ...).
    Rejected {
        status: u16,
        code: String,
        /// `details.current` / `details.max` for `ACTIVATION_LIMIT`.
        activations: Option<(u64, u64)>,
    },
    /// No answer, or one that is not the contract (5xx, a body that does not parse).
    Unreachable(String),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Activated {
    pub token: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct Verified {
    pub token: String,
    pub plan_name: Option<String>,
}

#[derive(Deserialize)]
struct Envelope {
    #[serde(default)]
    data: serde_json::Value,
    #[serde(default)]
    error: Option<ErrorBody>,
}

#[derive(Deserialize)]
struct ErrorBody {
    #[serde(default)]
    code: String,
    #[serde(default)]
    details: serde_json::Value,
}

/// A fresh random key per activation attempt; the retries of one attempt reuse it, so a
/// retry after a timeout cannot take a second activation.
pub fn idempotency_key() -> String {
    let mut bytes = [0u8; 16];
    getrandom::getrandom(&mut bytes).expect("the OS random source is unavailable");
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

impl LicenseClient {
    /// The one this build was configured with (`build.rs`).
    pub fn for_build() -> LicenseClient {
        LicenseClient {
            base_url: env!("KEYGATE_BASE_URL").to_owned(),
            product_slug: env!("KEYGATE_PRODUCT_SLUG").to_owned(),
            app_version: env!("CARGO_PKG_VERSION").to_owned(),
        }
    }

    /// Where to buy a license: Keygate's checkout page for this product.
    pub fn purchase_url(&self) -> String {
        format!("{}/buy/{}", self.base_url, self.product_slug)
    }

    fn call(
        &self,
        action: &str,
        body: serde_json::Value,
        idempotency_key: Option<&str>,
    ) -> Result<serde_json::Value, ClientError> {
        let mut request = ureq::post(&format!("{}/api/v1/license/{action}", self.base_url))
            .timeout(TIMEOUT)
            .set("X-Product-ID", &self.product_slug)
            .set("User-Agent", &format!("FileSeek/{}", self.app_version));
        if let Some(key) = idempotency_key {
            request = request.set("Idempotency-Key", key);
        }
        let (status, text) = match request.send_json(body) {
            Ok(response) => (response.status(), response.into_string()),
            Err(ureq::Error::Status(status, response)) => (status, response.into_string()),
            Err(error) => return Err(ClientError::Unreachable(error.to_string())),
        };
        let text = text.map_err(|e| ClientError::Unreachable(e.to_string()))?;
        let envelope: Option<Envelope> = serde_json::from_str(&text).ok();
        if (200..300).contains(&status) {
            return envelope.map(|e| e.data).ok_or_else(|| {
                ClientError::Unreachable(format!("unexpected response ({status})"))
            });
        }
        match envelope.and_then(|e| e.error) {
            // 5xx with or without a code: the server is in trouble, not saying no.
            Some(error) if status < 500 => {
                let count = |name: &str| error.details.get(name).and_then(|v| v.as_u64());
                Err(ClientError::Rejected {
                    status,
                    activations: count("current").zip(count("max")),
                    code: error.code,
                })
            }
            _ if status == 429 => Err(ClientError::Rejected {
                status,
                code: "LOCKED_OUT".into(),
                activations: None,
            }),
            _ => Err(ClientError::Unreachable(format!("HTTP {status}"))),
        }
    }

    fn token(data: &serde_json::Value) -> Result<String, ClientError> {
        data.get("token")
            .and_then(|t| t.as_str())
            .filter(|t| !t.is_empty())
            .map(str::to_owned)
            .ok_or_else(|| ClientError::Unreachable("the response has no token".into()))
    }

    pub fn activate(
        &self,
        license_key: &str,
        identifier: &str,
        label: &str,
        idempotency_key: &str,
    ) -> Result<Activated, ClientError> {
        let data = self.call(
            "activate",
            json!({
                "license_key": license_key,
                "identifier": identifier,
                "identifier_type": "device",
                "label": label,
            }),
            Some(idempotency_key),
        )?;
        Ok(Activated {
            token: Self::token(&data)?,
        })
    }

    pub fn verify(&self, license_key: &str, identifier: &str) -> Result<Verified, ClientError> {
        let data = self.call(
            "verify",
            json!({ "license_key": license_key, "identifier": identifier }),
            None,
        )?;
        Ok(Verified {
            token: Self::token(&data)?,
            plan_name: data
                .get("plan_name")
                .and_then(|v| v.as_str())
                .map(str::to_owned),
        })
    }

    pub fn deactivate(&self, license_key: &str, identifier: &str) -> Result<(), ClientError> {
        match self.call(
            "deactivate",
            json!({ "license_key": license_key, "identifier": identifier }),
            None,
        ) {
            Ok(_) => Ok(()),
            // Already freed (from the customer portal, say): the goal is reached.
            Err(ClientError::Rejected { status: 404, .. }) => Ok(()),
            Err(error) => Err(error),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::super::test_server::ScriptedServer;
    use super::*;

    fn client(server: &ScriptedServer) -> LicenseClient {
        LicenseClient {
            base_url: server.base.clone(),
            product_slug: "fileseek".into(),
            app_version: "1.2.3".into(),
        }
    }

    #[test]
    fn activate_sends_the_contract_and_returns_the_token() {
        let server = ScriptedServer::start();
        server.route(
            "POST",
            "/api/v1/license/activate",
            200,
            json!({"success": true, "data": {"status": "activated", "license_id": "l", "token": "p.s"}}),
        );

        let activated = client(&server)
            .activate("KG-AAAA", "dev-1", "My Mac", "idem-1")
            .unwrap();

        assert_eq!(activated.token, "p.s");
        let request = &server.requests()[0];
        assert_eq!(
            request.body,
            json!({"license_key": "KG-AAAA", "identifier": "dev-1",
                   "identifier_type": "device", "label": "My Mac"})
        );
        assert_eq!(request.header("idempotency-key").as_deref(), Some("idem-1"));
        assert_eq!(request.header("x-product-id").as_deref(), Some("fileseek"));
        assert!(
            !request.path.contains("KG-AAAA"),
            "the key must not be in the URL"
        );
    }

    #[test]
    fn already_activated_is_a_success() {
        let server = ScriptedServer::start();
        server.route(
            "POST",
            "/api/v1/license/activate",
            200,
            json!({"success": true, "data": {"status": "already_activated", "token": "p.s"}}),
        );

        assert!(client(&server).activate("k", "d", "l", "i").is_ok());
    }

    #[test]
    fn activation_limit_carries_the_counts() {
        let server = ScriptedServer::start();
        server.route(
            "POST",
            "/api/v1/license/activate",
            409,
            json!({"success": false, "error": {"code": "ACTIVATION_LIMIT", "message": "x",
                   "details": {"current": 2, "max": 2}}}),
        );

        assert_eq!(
            client(&server).activate("k", "d", "l", "i"),
            Err(ClientError::Rejected {
                status: 409,
                code: "ACTIVATION_LIMIT".into(),
                activations: Some((2, 2)),
            })
        );
    }

    #[test]
    fn verify_returns_the_new_token_and_plan_name() {
        let server = ScriptedServer::start();
        server.route(
            "POST",
            "/api/v1/license/verify",
            200,
            json!({"success": true, "data": {"status": "active", "plan_name": "Pro", "token": "n.t"}}),
        );

        assert_eq!(
            client(&server).verify("k", "d").unwrap(),
            Verified {
                token: "n.t".into(),
                plan_name: Some("Pro".into())
            }
        );
    }

    #[test]
    fn not_found_is_a_definite_no() {
        let server = ScriptedServer::start();
        server.route(
            "POST",
            "/api/v1/license/verify",
            404,
            json!({"success": false, "error": {"code": "LICENSE_NOT_FOUND", "message": "x"}}),
        );

        let error = client(&server).verify("k", "d").unwrap_err();

        assert!(matches!(error, ClientError::Rejected { status: 404, .. }));
    }

    #[test]
    fn server_errors_are_unreachable_and_lockouts_keep_their_code() {
        let server = ScriptedServer::start();
        server.route("POST", "/api/v1/license/verify", 503, json!("down"));
        server.route(
            "POST",
            "/api/v1/license/deactivate",
            429,
            json!({"success": false, "error": {"code": "LOCKED_OUT", "message": "x"}}),
        );

        assert!(matches!(
            client(&server).verify("k", "d"),
            Err(ClientError::Unreachable(_))
        ));
        assert!(matches!(
            client(&server).deactivate("k", "d"),
            Err(ClientError::Rejected { status: 429, ref code, .. }) if code == "LOCKED_OUT"
        ));
    }

    #[test]
    fn no_server_is_unreachable() {
        let client = LicenseClient {
            base_url: "http://127.0.0.1:9".into(),
            product_slug: "fileseek".into(),
            app_version: "0".into(),
        };

        assert!(matches!(
            client.verify("k", "d"),
            Err(ClientError::Unreachable(_))
        ));
    }

    #[test]
    fn deactivating_a_freed_device_is_done() {
        let server = ScriptedServer::start();
        server.route(
            "POST",
            "/api/v1/license/deactivate",
            404,
            json!({"success": false, "error": {"code": "LICENSE_NOT_FOUND", "message": "x"}}),
        );

        assert_eq!(client(&server).deactivate("k", "d"), Ok(()));
    }

    #[test]
    fn idempotency_keys_are_random() {
        let a = idempotency_key();
        assert_eq!(a.len(), 32);
        assert_ne!(a, idempotency_key());
    }

    #[test]
    fn the_build_points_at_the_configured_server() {
        let client = LicenseClient::for_build();
        assert!(client.base_url.starts_with("https://"));
        assert!(!client.base_url.ends_with('/'));
        assert_eq!(
            client.purchase_url(),
            format!("{}/buy/{}", client.base_url, client.product_slug)
        );
    }

    /// Against the real Keygate server: a key that does not exist is a definite no.
    /// Network access; run with `cargo test -- --ignored keygate`.
    #[test]
    #[ignore]
    fn keygate_rejects_an_unknown_key() {
        let error = LicenseClient::for_build()
            .verify("KG-TEST0000-TEST0000-TEST0000-TEST0000", &"0".repeat(64))
            .unwrap_err();

        assert_eq!(
            error,
            ClientError::Rejected {
                status: 404,
                code: "LICENSE_NOT_FOUND".into(),
                activations: None,
            }
        );
    }
}
