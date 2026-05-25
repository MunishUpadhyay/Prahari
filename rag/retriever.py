import logging
import chromadb
from chromadb.utils import embedding_functions

logger = logging.getLogger(__name__)


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
        client = chromadb.PersistentClient(path="rag/chroma_db")
        emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        collection = client.get_collection(
            name="legal_provisions",
            embedding_function=emb_fn
        )
        
        results = collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        formatted_results = []
        if not results or not results["documents"] or len(results["documents"]) == 0:
            return formatted_results
            
        for i in range(len(results["documents"][0])):
            text = results["documents"][0][i]
            metadata = results["metadatas"][0][i] if results["metadatas"] else {}
            distance = results["distances"][0][i] if results["distances"] else 0.0
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
        client = chromadb.PersistentClient(path="rag/chroma_db")
        emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        collection = client.get_collection(
            name="medical_protocols",
            embedding_function=emb_fn
        )
        
        results = collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        formatted_results = []
        if not results or not results["documents"] or len(results["documents"]) == 0:
            return formatted_results
            
        for i in range(len(results["documents"][0])):
            text = results["documents"][0][i]
            metadata = results["metadatas"][0][i] if results["metadatas"] else {}
            distance = results["distances"][0][i] if results["distances"] else 0.0
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
        client = chromadb.PersistentClient(path="rag/chroma_db")
        emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        
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


