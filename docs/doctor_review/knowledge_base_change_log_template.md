# Knowledge Base Change Log — Doctor Review Template

**Purpose**: every new record or modification proposed for `data/rag/rag_data.json` or any file in `data/structured_db/` during the Phase 1+ knowledge base expansion must have a row here **before** it is merged. This is a tracking artifact, not a change itself — creating a row does not approve a change; only a filled-in "Approved" status with a reviewing doctor's sign-off does.

Copy the table below into a new dated file per expansion batch (e.g. `2026-09-01_allergy_consolidation.md`) rather than growing one infinite table, so each batch is reviewable as a discrete unit. Keep this file itself as the blank template only.

## Column Definitions

| Column | Meaning |
|---|---|
| **Change ID** | Unique, stable identifier for this proposed change, e.g. `CHG-0001`. Referenced in commit messages/PRs once implemented. |
| **Source File** | Exact repo-relative path, e.g. `data/structured_db/allergies.json`. |
| **Record ID / Item Name** | The `food_id`/`condition_name`/`goal_name`/`allergy`/RAG `id` affected. For a NEW RECORD, the *proposed* identifier. |
| **Change Type** | `NEW RECORD` or `UPDATE EXISTING RECORD` — no other values. |
| **Existing Value** | For updates: the exact current field value(s), verbatim. Blank/N/A for new records. |
| **Proposed New Value/Content** | The exact proposed value(s) or full new record content. |
| **Reason for Change** | Why this change is needed — reference the specific audit finding it addresses where applicable (e.g. "fills blank severity, see docs/phase1_knowledge_base_audit.md §3 allergies.json"). |
| **Knowledge Category** | One of: `foods` / `conditions` / `allergies` / `goals` / `rag_narrative` / `other` (specify). |
| **Source/Reference** | The authoritative source consulted (e.g. "ICMR-NIN Indian Food Composition Tables 2017", "AAP Clinical Report — Allergy X"). Never "AI-generated" or "estimated" alone. |
| **Exact Source Location** | Page/section/table number, or URL + access date for a web source. Must be specific enough for the doctor to independently verify without re-deriving it. |
| **Doctor Review Status** | `Not Reviewed` / `Under Review` / `Reviewed`. |
| **Doctor Comments** | Free text — clinical caveats, corrections, requested edits. |
| **Approved / Rejected** | `Approved` / `Rejected` / `Approved with Edits` (if edited, note what changed from the Proposed value). Blank until a decision is made. |
| **Date Reviewed** | ISO date (YYYY-MM-DD) of the doctor's review. |

## Table Template

| Change ID | Source File | Record ID / Item Name | Change Type | Existing Value | Proposed New Value/Content | Reason for Change | Knowledge Category | Source/Reference | Exact Source Location | Doctor Review Status | Doctor Comments | Approved / Rejected | Date Reviewed |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CHG-0001 | | | | | | | | | | Not Reviewed | | | |

## Worked Examples (illustrative format only — not real proposed changes)

**NEW RECORD**
| Change ID | Source File | Record ID / Item Name | Change Type | Existing Value | Proposed New Value/Content | Reason for Change | Knowledge Category | Source/Reference | Exact Source Location | Doctor Review Status | Doctor Comments | Approved / Rejected | Date Reviewed |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CHG-0042 | `data/rag/rag_data.json` | `RAG_SUBST_1` (proposed) | NEW RECORD | N/A | `{"id":"RAG_SUBST_1","text":"<proposed sentence>","metadata":{"type":"food_substitution","tags":["egg_protein","substitution"],"source":"<TBD>"}}` | Fills the food-substitution gap identified in docs/phase1_knowledge_base_audit.md §6 | rag_narrative | (fill in) | (fill in) | Not Reviewed | | | |

**UPDATE EXISTING RECORD**
| Change ID | Source File | Record ID / Item Name | Change Type | Existing Value | Proposed New Value/Content | Reason for Change | Knowledge Category | Source/Reference | Exact Source Location | Doctor Review Status | Doctor Comments | Approved / Rejected | Date Reviewed |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CHG-0043 | `data/structured_db/foods.json` | `F200` (vegetables) — `protein_g` field | UPDATE EXISTING RECORD | `""` (blank) | `1.8` | Fills blank core nutrition field, see docs/phase1_knowledge_base_audit.md §3/§7 Option 1 | foods | (fill in) | (fill in) | Not Reviewed | | | |

## Process Notes

1. One row per **field-level** change where practical (e.g. don't bundle 5 unrelated field updates to the same record into one row) — this keeps doctor review granular and makes partial approval ("Approved with Edits") meaningful.
2. `Change Type` must exactly match `NEW RECORD` or `UPDATE EXISTING RECORD` — no free text, so batches can be filtered/counted programmatically later if needed.
3. No row moves from `Not Reviewed` to `Approved`/`Rejected` without an actual doctor's comments and a reviewed date — a blank `Doctor Comments` field with a filled `Approved` status should be treated as suspicious, not processed.
4. Only `Approved` (or `Approved with Edits`, using the edited value) rows may be merged into the actual data files. `Rejected` rows stay in the log as a permanent record of what was considered and declined, and why.
5. This template itself must never be edited to remove past batches — copy it forward per batch as instructed above, don't overwrite history.
