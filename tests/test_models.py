"""Tests for spurt.core.models — model registry."""

import pytest

from spurt.core.models import (
    MODELS,
    MODELS_BY_ID,
    MODELS_BY_NAME,
    DEFAULT_MODEL,
    ModelInfo,
    resolve_model,
)


class TestModelRegistry:
    """Tests for the static model registry data."""

    def test_all_ids_unique(self):
        ids = [m.id for m in MODELS]
        assert len(set(ids)) == len(MODELS), "Duplicate model IDs found"

    def test_all_names_unique(self):
        names = [m.name for m in MODELS]
        assert len(set(names)) == len(MODELS), "Duplicate model names found"

    def test_default_model_exists(self):
        assert (
            DEFAULT_MODEL in MODELS_BY_NAME
        ), f"Default model {DEFAULT_MODEL!r} not in registry"

    def test_models_by_id_matches_list(self):
        assert len(MODELS_BY_ID) == len(MODELS)
        for m in MODELS:
            assert MODELS_BY_ID[m.id] is m

    def test_models_by_name_matches_list(self):
        assert len(MODELS_BY_NAME) == len(MODELS)
        for m in MODELS:
            assert MODELS_BY_NAME[m.name] is m

    def test_model_info_is_frozen(self):
        model = MODELS[0]
        with pytest.raises(AttributeError):
            model.name = "changed"


class TestResolveModel:
    """Tests for resolve_model()."""

    def test_resolve_by_id(self):
        result = resolve_model("3")
        assert result.name == "base.en"
        assert result.id == 3

    def test_resolve_by_name(self):
        result = resolve_model("base.en")
        assert result.id == 3
        assert result.name == "base.en"

    def test_resolve_first_model_by_id(self):
        result = resolve_model("1")
        assert result.name == "tiny.en"

    def test_resolve_last_model_by_id(self):
        result = resolve_model("9")
        assert result.name == "large-v3"

    def test_resolve_invalid_id(self):
        with pytest.raises(ValueError, match="Unknown model"):
            resolve_model("99")

    def test_resolve_invalid_name(self):
        with pytest.raises(ValueError, match="Unknown model"):
            resolve_model("nonexistent")

    def test_resolve_empty_string(self):
        with pytest.raises(ValueError, match="Unknown model"):
            resolve_model("")

    def test_resolve_non_string_raises_type_error(self):
        with pytest.raises(TypeError, match="Expected string"):
            resolve_model(3)

    def test_resolve_id_zero(self):
        with pytest.raises(ValueError, match="Unknown model"):
            resolve_model("0")

    def test_resolve_negative_id(self):
        with pytest.raises(ValueError, match="Unknown model"):
            resolve_model("-1")
