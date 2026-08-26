"""
Deterministic Mathematics for Information Retrieval Metrics.
No LLM dependencies.
"""

PRECISION_STATUS_VALID = "VALID"
PRECISION_STATUS_REAL_ZERO = "REAL_ZERO"
PRECISION_STATUS_INCOMPLETE_RETRIEVAL = "INCOMPLETE_RETRIEVAL"
PRECISION_STATUS_EVALUATION_FAILURE = "EVALUATION_FAILURE"

RECALL_STATUS_VALID = "VALID"
RECALL_STATUS_REAL_ZERO = "REAL_ZERO"
RECALL_STATUS_MISSING_GROUND_TRUTH = "MISSING_GROUND_TRUTH"
RECALL_STATUS_EMPTY_RETRIEVAL = "EMPTY_RETRIEVAL"
RECALL_STATUS_INVALID_GROUND_TRUTH = "INVALID_GROUND_TRUTH"
RECALL_STATUS_INCOMPLETE_RETRIEVAL = "INCOMPLETE_RETRIEVAL"
RECALL_STATUS_EVALUATION_FAILURE = "EVALUATION_FAILURE"

MAP_STATUS_VALID = "VALID"
MAP_STATUS_REAL_ZERO = "REAL_ZERO"
MAP_STATUS_MISSING_GROUND_TRUTH = "MISSING_GROUND_TRUTH"
MAP_STATUS_EMPTY_RETRIEVAL = "EMPTY_RETRIEVAL"
MAP_STATUS_INVALID_GROUND_TRUTH = "INVALID_GROUND_TRUTH"
MAP_STATUS_INCOMPLETE_RETRIEVAL = "INCOMPLETE_RETRIEVAL"
MAP_STATUS_EVALUATION_FAILURE = "EVALUATION_FAILURE"

MRR_STATUS_VALID = "VALID"
MRR_STATUS_REAL_ZERO = "REAL_ZERO"
MRR_STATUS_MISSING_GROUND_TRUTH = "MISSING_GROUND_TRUTH"
MRR_STATUS_EMPTY_RETRIEVAL = "EMPTY_RETRIEVAL"
MRR_STATUS_INVALID_GROUND_TRUTH = "INVALID_GROUND_TRUTH"
MRR_STATUS_INCOMPLETE_RETRIEVAL = "INCOMPLETE_RETRIEVAL"
MRR_STATUS_EVALUATION_FAILURE = "EVALUATION_FAILURE"

def calculate_precision_at_k(relevance_labels, k=5):
    """
    Computes Precision@K.
    relevance_labels: List of booleans [True, False, True...] ordered by rank.
    """
    return calculate_precision_at_k_details(relevance_labels, k=k)["score"]

def calculate_precision_at_k_details(relevance_labels, k=5, evaluation_failed=False):
    """
    Computes Precision@K with an explicit validity status.

    Precision@K is only valid when K ranked relevance labels are available.
    Missing positions are not silently dropped from the denominator.
    """
    if k <= 0:
        raise ValueError("k must be a positive integer")

    labels = [] if relevance_labels is None else list(relevance_labels)

    if evaluation_failed:
        return {
            "score": None,
            "status": PRECISION_STATUS_EVALUATION_FAILURE,
            "k": k,
            "label_count": len(labels),
            "relevant_count": None
        }

    if len(labels) < k:
        return {
            "score": None,
            "status": PRECISION_STATUS_INCOMPLETE_RETRIEVAL,
            "k": k,
            "label_count": len(labels),
            "relevant_count": sum(1 for label in labels if label is True)
        }

    k_labels = labels[:k]
    relevant_count = sum(1 for label in k_labels if label is True)
    score = relevant_count / k

    return {
        "score": score,
        "status": PRECISION_STATUS_REAL_ZERO if relevant_count == 0 else PRECISION_STATUS_VALID,
        "k": k,
        "label_count": len(k_labels),
        "relevant_count": relevant_count
    }

def calculate_recall_at_k(retrieved_chunk_ids, gold_relevant_chunk_ids, k=5):
    """
    Computes Recall@K from retrieved chunk IDs and gold relevant chunk IDs.
    """
    return calculate_recall_at_k_details(
        retrieved_chunk_ids,
        gold_relevant_chunk_ids,
        k=k
    )["score"]

