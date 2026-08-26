# KidsNutriBite — Phase 2B Evaluation Question Set (Revised)

**Status: Revision pass on the existing 49-question candidate set. Questions and basic metadata only. No `relevant_chunk_ids`, `gold_facts`, `reference_answer`, or `safety_ground_truth` have been created. `evaluation/dataset.py` was not modified. No knowledge-base, metric, or notebook file was modified.**

Machine-readable dataset: [`phase2b_evaluation_questions.json`](phase2b_evaluation_questions.json) (49 cases, `{"cases": [...]}`).

This revision keeps the same 49 case IDs (`EVAL_001`–`EVAL_049`) and the same category/count structure as the first draft, but rewrites question phrasing into realistic parent/caregiver voice, replaces two weak or non-compliant questions, and re-verifies every question and profile value directly against the current KB.

---

## 1. What changed and why

The first draft (produced under the Phase 2B instructions) was technically KB-grounded but skewed toward academic/clinical phrasing ("What is the difference between...", "Why does X occur...") rather than how a parent using KidsNutriBite would actually ask. This revision was requested to:

1. Rewrite question phrasing into natural parent/caregiver voice ("Can my...", "What should I...", "Is it okay for my...") wherever the underlying KB fact supports it.
2. Remove the one clinical **dosing** question (Vitamin A prophylaxis schedule) and replace it with a non-dosing, KB-supported alternative.
3. Reconsider the one clearly low-value/academic question (Type I vs. Type II nutrient labeling) and replace it with a more useful parent-relevant question drawing on different, still-current KB content.
4. Re-verify every question against the current KB directly (again — not from memory of the first pass) and every profile value against the live `conditions.json`/`goals.json`/`allergies.json`.

No new facts, sources, or categories were introduced. No question relies on the still-pending, unapproved doctor-review KB expansion batch — every fact used was independently re-confirmed to already exist in `data/rag/rag_data.json` or the structured DB files, exactly as in the first draft.

---

## 2. Category and coverage summary (unchanged from the first draft)

| Category | Count | Target |
|---|---|---|
| General Nutrition & Nutrients | 9 | 8–10 |
| Age-Specific Feeding | 9 | 8–10 |
| Allergies & Intolerances | 9 | 8–10 |
| Pediatric Conditions | 9 | 8–10 |
| Food Safety & Suitability | 7 | 6–8 |
| Growth, Development & Reference Data | 6 | 4–6 |
| **Total** | **49** | ~49–50 |

**Knowledge-only cases: 28. Profile-aware cases: 21** (unchanged counts from the first draft; two profile-aware cases had their `age` value adjusted for cleaner parent-style phrasing — see §3).

---

## 3. Revision change log

**46 questions rewritten** (phrasing changed into parent/caregiver voice; underlying KB fact and category unchanged), **2 questions replaced** (underlying fact changed because the original violated a hard rule), **1 question left unchanged** (already realistic).

### Replaced (2)

| ID | Old question | New question | Why replaced |
|---|---|---|---|
| EVAL_008 | "What is the difference between 'Type I' and 'Type II' nutrients in food labeling?" | "Which nutrients are especially important for my child's brain development?" | The old question was technically KB-supported but academic/low-value with no realistic parent use case (per instruction §7). Replaced with a genuinely KB-supported, parent-relevant question drawing on `rag_super_nutrients_001` ("Super Nutrients for brain health: Vitamin A, Iron, Folic Acid, and Omega-3 fatty acids") — a different current-KB record, no outside knowledge added. |
| EVAL_048 | "What is the national Vitamin A prophylaxis dosing schedule for young children in India?" | "How much of my child's brain has developed by age 2, compared to an adult?" | The old question directly asked for a **prophylaxis dosing schedule**, explicitly excluded by the no-dosing rule (§6). Replaced with a non-dosing growth-reference question drawing on `rag_pem_brain_001` ("Brain weight benchmarks: Birth 25% adult size, 6 months 50%, 2 years 75%, 5 years 90%") — a different current-KB record, no outside knowledge added. |

### Unchanged (1)

| ID | Question | Why kept as-is |
|---|---|---|
| EVAL_020 | "Can my child with a nut allergy eat food made with peanut powder?" | Already realistic "Can my child..." parent phrasing; no improvement needed. |

### Rewritten (46)

All other cases (EVAL_001–EVAL_007, EVAL_009–EVAL_019, EVAL_021–EVAL_047, EVAL_049) kept their category, subcategory, age group, knowledge area, source scope, and underlying KB fact(s), and were rewritten only in phrasing — moving from academic/clinical framing ("What foods should be avoided for a child with...") to first-person parent/caregiver framing ("My child has... — what should I avoid?", "Can my...", "Should I...", "Is it okay for my..."). Two of these also had a minor profile `age` adjustment for cleaner phrasing, both staying inside the same age band the question already tested:

