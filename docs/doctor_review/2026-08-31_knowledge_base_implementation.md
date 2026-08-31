# KidsNutriBite Knowledge Base — Implementation Log

**Date:** 2026-08-31
**Source of truth for this pass:** `docs/doctor_review/2026-08-31_knowledge_base_ai_verification.md` (the independent AI verification report). This log records what was actually applied to the live knowledge-base files, exactly as scoped by that report's lettered items A–I.
**Doctor-review status:** Mam's response to the original doctor-review document is still pending. Nothing implemented here is doctor-approved — these are the independently-verified, evidence-sufficient changes the team decided not to block on. When Mam responds, her feedback governs any correction pass, and this document does not claim otherwise. No "provisional" label was added to the production data, per instruction.
**Not committed / not pushed**, per instruction. This is a working-tree change only, for review before the next evaluation phase.

---

## 1. What was implemented, and why

Scope for this pass was the 9 lettered items (A–I) explicitly named in the implementation instructions, all of which the verification report rated sufficiently evidenced. Two items (2.2 peanut introduction, egg hidden-ingredient terms / "Rapid-3") were in the verification report but **not** in the lettered A–I list for this pass, and were deliberately left unimplemented — see §4.

### A. Honey/botulism mislabel — CORRECTED
- `data/structured_db/goals.json`, `botulism_prevention_management.preventative_rules`: `"Avoid honey for infants < 1 year (SIDS risk)"` → `"Avoid honey for infants < 1 year (infant botulism risk)"`.
- `data/structured_db/conditions.json`, `botulism.tags`: `"SIDS_risk"` → `"infant_botulism_risk"`.
- **Why:** these two records contradicted the KB's own correct narrative chunk (`rag_honey_infant_warning_001`, unchanged, already correctly attributes the risk to infant botulism). CDC and AAP both attribute honey avoidance under 12 months to infant botulism, not SIDS.
- No RAG counterpart needed — the correct narrative content already existed.

### B. Choking-hazard knowledge — ADDED
- New RAG record `rag_choking_hazard_foods_001`: high-risk foods for under-4s (whole grapes, hot dogs, hard/sticky candy, raw carrots, popcorn, thick nut butter, large meat/cheese chunks) and safe-preparation guidance (cut small, cut grapes in quarters, cut hot dogs lengthwise, spread nut butter thinly, always seated and supervised).
- **Why:** this was the single largest gap found in the audit — zero prior coverage of choking safety anywhere in the KB, on a platform whose core purpose is guiding what young children eat.
- **India-specific foods:** deliberately **not added**, per instruction — the verified sources (AAP, USDA WIC) don't cover India-specific items, and inventing them would violate the "do not guess" rule.

### C. ORS composition — UPDATED
- `data/rag/rag_data.json`, `rag_hypo_osmolar_ors_benefits_001`: text updated from Sodium/Glucose only to the full WHO/UNICEF reduced-osmolarity composition (Sodium 75, Potassium 20, **Chloride 65**, Citrate 10, Glucose 75 mmol/L, total osmolarity 245 mOsm/L). `source` metadata field added.
- **Why:** resolves the doctor-review document's open Chloride question (65, not 60 — three independent technical sources converged on 65) and fills in the three composition values (K, Cl, Citrate) that were entirely missing from the prior record.
- Same record ID preserved (UPDATE, not a new record) — this is the correct, more complete version of the same fact, not a competing one.

### D. Standalone sesame allergy — ADDED
- New structured record in `data/structured_db/allergies.json`: `{"allergy": "sesame_allergy", "avoid_foods": ["sesame_powder"], "severity": "high", "description": ...}`.
- `sesame_powder` was **removed** from the consolidated `nut_allergy` record's `avoid_foods` (see H) — it now lives only under its own `sesame_allergy` entry.
- New RAG record `rag_sesame_major_allergen_001`, narrating sesame's status as a major allergen in its own right (FDA FASTER Act 9th allergen; EU 14-allergen list).
- **Why:** sesame was previously buried as a bare tag inside `nut_allergy`, with no standalone representation and nothing a parent asking "is sesame a major allergen" could retrieve.

