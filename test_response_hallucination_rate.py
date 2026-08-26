import unittest

from evaluation.metrics.grounding_metrics import (
    RESPONSE_HALLUCINATION_STATUS_EVALUATION_FAILURE,
    RESPONSE_HALLUCINATION_STATUS_INVALID_CLAIM_DATA,
    RESPONSE_HALLUCINATION_STATUS_INVALID_TYPE_DATA,
    RESPONSE_HALLUCINATION_STATUS_NO_CLAIMS_EXTRACTED,
    RESPONSE_HALLUCINATION_STATUS_REAL_ZERO,
    RESPONSE_HALLUCINATION_STATUS_VALID,
    UNSUPPORTED_CLAIM_RATE_STATUS_REAL_ZERO,
    UNSUPPORTED_CLAIM_RATE_STATUS_VALID,
    calculate_response_hallucination_type_details,
    calculate_unsupported_claim_rate_details,
)

# Response-level Intrinsic/Extrinsic Response Rate: adapted from Maynez et
# al. (2020), ACL 2020, arXiv:2005.00661, Table 2 / Section 5.2, page 6 -
# "the percentage of summaries where at least one word was annotated... as
# an intrinsic (I) or extrinsic (E) hallucination." I and E are computed
# INDEPENDENTLY there, not as a mutually exclusive partition - a response
# can be flagged for both. KidsNutriBite substitutes LLM-judged atomic
# claims for Maynez's human-annotated spans; resulting numbers are not
# directly comparable to Maynez's published percentages. Category
# definitions are Ji et al.'s taxonomy.
#
# An unknown evaluation (failure, no claims, invalid is_supported data, or
# invalid/missing hallucination_type on an unsupported claim) must never be
# silently treated as "not hallucinated" - it reports None, to be excluded
# from both the numerator and denominator at aggregation time.


def supported(claim="s"):
    return {"claim": claim, "is_supported": True}


def unsupported(claim="u", htype="Intrinsic"):
    return {"claim": claim, "is_supported": False, "hallucination_type": htype}


