import logging
from celery import shared_task
from apps.signals.models import Signal
from apps.incidents.models import Incident
from apps.notifications.models import Notification

logger = logging.getLogger(__name__)


@shared_task(name="notifications.send_notification")
def send_notification(signal_id: str, incident_id: str):
    """
    Celery task that simulates sending an SMS notification to the citizen.
    Funnels situation brief and title into standard SMS-friendly (max 160 chars) messages.
    """
    logger.info("[send_notification] Processing for signal_id=%s, incident_id=%s", signal_id, incident_id)
    try:
        signal = Signal.objects.get(id=signal_id)
        incident = Incident.objects.get(id=incident_id)

        # Get contact number from field or fallback metadata dictionary
        contact_number = signal.contact_number or signal.metadata.get("contact_number")
        if not contact_number:
            logger.info("[send_notification] No contact number found for signal_id=%s. Skipping.", signal_id)
            return {"status": "skipped", "reason": "no_contact_number"}

        # Extract agent outputs
        outputs = incident.agent_outputs or {}
        coord = outputs.get("coordination", {})
        lang = outputs.get("language", {}).get("hindi", {})

        title_en = coord.get("situation_title", "Incident Update")
        brief_en = incident.situation_brief or coord.get("situation_brief", "")

        title_hi = lang.get("situation_title", "घटना अपडेट") if isinstance(lang, dict) else "घटना अपडेट"
        brief_hi = lang.get("situation_brief", "") if isinstance(lang, dict) else ""

        # Build short SMS messages
        sms_en = f"Prahari Alert: {title_en} - {brief_en}".strip()
        if len(sms_en) > 160:
            sms_en = sms_en[:157] + "..."

        sms_hi = f"प्रहरी अलर्ट: {title_hi} - {brief_hi}".strip()
        if len(sms_hi) > 160:
            sms_hi = sms_hi[:157] + "..."

        # Save record to simulate dispatch log
        notif = Notification.objects.create(
            signal=signal,
            contact_number=contact_number,
            message_english=sms_en,
            message_hindi=sms_hi,
            status="sent"
        )

        logger.info(
            "[SMS Simulation] SMS would be sent to %s:\n[EN] %s\n[HI] %s",
            contact_number,
            sms_en,
            sms_hi
        )
        return {"status": "success", "notification_id": str(notif.id)}

    except Exception as e:
        logger.error("[send_notification] Failed to send notification: %s", e)
        return {"status": "failed", "error": str(e)}
