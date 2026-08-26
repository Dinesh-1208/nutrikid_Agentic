# KidsNutriBite — Final Evaluation Dataset Schema (Phase 2A)

**Status: SCHEMA DESIGN ONLY. No questions, gold facts, chunk IDs, reference answers, or safety labels have been created. `evaluation/dataset.py` has not been modified. No knowledge-base, metric, or notebook file has been modified.**

---

## 1. Purpose

This document defines the field-by-field schema for the final ~50-question KidsNutriBite evaluation dataset, derived directly from what the current, finalized metric implementations (retrieval, RAG/generation, hallucination, safety) actually read — not from what would be generically nice to have. It also defines validation rules the later question-generation phase (2B) must satisfy.

It does **not** contain any evaluation question, gold fact, chunk ID, reference answer, or safety label. It does not include diet-planning/meal-planning cases — that module is still being developed separately.

---

## 2. Method: how this schema was derived

Every field below was traced to its actual consumer in the current code, read directly this session:

- `evaluation/dataset.py` (current 100-question `EVALUATION_DATA`, to be replaced)
- `evaluation/evaluator.py` (`KidsNutriEvaluator.run_single_evaluation`)
- `evaluation/comparator.py` (`KidsNutriComparator.compute_safety_metrics`, `run_comparison`)
- `evaluation/metrics/retrieval_metrics.py`, `grounding_metrics.py`, `relevancy_metrics.py`, `safety_metrics.py`
- `evaluation/judges/context_judge.py`, `grounding_judge.py`, `relevancy_judge.py`, `safety_judge.py`
- `test_safety_ground_truth.py`, `test_map_at_k.py`, `test_mrr_at_k.py`
- `data/recall5_annotation_template.json` (the existing, not-yet-filled-in gold-ID annotation scaffold)

No field name here was assumed from a generic RAG-evaluation template. Two fields in particular turned out **not** to mean what a generic template would assume, and the schema below is designed around the actual, verified behavior:

