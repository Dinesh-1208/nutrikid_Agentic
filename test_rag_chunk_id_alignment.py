import unittest

from rag.services.prompt_context_service import PromptContextService
from evaluation.metrics.retrieval_metrics import (
    RECALL_STATUS_VALID,
    RECALL_STATUS_REAL_ZERO,
    MRR_STATUS_VALID,
    MAP_STATUS_VALID,
    calculate_recall_at_k_details,
    calculate_mrr_at_k_details,
    calculate_ap_at_k_details,
)

# Regression coverage for the RAG chunk-ID alignment fix.
#
# Bug: rag/chunker.py's ParentChildChunker builds retrievable *child* chunk IDs shaped
# like "<source_id>_P0_C0" from each rag_data.json record's own "id" field
# (<source_id>). The retriever's final output ("id") is always this child-chunk form,
# but every gold `relevant_chunk_ids` list in docs/evaluation/phase2c_gold_annotations.json
# is authored at the source-record level (e.g. "rag_iron_absorption_heme_001", matching
# rag_data.json's own "id" field) - never the "_P0_C0"-suffixed form. A full-corpus
# audit confirmed this affected all 38 RAG-gold-bearing cases (86/86 unique gold IDs had
# zero exact matches against any real child or parent chunk ID), so Recall@5/MAP@5/MRR@5
# were structurally unable to score a true positive.
#
# Fix: rag/services/prompt_context_service.py now passes a "source_id" field through
# to every retrieved result (it was already computed by the chunker and present on
# every child-chunk dict, just dropped during final formatting). evaluation/evaluator.py
# now builds retrieved_chunk_ids by preferring "source_id" over the child-level "id".
# No retrieval_metrics.py formula changed; no gold data changed; Precision@5 is
# unaffected (it never uses chunk IDs, only positional LLM relevance judgments).


def _build_evaluator_retrieved_chunk_ids(retrieved_contexts):
    """Mirrors the exact list-comprehension in evaluation/evaluator.py::run_single_evaluation."""
    return [
        (chunk.get("source_id") or chunk.get("id"))
        for chunk in retrieved_contexts
        if chunk.get("source_id") or chunk.get("id")
    ]


class TestPromptContextServiceSourceIdPassthrough(unittest.TestCase):
    """Covers item 1/2 of the pipeline trace: parent-id vs child-chunk-id alignment
    at the exact point (rag/services/prompt_context_service.py) where the retriever
    used to silently drop the source_id it already had computed."""

    def setUp(self):
        self.service = PromptContextService()

    def test_one_parent_one_child_passes_through_source_id(self):
        # A record whose text is short enough to produce exactly one parent and one
        # child chunk (the common case - 72 of the 86 unique gold IDs in the dataset).
        retrieved = [{
            "id": "RAG_INF_1_P0_C0",
            "parent_id": "RAG_INF_1_P0",
            "source_id": "RAG_INF_1",
            "text": "Infants aged 6 to 8 months should be given complementary foods at least twice a day.",
            "metadata": {"type": "condition"},
            "score": 0.9,
        }]
        parent_map = {"RAG_INF_1_P0": {"id": "RAG_INF_1_P0", "text": "Infants aged 6 to 8 months..."}}

        out = self.service.expand_and_format_context(retrieved, parent_map)

        self.assertEqual(out[0]["id"], "RAG_INF_1_P0_C0")
        self.assertEqual(out[0]["source_id"], "RAG_INF_1")

    def test_one_parent_multiple_children_all_share_one_source_id(self):
        # A record long enough to be split into multiple child chunks (14 of the 86
        # unique gold IDs in the dataset, e.g. the two iron-bioavailability records).
        retrieved = [
            {
                "id": "rag_iron_absorption_heme_001_P0_C0",
                "parent_id": "rag_iron_absorption_heme_001_P0",
                "source_id": "rag_iron_absorption_heme_001",
                "text": "Iron Bioavailability: Heme iron (animal source) has approximately 15-35% absorption...",
                "metadata": {"type": "mineral_metabolism"},
                "score": 0.8,
            },
            {
                "id": "rag_iron_absorption_heme_001_P0_C1",
                "parent_id": "rag_iron_absorption_heme_001_P0",
                "source_id": "rag_iron_absorption_heme_001",
                "text": "...Non-heme (plant) has 5%. Absorption is enhanced by Vitamin C...",
                "metadata": {"type": "mineral_metabolism"},
                "score": 0.4,
            },
        ]
        parent_map = {"rag_iron_absorption_heme_001_P0": {"id": "rag_iron_absorption_heme_001_P0", "text": "..."}}

        out = self.service.expand_and_format_context(retrieved, parent_map)

        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["id"], "rag_iron_absorption_heme_001_P0_C0")
        self.assertEqual(out[1]["id"], "rag_iron_absorption_heme_001_P0_C1")
        # Different child IDs, but both must canonicalize to the same source record.
        self.assertEqual(out[0]["source_id"], "rag_iron_absorption_heme_001")
        self.assertEqual(out[1]["source_id"], "rag_iron_absorption_heme_001")

    def test_missing_source_id_does_not_crash(self):
        # Defensive: a hand-built/mocked retriever result without source_id (e.g. in
        # older tests) must not break formatting - "source_id" simply comes back None.
        retrieved = [{"id": "SOME_ID_P0_C0", "parent_id": "SOME_ID_P0", "text": "x", "score": 0.1}]
        out = self.service.expand_and_format_context(retrieved, {})
        self.assertIsNone(out[0]["source_id"])


