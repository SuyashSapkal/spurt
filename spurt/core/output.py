"""Type transcribed text into the active window."""

import time

from pynput.keyboard import Controller


class TextOutput:
    """Simulates keyboard typing to output text into the focused window.

    Types character-by-character with a small delay for reliability across
    apps — some Electron-based apps (VS Code, Slack) drop keystrokes when
    they arrive in a burst.
    """

    def __init__(
        self,
        inter_key_delay: float = 0.01,
        prepend_space: bool = True,
    ) -> None:
        if inter_key_delay < 0:
            raise ValueError(f"inter_key_delay must be >= 0, got {inter_key_delay}")
        self._controller = Controller()
        self._inter_key_delay = inter_key_delay
        self._prepend_space = prepend_space
        self._has_typed_before = False

    def type_text(self, text: str) -> None:
        """Type the given text into the currently focused window.

        Args:
            text: The text to type. Empty strings are silently ignored.
        """
        if not isinstance(text, str):
            raise TypeError(f"Expected string, got {type(text).__name__}")
        if not text:
            return

        # Prepend space to separate from previous dictation
        if self._prepend_space and self._has_typed_before:
            text = " " + text

        for char in text:
            self._controller.type(char)
            if self._inter_key_delay > 0:
                time.sleep(self._inter_key_delay)

        self._has_typed_before = True

    def reset(self) -> None:
        """Reset state — next type_text() won't prepend a space."""
        self._has_typed_before = False
