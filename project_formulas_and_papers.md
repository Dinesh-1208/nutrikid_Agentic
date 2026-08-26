# KidsNutriBite: Project Formulas and Scientific Origins

This document records which formulas are implemented in the KidsNutriBite evaluation code, which formulas are backed by papers or standard evaluation math, and where the exact formulas were verified.

## Verification Scope

- Local reports checked: `reports/`, `research_notes.md`, `llm_judge_analysis.md`, and `project_formulas_and_papers.md`.
- Local code checked: `evaluation/evaluator.py`, `evaluation/comparator.py`, and `evaluation/metrics/`.
- PDFs checked locally in `_paper_check/` from the cited arXiv sources.
- Important distinction: some formulas are used in code, some are only discussed in papers, and some are standard IR/classification formulas rather than formulas newly introduced by the cited papers.

## 1. Core LLM-as-a-Judge Metrics Implemented in Code

These metrics use Layer 1 LLM judges to extract structured judgments, then Layer 2 Python functions compute deterministic scores.

| Metric | Formula Used in Project | Implemented in Code? | Used in Live Evaluation? | Backing Source | Exact Formula Printed? | Verified Page / Location |
| :--- | :--- | :---: | :---: | :--- | :---: | :--- |
| Faithfulness | `supported_claims / total_claims` | Yes | Yes | RAGAS, Es et al. (2023), arXiv:2309.15217 | Yes | PDF page 3, Section 3 |
| Answer Relevancy | `(1 / n) * sum(sim(original_question, generated_question_i))` | Yes | Yes | RAGAS, Es et al. (2023), arXiv:2309.15217 | Yes | PDF page 3, Section 3 |
| Context Recall | `supported_expected_facts / total_expected_facts` | Yes | Yes | RAGAS documentation (docs.ragas.io) — NOT defined in Es et al. (2023) arXiv:2309.15217, which is reference-free by design and defines a different metric, Context Relevance | Yes in RAGAS documentation | RAGAS Context Recall docs (docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_recall/) |
| Unsupported Claim Rate | `unsupported_claims / total_claims` | Yes | Yes | Project operational metric; ratio structure informed by the supported-claim precision pattern in FActScore (Min et al., 2023, EMNLP, arXiv:2305.14251) and SAFE (Wei et al., 2024, NeurIPS, arXiv:2403.18802) — neither paper names a metric "Unsupported Claim Rate" or "Hallucination Rate"; SAFE explicitly distinguishes its factuality metric from "hallucination". This is the sole claim-level aggregate; see "Response-Level Hallucination Metrics" below for the separate response-level metrics. | Project operational formula (complement pattern verified against FActScore Sec 3.1 p.3, SAFE Sec 5 p.6 Eq.1) | See `docs/overall_hallucination_literature_audit.md` |
| Hallucination Rate / Intrinsic Response Rate / Extrinsic Response Rate | response-level containment rates — see dedicated section below | Yes | Yes | Maynez et al. (2020, ACL, arXiv:2005.00661, Table 2/Sec 5.2 p.6) — direct methodology match; Ji et al. (2022/2023, arXiv:2202.03629, Sec 2.1 p.4, Sec 6.1 p.15) — taxonomy + explicit statement that separate claim-level I/E quantification is uncommon | Formula matches Maynez's reported methodology; not a claim-level formula | See "Response-Level Hallucination Metrics" below and `docs/intrinsic_extrinsic_hallucination_literature_audit.md` |
| Cosine Similarity | `(A dot B) / (norm(A) * norm(B))` | Yes | Yes, inside Answer Relevancy | Standard vector similarity; used by RAGAS answer relevancy | Yes as part of RAGAS answer relevancy | PDF page 3, Section 3 |

### Response-Level Hallucination Metrics

Unit of analysis: one evaluated response (question-answer pair), not one claim. All three metrics below are computed in `evaluation/comparator.py` from the per-claim `is_supported`/`hallucination_type` data already produced for Faithfulness/Unsupported Claim Rate, via `evaluation/metrics/grounding_metrics.py::calculate_response_hallucination_type_details` for the intrinsic/extrinsic flags.

**Response-Level Hallucination Rate**
Formula: `responses with >=1 unsupported claim / total valid responses`
Research: Maynez et al. (2020), ACL 2020, arXiv:2005.00661, Table 2, Section 5.2, page 6 — matches the paper's `I∪E` (union) column: *"the percentage of summaries where at least one word was annotated... as an intrinsic (I) or extrinsic (E) hallucination."*

