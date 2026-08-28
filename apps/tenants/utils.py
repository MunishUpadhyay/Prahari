import logging

logger = logging.getLogger(__name__)

def get_authorized_tenant(request):
    """
    Resolves the tenant authorized for the requesting user/session.
    Currently, Prahari MVP is single-tenant and does not maintain
    User-to-Tenant relationship mapping in the database.
    This helper returns the first active tenant as the default fallback.
    """
    from apps.tenants.models import Tenant
    tenant = Tenant.objects.filter(is_active=True).order_by('id').first()
    if not tenant:
        # Fallback/create default for dev/test environment
        tenant, _ = Tenant.objects.get_or_create(
            name="Default Tenant",
            defaults={"api_key_hash": Tenant.hash_api_key("default_key")}
        )
    return tenant
