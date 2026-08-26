# Knowledge Base Change Log — Batch: Allergy Consolidation (Option 3)

**Status: research/proposal only. `data/structured_db/allergies.json` has NOT been modified.** Every row below is a proposal awaiting doctor review per `docs/doctor_review/knowledge_base_change_log_template.md`. No `avoid_foods`/`severity` value has been written back to the actual file.

Sources were opened and read directly this session (WebFetch, with PDF text extracted via `pypdf` where the fetch summarizer couldn't parse binary content) — not accepted from search snippets alone, per the trusted-source policy. Where a source could not be opened (paywalled/blocked), this is stated explicitly rather than treated as verified.

## Current `allergies.json` records addressed in this batch

| # | allergy | avoid_foods (current) | severity (current) |
|---|---|---|---|
| 1 | nut_allergy | `["nuts_seeds"]` | high |
| 2 | lactose_intolerance | `["milk_curd"]` | medium |
| 3 | lactose_intolerance | `["milk"]` | medium |
| 4 | nut_allergy | `["nuts"]` | high |
| 5 | milk_lactose | `["milk"]` | moderate |
| 7 | milk | `["eggnog","milk_added_recipes","milk_added_foods","curd"]` | moderate |
| 8/14 | fish | `["mashed_fish","pomfret_fish_mashed","murrel_fish_mashed"]` (×2, identical) | moderate |
| 10 | milk | `["eggnog","milk_added_foods"]` | moderate |
| 11 | nut_allergy | `["peanut_powder","sesame_powder"]` | high |
| 13 | milk | `["curd"]` | moderate |
| 15 | cow_milk_protein_allergy | `["cows_milk","unmodified_bovine_milk"]` | *(blank)* |
| 16 | milk_protein_sensitive_enteropathy | `["bovine_milk","unmodified_cow_milk"]` | *(blank)* |
| 17 | gluten_sensitivity | `["wheat","barley","rye"]` | *(blank)* |

(egg_protein records 6/9/12 also belong to this batch by scope but are not addressed here — see "Not Completed" below.)

---

## CHG-0001 — Taxonomy flag: lactose intolerance is not an allergy

- **Source File**: `data/structured_db/allergies.json`
- **Record ID / Item Name**: records 2 and 3 (`lactose_intolerance`)
- **Change Type**: FLAG FOR DOCTOR DECISION (not a simple field update — see reason)
- **Existing Value**: classified as an entry in `allergies.json` alongside true allergies, `severity: "medium"`
- **Proposed New Value/Content**: *no value proposed* — the finding is that this item may not belong in an allergy file at all, or needs an explicit "intolerance, not allergy" flag distinguishing it from IgE-mediated allergies. Left for doctor decision.
- **Reason for Change**: Verified directly that lactose intolerance and milk allergy are mechanistically distinct: lactose intolerance is a digestive enzyme (lactase) deficiency causing malabsorption, not an immune reaction. Confirmed independently by a second source: "Cow's milk allergy must be distinguished from primary lactose intolerance" (BSACI guideline, see CHG-0002 source). NIDDK also states it does not assign lactose intolerance a severity scale — tolerance is dose-dependent per individual, not a fixed severity tier.
- **Knowledge Category**: allergies (taxonomy/scope question)
- **Source/Reference**: National Institute of Diabetes and Digestive and Kidney Diseases (NIDDK), part of NIH — "Definition & Facts for Lactose Intolerance." Government health institute, Tier 1.
- **Exact Source Location**: https://www.niddk.nih.gov/health-information/digestive-diseases/lactose-intolerance/definition-facts — page opened and read directly this session. Quote: *"lactose intolerance is a condition in which you have digestive symptoms... after you consume foods... that contain lactose"* vs. *"a milk allergy is an immune system disorder."* Access date: 2026-08-25.
- **Whether primary guidance, clinical guideline, or research**: Primary government patient/clinical guidance.
- **Doctor Review Status**: Not Reviewed

---

## CHG-0002 — Milk allergy avoid-foods list, sourced

- **Source File**: `data/structured_db/allergies.json`
- **Record ID / Item Name**: records 5, 7, 10, 13, 15, 16 (`milk_lactose`, `milk`×3, `cow_milk_protein_allergy`, `milk_protein_sensitive_enteropathy`) — proposed to be considered together, not individually
- **Change Type**: UPDATE EXISTING RECORD (proposed consolidated `avoid_foods`, pending doctor decision on how to merge with existing project-specific items like `curd`/`eggnog`)
- **Existing Value**: 6 separate records, 5 different (non-identical) `avoid_foods` lists, see table above
- **Proposed New Value/Content**: A verified, evidence-based ingredient list exists (Table 9 of the source below): *"Butter, butter fat, butter milk, butter oil; Casein (curds), caseinates, hydrolysed casein, calcium caseinate, sodium caseinate; Cheese, cheese powder, cottage cheese; Cow's milk (fresh, condensed, dried, evaporated, powdered (infant formulas), UHT); Cream, artificial cream, sour cream; Ghee; Ice cream; Lactalbumin, lactoglobulin; Low-fat milk; Malted milk; Margarine; Milk protein, milk powder, skimmed milk powder, milk solids, non-fat dairy solids, non-fat milk solids, milk sugar; Whey, hydrolysed whey, whey powder, whey syrup sweetener; Yogurt, fromage frais."* This is presented as source evidence, **not yet mapped onto the project's existing item-naming convention** (e.g. how `curd`/`eggnog`/`milk_added_recipes` in the current records correspond to this list) — that mapping needs doctor input, not an automatic substitution.
- **Reason for Change**: Current 6 records have inconsistent, narrower `avoid_foods` lists than a verified clinical source provides, and are fragmented across multiple differently-named records for what may be overlapping concepts.
- **Knowledge Category**: allergies
- **Source/Reference**: Luyt D, Ball H, Makwana N, Green MR, Bravin K, Nasser SM, Clark AT. "BSACI guideline for the diagnosis and management of cow's milk allergy." *Clinical & Experimental Allergy*, 2014;44:642-672. British Society for Allergy and Clinical Immunology (BSACI) — Tier 2 professional organization; peer-reviewed journal — Tier 3. DOI: 10.1111/cea.12302.
- **Exact Source Location**: Table 9, "Food items and ingredients that contain cow's milk protein," page 656 (PDF page 15) — PDF opened directly and text extracted this session (`https://www.bsaci.org/wp-content/uploads/2020/09/Milk-guideline-pdf.pdf`). Access date: 2026-08-25.
- **Whether primary guidance, clinical guideline, or research**: Official clinical guideline (Standards of Care Committee, BSACI).
- **Doctor Review Status**: Not Reviewed

---

## CHG-0003 — Milk allergy severity: source does not map to a single categorical value

- **Source File**: `data/structured_db/allergies.json`
- **Record ID / Item Name**: records 5, 7, 10, 13 (currently `severity: "moderate"`); records 15, 16 (currently blank)
- **Change Type**: FLAG FOR DOCTOR DECISION — **no value proposed**
- **Existing Value**: `"moderate"` (4 records) / `""` (2 records)
- **Proposed New Value/Content**: None. The source distinguishes IgE-mediated cow's milk allergy (immediate onset, capable of anaphylaxis, potentially severe) from non-IgE-mediated cow's milk allergy (delayed onset, typically gastrointestinal, usually not anaphylactic) — this is the clinically meaningful severity-relevant distinction, but it does not translate into a single "high/medium/moderate" label the way the project's schema expects. Per the strict no-fabrication/no-inference rule, I am not assigning a severity value from this — it needs a doctor's judgment on how (or whether) to encode IgE-mediated vs. non-IgE-mediated status in the existing schema.
- **Reason for Change**: N/A — flag only, not a proposed value.
- **Knowledge Category**: allergies
- **Source/Reference**: Same as CHG-0002 (BSACI 2014 guideline).
- **Exact Source Location**: Multiple sections discussing IgE-mediated vs. non-IgE-mediated presentation throughout the guideline (41 and 24 occurrences respectively, confirmed via direct text search of the extracted PDF); not a single table.
- **Whether primary guidance, clinical guideline, or research**: Official clinical guideline.
- **Doctor Review Status**: Not Reviewed

---

## CHG-0004 — Nut allergy: current blanket-avoidance framing may not reflect current guidance

- **Source File**: `data/structured_db/allergies.json`
- **Record ID / Item Name**: records 1, 4, 11 (`nut_allergy`×3)
- **Change Type**: FLAG FOR DOCTOR DECISION — **no value proposed**
- **Existing Value**: three separate `nut_allergy` records with `avoid_foods` of `["nuts_seeds"]`, `["nuts"]`, `["peanut_powder","sesame_powder"]` respectively — all framing "nut allergy" as a single category with blanket avoidance.
- **Proposed New Value/Content**: None proposed. Flagging that a current (2024/2025), official, peer-reviewed guideline explicitly recommends *against* this framing.
- **Reason for Change**: **This is a design-level finding, not a value-completeness gap.** Verified directly: *"Foods related to an implicated allergen should not be automatically avoided and their consumption should be maintained (e.g. other tree nuts already tolerated in a hazel nut allergic child)."* This is current, top-tier, official guidance recommending individualized, per-specific-nut assessment rather than the blanket "avoid nuts/nuts_seeds" framing the project currently uses. Restructuring `nut_allergy` from one category into per-nut records (or otherwise encoding this nuance) is a scope decision for the doctor and project team, not something to silently fix by picking a value.
- **Knowledge Category**: allergies (design/scope question)
- **Source/Reference**: Santos AF, Riggioni C, Agache I, et al. "EAACI guidelines on the management of IgE-mediated food allergy." *Allergy*, 2024 (published online 30 Oct 2024; issue Jan 2025). European Academy of Allergy and Clinical Immunology (EAACI) — Tier 2 professional organization; peer-reviewed — Tier 3. DOI: 10.1111/all.16345.
- **Exact Source Location**: "Recommendation 2 (Continued consumption of tolerated foods)" section — open-access version at https://pmc.ncbi.nlm.nih.gov/articles/PMC11724237/, opened and read directly this session. Access date: 2026-08-25.
- **Whether primary guidance, clinical guideline, or research**: Official clinical guideline (EAACI).
- **Doctor Review Status**: Not Reviewed
- **Additional unverified observation (not a sourced claim)**: record 11 lists `sesame_powder` under `nut_allergy` — sesame is regulatorily and clinically treated as its own distinct major allergen category in several jurisdictions (not a tree nut or a peanut/legume), which may mean this item is miscategorized. This observation was **not independently verified against a primary source this session** and is flagged only as something worth the doctor's attention, not a confirmed finding.

---

## CHG-0005 — Fish allergy: confirmed true duplicate, no new sourcing needed

- **Source File**: `data/structured_db/allergies.json`
- **Record ID / Item Name**: records 8 and 14 (`fish`)
- **Change Type**: UPDATE EXISTING RECORD (consolidation — remove one exact duplicate)
- **Existing Value**: two records, both `avoid_foods: ["pomfret_fish_mashed","murrel_fish_mashed"]` (record 8 additionally has `mashed_fish`)
- **Proposed New Value/Content**: Not a sourcing question — records 8 and 14 are near-identical (record 8 has one extra item). No external source needed to observe this; a doctor should simply confirm whether `mashed_fish` (a generic term) is intended to be redundant with the two specific fish names, or should be kept as a broader catch-all category.
- **Reason for Change**: Data hygiene, not new medical fact.
- **Knowledge Category**: allergies
- **Source/Reference**: N/A — internal consistency observation, not a sourced fact.
- **Exact Source Location**: N/A
- **Whether primary guidance, clinical guideline, or research**: N/A
- **Doctor Review Status**: Not Reviewed

---

## Not Completed This Session — explicit status, per "INSUFFICIENT VERIFIED EVIDENCE" rule

- **egg_protein (records 6, 9, 12)**: A directly relevant, real, peer-reviewed source was identified — Leech SC, Ewan PW, Skypala IJ, et al. "BSACI 2021 guideline for the management of egg allergy," *Clinical & Experimental Allergy* 2021;51(10):1262-1278, DOI: 10.1111/cea.14009 (BSACI, Tier 2/3). **Its actual content was NOT opened or independently verified this session** — the Wiley Online Library page returned HTTP 403 on every attempt, and no alternate direct-PDF host was found (unlike the milk guideline, which BSACI hosts directly). Status: **INSUFFICIENT VERIFIED EVIDENCE** — no avoid_foods/severity proposal made. A WebSearch-only summary suggested baked-egg tolerance nuance similar to milk, but per the strict rule this is explicitly **not treated as verified** and no value is proposed from it.
- **gluten_sensitivity (record 17)**: Not researched this session (deprioritized by remaining time/effort within this batch). `severity` remains blank; `avoid_foods: ["wheat","barley","rye"]` not verified against a primary celiac/gluten-sensitivity guideline (e.g. ESPGHAN) this session. Status: **not yet attempted**.

## Summary of what this batch does and does not do

- Proposes one sourced, verifiable expansion (CHG-0002, milk avoid-foods list) with an exact table/page citation.
- Raises two design-level flags requiring doctor judgment, not data entry (CHG-0001 lactose-intolerance taxonomy; CHG-0004 nut-allergy blanket-avoidance framing) — both backed by directly-opened, current, authoritative guidelines.
- Explicitly declines to fabricate a severity value where the source doesn't map cleanly to the schema (CHG-0003).
- Explicitly reports two items (egg, gluten) as unverified/incomplete rather than filling them with unverified or inferred content.
- **`data/structured_db/allergies.json` has not been edited.** All of the above are proposals in this log only.
