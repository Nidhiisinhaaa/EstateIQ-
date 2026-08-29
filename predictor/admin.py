from django.contrib import admin

from .models import ModelMetric, PredictionLog, RetrainJob


class ReadOnlyAdminMixin:
    """Shared by PredictionLog and ModelMetric: both are system-generated records, not
    hand-edited data, so admin should only ever list/view them, never add or change them."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields]


@admin.register(PredictionLog)
class PredictionLogAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = [
        "id", "location_name", "bhk", "area_sqft", "predicted_price",
        "confidence_score", "model_name", "user", "created_at",
    ]
    list_filter = ["model_name", "property_type", "furnishing"]
    search_fields = ["location_name", "user__username", "ip_address"]
    date_hierarchy = "created_at"


@admin.register(ModelMetric)
class ModelMetricAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ["model_name", "mae", "rmse", "r2", "mape", "cv_r2_mean", "is_best", "trained_at"]
    list_filter = ["is_best"]
    search_fields = ["model_name"]


@admin.register(RetrainJob)
class RetrainJobAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ["id", "status", "triggered_by", "started_at", "finished_at", "created_at"]
    list_filter = ["status"]