def calculate_recall_at_k_details(retrieved_chunk_ids, gold_relevant_chunk_ids, k=5):
    """
    Computes Recall@K with explicit validity status.

    Recall@K = |top_k_retrieved_ids intersect gold_relevant_ids| / |gold_relevant_ids|.
    Duplicate retrieved IDs do not inflate the numerator.
    """
    if k <= 0:
        raise ValueError("k must be a positive integer")

    if gold_relevant_chunk_ids is None:
        return {
            "score": None,
            "status": RECALL_STATUS_MISSING_GROUND_TRUTH,
            "k": k,
            "retrieved_count": 0 if retrieved_chunk_ids is None else len(list(retrieved_chunk_ids)),
            "retrieved_relevant_count": None,
            "total_relevant_count": None
        }

    if not isinstance(gold_relevant_chunk_ids, (list, tuple, set)):
        return {
            "score": None,
            "status": RECALL_STATUS_INVALID_GROUND_TRUTH,
            "k": k,
            "retrieved_count": 0 if retrieved_chunk_ids is None else len(list(retrieved_chunk_ids)),
            "retrieved_relevant_count": None,
            "total_relevant_count": None
        }

    gold_ids = {str(chunk_id) for chunk_id in gold_relevant_chunk_ids if chunk_id}
    if not gold_ids:
        return {
            "score": None,
            "status": RECALL_STATUS_INVALID_GROUND_TRUTH,
            "k": k,
            "retrieved_count": 0 if retrieved_chunk_ids is None else len(list(retrieved_chunk_ids)),
            "retrieved_relevant_count": None,
            "total_relevant_count": 0
        }

    retrieved_ids = [] if retrieved_chunk_ids is None else [str(chunk_id) for chunk_id in retrieved_chunk_ids if chunk_id]
    top_k_ids = retrieved_ids[:k]
    retrieved_relevant = len(set(top_k_ids).intersection(gold_ids))
    total_relevant = len(gold_ids)
    score = retrieved_relevant / total_relevant

    if not top_k_ids:
        status = RECALL_STATUS_EMPTY_RETRIEVAL
    elif len(top_k_ids) < k:
        status = RECALL_STATUS_INCOMPLETE_RETRIEVAL
    elif retrieved_relevant == 0:
        status = RECALL_STATUS_REAL_ZERO
    else:
        status = RECALL_STATUS_VALID

    return {
        "score": score,
        "status": status,
        "k": k,
        "retrieved_count": len(top_k_ids),
        "retrieved_relevant_count": retrieved_relevant,
        "total_relevant_count": total_relevant
    }

def calculate_mrr_at_k(retrieved_chunk_ids, gold_relevant_chunk_ids, k=5):
    """
    Computes RR@K for a single query from retrieved IDs and gold relevant IDs.
    """
    return calculate_mrr_at_k_details(
        retrieved_chunk_ids,
        gold_relevant_chunk_ids,
        k=k
    )["score"]

def calculate_mrr_at_k_details(retrieved_chunk_ids, gold_relevant_chunk_ids, k=5):
    """
    Computes RR@K with explicit validity status.

    RR@K = 1 / rank of the first retrieved ID that appears in the gold set.
    Duplicate retrieved IDs cannot create additional or earlier hits.
    """
    if k <= 0:
        raise ValueError("k must be a positive integer")

    retrieved_ids = [] if retrieved_chunk_ids is None else list(retrieved_chunk_ids)

    if gold_relevant_chunk_ids is None:
        return {
            "score": None,
            "status": MRR_STATUS_MISSING_GROUND_TRUTH,
            "k": k,
            "retrieved_count": len(retrieved_ids),
            "first_relevant_rank": None,
            "gold_relevant_count": None
        }

    if not isinstance(gold_relevant_chunk_ids, (list, tuple, set)):
        return {
            "score": None,
            "status": MRR_STATUS_INVALID_GROUND_TRUTH,
            "k": k,
            "retrieved_count": len(retrieved_ids),
            "first_relevant_rank": None,
            "gold_relevant_count": None
        }

    if not gold_relevant_chunk_ids:
        return {
            "score": None,
            "status": MRR_STATUS_MISSING_GROUND_TRUTH,
            "k": k,
            "retrieved_count": len(retrieved_ids),
            "first_relevant_rank": None,
            "gold_relevant_count": None
        }

    if any(not isinstance(chunk_id, str) or not chunk_id.strip() for chunk_id in gold_relevant_chunk_ids):
        return {
            "score": None,
            "status": MRR_STATUS_INVALID_GROUND_TRUTH,
            "k": k,
            "retrieved_count": len(retrieved_ids),
            "first_relevant_rank": None,
            "gold_relevant_count": None
        }

    gold_ids = {chunk_id.strip() for chunk_id in gold_relevant_chunk_ids}
    top_k_ids = [str(chunk_id) for chunk_id in retrieved_ids[:k] if chunk_id]

    if not top_k_ids:
        return {
            "score": None,
            "status": MRR_STATUS_EMPTY_RETRIEVAL,
            "k": k,
            "retrieved_count": 0,
            "first_relevant_rank": None,
            "gold_relevant_count": len(gold_ids)
        }

    seen_ids = set()
    first_relevant_rank = None
    for rank, chunk_id in enumerate(top_k_ids, start=1):
        if chunk_id in seen_ids:
            continue
        seen_ids.add(chunk_id)
        if chunk_id in gold_ids:
            first_relevant_rank = rank
            break

    if len(top_k_ids) < k:
        return {
            "score": None,
            "status": MRR_STATUS_INCOMPLETE_RETRIEVAL,
            "k": k,
            "retrieved_count": len(top_k_ids),
            "first_relevant_rank": first_relevant_rank,
            "gold_relevant_count": len(gold_ids)
        }

    if first_relevant_rank is None:
        return {
            "score": 0.0,
            "status": MRR_STATUS_REAL_ZERO,
            "k": k,
            "retrieved_count": len(top_k_ids),
            "first_relevant_rank": None,
            "gold_relevant_count": len(gold_ids)
        }

    return {
        "score": 1.0 / first_relevant_rank,
        "status": MRR_STATUS_VALID,
        "k": k,
        "retrieved_count": len(top_k_ids),
        "first_relevant_rank": first_relevant_rank,
        "gold_relevant_count": len(gold_ids)
    }

