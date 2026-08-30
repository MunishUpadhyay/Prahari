import pytest
from unittest.mock import MagicMock, patch
from django.db import OperationalError
from django.utils import timezone
from apps.signals.models import Signal, SourceType
from apps.incidents.models import Incident
from apps.tenants.models import Tenant
from apps.audit.models import AuditLog
from pipeline.tasks import route_to_agents, push_to_websocket

@pytest.mark.django_db
def test_audit_log_creation_and_hash_generation():
    tenant = Tenant.objects.create(name="Test Tenant", is_active=True)
    signal = Signal.objects.create(tenant=tenant, raw_text="Emergency test", source_type=SourceType.TEXT)
    incident = Incident.objects.create(
        signal=signal,
        severity_score=0.5,
        severity_label="medium",
        domain="health"
    )

    # 1. AuditLog can be created
    log = AuditLog.objects.create(
        incident=incident,
        action="incident_created",
        performed_by="system/pipeline",
        payload={"reason": "test"}
    )
    assert log.id is not None
    assert log.action == "incident_created"
    assert log.performed_by == "system/pipeline"
    assert log.payload == {"reason": "test"}

    # 2. Hash is automatically generated
    assert log.hash is not None
    assert len(log.hash) == 64  # SHA-256 hex digest length

    # 3. Hash is deterministic
    computed = log.compute_hash()
    assert log.hash == computed

    # 4. Changing protected data invalidates the expected hash
    original_hash = log.hash
    log.action = "status_changed"  # Modify protected field
    # The stored hash doesn't change until save() is called, but compute_hash() will now be different
    new_computed = log.compute_hash()
    assert original_hash != new_computed

@pytest.mark.django_db
def test_audit_log_event_helper():
    tenant = Tenant.objects.create(name="Test Tenant", is_active=True)
    signal = Signal.objects.create(tenant=tenant, raw_text="Emergency test", source_type=SourceType.TEXT)
    incident = Incident.objects.create(
        signal=signal,
        severity_score=0.5,
        severity_label="medium",
        domain="health"
    )

    # Verify log_event helper functions correctly
    log = AuditLog.log_event(
        incident=incident,
        action="test_action",
        performed_by="test_user",
        payload={"foo": "bar"}
    )
    assert log is not None
    assert log.action == "test_action"
    assert log.performed_by == "test_user"
    assert log.payload == {"foo": "bar"}

@pytest.mark.django_db
def test_non_blocking_audit_failure(monkeypatch):
    tenant = Tenant.objects.create(name="Test Tenant", is_active=True)
    signal = Signal.objects.create(tenant=tenant, raw_text="Emergency test", source_type=SourceType.TEXT)
    incident = Incident.objects.create(
        signal=signal,
        severity_score=0.5,
        severity_label="medium",
        domain="health"
    )

    # Mock AuditLog.objects.create to raise a database OperationalError
    def mock_create(*args, **kwargs):
        raise OperationalError("Database save failed")
    
    monkeypatch.setattr(AuditLog.objects, "create", mock_create)

    # Calling log_event should catch the exception and return None instead of crashing
    log = AuditLog.log_event(
        incident=incident,
        action="test_failed_action",
        performed_by="test_user"
    )
    assert log is None  # Caught and logged without throwing exception

@pytest.mark.django_db
def test_pipeline_incident_created_audit(monkeypatch, mock_groq):
    tenant = Tenant.objects.create(name="Test Tenant", is_active=True)
    signal = Signal.objects.create(tenant=tenant, raw_text="Urgent help needed", source_type=SourceType.TEXT)

    actual_task = route_to_agents._get_current_object()
    mock_request = MagicMock()
    mock_request.retries = 0
    monkeypatch.setattr(type(actual_task), "request", property(lambda self: mock_request))

    # Clean audit logs initially
    assert AuditLog.objects.count() == 0

    # Run route_to_agents task which creates the incident
    route_to_agents.run(str(signal.id), {"domain": "health"})

    # Verify incident_created log was written
    incident = Incident.objects.get(signal=signal)
    logs = AuditLog.objects.filter(incident=incident, action="incident_created")
    assert logs.count() == 1
    assert logs[0].performed_by == "system/pipeline"

    # Verify no secrets are stored in payload
    payload = logs[0].payload
    assert "api_key" not in payload
    assert "token" not in payload

