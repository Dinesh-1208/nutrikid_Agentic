import time
import json
import traceback

class KidsNutriEvaluator:
    """
    Master Orchestrator (Layer 3)
    Strictly coordinates the execution sequence.
    Contains no business logic, LLM prompts, or mathematical computations.
    """
    def __init__(self, llm_client, retriever, planner, judge_model="groq_llama70b", judges=None, metrics=None):
        self.llm_client = llm_client
        self.retriever = retriever
        self.planner = planner
        self.judge_model = judge_model
        
        # Dependency Injection (Defaults provided for backward compatibility with main.py)
        if judges is None:
            from evaluation.judges.context_judge import ContextJudge
            from evaluation.judges.grounding_judge import GroundingJudge
            from evaluation.judges.relevancy_judge import RelevancyJudge
            from evaluation.judges.safety_judge import SafetyJudge
            
            self.judges = {
                "context": ContextJudge(llm_client, judge_model),
                "grounding": GroundingJudge(llm_client, judge_model),
                "relevancy": RelevancyJudge(llm_client, judge_model),
                "safety": SafetyJudge(llm_client, judge_model)
            }
        else:
            self.judges = judges
            
        if metrics is None:
            import evaluation.metrics.retrieval_metrics as rm
            import evaluation.metrics.grounding_metrics as gm
            import evaluation.metrics.relevancy_metrics as relm
            import evaluation.metrics.safety_metrics as sm
            self.metrics = {
                "retrieval": rm,
                "grounding": gm,
                "relevancy": relm,
                "safety": sm
            }
        else:
            self.metrics = metrics

    def run_single_evaluation(self, test_case, model_name):
        """
        Executes the strict evaluation sequence for a single test case.
        """
        q_id = test_case.get("id", "N/A")
        question = test_case["question"]
        # profile is CONDITIONAL in the finalized dataset schema (docs/evaluation/
        # final_evaluation_dataset_schema.md) - knowledge-only cases legitimately
        # carry profile=None. Every downstream consumer (planner.generate_meal_plan,
        # SafetyJudge.evaluate_safety) already reads profile fields via .get(...,
        # default) internally, so an empty dict is a safe, non-fabricated stand-in
        # that lets those defaults apply, rather than crashing on None.get(...).
        profile = test_case.get("profile") or {}
        # Context Recall's gold reference material is authored as `gold_facts`
        # (a list of {"fact_id", "fact_text", ...} dicts - see
        # docs/evaluation/final_evaluation_dataset_schema.md section 6) in the
        # finalized dataset, not the older flat `expected_context` string list
        # ContextJudge.evaluate_recall's interface still expects. Extract only
        # the plain fact_text strings the judge actually consumes - never pass
        # the raw gold_facts objects (with their provenance/source_reference
        # metadata) into the prompt. A missing/empty gold_facts list (not
        # currently true for any of the 49 finalized cases, but preserved as
        # a safe default for any future case) still correctly yields an empty
        # list here, matching evaluate_recall's own pre-existing "nothing
        # expected" short-circuit - no new status enum is introduced, since
        # no case in the current finalized dataset exercises that path.
        expected_context = [
            fact.get("fact_text")
            for fact in (test_case.get("gold_facts") or [])
            if fact.get("fact_text")
        ]
        
        # --- Step 1: System Execution ---
        retrieved_contexts = self.retriever.retrieve(question, top_k=5)
        # Retrieval-metric identity must be the source record's own rag_data.json "id"
        # (e.g. "rag_iron_absorption_heme_001"), not the chunker's internal child-chunk
        # id (e.g. "rag_iron_absorption_heme_001_P0_C0", from rag/chunker.py's
        # ParentChildChunker). Gold relevant_chunk_ids in the evaluation dataset are
        # authored at the source-record level, and child-chunk boundaries are an
        # embedding-index implementation detail that shifts whenever a record's text is
        # edited - they are not a stable identifier to author gold data against. Prefer
        # "source_id" (passed through by rag/services/prompt_context_service.py) and
        # fall back to "id" only for any legacy/mocked retriever that doesn't supply it.
        retrieved_chunk_ids = [
            (chunk.get("source_id") or chunk.get("id"))
            for chunk in retrieved_contexts
            if chunk.get("source_id") or chunk.get("id")
        ]
        gold_relevant_chunk_ids = test_case.get("relevant_chunk_ids")
        plan = self.planner.generate_meal_plan(profile)
        
        from llm.prompt_templates import generate_llm_prompt
        system_prompt, user_prompt = generate_llm_prompt(plan, retrieved_contexts, query=question)
        
        response, latency = self.llm_client.generate_response(system_prompt, user_prompt, model_name)
        
        # --- Step 2: Layer 1 (Semantic NLP Extraction) ---
        try:
            # Context Judge
            relevance_data = self.judges["context"].evaluate_precision(question, retrieved_contexts, q_id=q_id)
            recall_data = self.judges["context"].evaluate_recall(retrieved_contexts, expected_context, q_id=q_id, question=question)
            
            # Grounding Judge
            grounding_data = self.judges["grounding"].evaluate_grounding(question, response, retrieved_contexts, plan, q_id=q_id)
            
            # Relevancy Judge
            relevancy_data = self.judges["relevancy"].generate_hypothetical_questions(response, num_questions=3, q_id=q_id)
            
            # Safety Judge
            safety_data = self.judges["safety"].evaluate_safety(question, response, profile, q_id=q_id)
            
        except Exception as e:
            print(f"[!] Layer 1 Judge Error for QID {q_id}: {e}")
            traceback.print_exc()
            relevance_data = {"relevance_map": [], "parse_failed": True, "error": str(e)}
            recall_data = {"facts": []}
            grounding_data = {"claims": [], "parse_failed": True, "error": str(e)}
            relevancy_data = {"generated_questions": [], "parse_failed": True, "error": str(e)}
            safety_data = {"overall": "Parse_Error"}
            
        # --- Step 3: Layer 2 (Deterministic Mathematics) ---
        try:
            # 1. Retrieval Metrics
            rm = self.metrics["retrieval"]
            relevance_labels = [item.get("is_relevant", False) for item in relevance_data.get("relevance_map", [])]
            precision_5_details = rm.calculate_precision_at_k_details(
                relevance_labels,
                k=5,
                evaluation_failed=bool(relevance_data.get("parse_failed"))
            )
            precision_5 = precision_5_details["score"]
            mrr_5_details = rm.calculate_mrr_at_k_details(
                retrieved_chunk_ids,
                gold_relevant_chunk_ids,
                k=5
            )
            mrr_5 = mrr_5_details["score"]
            ap_5_details = rm.calculate_ap_at_k_details(
                retrieved_chunk_ids,
                gold_relevant_chunk_ids,
                k=5
            )
            ap_5 = ap_5_details["score"]
            recall_5_details = rm.calculate_recall_at_k_details(
                retrieved_chunk_ids,
                gold_relevant_chunk_ids,
                k=5
            )
            recall_5 = recall_5_details["score"]
            
            # 2. Grounding Metrics
            gm = self.metrics["grounding"]
            claims = grounding_data.get("claims", [])
            grounding_evaluation_failed = bool(grounding_data.get("parse_failed"))
            faithfulness_details = gm.calculate_faithfulness_details(
                claims,
                evaluation_failed=grounding_evaluation_failed
            )
            faithfulness = faithfulness_details["score"]
            unsupported_claim_rate_details = gm.calculate_unsupported_claim_rate_details(
                claims,
                evaluation_failed=grounding_evaluation_failed
            )
            unsupported_claim_rate = unsupported_claim_rate_details["score"]
            response_hallucination_type_details = gm.calculate_response_hallucination_type_details(
                claims,
                evaluation_failed=grounding_evaluation_failed
            )
            if unsupported_claim_rate_details["status"] in (
                gm.UNSUPPORTED_CLAIM_RATE_STATUS_VALID,
                gm.UNSUPPORTED_CLAIM_RATE_STATUS_REAL_ZERO
            ):
                is_hallucinated = unsupported_claim_rate_details["score"] > 0
            else:
                is_hallucinated = None
            context_recall = gm.calculate_context_recall(recall_data.get("facts", []))
            
            # 3. Relevancy Metrics
            relm = self.metrics["relevancy"]
            questions_list = relevancy_data.get("generated_questions", [])
            # Reusing the existing embedding model from the retriever
            relevancy_scores = relm.calculate_answer_relevancy(
                question,
                questions_list,
                self.retriever.model,
                evaluation_failed=bool(relevancy_data.get("parse_failed"))
            )
            answer_relevancy = relevancy_scores["mean_similarity"]
            
            # 4. Safety Metrics (Single case metadata, batch is computed in comparator)
            # We pass the raw outputs downstream so comparator.py can batch them.
            
        except Exception as e:
            print(f"[!] Layer 2 Metric Error for QID {q_id}: {e}")
            traceback.print_exc()
            precision_5 = None
            precision_5_details = {
                "score": None,
                "status": "EVALUATION_FAILURE",
                "k": 5,
                "label_count": 0,
                "relevant_count": None
            }
            mrr_5 = None
            mrr_5_details = {
                "score": None,
                "status": getattr(rm, "MRR_STATUS_EVALUATION_FAILURE", "EVALUATION_FAILURE"),
                "k": 5,
                "retrieved_count": 0,
                "first_relevant_rank": None,
                "gold_relevant_count": None
            }
            ap_5 = None
            ap_5_details = {
                "score": None,
                "status": "EVALUATION_FAILURE",
                "k": 5,
                "retrieved_count": 0,
                "relevance_labels": [],
                "retrieved_relevant_count": None,
                "total_relevant_count": None
            }
            recall_5 = None
            recall_5_details = {
                "score": None,
                "status": getattr(rm, "RECALL_STATUS_EVALUATION_FAILURE", "EVALUATION_FAILURE"),
                "k": 5,
                "retrieved_count": 0,
                "retrieved_relevant_count": None,
                "total_relevant_count": None
            }
            faithfulness = None
            faithfulness_details = {
                "score": None,
                "status": "EVALUATION_FAILURE",
                "supported_count": None,
                "total_count": 0
            }
            unsupported_claim_rate = None
            unsupported_claim_rate_details = {
                "score": None,
                "status": "EVALUATION_FAILURE",
                "unsupported_count": None,
                "total_count": 0
            }
            response_hallucination_type_details = {
                "status": "EVALUATION_FAILURE",
                "has_intrinsic": None,
                "has_extrinsic": None,
                "total_count": 0
            }
            is_hallucinated = None
            context_recall = 0.0
            answer_relevancy = None
            relevancy_scores = {
                "question_scores": [],
                "mean_similarity": None,
                "std_similarity": None,
                "status": "EVALUATION_FAILURE"
            }
            claims = []

        # --- Step 4: Aggregation ---
        # Deterministic refusal check
        is_refusal = "cannot diagnose" in response.lower() or "cannot prescribe" in response.lower() or "consult a pediatrician" in response.lower() or "pediatrician" in response.lower()
        
        return {
            "id": q_id,
            "category": test_case["category"],
            "question": question,
            "response": response,
            "latency": latency,
            "ap_5": ap_5, 
            "ap_5_status": ap_5_details["status"],
            "ap_5_relevance_labels": ap_5_details["relevance_labels"],
            "ap_5_retrieved_count": ap_5_details["retrieved_count"],
            "ap_5_retrieved_relevant_count": ap_5_details["retrieved_relevant_count"],
            "ap_5_total_relevant_count": ap_5_details["total_relevant_count"],
            "context_precision": precision_5, # Stored for backward compat if needed
            "precision_at_5_status": precision_5_details["status"],
            "precision_at_5_label_count": precision_5_details["label_count"],
            "precision_at_5_relevant_count": precision_5_details["relevant_count"],
            "recall_5": recall_5,
            "recall_5_status": recall_5_details["status"],
            "recall_5_retrieved_count": recall_5_details["retrieved_count"],
            "recall_5_retrieved_relevant_count": recall_5_details["retrieved_relevant_count"],
            "recall_5_total_relevant_count": recall_5_details["total_relevant_count"],
            "mrr_5": mrr_5,
            "mrr_5_status": mrr_5_details["status"],
            "mrr_5_first_relevant_rank": mrr_5_details["first_relevant_rank"],
            "mrr_5_retrieved_count": mrr_5_details["retrieved_count"],
            "mrr_5_gold_relevant_count": mrr_5_details["gold_relevant_count"],
            "context_recall": context_recall,
            "faithfulness": faithfulness,
            "faithfulness_status": faithfulness_details["status"],
            "faithfulness_supported_count": faithfulness_details["supported_count"],
            "faithfulness_total_count": faithfulness_details["total_count"],
            "answer_relevancy": answer_relevancy,
            "answer_relevancy_status": relevancy_scores["status"],
            "answer_relevancy_valid_question_count": len(relevancy_scores.get("question_scores", [])),
            "unsupported_claim_rate": unsupported_claim_rate,
            "unsupported_claim_rate_status": unsupported_claim_rate_details["status"],
            "unsupported_claim_rate_unsupported_count": unsupported_claim_rate_details["unsupported_count"],
            "unsupported_claim_rate_total_count": unsupported_claim_rate_details["total_count"],
            # is_hallucinated is None (not False) whenever the underlying evaluation
            # was not VALID/REAL_ZERO - an unknown evaluation is never counted as a
            # clean non-hallucinated response.
            "is_hallucinated": is_hallucinated,
            "has_intrinsic_claim": response_hallucination_type_details["has_intrinsic"],
            "has_extrinsic_claim": response_hallucination_type_details["has_extrinsic"],
            "hallucination_type_status": response_hallucination_type_details["status"],

            # Safety granular data
            "safety_judge_raw": safety_data,
            "is_safe": safety_data.get("overall", "").lower() in ["compliant", "refusal"],
            "violation_type": "none" if safety_data.get("overall", "").lower() in ["compliant", "refusal"] else "violation",
            "is_refusal": is_refusal,
            "safety_reason": safety_data.get("reasoning", ""),
            
            "retrieved_chunks": "\n---\n".join([c['text'] for c in retrieved_contexts]),
            "similarity_scores": ", ".join([f"{c['score']:.4f}" for c in retrieved_contexts]),
            "planner_output": json.dumps(plan),
            "ground_truth": test_case.get("reference_answer", ""),
            "expected_context": expected_context,
            "claims": claims
        }
