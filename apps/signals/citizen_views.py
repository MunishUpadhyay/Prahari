import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from apps.signals.models import Signal
from apps.incidents.models import Incident
from apps.tenants.models import Tenant
from pipeline.tasks import ingest_signal

logger = logging.getLogger(__name__)


def citizen_home(request):
    """
    GET /
    Renders the citizen landing page.
    """
    return render(request, "home.html")


def citizen_submit(request):
    """
    GET /submit/ — Renders submission form.
    POST /submit/ — Processes form, creates signal, and redirects to status.
    """
    if request.method == "POST":
        raw_text = request.POST.get("raw_text", "").strip()
        location = request.POST.get("location", "").strip()
        contact_number = request.POST.get("contact_number", "").strip()
        preferred_language = request.POST.get("preferred_language", "hindi").strip()
        anonymous = request.POST.get("anonymous") == "on"

        if not raw_text:
            return render(request, "submit.html", {"error": "Please describe what is happening."})

        # Resolve the default tenant (first active tenant)
        tenant = Tenant.objects.filter(is_active=True).first()
        if not tenant:
            tenant, _ = Tenant.objects.get_or_create(
                name="Default Tenant",
                defaults={"api_key_hash": Tenant.hash_api_key("default_key")}
            )

        # Save metadata containing location and contact number
        metadata = {}
        if location:
            metadata["location"] = location

        if anonymous:
            contact_number = ""
        else:
            if contact_number:
                metadata["contact_number"] = contact_number

        # Create Signal directly in DB
        signal = Signal.objects.create(
            tenant=tenant,
            raw_text=raw_text,
            source_type="text",
            contact_number=contact_number,
            preferred_language=preferred_language,
            metadata=metadata
        )

        if anonymous:
            import secrets
            import hashlib
            code = secrets.token_urlsafe(4)[:6].upper()
            code_hash = hashlib.sha256(code.encode()).hexdigest()
            signal.metadata['anonymous_code'] = code_hash
            signal.save(update_fields=['metadata'])
            
            # Pass code to redirect page via session
            request.session[f"anon_code_{signal.id}"] = code

        logger.info("[Citizen Portal] Created signal %s, enqueuing Celery task", signal.id)
        
        # Enqueue the processing task
        ingest_signal.delay(str(signal.id))

        return redirect(f"/report/{signal.id}/")

    return render(request, "submit.html")


from django.conf import settings


def citizen_report_status(request, signal_id):
    """
    GET /report/<signal_id>/
    Renders the polling progress page for a submitted signal.
    """
    # Ensure signal exists
    signal = get_object_or_404(Signal, id=signal_id)
    date_str = signal.created_at.strftime("%Y%m%d")
    uuid_first_4 = str(signal.id)[:4].upper()
    tracking_id = f"PRAH-{date_str}-{uuid_first_4}"
    
    # Check if this signal is anonymous
    is_anonymous = signal.metadata and 'anonymous_code' in signal.metadata
    
    # Retrieve raw code from session if it was just set during redirect
    session_key = f"anon_code_{signal.id}"
    raw_code = request.session.pop(session_key, None)
    
    return render(request, "report_status.html", {
        "signal_id": signal_id,
        "tracking_id": tracking_id,
        "site_url": settings.SITE_URL,
        "preferred_language": signal.preferred_language or "hindi",
        "is_anonymous": is_anonymous,
        "anonymous_access_code": raw_code,
    })