def calculate_ap_at_k(relevance_labels, k=5, total_relevant_count=None):
    """
    Computes Average Precision (AP@K) for a single query.
    This is required to compute MAP@K across multiple queries.

    Per Manning, Raghavan & Schutze, "Introduction to Information Retrieval"
    (2008), Chapter 8, Section 8.4, Eq. 8.8: AP is the sum of the precision
    value at each rank where a relevant item is retrieved, divided by the
    TRUE total number of relevant items for the query (total_relevant_count) -
    not by the number of relevant items actually found. A relevant item that
    is never retrieved contributes 0 to the sum, but total_relevant_count is
    not reduced to compensate.

    total_relevant_count must be supplied by the caller to get the
    textbook-exact score. If omitted, this falls back to normalizing by the
    number of relevant hits found within the top K (legacy behavior),
    preserved only for callers with no gold total-relevant count available
    (e.g. LLM-judged relevance experiments with no ground truth).
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

    denominator = num_hits if total_relevant_count is None else total_relevant_count

    if not denominator:
        return 0.0

    return score_sum / denominator

def calculate_ap_at_k_details(retrieved_chunk_ids, gold_relevant_chunk_ids, k=5):
    """
    Computes AP@K from retrieved chunk IDs and gold relevant chunk IDs.

    The relevance vector is derived deterministically from membership in the
    gold set. Duplicate retrieved IDs do not create extra relevant hits.
    """
    if k <= 0:
        raise ValueError("k must be a positive integer")

    retrieved_ids = [] if retrieved_chunk_ids is None else list(retrieved_chunk_ids)

    if gold_relevant_chunk_ids is None:
        return {
            "score": None,
            "status": MAP_STATUS_MISSING_GROUND_TRUTH,
            "k": k,
            "retrieved_count": len(retrieved_ids),
            "relevance_labels": [],
            "retrieved_relevant_count": None,
            "total_relevant_count": None
        }

    if not isinstance(gold_relevant_chunk_ids, (list, tuple, set)):
        return {
            "score": None,
            "status": MAP_STATUS_INVALID_GROUND_TRUTH,
            "k": k,
            "retrieved_count": len(retrieved_ids),
            "relevance_labels": [],
            "retrieved_relevant_count": None,
            "total_relevant_count": None
        }

    if not gold_relevant_chunk_ids:
        return {
            "score": None,
            "status": MAP_STATUS_MISSING_GROUND_TRUTH,
            "k": k,
            "retrieved_count": len(retrieved_ids),
            "relevance_labels": [],
            "retrieved_relevant_count": None,
            "total_relevant_count": None
        }

    if any(not isinstance(chunk_id, str) or not chunk_id.strip() for chunk_id in gold_relevant_chunk_ids):
        return {
            "score": None,
            "status": MAP_STATUS_INVALID_GROUND_TRUTH,
            "k": k,
            "retrieved_count": len(retrieved_ids),
            "relevance_labels": [],
            "retrieved_relevant_count": None,
            "total_relevant_count": None
        }

    gold_ids = {chunk_id.strip() for chunk_id in gold_relevant_chunk_ids}
    top_k_ids = [str(chunk_id) for chunk_id in retrieved_ids[:k] if chunk_id]

    if not top_k_ids:
        return {
            "score": None,
            "status": MAP_STATUS_EMPTY_RETRIEVAL,
            "k": k,
            "retrieved_count": 0,
            "relevance_labels": [],
            "retrieved_relevant_count": None,
            "total_relevant_count": len(gold_ids)
        }

    relevance_labels = []
    seen_relevant_ids = set()
    for chunk_id in top_k_ids:
        if chunk_id in gold_ids and chunk_id not in seen_relevant_ids:
            relevance_labels.append(True)
            seen_relevant_ids.add(chunk_id)
        else:
            relevance_labels.append(False)

    retrieved_relevant_count = sum(1 for label in relevance_labels if label)
    score = calculate_ap_at_k(relevance_labels, k=k, total_relevant_count=len(gold_ids))

    if len(top_k_ids) < k:
        status = MAP_STATUS_INCOMPLETE_RETRIEVAL
    elif retrieved_relevant_count == 0:
        status = MAP_STATUS_REAL_ZERO
    else:
        status = MAP_STATUS_VALID

    return {
        "score": score,
        "status": status,
        "k": k,
        "retrieved_count": len(top_k_ids),
        "relevance_labels": relevance_labels,
        "retrieved_relevant_count": retrieved_relevant_count,
        "total_relevant_count": len(gold_ids)
    }

def calculate_map_at_k(list_of_relevance_labels, k=5):
    """
    Computes Mean Average Precision (MAP@K) across a dataset of queries.
    """
    if not list_of_relevance_labels:
        return 0.0
    
    ap_scores = [calculate_ap_at_k(labels, k) for labels in list_of_relevance_labels]
    return sum(ap_scores) / len(ap_scores)

def calculate_map_at_k_details(ap_results):
    """
    Computes MAP@K from per-query AP result dictionaries.

    Missing or invalid ground-truth cases are excluded; real-zero AP cases are
    included because they are valid retrieval outcomes.
    """
    results = [] if ap_results is None else list(ap_results)
    contributing_statuses = {MAP_STATUS_VALID, MAP_STATUS_REAL_ZERO}
    valid_scores = [
        result.get("score")
        for result in results
        if result.get("status") in contributing_statuses and result.get("score") is not None
    ]

    score = sum(valid_scores) / len(valid_scores) if valid_scores else None

    return {
        "score": score,
        "valid_cases": len(valid_scores),
        "missing_ground_truth": sum(1 for result in results if result.get("status") == MAP_STATUS_MISSING_GROUND_TRUTH),
        "real_zero_cases": sum(1 for result in results if result.get("status") == MAP_STATUS_REAL_ZERO),
        "evaluation_failures": sum(1 for result in results if result.get("status") == MAP_STATUS_EVALUATION_FAILURE),
        "invalid_ground_truth": sum(1 for result in results if result.get("status") == MAP_STATUS_INVALID_GROUND_TRUTH),
        "empty_retrieval": sum(1 for result in results if result.get("status") == MAP_STATUS_EMPTY_RETRIEVAL),
        "incomplete_retrieval": sum(1 for result in results if result.get("status") == MAP_STATUS_INCOMPLETE_RETRIEVAL)
    }

def calculate_mean_mrr_at_k_details(mrr_results):
    """
    Computes MRR@K from per-query RR result dictionaries.

    Missing or invalid ground-truth cases are excluded; real-zero RR cases are
    included because they are valid retrieval outcomes.
    """
    results = [] if mrr_results is None else list(mrr_results)
    contributing_statuses = {MRR_STATUS_VALID, MRR_STATUS_REAL_ZERO}
    valid_scores = [
        result.get("score")
        for result in results
        if result.get("status") in contributing_statuses and result.get("score") is not None
    ]

    score = sum(valid_scores) / len(valid_scores) if valid_scores else None

    return {
        "score": score,
        "valid_cases": len(valid_scores),
        "missing_ground_truth": sum(1 for result in results if result.get("status") == MRR_STATUS_MISSING_GROUND_TRUTH),
        "real_zero_cases": sum(1 for result in results if result.get("status") == MRR_STATUS_REAL_ZERO),
        "evaluation_failures": sum(1 for result in results if result.get("status") == MRR_STATUS_EVALUATION_FAILURE),
        "invalid_ground_truth": sum(1 for result in results if result.get("status") == MRR_STATUS_INVALID_GROUND_TRUTH),
        "empty_retrieval": sum(1 for result in results if result.get("status") == MRR_STATUS_EMPTY_RETRIEVAL),
        "incomplete_retrieval": sum(1 for result in results if result.get("status") == MRR_STATUS_INCOMPLETE_RETRIEVAL)
    }
