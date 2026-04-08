# Spurt — Push-to-Talk Dictation

A cross-platform push-to-talk dictation tool powered by [whisper.cpp](https://github.com/ggerganov/whisper.cpp). Press and hold a hotkey, speak into your mic, release — your words are typed into the active window.

---

## Quick Start

### Option 1: Download the pre-built binary (easiest)

Download the latest release for your OS from [**GitHub Releases**](https://github.com/SuyashSapkal/spurt-x/releases).

- **Windows:** `spurt-cli-windows.zip` (contains `spurt-cli.exe`)
- **Linux:** `spurt-cli-linux.zip` (contains `spurt-cli`)
- **macOS:** `spurt-cli-macos.zip` (contains `spurt-cli`)

Unzip and run — no Python required. Default configuration is already in place, no setup needed:

```bash
# Start dictating immediately
spurt-cli run
```

The whisper model downloads automatically on first run. Once you see `Model loaded. Press Ctrl+C to stop.`, hold the trigger key (Right Ctrl on Windows/Linux, Right Cmd on macOS), speak, and release — your words appear in the active window.

Configuration is **optional** — see the [Configuration](#configuration) section if you want to change the model, trigger key, or key mode.

### Option 2: Run from source

> **Note:** The Python command varies by OS. This README uses `python`. On **Windows**, you may need to use `py` instead. On some **Linux** systems, use `python3`. Replace accordingly in all commands below.

```bash
# Clone and enter the project
git clone <repo-url>
cd spurt

# Create a virtual environment and activate it
python -m venv .venv
source .venv/bin/activate          # Linux/macOS
.venv\Scripts\activate.bat         # Windows (cmd)
.venv\Scripts\Activate.ps1         # Windows (PowerShell)

# Install dependencies
pip install -r requirements.txt

# Start dictating — defaults work out of the box, no configuration needed
python -m spurt.cli.main run
```

The whisper model downloads automatically on first run. Once you see `Model loaded. Press Ctrl+C to stop.`, hold the trigger key (Right Ctrl on Windows/Linux, Right Cmd on macOS), speak, and release — your words appear in the active window.

> **Tip:** To run spurt in the background, use a separate terminal or tmux session.

---

## Building a Standalone Binary

If you want a single executable that doesn't require Python:

```bash
# Install dev dependencies (includes PyInstaller)
pip install -r requirements-dev.txt

# Build
pyinstaller --onefile --name spurt-cli --paths . --distpath output spurt/cli/main.py
```

The binary is at `output/spurt-cli` (Linux/macOS) or `output/spurt-cli.exe` (Windows). It works the same way — defaults are ready out of the box:

```bash
# Start dictating — no configuration needed
output/spurt-cli run

# All other commands work the same
output/spurt-cli config --model-list
output/spurt-cli --version
output/spurt-cli --help
```

---

## Configuration

Configuration is **optional** — sensible defaults work out of the box.

**Defaults:**
- **Model:** `base.en` (~142MB, balanced speed/accuracy, English-only)
- **Trigger key:** Right Ctrl (Windows/Linux), Right Cmd (macOS)
- **Key mode:** Hold (press and hold to dictate, release to stop)
- **Max recording time:** 100 seconds

### View current config

```bash
python -m spurt.cli.main config
```

### Change the whisper model

```bash
# See available models (shows which are downloaded)
python -m spurt.cli.main config --model-list

# Set by ID or name
python -m spurt.cli.main config --model 1          # tiny.en — fastest, least accurate
python -m spurt.cli.main config --model small.en    # slower but more accurate
```

### Change the trigger key

```bash
# Interactive — press the key you want to use
python -m spurt.cli.main config --key
```

### Change the key mode

```bash
# See available modes
python -m spurt.cli.main config --key-mode-list

# Set by ID or name
python -m spurt.cli.main config --key-mode 1       # hold — press and hold to dictate
python -m spurt.cli.main config --key-mode 2       # toggle — press to start, press again to stop
```

### Change max recording time

The recording auto-stops after this many seconds and transcribes what it has.

```bash
python -m spurt.cli.main config --max-time 60      # 60 seconds
```

### Manage downloaded models

Models stay on disk when you switch between them. To free space:

```bash
# Delete by ID or name (multiple at once)
python -m spurt.cli.main config --model-delete 1 2 3
python -m spurt.cli.main config --model-delete tiny.en

# Note: you cannot delete the currently configured model
```

### Reset to defaults

```bash
python -m spurt.cli.main config --reset
```

---

## Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage report
python -m pytest tests/ -v --cov=spurt

# Run a specific test file
python -m pytest tests/test_models.py -v

# Run a specific test
python -m pytest tests/test_hotkey.py::TestHoldMode::test_press_activates -v
```

All tests mock external dependencies (pywhispercpp, sounddevice, pynput). No microphone, no model downloads, no network access needed.

---

## Troubleshooting

### Microphone not working

| Platform | What to check |
|----------|---------------|
| **Windows** | Should work out of the box. Check that your mic is set as the default recording device in Sound Settings. |
| **Linux** | You may need to install PortAudio: `sudo apt install libportaudio2` |
| **macOS** | Grant microphone permission to your terminal app when prompted. Check System Settings → Privacy & Security → Microphone. |

### Model download fails

Models are downloaded from Hugging Face on first use. If the download fails:
- Check your internet connection
- Try again — the download resumes where it left off
- Manually check the model cache directory (see Reference section below)

### Trigger key not detected

- Make sure spurt is running (`python -m spurt.cli.main run`)
- On **Linux/Wayland**, `pynput` may have limited support — X11 works best
- Try a different key: `python -m spurt.cli.main config --key`

### Text not appearing in active window

- Click into the target window (text editor, browser, etc.) before pressing the trigger key
- On **macOS**, grant Accessibility permission to your terminal app (System Settings → Privacy & Security → Accessibility)
- On **Linux/Wayland**, keyboard simulation may require X11

---

## Reference

### Available models

| ID | Model | Size | Description |
|----|-------|------|-------------|
| 1 | tiny.en | ~75MB | Fastest, English-only, lower accuracy |
| 2 | tiny | ~75MB | Fastest, multilingual, lower accuracy |
| 3 | base.en | ~142MB | Balanced, English-only **(default)** |
| 4 | base | ~142MB | Balanced, multilingual |
| 5 | small.en | ~466MB | Slower, English-only, higher accuracy |
| 6 | small | ~466MB | Slower, multilingual, higher accuracy |
| 7 | medium.en | ~1.5GB | Slow, English-only, high accuracy |
| 8 | medium | ~1.5GB | Slow, multilingual, high accuracy |
| 9 | large-v3 | ~3.1GB | Slowest, multilingual, highest accuracy |

Models ending in `.en` are English-only (faster, more accurate for English). Models without `.en` support 99+ languages.

### Key modes

| ID | Mode | Description |
|----|------|-------------|
| 1 | hold | Press and hold to dictate, release to stop **(default)** |
| 2 | toggle | Press once to start, press again to stop |

### Config file location

| Platform | Path |
|----------|------|
| **Windows** | `%APPDATA%\spurt\config.json` |
| **Linux** | `~/.config/spurt/config.json` |
| **macOS** | `~/Library/Application Support/spurt/config.json` |

### Model cache location

| Platform | Path |
|----------|------|
| **Windows** | `%APPDATA%\pywhispercpp\models\` |
| **Linux** | `~/.local/share/pywhispercpp/models/` |
| **macOS** | `~/Library/Application Support/pywhispercpp/models/` |

### Project structure

```
spurt/
├── requirements.txt          # Runtime dependencies (3 packages)
├── requirements-dev.txt      # Dev dependencies (testing + build)
├── .gitignore
├── README.md
├── spurt/
│   ├── __init__.py           # Package version
│   ├── core/
│   │   ├── __init__.py
│   │   ├── models.py         # Whisper model registry + cache helpers
│   │   ├── config.py         # Config load/save/reset
│   │   ├── transcriber.py    # pywhispercpp wrapper (pre-loads model on run)
│   │   ├── recorder.py       # Microphone capture via sounddevice
│   │   ├── hotkey.py         # Global hotkey detection + key modes
│   │   ├── output.py         # Type text into active window
│   │   └── engine.py         # Orchestrator — wires all components
│   └── cli/
│       ├── __init__.py
│       └── main.py           # argparse CLI (thin wrapper)
└── tests/
    ├── __init__.py
    ├── conftest.py           # Shared fixtures
    ├── test_models.py
    ├── test_config.py
    ├── test_transcriber.py
    ├── test_recorder.py
    ├── test_hotkey.py
    ├── test_output.py
    └── test_engine.py
```

### Dependencies

Only 3 external runtime packages — everything else is Python stdlib:

| Package | Purpose |
|---------|---------|
| `pywhispercpp` | Whisper speech-to-text engine |
| `sounddevice` | Cross-platform microphone capture |
| `pynput` | Global hotkey detection + keyboard typing simulation |

---

## License

This project is licensed under the [BSD 2-Clause License](LICENSE).
