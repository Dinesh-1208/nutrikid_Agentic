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

    def test_transient_rate_limit_still_recovers_within_the_retry_budget(self):
        # A per-minute/short-window 429 (no "per day"/"TPD" phrase) must still
        # recover within the retry budget like any other transient failure -
        # it should not be treated as unrecoverable.
        judge, client = self._make_judge()
        client.generate_response.side_effect = [
            RuntimeError("Error code: 429 - Rate limit reached. Please try again in 2.1s."),
            ('{"relevance_map": []}', 0.1),
        ]

        with _silence_sleep():
            result = judge.call_llm_with_retry("some prompt", max_retries=3)

        self.assertNotIn("parse_failed", result)
        self.assertEqual(client.generate_response.call_count, 2)

    def test_transient_rate_limit_uses_a_much_longer_backoff_than_a_generic_failure(self):
        # Live evidence (a real Kaggle run against a Groq account with an
        # 8,000 TPM limit) showed the previous 1s/2s exponential backoff never
        # gave a per-minute throttle window any real chance to clear before
        # retries were exhausted. rate_limited_transient/empty_response must
        # now use a much longer backoff (20s, 40s) than a generic failure
        # (1s, 2s) - verified here by asserting the actual sleep durations,
        # not just that some retry happened.
        judge, client = self._make_judge()
        client.generate_response.side_effect = [
            RuntimeError("Error code: 429 - Rate limit reached. Please try again in 2.1s."),
            RuntimeError("Error code: 429 - Rate limit reached. Please try again in 2.1s."),
            ('{"relevance_map": []}', 0.1),
        ]

        with patch("time.sleep") as mock_sleep:
            result = judge.call_llm_with_retry("some prompt", max_retries=3)

        self.assertNotIn("parse_failed", result)
        mock_sleep.assert_any_call(20)
        mock_sleep.assert_any_call(40)

    def test_empty_response_is_classified_distinctly_and_uses_the_longer_backoff(self):
        # "Received empty response from API." is raised internally (not by
        # the provider SDK) and was previously lumped into the generic
        # 'other' bucket with a short 1s/2s backoff. Live evidence showed it
        # clustering with explicit TPM 429s on the same throttled account, so
        # it now gets the same longer backoff treatment as
        # rate_limited_transient.
        judge, client = self._make_judge()
        client.generate_response.side_effect = [
            ("   ", 0.1),  # blank -> triggers "Received empty response from API."
            ('{"relevance_map": []}', 0.1),
        ]

        with patch("time.sleep") as mock_sleep:
            result = judge.call_llm_with_retry("some prompt", max_retries=3)

        self.assertNotIn("parse_failed", result)
        mock_sleep.assert_called_once_with(20)

    def test_malformed_json_still_uses_the_short_backoff_not_the_long_one(self):
        # A persistently malformed response is not resource-recovery-
        # dependent - waiting longer would not improve the odds of success -
        # so it must keep the original short 1s/2s schedule, not the longer
        # rate-limit-oriented one.
        judge, client = self._make_judge()
        client.generate_response.return_value = ("not json, just prose", 0.1)

        with patch("time.sleep") as mock_sleep:
            judge.call_llm_with_retry("some prompt", max_retries=3)

        mock_sleep.assert_any_call(1)
        mock_sleep.assert_any_call(2)

    def test_auth_permission_failure_fails_fast_via_typed_exception(self):
        # A provider SDK's own typed exception (e.g. an
        # AuthenticationError/PermissionDeniedError) must fail fast, since
        # retrying with the same invalid/unauthorized credential cannot
        # succeed within this run.
        class PermissionDeniedError(Exception):
            pass

        judge, client = self._make_judge()
        client.generate_response.side_effect = PermissionDeniedError("403 - caller does not have permission")

        with _silence_sleep():
            result = judge.call_llm_with_retry("some prompt", max_retries=3)

        self.assertTrue(result.get("parse_failed"))
        self.assertEqual(result.get("error_class"), "auth_permission_failure")
        self.assertEqual(client.generate_response.call_count, 1)

    def test_auth_permission_failure_fails_fast_via_string_match_fallback(self):
        # Same contract as above, but for a provider (e.g. Groq, Gemini) whose
        # error surfaces as a generic exception type with a 401/403/
        # "permission" phrase in the message rather than a typed exception.
        judge, client = self._make_judge()
        client.generate_response.side_effect = RuntimeError(
            "Error code: 401 - Unauthorized: invalid API key provided"
        )

        with _silence_sleep():
            result = judge.call_llm_with_retry("some prompt", max_retries=3)

        self.assertTrue(result.get("parse_failed"))
        self.assertEqual(result.get("error_class"), "auth_permission_failure")
        self.assertEqual(client.generate_response.call_count, 1)


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

    def test_first_call_is_never_paced(self):
        # No prior call has happened yet, so there is nothing to pace against -
        # the first call in a run must not be delayed.
        from llm.groq_client import KidsNutriGroqClient

        with patch("llm.groq_client.Groq") as MockGroq:
            mock_client_instance = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(content='{"ok": true}'))]
            mock_client_instance.chat.completions.create.return_value = mock_response
            MockGroq.return_value = mock_client_instance

            with patch.dict("os.environ", {"GROQ_API_KEY": "fake-key-for-test"}), \
                 patch("llm.groq_client.time.sleep") as mock_sleep:
                gc = KidsNutriGroqClient()
                gc.generate_response(model_id="m", system_prompt="s", user_prompt="u")

        mock_sleep.assert_not_called()

    def test_second_call_within_the_pacing_window_is_delayed(self):
        # Added after a real Kaggle run against a Groq account with an 8,000
        # TPM limit (see base_judge.py's _classify_api_error docstring for
        # the live evidence). A second call made immediately after the first
        # must be delayed by roughly the configured minimum interval, so the
        # project's 5-calls-per-case judge sequence cannot burst straight
        # through the account's real per-minute budget.
        from llm.groq_client import KidsNutriGroqClient

        with patch("llm.groq_client.Groq") as MockGroq:
            mock_client_instance = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(content='{"ok": true}'))]
            mock_client_instance.chat.completions.create.return_value = mock_response
            MockGroq.return_value = mock_client_instance

            with patch.dict("os.environ", {"GROQ_API_KEY": "fake-key-for-test", "GROQ_MIN_CALL_INTERVAL_SECONDS": "8"}), \
                 patch("llm.groq_client.time.sleep") as mock_sleep:
                gc = KidsNutriGroqClient()
                gc.generate_response(model_id="m", system_prompt="s", user_prompt="u")
                gc.generate_response(model_id="m", system_prompt="s", user_prompt="u")

        mock_sleep.assert_called_once()
        # Should be close to the configured 8s window (allow slack for the
        # negligible real time elapsed between the two mocked calls above).
        slept_seconds = mock_sleep.call_args[0][0]
        self.assertGreater(slept_seconds, 7.0)
        self.assertLessEqual(slept_seconds, 8.0)

    def test_pacing_can_be_disabled_via_zero_interval(self):
        from llm.groq_client import KidsNutriGroqClient

        with patch("llm.groq_client.Groq") as MockGroq:
            mock_client_instance = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(content='{"ok": true}'))]
            mock_client_instance.chat.completions.create.return_value = mock_response
            MockGroq.return_value = mock_client_instance

            with patch.dict("os.environ", {"GROQ_API_KEY": "fake-key-for-test", "GROQ_MIN_CALL_INTERVAL_SECONDS": "0"}), \
                 patch("llm.groq_client.time.sleep") as mock_sleep:
                gc = KidsNutriGroqClient()
                gc.generate_response(model_id="m", system_prompt="s", user_prompt="u")
                gc.generate_response(model_id="m", system_prompt="s", user_prompt="u")

        mock_sleep.assert_not_called()

    def _mock_groq_returning(self, content):
        MockGroq_patch = patch("llm.groq_client.Groq")
        MockGroq = MockGroq_patch.start()
        self.addCleanup(MockGroq_patch.stop)
        mock_client_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=content))]
        mock_client_instance.chat.completions.create.return_value = mock_response
        MockGroq.return_value = mock_client_instance
        return mock_client_instance

    def test_gpt_oss_model_gets_low_reasoning_effort_and_hidden_reasoning_format_by_default(self):
        # Root cause fix: a live direct test against openai/gpt-oss-120b
        # proved the model's internal reasoning tokens share the completion
        # budget with the visible answer (completion_tokens=20,
        # reasoning_tokens=18, empty content). "low" effort + hidden format
        # keeps more of the budget for the actual JSON and keeps content
        # free of any leaked reasoning trace.
        from llm.groq_client import KidsNutriGroqClient

        mock_client_instance = self._mock_groq_returning('{"ok": true}')
        with patch.dict("os.environ", {"GROQ_API_KEY": "fake-key-for-test"}, clear=False):
            gc = KidsNutriGroqClient()
            gc.generate_response(model_id="openai/gpt-oss-120b", system_prompt="s", user_prompt="u")

        call_kwargs = mock_client_instance.chat.completions.create.call_args.kwargs
        self.assertEqual(call_kwargs["reasoning_effort"], "low")
        self.assertEqual(call_kwargs["reasoning_format"], "hidden")

    def test_gpt_oss_model_uses_the_larger_2048_judge_completion_budget_by_default(self):
        # Previously this silently reused self.gen_config["max_new_tokens"]
        # (1024, shared with local Transformers generation) - now Groq judge
        # calls get their own dedicated, larger budget sized to cover both
        # reasoning tokens and the largest judge schema (GroundingJudge).
        from llm.groq_client import KidsNutriGroqClient

        mock_client_instance = self._mock_groq_returning('{"ok": true}')
        with patch.dict("os.environ", {"GROQ_API_KEY": "fake-key-for-test"}, clear=False):
            gc = KidsNutriGroqClient()
            gc.generate_response(model_id="openai/gpt-oss-120b", system_prompt="s", user_prompt="u")

        call_kwargs = mock_client_instance.chat.completions.create.call_args.kwargs
        self.assertEqual(call_kwargs["max_tokens"], 2048)

    def test_explicit_max_tokens_overrides_the_judge_default(self):
        from llm.groq_client import KidsNutriGroqClient

        mock_client_instance = self._mock_groq_returning('{"ok": true}')
        with patch.dict("os.environ", {"GROQ_API_KEY": "fake-key-for-test"}, clear=False):
            gc = KidsNutriGroqClient()
            gc.generate_response(model_id="openai/gpt-oss-120b", system_prompt="s", user_prompt="u", max_tokens=4096)

        call_kwargs = mock_client_instance.chat.completions.create.call_args.kwargs
        self.assertEqual(call_kwargs["max_tokens"], 4096)

    def test_non_gpt_oss_model_does_not_receive_reasoning_params(self):
        # reasoning_effort/reasoning_format are GPT-OSS-specific controls -
        # sending them to an unrelated Groq model family (e.g. the optional
        # "groq_qwen" route) is not confirmed safe, so they must be omitted
        # entirely for any model_id outside the openai/gpt-oss-* family.
        from llm.groq_client import KidsNutriGroqClient

        mock_client_instance = self._mock_groq_returning('{"ok": true}')
        with patch.dict("os.environ", {"GROQ_API_KEY": "fake-key-for-test"}, clear=False):
            gc = KidsNutriGroqClient()
            gc.generate_response(model_id="qwen/qwen3.6-27b", system_prompt="s", user_prompt="u")

        call_kwargs = mock_client_instance.chat.completions.create.call_args.kwargs
        self.assertNotIn("reasoning_effort", call_kwargs)
        self.assertNotIn("reasoning_format", call_kwargs)
        # The larger completion budget is still safe and applied universally
        # (it is only a ceiling, not a fixed cost).
        self.assertEqual(call_kwargs["max_tokens"], 2048)

    def test_reasoning_effort_and_format_are_configurable_via_env_vars(self):
        from llm.groq_client import KidsNutriGroqClient

        mock_client_instance = self._mock_groq_returning('{"ok": true}')
        with patch.dict("os.environ", {
            "GROQ_API_KEY": "fake-key-for-test",
            "GROQ_JUDGE_REASONING_EFFORT": "medium",
            "GROQ_JUDGE_REASONING_FORMAT": "parsed",
            "GROQ_JUDGE_MAX_COMPLETION_TOKENS": "3000",
        }, clear=False):
            gc = KidsNutriGroqClient()
            gc.generate_response(model_id="openai/gpt-oss-120b", system_prompt="s", user_prompt="u")

        call_kwargs = mock_client_instance.chat.completions.create.call_args.kwargs
        self.assertEqual(call_kwargs["reasoning_effort"], "medium")
        self.assertEqual(call_kwargs["reasoning_format"], "parsed")
        self.assertEqual(call_kwargs["max_tokens"], 3000)

    def test_call_groq_no_longer_hardwires_the_local_generation_token_budget(self):
        # _call_groq (llm_client.py) must not pass
        # max_tokens=self.gen_config["max_new_tokens"] any more - that
        # setting is for local Transformers generation and has no
        # relationship to Groq's reasoning-model token accounting. Letting
        # the call fall through to KidsNutriGroqClient's own judge default
        # (2048) is the fix.
        client = KidsNutriLLMClient()
        client.groq_client_instance = MagicMock()
        client.groq_client_instance.generate_response.return_value = '{"ok": true}'

        client._call_groq("openai/gpt-oss-120b", "sys", "usr")

        call_kwargs = client.groq_client_instance.generate_response.call_args.kwargs
        self.assertNotIn("max_tokens", call_kwargs)


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


