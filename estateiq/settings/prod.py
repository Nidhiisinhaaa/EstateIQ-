"""
Production settings, intended for the Hostinger VPS deployment (see deploy/DEPLOY.md).
Set DJANGO_SETTINGS_MODULE=estateiq.settings.prod in the environment (systemd unit / gunicorn).
"""

import os

from .base import *  # noqa: F401,F403

# Hardcoded rather than env-driven on purpose: a missing/misspelled DEBUG env var in production
# must never silently re-enable the debugger and stack traces.
DEBUG = False

if not ALLOWED_HOSTS or ALLOWED_HOSTS == ["localhost", "127.0.0.1"]:  # noqa: F405
    raise RuntimeError(
        "ALLOWED_HOSTS must be set via the environment in production (see deploy/DEPLOY.md)."
    )

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
