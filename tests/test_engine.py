"""Tests for spurt.core.engine — orchestrator."""

from unittest.mock import MagicMock, patch, PropertyMock

import numpy as np
import pytest

from spurt.core.config import Config
from spurt.core.engine import Engine


@pytest.fixture
def config():
    return Config(trigger_key="Key.ctrl_r", key_mode="hold", model="base.en")


@pytest.fixture
def engine_with_mocks(config):
    """Create an Engine with all components mocked."""
    with patch("spurt.core.engine.Transcriber") as MockTranscriber, patch(
        "spurt.core.engine.Recorder"
    ) as MockRecorder, patch("spurt.core.engine.TextOutput") as MockOutput, patch(
        "spurt.core.engine.HotkeyListener"
    ) as MockListener, patch(
        "spurt.core.engine.deserialize_key"
    ) as mock_deser, patch(
        "spurt.core.engine.get_key_mode"
    ) as mock_get_mode:

        mock_deser.return_value = MagicMock()
        mock_get_mode.return_value = MagicMock()

        engine = Engine(config)

        yield {
            "engine": engine,
            "transcriber": MockTranscriber.return_value,
            "recorder": MockRecorder.return_value,
            "output": MockOutput.return_value,
            "listener": MockListener.return_value,
        }


class TestEngineInit:
    """Tests for Engine initialization."""

    def test_rejects_non_config(self):
        with pytest.raises(TypeError, match="Expected Config"):
            Engine("not a config")


class TestEngineActivate:
    """Tests for _on_activate()."""

    def test_activate_starts_recorder(self, engine_with_mocks):
        mocks = engine_with_mocks
        mocks["engine"]._on_activate()
        mocks["recorder"].start.assert_called_once()


class TestEngineDeactivate:
    """Tests for _on_deactivate()."""

    def test_full_flow(self, engine_with_mocks):
        """Deactivate: stop recorder → transcribe → type text."""
        mocks = engine_with_mocks
        mocks["recorder"].stop.return_value = np.ones(16000, dtype=np.float32)
        mocks["transcriber"].transcribe.return_value = "hello world"

        mocks["engine"]._on_deactivate()

        mocks["recorder"].stop.assert_called_once()
        mocks["transcriber"].transcribe.assert_called_once()
        mocks["output"].type_text.assert_called_once_with("hello world")

    def test_empty_audio_skips_transcribe(self, engine_with_mocks):
        """If recorder returns empty audio, don't call transcriber."""
        mocks = engine_with_mocks
        mocks["recorder"].stop.return_value = np.array([], dtype=np.float32)

        mocks["engine"]._on_deactivate()

        mocks["recorder"].stop.assert_called_once()
        mocks["transcriber"].transcribe.assert_not_called()
        mocks["output"].type_text.assert_not_called()

    def test_empty_text_skips_output(self, engine_with_mocks):
        """If transcriber returns empty text, don't call output."""
        mocks = engine_with_mocks
        mocks["recorder"].stop.return_value = np.ones(16000, dtype=np.float32)
        mocks["transcriber"].transcribe.return_value = ""

        mocks["engine"]._on_deactivate()

        mocks["recorder"].stop.assert_called_once()
        mocks["transcriber"].transcribe.assert_called_once()
        mocks["output"].type_text.assert_not_called()


class TestEngineShutdown:
    """Tests for shutdown()."""

    def test_shutdown_sets_event(self, engine_with_mocks):
        mocks = engine_with_mocks
        engine = mocks["engine"]

        assert not engine._shutdown_event.is_set()
        engine.shutdown()
        assert engine._shutdown_event.is_set()
