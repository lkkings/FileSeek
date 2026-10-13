//! The `identifier` Keygate binds an activation to.
//!
//! One value: the OS install's machine id, salted and hashed. Keygate matches it exactly,
//! so it must not drift: not the MAC address (VPNs, docks and private MACs change it), not
//! the install path (moving the app, or macOS App Translocation, changes it). The serial
//! number is never sent, hashed or not.
//!
//! An OS reinstall changes the machine id; the user then frees the old device in the
//! customer portal and activates again.

use sha2::{Digest, Sha256};

/// Changing it changes every user's identifier and costs each an activation.
const SALT: &str = "fileseek-device-v2:";

/// This machine's identifier, or `None` when the OS gives no machine id. Never made up:
/// a random id would be new on every launch and use up the user's activations.
pub fn identifier() -> Option<String> {
    from_machine_id(&read_machine_id())
}

fn from_machine_id(machine_id: &str) -> Option<String> {
    let machine_id = machine_id.trim();
    if machine_id.is_empty() {
        return None;
    }
    let digest = Sha256::digest(format!("{SALT}{machine_id}").as_bytes());
    Some(digest.iter().map(|b| format!("{b:02x}")).collect())
}

/// `"Key" = "value"` from `ioreg -l` style output.
#[cfg_attr(not(target_os = "macos"), allow(dead_code))]
fn ioreg_value(output: &str, key: &str) -> String {
    let needle = format!("\"{key}\" = \"");
    output
        .lines()
        .find_map(|line| {
            let start = line.find(&needle)? + needle.len();
            let rest = &line[start..];
            Some(rest[..rest.find('"')?].to_owned())
        })
        .unwrap_or_default()
}

#[cfg(target_os = "macos")]
fn read_machine_id() -> String {
    let output = std::process::Command::new("ioreg")
        .args(["-rd1", "-c", "IOPlatformExpertDevice"])
        .output()
        .ok()
        .filter(|output| output.status.success())
        .map(|output| String::from_utf8_lossy(&output.stdout).into_owned())
        .unwrap_or_default();
    ioreg_value(&output, "IOPlatformUUID")
}

#[cfg(target_os = "windows")]
fn read_machine_id() -> String {
    use winreg::enums::{HKEY_LOCAL_MACHINE, KEY_READ, KEY_WOW64_64KEY};
    use winreg::RegKey;
    // The 64-bit view: a 32-bit view would read a different (or no) value.
    RegKey::predef(HKEY_LOCAL_MACHINE)
        .open_subkey_with_flags(
            r"SOFTWARE\Microsoft\Cryptography",
            KEY_READ | KEY_WOW64_64KEY,
        )
        .and_then(|key| key.get_value::<String, _>("MachineGuid"))
        .unwrap_or_default()
}

#[cfg(all(unix, not(target_os = "macos")))]
fn read_machine_id() -> String {
    ["/etc/machine-id", "/var/lib/dbus/machine-id"]
        .iter()
        .map(|path| std::fs::read_to_string(path).unwrap_or_default())
        .find(|id| !id.trim().is_empty())
        .unwrap_or_default()
}

#[cfg(not(any(unix, windows)))]
fn read_machine_id() -> String {
    String::new()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn is_a_salted_sha256_of_the_machine_id() {
        let id = from_machine_id("8E7B-1234\n").unwrap();
        assert_eq!(id.len(), 64);
        assert_eq!(Some(id.clone()), from_machine_id("8E7B-1234"));
        // Salted: not the bare hash a third party could compute from the machine id.
        let bare: String = Sha256::digest(b"8E7B-1234")
            .iter()
            .map(|b| format!("{b:02x}"))
            .collect();
        assert_ne!(id, bare);
    }

    #[test]
    fn no_machine_id_means_no_identifier() {
        assert_eq!(from_machine_id(""), None);
        assert_eq!(from_machine_id("  \n"), None);
    }

    #[test]
    fn parses_ioreg_output() {
        let output = r#"  | "IOPlatformSerialNumber" = "C02XYZ"
  | "IOPlatformUUID" = "8E7B-1234""#;
        assert_eq!(ioreg_value(output, "IOPlatformUUID"), "8E7B-1234");
        assert_eq!(ioreg_value(output, "Missing"), "");
    }

    #[test]
    fn reads_this_machine_stably() {
        let first = identifier().expect("this machine has no machine id");
        assert_eq!(Some(first), identifier());
    }
}
