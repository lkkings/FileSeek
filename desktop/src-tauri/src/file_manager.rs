use std::path::{Path, PathBuf};

#[cfg_attr(target_os = "macos", allow(dead_code))]
pub const WINDOWS_SHELL_VERB_ID: &str = "AddToFileSeek";
pub const MACOS_FINDER_EXTENSION_ID: &str = "com.fileseek.desktop.FinderSync";

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FileManagerCommand {
    pub program: PathBuf,
}

impl FileManagerCommand {
    pub fn current() -> Result<Self, String> {
        let program = std::env::current_exe()
            .map_err(|error| format!("could not determine the executable path: {error}"))?;
        Ok(Self { program })
    }

    #[cfg_attr(target_os = "macos", allow(dead_code))]
    pub fn program_str(&self) -> String {
        self.program.to_string_lossy().into_owned()
    }
}

#[cfg_attr(target_os = "macos", allow(dead_code))]
pub fn explorer_command_value(command: &FileManagerCommand) -> String {
    format!("\"{}\" --add \"%*\"", command.program_str())
}

#[cfg_attr(not(target_os = "linux"), allow(dead_code))]
pub fn nautilus_extension_source(command: &FileManagerCommand) -> String {
    format!(
        r#"import subprocess
import nautilus
from urllib.parse import unquote

FILESEEK_PROGRAM = {program}


class FileSeekMenuProvider:
    def get_file_items(self, window, files):
        return self._menu(files)

    def get_background_items(self, window, file):
        return []

    def _menu(self, files):
        item = nautilus.MenuItem(
            name="FileSeek::add_to_fileseek",
            label="Add to FileSeek",
            tip="Add selected files to FileSeek",
        )
        item.connect("activate", self.activate, files)
        return [item]

    @staticmethod
    def activate(menu_item, files):
        paths = []
        for file_info in files:
            if file_info.is_directory():
                continue
            paths.append(unquote(file_info.get_uri()).removeprefix("file://"))
        if paths:
            subprocess.Popen([FILESEEK_PROGRAM, "--add", *paths])
"#,
        program = format!("{:?}", command.program_str()),
    )
}

#[cfg_attr(not(target_os = "linux"), allow(dead_code))]
pub fn dolphin_service_entry(command: &FileManagerCommand) -> String {
    format!(
        "[Desktop Entry]\nType=Service\nMimeType=all/allfiles;\nActions={action};\nX-KDE-Priority=TopLevel\nX-KDE-Submenu=\n\n[Desktop Action {action}]\nName=Add to FileSeek\nExec=\"{program}\" --add %F\nIcon=fileseek\n",
        action = WINDOWS_SHELL_VERB_ID,
        program = command.program_str()
    )
}

#[cfg_attr(not(target_os = "linux"), allow(dead_code))]
pub fn linux_paths(data_home: &Path) -> (PathBuf, PathBuf) {
    let nautilus = data_home
        .join("nautilus-python")
        .join("extensions")
        .join("fileseek.py");
    let dolphin = data_home.join("kservices5").join("FileSeek.desktop");
    (nautilus, dolphin)
}

pub fn set_integration(enabled: bool) -> Result<bool, String> {
    let command = FileManagerCommand::current()?;
    set_integration_with(command, enabled)
}

pub fn set_integration_with(command: FileManagerCommand, enabled: bool) -> Result<bool, String> {
    #[cfg(target_os = "macos")]
    {
        let _ = &command;
        if enabled && !is_enabled()? {
            return Err("approve the Finder extension in macOS system settings".to_owned());
        }
        return is_enabled();
    }

    #[cfg(not(target_os = "macos"))]
    {
        if !enabled {
            disable()?;
            return is_enabled();
        }

        enable(&command)?;
        is_enabled()
    }
}

pub fn is_enabled() -> Result<bool, String> {
    is_enabled_with(FileManagerCommand::current()?)
}

