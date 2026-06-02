import uuid
from django.db import models
from apps.signals.models import Signal, Domain


class SeverityLevel(models.TextChoices):
    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"
    CRITICAL = "critical", "Critical"


class Incident(models.Model):
    """
    Tracks a processed Signal through its full lifecycle.
    agent_outputs stores each agent's structured response keyed by agent name.
    situation_brief is the human-readable summary produced by LanguageAgent.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    signal = models.OneToOneField(
        Signal,
        on_delete=models.CASCADE,
        related_name="incident",
    )
    severity_score = models.FloatField(
        default=0.0,
        help_text="Normalised severity in [0.0, 1.0] assigned by SentinelAgent.",
    )
    severity_label = models.CharField(
        max_length=10,
        choices=SeverityLevel.choices,
        default=SeverityLevel.LOW,
    )
    domain = models.CharField(
        max_length=10,
        choices=Domain.choices,
        blank=True,
    )
    agent_outputs = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Structured outputs from all agents, keyed by agent name. "
            'Example: {"sentinel": {...}, "rights": {...}}'
        ),
    )
    situation_brief = models.TextField(
        blank=True,
        help_text="Plain-language situation summary produced by LanguageAgent.",
    )
    recommended_resources = models.JSONField(
        default=list,
        blank=True,
        help_text="List of recommended resource IDs from CoordinationAgent.",
    )
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    coordinator_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('under_review', 'Under Review'),
            ('action_taken', 'Action Taken'),
            ('resolved', 'Resolved')
        ],
        default='pending'
    )
    coordinator_notes = models.TextField(blank=True, default='')
    status_updated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Incident"
        verbose_name_plural = "Incidents"
        indexes = [
            models.Index(fields=["is_resolved"]),
            models.Index(fields=["severity_label"]),
            models.Index(fields=["domain"]),
        ]

    def __str__(self):
        return f"Incident({self.id}) — severity={self.severity_label} resolved={self.is_resolved}"

    def save(self, *args, **kwargs):
        from django.utils import timezone
        if self.pk:
            try:
                orig = Incident.objects.get(pk=self.pk)
                if orig.coordinator_status != self.coordinator_status:
                    self.status_updated_at = timezone.now()
                    if self.coordinator_status == 'resolved':
                        self.is_resolved = True
                        if not self.resolved_at:
                            self.resolved_at = timezone.now()
                    else:
                        self.is_resolved = False
                        self.resolved_at = None
            except Incident.DoesNotExist:
                pass
        else:
            if not self.status_updated_at:
                self.status_updated_at = timezone.now()
            if self.coordinator_status == 'resolved':
                self.is_resolved = True
                if not self.resolved_at:
                    self.resolved_at = timezone.now()
        super().save(*args, **kwargs)
