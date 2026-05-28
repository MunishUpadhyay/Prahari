"""
Signal API views.

POST /api/signals/ — Ingest a new signal.
"""

import logging
from django.utils.decorators import method_decorator
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.generics import CreateAPIView

from .serializers import SignalIngestSerializer
from .utils import rate_limit_ip
from pipeline.tasks import ingest_signal

logger = logging.getLogger(__name__)


@method_decorator(rate_limit_ip(limit=10, period=3600), name="dispatch")
class SignalIngestView(CreateAPIView):
    """
    POST /api/signals/

    Accepts text, image, or webhook payloads and creates a Signal record.
    Immediately enqueues the Celery processing pipeline.
    
    JWT authentication is applied if Authorization header is present.
    Otherwise, rate-limited public citizen submissions are allowed.
    """
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    serializer_class = SignalIngestSerializer

    def get_permissions(self):
        # Enforce JWT auth only if Authorization header is present
        if self.request.META.get("HTTP_AUTHORIZATION") or self.request.headers.get("Authorization"):
            return [IsAuthenticated()]
        return []

    def perform_create(self, serializer):
        # Resolve tenant from request.tenant if present
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


import hashlib
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import Signal

class SignalVerifyCodeView(APIView):
    """
    POST /api/signals/<signal_id>/verify-code/
    Body: {"code": "XK7P2M"}
    Response: {"valid": true} or {"valid": false}
    """
    permission_classes = []  # Public endpoint

    def post(self, request, signal_id):
        signal = get_object_or_404(Signal, id=signal_id)
        code = request.data.get("code", "").strip().upper()
        
        stored_hash = signal.metadata.get("anonymous_code") if signal.metadata else None
        if not stored_hash:
            # Not an anonymous signal, or code not set
            return Response({"valid": False}, status=status.HTTP_200_OK)
            
        # Hash the entered code
        entered_hash = hashlib.sha256(code.encode()).hexdigest()
        
        if entered_hash == stored_hash:
            return Response({"valid": True}, status=status.HTTP_200_OK)
        else:
            return Response({"valid": False}, status=status.HTTP_200_OK)

