# Latency — Final Audit

**Status: research/inspection only. No code, dataset, notebook, model configuration, instrumentation, or reports modified.**

Everything below was re-verified directly against the current repository this turn — no reliance on the prior latency audit's conclusions or on remembered assumptions about which model is "the" production model.

---

## 1. Actual Project Model Architecture — the real production/request path

Traced `main.py` directly (the actual CLI entry point), not `evaluator.py` in isolation.

```
User (`--ask <query>`)
  → retriever.retrieve(query, top_k=5)                    [rag/retriever.py::KidsNutriRetriever.retrieve
                                                              → rag/services/retrieval_service.py::RetrievalService.retrieve]
  → (if diet-plan intent detected) planner.generate_meal_plan(profile)  [planner/diet_planner.py::DietPlanner]
  → generate_llm_prompt(...) or generate_qa_prompt(...)     [llm/prompt_templates.py]
  → client.generate_response(system_prompt, user_prompt, args.model)  [llm/llm_client.py::KidsNutriLLMClient.generate_response]
       → dispatches by model_name to _call_gemini / _call_openrouter / _call_local_transformers / _call_groq
  → response text printed to the user (main.py lines 121-123)
```

This is the exact same pipeline shape `evaluation/evaluator.py::run_single_evaluation` reimplements for batch scoring (confirmed by direct comparison of both files) — so conclusions drawn from `evaluator.py`'s structure do carry over to the real production path; they are not evaluation-only artifacts.

**Which model actually produces the final answer, and where is it selected?**
- `main.py` line 29: `parser.add_argument("--model", type=str, default="gemini", ...)` — **the CLI's own default production model is Gemini** (`gemini-2.5-flash`, set in `llm_client.py::_call_gemini` line 230).
- `llm/llm_client.py::KidsNutriLLMClient.__init__` line 9: `default_model="gemini"` — the client's own internal default, independent of the CLI, is also Gemini.
- The final-answer-producing function is unambiguous: `KidsNutriLLMClient.generate_response` (line 35), which returns `(response_text, latency)`.
- **This is user-overridable per the `--model` flag** to any of: `qwen`, `llama` (OpenRouter), `qwen_local`, `llama_local` (local Transformers), `groq_llama70b`, `groq_llama8b`, `groq_qwen` (Groq). Gemini is the default, not the only option — the architecture is explicitly designed to let several candidate answer-generation backends be swapped in.

**Production/candidate-answer models vs. evaluation judge model — a real, important distinction, verified directly:**
- `main.py` line 25: `parser.add_argument("--models", type=str, default="gemini,qwen_local", ...)` — the `--evaluate` benchmark's default is to compare **two candidate answer-generation models against each other**: Gemini and a locally-run Qwen.
- `main.py` line 26: `parser.add_argument("--judge-model", type=str, default="groq_llama70b", ...)` — **the evaluation judges (Context, Grounding, Relevancy, Safety — all four, per `evaluator.py::__init__`) default to a separate, single model: Groq-hosted Llama-3.3-70B, not Gemini.**
- These are architecturally distinct roles using the same `KidsNutriLLMClient.generate_response` machinery but for entirely different purposes: **answer-generation models** (`gemini`, `qwen_local`, or whichever the user selects/benchmarks) produce the thing a real user reads; the **judge model** (Groq by default) never produces user-facing content — it only scores.

**Conclusion for Part 1**: Gemini is the real, verified default for the user-facing answer in both the live `--ask` path and as one of the two models benchmarked by default under `--evaluate`. It is not an assumption carried over from old notes — it is the literal `argparse` default in the current `main.py`. But it is one of several interchangeable candidate backends, not an exclusive architectural choice, and the judge model is confirmed architecturally separate (Groq by default) and should not be treated as user-facing latency.

## 2. All Current Latency Measurements — exhaustive, re-verified via full-repo search this turn

