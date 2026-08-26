# Phase 4A — Full Repository Audit (Read-Only)

**Status: AUDIT ONLY. Nothing was deleted, moved, renamed, edited, refactored, reorganized, or committed. `.gitignore` and `requirements.txt` are unmodified. No dataset, RAG index, or notebook file was touched. Every claim below is backed by a direct code read, grep, or `git` command run this session — not inferred from filenames alone.**

---

## 1. Executive summary

KidsNutriBite's core pipeline (Qwen-local → RAG/structured-DB/planner → Groq/Gemini judges → deterministic metrics) is real, coherent, and correctly wired **at the code level** — confirmed by direct tracing, not assumption. However, this audit found **three separate, concrete disconnection/staleness problems** that mean the repository, as it stands, would not currently produce a correct end-to-end evaluation run if executed today:

1. **The entire Phase 2A–2D gold-dataset effort (`docs/evaluation/phase2c_gold_annotations.json`, 49 questions, gold facts, `relevant_chunk_ids`) is never loaded by any Python code.** `evaluation/comparator.py` still imports `EVALUATION_DATA` from the old `evaluation/dataset.py` (100 questions, older schema). Confirmed by grep: zero `.py` files besides my own test file reference the new dataset path at all.
2. **The Kaggle notebook (`KidsNutriBite_Evaluation.ipynb`) is stale and would crash or mislead** at multiple points: it reads a non-existent `data/planner/` directory (real path is `data/structured_db/`), it runs `--model gemini`/`--models gemini` (contradicting the finalized Qwen-local architecture decision), and its final "winners" cell references `df["Safety F2"]` and `df["Average Latency"]` — two columns that were **deliberately removed** from `comparator.py`'s official output during this engagement's earlier metric-audit phases. Running the notebook's later cells today would raise a `KeyError`.
3. **A duplicated, dead first-generation RAG module set exists in `rag/` alongside the real, actively-used `rag/services/` package** (`rag/bm25_retriever.py`, `config.py`, `dataset_hasher.py`, `logger.py`, `performance_monitor.py`, `reranker.py`, `semantic_cache.py`) — confirmed via repo-wide grep: **zero imports of any of these seven files exist anywhere**, including the notebook.

