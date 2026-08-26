# KidsNutriBite — Project Understanding & Architecture Audit (Phase 0, Read-Only)

**Scope of this document:** A complete, code-verified map of the KidsNutriBite V2 repository as it exists on branch `feature/weekly-meal-planner` on 2026-08-24. No files were modified to produce this document except the creation of this file itself. Every claim below was verified against the actual source in this repository; where a claim comes from an existing project document instead of direct code inspection, it is explicitly attributed and, where possible, cross-checked.

---

## 1. Executive Project Summary

KidsNutriBite is a pediatric nutrition assistant that answers parents' questions about a child's diet and, when asked, produces a structured meal plan. It combines three separate subsystems and hands the results to an LLM only for the last step — turning verified facts into a friendly explanation:

1. **A deterministic Diet Planner** (`planner/diet_planner.py`) — plain Python, no LLM — computes calorie targets from age/weight, filters a food database by allergy and condition/goal rules, and assembles a meal plan with exact macro totals.
2. **A Hybrid RAG retriever** (`rag/`) — combines dense vector search (FAISS + `BAAI/bge-small-en-v1.5`), sparse keyword search (BM25), a semantic LRU cache, weighted score fusion, and cross-encoder reranking to pull the most relevant pediatric-nutrition guideline chunks for a query.
3. **An LLM generation layer** (`llm/`) — takes the planner's numbers and the RAG's retrieved chunks and writes the parent-facing answer, under a system prompt that forbids it from doing its own arithmetic or diagnosing/prescribing.

A fourth subsystem, **the evaluation framework** (`evaluation/`), benchmarks this pipeline: LLM "judges" extract structured facts/claims/labels from the pipeline's outputs (semantic classification only), and separate pure-Python modules turn those structured outputs into the actual metric numbers (precision, recall, F1, hallucination rates, etc.), so no floating-point score is ever decided by an LLM directly.

The project is presently mid-feature: a 7-day weekly meal planner was just added (most recent commit) but is not yet wired into the request pipeline, and a move toward manually-annotated retrieval ground truth (`relevant_chunk_ids`) is planned but not yet started (0 of 100 cases annotated).

---

## 2. Complete Architecture (as implemented)

```
User query + child profile (age, weight, condition, goal, allergies)
                    │
                    ▼
        ┌────────────────────────┐
        │   main.py (CLI only)   │   <- routes to --index / --query / --plan / --ask / --evaluate
        └───────────┬────────────┘
                     │ (--ask path, the only "full pipeline" entry point)
      ┌──────────────┴───────────────┐
      ▼                               ▼
┌─────────────────────┐     ┌──────────────────────────┐
│  DietPlanner          │     │  KidsNutriRetriever        │
│  (planner/diet_planner)│     │  (rag/retriever.py facade) │
│  - calorie calc        │     │  → RetrievalService:        │
│  - allergy/condition    │     │   1. Embed query (bge-small)│
│    filtering            │     │   2. Semantic cache lookup  │
│  - meal assembly        │     │   3. FAISS dense search      │
│  (daily plan only —     │     │   4. BM25 sparse search      │
│   weekly plan exists but│     │   5. Weighted fusion (α=0.7) │
│   is NOT called here)   │     │   6. Metadata filter (dormant│
└───────────┬─────────────┘     │      — never given filters)  │
            │                   │   7. Cross-encoder rerank    │
            │                   │   8. Parent-chunk expansion  │
            │                   │   9. Cache store + logging   │
            │                   └───────────────┬──────────────┘
            └───────────────┬───────────────────┘
                             ▼
                 llm/prompt_templates.py
                 (generate_llm_prompt / generate_qa_prompt
                  — chosen by a keyword-based intent router
                  in main.py, e.g. "plan"/"diet"/"meal"/"menu")
                             │
                             ▼
                 llm/llm_client.py (KidsNutriLLMClient)
                 → Gemini / Groq (3 models) / OpenRouter
                   (Qwen, Llama) / local Transformers
                   (Qwen, Llama, 4-bit)
                             │
                             ▼
                  Personalized natural-language answer
```

Everything left of the LLM box is deterministic Python; only the final synthesis step is generative. This is intentional and stated explicitly in the system prompts (`llm/prompt_templates.py`): the LLM is told not to recompute or alter any planner numbers.

---

## 3. Directory / Module Map

