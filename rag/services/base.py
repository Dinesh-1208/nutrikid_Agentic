from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
import numpy as np

class BaseService(ABC):
    """Abstract Base Class for all RAG Services."""
    pass

class IEmbeddingService(ABC):
    @abstractmethod
    def encode_query(self, query: str) -> np.ndarray:
        pass

    @abstractmethod
    def encode_texts(self, texts: List[str]) -> np.ndarray:
        pass

class ICacheService(ABC):
    @abstractmethod
    def get(self, query: str, query_embedding: np.ndarray, current_dataset_hash: str) -> Optional[Tuple[List[Dict[str, Any]], float]]:
        pass

    @abstractmethod
    def put(self, query: str, query_embedding: np.ndarray, retrieved_context: List[Dict[str, Any]], current_dataset_hash: str):
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        pass

class IBM25Service(ABC):
    @abstractmethod
    def retrieve(self, query: str, top_k: int = 20, metadata_filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        pass

class IFusionService(ABC):
    @abstractmethod
    def fuse_results(self, dense_results: List[Dict[str, Any]], sparse_results: List[Dict[str, Any]], alpha: float = 0.7) -> List[Dict[str, Any]]:
        pass

class IRerankerService(ABC):
    @abstractmethod
    def rerank(self, query: str, candidates: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
        pass

class IMetadataFilterService(ABC):
    @abstractmethod
    def filter_chunks(self, chunks: List[Dict[str, Any]], metadata_filters: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        pass

class IPromptContextService(ABC):
    @abstractmethod
    def expand_and_format_context(self, retrieved_chunks: List[Dict[str, Any]], parent_map: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        pass