### E. Gluten-related wording — CORRECTED
- `data/structured_db/allergies.json`, `gluten_sensitivity.description`: replaced the stale "Avoidance in early infancy (before 4-6 months)" with the current ESPGHAN 2024 4–12-month introduction-window wording, and an explicit note that coeliac disease is a distinct diagnosis from general gluten sensitivity.
- `data/structured_db/conditions.json`, `coeliac_sprue.description`: replaced "Gluten sensitivity leading to malabsorption" (a diagnosis-conflating description) with an accurate, standalone definition: coeliac disease as an autoimmune reaction to gluten, distinct from non-coeliac gluten sensitivity.
- New RAG record `rag_gluten_introduction_window_001` carrying the same corrected 4–12-month window and the coeliac/gluten-sensitivity distinction, narratively.
- **Why:** the old wording predated the 2024 ESPGHAN position paper and read as a delay-based recommendation inconsistent with current evidence; the two diagnoses (coeliac disease vs. gluten sensitivity) were being described as if one were a symptom of the other.

### F. Lactose intolerance vs. cow's milk allergy — CLARIFIED
- `data/structured_db/allergies.json`: consolidated the two duplicate `lactose_intolerance` records into one (union of `avoid_foods`: `["milk_curd", "milk"]`), and added a `description` field to it and to `milk_lactose` and `cow_milk_protein_allergy`, each explaining the enzymatic-vs-immune distinction without overclaiming a universal trace-tolerance threshold (worded as "often tolerated," not "always safe").
- New RAG record `rag_lactose_intolerance_vs_cmpa_001` carrying the same distinction narratively (this is the version that actually reaches a parent-facing answer — see the architecture note in §2).
- **Why:** this exact distinction is one of the most common real-world parent-confusion points, and the KB previously represented both conditions structurally without ever explaining the difference.

### G. Hidden cow's-milk-protein coverage — ADDED (as RAG narrative, not structured `avoid_foods` — see §2 for why)
- New RAG record `rag_hidden_milk_protein_sources_001`: casein, whey (beta-lactoglobulin, alpha-lactalbumin), lactalbumin, ghee.
- **"Butter oil" deliberately excluded** — the verification report could not confirm this specific term against BSACI's primary document (the PDF fetch failed to parse), so per the report's own `INSUFFICIENT VERIFIED EVIDENCE` finding, it was not added.
- **Why not added to `cow_milk_protein_allergy.avoid_foods` (the structured record) as originally proposed:** during implementation, I checked `foods.json` and the planner's actual filtering logic (`get_allergy()` → `avoid_food_names` set matched against food `food_name`/tags) and confirmed **no food item in `foods.json` is tagged or named "ghee," "casein," "whey," or "lactalbumin."** Adding these strings to `avoid_foods` would have been silently non-functional for the planner's filtering (nothing would ever match), which would misrepresent the change as doing more than it does. This is exactly the kind of "hidden/label-reading" educational content the task's own §6 guidance assigns to RAG ("narrative guidance... parent-facing safety guidance"), not structured DB ("machine-readable structured properties" the planner actually filters on). Documented here as a deliberate placement deviation from the original report's literal wording, per §6's own instruction to decide placement based on the actual existing architecture.

