"""
Tenants API views.

POST /api/webhooks/register/ — Register or update a webhook URL for the tenant
                               associated with the authenticated JWT token.
"""

import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import WebhookRegisterSerializer

logger = logging.getLogger(__name__)


class WebhookRegisterView(APIView):
    """
    POST /api/webhooks/register/

    Body: { "webhook_url": "https://your-server.com/prahari-hook" }

    Saves the webhook URL against the tenant.  Prahari will POST incident
    update payloads to this URL whenever a new Incident is finalised.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = WebhookRegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # TODO: resolve tenant from JWT claim and persist webhook_url
        # tenant_id = request.auth.get("tenant_id")
        # tenant = get_object_or_404(Tenant, id=tenant_id, is_active=True)
        # tenant.webhook_url = serializer.validated_data["webhook_url"]
        # tenant.save(update_fields=["webhook_url"])
        # return Response(TenantSerializer(tenant).data, status=status.HTTP_200_OK)

        logger.info("Webhook register endpoint hit — tenant wiring pending.")
        return Response(
            {"detail": "Webhook registration scaffold — tenant JWT wiring pending."},
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )
