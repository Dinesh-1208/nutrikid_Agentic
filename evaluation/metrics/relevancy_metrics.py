"""
Deterministic Mathematics for Answer Relevancy Metrics.
No LLM dependencies. Computes vector similarities using SentenceTransformers.
"""
import numpy as np

def calculate_cosine_similarity(vec_a, vec_b):
    """
    Computes the cosine similarity between two 1D numpy arrays.
    Formula: (A dot B) / (||A|| * ||B||)
    """
    dot_product = np.dot(vec_a, vec_b)
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
        
    return float(dot_product / (norm_a * norm_b))

def calculate_answer_relevancy(original_query, hypothetical_questions_list, embedding_model):
    """
    Computes Answer Relevancy by measuring the semantic similarity between the original user query 
    and the hypothetical questions reverse-engineered from the generated answer.
    
    Paper Reference: Es et al. (2023) "RAGAS: Automated Evaluation of Retrieval Augmented Generation"
    
    Args:
        original_query (str): The original question asked by the user.
        hypothetical_questions_list (list): A list of dictionaries, e.g., [{"question_id": "Q1", "text": "..."}]
        embedding_model (SentenceTransformer): A pre-loaded embedding model (e.g., from the Retriever) to reuse memory.
        
    Returns:
        dict: A structured dictionary containing individual scores, mean, and standard deviation.
    """
    if not hypothetical_questions_list:
        return {
            "question_scores": [],
            "mean_similarity": 0.0,
            "std_similarity": 0.0
        }
        
    # Encode the original query
    query_vector = embedding_model.encode(original_query, convert_to_numpy=True)
    
    scores = []
    similarities = []
    
    for hq in hypothetical_questions_list:
        q_id = hq.get("question_id", "Unknown")
        q_text = hq.get("text", "")
        
        if not q_text:
            continue
            
        # Encode the hypothetical question
        hq_vector = embedding_model.encode(q_text, convert_to_numpy=True)
        
        # Compute cosine similarity
        sim = calculate_cosine_similarity(query_vector, hq_vector)
        
        # Standardize negative similarities to 0 (very rare in dense text embeddings, but safe bound)
        sim = max(0.0, sim)
        
        scores.append({
            "question_id": q_id,
            "similarity": round(sim, 4)
        })
        similarities.append(sim)
        
    if not similarities:
        return {
            "question_scores": [],
            "mean_similarity": 0.0,
            "std_similarity": 0.0
        }
        
    mean_sim = float(np.mean(similarities))
    std_sim = float(np.std(similarities))
    
    return {
        "question_scores": scores,
        "mean_similarity": round(mean_sim, 4),
        "std_similarity": round(std_sim, 4)
    }
