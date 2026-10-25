# Feature Engineering Research for KidsNutriBite

**Prepared:** 2026-09-23
**Status:** Research document. No project code was modified.
**Supersedes:** the earlier short feature-engineering note at this path. All of its content
(including experiments F1–F4) is carried forward — see §16.4.

---

## How to read this document

Two labels are used throughout, and they matter:

| Label | Meaning |
|---|---|
| ✅ **VERIFIED** | I read the actual file in this repository and counted. The number is a fact about our data. |
| 🔷 **PROPOSED** | My design suggestion or inference. Not implemented, not measured. |

A third label appears where I could not confirm something:
⚠️ **NOT VERIFIED** — stated as unknown rather than guessed.

**Why your guide's question is ambiguous.** "Feature engineering" names at least six different
activities in a system like ours. §1 and §2 separate them; §2.7 tells you which ones actually apply
to NutriBite. If you only read two sections, read **§2.7** (which meaning applies) and **§3.5**
(what we found wrong in our data).

---

# 1. What Feature Engineering Means

## 1.1 The plain definition

A **feature** is a single measurable property of something you want a computer to reason about.
If the "something" is a child, then *age*, *weight*, and *has a peanut allergy* are three features.

**Feature engineering** is the work of turning messy real-world information into features that a
system can actually use. It has four parts:

| Part | Plain meaning | NutriBite example |
|---|---|---|
| **Extraction** | Pull the value out of raw data | Find "5 year old" in a sentence |
| **Normalization** | Put it in one standard form | "5 year old", "5yrs", "60 months" → `5.0` (years) |
| **Derivation** | Compute new values from existing ones | age `5.0` → age band `preschool_3_6y` |
| **Selection** | Keep only features that earn their place | Drop a feature nothing consumes |

**Terms defined before use:**

- **Raw data** — information as it arrives, unprocessed. A parent's typed sentence; a row in a JSON file.
- **Structured data** — data with a fixed shape where every value has a known name and type.
  `{"age": 5.0}` is structured.
- **Unstructured data** — data with no fixed shape. A paragraph of text is unstructured: the
  computer sees characters, not meaning.
- **Schema** — the agreed list of field names and their types. A contract between producer and consumer.
- **Categorical feature** — takes one of a fixed set of values (`breakfast`, `lunch`, `dinner`, `snack`).
- **Numerical feature** — a number (`age_years = 5.0`).
- **Derived feature** — computed from other features rather than observed directly (BMI from weight and height).
- **Cardinality** — how many distinct values a categorical feature has. High cardinality (hundreds of
  values, few examples each) makes a feature hard to use. ✅ This is a real problem in our data (§3.4).

## 1.2 Feature engineering in traditional machine learning

In classical ML (before deep learning), the model was a relatively simple mathematical function —
logistic regression, a decision tree, a support vector machine. Such a model cannot discover
structure on its own; **a human had to hand it the right numbers**. Performance depended more on the
features than on the algorithm.

