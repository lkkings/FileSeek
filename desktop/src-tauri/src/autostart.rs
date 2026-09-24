//! The start-at-login switch, and how each platform registers it.
//!
//! `desktop-client` asks for a start-at-login switch whose default state is visible to the
//! user (系统 **MUST** 提供开机自启开关，且该开关默认状态对用户可见). The default is off:
//! nothing is registered until the user turns it on, so a fresh install adds nothing to the
//! user's login items.
//!
//! The three platforms register in entirely different places:
//!
//! | Platform | Registration |
//! |----------|--------------|
//! | macOS    | a LaunchAgent plist in `~/Library/LaunchAgents` |
//! | Linux    | an XDG autostart `.desktop` file under `$XDG_CONFIG_HOME/autostart` |
//! | Windows  | a value under `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` |
//!
//! Two of those are files and one is a registry value, so the switch itself is written
//! against an `AutostartStore` — read, write, remove one entry — and each platform supplies
//! its own. That keeps the toggle semantics platform-independent and testable, and leaves
//! only the raw registry access behind `cfg(windows)`.

use std::path::{Path, PathBuf};

/// The LaunchAgent label on macOS, which is also its file name.
pub const LAUNCH_AGENT_LABEL: &str = "com.fileseek.desktop";

/// The name the registration carries: the Windows registry value, and the display name in
/// the Linux autostart entry.
#[allow(dead_code, reason = "used on Windows and Linux; tested on all platforms")]
pub const ENTRY_NAME: &str = "FileSeek";

/// What login should start.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LoginCommand {
    pub program: PathBuf,
}

impl LoginCommand {
    pub fn new(program: impl Into<PathBuf>) -> Self {
        LoginCommand { program: program.into() }
    }

    /// The running executable — what login should start again.
    pub fn current() -> Result<Self, String> {
        std::env::current_exe()
            .map(LoginCommand::new)
            .map_err(|error| format!("could not determine this executable's path: {error}"))
    }

    pub fn program_str(&self) -> String {
        self.program.to_string_lossy().into_owned()
    }
}

/// The LaunchAgent plist macOS reads at login.
///
/// `RunAtLoad` is what makes it a login item; without it the agent is merely known to
/// `launchd` and never started. `KeepAlive` is deliberately absent — the user quitting from
/// the tray must stay quit, and `launchd` would otherwise restart the app immediately.
pub fn launch_agent_plist(command: &LoginCommand) -> String {
    format!(
        r#"<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{program}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
"#,
        label = LAUNCH_AGENT_LABEL,
        program = escape_xml(&command.program_str()),
    )
}

/// The XDG autostart entry Linux desktop environments read at login.
///
/// `X-GNOME-Autostart-enabled=true` is what GNOME's own Startup Applications reads, so the
/// state shown there agrees with this switch rather than contradicting it.
#[allow(dead_code, reason = "used on Linux; tested on all platforms")]
pub fn autostart_desktop_entry(command: &LoginCommand) -> String {
    format!(
        "[Desktop Entry]\n\
         Type=Application\n\
         Name={name}\n\
         Comment=启动 FileSeek 并常驻托盘\n\
         Exec={exec}\n\
         Terminal=false\n\
         X-GNOME-Autostart-enabled=true\n",
        name = ENTRY_NAME,
        exec = escape_desktop_exec(&command.program_str()),
    )
}

/// The value written under the Windows `Run` key.
///
/// Quoted because the `Run` key's value is a command line: an unquoted path containing a
/// space (`C:\Program Files\...`) would be parsed as a program plus arguments.
#[allow(dead_code, reason = "used on Windows; tested on all platforms")]
pub fn run_key_value(command: &LoginCommand) -> String {
    format!("\"{}\"", command.program_str())
}

/// Escape text going into the plist's XML.
fn escape_xml(value: &str) -> String {
    value
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
}

