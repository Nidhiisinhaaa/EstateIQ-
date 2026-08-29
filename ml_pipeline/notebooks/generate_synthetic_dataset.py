"""
Generates ml_pipeline/data/raw/properties_raw.csv.

This is NOT part of the graded cleaning pipeline (01_clean.py). It is a one-time data
preparation utility that stands in for a scraped dataset -- see ../data/raw/SOURCE.md for why.

Deliberately reproduces the messiness of common Bengaluru/Mumbai Kaggle-style housing CSVs:
free-text size, total_sqft ranges and alternate units, a heavily-null society column, a long
tail of rare localities, and injected outliers -- so that 01_clean.py has real work to do.

Run: python ml_pipeline/notebooks/generate_synthetic_dataset.py
"""

import random
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
random.seed(SEED)
np.random.seed(SEED)

OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "raw" / "properties_raw.csv"

N_ROWS = 10000

# location name -> (tier, weight, base price-per-sqft in INR)
MAIN_LOCATIONS = {
    "Whitefield": ("Mid", 55, 5800),
    "Electronic City": ("Budget", 60, 4200),
    "Sarjapur Road": ("Mid", 58, 5600),
    "Marathahalli": ("Mid", 50, 6100),
    "HSR Layout": ("Premium", 48, 7800),
    "Indiranagar": ("Premium", 40, 11500),
    "Koramangala": ("Premium", 42, 12200),
    "Jayanagar": ("Premium", 38, 9200),
    "JP Nagar": ("Mid", 45, 6800),
    "Yelahanka": ("Budget", 46, 4500),
    "Hebbal": ("Mid", 40, 6900),
    "Bannerghatta Road": ("Budget", 42, 4700),
    "Hennur": ("Mid", 36, 5900),
    "Kanakapura Road": ("Budget", 44, 4300),
    "Rajaji Nagar": ("Premium", 30, 8900),
    "Malleshwaram": ("Premium", 28, 10200),
    "Basavanagudi": ("Premium", 26, 9500),
    "BTM Layout": ("Mid", 47, 6600),
    "Bellandur": ("Mid", 52, 6400),
    "Varthur": ("Budget", 49, 4400),
    "KR Puram": ("Budget", 43, 4600),
    "Banashankari": ("Mid", 39, 6200),
    "Uttarahalli": ("Budget", 34, 4100),
    "Vijayanagar": ("Mid", 31, 6300),
    "Frazer Town": ("Premium", 22, 9800),
    "RT Nagar": ("Mid", 29, 6000),
    "Domlur": ("Premium", 24, 10800),
    "CV Raman Nagar": ("Mid", 27, 6700),
    "Kengeri": ("Budget", 33, 3900),
    "Yeshwanthpur": ("Mid", 32, 6500),
}

RARE_SUFFIXES = [
    "Layout", "Extension", "Phase 1", "Phase 2", "Stage 2", "Cross", "Main Road",
    "Colony", "Gardens", "Enclave", "Nagar", "Block", "Township",
]
RARE_ROOTS = [
    "Munnekollal", "Doddakannelli", "Chikkabanavara", "Thanisandra", "Nagarbhavi",
    "Vidyaranyapura", "Horamavu", "Kaggadasapura", "Anekal", "Attibele", "Begur",
    "Chandapura", "Dodballapur Road", "Gottigere", "Harlur", "Jalahalli", "Kadugodi",
    "Kudlu Gate", "Mahadevapura", "Nallurhalli", "Old Airport Road", "Rajarajeshwari Nagar",
    "Sompura", "Talaghattapura", "Tumkur Road", "Vishveshwarya Layout", "Whitefield Hope Farm",
    "Yelenahalli", "Akshaya Nagar", "Ambalipura", "Devanahalli", "Gunjur", "Haralur Road",
    "Kalyan Nagar", "Kumaraswamy Layout", "Nagavara", "Pattandur Agrahara", "Ramamurthy Nagar",
    "Sarjapur", "Sathanur", "Singasandra", "Sonnenahalli", "Subramanyapura", "Vasanthapura",
]

rare_locations = {}
for root in RARE_ROOTS:
    n_variants = random.randint(2, 4)
    for suf in random.sample(RARE_SUFFIXES, n_variants):
        name = f"{root} {suf}"
        tier = random.choice(["Budget", "Mid", "Premium"])
        base_ppsf = {"Budget": 4200, "Mid": 6200, "Premium": 9500}[tier] + random.randint(-800, 800)
        rare_locations[name] = (tier, random.randint(1, 8), base_ppsf)

