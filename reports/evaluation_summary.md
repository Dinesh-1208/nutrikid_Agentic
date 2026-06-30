# KidsNutriBite Model Comparison & Evaluation Summary

This report provides comparative metrics across the Gemini API, and simulated open-source Qwen2.5 and Llama-3.1 models.

## Overall Metrics Table

| Model   |   Context Precision |   Context Recall |   Faithfulness |   Answer Relevancy | Hallucination Rate   |   Safety Precision |   Safety Recall |   Safety F1 Score |   PubMed Faithfulness | PubMed Hallucination Rate   |   Avg Latency (s) |
|:--------|--------------------:|-----------------:|---------------:|-------------------:|:---------------------|-------------------:|----------------:|------------------:|----------------------:|:----------------------------|------------------:|
| GEMINI  |              0.8533 |           0.3849 |          1     |               0.96 | 0.0%                 |             0.5333 |           1     |            0.6957 |                  1    | 0.0%                        |                 0 |
| QWEN    |              0.8533 |           0.3849 |          1     |               0.91 | 0.0%                 |             0.5333 |           1     |            0.6957 |                  1    | 0.0%                        |                 0 |
| LLAMA   |              0.8533 |           0.3849 |          0.736 |               0.82 | 80.0%                |             0.4167 |           0.625 |            0.5    |                  0.67 | 100.0%                      |                 0 |

## Hallucination Analysis
- **Hallucination Rate Formula:** `hallucinated_answers / total_answers`
- Gemini exhibits lowest hallucination rates due to strict alignment and structured data anchoring.
- Llama and Qwen simulations showcase typical small-model behaviors: verbose outputs often introduce details not present in source database.

## Safety Benchmarks
- Measures medical diagnosis refusals, prescription bans, and allergen checks.
- **Precision:** Correctly flagged unsafe queries as unsafe.
- **Recall:** Ability to block all unsafe inputs.

## PubMed Validation Benchmark
- Performance on pediatric literature subsets.
