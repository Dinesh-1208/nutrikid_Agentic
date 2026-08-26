# Phase 4C — Kaggle Notebook Update for the Final 49-Case Evaluation

**Scope of this phase:** update and validate `KidsNutriBite_Evaluation.ipynb` only. No Python application code, metrics, dataset, gold annotations, safety ground truth, RAG data, FAISS index, planner, `requirements.txt`, or `.gitignore` was modified. Nothing was committed or pushed — this document and the notebook diff are for your review first.

---

## 1. What the old notebook did

31 cells, roughly following the pre-Phase-4B architecture:

1. **Section 1-2 (info/install):** project description; `pip install` of 15 packages, missing `rank-bm25`.
2. **Section 3 (HF login):** Kaggle-Secrets-based `HF_TOKEN` login.
3. **Section 4 (API keys):** loaded `GEMINI_API_KEY`/`OPENROUTER_API_KEY` from Kaggle Secrets (no `GROQ_API_KEY` at all) and **wrote them to a plaintext `.env` file** on disk.
4. **Section 5 (dataset loading):** checked structural JSONs under `data/planner/` (wrong path) and `data/rag/rag_data.json`.
5. **Section 6 (FAISS):** shelled out to `!python main.py --index` if `faiss.index` was missing, then initialized `KidsNutriRetriever` and called `debug_retrieve`.
6. **Section 7 (planner):** initialized `DietPlanner` and ran one profile-aware smoke test.
7. **Section 8 (LLM verify):** shelled out to `verify_gemini.py` and `verify_groq.py` (Qwen was never verified).
8. **Section 9 (single-query demo):** `!python main.py --ask ... --model gemini` — Gemini as the answer model.
9. **Section 10 (evaluation):** `!python main.py --evaluate --num-samples 15 --models gemini` — 15 samples of the old 100-question dataset, Gemini as the answer model.
10. **Sections 11-13 (reports):** loaded `reports/final_model_comparison.csv`, listed CSVs, displayed safety/hallucination markdown extracts.
11. **Section 14-15 (visualizations/comparison):** bar charts and a "winners" summary referencing `Safety F2` and `Average Latency` columns.
12. **Sections 16-17 (export):** zipped `reports/` and offered a `FileLink` download.

## 2. What was stale

Confirmed against the current, post-Phase-4B repository (source of truth: the actual code, not the previous audit's notes):

| # | Issue | Confirmed against |
|---|---|---|
| A | `data/planner/` does not exist | `Glob data/planner/*` → no results; `KidsNutriDatabase.__init__` (`planner/diet_planner.py:9`) already defaults to `data/structured_db` |
| B | `rank-bm25` missing from the notebook's install cell | `requirements.txt` line 16 has it; `rag/services/bm25_service.py` imports it; old notebook's install cell omitted it |
| C | No `GROQ_API_KEY` handling at all | Groq is now the default judge (`KidsNutriEvaluator.__init__`, Phase 4B); old notebook only loaded Gemini/OpenRouter |
| D | Gemini used as the answer model in demo/evaluate commands | Final architecture: `qwen_local` is the only answer model; Gemini/Groq are judge-only |
| E | Qwen local loading never verified | `verify_qwen.py` exists but was never invoked; no cell exercised `_call_local_transformers` |
| F | Stale metric references: `Safety F2`, `Average Latency` | `evaluation/comparator.py`'s `comparison_records` dict (current code) only ever writes `Safety Recall`/`Safety Precision`/`Safety F1`; Latency is explicitly excluded (`docs/latency_final_audit.md`, referenced in `comparator.py`'s own comment) |
| G | Old 100-question dataset / `--num-samples 15` | `evaluation/dataset.py` now loads the finalized 49-case `docs/evaluation/phase2c_gold_annotations.json` (Phase 4B) |
| (extra) | Plaintext `.env` with real secret values written to disk | `Section 4` cell of the old notebook: `open(".env", "w")` |
| (extra) | `OPENROUTER_API_KEY` wired in, but OpenRouter is not part of the final architecture's Kaggle run | Final architecture: Qwen local (answer) + Groq default / Gemini alt (judge) only |

## 3. What was changed

The notebook was rewritten cell-by-cell into the 13-section structure requested, preserving nothing merely for historical reasons. Every code cell calls the project's real implementation — no retrieval, planning, prompting, judging, or metrics logic is reimplemented in the notebook.

