"""Tests for spurt.core.output — text typing simulation."""

from unittest.mock import MagicMock, patch

import pytest

from spurt.core.output import TextOutput


@pytest.fixture
def mock_controller():
    """Patch pynput.keyboard.Controller."""
    with patch("spurt.core.output.Controller") as MockCtrl:
        instance = MagicMock()
        MockCtrl.return_value = instance
        yield instance


class TestTextOutput:
    """Tests for TextOutput typing behavior."""

    def test_type_text(self, mock_controller):
        output = TextOutput(inter_key_delay=0)
        output.type_text("hi")

        assert mock_controller.type.call_count == 2
        mock_controller.type.assert_any_call("h")
        mock_controller.type.assert_any_call("i")

    def test_empty_text_ignored(self, mock_controller):
        output = TextOutput(inter_key_delay=0)
        output.type_text("")

        mock_controller.type.assert_not_called()

    def test_prepend_space_on_second_call(self, mock_controller):
        output = TextOutput(inter_key_delay=0)
        output.type_text("a")
        output.type_text("b")

        # Second call should type " b" (space + b)
        calls = [c[0][0] for c in mock_controller.type.call_args_list]
        assert calls == ["a", " ", "b"]

    def test_no_space_on_first_call(self, mock_controller):
        output = TextOutput(inter_key_delay=0)
        output.type_text("a")

        calls = [c[0][0] for c in mock_controller.type.call_args_list]
        assert calls == ["a"]

    def test_reset_clears_space_tracker(self, mock_controller):
        output = TextOutput(inter_key_delay=0)
        output.type_text("a")
        output.reset()
        output.type_text("b")

        # After reset, no prepended space
        calls = [c[0][0] for c in mock_controller.type.call_args_list]
        assert calls == ["a", "b"]

    def test_prepend_space_disabled(self, mock_controller):
        output = TextOutput(inter_key_delay=0, prepend_space=False)
        output.type_text("a")
        output.type_text("b")

        calls = [c[0][0] for c in mock_controller.type.call_args_list]
        assert calls == ["a", "b"]

    def test_non_string_raises_type_error(self, mock_controller):
        output = TextOutput(inter_key_delay=0)
        with pytest.raises(TypeError, match="Expected string"):
            output.type_text(123)

    def test_negative_delay_raises(self):
        with pytest.raises(ValueError, match="inter_key_delay"):
            TextOutput(inter_key_delay=-1)
