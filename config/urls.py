"""
Root URL configuration for Prahari.
All app URLs are namespaced and versioned under /api/v1/.
"""

from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from django.views.generic import TemplateView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from apps.signals.citizen_views import (
    citizen_home,
    citizen_submit,
    citizen_report_status,
    citizen_signal_status_api,
)

urlpatterns = [
    # Citizen Portal
    path("", citizen_home, name="citizen_home"),
    path("submit/", citizen_submit, name="citizen_submit"),
    path("report/<uuid:signal_id>/", citizen_report_status, name="citizen_report_status"),
    path("report/<uuid:signal_id>/status/", citizen_signal_status_api, name="citizen_signal_status_api"),

    # Dashboard
    path("dashboard/", TemplateView.as_view(template_name="dashboard.html"), name="dashboard"),


    # Admin
    path("admin/", admin.site.urls),

    # JWT auth
    path("api/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    # Domain APIs
    path("api/signals/", include("apps.signals.urls", namespace="signals")),
    path("api/incidents/", include("apps.incidents.urls", namespace="incidents")),
    path("api/resources/", include("apps.resources.urls", namespace="resources")),
    path("api/webhooks/", include("apps.tenants.urls", namespace="tenants")),

    # OpenAPI Docs
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]
