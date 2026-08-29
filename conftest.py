import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def _clear_cache():
    """Analytics aggregates and the rate limiter both use the local-memory cache; without this,
    one test's cached results or rate-limit counters could leak into the next."""
    cache.clear()
    yield
    cache.clear()
