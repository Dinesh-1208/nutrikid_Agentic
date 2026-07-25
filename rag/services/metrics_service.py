import time
from typing import Dict, Any, List
from rag.services.base import BaseService

class MetricsService(BaseService):
    """
    Microsecond-granularity latency timer and performance collector.
    """
    def __init__(self):
        self.history: List[Dict[str, Any]] = []

    def create_timer(self) -> Dict[str, float]:
        return {
            "start_time": time.perf_counter(),
            "embedding_latency_ms": 0.0,
            "cache_lookup_latency_ms": 0.0,
            "faiss_latency_ms": 0.0,
            "bm25_latency_ms": 0.0,
            "fusion_latency_ms": 0.0,
            "rerank_latency_ms": 0.0,
            "total_retrieval_latency_ms": 0.0
        }

    def record_step(self, timer: Dict[str, float], step_name: str, duration_ms: float):
        timer[f"{step_name}_latency_ms"] = round(duration_ms, 3)

    def finalize_timer(self, timer: Dict[str, float], is_cache_hit: bool = False) -> Dict[str, float]:
        total_ms = (time.perf_counter() - timer["start_time"]) * 1000.0
        timer["total_retrieval_latency_ms"] = round(total_ms, 3)
        timer["is_cache_hit"] = is_cache_hit
        del timer["start_time"]
        self.history.append(timer)
        return timer

    def get_summary(self) -> Dict[str, Any]:
        if not self.history:
            return {"total_queries": 0}

        keys = ["embedding_latency_ms", "cache_lookup_latency_ms", "faiss_latency_ms", 
                "bm25_latency_ms", "fusion_latency_ms", "rerank_latency_ms", "total_retrieval_latency_ms"]

        avg_latencies = {}
        for k in keys:
            vals = [item[k] for item in self.history if k in item]
            avg_latencies[f"avg_{k}"] = round(sum(vals) / len(vals), 3) if vals else 0.0

        hits = sum(1 for item in self.history if item.get("is_cache_hit", False))
        avg_latencies["total_queries"] = len(self.history)
        avg_latencies["cache_hits"] = hits
        avg_latencies["hit_rate"] = round(hits / len(self.history), 4)

        return avg_latencies