**Intrinsic Response Rate**
Formula: `responses with >=1 intrinsic hallucination / total valid responses`
Research: Maynez et al. (2020) — matches the paper's separately-reported `I` column.

**Extrinsic Response Rate**
Formula: `responses with >=1 extrinsic hallucination / total valid responses`
Research: Maynez et al. (2020) — matches the paper's separately-reported `E` column.

**Adaptation note**: KidsNutriBite adapts the Maynez response-level methodology by using LLM-judged atomic claims rather than human-annotated text spans (Maynez's spans required unanimous agreement across three human annotators; KidsNutriBite's claims are classified by a single LLM pass with no consensus mechanism). Resulting percentages are not directly comparable to Maynez's published figures.

**Independence, not partition**: Intrinsic Response Rate and Extrinsic Response Rate are computed independently — a response containing both an intrinsic and an extrinsic unsupported claim counts in *both* rates, matching Maynez's own table structure and Ji et al.'s explicit observation (arXiv:2202.03629, Section 6.1, page 15) that *"it is common for a single generation to have both types"* of hallucination. Consequently `Hallucination Rate <= Intrinsic Response Rate + Extrinsic Response Rate` — it is the union of the two, not their sum, and no code enforces `Intrinsic + Extrinsic = Hallucination Rate`.

**"Total valid responses" excludes unknowns**: a response whose grounding evaluation failed, extracted no claims, had malformed `is_supported` data, or (for the two type-specific rates only) had a malformed/missing `hallucination_type` on an unsupported claim, is excluded from both the numerator and denominator of the relevant rate — never silently counted as "not hallucinated."

**Taxonomy source**: the Intrinsic/Extrinsic category *definitions* themselves remain Ji et al.'s (2022/2023, arXiv:2202.03629, Section 2.1, page 4). Per-claim `hallucination_type` labels continue to be shown as diagnostics (claim text, `is_supported`, `hallucination_type`) in `reports/hallucination_analysis.md`, independent of whether they also feed a response-level rate.

## 2. Standard IR and Classification Metrics Implemented in Code

These are standard Information Retrieval or Machine Learning formulas. The project papers may mention these metrics conceptually, but they do not always print the formula.

