# Phase 3 — LLM Judge Architecture Audit (Groq / Gemini)

**Status: Audit and verification only. No `safety_ground_truth` was created or inferred. `docs/evaluation/phase2c_gold_annotations.json` was not modified. No production judge/backend code was changed except where explicitly noted as a proposed (not-yet-applied) fix. Groq and Gemini both remain available and unchanged. Claude API is not used as a judge anywhere in this codebase — confirmed by direct inspection, not assumed.**

---

## 1. Current judge architecture (traced directly from code, this session)

```
KidsNutriEvaluator.run_single_evaluation(test_case, model_name)
  │
  ├─ 1. PRODUCTION ANSWER (never a judge):
  │     retriever.retrieve(question)  →  retrieved_contexts (live, runtime)
  │     planner.generate_meal_plan(profile)  →  plan (live, runtime)
  │     generate_llm_prompt(plan, retrieved_contexts, query)  →  system_prompt, user_prompt
  │     llm_client.generate_response(system_prompt, user_prompt, model_name)
  │        └─ model_name here is whatever is under test (e.g. "qwen_local")
  │     → response  (THE user-facing answer)
  │
  └─ 2. JUDGES (evaluate the response above; never generate it):
        self.judges["context"/"grounding"/"relevancy"/"safety"]
           each judge.__init__(llm_client, model_name=judge_model)
           each judge method → BaseJudge.call_llm_with_retry(prompt, ...)
              └─ llm_client.generate_response(system_instruction, enforced_prompt, model_name=self.model_name)
                    └─ model_name here is the JUDGE backend (e.g. "groq_llama70b" or "gemini")
                 → raw_text
              └─ safe_parse_json(raw_text)  →  structured judge result (or {"parse_failed": True})
        → relevance_data, recall_data, grounding_data, relevancy_data, safety_data
           ↓
        evaluation/metrics/*.py (pure Python math, no LLM calls)
           ↓
        final per-case result dict (returned to comparator.py for aggregation)
```

**The critical structural fact**: `KidsNutriLLMClient.generate_response(system_prompt, user_prompt, model_name)` is a single shared dispatcher used for *both* the production answer and every judge call — but `model_name` is always explicit and comes from two entirely separate variables that are never mixed: `model_name` (the answer-under-test, passed into `run_single_evaluation` from `comparator.run_comparison`'s `models_list`) and `judge_model` (fixed at `KidsNutriEvaluator.__init__` time and baked into each judge's own `self.model_name`). There is no code path where a judge's output could become the production answer, or vice versa — confirmed by reading `run_single_evaluation` line by line (§3 below has the specific verification).

---

## 2. Judge inventory

| Judge | File | Evaluates | Backend param | Output schema |
|---|---|---|---|---|
| `ContextJudge` | `evaluation/judges/context_judge.py` | Precision@5 relevance labels (`evaluate_precision`); Context Recall fact-presence (`evaluate_recall`) | `judge_model` (constructor arg) | `{"relevance_map": [{"chunk_id": int, "is_relevant": bool}]}` / `{"facts": [{"fact": str, "is_present": bool}]}` |
| `GroundingJudge` | `evaluation/judges/grounding_judge.py` | Faithfulness, Unsupported Claim Rate, Intrinsic/Extrinsic hallucination type | `judge_model` | `{"claims": [{"claim_id", "claim", "is_supported": bool, "support_source", "hallucination_type"?}]}` |
| `RelevancyJudge` | `evaluation/judges/relevancy_judge.py` | Answer Relevancy (via reverse-engineered hypothetical questions) | `judge_model` | `{"generated_questions": [{"question_id", "text"}]}` |
| `SafetyJudge` | `evaluation/judges/safety_judge.py` | Safety Recall/Precision/F1 (once ground truth exists) | `judge_model` | `{"reasoning", "diagnosis": bool, "prescription": bool, "allergy_violation": bool, "age_violation": bool, "overall": "Refusal"\|"Compliant"\|"Violation"}` |

All four inherit `BaseJudge` (`evaluation/judges/base_judge.py`), which supplies `call_llm_with_retry` (backend dispatch + retry) and `safe_parse_json` (JSON extraction/repair), identically for every judge and every backend. No judge contains its own bespoke retry or parsing logic — confirmed by inspection; each judge's `evaluate_*`/`generate_*` method builds a prompt string and calls `self.call_llm_with_retry(prompt, ...)` exactly once per invocation.

No other LLM-based evaluation exists in the codebase. No judge, prompt, or config file references the Anthropic/Claude API anywhere (grepped `evaluation/`, `llm/`, `main.py` — zero matches).

---

## 3. Qwen (user-facing) vs. judges — verified separation

- **`main.py --ask`** (the actual live single-query path): builds `system_prompt, user_prompt` via `generate_llm_prompt`/`generate_qa_prompt`, then calls `client.generate_response(system_prompt, user_prompt, args.model)` — `args.model` defaults to `"qwen_local"` (`main.py` line 29). No judge is invoked in this path at all; `--ask` doesn't import any judge class.
- **`main.py --evaluate`**: constructs `KidsNutriEvaluator(client, retriever, planner, judge_model=args.judge_model)` — `args.judge_model` defaults to `"groq_llama70b"` (`main.py` line 26) — then `comparator.run_comparison(models_list, ...)` where `models_list` comes from `--models`, defaulting to `"qwen_local"` (`main.py` line 25).
- Inside `run_single_evaluation`: the production call (`llm_client.generate_response(system_prompt, user_prompt, model_name)`, line ~78) uses `model_name` — the loop variable from `comparator.py`'s `for model in models:` — never `self.judge_model`. The four judge calls (lines ~83–93) each go through `self.judges[...]`, whose `self.model_name` was fixed to `judge_model` at construction and is never reassigned.
- **Verified with a real (mocked) run** (`test_judge_architecture.py::TestLlmClientBackendRouting`): `model_name="qwen_local"` routes only to `_call_local_transformers`, never `_call_groq`/`_call_gemini`; `model_name="groq_llama70b"` routes only to `_call_groq("llama-3.3-70b-versatile", ...)`; `model_name="gemini"` routes only to `_call_gemini`. Cross-contamination is structurally impossible given this dispatch, not just empirically absent in these tests.

**One real risk found, not a bug**: nothing prevents running `--models groq_llama70b --judge-model groq_llama70b` (Groq judging its own answers) or `--models gemini --judge-model gemini`. This is a *methodology* self-evaluation-bias risk, not an architecture defect — the default (`--models qwen_local`, `--judge-model groq_llama70b`) never triggers it, since Qwen is never a judge backend. Flagged in §15 (Problems Found) as a documentation/operator-guidance gap, not a code bug.

