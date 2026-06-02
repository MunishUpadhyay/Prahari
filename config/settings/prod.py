import os
from .base import *

DEBUG = False

SECRET_KEY = os.environ.get('SECRET_KEY')

ALLOWED_HOSTS = os.environ.get(
    'ALLOWED_HOSTS', '').split(',')

# Database — use DATABASE_URL from environment
import dj_database_url
DATABASES = {
    'default': dj_database_url.config(
        conn_max_age=600,
        ssl_require=True
    )
}

# Set engine to PostGIS if GDAL is available, fallback to plain postgresql
GDAL_AVAILABLE = True
try:
    from django.contrib.gis.gdal import HAS_GDAL
    if HAS_GDAL:
        DATABASES['default']['ENGINE'] = 'django.contrib.gis.db.backends.postgis'
    else:
        DATABASES['default']['ENGINE'] = 'django.db.backends.postgresql'
        GDAL_AVAILABLE = False
except Exception:
    DATABASES['default']['ENGINE'] = 'django.db.backends.postgresql'
    GDAL_AVAILABLE = False

if not GDAL_AVAILABLE:
    if "django.contrib.gis" in INSTALLED_APPS:
        INSTALLED_APPS.remove("django.contrib.gis")

# Redis
REDIS_URL = os.environ.get(
    'REDIS_URL', 'redis://localhost:6379/0')

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {'hosts': [REDIS_URL]},
    }
}

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL

# Static files with WhiteNoise
MIDDLEWARE = [
    'whitenoise.middleware.WhiteNoiseMiddleware',
] + MIDDLEWARE

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = (
    'whitenoise.storage'
    '.CompressedManifestStaticFilesStorage'
)

# Security
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = (
    'HTTP_X_FORWARDED_PROTO', 'https')

# CORS — update after deployment with real URL
CORS_ALLOWED_ORIGINS = os.environ.get(
    'CORS_ALLOWED_ORIGINS', '').split(',')

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
}
