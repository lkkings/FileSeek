from pathlib import Path

import pytest

from fileseek.paths import (
    AppPaths,
    UnsupportedPlatformError,
    is_network_path,
    normalize_platform,
)

HOME = Path("/home/tester")


def test_normalize_platform_maps_known_values() -> None:
    assert normalize_platform("win32") == "win32"
    assert normalize_platform("darwin") == "darwin"
    assert normalize_platform("linux") == "linux"
    assert normalize_platform("linux2") == "linux"


def test_normalize_platform_rejects_unknown() -> None:
    with pytest.raises(UnsupportedPlatformError, match="freebsd"):
        normalize_platform("freebsd")


def test_windows_uses_appdata_env() -> None:
    paths = AppPaths.resolve(
        platform="win32",
        env={"APPDATA": "C:/Users/t/AppData/Roaming", "LOCALAPPDATA": "C:/Users/t/AppData/Local"},
        home=HOME,
    )

    assert paths.config_dir == Path("C:/Users/t/AppData/Roaming/FileSeek")
    assert paths.data_dir == Path("C:/Users/t/AppData/Local/FileSeek")
    assert paths.cache_dir == Path("C:/Users/t/AppData/Local/FileSeek/Cache")


def test_windows_falls_back_to_home_when_env_missing() -> None:
    paths = AppPaths.resolve(platform="win32", env={}, home=HOME)

    assert paths.config_dir == HOME / "AppData/Roaming/FileSeek"
    assert paths.data_dir == HOME / "AppData/Local/FileSeek"


def test_macos_uses_library_directories() -> None:
    paths = AppPaths.resolve(platform="darwin", env={}, home=HOME)

    assert paths.config_dir == HOME / "Library/Application Support/FileSeek"
    assert paths.data_dir == HOME / "Library/Application Support/FileSeek"
    assert paths.cache_dir == HOME / "Library/Caches/FileSeek"


def test_linux_honours_xdg_env() -> None:
    paths = AppPaths.resolve(
        platform="linux",
        env={
            "XDG_CONFIG_HOME": "/cfg",
            "XDG_DATA_HOME": "/data",
            "XDG_CACHE_HOME": "/cache",
        },
        home=HOME,
    )

    assert paths.config_dir == Path("/cfg/fileseek")
    assert paths.data_dir == Path("/data/fileseek")
    assert paths.cache_dir == Path("/cache/fileseek")


def test_linux_falls_back_to_xdg_defaults() -> None:
    paths = AppPaths.resolve(platform="linux", env={}, home=HOME)

    assert paths.config_dir == HOME / ".config/fileseek"
    assert paths.data_dir == HOME / ".local/share/fileseek"
    assert paths.cache_dir == HOME / ".cache/fileseek"


def test_empty_env_value_is_ignored() -> None:
    paths = AppPaths.resolve(platform="linux", env={"XDG_CONFIG_HOME": ""}, home=HOME)

    assert paths.config_dir == HOME / ".config/fileseek"


def test_resolve_defaults_to_running_platform() -> None:
    paths = AppPaths.resolve()

    assert paths.config_dir.is_absolute()
    assert paths.data_dir.is_absolute()


def test_derived_file_locations_sit_under_base_dirs() -> None:
    paths = AppPaths.resolve(platform="linux", env={}, home=HOME)

    assert paths.database_path == paths.data_dir / "metadata.db"
    assert paths.index_dir == paths.data_dir / "index"
    assert paths.config_file == paths.config_dir / "config.yaml"
    assert paths.connection_file == paths.config_dir / "connection.json"
    assert paths.model_dir == paths.data_dir / "models"
    assert paths.thumbnail_cache_dir == paths.cache_dir / "thumbnails"


def test_model_dir_defaults_under_data_dir() -> None:
    paths = AppPaths.resolve(platform="linux", env={}, home=HOME)

    assert paths.model_dir == paths.data_dir / "models"
    assert paths.model_dir_override is None


def test_model_dir_can_be_moved_off_the_system_drive() -> None:
    paths = AppPaths.resolve(platform="win32", env={}, home=HOME).with_model_dir(
        "D:/FileSeek/.models"
    )

    assert paths.model_dir == Path("D:/FileSeek/.models")


def test_moving_model_dir_leaves_other_locations_alone() -> None:
    original = AppPaths.resolve(platform="win32", env={}, home=HOME)

    moved = original.with_model_dir("D:/elsewhere")

    assert moved.data_dir == original.data_dir
    assert moved.config_dir == original.config_dir
    assert moved.database_path == original.database_path


def test_model_dir_override_can_be_cleared() -> None:
    paths = AppPaths.resolve(platform="linux", env={}, home=HOME).with_model_dir("/mnt/big/models")

    restored = paths.with_model_dir(None)

    assert restored.model_dir == restored.data_dir / "models"


def test_create_dirs_is_idempotent(tmp_path: Path) -> None:
    paths = AppPaths(
        config_dir=tmp_path / "cfg",
        data_dir=tmp_path / "data",
        cache_dir=tmp_path / "cache",
    )

    paths.create_dirs()
    paths.create_dirs()

    assert paths.all_dirs() == (paths.config_dir, paths.data_dir, paths.cache_dir)
    for directory in (*paths.all_dirs(), paths.index_dir, paths.thumbnail_cache_dir):
        assert directory.is_dir()


@pytest.mark.parametrize(
    "candidate",
    [
        r"\\nas\share\library",
        "//nas/share/library",
        "smb://nas/library",
        "nfs://nas/library",
        "webdav://host/library",
    ],
)
def test_network_paths_are_detected(candidate: str) -> None:
    assert is_network_path(candidate) is True


@pytest.mark.parametrize(
    "candidate",
    ["", "D:/FileSeek/library", "/home/tester/library", r"C:\Users\t\AppData"],
)
def test_local_paths_are_not_network(candidate: str) -> None:
    assert is_network_path(candidate) is False
