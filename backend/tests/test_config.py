from pathlib import Path
from typing import Any

import pytest
import yaml

from fileseek.config import (
    DEFAULT_MAX_CONCURRENT,
    MAX_ALLOWED_CONCURRENT,
    MAX_VIDEO_FPS,
    ConfigError,
    NasSettings,
    ProcessingSettings,
    Settings,
    load_settings,
    save_settings,
)
from fileseek.paths import AppPaths

HOME = Path("/home/tester")


def write_config(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return path


def test_defaults_are_usable_without_a_file(tmp_path: Path) -> None:
    settings = load_settings(tmp_path / "config.yaml")

    assert settings.library_root is None
    assert settings.is_configured is False
    assert settings.processing.max_concurrent == DEFAULT_MAX_CONCURRENT


def test_first_run_is_detected_until_a_library_is_chosen() -> None:
    assert Settings().is_configured is False
    assert Settings().with_library_root("D:/library").is_configured is True


def test_library_root_round_trips(tmp_path: Path) -> None:
    target = tmp_path / "config.yaml"
    save_settings(Settings().with_library_root("D:/library"), target)

    assert load_settings(target).library_root == Path("D:/library")


def test_model_dir_round_trips(tmp_path: Path) -> None:
    target = tmp_path / "config.yaml"
    settings = Settings(model_dir=Path("D:/FileSeek/.models"))

    save_settings(settings, target)

    assert load_settings(target).model_dir == Path("D:/FileSeek/.models")


def test_model_dir_reaches_app_paths(tmp_path: Path) -> None:
    """The override is only real if it actually moves where weights are read from."""
    settings = Settings(model_dir=Path("D:/FileSeek/.models"))
    paths = AppPaths.resolve(platform="win32", env={}, home=HOME)

    applied = settings.apply_to(paths)

    assert applied.model_dir == Path("D:/FileSeek/.models")
    assert applied.database_path == paths.database_path


def test_absent_model_dir_keeps_the_platform_default() -> None:
    paths = AppPaths.resolve(platform="linux", env={}, home=HOME)

    applied = Settings().apply_to(paths)

    assert applied.model_dir == paths.data_dir / "models"


def test_model_dir_on_a_share_is_rejected(tmp_path: Path) -> None:
    target = write_config(tmp_path / "config.yaml", {"models": {"path": "//nas/share/models"}})

    with pytest.raises(ConfigError, match="local path") as excinfo:
        load_settings(target)

    assert excinfo.value.field_name == "models.path"


def test_full_settings_survive_a_round_trip(tmp_path: Path) -> None:
    target = tmp_path / "config.yaml"
    original = Settings(
        library_root=Path("Z:/library"),
        model_dir=Path("D:/models"),
        processing=ProcessingSettings(
            max_concurrent=5,
            video_fps=2.0,
            thumbnail_size=(400, 225),
            device_preference="cpu",
        ),
        nas=NasSettings(
            enabled=True,
            protocol="smb",
            host="192.168.1.100",
            share="fileseek",
            username="user",
            has_credential=True,
            auto_discover=False,
            health_check_seconds=60,
        ),
    )

    save_settings(original, target)

    assert load_settings(target) == original


def test_saved_file_is_readable_yaml(tmp_path: Path) -> None:
    target = tmp_path / "config.yaml"

    save_settings(Settings().with_library_root("D:/library"), target)

    parsed = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert Path(parsed["library"]["root"]) == Path("D:/library")


def test_save_creates_the_parent_directory(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "deeper" / "config.yaml"

    save_settings(Settings(), target)

    assert target.is_file()


def test_save_leaves_no_staging_file(tmp_path: Path) -> None:
    target = tmp_path / "config.yaml"

    save_settings(Settings(), target)

    assert list(tmp_path.glob("*.writing")) == []


def test_save_replaces_a_previous_config(tmp_path: Path) -> None:
    target = tmp_path / "config.yaml"
    save_settings(Settings().with_library_root("D:/first"), target)

    save_settings(Settings().with_library_root("D:/second"), target)

    assert load_settings(target).library_root == Path("D:/second")


def test_nas_password_is_never_written(tmp_path: Path) -> None:
    """Credentials belong in the OS keychain, so the file only records their presence."""
    target = tmp_path / "config.yaml"
    settings = Settings(
        nas=NasSettings(enabled=True, host="nas.local", username="user", has_credential=True)
    )

    save_settings(settings, target)

    text = target.read_text(encoding="utf-8")
    assert "password" not in text.lower()
    assert "has_credential: true" in text


def test_credential_key_identifies_the_connection() -> None:
    nas = NasSettings(protocol="smb", host="nas.local", share="lib", username="user")

    assert nas.credential_key == "smb://user@nas.local/lib"


def test_malformed_yaml_is_reported(tmp_path: Path) -> None:
    target = tmp_path / "config.yaml"
    target.write_text("library: {root: [unclosed", encoding="utf-8")

    with pytest.raises(ConfigError, match="could not parse"):
        load_settings(target)


def test_non_mapping_root_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "config.yaml"
    target.write_text("- just\n- a\n- list\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="expected a mapping"):
        load_settings(target)


def test_empty_file_yields_defaults(tmp_path: Path) -> None:
    target = tmp_path / "config.yaml"
    target.write_text("", encoding="utf-8")

    assert load_settings(target) == Settings()


@pytest.mark.parametrize("value", [0, -1, MAX_ALLOWED_CONCURRENT + 1])
def test_out_of_range_concurrency_is_rejected(tmp_path: Path, value: int) -> None:
    target = write_config(tmp_path / "config.yaml", {"processing": {"max_concurrent": value}})

    with pytest.raises(ConfigError, match="max_concurrent"):
        load_settings(target)


def test_non_numeric_concurrency_is_rejected(tmp_path: Path) -> None:
    target = write_config(tmp_path / "config.yaml", {"processing": {"max_concurrent": "three"}})

    with pytest.raises(ConfigError, match="whole number"):
        load_settings(target)


def test_boolean_is_not_accepted_as_a_number(tmp_path: Path) -> None:
    target = write_config(tmp_path / "config.yaml", {"processing": {"max_concurrent": True}})

    with pytest.raises(ConfigError, match="whole number"):
        load_settings(target)


@pytest.mark.parametrize("value", [0, -1, MAX_VIDEO_FPS + 1])
def test_out_of_range_video_fps_is_rejected(tmp_path: Path, value: float) -> None:
    target = write_config(tmp_path / "config.yaml", {"processing": {"video_fps": value}})

    with pytest.raises(ConfigError, match="video_fps"):
        load_settings(target)


def test_non_numeric_video_fps_is_rejected(tmp_path: Path) -> None:
    target = write_config(tmp_path / "config.yaml", {"processing": {"video_fps": "fast"}})

    with pytest.raises(ConfigError, match="expected a number"):
        load_settings(target)


def test_fractional_video_fps_is_accepted(tmp_path: Path) -> None:
    target = write_config(tmp_path / "config.yaml", {"processing": {"video_fps": 0.5}})

    assert load_settings(target).processing.video_fps == 0.5


def test_unknown_device_preference_is_rejected(tmp_path: Path) -> None:
    target = write_config(
        tmp_path / "config.yaml", {"processing": {"device_preference": "quantum"}}
    )

    with pytest.raises(ConfigError, match="auto, gpu or cpu"):
        load_settings(target)


@pytest.mark.parametrize("preference", ["auto", "gpu", "cpu"])
def test_each_device_preference_is_accepted(tmp_path: Path, preference: str) -> None:
    target = write_config(
        tmp_path / "config.yaml", {"processing": {"device_preference": preference}}
    )

    assert load_settings(target).processing.device_preference == preference


def test_malformed_thumbnail_size_is_rejected(tmp_path: Path) -> None:
    target = write_config(tmp_path / "config.yaml", {"processing": {"thumbnail_size": [320]}})

    with pytest.raises(ConfigError, match="width, height"):
        load_settings(target)


def test_non_positive_thumbnail_dimension_is_rejected(tmp_path: Path) -> None:
    target = write_config(tmp_path / "config.yaml", {"processing": {"thumbnail_size": [320, 0]}})

    with pytest.raises(ConfigError, match="thumbnail_size"):
        load_settings(target)


def test_non_mapping_processing_section_is_rejected(tmp_path: Path) -> None:
    target = write_config(tmp_path / "config.yaml", {"processing": ["nope"]})

    with pytest.raises(ConfigError, match="processing"):
        load_settings(target)


def test_enabled_nas_requires_a_host(tmp_path: Path) -> None:
    target = write_config(tmp_path / "config.yaml", {"nas": {"enabled": True}})

    with pytest.raises(ConfigError, match="host is required"):
        load_settings(target)


def test_disabled_nas_needs_no_host(tmp_path: Path) -> None:
    target = write_config(tmp_path / "config.yaml", {"nas": {"enabled": False}})

    assert load_settings(target).nas.enabled is False


def test_unknown_nas_protocol_is_rejected(tmp_path: Path) -> None:
    target = write_config(
        tmp_path / "config.yaml", {"nas": {"protocol": "telepathy", "host": "nas"}}
    )

    with pytest.raises(ConfigError, match="smb, nfs or webdav"):
        load_settings(target)


@pytest.mark.parametrize("protocol", ["smb", "nfs", "webdav"])
def test_each_nas_protocol_is_accepted(tmp_path: Path, protocol: str) -> None:
    target = write_config(
        tmp_path / "config.yaml",
        {"nas": {"enabled": True, "protocol": protocol, "host": "nas.local"}},
    )

    assert load_settings(target).nas.protocol == protocol


def test_bad_health_check_interval_is_rejected(tmp_path: Path) -> None:
    target = write_config(
        tmp_path / "config.yaml", {"nas": {"host": "nas", "health_check_seconds": 0}}
    )

    with pytest.raises(ConfigError, match="health_check_seconds"):
        load_settings(target)


def test_non_mapping_nas_section_is_rejected(tmp_path: Path) -> None:
    target = write_config(tmp_path / "config.yaml", {"nas": "yes please"})

    with pytest.raises(ConfigError, match="nas"):
        load_settings(target)


def test_auto_discover_defaults_on_and_can_be_disabled(tmp_path: Path) -> None:
    assert NasSettings().auto_discover is True

    target = write_config(tmp_path / "config.yaml", {"nas": {"auto_discover": False}})

    assert load_settings(target).nas.auto_discover is False


def test_empty_library_root_is_rejected(tmp_path: Path) -> None:
    target = write_config(tmp_path / "config.yaml", {"library": {"root": "   "}})

    with pytest.raises(ConfigError, match="non-empty string"):
        load_settings(target)


def test_non_mapping_library_section_is_rejected(tmp_path: Path) -> None:
    target = write_config(tmp_path / "config.yaml", {"library": 42})

    with pytest.raises(ConfigError, match="library"):
        load_settings(target)


def test_non_mapping_models_section_is_rejected(tmp_path: Path) -> None:
    target = write_config(tmp_path / "config.yaml", {"models": 42})

    with pytest.raises(ConfigError, match="models"):
        load_settings(target)


def test_null_sections_fall_back_to_defaults(tmp_path: Path) -> None:
    target = tmp_path / "config.yaml"
    target.write_text("library:\nmodels:\nprocessing:\nnas:\n", encoding="utf-8")

    settings = load_settings(target)

    assert settings == Settings()


def test_unicode_paths_survive_a_round_trip(tmp_path: Path) -> None:
    target = tmp_path / "config.yaml"

    save_settings(Settings().with_library_root("D:/文件库"), target)

    assert load_settings(target).library_root == Path("D:/文件库")


def test_settings_from_none_yields_defaults() -> None:
    assert Settings.from_dict(None) == Settings()
    assert ProcessingSettings.from_dict(None) == ProcessingSettings()
    assert NasSettings.from_dict(None) == NasSettings()
