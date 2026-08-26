# RAG Chunk-ID Alignment — Investigation and Fix

**Status: Investigation complete, minimum fix implemented, all tests passing. No knowledge content, question text, gold facts, reference answers, safety ground truth, the 15–35% iron correction, the planner, judges, or the notebook were modified.**

---

## 1. Full ID pipeline trace (with direct evidence)

```
rag_data.json record "id" (source_id)
    ↓  rag/chunker.py::ParentChildChunker.process_documents
parent chunk id  =  f"{source_id}_P{p_idx}"          (almost always _P0 — see §3)
    ↓  same function, child-splits each parent
child chunk id   =  f"{parent_id}_C{c_idx}"           (e.g. "..._P0_C0", "..._P0_C1", ...)
    ↓  rag/indexer.py::build_index embeds child_chunks, saves to metadata.pkl + faiss.index
    ↓  rag/services/retrieval_service.py::RetrievalService.retrieve
      dense (FAISS) / sparse (BM25) results are *copies* of child_chunk dicts —
      every field (id, parent_id, source_id, text, metadata) survives fusion + rerank
    ↓  rag/services/prompt_context_service.py::expand_and_format_context   <-- BUG WAS HERE
      rebuilds a NEW dict keeping only {id, parent_id, text, child_text, metadata, score,
      rerank_score} — "source_id" was silently dropped, even though it was already
      present on every incoming item
    ↓  evaluation/evaluator.py::run_single_evaluation
      retrieved_chunk_ids = [chunk.get("id") for chunk in retrieved_contexts ...]  <-- BUG
      this "id" is the CHILD-chunk id (e.g. "rag_iron_absorption_heme_001_P0_C0")
    ↓  evaluation/metrics/retrieval_metrics.py
      calculate_recall_at_k_details / calculate_ap_at_k_details / calculate_mrr_at_k_details
      compare retrieved_chunk_ids against gold_relevant_chunk_ids by exact string membership
    ↓  docs/evaluation/phase2c_gold_annotations.json
      relevant_chunk_ids are authored as the bare rag_data.json "id" (source_id) —
      e.g. "rag_iron_absorption_heme_001", "RAG_MACRO_1" — NEVER child-chunk form
```

**The exact transformation**: `source_id` (e.g. `RAG_INF_1`) → `parent_id = source_id + "_P0"` → `child_id = parent_id + "_C0"` (or `_C1`, `_C2`, ... if the parent text is long enough to split further). `source_id` is computed once in `rag/chunker.py` and is present on every intermediate dict, but was discarded at the single point (`prompt_context_service.py`) where the retriever's output is finalized for external callers.

---

## 2. The actual bug — confirmed with concrete evidence from several different records

| Question | A. `rag_data.json` id | B. `metadata.pkl` child id | C. `retriever.retrieve()` output `"id"` | D. What retrieval_metrics compared against | E. Phase 2C gold `relevant_chunk_ids` format |
|---|---|---|---|---|---|
| "How often should I offer complementary foods to my 6-month-old?" | `RAG_INF_1` | `RAG_INF_1_P0_C0` | `RAG_INF_1_P0_C0` | (D) is fed exactly what (C) returns | `RAG_INF_1` |
| "What foods can help my child who has iron deficiency anemia?" | `rag_iron_absorption_heme_001` | `rag_iron_absorption_heme_001_P0_C0`, `..._P0_C1` (2 children) | `rag_iron_absorption_heme_001_P0_C0` (or `_C1`, depending on which ranks higher) | same | `rag_iron_absorption_heme_001` |
| "How do I avoid cross-contamination..." | `fssai_hygiene_food_handling_001` | `fssai_hygiene_food_handling_001_P0_C0` | `fssai_hygiene_food_handling_001_P0_C0` | same | `fssai_hygiene_food_handling_001` |

**B and C never equal E**, for any record, by construction — a bare source id is never itself a valid child-chunk id (the child id is always strictly longer, with a `_P{n}_C{n}` suffix appended). This is not a rare edge case; it is unconditional for every record in the corpus.

