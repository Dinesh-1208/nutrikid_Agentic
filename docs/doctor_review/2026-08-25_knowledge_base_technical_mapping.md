# Knowledge Base Technical Mapping — Internal, Project Team Only

**Companion to `docs/doctor_review/2026-08-25_knowledge_base_medical_review.md`. Not for doctor review — this maps each medically-reviewed item to its eventual technical implementation, once (and only once) it is approved.**

**No implementation has occurred.** No JSON file has been modified, no record added/removed/consolidated, no FAISS/index rebuild performed. This document exists so the mapping decision doesn't have to be re-derived after doctor approval — it's pre-scoped now, executed later.

---

## KB-REVIEW-001 — Lactose intolerance taxonomy

- **Proposed destination**: LATER DECISION — depends entirely on the doctor's answer (separate file vs. same file with a distinguishing field vs. leave as-is with a clarifying note).
- **Existing record(s) affected**: `data/structured_db/allergies.json`, the two `lactose_intolerance` entries.
- **NEW RECORD or UPDATE EXISTING**: UPDATE EXISTING (most likely), contingent on doctor's decision.
- **Technical implementation notes**: If separated into its own conceptual category, `planner/diet_planner.py::get_allergy` (and any caller that treats "allergy" as a single lookup type) would need to still resolve it correctly — check whether the planner's allergy-matching logic assumes every entry is a true IgE-mediated allergy anywhere in its logic (not yet checked this session, deferred to implementation phase, since KB-REVIEW-001 itself only proposes a documentation/classification clarification, not new avoid_foods content, so functional risk is currently believed low but not yet verified).
- **FAISS/index rebuild required?**: No — `allergies.json` is structured DB, not RAG; no reindex needed regardless of how this resolves.

## KB-REVIEW-002 — Milk allergy avoid-foods completion

