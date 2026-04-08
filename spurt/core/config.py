"""Configuration management for Spurt."""

import json
import platform
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

from spurt.core.models import DEFAULT_MODEL

CONFIG_FILENAME = "config.json"


def _default_trigger_key() -> str:
    """Platform-aware default trigger key."""
    if platform.system() == "Darwin":
        return "Key.cmd_r"
    return "Key.ctrl_r"


def _get_config_dir() -> Path:
    """Get the platform user config directory for spurt.

    - Windows: %APPDATA%/spurt/
    - macOS: ~/Library/Application Support/spurt/
    - Linux: ~/.config/spurt/ (XDG convention)
    """
    system = platform.system()

    if system == "Windows":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif system == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        # Linux and other Unix — follow XDG
        xdg = os.environ.get("XDG_CONFIG_HOME")
        base = Path(xdg) if xdg else Path.home() / ".config"

    config_dir = base / "spurt"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


# Need os for environment variable access in _get_config_dir
import os


@dataclass
class Config:
    """Typed configuration with platform-aware defaults."""

    trigger_key: str = field(default_factory=_default_trigger_key)
    key_mode: str = "hold"
    model: str = DEFAULT_MODEL
    max_recording_time: float = 100.0

    @classmethod
    def load(cls, config_dir: Path | None = None) -> "Config":
        """Load config from disk. Returns defaults if file is missing or corrupt.

        Args:
            config_dir: Override config directory (used by tests).
                        If None, uses the platform user config directory.
        """
        path = (config_dir or _get_config_dir()) / CONFIG_FILENAME
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return cls()
            known_fields = {f.name for f in cls.__dataclass_fields__.values()}
            filtered = {k: v for k, v in data.items() if k in known_fields}
            return cls(**filtered)
        except (json.JSONDecodeError, TypeError, ValueError):
            return cls()

    def save(self, config_dir: Path | None = None) -> Path:
        """Write config to disk. Creates the directory if needed.

        Args:
            config_dir: Override config directory (used by tests).

        Returns:
            The path to the written config file.
        """
        directory = config_dir or _get_config_dir()
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / CONFIG_FILENAME
        path.write_text(
            json.dumps(asdict(self), indent=2) + "\n",
            encoding="utf-8",
        )
        return path

    @classmethod
    def reset(cls, config_dir: Path | None = None) -> "Config":
        """Reset config to defaults and save to disk.

        Returns:
            The new default Config instance.
        """
        cfg = cls()
        cfg.save(config_dir)
        return cfg

    @classmethod
    def config_path(cls, config_dir: Path | None = None) -> Path:
        """Return the resolved path to the config file."""
        return (config_dir or _get_config_dir()) / CONFIG_FILENAME