### H. Nut-allergy records — CONSOLIDATED and CORRECTED
- `data/structured_db/allergies.json`: the three fragmented `nut_allergy` records (`["nuts_seeds"]`, `["nuts"]`, `["peanut_powder", "sesame_powder"]`) consolidated into one record with `avoid_foods: ["nuts_seeds", "nuts", "peanut_powder"]` (sesame moved out to its own record, see D) and a `description` field stating the EAACI 2024 allergen-specific-avoidance principle.
- New RAG record `rag_nut_allergy_specific_avoidance_001` carrying the same principle narratively.
- **Safety-verified before consolidating:** `planner/diet_planner.py`'s `get_allergy()` (lines ~159-172) already unions `avoid_foods` across every record sharing the same `allergy` key at runtime, and takes the severity of the first match. Consolidating same-keyed duplicate records into one is therefore **behaviorally identical** to what the code already did at query time — confirmed by a direct planner smoke test (§6) producing the same filtered meal plan before and after.
- **What was not attempted:** true per-nut-type allergen specificity (e.g. "avoid almonds but not walnuts") would require tagging individual tree-nut types on individual food items, which `foods.json`'s current schema does not support. Implementing the full clinical nuance would require a schema extension outside "minimal changes" — the consolidation plus the explanatory RAG/description text is the correct-sized change for this pass; a full per-nut-type schema is left for a future, explicitly-scoped phase.

### I. Non-IgE allergy information — ADDED (schema-safe)
- New `data/structured_db/conditions.json` record, `food_allergy_non_ige_mediated`, as a direct sibling to the existing `food_allergy_type_1` (IgE-mediated) record, using the exact same optional-field pattern already present in that file (`description`, `onset`, `features`, `common_allergens`, `tags`) — no schema change.
- New RAG record `rag_ige_vs_non_ige_food_allergy_001` carrying the distinction narratively.
- **Why safe:** `conditions.json`'s schema (per `data/validate_db.py`) only requires `condition_name`/`required_tags`/`avoid_tags`; optional extra fields are already used throughout the file (including on the existing `food_allergy_type_1` record this new one mirrors), so this is a same-shape addition, not a new field.
- **Deliberately not done:** I did not reclassify `cow_milk_protein_allergy`'s existing symptom list (diarrhoea/respiratory allergy/eczema — which reads more like a non-IgE picture) as IgE or non-IgE myself. The verification report explicitly flagged this as needing the doctor's own clinical judgment, not an AI-side reclassification, and that stands.

---

## 2. Architecture note: why several corrections needed a RAG counterpart, not just a structured-DB edit

While implementing D/E/F/G/H/I, I checked `llm/prompt_templates.py` directly to confirm what the generation pipeline actually shows an LLM (and therefore a parent). **Only the retrieved RAG chunks (`rag_context`) and a few raw profile fields (age, weight, goal, condition name, allergy name) ever reach the prompt.** `allergies.json`'s and `conditions.json`'s `description`/`triggers`/`symptoms`/`features` fields are used exclusively by the deterministic planner for internal food filtering — they are never surfaced to the LLM or the parent.

This meant that fixing only the structured-DB `description` fields (as the original verification report's proposed-change table literally described several of these items) would have been **silently inert for actual question-answering** — accurate, consistent data that a parent asking "what's the difference between lactose intolerance and milk allergy" would never actually see in an answer. I caught this during implementation (via a first round of retrieval smoke tests that came back empty/wrong for sesame and the lactose/CMPA distinction), and added a matching narrative RAG record for every one of D, E, F, G, H, and I, per the task's own §6 instruction ("if a fact belongs in both, keep the structured and narrative versions consistent"). A (honey/botulism) and C (ORS) didn't need this — A already had correct RAG content, and C's home was already RAG.

This added 5 RAG records beyond what I'd first drafted (sesame, lactose-vs-CMPA, gluten window, nut-allergy specificity, IgE/non-IgE) — reported transparently here rather than silently, since it changes the record count from what a first read of the verification report's table alone would suggest.

---

## 3. Trusted evidence used

All citations are as documented in detail, with exact source/location/access-date, in `docs/doctor_review/2026-08-31_knowledge_base_ai_verification.md` §2–3. Summary: CDC + AAP/HealthyChildren (honey/botulism, choking), WHO/UNICEF + Global Health Supply Chain Program technical reference (ORS composition), FDA/FASTER Act 2021 + Eufic EU-14-allergen list (sesame), ESPGHAN 2024 position paper + independent PMC peer-reviewed corroboration (gluten window), NIH/NIDDK + BSACI 2014 guideline (lactose intolerance vs. CMPA, hidden milk sources, IgE/non-IgE), EAACI 2024 guideline (nut-allergy specific avoidance). Every new/materially-revised RAG record carries this attribution in its own `metadata.source` field, matching the project's existing citation format (e.g. `rag_iron_absorption_heme_001`'s `"source": "Piskin et al. 2022 (ACS Omega, PMC9219084)"` pattern). No structured-DB field carries a `source` attribution, consistent with the project's existing architecture — that file family has never carried source metadata (only RAG does); citations for the structured-DB text corrections are recorded here and in the verification report instead.

