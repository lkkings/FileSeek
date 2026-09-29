use std::collections::HashSet;
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};

pub const EVENT_NAME: &str = "system-import-request";

#[derive(Debug, Clone, PartialEq, Eq, Default, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SystemImportRequest {
    pub paths: Vec<String>,
    pub errors: Vec<String>,
}

impl SystemImportRequest {
    pub fn from_paths<I>(paths: I) -> Self
    where
        I: IntoIterator<Item = PathBuf>,
    {
        let (paths, errors) = normalize_paths_with_errors(paths);
        Self {
            paths: paths
                .into_iter()
                .map(|path| path.to_string_lossy().into_owned())
                .collect(),
            errors,
        }
    }
}

#[allow(dead_code)]
pub fn normalize_paths<I>(paths: I) -> Result<Vec<PathBuf>, String>
where
    I: IntoIterator<Item = PathBuf>,
{
    let mut normalized = Vec::new();
    let mut seen = HashSet::new();

    for path in paths {
        let normalized_path = normalize_path(&path)?;
        let key = normalized_path.to_string_lossy().to_string();
        if seen.insert(key) {
            normalized.push(normalized_path);
        }
    }

    Ok(normalized)
}

pub fn normalize_paths_with_errors<I>(paths: I) -> (Vec<PathBuf>, Vec<String>)
where
    I: IntoIterator<Item = PathBuf>,
{
    let mut valid = Vec::new();
    let mut errors = Vec::new();
    let mut seen = HashSet::new();

    for path in paths {
        match normalize_path(&path) {
            Ok(normalized) => {
                let key = normalized.to_string_lossy().to_string();
                if seen.insert(key) {
                    valid.push(normalized);
                }
            }
            Err(error) => errors.push(error),
        }
    }

    (valid, errors)
}

pub fn absolutize<I>(paths: I, current_directory: &Path) -> Vec<PathBuf>
where
    I: IntoIterator<Item = PathBuf>,
{
    paths
        .into_iter()
        .map(|path| {
            if path.is_absolute() {
                path
            } else {
                current_directory.join(path)
            }
        })
        .collect()
}

pub fn request_from_args<I>(args: I, current_directory: &Path) -> Option<SystemImportRequest>
where
    I: IntoIterator<Item = String>,
{
    let intent = crate::startup_args::parse(args);
    if intent.add_files.is_empty() {
        return None;
    }

    Some(SystemImportRequest::from_paths(absolutize(
        intent.add_files,
        current_directory,
    )))
}

#[tauri::command]
pub fn take_pending_system_import(
    pending: tauri::State<'_, std::sync::Mutex<Option<SystemImportRequest>>>,
) -> SystemImportRequest {
    pending
        .lock()
        .map(|mut pending| pending.take())
        .ok()
        .flatten()
        .unwrap_or_default()
}

#[allow(dead_code)]
pub fn normalize_path(path: &Path) -> Result<PathBuf, String> {
    if path.as_os_str().is_empty() {
        return Err("empty path".to_owned());
    }

    let metadata = std::fs::metadata(path)
        .map_err(|error| format!("could not read {}: {error}", path.display()))?;
    if !metadata.is_file() {
        return Err(format!("{} is not a file", path.display()));
    }

    let normalized = path.canonicalize().unwrap_or_else(|_| path.to_path_buf());
    if !is_readable(&normalized) {
        return Err(format!("{} is not readable", path.display()));
    }

    Ok(normalized)
}

