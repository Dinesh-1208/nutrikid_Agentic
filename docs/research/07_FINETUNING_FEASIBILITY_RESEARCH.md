# 07 — Fine-Tuning Feasibility: Dataset Survey and Recommendation

**Mandated constraint from the brief:** *"DO NOT recommend fine-tuning automatically."* Fine-tuning is
to be recommended **only if suitable public datasets exist.**

**Headline finding, stated first:**

> After a systematic search of public dataset repositories and the research literature, **no public
> dataset suitable for instruction-tuning a pediatric nutrition assistant was found.** The closest
> candidates are either (a) general medical exam QA with negligible pediatric-nutrition content,
> (b) food-composition *tables* rather than QA pairs, (c) food *NER* annotations rather than
> instructions, or (d) a 50-item vision benchmark that shares only its name with our task.
>
> **Therefore this report does not recommend fine-tuning at this stage.** §7 gives the conditions
> under which that conclusion should be revisited, and §8 gives the one narrow fine-tuning path that
> would be defensible if the project insists on one.

This negative result is itself a reportable finding, and arguably a more useful contribution than an
unjustified fine-tuning run: *"a public instruction-tuning corpus for pediatric nutrition guidance,
particularly in the Indian dietary context, does not currently exist"* is a concrete, citable gap
statement for the paper's future-work section.

---

## 1. Search Methodology

To make the negative finding credible, the search procedure is documented.

**Repositories and sources searched:**
- Hugging Face Datasets Hub (queries: nutrition, pediatric nutrition, dietetics, food QA, child nutrition, meal planning)
- arXiv / ACL Anthology / PubMed for associated papers
- Papers With Code
- Government and IGO data portals: USDA FoodData Central, WHO, UNICEF, ICMR-NIN (India)
- Open Food Facts

**Inclusion criteria applied:**
1. Publicly downloadable (no private/paywalled access)
2. A usable license for research
3. Content in the nutrition, food or medical-nutrition domain
4. Convertible to instruction-response pairs

**Exclusion criteria:** proprietary, image-only where our task is text, or fewer than ~50 usable items.

---

## 2. Dataset Survey

Each entry is documented against the fields the brief requires: Name, Source, License, Domain,
Number of samples, Pediatric relevance, Indian relevance, Suitability for Qwen instruction tuning,
Associated papers, Limitations.

---

### 2.1 MedQA (USMLE)