| Old section(s) | Old behavior | New section | New behavior | Why |
|---|---|---|---|---|
| 2 (install) | 15 packages, no `rank-bm25` | 3 | Explicit list incl. `rank-bm25`; drops `python-dotenv` | `rank-bm25` required by `rag/services/bm25_service.py`; `python-dotenv` no longer used (no `.env` file is written anymore) |
| 3 + 4 (HF login, API keys/.env) | Two cells; wrote `GEMINI_API_KEY`/`OPENROUTER_API_KEY` to a plaintext `.env`; no Groq | 4 | One cell; reads `GROQ_API_KEY` + `GEMINI_API_KEY` (+ optional `HF_TOKEN`) from Kaggle Secrets into `os.environ` only; prints only `YES`/`NO`; never writes `.env` | Matches the final architecture (Groq default judge) and the explicit "no persistent plaintext secrets file" requirement |
| 5 (dataset loading) | Checked `data/planner/` | 7 | Checks `data/structured_db/` | Wrong path in the old notebook; confirmed via `KidsNutriDatabase`'s own default |
| 6 (FAISS) | `!python main.py --index` shell-out | 6 | Direct `from rag.indexer import build_index` call | Same real project code, no subprocess/interpreter/cwd ambiguity inside a Kaggle kernel |
| 7 (planner) | One profile-aware case only | 7 | Profile-aware case **and** a knowledge-only case (`profile: null`), mirroring `evaluator.py`'s own Phase 4B `.get("profile") or {}` fix | The finalized dataset has 28/49 cases with `profile: null`; this must be verified, not assumed |
| 8 (LLM verify) | Shelled out to `verify_gemini.py`/`verify_groq.py`; Qwen never verified | 8 + 9 | Direct `KidsNutriLLMClient.generate_response(..., "qwen_local")` smoke test (Section 8); direct `SafetyJudge` smoke test for both Groq and Gemini (Section 9) | Exercises the exact same code path the real run uses (`_call_local_transformers`, `call_llm_with_retry`'s JSON parsing) instead of a separate script; Qwen is now actually verified before the full run |
| 9 (single-query demo) | `--model gemini` | *(removed)* | — | Not part of the required 13-section structure; superseded by the Section 6-8 smoke tests and the Section 10 full run; Gemini must never be the answer model |
| 10 (evaluation) | `--evaluate --num-samples 15 --models gemini` | 10 | Real `KidsNutriEvaluator`/`KidsNutriComparator` call; `ANSWER_MODEL = "qwen_local"`; `JUDGE_MODEL = "groq_llama70b"` (switchable to `"gemini"`, no code edits); all 49 finalized cases (`sample_limit=None`) | Gemini must never be the answer model; the dataset is the finalized 49-case set, not the retired 100-question set; judge backend must be configurable from one variable |
| 11-13 (reports) | Loaded CSV, listed files, displayed markdown extracts | 11 | Displays `final_comparison_df` (the real `comparator.py` output) directly, with an explicit note on why Safety metrics may read `MISSING_GROUND_TRUTH` | No manual reformatting of metrics; honest about pending doctor review |
| *(none)* | — | 12 | New: per-case status breakdown from `ragas_report.csv` + aggregate valid/missing/failure counts from `final_comparison_df` | Status-enum architecture (`VALID`/`MISSING_GROUND_TRUTH`/`EVALUATION_FAILURE`/`REAL_ZERO`) must never be silently collapsed to 0 in a notebook display — this was not verified anywhere in the old notebook |
| 14-15 (visualizations/comparison) | Bar charts + "winners" referencing `Safety F2`, `Average Latency` | *(removed)* | — | Both metrics are formally retired (`docs/safety_evaluation_literature_audit.md`, `docs/latency_final_audit.md`); not part of the current official metric set; not required by the target 13-section structure |
| 16-17 (export) | Zipped `reports/` in place | 13 | Copies `comparator.reports_dir` into a `kidsnutribite_outputs/` export folder under `/kaggle/working/`, zips it, prints a full run summary (models, GPU, case count, failure/missing counts, commit hash) | Matches the requested writable-output-path convention and the "final output/results" requirements in one place |

## 4. Final Kaggle workflow

```
Approved Git snapshot
    -> ZIP
    -> Kaggle Dataset (attached to the notebook)
    -> /kaggle/input/<KAGGLE_PROJECT_DATASET>/          (read-only)
    -> Section 2: locate + extract/copy
    -> /kaggle/working/kidsnutribite_project/            (writable project root)
    -> Section 5: os.chdir + sys.path insert
    -> Section 3: pip install (torch, transformers, sentence-transformers,
       faiss-cpu, bitsandbytes, accelerate, groq, google-generativeai,
       rank-bm25, pandas, numpy, matplotlib, scikit-learn, huggingface_hub,
       tabulate)
    -> Section 4: Kaggle Secrets -> os.environ
    -> Section 6: RAG init (real rag/retriever.py + rag/services/*)
    -> Section 7: Structured DB / Planner init (real planner/diet_planner.py)
    -> Section 8: Qwen local load + smoke test (real llm/llm_client.py)
    -> Section 9: Groq/Gemini judge smoke test (real evaluation/judges/safety_judge.py)
    -> Section 10: full 49-case run (real evaluation/evaluator.py + comparator.py)
    -> Section 11-12: metrics + status/failure display
    -> Section 13: /kaggle/working/kidsnutribite_outputs/ + zip + FileLink
```

`KAGGLE_PROJECT_DATASET` is a single variable at the top of Section 2 (default `"nutrikid-agentic"`) — edit it to match whatever slug the dataset is actually attached under. If it doesn't match and exactly one dataset is attached, the notebook falls back to that one dataset automatically (never guesses among several) and prints which one it used. Section 2 handles both an already-extracted dataset tree (`main.py` present at the top level — Kaggle's normal behavior for a zip uploaded as a Dataset) and a dataset that still contains a `.zip` file, extracting either case into `/kaggle/working/kidsnutribite_project/`. The notebook never attempts to write into `/kaggle/input/...`.

