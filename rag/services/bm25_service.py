import re
from typing import List, Dict, Any, Optional
from rank_bm25 import BM25Okapi
from rag.services.base import IBM25Service, BaseService

class BM25Service(IBM25Service, BaseService):
    """
    Service handling BM25 keyword indexing and sparse retrieval.
    """
    def __init__(self, corpus_chunks: Optional[List[Dict[str, Any]]] = None):
        self.corpus_chunks: List[Dict[str, Any]] = corpus_chunks or []
        self.bm25: Optional[BM25Okapi] = None
        if self.corpus_chunks:
            self.build_index(self.corpus_chunks)

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r'\w+', text.lower())

    def build_index(self, corpus_chunks: List[Dict[str, Any]]):
        self.corpus_chunks = corpus_chunks
        tokenized_corpus = [self._tokenize(chunk.get("text", "")) for chunk in self.corpus_chunks]
        self.bm25 = BM25Okapi(tokenized_corpus)

    def retrieve(
        self,
        query: str,
        top_k: int = 20,
        metadata_filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        if not self.bm25 or not self.corpus_chunks:
            return []

        tokenized_query = self._tokenize(query)
        if not tokenized_query:
            return []

        raw_scores = self.bm25.get_scores(tokenized_query)

        valid_indices = list(range(len(self.corpus_chunks)))
        filtered_scores = [(idx, raw_scores[idx]) for idx in valid_indices]
        filtered_scores.sort(key=lambda x: x[1], reverse=True)

        top_indices = filtered_scores[:top_k]
        if not top_indices:
            return []

        max_score = top_indices[0][1]
        min_score = top_indices[-1][1]
        score_range = max_score - min_score

        results = []
        for idx, raw_score in top_indices:
            if score_range > 1e-6:
                norm_score = (raw_score - min_score) / score_range
            else:
                norm_score = 1.0 if raw_score > 0 else 0.0

            chunk = self.corpus_chunks[idx].copy()
            chunk["bm25_score"] = float(raw_score)
            chunk["score"] = float(norm_score)
            results.append(chunk)

        return results