Beyond these three, the audit found a **third stale default** (`comparator.py::run_comparison`'s own `models=["gemini", "qwen_local"]` default, independent of the two stale defaults already found and reported in Phase 3), a large committed-but-never-referenced-by-current-code `reports/` folder mix of historical hand-written research documents and pre-metric-audit generated CSVs, a committed 1.1MB binary FAISS index, and no secrets or committed credentials anywhere in the repository or its git history (confirmed clean).

**Nothing in this report has been fixed.** This is the complete evidence base for a Phase 4B cleanup decision.

---

## 2. Current repository structure (as it actually exists on disk)

```
.
├── .claude/settings.local.json          (untracked — Claude Code session config)
├── .gitignore                            (2 lines: .env, __pycache__/)
├── KidsNutriBite_Evaluation.ipynb        (Kaggle notebook — STALE, see §9)
├── README.md
├── requirements.txt
├── main.py                               (CLI entry point)
├── _paper_check/*.pdf (7 files)          (reference PDFs, doc-support only)
├── data/
│   ├── structured_db/{foods,conditions,goals,allergies}.json
│   ├── rag/{rag_data.json, faiss.index, metadata.pkl, dataset_hash.txt}
│   ├── recall5_annotation_template.json  (untracked, unused scaffold — see §11)
│   └── validate_db.py
├── planner/{diet_planner.py, test_weekly_planner.py}
├── llm/{llm_client.py, groq_client.py, prompt_templates.py}
├── rag/
│   ├── {bm25_retriever,config,dataset_hasher,indexer,logger,performance_monitor,reranker,retriever,semantic_cache}.py
│   └── services/{__init__,base,bm25_service,cache_service,config_service,dataset_version_service,embedding_service,fusion_service,logger_service,metadata_filter_service,metrics_service,prompt_context_service,reranker_service,retrieval_service}.py
├── evaluation/
│   ├── {dataset,evaluator,comparator}.py
│   ├── judges/{__init__,base_judge,context_judge,grounding_judge,relevancy_judge,safety_judge}.py
│   └── metrics/{__init__,grounding_metrics,relevancy_metrics,retrieval_metrics,safety_metrics}.py
├── docs/
│   ├── (16 top-level audit/research markdown files from this engagement)
│   ├── doctor_review/ (7 files, incl. the Phase 2D .docx)
│   └── evaluation/ (8 files: schema, phase2b/2c datasets + reviews, phase3 audit, chunk-ID investigation, iron verification)
├── reports/ (13 files — mixed: pre-engagement generated CSVs, hand-written research .md, and my own session's debug logs)
├── test_*.py (10 files, root level)
├── verify_{gemini,groq,qwen}.py (root level, standalone diagnostics)
├── test_runner.py (root level, planner-only manual verification script)
├── llm_judge_analysis.md, research_notes.md, technical_documentation.md, project_formulas_and_papers.md (root-level docs)
└── __pycache__/ (repo-root and per-package, all untracked, all `.gitignore`d)
```

**File counts** (excluding `.git/`): 180 files on disk; 81 tracked in git (`git ls-files`); 99 untracked. Every `__pycache__/*.pyc` is untracked (correctly `.gitignore`d).

---

## 3. Runtime architecture (traced this session and in the immediately preceding Phase 3 audit, re-confirmed)

```
main.py --ask  →  planner.generate_meal_plan / retriever.retrieve  →  generate_llm_prompt/generate_qa_prompt
               →  llm_client.generate_response(..., model_name=args.model)   [default: qwen_local]
               →  final answer printed to console

main.py --evaluate  →  KidsNutriEvaluator(client, retriever, planner, judge_model=args.judge_model)  [default: groq_llama70b]
                    →  KidsNutriComparator(evaluator).run_comparison(models_list, num_samples)
                    →  dataset = EVALUATION_DATA  (from evaluation/dataset.py — the OLD 100-question set, see §1/§8)
                    →  per-model, per-question: evaluator.run_single_evaluation(test_case, model)
                    →  judges (context/grounding/relevancy/safety) via judge_model backend
                    →  evaluation/metrics/*.py (pure Python)
                    →  reports/*.csv, reports/*.md
```

This matches the intended architecture from §2 of the task instructions, **with one critical exception**: the "EVALUATION DATA" box in the intended architecture (final 49-question dataset, gold annotations, doctor-reviewed safety ground truth) is **not actually in this loop today** — `EVALUATION_DATA` in the diagram above is the old dataset, not the new one. See §8 and §15.

---

## 4. Application connectivity (entry points traced line-by-line)

| Step | File:function | Verified? |
|---|---|---|
| CLI parsing | `main.py::main` (argparse) | Yes — `--index`/`--query`/`--plan`/`--ask`/`--evaluate` are mutually exclusive, all four handlers read directly from the same `args` namespace. |
| Config | No dedicated config file for CLI args — argparse defaults double as config (`--model qwen_local`, `--judge-model groq_llama70b`, `--models qwen_local`) | Confirmed via direct read of `main.py` lines 17–29. |
| Model (production) | `llm.llm_client.KidsNutriLLMClient.generate_response` → `_call_local_transformers("Qwen/Qwen2.5-7B-Instruct", ...)` for `model_name="qwen_local"` | Confirmed — hard-fails with `RuntimeError` if no CUDA GPU (verified in this sandbox: `torch.cuda.is_available()` is `False`, so `--ask`/`--evaluate` with the default model cannot complete an actual generation in this environment; this is expected, per the Kaggle-T4-only architecture). |
| Retriever | `rag.retriever.KidsNutriRetriever` → `RetrievalService` → FAISS + BM25 + fusion + rerank + `PromptContextService` | Confirmed (re-traced in Phase 3 and this session; unchanged). |
| Planner | `planner.diet_planner.KidsNutriDatabase`/`DietPlanner.generate_meal_plan` | Confirmed — reads `data/structured_db/*.json` via a path computed relative to `diet_planner.py`'s own file location (`os.path.dirname(os.path.dirname(os.path.abspath(__file__)))` + `"data/structured_db"`), independent of CLI working directory. |
| Prompt construction | `llm.prompt_templates.generate_llm_prompt` (diet-plan-aware) or `generate_qa_prompt` (general QA) — `main.py --ask` chooses between them via a keyword heuristic (`"plan"`/`"diet"`/`"meal"`/`"menu"` in the query) | Confirmed. `evaluator.py` always uses `generate_llm_prompt` (never `generate_qa_prompt`) — a real, minor asymmetry between the `--ask` and `--evaluate` code paths worth noting (not a bug; `--evaluate`'s test cases were designed around the diet-planner-aware prompt). |
| Answer | Returned to console (`--ask`) or into `run_single_evaluation`'s result dict (`--evaluate`) | Confirmed. |

**Verdict: CONNECTED CORRECTLY** for the answer-generation path, with the caveat that this sandbox cannot execute it end-to-end (no GPU) — this is an environment limitation, not a code defect.

---

## 5. RAG stack connectivity

Traced fully in Phase 3 and re-verified this session:

- **Actually used at runtime**: `rag/chunker.py` (`ParentChildChunker`, used only by `rag/indexer.py` at index-build time, not at query time), `rag/indexer.py` (`build_index`, called by `main.py --index` and auto-invoked by `RetrievalService.__init__` if the index is missing), `rag/retriever.py` (`KidsNutriRetriever`, the sole public-facing class other modules import), and the entire `rag/services/` package (`base.py`, `bm25_service.py`, `cache_service.py`, `config_service.py`, `dataset_version_service.py`, `embedding_service.py`, `fusion_service.py`, `logger_service.py`, `metadata_filter_service.py`, `metrics_service.py`, `prompt_context_service.py`, `reranker_service.py`, `retrieval_service.py`) — every one of these 13 files is imported by `RetrievalService.__init__` or by a class it constructs.
- **Confirmed obsolete (dead)**: `rag/bm25_retriever.py`, `rag/config.py`, `rag/dataset_hasher.py`, `rag/logger.py`, `rag/performance_monitor.py`, `rag/reranker.py`, `rag/semantic_cache.py` — a repo-wide grep for `from rag.bm25_retriever|rag.config|rag.dataset_hasher|rag.logger|rag.performance_monitor|rag.reranker|rag.semantic_cache import` (and the `import rag.X` form) returned **zero matches** anywhere, including the notebook and every test file. These seven files appear to be a first-generation flat implementation that was superseded by the `rag/services/` package (whose files are named almost 1:1 with these — `bm25_retriever.py`→`bm25_service.py`, `config.py`→`config_service.py`, `dataset_hasher.py`→`dataset_version_service.py`, `logger.py`→`logger_service.py`, `performance_monitor.py`→`metrics_service.py`, `reranker.py`→`reranker_service.py`, `semantic_cache.py`→`cache_service.py`) but never deleted.
- **Index-build-only** (not needed at query time once the index exists): `rag/chunker.py`, `rag/indexer.py`'s `build_index` function itself (the module is still imported lazily by `RetrievalService.__init__` as an auto-rebuild fallback, so it's not purely build-time-only in practice).
- **`source_id`/canonical-ID flow** (the fix applied in the immediately preceding phase): traced and confirmed still correctly in place — `rag/chunker.py` computes `source_id` on every child chunk → `rag/services/prompt_context_service.py::expand_and_format_context` passes it through in the final formatted result dict → `evaluation/evaluator.py`'s `retrieved_chunk_ids` construction prefers it over the child-chunk `id`. No regression found.

---

## 6. Structured DB / planner connectivity

- **`planner/diet_planner.py::KidsNutriDatabase`** loads all four `data/structured_db/*.json` files via a hardcoded-but-correctly-relative path; confirmed this matches the real directory (not the notebook's stale `data/planner/` reference — see §9).
- **Fields actually consumed by the planner** (`DietPlanner.generate_meal_plan`/`generate_weekly_meal_plan`): `food_name`, `category`, `energy_kcal_per_100g`, `protein_g`, `fat_g`, `carbs_g`, `iron_mg`, `fiber_g` (weekly planner only), `portion_unit`, `portion_energy_kcal`, `portion_protein_g`, `age_min`, `allergy_tags`, `tags`, `meal_types`, `digestibility_boiled`, `digestibility_fried`. Fields present in `foods.json` but **never read by any planner code**: `digestibility_boiled`'s sibling `digestibility_fried` is read but only for a `-2` score penalty; `glycemic_index`, `benefits`, `preparation`, `composition`, `active_compound`, `clinical_use`, `clinical_note`, `clinical_benefits`, `nutrient_density`, `swelling_ratio`, `usage`, `description`, `ingredients`, `probiotic_strains`, `electrolytes_mEq_L`, `energy_kcal_1000ml`, `nutrients_per_100ml`/`nutrients_per_ml`/`nutrients_per_100g`, `glucose_g_L`, `protein_g_100ml`, `categories` are all present on various `foods.json` records (confirmed via the full field-name set discovered during the Phase 1 KB audit) but **not read anywhere in `diet_planner.py`** — this is old, already-known, already-documented territory (Phase 1 KB audit), re-confirmed here as still true and unchanged.
- **`get_condition`/`get_goal`/`get_allergy`**: confirmed (again) to merge same-named duplicate records via set-union of tags, not "pick first match" — unchanged since the Phase 1 audit.
- **`generate_weekly_meal_plan`**: a substantial, fully-implemented second planning method, **not called by `main.py`, `evaluator.py`, or `comparator.py` anywhere** — its only callers are `planner/test_weekly_planner.py` (a real unittest) and `test_runner.py` (a standalone manual script). This matches the current git branch name (`feature/weekly-meal-planner`) — it is **in-development, not yet integrated into the production `--ask`/`--evaluate` pipeline**. Classification: ACTIVE (has real tests, real code, genuinely runs) but **not yet wired into the application's real entry points** — a distinct category from both "dead" and "fully integrated."
- **Missing integration** (not a planner bug, but a connectivity gap): the 85%-dead-tag-vocabulary finding from the Phase 1 KB audit (`conditions.json`/`goals.json`'s `required_tags`/`avoid_tags` mostly never match any `foods.json` tag) still applies unchanged — re-confirmed present in the code paths read this session (`score_food`/`rotation_score` in `diet_planner.py` both filter/score against `required_tags`/`avoid_tags` exactly as before).
- **No duplicate rule logic found** inside `diet_planner.py` itself beyond the expected near-duplication between `generate_meal_plan` and `generate_weekly_meal_plan` (the weekly version is a superset/variant of the daily version's logic, not an accidental copy of unrelated code) — see §12.

---

## 7. LLM layer inventory

**KEEP (per the final architecture decision, confirmed still wired as such):**
- Qwen local (`_call_local_transformers`, model id `Qwen/Qwen2.5-7B-Instruct`) — production answer model.
- Groq (`llm/groq_client.py::KidsNutriGroqClient`, routed via `_call_groq`) — primary judge backend (`groq_llama70b` = `llama-3.3-70b-versatile`, `groq_llama8b` = `llama-3.1-8b-instant`, `groq_qwen` = `qwen/qwen3.6-27b`, id unverified — see Phase 3 audit).
- Gemini (`_call_gemini`, model id hardcoded `gemini-2.5-flash`) — alternative/fallback judge backend.

**Not part of the finalized architecture, but still present and technically live:**
- `_call_openrouter` and its two routed model options (`"qwen"` → `qwen/qwen-2.5-7b-instruct`, `"llama"` → `meta-llama/llama-3.1-8b-instruct`) — reachable via `--model qwen`/`--model llama`, requires `OPENROUTER_API_KEY`. Not the production answer model (that's `qwen_local`), not a judge backend anywhere in the codebase. **Classification: REVIEW IN PHASE 4** (not dead — reachable and functional — but not part of the stated final architecture either; a product decision on whether to keep OpenRouter as an "optional alternative backend," as `main.py`'s own help text already calls it, or remove it).
- `"llama_local"` model option (`meta-llama/Llama-3.1-8B-Instruct` via local Transformers) — same reasoning, **REVIEW IN PHASE 4**.

**Dead/deprecated found this session:**
- `BaseJudge._call_judge` — its own docstring says "Deprecated: Use call_llm_with_retry instead." Confirmed **zero call sites** anywhere (grepped `evaluation/`, `main.py`, all test files). **Classification: DEAD, high confidence.**
- `google.generativeai` (the Gemini SDK actually used) is itself deprecated upstream (confirmed via import warning this session: "All support for the `google.generativeai` package has ended"). This is a dependency-level, not a KidsNutriBite-code-level, deprecation — see §16.

**No duplicate LLM wrappers found** — `KidsNutriGroqClient` and the various `_call_*` methods on `KidsNutriLLMClient` each have a distinct, non-overlapping responsibility. **No unused prompt templates found** in `llm/prompt_templates.py` — both `generate_llm_prompt` and `generate_qa_prompt` are live call sites (`main.py --ask`'s two branches; `evaluator.py` uses only `generate_llm_prompt`).

**Stale model identifiers**: `groq_qwen`'s `qwen/qwen3.6-27b` (flagged in Phase 3, re-confirmed here — this exact string does not match any Groq-published model-ID pattern this audit could verify without live API access).

---

## 8. Evaluation stack connectivity — the central finding of this audit

```
question (from evaluation/dataset.py's EVALUATION_DATA — the OLD 100-question set)
   ↓
evaluator.run_single_evaluation
   ↓ (retrieval — live)          ↓ (answer — live, if GPU/API available)
retrieved_contexts               response
   ↓
judges (context/grounding/relevancy/safety) — live, backend-selectable
   ↓
evaluation/metrics/*.py — pure Python, unchanged, all tests passing
   ↓
comparator.py aggregation → reports/*.csv, reports/*.md
```

**This loop is real and internally consistent** — but it runs on `evaluation/dataset.py`, not `docs/evaluation/phase2c_gold_annotations.json`. Confirmed via direct grep (§1): the new dataset file is loaded by **zero** production or evaluation code, only by this audit's own analysis and by `test_rag_chunk_id_alignment.py` (which loads it purely to validate the gold-annotation JSON's internal structure, not to run it through the evaluator).

**Practical consequence of this disconnect, precisely stated** (correcting a nuance from the Phase 3 audit for accuracy): the Phase 3 audit found that `evaluator.py` reads `test_case.get("expected_context", [])`, and that this key does not exist on the new dataset's cases (they use `gold_facts` instead), which would make Context Recall silently report `0.0` for all 49 cases **if the new dataset were ever wired in as-is**. **The old, currently-actually-used `evaluation/dataset.py` still has `expected_context` on every one of its 100 records** — so this specific bug does **not** currently manifest in practice, because the new dataset was never connected. The Context Recall / `expected_context` vs. `gold_facts` mismatch is a **latent** bug that would only trigger at the moment someone rewires `comparator.py`/`main.py` to point at the new dataset — which has not happened yet. Both facts are true simultaneously: (a) the new dataset is disconnected today, and (b) if it were connected today without also updating `evaluator.py`'s field name, Context Recall would break. Phase 4B needs to address both together, not just one.

**Dead metrics still referenced?** Checked directly: `"Average Latency"` and `"Safety F2"`/`"Safety Accuracy"` were **already actually removed** from `comparator.py`'s `comparison_records` dict (confirmed present-tense in the live code, not just historical) during the earlier metric-audit phases of this engagement. They are **not** "removed metrics still referenced" in the current Python code — the only place they're still referenced is the **stale notebook** (§9), which is a separate file, not a code inconsistency within `evaluation/`.

**Stale report fields / old terminology found**: the pre-engagement `reports/evaluation_summary.md` (tracked, generated by an older version of the code) still uses "Context Precision" (renamed to "Precision@5" in the current metric-audit terminology) and includes "PubMed Faithfulness"/"PubMed Hallucination Rate" columns that reflect the old, now-removed `is_pubmed` dataset field (confirmed dead — Phase 2A audit already found `is_pubmed` is read by zero code). This file is a stale historical snapshot, not something current code produces or reads.

**No duplicated metric calculations found** inside `evaluation/metrics/` itself — each of the four files (`retrieval_metrics.py`, `grounding_metrics.py`, `relevancy_metrics.py`, `safety_metrics.py`) owns a distinct, non-overlapping metric family.

---

## 9. Notebook dependency audit (`KidsNutriBite_Evaluation.ipynb`, 31 cells — read in full this session, not modified)

| Cell | What it does | Compatible with current code? |
|---|---|---|
| 2 (pip install) | Installs `torch transformers sentence-transformers faiss-cpu bitsandbytes accelerate python-dotenv groq google-generativeai matplotlib pandas numpy scikit-learn huggingface_hub tabulate` | **No — missing `rank-bm25`.** `rag/services/bm25_service.py` does `from rank_bm25 import BM25Okapi` unconditionally, and `RetrievalService.__init__` unconditionally constructs a `BM25Service`. Running this notebook fresh on Kaggle would `ImportError` the first time any retrieval happens (Cell 10 onward), unless `rank-bm25` happens to already be present in the Kaggle base image. `requirements.txt` (the presumed source of truth) does list `rank-bm25` — the notebook's install cell is a stale, incomplete subset of it. |
| 4 (HF login) | Kaggle-secrets-aware HF Hub login | Compatible — no code dependency issue. |
| 6 (API keys) | Sets `GEMINI_API_KEY`/`OPENROUTER_API_KEY` from Kaggle secrets, writes a local `.env` | Compatible with `llm_client.py`'s `os.getenv` usage. **Does not set `GROQ_API_KEY`** — the notebook never plumbs a Groq key through Kaggle secrets at all, despite Groq being the project's actual default judge backend. This is a real gap: as written, the notebook could never successfully exercise the actual default (`--judge-model groq_llama70b`) judge path on Kaggle. |
| 8 (dataset load verification) | Reads from `data/planner/{foods,conditions,goals,allergies}.json` | **No — wrong path.** The real directory is `data/structured_db/`. `data/planner/` does not exist anywhere in this repository. This specific cell won't crash (it has an `if os.path.exists(...) else print("Missing: ...")` guard) but will **misleadingly report all four structured-DB files as "Missing"** even though they are present and the real planner (Cell 12) loads them correctly from the right path moments later. |
| 10 (FAISS/retriever) | Builds index if missing, constructs `KidsNutriRetriever`, runs a debug retrieval | Compatible, **provided** Cell 2's missing `rank-bm25` doesn't block it first. |
| 12 (planner) | `KidsNutriDatabase()` / `DietPlanner(db)` / `generate_meal_plan` | Compatible — uses the real, correct path internally (doesn't hardcode `data/planner/` the way Cell 8 does). |
| 14 (LLM verification) | Runs `verify_gemini.py` and `verify_groq.py` only | **`verify_qwen.py` is never invoked anywhere in the notebook**, despite Qwen-local being the actual production answer model. This is a real gap in Kaggle-readiness verification — the notebook currently only smoke-tests the two judge backends, never the model that actually generates the final answer. |
| 16 (`--ask` demo) | `main.py --ask ... --model gemini` | **Contradicts the finalized architecture.** The production answer model is `qwen_local`; this cell demonstrates Gemini generating the answer instead, which is exactly the "judge backend accidentally used as the answer generator" scenario Phase 3 confirmed is *architecturally impossible via the code* but is clearly still happening *by explicit user choice* in this stale notebook cell. |
| 18 (`--evaluate`) | `main.py --evaluate --num-samples 15 --models gemini` | Same issue — evaluates Gemini as the model under test, not `qwen_local`. Also relies on the stale `EVALUATION_DATA` (§8), not the new gold dataset (not the notebook's fault — nothing currently lets it use the new dataset even if it wanted to). |
| 20 (metric report) | `pd.read_csv("reports/final_model_comparison.csv")` | Filename matches current `comparator.py` output exactly — **compatible**, but this exact file does not currently exist anywhere in the repo (§18) because no real end-to-end run has been executed against the current code in this environment. |
| 22 (CSV listing) | Lists `reports/*.csv` | Compatible, generic. |
| 24 (markdown reports) | Reads `reports/safety_analysis.md`, `reports/hallucination_analysis.md` | Filenames match current `comparator.py` output exactly — **compatible**. |
| 26 (visualization) | Plots `df[["MAP@5","MRR@5","Context Recall","Faithfulness","Answer Relevancy"]]` and `df[["Safety F2","Safety F1","Hallucination Rate (float)"]]` | **`"Safety F2"` no longer exists as a column** in the current `comparator.py`'s output (confirmed removed during the earlier safety-metric-selection phase of this engagement). This line will raise `KeyError`. |
| 28 (winners) | `df.loc[df["Safety F2"].idxmax()]`, `df.loc[df["Average Latency"].idxmin()]` | **Both columns no longer exist.** `"Average Latency"` was deliberately excluded from official reporting per `docs/latency_final_audit.md`'s architecture decision. **This cell cannot run against current code.** |
| 30 (export/zip) | Zips `reports/` folder | Compatible, generic. |

**Notebook dependencies that must remain compatible for Phase 4B** (the concrete list requested by the task): `data/structured_db/*.json` (fix the Cell 8 path), `data/rag/*` (fine), `rank-bm25` (fix Cell 2's install list), a `GROQ_API_KEY` secrets path (currently entirely absent — needs adding, not just fixing), `verify_qwen.py` (currently unreferenced — should be added to Cell 14 or a new cell), `--model`/`--models` should default to (or explicitly pass) `qwen_local` rather than `gemini` in Cells 16/18, and the final `reports/final_model_comparison.csv` column set used in Cells 26/28 must be updated to the current schema (no `Safety F2`, no `Average Latency`; current columns confirmed from `comparator.py`: `Model`, `map_5`, `MAP@5`, `map_5_valid_cases`, `map_5_missing_ground_truth`, `map_5_real_zero_cases`, `map_5_evaluation_failures`, `mrr_5`, `MRR@5`, `mrr_5_valid_cases`, `mrr_5_missing_ground_truth`, `mrr_5_real_zero_cases`, `mrr_5_evaluation_failures`, `Recall@5`, `Recall@5 Valid Count`, `Recall@5 Missing Ground Truth`, `Context Recall`, `Faithfulness`, `Answer Relevancy`, `Hallucination Rate`, `Intrinsic Response Rate`, `Extrinsic Response Rate`, `Safety Recall`, `Safety Precision`, `Safety F1`).

---

## 10. Test suite audit (every `test_*.py` file, root and `planner/`)

| File | Tests | Current code? | Obsolete? | Duplicates another? | Depends on removed functionality? | Recommendation |
|---|---|---|---|---|---|---|
| `test_precision_at_k.py` | `retrieval_metrics.calculate_precision_at_k_details` | Yes | No | No | No | KEEP |
| `test_recall_at_k.py` | `retrieval_metrics.calculate_recall_at_k_details` | Yes | No | No | No | KEEP |
| `test_map_at_k.py` | `retrieval_metrics.calculate_ap_at_k_details`/`calculate_map_at_k_details` | Yes | No | No | No | KEEP |
| `test_mrr_at_k.py` | `retrieval_metrics.calculate_mrr_at_k_details`/`calculate_mean_mrr_at_k_details` | Yes | No | No | No | KEEP |
| `test_faithfulness.py` | `grounding_metrics.calculate_faithfulness_details` | Yes | No | No | No | KEEP |
| `test_unsupported_claim_rate.py` | `grounding_metrics.calculate_unsupported_claim_rate_details` | Yes | No | No | No | KEEP |
| `test_response_hallucination_rate.py` | `grounding_metrics.calculate_response_hallucination_type_details` + response-level aggregation | Yes | No | No | No | KEEP |
| `test_answer_relevancy.py` | `relevancy_metrics.calculate_answer_relevancy` | Yes | No | No | No | KEEP |
| `test_safety_ground_truth.py` | `comparator.compute_safety_metrics` ground-truth handling | Yes | No | No | No | KEEP |
| `test_rag_chunk_id_alignment.py` | `PromptContextService` source_id passthrough + retrieval-metric canonicalization (this engagement's most recent fix) | Yes | No | No | No | KEEP |
| `test_judge_architecture.py` | `BaseJudge`, `KidsNutriLLMClient` routing, `KidsNutriGroqClient`, Gemini retry, gold-leakage, failure propagation (Phase 3) | Yes | No | No | No | KEEP |
| `test_runner.py` (root) | Manual planner smoke-test script (not `unittest`-based — a `if __name__ == "__main__"` script with `assert` statements) | Yes (imports `planner.diet_planner`, still valid) | No | Partially overlaps `planner/test_weekly_planner.py`'s coverage intent, but tests `generate_meal_plan`/`generate_weekly_meal_plan` together in one narrative script rather than isolated unit tests | No | **REVIEW** — not a `unittest` file (won't be picked up by `python -m unittest discover`), was excluded from every `discover` run performed in this engagement; still functional if run directly (`python test_runner.py`), but its filename (`test_runner.py`, no `Test` class) makes it easy to mistake for a real test suite member. |
| `planner/test_weekly_planner.py` | `generate_weekly_meal_plan` output structure/rotation | Yes | No | No | No | KEEP — **note: this file is NOT discovered by `python -m unittest discover` run from the repo root**, because `unittest discover`'s default pattern only looks in the top-level directory unless `-s planner` is passed; confirmed by this session's own repeated `python -m unittest discover` runs never mentioning it. This is a real, evidence-based gap: this test currently never runs as part of the "run the tests" habit established throughout this engagement. |

**No obsolete test found** — every test file tests currently-live code. **The one real gap**: `planner/test_weekly_planner.py` (and, differently, `test_runner.py`) are not exercised by the `python -m unittest discover` command used throughout this entire engagement's "run the tests" step, meaning the weekly-planner feature has had **zero regression coverage in every test run performed so far in this project's audit history**, despite having a real, passing test file sitting in the repo.

---

## 11. Dead-code classification (full inventory, using the required A–H scheme)

### A. ACTIVE — definitely used
`main.py`; `llm/llm_client.py`, `llm/groq_client.py`, `llm/prompt_templates.py`; `rag/chunker.py`, `rag/indexer.py`, `rag/retriever.py`, entire `rag/services/` (13 files); `planner/diet_planner.py`; `evaluation/dataset.py`, `evaluation/evaluator.py`, `evaluation/comparator.py`; `evaluation/judges/{base_judge,context_judge,grounding_judge,relevancy_judge,safety_judge}.py`; `evaluation/metrics/{retrieval_metrics,grounding_metrics,relevancy_metrics,safety_metrics}.py`; `data/structured_db/*.json`; `data/rag/{rag_data.json,faiss.index,metadata.pkl,dataset_hash.txt}`; `requirements.txt`; `.gitignore`.

### B. INDIRECTLY USED — runtime/config/notebook/dynamic
`data/validate_db.py` (invoked via `subprocess.run(["python", "data/validate_db.py"])` from `test_runner.py` — a dynamic subprocess call, correctly not missed by grep-for-import); `verify_gemini.py`, `verify_groq.py` (invoked via notebook `!python` shell-out, Cell 14 — not a Python import, correctly classified as indirectly used, not dead); `planner/generate_weekly_meal_plan` (used only by its own test files, not by any CLI/evaluator entry point — indirectly used via tests, in-development feature).

### C. TEST-ONLY — intentionally retained for tests
All 12 `test_*.py` files (§10) plus `planner/test_weekly_planner.py`.

### D. DOC-ONLY — intentionally retained documentation
`README.md`, `project_formulas_and_papers.md`, `llm_judge_analysis.md`, `research_notes.md`, `technical_documentation.md`, all of `docs/` (every `.md` and the one `.docx`), `docs/doctor_review/knowledge_base_change_log_template.md`.

### E. GENERATED — should not normally be committed
`data/rag/faiss.index`, `data/rag/metadata.pkl`, `data/rag/dataset_hash.txt` (all three are fully reproducible from `data/rag/rag_data.json` via `python main.py --index` — **yet all three are currently tracked in git**, see §13/§19); `reports/model_comparison_report.csv`, `reports/model_comparison_report.json`, `reports/detailed_evaluation_records.csv` (tracked, generated by an *older* version of the pipeline — see §19); every `__pycache__/*.pyc` (untracked, correctly `.gitignore`d already); this session's own `reports/debug/llm_call_metadata_latest.json`, `reports/judge_parse_failures.csv`, `reports/judge_raw_outputs.log` (untracked, produced as a side effect of `BaseJudge`'s unconditional logging during Phase 3's test runs).

### F. EXPERIMENTAL — likely removable, needs human decision
`llm/llm_client.py`'s OpenRouter routes (`"qwen"`, `"llama"`) and `"llama_local"` route (§7); `data/recall5_annotation_template.json` (an unfilled scaffold from an earlier phase of this engagement, superseded in practice by the fully-populated `docs/evaluation/phase2c_gold_annotations.json` — every `relevant_chunk_ids` field in the template is still `[]`, and nothing in current code reads this file at all); `planner/generate_weekly_meal_plan` and its test (real, working, but not yet integrated into any production entry point — a human product decision on timeline, not a code-quality issue).

### G. DEAD — proven unused (see §21 for full evidence per file)
`rag/bm25_retriever.py`, `rag/config.py`, `rag/dataset_hasher.py`, `rag/logger.py`, `rag/performance_monitor.py`, `rag/reranker.py`, `rag/semantic_cache.py` (all seven — superseded by `rag/services/`, zero imports anywhere); `evaluation/judges/base_judge.py::BaseJudge._call_judge` (dead method inside a live file — the file stays, the method is provably unreachable).

### H. UNCERTAIN — insufficient evidence
`verify_qwen.py` — not referenced by the notebook (confirmed) or any other code, but its purpose (a standalone Kaggle GPU/model smoke-test, structurally identical in spirit to `verify_gemini.py`/`verify_groq.py`, which *are* notebook-referenced) strongly suggests it is meant to be run manually or was omitted from the notebook by oversight rather than by design. **Cannot determine intent from code alone** — flagged for a human decision rather than classified as dead. `reports/architecture_research_study.md`, `reports/context_recall_failure_analysis.md`, `reports/retrieval_diagnostics.md`, `reports/manual_verification_report.md`, `reports/prototype_audit_report.md`, `reports/inference_validation.md`, `reports/evaluation_summary.md` — confirmed these are hand-written/historically-generated (not reproducible by current code, using stale terminology), but whether the project wants to keep them as a historical record or remove them as clutter is a **product/archival decision**, not something this audit can resolve from evidence alone.

---

## 12. Duplication audit

| What's duplicated | Where | Identical behavior? | Safe to merge? | Recommended future location |
|---|---|---|---|---|
| RAG service logic (BM25, cache, config, dataset-hash, logging, metrics/performance, reranking) | `rag/{bm25_retriever,config,dataset_hasher,logger,performance_monitor,reranker,semantic_cache}.py` **vs.** `rag/services/{bm25_service,config_service,dataset_version_service,logger_service,metrics_service,reranker_service,cache_service}.py` | Not verified line-by-line (the flat versions are provably unreachable, so their internal behavior is moot), but the naming and role mapping is unambiguous 1:1 | **Yes — the flat versions can be deleted outright**, not "merged" (nothing calls them, there's nothing to reconcile) | N/A — deletion candidate, not a merge candidate |
| Daily vs. weekly meal-planning logic | `planner/diet_planner.py::generate_meal_plan` vs. `generate_weekly_meal_plan` | No — genuinely different (daily: 4 meal slots, simple greedy fill; weekly: 6 slots × 7 days, rotation-penalty scoring) | Not safe to merge — this is intentional feature scope difference, not accidental duplication | Keep separate; if anything, extract the shared `score_food`-style scoring helper (each method defines its own near-identical local `score_food`/`rotation_score` closure) into a shared module-level function |
| Allergy/age filtering logic | Repeated near-verbatim inside both `generate_meal_plan` and `generate_weekly_meal_plan` (the `is_allergic` check block, ~15 lines, is copy-pasted with no differences) | Yes — identical | **Yes, safe to extract into a shared private method** (e.g. `_filter_candidate_foods`) | `planner/diet_planner.py`, as a new `DietPlanner` method |
| Model-comparison report generation | `reports/model_comparison_report.csv`/`.json` (tracked, from an older version of `comparator.py`) vs. `final_model_comparison.csv` (current `comparator.py`'s actual output filename, never yet generated in this repo) | Different schemas (older report has `PubMed Faithfulness` etc. that no longer exist) | Not a code duplication — a **stale generated-artifact vs. current-code-output** mismatch, not two code paths producing the same thing | See §19 — recommend removing the stale generated files, not merging them |
| Judge retry/parsing logic | None found — correctly centralized once in `BaseJudge`, not duplicated per-judge | N/A | N/A | N/A |
| Constants (model IDs, metric names) | No duplicated constant definitions found across files (e.g., `"qwen_local"` is checked as a string literal in multiple places — `main.py`, `llm_client.py` — but this is normal string-based dispatch, not a duplicated *definition*) | N/A | Low-priority: could centralize model-name string literals into a shared constants module, but this is a style preference, not a bug | Deferred |

---

## 13. GitHub relevance audit

| Item | Currently tracked? | Recommend KEEP IN GITHUB or LOCAL/GENERATED/IGNORE | Why |
|---|---|---|---|
| `data/rag/faiss.index` (1.1 MB), `data/rag/metadata.pkl` (268 KB), `data/rag/dataset_hash.txt` | **Tracked** | **Reconsider — candidate for LOCAL/GENERATED.** Fully reproducible in seconds via `python main.py --index` from `data/rag/rag_data.json` (which itself should stay tracked). Committing binary index artifacts means every KB-content edit produces an unreadable binary diff and repo bloat over time. Counter-argument: keeping it committed means a fresh clone can run `--ask`/`--evaluate` immediately without a build step — a genuine convenience for Kaggle/CI. **This is a judgment call for Phase 4B, not a clear-cut removal.** |
| `_paper_check/*.pdf` (7 files, 13.3 MB largest) | Tracked | **Reconsider.** These are reference PDFs used for citation verification during this engagement's research phases (confirmed referenced only from `docs/claude_project_understanding.md` and `project_formulas_and_papers.md`, never loaded by code). A 13 MB PDF is a large binary for a git repo; consider keeping only the citation (title/DOI/URL) in the docs and dropping the PDFs themselves, or moving them to Git LFS / a release asset if the team wants them preserved. |
| `reports/model_comparison_report.csv`/`.json`, `reports/detailed_evaluation_records.csv` | Tracked | **LOCAL/GENERATED — recommend untracking.** Stale output from an older code version; regenerable (once the dataset-connectivity fix in §8/§15 is made) via `--evaluate`; keeping stale generated data in git risks someone mistaking it for current results. |
| `reports/*.md` (architecture_research_study, context_recall_failure_analysis, evaluation_summary, inference_validation, manual_verification_report, prototype_audit_report, retrieval_diagnostics) | Tracked | **KEEP, but relocate/relabel as historical.** These are hand-written research narratives with real investigative value (some document exactly the kind of RAG/retrieval issues this engagement independently rediscovered), but their *current* location inside `reports/` (a directory whose other contents are meant to be fresh generated run output) invites confusion between "this is live" and "this is a 2026-era historical snapshot." A `docs/history/` or `docs/archive/` location would better signal their nature — see §14. |
| `reports/debug/`, `reports/judge_parse_failures.csv`, `reports/judge_raw_outputs.log` | **Untracked** (my own session's test-run byproducts) | **IGNORE.** These should never be committed — recommend adding `reports/debug/`, `reports/judge_parse_failures.csv`, `reports/judge_raw_outputs.log` (or simply `reports/` generated-output patterns generally) to `.gitignore` in Phase 4B. |
| `.claude/` (specifically `settings.local.json`) | **Untracked** | **Recommend adding to `.gitignore`.** This is a per-developer/per-session Claude Code tool-permission file, not project source — analogous to `.vscode/settings.json` or `.idea/`, which are conventionally ignored. No evidence it needs to be shared via version control; every other engineer/session would generate their own. **Explicit recommendation: YES, ignore `.claude/`** (not modified this task, per instruction — recommendation only). |
| `docs/` (all audit/research/doctor-review markdown + the phase2b/phase2c JSON + the phase2d .docx) | **Untracked** | **KEEP IN GITHUB — recommend tracking.** This is the actual substantive deliverable of Phases 1–4 of this engagement (schema, gold annotations, doctor-review packet, audits) — it belongs in version control, not local-only. |
| `data/recall5_annotation_template.json` | **Untracked** | **REVIEW.** Superseded in practice by the populated `phase2c_gold_annotations.json`; either keep as a historical scaffold-format reference or remove once the team confirms it's no longer needed as a template. |
| All 10 new `test_*.py` root-level files | **Untracked** | **KEEP IN GITHUB — recommend tracking.** Real, passing, currently-relevant test coverage. |
| `__pycache__/` (everywhere) | Untracked | **Already correctly ignored** via `.gitignore`'s `__pycache__/` line — no change needed. |
| `.env` | N/A (does not exist in this repo) | **Already correctly ignored** via `.gitignore`'s `.env` line, and confirmed (§17) it has never existed in this repo's history. |

---

## 14. Proposed future folder structure (PROPOSAL ONLY — not implemented)

```
CURRENT (relevant subset)                       PROPOSED
.                                                .
├── rag/                                         ├── rag/
│   ├── bm25_retriever.py  (DEAD)                │   ├── chunker.py
│   ├── config.py          (DEAD)                │   ├── indexer.py
│   ├── dataset_hasher.py  (DEAD)                │   ├── retriever.py
│   ├── logger.py          (DEAD)                │   └── services/  (unchanged - already well-organized)
│   ├── performance_monitor.py (DEAD)            │
│   ├── reranker.py        (DEAD)                │
│   ├── semantic_cache.py  (DEAD)                │
│   ├── chunker.py                               │
│   ├── indexer.py                               │
│   ├── retriever.py                             │
│   └── services/ (13 files, already good)       │
│                                                 │
├── reports/ (mixed fresh + stale + historical)  ├── reports/            (fresh, generated-only, gitignored)
│                                                 ├── docs/history/       (the 7 hand-written stale .md research reports)
│                                                 │
├── (root-level) verify_gemini.py                ├── scripts/
├── (root-level) verify_groq.py                  │   ├── verify_gemini.py
├── (root-level) verify_qwen.py                  │   ├── verify_groq.py
├── (root-level) test_runner.py                  │   ├── verify_qwen.py
├── data/validate_db.py                          │   └── validate_db.py   (moved from data/)
│                                                 │
├── (root-level) test_*.py (10 files)             ├── tests/
├── planner/test_weekly_planner.py                │   ├── test_*.py (all 10, moved from root)
│                                                 │   └── planner/test_weekly_planner.py (moved)
│                                                 │
├── (root-level) llm_judge_analysis.md            ├── docs/
├── (root-level) research_notes.md                │   ├── llm_judge_analysis.md
├── (root-level) technical_documentation.md       │   ├── research_notes.md
├── (root-level) project_formulas_and_papers.md   │   ├── technical_documentation.md
│                                                 │   ├── project_formulas_and_papers.md
│                                                 │   └── (everything already in docs/, unchanged)
│                                                 │
├── _paper_check/*.pdf                            ├── docs/references/*.pdf  (or removed, see §13)
│                                                 │
├── evaluation/dataset.py (old, still wired)      ├── evaluation/
├── docs/evaluation/phase2b_evaluation_questions.json │   ├── dataset.py            (retired or repointed - see §15)
├── docs/evaluation/phase2c_gold_annotations.json │   └── gold_dataset.py OR data/evaluation/phase2c_gold_annotations.json  (the file the code should actually import)
```

**For every proposed move:**

| Current path | Proposed path | Why | Dependencies to update | Risk |
|---|---|---|---|---|
| `rag/{bm25_retriever,config,dataset_hasher,logger,performance_monitor,reranker,semantic_cache}.py` | *(deleted, not moved)* | Zero live references anywhere | None — nothing imports them | **Low** — deletion is safe by the evidence in §21, but should be a Phase 4B human-approved step, not automatic |
| `verify_gemini.py`, `verify_groq.py`, `verify_qwen.py`, `data/validate_db.py` | `scripts/` | Groups standalone diagnostic/utility scripts separately from the application package structure | Notebook Cell 14 (`!python verify_gemini.py` → `!python scripts/verify_gemini.py`); `test_runner.py`'s `subprocess.run(["python", "data/validate_db.py"])` → update path | **Medium** — touches the notebook, which the task explicitly says not to modify yet; a real Phase 4B step, not this one |
| All root-level `test_*.py`, `planner/test_weekly_planner.py` | `tests/` | Standard Python convention; currently split between root and `planner/`, inconsistent | `python -m unittest discover` invocation would need `-s tests` or a root `tests/__init__.py`; CI/habit commands used throughout this engagement would need updating | **Medium** — every "run the tests" step in this engagement's own established habit would need to change its invocation |
| `llm_judge_analysis.md`, `research_notes.md`, `technical_documentation.md`, `project_formulas_and_papers.md` | `docs/` | Consolidates all documentation under one directory (currently split between repo root and `docs/`) | Any cross-references between these files and others (none found via grep this session referencing them by relative path) | **Low** |
| `reports/architecture_research_study.md`, `context_recall_failure_analysis.md`, `evaluation_summary.md`, `inference_validation.md`, `manual_verification_report.md`, `prototype_audit_report.md`, `retrieval_diagnostics.md` | `docs/history/` (new folder) | Separates permanent historical research narrative from `reports/`'s actual purpose (fresh, disposable, generated run output) | None (not referenced by any code or the notebook) | **Low** |
| `_paper_check/*.pdf` | `docs/references/` (or remove — see §13) | Groups reference material under `docs/`; or drop entirely if the team decides citations-in-text are sufficient | `docs/claude_project_understanding.md`, `project_formulas_and_papers.md` reference this path by name — would need updating if moved | **Low-Medium** (only two doc files reference it) |
| `docs/evaluation/phase2c_gold_annotations.json` | *(stays where it is, OR moves to `data/evaluation/`)* | The real fix here is not a file move but a code change — `comparator.py` needs to import from wherever this file ends up | `evaluation/comparator.py` line 7 | **High** — this is the single most important, most carefully-sequenced Phase 4B change (see §15); recommend deciding the final path *before* writing the import fix, not moving it twice |

**Do not force these names** — this is one reasonable proposal given actual usage patterns found this session, not a mandate. In particular, the `rag/services/` package is already well-organized internally and should not be restructured further.

---

## 15. Production-connectivity audit (explicit per-component verdicts)

| Component | Verdict | Evidence |
|---|---|---|
| Qwen local | **CONNECTED CORRECTLY** | `main.py`'s default `--model`/`--models` is `qwen_local`; `_call_local_transformers` is reachable and correctly gated by a GPU check; never reachable from any judge code path (confirmed in Phase 3, re-confirmed this session). |
| RAG | **CONNECTED CORRECTLY** | Full chunker→indexer→FAISS/BM25→fusion→rerank→prompt-context chain confirmed live and internally consistent (§5); `source_id` canonical-ID fix confirmed still in place. |
| Structured DB | **CONNECTED CORRECTLY** | `KidsNutriDatabase` loads the real path correctly; consumed by both `generate_meal_plan` (production-integrated) and `generate_weekly_meal_plan` (test-integrated only). |
| Planner | **CONNECTED CORRECTLY** (daily) / **PARTIALLY CONNECTED** (weekly) | `generate_meal_plan` is called by both `main.py --ask`/`--plan` and `evaluator.py`; `generate_weekly_meal_plan` is fully implemented and tested but has zero callers outside its own tests. |
| Prompt generation | **CONNECTED CORRECTLY** | `generate_llm_prompt`/`generate_qa_prompt` both live, both reachable, correctly receive only runtime data (re-confirmed, no gold leakage, per Phase 3). |
| Groq judge | **CONNECTED CORRECTLY** | Confirmed default (`--judge-model groq_llama70b`), confirmed reachable, confirmed interface-compatible with all four judges (Phase 3). Notebook does not currently exercise this path (§9), which is a notebook gap, not a code connectivity gap. |
| Gemini judge | **CONNECTED CORRECTLY** | Fully wired as a configurable alternative; confirmed reachable via `--judge-model gemini`; confirmed interface-compatible (Phase 3). |
| Evaluation metrics | **CONNECTED CORRECTLY**, with one **PARTIALLY CONNECTED** caveat | All four metric families are correctly wired to their respective judges and to `comparator.py`'s aggregation; Context Recall is technically connected but functionally degraded against the (currently unused) new dataset schema (§8). |
| Comparator | **PARTIALLY CONNECTED** | Correctly aggregates and reports everything it's given — but what it's given (`EVALUATION_DATA` from the old `evaluation/dataset.py`) is not the project's actual finalized evaluation dataset. The code path itself is fully functional; the *data* it's wired to is stale. |
| Notebook | **PARTIALLY CONNECTED / NOT CONNECTED (mixed, cell-by-cell)** | See the full cell-by-cell table in §9 — roughly half the cells are compatible as-is, the other half reference stale paths, stale model choices, or removed columns. |

**No component was found to be entirely NOT CONNECTED** — every piece of the intended architecture has at least a real, functioning code path. The failures found are **data-wiring and documentation-staleness problems**, not missing or broken application logic.

---

## 16. Environment / dependency audit

`requirements.txt` (17 lines, re-read this session): `torch`, `transformers`, `sentence-transformers`, `faiss-cpu`, `bitsandbytes`, `accelerate`, `python-dotenv`, `groq`, `google-generativeai`, `matplotlib`, `pandas`, `numpy`, `scikit-learn`, `huggingface_hub`, `tabulate`, `rank-bm25`.

- **Missing from `requirements.txt` but actually imported by live code**: none found — every import in `rag/`, `llm/`, `evaluation/` traces to a package in this list (or the Python standard library).
- **Present in `requirements.txt` but only reachable via non-default/optional code paths**: `google-generativeai` (only used if `--judge-model gemini` or `--model gemini`, not the default for either); `bitsandbytes` (only used for 4-bit quantization inside `_call_local_transformers`, gracefully degrades to float16 if absent per the code's own `except ImportError` handling — so not strictly required, but needed for the documented "fits in 15GB VRAM" Kaggle-T4 use case).
- **Duplicated packages**: none.
- **Packages needed only by obsolete code**: none of the seven dead `rag/*.py` files import anything that the live `rag/services/` equivalents don't already need — no dependency is uniquely tied to dead code.
- **Packages needed by Kaggle specifically**: `huggingface_hub` (login), `bitsandbytes`+`accelerate` (T4 4-bit quantization), all confirmed still required by live code.
- **`python-dotenv` is listed in `requirements.txt` but never actually imported anywhere in the Python codebase** (`llm_client.py` reads env vars via plain `os.getenv`, no `dotenv.load_dotenv()` call found anywhere in `main.py`, `llm/`, `evaluation/`, or `rag/`). The notebook manually writes a `.env` file (Cell 6) but never loads it via `python-dotenv` either — it works only because Kaggle-secrets-sourced values are set directly into `os.environ` in the same cell, making the `.env` file write essentially inert. **This is a real, evidence-based "declared but unused" dependency finding.**
- **CPU/GPU assumptions**: `qwen_local`/`llama_local` hard-require CUDA (explicit `RuntimeError` if absent — confirmed, and confirmed to actually trigger in this sandbox); every other backend (Groq, Gemini, OpenRouter) is CPU-only/network-based. `faiss-cpu` (not `faiss-gpu`) is specified — consistent with FAISS search being cheap enough to not need GPU acceleration for this corpus size (551 records).

---

## 17. Security / secrets audit

| File | Line/location | Secret type | Action recommended |
|---|---|---|---|
| *(none found)* | — | — | — |

**Full result**: grepped the entire repository (all `.py`, `.json`, `.md`, `.ipynb`, `.txt` files, excluding `.git/`) for API-key/secret/token/password patterns and for real-looking credential shapes (Groq `gsk_...`, Gemini `AIza...`, OpenAI-style `sk-...`, HuggingFace `hf_...`). **Zero real secret values found anywhere.** Every match was either (a) an environment-variable *name* reference (`os.getenv("GEMINI_API_KEY")`, `os.getenv("GROQ_API_KEY")`, etc. — code, not a secret), or (b) an explicit placeholder string (the notebook's `"YOUR_GEMINI_API_KEY"`, `"YOUR_OPENROUTER_API_KEY"`). No `.env` file exists anywhere in the working tree, and `git log --all --diff-filter=A --name-only | grep -i "\.env"` returned **zero results** — confirming (consistent with this engagement's earlier `.env`-history-purge work) that no `.env` file has ever been added to this repository's git history. `.gitignore` already correctly excludes `.env`.

**For the final Kaggle design**: consistent with the notebook's existing pattern (Kaggle Secrets → `os.environ`), no committed-credential risk was found that needs remediation.

---

## 18. Git / repository state audit

- **Tracked files**: 81 (`git ls-files`).
- **Untracked files**: 99, comprising: this entire engagement's `docs/` output (Phases 1–4, ~24 files), all 10 new root-level `test_*.py` files, `test_judge_architecture.py` + `test_rag_chunk_id_alignment.py`, `.claude/settings.local.json`, `data/recall5_annotation_template.json`, every `__pycache__/*.pyc` (correctly ignored, shown by `git status` as untracked-but-would-be-ignored), and this session's leftover `reports/debug/`, `reports/judge_parse_failures.csv`, `reports/judge_raw_outputs.log`.
- **Recent commits** (`git log --oneline`, 3 total in this repo's history): `cac28a0` "fix: Update Groq Qwen ID and set Groq Llama as default judge" (the commit that made Groq the deliberate default, referenced throughout Phase 3); `4535df2` "Release v1.0: Final Deterministic Evaluation Architecture & Refactored Notebook"; `9ac89a9` "Initial commit: KidsNutriBite project structure and research study". **No commits exist reflecting any of this engagement's Phase 1–4 work** — everything from the `.env`-purge onward is uncommitted, working-tree-only state.
- **Large files** (by disk size, largest first): `_paper_check/llama2_2307.09288.pdf` (13.3 MB, tracked), `_paper_check/2411.00300.pdf` (6.2 MB, tracked), `_paper_check/2603.03301.pdf` (1.9 MB, tracked), `data/rag/faiss.index` (1.1 MB, tracked), several more `_paper_check/*.pdf` (0.4–0.8 MB each, tracked), `data/rag/metadata.pkl` (268 KB, tracked). **The `_paper_check/` PDFs collectively account for the large majority of this repository's total tracked size.**
- **What should eventually be committed** (currently untracked but belongs in git): all of `docs/`, all new `test_*.py` files — this is real, valuable project output.
- **What should be ignored** (currently untracked, correctly should stay that way): `.claude/`, `reports/debug/`, `reports/judge_parse_failures.csv`, `reports/judge_raw_outputs.log`, all `__pycache__/`.
- **What should arguably be removed from the repo** (currently tracked, candidate for untracking): `data/rag/faiss.index`/`metadata.pkl`/`dataset_hash.txt` (regenerable), `reports/model_comparison_report.csv`/`.json`, `reports/detailed_evaluation_records.csv` (stale, from an older code version) — all judgment calls for Phase 4B, not executed here.

**Nothing was committed, staged, or modified as part of this audit.**

---

## 19. Risks

- **Risk of fixing the dataset-connectivity gap (§8/§15) without also fixing the `expected_context`/`gold_facts` field mismatch (Phase 3 finding)**: would silently zero out Context Recall the moment the new dataset goes live — these two fixes must be sequenced together, not independently.
- **Risk of deleting the seven dead `rag/*.py` files without a final live-grep re-check immediately before deletion**: low, but non-zero — dynamic imports (`importlib`, `__import__`, string-based module loading) were specifically checked for and **none were found** anywhere in this codebase referencing these seven files, but a final re-check at the moment of deletion (not weeks later) is good practice given how much can change between audit and execution.
- **Risk of moving `test_*.py` files into a `tests/` folder**: every "run the tests" habit established throughout this entire engagement invoked `python -m unittest discover` from the repo root with no `-s` flag — moving the files would silently break that exact command unless a `tests/__init__.py` or equivalent discovery configuration is added at the same time.
- **Risk of touching the notebook**: explicitly out of scope for this phase and for Phase 4B's first pass per the task's own instructions elsewhere in this engagement ("do not modify the notebook") — but the notebook's staleness (§9) means it **cannot currently be run successfully end-to-end on Kaggle today**, which is itself a risk to the project's stated Kaggle-T4-evaluation goal, independent of any cleanup work.
- **Risk of removing `_paper_check/*.pdf` or the stale `reports/*.md` history files**: low technical risk (nothing imports them), but real *informational* risk if the team wants to preserve the research trail they represent — recommend archiving (move to `docs/history/`/`docs/references/`), not deleting, unless explicitly confirmed unwanted.
- **Risk of leaving `data/rag/faiss.index`/`metadata.pkl` committed indefinitely**: low immediate risk, but binary-diff repo bloat compounds every time the RAG corpus is edited (as it already was, once, during the iron-bioavailability fix) — worth deciding the policy before the next KB edit, not after several more have accumulated.

---

## 20. Recommended cleanup order (for Phase 4B — NOT executed now)

1. **Decide and fix the dataset-connectivity gap first** (§8/§15): point `evaluation/comparator.py` at the real, doctor-review-pending-safety-ground-truth-aside, finalized dataset — and in the same change, fix `evaluator.py`'s `expected_context` → `gold_facts` field read (Phase 3 finding) so Context Recall doesn't silently break the moment the new dataset is connected. This is the highest-value, highest-risk-if-done-partially change, so it should go first and be tested thoroughly before anything else.
2. **Delete the seven proven-dead `rag/*.py` files** (§7/§11/§21) — lowest-risk deletion in this entire audit (zero references found anywhere), good "first win" to build confidence before touching anything riskier.
3. **Remove `BaseJudge._call_judge`** (dead method, zero call sites).
4. **Fix the three stale defaults** found across this engagement's Phase 3 and Phase 4A audits together in one pass: `KidsNutriEvaluator.__init__`'s `judge_model="gemini"` → `"groq_llama70b"`; `KidsNutriComparator.run_comparison`'s `models=["gemini", "qwen_local"]` → `["qwen_local"]`; confirm `main.py`'s CLI defaults are already correct (they are).
5. **Update the notebook** (§9) — fix the `data/planner/` path, add `rank-bm25` to the pip-install cell, add a Groq-secrets cell, add a `verify_qwen.py` invocation, change `--model gemini`/`--models gemini` to `qwen_local`, and update the final visualization/winners cells to the current column schema (no `Safety F2`, no `Average Latency`).
6. **Decide the fate of** the OpenRouter/`llama_local` model routes, `data/recall5_annotation_template.json`, the stale `reports/*.md` historical files, and `_paper_check/*.pdf` — human product decisions, not evidence-driven deletions.
7. **Decide the FAISS-index-in-git policy** (§13/§19) and act on it consistently.
8. **Add `.claude/` and generated `reports/` byproducts to `.gitignore`** (only after the above is settled, so the `.gitignore` change reflects the final structure, not an intermediate one).
9. **Restructure folders** (§14), only after 1–8 are stable and tested — folder moves should be the *last* structural change, not the first, so import-path fixes aren't done twice.
10. **Run the full test suite, `compileall`, and a CLI smoke test** after every one of the above steps, not just at the end.

---

## 21. Proposed deletions — full evidence per file (required format)

**File**: `rag/bm25_retriever.py`
**Classification**: DEAD
**Evidence**: zero imports anywhere (`from rag.bm25_retriever import` / `import rag.bm25_retriever` — grepped whole repo, 0 matches); not referenced in the notebook; not referenced in any test; not referenced in any config; `rag/services/bm25_service.py` is the actual, live BM25 implementation used by `RetrievalService.__init__`.
**What depends on it**: nothing.
**Risk if deleted**: none identified.
**Confidence**: High.

**File**: `rag/config.py`
**Classification**: DEAD
**Evidence**: same method as above, 0 matches; `rag/services/config_service.py`'s `RAGConfig`/`ConfigurationService` is the live implementation actually imported by `rag/retriever.py` and `rag/indexer.py`.
**What depends on it**: nothing.
**Risk if deleted**: none identified.
**Confidence**: High.

**File**: `rag/dataset_hasher.py`
**Classification**: DEAD
**Evidence**: 0 matches; `rag/services/dataset_version_service.py::DatasetVersionService` is the live implementation, directly confirmed in use by `rag/indexer.py::build_index` and `RetrievalService.__init__` this session (its hash appeared in this session's actual retrieval-event logs).
**What depends on it**: nothing.
**Risk if deleted**: none identified.
**Confidence**: High.

**File**: `rag/logger.py`
**Classification**: DEAD
**Evidence**: 0 matches; `rag/services/logger_service.py::LoggerService` is the live implementation (its `log_retrieval_event` output was directly observed in this session's own test runs).
**What depends on it**: nothing.
**Risk if deleted**: none identified.
**Confidence**: High.

**File**: `rag/performance_monitor.py`
**Classification**: DEAD
**Evidence**: 0 matches; `rag/services/metrics_service.py::MetricsService` is the live implementation (its `create_timer`/`record_step`/`finalize_timer` calls were directly observed in `RetrievalService.retrieve`'s source this session).
**What depends on it**: nothing.
**Risk if deleted**: none identified.
**Confidence**: High.

**File**: `rag/reranker.py`
**Classification**: DEAD
**Evidence**: 0 matches; `rag/services/reranker_service.py::RerankerService` is the live implementation (directly read this session, confirmed as the sole reranking code path).
**What depends on it**: nothing.
**Risk if deleted**: none identified.
**Confidence**: High.

**File**: `rag/semantic_cache.py`
**Classification**: DEAD
**Evidence**: 0 matches; `rag/services/cache_service.py::CacheService` is the live implementation (directly read this session, confirmed as the sole cache code path, including the semantic-similarity cache-hit logic).
**What depends on it**: nothing.
**Risk if deleted**: none identified.
**Confidence**: High.

**File**: `evaluation/judges/base_judge.py::BaseJudge._call_judge` (a method, not a whole file — the file itself is very much ACTIVE)
**Classification**: DEAD
**Evidence**: the method's own docstring says "Deprecated: Use call_llm_with_retry instead. Kept for short-term compatibility if needed."; grepped `evaluation/`, `main.py`, every test file for `_call_judge` — 0 call sites found anywhere.
**What depends on it**: nothing.
**Risk if deleted**: none identified.
**Confidence**: High.

**No other file in this repository met this audit's evidentiary bar for a DEAD classification.** Everything else is at minimum ACTIVE, INDIRECTLY USED, TEST-ONLY, DOC-ONLY, GENERATED, EXPERIMENTAL, or UNCERTAIN (§11) — none of those weaker categories are proposed for deletion here; they require a human product decision, not a code-evidence deletion.

---

## 22. Proposed final structure

Already given in full in §14. Reproduced here as the compact before/after tree per the task's request:

```
CURRENT                                  PROPOSED
rag/ (7 dead flat files + 6 live + services/)   rag/ (6 live files + services/, dead files removed)
reports/ (fresh + stale + historical mixed)     reports/ (fresh only) + docs/history/ (historical)
verify_*.py, test_runner.py, validate_db.py at root/data/   scripts/ (all four)
test_*.py split across root + planner/          tests/ (all, including planner's)
docs + 4 root-level .md files                   docs/ (all documentation consolidated)
_paper_check/ at root                           docs/references/ (or removed)
evaluation/dataset.py (wired, but old data)      evaluation/dataset.py repointed to the real finalized dataset
```

**Not implemented. Proposal only, pending your review.**

---

## 23. Final decision table

| Path | Classification | Keep? | Proposed action | Evidence | Confidence |
|---|---|---|---|---|---|
| `main.py` | ACTIVE | Yes | KEEP | Sole CLI entry point, all 5 modes traced | High |
| `llm/llm_client.py` | ACTIVE | Yes | KEEP | Central dispatcher, traced fully | High |
| `llm/groq_client.py` | ACTIVE | Yes | KEEP | Live Groq wrapper | High |
| `llm/prompt_templates.py` | ACTIVE | Yes | KEEP | Both functions have live call sites | High |
| `rag/chunker.py` | ACTIVE | Yes | KEEP | Used by indexer | High |
| `rag/indexer.py` | ACTIVE | Yes | KEEP | Used by `main.py --index` and auto-rebuild | High |
| `rag/retriever.py` | ACTIVE | Yes | KEEP | Sole public retriever facade | High |
| `rag/services/*.py` (13 files) | ACTIVE | Yes | KEEP | All imported by `RetrievalService` | High |
| `rag/bm25_retriever.py` | DEAD | No | DELETE | Zero references anywhere | High |
| `rag/config.py` | DEAD | No | DELETE | Zero references anywhere | High |
| `rag/dataset_hasher.py` | DEAD | No | DELETE | Zero references anywhere | High |
| `rag/logger.py` | DEAD | No | DELETE | Zero references anywhere | High |
| `rag/performance_monitor.py` | DEAD | No | DELETE | Zero references anywhere | High |
| `rag/reranker.py` | DEAD | No | DELETE | Zero references anywhere | High |
| `rag/semantic_cache.py` | DEAD | No | DELETE | Zero references anywhere | High |
| `planner/diet_planner.py` | ACTIVE | Yes | KEEP | Core planner, both entry points | High |
| `planner/test_weekly_planner.py` | TEST-ONLY | Yes | KEEP (move to `tests/`) | Real, passing, but not `discover`-reachable from root | High |
| `evaluation/dataset.py` | ACTIVE (stale data) | Yes, but REVIEW | REVIEW — repoint or replace with the finalized dataset | Only dataset `comparator.py` actually loads | High |
| `evaluation/evaluator.py` | ACTIVE | Yes | KEEP (needs the `gold_facts` field fix, separately tracked) | Core orchestrator | High |
| `evaluation/comparator.py` | ACTIVE (stale default + stale data source) | Yes | REVIEW — fix `models=` default and dataset import | Confirmed both issues by direct read | High |
| `evaluation/judges/*.py` (5 files) | ACTIVE | Yes | KEEP | All reachable, Phase 3-audited | High |
| `evaluation/judges/base_judge.py::_call_judge` | DEAD (method) | No | DELETE (method only, keep file) | Self-documented deprecated, 0 call sites | High |
| `evaluation/metrics/*.py` (4 files) | ACTIVE | Yes | KEEP | All reachable, extensively tested | High |
| `data/structured_db/*.json` | ACTIVE | Yes | KEEP | Loaded by planner | High |
| `data/rag/rag_data.json` | ACTIVE | Yes | KEEP | Source of truth for RAG | High |
| `data/rag/faiss.index`, `metadata.pkl`, `dataset_hash.txt` | GENERATED | Yes (for now) | REVIEW — consider untracking, regenerable | Confirmed reproducible via `--index` | Medium (policy call, not evidence gap) |
| `data/recall5_annotation_template.json` | EXPERIMENTAL | Uncertain | REVIEW | Superseded by phase2c dataset, unfilled, unread by code | Medium |
| `data/validate_db.py` | INDIRECTLY USED | Yes | KEEP (move to `scripts/`) | Called via subprocess from `test_runner.py` | High |
| `docs/**` (all, incl. phase2b/2c JSON, phase2d docx) | DOC-ONLY / DATA | Yes | KEEP, track in git | This engagement's actual deliverable | High |
| `docs/doctor_review/knowledge_base_change_log_template.md` | DOC-ONLY | Yes | KEEP | Active process template | High |
| `reports/model_comparison_report.csv`/`.json`, `detailed_evaluation_records.csv` | GENERATED (stale) | No | REVIEW — untrack, regenerate fresh once dataset fix lands | Schema mismatch vs. current `comparator.py` confirmed | High |
| `reports/*.md` (7 historical files) | DOC-ONLY (stale/historical) | Yes | REVIEW — move to `docs/history/` | Hand-written, not code-reproducible, stale terminology confirmed | High |
| `reports/debug/`, `judge_parse_failures.csv`, `judge_raw_outputs.log` | GENERATED | No (as committed artifacts) | IGNORE — add to `.gitignore` | Produced as this session's own test-run side effect | High |
| `verify_gemini.py`, `verify_groq.py` | INDIRECTLY USED | Yes | KEEP (move to `scripts/`) | Notebook `!python` shell-out, Cell 14 | High |
| `verify_qwen.py` | UNCERTAIN | Yes (likely) | REVIEW — confirm intent, then wire into notebook or keep as manual tool | Not notebook-referenced, but structurally identical purpose to the two that are | Medium |
| `test_runner.py` | TEST-ONLY (non-standard) | Yes | KEEP (move to `scripts/` or `tests/`, clarify it's not `unittest`-discoverable) | Confirmed not picked up by `unittest discover` | High |
| All 10 root-level `test_*.py` | TEST-ONLY | Yes | KEEP, track in git (optionally move to `tests/`) | All pass, all test live code | High |
| `_paper_check/*.pdf` (7 files) | DOC-ONLY (reference) | Yes | REVIEW — keep, move to `docs/references/`, or drop (large binaries) | Referenced only from 2 doc files, never by code | High |
| `llm_judge_analysis.md`, `research_notes.md`, `technical_documentation.md`, `project_formulas_and_papers.md` | DOC-ONLY | Yes | KEEP (move to `docs/`) | No code references; pure documentation | High |
| `.claude/settings.local.json` | Session config | Yes (locally) | IGNORE (add `.claude/` to `.gitignore`) | Per-session tool-permission file, not project source | High |
| `KidsNutriBite_Evaluation.ipynb` | ACTIVE (stale in parts) | Yes | REVIEW — fix per §9's cell-by-cell list | Multiple confirmed stale references | High |
| `requirements.txt` | ACTIVE | Yes | KEEP | Matches actual imports; `python-dotenv` unused but harmless | High |
| `.gitignore` | ACTIVE (incomplete) | Yes | REVIEW — extend per §13 (not done this task) | Only 2 lines currently; misses `.claude/`, `reports/` generated output | High |
| `README.md` | DOC-ONLY | Yes | KEEP | Project overview | High |

---

## 24. Test / validation plan for Phase 4B (to be executed only after approval — NOT run now)

1. Fix the dataset-connectivity gap: repoint `evaluation/comparator.py` to the finalized dataset, and fix `evaluator.py`'s `expected_context`→`gold_facts` read in the same change.
2. Remove the seven approved-dead `rag/*.py` files (final live-grep re-check immediately before deletion, per §19's risk note).
3. Remove `BaseJudge._call_judge`.
4. Fix the three stale defaults (`KidsNutriEvaluator.judge_model`, `KidsNutriComparator.run_comparison`'s `models=`, and re-confirm `main.py`'s are already correct).
5. Update imports/paths for anything moved (if folder moves are approved for this pass).
6. Update the notebook (path fix, `rank-bm25` install, Groq secrets cell, `verify_qwen.py` invocation, `qwen_local` instead of `gemini`, current column schema in the visualization/winners cells).
7. Update `.gitignore` (add `.claude/`, generated `reports/` byproducts) — only if approved.
8. Decide and act on the FAISS-index-in-git and stale-`reports/`-artifact policy — only if approved.
9. Run `python -m unittest discover -v` (and explicitly also `planner/test_weekly_planner.py` and `test_runner.py`, which are not covered by the bare `discover` command — a gap this audit found, see §10).
10. Run `python -m compileall -q .`.
11. Run a CLI smoke test: `python main.py --index`, `python main.py --plan --age 5 --condition healthy_growth --goal balanced_nutrition`, `python main.py --ask "..." --model qwen_local` (expected to fail gracefully with the documented `RuntimeError` in a no-GPU environment — confirm the failure message is still correct, not that it succeeds), `python main.py --evaluate --num-samples 3` (same GPU caveat).
12. Run a Kaggle-compatibility check: confirm the updated notebook's pip-install cell lists every package `requirements.txt` lists, confirm every hardcoded path in every cell resolves against the actual repo structure post-move.
13. Review `git status` and `git diff` in full before staging anything.
14. Commit a clean baseline — first commit in this repository's history to include any of this engagement's Phase 1–4 work.

**None of the above has been executed.** This document is the complete evidence base for deciding which of these steps to approve, defer, or reject.
