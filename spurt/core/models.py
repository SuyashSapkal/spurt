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