- `reference_answer` is currently **not read by any metric**. It flows only into human-readable CSV/report columns (`comparator.py`'s `detailed_records["Expected Answer"]`). Context Recall does not use it.
- `expected_context` (a flat list of strings/keywords) — not `reference_answer` — is what actually drives Context Recall today, via `ContextJudge.evaluate_recall`, which asks an LLM to atomize this list into facts and check their presence in the retrieved chunks.
- `is_pubmed` exists on every current dataset record but is read by **no code anywhere** (confirmed again this session; also flagged in the earlier `docs/claude_project_understanding.md` audit). It is dead metadata in the current dataset and is not carried forward as a required field.
- `is_safety` is preserved only as a topic/safety-relevance flag. It is **never** used to derive a safety outcome — `compute_safety_metrics` reads only `test_case["safety_ground_truth"]`, and `test_safety_ground_truth.py` explicitly tests that `is_safety=True` must never be silently treated as `ground_truth["overall"] == "Violation"`.
- Precision@5 needs **no gold data at all** — it is scored entirely from the ContextJudge's live LLM relevance judgments of whatever was retrieved. Recall@5, MAP@5, and MRR@5, by contrast, are strictly gold-`relevant_chunk_ids`-dependent. This asymmetry is a real, current property of the code, not an oversight to "fix" here.

---

## 3. Design principles

**A. Offline gold / annotation data** — hand-authored or expert-reviewed, used only *after* the production pipeline has already produced its retrieval/response, purely to score it. Never sent to the retriever or the LLM.

**B. User query / input data** — what is actually sent through the production pipeline (question text, structured patient profile). This is the only category visible to the retriever and to Qwen.

**C. Metadata** — organizes/filters cases (category, age group, source/provenance tags). Not sent to the model; not scored directly.

**D. Runtime outputs** — generated fresh every time the pipeline runs an evaluation (retrieved chunk IDs, LLM judge outputs, computed scores, latency). Never hand-authored, never stored as "gold" in the dataset file.

**Hard rule, confirmed against the actual prompt-construction code (`llm/prompt_templates.py::generate_llm_prompt`, called from `evaluator.py` with only `plan`, `retrieved_contexts`, and `query`):** gold annotation fields (`relevant_chunk_ids`, `gold_facts`/`expected_context`, `reference_answer`, `safety_ground_truth`) are never passed into the prompt. Only `question` and `profile` (via the planner) reach the production pipeline. The schema keeps these two groups structurally separate so this can't accidentally regress.

---

## 4. Core case schema

Field-by-field, grouped by the A/B/C/D categories above. "Consumed by" cites the actual code path.

### B. User query / input data (sent to the production pipeline)

| Field | Type | Required? | Purpose | Consumed by | Sent to model? |
|---|---|---|---|---|---|
| `question` | string | **Required** | The natural-language question sent to the retriever and, indirectly, to the LLM prompt. | `retriever.retrieve(question)`; `generate_llm_prompt(..., query=question)`; both judge prompts | Yes (via prompt) |
| `profile` | object | **Required** | Patient profile: `age` (float, years), `weight` (float, kg), `condition` (string, must match a `conditions.json` `condition_name`), `goal` (string, must match a `goals.json` `goal_name`), `allergies` (list of strings, must match `allergies.json` `allergy_name` values). | `planner.generate_meal_plan(profile)`; `SafetyJudge.evaluate_safety(..., profile)` reads `profile["age"]`, `profile["allergies"]` directly | Indirectly — the planner's derived meal plan (not the raw profile dict) is passed into the prompt |

### C. Metadata (organizes/filters; not sent to the model, not scored directly)

| Field | Type | Required? | Purpose | Consumed by | Sent to model? |
|---|---|---|---|---|---|
| `case_id` | string | **Required** | Stable unique identifier for the case, used to join runtime results back to gold data (`next(t for t in dataset if t["id"] == case["id"])` in `comparator.py`). Note: current code reads this key as `"id"`, not `"case_id"` — see §14 naming note. | Result-joining logic in `evaluator.py`/`comparator.py` | No |
| `category` | string | **Required** | Coarse topic bucket for filtering/reporting (e.g. `compute_safety_metrics(..., category_filter="allergies")`). | `comparator.py` category filtering; report grouping | No |
| `subcategory` | string | Optional | Finer-grained topic tag for readability/reporting only. Not read by any current metric code. | None currently — organizational only | No |
| `age_group` | string | **Required** (pediatric scope) | Human-facing pediatric age band, sourced from whichever authoritative guideline underlies the specific fact being tested (see §9). Distinct from `profile.age`, which is the exact numeric age fed to the planner. | Reporting/filtering only — no metric reads this directly today | No |
| `knowledge_area` | string | Optional | Which of the Phase-1/Phase-2 knowledge-base areas (A–I) the question probes (e.g. "allergy expansion", "age-specific feeding"). Purely organizational, for dataset-coverage auditing. | None | No |
| `source_scope` | string | Optional | Declares whether the question is answerable from RAG content, structured DB content, or both — helps a reviewer sanity-check that `relevant_chunk_ids` (if RAG-scoped) or planner-relevant profile fields (if structured-DB-scoped) were annotated consistently. | None (documentation aid only) | No |

### A. Offline gold / annotation data (used only for scoring, never sent to the model)

| Field | Type | Required? | Purpose | Consumed by | Sent to model? |
|---|---|---|---|---|---|
| `relevant_chunk_ids` | list of non-empty strings, or omitted/`None` | Conditional — required only for a case to get a real Recall@5/MAP@5/MRR@5 score; otherwise the case reports `MISSING_GROUND_TRUTH` for those three metrics (Precision@5 is unaffected either way) | The full gold set of RAG chunk IDs relevant to the question, used as the ground truth for rank-based retrieval scoring. See §6 for exact structural rules. | `retrieval_metrics.calculate_recall_at_k_details`, `calculate_ap_at_k_details` (→ MAP@5), `calculate_mrr_at_k_details` — all called directly with this field's value as `gold_relevant_chunk_ids` | No |
| `expected_context` (current name) / `gold_facts` (proposed structured replacement — see §7) | list of strings (current) / list of fact objects (proposed) | Conditional — required only for a case to get a real Context Recall score; an empty/absent list makes `ContextJudge.evaluate_recall` short-circuit to `{"facts": []}`, and `calculate_context_recall([])` returns `0.0` (a **real zero score**, not a missing-ground-truth status — this is a pre-existing implementation gap; Context Recall has no status-enum layer, unlike every other metric in this project) | `ContextJudge.evaluate_recall(retrieved_contexts, expected_context, ...)` → `grounding_metrics.calculate_context_recall(facts_list)` | No |
| `reference_answer` | string | Optional | Human-readable expected answer, shown in report CSVs (`detailed_records["Expected Answer"]`) for manual review. **Not consumed by any metric computation today.** | `comparator.py` CSV export only | No |
| `safety_ground_truth` | object, shape: `{"overall": "Compliant"|"Refusal"|"Violation", "diagnosis": bool, "prescription": bool, "allergy_violation": bool, "age_violation": bool}` | Conditional — required only for a case to get a real Safety Recall/Precision/F1 score; otherwise the whole batch reports `MISSING_GROUND_TRUTH` (today, with zero cases annotated, this is the status for every case) | `comparator.py::compute_safety_metrics` reads `test_case["safety_ground_truth"]` directly; feeds `evaluate_safety_batch` in `safety_metrics.py` | No |
| `provenance` | object (see §12) | Recommended for any case carrying `gold_facts`, `reference_answer`, or `safety_ground_truth` | Traceability back to the trusted source that justified the gold value, matching the trusted-source discipline established in the Phase 1 KB review. | Not read by any metric code — human/audit trail only | No |

### D. Runtime outputs (never hand-authored; generated fresh each evaluation run)

Not part of the dataset file at all — listed here only so it's clear what's already covered by existing runtime code and does **not** need a dataset field: `response`, `latency`, `retrieved_chunks`/`retrieved_chunk_ids`, `planner_output`, `safety_judge_raw`, `is_refusal` (deterministic keyword check in `evaluator.py`), all computed metric scores/statuses, `claims` (from `GroundingJudge`).

---

## 5. Retrieval gold structure (`relevant_chunk_ids`)

Traced directly from `retrieval_metrics.py` and the existing `data/recall5_annotation_template.json` scaffold:

- **Format**: a flat list (or set/tuple) of chunk-ID strings, e.g. shaped like the retriever's real IDs (`RAG_SOURCE_P0_C0` per the annotation template's own instructions). No real IDs are proposed in this document.
- **Multiple chunks allowed and expected**: yes — `total_relevant_count = len(gold_ids)` (a set) is the literal AP@K/Recall@K denominator (Manning, Raghavan & Schütze, Eq. 8.8), so a question with several genuinely relevant chunks must have all of them listed for Recall@5/MAP@5 to be meaningful.
- **Order does not matter for the gold list** — all three metrics coerce it to a Python `set` before comparing. Order matters only for the *retrieved* list (rank position), which is runtime output, not annotated.
- **Duplicates in the gold list are harmless** (deduped via `set()`) but should be avoided for annotation cleanliness.
- **Type strictness differs by metric — annotate defensively**: `calculate_recall_at_k_details` accepts any hashable, non-falsy value and coerces via `str()`. `calculate_mrr_at_k_details` and `calculate_ap_at_k_details` are strict — every element must already be a `str` instance with non-whitespace content, or the whole case reports `INVALID_GROUND_TRUTH` (score `None`) for that metric. **Conclusion: always annotate `relevant_chunk_ids` as a list of plain, non-empty strings.**
- **`None`/omitted vs. `[]` are NOT equivalent, and this is a real, current inconsistency in the code that the annotation process must work around, not "fix" here**:
  - `None` (field omitted) → `MISSING_GROUND_TRUTH` for all three metrics (Recall@5, MAP@5, MRR@5).
  - `[]` (present but empty) → `INVALID_GROUND_TRUTH` for Recall@5 (`total_relevant_count` reported as `0`), but → `MISSING_GROUND_TRUTH` for MAP@5/MRR@5 (both short-circuit on `if not gold_relevant_chunk_ids`).
  - **Rule for the annotation phase: never annotate `[]` to mean "no relevant chunks exist." Omit the field entirely (or set it to `None`) for genuinely gold-free cases.** If a question is deliberately being tested for "the KB has no answer to this," that is a distinct annotation decision requiring its own convention — not something to invent here.
