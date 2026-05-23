"""
Incident API views.

GET /api/incidents/       — Paginated list of incidents for the requesting tenant.
GET /api/incidents/<id>/  — Full incident detail including agent outputs.

Tenant filtering:
    Queries are scoped to the tenant associated with the JWT token.
    The FK join goes: JWT → tenant_id → Signal → Incident.
"""

import logging

from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Incident
from .serializers import IncidentDetailSerializer, IncidentListSerializer

logger = logging.getLogger(__name__)


class IncidentListView(ListAPIView):
    """
    GET /api/incidents/

    Returns a paginated list of incidents belonging to the requesting tenant,
    ordered by creation date (newest first).
    """

    permission_classes = [IsAuthenticated]
    serializer_class = IncidentListSerializer

    def get_queryset(self):
        # TODO: filter by tenant once JWT claim wiring is in place
        # tenant_id = self.request.auth.get("tenant_id")
        # return Incident.objects.filter(signal__tenant_id=tenant_id).select_related("signal")
        logger.warning("Tenant filtering not yet wired — returning all incidents.")
        return Incident.objects.select_related("signal").all()


class IncidentDetailView(RetrieveAPIView):
    """
    GET /api/incidents/<id>/

    Returns the full incident record including all agent outputs.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = IncidentDetailSerializer
    lookup_field = "id"

    def get_queryset(self):
        # TODO: scope to tenant
        return Incident.objects.select_related("signal").all()
