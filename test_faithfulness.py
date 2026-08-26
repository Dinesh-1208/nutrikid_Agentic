import unittest

from evaluation.metrics.grounding_metrics import (
    FAITHFULNESS_STATUS_EVALUATION_FAILURE,
    FAITHFULNESS_STATUS_INVALID_CLAIM_DATA,
    FAITHFULNESS_STATUS_NO_CLAIMS_EXTRACTED,
    FAITHFULNESS_STATUS_REAL_ZERO,
    FAITHFULNESS_STATUS_VALID,
    calculate_faithfulness,
    calculate_faithfulness_details,
)

# Faithfulness: F = |V| / |S| (supported claims / total extracted claims).
# Per Es et al. (2023) "RAGAS: Automated Evaluation of Retrieval Augmented
# Generation" (arXiv:2309.15217), Section 3, page 3.
#
# An empty claims_list must never be silently scored as 0.0: it is either
# NO_CLAIMS_EXTRACTED (evaluation succeeded, answer had no factual claims)
# or EVALUATION_FAILURE (judge/API/parser failure produced no claims) - both
# distinct from REAL_ZERO (claims existed, but none were supported).


class TestFaithfulness(unittest.TestCase):
    def test_valid_mixed_support(self):
        claims = [
            {"claim_id": "C001", "claim": "supported one", "is_supported": True},
            {"claim_id": "C002", "claim": "supported two", "is_supported": True},
            {"claim_id": "C003", "claim": "unsupported one", "is_supported": False},
        ]
        result = calculate_faithfulness_details(claims)

        self.assertEqual(result["status"], FAITHFULNESS_STATUS_VALID)
        self.assertAlmostEqual(result["score"], 2 / 3)
        self.assertEqual(result["supported_count"], 2)
        self.assertEqual(result["total_count"], 3)
        self.assertAlmostEqual(calculate_faithfulness(claims), 2 / 3)

    def test_real_zero_all_unsupported(self):
        claims = [
            {"claim_id": "C001", "claim": "a", "is_supported": False},
            {"claim_id": "C002", "claim": "b", "is_supported": False},
            {"claim_id": "C003", "claim": "c", "is_supported": False},
        ]
        result = calculate_faithfulness_details(claims)

        self.assertEqual(result["status"], FAITHFULNESS_STATUS_REAL_ZERO)
        self.assertEqual(result["score"], 0.0)
        self.assertEqual(result["supported_count"], 0)
        self.assertEqual(result["total_count"], 3)
        self.assertEqual(calculate_faithfulness(claims), 0.0)

    def test_no_claims_extracted_is_not_zero(self):
        result = calculate_faithfulness_details([], evaluation_failed=False)

        self.assertEqual(result["status"], FAITHFULNESS_STATUS_NO_CLAIMS_EXTRACTED)
        self.assertIsNone(result["score"])
        self.assertEqual(result["supported_count"], 0)
        self.assertEqual(result["total_count"], 0)
        self.assertIsNone(calculate_faithfulness([]))

    def test_none_claims_list_is_no_claims_extracted(self):
        result = calculate_faithfulness_details(None, evaluation_failed=False)

        self.assertEqual(result["status"], FAITHFULNESS_STATUS_NO_CLAIMS_EXTRACTED)
        self.assertIsNone(result["score"])

    def test_evaluation_failure_is_not_zero(self):
        result = calculate_faithfulness_details([], evaluation_failed=True)

        self.assertEqual(result["status"], FAITHFULNESS_STATUS_EVALUATION_FAILURE)
        self.assertIsNone(result["score"])
        self.assertIsNone(result["supported_count"])
        self.assertEqual(result["total_count"], 0)

    def test_evaluation_failure_takes_priority_over_extracted_claims(self):
        # Even if claims were partially extracted before the judge/parser
        # failed, evaluation_failed=True must still yield EVALUATION_FAILURE,
        # not a score computed from a possibly-incomplete claims list.
        claims = [{"claim_id": "C001", "claim": "a", "is_supported": True}]
        result = calculate_faithfulness_details(claims, evaluation_failed=True)

        self.assertEqual(result["status"], FAITHFULNESS_STATUS_EVALUATION_FAILURE)
        self.assertIsNone(result["score"])

    def test_missing_is_supported_field_is_invalid_not_silently_true_or_false(self):
        claims = [
            {"claim_id": "C001", "claim": "a", "is_supported": True},
            {"claim_id": "C002", "claim": "b"},
        ]
        result = calculate_faithfulness_details(claims)

        self.assertEqual(result["status"], FAITHFULNESS_STATUS_INVALID_CLAIM_DATA)
        self.assertIsNone(result["score"])
        self.assertIsNone(result["supported_count"])
        self.assertEqual(result["total_count"], 2)
        self.assertIsNone(calculate_faithfulness(claims))

    def test_non_bool_is_supported_field_is_invalid(self):
        claims = [{"claim_id": "C001", "claim": "a", "is_supported": "yes"}]
        result = calculate_faithfulness_details(claims)

        self.assertEqual(result["status"], FAITHFULNESS_STATUS_INVALID_CLAIM_DATA)
        self.assertIsNone(result["score"])


if __name__ == "__main__":
    unittest.main()
