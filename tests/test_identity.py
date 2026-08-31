import pytest
import hashlib
from django.contrib.auth.models import User
from django.test import Client
from apps.signals.models import Signal
from apps.incidents.models import Incident
from apps.tenants.models import Tenant

@pytest.fixture
def tenant(db):
    tenant, _ = Tenant.objects.get_or_create(
        name="Test Tenant",
        defaults={"api_key_hash": Tenant.hash_api_key("test_key")}
    )
    return tenant

@pytest.fixture
def citizen_a(db):
    return User.objects.create_user(
        username="citizen_a@example.com",
        email="citizen_a@example.com",
        password="password123",
        is_staff=False
    )

@pytest.fixture
def citizen_b(db):
    return User.objects.create_user(
        username="citizen_b@example.com",
        email="citizen_b@example.com",
        password="password123",
        is_staff=False
    )

@pytest.fixture
def coordinator(db):
    return User.objects.create_user(
        username="coordinator",
        email="coord@example.com",
        password="password123",
        is_staff=True
    )

@pytest.fixture
def client():
    return Client()

# --- Registration Tests ---

@pytest.mark.django_db
def test_citizen_registration_success(client):
    response = client.post("/citizen/register/", {
        "email": "new_citizen@example.com",
        "password": "password123",
        "confirm_password": "password123"
    })
    assert response.status_code == 302
    assert response.url == "/profile/"
    assert User.objects.filter(email="new_citizen@example.com").exists()

@pytest.mark.django_db
def test_citizen_registration_duplicate_email(client, citizen_a):
    response = client.post("/citizen/register/", {
        "email": citizen_a.email,
        "password": "password123",
        "confirm_password": "password123"
    })
    assert response.status_code == 200
    assert "An account with this email already exists" in response.content.decode()

@pytest.mark.django_db
def test_citizen_registration_password_mismatch(client):
    response = client.post("/citizen/register/", {
        "email": "test@example.com",
        "password": "password123",
        "confirm_password": "different_password"
    })
    assert response.status_code == 200
    assert "Passwords do not match" in response.content.decode()

@pytest.mark.django_db
def test_citizen_registration_short_password(client):
    response = client.post("/citizen/register/", {
        "email": "test@example.com",
        "password": "123",
        "confirm_password": "123"
    })
    assert response.status_code == 200
    assert "Password must be at least 6 characters" in response.content.decode()


# --- Login / Logout Tests ---

@pytest.mark.django_db
def test_citizen_login_success(client, citizen_a):
    response = client.post("/citizen/login/", {
        "email": citizen_a.email,
        "password": "password123"
    })
    assert response.status_code == 302
    assert response.url == "/profile/"

@pytest.mark.django_db
def test_citizen_login_invalid_credentials(client, citizen_a):
    response = client.post("/citizen/login/", {
        "email": citizen_a.email,
        "password": "wrong_password"
    })
    assert response.status_code == 200
    assert "Invalid email or password" in response.content.decode()

@pytest.mark.django_db
def test_citizen_logout(client, citizen_a):
    client.login(username=citizen_a.username, password="password123")
    response = client.get("/citizen/logout/")
    assert response.status_code == 302
    assert response.url == "/"


# --- Ownership Tests ---

@pytest.mark.django_db
def test_citizen_ownership_authorization(client, tenant, citizen_a, citizen_b):
    # Create report owned by citizen_a
    sig = Signal.objects.create(
        tenant=tenant,
        raw_text="Owned by citizen A",
        user=citizen_a
    )
    tracking_id = f"PRAH-{sig.created_at.strftime('%Y%m%d')}-{str(sig.id)[:4].upper()}"

    # Unauthenticated user access report -> raises 404
    response = client.get(f"/report/{tracking_id}/")
    assert response.status_code == 404

    # Citizen B access report -> raises 404
    client.login(username=citizen_b.username, password="password123")
    response = client.get(f"/report/{tracking_id}/")
    assert response.status_code == 404
    client.logout()

    # Citizen A access report -> works (renders status template)
    client.login(username=citizen_a.username, password="password123")
    response = client.get(f"/report/{tracking_id}/")
    assert response.status_code == 200
    assert "Report ID" in response.content.decode()


# --- Anonymous Reports Tests ---

@pytest.mark.django_db
def test_anonymous_report_remains_unowned(client, tenant, citizen_a):
    client.login(username=citizen_a.username, password="password123")
    
    # Post anonymous submission while logged in
    response = client.post("/submit/", {
        "raw_text": "An incident of importance",
        "anonymous": "on",
        "preferred_language": "hindi"
    })
    assert response.status_code == 302
    
    # Get the created signal
    signal = Signal.objects.latest("created_at")
    assert signal.user is None
    assert "anonymous_code" in signal.metadata


# --- Linking Tests ---