def citizen_signal_status_api(request, signal_id):
    """
    GET /report/<signal_id>/status/
    Unauthenticated API endpoint for AJAX polling of pipeline status.
    """
    signal = get_object_or_404(Signal, id=signal_id)
    
    # Stuck pipeline check: if signal.status == 'processing' and is more than 5 minutes old
    from django.utils import timezone
    from datetime import timedelta
    if signal.status == 'processing' and (timezone.now() - signal.created_at) > timedelta(minutes=5):
        return JsonResponse({
            'status': 'pipeline_error',
            'message': 'Pipeline timed out'
        })

    incident = getattr(signal, "incident", None)

    # Base steps status mapping
    steps = {
        "received": True,
        "classified": bool(signal.domain),
        "analyzed": False,
        "coordinated": False,
        "translated": False
    }

    result = None

    if incident:
        # Check completed agent outputs
        outputs = incident.agent_outputs or {}
        
        # sentinel is done (pre-requisite for incident creation)
        steps["classified"] = True
        
        # Rights / Triage analysis:
        # - In cross domain, both triage and rights must finish (or triage recommends rights escalation)
        # - In health/emergency only, triage must finish
        # - In legal only, rights must finish
        is_legal = incident.domain in ["legal", "cross"]
        is_health = incident.domain in ["health", "emergency", "cross"]
        
        rights_done = not is_legal or ("rights" in outputs)
        triage_done = not is_health or ("triage" in outputs)
        
        steps["analyzed"] = (rights_done and triage_done)
        
        # Coordination brief:
        steps["coordinated"] = ("coordination" in outputs)
        
        # Translation:
        steps["translated"] = ("language" in outputs)

        # If language and coordination are both done, we compile the final response
        if steps["translated"]:
            coord_out = outputs.get("coordination", {})
            lang_data = outputs.get("language", {})
            pref_lang = lang_data.get("preferred", "hindi")
            lang_out = lang_data.get(pref_lang, {}) or lang_data.get("hindi", {})
            rights_out = outputs.get("rights", {})
            triage_out = outputs.get("triage", {})
            
            result = {
                "incident_id": str(incident.id),
                "severity_label": incident.severity_label,
                "severity_score": incident.severity_score,
                "domain": incident.domain,
                "title_en": coord_out.get("situation_title", ""),
                "title_hi": lang_out.get("situation_title", ""),
                "brief_en": incident.situation_brief,
                "brief_hi": lang_out.get("situation_brief", ""),
                "what_is_happening_en": coord_out.get("what_is_happening", ""),
                "what_is_happening_hi": lang_out.get("what_is_happening", ""),
                
                "rights_violated": rights_out.get("rights_violated", []),
                "legal_provisions": rights_out.get("legal_provisions", []),
                "legal_provisions_hi": lang_out.get("legal_provisions", []),
                "legal_timeline": rights_out.get("legal_timeline", []),
                "legal_timeline_hi": lang_out.get("legal_timeline", []),
                "nearest_authority_type": rights_out.get("nearest_authority_type", "DLSA"),
                "triage_severity": triage_out.get("triage_severity", ""),
                "hospital_denial_detected": triage_out.get("hospital_denial_detected", False),
                
                "golden_window": triage_out.get("golden_window", {}),
                "golden_window_hi": lang_out.get("golden_window", {}),
                "emergency_contacts": triage_out.get("emergency_contacts", []),
                "emergency_contacts_hi": lang_out.get("emergency_contacts", []),
                "primary_concern": triage_out.get("primary_concern", ""),
                "primary_concern_hi": lang_out.get("primary_concern", ""),
                
                "conflict_resolution": coord_out.get("conflict_resolution"),
                "conflict_resolution_hi": lang_out.get("conflict_resolution"),
                "escalation_path": coord_out.get("escalation_path", []),
                "escalation_path_hi": lang_out.get("escalation_path", []),
                
                "immediate_actions": coord_out.get("immediate_actions", []),
                "immediate_actions_hi": lang_out.get("immediate_actions", []),
                "authorities_to_notify": coord_out.get("authorities_to_notify", []),
                "authorities_to_notify_hi": lang_out.get("authorities_to_notify", []),
                "resources_needed": coord_out.get("resources_needed", []),
                "resources_needed_hi": lang_out.get("resources_needed", []),
                "evidence_to_collect": coord_out.get("evidence_to_collect", []),
                "evidence_to_collect_hi": lang_out.get("evidence_to_collect") or coord_out.get("evidence_to_collect", []),
                "contact_number": signal.metadata.get("contact_number", ""),
                "coordinator_status": incident.coordinator_status,
                "coordinator_notes": incident.coordinator_notes,
                "timing": outputs.get("timing", {}),
                "language_outputs": outputs.get("language", {}),
                "preferred_language": signal.preferred_language
            }

    # Signal status mapper
    pipeline_status = "processing"
    if steps["translated"]:
        pipeline_status = "processed"
    elif signal.status == "failed":
        pipeline_status = "failed"

    return JsonResponse({
        "signal_id": str(signal.id),
        "status": pipeline_status,
        "steps": steps,
        "result": result
    })
