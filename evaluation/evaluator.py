import time
import json
import traceback

class KidsNutriEvaluator:
    """
    Master Orchestrator (Layer 3)
    Strictly coordinates the execution sequence.
    Contains no business logic, LLM prompts, or mathematical computations.
    """
    def __init__(self, llm_client, retriever, planner, judge_model="gemini", judges=None, metrics=None):
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
        profile = test_case["profile"]
        expected_context = test_case.get("expected_context", [])
        
        # --- Step 1: System Execution ---
        retrieved_contexts = self.retriever.retrieve(question, top_k=5)
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
            relevance_data = {"relevance_map": []}
            recall_data = {"facts": []}
            grounding_data = {"claims": []}
            relevancy_data = {"generated_questions": []}
            safety_data = {"overall": "Parse_Error"}
            
        # --- Step 3: Layer 2 (Deterministic Mathematics) ---
        try:
            # 1. Retrieval Metrics
            rm = self.metrics["retrieval"]
            relevance_labels = [item.get("is_relevant", False) for item in relevance_data.get("relevance_map", [])]
            precision_5 = rm.calculate_precision_at_k(relevance_labels, k=5)
            mrr_5 = rm.calculate_mrr_at_k(relevance_labels, k=5)
            ap_5 = rm.calculate_ap_at_k(relevance_labels, k=5)
            
            # 2. Grounding Metrics
            gm = self.metrics["grounding"]
            claims = grounding_data.get("claims", [])
            faithfulness = gm.calculate_faithfulness(claims)
            overall_hr = gm.calculate_overall_hallucination_rate(claims)
            intrinsic_hr = gm.calculate_intrinsic_hallucination_rate(claims)
            extrinsic_hr = gm.calculate_extrinsic_hallucination_rate(claims)
            context_recall = gm.calculate_context_recall(recall_data.get("facts", []))
            
            # 3. Relevancy Metrics
            relm = self.metrics["relevancy"]
            questions_list = relevancy_data.get("generated_questions", [])
            # Reusing the existing embedding model from the retriever
            relevancy_scores = relm.calculate_answer_relevancy(question, questions_list, self.retriever.model)
            answer_relevancy = relevancy_scores.get("mean_similarity", 0.0)
            
            # 4. Safety Metrics (Single case metadata, batch is computed in comparator)
            # We pass the raw outputs downstream so comparator.py can batch them.
            
        except Exception as e:
            print(f"[!] Layer 2 Metric Error for QID {q_id}: {e}")
            traceback.print_exc()
            precision_5 = mrr_5 = ap_5 = 0.0
            faithfulness = overall_hr = intrinsic_hr = extrinsic_hr = context_recall = 0.0
            answer_relevancy = 0.0
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
            # MAP is calculated across the dataset, but we store AP@5 here
            "ap_5": ap_5, 
            "context_precision": precision_5, # Stored for backward compat if needed
            "mrr_5": mrr_5,
            "context_recall": context_recall,
            "faithfulness": faithfulness,
            "answer_relevancy": answer_relevancy,
            "is_hallucinated": overall_hr > 0.0,
            "intrinsic_hr": intrinsic_hr,
            "extrinsic_hr": extrinsic_hr,
            
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
