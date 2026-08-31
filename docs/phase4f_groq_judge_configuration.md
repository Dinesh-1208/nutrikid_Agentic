# Phase 4F — Groq Judge Model, Quota, and Evaluation-Call Optimization

**Status:** Engineering/configuration audit and fix, complete for everything achievable without a live Groq/Gemini API key or a CUDA GPU in this local environment (neither is present here — see §16). Full 49-case Kaggle benchmark **not run** — per the explicit stop condition for this phase, that remains the user's next step after reviewing this document.

**Scope discipline:** this phase touched only judge-model configuration, judge-call volume, and judge-call failure handling. It did not touch: evaluation questions, gold facts, reference answers, `relevant_chunk_ids`, `safety_ground_truth`, RAG data, FAISS index, structured DB, planner logic, Context Recall methodology/formula, or any other retrieval/safety formula. `evaluation/dataset.py`, `docs/evaluation/phase2c_gold_annotations.json`, and `data/` were not opened for writing at any point in this phase.

---

## 1. Model-selection trace (current project code, as of this phase)

| Layer | Where | What it held before this phase |
|---|---|---|
| Symbolic name (evaluator/CLI default) | `evaluation/evaluator.py:11`, `main.py:26` | `"groq_llama70b"` |
| Symbolic name (notebook config) | `KidsNutriBite_Evaluation.ipynb`, Section 10 cell | `JUDGE_MODEL = "groq_llama70b"` |
| Real model ID (dispatch table) | `llm/llm_client.py`, `generate_response()` | `"groq_llama70b"` -> `_call_groq("llama-3.3-70b-versatile", ...)` |
| Actual Groq account catalog | `groq.models.list()`, captured live during the first Kaggle run (`docs/phase4d_first_kaggle_results_audit.md` §16) | `qwen/qwen3.6-27b, groq/compound-mini, canopylabs/orpheus-v1-english, whisper-large-v3, openai/gpt-oss-120b, meta-llama/llama-prompt-guard-2-86m, canopylabs/orpheus-arabic-saudi, allam-2-7b, qwen/qwen3.8-27b, groq/compound, meta-llama/llama-prompt-guard-2-22m, openai/gpt-oss-safeguard-20b, whisper-large-v3-turbo, openai/gpt-oss-20b` — **`llama-3.3-70b-versatile` is absent.** |
| Actual model called (from the first run's own error logs) | `docs/phase4d_first_kaggle_results_audit.md` §7, §16 | Every one of the run's 987 rate-limit errors names `'openai/gpt-oss-120b'` explicitly in the error body, e.g.: `Rate limit reached for model 'openai/gpt-oss-120b' ... on tokens per day (TPD): Limit 200000, Used 199649, Requested 1422.` |

**Conclusion (closes the discrepancy carried over from Phase 4D):** the committed code/notebook at the time of the first Kaggle run said `groq_llama70b` -> `llama-3.3-70b-versatile`, but the run's own logs prove `openai/gpt-oss-120b` is what was actually invoked. Since `_call_groq()` only ever forwards whatever model ID it is given (`llm/llm_client.py`, no fallback/substitution logic exists anywhere in the client), the only explanation consistent with the evidence is that `JUDGE_MODEL` (or the evaluator's `judge_model` argument) was changed live inside that Kaggle session, outside the notebook's committed history — the committed notebook never contained `openai/gpt-oss-120b` before this phase. This phase's notebook change (§13) adds a permanent live-catalog print (Section 9) specifically so this kind of undocumented live edit can never happen unnoticed again.

## 2. Selected model and why

**New default: `groq_judge` -> `openai/gpt-oss-120b`.**