- **EVAL_011**: profile `age` adjusted from `0.7` to `0.6` so the question could say "my 6-month-old" cleanly, still inside the 6–8 month band (`infant_6_8_months`).
- **EVAL_016**: profile `age` adjusted from `2.5` to `2` so the question could say "my 2-year-old" cleanly, still inside the 2–3 year band tested by `condition_toddler_001`.

The full per-question rationale for every rewrite is in the internal source-mapping table below (§5), which states the exact KB record(s) behind each question and, where applicable, the phrasing change made.

---

## 4. Compliance re-verification

Every one of the 49 revised questions was re-checked against these rules:

1. **Current KB support** — every question maps to a record that was re-confirmed present in `data/rag/rag_data.json` or a structured DB file this session (see §5).
2. **Pediatric** — every question concerns a child aged 0–10 years; no adult-only question (pregnancy/lactation/adult-BMR content from the RAG corpus, which is extensive, was not used, matching the first draft).
3. **No adult-only assumptions** — confirmed.
4. **No diet-planning** — confirmed; no question asks the system to construct, plan, or optimize a meal, day, or week of meals.
5. **No medication/dosing** — confirmed; EVAL_048 (Vitamin A dosing) was the only dosing question in the prior draft and has been replaced. No other dosing/prescription/supplement-dosage question exists in the set (re-checked: no question references `anaemia_prophylaxis`'s Folifer Paed dosage, `ort_management_plans`' ORS composition, or `zinc_supplementation` diarrhoea dosing — none of these were used in either draft).
6. **No invented profile values** — re-verified programmatically this session: every `condition`, `goal`, and `allergies` value in all 21 profile-aware cases was checked against the live `conditions.json` (160 names), `goals.json` (144 names), and `allergies.json` (9 distinct `allergy` values) — zero mismatches.
7. **No duplicate/near-duplicate questions** — re-checked programmatically (49 unique question strings) and manually for near-duplicate intent (e.g., only one Vitamin-C-plus-iron question, one tea-and-iron question, despite the RAG corpus repeating both facts across four+ records each).
8. **Realistic parent/caregiver phrasing** — achieved for 48 of 49 cases; EVAL_045/EVAL_046 (age-banded energy/protein RDA tables) and EVAL_049 (Jelliffe deficiency signs) were deliberately kept closer to direct-reference phrasing, per the explicit instruction to retain "a smaller number of direct reference questions" for evaluation coverage, though even these were softened from the first draft's fully clinical phrasing.
9. **Appropriate category** — unchanged from the first draft, re-confirmed.
10. **Appropriate age_group** — unchanged from the first draft, re-confirmed against each record's own stated age band.
11. **No dependence on pending doctor-review content** — re-confirmed for every question, including EVAL_027 (lactose intolerance vs. milk allergy), which is based only on the two already-distinct current `allergies.json` records, not the pending taxonomy-fix proposal from the doctor-review batch.

---

## 5. Internal source mapping (documentation only — NOT copied into the JSON dataset)

Unchanged from the first draft for all rewritten/unchanged questions (same underlying record(s), only phrasing changed), with EVAL_008 and EVAL_048 updated to their new source records. This is **not** a `relevant_chunk_ids` annotation — no exhaustive full-corpus relevance search has been performed.