| Metric | Formula Used in Project | Implemented in Code? | Used in Live Evaluation? | Backing Source | Exact Formula Printed in Project-Cited Paper? | Verified Page / Location |
| :--- | :--- | :---: | :---: | :--- | :---: | :--- |
| Precision@K | `relevant_hits_in_top_k / k` | Yes | Yes, as Precision@5 / Context Precision | Standard IR metric; arXiv:2504.19754 and arXiv:2606.00881 mention related retrieval metrics | No | arXiv:2504.19754 page 9 mentions NDCG/MAP/F1 conceptually; arXiv:2606.00881 pages 5-6 report Accuracy@5/Recall@10 |
| Recall@K | `relevant_hits_in_top_k / total_relevant` | Yes | Helper exists; not directly used as Recall@10 in the main live pipeline | Standard IR metric; arXiv:2606.00881 reports Recall@10 | No | arXiv:2606.00881 page 6 reports Recall@10 table |
| MRR@K | `1 / rank_of_first_relevant_result` | Yes | Yes, as MRR@5 | Standard IR metric | No direct paper citation | N/A |
| AP@K | Average of Precision@rank for each relevant hit in top K | Yes | Yes, as AP@5 | Standard IR metric; MAP is discussed in arXiv:2504.19754 | No | arXiv:2504.19754 page 9 mentions MAP conceptually |
| MAP@K | Mean of AP@K over queries | Yes | Partly. Helper exists; `comparator.py` manually averages AP@K for MAP@K | Standard IR metric; MAP is discussed in arXiv:2504.19754 | No | arXiv:2504.19754 page 9 mentions MAP conceptually |
| Safety Accuracy — **REMOVED** (2026-08-25) | `(TP + TN) / (TP + FP + TN + FN)` | Generic math still exists in `safety_metrics.py::calculate_classification_metrics` | **No** — removed from the official safety metric set/reporting | Not used in any of Llama 2, XSTest, Llama Guard, MedSafetyBench, or NOHARM (all verified directly) — also structurally misleading under class imbalance for a safety task | No | See `docs/safety_evaluation_literature_audit.md` |
| Safety F2 — **REMOVED** (2026-08-25) | `5PR / (4P + R)` | Generic math still exists in `safety_metrics.py::calculate_classification_metrics` | **No** — removed from the official safety metric set/reporting | F-beta (β=2) is general classification theory (van Rijsbergen, 1979, not independently verified), but zero of the five verified safety-specific sources use it — project-specific choice, not literature-backed for this domain | No | See `docs/safety_evaluation_literature_audit.md` |
| Safety Recall — **RETAINED (primary/headline)** | `TP / (TP + FN)` | Yes | **Not currently reportable — no valid safety ground truth exists yet** (see below) | Llama Guard (arXiv:2312.06674, Sec 4.3.3 p.7) uses Recall as a fallback classifier-evaluation metric; conceptually the core concern of every verified safety source | No | `docs/safety_evaluation_literature_audit.md` |
| Safety Precision — **RETAINED (companion)** | `TP / (TP + FP)` | Yes | **Not currently reportable — no valid safety ground truth exists yet** | Llama Guard (Sec 4.3.3), fallback classifier-evaluation metric | No | `docs/safety_evaluation_literature_audit.md` |
| Safety F1 — **RETAINED (summary)** | `2PR / (P + R)` | Yes | **Not currently reportable — no valid safety ground truth exists yet** | Llama Guard (Sec 4.3.3), fallback classifier-evaluation metric | No | `docs/safety_evaluation_literature_audit.md` |
| Refusal Rate (on known-safe prompts) — **ADDED, not yet implemented** | `refusals / known_safe_prompts` | No — deferred pending ground truth for known-safe prompts | No | XSTest (arXiv:2308.01263, Sec 4.2, pp.4-5) — the direct precedent; preserves `SafetyJudge`'s existing three-way `Refusal`/`Compliant`/`Violation` output rather than collapsing Refusal into Compliant | Yes | `docs/safety_evaluation_literature_audit.md` |
| AUPRC — **DEFERRED** | Area under precision-recall curve | No | No | Llama Guard's actual *primary* metric (Sec 4.3.3); requires `SafetyJudge` to output a calibrated confidence score, not just categorical booleans — an architecture change, not adopted yet | N/A | `docs/safety_evaluation_literature_audit.md` |

### Safety Ground-Truth Fix (2026-08-25)

`evaluation/comparator.py::compute_safety_metrics` no longer fabricates ground truth. The old logic set `ground_truth["overall"] = "Violation" if test_case["is_safety"] else "Compliant"` and hardcoded all four rubric ground-truth labels (`diagnosis`, `prescription`, `allergy_violation`, `age_violation`) to `False` for every case — confirmed broken (Q_COND_01, an `is_safety=True` breastfeeding question whose own `reference_answer` is compliant, was being scored as if a violation was the correct outcome). It now requires a real `test_case["safety_ground_truth"]` field, which does not exist in the dataset yet; every case is therefore currently `MISSING_GROUND_TRUTH` (`recall`/`precision`/`f1` = `None`), reported honestly rather than fabricated. `is_safety` is preserved exactly as before, but strictly as a topic/safety-relevance flag — never as an outcome label.

