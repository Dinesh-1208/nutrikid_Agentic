# 05 — Hyperparameter Optimization for KidsNutriBite

**Structure mandated by the mentor's brief:**
- **A.** LLM inference parameters
- **B.** Retrieval parameters
- **C.** Reranker parameters
- **D.** Training parameters — **deliberately excluded**; see §7 for why, with a pointer to
  `07_FINETUNING_FEASIBILITY_RESEARCH.md`.

**Core constraint that governs this entire report:** the evaluation set is **49 cases, 41 of them
RAG-applicable**. That is small. §6 is therefore not an appendix — it is the part that determines
whether any tuning result means anything, and it should be read before §1–§5.

---

## 0. Current State: One Hardcoded Configuration, Never Tuned

Every parameter below currently sits at a single default in `rag/services/config_service.py` or
`llm/llm_client.py`. There is no sweep, no search, no validation split, and no record of why any
value was chosen. That is a legitimate thing to state in the paper as the starting point — and it
means *any* systematic tuning is a contribution over the baseline.

---

## A. LLM Inference Parameters

| # | Parameter | Current | Where | Search range to consider |
|---|---|---|---|---|
| A1 | `temperature` | **0.1** | `llm_client.py` | `{0.0 (greedy), 0.1, 0.3, 0.7}` |
| A2 | `top_p` | **0.9** | `llm_client.py` | `{0.9, 0.95, 1.0}` |
| A3 | `max_new_tokens` | **1024** | `llm_client.py` | `{512, 768, 1024, 1536}` |
| A4 | `do_sample` | implied `True` | `llm_client.py` | `{True, False}` |
| A5 | `repetition_penalty` | not set (1.0) | — | `{1.0, 1.05, 1.1}` |
| A6 | quantisation | 4-bit NF4 + double quant | `llm_client.py` | `{nf4, fp4, int8, bf16}` |
| A7 | `bnb_4bit_compute_dtype` | `float16` | `llm_client.py` | fixed by T4 hardware |
| A8 | `attn_implementation` | **not set** | — | `{eager, sdpa}` (`flash_attention_2` needs Ampere+) |

### A1/A4 — Temperature and the determinism problem

This is the most important finding in section A, and it is a **methodological** point, not a tuning
point.

At `temperature = 0.1` with sampling enabled, generation is **near-greedy but not deterministic**.
Every metric we report therefore carries generation variance stacked on top of judge variance and
n=41 sampling variance. Three sources of noise, one of which is trivially removable.

**Recommendation: set `do_sample = False` (greedy) for all evaluation runs.** Justification:
- The task is grounded, factual explanation of a deterministically-computed diet plan. There is no
  value in diversity.
- It makes the experiment **exactly reproducible**, which matters far more for a final-year project
  than a fractional quality difference.
- It removes one confound from every other experiment in reports 01, 02 and this one.

This is a change with a real cost — it is a code change, and the existing results were produced under
sampling — so it should be introduced as a *new* configuration and its baseline re-run, not
retro-fitted to existing numbers.

> **Experiment A-E1 (variance audit, run this first):** regenerate answers for the same 10 cases
> **5 times** under the current `temperature=0.1, do_sample=True` settings. Report the standard
> deviation of Faithfulness and Hallucination Rate across repeats.
> **This single experiment tells us how large a difference has to be before it means anything.** If
> run-to-run σ turns out to be 3 points, then a 4-point improvement from any intervention is noise.
> It is cheap (50 generations, no new code paths) and it is the highest-value experiment in this
> entire report.

### A2 — top_p
At `T = 0.1` the softmax is already sharply peaked, so the nucleus rarely binds; `top_p = 0.9` is
close to inert. Not wrong, but it should not be presented as an active control in the paper. If
greedy decoding is adopted (A4), `top_p` becomes formally irrelevant.

