# MASTER RESEARCH ROADMAP — KidsNutriBite

**Prepared:** 2026-09-18
**Basis:** direct inspection of this repository + verified literature search
**Constraint observed:** no project file was modified and no code was implemented. This document and
its companions in [docs/research/](.) are new files only.

**Companion reports**

| File | Topic |
|---|---|
| [00_CURRENT_ARCHITECTURE.md](00_CURRENT_ARCHITECTURE.md) | What the system actually is today |
| [01_NER_RESEARCH.md](01_NER_RESEARCH.md) | Named Entity Recognition |
| [02_FEATURE_ENGINEERING_RESEARCH.md](02_FEATURE_ENGINEERING_RESEARCH.md) | Feature engineering |
| [03_QWEN_ARCHITECTURE_RESEARCH.md](03_QWEN_ARCHITECTURE_RESEARCH.md) | Qwen2.5-7B architecture |
| [04_SELF_ATTENTION_RESEARCH.md](04_SELF_ATTENTION_RESEARCH.md) | Self-attention |
| [05_HYPERPARAMETER_OPTIMIZATION_RESEARCH.md](05_HYPERPARAMETER_OPTIMIZATION_RESEARCH.md) | Hyperparameter optimization |
| [06_PRUNING_RESEARCH.md](06_PRUNING_RESEARCH.md) | Pruning |
| [07_FINETUNING_FEASIBILITY_RESEARCH.md](07_FINETUNING_FEASIBILITY_RESEARCH.md) | Fine-tuning feasibility |

---

## 1. Current Implementation — One-Page Summary

KidsNutriBite is a **CLI research prototype** (`main.py`, argparse, five mutually exclusive modes).
**There is no frontend and no backend web service.**

| Layer | What is implemented |
|---|---|
| **Knowledge** | 558 RAG records (mean 134 chars); structured DB: 99 foods, 173 conditions, 148 goals, 15 allergies |
| **Index** | Parent–child chunking (600/150/30) → 558 parents, 781 children; `BAAI/bge-small-en-v1.5` (384-d); FAISS `IndexFlatIP` (exact), `ntotal=781` |
| **Retrieval** | Semantic LRU cache (0.95) → FAISS top-20 + BM25 top-20 → weighted linear fusion **α=0.7** → metadata filter (never invoked) → cross-encoder rerank 20→5 → parent expansion |
| **Routing** | `any(kw in query.lower() for kw in ["plan","diet","meal","menu"])` |
| **Planner** | Deterministic: Holliday–Segar energy, 25/35/30/10 meal split, tag-based filtering, greedy fill to 95% |
| **LLM** | `Qwen/Qwen2.5-7B-Instruct`, local, 4-bit NF4 + double quant, T=0.1, top_p=0.9, max_new_tokens=1024 |
| **Prompting** | Two templates (diet / QA), both with no-diagnosis, no-prescription, no-invention and allergy guardrails; diet template also forbids arithmetic |
| **Evaluation** | 49 cases (41 RAG-applicable); RAGAS-style + IR metrics; judges on Groq **`openai/gpt-oss-120b`**; typed status enums so judge failures never become zeros |

**Architectural strength worth claiming in the paper:** all nutrition arithmetic is deterministic
Python and the LLM is explicitly forbidden from recalculating it. *Numbers come from code, prose comes
from the model.* This is a defensible safety design, not an accident.

### 1.1 Verified gaps

