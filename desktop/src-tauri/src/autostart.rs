use std::path::PathBuf;

pub const LAUNCH_AGENT_LABEL: &str = "com.fileseek.desktop";
#[allow(dead_code)]
pub const ENTRY_NAME: &str = "FileSeek";

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LoginCommand {
    pub program: PathBuf,
    pub args: Vec<String>,
}

impl LoginCommand {
    pub fn new(program: impl Into<PathBuf>, args: Vec<String>) -> Self {
        Self {
            program: program.into(),
            args,
        }
    }

    pub fn current() -> Result<Self, String> {
        let program = std::env::current_exe()
            .map_err(|error| format!("could not determine the executable path: {error}"))?;
        Ok(Self::new(program, vec!["--silent".to_owned()]))
    }

    pub fn program_str(&self) -> String {
        self.program.to_string_lossy().into_owned()
    }

    #[allow(dead_code)]
    pub fn args_str(&self) -> String {
        self.args.join(" ")
    }
}

pub fn launch_agent_plist(command: &LoginCommand) -> String {
    let mut args = String::new();
    args.push_str(&escape_xml(&command.program_str()));
    for arg in &command.args {
        args.push_str("</string><string>");
        args.push_str(&escape_xml(arg));
    }

    format!(
        r#"<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{args}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
"#,
        label = LAUNCH_AGENT_LABEL,
        args = args,
    )
}

#[allow(dead_code)]
pub fn autostart_desktop_entry(command: &LoginCommand) -> String {
    let exec = format!(
        "{} {}",
        escape_desktop_exec(&command.program_str()),
        command.args_str()
    );
    format!(
        "[Desktop Entry]\nType=Application\nName={name}\nComment=Start FileSeek in the tray\nExec={exec}\nTerminal=false\nX-GNOME-Autostart-enabled=true\n",
        name = ENTRY_NAME,
        exec = exec
    )
}

#[allow(dead_code)]
pub fn run_key_value(command: &LoginCommand) -> String {
    format!("\"{}\" {}", command.program_str(), command.args_str())
}

pub trait AutostartStore {
    fn read(&self) -> Result<Option<String>, String>;
    fn write(&self, contents: &str) -> Result<(), String>;
    fn remove(&self) -> Result<(), String>;
    #[allow(dead_code)]
    fn location(&self) -> String;
}

pub struct FileStore {
    path: PathBuf,
}

impl FileStore {
    pub fn new(path: impl Into<PathBuf>) -> Self {
        Self { path: path.into() }
    }
}

impl AutostartStore for FileStore {
    fn read(&self) -> Result<Option<String>, String> {
        std::fs::read_to_string(&self.path)
            .map(Some)
            .or_else(|error| {
                if error.kind() == std::io::ErrorKind::NotFound {
                    Ok(None)
                } else {
                    Err(format!("could not read {}: {error}", self.path.display()))
                }
            })
    }

    fn write(&self, contents: &str) -> Result<(), String> {
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
            Err(error) => Err(format!("could not remove {}: {error}", self.path.display())),
        }
    }

    fn location(&self) -> String {
        self.path.display().to_string()
    }
}

#[cfg(windows)]
pub struct RunKeyStore;

#[cfg(windows)]
impl AutostartStore for RunKeyStore {
    fn read(&self) -> Result<Option<String>, String> {
        use winreg::enums::{HKEY_CURRENT_USER, KEY_READ};
        use winreg::RegKey;

        let key = RegKey::predef(HKEY_CURRENT_USER)
            .open_subkey_with_flags(r"Software\Microsoft\Windows\CurrentVersion\Run", KEY_READ)
            .map_err(|error| format!("could not open the Run key: {error}"))?;

        key.get_value::<String, _>(ENTRY_NAME)
            .map(Some)
            .or_else(|error| {
                if error.kind() == std::io::ErrorKind::NotFound {
                    Ok(None)
                } else {
                    Err(format!("could not read the Run value: {error}"))
                }
            })
    }

    fn write(&self, contents: &str) -> Result<(), String> {
        use winreg::enums::{HKEY_CURRENT_USER, KEY_WRITE};
        use winreg::RegKey;

        let (key, _) = RegKey::predef(HKEY_CURRENT_USER)
            .create_subkey_with_flags(r"Software\Microsoft\Windows\CurrentVersion\Run", KEY_WRITE)
            .map_err(|error| format!("could not open the Run key: {error}"))?;
        key.set_value(ENTRY_NAME, &contents.to_string())
            .map_err(|error| format!("could not write the Run value: {error}"))
    }

    fn remove(&self) -> Result<(), String> {
        use winreg::enums::{HKEY_CURRENT_USER, KEY_WRITE};
        use winreg::RegKey;

        let key = RegKey::predef(HKEY_CURRENT_USER)
            .open_subkey_with_flags(r"Software\Microsoft\Windows\CurrentVersion\Run", KEY_WRITE)
            .map_err(|error| format!("could not open the Run key: {error}"))?;
        match key.delete_value(ENTRY_NAME) {
            Ok(()) => Ok(()),
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(()),
            Err(error) => Err(format!("could not remove the Run value: {error}")),
        }
    }

    fn location(&self) -> String {
        r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run\FileSeek".to_owned()
    }
}

pub struct Autostart<S: AutostartStore> {
    store: S,
    command: LoginCommand,
}

impl<S: AutostartStore> Autostart<S> {
    pub fn new(store: S, command: LoginCommand) -> Self {
        Self { store, command }
    }

