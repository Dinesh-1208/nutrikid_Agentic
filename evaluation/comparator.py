import os
import json
import time
import re
import pandas as pd
from tabulate import tabulate
from evaluation.dataset import EVALUATION_DATA
from evaluation.evaluator import KidsNutriEvaluator
from evaluation.metrics.safety_metrics import evaluate_safety_batch

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
        Uses the deterministic Layer 2 safety metrics batch processor.
        Extracts predictions from the model results and maps ground truths from the dataset.
        """
        preds = []
        gts = []
        
        for case in model_res:
            tc = next(t for t in dataset if t["id"] == case["id"])
            if category_filter and tc["category"] != category_filter:
                continue
                
            pred_raw = case.get("safety_judge_raw", {})
            preds.append(pred_raw)
            
            # Reconstruct ground truth from legacy dataset format
            is_safety_query = tc.get("is_safety", False)
            gts.append({
                "overall": "Violation" if is_safety_query else "Compliant",
                # The legacy dataset doesn't have granular GTs, so we assume False for rubrics
                "diagnosis": False,
                "prescription": False,
                "allergy_violation": False,
                "age_violation": False
            })
            
        return evaluate_safety_batch(preds, gts)

    def run_comparison(self, models=["gemini", "qwen_local"], sample_limit=None):
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
                    "Context Precision": record["context_precision"], # AP@5 is used for single
                    "MAP@5": record["ap_5"],
                    "MRR@5": record["mrr_5"],
                    "Context Recall": record["context_recall"],
                    "Faithfulness": record["faithfulness"],
                    "Answer Relevancy": record["answer_relevancy"]
                })
        ragas_df = pd.DataFrame(ragas_records)
        ragas_report_path = os.path.join(self.reports_dir, "ragas_report.csv")
        ragas_df.to_csv(ragas_report_path, index=False)

        # ================= HALLUCINATION ANALYSIS =================
        with open(os.path.join(self.reports_dir, "hallucination_analysis.md"), "w", encoding="utf-8") as f:
            f.write("# KidsNutriBite Hallucination Analysis\n\n")
            for model, model_res in results.items():
                hallucinated_cases = [r for r in model_res if r["is_hallucinated"]]
                rate = len(hallucinated_cases) / len(model_res) if model_res else 0.0
                
                intrinsic_rate = sum(r["intrinsic_hr"] for r in model_res) / len(model_res) if model_res else 0.0
                extrinsic_rate = sum(r["extrinsic_hr"] for r in model_res) / len(model_res) if model_res else 0.0
                
                f.write(f"## Model: {model.upper()}\n")
                f.write(f"- **Overall Hallucination Rate:** {rate*100:.2f}%\n")
                f.write(f"- **Intrinsic Hallucination Rate:** {intrinsic_rate*100:.2f}%\n")
                f.write(f"- **Extrinsic Hallucination Rate:** {extrinsic_rate*100:.2f}%\n\n")
                
                if hallucinated_cases:
                    f.write("| Question | Model Response | Intrinsic HR | Extrinsic HR | Claims |\n")
                    f.write("| --- | --- | --- | --- | --- |\n")
                    for case in hallucinated_cases:
                        claims_str = "<br>".join([f"• {c['claim']} (Supported: {c['is_supported']})" for c in case.get("claims", [])])
                        f.write(f"| {case['question']} | {case['response']} | {case['intrinsic_hr']:.2f} | {case['extrinsic_hr']:.2f} | {claims_str} |\n")
                else:
                    f.write("No hallucinated examples found.\n")
                f.write("\n---\n\n")

        # ================= SAFETY ANALYSIS =================
        with open(os.path.join(self.reports_dir, "safety_analysis.md"), "w", encoding="utf-8") as f:
            f.write("# KidsNutriBite Deterministic Safety Analysis Report\n\n")
            for model, model_res in results.items():
                overall_safety = self.compute_safety_metrics(model_res, dataset)
                allergy_safety = self.compute_safety_metrics(model_res, dataset, category_filter="allergies")
                
                f.write(f"## Model: {model.upper()}\n\n")
                f.write("### Overall System Safety\n")
                f.write("| Metric | Value |\n")
                f.write("| --- | --- |\n")
                for k, v in overall_safety["overall"].items():
                    f.write(f"| {k} | {v} |\n")
                f.write("\n")
                
                f.write("### Allergy-Specific Queries Safety\n")
                f.write("| Metric | Value |\n")
                f.write("| --- | --- |\n")
                for k, v in allergy_safety["overall"].items():
                    f.write(f"| {k} | {v} |\n")
                f.write("\n---\n\n")

        # ================= RETRIEVAL DIAGNOSTICS =================
        self.run_retrieval_experiments(dataset)

        # ================= FINAL REPORT =================
        comparison_records = []
        for model in results.keys():
            model_res = results[model]
            df = pd.DataFrame(model_res)
            
            avg_map = df["ap_5"].mean()
            avg_mrr = df["mrr_5"].mean()
            avg_recall = df["context_recall"].mean()
            avg_faithfulness = df["faithfulness"].mean()
            avg_relevancy = df["answer_relevancy"].mean()
            
            hallucinated_count = df["is_hallucinated"].sum()
            hallucination_rate = hallucinated_count / len(df) if len(df) > 0 else 0.0
            
            safety_stats = self.compute_safety_metrics(model_res, dataset)["overall"]
            avg_latency = df["latency"].mean()
            
            comparison_records.append({
                "Model": model.upper(),
                "MAP@5": round(avg_map, 4),
                "MRR@5": round(avg_mrr, 4),
                "Context Recall": round(avg_recall, 4),
                "Faithfulness": round(avg_faithfulness, 4),
                "Answer Relevancy": round(avg_relevancy, 4),
                "Hallucination Rate": f"{round(hallucination_rate * 100, 2)}%",
                "Safety F2": round(safety_stats["f2"], 4),
                "Safety F1": round(safety_stats["f1"], 4),
                "Average Latency": round(avg_latency, 2)
            })
            
        final_comparison_df = pd.DataFrame(comparison_records)
        final_report_path = os.path.join(self.reports_dir, "final_model_comparison.csv")
        final_comparison_df.to_csv(final_report_path, index=False)
        print(f"\n=== FINAL EVALUATION REPORT ===")
        print(tabulate(final_comparison_df, headers="keys", tablefmt="grid"))
        return final_comparison_df

    def run_retrieval_experiments(self, dataset):
        print("\n=== Running Retrieval Experiments (K=3, K=5, K=10) ===")
        results = []
        
        for k in [3, 5, 10]:
            print(f"[+] Evaluating RAG Retrieval with Top K = {k}...")
            k_ap = []
            k_recall = []
            for i, case in enumerate(dataset, 1):
                question = case["question"]
                expected = case.get("expected_context", [])
                
                retrieved = self.evaluator.retriever.retrieve(question, top_k=k)
                
                # Execute Layer 1 Judges
                relevance_data = self.evaluator.judges["context"].evaluate_precision(question, retrieved)
                recall_data = self.evaluator.judges["context"].evaluate_recall(retrieved, expected, question=question)
                
                # Execute Layer 2 Metrics
                labels = [item.get("is_relevant", False) for item in relevance_data.get("relevance_map", [])]
                ap = self.evaluator.metrics["retrieval"].calculate_ap_at_k(labels, k=k)
                rec = self.evaluator.metrics["grounding"].calculate_context_recall(recall_data.get("facts", []))
                
                k_ap.append(ap)
                k_recall.append(rec)
                
                time.sleep(0.2)
                
            avg_map = sum(k_ap) / len(k_ap) if k_ap else 0.0
            avg_rec = sum(k_recall) / len(k_recall) if k_recall else 0.0
            
            results.append({
                "Top K": k,
                "MAP@K": round(avg_map, 4),
                "Context Recall": round(avg_rec, 4)
            })
            
        exp_df = pd.DataFrame(results)
        exp_path = os.path.join(self.reports_dir, "retrieval_experiment.csv")
        exp_df.to_csv(exp_path, index=False)
        print(tabulate(exp_df, headers="keys", tablefmt="grid"))
