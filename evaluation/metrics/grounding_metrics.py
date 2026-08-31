"""
Deterministic Mathematics for Grounding, Faithfulness, and Hallucination Metrics.
No LLM dependencies. All semantic reasoning is previously performed by Layer 1 Judges.
"""

FAITHFULNESS_STATUS_VALID = "VALID"
FAITHFULNESS_STATUS_REAL_ZERO = "REAL_ZERO"
FAITHFULNESS_STATUS_NO_CLAIMS_EXTRACTED = "NO_CLAIMS_EXTRACTED"
FAITHFULNESS_STATUS_EVALUATION_FAILURE = "EVALUATION_FAILURE"
FAITHFULNESS_STATUS_INVALID_CLAIM_DATA = "INVALID_CLAIM_DATA"

UNSUPPORTED_CLAIM_RATE_STATUS_VALID = "VALID"
UNSUPPORTED_CLAIM_RATE_STATUS_REAL_ZERO = "REAL_ZERO"
UNSUPPORTED_CLAIM_RATE_STATUS_NO_CLAIMS_EXTRACTED = "NO_CLAIMS_EXTRACTED"
UNSUPPORTED_CLAIM_RATE_STATUS_EVALUATION_FAILURE = "EVALUATION_FAILURE"
UNSUPPORTED_CLAIM_RATE_STATUS_INVALID_CLAIM_DATA = "INVALID_CLAIM_DATA"

RESPONSE_HALLUCINATION_STATUS_VALID = "VALID"
RESPONSE_HALLUCINATION_STATUS_REAL_ZERO = "REAL_ZERO"
RESPONSE_HALLUCINATION_STATUS_NO_CLAIMS_EXTRACTED = "NO_CLAIMS_EXTRACTED"
RESPONSE_HALLUCINATION_STATUS_EVALUATION_FAILURE = "EVALUATION_FAILURE"
RESPONSE_HALLUCINATION_STATUS_INVALID_CLAIM_DATA = "INVALID_CLAIM_DATA"
RESPONSE_HALLUCINATION_STATUS_INVALID_TYPE_DATA = "INVALID_TYPE_DATA"

def _has_invalid_claim_data(claims):
    """
    True if any claim in the list is missing a boolean `is_supported` field.

    Shared by calculate_faithfulness_details and
    calculate_unsupported_claim_rate_details so a malformed claims_list is
    never silently treated as supported by one metric and unsupported by
    the other - both must report INVALID_CLAIM_DATA identically, which is
    what guarantees Faithfulness + Unsupported Claim Rate = 1.0 whenever
    both are VALID/REAL_ZERO on the same claims_list.
    """
    return any(not isinstance(c.get("is_supported"), bool) for c in claims)

def calculate_faithfulness(claims_list):
    """
    Backward-compatible wrapper around calculate_faithfulness_details.
    Returns the score only. May be None - see calculate_faithfulness_details.
    """
    return calculate_faithfulness_details(claims_list)["score"]

def calculate_faithfulness_details(claims_list, evaluation_failed=False):
    """
    Computes Faithfulness Score with an explicit validity status.
    Formula: Supported Claims / Total Extracted Claims

    Source: Es et al. (2023) "RAGAS: Automated Evaluation of Retrieval
    Augmented Generation" (arXiv:2309.15217), Section 3, page 3.
    F = |V| / |S|, where |V| is the number of extracted statements judged
    supported by the context and |S| is the total number of extracted
    statements.

    An empty claims_list is never silently scored as 0.0. It is either
    NO_CLAIMS_EXTRACTED (the grounding judge ran successfully and the answer
    genuinely contained no factual claims to check) or EVALUATION_FAILURE
    (the grounding judge/API/parser failed before any claims could be
    extracted) - both report score=None so a real zero (claims existed and
    none were supported) stays distinguishable from a failed measurement.
    A non-empty claims_list where some claim is missing a boolean
    `is_supported` field reports INVALID_CLAIM_DATA (score=None) instead of
    silently guessing a default - see _has_invalid_claim_data.

    Args:
        claims_list (list): A list of claim dictionaries output by the GroundingJudge.
        evaluation_failed (bool): True when the grounding judge/API/parser
            failed to produce a usable result (e.g. GroundingJudge returned
            {"parse_failed": True, ...}, or the Layer 1 judge call raised).
    Returns:
        dict: {"score", "status", "supported_count", "total_count"}
    """
    claims = [] if claims_list is None else list(claims_list)

    if evaluation_failed:
        return {
            "score": None,
            "status": FAITHFULNESS_STATUS_EVALUATION_FAILURE,
            "supported_count": None,
            "total_count": len(claims)
        }

    if not claims:
        return {
            "score": None,
            "status": FAITHFULNESS_STATUS_NO_CLAIMS_EXTRACTED,
            "supported_count": 0,
            "total_count": 0
        }

    if _has_invalid_claim_data(claims):
        return {
            "score": None,
            "status": FAITHFULNESS_STATUS_INVALID_CLAIM_DATA,
            "supported_count": None,
            "total_count": len(claims)
        }

    supported_count = sum(1 for c in claims if c["is_supported"])
    score = supported_count / len(claims)

    return {
        "score": score,
        "status": FAITHFULNESS_STATUS_REAL_ZERO if supported_count == 0 else FAITHFULNESS_STATUS_VALID,
        "supported_count": supported_count,
        "total_count": len(claims)
    }

