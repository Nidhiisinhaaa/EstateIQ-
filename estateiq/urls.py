from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
    path("predictor/", include("predictor.urls")),
    path("analytics/", include("analytics.urls")),
    path("account/", include("core.auth_urls")),
]
