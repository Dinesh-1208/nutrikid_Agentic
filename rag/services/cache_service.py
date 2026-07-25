import time
import numpy as np
from collections import OrderedDict
from typing import Dict, Any, List, Optional, Tuple
from rag.services.base import ICacheService, BaseService

class CacheService(ICacheService, BaseService):
    """
    LRU Semantic Cache Service using vector cosine similarity matching.
    """
    def __init__(self, max_size: int = 1000, similarity_threshold: float = 0.95):
        self.max_size = max_size
        self.similarity_threshold = similarity_threshold
        self.cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def _normalize_query(self, query: str) -> str:
        return " ".join(query.strip().lower().split())

    def get(self, query: str, query_embedding: np.ndarray, current_dataset_hash: str) -> Optional[Tuple[List[Dict[str, Any]], float]]:
        if not self.cache:
            self.misses += 1
            return None

        normalized_q = self._normalize_query(query)
        emb = np.squeeze(np.asarray(query_embedding, dtype=np.float32))
        norm = np.linalg.norm(emb)
        if norm > 0:
            emb = emb / norm

        best_key = None
        best_score = -1.0
        best_entry = None

        keys_to_delete = []
        for key, entry in list(self.cache.items()):
            # Invalidate if dataset hash changed
            if entry.get("dataset_hash") != current_dataset_hash:
                keys_to_delete.append(key)
                continue

            if entry.get("normalized_query") == normalized_q:
                best_key = key
                best_score = 1.0
                best_entry = entry
                break

            cached_emb = entry["embedding"]
            score = float(np.dot(emb, cached_emb))
            if score > best_score:
                best_score = score
                best_key = key
                best_entry = entry

        for k in keys_to_delete:
            del self.cache[k]

        if best_entry and best_score >= self.similarity_threshold:
            self.cache.move_to_end(best_key)
            self.hits += 1
            return best_entry["retrieved_context"], best_score

        self.misses += 1
        return None

    def put(
        self,
        query: str,
        query_embedding: np.ndarray,
        retrieved_context: List[Dict[str, Any]],
        current_dataset_hash: str
    ):
        normalized_q = self._normalize_query(query)
        emb = np.squeeze(np.asarray(query_embedding, dtype=np.float32))
        norm = np.linalg.norm(emb)
        if norm > 0:
            emb = emb / norm

        chunk_ids = [c.get("id") for c in retrieved_context if isinstance(c, dict)]

        entry = {
            "query_text": query,
            "normalized_query": normalized_q,
            "embedding": emb,
            "retrieved_chunk_ids": chunk_ids,
            "retrieved_context": retrieved_context,
            "timestamp": time.time(),
            "dataset_hash": current_dataset_hash
        }

        if normalized_q in self.cache:
            self.cache[normalized_q] = entry
            self.cache.move_to_end(normalized_q)
        else:
            if len(self.cache) >= self.max_size:
                self.cache.popitem(last=False)
                self.evictions += 1
            self.cache[normalized_q] = entry

    def invalidate(self):
        self.cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        total = self.hits + self.misses
        hit_ratio = (self.hits / total) if total > 0 else 0.0
        return {
            "cache_size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "total_queries": total,
            "hit_ratio": round(hit_ratio, 4)
        }
