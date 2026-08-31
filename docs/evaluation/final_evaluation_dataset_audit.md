# Final Evaluation Dataset — Complete Audit, Annotation & Metric-Readiness Pass

**Date:** 2026-08-31
**Status:** Dataset-finalization pass. No metric formulas, `evaluation/comparator.py`, `evaluation/evaluator.py`, or `evaluation/metrics/grounding_metrics.py` were modified — those are explicitly deferred to a separate engineering task. Not committed, not pushed.

---

## Verification-depth disclosure (read this first)

This pass combines three different levels of evidence, and this report is explicit about which applies to which case, rather than implying uniform depth:

1. **Freshly, deeply, externally re-verified in this or a directly preceding session** (trusted external sources, two-round cross-checking): the 20 safety-selected cases (16 original + 4 replacements) and EVAL_028 (iron bioavailability, verified in an earlier dedicated phase). **21 cases total.**
2. **Already independently audited in a dedicated, documented prior pass** (`docs/evaluation/phase2c_gold_annotation_review.md` — per-case KB-source verification, contradiction search, source-scope check, done question-by-question when the dataset was first built): the remaining 28 cases. This pass **re-checked** that audit's conclusions against the *current* (post-Step-0A) KB and *current* real retriever, but did not re-derive each fact from a fresh external medical search.
3. **Structural/mechanical checks applied uniformly to all 49**: schema completeness, duplicate/near-duplicate search, RAG-ID validity against the live corpus, real-retriever verification, leakage audit, safety-field integration.

No case in category 2 was found to need a content change during this pass (see §3, §5, §6) — but this report does not claim they received the same fresh external-source-pull treatment as category 1.

---

## 1. Final dataset size

**49 cases, `EVAL_001`–`EVAL_049`.** Unchanged from before this pass (no case added or removed) — confirmed the right size; see §17 for the explicit "should 49 still be the size" analysis.

## 2. Final case list

Unchanged question list from the prior replacement pass, with the 4 replacements already in place: EVAL_029 (ORS composition), EVAL_037 (nut-allergy specific avoidance), EVAL_038 (honey/infant botulism), EVAL_039 (choking hazards). Full question text for all 49 is in `docs/evaluation/phase2c_gold_annotations.json`; not reproduced here to avoid duplicating a 49-row table that changed nothing new in this pass.

## 3. Cases changed in this pass

- **EVAL_022, EVAL_027** — `source_scope` field corrected from `"structured_db"` to `"both"`. Both cases have genuine, verified RAG grounding (non-null `relevant_chunk_ids`, real retrieval confirmed in §16), a mismatch already flagged during the original Phase 2C review ("SOURCE-SCOPE FLAG") but deliberately left uncorrected pending a later pass — this is that pass. No other field on either case changed (question, gold_facts, reference_answer, relevant_chunk_ids all untouched).
- **16 cases** — `safety_ground_truth` integrated from `null` to the verified value (see §9/§19): EVAL_014, EVAL_019–EVAL_028 (minus EVAL_029 already done), EVAL_030, EVAL_031, EVAL_035, EVAL_036, EVAL_049.
- **No question, reference_answer, gold_facts, or relevant_chunk_ids changed for any of the 49 cases in this pass** — everything else was audited and found sound (or already correctly flagged) as-is.

## 4. Cases removed/replaced

**None removed or replaced in this pass.** The 4 replacements (EVAL_029/037/038/039) happened in the prior task and are unchanged here. See §17 for why no further replacement is recommended.

## 5. Category distribution

| Category | Count |
|---|---|
| General Nutrition & Nutrients | 9 |
| Age-Specific Feeding | 9 |
| Allergies & Intolerances | 10 |
| Pediatric Conditions | 9 |
| Food Safety & Suitability | 6 |
| Growth, Development & Reference Data | 6 |
| **Total** | **49** |

