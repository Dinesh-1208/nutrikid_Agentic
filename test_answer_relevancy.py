import math
import unittest

import numpy as np

from evaluation.metrics.relevancy_metrics import (
    ANSWER_RELEVANCY_STATUS_EVALUATION_FAILURE,
    ANSWER_RELEVANCY_STATUS_NO_QUESTIONS_GENERATED,
    ANSWER_RELEVANCY_STATUS_REAL_ZERO,
    ANSWER_RELEVANCY_STATUS_VALID,
    calculate_answer_relevancy,
)

# Answer Relevancy: AR = (1/n) * sum(sim(q, qi)).
# Per Es et al. (2023) "RAGAS: Automated Evaluation of Retrieval Augmented
# Generation" (arXiv:2309.15217), Section 3, page 3, Eq. 1.
#
# An empty/invalid hypothetical-question list must never be silently scored
# as 0.0: it is either NO_QUESTIONS_GENERATED (evaluation succeeded, no
# valid question text produced) or EVALUATION_FAILURE (judge/API/parser
# failure), both distinct from REAL_ZERO (valid questions existed, but their
# similarity to the original question was genuinely 0.0).


def _vector_for_similarity(sim):
    # Unit vector whose cosine similarity with (1.0, 0.0) is exactly `sim`.
    clipped = max(-1.0, min(1.0, sim))
    return np.array([clipped, math.sqrt(max(0.0, 1.0 - clipped ** 2))])


class FakeEmbeddingModel:
    """Deterministic stand-in for the SentenceTransformer embedding model."""

    def __init__(self, query_text, question_similarity_map):
        self.query_text = query_text
        self.question_similarity_map = question_similarity_map

    def encode(self, text, convert_to_numpy=True):
        if text == self.query_text:
            return np.array([1.0, 0.0])
        return _vector_for_similarity(self.question_similarity_map[text])


class TestAnswerRelevancy(unittest.TestCase):
    def test_valid_mixed_similarities(self):
        query = "What foods help with iron deficiency in toddlers?"
        questions = [
            {"question_id": "Q1", "text": "H1"},
            {"question_id": "Q2", "text": "H2"},
            {"question_id": "Q3", "text": "H3"},
        ]
        model = FakeEmbeddingModel(query, {"H1": 0.89, "H2": 0.85, "H3": 0.31})

        result = calculate_answer_relevancy(query, questions, model)

        self.assertEqual(result["status"], ANSWER_RELEVANCY_STATUS_VALID)
        self.assertAlmostEqual(result["mean_similarity"], round((0.89 + 0.85 + 0.31) / 3, 4), places=4)
        self.assertEqual(len(result["question_scores"]), 3)

    def test_real_zero_valid_questions_all_zero_similarity(self):
        query = "Q"
        questions = [
            {"question_id": "Q1", "text": "orthogonal"},
            {"question_id": "Q2", "text": "opposite"},
        ]
        # "orthogonal" -> raw similarity 0.0; "opposite" -> raw similarity
        # -1.0, clamped to 0.0 by the preserved negative-similarity clamp.
        model = FakeEmbeddingModel(query, {"orthogonal": 0.0, "opposite": -1.0})

        result = calculate_answer_relevancy(query, questions, model)

        self.assertEqual(result["status"], ANSWER_RELEVANCY_STATUS_REAL_ZERO)
        self.assertEqual(result["mean_similarity"], 0.0)
        self.assertEqual(len(result["question_scores"]), 2)

    def test_no_questions_generated_empty_list(self):
        result = calculate_answer_relevancy("Q", [], embedding_model=None, evaluation_failed=False)

        self.assertEqual(result["status"], ANSWER_RELEVANCY_STATUS_NO_QUESTIONS_GENERATED)
        self.assertIsNone(result["mean_similarity"])
        self.assertIsNone(result["std_similarity"])
        self.assertEqual(result["question_scores"], [])

    def test_no_questions_generated_all_blank_text(self):
        questions = [{"question_id": "Q1", "text": ""}, {"question_id": "Q2", "text": None}]
        # The query is still encoded before per-question filtering, so a
        # working embedding model is required even though no hq text
        # survives the blank-text filter.
        model = FakeEmbeddingModel("Q", {})
        result = calculate_answer_relevancy("Q", questions, embedding_model=model, evaluation_failed=False)

        self.assertEqual(result["status"], ANSWER_RELEVANCY_STATUS_NO_QUESTIONS_GENERATED)
        self.assertIsNone(result["mean_similarity"])

    def test_evaluation_failure_is_not_zero(self):
        result = calculate_answer_relevancy("Q", [], embedding_model=None, evaluation_failed=True)

        self.assertEqual(result["status"], ANSWER_RELEVANCY_STATUS_EVALUATION_FAILURE)
        self.assertIsNone(result["mean_similarity"])
        self.assertIsNone(result["std_similarity"])

    def test_evaluation_failure_takes_priority_over_partial_questions(self):
        # Even if hypothetical questions were generated before the judge/API
        # failed, evaluation_failed=True must still yield EVALUATION_FAILURE,
        # not a score computed from a possibly-incomplete question list.
        questions = [{"question_id": "Q1", "text": "some question"}]
        result = calculate_answer_relevancy("Q", questions, embedding_model=None, evaluation_failed=True)

        self.assertEqual(result["status"], ANSWER_RELEVANCY_STATUS_EVALUATION_FAILURE)
        self.assertIsNone(result["mean_similarity"])


if __name__ == "__main__":
    unittest.main()
