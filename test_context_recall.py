import unittest
from unittest.mock import MagicMock

from evaluation.metrics.grounding_metrics import (
    CONTEXT_RECALL_STATUS_VALID,
    CONTEXT_RECALL_STATUS_REAL_ZERO,
    CONTEXT_RECALL_STATUS_MISSING_GROUND_TRUTH,
    CONTEXT_RECALL_STATUS_EVALUATION_FAILURE,
    calculate_context_recall,
    calculate_context_recall_details,
)

# ============================================================================
# Phase 4E root-cause fix (docs/phase4e_context_recall_fix.md).
#
# Root cause: calculate_context_recall's only branch was
# `if not facts_list: return 0.0`. An empty facts_list meant three
# structurally different things - a judge that genuinely found zero supported
# facts, a judge/API/parser failure that never produced any facts, and a case
# with no RAG ground truth to check recall against in the first place - and
# all three silently produced the identical 0.0, contaminating the aggregate
# with non-results disguised as real ones.
#
# These tests prove, at both the pure-math layer (Part 1) and the real
# evaluator-integration layer (Part 2, mocked judges/retriever/planner/LLM -
# no live API calls), that the four cases the fix distinguishes are now
# actually distinguished, and specifically that none of the three known
# failure/inapplicability code paths can produce a fake 0.0 anymore.
# ============================================================================


class TestCalculateContextRecallDetailsPureMath(unittest.TestCase):
    """Direct unit tests on the metric function - no evaluator involved."""

    def test_real_zero_judge_succeeded_none_supported(self):
        # CASE A (task spec): judge successfully evaluates, finds zero
        # supported gold facts. Expected: a VALID, real 0.0 - not a failure.
        facts = [{"fact": "x", "is_present": False}, {"fact": "y", "is_present": False}]
        result = calculate_context_recall_details(facts)
        self.assertEqual(result["score"], 0.0)
        self.assertEqual(result["status"], CONTEXT_RECALL_STATUS_REAL_ZERO)
        self.assertEqual(result["supported_count"], 0)
        self.assertEqual(result["total_count"], 2)

    def test_evaluation_failure_is_never_a_fake_zero(self):
        # CASE B: judge call failed. Expected: EVALUATION_FAILURE, score=None
        # - explicitly NOT 0.0, even though the caller might pass an empty
        # facts_list (mirroring what a parse_failed dict's .get("facts")
        # would yield).
        result = calculate_context_recall_details([], evaluation_failed=True)
        self.assertIsNone(result["score"])
        self.assertEqual(result["status"], CONTEXT_RECALL_STATUS_EVALUATION_FAILURE)
        self.assertNotEqual(result["score"], 0.0)

    def test_evaluation_failure_takes_priority_over_nonempty_facts(self):
        # Even if a non-empty facts_list somehow accompanies
        # evaluation_failed=True, failure must win - never silently compute a
        # score from possibly-partial data during a failure.
        facts = [{"fact": "x", "is_present": True}]
        result = calculate_context_recall_details(facts, evaluation_failed=True)
        self.assertIsNone(result["score"])
        self.assertEqual(result["status"], CONTEXT_RECALL_STATUS_EVALUATION_FAILURE)

    def test_missing_ground_truth_when_not_applicable(self):
        # CASE C (task spec): case lacks required RAG context ground truth
        # (non-RAG-applicable case). Expected: missing-ground-truth behavior,
        # not a fabricated 0.0.
        result = calculate_context_recall_details(None, ground_truth_available=False)
        self.assertIsNone(result["score"])
        self.assertEqual(result["status"], CONTEXT_RECALL_STATUS_MISSING_GROUND_TRUTH)
        self.assertNotEqual(result["score"], 0.0)

    def test_missing_ground_truth_when_no_facts_expected(self):
        # A separate route to the same status: ground truth IS applicable but
        # genuinely zero facts were expected/extracted (not currently
        # exercised by any of the 49 finalized cases - every case has >=1
        # gold fact - but preserved as a safe default).
        result = calculate_context_recall_details([])
        self.assertIsNone(result["score"])
        self.assertEqual(result["status"], CONTEXT_RECALL_STATUS_MISSING_GROUND_TRUTH)

    def test_partial_recall(self):
        # CASE D (task spec): some gold facts supported, some not. Expected:
        # a partial score.
        facts = [
            {"fact": "a", "is_present": True},
            {"fact": "b", "is_present": False},
            {"fact": "c", "is_present": True},
        ]
        result = calculate_context_recall_details(facts)
        self.assertAlmostEqual(result["score"], 2 / 3)
        self.assertEqual(result["status"], CONTEXT_RECALL_STATUS_VALID)
        self.assertEqual(result["supported_count"], 2)
        self.assertEqual(result["total_count"], 3)

    def test_full_recall(self):
        facts = [{"fact": "a", "is_present": True}, {"fact": "b", "is_present": True}]
        result = calculate_context_recall_details(facts)
        self.assertEqual(result["score"], 1.0)
        self.assertEqual(result["status"], CONTEXT_RECALL_STATUS_VALID)

    def test_multi_fact_case_all_four_combinations_distinguishable(self):
        # 0/N, 1/N, N/N must all be numerically and semantically distinct -
        # an empty list must never silently mean the same thing as "0/N
        # succeeded".
        zero_of_three = calculate_context_recall_details(
            [{"is_present": False}] * 3
        )
        one_of_three = calculate_context_recall_details(
            [{"is_present": True}] + [{"is_present": False}] * 2
        )
        three_of_three = calculate_context_recall_details(
            [{"is_present": True}] * 3
        )
        failed = calculate_context_recall_details([], evaluation_failed=True)

        scores = [zero_of_three["score"], one_of_three["score"], three_of_three["score"], failed["score"]]
        self.assertEqual(scores, [0.0, 1 / 3, 1.0, None])
        # The REAL_ZERO case and the EVALUATION_FAILURE case must never share
        # a status, even though both can arise from "no facts marked present".
        self.assertNotEqual(zero_of_three["status"], failed["status"])

    def test_backward_compatible_wrapper_returns_score_only(self):
        self.assertEqual(calculate_context_recall([{"is_present": True}]), 1.0)
        self.assertIsNone(calculate_context_recall([], ))  # no facts -> MISSING_GROUND_TRUTH -> None, not 0.0


