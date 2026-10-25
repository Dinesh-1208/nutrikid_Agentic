# 06 — Model Pruning for Qwen2.5-7B-Instruct: Complete Research Space

**Framing instruction governing this document:** hardware availability is **not** used as an
elimination criterion. Every technically applicable pruning method is documented in full, with
compute requirements reported as a **separate implementation consideration** (§16). Assume suitable
cloud GPUs (A100 / H100 / multi-GPU nodes) can be obtained when a method requires them.

**Every method is documented against the same six headings:**
1. What it does
2. Why it could be useful for NutriBite
3. Data / calibration required
4. GPU / compute ideally required
5. Experiments we could perform
6. Expected benefits and risks

**No final pruning method is selected in this document.** §14 ranks candidates; the decision is
deferred until the experiment programme in §15 has been run.

**Status tags used throughout:**
`✅ PRIMARY CANDIDATE` · `🔬 RESEARCH CANDIDATE` · `🔮 POTENTIAL FUTURE WORK` ·
`⚡ HIGH-COMPUTE OPTION` · `🖥️ REQUIRES ADDITIONAL GPU RESOURCES`

---

## 1. Where the Parameters Are (Prerequisite for Every Method)

Derived from the verified config (`03_QWEN_ARCHITECTURE_RESEARCH.md` §0): `hidden_size` 3584,
28 layers, 28 Q heads / 4 KV heads, `d_head` 128, `intermediate_size` 18944, `vocab_size` 152064,
`tie_word_embeddings` false.

| Component | Formula | Parameters | Share |
|---|---|---|---|
| **FFN (SwiGLU, 3 matrices/layer)** | `3 × 3584 × 18944 × 28` | **≈ 5.70 B** | **≈ 75%** |
| Attention Q/K/V/O projections | see below | ≈ 0.82 B | ≈ 11% |
| **Embedding + untied `lm_head`** | `2 × 152064 × 3584` | **≈ 1.09 B** | **≈ 14%** |
| Norms / biases | — | negligible | < 0.1% |

Attention detail (GQA shrinks K and V by 7×):
```
W_Q: 3584 × 3584          = 12.85 M
W_K: 3584 × 512           =  1.84 M     (4 KV heads × 128)
W_V: 3584 × 512           =  1.84 M
W_O: 3584 × 3584          = 12.85 M
                per layer ≈ 29.4 M   × 28 ≈ 0.82 B
```

**Three structural facts that constrain every method below:**

1. **The FFN is the parameter mass.** Any method that does not touch the FFN has a ceiling of ~25%.
2. **Attention is only ~11%**, and GQA has already removed the KV redundancy that classical head
   pruning exploited. Head pruning's ceiling here is ~5–6%.
3. **Embeddings are ~14%** and are conventionally excluded from pruning — *except* by SliceGPT and
   Minitron-style width pruning, which explicitly include the embedding dimension. That is precisely
   what makes those two methods interesting for us.

---

## 2. Taxonomy

```
PRUNING
├── Unstructured (individual weights → 0; shape unchanged)
│     §3 magnitude · §4 SparseGPT · §5 Wanda · §7 OWL (sparsity allocation)
│     §8 sparse pretraining · §15 D-Pruner (domain-aware)
├── Semi-structured (N:M patterns; hardware-accelerable)
│     §6 2:4 / 4:8 · MaskLLM
└── Structured (whole units removed; universally faster)
      ├── Depth  §10 ShortGPT · Gromov · Shortened LLaMA · LaCo · SLEB
      ├── Width  §11 heads · §12 MLP/neurons · §13 Minitron · §9 LLM-Pruner family
      ├── Dimension §14 SliceGPT (embedding dimension itself)
      └── Objective-conditioned §15 task-aware (ZipLM) · domain-aware (D-Pruner)
```

