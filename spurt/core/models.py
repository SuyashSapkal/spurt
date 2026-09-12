"""Predefined Whisper model registry."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ModelInfo:
    """Metadata for a Whisper model."""

    id: int
    name: str
    size: str
    description: str


MODELS: list[ModelInfo] = [
    ModelInfo(1, "tiny.en", "~75MB", "Fastest, English-only, lower accuracy"),
    ModelInfo(2, "tiny", "~75MB", "Fastest, multilingual, lower accuracy"),
    ModelInfo(3, "base.en", "~142MB", "Balanced, English-only (default)"),
    ModelInfo(4, "base", "~142MB", "Balanced, multilingual"),
    ModelInfo(5, "small.en", "~466MB", "Slower, English-only, higher accuracy"),
    ModelInfo(6, "small", "~466MB", "Slower, multilingual, higher accuracy"),
    ModelInfo(7, "medium.en", "~1.5GB", "Slow, English-only, high accuracy"),
    ModelInfo(8, "medium", "~1.5GB", "Slow, multilingual, high accuracy"),
    ModelInfo(9, "large-v3", "~3.1GB", "Slowest, multilingual, highest accuracy"),
]

MODELS_BY_ID: dict[int, ModelInfo] = {m.id: m for m in MODELS}
MODELS_BY_NAME: dict[str, ModelInfo] = {m.name: m for m in MODELS}
DEFAULT_MODEL = "base.en"


def resolve_model(identifier: str) -> ModelInfo:
    """Resolve a model by numeric ID ('3') or name ('base.en').

    Args:
        identifier: A numeric ID string or model name.

    Returns:
        The matching ModelInfo.

    Raises:
        ValueError: If no model matches the identifier.
    """
    if not isinstance(identifier, str):
        raise TypeError(f"Expected string identifier, got {type(identifier).__name__}")

    # Try numeric ID first
    try:
        num = int(identifier)
        if num in MODELS_BY_ID:
            return MODELS_BY_ID[num]
    except ValueError:
        pass

    # Try name lookup
    if identifier in MODELS_BY_NAME:
        return MODELS_BY_NAME[identifier]

    raise ValueError(
        f"Unknown model: {identifier!r}. "
        f"Use 'spurt-cli config --model-list' to see available models."
    )


# ──── Model Cache Helpers ────


def get_models_dir() -> Path:
    """Get the pywhispercpp model cache directory.

    Uses platformdirs (a transitive dependency of pywhispercpp) to find
    the platform-specific user data directory.

    Returns:
        Path to the models directory:
        - Windows: %APPDATA%/pywhispercpp/models/
        - macOS: ~/Library/Application Support/pywhispercpp/models/
        - Linux: ~/.local/share/pywhispercpp/models/
    """
    from platformdirs import user_data_dir

    return Path(user_data_dir("pywhispercpp")) / "models"


def get_model_path(model_name: str) -> Path:
    """Get the path to a cached model file.

    Args:
        model_name: The model name (e.g., "base.en").

    Returns:
        Path to the model file (may not exist if not downloaded).
    """
    return get_models_dir() / f"ggml-{model_name}.bin"


def is_model_downloaded(model_name: str) -> bool:
    """Check if a model is already downloaded to the cache.

    Args:
        model_name: The model name (e.g., "base.en").
    """
    return get_model_path(model_name).exists()


def delete_model(model_name: str) -> bool:
    """Delete a cached model file to free disk space.

    Args:
        model_name: The model name (e.g., "base.en").

    Returns:
        True if the model was deleted, False if it wasn't downloaded.
    """
    path = get_model_path(model_name)
    if path.exists():
        path.unlink()
        return True
    return False


# whisper.cpp GGML weights live in this Hugging Face repo. pywhispercpp pulls
# from the same place; we download here ourselves only so a UI can show a real
# progress bar (pywhispercpp exposes no download-progress hook).
_HF_MODEL_URL = (
    "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-{name}.bin"
)


def download_model(model_name: str, on_progress=None, chunk_size: int = 1 << 20) -> Path:
    """Download a Whisper model into the cache, reporting progress.

    Streams ``ggml-<model_name>.bin`` into the pywhispercpp cache directory so a
    subsequent Transcriber load finds it cached (no second download). Intended
    for UIs that want a determinate progress bar; the CLI path still lets
    pywhispercpp download internally.

    Args:
        model_name: The model name (e.g., "base.en").
        on_progress: Optional callable ``(downloaded_bytes, total_bytes)``.
                     ``total_bytes`` is 0 when the server omits Content-Length —
                     callers should then show an indeterminate indicator.
        chunk_size: Read/write chunk size in bytes.

    Returns:
        Path to the downloaded model file.

    Raises:
        ValueError: If the model name is unknown.
        urllib.error.URLError / OSError: On network or filesystem failure.
    """
    # Validate the name against the registry before hitting the network.
    resolve_model(model_name if isinstance(model_name, str) else str(model_name))

    import urllib.request

    dest = get_model_path(model_name)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")

    url = _HF_MODEL_URL.format(name=model_name)
    req = urllib.request.Request(url, headers={"User-Agent": "spurt"})
    try:
        with urllib.request.urlopen(req) as resp:  # nosec B310 — pinned https host
            total = int(resp.headers.get("Content-Length", 0) or 0)
            downloaded = 0
            if on_progress is not None:
                on_progress(downloaded, total)
            with open(tmp, "wb") as f:
                while True:
                    buf = resp.read(chunk_size)
                    if not buf:
                        break
                    f.write(buf)
                    downloaded += len(buf)
                    if on_progress is not None:
                        on_progress(downloaded, total)
        # Atomic swap — never leave a half-written file at the real path.
        tmp.replace(dest)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
    return dest