- **Llama Guard** (arXiv:2312.06674) is the direct precedent for evaluating `SafetyJudge` as a classifier via Precision/Recall/F1 against labeled ground truth — the closest structural analog, since it's the only one of the five verified sources with a separate judge/classifier being scored (the other four have humans directly rate the underlying model, with no intermediate classifier).
- **XSTest** (arXiv:2308.01263) is the precedent for the deferred Refusal Rate metric, and for preserving `SafetyJudge`'s three-way `Refusal`/`Compliant`/`Violation` output — collapsing `Refusal` into `Compliant` (as the old binarization did) makes over-refusal invisible, exactly the failure mode XSTest exists to catch.
- **Llama 2** (arXiv:2307.09288) and **NOHARM** (arXiv:2512.01241) are the evidence that credible safety ground truth is built from human/expert judgment of actual response *content* (3-annotator majority vote with Gwet's AC1/2 for Llama 2; blinded multi-physician severity rating with unanimity-gated concordance for NOHARM) — never from a topic/category proxy like `is_safety`.

## 3. Paper Formulas Verified but Not Implemented in Code

These formulas exist in the cited papers and are documented in `research_notes.md`, but they are not used by the current Python evaluation pipeline.

| Formula / Metric | Implemented in Code? | Paper | Exact Formula Printed? | Verified Page / Location |
| :--- | :---: | :--- | :---: | :--- |
| ROUGE-L Precision, Recall, and F1 | No | arXiv:2411.00300, Rationale-Guided Retrieval Augmented Generation for Medical Question Answering | Yes | PDF page 14, Appendix A.4.1 |
| BERTScore Precision, Recall, and F1 | No | arXiv:2411.00300, Rationale-Guided Retrieval Augmented Generation for Medical Question Answering | Yes | PDF page 14, Appendix A.4.1 |
| Delta PPL / Perplexity filtering equations | No | arXiv:2411.00300, Rationale-Guided Retrieval Augmented Generation for Medical Question Answering | Yes | PDF page 4, Section 3.2 |
| Volume Score | No | arXiv:2603.03301, From Exact Hits to Close Enough: Semantic Caching for LLM Embeddings | Yes | PDF page 5, Section 3.3.2 |
| Next Cover | No | arXiv:2603.03301, From Exact Hits to Close Enough: Semantic Caching for LLM Embeddings | Yes | PDF page 5, Section 3.3.3 |
| SphereLFU formulas | No | arXiv:2603.03301, From Exact Hits to Close Enough: Semantic Caching for LLM Embeddings | Yes | PDF page 16, Appendix B.2.1 |
| DistanceLFU update | No | arXiv:2603.03301, From Exact Hits to Close Enough: Semantic Caching for LLM Embeddings | Yes | PDF page 17, Appendix B.2.5 |
| Linguistic Surprisal | No | arXiv:2603.03301, From Exact Hits to Close Enough: Semantic Caching for LLM Embeddings | Yes | PDF page 17, Appendix B.2.7 |

### Exact Paper Formulas Referenced Above

These formulas are verified in the cited PDFs but are not implemented in the current KidsNutriBite Python evaluation pipeline.

**ROUGE-L formulas** - arXiv:2411.00300, PDF page 14, Appendix A.4.1:

```text
ROUGE-L Precision(C, R) = LCS(C, R) / |C|
ROUGE-L Recall(C, R)    = LCS(C, R) / |R|
ROUGE-L F1(C, R)        = 2 * Precision * Recall / (Precision + Recall)
```

**BERTScore formulas** - arXiv:2411.00300, PDF page 14, Appendix A.4.1:

```text
BERTScore Precision(C, R) = (1 / |C|) * sum over c in C of max over r in R cosine_similarity(c, r)
BERTScore Recall(C, R)    = (1 / |R|) * sum over r in R of max over c in C cosine_similarity(r, c)
BERTScore F1(C, R)        = 2 * Precision * Recall / (Precision + Recall)
```

**Delta PPL / perplexity filtering formulas** - arXiv:2411.00300, PDF page 4, Section 3.2:

```text
Delta PPL = PPL(x) - PPL(x, d) > tau

PPL(x)    = exp(-(1 / N) * sum from i=1 to N log P(x_i | x_<i))
PPL(x, d) = exp(-(1 / N) * sum from i=1 to N log P(x_i | x_<i, d))
```

**Semantic caching formulas** - arXiv:2603.03301:

```text
Volume Score, PDF page 5:
Vol(v) = | { r in R_t: d(v, r) <= D_thresh } |

Next Cover, PDF page 5:
NextCover(r_i, t) = min { j > t : d(r_j, r_i) <= D_thresh }

SphereLFU kernel, responsibility, update, and decay, PDF page 16:
p(q | Z = i) proportional to exp(-kappa * d(q, e_i)^2)
r_i(q) = c_i * exp(-kappa * d(q, e_i)^2) / (sum over j in M(q) c_j * exp(-kappa * d(q, e_j)^2) + alpha)
c_i <- c_i + r_i(q)
c_i <- gamma * c_i

DistanceLFU update, PDF page 17:
c_i <- c_i + (1 - d(q, e_i) / D_thresh)

Linguistic Surprisal, PDF page 17:
S(s) = - sum over w in s log p(w)
```
## 4. Conceptual Paper Metrics Not Implemented as Project Formulas

| Metric / Concept | Implemented in Code? | Paper | Verification Result |
| :--- | :---: | :--- | :--- |
| NDCG | No | arXiv:2504.19754 | Mentioned and reported, but no formula printed; verified on PDF pages 9, 11, and 12 |
| Accuracy@5 | No | arXiv:2606.00881 | Reported as an experiment metric; no formula printed; verified on PDF pages 5 and 7 |
| Recall@10 | No, except generic Recall@K helper exists | arXiv:2606.00881 | Reported as an experiment metric; no formula printed; verified on PDF page 6 |
| LLM-as-a-judge Likert score | No | arXiv:2606.00881 | Method described with a five-point Likert scale; not implemented as a 1-5 score in this project; verified on PDF pages 5 and 7 |
| Scoping review evaluation metrics | No direct formulas | arXiv:2511.05901 | Mentions ROUGE, BERTScore, BLEU, METEOR, hallucination, bias, safety, etc. conceptually; no formulas printed; verified on PDF page 10 |

## Bottom Line

The implemented KidsNutriBite evaluation is scientifically defensible, but not every formula is printed in the recent RAG papers cited in the reports.

- RAGAS directly backs Faithfulness and Answer Relevancy formulas.
- RAGAS documentation backs the Context Recall formula used here. This is distinct from the arXiv:2309.15217 paper's own "Context Relevance" metric (a precision-style measure of the retrieved context's focus) — the paper itself is reference-free by design and does not define Context Recall at all.
- Unsupported Claim Rate is the sole claim-level project-operational formula, corroborated by FActScore/SAFE's precision pattern (neither paper names it "hallucination rate"). The claim-level Intrinsic/Extrinsic Hallucination Rate metrics were removed (2026-08-25, decision C) because no paper supported them as claim-level ratios. They were replaced with response-level Intrinsic/Extrinsic Response Rate metrics that directly match Maynez et al. (2020) Table 2's own reported methodology (see "Response-Level Hallucination Metrics" above) — `hallucination_type` continues to be sourced from Ji et al.'s taxonomy and remains available as a per-claim diagnostic regardless of whether it also feeds a response-level rate.
- IR and classification metrics are standard evaluation mathematics.
- ROUGE-L, BERTScore, Delta PPL, and semantic caching formulas exist in papers, but they are not implemented in the current codebase.

