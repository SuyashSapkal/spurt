"""Spurt CLI — thin wrapper around core engine.

Uses Python's built-in argparse module. No business logic here — just
argument parsing, output formatting, and calling into spurt.core.
"""

import argparse
import sys

from spurt import __version__
from spurt.core.config import Config
from spurt.core.models import MODELS, resolve_model, is_model_downloaded, delete_model
from spurt.core.hotkey import (
    KEY_MODES,
    resolve_key_mode,
    serialize_key,
)
from spurt.core.engine import Engine


def build_parser() -> argparse.ArgumentParser:
    """Construct the CLI argument parser with all subcommands and options."""
    parser = argparse.ArgumentParser(
        prog="spurt-cli",
        description="Spurt — push-to-talk dictation powered by whisper.cpp.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"spurt {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ─── run ───
    subparsers.add_parser("run", help="Start the dictation engine.")

    # ─── config ───
    config_parser = subparsers.add_parser(
        "config",
        help="View or modify configuration.",
    )
    config_parser.add_argument(
        "--key",
        action="store_true",
        help="Interactively set the trigger key.",
    )
    config_parser.add_argument(
        "--key-mode",
        type=str,
        default=None,
        metavar="ID",
        help="Set trigger mode by ID or name (e.g., 1 or hold).",
    )
    config_parser.add_argument(
        "--key-mode-list",
        action="store_true",
        help="Show available key modes.",
    )
    config_parser.add_argument(
        "--model",
        type=str,
        default=None,
        dest="model_id",
        metavar="ID",
        help="Set Whisper model by ID or name (e.g., 3 or base.en).",
    )
    config_parser.add_argument(
        "--model-list",
        action="store_true",
        help="Show available Whisper models.",
    )
    config_parser.add_argument(
        "--model-delete",
        nargs="+",
        metavar="ID",
        help="Delete downloaded model(s) by ID or name to free disk space.",
    )
    config_parser.add_argument(
        "--max-time",
        type=float,
        default=None,
        metavar="SECONDS",
        help="Set maximum recording time in seconds (default: 100).",
    )
    config_parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset all configuration to defaults.",
    )

    return parser


# ──── Command Handlers ────


def handle_run(args) -> None:
    """Handle the 'run' command."""
    config = Config.load()

    print(
        f"Spurt running (model: {config.model}, "
        f"key: {config.trigger_key}, mode: {config.key_mode}, "
        f"max time: {config.max_recording_time}s)"
    )
    print("Loading model... (first run may download the model)")
    engine = Engine(config)
    engine.run()


def handle_config(args) -> None:
    """Handle the 'config' command and its flags."""
    if args.reset:
        Config.reset()
        print("Configuration reset to defaults.")
        return

    if args.key:
        _interactive_key_config()
        return

    if args.key_mode is not None:
        try:
            info = resolve_key_mode(args.key_mode)
        except ValueError as e:
            print(str(e))
            sys.exit(1)
        cfg = Config.load()
        cfg.key_mode = info.name
        cfg.save()
        print(f"Key mode set to: {info.name} ({info.description})")
        return

    if args.key_mode_list:
        cfg = Config.load()
        print(f"{'ID':<4} {'':>2} {'Mode':<10} Description")
        print(f"{'──':<4} {'':>2} {'────':<10} ───────────")
        for m in KEY_MODES:
            selected = "✅" if m.name == cfg.key_mode else "  "
            print(f"{m.id:<4} {selected} {m.name:<10} {m.description}")
        return

    if args.model_id is not None:
        try:
            info = resolve_model(args.model_id)
        except ValueError as e:
            print(str(e))
            sys.exit(1)
        cfg = Config.load()
        cfg.model = info.name
        cfg.save()
        print(f"Model set to: {info.name} ({info.size}, {info.description})")
        return

    if args.model_list:
        cfg = Config.load()
        print(
            f"{'ID':<4} {'':>2} {'Model':<12} {'Size':<10} {'Downloaded':<12} Description"
        )
        print(
            f"{'──':<4} {'':>2} {'─────':<12} {'────':<10} {'──────────':<12} ───────────"
        )
        for m in MODELS:
            downloaded = "yes" if is_model_downloaded(m.name) else "no"
            selected = "✅" if m.name == cfg.model else "  "
            print(
                f"{m.id:<4} {selected} {m.name:<12} {m.size:<10} {downloaded:<12} {m.description}"
            )
        return

    if args.model_delete:
        cfg = Config.load()
        for identifier in args.model_delete:
            try:
                info = resolve_model(identifier)
            except ValueError as e:
                print(str(e))
                continue
            if info.name == cfg.model:
                print(
                    f"Cannot delete {info.name} — it's the currently configured model. "
                    f"Switch to a different model first with --model."
                )
                continue
            if delete_model(info.name):
                print(f"Deleted: {info.name} ({info.size})")
            else:
                print(f"Not downloaded: {info.name}")
        return

    if args.max_time is not None:
        if args.max_time <= 0:
            print("Max recording time must be a positive number.")
            sys.exit(1)
        cfg = Config.load()
        cfg.max_recording_time = args.max_time
        cfg.save()
        print(f"Max recording time set to: {args.max_time}s")
        return

    # No flags → show current config
    cfg = Config.load()
    print(f"trigger_key:       {cfg.trigger_key}")
    print(f"key_mode:          {cfg.key_mode}")
    print(f"model:             {cfg.model}")
    print(f"max_recording_time: {cfg.max_recording_time}s")


def _interactive_key_config() -> None:
    """Interactive key capture for --key flag."""
    print("Press the key you want to use as trigger...")

    from pynput import keyboard as kb

    captured = {}

    def on_press(k):
        captured["key"] = k
        return False  # Stop listener

    with kb.Listener(on_press=on_press) as listener:
        listener.join()

    if "key" not in captured:
        print("No key detected.")
        return

    key_str = serialize_key(captured["key"])
    cfg = Config.load()
    cfg.trigger_key = key_str
    cfg.save()
    print(f"Trigger key set to: {key_str}")


# ──── Entry Point ────


def main() -> None:
    """Parse arguments and dispatch to the appropriate handler."""
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    handlers = {
        "run": handle_run,
        "config": handle_config,
    }

    handler = handlers.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
