//! The license token Keygate signs: `base64url(payload) "." base64url(ed25519(payload))`.
//!
//! Not a JWT: no header, one key. The signature covers the payload exactly as it appears
//! in the token (the base64url text, before decoding), so nothing has to agree on a
//! canonical JSON form. Only the signature is checked before the payload is decoded.
//!
//! Of the payload, the client reads what it needs to decide locally and to show the user;
//! plan, status, grace days and features are the server's business, carried by `exp` and
//! by whether `verify` succeeds.

use base64::engine::general_purpose::URL_SAFE_NO_PAD;
use base64::Engine;
use chrono::{DateTime, Utc};
use ed25519_dalek::{Signature, Verifier, VerifyingKey};
use serde::Deserialize;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Claims {
    /// License id: shown in settings and logged instead of the key.
    pub license_id: String,
    /// Product id; must be this build's.
    pub product_id: String,
    /// The device identifier the token was issued to; must be this machine's.
    pub device: String,
    pub issued_at: DateTime<Utc>,
    /// When the client must ask the server again. Keygate already folded the check-in
    /// interval, the license's end and its grace days into this one time.
    pub check_by: DateTime<Utc>,
    /// The license's own end; `None` for one that never expires. Display only.
    pub valid_until: Option<DateTime<Utc>>,
    /// The last release date this license may install. Display only: Keygate's feed
    /// enforces it.
    pub updates_until: Option<DateTime<Utc>>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TokenError {
    /// Not `payload.signature`, or the payload is not the expected JSON.
    Malformed,
    /// The signature does not match: forged, or edited after signing.
    BadSignature,
    /// Signed for another product on the same Keygate server.
    WrongProduct,
    /// Issued to another device.
    WrongDevice,
}

impl std::fmt::Display for TokenError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(match self {
            TokenError::Malformed => "the license token is damaged",
            TokenError::BadSignature => "the license token signature is invalid",
            TokenError::WrongProduct => "the license token is for another product",
            TokenError::WrongDevice => "the license token was issued to another device",
        })
    }
}

/// What this build trusts and expects, from `build.rs`.
#[derive(Debug, Clone)]
pub struct TokenVerifier {
    key: VerifyingKey,
    /// Empty in a debug build without one configured: the product check is skipped.
    product_id: String,
}

#[derive(Deserialize)]
struct Payload {
    lid: serde_json::Value,
    #[serde(default)]
    pid: serde_json::Value,
    did: String,
    iat: i64,
    exp: i64,
    #[serde(default)]
    vun: Option<i64>,
    #[serde(default)]
    upd: Option<i64>,
}

/// Ids may come as strings or numbers; compare and show them as text.
fn id_text(value: &serde_json::Value) -> String {
    match value {
        serde_json::Value::String(text) => text.clone(),
        serde_json::Value::Null => String::new(),
        other => other.to_string(),
    }
}

fn time(seconds: i64) -> Result<DateTime<Utc>, TokenError> {
    DateTime::from_timestamp(seconds, 0).ok_or(TokenError::Malformed)
}

impl TokenVerifier {
    /// From the hex public key (`GET /api/v1/license/pubkey`) and the expected `pid`.
    pub fn new(public_key_hex: &str, product_id: &str) -> Option<TokenVerifier> {
        let bytes: Vec<u8> = (0..public_key_hex.len())
            .step_by(2)
            .map(|i| u8::from_str_radix(public_key_hex.get(i..i + 2)?, 16).ok())
            .collect::<Option<_>>()?;
        let bytes: [u8; 32] = bytes.try_into().ok()?;
        Some(TokenVerifier {
            key: VerifyingKey::from_bytes(&bytes).ok()?,
            product_id: product_id.to_owned(),
        })
    }

    /// The one this build was configured with.
    pub fn for_build() -> TokenVerifier {
        TokenVerifier::new(
            env!("KEYGATE_LICENSE_PUBLIC_KEY"),
            env!("KEYGATE_PRODUCT_ID"),
        )
        .expect("build.rs checked the license public key")
    }

    /// Checks the signature, then that the token is for this product and this device.
    /// Says nothing about time: whether `check_by` has passed is the caller's to decide.
    pub fn verify(&self, token: &str, device: &str) -> Result<Claims, TokenError> {
        let (payload, signature) = token.trim().split_once('.').ok_or(TokenError::Malformed)?;
        let signature: [u8; 64] = URL_SAFE_NO_PAD
            .decode(signature)
            .ok()
            .and_then(|bytes| bytes.try_into().ok())
            .ok_or(TokenError::BadSignature)?;
        self.key
            .verify(payload.as_bytes(), &Signature::from_bytes(&signature))
            .map_err(|_| TokenError::BadSignature)?;

        let payload: Payload = URL_SAFE_NO_PAD
            .decode(payload)
            .ok()
            .and_then(|json| serde_json::from_slice(&json).ok())
            .ok_or(TokenError::Malformed)?;
        let claims = Claims {
            license_id: id_text(&payload.lid),
            product_id: id_text(&payload.pid),
            device: payload.did,
            issued_at: time(payload.iat)?,
            check_by: time(payload.exp)?,
            valid_until: payload.vun.map(time).transpose()?,
            updates_until: payload.upd.map(time).transpose()?,
        };
        if !self.product_id.is_empty() && claims.product_id != self.product_id {
            return Err(TokenError::WrongProduct);
        }
        if claims.device != device {
            return Err(TokenError::WrongDevice);
        }
        Ok(claims)
    }
}

