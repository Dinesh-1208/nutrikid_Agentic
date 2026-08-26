# Phase 4B — High-Confidence Cleanup + Final Evaluation Dataset Wiring

**Branch: `phase4b-high-confidence-cleanup`, created from the current `main` (post-checkpoint-merge, commit `6f6a98e`). No changes were made to `main`. This document lives on this branch only until reviewed.**

**Status: this is the "high-confidence" pass only — dataset wiring, Context Recall field mapping, seven proven-dead RAG files, one dead method, and three stale defaults. No notebook change, no folder restructuring, no OpenRouter/`llama_local` removal, no `reports/` archival, no FAISS-in-git policy change, no `.gitignore` change, no knowledge-base/gold-content/planner change, per explicit scope.**

---

## 1. What was changed

1. **Connected the finalized 49-question dataset to the runtime.** `evaluation/dataset.py` is now a loader that reads `docs/evaluation/phase2c_gold_annotations.json` and exposes it as `EVALUATION_DATA` — the exact same import name every existing call site (`evaluation/comparator.py`) already used, so no call site needed to change.
2. **Preserved the old 100-question dataset, unmodified, under a new name** in a new file, `evaluation/legacy_dataset.py`, as `LEGACY_EVALUATION_DATA` — not deleted, not wired into anything, clearly labeled as historical.
3. **Fixed Context Recall's gold-field wiring.** `evaluator.py` now builds its `expected_context` list from the finalized dataset's `gold_facts[].fact_text` (plain strings only — never the raw fact dicts with provenance metadata), instead of reading the now-nonexistent `expected_context` key.
4. **Fixed a newly-discovered, necessary companion bug**: `evaluator.py` used to do `profile = test_case["profile"]` — a direct key access that would `AttributeError`-crash the moment a knowledge-only case (`profile: null`, true for 28 of the 49 finalized cases) reached `planner.generate_meal_plan(profile)`. Changed to `profile = test_case.get("profile") or {}`. Every downstream consumer already reads profile fields via `.get(key, default)`, so an empty dict safely triggers those existing defaults — nothing was invented.
5. **Deleted the seven proven-dead first-generation RAG modules**: `rag/bm25_retriever.py`, `rag/config.py`, `rag/dataset_hasher.py`, `rag/logger.py`, `rag/performance_monitor.py`, `rag/reranker.py`, `rag/semantic_cache.py`.
6. **Deleted the dead `BaseJudge._call_judge` method** (the file `evaluation/judges/base_judge.py` remains — only the one method was removed).
7. **Fixed three stale defaults**: `KidsNutriEvaluator.__init__`'s `judge_model` (`"gemini"` → `"groq_llama70b"`), `KidsNutriComparator.run_comparison`'s `models` (`["gemini", "qwen_local"]` → `["qwen_local"]`), and re-confirmed `main.py`'s three CLI defaults were already correct (unchanged).
8. **Fixed two existing tests whose assumptions were made false by the dataset swap**, and **added one new test file** covering the full integration.

---

## 2. Exact files modified

| File | Change |
|---|---|
| `evaluation/dataset.py` | Rewritten from a 759-line hardcoded 100-question list into a ~35-line loader for the finalized JSON dataset. |
| `evaluation/evaluator.py` | `profile` now defaults to `{}` instead of crashing on `None`; `expected_context` now derived from `gold_facts[].fact_text` instead of the removed `expected_context` key; `judge_model` default fixed. |
| `evaluation/comparator.py` | `run_comparison`'s `models` default fixed. |
| `evaluation/judges/base_judge.py` | Removed the dead `_call_judge` method (4 lines). |
| `test_map_at_k.py` | Removed its dependency on the real `EVALUATION_DATA` (previously asserted it had exactly 100, all-unannotated cases — no longer true); replaced with a self-contained synthetic unannotated batch that tests the same invariant. |
| `test_mrr_at_k.py` | Same fix, mirrored. |
| `test_judge_architecture.py` | Fixed a pre-existing test-fixture mislabeling (a marker meant to represent `reference_answer` was accidentally placed inside `gold_facts.fact_text`, which — now that `gold_facts` correctly reaches `ContextJudge.evaluate_recall` by design — made the test wrongly flag approved behavior as a leak). Rewrote the assertion to precisely check the real boundary: `gold_facts.fact_text` is expected only inside the context judge's `evaluate_recall` call; `relevant_chunk_ids`/`reference_answer` must never appear in any judge call or the production prompt; the raw fact dict shape (`fact_id`, etc.) must never appear anywhere. |

