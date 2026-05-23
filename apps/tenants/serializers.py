from rest_framework import serializers
from .models import Tenant


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ["id", "name", "webhook_url", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]


class WebhookRegisterSerializer(serializers.Serializer):
    """
    Accepts a webhook_url to register (or update) for the authenticated tenant.
    """

    webhook_url = serializers.URLField()