@pytest.mark.django_db
def test_pipeline_completed_audit(monkeypatch, mock_groq):
    tenant = Tenant.objects.create(name="Test Tenant", is_active=True)
    signal = Signal.objects.create(tenant=tenant, raw_text="Urgent help needed", source_type=SourceType.TEXT)
    incident = Incident.objects.create(
        signal=signal,
        severity_score=0.5,
        severity_label="medium",
        domain="health",
        agent_outputs={}
    )

    actual_task = push_to_websocket._get_current_object()
    mock_request = MagicMock()
    mock_request.retries = 0
    monkeypatch.setattr(type(actual_task), "request", property(lambda self: mock_request))

    # Run push_to_websocket task
    push_to_websocket.run(str(incident.id), {"situation_title": "Completed"})

    # Verify pipeline_completed log was written
    logs = AuditLog.objects.filter(incident=incident, action="pipeline_completed")
    assert logs.count() == 1
    assert logs[0].performed_by == "system/pipeline"

@pytest.mark.django_db
def test_pipeline_completed_idempotency(monkeypatch, mock_groq):
    tenant = Tenant.objects.create(name="Test Tenant", is_active=True)
    signal = Signal.objects.create(tenant=tenant, raw_text="Urgent help", source_type=SourceType.TEXT)
    incident = Incident.objects.create(
        signal=signal,
        severity_score=0.5,
        severity_label="medium",
        domain="health",
        agent_outputs={}
    )

    actual_task = push_to_websocket._get_current_object()
    mock_request = MagicMock()
    mock_request.retries = 0
    monkeypatch.setattr(type(actual_task), "request", property(lambda self: mock_request))

    # Pre-create a pipeline_completed log to simulate a previously completed execution
    AuditLog.objects.create(
        incident=incident,
        action="pipeline_completed",
        performed_by="system/pipeline"
    )
    assert AuditLog.objects.filter(incident=incident, action="pipeline_completed").count() == 1

    # Run task again
    push_to_websocket.run(str(incident.id), {"situation_title": "Completed"})

    # Verify that no duplicate logs were created
    assert AuditLog.objects.filter(incident=incident, action="pipeline_completed").count() == 1

@pytest.mark.django_db
def test_incident_resolved_api_audit(client):
    tenant = Tenant.objects.create(name="Test Tenant", is_active=True)
    signal = Signal.objects.create(tenant=tenant, raw_text="Resolved issue", source_type=SourceType.TEXT)
    incident = Incident.objects.create(
        signal=signal,
        severity_score=0.5,
        severity_label="medium",
        domain="health"
    )

    # Create and authenticate a coordinator user
    from django.contrib.auth.models import User
    from rest_framework_simplejwt.tokens import RefreshToken
    user = User.objects.create_user(username="coordinator_bob", password="password")
    token = str(RefreshToken.for_user(user).access_token)

    # Send status change patch
    response = client.patch(
        f"/api/incidents/{incident.id}/",
        data={"coordinator_status": "resolved"},
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token}"
    )
    assert response.status_code == 200

    # Verify incident is resolved and audit log is written with username
    incident.refresh_from_db()
    assert incident.is_resolved is True
    assert incident.coordinator_status == "resolved"

    logs = AuditLog.objects.filter(incident=incident, action="incident_resolved")
    assert logs.count() == 1
    assert logs[0].performed_by == "coordinator_bob"

@pytest.mark.django_db
def test_incident_resolved_dashboard_audit(client):
    tenant = Tenant.objects.create(name="Test Tenant", is_active=True)
    signal = Signal.objects.create(tenant=tenant, raw_text="Resolved issue", source_type=SourceType.TEXT)
    incident = Incident.objects.create(
        signal=signal,
        severity_score=0.5,
        severity_label="medium",
        domain="health"
    )

    from django.contrib.auth.models import User
    user = User.objects.create_user(username="coordinator_alice", password="password", is_staff=True)
    client.force_login(user)

    # Post to dashboard resolve URL
    response = client.post(f"/coordinator/incident/{incident.id}/resolve/")
    assert response.status_code == 200

    incident.refresh_from_db()
    assert incident.is_resolved is True

    logs = AuditLog.objects.filter(incident=incident, action="incident_resolved")
    assert logs.count() == 1
    assert logs[0].performed_by == "coordinator_alice"
