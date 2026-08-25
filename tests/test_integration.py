import pytest
from apps.signals.models import Signal, SourceType
from apps.tenants.models import Tenant
from apps.incidents.models import Incident
from pipeline.tasks import ingest_signal

@pytest.mark.django_db
def test_mocked_pipeline_integration(mock_groq):
    tenant = Tenant.objects.create(name="Test Tenant", is_active=True)
    signal = Signal.objects.create(
        tenant=tenant,
        raw_text="Urgent: Patient is denied admission and requires immediate aid.",
        source_type=SourceType.TEXT,
        preferred_language="hindi"
    )
    
    # Run the pipeline synchronously
    ingest_signal.delay(str(signal.id))
    
    # Refresh and assert
    signal.refresh_from_db()
    assert signal.status == "processed"
    assert signal.domain == "cross"  # Normalized to cross in route_to_agents
    
    # Assert Incident creation
    incident = Incident.objects.get(signal=signal)
    assert incident.severity_label == "high" # Max score is 0.8 (cross domain mapping score) -> high
    assert incident.situation_brief == "A summarized brief of the incident."
    
    # Check agent outputs are present
    outputs = incident.agent_outputs
    assert "sentinel" in outputs
    assert "triage" in outputs
    assert "rights" in outputs
    assert "coordination" in outputs
    assert "language" in outputs
