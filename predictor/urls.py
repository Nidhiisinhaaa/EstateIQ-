from django.urls import path

from . import views

app_name = "predictor"

urlpatterns = [
    path("", views.predict, name="predict"),
    path("result/<int:pk>/", views.result, name="result"),
    path("model-report/", views.model_report, name="model_report"),
    path("model-report/export/", views.export_model_comparison_csv, name="export_csv"),
    path("retrain/", views.retrain, name="retrain"),
    path("retrain/<int:pk>/status/", views.retrain_status, name="retrain_status"),
]
