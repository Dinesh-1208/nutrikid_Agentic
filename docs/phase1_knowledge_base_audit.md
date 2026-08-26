# Phase 1 — Knowledge Base Audit

**Status: read-only inventory. No `rag_data.json`, `foods.json`, `conditions.json`, `allergies.json`, `goals.json`, FAISS index, metadata, code, evaluation dataset, or notebook modified.**

All figures below come from direct inspection of the current repository this session (Python analysis over the actual JSON files, and direct reads of `rag/indexer.py`, `rag/chunker.py`, `planner/diet_planner.py`) — not from prior notes.

**Path correction**: the task brief referenced `rag/rag_data.json` and `rag/structured_db/`. Verified via `Glob` that the real locations are **`data/rag/rag_data.json`**, **`data/rag/faiss.index`**, **`data/rag/metadata.pkl`**, and **`data/structured_db/{foods,conditions,allergies,goals}.json`**.

---

## 1. Executive Summary

The knowledge base has two genuinely distinct, complementary halves: a 551-document free-text RAG corpus (chunked and embedded for semantic retrieval) and a 436-record structured DB (99 foods, 172 conditions, 17 allergies, 148 goals) driving the deterministic planner's rule-based food selection. Both halves show the same underlying pattern: **real, clinically-substantive content coexists with severe sparsity and internal inconsistency**. The single most important finding is a confirmed, code-verified vocabulary mismatch — **110 of 129 distinct tags referenced by conditions/goals' `required_tags`/`avoid_tags` never appear on any food record**, meaning the large majority of condition- and goal-driven food filtering rules can never actually fire. The second most important finding is in `allergies.json`, the most safety-critical file in the project: the same allergy (e.g. `nut_allergy`, `milk`, `egg_protein`) appears under 2-3 separate records with **different, non-identical `avoid_foods` lists**, and 3 of 17 records have a blank `severity` field. Sourcing/provenance is present for only ~10% of RAG records (two real, legitimate authorities: ICMR-NIN 2020 and FSSAI). These are concrete, fixable gaps, not reasons to distrust the whole knowledge base — the content that *is* present is generally substantive and clinically literate, not generic filler.

## 2. Current RAG Data Inventory (`data/rag/rag_data.json`)

**Structure**: a flat JSON list of 551 objects, each `{"id": str, "text": str, "metadata": {...}}`. Every record has all three top-level keys populated (0 missing `text`, 0 missing `metadata`, 0 duplicate `id`). Text length ranges 48-303 characters (avg 129).

**How it becomes retrievable** (traced directly, `rag/indexer.py` + `rag/chunker.py`): each raw document's `text` is split into ~600-char "parent" chunks, each parent further split into ~150-char "child" chunks (30-char overlap). Only **child chunks are embedded** (`BAAI/bge-small-en-v1.5`) and indexed in a FAISS `IndexFlatIP`; `metadata.pkl` stores child chunks, parent chunks, the parent map, and the original raw documents together. `metadata` on a raw document is copied unchanged onto every chunk derived from it. So what's "retrievable" is exactly, and only, whatever sentence-level content exists inside each record's `text` field — nothing more (no cross-references, no inference beyond what's written).

**Metadata field coverage** (out of 551):
| Field | Present | Missing |
|---|---|---|
| `type` | 551 (100%) | 0 |
| `tags` | 395 (72%) | 156 (28%) |
| `condition` | 94 (17%) | 457 (83%) |
| `source` | 53 (10%) | 498 (90%) |
| `food_name` | 13 (2%) | 538 (98%) |
| `goal` | 13 (2%) | 538 (98%) |

**`type` taxonomy**: **147 distinct values**, extremely long-tailed. Eight types account for the bulk of records (`condition`:133, `general`:57, `food`:56, `nutritional_biochemistry`:26, `general_knowledge`:21, `goal`:15, `protocol`:14, `growth_metric`:12); the remaining ~139 types have 1-9 records each (e.g. `piaget_cognitive_stages`-style one-offs like `epigenetics`:1, `tb_resistance`:1, `athletic_pathology`:1). This means type-based filtering is only meaningful for the top ~8 categories.

