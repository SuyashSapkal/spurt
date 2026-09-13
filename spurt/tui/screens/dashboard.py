"""Dashboard screen — live engine status, pause/resume, transcript log."""

from __future__ import annotations

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Container
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Footer, Header, ProgressBar, RichLog, Static

from spurt.core.engine import Engine
from spurt.core.models import download_model, is_model_downloaded

# state -> (label shown in the status bar, CSS class on #status)
_STATE_LABELS = {
    "loading": ("Loading…", "loading"),
    "idle": ("Listening — ready to dictate", "idle"),
    "recording": ("● Recording…", "recording"),
    "transcribing": ("Transcribing…", "transcribing"),
    "typing": ("Typing…", "typing"),
    "paused": ("Paused — press space to resume", "paused"),
}


class DashboardScreen(Screen):
    """Owns the Engine and mirrors its state into widgets.

    Engine callbacks fire on background threads (the pynput listener, the
    max-time timer, or the startup worker). They are marshalled onto the UI
    thread with post_message(), which is thread-safe.
    """

    BINDINGS = [
        ("space", "toggle_listen", "Pause/Resume"),
        ("c", "open_config", "Config"),
        ("q", "quit_app", "Quit"),
    ]

    # ── Thread-safe messages posted from engine callbacks ──
    class StateChanged(Message):
        def __init__(self, state: str) -> None:
            self.state = state
            super().__init__()

    class Progress(Message):
        def __init__(self, done: int, total: int) -> None:
            self.done = done
            self.total = total
            super().__init__()

    class Transcribed(Message):
        def __init__(self, text: str) -> None:
            self.text = text
            super().__init__()

    class Phase(Message):
        """Startup phase: 'download', 'load', or 'ready'."""

        def __init__(self, phase: str) -> None:
            self.phase = phase
            super().__init__()

    def __init__(self) -> None:
        super().__init__()
        self.engine: Engine | None = None
        self._ready = False
        self._listening = False

    # ── Layout ──
    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Dashboard", id="main_title")
        with Container(id="panel"):
            yield Static("Starting…", id="status", classes="loading")
            yield ProgressBar(id="progress", total=None, show_eta=False)
            yield Static(id="summary")
            yield RichLog(id="log", wrap=True, markup=False)
            yield Static(
                "Tip: focus the window you want to dictate into — "
                "text is typed into whatever is focused, not this panel.",
                id="hint",
            )
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#progress").add_class("hidden")
        self._refresh_summary()
        self._start_engine()

    # ── Engine startup / restart (worker thread) ──
    @work(thread=True, exclusive=True, group="engine")
    def _start_engine(self) -> None:
        # Tear down any previous engine first (used by config restart).
        if self.engine is not None:
            try:
                self.engine.stop()
            except Exception:
                pass
            self.engine = None
        self._ready = False
        self._listening = False

        cfg = self.app.cfg
        self.engine = Engine(
            cfg,
            on_state_change=lambda s: self.post_message(self.StateChanged(s)),
            on_transcript=lambda t: self.post_message(self.Transcribed(t)),
        )

        # Phase 1: download (first run only) with a real progress bar.
        if not is_model_downloaded(cfg.model):
            self.post_message(self.Phase("download"))
            try:
                download_model(
                    cfg.model,
                    on_progress=lambda d, t: self.post_message(self.Progress(d, t)),
                )
            except Exception as exc:  # fall back to pywhispercpp's own download
                self.post_message(
                    self.Transcribed(f"[download] {cfg.model} fetch failed: {exc}")
                )

        # Phase 2: load into memory (indeterminate) and start listening.
        self.post_message(self.Phase("load"))
        self.engine.start()  # ensure_model() + resume() -> emits "idle"
        self._ready = True
        self._listening = True
        self.post_message(self.Phase("ready"))

    # ── Message handlers (UI thread) ──
    @on(StateChanged)
    def _handle_state(self, msg: "DashboardScreen.StateChanged") -> None:
        self._apply_state(msg.state)

    @on(Progress)
    def _handle_progress(self, msg: "DashboardScreen.Progress") -> None:
        bar = self.query_one("#progress", ProgressBar)
        if msg.total > 0:
            bar.update(total=msg.total, progress=msg.done)
        else:
            bar.update(total=None)  # indeterminate

    @on(Transcribed)
    def _handle_transcribed(self, msg: "DashboardScreen.Transcribed") -> None:
        self.query_one("#log", RichLog).write(msg.text)

    @on(Phase)
    def _handle_phase(self, msg: "DashboardScreen.Phase") -> None:
        bar = self.query_one("#progress", ProgressBar)
        if msg.phase == "download":
            bar.remove_class("hidden")
            bar.update(total=None, progress=0)
            self._set_status("loading", f"Downloading model: {self.app.cfg.model}…")
        elif msg.phase == "load":
            bar.remove_class("hidden")
            bar.update(total=None)
            self._set_status("loading", "Loading model into memory…")
        elif msg.phase == "ready":
            bar.add_class("hidden")
            # actual state already emitted as "idle" by engine.resume()

    # ── Actions ──
    def action_toggle_listen(self) -> None:
        if not self._ready or self.engine is None:
            return
        if self._listening:
            self.engine.pause()
            self._listening = False
        else:
            self.engine.resume()
            self._listening = True

    def action_open_config(self) -> None:
        from spurt.tui.screens.config_screen import ConfigScreen

        def _after(changed: bool | None) -> None:
            self._refresh_summary()
            if changed:
                self.query_one("#log", RichLog).write(
                    "[config] applied — restarting engine…"
                )
                self._start_engine()

        self.app.push_screen(ConfigScreen(self), _after)

    def action_quit_app(self) -> None:
        if self.engine is not None:
            try:
                self.engine.stop()
            except Exception:
                pass
            self.engine = None
        self.app.exit()

    def on_unmount(self) -> None:
        # Safety net if the app is closed some other way.
        if self.engine is not None:
            try:
                self.engine.stop()
            except Exception:
                pass
            self.engine = None

    # ── Helpers ──
    def _apply_state(self, state: str) -> None:
        label, css = _STATE_LABELS.get(state, (state, "idle"))
        self._set_status(css, label)
        self._listening = state != "paused"

    def _set_status(self, css: str, label: str) -> None:
        status = self.query_one("#status", Static)
        status.update(label)
        for name in ("idle", "recording", "transcribing", "typing", "paused", "loading"):
            status.remove_class(name)
        status.add_class(css)

    def _refresh_summary(self) -> None:
        c = self.app.cfg
        self.query_one("#summary", Static).update(
            f"model: {c.model}    key: {c.trigger_key}    "
            f"mode: {c.key_mode}    max time: {c.max_recording_time}s"
        )
