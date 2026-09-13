"""Spurt Textual TUI application.

Thin frontend over spurt.core: owns a single Engine and reflects its state.
No dictation logic lives here — the same core functions the CLI uses are reused.
"""

from __future__ import annotations

import contextlib
import os

from textual.app import App

from spurt import __version__
from spurt.core.config import Config
from spurt.tui.screens.dashboard import DashboardScreen


class SpurtApp(App):
    """Status/control panel for the push-to-talk dictation engine.

    The engine types into whatever window is focused, so this panel is not the
    dictation target — focus the app you want to dictate into. Here you see live
    state, pause/resume listening (model stays warm), and change config.
    """

    TITLE = "Spurt"
    SUB_TITLE = f"push-to-talk dictation · v{__version__}"

    CSS = """
    Screen {
        align: center top;
    }

    #main_title {
        text-style: bold;
        color: $primary;
        border: round $primary;
        padding: 1;
        background: $secondary 20%;
        text-align: center;
    }

    #panel {
        width: 100%;
        height: 1fr;
        padding: 1 2;
        border: round $secondary;
    }

    #status {
        width: 100%;
        height: 3;
        content-align: center middle;
        text-style: bold;
        border: round $panel-lighten-2;
        margin-bottom: 1;
    }
    #status.idle        { background: $success 20%; color: $success; }
    #status.recording   { background: $error 30%;   color: $error; }
    #status.transcribing{ background: $warning 30%; color: $warning; }
    #status.typing      { background: $accent 30%;  color: $accent; }
    #status.paused      { background: $panel;        color: $text-muted; }
    #status.loading     { background: $primary 20%; color: $primary; }

    #progress {
        width: 100%;
        margin-bottom: 1;
    }
    .hidden { display: none; }

    #summary {
        width: 100%;
        padding: 0 1;
        color: $text-muted;
        margin-bottom: 1;
        border: round $secondary
    }

    #log {
        width: 100%;
        height: 1fr;
        border: round $panel-lighten-2;
        padding: 0 1;
    }

    #hint {
        width: 100%;
        color: $text-muted;
        text-style: italic;
        margin-top: 1;
    }

    ConfigScreen {
        align: center middle;
    }
    ConfigScreen #config-body {
        # width: 100%;
        # height: 100%;
        border: round $primary;
        padding: 0 2;
        # background: $surface;
    }
    ConfigScreen DataTable {
        height: auto;
        max-height: 12;
        margin-bottom: 1;
    }
    ConfigScreen .section-title {
        text-style: bold;
        color: $primary;
        margin: 1 0;
        border-bottom: solid $secondary;
    }
    ConfigScreen Horizontal {
        height: auto;
        margin: 1 0;
    }
    ConfigScreen #maxtime {
        width: 50%;
    }
    ConfigScreen #set-max {
        width: auto;
    }
    ConfigScreen #capture {
        width: auto;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        # Loaded once; the config screen mutates and re-saves this instance.
        self.cfg: Config = Config.load()

    def on_mount(self) -> None:
        self.push_screen(DashboardScreen())


@contextlib.contextmanager
def _silence_stderr():
    """Redirect the process's stderr file descriptor to null.

    whisper.cpp and PortAudio log directly to the C-level stderr fd (model
    loading, transcribe progress, audio-backend warnings). Those writes corrupt
    the Textual screen. Textual draws via stdout / the console handle, so
    silencing fd 2 keeps the UI clean. The fd is restored on exit, so a real
    crash still prints its traceback.
    """
    try:
        stderr_fd = 2
        saved = os.dup(stderr_fd)
    except OSError:
        # No real stderr (e.g. detached process) — nothing to silence.
        yield
        return
    devnull = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(devnull, stderr_fd)
        yield
    finally:
        os.dup2(saved, stderr_fd)
        os.close(devnull)
        os.close(saved)


def run_tui() -> None:
    """Entry point used by the CLI when invoked with no subcommand."""
    with _silence_stderr():
        SpurtApp().run()