ALL_LOCATIONS = {**MAIN_LOCATIONS, **rare_locations}
names = list(ALL_LOCATIONS.keys())
weights = np.array([ALL_LOCATIONS[n][1] for n in names], dtype=float)
weights = weights / weights.sum()

UNIT_CONVERSIONS = {
    "Sq. Meter": 10.7639,
    "Perch": 272.25,
    "Acre": 43560.0,
    "Guntha": 1089.0,
    "Cents": 435.6,
}

AREA_TYPES = ["Super built-up  Area", "Built-up  Area", "Plot  Area", "Carpet  Area"]
AREA_TYPE_WEIGHTS = [0.55, 0.25, 0.10, 0.10]

AVAILABILITY_DATES = ["18-Dec", "18-Jun", "19-Mar", "19-May", "18-Nov", "19-Aug"]

SOCIETY_ROOTS = ["Prestige", "Sobha", "Brigade", "Purva", "Godrej", "Mantri", "Salarpuria", "Adarsh"]


def make_total_sqft(sqft_value: float) -> str:
    r = random.random()
    if r < 0.68:
        return str(round(sqft_value, 2 if random.random() < 0.3 else 0))
    if r < 0.83:
        spread = sqft_value * random.uniform(0.05, 0.15)
        low = round(sqft_value - spread)
        high = round(sqft_value + spread)
        return f"{low} - {high}"
    if r < 0.95:
        unit, factor = random.choice(list(UNIT_CONVERSIONS.items()))
        native = sqft_value / factor
        return f"{round(native, 2)}{unit}"
    # unparseable garbage, dropped by the cleaning step
    return random.choice(["", "NA", "size unknown", "--"])


def make_size(bhk: int) -> str:
    if random.random() < 0.8:
        return f"{bhk} BHK"
    return f"{bhk} Bedroom"


def make_society() -> str:
    if random.random() < 0.55:
        return np.nan  # heavy nulls -- exercises the "drop columns with excessive nulls" rule
    return f"{random.choice(SOCIETY_ROOTS)}{random.choice(['Meridian', 'Heights', 'Residency', 'Greens', 'Enclave'])}"


rows = []
for _ in range(N_ROWS):
    loc = np.random.choice(names, p=weights)
    tier, _, base_ppsf = ALL_LOCATIONS[loc]

    bhk = int(np.random.choice([1, 2, 3, 4, 5, 6], p=[0.12, 0.38, 0.32, 0.13, 0.04, 0.01]))
    base_sqft_per_bhk = random.uniform(430, 720)
    sqft = max(250, bhk * base_sqft_per_bhk + np.random.normal(0, 60))

    # inject undersized-floor-plan outliers (~2%)
    if random.random() < 0.02:
        sqft = bhk * random.uniform(120, 280)

    ppsf = base_ppsf * np.random.normal(1.0, 0.12)
    # inject per-location price spike outliers (~1.5%)
    if random.random() < 0.015:
        ppsf *= random.choice([2.6, 3.2, 0.28])

    price_inr = ppsf * sqft
    price_lakhs = round(price_inr / 100000, 2)

    bath = bhk + random.choice([-1, 0, 0, 0, 1])
    bath = max(1, bath)
    # inject bath >> bhk outliers (~1%)
    if random.random() < 0.01:
        bath = bhk + random.randint(3, 6)
    bath_val = bath if random.random() > 0.03 else np.nan

    balcony_val = random.choice([0, 1, 1, 2, 2, 3]) if random.random() > 0.1 else np.nan

    rows.append({
        "area_type": np.random.choice(AREA_TYPES, p=AREA_TYPE_WEIGHTS),
        "availability": "Ready To Move" if random.random() < 0.75 else random.choice(AVAILABILITY_DATES),
        "location": loc if random.random() > 0.01 else "",  # a few blank locations, dropped later
        "size": make_size(bhk) if random.random() > 0.01 else np.nan,
        "society": make_society(),
        "total_sqft": make_total_sqft(sqft),
        "bath": bath_val,
        "balcony": balcony_val,
        "price": price_lakhs,
    })

df = pd.DataFrame(rows)
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(OUT_PATH, index=False)
print(f"Wrote {len(df)} rows to {OUT_PATH}")
print(f"Unique locations: {df['location'].nunique()}")