Orthogonal axes that combine with any of the above: **quantisation** (we already run 4-bit NF4),
**knowledge distillation** (Hinton et al. — [arXiv:1503.02531](https://arxiv.org/abs/1503.02531)),
and **recovery training** (LoRA/QLoRA or continued pretraining).

---

## 3. Magnitude / Unstructured Pruning `🔬 RESEARCH CANDIDATE`

**1. What it does.** Zero individual weights with the smallest `|w|`, optionally with iterative
schedules. Foundational: LeCun, Denker & Solla, *Optimal Brain Damage*, NIPS 1989 —
[NeurIPS](https://proceedings.neurips.cc/paper/1989/hash/6c9882bbac1c7093bd25041881277658-Abstract.html);
Han, Pool, Tran & Dally, NIPS 2015 — [arXiv:1506.02626](https://arxiv.org/abs/1506.02626);
gradual schedules, Zhu & Gupta — [arXiv:1710.01878](https://arxiv.org/abs/1710.01878);
lottery-ticket framing, Frankle & Carbin, ICLR 2019 —
[arXiv:1803.03635](https://arxiv.org/abs/1803.03635). Fine-tuning-aware variant: **movement pruning**,
Sanh, Wolf & Rush, NeurIPS 2020 — [arXiv:2005.07683](https://arxiv.org/abs/2005.07683), which scores
weights by how they *move* during adaptation rather than by magnitude — notably better in
transfer-learning regimes, which is conceptually close to our domain-specialisation setting.

**2. Why useful for NutriBite.** Primarily as the **scientific baseline** every modern method is
measured against. A magnitude-pruning curve makes SparseGPT/Wanda/OWL results interpretable rather
than free-floating. Movement pruning is additionally interesting *if* we ever perform domain
adaptation, because it would identify the weights that matter for pediatric nutrition specifically.

**3. Data / calibration.** Pure magnitude pruning needs **none**. Movement pruning needs gradients
over a domain training set — which we do not currently have (report 07).

**4. Compute.** Load 7.6 B params in fp16 ≈ 15.2 GB. A single **24 GB** GPU (RTX 4090 / L4 / A10G)
suffices; **40 GB A100** comfortable. Pruning itself is seconds to minutes. Evaluation dominates.

**5. Experiments.** Sparsity sweep {10, 20, 30, 40, 50, 60, 70}% measuring our full metric suite;
per-layer vs global magnitude thresholds; magnitude-vs-Wanda-vs-SparseGPT at matched sparsity.

**6. Benefits and risks.** Benefit: trivially implementable, no calibration, a clean control.
Risks: known to collapse badly at high sparsity on LLMs — SparseGPT and Wanda both report magnitude
pruning failing well before 50% where they succeed. **Also: unstructured sparsity yields no speedup
without sparse kernels or sparse-capable hardware** (§16).

---

## 4. SparseGPT `🔬 RESEARCH CANDIDATE` `🖥️`

**1. What it does.** One-shot post-training pruning that solves a **layer-wise reconstruction**
problem, using approximate second-order (Hessian) information to both select weights to remove and
**update the surviving weights** to compensate. Reports pruning GPT-family models to **50–60%
sparsity in one shot** with modest perplexity increase and **no retraining**. Frantar & Alistarh,
ICML 2023 — [arXiv:2301.00774](https://arxiv.org/abs/2301.00774) ·
[code](https://github.com/IST-DASLab/sparsegpt).

**2. Why useful for NutriBite.** It is the strongest *no-retraining* unstructured method, which
matters because report 07 establishes we have no domain training corpus. If we can compress without
retraining, the dataset gap stops being a blocker. It also supports **2:4 semi-structured** masks
(§6), which is the route to actual hardware speedup.

**3. Data / calibration.** ~**128 sequences × 2048 tokens**, conventionally from C4. **For us the
interesting variant is calibrating on our own 558 RAG records + benchmark questions** — turning
SparseGPT into a domain-aware method (§15.3).

**4. Compute.** Layer-wise, so memory is bounded by one layer's Hessian, not the whole model:
a single **40–80 GB A100** is comfortable; 24 GB is workable with care. Runtime for a 7B model is
roughly **tens of minutes** on an A100 (*estimate from the paper's reported scaling —
NOT INDEPENDENTLY VERIFIED*).

**5. Experiments.** Sparsity sweep; C4-calibration vs **nutrition-corpus calibration**; with and
without 2:4 constraint; SparseGPT-on-fp16 vs SparseGPT-then-NF4-quantise ordering.

**6. Benefits and risks.** Benefits: no retraining; strong accuracy at 50%; well-supported code.
Risks: weight *updates* mean the model is no longer bit-identical to stock Qwen, complicating the
"we used stock Qwen2.5-7B" claim; calibration-set sensitivity is real and must be ablated;
interaction with our existing NF4 quantisation is not standard practice and needs its own validation.

---

## 5. Wanda `✅ PRIMARY CANDIDATE (unstructured)`

**1. What it does.** Prunes by `|W_ij| · ‖X_j‖₂` — weight magnitude scaled by the **norm of the
corresponding input activation** — computed per output row. **No weight update, no retraining, no
Hessian.** Matches or approaches SparseGPT at a small fraction of the cost. Sun, Liu, Bair & Kolter,
ICLR 2024 — [arXiv:2306.11695](https://arxiv.org/abs/2306.11695) ·
[code](https://github.com/locuslab/wanda).

**2. Why useful for NutriBite.** The best cost/benefit in the unstructured family: minutes of
compute, no retraining, no weight modification beyond zeroing. Critically, **the activation term is
computed on a calibration set, so Wanda is trivially made domain-aware** by calibrating on pediatric
nutrition text. That is a cheap, novel, publishable experiment (§15.3).

**3. Data / calibration.** ~128 calibration sequences for activation statistics. Our corpus supplies
558 records + 49 questions + generated answers — enough for a domain calibration set.

**4. Compute.** Single **24 GB** GPU sufficient; **40 GB A100** comfortable. Pruning runs in
**minutes**. The cheapest method in this document.

**5. Experiments.** Sparsity sweep {20…70}%; per-output vs per-layer comparison groups;
**generic-C4 vs nutrition-domain calibration** (the key experiment); Wanda + 2:4; Wanda + OWL
allocation (§7); Wanda applied before vs after NF4 quantisation.

**6. Benefits and risks.** Benefits: fastest, simplest, no retraining, weights unchanged except
zeros, strong published results. Risks: same no-speedup-without-sparse-hardware caveat (§16);
degradation beyond ~50–60% is steep; domain calibration could *overfit* to our 558 records and
damage general language ability — which must be measured, not assumed.

---

## 6. Semi-Structured N:M Sparsity (2:4, 4:8) `🔬 RESEARCH CANDIDATE` `🖥️`

**1. What it does.** Constrains sparsity to a fixed pattern — exactly N non-zeros in every contiguous
group of M weights. **2:4** (50%) is directly accelerated by NVIDIA **Sparse Tensor Cores**, giving
**up to 2× math throughput**. Mishra et al., *Accelerating Sparse Deep Neural Networks* —
[arXiv:2104.08378](https://arxiv.org/abs/2104.08378); Zhou et al., *Learning N:M Fine-grained
Structured Sparse Neural Networks From Scratch*, ICLR 2021 —
[arXiv:2102.04010](https://arxiv.org/abs/2102.04010). Learnable masks: **MaskLLM**, NeurIPS 2024 —
[arXiv:2409.17481](https://arxiv.org/abs/2409.17481). Both SparseGPT and Wanda support 2:4/4:8 masks.

**2. Why useful for NutriBite.** **This is the only unstructured-family route that produces a real
wall-clock speedup.** Our latency bottleneck is 1,024 sequential decode steps × 28 layers
(`03` §6); a 2× matmul throughput gain on Ampere+ hardware attacks that directly. 4:8 is a looser
constraint (better accuracy, still structured) where supported.

**3. Data / calibration.** Same as the underlying method (Wanda or SparseGPT): ~128 sequences.
MaskLLM instead *learns* masks and requires training data and compute.

**4. Compute.** Mask generation: same as §4/§5. **Realising the speedup requires Ampere or newer**
— A100, A10G, L4, RTX 30/40-series, H100. `🖥️ REQUIRES ADDITIONAL GPU RESOURCES` relative to a
Turing T4. Deployment via TensorRT or `nm-vllm`.

**5. Experiments.** 2:4 vs 4:8 vs unconstrained at 50% sparsity (accuracy cost of the constraint);
**measured tokens/sec on an Ampere GPU, dense vs 2:4** — the number that justifies the whole family;
2:4 combined with quantisation.

**6. Benefits and risks.** Benefits: genuine speedup; hardware-supported; mature tooling.
Risks: the 2:4 constraint costs accuracy relative to unconstrained sparsity at equal ratio; speedup
is kernel- and shape-dependent and frequently below the theoretical 2×; **on pre-Ampere hardware the
benefit is exactly zero** (§16).

---

## 7. Non-Uniform Layerwise Sparsity — OWL `🔬 RESEARCH CANDIDATE`

**1. What it does.** Nearly all LLM pruning applies the **same** sparsity ratio to every layer. OWL
shows this is suboptimal and allocates **per-layer sparsity proportional to that layer's activation
outlier ratio**, protecting outlier-heavy layers. It is a *sparsity-allocation scheme* that composes
with Wanda or SparseGPT rather than replacing them, and is reported to materially extend the
achievable high-sparsity regime. Yin et al., ICML 2024 —
[arXiv:2310.05175](https://arxiv.org/abs/2310.05175) · [code](https://github.com/luuyin/OWL).
Follow-up: *DLP: Dynamic Layerwise Pruning* — [arXiv:2505.23807](https://arxiv.org/abs/2505.23807).

**2. Why useful for NutriBite.** Two reasons, one of them specific to us. First, it is a cheap
multiplier on Wanda. Second — and more interesting — **the outlier distribution is measured on a
calibration set, so OWL computed on pediatric nutrition text would reveal which layers matter for
*our* domain.** That layer-importance profile is itself a research artifact worth reporting, entirely
independent of whether we ship a pruned model.

**3. Data / calibration.** Same calibration set as the base method, plus one extra forward pass to
collect outlier statistics.

**4. Compute.** Negligible over Wanda/SparseGPT. Single **24–40 GB** GPU.

**5. Experiments.** Uniform vs OWL allocation at matched global sparsity (50%, 60%, 70%);
**publish the per-layer outlier profile for nutrition-domain text vs generic C4 text** — a genuinely
novel measurement; OWL + 2:4.

**6. Benefits and risks.** Benefits: cheap, composable, well-cited, produces an interpretable
per-layer importance map. Risks: gains are reported mainly at *high* sparsity (≥60%), a regime where
absolute quality may already be unacceptable for a safety-critical assistant; non-uniform sparsity
complicates any downstream hardware-pattern constraint like 2:4.

---

## 8. Sparse Pretraining / High-Sparsity Foundation Models `⚡ HIGH-COMPUTE OPTION` `🔮`

**1. What it does.** Rather than pruning a finished model, combine one-shot pruning with **sparse
pretraining** so the model *learns* in the sparse regime. Agarwalla et al., *Enabling High-Sparsity
Foundational Llama Models with Efficient Pretraining and Deployment* —
[arXiv:2405.03594](https://arxiv.org/abs/2405.03594). Reports **full accuracy recovery for
fine-tuning tasks at up to 70% sparsity** on LLaMA-2 7B, by combining SparseGPT with sparse
pretraining on SlimPajama + The Stack. Deployment: **up to 3× on CPU** (DeepSparse), **1.7× on GPU**
(nm-vllm), and **up to 8.6× on CPU when sparse-quantised**.

**2. Why useful for NutriBite.** The CPU numbers are the striking part. A **3–8.6× CPU speedup**
opens a deployment mode this project does not currently have: running the assistant **without a GPU
at all**, which is directly relevant to a low-resource / rural-deployment story for an Indian
pediatric nutrition tool. That is a product-level argument, not just an efficiency one.

**3. Data / calibration.** Large pretraining corpora (SlimPajama subset + code). Not domain data.

**4. Compute.** `⚡` Sparse pretraining of a 7B model is a **multi-GPU, multi-day** job — realistically
**8–64 A100/H100** for the pretraining phase. Well beyond a student project's budget, but the
**released sparse checkpoints can be used directly**, which is the practical path.

**5. Experiments.** Evaluate an *existing* released sparse LLaMA checkpoint on our benchmark as a
reference point; measure DeepSparse CPU throughput for our prompt shape; if a sparse Qwen2.5 variant
is ever released, compare directly.

**6. Benefits and risks.** Benefits: the only route to full recovery at 70%; unlocks CPU deployment.
Risks: pretraining is out of budget; **released checkpoints are LLaMA-family, not Qwen**, so using
them means changing the base model and invalidating every existing result; DeepSparse is
CPU-architecture-sensitive.

---

## 9. Structured Pruning — LLM-Pruner and Family `✅ PRIMARY CANDIDATE (structured)` `🖥️`

**1. What it does.** Removes **whole structural units** — FFN channels, attention heads, coupled
groups — so the model is genuinely smaller and faster **on any hardware, with no special kernels**.

| Method | Contribution | Reference |
|---|---|---|
| **LLM-Pruner** | Gradient-based coupled-structure discovery + **LoRA recovery** | Ma, Fang & Wang, NeurIPS 2023 — [arXiv:2305.11627](https://arxiv.org/abs/2305.11627) |
| **FLAP** | Fluctuation-based, **retraining-free** structured pruning | [arXiv:2312.11983](https://arxiv.org/abs/2312.11983) |
| **LoRAPrune** | Joint LoRA + iterative structured pruning | [arXiv:2305.18403](https://arxiv.org/abs/2305.18403) |
| **LoRAShear** | Dependency-graph analysis, marks knowledge-critical structures unprunable, progressive pruning + recovery | [arXiv:2310.18356](https://arxiv.org/abs/2310.18356) |
| **ZipLM** | **Inference-aware**, loss-vs-runtime trade-off at each step, with speedup guarantees | Kurtic et al., NeurIPS 2023 — [arXiv:2302.04089](https://arxiv.org/abs/2302.04089) |
| **SlimGPT** | Layer-wise structured pruning | [arXiv:2412.18110](https://arxiv.org/abs/2412.18110) |

**2. Why useful for NutriBite.** Structured pruning is the family that delivers a **real, portable
speedup** — critical because our bottleneck is sequential decode, and because we want the result to
hold whatever GPU we deploy on. **ZipLM deserves particular attention**: it optimises the
loss/runtime trade-off directly and offers speedup *guarantees*, which converts "we pruned 20%" into
"we achieved a target latency", a far more defensible engineering claim. **LoRAShear's notion of
marking knowledge-critical structures as unprunable** maps naturally onto a safety requirement —
protect the circuits responsible for refusal behaviour.

**3. Data / calibration.** LLM-Pruner needs **gradients** (calibration data with backward passes).
Recovery needs an instruction corpus — LLM-Pruner used ~50 k Alpaca samples. FLAP avoids recovery
entirely, which is why it matters to us given report 07's data gap.

**4. Compute.** Gradient computation on a 7B model needs far more than inference: **40–80 GB
(A100-80GB)** is the comfortable target, or gradient checkpointing on 40 GB. LoRA recovery on ~50 k
samples ≈ **several hours on one A100**. `🖥️`

**5. Experiments.** FFN-width sweep {10, 20, 30, 50}%; **FLAP (no recovery) vs LLM-Pruner (with LoRA
recovery)** — isolates how much of the loss recovery buys back; ZipLM targeting a **specific latency
budget**; LoRAShear with refusal-critical structures protected — a safety-aware pruning experiment
that, to my knowledge, has no direct precedent in the nutrition domain.

**6. Benefits and risks.** Benefits: real hardware-independent speedup and memory reduction; mature
methods; composes with quantisation. Risks: **every credible result at ≥20% includes recovery
training**, which needs data (report 07); generic-corpus recovery would restore general ability
without helping pediatric nutrition; higher implementation complexity than depth pruning.

**Size arithmetic for FFN width reduction:**

| FFN width | Params removed | 4-bit size (approx) |
|---|---|---|
| 18,944 (current) | — | ~4.2 GB |
| 15,155 (−20%) | ~1.14 B | ~3.6 GB |
| 13,261 (−30%) | ~1.71 B | ~3.3 GB |
| 9,472 (−50%) | ~2.85 B | ~2.8 GB |

---

## 10. Layer / Depth Pruning `✅ PRIMARY CANDIDATE`

**1. What it does.** Delete entire transformer blocks. The residual stream makes this viable: a
removed block leaves an identity path `x → x` rather than a severed network (`03` §3.2).

| Method | Selection criterion | Reference |
|---|---|---|
| **ShortGPT** | **Block Influence** — how much a layer changes the hidden state | Men et al. — [arXiv:2403.03853](https://arxiv.org/abs/2403.03853) |
| **Gromov et al.** | Angular similarity between layer inputs/outputs; **QLoRA healing**; finds deeper layers most removable | [arXiv:2403.17887](https://arxiv.org/abs/2403.17887) |
| **Shortened LLaMA** | Perplexity and Taylor-expansion importance; **finds continued pretraining clearly beats LoRA for recovery at severe ratios** | Kim et al. — [arXiv:2402.02834](https://arxiv.org/abs/2402.02834) |
| **LaCo** | **Collapses** rear layers into a prior layer rather than deleting; reports **30–50% layer removal without training** | Yang et al., EMNLP Findings 2024 — [arXiv:2402.11187](https://arxiv.org/abs/2402.11187) · [ACL](https://aclanthology.org/2024.findings-emnlp.372.pdf) |
| **SLEB** | Redundancy verification over transformer blocks, exploiting high similarity between neighbouring block outputs | [arXiv:2402.09025](https://arxiv.org/abs/2402.09025) |

**2. Why useful for NutriBite.** The strongest practical case in this document:
- **Latency scales ~linearly with depth**, and our cost is `max_new_tokens=1024` × 28 layers of
  sequential decode. Cutting 28 → 22 layers is ~21% off *every generated token*.
- **Simplest possible implementation** — delete entries from `model.model.layers`.
- **Composes cleanly with our 4-bit NF4 quantisation** — orthogonal concerns.
- **LaCo's training-free 30–50% claim** means a large compression is testable *without* solving the
  dataset problem first.
- **Measurable with our existing evaluation harness**, no new metric infrastructure.

**3. Data / calibration.** ShortGPT/SLEB/LaCo need only a small calibration set for importance
scoring — **our own 558 records work**, making the importance profile domain-specific. Healing
(optional) needs instruction data.

**4. Compute.** Importance scoring: inference only, **24 GB** sufficient. Pruning itself: free.
Optional QLoRA healing: **1 × 24–40 GB** for a few hours. The **lowest compute requirement of any
structured method**.

**5. Experiments.** See §15 P1 — the flagship experiment. Sweep 2/4/6/8/10 removed layers ×
{contiguous-deep, Block-Influence, LaCo-collapse, **random control**} × {no healing, QLoRA healing}.

**6. Benefits and risks.** Benefits: simple, immediate latency win, hardware-independent, strong
citations, cheap. Risks: **published results are on MMLU/HellaSwag/perplexity, not on grounded
safety-constrained domain RAG.** Our task additionally demands reading long retrieved context,
emitting a fixed 4-section format, obeying a verbatim refusal script, and not contradicting a JSON
payload. **Do not assume published ratios transfer** — which is exactly what makes measuring it a
contribution.

---

## 11. Attention-Head Pruning `🔬 RESEARCH CANDIDATE`

**1. What it does.** Remove individual attention heads deemed redundant. Michel, Levy & Neubig,
*Are Sixteen Heads Really Better than One?*, NeurIPS 2019 —
[arXiv:1905.10650](https://arxiv.org/abs/1905.10650); Voita et al., ACL 2019 —
[arXiv:1905.09418](https://arxiv.org/abs/1905.09418) — both find most heads removable with limited
degradation, and only a minority carrying specialised roles.

**2. Why useful for NutriBite.** Modest as a compression method, but **valuable as interpretability**.
Identifying which heads matter for *retrieved-context grounding* would be a genuinely interesting
analysis — and it connects to the attention-attribution discussion in `04` §7. A head-importance map
for nutrition RAG is a reportable artifact even if we never ship a head-pruned model.

**3. Data / calibration.** Calibration set with forward (and for gradient-based importance, backward)
passes. Our benchmark questions suffice.

**4. Compute.** Single **24–40 GB** GPU; gradient-based importance pushes toward 40–80 GB.

**5. Experiments.** Head-importance ranking on nutrition RAG prompts vs generic text; prune
{10, 25, 50}% of query heads; **whole-GQA-group removal** (all 7 query heads + their shared KV head)
vs scattered query-head removal — the comparison that actually matters under GQA.

**6. Benefits and risks.** Benefits: interpretability value; cheap; well-cited.
Risks (both significant and specific to this model): **(a) ceiling ~5–6%** since attention is only
~11% of parameters; **(b) GQA breaks the classic assumption** — pruning query heads within a group of
7 does not remove the shared KV head, so the KV cache does not shrink unless a whole group goes, and
our KV cache is already only ~165 MiB (`03` §7). Both cited papers predate GQA and studied MHA
models, so **their redundancy findings may not transfer — arguably GQA has already harvested that
redundancy.**

---

## 12. MLP / Neuron Pruning `🔬 RESEARCH CANDIDATE` `🖥️`

**1. What it does.** Remove individual **neurons** (intermediate channels) from the SwiGLU FFN —
i.e. drop rows of `W_gate`/`W_up` and the corresponding columns of `W_down`. Importance is typically
activation-frequency or magnitude based. Closely related is the observation that FFN activations are
highly sparse in practice, exploited by conditional-computation work such as
**Deja Vu** — Liu et al., ICML 2023 — [arXiv:2310.17157](https://arxiv.org/abs/2310.17157).

**2. Why useful for NutriBite.** This is where **75% of the parameters live** (§1) — the highest
ceiling of any width-pruning target. And it is the most plausible site of **domain redundancy**:
a general-purpose 7B allocates FFN capacity to code, mathematics, multilingual text and countless
topics NutriBite never touches. Measuring which neurons activate on pediatric nutrition prompts
versus generic text is a direct, cheap test of that hypothesis (§15.3).

**3. Data / calibration.** Activation statistics over a calibration set — cheap, forward-pass only.
Domain vs generic comparison is the interesting design.

**4. Compute.** Statistics collection: **24 GB**, forward only. Recovery (if pruning >20%):
**40–80 GB** for LoRA. `🖥️`

**5. Experiments.** Collect per-neuron activation frequency on (a) our 49 benchmark prompts,
(b) generic C4 — and report the **overlap**; prune the bottom {10, 20, 30, 40}% by domain activation;
compare domain-selected vs generic-selected neuron removal at matched ratio. **If domain-selected
pruning preserves nutrition quality while generic-selected does not, that is the core empirical
result of a domain-aware pruning paper.**

**6. Benefits and risks.** Benefits: highest parameter ceiling; real structured speedup; directly
tests the domain-redundancy hypothesis. Risks: aggressive FFN pruning damages general language
fluency, which our *prose-quality* metrics may not capture well; needs recovery beyond ~20%;
activation sparsity is input-dependent, so a statically pruned model may fail on unusual queries.

---

## 13. Width Pruning + Distillation — Minitron `⚡ HIGH-COMPUTE OPTION` `🖥️` `🔮`

**1. What it does.** NVIDIA's systematic recipe combining **depth, width, attention and MLP pruning
with knowledge-distillation-based retraining**. Muralidharan et al., *Compact Language Models via
Pruning and Knowledge Distillation*, NeurIPS 2024 —
[arXiv:2407.14679](https://arxiv.org/abs/2407.14679) · [code](https://github.com/NVlabs/Minitron);
practical follow-up [arXiv:2408.11796](https://arxiv.org/abs/2408.11796).

Headline findings, all directly relevant to our method choice:
- Compressed the Nemotron-4 family **2–4×**.
- Deriving 8B and 4B from a pretrained 15B needed **up to 40× fewer training tokens** than training
  from scratch, for **1.8×** total compute saving across the family.
- **Up to 16% better MMLU than training from scratch.**
- **"Width pruning outperforms depth — but only after retraining."** ← the single most decision-relevant
  sentence in the pruning literature for this project.

**2. Why useful for NutriBite.** That last finding tells us how to interpret our own results: if we
prune **without** retraining, **depth pruning is expected to be the better choice**; width pruning
only wins once a recovery budget exists. This lets us make a principled, citation-backed method
choice rather than an arbitrary one. Distillation also offers a data path that sidesteps report 07's
gap: the **teacher is the unpruned Qwen**, so no human-labelled corpus is required.

**3. Data / calibration.** Distillation needs a substantial unlabelled corpus (<3% of original
pretraining data — still **billions of tokens**). Teacher logits come free from the dense model.

**4. Compute.** `⚡` The real cost. Even at 40× reduction, retraining a 7B-class model on billions of
tokens implies **8–64 A100/H100 for days**. `🖥️ REQUIRES ADDITIONAL GPU RESOURCES` — this is a
funded-lab-scale job, not a student-project job.

**5. Experiments.** Full Minitron recipe on Qwen2.5-7B → 4B (**if cluster access is obtained**);
a **scaled-down** variant — prune 20% width, distil on a few hundred million tokens — as a
budget-feasible partial replication; **confirm or refute the "width beats depth only after
retraining" finding in the grounded-RAG setting**, which would be a real contribution since the
original claim is established on general benchmarks.

**6. Benefits and risks.** Benefits: best-in-class published results; principled recipe; distillation
removes the labelled-data dependency. Risks: compute cost is the dominant blocker; a full replication
is out of scope; a partial replication risks under-training and producing a misleadingly negative
result — which must be reported as *under-trained*, not as *method failure*.

---

## 14. Dimension Pruning — SliceGPT `🔬 RESEARCH CANDIDATE` `🖥️`

**1. What it does.** A structurally different idea: exploit **computational invariance** in
transformers to replace each weight matrix with a **smaller dense matrix**, reducing the
**embedding dimension** itself. Rows and columns are deleted based on PCA of activations. Ashkboos,
Croci, Gennari do Nascimento, Hoefler & Hensman, ICLR 2024 —
[arXiv:2401.15024](https://arxiv.org/abs/2401.15024) ·
[code](https://github.com/microsoft/TransformerCompression).

Reported: removes **up to 25% of parameters including embeddings** from Llama-2 70B, OPT 66B and
Phi-2 while retaining **99%, 99% and 90%** of dense zero-shot performance; reduces total inference
compute to **64%** of dense on 24 GB consumer GPUs and **66%** on 40 GB A100s.

**2. Why useful for NutriBite.** Uniquely, it prunes the **embedding matrices**, which are **~14% of
Qwen2.5-7B** (§1) and are untouched by every other method here. Our vocabulary is 152,064 with
**untied** input and output embeddings — an unusually large share — so we have more to gain from
SliceGPT than a typical smaller-vocabulary model. It also produces **dense** smaller matrices, so the
speedup is real on any hardware including a T4.

**3. Data / calibration.** Calibration set for the PCA of activations. Domain-calibrated slicing is
again an available variant.

**4. Compute.** PCA over activations for a 7B model: **40 GB A100** comfortable; 24 GB feasible.
One-shot, no retraining required (optional recovery fine-tuning improves results). `🖥️`

**5. Experiments.** Slice {10, 20, 25, 30}% and evaluate; **generic vs nutrition-domain calibration**;
SliceGPT vs depth pruning at matched parameter reduction — a clean head-to-head; SliceGPT combined
with 4-bit quantisation.

**6. Benefits and risks.** Benefits: only method reaching the embedding mass; dense output so
hardware-independent speedup; one-shot; strong ICLR-2024 provenance. Risks: results are reported on
Llama/OPT/Phi, **not Qwen** — the invariance argument should hold but transfer is unverified; the
Phi-2 result (90%) shows **smaller models degrade more**, and at 7B we are much nearer Phi-2's scale
than Llama-2-70B's, so **we should expect results closer to the weaker end**; implementation requires
care with RMSNorm and RoPE.

---

## 15. Objective-Conditioned Pruning: Task-Aware and Nutrition-Domain-Aware

This is, in my assessment, **where the genuine research novelty for this project lies**, and it was
under-developed in the previous version of this report.

### 15.1 Task-aware pruning — ZipLM `🔬 RESEARCH CANDIDATE`

**1. What it does.** Prunes with the **target task and target hardware runtime** in the objective,
rather than pruning generically and hoping. ZipLM balances the loss-runtime trade-off at each step
and **provides speedup guarantees**. Kurtic et al., NeurIPS 2023 —
[arXiv:2302.04089](https://arxiv.org/abs/2302.04089) ·
[code](https://github.com/IST-DASLab/ZipLM). Predecessor for BERT-scale: *The Optimal BERT Surgeon*
(oBERT) — [arXiv:2203.07259](https://arxiv.org/abs/2203.07259).

**2. Why useful for NutriBite.** We have a **single, narrow task**: grounded pediatric nutrition
explanation in a fixed 4-section format with fixed safety behaviour. We do **not** need code
generation, multilingual ability, mathematical reasoning, or creative writing. A task-aware objective
can exploit that. And the ability to prune **to a latency target** converts pruning from a vague
compression exercise into a concrete engineering deliverable.

**3. Data / calibration.** Task-specific calibration — our benchmark questions plus their full
assembled RAG prompts. Larger task sets give better estimates; our 49 cases are small, so this would
want the expanded evaluation set (roadmap R11).

**4. Compute.** Structured-pruning class: **40–80 GB A100** for gradient/Hessian estimation. `🖥️`

**5. Experiments.** Prune to a target of {0.75×, 0.5×} current per-token latency and measure quality;
task-aware vs task-agnostic pruning at matched compression.

**6. Benefits and risks.** Benefits: directly aligned with how we actually deploy; guarantees rather
than hopes. Risks: **over-specialisation** — a model pruned hard against 49 questions will do well on
those 49 questions. Any result *must* be evaluated on genuinely held-out queries, or it is
meaningless.

### 15.2 Domain-aware pruning — D-Pruner `✅ PRIMARY CANDIDATE (novel-contribution route)`

**1. What it does.** **The most directly relevant paper found in this entire survey.** D-Pruner is an
**unstructured dual-pruning** method for **domain-specific** compression: it separately identifies
weights pivotal for **general capability** (linguistic competence, multi-task ability) and weights
pivotal for **domain-specific knowledge**, then prunes with both in view — yielding a compressed,
domain-specific, task-agnostic LLM. Zhang et al., *Pruning as a Domain-specific LLM Extractor*,
**NAACL Findings 2024** — [arXiv:2405.06275](https://arxiv.org/abs/2405.06275) ·
[ACL Anthology](https://aclanthology.org/2024.findings-naacl.91/) ·
[code](https://github.com/psunlpgroup/D-Pruner).

**Crucially: its reported experiments are in the healthcare and legal domains.** Healthcare is
adjacent to pediatric nutrition, which makes transfer plausible and gives us a directly comparable
baseline.

**2. Why useful for NutriBite.** This is the method that matches the project's actual thesis. The
framing — *"extract a domain-specific model from a general one by pruning"* — is exactly what
NutriBite is: a pediatric-nutrition specialist built on a general assistant. **A D-Pruner-style study
in the pediatric-nutrition domain appears to be unoccupied ground**, and it would be a genuine
contribution rather than a re-run of a published benchmark. It also inverts the usual pruning
narrative: instead of *"how much quality do we lose?"*, the question becomes *"does removing
general-purpose capacity sharpen domain behaviour?"* — a hypothesis that can be falsified.

**3. Data / calibration.** Needs **both** a domain corpus (our 558 RAG records, 49 benchmark
questions, generated answers, expandable via IFCT/WHO-IYCF per report 07 §9) **and** a general corpus
for the general-capability term. Notably, **this does not require labelled instruction data** — the
report-07 blocker does not apply here.

**4. Compute.** Involves a general-capability weight-importance term computed with gradients →
**40–80 GB A100** territory. `🖥️` Estimate; not independently verified.

**5. Experiments.** The flagship study — D-Pruner with a **pediatric-nutrition** domain corpus at
{20, 30, 50}% sparsity, evaluated on: our nutrition benchmark (should hold up), **and** a general
benchmark (expected to degrade — and we should say by how much); compared against domain-agnostic
Wanda/SparseGPT at matched sparsity. **The pre-registered hypothesis: domain-aware pruning retains
nutrition quality at sparsity levels where domain-agnostic pruning does not.**

**6. Benefits and risks.** Benefits: novel in our domain; healthcare precedent; needs no labelled
data; thesis-aligned. Risks: unstructured → **no speedup without sparse hardware** (§16); our domain
corpus (558 short records) may be too small for stable importance estimation — **a real concern that
should be tested by varying calibration-set size**; deliberately degrading general capability is
dangerous in an assistant that must handle off-topic and adversarial queries safely.

### 15.3 Nutrition-domain-aware calibration as a cross-cutting variable `✅`

Separately from D-Pruner, **almost every method above takes a calibration set**, conventionally
generic C4 text. Substituting **pediatric-nutrition text** is a low-cost, high-novelty variable that
can be applied across Wanda, SparseGPT, OWL, SliceGPT and MLP-neuron pruning.

This yields a clean experimental matrix — `{method} × {generic calibration, domain calibration}` —
and answers one crisp question: **does domain-specific calibration change which weights are judged
important, and does that translate into better domain performance at equal sparsity?** It is cheap,
it is reportable whichever way it comes out, and it does not depend on obtaining any new dataset.

---

## 16. Hardware and Implementation Considerations (Separate from Method Selection)

**This section records feasibility only. Nothing here removes a method from the research space.**

### 16.1 The sparse-acceleration constraint

NVIDIA **Sparse Tensor Cores**, which accelerate 2:4 sparsity, were introduced with **Ampere**
([A100 architecture whitepaper](https://images.nvidia.com/aem-dam/en-zz/Solutions/data-center/nvidia-ampere-architecture-whitepaper.pdf);
[NVIDIA developer blog](https://developer.nvidia.com/blog/accelerating-inference-with-sparsity-using-ampere-and-tensorrt/)).

| GPU | Architecture | Sparse tensor cores | Consequence for unstructured/2:4 |
|---|---|---|---|
| Kaggle **T4** | Turing (sm_75) | **No** | Sparsity gives **no** speedup or memory saving |
| Kaggle **P100** | Pascal | **No** | Same |
| **A100 / A10G / L4 / RTX 30-40** | Ampere/Ada | **Yes** | 2:4 speedup available |
| **H100** | Hopper | **Yes** | Best support |

**Interpretation:** this constrains *where we run the deployment benchmark*, not *whether we study
the method*. Accuracy results for Wanda / SparseGPT / OWL / D-Pruner are **hardware-independent and
can be produced on any GPU**, including a T4. Only the **speed measurement** needs Ampere+. The
correct plan is therefore: measure quality anywhere, rent one Ampere instance for the throughput
numbers.

### 16.2 Compute requirement summary

| Method | Min viable | Comfortable | Class |
|---|---|---|---|
| Magnitude (§3) | 24 GB | 40 GB | Single GPU |
| Wanda (§5) | 24 GB | 40 GB | Single GPU, minutes |
| SparseGPT (§4) | 24 GB | 80 GB | Single GPU, tens of minutes |
| 2:4 masks (§6) | as above | + **Ampere+ for speed** | Single GPU |
| OWL (§7) | 24 GB | 40 GB | Single GPU |
| Layer pruning (§10) | **24 GB** | 40 GB | **Cheapest structured** |
| Head / MLP pruning (§11–12) | 40 GB | 80 GB | Gradients push memory |
| LLM-Pruner family (§9) | 40 GB | 80 GB | + hours of LoRA recovery |
| SliceGPT (§14) | 24 GB | 40 GB | One-shot PCA |
| ZipLM (§15.1) | 40 GB | 80 GB | Gradient/Hessian |
| D-Pruner (§15.2) | 40 GB | 80 GB | Dual importance terms |
| **Minitron (§13)** | — | **8–64 A100/H100, days** | `⚡ Cluster` |
| **Sparse pretraining (§8)** | — | **Multi-node, days** | `⚡ Cluster` |

### 16.3 Interaction with our existing 4-bit NF4 quantisation
We currently run NF4 + double quantisation (`llm/llm_client.py`). Pruning and quantisation compose,
but **order matters and is under-documented**. Standard practice is prune in fp16/bf16 → evaluate →
then quantise. Any experiment must state the order used. Note also that `bitsandbytes` NF4 has **no
standard 2:4 sparse path**, so a sparse+NF4 deployment would likely require a different stack
(TensorRT-LLM, nm-vllm). *This is an engineering unknown, flagged rather than resolved.*

### 16.4 Software stacks
`torch.nn.utils.prune` (masks only, no speedup) · [SparseGPT](https://github.com/IST-DASLab/sparsegpt) ·
[Wanda](https://github.com/locuslab/wanda) · [OWL](https://github.com/luuyin/OWL) ·
[LLM-Pruner](https://github.com/horseee/LLM-Pruner) · [ZipLM](https://github.com/IST-DASLab/ZipLM) ·
[D-Pruner](https://github.com/psunlpgroup/D-Pruner) ·
[SliceGPT / TransformerCompression](https://github.com/microsoft/TransformerCompression) ·
[Minitron](https://github.com/NVlabs/Minitron) · TensorRT-LLM · nm-vllm / DeepSparse.

---

## 17. Full Comparison Table

| § | Method | Type | Retrain needed | Real speedup on **any** HW | Param ceiling | Compute class | Status |
|---|---|---|---|---|---|---|---|
| 3 | Magnitude | Unstructured | No | No | ~50% | Low | 🔬 baseline |
| 4 | SparseGPT | Unstructured | **No** | No (yes w/ 2:4 + Ampere) | 50–60% | Medium | 🔬 |
| 5 | **Wanda** | Unstructured | **No** | No (yes w/ 2:4 + Ampere) | 50–60% | **Lowest** | ✅ |
| 6 | 2:4 / 4:8 | Semi-structured | No | **Yes on Ampere+** | 50% | Medium | 🔬 🖥️ |
| 7 | OWL | Allocation scheme | No | inherits base | extends base | Low | 🔬 |
| 8 | Sparse pretraining | Unstructured | **Yes (pretrain)** | Yes (3–8.6× CPU) | **70%** | ⚡ Cluster | 🔮 ⚡ |
| 9 | LLM-Pruner / ZipLM / FLAP | Structured | Usually yes (FLAP no) | **Yes** | ~75% (FFN) | High | ✅ 🖥️ |
| 10 | **Layer / depth** | Structured | Optional | **Yes, ~linear** | ∝ layers cut | **Low** | ✅ |
| 11 | Head pruning | Structured | Usually | Small | **~5–6%** | Medium | 🔬 |
| 12 | MLP / neuron | Structured | >20% yes | **Yes** | **~75%** | Medium-high | 🔬 |
| 13 | **Minitron** (width+depth+KD) | Structured | **Yes (KD)** | **Yes** | 2–4× | ⚡ Cluster | 🔮 ⚡ 🖥️ |
| 14 | **SliceGPT** | Dimension | Optional | **Yes (dense)** | ~25% **incl. embeddings** | Medium | 🔬 🖥️ |
| 15.1 | ZipLM (task-aware) | Structured | Yes | **Yes, guaranteed** | tunable | High | 🔬 🖥️ |
| 15.2 | **D-Pruner** (domain-aware) | Unstructured | No | No (needs sparse HW) | 20–50% | High | ✅ **novel** |
| 15.3 | Domain calibration | Cross-cutting | No | inherits base | inherits | **Lowest** | ✅ |

---

## 18. Experiment Programme

### P1 — Layer/depth pruning sweep `✅ flagship, low compute`
- **Baseline:** full 28-layer Qwen2.5-7B-Instruct.
- **Variants:** remove 2 / 4 / 6 / 8 / 10 layers.
- **Selection:** (a) contiguous deep block (Gromov), (b) Block Influence (ShortGPT), (c) LaCo
  collapse, (d) SLEB block redundancy, (e) **random — the control**, without which no claim about
  (a)–(d) is attributable to the selection method rather than to depth reduction itself.
- **Recovery:** none, then QLoRA healing as a second arm (Gromov; Shortened LLaMA reports continued
  pretraining beats LoRA at severe ratios — worth stating as a known limitation of the LoRA arm).
- **Calibration for (b)/(d):** our own 558 records → domain-specific importance.

### P2 — Unstructured sparsity family `🔬`
Wanda vs SparseGPT vs magnitude at {20, 30, 40, 50, 60, 70}%, × {uniform, OWL} allocation,
× {generic C4 calibration, **nutrition-domain calibration**}. Quality measured anywhere; **throughput
measured on one rented Ampere instance** with and without 2:4.

### P3 — D-Pruner domain-aware extraction `✅ novel contribution`
D-Pruner with a pediatric-nutrition domain corpus at {20, 30, 50}% vs domain-agnostic Wanda at
matched sparsity. Evaluate on **both** our nutrition benchmark and a general benchmark, and report
the general-capability loss explicitly. **Pre-registered hypothesis:** domain-aware pruning retains
nutrition quality at sparsity levels where domain-agnostic pruning does not. Vary calibration-set
size to test stability on our small corpus.

### P4 — SliceGPT dimension reduction `🔬`
Slice {10, 20, 25, 30}%; generic vs domain calibration; head-to-head against P1 at matched parameter
reduction. Expect results nearer the Phi-2 end of the published range given our 7B scale.

### P5 — Structured FFN/width pruning `🖥️`
FLAP (retraining-free) vs LLM-Pruner (LoRA recovery) vs ZipLM (latency-targeted) at {10, 20, 30, 50}%
FFN sparsity. Tests Minitron's "width beats depth only after retraining" claim in our setting.

### P6 — Domain-redundancy analysis `✅ zero-risk, high-insight`
No pruning at all: collect per-neuron FFN activation statistics and per-head attention statistics on
(a) our 49 benchmark prompts and (b) generic text, and report the **overlap**. Directly measures how
much of Qwen2.5-7B our task actually uses. **This is the cheapest experiment in the document and it
informs every other one.**

### P7 — Head pruning under GQA `🔬`
Whole-group removal (7 Q heads + shared KV head) vs scattered query-head removal at matched count.
Tests whether pre-GQA head-redundancy findings transfer.

### P8 — Minitron-style width+depth+KD `⚡ 🔮`
Full recipe if cluster access is obtained; otherwise a scaled-down partial replication, reported
explicitly as under-trained.

### 18.1 Metrics — all experiments report all five families

| Family | Metrics | Judge needed |
|---|---|---|
| **Quality** | Faithfulness, Answer Relevancy, Hallucination Rate (41 RAG cases) | Yes |
| **Behavioural** | **4-section format compliance**; **verbatim refusal-script compliance**; "did it recalculate calories when forbidden?" | **No — deterministic** |
| **Safety** | `SafetyJudge` Compliant/Refusal/Violation distribution | Yes |
| **Efficiency** | median + p90 latency; **ms per generated token**; peak GPU memory; tokens/sec | No |
| **Size** | parameter count; on-disk bytes; achieved sparsity | No |

**The behavioural metrics matter more here than perplexity.** A pruned model that still scores well
on Faithfulness but stops emitting the safety disclaimer, or stops refusing medical questions, has
failed in precisely the way this project cares about — and general benchmarks would never detect it.
That is the strongest argument for running pruning experiments in this domain at all.

### 18.2 Controls (non-negotiable)
`do_sample = False` (greedy) so pruning effects are not confounded with sampling noise (`05` §A1);
`enable_cache = False`; identical prompts and retrieved contexts across arms; report the noise floor
from `05` Experiment A-E1 alongside every degradation curve; **random-selection control in every
structured experiment**.

---

## 19. Honest Assessment — Recorded, Not Used to Eliminate

The arguments below were the basis of the earlier version's rejection of pruning. They are retained
as **decision context**, explicitly **not** as elimination criteria.

1. **Quantisation has already solved our deployment constraint.** NF4 4-bit takes ~15.2 GB → ~4.2 GB
   (~3.6×), with no retraining. There is no unmet *memory* requirement for pruning to solve.
   *Counterpoint:* pruning targets **latency and throughput**, which quantisation does not fully
   address, and the two compose.
2. **Our measured bottleneck is `max_new_tokens = 1024` sequential decode**, not model size. Reducing
   that cap or batching through vLLM is cheaper and risk-free. *Counterpoint:* depth pruning attacks
   the same bottleneck multiplicatively and composes with those fixes.
3. **Pruning degrades quality by construction**, while the project's thesis is about grounding,
   faithfulness and safety. *Counterpoint:* §15.2's hypothesis is precisely that **domain-aware**
   pruning need not degrade *domain* quality — which is a testable claim, not an assumption.
4. **Recovery training needs data we do not have** (report 07). *Counterpoint:* FLAP, LaCo, Wanda,
   SparseGPT, SliceGPT and D-Pruner are **all training-free**; and Minitron-style distillation uses
   the dense model as teacher, requiring no labels.

**Standing research argument in favour:** published pruning results are overwhelmingly on general
benchmarks — perplexity, MMLU, HellaSwag. **Grounded, safety-constrained, domain-specific RAG is
under-studied as a pruning evaluation setting**, and pediatric nutrition appears unoccupied. The
question *"how much can Qwen2.5-7B be compressed before grounded pediatric nutrition guidance
degrades — and does domain-aware pruning shift that frontier?"* has a real, citable, currently
unknown answer.

### 19.1 Deployment motivation worth stating
Beyond research value, §8's **3–8.6× CPU speedup** figures point at a deployment mode NutriBite does
not have: **GPU-free operation**. For a pediatric nutrition tool aimed at Indian caregivers,
CPU-only or offline capability is a substantive product argument, not merely an efficiency footnote.

---

## 20. Rejected and Deprioritised Alternatives (Retained With Reasons)

| Method | Status | Reason |
|---|---|---|
| Pruning the embedding/`lm_head` directly | **Deprioritised** | 14% of params but conventionally excluded — degradation is severe. **SliceGPT (§14) is the principled way to reach this mass** and is retained as a candidate |
| Vocabulary pruning (trim 152,064 tokens to an English-nutrition subset) | **🔬 Research candidate, not developed** | Would shrink both embedding matrices substantially given our monolingual, narrow domain. Risk: byte-level BPE guarantees no OOV, and trimming breaks that guarantee. **Flagged as an unexplored option worth a look** |
| Linear/approximate attention (Performer [arXiv:2009.14794](https://arxiv.org/abs/2009.14794), Linformer [arXiv:2006.04768](https://arxiv.org/abs/2006.04768)) | **Rejected** | Requires architectural change **and full retraining**; our sequences (~1–2k tokens) are far too short for the asymptotic benefit to appear. Rejected on task-fit, not hardware |
| Mixture-of-Experts conversion | **🔮 Future work** | Converting a dense FFN to MoE (cf. [arXiv:2502.04416](https://arxiv.org/abs/2502.04416)) routes only relevant experts per token. Conceptually attractive for domain specialisation; substantial retraining required |
| Dynamic/conditional computation (Deja Vu [arXiv:2310.17157](https://arxiv.org/abs/2310.17157), SkipGPT [arXiv:2506.04179](https://arxiv.org/abs/2506.04179)) | **🔬 Research candidate** | Input-dependent pruning at inference rather than static removal — preserves worst-case capability while saving average compute. **Genuinely interesting and not developed here; worth a follow-up** |
| Early-exit / speculative decoding | **🔮 Future work** | Not pruning, but attacks the same decode bottleneck. Should be compared against pruning on a like-for-like latency basis |
| Quantisation beyond 4-bit (2/3-bit: GPTQ, AWQ) | **🔬 Research candidate** | Complementary compression axis, deliberately out of this report's scope but a fair competitor for the same latency/size goal |

---

## 21. Sources

**Foundational**
- LeCun, Denker & Solla, *Optimal Brain Damage*, NIPS 1989 — [NeurIPS](https://proceedings.neurips.cc/paper/1989/hash/6c9882bbac1c7093bd25041881277658-Abstract.html)
- Han et al., *Learning both Weights and Connections*, NIPS 2015 — [arXiv:1506.02626](https://arxiv.org/abs/1506.02626)
- Zhu & Gupta, *To Prune, or Not to Prune* — [arXiv:1710.01878](https://arxiv.org/abs/1710.01878)
- Frankle & Carbin, *Lottery Ticket Hypothesis*, ICLR 2019 — [arXiv:1803.03635](https://arxiv.org/abs/1803.03635)
- Sanh, Wolf & Rush, *Movement Pruning*, NeurIPS 2020 — [arXiv:2005.07683](https://arxiv.org/abs/2005.07683)
- Hinton, Vinyals & Dean, *Distilling the Knowledge in a Neural Network* — [arXiv:1503.02531](https://arxiv.org/abs/1503.02531)
- Survey: *A Survey on Deep Neural Network Pruning* — [arXiv:2308.06767](https://arxiv.org/abs/2308.06767)

**Unstructured / semi-structured for LLMs**
- Frantar & Alistarh, *SparseGPT*, ICML 2023 — [arXiv:2301.00774](https://arxiv.org/abs/2301.00774)
- Sun, Liu, Bair & Kolter, *Wanda*, ICLR 2024 — [arXiv:2306.11695](https://arxiv.org/abs/2306.11695)
- Yin et al., *OWL*, ICML 2024 — [arXiv:2310.05175](https://arxiv.org/abs/2310.05175)
- Mishra et al., *Accelerating Sparse Deep Neural Networks* — [arXiv:2104.08378](https://arxiv.org/abs/2104.08378)
- Zhou et al., *Learning N:M Sparse Networks from Scratch*, ICLR 2021 — [arXiv:2102.04010](https://arxiv.org/abs/2102.04010)
- *MaskLLM*, NeurIPS 2024 — [arXiv:2409.17481](https://arxiv.org/abs/2409.17481)
- Agarwalla et al., *High-Sparsity Foundational Llama Models* — [arXiv:2405.03594](https://arxiv.org/abs/2405.03594)

**Structured**
- Ma, Fang & Wang, *LLM-Pruner*, NeurIPS 2023 — [arXiv:2305.11627](https://arxiv.org/abs/2305.11627)
- Kurtic et al., *ZipLM*, NeurIPS 2023 — [arXiv:2302.04089](https://arxiv.org/abs/2302.04089)
- Kurtic et al., *The Optimal BERT Surgeon* — [arXiv:2203.07259](https://arxiv.org/abs/2203.07259)
- An et al., *FLAP* — [arXiv:2312.11983](https://arxiv.org/abs/2312.11983)
- *LoRAPrune* — [arXiv:2305.18403](https://arxiv.org/abs/2305.18403) · *LoRAShear* — [arXiv:2310.18356](https://arxiv.org/abs/2310.18356)
- *SlimGPT* — [arXiv:2412.18110](https://arxiv.org/abs/2412.18110)
- Xia, Gao, Zeng & Chen, *Sheared LLaMA*, ICLR 2024 — [arXiv:2310.06694](https://arxiv.org/abs/2310.06694)
- Ashkboos et al., *SliceGPT*, ICLR 2024 — [arXiv:2401.15024](https://arxiv.org/abs/2401.15024)
- Muralidharan et al., *Minitron*, NeurIPS 2024 — [arXiv:2407.14679](https://arxiv.org/abs/2407.14679) · [practice](https://arxiv.org/abs/2408.11796)

**Depth**
- Men et al., *ShortGPT* — [arXiv:2403.03853](https://arxiv.org/abs/2403.03853)
- Gromov et al., *The Unreasonable Ineffectiveness of the Deeper Layers* — [arXiv:2403.17887](https://arxiv.org/abs/2403.17887)
- Kim et al., *Shortened LLaMA* — [arXiv:2402.02834](https://arxiv.org/abs/2402.02834)
- Yang et al., *LaCo*, EMNLP Findings 2024 — [arXiv:2402.11187](https://arxiv.org/abs/2402.11187)
- *SLEB* — [arXiv:2402.09025](https://arxiv.org/abs/2402.09025)

**Heads / neurons / task / domain**
- Michel, Levy & Neubig, NeurIPS 2019 — [arXiv:1905.10650](https://arxiv.org/abs/1905.10650)
- Voita et al., ACL 2019 — [arXiv:1905.09418](https://arxiv.org/abs/1905.09418)
- Liu et al., *Deja Vu*, ICML 2023 — [arXiv:2310.17157](https://arxiv.org/abs/2310.17157)
- **Zhang et al., *Pruning as a Domain-specific LLM Extractor* (D-Pruner), NAACL Findings 2024 — [arXiv:2405.06275](https://arxiv.org/abs/2405.06275) · [ACL](https://aclanthology.org/2024.findings-naacl.91/)**

**Hardware**
- NVIDIA, *A100 Tensor Core GPU Architecture* — [whitepaper](https://images.nvidia.com/aem-dam/en-zz/Solutions/data-center/nvidia-ampere-architecture-whitepaper.pdf)
- NVIDIA, *Accelerating Inference with Sparsity Using Ampere and TensorRT* — [blog](https://developer.nvidia.com/blog/accelerating-inference-with-sparsity-using-ampere-and-tensorrt/)
- Dettmers et al., *QLoRA*, NeurIPS 2023 — [arXiv:2305.14314](https://arxiv.org/abs/2305.14314)