---

## 4. What was deliberately NOT implemented

| Item | Reason |
|---|---|
| 1.5 — change 1–3y calorie RDA from 1110 to 1070 kcal | Explicitly instructed to keep 1110 kcal unless the primary ICMR-NIN source is directly verified. It was not (PDF fetch failed to parse in the verification pass). **Not changed.** |
| 3.3b — propofol/egg-allergy warning | Explicitly instructed not to add it; current evidence (BJA 2017, 2021 review, pediatric cohort study) contradicts the proposed caution. **Not added.** |
| 2.6 — plant-based milk substitute warning, "per NASPGHAN" | Explicitly instructed to withhold until a directly-verifiable source is obtained. The verification report could not confirm this specific attribution. **Not added.** |
| 2.2 — peanut introduction (risk-stratified) | In the verification report as a well-supported item, but **not** in this implementation pass's lettered A–I scope. Left for a future pass; the report already has the corrected (non-flat) wording ready if/when implemented. |
| Rapid-3 — egg hidden-ingredient terms (ovalbumin, ovomucoid, lysozyme, etc.) | Same reasoning as 2.2 — well-supported in the report, but not in this pass's explicit A–I scope. Deferred, not rejected. |
| "Butter oil" as a hidden milk-protein term | `INSUFFICIENT VERIFIED EVIDENCE` per the report (could not confirm against BSACI's primary document). Not added; casein/whey/ghee/lactalbumin were added, "butter oil" was not. |
| Milk-allergy family full consolidation (5 records: `milk` x3, `milk_lactose`, `cow_milk_protein_allergy`, `milk_protein_sensitive_enteropathy`) | The report flagged this as a MEDIUM-priority "additional gap" (AG-3), not one of this pass's lettered A–I items. Only the `lactose_intolerance` duplicate pair (within F's scope) was consolidated; the `milk`-keyed records and the distinct condition-named records were left as-is to keep this pass tightly scoped to what was explicitly asked. |
| `coeliac_sprue.triggers` list (includes "oats", which is naturally gluten-free unless cross-contaminated) | Noticed during E's edit but out of the verified scope for this pass (not covered by the verification report) — flagged here, not touched. |

---

## 5. RAG index rebuild details

`data/rag/rag_data.json` changed (7 new records, 1 updated record: 551 → 558 total), so the index was rebuilt via the project's real indexer (`python main.py --index`, i.e. `rag.indexer.build_index`), **twice** — once after the first batch of structured+RAG edits, and again after the 5 additional RAG counterparts were added (see §2). Final rebuild:

```
Loaded 558 raw document entries.
Generated 558 parent chunks and 781 child chunks.
Loading embedding model: BAAI/bge-small-en-v1.5
Creating FAISS IndexFlatIP index with dimension 384...
Dataset Hash: 1ffd4b30f0900b8a...
Indexing completed successfully!
```

`data/rag/faiss.index`, `data/rag/metadata.pkl`, and `data/rag/dataset_hash.txt` were all regenerated by this run — no manual edits to any of the three.

