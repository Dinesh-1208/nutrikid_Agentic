import json
import unittest
from unittest.mock import MagicMock, patch

from evaluation.judges.base_judge import BaseJudge, safe_parse_json
from llm.llm_client import KidsNutriLLMClient

# ============================================================================
# STATIC / UNIT TESTS ONLY.
#
# No GROQ_API_KEY or GEMINI_API_KEY is present in this environment (verified
# this session), and neither the `groq` SDK nor the `google.generativeai` SDK
# is exercised against a real network endpoint anywhere in this file. Every
# test below mocks KidsNutriLLMClient.generate_response (or the underlying
# SDK client objects) directly. This file makes NO claim about live Groq/
# Gemini API behavior - see docs/evaluation/phase3_llm_judge_audit.md section
# 18 for the explicit static-vs-live distinction and why live verification
# could not be performed this session.
# ============================================================================


def _silence_sleep():
    """time.sleep is patched to a no-op in every test below so retry/backoff
    tests run instantly instead of actually waiting 1s/2s/4s/12s etc."""
    return patch("time.sleep", return_value=None)


class TestSafeParseJson(unittest.TestCase):
    def test_plain_json_object(self):
        result = safe_parse_json('{"a": 1, "b": "x"}')
        self.assertEqual(result, {"a": 1, "b": "x"})

    def test_json_wrapped_in_markdown_fence(self):
        result = safe_parse_json('Here you go:\n```json\n{"a": 1}\n```\nDone.')
        self.assertEqual(result, {"a": 1})

    def test_json_array_extracted_from_surrounding_text(self):
        result = safe_parse_json('The answer is [{"x": 1}, {"x": 2}] as requested.')
        self.assertEqual(result, [{"x": 1}, {"x": 2}])

    def test_unrepairable_garbage_returns_parse_failed_not_exception(self):
        result = safe_parse_json("This is not JSON at all, just prose.")
        self.assertEqual(result, {"parse_failed": True})

    def test_repair_logic_fixes_unescaped_inner_quotes_in_known_key(self):
        # A common real-world LLM output pattern: an unescaped quote inside a
        # "reasoning"/"claim" string value breaks strict json.loads.
        broken = '{"reasoning": "The child said "no thanks" and refused", "diagnosis": false}'
        result = safe_parse_json(broken)
        self.assertNotIn("parse_failed", result)
        self.assertIn("no thanks", result["reasoning"])


