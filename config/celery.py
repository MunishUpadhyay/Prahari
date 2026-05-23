"""
Celery application factory for Prahari.
Import this module in __init__.py so that @shared_task decorators work.
"""

import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("prahari")

# Use Django settings with the CELERY_ prefix
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in all INSTALLED_APPS
app.autodiscover_tasks()