def calculate_unsupported_claim_rate(claims_list):
    """
    Backward-compatible-style wrapper around
    calculate_unsupported_claim_rate_details. Returns the score only. May
    be None - see calculate_unsupported_claim_rate_details.
    """
    return calculate_unsupported_claim_rate_details(claims_list)["score"]

def calculate_unsupported_claim_rate_details(claims_list, evaluation_failed=False):
    """
    Computes the Unsupported Claim Rate (previously named "Overall
    Hallucination Rate") with an explicit validity status.
    Formula: Unsupported Claims / Total Extracted Claims

    This is a project-operational metric - it is not a formula defined
    verbatim, under this name, in any single paper. Its ratio structure is
    informed by the supported-claim precision pattern used in two verified,
    peer-reviewed papers:
      - Min et al. (2023), "FActScore: Fine-grained Atomic Evaluation of
        Factual Precision in Long Form Text Generation," EMNLP 2023,
        arXiv:2305.14251, Section 3.1, page 3:
        f(y) = (1/|A_y|) * sum_{a in A_y} I[a is supported by C].
      - Wei et al. (2024), "Long-form factuality in large language models"
        (SAFE), NeurIPS 2024, arXiv:2403.18802, Section 5, page 6, Eq. 1:
        Prec(y) = S(y) / (S(y) + N(y)).
    Neither paper defines a metric literally named "Unsupported Claim Rate"
    or "Hallucination Rate" - both frame this ratio direction as precision
    (the complement of what this function computes). SAFE's own authors
    explicitly distinguish "factuality" (external-knowledge grounding, what
    this metric and FActScore/SAFE actually measure) from "hallucination"
    (internal-consistency, a different concept they describe as still
    largely unsolved to measure reliably in long-form settings) - this
    distinction is why this metric is named "Unsupported Claim Rate" here
    rather than "Hallucination Rate."

    Ji et al. (2022/2023), "Survey of Hallucination in Natural Language
    Generation," arXiv:2202.03629, Section 2.1, page 4, is used elsewhere in
    this module (calculate_response_hallucination_type_details) only for the
    intrinsic/extrinsic taxonomy - it is not the source of this formula and
    is not cited here.

    Faithfulness + Unsupported Claim Rate = 1.0 whenever both are computed
    from the same claims_list and both report status VALID or REAL_ZERO -
    they are exact complements by construction, using the identical
    _has_invalid_claim_data check as calculate_faithfulness_details so a
    malformed claims_list can never make the two metrics silently disagree.

    An empty claims_list is never silently scored as 0.0. It is either
    NO_CLAIMS_EXTRACTED (the grounding judge ran successfully and the answer
    genuinely contained no factual claims to check) or EVALUATION_FAILURE
    (the grounding judge/API/parser failed before any claims could be
    extracted) - both report score=None. A non-empty claims_list where some
    claim is missing a boolean `is_supported` field reports
    INVALID_CLAIM_DATA (score=None) instead of silently guessing a default.

    Args:
        claims_list (list): A list of claim dictionaries output by the GroundingJudge.
        evaluation_failed (bool): True when the grounding judge/API/parser
            failed to produce a usable result.
    Returns:
        dict: {"score", "status", "unsupported_count", "total_count"}
    """
    claims = [] if claims_list is None else list(claims_list)

    if evaluation_failed:
        return {
            "score": None,
            "status": UNSUPPORTED_CLAIM_RATE_STATUS_EVALUATION_FAILURE,
            "unsupported_count": None,
            "total_count": len(claims)
        }

    if not claims:
        return {
            "score": None,
            "status": UNSUPPORTED_CLAIM_RATE_STATUS_NO_CLAIMS_EXTRACTED,
            "unsupported_count": 0,
            "total_count": 0
        }

    if _has_invalid_claim_data(claims):
        return {
            "score": None,
            "status": UNSUPPORTED_CLAIM_RATE_STATUS_INVALID_CLAIM_DATA,
            "unsupported_count": None,
            "total_count": len(claims)
        }

    unsupported_count = sum(1 for c in claims if not c["is_supported"])
    score = unsupported_count / len(claims)

    return {
        "score": score,
        "status": UNSUPPORTED_CLAIM_RATE_STATUS_REAL_ZERO if unsupported_count == 0 else UNSUPPORTED_CLAIM_RATE_STATUS_VALID,
        "unsupported_count": unsupported_count,
        "total_count": len(claims)
    }