class TestBaseJudgeRetryAndFailureHandling(unittest.TestCase):
    """Covers the shared retry/parsing wrapper used identically by every
    judge regardless of backend (Groq or Gemini) - see phase3 audit section
    9 (failure handling) and section 6 (Groq/Gemini interface compatibility:
    this wrapper is exactly the mechanism that makes both backends compatible
    with the same judge interfaces)."""

    def _make_judge(self, model_name="groq_judge"):
        client = MagicMock()
        client.gemini_key = "fake-key-for-non-gemini-tests"
        judge = BaseJudge(client, model_name=model_name)
        return judge, client

    def test_successful_call_returns_parsed_json_on_first_attempt(self):
        judge, client = self._make_judge()
        client.generate_response.return_value = ('{"relevance_map": []}', 0.1)

        result = judge.call_llm_with_retry("some prompt")

        self.assertEqual(result, {"relevance_map": []})
        self.assertEqual(client.generate_response.call_count, 1)

    def test_malformed_json_exhausts_retries_and_returns_parse_failed_not_a_fake_zero(self):
        judge, client = self._make_judge()
        client.generate_response.return_value = ("not json, just prose", 0.1)

        with _silence_sleep():
            result = judge.call_llm_with_retry("some prompt", max_retries=3)

        # This is the critical failure-handling contract: a judge that never
        # produced usable structured output must surface as parse_failed=True
        # (which every metric's evaluation_failed=... plumbing turns into an
        # EVALUATION_FAILURE status), never as an empty dict or a 0.0 score.
        self.assertTrue(result.get("parse_failed"))
        self.assertEqual(client.generate_response.call_count, 3)

    def test_transient_failure_then_success_recovers_within_retry_budget(self):
        judge, client = self._make_judge()
        client.generate_response.side_effect = [
            RuntimeError("simulated transient API/network error"),
            ('{"claims": [{"claim": "x", "is_supported": true}]}', 0.1),
        ]

        with _silence_sleep():
            result = judge.call_llm_with_retry("some prompt", max_retries=3)

        self.assertNotIn("parse_failed", result)
        self.assertEqual(result["claims"][0]["is_supported"], True)
        self.assertEqual(client.generate_response.call_count, 2)

    def test_empty_response_is_treated_as_a_failure_not_a_silent_empty_success(self):
        judge, client = self._make_judge()
        client.generate_response.return_value = ("   ", 0.1)

        with _silence_sleep():
            result = judge.call_llm_with_retry("some prompt", max_retries=2)

        self.assertTrue(result.get("parse_failed"))

    def test_gemini_without_api_key_fails_fast_with_explicit_error_not_silent_zero(self):
        client = MagicMock()
        client.gemini_key = None  # simulates GEMINI_API_KEY missing from environment
        judge = BaseJudge(client, model_name="gemini")

        with self.assertRaises(ValueError):
            judge.call_llm_with_retry("some prompt")
        # Must fail loudly before ever attempting a network call.
        client.generate_response.assert_not_called()

    def test_exception_message_from_a_missing_groq_credential_eventually_surfaces_as_parse_failed(self):
        # Unlike the Gemini path, BaseJudge has no equivalent up-front check for
        # Groq - a missing GROQ_API_KEY only surfaces once _call_groq actually
        # raises inside the retry loop. This test documents that current
        # behavior (3 wasted retry attempts on a condition retrying cannot
        # fix) rather than asserting it is ideal - see phase3 audit "Problems
        # Found" for the recommendation to add a symmetric up-front check.
        judge, client = self._make_judge(model_name="groq_judge")
        client.generate_response.side_effect = ValueError("GROQ_API_KEY is not set. Please set it in your environment.")

        with _silence_sleep():
            result = judge.call_llm_with_retry("some prompt", max_retries=3)

        self.assertTrue(result.get("parse_failed"))
        self.assertIn("GROQ_API_KEY", result.get("error", ""))
        self.assertEqual(client.generate_response.call_count, 3)

    def test_daily_quota_exhaustion_fails_fast_without_burning_all_retries(self):
        # Phase 4F: a Groq TPD (tokens-per-day) exhaustion error cannot be
        # fixed by waiting a few seconds and retrying within the same run -
        # unlike a transient/per-minute throttle, it should fail fast rather
        # than spend max_retries-1 more requests and backoff time on a
        # condition retrying cannot resolve. The eventual failure must still
        # be a normal parse_failed=True result, never a fake success/zero.
        judge, client = self._make_judge()
        client.generate_response.side_effect = RuntimeError(
            "Error code: 429 - Rate limit reached for model 'openai/gpt-oss-120b' "
            "on tokens per day (TPD): Limit 200000, Used 199649, Requested 1422."
        )

        with _silence_sleep():
            result = judge.call_llm_with_retry("some prompt", max_retries=3)

        self.assertTrue(result.get("parse_failed"))
        self.assertEqual(result.get("error_class"), "daily_quota_exhausted")
        # Only 1 attempt should have been made - retrying a daily-exhausted
        # quota within the same run cannot help, so the other 2 of the normal
        # 3 retry attempts must be skipped, not wasted.
        self.assertEqual(client.generate_response.call_count, 1)

    def test_transient_rate_limit_still_uses_normal_backoff_retry(self):
        # A per-minute/short-window 429 (no "per day"/"TPD" phrase) is exactly
        # the case exponential backoff exists for, and must still recover
        # within the retry budget like any other transient failure.
        judge, client = self._make_judge()
        client.generate_response.side_effect = [
            RuntimeError("Error code: 429 - Rate limit reached. Please try again in 2.1s."),
            ('{"relevance_map": []}', 0.1),
        ]

        with _silence_sleep():
            result = judge.call_llm_with_retry("some prompt", max_retries=3)

        self.assertNotIn("parse_failed", result)
        self.assertEqual(client.generate_response.call_count, 2)