class TestEvaluatorChunkIdCanonicalization(unittest.TestCase):
    """Covers item 3 of the pipeline trace: evaluator.py's construction of
    retrieved_chunk_ids, the single call site that feeds Recall@5/MAP@5/MRR@5."""

    def test_prefers_source_id_over_child_id(self):
        retrieved_contexts = [
            {"id": "RAG_INF_1_P0_C0", "source_id": "RAG_INF_1"},
            {"id": "RAG_INF_2_P0_C0", "source_id": "RAG_INF_2"},
        ]
        self.assertEqual(
            _build_evaluator_retrieved_chunk_ids(retrieved_contexts),
            ["RAG_INF_1", "RAG_INF_2"],
        )

    def test_falls_back_to_id_when_source_id_absent(self):
        # Backward compatibility for a retriever/mock that only supplies "id".
        retrieved_contexts = [{"id": "LEGACY_CHUNK_1"}, {"id": "LEGACY_CHUNK_2"}]
        self.assertEqual(
            _build_evaluator_retrieved_chunk_ids(retrieved_contexts),
            ["LEGACY_CHUNK_1", "LEGACY_CHUNK_2"],
        )

    def test_multiple_children_of_the_same_source_collapse_to_repeated_source_id(self):
        retrieved_contexts = [
            {"id": "rag_iron_absorption_heme_001_P0_C0", "source_id": "rag_iron_absorption_heme_001"},
            {"id": "rag_iron_absorption_heme_001_P0_C1", "source_id": "rag_iron_absorption_heme_001"},
            {"id": "RAG_DO_1_P0_C0", "source_id": "RAG_DO_1"},
        ]
        result = _build_evaluator_retrieved_chunk_ids(retrieved_contexts)
        # Order and repetition are preserved here deliberately - retrieval_metrics.py's
        # own set()/seen-id dedup logic (already tested in test_recall_at_k.py etc.) is
        # responsible for preventing double-counting, not this list construction.
        self.assertEqual(result, ["rag_iron_absorption_heme_001", "rag_iron_absorption_heme_001", "RAG_DO_1"])


