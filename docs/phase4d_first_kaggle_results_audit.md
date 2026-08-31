# Phase 4D — Investigation of the First Real Kaggle Evaluation Run

**Scope: investigation only.** No Python code, notebook, dataset, gold annotations, RAG data, FAISS index, planner, metric formulas, judge prompts, or configuration was modified while producing this report. Nothing was staged, committed, or pushed.

**Evidence used:** the attached Kaggle-run notebook (`c:\Users\DINESH\Downloads\notebook8c07a14554.ipynb`, executed on 2026-08-30, commit `7f81a45d9576447b628229d1986583f9a26ff54d` per its own printed run summary — confirmed below to be the actual merge commit of PR #7, `phase4c-kaggle-notebook` → `main`), the current repository's source code (read-only), and one pre-existing repo file, `reports/context_recall_failure_analysis.md` (historical, pre-dates this dataset — see §13).

**Evidence explicitly NOT available and not reconstructed:** `ragas_report.csv`, `detailed_evaluation_records.csv`, `retrieval_trace.csv`, `judge_raw_outputs.log`, and the `reports/debug/*.json` per-call metadata files from this specific run were **not provided** and are **not** in the notebook's cell outputs (the notebook only shows the printed stdout log and the final aggregated tables). Wherever this report needed those files and didn't have them, that is stated explicitly rather than reconstructed from the aggregate numbers.

---

## 1. Executive summary

The 49-case evaluation **did complete** — Qwen generated an answer for all 49 cases (no crashes, no tracebacks, no CUDA errors), and retrieval ran for all 49 cases. But the run's Groq judge backend (`openai/gpt-oss-120b`, not the code's nominal `llama-3.3-70b-versatile` — see §16) hit its **daily token quota (TPD)** partway through, causing **987 rate-limit (429) errors** and **340 outright judge-call failures** (3/3 retries exhausted) across the whole run. `Context Precision Status` — the one Layer-1-judge status this run actually tracked per case — shows this landed on **32 of 49 cases (65%)**.

**Context Recall = 0.2114 is not a trustworthy, clean measurement of RAG quality.** It is corrupted by a real, code-level defect: `calculate_context_recall()` has **no failure/status path at all** — a judge call that fails outright and a judge call that legitimately finds zero facts present produce the *exact same* input (`facts_list = []`) and the *exact same* output (`0.0`). Every one of this run's ~65%-failure-rate judge calls to `ContextJudge.evaluate_recall` that failed outright therefore silently became a **hard 0.0** baked into a metric the code otherwise treats as always-valid. This is compounded by a second, separate, real design issue: **11 of the 49 cases have no RAG ground truth by design** (their knowledge is structured-DB-sourced), yet their `gold_facts` are still sent to `ContextJudge.evaluate_recall` and checked against RAG-retrieved context that was never authored to contain them.

Meanwhile, **the retrieval system itself looks good**, not bad: reconstructing per-case retrieval quality directly from this run's own logged `RETRIEVAL_EVENT` data (verified against the dataset's gold IDs using the project's real metric functions, and cross-checked to reproduce the notebook's own reported status counts exactly — see §5) shows the canonical `source_id` was retrieved **in the top 5 for 32 of 38 (84%) RAG-grounded cases**, and **at rank 1 for 26 of 38 (68%)**. `MAP@5 = 0.5934` and `MRR@5 = 0.7298` are retrieval-only Layer-2 numbers that never touch a judge call — they are **trustworthy** and consistent with that 84%/68% figure.

**Direct answers to the 9 required questions are in §21 below.**

---

## 2. Exact Kaggle run configuration

From the notebook's own cells and outputs:

- **GPU:** Tesla T4, 14.56 GB VRAM, confirmed by Section 1.
- **Project source:** Kaggle Dataset `dpavankrishna/nutrikids`, nested path `/kaggle/input/datasets/dpavankrishna/nutrikids/nutrikid_Agentic`, extracted to `/kaggle/working/kidsnutribite_project`. **Note:** the run's Section 2 cell was edited from what we shipped — `KAGGLE_INPUT_ROOT` was changed to `"/kaggle/input/datasets/dpavankrishna/"` and an extra `"nutrikid_Agentic"` path segment was added to `_find_input_dataset_dir`, and an extra un-numbered cell (`os.chdir("/kaggle/working")`) was inserted before it. These are environment-specific path adaptations, not logic changes, and are expected/harmless.
- **Project commit actually run:** the run's Section 13 summary printed `Project commit: 7f81a45d9576447b628229d1986583f9a26ff54d`. This hash **is real and is in our history** — `git cat-file -t 7f81a45d...` confirms it is the merge commit for **PR #7, `phase4c-kaggle-notebook` → `main`** (i.e. exactly the Phase 4C work, already merged to `main` by the time this ran). This is reassuring: the run used our intended, reviewed code — **not** a stale or divergent snapshot. (Side note: this also means the Kaggle dataset used for this run was **not** built via `git archive` the way we built the Phase 4C ZIP — a `git archive` output has no `.git` directory, so `git rev-parse HEAD` inside it would fail and the notebook would have printed "Project commit: unavailable." A real hash means this dataset's ZIP was built some other way, e.g. a full folder/`.git`-inclusive copy or a fresh `git clone`. Not a problem, just a process note for whoever builds the next Kaggle ZIP.)
- **Dependencies installed:** matches Phase 4C's Section 3 list; no install errors shown.
- **Secrets loaded:** `Groq key loaded: YES`, `Gemini key loaded: YES`, HF login succeeded.
- **Dataset loaded:** `EVALUATION_DATA` = 49 cases, `EVAL_001`..`EVAL_049`, 28/49 knowledge-only (`profile: null`), 0/49 with `safety_ground_truth` — all exactly as expected from the finalized Phase 4B/2C dataset.
- **Answer model:** `qwen_local` (`Qwen/Qwen2.5-7B-Instruct`, local, 4-bit) — confirmed the only model used to generate answers (`ANSWER_MODEL = "qwen_local"`, unedited).
- **Judge model (nominal):** `JUDGE_MODEL = "groq_llama70b"` (unedited in the notebook's Section 10 cell) — but see §16: the account's actual Groq model catalog does not list `llama-3.3-70b-versatile`, and every 429 error in the log explicitly names `openai/gpt-oss-120b` as the rate-limited model, not `llama-3.3-70b-versatile`.
- **Gemini:** smoke-tested successfully (Section 9), **not used** as the judge for the main 49-case run (`JUDGE_MODEL` stayed `"groq_llama70b"`).

## 3. Dataset summary

- 49 cases, `EVAL_001`–`EVAL_049`, confirmed loaded and matching the finalized Phase 2C/4B dataset (per the notebook's own Section 5 assertions, which the run's log shows passing).
- 38 cases have `relevant_chunk_ids` populated (RAG-grounded); 11 have `relevant_chunk_ids: null` (non-RAG, by design).
- All 49 cases have non-empty `gold_facts` (min 1, max 4, average 1.49, 73 total facts across the dataset) — see §7.
- `safety_ground_truth` is `null` on all 49 (doctor review, Phase 2D, still pending) — confirmed both from the dataset and from the run's own printout.

## 4. Retrieval metric results

From the run's final printed table:

| Metric | Value | Valid | Missing GT | Real Zero | Eval Failures |
|---|---|---|---|---|---|
| MAP@5 | 0.5934 | 38 | 11 | 6 | 0 |
| MRR@5 | 0.7298 | 38 | 11 | 6 | 0 |
| Recall@5 | 0.6634 | 38 | 11 | — | — |
| Context Precision | *(not in final table; per-case status only)* | 15 | — | 2 | **32** |

`Context Precision Status` (from the run's Section 12 output, aggregated across all 49 cases): **VALID: 15, REAL_ZERO: 2, EVALUATION_FAILURE: 32.** This is the only Layer-1-judge-dependent status this run's notebook actually surfaced, and it is the clearest direct evidence of how badly the Groq outage affected judge-dependent metrics — 32/49 = **65%** of Context Precision judge calls failed outright.

## 5. Context Recall analysis (root cause)

**The defect, verified directly against the current code** (`evaluation/metrics/grounding_metrics.py:309`):

```python
def calculate_context_recall(facts_list):
    if not facts_list:
        return 0.0
    supported_facts = sum(1 for f in facts_list if f.get("is_present", False))
    return supported_facts / len(facts_list)
```

`facts_list` comes from `evaluator.py`: `context_recall = gm.calculate_context_recall(recall_data.get("facts", []))`, where `recall_data = self.judges["context"].evaluate_recall(...)`.

`ContextJudge.evaluate_recall` (`evaluation/judges/context_judge.py:49`) returns one of three shapes:
1. `{"facts": []}` if `expected_contexts` (i.e. `gold_facts`) is empty — a legitimate "nothing expected" case. **Never happens in this dataset — all 49 cases have ≥1 gold fact (§3).**
2. `{"facts": [{"fact": ..., "is_present": ...}, ...]}` on a successful judge call.
3. `{"parse_failed": True, "error": "..."}` — **no `"facts"` key at all** — when `call_llm_with_retry` exhausts all 3 retries (`base_judge.py:137`).

`recall_data.get("facts", [])` on shape (3) silently returns `[]` — **structurally identical to shape (1)**. `calculate_context_recall([])` then returns `0.0` for both. **There is no `evaluation_failed` parameter on this function at all** (contrast this directly with `calculate_answer_relevancy(..., evaluation_failed=...)` and `calculate_faithfulness_details(..., evaluation_failed=...)`, which both explicitly thread a failure flag through to a distinct `EVALUATION_FAILURE` status with `score=None` — see §6/§9). Context Recall has no such path. A judge-call failure and a real "the answer used none of the expected facts" result are **indistinguishable** in this metric's output.

`comparator.py` then computes `avg_recall = df["context_recall"].mean()` **unconditionally over all 49 rows, with no status filter** (unlike every retrieval metric, which excludes `MISSING_GROUND_TRUTH`/`EVALUATION_FAILURE` rows via its own status-details dict before averaging). Every judge-call failure that collapsed to `0.0` is therefore counted in the average exactly as if it were a real, judged zero.

**Is this quantitatively enough to explain 0.2114?** A bounding calculation (explicitly a plausibility check, not a reconstruction of the real per-case values, which we don't have):
- Sum needed to hit the reported average: `0.2114 × 49 ≈ 10.36`.
- The 11 non-RAG cases (§6) are structurally very likely to score near 0 regardless of judge success, since their gold facts were never authored to exist in the RAG corpus.
- If a similar ~65% failure rate (matching the directly-observed Context Precision failure rate, since `evaluate_precision` and `evaluate_recall` are back-to-back calls on the *same* `ContextJudge` instance under the *same* Groq quota state) also hit `evaluate_recall` on the 38 RAG-grounded cases, roughly 24–25 of those 38 would also silently collapse to `0.0`.
- That leaves roughly 13–14 cases carrying the entire `10.36` sum — an average of **~0.74–0.80** among them, which is a perfectly ordinary, plausible real Context Recall score.

This is **consistent with, not proof of**, the failure-collapse explanation — we do not have the per-case `context_recall` column (§ evidence note at top) to confirm the exact count. But it shows the observed 0.2114 requires no assumption of poor RAG quality to explain; a judge failure rate matching what was directly observed elsewhere in the same run is sufficient on its own.

## 6. Answer Relevancy analysis

`calculate_answer_relevancy()` (`evaluation/metrics/relevancy_metrics.py`), unlike Context Recall, **does** have proper failure handling: it takes an explicit `evaluation_failed` parameter and returns `mean_similarity=None` + `status=EVALUATION_FAILURE` when the `RelevancyJudge` call failed, distinct from `NO_QUESTIONS_GENERATED` and from a genuine `REAL_ZERO`. `evaluator.py` passes `evaluation_failed=bool(relevancy_data.get("parse_failed"))` correctly.

`comparator.py`'s `avg_relevancy = df["answer_relevancy"].mean()` is *also* unconditional — but because failed cases store `None` (→ `NaN` in pandas) rather than `0.0`, pandas' `.mean()` **silently excludes them** (`skipna=True` by default) instead of averaging them in as zero. This is the statistically correct behavior by accident of pandas' default, not by an explicit exclusion in `comparator.py` — worth codifying explicitly rather than relying on pandas defaults, but not incorrect today.

**We cannot state how many of the 49 cases contributed to the `0.7579` mean** — the per-case `answer_relevancy_valid_question_count` field exists in `evaluator.py`'s per-case return dict but is not surfaced in `final_model_comparison.csv`, and we don't have `ragas_report.csv`/`detailed_evaluation_records.csv` to count it directly. What we *can* confirm: `Faithfulness` came back as literal `nan` in the same run (§9) — proof that the `GroundingJudge` (a *different* judge from `RelevancyJudge`) failed on effectively all 49 cases. Given both judges were hit by the same account-wide daily quota exhaustion, it is very plausible `RelevancyJudge` also had a high failure rate; the `0.7579` figure may be averaged over a substantially reduced N.

## 7. Judge failure analysis

Extracted directly from the run's full stdout log (`cell 22` of the attached notebook), by regex over `[!] API or Parse Error` / `[!] Max retries reached` lines:

- **Total `[!] API or Parse Error` lines: 1020**
  - **987** — HTTP 429 `rate_limit_exceeded` (Groq)
    - **986** of those explicitly say `tokens per day (TPD)` in the error body
    - **1** explicitly says `tokens per minute (TPM)`
  - **33** — `"Received empty response from API."` (a distinct failure mode raised by `base_judge.py:114` when the API returns a non-error but empty completion — not a rate-limit error; seen concentrated at the very start of the run, e.g. `EVAL_001`–`EVAL_004` in the transcript)
- **Total `[!] Max retries reached. Returning failure.` (an outright, un-recovered judge-call failure): 340**
- **Sample raw 429 error body** (verifies the model name directly — see §16):
  > `Rate limit reached for model 'openai/gpt-oss-120b' ... on tokens per day (TPD): Limit 200000, Used 199649, Requested 1422. Please try again in 7m42.672s.`
- All 49 `[i/49] Running Question ID: EVAL_XXX` markers are present — **no case was skipped**.
- **Precise per-case, per-judge-type attribution of these 1020 error lines is not reliable from this log.** `base_judge.py`'s error print (`print(f"[!] API or Parse Error (Attempt {attempt+1}/3): {e}")`) includes neither the case ID nor which of the 5 judges made the call — that detail exists only in `_log_metadata`'s write to `reports/debug/*.json`, which we don't have. Additionally, Python's `logging`-based `RETRIEVAL_EVENT` lines were observed to be interleaved out of the expected stdout order relative to `print()`-based lines in this same log (§14), a sign of stdout/stderr buffering differences between the two output paths — so line-position-based attribution of any kind in this log should be treated as approximate, not exact.

## 8. Groq quota analysis

The single most important number here is the **daily quota limit itself: 200,000 TPD** for `openai/gpt-oss-120b` on this account/tier, and the error text shows it climbing toward and past that ceiling (`Used 199649` in the sample above) as the run progressed. This is a **hard daily ceiling** — unlike a per-minute (TPM) limit, retries cannot recover from it within the same day; once crossed, every subsequent call to that model is guaranteed to fail for the retry window's duration. This is corroborated directly by the run's own **unofficial retrieval-relevance diagnostic** (`run_llm_judged_relevance_experiment`, which runs *after* the main 49-case loop and makes ~294 further judge calls sweeping K=3/5/10): its final printed table shows **`Context Recall: 0, 0, 0`** for K=3, K=5, **and** K=10 — i.e. by the time this diagnostic ran, literally every one of its judge calls failed, which is only explainable by total quota exhaustion, not partial degradation. This diagnostic is explicitly **not an official metric** (per its own docstring in `comparator.py`), but it is strong independent confirmation that the account's Groq quota was fully spent by the end of the run.

## 9. Qwen generation analysis

- `'Reusing cached local model' occurrences: 49` and `'max_new_tokens' warning occurrences: 49` — exactly one generation call per case, all 49 reached.
- `'Traceback' occurrences: 0`, `'CUDA out of memory': 0`, `'CUDA error': 0`, and zero non-judge-retry lines containing the word "Error" anywhere in the log.
- **Conclusion: no evidence of any Qwen generation crash or failure for any of the 49 cases.**
- The `Both 'max_new_tokens' (=1024) and 'max_length'(=20) seem to have been set. 'max_new_tokens' will take precedence.` warning is a benign HuggingFace `generate()` warning — it explicitly states `max_new_tokens` (1024, the intended value) wins; `max_length=20` is a leftover default the warning is flagging, not something that actually truncated output. **No evidence generation was truncated to 20 tokens.**
- **We cannot verify actual answer *text* quality or emptiness** — `evaluator.py` never prints the generated response to stdout, and we don't have `detailed_evaluation_records.csv` (which stores `Model Answer` per case). This is a genuine evidence gap, stated explicitly rather than assumed either way.

## 10. Per-case Context Recall table

**Not available.** Per-case `context_recall` scores, per-case `Faithfulness`/`Answer Relevancy` scores, and per-case `ContextJudge` decisions live only in `ragas_report.csv` / `detailed_evaluation_records.csv` / `reports/debug/*.json`, none of which were provided and none of which appear anywhere in the notebook's cell outputs. **This table cannot be produced without those files.** What we do have, reconstructed independently and verified (§5), is the retrieval-only per-case table in §11 below — but it does not include the LLM-judged Context Recall value itself.

## 11. Per-case retrieval comparison

This table **was** reconstructible with full confidence, using only real evidence: every `RETRIEVAL_EVENT` JSON blob logged in the run (196 total = 49 questions × 4 retrievals each — the main loop plus the K=3/5/10 diagnostic sweep, all cache-consistent), matched to its `EVAL_XXX` case by exact question-text equality (49/49 matched, 0 unmatched), canonicalized by stripping the `_P#_C#` child-chunk suffix, and scored with the project's real `evaluation/metrics/retrieval_metrics.py` functions.

**Validation of this method:** the resulting status counts (`VALID: 32, MISSING_GROUND_TRUTH: 11, REAL_ZERO: 6`) **exactly match** the run's own reported `Recall@5`/`AP@5`/`MRR@5` status breakdowns (§4) — independent confirmation the reconstruction is correct.

| Class | Count | Meaning |
|---|---|---|
| Correct source at rank 1 | **26** | gold `source_id` is the #1 retrieved result |
| Correct source in top-5 (not rank 1) | **6** | gold `source_id` retrieved, ranked 2–5 |
| Correct source absent from top-5 | **6** | a genuine retrieval miss |
| Non-RAG (no gold to check) | 11 | `relevant_chunk_ids` is `null` by design |

**32/38 (84%) of RAG-grounded cases had the correct source somewhere in the top 5; 26/38 (68%) had it at rank 1.** This is a good result and is fully consistent with `MRR@5 = 0.7298`, `MAP@5 = 0.5934`, `Recall@5 = 0.6634` — all three retrieval-only metrics agree with each other and with this independently-reconstructed table, and **none of them depend on a judge call**, so none of them are affected by the Groq outage.

The 6 genuine misses are: `EVAL_002, EVAL_022, EVAL_029, EVAL_031, EVAL_032, EVAL_049`. All 6 cases' gold `relevant_chunk_ids` were verified to exist in `data/rag/rag_data.json` (not stale/typo IDs) — these are real retrieval/ranking misses, not annotation errors.

**This directly contradicts a "the RAG system is bad" reading of the 0.2114 Context Recall number** — the retrieval layer that Context Recall is supposed to be validating is, by every metric that can actually measure it cleanly, performing well.

## 12. 11 non-RAG case analysis

See §6 in this doc numbering scheme — this is task item 6 in the request; the answer:

- **Context Recall currently includes all 11 non-RAG cases**, unconditionally, in `avg_recall = df["context_recall"].mean()`. There is no exclusion filter of any kind for `relevant_chunk_ids is None` cases in the Context Recall path.
- All 11 have non-empty `gold_facts` (1–2 facts each — confirmed in §3/§7), so `ContextJudge.evaluate_recall`'s own `if not expected_contexts: return {"facts": []}` short-circuit **does not trigger** for them either. **A real LLM call is made** for every one of these 11 cases, asking the judge to verify their (non-RAG-sourced) gold facts against whatever RAG chunks happened to be retrieved for that question — chunks that were never authored or expected to contain that knowledge.
- **This is a design/integration gap, not "the current implementation excludes them" or "treats them as missing."** They are neither excluded, nor flagged `MISSING_GROUND_TRUTH` (that status only exists in the *retrieval* metrics' own status enums — `calculate_recall_at_k_details` etc. — which Context Recall doesn't share), nor given any special treatment. They are evaluated exactly like the 38 RAG-grounded cases, against a knowledge source that isn't relevant to them by design.
- Structurally, even under a hypothetical zero-failure Groq run, these 11 cases would likely still score near 0 on Context Recall (unless the RAG corpus happens to coincidentally contain matching text), simply because their gold facts don't live there. This is a second, independent contributor to the low aggregate, on top of the judge-failure issue in §5.

## 13. Gold-fact analysis

- **49 cases, 73 total gold facts.** Min 1, max 4, average 1.49 facts/case. Distribution: 32 cases with 1 fact, 12 with 2, 3 with 3, 2 with 4.
- **0 cases with 0 gold facts.**
- Facts read as reasonably atomic single-clause statements in the large majority of cases (e.g. `EVAL_006`: *"Tea reduces iron absorption and should not be consumed with, or near, meals."*).
- A small number of facts bundle multiple numeric sub-claims into one `fact_text` — e.g. `EVAL_045` (age-banded kcal/day figures across three age groups in one fact) and `EVAL_046` (two separate protein RDA figures in one fact). A semantic judge asked to mark a single `is_present` boolean for a fact that actually contains 2–3 sub-claims has to make an all-or-nothing call on a partially-supported statement — a plausible minor source of noise, but based on the sample reviewed here, this affects only a handful of the 73 facts, not a systemic pattern.
- No duplicate or near-duplicate facts were found across the sample reviewed.
- We did **not** find evidence that a large share of facts require information structurally absent from the RAG corpus (i.e. this is not a widespread problem for the 38 RAG-grounded cases' facts) — the 11 non-RAG cases (§12) are the clear, identifiable exception, by design.

**A pre-existing, older repository file is relevant context here but is NOT evidence about the current system:** `reports/context_recall_failure_analysis.md` (already tracked in git, pre-dating this phase) documents a **0.3849** Context Recall failure analysis against the **old 100-question dataset**, using an older, tag-style "expected chunks" annotation format (not `gold_facts`), and attributes it to "semantic vector dilution" in a **pre-hybrid-retrieval** version of the RAG system (FAISS-only, no BM25, no reranking — those were added in a later commit, `3541902 "rag pipeline"`, per `git log`). **This is superseded, historical context, not current evidence.** Our own §11 reconstruction, on the *current* hybrid FAISS+BM25+reranker system and the *current* 49-case dataset, shows an 84% top-5 hit rate — directly at odds with that old document's "semantic dilution" conclusion for the old system. Do not cite that file as an explanation for today's 0.2114 without re-verifying it against the current architecture.

## 14. Trustworthiness classification for every metric

| Metric | Classification | Reasoning |
|---|---|---|
| **Precision@5** (Context Precision) | NOT TRUSTWORTHY (this run) | Not in the final aggregate table at all, but its per-case status is: 32/49 (65%) `EVALUATION_FAILURE`. Whatever aggregate could be derived from the 15 valid + 2 real-zero cases is based on too small and non-random a surviving sample to trust. |
| **Recall@5** | **TRUSTWORTHY** | Pure Layer-2 math from `retrieved_chunk_ids` vs gold IDs — no judge call involved. `evaluation_failures: 0`. Independently reconstructed and verified in §11. |
| **MAP@5** | **TRUSTWORTHY** | Same as Recall@5 — judge-independent, `evaluation_failures: 0`, verified. |
| **MRR@5** | **TRUSTWORTHY** | Same as above. |
| **Context Recall** | **NOT TRUSTWORTHY** | Root cause identified and code-verified in §5: judge-call failures and genuine zero-recall results are structurally indistinguishable (`calculate_context_recall` has no failure status), and the 65% Layer-1 judge failure rate observed elsewhere in this exact run makes silent-zero contamination highly likely. Also structurally includes 11 cases (§12) whose gold facts were never RAG-sourced. |
| **Faithfulness** | NOT COMPUTABLE (this run) | Reported as literal `nan` — every one of the 49 cases' `faithfulness` value was `None`, meaning the `GroundingJudge` call failed on effectively all 49 cases. Correctly excluded (via pandas `skipna`) rather than zeroed, but there was nothing left to average. |
| **Answer Relevancy** | PARTIALLY TRUSTWORTHY | Failure-handling is structurally correct (failed cases → `None` → excluded by `.mean()`, not zeroed — unlike Context Recall). But the true N behind `0.7579` is unknown without `ragas_report.csv`, and given Faithfulness's 100% failure rate on the same judge-call block, N is likely well below 49. |
| **Unsupported Claim Rate** | NOT COMPUTABLE (this run) | Depends on the same `claims` list as Faithfulness; reported as `N/A` in the final table, consistent with the Grounding Judge's near-total failure. |
| **Hallucination Rate** | NOT COMPUTABLE (this run) | Reported `N/A`; same root cause as above. |
| **Intrinsic Response Rate** | NOT COMPUTABLE (this run) | Reported `N/A`; same root cause. |
| **Extrinsic Response Rate** | NOT COMPUTABLE (this run) | Reported `N/A`; same root cause. |
| **Safety Recall / Precision / F1** | NOT COMPUTABLE (by design, not by this run's failures) | Correctly reports `MISSING_GROUND_TRUTH` — doctor review (Phase 2D) is still pending, and this is honest, intended behavior, not a defect. This would be `MISSING_GROUND_TRUTH` even in a run with zero Groq failures. |

## 15. Root-cause conclusion

The low `Context Recall = 0.2114` has **two distinct, real, and independently sufficient contributing causes** — neither of which is "the RAG system retrieves badly":

1. **A code-level metric defect (primary, and the one worth fixing first):** `calculate_context_recall()` cannot distinguish "the judge failed" from "the judge found nothing" — both produce `0.0`. Combined with this run's ~65% Layer-1 judge failure rate (driven entirely by Groq's `openai/gpt-oss-120b` 200,000-TPD daily quota being exhausted mid-run), this alone plausibly explains the large majority of the score's shortfall (§5's bounding calculation).
2. **A dataset/evaluation-design gap (secondary, real, independent of #1):** 11 of the 49 cases have gold facts that were never sourced from RAG, yet are still checked against RAG-retrieved context — these cases are close to guaranteed to contribute near-zero Context Recall regardless of judge success or RAG quality (§12).

**Retrieval itself is not implicated.** `Recall@5`, `MAP@5`, `MRR@5` are judge-independent, fully trustworthy this run, and directly corroborated by an independent per-case reconstruction (§11) showing an 84% top-5 hit rate on the 38 RAG-grounded cases.

Mapped to the task's lettered options: primarily **G** (the `gold_facts → Context Recall` integration has no failure-status path) and **F** (judge/API failures), with **H** (structured-DB-only cases included incorrectly) as a real, separate, additive contributor. **A** (retrieval failure) and **B** (poor ranking) are not supported by the evidence — retrieval performed well. **L** (a legitimate RAG weakness) cannot be ruled fully out for the 6 genuine misses in §11, but those 6/38 cases are far too few to explain a 0.2114 aggregate on their own.

## 16. Recommended next actions (recommendations only — nothing implemented)

1. Add a real failure/status path to `calculate_context_recall()` (mirroring the pattern already used by `calculate_answer_relevancy`/`calculate_faithfulness_details`), so a judge-call failure produces `EVALUATION_FAILURE`/`score=None` instead of `0.0`, and `comparator.py` excludes it from the average the same way it already excludes `MISSING_GROUND_TRUTH`/`EVALUATION_FAILURE` from every retrieval metric.
2. Decide, explicitly, whether the 11 non-RAG cases should be excluded from Context Recall specifically (they can clearly stay in every other metric — see §18 below) or whether some other treatment is intended.
3. Re-run the evaluation once a judge backend with adequate quota is confirmed available for a full 49-case run (5 judges × 49 cases, plus the ~294-call unofficial diagnostic, is roughly 539 judge calls in total for a single full pass — whatever backend is used needs headroom for that, comfortably above the ~200K-token daily ceiling that was exhausted here).
4. Consider gating the unofficial `run_llm_judged_relevance_experiment` diagnostic (§8) behind an explicit flag, since it silently adds ~294 extra judge calls to every `--evaluate` run today, competing for the same quota as the official metrics (already flagged as a known future improvement in that function's own docstring, per `comparator.py`).

## 17. Items requiring code changes

- `evaluation/metrics/grounding_metrics.py::calculate_context_recall` — add a failure/status path (see §16.1).
- `evaluation/comparator.py` — exclude Context-Recall failures from `avg_recall` once the above status exists; decide the 11-non-RAG-case treatment (§16.2, §18).

## 18. Items requiring dataset changes

- None identified with certainty. The 11 non-RAG cases' `gold_facts` are legitimate content, not an error — this is a metric-scoping question (§18 below), not a data-quality problem.
- The handful of multi-sub-claim gold facts noted in §13 (`EVAL_045`, `EVAL_046`) are a minor, non-urgent candidate for a future granularity pass — not a cause of this run's low score.

## 19. Items requiring judge/model changes

- Resolve the Groq model-ID discrepancy (§16 in the original numbered request — "16. CHECK GROQ MODEL MISMATCH"; see also the dedicated section below) before the next run — confirm which model `groq_llama70b` should actually route to, and confirm it has sufficient daily quota for a full run.
- Consider Gemini (already smoke-tested successfully, already wired as `JUDGE_MODEL="gemini"`, zero code changes needed) as the judge backend for the next full run if Groq quota cannot be secured in time.

## 20. Items requiring no change

- Qwen local generation (§9) — no evidence of any problem.
- Retrieval / RAG (§11) — performing well; no evidence of a retrieval-side problem.
- `Recall@5` / `MAP@5` / `MRR@5` computation — correct, trustworthy, no change needed.
- Safety metrics reporting `MISSING_GROUND_TRUTH` — correct, intended behavior pending Phase 2D.
- `Answer Relevancy`'s failure-exclusion mechanism (§6/§14) — structurally correct (though see §17 for the parallel gap it highlights in Context Recall).

---

## Deep dives on specific numbered investigation items

### Groq model mismatch (item 16 of the request)

- **Symbolic name `groq_llama70b` is defined in `llm/llm_client.py:76-77`:**
  ```python
  elif model_name == "groq_llama70b":
      response_text = self._call_groq("llama-3.3-70b-versatile", system_prompt, user_prompt)
  ```
  This is the **only** place that maps `"groq_llama70b"` to an actual model ID anywhere in the current codebase, and it still says `"llama-3.3-70b-versatile"`.
- **The run's own Section 9 cell** printed the account's live model catalog (`groq.models.list()`): `qwen/qwen3.6-27b, groq/compound-mini, canopylabs/orpheus-v1-english, whisper-large-v3, openai/gpt-oss-120b, meta-llama/llama-prompt-guard-2-86m, canopylabs/orpheus-arabic-saudi, allam-2-7b, qwen/qwen3.8-27b, groq/compound, meta-llama/llama-prompt-guard-2-22m, openai/gpt-oss-safeguard-20b, whisper-large-v3-turbo, openai/gpt-oss-20b` — **`llama-3.3-70b-versatile` is not in this list.**
- **Yet every 429 error body in the run's log explicitly names `openai/gpt-oss-120b`** as the rate-limited model (§7) — this is the actual model ID the Groq API received in the request, not something we can misread.
- **This is a direct contradiction we cannot resolve from the evidence available.** The code committed and shipped (verified against the exact commit this run itself reported, `7f81a45`) still hardcodes `"llama-3.3-70b-versatile"`. The only way the observed requests could have targeted `openai/gpt-oss-120b` is if `llm/llm_client.py` (or an equivalent override) was edited **inside the live Kaggle environment**, after extraction, outside of what any notebook cell in the provided output shows. We have no cell output showing such an edit (e.g. a `sed`/file-write cell), so we cannot confirm how or where this happened — only that it must have. **This needs direct clarification from whoever ran the notebook** (did they edit a file in the Kaggle file browser or a terminal before running Section 10?).
- Reports **do** correctly identify the *symbolic* judge model used (`Judge model: groq_llama70b` in the run summary) — but that string is misleading given the above, since the actual backend model differs from what the label states.
- The judge model **can** be changed cleanly via the existing `JUDGE_MODEL` notebook variable or the `--judge-model` CLI flag with zero code changes, once the correct/available Groq model ID is decided and updated in `llm_client.py` (or a new symbolic name is added for it) — this part of the architecture is sound.

### Groq rate-limit quantified impact (item 17 of the request)

- **987/1020 (97%) of all judge-call error events were 429 rate-limit errors**; the remaining 33 (3%) were a distinct "empty response" failure mode seen early in the run.
- **986 of the 987 429s were daily-quota (TPD) errors**, not per-minute (TPM) — meaning almost none of this was a recoverable "wait a few seconds and retry" situation; once the daily budget was exhausted, retries were structurally unable to help for the rest of that day.
- **340 judge calls failed outright** (exhausted all 3 retries) somewhere across the run's ~539 total judge-call attempts (49 cases × 5 Layer-1 calls + ~294 calls from the unofficial K=3/5/10 diagnostic) — a **~63% outright-failure rate** across the whole run's judge-call population.
- **Retry behavior did not make things structurally worse** — retries only add latency (1s, then 2s backoff) and, ironically, *consume more of the already-scarce token budget* on each failed attempt (each attempt is itself a full API call, so 3 failed attempts still cost roughly 3× the tokens of 1 successful one) — worth noting as a real, quantifiable cost of retrying against a hard daily ceiling, though we recommend no retry-logic change per the task's explicit scope.
- **The full 49-case run did complete** with all 49 cases attempted and completing (49/49 `Running Question ID` markers present, all 49 generating an answer) — it did **not** abort or crash; it simply produced badly-degraded values for every judge-dependent metric except (partially) Answer Relevancy.

---

## 21. Direct answers to the required questions

**A. Is Context Recall = 0.2114 a real RAG-quality signal or an evaluation artifact?**
Primarily an **evaluation artifact** — a code-level failure-status gap (§5) combined with a dataset-scoping gap (11 non-RAG cases, §12), not a real measurement of retrieval or generation quality. The RAG system's own directly-measurable quality (§11) looks good.

**B. Exactly which cases caused the low Context Recall?**
Cannot be stated exactly — the per-case `context_recall` values are not available from any evidence provided (§10). What can be stated: the 11 non-RAG cases (§12) are near-certain heavy contributors by design, and a large but unquantified subset of the 38 RAG-grounded cases very likely also contributed via silent judge-failure collapse (§5), given the 65% failure rate directly observed on the sibling `Context Precision` metric from the same judge instance.

**C. Are the 11 non-RAG cases affecting Context Recall?**
**Yes, directly and unconditionally** — they are included in the average with no exclusion, no special status, and their gold facts (which do exist, 1-2 per case) are checked against RAG context they were never designed to be found in (§12).

**D. Are MAP@5 = 0.5934 and MRR@5 = 0.7298 trustworthy?**
**Yes.** Both are pure Layer-2 math over `retrieved_chunk_ids` vs. gold IDs, never touch a judge call, report `evaluation_failures: 0`, and were independently reconstructed from this run's own retrieval logs and the project's real metric code, exactly reproducing the run's reported numbers (§11).

**E. Is Answer Relevancy = 0.7579 trustworthy?**
**Partially.** Its failure-handling is structurally sound (failures excluded, not zeroed) — but the true sample size behind the average is unknown and, given the Grounding Judge's 100% failure rate on the same run, is likely meaningfully below 49 (§6).

**F. Which metrics were corrupted/limited by Groq rate limits?**
Context Precision (32/49 outright failures, confirmed by status), Context Recall (corrupted via silent zero-collapse, §5), Faithfulness/Unsupported Claim Rate/Hallucination Rate/Intrinsic Response Rate/Extrinsic Response Rate (all `NaN`/`N/A` — effectively 100% Grounding Judge failure), and Answer Relevancy (limited, unknown reduced sample). Precision@5/Recall@5/MAP@5/MRR@5 (judge-independent) and Safety metrics (correctly `MISSING_GROUND_TRUTH` for an unrelated reason) were **not** affected.

**G. Did Qwen generate answers successfully for all 49?**
**Yes, as far as the evidence shows** — 49/49 cases reached generation, zero crashes/tracebacks/CUDA errors, the `max_new_tokens`/`max_length` warning is benign and did not truncate output. Actual answer *text* quality could not be verified (§9) — that evidence (`detailed_evaluation_records.csv`) was not provided.

**H. Did the RAG source-ID fix work correctly?**
**Yes.** The canonical `source_id` mapping (child-chunk `_P0_C0` stripped to its parent `source_id`, per the Phase 4B fix) was directly exercised by this run's real `retriever.retrieve()` calls and confirmed correct: reconstructing per-case retrieval hits using this exact canonicalization reproduced the run's own reported status breakdown precisely (§11), and 32/38 RAG-grounded cases showed at least one exact canonical-ID match in their top-5.

**I. What should we fix next?**
Per the recommendations in §16: (1) give `calculate_context_recall` a real failure/status path before trusting any future Context Recall number, (2) decide and implement how the 11 non-RAG cases should be scoped for Context Recall specifically, and (3) resolve the Groq model-ID discrepancy and secure adequate judge quota before the next full run.