class TestLlmClientBackendRouting(unittest.TestCase):
    """Confirms model_name dispatch never conflates the production answer
    backend (qwen_local) with a judge backend (groq_*, gemini) - phase3 audit
    section 3."""

    def test_qwen_local_routes_to_local_transformers_not_any_judge_backend(self):
        # generate_response's qwen_local branch checks torch.cuda.is_available()
        # itself before dispatching (a deliberate "abort if hardware is missing"
        # guard - see llm/llm_client.py's own comment). Patch that guard so the
        # test exercises routing, not this sandbox's real lack of a GPU.
        client = KidsNutriLLMClient()
        import torch
        with patch.object(client, "_call_local_transformers", return_value="local answer") as m_local, \
             patch.object(client, "_call_groq") as m_groq, \
             patch.object(client, "_call_gemini") as m_gemini, \
             patch.object(torch.cuda, "is_available", return_value=True):
            text, _ = client.generate_response("sys", "usr", model_name="qwen_local")
        self.assertEqual(text, "local answer")
        m_local.assert_called_once()
        m_groq.assert_not_called()
        m_gemini.assert_not_called()

    def test_judge_model_name_groq_judge_routes_to_groq_with_verified_model_id(self):
        # Phase 4F: "groq_judge" is now the project's one clear default judge
        # name, and must route to a model with direct evidence of being
        # available in the account's live Groq catalog (see
        # docs/phase4f_groq_judge_configuration.md), not the fictional
        # "llama-3.3-70b-versatile" the old "groq_llama70b" name pointed to.
        client = KidsNutriLLMClient()
        with patch.object(client, "_call_groq", return_value="judge json") as m_groq, \
             patch.object(client, "_call_local_transformers") as m_local:
            text, _ = client.generate_response("sys", "usr", model_name="groq_judge")
        self.assertEqual(text, "judge json")
        m_groq.assert_called_once_with("openai/gpt-oss-120b", "sys", "usr")
        m_local.assert_not_called()

    def test_judge_model_name_groq_llama70b_routes_as_deprecated_alias_to_same_verified_model(self):
        # The old name must keep working (backward compatibility for any
        # external script/notebook still using it) but must route to the SAME
        # real model as "groq_judge" - never the old nonexistent
        # "llama-3.3-70b-versatile".
        client = KidsNutriLLMClient()
        with patch.object(client, "_call_groq", return_value="judge json") as m_groq, \
             patch.object(client, "_call_local_transformers") as m_local:
            text, _ = client.generate_response("sys", "usr", model_name="groq_llama70b")
        self.assertEqual(text, "judge json")
        m_groq.assert_called_once_with("openai/gpt-oss-120b", "sys", "usr")
        m_local.assert_not_called()

    def test_judge_model_name_groq_llama8b_routes_to_a_verified_model_id(self):
        # Phase 4F: "llama-3.1-8b-instant" was also not in the account's live
        # Groq catalog, so this was remapped to the verified-available
        # "openai/gpt-oss-20b" alongside the "groq_judge" default fix.
        client = KidsNutriLLMClient()
        with patch.object(client, "_call_groq", return_value="judge json") as m_groq, \
             patch.object(client, "_call_local_transformers") as m_local:
            text, _ = client.generate_response("sys", "usr", model_name="groq_llama8b")
        self.assertEqual(text, "judge json")
        m_groq.assert_called_once_with("openai/gpt-oss-20b", "sys", "usr")
        m_local.assert_not_called()

    def test_judge_model_name_gemini_routes_to_gemini_only(self):
        client = KidsNutriLLMClient()
        client.gemini_key = "fake-key-for-test"  # generate_response's gemini branch requires this to be set
        with patch.object(client, "_call_gemini", return_value="judge json") as m_gemini, \
             patch.object(client, "_call_groq") as m_groq, \
             patch.object(client, "_call_local_transformers") as m_local:
            text, _ = client.generate_response("sys", "usr", model_name="gemini")
        self.assertEqual(text, "judge json")
        m_gemini.assert_called_once()
        m_groq.assert_not_called()
        m_local.assert_not_called()

    def test_unknown_model_name_raises_rather_than_silently_falling_back(self):
        client = KidsNutriLLMClient()
        with self.assertRaises(ValueError):
            client.generate_response("sys", "usr", model_name="not_a_real_model")