**Sourcing**: only 53/551 records cite a `source` at all, and only two distinct sources appear across all of them: **ICMR-NIN 2020** (Indian Council of Medical Research – National Institute of Nutrition, 42 records) and **FSSAI** (Food Safety and Standards Authority of India, 11 records). Both are real, legitimate government nutrition/food-safety authorities — the sourced content is well-provenanced where it exists, but **90% of the corpus has no traceable source at all**, which matters directly for the doctor-review effort (most existing content can't currently be pointed at an authority for verification).

**Tag sparsity by type**: of records with no `tags` at all, 104 are `condition`-type (104/133 = 78% of all condition records untagged) and 33 are `food`-type (33/56 = 59%).

**Field/type inconsistencies found**: 39 of 133 `condition`-type records have no `condition` metadata field naming which condition they're about (e.g. `RAG_MINERAL_2`, `RAG_HIV_1`, `RAG_COVID_1`, `RAG_INF_4` through `RAG_INF_13`) — relying entirely on free text. Similarly 43 of 56 `food`-type records have no `food_name` field (e.g. `RAG_INTRO_6`, `RAG_CARB_1`, `RAG_PROTEIN_1`, `RAG_FAT_1`). One example of ID/content mismatch: `RAG_MINERAL_2`'s text ("Iron deficiency can lead to anemia...") is about a *condition*, and its metadata does say `type: condition` — but the ID prefix "MINERAL" suggests it was originally filed as mineral-nutrition content, illustrating drift between ID naming and eventual categorization.

**Duplicates**: essentially none — only 1 exact duplicate text body across all 551 records ("Breast milk contains antibodies that protect infants from infections.").

**ID naming inconsistency**: mixed case prefixes (`rag_` lowercase: 238 records vs `RAG_` uppercase: 192 records), plus separate `icmr` (42), `condition` (30), `goal` (13), `food` (11), `fssai` (11) prefix families, plus a scatter of unique `RAG2001`-`RAG3008`-style numeric IDs. Cosmetic, but worth normalizing if IDs are ever used for cross-referencing.

## 3. Current Structured DB Inventory (`data/structured_db/`)

| File | Records | Core matching fields (in 100% of records) | Notes |
|---|---|---|---|
| `foods.json` | **99** | `food_id`, `food_name`, `category`, `tags` | 41 distinct fields total, most used by a handful of records only |
| `conditions.json` | **172** | `condition_name`, `required_tags`, `avoid_tags`, `meal_pattern` | 129 distinct fields total, 125 of them used by ≤2 records |
| `allergies.json` | **17** | `allergy`, `avoid_foods`, `severity` | Smallest file, most safety-critical, worst internal consistency (see §6) |
| `goals.json` | **148** | `goal_name`, `required_tags`, `avoid_tags`, `meal_frequency` | 175 distinct fields total, same long-tail pattern as conditions |

### `foods.json` (99 records) — field sparsity on core nutrition fields

| Field | Empty | Populated |
|---|---|---|
| `energy_kcal_per_100g` | 38 (38%) | 61 |
| `protein_g` | 44 (44%) | 55 |
| `fat_g` | 50 (51%) | 49 |
| `carbs_g` | 50 (51%) | 49 |
| `iron_mg` | 57 (58%) | 42 |
| `allergy_tags` | 78 (79%) | 21 |
| `category` | 5 (5%) | 94 |

Confirmed directly (not just inferred): **37 of 99 records have all of `energy_kcal_per_100g`/`protein_g`/`carbs_g` blank, with no alternate nutrient field either** (checked `F200`, `F600`, `F900`, `F1253` directly — none carry `nutrients_per_100g`/`nutrients_per_100ml` or any other nutrient data; they have only qualitative fields like `digestibility_boiled`, `glycemic_index`, `tags`, `meal_types`). This is a real gap, not a naming inconsistency — over a third of the food database has zero quantitative nutrition data.

**Schema sprawl**: 41 distinct fields exist across the file, but most (`probiotic_strains`, `nutrients_per_ml`, `clinical_note`, `ingredients`, `nutrient_density`, `usage` — each populated in exactly 1/99 records) look like they were added for one specific specialized record (e.g. a parenteral-nutrition fluid or infant formula) rather than representing a general schema gap. This suggests the file was assembled by appending different food subtypes (regular foods, infant formulas, therapeutic/medical fluids) each bringing their own ad-hoc fields, rather than one consistent schema.

**Duplicate/near-duplicate `food_name` values** (9 pairs: `vegetables`, `fruits`, `cereals`, `milk`, `green_leafy_vegetables`, `nuts`, `amylase_rich_foods`, `egg_pudding`, `eggnog`). Checked two pairs directly:
- **`milk` (F302 vs F402) — a genuine, unexplained conflicting duplicate.** Same category, same portion (300ml/day), same allergy_tags, nearly identical protein/carbs — but `energy_kcal_per_100g` is 42 vs 72 (71% different) and `fat_g` is 1 vs 4.2 (320% different), with nothing in either record (no "whole milk" vs "skim milk" style qualifier) explaining the difference. A rule that matches "milk" could pull either value inconsistently.
- **`vegetables` (F200 vs F403)** — not a true duplicate but a completeness split: F200 has zero nutrition numbers (see above), F403 has real per-100g values (35 kcal / 1.8g protein / 0.4g fat / 5g carbs). Same underlying concept represented at two different levels of completeness under the same name.

### `conditions.json` (172 records)

**129/172 (75%) have empty `required_tags`; 131/172 (76%) have empty `avoid_tags`.** Since these two fields are the *only* thing the planner actually uses from a condition record to influence food selection (see §4), roughly three-quarters of `conditions.json` cannot influence deterministic food filtering/scoring at all today — it functions as reference text, not planner-driving data, despite living inside the "structured DB."

**Massive schema fragmentation beyond the 4 core fields**: 125 of 129 total distinct fields appear in only 1-2 records each — things like `oedema_grading`, `who_hb_thresholds`, `hypokalaemia_signs`, `ponderal_index`, `essential_amino_acids_additional`, `probiotic_antagonist`. This reads like clinical reference material (staging systems, diagnostic thresholds, biochemical markers) that happens to be filed under a `condition_name` record rather than free text — content that looks more suited to the RAG corpus than to a structured matching table (see §4).

**Duplicate `condition_name` values** (10): `anemia`×3, `pregnancy`×3, `micronutrient_deficiency`×2, `lactation`×2, `breastfeeding`×2, `infant_6_12_months`×2, `child_above_1_year`×2, `lactose_intolerance`×2, `infection_or_diarrhea`×2, `galactosaemia`×2. **Verified directly against `planner/diet_planner.py::get_condition`** (lines 120-139): duplicates are *not* silently overwritten or arbitrarily picked — the planner explicitly merges (unions) `required_tags`/`avoid_tags` across all records sharing a `condition_name`. So this isn't a correctness bug, but it is redundant: these records functionally behave as one merged condition already, and consolidating them would be a cleanup, not a fix.

### `goals.json` (148 records)

Same structural pattern as `conditions.json`: 4 core fields in 100% of records, 175 total distinct fields with 165+ used in ≤2 records. Unlike conditions, several of the one-off fields in `goals.json` are **not dietary-goal content at all** — e.g. `piaget_cognitive_stages`, `iq_formula`, `briscoe_sanitation_scale`, `tetanus_toxoid`/`rubella`/`hepatitis_b` (vaccination schedule fields), `toilet_training`, `gross_motor`/`fine_motor_adaptive`/`language` (developmental milestone fields). These look like general pediatric/public-health reference facts that were filed under `goals.json` rather than content that fits the "dietary goal → required/avoid tags" concept the planner expects.

4 duplicate `goal_name` values: `healthy_pregnancy`×2, `infant_weight_gain`×2, `safe_feeding`×2, `digestive_support`×2 (same merge-not-overwrite behavior presumed, consistent with `get_condition`'s pattern, though `get_goal`'s exact code wasn't re-verified line-by-line this session).

### `allergies.json` (17 records) — smallest file, most safety-critical, worst consistency

This is the most important quality finding in the structured DB, given allergen avoidance is a hard safety constraint for a pediatric application:

- **`nut_allergy` appears 3 times** with three different `avoid_foods` lists: `["nuts_seeds"]`, `["nuts"]`, `["peanut_powder", "sesame_powder"]`.
- **`milk` appears 3 times** (plus a 4th, differently-named `milk_lactose`, plus a 5th and 6th, `cow_milk_protein_allergy` and `milk_protein_sensitive_enteropathy`) — six records covering overlapping dairy-sensitivity concepts, with `avoid_foods` lists that don't agree: `["eggnog","milk_added_recipes","milk_added_foods","curd"]`, `["eggnog","milk_added_foods"]`, `["curd"]`, `["milk_curd"]`, `["milk"]`, `["cows_milk","unmodified_bovine_milk"]`, `["bovine_milk","unmodified_cow_milk"]`.
- **`egg_protein` appears 3 times** with overlapping-but-not-identical `avoid_foods` lists.
- **`lactose_intolerance` appears twice** with different `avoid_foods` (`["milk_curd"]` vs `["milk"]`).
- **`fish` appears twice** with identical `avoid_foods` in both instances (this pair is a true, harmless exact duplicate).
- **3 of 17 records have `severity: ""`** (blank) — `cow_milk_protein_allergy`, `milk_protein_sensitive_enteropathy`, `gluten_sensitivity` — a real gap on a field that plausibly drives how strictly the planner should treat an exclusion.

**This file is small enough (17 records) that consolidating it correctly is a tractable, high-value fix** — but it should not be done without clinical review given the safety stakes, per the doctor-review process below.

## 4. RAG vs Structured DB Roles

**RAG (`data/rag/rag_data.json`)**: free-text, narrative/explanatory knowledge, retrieved by semantic similarity and used by the LLM to *write* the final answer (context for generation, and for the Faithfulness/Context Recall/Unsupported Claim Rate evaluation metrics). Suitable content: anything that reads as prose explanation — "why," background, clinical rationale, reference facts a user might ask about directly. Confirmed unsuitable for anything the deterministic planner needs to *compute* or *decide* on, since nothing here is machine-actionable beyond string matching.

**Structured DB (`data/structured_db/`)**: deterministic, planner-consumed matching rules. `foods.json` is the candidate pool the planner selects from (tag/category/age/meal-type matching, nutrition-number scoring where present). `conditions.json`/`goals.json`/`allergies.json` are rule sets applied against a user's profile to compute `required_tags`/`avoid_tags`/exclusions before food selection (traced directly in `planner/diet_planner.py::generate_meal_plan`, lines 223-291). Anything that isn't literally a tag/number the planner logic reads has no functional effect here regardless of how substantive it looks.

**Confirmed overlap between the two sources**: both cover the same conceptual domains (conditions, foods, goals) but in different forms — RAG has narrative sentences about conditions/foods/goals, the structured DB has matching rules for the same concepts. This is a sensible split in principle (one explains, one decides) but the *specific* overlap found in `conditions.json`/`goals.json`'s long-tail fields (biochemical thresholds, staging systems, vaccination schedules, developmental milestones) looks like content that was put in the wrong place — it reads like RAG-appropriate reference material sitting inertly inside structured-DB records where the planner can't use it and a semantic search can't find it either (since it's not chunked/embedded).

**A confirmed, quantified, functional gap connecting both sources** — the most significant finding of this audit: cross-checked the actual vocabulary. `foods.json` uses 133 distinct `tags` values. `conditions.json` + `goals.json` together reference 129 distinct values across `required_tags`/`avoid_tags`. **Only 19 of those 129 tags actually appear on any food record.** The other **110 (85%) are dead — they can never match or exclude any food**, confirmed against the planner's actual matching code (`if any(tag in avoid_tags for tag in f_tags): continue` and `score += sum(5 for tag in f_tags if tag in required_tags)`, both operating on `food["tags"]`). This means the large majority of condition- and goal-driven food filtering rules are currently inert in practice, regardless of how complete or clinically sound their intent is.

**Recommendation framework for future additions** (A=RAG / B=Structured DB / C=Both / D=Neither):
- New narrative facts, explanations, "why" content → **A**.
- New food nutrition numbers, new tag values that need to actually drive planner matching → **B**, and *must* use tag vocabulary that already exists in (or is added consistently to) `foods.json`.
- A new food item with both a nutrition profile (planner-relevant) and a longer explanatory description (retrieval-relevant) → **C**.
- Content with no dietary/nutrition relevance at all (e.g. general pediatric milestones unconnected to feeding) → **D**, or reconsider whether it belongs in this project at all.

## 5. Quality / Sparsity Issues — Summary Table

| Issue | Location | Scale | Example record(s) |
|---|---|---|---|
| Missing `source`/provenance | `rag_data.json` | 498/551 (90%) | Any record without `metadata.source` |
| Extreme `type` taxonomy fragmentation | `rag_data.json` | 147 distinct types, ~139 with ≤9 records | `epigenetics`, `tb_resistance` (1 each) |
| Missing `condition`/`food_name` metadata on typed records | `rag_data.json` | 39/133 condition-type, 43/56 food-type | `RAG_MINERAL_2`, `RAG_CARB_1` |
| Core nutrition fields blank | `foods.json` | 37/99 records fully blank (energy/protein/carbs) | `F200`, `F600`, `F900`, `F1253` |
| Conflicting duplicate food record | `foods.json` | `milk`: F302 vs F402, 71-320% value differences | F302, F402 |
| `required_tags`/`avoid_tags` empty | `conditions.json` | 129/172 (75%) / 131/172 (76%) | Majority of the file |
| Non-dietary content mixed into goals | `goals.json` | dozens of one-off fields | `piaget_cognitive_stages`, `tetanus_toxoid` |
| Inconsistent allergen avoid-lists for the same allergy | `allergies.json` | `nut_allergy`×3, `milk`-family×6, `egg_protein`×3, `lactose_intolerance`×2, each with differing `avoid_foods` | See §3 |
| Blank `severity` on a safety field | `allergies.json` | 3/17 | `cow_milk_protein_allergy`, `milk_protein_sensitive_enteropathy`, `gluten_sensitivity` |
| Tag vocabulary mismatch (planner rules that can never fire) | `foods.json` ↔ `conditions.json`/`goals.json` | 110/129 (85%) of referenced tags | See §4 |

No item above has been corrected — this is inventory only.

## 6. Missing Knowledge (by domain, per the requested organization)

- **Foods/nutrition**: core macro/micronutrient data missing for over a third of food records (§3). No records at all for many common food items a pediatric nutrition system would plausibly need (e.g. no clear entries for common regional staples beyond the ~99 present; coverage is real but narrow).
- **Nutrients**: some standalone nutrient-science content exists in RAG (`nutritional_biochemistry`: 26 records) but isn't cross-linked to specific foods' nutrient fields.
- **Meals**: `meal_types`/`meal_frequency` exist structurally but only for foods that have them populated (55/99 have `meal_types`).
- **Conditions**: broad topical coverage (133 RAG records + 172 structured records) but three-quarters of the structured records can't influence planning (§3), and RAG condition records are 78% untagged.
- **Symptoms**: present only incidentally inside condition free-text and a few `signs`/`symptoms`/`clinical_features` fields (11, 9, 2 records respectively in `conditions.json`) — not a distinct, queryable domain.
- **Allergies**: only 17 structured records, covering nut/milk/egg/fish/gluten-family allergies — no coverage found for other common pediatric allergies (e.g. soy, shellfish, sesame as a standalone category) in a quick scan of the 17 entries. Internal consistency is the immediate priority over breadth here (§3).
- **Age-related guidance**: `age_min` exists on 55/99 foods; RAG has some age-specific content (`RAG_INF_*` prefix family) but it's not systematically tagged by age band.
- **Dietary goals**: 148 structured records, but heavily diluted by non-dietary content (§3); genuine goal-matching content is a smaller subset than the raw count suggests.
- **Food substitutions**: no dedicated substitution-mapping structure found in either source (e.g. nothing that says "if allergic to X, substitute Y") — `allergies.json`'s single `preferred_alternative` field (only on the `gluten_sensitivity` record, suggesting `rice`) is the only instance found.
- **Meal-planning information**: covered by the structured DB's core matching fields; the RAG side has some `protocol`-type content (14 records) that may support this.
- **Safety-related information**: RAG has some direct content (`emergency_protocol`:2, `toxicology`:3, `infant_safety`:1) but this is thin; the structured DB's allergy data is the primary safety mechanism and is the least consistent file in the project (§3).
- **Other domains present but not requested above**: growth/anthropometry reference data (`growth_metric`:12, `anthropometry`:4), general public-health/programme content in `goals.json` (vaccination, sanitation) that's arguably out of scope for a dietary system.

## 7. Expansion Opportunities

**HIGH PRIORITY**
1. **Fill core nutrition fields for the 37 fully-blank food records.** Fills a direct, quantified gap; belongs in `foods.json` (Structured DB); update existing records, not new ones. High confidence this materially improves planner scoring quality.
2. **Resolve the `allergies.json` inconsistencies** (consolidate duplicate allergy names into single, clinically-verified `avoid_foods` lists; fill the 3 blank `severity` values). Safety-critical; Structured DB; update existing records. Small file (17 records) — tractable, but must go through doctor review given the stakes.
3. **Close the tag-vocabulary gap** between `foods.json` and `conditions.json`/`goals.json` (either add the missing 110 tags to relevant foods, or determine which of those tags were never intended to be food-matchable and should be pruned from `required_tags`/`avoid_tags`). Structured DB; a mix of updates to existing food records and a scoping decision on which condition/goal rules are meant to be planner-functional. This is the single highest-leverage fix for making the deterministic planner behave as its own data implies it should.

**MEDIUM PRIORITY**
4. **Add `source` provenance to more RAG records**, prioritizing the ~90% currently unsourced, especially any that get used as condition/food explanatory content. RAG; update existing records; fills the traceability gap directly relevant to doctor review.
5. **Add `condition`/`food_name` metadata to the 39 + 43 typed-but-unlabeled RAG records** (§2). RAG; update existing records; improves any future metadata-filtered retrieval.
6. **Consolidate duplicate `condition_name`/`goal_name`/`food_name` records** where they're confirmed true duplicates (not intentional variants) — reduces confusion even though the planner's merge logic already prevents a correctness bug for conditions/goals.

**LOW PRIORITY**
7. **Normalize RAG ID casing/prefix conventions** (`rag_`/`RAG_` mix). Cosmetic only.
8. **Re-scope `goals.json`'s non-dietary content** (vaccination schedules, developmental milestones) — decide whether it belongs in this project at all, and if so, move to RAG rather than leaving it inert inside `goals.json`.
9. **Reduce `type` taxonomy fragmentation in RAG** (147 → a smaller, more consistent set) — improves any future type-based filtering, but current retrieval already works via embeddings regardless of type granularity, so this is cosmetic/organizational rather than functional.

## 8. Source/Verification Plan (for HIGH PRIORITY items only)

- **Food nutrition data (item 1)**: national/international food composition databases — e.g. **ICMR-NIN's Indian Food Composition Tables** (the same authority already cited 42 times in the existing RAG corpus, so consistent with current sourcing precedent), or **USDA FoodData Central** where an Indian-specific value isn't available. Cross-check against **WHO/FAO nutrient reference tables** for macronutrient consistency.
- **Allergy data (item 2)**: pediatric allergy avoidance lists should be verified against **AAP (American Academy of Pediatrics)** or equivalent Indian pediatric body guidance, and **WHO/FSSAI allergen-labeling standards** (FSSAI is already an existing project source) — but given this is a hard safety constraint, the doctor's direct clinical review should be the final authority regardless of which reference document is cited, not a substitute for it.
- **Tag vocabulary reconciliation (item 3)**: this is an internal-consistency fix, not a new-facts fix — it doesn't need an external authoritative source, only a project-level decision (with clinical sign-off on any resulting change to what foods are recommended/excluded for a given condition or goal).

No facts have been collected or inserted — this section defines *where to look*, not *what the answer is*.

## 9. Doctor-Review Tracking Schema

See the separate reusable template: `docs/doctor_review/knowledge_base_change_log_template.md`. Every future addition or modification (including consolidations from item 6/9 above) must get a row there before being merged, per the strict rule that nothing in this phase creates actual changes.

## 10. Proposed Expansion Options (Phase 1 decision menu)

**Option 1 — Fill missing food nutrition fields**
Expected benefit: enables real nutrient-based scoring for the 37 currently-blank food records (currently scored only on qualitative tags). Files affected: `data/structured_db/foods.json`. Estimated scope: up to 37 record updates (energy/protein/fat/carbs/iron), possibly more if partially-blank records are included. Verification burden: moderate — each value needs a food-composition-table lookup, ICMR-NIN preferred. **Recommendation: UPDATE EXISTING.**

**Option 2 — Expand/clean condition-related knowledge**
Expected benefit: makes the 75% of `conditions.json` currently without `required_tags`/`avoid_tags` actually planner-functional, or clearly documents why they're reference-only. Files affected: `data/structured_db/conditions.json`, possibly `data/rag/rag_data.json` for content that should move to RAG instead. Estimated scope: up to 129 records need a tagging decision; scoping/triage needed before any bulk edit. Verification burden: high — requires clinical judgment on what tags are appropriate per condition. **Recommendation: UPDATE EXISTING** (after triage), **do not** treat as a simple fill-in-the-blanks task given the volume.

**Option 3 — Resolve allergy knowledge inconsistencies**
Expected benefit: removes contradictory `avoid_foods` lists for the same allergy — directly safety-relevant. Files affected: `data/structured_db/allergies.json`. Estimated scope: small (17 records, ~6 need consolidation/review, 3 need `severity` filled). Verification burden: high per-record stakes despite low record count — mandatory doctor sign-off given this drives hard exclusions. **Recommendation: UPDATE EXISTING**, highest priority-to-effort ratio in the whole audit.

**Option 4 — Re-scope goals.json**
Expected benefit: removes planner-irrelevant content, clarifies what's actually a "dietary goal." Files affected: `data/structured_db/goals.json`, possibly migrate content to `data/rag/rag_data.json`. Estimated scope: dozens of non-dietary fields across many records — a scoping/triage task, not a simple edit. Verification burden: low for the re-scoping decision itself, but any content that gets moved to RAG as new facts would need normal sourcing. **Recommendation: UPDATE EXISTING** (re-scope), low urgency relative to Options 1-3.

**Option 5 — Improve missing fields in existing RAG records**
Expected benefit: better metadata-filtering and traceability (source, condition, food_name fields). Files affected: `data/rag/rag_data.json`. Estimated scope: up to 498 records for `source`, 39+43 for condition/food_name. Verification burden: high for `source` specifically (needs a real citation per record, not just a label) — likely the largest-volume, lowest-per-item-urgency item in this list. **Recommendation: UPDATE EXISTING**, but sequence after Options 1-3.

**Option 6 — Add new RAG knowledge documents/chunks**
Expected benefit: genuinely new coverage (e.g. substitution guidance, currently almost entirely absent per §6). Files affected: `data/rag/rag_data.json` (and re-run of `rag/indexer.py`, out of scope for this phase). Estimated scope: undetermined until specific new-content decisions are made — this phase only identifies the *gap* (substitutions), not the content. Verification burden: highest of all options, since this is wholly new factual content requiring full sourcing per the plan in §8. **Recommendation: ADD NEW**, but only after Options 1-3 are resolved and only with a doctor-reviewed source per new fact, per §9's tracking schema.

**Tag vocabulary reconciliation** (the §4/§7 item 3 finding) is not listed as its own numbered option above because it cuts across Options 1, 2, and 4 — it should be resolved as part of whichever of those options is approved first, not as an independent task.

## 11. Risks / Duplicates / Overlap (consolidated)

- **Duplicates found and evidenced**: `foods.json` (9 name pairs, at least one — `milk` F302/F402 — a genuine conflicting duplicate, not harmless); `conditions.json` (10 condition_name duplicates, confirmed handled by union-merge in the planner, so redundant rather than broken); `goals.json` (4 goal_name duplicates, same presumed pattern); `allergies.json` (multiple duplicate allergy names with *inconsistent* `avoid_foods` — the one place duplication is actively risky, not just redundant); `rag_data.json` (1 exact text duplicate, negligible).
- **RAG/Structured-DB overlap**: conceptual overlap by design (both cover conditions/foods/goals) is fine; the concerning overlap is structured-DB records containing narrative/reference content that would be more useful and more discoverable as RAG chunks (§4).
- **Cross-file risk**: the 85% dead tag-vocabulary rate (§4) is the biggest systemic risk — it means the *appearance* of rich condition/goal-specific dietary rules in `conditions.json`/`goals.json` substantially overstates what the planner can actually act on today.
- **Safety risk concentration**: `allergies.json` is simultaneously the smallest file and the one where inconsistency has the most direct real-world consequence (a wrong or incomplete `avoid_foods` list is a genuine safety issue, not a UX inconvenience).

## 12. Final Recommendation

Proceed to Phase 1 expansion, but sequence it by risk/leverage rather than by file size: **allergy consolidation (Option 3) and food nutrition completion (Option 1) first** — small, tractable, high real-world stakes — **then the tag-vocabulary reconciliation** that cuts across conditions/goals/foods, **then** the broader conditions/goals re-scoping and RAG sourcing/metadata cleanup, **then** genuinely new content (substitutions and any other confirmed gap) last, once the existing data's internal consistency is fixed. Every item, without exception, goes through the doctor-review log in `docs/doctor_review/knowledge_base_change_log_template.md` before being merged — nothing in this phase should bypass that, including "obvious" consolidations like the exact-duplicate `fish` allergy entry, since even a seemingly-safe merge touches a safety-relevant file.

Nothing has been added, changed, or removed in this task. Waiting for your approval before any expansion work begins.