| Field | Value |
|---|---|
| **Name** | MedQA |
| **Source** | [GitHub: jind11/MedQA](https://github.com/jind11/MedQA) · [HF: bigbio/med_qa](https://huggingface.co/datasets/bigbio/med_qa) |
| **License** | MIT |
| **Domain** | Medical licensing-exam multiple-choice QA (US, Mainland China, Taiwan) |
| **Samples** | **12,723** English (USMLE) questions; ~61k across all three languages |
| **Pediatric relevance** | **Low.** Some pediatrics items, but as exam questions, not nutrition guidance |
| **Indian relevance** | **None** |
| **Suitability for Qwen instruction tuning** | **Poor for our task.** Format is 4–5-option MCQ with a letter answer. Our task is *grounded explanatory guidance for a parent*. Training on MCQ would push the model toward terse letter answers — the opposite of what our prompts require |
| **Paper** | Jin, Pan, Oufattole, Weng, Fang & Szolovits, *What Disease Does This Patient Have?*, Applied Sciences 11(14):6421, 2021 — [arXiv:2009.13081](https://arxiv.org/abs/2009.13081) · [DOI 10.3390/app11146421](https://doi.org/10.3390/app11146421) |
| **Limitations** | Format mismatch; clinician-facing not parent-facing; no nutrition focus; no Indian foods |

---

### 2.2 MedMCQA

| Field | Value |
|---|---|
| **Name** | MedMCQA |
| **Source** | [medmcqa.github.io](https://medmcqa.github.io/) · [HF: openlifescienceai/medmcqa](https://huggingface.co/datasets/openlifescienceai/medmcqa) |
| **License** | ⚠️ **Inconsistently stated across sources** — MIT on the project repo, but different terms appear elsewhere. **Must be verified before any use.** This is a genuine blocker, not a formality |
| **Domain** | Indian medical entrance exam MCQs (AIIMS, NEET-PG) |
| **Samples** | **~194,000** |
| **Pediatric relevance** | **Low–moderate.** Pediatrics is one of 21 subjects covered, but questions are diagnostic/clinical, not dietary guidance |
| **Indian relevance** | **High — the highest of any medical dataset found.** Derived from Indian exams, so Indian disease prevalence and terminology are represented |
| **Suitability for Qwen instruction tuning** | **Poor for our task, same format mismatch as MedQA.** Its value is as evidence that Indian medical QA data exists, not as usable training data for grounded parent-facing nutrition guidance |
| **Paper** | Pal, Umapathi & Sankarasubbu, *MedMCQA: A Large-scale Multi-Subject Multi-Choice Dataset for Medical domain QA*, PMLR CHIL 2022 — [PMLR v174](https://proceedings.mlr.press/v174/pal22a.html) · [arXiv:2203.14371](https://arxiv.org/abs/2203.14371) |
| **Limitations** | License uncertainty; MCQ format; exam-oriented; nutrition is a small minority of content |

---

### 2.3 PubMedQA

| Field | Value |
|---|---|
| **Name** | PubMedQA |
| **Source** | [pubmedqa.github.io](https://pubmedqa.github.io/) · [HF: qiaojin/PubMedQA](https://huggingface.co/datasets/qiaojin/PubMedQA) |
| **License** | MIT |
| **Domain** | Biomedical research QA over PubMed abstracts; yes/no/maybe answers |
| **Samples** | **1,000** expert-annotated (PQA-L), 61.2k unlabeled, **211,300** artificially generated (PQA-A) |
| **Pediatric relevance** | **Low.** Some pediatric nutrition abstracts exist but are not identified as a subset |
| **Indian relevance** | **None** |
| **Suitability for Qwen instruction tuning** | **Interesting but indirect.** Its structure — *answer a question **given a retrieved context**, and stay grounded in it* — is genuinely analogous to our RAG task. But the answers are yes/no/maybe plus a long-form conclusion, and the register is researcher-facing |
| **Paper** | Jin, Dhingra, Liu, Cohen & Lu, *PubMedQA: A Dataset for Biomedical Research Question Answering*, EMNLP-IJCNLP 2019 — [arXiv:1909.06146](https://arxiv.org/abs/1909.06146) · [ACL D19-1259](https://aclanthology.org/D19-1259/) |
| **Limitations** | Research abstracts, not caregiver guidance; the 211k artificial subset is machine-generated and noisy; no pediatric or Indian subset |

---

### 2.4 NutritionQA — ⚠️ name collision, not what it sounds like

| Field | Value |
|---|---|
| **Name** | NutritionQA |
| **Source** | [HF: yyupenn/NutritionQA](https://huggingface.co/datasets/yyupenn/NutritionQA) |
| **License** | See dataset card |
| **Domain** | **Vision-language**: photographs of nutrition **labels**, with descriptive and reasoning questions |
| **Samples** | **50 photographs** |
| **Pediatric relevance** | **None** |
| **Indian relevance** | **None** |
| **Suitability for Qwen instruction tuning** | **None.** It is an image benchmark of 50 items. Qwen2.5-7B-**Instruct** as we deploy it is a text-only model |
| **Paper** | Dataset card |
| **Limitations** | Despite the promising name, this is unusable for our task. **Flagging it explicitly because its name makes it the first hit for "nutrition QA dataset" and it would be an easy citation error in a literature review** |

---

### 2.5 FoodBase corpus (FoodNER)

| Field | Value |
|---|---|
| **Name** | FoodBase |
| **Source** | Jožef Stefan Institute; published in *Database* (Oxford) |
| **License** | See publication; academic use |
| **Domain** | **Food named-entity annotation** over recipe text |
| **Samples** | **Gold standard: 1,000 recipes, 12,844 annotations, 2,105 unique entities.** Weakly annotated: 21,790 recipes, 274,053 annotations, 13,079 unique entities |
| **Pediatric relevance** | **None** |
| **Indian relevance** | **Low.** Recipe corpus is Western-oriented; coverage of ragi, khichdi, poha, sattu etc. is **NOT VERIFIED** and should be measured before relying on it |
| **Suitability for Qwen instruction tuning** | **Not applicable — wrong task.** It is span annotation, not instruction data. **However it is highly relevant to `01_NER_RESEARCH.md`** as training/evaluation data for a `FOOD` entity recogniser |
| **Paper** | Popovski & Koroušić Seljak, *FoodBase corpus: a new resource of annotated food entities*, *Database* (Oxford), 2019 — [PMC6827550](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6827550/) · [PubMed 31682732](https://pubmed.ncbi.nlm.nih.gov/31682732/) |
| **Limitations** | NER only; recipe domain; no nutrition guidance; Indian coverage unverified |

---

### 2.6 USDA FoodData Central

| Field | Value |
|---|---|
| **Name** | FoodData Central (FDC) |
| **Source** | [fdc.nal.usda.gov](https://fdc.nal.usda.gov/) · [API](https://fdc.nal.usda.gov/api-guide.html) |
| **License** | **CC0 1.0 Public Domain** — the most permissive license of anything in this survey |
| **Domain** | Food composition: nutrients per food item |
| **Samples** | **600,000+** food entries across Foundation Foods, SR Legacy, FNDDS, Branded Foods |
| **Pediatric relevance** | **Indirect.** Composition data is age-agnostic |
| **Indian relevance** | **Low.** US food supply; some Indian branded items in the Branded Foods subset, but staples are US-centric |
| **Suitability for Qwen instruction tuning** | **Not as instruction data — and deliberately so.** This is *structured numeric data*, which belongs in our deterministic planner (`foods.json`), **not** in the LLM's weights. Training a language model to memorise nutrient values is precisely the design error our architecture already avoids (`00` §6: *numbers come from code, prose comes from the model*) |
| **Paper** | [USDA FoodData Central documentation](https://fdc.nal.usda.gov/) |
| **Limitations** | Not QA data; US-centric; API key required (rate-limited, ~1,000 requests/hour) |
| **Actual value to this project** | **High — but for the database, not the model.** Could expand `foods.json` from 99 items |

---

### 2.7 IFCT 2017 — Indian Food Composition Tables

| Field | Value |
|---|---|
| **Name** | Indian Food Composition Tables (IFCT) 2017 |
| **Source** | ICMR – National Institute of Nutrition, Hyderabad — [nin.res.in/ebooks/IFCT2017.pdf](https://www.nin.res.in/ebooks/IFCT2017.pdf) · [FAO INFOODS listing](https://www.fao.org/food-composition/tables-and-databases/detail/(country--date)-title-9/en) |
| **License** | ⚠️ **Not a standard open license.** Described as an open-access publication, but redistribution terms are **NOT VERIFIED**. Published as a PDF book, not as a licensed dataset. **Clarify before redistributing any extract** |
| **Domain** | Indian food composition |
| **Samples** | **528 raw food items**, **151 food components** (macronutrients, vitamins, minerals, phytochemicals, amino acids, fatty acids; includes vitamin D2, oligosaccharides, phytosterols, organic acids, individual polyphenols). Groups include cereals & millets (24), grain legumes (25), green leafy vegetables (34), other vegetables (78), fruits (68), roots & tubers (19), condiments & spices (33), nuts & oilseeds (21) |
| **Pediatric relevance** | Indirect (composition is age-agnostic), but it is the correct compositional basis for Indian pediatric diets |
| **Indian relevance** | **Highest of any resource in this survey.** This is *the* authoritative Indian food composition reference |
| **Suitability for Qwen instruction tuning** | **Not as instruction data.** Same argument as USDA FDC — this is planner data |
| **Related** | Indian Nutrient Databank (INDB), an open-access database derived from IFCT — *Development of an Indian Food Composition Database* — [PMC11277795](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11277795/) · [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S2475299124017244). **Access terms NOT VERIFIED** (the PMC page was CAPTCHA-gated at time of writing) |
| **Limitations** | PDF format requires extraction; redistribution license unclear; raw foods, not cooked dishes; not QA data |
| **Actual value to this project** | **Very high — for `foods.json`, not for fine-tuning.** Our 99-item food database could be grounded in the authoritative national reference, which would be a **strong, defensible claim for the paper** |

---

### 2.8 WHO / UNICEF Infant and Young Child Feeding (IYCF) indicators

| Field | Value |
|---|---|
| **Name** | IYCF indicators + UNICEF global database |
| **Source** | WHO/UNICEF, *Indicators for assessing infant and young child feeding practices: definitions and measurement methods*, 2021 — [WHO](https://www.who.int/publications/i/item/9789240018389) · [UNICEF data](https://data.unicef.org/topic/nutrition/infant-and-young-child-feeding/) |
| **License** | UNICEF global database under **CC BY 3.0 IGO**; WHO publications under CC BY-NC-SA 3.0 IGO |
| **Domain** | Infant and young child feeding practice indicators and country-level statistics |
| **Samples** | **17 indicators**; country-level time series |
| **Pediatric relevance** | **Highest of any resource in this survey** — the 0–23 month window is exactly the age band where dietary guidance is most safety-critical |
| **Indian relevance** | **Good** — India is covered in the global database |
| **Suitability for Qwen instruction tuning** | **Not as instruction data**, but **excellent as authoritative RAG corpus content.** The guideline text is exactly what our `rag_data.json` should contain, and it is properly licensed for reuse with attribution |
| **Paper** | WHO/UNICEF 2021 (above) |
| **Limitations** | Indicators and statistics, not QA pairs; population-level, not individual guidance |
| **Actual value** | **High — expand the RAG corpus, with a citable authoritative source and a clear license** |

---

### 2.9 Open Food Facts

| Field | Value |
|---|---|
| **Name** | Open Food Facts |
| **Source** | [world.openfoodfacts.org/data](https://world.openfoodfacts.org/data) |
| **License** | Database under **Open Database License (ODbL)**; product images CC BY-SA. **ODbL has share-alike obligations** — relevant if derived data is redistributed |
| **Domain** | Crowd-sourced packaged-food products with nutrition labels |
| **Samples** | Millions of products (count varies continuously) |
| **Pediatric relevance** | Low (though it does carry baby-food categories) |
| **Indian relevance** | Moderate — Indian products present, coverage uneven |
| **Suitability for Qwen instruction tuning** | Not applicable — product records, not QA |
| **Limitations** | Crowd-sourced → variable quality; packaged foods rather than home-cooked meals, which is the wrong emphasis for Indian pediatric diets; ODbL share-alike |

---

### 2.10 FoodSky / FoodEarth — the closest published precedent

| Field | Value |
|---|---|
| **Name** | FoodSky (model) / FoodEarth (corpus) |
| **Source** | [arXiv:2406.10261](https://arxiv.org/abs/2406.10261) |
| **License** | **Public availability of FoodEarth NOT VERIFIED** — the paper describes the corpus but I could not confirm a public release |
| **Domain** | Chinese food and dietetics; passes the Chinese National Chef Exam (67.2%) and National Dietetic Exam (66.4%) |
| **Samples** | Corpus size not disclosed in the abstract |
| **Pediatric relevance** | **Not mentioned** |
| **Indian relevance** | **None** — explicitly Chinese-cuisine oriented |
| **Suitability for Qwen instruction tuning** | **Not usable** (availability unconfirmed, wrong cuisine and language) |
| **Paper** | Zhou, Min, Fu, Jin, Huang, Li, Mei & Jiang, *FoodSky: A Food-oriented Large Language Model that Passes the Chef and Dietetic Examination* — [arXiv:2406.10261](https://arxiv.org/abs/2406.10261) |
| **Why it matters anyway** | **This is the strongest piece of related work for the paper.** It demonstrates that domain-specific food/dietetics LLMs are a live research area, that a bespoke corpus had to be constructed because none existed, and that the resulting system is region-specific. It is the best available citation for the claim *"the equivalent resource for Indian pediatric nutrition does not exist"* — and it also introduces a hierarchical topic-based RAG mechanism (HTRAG), making it directly comparable related work for our Hybrid RAG design |

---

### 2.11 Minor / community datasets

| Name | Source | Assessment |
|---|---|---|
| UgandanNutritionMealPlanning | [HF](https://huggingface.co/datasets/Shakiran/UgandanNutritionMealPlanning) | Meal-planning examples with caregiver-facing nutritional explanations — **the closest format match found to our task**, but a small, unvetted community dataset for a different country's food system. Size and provenance **NOT VERIFIED** |
| openfoodfacts/nutrition-table-detection | [HF](https://huggingface.co/datasets/openfoodfacts/nutrition-table-detection) | Object detection on label images — wrong modality |
| HF `?other=nutrition` collection | [HF](https://huggingface.co/datasets?other=nutrition) | Browsed; no pediatric nutrition instruction dataset present |

---

## 3. Summary Table

| Dataset | Samples | Pediatric | Indian | Instruction-tunable for our task | Real value to this project |
|---|---|---|---|---|---|
| MedQA | 12,723 | Low | None | **No** (MCQ) | Low |
| MedMCQA | ~194,000 | Low–Mod | **High** | **No** (MCQ, license unclear) | Low |
| PubMedQA | 1,000 + 211k | Low | None | **No** (research register) | Low |
| NutritionQA | **50** | None | None | **No** (vision) | **None — name collision** |
| FoodBase | 1,000 / 21,790 recipes | None | Low | **No** (NER) | **NER training (report 01)** |
| USDA FDC | 600,000+ | Indirect | Low | **No** (tables) | **Expand `foods.json`** |
| **IFCT 2017** | 528 foods / 151 components | Indirect | **Highest** | **No** (tables) | **Expand `foods.json` — authoritative Indian basis** |
| **WHO/UNICEF IYCF** | 17 indicators | **Highest** | Good | **No** (guidelines) | **Expand RAG corpus, CC BY 3.0 IGO** |
| Open Food Facts | Millions | Low | Moderate | **No** | Low (ODbL share-alike) |
| FoodSky/FoodEarth | Undisclosed | Not stated | None | **No** (unavailable) | **Key related-work citation** |

**Not one row in this table is a suitable instruction-tuning corpus for our task.** Three rows are
valuable for *other* parts of the project — and that redirection is the practical output of this
survey.

---

## 4. Why the Gap Exists

Worth one paragraph in the paper, because it explains the finding rather than merely reporting it.

Pediatric nutrition guidance sits at an awkward intersection: it is **medical enough** that
authoritative content is produced by clinicians and health agencies as prose guidelines rather than
as structured QA, **consumer-facing enough** that most available text is low-quality web content
unsuitable for training, and **culturally specific enough** that a corpus built for one food system
transfers poorly to another. Add the liability concerns around child health advice, and there is
little incentive for anyone to publish an openly-licensed instruction corpus. FoodSky
([arXiv:2406.10261](https://arxiv.org/abs/2406.10261)) is instructive here: a well-resourced group
working on food LLMs had to **construct** their corpus (FoodEarth) because none existed, and did so
for Chinese cuisine only.

---

## 5. Fine-Tuning Methods — Full Space

**Framing:** compute requirements are reported as an **implementation consideration**, not as an
elimination criterion. Assume suitable cloud GPUs can be obtained. **The binding constraint in this
report is data availability (§2–§4, §5.4), not hardware.**

Status tags: `🔬 RESEARCH CANDIDATE` · `⚡ HIGH-COMPUTE OPTION` · `🖥️ REQUIRES ADDITIONAL GPU RESOURCES`
· `🔮 POTENTIAL FUTURE WORK`

### 5.1 Method comparison

| Method | Reference | Trainable params (7B) | Memory (approx) | Ideal hardware | Status |
|---|---|---|---|---|---|
| **Full fine-tuning** | — | 7.6 B | **~120–150 GB** (fp16 weights + grads + Adam states) | 2–8 × A100-80GB with FSDP/ZeRO-3 | `⚡` `🖥️` `🔬` |
| Full FT + ZeRO-3 offload | Rajbhandari et al., *ZeRO*, SC 2020 — [arXiv:1910.02054](https://arxiv.org/abs/1910.02054) | 7.6 B | fits smaller GPUs, much slower | 1–4 × A100-80GB | `⚡` `🔬` |
| **LoRA** | Hu et al., ICLR 2022 — [arXiv:2106.09685](https://arxiv.org/abs/2106.09685) | ~0.1–1% | ~35–60 GB at fp16/bf16 | 1 × A100-80GB, or 40 GB w/ checkpointing | `🔬` `🖥️` |
| **QLoRA** | Dettmers et al., NeurIPS 2023 — [arXiv:2305.14314](https://arxiv.org/abs/2305.14314) | ~0.1–1% over 4-bit base | **~10–16 GB** | 1 × 24 GB (A10G/L4/4090); runs on 16 GB with care | `🔬` **lowest cost** |
| **DoRA** (weight-decomposed LoRA) | Liu et al., ICML 2024 — [arXiv:2402.09353](https://arxiv.org/abs/2402.09353) | ~LoRA | ~LoRA | as LoRA | `🔬` |
| rsLoRA (rank-stabilised) | [arXiv:2312.03732](https://arxiv.org/abs/2312.03732) | ~LoRA | ~LoRA | as LoRA | `🔬` |
| Prefix / prompt tuning | Li & Liang, ACL 2021 — [arXiv:2101.00190](https://arxiv.org/abs/2101.00190) | <0.1% | low | 1 × 24 GB | `🔬` |
| (IA)³ | Liu et al., NeurIPS 2022 — [arXiv:2205.05638](https://arxiv.org/abs/2205.05638) | <0.05% | low | 1 × 24 GB | `🔬` |
| **DPO** (preference) | Rafailov et al., NeurIPS 2023 — [arXiv:2305.18290](https://arxiv.org/abs/2305.18290) | via LoRA | ~2× LoRA (ref model) | 1–2 × A100 | `🔮` needs preference pairs |
| ORPO (reference-free) | Hong et al. — [arXiv:2403.07691](https://arxiv.org/abs/2403.07691) | via LoRA | ~LoRA | 1 × A100 | `🔮` |
| RLHF / PPO | Ouyang et al., NeurIPS 2022 — [arXiv:2203.02155](https://arxiv.org/abs/2203.02155) | — | very high (4 models in memory) | multi-A100 | `⚡` `🔮` |
| **Continued pretraining** (domain-adaptive) | Gururangan et al., *Don't Stop Pretraining*, ACL 2020 — [arXiv:2004.10964](https://arxiv.org/abs/2004.10964) | 7.6 B | as full FT | multi-node, billions of tokens | `⚡` `🖥️` `🔮` |
| **Knowledge distillation** from a larger teacher | Hinton et al. — [arXiv:1503.02531](https://arxiv.org/abs/1503.02531) | varies | teacher + student | multi-A100 | `🔮` |

### 5.2 Which methods the data situation actually permits

Ranked by **data requirement**, which is our real constraint:

| Data needed | Methods | Do we have it? |
|---|---|---|
| ~200–1,000 labelled instruction pairs | QLoRA / LoRA / DoRA / prefix tuning | **No** — must be constructed (§8) |
| ~10k–100k instruction pairs | LoRA, full FT for meaningful domain gain | **No** |
| Preference pairs (chosen/rejected) | DPO, ORPO, RLHF | **No** |
| Billions of unlabelled domain tokens | Continued pretraining | **No** — our corpus is 558 records ≈ **75 k characters ≈ 19 k tokens** |
| Teacher model logits only | Distillation | **Yes** — the one method with no labelled-data dependency |

That last row is worth noting: **distillation is the only fine-tuning-family method whose data
requirement we can satisfy today**, because the teacher supplies the supervision. It is developed in
§8.3.

### 5.3 Continued pretraining — why it fails on volume, not on hardware

Domain-adaptive pretraining (Gururangan et al., ACL 2020 —
[arXiv:2004.10964](https://arxiv.org/abs/2004.10964)) is the textbook route to domain specialisation.
Its requirement is corpus **volume**.

```
Our entire RAG corpus: 558 records × ~134 chars ≈ 75,000 characters ≈ ~19,000 tokens
Typical DAPT corpus:   hundreds of millions to billions of tokens
Shortfall:             roughly 4-5 orders of magnitude
```

Even with the expansions recommended in §9 (IFCT 2017's 528 foods, WHO/UNICEF IYCF guidance), we
would add thousands of tokens, not billions. **This is a data-volume conclusion and would not change
if we had an H100 cluster.** Recorded here so the finding is not mistaken for a hardware limitation.

### 5.4 Is the available data actually sufficient? — direct answer

| Requirement | Available | Sufficient? |
|---|---|---|
| Public pediatric-nutrition instruction pairs | **0 found** (§2–§3) | **No** |
| Own labelled QA pairs | 49 benchmark cases (also our **test set** — unusable for training) | **No** |
| Own unlabelled domain text | ~19 k tokens | **No** — 4–5 orders of magnitude short for DAPT |
| Indian pediatric nutrition instruction data | **0 found** | **No** |
| Preference/comparison data | **0** | **No** |
| Expert (dietitian) validation capacity | **none — no doctor-in-the-loop** | **No** |
| Teacher-model supervision | Qwen2.5-7B + Groq-hosted larger models | **Yes** (§8.3) |

**Conclusion: the available data is not sufficient for knowledge-oriented fine-tuning by any method.**
It may be sufficient for the narrow *behavioural* objective in §8, and for distillation in §8.3.

---

## 6. Arguments Against Fine-Tuning For This Project

Beyond the data gap, four substantive arguments — all grounded in verified facts about this system:

**1. RAG already addresses the knowledge problem, and is more appropriate for safety.** Our 558-record
corpus can be **corrected, audited and versioned**; a fine-tuned weight update cannot. In a pediatric
health system, "we updated the guideline record and re-indexed" is a far better incident response than
"we retrained the model." Retrieval-based knowledge injection also lets the answer cite its source —
which is what makes our Faithfulness measurement meaningful at all. Lewis et al., NeurIPS 2020 —
[arXiv:2005.11401](https://arxiv.org/abs/2005.11401).

**2. Fine-tuning would break the current evaluation.** All existing results
(Faithfulness 0.9549, Answer Relevancy 0.7522, Hallucination Rate 9.09%) were produced with stock
Qwen2.5-7B-Instruct. A fine-tuned model invalidates every baseline and requires a full re-run — a
large cost for an unproven gain.

**3. The measured weaknesses are not in the model's knowledge.** The verified defects in
`00_CURRENT_ARCHITECTURE.md` §10 are: no query understanding (G1), dormant metadata filtering (G2),
a 4-keyword router (G3), degenerate chunking (G4), no safety validation (G5), an undefined safety
metric (G7). **Not one of these is fixed by fine-tuning.** Every one is fixed by the work in
reports 01, 02 and 05.

**4. Self-generated training data is a trap.** The obvious shortcut — have Qwen or a larger model
generate synthetic QA pairs from our 558 records, then train Qwen on them — risks amplifying the
model's existing errors and is not independent evidence of anything. Where the teacher is a model,
the student inherits its hallucinations. Related concern: Shumailov et al., *The Curse of Recursion /
model collapse* — [arXiv:2305.17493](https://arxiv.org/abs/2305.17493). If synthetic data is used at
all, it needs human validation, which returns us to the annotation-cost problem.

---

## 7. Conditions Under Which to Revisit This Conclusion

Stated in advance so the decision is not made ad hoc:

| Condition | Threshold |
|---|---|
| A suitable public corpus appears | ≥ 1,000 pediatric-nutrition instruction pairs, openly licensed, with pediatric and ideally Indian coverage |
| Manual corpus construction becomes viable | ≥ 500 expert-validated QA pairs; realistically needs a dietitian collaborator — the project currently has **no doctor-in-the-loop** |
| A specific, measured failure is traced to the model | E.g. the model consistently fails to follow the 4-section format or the refusal script *even with correct context retrieved* — a capability gap RAG cannot fix |
| Evaluation is strong enough to detect the effect | Current n = 41 with a permissive judge cannot reliably detect a small improvement (`05` §6). Fine-tuning without a trustworthy measurement is unfalsifiable |

**All four are currently unmet.** The fourth is worth emphasising: even a successful fine-tune could
not be *demonstrated* to be successful with the present evaluation set.

---

## 8. Alternative Research Directions (Given That No Suitable Dataset Exists)

The brief asks that, where no suitable dataset exists, **alternative research directions be explained
rather than an unsuitable dataset recommended**. Four are developed below. All are research
candidates; none is recommended as a default.

### 8.0 Summary of the four alternatives

| # | Direction | Data requirement | Status |
|---|---|---|---|
| 8.1 | **Behavioural** fine-tuning (format + refusal only) | 200–400 self-built pairs | `🔬 RESEARCH CANDIDATE` |
| 8.2 | **Synthetic instruction generation** (Self-Instruct / Evol-Instruct) | teacher model + our 558 records | `🔬` with a large validity caveat |
| 8.3 | **Knowledge distillation** from a stronger teacher | **teacher logits only — no labels** | `🔬` the only label-free route |
| 8.4 | **RAFT — retrieval-aware fine-tuning** | QA pairs over **our own documents** | `🔬` **best-aligned with this project's thesis** |

---

### 8.1 Behavioural fine-tuning — the narrowest defensible version `🔬`

**Do not fine-tune for knowledge. Fine-tune for *format and refusal compliance*.**

Rationale: format compliance and safety-refusal behaviour are **behavioural** properties, they are
**objectively checkable without a judge** (regex for the four required sections; exact-match for the
refusal script), and a small dataset suffices because the target behaviour is narrow and highly
patterned.

**Protocol**
1. **Data:** 200–400 pairs, built from our own 49 benchmark cases plus new questions, where the
   *input* is the real assembled prompt (profile + planner JSON + retrieved chunks) and the *output*
   is a **human-validated** correctly-formatted answer. Include ~50 medical-advice questions whose
   correct output is the exact refusal script from `llm/prompt_templates.py:8`.
2. **Method:** QLoRA on the existing 4-bit base ([arXiv:2305.14314](https://arxiv.org/abs/2305.14314)),
   rank 8–16.
3. **Split:** strict train/dev/test with **no** overlap with the 49 evaluation cases — otherwise the
   result is meaningless.
4. **Primary metrics (judge-free, objective):** section-format compliance rate; refusal-script exact
   compliance on medical queries; instruction-adherence ("did it recalculate calories when told not
   to?" — directly checkable against the planner JSON).
5. **Guardrail metrics:** Faithfulness, Answer Relevancy, Hallucination Rate must **not degrade**
   beyond the noise floor established in `05` Experiment A-E1.
6. **Report honestly**, including the possibility that prompt engineering achieves the same
   format compliance at zero training cost — which should be tested **first**, as the cheaper control.

**Training hyperparameters** (the section `05` deliberately deferred here): LoRA rank 8–16, α = 16–32,
dropout 0.05, target modules `q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj`, learning rate
1e-4 to 2e-4 with cosine decay, 2–3 epochs, effective batch size 8–16 via gradient accumulation,
`paged_adamw_8bit`. These are the QLoRA paper's conventional settings, not tuned values — and tuning
them at n = 400 would overfit.

**The honest framing for the report:** this is a *behavioural alignment* experiment, not a knowledge
injection experiment, and its most likely useful outcome is a negative one — *"prompt engineering
achieved equivalent format compliance without training."*

**Compute:** QLoRA on 400 samples ≈ **1 × 24 GB GPU, well under an hour**. Not a compute-limited
experiment at any point.

---

### 8.2 Synthetic instruction generation `🔬 — with a large validity caveat`

**What it does.** Use a strong teacher model to generate instruction-response pairs from our existing
558 RAG records, then train on them. Established recipes: **Self-Instruct** — Wang et al., ACL 2023 —
[arXiv:2212.10560](https://arxiv.org/abs/2212.10560); **Evol-Instruct / WizardLM** —
[arXiv:2304.12244](https://arxiv.org/abs/2304.12244); Stanford **Alpaca** —
[project page](https://crfm.stanford.edu/2023/03/13/alpaca.html).

**Why it could be useful for NutriBite.** It is the only way to manufacture instruction data at scale
from the corpus we already own, and each generated pair is at least *anchored* to a real record
rather than invented from nothing.

**Data / calibration.** Our 558 records + a teacher (Groq-hosted `openai/gpt-oss-120b`, already
wired up as `groq_judge`, or a larger frontier model).

**Compute.** Generation is API-bound, not GPU-bound. Training: QLoRA on 1–5 k pairs ≈
**1 × 24–40 GB, a few hours.**

**Experiments.** Generate 1–5 k pairs; human-validate a random 10% sample and **report the error rate
of the generator** — that number is itself a finding; train and compare against the untrained
baseline with the guardrail metrics from §8.1.

**Benefits and risks.** Benefit: breaks the data deadlock at low cost. **Risks, and they are
serious:** the student inherits the teacher's errors, and an error in pediatric nutrition guidance is
a safety issue, not a quality issue; training a model on its own family's output risks degenerate
self-reinforcement (Shumailov et al., *The Curse of Recursion* —
[arXiv:2305.17493](https://arxiv.org/abs/2305.17493)); and **evaluating the result with an LLM judge
from the same family closes a circularity loop** that must be disclosed. **Human validation is not
optional here** — which returns us to the missing dietitian.

---

### 8.3 Knowledge distillation `🔬 — the only label-free route` `🖥️`

**What it does.** Train a student to match a stronger teacher's output distribution rather than
human labels. Hinton, Vinyals & Dean — [arXiv:1503.02531](https://arxiv.org/abs/1503.02531);
sequence-level variant, Kim & Rush, EMNLP 2016 —
[arXiv:1606.07947](https://arxiv.org/abs/1606.07947). This is also the retraining mechanism used by
**Minitron** (`06_PRUNING_RESEARCH.md` §13).

**Why useful for NutriBite.** **It is the only fine-tuning-family method whose data requirement we
can already satisfy** (§5.2), because supervision comes from the teacher, not from annotation. Two
concrete framings: (a) distil a *larger* model's pediatric-nutrition behaviour into Qwen2.5-7B;
(b) distil Qwen2.5-7B into a **smaller** student for deployment — which merges directly with the
pruning programme, where distillation is the recovery step.

**Data / calibration.** Unlabelled prompts (ours plus generated variations) + teacher outputs. Full
logit distillation requires teacher logits, which **API-hosted teachers do not expose** — so in
practice this means sequence-level distillation on teacher *text*, which collapses into §8.2 and
inherits its caveats. A locally-run larger open teacher (e.g. Qwen2.5-32B/72B) would restore true
logit distillation. `🖥️`

**Compute.** Local teacher + student in memory: **2 × A100-80GB** for a 72B teacher, or
**1 × A100-80GB** for a 32B teacher at 4-bit. `⚡` for the larger variants.

**Experiments.** Distil Qwen2.5-32B/72B nutrition behaviour into 7B; measure whether the student
approaches the teacher on our benchmark; combine with §18 P1 layer pruning as the healing step.

**Benefits and risks.** Benefit: no labelled data needed; well-established; composes with pruning.
Risks: needs a *better* teacher than our current model to be worthwhile, and it is unverified that
any available open model is meaningfully better at **Indian pediatric nutrition** specifically;
text-only distillation inherits all of §8.2's risks.

---

### 8.4 RAFT — retrieval-aware fine-tuning `🔬 best-aligned with this project`

**What it does.** **RAFT (Retrieval-Augmented Fine-Tuning)** trains a model to perform well in the
*open-book, in-domain* setting: given a question plus a mixture of relevant documents **and
distractor documents**, the model learns to ignore the distractors and to **cite verbatim the
supporting span** from the relevant document. Zhang et al., *RAFT: Adapting Language Model to Domain
Specific RAG* — [arXiv:2403.10131](https://arxiv.org/abs/2403.10131) ·
[paper PDF](https://shishirpatil.github.io/publications/raft-2024.pdf).

Closely related: **Self-RAG**, which trains a model to adaptively retrieve and to critique its own
generations using special reflection tokens — Asai, Wu, Wang, Sil & Hajishirzi, ICLR 2024 —
[arXiv:2310.11511](https://arxiv.org/abs/2310.11511) ·
[ICLR proceedings](https://proceedings.iclr.cc/paper_files/paper/2024/file/25f7be9694d7b32d5cc670927b8091e1-Paper-Conference.pdf).

**Why useful for NutriBite — the strongest fine-tuning argument in this report.** RAFT is not about
injecting knowledge; it is about **teaching the model to use retrieved context correctly**. That is
*exactly* the project's stated thesis — grounding, faithfulness, hallucination reduction. And it maps
onto a verified property of our pipeline: our retriever returns **top-5** chunks after
fusion + reranking, and **not all five are relevant** — the reranker orders them, it does not
guarantee them. Distractor documents are therefore not hypothetical for us; they are in every prompt
we send. RAFT's verbatim-citation objective also aligns with our `[ID: …, Relevance Score: …]` chunk
formatting, which already primes citation-style grounding.

Self-RAG's critique tokens are likewise attractive for a safety-sensitive system: a model that can
signal *"the retrieved context does not support an answer"* is directly useful where our current
prompt can only *ask* for that behaviour.

**Data / calibration.** QA pairs **over our own documents**, with deliberately mixed relevant and
distractor chunks. Distractors are free — sample them from the other 557 records. The questions and
reference answers still need to exist, so this **does not escape the annotation requirement**, but it
reduces it: the supervision signal is "use this chunk, ignore that one", which is cheaper to
construct and verify than authoring full clinical answers.

**Compute.** QLoRA-scale: **1 × 40–80 GB A100** for a few hours on a few thousand examples. `🖥️`

**Experiments.** Build 500–2,000 RAFT-style examples from our corpus; train with QLoRA; evaluate
with the **existing** Faithfulness / Hallucination / Context Recall metrics — no new metric
infrastructure needed; ablate the distractor ratio; test specifically whether the model's behaviour
improves when the retriever returns **poor** context, which is the failure mode that matters most.

**Benefits and risks.** Benefits: thesis-aligned; uses data we own; measurable with the existing
harness; addresses a verified pipeline property rather than a hypothetical one. Risks: still needs
question/answer authoring; risks **over-fitting to our retriever's specific output distribution**, so
a retriever change could invalidate it; and the 49-case benchmark is far too small to both train and
evaluate, making evaluation-set expansion (roadmap R11) a hard prerequisite.

---

## 9. Recommendation

**Do not fine-tune *for knowledge*.** The condition set by the brief — *"only if suitable public
datasets exist"* — is **not met**. No public pediatric-nutrition instruction-tuning dataset was
found, and the substitutes are format-mismatched, domain-mismatched, or the wrong task entirely.
This is a **data-availability** conclusion; it would not change with more GPUs.

**If a fine-tuning research contribution is nevertheless required**, the ranked candidates are:

| Rank | Direction | Why | Compute |
|---|---|---|---|
| 1 | **RAFT — retrieval-aware fine-tuning (§8.4)** | Thesis-aligned (grounding, not knowledge); uses documents we own; distractors are free; measurable with existing metrics | 1 × 40–80 GB A100, hours |
| 2 | **Behavioural fine-tuning (§8.1)** | Objectively checkable without a judge; smallest data requirement | 1 × 24 GB, < 1 hour |
| 3 | **Distillation (§8.3)** | Only genuinely label-free route; composes with pruning recovery | 1–2 × A100-80GB |
| 4 | **Synthetic instruction data (§8.2)** | Breaks the deadlock, but inherits teacher errors and creates evaluation circularity | API + 1 × 24–40 GB |

**Hard prerequisite for all four:** the evaluation set must be expanded (roadmap R11). With 49 cases
serving as the test set, there is no honest way to both train and evaluate.

**Redirect the effort as follows**, in priority order:

1. **Expand `foods.json` from IFCT 2017** (528 Indian foods, 151 components) — turns our 99-item food
   table into something grounded in the authoritative Indian national reference. High value, no
   model training, and a strong claim for the paper. *Clarify redistribution terms first.*
2. **Expand `rag_data.json` with WHO/UNICEF IYCF guideline content** — properly licensed
   (CC BY 3.0 IGO), authoritative, and squarely in the 0–23 month band where guidance matters most.
   Also directly addresses the degenerate-chunking finding (`00` §3.2) by adding longer records.
3. **Use FoodBase for NER**, not for fine-tuning (report 01).
4. **Cite FoodSky as related work** and as evidence for the gap claim.
5. **Build the evaluation set out** — more cases, and critically some `Violation` safety labels —
   before any training is contemplated, because otherwise no training result can be verified.

Steps 1, 2 and 5 improve the system measurably, require no GPU training, and carry none of
fine-tuning's risks.

---

## 10. Sources

- Jin et al., *MedQA / What Disease Does This Patient Have?* — [arXiv:2009.13081](https://arxiv.org/abs/2009.13081) · [DOI 10.3390/app11146421](https://doi.org/10.3390/app11146421)
- Pal, Umapathi & Sankarasubbu, *MedMCQA*, CHIL 2022 — [PMLR v174](https://proceedings.mlr.press/v174/pal22a.html) · [arXiv:2203.14371](https://arxiv.org/abs/2203.14371)
- Jin et al., *PubMedQA*, EMNLP-IJCNLP 2019 — [arXiv:1909.06146](https://arxiv.org/abs/1909.06146) · [ACL D19-1259](https://aclanthology.org/D19-1259/)
- Popovski & Koroušić Seljak, *FoodBase corpus*, Database (Oxford) 2019 — [PMC6827550](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6827550/)
- Zhou et al., *FoodSky* — [arXiv:2406.10261](https://arxiv.org/abs/2406.10261)
- USDA FoodData Central — [fdc.nal.usda.gov](https://fdc.nal.usda.gov/)
- ICMR-NIN, *Indian Food Composition Tables 2017* — [nin.res.in/ebooks/IFCT2017.pdf](https://www.nin.res.in/ebooks/IFCT2017.pdf) · [FAO INFOODS](https://www.fao.org/food-composition/tables-and-databases/detail/(country--date)-title-9/en)
- *Development of an Indian Food Composition Database (INDB)* — [PMC11277795](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11277795/)
- WHO/UNICEF, *IYCF indicators*, 2021 — [WHO 9789240018389](https://www.who.int/publications/i/item/9789240018389) · [UNICEF data](https://data.unicef.org/topic/nutrition/infant-and-young-child-feeding/)
- Open Food Facts — [world.openfoodfacts.org/data](https://world.openfoodfacts.org/data)
**Fine-tuning methods**
- Hu et al., *LoRA*, ICLR 2022 — [arXiv:2106.09685](https://arxiv.org/abs/2106.09685)
- Dettmers et al., *QLoRA*, NeurIPS 2023 — [arXiv:2305.14314](https://arxiv.org/abs/2305.14314)
- Liu et al., *DoRA*, ICML 2024 — [arXiv:2402.09353](https://arxiv.org/abs/2402.09353)
- *rsLoRA* — [arXiv:2312.03732](https://arxiv.org/abs/2312.03732)
- Li & Liang, *Prefix-Tuning*, ACL 2021 — [arXiv:2101.00190](https://arxiv.org/abs/2101.00190)
- Liu et al., *(IA)³ / Few-Shot PEFT*, NeurIPS 2022 — [arXiv:2205.05638](https://arxiv.org/abs/2205.05638)
- Rafailov et al., *Direct Preference Optimization*, NeurIPS 2023 — [arXiv:2305.18290](https://arxiv.org/abs/2305.18290)
- Hong et al., *ORPO* — [arXiv:2403.07691](https://arxiv.org/abs/2403.07691)
- Ouyang et al., *InstructGPT / RLHF*, NeurIPS 2022 — [arXiv:2203.02155](https://arxiv.org/abs/2203.02155)
- Rajbhandari et al., *ZeRO*, SC 2020 — [arXiv:1910.02054](https://arxiv.org/abs/1910.02054)
- Gururangan et al., *Don't Stop Pretraining*, ACL 2020 — [arXiv:2004.10964](https://arxiv.org/abs/2004.10964)

**Alternative directions**
- Zhang et al., *RAFT: Adapting Language Model to Domain Specific RAG* — [arXiv:2403.10131](https://arxiv.org/abs/2403.10131) · [PDF](https://shishirpatil.github.io/publications/raft-2024.pdf)
- Asai et al., *Self-RAG*, ICLR 2024 — [arXiv:2310.11511](https://arxiv.org/abs/2310.11511)
- Wang et al., *Self-Instruct*, ACL 2023 — [arXiv:2212.10560](https://arxiv.org/abs/2212.10560)
- Xu et al., *WizardLM / Evol-Instruct* — [arXiv:2304.12244](https://arxiv.org/abs/2304.12244)
- Stanford *Alpaca* — [project page](https://crfm.stanford.edu/2023/03/13/alpaca.html)
- Hinton, Vinyals & Dean, *Knowledge Distillation* — [arXiv:1503.02531](https://arxiv.org/abs/1503.02531)
- Kim & Rush, *Sequence-Level Knowledge Distillation*, EMNLP 2016 — [arXiv:1606.07947](https://arxiv.org/abs/1606.07947)
- Lewis et al., *RAG*, NeurIPS 2020 — [arXiv:2005.11401](https://arxiv.org/abs/2005.11401)
- Shumailov et al., *The Curse of Recursion (model collapse)* — [arXiv:2305.17493](https://arxiv.org/abs/2305.17493)
