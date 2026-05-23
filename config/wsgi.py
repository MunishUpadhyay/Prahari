"""
WSGI config for Prahari.
Used by traditional WSGI servers (gunicorn) for HTTP-only deployments.
For full WebSocket support, use asgi.py with uvicorn/daphne.
"""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

application = get_wsgi_application()
