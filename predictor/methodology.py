"""
Static rationale text for the Phase 8 Model Report methodology section. The row counts and
deltas shown alongside this text always come from ml_pipeline/artifacts/cleaning_report.json
(read live in views.py) so the numbers can never drift from the actual pipeline run -- only the
prose explanation of *why* each rule exists lives here, since that reasoning doesn't change
between pipeline runs.
"""

CLEANING_STEP_RATIONALE = {
    "drop rows missing critical fields": (
        "Location, size, total_sqft and price are the fields every downstream step depends on. "
        "A row missing any of them cannot be feature-engineered or used as a training label, so "
        "it is dropped rather than imputed -- guessing a price or square footage would inject "
        "fabricated signal into the model."
    ),
    "parse size -> bhk": (
        "The raw `size` field is free text ('2 BHK', '3 Bedroom'). Rows where no leading integer "
        "can be extracted carry no usable bedroom count and are dropped."
    ),
    "normalise total_sqft (ranges/units)": (
        "total_sqft arrives as plain numbers, ranges ('1200 - 1400'), and alternate land-measurement "
        "units (Sq. Meter, Perch, Acre, Guntha, Cents). Ranges are collapsed to their midpoint as the "
        "least-biased point estimate; units are converted to a common sqft basis; anything left "
        "unparseable is dropped rather than silently coerced to zero or NaN."
    ),
    "drop total_sqft/bhk < 300": (
        "Under 300 sqft per bedroom is below livable Indian residential norms and is almost always "
        "a data-entry error (frequently a unit mismatch) rather than a genuine micro-unit."
    ),
    "per-location price_per_sqft within mean +/- 1 std": (
        "Price per sqft varies enormously between localities, so outlier filtering is done per "
        "location rather than citywide -- a citywide filter would simply remove entire premium or "
        "budget areas instead of true within-area outliers."
    ),
    "drop bhk flat cheaper than mean of (bhk-1) in same location": (
        "In the same locality, a flat with more bedrooms should not, on average, be cheaper than a "
        "smaller flat. Rows that violate this catch BHK mislabelling that survives the two filters "
        "above."
    ),
    "drop bath > bhk + 2": (
        "More than two extra bathrooms relative to bedrooms is implausible for residential listings "
        "in this dataset and usually indicates a swapped bath/balcony entry."
    ),
}

ENGINEERED_FEATURES = [
    {
        "name": "sqft_per_bhk",
        "rationale": (
            "total_sqft divided by bhk -- captures room generosity independent of overall size, so "
            "the model can distinguish a spacious 2 BHK from a cramped 4 BHK with the same footprint."
        ),
    },
    {
        "name": "bath_per_bhk",
        "rationale": "bathrooms divided by bhk -- a proxy for finish quality; higher ratios trend with premium construction.",
    },
    {
        "name": "is_large",
        "rationale": (
            "Binary flag for total_sqft > 2000 sqft -- large-format homes follow a different pricing "
            "regime than typical apartments, which a single linear term cannot capture."
        ),
    },
    {
        "name": "location_tier",
        "rationale": (
            "Locations are binned into Premium/Mid/Budget terciles by their historical median "
            "price_per_sqft. This gives the model a coarse locality signal that generalises, rather "
            "than relying only on individual location one-hot columns."
        ),
    },
    {
        "name": "location (one-hot, drop_first=True)",
        "rationale": (
            "Location is the single strongest predictor of price in Indian real estate. One-hot "
            "encoding avoids imposing a false ordinal relationship between location names."
        ),
    },
    {
        "name": "price_per_sqft -- deliberately EXCLUDED from model input",
        "rationale": (
            "price_per_sqft = price_inr / total_sqft, i.e. it is algebraically derived from the "
            "prediction target. A user asking for a price estimate cannot supply their own "
            "price_per_sqft, so training on it would be leakage that inflates offline accuracy while "
            "being unusable at inference. It is kept only as a reference/display column."
        ),
    },
]
