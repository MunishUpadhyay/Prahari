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


import re


def _norm_word(w: str) -> str:
    w = w.lower()
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("es") and len(w) > 4:
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def _fallback_legal_search(query: str, n_results: int = 3) -> list[dict]:
    """Zero-memory keyword fallback search against VERIFIED_LEGAL_DATABASE."""
    try:
        from apps.agents.legal_reference import VERIFIED_LEGAL_DATABASE
        stop_words = {"the", "a", "an", "is", "and", "or", "in", "on", "of", "to", "for", "with", "my", "me", "i", "without", "need", "after", "from", "but", "by", "from"}
        raw_words = [w.lower() for w in re.findall(r'\w+', query) if w.lower() not in stop_words]
        norm_query_words = {_norm_word(w) for w in raw_words}
        if not norm_query_words:
            return []
        scored = []
        for (code, sec), rec in VERIFIED_LEGAL_DATABASE.items():
            text_corpus = f"{code} {sec} {rec['title']} {rec['statutory_text']}".lower()
            corpus_words = {_norm_word(w) for w in re.findall(r'\w+', text_corpus)}
            overlap = norm_query_words.intersection(corpus_words)
            score = len(overlap)
            if score > 0:
                doc_str = f"{code} Section {sec} — {rec['title']}. Statutory Text: {rec['statutory_text']}"
                meta = {
                    "code": code,
                    "section": sec,
                    "title": rec["title"],
                    "category": rec["type"],
                    "legacy_code": rec.get("legacy_code") or "None",
                    "legacy_section": rec.get("legacy_section") or "None",
                    "verified": "True"
                }
                scored.append({
                    "text": doc_str,
                    "metadata": meta,
                    "distance": max(0.1, round(1.0 - (score / (len(norm_query_words) + 1)), 2)),
                    "score": score
                })
        scored.sort(key=lambda x: x["score"], reverse=True)
        return [{
            "text": item["text"],
            "metadata": item["metadata"],
            "distance": item["distance"]
        } for item in scored[:n_results]]
    except Exception as e:
        logger.warning("Fallback legal search error: %s", e)
        return []


def _fallback_medical_search(query: str, n_results: int = 3) -> list[dict]:
    """Zero-memory keyword fallback search against VERIFIED_MEDICAL_DATABASE."""
    try:
        from apps.agents.medical_reference import VERIFIED_MEDICAL_DATABASE
        stop_words = {"the", "a", "an", "is", "and", "or", "in", "on", "of", "to", "for", "with", "my", "me", "i", "without", "need"}
        words = set(re.findall(r'\w+', query.lower())) - stop_words
        if not words:
            return []
        scored = []
        for key, rec in VERIFIED_MEDICAL_DATABASE.items():
            text_corpus = f"{rec.get('title', '')} {rec.get('category', '')} {rec.get('act', '')} {rec.get('statutory_text', '')}".lower()
            score = sum(1 for w in words if w in text_corpus)
            if score > 0:
                doc_str = f"Medical Protocol: {rec.get('title')}. Category: {rec.get('category')}. Details: {rec.get('statutory_text')}"
                meta = {
                    "title": rec.get("title"),
                    "category": rec.get("category"),
                    "act": rec.get("act"),
                    "verified": "True"
                }
                scored.append({
                    "text": doc_str,
                    "metadata": meta,
                    "distance": max(0.1, round(1.0 - (score / (len(words) + 1)), 2)),
                    "score": score
                })
        scored.sort(key=lambda x: x["score"], reverse=True)
        return [{
            "text": item["text"],
            "metadata": item["metadata"],
            "distance": item["distance"]
        } for item in scored[:n_results]]
    except Exception as e:
        logger.warning("Fallback medical search error: %s", e)
        return []


