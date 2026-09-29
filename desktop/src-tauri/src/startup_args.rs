use std::path::PathBuf;

#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct StartupIntent {
    pub silent: bool,
    pub add_files: Vec<PathBuf>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum StartupVisibility {
    Show,
    Hide,
}

pub fn visibility(intent: &StartupIntent) -> StartupVisibility {
    if intent.silent && intent.add_files.is_empty() {
        StartupVisibility::Hide
    } else {
        StartupVisibility::Show
    }
}

pub fn parse<I>(args: I) -> StartupIntent
where
    I: IntoIterator<Item = String>,
{
    let mut intent = StartupIntent::default();
    let mut collecting_files = false;

    for arg in args {
        if arg == "--silent" {
            intent.silent = true;
            collecting_files = false;
        } else if arg == "--add" {
            collecting_files = true;
        } else if collecting_files && !arg.starts_with('-') {
            intent.add_files.push(PathBuf::from(arg));
        }
    }

    intent
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_silent_without_files() {
        let intent = parse(["desktop", "--silent"].map(String::from));
        assert!(intent.silent);
        assert!(intent.add_files.is_empty());
    }

    #[test]
    fn parses_added_files_and_ignores_executable() {
        let intent = parse(
            [
                "/usr/bin/fileseek".to_owned(),
                "--add".to_owned(),
                "/tmp/a.pdf".to_owned(),
                "/tmp/b.png".to_owned(),
            ]
            .into_iter(),
        );
        assert!(!intent.silent);
        assert_eq!(
            intent.add_files,
            vec![PathBuf::from("/tmp/a.pdf"), PathBuf::from("/tmp/b.png")]
        );
    }

    #[test]
    fn normal_startup_shows_and_silent_startup_hides() {
        let normal = parse(["desktop"].map(String::from));
        let silent = parse(["desktop", "--silent"].map(String::from));
        let silent_import = parse(
            ["desktop", "--silent", "--add", "/tmp/file.pdf"]
                .map(String::from)
                .into_iter(),
        );

        assert_eq!(visibility(&normal), StartupVisibility::Show);
        assert_eq!(visibility(&silent), StartupVisibility::Hide);
        assert_eq!(visibility(&silent_import), StartupVisibility::Show);
    }
}
