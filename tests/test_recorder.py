"""Tests for spurt.core.recorder — microphone capture."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from spurt.core.recorder import Recorder, SAMPLE_RATE


@pytest.fixture
def mock_stream():
    """Patch sounddevice.InputStream."""
    with patch("spurt.core.recorder.sd.InputStream") as MockStream:
        instance = MagicMock()
        MockStream.return_value = instance
        yield MockStream, instance


class TestRecorderInit:
    """Tests for Recorder initialization."""

    def test_default_sample_rate(self):
        r = Recorder.__new__(Recorder)
        r._sample_rate = SAMPLE_RATE
        assert r._sample_rate == 16000

    def test_invalid_sample_rate(self):
        with pytest.raises(ValueError, match="positive integer"):
            Recorder(sample_rate=0)

    def test_negative_sample_rate(self):
        with pytest.raises(ValueError, match="positive integer"):
            Recorder(sample_rate=-1)


class TestRecorderStartStop:
    """Tests for start/stop lifecycle."""

    def test_start_creates_stream(self, mock_stream):
        MockStream, instance = mock_stream
        r = Recorder()
        r.start()

        MockStream.assert_called_once()
        instance.start.assert_called_once()
        assert r.is_recording

    def test_start_is_idempotent(self, mock_stream):
        MockStream, instance = mock_stream
        r = Recorder()
        r.start()
        r.start()  # Second call should be a no-op

        MockStream.assert_called_once()
        instance.start.assert_called_once()

    def test_stop_returns_audio(self, mock_stream):
        MockStream, instance = mock_stream
        r = Recorder()
        r.start()

        # Simulate audio chunks arriving via callback
        chunk1 = np.array([[0.1], [0.2], [0.3]], dtype=np.float32)
        chunk2 = np.array([[0.4], [0.5]], dtype=np.float32)
        r._callback(chunk1, 3, None, None)
        r._callback(chunk2, 2, None, None)

        audio = r.stop()

        assert isinstance(audio, np.ndarray)
        assert audio.dtype == np.float32
        assert audio.ndim == 1
        assert len(audio) == 5
        np.testing.assert_array_almost_equal(audio, [0.1, 0.2, 0.3, 0.4, 0.5])
        assert not r.is_recording

    def test_stop_when_not_recording(self):
        r = Recorder.__new__(Recorder)
        r._sample_rate = SAMPLE_RATE
        r._stream = None
        r._chunks = []

        audio = r.stop()

        assert isinstance(audio, np.ndarray)
        assert audio.dtype == np.float32
        assert audio.size == 0

    def test_stop_with_no_chunks(self, mock_stream):
        MockStream, instance = mock_stream
        r = Recorder()
        r.start()

        audio = r.stop()

        assert audio.size == 0
        assert not r.is_recording

    def test_is_recording_false_initially(self):
        r = Recorder.__new__(Recorder)
        r._stream = None
        r._chunks = []
        assert not r.is_recording


class TestRecorderCallback:
    """Tests for the audio callback."""

    def test_callback_copies_data(self, mock_stream):
        MockStream, instance = mock_stream
        r = Recorder()
        r.start()

        # Simulate sounddevice reusing the same buffer
        buffer = np.array([[1.0], [2.0]], dtype=np.float32)
        r._callback(buffer, 2, None, None)

        # Modify the original buffer (simulating sounddevice reuse)
        buffer[:] = 0.0

        # Our stored chunk should still have the original values
        assert r._chunks[0][0, 0] == 1.0
        assert r._chunks[0][1, 0] == 2.0
