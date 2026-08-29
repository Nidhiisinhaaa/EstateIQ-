"""Verifies the Django predictor reproduces the Phase 2 feature contract exactly."""

import json

import pytest
from django.conf import settings

from predictor.services.engine import PredictionEngine


def _require_artifacts():
    health = PredictionEngine.health_check()
    if not health["ok"]:
        pytest.skip(f"ML artifacts not present: {health}. Run ml_pipeline/run_pipeline.py --step all first.")


def test_feature_vector_column_order_matches_feature_columns_json():
    _require_artifacts()

    with open(settings.ML_ARTIFACTS_DIR / "feature_columns.json") as f:
        expected_columns = json.load(f)
    with open(settings.ML_ARTIFACTS_DIR / "location_tier_map.json") as f:
        tier_map = json.load(f)

    sample_location = next(iter(tier_map))
    payload = {"location": sample_location, "area_sqft": 1000, "bhk": 2, "bathrooms": 2, "balcony": 1}

    engine = PredictionEngine()
    X = engine.build_feature_vector(payload)

    assert list(X.columns) == expected_columns


def test_feature_vector_rejects_unknown_location():
    from django.core.exceptions import ValidationError

    _require_artifacts()
    engine = PredictionEngine()
    payload = {"location": "Nonexistent Location Xyz", "area_sqft": 1000, "bhk": 2, "bathrooms": 2, "balcony": 1}

    with pytest.raises(ValidationError):
        engine.build_feature_vector(payload)
