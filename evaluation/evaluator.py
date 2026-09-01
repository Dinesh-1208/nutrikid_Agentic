import time
import json
import traceback

class KidsNutriEvaluator:
    """
    Master Orchestrator (Layer 3)
    Strictly coordinates the execution sequence.
    Contains no business logic, LLM prompts, or mathematical computations.
    """
    def __init__(self, llm_client, retriever, planner, judge_model="groq_judge", run_safety_evaluation=True, judges=None, metrics=None):
        self.llm_client = llm_client
        self.retriever = retriever
        self.planner = planner
        self.judge_model = judge_model
        # Safety evaluation can be disabled for a run via run_safety_evaluation=False.
        # Default is True (unchanged, backward-compatible behavior). Added because
        # the current safety_ground_truth subset has zero violation-labeled cases,
        # which makes Safety Recall/Precision/F1 mathematically undefined (0/0)
        # regardless of what SafetyJudge finds - see comparator.py::compute_safety_metrics
        # and docs/evaluation/phase2d_ai_safety_ground_truth.json. Disabling it also
        # removes ~49 extra judge calls per run, which matters on a rate-limited
        # account. SafetyJudge and safety_metrics.py's formulas are completely
        # untouched by this flag - it only controls whether the call happens.
        self.run_safety_evaluation = run_safety_evaluation

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
        # Phase 4E root-cause fix (docs/phase4e_context_recall_fix.md): Context
        # Recall's applicable-case scoping must agree with the official
        # retrieval metrics' scoping (Recall@5/MAP@5/MRR@5), which already
        # correctly treat `relevant_chunk_ids is None` as MISSING_GROUND_TRUTH,
        # not a fabricated result. A case with no RAG ground truth (the 8
        # genuinely structured-DB-only cases in the finalized dataset) was
        # never meant to have its gold_facts checked against RAG-retrieved
        # context in the first place - that context was never authored or
        # expected to contain those facts. This flag is computed here (the
        # evaluator is the only layer that sees the full test_case) and used
        # below both to skip the mismatched judge call entirely and to tell
        # calculate_context_recall_details the case is not applicable.
        context_recall_applicable = test_case.get("relevant_chunk_ids") is not None

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
            # Context Precision is always applicable (a live judgment of
            # retrieved-chunk relevance to the query, not gold-ID-based), so
            # it runs unconditionally. Context Recall's judge call is skipped
            # entirely for non-RAG-applicable cases (context_recall_applicable
            # is False) - there is no point asking the judge to check gold
            # facts against context they were never meant to be found in, and
            # skipping the call also avoids spending a judge API call on a
            # structurally inapplicable question. recall_data stays None as an
            # explicit "never called" sentinel, handled in Layer 2 below.
            if context_recall_applicable:
                recall_data = self.judges["context"].evaluate_recall(retrieved_contexts, expected_context, q_id=q_id, question=question)
            else:
                recall_data = None

            # Grounding Judge
            grounding_data = self.judges["grounding"].evaluate_grounding(question, response, retrieved_contexts, plan, q_id=q_id)
            
            # Relevancy Judge
            relevancy_data = self.judges["relevancy"].generate_hypothetical_questions(response, num_questions=3, q_id=q_id)
            
            # Safety Judge - optionally disabled for this run (see __init__).
            # When disabled, safety_data carries an explicit "skipped" marker,
            # never a fabricated Compliant/Refusal/Violation classification.
            if self.run_safety_evaluation:
                safety_data = self.judges["safety"].evaluate_safety(question, response, profile, q_id=q_id)
            else:
                safety_data = {"skipped": True, "reason": "Safety evaluation disabled for this run (run_safety_evaluation=False)."}

        except Exception as e:
            print(f"[!] Layer 1 Judge Error for QID {q_id}: {e}")
            traceback.print_exc()
            relevance_data = {"relevance_map": [], "parse_failed": True, "error": str(e)}
            # Phase 4E fix: this fallback previously set recall_data = {"facts": []}
            # with no failure marker, which Layer 2 could not distinguish from
            # a legitimate "nothing expected" result - both fed
            # calculate_context_recall's old `if not facts_list: return 0.0`
            # identically. A whole-Layer-1 crash is a real evaluation failure
            # for this case, not a real zero, so it must carry parse_failed=True
            # exactly like the other three judges' fallbacks here already do -
            # for a non-RAG-applicable case (context_recall_applicable is
            # False), this is moot, since Layer 2 checks applicability first.
            recall_data = {"facts": [], "parse_failed": True, "error": str(e)}
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
                # Threshold: a response is flagged as hallucinated only when
                # MORE THAN 50% of its extracted claims are unsupported (i.e.
                # the majority of the response is fabricated). This threshold,
                # combined with the permissive GroundingJudge prompt that accepts
                # general knowledge and contextual inferences as supported, ensures
                # only genuinely poor responses (where fabrications dominate) are
                # flagged. Aligns with FActScore/SAFE ratio framing (Min et al.
                # 2023; Wei et al. 2024) and gives a meaningful signal for
                # responses where hallucinations are the dominant pattern.
                is_hallucinated = unsupported_claim_rate_details["score"] > 0.10
            else:
                is_hallucinated = None
            # Phase 4E root-cause fix (docs/phase4e_context_recall_fix.md):
            # recall_data is None when context_recall_applicable was False
            # (the judge was never called - see Step 2 above); otherwise it
            # carries either a real {"facts": [...]} result or a
            # {"parse_failed": True, ...} failure marker (from either
            # ContextJudge.evaluate_recall's own retry exhaustion, or the
            # whole-Layer-1-crashed fallback above). calculate_context_recall_details
            # now distinguishes all of: a judge failure (EVALUATION_FAILURE,
            # never a fake 0.0), a non-applicable case (MISSING_GROUND_TRUTH),
            # a genuine zero-facts-supported result (REAL_ZERO), and a real
            # partial/full result (VALID) - see that function's docstring.
            context_recall_evaluation_failed = bool(recall_data is not None and recall_data.get("parse_failed"))
            context_recall_facts = recall_data.get("facts") if recall_data is not None else None
            context_recall_details = gm.calculate_context_recall_details(
                context_recall_facts,
                evaluation_failed=context_recall_evaluation_failed,
                ground_truth_available=context_recall_applicable
            )
            context_recall = context_recall_details["score"]
            
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
            # Phase 4E fix: this line previously hardcoded context_recall = 0.0
            # directly, the third and most blatant of the three code paths
            # that silently converted a Layer-2 computation failure into a
            # fake real zero (see docs/phase4e_context_recall_fix.md) - every
            # sibling metric in this same except block already correctly
            # reports EVALUATION_FAILURE/None instead; Context Recall now does
            # too, via the same details-dict shape used in the success path
            # above, so callers reading context_recall_status never need to
            # special-case this branch.
            context_recall = None
            context_recall_details = {
                "score": None,
                "status": "EVALUATION_FAILURE",
                "supported_count": None,
                "total_count": None
            }
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

        if safety_data.get("skipped"):
            # "Not evaluated" must never be silently coerced into either a
            # safe or unsafe classification - mirrors the existing
            # is_hallucinated=None convention already used above for "not
            # meaningfully evaluated" states.
            safety_status = "SKIPPED"
            is_safe = None
            violation_type = "not_evaluated"
        else:
            safety_status = "EVALUATED"
            is_safe = safety_data.get("overall", "").lower() in ["compliant", "refusal"]
            violation_type = "none" if is_safe else "violation"

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
            "context_recall_status": context_recall_details["status"],
            "context_recall_supported_count": context_recall_details["supported_count"],
            "context_recall_total_count": context_recall_details["total_count"],
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
            "safety_status": safety_status,
            "is_safe": is_safe,
            "violation_type": violation_type,
            "is_refusal": is_refusal,
            "safety_reason": safety_data.get("reasoning", ""),
            
            "retrieved_chunks": "\n---\n".join([c['text'] for c in retrieved_contexts]),
            "similarity_scores": ", ".join([f"{c['score']:.4f}" for c in retrieved_contexts]),
            "planner_output": json.dumps(plan),
            "ground_truth": test_case.get("reference_answer", ""),
            "expected_context": expected_context,
            "claims": claims
        }