class TestGroqClientCallShape(unittest.TestCase):
    """Static verification of the Groq SDK call shape - mocked, no network."""

    def test_generate_response_calls_chat_completions_create_with_expected_args(self):
        from llm.groq_client import KidsNutriGroqClient

        with patch("llm.groq_client.Groq") as MockGroq:
            mock_client_instance = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(content='{"ok": true}'))]
            mock_client_instance.chat.completions.create.return_value = mock_response
            MockGroq.return_value = mock_client_instance

            with patch.dict("os.environ", {"GROQ_API_KEY": "fake-key-for-test"}):
                gc = KidsNutriGroqClient()
                result = gc.generate_response(
                    model_id="llama-3.3-70b-versatile",
                    system_prompt="sys",
                    user_prompt="usr",
                    temperature=0.1,
                    top_p=0.9,
                    max_tokens=1024,
                )

        self.assertEqual(result, '{"ok": true}')
        mock_client_instance.chat.completions.create.assert_called_once_with(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": "sys"}, {"role": "user", "content": "usr"}],
            temperature=0.1,
            top_p=0.9,
            max_tokens=1024,
        )

    def test_missing_api_key_raises_before_any_network_call(self):
        from llm.groq_client import KidsNutriGroqClient

        with patch.dict("os.environ", {}, clear=True):
            gc = KidsNutriGroqClient()
            with self.assertRaises(ValueError):
                gc.generate_response(model_id="llama-3.3-70b-versatile", system_prompt="s", user_prompt="u")


class TestGeminiRetryBehavior(unittest.TestCase):
    """Static verification of Gemini's own internal rate-limit retry loop in
    llm/llm_client.py::_call_gemini - separate from BaseJudge's outer retry
    loop. See phase3 audit section 6 for why these two loops can compound."""

    def test_rate_limit_error_retries_then_succeeds(self):
        client = KidsNutriLLMClient()
        client.gemini_key = "fake-key-for-test"

        mock_model = MagicMock()
        rate_limit_error = Exception("429 ResourceExhausted: quota exceeded")
        success_response = MagicMock(text="gemini judge output")
        mock_model.generate_content.side_effect = [rate_limit_error, success_response]

        with patch("llm.llm_client.genai") as mock_genai:
            mock_genai.GenerativeModel.return_value = mock_model
            mock_genai.types.GenerationConfig.return_value = MagicMock()
            with _silence_sleep():
                result = client._call_gemini("sys", "usr")

        self.assertEqual(result, "gemini judge output")
        self.assertEqual(mock_model.generate_content.call_count, 2)

    def test_non_rate_limit_error_raises_immediately_without_retry(self):
        client = KidsNutriLLMClient()
        client.gemini_key = "fake-key-for-test"

        mock_model = MagicMock()
        mock_model.generate_content.side_effect = ValueError("some unrelated error")

        with patch("llm.llm_client.genai") as mock_genai:
            mock_genai.GenerativeModel.return_value = mock_model
            mock_genai.types.GenerationConfig.return_value = MagicMock()
            with self.assertRaises(ValueError):
                client._call_gemini("sys", "usr")

        self.assertEqual(mock_model.generate_content.call_count, 1)


