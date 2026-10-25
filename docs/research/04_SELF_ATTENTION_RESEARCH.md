# 04 — Self-Attention: Mechanism, Variants, and Its Role in KidsNutriBite

This report goes deeper on the mechanism summarised in `03_QWEN_ARCHITECTURE_RESEARCH.md` §5, and
connects it to two things this project actually cares about: **why a RAG prompt of 5 chunks is
affordable**, and **whether attention-based analysis could tell us anything useful about grounding**.

---

## 1. The Core Operation

### 1.1 Scaled dot-product attention

Given a sequence of `n` token representations `X ∈ R^{n × d_model}`:

```
Q = X W_Q + b_Q          (queries)
K = X W_K + b_K          (keys)
V = X W_V + b_V          (values)

Attention(Q, K, V) = softmax( (Q Kᵀ) / sqrt(d_head) + M ) V
```

where `M` is the causal mask (`0` where `j ≤ i`, `−∞` where `j > i`).

Vaswani et al., *Attention Is All You Need*, NeurIPS 2017 —
[arXiv:1706.03762](https://arxiv.org/abs/1706.03762).

**Why divide by `sqrt(d_head)`?** For random `q, k` with unit-variance components, the dot product
`q·k` has variance proportional to `d_head`. Without the scaling, at `d_head = 128` the logits would
have standard deviation ~11.3, pushing softmax into a near-one-hot regime where gradients vanish.
The scaling keeps the logit distribution in a usable range. This is stated explicitly in §3.2.1 of
the original paper.

**Why bias terms?** Qwen2/Qwen2.5 add biases `b_Q, b_K, b_V` on the QKV projections — a deliberate
departure from LLaMA, motivated in the Qwen2 technical report by improved length extrapolation
([arXiv:2407.10671](https://arxiv.org/abs/2407.10671)).

### 1.2 The intuition, in this project's terms

Attention is **content-based soft lookup**. For each position, the query asks *"which earlier
positions are relevant to me?"*, the keys answer, and the values carry the information that gets
mixed in.

This is worth stating carefully in our report, because there is a tempting but **false** analogy:

| | RAG retrieval | Self-attention |
|---|---|---|
| Query | one 384-dim BGE vector for the whole question | one 128-dim vector **per token per head** |
| Keys | 781 chunk vectors in FAISS | every previous token's key, recomputed at each layer |
| Selection | **hard** top-k = 5, discrete | **soft** softmax weights over all positions |
| Output | 5 text chunks | a weighted sum of value vectors |
| Learned? | frozen pretrained encoder | learned jointly with the LM |
| Happens | once, before generation | 28 layers × 28 heads × every token |

They are structurally analogous (both are query-key-value lookups) but operationally different:
retrieval is a **discrete, one-shot, external** selection over a corpus; attention is a
**continuous, repeated, internal** mixing over the context. Our report may draw the analogy — it is
pedagogically useful — but must not claim they are the same mechanism.

---

## 2. Multi-Head Attention

Instead of one attention with `d_model = 3584`, run `h = 28` heads each of `d_head = 128`, in
parallel, and concatenate:

```
head_i = Attention(X W_Q^i, X W_K^i, X W_V^i)
MHA(X)  = Concat(head_1, ..., head_28) W_O
```

Rationale (Vaswani §3.2.2): different heads can specialise in different relation types. There is
substantial interpretability evidence for this — e.g. Clark, Khandelwal, Levy & Manning,
*What Does BERT Look At? An Analysis of BERT's Attention*, BlackboxNLP 2019 —
[arXiv:1906.04341](https://arxiv.org/abs/1906.04341) — which finds heads that track syntactic
dependencies, coreference, and delimiters.

**Counter-evidence worth citing**, because it matters directly for `06_PRUNING_RESEARCH.md`:
Michel, Levy & Neubig, *Are Sixteen Heads Really Better than One?*, NeurIPS 2019 —
[arXiv:1905.10650](https://arxiv.org/abs/1905.10650) — a large fraction of heads can be removed at
test time with limited degradation. Also Voita et al., *Analyzing Multi-Head Self-Attention*,
ACL 2019 — [arXiv:1905.09418](https://arxiv.org/abs/1905.09418) — only a small subset of heads
carry specialised, important roles.

So "28 heads each learning something distinct" is an oversimplification: many heads are redundant.
That is precisely what head pruning exploits.

---

## 3. Causal Masking

Decoder-only LMs mask future positions:

```
        j=0   j=1   j=2   j=3
 i=0  [  .    -inf  -inf  -inf ]
 i=1  [  .     .    -inf  -inf ]
 i=2  [  .     .     .    -inf ]
 i=3  [  .     .     .     .   ]
```

Two consequences for us:

1. **The KV cache is valid.** Because token `i`'s key/value never depends on tokens after it, past
   K,V are immutable and reusable. Without causality there would be no cache and no efficient
   autoregressive decoding.
2. **Prompt order matters.** Later tokens see earlier ones, not vice versa. In
   `llm/prompt_templates.py` the ordering is: system prompt → question → profile → planner output →
   **RAG chunks last** → instruction tail. So the final instruction and the retrieved evidence are
   closest to the generation point. Whether that ordering is optimal is an **empirically testable
   question**, and a relevant one: Liu et al., *Lost in the Middle: How Language Models Use Long
   Contexts*, TACL 2024 — [arXiv:2307.03172](https://arxiv.org/abs/2307.03172) — shows models attend
   most reliably to the **beginning and end** of the context and degrade for information in the
   middle. See §7 for the experiment this suggests.

---

## 4. Grouped-Query Attention in Qwen2.5-7B

### 4.1 The spectrum

| Variant | Q heads | KV heads | KV cache | Quality |
|---|---|---|---|---|
| **MHA** (Vaswani 2017) | 28 | 28 | 1× (largest) | baseline |
| **GQA** (Ainslie 2023) | 28 | **4** | **1/7×** | near-MHA |
| **MQA** (Shazeer 2019) | 28 | 1 | 1/28× | measurable degradation |

- MQA: Shazeer, *Fast Transformer Decoding: One Write-Head is All You Need* —
  [arXiv:1911.02150](https://arxiv.org/abs/1911.02150)
- GQA: Ainslie, Lee-Thorp, de Jong, Zemlyanskiy, Lebrón & Sanghai, *GQA: Training Generalized
  Multi-Query Transformer Models from Multi-Head Checkpoints*, EMNLP 2023 —
  [arXiv:2305.13245](https://arxiv.org/abs/2305.13245),
  [ACL 2023.emnlp-main.298](https://aclanthology.org/2023.emnlp-main.298/)

GQA's contribution is twofold: the interpolation itself, and an **uptraining** recipe that converts
an existing MHA checkpoint to GQA using a small fraction of the original pretraining compute — which
is why GQA was adopted so widely so quickly.

### 4.2 Concretely in Qwen2.5-7B

```
28 query heads, 4 KV heads, d_head = 128
-> query heads 0-6   share KV head 0
   query heads 7-13  share KV head 1
   query heads 14-20 share KV head 2
   query heads 21-27 share KV head 3
```

Each KV head is broadcast to its 7 query heads. Attention output is still computed per query head,
so the model retains 28 distinct "views" — only the keys and values are shared.

### 4.3 Why this matters for *this* project specifically

Decode is **memory-bandwidth-bound**: at each step the GPU must read the entire KV cache. Reducing
the cache 7× reduces that traffic ~7×. For a RAG system whose prompts are long *by design* — five
retrieved chunks plus a full diet-plan JSON — this is the difference between a workable and an
unworkable prompt budget on free-tier hardware.

KV cache arithmetic (fp16, from `03` §7):

```
per token = 2 × 28 layers × 4 kv_heads × 128 d_head × 2 bytes = 57,344 B ≈ 56 KiB
```

| Our prompt regime | KV cache (GQA) | KV cache (hypothetical MHA) |
|---|---|---|
| ~1,500 prompt tokens | ~82 MiB | ~574 MiB |
| ~2,500 prompt + generated | ~137 MiB | ~958 MiB |

Note the cache is **fp16 even under 4-bit weight quantisation** — `load_in_4bit` does not quantise
the KV cache.

---

## 5. Rotary Position Embeddings

### 5.1 Mechanism
RoPE rotates each 2-dimensional sub-pair of `q` and `k` by an angle proportional to its absolute
position:

```
for pair index m (0 ≤ m < d_head/2):
    θ_m = base^(-2m / d_head)          # base = rope_theta = 1,000,000
    rotate (q_{2m}, q_{2m+1}) by (position · θ_m)
```

The key algebraic property: after rotation, the dot product `q_i · k_j` depends only on `(i − j)`.
Absolute positions are injected, but the attention score is **relative** — which is why RoPE
generalises better across lengths than learned absolute position embeddings.

Su, Lu, Pan, Murtadha, Wen & Liu, *RoFormer: Enhanced Transformer with Rotary Position Embedding* —
[arXiv:2104.09864](https://arxiv.org/abs/2104.09864); *Neurocomputing* vol. 568, p. 127063, 2024 —
[DOI 10.1016/j.neucom.2023.127063](https://doi.org/10.1016/j.neucom.2023.127063).

### 5.2 Why `rope_theta = 1,000,000`?
The original RoPE used base 10,000. A larger base lengthens the wavelengths of the low-frequency
components, so positions far apart stay distinguishable rather than aliasing — the standard route to
long context. Related: Chen et al., *Extending Context Window of LLMs via Positional Interpolation* —
[arXiv:2306.15595](https://arxiv.org/abs/2306.15595); Peng et al., *YaRN* —
[arXiv:2309.00071](https://arxiv.org/abs/2309.00071).

### 5.3 In KidsNutriBite
Our prompts are ~1–2k tokens against a 32,768-token trained context. We operate deep inside the
comfortable regime; RoPE extrapolation is **not** a limiting factor for us. This is worth stating in
the paper as a *non*-issue, so that a reviewer does not assume long-context degradation is confounding
our results.

---

## 6. Computational Complexity and Efficient Attention

| Phase | Attention cost | Bound by |
|---|---|---|
| Prefill (n prompt tokens) | `O(n² · d)` | compute |
| Decode (per token, cache length n) | `O(n · d)` | memory bandwidth |

The quadratic prefill term is why long prompts get expensive — but at n ≈ 1,500 it is not our
bottleneck; 1,024 sequential decode steps are.

Relevant efficiency work. **Hardware requirements are noted as implementation considerations, not as
reasons to exclude a method from the research space.**

- **FlashAttention** `🔬 RESEARCH CANDIDATE` `🖥️` — Dao, Fu, Ermon, Rudra & Ré, NeurIPS 2022 —
  [arXiv:2205.14135](https://arxiv.org/abs/2205.14135); FlashAttention-2 —
  [arXiv:2307.08691](https://arxiv.org/abs/2307.08691); FlashAttention-3 (Hopper) —
  [arXiv:2407.08608](https://arxiv.org/abs/2407.08608). An **exact** IO-aware attention algorithm
  that tiles computation to avoid materialising the `n × n` matrix. **Not an approximation — zero
  quality cost**, so it can never confound a quality result. Usable via
  `attn_implementation="flash_attention_2"`. *Implementation consideration:* requires **Ampere or
  newer**; on a Turing T4 the equivalent-quality option is PyTorch SDPA (`"sdpa"`).
  **NOT VERIFIED FROM CODE** — `llm/llm_client.py` does not set `attn_implementation`, so whichever
  default `transformers` selects is in force. **This should be pinned explicitly for reproducibility
  regardless of which backend is chosen.**
- **PagedAttention / vLLM** `🔬` — Kwon et al., SOSP 2023 —
  [arXiv:2309.06180](https://arxiv.org/abs/2309.06180). KV-cache memory management for serving.
  **High value for us**: batching the 41-case benchmark through vLLM would cut sweep wall-clock time
  substantially, and `05` lists ~16 experiments each requiring a full pass.
- **Linear / approximate attention** `🔮 POTENTIAL FUTURE WORK` — Performer
  ([arXiv:2009.14794](https://arxiv.org/abs/2009.14794)), Linformer
  ([arXiv:2006.04768](https://arxiv.org/abs/2006.04768)), Longformer
  ([arXiv:2004.05150](https://arxiv.org/abs/2004.05150)). **Retained in the research space with the
  reason for deprioritisation recorded:** these require architectural change and retraining, and
  their asymptotic benefit appears at long sequence lengths, whereas our prompts are ~1–2k tokens
  against a 32,768 window. The rejection is on **task fit (sequence length), not on hardware** — and
  it would change if NutriBite ever moved to long multi-turn histories or whole-document contexts.
- **Speculative decoding** `🔬 RESEARCH CANDIDATE — not developed here` — Leviathan, Kalman & Matias,
  ICML 2023 — [arXiv:2211.17192](https://arxiv.org/abs/2211.17192); Chen et al. —
  [arXiv:2302.01318](https://arxiv.org/abs/2302.01318). A small draft model proposes tokens that the
  7B verifies in parallel. **Directly attacks our actual bottleneck** — 1,024 sequential decode
  steps — and is **lossless** (output distribution preserved). Arguably a better latency intervention
  than pruning, and it is not covered elsewhere in these reports. Worth a dedicated look.

**Practical recommendation:** batching the evaluation set through vLLM is a legitimate engineering
improvement, but it changes the inference stack — so any results produced under it must not be mixed
with results produced under `transformers.pipeline` without re-running the baseline.

---

## 7. Can Attention Tell Us Anything About Grounding?

This is the question most relevant to KidsNutriBite's actual research goal, and it deserves a careful
rather than an enthusiastic answer.

### 7.1 The tempting idea
Our prompt marks each retrieved chunk with `[ID: {id}, Relevance Score: {score}]`. One could compute,
for each generated token, how much attention mass falls on each chunk's token span, and produce an
**attention-based attribution**: "this sentence was generated while attending mostly to chunk
`RAG_0231`." That would be a cheap, automatic grounding signal — potentially a complement to the
LLM judge.

### 7.2 Why this is not sound as an explanation
There is a substantial literature arguing attention weights are **not** reliable explanations:
- Jain & Wallace, *Attention is not Explanation*, NAACL 2019 —
  [arXiv:1902.10186](https://arxiv.org/abs/1902.10186) — attention weights correlate poorly with
  gradient-based importance, and alternative attention distributions can yield identical predictions.
- Wiegreffe & Pinter, *Attention is not not Explanation*, EMNLP 2019 —
  [arXiv:1908.04626](https://arxiv.org/abs/1908.04626) — a rebuttal: attention *can* be meaningful
  depending on what claim is made and how it is tested.
- Serrano & Smith, *Is Attention Interpretable?*, ACL 2019 —
  [arXiv:1906.03731](https://arxiv.org/abs/1906.03731) — attention magnitude is an unreliable
  indicator of importance.

There is also the mechanical problem of **attention sinks**: a large fraction of attention mass
concentrates on the first token(s) regardless of content — Xiao et al., *Efficient Streaming Language
Models with Attention Sinks*, ICLR 2024 — [arXiv:2309.17453](https://arxiv.org/abs/2309.17453). Any
naive per-chunk attention-mass computation would be dominated by this artefact and would need
explicit correction.

### 7.3 Honest position for this project
**Attention-based grounding attribution should be framed as exploratory analysis, never as a
validated metric, and never as a replacement for the LLM judge.** If pursued, it must be *validated
against* the existing human/LLM faithfulness labels, and the null result — "attention attribution
does not agree with judged faithfulness" — must be reportable.

A more defensible alternative with the same goal: **leave-one-out context ablation**. Remove chunk
`c` from the prompt, regenerate, and measure how much the answer changes. This is causal rather than
correlational and needs no attention introspection — but it costs `k` extra generations per query
(5× our current generation cost on 41 cases ≈ 205 extra generations). That is affordable on a Groq
backend, expensive on local Qwen.

### 7.4 Proposed experiment A1 — context position sensitivity
Directly motivated by *Lost in the Middle* ([arXiv:2307.03172](https://arxiv.org/abs/2307.03172))
and testable with **no code changes to the retrieval stack** — only prompt-assembly order:

- **A:** chunks in current relevance order (best first) — today's behaviour.
- **B:** reversed order (best last, closest to the generation point).
- **C:** best chunk first *and* a restated instruction after the chunks.
- **Metrics:** Faithfulness, Answer Relevancy, Hallucination Rate (existing judges).
- **Why it is worth running:** it is one of the cheapest possible interventions — a reordering of
  strings — and the literature gives a specific reason to expect an effect.
- **Caveat:** at n = 41 with a deliberately permissive grounding judge, only a large effect would be
  detectable. Report bootstrap CIs and frame as exploratory.

---

## 8. Summary: Attention Concepts Mapped to KidsNutriBite

| Concept | Qwen2.5-7B value | Consequence for this project |
|---|---|---|
| Scaled dot-product attention | `d_head = 128`, scale `1/√128` | The core mechanism; no project-specific tuning |
| Multi-head | 28 heads | Many are redundant (Michel 2019) → head pruning is plausible (`06`) |
| QKV bias | present | Qwen-specific detail; get it right in the architecture description |
| Causal masking | yes | Enables the KV cache; makes **prompt ordering** consequential (§7.4) |
| GQA | 28 Q / 4 KV = 7:1 | **7× smaller KV cache** → long RAG prompts affordable on a T4 |
| RoPE | θ = 1e6, 32,768 ctx | We use ~1–2k tokens → long-context degradation is **not** a confound |
| Prefill vs decode | O(n²) vs O(n) | 1,024 decode steps dominate latency, not our ~1.5k prompt |
| FlashAttention | exact, Ampere+ | Zero quality cost; pin `sdpa` on T4, `flash_attention_2` on rented Ampere |
| Speculative decoding | lossless | **Attacks our real bottleneck**; under-explored here |
| Attention as explanation | — | **Not a valid grounding metric**; prefer causal ablation |

---

## 9. Sources

- Vaswani et al., *Attention Is All You Need*, NeurIPS 2017 — [arXiv:1706.03762](https://arxiv.org/abs/1706.03762)
- Ainslie et al., *GQA*, EMNLP 2023 — [arXiv:2305.13245](https://arxiv.org/abs/2305.13245) · [ACL 2023.emnlp-main.298](https://aclanthology.org/2023.emnlp-main.298/)
- Shazeer, *Fast Transformer Decoding* (MQA) — [arXiv:1911.02150](https://arxiv.org/abs/1911.02150)
- Su et al., *RoFormer / RoPE* — [arXiv:2104.09864](https://arxiv.org/abs/2104.09864) · [DOI 10.1016/j.neucom.2023.127063](https://doi.org/10.1016/j.neucom.2023.127063)
- Chen et al., *Positional Interpolation* — [arXiv:2306.15595](https://arxiv.org/abs/2306.15595)
- Peng et al., *YaRN* — [arXiv:2309.00071](https://arxiv.org/abs/2309.00071)
- Dao et al., *FlashAttention*, NeurIPS 2022 — [arXiv:2205.14135](https://arxiv.org/abs/2205.14135); *FlashAttention-2* — [arXiv:2307.08691](https://arxiv.org/abs/2307.08691); *FlashAttention-3* — [arXiv:2407.08608](https://arxiv.org/abs/2407.08608)
- Kwon et al., *PagedAttention / vLLM*, SOSP 2023 — [arXiv:2309.06180](https://arxiv.org/abs/2309.06180)
- Leviathan, Kalman & Matias, *Fast Inference via Speculative Decoding*, ICML 2023 — [arXiv:2211.17192](https://arxiv.org/abs/2211.17192); Chen et al. — [arXiv:2302.01318](https://arxiv.org/abs/2302.01318)
- Choromanski et al., *Performer* — [arXiv:2009.14794](https://arxiv.org/abs/2009.14794); Wang et al., *Linformer* — [arXiv:2006.04768](https://arxiv.org/abs/2006.04768); Beltagy et al., *Longformer* — [arXiv:2004.05150](https://arxiv.org/abs/2004.05150)
- Michel, Levy & Neubig, *Are Sixteen Heads Really Better than One?*, NeurIPS 2019 — [arXiv:1905.10650](https://arxiv.org/abs/1905.10650)
- Voita et al., *Analyzing Multi-Head Self-Attention*, ACL 2019 — [arXiv:1905.09418](https://arxiv.org/abs/1905.09418)
- Clark et al., *What Does BERT Look At?*, BlackboxNLP 2019 — [arXiv:1906.04341](https://arxiv.org/abs/1906.04341)
- Jain & Wallace, *Attention is not Explanation*, NAACL 2019 — [arXiv:1902.10186](https://arxiv.org/abs/1902.10186)
- Wiegreffe & Pinter, *Attention is not not Explanation*, EMNLP 2019 — [arXiv:1908.04626](https://arxiv.org/abs/1908.04626)
- Serrano & Smith, *Is Attention Interpretable?*, ACL 2019 — [arXiv:1906.03731](https://arxiv.org/abs/1906.03731)
- Xiao et al., *Attention Sinks / StreamingLLM*, ICLR 2024 — [arXiv:2309.17453](https://arxiv.org/abs/2309.17453)
- Liu et al., *Lost in the Middle*, TACL 2024 — [arXiv:2307.03172](https://arxiv.org/abs/2307.03172)
- Qwen Team, *Qwen2 Technical Report* — [arXiv:2407.10671](https://arxiv.org/abs/2407.10671)
