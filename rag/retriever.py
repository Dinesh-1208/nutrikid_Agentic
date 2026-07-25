import os
from typing import List, Dict, Any, Optional

from rag.services.config_service import ConfigurationService, RAGConfig
from rag.services.retrieval_service import RetrievalService

class KidsNutriRetriever:
    """
    Facade class wrapping RetrievalService for 100% backward compatibility.
    Guarantees seamless integration with CLI main.py, Evaluator, Comparator, and Notebooks.
    """
    def __init__(self, index_dir: Optional[str] = None, model_name: str = "BAAI/bge-small-en-v1.5", config: Optional[RAGConfig] = None):
        if config is None:
            config = RAGConfig(embedding_model=model_name)
        if index_dir is not None:
            config.index_dir = index_dir

        config_service = ConfigurationService(config=config)
        self.service = RetrievalService(config_service=config_service)
        self.config = config

    @property
    def model(self):
        """Exposes embedding model instance for backward compatibility (e.g. evaluator.py)."""
        self.service.embedding_service._lazy_load()
        return self.service.embedding_service.model

    @property
    def metadata(self):
        """Exposes metadata items list for backward compatibility."""
        return self.service.child_chunks

    @property
    def cache(self):
        """Exposes cache service for stats and debugging."""
        return self.service.cache_service

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        metadata_filters: Optional[Dict[str, Any]] = None,
        mode: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        return self.service.retrieve(query=query, top_k=top_k, metadata_filters=metadata_filters, mode=mode)

    def debug_retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        results = self.retrieve(query, top_k=top_k)
        print(f"\n--- RAG Retrieval Debug for Query: '{query}' ---")
        stats = self.cache.get_stats()
        print(f"Cache Stats: Hits={stats['hits']} | Misses={stats['misses']} | Hit Ratio={stats['hit_ratio']}")
        for i, res in enumerate(results, 1):
            print(f"\n[{i}] Score: {res['score']:.4f} | ID: {res['id']}")
            print(f"Text: {res['text']}")
            print(f"Metadata: {res['metadata']}")
        return results

if __name__ == '__main__':
    try:
        retriever = KidsNutriRetriever()
        retriever.debug_retrieve("Can my child eat egg during fever?", top_k=3)
    except Exception as e:
        print(f"Retriever test error: {e}")