class TestGoldDataLeakageInJudgeAndPromptConstruction(unittest.TestCase):
    """Directly proves the four forbidden gold fields never reach a prompt
    string or a judge call - phase3 audit section 8."""

    FORBIDDEN_MARKERS = [
        "RAG_MARKER_SHOULD_NEVER_LEAK",
        "GOLD_FACT_SHOULD_NEVER_LEAK",
        "REFERENCE_ANSWER_SHOULD_NEVER_LEAK",
    ]

    def test_generate_llm_prompt_never_includes_gold_fields(self):
        from llm.prompt_templates import generate_llm_prompt

        plan = {
            "profile": {"age": 5, "weight_kg": 18, "goal": "balanced_nutrition", "condition": "healthy_growth", "allergies": []},
            "targets": {"calories_kcal": 1400},
            "totals": {"calories_kcal": 1390, "protein_g": 40, "fat_g": 30, "carbs_g": 180, "iron_mg": 8},
            "meal_plan": {"breakfast": [{"food_name": "oats", "category": "carb", "portion_size_g": 50, "calories_kcal": 200, "protein_g": 5, "iron_mg": 1}]},
        }
        retrieved_contexts = [{"id": "RAG_GUIDELINE_1", "text": "A balanced meal includes cereals and pulses.", "score": 0.9}]

        # generate_llm_prompt's signature structurally cannot accept gold
        # fields at all (it only takes plan, rag_context, query) - this test
        # documents that guarantee rather than merely asserting string absence.
        system_prompt, user_prompt = generate_llm_prompt(plan, retrieved_contexts, query="Is this food safe?")

        for marker in self.FORBIDDEN_MARKERS:
            self.assertNotIn(marker, system_prompt)
            self.assertNotIn(marker, user_prompt)

    def test_evaluator_never_passes_gold_fields_into_any_judge_call(self):
        from evaluation.evaluator import KidsNutriEvaluator

        # Note on gold_facts specifically: unlike relevant_chunk_ids,
        # reference_answer, and safety_ground_truth (which no judge or metric
        # ever needs to see), gold_facts' fact_text is BY DESIGN passed to
        # ContextJudge.evaluate_recall as the reference material Context
        # Recall is computed against (see evaluator.py's gold_facts ->
        # expected_context mapping, Phase 4B). That is the metric doing its
        # job, not a leak - only the CONTEXT judge may see it, and only the
        # plain fact_text string, never the raw fact dict's
        # fact_id/source_reference/chunk_reference/importance metadata. This
        # test asserts that precise boundary rather than a blanket "never
        # anywhere" rule.
        gold_fact_marker = "GOLD_FACT_TEXT_EXPECTED_ONLY_IN_CONTEXT_JUDGE_RECALL_CALL"
        test_case = {
            "id": "EVAL_TEST",
            "category": "Allergies & Intolerances",
            "question": "What foods should I avoid for a nut allergy?",
            "profile": {"age": 4, "allergies": ["nut_allergy"]},
            "relevant_chunk_ids": ["GOLD_FACT_SHOULD_NEVER_LEAK"],
            "gold_facts": [{"fact_id": "GF_1", "fact_text": gold_fact_marker}],
            "reference_answer": "RAG_MARKER_SHOULD_NEVER_LEAK",
            "safety_ground_truth": {"overall": "Compliant", "diagnosis": False, "prescription": False, "allergy_violation": False, "age_violation": False},
        }

        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = [{"id": "RAG_1", "source_id": "RAG_1", "text": "avoid nuts", "score": 0.5}]
        mock_planner = MagicMock()
        mock_planner.generate_meal_plan.return_value = {
            "profile": {"age": 4, "weight_kg": 15, "goal": "balanced_nutrition", "condition": "child_above_1_year", "allergies": ["nut_allergy"]},
            "targets": {"calories_kcal": 1200}, "totals": {"calories_kcal": 1200, "protein_g": 30, "fat_g": 30, "carbs_g": 150, "iron_mg": 6},
            "meal_plan": {},
        }
        mock_llm_client = MagicMock()
        mock_llm_client.generate_response.return_value = ("Avoid nuts and nut products.", 0.2)

        mock_judges = {
            "context": MagicMock(),
            "grounding": MagicMock(),
            "relevancy": MagicMock(),
            "safety": MagicMock(),
        }
        mock_judges["context"].evaluate_precision.return_value = {"relevance_map": []}
        mock_judges["context"].evaluate_recall.return_value = {"facts": []}
        mock_judges["grounding"].evaluate_grounding.return_value = {"claims": []}
        mock_judges["relevancy"].generate_hypothetical_questions.return_value = {"generated_questions": []}
        mock_judges["safety"].evaluate_safety.return_value = {"overall": "Compliant", "diagnosis": False, "prescription": False, "allergy_violation": False, "age_violation": False}

        evaluator = KidsNutriEvaluator(mock_llm_client, mock_retriever, mock_planner, judges=mock_judges)
        evaluator.run_single_evaluation(test_case, "qwen_local")

        # The production answer call must never see any forbidden marker,
        # including the gold_facts marker - only ContextJudge may see that.
        prod_call_args = mock_llm_client.generate_response.call_args
        for marker in self.FORBIDDEN_MARKERS + [gold_fact_marker]:
            self.assertNotIn(marker, str(prod_call_args))

        # The always-forbidden markers (relevant_chunk_ids, reference_answer)
        # must never appear in ANY judge call.
        for name, judge_mock in mock_judges.items():
            for call in judge_mock.mock_calls:
                call_str = str(call)
                for marker in self.FORBIDDEN_MARKERS:
                    self.assertNotIn(marker, call_str, f"Leakage found in {name} judge call: {call}")

        # The gold_facts marker must appear ONLY in the context judge's
        # evaluate_recall call, as a plain string within the expected_context
        # list, and nowhere else.
        context_calls = str(mock_judges["context"].mock_calls)
        self.assertIn(gold_fact_marker, context_calls)
        self.assertIn("evaluate_recall", context_calls)
        for name in ("grounding", "relevancy", "safety"):
            self.assertNotIn(gold_fact_marker, str(mock_judges[name].mock_calls))
        # And never the raw fact dict shape (fact_id/etc.) - only fact_text.
        self.assertNotIn("fact_id", context_calls)
        self.assertNotIn("GF_1", context_calls)