Compared candidates (everything in the live catalog capable of general chat/instruction-following, excluding audio (`whisper-*`), TTS (`orpheus-*`), classifier-only (`llama-prompt-guard-*`), and Groq's own agentic-compound models (`groq/compound*`, a different product surface, not a plain chat-completions judge model) — see the full catalog above):

| Candidate | Availability | Direct evidence of working in this project | Notes |
|---|---|---|---|
| `openai/gpt-oss-120b` | Confirmed (live catalog) | **Yes** — produced valid, parseable judge JSON across hundreds of real calls in the first Kaggle run before its 200K TPD quota was exhausted | Selected. Not chosen for size — chosen because it is the only candidate with direct proof of working end-to-end against this project's real judge prompts. |
| `openai/gpt-oss-20b` | Confirmed (live catalog) | No prior evidence either way | Smaller/faster sibling of the above; used instead for the previously-broken `groq_llama8b` alternate slot (§5), not the primary judge, since there is no evidence (only a plausible assumption) that it has a more generous quota. |
| `openai/gpt-oss-safeguard-20b` | Confirmed (live catalog) | No prior evidence | A safety/policy-classification-specialized variant. Rejected as the *general* judge default because the same `judge_model` is shared by all four judges (Context, Grounding, Relevancy, Safety — `evaluation/evaluator.py:24-29`), and a safety-specialized model is not evidenced to be reliable for the non-safety extraction/labeling tasks the other three judges need. |
| `qwen/qwen3.6-27b` | Confirmed (live catalog) | No prior evidence, but this is the model already used for the alternate `groq_qwen` route (unchanged by this phase) | Left as the existing `groq_qwen` alternate; not promoted to default without evidence it's better-suited than the already-proven `gpt-oss-120b`. |
| `llama-3.3-70b-versatile` | **Not in the live catalog** | N/A | Rejected — this is exactly the confirmed-unavailable model this phase fixes. Not restored "by assumption" per the task's explicit instruction. |

This selection is **evidence-first, not size-first**: `gpt-oss-120b` happens to be the largest of the viable candidates, but the reason it was chosen is that it is the only one with a proven track record against this project's actual judge prompts, not its parameter count.

## 3. Removing model-configuration ambiguity

One symbolic name now means one thing everywhere: **`groq_judge` -> `openai/gpt-oss-120b`.**

- `llm/llm_client.py`: added `"groq_judge"` as the primary route. `"groq_llama70b"` is kept only as a **deprecated backward-compatible alias** routing to the exact same real model (`openai/gpt-oss-120b`) — so old scripts/tests referencing the literal string `"groq_llama70b"` keep working, but the name no longer lies about which model it invokes.
- `evaluation/evaluator.py:11`: constructor default changed `"groq_llama70b"` -> `"groq_judge"`.
- `main.py:26`: `--judge-model` CLI default changed `"groq_llama70b"` -> `"groq_judge"`; help text updated.
- `KidsNutriBite_Evaluation.ipynb`, Section 10: `JUDGE_MODEL = "groq_judge"`.
- `verify_groq.py`: now tests `groq_judge` (primary), `groq_llama8b` (alternate), and `groq_llama70b` (alias, to prove backward compatibility), and prints the live model catalog first.

**Repo-wide search performed** for `groq_llama70b`, `llama-3.3-70b-versatile`, `groq_llama8b`, `llama-3.1-8b-instant`, `openai/gpt-oss-120b`: every remaining occurrence of the old names in `*.py` files is either (a) the intentional backward-compatible alias branch and its tests, or (b) a generic Groq-SDK call-shape test (`test_judge_architecture.py::TestGroqClientCallShape`) that uses `"llama-3.3-70b-versatile"` purely as an arbitrary example string to prove `KidsNutriGroqClient.generate_response` forwards whatever `model_id` it's given — unrelated to project defaults, left unchanged. No file still treats `"llama-3.3-70b-versatile"` as a live default.

**A second, related mapping was also broken and is fixed here:** `groq_llama8b` pointed at `"llama-3.1-8b-instant"`, which is *also* absent from the live catalog. Remapped to `"openai/gpt-oss-20b"` (confirmed-available). This is not the default judge and doesn't affect the official run, but was fixed under the same evidence rather than left silently broken.

## 4. Judge-call table (official metrics, single model, 49-case dataset)

Traced directly from `evaluation/evaluator.py::run_single_evaluation` (Layer 1) — each judge method makes exactly one `call_llm_with_retry` call per invocation (verified via `grep -n call_llm_with_retry` across all four judge files: one call site each).

| Component | Calls per applicable case | Applicable cases | Retries possible | Approx. total (best case, 0 retries) |
|---|---|---|---|---|
| Context Precision (`ContextJudge.evaluate_precision`) | 1 | 49 (always — a live relevance judgment, not gold-dependent) | up to 3 | 49 |
| Context Recall (`ContextJudge.evaluate_recall`) | 1 | 41 (skipped for the 8 non-RAG cases — Phase 4E fix, `context_recall_applicable`) | up to 3 | 41 |
| Grounding / Faithfulness (`GroundingJudge.evaluate_grounding`) | 1 (feeds Faithfulness, Unsupported Claim Rate, and Hallucination Type — 3 metrics from 1 call, already non-duplicated) | 49 | up to 3 | 49 |
| Answer Relevancy (`RelevancyJudge.generate_hypothetical_questions`) | 1 | 49 | up to 3 | 49 |
| Safety (`SafetyJudge.evaluate_safety`) | 1 | 49 | up to 3 | 49 |
| **Official total** | | | | **237** |
| Unofficial retrieval-depth diagnostic (`run_llm_judged_relevance_experiment`) | 2 × 3 K-values (K=3,5,10) | 49 | up to 3 each | 294 — **off by default as of this phase (§6)** |

Worst case with every call exhausting all 3 retries: 237 × 3 = 711 official calls (this worst case is now less likely to fully materialize for daily-quota failures specifically, since those now fail on attempt 1 — see §9).

## 5. Investigation: `run_llm_judged_relevance_experiment` diagnostic

- **Where invoked:** `evaluation/comparator.py::run_comparison`, previously called unconditionally at the end of every `--evaluate` / `run_comparison()` invocation (was at the line `self.run_llm_judged_relevance_experiment(dataset)`).
- **Enabled by default?** Previously yes (unconditional). **Now no** — gated behind a new `run_diagnostic_experiment=False` parameter on `run_comparison()`, and a new `--run-retrieval-diagnostic` CLI flag on `main.py` (both default off).
- **Exact call count:** 2 judge calls × 49 cases × 3 K-values = 294, independent of how many models are being compared.
- **Does it affect official metrics?** No — confirmed by reading its own docstring and the metric names it writes (`retrieval_experiment.csv` only); it is explicitly documented as "NOT part of the official gold-grounded retrieval metrics" and is not read by any code path that produces `ragas_report.csv` / `final_model_comparison.csv`.
- **Action taken:** off by default, opt-in via `run_diagnostic_experiment=True` / `--run-retrieval-diagnostic`. The method itself is untouched and still fully functional when opted into — not removed, per the task's explicit instruction.

## 6. Judge call count optimization (before/after)

| | Before this phase | After this phase (default run) |
|---|---|---|
| Official metric calls | 237 | 237 (unchanged — no genuine duplication found; the grounding judge already correctly serves 3 metrics from 1 call) |
| Diagnostic calls | 294 (always ran) | 0 (opt-in only) |
| **Total judge calls, default run** | **531** | **237** |
| Reduction | | **55.4%** |

No duplicate official judge calls were found or removed — each of the 5 official judge-call sites in `run_single_evaluation` serves a logically distinct metric (or, for Grounding, a distinct *bundle* of metrics computed from one shared response), so nothing there was combined or removed. The entire optimization is the diagnostic's default-off gating.

## 7. Retry behavior investigation and fix

**Before:** `BaseJudge.call_llm_with_retry` (`evaluation/judges/base_judge.py`) retried *any* exception identically — up to 3 attempts with 1s/2s/4s exponential backoff — with no distinction between a transient network blip, a per-minute rate limit, or a daily-quota exhaustion. On a TPD-exhausted judge (exactly what happened in the first Kaggle run — 986/987 of its 429s were `tokens per day (TPD)` errors, `docs/phase4d_first_kaggle_results_audit.md` §17), this meant burning 2 extra wasted API requests plus 3 seconds of backoff per judge call for a condition that cannot be fixed within the same day.

**After:** added `BaseJudge._classify_api_error(exc)`, a best-effort string classifier distinguishing:
- `"daily_quota_exhausted"` — error text contains a 429 indicator plus a daily-limit phrase (`"per day"`, `"tpd"`, `"daily"`, `"requests per day"`). **Fails fast on attempt 1** — no further retries, since waiting seconds cannot un-exhaust a daily quota.
- `"rate_limited_transient"` — a 429 without a daily-limit phrase (e.g. a per-minute/short-window throttle). Uses the existing backoff/retry path unchanged — this is exactly the case backoff exists for.
- `"other"` — anything else (network error, malformed JSON, missing credential, etc.). Uses the existing backoff/retry path unchanged.

The eventual failure shape is **unchanged** in both cases: `{"parse_failed": True, "error": ..., "error_class": ...}` — never a fake success, never a fabricated score. This preserves the Phase 4E principle (a judge failure must surface as `EVALUATION_FAILURE`, never `0.0`) while stopping the new fail-fast path from wasting further requests/tokens against an exhausted daily budget. Regression tests: `test_judge_architecture.py::TestBaseJudgeRetryAndFailureContract::test_daily_quota_exhaustion_fails_fast_without_burning_all_retries` and `::test_transient_rate_limit_still_uses_normal_backoff_retry`.

## 8. API key handling

Verified unchanged and correct — Kaggle Secrets only (`KidsNutriBite_Evaluation.ipynb` Section 4), `os.environ[...]` set directly, no `.env` file written anywhere in the notebook, only `YES`/`NO` printed for key presence, never a value. `llm/groq_client.py` and `llm/llm_client.py` read exclusively from `os.getenv(...)`; no hardcoded key anywhere in the repo (`git grep` for `gsk_`/`AIza` patterns in tracked files: none found).

## 9. Gemini's role

Unchanged by this phase. `llm/llm_client.py`'s `"gemini"` route remains available as (a) an alternate/cross-check judge backend (`JUDGE_MODEL = "gemini"` in the notebook, no code change needed) and (b) an optional alternative *answer*-comparison backend for `--models qwen_local,gemini` runs — a pre-existing, intentional feature unrelated to the official single-model (`qwen_local`) benchmark. The notebook's `ANSWER_MODEL = "qwen_local"` remains hardcoded with an explicit "do not change to gemini/groq for the official run" comment. Gemini is not removed, not proven unused (it is the documented fallback judge), and never used as the production answer model.

## 10. Default agreement across all four configuration points

Verified via `test_phase4f_judge_config.py::TestJudgeModelDefaultAgreesEverywhere` (new, all passing):

| Location | Value |
|---|---|
| `evaluation/evaluator.py::KidsNutriEvaluator.__init__` | `judge_model="groq_judge"` |
| `main.py` `--judge-model` | `default="groq_judge"` |
| `KidsNutriBite_Evaluation.ipynb` Section 10 | `JUDGE_MODEL = "groq_judge"` |
| `llm/llm_client.py` dispatch table | `"groq_judge"` -> `openai/gpt-oss-120b` |

No hidden override exists anywhere in this chain — `KidsNutriEvaluator` passes `judge_model` straight through to each of the four judge constructors (`evaluation/evaluator.py:24-29`), and each judge stores it verbatim as `self.model_name`, used unmodified by `call_llm_with_retry`.

## 11. Notebook cell-by-cell silent-override audit

Every cell in `KidsNutriBite_Evaluation.ipynb` was re-read after editing. No cell overrides a model name, env var, retry setting, or evaluator default outside of the two intentional, visible config cells (Section 4's Kaggle Secrets cell, which only sets `os.environ["GROQ_API_KEY"]`/`["GEMINI_API_KEY"]` from Kaggle Secrets — never a literal value — and Section 10's `JUDGE_MODEL`/`ANSWER_MODEL`/`RUN_RETRIEVAL_DIAGNOSTIC` variables, all clearly commented). Section 9 was extended to print the account's live Groq model catalog and flag a mismatch against `openai/gpt-oss-120b` explicitly, closing the exact gap that let the first run's undocumented live edit go unnoticed.

## 12. Official run call profile and token-budget estimate

**Call profile (default configuration, `RUN_RETRIEVAL_DIAGNOSTIC = False`):** 237 judge calls, per §4's table.

**Token estimate — honest range, not a guaranteed number** (no per-call token telemetry exists from a prior run against `openai/gpt-oss-120b` specifically; this phase adds that telemetry, §14, for the next real run to confirm or correct this estimate):

- RAG chunk size in the live dataset: measured directly — average 134 characters (~34 tokens) per chunk, 5 chunks retrieved per case ≈ 170 tokens of context for Precision/Recall calls.
- Grounding/Relevancy/Safety judge prompts additionally embed Qwen's generated answer (up to `max_new_tokens=1024`, real answers plausibly 150-400 tokens) plus prompt-template overhead (~150-250 tokens) plus a JSON-formatted completion (~100-400 tokens).

| Component | Calls | Est. tokens/call (prompt + completion) | Est. subtotal |
|---|---|---|---|
| Context Precision | 49 | ~450-700 | ~22K-34K |
| Context Recall | 41 | ~550-850 | ~23K-35K |
| Grounding | 49 | ~850-2000 | ~42K-98K |
| Answer Relevancy | 49 | ~400-750 | ~20K-37K |
| Safety | 49 | ~500-900 | ~25K-44K |
| **Total** | 237 | | **~132K-248K** |

**This range straddles the 200,000 TPD limit.** The lower bound (~132K, 66%) leaves real margin; the upper bound (~248K, 124%) would exhaust the quota mid-run even with the diagnostic off. This is a genuinely uncertain estimate, not a comfortable safety margin, and is reported honestly rather than rounded to a reassuring number. **Recommendation:** run the small validation (§16) first and read the real `total_tokens_used` figure the new telemetry (§14) reports before committing to a full unattended 49-case run; if real per-call usage lands in the upper half of this range, consider running on a day with a fresh TPD window and monitoring the live running total mid-run rather than assuming success.

## 13. Notebook changes made

| Cell (Section) | Change |
|---|---|
| Intro (Section 0) | Judge model description updated to `groq_judge` / `openai/gpt-oss-120b`; added a judge-call-volume summary and a note about Section 5's now-stale safety-count display text (found, not fixed — out of this phase's scope, flagged for the user). |
| Section 4 (Kaggle Secrets) | Warning string updated from `groq_llama70b` to `groq_judge`. |
| Section 9 (Groq/Gemini smoke test) | Added a live `groq.models.list()` print with an explicit mismatch warning if `openai/gpt-oss-120b` is absent; smoke test now uses `groq_judge`; prints the real token count Groq reports for that one call. |
| Section 10 (49-case run) | `JUDGE_MODEL = "groq_judge"`; added `RUN_RETRIEVAL_DIAGNOSTIC = False` (opt-in) passed through to `run_comparison(..., run_diagnostic_experiment=RUN_RETRIEVAL_DIAGNOSTIC)`; prints an estimated official-call count before running and the real cumulative Groq token usage after running. |