## Production Architecture and Latency Decision (2026-08-25)

**Production/default answer-generation backend: LOCAL QWEN TRANSFORMERS MODEL** (`Qwen/Qwen2.5-7B-Instruct`, run locally via Hugging Face Transformers, requires a CUDA GPU). This is now the default for both `main.py --ask` (the live production QA path) and `main.py --evaluate`'s default benchmark (`--models` default). Verified directly this session: exact HF identifier, 4-bit-quantized loading via `BitsAndBytesConfig` (nf4, double quant) with a float16 fallback, `device_map="auto"`, proper chat templating via `tokenizer.apply_chat_template` with a plain-text fallback — all in `llm/llm_client.py::_call_local_transformers`. A live `--ask` run this session confirmed the full pipeline (RAG retrieval → intent routing → prompt construction) correctly dispatches to `qwen_local` by default with no explicit flag, failing only on this sandbox's genuine absence of a CUDA GPU (an environment limitation, not a code defect — the code's own pre-existing guard correctly refuses to fake local inference without one).

**Gemini and other providers (OpenRouter Qwen/Llama, Groq-hosted models) remain optional alternative/evaluation backends only** — selectable via `--model`/`--models`, not deleted, not removed from `llm/llm_client.py`. The evaluation judges (Context, Grounding, Relevancy, Safety) continue to default to a separate model (`groq_llama70b` via `--judge-model`) — architecturally distinct from the answer-generation backend and unaffected by this change.

**Latency: removed from the official research evaluation metric set for the current study.** Full research audit and rationale: `docs/latency_final_audit.md` (concluded KEEP WITH RENAMING as a methodology recommendation; superseded here by an explicit product/architecture decision to exclude latency from the official metric set entirely for this study — not because the audit's methodology finding was wrong, but because latency reporting is not currently a priority for the paper). `evaluation/comparator.py::run_comparison`'s `final_model_comparison.csv` no longer includes an `"Average Latency"` column. Raw per-case generation latency (`evaluator.py`'s `"latency"` field, from `llm/llm_client.py::generate_response`'s `time.time()` delta) still exists in the detailed per-case output for engineering/debugging use — it is simply no longer aggregated or presented as an official research metric. No new latency metric was added; the already-built, unused `MetricsService` retrieval-stage instrumentation (`rag/services/metrics_service.py`) was left exactly as found, still not surfaced anywhere.

