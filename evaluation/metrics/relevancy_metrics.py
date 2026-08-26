"""
Deterministic Mathematics for Answer Relevancy Metrics.
No LLM dependencies. Computes vector similarities using SentenceTransformers.
"""
import numpy as np

ANSWER_RELEVANCY_STATUS_VALID = "VALID"
ANSWER_RELEVANCY_STATUS_REAL_ZERO = "REAL_ZERO"
ANSWER_RELEVANCY_STATUS_NO_QUESTIONS_GENERATED = "NO_QUESTIONS_GENERATED"
ANSWER_RELEVANCY_STATUS_EVALUATION_FAILURE = "EVALUATION_FAILURE"

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

def calculate_answer_relevancy(original_query, hypothetical_questions_list, embedding_model, evaluation_failed=False):
    """
    Computes Answer Relevancy by measuring the semantic similarity between the original user query
    and the hypothetical questions reverse-engineered from the generated answer.

    Formula: AR = (1/n) * sum(sim(q, qi))
    Source: Es et al. (2023) "RAGAS: Automated Evaluation of Retrieval
    Augmented Generation" (arXiv:2309.15217), Section 3, page 3, Eq. 1.

    Embedding model (BAAI/bge-small-en-v1.5, reused from the retriever) and
    the negative-similarity clamp are deliberate KidsNutriBite adaptations of
    the paper's text-embedding-ada-002 + unclamped cosine similarity - both
    preserved unchanged here.

    An empty/invalid hypothetical_questions_list is never silently scored as
    0.0. It is either NO_QUESTIONS_GENERATED (the relevancy judge ran
    successfully but no valid question text was produced) or
    EVALUATION_FAILURE (the relevancy judge/API/parser failed before any
    questions could be generated) - both report mean_similarity=None, so a
    real zero (valid questions existed, all with genuinely 0.0 similarity)
    stays distinguishable from a failed measurement.

    Args:
        original_query (str): The original question asked by the user.
        hypothetical_questions_list (list): A list of dictionaries, e.g., [{"question_id": "Q1", "text": "..."}]
        embedding_model (SentenceTransformer): A pre-loaded embedding model (e.g., from the Retriever) to reuse memory.
        evaluation_failed (bool): True when the relevancy judge/API/parser
            failed to produce a usable result (e.g. RelevancyJudge returned
            {"parse_failed": True, ...}, or the Layer 1 judge call raised).

    Returns:
        dict: {"question_scores", "mean_similarity", "std_similarity", "status"}
    """
    if evaluation_failed:
        return {
            "question_scores": [],
            "mean_similarity": None,
            "std_similarity": None,
            "status": ANSWER_RELEVANCY_STATUS_EVALUATION_FAILURE
        }

    if not hypothetical_questions_list:
        return {
            "question_scores": [],
            "mean_similarity": None,
            "std_similarity": None,
            "status": ANSWER_RELEVANCY_STATUS_NO_QUESTIONS_GENERATED
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
            "mean_similarity": None,
            "std_similarity": None,
            "status": ANSWER_RELEVANCY_STATUS_NO_QUESTIONS_GENERATED
        }

    mean_sim = float(np.mean(similarities))
    std_sim = float(np.std(similarities))

    return {
        "question_scores": scores,
        "mean_similarity": round(mean_sim, 4),
        "std_similarity": round(std_sim, 4),
        "status": ANSWER_RELEVANCY_STATUS_REAL_ZERO if mean_sim == 0.0 else ANSWER_RELEVANCY_STATUS_VALID
    }
