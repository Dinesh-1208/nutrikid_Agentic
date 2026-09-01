import importlib
import json
import unittest
from unittest.mock import MagicMock, patch

# ============================================================================
# Phase 4B regression coverage: connecting the finalized 49-case dataset to
# the runtime evaluator/comparator, fixing Context Recall's gold-field
# wiring, removing the seven dead first-generation RAG modules and the dead
# BaseJudge._call_judge method, and correcting three stale
# judge/model-backend defaults. See docs/phase4b_high_confidence_cleanup.md
# for the full narrative.
# ============================================================================


class TestFinalizedDatasetIsTheActiveDataset(unittest.TestCase):
    """Items 1, 2, 3, 6, 7."""

    def test_evaluation_dataset_loads_exactly_49_cases(self):
        from evaluation.dataset import EVALUATION_DATA
        self.assertEqual(len(EVALUATION_DATA), 49)

    def test_all_49_ids_present_in_order(self):
        from evaluation.dataset import EVALUATION_DATA
        ids = [c["id"] for c in EVALUATION_DATA]
        self.assertEqual(ids, [f"EVAL_{i:03d}" for i in range(1, 50)])

    def test_comparator_module_imports_the_new_dataset_not_the_legacy_one(self):
        import evaluation.comparator as comparator_module
        # comparator.py's own EVALUATION_DATA binding must be the 49-case set.
        self.assertEqual(len(comparator_module.EVALUATION_DATA), 49)
        legacy_ids = {"Q_COND_01", "Q_ALL_01", "Q_GOAL_01", "Q_SUIT_01", "Q_GEN_01"}
        active_ids = {c["id"] for c in comparator_module.EVALUATION_DATA}
        self.assertTrue(active_ids.isdisjoint(legacy_ids))

    def test_legacy_dataset_is_preserved_unmodified_but_not_wired_into_comparator(self):
        from evaluation.legacy_dataset import LEGACY_EVALUATION_DATA
        import evaluation.comparator as comparator_module
        self.assertEqual(len(LEGACY_EVALUATION_DATA), 100)
        self.assertEqual(LEGACY_EVALUATION_DATA[0]["id"], "Q_COND_01")
        # The legacy module must not be imported by comparator.py at all.
        self.assertNotIn("legacy_dataset", comparator_module.__spec__.name)
        with open("evaluation/comparator.py", encoding="utf-8") as f:
            comparator_src = f.read()
        self.assertNotIn("legacy_dataset", comparator_src)
        self.assertNotIn("LEGACY_EVALUATION_DATA", comparator_src)

    def test_relevant_chunk_ids_are_intact_after_wiring(self):
        # 38/11 was the split before the Phase 2D safety-case replacement
        # (2026-08-31, docs/evaluation/phase2d_replacement_cases.md): three of
        # the four replaced cases (EVAL_037, EVAL_038, EVAL_039) went from
        # relevant_chunk_ids=None (structured_db-only, no RAG chunk) to real,
        # retrieval-verified RAG grounding, correctly shifting the split to
        # 41/8 - this is an intended improvement from that replacement, not a
        # regression.
        from evaluation.dataset import EVALUATION_DATA
        with_gold = [c for c in EVALUATION_DATA if c["relevant_chunk_ids"] is not None]
        without_gold = [c for c in EVALUATION_DATA if c["relevant_chunk_ids"] is None]
        self.assertEqual(len(with_gold), 41)
        self.assertEqual(len(without_gold), 8)
        for c in with_gold:
            self.assertIsInstance(c["relevant_chunk_ids"], list)
            self.assertGreater(len(c["relevant_chunk_ids"]), 0)

    def test_safety_ground_truth_is_non_null_only_for_the_20_selected_safety_cases(self):
        # Final evaluation dataset audit (2026-08-31,
        # docs/evaluation/final_evaluation_dataset_audit.md) integrated the
        # full, independently two-round-verified 20-case safety selection
        # (docs/evaluation/phase2d_ai_safety_ground_truth.json: the original
        # 16 cases + the 4 replacement cases already embedded by the prior
        # replacement pass) directly into phase2c_gold_annotations.json. The
        # remaining 29 cases were never part of that selection and correctly
        # remain null - this test verifies exactly that split, not a blanket
        # "always null" invariant.
        from evaluation.dataset import EVALUATION_DATA
        expected_non_null = {
            "EVAL_014", "EVAL_019", "EVAL_020", "EVAL_021", "EVAL_022",
            "EVAL_023", "EVAL_024", "EVAL_025", "EVAL_026", "EVAL_027",
            "EVAL_028", "EVAL_029", "EVAL_030", "EVAL_031", "EVAL_035",
            "EVAL_036", "EVAL_037", "EVAL_038", "EVAL_039", "EVAL_049",
        }
        self.assertEqual(len(expected_non_null), 20)
        actual_non_null = {c["id"] for c in EVALUATION_DATA if c["safety_ground_truth"] is not None}
        self.assertEqual(actual_non_null, expected_non_null)
        for c in EVALUATION_DATA:
            if c["id"] in expected_non_null:
                sgt = c["safety_ground_truth"]
                self.assertIn(sgt["overall"], ("Compliant", "Refusal", "Violation"))
                for key in ("diagnosis", "prescription", "allergy_violation", "age_violation"):
                    self.assertIsInstance(sgt[key], bool)
            else:
                self.assertIsNone(c["safety_ground_truth"])

    def test_dataset_matches_the_source_json_verbatim(self):
        from evaluation.dataset import EVALUATION_DATA
        with open("docs/evaluation/phase2c_gold_annotations.json", encoding="utf-8") as f:
            raw = json.load(f)["cases"]
        self.assertEqual(EVALUATION_DATA, raw)


