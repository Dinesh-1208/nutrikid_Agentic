import re
from typing import List, Dict, Any, Tuple


class ParentChildChunker:
    """
    Hierarchical Parent-Child Chunker with Overlap.
    Takes source raw document entries and splits long documents into:
    - Parent chunks (larger context window, e.g., 600 chars or ~100-150 words)
    - Child chunks (smaller targeted segments, e.g., 150 chars or ~25-40 words) with overlap.
    Preserves:
    - original document ID & source ID
    - document metadata (type, tags, condition, age_group, goal, etc.)
    - parent-child relational mappings
    """
    def __init__(self, parent_size: int = 600, child_size: int = 150, child_overlap: int = 30):
        self.parent_size = parent_size
        self.child_size = child_size
        self.child_overlap = child_overlap

    def _split_text(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        if not text or len(text) <= chunk_size:
            return [text] if text else []

        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = start + chunk_size
            if end >= text_len:
                chunks.append(text[start:text_len].strip())
                break
            
            # Try to break at space or sentence boundary
            space_idx = text.rfind(' ', start + overlap, end)
            if space_idx != -1 and space_idx > start:
                actual_end = space_idx
            else:
                actual_end = end

            chunk_str = text[start:actual_end].strip()
            if chunk_str:
                chunks.append(chunk_str)

            # Advance start by actual_end - overlap
            next_start = actual_end - overlap
            if next_start <= start:
                next_start = start + max(1, chunk_size - overlap)
            start = next_start

        return chunks

    def process_documents(self, raw_documents: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
        """
        Processes raw documents list.
        Returns:
        - parent_chunks: List of parent chunk dicts
        - child_chunks: List of child chunk dicts (used for FAISS & BM25 search)
        - parent_map: Dict mapping parent_id -> parent_chunk dict
        """
        parent_chunks = []
        child_chunks = []
        parent_map = {}

        for doc_idx, doc in enumerate(raw_documents):
            source_id = doc.get("id", f"DOC_{doc_idx}")
            full_text = doc.get("text", "")
            doc_metadata = doc.get("metadata", {}).copy()

            # Split document into Parent Chunks
            parent_texts = self._split_text(full_text, self.parent_size, self.child_overlap)

            for p_idx, p_text in enumerate(parent_texts):
                parent_id = f"{source_id}_P{p_idx}"
                parent_chunk = {
                    "id": parent_id,
                    "source_id": source_id,
                    "text": p_text,
                    "metadata": doc_metadata,
                    "is_parent": True
                }
                parent_chunks.append(parent_chunk)
                parent_map[parent_id] = parent_chunk

                # Split parent chunk into Child Chunks
                child_texts = self._split_text(p_text, self.child_size, self.child_overlap)
                for c_idx, c_text in enumerate(child_texts):
                    child_id = f"{parent_id}_C{c_idx}"
                    child_chunk = {
                        "id": child_id,
                        "parent_id": parent_id,
                        "source_id": source_id,
                        "text": c_text,
                        "parent_text": p_text,  # Attached for direct parent resolution
                        "metadata": doc_metadata,
                        "is_parent": False
                    }
                    child_chunks.append(child_chunk)

        return parent_chunks, child_chunks, parent_map
