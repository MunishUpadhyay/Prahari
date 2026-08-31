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

