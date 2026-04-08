"""Tests for spurt.core.hotkey — key detection and modes."""

from unittest.mock import MagicMock, patch

import pytest
from pynput import keyboard

from spurt.core.hotkey import (
    KEY_MODES,
    KEY_MODES_BY_ID,
    KEY_MODES_BY_NAME,
    DEFAULT_KEY_MODE,
    HoldMode,
    HotkeyListener,
    KeyMode,
    KeyModeInfo,
    ToggleMode,
    deserialize_key,
    get_key_mode,
    resolve_key_mode,
    serialize_key,
)

# ──── Key Serialization Tests ────


class TestSerializeKey:
    """Tests for serialize_key()."""

    def test_serialize_key_enum(self):
        assert serialize_key(keyboard.Key.ctrl_r) == "Key.ctrl_r"

    def test_serialize_key_cmd(self):
        assert serialize_key(keyboard.Key.cmd_r) == "Key.cmd_r"

    def test_serialize_keycode_char(self):
        key = keyboard.KeyCode.from_char("a")
        result = serialize_key(key)
        assert result == "KeyCode.char.a"

    def test_serialize_keycode_vk(self):
        key = keyboard.KeyCode.from_vk(162)
        result = serialize_key(key)
        assert result == "KeyCode.vk.162"


class TestDeserializeKey:
    """Tests for deserialize_key()."""

    def test_deserialize_key_enum(self):
        result = deserialize_key("Key.ctrl_r")
        assert result == keyboard.Key.ctrl_r

    def test_deserialize_key_cmd(self):
        result = deserialize_key("Key.cmd_r")
        assert result == keyboard.Key.cmd_r

    def test_deserialize_keycode_char(self):
        result = deserialize_key("KeyCode.char.a")
        assert isinstance(result, keyboard.KeyCode)

    def test_deserialize_keycode_vk(self):
        result = deserialize_key("KeyCode.vk.162")
        assert isinstance(result, keyboard.KeyCode)

    def test_roundtrip_key_enum(self):
        original = keyboard.Key.ctrl_r
        assert deserialize_key(serialize_key(original)) == original

    def test_roundtrip_key_cmd(self):
        original = keyboard.Key.cmd_r
        assert deserialize_key(serialize_key(original)) == original

    def test_deserialize_invalid_string(self):
        with pytest.raises(ValueError, match="Cannot deserialize"):
            deserialize_key("garbage")

    def test_deserialize_unknown_key_name(self):
        with pytest.raises(ValueError, match="Unknown key name"):
            deserialize_key("Key.nonexistent_key")

    def test_deserialize_invalid_vk(self):
        with pytest.raises(ValueError, match="Invalid virtual key"):
            deserialize_key("KeyCode.vk.notanumber")

    def test_deserialize_multi_char(self):
        with pytest.raises(ValueError, match="single character"):
            deserialize_key("KeyCode.char.abc")

    def test_deserialize_non_string(self):
        with pytest.raises(TypeError, match="Expected string"):
            deserialize_key(42)


# ──── Key Mode Registry Tests ────


class TestKeyModeRegistry:
    """Tests for the key mode registry."""

    def test_all_ids_unique(self):
        ids = [m.id for m in KEY_MODES]
        assert len(set(ids)) == len(KEY_MODES)

    def test_all_names_unique(self):
        names = [m.name for m in KEY_MODES]
        assert len(set(names)) == len(KEY_MODES)

    def test_default_mode_exists(self):
        assert DEFAULT_KEY_MODE in KEY_MODES_BY_NAME

    def test_resolve_by_id(self):
        result = resolve_key_mode("1")
        assert result.name == "hold"

    def test_resolve_by_name(self):
        result = resolve_key_mode("hold")
        assert result.id == 1

    def test_resolve_toggle_by_id(self):
        result = resolve_key_mode("2")
        assert result.name == "toggle"

    def test_resolve_invalid(self):
        with pytest.raises(ValueError, match="Unknown key mode"):
            resolve_key_mode("nonexistent")

    def test_resolve_non_string(self):
        with pytest.raises(TypeError, match="Expected string"):
            resolve_key_mode(1)


# ──── HoldMode Tests ────


class TestHoldMode:
    """Tests for HoldMode behavior."""

    def _make_hold_mode(self):
        activate = MagicMock()
        deactivate = MagicMock()
        mode = HoldMode(
            trigger_key=keyboard.Key.ctrl_r,
            on_activate=activate,
            on_deactivate=deactivate,
        )
        return mode, activate, deactivate

    def test_press_activates(self):
        mode, activate, deactivate = self._make_hold_mode()
        mode.on_key_press(keyboard.Key.ctrl_r)
        activate.assert_called_once()
        deactivate.assert_not_called()

    def test_release_deactivates(self):
        mode, activate, deactivate = self._make_hold_mode()
        mode.on_key_press(keyboard.Key.ctrl_r)
        mode.on_key_release(keyboard.Key.ctrl_r)
        deactivate.assert_called_once()

    def test_no_repeat_on_held_key(self):
        """OS key-repeat fires multiple press events — only one activate."""
        mode, activate, deactivate = self._make_hold_mode()
        mode.on_key_press(keyboard.Key.ctrl_r)
        mode.on_key_press(keyboard.Key.ctrl_r)
        mode.on_key_press(keyboard.Key.ctrl_r)
        mode.on_key_press(keyboard.Key.ctrl_r)
        mode.on_key_press(keyboard.Key.ctrl_r)
        activate.assert_called_once()

    def test_wrong_key_ignored(self):
        mode, activate, deactivate = self._make_hold_mode()
        mode.on_key_press(keyboard.Key.alt_r)
        mode.on_key_release(keyboard.Key.alt_r)
        activate.assert_not_called()
        deactivate.assert_not_called()

    def test_release_without_press_ignored(self):
        mode, activate, deactivate = self._make_hold_mode()
        mode.on_key_release(keyboard.Key.ctrl_r)
        deactivate.assert_not_called()

    def test_full_cycle(self):
        """Press → release → press → release = two full cycles."""
        mode, activate, deactivate = self._make_hold_mode()
        mode.on_key_press(keyboard.Key.ctrl_r)
        mode.on_key_release(keyboard.Key.ctrl_r)
        mode.on_key_press(keyboard.Key.ctrl_r)
        mode.on_key_release(keyboard.Key.ctrl_r)
        assert activate.call_count == 2
        assert deactivate.call_count == 2