**D (`calculate_recall_at_k_details` / `calculate_ap_at_k_details` / `calculate_mrr_at_k_details`)**: all three do exact string-set/list membership comparisons between whatever list `evaluator.py` hands them as `retrieved_chunk_ids` and whatever list the dataset stores as `relevant_chunk_ids` — no normalization is or was performed inside these functions.

---

## 3. Dataset-wide scope (programmatically verified, not assumed)

```
Total unique gold relevant_chunk_ids across all 49 cases:  86
Exact match against a real CHILD chunk id:                  0   /  86
Exact match against a real PARENT chunk id:                 0   /  86
Exact match against a real rag_data.json SOURCE id:         86  /  86
Gold source IDs producing exactly 1 child chunk:            72
Gold source IDs producing MULTIPLE child chunks:             14
Gold source IDs producing 0 children (orphaned/bug):          0
Cases with RAG gold (relevant_chunk_ids != null):            38  / 49
Cases with null RAG gold (structured-DB-only, unaffected):   11  / 49
```

**Conclusion: this was 100% dataset-wide** across every one of the 38 RAG-gold-bearing cases, not an iron-record-specific issue — confirmed, not assumed, by checking all 86 unique gold IDs against the live index.

The 14 multi-child source records (`rag_iron_absorption_heme_001`, `rag_iron_bioavailability_logic_001`, `rag_sat_mix_therapeutic_recipe_001`, `rag_dietary_fibre_benefits_001`, `rag_food_allergy_cross_reactivity_001`, `rag_smart_nutrients_brain_001`, `icmr_2020_protein_001`, `rag_trace_elements_002`, `rag_vitamin_a_indicators_001`, `fssai_contamination_micro_001`, `icmr_2020_v2_energy_004`, `fssai_tiffin_safety_001`, `rag_soluble_vs_insoluble_fiber_001`, `fssai_handler_safety_001`) are exactly the kind of case Option A (rewriting gold to child-chunk IDs) would have made fragile — see §4.

---

## 4. Design options evaluated

**Option A — rewrite all 38 cases' gold IDs to child-chunk form.**
- Correctness: would work today, but couples gold data to `rag/chunker.py`'s current `parent_size=600`/`child_size=150`/`child_overlap=30` config and to each record's exact current text length. **Directly demonstrated this session**: editing the two iron records' text (the approved 15–35% correction) changed their child-chunk boundaries and IDs (`_P0_C0`/`_C1`/`_C2` shifted) as an incidental side effect of an unrelated wording fix. Any future KB text edit could silently re-fragment a record and invalidate previously-correct gold IDs with no error or warning.
- Risk: highest — touches all 38 gold cases, and creates an ongoing maintenance hazard for every future KB edit.
- Rejected.

**Option C — change the retriever/indexer to return canonical parent/source IDs as `"id"` itself.**
- Would require redefining what `"id"` means for every consumer of `retriever.retrieve()` output (evaluator.py's CSV/report columns, live-app logging, the semantic cache's stored payloads, `retriever.metadata` used by other services) — a broad, production-facing behavior change far outside "the minimum necessary fix," and touches code whose primary job is serving the live application, not evaluation.
- Rejected as disproportionate to the problem.