def _fallback_similar_incidents_search(query: str,
                                       n_results: int = 3,
                                       exclude_id: str = None
                                       ) -> list[dict]:
    """Zero-memory SQL/keyword search against Incident DB for similar incidents."""
    try:
        from apps.incidents.models import Incident
        qs = Incident.objects.all()
        if exclude_id:
            qs = qs.exclude(id=exclude_id)
            
        stop_words = {"the", "a", "an", "is", "and", "or", "in", "on", "of", "to", "for", "with", "my", "me", "i", "without", "need", "report"}
        raw_words = [w.lower() for w in re.findall(r'\w+', query) if w.lower() not in stop_words]
        norm_words = {_norm_word(w) for w in raw_words}
        if not norm_words:
            return []
            
        incidents = list(qs.select_related("signal")[:50])
        scored = []
        for inc in incidents:
            text = f"{inc.situation_brief or ''} {inc.signal.raw_text if inc.signal else ''}".lower()
            corpus_words = {_norm_word(w) for w in re.findall(r'\w+', text)}
            overlap = norm_words.intersection(corpus_words)
            score = len(overlap)
            if score > 0:
                sim_score = float(round(min(0.95, score / (len(norm_words) + 1)), 4))
                scored.append({
                    "incident_id": str(inc.id),
                    "situation_brief": inc.situation_brief or (inc.signal.raw_text[:120] if inc.signal else "Civic incident report"),
                    "domain": inc.domain,
                    "severity": inc.severity,
                    "resolved": inc.status in ["resolved", "closed"],
                    "similarity_score": sim_score,
                    "score": score
                })
        scored.sort(key=lambda x: x["score"], reverse=True)
        return [{
            "incident_id": item["incident_id"],
            "situation_brief": item["situation_brief"],
            "domain": item["domain"],
            "severity": item["severity"],
            "resolved": item["resolved"],
            "similarity_score": item["similarity_score"]
        } for item in scored[:n_results]]
    except Exception as e:
        logger.warning("Fallback similar incidents search error: %s", e)
        return []


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
    if getattr(settings, "USE_ZERO_MEMORY_RAG", True):
        logger.info("[retrieve_legal_provisions] Zero-memory mode active. Bypassing SentenceTransformer/Chroma.")
        return _fallback_legal_search(query, n_results)

    try:
        client = get_chroma_client()
        try:
            collection = client.get_collection(name="legal_provisions")
            emb_fn = get_embedding_function()
            collection._embedding_function = emb_fn
        except Exception:
            logger.info("Collection 'legal_provisions' missing. Using zero-memory statutory database fallback matcher.")
            return _fallback_legal_search(query, n_results)
        
        results = collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        try:
            max_dist = getattr(settings, "RAG_LEGAL_DISTANCE_THRESHOLD", 0.85)
        except Exception:
            max_dist = 0.85
        
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
        logger.exception("Error during legal provisions retrieval: %s. Using zero-memory fallback.", e)
        return _fallback_legal_search(query, n_results)


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
    if getattr(settings, "USE_ZERO_MEMORY_RAG", True):
        logger.info("[retrieve_medical_protocols] Zero-memory mode active. Bypassing SentenceTransformer/Chroma.")
        return _fallback_medical_search(query, n_results)

    try:
        client = get_chroma_client()
        try:
            collection = client.get_collection(name="medical_protocols")
            emb_fn = get_embedding_function()
            collection._embedding_function = emb_fn
        except Exception:
            logger.info("Collection 'medical_protocols' missing. Using zero-memory medical database fallback matcher.")
            return _fallback_medical_search(query, n_results)
        
        results = collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        try:
            max_dist = getattr(settings, "RAG_MEDICAL_DISTANCE_THRESHOLD", 1.1)
        except Exception:
            max_dist = 1.1
        
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
        logger.exception("Error during medical protocols retrieval: %s. Using zero-memory fallback.", e)
        return _fallback_medical_search(query, n_results)


def retrieve_similar_incidents(query: str,
                               n_results: int = 3,
                               exclude_id: str = None
                               ) -> list[dict]:
    """
    Retrieve top similar incidents from ChromaDB 'incident_history' collection,
    optionally excluding a specific incident_id (e.g., the current incident).
    """
    logger.info("Retrieving similar incidents for query: %r (exclude_id: %s)", query, exclude_id)
    if getattr(settings, "USE_ZERO_MEMORY_RAG", True):
        logger.info("[retrieve_similar_incidents] Zero-memory mode active. Bypassing SentenceTransformer/Chroma.")
        return _fallback_similar_incidents_search(query, n_results, exclude_id)

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