Pedro Domingos put it directly: *"At the end of the day, some machine learning projects succeed and
some fail. What makes the difference? Easily the most important factor is the features used."*
— Domingos, *A Few Useful Things to Know About Machine Learning*, CACM 55(10), 2012
([DOI 10.1145/2347736.2347755](https://doi.org/10.1145/2347736.2347755)).

Standard references: Zheng & Casari, *Feature Engineering for Machine Learning*, O'Reilly 2018;
Kuhn & Johnson, *Feature Engineering and Selection*, CRC Press 2019
([free online](http://www.feat.engineering/)).

Typical traditional operations — **most of which are NOT what NutriBite needs**, and it is worth
knowing that up front:

| Operation | What it does | Relevant to us? |
|---|---|---|
| Scaling / standardisation | Rescale numbers to comparable ranges | ❌ No — we have no trained numeric model |
| One-hot encoding | Turn a category into 0/1 columns | ❌ No — Qwen reads text, not vectors |
| Binning | Group a number into ranges | ✅ **Yes** — age → age band |
| Missing-value imputation | Fill in absent values | ⚠️ **Yes, but dangerously** — see §3.5, §13 |
| Interaction terms | Multiply features together | ❌ No |
| Log transforms | Compress skewed distributions | ❌ No |

**This is the first source of confusion with your guide.** If he means feature engineering in the
classical ML sense — scaling, encoding, imputation for a predictive model — **NutriBite has no such
model**. We have a retriever, a rule-based planner, and a language model. None of them consumes a
numeric feature vector.

## 1.3 Feature engineering in NLP

In natural language processing, before neural networks, features were extracted from text by hand:
word counts, TF-IDF weights, part-of-speech tags, n-grams, hand-written lexicon matches.

- **TF-IDF** (term frequency–inverse document frequency) — scores a word by how often it appears in
  one document versus how rare it is across all documents. **Our BM25 retrieval is a refined
  descendant of this idea** (Robertson & Zaragoza, 2009 —
  [DOI 10.1561/1500000019](https://doi.org/10.1561/1500000019)).
- **n-gram** — a sequence of n consecutive words.

So one small but real piece of classical NLP feature engineering **is already running in NutriBite**:
✅ our BM25 service tokenises with `re.findall(r'\w+', text.lower())` and scores on term statistics.

## 1.4 Feature engineering in the deep-learning / LLM era

Deep learning changed the picture. Neural networks **learn their own internal features** from raw
data, which is the subject of *representation learning* — Bengio, Courville & Vincent,
*Representation Learning: A Review and New Perspectives*, IEEE TPAMI 35(8), 2013
([arXiv:1206.5538](https://arxiv.org/abs/1206.5538)).

A large language model like Qwen2.5-7B takes **raw text** as input. You do not hand it a feature
vector. So a natural question is: **is feature engineering dead for LLM applications?**

**No — but it moved.** It moved out of the model and into the *system around* the model:

| Era | Where features are engineered | Who consumes them |
|---|---|---|
| Classical ML | Input vector to the model | The model |
| Deep learning | Learned internally | The network's own layers |
| **LLM applications** | **The surrounding pipeline** | **Retriever, router, business logic, prompt** |

This is the meaning that matters for NutriBite, and §2 develops it.

---

# 2. Feature Engineering in LLM/RAG Systems

## 2.1 Definitions first

- **LLM (Large Language Model)** — a neural network that predicts the next piece of text. Ours is
  `Qwen/Qwen2.5-7B-Instruct`. ✅ Verified in `llm/llm_client.py`.
- **RAG (Retrieval-Augmented Generation)** — instead of relying on what the model memorised, search a
  document collection for relevant passages and paste them into the prompt. Lewis et al., NeurIPS 2020
  ([arXiv:2005.11401](https://arxiv.org/abs/2005.11401)).
- **Retriever** — the component that searches. Ours combines BM25 (keyword matching) and dense vector
  search, then re-ranks. ✅ Verified in `rag/services/retrieval_service.py`.
- **Embedding** — a list of numbers representing a piece of text's meaning. ✅ Ours are 384 numbers
  long, from `BAAI/bge-small-en-v1.5`.
- **Metadata** — extra labelled information attached to a document alongside its text
  (`{"condition": "anemia"}`).
- **Metadata filtering** — restricting search to documents whose metadata matches a condition.
- **Prompt** — the full text sent to the LLM.

## 2.2 The six distinct meanings — kept separate

Your guide could mean any of these. They are genuinely different activities.

```
 ┌──────────────────────────────────────────────────────────────────────┐
 │  M1  DOCUMENT-SIDE      Adding metadata to knowledge-base records     │
 │      (offline, once)    "tag this record with condition=anemia"       │
 ├──────────────────────────────────────────────────────────────────────┤
 │  M2  QUERY-SIDE         Turning a typed question into structured      │
 │      (online, per query) fields: age=5, allergy=[peanut]              │
 ├──────────────────────────────────────────────────────────────────────┤
 │  M3  PROFILE-SIDE       Deriving features from stored child data      │
 │      (online, per user)  age → age_band; weight+height → BMI-for-age  │
 ├──────────────────────────────────────────────────────────────────────┤
 │  M4  PROMPT-SIDE        Choosing what to put in the prompt and how    │
 │      (online, per query) to format it for the LLM                     │
 ├──────────────────────────────────────────────────────────────────────┤
 │  M5  TRAINING-SIDE      Building features/examples to train or        │
 │      (offline)          fine-tune a model                             │
 ├──────────────────────────────────────────────────────────────────────┤
 │  M6  INTERNAL           Analysing/steering the LLM's own hidden       │
 │      (research)         activations — a different research field      │
 └──────────────────────────────────────────────────────────────────────┘
```

## 2.3 M1 — Document-side feature engineering

**What:** enrich each knowledge-base record with structured metadata so it can be filtered,
not just semantically matched.

**Why it exists:** semantic similarity alone cannot express a *hard constraint*. "Find passages about
iron-rich foods" is a similarity question. "Find passages that are **safe for a 7-month-old**" is a
constraint — and a passage about iron-rich peanut snacks may be highly similar while being
categorically wrong for an infant.

**Status in NutriBite:** ✅ partially present, ✅ **currently unused**. Our records carry metadata
(§3.2) and a `MetadataFilterService` exists, but `main.py` never passes filters to it.

## 2.4 M2 — Query-side feature engineering

**What:** convert a free-text question into structured fields.

**The established academic name for this is *slot filling*** (and, across a conversation,
*dialogue state tracking*). This is a mature field with decades of work — ATIS (Hemphill et al., 1990),
MultiWOZ (Budzianowski et al., EMNLP 2018 — [arXiv:1810.00278](https://arxiv.org/abs/1810.00278)),
and a survey: Weld et al., *A Survey of Joint Intent Detection and Slot Filling Models in Natural
Language Understanding*, ACM Computing Surveys, 2022
([DOI 10.1145/3547138](https://doi.org/10.1145/3547138)).

🔷 **This framing is worth telling your guide.** "Query-side feature engineering" in our system is
precisely the classical **intent detection + slot filling** task, and citing that literature is
stronger than describing it as ad-hoc parsing.

**Status in NutriBite:** ✅ **completely absent.** Verified: `main.py:86-92` builds the profile
entirely from command-line flags and falls back to constants. The query text is never parsed.

## 2.5 M3, M4, M5 — briefly

- **M3 profile-side** — deriving features from stored child data. ✅ Partially present: the planner
  derives calorie targets from age/weight. 🔷 §5 proposes more.
- **M4 prompt-side** — what goes in the prompt and in what order. ✅ Present: `prompt_templates.py`
  assembles a profile block, planner output and retrieved chunks.
- **M5 training-side** — features/examples for training. ❌ **Not applicable.** We are not training
  or fine-tuning anything (report 07 established no suitable dataset exists). Per your instruction,
  nothing in this report is designed around fine-tuning.

## 2.6 Related but Different: Internal LLM Representation/Feature Methods

**This is a separate research area. It is NOT what practitioners mean by "feature engineering" in an
application, and it should not be mixed with §2.2's M1–M4.**

Inside Qwen2.5-7B, each layer produces a 3584-dimensional vector per token. Researchers sometimes
call the directions in that space "features". Work in this area includes:

- **Representation Engineering (RepE)** — Zou et al., *Representation Engineering: A Top-Down
  Approach to AI Transparency* ([arXiv:2310.01405](https://arxiv.org/abs/2310.01405)). Places
  *population-level representations* rather than individual neurons at the centre of analysis, and
  offers methods for **monitoring and manipulating** high-level behaviours — including
  safety-relevant ones such as honesty and harmlessness.
- **Sparse autoencoders / monosemanticity** — decomposing activations into interpretable units.
  Critical appraisal: *Are Sparse Autoencoders Useful? A Case Study in Sparse Probing*
  ([arXiv:2502.16681](https://arxiv.org/abs/2502.16681)).
- **Activation steering / probing** — reading or nudging internal states at inference.

**Why it is listed but not recommended for your project:**

| | Application feature engineering (M1–M4) | Internal representation methods (M6) |
|---|---|---|
| Where it acts | Outside the model | Inside the model |
| Who controls it | You | Requires access to hidden states |
| Interpretable to an examiner | Yes — it is JSON | No — high-dimensional vectors |
| Needed for NutriBite to work | **Yes** | No |
| Maturity | Production-standard | Active research, contested |

🔷 **Recommendation:** mention it in one paragraph of your report to show awareness, and state
plainly that it is a distinct field. There is one legitimate future connection — RepE's
safety-monitoring angle could someday complement our safety validator — and §16 records it as future
work. **Do not present it as part of the feature-engineering contribution.**

## 2.7 Which meanings actually apply to NutriBite — the direct answer

| Meaning | Applies? | Current state | Priority |
|---|---|---|---|
| **M1 Document-side** | ✅ **Yes** | Metadata exists but is unused and vocabularies are broken (§3) | **Highest** |
| **M2 Query-side** | ✅ **Yes** | Entirely absent | **High** |
| **M3 Profile-side** | ✅ **Yes** | Partial; fabricated defaults are a live defect | **High** |
| **M4 Prompt-side** | ✅ **Yes** | Present but asserts invented values as fact | **Medium** |
| **M5 Training-side** | ❌ No | Not training anything | **Out of scope** |
| **M6 Internal** | ❌ No | Different field | **Awareness only** |

**One-sentence answer for your guide:** *In NutriBite, feature engineering means turning the parent's
free-text query and the child's stored profile into a validated structured object, and attaching
matching metadata to our knowledge-base records, so that retrieval, meal planning, routing, safety
checking and prompting can all act on explicit fields instead of raw text.*

---

# 3. Dataset-Side Feature Engineering

This section is based on **reading and counting the actual files**. Every number is ✅ VERIFIED.

## 3.1 What raw data we actually have

| File | Records | Nature |
|---|---|---|
| `data/rag/rag_data.json` | **558** | Short text passages + metadata (semi-structured) |
| `data/structured_db/foods.json` | **99** | Food records (structured) |
| `data/structured_db/conditions.json` | **173** | Clinical conditions (structured core + long tail) |
| `data/structured_db/goals.json` | **148** | Nutrition goals (structured core + long tail) |
| `data/structured_db/allergies.json` | **15** | Allergies (structured) |
| `evaluation/dataset.py` | **49** | Benchmark questions with gold answers |

> ✅ **Correction to an earlier report:** the path is `data/structured_db/`, not `data/db/`.
> `00_CURRENT_ARCHITECTURE.md` §2.2 states the wrong path and should be read with this correction.

## 3.2 What is already structured

**`foods.json` — a clean 19-field core present on all 99 records:**

```
food_id · food_name · category · energy_kcal_per_100g · protein_g · fat_g · carbs_g ·
iron_mg · portion_unit · portion_energy_kcal · portion_protein_g ·
digestibility_boiled · digestibility_fried · fat_level_fried · glycemic_index ·
age_min · allergy_tags · meal_types · tags
```

This is genuinely good design. **`age_min`, `allergy_tags` and `meal_types` already exist** — three of
the most important features this report would otherwise have to propose.

**`conditions.json`** — all 173 have `condition_name`, `required_tags`, `avoid_tags`, `meal_pattern`.
**`goals.json`** — all 148 have `goal_name`, `required_tags`, `avoid_tags`, `meal_frequency`.
**`allergies.json`** — all 15 have `allergy`, `avoid_foods`, `severity`.

**`rag_data.json`** — every record is `{id, text, metadata}`:

| Metadata key | Coverage | Distinct values |
|---|---|---|
| `type` | 558 / 558 (100%) | 147 |
| `tags` | 402 / 558 (72%) | **888** |
| `condition` | 94 / 558 (17%) | — |
| `source` | 63 / 558 (11%) | — |
| `food_name` | 13 / 558 (2%) | — |
| `goal` | 13 / 558 (2%) | — |

## 3.3 What is unstructured

1. **The `text` field of all 558 RAG records.** Mean 134 characters. This is the actual knowledge.
2. **The long tail of optional fields** in the structured DB — `foods.json` has ~22 additional keys
   appearing on 1–39 records (`clinical_benefits` on 10, `nutrients_per_100g` on 10,
   `probiotic_strains` on 1…); `conditions.json` has ~45 such keys. These are effectively
   free-text notes stored in a structured file. **No code reads them.**
3. **The parent's query** — the entire subject of §4.

## 3.4 ✅ VERIFIED data-quality findings

These were found by counting, and several are serious.

### Finding 1 — Numeric nutrition fields are largely empty strings

| Field | Numeric | **Empty string `""`** | % missing |
|---|---|---|---|
| `energy_kcal_per_100g` | 61 | **38** | 38% |
| `protein_g` | 54 | 44 (+1 other string) | 45% |
| `fat_g` | 49 | **50** | 51% |
| `carbs_g` | 49 | **50** | 51% |
| **`iron_mg`** | 42 | **57** | **58%** |
| `portion_energy_kcal` | 34 | **65** | 66% |
| `portion_protein_g` | 34 | **65** | 66% |

**Why this matters, concretely:** the planner sums nutrients across selected foods, and
`prompt_templates.py` renders `- Planned Iron: {totals[iron_mg]} mg` into the prompt — which the LLM
then explains to a parent. With **58% of foods carrying no iron value**, that total is computed over
an unknown subset. The number shown to the parent is not wrong so much as **not meaningful**, and
nothing in the system communicates that.

Note the type problem too: the missing marker is `""` (empty string), not `null`. In Python
`"" != 0` but `""` is falsy, so naive arithmetic either crashes or silently skips.

### Finding 2 — `age_min` is ambiguous in unit and 44% absent

✅ Values observed: `"" ×44`, `1 ×22`, `6 ×16`, `2 ×5`, `9 ×5`, `8 ×4`, `12 ×3`.

Is `age_min: 6` **six months** or **six years**? Is `12` twelve months (= 1 year) or twelve years?
Both readings are plausible and they are **clinically opposite**. ⚠️ **NOT VERIFIED** — I could not
determine the intended unit from the data or from code. Given that `1` appears 22 times and `6`
16 times, and that the corpus is pediatric, months seems more likely for the small values — but
`age_min: 1` would then mean one month, which is implausible for solid food.

**This single ambiguity blocks any age-based food filtering until resolved by whoever authored the
file.** It is the clearest example in our project of why *normalization* (§1.1) is not optional.

### Finding 3 — 🚨 The allergy join is broken, and this is a safety issue

`allergies.json` lists `avoid_foods` strings. For those to exclude anything, they must match
something in `foods.json`. ✅ Of **24 distinct `avoid_foods` strings**:

| Resolves to | Count | Examples |
|---|---|---|
| A `food_name` | 14 | `cows_milk`, `boiled_egg`, `nuts`, `mashed_fish` |
| A food `tag` | **0** | — |
| A food `allergy_tag` | 1 | `milk` |
| ❌ **Nothing at all** | **10** | **`peanut_powder`, `wheat`, `barley`, `rye`, `sesame_powder`**, `bovine_milk`, `milk_added_foods`, `milk_added_recipes`, `unmodified_bovine_milk`, `unmodified_cow_milk` |

**A child with a declared nut allergy: `peanut_powder` matches nothing. A child with gluten
sensitivity: `wheat`, `barley` and `rye` all match nothing.** The exclusion silently does nothing.

🔷 This is the strongest argument in this entire report for doing dataset-side feature engineering,
and it is a *correctness and safety* argument, not a performance one.

### Finding 4 — `allergy_tags` are absent from 79% of foods

✅ 78 of 99 foods have an empty `allergy_tags` list. The whole vocabulary is 7 tags:
`egg_protein`, `milk`, `lactose`, `nut_allergy`, `fish`, `gluten_optional`, `seafood_allergy`.

So even where the join works, only 21 foods can ever be excluded by it.

### Finding 5 — Condition and goal tag vocabularies are disjoint from food tags

The planner filters foods using `conditions.required_tags` / `avoid_tags`. For that to work, those
tags must exist on foods. ✅ Measured:

| Source | Distinct tags referenced | Match a food tag | Match rate |
|---|---|---|---|
| `conditions.json` | 73 | 11 | **15.1%** |
| `goals.json` | 79 | 15 | **19.0%** |
| `rag_data.json` | 888 | 34 | **3.8%** |

Unmatched examples: `balanced_diet`, `added_sugar`, `continue_feeding`, `diverse_food_groups`,
`carb_50_60`, `age_specific_diet`.

**The reason is a vocabulary mismatch, and it is instructive.** Foods are tagged with *nutritional
attributes* (`fiber_rich`, `vitamin_rich`, `low_calorie` — 133 distinct). Conditions and goals are
tagged with *dietary advice concepts* (`balanced_diet`, `avoid_added_sugar`). These are different
kinds of thing, so they do not join. **85% of condition-driven food filtering cannot fire.**

### Finding 6 — Inconsistent categorical vocabularies

✅ `meal_types` on foods uses **nine** values: `lunch`(27), `dinner`(16), `snack`(15),
`breakfast`(11), `evening`(6), `all`(4), `mid_morning`(4), `afternoon`(2), `morning`(1).

But the planner emits exactly **four** meals: breakfast, lunch, dinner, snack. So `evening`,
`mid_morning`, `afternoon`, `morning` and `all` — **17 foods' worth** — do not map onto any meal the
planner produces.

✅ `category` has 12+ values with **5 foods having `""`**.

### Finding 7 — Duplicate records in `allergies.json`

✅ 15 records, but the `allergy` names include `egg_protein` ×3, `milk` ×3, `fish` ×2. So there are
roughly **10 distinct allergies in 15 records**. A lookup keyed on allergy name will hit whichever
duplicate comes first and silently ignore the others' `avoid_foods` — meaning some exclusions are
lost even when they would otherwise resolve.

### Finding 8 — No age metadata anywhere in the RAG corpus

✅ **0 of 558** RAG records carry any age-like metadata key.

Age is the single most important variable in pediatric nutrition — advice for a 6-month-old and a
12-year-old is not merely different, it is oppositely dangerous. **Age-based retrieval filtering is
impossible today**, no matter how well we extract age from the query.

### Finding 9 — The `condition` field is overloaded to carry age bands

✅ In `evaluation/dataset.py`, profiles include `{"age": 0.6, "condition": "infant_6_8_months"}`.
"infant_6_8_months" is an **age band**, not a clinical condition. Two distinct concepts are sharing
one field.

## 3.5 Summary: dataset-side work that is justified

| # | Task | Justification | Evidence |
|---|---|---|---|
| D1 | **Resolve the `age_min` unit ambiguity** | Blocks all age filtering | Finding 2 |
| D2 | **Fix the allergy join** — make `avoid_foods` resolve | **Safety**: 10/24 resolve to nothing | Finding 3 |
| D3 | **Back-fill `allergy_tags`** on the other 78 foods | Only 21 foods are excludable | Finding 4 |
| D4 | **Reconcile tag vocabularies** or add a mapping layer | 85% of condition filtering cannot fire | Finding 5 |
| D5 | **Normalise `meal_types`** to the planner's 4 slots | 17 foods unreachable | Finding 6 |
| D6 | **Deduplicate `allergies.json`** | Silent loss of exclusions | Finding 7 |
| D7 | **Add `age_band` metadata to RAG records** | Enables age filtering at all | Finding 8 |
| D8 | **Replace `""` with `null` + add a `*_known` flag** | Distinguishes "zero" from "unknown" | Finding 1 |
| D9 | **Separate age band from condition** | Two concepts, one field | Finding 9 |
| D10 | Normalise `category`; fill the 5 empty | Low cost, low risk | Finding 6 |

🔷 **D1, D2 and D8 are the ones I would do first.** D2 is a safety defect; D1 blocks a whole feature
class; D8 is what stops the system reporting meaningless nutrient totals as if they were real.

### 3.6 On numerical transformations — a deliberate non-recommendation

Section E of your brief asks about "numerical transformations". Classical options are scaling,
normalisation, log transforms and binning (§1.2).

🔷 **My assessment: only binning is useful to us, and the rest should be explicitly excluded.**
Scaling and log transforms exist to help gradient-based models train. **We are not training a model.**
Our numbers are consumed by (a) arithmetic in the planner, which needs true units, and (b) the LLM
as text, which needs human-readable values. Scaling would actively harm both.

Saying "we considered numerical transformations and rejected them because there is no trained
numerical model in the pipeline" is a better answer to your guide than applying them unnecessarily.

### 3.7 Derived nutritional features — worth it only where used

| Derived feature | Formula | Real reason to add? |
|---|---|---|
| **Protein density** | `protein_g / energy_kcal × 100` | 🔷 Yes if a goal is "weight gain with lean mass"; ⚠️ computable for only ~54/99 foods |
| **Iron per 100 kcal** | `iron_mg / energy_kcal × 100` | 🔷 Yes for anemia — a core NutriBite use case; ⚠️ only ~42/99 foods |
| **Energy density** | `energy_kcal / 100 g` | ✅ Already present as `energy_kcal_per_100g` |
| **Macro ratio** (carb/protein/fat %) | from the three fields | 🔷 Only if a goal expresses macro targets. The unused weekly planner does; the live planner does not |
| **Nutrient completeness score** | count of non-empty nutrient fields | 🔷 **Yes — high value.** Directly encodes Finding 1, letting the planner prefer well-characterised foods and letting the prompt flag uncertainty |
| Glycemic load | `GI × available carbs / 100` | ❌ **No.** `glycemic_index` is categorical (`low`/`high`), not numeric — the formula cannot be computed |

**The last row is the point of this table.** Not every textbook derived feature survives contact with
the actual data. Proposing glycemic load would look sophisticated and would be undeliverable.

---

# 4. Query-Side Feature Engineering

## 4.1 The task

Turn this:

> *"My 5 year old is allergic to peanuts and needs an iron-rich breakfast"*

into something a program can branch on. Your brief proposes:

```json
{ "age_years": 5, "allergies": ["peanut"], "nutrients": ["iron"], "meal_slot": ["breakfast"] }
```

**You asked me not to assume this schema is correct. It is a good start, and it has four problems.**

## 4.2 What is wrong with the obvious schema

**Problem 1 — no provenance.** The object cannot express *where a value came from*. `age_years: 5`
looks identical whether the parent said it, the database holds it, or the system invented it.
✅ This is not hypothetical: `main.py:86-92` currently defaults to `age=7.0, weight=20.0` and
`prompt_templates.py:56-61` then prints those to the LLM as statements of fact.

**Problem 2 — absence is unrepresentable.** If the parent does not mention age, is the field missing,
null, or defaulted? A schema must distinguish *unknown* from *zero* from *not applicable*. Compare
the missing-data literature's distinction between data missing completely at random, at random, and
not at random — Little & Rubin, *Statistical Analysis with Missing Data*, Wiley
([DOI 10.1002/9781119482260](https://doi.org/10.1002/9781119482260)).

**Problem 3 — surface forms are not database keys.** `"peanut"` is what the parent typed.
✅ Our `allergies.json` uses `nut_allergy`; our foods use `allergy_tags` like `nut_allergy`. Storing
the surface form guarantees the lookup fails. The schema must carry **both** the surface span and the
resolved key.

**Problem 4 — no confidence, so no way to be cautious.** A safety-critical system must be able to
say "I think I saw an allergy but I am not sure", and treat that differently from certainty.

## 4.3 🔷 What should actually be extracted

Derived from what our code and data can actually *consume* — a feature nothing consumes is a
liability, not an asset (§1.1 selection).

| # | Feature | Type | Justification (why it earns its place) | Consumer exists today? |
|---|---|---|---|---|
| 1 | `age_years` | float | Drives Holliday–Segar calories; `foods.age_min`; safety | ✅ Planner |
| 2 | `age_band` | enum | Derived. Filter key; 17 free-text age strings in our benchmark are unusable raw | 🔷 Needs D7 |
| 3 | `allergies[]` | list | **Safety-critical**; `allergies.json` exists | ✅ Planner (partly broken, D2) |
| 4 | `conditions[]` | list | Planner multiplier; RAG `condition` metadata on 94 records | ✅ Planner + retriever |
| 5 | `goals[]` | list | ±kcal adjustment | ✅ Planner |
| 6 | `meal_slots[]` | list | Routing; scoping the answer | 🔷 Planner emits all 4 regardless |
| 7 | `foods_mentioned[]` | list | "Is ragi good for her?" needs the food identified | 🔷 Retrieval only |
| 8 | `nutrients_mentioned[]` | list | "iron-rich" → target the answer | 🔷 Retrieval only |
| 9 | `weight_kg` | float? | Holliday–Segar input (currently defaulted to 20.0) | ✅ Planner |
| 10 | `height_cm` | float? | Only needed for BMI-for-age — see §5.3 | ❌ **No consumer** |
| 11 | `diet_pattern` | enum? | Vegetarian/Jain etc. — major in Indian context | 🔷 Via tags |
| 12 | `quantities[]` | list | "2 cups of milk — is that too much?" is a real parent question | ❌ **No consumer** |
| 13 | `intent` | enum | Replaces the 4-keyword router | ✅ Router exists |
| 14 | `is_medical_request` | bool | Triggers the refusal script | ✅ In prompt only |
| 15 | `symptoms[]` | list | 🔷 **Escalation signal**, not nutrition advice | ❌ No consumer |
| 16 | `medications[]` | list | 🔷 **Hard escalation trigger** | ❌ No consumer |
| 17 | `frequency` / `duration` | — | ⚠️ **I found no consumer and no clear use.** Recommend **excluding** for now | ❌ No |

**On 15, 16, 17 — being honest about what does not belong.** Your brief lists frequency/duration,
symptoms and medications. Symptoms and medications have a genuine *safety escalation* rationale
(a parent reporting vomiting should be pointed to a doctor, not given a meal plan). Frequency and
duration, I could not justify: I found no component that would act differently based on "twice a
day". 🔷 **Recommend excluding `frequency`/`duration` until a consumer exists.**

## 4.4 How extraction could be done

Four approaches, evaluated in depth in `01_NER_RESEARCH.md` §3–§6. Summary:

| Approach | Needs training data? | Fit for us |
|---|---|---|
| **Gazetteer + regex** | No | ✅ **Best starting point** — our DB *is* the gazetteer (99 foods, 173 conditions, 148 goals, 15 allergies) |
| Pretrained general NER | Fine-tuning | ❌ No labels for FOOD/ALLERGEN/CONDITION |
| Biomedical NER (scispaCy) | No | 🔷 Useful for CONDITION only |
| **GLiNER** (zero-shot) | No | 🔷 Strong research comparison — [arXiv:2311.08526](https://arxiv.org/abs/2311.08526) |
| **Qwen itself** (JSON extraction) | No | 🔷 Flexible, but adds latency and **can hallucinate an allergy** |

---

# 5. Profile Feature Engineering

## 5.1 ⚠️ A critical architectural distinction

**You explicitly flagged this, and it changes the design.** The CLI prototype is **not** the intended
final architecture.

| | ✅ Current CLI prototype | 🔷 Intended full-stack NutriBite |
|---|---|---|
| Where profile comes from | `--age`, `--weight`, `--allergies` flags | **Application database** |
| Authority | None — hardcoded fallbacks | **Authoritative, user-confirmed** |
| Persistence | None (single-shot) | Stored per child |
| Verified by | — | 🔷 Parent at onboarding; ideally a clinician |

**The consequence for feature-engineering design:**

> 🔷 **Query-side extraction must AUGMENT authoritative profile data, never replace or fabricate it.**

The query is evidence about *this question*. The profile is the record of *this child*. When a
profile exists, it wins on identity facts (age, weight, diagnosed conditions, confirmed allergies);
the query contributes intent, meal slot, mentioned foods, and **new information to be confirmed** —
not silently written.

## 5.2 🔷 Proposed precedence rules

| Situation | Rule | Reason |
|---|---|---|
| Profile has age, query does not | **Use profile** | Authoritative |
| Query states age, profile has none | **Use query**, mark `source: "extracted"` | Better than a default |
| Both present and **agree** | Use profile; raise confidence | Consistent |
| Both present and **conflict** | 🚨 **Use profile, flag the conflict, surface it to the parent** | Never silently overwrite a stored fact |
| Query mentions a **new allergy** not in profile | **Apply it for this turn** (restrict), and prompt to add it to the profile | **Fail-safe**: adding a restriction is safe; ignoring one is not |
| Query says an allergy has **resolved** | **Do not remove it.** Require explicit profile update | Removing a restriction from free text is unsafe |
| Neither has it | `source: "absent"`, render as **"not specified"** | **Never fabricate** |

The asymmetry in the last three rows is deliberate and is the most important safety principle in this
report: **free text may tighten a constraint, never loosen one.**

## 5.3 Derived profile features — and an important domain correction

**BMI must be handled differently for children than for adults.** Adult BMI categories
(18.5 / 25 / 30) are **not valid for children**, because healthy body composition changes with age
and sex. The correct instrument is **BMI-for-age**, expressed as a percentile or **z-score** against
a growth reference.

WHO defines BMI-for-age as a standard indicator
([WHO BMI-for-age](https://www.who.int/toolkits/child-growth-standards/standards/body-mass-index-for-age-bmi-for-age)),
and the WHO Child Growth Standards are recommended for children 0–5 years
([WHO Child Growth Standards](https://www.who.int/tools/child-growth-standards/standards/weight-for-age)).
For 0–5 year olds, WHO BMI-for-age z-score cut-points of **< −2.0, > 1.0, > 2.0 and > 3.0** classify
wasted, risk-of-overweight, overweight and obese respectively. Using rounded percentiles instead of
z-scores measurably misclassifies children — Furlong et al.
([PMC5706297](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5706297/)).

| Derived feature | Formula | Recommendation |
|---|---|---|
| Raw BMI | `kg / m²` | ⚠️ **Compute but never categorise with adult thresholds** |
| **BMI-for-age z-score** | vs WHO LMS reference | 🔷 Correct method — **requires the WHO reference tables, which we do not have** |
| `weight_estimated` | bool | ✅ **High value, trivial** — flags the 20.0 kg default as an estimate |
| `age_band` | bin `age_years` | 🔷 High value (§7.2) |
| `specificity_score` | non-null features ÷ total | 🔷 Proxy for "how much do we know about this child" |

🔷 **Honest recommendation:** implement `weight_estimated` and `age_band` now. Treat BMI-for-age
z-scores as **future work** — doing it properly needs WHO LMS tables and a clinician's sign-off, and
doing it *improperly* (adult thresholds on a child) would be a clinical error worse than omitting it.

---

# 6. NER vs Feature Engineering

## 6.1 The distinction, stated plainly

**NER (Named Entity Recognition)** finds and labels *spans of text*. That is all it does.

**Feature engineering** takes those spans and produces a *validated, typed object other components
can act on*.

```
  RAW QUERY
  "my 5 yr old is allergic to peanuts, need iron rich breakfast"
        │
        ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ STEP 1 — NER / ENTITY EXTRACTION                             │
  │ Output: labelled spans, with character offsets               │
  │   "5 yr old"  → AGE        (chars 3-11)                      │
  │   "peanuts"   → ALLERGEN   (chars 30-37)                     │
  │   "iron"      → NUTRIENT   (chars 44-48)                     │
  │   "breakfast" → MEAL_SLOT  (chars 54-63)                     │
  │ ⚠️ Still just TEXT. Not usable by any component.             │
  └─────────────────────────────────────────────────────────────┘
        │
        ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ STEP 2 — NORMALIZATION                                       │
  │ Surface form → canonical value/unit                          │
  │   "5 yr old" → 5.0 (float, years)                            │
  │   "peanuts"  → "nut_allergy"   ← key in allergies.json       │
  │   "iron"     → "iron_mg"       ← field in foods.json         │
  │   "breakfast"→ "breakfast"     ← one of planner's 4 slots    │
  └─────────────────────────────────────────────────────────────┘
        │
        ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ STEP 3 — VALIDATION                                          │
  │   age 5.0 in [0, 18]?                    ✅                   │
  │   "nut_allergy" exists in allergies.json? ✅                  │
  │   does it resolve to foods? (D2!)         ⚠️ partially        │
  │   conflicts with stored profile?          check              │
  └─────────────────────────────────────────────────────────────┘
        │
        ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ STEP 4 — MERGE WITH AUTHORITATIVE PROFILE (§5.2)             │
  │   profile wins on identity; query may only TIGHTEN           │
  └─────────────────────────────────────────────────────────────┘
        │
        ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ STEP 5 — DERIVATION                                          │
  │   age_band = "preschool_3_6y";  intent = "meal_plan"         │
  │   requires_planner = true                                    │
  └─────────────────────────────────────────────────────────────┘
        │
        ▼
  STRUCTURED FEATURE OBJECT  →  RAG · Planner · Router · Safety · Qwen
```

## 6.2 What NER alone cannot do

| NER cannot… | Why it matters here | Handled by |
|---|---|---|
| Convert "18 months" to `1.5` | The planner needs a float in years | Normalization |
| Map "peanuts" → `nut_allergy` | ✅ Our DB key is `nut_allergy` | Entity linking |
| Know 200 years old is impossible | An absurd age would corrupt calorie maths | Validation |
| Resolve query vs profile conflict | Two sources, one child | Merge (§5.2) |
| Know `peanut_powder` resolves to nothing | ✅ Finding 3 — **safety** | Validation |
| Decide planner vs QA route | Needs a policy | Derivation |
| Say how confident it is | Safety needs caution | Confidence |
| Remember across turns | Full-stack need | Profile store |

**Summary:** NER produces *evidence*. Feature engineering produces *decisions*. NER without the four
steps after it is not usable by any component in NutriBite.

## 6.3 Provenance and confidence

🔷 Every field should carry:

```jsonc
"age_years": {
  "value": 5.0,
  "source": "extracted",     // profile | extracted | derived | default | absent
  "confidence": 0.95,
  "span": "5 year old",      // for audit — lets a human check the extractor
  "conflict": null           // set if profile and query disagree
}
```

🔷 **Proposed confidence policy** — the thresholds are design choices, not measured values, and would
need calibrating against the NER evaluation in `01_NER_RESEARCH.md` §9 (E0):

| Band | Non-safety fields | **Safety fields (allergy, medication, symptom)** |
|---|---|---|
| High (≥0.9) | Use | Use |
| Medium (0.6–0.9) | Use, mark uncertain | **Apply restriction + ask to confirm** |
| Low (<0.6) | Ignore | **Still apply the restriction, and ask** |

The right column never ignores a possible allergy. Acting on a false positive costs one unnecessary
food exclusion; missing a true positive can harm a child.

---

# 7. Feature Schema for NutriBite

## 7.1 🔷 Proposed schema

```jsonc
{
  "schema_version": "1.0",
  "query": {
    "raw": "My 5 year old is allergic to peanuts and needs an iron-rich breakfast",
    "normalized": "my 5 year old is allergic to peanuts and needs an iron rich breakfast"
  },

  "child_profile": {
    "age_years":  { "value": 5.0,  "source": "profile",   "confidence": 1.0, "conflict": null },
    "age_band":   { "value": "preschool_3_6y", "source": "derived" },
    "weight_kg":  { "value": null, "source": "absent" },
    "weight_estimated": true,
    "height_cm":  { "value": null, "source": "absent" },
    "diet_pattern": { "value": null, "source": "absent" }
  },

  "clinical": {
    "allergies": [
      { "surface": "peanuts", "linked_key": "nut_allergy",
        "source": "extracted", "confidence": 0.97,
        "in_db": true, "resolves_to_foods": ["nuts", "nuts_seeds"],
        "unresolved_terms": ["peanut_powder"],        // ← Finding 3, made visible
        "in_profile": false, "action": "apply_and_confirm" }
    ],
    "conditions": [], "goals": [], "medications_mentioned": [], "symptoms": []
  },

  "nutrition_context": {
    "nutrients_mentioned": [ { "surface": "iron-rich", "linked_key": "iron_mg" } ],
    "foods_mentioned": [], "meal_slots": ["breakfast"], "quantities": []
  },

  "intent": {
    "label": "meal_plan", "requires_planner": true,
    "is_medical_request": false, "escalate_to_clinician": false, "confidence": 0.86
  },

  "retrieval_filters": { "condition": null, "goal": null, "category": null },

  "provenance": {
    "extractor": "gazetteer_v1", "extraction_latency_ms": 3.2,
    "fields_defaulted": ["weight_kg"],
    "validation_warnings": ["allergy term 'peanut_powder' does not resolve to any food record"]
  }
}
```

## 7.2 🔷 `age_band` vocabulary

Aligned to WHO/UNICEF infant and young child feeding practice
([WHO/UNICEF IYCF indicators, 2021](https://www.who.int/publications/i/item/9789240018389)):

| Band | Range | Why this boundary |
|---|---|---|
| `infant_0_6m` | 0–<0.5 y | Exclusive breastfeeding period |
| `infant_6_12m` | 0.5–<1 y | Complementary feeding begins |
| `toddler_1_3y` | 1–<3 y | Transition to family foods |
| `preschool_3_6y` | 3–<6 y | — |
| `school_6_10y` | 6–<10 y | — |
| `preadolescent_10_13y` | 10–<13 y | — |
| `adolescent_13_18y` | 13–18 y | — |

The 0–6 m / 6–12 m split is not arbitrary — it is the exclusive-breastfeeding boundary, and the band
where a wrong food recommendation is most dangerous.

## 7.3 Three design decisions worth defending

**(a) `retrieval_filters` is a separate flat block.** ✅ Because `MetadataFilterService` accepts only
`condition`/`goal`/`category` as string equality. Keeping it separate lets the rich clinical model
evolve without breaking that contract.

**(b) Allergies deliberately do NOT go through the metadata filter.** ✅ Verified: its list branch is
literally `elif isinstance(val, list): pass` — a no-op. Passing `{"allergies": [...]}` would silently
do nothing. Allergy handling must go to the planner and a post-generation validator instead.

**(c) `unresolved_terms` is a first-class field.** 🔷 It makes Finding 3 visible at runtime instead of
silent. A system that knows what it failed to exclude can warn; one that does not, cannot.

---

# 8. Document Metadata Engineering for RAG

## 8.1 The design question you raised

> *query says peanut allergy → retrieve/filter documents with allergen-safe information*

**⚠️ I do not think this design is sound as stated, and it is important to say so.**

Two problems:

1. **Documents are not "allergen-safe" or "allergen-unsafe".** A passage explaining why peanuts are a
   good protein source is not *unsafe* — it is *inapplicable to this child*. Filtering it out of
   retrieval does not protect anyone; it just narrows the evidence.
2. **The real risk is in the generated answer, not the retrieved document.** Harm occurs if the
   answer *recommends* peanuts to an allergic child. That is a **generation-time** check, not a
   retrieval-time filter.

🔷 **Recommended alternative: retrieval filtering for relevance, generation validation for safety.**

| Concern | Right mechanism | Where |
|---|---|---|
| "Find passages about infant feeding" | Metadata filter on `age_band` | Retrieval |
| "Find passages about anemia" | Metadata filter on `condition` | Retrieval |
| **"Never recommend peanuts to this child"** | **Post-generation allergen validator** | **After generation** |
| "Exclude peanut foods from the plan" | Planner tag exclusion | Planner |

This matters because filtering documents by allergen could **remove the very passage explaining the
allergy** — the opposite of the intent.

## 8.2 🔷 Proposed metadata schema for RAG records

Current: `{type, tags, condition, source, food_name, goal}`.

| Field | Status | Proposal | Priority |
|---|---|---|---|
| `type` | ✅ 100%, **147 distinct** | Add coarse `type_group` (10–15 classes); keep `type` as sub-field | **High** |
| `tags` | ✅ 72%, **888 distinct** | Too fragmented to filter on (~2.2 records/tag). Keep for BM25; **do not use as a filter key** | Medium |
| `condition` | ✅ 17% | **Back-fill** using the gazetteer over record text | **High** |
| `age_band` | ❌ **0%** | **Add** — enables age filtering at all | **Highest** |
| `goal` | ✅ 2% | Back-fill | Medium |
| `food_name` | ✅ 2% | Back-fill from the 99-name gazetteer | Medium |
| `source` | ✅ 11% | 🔷 **Add `authority` tier** (WHO/ICMR > textbook > general) | **High** |
| `evidence_level` | ❌ | 🔷 Future — needs clinical input | Low |

**On `authority`:** 🔷 this is arguably the highest-value *new* field. For a pediatric health system,
being able to prefer or cite WHO/ICMR-sourced guidance over general text is both a retrieval
improvement and a trust argument — and it connects directly to report 07's recommendation to expand
the corpus from IFCT 2017 and WHO/UNICEF IYCF.

## 8.3 Why document-side work must come first

🔷 **Query-side extraction can only exploit metadata that exists.**

Perfect extraction of `age_band = infant_6_12m` is worthless when ✅ **0 of 558 records carry age
metadata**. Likewise, filtering on `condition` restricts to a ✅ **17% subset**, which on 558 records
means ~94 candidates — and with `top_k=5` there is a real risk of over-filtering.

🔷 **Therefore: measure metadata coverage after back-fill BEFORE investing in query-side filtering.**
That is experiment F2 (§16.4), it requires no LLM calls, and it is the cheapest decisive test in this
report.

## 8.4 Standards worth citing

Not necessarily to adopt — but citing them shows the taxonomy problem is a known one:

| Standard | Domain | Relevance |
|---|---|---|
| **FoodOn** | Food ontology, farm to fork | Dooley et al., *npj Science of Food* 2, 2018 — [DOI 10.1038/s41538-018-0032-6](https://doi.org/10.1038/s41538-018-0032-6) · [foodon.org](https://foodon.org/). Built largely from **LanguaL**, a food indexing thesaurus with 14 facets |
| **LanguaL** | Food indexing | The basis of FoodOn's vocabulary |
| **SNOMED CT** | Clinical terms | Standard for condition normalization ⚠️ licensing applies |
| **UCUM** | Units of measure | [Unified Code for Units of Measure](https://ucum.org/) — unambiguous machine-readable units. ⚠️ Note: no mapping exists between UCUM and SNOMED units, and SNOMED lacks scaling info |
| **ICMR-NIN IFCT 2017** | Indian food composition | [nin.res.in](https://www.nin.res.in/ebooks/IFCT2017.pdf) — 528 foods, 151 components |

🔷 **Recommendation: cite these, adopt none of them wholesale.** Mapping 99 foods onto FoodOn is a
project in itself. But saying *"we defined a local taxonomy rather than adopting FoodOn, because our
99-food scope did not justify the mapping cost"* is a defensible engineering decision, whereas not
knowing they exist is not.

---

# 9. How Features Flow Through NutriBite

## 9.1 🔷 Proposed pipeline

```
 ┌───────────────────────┐        ┌──────────────────────────────┐
 │  PARENT / CHILD       │        │  CURRENT USER QUERY          │
 │  PROFILE (app DB)     │        │  free text                   │
 │  authoritative        │        │                              │
 └───────────┬───────────┘        └──────────────┬───────────────┘
             │                                    │
             │                                    ▼
             │                     ┌──────────────────────────────┐
             │                     │ 1. QUERY UNDERSTANDING / NER │
             │                     │    gazetteer + regex         │
             │                     │    → labelled spans          │
             │                     └──────────────┬───────────────┘
             │                                    ▼
             │                     ┌──────────────────────────────┐
             │                     │ 2. NORMALIZATION             │
             │                     │    units, canonical keys     │
             │                     └──────────────┬───────────────┘
             │                                    ▼
             │                     ┌──────────────────────────────┐
             │                     │ 3. VALIDATION                │
             │                     │    ranges, DB existence,     │
             │                     │    unresolved-term warnings  │
             │                     └──────────────┬───────────────┘
             └────────────┬───────────────────────┘
                          ▼
             ┌────────────────────────────────────┐
             │ 4. MERGE (profile wins on identity;│
             │    query may only TIGHTEN)         │
             └────────────────┬───────────────────┘
                              ▼
             ┌────────────────────────────────────┐
             │ 5. DERIVATION                      │
             │    age_band, intent, flags         │
             └────────────────┬───────────────────┘
                              ▼
             ╔════════════════════════════════════╗
             ║   ENGINEERED FEATURE OBJECT (§7)   ║
             ╚════════════════╤═══════════════════╝
                              │
   ┌──────────┬───────────────┼───────────────┬──────────────┐
   ▼          ▼               ▼               ▼              ▼
┌────────┐ ┌────────┐ ┌──────────────┐ ┌───────────┐ ┌─────────────┐
│6. RAG  │ │7. PLAN │ │8. ROUTING    │ │9. QWEN    │ │10. SAFETY   │
│filters │ │ner     │ │planner vs QA │ │prompt     │ │validator    │
└───┬────┘ └───┬────┘ └──────┬───────┘ └─────┬─────┘ └──────┬──────┘
    │          │             │               │              │
    └──────────┴─────────────┴───────┬───────┘              │
                                     ▼                      │
                            ┌─────────────────┐             │
                            │ GENERATED ANSWER│─────────────┘
                            └────────┬────────┘   (checked AFTER generation)
                                     ▼
                            ┌─────────────────┐
                            │ 11. EVALUATION  │
                            └─────────────────┘
```

## 9.2 Step-by-step

| Step | What happens | Input | Output | Status |
|---|---|---|---|---|
| 1 | Gazetteer + regex over the query | raw text | labelled spans | 🔷 To build |
| 2 | Surface → canonical value/unit | spans | normalized values | 🔷 To build |
| 3 | Range checks, DB existence, warnings | normalized | validated + warnings | 🔷 To build |
| 4 | Merge with profile under §5.2 rules | validated + profile | merged | 🔷 To build |
| 5 | Compute `age_band`, `intent`, flags | merged | feature object | 🔷 To build |
| 6 | `retrieve(query, top_k, filters=…)` | `retrieval_filters` | 5 chunks | ✅ Retriever exists, filters unused |
| 7 | `generate_meal_plan(profile)` | profile fields | meal plan | ✅ Exists |
| 8 | `requires_planner` replaces 4 keywords | `intent` | route | ✅ Router exists (weak) |
| 9 | Render a truthful profile block | feature object | prompt | ✅ Templates exist |
| 10 | Cross-check answer foods vs allergies | features + answer | pass/flag | ❌ **Does not exist** |
| 11 | Log features with metrics | everything | records | 🔷 To build |

---

# 10. Feature → Component Mapping Table

**Consumer key:** RAG = retrieval · PLAN = planner · ROUTE = routing · SAFE = safety validator ·
QWEN = prompt · EVAL = evaluation

| Feature | Source | Transformation | Consumer | Why useful | Risk |
|---|---|---|---|---|---|
| `age_years` | Profile (auth.) / query | "5 yr" → `5.0` float years | PLAN, RAG, SAFE, QWEN | Drives Holliday–Segar; ✅ replaces the fabricated 7.0 default | Wrong age → wrong calories for a child |
| `age_band` | Derived | Bin per §7.2 | RAG, SAFE, QWEN | Turns 17 free-text age strings into a filter key | ⚠️ Useless until D7 adds age metadata to records |
| `weight_kg` | Profile / query | "12 kg" → `12.0` | PLAN | ✅ Replaces the 20.0 kg default | Missing → must estimate, not invent |
| `weight_estimated` | Derived | bool | QWEN, EVAL | Lets the prompt say "estimated" instead of asserting | None — pure honesty gain |
| `allergies[]` | **Profile (auth.)** + query | Link → `allergies.json` key | PLAN, **SAFE**, QWEN | 🚨 Safety-critical | ✅ **10/24 avoid_foods resolve to nothing (D2)** |
| `unresolved_terms[]` | Derived | Set difference vs food DB | SAFE, QWEN, EVAL | Makes Finding 3 visible instead of silent | None — surfaces an existing failure |
| `conditions[]` | Profile / query | Link → `conditions.json` | PLAN, RAG, QWEN | Planner multiplier; 94 RAG records tagged | ⚠️ Filters to a 17% subset → over-filtering |
| `goals[]` | Profile / query | Link → `goals.json` | PLAN, RAG | ±300/−200 kcal | ⚠️ Only 19% of goal tags match food tags |
| `meal_slots[]` | Query | Map → 4 planner slots | ROUTE, PLAN, QWEN | Scopes "what for breakfast?" to one meal | ⚠️ 9 vocabularies in data vs 4 in planner (D5) |
| `foods_mentioned[]` | Query | Link → `food_name` | RAG, SAFE | "Is ragi good?" needs ragi identified | Gazetteer misses synonyms |
| `nutrients_mentioned[]` | Query | Link → `iron_mg` etc. | RAG, QWEN | Targets the answer | ✅ 58% of foods lack `iron_mg` |
| `diet_pattern` | Profile | Enum | PLAN | Major in the Indian context | Vocabulary not yet in food tags |
| `intent` | Derived | Rule over features | **ROUTE** | ✅ Replaces the 4-keyword test | Misroute → wrong prompt template |
| `is_medical_request` | Derived | Pattern + `medications[]` | SAFE, QWEN | Triggers the refusal script | False negative = unsafe |
| `escalate_to_clinician` | Derived | From `symptoms[]`/`medications[]` | SAFE | Points to a doctor, not a meal plan | ❌ No consumer exists yet |
| `source` (per field) | Derived | Enum | **QWEN**, EVAL | ✅ Stops the prompt asserting invented values as fact | None — this is the fix |
| `confidence` | Extractor | Float | SAFE, ROUTE | Enables caution | ⚠️ Uncalibrated number looks authoritative |
| `specificity_score` | Derived | Non-null ÷ total | QWEN, EVAL | "How much do we know about this child?" | Low value until validated |
| `nutrient_completeness` | **Document-side** | Count non-empty fields | PLAN, QWEN | ✅ Encodes Finding 1 — prefer well-characterised foods | Could over-restrict to 42 iron-known foods |
| `authority` | **Document-side** | Tier from `source` | RAG, QWEN | Prefer WHO/ICMR guidance | Needs manual tiering |

---

# 11. Real Query Examples

Each shows: raw → entities → normalized → derived → usage. ⚠️ These are **worked design examples**,
not system outputs — nothing here was executed.

### Example 1 — The clean case

> *"My 5 year old is allergic to peanuts and needs an iron-rich breakfast"*

| Stage | Result |
|---|---|
| **Entities** | `AGE "5 year old"` · `ALLERGEN "peanuts"` · `NUTRIENT "iron-rich"` · `MEAL_SLOT "breakfast"` |
| **Normalized** | `age_years 5.0` · `nut_allergy` · `iron_mg` · `breakfast` |
| **Derived** | `age_band preschool_3_6y` · `intent meal_plan` · `requires_planner true` |
| **RAG** | filter `{}` (no condition); query expanded with "iron" |
| **PLAN** | exclude nut foods; ⚠️ **`peanut_powder` unresolved — warn** |
| **QWEN** | "Age: 5 years (stated) · Allergies: peanut (STRICT) · Requested meal: breakfast" |
| **SAFE** | check answer's foods against nut exclusion |

### Example 2 — Missing age (the most common real case)

> *"What foods help with iron deficiency?"*

| Stage | Result |
|---|---|
| **Entities** | `CONDITION "iron deficiency"` · `NUTRIENT "iron"` |
| **Normalized** | `iron_deficiency_anemia` · `iron_mg` |
| **Merge** | ⚠️ No age in query. **Profile lookup.** If profile has age → use it. If not → `source: "absent"` |
| **Derived** | `intent condition_advice` · `requires_planner false` |
| **QWEN** | 🔷 **"Age: not specified"** — ✅ **not** the current `Age: 7.0 years old` |
| **Behaviour** | Answer general guidance **and ask for the child's age** |

🔷 **This is the single most valuable fix in the report.** ✅ Today this query produces a plan for a
fabricated 7-year-old, 20 kg, healthy child, and the prompt states those as facts.

### Example 3 — Multiple allergies and multiple conditions

> *"My 3 year old has anemia and is underweight. She's allergic to milk and eggs. What should I give her?"*

| Stage | Result |
|---|---|
| **Entities** | `AGE` · `CONDITION ×2` · `ALLERGEN ×2` |
| **Normalized** | `3.0` · `[iron_deficiency_anemia, underweight]` · `[milk, egg_protein]` |
| **⚠️ Truncation** | ✅ The planner takes `conditions[0]` and `goals[0]` — **singular**. The second condition is silently dropped |
| **🔷 Required** | Log the truncation; tell Qwen "multiple conditions mentioned: anemia, underweight — plan optimised for anemia" |
| **⚠️ Conflict** | Anemia wants iron-rich foods; milk allergy removes dairy; ✅ `egg_protein` appears on **8 foods** and `milk` on 4 — a large share of the 21 excludable foods |
| **RAG** | ⚠️ Filtering on one condition loses the other — argues for **soft boosting** over hard filtering |

### Example 4 — Ambiguous quantity

> *"Is 2 cups of milk a day too much for a 4 year old?"*

| Stage | Result |
|---|---|
| **Entities** | `QUANTITY "2"` · `UNIT "cups"` · `FOOD "milk"` · `AGE "4 year old"` |
| **⚠️ Ambiguity** | "cup" is not standard. US cup 240 ml; metric 250 ml; an Indian *katori* varies ~150–200 ml. ⚠️ **NOT VERIFIED** — our data has no cup definition |
| **Normalized** | `quantity {value: 2, unit: "cup", of: "milk", ml_estimate: 480, unit_confidence: "low"}` |
| **🔷 Required** | **Never silently pick 240 ml.** Either state the assumption in the answer or ask |
| **Derived** | `intent quantity_check` · `requires_planner false` ← ✅ note the current router sees no keyword and correctly routes to QA, but for the wrong reason |
| **⚠️ Gap** | ✅ **No component consumes `quantities[]`.** The LLM answers from context alone; no deterministic check exists. This is an honest gap |

### Example 5 — Contradiction between profile and query

> Profile: `{age: 2.0, allergies: ["nut_allergy"]}`
> Query: *"My 6 year old wants peanut butter — is that ok?"*

| Stage | Result |
|---|---|
| **Conflict 1** | Age: profile 2.0 vs query 6 → 🚨 **Use profile (2.0), flag it.** Possibly a sibling, possibly a stale profile |
| **Conflict 2** | Query implies peanut butter is acceptable; profile records a nut allergy |
| **🔷 Rule** | ✅ §5.2: **free text may tighten, never loosen.** The allergy stands |
| **Response** | Do not answer as if safe. Surface the conflict: *"Our records show a nut allergy and an age of 2. Please confirm which child this is for."* |
| **Why it matters** | 🔷 This is where fabricated-default logic would be actively dangerous — the system must prefer asking over guessing |

### Example 6 — Information in profile but not in query

> Profile: `{age: 0.6, condition: "infant_6_8_months", allergies: []}`
> Query: *"Can I give her rice?"*

| Stage | Result |
|---|---|
| **Entities** | `FOOD "rice"` only |
| **Merge** | Profile supplies age `0.6` years (≈7 months) and the band |
| **⚠️ Finding 9** | ✅ `condition: "infant_6_8_months"` is an **age band stored in the condition field** — D9 |
| **Derived** | `age_band infant_6_12m` · `intent food_safety` |
| **PLAN/RAG** | ⚠️ `foods.age_min` would answer this directly — **but the unit is ambiguous (Finding 2) and 44% are empty**, so it cannot be relied on |
| **Lesson** | 🔷 Query-side extraction contributed almost nothing here; **the profile did the work.** This is the strongest illustration that profile-side engineering matters more than query-side for a real application |

---

# 12. Benefits — What Evidence Actually Supports

**You asked me not to claim improvements without evidence. This section is deliberately conservative.**

## 12.1 ⚠️ The honest headline

**No published study evaluates feature engineering in a pediatric nutrition RAG system.** Any claim
that it will improve NutriBite's metrics is a **hypothesis to test**, not a finding to cite. Below I
separate what evidence exists from what does not.

| Claimed benefit | Evidence status | Source / reasoning |
|---|---|---|
| **Correctness: stop fabricating profile values** | ✅ **Not an empirical claim — a logical one** | ✅ Verified: `main.py:86-92` defaults, printed as fact in the prompt. Removing a falsehood does not need a paper |
| **Safety: allergen exclusion actually resolves** | ✅ **Logical, not empirical** | ✅ Verified: 10/24 `avoid_foods` resolve to nothing. Fixing it is a bug fix |
| Routing accuracy improves | 🔷 **Plausible, untested** | Intent classification is a mature task (ACM CSUR [10.1145/3547138](https://doi.org/10.1145/3547138)); Wang et al. EMNLP 2024 evaluate query classification in RAG ([ACL 2024.emnlp-main.981](https://aclanthology.org/2024.emnlp-main.981/)). ⚠️ Neither studies our system |
| Retrieval precision improves via metadata filtering | ⚠️ **Weak evidence; plausible it does NOT help here** | Documented pattern ([LangChain self-query](https://python.langchain.com/docs/how_to/self_query/), [LlamaIndex metadata](https://docs.llamaindex.ai/en/stable/module_guides/indexing/metadata_extraction/)) but these are vendor docs, not evaluations. ✅ On **781 vectors with cross-encoder reranking**, headroom may be small |
| Grounding / hallucination reduction | ⚠️ **Not supported for feature engineering** | Evidence exists for *retrieval-aware training* (RAFT — [arXiv:2403.10131](https://arxiv.org/abs/2403.10131)) and for context position (*Lost in the Middle* — [arXiv:2307.03172](https://arxiv.org/abs/2307.03172)). Neither is feature engineering |
| Personalization improves | 🔷 **Logical** | A plan computed from the real age differs from one computed from 7.0. Whether parents judge it better is unmeasured |
| Meal planning improves | 🔷 **Conditional on D1–D5** | ✅ With 58% of foods missing iron and 85% of condition tags unmatched, planner quality is currently bounded by **data**, not by features |
| Response consistency | ⚠️ **Confounded** | ✅ `temperature=0.1` with sampling is non-deterministic. Greedy decoding would do more for consistency than any feature |

## 12.2 🔷 What to tell your guide

> *"Feature engineering in NutriBite is primarily a **correctness and safety** intervention, and
> secondarily a possible retrieval improvement. The correctness part needs no evidence — the system
> currently fabricates child attributes and its allergy exclusions silently fail to resolve. The
> retrieval part is a hypothesis we propose to test, with a pre-stated possibility that it does not
> help on a corpus this small."*

That is a stronger and more defensible position than claiming improvements we cannot yet support.

---

# 13. Risks and Failure Modes

| # | Risk | Mechanism | Severity | 🔷 Mitigation |
|---|---|---|---|---|
| R1 | **Wrong allergen extraction** | Missed/misread allergen → unsafe recommendation | 🚨 **Critical** | Extraction may only **add** restrictions. Never remove a profile allergy from free text (§5.2). Low confidence still applies the restriction |
| R2 | **Wrong normalization** | "18 months" → 18.0 years | 🚨 Critical | Range validation (0–18); reject implausible; unit tests on the normalizer |
| R3 | **Over-filtering** | ✅ Condition filter → 17% subset; may yield <5 chunks | High | Mandatory fallback to unfiltered; measure empty-result rate; prefer **soft boosting** |
| R4 | **Missing values** | Parent gives no age | High | `source: "absent"` → render "not specified"; **ask**, never default |
| R5 | **Profile/query contradiction** | Example 5 | High | Profile wins on identity; surface the conflict; never silently overwrite |
| R6 | **Fabricated defaults** | ✅ `age=7.0, weight=20.0` asserted as fact | 🚨 **Critical, and live today** | Make `source: "default"` explicit, logged and visible in the prompt |
| R7 | **Stale profile data** | Child was 2 at registration, now 4 | High | Store `profile_updated_at`; treat age as derived from DOB, not stored as a number; re-confirm after a threshold |
| R8 | **Incorrect derived numbers** | ✅ Iron total summed over 42% of foods | High | `nutrient_completeness`; state coverage in the prompt; never present a partial total as complete |
| R9 | **Adult BMI thresholds on a child** | Misclassification | 🚨 Critical | Use **BMI-for-age z-scores** (§5.3) or omit entirely. ⚠️ We lack WHO LMS tables |
| R10 | **Feature leakage** | Gold `profile`/`relevant_chunk_ids` used as input during evaluation | High | ✅ Gold fields may be used **only** in a labelled "ceiling" condition, never in the reported system |
| R11 | **Excessive complexity** | 20 features, 3 consumers | Medium | ✅ §4.3 already excludes `frequency`/`duration`. Every feature needs a named consumer |
| R12 | **Increased prompt size** | More fields = more tokens | **Low** | ✅ We use ~1–2k of a 32,768 window. Measure, but this is not a real constraint |
| R13 | **Uncalibrated confidence** | `0.91` looks authoritative but is arbitrary | Medium | Do not show users; calibrate thresholds on NER eval data (`01` §9 E0) |
| R14 | **Silent truncation** | ✅ `conditions[0]` drops the second condition | Medium | Log it; surface in the prompt (Example 3) |
| R15 | **Broken joins stay silent** | ✅ `peanut_powder` matches nothing, no error | 🚨 **Critical** | `unresolved_terms` in the schema (§7.1); fail loudly |
| R16 | **Evaluation circularity** | Qwen extracts, answers, and a sibling LLM judges | Medium | Prefer gazetteer extraction; disclose if LLM extraction is used |
| R17 | **Over-trusting the gazetteer** | "finger millet" absent → ragi missed | Medium | Curate aliases; measure recall (E0); consider GLiNER as backup |

---

# 14. What We Can Implement Without Fine-Tuning

**✅ Answer: essentially all of it. Nothing in this report requires fine-tuning.**

| Component | Needs training? | Why not | Works with our data? |
|---|---|---|---|
| Gazetteer NER | ❌ No | ✅ Our DB *is* the gazetteer: 99 foods, 173 conditions, 148 goals, 15 allergies, 133 food tags | ✅ Yes |
| Regex for age/quantity/weight | ❌ No | Pattern matching | ✅ Yes |
| Normalization / unit conversion | ❌ No | Deterministic rules | ✅ Yes |
| Validation | ❌ No | Range + existence checks | ✅ Yes |
| Profile merge (§5.2) | ❌ No | Policy rules | ✅ Yes |
| `age_band` derivation | ❌ No | Binning | ✅ Yes |
| Intent routing (rules) | ❌ No | Rules over features | ✅ Yes |
| Metadata filtering | ❌ No | ✅ Service already exists | ⚠️ Needs D7 first |
| Allergen safety validator | ❌ No | Set intersection | ⚠️ Needs D2/D3 first |
| Document metadata back-fill | ❌ No | Gazetteer over 558 records offline | ✅ Yes |
| Prompt restructuring | ❌ No | String assembly | ✅ Yes |
| — | — | — | — |
| Trained intent classifier | ✅ Yes | Would need labelled queries | ❌ Optional only |
| Fine-tuned domain NER | ✅ Yes | Would need annotated spans | ❌ Optional only |
| GLiNER zero-shot NER | ❌ No | Zero-shot by design | ✅ Yes — research comparison |

🔷 **The reason the gazetteer approach is so well-suited here is worth stating plainly:** in a general
NLP setting, dictionary matching is a weak baseline. In *our* setting it is unusually strong, because
the dictionary entries **are already the canonical database keys**. Matching and entity linking
collapse into one lookup — a `FOOD` match is directly a `food_name`. That is a genuine architectural
advantage, not a compromise.

---

# 15. Recommended Practical Architecture

## 15.1 🔷 Scope for a B.Tech project

### Tier 1 — Should be implemented (highest value, lowest risk)

| # | Item | Why | Depends on |
|---|---|---|---|
| T1 | **Feature schema with `source` provenance** (§7) | ✅ Fixes a live correctness defect: fabricated values asserted as fact | — |
| T2 | **Gazetteer + regex extractor** | Free from existing data; deterministic; auditable | — |
| T3 | **Normalization + validation layer** | ✅ Without it, "peanuts" never reaches `nut_allergy` | T2 |
| T4 | **Profile merge with precedence rules** (§5.2) | ✅ Correct design for the real full-stack app | T3 |
| T5 | **D1: resolve `age_min` unit ambiguity** | ✅ Blocks all age features | Author's input |
| T6 | **D2: fix the allergy join** | 🚨 ✅ 10/24 resolve to nothing — safety defect | — |
| T7 | **D8: `""` → `null` + `*_known` flags** | ✅ Stops meaningless nutrient totals | — |
| T8 | **Truthful prompt block** ("not specified") | ✅ Removes false premises from the prompt | T1 |

### Tier 2 — Optional, good if time allows

| # | Item | Why | Risk |
|---|---|---|---|
| T9 | D7: `age_band` back-fill on RAG records | Enables age filtering | Manual effort |
| T10 | D3: back-fill `allergy_tags` on 78 foods | Widens exclusion beyond 21 foods | Needs care |
| T11 | Activate metadata filtering | Uses the dormant service | ⚠️ May not help (§12) |
| T12 | Feature-based routing | ✅ Replaces the 4-keyword test | Low |
| T13 | Post-generation allergen validator | 🔷 Highest real-world safety value | ⚠️ Can't be scored — 0 Violation labels |
| T14 | D4: tag-vocabulary mapping layer | ✅ 85% of condition filtering can't fire | Large manual effort |

### Tier 3 — Unnecessary for this project

| Item | Why not |
|---|---|
| Numerical scaling / log transforms | ✅ No trained numeric model exists (§3.6) |
| One-hot encoding | Qwen consumes text |
| BMI-for-age z-scores | ⚠️ Needs WHO LMS tables + clinical sign-off (§5.3) |
| FoodOn/SNOMED mapping | Mapping cost exceeds the benefit at 99 foods |
| `frequency` / `duration` extraction | ✅ No consumer (§4.3) |
| Trained intent classifier | Rules suffice; no labelled data |
| Internal representation methods | Different field (§2.6) |

## 15.2 🔷 Suggested build order

```
Week 1  T5 (age_min unit) ──► T6 (allergy join) ──► T7 (null handling)
        └─ data fixes first: everything downstream depends on them

Week 2  T1 (schema) ──► T2 (gazetteer) ──► T3 (normalize/validate)

Week 3  T4 (profile merge) ──► T8 (truthful prompt)
        └─ measurable correctness win, independent of retrieval results

Week 4  Measure: F2 metadata coverage (no LLM calls)
        └─ decide whether T9/T11 are worth doing at all

Week 5+ T12 routing ──► T13 safety validator (if data allows)
```

🔷 **Rationale for putting data fixes first:** T6 is a safety defect; T5 blocks a feature class; T7
stops the system reporting partial nutrient totals as complete. All three are cheap, and every
feature-engineering benefit downstream is bounded by them.

---

# 16. Research Gaps / Future Work

## 16.1 ⚠️ Honest gaps in this report

| Gap | Status |
|---|---|
| `age_min` unit (months vs years) | ⚠️ **NOT VERIFIED** — needs the file author |
| Indian household measures (*katori*, *cup*) in ml | ⚠️ **NOT VERIFIED** — no standard found in our data |
| Whether metadata filtering helps on 781 vectors | ⚠️ **Untested hypothesis** |
| Whether the gazetteer covers Indian food synonyms | ⚠️ **Unmeasured** (ragi/finger millet/nachni) |
| Confidence-threshold calibration | 🔷 Proposed values are guesses until E0 runs |
| Whether parents find personalised answers better | ⚠️ No user study; outside scope |

## 16.2 🔷 Future work

1. **BMI-for-age z-scores** using WHO LMS reference tables, with clinician review.
2. **Multi-turn dialogue state tracking** — the natural extension once the app has conversations
   (MultiWOZ-style; [arXiv:1810.00278](https://arxiv.org/abs/1810.00278)).
3. **Food ontology alignment** to FoodOn/LanguaL if the food DB grows past a few hundred items.
4. **Authority-tiered retrieval** preferring WHO/ICMR sources.
5. **Representation-engineering safety monitoring** (§2.6) — the one legitimate connection to the
   internal-features field, as a complement to (not a replacement for) the rule-based validator.

## 16.3 🔷 Proposed experiments

Carried forward from the earlier version of this document, with the statistical discipline in
`01_NER_RESEARCH.md` §9.1 (paired comparison, bootstrap CIs, exploratory framing at n=41).

| ID | Experiment | Conditions | Metrics | LLM calls? |
|---|---|---|---|---|
| **F1** | Structured profile injection | A: current defaults · B: "not specified" · C: gold profile (22 cases) | Faithfulness, Answer Relevancy, Hallucination Rate, **+ new false-premise rate** | 🔴 Yes |
| **F2** | **Document metadata back-fill coverage** | Gazetteer over all 558 records | **Coverage %** of `condition`/`age_band`/`allergen` | 🟢 **None** |
| **F3** | BM25 query expansion | A: raw query · B: query + canonical terms | Recall@5, MAP@5 in **bm25-only** mode | 🟢 None |
| **F4** | Adaptive fusion weight α | A: fixed 0.7 · B: 0.5 if ≥2 linked entities | Recall@5, MAP@5, MRR@5 | 🟢 None |
| **F5** | 🔷 **Join-integrity audit** | Measure resolution rates before/after D2–D4 | % of allergy/condition/goal tags that resolve | 🟢 **None** |

🔷 **Run F2 and F5 first.** They require **no LLM calls**, and F2 determines whether the filtering
experiments (F1/T11) are viable at all — ✅ given that 0% of records carry age metadata and only 17%
carry a condition.

**Note on F4:** ✅ with 781 vectors and a cross-encoder reranking the top 20, α may matter very little,
because the reranker can recover from first-stage ordering errors. A null result is a finding.

---

# 17. References

**Feature engineering — foundations**
- Domingos, *A Few Useful Things to Know About Machine Learning*, CACM 55(10), 2012 — [DOI 10.1145/2347736.2347755](https://doi.org/10.1145/2347736.2347755)
- Zheng & Casari, *Feature Engineering for Machine Learning*, O'Reilly, 2018
- Kuhn & Johnson, *Feature Engineering and Selection*, CRC Press, 2019 — [feat.engineering](http://www.feat.engineering/)
- Bengio, Courville & Vincent, *Representation Learning: A Review and New Perspectives*, IEEE TPAMI 35(8), 2013 — [arXiv:1206.5538](https://arxiv.org/abs/1206.5538)
- Little & Rubin, *Statistical Analysis with Missing Data*, Wiley — [DOI 10.1002/9781119482260](https://doi.org/10.1002/9781119482260)

**Query understanding — intent detection and slot filling**
- Weld et al., *A Survey of Joint Intent Detection and Slot Filling Models in NLU*, ACM Computing Surveys, 2022 — [DOI 10.1145/3547138](https://doi.org/10.1145/3547138)
- Budzianowski et al., *MultiWOZ*, EMNLP 2018 — [arXiv:1810.00278](https://arxiv.org/abs/1810.00278)
- Hemphill, Godfrey & Doddington, *The ATIS Spoken Language Systems Pilot Corpus*, 1990
- Zaratiana et al., *GLiNER*, NAACL 2024 — [arXiv:2311.08526](https://arxiv.org/abs/2311.08526)

**RAG and retrieval**
- Lewis et al., *Retrieval-Augmented Generation*, NeurIPS 2020 — [arXiv:2005.11401](https://arxiv.org/abs/2005.11401)
- Robertson & Zaragoza, *BM25 and Beyond*, FnTIR, 2009 — [DOI 10.1561/1500000019](https://doi.org/10.1561/1500000019)
- Wang et al., *Searching for Best Practices in RAG*, EMNLP 2024 — [ACL 2024.emnlp-main.981](https://aclanthology.org/2024.emnlp-main.981/) · [arXiv:2407.01219](https://arxiv.org/abs/2407.01219)
- Liu et al., *Lost in the Middle*, TACL 2024 — [arXiv:2307.03172](https://arxiv.org/abs/2307.03172)
- Zhang et al., *RAFT: Adapting Language Model to Domain Specific RAG* — [arXiv:2403.10131](https://arxiv.org/abs/2403.10131)
- [LangChain Self-Querying Retriever](https://python.langchain.com/docs/how_to/self_query/) · [LlamaIndex Metadata Extraction](https://docs.llamaindex.ai/en/stable/module_guides/indexing/metadata_extraction/)

**Nutrition, clinical and ontology standards**
- WHO, *BMI-for-age* — [who.int](https://www.who.int/toolkits/child-growth-standards/standards/body-mass-index-for-age-bmi-for-age)
- WHO, *Child Growth Standards* — [who.int](https://www.who.int/tools/child-growth-standards/standards/weight-for-age)
- Furlong et al., *Misclassification of child BMI from cut-points defined by rounded percentiles instead of Z-scores* — [PMC5706297](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5706297/)
- WHO/UNICEF, *Indicators for assessing infant and young child feeding practices*, 2021 — [WHO 9789240018389](https://www.who.int/publications/i/item/9789240018389)
- Dooley et al., *FoodOn: a harmonized food ontology*, npj Science of Food 2, 2018 — [DOI 10.1038/s41538-018-0032-6](https://doi.org/10.1038/s41538-018-0032-6) · [foodon.org](https://foodon.org/)
- [UCUM — Unified Code for Units of Measure](https://ucum.org/)
- [SNOMED CT](https://www.snomed.org/)
- ICMR-NIN, *Indian Food Composition Tables 2017* — [nin.res.in](https://www.nin.res.in/ebooks/IFCT2017.pdf)

**Related but different — internal representations (§2.6)**
- Zou et al., *Representation Engineering: A Top-Down Approach to AI Transparency* — [arXiv:2310.01405](https://arxiv.org/abs/2310.01405)
- *Are Sparse Autoencoders Useful? A Case Study in Sparse Probing* — [arXiv:2502.16681](https://arxiv.org/abs/2502.16681)

**Companion reports in this repository**
- [00_CURRENT_ARCHITECTURE.md](00_CURRENT_ARCHITECTURE.md) — verified current system (⚠️ §2.2 path correction in §3.1 above)
- [01_NER_RESEARCH.md](01_NER_RESEARCH.md) — entity extraction approaches and experiments
- [07_FINETUNING_FEASIBILITY_RESEARCH.md](07_FINETUNING_FEASIBILITY_RESEARCH.md) — why no fine-tuning is assumed
- [MASTER_RESEARCH_ROADMAP.md](MASTER_RESEARCH_ROADMAP.md) — overall prioritisation
