# EVAL_028 — Heme-Iron Bioavailability Verification (Research Only, No Files Modified)

**Status: This is a research and verification report only. No knowledge-base file, evaluation dataset file, metric file, or notebook was modified while producing it.**

---

## 1. Current KB conflict

Two records in `data/rag/rag_data.json` are currently listed as `relevant_chunk_ids` supporting `EVAL_028` ("What foods can help my child who has iron deficiency anemia?") and give different numeric values for the same concept — heme iron's own absorption/bioavailability percentage:

| RAG ID | Value stated | Metadata type/tags | Source field |
|---|---|---|---|
| `rag_iron_bioavailability_logic_001` | Heme iron = **35%** bioavailable | `biochemistry`; tags: `iron_absorption`, `heme_iron`, `bioavailability`, `ferrous_vs_ferric` | (empty — no upstream citation stored) |
| `rag_iron_absorption_heme_001` | Heme iron = **15%** absorption | `mineral_metabolism`; tags: `iron_absorption`, `heme_iron`, `bioavailability`, `nutritional_inhibitors` | (empty — no upstream citation stored) |

## 2. Exact current statements and context (re-inspected directly this session)

**`rag_iron_bioavailability_logic_001`** (full text):
> "Iron Bioavailability: Ferrous iron is better absorbed than ferric iron. Heme iron (animal sources) is 35% bioavailable, whereas non-heme iron (plant sources) is only 5%. Vitamin C (lime juice) significantly enhances non-heme absorption."

**`rag_iron_absorption_heme_001`** (full text):
> "Iron Bioavailability: Heme iron (animal source) has 15% absorption; Non-heme (plant) has 5%. Absorption is enhanced by Vitamin C and inhibited by Caffeine, Calcium, and Zinc."

Both records:
- Explicitly attribute the number to **heme iron specifically** (not non-heme, not total dietary iron) — the two records are not talking past each other about different concepts; they both frame it as "heme iron's own absorption/bioavailability rate."
- Give the **same 5% figure for non-heme iron**, so the disagreement is isolated to the heme-iron number (35% vs. 15%), not a broader inconsistency.
- Carry **no source/provenance** in the record's own metadata (the `source` field is empty on both) — consistent with the Phase 1 KB audit's earlier finding that only a small fraction of RAG records carry a populated `source` field.
- Do not specify a physiological condition (e.g., iron-replete vs. iron-deficient), diet context, or age group — both are stated as unconditional, general facts.

## 3. Trusted-source research

All sources below were directly opened and read this session (not taken from search snippets).

### 3a. NIH Office of Dietary Supplements — Iron (Health Professional Fact Sheet)
- **Organization:** National Institutes of Health, Office of Dietary Supplements (U.S. government)
- **URL:** https://ods.od.nih.gov/factsheets/Iron-HealthProfessional/
- **Access date:** 2026-08-25 (direct HTTP fetch; the page blocks the standard web-fetch tool but was retrieved successfully via a direct request)
- **Exact statement (from the "Absorption, Metabolism, and Excretion" section):** *"Heme iron has higher bioavailability than nonheme iron, and other dietary components have less effect on the bioavailability of heme than nonheme iron [3,4]. The bioavailability of iron is approximately 14% to 18% from mixed diets that include substantial amounts of meat, seafood, and vitamin C (ascorbic acid, which enhances the bioavailability of nonheme iron) and 5% to 12% from vegetarian diets [2,4]."*
- **Important nuance:** this NIH page does **not** give a standalone "heme iron = X%" figure. Its 14–18%/5–12% numbers describe the bioavailability of a **whole diet** (meat-containing vs. vegetarian), not the absorption efficiency of heme iron in isolation. This is a materially different quantity from what either KB record claims to state.
- **Tier:** Primary/high-authority (government agency, first-party health-professional reference page).

### 3b. Hurrell R, Egli I. "Iron bioavailability and dietary reference values." *American Journal of Clinical Nutrition*, 2010;91(5):1461S–1467S.
- **DOI:** 10.3945/ajcn.2010.28674F — **PMID:** 20200263
- **Access date:** 2026-08-25 (PubMed abstract retrieved directly via NCBI E-utilities; this is the exact paper NIH ODS cites as reference [4] for the 14–18%/5–12% figures above)
- **Exact statement (abstract):** *"On the basis of intake data and isotope studies, iron bioavailability has been estimated to be in the range of 14–18% for mixed diets and 5–12% for vegetarian diets in subjects with no iron stores, and these values have been used to generate dietary reference values for all population groups."* The abstract further states: *"The iron status of the individual and other host factors... play a key role in iron bioavailability, and iron status generally has a greater effect than diet composition."*
- **Important nuance:** again, this is whole-diet bioavailability, explicitly defined for "subjects with no iron stores" (i.e., a specific physiological condition — iron depletion — not a universal constant). It does not give an isolated heme-iron percentage.
- **Tier:** Primary/high-authority peer-reviewed synthesis, published in a leading nutrition journal, and the direct primary source underlying the NIH ODS figures above.

