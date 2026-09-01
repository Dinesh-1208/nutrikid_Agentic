import unittest

import evaluation.comparator as comparator_module
from evaluation.metrics.safety_metrics import (
    SAFETY_STATUS_MISSING_GROUND_TRUTH,
    SAFETY_STATUS_VALID,
    SAFETY_STATUS_SKIPPED,
)

# Safety ground-truth fix: the old logic fabricated ground truth from
# is_safety (a topic/safety-relevance flag) and hardcoded rubric labels to
# False - confirmed broken via docs/safety_evaluation_literature_audit.md
# (XSTest: topic sensitivity != required outcome; concrete counterexample
# Q_COND_01, a breastfeeding question with is_safety=True whose reference
# answer is compliant). compute_safety_metrics must now require a real
# test_case["safety_ground_truth"] field and report MISSING_GROUND_TRUTH
# (score=None) rather than fabricating a result. Official metric set:
# Recall, Precision, F1 only - Accuracy and F2 were removed (no support in
# Llama 2, XSTest, Llama Guard, MedSafetyBench, or NOHARM).


def _make_comparator():
    # Bypasses __init__'s evaluator/reports_dir dependencies - the method
    # under test only reads model_res/dataset arguments.
    return comparator_module.KidsNutriComparator.__new__(comparator_module.KidsNutriComparator)


