"""
WebSocket URL routing for Prahari pipeline.
Imported by config/asgi.py.
"""

from django.urls import re_path
from .consumers import DashboardConsumer

websocket_urlpatterns = [
    # Dashboard stream — optionally scoped to a tenant via URL param
    re_path(r"^ws/dashboard/$", DashboardConsumer.as_asgi()),
]
