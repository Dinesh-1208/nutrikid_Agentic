# KidsNutriBite: Project Formulas and Scientific Origins

This document outlines the mathematical formulas and metrics used in the KidsNutriBite evaluation subsystem. It provides a precise breakdown of which formulas are explicitly backed by recent RAG research papers, which are standard mathematical operationalizations, and which concepts were documented but not implemented in code.

## 1. Core LLM-as-a-Judge Evaluation Metrics (Layer 2)

These metrics rely on LLM-extracted structured data (Layer 1) processed through deterministic mathematical formulas (Layer 2).

| Metric | Formula | Implemented in code? | Paper-backed? | Exact formula printed in source? | Exact page/location |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **Faithfulness** | `F = Supported Claims / Total Claims` | Yes | Yes | Yes | RAGAS (Es et al., 2023), Section 3 (arXiv:2309.15217, ~Page 3) |
| **Answer Relevancy** | `AR = 1/n ∑ sim(q, qi)` (Mean cosine similarity of generated questions to original query) | Yes | Yes | Yes | RAGAS (Es et al., 2023), Section 3 (arXiv:2309.15217, ~Page 3) |
| **Context Recall** | `CR = Supported Expected Facts / Total Expected Facts` | Yes | Yes | Yes (in docs) | [RAGAS Context Recall Documentation](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_recall/) |
| **Overall Hallucination** | `HR = Unsupported Claims / Total Claims` | Yes | Yes | No (Operationalized) | Conceptual taxonomy from Ji et al. (2023) |
| **Intrinsic Hallucination** | `IHR = Intrinsic Unsupported / Total Claims` | Yes | Yes | No (Operationalized) | Conceptual taxonomy from Ji et al. (2023) |
| **Extrinsic Hallucination** | `EHR = Extrinsic Unsupported / Total Claims` | Yes | Yes | No (Operationalized) | Conceptual taxonomy from Ji et al. (2023) |

## 2. Standard Mathematical & Statistical Metrics

These are universal formulas used in the code to evaluate Information Retrieval (IR) and Classification accuracy. They are standard computer science metrics and are conceptually referenced, rather than explicitly defined, in the cited RAG papers.

| Metric | Formula | Implemented in code? | Paper-backed? | Exact formula printed in source? | Exact page/location |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **Precision@K** | `P@K = (Relevant hits in top K) / K` | Yes | Standard IR | No | Foundational IR Metric |
| **Recall@K** | `R@K = (Relevant hits in top K) / Total Relevant` | Yes | Standard IR | No | Foundational IR Metric |
| **MRR@K** | `1 / (Rank of first relevant result)` | Yes | Standard IR | No | Foundational IR Metric |
| **MAP** | `Mean(Average Precision@K over queries)` | Yes | Standard IR | No | Foundational IR Metric |
| **Safety F1** | `2PR / (P + R)` | Yes | Standard Math | No | Universal Classification Metric |
| **Safety F2** | `5PR / (4P + R)` | Yes | Project Choice | No | Project-specific choice prioritizing clinical safety (Recall over Precision) |

## 3. Documented Research (Not Implemented)

During the architectural design phase, several advanced methodologies were reviewed and documented in `research_notes.md`, but were ultimately excluded from the final project codebase to maintain a deterministic, decoupled evaluation architecture.

| Metric / Concept | Formula / Concept | Implemented in code? | Paper-backed? | Exact formula printed in source? | Exact page/location |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **ROUGE-L (P, R, F1)** | String-overlap similarity | No | Yes | No | arXiv:2411.00300, Page 14 |
| **BERTScore** | Embedding-based similarity | No | Yes | No | arXiv:2411.00300, Page 14 |
| **ΔPPL (Perplexity)** | Filtering rule equations | No | Yes | Yes | arXiv:2411.00300, Page 4 |
| **Semantic Caching** | Volume Score, Next Cover, DistanceLFU | No | Yes | Yes | arXiv:2603.03301, Pages 5, 6, 10, 11 |

---
*Note: This architecture intentionally separates semantic extraction (LLM) from formulaic computation (Python) to ensure perfectly auditable, mathematically deterministic scoring.*
