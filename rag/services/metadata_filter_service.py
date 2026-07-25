from typing import List, Dict, Any, Optional
from rag.services.base import IMetadataFilterService, BaseService

class MetadataFilterService(IMetadataFilterService, BaseService):
    """
    Filters chunks based on age group, medical condition, nutrition goal, category, or allergy tags.
    """
    def filter_chunks(
        self,
        chunks: List[Dict[str, Any]],
        metadata_filters: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        if not metadata_filters or not chunks:
            return chunks

        filtered = []
        for chunk in chunks:
            if self._matches(chunk, metadata_filters):
                filtered.append(chunk)

        # Return original list if pre-filter excludes all items (fallback)
        return filtered if filtered else chunks

    def _matches(self, chunk: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        chunk_meta = chunk.get("metadata", {})
        chunk_tags = [t.lower() for t in chunk_meta.get("tags", [])]
        chunk_type = chunk_meta.get("type", "").lower()
        chunk_text = chunk.get("text", "").lower()

        for key, val in filters.items():
            if not val:
                continue
            if isinstance(val, str):
                target = val.lower()
                if key in ["condition", "medical_condition"]:
                    if target not in chunk_type and target not in chunk_tags and target not in chunk_text:
                        return False
                elif key in ["goal", "nutrition_goal"]:
                    if target not in chunk_type and target not in chunk_tags and target not in chunk_text:
                        return False
                elif key in ["category", "food_category"]:
                    if target not in chunk_type and target not in chunk_tags:
                        return False
            elif isinstance(val, list):
                # E.g. allergy exclusion tags
                pass

        return True