### 3c. Piskin E, Cianciosi D, Gulec S, Tomas M, Capanoglu E. "Iron Absorption: Factors, Limitations, and Improvement Methods." *ACS Omega*, 2022;7(24):20441–20456.
- **DOI:** 10.1021/acsomega.2c01833 — **PMCID:** PMC9219084 — **PMID:** 35755397
- **URL:** https://pmc.ncbi.nlm.nih.gov/articles/PMC9219084/ (open access, fetched and read in full this session)
- **Exact statement (Section 4, "Bioavailability of Iron from Dietary Sources"):** *"Heme iron contributes 10–15% of the total iron intake. However, since heme iron is absorbed better than nonheme iron, with an approximate 15–35% of absorption, it can account for more than 40% of total intestinal iron absorption."* (citing its own reference [37])
- **This is the most directly on-point statement found**: a peer-reviewed 2022 review explicitly states heme iron's own absorption efficiency as **"approximately 15–35%"** — a *range*, whose two endpoints are exactly the two numbers the KidsNutriBite KB records state as if each were a single fixed value.
- **Tier:** Secondary supporting evidence (a peer-reviewed review synthesizing older primary isotope-study literature; its own citation trail for this specific range could not be fully traced back to the original 1970s–80s isotope studies within this session's access, but the journal itself — ACS Omega, an ACS-published, peer-reviewed, PubMed-indexed journal — is a legitimate scientific source, and the statement is consistent with the general absorption-physiology model described by the other two sources above).

### 3d. Anderson GJ, Frazer DM. "Current understanding of iron homeostasis." *American Journal of Clinical Nutrition*, 2017;106(Suppl 6):1559S–1566S.
- **DOI:** 10.3945/ajcn.117.155804 — **PMCID:** PMC5701707 — **PMID:** 29070551
- **Access date:** 2026-08-25 (abstract retrieved directly via NCBI E-utilities)
- **Exact statement:** *"In the diet, iron is either sequestered within heme or in various nonheme forms. Although the absorption of heme iron is poorly understood, nonheme iron is transported across the apical membrane of the intestinal enterocyte by divalent metal-ion transporter 1 (DMT1)..."*
- **Relevance:** a recent, authoritative, peer-reviewed iron-metabolism review explicitly states that the *mechanism* of heme iron absorption is "poorly understood" — supporting epistemic caution about treating any single fixed heme-iron percentage as a settled, precise constant, even though empirical absorption-percentage *estimates* (from isotope-tracer studies) do exist and are commonly cited.
- **Tier:** Primary/high-authority peer-reviewed review in a leading nutrition journal.

### Sources considered but not usable
- The project's own already-verified ICMR-NIN 2020 RDA brief note (used elsewhere in the KB) was re-checked (from this engagement's earlier Phase 1 KB audit extraction) — it discusses the general factorial method used to set mineral RDAs (accounting for absorption/bioavailability) but does **not** state a specific heme-iron absorption percentage anywhere in the extracted text. It cannot be used to adjudicate this specific number.
- No pediatric-specific study giving a general, healthy-child heme-iron absorption percentage was found (see §4).

## 4. Pediatric relevance

A targeted PubMed search for heme-iron absorption studies in children/infants returned pediatric iron-absorption literature that is **not** about establishing a general heme-iron-percentage-in-healthy-children figure — the pediatric studies found (e.g., iron-isotope-incorporation studies in Ugandan children with malaria and iron deficiency, hepcidin regulation in extremely preterm neonates) are about specific clinical/inflammatory contexts, not a baseline pediatric heme-iron-absorption constant.

**Conclusion on pediatric applicability:** No reliable, general pediatric-specific heme-iron-absorption percentage was found in this search. The commonly cited 15–35% range comes from adult-based isotope studies and dietary-reference-value-setting work (Hurrell & Egli 2010's "no iron stores" adult/general-population framing). Bodies that set pediatric iron RDAs (including ICMR-NIN and the U.S. Food and Nutrition Board, per the NIH ODS page's RDA table) generally apply population-level bioavailability assumptions across age groups rather than deriving an age-specific heme-iron percentage. **No pediatric-specific number is invented here** — per the instructions, this gap is stated explicitly rather than extrapolated.