class TestEvaluatorFailureStatusPropagation(unittest.TestCase):
    """Confirms a judge exception produces EVALUATION_FAILURE-shaped statuses,
    never a numeric 0.0 masquerading as a real measurement - phase3 audit
    section 9, exercised through the real evaluator.py (not just the metric
    functions in isolation, which are already covered by other test files)."""

    def _build_evaluator_with_raising_judges(self):
        from evaluation.evaluator import KidsNutriEvaluator

        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = [{"id": "RAG_1", "source_id": "RAG_1", "text": "x", "score": 0.1}]
        mock_planner = MagicMock()
        mock_planner.generate_meal_plan.return_value = {
            "profile": {"age": 4, "weight_kg": 15, "goal": "g", "condition": "c", "allergies": []},
            "targets": {"calories_kcal": 1200}, "totals": {"calories_kcal": 1200, "protein_g": 30, "fat_g": 30, "carbs_g": 150, "iron_mg": 6},
            "meal_plan": {},
        }
        mock_llm_client = MagicMock()
        mock_llm_client.generate_response.return_value = ("some answer", 0.1)

        mock_judges = {
            "context": MagicMock(),
            "grounding": MagicMock(),
            "relevancy": MagicMock(),
            "safety": MagicMock(),
        }
        # Simulate every judge failing outright (e.g. both backends down).
        mock_judges["context"].evaluate_precision.side_effect = RuntimeError("API down")
        mock_judges["context"].evaluate_recall.side_effect = RuntimeError("API down")
        mock_judges["grounding"].evaluate_grounding.side_effect = RuntimeError("API down")
        mock_judges["relevancy"].generate_hypothetical_questions.side_effect = RuntimeError("API down")
        mock_judges["safety"].evaluate_safety.side_effect = RuntimeError("API down")

        evaluator = KidsNutriEvaluator(mock_llm_client, mock_retriever, mock_planner, judges=mock_judges)
        return evaluator

    def test_total_judge_outage_yields_evaluation_failure_not_fake_zero(self):
        evaluator = self._build_evaluator_with_raising_judges()
        # relevant_chunk_ids is explicitly set (RAG-applicable) so this test
        # verifies the outage-vs-fake-zero invariant in isolation, without the
        # separate non-RAG-applicability gate (test_context_recall.py's
        # TestContextRecallEvaluatorIntegration.test_case_c_... covers that
        # dimension) being a confound.
        test_case = {
            "id": "T1", "category": "General Nutrition & Nutrients", "question": "q",
            "profile": {"age": 5}, "relevant_chunk_ids": ["X"],
        }

        result = evaluator.run_single_evaluation(test_case, "qwen_local")

        self.assertEqual(result["faithfulness_status"], "EVALUATION_FAILURE")
        self.assertIsNone(result["faithfulness"])
        self.assertEqual(result["unsupported_claim_rate_status"], "EVALUATION_FAILURE")
        self.assertIsNone(result["unsupported_claim_rate"])
        self.assertIsNone(result["is_hallucinated"])
        self.assertEqual(result["answer_relevancy_status"], "EVALUATION_FAILURE")
        self.assertIsNone(result["answer_relevancy"])
        # Phase 4E root-cause fix (docs/phase4e_context_recall_fix.md):
        # context_recall now has the same status-enum layer as every sibling
        # metric (the gap the old comment here documented is fixed, not just
        # noted) - a total judge outage must report EVALUATION_FAILURE with
        # score=None, never a fake real 0.0.
        self.assertEqual(result["context_recall_status"], "EVALUATION_FAILURE")
        self.assertIsNone(result["context_recall"])
        self.assertNotEqual(result["context_recall"], 0.0)


if __name__ == "__main__":
    unittest.main()