class TestContextRecallGoldFieldWiring(unittest.TestCase):
    """Items 4, 5."""

    def _run_case_with_captured_recall_input(self, test_case):
        from evaluation.evaluator import KidsNutriEvaluator

        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = [{"id": "X_P0_C0", "source_id": "X", "text": "t", "score": 0.1}]
        mock_planner = MagicMock()
        mock_planner.generate_meal_plan.return_value = {
            "profile": {"age": 5, "weight_kg": 18, "goal": "g", "condition": "c", "allergies": []},
            "targets": {"calories_kcal": 1200},
            "totals": {"calories_kcal": 1200, "protein_g": 1, "fat_g": 1, "carbs_g": 1, "iron_mg": 1},
            "meal_plan": {},
        }
        mock_llm = MagicMock()
        mock_llm.generate_response.return_value = ("an answer", 0.1)

        captured = {}

        def fake_evaluate_recall(retrieved, expected, q_id=None, question=None):
            captured["expected_context"] = expected
            return {"facts": [{"fact": e, "is_present": True} for e in expected]}

        mock_judges = {
            "context": MagicMock(),
            "grounding": MagicMock(),
            "relevancy": MagicMock(),
            "safety": MagicMock(),
        }
        mock_judges["context"].evaluate_precision.return_value = {"relevance_map": []}
        mock_judges["context"].evaluate_recall.side_effect = fake_evaluate_recall
        mock_judges["grounding"].evaluate_grounding.return_value = {"claims": []}
        mock_judges["relevancy"].generate_hypothetical_questions.return_value = {"generated_questions": []}
        mock_judges["safety"].evaluate_safety.return_value = {
            "overall": "Compliant", "diagnosis": False, "prescription": False,
            "allergy_violation": False, "age_violation": False,
        }

        evaluator = KidsNutriEvaluator(mock_llm, mock_retriever, mock_planner, judges=mock_judges)
        result = evaluator.run_single_evaluation(test_case, "qwen_local")
        return result, captured

    def test_gold_facts_fact_text_is_passed_to_context_judge_not_raw_dicts(self):
        from evaluation.dataset import EVALUATION_DATA
        case = next(c for c in EVALUATION_DATA if c["gold_facts"])
        result, captured = self._run_case_with_captured_recall_input(case)

        expected_texts = [f["fact_text"] for f in case["gold_facts"]]
        self.assertEqual(captured["expected_context"], expected_texts)
        # Only plain strings must reach the judge - never the raw gold_facts
        # dict shape (fact_id/source_reference/chunk_reference/importance).
        for item in captured["expected_context"]:
            self.assertIsInstance(item, str)
        self.assertEqual(result["context_recall"], 1.0)

    def test_no_case_relies_on_the_old_expected_context_key(self):
        from evaluation.dataset import EVALUATION_DATA
        # The finalized schema has no expected_context field at all - confirm
        # the evaluator isn't silently reading a key that no longer exists.
        for case in EVALUATION_DATA:
            self.assertNotIn("expected_context", case)

    def test_evaluator_no_longer_reads_expected_context_key(self):
        with open("evaluation/evaluator.py", encoding="utf-8") as f:
            src = f.read()
        self.assertNotIn('test_case.get("expected_context"', src)
        self.assertIn('test_case.get("gold_facts")', src)

    def test_knowledge_only_case_with_no_profile_does_not_crash(self):
        from evaluation.dataset import EVALUATION_DATA
        case = next(c for c in EVALUATION_DATA if c["profile"] is None)
        result, captured = self._run_case_with_captured_recall_input(case)
        self.assertIsNotNone(result["response"])
        self.assertGreater(len(captured["expected_context"]), 0)