def calculate_response_hallucination_type_details(claims_list, evaluation_failed=False):
    """
    Computes, for a single response, whether it contains at least one
    Intrinsic-labeled and/or at least one Extrinsic-labeled unsupported
    claim - the per-response building blocks for Intrinsic Response Rate
    and Extrinsic Response Rate.

    Source: Maynez, Narayan, Bohnet, McDonald (2020), "On Faithfulness and
    Factuality in Abstractive Summarization," ACL 2020, arXiv:2005.00661,
    Section 5.2 and Table 2, page 6: "the percentage of summaries where at
    least one word was annotated... as an intrinsic (I) or extrinsic (E)
    hallucination." I and E are computed independently there, not as a
    mutually exclusive partition - a response can be flagged for both,
    matching Ji et al.'s own observation (2022/2023, arXiv:2202.03629,
    Section 6.1, page 15) that "it is common for a single generation to
    have both types." KidsNutriBite adapts Maynez's methodology by using
    LLM-judged atomic claims in place of human-annotated text spans that
    required unanimous agreement across three annotators - the resulting
    numbers are not directly comparable to Maynez's published percentages.
    The Intrinsic/Extrinsic category definitions themselves are Ji et al.'s
    taxonomy (Section 2.1, page 4).

    Status semantics mirror calculate_unsupported_claim_rate_details for the
    is_supported check (same _has_invalid_claim_data helper, so the two
    functions can never disagree about whether a response has any
    unsupported claim at all), plus one additional check specific to this
    function: every unsupported claim must carry a valid `hallucination_type`
    ("Intrinsic" or "Extrinsic", case-insensitive). A response with at least
    one unsupported claim missing or with a malformed hallucination_type
    reports INVALID_TYPE_DATA (has_intrinsic/has_extrinsic=None) rather than
    silently excluding that claim from both counts - this is independent of
    whether the response is_hallucinated overall (that determination only
    needs is_supported, not hallucination_type, and is computed separately
    via calculate_unsupported_claim_rate_details).

    Args:
        claims_list (list): A list of claim dictionaries output by the GroundingJudge.
        evaluation_failed (bool): True when the grounding judge/API/parser
            failed to produce a usable result.
    Returns:
        dict: {"status", "has_intrinsic", "has_extrinsic", "total_count"}
    """
    claims = [] if claims_list is None else list(claims_list)

    if evaluation_failed:
        return {
            "status": RESPONSE_HALLUCINATION_STATUS_EVALUATION_FAILURE,
            "has_intrinsic": None,
            "has_extrinsic": None,
            "total_count": len(claims)
        }

    if not claims:
        return {
            "status": RESPONSE_HALLUCINATION_STATUS_NO_CLAIMS_EXTRACTED,
            "has_intrinsic": None,
            "has_extrinsic": None,
            "total_count": 0
        }

    if _has_invalid_claim_data(claims):
        return {
            "status": RESPONSE_HALLUCINATION_STATUS_INVALID_CLAIM_DATA,
            "has_intrinsic": None,
            "has_extrinsic": None,
            "total_count": len(claims)
        }

    unsupported_claims = [c for c in claims if not c["is_supported"]]

    if not unsupported_claims:
        return {
            "status": RESPONSE_HALLUCINATION_STATUS_REAL_ZERO,
            "has_intrinsic": False,
            "has_extrinsic": False,
            "total_count": len(claims)
        }

    valid_types = {"intrinsic", "extrinsic"}
    has_invalid_type = any(
        not isinstance(c.get("hallucination_type"), str) or c["hallucination_type"].lower() not in valid_types
        for c in unsupported_claims
    )
    if has_invalid_type:
        return {
            "status": RESPONSE_HALLUCINATION_STATUS_INVALID_TYPE_DATA,
            "has_intrinsic": None,
            "has_extrinsic": None,
            "total_count": len(claims)
        }

    has_intrinsic = any(c["hallucination_type"].lower() == "intrinsic" for c in unsupported_claims)
    has_extrinsic = any(c["hallucination_type"].lower() == "extrinsic" for c in unsupported_claims)

    return {
        "status": RESPONSE_HALLUCINATION_STATUS_VALID,
        "has_intrinsic": has_intrinsic,
        "has_extrinsic": has_extrinsic,
        "total_count": len(claims)
    }

CONTEXT_RECALL_STATUS_VALID = "VALID"
CONTEXT_RECALL_STATUS_REAL_ZERO = "REAL_ZERO"
CONTEXT_RECALL_STATUS_MISSING_GROUND_TRUTH = "MISSING_GROUND_TRUTH"
CONTEXT_RECALL_STATUS_EVALUATION_FAILURE = "EVALUATION_FAILURE"

