"""Config screen — change model, key mode, trigger key, max time; reset.

Reuses the same core registries and Config the CLI uses — no logic duplication.
Saves each change immediately (like the CLI's per-flag behavior) and reports back
to the dashboard whether anything changed so it can restart the engine.
"""

from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import Button, DataTable, Input, Static

from spurt.core.config import Config
from spurt.core.hotkey import KEY_MODES, serialize_key
from spurt.core.models import MODELS, delete_model, is_model_downloaded


class ConfigScreen(Screen):
    """Modal-style config editor. Dismisses with True if anything changed."""

    BINDINGS = [("escape", "back", "Back")]

    def __init__(self, dashboard) -> None:
        super().__init__()
        self._dashboard = dashboard  # to pause/resume during key capture
        self._changed = False
        self._highlighted_model: str | None = None  # model row under the cursor

    def compose(self) -> ComposeResult:
        with Container(id="config-body"):
            yield Static("Configuration", classes="section-title")
            yield Static("Model (click a row to select):", classes="section-title")
            yield DataTable(id="models", cursor_type="row", zebra_stripes=True)
            with Horizontal():
                yield Button("Delete highlighted model", id="delete-model", variant="error")
            yield Static("Key mode (click a row to select):", classes="section-title")
            yield DataTable(id="modes", cursor_type="row", zebra_stripes=True)
            with Horizontal():
                yield Input(id="maxtime", placeholder="max recording seconds")
                yield Button("Save", id="set-max", variant="primary")
            with Horizontal():
                yield Button("Capture trigger key", id="capture")
                yield Button("Reset defaults", id="reset", variant="warning")
                yield Button("Back", id="back", variant="success")
            yield Static("", id="config-status")

    def on_mount(self) -> None:
        models = self.query_one("#models", DataTable)
        models.add_columns("ID", " ", "Model", "Size", "Downloaded", "Description")
        modes = self.query_one("#modes", DataTable)
        modes.add_columns("ID", " ", "Mode", "Description")
        self.query_one("#maxtime", Input).value = str(self.app.cfg.max_recording_time)
        self._populate()

    def _populate(self) -> None:
        cfg = self.app.cfg
        models = self.query_one("#models", DataTable)
        models.clear()
        for m in MODELS:
            marker = "*" if m.name == cfg.model else ""
            downloaded = "yes" if is_model_downloaded(m.name) else "no"
            models.add_row(
                str(m.id), marker, m.name, m.size, downloaded, m.description,
                key=m.name,
            )
        modes = self.query_one("#modes", DataTable)
        modes.clear()
        for km in KEY_MODES:
            marker = "*" if km.name == cfg.key_mode else ""
            modes.add_row(str(km.id), marker, km.name, km.description, key=km.name)

    def _status(self, text: str) -> None:
        self.query_one("#config-status", Static).update(text)

    def _mark_changed(self) -> None:
        self._changed = True

    # -- Row selection --
    def on_data_table_row_highlighted(
        self, event: DataTable.RowHighlighted
    ) -> None:
        if event.data_table.id == "models" and event.row_key is not None:
            self._highlighted_model = event.row_key.value

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        name = event.row_key.value
        cfg = self.app.cfg
        if event.data_table.id == "models":
            cfg.model = name
            cfg.save()
            self._mark_changed()
            self._status(f"Model set to {name}.")
        elif event.data_table.id == "modes":
            cfg.key_mode = name
            cfg.save()
            self._mark_changed()
            self._status(f"Key mode set to {name}.")
        self._populate()

    # -- Buttons --
    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "set-max":
            self._set_max_time()
        elif bid == "delete-model":
            self._delete_model()
        elif bid == "capture":
            self._capture_key()
        elif bid == "reset":
            self.app.cfg = Config.reset()
            self.query_one("#maxtime", Input).value = str(
                self.app.cfg.max_recording_time
            )
            self._mark_changed()
            self._status("Configuration reset to defaults.")
            self._populate()
        elif bid == "back":
            self.action_back()

    def _set_max_time(self) -> None:
        raw = self.query_one("#maxtime", Input).value.strip()
        try:
            value = float(raw)
        except ValueError:
            self._status("Max time must be a number.")
            return
        if value <= 0:
            self._status("Max time must be positive.")
            return
        self.app.cfg.max_recording_time = value
        self.app.cfg.save()
        self._mark_changed()
        self._status(f"Max recording time set to {value}s.")

    def _delete_model(self) -> None:
        name = self._highlighted_model
        if name is None:
            self._status("Highlight a model row first.")
            return
        if name == self.app.cfg.model:
            self._status(f"Can't delete {name} — it's the model in use.")
            return
        if not is_model_downloaded(name):
            self._status(f"{name} isn't downloaded.")
            return
        delete_model(name)
        self._status(f"Deleted {name}.")
        self._populate()

    # -- Trigger-key capture (worker thread; engine paused meanwhile) --
    @work(thread=True, exclusive=True)
    def _capture_key(self) -> None:
        self.app.call_from_thread(self._status, "Press the key to use as trigger...")

        engine = getattr(self._dashboard, "engine", None)
        was_listening = bool(getattr(self._dashboard, "_listening", False))
        if engine is not None and was_listening:
            engine.pause()
        try:
            from pynput import keyboard as kb

            captured = {}

            def on_press(k):
                captured["key"] = k
                return False  # stop listener

            with kb.Listener(on_press=on_press) as listener:
                listener.join()
        finally:
            if engine is not None and was_listening:
                engine.resume()

        key = captured.get("key")
        if key is None:
            self.app.call_from_thread(self._status, "No key detected.")
            return
        key_str = serialize_key(key)
        self.app.cfg.trigger_key = key_str
        self.app.cfg.save()
        self.app.call_from_thread(self._mark_changed)
        self.app.call_from_thread(self._status, f"Trigger key set to {key_str}.")

    def action_back(self) -> None:
        self.dismiss(self._changed)
