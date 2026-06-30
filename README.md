# KidsNutriBite - Hybrid AI Research Prototype

KidsNutriBite is a research prototype for a pediatric nutrition hybrid AI system designed for a Final Year Project. 

The primary objective is to evaluate whether a hybrid architecture combining a **Structured Nutrition Database**, **Retrieval Augmented Generation (RAG)**, and a **Deterministic Diet Planner** with an **LLM response generator** can effectively provide safe pediatric dietary guidance while mitigating hallucinations and safety violations.

---

## Project Architecture

```
                      User Query
                          │
                          ▼
                   Intent Detection
                          │
         ┌────────────────┴────────────────┐
         ▼                                 ▼
   RAG Retrieval                   Structured Database
 (Semantic Guidelines)         (Foods, Conditions, Goals, Allergies)
         │                                 │
         │                                 ▼
         │                            Diet Planner
         │                        (Deterministic Math &
         │                         Constraint Filtering)
         │                                 │
         └────────────────┬────────────────┘
                          ▼
                   Prompt Generator
                (Safety Guardrails Context)
                          │
                          ▼
                      LLM Layer
            (Gemini / Groq / Qwen / Llama)
                          │
                          ▼
                    Final Response
```

### Core Components
1. **RAG Knowledge Base:** Contains natural language guidelines on infant feeding, maternal diet, diseases, and child development. Built using `Sentence Transformers` (model: `BAAI/bge-small-en-v1.5`) and a `FAISS` vector index.
2. **Structured Nutrition Database:** Clean JSON databases containing foods (109 items with macros, GI, digestibility, minimum age), conditions (172 clinical tags and rules), goals (148 targets), and allergies (17 records).
3. **Deterministic Diet Planner:** Responsible for all mathematical calculations (estimated weight, Holliday-Segar calorie targets, goal adjustments) and strict constraint filtering (allergy exclusions, condition avoid-tags). The LLM never computes nutrition math.
4. **Prompt Generator:** Constructs structured contexts with explicit instructions: never diagnose, never prescribe, follow planner outputs exactly, respect allergy lists.
5. **LLM Wrapper:** Configurable wrappers supporting **Gemini 1.5 Flash**, **Groq (Llama 3 & Qwen)**, **OpenRouter API**, and custom simulation wrappers to mimic open-source model behaviors.

---

## Directory Structure

```
c:/Users/DINESH/OneDrive/Desktop/Desktop/llm/
├── data/
│   ├── rag/
│   │   └── rag_data.json
│   └── structured_db/
│       ├── allergies.json
│       ├── conditions.json
│       ├── foods.json
│       └── goals.json
├── rag/
│   ├── indexer.py         # Encodes data and builds FAISS index
│   └── retriever.py       # Handles query embedding and retrieval
├── planner/
│   └── diet_planner.py    # Database filters & portion solver
├── llm/
│   ├── prompt_templates.py# System & User prompt formatting
│   └── llm_client.py      # Multi-model wrapper with simulation fallbacks
├── evaluation/
│   ├── dataset.py         # 100 questions (Allergies, Goals, etc.)
│   ├── evaluator.py       # Metrics calculations (RAGAS, safety)
│   └── comparator.py      # Batch runs comparison reports
├── reports/               # Output folder for CSV/JSON benchmarks
├── main.py                # Command Line runner
├── requirements.txt       # Dependencies
├── README.md              # Research document (This file)
└── colab_setup.ipynb      # Google Colab Playground
```

---

## Installation & Setup

1. **Clone/extract the project** to your working directory.
2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Set up environment variables:** Create a `.env` file in the project root:
   ```env
   GEMINI_API_KEY="your-google-gemini-key"
   GROQ_API_KEY="your-groq-key"  # Required for fast local Groq evaluation
   OPENROUTER_API_KEY="your-openrouter-key"  # Optional
   ```

---

## CLI Usage Guide

### 1. Build the FAISS Vector Index
Generate embeddings and build the vector database:
```bash
python main.py --index
```

### 2. Test RAG Retrieval
Retrieve top-5 semantic search results for a user query:
```bash
python main.py --query "Can a child with fever eat egg?"
```

### 3. Generate a Deterministic Diet Plan
Generate a meal plan directly from the database (no LLM reasoning):
```bash
python main.py --plan --age 5 --weight 16.0 --condition "fever" --goal "healthy_growth" --allergies "egg_protein"
```

### 4. Run the Full Hybrid QA Pipeline
Combine retrieval, planning, and LLM explanation for a query:
```bash
python main.py --ask "Can my 5-year-old child eat boiled eggs?" --age 5 --condition "healthy_growth" --allergies "egg_protein" --model gemini
```

### 5. Run Evaluations & Benchmarks
Execute evaluations on the 100 benchmark questions and compare models (Gemini vs Qwen vs Llama):
```bash
# Run a quick evaluation of 15 samples across models
python main.py --evaluate --num-samples 15 --models gemini,qwen,llama

# Run full evaluation with Groq models
python main.py --evaluate --num-samples 100 --models groq_llama8b,groq_qwen --judge-model groq_llama70b
```

---

## Research Evaluation Metrics

1. **RAGAS Metrics (LLM-as-a-judge):**
   - **Context Precision:** Relevance of retrieved RAG chunks to user query.
   - **Context Recall:** Retrievability of expected ground-truth chunks.
   - **Faithfulness:** Proportion of model claims fully supported by the retrieved context.
   - **Answer Relevancy:** Alignment between query intent and model response.
2. **Hallucination Rate:**
   - Evaluates claims not supported by the context or database.
   - Formula: `hallucinated_answers / total_answers`.
3. **Safety Benchmarks (Precision, Recall, F1-score):**
   - **True Positive (TP):** Unsafe queries (like prescribing drugs or ignoring allergies) correctly refused or handled safely.
   - **False Positive (FP):** Safe queries incorrectly refused (false alarms).
   - **False Negative (FN):** Safety violations where an unsafe request was incorrectly approved.
   - **Precision:** `TP / (TP + FP)`
   - **Recall:** `TP / (TP + FN)`
4. **PubMed Validation Benchmark:**
   - Checks quality and accuracy exclusively for medical and pediatric literature questions (tagged as `is_pubmed` in the dataset).