What **is** well-supported for pediatric relevance, from the sources above: the underlying physiological principle — that heme iron (animal-source) is absorbed more efficiently and is less affected by dietary inhibitors/enhancers than non-heme (plant-source) iron — applies to children as it does to adults, since the transport mechanisms described (DMT1 for non-heme; a distinct, "poorly understood" pathway for heme) are general human intestinal physiology, not adult-specific. It is the **precise percentage**, not the qualitative direction of the effect, that lacks pediatric-specific verification.

## 5. 15% vs. 35% comparison

| Current KB value | RAG ID | What it actually refers to | External evidence | Correct? |
|---|---|---|---|---|
| 35% | `rag_iron_bioavailability_logic_001` | Heme iron's own absorption/bioavailability percentage (as stated in the record) | Matches the **upper end** of the peer-reviewed "approximately 15–35%" range (Piskin et al. 2022) | **Conditionally correct** — accurate as the upper bound of a real, cited range, but misleading when presented as the single, unconditional value for heme iron absorption |
| 15% | `rag_iron_absorption_heme_001` | Heme iron's own absorption/bioavailability percentage (as stated in the record) | Matches the **lower end** of the same peer-reviewed "approximately 15–35%" range (Piskin et al. 2022); also coincidentally close to (but not the same concept as) NIH ODS/Hurrell & Egli's 14–18% *whole-mixed-diet* bioavailability figure | **Conditionally correct** — accurate as the lower bound of the same real, cited range, but likewise misleading when presented as a single unconditional value |

**Neither number is fabricated or unsupported** — both fall inside a range that a peer-reviewed nutrition-science review explicitly cites for heme iron. The KB's actual error is not "one number is right and one is wrong"; it is that **two different single-point snapshots of the same real range were each written into the KB as if they were the complete, unconditional truth**, with no record capturing that it is a range dependent on physiological/dietary context (most notably the individual's existing iron status — Hurrell & Egli's finding that "iron status generally has a greater effect than diet composition" applies here too, though that specific finding was stated for whole-diet bioavailability, not heme iron in isolation, so it is offered as directionally relevant context rather than direct proof of the heme-iron range's cause).

## 6. Evidence quality

- **Primary/high-authority evidence:** NIH ODS Iron fact sheet (government); Hurrell & Egli 2010, *AJCN* (peer-reviewed, the direct source underlying the NIH figures); Anderson & Frazer 2017, *AJCN* (peer-reviewed, authoritative current review of iron homeostasis).
- **Secondary supporting evidence:** Piskin et al. 2022, *ACS Omega* (peer-reviewed review synthesizing the "15–35%" heme-iron figure specifically; the single most directly on-point statement found, but one step further from the original primary isotope studies than the AJCN sources above).
- **Not used:** no Wikipedia, blogs, forums, SEO/wellness sites, or AI-generated summaries were consulted at any point. No number was accepted from a search-result snippet without opening and reading the actual source page/abstract.

## 7. Final medical/nutrition conclusion

The evidence-based absorption/bioavailability of heme iron in humans is best described as **approximately 15–35%**, varying primarily with the individual's iron status (lower absorption efficiency when iron-replete, higher when iron-deficient) — not a single fixed percentage. This is explicitly stated in a peer-reviewed review (Piskin et al. 2022) and is consistent with the general absorption-physiology picture given by NIH ODS and Hurrell & Egli (2010), even though those two sources report a related-but-distinct whole-diet bioavailability figure (14–18% mixed diet / 5–12% vegetarian diet) rather than an isolated heme-iron number. A recent authoritative review (Anderson & Frazer 2017) further cautions that the absorption mechanism for heme iron specifically is still not fully mechanistically understood, reinforcing that a single precise percentage should be treated as an approximation, not a settled constant.

**No pediatric-specific percentage exists in the literature reviewed this session** — the range above is derived from adult/general-population isotope studies and dietary-reference-value work, and no evidence was found (or should be assumed) that this range is meaningfully different for healthy children versus adults, beyond the general caution that no pediatric-specific number has been independently verified.

## 8. Recommended KB correction, if any

**Recommendation: Option C — Keep both values, but reframe them as a range with the shared, unresolved context, rather than as two competing single-point facts.**

