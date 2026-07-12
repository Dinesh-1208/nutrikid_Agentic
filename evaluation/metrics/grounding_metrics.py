"""
Deterministic Mathematics for Grounding, Faithfulness, and Hallucination Metrics.
No LLM dependencies. All semantic reasoning is previously performed by Layer 1 Judges.
"""

def calculate_faithfulness(claims_list):
    """
    Computes Faithfulness Score based on the RAGAS framework.
    Formula: Supported Claims / Total Extracted Claims
    Paper Reference: Es et al. (2023) "RAGAS: Automated Evaluation of Retrieval Augmented Generation"
    
    Args:
        claims_list (list): A list of claim dictionaries output by the GroundingJudge.
    Returns:
        float: Faithfulness score between 0.0 and 1.0.
    """
    if not claims_list:
        return 0.0
    supported = sum(1 for c in claims_list if c.get("is_supported", False))
    return supported / len(claims_list)

def calculate_overall_hallucination_rate(claims_list):
    """
    Computes the Overall Hallucination Rate.
    Formula: Unsupported Claims / Total Extracted Claims
    Paper Reference: Ji et al. (2023) "Survey of Hallucination in Natural Language Generation"
    
    Args:
        claims_list (list): A list of claim dictionaries.
    Returns:
        float: Hallucination rate between 0.0 and 1.0.
    """
    if not claims_list:
        return 0.0
    unsupported = sum(1 for c in claims_list if not c.get("is_supported", True))
    return unsupported / len(claims_list)

def calculate_intrinsic_hallucination_rate(claims_list):
    """
    Computes the Intrinsic Hallucination Rate.
    Formula: Intrinsic Unsupported Claims / Total Extracted Claims
    Paper Reference: Ji et al. (2023) "Survey of Hallucination in Natural Language Generation"
    
    Args:
        claims_list (list): A list of claim dictionaries.
    Returns:
        float: Intrinsic Hallucination rate between 0.0 and 1.0.
    """
    if not claims_list:
        return 0.0
    intrinsic = sum(
        1 for c in claims_list 
        if not c.get("is_supported", True) and c.get("hallucination_type", "").lower() == "intrinsic"
    )
    return intrinsic / len(claims_list)

def calculate_extrinsic_hallucination_rate(claims_list):
    """
    Computes the Extrinsic Hallucination Rate.
    Formula: Extrinsic Unsupported Claims / Total Extracted Claims
    Paper Reference: Ji et al. (2023) "Survey of Hallucination in Natural Language Generation"
    
    Args:
        claims_list (list): A list of claim dictionaries.
    Returns:
        float: Extrinsic Hallucination rate between 0.0 and 1.0.
    """
    if not claims_list:
        return 0.0
    extrinsic = sum(
        1 for c in claims_list 
        if not c.get("is_supported", True) and c.get("hallucination_type", "").lower() == "extrinsic"
    )
    return extrinsic / len(claims_list)

def calculate_context_recall(facts_list):
    """
    Computes Context Recall based on expected fact statement extraction.
    Formula: Supported Expected Facts / Total Expected Facts
    Paper Reference: Es et al. (2023) "RAGAS: Automated Evaluation of Retrieval Augmented Generation"
    
    Args:
        facts_list (list): A list of fact dictionaries output by the ContextJudge.
    Returns:
        float: Context Recall score between 0.0 and 1.0.
    """
    if not facts_list:
        return 0.0
    supported_facts = sum(1 for f in facts_list if f.get("is_present", False))
    return supported_facts / len(facts_list)
