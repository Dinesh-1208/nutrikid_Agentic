import os
import json
import pickle
import numpy as np

def build_index(data_path, output_dir, model_name="BAAI/bge-small-en-v1.5"):
    print(f"Loading RAG data from: {data_path}")
    with open(data_path, 'r', encoding='utf-8') as f:
        rag_data = json.load(f)
        
    print(f"Total chunks loaded: {len(rag_data)}")
    
    # Extract texts
    texts = [item['text'] for item in rag_data]
    
    print(f"Loading embedding model: {model_name}...")
    from sentence_transformers import SentenceTransformer
    import faiss
    
    model = SentenceTransformer(model_name)
    
    print("Generating embeddings (this may take a moment)...")
    embeddings = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)
    
    print("Normalizing embeddings for cosine similarity...")
    faiss.normalize_L2(embeddings)
    
    d = embeddings.shape[1]
    print(f"Creating FAISS index with dimension {d}...")
    index = faiss.IndexFlatIP(d)
    index.add(embeddings)
    
    index_path = os.path.join(output_dir, "faiss.index")
    metadata_path = os.path.join(output_dir, "metadata.pkl")
    
    print(f"Saving FAISS index to: {index_path}")
    faiss.write_index(index, index_path)
    
    print(f"Saving metadata to: {metadata_path}")
    with open(metadata_path, 'wb') as f:
        pickle.dump(rag_data, f)
        
    print("FAISS indexing completed successfully!")

if __name__ == '__main__':
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_path = os.path.join(base_dir, "data", "rag", "rag_data.json")
    output_dir = os.path.join(base_dir, "data", "rag")
    build_index(data_path, output_dir)
