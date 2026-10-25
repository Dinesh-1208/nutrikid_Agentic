# 00 — Current Architecture of KidsNutriBite (As Implemented)

**Status:** Verified by direct source inspection on 2026-09-18. Every claim below is traceable to a file
and line in this repository. Anything I could not verify from code is explicitly marked
**NOT VERIFIED FROM CODE**.

**Scope note:** This document describes *what exists today*, not what is planned. The research reports
01–07 propose extensions; they must be read against this baseline.

---

## 1. Top-Level Shape of the System

KidsNutriBite is a **command-line research prototype**, not a web application.

- There is **no frontend** — no HTML, JS, React, Streamlit, Gradio or template directory exists.
- There is **no backend web service** — no Flask, FastAPI, Django, `uvicorn`, or route definitions exist.
- The single entry point is `main.py`, an `argparse` CLI whose own description string is
  `"KidsNutriBite Research Prototype CLI"` (`main.py:6`).

> ⚠️ **Documentation risk.** Any paper, slide or report describing a "frontend", "web UI",
> "REST API", "mobile app" or "user dashboard" would be describing something that does not exist in
> this repository. This is the single most important thing to keep straight when writing up the project.

### 1.1 The five CLI modes

| Flag | Purpose | Code |
|---|---|---|
| `--index` | Build the FAISS index from `data/rag/rag_data.json` | `main.py:37-42` |
| `--query <text>` | Debug semantic search only (prints retrieved chunks) | `main.py:44-48` |
| `--plan` | Run the deterministic diet planner only (no LLM, no RAG) | `main.py:50-69` |
| `--ask <text>` | **The full production pipeline**: retrieve → route → prompt → generate | `main.py:71-125` |
| `--evaluate` | Run the evaluation/comparison benchmark | `main.py:127-144` |

These sit in a `add_mutually_exclusive_group(required=True)` (`main.py:9`), so exactly one runs per invocation.

### 1.2 End-to-end control flow for `--ask`

```
  user query (string)                      CLI profile flags (--age --weight
        |                                   --condition --goal --allergies)
        |                                            |
        v                                            v
  KidsNutriRetriever.retrieve(query, top_k=5)   profile dict (hardcoded defaults:
        |                                        age=7.0, weight=20.0,
        |                                        condition="healthy_growth",
        |                                        goal="balanced_nutrition")
        v                                            |
  5 parent-expanded context chunks                   |
        |                                            |
        +---------------------+----------------------+
                              v
        Intent routing: 4-keyword substring test
        ["plan","diet","meal","menu"] in query.lower()
                              |
             +----------------+-----------------+
         TRUE|                                  |FALSE
             v                                  v
  DietPlanner.generate_meal_plan        (planner skipped)
             |                                  |
             v                                  v
  generate_llm_prompt(plan,           generate_qa_prompt(profile,
      contexts, query)                    contexts, query)
             |                                  |
             +----------------+-----------------+
                              v
         KidsNutriLLMClient.generate_response(
             system_prompt, user_prompt, model="qwen_local")
                              v
               Qwen2.5-7B-Instruct (4-bit, local)
                              v
                       answer + latency
```

Source: `main.py:71-125`.

---

## 2. Data Layer (Verified by Counting the Actual Files)

### 2.1 RAG knowledge corpus — `data/rag/rag_data.json`

| Property | Value |
|---|---|
| Records | **558** |
| Mean `text` length | **133.9 characters** |
| Max `text` length | **567 characters** |
| Metadata key `type` | present on 558 records (100%) |
| Metadata key `tags` | present on 402 records |
| Metadata key `condition` | present on 94 records |
| Metadata key `source` | present on 63 records |
| Metadata key `food_name` | present on 13 records |
| Metadata key `goal` | present on 13 records |
| Distinct `type` values | 147 |
| Distinct `tags` values | 888 |

### 2.2 Structured nutrition database — `data/structured_db/`

> **Correction (2026-09-23):** an earlier draft of this document gave the path as `data/db/`.
> The actual path is **`data/structured_db/`**.

