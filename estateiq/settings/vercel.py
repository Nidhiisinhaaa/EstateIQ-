import os

from .base import *

DEBUG = False

ALLOWED_HOSTS = [".vercel.app", ".now.sh", "localhost", "127.0.0.1"]

CSRF_TRUSTED_ORIGINS = ["https://*.vercel.app"]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SECURE_SSL_REDIRECT = False

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