| ID | Primary KB source(s) consulted |
|---|---|
| EVAL_001 | `RAG_GUIDELINE_1`, `RAG_G1_2` |
| EVAL_002 | `RAG_MACRO_1`, `RAG_MACRO_2`, `RAG_MACRO_3` |
| EVAL_003 | `RAG_PROTEIN_2` |
| EVAL_004 | `RAG_CARB_2`, `rag_fiber_001` |
| EVAL_005 | `RAG_VITAMIN_1` |
| EVAL_006 | `RAG_IRON_3`, `rag_iron_002` |
| EVAL_007 | `RAG_IRON_2`, `rag_iron_bioavailability_logic_001` |
| EVAL_008 | `rag_super_nutrients_001` *(changed from `rag_nutrients_type_001`)* |
| EVAL_009 | `RAG_MINERAL_1` |
| EVAL_010 | `RAG3002`, `goal_complementary_001` |
| EVAL_011 | `RAG_INF_1`; structured DB `conditions.json: infant_6_8_months` |
| EVAL_012 | `RAG_INF_2`; structured DB `conditions.json: infant_9_12_months` |
| EVAL_013 | `RAG_INF_FULL_17` |
| EVAL_014 | `condition_readiness_001` |
| EVAL_015 | `goal_family_pot_001` |
| EVAL_016 | `condition_toddler_001` |
| EVAL_017 | `rag_behavioral_001` |
| EVAL_018 | `food_rice_porridge_001` |
| EVAL_019 | `allergies.json: nut_allergy` records |
| EVAL_020 | `allergies.json: nut_allergy` (`peanut_powder`) |
| EVAL_021 | `allergies.json: egg_protein` records |
| EVAL_022 | `allergies.json: milk` records |
| EVAL_023 | `allergies.json: cow_milk_protein_allergy` |
| EVAL_024 | `allergies.json: milk_protein_sensitive_enteropathy` |
| EVAL_025 | `allergies.json: gluten_sensitivity` |
| EVAL_026 | `allergies.json: fish` records |
| EVAL_027 | `allergies.json: lactose_intolerance` / `milk_lactose` vs. `milk` / `cow_milk_protein_allergy` (comparison across existing distinct records) |
| EVAL_028 | `conditions.json: iron_deficiency_anaemia`; `goals.json: iron_boost`; `RAG_MINERAL_2` |
| EVAL_029 | `conditions.json: malnutrition`; `goals.json: prevent_malnutrition` |
| EVAL_030 | `conditions.json: infant_diarrhea`; `RAG3006` |
| EVAL_031 | `conditions.json: low_birth_weight`; `condition_lbw_001` |
| EVAL_032 | `conditions.json: overweight_obesity`; `goals.json: weight_management` |
| EVAL_033 | `conditions.json: infant_illness_feeding`; `condition_illness_003` |
| EVAL_034 | `conditions.json: zinc_deficiency_signs`; `rag_trace_elements_002` |
| EVAL_035 | `conditions.json: breastfeeding`; `condition_maternal_illness_001` |
| EVAL_036 | `conditions.json: failure_to_thrive_organic`; `condition_ftt_001` |
| EVAL_037 | `foods.json: nuts` / `nuts_seeds` (`age_min=2`) |
| EVAL_038 | `foods.json: egg` (`age_min=1`) |
| EVAL_039 | `foods.json: fish` (`age_min=2`) |
| EVAL_040 | `fssai_handler_safety_001` |
| EVAL_041 | `fssai_water_ice_safety_001` |
| EVAL_042 | `fssai_hygiene_food_handling_001` |
| EVAL_043 | `fssai_tiffin_safety_001` |
| EVAL_044 | `rag_growth_001` |
| EVAL_045 | `icmr_2020_energy_children_001` (also `icmr_2020_v2_energy_table_004`) |
| EVAL_046 | `icmr_2020_v2_protein_table_003` (also `icmr_2020_protein_children_001`) |
| EVAL_047 | `goals.json: anthropometric_expected_norms` |
| EVAL_048 | `rag_pem_brain_001` *(changed from `goals.json: vitamin_a_prophylaxis` / `rag_vitamin_a_001`)* |
| EVAL_049 | `goals.json: jelliffe_clinical_signs_checklist` |

---

## 6. Final report

- **Final question count**: 49
- **Rewritten**: 46
- **Replaced**: 2 (EVAL_008, EVAL_048 — see §3 for exact old/new questions and rationale)
- **Unchanged**: 1 (EVAL_020)
- **Category counts**: General Nutrition & Nutrients 9; Age-Specific Feeding 9; Allergies & Intolerances 9; Pediatric Conditions 9; Food Safety & Suitability 7; Growth, Development & Reference Data 6
- **Profile-aware vs. knowledge-only**: 21 profile-aware, 28 knowledge-only (unchanged split from the first draft)
- **Diet-planning confirmation**: **zero** diet-planning/meal-planning questions in the revised set
- **Dosing/medication confirmation**: **zero** dosing/medication/prescription questions in the revised set — the one dosing question from the first draft (EVAL_048, Vitamin A prophylaxis schedule) has been replaced
- **Current-KB support confirmation**: every one of the 49 questions maps to a record independently re-confirmed present in `data/rag/rag_data.json` or a structured DB file this session (see §5); no question depends on the pending, unapproved doctor-review KB expansion batch
- **Gold-annotation confirmation**: **zero** `relevant_chunk_ids`, `gold_facts`, `reference_answer`, or `safety_ground_truth` values exist anywhere in `phase2b_evaluation_questions.json` — every case contains only `id`, `question`, `category`, `subcategory`, `age_group`, `knowledge_area`, `source_scope`, and `profile`
- **Files touched**: only `docs/evaluation/phase2b_evaluation_questions.md` (this file) and `docs/evaluation/phase2b_evaluation_questions.json` were modified. `evaluation/dataset.py`, all metric files, the notebook, the planner, and every knowledge-base JSON file remain unmodified (verified via `git status` after this task).
