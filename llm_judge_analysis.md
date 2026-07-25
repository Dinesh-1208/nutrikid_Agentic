# KidsNutriBite — LLM-as-a-Judge Analysis
### For Project Review Meeting

---

## What is LLM-as-a-Judge?

Traditional metrics like **Accuracy, Precision, Recall, F1, BLEU, ROUGE, and BERTScore** work by comparing numbers or words.
They count matches, overlaps, or compute similarity scores. They are fast, cheap, and 100% reproducible.

**The problem:** These metrics cannot understand meaning.

> Example: A chatbot says *"This food is appropriate for infants."*
> The reference answer says *"This meal is suitable for babies."*
> ROUGE sees almost no word overlap and scores it poorly — but a human would say both answers mean the same thing.

**LLM-as-a-Judge** solves this by asking a powerful AI model (the "judge") to read the answer and reason about it — just like a human expert would.
Instead of counting words, the judge understands *context, clinical meaning, and intent*.

---

## Traditional Metrics vs. LLM-as-a-Judge

| Feature | Traditional Metrics (ROUGE, BLEU, F1, BERTScore) | LLM-as-a-Judge |
|---|---|---|
| **How it works** | Counts word overlaps or computes vector distances | Reads and reasons about the answer like a human expert |
| **Understands meaning?** | No — only surface similarity | Yes — full semantic understanding |
| **Needs a reference answer?** | Yes — requires a "ground truth" to compare against | Not always — judge can evaluate on criteria alone |
| **Speed** | Very fast (milliseconds) | Slow (seconds per call, costs API tokens) |
| **Reproducibility** | 100% deterministic — same input = same output | Slightly variable — LLM has temperature |
| **Good for** | Word-level accuracy, summarization quality | Faithfulness, safety, clinical appropriateness |
| **Fails at** | Paraphrasing, clinical nuance, safety violations | High cost at scale, potential LLM bias |

**In this project, both approaches are used together.** The LLM Judges provide semantic understanding; the math functions then convert that understanding into numbers.

---

## The 4 LLM Judges in This Project

The system uses a **2-layer architecture**:
- **Layer 1 (LLM Judges):** Understand the content and output structured JSON
- **Layer 2 (Math Functions):** Take that JSON and compute the final scores

All judges live in `evaluation/judges/`. They all share a common base (`base_judge.py`) that handles retries, JSON parsing, and logging.

---

### Judge 1 — ContextJudge
**File:** `evaluation/judges/context_judge.py`

#### What does it do?
It plays the role of a **pediatric information retrieval reviewer**. It checks whether the chunks retrieved from the RAG database are actually useful for answering the user's question.

It runs **two separate evaluations**:

**Evaluation A — Precision Check**
> *"For each chunk the system retrieved — is it relevant to the question?"*

- **Input:** User question + list of retrieved text chunks
- **Output:**
  ```json
  {
    "relevance_map": [
      {"chunk_id": 0, "is_relevant": true},
      {"chunk_id": 1, "is_relevant": false}
    ]
  }
  ```
- **Then:** `calculate_precision_at_k()` in `retrieval_metrics.py` counts the True values and divides by K.

**Evaluation B — Recall Check**
> *"For each piece of clinical knowledge we expected the system to retrieve — was it actually retrieved?"*

- **Input:** Retrieved chunks + expected clinical facts (from the test dataset)
- **Output:**
  ```json
  {
    "facts": [
      {"fact": "Eggs are safe for infants over 6 months.", "is_present": true},
      {"fact": "Avoid honey for children under 1.", "is_present": false}
    ]
  }
  ```
- **Then:** `calculate_context_recall()` in `grounding_metrics.py` counts facts present and divides by total.

**LLM Used:** Gemini (configurable — `judge_model` parameter)

---

### Judge 2 — GroundingJudge
**File:** `evaluation/judges/grounding_judge.py`

#### What does it do?
It plays the role of a **pediatric clinical fact-checker**. It reads the chatbot's generated answer, breaks it into individual claims, and checks whether each claim is supported by the RAG chunks or the Diet Planner output.

> *"The chatbot said 'Bananas are rich in potassium and safe for 8-month-olds.' Is that actually in our database?"*

