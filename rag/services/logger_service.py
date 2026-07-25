import logging
import json
from typing import Dict, Any, List, Optional
from rag.services.base import BaseService

class LoggerService(BaseService):
    """
    Service responsible for structured JSON logging of retrieval events.
    """
    def __init__(self, name: str = "KidsNutriRAG", level: int = logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)

        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s")
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def log_retrieval_event(
        self,
        query: str,
        cache_hit: bool,
        retrieved_chunk_ids: List[str],
        retrieval_scores: List[float],
        rerank_scores: Optional[List[float]],
        metadata_filters: Optional[Dict[str, Any]],
        latencies: Dict[str, float],
        dataset_hash: str
    ):
        log_payload = {
            "query": query,
            "cache_status": "HIT" if cache_hit else "MISS",
            "retrieved_chunk_ids": retrieved_chunk_ids,
            "retrieval_scores": [round(s, 4) for s in retrieval_scores],
            "rerank_scores": [round(s, 4) for s in rerank_scores] if rerank_scores else [],
            "metadata_filters": metadata_filters or {},
            "latencies_ms": latencies,
            "dataset_version_hash": dataset_hash[:12] + "..." if dataset_hash else "N/A"
        }
        self.logger.info(f"RETRIEVAL_EVENT: {json.dumps(log_payload)}")

    def info(self, msg: str):
        self.logger.info(msg)

    def warning(self, msg: str):
        self.logger.warning(msg)

    def error(self, msg: str):
        self.logger.error(msg)
