import logging
from celery import shared_task
from apps.signals.models import Signal
from apps.incidents.models import Incident
from apps.notifications.models import Notification

logger = logging.getLogger(__name__)


@shared_task(name="notifications.send_notification")
def send_notification(signal_id: str, incident_id: str):
    """
    Deprecated Celery task. SMS notification workflow has been completely removed from Prahari.
    """
    logger.info("[send_notification] Task deprecated. Skipping for signal_id=%s", signal_id)
    return {"status": "skipped", "reason": "sms_workflow_removed"}
