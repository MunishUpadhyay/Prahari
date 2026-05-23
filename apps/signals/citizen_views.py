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
        if contact_number:
            metadata["contact_number"] = contact_number

        # Create Signal directly in DB
        signal = Signal.objects.create(
            tenant=tenant,
            raw_text=raw_text,
            source_type="text",
            metadata=metadata
        )

        logger.info("[Citizen Portal] Created signal %s, enqueuing Celery task", signal.id)
        
        # Enqueue the processing task
        ingest_signal.delay(str(signal.id))

        return redirect(f"/report/{signal.id}/")

    return render(request, "submit.html")


def citizen_report_status(request, signal_id):
    """
    GET /report/<signal_id>/
    Renders the polling progress page for a submitted signal.
    """
    # Ensure signal exists
    get_object_or_404(Signal, id=signal_id)
    return render(request, "report_status.html", {"signal_id": signal_id})


def citizen_signal_status_api(request, signal_id):
    """
    GET /report/<signal_id>/status/
    Unauthenticated API endpoint for AJAX polling of pipeline status.
    """
    signal = get_object_or_404(Signal, id=signal_id)
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
            lang_out = outputs.get("language", {}).get("hindi", {})
            rights_out = outputs.get("rights", {})
            
            result = {
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
                "immediate_actions": coord_out.get("immediate_actions", []),
                "immediate_actions_hi": lang_out.get("immediate_actions", []),
                "authorities_to_notify": coord_out.get("authorities_to_notify", []),
                "resources_needed": coord_out.get("resources_needed", []),
                "resources_needed_hi": lang_out.get("resources_needed", []),
                "contact_number": signal.metadata.get("contact_number", "")
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
