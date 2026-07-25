import os
import json
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any
from rag.services.base import BaseService

@dataclass
class RAGConfig:
    # Embedding Model
    embedding_model: str = "BAAI/bge-small-en-v1.5"

    # Parent-Child Chunking
    parent_chunk_size: int = 600
    child_chunk_size: int = 150
    child_overlap: int = 30

    # Semantic Cache
    cache_size: int = 1000
    cache_similarity_threshold: float = 0.95
    enable_cache: bool = True

    # Retrieval Strategy
    retrieval_mode: str = "hybrid"  # "hybrid", "semantic", "keyword"
    alpha: float = 0.7              # 0.7 semantic, 0.3 keyword
    top_k: int = 5
    rerank_top_n: int = 20

    # Cross-Encoder Re-ranking
    enable_reranking: bool = True
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # Metadata Filtering
    enable_metadata_filtering: bool = True

    # Directories
    index_dir: Optional[str] = None
    data_dir: Optional[str] = None

    def __post_init__(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        if self.index_dir is None:
            self.index_dir = os.path.join(base_dir, "data", "rag")
        if self.data_dir is None:
            self.data_dir = os.path.join(base_dir, "data")

class ConfigurationService(BaseService):
    """
    Service responsible for loading, managing, and validating RAGConfig.
    """
    def __init__(self, config: Optional[RAGConfig] = None):
        self.config = config or RAGConfig()

    def get_config(self) -> RAGConfig:
        return self.config

    @classmethod
    def load_from_json(cls, json_path: str) -> "ConfigurationService":
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return cls(config=RAGConfig(**data))
        return cls()

    def save_to_json(self, json_path: str):
        os.makedirs(os.path.dirname(json_path), exist_ok=True)
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(self.config), f, indent=2)
