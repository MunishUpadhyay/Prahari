import logging
import threading
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from django.conf import settings

logger = logging.getLogger(__name__)

_client_lock = threading.Lock()
_emb_fn_lock = threading.Lock()

_cached_client = None
_cached_client_class = None

_cached_emb_fn = None
_cached_emb_fn_class = None


def get_chroma_client():
    """
    Lazy process-local singleton for Chroma PersistentClient.
    Tracks client class to support test monkeypatching smoothly.
    """
    global _cached_client, _cached_client_class
    current_class = chromadb.PersistentClient
    if _cached_client is None or _cached_client_class != current_class:
        with _client_lock:
            if _cached_client is None or _cached_client_class != current_class:
                _cached_client = chromadb.PersistentClient(
                    path="rag/chroma_db",
                    settings=Settings(anonymized_telemetry=False)
                )
                _cached_client_class = current_class
    return _cached_client


def get_embedding_function():
    """
    Lazy process-local singleton for SentenceTransformerEmbeddingFunction.
    Tracks embedding function class to support test monkeypatching smoothly.
    """
    global _cached_emb_fn, _cached_emb_fn_class
    current_class = embedding_functions.SentenceTransformerEmbeddingFunction
    if _cached_emb_fn is None or _cached_emb_fn_class != current_class:
        with _emb_fn_lock:
            if _cached_emb_fn is None or _cached_emb_fn_class != current_class:
                _cached_emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name="all-MiniLM-L6-v2"
                )
                _cached_emb_fn_class = current_class
    return _cached_emb_fn


def retrieve_legal_provisions(query: str, n_results: int = 3) -> list[dict]:
    """
    Retrieve the top n_results most relevant legal provisions for a query.

    Args:
        query (str): The search query (e.g. signal text).
        n_results (int): Number of provisions to retrieve.

    Returns:
        list[dict]: List of dicts with keys "text", "metadata", "distance".
    """
    logger.info("Retrieving legal provisions for query: %r", query)
    try:
        client = get_chroma_client()
        emb_fn = get_embedding_function()
        collection = client.get_collection(
            name="legal_provisions",
            embedding_function=emb_fn
        )
        
        results = collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        # Centralized configurable threshold (lowered to 0.85 to prevent irrelevant retrieval)
        max_dist = getattr(settings, "RAG_LEGAL_DISTANCE_THRESHOLD", 0.85)
        
        formatted_results = []
        if not results or not results["documents"] or len(results["documents"]) == 0:
            return formatted_results
            
        for i in range(len(results["documents"][0])):
            distance = results["distances"][0][i] if results["distances"] else 0.0
            if distance > max_dist:
                logger.info(
                    "[retrieve_legal_provisions] Discarding result distance=%s > max_dist=%s",
                    distance, max_dist
                )
                continue
            text = results["documents"][0][i]
            metadata = results["metadatas"][0][i] if results["metadatas"] else {}
            formatted_results.append({
                "text": text,
                "metadata": metadata,
                "distance": distance
            })
            
        return formatted_results
    except Exception as e:
        logger.exception("Error during legal provisions retrieval: %s", e)
        return []


def retrieve_medical_protocols(query: str, n_results: int = 3) -> list[dict]:
    """
    Retrieve the top n_results most relevant medical protocols for a query.

    Args:
        query (str): The search query (e.g. signal text).
        n_results (int): Number of protocols to retrieve.

    Returns:
        list[dict]: List of dicts with keys "text", "metadata", "distance".
    """
    logger.info("Retrieving medical protocols for query: %r", query)
    try:
        client = get_chroma_client()
        emb_fn = get_embedding_function()
        collection = client.get_collection(
            name="medical_protocols",
            embedding_function=emb_fn
        )
        
        results = collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        # Centralized configurable threshold
        max_dist = getattr(settings, "RAG_MEDICAL_DISTANCE_THRESHOLD", 1.1)
        
        formatted_results = []
        if not results or not results["documents"] or len(results["documents"]) == 0:
            return formatted_results
            
        for i in range(len(results["documents"][0])):
            distance = results["distances"][0][i] if results["distances"] else 0.0
            if distance > max_dist:
                logger.info(
                    "[retrieve_medical_protocols] Discarding result distance=%s > max_dist=%s",
                    distance, max_dist
                )
                continue
            text = results["documents"][0][i]
            metadata = results["metadatas"][0][i] if results["metadatas"] else {}
            formatted_results.append({
                "text": text,
                "metadata": metadata,
                "distance": distance
            })
            
        return formatted_results
    except Exception as e:
        logger.exception("Error during medical protocols retrieval: %s", e)
        return []


def retrieve_similar_incidents(query: str,
                               n_results: int = 3,
                               exclude_id: str = None
                               ) -> list[dict]:
    """
    Retrieve top similar incidents from ChromaDB 'incident_history' collection,
    optionally excluding a specific incident_id (e.g., the current incident).
    """
    logger.info("Retrieving similar incidents for query: %r (exclude_id: %s)", query, exclude_id)
    try:
        client = get_chroma_client()
        emb_fn = get_embedding_function()
        
        # Access the collection safely. Return empty list if collection doesn't exist yet.
        try:
            collection = client.get_collection(
                name="incident_history",
                embedding_function=emb_fn
            )
        except Exception:
            logger.info("Collection 'incident_history' does not exist yet. Returning empty list.")
            return []
            
        # Build query parameters with metadata filter if exclude_id is provided
        query_kwargs = {
            "query_texts": [query],
            "n_results": n_results
        }
        if exclude_id:
            query_kwargs["where"] = {"incident_id": {"$ne": str(exclude_id)}}
            
        results = collection.query(**query_kwargs)
        
        formatted_results = []
        if not results or not results["documents"] or len(results["documents"]) == 0:
            return formatted_results
            
        for i in range(len(results["documents"][0])):
            text = results["documents"][0][i]
            metadata = results["metadatas"][0][i] if results["metadatas"] else {}
            distance = results["distances"][0][i] if results["distances"] else 0.0
            
            # Convert distance to similarity score: similarity = 1 / (1 + distance)
            similarity_score = float(round(1.0 / (1.0 + distance), 4))
            
            formatted_results.append({
                "incident_id": metadata.get("incident_id"),
                "situation_brief": text,
                "domain": metadata.get("domain"),
                "severity": metadata.get("severity"),
                "resolved": bool(metadata.get("resolved", False)),
                "similarity_score": similarity_score
            })
            
        return formatted_results
    except Exception as e:
        logger.exception("Error during similar incidents retrieval: %s", e)
        return []


