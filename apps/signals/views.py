"""
Signal API views.

POST /api/signals/ — Ingest a new signal.
"""

import logging
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.generics import CreateAPIView

from .serializers import SignalIngestSerializer
from pipeline.tasks import ingest_signal

logger = logging.getLogger(__name__)


class SignalIngestView(CreateAPIView):
    """
    POST /api/signals/

    Accepts text, image, or webhook payloads and creates a Signal record.
    Immediately enqueues the Celery processing pipeline.
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    serializer_class = SignalIngestSerializer

    def perform_create(self, serializer):
        # Resolve tenant from request.tenant if present (for future compatibility)
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            # Fallback to get first active tenant or create a default one for development
            from apps.tenants.models import Tenant
            tenant = Tenant.objects.filter(is_active=True).first()
            if not tenant:
                tenant, _ = Tenant.objects.get_or_create(
                    name="Default Tenant",
                    defaults={"api_key_hash": Tenant.hash_api_key("default_key")}
                )
        
        signal = serializer.save(tenant=tenant)
        logger.info("Signal ingested successfully, enqueuing pipeline task for ID: %s", signal.id)
        ingest_signal.delay(str(signal.id))
