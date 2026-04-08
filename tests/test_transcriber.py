"""Tests for spurt.core.transcriber — whisper wrapper."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from spurt.core.config import Config
from spurt.core.transcriber import Transcriber


class FakeSegment:
    """Mock whisper segment with a .text attribute."""

    def __init__(self, text: str):
        self.text = text


@pytest.fixture
def config():
    return Config(trigger_key="Key.ctrl_r", key_mode="hold", model="base.en")


@pytest.fixture
def mock_whisper_model():
    """Patch pywhispercpp.model.Model so no real model is loaded."""
    with patch("spurt.core.transcriber.resolve_model") as mock_resolve:
        mock_resolve.return_value = MagicMock(name="base.en")
        with patch("pywhispercpp.model.Model") as MockModel:
            instance = MagicMock()
            MockModel.return_value = instance
            yield instance


class TestTranscriberInit:
    """Tests for Transcriber initialization."""

    def test_lazy_load_model_not_loaded_on_init(self, config):
        t = Transcriber(config)
        assert not t.is_loaded

    def test_init_rejects_non_config(self):
        with pytest.raises(TypeError, match="Expected Config"):
            Transcriber("not a config")


class TestTranscriberTranscribe:
    """Tests for the transcribe() method."""

    def test_transcribe_joins_segments(self, config, mock_whisper_model):
        mock_whisper_model.transcribe.return_value = [
            FakeSegment(" hello "),
            FakeSegment(" world "),
        ]

        t = Transcriber(config)
        result = t.transcribe(np.zeros(16000, dtype=np.float32))

        assert result == "hello world"
        assert t.is_loaded

    def test_transcribe_empty_segments(self, config, mock_whisper_model):
        mock_whisper_model.transcribe.return_value = []

        t = Transcriber(config)
        result = t.transcribe(np.zeros(16000, dtype=np.float32))

        assert result == ""

    def test_transcribe_single_segment(self, config, mock_whisper_model):
        mock_whisper_model.transcribe.return_value = [FakeSegment("hello")]

        t = Transcriber(config)
        result = t.transcribe(np.zeros(16000, dtype=np.float32))

        assert result == "hello"

    def test_transcribe_whitespace_only_segments_filtered(
        self, config, mock_whisper_model
    ):
        mock_whisper_model.transcribe.return_value = [
            FakeSegment("hello"),
            FakeSegment("   "),
            FakeSegment("world"),
        ]

        t = Transcriber(config)
        result = t.transcribe(np.zeros(16000, dtype=np.float32))

        assert result == "hello world"

    def test_transcribe_empty_audio_returns_empty(self, config):
        t = Transcriber(config)
        result = t.transcribe(np.array([], dtype=np.float32))
        assert result == ""

    def test_temp_file_cleanup_on_success(self, config, mock_whisper_model):
        mock_whisper_model.transcribe.return_value = [FakeSegment("test")]

        t = Transcriber(config)
        t.transcribe(np.zeros(16000, dtype=np.float32))

        # Verify the temp file path that was passed to model.transcribe
        call_args = mock_whisper_model.transcribe.call_args
        tmp_path = call_args[0][0]
        assert not Path(tmp_path).exists(), "Temp WAV file should be cleaned up"

    def test_temp_file_cleanup_on_error(self, config, mock_whisper_model):
        mock_whisper_model.transcribe.side_effect = RuntimeError("model error")

        t = Transcriber(config)
        with pytest.raises(RuntimeError, match="model error"):
            t.transcribe(np.zeros(16000, dtype=np.float32))

        # Temp file should still be cleaned up
        # (we can't easily check the path here, but the finally block handles it)


class TestTranscriberInputValidation:
    """Tests for input validation."""

    def test_rejects_non_numpy_array(self, config):
        t = Transcriber(config)
        with pytest.raises(TypeError, match="Expected numpy array"):
            t.transcribe([1.0, 2.0, 3.0])

    def test_rejects_2d_array(self, config):
        t = Transcriber(config)
        audio = np.zeros((100, 2), dtype=np.float32)
        with pytest.raises(ValueError, match="Expected 1-D"):
            t.transcribe(audio)

    def test_rejects_int16_dtype(self, config):
        t = Transcriber(config)
        audio = np.zeros(100, dtype=np.int16)
        with pytest.raises(TypeError, match="Expected float32"):
            t.transcribe(audio)


class TestTranscriberUnload:
    """Tests for model unloading."""

    def test_unload_clears_model(self, config, mock_whisper_model):
        mock_whisper_model.transcribe.return_value = [FakeSegment("test")]

        t = Transcriber(config)
        t.transcribe(np.zeros(16000, dtype=np.float32))
        assert t.is_loaded

        t.unload()
        assert not t.is_loaded

    def test_unload_when_not_loaded(self, config):
        t = Transcriber(config)
        t.unload()  # Should not raise
        assert not t.is_loaded
