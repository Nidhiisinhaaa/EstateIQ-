"""Verifies analytics aggregate functions return the expected shape on a small fixture."""

import datetime

import pytest

from analytics.services import aggregates
from properties.models import Amenity, Location, Property


@pytest.fixture
def small_dataset(db):
    premium = Location.objects.create(name="Premium Loc", tier="Premium")
    budget = Location.objects.create(name="Budget Loc", tier="Budget")

    Property.objects.create(
        location=premium, area_sqft=1000, bhk=2, bathrooms=2, balcony=1,
        price_inr=10_000_000, listed_on=datetime.date.today(), source="Manual",
        furnishing="Full", property_type="Apartment", amenities=["Gym"],
    )
    Property.objects.create(
        location=budget, area_sqft=1200, bhk=3, bathrooms=2, balcony=1,
        price_inr=6_000_000, listed_on=datetime.date.today(), source="Manual",
        furnishing="Unfurnished", property_type="Apartment", amenities=[],
    )
    Amenity.objects.get_or_create(name="Gym", defaults={"icon_key": "dumbbell"})
    return {"premium": premium, "budget": budget}


@pytest.mark.django_db
def test_headline_stats_shape(small_dataset):
    stats = aggregates.headline_stats()
    assert set(stats.keys()) == {
        "total_listings", "locations_covered", "median_price", "median_price_per_sqft", "predictions_served",
    }
    assert stats["total_listings"] == 2
    assert stats["locations_covered"] == 2


@pytest.mark.django_db
def test_bhk_price_distribution_shape(small_dataset):
    rows = aggregates.bhk_price_distribution()
    assert len(rows) == 2
    for row in rows:
        assert set(row.keys()) == {"bhk", "average_price", "count"}


@pytest.mark.django_db
def test_average_price_by_location_shape(small_dataset):
    rows = aggregates.average_price_by_location(limit=5)
    assert len(rows) == 2
    for row in rows:
        assert set(row.keys()) == {"location", "average_price", "count"}


@pytest.mark.django_db
def test_property_type_distribution_shape(small_dataset):
    rows = aggregates.property_type_distribution()
    assert rows
    for row in rows:
        assert set(row.keys()) == {"property_type", "count", "share"}


@pytest.mark.django_db
def test_tier_price_comparison_shape(small_dataset):
    rows = aggregates.tier_price_comparison()
    tiers = {row["tier"] for row in rows}
    assert tiers == {"Premium", "Mid", "Budget"}
    for row in rows:
        assert set(row.keys()) == {"tier", "median_price_per_sqft", "count"}