def _make_mock_client_retriever_planner():
    mock_llm = MagicMock()
    mock_llm.generate_response.return_value = ("a generated answer", 0.1)
    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = [{"id": "X_P0_C0", "source_id": "X", "text": "some retrieved text", "score": 0.5}]
    mock_planner = MagicMock()
    mock_planner.generate_meal_plan.return_value = {
        "profile": {"age": 5, "weight_kg": 18, "goal": "g", "condition": "c", "allergies": []},
        "targets": {"calories_kcal": 1200},
        "totals": {"calories_kcal": 1200, "protein_g": 1, "fat_g": 1, "carbs_g": 1, "iron_mg": 1},
        "meal_plan": {},
    }
    return mock_llm, mock_retriever, mock_planner


def _make_mock_judges(precision_map=None, recall_facts=None, recall_side_effect=None):
    judges = {
        "context": MagicMock(),
        "grounding": MagicMock(),
        "relevancy": MagicMock(),
        "safety": MagicMock(),
    }
    judges["context"].evaluate_precision.return_value = {"relevance_map": precision_map or []}
    if recall_side_effect is not None:
        judges["context"].evaluate_recall.side_effect = recall_side_effect
    else:
        judges["context"].evaluate_recall.return_value = {"facts": recall_facts if recall_facts is not None else []}
    judges["grounding"].evaluate_grounding.return_value = {"claims": []}
    judges["relevancy"].generate_hypothetical_questions.return_value = {"generated_questions": []}
    judges["safety"].evaluate_safety.return_value = {
        "overall": "Compliant", "diagnosis": False, "prescription": False,
        "allergy_violation": False, "age_violation": False,
    }
    return judges