Validated: notebook is valid JSON, every code cell parses as Python (except the pre-existing `!pip install` shell-magic cell, expected), no `.env` writes, no hardcoded secret values, no stale `llama-3.3-70b-versatile` as an active config value (only in explanatory prose about the fix itself), diagnostic not auto-launched, Qwen remains the sole answer model, Groq remains the default judge.

## 14. Quota-visibility addition (`llm/groq_client.py`)

Added best-effort capture of Groq's own reported `response.usage.total_tokens` per call, exposed as `self.last_call_tokens` (most recent call) and `self.total_tokens_used` (running total) on `KidsNutriGroqClient`. Never changes call behavior or the function's return type/signature (still returns the response text string); wrapped in `try/except` so a missing/unexpected usage shape can never break an otherwise-successful call. Used by the notebook (§13) to print real, not estimated, token usage during both the smoke test and the full run — this is what will let the next real run confirm or correct §12's estimate.

## 15. Quota safety check summary

- Groq's documented limit for this account/model: 200,000 TPD (confirmed directly from the first run's own 429 error bodies).
- Estimated calls for the default (diagnostic-off) official run: 237.
- Estimated token usage: ~132K-248K (§12) — **not** a comfortable, confidently-under-quota margin; genuinely close to or potentially over the limit depending on real answer lengths.
- Mitigations already in place: diagnostic off by default (removes 294 calls / a large token chunk entirely), daily-quota-exhaustion now fails fast instead of wasting further requests, real token telemetry now available to measure actual usage starting with the very first smoke-test call.
- Mitigation **not** taken: no artificial call-count or prompt-size reduction was made to force the estimate under quota, since doing so without evidence of where the real cost concentrates would risk weakening judge prompt quality for a guess. The honest position is: the diagnostic-off default is a large, evidenced improvement (55% fewer calls) but does not *guarantee* headroom by itself — real measurement via §16/§14 is the next required step, not assumed here.