Reference: Holtzman et al., *The Curious Case of Neural Text Degeneration*, ICLR 2020 —
[arXiv:1904.09751](https://arxiv.org/abs/1904.09751).

### A3 — max_new_tokens: check for truncation before tuning
`max_new_tokens = 1024` is a **hard cut**, not a target. Our diet-mode prompt requests four sections
including a per-meal walkthrough, which is a long output.

> **Prerequisite check (not an experiment — just a measurement):** inspect the saved answer CSVs
> (`qwen_with_rag_answers.csv`, `experiment1_no_rag_answers.csv`) for answers ending mid-sentence or
> at exactly the token cap. **NOT VERIFIED — I have not measured this.** If truncation is occurring,
> Faithfulness is being judged on incomplete text and the whole results table is affected. This must
> be checked before any tuning is reported.

Trade-off: `max_new_tokens` is the dominant term in generation latency (each token = one full 28-layer
pass, `03` §3). Reducing it is the single most effective latency lever; raising it risks nothing
except time, given our large context headroom.

### A5 — repetition_penalty
Not currently set. Worth a single check rather than a sweep: inspect existing answers for repeated
phrasing. If none is present, leave it at 1.0 and say so — adding a penalty to a grounded extraction
task can *suppress* legitimate repetition of nutrient names and food terms, which would be actively
harmful here.

### A6 — Quantisation as a quality/memory trade-off `⚡ HIGH-COMPUTE OPTION` `🖥️`
Currently 4-bit NF4 + double quantisation (QLoRA data types — Dettmers et al., NeurIPS 2023 —
[arXiv:2305.14314](https://arxiv.org/abs/2305.14314)).

**We have never measured the quality cost of quantisation on this task**, so we do not know whether
our reported Faithfulness is depressed by it. This is one of the most consequential unmeasured
variables in the project and it should be measured.

**Full quantisation ladder worth sweeping** (not just bf16 vs NF4):

| Setting | Weight memory (approx) | Ideal hardware | Note |
|---|---|---|---|
| **bf16 / fp16** (reference) | ~15.2 GB | **1 × A100-40GB or L4-24GB** | The true quality ceiling |
| int8 (`LLM.int8()`) | ~7.6 GB | 1 × 24 GB | Dettmers et al. — [arXiv:2208.07339](https://arxiv.org/abs/2208.07339) |
| **NF4 + double quant** (current) | ~4.2 GB | 1 × 16 GB | Our production setting |
| fp4 | ~4.2 GB | 1 × 16 GB | NF4 alternative in `bitsandbytes` |
| GPTQ 4-bit / 3-bit | ~4.2 / ~3.2 GB | 1 × 16–24 GB | Frantar et al., ICLR 2023 — [arXiv:2210.17323](https://arxiv.org/abs/2210.17323) |
| AWQ 4-bit | ~4.2 GB | 1 × 16–24 GB | Lin et al., MLSys 2024 — [arXiv:2306.00978](https://arxiv.org/abs/2306.00978) |

> **Implementation consideration (not an elimination):** bf16 at ~15.2 GB does not fit comfortably
> on a 15–16 GB T4 alongside activations and KV cache. **Rent one A100-40GB or L4-24GB instance for
> this single sweep.** The experiment is valuable and should not be dropped for want of local VRAM —
> it establishes the quality ceiling against which every other result is judged.

### A8 — attn_implementation `🖥️ for the fastest option`
Not explicitly set, so `transformers` picks a default. **For reproducibility this should be pinned
regardless of which is chosen.**

| Option | Quality effect | Hardware |
|---|---|---|
| `eager` | none (reference) | any |
| `sdpa` | none (exact) | any, incl. Turing T4 |
| `flash_attention_2` | **none — exact, not an approximation** | **Ampere or newer** |

Dao et al., *FlashAttention* — [arXiv:2205.14135](https://arxiv.org/abs/2205.14135);
*FlashAttention-2* — [arXiv:2307.08691](https://arxiv.org/abs/2307.08691).

Because FlashAttention is **exact**, switching to it changes speed and memory but **not output**, so
it cannot confound quality results. On a T4 (Turing, sm_75) it is unavailable and `sdpa` is the
correct choice; on a rented Ampere+ instance `flash_attention_2` should be used. **This is a
deployment-target decision, not a research-scope decision.**

---

## B. Retrieval Parameters

| # | Parameter | Current | Where | Search range |
|---|---|---|---|---|
| B1 | `embedding_model` | `BAAI/bge-small-en-v1.5` (384-d) | `config_service.py` | `{bge-small, bge-base, bge-large, e5-base, gte-base}` |
| B2 | `parent_chunk_size` | **600** | `config_service.py` | **inert — see B-crit** |
| B3 | `child_chunk_size` | **150** | `config_service.py` | `{100, 150, 250, 400}` |
| B4 | `child_overlap` | **30** | `config_service.py` | `{0, 30, 60}` |
| B5 | `retrieval_mode` | `hybrid` | `config_service.py` | `{dense, bm25, hybrid}` |
| B6 | `alpha` (fusion weight) | **0.7** | `fusion_service.py` | `{0.0, 0.3, 0.5, 0.7, 0.9, 1.0}` |
| B7 | `top_k` | **5** | `config_service.py` | `{3, 5, 10, 15}` |
| B8 | `fetch_n` (candidate pool) | `max(20, k·3)` = **20** | `retrieval_service.py` | `{20, 50, 100}` |
| B9 | `enable_metadata_filtering` | `True` but **never invoked** | `config_service.py` | see report 01/02 |
| B10 | `cache_similarity_threshold` | **0.95** | `config_service.py` | `{0.95, 0.99}` |
| B11 | `enable_cache` | `True` | `config_service.py` | **set `False` for all experiments** |
| B12 | index type | `IndexFlatIP` (exact) | `indexer.py` | leave alone — see B-note |

### B-crit — The chunking parameters are partly inert (verified)

From `00_CURRENT_ARCHITECTURE.md` §3.2:

- **100% of the 558 source records are ≤ 600 characters**, so `parent_chunk_size = 600` **never
  fires**. Tuning B2 would change nothing. This must be stated, or a reviewer will ask why a swept
  parameter had zero effect.
- **64% of parents produce exactly one child**, so for most of the corpus parent expansion is a no-op
  and the "small-to-big" retrieval design contributes nothing.

**Implication: the interesting chunking experiment is the opposite of the usual one.** Rather than
splitting more finely, the question is whether **merging related short records into larger parents**
(by `type`, `condition`, or topic) would make hierarchical chunking actually function. That is a
data-engineering experiment, not a parameter sweep, and it is more likely to matter than B3/B4.

### B6 — alpha, and an honest expectation

`alpha = 0.7` weights dense 0.7 / sparse 0.3 in a **weighted linear** fusion (not RRF — see
`00` §4.2).

The endpoints are the most informative settings: `alpha = 1.0` is dense-only, `alpha = 0.0` is
BM25-only. Running just `{0.0, 0.5, 0.7, 1.0}` answers *"does hybrid retrieval help at all on this
corpus?"* — which is a better research question than finding the optimal third decimal place.

**Expect a possibly flat curve.** With only 781 vectors and a cross-encoder reranking the top 20, the
reranker can recover from first-stage ordering mistakes, which compresses differences between fusion
weights. A flat result is a finding: *"on a corpus of this size, with cross-encoder reranking,
first-stage fusion weight had little measurable effect."* That is worth reporting, not hiding.

Alternative fusion to cite as the road not taken: Reciprocal Rank Fusion — Cormack, Clarke &
Büttcher, SIGIR 2009 — [DOI 10.1145/1571941.1572114](https://doi.org/10.1145/1571941.1572114). RRF
is scale-free and needs no score normalisation, which removes the min-max normalisation step our
BM25 service currently performs. A B-vs-RRF comparison is a clean, citable experiment.

### B7/B8 — top_k and the candidate pool

Note the coupling in `retrieval_service.py`: `fetch_n = max(rerank_top_n, k*3)`. With
`rerank_top_n = 20` and `k = 5`, `fetch_n = 20`. Raising `k` to 10 gives `max(20, 30) = 30`. So B7
and B8 are **not independent** — a sweep must account for this, or the reported "top_k effect" will
silently include a pool-size effect.

**Context budget is not a constraint** (`03` §7): we use ~1–2k of a 32,768-token window. Raising
`top_k` from 5 to 15 is entirely affordable in tokens. The only question is whether more context
helps or **dilutes** — and *Lost in the Middle* (Liu et al., TACL 2024 —
[arXiv:2307.03172](https://arxiv.org/abs/2307.03172)) gives specific reason to expect dilution past
some point. This makes B7 one of the genuinely interesting sweeps.

Also note: with 781 child chunks, `top_k = 15` retrieves ~1.9% of the corpus. Recall@k will rise
mechanically with k, so **Recall@k alone must not be used to pick k** — Faithfulness and
Hallucination Rate must be co-reported, since they capture the dilution cost.

### B11 — Disable the cache during every experiment

`CacheService` returns a hit for any query within cosine 0.95 of a previous one
(`00` §4.6). During a sweep, the same 41 questions are run repeatedly; cache hits would return
contexts computed under a *previous* configuration, silently invalidating the comparison.

**`enable_cache = False` is mandatory for all tuning runs.** This is the kind of detail that
invalidates results if missed, and it costs nothing to get right.

### B12 — Do not tune the index type
`IndexFlatIP` is exact brute force. At 781 vectors, an approximate index (IVF, HNSW) would add
approximation error for no measurable speed benefit. Leave it. State in the paper that exact search
is used, so retrieval quality is not confounded by ANN recall loss — that is a *strength* of the
current setup worth claiming.
FAISS reference: Douze et al., *The Faiss library* — [arXiv:2401.08281](https://arxiv.org/abs/2401.08281).

### B1 — Embedding model
`bge-small-en-v1.5` is 384-d and fast (Xiao et al., *C-Pack*, SIGIR 2024 —
[arXiv:2309.07597](https://arxiv.org/abs/2309.07597)). `bge-base` (768-d) and `bge-large` (1024-d)
are the obvious upgrades; `e5` (Wang et al. — [arXiv:2212.03533](https://arxiv.org/abs/2212.03533))
and `gte` (Li et al. — [arXiv:2308.03281](https://arxiv.org/abs/2308.03281)) are alternatives.
Comparative context: MTEB benchmark — Muennighoff et al., EACL 2023 —
[arXiv:2210.07316](https://arxiv.org/abs/2210.07316).

**Cost warning:** changing B1 requires a **full index rebuild** and invalidates the cache and the
`dataset_hash`. It is the most expensive parameter to sweep. Given that reranking follows retrieval,
a stronger bi-encoder may show a smaller end-to-end effect than expected. Run this **last**, if at all.

---

## C. Reranker Parameters

| # | Parameter | Current | Where | Search range |
|---|---|---|---|---|
| C1 | `enable_reranking` | `True` | `config_service.py` | `{True, False}` |
| C2 | `reranker_model` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | `config_service.py` | `{MiniLM-L-2, L-4, L-6, L-12, bge-reranker-base, bge-reranker-large}` |
| C3 | `rerank_top_n` (pool) | **20** | `config_service.py` | `{10, 20, 50, 100}` |
| C4 | output `top_k` | **5** | `config_service.py` | coupled with B7 |
| C5 | reranker batch size | default | — | latency only |

### C1 — The ablation that must be in the paper
**"With reranker" vs "without reranker"** is the single most valuable retrieval experiment here,
because it is a clean, complete component ablation, it needs only a config flag, and it produces a
result that either justifies the component or does not.

Method: cross-encoder reranking — Nogueira & Cho, *Passage Re-ranking with BERT* —
[arXiv:1901.04085](https://arxiv.org/abs/1901.04085).

### C2 — The out-of-domain problem
`ms-marco-MiniLM-L-6-v2` is trained on **MS MARCO web-search relevance**
([model card](https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2); MS MARCO —
[arXiv:1611.09268](https://arxiv.org/abs/1611.09268)). It has never seen pediatric clinical text.

Candidate replacements, both worth testing:
- `BAAI/bge-reranker-base` / `bge-reranker-large` — trained with the BGE recipe and multilingual
  data ([BAAI/bge-reranker-base](https://huggingface.co/BAAI/bge-reranker-base); C-Pack —
  [arXiv:2309.07597](https://arxiv.org/abs/2309.07597)).
- Larger MiniLM variants (`L-12`) — better quality, higher latency.

Relevant empirical context: Wang et al., *Searching for Best Practices in Retrieval-Augmented
Generation*, EMNLP 2024, pp. 17716–17736 —
[ACL 2024.emnlp-main.981](https://aclanthology.org/2024.emnlp-main.981/),
[arXiv:2407.01219](https://arxiv.org/abs/2407.01219) — systematically evaluates reranker choice
among other RAG design decisions; also BEIR for zero-shot/out-of-domain retrieval behaviour —
Thakur et al., NeurIPS 2021 Datasets & Benchmarks — [arXiv:2104.08663](https://arxiv.org/abs/2104.08663).

### C3 — Pool size is the reranker's recall ceiling
The reranker can only reorder what the first stage produced. With `rerank_top_n = 20` out of 781
chunks, any gold chunk ranked 21st by fusion is **permanently unreachable**, no matter how good the
reranker is.

> **Diagnostic to run before tuning C3:** for each of the 41 cases, compute the fusion rank of each
> gold `relevant_chunk_id`. Report **Recall@20** (the pool) alongside **Recall@5** (the output).
> The gap between them is the maximum possible gain from a better reranker; the shortfall of
> Recall@20 from 1.0 is the maximum possible gain from a larger pool. This single diagnostic tells us
> whether to invest in C2 or C3, and it costs **no LLM calls at all**.

Cost note: the cross-encoder scores every (query, chunk) pair, so latency scales **linearly** with
`rerank_top_n`. Going 20 → 100 is a 5× reranking cost.

---

## D. Training Parameters — Deliberately Excluded

Per the brief, training hyperparameters (learning rate, batch size, epochs, LoRA rank/alpha, warmup,
weight decay) are **out of scope** for this report.

The reason is substantive, not merely procedural: **we have not established that fine-tuning is
warranted or that suitable training data exists.** `07_FINETUNING_FEASIBILITY_RESEARCH.md` documents
the dataset search and its conclusion. Specifying a learning-rate schedule for a model we have no
justified corpus to train would be putting the method before the question.

If and only if report 07's feasibility criteria are met, training hyperparameters are discussed there.

---

## 6. Experimental Methodology — The Part That Determines Validity

### 6.1 The sample-size problem, stated plainly

- **49 cases total; 41 RAG-applicable; 22 with a profile; 20 with a `Compliant` safety label; 0 with
  a `Violation` label.**

At n = 41, the 95% confidence interval on a proportion near 0.9 is roughly **±9 percentage points**.
That means a configuration scoring 0.92 and one scoring 0.88 are **statistically indistinguishable**
on this set. Any tuning report that presents a ranked table of configurations differing by a few
points, without intervals, is reporting noise as signal.

This is not a reason to abandon tuning. It is a reason to:
1. Report **bootstrap 95% CIs** on every number (Efron, 1979 —
   [DOI 10.1214/aos/1176344552](https://doi.org/10.1214/aos/1176344552)).
2. Use **paired** tests on identical cases — a paired randomisation test is the standard IR
   recommendation (Smucker, Allan & Carterette, CIKM 2007 —
   [DOI 10.1145/1321440.1321528](https://doi.org/10.1145/1321440.1321528)).
3. Prefer **large, coarse contrasts** (reranker on/off, dense-only vs hybrid, k=5 vs k=15) over fine
   sweeps, because only large effects are detectable.
4. Label the study **exploratory**, which is honest and entirely acceptable for a B.Tech project.

### 6.2 Overfitting the benchmark
Tuning on all 49 cases and reporting on the same 49 cases **overfits**. The clean protocol is a
**dev/test split** (e.g. 30 tune / 19 report). With n = 49 that split is painfully small, so the
honest alternatives are:
- split anyway and accept wide intervals, **or**
- tune on all 49 and state explicitly that reported numbers are **in-sample** and optimistic.

Either is defensible if stated. Silently doing the second while implying the first is not.

### 6.3 Search strategy
For the small, mostly-categorical spaces above, **grid search over a few coarse values** is
appropriate and fully interpretable. Random search (Bergstra & Bengio, JMLR 2012 —
[JMLR v13](https://jmlr.org/papers/v13/bergstra12a.html)) beats grid search in high-dimensional
continuous spaces — not our situation. Bayesian optimisation (Optuna — Akiba et al., KDD 2019 —
[arXiv:1907.10902](https://arxiv.org/abs/1907.10902)) is real overkill at n = 41: it would optimise
against evaluation noise. **Recommend grid search, and say why** — that reasoning is itself a
defensible research contribution.

### 6.4 Cost accounting
Each full evaluation run on 41 cases costs roughly: 41 local Qwen generations (the slow part) plus
~4 judge calls per case ≈ 164 Groq calls. A 6-point sweep of one parameter ≈ 246 generations and
~1,000 judge calls. **Budget deliberately**: prefer the retrieval-only experiments (no generation, no
judges) wherever a question can be answered with Recall@5 / MAP@5 alone.

### 6.5 Metrics to report per configuration

| Layer | Metrics | Generation/judge calls needed? |
|---|---|---|
| Retrieval | Recall@5, Recall@20, Precision@5, MAP@5, MRR@5, empty-result rate | **No** — cheap |
| Generation | Faithfulness, Answer Relevancy, Hallucination Rate | Yes — expensive |
| Safety | Compliant rate, refusal rate | Yes (P/R/F1 **undefined**, see 6.6) |
| Efficiency | retrieval latency, generation latency, peak GPU memory | No judges |

Prefer retrieval-layer experiments. They are ~50× cheaper and answer most of the open questions.

### 6.6 Two standing caveats that apply to every number
1. **The grounding judge is deliberately permissive** — its prompt says *"Be GENEROUS with
   `is_supported: true`"* and accepts "well-established fact" and "contextual inference" as support.
   Faithfulness is therefore an **upper bound**. Configurations cannot be finely discriminated by a
   metric tuned to be generous.
2. **Safety P/R/F1 are mathematically undefined** on this dataset (zero `Violation` labels). Do not
   report them as numbers; report the label distribution and say why the metrics are undefined.

---

## 7. Recommended Priority Order

Ranked by (information gained) ÷ (cost), using only verified facts about this system:

| Rank | Experiment | Cost | Why first |
|---|---|---|---|
| 1 | **A-E1 variance audit** (5 repeats × 10 cases) | Low | Establishes the noise floor. Without it, no other result is interpretable. |
| 2 | **C3 pool diagnostic** (Recall@20 vs Recall@5) | **Zero LLM calls** | Tells us whether to invest in the reranker or the first stage |
| 3 | **C1 reranker on/off** | Retrieval-only | Clean component ablation; must be in the paper |
| 4 | **B6 alpha endpoints** {0.0, 0.5, 0.7, 1.0} | Retrieval-only | Answers "does hybrid help at all?" |
| 5 | **B7 top_k** {3, 5, 10, 15} | Retrieval + generation | Context headroom makes this affordable; dilution is a real hypothesis |
| 6 | **A4 greedy decoding** | Low | Removes a noise source permanently |
| 7 | **A3 truncation check** | **Zero cost** — inspect existing CSVs | May invalidate existing results; check now |
| 8 | **C2 reranker swap** (bge-reranker-base) | Medium | Addresses the verified out-of-domain problem |
| 9 | **B3/B4 chunk sizes** | Index rebuild | Partly inert (B-crit); reframe as record-merging |
| 10 | **B1 embedding model** | Full rebuild | Most expensive, likely masked by reranking |
| 11 | **A6 quantisation ladder** (bf16 → int8 → NF4 → GPTQ/AWQ) | `🖥️` rent 1 × A100-40GB / L4 | **Establishes the quality ceiling.** Rank is low only because it needs a rented instance, not because it is low-value |

Items 2, 3, 4 and 7 require **no LLM generation at all** and can be completed quickly. That is where
to start.

### 7.1 Experiments requiring rented GPU time (do not drop — schedule)

| Experiment | Why it needs better hardware | Minimum instance |
|---|---|---|
| A6 quantisation ladder | bf16 weights ~15.2 GB + activations | A100-40GB or L4-24GB |
| `flash_attention_2` throughput comparison | Ampere+ only | A10G / L4 / A100 |
| Batched evaluation via vLLM | Throughput benefit needs headroom | A100-40GB |
| Any pruning **speed** measurement (`06` §16) | 2:4 sparsity needs Ampere+ sparse tensor cores | A100 / L4 / RTX 40 |

**These are budget items, not research exclusions.** A single rented A100 day would cover the
quantisation ladder, the attention-implementation comparison and the pruning throughput numbers
together.

---

## 8. Sources

- Holtzman et al., *The Curious Case of Neural Text Degeneration*, ICLR 2020 — [arXiv:1904.09751](https://arxiv.org/abs/1904.09751)
- Dettmers et al., *QLoRA*, NeurIPS 2023 — [arXiv:2305.14314](https://arxiv.org/abs/2305.14314)
- Dao et al., *FlashAttention*, NeurIPS 2022 — [arXiv:2205.14135](https://arxiv.org/abs/2205.14135)
- Robertson & Zaragoza, *BM25 and Beyond*, FnTIR 2009 — [DOI 10.1561/1500000019](https://doi.org/10.1561/1500000019)
- Cormack, Clarke & Büttcher, *Reciprocal Rank Fusion*, SIGIR 2009 — [DOI 10.1145/1571941.1572114](https://doi.org/10.1145/1571941.1572114)
- Karpukhin et al., *Dense Passage Retrieval*, EMNLP 2020 — [arXiv:2004.04906](https://arxiv.org/abs/2004.04906)
- Nogueira & Cho, *Passage Re-ranking with BERT* — [arXiv:1901.04085](https://arxiv.org/abs/1901.04085)
- Xiao et al., *C-Pack / BGE*, SIGIR 2024 — [arXiv:2309.07597](https://arxiv.org/abs/2309.07597)
- Wang et al., *Text Embeddings by Weakly-Supervised Contrastive Pre-training (E5)* — [arXiv:2212.03533](https://arxiv.org/abs/2212.03533)
- Li et al., *Towards General Text Embeddings (GTE)* — [arXiv:2308.03281](https://arxiv.org/abs/2308.03281)
- Muennighoff et al., *MTEB*, EACL 2023 — [arXiv:2210.07316](https://arxiv.org/abs/2210.07316)
- Thakur et al., *BEIR*, NeurIPS 2021 D&B — [arXiv:2104.08663](https://arxiv.org/abs/2104.08663)
- Wang et al., *Searching for Best Practices in RAG*, EMNLP 2024 — [ACL 2024.emnlp-main.981](https://aclanthology.org/2024.emnlp-main.981/) · [arXiv:2407.01219](https://arxiv.org/abs/2407.01219)
- Liu et al., *Lost in the Middle*, TACL 2024 — [arXiv:2307.03172](https://arxiv.org/abs/2307.03172)
- Douze et al., *The Faiss library* — [arXiv:2401.08281](https://arxiv.org/abs/2401.08281)
- Bergstra & Bengio, *Random Search for Hyper-Parameter Optimization*, JMLR 2012 — [JMLR v13](https://jmlr.org/papers/v13/bergstra12a.html)
- Akiba et al., *Optuna*, KDD 2019 — [arXiv:1907.10902](https://arxiv.org/abs/1907.10902)
- Smucker, Allan & Carterette, *Statistical Significance Tests for IR*, CIKM 2007 — [DOI 10.1145/1321440.1321528](https://doi.org/10.1145/1321440.1321528)
- Efron, *Bootstrap Methods*, Ann. Statist. 1979 — [DOI 10.1214/aos/1176344552](https://doi.org/10.1214/aos/1176344552)
