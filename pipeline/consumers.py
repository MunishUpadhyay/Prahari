"""
WebSocket consumers for Prahari.

ws://localhost:8000/ws/dashboard/

DashboardConsumer:
    - On connect: authenticates via JWT query param, joins tenant-scoped
      channel group `dashboard_<tenant_id>`.
    - On disconnect: leaves the group.
    - On receive: no-op (server-push only — clients do not send data).
    - Push path: Celery task push_to_websocket() calls
      channel_layer.group_send("dashboard_<tenant_id>", {...}) which
      triggers send_incident_update() on all connected clients.
"""

import json
import logging
from urllib.parse import parse_qs

from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken

from apps.tenants.models import Tenant

logger = logging.getLogger(__name__)


class DashboardConsumer(AsyncWebsocketConsumer):
    """
    Real-time incident update stream for a tenant's dashboard.

    Group naming: ``dashboard_<tenant_id>``

    Message schema sent to clients:
    {
        "type": "incident.update",
        "incident_id": "<uuid>",
        "severity_label": "high",
        "domain": "emergency",
        "situation_brief": "...",
        "is_resolved": false,
        "timestamp": "<iso8601>"
    }
    """

    async def connect(self):
        """
        Accept the WebSocket and subscribe to the tenant's dashboard group.
        Enforces JWT authentication and stopgap tenant resolution.
        """
        # Extract query parameters
        query_string = self.scope["query_string"].decode()
        query_params = parse_qs(query_string)
        token = query_params.get("token", [None])[0]
        client_tenant_id = query_params.get("tenant_id", [None])[0]

        # Token validation
        if not token:
            await self.close(code=4001)
            return
        try:
            access = AccessToken(token)
            user_id = access.get("user_id") or access["user_id"]
            User = get_user_model()
            user = await sync_to_async(User.objects.filter(id=user_id, is_active=True).first)()
            if not user:
                await self.close(code=4002)
                return
        except Exception:
            await self.close(code=4002)
            return

        # Resolve tenant server‑side (stopgap single active tenant)
        tenant = await sync_to_async(lambda: Tenant.objects.filter(is_active=True).order_by('id').first())()
        if not tenant:
            await self.close(code=4004)
            return
        tenant_id = str(tenant.id)

        # Verify client‑supplied tenant_id if present
        if client_tenant_id and client_tenant_id != tenant_id:
            await self.close(code=4003)
            return

        # Set tenant context and group name
        self.tenant_id = tenant_id
        self.group_name = f"dashboard_{self.tenant_id}"
        self.extra_group_names = []

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.info("WS connected: %s → group %s", self.channel_name, self.group_name)

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        if hasattr(self, 'extra_group_names'):
            for group in self.extra_group_names:
                await self.channel_layer.group_discard(group, self.channel_name)
        logger.info("WS disconnected: %s (code=%s)", self.channel_name, close_code)

    async def receive(self, text_data=None, bytes_data=None):
        """Server-push only — ignore all client messages."""
        pass

    # ------------------------------------------------------------------ #
    # Channel layer message handlers                                       #
    # ------------------------------------------------------------------ #

    async def incident_update(self, event):
        """
        Handles messages of type "incident.update" sent via channel layer.
        Forwards the payload directly to the WebSocket client.

        Called by: pipeline.tasks.push_to_websocket()
        """
        await self.send(text_data=json.dumps(event))

    async def dashboard_update(self, event):
        """
        Handles messages of type "dashboard.update" sent via channel layer.
        Forwards the message field directly to the WebSocket client.
        """
        await self.send(text_data=json.dumps(event['message']))