**Retrieval verified for every new/updated record** via the real `rag.retriever.KidsNutriRetriever` (not a mock or a separate implementation) — see §7. Canonical `source_id` propagation (child-chunk suffix stripped back to the parent record ID) was confirmed correct for every new record.

---

## 6. Validation results

```
python -m unittest discover -v          → 124/124 tests, OK
python -m unittest planner.test_weekly_planner -v → 3/3 tests, OK
python -m compileall -q .               → clean, no errors
python data/validate_db.py              → PASSED, all files match frozen schemas
                                            (foods.json's pre-existing fiber_g
                                            completeness warning is unrelated/unchanged)
```

Additional checks performed:
- `json.load()` on all four modified files (`rag_data.json`, `allergies.json`, `conditions.json`, `goals.json`) — all parse cleanly.
- No duplicate RAG `id` values (558 unique ids, confirmed programmatically).
- No new duplicate `condition_name` values introduced (the pre-existing, unrelated duplicate condition names already in the file — e.g. `anemia`, `pregnancy` — were not touched and are outside this pass's scope).
- `allergies.json` allergy-key list re-verified post-edit: `nut_allergy`(1), `sesame_allergy`(1, new), `lactose_intolerance`(1, consolidated), `milk_lactose`(1), `egg_protein`(3, unchanged), `milk`(3, unchanged), `fish`(2, unchanged), `cow_milk_protein_allergy`(1), `milk_protein_sensitive_enteropathy`(1), `gluten_sensitivity`(1) — 15 total, matching the intended consolidation exactly.

---

## 7. Functional smoke-test results (real project code — `KidsNutriRetriever`, `DietPlanner`, no mock/fake retrieval)

Ran the real `rag.retriever.KidsNutriRetriever().retrieve()` for one representative question per implemented topic, after the final index rebuild:

| Question | Top result `source_id` | Result |
|---|---|---|
| "What foods are choking hazards for a young child?" | `rag_choking_hazard_foods_001` | ✅ correct, rank 1 |
| "Can I give my 8 month old baby honey?" | `rag_honey_infant_warning_001` | ✅ correct, rank 1 |
| "Is sesame a major food allergen for children?" | `rag_sesame_major_allergen_001` | ✅ correct, rank 1 |
| "What is the difference between lactose intolerance and cow's milk allergy?" | `rag_lactose_intolerance_vs_cmpa_001` | ✅ correct, rank 1 |
| "What hidden ingredients should I avoid if my child has a milk allergy?" | `rag_hidden_milk_protein_sources_001` | ✅ correct, rank 1 |
| "When should I introduce gluten to my baby?" | `rag_gluten_introduction_window_001` | ✅ correct, rank 1 |
| "What is the reduced osmolarity ORS sodium potassium chloride citrate content?" | `rag_hypo_osmolar_ors_benefits_001` | ✅ correct, rank 1, full composition confirmed present in retrieved text |
| "If my child is allergic to one nut, do they need to avoid all nuts?" | `rag_nut_allergy_specific_avoidance_001` | ✅ correct, rank 1 |
| "What is the difference between an immediate and a delayed food allergy reaction?" | `rag_ige_vs_non_ige_food_allergy_001` | ✅ correct, rank 1 |

**Planner-side smoke test:** `db.get_allergy()` called directly for all 8 touched/added allergy keys — each returns the expected consolidated/new record with correct `avoid_foods` union and severity (see the exact output captured during implementation: `nut_allergy` → `['nuts_seeds', 'nuts', 'peanut_powder']`; `sesame_allergy` → `['sesame_powder']`; `lactose_intolerance` → `['milk_curd', 'milk']`, etc.). A full `generate_meal_plan()` call for a profile with `allergies: ["nut_allergy", "sesame_allergy"]` completed successfully (1250 kcal plan) with zero nut/sesame food names appearing in the resulting meal plan — confirming the consolidation did not change, let alone weaken, the planner's actual allergen-filtering behavior.

---

## 8. Before/after counts

| File | Before | After | New | Updated | Consolidated (records removed via merge) |
|---|---|---|---|---|---|
| `data/rag/rag_data.json` | 551 | 558 | 7 | 1 | 0 |
| `data/structured_db/allergies.json` | 17 | 15 | 1 (`sesame_allergy`) | 4 descriptions added (`lactose_intolerance`, `milk_lactose`, `cow_milk_protein_allergy`, `gluten_sensitivity`) | 3 → 1 (`nut_allergy`), 2 → 1 (`lactose_intolerance`) — net −2 records |
| `data/structured_db/conditions.json` | 172 | 173 | 1 (`food_allergy_non_ige_mediated`) | 2 (`botulism` tag, `coeliac_sprue` description) | 0 |
| `data/structured_db/goals.json` | 148 | 148 | 0 | 1 (`botulism_prevention_management` text) | 0 |
| `data/structured_db/foods.json` | 99 | 99 | — | **not modified** | — |

**Totals:** 8 new RAG records were drafted but 1 (ORS) was an update to an existing record, so **7 new RAG records + 1 updated RAG record**; **1 new + 2 consolidated-away structured allergy records** (net −2, 17→15); **1 new + 2 updated structured condition records**; **1 updated structured goal record**; **0 changes to `foods.json`**.

Deliberately rejected/deferred proposals from the original verification report: **6** (1.5's kcal change, 3.3b propofol, 2.6 plant-milk-with-NASPGHAN-attribution, 2.2 peanut, Rapid-3 egg-hidden-ingredients, "butter oil" specifically) — see §4 for the reason for each.

**Confirmed no unrelated project files changed** (`git status`/`git diff --stat` show only the 7 knowledge-base files above, plus this log and the earlier-session `docs/phase4d_first_kaggle_results_audit.md`, which is unrelated to this task and was already present from the prior investigation phase). `evaluation/`, `planner/` logic, the notebook, `llm/` client code, `rag/` retrieval code, `main.py`, and `requirements.txt` are all untouched.

---

## 9. Remaining evidence gaps

- The 1–3y ICMR-NIN calorie RDA (1110 vs. 1070 kcal) is still unresolved — needs someone with direct, readable access to the ICMR-NIN 2020 RDA book's actual table.
- "Butter oil" as a hidden milk-protein term remains unconfirmed against a primary source.
- The NASPGHAN attribution for the plant-based-milk-substitute warning remains unconfirmed.
- `cow_milk_protein_allergy`'s IgE-vs-non-IgE classification was deliberately left unassigned pending the doctor's own clinical judgment (its existing symptom list reads more like non-IgE, but this project should not make that call unilaterally).
- 2.2 (peanut) and Rapid-3 (egg hidden ingredients) remain valid, evidence-sufficient, unimplemented proposals — ready for a future pass if the team chooses to extend scope.

## 10. Items Mam may later review or change

Every item implemented in this pass came from the doctor-review document originally sent to her (A, C, D, E, F, G, H) or was found during the independent audit (B, I) — none are outside the spirit of what was already sent for her review. When she responds:
- She may confirm, modify, or reject any of A–I as implemented here — this document and the underlying data are both fully revisable.
- Her answer to the original 1.3 "general rule vs. medical caveats" question (follow-up formula) was not part of this pass's scope and remains open.
- Her answer on 3.3 (yellow fever/egg-allergy/vaccine — nutrition-platform scope question) remains open; nothing on that topic was added in this pass.
- Any clinical correction she provides — including to items already implemented here (e.g. if she disagrees with the ESPGHAN gluten window, or wants different choking-hazard wording) — should be treated as authoritative over this AI-verified pass, per the original task's standing instruction.
