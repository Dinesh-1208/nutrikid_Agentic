import numpy as np
import faiss
from typing import List, Optional
from rag.services.base import IEmbeddingService, BaseService

class EmbeddingService(IEmbeddingService, BaseService):
    """
    Encapsulates SentenceTransformer model loading and vector encoding operations.
    """
    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        self.model_name = model_name
        self.model = None

    def _lazy_load(self):
        if self.model is None:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(self.model_name)

    def encode_query(self, query: str) -> np.ndarray:
        self._lazy_load()
        vector = self.model.encode([query], convert_to_numpy=True)
        faiss.normalize_L2(vector)
        return vector

    def encode_texts(self, texts: List[str], show_progress: bool = False) -> np.ndarray:
        self._lazy_load()
        vectors = self.model.encode(texts, show_progress_bar=show_progress, convert_to_numpy=True)
        faiss.normalize_L2(vectors)
        return vectors
