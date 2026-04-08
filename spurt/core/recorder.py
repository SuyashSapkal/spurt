"""Microphone audio capture."""

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "float32"


class Recorder:
    """Records audio from the default microphone.

    Uses sounddevice.InputStream with a callback to capture audio chunks.
    Audio is returned as a 1-D float32 numpy array at 16kHz mono.
    """

    def __init__(self, sample_rate: int = SAMPLE_RATE) -> None:
        if not isinstance(sample_rate, int) or sample_rate <= 0:
            raise ValueError(
                f"Sample rate must be a positive integer, got {sample_rate}"
            )
        self._sample_rate = sample_rate
        self._stream: sd.InputStream | None = None
        self._chunks: list[np.ndarray] = []

    def _callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info,
        status: sd.CallbackFlags,
    ) -> None:
        """Called by sounddevice for each audio block.

        Copies the data to avoid buffer reuse issues — sounddevice reuses
        the indata buffer between callbacks.
        """
        self._chunks.append(indata.copy())

    def start(self) -> None:
        """Start recording from the default microphone.

        Idempotent — calling start() while already recording is a no-op.
        """
        if self._stream is not None:
            return
        self._chunks = []
        self._stream = sd.InputStream(
            samplerate=self._sample_rate,
            channels=CHANNELS,
            dtype=DTYPE,
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> np.ndarray:
        """Stop recording and return captured audio.

        Returns:
            1-D float32 numpy array of captured audio at 16kHz.
            Returns an empty array if not recording or no audio was captured.
        """
        if self._stream is None:
            return np.array([], dtype=np.float32)

        self._stream.stop()
        self._stream.close()
        self._stream = None

        if not self._chunks:
            return np.array([], dtype=np.float32)

        audio = np.concatenate(self._chunks, axis=0)
        self._chunks = []
        return audio.flatten()

    @property
    def is_recording(self) -> bool:
        """Whether the recorder is currently capturing audio."""
        return self._stream is not None

    @property
    def sample_rate(self) -> int:
        """The sample rate in Hz."""
        return self._sample_rate

    def __del__(self) -> None:
        """Clean up the stream if the recorder is garbage collected."""
        if getattr(self, "_stream", None) is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
