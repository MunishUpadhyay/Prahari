"""
dev_nogis.py — Local development settings WITHOUT GDAL/PostGIS.

Use this settings file when GDAL native libraries are NOT installed
on the local machine (common on Windows dev environments).

What changes:
    - DB backend → standard django.db.backends.postgresql (no GIS)
    - GeoDjango (django.contrib.gis) removed from INSTALLED_APPS
    - PointField models will NOT be available — use this only for
      checking/migrating non-geo apps and running tests.

Usage:
    set DJANGO_SETTINGS_MODULE=config.settings.dev_nogis
    python manage.py check
    python manage.py makemigrations
    python manage.py migrate

For full GIS support in production use the PostGIS docker container
and the standard dev.py / prod.py settings with GDAL installed.
"""

from .dev import *  # noqa: F401, F403

# ---- Swap to non-GIS PostgreSQL backend ----
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "prahari",
        "USER": "prahari_user",
        "PASSWORD": "prahari_pass",
        "HOST": "localhost",
        "PORT": "5432",
    }
}

# ---- Remove GeoDjango from INSTALLED_APPS ----
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != "django.contrib.gis"]
