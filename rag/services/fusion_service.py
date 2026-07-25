from typing import List, Dict, Any
from rag.services.base import IFusionService, BaseService

class FusionService(IFusionService, BaseService):
    """
    Performs score normalization and weighted linear score fusion of dense and sparse search candidates.
    Formula: score = alpha * dense_score + (1.0 - alpha) * bm25_score
    """
    def fuse_results(
        self,
        dense_results: List[Dict[str, Any]],
        sparse_results: List[Dict[str, Any]],
        alpha: float = 0.7
    ) -> List[Dict[str, Any]]:
        candidates_map: Dict[str, Dict[str, Any]] = {}

        # Index dense candidates
        for item in dense_results:
            cid = item["id"]
            candidates_map[cid] = item.copy()
            candidates_map[cid]["dense_score"] = item.get("dense_score", item.get("score", 0.0))
            candidates_map[cid]["bm25_score"] = 0.0

        # Index sparse candidates
        for item in sparse_results:
            cid = item["id"]
            if cid in candidates_map:
                candidates_map[cid]["bm25_score"] = item.get("score", 0.0)
            else:
                item_copy = item.copy()
                item_copy["dense_score"] = 0.0
                item_copy["bm25_score"] = item.get("score", 0.0)
                candidates_map[cid] = item_copy

        # Compute weighted fused score
        fused_list = []
        for cid, item in candidates_map.items():
            d_score = item.get("dense_score", 0.0)
            b_score = item.get("bm25_score", 0.0)
            fused_score = alpha * d_score + (1.0 - alpha) * b_score
            item["score"] = float(fused_score)
            fused_list.append(item)

        fused_list.sort(key=lambda x: x["score"], reverse=True)
        return fused_list