fn is_readable(path: &Path) -> bool {
    std::fs::File::open(path).is_ok()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::os::unix::fs::PermissionsExt;

    #[cfg(unix)]
    fn temp_file(name: &str) -> PathBuf {
        let mut path = std::env::temp_dir();
        path.push(format!(
            "fileseek-import-test-{name}-{}",
            std::process::id()
        ));
        let _ = fs::remove_file(&path);
        fs::write(&path, b"file").expect("temp file");
        path
    }

    #[cfg(unix)]
    #[test]
    fn normalizes_posix_paths_and_removes_duplicates() {
        let first = temp_file("posix-a");
        let duplicate = first.clone();
        let second = temp_file("posix-b");

        let paths = normalize_paths(vec![first, duplicate, second]).expect("paths");

        assert_eq!(paths.len(), 2);
        assert!(paths.iter().all(|path| path.is_absolute()));
    }

    #[cfg(unix)]
    #[test]
    fn rejects_missing_directory_and_unreadable_paths() {
        let missing = PathBuf::from("/definitely-missing-fileseek-path");
        let directory = std::env::temp_dir();
        let unreadable = temp_file("unreadable");
        let mut permissions = fs::metadata(&unreadable).expect("metadata").permissions();
        permissions.set_mode(0o000);
        fs::set_permissions(&unreadable, permissions).expect("permissions");

        assert!(normalize_paths(vec![missing]).is_err());
        assert!(normalize_paths(vec![directory]).is_err());
        assert!(normalize_paths(vec![unreadable]).is_err());
    }

    #[cfg(unix)]
    #[test]
    fn rejects_empty_paths() {
        assert!(normalize_paths(vec![PathBuf::new()]).is_err());
    }

    #[cfg(unix)]
    #[test]
    fn converts_relative_paths_with_the_second_instance_directory() {
        let paths = absolutize(vec![PathBuf::from("file.pdf")], Path::new("/tmp"));
        assert_eq!(paths, vec![PathBuf::from("/tmp/file.pdf")]);
    }

    #[cfg(unix)]
    #[test]
    fn first_launch_and_resident_launch_use_the_same_import_request() {
        let file = temp_file("instance");
        let args = [
            "fileseek".to_owned(),
            "--add".to_owned(),
            file.to_string_lossy().into_owned(),
        ];
        let request = request_from_args(args, Path::new("/")).expect("request");

        assert_eq!(
            request.paths,
            vec![file
                .canonicalize()
                .expect("canonical")
                .to_string_lossy()
                .into_owned()]
        );
    }

    #[cfg(unix)]
    #[test]
    fn duplicate_launches_are_normalized_to_one_request() {
        let file = temp_file("duplicate");
        let path = file.to_string_lossy().into_owned();
        let request = request_from_args(
            [
                "fileseek".to_owned(),
                "--add".to_owned(),
                path.clone(),
                path.clone(),
            ],
            Path::new("/"),
        )
        .expect("request");

        assert_eq!(
            request.paths,
            vec![file
                .canonicalize()
                .expect("canonical")
                .to_string_lossy()
                .into_owned()]
        );
    }

    #[test]
    fn launches_without_an_import_intent_focus_the_window() {
        assert!(request_from_args(["fileseek".to_owned()], Path::new("/")).is_none());
    }

    #[cfg(unix)]
    #[test]
    fn reports_invalid_paths_without_discarding_valid_paths() {
        let valid = temp_file("mixed");
        let (paths, errors) = normalize_paths_with_errors(vec![
            valid,
            PathBuf::from("/definitely-missing-fileseek-path"),
        ]);

        assert_eq!(paths.len(), 1);
        assert_eq!(errors.len(), 1);
        assert!(errors[0].contains("could not read"));
    }

    #[cfg(windows)]
    #[test]
    fn normalizes_windows_paths_and_removes_duplicates() {
        let first = temp_file("windows-a");
        let duplicate = first.clone();
        let second = temp_file("windows-b");

        let paths = normalize_paths(vec![first, duplicate, second]).expect("paths");

        assert_eq!(paths.len(), 2);
        assert!(paths.iter().all(|path| path.is_absolute()));
    }

    #[cfg(windows)]
    #[test]
    fn rejects_windows_missing_directory_and_unreadable_paths() {
        let missing = PathBuf::from(r"C:\definitely-missing-fileseek-path");
        let directory = std::env::temp_dir();
        let unreadable = temp_file("windows-unreadable");
        let mut permissions = fs::metadata(&unreadable).expect("metadata").permissions();
        permissions.set_mode(0o000);
        fs::set_permissions(&unreadable, permissions).expect("permissions");

        assert!(normalize_paths(vec![missing]).is_err());
        assert!(normalize_paths(vec![directory]).is_err());
        assert!(normalize_paths(vec![unreadable]).is_err());
    }
}
