import pytest
import sys
from unittest.mock import MagicMock
from rag.retriever import (
    retrieve_legal_provisions,
    retrieve_medical_protocols,
    retrieve_similar_incidents,
    get_chroma_client,
    get_embedding_function,
)

def test_retrieve_legal_provisions_mocked():
    results = retrieve_legal_provisions("Test query", n_results=3)
    assert len(results) > 0
    assert results[0]["text"] == "Mock provisions/protocols document"
    assert results[0]["distance"] == 0.15

def test_retrieve_medical_protocols_mocked():
    results = retrieve_medical_protocols("Test query", n_results=2)
    assert len(results) > 0
    assert results[0]["text"] == "Mock provisions/protocols document"

def test_retrieve_similar_incidents_mocked():
    results = retrieve_similar_incidents("Test query", n_results=3)
    assert isinstance(results, list)

def test_retriever_fails_gracefully(mock_chromadb):
    mock_chromadb.get_collection.side_effect = Exception("Database connection lost")
    results = retrieve_legal_provisions("Test query")
    assert results == []

def test_module_imports_lazy_rag():
    """
    Verify that importing apps.incidents.views and apps.agents.agents
    does not throw errors and can be loaded without eager RAG initialization.
    """
    import apps.incidents.views
    import apps.agents.agents
    assert True

def test_rag_singleton_caching():
    """
    Verify that repeated calls to get_chroma_client and get_embedding_function
    return the exact same cached instance.
    """
    client1 = get_chroma_client()
    client2 = get_chroma_client()
    assert client1 is client2

    emb1 = get_embedding_function()
    emb2 = get_embedding_function()
    assert emb1 is emb2

def test_timeout_status_response_includes_steps(db, client):
    """
    Verify that when a signal times out, citizen_signal_status_api returns
    status: 'pipeline_error' AND includes the 'steps' dict.
    """
    from datetime import timedelta
    from django.utils import timezone
    from django.urls import reverse
    from apps.signals.models import Signal
    from apps.tenants.models import Tenant

    tenant, _ = Tenant.objects.get_or_create(
        name="Test Tenant",
        defaults={"api_key_hash": Tenant.hash_api_key("test_key")}
    )
    
    old_time = timezone.now() - timedelta(minutes=15)
    signal = Signal.objects.create(
        tenant=tenant,
        raw_text="Test incident description",
        status="processing",
        domain="legal"
    )
    Signal.objects.filter(id=signal.id).update(created_at=old_time)
    
    session = client.session
    session[f"verified_{signal.id}"] = True
    session.save()
    
    url = reverse("citizen_signal_status_api", kwargs={"signal_id": signal.id})
    response = client.get(url)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pipeline_error"
    assert data["message"] == "Pipeline timed out"
    assert "steps" in data
    assert data["steps"]["received"] is True
    assert data["steps"]["classified"] is True
    assert data["steps"]["analyzed"] is False
