import logging
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.utils import timezone
from apps.incidents.models import Incident, SeverityLevel
from apps.signals.models import Domain
from apps.incidents.serializers import IncidentListSerializer

# Dynamically patch IncidentListSerializer to include agent_outputs on the list API
if "agent_outputs" not in IncidentListSerializer.Meta.fields:
    IncidentListSerializer.Meta.fields = list(IncidentListSerializer.Meta.fields) + ["agent_outputs"]

logger = logging.getLogger(__name__)


def coordinator_login(request):
    """
    GET /login/ — Renders login form.
    POST /login/ — Authenticates user and redirects to dashboard.
    """
    if request.user.is_authenticated:
        return redirect("/coordinator/dashboard/")

    error = None
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            logger.info("User %s logged in successfully.", username)
            return redirect("/coordinator/dashboard/")
        else:
            error = "Invalid username or password."

    return render(request, "login.html", {"error": error})


def coordinator_logout(request):
    """
    GET /logout/
    Logs out the user and redirects to login.
    """
    logout(request)
    return redirect("/login/")


@login_required(login_url="/login/")
def coordinator_dashboard(request):
    """
    GET /coordinator/dashboard/
    Renders the live incidents dashboard (login protected).
    """
    today = timezone.now().date()
    
    # Calculate stats for today
    stats = {
        "total": Incident.objects.filter(created_at__date=today).count(),
        "critical": Incident.objects.filter(created_at__date=today, severity_label=SeverityLevel.CRITICAL).count(),
        "resolved": Incident.objects.filter(created_at__date=today, is_resolved=True).count(),
        "pending": Incident.objects.filter(created_at__date=today, is_resolved=False).count(),
    }

    # Fetch last 50 incidents to populate the list on load
    incidents = Incident.objects.select_related("signal").order_by("-created_at")[:50]

    # Convert incidents to list of dicts for JSON representation in JS
    incidents_data = []
    for inc in incidents:
        outputs = inc.agent_outputs or {}
        coord = outputs.get("coordination") or {}
        lang_out = outputs.get("language") or {}
        preferred = lang_out.get("preferred") or "hindi"
        lang = lang_out.get(preferred) or {}
        
        situation_brief = inc.situation_brief
        if not situation_brief and isinstance(coord, dict):
            situation_brief = coord.get("situation_brief", "")
        if not situation_brief:
            situation_brief = "No summary available."
            
        situation_brief_hindi = ""
        if isinstance(lang, dict):
            situation_brief_hindi = lang.get("situation_brief", "")
            
        title_en = "Incident"
        if isinstance(coord, dict):
            title_en = coord.get("situation_title", inc.situation_brief or "Incident")
            
        title_hi = ""
        if isinstance(lang, dict):
            title_hi = lang.get("situation_title", "")
        
        incidents_data.append({
            "incident_id": str(inc.id),
            "severity": inc.severity_score,
            "severity_label": inc.severity_label,
            "domain": inc.domain,
            "situation_brief": situation_brief,
            "situation_brief_hindi": situation_brief_hindi,
            "title_en": title_en,
            "title_hi": title_hi,
            "is_resolved": inc.is_resolved,
            "coordinator_status": inc.coordinator_status,
            "coordinator_notes": inc.coordinator_notes,
            "timestamp": inc.updated_at.isoformat() if inc.updated_at else inc.created_at.isoformat(),
            "agent_outputs": inc.agent_outputs,
            "signal_raw_text": inc.signal.raw_text,
        })

    # Pass tenant_id to connect to correct websocket group (first active tenant is default fallback)
    from apps.tenants.models import Tenant
    tenant = Tenant.objects.filter(is_active=True).first()
    tenant_id = str(tenant.id) if tenant else "default"

    # Generate last 7 days daily counts for trend visualization
    import datetime
    daily_counts = []
    for i in range(6, -1, -1):
        day = today - datetime.timedelta(days=i)
        daily_counts.append(Incident.objects.filter(created_at__date=day).count())

    # Generate JWT token for API auth on page load
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(request.user)
    jwt_token = str(refresh.access_token)

    import json
    context = {
        "stats": stats,
        "incidents_json": json.dumps(incidents_data),
        "tenant_id": tenant_id,
        "jwt_token": jwt_token,
        "daily_counts": daily_counts,
    }
    return render(request, "coordinator_dashboard.html", context)


