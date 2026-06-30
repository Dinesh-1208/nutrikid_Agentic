import os
import pickle
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

class KidsNutriRetriever:
    def __init__(self, index_dir=None, model_name="BAAI/bge-small-en-v1.5"):
        if index_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            index_dir = os.path.join(base_dir, "data", "rag")
            
        self.index_path = os.path.join(index_dir, "faiss.index")
        self.metadata_path = os.path.join(index_dir, "metadata.pkl")
        self.model_name = model_name
        
        print(f"Loading retriever model: {self.model_name}...")
        self.model = SentenceTransformer(self.model_name)
        
        if not os.path.exists(self.index_path) or not os.path.exists(self.metadata_path):
            raise FileNotFoundError(f"FAISS index or metadata not found at {index_dir}. Please run the indexing script first.")
            
        print("Loading FAISS index...")
        self.index = faiss.read_index(self.index_path)
        
        print("Loading metadata...")
        with open(self.metadata_path, 'rb') as f:
            self.metadata = pickle.load(f)
            
        print("Retriever initialized successfully!")

    def retrieve(self, query, top_k=5):
        # Encode the query
        query_vector = self.model.encode([query], convert_to_numpy=True)
        # Normalize for cosine similarity
        faiss.normalize_L2(query_vector)
        
        # Search index
        scores, indices = self.index.search(query_vector, top_k)
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.metadata):
                continue
            item = self.metadata[idx]
            results.append({
                "id": item.get("id"),
                "text": item.get("text"),
                "metadata": item.get("metadata", {}),
                "score": float(score)
            })
        return results

    def debug_retrieve(self, query, top_k=5):
        results = self.retrieve(query, top_k)
        print(f"\n--- RAG Retrieval Debug for Query: '{query}' ---")
        for i, res in enumerate(results, 1):
            print(f"\n[{i}] Score: {res['score']:.4f} | ID: {res['id']}")
            print(f"Text: {res['text']}")
            print(f"Metadata: {res['metadata']}")
        return results

if __name__ == '__main__':
    # Test retrieval
    try:
        retriever = KidsNutriRetriever()
        retriever.debug_retrieve("Can my child eat egg during fever?", top_k=3)
    except Exception as e:
        print(f"Retriever test error (likely index not built yet): {e}")
