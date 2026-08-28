import pytest
from django.urls import reverse
from rest_framework import status
from apps.signals.models import Signal, SourceType, Domain
from apps.incidents.models import Incident
from apps.tenants.models import Tenant
from apps.incidents.serializers import IncidentListSerializer

from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken

@pytest.mark.django_db
def test_similar_incidents_view_authentication(client):
    tenant = Tenant.objects.create(name="Test Tenant", is_active=True)
    signal = Signal.objects.create(tenant=tenant, raw_text="Test raw content", source_type=SourceType.TEXT, domain=Domain.LEGAL)
    incident = Incident.objects.create(signal=signal, severity_score=0.5, severity_label="medium", domain="legal")
    url = reverse("incidents:similar", kwargs={"id": incident.id})
    
    # Case 1: Anonymous request
    response = client.get(url)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    # Case 2: Invalid JWT
    response = client.get(url, HTTP_AUTHORIZATION="Bearer invalid_token_value")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    # Case 3: Valid JWT
    user = User.objects.create_user(username="testuser", password="password")
    token = str(RefreshToken.for_user(user).access_token)
    response = client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")
    assert response.status_code == status.HTTP_200_OK

@pytest.mark.django_db
def test_legal_notice_view_authentication(client, mock_groq):
    tenant = Tenant.objects.create(name="Test Tenant", is_active=True)
    signal = Signal.objects.create(tenant=tenant, raw_text="Test raw content", source_type=SourceType.TEXT, domain=Domain.LEGAL)
    agent_outputs = {"rights": {"rights_violated": ["Right to Life"], "legal_provisions": [], "immediate_actions": [], "authority_to_contact": "DLSA"}}
    incident = Incident.objects.create(signal=signal, severity_score=0.5, severity_label="medium", domain="legal", agent_outputs=agent_outputs)
    url = reverse("incidents:legal-notice", kwargs={"id": incident.id})
    
    # Case 1: Anonymous request
    response = client.get(url)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    # Case 2: Invalid JWT
    response = client.get(url, HTTP_AUTHORIZATION="Bearer invalid_token_value")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    # Case 3: Valid JWT
    user = User.objects.create_user(username="testuser", password="password")
    token = str(RefreshToken.for_user(user).access_token)
    response = client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")
    assert response.status_code == status.HTTP_200_OK
    assert "notice" in response.data

@pytest.mark.django_db
def test_incident_list_serializer_baseline():
    tenant = Tenant.objects.create(name="Test Tenant", is_active=True)
    signal = Signal.objects.create(tenant=tenant, raw_text="Test", source_type=SourceType.TEXT)
    
    # Case 1: Null/empty agent_outputs
    incident_empty = Incident.objects.create(signal=signal, severity_score=0.5, severity_label="medium", domain="legal", agent_outputs={})
    data_empty = IncidentListSerializer(incident_empty).data
    assert "agent_outputs" in data_empty
    assert data_empty["agent_outputs"] == {}
    
    # Case 2: Populated agent_outputs
    mock_outputs = {"sentinel": {"severity_score": 0.5}}
    incident_empty.agent_outputs = mock_outputs
    incident_empty.save()
    
    data_pop = IncidentListSerializer(incident_empty).data
    assert "agent_outputs" in data_pop
    assert data_pop["agent_outputs"] == mock_outputs
    
    # Verify that the serializer Meta configuration statically lists the field
    assert "agent_outputs" in IncidentListSerializer.Meta.fields
    
    # Verify other fields are unaffected
    assert "id" in data_pop
    assert "signal_raw_text" in data_pop
    assert "severity_score" in data_pop
    assert "severity_label" in data_pop
    assert "domain" in data_pop