@login_required(login_url="/login/")
def coordinator_incident_detail(request, incident_id):
    """
    GET /coordinator/incident/<id>/
    Renders detailed tabbed view of a single incident.
    """
    incident = get_object_or_404(Incident.objects.select_related("signal"), id=incident_id)
    outputs = incident.agent_outputs or {}
    import json
    # Ensure they are dicts if stored as strings
    for k in ["sentinel", "rights", "triage", "coordination", "language"]:
        val = outputs.get(k)
        if isinstance(val, str):
            try:
                outputs[k] = json.loads(val)
            except Exception:
                pass

    sentinel = outputs.get("sentinel")
    if sentinel and isinstance(sentinel, dict):
        confidence = sentinel.get("confidence")
        if confidence is not None:
            try:
                sentinel["confidence_pct"] = int(float(confidence) * 100)
            except Exception:
                sentinel["confidence_pct"] = 0

    triage = outputs.get("triage")
    if triage and isinstance(triage, dict):
        confidence = triage.get("confidence")
        if confidence is not None:
            try:
                triage["confidence_pct"] = int(float(confidence) * 100)
            except Exception:
                triage["confidence_pct"] = 90
        else:
            triage["confidence_pct"] = 90

    rights = outputs.get("rights")
    if rights and isinstance(rights, dict):
        confidence = rights.get("confidence")
        if confidence is not None:
            try:
                rights["confidence_pct"] = int(float(confidence) * 100)
            except Exception:
                rights["confidence_pct"] = 90
        else:
            rights["confidence_pct"] = 90

        # Calculate case_strength_pct
        case_strength = rights.get("case_strength")
        if case_strength is not None:
            try:
                rights["case_strength_pct"] = int(float(case_strength) * 100)
            except Exception:
                rights["case_strength_pct"] = rights["confidence_pct"]
        else:
            rights["case_strength_pct"] = rights["confidence_pct"]

    # Calculate complete steps for timeline
    is_processed = incident.signal.status == 'processed'
    timeline = [
        {"name_en": "Signal Ingested", "name_hi": "सिग्नल प्राप्त हुआ", "time": incident.created_at, "status": "done"},
        {"name_en": "Sentinel Classified", "name_hi": "सेंटीनेल वर्गीकृत", "time": incident.created_at, "status": "done" if "sentinel" in outputs else "failed" if is_processed else "pending"},
        {"name_en": "Triage Assessed", "name_hi": "ट्राइएज मूल्यांकन", "time": incident.created_at, "status": "done" if "triage" in outputs else "skipped"},
        {"name_en": "Rights Assessed", "name_hi": "अधिकार मूल्यांकन", "time": incident.created_at, "status": "done" if "rights" in outputs else "skipped"},
        {"name_en": "Brief Coordinated", "name_hi": "संक्षिप्त विवरण समन्वित", "time": incident.created_at, "status": "done" if "coordination" in outputs else "failed" if is_processed else "pending"},
    ]

    lang_full = outputs.get("language") or {}
    pref_lang = lang_full.get("preferred", incident.signal.preferred_language or "hindi")
    lang_sub = lang_full.get(pref_lang) if isinstance(lang_full, dict) else {}

    context = {
        "incident": incident,
        "outputs": outputs,
        "sentinel": sentinel,
        "rights": outputs.get("rights"),
        "triage": outputs.get("triage"),
        "coordination": outputs.get("coordination"),
        "language": lang_sub,
        "pref_lang": pref_lang,
        "timeline": timeline,
        "timing": outputs.get("timing"),
    }
    return render(request, "coordinator_detail.html", context)


@login_required(login_url="/login/")
def coordinator_resolve_incident(request, incident_id):
    """
    POST /coordinator/incident/<id>/resolve/
    Marks the incident as resolved.
    """
    if request.method == "POST":
        incident = get_object_or_404(Incident, id=incident_id)
        incident.is_resolved = True
        incident.resolved_at = timezone.now()
        incident.coordinator_status = 'resolved'
        incident.status_updated_at = timezone.now()
        incident.save(update_fields=["is_resolved", "resolved_at", "coordinator_status", "status_updated_at"])
        
        logger.info("Incident %s resolved by coordinator.", incident_id)
        
        return JsonResponse({
            "status": "success",
            "incident_id": str(incident.id),
            "is_resolved": True,
            "resolved_at": incident.resolved_at.isoformat()
        })
        
    return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)
