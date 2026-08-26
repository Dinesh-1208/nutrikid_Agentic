import unittest

from evaluation.metrics.retrieval_metrics import (
    RECALL_STATUS_INCOMPLETE_RETRIEVAL,
    RECALL_STATUS_MISSING_GROUND_TRUTH,
    RECALL_STATUS_REAL_ZERO,
    RECALL_STATUS_VALID,
    calculate_recall_at_k,
    calculate_recall_at_k_details,
)


class TestRecallAtK(unittest.TestCase):
    def test_recall_at_5_with_valid_ground_truth(self):
        result = calculate_recall_at_k_details(
            ["A", "X", "B", "Y", "C"],
            ["A", "B", "C", "D"],
            k=5
        )

        self.assertEqual(result["status"], RECALL_STATUS_VALID)
        self.assertEqual(result["retrieved_relevant_count"], 3)
        self.assertEqual(result["total_relevant_count"], 4)
        self.assertAlmostEqual(result["score"], 0.75)

    def test_recall_at_5_real_zero(self):
        result = calculate_recall_at_k_details(
            ["X", "Y", "Z", "Q", "P"],
            ["A", "B", "C"],
            k=5
        )

        self.assertEqual(result["status"], RECALL_STATUS_REAL_ZERO)
        self.assertEqual(result["retrieved_relevant_count"], 0)
        self.assertEqual(result["total_relevant_count"], 3)
        self.assertEqual(result["score"], 0.0)

    def test_missing_ground_truth_is_invalid(self):
        result = calculate_recall_at_k_details(
            ["A", "B", "C"],
            None,
            k=5
        )

        self.assertEqual(result["status"], RECALL_STATUS_MISSING_GROUND_TRUTH)
        self.assertIsNone(result["retrieved_relevant_count"])
        self.assertIsNone(result["total_relevant_count"])
        self.assertIsNone(result["score"])

    def test_incomplete_retrieval_still_computes_with_status(self):
        result = calculate_recall_at_k_details(
            ["A", "B"],
            ["A", "B", "C"],
            k=5
        )

        self.assertEqual(result["status"], RECALL_STATUS_INCOMPLETE_RETRIEVAL)
        self.assertEqual(result["retrieved_count"], 2)
        self.assertEqual(result["retrieved_relevant_count"], 2)
        self.assertEqual(result["total_relevant_count"], 3)
        self.assertAlmostEqual(result["score"], 2 / 3)

    def test_duplicate_retrieved_ids_do_not_inflate_numerator(self):
        result = calculate_recall_at_k_details(
            ["A", "A", "B", "X", "Y"],
            ["A", "B", "C"],
            k=5
        )

        self.assertEqual(result["status"], RECALL_STATUS_VALID)
        self.assertEqual(result["retrieved_relevant_count"], 2)
        self.assertEqual(result["total_relevant_count"], 3)
        self.assertAlmostEqual(result["score"], 2 / 3)

    def test_score_only_wrapper_returns_recall_score(self):
        score = calculate_recall_at_k(
            ["A", "X", "B", "Y", "C"],
            ["A", "B", "C", "D"],
            k=5
        )

        self.assertAlmostEqual(score, 0.75)


if __name__ == "__main__":
    unittest.main()
