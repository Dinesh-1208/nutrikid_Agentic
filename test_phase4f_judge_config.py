"""
Phase 4F regression tests: Groq judge model, quota, and evaluation-call
optimization (docs/phase4f_groq_judge_configuration.md).

Covers the specific things this phase changed and must not silently regress:
  1. Judge-model mapping - "groq_judge" is the one clear default, mapped to a
     model with direct evidence of being available in the account's live
     Groq catalog; "groq_llama70b" still works as a backward-compatible
     alias to the SAME model, never the old nonexistent
     "llama-3.3-70b-versatile".
  2. No hidden override - evaluator.py's constructor default, main.py's CLI
     default, and the notebook's JUDGE_MODEL variable must all agree with
     each other, with nothing silently overriding the default elsewhere.
  3. The unofficial retrieval-depth diagnostic is off by default and must be
     explicitly opted into.
  4. A judge-call failure (including a fast-failed daily-quota-exhaustion)
     must never surface as a fake success/score - see also test_context_recall.py
     and test_judge_architecture.py for the broader status-enum contract this
     phase deliberately preserved.
"""
import inspect
import json
import unittest
from unittest.mock import MagicMock, patch


class TestJudgeModelDefaultAgreesEverywhere(unittest.TestCase):
    """Item 12: the judge model default must agree across every place it is
    configured, with no hidden override."""

    EXPECTED_DEFAULT = "groq_judge"
    EXPECTED_REAL_MODEL_ID = "openai/gpt-oss-120b"

    def test_evaluator_constructor_default(self):
        from evaluation.evaluator import KidsNutriEvaluator
        sig = inspect.signature(KidsNutriEvaluator.__init__)
        self.assertEqual(sig.parameters["judge_model"].default, self.EXPECTED_DEFAULT)

    def test_main_cli_default(self):
        with open("main.py", encoding="utf-8") as f:
            src = f.read()
        self.assertIn(f'"--judge-model", type=str, default="{self.EXPECTED_DEFAULT}"', src)

    def test_notebook_judge_model_variable_matches(self):
        with open("KidsNutriBite_Evaluation.ipynb", encoding="utf-8") as f:
            nb = json.load(f)
        judge_model_lines = [
            line
            for cell in nb["cells"]
            if cell["cell_type"] == "code"
            for line in (cell["source"] if isinstance(cell["source"], list) else cell["source"].splitlines())
            if line.strip().startswith("JUDGE_MODEL =")
        ]
        self.assertEqual(len(judge_model_lines), 1, "Expected exactly one JUDGE_MODEL assignment in the notebook.")
        self.assertIn(f'"{self.EXPECTED_DEFAULT}"', judge_model_lines[0])

    def test_default_judge_model_name_routes_to_the_evidenced_real_model(self):
        from llm.llm_client import KidsNutriLLMClient
        client = KidsNutriLLMClient()
        with patch.object(client, "_call_groq", return_value="ok") as m_groq:
            client.generate_response("s", "u", model_name=self.EXPECTED_DEFAULT)
        m_groq.assert_called_once_with(self.EXPECTED_REAL_MODEL_ID, "s", "u")

    def test_deprecated_alias_routes_to_the_same_real_model_not_the_old_fictional_one(self):
        from llm.llm_client import KidsNutriLLMClient
        client = KidsNutriLLMClient()
        with patch.object(client, "_call_groq", return_value="ok") as m_groq:
            client.generate_response("s", "u", model_name="groq_llama70b")
        m_groq.assert_called_once_with(self.EXPECTED_REAL_MODEL_ID, "s", "u")
        # The specific regression this phase fixed: this name must never again
        # resolve to a model absent from the account's live catalog.
        called_model_id = m_groq.call_args[0][0]
        self.assertNotEqual(called_model_id, "llama-3.3-70b-versatile")

    def test_evaluator_judges_are_constructed_with_the_evaluator_supplied_model_not_a_hidden_default(self):
        # Guards against a judge silently ignoring judge_model and falling
        # back to its own internal default instead.
        from evaluation.evaluator import KidsNutriEvaluator
        mock_client, mock_retriever, mock_planner = MagicMock(), MagicMock(), MagicMock()
        evaluator = KidsNutriEvaluator(mock_client, mock_retriever, mock_planner, judge_model="gemini")
        for judge in evaluator.judges.values():
            self.assertEqual(judge.model_name, "gemini")


class TestUnofficialDiagnosticOffByDefault(unittest.TestCase):
    """Item 7/8: the unofficial LLM-judged retrieval-depth diagnostic must
    not run unless explicitly opted into."""

    def test_run_comparison_default_does_not_enable_diagnostic(self):
        from evaluation.comparator import KidsNutriComparator
        sig = inspect.signature(KidsNutriComparator.run_comparison)
        self.assertEqual(sig.parameters["run_diagnostic_experiment"].default, False)

    def test_diagnostic_call_site_is_source_level_gated_behind_the_flag(self):
        # A direct integration run through run_comparison's full body (report
        # generation, DataFrame aggregation, etc.) is out of scope for a unit
        # test and would require mocking most of comparator.py's internals -
        # instead, verify at the source level that the only call site for the
        # diagnostic is guarded by run_diagnostic_experiment, so a default
        # (False) run structurally cannot reach it.
        with open("evaluation/comparator.py", encoding="utf-8") as f:
            src = f.read()
        call_site = src.index("self.run_llm_judged_relevance_experiment(dataset)")
        preceding = src[:call_site]
        guard_index = preceding.rfind("if run_diagnostic_experiment:")
        self.assertNotEqual(guard_index, -1, "Diagnostic call site is no longer guarded by run_diagnostic_experiment.")
        # Nothing but whitespace/comments should sit between the guard and the call.
        between = preceding[guard_index:]
        self.assertNotIn("def ", between, "Guard and call site are not in the same function body.")

    def test_main_cli_exposes_an_explicit_opt_in_flag(self):
        with open("main.py", encoding="utf-8") as f:
            src = f.read()
        self.assertIn("--run-retrieval-diagnostic", src)


class TestDailyQuotaExhaustionNeverBecomesAFakeSuccess(unittest.TestCase):
    """Item 9: a judge-call failure - including the new fast-fail path for a
    daily-quota-exhaustion 429 - must still surface as parse_failed=True,
    never a fabricated success or a fake 0.0 score."""

    def test_quota_exhausted_judge_call_is_reported_as_a_failure(self):
        from evaluation.judges.base_judge import BaseJudge
        client = MagicMock()
        client.gemini_key = "fake-key"
        judge = BaseJudge(client, model_name="groq_judge")
        client.generate_response.side_effect = RuntimeError(
            "Error code: 429 - Rate limit reached for model 'openai/gpt-oss-120b' "
            "on tokens per day (TPD): Limit 200000, Used 200000, Requested 500."
        )
        with patch("time.sleep"):
            result = judge.call_llm_with_retry("prompt", max_retries=3)
        self.assertTrue(result.get("parse_failed"))
        self.assertIsNone(result.get("score"))  # never a fabricated numeric score


if __name__ == "__main__":
    unittest.main()