pub fn is_supported() -> Result<bool, String> {
    FileManagerCommand::current()?;
    #[cfg(target_os = "macos")]
    {
        return Ok(finder_extension_path(std::env::current_exe().unwrap_or_default()).exists());
    }
    #[cfg(not(target_os = "macos"))]
    {
        Ok(true)
    }
}

#[cfg(any(windows, target_os = "linux"))]
fn enable(command: &FileManagerCommand) -> Result<(), String> {
    #[cfg(windows)]
    {
        use winreg::enums::{HKEY_CURRENT_USER, KEY_WRITE};
        use winreg::RegKey;

        let root = RegKey::predef(HKEY_CURRENT_USER);
        let (shell, _) = root
            .create_subkey_with_flags(r"Software\Classes\*\shell", KEY_WRITE)
            .map_err(|error| format!("could not open the Explorer shell key: {error}"))?;
        let (verb, _) = shell
            .create_subkey_with_flags(WINDOWS_SHELL_VERB_ID, KEY_WRITE)
            .map_err(|error| format!("could not create the FileSeek shell verb: {error}"))?;
        verb.set_value("", &"Add to FileSeek")
            .map_err(|error| format!("could not set the FileSeek menu label: {error}"))?;
        let (command_key, _) = verb
            .create_subkey_with_flags("command", KEY_WRITE)
            .map_err(|error| format!("could not create the FileSeek command: {error}"))?;
        command_key
            .set_value("", &explorer_command_value(command))
            .map_err(|error| format!("could not set the FileSeek command: {error}"))
    }

    #[cfg(target_os = "linux")]
    {
        let data_home = dirs::data_dir()
            .ok_or_else(|| "could not determine the user data directory".to_owned())?;
        let (nautilus_path, dolphin_path) = linux_paths(&data_home);
        write_file(&nautilus_path, &nautilus_extension_source(command))?;
        write_file(&dolphin_path, &dolphin_service_entry(command))
    }
}

#[cfg(any(windows, target_os = "linux"))]
fn disable() -> Result<(), String> {
    #[cfg(windows)]
    {
        use winreg::enums::{HKEY_CURRENT_USER, KEY_WRITE};
        use winreg::RegKey;

        let root = RegKey::predef(HKEY_CURRENT_USER);

        // Try to open and delete the subkey recursively
        let result = root
            .open_subkey_with_flags(r"Software\Classes\*\shell", KEY_WRITE)
            .and_then(|shell| {
                // First try to open the verb key to delete its children
                if let Ok(verb_key) = shell.open_subkey_with_flags(WINDOWS_SHELL_VERB_ID, KEY_WRITE) {
                    // Delete all subkeys first
                    for subkey_name in verb_key.enum_keys().filter_map(|k| k.ok()) {
                        let _ = verb_key.delete_subkey(&subkey_name);
                    }
                }
                // Then delete the verb key itself
                shell.delete_subkey(WINDOWS_SHELL_VERB_ID)
            })
            .or_else(|error| {
                if error.kind() == std::io::ErrorKind::NotFound {
                    Ok(())
                } else {
                    Err(error)
                }
            });

        result.map_err(|error| format!("could not remove the FileSeek shell verb: {error}"))
    }

    #[cfg(target_os = "linux")]
    {
        let data_home = dirs::data_dir()
            .ok_or_else(|| "could not determine the user data directory".to_owned())?;
        let (nautilus_path, dolphin_path) = linux_paths(&data_home);
        remove_file(&nautilus_path)?;
        remove_file(&dolphin_path)
    }
}

