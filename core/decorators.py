"""Simple cache-based rate limiting. Uses cache.add + cache.incr for a fixed (non-sliding)
window, so a burst of requests can't keep resetting the window's expiry."""

from functools import wraps

from django.conf import settings
from django.core.cache import cache
from django.shortcuts import render


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def rate_limit_post(cache_key_prefix, max_requests=None, window_seconds=None):
    """Rate-limits only POST requests on the wrapped view, keyed by client IP."""
    max_requests = max_requests or settings.RATE_LIMIT_PREDICT_MAX
    window_seconds = window_seconds or settings.RATE_LIMIT_PREDICT_WINDOW_SECONDS

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if request.method == "POST":
                ip = _client_ip(request) or "unknown"
                cache_key = f"ratelimit:{cache_key_prefix}:{ip}"

                if cache.add(cache_key, 1, window_seconds):
                    count = 1
                else:
                    try:
                        count = cache.incr(cache_key)
                    except ValueError:
                        cache.set(cache_key, 1, window_seconds)
                        count = 1

                if count > max_requests:
                    return render(request, "429.html", status=429)

            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator
