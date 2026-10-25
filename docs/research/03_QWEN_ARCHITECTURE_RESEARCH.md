# 03 — Qwen2.5-7B-Instruct Architecture, Related to Our Implementation

**Scope:** tokenizer → embeddings → transformer blocks → self-attention → feed-forward network →
KV cache → autoregressive generation. Every section ends with **"In KidsNutriBite"**, tying the
concept to verified code in this repository.

Self-attention gets a dedicated deep-dive in `04_SELF_ATTENTION_RESEARCH.md`; §5 here is the
architectural summary only.

---

## 0. Ground Truth: The Actual Configuration

All values below were fetched directly from the official model configuration at
[huggingface.co/Qwen/Qwen2.5-7B-Instruct/blob/main/config.json](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct/blob/main/config.json),
not inferred.

| Field | Value | Meaning |
|---|---|---|
| `hidden_size` | **3584** | model dimension `d_model` |
| `num_hidden_layers` | **28** | transformer blocks |
| `num_attention_heads` | **28** | query heads |
| `num_key_value_heads` | **4** | KV heads → **GQA ratio 7:1** |
| `intermediate_size` | **18944** | FFN inner width |
| `max_position_embeddings` | **32768** | context length |
| `vocab_size` | **152064** | tokenizer vocabulary |
| `rope_theta` | **1000000.0** | RoPE base frequency |
| `rms_norm_eps` | **1e-06** | RMSNorm epsilon |
| `hidden_act` | **"silu"** | SwiGLU activation |
| `sliding_window` | **131072** | (larger than context → effectively inactive) |
| `tie_word_embeddings` | **false** | separate input/output embedding matrices |
| `torch_dtype` | **bfloat16** | released precision |