class TestDeadCodeRemoval(unittest.TestCase):
    """Items 8, 9."""

    def test_seven_dead_rag_modules_no_longer_exist_or_import(self):
        import os
        dead_files = [
            "rag/bm25_retriever.py", "rag/config.py", "rag/dataset_hasher.py",
            "rag/logger.py", "rag/performance_monitor.py", "rag/reranker.py",
            "rag/semantic_cache.py",
        ]
        for path in dead_files:
            self.assertFalse(os.path.exists(path), f"{path} should have been deleted")

        dead_modules = [
            "rag.bm25_retriever", "rag.config", "rag.dataset_hasher",
            "rag.logger", "rag.performance_monitor", "rag.reranker",
            "rag.semantic_cache",
        ]
        for mod_name in dead_modules:
            with self.assertRaises(ImportError):
                importlib.import_module(mod_name)

    def test_rag_services_equivalents_still_import_correctly(self):
        # The live replacements must be unaffected by the deletion.
        from rag.services.bm25_service import BM25Service
        from rag.services.config_service import ConfigurationService, RAGConfig
        from rag.services.dataset_version_service import DatasetVersionService
        from rag.services.logger_service import LoggerService
        from rag.services.metrics_service import MetricsService
        from rag.services.reranker_service import RerankerService
        from rag.services.cache_service import CacheService
        self.assertTrue(all([BM25Service, ConfigurationService, RAGConfig, DatasetVersionService,
                              LoggerService, MetricsService, RerankerService, CacheService]))

    def test_base_judge_call_judge_method_no_longer_exists(self):
        from evaluation.judges.base_judge import BaseJudge
        self.assertFalse(hasattr(BaseJudge, "_call_judge"))

    def test_base_judge_call_llm_with_retry_still_exists(self):
        from evaluation.judges.base_judge import BaseJudge
        self.assertTrue(hasattr(BaseJudge, "call_llm_with_retry"))


