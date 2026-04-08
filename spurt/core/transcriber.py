"""Whisper transcription wrapper."""

import tempfile
import wave
from pathlib import Path

import numpy as np

from spurt.core.config import Config
from spurt.core.models import resolve_model


class Transcriber:
    """Loads a Whisper model lazily and transcribes audio buffers to text.

    The model is not loaded until the first call to transcribe(). This keeps
    config commands and startup fast — the multi-GB model only loads when
    the user actually dictates.
    """

    def __init__(self, config: Config) -> None:
        if not isinstance(config, Config):
            raise TypeError(f"Expected Config instance, got {type(config).__name__}")
        self._config = config
        self._model = None  # Lazy-loaded on first transcribe()

    def ensure_model(self) -> None:
        """Load the whisper model if not already loaded. Downloads on first use."""
        if self._model is not None:
            return
        from pywhispercpp.model import Model

        model_info = resolve_model(self._config.model)
        self._model = Model(model_info.name, n_threads=4)

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        """Transcribe a numpy float32 audio array to text.

        Args:
            audio: 1-D float32 numpy array, mono, 16kHz.
            sample_rate: Sample rate in Hz (must be 16000 for Whisper).

        Returns:
            Transcribed text string, stripped and joined.

        Raises:
            ValueError: If audio array is not 1-D or is empty.
            TypeError: If audio is not float32.
        """
        if not isinstance(audio, np.ndarray):
            raise TypeError(f"Expected numpy array, got {type(audio).__name__}")
        if audio.ndim != 1:
            raise ValueError(f"Expected 1-D audio array, got {audio.ndim}-D")
        if audio.dtype != np.float32:
            raise TypeError(f"Expected float32 audio, got {audio.dtype}")
        if audio.size == 0:
            return ""

        self.ensure_model()

        # Convert float32 [-1.0, 1.0] → int16 PCM for WAV writing
        audio_clipped = np.clip(audio, -1.0, 1.0)
        audio_int16 = (audio_clipped * 32767).astype(np.int16)

        # Write to temp WAV file (pywhispercpp needs a file path)
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp_path = f.name
                with wave.open(f, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)  # 16-bit
                    wf.setframerate(sample_rate)
                    wf.writeframes(audio_int16.tobytes())

            segments = self._model.transcribe(tmp_path)
            text = " ".join(seg.text.strip() for seg in segments if seg.text.strip())
            return text.strip()
        finally:
            if tmp_path is not None:
                Path(tmp_path).unlink(missing_ok=True)

    def unload(self) -> None:
        """Release the model from memory."""
        self._model = None

    @property
    def is_loaded(self) -> bool:
        """Whether the model is currently loaded in memory."""
        return self._model is not None
