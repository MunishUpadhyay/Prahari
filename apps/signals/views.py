"""
Signal API views.

POST /api/signals/ — Ingest a new signal.
"""

import logging
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
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


from rest_framework.authentication import SessionAuthentication
import hashlib
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import Signal

from .citizen_views import resolve_signal

from django.core.cache import cache

@method_decorator(rate_limit_ip(limit=10, period=60, key_prefix="verify_ip"), name="dispatch")
class SignalVerifyCodeView(APIView):
    """
    POST /api/signals/<signal_id>/verify-code/
    Body: {"code": "XK7P2M"}
    Response: {"valid": true} or {"valid": false, "locked": bool, "message": str}
    """
    authentication_classes = [SessionAuthentication]
    permission_classes = []  # Public endpoint

    def post(self, request, signal_id):
        signal = resolve_signal(signal_id)
        
        lock_key = f"verify_lock_{signal.id}"
        failed_key = f"verify_failed_attempts_{signal.id}"
        
        # Check if report is locked due to brute-force attempts
        if cache.get(lock_key):
            return Response({
                "valid": False,
                "locked": True,
                "message": "Too many failed attempts. Verification for this report is locked for 15 minutes. / बहुत अधिक असफल प्रयास। यह रिपोर्ट 15 मिनट के लिए लॉक है।"
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        code = request.data.get("code", "").strip().upper()
        
        stored_hash = signal.metadata.get("anonymous_code") if signal.metadata else None
        if not stored_hash:
            # Not an anonymous signal, or code not set
            return Response({"valid": False, "message": "Report is not an anonymous signal."}, status=status.HTTP_200_OK)
            
        # Hash the entered code
        entered_hash = hashlib.sha256(code.encode()).hexdigest()
        
        if entered_hash == stored_hash:
            # Clear failed attempts counter upon successful verification
            cache.delete(failed_key)
            request.session[f"verified_{signal.id}"] = True
            return Response({"valid": True}, status=status.HTTP_200_OK)
        else:
            attempts = cache.get(failed_key, 0) + 1
            if attempts >= 5:
                # Lock for 15 minutes (900 seconds)
                cache.set(lock_key, True, timeout=900)
                cache.delete(failed_key)
                return Response({
                    "valid": False,
                    "locked": True,
                    "message": "Too many failed attempts. Verification for this report is locked for 15 minutes. / बहुत अधिक असफल प्रयास। यह रिपोर्ट 15 मिनट के लिए लॉक है।"
                }, status=status.HTTP_429_TOO_MANY_REQUESTS)
            else:
                cache.set(failed_key, attempts, timeout=900)
                return Response({
                    "valid": False,
                    "locked": False,
                    "attempts_remaining": 5 - attempts,
                    "message": f"Invalid Return Key. {5 - attempts} attempts remaining. / अमान्य रिटर्न कुंजी। {5 - attempts} प्रयास शेष हैं।"
                }, status=status.HTTP_200_OK)


@method_decorator(rate_limit_ip(limit=10, period=60, key_prefix="close_session"), name="dispatch")
class SignalCloseSessionView(APIView):
    """
    POST /api/signals/<signal_id>/close-session/
    
    Citizen session operation to close/invalidate the verification session.
    Removes only verified_<signal_id> from the session store.
    """
    authentication_classes = [SessionAuthentication]
    permission_classes = []  # Public endpoint

    def post(self, request, signal_id):
        from rest_framework.authentication import CSRFCheck
        from rest_framework.exceptions import PermissionDenied
        
        reason = CSRFCheck(lambda req: None).process_view(request._request, None, (), {})
        if reason:
            raise PermissionDenied(f"CSRF Failed: {reason}")

        signal = resolve_signal(signal_id)
        
        session_key = f"verified_{signal.id}"
        if session_key in request.session:
            del request.session[session_key]
            request.session.modified = True
            return Response({"status": "success", "message": "Session closed successfully."}, status=status.HTTP_200_OK)
            
        return Response({"status": "success", "message": "Session already closed or not found."}, status=status.HTTP_200_OK)