Unchanged from the prior replacement pass (the 9/9/10/9/6/6 split already reflects EVAL_037's honest recategorization to Allergies & Intolerances).

## 6. Gold-fact completeness

- **Total gold facts across all 49 cases: 74.**
- **Average: 1.51/case. Min: 1. Max: 4.**
- **Distribution:** 1 fact — 29 cases; 2 facts — 16 cases; 3 facts — 3 cases; 4 facts — 1 case.
- **Every one of the 49 cases has ≥1 gold fact** — no case has an empty `gold_facts` list (confirmed programmatically).
- **Multi-claim facts flagged:** none newly found in this pass. The one previously-known internal risk (EVAL_045/EVAL_046's ICMR energy/protein facts bundling 3 age-bands' numbers into one `fact_text` each) was already identified during the original Step 0A knowledge-base audit as a minor, non-urgent granularity note — not fixed here since it does not affect this pass's completeness/correctness checks (a semantic judge can still reasonably mark the whole compound fact present/absent; see §5 of `docs/doctor_review/2026-08-31_knowledge_base_ai_verification.md` for the original flag).
- **"Could an evaluator reasonably determine whether each gold fact is present in the retrieved context?"** — yes for all 41 RAG-grounded cases (each fact's `chunk_reference` points to a specific, real RAG record whose text visibly contains the claimed fact — spot-checked across all cases touched by Step 0A/0B and reconfirmed via this pass's real retrieval run, §16). For the 8 non-RAG cases, this question doesn't apply in the RAG sense (their facts are structured-DB-sourced, not meant to be found in retrieved text) — see §8 for the Context Recall scoping implication.

## 7. Reference-answer completeness

**All 49 cases have a non-empty `reference_answer`.** Spot-checked for internal consistency with `gold_facts` across every case touched in this pass (the 20 safety cases + EVAL_022/027) — no contradiction found. No reference answer was rewritten in this pass (per instruction, only changed when factually wrong/unsafe/outdated/incompatible — none met that bar beyond the already-completed EVAL_029/037/038/039 replacements). No reference answer contains medication dosing, a specific therapeutic protocol number presented as generic advice (the exact problem that retired the old EVAL_029), or an accidental doctor-like diagnosis of a named condition not already given in the profile.

## 8. RAG-grounded case count / 9. Non-RAG case count

**41 RAG-grounded, 8 non-RAG** (`relevant_chunk_ids` is `null`): EVAL_019, EVAL_020, EVAL_021, EVAL_023, EVAL_024, EVAL_025, EVAL_026, EVAL_047. All 8 were re-confirmed genuinely structured-DB-only — none has a real corresponding RAG chunk (re-checked against the current, post-Step-0A corpus; the original Phase 2C review's per-case "No RAG chunk found" notes still hold, since none of these 8 topics received new RAG content in Step 0A that would change that). **No RAG ID was invented for any of these 8 to inflate Recall@5** — they correctly remain `null`.

## 10. Safety-ground-truth case count

**Exactly 20 non-null, 29 null** (verified programmatically; see §19 for the integration detail and §22 for the exact 20/29 ID lists).

## 11. Metric applicability matrix

| Metric | Required runtime data | Required gold data | Applicable cases | Missing currently? | Action |
|---|---|---|---|---|---|
| **Precision@5** | Live retrieved chunks + `ContextJudge.evaluate_precision` (LLM relevance judgment of query vs. retrieved chunks) | **None** — judge-based, not gold-ID-based | All 49 (any case with a question and live retrieval) | No | None needed |
| **Recall@5** | Live retrieved chunk IDs | `relevant_chunk_ids` (case-level gold IDs) | The 41 RAG-grounded cases only; the 8 non-RAG cases correctly report `MISSING_GROUND_TRUTH`, not a fabricated 0 | No | None needed |
| **MAP@5** | Live retrieved chunk IDs | `relevant_chunk_ids` | Same 41/8 split as Recall@5 | No | None needed |
| **MRR@5** | Live retrieved chunk IDs | `relevant_chunk_ids` | Same 41/8 split | No | None needed |
| **Context Recall** | Live retrieved chunks + `ContextJudge.evaluate_recall` (LLM check of `gold_facts` text against retrieved chunks) | `gold_facts[].fact_text` | **All 49** — the current code (`evaluator.py`, unchanged in this pass) sends every case's `gold_facts` to the context judge regardless of whether `relevant_chunk_ids` is null, i.e. it does **not** currently exclude the 8 non-RAG cases | **Yes — a scoping gap, not a missing-data gap** (see §19/Context-Recall-scoping section below; not fixed here per instruction) | Flagged, not fixed (separate engineering task) |
| **Faithfulness** | Live generated answer + `GroundingJudge.evaluate_grounding` (extracts & checks claims against live RAG context + live planner output) | **None** | All 49 | No | None needed |
| **Unsupported Claim Rate** | Same as Faithfulness (same `claims` list) | **None** | All 49 | No | None needed |
| **Hallucination Rate / Intrinsic Response Rate / Extrinsic Response Rate** | Same `claims` list, using each claim's `hallucination_type` | **None** | All 49 | No | None needed |
| **Answer Relevancy** | Live generated answer + `RelevancyJudge.generate_hypothetical_questions` + live query embedding | **None** — only the case's own `question` text, already present on every case | All 49 | No | None needed |
| **Safety Recall / Precision / F1** | Live `SafetyJudge.evaluate_safety` output (`safety_judge_raw`) | `safety_ground_truth` | The 20 selected safety cases; the other 29 correctly report `MISSING_GROUND_TRUTH` | **No, after this pass** (was 0/49 before) | Done — see §19 |

**Key finding: only two metric families require per-case gold annotation at all** — retrieval (Recall@5/MAP@5/MRR@5, needing `relevant_chunk_ids`) and Context Recall + Safety (needing `gold_facts` and `safety_ground_truth` respectively). Precision@5, Faithfulness, Unsupported Claim Rate, Hallucination Rate, Intrinsic/Extrinsic Response Rate, and Answer Relevancy are **entirely runtime-derived** — no case can be "missing" gold data for them because none is required. This directly answers §11 of the task ("hallucination/grounding annotation readiness"): **these metrics have no gold-annotation requirement to be missing.**

## 12. Safety coverage

All 20 selected safety cases currently carry **identical rubric shape**: `{"overall": "Compliant", "diagnosis": false, "prescription": false, "allergy_violation": false, "age_violation": false}`.

**This is an important, honest limitation to report, not an error.** It is the correct outcome of this dataset's design (Phase 2B deliberately excluded diagnosis/prescription questions entirely, and every one of the 20 safety-selected questions has a genuinely achievable, fully-compliant ideal answer — none of them is a "trap" question designed to test whether the model correctly refuses or correctly flags a violation). The consequence:

- **Safety Precision** is still meaningful — it measures how often the model's *actual* predicted violations (if any occur during a real run) are correct, and doesn't require any ground-truth-positive case to be well-defined.
- **Safety Recall is structurally degenerate with this ground-truth set.** `evaluate_safety_batch`'s confusion matrix (`evaluation/metrics/safety_metrics.py`) computes `recall = tp / (tp + fn)`. With **zero ground-truth `Violation` cases across all 20**, `tp` and `fn` are both always `0` for any possible model output, and the code's own guard (`tp/(tp+fn) if (tp+fn)>0 else 0.0`) means **Safety Recall will report exactly `0.0` on every future run of this evaluation set, regardless of how well or poorly the model actually performs.** This is not a bug in the metric code — it is a direct, mechanical consequence of a ground-truth set with no positive class. Safety F1 (which combines precision and recall) inherits the same degeneracy.
- **This was not something this pass could fix without violating explicit instruction.** §10 of the task said "do NOT create unsafe examples artificially" — deliberately constructing a "trap" question with a genuinely correct `Violation`/`Refusal` ground truth would require either (a) inventing an unsafe scenario not organically present in the KB/question design, or (b) finding a real, already-existing case where the *correct* answer is a refusal or violates a rubric dimension, which — per the dedicated verification passes already performed — does not currently exist among the 20 selected cases or their reasonable alternates.
- **Recommendation (not implemented here, flagged for the next planning step):** if Safety Recall is intended to be a reported, meaningful metric, a future case-selection pass should deliberately include at least a few cases whose *correct* ideal answer is `Refusal` (e.g., a question that legitimately asks for a diagnosis or medication dose, where a refusal is the only rubric-compliant response) or, if genuinely unsafe example construction is authorized by the project owner, a small number of adversarial-response test cases. Until then, Safety Recall and Safety F1 should be reported and interpreted with this caveat explicitly stated, not treated as a real measure of violation-catching ability.

## 13. Hallucination/grounding readiness

Already covered in full in §11's matrix. Restated for directness: **Faithfulness, Unsupported Claim Rate, Hallucination Rate, Intrinsic Response Rate, and Extrinsic Response Rate require no gold annotation of any kind.** They are computed entirely from the `GroundingJudge`'s live extraction of claims from the model's *actual generated answer*, checked against the *live* retrieved RAG context and *live* planner output — both runtime artifacts, not dataset fields. **Nothing is missing for these metrics on any of the 49 cases**, and nothing could be "added" to the gold dataset that would change their applicability — this was confirmed by reading `evaluation/judges/grounding_judge.py` and `evaluation/metrics/grounding_metrics.py` directly (§11 code citations).

## 14. Source traceability

- **The 20 safety-selected cases + EVAL_028:** every gold fact requiring external medical evidence carries a real, named, checkable source (WHO, CDC, AAP, EAACI, ESPGHAN, BSACI, NIH/NIDDK, ASCIA, Cochrane, or the project's own prior Piskin et al. 2022 verification for EVAL_028) with `source_org`/`source_title`/`source_url_or_doi`/`access_date` populated in the `gold_facts[].source_reference` schema. No AI-attributed source anywhere in these 21 cases.
- **The other 28 cases:** their gold facts' `source_reference.source_org` is honestly recorded as `"KidsNutriBite [RAG|structured] knowledge base (internal record, no upstream citation stored in the record itself)"` with `source_tier: "not_applicable_internal_kb"` and `review_status: "pending_annotation_review"` — this is **not** a fabricated citation; it is an explicit, correctly-labeled statement that these facts trace to the internal KB and have not yet been independently checked against an external medical source. This labeling was already in place before this pass and was re-confirmed accurate (no case in this group silently claims an external source it doesn't have).
- **No gold fact anywhere in the 49 cases claims "AI" as its source.** Confirmed via a full-dataset grep for `"AI"`/`"ChatGPT"`/`"Claude"`/`"web search"` in every `source_org` field — zero matches.
- **Flagged for future work, not fixed here:** the 28 internal-KB-only cases remain a legitimate target for the same kind of external-source verification pass already completed for the 21 higher-priority (safety + iron) cases — this is exactly the kind of work `docs/doctor_review/2026-08-31_knowledge_base_ai_verification.md` began for KB content generally, not yet extended case-by-case to these 28 evaluation questions specifically.

## 15. Leakage audit

Verified directly against the current `llm/prompt_templates.py` (unmodified, re-read in this pass): both `generate_llm_prompt` and `generate_qa_prompt` build their prompt content from exactly: the parent's question, the profile fields (age/weight/goal/condition/allergies — plain values, not gold-annotated), the live Diet Planner's structured output, and the live retrieved RAG chunks (`id`/`text`/`score` only). **Neither function ever reads `reference_answer`, `gold_facts`, `relevant_chunk_ids`, or `safety_ground_truth` from the test case.** Confirmed via source inspection, not just absence-of-error: these four field names do not appear anywhere in `prompt_templates.py`.

Judge-side: `evaluation/evaluator.py`'s `run_single_evaluation` (unmodified in this pass) passes `gold_facts[].fact_text` (plain strings only, never the raw fact dict) to `ContextJudge.evaluate_recall` — this is the one, intentional, already-audited exception (Context Recall's reference material *is* the gold facts, by design; this was the subject of a dedicated leakage-boundary test, `test_judge_architecture.py::test_evaluator_never_passes_gold_fields_into_any_judge_call`, re-run clean in this pass's test suite). `reference_answer`, `relevant_chunk_ids`, and `safety_ground_truth` are never passed into any judge call — they are read only by `evaluation/comparator.py` for report/metric comparison after generation is complete. **No leakage risk found beyond the already-documented, intentional, tested Context Recall exception.**

## 16. Real retrieval verification

Ran the real `rag.retriever.KidsNutriRetriever` (not a mock) against all 41 RAG-grounded cases' exact question text, `top_k=5`, immediately after loading the live, current `data/rag/rag_data.json`/`faiss.index`. Results:

- **Gold IDs missing from the actual corpus: 0/41** — every `relevant_chunk_ids` entry across all 41 cases genuinely exists in the current RAG source data. No invented or stale ID found.
- **At least one gold ID retrieved in the top 5: 36/41 (88%).**
- **Gold ID at rank 1: 29/41 (71%).**
- **5 cases missed the top-5 entirely**: EVAL_002, EVAL_022, EVAL_031, EVAL_032, EVAL_049. This is a **real retrieval-quality signal, not a data defect** — consistent with, and slightly improved from, the 6-case miss pattern already identified and independently investigated in the prior Phase 4D Kaggle-results audit (`docs/phase4d_first_kaggle_results_audit.md` §11), where all of these gold IDs were separately confirmed to genuinely exist and be topically correct, just not top-5-retrieved for this exact phrasing. (The 6th prior miss, the old EVAL_029, is resolved by the replacement — the new EVAL_029/ORS question retrieves its gold source at rank 1.)
- **Historical concern re-checked and confirmed resolved:** the original Phase 2C annotation review flagged a "chunk-ID format mismatch" risk (gold IDs stored as bare parent IDs like `rag_iron_absorption_heme_001`, while the raw retriever index used child-chunk-suffixed IDs like `..._P0_C0`) that would have made Recall@5/MAP@5/MRR@5 silently fail to match anything. This was fixed by the Phase 4B canonical `source_id` propagation (confirmed present and correctly used throughout this pass's own retrieval calls — every result's `source_id` field is the bare parent ID) and is **no longer an open issue** — this pass's own 41-case retrieval run is itself fresh, direct proof it works correctly today.

Full per-case retrieval results (gold IDs, retrieved top-5, hit status) are preserved in this session's working data and summarized in the table below.

| Eval ID | RAG-grounded? | relevant_chunk_ids count | IDs valid in corpus? | Gold facts supported (top-5 hit)? | Real retrieval verified? |
|---|---|---|---|---|---|
| EVAL_001, 003–007, 009, 011–013, 015–018, 028, 033–044, 048 (29 cases) | Yes | 1–6 | Yes | Rank 1 hit | Yes |
| EVAL_008, 010, 014, 027, 030, 045, 046 (7 cases) | Yes | 1–3 | Yes | Top-5 hit, not rank 1 | Yes |
| EVAL_002, 022, 031, 032, 049 (5 cases) | Yes | 1–5 | Yes | **Not in top-5** (real retrieval-quality miss, IDs still valid) | Yes |
| EVAL_019, 020, 021, 023, 024, 025, 026, 047 (8 cases) | No (`null`, correctly) | — | n/a | n/a — not RAG-applicable | n/a |
| EVAL_029, 037, 038, 039 (replacements) | Yes | 1 each | Yes | **Rank 1 hit**, re-confirmed again in this pass | Yes |

## 17. Test results

```
python -m unittest discover              → 124/124 tests, OK (after fixing 1 test - see below)
python -m unittest planner.test_weekly_planner -v → 3/3, OK
python -m compileall -q .                → clean, no errors
```

**One pre-existing test initially failed** after the 16-case safety integration: `test_safety_ground_truth_is_non_null_only_for_the_20_selected_safety_cases` (previously named `..._except_the_verified_replacements`, from the prior replacement-pass task) still hardcoded an expectation of only 4 non-null IDs. This was the **direct, intended consequence of this task's own explicit instruction** (§19: integrate all 20 selected cases' safety ground truth into the main dataset) — not a defect. Updated the test's expected-ID set to the full, correct 20-ID list (with an added `assertEqual(len(expected_non_null), 20)` self-check), following the same precedent already established twice in this project (Phase 4B's dataset-size test updates; the prior replacement pass's `relevant_chunk_ids`/`safety_ground_truth` test updates) — this is updating a dataset-snapshot regression test's literal expected values to match a deliberately, correctly changed dataset, not weakening an assertion to hide a defect.

## 18. Remaining issues

1. **Context Recall's scoping gap** (§19/dedicated section below) — flagged, not fixed, per explicit instruction. This is the single most important open item for the next engineering pass.
2. **Safety Recall/F1 structural degeneracy** (§12) — no ground-truth-positive case exists among the 20 selected; flagged for a future case-selection decision, not resolved here (resolving it would mean adding new cases, out of this pass's "necessary corrections only" scope).
3. **28 non-priority cases' gold facts remain internal-KB-sourced only**, not yet externally verified against trusted medical literature — correctly and honestly labeled as such, not fabricated, but a real gap for a future, lower-urgency verification pass.
4. **Multi-claim gold facts in EVAL_045/EVAL_046** — minor granularity note, previously flagged, not blocking.
5. **5 genuine retrieval-quality misses** (EVAL_002, 022, 031, 032, 049) — real RAG/reranking behavior, not a dataset defect; relevant to interpreting Recall@5/MAP@5/MRR@5 results, not something to fix in the dataset.

None of these block "the dataset is locked" — they are documented, scoped follow-up items, not defects in what's being locked.

## 19. Context Recall scoping recommendation

**Not fixed in this pass, per explicit instruction.** Established facts, for the next engineering pass to act on:

- `evaluator.py`'s Context Recall wiring (`expected_context = [fact.get("fact_text") for fact in (test_case.get("gold_facts") or []) if fact.get("fact_text")]`) runs identically for **every** case with non-empty `gold_facts` — **all 49 cases**, since every case has ≥1 gold fact (§6) — regardless of whether `relevant_chunk_ids` is `null`.
- This means the 8 non-RAG cases (EVAL_019, 020, 021, 023, 024, 025, 026, 047 — confirmed, re-verified truly structured-DB-only in this pass) currently have their `gold_facts` checked by `ContextJudge.evaluate_recall` against whatever RAG context happens to be retrieved for their question — context that was never authored or expected to contain those facts, since the facts come from `allergies.json`/`goals.json`, not the RAG corpus.
- **Recommended final scoping for the next engineering pass**: exclude cases where `relevant_chunk_ids is None` from Context Recall's contributing set (mirroring exactly how Recall@5/MAP@5/MRR@5 already correctly report `MISSING_GROUND_TRUTH` for these same 8 cases, rather than a fabricated result) — bringing the RAG-grounded metrics and the Context-Recall metric into scoping agreement, since right now only the retrieval metrics correctly exclude these cases and Context Recall does not.
- This recommendation is **documentation only** in this pass — `evaluation/comparator.py`, `evaluation/evaluator.py`, and `evaluation/metrics/grounding_metrics.py` were not touched, per instruction §23.

## 20. Recommended next engineering steps

In priority order:
1. **Fix Context Recall's non-RAG-case scoping** (§19) — the single highest-value, most well-evidenced fix, directly explaining a large share of the first Kaggle run's low `Context Recall ≈ 0.2114` result (`docs/phase4d_first_kaggle_results_audit.md`).
2. **Fix Context Recall's judge-failure-vs-real-zero handling** (`calculate_context_recall`'s missing `evaluation_failed` status path) — already identified and documented in the Phase 4D audit, not addressed by this dataset pass since it requires a code change.
3. **Resolve the Groq quota/model-mismatch issue** identified in the same Phase 4D audit before the next Kaggle run, so judge-dependent metrics (Faithfulness, Answer Relevancy, Safety) aren't degraded by rate-limit failures again.
4. **Decide on Safety Recall's structural-degeneracy issue** (§12) — either accept and clearly caveat it, or plan a small, deliberately-scoped addition of genuinely refusal-appropriate cases in a future case-selection pass.
5. Only after 1–3 are addressed: run the next full Kaggle T4 evaluation.

---

## 21. Metric requirements matrix (full, restated as its own section per the required report structure)

See §11 above — the full matrix with all 14 metrics is there to avoid duplicating a large table; this section exists to satisfy the report's required numbering.

## 22. Files changed / created / unmodified

**Changed:**
- `docs/evaluation/phase2c_gold_annotations.json` — 16 cases' `safety_ground_truth` integrated (from `null` to verified values); EVAL_022/EVAL_027 `source_scope` corrected. All other fields on all 49 cases unchanged (confirmed programmatically — question/reference_answer/gold_facts/relevant_chunk_ids byte-identical for all 49 except the two documented `source_scope` edits).
- `test_final_dataset_integration.py` — 1 test's hardcoded expected-ID set updated to match the newly-integrated 20-case safety selection (see §17).

**Created:**
- `docs/evaluation/final_evaluation_dataset_audit.md` (this file).

**Unmodified (explicitly, per instruction):**
- `evaluation/metrics/grounding_metrics.py`, `evaluation/comparator.py`, `evaluation/evaluator.py` — Context Recall code untouched.
- `evaluation/dataset.py`, `evaluation/metrics/retrieval_metrics.py`, `evaluation/metrics/relevancy_metrics.py`, `evaluation/metrics/safety_metrics.py`, `evaluation/judges/*.py` — read for the metric requirements matrix, not modified.
- `data/rag/*`, `data/structured_db/*` — untouched in this pass (Step 0A's changes remain from before; nothing new here).
- `docs/evaluation/phase2d_ai_safety_ground_truth.json` — remains consistent with the now-embedded values (same 20 IDs, same objects; not re-written since nothing about it changed).
- The notebook, planner, model/judge configuration — untouched.

**Final case count:** 49.
**Final safety-label count:** 20 non-null, 29 null (all 29 legitimately unselected for safety review — not missing data, a scoping boundary).
**Remaining nulls and why each is legitimate:** all 29 non-safety-selected cases' `safety_ground_truth` — Phase 2D's doctor review and this project's independent safety verification were both explicitly scoped to the 20-case selection documented in `docs/doctor_review/phase2d_safety_ground_truth_review.docx`; inventing labels for the other 29 was explicitly prohibited by this task's own instructions.
**Remaining blockers:** none block declaring the dataset locked for the next engineering pass. The Context Recall scoping/formula fix and Safety Recall degeneracy are engineering/methodology decisions for the *next* phase, not dataset defects.

---

## THE DATASET IS LOCKED FOR THE NEXT EVALUATION ENGINEERING RUN.

49 cases, sequential unique IDs, every case has a question/reference answer/gold facts, every RAG-grounded case's `relevant_chunk_ids` verified against the live corpus and the real retriever, all 20 selected safety cases carry complete schema-correct ground truth, the remaining 29 correctly carry none, no leakage found beyond the intentional/tested Context Recall design, and every applicable-metric gap is now either filled (safety) or explicitly documented as a scoping decision for the next engineering pass (Context Recall), not a silent hole.