@pytest.mark.django_db
def test_citizen_linking_anonymous_report(client, tenant, citizen_a, citizen_b):
    # Create anonymous report with Return Key
    code = "XK7P2M"
    code_hash = hashlib.sha256(code.encode()).hexdigest()
    sig = Signal.objects.create(
        tenant=tenant,
        raw_text="Anonymous report text",
        metadata={"anonymous_code": code_hash}
    )
    tracking_id = f"PRAH-{sig.created_at.strftime('%Y%m%d')}-{str(sig.id)[:4].upper()}"

    # Log in Citizen A
    client.login(username=citizen_a.username, password="password123")

    # Link with invalid key
    response = client.post("/profile/link/", {
        "tracking_id": tracking_id,
        "return_key": "WRONGKEY"
    })
    sig.refresh_from_db()
    assert sig.user is None

    # Link with valid key
    response = client.post("/profile/link/", {
        "tracking_id": tracking_id,
        "return_key": code
    })
    sig.refresh_from_db()
    assert sig.user == citizen_a

    # Citizen B tries to claim the already-owned report
    client.logout()
    client.login(username=citizen_b.username, password="password123")
    response = client.post("/profile/link/", {
        "tracking_id": tracking_id,
        "return_key": code
    })
    sig.refresh_from_db()
    assert sig.user == citizen_a  # Ownership does not change


# --- Coordinator Isolation Tests ---

@pytest.mark.django_db
def test_coordinator_dashboard_isolation(client, tenant, citizen_a, coordinator):
    # Citizen tries to access dashboard -> redirected to /
    client.login(username=citizen_a.username, password="password123")
    response = client.get("/coordinator/dashboard/")
    assert response.status_code == 302
    assert response.url == "/"
    client.logout()

    # Coordinator dashboard access -> works
    client.login(username=coordinator.username, password="password123")
    response = client.get("/coordinator/dashboard/")
    assert response.status_code == 200


# --- Phase 4L.2 Report Verification & Access Lifecycle Tests ---

@pytest.mark.django_db
def test_authenticated_identified_submission_flow(client, tenant, citizen_a):
    client.login(username=citizen_a.username, password="password123")

    # Post identified report
    response = client.post("/submit/", {
        "raw_text": "Identified incident report",
        "location": "Mumbai",
        "contact_number": "+919876543210",
        "preferred_language": "english"
    }, follow=True)

    assert response.status_code == 200
    content = response.content.decode()

    # Must NOT ask for verification code
    assert "Verification Required" not in content
    # Report ID should be visible
    assert "Report ID" in content

    # Signal in DB must be owned by citizen_a
    signal = Signal.objects.latest("created_at")
    assert signal.user == citizen_a


@pytest.mark.django_db
def test_anonymous_submission_immediate_access_and_subsequent_verification(client, tenant):
    # 1. Unauthenticated visitor submits report
    response = client.post("/submit/", {
        "raw_text": "Anonymous incident report",
        "location": "Delhi",
        "preferred_language": "hindi"
    }, follow=True)

    assert response.status_code == 200
    content = response.content.decode()

    # Report was created as anonymous
    signal = Signal.objects.latest("created_at")
    assert signal.user is None
    assert "anonymous_code" in signal.metadata

    # 2. Immediately after submission: Citizen receives Return Key banner and NOT blocked by verification card
    assert "Private Return Key" in content
    assert "Verification Required" not in content

    tracking_id = f"PRAH-{signal.created_at.strftime('%Y%m%d')}-{str(signal.id)[:4].upper()}"

    # 3. New browser client accesses the report without session authorization
    fresh_client = Client()
    resp_fresh = fresh_client.get(f"/report/{tracking_id}/")
    assert resp_fresh.status_code == 200
    fresh_content = resp_fresh.content.decode()

    # Fresh client MUST be challenged with Verification Required
    assert "Verification Required" in fresh_content

    # 4. Status API is also blocked for unauthorized client
    status_resp = fresh_client.get(f"/report/{tracking_id}/status/")
    assert status_resp.status_code == 403

    # 5. Entering invalid Return Key fails
    verify_resp_invalid = fresh_client.post(
        f"/api/signals/{signal.id}/verify-code/",
        {"code": "WRONGK"},
        content_type="application/json"
    )
    assert verify_resp_invalid.status_code == 200
    assert verify_resp_invalid.json()["valid"] is False

    # 6. We can retrieve the valid code from raw test helper for verification
    # Signal metadata stored SHA-256; let's simulate the user having their code
    # We test with a known code:
    code = "7X9K2M"
    code_hash = hashlib.sha256(code.encode()).hexdigest()
    signal.metadata["anonymous_code"] = code_hash
    signal.save(update_fields=["metadata"])

    verify_resp_valid = fresh_client.post(
        f"/api/signals/{signal.id}/verify-code/",
        {"code": code},
        content_type="application/json"
    )
    assert verify_resp_valid.status_code == 200
    assert verify_resp_valid.json()["valid"] is True

    # 7. Subsequent page reload on fresh_client now grants full access
    resp_unlocked = fresh_client.get(f"/report/{tracking_id}/")
    assert resp_unlocked.status_code == 200
    assert "Verification Required" not in resp_unlocked.content.decode()


# --- Phase 4M.1 Password Reset & Coordinator Search/Filter Tests ---