@pytest.mark.django_db
def test_anonymous_code_verification_status_api(client):
    import hashlib
    tenant = Tenant.objects.create(name="Test Tenant", is_active=True)
    
    # 1. Create an anonymous signal with access code hash
    code = "ABCDEF"
    code_hash = hashlib.sha256(code.encode()).hexdigest()
    signal = Signal.objects.create(
        tenant=tenant,
        raw_text="Test anonymous incident",
        source_type=SourceType.TEXT,
        metadata={"anonymous_code": code_hash}
    )
    
    # Status API URL
    status_url = reverse("citizen_signal_status_api", kwargs={"signal_id": signal.id})
    verify_url = reverse("signals:verify_code", kwargs={"signal_id": signal.id})
    
    # Case A: Status API returns 403 Forbidden without code verification in session
    response = client.get(status_url)
    assert response.status_code == 403
    assert "Anonymous access code verification required" in response.json()["message"]
    
    # Case B: Call verify-code with incorrect code
    response = client.post(verify_url, {"code": "WRONG"}, content_type="application/json")
    assert response.status_code == 200
    assert response.json()["valid"] is False
    
    # Status API still returns 403
    response = client.get(status_url)
    assert response.status_code == 403
    
    # Case C: Call verify-code with correct code
    response = client.post(verify_url, {"code": code}, content_type="application/json")
    assert response.status_code == 200
    assert response.json()["valid"] is True
    
    # Status API now succeeds (200)
    response = client.get(status_url)
    assert response.status_code == 200
    
    # 2. Create a non-anonymous signal
    non_anon_signal = Signal.objects.create(
        tenant=tenant,
        raw_text="Test public incident",
        source_type=SourceType.TEXT
    )
    non_anon_status_url = reverse("citizen_signal_status_api", kwargs={"signal_id": non_anon_signal.id})
    
    # Status API succeeds immediately without session validation
    response = client.get(non_anon_status_url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_security_regression(client):
    import hashlib
    from apps.signals.models import Signal, SourceType
    from apps.incidents.models import Incident
    from apps.tenants.models import Tenant
    from django.contrib.auth.models import User
    from rest_framework_simplejwt.tokens import RefreshToken
    from django.core.cache import cache

    # Setup Tenants
    tenant_a = Tenant.objects.create(name="Tenant A", api_key_hash="hash_a", is_active=True)
    tenant_b = Tenant.objects.create(name="Tenant B", api_key_hash="hash_b", is_active=False)

    # 1. Citizen A (Anonymous Signal A in Tenant A)
    code_a = "CODEAA"
    hash_a = hashlib.sha256(code_a.encode()).hexdigest()
    signal_a = Signal.objects.create(
        tenant=tenant_a,
        raw_text="Citizen A raw text",
        source_type=SourceType.TEXT,
        metadata={"anonymous_code": hash_a}
    )
    incident_a = Incident.objects.create(signal=signal_a, severity_score=0.7, severity_label="high", domain="legal")

    # 2. Citizen B (Anonymous Signal B in Tenant B)
    code_b = "CODEBB"
    hash_b = hashlib.sha256(code_b.encode()).hexdigest()
    signal_b = Signal.objects.create(
        tenant=tenant_b,
        raw_text="Citizen B raw text",
        source_type=SourceType.TEXT,
        metadata={"anonymous_code": hash_b}
    )
    incident_b = Incident.objects.create(signal=signal_b, severity_score=0.4, severity_label="medium", domain="legal")

    # URLs
    status_a_url = reverse("citizen_signal_status_api", kwargs={"signal_id": signal_a.id})
    status_b_url = reverse("citizen_signal_status_api", kwargs={"signal_id": signal_b.id})
    verify_a_url = reverse("signals:verify_code", kwargs={"signal_id": signal_a.id})
    verify_b_url = reverse("signals:verify_code", kwargs={"signal_id": signal_b.id})

    # Coordinator User (For Tenant A)
    # Note: MVP relies on single active tenant default, which will resolve to first active tenant (Tenant A).
    # Incidents not belonging to Tenant A (like Tenant B's incident) will be blocked.
    user = User.objects.create_user(username="coord", password="pwd")
    token = str(RefreshToken.for_user(user).access_token)
    headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    # API Incident URLs
    detail_a_url = reverse("incidents:detail", kwargs={"id": incident_a.id})
    detail_b_url = reverse("incidents:detail", kwargs={"id": incident_b.id})

    # Test 1: Citizen A accesses Citizen A incident status (Unverified) -> Forbidden (403)
    response = client.get(status_a_url)
    assert response.status_code == 403

    # Verify code A
    response = client.post(verify_a_url, {"code": code_a}, content_type="application/json")
    assert response.status_code == 200
    assert response.json()["valid"] is True

    # Citizen A accesses Citizen A incident status (Verified) -> Allowed (200)
    response = client.get(status_a_url)
    assert response.status_code == 200

    # Test 2: Citizen A accesses Citizen B unverified anonymous status -> Forbidden (403)
    response = client.get(status_b_url)
    assert response.status_code == 403

    # Test 3: Anonymous user accesses unverified anonymous status -> Forbidden (403)
    # Using a clean client
    from django.test import Client
    clean_client = Client()
    response = clean_client.get(status_a_url)
    assert response.status_code == 403

    # Test 4: Verified Citizen A accesses Citizen B anonymous status -> Forbidden (403)
    # Client has verified signal A but not B
    response = client.get(status_b_url)
    assert response.status_code == 403

    # Test 5: Valid verification code for A + querying UUID of B -> Forbidden (403)
    response = client.post(verify_a_url, {"code": code_a}, content_type="application/json")
    assert response.status_code == 200
    response = client.get(status_b_url)
    assert response.status_code == 403

    # Test 6: Coordinator A accesses tenant-authorized incident A -> Allowed (200)
    response = client.get(detail_a_url, **headers)
    assert response.status_code == 200

    # Test 7: Coordinator A tries to retrieve Tenant B's incident B -> Not Found (404)
    response = client.get(detail_b_url, **headers)
    assert response.status_code == 404

    # Test 8: Coordinator A tries to mutate/resolve Tenant B's incident B -> Not Found (404)
    response = client.patch(detail_b_url, {"coordinator_status": "under_review"}, content_type="application/json", **headers)
    assert response.status_code == 404

    # Test 9: Unauthenticated coordinator dashboard access -> Redirects (302)
    response = client.get(reverse("coordinator_dashboard"))
    assert response.status_code == 302

    # Test 10: Invalid JWT on incident details -> Unauthorized (401)
    response = client.get(detail_a_url, HTTP_AUTHORIZATION="Bearer invalidtoken")
    assert response.status_code == 401

    # Test 11: Nonexistent incident UUID -> Not Found (404)
    import uuid
    nonexistent_url = reverse("incidents:detail", kwargs={"id": uuid.uuid4()})
    response = client.get(nonexistent_url, **headers)
    assert response.status_code == 404

    # Test 12: Repeated verify-code attempts -> Rate Limited (429)
    # Clear verify cache for client IP to start clean
    cache.clear()
    rate_limited = False
    for _ in range(10):
        # We need to use a clean client or simulate IP requests
        # Note: client IP rate limit triggers on the client IP remote address
        res = client.post(verify_a_url, {"code": "WRONG"}, content_type="application/json")
        if res.status_code == 429:
            rate_limited = True
            break
    assert rate_limited is True


