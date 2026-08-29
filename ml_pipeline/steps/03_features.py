"""
Phase 2, Part B -- Feature engineering.

Reads the Phase 1 cleaned dataset and produces the exact, stable feature contract the Django
predictor (Phase 5) will reproduce at inference time:
  - ml_pipeline/artifacts/feature_columns.json  -- ordered list of the model's input columns
  - ml_pipeline/artifacts/numeric_feature_columns.json -- the subset that passes through the scaler
  - ml_pipeline/artifacts/location_tier_map.json -- location -> tier, needed because tier is
    derived from *location-level* historical price_per_sqft, not from any single row, so it must
    be looked up rather than recomputed at prediction time
  - ml_pipeline/artifacts/scaler.joblib -- StandardScaler fit on numeric columns only
  - ml_pipeline/data/processed/features.csv -- the final ML-ready matrix (+ price_inr target)
  - ml_pipeline/artifacts/split_indices.json -- train/test row indices, fixed for reproducibility

IMPORTANT -- price_per_sqft is intentionally NOT included as a model input feature. It is
computed as price_inr / total_sqft, i.e. it is algebraically derived from the prediction target.
A user asking "what will this property cost?" cannot supply their own price_per_sqft, so training
on it would be leakage that inflates offline accuracy while being useless (or actively
misleading) at inference. It is kept in features.csv as a reference column only.

Pure pandas/numpy/scikit-learn. No Django imports.
"""

import json
import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s  %(message)s")
logger = logging.getLogger("features")

SEED = 42
np.random.seed(SEED)

BASE_DIR = Path(__file__).resolve().parent.parent
CLEAN_CSV = BASE_DIR / "data" / "processed" / "properties_clean.csv"
FEATURES_CSV = BASE_DIR / "data" / "processed" / "features.csv"
ARTIFACTS_DIR = BASE_DIR / "artifacts"

FEATURE_COLUMNS_JSON = ARTIFACTS_DIR / "feature_columns.json"
NUMERIC_COLUMNS_JSON = ARTIFACTS_DIR / "numeric_feature_columns.json"
LOCATION_TIER_MAP_JSON = ARTIFACTS_DIR / "location_tier_map.json"
SCALER_PATH = ARTIFACTS_DIR / "scaler.joblib"
SPLIT_INDICES_JSON = ARTIFACTS_DIR / "split_indices.json"

# Raw numeric predictors -- all directly computable from a user's prediction-form input.
NUMERIC_FEATURE_COLUMNS = ["total_sqft", "bath", "balcony", "bhk", "sqft_per_bhk", "bath_per_bhk"]

LARGE_SQFT_THRESHOLD = 2000
TIER_LABELS = ["Budget", "Mid", "Premium"]


def _engineer_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["sqft_per_bhk"] = df["total_sqft"] / df["bhk"]
    df["bath_per_bhk"] = df["bath"] / df["bhk"]
    df["is_large"] = (df["total_sqft"] > LARGE_SQFT_THRESHOLD).astype(int)
    return df


def _derive_location_tier(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Bins locations into Premium/Mid/Budget by tercile of *location-level median* price_per_sqft
    (not the individual row's price_per_sqft -- that would reintroduce the same leakage problem
    price_per_sqft has on its own). The resulting location -> tier map is a stable lookup table
    the Django predictor can use for any known location without recomputation.
    """
    loc_median = df.groupby("location")["price_per_sqft"].median().sort_values()
    tiers = pd.qcut(loc_median, q=3, labels=TIER_LABELS)
    tier_map = tiers.astype(str).to_dict()
    df = df.copy()
    df["location_tier"] = df["location"].map(tier_map)
    return df, tier_map


def run():
    logger.info("Loading cleaned dataset from %s", CLEAN_CSV)
    df = pd.read_csv(CLEAN_CSV)

    df = _engineer_columns(df)
    df, tier_map = _derive_location_tier(df)
    logger.info("Derived location_tier for %d locations", len(tier_map))

    # One-hot encode location and location_tier (drop_first=True per the spec's stable contract).
    location_dummies = pd.get_dummies(df["location"], prefix="location", drop_first=True)
    tier_dummies = pd.get_dummies(df["location_tier"], prefix="location_tier", drop_first=True)
    location_dummies = location_dummies.astype(int)
    tier_dummies = tier_dummies.astype(int)

    # Fit the scaler on numeric columns only, then overwrite them in place.
    scaler = StandardScaler()
    scaled_numeric = pd.DataFrame(
        scaler.fit_transform(df[NUMERIC_FEATURE_COLUMNS]),
        columns=NUMERIC_FEATURE_COLUMNS,
        index=df.index,
    )

    model_df = pd.concat(
        [scaled_numeric, df[["is_large"]], location_dummies, tier_dummies], axis=1
    )
    feature_columns = model_df.columns.tolist()

    # Reference columns kept for display/debugging but excluded from the model's X matrix.
    model_df["price_inr"] = df["price_inr"]
    model_df["price_per_sqft"] = df["price_per_sqft"]
    model_df["location"] = df["location"]

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    FEATURES_CSV.parent.mkdir(parents=True, exist_ok=True)
    model_df.to_csv(FEATURES_CSV, index=False)
    logger.info("Wrote %s (%d rows, %d feature columns)", FEATURES_CSV, len(model_df), len(feature_columns))

    with open(FEATURE_COLUMNS_JSON, "w") as f:
        json.dump(feature_columns, f, indent=2)
    with open(NUMERIC_COLUMNS_JSON, "w") as f:
        json.dump(NUMERIC_FEATURE_COLUMNS, f, indent=2)
    with open(LOCATION_TIER_MAP_JSON, "w") as f:
        json.dump(tier_map, f, indent=2)
    joblib.dump(scaler, SCALER_PATH)
    logger.info("Wrote feature_columns.json, numeric_feature_columns.json, location_tier_map.json, scaler.joblib")

    # Fixed train/test split, saved by row-index so Phase 3 training reproduces it exactly.
    train_idx, test_idx = train_test_split(model_df.index.tolist(), test_size=0.2, random_state=SEED)
    with open(SPLIT_INDICES_JSON, "w") as f:
        json.dump({"train": train_idx, "test": test_idx, "test_size": 0.2, "random_state": SEED}, f)
    logger.info("Wrote split_indices.json (train=%d, test=%d)", len(train_idx), len(test_idx))

    return model_df


if __name__ == "__main__":
    run()
