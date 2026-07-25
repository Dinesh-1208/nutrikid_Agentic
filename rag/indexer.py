import os
import json
import pickle
import numpy as np
from typing import Optional

from rag.services import RAGConfig, DatasetVersionService, EmbeddingService
from rag.chunker import ParentChildChunker

def build_index(
    data_path: str,
    output_dir: str,
    model_name: str = "BAAI/bge-small-en-v1.5",
    config: Optional[RAGConfig] = None
):
    if config is None:
        config = RAGConfig(embedding_model=model_name)

    print(f"Loading raw RAG data from: {data_path}")
    with open(data_path, 'r', encoding='utf-8') as f:
        raw_documents = json.load(f)

    print(f"Loaded {len(raw_documents)} raw document entries.")

    # 1. Parent-Child Chunking
    print("Applying Parent-Child chunking with overlap...")
    chunker = ParentChildChunker(
        parent_size=config.parent_chunk_size,
        child_size=config.child_chunk_size,
        child_overlap=config.child_overlap
    )
    parent_chunks, child_chunks, parent_map = chunker.process_documents(raw_documents)
    print(f"Generated {len(parent_chunks)} parent chunks and {len(child_chunks)} child chunks.")

    # 2. Embedding Child Chunks
    print(f"Loading embedding model via EmbeddingService: {config.embedding_model}...")
    import faiss
    embed_service = EmbeddingService(model_name=config.embedding_model)

    child_texts = [c["text"] for c in child_chunks]
    print(f"Generating vector embeddings for {len(child_texts)} child chunks...")
    embeddings = embed_service.encode_texts(child_texts, show_progress=True)

    d = embeddings.shape[1]
    print(f"Creating FAISS IndexFlatIP index with dimension {d}...")
    index = faiss.IndexFlatIP(d)
    index.add(embeddings)

    # 3. Compute Dataset Version Hash
    print("Computing composite dataset SHA-256 hash...")
    data_dir = os.path.dirname(data_path) if "rag" not in os.path.basename(data_path) else os.path.dirname(os.path.dirname(data_path))
    hasher = DatasetVersionService(data_dir=data_dir)
    dataset_hash = hasher.compute_dataset_hash()
    print(f"Dataset Hash: {dataset_hash[:16]}...")

    # 4. Save Artifacts
    os.makedirs(output_dir, exist_ok=True)
    index_path = os.path.join(output_dir, "faiss.index")
    metadata_path = os.path.join(output_dir, "metadata.pkl")
    hash_path = os.path.join(output_dir, "dataset_hash.txt")

    print(f"Saving FAISS index to: {index_path}")
    faiss.write_index(index, index_path)

    metadata_payload = {
        "child_chunks": child_chunks,
        "parent_chunks": parent_chunks,
        "parent_map": parent_map,
        "raw_documents": raw_documents,
        "dataset_hash": dataset_hash,
        "config": {
            "embedding_model": config.embedding_model,
            "parent_chunk_size": config.parent_chunk_size,
            "child_chunk_size": config.child_chunk_size,
            "child_overlap": config.child_overlap
        }
    }

    print(f"Saving enriched metadata to: {metadata_path}")
    with open(metadata_path, 'wb') as f:
        pickle.dump(metadata_payload, f)

    with open(hash_path, 'w', encoding='utf-8') as f:
        f.write(dataset_hash)

    print("Indexing completed successfully!")

if __name__ == '__main__':
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_path = os.path.join(base_dir, "data", "rag", "rag_data.json")
    output_dir = os.path.join(base_dir, "data", "rag")
    build_index(data_path, output_dir)