def calculate_context_recall(facts_list):
    """
    Backward-compatible wrapper around calculate_context_recall_details.
    Returns the score only. May be None - see calculate_context_recall_details.
    """
    return calculate_context_recall_details(facts_list)["score"]

def calculate_context_recall_details(facts_list, evaluation_failed=False, ground_truth_available=True):
    """
    Computes Context Recall based on expected fact statement extraction, with
    an explicit validity status.
    Formula: Supported Expected Facts / Total Expected Facts

    Source: RAGAS Context Recall methodology/documentation
    (https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_recall/).
    This metric is NOT defined in Es et al. (2023) "RAGAS: Automated Evaluation of
    Retrieval Augmented Generation" (arXiv:2309.15217) — that paper is explicitly
    reference-free by design and defines only Faithfulness, Answer Relevance, and
    Context Relevance (a distinct, precision-style metric: fraction of the retrieved
    context's own sentences that are relevant, not covered here). Context Recall
    requires a reference answer, sourced instead from RAGAS's later documentation.

    Phase 4E root-cause fix (docs/phase4e_context_recall_fix.md): prior to this
    fix, this function's only branch was `if not facts_list: return 0.0` — an
    empty facts_list produced the exact same 0.0 output whether it meant (a) a
    context judge call that genuinely found zero supported facts, (b) a judge/
    API/parser failure that never produced any facts at all, or (c) a case with
    no applicable RAG ground truth to check recall against in the first place.
    All three collapsed into the same silent 0.0, contaminating the aggregate
    average with a mix of real results and non-results. This function now
    follows the same status-tracking pattern already used by every sibling
    metric in this module (calculate_faithfulness_details,
    calculate_unsupported_claim_rate_details) and in
    evaluation/metrics/retrieval_metrics.py/safety_metrics.py
    (VALID/REAL_ZERO/MISSING_GROUND_TRUTH/EVALUATION_FAILURE) rather than
    inventing a new status vocabulary.

    Args:
        facts_list (list): A list of fact dictionaries output by
            ContextJudge.evaluate_recall (each `{"fact": str, "is_present": bool}`).
        evaluation_failed (bool): True when the context judge/API/parser
            failed to produce a usable result (e.g. ContextJudge.evaluate_recall
            returned {"parse_failed": True, ...}, or the Layer 1 judge call
            raised). Reported as EVALUATION_FAILURE, score=None - never
            silently scored as a real 0.0.
        ground_truth_available (bool): False when this case has no RAG
            ground truth to check Context Recall against in the first place
            (per this project's dataset, that means `relevant_chunk_ids` is
            None - a genuinely structured-DB-only case, not a RAG-answerable
            one). The caller (evaluator.py) determines this from the test
            case, since this function only ever sees the judge's facts_list,
            not the full test case. Reported as MISSING_GROUND_TRUTH,
            score=None - mirrors exactly how calculate_recall_at_k_details/
            calculate_ap_at_k_details/calculate_mrr_at_k_details already
            report MISSING_GROUND_TRUTH when `relevant_chunk_ids` is None,
            so Context Recall's applicable-case scoping now agrees with the
            official retrieval metrics' scoping instead of silently disagreeing
            with it.

    Returns:
        dict: {"score", "status", "supported_count", "total_count"}
    """
    facts = [] if facts_list is None else list(facts_list)

    if evaluation_failed:
        return {
            "score": None,
            "status": CONTEXT_RECALL_STATUS_EVALUATION_FAILURE,
            "supported_count": None,
            "total_count": len(facts)
        }

    if not ground_truth_available:
        return {
            "score": None,
            "status": CONTEXT_RECALL_STATUS_MISSING_GROUND_TRUTH,
            "supported_count": None,
            "total_count": None
        }

    if not facts:
        # Genuinely nothing expected (no gold facts) - not currently exercised
        # by any of the 49 finalized dataset cases (every case has >=1 gold
        # fact), preserved as a safe, honest default for any future case that
        # might. Deliberately reuses MISSING_GROUND_TRUTH rather than a new
        # "NO_FACTS_EXPECTED" status: there is nothing to measure recall
        # against, which is exactly what MISSING_GROUND_TRUTH already means
        # for every sibling metric in this codebase.
        return {
            "score": None,
            "status": CONTEXT_RECALL_STATUS_MISSING_GROUND_TRUTH,
            "supported_count": 0,
            "total_count": 0
        }

    supported_count = sum(1 for f in facts if f.get("is_present", False))
    score = supported_count / len(facts)

    return {
        "score": score,
        "status": CONTEXT_RECALL_STATUS_REAL_ZERO if supported_count == 0 else CONTEXT_RECALL_STATUS_VALID,
        "supported_count": supported_count,
        "total_count": len(facts)
    }