#[cfg(test)]
pub mod testing {
    //! Tokens signed the way Keygate signs them, with a key made up for the tests.

    use super::*;
    use ed25519_dalek::{Signer, SigningKey};

    pub const DEVICE: &str = "device-under-test";
    pub const PRODUCT: &str = "prod-fileseek";

    pub fn signing_key() -> SigningKey {
        SigningKey::from_bytes(&[7u8; 32])
    }

    pub fn public_key_hex() -> String {
        signing_key()
            .verifying_key()
            .to_bytes()
            .iter()
            .map(|b| format!("{b:02x}"))
            .collect()
    }

    pub fn verifier() -> TokenVerifier {
        TokenVerifier::new(&public_key_hex(), PRODUCT).unwrap()
    }

    /// Signs `payload` (JSON) as a token.
    pub fn sign_json(payload: &serde_json::Value) -> String {
        let encoded = URL_SAFE_NO_PAD.encode(serde_json::to_vec(payload).unwrap());
        let signature = signing_key().sign(encoded.as_bytes());
        format!("{encoded}.{}", URL_SAFE_NO_PAD.encode(signature.to_bytes()))
    }

    /// A token for this device issued at `iat`, to be checked again by `exp`.
    pub fn token(iat: i64, exp: i64) -> String {
        sign_json(&serde_json::json!({
            "lid": "lic_1", "pid": PRODUCT, "pln": "plan_pro", "sts": "active",
            "did": DEVICE, "ftr": {"export": true}, "iat": iat, "exp": exp,
        }))
    }
}

#[cfg(test)]
mod tests {
    use super::testing::*;
    use super::*;

    #[test]
    fn a_token_signed_by_the_server_key_verifies() {
        let claims = verifier()
            .verify(&token(1_700_000_000, 1_700_604_800), DEVICE)
            .unwrap();

        assert_eq!(claims.license_id, "lic_1");
        assert_eq!(claims.check_by.timestamp(), 1_700_604_800);
        assert_eq!(claims.valid_until, None);
    }

    #[test]
    fn display_fields_are_read_when_present() {
        let token = sign_json(&serde_json::json!({
            "lid": 42, "pid": PRODUCT, "did": DEVICE, "iat": 1, "exp": 2,
            "vun": 4_914_950_400_i64, "grc": 3, "upd": 1_800_000_000,
        }));

        let claims = verifier().verify(&token, DEVICE).unwrap();

        assert_eq!(claims.license_id, "42");
        // Past 2038: needs 64-bit time.
        assert_eq!(claims.valid_until.unwrap().timestamp(), 4_914_950_400);
        assert_eq!(claims.updates_until.unwrap().timestamp(), 1_800_000_000);
    }

    #[test]
    fn editing_the_payload_breaks_the_signature() {
        let original = token(1_700_000_000, 1_700_604_800);
        let (payload, signature) = original.split_once('.').unwrap();
        let mut json: serde_json::Value =
            serde_json::from_slice(&URL_SAFE_NO_PAD.decode(payload).unwrap()).unwrap();
        json["exp"] = 4_000_000_000_i64.into();
        let edited = format!(
            "{}.{signature}",
            URL_SAFE_NO_PAD.encode(serde_json::to_vec(&json).unwrap())
        );

        assert_eq!(
            verifier().verify(&edited, DEVICE),
            Err(TokenError::BadSignature)
        );
    }

    #[test]
    fn another_key_is_rejected() {
        let other = TokenVerifier::new(&"11".repeat(32), PRODUCT);
        // Not every 32 bytes are a valid point; when they are, the signature must fail.
        if let Some(other) = other {
            assert_eq!(
                other.verify(&token(1, 2), DEVICE),
                Err(TokenError::BadSignature)
            );
        }
    }

    #[test]
    fn a_token_for_another_device_is_rejected() {
        assert_eq!(
            verifier().verify(&token(1, 2), "someone-else"),
            Err(TokenError::WrongDevice)
        );
    }

    #[test]
    fn a_token_for_another_product_is_rejected() {
        let token = sign_json(&serde_json::json!({
            "lid": "x", "pid": "other-app", "did": DEVICE, "iat": 1, "exp": 2,
        }));

        assert_eq!(
            verifier().verify(&token, DEVICE),
            Err(TokenError::WrongProduct)
        );
    }

    #[test]
    fn without_a_configured_product_any_product_passes() {
        let verifier = TokenVerifier::new(&public_key_hex(), "").unwrap();
        let token = sign_json(&serde_json::json!({
            "lid": "x", "pid": "whatever", "did": DEVICE, "iat": 1, "exp": 2,
        }));

        assert!(verifier.verify(&token, DEVICE).is_ok());
    }

    #[test]
    fn garbage_is_malformed_or_unsigned() {
        assert_eq!(
            verifier().verify("no-dot", DEVICE),
            Err(TokenError::Malformed)
        );
        assert_eq!(
            verifier().verify("abc.def", DEVICE),
            Err(TokenError::BadSignature)
        );
        let not_claims = sign_json(&serde_json::json!({"hello": 1}));
        assert_eq!(
            verifier().verify(&not_claims, DEVICE),
            Err(TokenError::Malformed)
        );
    }

    #[test]
    fn the_build_key_parses() {
        let _ = TokenVerifier::for_build();
    }

    #[test]
    fn a_bad_hex_key_is_refused() {
        assert!(TokenVerifier::new("zz", "").is_none());
        assert!(TokenVerifier::new(&"ab".repeat(31), "").is_none());
    }
}
