"""
PredictionEngine: loads the Phase 3 model artifact and the Phase 2 feature contract once per
process, caches them, and reproduces Phase 2's feature engineering exactly so a live user
payload turns into the same column layout the model was trained on.
"""

import json
import threading
from dataclasses import dataclass

import joblib
import pandas as pd
from django.conf import settings
from django.core.exceptions import ValidationError

_LOCK = threading.Lock()

LARGE_SQFT_THRESHOLD = 2000
CONFIDENCE_DATA_VOLUME_SATURATION = 50  # listings in a location beyond which data-volume confidence maxes out


@dataclass
class PredictionResult:
    point_estimate: float
    lower_bound: float
    upper_bound: float
    confidence_score: float
    model_name: str
    price_per_sqft: float
    comparable_count: int


REQUIRED_ARTIFACTS = [
    "best_model.joblib",
    "scaler.joblib",
    "feature_columns.json",
    "numeric_feature_columns.json",
    "model_meta.json",
    "location_tier_map.json",
]


class PredictionEngine:
    """
    Process-local singleton -- artifacts are read-only and a few MB at most, so per-process
    caching (rather than a shared cache) is the right tradeoff. Loading is lazy: constructing
    an instance never touches disk, so views can safely build one before checking health_check().
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            with _LOCK:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._loaded = False
        return cls._instance

    def _ensure_loaded(self):
        if self._loaded:
            return
        with _LOCK:
            if self._loaded:
                return
            artifacts_dir = settings.ML_ARTIFACTS_DIR
            self.model = joblib.load(artifacts_dir / "best_model.joblib")
            self.scaler = joblib.load(artifacts_dir / "scaler.joblib")
            with open(artifacts_dir / "feature_columns.json") as f:
                self.feature_columns = json.load(f)
            with open(artifacts_dir / "numeric_feature_columns.json") as f:
                self.numeric_columns = json.load(f)
            with open(artifacts_dir / "model_meta.json") as f:
                self.model_meta = json.load(f)
            with open(artifacts_dir / "location_tier_map.json") as f:
                self.location_tier_map = json.load(f)
            self._loaded = True

    @classmethod
    def reset(cls):
        """Invalidates the cached artifacts so the next call reloads from disk. Used after a
        successful retrain (Phase 8) so a freshly trained model is served without a process restart."""
        if cls._instance is not None:
            cls._instance._loaded = False

    @staticmethod
    def health_check() -> dict:
        """Reports whether every artifact the engine needs is present and loadable."""
        artifacts_dir = settings.ML_ARTIFACTS_DIR
        missing = [name for name in REQUIRED_ARTIFACTS if not (artifacts_dir / name).exists()]
        if missing:
            return {"ok": False, "missing": missing, "error": None}
        try:
            engine = PredictionEngine()
            engine._ensure_loaded()
        except Exception as exc:
            return {"ok": False, "missing": [], "error": str(exc)}
        return {"ok": True, "missing": [], "error": None}

    def get_model_meta(self) -> dict:
        self._ensure_loaded()
        return self.model_meta

    def build_feature_vector(self, payload: dict) -> pd.DataFrame:
        """
        Reproduces ml_pipeline/steps/03_features.py exactly: derive sqft_per_bhk/bath_per_bhk/
        is_large, scale the numeric columns with the fitted StandardScaler, one-hot the location
        and its tier, and reindex to feature_columns.json order (absent one-hot columns are 0 --
        this is correct for drop_first-encoded categories, not a missing-data workaround).
        """
        self._ensure_loaded()

        location = payload["location"]
        if location not in self.location_tier_map:
            raise ValidationError(f"Unknown location: {location}")

        area_sqft = float(payload["area_sqft"])
        bhk = int(payload["bhk"])
        bathrooms = int(payload["bathrooms"])
        balcony = int(payload.get("balcony", 0))

        raw_numeric = {
            "total_sqft": area_sqft,
            "bath": bathrooms,
            "balcony": balcony,
            "bhk": bhk,
            "sqft_per_bhk": area_sqft / bhk,
            "bath_per_bhk": bathrooms / bhk,
        }

        numeric_df = pd.DataFrame([{col: raw_numeric[col] for col in self.numeric_columns}])
        scaled = self.scaler.transform(numeric_df)
        scaled_row = dict(zip(self.numeric_columns, scaled[0]))

        vector = {col: 0 for col in self.feature_columns}
        for col, value in scaled_row.items():
            if col in vector:
                vector[col] = value

        if "is_large" in vector:
            vector["is_large"] = int(area_sqft > LARGE_SQFT_THRESHOLD)

        location_col = f"location_{location}"
        if location_col in vector:
            vector[location_col] = 1

        tier = self.location_tier_map[location]
        tier_col = f"location_tier_{tier}"
        if tier_col in vector:
            vector[tier_col] = 1

        return pd.DataFrame([vector])[self.feature_columns]

    def _confidence_score(self, location: str) -> float:
        """
        0-100 confidence blends two signals:
          - model fit quality: the deployed model's held-out test R2 (model_meta.json),
            contributing up to 60 points
          - local data volume: how many training listings exist for this location
            (Location.listing_count), contributing up to 40 points, saturating at
            CONFIDENCE_DATA_VOLUME_SATURATION listings
        A location with no training listings (e.g. a brand-new area) still gets a score driven
        by model R2 alone, rather than crashing or returning zero.
        """
        from properties.models import Location

        r2 = max(0.0, min(1.0, self.model_meta.get("r2", 0.0)))
        try:
            listing_count = Location.objects.get(name=location).listing_count
        except Location.DoesNotExist:
            listing_count = 0
        data_volume_component = min(1.0, listing_count / CONFIDENCE_DATA_VOLUME_SATURATION)
        return round(60 * r2 + 40 * data_volume_component, 1)

    def find_comparables(self, location: str, area_sqft: float, bhk: int, limit: int = 6):
        """Same location, same BHK, area within +/-15%. Pure DB query -- does not need the ML
        artifacts loaded, so it works even when health_check() is False."""
        from properties.models import Property

        low, high = area_sqft * 0.85, area_sqft * 1.15
        qs = (
            Property.objects.filter(location__name=location, bhk=bhk, area_sqft__gte=low, area_sqft__lte=high)
            .select_related("location")
            .order_by("area_sqft")
        )
        count = qs.count()
        return list(qs[:limit]), count

    def predict(self, payload: dict) -> PredictionResult:
        self._ensure_loaded()

        X = self.build_feature_vector(payload)
        point_estimate = float(self.model.predict(X)[0])

        residual_std = self.model_meta.get("residual_std", 0.0)
        margin = 1.96 * residual_std
        lower_bound = max(0.0, point_estimate - margin)
        upper_bound = point_estimate + margin

        area_sqft = float(payload["area_sqft"])
        price_per_sqft = point_estimate / area_sqft if area_sqft else 0.0

        _, comparable_count = self.find_comparables(payload["location"], area_sqft, int(payload["bhk"]))

        return PredictionResult(
            point_estimate=round(point_estimate, 2),
            lower_bound=round(lower_bound, 2),
            upper_bound=round(upper_bound, 2),
            confidence_score=self._confidence_score(payload["location"]),
            model_name=self.model_meta.get("best_model_name", "unknown"),
            price_per_sqft=round(price_per_sqft, 2),
            comparable_count=comparable_count,
        )
