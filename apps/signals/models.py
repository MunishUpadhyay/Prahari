import uuid
from django.db import models
from apps.tenants.models import Tenant

class SourceType(models.TextChoices):
    TEXT = "text", "Text"
    IMAGE = "image", "Image"
    WEBHOOK = "webhook", "Webhook"


class Domain(models.TextChoices):
    LEGAL = "legal", "Legal"
    HEALTH = "health", "Health"
    EMERGENCY = "emergency", "Emergency"
    CROSS = "cross", "Cross-domain"


class SignalStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    PROCESSED = "processed", "Processed"
    FAILED = "failed", "Failed"


class Signal(models.Model):
    """
    A raw civic input ingested into Prahari.
    Can originate as free text, an image upload, or an external webhook call.
    Each Signal belongs to a Tenant and is processed through the Celery pipeline.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="signals",
    )
    raw_text = models.TextField(
        blank=True,
        help_text="Raw text content of the signal.",
    )
    image = models.ImageField(
        upload_to="signals/images/%Y/%m/",
        blank=True,
        null=True,
        help_text="Optional image attachment.",
    )
    source_type = models.CharField(
        max_length=10,
        choices=SourceType.choices,
        default=SourceType.TEXT,
    )
    try:
        from django.contrib.gis.db import models as gis_models
        location = gis_models.PointField(
            null=True,
            blank=True,
            help_text="Geographic origin of the signal (WGS84).",
        )
    except Exception:
        from django.db import models as std_models
        location = std_models.JSONField(
            null=True,
            blank=True,
            help_text="Fallback: store as {lat, lng} when GDAL unavailable",
        )
    domain = models.CharField(
        max_length=10,
        choices=Domain.choices,
        blank=True,
        help_text="Classified domain — set by the pipeline after ingestion.",
    )
    status = models.CharField(
        max_length=12,
        choices=SignalStatus.choices,
        default=SignalStatus.PENDING,
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Arbitrary extra data from the ingestion source.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Signal"
        verbose_name_plural = "Signals"
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["domain"]),
        ]

    def __str__(self):
        return f"Signal({self.id}) [{self.source_type}] — {self.tenant.name}"
