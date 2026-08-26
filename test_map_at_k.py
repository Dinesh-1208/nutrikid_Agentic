import unittest

from evaluation.metrics.retrieval_metrics import (
    MAP_STATUS_EMPTY_RETRIEVAL,
    MAP_STATUS_MISSING_GROUND_TRUTH,
    MAP_STATUS_REAL_ZERO,
    MAP_STATUS_VALID,
    calculate_ap_at_k_details,
    calculate_map_at_k_details,
)

# AP@K is normalized by the TRUE total number of relevant items for the
# query (total_relevant_count), not by the number of relevant items
# actually found within the top K. A relevant item never retrieved
# contributes 0 to the numerator sum, but does not shrink the denominator.
# Per Manning, Raghavan & Schutze, "Introduction to Information Retrieval"
# (2008), Chapter 8, Section 8.4, Eq. 8.8.


class TestMapAtK(unittest.TestCase):
    def test_valid_gold_id_ap_at_5(self):
        # Eq. 8.8 worked example: gold has 4 relevant chunks, only 3 are
        # retrieved (at ranks 1, 3, 5); the 4th ("D") is never retrieved at
        # all and contributes 0 to the sum, but total_relevant_count stays 4.
        # score_sum = 1/1 + 2/3 + 3/5 = 2.266666...
        # AP@5 = 2.266666... / 4 = 0.566666...
        result = calculate_ap_at_k_details(
            ["A", "X", "C", "Y", "B"],
            ["A", "B", "C", "D"],
            k=5
        )

        self.assertEqual(result["status"], MAP_STATUS_VALID)
        self.assertEqual(result["relevance_labels"], [True, False, True, False, True])
        self.assertEqual(result["retrieved_relevant_count"], 3)
        self.assertEqual(result["total_relevant_count"], 4)
        self.assertAlmostEqual(result["score"], (1.0 + (2 / 3) + (3 / 5)) / 4)
        self.assertAlmostEqual(result["score"], 0.5666666666666667)

    def test_all_relevant_found_gives_perfect_ap(self):
        # Every gold-relevant chunk is retrieved, all ranked at the very
        # top: num_hits == total_relevant_count, so AP@5 = 1.0 exactly,
        # same as it would be under the old (buggy) num_hits-normalized
        # formula. This confirms the fix only changes scores for queries
        # with genuine misses, not perfect retrievals.
        result = calculate_ap_at_k_details(
            ["A", "B", "C", "X", "Y"],
            ["A", "B", "C"],
            k=5
        )

        self.assertEqual(result["status"], MAP_STATUS_VALID)
        self.assertEqual(result["relevance_labels"], [True, True, True, False, False])
        self.assertEqual(result["retrieved_relevant_count"], 3)
        self.assertEqual(result["total_relevant_count"], 3)
        self.assertAlmostEqual(result["score"], 1.0)

    def test_real_zero_ap_at_5(self):
        # No relevant chunk appears anywhere in the top 5. score_sum = 0,
        # so AP@5 = 0 regardless of what total_relevant_count is normalized
        # by - this case is unaffected by the total_relevant_count fix.
        result = calculate_ap_at_k_details(
            ["X", "Y", "Z", "Q", "P"],
            ["A", "B", "C"],
            k=5
        )

        self.assertEqual(result["status"], MAP_STATUS_REAL_ZERO)
        self.assertEqual(result["relevance_labels"], [False, False, False, False, False])
        self.assertEqual(result["retrieved_relevant_count"], 0)
        self.assertEqual(result["total_relevant_count"], 3)
        self.assertEqual(result["score"], 0.0)

    def test_missing_ground_truth_is_not_zero(self):
        missing_result = calculate_ap_at_k_details(["A", "B"], None, k=5)
        empty_result = calculate_ap_at_k_details(["A", "B"], [], k=5)

        for result in (missing_result, empty_result):
            self.assertEqual(result["status"], MAP_STATUS_MISSING_GROUND_TRUTH)
            self.assertIsNone(result["score"])

    def test_empty_retrieval_is_not_zero(self):
        result = calculate_ap_at_k_details(
            [],
            ["A", "B", "C"],
            k=5
        )

        self.assertEqual(result["status"], MAP_STATUS_EMPTY_RETRIEVAL)
        self.assertIsNone(result["score"])

    def test_duplicate_retrieved_ids_do_not_inflate_ap(self):
        # gold has 3 total relevant chunks; only "A" and "B" are ever
        # retrieved ("A" is duplicated, "C" is never retrieved).
        # score_sum = 1/1 + 2/3 = 1.666666...
        # AP@5 = 1.666666... / 3 = 0.555555...  (normalized by
        # total_relevant_count=3, not by num_hits=2)
        result = calculate_ap_at_k_details(
            ["A", "A", "B", "X", "Y"],
            ["A", "B", "C"],
            k=5
        )

        self.assertEqual(result["status"], MAP_STATUS_VALID)
        self.assertEqual(result["relevance_labels"], [True, False, True, False, False])
        self.assertEqual(result["retrieved_relevant_count"], 2)
        self.assertEqual(result["total_relevant_count"], 3)
        self.assertAlmostEqual(result["score"], (1.0 + (2 / 3)) / 3)

    def test_map_at_5_averages_only_valid_scores(self):
        q1 = calculate_ap_at_k_details(["A", "X", "C", "Y", "B"], ["A", "B", "C", "D"], k=5)
        q2 = calculate_ap_at_k_details(["X", "B", "Y", "Z", "Q"], ["B"], k=5)
        q3 = calculate_ap_at_k_details(["A", "X", "Y", "Z", "Q"], ["A"], k=5)
        missing = calculate_ap_at_k_details(["A", "B"], None, k=5)

        result = calculate_map_at_k_details([q1, q2, q3, missing])

        self.assertEqual(result["valid_cases"], 3)
        self.assertEqual(result["missing_ground_truth"], 1)
        self.assertAlmostEqual(
            result["score"],
            (((1.0 + (2 / 3) + (3 / 5)) / 4) + 0.5 + 1.0) / 3
        )

    def test_unannotated_dataset_does_not_become_zero_map(self):
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
        ap_results = [
            calculate_ap_at_k_details(["A", "B", "C", "D", "E"], case.get("relevant_chunk_ids"), k=5)
            for case in unannotated_cases
        ]
        result = calculate_map_at_k_details(ap_results)

        self.assertEqual(result["valid_cases"], 0)
        self.assertEqual(result["missing_ground_truth"], len(unannotated_cases))
        self.assertIsNone(result["score"])


if __name__ == "__main__":
    unittest.main()
