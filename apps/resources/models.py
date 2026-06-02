import uuid
from django.db import models
from apps.tenants.models import Tenant


class ResourceType(models.TextChoices):
    HOSPITAL = "hospital", "Hospital"
    LEGAL_AID = "legal_aid", "Legal Aid"
    EMERGENCY = "emergency", "Emergency Services"
    SHELTER = "shelter", "Shelter"
    OTHER = "other", "Other"


class Resource(models.Model):
    """
    A civic resource (hospital, legal aid office, emergency service, etc.)
    associated with a Tenant and geo-indexed for proximity queries.
    The metadata field holds resource-specific details (e.g. bed count,
    specialities, jurisdiction) without schema constraints.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="resources",
    )
    name = models.CharField(max_length=255)
    resource_type = models.CharField(
        max_length=12,
        choices=ResourceType.choices,
        default=ResourceType.OTHER,
    )
    from django.conf import settings
    if "django.contrib.gis" in getattr(settings, "INSTALLED_APPS", []):
        try:
            from django.contrib.gis.db import models as gis_models
            location = gis_models.PointField(
                null=True,
                blank=True,
                help_text="Resource location (WGS84). Required for proximity queries.",
            )
        except Exception:
            location = models.JSONField(
                null=True,
                blank=True,
                help_text="Fallback: store as {lat, lng} when GDAL unavailable",
            )
    else:
        location = models.JSONField(
            null=True,
            blank=True,
            help_text="Fallback: store as {lat, lng} when GDAL unavailable",
        )
    is_available = models.BooleanField(
        default=True,
        help_text="Whether this resource is currently operational.",
    )
    contact_info = models.JSONField(
        default=dict,
        blank=True,
        help_text='E.g. {"phone": "+91-...", "email": "..."}'
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Flexible resource-specific data (beds, jurisdiction, etc.).",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Resource"
        verbose_name_plural = "Resources"
        indexes = [
            models.Index(fields=["resource_type", "is_available"]),
        ]

    def __str__(self):
        return f"{self.name} [{self.resource_type}]"
