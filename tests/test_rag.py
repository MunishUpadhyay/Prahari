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

def test_retrieve_legal_provisions_mocked(settings):
    settings.USE_ZERO_MEMORY_RAG = False
    results = retrieve_legal_provisions("Test query", n_results=3)
    assert len(results) > 0
    assert results[0]["text"] == "Mock provisions/protocols document"
    assert results[0]["distance"] == 0.15

def test_retrieve_medical_protocols_mocked(settings):
    settings.USE_ZERO_MEMORY_RAG = False
    results = retrieve_medical_protocols("Test query", n_results=2)
    assert len(results) > 0
    assert results[0]["text"] == "Mock provisions/protocols document"

def test_retrieve_similar_incidents_mocked(settings):
    settings.USE_ZERO_MEMORY_RAG = False
    results = retrieve_similar_incidents("Test query", n_results=3)
    assert isinstance(results, list)

def test_retriever_fails_gracefully(mock_chromadb, settings):
    settings.USE_ZERO_MEMORY_RAG = False
    mock_chromadb.get_collection.side_effect = Exception("Database connection lost")
    results = retrieve_legal_provisions("Test query")
    assert results == []

def test_zero_memory_rag_mode_bypasses_model_loading(settings, monkeypatch):
    """
    Verify that in zero-memory RAG mode (USE_ZERO_MEMORY_RAG=True):
    1. retrieve_legal_provisions returns fallback results.
    2. retrieve_medical_protocols returns fallback results.
    3. retrieve_similar_incidents returns fallback results.
    4. get_embedding_function is NEVER called.
    """
    settings.USE_ZERO_MEMORY_RAG = True
    
    # Monkeypatch get_embedding_function to raise an error if called
    def fail_if_called():
        raise RuntimeError("get_embedding_function should NOT be called in zero-memory mode!")
        
    monkeypatch.setattr("rag.retriever.get_embedding_function", fail_if_called)
    monkeypatch.setattr("rag.retriever.get_chroma_client", fail_if_called)
    
    # Test legal retrieval
    legal_res = retrieve_legal_provisions("salary unpaid employee")
    assert isinstance(legal_res, list)
    assert len(legal_res) > 0
    assert "code" in legal_res[0]["metadata"]
    
    # Test medical retrieval
    med_res = retrieve_medical_protocols("heart attack chest pain")
    assert isinstance(med_res, list)
    assert len(med_res) > 0
    assert "title" in med_res[0]["metadata"]
    
    # Test similar incidents retrieval
    similar_res = retrieve_similar_incidents("tenant landlord dispute")
    assert isinstance(similar_res, list)

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
