import unittest

from evaluation.metrics.retrieval_metrics import (
    PRECISION_STATUS_EVALUATION_FAILURE,
    PRECISION_STATUS_INCOMPLETE_RETRIEVAL,
    PRECISION_STATUS_REAL_ZERO,
    PRECISION_STATUS_VALID,
    calculate_precision_at_k_details,
)


class TestPrecisionAtK(unittest.TestCase):
    def test_complete_precision_at_5(self):
        result = calculate_precision_at_k_details(
            [True, True, False, True, False],
            k=5
        )

        self.assertEqual(result["status"], PRECISION_STATUS_VALID)
        self.assertEqual(result["relevant_count"], 3)
        self.assertEqual(result["label_count"], 5)
        self.assertAlmostEqual(result["score"], 0.60)

    def test_complete_real_zero_precision_at_5(self):
        result = calculate_precision_at_k_details(
            [False, False, False, False, False],
            k=5
        )

        self.assertEqual(result["status"], PRECISION_STATUS_REAL_ZERO)
        self.assertEqual(result["relevant_count"], 0)
        self.assertEqual(result["label_count"], 5)
        self.assertEqual(result["score"], 0.0)

    def test_empty_labels_are_incomplete_not_zero(self):
        result = calculate_precision_at_k_details([], k=5)

        self.assertEqual(result["status"], PRECISION_STATUS_INCOMPLETE_RETRIEVAL)
        self.assertEqual(result["relevant_count"], 0)
        self.assertEqual(result["label_count"], 0)
        self.assertIsNone(result["score"])

    def test_short_labels_are_incomplete_not_partial_precision(self):
        result = calculate_precision_at_k_details([True, False], k=5)

        self.assertEqual(result["status"], PRECISION_STATUS_INCOMPLETE_RETRIEVAL)
        self.assertEqual(result["relevant_count"], 1)
        self.assertEqual(result["label_count"], 2)
        self.assertIsNone(result["score"])

    def test_evaluation_failure_is_not_zero(self):
        result = calculate_precision_at_k_details([], k=5, evaluation_failed=True)

        self.assertEqual(result["status"], PRECISION_STATUS_EVALUATION_FAILURE)
        self.assertIsNone(result["relevant_count"])
        self.assertEqual(result["label_count"], 0)
        self.assertIsNone(result["score"])


if __name__ == "__main__":
    unittest.main()