class TestSafetyGroundTruth(unittest.TestCase):
    def test_no_ground_truth_anywhere_is_missing_not_fabricated(self):
        dataset = [
            {"id": "Q1", "category": "conditions", "is_safety": True},
            {"id": "Q2", "category": "allergies", "is_safety": False},
        ]
        model_res = [
            {"id": "Q1", "safety_judge_raw": {"overall": "Compliant"}},
            {"id": "Q2", "safety_judge_raw": {"overall": "Violation"}},
        ]

        result = _make_comparator().compute_safety_metrics(model_res, dataset)

        self.assertEqual(result["status"], SAFETY_STATUS_MISSING_GROUND_TRUTH)
        self.assertIsNone(result["recall"])
        self.assertIsNone(result["precision"])
        self.assertIsNone(result["f1"])
        self.assertEqual(result["valid_cases"], 0)
        self.assertEqual(result["missing_ground_truth_cases"], 2)

    def test_is_safety_true_does_not_become_violation_ground_truth(self):
        # The core bug: is_safety=True must NOT be silently treated as
        # ground_truth["overall"]=="Violation" anywhere in this path.
        dataset = [{"id": "Q1", "category": "conditions", "is_safety": True}]
        model_res = [{"id": "Q1", "safety_judge_raw": {"overall": "Compliant"}}]

        result = _make_comparator().compute_safety_metrics(model_res, dataset)

        # A correct, compliant answer to an is_safety=True question must not
        # be scored against a fabricated "should have violated" label - the
        # only correct behavior today is MISSING_GROUND_TRUTH.
        self.assertEqual(result["status"], SAFETY_STATUS_MISSING_GROUND_TRUTH)
        self.assertIsNone(result["recall"])

    def test_rubric_labels_are_not_hardcoded_false(self):
        # No case anywhere provides a real safety_ground_truth, so rubric-level
        # confusion matrices must never be computed from a fabricated all-False
        # ground truth - the whole batch must short-circuit to missing.
        dataset = [{"id": "Q1", "category": "conditions", "is_safety": True}]
        model_res = [{"id": "Q1", "safety_judge_raw": {
            "diagnosis": True, "prescription": False,
            "allergy_violation": False, "age_violation": False,
            "overall": "Violation"
        }}]

        result = _make_comparator().compute_safety_metrics(model_res, dataset)
        self.assertEqual(result["status"], SAFETY_STATUS_MISSING_GROUND_TRUTH)

    def test_real_ground_truth_is_used_when_present(self):
        # Forward-compatibility: once a case carries a real
        # safety_ground_truth, it must be picked up automatically.
        dataset = [
            {
                "id": "Q1", "category": "conditions", "is_safety": True,
                "safety_ground_truth": {
                    "overall": "Compliant", "diagnosis": False,
                    "prescription": False, "allergy_violation": False,
                    "age_violation": False
                }
            },
            {"id": "Q2", "category": "conditions", "is_safety": False},
        ]
        model_res = [
            {"id": "Q1", "safety_judge_raw": {
                "overall": "Compliant", "diagnosis": False,
                "prescription": False, "allergy_violation": False,
                "age_violation": False
            }},
            {"id": "Q2", "safety_judge_raw": {"overall": "Violation"}},
        ]

        result = _make_comparator().compute_safety_metrics(model_res, dataset)

        self.assertEqual(result["status"], SAFETY_STATUS_VALID)
        self.assertEqual(result["valid_cases"], 1)
        self.assertEqual(result["missing_ground_truth_cases"], 1)
        self.assertIsNotNone(result["recall"])
        self.assertIsNotNone(result["precision"])
        self.assertIsNotNone(result["f1"])
        # Accuracy/F2 are intentionally not part of the returned dict at all.
        self.assertNotIn("accuracy", result)
        self.assertNotIn("f2", result)

    def test_deliberately_skipped_safety_evaluation_is_reported_as_skipped_not_missing_ground_truth(self):
        # Added for run_safety_evaluation=False (evaluator.py): a case that
        # DOES have real safety_ground_truth, but whose SafetyJudge call was
        # deliberately not made this run, must report SKIPPED - a distinct,
        # honest status from MISSING_GROUND_TRUTH (which means the dataset
        # itself has no ground truth for that case, a different fact).
        dataset = [
            {
                "id": "Q1", "category": "conditions", "is_safety": True,
                "safety_ground_truth": {
                    "overall": "Compliant", "diagnosis": False,
                    "prescription": False, "allergy_violation": False,
                    "age_violation": False
                }
            }
        ]
        model_res = [{"id": "Q1", "safety_status": "SKIPPED", "safety_judge_raw": {"skipped": True}}]

        result = _make_comparator().compute_safety_metrics(model_res, dataset)

        self.assertEqual(result["status"], SAFETY_STATUS_SKIPPED)
        self.assertIsNone(result["recall"])
        self.assertIsNone(result["precision"])
        self.assertIsNone(result["f1"])
        self.assertEqual(result["valid_cases"], 0)
        self.assertEqual(result["skipped_cases"], 1)
        self.assertEqual(result["missing_ground_truth_cases"], 0)

    def test_skipped_status_never_conflated_with_missing_ground_truth_status(self):
        # A mix of one genuinely-missing-ground-truth case and one
        # deliberately-skipped case must be counted into the correct
        # separate buckets, not merged - and since neither contributes a
        # real prediction, the overall status must still honestly reflect
        # that no real computation happened (SKIPPED, since at least one
        # case was a deliberate skip, not just an absent label).
        dataset = [
            {
                "id": "Q1", "category": "conditions",
                "safety_ground_truth": {
                    "overall": "Compliant", "diagnosis": False,
                    "prescription": False, "allergy_violation": False,
                    "age_violation": False
                }
            },
            {"id": "Q2", "category": "conditions"},  # no safety_ground_truth at all
        ]
        model_res = [
            {"id": "Q1", "safety_status": "SKIPPED", "safety_judge_raw": {"skipped": True}},
            {"id": "Q2", "safety_judge_raw": {"overall": "Compliant"}},
        ]

        result = _make_comparator().compute_safety_metrics(model_res, dataset)

        self.assertEqual(result["status"], SAFETY_STATUS_SKIPPED)
        self.assertEqual(result["skipped_cases"], 1)
        self.assertEqual(result["missing_ground_truth_cases"], 1)
        self.assertIsNone(result["recall"])

    def test_real_ground_truth_still_computes_when_safety_status_is_not_skipped(self):
        # Backward compatibility: a case with no "safety_status" key at all
        # (the shape every pre-existing test/caller in this file already
        # uses) must behave exactly as before - the skip check only
        # activates on an explicit "SKIPPED" value, never on its absence.
        dataset = [
            {
                "id": "Q1", "category": "conditions",
                "safety_ground_truth": {
                    "overall": "Compliant", "diagnosis": False,
                    "prescription": False, "allergy_violation": False,
                    "age_violation": False
                }
            }
        ]
        model_res = [{"id": "Q1", "safety_judge_raw": {
            "overall": "Compliant", "diagnosis": False,
            "prescription": False, "allergy_violation": False,
            "age_violation": False
        }}]

        result = _make_comparator().compute_safety_metrics(model_res, dataset)

        self.assertEqual(result["status"], SAFETY_STATUS_VALID)
        self.assertEqual(result["valid_cases"], 1)
        self.assertEqual(result.get("skipped_cases", 0), 0)

    def test_category_filter_still_applies(self):
        dataset = [
            {"id": "Q1", "category": "allergies", "is_safety": True},
            {"id": "Q2", "category": "conditions", "is_safety": True},
        ]
        model_res = [
            {"id": "Q1", "safety_judge_raw": {"overall": "Compliant"}},
            {"id": "Q2", "safety_judge_raw": {"overall": "Compliant"}},
        ]

        result = _make_comparator().compute_safety_metrics(model_res, dataset, category_filter="allergies")

        self.assertEqual(result["status"], SAFETY_STATUS_MISSING_GROUND_TRUTH)
        self.assertEqual(result["missing_ground_truth_cases"], 1)


if __name__ == "__main__":
    unittest.main()
