"""Local development settings. Used by manage.py by default."""

import os

from .base import *  # noqa: F401,F403

DEBUG = os.environ.get("DEBUG", "True") == "True"  # noqa: F405

# No HTTPS locally -- these must stay off or `runserver` becomes unusable over plain http.
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0