Primary reference: Qwen Team, *Qwen2.5 Technical Report* —
[arXiv:2412.15115](https://arxiv.org/abs/2412.15115). Predecessor: *Qwen2 Technical Report* —
[arXiv:2407.10671](https://arxiv.org/abs/2407.10671). Docs:
[qwen.readthedocs.io](https://qwen.readthedocs.io/en/latest/).

Head dimension follows: `d_head = 3584 / 28 = 128`.

**In KidsNutriBite:** `llm/llm_client.py` loads exactly `Qwen/Qwen2.5-7B-Instruct` through
`transformers.pipeline`, so every number above is the architecture actually running in our
experiments. The only deviation is numeric precision: we load **4-bit NF4** weights with **fp16
compute**, not bfloat16 (§9).

---

## 1. Tokenizer

### Concept
Qwen2.5 uses **byte-level BPE** (Sennrich, Haddow & Birch, *Neural Machine Translation of Rare Words
with Subword Units*, ACL 2016 — [arXiv:1508.07909](https://arxiv.org/abs/1508.07909); byte-level
variant from GPT-2, Radford et al., 2019 —
[paper](https://cdn.openai.com/better-language-models/language_models_are_unsupervised_multitask_learners.pdf)).

Byte-level means **no out-of-vocabulary token is possible** — any byte sequence is representable.
Vocabulary: **152,064** entries (including special/control tokens), notably large, which improves
multilingual and code coverage at the cost of a bigger embedding matrix.

Instruction models apply a **ChatML-style** chat template that wraps turns in
`<|im_start|>role ... <|im_end|>` markers ([Qwen docs](https://qwen.readthedocs.io/en/latest/)).

### In KidsNutriBite
Three consequences that matter for us:

1. **Our system+user prompt is converted by the chat template**, so the model receives role markers
   around `SYSTEM_PROMPT` and `user_content` from `llm/prompt_templates.py`. Using
   `transformers.pipeline` with a chat-formatted input applies this automatically.
2. **Indian food terms tokenize inefficiently.** "ragi", "khichdi", "poha", "sattu", "katori" are
   almost certainly not single tokens; they fragment into several subwords. **NOT VERIFIED FROM CODE**
   — I did not run the tokenizer to count. This is easy to measure and worth measuring, because it
   affects both prompt length and the model's handling of these terms.
3. **Our chunk IDs are token-expensive.** Every retrieved chunk is rendered as
   `- [ID: {id}, Relevance Score: {score}] {text}`. Identifiers and float scores tokenize poorly
   (digits often split individually). With 5 chunks per prompt this is a small but real overhead;
   the benefit is that it enables citation-style grounding checks, which is worth the cost.

---

## 2. Embeddings

### Concept
A learned matrix `E ∈ R^{152064 × 3584}` maps token IDs to vectors. Because
`tie_word_embeddings = false`, the output projection (`lm_head`) is a **separate** matrix of the same
shape rather than `Eᵀ`.

Parameter cost of this choice:
```
152064 × 3584 = 545,077,760 parameters per matrix
two untied matrices ≈ 1.09 B parameters ≈ 15.6% of the 7B total
```
That is a striking fraction — a consequence of the large vocabulary. It is directly relevant to the
pruning discussion (`06_PRUNING_RESEARCH.md`): embedding/`lm_head` matrices are a large,
often-overlooked share of the parameter budget, and they are usually *excluded* from pruning
because damaging them degrades the model badly.

**There are no learned positional embeddings.** Position is injected inside attention via RoPE (§5.3),
so no `max_position_embeddings × hidden_size` position table exists.

### In KidsNutriBite
Do not confuse these with our **retrieval** embeddings. Two entirely separate embedding spaces exist
in this system, and conflating them in a report would be a visible error:

| | Retrieval embeddings | Qwen embeddings |
|---|---|---|
| Model | `BAAI/bge-small-en-v1.5` | Qwen2.5-7B-Instruct |
| Dimension | **384** | **3584** |
| Purpose | Sentence-level semantic similarity for FAISS | Token-level input to the LM |
| Unit | one vector per chunk | one vector per token |
| Trained for | contrastive retrieval | next-token prediction |
| Where | `rag/indexer.py`, `faiss.index` | inside the LLM |

They never interact. FAISS finds the text; Qwen then re-tokenizes and re-embeds that text in its own
space.

---

## 3. The Transformer Block

Qwen2.5 uses a **pre-normalisation decoder-only** block, repeated 28 times:

```
x -> RMSNorm -> Self-Attention (GQA + RoPE) -> + residual -> h
h -> RMSNorm -> SwiGLU FFN                  -> + residual -> out
```

Base architecture: Vaswani et al., *Attention Is All You Need*, NeurIPS 2017 —
[arXiv:1706.03762](https://arxiv.org/abs/1706.03762). Decoder-only LM formulation: Radford et al.
(GPT-2, above). Pre-norm placement: Xiong et al., *On Layer Normalization in the Transformer
Architecture*, ICML 2020 — [arXiv:2002.04745](https://arxiv.org/abs/2002.04745) — pre-norm removes
the need for learning-rate warmup and stabilises deep stacks.

### 3.1 RMSNorm
```
RMSNorm(x) = x / sqrt(mean(x²) + ε) · g        with ε = 1e-6, learnable gain g
```
Zhang & Sennrich, *Root Mean Square Layer Normalization*, NeurIPS 2019 —
[arXiv:1910.07467](https://arxiv.org/abs/1910.07467). Cheaper than LayerNorm: no mean subtraction and
no bias term.

### 3.2 Residual connections
He et al., *Deep Residual Learning*, CVPR 2016 — [arXiv:1512.03385](https://arxiv.org/abs/1512.03385).
The residual stream is what makes **layer pruning** plausible at all (`06` §4): removing a block
leaves `x -> x`, an identity path, rather than breaking the network.

### In KidsNutriBite
28 blocks is our **latency multiplier**. Every generated token runs all 28 blocks. With
`max_new_tokens = 1024`, a maximal answer costs up to `1024 × 28` block executions sequentially. This
is why decode speed, not prompt length, dominates our end-to-end time — and why
`max_new_tokens` is the single most consequential inference hyperparameter for latency
(`05_HYPERPARAMETER_OPTIMIZATION_RESEARCH.md` §2).

---

## 4. Feed-Forward Network (SwiGLU)

### Concept
```
FFN(x) = W_down( SiLU(W_gate x) ⊙ W_up x )
```
with `W_gate, W_up ∈ R^{3584 → 18944}` and `W_down ∈ R^{18944 → 3584}`.

- SiLU / Swish: Elfwing, Uchibe & Doya — [arXiv:1702.03118](https://arxiv.org/abs/1702.03118);
  Ramachandran, Zoph & Le, *Searching for Activation Functions* —
  [arXiv:1710.05941](https://arxiv.org/abs/1710.05941).
- Gated variant: Shazeer, *GLU Variants Improve Transformer* —
  [arXiv:2002.05202](https://arxiv.org/abs/2002.05202). Confirmed for Qwen2.5 in the technical report
  ([arXiv:2412.15115](https://arxiv.org/abs/2412.15115)).

**Three** matrices, not two — this is the defining feature of a gated FFN and a frequent source of
error in write-ups.

Parameter count per layer:
```
3 × 3584 × 18944 = 203,685,888 params
× 28 layers      ≈ 5.70 B params
```
So the FFN stack is roughly **~81% of the 7.6 B total parameters**. Attention projections and
embeddings make up the rest.

### In KidsNutriBite
This is the **single most important number for the pruning report**. If ~81% of parameters live in
the FFN, then:
- FFN width pruning is where structured pruning must act to matter (`06` §3);
- and it also explains why **4-bit quantisation** is so effective for us: compressing the dominant
  weight mass 4× is what lets a 7B model fit in the ~15 GB of a Kaggle T4/P100.

Ratio check: `18944 / 3584 ≈ 5.29×`, wider than the classic 4× of the original transformer — typical
for gated FFNs, where the 3-matrix structure is compensated by a different width ratio.

---

## 5. Self-Attention (Architectural Summary)

Full treatment in `04_SELF_ATTENTION_RESEARCH.md`. The architecturally distinctive points:

### 5.1 Grouped-Query Attention
28 query heads share **4** KV heads → each KV head serves **7** query heads.

Ainslie et al., *GQA: Training Generalized Multi-Query Transformer Models from Multi-Head
Checkpoints*, EMNLP 2023 — [arXiv:2305.13245](https://arxiv.org/abs/2305.13245),
[ACL 2023.emnlp-main.298](https://aclanthology.org/2023.emnlp-main.298/). Precursor: Shazeer,
*Fast Transformer Decoding: One Write-Head is All You Need* (MQA) —
[arXiv:1911.02150](https://arxiv.org/abs/1911.02150).

The benefit is entirely about the **KV cache**, quantified in §7.

### 5.2 Causal masking
Position `i` attends only to `j ≤ i`. This is what makes the KV cache valid: past keys/values never
change, so they can be stored and reused.

### 5.3 RoPE
Rotary position embedding rotates query and key vectors by a position-dependent angle, so the
attention score depends on **relative** position `(i − j)`.

Su et al., *RoFormer: Enhanced Transformer with Rotary Position Embedding* —
[arXiv:2104.09864](https://arxiv.org/abs/2104.09864); published in *Neurocomputing* vol. 568,
p. 127063, 2024 — [DOI 10.1016/j.neucom.2023.127063](https://doi.org/10.1016/j.neucom.2023.127063).

`rope_theta = 1,000,000` — far above the original 10,000. A larger base stretches the wavelength
spectrum so that distant positions remain distinguishable, which is the standard mechanism for
supporting long contexts (cf. "NTK-aware"/base-scaling approaches; Chen et al., *Extending Context
Window of LLMs via Positional Interpolation* — [arXiv:2306.15595](https://arxiv.org/abs/2306.15595)).

### 5.4 Attention bias
Qwen2 and Qwen2.5 apply **bias terms on the Q, K, V projections** (a deliberate deviation from LLaMA,
noted in the Qwen2 technical report — [arXiv:2407.10671](https://arxiv.org/abs/2407.10671)) to
improve extrapolation. Minor parameter cost, but worth getting right in an architecture description.

### In KidsNutriBite
GQA is the reason a 7B model is viable on our hardware **at long prompts**. Our prompts carry 5
retrieved chunks plus a full diet-plan JSON; without GQA the cache for that prefix would be 7× larger
(§7).

---

## 6. Autoregressive Generation

### Concept
The model factorises `P(x₁..x_T) = Π P(x_t | x_<t)` and generates one token at a time. Two distinct
phases:

| Phase | What happens | Compute profile |
|---|---|---|
| **Prefill** | The whole prompt is processed in one parallel forward pass; K,V for every prompt token are computed and cached | **Compute-bound**, highly parallel, O(n²) attention |
| **Decode** | One token at a time; each step attends over the cache | **Memory-bandwidth-bound**, sequential, one token per full 28-layer pass |

This asymmetry is the central fact of LLM inference performance and is documented in the vLLM /
PagedAttention work: Kwon et al., *Efficient Memory Management for LLM Serving with PagedAttention*,
SOSP 2023 — [arXiv:2309.06180](https://arxiv.org/abs/2309.06180).

### Sampling
- **Temperature** rescales logits before softmax; `T → 0` approaches greedy decoding.
- **Top-p (nucleus) sampling**: sample from the smallest set whose cumulative probability ≥ p.
  Holtzman, Buys, Du, Forbes & Choi, *The Curious Case of Neural Text Degeneration*, ICLR 2020 —
  [arXiv:1904.09751](https://arxiv.org/abs/1904.09751).

### In KidsNutriBite
Our settings (`llm/llm_client.py`): `temperature = 0.1`, `top_p = 0.9`, `max_new_tokens = 1024`.

- `temperature = 0.1` is **near-greedy**. This is the right choice for a grounded, safety-sensitive
  nutrition assistant: we want the answer that best follows the retrieved context, not a creative one.
  It also *reduces* (but does not eliminate) run-to-run variance in evaluation.
- **Important nuance for the evaluation write-up:** temperature 0.1 is **not** deterministic.
  Sampling still occurs. Reported metrics therefore carry generation variance on top of judge
  variance and the n=41 sampling variance. If exact reproducibility is wanted,
  `do_sample=False` (greedy) is the correct setting — and switching to it is a legitimate,
  defensible methodological improvement to propose.
- At `T = 0.1`, `top_p = 0.9` is nearly inert: the temperature has already collapsed the distribution
  onto a few tokens, so the nucleus rarely binds. It is not wrong, just largely redundant. Worth
  stating rather than presenting top-p as an active control.
- `max_new_tokens = 1024` is a **hard truncation**, not a target. Our diet-mode prompt asks for a
  4-section response including a full meal walkthrough; if a response is cut mid-sentence, the
  grounding judge sees a truncated answer and Faithfulness is measured on incomplete text. **Whether
  truncation actually occurs on our 49 cases is NOT VERIFIED** — it is directly checkable by looking
  for `finish_reason`/length at the cap in the saved answer CSVs, and it should be checked before the
  results are written up.

---

## 7. KV Cache

### Concept
During decode, past keys and values are reused rather than recomputed. Size:

```
bytes = 2 (K and V) × layers × kv_heads × d_head × seq_len × bytes_per_element
```

For Qwen2.5-7B at fp16 (2 bytes):
```
2 × 28 × 4 × 128 × seq_len × 2  =  57,344 bytes per token  ≈ 56 KiB/token
```

**Without GQA** (i.e. if all 28 heads had their own KV):
```
2 × 28 × 28 × 128 × 2 = 401,408 bytes per token ≈ 392 KiB/token
```

**GQA saves exactly 7× on KV cache memory.** Concretely:

| Sequence length | KV cache with GQA (4 KV heads) | Hypothetical MHA (28 KV heads) |
|---|---|---|
| 1,000 tokens | ~55 MiB | ~383 MiB |
| 4,000 tokens | ~219 MiB | ~1.5 GiB |
| 32,768 tokens (max) | ~1.75 GiB | ~12.25 GiB |

### In KidsNutriBite
Estimated prompt size for our diet-mode path:
- `SYSTEM_PROMPT` ≈ 350–450 tokens
- Child profile block ≈ 60–80 tokens
- Diet planner output (targets + 4 meals with per-item nutrients) ≈ 300–600 tokens
- 5 RAG chunks: parents average ~134 chars, max 567 → ≈ 40–170 tokens each → ≈ 200–850 tokens
- Instruction tail ≈ 40 tokens

**Total ≈ 1,000–2,000 prompt tokens**, plus up to 1,024 generated → roughly **2,000–3,000 tokens**
of KV cache in the worst case. **NOT VERIFIED FROM CODE** — these are estimates from character
counts at a conventional ~4 chars/token, not measured token counts.

Two conclusions follow, both actionable:

1. **KV cache is not our bottleneck.** ~3,000 tokens × 56 KiB ≈ **165 MiB**. Negligible against the
   ~4.5 GB of 4-bit weights. Model weights dominate memory; the cache does not.
2. **We are using under 10% of a 32,768-token context window.** There is very large headroom. This
   directly justifies experimenting with larger `top_k` (5 → 10 → 15) in
   `05_HYPERPARAMETER_OPTIMIZATION_RESEARCH.md` §3: context capacity is not the constraint, so the
   only question is whether more chunks help or dilute. That is an empirical question we can afford
   to ask.

---

## 8. Putting It Together: One Query Through Qwen

```
Retrieved 5 parent chunks + planner JSON + profile
        |
        v
[chat template]  <|im_start|>system {SYSTEM_PROMPT}<|im_end|>
                 <|im_start|>user   {user_content}<|im_end|>
                 <|im_start|>assistant
        |
        v
[byte-level BPE]  ~1,000-2,000 token IDs
        |
        v
[embedding]  152064 x 3584 lookup  ->  [n, 3584]
        |
        v
+-------- 28 x transformer block --------------------------+
|  RMSNorm -> GQA attention (28 Q heads / 4 KV heads,       |
|             RoPE theta=1e6, causal mask) -> + residual    |
|  RMSNorm -> SwiGLU FFN (3584 -> 18944 -> 3584) -> + res   |
+-----------------------------------------------------------+
        |
        v  (PREFILL: all tokens in parallel; K,V cached)
[final RMSNorm] -> [lm_head 3584 x 152064] -> logits
        |
        v
[T=0.1, top_p=0.9] -> sample token 1
        |
        v  (DECODE: repeat up to 1024 times, 1 token per pass,
        |   attending over the growing KV cache)
        v
Answer text + latency  ->  evaluation judges
```

---

## 9. Our 4-Bit Quantisation, Precisely

`llm/llm_client.py` uses:

```python
BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_use_double_quant=True,
    bnb_4bit_compute_dtype=torch.float16,
)
```

- **NF4** (4-bit NormalFloat) is an information-theoretically optimal data type for
  normally-distributed weights; **double quantisation** additionally quantises the quantisation
  constants. Both introduced in QLoRA — Dettmers, Pagnoni, Holtzman & Zettlemoyer, NeurIPS 2023 —
  [arXiv:2305.14314](https://arxiv.org/abs/2305.14314). Library:
  [bitsandbytes](https://github.com/bitsandbytes-foundation/bitsandbytes).
- Related prior work on 8-bit inference: Dettmers et al., *LLM.int8()*, NeurIPS 2022 —
  [arXiv:2208.07339](https://arxiv.org/abs/2208.07339).

**What is and is not quantised:**

| Component | Precision |
|---|---|
| Linear layer weights (attention projections, FFN) | **4-bit NF4** |
| Compute / activations | **fp16** (dequantised per-op) |
| **KV cache** | **fp16 — not quantised** |
| LayerNorm/RMSNorm gains, biases | fp16 |

This is a point frequently got wrong in student reports: `load_in_4bit` does **not** shrink the KV
cache. Our §7 estimate correctly uses fp16 for the cache.

Approximate memory:
```
7.6 B params × 0.5 bytes (4-bit)          ≈ 3.8 GB
+ double-quant constants + fp16 buffers   ≈ 4.0-4.5 GB
+ KV cache at ~3k tokens                  ≈ 0.16 GB
------------------------------------------------------
                                          ≈ 4.2-4.7 GB
```
Comfortably inside a 15–16 GB T4/P100, which is what makes this project runnable on free-tier
notebooks at all.

**Caveats to state honestly:**
- 4-bit quantisation is **lossy**. Our Faithfulness / Hallucination numbers are measured on a
  quantised model and are not necessarily what bf16 Qwen2.5-7B would produce. We have not run a
  bf16 comparison, so **the size of that gap is unknown for this system**.
- On a T4 (Turing, compute capability 7.5), fp16 compute is well supported but bf16 is not natively;
  the `float16` compute dtype in our config is therefore the correct choice for that hardware.

---

## 10. Concept-to-Code Map

| Qwen concept | Value | Where it shows up in KidsNutriBite |
|---|---|---|
| Byte-level BPE, vocab 152064 | — | Chat template wraps our two prompt templates |
| Embedding 3584-dim | 3584 | **Distinct from** our 384-dim BGE retrieval embeddings |
| 28 layers | 28 | Latency multiplier per generated token |
| GQA 28 Q / 4 KV | 7:1 | 7× smaller KV cache → long RAG prompts are affordable |
| RoPE θ = 1e6 | 1e6 | Long-context capability we currently barely use |
| SwiGLU 3584→18944 | ~81% of params | The mass that 4-bit quantisation compresses; the target for structured pruning |
| Context 32768 | 32768 | We use ~1–2k → large headroom for bigger `top_k` |
| Prefill vs decode | — | `max_new_tokens=1024` dominates latency, not prompt size |
| KV cache fp16 | ~56 KiB/token | ~165 MiB at our sizes — not a bottleneck |
| Temperature / top-p | 0.1 / 0.9 | Near-greedy; top-p largely inert; **still non-deterministic** |
| 4-bit NF4 + double quant | — | ~4.2–4.7 GB total → fits free-tier GPUs |

---

## 11. Sources

- Qwen Team, *Qwen2.5 Technical Report* — [arXiv:2412.15115](https://arxiv.org/abs/2412.15115)
- Qwen Team, *Qwen2 Technical Report* — [arXiv:2407.10671](https://arxiv.org/abs/2407.10671)
- Official config — [Qwen/Qwen2.5-7B-Instruct config.json](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct/blob/main/config.json)
- Vaswani et al., *Attention Is All You Need*, NeurIPS 2017 — [arXiv:1706.03762](https://arxiv.org/abs/1706.03762)
- Ainslie et al., *GQA*, EMNLP 2023 — [arXiv:2305.13245](https://arxiv.org/abs/2305.13245)
- Shazeer, *Fast Transformer Decoding* (MQA) — [arXiv:1911.02150](https://arxiv.org/abs/1911.02150)
- Su et al., *RoFormer* — [arXiv:2104.09864](https://arxiv.org/abs/2104.09864) · [DOI 10.1016/j.neucom.2023.127063](https://doi.org/10.1016/j.neucom.2023.127063)
- Chen et al., *Positional Interpolation* — [arXiv:2306.15595](https://arxiv.org/abs/2306.15595)
- Shazeer, *GLU Variants Improve Transformer* — [arXiv:2002.05202](https://arxiv.org/abs/2002.05202)
- Ramachandran, Zoph & Le, *Searching for Activation Functions* — [arXiv:1710.05941](https://arxiv.org/abs/1710.05941)
- Zhang & Sennrich, *RMSNorm*, NeurIPS 2019 — [arXiv:1910.07467](https://arxiv.org/abs/1910.07467)
- Xiong et al., *On Layer Normalization in the Transformer Architecture*, ICML 2020 — [arXiv:2002.04745](https://arxiv.org/abs/2002.04745)
- He et al., *Deep Residual Learning*, CVPR 2016 — [arXiv:1512.03385](https://arxiv.org/abs/1512.03385)
- Sennrich, Haddow & Birch, *Subword Units (BPE)*, ACL 2016 — [arXiv:1508.07909](https://arxiv.org/abs/1508.07909)
- Holtzman et al., *The Curious Case of Neural Text Degeneration*, ICLR 2020 — [arXiv:1904.09751](https://arxiv.org/abs/1904.09751)
- Kwon et al., *PagedAttention / vLLM*, SOSP 2023 — [arXiv:2309.06180](https://arxiv.org/abs/2309.06180)
- Dettmers et al., *QLoRA*, NeurIPS 2023 — [arXiv:2305.14314](https://arxiv.org/abs/2305.14314)
- Dettmers et al., *LLM.int8()*, NeurIPS 2022 — [arXiv:2208.07339](https://arxiv.org/abs/2208.07339)
