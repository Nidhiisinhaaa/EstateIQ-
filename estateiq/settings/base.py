"""
Settings shared by every environment. dev.py and prod.py both import * from this module and
override only what needs to differ.

Real Estate Price Intelligence and Prediction System Using Machine Learning and Django.
SQLite3 only -- no external database server is used anywhere in this project.
"""

from pathlib import Path
import os

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get(
    "SECRET_KEY", "django-insecure-dev-key-change-me-in-production-0000000000"
)

ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()
]

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
    "properties",
    "predictor",
    "analytics",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.ContentSecurityPolicyMiddleware",
]

ROOT_URLCONF = "estateiq.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.site_meta",
            ],
        },
    },
]

WSGI_APPLICATION = "estateiq.wsgi.application"
ASGI_APPLICATION = "estateiq.asgi.application"

# ---------------------------------------------------------------------------
# Database -- SQLite3 only
# ---------------------------------------------------------------------------

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "account:login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static and media files
# ---------------------------------------------------------------------------

STATIC_URL = "static/"
STATICFILES_DIRS = [
    BASE_DIR / "static",
    ("ml-artifacts", BASE_DIR / "ml_pipeline" / "artifacts" / "eda"),
]
STATIC_ROOT = BASE_DIR / "staticfiles"
WHITENOISE_USE_FINDERS = True

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# EstateIQ / ML pipeline paths
# ---------------------------------------------------------------------------

ML_PIPELINE_DIR = BASE_DIR / "ml_pipeline"
ML_ARTIFACTS_DIR = ML_PIPELINE_DIR / "artifacts"
ML_DATA_RAW_DIR = ML_PIPELINE_DIR / "data" / "raw"
ML_DATA_PROCESSED_DIR = ML_PIPELINE_DIR / "data" / "processed"

SITE_NAME = "EstateIQ"
SITE_TAGLINE = "Real Estate Price Intelligence and Prediction"

# ---------------------------------------------------------------------------
# Caching (local-memory cache used by analytics aggregates and rate limiting)
# ---------------------------------------------------------------------------

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "estateiq-locmem",
    }
}

# ---------------------------------------------------------------------------
# Baseline security headers applied in every environment. SSL/HSTS/secure-cookie
# settings are environment-specific and live in dev.py / prod.py.
# ---------------------------------------------------------------------------

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# CDNs the Content-Security-Policy middleware (core/middleware.py) must allow --
# every external host actually referenced by a template, kept in one place so the
# CSP can't silently drift from what the app really loads.
CSP_ALLOWED_SCRIPT_HOSTS = [
    "https://cdn.tailwindcss.com",
    "https://cdn.jsdelivr.net",
    "https://unpkg.com",
]
CSP_ALLOWED_STYLE_HOSTS = [
    "https://fonts.googleapis.com",
    "https://unpkg.com",
]
CSP_ALLOWED_FONT_HOSTS = [
    "https://fonts.gstatic.com",
]
CSP_ALLOWED_IMG_HOSTS = [
    "https://*.basemaps.cartocdn.com",
    "https://*.tile.openstreetmap.org",
    "https://unpkg.com",
]
CSP_ALLOWED_CONNECT_HOSTS = [
    "https://*.basemaps.cartocdn.com",
]

RATE_LIMIT_PREDICT_MAX = 30
RATE_LIMIT_PREDICT_WINDOW_SECONDS = 60 * 60
