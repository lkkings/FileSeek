//! What the user is entitled to, as the UI sees it: licensed or not, and why not.
//!
//! Nothing here limits features by plan: a valid license is a valid license.

use chrono::{DateTime, Duration, Utc};
use serde::Serialize;

use super::token::Claims;

/// How long past `exp` a license still counts while the server cannot be reached.
pub const OFFLINE_GRACE: Duration = Duration::days(7);
/// A clock this far behind a time already seen counts as turned back.
pub const CLOCK_ROLLBACK_TOLERANCE: Duration = Duration::hours(24);

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum State {
    Licensed,
    Unlicensed,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Reason {
    /// Never activated here (or deactivated).
    None,
    /// The saved license is damaged, edited, or for another device or product.
    Invalid,
    /// The server says it is no longer valid here: expired, revoked, suspended, or this
    /// device was freed in the customer portal.
    Revoked,
    /// The server could not be reached for longer than the offline grace, or the clock
    /// was turned back and the server could not be asked.
    OfflineExpired,
    /// The OS gives no machine id to activate this device with.
    NoDevice,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Entitlement {
    pub state: State,
    /// Why not licensed; `None` when licensed.
    pub reason: Option<Reason>,
    pub license_id: Option<String>,
    pub plan_name: Option<String>,
    /// `None` with a license: it never expires.
    pub valid_until: Option<DateTime<Utc>>,
    pub updates_until: Option<DateTime<Utc>>,
    /// Past `exp` and the server could not be asked: this many days left to connect.
    pub offline_days_left: Option<i64>,
    pub clock_anomaly: bool,
    pub purchase_url: String,
}

impl Entitlement {
    pub fn unlicensed(reason: Reason, purchase_url: &str) -> Entitlement {
        Entitlement {
            state: State::Unlicensed,
            reason: Some(reason),
            license_id: None,
            plan_name: None,
            valid_until: None,
            updates_until: None,
            offline_days_left: None,
            clock_anomaly: false,
            purchase_url: purchase_url.to_owned(),
        }
    }

    pub fn licensed(claims: &Claims, plan_name: Option<String>, purchase_url: &str) -> Entitlement {
        Entitlement {
            state: State::Licensed,
            reason: None,
            license_id: Some(claims.license_id.clone()),
            plan_name,
            valid_until: claims.valid_until,
            updates_until: claims.updates_until,
            offline_days_left: None,
            clock_anomaly: false,
            purchase_url: purchase_url.to_owned(),
        }
    }

    /// For debug builds, which skip licensing.
    pub fn development(purchase_url: &str) -> Entitlement {
        Entitlement {
            state: State::Licensed,
            reason: None,
            license_id: None,
            plan_name: Some("development".into()),
            valid_until: None,
            updates_until: None,
            offline_days_left: None,
            clock_anomaly: false,
            purchase_url: purchase_url.to_owned(),
        }
    }

    pub fn is_licensed(&self) -> bool {
        self.state == State::Licensed
    }
}

/// Whether the clock is behind something already seen by more than the tolerance: the
/// last time the app ran, or the time the token was issued.
pub fn clock_turned_back(
    now: DateTime<Utc>,
    last_seen: Option<DateTime<Utc>>,
    issued_at: Option<DateTime<Utc>>,
) -> bool {
    [last_seen, issued_at]
        .into_iter()
        .flatten()
        .any(|seen| now < seen - CLOCK_ROLLBACK_TOLERANCE)
}

/// Whole days left in the offline grace after `check_by`, or `None` once it is over.
pub fn offline_days_left(check_by: DateTime<Utc>, now: DateTime<Utc>) -> Option<i64> {
    let end = check_by + OFFLINE_GRACE;
    (now < end).then(|| {
        let left = end - now;
        // Rounded up: "1 day left" until the very end.
        (left.num_seconds() + 86_399) / 86_400
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn at(text: &str) -> DateTime<Utc> {
        text.parse().unwrap()
    }

    #[test]
    fn small_clock_corrections_are_not_rollback() {
        let seen = at("2026-10-10T12:00:00Z");
        assert!(!clock_turned_back(
            at("2026-10-10T11:50:00Z"),
            Some(seen),
            None
        ));
        assert!(clock_turned_back(
            at("2026-10-09T11:00:00Z"),
            Some(seen),
            None
        ));
    }

    #[test]
    fn a_clock_before_the_token_was_issued_is_rollback() {
        assert!(clock_turned_back(
            at("2026-09-01T00:00:00Z"),
            None,
            Some(at("2026-10-01T00:00:00Z"))
        ));
        assert!(!clock_turned_back(at("2026-10-01T00:00:00Z"), None, None));
    }

    #[test]
    fn offline_grace_counts_down_from_check_by() {
        let check_by = at("2026-10-01T00:00:00Z");
        assert_eq!(
            offline_days_left(check_by, at("2026-10-03T00:00:00Z")),
            Some(5)
        );
        assert_eq!(
            offline_days_left(check_by, at("2026-10-07T23:00:00Z")),
            Some(1)
        );
        assert_eq!(
            offline_days_left(check_by, at("2026-10-08T00:00:00Z")),
            None
        );
    }

    #[test]
    fn serializes_for_the_ui() {
        let value =
            serde_json::to_value(Entitlement::unlicensed(Reason::OfflineExpired, "u")).unwrap();
        assert_eq!(value["state"], "unlicensed");
        assert_eq!(value["reason"], "offline_expired");
        assert_eq!(value["purchaseUrl"], "u");
    }
}
