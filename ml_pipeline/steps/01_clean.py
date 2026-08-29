"""
Phase 1 -- Dataset ingestion and cleaning.

Pure pandas/numpy. No Django imports here: this module must run standalone from the CLI
(run_pipeline.py) or from a notebook, independent of the web application.

Domain reasoning for the outlier rules is documented inline on each function, since this is a
graded academic pipeline and the "why" behind each rule matters as much as the "what".
"""

import json
import logging
import re
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s  %(message)s")
logger = logging.getLogger("clean")

SEED = 42
np.random.seed(SEED)

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_CSV = BASE_DIR / "data" / "raw" / "properties_raw.csv"
CLEAN_CSV = BASE_DIR / "data" / "processed" / "properties_clean.csv"
REPORT_JSON = BASE_DIR / "artifacts" / "cleaning_report.json"

# Conversion factors to square feet. Documented here because Indian listings frequently mix
# metric and traditional land-measurement units within the same dataset.
UNIT_TO_SQFT = {
    "Sq. Meter": 10.7639,   # 1 sq metre
    "Sq. Yards": 9.0,       # 1 sq yard
    "Perch": 272.25,        # 1 perch (used in south Indian listings)
    "Acre": 43560.0,        # 1 acre
    "Guntha": 1089.0,       # 1 guntha (1/40th of an acre)
    "Cents": 435.6,         # 1 cent (1/100th of an acre)
    "Grounds": 2400.35,     # 1 ground (Chennai/Tamil Nadu convention)
}

MIN_LISTINGS_PER_LOCATION = 10
MIN_SQFT_PER_BHK = 300  # domain floor: a livable bedroom rarely fits in under 300 sqft
MAX_BATH_OVER_BHK = 2   # more than 2 extra bathrooms vs bedrooms is almost always a data-entry error


def _log_step(report: dict, name: str, before: int, after: int, note: str = "") -> None:
    delta = before - after
    entry = {"step": name, "rows_before": before, "rows_after": after, "rows_dropped": delta, "note": note}
    report["steps"].append(entry)
    logger.info("%-38s  before=%-6d after=%-6d dropped=%-6d %s", name, before, after, delta, note)


def _parse_bhk(size_value):
    """'2 BHK' / '3 Bedroom' -> 2 / 3. Anything without a leading integer is unparseable."""
    if not isinstance(size_value, str):
        return np.nan
    match = re.match(r"\s*(\d+)", size_value)
    return int(match.group(1)) if match else np.nan


def _parse_total_sqft(raw_value):
    """
    Normalises the many total_sqft representations seen in Indian listing exports:
      - plain numbers: '1200', '1200.5'
      - ranges: '1200 - 1400' -> midpoint 1300
      - alternate units: '34.46Sq. Meter', '5Perch' -> converted to sqft via UNIT_TO_SQFT
      - garbage: '', 'NA', 'size unknown', '--' -> NaN, dropped downstream
    """
    if not isinstance(raw_value, str):
        return np.nan
    text = raw_value.strip()
    if text == "":
        return np.nan

    # Range: take the midpoint -- the true value is unknown, the midpoint is the least-biased estimate.
    range_match = re.match(r"^(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)$", text)
    if range_match:
        low, high = float(range_match.group(1)), float(range_match.group(2))
        return (low + high) / 2.0

    # Alternate unit suffix.
    for unit, factor in UNIT_TO_SQFT.items():
        if unit in text:
            num_match = re.match(r"^(\d+(?:\.\d+)?)", text)
            if num_match:
                return float(num_match.group(1)) * factor
            return np.nan

    # Plain float.
    try:
        return float(text)
    except ValueError:
        return np.nan


def _drop_sparse_columns(df: pd.DataFrame, report: dict, null_frac_threshold: float = 0.30) -> pd.DataFrame:
    """Columns that are mostly null (e.g. `society`) carry little signal and complicate encoding."""
    before_cols = set(df.columns)
    null_frac = df.isna().mean()
    sparse_cols = null_frac[null_frac > null_frac_threshold].index.tolist()
    df = df.drop(columns=sparse_cols)
    report["dropped_columns"] = sparse_cols
    logger.info("Dropped sparse columns (null frac > %.0f%%): %s", null_frac_threshold * 100, sparse_cols or "none")
    return df


