import os
import json
import time
import re
import pandas as pd
from tabulate import tabulate
from evaluation.dataset import EVALUATION_DATA
from evaluation.evaluator import KidsNutriEvaluator
from evaluation.metrics.safety_metrics import (
    evaluate_safety_batch,
    SAFETY_STATUS_MISSING_GROUND_TRUTH,
    SAFETY_STATUS_VALID,
)

class KidsNutriComparator:
    def __init__(self, evaluator: KidsNutriEvaluator, reports_dir=None):
        self.evaluator = evaluator
        if reports_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            reports_dir = os.path.join(base_dir, "reports")
        self.reports_dir = reports_dir
        os.makedirs(self.reports_dir, exist_ok=True)

    def compute_safety_metrics(self, model_res, dataset, category_filter=None):
        """
        Computes the official KidsNutriBite safety metric set: Recall
        (primary), Precision (companion), F1 (summary). Accuracy and F2 are
        not part of the official set - the safety literature audit
        (docs/safety_evaluation_literature_audit.md) found no support for
        either in Llama 2, XSTest, Llama Guard, MedSafetyBench, or NOHARM.

        Ground truth must be real, annotated per-case safety outcome data -
        test_case["safety_ground_truth"]. `is_safety` is preserved ONLY as
        a topic/safety-relevance flag (per XSTest: topic sensitivity is not
        the same as required outcome - a safety-sensitive question can have
        a legitimately safe/compliant answer) and is never used to infer an
        outcome label here. No such ground-truth field exists in the
        dataset yet, so every case is currently MISSING_GROUND_TRUTH - this
        function reports that honestly (score=None) rather than fabricating
        a result, matching Llama 2/NOHARM's expert/content-based annotation
        standard rather than a topic-flag proxy.
        """
        preds = []
        gts = []
        missing_ground_truth_count = 0

        for case in model_res:
            tc = next(t for t in dataset if t["id"] == case["id"])
            if category_filter and tc["category"] != category_filter:
                continue

            ground_truth = tc.get("safety_ground_truth")
            if ground_truth is None:
                missing_ground_truth_count += 1
                continue

            preds.append(case.get("safety_judge_raw", {}))
            gts.append(ground_truth)

        if not gts:
            return {
                "status": SAFETY_STATUS_MISSING_GROUND_TRUTH,
                "recall": None,
                "precision": None,
                "f1": None,
                "valid_cases": 0,
                "missing_ground_truth_cases": missing_ground_truth_count
            }

        batch_result = evaluate_safety_batch(preds, gts)
        overall = batch_result["overall"]
        return {
            "status": SAFETY_STATUS_VALID,
            "recall": overall["recall"],
            "precision": overall["precision"],
            "f1": overall["f1"],
            "valid_cases": len(gts),
            "missing_ground_truth_cases": missing_ground_truth_count
        }

    def run_comparison(self, models=["qwen_local"], sample_limit=None):
        dataset = EVALUATION_DATA
        if sample_limit:
            # Take a balanced subset across categories
            categories = list(set([item["category"] for item in dataset]))
            subset = []
            per_cat = max(1, sample_limit // len(categories))
            cat_counts = {c: 0 for c in categories}
            for item in dataset:
                cat = item["category"]
                if cat_counts[cat] < per_cat:
                    subset.append(item)
                    cat_counts[cat] += 1
            dataset = subset

        print(f"Starting deterministic model comparison on {len(dataset)} evaluation questions...")
        
        results = {}
        retrieval_trace = []
        
        for model in models:
            print(f"\nEvaluating Model: {model.upper()}...")
            model_results = []
            for i, test_case in enumerate(dataset, 1):
                print(f"  [{i}/{len(dataset)}] Running Question ID: {test_case['id']}...")
                eval_res = self.evaluator.run_single_evaluation(test_case, model)
                model_results.append(eval_res)
                
                retrieval_trace.append({
                    "Model": model.upper(),
                    "QuestionID": test_case["id"],
                    "Question": eval_res["question"],
                    "Retrieved Chunks": eval_res["retrieved_chunks"],
                    "Similarity Scores": eval_res.get("similarity_scores", "")
                })
                
                time.sleep(0.5)
            results[model] = model_results
            
        # ================= SAVE RETRIEVAL TRACE =================
        trace_df = pd.DataFrame(retrieval_trace)
        trace_csv_path = os.path.join(self.reports_dir, "retrieval_trace.csv")
        trace_df.to_csv(trace_csv_path, index=False)

        # ================= DETAILED EXPORT =================
        detailed_records = []
        for model, model_res in results.items():
            for record in model_res:
                detailed_records.append({
                    "Model": model.upper(),
                    "Question": record["question"],
                    "Expected Answer": record["ground_truth"],
                    "Model Answer": record["response"],
                    "Retrieved Chunks": record["retrieved_chunks"],
                    "Planner Output": record["planner_output"]
                })
        
        detailed_df = pd.DataFrame(detailed_records)
        detailed_csv_path = os.path.join(self.reports_dir, "detailed_evaluation_records.csv")
        detailed_df.to_csv(detailed_csv_path, index=False)

        # ================= RAG EVALUATION =================
        ragas_records = []
        for model, model_res in results.items():
            for record in model_res:
                ragas_records.append({
                    "Model": model.upper(),
                    "Question": record["question"],
                    "Context Precision": record["context_precision"],
                    "Context Precision Status": record.get("precision_at_5_status", "UNKNOWN"),
                    "Context Precision Label Count": record.get("precision_at_5_label_count", ""),
                    "Context Precision Relevant Count": record.get("precision_at_5_relevant_count", ""),
                    "Recall@5": record.get("recall_5"),
                    "Recall@5 Status": record.get("recall_5_status", "UNKNOWN"),
                    "Recall@5 Retrieved Count": record.get("recall_5_retrieved_count", ""),
                    "Recall@5 Retrieved Relevant Count": record.get("recall_5_retrieved_relevant_count", ""),
                    "Recall@5 Total Relevant Count": record.get("recall_5_total_relevant_count", ""),
                    "AP@5": record["ap_5"],
                    "AP@5 Status": record.get("ap_5_status", "UNKNOWN"),
                    "AP@5 Relevance Labels": record.get("ap_5_relevance_labels", []),
                    "AP@5 Retrieved Count": record.get("ap_5_retrieved_count", ""),
                    "AP@5 Retrieved Relevant Count": record.get("ap_5_retrieved_relevant_count", ""),
                    "AP@5 Total Relevant Count": record.get("ap_5_total_relevant_count", ""),
                    "MRR@5": record["mrr_5"],
                    "MRR@5 Status": record.get("mrr_5_status", "UNKNOWN"),
                    "MRR@5 First Relevant Rank": record.get("mrr_5_first_relevant_rank", ""),
                    "MRR@5 Retrieved Count": record.get("mrr_5_retrieved_count", ""),
                    "MRR@5 Gold Relevant Count": record.get("mrr_5_gold_relevant_count", ""),
                    "Context Recall": record["context_recall"],
                    "Faithfulness": record["faithfulness"],
                    "Answer Relevancy": record["answer_relevancy"]
                })
        ragas_df = pd.DataFrame(ragas_records)
        ragas_report_path = os.path.join(self.reports_dir, "ragas_report.csv")
        ragas_df.to_csv(ragas_report_path, index=False)

        # ================= HALLUCINATION ANALYSIS =================
        # Response-level rates (unit: one evaluated question-answer pair). An
        # unknown evaluation (is_hallucinated/has_intrinsic_claim/
        # has_extrinsic_claim is None - EVALUATION_FAILURE, NO_CLAIMS_EXTRACTED,
        # INVALID_CLAIM_DATA, or INVALID_TYPE_DATA) is excluded from both the
        # numerator and denominator rather than silently counted as "not
        # hallucinated". Intrinsic Response Rate and Extrinsic Response Rate are
        # computed independently (Maynez et al. 2020, ACL, arXiv:2005.00661,
        # Table 2/Sec 5.2 p.6) - a response with both types counts in both
        # rates, so Hallucination Rate <= Intrinsic Response Rate + Extrinsic
        # Response Rate, not a strict sum.
        with open(os.path.join(self.reports_dir, "hallucination_analysis.md"), "w", encoding="utf-8") as f:
            f.write("# KidsNutriBite Hallucination Analysis\n\n")
            for model, model_res in results.items():
                valid_hallucination_cases = [r for r in model_res if r.get("is_hallucinated") is not None]
                hallucinated_cases = [r for r in valid_hallucination_cases if r["is_hallucinated"]]
                rate = len(hallucinated_cases) / len(valid_hallucination_cases) if valid_hallucination_cases else None

                valid_intrinsic_cases = [r for r in model_res if r.get("has_intrinsic_claim") is not None]
                intrinsic_rate = (
                    sum(1 for r in valid_intrinsic_cases if r["has_intrinsic_claim"]) / len(valid_intrinsic_cases)
                    if valid_intrinsic_cases else None
                )
                valid_extrinsic_cases = [r for r in model_res if r.get("has_extrinsic_claim") is not None]
                extrinsic_rate = (
                    sum(1 for r in valid_extrinsic_cases if r["has_extrinsic_claim"]) / len(valid_extrinsic_cases)
                    if valid_extrinsic_cases else None
                )
                valid_unsupported_claim_rates = [r.get("unsupported_claim_rate") for r in model_res if r.get("unsupported_claim_rate") is not None]
                avg_unsupported_claim_rate = (
                    sum(valid_unsupported_claim_rates) / len(valid_unsupported_claim_rates)
                    if valid_unsupported_claim_rates else None
                )

                f.write(f"## Model: {model.upper()}\n")
                f.write(f"- **Hallucination Rate (response-level):** {f'{rate*100:.2f}%' if rate is not None else 'N/A (no valid evaluations)'}\n")
                f.write(f"- **Intrinsic Response Rate (response-level):** {f'{intrinsic_rate*100:.2f}%' if intrinsic_rate is not None else 'N/A (no valid evaluations)'}\n")
                f.write(f"- **Extrinsic Response Rate (response-level):** {f'{extrinsic_rate*100:.2f}%' if extrinsic_rate is not None else 'N/A (no valid evaluations)'}\n")
                f.write(f"- **Unsupported Claim Rate (claim-level):** {f'{avg_unsupported_claim_rate*100:.2f}%' if avg_unsupported_claim_rate is not None else 'N/A (no valid evaluations)'}\n")
                f.write("- *(Intrinsic/Extrinsic Response Rate are independent - a response with both types counts in both; Hallucination Rate is their union, so it need not equal their sum.)*\n\n")

                if hallucinated_cases:
                    f.write("| Question | Model Response | Claims |\n")
                    f.write("| --- | --- | --- |\n")
                    for case in hallucinated_cases:
                        claims_str = "<br>".join([
                            f"• {c['claim']} (Supported: {c['is_supported']}"
                            + (f", Type: {c.get('hallucination_type', 'unlabeled')}" if not c.get("is_supported", True) else "")
                            + ")"
                            for c in case.get("claims", [])
                        ])
                        f.write(f"| {case['question']} | {case['response']} | {claims_str} |\n")
                else:
                    f.write("No hallucinated examples found.\n")
                f.write("\n---\n\n")

        # ================= SAFETY ANALYSIS =================
        # Official safety metric set: Recall (primary), Precision (companion),
        # F1 (summary) - see docs/safety_evaluation_literature_audit.md.
        # Accuracy and F2 were removed (no support in the verified literature).
        # Refusal Rate on known-safe prompts (XSTest-aligned) is deferred until
        # ground truth for known-safe prompts exists - not computed here yet.
        def _write_safety_block(f, title, safety_result):
            f.write(f"### {title}\n")
            if safety_result["status"] == SAFETY_STATUS_MISSING_GROUND_TRUTH:
                f.write(
                    "**Not reportable: valid safety ground truth does not yet exist.** "
                    f"({safety_result['missing_ground_truth_cases']} case(s) have no annotated "
                    "`safety_ground_truth`.) `is_safety` is a topic/safety-relevance flag only and "
                    "is not used as an outcome label.\n\n"
                )
                return
            f.write("| Metric | Value |\n")
            f.write("| --- | --- |\n")
            f.write(f"| Recall | {safety_result['recall']} |\n")
            f.write(f"| Precision | {safety_result['precision']} |\n")
            f.write(f"| F1 | {safety_result['f1']} |\n")
            f.write(f"| Valid Cases | {safety_result['valid_cases']} |\n")
            f.write("\n")

        with open(os.path.join(self.reports_dir, "safety_analysis.md"), "w", encoding="utf-8") as f:
            f.write("# KidsNutriBite Deterministic Safety Analysis Report\n\n")
            for model, model_res in results.items():
                overall_safety = self.compute_safety_metrics(model_res, dataset)
                allergy_safety = self.compute_safety_metrics(model_res, dataset, category_filter="allergies")

                f.write(f"## Model: {model.upper()}\n\n")
                _write_safety_block(f, "Overall System Safety", overall_safety)
                _write_safety_block(f, "Allergy-Specific Queries Safety", allergy_safety)
                f.write("---\n\n")

        # ================= RETRIEVAL DIAGNOSTICS (unofficial, LLM-judged, not gold-grounded) =================
        self.run_llm_judged_relevance_experiment(dataset)

        # ================= FINAL REPORT =================
        comparison_records = []
        for model in results.keys():
            model_res = results[model]
            df = pd.DataFrame(model_res)
            
            map_5_details = self.evaluator.metrics["retrieval"].calculate_map_at_k_details([
                {
                    "score": record.get("ap_5"),
                    "status": record.get("ap_5_status")
                }
                for record in model_res
            ])
            mrr_5_details = self.evaluator.metrics["retrieval"].calculate_mean_mrr_at_k_details([
                {
                    "score": record.get("mrr_5"),
                    "status": record.get("mrr_5_status")
                }
                for record in model_res
            ])
            valid_recall_5 = [r.get("recall_5") for r in model_res if r.get("recall_5") is not None]
            avg_recall_5 = sum(valid_recall_5) / len(valid_recall_5) if valid_recall_5 else None
            missing_recall_5_gt = sum(1 for r in model_res if r.get("recall_5_status") == "MISSING_GROUND_TRUTH")
            avg_recall = df["context_recall"].mean()
            avg_faithfulness = df["faithfulness"].mean()
            avg_relevancy = df["answer_relevancy"].mean()
            
            # Response-level rates: an unknown evaluation (is_hallucinated /
            # has_intrinsic_claim / has_extrinsic_claim is None) is excluded from
            # both the numerator and denominator, never silently counted as
            # "not hallucinated". Intrinsic/Extrinsic Response Rate are
            # independent (Maynez et al. 2020, Table 2/Sec 5.2 p.6) - a response
            # with both types counts in both, so Hallucination Rate need not
            # equal their sum.
            valid_hallucination = [r.get("is_hallucinated") for r in model_res if r.get("is_hallucinated") is not None]
            hallucination_rate = sum(valid_hallucination) / len(valid_hallucination) if valid_hallucination else None

            valid_intrinsic = [r.get("has_intrinsic_claim") for r in model_res if r.get("has_intrinsic_claim") is not None]
            intrinsic_response_rate = sum(valid_intrinsic) / len(valid_intrinsic) if valid_intrinsic else None

            valid_extrinsic = [r.get("has_extrinsic_claim") for r in model_res if r.get("has_extrinsic_claim") is not None]
            extrinsic_response_rate = sum(valid_extrinsic) / len(valid_extrinsic) if valid_extrinsic else None

            safety_stats = self.compute_safety_metrics(model_res, dataset)

            comparison_records.append({
                "Model": model.upper(),
                "map_5": round(map_5_details["score"], 4) if map_5_details["score"] is not None else None,
                "MAP@5": round(map_5_details["score"], 4) if map_5_details["score"] is not None else None,
                "map_5_valid_cases": map_5_details["valid_cases"],
                "map_5_missing_ground_truth": map_5_details["missing_ground_truth"],
                "map_5_real_zero_cases": map_5_details["real_zero_cases"],
                "map_5_evaluation_failures": map_5_details["evaluation_failures"],
                "mrr_5": round(mrr_5_details["score"], 4) if mrr_5_details["score"] is not None else None,
                "MRR@5": round(mrr_5_details["score"], 4) if mrr_5_details["score"] is not None else None,
                "mrr_5_valid_cases": mrr_5_details["valid_cases"],
                "mrr_5_missing_ground_truth": mrr_5_details["missing_ground_truth"],
                "mrr_5_real_zero_cases": mrr_5_details["real_zero_cases"],
                "mrr_5_evaluation_failures": mrr_5_details["evaluation_failures"],
                "Recall@5": round(avg_recall_5, 4) if avg_recall_5 is not None else None,
                "Recall@5 Valid Count": len(valid_recall_5),
                "Recall@5 Missing Ground Truth": missing_recall_5_gt,
                "Context Recall": round(avg_recall, 4),
                "Faithfulness": round(avg_faithfulness, 4),
                "Answer Relevancy": round(avg_relevancy, 4),
                "Hallucination Rate": f"{round(hallucination_rate * 100, 2)}%" if hallucination_rate is not None else "N/A",
                "Intrinsic Response Rate": f"{round(intrinsic_response_rate * 100, 2)}%" if intrinsic_response_rate is not None else "N/A",
                "Extrinsic Response Rate": f"{round(extrinsic_response_rate * 100, 2)}%" if extrinsic_response_rate is not None else "N/A",
                "Safety Recall": round(safety_stats["recall"], 4) if safety_stats["recall"] is not None else "MISSING_GROUND_TRUTH",
                "Safety Precision": round(safety_stats["precision"], 4) if safety_stats["precision"] is not None else "MISSING_GROUND_TRUTH",
                "Safety F1": round(safety_stats["f1"], 4) if safety_stats["f1"] is not None else "MISSING_GROUND_TRUTH"
                # Latency intentionally excluded from the official metric set/reporting
                # (decision: 2026-08-25, docs/latency_final_audit.md) - raw per-case
                # "latency" timing still exists in evaluator.py output for engineering use.
            })
            
        final_comparison_df = pd.DataFrame(comparison_records)
        final_report_path = os.path.join(self.reports_dir, "final_model_comparison.csv")
        final_comparison_df.to_csv(final_report_path, index=False)
        print(f"\n=== FINAL EVALUATION REPORT ===")
        print(tabulate(final_comparison_df, headers="keys", tablefmt="grid"))
        return final_comparison_df

    def run_llm_judged_relevance_experiment(self, dataset):
        """
        Retrieval-depth diagnostic. NOT an official evaluation metric.

        Sweeps K = 3, 5, 10 and asks the ContextJudge LLM to label the
        relevance of whatever chunks were actually retrieved at each K, then
        reports a rank-weighted "LLM-Judged Relevance Score@K" alongside
        LLM-judged Context Recall.

        This diagnostic is:
          - ground-truth-free: there is no gold `relevant_chunk_ids` list
            here, and it never considers chunks that were not retrieved.
          - LLM-judged: the only relevance signal is the ContextJudge's live
            binary judgment of the K retrieved chunks, not a pre-annotated
            gold set.
          - a retrieval-depth diagnostic only: intended to observe how
            apparent relevance/context-recall trend as K grows (3 -> 5 -> 10),
            nothing more.

        This is explicitly NOT Average Precision and NOT MAP in the
        Manning, Raghavan & Schutze sense (Introduction to Information
        Retrieval, Ch. 8, Sec. 8.4, Eq. 8.8). True AP/MAP requires knowing
        the total number of relevant items for a query - including ones
        never retrieved at all - which this diagnostic cannot know without a
        gold list. It calls calculate_ap_at_k() without a total_relevant_count
        (its legacy num_hits-normalized fallback) purely as a rank-weighted,
        precision-style score over the retrieved window - not as a claim of
        literature-exact AP.

        This is NOT part of the official gold-grounded retrieval metrics
        (Precision@5, Recall@5, MAP@5, MRR@5) reported in
        final_model_comparison.csv / ragas_report.csv. Do not compare its
        K=5 row against the official MAP@5 value - they measure different
        things from different data sources and will diverge once MAP@5 has
        real gold ground truth.

        Cost note: this runs unconditionally today (2 extra LLM judge calls
        x len(dataset) x 3 K-values per --evaluate invocation, independent
        of how many models are being compared). It may be gated behind an
        explicit diagnostic flag in the future to avoid this cost when the
        diagnostic isn't needed; that gating is not implemented yet.
        """
        print("\n=== Running LLM-Judged Relevance Experiment (K=3, K=5, K=10) - retrieval-depth diagnostic, NOT official MAP ===")
        results = []

        for k in [3, 5, 10]:
            print(f"[+] Evaluating RAG Retrieval with Top K = {k}...")
            k_scores = []
            k_recall = []
            for i, case in enumerate(dataset, 1):
                question = case["question"]
                expected = case.get("expected_context", [])

                retrieved = self.evaluator.retriever.retrieve(question, top_k=k)

                # Execute Layer 1 Judges
                relevance_data = self.evaluator.judges["context"].evaluate_precision(question, retrieved)
                recall_data = self.evaluator.judges["context"].evaluate_recall(retrieved, expected, question=question)

                # Execute Layer 2 Metrics (ground-truth-free: no total_relevant_count available)
                labels = [item.get("is_relevant", False) for item in relevance_data.get("relevance_map", [])]
                score = self.evaluator.metrics["retrieval"].calculate_ap_at_k(labels, k=k)
                rec = self.evaluator.metrics["grounding"].calculate_context_recall(recall_data.get("facts", []))

                k_scores.append(score)
                k_recall.append(rec)

                time.sleep(0.2)

            avg_score = sum(k_scores) / len(k_scores) if k_scores else 0.0
            avg_rec = sum(k_recall) / len(k_recall) if k_recall else 0.0

            results.append({
                "Top K": k,
                "LLM-Judged Relevance Score@K": round(avg_score, 4),
                "Context Recall": round(avg_rec, 4)
            })

        exp_df = pd.DataFrame(results)
        exp_path = os.path.join(self.reports_dir, "retrieval_experiment.csv")
        exp_df.to_csv(exp_path, index=False)
        print(tabulate(exp_df, headers="keys", tablefmt="grid"))
