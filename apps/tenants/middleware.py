from django.utils.functional import SimpleLazyObject

def get_tenant_from_request(request):
    # For demo purposes, return the first tenant
    # In production this would be resolved from JWT claims
    from apps.tenants.models import Tenant
    return Tenant.objects.first()

class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        request.tenant = SimpleLazyObject(
            lambda: get_tenant_from_request(request)
        )
        return self.get_response(request)