fn is_enabled_with(command: FileManagerCommand) -> Result<bool, String> {
    let _ = &command;

    #[cfg(target_os = "macos")]
    {
        return Ok(
            finder_extension_path(std::env::current_exe().unwrap_or_default()).exists()
                && finder_extension_approved(),
        );
    }

    #[cfg(windows)]
    {
        use winreg::enums::{HKEY_CURRENT_USER, KEY_READ};
        use winreg::RegKey;

        let root = RegKey::predef(HKEY_CURRENT_USER);
        let command_value = root
            .open_subkey_with_flags(
                &format!(
                    r"Software\Classes\*\shell\{}\command",
                    WINDOWS_SHELL_VERB_ID
                ),
                KEY_READ,
            )
            .and_then(|key| key.get_value::<String, _>(""));
        Ok(command_value
            .map(|value| value == explorer_command_value(&command))
            .unwrap_or(false))
    }

    #[cfg(target_os = "linux")]
    {
        let data_home = dirs::data_dir()
            .ok_or_else(|| "could not determine the user data directory".to_owned())?;
        let (nautilus_path, dolphin_path) = linux_paths(&data_home);
        Ok(nautilus_path.exists() && dolphin_path.exists())
    }
}

#[cfg(target_os = "macos")]
pub fn finder_extension_approval_required() -> bool {
    finder_extension_path(std::env::current_exe().unwrap_or_default()).exists()
        && !finder_extension_approved()
}

#[cfg(target_os = "macos")]
fn finder_extension_approved() -> bool {
    std::process::Command::new("pluginkit")
        .args(["-m", "-i", MACOS_FINDER_EXTENSION_ID])
        .output()
        .ok()
        .and_then(|output| String::from_utf8(output.stdout).ok())
        .map(|output| output.trim().contains('+'))
        .unwrap_or(false)
}

#[cfg(target_os = "linux")]
fn write_file(path: &Path, contents: &str) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)
            .map_err(|error| format!("could not create {}: {error}", parent.display()))?;
    }
    std::fs::write(path, contents)
        .map_err(|error| format!("could not write {}: {error}", path.display()))
}

#[cfg(target_os = "linux")]
fn remove_file(path: &Path) -> Result<(), String> {
    match std::fs::remove_file(path) {
        Ok(()) => Ok(()),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(()),
        Err(error) => Err(format!("could not remove {}: {error}", path.display())),
    }
}

#[cfg(target_os = "macos")]
fn finder_extension_path(executable: PathBuf) -> PathBuf {
    let mut current = Some(executable.as_path());
    while let Some(path) = current {
        if path.extension().is_some_and(|extension| extension == "app") {
            return path
                .join("Contents")
                .join("PlugIns")
                .join("FileSeekFinderSync.appex");
        }
        current = path.parent();
    }
    PathBuf::from("FileSeekFinderSync.appex")
}

#[cfg(test)]
mod tests {
    use super::*;

    fn command() -> FileManagerCommand {
        FileManagerCommand {
            program: PathBuf::from("/Applications/FileSeek.app/Contents/MacOS/fileseek"),
        }
    }

    #[test]
    fn explorer_command_forwards_all_selected_files() {
        let contents = explorer_command_value(&command());
        assert!(contents.contains("--add"));
        assert!(contents.contains("\"%*\""));
    }

    #[test]
    fn nautilus_extension_is_a_native_first_level_menu_provider() {
        let contents = nautilus_extension_source(&command());
        assert!(contents.contains("class FileSeekMenuProvider"));
        assert!(contains("get_file_items", &contents));
        assert!(contains("Add to FileSeek", &contents));
        assert!(contains("subprocess.Popen", &contents));
    }

    #[test]
    fn dolphin_service_entry_is_top_level_and_accepts_multiple_files() {
        let contents = dolphin_service_entry(&command());
        assert!(contains("X-KDE-Priority=TopLevel", &contents));
        assert!(contains("X-KDE-Submenu=\n", &contents));
        assert!(contains("--add %F", &contents));
    }

    #[test]
    fn linux_paths_are_user_scoped() {
        let (nautilus, dolphin) = linux_paths(Path::new("/home/demo/.local/share"));
        assert_eq!(
            nautilus,
            PathBuf::from("/home/demo/.local/share/nautilus-python/extensions/fileseek.py")
        );
        assert_eq!(
            dolphin,
            PathBuf::from("/home/demo/.local/share/kservices5/FileSeek.desktop")
        );
    }

    fn contains(needle: &str, contents: &str) -> bool {
        contents.contains(needle)
    }
}
