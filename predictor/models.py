from django.conf import settings
from django.db import models


class PredictionLog(models.Model):
    """
    Mirrors the PredictionForm inputs plus the engine's output, so a prediction can be
    replayed, exported, or compared later without recomputation.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="predictions"
    )
    session_key = models.CharField(
        max_length=40, blank=True, db_index=True,
        help_text="Set for anonymous users so their results survive a page refresh (Phase 9).",
    )

    location = models.ForeignKey(
        "properties.Location", on_delete=models.SET_NULL, null=True, blank=True, related_name="predictions"
    )
    location_name = models.CharField(max_length=120)

    area_sqft = models.FloatField()
    bhk = models.PositiveSmallIntegerField()
    bathrooms = models.PositiveSmallIntegerField()
    balcony = models.PositiveSmallIntegerField(default=0)
    floor = models.PositiveSmallIntegerField(null=True, blank=True)
    total_floors = models.PositiveSmallIntegerField(null=True, blank=True)
    age_years = models.PositiveSmallIntegerField(default=0)
    parking = models.BooleanField(default=False)
    furnishing = models.CharField(max_length=12, default="Unfurnished")
    property_type = models.CharField(max_length=24, default="Apartment")
    amenities = models.JSONField(default=list, blank=True)

    predicted_price = models.DecimalField(max_digits=14, decimal_places=2)
    lower_bound = models.DecimalField(max_digits=14, decimal_places=2)
    upper_bound = models.DecimalField(max_digits=14, decimal_places=2)
    confidence_score = models.FloatField()
    model_name = models.CharField(max_length=60)
    model_version = models.CharField(max_length=40, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["created_at"])]

    def __str__(self):
        return f"{self.location_name} -- {self.bhk} BHK -> {self.predicted_price}"


class RetrainJob(models.Model):
    STATUS_CHOICES = [
        ("queued", "Queued"),
        ("running", "Running"),
        ("success", "Success"),
        ("failed", "Failed"),
    ]

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="queued", db_index=True)
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="retrain_jobs"
    )
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    log_tail = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"RetrainJob #{self.pk} ({self.status})"


class ModelMetric(models.Model):
    model_name = models.CharField(max_length=60, unique=True)
    params = models.JSONField(default=dict, blank=True)
    mae = models.FloatField()
    rmse = models.FloatField()
    r2 = models.FloatField()
    mape = models.FloatField()
    cv_r2_mean = models.FloatField()
    cv_r2_std = models.FloatField(default=0)
    train_seconds = models.FloatField()
    is_best = models.BooleanField(default=False, db_index=True)
    trained_at = models.DateTimeField()

    class Meta:
        ordering = ["rmse"]

    def __str__(self):
        return self.model_name