| # | Gap | Evidence |
|---|---|---|
| G1 | No query understanding — profile from CLI flags with **hardcoded fabricated defaults** (age 7.0, weight 20.0) that are then asserted to the LLM as fact | `main.py:86-92`, `prompt_templates.py:56-61` |
| G2 | Metadata filtering **never invoked**; list branch is `pass`; no age handling | `metadata_filter_service.py`, `main.py:99` |
| G3 | Routing is a 4-keyword substring test with known false positives and negatives | `main.py:103-105` |
| G4 | Parent–child chunking **degenerate**: 100% of records < 600 chars (split never fires); 64% single-child | built index artifact |
| G5 | **No post-generation allergen/safety validation** of answer text | no such code exists |
| G6 | Reranker is out-of-domain (MS MARCO web search) | model card |
| G7 | Safety P/R/F1 **mathematically undefined** — 0 `Violation` labels | `dataset.py` |
| G8 | No systematic hyperparameter tuning; one hardcoded config | `config_service.py` |
| G9 | No evidence fine-tuning is warranted or that data exists | report 07 |
| G10 | BM25 `metadata_filters` parameter accepted but unused | `bm25_service.py` |
| G11 | Weekly planner is dead code (only its own test calls it) | `planner/` |
| G12 | Evaluation always uses the **diet** prompt; production mostly uses the **QA** prompt | `evaluator.py` |

---

## 2. Proposed Research Extensions

| # | Extension | Source report | Addresses |
|---|---|---|---|
| R1 | Entity extraction from free-text queries (gazetteer-first) | 01 | G1, G3 |
| R2 | Structured feature schema with `source` provenance | 02 | G1 |
| R3 | Document-side metadata back-fill | 02 | G2, G4 |
| R4 | Activate metadata filtering | 01, 02 | G2, G10 |
| R5 | NER-based intent routing | 01 | G3 |
| R6 | Deterministic allergen safety validator | 01 | G5 |
| R7 | Retrieval/reranker hyperparameter study | 05 | G6, G8 |
| R8 | Inference-parameter study incl. greedy decoding | 05 | G8 |
| R9 | Context-ordering study (*Lost in the Middle*) | 04 | — |
| R10 | Corpus expansion from IFCT 2017 + WHO/UNICEF IYCF | 07 | G4 |
| R11 | Evaluation-set expansion incl. `Violation` cases | 05, 07 | G7 |
| R12 | **Layer/depth pruning study** (ShortGPT / LaCo / SLEB / Gromov) | 06 §10 | efficiency + novel evaluation setting |
| R13 | **Domain-aware pruning (D-Pruner) for pediatric nutrition** | 06 §15.2 | **novel contribution route** |
| R14 | **Nutrition-domain calibration** across Wanda / SparseGPT / OWL / SliceGPT | 06 §15.3 | cheap, cross-cutting, high novelty |
| R15 | Domain-redundancy analysis (which neurons/heads our task actually uses) | 06 §18 P6 | zero-risk insight |
| R16 | SliceGPT dimension pruning (reaches the 14% embedding mass) | 06 §14 | only method touching embeddings |
| R17 | Quantisation ladder (bf16 → int8 → NF4 → GPTQ/AWQ) | 05 §A6 | establishes the quality ceiling |
| R18 | **RAFT — retrieval-aware fine-tuning** | 07 §8.4 | thesis-aligned; uses documents we own |
| R19 | Speculative decoding (lossless latency) | 04 §6 | attacks the real bottleneck |
| R20 | Minitron-style width+depth+distillation | 06 §13 | `⚡` cluster-scale |

---

## 3. Literature Review Summary

Grouped by the system component each body of work informs. Full citation lists live in the
individual reports.