## 3. Exact files deleted

`rag/bm25_retriever.py`, `rag/config.py`, `rag/dataset_hasher.py`, `rag/logger.py`, `rag/performance_monitor.py`, `rag/reranker.py`, `rag/semantic_cache.py` — 7 files, all previously confirmed (Phase 4A) and re-confirmed this session (fresh repo-wide grep immediately before deletion, per the task's own instruction) to have zero imports, zero notebook references, zero test references, zero dynamic/string/subprocess references anywhere.

## 4. Exact files created

- `evaluation/legacy_dataset.py` — the old 100-question dataset, verbatim, renamed to `LEGACY_EVALUATION_DATA`, with a header explaining its status.
- `test_final_dataset_integration.py` — new focused test file (22 tests, see §7).

---

## 5. Final evaluation dataset wiring — how it works now

```
docs/evaluation/phase2c_gold_annotations.json   (49 cases, unchanged, not touched this phase)
    ↓  json.load, at import time
evaluation/dataset.py :: EVALUATION_DATA        (49 case dicts, verbatim)
    ↓  from evaluation.dataset import EVALUATION_DATA   (unchanged import statement)
evaluation/comparator.py :: run_comparison
    ↓  per case
evaluation/evaluator.py :: run_single_evaluation
    ↓
retrieval (live) → Qwen/whichever model is under test (live) → judges (Groq/Gemini) → metrics → report layer
```

Verified directly (not assumed): `len(EVALUATION_DATA) == 49`; ids are exactly `EVAL_001`..`EVAL_049` in order; `evaluation.comparator`'s own `EVALUATION_DATA` binding is the same 49-case set; `evaluation.legacy_dataset.LEGACY_EVALUATION_DATA` still has all 100 original entries, untouched, and is imported nowhere in `comparator.py`'s source (checked by direct string search, not just by import graph). A full mocked run of `run_single_evaluation` was executed this session against both a knowledge-only case (`profile: null`, e.g. `EVAL_001`) and a profile-aware case (e.g. `EVAL_011`) — both completed without error.

## 6. Context Recall field mapping — before/after

**Before:**
```python
expected_context = test_case.get("expected_context", [])
```
The finalized dataset has no `expected_context` key on any of its 49 cases (confirmed: 0/49). This meant `expected_context` was always `[]`, which makes `ContextJudge.evaluate_recall` short-circuit to `{"facts": []}` without ever calling an LLM, and `calculate_context_recall([])` returns a hardcoded `0.0` — a silent, deterministic zero for every case, indistinguishable from "the answer covered none of the expected facts."

**After:**
```python
expected_context = [
    fact.get("fact_text")
    for fact in (test_case.get("gold_facts") or [])
    if fact.get("fact_text")
]
```
Verified this pulls the exact `fact_text` strings authored in Phase 2C's gold annotation (checked byte-for-byte equality against the source JSON for a sample case), and only the plain text — never `fact_id`, `source_reference`, `chunk_reference`, or `importance`. Confirmed all 49 finalized cases have at least one `gold_facts` entry with non-empty `fact_text` (checked this session: 0 cases with empty/missing `gold_facts`, 0 gold-fact entries with missing `fact_text`), so the pre-existing "empty list → silent 0.0" behavior of `calculate_context_recall` is **not currently exercised by any of the 49 real cases** — it remains a latent, documented, deliberately-not-fixed edge case for any future case that might lack `gold_facts`, exactly matching the "do not invent a new status enum unless the current code genuinely requires one" instruction: it does not, for this dataset, today.

**No Context Recall formula change. No `ContextJudge` prompt change. No new status enum introduced.**

## 7. Default-model changes

| Location | Old default | New default |
|---|---|---|
| `KidsNutriEvaluator.__init__`'s `judge_model` | `"gemini"` | `"groq_llama70b"` |
| `KidsNutriComparator.run_comparison`'s `models` | `["gemini", "qwen_local"]` | `["qwen_local"]` |
| `main.py --model` | `"qwen_local"` (already correct) | unchanged |
| `main.py --models` | `"qwen_local"` (already correct) | unchanged |
| `main.py --judge-model` | `"groq_llama70b"` (already correct) | unchanged |

Gemini was not removed anywhere — confirmed still fully reachable and functional via `--judge-model gemini` / `--model gemini`, and via `KidsNutriEvaluator(..., judge_model="gemini")`.

## 8. Tests added/changed

**New file `test_final_dataset_integration.py`** (22 tests):
- `TestFinalizedDatasetIsTheActiveDataset` (7 tests) — exact 49-case count, exact ID sequence, `comparator.py`'s own binding is the new dataset (and provably disjoint from legacy IDs), the legacy dataset is preserved and unreferenced by `comparator.py`, `relevant_chunk_ids` intact (38 populated / 11 `null`, never `[]`), `safety_ground_truth` null on all 49, and the loaded data matches the source JSON byte-for-byte.
- `TestContextRecallGoldFieldWiring` (4 tests) — `gold_facts.fact_text` (plain strings) reaches the context judge exactly, the old `expected_context` key is confirmed absent from every case and confirmed no longer read by `evaluator.py`'s source, and a knowledge-only (`profile: null`) case runs without crashing while still producing real expected-context content.
- `TestDeadCodeRemoval` (3 tests) — the seven dead files no longer exist on disk AND no longer import (`ImportError` asserted), the seven live `rag/services/` equivalents still import correctly, and `BaseJudge._call_judge` no longer exists while `call_llm_with_retry` still does.
- `TestCorrectedDefaults` (8 tests) — the two Python-level defaults are fixed (checked via `inspect.signature`, not just by reading source text), `main.py`'s three CLI defaults are confirmed still correct, Qwen-local is confirmed to still be the only route `generate_response("qwen_local")` reaches, Groq (`llama-3.3-70b-versatile`) is confirmed reachable as the default judge backend, Gemini is confirmed still reachable as an alternative, and `KidsNutriEvaluator`'s auto-constructed judges (when `judge_model` isn't explicitly passed) are confirmed to all use `groq_llama70b`.

**Modified**: `test_map_at_k.py`, `test_mrr_at_k.py` (decoupled from the real `EVALUATION_DATA`, using a synthetic unannotated batch instead — see §2); `test_judge_architecture.py` (fixed a pre-existing test-fixture mislabeling exposed by the Context Recall fix — see §2).

No test in this set requires a live external API — all use `unittest.mock`.

## 9. Test results

```
python -m unittest test_final_dataset_integration -v   → 22 tests, OK
python -m unittest test_judge_architecture -v            → 22 tests, OK (1 pre-existing test fixed)
python -m unittest discover -v                            → 124 tests, OK
python -m unittest planner.test_weekly_planner -v         → 3 tests, OK (this project's known discover-gap, run explicitly per instruction)
```

124 = 102 pre-Phase-4B tests (unchanged in count; two had their bodies fixed, not removed) + 22 new. The weekly-planner test suite (not picked up by bare `unittest discover`, a pre-existing, documented project gap — see `docs/phase4_repository_audit.md` §10) was run explicitly and separately, per instruction, and passes.

## 10. Compile result

```
python -m compileall -q .   → clean, no errors
```

Also directly verified (beyond `compileall`'s syntax-only check): `rag/retriever.py::KidsNutriRetriever` still constructs and runs a real retrieval (`retriever.retrieve("Can my child eat egg during fever?", top_k=3)`) successfully after the seven-file deletion, confirming no runtime import regression, not just a syntax-level pass.

## 11. Git diff summary

Branch: `phase4b-high-confidence-cleanup`, created from `main` at `6f6a98e` (the just-merged checkpoint). **Nothing was staged or committed until this report was written and reviewed internally; `main` was never touched.**

```
 evaluation/comparator.py        |   2 +-
 evaluation/dataset.py           | 794 ++--------------------------------------
 evaluation/evaluator.py         |  29 +-
 evaluation/judges/base_judge.py |   4 -
 rag/bm25_retriever.py           |   3 -    (deleted)
 rag/config.py                   |   3 -    (deleted)
 rag/dataset_hasher.py           |   3 -    (deleted)
 rag/logger.py                   |   3 -    (deleted)
 rag/performance_monitor.py      |   3 -    (deleted)
 rag/reranker.py                 |   3 -    (deleted)
 rag/semantic_cache.py           |   3 -    (deleted)
 test_judge_architecture.py      |  36 +-
 test_map_at_k.py                |  16 +-
 test_mrr_at_k.py                |  16 +-
 14 files changed, 121 insertions(+), 797 deletions(-)
```
Plus 2 new untracked files at report time: `evaluation/legacy_dataset.py`, `test_final_dataset_integration.py`.

**Untouched by this phase** (verified via `git status`/`git diff` showing no entry for them): the notebook, the planner, every knowledge-base JSON, the FAISS index/metadata, every `docs/doctor_review/*` file, `docs/evaluation/phase2c_gold_annotations.json` itself (only *read*, never written), `.gitignore`, `requirements.txt`, OpenRouter/`llama_local` routing code, and every `reports/*` file.

---

## 12. Confirmations

- **49 questions unchanged**: `evaluation/dataset.py`'s loaded `EVALUATION_DATA` was diffed against a fresh `json.load` of `docs/evaluation/phase2c_gold_annotations.json` this session and found byte-for-byte identical (`EVALUATION_DATA == raw["cases"]`, asserted in `test_final_dataset_integration.py`).
- **Gold facts unchanged**: the source JSON file was never opened for writing this phase — only read, by the new loader and by the test suite. No `Write`/`Edit` tool call touched `docs/evaluation/phase2c_gold_annotations.json`.
- **Reference answers unchanged**: same reasoning — read-only.
- **`safety_ground_truth` unchanged/null**: confirmed `null` on all 49 cases, both before and after this phase; no doctor label was invented, inferred, or simulated.
- **RAG data unchanged**: `data/rag/rag_data.json`, `faiss.index`, `metadata.pkl`, `dataset_hash.txt` were not opened for writing this phase; the only RAG-side change was deleting seven dead *Python code* files, which is unrelated to the RAG *data*.
- **Planner unchanged**: `planner/diet_planner.py` and `planner/test_weekly_planner.py` were not modified.
- **Notebook unchanged**: `KidsNutriBite_Evaluation.ipynb` was not opened for writing.
- **Groq/Gemini retained**: both remain fully present, both remain reachable (Groq now the confirmed default judge, matching the already-established project decision; Gemini confirmed still selectable), neither backend's client code (`llm/groq_client.py`, `_call_gemini`) was modified.
- **OpenRouter / `llama_local` retained**: not touched, per explicit scope exclusion.

---

## 13. Deferred to a later, broader Phase 4 pass (explicitly not done here)

Notebook update (stale `data/planner/` path, missing `rank-bm25` in the pip-install cell, `--model gemini`/`--models gemini` instead of `qwen_local`, removed `Safety F2`/`Average Latency` columns in the visualization cells, no Groq secrets wiring, `verify_qwen.py` never invoked); folder restructuring (`scripts/`, `tests/`, `docs/history/`); OpenRouter/`llama_local` keep-or-remove decision; `reports/` historical-file archival; FAISS-index-in-git policy; `.gitignore` extension (`.claude/`, generated `reports/` byproducts); and the eventual commit/merge of that broader work. All of these remain exactly as documented in `docs/phase4_repository_audit.md`, awaiting your review of this narrower diff first.
