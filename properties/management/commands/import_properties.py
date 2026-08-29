"""
Imports ml_pipeline/data/processed/properties_clean.csv into Location and Property rows.

Idempotent: every run first deletes existing source="Dataset" Property rows, then recreates them,
so re-running after a pipeline refresh never duplicates data.

The Phase 1 raw dataset does not carry floor/total_floors/age_years/parking/furnishing/
property_type/amenities/listed_on -- those attributes are synthesised here with a seeded random
generator (seeded per-row for determinism) so the Property table has enough realistic variety for
the Phase 6 analytics aggregates (amenity_price_impact, furnishing_price_impact, etc.) to be
meaningful rather than flat. property_type is grounded in the real `area_type` column where
possible (Plot Area -> Plot); everything else is otherwise-unmodelled auxiliary detail.
"""

import json
import random
from datetime import timedelta

import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from properties.models import Amenity, Location, Property

SEED = 42

AMENITIES = [
    ("Power Backup", "bolt"),
    ("Lift", "elevator"),
    ("Gym", "dumbbell"),
    ("Swimming Pool", "waves"),
    ("Clubhouse", "building"),
    ("Children's Play Area", "swing"),
    ("24x7 Security", "shield"),
    ("Park", "tree"),
    ("Rain Water Harvesting", "cloud-rain"),
    ("Vaastu Compliant", "compass"),
    ("Intercom", "phone"),
    ("Gas Pipeline", "flame"),
    ("Visitor Parking", "car"),
    ("Jogging Track", "footprints"),
    ("Indoor Games", "gamepad"),
]

FURNISHING_WEIGHTS = [("Unfurnished", 0.45), ("Semi", 0.35), ("Full", 0.20)]
PROPERTY_TYPE_WEIGHTS = [("Apartment", 0.80), ("Villa", 0.08), ("Independent House", 0.12)]

BATCH_SIZE = 1000


def _weighted_choice(rng: random.Random, weighted_options):
    labels = [o[0] for o in weighted_options]
    weights = [o[1] for o in weighted_options]
    return rng.choices(labels, weights=weights, k=1)[0]


def _load_location_tier_map():
    path = settings.ML_ARTIFACTS_DIR / "location_tier_map.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def _synthesize_property_fields(row_index: int, area_type: str):
    """Deterministic per-row synthesis for attributes absent from the raw dataset."""
    rng = random.Random(SEED + row_index)

    if isinstance(area_type, str) and "Plot" in area_type:
        property_type = "Plot"
    else:
        property_type = _weighted_choice(rng, PROPERTY_TYPE_WEIGHTS)

    if property_type == "Apartment":
        total_floors = rng.randint(3, 20)
        floor = rng.randint(0, total_floors)
    elif property_type in ("Villa", "Independent House"):
        total_floors = rng.randint(1, 3)
        floor = rng.randint(0, total_floors)
    else:  # Plot
        total_floors = None
        floor = None

    furnishing = "Unfurnished" if property_type == "Plot" else _weighted_choice(rng, FURNISHING_WEIGHTS)
    age_years = 0 if property_type == "Plot" else rng.randint(0, 25)
    parking = False if property_type == "Plot" else rng.random() < 0.65

    n_amenities = 0 if property_type == "Plot" else rng.randint(0, 6)
    amenities = rng.sample([a[0] for a in AMENITIES], k=n_amenities)

    days_ago = rng.randint(0, 3 * 365)
    listed_on = (timezone.now() - timedelta(days=days_ago)).date()

    return {
        "property_type": property_type,
        "floor": floor,
        "total_floors": total_floors,
        "furnishing": furnishing,
        "age_years": age_years,
        "parking": parking,
        "amenities": amenities,
        "listed_on": listed_on,
    }


class Command(BaseCommand):
    help = "Import the cleaned dataset (properties_clean.csv) into Location and Property rows."

    def handle(self, *args, **options):
        csv_path = settings.ML_DATA_PROCESSED_DIR / "properties_clean.csv"
        if not csv_path.exists():
            raise CommandError(
                f"{csv_path} not found. Run the ML pipeline first: "
                f"python ml_pipeline/run_pipeline.py --step all"
            )

        df = pd.read_csv(csv_path)
        tier_map = _load_location_tier_map()

        for name, icon_key in AMENITIES:
            Amenity.objects.get_or_create(name=name, defaults={"icon_key": icon_key})

        with transaction.atomic():
            deleted, _ = Property.objects.filter(source="Dataset").delete()
            self.stdout.write(f"Cleared {deleted} prior Dataset-sourced Property rows")

            loc_stats = df.groupby("location")["price_per_sqft"].agg(["count", "median"])
            location_objs = {}
            for name, stats in loc_stats.iterrows():
                tier = tier_map.get(name, "Mid")
                loc, _ = Location.objects.update_or_create(
                    name=name,
                    defaults={
                        "tier": tier,
                        "listing_count": int(stats["count"]),
                        "median_price_per_sqft": round(float(stats["median"]), 2),
                    },
                )
                location_objs[name] = loc
            self.stdout.write(f"Upserted {len(location_objs)} locations")

            batch = []
            total_created = 0
            for row_index, row in enumerate(df.itertuples(index=False)):
                extra = _synthesize_property_fields(row_index, getattr(row, "area_type", ""))
                batch.append(Property(
                    location=location_objs[row.location],
                    area_sqft=row.total_sqft,
                    bhk=int(row.bhk),
                    bathrooms=int(row.bath),
                    balcony=int(row.balcony),
                    floor=extra["floor"],
                    total_floors=extra["total_floors"],
                    age_years=extra["age_years"],
                    parking=extra["parking"],
                    furnishing=extra["furnishing"],
                    property_type=extra["property_type"],
                    amenities=extra["amenities"],
                    price_inr=round(float(row.price_inr), 2),
                    price_per_sqft=round(float(row.price_per_sqft), 2),
                    listed_on=extra["listed_on"],
                    source="Dataset",
                ))
                if len(batch) >= BATCH_SIZE:
                    Property.objects.bulk_create(batch)
                    total_created += len(batch)
                    batch = []
            if batch:
                Property.objects.bulk_create(batch)
                total_created += len(batch)

        self.stdout.write(self.style.SUCCESS(
            f"Imported {total_created} properties across {len(location_objs)} locations"
        ))
