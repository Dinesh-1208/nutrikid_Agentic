# 01 — Named Entity Recognition for KidsNutriBite

**Research question:** *Would extracting structured entities from a parent's free-text nutrition
question measurably improve KidsNutriBite's retrieval, generation, safety and routing?*

**Stance of this report.** I do **not** assume NER improves performance. NER adds a component that
can fail, adds latency, and adds a new error-propagation path (a wrong entity is worse than no
entity). §8 therefore specifies experiments whose *possible outcome is that NER does not help*, and
§9 states in advance what result would mean "abandon this direction".

---

## 1. What NER Is

Named Entity Recognition is the task of locating spans in text and classifying them into predefined
types. Formally it is sequence labelling, conventionally with BIO tagging (Ramshaw & Marcus,
*Text Chunking using Transformation-Based Learning*, 1995 —
[arXiv:cmp-lg/9505040](https://arxiv.org/abs/cmp-lg/9505040)). The modern benchmark framing comes
from CoNLL-2003 (Tjong Kim Sang & De Meulder —
[ACL Anthology W03-0419](https://aclanthology.org/W03-0419/)), and the neural formulation from
Lample et al., *Neural Architectures for Named Entity Recognition*, NAACL 2016 —
[arXiv:1603.01360](https://arxiv.org/abs/1603.01360).

Example on a query this system would actually receive:

```
"My 4 year old has iron deficiency anemia and is allergic to peanuts —
 what should I give for breakfast, about 2 cups of milk a day ok?"

  4 year old               -> AGE          (normalised: 4.0 years)
  iron deficiency anemia   -> CONDITION    (linked: conditions.json)
  peanuts                  -> ALLERGEN     (linked: allergies.json)
  breakfast                -> MEAL_SLOT
  2                        -> QUANTITY
  cups                     -> UNIT
  milk                     -> FOOD         (linked: foods.json)
  iron                     -> NUTRIENT
```

**The key point for this project:** the current system extracts **none** of this. `main.py:86-92`
builds the child profile purely from CLI flags and falls back to hardcoded constants
(`age=7.0, weight=20.0, condition="healthy_growth", goal="balanced_nutrition"`). A parent who types
the sentence above gets a plan for a **7-year-old with no allergies**. That is the concrete, verified
motivation for this report — not a hypothetical one.

---

## 2. Proposed Entity Schema for Pediatric Nutrition

The schema below is derived from what the repository actually contains and consumes, so that every
entity type has a real downstream use. Types with no consumer are marked as such.

| # | Entity type | Definition | Example spans | Grounding in this repo | Downstream consumer |
|---|---|---|---|---|---|
| 1 | `AGE` | Child's age, any surface form | "4 year old", "18 months", "toddler", "school-going" | `dataset.py` has 17 distinct free-text `age_group` strings | Planner (`profile["age"]`), retrieval filter, safety rubric |
| 2 | `FOOD` | An edible item or dish | "ragi", "milk", "khichdi", "apple" | `foods.json` — **99 named foods** = ready-made gazetteer | Planner food selection, retrieval |
| 3 | `NUTRIENT` | A nutrient or micronutrient | "iron", "protein", "vitamin D", "fibre" | `foods.json` keys: `protein_g`, `iron_mg`, `carbs_g`, `fat_g` | Retrieval, answer targeting |
| 4 | `ALLERGEN` | Substance the child must avoid | "peanuts", "milk", "gluten", "egg" | `allergies.json` — **15 entries with exclusion tags** | **Safety** (planner exclusion + post-hoc validation) |
| 5 | `CONDITION` | Clinical / nutritional condition | "anemia", "underweight", "diarrhoea", "stunting" | `conditions.json` — **173 entries**; 94 RAG records carry a `condition` key | Planner multiplier, metadata filter |
| 6 | `GOAL` | Nutrition objective | "gain weight", "improve immunity", "grow taller" | `goals.json` — **148 entries**; 13 RAG records carry a `goal` key | Planner ±kcal, metadata filter |
| 7 | `QUANTITY` | A numeric amount | "2", "half", "250" | `portion_size_g` in planner output | Portion reasoning, unit validation |
| 8 | `UNIT` | Measurement unit | "cups", "g", "ml", "katori", "tbsp" | planner emits `g`, `kcal`, `mg` | Normalisation, unit-conversion checking |
| 9 | `MEAL_SLOT` | Which meal | "breakfast", "lunch", "dinner", "snack", "tiffin" | planner's exact four keys | **Routing**, targeted plan responses |
| 10 | `DIET_PATTERN` | Dietary regime | "vegetarian", "vegan", "Jain", "eggetarian" | `tags` field (888 distinct tags) | Food filtering |
| 11 | `ANTHROPOMETRIC` | Body measurement | "12 kg", "95 cm", "BMI 14" | `profile["weight"]` | Planner (removes the 20.0 kg default) |
| 12 | `FREQUENCY` / `DURATION` | Temporal pattern | "twice a day", "for 3 weeks", "daily" | — **no consumer today** | Future: adherence, escalation triggers |
| 13 | `SYMPTOM` | Reported symptom | "not eating", "vomiting", "loose motions" | — **no consumer today** | Future: **safety escalation** (refer to doctor) |
| 14 | `MEDICATION` | Drug mention | "iron syrup", "albendazole" | — **no consumer today** | **Safety**: hard trigger for the refusal script |

**Recommended scope for a final-year project:** implement types **1–11** (all have a real consumer).
Treat 12–14 as annotation-only for now; 13 and 14 become valuable the moment a safety-escalation
policy exists.

### 2.1 Entity *linking* matters more than entity *recognition* here

Detecting the span "anemia" is not useful on its own. What the pipeline needs is the **canonical key**
that matches `conditions.json`. So the real task is NER **+ normalisation/linking**:

```
"my kid is anaemic"  ->  CONDITION span "anaemic"  ->  linked id "iron_deficiency_anemia"
"18 months"          ->  AGE span                  ->  normalised 1.5 (years, float)
"2 cups of milk"     ->  QUANTITY+UNIT+FOOD        ->  ~480 ml milk
```

This normalisation layer is where most of the practical value — and most of the engineering risk —
lives. It is covered in detail in `02_FEATURE_ENGINEERING_RESEARCH.md`.

---

## 3. Approach A — Rule-Based / Gazetteer NER

### How it works
Dictionary matching against a controlled vocabulary, plus regular expressions for numeric patterns
(age, quantity, unit). Efficient multi-pattern matching uses Aho–Corasick
(Aho & Corasick, CACM 18(6), 1975 — [DOI 10.1145/360825.360855](https://doi.org/10.1145/360825.360855)),
available in spaCy as the `EntityRuler` / `PhraseMatcher`
([spaCy EntityRuler docs](https://spacy.io/api/entityruler)).

### Why it is unusually strong *for this specific project*
The repository **already contains the gazetteers**, for free:

| Source file | Entries | Becomes gazetteer for |
|---|---|---|
| `data/db/foods.json` | 99 | `FOOD` |
| `data/db/conditions.json` | 173 | `CONDITION` |
| `data/db/goals.json` | 148 | `GOAL` |
| `data/db/allergies.json` | 15 | `ALLERGEN` |
| RAG metadata `tags` | 888 distinct | `DIET_PATTERN`, `NUTRIENT` |

That is ~435 curated domain terms plus 888 tags with **zero annotation effort**, and — critically —
each match already *is* the canonical key the downstream services expect. Gazetteer NER solves
recognition and linking in one step.

`AGE`, `QUANTITY`, `UNIT` and `ANTHROPOMETRIC` are numeric-pattern entities; regex handles them with
very high precision (`(\d+)\s*(year|yr|month|mo)s?\s*(old)?`, `(\d+(\.\d+)?)\s*(kg|kgs|kilo)`).

### Strengths
- **Zero training data required** — decisive, given §7 of `07_FINETUNING_FEASIBILITY_RESEARCH.md`
  (no suitable public pediatric-nutrition annotation set exists).
- Deterministic, inspectable, debuggable — appropriate for a safety-sensitive system.
- Near-zero latency (microseconds) and no GPU.
- Recognition and linking collapse into one lookup.
- An examiner can read the rule file and verify it.

### Weaknesses
- **No generalisation.** "ragi" is in `foods.json`; "finger millet", "nachni" and "mandua" are not,
  unless aliases are curated.
- Misspellings fail ("anemia" vs "anaemia" vs "anemya"). Mitigable with fuzzy matching
  (e.g. `rapidfuzz`) at a precision cost.
- Ambiguity is unresolved: "milk" is simultaneously a `FOOD` and an `ALLERGEN`; "cold" is a symptom
  and an adjective.
- Multi-word/nested spans need care ("iron deficiency anemia" contains "iron" → `NUTRIENT`).
- Maintenance burden grows with vocabulary.

### Verdict for this project
**This is the correct baseline and very likely the correct production choice.** It should be the
first thing built, and every other approach must beat it to justify its cost.

---

## 4. Approach B — Pretrained Transformer NER (General Domain)

### How it works
A pretrained encoder (BERT-family) with a token-classification head, fine-tuned on a general NER
corpus. Foundation: Devlin et al., *BERT*, NAACL 2019 —
[arXiv:1810.04805](https://arxiv.org/abs/1810.04805); Lample et al. (above) for the architecture.

### Off-the-shelf options
- **spaCy `en_core_web_trf` / `en_core_web_sm`** — [spaCy models](https://spacy.io/models/en).
  Types: `PERSON, ORG, GPE, DATE, CARDINAL, QUANTITY, ...`
- **`dslim/bert-base-NER`** — CoNLL-2003 types —
  [model card](https://huggingface.co/dslim/bert-base-NER).

### Assessment for KidsNutriBite
A general NER model has **no label for FOOD, NUTRIENT, ALLERGEN, CONDITION or GOAL**. Out of our
14-type schema it can supply only:
- `DATE` / `CARDINAL` → partially useful for `AGE`, `QUANTITY`
- `QUANTITY` → partially useful for `ANTHROPOMETRIC`

Everything that matters for nutrition safety is missing. Using it unchanged would be a mis-fit; using
it means **fine-tuning it on our own annotated data**, which returns us to the annotation-cost
problem.

### Verdict
**Not recommended as-is.** Its only defensible role is as a *numeric/temporal* extractor alongside
the gazetteer, and even there regex is simpler and more precise for our patterns.

---

## 5. Approach C — Biomedical / Clinical NER

### Options

| Tool | Entity types | Training corpus | Source |
|---|---|---|---|
| **scispaCy** (`en_ner_bc5cdr_md`) | `DISEASE`, `CHEMICAL` | BC5CDR | Neumann et al., BioNLP 2019 — [arXiv:1902.07669](https://arxiv.org/abs/1902.07669); [allenai/scispacy](https://github.com/allenai/scispacy) |
| **scispaCy** (`en_ner_bionlp13cg_md`) | 16 types incl. `ORGANISM`, `TISSUE` | BioNLP13CG | same |
| **BioBERT** | biomedical NER backbone | PubMed + PMC | Lee et al., *Bioinformatics* 36(4):1234–1240, 2020 — [DOI 10.1093/bioinformatics/btz682](https://doi.org/10.1093/bioinformatics/btz682) |
| **PubMedBERT** | biomedical NER backbone | PubMed from scratch | Gu et al., ACM TCHI 2021 — [arXiv:2007.15779](https://arxiv.org/abs/2007.15779) |
| **Med7** | 7 clinical *medication* types (drug, dosage, route, frequency, duration, strength, form) | MIMIC-III | Kormilitzin et al. — [arXiv:2003.01271](https://arxiv.org/abs/2003.01271) |
| **FoodBase / FoodNER** | **`FOOD`** | recipe corpus | Popovski & Koroušić Seljak, *Database* (Oxford) 2019 — [PMC6827550](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6827550/), [PubMed 31682732](https://pubmed.ncbi.nlm.nih.gov/31682732/) |

**FoodBase** is the single most relevant public resource for `FOOD`:
- Gold standard: **1,000 recipes, 12,844 annotations, 2,105 unique entities**
- Weakly-annotated: **21,790 recipes, 274,053 annotations, 13,079 unique entities**

### Assessment
- `CONDITION` ← scispaCy `DISEASE` is a **genuine fit**. "iron deficiency anemia", "malnutrition",
  "diarrhoea" are exactly BC5CDR's domain.
- `MEDICATION` ← Med7 or scispaCy `CHEMICAL` is a genuine fit, and would be a strong safety trigger.
- `FOOD` ← FoodBase-trained models exist, but the corpus is **recipe English** (Western recipe
  vocabulary). Indian pediatric staples (ragi, khichdi, upma, poha, dalia, sattu) are unlikely to be
  well covered. **NOT VERIFIED FROM SOURCE** — I did not measure FoodBase's coverage of Indian food
  terms; this should be measured before relying on it.
- `NUTRIENT`, `GOAL`, `ALLERGEN`, `AGE`, `MEAL_SLOT` — **no clinical model provides these**.

### Cost
scispaCy models are hundreds of MB and add real per-query latency on CPU; they are additional heavy
dependencies in a project already loading a 7B LLM, a bi-encoder and a cross-encoder.

### Verdict
**Recommended narrowly.** Use scispaCy `en_ner_bc5cdr_md` as a *recall booster for `CONDITION` only*,
layered over the gazetteer, and evaluate whether that recall gain survives the latency cost. Do not
adopt it for `FOOD`.

---

## 6. Approach D — Zero-Shot / LLM-Based Structured Extraction

### D1. GLiNER
A compact bidirectional encoder that performs **open-type** NER: entity types are supplied at
inference time as natural-language labels. Zaratiana, Tomeh, Holat & Charnois, *GLiNER: Generalist
Model for NER using Bidirectional Transformer*, NAACL 2024 —
[arXiv:2311.08526](https://arxiv.org/abs/2311.08526),
[ACL Anthology 2024.naacl-long.300](https://aclanthology.org/2024.naacl-long.300/).

Directly usable: pass our 14 type names as labels, no training. Model sizes ~
`gliner_small`/`medium`/`large` ([urchade/gliner_medium-v2.1](https://huggingface.co/urchade/gliner_medium-v2.1)).
This is the **best fit among zero-shot options** — small, fast relative to an LLM, and schema-flexible.

### D2. UniversalNER
Targeted distillation from ChatGPT into a smaller open NER model. Zhou et al., ICLR 2024 —
[arXiv:2308.03279](https://arxiv.org/abs/2308.03279). Reports outperforming general instruction-tuned
models (Alpaca, Vicuna) by >30 absolute F1 on average, across a 43-dataset / 9-domain benchmark.
Larger and heavier than GLiNER.

### D3. Use Qwen2.5-7B itself (JSON-schema extraction)
The system already loads Qwen2.5-7B-Instruct. A second, short call could extract the schema directly:

```
System: You are an information extraction system. Extract entities as JSON.
        Output ONLY valid JSON matching the given schema. Use null for absent fields.
User:   {the parent's question}
```

**Strengths:** zero new dependencies, zero new model downloads, handles paraphrase and colloquial
Indian-English ("my kid is 4 saal ka"), and can perform normalisation (age → float) in the same pass.

**Weaknesses — all material:**
- **Latency doubles.** A 7B model at 4-bit is already the pipeline bottleneck. Two calls per query
  roughly doubles end-to-end time. This must be *measured*, not assumed acceptable.
- **The extractor can hallucinate.** An invented allergen or age is a *safety* failure, not just a
  quality failure. Requires strict JSON-schema validation and a rejection path.
- **Non-determinism.** Even at `temperature=0.1` the output is not guaranteed stable.
- **Circularity risk in evaluation:** if Qwen extracts entities *and* generates the answer *and* a
  sibling LLM judges it, the evaluation becomes partly self-referential. Must be disclosed.

Structured-output tooling that reduces the JSON-validity risk:
[Outlines](https://github.com/dottxt-ai/outlines) (Willard & Louf, *Efficient Guided Generation for
LLMs* — [arXiv:2307.09702](https://arxiv.org/abs/2307.09702)), and constrained decoding via
`transformers`' logits processors.

### Verdict
**GLiNER is the strongest research comparison** (cheap, open-type, citable, NAACL 2024).
**Qwen-based extraction is the strongest engineering fallback** if GLiNER underperforms on our
Indian-food vocabulary — but only with schema validation and a measured latency budget.

---

## 7. Comparison Table

| Criterion | A. Rule/Gazetteer | B. General transformer | C. Biomedical NER | D1. GLiNER | D3. Qwen extraction |
|---|---|---|---|---|---|
| Training data needed | **None** | Yes (fine-tune) | None (pretrained) | **None** | **None** |
| Covers `FOOD` | **Yes** (99 curated) | No | Partial (FoodBase) | Yes (zero-shot) | Yes |
| Covers `CONDITION` | **Yes** (173 curated) | No | **Yes** (BC5CDR) | Yes | Yes |
| Covers `ALLERGEN` | **Yes** (15 curated) | No | No | Yes | Yes |
| Covers `AGE`/`QUANTITY` | **Yes** (regex) | Partial | No | Yes | Yes |
| Covers `GOAL`/`MEAL_SLOT` | **Yes** | No | No | Yes | Yes |
| Handles unseen synonyms | **No** | Yes | Yes | Yes | **Yes** |
| Handles misspellings | Weak | Yes | Yes | Yes | **Yes** |
| Gives canonical DB key directly | **Yes** | No | No | No | With prompting |
| Added latency | ~0 ms | ~10–50 ms | ~50–200 ms | ~20–100 ms | **~1–5 s** |
| New heavy dependency | No | Yes | Yes | Yes | **No** (reuses Qwen) |
| Can hallucinate entities | **No** | No | No | No | **Yes** |
| Deterministic | **Yes** | Yes | Yes | Yes | **No** |
| Auditability for a safety system | **Highest** | Medium | Medium | Low | **Lowest** |

*(Latency figures are order-of-magnitude expectations from model size, **not measured on this
hardware — NOT VERIFIED**. Measuring them is Experiment E0 in §8.)*

---

## 8. Where NER Would Plug Into the Existing Pipeline

Six concrete integration points, each tied to verified code.

### 8.1 Retrieval — **activate the dormant metadata filter**
`main.py:99` calls `retriever.retrieve(args.ask, top_k=5)` with no filters, and
`MetadataFilterService` therefore never runs (`00_CURRENT_ARCHITECTURE.md` §4.3). NER supplies the
missing argument:

```
NER -> {"condition": "iron_deficiency_anemia", "goal": "weight_gain"}
     -> retriever.retrieve(query, top_k=5, filters=<that dict>)
```

94 RAG records carry a `condition` key and 13 carry `goal`, so this filter has real signal to act on.
**Caveat:** filtering a 558-record corpus to a 94-record subset risks over-filtering into empty
results. Any implementation needs a fallback-to-unfiltered path, and the experiment must measure
whether filtering *helps or hurts* Recall@5.

### 8.2 Prompting — replace hardcoded profile defaults
`generate_qa_prompt` and `generate_llm_prompt` both render a `### Child Profile:` block from the
profile dict. Today that block frequently contains fabricated defaults (age 7.0, weight 20.0).
NER-extracted values would make that block *true*, which is a correctness fix, not just an
enhancement.

### 8.3 Structured memory (multi-turn)
The CLI is single-shot today. An entity store keyed by extracted `AGE`, `ALLERGEN`, `CONDITION`
would let a future conversational interface carry the child profile across turns without re-asking.
**Out of scope for the current architecture** — list as future work, not as an experiment.

### 8.4 Safety validation — **currently missing entirely**
There is no post-generation check that the answer respects the child's allergies. The prompt asks
the model to respect them (`prompt_templates.py:13-15`), but nothing verifies it. A concrete,
deterministic validator:

```
extracted_allergens = NER(user_query) ∪ profile.allergies
foods_in_answer     = NER(generated_answer)          # FOOD entities
violation           = any(food maps to an excluded tag of any extracted allergen)
```

This is a **rule-based safety net independent of the LLM**, which is exactly the right architecture
for a safety check. It is arguably the highest-value application of NER in this project, and it does
not depend on NER improving retrieval at all.

> Note the evaluation constraint: with **zero `Violation`-labelled cases** in `dataset.py`, this
> validator cannot currently be scored. Building adversarial allergen cases is a prerequisite
> (see §8.5 of the roadmap).

### 8.5 Personalisation
`ANTHROPOMETRIC` and `AGE` extraction removes the `age=7.0, weight=20.0` fallback, which directly
changes the Holliday–Segar calorie target. This is measurable *without any LLM*: compare planner
output for a query stating an age against the default-driven output.

### 8.6 Agent routing — replace the 4-keyword test
Current rule: `any(kw in query.lower() for kw in ["plan","diet","meal","menu"])`.

NER-based rule: route to the planner when the query contains a `MEAL_SLOT` **or** a `GOAL` entity
**and** an `AGE` entity; route to QA otherwise. This is testable on the existing 49 questions by
hand-labelling the correct route.

---

## 9. Proposed Experiments (Baseline vs NER-Enhanced)

All experiments reuse the **existing** harness (`evaluation/evaluator.py`, the 49-case dataset, the
`openai/gpt-oss-120b` judge). No new metric infrastructure is required for E1–E3.

### E0 — NER component evaluation (must come first)
**This is a prerequisite.** If NER itself is inaccurate, no downstream experiment is interpretable.

- **Data:** annotate the **49 existing benchmark questions** with gold entity spans (+ ideally 100–150
  additional realistic parent questions). Two annotators; report **Cohen's κ**
  (Cohen, 1960 — [DOI 10.1177/001316446002000104](https://doi.org/10.1177/001316446002000104)).
- **Metrics:** per-type Precision / Recall / F1 under **exact-span** and **relaxed (overlap)**
  matching, following the CoNLL-2003 protocol
  ([W03-0419](https://aclanthology.org/W03-0419/)); plus **linking accuracy** (fraction of correctly
  resolved canonical keys) and **median latency in ms**.
- **Systems:** A (gazetteer+regex), C (scispaCy for `CONDITION` only), D1 (GLiNER), D3 (Qwen JSON).
- **Report:** a per-type table. Expect gazetteer to win precision and lose recall — that is the
  interesting result, not a failure.

### E1 — Retrieval with vs without NER-derived metadata filters
- **Condition A (baseline):** `retrieve(q, top_k=5)` — exactly today's behaviour.
- **Condition B:** `retrieve(q, top_k=5, filters=NER(q))`.
- **Condition C (ceiling):** filters from the **gold** `profile`/`age_group` fields already in
  `dataset.py` — this isolates *"would perfect extraction help?"* from *"is our extractor good
  enough?"*. **Running C first is the cheap decisive test: if gold filters do not help, NER cannot.**
- **Metrics:** Recall@5, Precision@5, MAP@5, MRR@5 (all already implemented), plus **empty-result
  rate** and **median retrieval latency**.
- **Data:** the 41 RAG-applicable cases.
- **Control:** set `enable_cache = False` so cache hits cannot confound.

### E2 — Generation quality with vs without NER-populated profile
- **Condition A:** hardcoded default profile (today).
- **Condition B:** NER-extracted profile.
- **Condition C:** gold `profile` from `dataset.py` (22 cases have one) — ceiling.
- **Metrics:** Faithfulness, Answer Relevancy, Hallucination Rate (existing judges), plus
  **profile-accuracy** — does the answer state the *correct* age/allergy?
- **Caveat that must be stated:** the current `GroundingJudge` prompt is deliberately permissive
  ("Be GENEROUS with `is_supported: true`"), so Faithfulness is an **upper bound**. Differences of a
  few points between conditions are not meaningful under that judge.

### E3 — Routing accuracy
- Hand-label the correct route (`planner` vs `qa`) for all 49 questions + ~50 adversarial ones
  ("Is a **meal** replacement shake safe?" → should be `qa`).
- Compare keyword rule vs NER rule.
- **Metrics:** routing accuracy, and separately the **false-planner-invocation rate** (the expensive
  error).
- This is the **cheapest experiment in the whole report** — no LLM calls needed — and the one most
  likely to show a clear win.

### E4 — Allergen safety validation
- Build an adversarial set: queries declaring an allergen where the corpus contains tempting
  recommendations of that allergen.
- **Metrics:** violation-detection Recall (the safety-critical direction), Precision, and
  **false-alarm rate** on the 20 `Compliant` cases.
- **Prerequisite:** this set does not exist yet; creating it is itself a contribution.

### 9.1 Statistical discipline (applies to all of E1–E4)
With **n = 41–49**, point differences are unreliable. Every comparison must report:
- **Paired** comparison on the same cases (same question through both configurations).
- **Bootstrap 95% confidence intervals** (Efron, 1979 —
  [DOI 10.1214/aos/1176344552](https://doi.org/10.1214/aos/1176344552)), and/or
- a **paired randomisation / permutation test**, which is the standard recommendation for IR
  evaluation — Smucker, Allan & Carterette, CIKM 2007 —
  [DOI 10.1145/1321440.1321528](https://doi.org/10.1145/1321440.1321528).
- Since E1–E4 test multiple hypotheses, apply a correction (Holm, 1979 —
  [JSTOR 4615733](https://www.jstor.org/stable/4615733)) or state clearly that the study is
  **exploratory, not confirmatory**. For a B.Tech project, "exploratory with CIs reported" is honest
  and defensible; claiming significance at n=41 without a test is not.

---

## 10. Decision Rules Stated In Advance

To avoid post-hoc rationalisation, the criteria are fixed now:

| Experiment | Adopt NER if | Reject / park NER if |
|---|---|---|
| E0 | Gazetteer F1 ≥ 0.85 on `FOOD`/`CONDITION`/`ALLERGEN`, and latency < 50 ms | Any approach's `ALLERGEN` recall < 0.90 → unsafe to rely on for safety |
| E1 | Recall@5 CI lower bound > baseline point estimate, **and** empty-result rate < 5% | Gold-filter condition C shows no gain → **the metadata filter itself is the wrong idea**; stop here |
| E2 | Profile-accuracy improves **and** Faithfulness does not degrade | Faithfulness drops or hallucination rises |
| E3 | Routing accuracy improves by a margin exceeding its bootstrap CI | No improvement over the 4-keyword rule |
| E4 | Violation recall > 0.90 at false-alarm rate < 0.10 | Cannot build a credible adversarial set |

**Explicit possibility of a negative result.** On a 558-record corpus, dense+BM25+cross-encoder
retrieval over 781 vectors may already be near its ceiling; there is very little for a filter to
prune. A finding of *"NER-derived metadata filtering did not improve Recall@5 on a corpus of this
size, while NER-based routing and allergen validation did improve"* would be a **good, publishable,
honest result** — and it is a genuinely plausible outcome.

---

## 11. Recommended Order of Work

1. **E3 (routing)** — cheapest, no LLM calls, clearest expected win, directly fixes a verified defect.
2. **E0 (gazetteer NER + annotation)** — builds the asset every other experiment needs.
3. **E1 condition C only (gold filters)** — one cheap run that decides whether E1 is worth doing at all.
4. **E1 full**, only if step 3 is positive.
5. **E4 (safety validation)** — highest real-world value; requires new adversarial data.
6. **E2 (generation)** — most expensive in judge calls; run last.

---

## 12. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Wrong `ALLERGEN` extraction → unsafe recommendation | **Critical** | Never *remove* a declared allergy based on NER; NER may only *add* restrictions. Fail-safe, not fail-open. |
| Over-filtering → empty retrieval | High | Mandatory fallback to unfiltered retrieval; measure empty-result rate |
| Wrong `AGE` → wrong calorie target | High | Reject implausible ages (<0.5 or >18); fall back to asking, not to a default |
| Latency regression from a second LLM call | Medium | Measure in E0; prefer gazetteer/GLiNER |
| Annotation of 49–200 questions is real effort | Medium | Start with the 49 existing questions only |
| Evaluation circularity (Qwen extracts, Qwen answers, LLM judges) | Medium | Prefer non-LLM extraction; disclose if used |
| n=41 too small for significance | High | Report CIs; label the study exploratory |

---

## 13. Sources

- Ramshaw & Marcus, *Text Chunking using Transformation-Based Learning*, 1995 — [arXiv:cmp-lg/9505040](https://arxiv.org/abs/cmp-lg/9505040)
- Tjong Kim Sang & De Meulder, *CoNLL-2003 Shared Task: Language-Independent NER* — [ACL W03-0419](https://aclanthology.org/W03-0419/)
- Lample et al., *Neural Architectures for NER*, NAACL 2016 — [arXiv:1603.01360](https://arxiv.org/abs/1603.01360)
- Devlin et al., *BERT*, NAACL 2019 — [arXiv:1810.04805](https://arxiv.org/abs/1810.04805)
- Aho & Corasick, *Efficient string matching*, CACM 1975 — [DOI 10.1145/360825.360855](https://doi.org/10.1145/360825.360855)
- Neumann et al., *ScispaCy*, BioNLP 2019 — [arXiv:1902.07669](https://arxiv.org/abs/1902.07669) · [GitHub](https://github.com/allenai/scispacy)
- Lee et al., *BioBERT*, Bioinformatics 2020 — [DOI 10.1093/bioinformatics/btz682](https://doi.org/10.1093/bioinformatics/btz682)
- Gu et al., *PubMedBERT / Domain-Specific LM Pretraining for Biomedical NLP* — [arXiv:2007.15779](https://arxiv.org/abs/2007.15779)
- Kormilitzin et al., *Med7* — [arXiv:2003.01271](https://arxiv.org/abs/2003.01271)
- Popovski & Koroušić Seljak, *FoodBase corpus*, Database (Oxford) 2019 — [PMC6827550](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6827550/)
- Zaratiana et al., *GLiNER*, NAACL 2024 — [arXiv:2311.08526](https://arxiv.org/abs/2311.08526) · [ACL 2024.naacl-long.300](https://aclanthology.org/2024.naacl-long.300/)
- Zhou et al., *UniversalNER*, ICLR 2024 — [arXiv:2308.03279](https://arxiv.org/abs/2308.03279)
- Willard & Louf, *Efficient Guided Generation for LLMs* — [arXiv:2307.09702](https://arxiv.org/abs/2307.09702)
- Cohen, *A Coefficient of Agreement for Nominal Scales*, 1960 — [DOI 10.1177/001316446002000104](https://doi.org/10.1177/001316446002000104)
- Smucker, Allan & Carterette, *A Comparison of Statistical Significance Tests for IR Evaluation*, CIKM 2007 — [DOI 10.1145/1321440.1321528](https://doi.org/10.1145/1321440.1321528)
- Efron, *Bootstrap Methods*, Annals of Statistics 1979 — [DOI 10.1214/aos/1176344552](https://doi.org/10.1214/aos/1176344552)
- Holm, *A Simple Sequentially Rejective Multiple Test Procedure*, 1979 — [JSTOR 4615733](https://www.jstor.org/stable/4615733)