class TestResponseHallucinationTypeDetails(unittest.TestCase):
    def test_all_supported_is_real_zero(self):
        claims = [supported("a"), supported("b")]
        result = calculate_response_hallucination_type_details(claims)

        self.assertEqual(result["status"], RESPONSE_HALLUCINATION_STATUS_REAL_ZERO)
        self.assertEqual(result["has_intrinsic"], False)
        self.assertEqual(result["has_extrinsic"], False)

        unsupported_rate = calculate_unsupported_claim_rate_details(claims)
        self.assertEqual(unsupported_rate["status"], UNSUPPORTED_CLAIM_RATE_STATUS_REAL_ZERO)
        self.assertEqual(unsupported_rate["score"], 0.0)

    def test_intrinsic_only_response(self):
        claims = [supported("a"), unsupported("b", "Intrinsic")]
        result = calculate_response_hallucination_type_details(claims)

        self.assertEqual(result["status"], RESPONSE_HALLUCINATION_STATUS_VALID)
        self.assertEqual(result["has_intrinsic"], True)
        self.assertEqual(result["has_extrinsic"], False)

    def test_extrinsic_only_response(self):
        claims = [supported("a"), unsupported("b", "Extrinsic")]
        result = calculate_response_hallucination_type_details(claims)

        self.assertEqual(result["status"], RESPONSE_HALLUCINATION_STATUS_VALID)
        self.assertEqual(result["has_intrinsic"], False)
        self.assertEqual(result["has_extrinsic"], True)

    def test_overlap_response_counts_in_both(self):
        # Response A: supported, unsupported+Intrinsic, unsupported+Extrinsic.
        claims = [
            supported("a"),
            unsupported("b", "Intrinsic"),
            unsupported("c", "Extrinsic"),
        ]
        result = calculate_response_hallucination_type_details(claims)
        unsupported_rate = calculate_unsupported_claim_rate_details(claims)

        self.assertEqual(result["status"], RESPONSE_HALLUCINATION_STATUS_VALID)
        self.assertEqual(result["has_intrinsic"], True)
        self.assertEqual(result["has_extrinsic"], True)
        # Hallucination Rate contribution (is_hallucinated) is derived from
        # the unsupported_claim_rate status/score, same as evaluator.py does.
        self.assertEqual(unsupported_rate["status"], UNSUPPORTED_CLAIM_RATE_STATUS_VALID)
        self.assertGreater(unsupported_rate["score"], 0)

    def test_evaluation_failure_is_not_false(self):
        result = calculate_response_hallucination_type_details([unsupported()], evaluation_failed=True)

        self.assertEqual(result["status"], RESPONSE_HALLUCINATION_STATUS_EVALUATION_FAILURE)
        self.assertIsNone(result["has_intrinsic"])
        self.assertIsNone(result["has_extrinsic"])

    def test_no_claims_extracted_is_not_false(self):
        result = calculate_response_hallucination_type_details([])

        self.assertEqual(result["status"], RESPONSE_HALLUCINATION_STATUS_NO_CLAIMS_EXTRACTED)
        self.assertIsNone(result["has_intrinsic"])
        self.assertIsNone(result["has_extrinsic"])

    def test_invalid_claim_data_is_not_false(self):
        claims = [{"claim": "a"}]  # missing is_supported entirely
        result = calculate_response_hallucination_type_details(claims)

        self.assertEqual(result["status"], RESPONSE_HALLUCINATION_STATUS_INVALID_CLAIM_DATA)
        self.assertIsNone(result["has_intrinsic"])
        self.assertIsNone(result["has_extrinsic"])

    def test_invalid_hallucination_type_is_unknown_not_excluded(self):
        # is_supported data is valid, but the unsupported claim's type is
        # missing entirely.
        claims = [supported("a"), {"claim": "b", "is_supported": False}]
        result = calculate_response_hallucination_type_details(claims)

        self.assertEqual(result["status"], RESPONSE_HALLUCINATION_STATUS_INVALID_TYPE_DATA)
        self.assertIsNone(result["has_intrinsic"])
        self.assertIsNone(result["has_extrinsic"])

        # But is_hallucinated (from the separate, unchanged unsupported-claim
        # check) is still determinable - it only needs is_supported, not
        # hallucination_type.
        unsupported_rate = calculate_unsupported_claim_rate_details(claims)
        self.assertEqual(unsupported_rate["status"], UNSUPPORTED_CLAIM_RATE_STATUS_VALID)
        self.assertGreater(unsupported_rate["score"], 0)

    def test_malformed_hallucination_type_value_is_invalid(self):
        claims = [{"claim": "b", "is_supported": False, "hallucination_type": "Something Else"}]
        result = calculate_response_hallucination_type_details(claims)

        self.assertEqual(result["status"], RESPONSE_HALLUCINATION_STATUS_INVALID_TYPE_DATA)
        self.assertIsNone(result["has_intrinsic"])
        self.assertIsNone(result["has_extrinsic"])

    def test_hallucination_type_is_case_insensitive(self):
        claims = [unsupported("b", "intrinsic")]
        result = calculate_response_hallucination_type_details(claims)

        self.assertEqual(result["status"], RESPONSE_HALLUCINATION_STATUS_VALID)
        self.assertTrue(result["has_intrinsic"])


class TestResponseLevelAggregation(unittest.TestCase):
    """
    Simulates the exact filter-then-average pattern used in
    evaluation/comparator.py to verify aggregation-level behavior without
    needing the full evaluator/comparator pipeline.
    """

    def _aggregate(self, values):
        valid = [v for v in values if v is not None]
        return sum(valid) / len(valid) if valid else None

    def test_unknown_evaluations_excluded_from_denominator(self):
        # 3 valid responses (1 hallucinated), 2 unknown (None) - the None
        # values must not reduce the reported rate.
        is_hallucinated_values = [True, False, False, None, None]
        rate = self._aggregate(is_hallucinated_values)

        self.assertAlmostEqual(rate, 1 / 3)  # not 1/5

    def test_all_unknown_yields_none_not_zero(self):
        rate = self._aggregate([None, None, None])
        self.assertIsNone(rate)

    def test_response_with_both_types_counts_in_both_rates(self):
        # Mirrors the overlap response: has_intrinsic_claim=True and
        # has_extrinsic_claim=True for the SAME response.
        has_intrinsic_values = [True, False]
        has_extrinsic_values = [True, False]

        intrinsic_rate = self._aggregate(has_intrinsic_values)
        extrinsic_rate = self._aggregate(has_extrinsic_values)
        is_hallucinated_values = [True, False]
        hallucination_rate = self._aggregate(is_hallucinated_values)

        self.assertEqual(intrinsic_rate, 0.5)
        self.assertEqual(extrinsic_rate, 0.5)
        # Hallucination Rate <= Intrinsic + Extrinsic (union, not a strict sum).
        self.assertLessEqual(hallucination_rate, intrinsic_rate + extrinsic_rate)


if __name__ == "__main__":
    unittest.main()