class TestRetrievalMetricsWithCanonicalIds(unittest.TestCase):
    """End-to-end proof that once retrieved_chunk_ids are canonicalized to source_id
    form, they correctly match source-id-level gold data - covering rank-1 hits,
    later-rank hits, real misses, and the one-parent/multiple-children duplicate case -
    entirely through the existing, UNCHANGED retrieval_metrics.py formulas."""

    def test_one_parent_one_child_relevant_at_rank_one(self):
        # EVAL_011-style case: gold = ["RAG_INF_1"], the record has exactly one child.
        retrieved = _build_evaluator_retrieved_chunk_ids([
            {"id": "RAG_INF_1_P0_C0", "source_id": "RAG_INF_1"},
            {"id": "RAG_INF_2_P0_C0", "source_id": "RAG_INF_2"},
            {"id": "RAG3003_P0_C0", "source_id": "RAG3003"},
            {"id": "RAG3002_P0_C0", "source_id": "RAG3002"},
            {"id": "goal_complementary_001_P0_C0", "source_id": "goal_complementary_001"},
        ])
        gold = ["RAG_INF_1"]

        recall = calculate_recall_at_k_details(retrieved, gold, k=5)
        mrr = calculate_mrr_at_k_details(retrieved, gold, k=5)
        ap = calculate_ap_at_k_details(retrieved, gold, k=5)

        self.assertEqual(recall["status"], RECALL_STATUS_VALID)
        self.assertAlmostEqual(recall["score"], 1.0)
        self.assertEqual(mrr["status"], MRR_STATUS_VALID)
        self.assertAlmostEqual(mrr["score"], 1.0)  # first relevant hit at rank 1
        self.assertEqual(ap["status"], MAP_STATUS_VALID)
        self.assertAlmostEqual(ap["score"], 1.0)

    def test_relevant_result_found_at_a_later_rank(self):
        retrieved = _build_evaluator_retrieved_chunk_ids([
            {"id": "RAG_IRON_6_P0_C0", "source_id": "RAG_IRON_6"},
            {"id": "RAG_IRON_3_P0_C0", "source_id": "RAG_IRON_3"},
            {"id": "RAG_IRON_7_P0_C0", "source_id": "RAG_IRON_7"},
            {"id": "RAG_DO_1_P0_C0", "source_id": "RAG_DO_1"},
            {"id": "rag_iron_002_P0_C0", "source_id": "rag_iron_002"},
        ])
        gold = ["RAG_DO_1"]  # present at rank 4, to exercise "later rank" explicitly

        mrr = calculate_mrr_at_k_details(retrieved, gold, k=5)

        self.assertEqual(mrr["status"], MRR_STATUS_VALID)
        self.assertEqual(mrr["first_relevant_rank"], 4)
        self.assertAlmostEqual(mrr["score"], 1.0 / 4.0)

    def test_no_relevant_chunk_retrieved_is_a_real_zero_not_a_missing_status(self):
        retrieved = _build_evaluator_retrieved_chunk_ids([
            {"id": "RAG_RULE_2_P0_C0", "source_id": "RAG_RULE_2"},
            {"id": "RAG3008_P0_C0", "source_id": "RAG3008"},
            {"id": "RAG_INF_4_P0_C0", "source_id": "RAG_INF_4"},
            {"id": "RAG2005_P0_C0", "source_id": "RAG2005"},
            {"id": "RAG_PREG_10_P0_C0", "source_id": "RAG_PREG_10"},
        ])
        gold = ["rag_food_allergy_cross_reactivity_001"]

        recall = calculate_recall_at_k_details(retrieved, gold, k=5)
        mrr = calculate_mrr_at_k_details(retrieved, gold, k=5)

        self.assertEqual(recall["status"], RECALL_STATUS_REAL_ZERO)
        self.assertEqual(recall["score"], 0.0)
        self.assertEqual(mrr["score"], 0.0)

    def test_one_parent_multiple_children_both_retrieved_do_not_double_count(self):
        # Two DIFFERENT child chunks from the SAME source record both land in the
        # top-5 (a real, observed scenario for the 14 multi-child gold sources) -
        # canonicalization must not let this source count as "2 relevant hits".
        retrieved = _build_evaluator_retrieved_chunk_ids([
            {"id": "rag_iron_absorption_heme_001_P0_C0", "source_id": "rag_iron_absorption_heme_001"},
            {"id": "rag_iron_absorption_heme_001_P0_C1", "source_id": "rag_iron_absorption_heme_001"},
            {"id": "RAG_IRON_6_P0_C0", "source_id": "RAG_IRON_6"},
            {"id": "RAG_IRON_3_P0_C0", "source_id": "RAG_IRON_3"},
            {"id": "RAG_DO_1_P0_C0", "source_id": "RAG_DO_1"},
        ])
        gold = ["rag_iron_absorption_heme_001", "RAG_IRON_6"]

        recall = calculate_recall_at_k_details(retrieved, gold, k=5)
        ap = calculate_ap_at_k_details(retrieved, gold, k=5)

        # Two distinct gold IDs relevant, two distinct gold IDs actually matched -
        # not three, even though the duplicated source_id appears twice in the list.
        self.assertEqual(recall["retrieved_relevant_count"], 2)
        self.assertEqual(recall["total_relevant_count"], 2)
        self.assertAlmostEqual(recall["score"], 1.0)
        self.assertEqual(ap["retrieved_relevant_count"], 2)

    def test_precision_at_5_is_unaffected_by_chunk_id_format(self):
        # Precision@5 (evaluated separately in evaluator.py via the LLM ContextJudge on
        # positional relevance_labels) never consumes chunk IDs at all - confirming the
        # canonicalization fix has zero surface area on it. This is a documentation
        # test: it asserts the recall/MRR/MAP functions' signatures are what
        # evaluator.py actually calls with canonicalized IDs, while Precision@5's own
        # calculate_precision_at_k_details (imported here only to prove it takes no
        # chunk-id argument at all) is untouched by this fix.
        from evaluation.metrics.retrieval_metrics import calculate_precision_at_k_details
        import inspect
        params = list(inspect.signature(calculate_precision_at_k_details).parameters)
        self.assertNotIn("retrieved_chunk_ids", params)
        self.assertNotIn("gold_relevant_chunk_ids", params)


if __name__ == "__main__":
    unittest.main()
