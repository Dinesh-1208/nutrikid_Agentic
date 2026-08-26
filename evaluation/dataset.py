# Official Evaluation Dataset Loader for KidsNutriBite.
#
# THE OFFICIAL EVALUATION DATASET is the finalized, gold-annotated 49-case
# set produced by this project's Phase 2A-2D evaluation-methodology work:
#
#     docs/evaluation/phase2c_gold_annotations.json
#
# This module loads that file once at import time and exposes it as
# EVALUATION_DATA, preserving the historical import contract
# (`from evaluation.dataset import EVALUATION_DATA`) already used by
# evaluation/comparator.py and by existing tests, so no call site elsewhere
# needs to change.
#
# Each case dict is loaded verbatim from the JSON (nothing invented, renamed,
# or regenerated here) and includes: id, question, category, subcategory,
# age_group, knowledge_area, source_scope, profile, relevant_chunk_ids,
# gold_facts, reference_answer, safety_ground_truth, annotation_status,
# annotation_notes.
#
# safety_ground_truth is null on every case until doctor review (Phase 2D)
# completes - this loader does not fabricate it, and nothing here infers a
# value from any other field.
#
# The prior hardcoded 100-question dataset (pre-Phase-2 schema: no gold
# relevant_chunk_ids/gold_facts) is preserved, unmodified, in
# evaluation/legacy_dataset.py as LEGACY_EVALUATION_DATA, for reference. It
# is no longer the active dataset for evaluation/comparator.py or any other
# real evaluation entry point.

import json
import os

_DATASET_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "docs", "evaluation", "phase2c_gold_annotations.json",
)


def _load_evaluation_data(path=_DATASET_PATH):
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return payload["cases"]


EVALUATION_DATA = _load_evaluation_data()
