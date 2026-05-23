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