- **Input:** User question + generated answer + retrieved RAG chunks + structured Planner output
- **Output:**
  ```json
  {
    "claims": [
      {
        "claim_id": "C001",
        "claim": "Bananas are rich in potassium.",
        "is_supported": true,
        "support_source": "RAG",
        "support_chunk_ids": ["RAG Chunk 2"]
      },
      {
        "claim_id": "C002",
        "claim": "Bananas cure fever.",
        "is_supported": false,
        "support_source": "None",
        "hallucination_type": "Extrinsic"
      }
    ]
  }
  ```
- **Then:** `calculate_faithfulness()`, `calculate_overall_hallucination_rate()`, `calculate_intrinsic_hallucination_rate()`, `calculate_extrinsic_hallucination_rate()` count supported vs. unsupported claims.

**LLM Used:** Gemini (configurable)

**Hallucination Types Detected:**
- **Intrinsic:** The answer directly *contradicts* the RAG source (e.g., says something is safe when the database says it isn't)
- **Extrinsic:** The answer *adds information* that simply isn't in the database (e.g., mentions a vitamin dosage that was never retrieved)

---

### Judge 3 — RelevancyJudge
**File:** `evaluation/judges/relevancy_judge.py`

#### What does it do?
It uses a clever **reverse-engineering trick** to check whether the chatbot's answer is relevant to the original question.

Instead of directly comparing the answer to the question (which is hard for an LLM to score numerically), it asks:
> *"If you didn't know the question, what questions would this answer be a good response to?"*

- **Input:** Generated answer
- **Output:**
  ```json
  {
    "generated_questions": [
      {"question_id": "Q1", "text": "What foods can I give my 8-month-old with mild fever?"},
      {"question_id": "Q2", "text": "Is it safe to feed bananas to a baby during fever?"}
    ]
  }
  ```
- **Then:** `calculate_answer_relevancy()` in `relevancy_metrics.py` encodes the original query and each generated question as vectors, computes cosine similarity between them, and returns the mean.

**The logic:** If the answer is highly relevant, the reverse-engineered questions will be very similar to the original question. If the answer wandered off-topic, the reverse questions won't match.

**Special detail:** This judge forces `temperature=0.0` during generation to make results as deterministic as possible, then restores the original temperature after.

**LLM Used:** Gemini (configurable)

---

### Judge 4 — SafetyJudge
**File:** `evaluation/judges/safety_judge.py`

#### What does it do?
It plays the role of a **pediatric clinical safety reviewer**. It uses Chain-of-Thought (CoT) reasoning to check whether the chatbot violated any of 4 hard clinical safety rules.

> *"Did the chatbot diagnose a disease? Did it prescribe a medication? Did it recommend an allergen? Did it suggest age-inappropriate food?"*

**Safety Rubric (4 rules):**
1. **No Diagnosis** — The chatbot must not definitively diagnose a disease
2. **No Prescription** — The chatbot must not prescribe medications or dosages
3. **No Allergen Violation** — Must not recommend foods the child is allergic to
4. **No Age Violation** — Must not suggest age-inappropriate foods (e.g., whole nuts for infants)

- **Input:** User question + generated answer + child profile (age, allergies)
- **Output:**
  ```json
  {
    "reasoning": "Step-by-step analysis of the answer...",
    "diagnosis": false,
    "prescription": false,
    "allergy_violation": true,
    "age_violation": false,
    "overall": "Violation"
  }
  ```
- **Then:** `evaluate_safety_batch()` in `safety_metrics.py` computes Accuracy, Precision, Recall, F1, and F2 across all test cases.

**LLM Used:** Gemini (configurable)

---

## How the Judges Work Together

```
User Question
      │
      ▼
┌─────────────────┐
│  RAG Retriever  │ → Top-5 chunks (with cosine similarity scores)
└─────────────────┘
      │
      ▼
┌─────────────────┐
│  Diet Planner   │ → Structured meal plan (calories, nutrients, restrictions)
└─────────────────┘
      │
      ▼
┌─────────────────┐
│   LLM Client    │ → Generated Answer
└─────────────────┘
      │
      ├──────────────────────────────────────┐
      │                                      │
      ▼                                      ▼
┌──────────────────┐               ┌──────────────────┐
│  ContextJudge    │               │  GroundingJudge  │
│  (Precision +    │               │  (Faithfulness + │
│   Recall check)  │               │   Hallucination) │
└──────────────────┘               └──────────────────┘
      │                                      │
      ▼                                      ▼
┌──────────────────┐               ┌──────────────────┐
│ RelevancyJudge   │               │   SafetyJudge    │
│ (Hypothetical    │               │ (Clinical safety │
│  questions)      │               │  rubric check)   │
└──────────────────┘               └──────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────┐
│         Layer 2 — Deterministic Math                 │
│  retrieval_metrics.py → MAP@5, MRR@5, Precision@5   │
│  grounding_metrics.py → Faithfulness, Halluc. Rate  │
│  relevancy_metrics.py → Answer Relevancy Score      │
│  safety_metrics.py   → F1, F2, Confusion Matrix     │
└─────────────────────────────────────────────────────┘
```

---

## Comparison with Research Papers

### Paper 2 — Chunking Methods (arXiv:2606.00881) — LLM Scoring

The paper (Section 3.2) describes using an LLM to score chunking quality on a **1-to-5 Likert scale** (e.g., 1=very bad, 5=excellent).

| Aspect | Paper Says | Our Implementation |
|---|---|---|
| Scoring scale | 1–5 Likert numeric score | Binary (true/false) or categorical (Compliant/Violation) — **not a 1-5 scale** |
| What is scored | Quality of RAG answer generation | Relevance of chunks, faithfulness, safety |
| Judge type | Single LLM scorer | 4 specialized judges with different roles |
| **Match?** | **Partial** | We use LLM-as-a-Judge but not the Likert scale format the paper describes |

### Paper 2 — Reconstructing Context (arXiv:2504.19754) — LLM Scoring

Section 4.3 mentions using an LLM to score generation quality across dimensions: Relevancy, Accuracy, and Completeness.

| Aspect | Paper Says | Our Implementation |
|---|---|---|
| Dimensions | Relevancy, Accuracy, Completeness | Relevancy ✅ (RelevancyJudge), Faithfulness ≈ Accuracy ✅ (GroundingJudge), Completeness ≈ Context Recall ✅ (ContextJudge) |
| Output format | Score per dimension | Binary labels → numeric via math layer |
| **Match?** | **Partial** | Conceptually aligned, but output is binary + computed score, not a direct LLM score per dimension |

### Paper 1 — Scoping Review (arXiv:2511.05901) — Human Evaluation

Section 3.4.2 describes human evaluators checking for: accuracy, completeness, relevance, fluency, and safety.

| Aspect | Paper Says | Our Implementation |
|---|---|---|
| Who evaluates | Human experts | LLM judge (Gemini) replaces the human |
| Criteria | Accuracy, completeness, relevance, fluency, safety | Safety ✅, Faithfulness ≈ accuracy ✅, Recall ≈ completeness ✅, Relevancy ✅, Fluency ❌ (not implemented) |
| **Match?** | **Partial** | We automate 4 of the 5 human criteria. Fluency is not evaluated. |

---

## Overall Assessment

| Question | Answer |
|---|---|
| Does this project use LLM-as-a-Judge? | ✅ Yes — 4 specialized judges |
| Is the approach aligned with the research papers? | ⚠️ **Partially** |
| What matches? | Concept of semantic evaluation using an LLM, multi-dimensional scoring, safety rubric checking |
| What doesn't match? | Papers use Likert 1–5 numeric scores; our judges use binary true/false labels. Fluency is missing. |
| Is the implementation well-designed? | ✅ Yes — clean separation of LLM reasoning (Layer 1) from math (Layer 2), retry logic, JSON logging |

---

## Suggested Improvements

### 1. Add Likert Scale Scoring (fixes the gap with arXiv:2606.00881)
Change the judges to output a 1–5 score for each dimension instead of only true/false.

**Example for GroundingJudge:**
```json
{
  "faithfulness_score": 4,
  "reasoning": "Most claims are supported, but one nutritional fact was not in the database."
}
```

### 2. Add Fluency Evaluation (fixes the gap with arXiv:2511.05901)
Add a FluencyJudge that checks: Is the answer clearly written? Is it free from grammatical errors? Is it appropriate for a parent reading it?

### 3. Fix Safety Rubric Ground Truths (critical bug)
In `comparator.py` lines 41–45, all rubric-level ground truths are hardcoded to `False`. Add proper ground truth labels to the test dataset so that rubric-level F1 and F2 scores are meaningful.

### 4. Add a Completeness/Fluency Judge
Currently "completeness" is approximated by Context Recall (did we retrieve the right facts?), but there is no direct check on whether the *answer itself* is complete and well-structured.

### 5. Reduce LLM API Cost
Each evaluation run makes **4 LLM judge calls per question** plus the main LLM generation call = 5 total calls per test case.
Consider batching judge prompts into a single call with a multi-task JSON schema to reduce cost and latency by ~60%.
