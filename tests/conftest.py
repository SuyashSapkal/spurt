"""Shared test fixtures."""

import pytest
from pathlib import Path

from spurt.core.config import Config


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    """Provide a temporary directory for config files."""
    return tmp_path


@pytest.fixture
def default_config(config_dir: Path) -> Config:
    """A Config instance using a temporary directory."""
    return Config.load(config_dir)
