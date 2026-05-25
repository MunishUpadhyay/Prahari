import time
import logging
from functools import wraps
from django.core.cache import cache
from django.http import JsonResponse

logger = logging.getLogger(__name__)


def rate_limit_ip(limit=10, period=3600):
    """
    Decorator that rate-limits unauthenticated requests based on client IP.
    Authenticated API requests (containing Authorization headers) bypass this limit.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # Bypass rate limit if it's an authenticated API call
            if request.META.get("HTTP_AUTHORIZATION") or request.headers.get("Authorization"):
                return view_func(request, *args, **kwargs)

            # Extract client IP
            x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
            if x_forwarded_for:
                ip = x_forwarded_for.split(",")[0].strip()
            else:
                ip = request.META.get("REMOTE_ADDR")

            # Check request timestamps in Cache
            key = f"rate_limit_ingest_{ip}"
            request_timestamps = cache.get(key, [])
            
            now = time.time()
            # Retain only timestamps within the current sliding window
            request_timestamps = [t for t in request_timestamps if now - t < period]

            if len(request_timestamps) >= limit:
                logger.warning("Rate limit exceeded for IP: %s", ip)
                return JsonResponse(
                    {"error": "Rate limit exceeded. Maximum 10 requests per hour."},
                    status=429
                )

            # Record current request timestamp
            request_timestamps.append(now)
            cache.set(key, request_timestamps, period)

            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator
