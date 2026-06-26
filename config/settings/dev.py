"""
Development settings for Prahari.
Reads secrets from .env file via python-decouple.
"""

import os
from pathlib import Path
import environ

# Initialize environ
env = environ.Env()

# Load .env file if present
_env_file = Path(__file__).resolve().parent.parent.parent / ".env"
if _env_file.exists():
    environ.Env.read_env(_env_file)

from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = ["*"]

# Looser CORS for local dev
CORS_ALLOW_ALL_ORIGINS = True

# Django Debug Toolbar (optional; install separately if needed)
INTERNAL_IPS = ["127.0.0.1"]

# Simpler logging in dev
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "DEBUG",
    },
}

# GDAL availability check for local development
GDAL_AVAILABLE = True
try:
    from django.contrib.gis.gdal import HAS_GDAL
    if not HAS_GDAL:
        GDAL_AVAILABLE = False
except Exception:
    GDAL_AVAILABLE = False

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

if "django.contrib.gis" in INSTALLED_APPS:
    INSTALLED_APPS.remove("django.contrib.gis")

# Run Celery tasks asynchronously in development (via worker)
CELERY_TASK_ALWAYS_EAGER = False
CELERY_TASK_EAGER_PROPAGATES = True
