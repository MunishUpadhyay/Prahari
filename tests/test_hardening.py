import pytest
import hashlib
from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache
from django.contrib.auth.models import User
from django.test import Client
from apps.signals.models import Signal, SignalStatus
from apps.incidents.models import Incident
from apps.tenants.models import Tenant
from pipeline.tasks import cleanup_stale_signals, classify_domain

@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()

@pytest.fixture
def tenant(db):
    tenant, _ = Tenant.objects.get_or_create(
        name="Hardening Test Tenant",
        defaults={"api_key_hash": Tenant.hash_api_key("hardening_key")}
    )
    return tenant

@pytest.fixture
def citizen(db):
    return User.objects.create_user(
        username="hardened_citizen@example.com",
        email="hardened_citizen@example.com",
        password="password123",
        is_staff=False
    )

@pytest.fixture
def client():
    return Client()


# ---------------------------------------------------------------------------
# 1. Health Check Endpoint Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_health_check_endpoint(client):
    response = client.get("/health/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"

    response_api = client.get("/api/health/")
    assert response_api.status_code == 200
    assert response_api.json()["status"] == "healthy"


# ---------------------------------------------------------------------------
# 2. Return Key Per-Report Rate Limiting & Lockout Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_return_key_per_report_rate_limiting_and_lockout(client, tenant):
    # Setup Signal A and Signal B
    code_a = "XK7P2M"
    code_a_hash = hashlib.sha256(code_a.encode()).hexdigest()
    sig_a = Signal.objects.create(
        tenant=tenant,
        raw_text="Signal A text",
        metadata={"anonymous_code": code_a_hash}
    )

    code_b = "AB12CD"
    code_b_hash = hashlib.sha256(code_b.encode()).hexdigest()
    sig_b = Signal.objects.create(
        tenant=tenant,
        raw_text="Signal B text",
        metadata={"anonymous_code": code_b_hash}
    )

    verify_url_a = f"/api/signals/{sig_a.id}/verify-code/"
    verify_url_b = f"/api/signals/{sig_b.id}/verify-code/"

    # 1. Invalid attempts 1 to 4 should return 200 with valid=False and attempts remaining
    for i in range(1, 5):
        resp = client.post(verify_url_a, {"code": "WRONG"}, content_type="application/json")
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert data["locked"] is False
        assert data["attempts_remaining"] == 5 - i

    # 2. 5th invalid attempt triggers 429 lock
    resp5 = client.post(verify_url_a, {"code": "WRONG"}, content_type="application/json")
    assert resp5.status_code == 429
    data5 = resp5.json()
    assert data5["valid"] is False
    assert data5["locked"] is True

    # 3. Subsequent attempts on Signal A (even with correct code) are blocked by lock
    resp_blocked = client.post(verify_url_a, {"code": code_a}, content_type="application/json")
    assert resp_blocked.status_code == 429
    assert resp_blocked.json()["locked"] is True

    # 4. Signal B is NOT affected by Signal A's lock
    resp_b = client.post(verify_url_b, {"code": code_b}, content_type="application/json")
    assert resp_b.status_code == 200
    assert resp_b.json()["valid"] is True


@pytest.mark.django_db
def test_successful_return_key_resets_failed_counter(client, tenant):
    code = "PW99ZZ"
    code_hash = hashlib.sha256(code.encode()).hexdigest()
    sig = Signal.objects.create(
        tenant=tenant,
        raw_text="Reset counter test",
        metadata={"anonymous_code": code_hash}
    )
    verify_url = f"/api/signals/{sig.id}/verify-code/"

    # 2 failed attempts
    client.post(verify_url, {"code": "WRONG1"}, content_type="application/json")
    client.post(verify_url, {"code": "WRONG2"}, content_type="application/json")
    assert cache.get(f"verify_failed_attempts_{sig.id}") == 2

    # 1 valid attempt
    resp_valid = client.post(verify_url, {"code": code}, content_type="application/json")
    assert resp_valid.status_code == 200
    assert resp_valid.json()["valid"] is True

    # Failed counter must be cleared
    assert cache.get(f"verify_failed_attempts_{sig.id}") is None


# ---------------------------------------------------------------------------
# 3. Status API Sanitization Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_status_api_sanitization_excludes_raw_agent_outputs(client, tenant, citizen):
    client.login(username=citizen.username, password="password123")

    sig = Signal.objects.create(
        tenant=tenant,
        raw_text="Citizen medical emergency",
        user=citizen,
        domain="health",
        status="processed"
    )

    incident = Incident.objects.create(
        signal=sig,
        severity_score=0.85,
        severity_label="high",
        domain="health",
        situation_brief="Citizen requires medical intervention.",
        agent_outputs={
            "sentinel": {"confidence": 0.95, "internal_reasoning": "classified as health"},
            "triage": {"primary_concern": "Hospital admission required"},
            "coordination": {"situation_title": "Hospital Assistance Needed"},
            "language": {
                "hindi": {"situation_title": "अस्पताल सहायता आवश्यक"},
                "preferred": "hindi"
            },
            "timing": {"sentinel": 120, "triage": 340}
        }
    )

    tracking_id = f"PRAH-{sig.created_at.strftime('%Y%m%d')}-{str(sig.id)[:4].upper()}"
    response = client.get(f"/report/{tracking_id}/status/")
    assert response.status_code == 200
    data = response.json()

    # Verify sensitive/raw internal keys are NOT in response root
    assert "agent_outputs" not in data
    assert "coordination" not in data
    assert "language" not in data

    # Verify sensitive/raw internal keys are NOT in result object
    result = data["result"]
    assert result is not None
    assert "agent_outputs" not in result
    assert "timing" not in result
    assert "language_outputs" not in result

    # Verify citizen-facing fields ARE present and intact
    assert result["title_en"] == "Hospital Assistance Needed"
    assert result["title_hi"] == "अस्पताल सहायता आवश्यक"
    assert result["severity_label"] == "high"


# ---------------------------------------------------------------------------
# 4. Stale Pipeline Cleanup Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_cleanup_stale_signals(tenant):
    now = timezone.now()
    old_time = now - timedelta(minutes=25)
    recent_time = now - timedelta(minutes=5)

    # 1. Stale processing signal (created 25 mins ago, no recent activity) -> Should become 'failed'
    stale_sig = Signal.objects.create(
        tenant=tenant,
        raw_text="Stuck processing signal",
        status="processing"
    )
    Signal.objects.filter(id=stale_sig.id).update(created_at=old_time)

    # 2. Active recent processing signal (created 5 mins ago) -> Should remain 'processing'
    active_sig = Signal.objects.create(
        tenant=tenant,
        raw_text="Active processing signal",
        status="processing"
    )
    Signal.objects.filter(id=active_sig.id).update(created_at=recent_time)

    # 3. Processed signal (created 25 mins ago) -> Should remain 'processed'
    completed_sig = Signal.objects.create(
        tenant=tenant,
        raw_text="Completed signal",
        status="processed"
    )
    Signal.objects.filter(id=completed_sig.id).update(created_at=old_time)

    # Run cleanup with 15 minute threshold
    cleaned = cleanup_stale_signals(timeout_minutes=15)
    assert cleaned == 1

    stale_sig.refresh_from_db()
    active_sig.refresh_from_db()
    completed_sig.refresh_from_db()

    assert stale_sig.status == "failed"
    assert stale_sig.metadata.get("error") == "Pipeline processing timed out"
    assert active_sig.status == "processing"
    assert completed_sig.status == "processed"


# ---------------------------------------------------------------------------
# 5. Database Indexing & Report History Query Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_citizen_report_history_indexed_query(client, tenant, citizen):
    client.login(username=citizen.username, password="password123")

    for i in range(3):
        Signal.objects.create(
            tenant=tenant,
            raw_text=f"Report {i}",
            user=citizen
        )

    # Query matching index [user, -created_at]
    signals = list(Signal.objects.filter(user=citizen).order_by("-created_at"))
    assert len(signals) == 3

    resp = client.get("/profile/")
    assert resp.status_code == 200
    content = resp.content.decode()
    assert "My Reports" in content
    assert "Report 0" not in content  # Text is private, only metadata/tracking id is listed


# ---------------------------------------------------------------------------
# 6. Phase 4N.4 Remediation Regression Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_phone_sms_workflow_completely_removed(client, tenant):
    # 1. GET /submit/ HTML should not contain phone input or SMS updates text
    resp_submit_get = client.get("/submit/")
    assert resp_submit_get.status_code == 200
    html = resp_submit_get.content.decode()
    assert "Identity &amp; Report Access" in html or "Identity & Report Access" in html
    assert "Contact Number (optional, for SMS updates)" not in html
    assert "contact_number" not in html
    assert "so coordinators can message you" not in html

    # 2. POST /submit/ ignoring any posted contact_number field
    post_resp = client.post("/submit/", {
        "raw_text": "Pothole hazard on main street road",
        "location": "Central Delhi",
        "contact_number": "+919876543210"
    }, follow=True)
    assert post_resp.status_code == 200

    sig = Signal.objects.latest("created_at")
    assert not hasattr(sig, "contact_number")
    assert "contact_number" not in sig.metadata

    # 3. Status API payload must not contain contact_number
    tracking_id = f"PRAH-{sig.created_at.strftime('%Y%m%d')}-{str(sig.id)[:4].upper()}"
    status_resp = client.get(f"/report/{tracking_id}/status/")
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert "contact_number" not in data
    if data.get("result"):
        assert "contact_number" not in data["result"]


@pytest.mark.django_db
def test_privacy_claims_accurate_wording(client):
    resp = client.get("/submit/")
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "Submissions are encrypted in transit over HTTPS" in html
    assert "we do not log your IP address or browser details" not in html


# ---------------------------------------------------------------------------
# 6. Rate Limit Cache Resilience Tests (Fail Open on Cache Outage)
# ---------------------------------------------------------------------------

from unittest.mock import patch

@pytest.mark.django_db
def test_rate_limit_cache_get_failure_fails_open(client):
    """When cache.get raises a connection error, request must fail open without 500 error."""
    with patch("apps.signals.utils.cache.get", side_effect=Exception("Redis connection error")):
        resp = client.get("/")
        # Request continues safely despite cache outage (200 OK)
        assert resp.status_code == 200


@pytest.mark.django_db
def test_rate_limit_cache_set_failure_continues(client):
    """When cache.set raises a connection error, request completes safely without 500 error."""
    with patch("apps.signals.utils.cache.set", side_effect=Exception("Redis write error")):
        resp = client.get("/")
        assert resp.status_code == 200


@pytest.mark.django_db
def test_rate_limit_normal_behavior_unchanged(client):
    """When cache is functioning normally, rate limiting operates as configured."""
    from apps.signals.utils import rate_limit_ip
    from django.http import HttpResponse

    @rate_limit_ip(limit=2, period=60, key_prefix="test_normal")
    def dummy_view(request):
        return HttpResponse("OK")

    from django.test.client import RequestFactory
    rf = RequestFactory()

    req1 = rf.get("/dummy/")
    req1.META["REMOTE_ADDR"] = "192.168.1.100"
    resp1 = dummy_view(req1)
    assert resp1.status_code == 200

    req2 = rf.get("/dummy/")
    req2.META["REMOTE_ADDR"] = "192.168.1.100"
    resp2 = dummy_view(req2)
    assert resp2.status_code == 200

    req3 = rf.get("/dummy/")
    req3.META["REMOTE_ADDR"] = "192.168.1.100"
    resp3 = dummy_view(req3)
    assert resp3.status_code == 429


# ---------------------------------------------------------------------------
# 7. Citizen Status API HTTP Boundary Response Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_status_api_404_not_found(client):
    """Status API returns 404 for invalid report tracking ID."""
    resp = client.get("/report/PRAH-20260903-NONEXISTENT/status/")
    assert resp.status_code == 404


@pytest.mark.django_db
def test_status_api_403_unauthorized_for_unverified_anonymous_signal(client, tenant):
    """Status API returns 403 for anonymous signal without Return Key session verification."""
    from apps.signals.models import Signal
    import hashlib

    sig = Signal.objects.create(
        tenant=tenant,
        raw_text="Anonymous test signal for boundary check",
        metadata={"anonymous_code": hashlib.sha256(b"SECRET").hexdigest()},
        status="pending"
    )
    date_str = sig.created_at.strftime("%Y%m%d")
    uuid_4 = str(sig.id)[:4].upper()
    tracking_id = f"PRAH-{date_str}-{uuid_4}"

    # Request status API without setting verified in session -> Must return 403
    resp = client.get(f"/report/{tracking_id}/status/")
    assert resp.status_code == 403
    data = resp.json()
    assert data.get("status") == "unauthorized"


@pytest.mark.django_db
def test_status_api_200_processing_response(client, tenant):
    """Status API returns 200 with status='processing' and steps when verified."""
    from apps.signals.models import Signal
    import hashlib

    sig = Signal.objects.create(
        tenant=tenant,
        raw_text="Anonymous processing test signal",
        metadata={"anonymous_code": hashlib.sha256(b"SECRET").hexdigest()},
        status="processing"
    )
    date_str = sig.created_at.strftime("%Y%m%d")
    uuid_4 = str(sig.id)[:4].upper()
    tracking_id = f"PRAH-{date_str}-{uuid_4}"

    # Set session verification
    session = client.session
    session[f"verified_{sig.id}"] = True
    session.save()

    resp = client.get(f"/report/{tracking_id}/status/")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "processing"
    assert data.get("steps", {}).get("received") is True
    assert data.get("steps", {}).get("translated") is False


@pytest.mark.django_db
def test_status_api_200_completed_response(client, tenant):
    """Status API returns 200 with status='processed' and steps.translated=True when completed."""
    from apps.signals.models import Signal
    from apps.incidents.models import Incident
    import hashlib

    sig = Signal.objects.create(
        tenant=tenant,
        raw_text="Anonymous completed test signal",
        metadata={"anonymous_code": hashlib.sha256(b"SECRET").hexdigest()},
        status="processed"
    )
    inc = Incident.objects.create(
        signal=sig,
        domain="legal",
        situation_brief="Completed legal test incident",
        agent_outputs={
            "triage": {"triage_severity": "LOW"},
            "rights": {"rights_violated": []},
            "coordination": {"situation_title": "Completed Notice"},
            "language": {"preferred": "english", "english": {"situation_title": "Completed Notice"}}
        }
    )
    date_str = sig.created_at.strftime("%Y%m%d")
    uuid_4 = str(sig.id)[:4].upper()
    tracking_id = f"PRAH-{date_str}-{uuid_4}"

    # Set session verification
    session = client.session
    session[f"verified_{sig.id}"] = True
    session.save()

    resp = client.get(f"/report/{tracking_id}/status/")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "processed"
    assert data.get("steps", {}).get("translated") is True
    assert data.get("result", {}).get("incident_id") == str(inc.id)