/// Escape a program path for a desktop entry's `Exec`.
///
/// The desktop entry spec reserves the backslash and quotes inside a quoted argument, and
/// requires quoting for a value containing spaces.
#[allow(dead_code, reason = "used on Linux; tested on all platforms")]
fn escape_desktop_exec(program: &str) -> String {
    let escaped = program.replace('\\', r"\\").replace('"', r#"\""#);
    if program.contains(' ') {
        format!("\"{escaped}\"")
    } else {
        escaped
    }
}

/// Where the macOS LaunchAgent plist lives.
pub fn launch_agent_path(home: &Path) -> PathBuf {
    home.join("Library")
        .join("LaunchAgents")
        .join(format!("{LAUNCH_AGENT_LABEL}.plist"))
}

/// Where the Linux autostart entry lives.
///
/// Honours `XDG_CONFIG_HOME` the same way `sidecar::connection_file_path` does, so both
/// land in the same config root when a user has moved it.
#[allow(dead_code, reason = "used on Linux; tested on all platforms")]
pub fn autostart_desktop_path(home: &Path) -> PathBuf {
    let config_home = std::env::var_os("XDG_CONFIG_HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|| home.join(".config"));
    config_home.join("autostart").join("fileseek.desktop")
}

/// One platform's login-item registration: at most one entry, read/written/removed whole.
///
/// The trait exists so the toggle below is the same code on every platform, and so its
/// behaviour can be tested against a store that writes to a temp directory instead of the
/// user's real login items.
pub trait AutostartStore {
    /// The current entry's contents, or `None` when nothing is registered.
    fn read(&self) -> Result<Option<String>, String>;

    /// Register `contents`, replacing any existing entry.
    fn write(&self, contents: &str) -> Result<(), String>;

    /// Remove the entry. Removing what is not there is success, not an error.
    fn remove(&self) -> Result<(), String>;

    /// Where the entry lives, for messages and for tests that assert on the location.
    fn location(&self) -> String;
}

/// A store backed by a single file: the macOS LaunchAgent and the Linux autostart entry.
pub struct FileStore {
    path: PathBuf,
}

impl FileStore {
    pub fn new(path: impl Into<PathBuf>) -> Self {
        FileStore { path: path.into() }
    }
}

impl AutostartStore for FileStore {
    fn read(&self) -> Result<Option<String>, String> {
        match std::fs::read_to_string(&self.path) {
            Ok(contents) => Ok(Some(contents)),
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(None),
            Err(error) => Err(format!(
                "could not read {}: {error}",
                self.path.display()
            )),
        }
    }

    fn write(&self, contents: &str) -> Result<(), String> {
        // `~/Library/LaunchAgents` and `~/.config/autostart` do not exist on a machine that
        // has never had a login item, so the directory is created rather than assumed.
        if let Some(parent) = self.path.parent() {
            std::fs::create_dir_all(parent)
                .map_err(|error| format!("could not create {}: {error}", parent.display()))?;
        }
        std::fs::write(&self.path, contents)
            .map_err(|error| format!("could not write {}: {error}", self.path.display()))
    }

    fn remove(&self) -> Result<(), String> {
        match std::fs::remove_file(&self.path) {
            Ok(()) => Ok(()),
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(()),
            Err(error) => Err(format!(
                "could not remove {}: {error}",
                self.path.display()
            )),
        }
    }

    fn location(&self) -> String {
        self.path.display().to_string()
    }
}

/// The Windows `Run` key: `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`.
///
/// Under `HKEY_CURRENT_USER` rather than `HKEY_LOCAL_MACHINE` so turning the switch on
/// needs no elevation and affects only the user who asked for it.
#[cfg(windows)]
pub struct RunKeyStore {
    value_name: String,
}

#[cfg(windows)]
impl RunKeyStore {
    const SUBKEY: &'static str = r"Software\Microsoft\Windows\CurrentVersion\Run";

    pub fn new(value_name: impl Into<String>) -> Self {
        RunKeyStore { value_name: value_name.into() }
    }

    fn open_for_write(&self) -> Result<winreg::RegKey, String> {
        use winreg::enums::HKEY_CURRENT_USER;
        use winreg::RegKey;

        RegKey::predef(HKEY_CURRENT_USER)
            .create_subkey(Self::SUBKEY)
            .map(|(key, _)| key)
            .map_err(|error| format!("could not open the Run key: {error}"))
    }
}

#[cfg(windows)]
impl AutostartStore for RunKeyStore {
    fn read(&self) -> Result<Option<String>, String> {
        use winreg::enums::{HKEY_CURRENT_USER, KEY_READ};
        use winreg::RegKey;

        let key = match RegKey::predef(HKEY_CURRENT_USER).open_subkey_with_flags(Self::SUBKEY, KEY_READ)
        {
            Ok(key) => key,
            // No Run key at all is the same as no entry in it.
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(None),
            Err(error) => return Err(format!("could not open the Run key: {error}")),
        };

        match key.get_value::<String, _>(&self.value_name) {
            Ok(value) => Ok(Some(value)),
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(None),
            Err(error) => Err(format!("could not read the {} value: {error}", self.value_name)),
        }
    }

    fn write(&self, contents: &str) -> Result<(), String> {
        self.open_for_write()?
            .set_value(&self.value_name, &contents.to_string())
            .map_err(|error| format!("could not write the {} value: {error}", self.value_name))
    }

    fn remove(&self) -> Result<(), String> {
        let key = self.open_for_write()?;
        match key.delete_value(&self.value_name) {
            Ok(()) => Ok(()),
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(()),
            Err(error) => Err(format!("could not remove the {} value: {error}", self.value_name)),
        }
    }

    fn location(&self) -> String {
        format!(r"HKCU\{}\{}", Self::SUBKEY, self.value_name)
    }
}

/// The start-at-login switch over one platform's registration.
pub struct Autostart<S: AutostartStore> {
    store: S,
    command: LoginCommand,
}

impl<S: AutostartStore> Autostart<S> {
    pub fn new(store: S, command: LoginCommand) -> Self {
        Autostart { store, command }
    }

    /// Whether login would start *this* executable.
    ///
    /// An entry that exists but names a different program reads as off, which is what keeps
    /// the switch honest after the app is moved or reinstalled: login would start the old
    /// path, not this one, so reporting "on" would be a claim the system does not back.
    pub fn is_enabled(&self) -> Result<bool, String> {
        let Some(contents) = self.store.read()? else {
            return Ok(false);
        };
        Ok(contents.contains(&self.command.program_str()))
    }

    /// Turn the switch on or off, then report the state actually in effect.
    ///
    /// The return value is re-read from the store rather than echoed from `enabled`, so a
    /// caller never shows a state the system does not hold.
    pub fn set(&self, enabled: bool) -> Result<bool, String> {
        if enabled {
            self.store.write(&self.registration_contents())?;
        } else {
            self.store.remove()?;
        }
        self.is_enabled()
    }

    /// Where this platform keeps the registration.
    pub fn location(&self) -> String {
        self.store.location()
    }

    /// What gets registered, in the format this platform expects.
    fn registration_contents(&self) -> String {
        #[cfg(target_os = "macos")]
        {
            launch_agent_plist(&self.command)
        }
        #[cfg(windows)]
        {
            run_key_value(&self.command)
        }
        #[cfg(all(unix, not(target_os = "macos")))]
        {
            autostart_desktop_entry(&self.command)
        }
    }
}

/// The switch for the current platform and the running executable.
pub fn current() -> Result<Autostart<PlatformStore>, String> {
    let command = LoginCommand::current()?;
    Ok(Autostart::new(platform_store()?, command))
}

/// The store type in use on this platform, named so `current` has a concrete return type.
#[cfg(not(windows))]
pub type PlatformStore = FileStore;

#[cfg(windows)]
pub type PlatformStore = RunKeyStore;

#[cfg(not(windows))]
fn platform_store() -> Result<PlatformStore, String> {
    let home = crate::connection::home_dir()
        .ok_or_else(|| "could not determine the home directory".to_string())?;

    #[cfg(target_os = "macos")]
    {
        Ok(FileStore::new(launch_agent_path(&home)))
    }
    #[cfg(all(unix, not(target_os = "macos")))]
    {
        Ok(FileStore::new(autostart_desktop_path(&home)))
    }
}

#[cfg(windows)]
fn platform_store() -> Result<PlatformStore, String> {
    Ok(RunKeyStore::new(ENTRY_NAME))
}

/// What the UI shows for the switch: its state and where it is registered.
#[derive(Debug, Clone, serde::Serialize)]
pub struct AutostartStatus {
    pub enabled: bool,
    pub location: String,
}

/// Read the switch's current state.
///
/// The settings UI calls this on open so the default — off, nothing registered — is visible
/// rather than assumed.
#[tauri::command]
pub fn autostart_status() -> Result<AutostartStatus, String> {
    let switch = current()?;
    Ok(AutostartStatus { enabled: switch.is_enabled()?, location: switch.location() })
}

/// Turn the switch on or off, returning the state that actually took effect.
#[tauri::command]
pub fn set_autostart(enabled: bool) -> Result<AutostartStatus, String> {
    let switch = current()?;
    let in_effect = switch.set(enabled)?;
    Ok(AutostartStatus { enabled: in_effect, location: switch.location() })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::test_support::{temp_dir, TempDir};

    /// A switch over a file in a temp directory, standing in for the platform's real
    /// registration location. The contents written are the platform's own format, so what
    /// these tests exercise is the toggle's behaviour rather than a test-only encoding.
    fn switch_in(name: &str) -> (Autostart<FileStore>, PathBuf, TempDir) {
        let dir = temp_dir(name);
        let entry = dir.path.join("login-item");
        let command = LoginCommand::new("/Applications/FileSeek.app/Contents/MacOS/FileSeek");
        (Autostart::new(FileStore::new(&entry), command), entry, dir)
    }

    #[test]
    fn nothing_is_registered_by_default() {
        // The default is off: a fresh install adds no login item.
        let (switch, entry, _dir) = switch_in("autostart-default");

        assert!(!switch.is_enabled().unwrap());
        assert!(!entry.exists(), "nothing should be registered before the switch is used");
    }

    #[test]
    fn turning_it_on_registers_and_reads_back_as_on() {
        // desktop-client: 开关状态与系统注册项一致.
        let (switch, entry, _dir) = switch_in("autostart-on");

        let in_effect = switch.set(true).unwrap();

        assert!(in_effect, "set should report the state it put in place");
        assert!(entry.exists(), "the registration should exist at {}", entry.display());
        let contents = std::fs::read_to_string(&entry).unwrap();
        assert!(
            contents.contains("/Applications/FileSeek.app/Contents/MacOS/FileSeek"),
            "the registration should name the program to start: {contents}"
        );
        assert!(switch.is_enabled().unwrap());
    }

    #[test]
    fn turning_it_off_removes_the_registration() {
        // desktop-client: 用户关闭开机自启 → 后续系统启动时不再自动运行.
        let (switch, entry, _dir) = switch_in("autostart-off");
        switch.set(true).unwrap();

        let in_effect = switch.set(false).unwrap();

        assert!(!in_effect);
        assert!(!entry.exists(), "the registration should be gone");
        assert!(!switch.is_enabled().unwrap());
    }

    #[test]
    fn turning_it_off_twice_is_harmless() {
        let (switch, _entry, _dir) = switch_in("autostart-off-twice");

        assert!(!switch.set(false).unwrap());
        assert!(!switch.set(false).unwrap());
    }

    #[test]
    fn turning_it_on_twice_leaves_one_registration() {
        let (switch, entry, _dir) = switch_in("autostart-on-twice");

        switch.set(true).unwrap();
        let first = std::fs::read_to_string(&entry).unwrap();
        switch.set(true).unwrap();
        let second = std::fs::read_to_string(&entry).unwrap();

        assert_eq!(first, second, "re-registering should replace, not append");
    }

    #[test]
    fn a_registration_naming_another_program_reads_as_off() {
        // The app was moved or reinstalled: login would start the old path, so reporting
        // "on" for this executable would be a claim the system does not back.
        let dir = temp_dir("autostart-stale");
        let entry = dir.path.join("login-item");
        std::fs::write(&entry, "/old/location/FileSeek").unwrap();
        let switch = Autostart::new(
            FileStore::new(&entry),
            LoginCommand::new("/new/location/FileSeek"),
        );

        assert!(!switch.is_enabled().unwrap());
    }

    #[test]
    fn registering_creates_the_directory_when_it_is_absent() {
        // A machine that has never had a login item has no ~/Library/LaunchAgents.
        let dir = temp_dir("autostart-mkdir");
        let entry = dir.path.join("LaunchAgents").join("login-item");
        let switch = Autostart::new(FileStore::new(&entry), LoginCommand::new("/bin/fileseek"));

        assert!(switch.set(true).unwrap());
        assert!(entry.exists());
    }

    #[test]
    fn the_switch_reports_where_it_registers() {
        let (switch, entry, _dir) = switch_in("autostart-location");

        assert_eq!(switch.location(), entry.display().to_string());
    }

    #[test]
    fn the_launch_agent_runs_at_load_and_names_the_program() {
        let plist = launch_agent_plist(&LoginCommand::new("/Applications/FileSeek.app/x"));

        assert!(plist.contains("<key>RunAtLoad</key>"), "{plist}");
        assert!(plist.contains("<true/>"), "{plist}");
        assert!(plist.contains("/Applications/FileSeek.app/x"), "{plist}");
        assert!(plist.contains(LAUNCH_AGENT_LABEL), "{plist}");
        // KeepAlive would restart the app after the user quit from the tray.
        assert!(!plist.contains("KeepAlive"), "{plist}");
    }

    #[test]
    fn the_desktop_entry_is_an_enabled_autostart_application() {
        let entry = autostart_desktop_entry(&LoginCommand::new("/usr/bin/fileseek"));

        assert!(entry.contains("Type=Application"), "{entry}");
        assert!(entry.contains("Exec=/usr/bin/fileseek"), "{entry}");
        // What GNOME's Startup Applications reads, so it agrees with this switch.
        assert!(entry.contains("X-GNOME-Autostart-enabled=true"), "{entry}");
    }

    #[test]
    fn a_program_path_with_spaces_is_quoted_in_the_desktop_entry() {
        let entry = autostart_desktop_entry(&LoginCommand::new("/opt/File Seek/fileseek"));

        assert!(entry.contains(r#"Exec="/opt/File Seek/fileseek""#), "{entry}");
    }

    #[test]
    fn the_run_key_value_is_quoted() {
        // An unquoted `C:\Program Files\...` would be parsed as a program plus arguments.
        let value = run_key_value(&LoginCommand::new(r"C:\Program Files\FileSeek\FileSeek.exe"));

        assert_eq!(value, r#""C:\Program Files\FileSeek\FileSeek.exe""#);
    }

    #[test]
    fn xml_reserved_characters_in_the_path_are_escaped() {
        let plist = launch_agent_plist(&LoginCommand::new("/Apps/Fi&le<Seek>/x"));

        assert!(plist.contains("/Apps/Fi&amp;le&lt;Seek&gt;/x"), "{plist}");
    }

    #[test]
    fn the_platform_paths_are_the_ones_each_system_reads() {
        let home = Path::new("/home/testuser");

        assert_eq!(
            launch_agent_path(home),
            home.join("Library").join("LaunchAgents").join("com.fileseek.desktop.plist"),
        );
        let desktop = autostart_desktop_path(home);
        assert_eq!(desktop.file_name().unwrap(), "fileseek.desktop");
        assert_eq!(desktop.parent().unwrap().file_name().unwrap(), "autostart");
    }
}