**Option B — add a deterministic canonical-ID passthrough, used only by the evaluation layer. CHOSEN.**
- `source_id` was already computed by `rag/chunker.py` for exactly this purpose (its own docstring: "Preserves: original document ID & source ID") and was present on every intermediate dict already — it was simply dropped one step before being returned. Restoring it is additive (a new dict key), not a redefinition of any existing field's meaning.
- Zero gold-dataset changes needed: all 38 cases' existing `relevant_chunk_ids` are already in bare source-id form, so canonicalizing the *retrieved* side to match them fixes all 38 cases simultaneously with no dataset edits.
- Zero `retrieval_metrics.py` changes needed: `calculate_recall_at_k_details`/`calculate_ap_at_k_details`/`calculate_mrr_at_k_details` already deduplicate repeated IDs via `set()`/seen-id tracking (pre-existing, tested behavior — see `test_recall_at_k.py::test_duplicate_retrieved_ids_do_not_inflate_numerator`), which transparently handles the case where two child chunks of the same multi-child source both land in the retrieved top-5 (verified with a new test, §6).
- Zero effect on Precision@5 — confirmed by inspection and by a new test asserting `calculate_precision_at_k_details`'s signature takes no chunk-ID arguments at all; it is scored purely from the LLM `ContextJudge`'s positional relevance judgments.
- Single centralized fix point (`evaluator.py`'s one `retrieved_chunk_ids` construction) feeds all three ID-based metrics identically — no per-metric duplication of the mapping logic.

**Canonical evaluation unit: the `rag_data.json` record's own `"id"` field (source_id).** This is what gold data already uses, what the chunker already computes and labels `source_id`, and what is now what `evaluator.py` compares against retrieval output.

---

## 5. The fix (minimum necessary change, two files)

**`rag/services/prompt_context_service.py`** — one line added to `expand_and_format_context`'s output dict:
```python
formatted_item = {
    "id": item.get("id"),
    "parent_id": parent_id,
    "source_id": item.get("source_id"),   # <-- added: passthrough of data already computed
    "text": text_content,
    ...
}
```

**`evaluation/evaluator.py`** — the `retrieved_chunk_ids` construction now prefers `source_id`:
```python
retrieved_chunk_ids = [
    (chunk.get("source_id") or chunk.get("id"))
    for chunk in retrieved_contexts
    if chunk.get("source_id") or chunk.get("id")
]
```
The `or chunk.get("id")` fallback preserves behavior for any legacy/mocked retriever result that doesn't supply `source_id` (defensive, not required by any current production path).

**Nothing else changed.** `retrieval_metrics.py` formulas, `Precision@5` methodology, `docs/evaluation/phase2c_gold_annotations.json` (all 49 cases, all gold facts, all reference answers, `safety_ground_truth`, and the 15–35% iron-bioavailability text), the planner, judges, notebook, and FAISS index/metadata are all byte-for-byte unchanged by this task (confirmed via `git status` — only `evaluation/evaluator.py` and `rag/services/prompt_context_service.py` were newly modified this session).

---

## 6. Real examples across all six categories (before/after, live retrieval)

Run directly this session via `KidsNutriRetriever().retrieve(question, top_k=5)`:

| Category | Question | Gold ID(s) | OLD retrieved ids (child form) | OLD match | NEW retrieved ids (source_id form) | NEW match |
|---|---|---|---|---|---|---|
| General Nutrition | "How much of my child's daily food should come from carbohydrates, protein, and fat?" | `RAG_MACRO_1/2/3` | `RAG_INF_FULL_16_P0_C0`, `icmr_2020_protein_infants_001_P0_C0`, `icmr_2020_protein_children_001_P0_C0`, `condition_pregnancy_001_P0_C0`, `condition_lactation_001_P0_C0` | none | `RAG_INF_FULL_16`, `icmr_2020_protein_infants_001`, `icmr_2020_protein_children_001`, `condition_pregnancy_001`, `condition_lactation_001` | none (a genuine retrieval-quality miss, not an ID-format bug — the right chunks simply weren't ranked in top-5 for this query) |
| Age-Specific Feeding | "How often should I offer complementary foods to my 6-month-old?" | `RAG_INF_1` **(one parent → one child)** | `RAG_INF_1_P0_C0`, `RAG_INF_2_P0_C0`, `RAG3003_P0_C0`, `RAG3002_P0_C0`, `goal_complementary_001_P0_C0` | none | `RAG_INF_1`, `RAG_INF_2`, `RAG3003`, `RAG3002`, `goal_complementary_001` | **`RAG_INF_1`** ✓ |
| Allergies | "What foods should I avoid if my child has a milk allergy?" | `rag_food_allergy_cross_reactivity_001` | `RAG_RULE_2_P0_C0`, `RAG3008_P0_C0`, `RAG_INF_4_P0_C0`, `RAG2005_P0_C0`, `RAG_PREG_10_P0_C0` | none | (same, canonicalized) | none (genuine retrieval-quality miss) |
| Pediatric Conditions | "What foods can help my child who has iron deficiency anemia?" | 13 ids incl. `rag_iron_absorption_heme_001`/`rag_iron_bioavailability_logic_001` **(one parent → multiple children)** | `RAG_IRON_6_P0_C0`, `RAG_IRON_3_P0_C0`, `RAG_IRON_7_P0_C0`, `RAG_DO_1_P0_C0`, `rag_iron_002_P0_C0` | none | `RAG_IRON_6`, `RAG_IRON_3`, `RAG_IRON_7`, `RAG_DO_1`, `rag_iron_002` | **`RAG_IRON_6`, `RAG_IRON_3`, `RAG_IRON_7`, `RAG_DO_1`** ✓ (4 of 5) |
| Food Safety | "How do I avoid cross-contamination between raw and cooked food..." | `fssai_hygiene_food_handling_001`, `fssai_contamination_micro_001` | `fssai_hygiene_food_handling_001_P0_C0`, `RAG2005_P0_C0`, `RAG_RULE_2_P0_C0`, `RAG_INF_4_P0_C0`, `RAG_INF_13_P0_C0` | none | `fssai_hygiene_food_handling_001`, `RAG2005`, `RAG_RULE_2`, `RAG_INF_4`, `RAG_INF_13` | **`fssai_hygiene_food_handling_001`** ✓ |
| Growth/Reference | "How many calories should my child eat each day at ages 1-3, 4-6, and 7-9 years?" | `icmr_2020_energy_children_001`, `icmr_2020_v2_energy_table_004`, `icmr_2020_v2_energy_004` | `RAG_INF_5_P0_C0`, `RAG_INF_FULL_16_P0_C0`, `icmr_2020_energy_infants_001_P0_C0`, `RAG_INF_2_P0_C0`, `icmr_2020_energy_children_001_P0_C0` | none | `RAG_INF_5`, `RAG_INF_FULL_16`, `icmr_2020_energy_infants_001`, `RAG_INF_2`, `icmr_2020_energy_children_001` | **`icmr_2020_energy_children_001`** ✓ |

**Before the fix: 0 of 6 example cases had any gold match at all — the ID format made a true positive structurally impossible.** After the fix: 4 of 6 now register real, honest matches; the remaining 2 correctly still show no match, because in those two cases the retriever genuinely didn't rank the gold-relevant chunk in its top 5 — this is real retrieval-quality signal, exactly what Recall@5/MAP@5/MRR@5 are supposed to measure, now that the comparison itself is no longer broken.

---

## 7. Regression tests added

New file `test_rag_chunk_id_alignment.py`, 11 tests, three groups:

1. **`TestPromptContextServiceSourceIdPassthrough`** (3 tests) — one-parent/one-child passthrough, one-parent/multiple-children passthrough (both children correctly resolve to the same `source_id`), and a defensive no-crash-on-missing-`source_id` case.
2. **`TestEvaluatorChunkIdCanonicalization`** (3 tests) — prefers `source_id` over `id`; falls back to `id` when `source_id` is absent (backward compatibility); multiple children of the same source collapse to a repeated `source_id` in the list (dedup is left to `retrieval_metrics.py`, verified separately).
3. **`TestRetrievalMetricsWithCanonicalIds`** (5 tests) — one-parent/one-child relevant at rank 1 (Recall/MRR/MAP all score 1.0); relevant chunk found at a later rank (MRR = 1/4 at rank 4); no relevant chunk retrieved (real zero, not a missing/invalid status); one-parent/multiple-children both retrieved without double-counting (2 distinct gold hits stay 2, not 3); and a documentation-style test confirming `calculate_precision_at_k_details`'s signature takes no chunk-ID arguments at all, proving Precision@5 has zero surface area for this fix.

```
python -m unittest test_rag_chunk_id_alignment -v   → 11 tests, OK
python -m unittest discover -v                       → 80 tests (69 pre-existing + 11 new), OK
python -m compileall -q .                            → clean, no syntax/import errors
```

---

## 8. Final validation

- Every gold `relevant_chunk_id` across all 49 cases can now be matched against the canonical identifier (`source_id`) emitted by retrieval — confirmed programmatically (86/86 unique gold IDs match a real source id; 0/86 ever matched a child or parent id, before or after — the fix doesn't change what IDs *exist*, it changes what evaluator.py *compares*).
- No gold ID is silently unmatched due to format mismatch anymore — any remaining non-match is a genuine retrieval-ranking miss (see the two examples in §6).
- No false relevance is created by parent→child expansion — canonicalization only ever *collapses* multiple child IDs down to one shared source_id; it never invents a new ID or expands one ID into several. The existing `set()`/seen-id dedup logic in `retrieval_metrics.py` (unchanged) prevents any double-counting when a multi-child source is retrieved more than once (verified with a dedicated test, §7).
- All 49 evaluation cases remain valid and untouched: same 49 IDs, same question text, same `category`/`subcategory`/`age_group`/`knowledge_area`/`source_scope`/`profile`, same `gold_facts`, same `reference_answer`, same `safety_ground_truth` (`null` throughout), same `annotation_status` (`ANNOTATED` on all 49, unchanged by this task).
- `Recall@5`/`MAP@5`/`MRR@5`/`Precision@5` formulas are byte-for-byte unchanged in `evaluation/metrics/retrieval_metrics.py`.
- The question set is unchanged (no question text touched).
- `safety_ground_truth` is unchanged (`null` on all 49, not touched by this task).
- The 15–35% iron-bioavailability KB correction from the prior task is unchanged — confirmed both records still read "approximately 15-35%... varying with iron status" and `data/rag/rag_data.json`/`faiss.index`/`metadata.pkl`/`dataset_hash.txt` show no diff from this task (only `evaluator.py` and `prompt_context_service.py` are new modifications this session).
- FAISS metadata and the retriever now agree on the canonical evaluation ID: both ultimately trace back to the same `source_id` value stored on every child chunk in `metadata.pkl` since the index was first built — no re-indexing was required for this fix (only the two files above changed; no data changed).

### Summary table

| Item | Before | After |
|---|---|---|
| Gold ID format (`phase2c_gold_annotations.json`) | Source-record id (e.g. `RAG_INF_1`) | **Unchanged** — source-record id (e.g. `RAG_INF_1`) |
| Retriever ID format (`retriever.retrieve()["id"]`) | Child-chunk id (e.g. `RAG_INF_1_P0_C0`) | **Unchanged** — still child-chunk id (kept for any other consumer that wants sub-record granularity) |
| Canonical evaluation ID (what `evaluator.py` now compares) | Child-chunk id (`chunk.get("id")`) — never matched gold | **Source-record id** (`chunk.get("source_id") or chunk.get("id")`) — matches gold by construction |
| Gold IDs unmatched against canonical retrieval ID (structural ceiling, 86 total gold IDs) | 86 / 86 (100%) — every case structurally incapable of a true positive | 0 / 86 structurally unmatched — any remaining non-match is a genuine retrieval-ranking result, not a format bug |
| Cases affected | 38 / 49 (all RAG-gold-bearing cases); 11 structured-DB-only cases were never affected either way | Same 38 cases now scoreable; same 11 unaffected (as expected — they have no RAG gold to match) |

**No unrelated cleanup, planner, judge, safety, notebook, metric-formula, or question changes were made.** Stopping here per the task's scope control.
