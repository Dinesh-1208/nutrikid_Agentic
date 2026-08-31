# Phase 4E — Context Recall Root-Cause Fix + Validation

**Scope: engineering fix + validation only.** No evaluation-dataset question, gold fact, reference answer, `relevant_chunk_ids`, RAG data, structured DB, planner, notebook, or Groq/Gemini configuration was touched. Not committed, not pushed. The full 49-case Kaggle benchmark was **not** re-run — this phase stops after the code fix, regression tests, and local (mocked-judge) integration validation, per instruction.

---

## 1. Root cause

**Three separate code paths silently converted "no valid result" into a fabricated real `0.0`**, all traced to the same underlying gap: `calculate_context_recall(facts_list)` had exactly one branch, `if not facts_list: return 0.0`, with no way to represent failure, inapplicability, or a genuine zero as distinct outcomes.

1. **`evaluation/metrics/grounding_metrics.py::calculate_context_recall`** — an empty `facts_list` produced `0.0` whether it meant "the judge checked and found nothing supported" or "the judge never produced any facts at all" (failure).
2. **`evaluation/evaluator.py`'s outer Layer-1 exception handler** — a total judge-call crash set `recall_data = {"facts": []}` with **no failure marker at all**, so Layer 2 could not tell this apart from a legitimate empty result.
3. **`evaluation/evaluator.py`'s Layer-2 exception handler** — hardcoded `context_recall = 0.0` directly, even though every one of its sibling metrics in the exact same `except` block already correctly returned `None`/`EVALUATION_FAILURE`.

**A fourth, distinct issue** (not a failure-handling bug, a scoping bug): the evaluator sent every case's `gold_facts` to `ContextJudge.evaluate_recall` regardless of whether `relevant_chunk_ids` was `None` — i.e., structured-DB-only cases never authored to have their facts findable in RAG context were checked against that context anyway.

**A fifth, previously-undocumented issue found while tracing the code** (not part of the two originally-reported findings, surfaced during §3's data-flow trace): `evaluation/comparator.py::run_llm_judged_relevance_experiment` (the unofficial retrieval-depth diagnostic) read `case.get("expected_context", [])` — a field that was retired dataset-wide in Phase 4B in favor of `gold_facts`. Since no case has ever had an `expected_context` key since that migration, this diagnostic's own "Context Recall" column has always been computed from an empty expected-facts list — always hitting `ContextJudge.evaluate_recall`'s own "nothing expected" short-circuit — independent of, and in addition to, the Groq outage that also affected it during the first Kaggle run.

## 2. Current behavior before fix

| Scenario | Old behavior |
|---|---|
| Judge succeeds, 0/N facts supported | `context_recall = 0.0` (correct, but indistinguishable from the row below) |
| Judge call fails (retry-exhausted) | `context_recall = 0.0` (**wrong** — a non-result reported as a real measurement) |
| Whole Layer-1 crashes (different judge raises) | `context_recall = 0.0` (**wrong**, same reason) |
| Layer-2 math itself crashes | `context_recall = 0.0` (**wrong**, hardcoded directly, no failure status at all) |
| Case has no RAG ground truth (`relevant_chunk_ids is None`) | Judge is still called; gold facts checked against unrelated RAG context; if it happens to find nothing, `context_recall = 0.0` (**wrong on two counts** — the call should never have happened, and the result is indistinguishable from a real zero) |
| Partial/full support | Correct (`k/N`) — this path was never broken |

## 3. Correct intended behavior

**What Context Recall measures in this project:** whether the RAG context actually retrieved for a question contains the specific facts (`gold_facts[].fact_text`) that question's answer is expected to draw on — a RAG-context-coverage metric, applicable only to cases genuinely authored against the RAG corpus.

| Outcome | Meaning | Status | Score |
|---|---|---|---|
| **Valid positive** | Judge succeeded, ≥1 of N facts supported | `VALID` | `k/N`, `0 < score ≤ 1` |
| **Real zero** | Judge succeeded, genuinely 0/N facts supported | `REAL_ZERO` | `0.0` |
| **Evaluation failure** | Judge/API/parser did not successfully evaluate the case | `EVALUATION_FAILURE` | `None` |
| **Missing ground truth / not applicable** | Case has no RAG ground truth (`relevant_chunk_ids is None`) or genuinely no facts were expected | `MISSING_GROUND_TRUTH` | `None` |

This is exactly the same four-way distinction already used by `calculate_faithfulness_details`, `calculate_unsupported_claim_rate_details`, and every retrieval/safety metric in this codebase — **no new status vocabulary was invented.**

## 4. Data-flow trace (as it exists after the fix)

```
test_case
  -> profile = test_case.get("profile") or {}
  -> context_recall_applicable = test_case.get("relevant_chunk_ids") is not None   [NEW]
  -> retrieval: retrieved_contexts = retriever.retrieve(question, top_k=5)
  -> expected_context = [fact["fact_text"] for fact in test_case.get("gold_facts") or [] if fact.get("fact_text")]
       (UNCHANGED from Phase 4B - still gold_facts, never expected_context, never reverted)
  -> IF context_recall_applicable:
         recall_data = ContextJudge.evaluate_recall(retrieved_contexts, expected_context, ...)
            -> success: {"facts": [{"fact": str, "is_present": bool}, ...]}
            -> failure (3 retries exhausted): {"parse_failed": True, "error": str}
     ELSE:
         recall_data = None   [NEW - judge never called]
  -> [outer Layer-1 except, if ANY judge raised]:
         recall_data = {"facts": [], "parse_failed": True, "error": str(e)}   [NEW - now flagged]
  -> Layer 2:
         context_recall_evaluation_failed = bool(recall_data is not None and recall_data.get("parse_failed"))
         context_recall_facts = recall_data.get("facts") if recall_data is not None else None
         context_recall_details = calculate_context_recall_details(
             context_recall_facts,
             evaluation_failed=context_recall_evaluation_failed,
             ground_truth_available=context_recall_applicable
         )
         context_recall = context_recall_details["score"]
  -> [Layer-2 except, if math itself crashed]:
         context_recall = None; context_recall_details = {"score": None, "status": "EVALUATION_FAILURE", ...}   [NEW]
  -> returned per-case dict: context_recall, context_recall_status, context_recall_supported_count, context_recall_total_count   [NEW fields]
  -> comparator.py: per-model average computed only over VALID/REAL_ZERO cases; Valid/Missing/Failure counts reported alongside   [NEW]
```

## 5. Implementation changes

**`evaluation/metrics/grounding_metrics.py`**
- Added `CONTEXT_RECALL_STATUS_VALID`, `_REAL_ZERO`, `_MISSING_GROUND_TRUTH`, `_EVALUATION_FAILURE` constants (same names/vocabulary already used by `FAITHFULNESS_STATUS_*`, `RECALL_STATUS_*`, `SAFETY_STATUS_*`).
- Added `calculate_context_recall_details(facts_list, evaluation_failed=False, ground_truth_available=True)` — the new primary function, returning `{"score", "status", "supported_count", "total_count"}`, following the exact same shape/priority-order (`evaluation_failed` checked first, then applicability, then emptiness, then real computation) as `calculate_faithfulness_details`.
- `calculate_context_recall(facts_list)` is preserved as a thin backward-compatible wrapper (`return calculate_context_recall_details(facts_list)["score"]`) — same pattern already used for `calculate_faithfulness`/`calculate_unsupported_claim_rate` in the same file, so the one remaining direct caller (the unofficial diagnostic) needed no signature change, only a `None`-safety fix (below).

**`evaluation/evaluator.py`**
- Computes `context_recall_applicable = test_case.get("relevant_chunk_ids") is not None` once, alongside `expected_context`.
- Skips the `evaluate_recall` judge call entirely when not applicable (`recall_data = None`); `evaluate_precision` is unaffected and still runs unconditionally (it is always applicable — a live relevance judgment, not gold-ID-based).
- The outer Layer-1 exception fallback now sets `recall_data = {"facts": [], "parse_failed": True, "error": str(e)}` instead of an unflagged `{"facts": []}`.
- Layer 2 now calls `calculate_context_recall_details` with the correct `evaluation_failed`/`ground_truth_available` flags instead of the old bare `calculate_context_recall(recall_data.get("facts", []))`.
- The Layer-2 exception fallback now sets `context_recall = None` with a proper `EVALUATION_FAILURE` details dict, instead of the previously hardcoded `context_recall = 0.0`.
- The per-case return dict gained three new fields: `context_recall_status`, `context_recall_supported_count`, `context_recall_total_count` (mirroring every sibling metric's existing reporting granularity).

**`evaluation/comparator.py`**
- `ragas_report.csv` export gained `Context Recall Status`, `Context Recall Supported Count`, `Context Recall Total Count` columns.
- The final-report aggregate now averages **only** cases whose `context_recall_status` is `VALID` or `REAL_ZERO`, explicitly excluding `MISSING_GROUND_TRUTH`/`EVALUATION_FAILURE` cases from both the numerator and the denominator (mirroring exactly how `Recall@5`'s own aggregate already works) — plus three new columns, `Context Recall Valid Count`, `Context Recall Missing Ground Truth`, `Context Recall Evaluation Failures`, reported in `final_model_comparison.csv` alongside the score.
- `run_llm_judged_relevance_experiment` (the unofficial diagnostic): fixed the stale `case.get("expected_context", [])` read (see §1, finding 5) to derive from `gold_facts` the same way the official path does; made its own K-level average `None`-safe (a judge failure there can no longer silently become part of a `0.0` average either) and added a `Context Recall Valid Count` column to its own `retrieval_experiment.csv` output. This diagnostic remains explicitly unofficial and ground-truth-free — it was not made gold-grounded, only fixed to no longer be reading a retired field and to no longer crash or misreport on a failure.

**No change** to `evaluation/metrics/retrieval_metrics.py`, `evaluation/metrics/safety_metrics.py`, `evaluation/metrics/relevancy_metrics.py`, `evaluation/judges/*.py` (including `ContextJudge` itself — its prompt and short-circuit logic are unchanged), or any dataset/RAG/structured-DB/planner/notebook file.

## 6. Why non-RAG cases are excluded

The 8 genuinely structured-DB-only cases in the finalized dataset (`relevant_chunk_ids is None`) were never authored with the expectation that their `gold_facts` would be findable in RAG-retrieved context — that context comes from `allergies.json`/`goals.json`, not the RAG corpus. Checking their facts against RAG context anyway (the old behavior) meant these cases were structurally near-guaranteed to score at or near zero regardless of RAG quality, contaminating the aggregate with a result that measured nothing meaningful. The fix scopes Context Recall's applicable-case set to exactly the same set already used by the official retrieval metrics (Recall@5/MAP@5/MRR@5), which have always correctly excluded these cases as `MISSING_GROUND_TRUTH` — Context Recall now agrees with them instead of silently disagreeing.

## 7. Gold-fact handling

Confirmed unchanged and still correct: `expected_context` is still built from `gold_facts[].fact_text` (Phase 4B's fix), never reverted to the retired `expected_context` field on the test case itself. No second gold-fact representation was introduced. The one place that still read the retired field (`run_llm_judged_relevance_experiment`, an unofficial diagnostic — §1/§5) has been aligned to the same source.

## 8. Leakage analysis

Re-confirmed and covered by new tests (`test_context_recall.py::TestContextRecallLeakageBoundary`): `ContextJudge.evaluate_recall` receives only the plain `fact_text` strings extracted from `gold_facts` — never the raw fact dict, `fact_id`, `source_reference`, `reference_answer`, `relevant_chunk_ids`, or `safety_ground_truth`. This is unchanged, intentional, by-design behavior (Context Recall is specifically a reference-vs-context evaluation, per the project's established architecture) — the fix does not alter what reaches the judge, only whether the judge is called at all and how its outcome is classified. The new applicability gate (`context_recall_applicable`) is itself a **leakage reduction**, not a new leakage path: non-RAG cases' gold facts are now never sent to any judge call at all, where previously they were (checked against unrelated RAG context).

## 9. Regression tests

New file `test_context_recall.py` (18 tests):
- **`TestCalculateContextRecallDetailsPureMath`** (9 tests) — direct unit tests on the metric function: real zero, evaluation failure (never a fake zero, including when failure co-occurs with a non-empty facts list), missing ground truth via non-applicability, missing ground truth via genuinely-empty facts, partial recall, full recall, all-four-outcomes-distinguishable, and the backward-compatible wrapper.
- **`TestContextRecallEvaluatorIntegration`** (7 tests) — through the real `KidsNutriEvaluator.run_single_evaluation` (mocked judges/retriever/planner/LLM, no live API calls): the task's required Cases A–D, a multi-fact full-recall case, the whole-Layer-1-crash path specifically (proving the *second* bug path is fixed), and a direct real-zero-vs-failure non-conflation check.
- **`TestContextRecallLeakageBoundary`** (2 tests) — confirms only plain `fact_text` strings reach `evaluate_recall` and that non-RAG cases skip the call entirely (§8).

**One pre-existing test was corrected, not weakened**: `test_judge_architecture.py::test_total_judge_outage_yields_evaluation_failure_not_fake_zero`. Its own existing comment already read *"context_recall has no status-enum layer... it silently falls back to 0.0 on empty facts, which is exactly the gap this test documents rather than papers over"* — i.e., this test was deliberately written to pin down the exact bug this phase fixes, with an explicit note that it was tracking a known gap. Its assertion (`assertEqual(result["context_recall"], 0.0)`) has been updated to assert the now-correct invariant (`context_recall_status == "EVALUATION_FAILURE"`, `context_recall is None`, `context_recall != 0.0`), and its test-case fixture was given an explicit `relevant_chunk_ids` so it tests judge-outage in isolation from the separate non-RAG-applicability gate. This is strengthening a test whose own comment already called out the bug, not weakening a passing test to hide one.

## 10. Test results

```
python -m unittest test_context_recall -v         → 18/18, OK
python -m unittest discover                        → 142/142, OK (124 pre-existing + 18 new)
python -m unittest planner.test_weekly_planner -v  → 3/3, OK
python -m compileall -q .                          → clean, no errors
```

**Local integration validation** (real `KidsNutriRetriever` + real `KidsNutriDatabase`/`DietPlanner`, mocked judges/LLM only, run against actual finalized-dataset cases — not synthetic fixtures):

| Scenario | Case used | Result |
|---|---|---|
| RAG-grounded, multi-gold-fact (4 facts), full support | `EVAL_028` | `context_recall=1.0`, `status=VALID`, `4/4` supported |
| Non-RAG case | `EVAL_019` | `context_recall=None`, `status=MISSING_GROUND_TRUTH`, judge call confirmed **never made** |
| Retrieval genuinely misses the gold source | `EVAL_049` (confirmed real top-5 miss in `docs/evaluation/final_evaluation_dataset_audit.md` §16) | `context_recall=0.0`, `status=REAL_ZERO` — a legitimate outcome (the judge succeeded and correctly reported no support), correctly distinct from a failure |
| Judge failure on a RAG-grounded case | `EVAL_001` | `context_recall=None`, `status=EVALUATION_FAILURE` |

All four match the intended behavior exactly.

## 11. First-Kaggle-run interpretation

**What can be stated with certainty from stored data:**
- The first Kaggle run's dataset state (before the later 4-case replacement) had **38 RAG-grounded and 11 non-RAG cases**. Under the fix, all 11 non-RAG cases would now be excluded from Context Recall unconditionally (`MISSING_GROUND_TRUTH`), regardless of judge health that day.
- That run's own reported `Context Precision Status` breakdown — the one Layer-1-judge status it actually surfaced per case — was `VALID: 15, REAL_ZERO: 2, EVALUATION_FAILURE: 32` (out of 49), documented in `docs/phase4d_first_kaggle_results_audit.md`. `evaluate_precision` and `evaluate_recall` are back-to-back calls on the same `ContextJudge` instance, under the same Groq-quota exhaustion, in the same per-case block — this is a **reasonable proxy for**, but **not a direct measurement of**, `evaluate_recall`'s own failure rate that day.

**What cannot be stated with certainty:** the exact number of the 38 RAG-grounded cases whose `evaluate_recall` call specifically failed that day. **This requires per-case data (`ragas_report.csv` or `detailed_evaluation_records.csv` from that specific run) that was not provided and does not exist in this repository** — the Phase 4D audit already documented this exact gap explicitly rather than inventing numbers, and that gap has not changed. **No new aggregate score is fabricated here.**

**Best-evidence bounding (explicitly an estimate, not a recomputation):** if the ~65% Context-Precision failure rate applied proportionally to `evaluate_recall` on the same 38 RAG-grounded cases, roughly 25 of them would also have failed, leaving a denominator on the order of 13 genuinely valid cases contributing to that day's Context Recall — a small enough sample that the reported `0.2114` cannot be trusted as a stable measurement even before considering the 11 non-RAG cases' incorrect inclusion. This mirrors, and is now mechanistically confirmed rather than merely hypothesized by, the bounding calculation already presented in `docs/phase4d_first_kaggle_results_audit.md` §5.

## 12. Correct denominator / applicable-case logic

**Formula (now implemented):** a case contributes to Context Recall's average if and only if `relevant_chunk_ids is not None` **and** its `evaluate_recall` call succeeded (`context_recall_status in {VALID, REAL_ZERO}`). Cases with `relevant_chunk_ids is None` are excluded unconditionally, independent of judge health. Cases with a judge/parser failure are excluded regardless of RAG-applicability.

**For the current, locked 49-case dataset** (`docs/evaluation/final_evaluation_dataset_audit.md`): 41 RAG-grounded, 8 non-RAG. The maximum possible denominator on a fully-healthy judge run is **41** (all 8 non-RAG cases always excluded); the realized denominator on any given run will be `41 − (evaluate_recall failures that day)`.

## 13. Whether the old 0.2114 score can be trusted

**No.** Three independent, now-confirmed defects contributed to it: (1) an unknown but plausibly large fraction of its contributing "zeros" were actually silent judge failures, not real measurements; (2) 11 of the 49 cases (22%) were structurally near-guaranteed to score near zero because they were never RAG-answerable in the first place; (3) the specific dataset state that run used has since been improved (3 of the original non-RAG cases were replaced with genuinely RAG-grounded, retrieval-verified questions). The `0.2114` figure should not be cited as a real measurement of RAG quality, and should not be compared against any future corrected run's number as if they measured the same thing on the same footing.

## 14. What must be rerun on Kaggle

The full 49-case evaluation, on the current locked dataset, with the fixed Context Recall code, **and** with a judge backend confirmed to have adequate daily quota for the full run (≈41 RAG-applicable Context Recall calls + the other Layer-1 judge calls across all 49 cases + the unofficial diagnostic's own ~294 calls, unless that diagnostic is disabled — see the Phase 4D report's own recommendation to consider gating it). This phase does not run that benchmark, per instruction — it is the next step, pending review of this fix.

---

## 15. Answers to the required questions

**A. Was the 0.2114 Context Recall mathematically contaminated by judge failures?**
Almost certainly yes, at least in significant part — `calculate_context_recall`'s only branch (`if not facts_list: return 0.0`) could not distinguish a judge failure from a real zero, and the same run showed a 65% failure rate on the sibling `evaluate_precision` call from the identical judge instance under the identical Groq-quota-exhaustion conditions. The exact contaminated fraction cannot be recomputed (§11) but the mechanism is now proven, not hypothesized.

**B. Were non-RAG cases incorrectly contributing to Context Recall?**
Yes, confirmed. All 11 (now 8, post-replacement) non-RAG cases' `gold_facts` were sent to `ContextJudge.evaluate_recall` and checked against RAG context they were never authored to be found in, with no exclusion of any kind.

**C. What should happen to a real zero?**
It should be reported as-is: `score=0.0`, `status=REAL_ZERO` — a legitimate, trustworthy result, included in the average.

**D. What should happen to a failed judge call?**
`score=None`, `status=EVALUATION_FAILURE` — excluded from the average, never converted to `0.0`.

**E. What should happen to a case with no RAG ground truth?**
`score=None`, `status=MISSING_GROUND_TRUTH`, and the judge is never even called for that case's recall check.

**F. What is the final valid Context Recall denominator?**
Up to 41 (the current dataset's RAG-grounded case count), minus however many `evaluate_recall` calls fail on any given run — not a fixed number, but now a correctly and transparently computed one (`Context Recall Valid Count` in `final_model_comparison.csv`).

**G. Can the first 0.2114 score be trusted?**
No — see §13.

**H. What exact code changed?**
`evaluation/metrics/grounding_metrics.py` (new status constants + `calculate_context_recall_details`, backward-compatible wrapper preserved), `evaluation/evaluator.py` (applicability gate, failure-flag propagation in both exception handlers, new per-case fields), `evaluation/comparator.py` (status-filtered aggregate, new count columns, stale-field + None-safety fix in the unofficial diagnostic). Full diff detail in §5.

**I. What exact tests prove the fix?**
`test_context_recall.py` (18 new tests, §9) plus the corrected pre-existing `test_judge_architecture.py` test, plus the four real-code local integration scenarios in §10 (RAG multi-fact, non-RAG, retrieval-miss, judge-failure) run against actual dataset cases with the real retriever and planner.

**J. What do we need to rerun on Kaggle?**
The full 49-case evaluation with a judge backend that won't exhaust its quota mid-run (§14) — not performed in this phase.