```
nutrikid_Agentic-main/
├── main.py                     CLI entry point (--index/--query/--plan/--ask/--evaluate)
├── planner/
│   ├── diet_planner.py         KidsNutriDatabase (data loader) + DietPlanner (rules engine)
│   └── test_weekly_planner.py  unittest suite for the new weekly planner
├── rag/
│   ├── retriever.py            KidsNutriRetriever — thin backward-compat facade
│   ├── indexer.py              builds FAISS index + metadata.pkl from rag_data.json
│   ├── chunker.py              ParentChildChunker (parent 600/ child 150 chars, 30 overlap)
│   ├── config.py                re-exports RAGConfig/ConfigurationService
│   ├── services/                the real, current implementation (12 single-purpose services)
│   │   ├── base.py                    ABCs for every service (dependency-injection contracts)
│   │   ├── config_service.py          RAGConfig dataclass + load/save
│   │   ├── retrieval_service.py       orchestrator — the actual 9-step pipeline (see §5)
│   │   ├── embedding_service.py       SentenceTransformer wrapper, lazy-loaded
│   │   ├── cache_service.py           LRU + cosine-similarity semantic cache
│   │   ├── bm25_service.py            rank_bm25 BM25Okapi wrapper
│   │   ├── metadata_filter_service.py tag/type/text substring filter (see gap in §5)
│   │   ├── fusion_service.py          alpha-weighted dense+sparse score fusion
│   │   ├── reranker_service.py        cross-encoder/ms-marco-MiniLM-L-6-v2
│   │   ├── prompt_context_service.py  expands child chunk → parent chunk text
│   │   ├── dataset_version_service.py SHA-256 hash over the 5 source data files
│   │   ├── metrics_service.py         per-stage latency timers (embedding/cache/faiss/bm25/fusion/rerank)
│   │   └── logger_service.py          structured JSON retrieval-event logging
│   ├── bm25_retriever.py       ⚠ DEAD — legacy, imported nowhere (superseded by services/bm25_service.py)
│   ├── reranker.py             ⚠ DEAD — legacy, imported nowhere
│   ├── semantic_cache.py       ⚠ DEAD — legacy, imported nowhere
│   ├── dataset_hasher.py       ⚠ DEAD — legacy, imported nowhere
│   ├── logger.py               ⚠ DEAD — legacy, imported nowhere
│   └── performance_monitor.py  ⚠ DEAD — legacy, imported nowhere
├── llm/
│   ├── llm_client.py            KidsNutriLLMClient — provider router (Gemini/Groq/OpenRouter/local)
│   ├── groq_client.py           thin Groq SDK wrapper
│   └── prompt_templates.py      SYSTEM_PROMPT / QA_SYSTEM_PROMPT + prompt builders
├── evaluation/
│   ├── dataset.py               EVALUATION_DATA — 100 hardcoded test cases (5 categories)
│   ├── evaluator.py             KidsNutriEvaluator — per-case orchestration (Layer 3)
│   ├── comparator.py            KidsNutriComparator — batch runs + CSV/MD report generation
│   ├── judges/                  Layer 1 — LLM semantic extraction only, no math
│   │   ├── base_judge.py            shared retry/backoff + robust JSON parsing/repair
│   │   ├── context_judge.py         precision relevance labels + recall fact-checking
│   │   ├── grounding_judge.py       claim extraction + support/hallucination-type labeling
│   │   ├── relevancy_judge.py       reverse-engineers hypothetical questions from the answer
│   │   └── safety_judge.py          CoT safety rubric (diagnosis/prescription/allergy/age)
│   └── metrics/                 Layer 2 — pure Python math, no LLM calls
│       ├── retrieval_metrics.py     Precision/Recall/MRR/AP/MAP @K, with explicit status enums
│       ├── grounding_metrics.py     Faithfulness, Overall/Intrinsic/Extrinsic Hallucination, Context Recall
│       ├── relevancy_metrics.py     cosine similarity → Answer Relevancy
│       └── safety_metrics.py        confusion matrix → Accuracy/Precision/Recall/F1/F2
├── data/
│   ├── structured_db/           foods.json (99), conditions.json (172/160 unique), goals.json (148/144 unique), allergies.json (17/9 unique)
│   ├── rag/                     rag_data.json (551 chunks), faiss.index, metadata.pkl, dataset_hash.txt
│   ├── recall5_annotation_template.json   scaffold for the planned relevant_chunk_ids annotation (currently all empty)
│   └── validate_db.py           frozen-schema key-presence validator (not a data-quality validator)
├── reports/                     pre-existing audit/research documents and generated CSV/MD reports (see §12/§13 discussion)
├── KidsNutriBite_Evaluation.ipynb   Kaggle/Colab wrapper around the same CLI (see §7 and known problems)
├── test_map_at_k.py / test_mrr_at_k.py / test_precision_at_k.py / test_recall_at_k.py   unit tests for evaluation/metrics/retrieval_metrics.py
├── test_runner.py               manual smoke-test script for the weekly planner
├── verify_gemini.py / verify_groq.py / verify_qwen.py   standalone connectivity diagnostics
├── KidsNutriBite_Final.zip      ⚠ tracked in git, contains a `.env` with what appear to be live API keys — see §10, §12 (URGENT)
└── _paper_check/                6 arXiv PDFs backing project_formulas_and_papers.md's citations
```

---

## 4. End-to-End Request Flow (traced from actual code)

Only `main.py --ask` exercises the full pipeline; `--plan` skips RAG entirely, `--query` skips the planner and LLM entirely.

1. **CLI parses args** (`main.py`) into a profile dict: `{age, weight, condition, goal, allergies}`. Defaults are applied if age/weight/etc. are omitted (age=7.0, weight=20.0, condition="healthy_growth", goal="balanced_nutrition").
2. **Retrieval runs first, unconditionally**: `retriever.retrieve(args.ask, top_k=5)` — happens before intent routing and before the planner, regardless of whether the query is diet-plan-related.
3. **Intent routing** is a plain keyword check: `any(kw in query_lower for kw in ["plan","diet","meal","menu"])`.
   - If matched → `planner.generate_meal_plan(profile)` runs (the **daily**, 4-slot planner — `generate_meal_plan`, not the new `generate_weekly_meal_plan`), then `generate_llm_prompt(plan, contexts, query)` builds the prompt.
   - If not matched → `generate_qa_prompt(profile, contexts, query)` builds the prompt directly from the raw profile dict (planner is not invoked at all).
4. **LLM call**: `client.generate_response(system_prompt, user_prompt, args.model)` dispatches to Gemini/Groq/OpenRouter/local based on `args.model`.
5. **Output**: raw text + latency printed to stdout. There is no API/service layer, no session/conversation state, and no streaming — `main.py` is a one-shot CLI script.

The evaluation pipeline (`evaluator.run_single_evaluation`) follows the same shape but always takes the diet-plan branch (`generate_llm_prompt`, never `generate_qa_prompt`) and always calls `planner.generate_meal_plan` (never the weekly planner), regardless of the test question's category.

---

## 5. RAG Deep-Dive

**Orchestrator:** `rag/services/retrieval_service.py::RetrievalService.retrieve()`. Exact 8-step sequence per call (verified line-by-line):

1. **Embedding** — `EmbeddingService.encode_query` (`BAAI/bge-small-en-v1.5` via SentenceTransformers, L2-normalized).
2. **Semantic cache lookup** — `CacheService.get()`: normalizes the query string, then either does an exact normalized-string match or falls back to cosine similarity against every cached entry (linear scan), returning a hit only if similarity ≥ `cache_similarity_threshold` (default 0.95). Cache entries are invalidated per-entry if their stored `dataset_hash` differs from the current one (computed by `DatasetVersionService` over `foods.json`, `conditions.json`, `goals.json`, `allergies.json`, `rag_data.json`).
3. **Dense search** — FAISS `IndexFlatIP` search for `max(rerank_top_n=20, top_k*3)` candidates.
4. **Sparse search** — `BM25Service` (rank_bm25 `BM25Okapi`), min-max normalized to [0,1] per-query.
5. **Fusion** — `FusionService.fuse_results`: `score = alpha * dense_score + (1-alpha) * bm25_score`, alpha=0.7 by default. (`mode="semantic"` or `"keyword"` skip fusion entirely and use one signal only.)
6. **Metadata filtering** — `MetadataFilterService.filter_chunks`, only runs if `metadata_filters` is truthy. **In the current codebase, no caller ever passes `metadata_filters`** — not `main.py`, not `evaluator.py`. This pipeline stage exists, is implemented, and is unit-testable, but is dormant in every live code path checked.
7. **Cross-encoder reranking** — `cross-encoder/ms-marco-MiniLM-L-6-v2` re-scores the fused candidates and truncates to `top_k`.
8. **Parent-chunk expansion** — `PromptContextService` swaps the short "child" chunk text for its longer parent-chunk text (parent/child chunking done at index time by `rag/chunker.py::ParentChildChunker`, 600/150/30-char parent/child/overlap).
9. **Cache write + structured logging** of the final result, plus per-stage latency (embedding/cache/faiss/bm25/fusion/rerank) recorded by `MetricsService`.

