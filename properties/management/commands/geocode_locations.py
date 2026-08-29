"""
Populates Location.latitude/longitude from the bundled static coordinate lookup
(properties/fixtures/location_coords.json). No live geocoding API calls.

Locations not present in the lookup fall back to the city centroid, flagged is_approximate=True
so the Phase 7 map can render them with a distinct hollow-ring marker. A small deterministic
offset (derived from a hash of the location name) is applied to the fallback so approximate
markers do not all stack exactly on top of one another.
"""

import hashlib
import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from properties.models import Location

FIXTURE_PATH = settings.BASE_DIR / "properties" / "fixtures" / "location_coords.json"
JITTER_DEGREES = 0.03  # roughly +/- 3km at this latitude, enough to visually separate markers


def _deterministic_jitter(name: str) -> tuple[float, float]:
    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()
    lat_frac = (int(digest[:8], 16) / 0xFFFFFFFF) * 2 - 1
    lng_frac = (int(digest[8:16], 16) / 0xFFFFFFFF) * 2 - 1
    return lat_frac * JITTER_DEGREES, lng_frac * JITTER_DEGREES


class Command(BaseCommand):
    help = "Populate Location lat/lng from the bundled static coordinate lookup (no live API calls)."

    def handle(self, *args, **options):
        if not FIXTURE_PATH.exists():
            raise CommandError(f"{FIXTURE_PATH} not found")

        with open(FIXTURE_PATH) as f:
            fixture = json.load(f)

        centroid = fixture["city_centroid"]
        coords_by_name = fixture["locations"]

        matched, approximated = 0, 0
        for loc in Location.objects.all():
            entry = coords_by_name.get(loc.name)
            if entry:
                loc.latitude = entry["latitude"]
                loc.longitude = entry["longitude"]
                loc.is_approximate = False
                matched += 1
            else:
                dlat, dlng = _deterministic_jitter(loc.name)
                loc.latitude = centroid["latitude"] + dlat
                loc.longitude = centroid["longitude"] + dlng
                loc.is_approximate = True
                approximated += 1
            loc.save(update_fields=["latitude", "longitude", "is_approximate"])

        self.stdout.write(self.style.SUCCESS(
            f"Geocoded {matched + approximated} locations "
            f"({matched} matched exactly, {approximated} approximated to city centroid)"
        ))