class TestContextRecallEvaluatorIntegration(unittest.TestCase):
    """
    Integration-level tests through the real KidsNutriEvaluator.run_single_evaluation,
    with only the LLM client / retriever / planner / judges mocked (no live API
    calls, no live retrieval) - proves the fix end-to-end through the actual
    orchestration code, not just the isolated math function.
    """

    def _run(self, test_case, judges):
        from evaluation.evaluator import KidsNutriEvaluator
        mock_llm, mock_retriever, mock_planner = _make_mock_client_retriever_planner()
        evaluator = KidsNutriEvaluator(mock_llm, mock_retriever, mock_planner, judges=judges)
        result = evaluator.run_single_evaluation(test_case, "qwen_local")
        return result, judges

    def _rag_case(self, gold_facts):
        return {
            "id": "T1", "category": "conditions", "question": "q?",
            "profile": {"age": 5, "allergies": []},
            "relevant_chunk_ids": ["X"],
            "gold_facts": [{"fact_id": f"GF_{i}", "fact_text": t} for i, t in enumerate(gold_facts)],
        }

    def _non_rag_case(self, gold_facts):
        return {
            "id": "T2", "category": "allergies", "question": "q?",
            "profile": {"age": 5, "allergies": []},
            "relevant_chunk_ids": None,
            "gold_facts": [{"fact_id": f"GF_{i}", "fact_text": t} for i, t in enumerate(gold_facts)],
        }

    def test_case_a_successful_zero_is_real_zero_not_failure(self):
        judges = _make_mock_judges(recall_facts=[{"fact": "f1", "is_present": False}])
        result, _ = self._run(self._rag_case(["f1"]), judges)
        self.assertEqual(result["context_recall"], 0.0)
        self.assertEqual(result["context_recall_status"], "REAL_ZERO")

    def test_case_b_judge_failure_never_becomes_zero(self):
        judges = _make_mock_judges(recall_facts=None)
        judges["context"].evaluate_recall.return_value = {"parse_failed": True, "error": "simulated"}
        result, _ = self._run(self._rag_case(["f1"]), judges)
        self.assertIsNone(result["context_recall"])
        self.assertEqual(result["context_recall_status"], "EVALUATION_FAILURE")
        self.assertNotEqual(result["context_recall"], 0.0)

    def test_case_c_missing_ground_truth_for_non_rag_case(self):
        judges = _make_mock_judges()
        result, judges = self._run(self._non_rag_case(["f1"]), judges)
        self.assertIsNone(result["context_recall"])
        self.assertEqual(result["context_recall_status"], "MISSING_GROUND_TRUTH")
        # The judge must never even be asked to check gold facts against RAG
        # context it was never meant to be found in.
        judges["context"].evaluate_recall.assert_not_called()

    def test_case_d_partial_recall(self):
        judges = _make_mock_judges(recall_facts=[
            {"fact": "f1", "is_present": True},
            {"fact": "f2", "is_present": False},
        ])
        result, _ = self._run(self._rag_case(["f1", "f2"]), judges)
        self.assertEqual(result["context_recall"], 0.5)
        self.assertEqual(result["context_recall_status"], "VALID")

    def test_multi_fact_case_full_recall(self):
        judges = _make_mock_judges(recall_facts=[
            {"fact": "f1", "is_present": True},
            {"fact": "f2", "is_present": True},
            {"fact": "f3", "is_present": True},
        ])
        result, _ = self._run(self._rag_case(["f1", "f2", "f3"]), judges)
        self.assertEqual(result["context_recall"], 1.0)
        self.assertEqual(result["context_recall_status"], "VALID")
        self.assertEqual(result["context_recall_supported_count"], 3)
        self.assertEqual(result["context_recall_total_count"], 3)

    def test_whole_layer_1_crash_is_evaluation_failure_not_zero(self):
        # Forces the OUTER except block (a different judge entirely raises)
        # to prove the whole-Layer-1-crash fallback no longer silently
        # produces a real zero via an un-flagged empty facts list.
        judges = _make_mock_judges(recall_facts=[{"fact": "f1", "is_present": True}])
        judges["grounding"].evaluate_grounding.side_effect = RuntimeError("simulated crash")
        result, _ = self._run(self._rag_case(["f1"]), judges)
        self.assertIsNone(result["context_recall"])
        self.assertEqual(result["context_recall_status"], "EVALUATION_FAILURE")
        self.assertNotEqual(result["context_recall"], 0.0)

    def test_no_case_lets_an_empty_list_mean_two_different_things(self):
        # A judge that legitimately succeeds with zero supported facts and a
        # judge that fails outright must be distinguishable even though both
        # can result in an "empty-ish" facts representation somewhere in the
        # pipeline.
        real_zero_judges = _make_mock_judges(recall_facts=[{"fact": "f1", "is_present": False}])
        real_zero_result, _ = self._run(self._rag_case(["f1"]), real_zero_judges)

        failure_judges = _make_mock_judges()
        failure_judges["context"].evaluate_recall.return_value = {"parse_failed": True, "error": "x"}
        failure_result, _ = self._run(self._rag_case(["f1"]), failure_judges)

        self.assertEqual(real_zero_result["context_recall"], 0.0)
        self.assertEqual(real_zero_result["context_recall_status"], "REAL_ZERO")
        self.assertIsNone(failure_result["context_recall"])
        self.assertEqual(failure_result["context_recall_status"], "EVALUATION_FAILURE")
        self.assertNotEqual(real_zero_result["context_recall_status"], failure_result["context_recall_status"])