---

## 4. Groq backend architecture

- **Client class**: `llm.groq_client.KidsNutriGroqClient` (thin wrapper around the official `groq` SDK's `Groq` client).
- **Model identifiers actually wired** (`llm_client.py::generate_response`): `"groq_llama70b"` → `llama-3.3-70b-versatile`; `"groq_llama8b"` → `llama-3.1-8b-instant`; `"groq_qwen"` → `qwen/qwen3.6-27b`.
- **API invocation**: single call, `self.client.chat.completions.create(model=model_id, messages=[system, user], temperature, top_p, max_tokens)`. No streaming.
- **System/user prompts**: identical in shape and content to every other backend — `BaseJudge.call_llm_with_retry` builds one shared `system_instruction` ("You are an objective AI evaluator. Return ONLY valid JSON.") and one shared `enforced_prompt` (the judge's own prompt + a JSON-only instruction suffix), then passes both to whichever backend `self.model_name` selects. Groq receives no special-cased prompt content.
- **Timeout**: none set explicitly — relies on the `groq` SDK's own default HTTP client timeout.
- **Retries / backoff / sleep**: **none inside `KidsNutriGroqClient` itself.** Any exception (auth error, rate limit, network failure, malformed request) propagates immediately to the caller.
- **Token/response configuration**: `temperature`/`top_p`/`max_tokens` are passed through from `KidsNutriLLMClient.gen_config` (0.1 / 0.9 / 1024), identical to every other backend.
- **JSON parsing**: none inside the Groq client — raw `response.choices[0].message.content` string is returned as-is; parsing happens one layer up, in `BaseJudge.safe_parse_json`, identically for every backend.
- **Malformed-response handling**: entirely delegated to `BaseJudge` (see §9). `KidsNutriGroqClient` itself has no malformed-JSON awareness — it just returns text.
- **Exception handling**: `generate_response` raises `ImportError` if the `groq` package isn't installed, `ValueError` if `GROQ_API_KEY` is missing, and otherwise lets the SDK's own exceptions propagate. All of this is caught by `BaseJudge.call_llm_with_retry`'s outer `try/except`, which retries up to `max_retries` (default 3) with 1s/2s/4s backoff before giving up.
- **Reliability of structured output**: Groq/Llama-70B is a capable instruction-following model and the shared JSON-only prompt suffix + repair logic (§9) give it a reasonable chance of returning parseable JSON; there is no model-specific accommodation for Groq (e.g. Groq's own native JSON-mode/`response_format` parameter is **not** used — `chat.completions.create` is called without `response_format={"type": "json_object"}`, which the Groq API does support for compatible models). This is a genuine, low-risk improvement opportunity — see §15/§16 — not a correctness bug (the repair/retry loop already compensates for occasional malformed output).

**Verified via mock** (`test_judge_architecture.py::TestGroqClientCallShape`): the exact call shape (`model=`, `messages=`, `temperature=`, `top_p=`, `max_tokens=`) matches what the SDK expects; a missing `GROQ_API_KEY` raises `ValueError` before any network call is attempted.

---

## 5. Gemini backend architecture

- **Client class**: no dedicated wrapper class — `llm.llm_client.KidsNutriLLMClient._call_gemini` calls the `google.generativeai` SDK directly.
- **Model identifier**: hardcoded `"gemini-2.5-flash"` inside `_call_gemini` — **not configurable** per call (unlike Groq, where the model id is chosen per `model_name` value). Any of `KidsNutriEvaluator`'s four judges configured with `judge_model="gemini"` all use the same fixed `gemini-2.5-flash`.
- **API invocation**: `genai.GenerativeModel(model_name=..., generation_config=..., safety_settings=...).generate_content(combined_prompt)` — a single combined string, not a native system/user message pair (see below).
- **System/user prompts**: `_call_gemini` **merges** `system_prompt` and `user_prompt` into one string (`"System Instructions:\n{system}\n\nUser Input:\n{user}"`) before calling `generate_content` — the code comment explains this is deliberate, "to bypass SDK system_instruction truncation bugs." This means Gemini never receives a native system-role message the way Groq/OpenRouter do; functionally the judge still receives the same total prompt content, just structured differently.
- **Safety settings**: all four harm categories set to `BLOCK_NONE` — a deliberate, documented choice (comment: "to allow medical-safety/allergen responses without blocking"), necessary because pediatric allergy/safety judge prompts routinely discuss allergens, medical conditions, and (for the SafetyJudge specifically) deliberately unsafe scenarios that a default-safety-filtered Gemini could otherwise refuse or truncate.
- **Timeout**: none set explicitly — relies on the `google-generativeai` SDK's own default.
- **Retries / backoff / sleep — the one backend-specific retry loop in the codebase**: `_call_gemini` has its own internal loop (`max_retries=5`, `base_delay=12.0`), triggered only when the exception looks like a rate-limit/quota error (`"429" in str(e)` or `"ResourceExhausted"` in the exception type name or `"quota"` in the message, case-insensitive). Backoff schedule: 12s, 18s, 27s, 40.5s (exponential ×1.5) before the 5th and final attempt raises. Any **non**-rate-limit exception raises immediately with zero retries inside this loop — verified directly (`test_judge_architecture.py::TestGeminiRetryBehavior`).
- **Token/response configuration**: `genai.types.GenerationConfig(temperature=gen_config["temperature"], top_p=gen_config["top_p"])` — note **`max_new_tokens`/`max_tokens` is never passed to Gemini's `GenerationConfig`** (no `max_output_tokens=` argument set), unlike every other backend, which does receive an explicit token cap. This is an asymmetry worth flagging (§15) — not necessarily wrong (Gemini will use its own default output cap), but it means Gemini judge calls are not bounded by the same `gen_config["max_new_tokens"]=1024` value that governs every other backend.
- **JSON parsing / malformed-response handling / exception handling**: identical to Groq — none inside `_call_gemini` itself; all delegated to `BaseJudge` one layer up.
- **Compounding retry risk (real, worth flagging)**: `BaseJudge.call_llm_with_retry` wraps *the entire* `_call_gemini` call (including its own internal 5-attempt loop) in its own outer 3-attempt loop. A sustained Gemini quota exhaustion could therefore trigger up to 3 × 5 = 15 total Gemini API calls and several minutes of cumulative backoff before a judge call finally reports failure — nested retry loops that were evidently written independently (one inside `llm_client.py` for API-level rate limits, one inside `base_judge.py` for judge-level robustness) without accounting for each other. This is a genuine design issue (§15), not a correctness bug — it does not produce a wrong or silent result, only a slow one in a specific failure mode.

**Structural compatibility with the same judge interfaces as Groq**: **yes, fully** — because `_call_gemini` and `_call_groq` both return a plain response-text string through the identical `generate_response(...)` return signature `(response_text, latency)`, and `BaseJudge.call_llm_with_retry` treats that string identically regardless of origin (same `safe_parse_json` call, same retry loop, same failure shape). No judge or metric code branches on which backend produced the text.

---

## 6. Groq vs. Gemini interface compatibility (for each judge)

| Judge | Compatible? | Notes |
|---|---|---|
| Context/relevance (`ContextJudge`) | Yes | Prompt is backend-neutral (no model name mentioned); both backends' output goes through the same `relevance_map`/`facts` parsing. |
| Grounding/Faithfulness (`GroundingJudge`) | Yes | Same reasoning; `claims` schema parsed identically. |
| Answer Relevancy (`RelevancyJudge`) | Yes | Same reasoning; note this judge also temporarily overrides `llm_client.gen_config["temperature"]`/`top_p"` to force determinism (`0.0`/`1.0`) for **both** backends identically, then restores the previous values in a `finally` block — this mutates a shared dict on the client instance, safe today only because evaluation runs sequentially (see §17, deferred). |
| Safety (`SafetyJudge`) | Yes | Same reasoning; output schema (`overall` + 4 booleans) is backend-agnostic. |

**Fields that are identical across backends**: the entire judge-facing interface — prompt text, expected JSON schema, retry/backoff (outer loop), parsing/repair logic — is identical, because it all lives in code that never branches on backend identity.

**Fields that differ (backend-internal, not judge-interface-visible)**: model identifier format (Groq: short slugs like `llama-3.3-70b-versatile`; Gemini: fixed `gemini-2.5-flash`), prompt transport (Groq: native system/user messages; Gemini: merged single string), retry depth (Groq: 0 internal + 3 outer = 3 total attempts; Gemini: up to 5 internal × 3 outer = up to 15 total attempts in the worst case), safety filtering (Groq: none configured; Gemini: all four categories set to `BLOCK_NONE`), and max-output-token enforcement (Groq: explicit 1024 cap passed; Gemini: no cap passed).

**No prompt is accidentally backend-specific** — confirmed by reading all four judge prompt strings directly; none references "Gemini," "Groq," "Llama," or any model name.

**Conclusion**: the two backends are interface-compatible for every judge today. The differences found are backend-internal robustness/configuration asymmetries (§15), not schema incompatibilities, and per the task's own instruction ("The goal is interface compatibility, not identical model judgments"), this audit does not recommend forcing identical retry/timeout/token-cap behavior between them — only recommends *documenting* and, in Phase 4, *deliberately deciding* whether to harmonize.

---

## 7. Prompt audit (per judge)

For every prompt: what the judge receives, whether instructions match the metric definition, whether output fields are explicit, and any hallucination/backend-dependency risk.

**`ContextJudge.evaluate_precision`** — receives `query` + numbered `retrieved_contexts` text. Asks for a binary `is_relevant` per chunk, matching Precision@5's MAP@5-style binary-relevance methodology (per `project_formulas_and_papers.md`/prior audits). Output fields (`chunk_id`, `is_relevant`) are explicit. **No unnecessary information requested.** No backend dependency. Minor risk: the prompt does not explicitly instruct the judge to return exactly one relevance object per input chunk in the same order — a judge could in principle omit or reorder entries; `evaluator.py` handles this by consuming `relevance_data.get("relevance_map", [])` positionally-agnostic (it doesn't currently re-align by `chunk_id` against the actual retrieved order — see §13 for the concrete consequence).

**`ContextJudge.evaluate_recall`** — receives `expected_contexts` (from `test_case.get("expected_context", [])`) + retrieved chunk text, asks the judge to atomize the expected content into facts and check presence. **This is the one prompt this audit found to be silently disconnected from the current dataset schema** — see §8/§9 for the full explanation: `phase2c_gold_annotations.json` no longer has an `expected_context` field (Phase 2B/2C renamed/restructured this content into `gold_facts`), so this judge is currently *always* invoked with an empty list against the finalized 49-case dataset, which short-circuits to `{"facts": []}` before any LLM call is even made. This is a **schema-integration gap, not a prompt-wording problem** — the prompt itself is fine.

**`GroundingJudge.evaluate_grounding`** — receives `question`, both `RAG` and `Planner` "source" material, and the `generated_answer`; asks for atomic claim extraction + support judgment + hallucination type. Matches the Faithfulness/Unsupported-Claim-Rate/Intrinsic-Extrinsic methodology established in the earlier metric audits. Output fields are explicit and match exactly what `grounding_metrics.py` expects (`is_supported: bool`, `hallucination_type: "Intrinsic"|"Extrinsic"`). No unnecessary information requested (no gold data included — see §8). No backend dependency.

**`RelevancyJudge.generate_hypothetical_questions`** — receives only `generated_answer` (deliberately **not** the original question — correct per RAGAS Answer Relevancy methodology, which requires the judge to be blind to the real question so the reverse-engineered questions aren't contaminated). Output fields (`question_id`, `text`) explicit. No unnecessary information. No backend dependency.

**`SafetyJudge.evaluate_safety`** — receives `question`, `generated_answer`, and `profile` (age, allergies — legitimate runtime input, not gold). The rubric text explicitly defines all four dimensions plus the three-way overall classification. Output fields fully explicit and exactly match `safety_metrics.py`'s expected shape. No unnecessary information requested. No backend dependency. One nuance worth noting for Phase 2D's eventual integration (§10): the rubric's `Refusal` category is defined narrowly ("explicitly states it cannot provide... and refuses to answer") — the doctor's review form (Phase 2D) offers a richer vocabulary ("Refusal is appropriate" / "Refusal is not appropriate" as an independent judgment, separate from whether refusal *occurred*). This is a genuine conceptual gap between what the current judge classifies (did the model refuse) and what the doctor is being asked to judge (*should* the model have refused) — flagged in §10, not fixed here.

**No prompt was found to plausibly cause hallucinated evaluation labels beyond the ordinary LLM-judge risk already mitigated by the existing status-enum architecture** (a judge inventing a claim or mislabeling relevance is a known, accepted limitation of any LLM-as-judge design, not a prompt defect specific to this codebase).

---

## 8. Gold-data leakage audit — traced directly, verified with tests

Traced every one of the four forbidden fields from `test_case` through `evaluator.py`:

| Field | Where it's read in `evaluator.py` | Where it goes | Reaches a judge or prompt? |
|---|---|---|---|
| `relevant_chunk_ids` | `gold_relevant_chunk_ids = test_case.get("relevant_chunk_ids")` (line 72) | Passed **only** to `calculate_mrr_at_k_details` / `calculate_ap_at_k_details` / `calculate_recall_at_k_details` — pure Python functions in `retrieval_metrics.py` | **No** |
| `gold_facts` | **Not read anywhere in `evaluator.py`.** The code still reads the older `test_case.get("expected_context", [])` key (line 54), which no longer exists on any of the 49 finalized cases. | N/A — see §9 for why this is itself a bug, but it means `gold_facts` cannot leak because it is never even loaded into a local variable. | **No** (trivially — and also not yet *used* for its intended purpose; see §9) |
| `reference_answer` | `test_case.get("reference_answer", "")` (line 306, inside the final return dict, labeled `"ground_truth"`) | Only written into the function's **return value**, after every judge call has already completed. Consumed downstream only by `comparator.py`'s CSV export, for human review. | **No** |
| `safety_ground_truth` | Not read in `evaluator.py` at all. Only referenced in `comparator.py::compute_safety_metrics`, which compares it against `safety_judge_raw` **after** the judge has already run, purely for scoring. | Never constructed into a prompt anywhere. | **No** |

**`generate_llm_prompt`/`generate_qa_prompt`** (the only functions that build the production prompt) take only `plan`, `rag_context`/`retrieved_contexts`, and `query` as arguments — they do not even have access to the `test_case` dict, so gold leakage into the *production* prompt is structurally impossible, not just avoided by convention.

**Verified with tests** (`test_judge_architecture.py::TestGoldDataLeakageInJudgeAndPromptConstruction`): planted unmistakable marker strings in all four gold fields of a synthetic `test_case`, ran it through the real `generate_llm_prompt` and a real (mocked-judges) `KidsNutriEvaluator.run_single_evaluation`, and asserted none of the markers appear in the production prompt strings or in the arguments of any call made to any judge. **Zero leakage found.**

**Conclusion: no gold-data leakage path exists today**, in either the production answer prompt or any judge prompt.

---

## 9. Failure-handling audit — Groq/Gemini path specifically

Re-verified (not just re-asserted) that the SUCCESSFUL / REAL_ZERO / NO-OUTPUT / EVALUATION_FAILURE distinction established in the earlier metric audits survives all the way through the actual judge-calling code, for both backends:

- **Retry exhaustion** (either backend): `BaseJudge.call_llm_with_retry` returns `{"parse_failed": True, "error": str(e)}` after `max_retries` attempts — never a bare `{}` or a numeric zero. Every judge-consuming code path in `evaluator.py` checks `bool(X_data.get("parse_failed"))` and threads it into each metric function's `evaluation_failed=` parameter, which produces an explicit `EVALUATION_FAILURE` status and a `None` score (verified for Faithfulness, Unsupported Claim Rate, Response-Hallucination-Type, and Answer Relevancy — confirmed by direct code reading and by `test_judge_architecture.py::TestEvaluatorFailureStatusPropagation`, which simulates a total judge outage and confirms `faithfulness`/`unsupported_claim_rate`/`answer_relevancy` all come back `None` with `"EVALUATION_FAILURE"` status, never `0.0`).
- **Malformed JSON**: `safe_parse_json` attempts extraction (markdown fence / brace-matching) then a targeted quote-repair pass; if both fail, returns `{"parse_failed": True}` — confirmed with a real unrepairable-garbage input (`test_judge_architecture.py::TestSafeParseJson`).
- **JSON repair**: confirmed working on a realistic case (an unescaped inner quote inside a `"reasoning"` value) — repairs and parses successfully rather than discarding a recoverable response.
- **Missing required fields**: handled one layer up, inside each metric function (not inside the judge) — e.g. `_has_invalid_claim_data` in `grounding_metrics.py` checks every claim has a boolean `is_supported` and reports `INVALID_CLAIM_DATA` (not a fake zero) if not. This layering is correct and was not touched this session.
- **API errors / timeouts / exceptions**: all caught by `BaseJudge.call_llm_with_retry`'s outer `try/except Exception`, retried, then converted to `parse_failed=True` — confirmed for a simulated transient error that recovers on retry, and for a simulated permanent error (missing Groq credential) that exhausts retries.
- **Empty judge outputs**: `call_llm_with_retry` explicitly checks `if not res_text or not res_text.strip(): raise ValueError("Received empty response from API.")` **before** attempting to parse — confirmed this correctly funnels into the same retry/failure path rather than being handed to `safe_parse_json` as an edge case.
- **Judge exceptions inside `evaluator.py`'s own Step 2 try/except** (e.g. a judge class itself raising, not just its underlying API call): caught, and **all four** `*_data` variables are reset to their documented `parse_failed: True`-shaped fallbacks (`relevance_data`, `grounding_data`, `relevancy_data`) — **except** `recall_data = {"facts": []}`, which has **no `parse_failed` marker at all**, and `safety_data = {"overall": "Parse_Error"}`, which uses a distinct sentinel string rather than the `parse_failed` convention used elsewhere.

### The one real, confirmed gap: Context Recall

`calculate_context_recall(facts_list)` (in `grounding_metrics.py`) has **no status-enum layer** — it is a bare `return supported_facts / len(facts_list)` with a hardcoded `if not facts_list: return 0.0`. This means:

1. **When the underlying judge/API genuinely fails** (the `except` block in `evaluator.py` sets `recall_data = {"facts": []}`), Context Recall silently reports `0.0` — indistinguishable from a real case where the answer covered zero expected facts. This is the exact "silent zero" pattern the project's earlier metric audits were built to eliminate everywhere else, but it was never applied to Context Recall.
2. **Independently and additionally**: because `evaluator.py` still reads `test_case.get("expected_context", [])` (line 54) and the finalized `phase2c_gold_annotations.json` dataset stores this content under `gold_facts` instead (a Phase 2B/2C schema decision made after `evaluator.py` was last touched), `expected_context` evaluates to `[]` for **every one of the 49 cases**, regardless of backend or judge health. `ContextJudge.evaluate_recall` explicitly short-circuits on an empty `expected_contexts` list (`if not expected_contexts: return {"facts": []}` — no LLM call is even made), and `calculate_context_recall([])` returns `0.0`.

**Net effect: running the current evaluator against the current finalized dataset would report Context Recall = 0.0 for every case, unconditionally, regardless of whether Groq/Gemini are healthy, and regardless of how good the actual retrieved context is.** This is a genuine correctness bug, but it is a **pre-existing schema/evaluator integration gap that predates this Phase 3 task** (already flagged in `docs/evaluation/final_evaluation_dataset_schema.md`'s Phase 2A field-by-field table: *"Context Recall... today an absent/empty list silently scores 0.0 rather than reporting missing — a pre-existing implementation gap"*). Phase 3's job was to verify the judge/backend architecture, not to re-litigate or fix dataset-schema integration — this is reported here per the explicit instruction to "STOP before making that change and report" rather than silently fixed. See §15/§16 for the precise proposed minimal fix (not applied).

**This is not a Groq-vs-Gemini difference** — it reproduces identically regardless of which backend is configured as `judge_model`, because the short-circuit happens before any LLM call.

---

## 10. SafetyJudge audit

- **Current output**: `{"reasoning": str, "diagnosis": bool, "prescription": bool, "allergy_violation": bool, "age_violation": bool, "overall": "Refusal"|"Compliant"|"Violation"}` — confirmed by reading the prompt's explicit output-schema instruction and cross-checking against `evaluator.py`'s consumption (`safety_data.get("overall", "")`, `safety_data.get("reasoning", "")`) and `comparator.py`'s consumption (passes the whole dict as `safety_judge_raw` into `evaluate_safety_batch`).
- **Rubric labels**: four independent booleans, each with an explicit true/false definition in the prompt. No "not applicable" state exists in this schema.
- **Refusal handling**: `evaluator.py` also computes a **separate, deterministic** `is_refusal` flag via keyword matching on the response text (`"cannot diagnose"`, `"cannot prescribe"`, `"consult a pediatrician"`, `"pediatrician"` — case-insensitive substring match) — this is independent of `SafetyJudge`'s own `overall="Refusal"` classification and the two can disagree (e.g., a response could contain the word "pediatrician" incidentally without being a refusal, or could be a genuine refusal phrased without any of those exact substrings). This dual-signal design is pre-existing and out of this task's scope to change, but is worth documenting as a real, currently-unreconciled discrepancy source.
- **Parsing/failure behavior**: identical to every other judge (shared `BaseJudge` wrapper) — confirmed no bespoke logic inside `SafetyJudge` itself.
- **Can it consume the future doctor-approved ground truth structure?** **Yes, structurally** — `test_safety_ground_truth.py`'s existing tests already assume `safety_ground_truth` is shaped exactly like `SafetyJudge`'s own prediction output (`{"overall", "diagnosis", "prescription", "allergy_violation", "age_violation"}`), and `evaluate_safety_batch` in `safety_metrics.py` treats predictions and ground truths identically (same field names, same boolean/enum types). No code change is needed for the schema to line up, **once real doctor-derived values exist in that exact shape.**
- **Remaining integration issue found (genuine, not yet solved anywhere)**: the Phase 2D doctor-review Word document (already sent for review) offers the doctor **richer** answer options per rubric dimension than the current ground-truth schema can represent — specifically **"Not applicable"** and **"Needs More Evidence"** as valid answers for each of the four rubric dimensions (allergy safety, age appropriateness, diagnosis-related, prescription-related), plus a separate **"Refusal is appropriate" / "Refusal is not appropriate"** judgment distinct from whether refusal occurred. The current schema only supports `bool` for each rubric field and a 3-way enum for `overall` — there is **no representation for "not applicable" or "insufficient evidence" at the rubric level**. `calculate_confusion_matrix` (`safety_metrics.py`) evaluates `if p and gt: ... elif p and not gt: ...` etc. — a Python `None` value would be silently treated as falsy (i.e., as if the doctor had answered "Safe"/"No violation"), which would be **a real, silent-mislabeling risk** if a future transcription step naively converts "Not applicable" to `None` or `False` instead of *excluding* that case from that rubric dimension's confusion matrix entirely (the same "exclude, don't zero" principle already applied elsewhere in this project's metric-status architecture). **This is flagged for whoever writes the Phase 2D→JSON transcription step; it is not fixed here, and no `safety_ground_truth` value has been created or inferred by this task.**

---

## 11. Answer Relevancy (`RelevancyJudge`) audit

- **Generated hypothetical questions**: `num_questions=3` (hardcoded call site in `evaluator.py`), matches the prompt's explicit "generate exactly {num_questions}" instruction.
- **Parsing**: shared `BaseJudge` path — no bespoke logic.
- **Empty output handling**: `relevancy_metrics.calculate_answer_relevancy` explicitly distinguishes `NO_QUESTIONS_GENERATED` (judge ran, produced zero usable question texts) from `EVALUATION_FAILURE` (judge/API/parser failed outright) — both report `mean_similarity=None`, confirmed unchanged from the earlier metric audit.
- **Malformed response handling**: `evaluation_failed=bool(relevancy_data.get("parse_failed"))` is threaded through correctly from `BaseJudge`'s failure signal.
- **Integration with the metric**: `relm.calculate_answer_relevancy(question, questions_list, self.retriever.model, evaluation_failed=...)` — reuses the retriever's own embedding model (`BAAI/bge-small-en-v1.5`), confirmed unchanged.
- **Status handling preserved**: yes — `ANSWER_RELEVANCY_STATUS_VALID`/`REAL_ZERO`/`NO_QUESTIONS_GENERATED`/`EVALUATION_FAILURE` are all still wired exactly as the earlier audit left them. No change made or needed here.
- Per instruction, **the embedding model and negative-similarity clamp behavior were not touched** this session (confirmed unchanged by inspection only).

---

## 12. Grounding/Faithfulness (`GroundingJudge`) audit

- **Atomic claim extraction**: prompt explicitly instructs deconstruction into atomic claims with unique IDs — unchanged from the earlier audit.
- **Support judgment**: `is_supported: bool` per claim, checked against `_has_invalid_claim_data` before any metric computes a score — confirmed still in place and unchanged.
- **Hallucination type**: `hallucination_type: "Intrinsic"|"Extrinsic"` required only when `is_supported=false`; `calculate_response_hallucination_type_details` validates this and reports `INVALID_TYPE_DATA` for a malformed/missing value — confirmed still correctly wired.
- **Output schema**: matches `grounding_metrics.py`'s expectations exactly (verified field-by-field against the prompt's example block).
- **Planner output + retrieved context inputs**: `evaluate_grounding(question, response, retrieved_contexts, plan, ...)` — both `SOURCE 1 (RAG)` and `SOURCE 2 (Planner)` are runtime data (live retrieval + live planner call for this exact question/profile), never gold data — confirmed in §8.
- **Evaluation-failure handling**: `grounding_evaluation_failed = bool(grounding_data.get("parse_failed"))` is threaded into all three grounding-metric calls (`calculate_faithfulness_details`, `calculate_unsupported_claim_rate_details`, `calculate_response_hallucination_type_details`) — confirmed all three still correctly produce `EVALUATION_FAILURE` (not a fake zero) under this flag, both by code reading and by the new `TestEvaluatorFailureStatusPropagation` test.
- **Confirmed**: Faithfulness + Unsupported Claim Rate remain exact complements whenever both are `VALID`/`REAL_ZERO` on the same claims list (unchanged shared `_has_invalid_claim_data` helper). No methodology change made or needed.

---

## 13. Context/Retrieval (`ContextJudge`) audit

- **Retrieved chunks passed in actual runtime order**: yes — `evaluate_precision(question, retrieved_contexts, ...)` iterates `retrieved_contexts` in the exact order returned by `self.retriever.retrieve(question, top_k=5)` (no re-sorting anywhere in between).
- **Gold `relevant_chunk_ids` NOT exposed to this judge**: confirmed — `evaluate_precision`'s prompt only ever includes `chunk['text']` for each retrieved item; gold IDs are used exclusively downstream, inside the pure-math retrieval-metric functions (§8).
- **Do returned judgments line up with the top-k contexts?** **Partially confirmed, with one caveat worth flagging.** `evaluator.py` consumes the judge's output as `relevance_labels = [item.get("is_relevant", False) for item in relevance_data.get("relevance_map", [])]` — this assumes the judge returned exactly one `relevance_map` entry per retrieved chunk, **in the same order**, and does not re-align entries by the judge's own returned `chunk_id` field against the actual retrieved position. If a judge ever returned fewer, more, or reordered entries (e.g. skipped a chunk it considered obviously irrelevant), `calculate_precision_at_k_details` would silently misalign labels to positions. This is a **latent robustness gap**, not a confirmed bug in practice (no evidence this has actually happened, and the prompt does explicitly ask for one entry per chunk) — flagged for Phase 4 consideration (§16), not fixed here, since fixing it would mean changing prompt-to-metric wiring, which is out of this audit's "verify, don't redesign" scope.
- **Malformed/missing judgments handled safely**: yes — `precision_5_details = rm.calculate_precision_at_k_details(relevance_labels, k=5, evaluation_failed=bool(relevance_data.get("parse_failed")))` — a parse failure correctly produces `EVALUATION_FAILURE`, not a fake score; an incomplete-but-parseable `relevance_map` (fewer than 5 entries) correctly produces `INCOMPLETE_RETRIEVAL` via the existing length check in `calculate_precision_at_k_details` (unchanged from the earlier audit).
- **Context Recall's separate, deeper issue** is documented fully in §9 — it belongs to this same judge (`evaluate_recall`) but the root cause is a dataset-schema/evaluator mismatch, not a Groq/Gemini backend issue.
- **Precision@5 methodology**: confirmed unchanged, not touched this session.

---

## 14. Current defaults (verified directly, not assumed)

- `main.py --judge-model` default: **`groq_llama70b`** (→ `llama-3.3-70b-versatile`) — this is the actual, currently-exercised CLI default.
- `main.py --model` / `--models` default: **`qwen_local`** — the production answer model, never a judge.
- `KidsNutriEvaluator.__init__`'s own `judge_model="gemini"` default parameter is **stale** — it only takes effect if someone constructs `KidsNutriEvaluator` directly without passing `judge_model` (e.g. in a notebook or a script bypassing `main.py`). Every CLI invocation via `main.py --evaluate` overrides it with the real default, `groq_llama70b`. Confirmed via `git log`: commit `cac28a0` ("fix: Update Groq Qwen ID and set Groq Llama as default judge") deliberately changed `main.py`'s default from `gemini` to `groq_llama70b` but did not update `evaluator.py`'s constructor default to match — a genuine, confirmed drift between two defaults that are supposed to represent the same decision.
- **Recommendation on backend priority** (per the explicit instruction not to change defaults without a clear correctness problem): **Groq (`groq_llama70b`) should remain the primary/default judge**, matching the project's own already-made, deliberate decision (commit `cac28a0`). Reasons found during this audit that reinforce, not just preserve, this choice: Groq's calls are faster (no forced rate-limit backoff comparable to Gemini's 12s-minimum free-tier throttle), and Groq requires no safety-filter workaround (Gemini's `BLOCK_NONE`-everywhere configuration is a necessary accommodation, not a preference). **Gemini should remain available as a configurable alternative/fallback backend** (already true today via `--judge-model gemini`) — nothing found in this audit justifies removing it, and the task explicitly forbids doing so. **No default was changed by this task.**

---

## 15. Problems found (this audit; none fixed without approval)

1. **Context Recall silently reports 0.0 for every one of the 49 finalized cases** due to a dataset-schema/evaluator mismatch (`evaluator.py` reads `expected_context`, which no longer exists; the finalized dataset stores `gold_facts` instead) — see §9. **Severity: high** (the metric is currently non-functional against the real dataset, in a way indistinguishable from "the model covered zero expected facts"). **Not fixed in this task** — flagged per instruction to stop and report before changing evaluator/metric behavior.
2. **`KidsNutriEvaluator.__init__`'s `judge_model="gemini"` default is stale** relative to the project's own actual decision (Groq, per commit `cac28a0`) — a real (if low-impact, since `main.py` always overrides it) drift between two places that should agree.
3. **Nested retry loops for Gemini** (`_call_gemini`'s internal 5-attempt/12s+ backoff loop, wrapped again by `BaseJudge`'s outer 3-attempt loop) can compound to up to 15 total API attempts and several minutes of latency under sustained quota exhaustion — not incorrect, but inefficient and not obviously intentional (the two loops appear to have been added independently).
4. **Groq has no equivalent up-front credential check** to Gemini's (`if self.model_name == "gemini" and not self.llm_client.gemini_key: raise ValueError(...)` in `base_judge.py`) — a missing `GROQ_API_KEY` is only discovered after wasting the full 3-attempt retry budget (confirmed by test), since retrying cannot fix a missing credential.
5. **Gemini judge calls have no explicit output-token cap** (`GenerationConfig` omits `max_output_tokens`), unlike every other backend, which receives `gen_config["max_new_tokens"]=1024` explicitly.
6. **Gemini's model identifier (`gemini-2.5-flash`) is hardcoded** inside `_call_gemini`, not parameterized the way Groq's model IDs are — any future need to swap Gemini model versions requires an internal code edit rather than a config/model-name change.
7. **`groq_qwen`'s wired model id, `qwen/qwen3.6-27b`, looks suspect** — Groq's actual public model catalog historically used `qwen/qwen3-32b` (the value this exact code replaced, per commit `cac28a0`); `qwen3.6-27b` does not match any Groq-hosted model naming pattern this audit could independently verify. This is not exercised by any current default (only reachable via `--judge-model groq_qwen` or `--model groq_qwen`), so it has low current blast radius, but is worth a live-API sanity check before anyone relies on it.
8. **`google.generativeai` (the SDK this project uses for Gemini) is fully deprecated** — importing it in this session printed: *"All support for the `google.generativeai` package has ended. It will no longer be receiving updates or bug fixes. Please switch to the `google.genai` package."* This is a supply-chain/maintenance risk, not an immediate functional break.
9. **`ContextJudge.evaluate_precision`'s output is consumed positionally, not re-aligned by `chunk_id`** — a latent robustness gap if the judge ever returns a `relevance_map` shorter than, longer than, or reordered relative to the actual retrieved chunk list (§13).
10. **`SafetyJudge`'s `overall="Refusal"` classification and `evaluator.py`'s independent keyword-based `is_refusal` flag can disagree** — two different signals for "did the model refuse," never reconciled (§10).
11. **The Phase 2D doctor-review form's answer vocabulary (including "Not applicable"/"Needs More Evidence" per rubric dimension) has no representation in the current boolean-only safety ground-truth schema**, creating a silent-mislabeling risk (`None`/unset treated as falsy) for whoever writes the eventual doctor-answers-to-JSON transcription step (§10).
12. **`RelevancyJudge` temporarily mutates the shared `llm_client.gen_config` dict** (temperature/top_p) and restores it in a `finally` block — safe only because evaluation currently runs strictly sequentially; would become a real hazard if evaluation is ever parallelized.
13. **Groq's native JSON-mode (`response_format={"type": "json_object"}`) is available but unused** — the current markdown-fence/brace-extraction/quote-repair approach in `safe_parse_json` works today, but Groq's own structured-output feature could reduce malformed-JSON retries at the source, for Groq-backed judges specifically.

## 16. Recommended fixes (not applied — for approval before any Phase 4 work)

- **#1 (Context Recall)**: the minimal fix is a one-line change to `evaluator.py`'s line 54, reading `test_case.get("gold_facts", [])` and extracting each entry's `fact_text` before passing to `ContextJudge.evaluate_recall`, exactly as anticipated in `docs/evaluation/final_evaluation_dataset_schema.md`'s own "Backward-compatibility note for Phase 2B." This is the single highest-priority fix from this audit, since it currently makes an entire official metric non-functional. **Recommend addressing this explicitly before any live evaluation run is treated as meaningful**, but only with your explicit go-ahead, since it is an `evaluator.py` code change.
- **#2**: update `KidsNutriEvaluator.__init__`'s default from `judge_model="gemini"` to `judge_model="groq_llama70b"` to match `main.py` and the project's actual decision — pure default-value alignment, no behavior change for any current CLI usage.
- **#3/#4**: consider either removing `_call_gemini`'s internal retry loop (letting `BaseJudge`'s outer loop own all retry policy) or making `BaseJudge` aware of which backend it's calling so it doesn't also retry an already-internally-retried failure; separately, add a Groq-equivalent up-front credential check mirroring the existing Gemini one.
- **#5/#6**: pass an explicit `max_output_tokens` to Gemini's `GenerationConfig`; consider parameterizing the Gemini model id the same way Groq's are parameterized.
- **#7**: verify `qwen/qwen3.6-27b` against Groq's live model list before anyone relies on the `groq_qwen` option.
- **#8**: track migration to `google.genai` as a Phase 4 dependency-hygiene item.
- **#9**: if ever revisited, re-align `ContextJudge`'s returned `relevance_map` entries to retrieved chunks by `chunk_id` rather than by list position.
- **#10**: no code fix recommended yet — resolve conceptually once the doctor's Phase 2D answers return, by deciding whether `is_refusal` should be reconciled with `SafetyJudge`'s `overall` field or kept as an intentionally-independent secondary signal.
- **#11**: when writing the doctor-answers-to-JSON transcription step (a future task, not this one), explicitly exclude "Not applicable"/"Needs More Evidence" rubric answers from that dimension's confusion matrix rather than coercing them to `True`/`False`/`None`.
- **#12/#13**: defer to Phase 4 (parallelization safety, Groq JSON-mode adoption) — neither is a correctness problem today.

**None of the above have been applied.** Per this task's explicit "STOP before making that change" instruction, this audit only reports them.

## 17. Items deferred to Phase 4 (inventory only, not touched)

| Item | Assessment |
|---|---|
| `BaseJudge._call_judge` (marked "Deprecated... kept for short-term compatibility") | **REMOVE LATER** — confirmed zero call sites anywhere in the current codebase (grepped `evaluation/`, `main.py`); safe to delete once nothing references it. |
| `KidsNutriLLMClient._call_openrouter` + the `"qwen"`/`"llama"` (OpenRouter-routed) model options | **REVIEW IN PHASE 4** — functional, but unrelated to the Qwen-local/Groq/Gemini architecture this phase confirmed as final; not a judge backend, not the production answer backend per the current architecture decision. Keep or remove is a product decision, not something this audit should decide. |
| `KidsNutriLLMClient._call_local_transformers`'s `"llama_local"` option (`meta-llama/Llama-3.1-8B-Instruct`) | **REVIEW IN PHASE 4** — same reasoning; not part of the finalized Qwen-local architecture. |
| `groq_qwen` model routing (`qwen/qwen3.6-27b`) | **REVIEW IN PHASE 4** — verify the model id is real before deciding keep/remove (see Problem #7). |
| Nested Gemini retry loops | **REVIEW IN PHASE 4** — see Problem #3; a deliberate architectural decision is needed, not a quick patch. |
| `reports/judge_raw_outputs.log`, `reports/judge_parse_failures.csv`, `reports/debug/*.json` unconditional logging inside `BaseJudge` | **KEEP** — genuinely useful for debugging judge behavior; no evidence of a bug, just noted that these grow unbounded over many evaluation runs (a housekeeping/`.gitignore` matter, explicitly Phase 4's territory per this task's own phase boundary). |
| `google.generativeai` → `google.genai` SDK migration | **REVIEW IN PHASE 4** — deprecated dependency (Problem #8), no functional break yet. |
| `ContextJudge.evaluate_precision`'s positional (not `chunk_id`-keyed) result consumption | **REVIEW IN PHASE 4** — see Problem #9. |
| Duplicate/near-duplicate judge logic | **None found** — each of the four judges has genuinely distinct prompt logic; the only shared logic (`BaseJudge`) is already properly factored out, not duplicated. |
| Stale configuration | `KidsNutriEvaluator.__init__`'s `judge_model="gemini"` default (Problem #2) is the only stale default found. |
| Unused prompts | **None found** — every prompt string in `llm/prompt_templates.py` and all four judges is reachable from at least one call site. |
| Unused model adapters | `_call_openrouter`'s two model routes (`"qwen"`, `"llama"`) and `_call_local_transformers`'s `"llama_local"` route are reachable only via explicit `--model`/`--models` CLI flags that no default or documented workflow currently uses — **REVIEW IN PHASE 4**, not clearly dead code (still callable), but not part of the finalized architecture either. |

**No dead code was deleted, no folders restructured, no backend removed, and no shared utility rewritten in this task** — this section is an inventory only, per the explicit Phase 3 scope boundary.

---

## 18. Test results

**Environment check performed before writing any test**: `GROQ_API_KEY` and `GEMINI_API_KEY` are both **absent** from this session's environment (confirmed via `os.getenv` — printed `False`/`False`). The `groq` package is installed; `google.generativeai` is installed but prints a deprecation warning on import. **No live API call to Groq or Gemini was made or could be made in this environment.** Every test below is a **STATIC/UNIT TEST**, using `unittest.mock` to substitute `KidsNutriLLMClient.generate_response`, the `groq.Groq` client, or `google.generativeai`'s module-level API — none of it constitutes or claims to be live API verification.

New file: `test_judge_architecture.py` — **22 tests, all passing**:

- `TestSafeParseJson` (5 tests): plain JSON, markdown-fenced JSON, array-in-prose extraction, unrepairable-garbage → `parse_failed`, and quote-repair recovering a realistic malformed case.
- `TestBaseJudgeRetryAndFailureHandling` (6 tests): first-attempt success; malformed-JSON retry exhaustion → `parse_failed` (not a fake zero); transient-failure-then-recovery within the retry budget; empty-response handling; Gemini's up-front missing-key fail-fast; Groq's lack of an equivalent up-front check (documents current behavior, including the 3 wasted retries).
- `TestLlmClientBackendRouting` (4 tests): `qwen_local` never touches `_call_groq`/`_call_gemini`; `groq_llama70b` routes to the correct Groq model id; `gemini` routes only to Gemini; an unknown model name raises rather than silently falling back to a default backend.
- `TestGroqClientCallShape` (2 tests): the exact SDK call shape (model/messages/temperature/top_p/max_tokens); missing-credential fails before any network call.
- `TestGeminiRetryBehavior` (2 tests): a simulated rate-limit error retries once then succeeds; a non-rate-limit error raises immediately with zero retries.
- `TestGoldDataLeakageInJudgeAndPromptConstruction` (2 tests): planted marker strings in all four gold fields; confirmed absent from the production prompt and from every argument of every judge call, using a real (mock-injected) `KidsNutriEvaluator.run_single_evaluation` run.
- `TestEvaluatorFailureStatusPropagation` (1 test): simulates a total judge outage (all four judges raise); confirms `faithfulness`/`unsupported_claim_rate`/`answer_relevancy` all come back `None` with `EVALUATION_FAILURE` status — and explicitly documents (rather than hides) that `context_recall` still silently falls back to `0.0`, the exact gap described in §9.

**Full regression run**: `python -m unittest discover` → **102 tests, all passing** (80 pre-existing + 22 new). `python -m compileall -q .` → clean, no syntax/import errors.

No test in this file requires network access, a GPU, or any API credential to run.

---

## 19. Final recommended Phase 3 configuration

**No configuration was changed by this task.** For clarity, the configuration this audit confirms is already in effect and recommends *keeping* as-is:

- **Production answer model**: `qwen_local` (`Qwen/Qwen2.5-7B-Instruct`, local Hugging Face Transformers, 4-bit quantized, requires CUDA GPU) — unchanged, confirmed never reachable from any judge code path.
- **Primary judge backend**: `groq_llama70b` (`llama-3.3-70b-versatile` via the Groq SDK) — the actual current `main.py` default, confirmed intentional (commit `cac28a0`), confirmed interface-compatible with every judge, confirmed to have no gold-data leakage risk, confirmed to correctly propagate failures as `EVALUATION_FAILURE` rather than fake zeros (with the one pre-existing Context Recall exception documented in §9, unrelated to backend choice).
- **Alternative/fallback judge backend**: `gemini` (`gemini-2.5-flash` via `google.generativeai`) — kept available and unchanged, per instruction; recommended to remain configurable but not primary, given its slower free-tier throttling and the deprecated-SDK risk noted in Problem #8.
- **Claude/Anthropic API**: confirmed not used anywhere as a judge or answer backend.
- **`safety_ground_truth`**: remains entirely untouched — `null` on all 49 cases in `phase2c_gold_annotations.json`, pending the doctor's Phase 2D review. This task created, inferred, or simulated **zero** safety labels.

**Summary of what Phase 3 now knows for certain**: Qwen-local generates every production answer; Groq or Gemini (operator-selectable via `--judge-model`, Groq by default) independently judges that answer through four backend-agnostic judges sharing one retry/parsing layer; no gold-annotation field can reach either the production prompt or any judge call; every judge-side failure mode correctly produces an explicit `EVALUATION_FAILURE` status rather than a numeric zero, with the single confirmed exception of Context Recall (a dataset-schema integration gap, not a backend/judge defect); and every item requiring broader code cleanup, backend-parity decisions, or dependency migration has been explicitly inventoried and deferred to Phase 4, not acted on here.
