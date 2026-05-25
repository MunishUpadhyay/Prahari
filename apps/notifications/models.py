import uuid
from django.db import models
from apps.signals.models import Signal


class Notification(models.Model):
    """
    Simulated SMS notifications dispatched to citizens upon incident analysis completion.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    signal = models.ForeignKey(
        Signal,
        on_delete=models.CASCADE,
        related_name="notifications",
        help_text="The signal this notification belongs to."
    )
    contact_number = models.CharField(
        max_length=15,
        help_text="Target phone number for simulated SMS."
    )
    message_english = models.TextField(
        help_text="Synthesized English message."
    )
    message_hindi = models.TextField(
        help_text="Translated Hindi message."
    )
    sent_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp of simulated dispatch."
    )
    status = models.CharField(
        max_length=20,
        default="sent",
        help_text="Notification delivery status."
    )

    class Meta:
        ordering = ["-sent_at"]
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"

    def __str__(self):
        return f"Notification({self.id}) -> {self.contact_number} status={self.status}"
