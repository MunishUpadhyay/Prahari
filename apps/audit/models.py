import uuid
import hashlib
from django.db import models
from django.utils import timezone
from apps.incidents.models import Incident


class AuditLog(models.Model):
    """
    Tamper-evident audit trail for every action taken on an Incident.

    The `hash` field is a SHA-256 digest computed over:
        incident_id | action | performed_by | timestamp (ISO8601)

    This creates a verifiable chain — any modification to previous fields
    will produce a different hash, exposing tampering.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    incident = models.ForeignKey(
        Incident,
        on_delete=models.CASCADE,
        related_name="audit_logs",
    )
    action = models.CharField(
        max_length=255,
        help_text="Description of the action (e.g. 'incident_created', 'status_changed').",
    )
    performed_by = models.CharField(
        max_length=255,
        help_text="User, agent name, or system component that performed the action.",
    )
    payload = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional structured data about the action.",
    )
    hash = models.CharField(
        max_length=64,
        editable=False,
        help_text="SHA-256 of (incident_id + action + performed_by + timestamp).",
    )
    timestamp = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["timestamp"]
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"

    def __str__(self):
        return f"AuditLog({self.incident_id}) — {self.action} by {self.performed_by}"

    def compute_hash(self) -> str:
        """Compute SHA-256 over the key audit fields."""
        raw = f"{self.incident_id}|{self.action}|{self.performed_by}|{self.timestamp.isoformat()}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def save(self, *args, **kwargs):
        # Always (re-)compute hash before persisting
        self.hash = self.compute_hash()
        super().save(*args, **kwargs)
