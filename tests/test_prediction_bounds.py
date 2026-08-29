"""Verifies the prediction interval always brackets the point estimate."""

import json

import pytest
from django.conf import settings

from predictor.services.engine import PredictionEngine
from properties.models import Location


def _require_artifacts():
    health = PredictionEngine.health_check()
    if not health["ok"]:
        pytest.skip(f"ML artifacts not present: {health}. Run ml_pipeline/run_pipeline.py --step all first.")


@pytest.mark.django_db
@pytest.mark.parametrize("area_sqft,bhk,bathrooms", [(600, 1, 1), (1200, 3, 2), (3500, 5, 4)])
def test_prediction_bounds_bracket_point_estimate(area_sqft, bhk, bathrooms):
    _require_artifacts()

    with open(settings.ML_ARTIFACTS_DIR / "location_tier_map.json") as f:
        tier_map = json.load(f)
    sample_location = next(iter(tier_map))
    Location.objects.get_or_create(name=sample_location, defaults={"tier": tier_map[sample_location]})

    engine = PredictionEngine()
    result = engine.predict({
        "location": sample_location, "area_sqft": area_sqft, "bhk": bhk,
        "bathrooms": bathrooms, "balcony": 1,
    })

    assert result.lower_bound <= result.point_estimate <= result.upper_bound
    assert result.lower_bound >= 0
    assert 0 <= result.confidence_score <= 100