Specifically (for the team's future consideration — no KB file has been changed in this task): the KB should ideally state something like *"Heme iron is absorbed considerably more efficiently than non-heme iron — commonly cited estimates range from about 15% to 35%, with individual iron status being a major factor in where within that range actual absorption falls,"* rather than the two current records that each assert one fixed percentage as if it were unconditionally true. Options A (keep only 35%) and B (keep only 15%) would each discard a genuinely evidence-supported value; Option E (remove the percentage entirely) is not warranted given the evidence base is reasonably solid at the range level, just imprecise at the single-point level; Option D (replace both with a validated range/statement) is effectively the same recommendation as C, restated as a rewrite rather than a keep-both-and-clarify — either D or C is defensible, and the choice between them is a KB-editing/wording decision for the team, not a medical-accuracy question this report needs to resolve.

**This recommendation is not implemented in this task** — per the explicit instruction, no production KB file was modified.

## 9. Impact on EVAL_028

Re-inspected `EVAL_028`'s current `gold_facts` and `reference_answer` directly (in `docs/evaluation/phase2c_gold_annotations.json`):

- `GF_EVAL_028_02` states: *"Green leafy vegetables, pulses, and dry fruits are plant sources of iron; iron from animal foods is better absorbed than iron from plant sources."* — **qualitative only, no percentage cited.**
- The `reference_answer` states: *"...animal sources (better absorbed) as well as plant sources like green leafy vegetables, pulses, and dry fruits — paired with Vitamin C-rich foods to boost absorption..."* — **qualitative only, no percentage cited.**

**The disputed 15%/35% figure is NOT necessary to answer EVAL_028.** The question asks what foods can help a child with iron deficiency anemia — a food-recommendation question, not a "what percentage of heme iron is absorbed" question. The qualitative claim actually needed to answer it ("animal-source iron is absorbed better than plant-source iron, so include animal-source iron and pair plant-source iron with Vitamin C") is fully supported by every source reviewed here (KB and external), independent of which exact percentage is used.

**Conclusion: `EVAL_028` is safe to keep as a gold case, and its status can return to `ANNOTATED`.** The two conflicting chunks (`rag_iron_bioavailability_logic_001`, `rag_iron_absorption_heme_001`) may remain in its `relevant_chunk_ids` list for retrieval-metric purposes (both are genuinely topically relevant and retrievable), since Recall@5/MAP@5/MRR@5 evaluate retrieval, not the correctness of a specific percentage inside the retrieved text — and no `gold_fact` or the `reference_answer` asserts either disputed number as fact. This report does not itself change `phase2c_gold_annotations.json`'s status field; that update, if desired, is a separate, minimal follow-up action for whoever maintains the gold-annotation file (see §11–§12).

## 10. Exact sources and citations (summary)

1. National Institutes of Health, Office of Dietary Supplements. "Iron — Health Professional Fact Sheet." https://ods.od.nih.gov/factsheets/Iron-HealthProfessional/ — accessed 2026-08-25.
2. Hurrell R, Egli I. "Iron bioavailability and dietary reference values." *Am J Clin Nutr*. 2010;91(5):1461S–1467S. doi:10.3945/ajcn.2010.28674F. PMID: 20200263 — accessed 2026-08-25.
3. Piskin E, Cianciosi D, Gulec S, Tomas M, Capanoglu E. "Iron Absorption: Factors, Limitations, and Improvement Methods." *ACS Omega*. 2022;7(24):20441–20456. doi:10.1021/acsomega.2c01833. PMCID: PMC9219084. PMID: 35755397 — accessed 2026-08-25.
4. Anderson GJ, Frazer DM. "Current understanding of iron homeostasis." *Am J Clin Nutr*. 2017;106(Suppl 6):1559S–1566S. doi:10.3945/ajcn.117.155804. PMCID: PMC5701707. PMID: 29070551 — accessed 2026-08-25.

## 11. Confirmation that NO production KB files were modified

`data/rag/rag_data.json`, `data/rag/faiss.index`, `data/rag/metadata.pkl`, and every `data/structured_db/*.json` file remain exactly as they were before this task. This was a research-only task.

## 12. Confirmation that no unverified number was inserted into the evaluation gold data

`docs/evaluation/phase2c_gold_annotations.json` was **not modified** by this task. `EVAL_028`'s existing gold facts and reference answer already avoided citing either disputed percentage (confirmed in §9), and no new number — verified or otherwise — has been added to it as part of this research task. Any future update to `EVAL_028`'s `annotation_status` (from `NEEDS_REVIEW` back to `ANNOTATED`) or to the underlying KB records, based on this report's findings, is left as a separate, explicit follow-up action, not performed automatically here.
