"""
Deterministic Mathematics for Information Retrieval Metrics.
No LLM dependencies.
"""

def calculate_precision_at_k(relevance_labels, k=5):
    """
    Computes Precision@K.
    relevance_labels: List of booleans [True, False, True...] ordered by rank.
    """
    if not relevance_labels:
        return 0.0
    k_labels = relevance_labels[:k]
    return sum(k_labels) / len(k_labels)

def calculate_recall_at_k(relevance_labels, total_relevant, k=5):
    """
    Computes Recall@K.
    total_relevant: Integer representing total number of known relevant documents in the corpus.
    """
    if total_relevant == 0:
        return 0.0
    if not relevance_labels:
        return 0.0
    k_labels = relevance_labels[:k]
    return sum(k_labels) / total_relevant

def calculate_mrr_at_k(relevance_labels, k=5):
    """
    Computes Mean Reciprocal Rank (MRR@K) for a single query.
    """
    if not relevance_labels:
        return 0.0
    
    for i, is_relevant in enumerate(relevance_labels[:k]):
        if is_relevant:
            return 1.0 / (i + 1)
    return 0.0

def calculate_ap_at_k(relevance_labels, k=5):
    """
    Computes Average Precision (AP@K) for a single query.
    This is required to compute MAP@K across multiple queries.
    """
    if not relevance_labels:
        return 0.0
        
    k_labels = relevance_labels[:k]
    num_hits = 0
    score_sum = 0.0
    
    for i, is_relevant in enumerate(k_labels):
        if is_relevant:
            num_hits += 1
            score_sum += num_hits / (i + 1.0)
            
    if num_hits == 0:
        return 0.0
        
    return score_sum / num_hits

def calculate_map_at_k(list_of_relevance_labels, k=5):
    """
    Computes Mean Average Precision (MAP@K) across a dataset of queries.
    """
    if not list_of_relevance_labels:
        return 0.0
    
    ap_scores = [calculate_ap_at_k(labels, k) for labels in list_of_relevance_labels]
    return sum(ap_scores) / len(ap_scores)