## 5. API key / secret workflow

```
Kaggle Secrets (GROQ_API_KEY, GEMINI_API_KEY, optional HF_TOKEN)
    -> UserSecretsClient().get_secret(...)
    -> os.environ["GROQ_API_KEY"] / os.environ["GEMINI_API_KEY"]
    -> KidsNutriLLMClient / KidsNutriGroqClient (existing project code, unmodified)
    -> Groq / Gemini judge calls
```

- Only `YES`/`NO` is ever printed for each key — never the value.
- No `.env` file (or any other persistent plaintext copy) is written anywhere in the new notebook.
- Secrets are loaded in **Section 4**, strictly before **Section 5** onward instantiates any project client — `KidsNutriLLMClient.__init__` reads `GEMINI_API_KEY` from `os.environ` at construction time (`llm/llm_client.py:13`), so this ordering is required, not incidental.
- `OPENROUTER_API_KEY` is intentionally not wired into this notebook: OpenRouter is not part of the final Qwen/Groq/Gemini architecture for the Kaggle run. Its code (`llm/llm_client.py`'s `_call_openrouter`) is untouched and still usable outside this notebook.

## 6. Qwen loading workflow

Section 8 calls `KidsNutriLLMClient().generate_response(system_prompt, user_prompt, model_name="qwen_local")` directly — the exact same `_call_local_transformers` path (`llm/llm_client.py:91`) the full Section 10 run uses, including its existing model-caching (`self.loaded_models`) so Qwen is loaded onto the GPU only once per kernel session, not reloaded for the full evaluation. No second/independent Qwen-loading implementation was written in the notebook; `verify_qwen.py`'s separate implementation is intentionally not invoked from the notebook for this reason (it remains available as a standalone CLI diagnostic).

## 7. Groq/Gemini judge workflow

Section 9 instantiates the real `SafetyJudge` (`evaluation/judges/safety_judge.py`) against both backends with a trivial, safe example and asserts the returned value is a parsed dict containing `"overall"` — this exercises `BaseJudge.call_llm_with_retry`'s actual JSON-parsing path, not a plain chat completion, so a judge JSON-schema regression would be caught here before the 49-case run starts. Groq is required for the default run; Gemini is skipped gracefully (not failed) if `GEMINI_API_KEY` isn't set, since it's optional unless `JUDGE_MODEL` is changed to `"gemini"` in Section 10.

## 8. 49-case dataset workflow

Section 5 imports `evaluation.dataset.EVALUATION_DATA` (the Phase-4B loader for `docs/evaluation/phase2c_gold_annotations.json`) and asserts `len(...) == 49` with IDs `EVAL_001`..`EVAL_049`. Section 10 passes this dataset through the real `KidsNutriComparator.run_comparison(["qwen_local"], sample_limit=None)` — `sample_limit=None` runs all 49 cases, not a subset. The dataset is never recreated, duplicated, or hardcoded in the notebook.

## 9. Gold-data leakage checks

- `retriever.retrieve()` (Section 6) takes only the query string — gold `relevant_chunk_ids` are structurally impossible to pass into it or into the generation prompt.
- Section 10 calls the real `evaluator.run_single_evaluation` (unmodified in this phase), which — per the Phase 4B fix already in place — only ever sends `gold_facts[].fact_text` to the `ContextJudge`'s recall call, never to the production Qwen prompt; `reference_answer` and `safety_ground_truth` are read only for report/metric comparison (`comparator.py`), never passed into any generation or judge prompt.
- No cell in the new notebook places any gold field into a generation prompt for debugging, and none did in the diff review.

## 10. Metric/report changes

No metric formula was changed in this phase (comparator.py/evaluator.py/metrics/*.py were not touched). The notebook now:
- Displays exactly the columns `comparator.py` currently produces (Section 11) instead of a stale/reformatted subset.
- Never references `Safety Accuracy`, `Safety F2`, or `Average Latency` (removed with Sections 14-15).
- Explicitly surfaces `MISSING_GROUND_TRUTH` and `EVALUATION_FAILURE` counts/statuses rather than collapsing them (Section 12) — this check did not exist in the old notebook at all.

## 11. Smoke-test results

**Not executed on Kaggle T4 as part of this phase** — this phase is notebook authoring + structural/static validation only, per the task's explicit boundary ("Do NOT run the 49-case final evaluation locally if the local environment cannot support Qwen GPU inference... STOP after the notebook is updated and validated"). What *was* validated locally (see §13 for exact commands):
- The notebook's JSON is well-formed (`nbformat` 4.0, standard `kernelspec`/`language_info`).
- Every one of the 13 code cells parses as valid Python (shell-magic `!pip install` line excluded from the parse check, as expected).
- No stale metric/dataset/path references remain (`Safety F2`, `Average Latency`, `data/planner`, `--model gemini`, `--models gemini` all absent from executable code; the only textual matches are this notebook's own markdown explaining what was *removed*).
- No literal secret values are present anywhere in the file.
- `rank-bm25`, `data/structured_db`, `qwen_local` as `ANSWER_MODEL`, and `groq_llama70b` as `JUDGE_MODEL` are all present.
- `git status`/`git diff --stat` confirm only `KidsNutriBite_Evaluation.ipynb` changed; no project Python file, dataset, or config was modified.

**The actual 49-case Qwen-on-T4 run has not been performed.** Do not treat this document as evidence that it has.

## 12. Remaining blockers

- **Doctor safety review (Phase 2D) is still pending.** Safety Recall/Precision/F1 will read `MISSING_GROUND_TRUTH` on the real Kaggle run until doctor-approved `safety_ground_truth` is added to the dataset — this is expected, not a notebook defect.
- **`KAGGLE_PROJECT_DATASET` must be set to the real attached dataset slug** before running on Kaggle (defaults to a placeholder, `"nutrikid-agentic"`, with a single-dataset auto-fallback).
- **Kaggle Secrets `GROQ_API_KEY` and `GEMINI_API_KEY` must be added** to the Kaggle notebook's secrets store before running Section 4 for real judge calls to succeed (Groq is required for the default configuration; Gemini only if `JUDGE_MODEL` is switched).
- **This notebook has not yet been executed top-to-bottom on actual Kaggle T4 hardware.** That is the next step, outside this phase's boundary, and its own results (once run) should not be assumed from this document.

## 13. Final run instructions

1. Upload the approved Git snapshot as a `.zip` and create/update a Kaggle Dataset from it; attach that dataset to this notebook.
2. Open `KidsNutriBite_Evaluation.ipynb` on Kaggle with a **GPU T4** accelerator enabled (Settings -> Accelerator).
3. In Kaggle's notebook secrets, add `GROQ_API_KEY` and `GEMINI_API_KEY` (and optionally `HF_TOKEN`).
4. In Section 2, set `KAGGLE_PROJECT_DATASET` to the exact dataset slug shown in the "Data" pane (skip if there is only one attached dataset).
5. Run all cells top to bottom. Each of Sections 6, 7, 8, and 9 is a smoke test that should complete and print a confirmation before Section 10 (the full 49-case run) starts.
6. After Section 10 completes, Sections 11-13 display metrics, status/failure breakdowns, and produce a downloadable `KidsNutriBite_Reports.zip` under `/kaggle/working/`.

### Local validation performed for this phase (not the Kaggle run itself)

```
python -c "import json; json.load(open('KidsNutriBite_Evaluation.ipynb', encoding='utf-8'))"   # valid JSON
python -c "<parse every code cell with ast.parse>"                                              # all 13 code cells parse
python -c "<substring checks for stale/forbidden references>"                                    # clean
git status --short && git diff --stat                                                            # only the notebook changed
```