class TestCorrectedDefaults(unittest.TestCase):
    """Items 10, 11, 12, 13."""

    def test_evaluator_default_judge_model_is_groq_not_gemini(self):
        import inspect
        from evaluation.evaluator import KidsNutriEvaluator
        sig = inspect.signature(KidsNutriEvaluator.__init__)
        # Phase 4F renamed the default from "groq_llama70b" to "groq_judge" -
        # the old name mapped to "llama-3.3-70b-versatile", a model confirmed
        # NOT present in the account's live Groq catalog (see
        # docs/phase4f_groq_judge_configuration.md). "groq_judge" is the one
        # clear, honestly-named default judge backend.
        self.assertEqual(sig.parameters["judge_model"].default, "groq_judge")

    def test_comparator_default_models_is_qwen_local_only(self):
        import inspect
        from evaluation.comparator import KidsNutriComparator
        sig = inspect.signature(KidsNutriComparator.run_comparison)
        self.assertEqual(sig.parameters["models"].default, ["qwen_local"])

    def test_main_cli_defaults_are_unchanged_and_correct(self):
        with open("main.py", encoding="utf-8") as f:
            src = f.read()
        self.assertIn('"--model", type=str, default="qwen_local"', src)
        self.assertIn('"--models", type=str, default="qwen_local"', src)
        self.assertIn('"--judge-model", type=str, default="groq_judge"', src)

    def test_qwen_local_is_still_the_production_answer_route(self):
        from llm.llm_client import KidsNutriLLMClient
        client = KidsNutriLLMClient()
        self.assertEqual(client.default_model, "qwen_local")
        import torch
        with patch.object(client, "_call_local_transformers", return_value="ans") as m_local, \
             patch.object(client, "_call_groq") as m_groq, \
             patch.object(client, "_call_gemini") as m_gemini, \
             patch.object(torch.cuda, "is_available", return_value=True):
            text, _ = client.generate_response("s", "u", model_name="qwen_local")
        self.assertEqual(text, "ans")
        m_local.assert_called_once()
        m_groq.assert_not_called()
        m_gemini.assert_not_called()

    def test_groq_judge_is_the_default_judge_backend_and_routes_to_a_verified_model(self):
        # Phase 4F: "groq_judge" is the new, honestly-named primary judge
        # route. It must route to a model directly evidenced as available in
        # the account's live Groq catalog (docs/phase4f_groq_judge_configuration.md),
        # not the fictional "llama-3.3-70b-versatile".
        from llm.llm_client import KidsNutriLLMClient
        client = KidsNutriLLMClient()
        with patch.object(client, "_call_groq", return_value="judge json") as m_groq:
            text, _ = client.generate_response("s", "u", model_name="groq_judge")
        self.assertEqual(text, "judge json")
        m_groq.assert_called_once_with("openai/gpt-oss-120b", "s", "u")

    def test_groq_llama70b_is_still_reachable_as_deprecated_alias(self):
        # Phase 4F: "groq_llama70b" is kept only for backward compatibility -
        # it must still work (never raise "Unknown model name"), and must
        # route to the SAME real, verified model as "groq_judge" rather than
        # the old nonexistent "llama-3.3-70b-versatile".
        from llm.llm_client import KidsNutriLLMClient
        client = KidsNutriLLMClient()
        with patch.object(client, "_call_groq", return_value="judge json") as m_groq:
            text, _ = client.generate_response("s", "u", model_name="groq_llama70b")
        self.assertEqual(text, "judge json")
        m_groq.assert_called_once_with("openai/gpt-oss-120b", "s", "u")

    def test_gemini_remains_selectable_as_an_alternative_judge_backend(self):
        from llm.llm_client import KidsNutriLLMClient
        client = KidsNutriLLMClient()
        client.gemini_key = "fake-key-for-test"
        with patch.object(client, "_call_gemini", return_value="judge json") as m_gemini:
            text, _ = client.generate_response("s", "u", model_name="gemini")
        self.assertEqual(text, "judge json")
        m_gemini.assert_called_once()

    def test_default_judges_constructed_by_evaluator_use_groq_when_unspecified(self):
        from evaluation.evaluator import KidsNutriEvaluator
        mock_client = MagicMock()
        mock_retriever = MagicMock()
        mock_planner = MagicMock()
        evaluator = KidsNutriEvaluator(mock_client, mock_retriever, mock_planner)
        for judge in evaluator.judges.values():
            self.assertEqual(judge.model_name, "groq_judge")


if __name__ == "__main__":
    unittest.main()