- **Proposed destination**: Structured DB.
- **Existing record(s) affected**: `data/structured_db/allergies.json`, records currently named `milk_lactose`, `milk` (×3), `cow_milk_protein_allergy`, `milk_protein_sensitive_enteropathy` (6 records total).
- **NEW RECORD or UPDATE EXISTING**: UPDATE EXISTING, likely consolidating 6 records into fewer — exact consolidation shape depends on doctor's review of how the BSACI Table 9 list should map onto existing project-specific terms (`curd`, `eggnog`, `milk_added_recipes`, etc.). Do not assume a 6→1 merge without doctor sign-off on wording; a 6→2 or 6→3 split (e.g. separating true IgE milk allergy from non-IgE milk protein enteropathy per KB-REVIEW-003) may be more medically accurate.
- **Technical implementation notes**: `planner/diet_planner.py::get_allergy` performs exact case-insensitive name matching (`allergy_name` lookup) — confirm the food-planning code path that consumes `avoid_foods` still receives a list of terms that match actual `foods.json`/`food_name`/`tags` vocabulary (cross-reference against the Phase 1 audit's tag-vocabulary-mismatch finding — a longer avoid_foods list is only useful if the planner can actually match those terms against real food records).
- **FAISS/index rebuild required?**: No.

## KB-REVIEW-003 — Milk allergy severity representation

- **Proposed destination**: LATER DECISION — this is a schema question (does `severity` need a second field, e.g. `onset_pattern: IgE-mediated / non-IgE-mediated`, or does the existing single field get a documented convention?), not resolvable until the doctor answers the medical-review question.
- **Existing record(s) affected**: Same 6 milk-family records as KB-REVIEW-002.
- **NEW RECORD or UPDATE EXISTING**: UPDATE EXISTING once schema question is resolved; may require a schema addition (new field) rather than a value change, which is a slightly larger change than a typical "UPDATE EXISTING RECORD" — flag this to the team before implementation, since it could affect `calculate_confusion_matrix`-adjacent safety-metric code if `severity` is ever wired into planner-side exclusion strictness (not currently the case, per Phase 1 audit — `severity` is stored but not read by `planner/diet_planner.py`'s matching logic as far as previously traced; **not re-verified this session**, re-check before implementing).
- **FAISS/index rebuild required?**: No.

## KB-REVIEW-004 — Nut allergy blanket-avoidance framing

- **Proposed destination**: LATER DECISION — this is the largest-scope item in the batch. If the doctor approves moving toward per-nut-type records, this could mean restructuring `nut_allergy` (currently 3 records with generic `["nuts"]`-style lists) into several new, more specific allergy records (e.g. `peanut_allergy`, `hazelnut_allergy`, ...), which is closer to NEW RECORD territory than a simple update.
- **Existing record(s) affected**: `data/structured_db/allergies.json`, `nut_allergy` records (3).
- **NEW RECORD or UPDATE EXISTING**: Likely a mix — some UPDATE EXISTING (refining current records), possibly NEW RECORDS if the doctor wants per-nut granularity. Genuinely depends on the doctor's scope decision; do not pre-build a specific schema until that's known.
- **Technical implementation notes**: If per-nut-type records are introduced, `profile["allergies"]` (the list a user/test-case supplies) would need to supply the more granular allergy name for the planner to look it up correctly — check `main.py`'s `--allergies` CLI arg parsing and the evaluation dataset's `profile.allergies` fields for whether they already use granular names anywhere, or would need a mapping/back-compat shim. **Not yet checked this session** — do before implementation.
- **FAISS/index rebuild required?**: No (structured DB only) — unless narrative RAG content about nut allergy is also added/changed as part of this, in which case yes for that portion.

## KB-REVIEW-005 — Duplicate fish entry

- **Proposed destination**: Structured DB.
- **Existing record(s) affected**: `data/structured_db/allergies.json`, the two `fish` records.
- **NEW RECORD or UPDATE EXISTING**: UPDATE EXISTING (delete one duplicate, keep the more complete one, or merge).
- **Technical implementation notes**: Simplest item in the batch — no external content change, straightforward record removal/merge once doctor confirms which fields to keep.
- **FAISS/index rebuild required?**: No.

## KB-REVIEW-006 — Egg allergy (INSUFFICIENT VERIFIED EVIDENCE)

- **Proposed destination**: N/A — no proposal to map, since no verified content exists yet.
- **Existing record(s) affected**: `data/structured_db/allergies.json`, `egg_protein` records (3) — unchanged for now.
- **NEW RECORD or UPDATE EXISTING**: N/A pending further sourcing.
- **Technical implementation notes**: None yet. Once a source is opened and verified (see the doctor doc's note on needing different access), re-run this item through the same research → doctor-review pipeline before any technical work.
- **FAISS/index rebuild required?**: N/A.

## KB-REVIEW-007 — Gluten introduction timing

- **Proposed destination**: Structured DB (primary — this is the existing `gluten_sensitivity` record's `description`/`avoid_foods` fields), possibly BOTH if a longer explanatory RAG chunk about the evidence/rationale is also wanted.
- **Existing record(s) affected**: `data/structured_db/allergies.json`, `gluten_sensitivity` record.
- **NEW RECORD or UPDATE EXISTING**: UPDATE EXISTING (`description` field wording; `avoid_foods` of `["wheat","barley","rye"]` was not contradicted by the source and likely doesn't need to change).
- **Technical implementation notes**: Low complexity — a wording refinement to an existing field, no new vocabulary/tag concerns identified.
- **FAISS/index rebuild required?**: No, unless a RAG chunk is also added (BOTH option) — in which case yes, `rag/indexer.py::build_index` would need to be re-run after `data/rag/rag_data.json` is updated.

## KB-REVIEW-008 — WHO complementary feeding guidance (NEW)

- **Proposed destination**: RAG (primary) — this is narrative/explanatory guidance well-suited to retrieval, matching the "explains why/what" role established for RAG in the Phase 1 audit. Could also inform structured `goals.json` fields (e.g. a `complementary_feeding` goal record with `required_tags`/`meal_frequency`) if the team wants it to also influence deterministic planning, but that's a bigger, separate design decision — default recommendation is RAG-only for this batch.
- **Existing record(s) affected**: None — this is new content, no existing record is being changed.
- **NEW RECORD or UPDATE EXISTING**: NEW RECORD(s) in `data/rag/rag_data.json` (likely 3-5 short chunks, one per key recommendation, following the existing corpus's ~50-300 char record-length convention observed in the Phase 1 audit).
- **Technical implementation notes**: New records need `id`, `text`, `metadata: {type, tags, source}` following the existing schema (Phase 1 audit found `source` populated in only ~10% of existing records — this is a chance to set a good precedent by including `"source": "WHO 2023 Complementary Feeding Guideline"` on every new record from this batch). Age-tagging (e.g. `tags: ["6_23_months", "complementary_feeding"]`) would help if any future retrieval filtering by age is built.
- **FAISS/index rebuild required?**: **Yes** — any new/changed `rag_data.json` content requires re-running `rag/indexer.py::build_index` to regenerate `faiss.index` and `metadata.pkl` before the new content is retrievable. Not done this session.

## KB-REVIEW-009 — ORS composition value discrepancy

- **Proposed destination**: Structured DB.
- **Existing record(s) affected**: `data/structured_db/goals.json`, the `ort_management_plans` record's `ors_composition_mmol_l.chloride` field (currently 65).
- **NEW RECORD or UPDATE EXISTING**: UPDATE EXISTING — but **do not change the value until the doctor confirms which figure (60 or 65) is correct**; this document only records that a discrepancy exists, per the strict source-conflict rule.
- **Technical implementation notes**: Also an opportunity to add a `source` field to this record (currently has none) once the doctor confirms the correct values — matching the Phase 1 audit's broader provenance-gap finding.
- **FAISS/index rebuild required?**: No.

## KB-REVIEW-010 — Egg allergy medication/vaccine hazards (NEW, scope question)

- **Proposed destination**: LATER DECISION — pending the doctor's judgment on whether this is in-scope for a dietary/nutrition assistant at all (flagged explicitly in the doctor doc). If approved as in-scope: RAG (narrative safety-note content, not planner-actionable).
- **Existing record(s) affected**: None.
- **NEW RECORD or UPDATE EXISTING**: NEW RECORD, if approved.
- **Technical implementation notes**: If added, tag clearly as `type: "safety_note"` or similar, distinct from dietary `avoid_foods`-style content, since it's about medications/vaccines, not food.
- **FAISS/index rebuild required?**: Yes, if added (same reason as KB-REVIEW-008).

## KB-REVIEW-011 — 6–23 month "avoid/limit" list (NEW)

- **Proposed destination**: RAG (narrative guidance) and possibly a `goals.json` entry (e.g. `avoid_tags` for added sugar/salt/trans-fat/sugar-sweetened beverages) if the team wants this to be planner-enforced, not just retrievable. Default recommendation for this batch: RAG-only, same reasoning as KB-REVIEW-008.
- **Existing record(s) affected**: None.
- **NEW RECORD or UPDATE EXISTING**: NEW RECORD(s) in `data/rag/rag_data.json`.
- **Technical implementation notes**: Tag as `tags: ["6_23_months", "avoid_list"]`, `source: "WHO 2023 Complementary Feeding Guideline"`. If later promoted to planner-enforced `avoid_tags`, must first verify matching `foods.json` tags exist (per the Phase 1 audit's tag-vocabulary-mismatch finding) or it will be silently inert.
- **FAISS/index rebuild required?**: Yes, if added.

## KB-REVIEW-012 — Milk type by age band (NEW)

- **Proposed destination**: RAG, possibly also `goals.json` age-banded milk guidance if planner enforcement is wanted later.
- **Existing record(s) affected**: None.
- **NEW RECORD or UPDATE EXISTING**: NEW RECORD.
- **Technical implementation notes**: Same tagging convention as KB-REVIEW-011 (`tags: ["6_11_months"]` / `["12_23_months"]`, `source`).
- **FAISS/index rebuild required?**: Yes, if added.

## KB-REVIEW-013 — Daily/frequent food-group guidance, 6–23 months (NEW)

- **Proposed destination**: RAG.
- **Existing record(s) affected**: None.
- **NEW RECORD or UPDATE EXISTING**: NEW RECORD.
- **Technical implementation notes**: Same tagging convention as above.
- **FAISS/index rebuild required?**: Yes, if added.

## KB-REVIEW-014 — Delayed allergen introduction may not prevent allergy (NEW, corroborating)

- **Proposed destination**: RAG, likely folded into the same chunk/topic as KB-REVIEW-019 rather than a standalone record, since it's corroborating rather than independent.
- **Existing record(s) affected**: None.
- **NEW RECORD or UPDATE EXISTING**: NEW RECORD (or merged into KB-REVIEW-019's record — doctor/team call).
- **Technical implementation notes**: If merged with KB-REVIEW-019, cite both sources in the record's `source` metadata.
- **FAISS/index rebuild required?**: Yes, if added.

## KB-REVIEW-015 — Choking-hazard foods (NEW, safety)

- **Proposed destination**: BOTH — RAG for the narrative safety content, and potentially `conditions.json`/`goals.json` `avoid_tags` (e.g. `choking_hazard`) if the team wants the planner to actively filter these foods out for young children, not just answer questions about them. This is the highest safety-value technical decision in the batch — recommend the team explicitly discuss planner enforcement, not just RAG retrieval.
- **Existing record(s) affected**: Possibly `foods.json` records for whole grapes, popcorn, nuts/seeds, hot dogs, hard candy, etc. — would need a tag added (e.g. `choking_hazard_under_4`) to each matching existing food record for planner enforcement to work; a cross-reference pass against `foods.json` is needed before implementation to see how many of the named foods already exist as records.
- **NEW RECORD or UPDATE EXISTING**: NEW RECORD(s) in RAG; UPDATE EXISTING (tag additions) in `foods.json` if planner enforcement is approved.
- **Technical implementation notes**: This is the one item in the batch most likely to need `planner/diet_planner.py` logic changes (age-conditional exclusion), not just data changes — flag for a design discussion, not a pure data-edit implementation.
- **FAISS/index rebuild required?**: Yes, for the RAG portion.

## KB-REVIEW-016 — Daily energy requirements by age, India-specific (NEW)

- **Proposed destination**: Structured DB — likely a new reference table/record type (e.g. a `nutrition_reference.json` or an addition to `goals.json`) rather than RAG, since these are precise numeric values best suited to deterministic lookup rather than retrieval-then-generation.
- **Existing record(s) affected**: None currently; may relate to whatever `goals.json` records already encode energy targets, if any (not confirmed this session — recheck before implementing).
- **NEW RECORD or UPDATE EXISTING**: NEW RECORD(s), schema TBD by the team (age-band → kcal/day table).
- **Technical implementation notes**: Also add as RAG content for conversational Q&A retrieval (BOTH), since parents will likely ask this as a natural-language question too, not just have it used deterministically by the planner.
- **FAISS/index rebuild required?**: Yes, if RAG content is also added.

## KB-REVIEW-017 — Daily protein requirements by age, India-specific (NEW)

- **Proposed destination**: Same as KB-REVIEW-016 — BOTH structured DB (numeric reference) and RAG (conversational retrieval), including the cereal-based-diet caveat as RAG narrative content.
- **Existing record(s) affected**: None currently confirmed; recheck `goals.json` before implementing.
- **NEW RECORD or UPDATE EXISTING**: NEW RECORD(s).
- **Technical implementation notes**: Keep the numeric table and the caveat text as separate concerns — the number goes to structured DB, the "why it might be higher in practice" explanation goes to RAG.
- **FAISS/index rebuild required?**: Yes, for the RAG portion.

## KB-REVIEW-018 — Plant-based milk substitution safety (NEW)

- **Proposed destination**: RAG (primary) — this is exactly the kind of explanatory/cautionary narrative content RAG is suited for. Cross-reference with KB-REVIEW-002/003 (milk allergy) since this is most relevant exactly when a milk-allergic child's family might otherwise reach for a plant-based substitute.
- **Existing record(s) affected**: None directly, but conceptually linked to the milk allergy records in `allergies.json`.
- **NEW RECORD or UPDATE EXISTING**: NEW RECORD.
- **Technical implementation notes**: Consider tagging so it's specifically retrievable when a milk-allergy query is being answered (`tags: ["milk_allergy", "substitution_safety"]`), not just generically indexed.
- **FAISS/index rebuild required?**: Yes, if added.

## KB-REVIEW-019 — Early peanut introduction reduces allergy risk (NEW)

- **Proposed destination**: RAG.
- **Existing record(s) affected**: None directly; conceptually relevant to `allergies.json` `nut_allergy`/`peanut` content and to infant-feeding guidance generally.
- **NEW RECORD or UPDATE EXISTING**: NEW RECORD.
- **Technical implementation notes**: Do NOT include a specific dosing amount/frequency (e.g. "2g protein 3x/week") since that figure was not independently verified this session — only the general early-introduction-timing finding should be encoded, per the doctor doc's explicit caveat.
- **FAISS/index rebuild required?**: Yes, if added.

## KB-REVIEW-020 — Undernutrition/wasting general principle (NEW)

- **Proposed destination**: RAG.
- **Existing record(s) affected**: Possibly relevant to existing malnutrition-related `conditions.json` records — not cross-checked this session, recheck before implementing.
- **NEW RECORD or UPDATE EXISTING**: NEW RECORD, kept general (per the doctor doc's caveat that detailed WHO protocol content was not accessible this session).
- **Technical implementation notes**: Keep scope narrow — this is a single general principle, not a full clinical protocol. Do not expand this record's content beyond what's stated in the doctor doc without a fresh verification pass.
- **FAISS/index rebuild required?**: Yes, if added.

## KB-REVIEW-021 — Iron-rich complementary foods from 6 months (COMPLETION of existing content)

- **Proposed destination**: RAG (new chunk) and/or an update to whatever existing `conditions.json` anemia/iron-deficiency record already exists — not cross-checked against current `conditions.json` this session, recheck before implementing to see if this is better framed as UPDATE EXISTING or NEW RECORD.
- **Existing record(s) affected**: Likely an existing anemia/iron-related `conditions.json` record — needs identification before implementation.
- **NEW RECORD or UPDATE EXISTING**: LATER DECISION, pending that lookup.
- **Technical implementation notes**: Tie explicitly to the 6-month complementary-feeding milestone in the record's text/tags, since that's the distinguishing new detail versus whatever anemia content may already exist.
- **FAISS/index rebuild required?**: Yes, if RAG content is added.

---

## Cross-cutting technical notes for the implementation phase (not doctor-facing)

1. **Any RAG addition in this batch (KB-REVIEW-008, possibly -007 and -010) requires a full `rag/indexer.py::build_index` re-run** before the new content is actually retrievable — this regenerates `data/rag/faiss.index` and `data/rag/metadata.pkl` from `data/rag/rag_data.json`. Budget for this as a discrete step after JSON edits, not assumed automatic.
2. **Structured DB changes (all allergy items) need no reindex** — `planner/diet_planner.py` reads `data/structured_db/*.json` directly at runtime.
3. **Tag-vocabulary consistency**: per the Phase 1 audit's confirmed finding that 85% of `conditions.json`/`goals.json` tags never match any `foods.json` tag, any new `avoid_tags`/`required_tags` introduced as part of these changes should be checked against actual `foods.json` tag vocabulary before merging, or they'll be silently inert in planner matching — this applies most directly to KB-REVIEW-004 if new nut-specific records are created with new tags.
4. **Testing after implementation**: once any batch is approved and implemented, re-run the existing `unittest discover` suite (unaffected by data-only changes, but confirms nothing broke) and manually verify at least one `--ask` query per changed condition/allergy to confirm the planner still resolves it correctly, per this project's established "test the golden path" practice.
5. This batch does not touch the evaluation dataset, gold facts, `relevant_chunk_ids`, or the notebook — none of that is affected by or relevant to this knowledge-base content work.