| File | Records | Core schema (present on 100% of records) |
|---|---|---|
| `foods.json` | 99 | 19 fields incl. `food_id`, `food_name`, `category`, `energy_kcal_per_100g`, `protein_g`, `fat_g`, `carbs_g`, `iron_mg`, `age_min`, `allergy_tags`, `meal_types`, `tags` |
| `conditions.json` | 173 | `condition_name`, `required_tags`, `avoid_tags`, `meal_pattern` |
| `goals.json` | 148 | `goal_name`, `required_tags`, `avoid_tags`, `meal_frequency` |
| `allergies.json` | 15 | `allergy`, `avoid_foods`, `severity` |

Beyond that core, the files carry a **long tail of optional keys** — ~22 additional keys in
`foods.json` (appearing on 1–39 records) and ~45 in `conditions.json` (mostly on 1–3 records).
**No code reads the long tail.**

> ⚠️ **Data-quality defects verified by counting on 2026-09-23.** These materially affect the planner
> and are documented in full in [02_FEATURE_ENGINEERING_RESEARCH.md](02_FEATURE_ENGINEERING_RESEARCH.md) §3.4:
>
> - **`iron_mg` is an empty string on 57/99 foods (58%)**; `energy_kcal_per_100g` on 38/99 (38%);
>   `fat_g` and `carbs_g` on 50/99 each. The planner nonetheless sums these and
>   `prompt_templates.py` renders `Planned Iron: … mg` into the prompt as if complete.
> - **`allergy_tags` is empty on 78/99 foods (79%)**; the whole vocabulary is 7 tags.
> - **10 of 24 `avoid_foods` strings in `allergies.json` match nothing** in `foods.json` — including
>   `peanut_powder`, `wheat`, `barley`, `rye`, `sesame_powder`. **Those exclusions silently fail.**
> - **`allergies.json` contains duplicate allergy names** (`egg_protein` ×3, `milk` ×3, `fish` ×2) —
>   ~10 distinct allergies across 15 records.
> - **Only 15.1% of `conditions.json` tags and 19.0% of `goals.json` tags match any food tag**, so
>   most condition/goal-driven food filtering cannot fire.
> - **`age_min` is empty on 44/99 and its unit is ambiguous** (values 1, 2, 6, 8, 9, 12 — months or
>   years is undetermined). ⚠️ NOT VERIFIED.
> - **`meal_types` uses 9 distinct values** but the planner emits only 4 meals, leaving 17 foods
>   unreachable.

### 2.3 Evaluation benchmark — `evaluation/dataset.py`

| Property | Value |
|---|---|
| Cases | **49** |
| Fields per case | `id`, `question`, `category`, `subcategory`, `age_group`, `knowledge_area`, `source_scope`, `profile`, `relevant_chunk_ids`, `gold_facts`, `reference_answer`, `safety_ground_truth`, `annotation_status`, `annotation_notes` |
| Cases with non-empty `relevant_chunk_ids` (RAG-applicable) | **41 / 49** |
| Cases with a non-null `profile` | **22 / 49** |
| `source_scope` distribution | `rag` = 33, `structured_db` = 10, `both` = 6 |
| Distinct `age_group` strings | **17** (free-text, not a controlled vocabulary) |
| `safety_ground_truth = "Compliant"` | 20 |
| `safety_ground_truth = None` | 29 |
| `safety_ground_truth = "Violation"` | **0** |

> ⚠️ **Evaluation risk, already acknowledged in the CLI help text.** Because there are **zero**
> `"Violation"`-labelled cases, Safety Recall / Precision / F1 are **mathematically undefined**
> on the current benchmark (the positive class is empty → recall has a zero denominator). The CLI
> flag `--skip-safety-evaluation` documents exactly this in `main.py:28`. No safety-detection
> performance claim can currently be substantiated by this dataset.

---

## 3. Indexing Pipeline (`--index`)

### 3.1 Parent–child chunking — `rag/chunker.py`

`ParentChildChunker` is configured from `RAGConfig` (`rag/services/config_service.py`):

| Parameter | Default value |
|---|---|
| `parent_chunk_size` | 600 characters |
| `child_chunk_size` | 150 characters |
| `child_overlap` | 30 characters |

The design intent is the standard "small-to-big" retrieval pattern: embed **small children** for
precise matching, but hand the **large parent** to the LLM for context
([LlamaIndex, *Auto-Merging / Parent Document Retriever*](https://docs.llamaindex.ai/en/stable/examples/retrievers/auto_merging_retriever/);
[LangChain, *ParentDocumentRetriever*](https://python.langchain.com/docs/how_to/parent_document_retriever/)).

### 3.2 ⚠️ Finding: the chunking is **degenerate on this corpus**

Measured on the actual built index:

| Measurement | Value |
|---|---|
| Parent chunks | **558** |
| Child chunks | **781** |
| Mean children per parent | **1.40** |
| Parents with exactly **one** child | **357 (64.0%)** |
| Source records ≤ 600 chars (the parent limit) | **558 / 558 = 100%** |

**Consequences:**

1. The **parent split never fires**. Every source record is shorter than `parent_chunk_size = 600`,
   so "1 record → 1 parent" always holds. The 600-character parameter is inert.
2. For **64% of parents, the child *is* the parent** (record ≤ 150 chars → one child covering the
   whole text). For those, parent expansion is a no-op and the small-to-big mechanism provides
   **zero additional context**.
3. The remaining 36% split into 2–4 children with 30-character overlap.

This is a legitimate, citable research finding about the current system and a strong motivation for
the chunking experiments proposed in `05_HYPERPARAMETER_OPTIMIZATION_RESEARCH.md`. It should **not**
be presented as though hierarchical chunking were delivering its textbook benefit here.

### 3.3 Embedding and index construction — `rag/indexer.py`

- Embedding model: **`BAAI/bge-small-en-v1.5`** (`RAGConfig.embedding_model`), loaded via
  `sentence-transformers`. Paper: Xiao et al., *C-Pack: Packed Resources for General Chinese
  Embeddings*, SIGIR 2024 — [arXiv:2309.07597](https://arxiv.org/abs/2309.07597),
  [ACM DL 10.1145/3626772.3657878](https://dl.acm.org/doi/10.1145/3626772.3657878). Model card:
  [huggingface.co/BAAI/bge-small-en-v1.5](https://huggingface.co/BAAI/bge-small-en-v1.5).
- Embeddings are **L2-normalised**, so inner product ≡ cosine similarity.
- Index type: **`faiss.IndexFlatIP(d)`** with `d = embeddings.shape[1]` (`rag/indexer.py`).
  `IndexFlatIP` is a brute-force **exact** index — no ANN approximation, no quantisation, no training
  step ([FAISS wiki, *Guidelines to choose an index*](https://github.com/facebookresearch/faiss/wiki/Guidelines-to-choose-an-index)).
  FAISS paper: Douze et al., *The Faiss library* — [arXiv:2401.08281](https://arxiv.org/abs/2401.08281).

Verified from the **built artifact** on disk:

```
faiss.index  ->  ntotal = 781,  d = 384,  type = IndexFlatIP
```

So the embedding dimension is **384**, confirmed empirically rather than assumed.

Persisted artifacts: `faiss.index`, `metadata.pkl` (child_chunks, parent_chunks, parent_map,
raw_documents, dataset_hash, config), `dataset_hash.txt`.

---

## 4. Retrieval Pipeline (`rag/services/retrieval_service.py`)

This is the canonical, verified order of operations:

| # | Step | Service | Key detail |
|---|---|---|---|
| 1 | Embed query | `EmbeddingService` | Same `bge-small-en-v1.5`, normalised |
| 2 | **Semantic cache lookup** | `CacheService` | Cosine ≥ `0.95` → **early return**, rest of pipeline skipped |
| 3 | Dense search | FAISS | `fetch_n = max(rerank_top_n, k*3)` = `max(20, 15)` = **20** |
| 4 | Sparse search | `BM25Service` | Top-20 over the same child chunks |
| 5 | **Fusion** | `FusionService` | `score = α·dense + (1−α)·bm25`, **α = 0.7** |
| 6 | Metadata filter | `MetadataFilterService` | **Only applied if the caller passes `filters`** |
| 7 | **Rerank** | `CrossEncoder` | Pool of 20 → **top 5** |
| 8 | **Parent expansion** | `PromptContextService` | Child ID → parent text |
| 9 | Cache store + logging | `CacheService` | Keyed on the normalised query |

### 4.1 Sparse retrieval — `rag/services/bm25_service.py`

- Implementation: `rank_bm25.BM25Okapi` over the **child** chunks.
- Tokeniser: `re.findall(r'\w+', text.lower())` — no stemming, no stop-word removal, no lemmatisation.
- Scores are **min–max normalised within the returned top-k batch** before fusion (necessary because
  raw BM25 scores are unbounded while cosine ∈ [−1, 1]).
- Theory: Robertson & Zaragoza, *The Probabilistic Relevance Framework: BM25 and Beyond*,
  Foundations and Trends in Information Retrieval 3(4), 2009 —
  [DOI 10.1561/1500000019](https://doi.org/10.1561/1500000019).
- Library: [rank_bm25 on PyPI](https://pypi.org/project/rank-bm25/).

> ⚠️ `bm25_service` **accepts a `metadata_filters` parameter but never uses it in the function body.**
> Sparse retrieval is therefore entirely unfiltered.

### 4.2 Fusion — `rag/services/fusion_service.py`

```
fused_score = alpha * dense_score + (1.0 - alpha) * bm25_score      # alpha = 0.7
```

This is **weighted linear score fusion**, *not* Reciprocal Rank Fusion. RRF
(Cormack, Clarke & Büttcher, SIGIR 2009 — [DOI 10.1145/1571941.1572114](https://doi.org/10.1145/1571941.1572114))
is rank-based and score-scale-free; linear fusion is score-based and requires the normalisation
described above. Write-ups must not call this RRF.

Dense retrieval background: Karpukhin et al., *Dense Passage Retrieval for Open-Domain Question
Answering*, EMNLP 2020 — [arXiv:2004.04906](https://arxiv.org/abs/2004.04906).

### 4.3 Metadata filtering — `rag/services/metadata_filter_service.py`

**This component is effectively dormant.** Verified facts:

1. It is applied **only when the caller passes a `filters` dict**. `main.py:99` calls
   `retriever.retrieve(args.ask, top_k=5)` — **no filters**. `evaluation/evaluator.py` likewise
   passes none. So in both the production path and the evaluation path, **no metadata filtering
   ever occurs**.
2. Even if filters were passed, the implementation handles only `condition`, `goal` and `category`
   as **string-equality** tests.
3. The list branch is literally `elif isinstance(val, list): pass` — a **no-op**. Allergy lists,
   the most safety-relevant filter imaginable, would be silently ignored.
4. There is **no `age_group` handling**, despite the docstring mentioning age.

This is the largest piece of latent, unexploited machinery in the codebase, and it is the main
structural reason the NER / feature-engineering work in reports `01` and `02` is worth doing:
**those reports supply exactly the filter dict this service is waiting for.**

### 4.4 Reranking

- Model: **`cross-encoder/ms-marco-MiniLM-L-6-v2`**, loaded via `sentence_transformers.CrossEncoder`.
  Model card: [huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2](https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2).
- Method: cross-encoder re-ranking of a first-stage candidate list — Nogueira & Cho,
  *Passage Re-ranking with BERT* — [arXiv:1901.04085](https://arxiv.org/abs/1901.04085).
- Training data: MS MARCO passage ranking — Nguyen et al. —
  [arXiv:1611.09268](https://arxiv.org/abs/1611.09268).
- Backbone: MiniLM — Wang et al., NeurIPS 2020 — [arXiv:2002.10957](https://arxiv.org/abs/2002.10957).
- Config: `rerank_top_n = 20` (candidate pool), `top_k = 5` (survivors), `enable_reranking = True`.

> ⚠️ **Domain-shift caveat for the write-up.** This reranker is trained on general web
> search relevance (MS MARCO), not on pediatric-nutrition or clinical text. Its relevance judgements
> are *out-of-domain* for this corpus. That is a legitimate limitation to state, and a tunable
> described in `05_HYPERPARAMETER_OPTIMIZATION_RESEARCH.md`.

### 4.5 Parent expansion — `rag/services/prompt_context_service.py`

Expansion happens **after** reranking, not before. Each final item carries:
- `"text"` → the **parent** text (what the LLM sees)
- `"child_text"` → the original child (what was actually matched)

Because of §3.2, for 64% of records these two strings are identical.

### 4.6 Semantic cache — `rag/services/cache_service.py`

- `OrderedDict`-based **LRU**, `max_size = 1000`.
- Exact-match fast path on the normalised query string; otherwise cosine similarity against every
  cached embedding, accepting the best if `score ≥ 0.95`.
- **Dataset-hash invalidation**: entries whose `dataset_hash` differs from the current index hash are
  deleted on lookup, so rebuilding the index correctly invalidates stale entries.
- Tracks `hits`, `misses`, `evictions`, `hit_ratio`.

> ⚠️ **Evaluation-integrity note.** The cache returns a hit for any query within cosine 0.95 of a
> previous one. In a benchmark run, near-duplicate questions could be served cached contexts. This
> does not appear to be controlled for in `evaluation/evaluator.py`. Worth stating as a threat to
> validity, and trivially removable for experiments by setting `enable_cache = False`.

---

## 5. Intent Routing / "Agent" Layer

The system's routing logic is, in full (`main.py:103-105`):

```python
query_lower = args.ask.lower()
diet_keywords = ["plan", "diet", "meal", "menu"]
is_diet_request = any(kw in query_lower for kw in diet_keywords)
```

That is the **entire** agentic layer: a case-insensitive substring test against four words.

There is **no** LLM-based routing, no trained intent classifier, no tool-calling, no ReAct loop, no
multi-agent orchestration, and no `langgraph` / `crewai` / `autogen` dependency.

Known failure modes of this rule, by construction:
- **False positives:** *"Is a **meal** replacement shake safe for a 6-year-old?"* → contains "meal" →
  routes to the planner and generates a full diet plan for what is a pure QA question.
- **False negatives:** *"What should my 5-year-old eat tomorrow?"* → contains none of the four
  keywords → routed to QA, planner never invoked.

This is the most obviously improvable component in the system and a direct target for the
NER/feature-based routing experiment in `01_NER_RESEARCH.md` §7.

---

## 6. Deterministic Diet Planner (`planner/diet_planner.py`)

`KidsNutriDatabase` loads `foods.json`, `conditions.json`, `goals.json`, `allergies.json`.

`DietPlanner.calculate_calories`:
- Base energy from the **Holliday–Segar** method (named in the source comment). Original:
  Holliday & Segar, *The maintenance need for water in parenteral fluid therapy*, Pediatrics 19(5),
  1957 — [DOI 10.1542/peds.19.5.823](https://doi.org/10.1542/peds.19.5.823). Note the formula's
  original purpose is **maintenance fluid/energy expenditure estimation**, not dietary energy
  prescription — worth stating as a modelling assumption rather than a clinical guideline.
- Goal adjustment by **keyword match** on the goal string: **+300 kcal** surplus / **−200 kcal** deficit.
- Condition adjustment: multiplier **1.12**.

`DietPlanner.generate_meal_plan`:
- Splits target calories **breakfast 25% / lunch 35% / dinner 30% / snack 10%**.
- Filters foods by tags (condition-recommended, goal-recommended, allergy-excluded).
- Greedily fills each meal until it reaches **95%** of that meal's calorie target.

> ⚠️ The **weekly** planner `generate_weekly_meal_plan` (which additionally computes macro targets and
> a fibre target `(calories/1000)*14.0`) is **never called by `main.py` or `evaluation/evaluator.py`**.
> Its only caller in the repository is `planner/test_weekly_planner.py`. It is dead code with respect
> to the production and evaluation paths and must not be presented as a live system feature.

**Important framing point:** all nutrition arithmetic is deterministic Python. The LLM is explicitly
forbidden from doing arithmetic (`SYSTEM_PROMPT`, `llm/prompt_templates.py:11`: *"Do NOT perform any
math or recalculate calorie/nutrient values"*). This is a genuine and defensible safety-architecture
decision worth highlighting: **numbers come from code, prose comes from the model.**

---

## 7. LLM Layer (`llm/llm_client.py`)

### 7.1 Production generation backend

- Model: **`Qwen/Qwen2.5-7B-Instruct`**, run **locally** through the Hugging Face
  `transformers.pipeline` API (`_call_local_transformers`).
- Quantisation: `BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
  bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.float16)`.
  NF4 and double quantisation are both introduced in **QLoRA** — Dettmers et al., NeurIPS 2023 —
  [arXiv:2305.14314](https://arxiv.org/abs/2305.14314). Library:
  [bitsandbytes](https://github.com/bitsandbytes-foundation/bitsandbytes).
- Placement: `device_map="auto"` (HF Accelerate).
- Decoding: `temperature = 0.1`, `top_p = 0.9`, `max_new_tokens = 1024`.

### 7.2 Other registered backends

`gemini`, `qwen`, `llama`, `groq_judge`, `groq_llama8b`, `groq_qwen` are selectable via `--model`
(`main.py:31`), but `qwen_local` is the default and the documented production path.

`"groq_judge"` maps to Groq-hosted **`openai/gpt-oss-120b`**.

> ⚠️ **Correction that must propagate to the paper and slides.** Any table row stating the LLM judge
> is *Llama-3.3-70B (Groq-hosted)* is **wrong**. `llm/llm_client.py` documents that
> `llama-3.3-70b-versatile` was not available on the account used, and `groq_llama70b` is retained
> only as a deprecated alias. The judge actually used is **`openai/gpt-oss-120b` (Groq-hosted)**.

### 7.3 Prompting — `llm/prompt_templates.py`

Two system prompts, selected by the keyword router:

| | `SYSTEM_PROMPT` (diet mode) | `QA_SYSTEM_PROMPT` (QA mode) |
|---|---|---|
| Role framing | "Senior Pediatric Dietitian and Nutrition Safety Expert" | same |
| No diagnosis / no prescription, with a **verbatim refusal script** | yes | yes |
| "Do not invent or extrapolate medical claims" | yes | yes |
| Allergy respect | yes | yes |
| **"Do NOT perform any math"** | yes | no (not needed — no numbers passed) |
| Response structure | 4 sections incl. meal walkthrough | 3 sections |

RAG chunks are injected in the format

```
- [ID: {id}, Relevance Score: {score}] {text}
```

— i.e. the model is shown chunk IDs and fusion scores. This is what makes citation-style grounding
checks possible downstream.

RAG background: Lewis et al., *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*,
NeurIPS 2020 — [arXiv:2005.11401](https://arxiv.org/abs/2005.11401).

---

## 8. Evaluation Pipeline (`evaluation/`)

- `evaluation/evaluator.py` — `KidsNutriEvaluator`; computes retrieval and generation metrics.
  Uses `top_k = 5` for all retrieval metrics. **Always calls `generate_llm_prompt` (diet mode)** —
  the QA prompt is never exercised in evaluation, even though `main.py` uses it for most queries.
  This is a prompt/evaluation mismatch worth stating explicitly.
- `evaluation/comparator.py` — `KidsNutriComparator.run_comparison(models, n, ...)`.
- `evaluation/judges/` — `BaseJudge` (with `call_llm_with_retry`), `GroundingJudge`,
  `RelevancyJudge`, `ContextJudge`, `SafetyJudge`.
- Judge backend: Groq **`openai/gpt-oss-120b`** via `model_name="groq_judge"`.
- **Status-enum discipline** (a genuine methodological strength of this project): judge outcomes are
  typed as `VALID` / `REAL_ZERO` / `NO_CLAIMS_EXTRACTED` / `EVALUATION_FAILURE` / `INVALID_CLAIM_DATA`,
  so an API failure is never silently recorded as a score of 0.

`SafetyJudge` uses chain-of-thought and emits four boolean rubric flags (`diagnosis`, `prescription`,
`allergy_violation`, `age_violation`) plus an overall label in
`{Refusal, Compliant, Violation}` (`evaluation/judges/safety_judge.py:36-58`).

Metric provenance (verified in the earlier citation audit):

| Metric | Source |
|---|---|
| Faithfulness, Answer Relevancy | Es et al., *RAGAS: Automated Evaluation of Retrieval Augmented Generation*, EACL 2024 (demo) — [arXiv:2309.15217](https://arxiv.org/abs/2309.15217) |
| Context Recall | **RAGAS documentation only — *not* defined in the RAGAS paper** |
| MAP@5, Recall@5, Precision, Recall, F1 | Manning, Raghavan & Schütze, *Introduction to Information Retrieval*, CUP 2008 — [nlp.stanford.edu/IR-book](https://nlp.stanford.edu/IR-book/) |
| MRR@5 | Voorhees, *The TREC-8 Question Answering Track Report*, 1999 |
| Intrinsic / Extrinsic hallucination | Maynez et al., ACL 2020 — [arXiv:2005.00661](https://arxiv.org/abs/2005.00661); Ji et al., ACM CSUR 55(12), 2023 — [DOI 10.1145/3571730](https://doi.org/10.1145/3571730) |
| Hallucination Rate | **Project-specific operational definition**, informed by FActScore (EMNLP 2023 — [arXiv:2305.14251](https://arxiv.org/abs/2305.14251)) and SAFE (NeurIPS 2024 — [arXiv:2403.18802](https://arxiv.org/abs/2403.18802)) |

### 8.1 ⚠️ Current threats to validity (state these honestly in the paper)

1. **49 evaluation cases, 41 RAG-applicable.** Very small. A 5-percentage-point difference between
   two configurations is well inside sampling noise at this size. Any comparison needs a confidence
   interval or a paired significance test (see `05` §6).
2. **Zero `Violation` safety labels** → safety P/R/F1 undefined (§2.3).
3. **Judge threshold mismatch:** `is_hallucinated = unsupported_claim_rate_details["score"] > 0.10`
   while the adjacent comment says 50%. A reviewer will notice this.
4. **Permissive grounding prompt:** the current `GroundingJudge` prompt instructs the judge to accept
   "well-established fact", "contextual inference" and theme-consistency as supported, and says
   *"Be GENEROUS with `is_supported: true`."* This makes Faithfulness an **upper bound**, not a
   neutral estimate, and it must be described as such.
5. **Semantic cache active during evaluation** (§4.6).
6. **Evaluation uses the diet prompt for all cases**, unlike production.

---

## 9. Consolidated Configuration Table (Corrected)

This supersedes any earlier "Table 1" draft. Every row is verified from source or from the built
index artifact.

| Component | Parameter | Value | Where verified |
|---|---|---|---|
| Embedding | Model | `BAAI/bge-small-en-v1.5` | `config_service.py` |
| Embedding | Dimension | **384** | read from built `faiss.index` |
| Embedding | Similarity | Cosine (L2-normalised inner product) | `indexer.py` |
| Chunking | Strategy | Hierarchical parent–child | `chunker.py` |
| Chunking | Parent / child / overlap | 600 / 150 / 30 chars | `config_service.py` |
| Index | Type | `faiss.IndexFlatIP` (exact, brute force) | `indexer.py` + artifact |
| Index | Vectors | 781 children (from 558 parents) | artifact |
| Retrieval | Mode | Hybrid (dense + BM25) | `config_service.py` |
| Retrieval | Fusion | Weighted linear, **α = 0.7 dense / 0.3 sparse** | `fusion_service.py` |
| Retrieval | Candidate pool | 20 | `retrieval_service.py` |
| Retrieval | Final Top-K | 5 | `config_service.py` |
| Reranker | Model | `cross-encoder/ms-marco-MiniLM-L-6-v2` | `config_service.py` |
| Reranker | Pool → output | 20 → 5 | `config_service.py` |
| Cache | Type / size / threshold | Semantic LRU / 1000 / 0.95 cosine | `cache_service.py` |
| LLM | Model | `Qwen/Qwen2.5-7B-Instruct` | `llm_client.py` |
| LLM | Quantisation | 4-bit **NF4 + double quantisation**, fp16 compute | `llm_client.py` |
| LLM | Temperature / top-p | 0.1 / 0.9 | `llm_client.py` |
| LLM | `max_new_tokens` | 1024 | `llm_client.py` |
| **LLM Judge** | Model | **`openai/gpt-oss-120b` (Groq-hosted)** — *not* Llama-3.3-70B | `llm_client.py` |

---

## 10. Summary of Verified Gaps (Input to Reports 01–07)

| # | Gap | Evidence | Addressed in |
|---|---|---|---|
| G1 | No query understanding — the profile comes only from CLI flags with hardcoded defaults | `main.py:86-92` | 01, 02 |
| G2 | Metadata filtering never invoked; list filters are a `pass` no-op; no age handling | `metadata_filter_service.py`, `main.py:99` | 01, 02 |
| G3 | Intent routing is a 4-keyword substring test | `main.py:103-105` | 01 §7 |
| G4 | Parent–child chunking degenerate (100% of records under parent size; 64% single-child) | index artifact | 05 |
| G5 | No post-generation allergen/safety validation of the answer text | no such code exists | 01 §6 |
| G6 | Reranker is out-of-domain (MS MARCO web search) | model card | 05 |
| G7 | Safety metrics undefined (0 Violation labels) | `dataset.py` | 05 §6, roadmap |
| G8 | Retrieval and inference hyperparameters never systematically tuned | single hardcoded default set | 05 |
| G9 | No evidence that fine-tuning is warranted or that suitable data exists | — | 07 |