# ──── ToggleMode Tests ────


class TestToggleMode:
    """Tests for ToggleMode behavior."""

    def _make_toggle_mode(self):
        activate = MagicMock()
        deactivate = MagicMock()
        mode = ToggleMode(
            trigger_key=keyboard.Key.ctrl_r,
            on_activate=activate,
            on_deactivate=deactivate,
        )
        return mode, activate, deactivate

    def test_first_press_activates(self):
        mode, activate, deactivate = self._make_toggle_mode()
        mode.on_key_press(keyboard.Key.ctrl_r)
        activate.assert_called_once()
        deactivate.assert_not_called()

    def test_second_press_deactivates(self):
        mode, activate, deactivate = self._make_toggle_mode()
        mode.on_key_press(keyboard.Key.ctrl_r)
        mode.on_key_press(keyboard.Key.ctrl_r)
        activate.assert_called_once()
        deactivate.assert_called_once()

    def test_release_ignored(self):
        mode, activate, deactivate = self._make_toggle_mode()
        mode.on_key_release(keyboard.Key.ctrl_r)
        activate.assert_not_called()
        deactivate.assert_not_called()

    def test_wrong_key_ignored(self):
        mode, activate, deactivate = self._make_toggle_mode()
        mode.on_key_press(keyboard.Key.alt_r)
        activate.assert_not_called()

    def test_full_toggle_cycle(self):
        mode, activate, deactivate = self._make_toggle_mode()
        mode.on_key_press(keyboard.Key.ctrl_r)  # activate
        mode.on_key_press(keyboard.Key.ctrl_r)  # deactivate
        mode.on_key_press(keyboard.Key.ctrl_r)  # activate again
        assert activate.call_count == 2
        assert deactivate.call_count == 1


# ──── get_key_mode Factory Tests ────


class TestGetKeyMode:
    """Tests for the get_key_mode() factory."""

    def test_get_hold_mode(self):
        mode = get_key_mode("hold", keyboard.Key.ctrl_r, lambda: None, lambda: None)
        assert isinstance(mode, HoldMode)

    def test_get_toggle_mode(self):
        mode = get_key_mode("toggle", keyboard.Key.ctrl_r, lambda: None, lambda: None)
        assert isinstance(mode, ToggleMode)

    def test_get_invalid_mode(self):
        with pytest.raises(ValueError, match="Unknown key mode"):
            get_key_mode("nonexistent", keyboard.Key.ctrl_r, lambda: None, lambda: None)


# ──── HotkeyListener Tests ────


class TestHotkeyListener:
    """Tests for HotkeyListener."""

    def test_rejects_non_key_mode(self):
        with pytest.raises(TypeError, match="Expected KeyMode"):
            HotkeyListener("not a key mode")

    @patch("spurt.core.hotkey.keyboard.Listener")
    def test_start_creates_listener(self, MockListener):
        mode = HoldMode(
            trigger_key=keyboard.Key.ctrl_r,
            on_activate=lambda: None,
            on_deactivate=lambda: None,
        )
        listener = HotkeyListener(mode)
        listener.start()

        MockListener.assert_called_once()
        MockListener.return_value.start.assert_called_once()

    @patch("spurt.core.hotkey.keyboard.Listener")
    def test_start_is_idempotent(self, MockListener):
        mode = HoldMode(
            trigger_key=keyboard.Key.ctrl_r,
            on_activate=lambda: None,
            on_deactivate=lambda: None,
        )
        listener = HotkeyListener(mode)
        listener.start()
        listener.start()  # Second call is a no-op

        MockListener.assert_called_once()

    @patch("spurt.core.hotkey.keyboard.Listener")
    def test_stop(self, MockListener):
        mode = HoldMode(
            trigger_key=keyboard.Key.ctrl_r,
            on_activate=lambda: None,
            on_deactivate=lambda: None,
        )
        listener = HotkeyListener(mode)
        listener.start()
        listener.stop()

        MockListener.return_value.stop.assert_called_once()

    def test_stop_when_not_started(self):
        mode = HoldMode(
            trigger_key=keyboard.Key.ctrl_r,
            on_activate=lambda: None,
            on_deactivate=lambda: None,
        )
        listener = HotkeyListener(mode)
        listener.stop()  # Should not raise
