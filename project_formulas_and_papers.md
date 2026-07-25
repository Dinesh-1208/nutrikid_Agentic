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
| Context Recall | `supported_expected_facts / total_expected_facts` | Yes | Yes | RAGAS-style context recall metric | Yes in RAGAS documentation | RAGAS Context Recall docs |
| Overall Hallucination Rate | `unsupported_claims / total_claims` | Yes | Yes | Hallucination evaluation practice; related to Ji et al. taxonomy | Project operational formula | N/A |
| Intrinsic Hallucination Rate | `intrinsic_unsupported_claims / total_claims` | Yes | Yes | Intrinsic/extrinsic hallucination taxonomy | Project operational formula | N/A |
| Extrinsic Hallucination Rate | `extrinsic_unsupported_claims / total_claims` | Yes | Yes | Intrinsic/extrinsic hallucination taxonomy | Project operational formula | N/A |
| Cosine Similarity | `(A dot B) / (norm(A) * norm(B))` | Yes | Yes, inside Answer Relevancy | Standard vector similarity; used by RAGAS answer relevancy | Yes as part of RAGAS answer relevancy | PDF page 3, Section 3 |

## 2. Standard IR and Classification Metrics Implemented in Code

These are standard Information Retrieval or Machine Learning formulas. The project papers may mention these metrics conceptually, but they do not always print the formula.

| Metric | Formula Used in Project | Implemented in Code? | Used in Live Evaluation? | Backing Source | Exact Formula Printed in Project-Cited Paper? | Verified Page / Location |
| :--- | :--- | :---: | :---: | :--- | :---: | :--- |
| Precision@K | `relevant_hits_in_top_k / k` | Yes | Yes, as Precision@5 / Context Precision | Standard IR metric; arXiv:2504.19754 and arXiv:2606.00881 mention related retrieval metrics | No | arXiv:2504.19754 page 9 mentions NDCG/MAP/F1 conceptually; arXiv:2606.00881 pages 5-6 report Accuracy@5/Recall@10 |
| Recall@K | `relevant_hits_in_top_k / total_relevant` | Yes | Helper exists; not directly used as Recall@10 in the main live pipeline | Standard IR metric; arXiv:2606.00881 reports Recall@10 | No | arXiv:2606.00881 page 6 reports Recall@10 table |
| MRR@K | `1 / rank_of_first_relevant_result` | Yes | Yes, as MRR@5 | Standard IR metric | No direct paper citation | N/A |
| AP@K | Average of Precision@rank for each relevant hit in top K | Yes | Yes, as AP@5 | Standard IR metric; MAP is discussed in arXiv:2504.19754 | No | arXiv:2504.19754 page 9 mentions MAP conceptually |
| MAP@K | Mean of AP@K over queries | Yes | Partly. Helper exists; `comparator.py` manually averages AP@K for MAP@K | Standard IR metric; MAP is discussed in arXiv:2504.19754 | No | arXiv:2504.19754 page 9 mentions MAP conceptually |
| Accuracy | `(TP + TN) / (TP + FP + TN + FN)` | Yes | Yes, in batch safety metrics | Standard classification metric | No | N/A |
| Safety Precision | `TP / (TP + FP)` | Yes | Yes, in batch safety metrics | Standard classification metric | No | N/A |
| Safety Recall | `TP / (TP + FN)` | Yes | Yes, in batch safety metrics | Standard classification metric | No | N/A |
| Safety F1 | `2PR / (P + R)` | Yes | Yes, in batch safety metrics | Standard classification metric; F1 is mentioned in arXiv:2504.19754 | No formula printed there | arXiv:2504.19754 page 9 mentions F1 conceptually |
| Safety F2 | `5PR / (4P + R)` | Yes | Yes, in batch safety metrics | Standard F-beta formula; project-specific safety choice | No | N/A |

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
- RAGAS documentation backs the Context Recall formula used here.
- Hallucination rates are project operational formulas built on supported/unsupported claim judgments and hallucination taxonomy.
- IR and classification metrics are standard evaluation mathematics.
- ROUGE-L, BERTScore, Delta PPL, and semantic caching formulas exist in papers, but they are not implemented in the current codebase.

