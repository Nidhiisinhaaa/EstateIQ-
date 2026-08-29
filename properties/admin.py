from django.contrib import admin

from .models import Amenity, Location, Property


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ["name", "tier", "listing_count", "median_price_per_sqft", "latitude", "longitude", "is_approximate"]
    list_filter = ["tier", "is_approximate"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ["name"]}


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = [
        "id", "location", "bhk", "area_sqft", "price_inr", "price_per_sqft",
        "property_type", "furnishing", "source", "listed_on",
    ]
    list_filter = ["property_type", "furnishing", "source", "parking", "location__tier"]
    search_fields = ["location__name"]
    autocomplete_fields = ["location"]


@admin.register(Amenity)
class AmenityAdmin(admin.ModelAdmin):
    list_display = ["name", "icon_key"]
    search_fields = ["name"]