def run() -> pd.DataFrame:
    report = {"seed": SEED, "steps": [], "dropped_columns": [], "unit_conversions": UNIT_TO_SQFT}

    logger.info("Loading raw CSV from %s", RAW_CSV)
    df = pd.read_csv(RAW_CSV)
    start_rows = len(df)
    report["initial_shape"] = [start_rows, df.shape[1]]
    logger.info("Loaded %d rows, %d columns", *df.shape)

    # 1. Drop sparse columns, then rows missing anything critical to price modelling.
    df = _drop_sparse_columns(df, report)
    critical = [c for c in ["location", "size", "total_sqft", "price"] if c in df.columns]
    before = len(df)
    df = df.dropna(subset=critical)
    _log_step(report, "drop rows missing critical fields", before, len(df), f"critical={critical}")

    # 2. Parse `size` -> integer `bhk`.
    before = len(df)
    df["bhk"] = df["size"].apply(_parse_bhk)
    df = df.dropna(subset=["bhk"])
    df["bhk"] = df["bhk"].astype(int)
    _log_step(report, "parse size -> bhk", before, len(df), "dropped rows with unparseable size")

    # 3. Normalise total_sqft (ranges, units) and drop unparseable rows.
    before = len(df)
    df["total_sqft"] = df["total_sqft"].apply(_parse_total_sqft)
    df = df.dropna(subset=["total_sqft"])
    df = df[df["total_sqft"] > 0]
    _log_step(report, "normalise total_sqft (ranges/units)", before, len(df), "dropped unparseable/zero sqft")

    # 3b. balcony is optional in most listing sources -- a blank entry means "not specified",
    #     not "no balcony", but 0 is the least-biased numeric stand-in and keeps the column
    #     usable as a model feature without dropping otherwise-good rows.
    if "balcony" in df.columns:
        n_filled = int(df["balcony"].isna().sum())
        df["balcony"] = df["balcony"].fillna(0)
        logger.info("Filled %d missing balcony values with 0", n_filled)

    # 4. price (lakhs) -> price_inr (absolute rupees) and price_per_sqft.
    df["price_inr"] = df["price"] * 100_000.0
    df["price_per_sqft"] = df["price_inr"] / df["total_sqft"]
    logger.info("Derived price_inr and price_per_sqft")

    # 5. Trim/title-case location; rare locations (< 10 listings) become "Other".
    df["location"] = df["location"].astype(str).str.strip().str.title()
    counts = df["location"].value_counts()
    rare = counts[counts < MIN_LISTINGS_PER_LOCATION].index
    n_rare_locations = len(rare)
    n_rare_rows = df["location"].isin(rare).sum()
    df.loc[df["location"].isin(rare), "location"] = "Other"
    logger.info(
        "Bucketed %d rare locations (%d rows, < %d listings each) into 'Other'",
        n_rare_locations, n_rare_rows, MIN_LISTINGS_PER_LOCATION,
    )
    report["rare_locations_bucketed"] = int(n_rare_locations)
    report["rare_location_rows"] = int(n_rare_rows)

    # 6. Outlier removal, applied in a fixed, logged order -- each rule assumes the previous
    #    ones already ran, so re-ordering them would change the result.

    # 6a. Floor plans under 300 sqft per bedroom are not livable at Indian residential norms;
    #     these are almost always data-entry errors (e.g. sqft typed in the wrong unit).
    before = len(df)
    df = df[(df["total_sqft"] / df["bhk"]) >= MIN_SQFT_PER_BHK]
    _log_step(report, "drop total_sqft/bhk < 300", before, len(df))

    # 6b. Per-location price_per_sqft outside mean +/- 1 std is filtered per location, because
    #     price_per_sqft varies enormously *between* localities (a citywide filter would just
    #     remove entire premium or budget areas rather than true outliers within each area).
    before = len(df)
    stats = df.groupby("location")["price_per_sqft"].agg(["mean", "std"]).rename(
        columns={"mean": "_loc_mean", "std": "_loc_std"}
    )
    df = df.join(stats, on="location")
    df["_loc_std"] = df["_loc_std"].fillna(0)
    lower = df["_loc_mean"] - df["_loc_std"]
    upper = df["_loc_mean"] + df["_loc_std"]
    df = df[(df["price_per_sqft"] >= lower) & (df["price_per_sqft"] <= upper)]
    df = df.drop(columns=["_loc_mean", "_loc_std"])
    _log_step(report, "per-location price_per_sqft within mean +/- 1 std", before, len(df))

    # 6c. A flat with more bedrooms should not be cheaper, on average, than a smaller flat in the
    #     same locality -- this catches BHK mislabelling that survives the two filters above.
    before = len(df)
    loc_bhk_mean_price = df.groupby(["location", "bhk"])["price_inr"].mean()

    def _bhk_price_ok(row):
        prev_key = (row["location"], row["bhk"] - 1)
        if prev_key not in loc_bhk_mean_price.index:
            return True
        return row["price_inr"] >= loc_bhk_mean_price.loc[prev_key]

    df = df[df.apply(_bhk_price_ok, axis=1)]
    _log_step(report, "drop bhk flat cheaper than mean of (bhk-1) in same location", before, len(df))

    # 6d. More than two extra bathrooms relative to bedrooms is implausible for residential
    #     listings in this dataset and usually indicates a swapped bath/balcony entry.
    before = len(df)
    if "bath" in df.columns:
        df["bath"] = df["bath"].fillna(df["bhk"])
        df = df[df["bath"] <= df["bhk"] + MAX_BATH_OVER_BHK]
    _log_step(report, "drop bath > bhk + 2", before, len(df))

    # Final tidy-up.
    df = df.reset_index(drop=True)
    report["final_shape"] = [len(df), df.shape[1]]
    report["total_rows_dropped"] = start_rows - len(df)
    report["final_columns"] = df.columns.tolist()

    CLEAN_CSV.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(CLEAN_CSV, index=False)
    with open(REPORT_JSON, "w") as f:
        json.dump(report, f, indent=2)

    logger.info("Wrote clean dataset: %s (%d rows, %d cols)", CLEAN_CSV, *df.shape)
    logger.info("Wrote cleaning report: %s", REPORT_JSON)
    logger.info("Total rows dropped: %d / %d (%.1f%%)", report["total_rows_dropped"], start_rows,
                100 * report["total_rows_dropped"] / start_rows)

    return df


if __name__ == "__main__":
    run()
