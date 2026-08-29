"""Verifies every named URL in the project resolves (reverse() succeeds)."""

import pytest
from django.urls import reverse

NAMED_URLS = [
    ("home", {}),
    ("predictor:predict", {}),
    ("predictor:result", {"pk": 1}),
    ("predictor:model_report", {}),
    ("predictor:export_csv", {}),
    ("predictor:retrain", {}),
    ("predictor:retrain_status", {"pk": 1}),
    ("analytics:dashboard", {}),
    ("analytics:map", {}),
    ("analytics:geojson_locations", {}),
    ("analytics:chart_api", {"slug": "bhk-price-distribution"}),
    ("account:login", {}),
    ("account:logout", {}),
    ("account:signup", {}),
    ("account:password_change", {}),
    ("account:password_change_done", {}),
    ("account:history", {}),
    ("account:history_delete", {"pk": 1}),
    ("account:history_clear", {}),
    ("account:compare", {}),
    ("account:export_prediction_pdf", {"pk": 1}),
    ("account:export_history_csv", {}),
    ("admin:index", {}),
]


@pytest.mark.parametrize("name,kwargs", NAMED_URLS, ids=[n for n, _ in NAMED_URLS])
def test_named_url_resolves(name, kwargs):
    assert reverse(name, kwargs=kwargs)