class TestContextRecallLeakageBoundary(unittest.TestCase):
    """
    Section 8: the ContextJudge may receive gold_facts' plain fact_text (by
    design, since Context Recall is a reference-vs-context evaluation) but
    must never receive reference_answer, relevant_chunk_ids, safety_ground_truth,
    or the raw gold_facts dict shape - and the applicability gate introduced
    by this fix must not create a new leakage path.
    """

    def test_evaluate_recall_receives_only_plain_fact_text_strings(self):
        from evaluation.evaluator import KidsNutriEvaluator
        mock_llm, mock_retriever, mock_planner = _make_mock_client_retriever_planner()
        judges = _make_mock_judges(recall_facts=[{"fact": "f1", "is_present": True}])
        test_case = {
            "id": "T3", "category": "conditions", "question": "q?",
            "profile": {"age": 5, "allergies": []},
            "relevant_chunk_ids": ["X"],
            "gold_facts": [{
                "fact_id": "GF_1",
                "fact_text": "LEAKAGE_BOUNDARY_MARKER",
                "source_reference": {"source_org": "should never reach the judge"},
            }],
            "reference_answer": "REFERENCE_ANSWER_SHOULD_NEVER_LEAK",
            "safety_ground_truth": {"overall": "Compliant", "diagnosis": False, "prescription": False, "allergy_violation": False, "age_violation": False},
        }
        evaluator = KidsNutriEvaluator(mock_llm, mock_retriever, mock_planner, judges=judges)
        evaluator.run_single_evaluation(test_case, "qwen_local")

        call_args = judges["context"].evaluate_recall.call_args
        passed_expected_contexts = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs.get("expected_contexts")
        self.assertEqual(passed_expected_contexts, ["LEAKAGE_BOUNDARY_MARKER"])
        for item in passed_expected_contexts:
            self.assertIsInstance(item, str)
        call_str = str(call_args)
        self.assertNotIn("REFERENCE_ANSWER_SHOULD_NEVER_LEAK", call_str)
        self.assertNotIn("fact_id", call_str)
        self.assertNotIn("source_reference", call_str)

    def test_non_rag_case_skips_the_call_entirely_no_leakage_possible(self):
        from evaluation.evaluator import KidsNutriEvaluator
        mock_llm, mock_retriever, mock_planner = _make_mock_client_retriever_planner()
        judges = _make_mock_judges()
        test_case = {
            "id": "T4", "category": "allergies", "question": "q?",
            "profile": {"age": 5, "allergies": []},
            "relevant_chunk_ids": None,
            "gold_facts": [{"fact_id": "GF_1", "fact_text": "should never be sent anywhere for this case"}],
        }
        evaluator = KidsNutriEvaluator(mock_llm, mock_retriever, mock_planner, judges=judges)
        evaluator.run_single_evaluation(test_case, "qwen_local")
        judges["context"].evaluate_recall.assert_not_called()


if __name__ == "__main__":
    unittest.main()
