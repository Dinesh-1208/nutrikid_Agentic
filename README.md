# KidsNutriBite: Pediatric RAG Dietary Chatbot & Evaluation Framework

KidsNutriBite is an advanced Hybrid Retrieval-Augmented Generation (RAG) agentic architecture designed specifically for pediatric clinical nutrition and dietary planning. It couples a structured deterministic diet planner with a dense semantic FAISS index of pediatric guidelines, outputting safe, mathematically sound, and hallucination-free advice.

This repository also contains a custom **4-Layer Deterministic Evaluation Subsystem** to automatically benchmark Large Language Models (Gemini, Llama, Qwen) on clinical safety, information retrieval, and hallucination rates.

## Architecture

1. **Hybrid RAG Generator**: 
    - A deterministic rules-engine calculates BMR, caloric limits, and macronutrient targets based on age/weight/allergies.
    - `BAAI/bge-small-en-v1.5` dense retriever searches a vector database of pediatric protocols.
    - The **production default answer-generation backend is a local Qwen model (`Qwen/Qwen2.5-7B-Instruct`) run via Hugging Face Transformers** (requires a CUDA GPU), which synthesizes the math and text into a friendly output. Gemini, OpenRouter (Qwen/Llama), and Groq-hosted models remain available as optional alternative backends via `--model`/`--models`.
2. **Layer 1 - Semantic Judges (LLM)**: LLMs extract pure structural arrays from outputs (binary relevance labels, isolated claims, hypothetical questions, and CoT safety boolean flags).
3. **Layer 2 - Deterministic Metrics**: Pure Python module computes exact RAGAS mathematics, F-Scores, MRR, MAP, and hallucination percentages without LLM subjectivity.
4. **Master Orchestrator & Comparator**: Automates batch pipeline execution and generates detailed CSV and Markdown reports.

## Installation

```bash
git clone https://github.com/your-username/kidsnutribite.git
cd kidsnutribite
pip install -r requirements.txt
```

### Environment Variables
Create a `.env` file in the root directory:
```env
GEMINI_API_KEY="your_api_key"
OPENROUTER_API_KEY="your_api_key_for_open_source_models"
```

## Usage (CLI)

1. **Build the RAG Database:**
```bash
python main.py --index
```
2. **Test Semantic Retrieval:**
```bash
python main.py --query "What is the feeding protocol for infant diarrhea?"
```
3. **Run Full QA Pipeline** (uses the local Qwen production default; requires a CUDA GPU):
```bash
python main.py --ask "Can my child eat eggs during a fever?" --age 5 --condition "healthy_growth"
```
Pass `--model gemini` (or `qwen`, `llama`, `groq_llama70b`, `groq_llama8b`, `groq_qwen`) to use an optional alternative backend instead.
4. **Run Full Safety Benchmark Evaluation** (defaults to the local Qwen production backend):
```bash
python main.py --evaluate --num-samples 50
```
Pass `--models qwen_local,gemini` to also compare against optional alternative backends.

## Running on Kaggle / Colab

Upload or run `KidsNutriBite_Evaluation.ipynb` in any Jupyter environment. It is structurally designed to natively handle HuggingFace and Kaggle Secrets auth, download models, run single queries, execute benchmarks, and automatically plot results.

## Reports Generation

Running the `--evaluate` pipeline automatically produces:
- `reports/final_model_comparison.csv`: Top-level benchmarking data, including the **official** gold-grounded Precision@5, Recall@5, MAP@5, and MRR@5.
- `reports/ragas_report.csv`: Layer 2 MAP, MRR, Faithfulness metrics.
- `reports/hallucination_analysis.md`: Detailed Intrinsic vs Extrinsic hallucination rates.
- `reports/safety_analysis.md`: Deterministic F-Scores and confusion matrices.
- `reports/detailed_evaluation_records.csv`: Full trace logs.
- `reports/retrieval_experiment.csv`: **Unofficial retrieval-depth diagnostic** (`LLM-Judged Relevance Score@K` for K=3, 5, 10), produced by `KidsNutriComparator.run_llm_judged_relevance_experiment`. This is ground-truth-free and LLM-judged — it is **not** Average Precision, **not** MAP, and not part of the official gold-grounded retrieval metrics above. Do not compare its K=5 row against the official MAP@5 in `final_model_comparison.csv`; they measure different things from different data sources. It currently runs unconditionally on every `--evaluate` call and may be gated behind an explicit diagnostic flag in a future change.