@pytest.mark.django_db
def test_password_reset_flow_and_enumeration_safety(client, citizen_a, mailoutbox):
    # 1. Nonexistent email request -> enumeration safe redirect to done page
    resp_nonexistent = client.post("/citizen/password-reset/", {"email": "nonexistent@example.com"})
    assert resp_nonexistent.status_code == 302
    assert resp_nonexistent.url == "/citizen/password-reset/done/"
    assert len(mailoutbox) == 0

    # 2. Existing citizen email request -> enumeration safe redirect + email sent
    resp_exist = client.post("/citizen/password-reset/", {"email": citizen_a.email})
    assert resp_exist.status_code == 302
    assert resp_exist.url == "/citizen/password-reset/done/"
    assert len(mailoutbox) == 1
    
    email_msg = mailoutbox[0]
    assert citizen_a.email in email_msg.to
    assert "/citizen/password-reset-confirm/" in email_msg.body

    # Extract uidb64 and token from email link
    import re
    match = re.search(r"/citizen/password-reset-confirm/([^/]+)/([^/]+)/", email_msg.body)
    assert match is not None
    uidb64, token = match.group(1), match.group(2)

    # 3. GET confirm page with valid token
    resp_confirm_get = client.get(f"/citizen/password-reset-confirm/{uidb64}/{token}/")
    assert resp_confirm_get.status_code == 200
    assert "Set New Password" in resp_confirm_get.content.decode()

    # 4. POST new password with mismatch -> fails
    resp_mismatch = client.post(f"/citizen/password-reset-confirm/{uidb64}/{token}/", {
        "password": "newpassword123",
        "confirm_password": "differentpassword"
    })
    assert resp_mismatch.status_code == 200
    assert "Passwords do not match" in resp_mismatch.content.decode()

    # 5. POST valid new password -> succeeds and redirects to complete page
    resp_success = client.post(f"/citizen/password-reset-confirm/{uidb64}/{token}/", {
        "password": "newpassword123",
        "confirm_password": "newpassword123"
    })
    assert resp_success.status_code == 302
    assert resp_success.url == "/citizen/password-reset/complete/"

    # 6. Verify login with NEW password works
    login_resp = client.post("/citizen/login/", {
        "email": citizen_a.email,
        "password": "newpassword123"
    })
    assert login_resp.status_code == 302
    assert login_resp.url == "/profile/"


@pytest.mark.django_db
def test_password_reset_confirm_invalid_and_expired_tokens(client, citizen_a):
    from django.utils.http import urlsafe_base64_encode
    from django.utils.encoding import force_bytes
    
    uidb64 = urlsafe_base64_encode(force_bytes(citizen_a.pk))

    # Invalid token -> displays invalid/expired error state
    resp_invalid = client.get(f"/citizen/password-reset-confirm/{uidb64}/invalid-token-123/")
    assert resp_invalid.status_code == 200
    assert "invalid or has expired" in resp_invalid.content.decode()

    # Invalid uidb64 -> displays invalid/expired error state
    resp_invalid_uid = client.get("/citizen/password-reset-confirm/invaliduid/invalid-token/")
    assert resp_invalid_uid.status_code == 200
    assert "invalid or has expired" in resp_invalid_uid.content.decode()


@pytest.mark.django_db
def test_coordinator_dashboard_filtering_and_search(client, tenant, coordinator):
    from apps.signals.models import Signal
    from apps.incidents.models import Incident, SeverityLevel

    client.login(username=coordinator.username, password="password123")

    sig1 = Signal.objects.create(tenant=tenant, raw_text="First test signal")
    inc1 = Incident.objects.create(signal=sig1, severity_score=0.9, severity_label=SeverityLevel.CRITICAL, coordinator_status="pending")
    
    sig2 = Signal.objects.create(tenant=tenant, raw_text="Second test signal")
    inc2 = Incident.objects.create(signal=sig2, severity_score=0.2, severity_label=SeverityLevel.LOW, coordinator_status="resolved", is_resolved=True)

    tracking_id_1 = f"PRAH-{sig1.created_at.strftime('%Y%m%d')}-{str(sig1.id)[:4].upper()}"

    # 1. Filter by status=pending
    resp_pending = client.get("/coordinator/dashboard/?status=pending")
    assert resp_pending.status_code == 200
    assert tracking_id_1 in resp_pending.content.decode()

    # 2. Filter by status=resolved
    resp_resolved = client.get("/coordinator/dashboard/?status=resolved")
    assert resp_resolved.status_code == 200
    assert tracking_id_1 not in resp_resolved.content.decode()

    # 3. Search by exact Tracking ID
    resp_search = client.get(f"/coordinator/dashboard/?search={tracking_id_1}")
    assert resp_search.status_code == 200
    assert tracking_id_1 in resp_search.content.decode()

    # 4. Search by nonexistent Tracking ID
    resp_empty = client.get("/coordinator/dashboard/?search=PRAH-99999999-XXXX")
    assert resp_empty.status_code == 200
    assert "No incidents found" in resp_empty.content.decode()

