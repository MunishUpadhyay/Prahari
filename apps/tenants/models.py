import uuid
import hashlib
from django.db import models


class Tenant(models.Model):
    """
    Represents an organisation using Prahari.
    Each Tenant owns its own Signals, Incidents, and Resources.
    The api_key field stores only the SHA-256 hash of the raw key;
    the raw key is shown once at creation and never persisted.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    api_key_hash = models.CharField(
        max_length=64,
        unique=True,
        help_text="SHA-256 hash of the raw API key.",
    )
    webhook_url = models.URLField(
        blank=True,
        null=True,
        help_text="Optional URL to POST incident updates to.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Tenant"
        verbose_name_plural = "Tenants"

    def __str__(self):
        return self.name

    @staticmethod
    def hash_api_key(raw_key: str) -> str:
        """Return the SHA-256 hex digest of a raw API key."""
        return hashlib.sha256(raw_key.encode()).hexdigest()

    @classmethod
    def verify_api_key(cls, raw_key: str, tenant_id: uuid.UUID) -> bool:
        """Check whether a raw key matches the stored hash for a given tenant."""
        try:
            tenant = cls.objects.get(pk=tenant_id, is_active=True)
        except cls.DoesNotExist:
            return False
        return tenant.api_key_hash == cls.hash_api_key(raw_key)
