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
    citizen_track_report,
    citizen_report_status,
    citizen_signal_status_api,
    health_check,
)
from apps.signals.citizen_auth_views import (
    citizen_register,
    citizen_login,
    citizen_logout_view,
    citizen_password_reset_request,
    citizen_password_reset_done,
    citizen_password_reset_confirm,
    citizen_password_reset_complete,
)
from apps.signals.profile_views import (
    citizen_profile,
    link_existing_report,
)
from apps.incidents.coordinator_views import (
    coordinator_login,
    coordinator_logout,
    coordinator_dashboard,
    coordinator_incident_detail,
    coordinator_resolve_incident,
)
from apps.signals.utils import rate_limit_ip

urlpatterns = [
    # Health check endpoints for production orchestrators
    path("health/", health_check, name="health_check"),
    path("api/health/", health_check, name="api_health_check"),

    # Citizen Portal
    path("", citizen_home, name="citizen_home"),
    path("submit/", citizen_submit, name="citizen_submit"),
    path("track/", citizen_track_report, name="citizen_track"),
    path("report/<str:signal_id>/", citizen_report_status, name="citizen_report_status"),
    path("report/<str:signal_id>/status/", citizen_signal_status_api, name="citizen_signal_status_api"),
    path("citizen/register/", citizen_register, name="citizen_register"),
    path("citizen/login/", citizen_login, name="citizen_login"),
    path("citizen/logout/", citizen_logout_view, name="citizen_logout"),
    path("citizen/password-reset/", citizen_password_reset_request, name="citizen_password_reset"),
    path("citizen/password-reset/done/", citizen_password_reset_done, name="citizen_password_reset_done"),
    path("citizen/password-reset-confirm/<str:uidb64>/<str:token>/", citizen_password_reset_confirm, name="citizen_password_reset_confirm"),
    path("citizen/password-reset/complete/", citizen_password_reset_complete, name="citizen_password_reset_complete"),
    path("profile/", citizen_profile, name="citizen_profile"),
    path("profile/link/", link_existing_report, name="link_existing_report"),

    # Coordinator Portal
    path("login/", coordinator_login, name="login"),
    path("logout/", coordinator_logout, name="logout"),
    path("coordinator/dashboard/", coordinator_dashboard, name="coordinator_dashboard"),
    path("coordinator/incident/<uuid:incident_id>/", coordinator_incident_detail, name="coordinator_incident_detail"),
    path("coordinator/incident/<uuid:incident_id>/resolve/", coordinator_resolve_incident, name="coordinator_resolve_incident"),

    # Old dashboard path (redirects or keeps for reference)
    path("dashboard/", TemplateView.as_view(template_name="dashboard.html"), name="dashboard"),



    # Admin
    path("admin/", admin.site.urls),

    # JWT auth
    path("api/auth/token/", rate_limit_ip(limit=5, period=60, key_prefix="token")(TokenObtainPairView.as_view()), name="token_obtain_pair"),
    path("api/auth/token/refresh/", rate_limit_ip(limit=10, period=60, key_prefix="token_refresh")(TokenRefreshView.as_view()), name="token_refresh"),

    # Domain APIs
    path("api/signals/", include("apps.signals.urls", namespace="signals")),
    path("api/incidents/", include("apps.incidents.urls", namespace="incidents")),
    path("api/resources/", include("apps.resources.urls", namespace="resources")),
    path("api/webhooks/", include("apps.tenants.urls", namespace="tenants")),

    # OpenAPI Docs
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]
