from django.urls import path

from . import views

app_name = "analytics"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("map/", views.map_view, name="map"),
    path("api/geo/", views.geojson_locations, name="geojson_locations"),
    path("api/<slug:slug>/", views.chart_api, name="chart_api"),
]
