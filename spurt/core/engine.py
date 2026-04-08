"""Main dictation engine — orchestrates all core components."""

import signal
import threading

from spurt.core.config import Config
from spurt.core.transcriber import Transcriber
from spurt.core.recorder import Recorder
from spurt.core.hotkey import HotkeyListener, deserialize_key, get_key_mode
from spurt.core.output import TextOutput


class Engine:
    """Push-to-talk dictation engine.

    Wires together the transcriber, recorder, hotkey listener, and text output.
    The flow is callback-driven:

        User presses trigger key
          → HotkeyListener → KeyMode.on_key_press()
          → _on_activate() → Recorder.start() + start max_time timer
          ... user speaks ...
        User releases trigger key (OR max_time timer fires)
          → HotkeyListener → KeyMode.on_key_release() (OR timer)
          → _on_deactivate() → cancel timer, Recorder.stop() → numpy audio
          → Transcriber.transcribe(audio) → text
          → TextOutput.type_text(text) → keystrokes in active window

    Usage:
        engine = Engine(config)
        engine.run()  # blocks until Ctrl+C or SIGTERM
    """

    def __init__(self, config: Config) -> None:
        if not isinstance(config, Config):
            raise TypeError(f"Expected Config instance, got {type(config).__name__}")

        self._config = config
        self._transcriber = Transcriber(config)
        self._recorder = Recorder()
        self._output = TextOutput()
        self._shutdown_event = threading.Event()
        self._max_time_timer: threading.Timer | None = None

        # Build key mode + listener
        trigger = deserialize_key(config.trigger_key)
        mode = get_key_mode(
            mode_name=config.key_mode,
            trigger_key=trigger,
            on_activate=self._on_activate,
            on_deactivate=self._on_deactivate,
        )
        self._listener = HotkeyListener(mode)

    def _on_activate(self) -> None:
        """Called when the user triggers 'start dictating'."""
        self._recorder.start()

        # Start max recording time timer
        if self._config.max_recording_time > 0:
            self._max_time_timer = threading.Timer(
                self._config.max_recording_time,
                self._on_deactivate,
            )
            self._max_time_timer.daemon = True
            self._max_time_timer.start()

    def _on_deactivate(self) -> None:
        """Called when the user triggers 'stop dictating'.

        Also called by the max_time timer if the user holds too long.
        Cancels the timer (if still running), stops recording,
        transcribes, and types the result.
        """
        # Cancel the max time timer if it's still running
        if self._max_time_timer is not None:
            self._max_time_timer.cancel()
            self._max_time_timer = None

        audio = self._recorder.stop()
        if audio.size == 0:
            return
        text = self._transcriber.transcribe(audio)
        if text:
            self._output.type_text(text)

    def run(self) -> None:
        """Start the engine. Blocks until Ctrl+C or SIGTERM."""
        # Pre-load the whisper model before starting the listener.
        # Downloads on first use, loads into memory. This ensures the
        # first dictation is instant — no delay waiting for the model.
        self._transcriber.ensure_model()

        print("Model loaded. Press Ctrl+C to stop.")

        # Set up signal handlers for clean shutdown
        def _handle_signal(signum, frame):
            self._shutdown_event.set()

        signal.signal(signal.SIGTERM, _handle_signal)
        signal.signal(signal.SIGINT, _handle_signal)

        try:
            self._listener.start()
            # Block until shutdown signal — use timeout loop so Ctrl+C
            # works on Windows (Event.wait() without timeout swallows SIGINT)
            while not self._shutdown_event.is_set():
                self._shutdown_event.wait(timeout=0.5)
        finally:
            self._listener.stop()
            # Cancel any pending max time timer
            if self._max_time_timer is not None:
                self._max_time_timer.cancel()
                self._max_time_timer = None
            self._transcriber.unload()

    def shutdown(self) -> None:
        """Programmatic shutdown (e.g., from tests)."""
        self._shutdown_event.set()