class TestOptionalSafetyEvaluationSkip(unittest.TestCase):
    """run_safety_evaluation=False (evaluator.py): SafetyJudge must never be
    called, and the skip must surface as an explicit, honest status - never
    a fabricated Compliant/Refusal/Violation classification. Added after a
    real Kaggle run where all 20 safety-ground-truth cases were labeled
    "Compliant" (zero "Violation" cases), making Safety Recall/Precision/F1
    mathematically undefined (0/0) regardless of judge output - see
    comparator.py::compute_safety_metrics and its SAFETY_STATUS_SKIPPED
    tests in test_safety_ground_truth.py for the aggregate-level half of
    this fix."""

    def _build_evaluator(self, run_safety_evaluation):
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
        mock_llm_client.generate_response.return_value = ("some safe answer", 0.1)

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
        mock_judges["safety"].evaluate_safety.return_value = {"overall": "Compliant"}

        evaluator = KidsNutriEvaluator(
            mock_llm_client, mock_retriever, mock_planner,
            run_safety_evaluation=run_safety_evaluation, judges=mock_judges
        )
        return evaluator, mock_judges

    def test_disabled_safety_evaluation_never_calls_the_safety_judge(self):
        evaluator, mock_judges = self._build_evaluator(run_safety_evaluation=False)
        test_case = {
            "id": "T1", "category": "General Nutrition & Nutrients", "question": "q",
            "profile": {"age": 5}, "relevant_chunk_ids": ["X"],
        }

        result = evaluator.run_single_evaluation(test_case, "qwen_local")

        mock_judges["safety"].evaluate_safety.assert_not_called()
        self.assertEqual(result["safety_status"], "SKIPPED")
        # Must never be silently coerced into either a safe or unsafe
        # classification - "not evaluated" is its own explicit state.
        self.assertIsNone(result["is_safe"])
        self.assertEqual(result["violation_type"], "not_evaluated")
        self.assertTrue(result["safety_judge_raw"].get("skipped"))

    def test_default_still_calls_the_safety_judge_and_computes_a_real_classification(self):
        # Backward compatibility: omitting run_safety_evaluation (the
        # default) must behave exactly as before this change.
        evaluator, mock_judges = self._build_evaluator(run_safety_evaluation=True)
        test_case = {
            "id": "T1", "category": "General Nutrition & Nutrients", "question": "q",
            "profile": {"age": 5}, "relevant_chunk_ids": ["X"],
        }

        result = evaluator.run_single_evaluation(test_case, "qwen_local")

        mock_judges["safety"].evaluate_safety.assert_called_once()
        self.assertEqual(result["safety_status"], "EVALUATED")
        self.assertTrue(result["is_safe"])
        self.assertEqual(result["violation_type"], "none")


if __name__ == "__main__":
    unittest.main()
