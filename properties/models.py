from django.db import models
from django.utils.text import slugify


class Location(models.Model):
    TIER_CHOICES = [
        ("Premium", "Premium"),
        ("Mid", "Mid"),
        ("Budget", "Budget"),
    ]

    name = models.CharField(max_length=120, unique=True, db_index=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    tier = models.CharField(max_length=10, choices=TIER_CHOICES, default="Mid", db_index=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    is_approximate = models.BooleanField(
        default=False, help_text="True when lat/lng fell back to the city centroid at geocode time."
    )
    listing_count = models.PositiveIntegerField(default=0)
    median_price_per_sqft = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Amenity(models.Model):
    name = models.CharField(max_length=60, unique=True)
    icon_key = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Amenities"

    def __str__(self):
        return self.name


class Property(models.Model):
    FURNISHING_CHOICES = [
        ("Unfurnished", "Unfurnished"),
        ("Semi", "Semi"),
        ("Full", "Full"),
    ]
    PROPERTY_TYPE_CHOICES = [
        ("Apartment", "Apartment"),
        ("Villa", "Villa"),
        ("Independent House", "Independent House"),
        ("Plot", "Plot"),
    ]
    SOURCE_CHOICES = [
        ("Dataset", "Dataset"),
        ("Manual", "Manual"),
    ]

    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="properties")
    area_sqft = models.FloatField()
    bhk = models.PositiveSmallIntegerField()
    bathrooms = models.PositiveSmallIntegerField()
    balcony = models.PositiveSmallIntegerField(default=0)
    floor = models.PositiveSmallIntegerField(null=True, blank=True)
    total_floors = models.PositiveSmallIntegerField(null=True, blank=True)
    age_years = models.PositiveSmallIntegerField(default=0)
    parking = models.BooleanField(default=False)
    furnishing = models.CharField(max_length=12, choices=FURNISHING_CHOICES, default="Unfurnished")
    property_type = models.CharField(max_length=24, choices=PROPERTY_TYPE_CHOICES, default="Apartment", db_index=True)
    amenities = models.JSONField(default=list, blank=True)
    price_inr = models.DecimalField(max_digits=14, decimal_places=2)
    price_per_sqft = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    listed_on = models.DateField()
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default="Dataset", db_index=True)

    class Meta:
        ordering = ["-listed_on"]
        indexes = [
            models.Index(fields=["location", "bhk"]),
            models.Index(fields=["source"]),
        ]
        verbose_name_plural = "Properties"

    def __str__(self):
        return f"{self.location.name} -- {self.bhk} BHK ({self.area_sqft:.0f} sqft)"

    def save(self, *args, **kwargs):
        if self.area_sqft:
            self.price_per_sqft = round(float(self.price_inr) / float(self.area_sqft), 2)
        super().save(*args, **kwargs)
