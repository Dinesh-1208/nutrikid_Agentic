import unittest

from evaluation.metrics.retrieval_metrics import (
    MRR_STATUS_EMPTY_RETRIEVAL,
    MRR_STATUS_INCOMPLETE_RETRIEVAL,
    MRR_STATUS_INVALID_GROUND_TRUTH,
    MRR_STATUS_MISSING_GROUND_TRUTH,
    MRR_STATUS_REAL_ZERO,
    MRR_STATUS_VALID,
    calculate_mean_mrr_at_k_details,
    calculate_mrr_at_k,
    calculate_mrr_at_k_details,
)


class TestMrrAtK(unittest.TestCase):
    def test_first_relevant_at_rank_two(self):
        result = calculate_mrr_at_k_details(
            ["X", "B", "Y", "C", "Z"],
            ["A", "B", "C"],
            k=5
        )

        self.assertEqual(result["status"], MRR_STATUS_VALID)
        self.assertEqual(result["first_relevant_rank"], 2)
        self.assertEqual(result["retrieved_count"], 5)
        self.assertEqual(result["gold_relevant_count"], 3)
        self.assertAlmostEqual(result["score"], 0.5)

    def test_no_gold_match_is_real_zero(self):
        result = calculate_mrr_at_k_details(
            ["X", "Y", "Z", "Q", "P"],
            ["A", "B", "C"],
            k=5
        )

        self.assertEqual(result["status"], MRR_STATUS_REAL_ZERO)
        self.assertIsNone(result["first_relevant_rank"])
        self.assertEqual(result["score"], 0.0)

    def test_missing_ground_truth_is_not_zero(self):
        missing_result = calculate_mrr_at_k_details(["A", "B", "C", "D", "E"], None, k=5)
        empty_result = calculate_mrr_at_k_details(["A", "B", "C", "D", "E"], [], k=5)

        for result in (missing_result, empty_result):
            self.assertEqual(result["status"], MRR_STATUS_MISSING_GROUND_TRUTH)
            self.assertIsNone(result["first_relevant_rank"])
            self.assertIsNone(result["score"])

    def test_first_relevant_at_rank_one(self):
        result = calculate_mrr_at_k_details(
            ["A", "X", "Y", "Z", "Q"],
            ["A", "B", "C"],
            k=5
        )

        self.assertEqual(result["status"], MRR_STATUS_VALID)
        self.assertEqual(result["first_relevant_rank"], 1)
        self.assertEqual(result["score"], 1.0)

    def test_duplicate_retrieval_ids_do_not_create_earlier_rank(self):
        result = calculate_mrr_at_k_details(
            ["X", "B", "B", "C", "Z"],
            ["A", "B", "C"],
            k=5
        )

        self.assertEqual(result["status"], MRR_STATUS_VALID)
        self.assertEqual(result["first_relevant_rank"], 2)
        self.assertAlmostEqual(result["score"], 0.5)

    def test_multiple_queries_average_valid_and_real_zero_scores(self):
        q1 = calculate_mrr_at_k_details(["A", "X", "Y", "Z", "Q"], ["A"], k=5)
        q2 = calculate_mrr_at_k_details(["X", "B", "Y", "Z", "Q"], ["B"], k=5)
        q3 = calculate_mrr_at_k_details(["X", "Y", "Z", "Q", "P"], ["A"], k=5)
        missing = calculate_mrr_at_k_details(["A", "B", "C", "D", "E"], None, k=5)

        result = calculate_mean_mrr_at_k_details([q1, q2, q3, missing])

        self.assertEqual(result["valid_cases"], 3)
        self.assertEqual(result["missing_ground_truth"], 1)
        self.assertEqual(result["real_zero_cases"], 1)
        self.assertAlmostEqual(result["score"], 0.5)

    def test_empty_retrieval_is_not_zero(self):
        result = calculate_mrr_at_k_details(
            [],
            ["A", "B", "C"],
            k=5
        )

        self.assertEqual(result["status"], MRR_STATUS_EMPTY_RETRIEVAL)
        self.assertIsNone(result["score"])

    def test_incomplete_retrieval_is_not_treated_as_valid(self):
        result = calculate_mrr_at_k_details(
            ["A", "X"],
            ["A", "B", "C"],
            k=5
        )

        self.assertEqual(result["status"], MRR_STATUS_INCOMPLETE_RETRIEVAL)
        self.assertEqual(result["first_relevant_rank"], 1)
        self.assertIsNone(result["score"])

    def test_invalid_ground_truth_is_not_zero(self):
        result = calculate_mrr_at_k_details(
            ["A", "B", "C", "D", "E"],
            ["A", ""],
            k=5
        )

        self.assertEqual(result["status"], MRR_STATUS_INVALID_GROUND_TRUTH)
        self.assertIsNone(result["score"])

    def test_score_only_wrapper_returns_rr_score(self):
        score = calculate_mrr_at_k(
            ["X", "B", "Y", "C", "Z"],
            ["A", "B", "C"],
            k=5
        )

        self.assertAlmostEqual(score, 0.5)

    def test_unannotated_dataset_does_not_become_zero_mrr(self):
        # A self-contained synthetic batch of entirely unannotated cases (no
        # relevant_chunk_ids at all) - this test proves the status-handling
        # invariant itself (an unannotated dataset must report
        # MISSING_GROUND_TRUTH, never a fabricated 0.0 score), independent of
        # whichever real dataset evaluation/dataset.py happens to load. It
        # previously imported the real EVALUATION_DATA and relied on that
        # dataset being 100% unannotated, which stopped being true once the
        # finalized, gold-annotated 49-case dataset (with real
        # relevant_chunk_ids on 38 of 49 cases) became the active dataset.
        unannotated_cases = [{"relevant_chunk_ids": None} for _ in range(7)]
        mrr_results = [
            calculate_mrr_at_k_details(["A", "B", "C", "D", "E"], case.get("relevant_chunk_ids"), k=5)
            for case in unannotated_cases
        ]
        result = calculate_mean_mrr_at_k_details(mrr_results)

        self.assertEqual(result["valid_cases"], 0)
        self.assertEqual(result["missing_ground_truth"], len(unannotated_cases))
        self.assertIsNone(result["score"])


if __name__ == "__main__":
    unittest.main()