**RAG and retrieval.** Lewis et al. NeurIPS 2020 ([arXiv:2005.11401](https://arxiv.org/abs/2005.11401))
for the paradigm; Karpukhin et al. EMNLP 2020 ([arXiv:2004.04906](https://arxiv.org/abs/2004.04906))
for dense retrieval; Robertson & Zaragoza FnTIR 2009
([DOI 10.1561/1500000019](https://doi.org/10.1561/1500000019)) for BM25; Cormack et al. SIGIR 2009
([DOI 10.1145/1571941.1572114](https://doi.org/10.1145/1571941.1572114)) for RRF as the alternative
to our linear fusion; Nogueira & Cho ([arXiv:1901.04085](https://arxiv.org/abs/1901.04085)) for
cross-encoder reranking; Xiao et al. SIGIR 2024
([arXiv:2309.07597](https://arxiv.org/abs/2309.07597)) for BGE; Wang et al. EMNLP 2024
([ACL 2024.emnlp-main.981](https://aclanthology.org/2024.emnlp-main.981/)) for systematic RAG design
choices — the closest methodological template for our experiment structure.

**Model architecture.** Qwen2.5 Technical Report
([arXiv:2412.15115](https://arxiv.org/abs/2412.15115)); Vaswani et al. NeurIPS 2017
([arXiv:1706.03762](https://arxiv.org/abs/1706.03762)); Ainslie et al. EMNLP 2023
([arXiv:2305.13245](https://arxiv.org/abs/2305.13245)) for GQA; Su et al.
([arXiv:2104.09864](https://arxiv.org/abs/2104.09864)) for RoPE; Shazeer
([arXiv:2002.05202](https://arxiv.org/abs/2002.05202)) for SwiGLU; Zhang & Sennrich
([arXiv:1910.07467](https://arxiv.org/abs/1910.07467)) for RMSNorm; Dettmers et al. NeurIPS 2023
([arXiv:2305.14314](https://arxiv.org/abs/2305.14314)) for NF4/QLoRA.

**Information extraction.** Lample et al. NAACL 2016
([arXiv:1603.01360](https://arxiv.org/abs/1603.01360)); Neumann et al. BioNLP 2019
([arXiv:1902.07669](https://arxiv.org/abs/1902.07669)) for scispaCy; Lee et al. Bioinformatics 2020
([DOI 10.1093/bioinformatics/btz682](https://doi.org/10.1093/bioinformatics/btz682)) for BioBERT;
Zaratiana et al. NAACL 2024 ([arXiv:2311.08526](https://arxiv.org/abs/2311.08526)) for GLiNER —
the strongest zero-shot option for our open schema; Popovski & Koroušić Seljak Database 2019
([PMC6827550](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6827550/)) for FoodBase.

**Evaluation and hallucination.** Es et al. EACL 2024
([arXiv:2309.15217](https://arxiv.org/abs/2309.15217)) for RAGAS; Maynez et al. ACL 2020
([arXiv:2005.00661](https://arxiv.org/abs/2005.00661)) and Ji et al. ACM CSUR 2023
([DOI 10.1145/3571730](https://doi.org/10.1145/3571730)) for the intrinsic/extrinsic taxonomy;
Min et al. EMNLP 2023 ([arXiv:2305.14251](https://arxiv.org/abs/2305.14251)) for FActScore;
Smucker et al. CIKM 2007 ([DOI 10.1145/1321440.1321528](https://doi.org/10.1145/1321440.1321528))
for significance testing in IR.

**Compression.** *Unstructured:* SparseGPT — Frantar & Alistarh ICML 2023
([arXiv:2301.00774](https://arxiv.org/abs/2301.00774)); Wanda — Sun et al. ICLR 2024
([arXiv:2306.11695](https://arxiv.org/abs/2306.11695)); OWL non-uniform sparsity — Yin et al. ICML 2024
([arXiv:2310.05175](https://arxiv.org/abs/2310.05175)); sparse pretraining
([arXiv:2405.03594](https://arxiv.org/abs/2405.03594)). *Semi-structured:* 2:4 N:M sparsity — Mishra
et al. ([arXiv:2104.08378](https://arxiv.org/abs/2104.08378)). *Structured:* LLM-Pruner — Ma et al.
NeurIPS 2023 ([arXiv:2305.11627](https://arxiv.org/abs/2305.11627)); ZipLM inference-aware — Kurtic
et al. NeurIPS 2023 ([arXiv:2302.04089](https://arxiv.org/abs/2302.04089)); SliceGPT — Ashkboos et al.
ICLR 2024 ([arXiv:2401.15024](https://arxiv.org/abs/2401.15024)); Minitron — Muralidharan et al.
NeurIPS 2024 ([arXiv:2407.14679](https://arxiv.org/abs/2407.14679)), whose finding that **"width
pruning outperforms depth, but only after retraining"** directly determines our method choice.
*Depth:* ShortGPT ([arXiv:2403.03853](https://arxiv.org/abs/2403.03853)), Gromov et al.
([arXiv:2403.17887](https://arxiv.org/abs/2403.17887)), Shortened LLaMA
([arXiv:2402.02834](https://arxiv.org/abs/2402.02834)), LaCo
([arXiv:2402.11187](https://arxiv.org/abs/2402.11187)), SLEB
([arXiv:2402.09025](https://arxiv.org/abs/2402.09025)).
***Domain-aware — the most relevant paper found:*** **D-Pruner**, *Pruning as a Domain-specific LLM
Extractor*, NAACL Findings 2024 ([arXiv:2405.06275](https://arxiv.org/abs/2405.06275)) — validated on
**healthcare** and legal domains, and the direct precedent for a pediatric-nutrition study.

**Retrieval-aware training.** RAFT ([arXiv:2403.10131](https://arxiv.org/abs/2403.10131)) and
Self-RAG ([arXiv:2310.11511](https://arxiv.org/abs/2310.11511)) — training a model to use retrieved
context correctly and ignore distractors, which is closer to this project's thesis than any
knowledge-injection fine-tuning would be.

**Domain precedent.** Zhou et al., *FoodSky*
([arXiv:2406.10261](https://arxiv.org/abs/2406.10261)) — a food/dietetics LLM passing Chinese chef
and dietetic examinations, which had to construct its own corpus. The single best citation for both
the related-work section and the dataset-gap claim.

---

## 4. Feasible Experiments — Ranked

Ranked by (information gained) ÷ (cost). **Cost class:** 🟢 no LLM calls · 🟡 retrieval + judges ·
🔴 full generation + judges.

| Rank | ID | Experiment | Cost | Why here |
|---|---|---|---|---|
| 1 | **X0** | **Truncation check** — do any saved answers hit the 1024-token cap mid-sentence? | 🟢 | Inspecting existing CSVs. **If truncation is occurring, existing results are affected.** Do this today |
| 2 | **X1** | **Variance audit** — 10 cases × 5 repeats at T=0.1 | 🔴 small | Establishes the **noise floor**. Without it, no other result is interpretable |
| 3 | **X2** | **Pool diagnostic** — Recall@20 vs Recall@5 on 41 cases | 🟢 | Reveals whether to invest in the reranker or the first stage. Zero LLM calls |
| 4 | **X3** | **Routing accuracy** — keyword vs NER rule, hand-labelled | 🟢 | Cheapest experiment with a likely clear win; fixes G3 |
| 5 | **X4** | **Reranker on/off ablation** | 🟡 | Clean component ablation; belongs in the paper regardless of outcome |
| 6 | **X5** | **Metadata back-fill coverage** — gazetteer over 558 records | 🟢 | **Decides whether filtering experiments are viable at all** |
| 7 | **X6** | **α endpoints** {0.0, 0.5, 0.7, 1.0} | 🟡 | Answers "does hybrid retrieval help at all?" |
| 8 | **X7** | **Gold-filter ceiling** — filters from `dataset.py` gold fields | 🟡 | One run that decides whether NER-based filtering is worth building |
| 9 | **X8** | **top_k sweep** {3, 5, 10, 15} | 🔴 | Large context headroom makes it affordable; dilution is a real hypothesis |
| 10 | **X9** | **Greedy decoding** switch + baseline re-run | 🔴 | Removes a noise source permanently |
| 11 | **X10** | **NER component eval** (E0 in report 01) | 🟢 + annotation | Prerequisite asset for X3, X7, X12 |
| 12 | **X11** | **Context ordering** (*Lost in the Middle*) | 🔴 | Reordering strings only; literature predicts an effect |
| 13 | **X12** | **NER-enhanced generation** (E2 in report 01) | 🔴 | Most expensive; run after X7 justifies it |
| 14 | **X13** | **Reranker swap** to `bge-reranker-base` | 🟡 | Addresses verified out-of-domain problem (G6) |
| 15 | **X14** | **Allergen safety validator** (E4 in report 01) | 🔴 + new data | Highest real-world value; needs an adversarial set first |

**Compression experiments (report 06) are listed separately in §7 Phase 5**, because they are ranked
on a different axis (compute tier) rather than on judge cost. They are **scheduled, not deferred**.

**Items 1, 3, 4, 6 and 11 require no LLM generation at all.** That is where to start — five
informative results at essentially zero inference cost.

---

## 5. Evaluation Metrics

### 5.1 Already implemented and usable

| Layer | Metrics | Source |
|---|---|---|
| Retrieval | Recall@5, Precision@5, MAP@5, MRR@5 | Manning et al. 2008; Voorhees TREC-8 1999 |
| Generation | Faithfulness, Answer Relevancy | RAGAS, EACL 2024 |
| Generation | Context Recall | **RAGAS documentation only — not in the paper** |
| Hallucination | Intrinsic/Extrinsic rate; Hallucination Rate | Maynez 2020; Ji 2023; operational definition project-specific |
| Safety | Compliant / Refusal / Violation classification | project rubric, `safety_judge.py` |

### 5.2 Proposed additions

| Metric | Definition | Why | Judge needed? |
|---|---|---|---|
| **Recall@20** | gold chunk in the rerank pool | Separates first-stage failure from reranker failure | No |
| **Empty-result rate** | queries returning < k chunks | Detects over-filtering | No |
| **Format compliance** | all required sections present | Objective; highly diagnostic under pruning/fine-tuning | No |
| **Refusal-script compliance** | exact refusal text on medical queries | Objective safety check | No |
| **False-premise rate** | answer asserts a child attribute the user never stated | **Catches the G1 defect, which no current metric detects** | Yes |
| **Entity F1 / linking accuracy** | per-type NER quality | Prerequisite for interpreting NER experiments | No |
| **Routing accuracy** | correct planner-vs-QA decision | Measures G3 | No |
| **Allergen violation recall** | detected unsafe recommendations | The safety metric that matters | Partly |
| **Latency p50/p90, peak GPU memory** | wall clock, `max_memory_allocated` | Required for pruning/efficiency claims | No |

Most proposed metrics are **judge-free and objective** — a deliberate improvement over relying on a
deliberately-permissive LLM judge.

### 5.3 Statistical protocol (mandatory)
Paired comparisons on identical cases; **bootstrap 95% CIs** (Efron 1979); paired randomisation tests
(Smucker et al. CIKM 2007); the study labelled **exploratory** at n = 41; in-sample tuning disclosed
if no dev/test split is used.

---

## 6. Risks

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| RK1 | **n = 41 cannot detect small effects** — most experiments may be inconclusive | **High** | X1 first; prefer coarse contrasts; report CIs; expand set (R11) |
| RK2 | **Permissive grounding judge inflates Faithfulness** | **High** | Describe it as an upper bound; add judge-free metrics (§5.2) |
| RK3 | **Safety metrics undefined** (0 Violation labels) | **High** | Report the label distribution, not P/R/F1; build adversarial cases |
| RK4 | **Semantic cache contaminating experiments** | High | `enable_cache = False` in every experimental run — non-negotiable |
| RK5 | **Sampling non-determinism** at T=0.1 | Medium | Greedy decoding (X9) |
| RK6 | **Over-filtering** from metadata filters | Medium | Fallback to unfiltered; measure empty-result rate |
| RK7 | **Wrong allergen extraction → unsafe output** | **Critical** | NER may only *add* restrictions, never remove a declared one. Fail-safe |
| RK8 | **Corpus metadata too sparse to filter** (17% condition coverage; no age field) | High | X5 decides before investing in X7/X12 |
| RK9 | **Evaluation circularity** if Qwen extracts, answers and a sibling LLM judges | Medium | Prefer gazetteer/GLiNER; disclose if used |
| RK10 | **Scope overreach** — 7 topics is more than one project can execute | **High** | §7 phasing by cost tier; Phases 1–3 are the core deliverable, Phases 5–6 are scoped by budget, not abandoned |
| RK15 | **Compute budget** — several experiments need rented A100/L4 time | Medium | §7 compute-budget table; one A100 day covers the highest-value cluster of measurements |
| RK16 | **Over-specialisation** from task/domain-aware pruning or RAFT — tuning against 49 questions then evaluating on them | **High** | Held-out queries mandatory; R11 evaluation-set expansion is a prerequisite |
| RK11 | **Documentation drift** — describing a frontend/backend that does not exist | **High** | `00` §1 is the authority |
| RK12 | **Truncated answers** silently degrading Faithfulness | Medium | X0, immediately |
| RK13 | **Licensing** — IFCT redistribution terms unverified; MedMCQA license inconsistent | Medium | Verify before redistributing anything |
| RK14 | **No doctor-in-the-loop** — no clinical validation of outputs or gold answers | **High** | State as an explicit limitation of the project |

---

## 7. What to Implement First

### Phase 1 — Correctness and measurement (do these first; mostly free)
1. **X0** — truncation check on existing answer CSVs.
2. **Fix the documented judge-model row** — the paper's Table 1 must read `openai/gpt-oss-120b`
   (Groq-hosted), **not** Llama-3.3-70B.
3. **Reconcile the `>0.10` threshold with its `50%` comment** in `evaluator.py`, and state the chosen
   value with a justification in the paper.
4. **X1** — variance audit. Establishes the noise floor.
5. **X2** — Recall@20 vs Recall@5 pool diagnostic.
6. **Disable the semantic cache** for all experimental runs.

*Phase 1 delivers: a defensible baseline, a known error bar, and two corrected claims. No new
components.*

### Phase 2 — The cheapest real research (highest return)
7. **X3** — routing accuracy, keyword vs NER. Fixes G3, needs no LLM.
8. **X5** — metadata back-fill coverage. Decides the viability of everything filter-related.
9. **X4** — reranker on/off ablation.
10. **X6** — α endpoints.

*Phase 2 delivers: four paper-ready results, minimal inference cost.*

### Phase 3 — NER and features (the main research contribution)
11. **X10** — annotate the 49 questions; build the gazetteer extractor; evaluate per-type F1.
12. **R2** — the feature schema with `source` provenance (fixes the fabricated-defaults defect).
13. **X7** — gold-filter ceiling. **If this shows no gain, stop the filtering line and say so.**
14. **X12** — NER-enhanced generation, only if X7 is positive.
15. **X8**, **X11**, **X13** as budget allows.

### Phase 4 — Corpus and evaluation quality
16. **R10** — IFCT 2017 foods; WHO/UNICEF IYCF guideline records (also addresses G4).
17. **R11** — expand the evaluation set, including `Violation` safety cases.
18. **X14** — allergen safety validator, once adversarial cases exist.

### Phase 5 — Compression programme (report 06) — **scheduled, not deferred**

Hardware is treated as a **budget item**, not an exclusion criterion. Ordered by cost:

19. **P6 — domain-redundancy analysis** (`06` §18). No pruning at all: measure which FFN neurons and
    attention heads our 49 prompts actually activate versus generic text. Zero risk, forward passes
    only, and it informs every other compression decision.
20. **P1 — layer/depth pruning sweep** (`06` §10, §18). Lowest-compute structured method; runs on
    24 GB; **must include a random-selection control**. Published depth-pruning results are on
    MMLU/perplexity, **not on grounded safety-constrained RAG**, so the answer here is genuinely
    unknown.
21. **R14 — nutrition-domain calibration** across Wanda / SparseGPT / OWL / SliceGPT (`06` §15.3).
    Cheap, cross-cutting, and reportable whichever way it comes out.
22. **P3 — D-Pruner domain-aware extraction** (`06` §15.2). **The novel-contribution route.**
    Precedent exists in healthcare and legal domains (NAACL Findings 2024); pediatric nutrition
    appears unoccupied. Needs no labelled data.
23. **P4 / P5 — SliceGPT and structured FFN pruning.** `🖥️` 40–80 GB.
24. **P8 — Minitron-style width+depth+KD.** `⚡` Cluster-scale; partial replication only if a full
    run is out of budget, and must be reported as under-trained rather than as method failure.

**Deployment motivation, not just efficiency:** sparse-quantised models report **up to 3× CPU and
8.6× sparse-quantised CPU speedups** ([arXiv:2405.03594](https://arxiv.org/abs/2405.03594)), which
would enable **GPU-free operation** — a substantive product argument for a pediatric nutrition tool
aimed at Indian caregivers in low-connectivity settings.

### Phase 6 — Fine-tuning, **gated on data, not on hardware**

**Report 07's conclusion stands: no suitable public pediatric-nutrition instruction dataset exists,
and our own corpus (~19 k tokens) is 4–5 orders of magnitude short of what domain-adaptive
pretraining needs.** That is a data conclusion; more GPUs would not change it.

If a fine-tuning contribution is nevertheless required, the ranked candidates (`07` §8) are:

25. **R18 — RAFT (retrieval-aware fine-tuning).** Trains the model to use retrieved context correctly
    and ignore distractors — which is this project's actual thesis, and addresses a verified property
    of our pipeline (top-5 chunks are ranked, not guaranteed relevant). Distractors are free from our
    own corpus.
26. **Behavioural fine-tuning** (format + refusal compliance only) — objectively checkable without a
    judge. **Test prompt engineering first**, as the cheaper control.
27. **Distillation** — the only genuinely label-free route; doubles as pruning recovery.
28. **Synthetic instruction data** — breaks the deadlock but inherits teacher errors and creates
    evaluation circularity. Requires human validation.

**Hard prerequisite for all four: R11 (evaluation-set expansion).** With 49 cases serving as the test
set, there is no honest way to both train and evaluate.

### Genuinely outside the current architecture
- Multi-turn conversational memory, web/mobile frontend, doctor-in-the-loop clinical review.
  Real and valuable; not reachable from a single-shot CLI without an architectural change.

### Compute budget summary

| Tier | Experiments | Hardware |
|---|---|---|
| **Free** | X0, X2, X3, X5, X6, P6 | Existing machine; several need no GPU at all |
| **Current T4/Kaggle** | X1, X4, X7–X13, P1 (quality arm) | 15–16 GB |
| **One rented A100-40GB / L4 day** | R17 quantisation ladder, FlashAttention comparison, vLLM batching, **all pruning throughput measurements** | `🖥️` |
| **A100-80GB, hours–days** | P3 D-Pruner, P4 SliceGPT, P5 structured pruning, R18 RAFT | `🖥️` |
| **Multi-GPU cluster, days** | P8 Minitron, sparse pretraining, continued pretraining | `⚡` |

**A single rented A100 day covers the quantisation ladder, the attention-backend comparison and every
pruning throughput number together.** That is the highest-leverage purchase in this roadmap.

---

## 8. The Honest Framing for the Paper

Three things this roadmap deliberately protects against:

1. **Do not claim components that are dormant.** Metadata filtering, the weekly planner, and the
   inert 600-char parent size are in the code but not in the working system. Describing them as
   features is the easiest way to lose credibility under questioning.

2. **Do not present small metric differences as findings.** At n = 41 with a permissive judge and
   sampling enabled, differences of a few points are noise. X1 exists precisely so the paper can say
   *how much* noise.

3. **Negative results are results.** Several plausible outcomes here are negative — metadata
   filtering may not help on a 781-vector corpus; α may not matter behind a cross-encoder; attention
   attribution may not agree with judged faithfulness; prompt engineering may match fine-tuning on
   format compliance. Each is publishable if measured properly, and each is more defensible than an
   overstated positive.

The strongest available narrative for this project is not *"we added seven techniques."* It is:

> *A verified-by-inspection account of a hybrid-RAG pediatric nutrition assistant, a measurement
> methodology honest about its own noise floor and its judge's permissiveness, and a set of targeted
> extensions — entity extraction, structured features, and systematic retrieval tuning — each
> evaluated against a pre-stated decision rule, including the rules under which the extension is
> rejected.*
