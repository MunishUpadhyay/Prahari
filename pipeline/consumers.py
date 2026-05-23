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

from channels.generic.websocket import AsyncWebsocketConsumer

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

        TODO: Extract and validate JWT from query string.
              query_string = self.scope["query_string"].decode()
              token = parse_qs(query_string).get("token", [None])[0]
              Validate token → resolve tenant_id.
        """
        # Placeholder: use "anonymous" group until JWT wiring is added
        self.tenant_id = self.scope.get("url_route", {}).get("kwargs", {}).get(
            "tenant_id", "anonymous"
        )
        self.group_name = f"dashboard_{self.tenant_id}"
        self.extra_group_names = []

        await self.channel_layer.group_add(self.group_name, self.channel_name)

        # Fallback: subscribe to the first active/existing tenant's group if anonymous
        if self.tenant_id == "anonymous":
            from apps.tenants.models import Tenant
            from asgiref.sync import sync_to_async
            
            @sync_to_async
            def get_first_tenant_id():
                tenant = Tenant.objects.first()
                return str(tenant.id) if tenant else None
            
            tenant_uuid = await get_first_tenant_id()
            if tenant_uuid:
                extra_group = f"dashboard_{tenant_uuid}"
                await self.channel_layer.group_add(extra_group, self.channel_name)
                self.extra_group_names.append(extra_group)

        await self.accept()
        logger.info("WS connected: %s → group %s (extra: %s)", self.channel_name, self.group_name, self.extra_group_names)

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
