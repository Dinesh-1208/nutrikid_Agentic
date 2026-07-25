import os
import time
import pickle
import faiss
import numpy as np
from typing import List, Dict, Any, Optional

from rag.services.base import BaseService
from rag.services.config_service import ConfigurationService, RAGConfig
from rag.services.dataset_version_service import DatasetVersionService
from rag.services.logger_service import LoggerService
from rag.services.metrics_service import MetricsService
from rag.services.embedding_service import EmbeddingService
from rag.services.cache_service import CacheService
from rag.services.bm25_service import BM25Service
from rag.services.metadata_filter_service import MetadataFilterService
from rag.services.fusion_service import FusionService
from rag.services.reranker_service import RerankerService
from rag.services.prompt_context_service import PromptContextService

class RetrievalService(BaseService):
    """
    Master Retrieval Service.
    Coordinates decoupled services via dependency injection to perform:
    1. Dataset Version Verification
    2. Semantic LRU Cache Lookup
    3. Metadata Scope Pre-filtering
    4. FAISS Vector Search + BM25 Keyword Search
    5. Weighted Score Fusion
    6. Cross-Encoder Re-ranking
    7. Parent Context Expansion
    8. Cache Storage, Latency Timing, and Structured Logging
    """
    def __init__(
        self,
        config_service: Optional[ConfigurationService] = None,
        dataset_version_service: Optional[DatasetVersionService] = None,
        logger_service: Optional[LoggerService] = None,
        metrics_service: Optional[MetricsService] = None,
        embedding_service: Optional[EmbeddingService] = None,
        cache_service: Optional[CacheService] = None,
        bm25_service: Optional[BM25Service] = None,
        metadata_filter_service: Optional[MetadataFilterService] = None,
        fusion_service: Optional[FusionService] = None,
        reranker_service: Optional[RerankerService] = None,
        prompt_context_service: Optional[PromptContextService] = None
    ):
        self.config_service = config_service or ConfigurationService()
        self.config = self.config_service.get_config()

        self.version_service = dataset_version_service or DatasetVersionService(data_dir=self.config.data_dir)
        self.current_dataset_hash = self.version_service.compute_dataset_hash()

        self.logger = logger_service or LoggerService()
        self.metrics = metrics_service or MetricsService()
        self.embedding_service = embedding_service or EmbeddingService(model_name=self.config.embedding_model)
        self.cache_service = cache_service or CacheService(
            max_size=self.config.cache_size,
            similarity_threshold=self.config.cache_similarity_threshold
        )

        # Load FAISS index & metadata store
        index_path = os.path.join(self.config.index_dir, "faiss.index")
        metadata_path = os.path.join(self.config.index_dir, "metadata.pkl")

        if not os.path.exists(index_path) or not os.path.exists(metadata_path):
            self.logger.warning(f"FAISS index or metadata missing at {self.config.index_dir}. Auto-building index...")
            from rag.indexer import build_index
            data_path = os.path.join(self.config.data_dir, "rag", "rag_data.json")
            build_index(data_path, self.config.index_dir, model_name=self.config.embedding_model)

        self.faiss_index = faiss.read_index(index_path)
        with open(metadata_path, 'rb') as f:
            raw_meta = pickle.load(f)

        if isinstance(raw_meta, dict):
            self.child_chunks = raw_meta.get("child_chunks", [])
            self.parent_chunks = raw_meta.get("parent_chunks", [])
            self.parent_map = raw_meta.get("parent_map", {})
            self.index_dataset_hash = raw_meta.get("dataset_hash", "")
        else:
            self.child_chunks = raw_meta
            self.parent_chunks = []
            self.parent_map = {}
            self.index_dataset_hash = ""

        # Initialize remaining retrieval services
        self.bm25_service = bm25_service or BM25Service(corpus_chunks=self.child_chunks)
        self.metadata_filter_service = metadata_filter_service or MetadataFilterService()
        self.fusion_service = fusion_service or FusionService()
        self.reranker_service = reranker_service or RerankerService(
            model_name=self.config.reranker_model,
            enabled=self.config.enable_reranking
        )
        self.prompt_context_service = prompt_context_service or PromptContextService()

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        metadata_filters: Optional[Dict[str, Any]] = None,
        mode: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        k = top_k if top_k is not None else self.config.top_k
        retrieval_mode = mode if mode is not None else self.config.retrieval_mode

        timer = self.metrics.create_timer()

        # 1. Embedding & Semantic Cache Lookup
        t0 = time.perf_counter()
        query_vector = self.embedding_service.encode_query(query)
        self.metrics.record_step(timer, "embedding", (time.perf_counter() - t0) * 1000.0)

        if self.config.enable_cache:
            t_cache = time.perf_counter()
            cached_result = self.cache_service.get(query, query_vector[0], self.current_dataset_hash)
            self.metrics.record_step(timer, "cache_lookup", (time.perf_counter() - t_cache) * 1000.0)

            if cached_result is not None:
                cached_chunks, _ = cached_result
                latencies = self.metrics.finalize_timer(timer, is_cache_hit=True)
                chunk_ids = [c["id"] for c in cached_chunks]
                scores = [c["score"] for c in cached_chunks]
                self.logger.log_retrieval_event(
                    query=query, cache_hit=True, retrieved_chunk_ids=chunk_ids,
                    retrieval_scores=scores, rerank_scores=None,
                    metadata_filters=metadata_filters, latencies=latencies,
                    dataset_hash=self.current_dataset_hash
                )
                return cached_chunks[:k]

        # 2. Dense FAISS Vector Search
        fetch_n = max(self.config.rerank_top_n, k * 3)
        dense_results: List[Dict[str, Any]] = []

        if retrieval_mode in ["hybrid", "semantic"]:
            t_faiss = time.perf_counter()
            scores, indices = self.faiss_index.search(query_vector, fetch_n)
            self.metrics.record_step(timer, "faiss", (time.perf_counter() - t_faiss) * 1000.0)

            for score, idx in zip(scores[0], indices[0]):
                if idx < 0 or idx >= len(self.child_chunks):
                    continue
                item = self.child_chunks[idx].copy()
                item["dense_score"] = float(score)
                dense_results.append(item)

        # 3. Sparse BM25 Search
        sparse_results: List[Dict[str, Any]] = []
        if retrieval_mode in ["hybrid", "keyword"]:
            t_bm25 = time.perf_counter()
            sparse_results = self.bm25_service.retrieve(
                query=query,
                top_k=fetch_n,
                metadata_filters=metadata_filters if self.config.enable_metadata_filtering else None
            )
            self.metrics.record_step(timer, "bm25", (time.perf_counter() - t_bm25) * 1000.0)

        # 4. Fusion Phase
        t_fusion = time.perf_counter()
        if retrieval_mode == "semantic":
            for item in dense_results:
                item["score"] = item.get("dense_score", 0.0)
            fused_candidates = dense_results[:fetch_n]
        elif retrieval_mode == "keyword":
            fused_candidates = sparse_results[:fetch_n]
        else:
            fused_candidates = self.fusion_service.fuse_results(
                dense_results=dense_results,
                sparse_results=sparse_results,
                alpha=self.config.alpha
            )[:fetch_n]
        self.metrics.record_step(timer, "fusion", (time.perf_counter() - t_fusion) * 1000.0)

        # 5. Metadata Pre-Filtering
        if self.config.enable_metadata_filtering and metadata_filters:
            fused_candidates = self.metadata_filter_service.filter_chunks(fused_candidates, metadata_filters)

        # 6. Cross-Encoder Re-ranking
        t_rerank = time.perf_counter()
        if self.config.enable_reranking:
            ranked_results = self.reranker_service.rerank(query, fused_candidates, top_k=k)
        else:
            ranked_results = fused_candidates[:k]
        self.metrics.record_step(timer, "rerank", (time.perf_counter() - t_rerank) * 1000.0)

        # 7. Parent Context Expansion
        final_results = self.prompt_context_service.expand_and_format_context(ranked_results, self.parent_map)

        # 8. Cache Store & Finalize
        if self.config.enable_cache and final_results:
            self.cache_service.put(query, query_vector[0], final_results, self.current_dataset_hash)

        latencies = self.metrics.finalize_timer(timer, is_cache_hit=False)
        chunk_ids = [c["id"] for c in final_results]
        scores = [c["score"] for c in final_results]
        rerank_scores = [c.get("rerank_score", c["score"]) for c in ranked_results]

        self.logger.log_retrieval_event(
            query=query, cache_hit=False, retrieved_chunk_ids=chunk_ids,
            retrieval_scores=scores, rerank_scores=rerank_scores,
            metadata_filters=metadata_filters, latencies=latencies,
            dataset_hash=self.current_dataset_hash
        )

        return final_results
