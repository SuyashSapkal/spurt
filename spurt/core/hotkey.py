"""Global hotkey detection with extensible key modes."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable

from pynput import keyboard

# ──── Key Mode Registry ────


@dataclass(frozen=True)
class KeyModeInfo:
    """Metadata for a key interaction mode."""

    id: int
    name: str
    description: str
    cls: type  # The KeyMode subclass


# ──── Key Serialization ────


def serialize_key(key: keyboard.Key | keyboard.KeyCode) -> str:
    """Convert a pynput key to a storable string.

    Args:
        key: A pynput Key enum or KeyCode instance.

    Returns:
        A string representation that can be stored in config and deserialized.
    """
    if isinstance(key, keyboard.Key):
        return f"Key.{key.name}"
    elif isinstance(key, keyboard.KeyCode):
        if key.vk is not None:
            return f"KeyCode.vk.{key.vk}"
        if key.char is not None:
            return f"KeyCode.char.{key.char}"
    return str(key)


def deserialize_key(s: str) -> keyboard.Key | keyboard.KeyCode:
    """Convert a stored string back to a pynput key.

    Args:
        s: A string previously produced by serialize_key().

    Returns:
        The corresponding pynput Key or KeyCode.

    Raises:
        ValueError: If the string cannot be deserialized.
    """
    if not isinstance(s, str):
        raise TypeError(f"Expected string, got {type(s).__name__}")

    if s.startswith("Key."):
        name = s[4:]
        try:
            return keyboard.Key[name]
        except KeyError:
            raise ValueError(f"Unknown key name: {name!r}")
    elif s.startswith("KeyCode.vk."):
        try:
            vk = int(s[11:])
            return keyboard.KeyCode.from_vk(vk)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid virtual key code in: {s!r}")
    elif s.startswith("KeyCode.char."):
        char = s[13:]
        if len(char) != 1:
            raise ValueError(f"Expected single character, got {char!r}")
        return keyboard.KeyCode.from_char(char)

    raise ValueError(f"Cannot deserialize key: {s!r}")


# ──── Key Mode Strategy ────


class KeyMode(ABC):
    """Abstract base for key interaction modes.

    Subclasses implement on_key_press/on_key_release to define how the
    trigger key activates and deactivates dictation.
    """

    def __init__(
        self,
        trigger_key: keyboard.Key | keyboard.KeyCode,
        on_activate: Callable[[], None],
        on_deactivate: Callable[[], None],
    ) -> None:
        self._trigger_key = trigger_key
        self._on_activate = on_activate
        self._on_deactivate = on_deactivate

    @abstractmethod
    def on_key_press(self, key) -> None:
        """Handle a key press event."""
        ...

    @abstractmethod
    def on_key_release(self, key) -> None:
        """Handle a key release event."""
        ...

    def _matches(self, key) -> bool:
        """Check if the pressed key matches the trigger key."""
        return key == self._trigger_key


class HoldMode(KeyMode):
    """Press-and-hold: record while the trigger key is held down.

    Guards against OS key-repeat — multiple press events while held
    only trigger one activation.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._is_held = False

    def on_key_press(self, key) -> None:
        if self._matches(key) and not self._is_held:
            self._is_held = True
            self._on_activate()

    def on_key_release(self, key) -> None:
        if self._matches(key) and self._is_held:
            self._is_held = False
            self._on_deactivate()


class ToggleMode(KeyMode):
    """Toggle: press once to start recording, press again to stop.

    Release events are ignored.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._is_active = False

    def on_key_press(self, key) -> None:
        if self._matches(key):
            if self._is_active:
                self._is_active = False
                self._on_deactivate()
            else:
                self._is_active = True
                self._on_activate()

    def on_key_release(self, key) -> None:
        pass  # Toggle mode ignores release events


# ──── Registry ────

# Defined after classes so we can reference them
KEY_MODES: list[KeyModeInfo] = [
    KeyModeInfo(
        1, "hold", "Press and hold to dictate, release to stop (default)", HoldMode
    ),
    KeyModeInfo(2, "toggle", "Press once to start, press again to stop", ToggleMode),
]

KEY_MODES_BY_ID: dict[int, KeyModeInfo] = {m.id: m for m in KEY_MODES}
KEY_MODES_BY_NAME: dict[str, KeyModeInfo] = {m.name: m for m in KEY_MODES}
DEFAULT_KEY_MODE = "hold"


def resolve_key_mode(identifier: str) -> KeyModeInfo:
    """Resolve a key mode by numeric ID ('1') or name ('hold').

    Args:
        identifier: A numeric ID string or mode name.

    Returns:
        The matching KeyModeInfo.

    Raises:
        ValueError: If no mode matches the identifier.
    """
    if not isinstance(identifier, str):
        raise TypeError(f"Expected string identifier, got {type(identifier).__name__}")

    # Try numeric ID first
    try:
        num = int(identifier)
        if num in KEY_MODES_BY_ID:
            return KEY_MODES_BY_ID[num]
    except ValueError:
        pass

    # Try name lookup
    if identifier in KEY_MODES_BY_NAME:
        return KEY_MODES_BY_NAME[identifier]

    raise ValueError(
        f"Unknown key mode: {identifier!r}. "
        f"Use 'spurt-cli config --key-mode-list' to see available modes."
    )


def get_key_mode(
    mode_name: str,
    trigger_key: keyboard.Key | keyboard.KeyCode,
    on_activate: Callable[[], None],
    on_deactivate: Callable[[], None],
) -> KeyMode:
    """Factory: create a KeyMode instance by name.

    Args:
        mode_name: The mode name (e.g., "hold", "toggle").
        trigger_key: The key that triggers dictation.
        on_activate: Called when dictation should start.
        on_deactivate: Called when dictation should stop.

    Returns:
        A KeyMode instance.

    Raises:
        ValueError: If the mode name is unknown.
    """
    info = resolve_key_mode(mode_name)
    return info.cls(
        trigger_key=trigger_key,
        on_activate=on_activate,
        on_deactivate=on_deactivate,
    )


# ──── Listener ────


class HotkeyListener:
    """Owns the pynput keyboard listener, delegates to a KeyMode strategy."""

    def __init__(self, key_mode: KeyMode) -> None:
        if not isinstance(key_mode, KeyMode):
            raise TypeError(f"Expected KeyMode instance, got {type(key_mode).__name__}")
        self._key_mode = key_mode
        self._listener: keyboard.Listener | None = None

    def start(self) -> None:
        """Start listening for keyboard events."""
        if self._listener is not None:
            return
        self._listener = keyboard.Listener(
            on_press=self._key_mode.on_key_press,
            on_release=self._key_mode.on_key_release,
        )
        self._listener.start()

    def stop(self) -> None:
        """Stop listening for keyboard events."""
        if self._listener is not None:
            self._listener.stop()
            self._listener = None

    @property
    def is_running(self) -> bool:
        """Whether the listener is currently active."""
        return self._listener is not None and self._listener.is_alive()
