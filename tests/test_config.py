"""Tests for spurt.core.config — configuration management."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from spurt.core.config import Config, CONFIG_FILENAME
from spurt.core.models import DEFAULT_MODEL


class TestConfigDefaults:
    """Tests for default configuration values."""

    def test_load_no_file_returns_defaults(self, tmp_path: Path):
        cfg = Config.load(tmp_path)
        assert cfg.key_mode == "hold"
        assert cfg.model == DEFAULT_MODEL

    @patch("spurt.core.config.platform.system", return_value="Darwin")
    def test_default_key_macos(self, mock_system, tmp_path: Path):
        cfg = Config.load(tmp_path)
        assert cfg.trigger_key == "Key.cmd_r"

    @patch("spurt.core.config.platform.system", return_value="Linux")
    def test_default_key_linux(self, mock_system, tmp_path: Path):
        cfg = Config.load(tmp_path)
        assert cfg.trigger_key == "Key.ctrl_r"

    @patch("spurt.core.config.platform.system", return_value="Windows")
    def test_default_key_windows(self, mock_system, tmp_path: Path):
        cfg = Config.load(tmp_path)
        assert cfg.trigger_key == "Key.ctrl_r"


class TestConfigSaveLoad:
    """Tests for save/load round-trip."""

    def test_save_and_load_roundtrip(self, tmp_path: Path):
        cfg = Config(trigger_key="Key.alt_r", key_mode="toggle", model="tiny.en")
        cfg.save(tmp_path)

        loaded = Config.load(tmp_path)
        assert loaded.trigger_key == "Key.alt_r"
        assert loaded.key_mode == "toggle"
        assert loaded.model == "tiny.en"

    def test_save_creates_file(self, tmp_path: Path):
        cfg = Config()
        path = cfg.save(tmp_path)
        assert path.exists()
        assert path.name == CONFIG_FILENAME

    def test_save_creates_directory(self, tmp_path: Path):
        nested = tmp_path / "sub" / "dir"
        cfg = Config()
        cfg.save(nested)
        assert (nested / CONFIG_FILENAME).exists()

    def test_saved_file_is_valid_json(self, tmp_path: Path):
        cfg = Config(trigger_key="Key.ctrl_r", key_mode="hold", model="base.en")
        cfg.save(tmp_path)

        data = json.loads((tmp_path / CONFIG_FILENAME).read_text())
        assert data["trigger_key"] == "Key.ctrl_r"
        assert data["key_mode"] == "hold"
        assert data["model"] == "base.en"


class TestConfigCorruption:
    """Tests for handling corrupt or unexpected config files."""

    def test_load_corrupt_json(self, tmp_path: Path):
        (tmp_path / CONFIG_FILENAME).write_text("not valid json {{{")
        cfg = Config.load(tmp_path)
        # Should fall back to defaults
        assert cfg.key_mode == "hold"
        assert cfg.model == DEFAULT_MODEL

    def test_load_json_array_instead_of_object(self, tmp_path: Path):
        (tmp_path / CONFIG_FILENAME).write_text("[1, 2, 3]")
        cfg = Config.load(tmp_path)
        assert cfg.key_mode == "hold"

    def test_load_empty_file(self, tmp_path: Path):
        (tmp_path / CONFIG_FILENAME).write_text("")
        cfg = Config.load(tmp_path)
        assert cfg.key_mode == "hold"

    def test_load_unknown_keys_ignored(self, tmp_path: Path):
        data = {"model": "tiny", "unknown_key": "value", "foo": 42}
        (tmp_path / CONFIG_FILENAME).write_text(json.dumps(data))
        cfg = Config.load(tmp_path)
        assert cfg.model == "tiny"
        assert not hasattr(cfg, "unknown_key")

    def test_load_missing_keys_get_defaults(self, tmp_path: Path):
        data = {"model": "tiny"}
        (tmp_path / CONFIG_FILENAME).write_text(json.dumps(data))
        cfg = Config.load(tmp_path)
        assert cfg.model == "tiny"
        assert cfg.key_mode == "hold"  # default


class TestConfigReset:
    """Tests for config reset."""

    def test_reset_writes_defaults(self, tmp_path: Path):
        # First save non-default values
        cfg = Config(trigger_key="Key.alt_r", key_mode="toggle", model="large-v3")
        cfg.save(tmp_path)

        # Reset
        reset_cfg = Config.reset(tmp_path)
        assert reset_cfg.key_mode == "hold"
        assert reset_cfg.model == DEFAULT_MODEL

        # Verify file on disk is also reset
        loaded = Config.load(tmp_path)
        assert loaded.key_mode == "hold"
        assert loaded.model == DEFAULT_MODEL

    def test_reset_returns_config_instance(self, tmp_path: Path):
        result = Config.reset(tmp_path)
        assert isinstance(result, Config)


class TestConfigPath:
    """Tests for config_path()."""

    def test_config_path_with_override(self, tmp_path: Path):
        path = Config.config_path(tmp_path)
        assert path == tmp_path / CONFIG_FILENAME

    def test_config_path_returns_path_object(self, tmp_path: Path):
        path = Config.config_path(tmp_path)
        assert isinstance(path, Path)
