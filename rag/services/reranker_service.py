from typing import List, Dict, Any
from rag.services.base import IRerankerService, BaseService

class RerankerService(IRerankerService, BaseService):
    """
    Service wrapping Cross-Encoder joint attention scoring.
    """
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2", enabled: bool = True):
        self.model_name = model_name
        self.enabled = enabled
        self.model = None

    def _lazy_load(self):
        if self.model is None and self.enabled:
            from sentence_transformers import CrossEncoder
            self.model = CrossEncoder(self.model_name)

    def rerank(self, query: str, candidates: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
        if not self.enabled or not candidates:
            return candidates[:top_k]

        self._lazy_load()
        if self.model is None:
            return candidates[:top_k]

        pairs = [[query, candidate.get("text", "")] for candidate in candidates]
        scores = self.model.predict(pairs)

        reranked = []
        for candidate, score in zip(candidates, scores):
            item = candidate.copy()
            item["rerank_score"] = float(score)
            item["score"] = float(score)
            reranked.append(item)

        reranked.sort(key=lambda x: x["rerank_score"], reverse=True)
        return reranked[:top_k]
