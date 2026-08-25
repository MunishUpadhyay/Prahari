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