## 16. Small-run validation — attempted, environment-limited

**Could not be completed end-to-end with live API calls in this local environment**, and this is stated plainly rather than fabricated:

- `GROQ_API_KEY`: not set locally (checked via `os.getenv`).
- `GEMINI_API_KEY`: not set locally (checked via `os.getenv`).
- CUDA GPU: not available locally (`torch.cuda.is_available()` returns `False`; local `torch` is the CPU-only build) — `qwen_local` answer generation deliberately raises `RuntimeError` without a GPU (`llm/llm_client.py`'s explicit hardware guard), so even the answer-generation half of a live small-run cannot execute here.

What **was** validated with real project code in this environment (no faked judge responses — mocking is confined to the LLM-client boundary, the same pattern the codebase's own existing test suite already uses):
- Judge-model routing (`groq_judge` -> `openai/gpt-oss-120b`; `groq_llama70b` alias -> same model; `groq_llama8b` -> `openai/gpt-oss-20b`) — `test_phase4f_judge_config.py`, `test_judge_architecture.py`, `test_final_dataset_integration.py`.
- Config agreement across evaluator/CLI/notebook — `test_phase4f_judge_config.py::TestJudgeModelDefaultAgreesEverywhere`.
- Diagnostic-off-by-default, both by signature and by source-level call-site guard — `test_phase4f_judge_config.py::TestUnofficialDiagnosticOffByDefault`.
- JSON parser and failure-classification behavior (malformed JSON, empty response, transient error + recovery, daily-quota-exhaustion fail-fast, transient-rate-limit backoff) — `test_judge_architecture.py::TestBaseJudgeRetryAndFailureContract`.
- Full existing regression suite (Context Recall's status-enum contract, retrieval metrics, safety ground truth wiring, etc.) — unaffected, all still passing.

**What genuinely still needs a live run** (recommended as the user's literal first step on Kaggle, before the full 49-case run): the notebook's own Section 9 cell now does exactly this — 2-3 real `SafetyJudge`/`ContextJudge` calls against the live `groq_judge` model, printing the live model catalog, a parsed-JSON confirmation, and real token usage. This satisfies the spirit of the requested small-run validation using the project's own real code; it could not be pre-executed here for lack of the GPU/API-key environment described above.

## 17. Regression tests added/updated (full list)

- `test_judge_architecture.py`: `_make_judge` default changed to `"groq_judge"`; added `test_daily_quota_exhaustion_fails_fast_without_burning_all_retries`, `test_transient_rate_limit_still_uses_normal_backoff_retry`; routing test split into `test_judge_model_name_groq_judge_routes_to_groq_with_verified_model_id`, `test_judge_model_name_groq_llama70b_routes_as_deprecated_alias_to_same_verified_model`, `test_judge_model_name_groq_llama8b_routes_to_a_verified_model_id`.
- `test_final_dataset_integration.py`: default-value assertions updated to `"groq_judge"`; `test_groq_llama70b_is_still_reachable_as_default_judge_backend` replaced with `test_groq_judge_is_the_default_judge_backend_and_routes_to_a_verified_model` (new default) plus `test_groq_llama70b_is_still_reachable_as_deprecated_alias` (alias still works); judges'-model-name assertion updated to `"groq_judge"`.
- `test_phase4f_judge_config.py` (new file, 10 tests): default agreement across evaluator/CLI/notebook, routing to the evidenced real model, alias correctness, diagnostic-off-by-default (signature + source-level guard), CLI opt-in flag presence, quota-exhaustion-never-a-fake-success.
- No existing test was weakened — every changed assertion reflects an intentional Phase 4F default change and, where applicable, was strengthened (e.g. the new alias test explicitly asserts the routed model is *not* the old fictional ID, not just that some string changed).

Full suite: `python -m unittest discover -v` -> **157 tests, all passing** (147 pre-existing + 10 new). `python -m unittest planner.test_weekly_planner -v` -> 3/3 passing. `python -m compileall -q .` -> clean, exit 0.

## 18. Files changed in this phase

- `llm/llm_client.py` — added `groq_judge` route; `groq_llama70b` kept as alias to the same real model; `groq_llama8b` remapped to a verified model.
- `llm/groq_client.py` — added best-effort token-usage capture (`last_call_tokens`, `total_tokens_used`); no signature/behavior change.
- `evaluation/evaluator.py` — `judge_model` default changed to `"groq_judge"`.
- `evaluation/judges/base_judge.py` — added `_classify_api_error`; daily-quota-exhaustion now fails fast instead of exhausting retries; failure dict gained an `error_class` key (additive, non-breaking).
- `evaluation/comparator.py` — `run_comparison` gained `run_diagnostic_experiment=False`; diagnostic call now gated behind it.
- `main.py` — `--judge-model` default changed to `"groq_judge"`; added `--run-retrieval-diagnostic` opt-in flag, wired through to `run_comparison`; `--model` help text updated.
- `verify_groq.py` — tests `groq_judge`/`groq_llama8b`/`groq_llama70b`; prints live model catalog first.
- `KidsNutriBite_Evaluation.ipynb` — Sections 0, 4, 9, 10 updated (model names, live-catalog print, diagnostic opt-in, call/token estimates and real-usage printing).
- `test_judge_architecture.py`, `test_final_dataset_integration.py` — updated for the intentional default/routing change; new tests added.
- `test_phase4f_judge_config.py` — new file.
- `docs/phase4f_groq_judge_configuration.md` — this document.

No dataset, RAG, structured-DB, FAISS, planner, or metric-formula file was modified. Nothing was committed or pushed; all changes remain unstaged in the working tree, consistent with this phase's explicit instruction.

---

## Final required answers

**A. Exact model chosen for the default judge, with real model ID:** `groq_judge` -> `openai/gpt-oss-120b` (Groq-hosted).

**B. Why this is preferable to blindly keeping `openai/gpt-oss-120b`'s old undocumented status (or guessing at another model):** It's the *same* model that was already proven, via the first real Kaggle run's own successful calls (before quota exhaustion), to produce valid parseable JSON against this project's actual judge prompts — the fix here is not changing which model gets called, but making the configuration honestly say so everywhere, closing the `groq_llama70b` → nonexistent-`llama-3.3-70b-versatile` naming lie and the silent-live-edit gap that produced it.

**C. Exact call count after optimization:** 237 official judge calls for the default (diagnostic-off) 49-case single-model run, down from 531 when the diagnostic ran unconditionally — a 55.4% reduction in default judge-call volume. (See §4, §6.)

**D. Expected quota percentage:** Estimated 66%-124% of the 200,000 TPD limit (~132K-248K tokens) — a genuine range, not a confident safety margin (§12, §15). Real measurement via the new token telemetry (§14) during the Section 9 smoke test and the full run is recommended before treating this as safe.

**E. Diagnostic-disabled confirmation:** Confirmed off by default at both the `run_comparison()` signature level and the notebook level (`RUN_RETRIEVAL_DIAGNOSTIC = False`); verified by `test_phase4f_judge_config.py::TestUnofficialDiagnosticOffByDefault` (3 tests, all passing).

**F. Can the full benchmark run without hitting quota?** Likely, but not certain from the estimate alone — see D. The diagnostic-off change alone removes a large, previously-unconditional cost; whether the remaining 237-call official run fits comfortably depends on real average answer/prompt lengths this estimate could only bound, not measure exactly. Recommend running Section 9's live smoke test first and reading its real token-usage print before running Section 10.

**G. Notebook/project config agreement:** Confirmed — evaluator default, CLI default, and notebook `JUDGE_MODEL` all read `"groq_judge"`; no hidden override found anywhere in the chain (§10, §11).

**H. Gemini's availability:** Unchanged — still available as an alternate/cross-check judge (`JUDGE_MODEL = "gemini"`) and as an optional alternative *answer*-comparison backend (`--models qwen_local,gemini`, pre-existing feature); never used as the production answer model; not removed (§9).

**I. Qwen-sole-answer-model confirmation:** Confirmed unchanged — `ANSWER_MODEL = "qwen_local"` remains hardcoded in the notebook's official run cell with an explicit do-not-change comment; no Groq-hosted model was substituted for answer generation anywhere in this phase.

**J. Validation success:** Partial and explicitly honest about the gap — everything achievable without a live Groq/Gemini API key or a CUDA GPU was validated with real project code (routing, config agreement, diagnostic gating, failure-classification behavior, full existing regression suite: 157/157 passing). The live-call portion (real Groq requests, real Qwen GPU inference) could not be executed in this local environment and is deferred to the notebook's own Section 9 smoke test as the literal first step of the next Kaggle run (§16).

**K. Exact files changed:** See §18's full list. No dataset/RAG/structured-DB/FAISS/planner/metric-formula file was touched; nothing committed or pushed.
