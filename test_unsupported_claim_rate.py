import unittest

from evaluation.metrics.grounding_metrics import (
    FAITHFULNESS_STATUS_EVALUATION_FAILURE,
    FAITHFULNESS_STATUS_INVALID_CLAIM_DATA,
    FAITHFULNESS_STATUS_NO_CLAIMS_EXTRACTED,
    FAITHFULNESS_STATUS_REAL_ZERO,
    FAITHFULNESS_STATUS_VALID,
    UNSUPPORTED_CLAIM_RATE_STATUS_EVALUATION_FAILURE,
    UNSUPPORTED_CLAIM_RATE_STATUS_INVALID_CLAIM_DATA,
    UNSUPPORTED_CLAIM_RATE_STATUS_NO_CLAIMS_EXTRACTED,
    UNSUPPORTED_CLAIM_RATE_STATUS_REAL_ZERO,
    UNSUPPORTED_CLAIM_RATE_STATUS_VALID,
    calculate_faithfulness_details,
    calculate_unsupported_claim_rate,
    calculate_unsupported_claim_rate_details,
)

# Unsupported Claim Rate (renamed from "Overall Hallucination Rate"):
# unsupported_claims / total_extracted_claims. Project-operational; ratio
# structure informed by the supported-claim precision pattern in FActScore
# (Min et al., 2023, EMNLP, arXiv:2305.14251, Sec 3.1 p.3) and SAFE (Wei et
# al., 2024, NeurIPS, arXiv:2403.18802, Sec 5 p.6 Eq.1) - neither paper
# names a metric "Unsupported Claim Rate" or "Hallucination Rate". Ji et al.
# taxonomy is NOT the source of this formula (used only by the sibling
# Intrinsic/Extrinsic Hallucination Rate functions).
#
# Faithfulness and Unsupported Claim Rate must be exact complements
# (sum to 1.0) on the same claims_list whenever both are VALID/REAL_ZERO,
# and must never silently disagree on malformed or missing data.


class TestUnsupportedClaimRate(unittest.TestCase):
    def test_mixed_support_matches_faithfulness_complement(self):
        claims = [
            {"claim_id": "C001", "claim": "a", "is_supported": True},
            {"claim_id": "C002", "claim": "b", "is_supported": True},
            {"claim_id": "C003", "claim": "c", "is_supported": False},
        ]
        faithfulness = calculate_faithfulness_details(claims)
        unsupported_rate = calculate_unsupported_claim_rate_details(claims)

        self.assertEqual(faithfulness["status"], FAITHFULNESS_STATUS_VALID)
        self.assertAlmostEqual(faithfulness["score"], 2 / 3)

        self.assertEqual(unsupported_rate["status"], UNSUPPORTED_CLAIM_RATE_STATUS_VALID)
        self.assertAlmostEqual(unsupported_rate["score"], 1 / 3)
        self.assertEqual(unsupported_rate["unsupported_count"], 1)
        self.assertEqual(unsupported_rate["total_count"], 3)
        self.assertAlmostEqual(calculate_unsupported_claim_rate(claims), 1 / 3)

        self.assertAlmostEqual(faithfulness["score"] + unsupported_rate["score"], 1.0)

    def test_all_supported(self):
        claims = [
            {"claim_id": "C001", "claim": "a", "is_supported": True},
            {"claim_id": "C002", "claim": "b", "is_supported": True},
        ]
        faithfulness = calculate_faithfulness_details(claims)
        unsupported_rate = calculate_unsupported_claim_rate_details(claims)

        self.assertEqual(faithfulness["score"], 1.0)
        self.assertEqual(faithfulness["status"], FAITHFULNESS_STATUS_VALID)

        self.assertEqual(unsupported_rate["score"], 0.0)
        self.assertEqual(unsupported_rate["status"], UNSUPPORTED_CLAIM_RATE_STATUS_REAL_ZERO)
        self.assertEqual(faithfulness["score"] + unsupported_rate["score"], 1.0)

    def test_all_unsupported(self):
        claims = [
            {"claim_id": "C001", "claim": "a", "is_supported": False},
            {"claim_id": "C002", "claim": "b", "is_supported": False},
        ]
        faithfulness = calculate_faithfulness_details(claims)
        unsupported_rate = calculate_unsupported_claim_rate_details(claims)

        self.assertEqual(faithfulness["score"], 0.0)
        self.assertEqual(faithfulness["status"], FAITHFULNESS_STATUS_REAL_ZERO)

        self.assertEqual(unsupported_rate["score"], 1.0)
        self.assertEqual(unsupported_rate["status"], UNSUPPORTED_CLAIM_RATE_STATUS_VALID)
        self.assertEqual(faithfulness["score"] + unsupported_rate["score"], 1.0)

    def test_missing_is_supported_field_does_not_silently_disagree(self):
        # Before the fix: Faithfulness defaulted a missing field to
        # "unsupported" while Overall Hallucination Rate defaulted the same
        # field to "supported" - so the two could silently contradict each
        # other on malformed data. Both must now report the SAME
        # INVALID_CLAIM_DATA status and score=None instead.
        claims = [
            {"claim_id": "C001", "claim": "a", "is_supported": True},
            {"claim_id": "C002", "claim": "b"},
        ]
        faithfulness = calculate_faithfulness_details(claims)
        unsupported_rate = calculate_unsupported_claim_rate_details(claims)

        self.assertEqual(faithfulness["status"], FAITHFULNESS_STATUS_INVALID_CLAIM_DATA)
        self.assertEqual(unsupported_rate["status"], UNSUPPORTED_CLAIM_RATE_STATUS_INVALID_CLAIM_DATA)
        self.assertIsNone(faithfulness["score"])
        self.assertIsNone(unsupported_rate["score"])

    def test_evaluation_failure_is_not_fake_zero_for_either_metric(self):
        claims = [{"claim_id": "C001", "claim": "a", "is_supported": True}]
        faithfulness = calculate_faithfulness_details(claims, evaluation_failed=True)
        unsupported_rate = calculate_unsupported_claim_rate_details(claims, evaluation_failed=True)

        self.assertEqual(faithfulness["status"], FAITHFULNESS_STATUS_EVALUATION_FAILURE)
        self.assertEqual(unsupported_rate["status"], UNSUPPORTED_CLAIM_RATE_STATUS_EVALUATION_FAILURE)
        self.assertIsNone(faithfulness["score"])
        self.assertIsNone(unsupported_rate["score"])

    def test_no_claims_handled_consistently(self):
        faithfulness = calculate_faithfulness_details([])
        unsupported_rate = calculate_unsupported_claim_rate_details([])

        self.assertEqual(faithfulness["status"], FAITHFULNESS_STATUS_NO_CLAIMS_EXTRACTED)
        self.assertEqual(unsupported_rate["status"], UNSUPPORTED_CLAIM_RATE_STATUS_NO_CLAIMS_EXTRACTED)
        self.assertIsNone(faithfulness["score"])
        self.assertIsNone(unsupported_rate["score"])

    def test_none_claims_list_handled_consistently(self):
        faithfulness = calculate_faithfulness_details(None)
        unsupported_rate = calculate_unsupported_claim_rate_details(None)

        self.assertEqual(faithfulness["status"], FAITHFULNESS_STATUS_NO_CLAIMS_EXTRACTED)
        self.assertEqual(unsupported_rate["status"], UNSUPPORTED_CLAIM_RATE_STATUS_NO_CLAIMS_EXTRACTED)


if __name__ == "__main__":
    unittest.main()
