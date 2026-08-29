from django import forms

from properties.models import Amenity, Location, Property


class PredictionForm(forms.Form):
    location = forms.ModelChoiceField(
        queryset=Location.objects.order_by("name"),
        to_field_name="name",
        widget=forms.Select(attrs={"class": "bp-input"}),
    )
    area_sqft = forms.FloatField(
        min_value=200, max_value=10000,
        widget=forms.NumberInput(attrs={"class": "bp-input", "step": "1"}),
    )
    bhk = forms.IntegerField(
        min_value=1, max_value=10, initial=2,
        widget=forms.NumberInput(attrs={"class": "bp-input"}),
    )
    bathrooms = forms.IntegerField(
        min_value=1, max_value=12, initial=2,
        widget=forms.NumberInput(attrs={"class": "bp-input"}),
    )
    balcony = forms.IntegerField(
        min_value=0, max_value=10, initial=1, required=False,
        widget=forms.NumberInput(attrs={"class": "bp-input"}),
    )
    floor = forms.IntegerField(
        min_value=0, max_value=200, required=False,
        widget=forms.NumberInput(attrs={"class": "bp-input"}),
    )
    total_floors = forms.IntegerField(
        min_value=1, max_value=200, required=False,
        widget=forms.NumberInput(attrs={"class": "bp-input"}),
    )
    age_years = forms.IntegerField(
        min_value=0, max_value=60, initial=0, required=False,
        widget=forms.NumberInput(attrs={"class": "bp-input"}),
    )
    parking = forms.BooleanField(required=False)
    furnishing = forms.ChoiceField(
        choices=Property.FURNISHING_CHOICES,
        widget=forms.Select(attrs={"class": "bp-input"}),
    )
    property_type = forms.ChoiceField(
        choices=Property.PROPERTY_TYPE_CHOICES,
        widget=forms.Select(attrs={"class": "bp-input"}),
    )
    amenities = forms.ModelMultipleChoiceField(
        queryset=Amenity.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    def clean(self):
        cleaned = super().clean()
        floor = cleaned.get("floor")
        total_floors = cleaned.get("total_floors")
        if floor is not None and total_floors is not None and floor > total_floors:
            self.add_error("floor", "Floor cannot exceed total floors.")
        return cleaned