- **Sufficiency vs. completeness**: annotators must identify **every** relevant chunk in the full RAG corpus for a question, not just chunks that happen to already appear in the system's top-5 retrieval. Because `total_relevant_count` is the true denominator, under-annotating (listing only "enough" chunks to make top-5 look good) would silently inflate Recall@5/MAP@5. This is a requirement for the later annotation task, not something this schema can enforce mechanically — it's a process discipline note for whoever fills the template.
- **Relationship to top-5 retrieval**: `k=5` is applied only to the *retrieved* list inside each metric function (`retrieved_ids[:k]`); the gold list itself is never truncated to 5. A case may legitimately have more than 5 gold-relevant chunks (Recall@5 would then have a ceiling below 1.0 by construction — that's expected, not a bug).

No actual chunk IDs are proposed here. The existing `data/recall5_annotation_template.json` (all `relevant_chunk_ids: []`, unfilled) is the intended tool for the later annotation task, once real retriever IDs are pulled from the live index.

---

## 6. Gold fact structure (`gold_facts`, superseding today's flat `expected_context`)

**What Context Recall currently needs, exactly**: `ContextJudge.evaluate_recall` takes a flat list of strings (`expected_contexts`) and asks an LLM to (1) atomize them into individual factual statements and (2) verify each against the retrieved chunks. `grounding_metrics.calculate_context_recall` then just computes `supported_facts / total_facts` from the judge's per-fact `is_present` booleans. **No fact-level `fact_id`, source reference, or importance flag is read by any code today** — the current implementation only needs the raw text list.

Given that, and given the project's now-established trusted-source discipline (Phase 1 KB review), the schema proposes evolving the flat list into a lightweight structured form — additive, not required by the metric math, but required by the project's own provenance rules for anything treated as gold medical content:

| Field | Type | Required? | Purpose |
|---|---|---|---|
| `fact_text` | string | **Required** (this is the only part the current Context Recall implementation actually consumes) | The atomic clinical fact statement — functionally replaces one entry of the current `expected_context` list. |
| `fact_id` | string | Optional | Stable ID for traceability/versioning across dataset revisions. Not read by metric code. |
| `source_reference` | object (see §12 provenance shape) | Recommended | Which trusted source justifies this fact, consistent with the Phase 1 KB review discipline. Not read by metric code — audit trail only. |
| `chunk_reference` | string or list of strings | Optional | If this fact is expected to be groundable in a specific RAG chunk, note it here — separate from `relevant_chunk_ids` (which is retrieval-ranking gold, not fact-verification gold), though they will often overlap for the same case. |
| `importance` | enum: `required` / `supporting` | Optional | Distinguishes a fact the answer *must* cover from a nice-to-have supporting detail. Not read by current metric code (today, every fact contributes equally to the recall ratio) — recording this now avoids re-deriving it later if a weighted-recall variant is ever built. |

**Backward-compatibility note for Phase 2B**: since `ContextJudge.evaluate_recall` only needs plain strings, the generation task can either (a) keep authoring a flat `expected_context: [str, ...]` list exactly as today and wrap it in `gold_facts: [{"fact_text": ..., ...}, ...]` only for the provenance-tracking fields, or (b) the evaluator's call site would need a one-line adjustment to extract `fact_text` before passing the list to the judge. That adjustment is a Phase 2C/implementation-time decision, not part of this schema-design task.

---

## 7. Reference answer

**Traced finding**: `reference_answer` is **not required by any current metric**. It is stored on every existing dataset record and flows only into `comparator.py`'s `detailed_records` CSV export as a human-readable "Expected Answer" column, next to the model's actual response, for manual reviewer comparison. No RAGAS-style metric (Faithfulness, Context Recall, Answer Relevancy) reads it — Faithfulness/Unsupported-Claim-Rate check claims against retrieved context + planner output, and Context Recall checks `expected_context` (not `reference_answer`) against retrieved context.

**Decision, per the instruction not to assume it's required just because it's generally useful**: `reference_answer` is an **optional, per-case field**. It should still be authored for most cases in the final ~50-question set, because it materially helps human doctor review of model outputs, but it is not a load-bearing field for any automated score, and the dataset validator (§16) must not require it.

---

## 8. Safety case schema — ground truth vs. judge prediction

The current `SafetyJudge.evaluate_safety` prediction shape (already implemented, unchanged) is:
```json
{"reasoning": "...", "diagnosis": false, "prescription": false, "allergy_violation": false, "age_violation": false, "overall": "Refusal|Compliant|Violation"}
```
This is **runtime output** (`safety_judge_raw` in `evaluator.py`) — never hand-authored, never stored in the dataset.

The **gold** counterpart the code already expects, exactly (per `compute_safety_metrics` and `test_safety_ground_truth.py`), is `safety_ground_truth`, with the same four boolean rubric keys plus `overall`, but expert/doctor-authored rather than model-generated:

| Field | Type | Required? | Purpose |
|---|---|---|---|
| `safety_ground_truth.overall` | enum: `Compliant` / `Refusal` / `Violation` | **Required if the field is present at all** | Converted to a binary "Violation present?" label by `evaluate_safety_batch` — this is what drives Safety Recall/Precision/F1. |
| `safety_ground_truth.diagnosis` | bool | **Required if present** | Rubric-level gold label #1 (definitive diagnosis given). |
| `safety_ground_truth.prescription` | bool | **Required if present** | Rubric-level gold label #2 (medication/dosage prescribed). |
| `safety_ground_truth.allergy_violation` | bool | **Required if present** | Rubric-level gold label #3 (recommended an allergen). |
| `safety_ground_truth.age_violation` | bool | **Required if present** | Rubric-level gold label #4 (age-inappropriate food suggested). |
| `safety_annotation_notes` | string | Optional | Free-text rationale from the doctor/expert annotator — mirrors the doctor-review-document discipline already used for KB content. |
| `safety_annotation_provenance` | object (see §12) | Recommended whenever `safety_ground_truth` is present | Who/what reviewed this label and against what standard — same audit-trail purpose as KB provenance. |
| `safety_review_status` | enum: `pending` / `doctor_approved` / `needs_revision` | Recommended | Tracks whether a proposed label has cleared expert review, matching the KB doctor-review workflow already established (research → doctor review → approval → implementation). |

**Nothing is invented here** — no case in this schema document carries an actual `safety_ground_truth` value; that is explicitly Phase 2D, requiring real doctor/expert annotation.

**Refusal Rate on known-safe prompts — an implementation gap, not just a schema gap.** This metric is **not computed by any code today**; `comparator.py` contains an explicit comment marking it deferred "until ground truth for known-safe prompts exists." Tracing what it would need: the runtime already computes `is_refusal` (a deterministic keyword check in `evaluator.py`) for every case. Once `safety_ground_truth.overall` exists, "known-safe prompt" doesn't need a *new* dataset field — it falls directly out of `safety_ground_truth.overall != "Violation"` (i.e., a case a doctor has certified does **not** require refusal). So: `Refusal Rate on known-safe prompts = count(is_refusal AND safety_ground_truth.overall != "Violation") / count(safety_ground_truth.overall != "Violation")`. This schema section exists so that decision is recorded now; actually wiring the calculation into `comparator.py` is implementation work for a later phase, not part of this schema task.

---

## 9. Pediatric / age metadata

KidsNutriBite's scope is 0–10 years per the current project constraint (diet-planning cases excluded for now, but the *non-planning* knowledge questions still span the full pediatric range). Two distinct age concepts already exist in the code and must not be collapsed into one field:

- `profile.age` (numeric, years, sometimes fractional for infants — e.g. `0.5` for 6 months) — the exact value fed to `planner.generate_meal_plan` and `SafetyJudge`. This is **input data**, required whenever a case exercises the planner/profile path.
- `age_group` (categorical, metadata-only) — a human-facing band for organizing/reporting the dataset.

**Per the explicit instruction not to invent age-band cutoffs**: this schema does not fix a single universal set of band boundaries. Different trusted sources already used in the KB expansion work define their own pediatric bands (WHO: 0–5m / 6–23m; ICMR-NIN: 1–3y / 4–6y / 7–9y; KidsNutriBite's own existing structured-DB condition names already encode bands like `infant_6_8_months` / `infant_9_12_months` / `child_above_1_year`). The schema's `age_group` field should record **whichever band the specific question's underlying trusted source actually uses**, not a KidsNutriBite-invented universal scale — exactly the same principle already applied in the KB doctor-review documents. Reconciling these into one master project-wide age taxonomy (if ever needed) is a separate decision for the team, not something to decide inside a dataset-schema task.

**Hard constraint carried into validation (§16)**: no case may use an age value or age-framed recommendation that is adult-only or diet-planning-scoped.

---

## 10. Category taxonomy

Verified against the **actual current knowledge scope** (RAG's `type` vocabulary + structured DB's `conditions`/`goals`/`allergies` content, from the Phase 1 KB audit, plus the 9 Phase-2 knowledge areas A–I), and against the current dataset's own 5 categories (`conditions`, `goals`, `allergies`, `food_suitability`, `general_nutrition`) — collapsed into a **manageable 6-category set**, explicitly excluding diet-planning:

1. **General Nutrition & Nutrients** — macronutrient/food-group basics, balanced-diet principles, micronutrient importance.
2. **Age-Specific Feeding** — infant/complementary feeding, toddler/preschool, school-age feeding guidance (knowledge questions, not full meal plans).
3. **Allergies & Intolerances** — what to avoid, severity, substitution safety, taxonomy clarifications (per the ongoing allergy consolidation work).
4. **Pediatric Conditions** — anemia, malnutrition/growth faltering, illness-related feeding, other condition-specific nutrition guidance.
5. **Food Safety & Suitability** — choking hazards, age-appropriateness of specific foods, safe food handling/preparation. (Distinct from diet planning — these are single-fact suitability/safety questions, not "plan my child's week.")
6. **Growth, Development & Reference Data** — anthropometric norms, RDA/nutrient reference values, growth milestones (the non-planning portion of today's heterogeneous `goals` category).

This taxonomy must be **re-validated against whatever knowledge base is actually approved** at Phase 2B question-generation time — per the project's own rule that questions may only be written from knowledge that then exists. It is a proposed structure, not a locked-in final list.

---

## 11. Provenance

**Practicality decision, per the instruction to keep the schema practical**: not every field needs its own independent provenance block. Provenance is attached at exactly the two points where a hand-authored medical/nutrition claim could otherwise be untraceable:

- Per-`gold_facts` entry (`source_reference`, §6)
- Per-case `provenance` for `reference_answer`/`safety_ground_truth` (this section)

**Provenance object shape** (reused in both places):

| Field | Type | Required? |
|---|---|---|
| `source_org` | string | **Required** whenever provenance is attached at all |
| `source_title` | string | **Required** |
| `source_url_or_doi` | string | **Required** |
| `access_date` | string (date) | **Required** |
| `exact_location` | string (page/section/table) | **Required** |
| `source_tier` | enum: `tier1_government_public_health` / `tier2_professional_medical_org` / `tier3_peer_reviewed_research` | **Required** — mirrors the strict trusted-source policy already established for KB work |
| `review_status` | enum: `pending_doctor_review` / `doctor_approved` / `doctor_rejected` / `insufficient_verified_evidence` | **Required** |

This is deliberately the same shape already used informally in the doctor-review documents (`docs/doctor_review/2026-08-25_knowledge_base_medical_review.md`) — no new provenance concept is introduced, just formalized into a reusable object.

---

## 12. Metric → field matrix

| Metric | Required schema fields | Gold data needed? | Runtime data needed? |
|---|---|---|---|
| Precision@5 | `question` (to retrieve against) | **No** — scored entirely by live LLM judgment of whatever was retrieved | Retrieved contexts; `ContextJudge.evaluate_precision` output |
| Recall@5 | `question`, `relevant_chunk_ids` | **Yes** — `MISSING_GROUND_TRUTH` without it | Retrieved chunk IDs |
| MAP@5 | `question`, `relevant_chunk_ids` | **Yes** | Retrieved chunk IDs |
| MRR@5 | `question`, `relevant_chunk_ids` | **Yes** | Retrieved chunk IDs |
| Context Recall | `question`, `gold_facts`/`expected_context` | **Yes** (though today an absent/empty list silently scores `0.0` rather than reporting missing — a pre-existing gap, not something this schema-only task fixes) | Retrieved contexts; `ContextJudge.evaluate_recall` output |
| Faithfulness | `question`, `profile` | No dataset gold needed — scored against retrieved context + planner output, not a hand-authored answer | Generated response; retrieved contexts; planner output; `GroundingJudge` claims |
| Answer Relevancy | `question` | No dataset gold needed — compares the question to hypothetical questions reverse-engineered from the response | Generated response; `RelevancyJudge` output; embedding model |
| Unsupported Claim Rate | `question`, `profile` | No dataset gold needed (same claims pipeline as Faithfulness) | Same as Faithfulness |
| Response Hallucination Rate | `question`, `profile` | No dataset gold needed | Same claims pipeline (`is_hallucinated`, derived from `unsupported_claim_rate_details`) |
| Intrinsic Response Rate | `question`, `profile` | No dataset gold needed | Same claims pipeline (`has_intrinsic_claim`) |
| Extrinsic Response Rate | `question`, `profile` | No dataset gold needed | Same claims pipeline (`has_extrinsic_claim`) |
| Safety Recall | `question`, `profile`, `safety_ground_truth` | **Yes** — `MISSING_GROUND_TRUTH` without it | `SafetyJudge` output (`safety_judge_raw`) |
| Safety Precision | `question`, `profile`, `safety_ground_truth` | **Yes** | `SafetyJudge` output |
| Safety F1 | `question`, `profile`, `safety_ground_truth` | **Yes** | `SafetyJudge` output |
| Refusal Rate on known-safe prompts | `question`, `profile`, `safety_ground_truth` | **Yes** (via `safety_ground_truth.overall != "Violation"`) — **and this metric is not yet implemented in `comparator.py` at all; wiring it up is future implementation work, not covered by this schema task** | Deterministic `is_refusal` flag (already computed in `evaluator.py`) |

---

## 13. Required vs. optional fields

**REQUIRED CORE FIELDS** (every case must have these, regardless of category):
- `case_id`
- `question`
- `category`
- `profile` (all four sub-fields: `age`, `weight`, `condition`, `goal`, `allergies` — `allergies` may be an empty list)
- `age_group`

**OPTIONAL / CONDITIONAL FIELDS** (present only when the case is meant to support the corresponding metric, or when useful for review):
- `relevant_chunk_ids` — only for cases meant to carry real Recall@5/MAP@5/MRR@5 scores
- `gold_facts` / `expected_context` — only for cases meant to carry a real Context Recall score
- `reference_answer` — optional on any case, recommended for most, required by no metric
- `safety_ground_truth` (+ `safety_annotation_notes`, `safety_annotation_provenance`, `safety_review_status`) — only on cases selected for doctor-reviewed safety annotation (not every case needs to be a safety case)
- `subcategory`, `knowledge_area`, `source_scope` — organizational only
- `provenance` / `source_reference` — recommended wherever gold medical content exists, not mechanically enforceable as "required" without knowing yet which facts will need it

**Explicit non-requirement, per the instruction**: safety-specific gold fields are never required on a plain nutrition-fact case. A case with no `safety_ground_truth` simply does not contribute to Safety Recall/Precision/F1/Refusal-Rate aggregates (excluded, not scored as a failure) — this already matches how `compute_safety_metrics` behaves today (`missing_ground_truth_cases` counted and reported separately, never silently treated as zero).

---

## 14. Naming note (flagged, not changed)

The current code reads the unique identifier as `"id"` (`test_case["id"]`, `test_case.get("id", "N/A")`), not `"case_id"`. This document uses `case_id` throughout because it is the clearer name for a schema-design document, but implementing this schema (Phase 2C+) must either (a) keep the on-disk key literally named `id` to match existing code, or (b) rename it and update every `test_case["id"]`/`case["id"]` read site. That is an implementation decision for a later phase — flagging it now so it isn't rediscovered as a surprise bug during dataset-generation.

---

## 15. Placeholder example — schema shape only

No real question, gold fact, chunk ID, or safety label appears below. All values are illustrative placeholders.

```json
{
  "case_id": "EXAMPLE_001",
  "question": "<question placeholder>",
  "category": "<one of the 6 taxonomy categories>",
  "subcategory": "<optional finer topic placeholder>",
  "age_group": "<age band placeholder, sourced from the fact's own guideline>",
  "knowledge_area": "<optional Phase-2 knowledge-area placeholder>",
  "source_scope": "<rag | structured_db | both>",

  "profile": {
    "age": 0.0,
    "weight": 0.0,
    "condition": "<placeholder condition_name>",
    "goal": "<placeholder goal_name>",
    "allergies": []
  },

  "relevant_chunk_ids": null,
  "gold_facts": [
    {
      "fact_id": "<placeholder>",
      "fact_text": "<placeholder atomic fact text>",
      "source_reference": {
        "source_org": "<placeholder>",
        "source_title": "<placeholder>",
        "source_url_or_doi": "<placeholder>",
        "access_date": "<placeholder date>",
        "exact_location": "<placeholder>",
        "source_tier": "tier1_government_public_health",
        "review_status": "pending_doctor_review"
      },
      "chunk_reference": null,
      "importance": "required"
    }
  ],

  "reference_answer": "<optional placeholder reference answer text>",

  "safety_ground_truth": null,
  "safety_annotation_notes": null,
  "safety_annotation_provenance": null,
  "safety_review_status": null
}
```

`relevant_chunk_ids: null` and `safety_ground_truth: null` are shown explicitly to illustrate the "omit/None rather than empty list" rule from §5 — not every example case needs every gold field populated.

---

## 16. Dataset validation rules (for the Phase 2B generation task to satisfy)

1. `case_id` (or `id`, per §14's resolution) must be unique across the entire dataset.
2. `question` must be non-empty, non-whitespace text.
3. `category` must be one of the approved taxonomy values (§10), re-validated against the then-current knowledge base.
4. `profile` must always be present with all four required sub-fields; `profile.condition`/`profile.goal`/`profile.allergies[*]` must correspond to real `condition_name`/`goal_name`/`allergy_name` values in the then-current structured DB (no invented profile values).
5. **No diet-planning/meal-planning cases** may be included in this dataset version.
6. **No adult-only case content.** Every case must reflect a pediatric-appropriate (0–10y, per current project scope) question and, where a recommendation differs by age, must be tagged to the correct source-specific `age_group`, never silently generalized from an adult recommendation.
7. `relevant_chunk_ids`, if present, must be a non-empty list of plain, non-empty strings corresponding to chunk IDs that actually exist in the live RAG index at annotation time (never invented IDs) — see §5's `None`-vs-`[]` rule.
8. `gold_facts`/`expected_context`, if present, must have non-empty `fact_text` for every entry; any entry carrying a `source_reference` must have all required provenance sub-fields (§12) filled in, never partially.
9. `safety_ground_truth`, if present, must include all four rubric booleans and a valid `overall` enum value — partial safety ground truth (e.g., `overall` without the rubric flags) must be rejected, not silently defaulted.
10. Gold annotation fields (`relevant_chunk_ids`, `gold_facts`, `reference_answer`, `safety_ground_truth`) must never be read by, or copied into, any code path that constructs the production LLM prompt — this must remain mechanically true, not just true by convention (e.g., verifiable by grepping `llm/prompt_templates.py` and `evaluator.py`'s prompt-construction call for any of these key names).
11. No two cases should be exact duplicate questions unless a documented, deliberate reason exists (e.g., testing the same fact across two different `age_group`s) — the current dataset's `Q_ALL_11`–`Q_ALL_20` pattern (ten near-identical templated questions varying only by age) is an example of what to avoid repeating at this scale for a curated 50-question set.
12. Every case authored against a trusted source (per the Phase 1/Phase 2 KB review discipline) must carry a `provenance`/`source_reference` block with `source_tier` set truthfully — no case may claim `tier1_government_public_health` sourcing without an opened, verified source (mirrors the KB review's "no fabrication" rule directly).
13. A case must not carry a `safety_ground_truth` unless it has actually cleared doctor/expert review (`safety_review_status: doctor_approved`) — a pending or self-authored safety label must not silently feed Safety Recall/Precision/F1 as if it were ground truth.

---

## 17. Later-phase workflow boundary

**PHASE 2A — NOW.** Schema design only (this document). No questions, gold facts, chunk IDs, reference answers, or safety labels exist yet.

**PHASE 2B — LATER.** Generate ~50 evaluation questions using only knowledge actually present in the then-approved knowledge base, following the category taxonomy (§10) and age-metadata approach (§9) defined here. No diet-planning questions.

**PHASE 2C — LATER.** Create `gold_facts`/`expected_context`, `relevant_chunk_ids` (via the live RAG index, using the existing `data/recall5_annotation_template.json`-style process), and `reference_answer` for the generated questions.

**PHASE 2D — LATER.** Create expert/doctor-reviewed `safety_ground_truth` for the subset of cases selected for safety evaluation, following the same research → doctor-review → approval workflow already used for KB content.

**PHASE 2E — LATER.** Update `evaluation/dataset.py` (or its replacement) and the notebook, and run the final evaluation.

No Phase 2B–2E activity has been performed as part of this task.

---

## Summary of findings from this audit

- 4 metrics (Precision@5, Faithfulness, Answer Relevancy, Unsupported Claim Rate, Response/Intrinsic/Extrinsic Hallucination Rate — 6 in total) require **no dataset-authored gold data at all**; they are scored from live LLM judgments and/or the production pipeline's own retrieved context/planner output.
- 3 retrieval metrics (Recall@5, MAP@5, MRR@5) and Context Recall are **strictly gold-data-dependent**, and today have zero real gold data in `evaluation/dataset.py` (`relevant_chunk_ids` doesn't exist on any current record; `data/recall5_annotation_template.json` is unfilled).
- 3 safety metrics (Recall, Precision, F1) are strictly gold-dependent and today report `MISSING_GROUND_TRUTH` for 100% of cases, by design (the ground-truth-fabrication bug was already fixed earlier this project; the honest gap remains open pending doctor annotation).
- Refusal Rate on known-safe prompts is not implemented in any code path yet — this schema positions `safety_ground_truth` to support it later without inventing a redundant field, but the calculation itself is future implementation work.
- `reference_answer` and `is_pubmed` are both currently present on every dataset record yet consumed by no metric; `reference_answer` is kept as optional/recommended (human review value), `is_pubmed` is not carried forward as a schema field.
- No code, dataset, knowledge-base JSON, notebook, or metric file was modified while producing this document.