**Indexing** (`rag/indexer.py`, run via `main.py --index`): loads `data/rag/rag_data.json` (551 raw entries), chunks it, embeds child chunks, builds `IndexFlatIP`, and writes `faiss.index` + `metadata.pkl` (containing child_chunks, parent_chunks, parent_map, raw_documents, dataset_hash, and the embedding config used) + `dataset_hash.txt`.

**Legacy/dead code:** `rag/bm25_retriever.py`, `reranker.py`, `semantic_cache.py`, `dataset_hasher.py`, `logger.py`, `performance_monitor.py` are top-level files that duplicate functionality now owned by `rag/services/*`. Confirmed via repo-wide grep: none of them are imported anywhere, including the notebook.

---

## 6. Diet Planner Deep-Dive

`planner/diet_planner.py` has two independent, non-interoperating public methods: `generate_meal_plan` (daily, 4 slots) and `generate_weekly_meal_plan` (7-day, 6 slots/day, with rotation). **Only `generate_meal_plan` is reachable from `main.py` or the evaluator** — `generate_weekly_meal_plan` is fully implemented and has its own test suite (`planner/test_weekly_planner.py`, `test_runner.py`) but is not called from anywhere in the request pipeline.

| Capability | Status | Notes |
|---|---|---|
| Calorie target calculation | **IMPLEMENTED** | Weight is either taken from the profile or estimated via age-banded anthropometric formulas; base calories via the **Holliday-Segar formula** (a formula from pediatric fluid-maintenance literature, being reused here for energy estimation — worth independent literature verification, see §9/§15); +12% multiplier for fever/infection/diarrhea; ±300/-200 kcal surplus/deficit for gain/loss-type goals. |
| Macro targets (weekly planner only) | **IMPLEMENTED** | Fixed AMDR-style split: 15% protein / 55% carbs / 30% fat, 14g fiber per 1000 kcal. |
| Allergy filtering | **IMPLEMENTED** | Matches by exact food/category name, `allergy_tags` list, and two hardcoded partial-string rules (`"nut" in allergy and "nut" in food_name`; `"milk" in allergy and ("milk" in food_name or "dairy" in category)`). |
| Condition/goal tag filtering | **IMPLEMENTED** | `required_tags`/`avoid_tags` pulled from `conditions.json`/`goals.json`, scored (+5 per matched required tag) rather than hard-required. |
| Meal-slot assignment | **IMPLEMENTED** | Primary match on `meal_types`; falls back to hardcoded category lists (e.g., breakfast → cereal/dairy/fruit) if no direct match; falls back again to "any candidate food" as a last resort. |
| Weekly rotation (penalize yesterday's food in the same slot) | **IMPLEMENTED** (weekly planner only) | `rotation_score` subtracts 100 if a food was used in the same slot the previous day, plus a macro-gap-driven +10 boost. |
| "is_safe" plan validation | **PARTIAL** | Only checks `len(candidate_foods) > 0` — this is not a real nutritional safety check, just "did filtering leave any candidates." |
| Portion-size math | **IMPLEMENTED**, **DATASET LIMITED** | Falls back to `energy_per_100 = 100.0 kcal` whenever a food's real energy value is missing/zero — this silently fabricates a plausible-looking number rather than surfacing the gap. |
| Fiber tracking | **DATASET LIMITED** | `fiber_g` is **absent from every single record** in `foods.json` (0/99 populated) — the weekly planner's fiber target and fiber totals are computed and reported, but the "actual" side is always 0.0 g, since `food.get("fiber_g", 0.0)` never finds the key. |
| Nutrition data completeness overall | **DATASET LIMITED** | Of 99 foods: 38 have empty `energy_kcal_per_100g`, 44 have empty `protein_g`, 44 have no `meal_types` at all (triggering the category-fallback path routinely, not as an edge case). |

**Verdict:** the rules engine itself is a complete, deterministic, well-tested implementation of what it claims to do. The output's real-world nutritional accuracy is bounded by data sparsity in `foods.json`, which the planner papers over with fallback constants (100 kcal/100g) rather than flagging. This matches the task brief's caution not to assume the planner is nutritionally perfect.

---

## 7. LLM Pipeline

`llm/llm_client.py::KidsNutriLLMClient.generate_response(system_prompt, user_prompt, model_name)` is the single entry point, dispatching on a string switch:

| `model_name` | Provider | Notes |
|---|---|---|
| `gemini` | Google `google.generativeai`, model `gemini-2.5-flash` | Safety settings forced to `BLOCK_NONE` on all 4 categories (to avoid over-refusal on medical/allergen topics); system+user prompt manually concatenated ("to bypass SDK system_instruction truncation bugs" — per code comment); 5-attempt exponential backoff (12s base) specifically on 429/quota errors. |
| `qwen`, `llama` | OpenRouter REST API | `qwen/qwen-2.5-7b-instruct`, `meta-llama/llama-3.1-8b-instruct`; requires `OPENROUTER_API_KEY`. |
| `qwen_local`, `llama_local` | Local HuggingFace `transformers`, 4-bit (bitsandbytes) | Hard-requires a CUDA GPU — raises `RuntimeError` immediately if `torch.cuda.is_available()` is False; models are cached per-process after first load. |
| `groq_llama70b`, `groq_llama8b`, `groq_qwen` | Groq API via `llm/groq_client.py` | `llama-3.3-70b-versatile`, `llama-3.1-8b-instant`, `qwen/qwen3.6-27b`. |

Generation is deterministic-leaning by default (`temperature=0.1`, `top_p=0.9`), except `RelevancyJudge` which forces `temperature=0.0, top_p=1.0` for its hypothetical-question generation and restores the prior config afterward.

**Prompting** (`llm/prompt_templates.py`): two system prompts (diet-plan mode vs. general-QA mode), both with hard safety guardrails (no diagnosis, no prescription, must respect allergies, must not recalculate planner numbers). **Confirmed bug**: `generate_qa_prompt` reads `profile.get('weight_kg')`, but the QA-mode profile dict built in `main.py` (`args.ask` branch, non-diet-plan queries) only has a `weight` key — so every general-QA prompt renders the child's weight as `"N/A"` even when a real weight was supplied on the CLI. This does not affect diet-plan-mode prompts, since those build the profile from the planner's own output (which does use `weight_kg`).

**JSON/retry handling** lives in the evaluation judges, not the generation client: `evaluation/judges/base_judge.py::safe_parse_json` strips markdown code fences, attempts a quote-repair pass on common keys, and falls back to `{"parse_failed": True}` after logging the raw failure to `reports/judge_parse_failures.csv`.

---

## 8. Evaluation Architecture

```
Layer 1 — LLM Judges (semantic extraction only, JSON out)
  ContextJudge    → evaluate_precision(): binary relevance_map per retrieved chunk
                  → evaluate_recall(): RAGAS-style atomic fact extraction + presence check
  GroundingJudge  → evaluate_grounding(): claim extraction + is_supported + hallucination_type
  RelevancyJudge  → generate_hypothetical_questions(): reverse-engineers 3 questions from the answer
  SafetyJudge     → evaluate_safety(): CoT reasoning + 4 boolean rubric flags + overall category
        │
        ▼
Layer 2 — Deterministic Metrics (evaluation/metrics/*, no LLM calls)
  retrieval_metrics.py  → Precision/Recall/MRR/AP/MAP @K, each with an explicit status enum
                           (VALID / REAL_ZERO / MISSING_GROUND_TRUTH / INVALID_GROUND_TRUTH /
                            EMPTY_RETRIEVAL / INCOMPLETE_RETRIEVAL / EVALUATION_FAILURE) so that
                           "no ground truth" is never silently averaged in as a 0.
  grounding_metrics.py  → Faithfulness, Overall/Intrinsic/Extrinsic Hallucination Rate, Context Recall
  relevancy_metrics.py  → cosine similarity of (original query, hypothetical questions) → Answer Relevancy
  safety_metrics.py     → confusion matrix → Accuracy/Precision/Recall/F1/F2
        │
        ▼
Layer 3 — Orchestration: evaluation/evaluator.py::KidsNutriEvaluator.run_single_evaluation()
  1 planner call + 1 retrieval call + 1 generation call + 4 judge calls per test case (5 LLM calls total)
        │
        ▼
Layer 4 — Aggregation: evaluation/comparator.py::KidsNutriComparator.run_comparison()
  Batches all 100 (or --num-samples) cases per model, writes:
    reports/retrieval_trace.csv, detailed_evaluation_records.csv, ragas_report.csv,
    hallucination_analysis.md, safety_analysis.md, retrieval_experiment.csv,
    final_model_comparison.csv
```

This is a genuinely well-separated architecture — the "LLM does semantic classification, Python does arithmetic" principle from the task brief is followed consistently in the retrieval/grounding/relevancy metrics. **The one place it breaks down is safety ground truth** (see §10, #4): the *math* in `safety_metrics.py` is standard and correct, but `comparator.py::compute_safety_metrics` builds its "ground truth" labels from the dataset's `is_safety` flag (which means "this question touches a safety-sensitive topic," not "a violation should have occurred here"), and hardcodes all 4 rubric-level ground truths to `False` because no per-case annotated violation labels exist. The resulting Accuracy/Precision/Recall/F1/F2 numbers are real computations over a proxy ground truth, not over true clinical-safety labels.

---

## 9. Metric Implementation Matrix

Status legend: **WORKING** (implemented correctly and receives real inputs) · **NEEDS AUDIT** (implemented, but a specific concern is documented below) · **IMPLEMENTATION GAP** (implemented but deviates from the standard/cited formula, or a dependency is dormant) · **GROUND TRUTH MISSING** (code is correct but has no real annotated ground truth to run on) · **NOT IMPLEMENTED**.

| Metric | File | Function | LLM role | Python role | Input | Output | Current status |
|---|---|---|---|---|---|---|---|
| Precision@5 | `evaluation/metrics/retrieval_metrics.py` | `calculate_precision_at_k_details` | `ContextJudge.evaluate_precision` labels each retrieved chunk relevant/not | `relevant_count / k`, with explicit status (per task note, already received an error-handling fix) | LLM relevance_map (booleans) | score ∈[0,1] or `None` | **WORKING** |
| Recall@5 | `evaluation/metrics/retrieval_metrics.py` | `calculate_recall_at_k_details` | none (pure ID-set math) | `\|retrieved_ids ∩ gold_ids\| / \|gold_ids\|` | `retrieved_chunk_ids`, `test_case["relevant_chunk_ids"]` | score or `None` | **GROUND TRUTH MISSING** — 0/100 cases have `relevant_chunk_ids` populated; every case returns status `MISSING_GROUND_TRUTH`, `score=None` (verified: this behavior is explicitly unit-tested in `test_recall_at_k.py`, and its non-silent-zero design is exactly what `data/recall5_annotation_template.json` is staged to fix) |
| MRR@5 | `evaluation/metrics/retrieval_metrics.py` | `calculate_mrr_at_k_details` | none | `1 / rank_of_first_gold_hit` | same as Recall@5 | score or `None` | **GROUND TRUTH MISSING** (same root cause) |
| AP@5 / MAP@5 | `evaluation/metrics/retrieval_metrics.py` | `calculate_ap_at_k_details` / `calculate_map_at_k_details` | none | Average Precision, then mean across cases | same as Recall@5 | score or `None` | **GROUND TRUTH MISSING**, plus a separate **IMPLEMENTATION GAP**: `calculate_ap_at_k` (the underlying scorer) normalizes by `num_hits` (relevant items actually found within top-K) rather than by `total_relevant` — confirmed directly from the code and its own passing unit test (`test_map_at_k.py::test_valid_gold_id_ap_at_5`, which asserts `2.2667/3=0.7556`, not `2.2667/4=0.5667`). This is a deviation from the standard Average Precision definition (which normalizes by total relevant documents, not by hits found) and will inflate MAP@5 once ground truth is annotated. Independently confirms a finding already raised in `research_notes.md`. |
| Context Recall | `evaluation/metrics/grounding_metrics.py` | `calculate_context_recall` | `ContextJudge.evaluate_recall` extracts atomic facts from `expected_context` and checks presence in retrieved chunks | `supported_facts / total_facts` | LLM `facts` list | score ∈[0,1] | **WORKING** as a metric computation; the *low observed values* (~0.38, per `reports/`) reflect genuine retrieval-quality issues (chunking/embedding), not a bug in this function |
| Faithfulness | `evaluation/metrics/grounding_metrics.py` | `calculate_faithfulness` | `GroundingJudge.evaluate_grounding` extracts claims + support status | `supported_claims / total_claims` | LLM `claims` list | score ∈[0,1] | **WORKING** |
| Answer Relevancy | `evaluation/metrics/relevancy_metrics.py` | `calculate_answer_relevancy` | `RelevancyJudge.generate_hypothetical_questions` (temp=0.0) | mean cosine similarity(original query, hypothetical questions), reusing the retriever's embedding model | LLM-generated questions | score ∈[0,1] | **WORKING** |
| Overall Hallucination Rate | `evaluation/metrics/grounding_metrics.py` | `calculate_overall_hallucination_rate` | same `GroundingJudge` claims | `unsupported_claims / total_claims` | LLM `claims` list | rate ∈[0,1] | **WORKING** |
| Intrinsic Hallucination Rate | `evaluation/metrics/grounding_metrics.py` | `calculate_intrinsic_hallucination_rate` | same, filtered on `hallucination_type=="intrinsic"` | ratio | LLM `claims` list | rate ∈[0,1] | **WORKING** |
| Extrinsic Hallucination Rate | `evaluation/metrics/grounding_metrics.py` | `calculate_extrinsic_hallucination_rate` | same, filtered on `hallucination_type=="extrinsic"` | ratio | LLM `claims` list | rate ∈[0,1] | **WORKING** |
| Safety Accuracy/Precision/Recall/F1/F2 | `evaluation/metrics/safety_metrics.py` | `calculate_classification_metrics` (via `evaluate_safety_batch`) | `SafetyJudge.evaluate_safety` produces predicted `overall` + 4 rubric booleans | Standard confusion-matrix math (F-beta formula is textbook-correct) | predictions from the judge; **"ground truth" reconstructed in `comparator.py::compute_safety_metrics`** as `overall = "Violation" if is_safety else "Compliant"` and **all 4 rubric ground truths hardcoded to `False`** | numbers | **IMPLEMENTATION GAP** (overall-level: proxy ground truth, not true violation labels) / **GROUND TRUTH MISSING** entirely at rubric level (diagnosis/prescription/allergy_violation/age_violation recall is structurally always 0/0 since no case can ever have a true-positive rubric ground truth) |
| End-to-End Latency | `llm/llm_client.py::generate_response` | wraps `time.time()` around the whole call | n/a | wall-clock delta | — | seconds | **RESOLVED (2026-08-25)** — this row is a Phase A snapshot, since superseded. Full re-audit: `docs/latency_final_audit.md` (confirmed the retry-inflation and judge-exclusion findings noted here, recommended KEEP WITH RENAMING). Final product decision: latency removed entirely from the official evaluation metric set (`evaluation/comparator.py`'s `"Average Latency"` column deleted); raw per-case timing still exists for engineering use only. See `project_formulas_and_papers.md`'s "Production Architecture and Latency Decision" section. Also note: the production default answer-generation model changed from Gemini to a local Qwen (`Qwen/Qwen2.5-7B-Instruct`) Transformers backend in the same decision — see that same section. |
| TTFT | — | — | — | — | — | — | **NOT IMPLEMENTED** (confirmed: no reference anywhere in the codebase; all providers are called in non-streaming mode) |
| RAG per-stage latency (embedding/cache/faiss/bm25/fusion/rerank) | `rag/services/metrics_service.py` | `MetricsService` | n/a | per-step `time.perf_counter()` deltas | — | ms per stage | **WORKING** at the retrieval-service level, but **not surfaced** into `evaluator.py`'s per-case result dict or any of the comparator's reports — the instrumentation exists and is queryable via `retriever.service.metrics.get_summary()`, but nothing in the evaluation pipeline currently calls it |

---

## 10. Current Known Problems

Grouped by how they were found. Nothing in this section has been fixed as part of this audit.

### Directly confirmed by reading the code in this session

1. **Committed API keys.** `KidsNutriBite_Final.zip` is tracked in git (`git ls-files` confirms) and contains a `.env` file with what appear to be **live, non-placeholder credentials**: `GEMINI_API_KEY` (53 chars, format-consistent with a real Google key) and `GROQ_API_KEY` (56 chars, starts `gsk_...`, the real Groq key prefix). `OPENROUTER_API_KEY` inside that same `.env` is empty. This is a credential-exposure issue independent of anything else in this audit — **see the flag at the top of my reply to you; this needs attention regardless of the rest of this phase.**
2. **`generate_qa_prompt` reads a profile key that general-QA callers never set.** `main.py`'s `--ask` non-diet-plan branch builds `profile["weight"]`, but `llm/prompt_templates.py::generate_qa_prompt` reads `profile.get('weight_kg')` — so weight always renders as `"N/A"` in general-QA responses, even when supplied on the CLI. (Diet-plan-mode prompts are unaffected — they source the profile from the planner's own output, which does use `weight_kg`.)
3. **`metadata_filters` is wired through the entire RAG pipeline but never populated by any caller.** `RetrievalService.retrieve`, `MetadataFilterService`, and the `KidsNutriRetriever` facade all accept/pass a `metadata_filters` argument; grep across the repo shows no caller (`main.py`, `evaluator.py`) ever supplies one. The "Metadata Filtering" box in the architecture diagram is implemented but dormant in every live path.
4. **Safety ground truth is a proxy, not real labels** (see §9 above) — `comparator.py` lines ~36-45 hardcode rubric-level ground truth to `False` and derive overall ground truth from the `is_safety` topic-flag rather than an actual annotated violation outcome.
5. **AP@K/MAP@K normalizes by hits-found, not total-relevant** (see §9) — a real deviation from the standard Average Precision formula, confirmed against the function's own passing unit test.
6. **6 dead legacy files in `rag/`** (`bm25_retriever.py`, `reranker.py`, `semantic_cache.py`, `dataset_hasher.py`, `logger.py`, `performance_monitor.py`) — superseded by `rag/services/*`, imported nowhere.
7. **The 7-day weekly planner is not integrated anywhere.** `generate_weekly_meal_plan` is implemented and independently tested but is not called by `main.py`, `evaluator.py`, or the notebook — the only pipeline that has ever run it is its own test suite.
8. **`fiber_g` is 0/99 populated in `foods.json`**, yet the weekly planner computes and reports a fiber target and fiber totals every day — the totals side is silently always 0.0g.
9. **`is_pubmed` field on every `EVALUATION_DATA` case is never read anywhere in `evaluator.py` or `comparator.py`.** (The pre-existing `reports/model_comparison_report.json` shows PubMed-specific breakdowns per the background research pass in this audit — those numbers could not have come from the current `comparator.py`, which has no PubMed-filtering logic at all; they must come from a different/older script not present in this repo state.)
10. **The plain (non-`_details`) wrapper functions in `retrieval_metrics.py`** (`calculate_precision_at_k`, `calculate_recall_at_k`, `calculate_mrr_at_k`, `calculate_map_at_k`) **are called only by the root-level unit tests, never by `evaluator.py`/`comparator.py`**, which exclusively use the `_details` variants. Not a bug, but worth knowing which functions are "live."
11. **`data/validate_db.py` validates key presence, not data quality.** It confirms `energy_kcal_per_100g` etc. exist as keys but explicitly does not flag the widespread empty-string sparsity described in §6 — it only warns (doesn't error) on missing `fiber_g`, and even that warning is a per-field, not per-record, count-based print.
12. **Loose, uncommitted scratch artifacts at repo root** (`git status` shows untracked): `rag_match.txt` and `sample_output.json` are UTF-16-encoded (likely produced by a PowerShell `Out-File` redirect rather than Python's UTF-8 file writes), `sample.json` is a normal UTF-8 weekly-plan dump. None of these appear to be referenced by any code path — they read as manual debugging/inspection output left in the working tree.
13. **Raw `age_min` values in `foods.json` are inconsistently typed** (mix of string and int across records) — handled safely by `KidsNutriDatabase._clean_foods`'s `try/except int()` coercion at load time, so not a runtime bug, but a data-hygiene note for anyone editing the raw file by hand.
14. **`evaluate_precision`/`evaluate_recall` in `ContextJudge`, and every other judge, make one full LLM round trip each** — a single evaluation case costs 5 LLM calls (1 generation + 4 judges), none of which are batched, confirmed directly in `evaluator.run_single_evaluation`.

### From the pre-existing project documents (`reports/*.md`, `research_notes.md`, `project_formulas_and_papers.md`, `llm_judge_analysis.md`) — reported here with attribution; verified against code where noted, otherwise reported as-claimed for the team's awareness

15. Context Recall is empirically low (~0.3849 in past runs) due to sentence/child-chunk-level "semantic vector dilution" in the dense retriever, compounded by no keyword-exact-match fallback at the time those reports were written — *architecture_research_study.md, context_recall_failure_analysis.md, retrieval_diagnostics.md*. **Note:** hybrid BM25+dense fusion and cross-encoder reranking (the fixes these documents recommend) **are now implemented** in `rag/services/*` — whether they resolved the measured Context Recall gap has not been re-verified by an actual rerun in this audit (that is explicitly out of scope for Phase 0).
16. `retrieval_diagnostics.md` documents that at least one evaluation question (`Q_COND_01`) was edited to better match the existing limited RAG corpus rather than the corpus being extended — worth the team's awareness when interpreting historical "before/after" retrieval numbers, since `context_recall_failure_analysis.md` and `manual_verification_report.md` still show the old question text, suggesting the edit wasn't (or wasn't yet, at time of writing) reflected everywhere.
17. `inference_validation.md` and `prototype_audit_report.md` reach opposite conclusions about whether past evaluation runs used real model inference or a "Local Simulation Wrapper" — both cite the same missing-API-key condition. **Not independently resolved in this session** — flagged as a contradiction for the team to reconcile using the current `llm_client.py`, which (as read in this session) has no simulation/mock path at all; it always attempts a real call and raises if credentials are missing. If a "Local Simulation Wrapper" existed, it is not present in the current codebase.
18. Several historical reports (`evaluation_summary.md`, `model_comparison_report.json`) list `Average Latency` as `0.0` for every model — an artifact the source documents themselves note is not real measured latency.
19. `research_notes.md`'s code audit claims `evaluator.py` mislabels AP@5 as "Context Precision." **Checked directly against the current `evaluator.py` in this session — not reproducible**: the current code stores `ap_5`/`ap_5_status` and `context_precision`/`precision_at_5_status` as two distinct fields, sourced from two distinct functions (`calculate_ap_at_k_details` and `calculate_precision_at_k_details`). This matches the task brief's note that Precision@5 already received a fix — this specific historical finding appears to be resolved already, and should not be treated as still-open.
20. `context_recall_failure_analysis.md`/`prototype_audit_report.md` report a Gemini safety confusion matrix with Precision=0 and Recall=0 but F1=1.0 in the same row — mathematically impossible under the harmonic-mean F1 formula. **Checked directly against `safety_metrics.py`'s `calculate_classification_metrics`**: the current code returns `f1=0.0` when `precision+recall==0`, so this specific inconsistency does not reproduce against the current metric code and likely reflects either a manual transcription error in that historical report or a since-changed formula.
21. ROUGE-L, BERTScore, Delta-PPL/perplexity filtering, and the semantic-cache-specific metrics (Volume Score, Next Cover, SphereLFU, DistanceLFU, Linguistic Surprisal) are discussed in the cited papers but are **not implemented anywhere in the codebase** — confirmed by absence (no matches for these terms in any `.py` file).
22. NDCG is discussed in cited papers but not implemented — confirmed by absence.

---

## 11. Full-Stack Integration Readiness

**NO INTEGRATION IMPLEMENTED IN THIS PHASE.** The following is an inventory of what exists today, for planning purposes only.

**Current input/profile schema actually consumed by the AI system:**
```python
{"age": float, "weight": float | None, "condition": str | None, "goal": str | None, "allergies": list[str]}
```
This is the entire profile surface read anywhere in `planner/diet_planner.py`, `llm/prompt_templates.py`, and `evaluation/dataset.py`. There is no `gender`, `height`, `activity_level`, `dietary_preference`, or free-text medical-history field anywhere in the current code (confirmed by repo-wide search).

**Current query interface:** a single free-text string (`question`/`--ask`), no conversation history, no session concept, no user/child identity beyond the profile dict passed in per-call.

**Current response format:** a raw string (LLM's natural-language answer) plus a `latency` float, returned from `KidsNutriLLMClient.generate_response`. No structured JSON response envelope, no citations/source-chunk references returned to the caller (chunk IDs are logged internally but not returned in the CLI/evaluator output contract).

**Current service boundary:** none — everything runs in-process via direct Python imports (`main.py` imports `planner`, `rag`, `llm` directly). There is no HTTP/REST/gRPC layer, no FastAPI/Flask app, in this repository. `technical_documentation.md` describes an *intended* future FastAPI/Flask + React/Flutter deployment, but no such server code exists here.

**What the richer full-stack profile would need to map into this system, when integration begins:**
- `age`, `weight` → used directly today.
- `allergies` → used directly today (list of strings matched against `allergy_tags`/`avoid_foods`/hardcoded partial-string rules).
- `condition`, `goal` → used directly today, but are free-text-matched against `conditions.json`/`goals.json` record names — a full-stack app would need to send values that already match this repo's frozen naming (e.g. `"child_above_1_year"`, `"balanced_nutrition"`), or a normalization/adapter layer would be needed to map the full-stack app's own condition/goal vocabulary onto this repo's ~160/~144 unique names.
- `gender`, `height`, `activity_level`, `dietary_preference` → **currently lost entirely** — nothing in the planner, RAG metadata filter, or prompts reads these, even though `MetadataFilterService` already has a generic `condition`/`goal`/`category` filter mechanism that could plausibly be extended.
- Any conversation/session history the full-stack app maintains → has no analog here; every call to this system is stateless.

This inventory is descriptive only — no adapter, contract, or schema is proposed or implemented here, per the task's explicit instruction not to invent the full-stack API contract.

---

## 12. Reproducibility

- **`requirements.txt`** lists `torch, transformers, sentence-transformers, faiss-cpu, bitsandbytes, accelerate, python-dotenv, groq, google-generativeai, matplotlib, pandas, numpy, scikit-learn, huggingface_hub, tabulate, rank-bm25`. `bitsandbytes` in particular is used only by the local-Transformers 4-bit path and is Linux/CUDA-oriented — a developer on Windows/CPU-only (like the current environment) will hit import friction on that path specifically (`llm_client.py` already guards this with a try/except and a printed warning, falling back to plain float16).
- **No `.env` file is present in the working tree** (correctly gitignored via `.gitignore`: `.env`, `__pycache__/`). However, see §10 #1 — a `.env` **with what appear to be real credentials is embedded inside the tracked `KidsNutriBite_Final.zip`**, which defeats the purpose of gitignoring `.env` at the top level.
- **Model/config names are hardcoded** in multiple places rather than centralized: `gemini-2.5-flash` in `llm_client.py`, `BAAI/bge-small-en-v1.5` in both `rag/config.py`'s default and `rag/retriever.py`'s constructor default, `cross-encoder/ms-marco-MiniLM-L-6-v2` in `RAGConfig`. Changing a model requires touching more than one file.
- **GPU dependency is real, not optional**, for `qwen_local`/`llama_local` — `llm_client.py` raises `RuntimeError` immediately if no CUDA device is found (this is intentional per code comments: "Enforce real model inference and abort if credentials/hardware are missing" — no silent fallback).
- **Notebook path bug**: `KidsNutriBite_Evaluation.ipynb` Section 5 ("Dataset Loading") reads structured DB files from `os.path.join("data", "planner")`, but the actual folder in this repository is `data/structured_db/` (confirmed: `planner/diet_planner.py::KidsNutriDatabase.__init__` defaults to `data/structured_db`, and that is the only structured-DB folder that exists on disk). Running that notebook cell as-is will print "Missing" for all four DB files.
- **First-run cost**: `RetrievalService.__init__` auto-builds the FAISS index if `faiss.index`/`metadata.pkl` are absent (calls `rag.indexer.build_index` internally) — so a fresh clone with only `rag_data.json` present will work without manually running `--index` first, but the first retrieval call will be slow (full corpus embedding).
- **`KidsNutriBite_Final.zip`** (999KB, tracked in git) appears to be a full point-in-time snapshot/backup of an earlier version of this same repository, bundled as a zip — its presence alongside the live repo is itself a reproducibility/hygiene question for the team (which is authoritative?), independent of the embedded-secrets issue.

---

## 13. Testing Status

| Test file | What it actually tests |
|---|---|
| `test_map_at_k.py`, `test_mrr_at_k.py`, `test_recall_at_k.py`, `test_precision_at_k.py` (repo root) | Unit tests for `evaluation/metrics/retrieval_metrics.py` only — pure math, no LLM, no retriever, no dataset I/O beyond importing `EVALUATION_DATA` to confirm the "0/100 annotated → all `MISSING_GROUND_TRUTH`, never a silent 0" behavior. These are thorough and well-designed (explicit edge cases: duplicates, incomplete retrieval, invalid ground truth, empty retrieval, evaluation failure). **This is the most solidly tested part of the repository.** |
| `planner/test_weekly_planner.py` | `generate_weekly_meal_plan` only: 7 days generated, 6 slots/day, every selected food exists in the DB, no allergy leakage (string-match check for `"egg"` substring), totals are non-negative, condition-rule text applied, and a rotation "runs successfully" check (explicitly does *not* assert zero overlap — comment acknowledges the DB may be too small to guarantee it). Also a `test_backward_compatibility` check that the old `generate_meal_plan` (4-slot) still works unchanged. |
| `test_runner.py` (repo root) | Not a `unittest` — a manual smoke-test script (`assert` statements + prints) exercising `data/validate_db.py` as a subprocess, then the weekly planner, printing a human-readable report. |
| `verify_gemini.py`, `verify_groq.py`, `verify_qwen.py` | Standalone connectivity diagnostics (not `unittest`), each hitting one real provider and printing pass/fail — meant to be run manually, not part of any test suite invocation. |

**Untested / no test coverage found for:**
- `rag/services/*` — no unit tests for `RetrievalService`, `CacheService`, `BM25Service`, `FusionService`, `RerankerService`, `MetadataFilterService`, etc. Confirmed by `Glob` across the repo — no `test_*` or `*_test.py` file references any `rag.services` module.
- `evaluation/judges/*` and `evaluation/evaluator.py`/`comparator.py` — no unit tests found; these are only exercised indirectly through `main.py --evaluate` (a real, expensive, multi-API-call run) or the notebook.
- `llm/llm_client.py`, `llm/groq_client.py` — no unit tests; only the manual `verify_*.py` scripts.
- `planner/diet_planner.py::generate_meal_plan` (the daily planner actually used by `main.py`/`evaluator.py`) — has no dedicated unit test; `test_weekly_planner.py::test_backward_compatibility` only smoke-checks that it runs and returns a `meal_plan` key with 4 entries, without checking correctness of calorie/macro math.
- `data/validate_db.py` — has no unit test of its own; it is itself a validation script for the JSON data, invoked manually or via `test_runner.py`'s subprocess call.

---

## 14. V2 Completeness Check

| Architecture box | Status | Basis |
|---|---|---|
| Semantic Cache | ✅ IMPLEMENTED | `CacheService` — LRU + cosine similarity + dataset-hash invalidation, fully wired into `RetrievalService`. |
| Metadata Filtering | ⚠️ PARTIAL | `MetadataFilterService` implemented and correct for the filter types it supports, but never receives real filters from any current caller — dormant. Also, its `list`-type filter branch (e.g., for allergy-exclusion tags) is an explicit no-op (`pass`), so even if wired up, list-valued filters would do nothing. |
| FAISS (dense) | ✅ IMPLEMENTED | `IndexFlatIP`, `EmbeddingService`, fully wired. |
| BM25 (sparse) | ✅ IMPLEMENTED | `BM25Service` via `rank_bm25`, fully wired into fusion. |
| Score Fusion | ✅ IMPLEMENTED | `FusionService`, alpha-weighted linear combination, fully wired. |
| Cross-Encoder Reranking | ✅ IMPLEMENTED | `RerankerService`, `ms-marco-MiniLM-L-6-v2`, fully wired, config-toggleable. |
| Deterministic Diet Planner — daily | ✅ IMPLEMENTED | `generate_meal_plan`, reachable from `main.py --plan`/`--ask` and the evaluator. |
| Deterministic Diet Planner — weekly | ⚠️ PARTIAL | `generate_weekly_meal_plan` fully implemented and independently tested, but **not reachable from any request-flow entry point** (`main.py`, evaluator, notebook). |
| Diet Planner nutritional accuracy | ⚠️ DATASET LIMITED | Rules engine is complete; the food database it draws from has 38-44% sparsity on key numeric fields and 100% sparsity on `fiber_g` (see §6). |
| LLM (multi-provider) | ✅ IMPLEMENTED | Gemini, 3 Groq models, 2 OpenRouter models, 2 local-Transformers models — all reachable via `KidsNutriLLMClient.generate_response`. Real-world availability of the local/OpenRouter paths depends on external GPU/keys not verified in this session. |
| Prompt Construction | ✅ IMPLEMENTED | Both diet-plan and general-QA prompt builders exist and are used; QA-mode has the `weight_kg` bug noted in §10. |
| Evaluation Layer 1 (LLM Judges) | ✅ IMPLEMENTED | All 4 judges present, consistent JSON-out contract, shared retry/parse-repair base class. |
| Evaluation Layer 2 (Deterministic Metrics) | ✅ IMPLEMENTED for retrieval/grounding/relevancy math; ⚠️ PARTIAL for safety (proxy ground truth, see §9/§10) | |
| Evaluation Layer 3 (Orchestrator) | ✅ IMPLEMENTED | `evaluator.py`, clean separation from Layer 1/2 logic. |
| Evaluation Layer 4 (Comparator/Reporting) | ✅ IMPLEMENTED | `comparator.py`, produces all CSV/MD outputs the README describes. |
| Recall@5 / MAP@5 / MRR@5 ground truth | ❌ MISSING | 0/100 cases annotated; code correctly reports this as `MISSING_GROUND_TRUTH` rather than a fake 0, per explicit design and unit tests. |

---

## 15. Recommended Next Order

Per the task brief, this is a report of the already-intended order, not a new plan, and nothing here should be started automatically:

1. Evaluation methodology verification
2. Evaluation implementation corrections
3. Dataset/question audit
4. Notebook audit
5. Experimental rerun
6. Result verification
7. Diet Planner research/verification
8. Full-stack integration
9. Future V3 agentic architecture

Two observations from this audit that may be useful context when the team reaches step 1 and step 3: the AP@K/MAP@K normalization deviation (§9, §10-#5) and the safety ground-truth proxy issue (§9, §10-#4) both sit squarely inside "evaluation methodology verification," and the `relevant_chunk_ids` annotation effort (already staged in `data/recall5_annotation_template.json`) is the prerequisite that unblocks Recall@5/MAP@5/MRR@5 from their current `MISSING_GROUND_TRUTH` state — both are steps 1-2 concerns, not steps 5+ concerns.

---

## What the team should know before making any changes

1. **A `.env` with what appear to be live Gemini and Groq API keys is committed to git inside `KidsNutriBite_Final.zip`.** This should be treated as a potential credential leak regardless of anything else in this document — rotate the keys and consider purging the file from git history. This is outside the scope of "understand the AI project" but was surfaced while tracing reproducibility/config, and is time-sensitive.
2. **Recall@5, MAP@5, and MRR@5 are correctly implemented but structurally cannot produce a score yet** — every one of the 100 evaluation cases has an empty `relevant_chunk_ids`, and the code deliberately returns `None`/`MISSING_GROUND_TRUTH` rather than a fake 0. Any report showing these as 0.0 is either stale or wrong; any report showing them as blank/None/missing is behaving correctly.
3. **The AP@K formula normalizes by hits-found rather than total-relevant** — once ground truth is annotated, MAP@5 numbers from the current formula will read higher than a standard-AP implementation would produce for the same retrieval. Worth deciding intentionally (project-custom metric vs. literature-exact) before the team starts trusting MAP@5 numbers.
4. **Safety Accuracy/Precision/Recall/F1/F2 are computed against a proxy ground truth**, not real annotated violation labels — the overall-level GT is just the dataset's "is this topic safety-sensitive" flag, and all 4 rubric-level GTs are hardcoded `False`. The math is correct; what it's measuring is not what the metric names imply.
5. **The weekly (7-day) meal planner — the most recent feature commit on this branch — is not connected to any request path.** It only runs inside its own test files. If the intent was for `--ask`/`--plan`/the evaluator to start using it, that wiring hasn't happened yet.
6. **The `foods.json` database has real sparsity**: no food has a fiber value, ~40% are missing energy/protein per-100g, and ~44% have no `meal_types` (triggering fallback category logic routinely, not as an edge case). Any nutritional-accuracy claims about the planner's output should be caveated by this.
7. **Several existing `reports/*.md` documents contradict each other** (real-vs-simulated inference conclusions; a mathematically-impossible F1=1.0 with Precision=Recall=0; a fever-question dataset edit that doesn't appear consistently across documents) — treat historical report numbers as provisional until the team's planned "result verification" step (§15, step 6) reconciles them, and note that at least one specific finding from `research_notes.md` (the AP@5/Context-Precision mislabeling) did **not** reproduce against the current code and appears to already be fixed.
8. **This document is a snapshot of the repository as read on 2026-08-24 on branch `feature/weekly-meal-planner`.** No code, data, or notebook was modified to produce it.
