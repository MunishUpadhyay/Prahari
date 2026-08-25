import pytest
from unittest.mock import MagicMock
from rag.retriever import retrieve_legal_provisions, retrieve_medical_protocols, retrieve_similar_incidents

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
    # Returns empty or formatted results depending on collection existence mock
    assert isinstance(results, list)

def test_retriever_fails_gracefully(mock_chromadb):
    # Force chroma collection query to raise an exception
    mock_chromadb.get_collection.side_effect = Exception("Database connection lost")
    results = retrieve_legal_provisions("Test query")
    # Should catch exception and return empty list gracefully
    assert results == []
