"""Verifies PredictionForm rejects the out-of-range inputs the spec calls out explicitly."""

import pytest

from predictor.forms import PredictionForm
from properties.models import Location


@pytest.fixture
def location(db):
    return Location.objects.create(name="Test Location", tier="Mid")


@pytest.mark.django_db
def test_area_sqft_below_minimum_rejected(location):
    form = PredictionForm(data={
        "location": location.name, "area_sqft": 150, "bhk": 2, "bathrooms": 2,
        "furnishing": "Unfurnished", "property_type": "Apartment",
    })
    assert not form.is_valid()
    assert "area_sqft" in form.errors


@pytest.mark.django_db
def test_area_sqft_above_maximum_rejected(location):
    form = PredictionForm(data={
        "location": location.name, "area_sqft": 15000, "bhk": 2, "bathrooms": 2,
        "furnishing": "Unfurnished", "property_type": "Apartment",
    })
    assert not form.is_valid()
    assert "area_sqft" in form.errors


@pytest.mark.django_db
def test_bhk_out_of_range_rejected(location):
    form = PredictionForm(data={
        "location": location.name, "area_sqft": 1000, "bhk": 11, "bathrooms": 2,
        "furnishing": "Unfurnished", "property_type": "Apartment",
    })
    assert not form.is_valid()
    assert "bhk" in form.errors


@pytest.mark.django_db
def test_bathrooms_out_of_range_rejected(location):
    form = PredictionForm(data={
        "location": location.name, "area_sqft": 1000, "bhk": 2, "bathrooms": 13,
        "furnishing": "Unfurnished", "property_type": "Apartment",
    })
    assert not form.is_valid()
    assert "bathrooms" in form.errors


@pytest.mark.django_db
def test_age_years_out_of_range_rejected(location):
    form = PredictionForm(data={
        "location": location.name, "area_sqft": 1000, "bhk": 2, "bathrooms": 2, "age_years": 61,
        "furnishing": "Unfurnished", "property_type": "Apartment",
    })
    assert not form.is_valid()
    assert "age_years" in form.errors


@pytest.mark.django_db
def test_floor_exceeding_total_floors_rejected(location):
    form = PredictionForm(data={
        "location": location.name, "area_sqft": 1000, "bhk": 2, "bathrooms": 2,
        "floor": 10, "total_floors": 5,
        "furnishing": "Unfurnished", "property_type": "Apartment",
    })
    assert not form.is_valid()
    assert "floor" in form.errors


@pytest.mark.django_db
def test_valid_form_within_range_accepted(location):
    form = PredictionForm(data={
        "location": location.name, "area_sqft": 1000, "bhk": 2, "bathrooms": 2,
        "floor": 3, "total_floors": 10, "age_years": 5,
        "furnishing": "Unfurnished", "property_type": "Apartment",
    })
    assert form.is_valid(), form.errors