    pub fn is_enabled(&self) -> Result<bool, String> {
        let Some(contents) = self.store.read()? else {
            return Ok(false);
        };
        Ok(contents.contains(&self.command.program_str())
            && self
                .command
                .args
                .iter()
                .all(|arg| contents.contains(arg.as_str())))
    }

    pub fn set(&self, enabled: bool) -> Result<bool, String> {
        if enabled {
            self.store
                .write(&self.registration_contents())
                .map_err(|error| error.to_string())?;
        } else {
            self.store.remove().map_err(|error| error.to_string())?;
        }
        self.is_enabled()
    }

    #[allow(dead_code)]
    pub fn location(&self) -> String {
        self.store.location()
    }

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

#[cfg(not(windows))]
pub type PlatformStore = FileStore;

#[cfg(windows)]
pub type PlatformStore = RunKeyStore;

pub fn platform_store() -> Result<PlatformStore, String> {
    #[cfg(target_os = "macos")]
    {
        let home = std::env::var_os("HOME").ok_or_else(|| "could not determine home".to_owned())?;
        let path = Path::new(&home)
            .join("Library")
            .join("LaunchAgents")
            .join(format!("{LAUNCH_AGENT_LABEL}.plist"));
        Ok(FileStore::new(path))
    }

    #[cfg(all(unix, not(target_os = "macos")))]
    {
        let config = std::env::var_os("XDG_CONFIG_HOME")
            .map(PathBuf::from)
            .or_else(|| std::env::var_os("HOME").map(|home| Path::new(&home).join(".config")))
            .ok_or_else(|| "could not determine the config directory".to_owned())?;
        Ok(FileStore::new(
            config.join("autostart").join("fileseek.desktop"),
        ))
    }

    #[cfg(windows)]
    {
        Ok(RunKeyStore)
    }
}

pub fn current() -> Result<Autostart<PlatformStore>, String> {
    Ok(Autostart::new(platform_store()?, LoginCommand::current()?))
}

fn escape_xml(value: &str) -> String {
    value
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
}

#[allow(dead_code)]
fn escape_desktop_exec(program: &str) -> String {
    let escaped = program.replace('\\', r"\\").replace('"', r#"\""#);
    if program.contains(' ') {
        format!("\"{escaped}\"")
    } else {
        escaped
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::cell::RefCell;
    use std::fs;

    struct InMemoryStore {
        contents: RefCell<Option<String>>,
    }

    impl InMemoryStore {
        fn new() -> Self {
            Self {
                contents: RefCell::new(None),
            }
        }
    }

    impl AutostartStore for InMemoryStore {
        fn read(&self) -> Result<Option<String>, String> {
            Ok(self.contents.borrow().clone())
        }

        fn write(&self, contents: &str) -> Result<(), String> {
            *self.contents.borrow_mut() = Some(contents.to_owned());
            Ok(())
        }

        fn remove(&self) -> Result<(), String> {
            *self.contents.borrow_mut() = None;
            Ok(())
        }

        fn location(&self) -> String {
            "memory".to_owned()
        }
    }

    fn command() -> LoginCommand {
        LoginCommand::new(
            "/Applications/FileSeek.app/Contents/MacOS/fileseek",
            vec!["--silent".to_owned()],
        )
    }

    #[test]
    fn launch_agent_contains_silent_and_no_keep_alive() {
        let contents = launch_agent_plist(&command());
        assert!(contents.contains("--silent"));
        assert!(contents.contains("RunAtLoad"));
        assert!(!contents.contains("KeepAlive"));
    }

    #[test]
    fn desktop_entry_contains_silent() {
        let contents = autostart_desktop_entry(&command());
        assert!(contents.contains("--silent"));
        assert!(contents.contains("X-GNOME-Autostart-enabled=true"));
    }

    #[test]
    fn run_key_quotes_program_and_contains_silent() {
        let contents = run_key_value(&command());
        assert!(contents.contains("\"/Applications/FileSeek.app"));
        assert!(contents.contains("--silent"));
    }

    #[test]
    fn file_store_round_trip_and_path_mismatch() {
        let mut path = std::env::temp_dir();
        path.push(format!("fileseek-autostart-test-{}", std::process::id()));
        let _ = fs::remove_dir_all(&path);
        fs::create_dir_all(&path).expect("temp dir");
        let store_path = path.join("autostart.plist");
        let store = FileStore::new(&store_path);
        let autostart = Autostart::new(store, command());

        assert!(!autostart.is_enabled().expect("state"));
        assert!(autostart.set(true).expect("enable"));
        assert!(autostart.is_enabled().expect("enabled"));

        let other = LoginCommand::new("/other/fileseek", vec!["--silent".to_owned()]);
        let mismatch = Autostart::new(FileStore::new(&store_path), other);
        assert!(!mismatch.is_enabled().expect("mismatch"));

        assert!(!autostart.set(false).expect("disable"));
        assert!(!autostart.is_enabled().expect("disabled"));
    }

    #[test]
    fn autostart_store_round_trip_and_path_mismatch() {
        let store = InMemoryStore::new();
        let autostart = Autostart::new(store, command());

        assert!(!autostart.is_enabled().expect("state"));
        assert!(autostart.set(true).expect("enable"));
        assert!(autostart.is_enabled().expect("enabled"));

        let other = LoginCommand::new("/other/fileseek", vec!["--silent".to_owned()]);
        let mismatch = Autostart::new(InMemoryStore::new(), other);
        assert!(!mismatch.is_enabled().expect("mismatch"));

        assert!(!autostart.set(false).expect("disable"));
        assert!(!autostart.is_enabled().expect("disabled"));
    }
}