| # | File / Function | Starts timer | Stops timer | Included | Excluded | Stored | Reported | Type |
|---|---|---|---|---|---|---|---|---|
| 1 | `llm/llm_client.py::generate_response` (lines 40, 88-89) | `time.time()` before model dispatch | `time.time()` after the call returns | The single answer-generation LLM call (incl. any internal retry/backoff sleep inside `_call_gemini`) | Retrieval, planning, prompt construction, judge calls | Returned as `(response_text, latency)` | `main.py` (printed directly, `--ask` path); `evaluator.py` → `comparator.py` (`--evaluate` path) | **Both** — this exact function is used by the live production path (`--ask`) and by the evaluation harness |
| 2 | `evaluation/evaluator.py` line 242 | n/a (stores #1's value) | n/a | Same as #1 | Same as #1 | `result["latency"]` per test case | `comparator.py` | Evaluation-only storage of #1 |
| 3 | `evaluation/comparator.py` lines 315, 343 | n/a | n/a | Averages #2 across all cases for one model | n/a | `avg_latency` | `"Average Latency"` column, `final_model_comparison.csv` | Evaluation-only aggregation |
| 4 | `evaluation/judges/base_judge.py::call_llm_with_retry` (lines 102, 110, 127) | `time.time()` per attempt | `time.time()` after each attempt | One judge-LLM call attempt (Context×2, Grounding, Relevancy, Safety — 5 calls/case) | Everything else | `_log_metadata` → `reports/debug/llm_call_metadata_latest.json` (**overwritten every call — not an aggregate log**) | Nowhere aggregated; not surfaced to `evaluator.py` or any report | **Evaluation-only instrumentation**, and correctly so — see Part 6 |
| 5 | `rag/services/metrics_service.py` + `rag/services/retrieval_service.py` (lines 107-194) | `time.perf_counter()` per retrieval stage | Same, per stage | Embedding, cache lookup, FAISS, BM25, fusion, rerank, total — genuinely populated on every `retriever.retrieve()` call from both `--ask` and `--evaluate` | Nothing within retrieval itself | `RetrievalService.metrics.history` (in-memory), queryable via `retriever.service.metrics.get_summary()` | **Nowhere** — confirmed via full-repo search: no caller in `evaluator.py`, `comparator.py`, or `main.py` ever reads this | Real production-relevant instrumentation, fully built, never surfaced |
| 6 | `rag/services/cache_service.py` line 89 | n/a | n/a | A cache-entry `"timestamp": time.time()` field | — | Cache entry metadata | Cache-internal only | **Not a latency measurement** — ruled out; this is expiry bookkeeping, unrelated to Part 2's scope |
| 7 | `verify_groq.py` lines 31-33 | Same as #1 (reuses `generate_response`) | Same | Same as #1 | Same as #1 | Printed to console | Console only | Standalone dev-verification script, not part of the evaluation or production pipeline |

## 3. What the Current Reported "Average Latency" Actually Means

Traced precisely (row 1-3 above): it is **the wall-clock time of a single call to the answer-generation model's API/inference function, averaged across test cases, for whichever model is currently selected** (`gemini` or `qwen_local` by default, or any other `--model`/`--models` value). It is:
- **Not** production *request* latency (excludes retrieval + planning + prompt construction, all of which a real user waits through in the `--ask` path).
- **Not** full pipeline latency (same reason).
- **Not** evaluation latency (correctly excludes judge calls — see Part 6).
- It **is**, precisely and only, **generation-call latency for the answer-producing model** — genuinely useful, but the name "End-to-End Latency" overclaims scope relative to what's measured. This is confirmed misleading, not merely a stylistic nitpick — see Part 5's literature comparison.

## 4. Do We Even Need a Latency Metric?

Yes. Given the confirmed architecture — multiple interchangeable answer-generation backends (`gemini`, `qwen_local`, Groq-hosted models, OpenRouter models, local Transformers) genuinely being compared against each other for a real chatbot use case — response speed is a legitimate, practically important axis for KidsNutriBite's research question ("which model should power this pediatric chatbot"). A parent waiting for dietary guidance cares about latency, not just accuracy/safety. Removing it entirely (option D) would drop real, decision-relevant information from the final comparison. The question is not *whether* to measure latency but *what exactly* is being measured and whether the name matches it.

## 5. Research Comparison

One search-level check this turn (not a full multi-paper primary-source fetch, appropriately scoped given Part 5's own "only if needed" framing) confirms the RAG/LLM-serving literature uses **multiple, genuinely distinct latency measures**, not one universal standard:
- **Time-to-First-Token (TTFT)** — retrieval + prefill time until the first output token; the user-experience-critical measure in interactive settings.
- **End-to-End Latency / Response Time** — explicitly defined across the sources found as covering **retrieval + prompt construction + full generation of all tokens** (one characterization: "Response Time... measured from the moment the query is submitted to the completion of the full model response, including subgraph retrieval, prompt construction, LLM prefill, and token generation").
- **TPOT (Time Per Output Token) / inter-token latency** — post-first-token generation speed.
- **Retrieval Latency** — reported separately in several sources, sometimes noted as a large share (~41-47%) of both TTFT and end-to-end latency.

**This is a search-engine-level synthesis across several sources, not independent full-text verification of one pinned primary paper** — flagged honestly, consistent with this audit series' evidentiary standard. But the finding is directly useful and consistent across sources: **wherever "End-to-End Latency" is defined in this space, it explicitly includes retrieval — which KidsNutriBite's current measurement does not.** The literature does not converge on one single "the" latency metric overall (TTFT vs. end-to-end vs. TPOT serve different purposes), so I am not asserting a single research-mandated definition — only that *if* the name "End-to-End Latency" is kept, its scope is inconsistent with how that specific term is used wherever I found it defined.

## 6. Cross-Model Check

Re-examined specifically per the instruction not to over-focus on Gemini unless it's genuinely part of the production/benchmark set — confirmed it is (Part 1). Restating the retry-inflation finding with the now-confirmed production/judge distinction in mind:

- **Answer-generation models actually benchmarked by default**: `gemini`, `qwen_local` (the `--models` default). Both are legitimate production-candidate targets for a latency comparison.
- **`_call_gemini`** (verified, `llm_client.py` lines 238-251): internal retry loop, `max_retries=5`, exponential backoff `12.0 * 1.5^attempt` — sleeps of 12.0s/18.0s/27.0s/40.5s across attempts 0-3, summing to 97.5s, included inside the timed window whenever the free-tier 5-RPM quota is hit.
- **`_call_local_transformers`** (used by `qwen_local`, the other default-benchmarked model): no network call, no retry logic — no equivalent inflation risk.
- **`_call_openrouter`, `_call_groq`**: confirmed, no retry/backoff loops in either path.
- Since `gemini` and `qwen_local` are the two models actually compared side-by-side by default in `final_model_comparison.csv`'s "Average Latency" column, this asymmetry is a genuine comparability problem **for the models that are actually benchmarked**, not a hypothetical concern about an unused model. This finding is reaffirmed, not walked back, now that Part 1 has confirmed Gemini's real role.
- **The judge model (Groq, default) is correctly excluded from this metric** — it never produces user-facing content, so its latency is rightly not part of a "how fast does the chatbot answer" figure. This is good design, not a gap, contrary to how the prior latency audit framed judge-exclusion as unconditionally a problem; re-examined here, it is not.

## 7. Final Recommendation

**KEEP WITH RENAMING**

- **What the final metric would measure**: exactly what's measured today, unchanged in scope — the wall-clock time of the single answer-generation model call — but under an accurate name (e.g., "Answer Generation Latency" or "Final Response Latency") instead of "End-to-End Latency," which the literature check (Part 5) confirms implies a broader scope (including retrieval) than what's actually captured.
- **Why useful**: genuinely informs the real research question (comparing candidate answer-generation backends for a production chatbot) and requires no architectural change to keep.
- **Why not "SIMPLIFY"**: the current measurement is already the simple, single-call version — there's nothing further to strip down; the problems are a naming mismatch and a data-quality defect, not excess complexity.
- **Why not "REMOVE"**: latency is a real, decision-relevant axis for comparing multiple genuinely interchangeable production backends — confirmed by the architecture itself, not assumed.
- **What exact code currently measures**: `llm/llm_client.py::generate_response`'s `time.time()` delta around the dispatched model call, propagated through `evaluator.py`'s `"latency"` field and averaged in `comparator.py`'s `"Average Latency"` column.
- **Is code correction required?** Yes, one — separate from the rename: the Gemini retry/backoff sleep (confirmed, up to 97.5s) is currently included in the timed window and inflates only one of the two default-benchmarked models, undermining the very comparison this metric exists to support. This should be fixed (e.g., excluding `time.sleep()` duration from the measured latency) before the renamed metric can be trusted, exactly the same "rename alone isn't enough, the underlying number must be trustworthy" pattern already applied to Unsupported Claim Rate and the response-level hallucination metrics earlier in this audit.
- **Is a research citation needed?** No single citation is warranted or honest — the literature check found multiple valid latency definitions (TTFT, end-to-end, TPOT), not one canonical formula to cite as "the" source. The rename should be justified by internal accuracy (matching what's measured) rather than an external citation.
- **Does it belong in the final paper's metric table?** Yes, under the corrected name, once the retry-sleep contamination is fixed. Optionally, the already-built but unused `MetricsService` retrieval-stage data (Part 2, row 5) could be surfaced as a second, separate "Retrieval Latency" figure if a fuller latency picture is wanted — this is an addition, not a requirement for fixing the current metric.

## 8. Exact Files/Functions Inspected This Turn

`main.py` (full file); `llm/llm_client.py` (full file, all `_call_*` methods); `llm/groq_client.py` (grepped for retry logic — none found); `rag/retriever.py` (full file); `rag/services/retrieval_service.py` (grepped for `MetricsService` usage, lines 12/39/55/107-194); `rag/services/metrics_service.py` (full file); `rag/services/cache_service.py` (line 89 only, ruled out as unrelated); `evaluation/evaluator.py` (lines 47-90, 242); `evaluation/comparator.py` (lines 315, 343); `evaluation/judges/base_judge.py` (lines 88-149); `verify_groq.py` (lines 31-33); full-repo grep for `time.time()`/`perf_counter`/`latency` (case-insensitive) across all `.py` files to confirm exhaustiveness of Part 2's table.

## 9. What Should Be Changed, If Anything (pending your approval — nothing implemented)

1. Rename "End-to-End Latency" → an accurate name reflecting generation-call-only scope (e.g., "Answer Generation Latency").
2. Fix the Gemini retry/backoff sleep contamination so the renamed metric is trustworthy and fairly comparable across the actually-benchmarked models (`gemini`, `qwen_local`, and any others selected).
3. Optional, separate addition: surface the already-built `MetricsService` retrieval-stage summary as its own reported figure, if a fuller latency picture is desired — not required to fix items 1-2.

Nothing has been implemented. This is the final item in the fixed 16-metric audit order. Waiting for your approval before touching any code.
