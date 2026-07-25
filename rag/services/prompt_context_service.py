from typing import List, Dict, Any
from rag.services.base import IPromptContextService, BaseService

class PromptContextService(IPromptContextService, BaseService):
    """
    Expands fine-grained child chunks into complete parent contexts and formats context payloads for Prompt Builders.
    """
    def expand_and_format_context(
        self,
        retrieved_chunks: List[Dict[str, Any]],
        parent_map: Dict[str, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        formatted_results = []
        for item in retrieved_chunks:
            parent_id = item.get("parent_id")
            parent_text = item.get("parent_text")

            if not parent_text and parent_id and parent_id in parent_map:
                parent_text = parent_map[parent_id].get("text")

            text_content = parent_text if parent_text else item.get("text", "")

            formatted_item = {
                "id": item.get("id"),
                "parent_id": parent_id,
                "text": text_content,
                "child_text": item.get("text", ""),
                "metadata": item.get("metadata", {}),
                "score": float(item.get("score", 0.0))
            }
            if "rerank_score" in item:
                formatted_item["rerank_score"] = float(item["rerank_score"])
            formatted_results.append(formatted_item)

        return formatted_results
