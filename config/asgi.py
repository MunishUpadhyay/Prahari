"""
ASGI config for Prahari.

Supports both HTTP (Django) and WebSocket (Channels) protocols
via ProtocolTypeRouter.
"""

import os
import django
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

# Must call setup() before importing anything that uses the ORM
django.setup()

from pipeline.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        # Standard Django HTTP
        "http": get_asgi_application(),
        # WebSocket with JWT-aware auth stack
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(
                URLRouter(websocket_urlpatterns)
            )
        ),
    }
)
