# Overall Hallucination Rate — Literature Research Audit

**Status: research only. No code, dataset, or notebook changes made. Awaiting approval before any implementation.**

All sources below were fetched fresh in this session (via WebFetch, which saves the raw PDF locally even when its own summarizer cannot parse the binary) and their text extracted directly with `pypdf` — genuine, real, text-native PDFs in every case, no OCR needed. None of this is drawn from memory, blogs, vendor pages, or secondary summaries.

---

## 1. Research Question

Is there a well-established, peer-reviewed RAG/LLM evaluation metric that defines a numeric **hallucination rate** using something equivalent to `unsupported_claims / total_claims`, or an equivalent complement of supported-claim precision — and does any such paper itself treat that complement as a "hallucination rate"?

## 2. Current KidsNutriBite Metric

```python
def calculate_overall_hallucination_rate(claims_list):
    if not claims_list:
        return 0.0
    unsupported = sum(1 for c in claims_list if not c.get("is_supported", True))
    return unsupported / len(claims_list)
```

Pipeline: `Answer → atomic claims (GroundingJudge, one merged LLM call) → support judgment against RAG context + Planner output → unsupported_claims / total_claims`. Currently cites "Ji et al. (2023)" as its paper reference. Shares its input (`claims_list`, from `GroundingJudge.evaluate_grounding`) with `calculate_faithfulness`.

## 3. Candidate Literature

Searched and verified directly, prioritizing peer-reviewed RAG/LLM factuality papers, a clinical/medical hallucination benchmark, and papers already in this project's own citation trail:

| # | Paper | Category |
|---|---|---|
| 1 | Ji et al., "Survey of Hallucination in Natural Language Generation" | Hallucination survey (re-verified from prior turn) |
| 2 | Es et al., "RAGAS" | RAG evaluation (this project's own primary source) |
| 3 | Min et al., "FActScore" | LLM factuality evaluation |
| 4 | Wei et al., "Long-form factuality in large language models" (SAFE) | LLM factuality evaluation |
| 5 | Li et al., "HaluEval" | LLM hallucination benchmark |
| 6 | Manakul et al., "SelfCheckGPT" | LLM hallucination detection |
| 7 | Pal et al., "Med-HALT" | Clinical/medical hallucination benchmark |

## 4. Verified Formulas

### 4.1 Ji et al. (2022/2023) — arXiv:2202.03629, ACM Computing Surveys
- **Metric name**: none (survey paper; Section 4 catalogs *other* papers' metrics: PARENT, Knowledge F1, BVSS, model-based methods).
- **Formula**: none proposed by this paper itself.
- **Directly defines vs. related concept**: Related concept only — defines the intrinsic/extrinsic hallucination *taxonomy* (Section 2.1, page 4: *"there are two main types of hallucinations, namely intrinsic hallucination and extrinsic hallucination"*), does not define a numeric rate.
- **URL**: https://arxiv.org/abs/2202.03629

### 4.2 Es et al. (2023) — RAGAS, arXiv:2309.15217, EACL 2024
- **Metric name**: Faithfulness.
- **Formula** (Section 3, page 3): `F = |V| / |S|` — supported statements / total extracted statements.
- **Numerator**: statements the LLM judged inferable from context. **Denominator**: total extracted statements.
- **Claim unit**: LLM-decomposed atomic statement from the answer.
- **Evidence source**: retrieved context `c(q)`.
- **Reference-free/based**: reference-free (no gold answer).
- **RAG/LLM applicability**: Yes — this is the project's own primary methodological basis.
- **Directly defines vs. related concept**: Defines Faithfulness directly; does **not** define a "hallucination rate." Notably, RAGAS's own Related Work cites Ji et al. (2023) for hallucination background (*"The problem of detecting hallucinations in LLM generated responses has been extensively studied (Ji et al., 2023)"*) and motivates Faithfulness as helping to *"avoid hallucinations"* — but never operationalizes `1 - F` as a named "hallucination rate" metric anywhere in the paper (checked all 6 occurrences of "hallucinat*" in the full text).
- **URL**: https://arxiv.org/abs/2309.15217

### 4.3 Min et al. (2023) — FActScore, EMNLP 2023, arXiv:2305.14251
- **Metric name**: FACTSCORE.
- **Formula** (Section 3.1 "Definition," page 3): `f(y) = (1/|A_y|) · Σ_{a∈A_y} I[a is supported by C]`; `FACTSCORE(M) = E_{x∈X}[f(M_x) | M_x responds]`.
- **Numerator**: atomic facts judged supported by knowledge source `C`. **Denominator**: `|A_y|`, total atomic facts in the response.
- **Claim unit**: "a short sentence conveying one piece of information."
- **Evidence source**: an external knowledge source `C` (e.g. Wikipedia).
- **Reference-free/based**: no gold reference answer; requires an external knowledge source to check against.
- **RAG/LLM applicability**: Yes — designed for long-form LLM generation factuality.
- **Directly defines vs. related concept**: Defines `f(y)` directly as a **precision** metric. The word "hallucinat*" appears exactly once in the entire paper, only inside a bibliography entry title (Shuster et al. 2021) — **the paper never frames its own metric, or its complement, as measuring "hallucination."**
- **URL**: https://arxiv.org/abs/2305.14251

### 4.4 Wei et al. (2024) — SAFE, NeurIPS 2024, arXiv:2403.18802
- **Metric name**: F1@K (built from factual Precision `Prec(y)` and Recall `R_K(y)`).
- **Formula** (Section 5 "F1@K: Extending F1 with recall from human-preferred length," page 6, Eq. 1): `Prec(y) = S(y)/(S(y)+N(y))`; `R_K(y) = min(S(y)/K, 1)`; `F1@K(y) = 2·Prec(y)·R_K(y)/(Prec(y)+R_K(y))` if `S(y)>0`, else `0`.
- **Numerator** (of Prec): `S(y)`, supported facts. **Denominator**: `S(y)+N(y)`, supported + not-supported facts (irrelevant facts explicitly excluded, footnote 7).
- **Claim unit**: individually verifiable "fact" extracted from a long-form response.
- **Evidence source**: their own SAFE pipeline (LLM + Google Search-augmented verification).
- **Reference-free/based**: reference-free (no gold answer); evidence-based via live search.
- **RAG/LLM applicability**: Yes — explicit LLM long-form factuality benchmark (GPT-4, Claude, Gemini, PaLM-2).
- **Directly defines vs. related concept**: Defines `Prec(y)` directly as **factuality**, not hallucination — and the paper **explicitly and deliberately distinguishes the two**: *"We focus on factuality and factual errors, not hallucination, as our proposed evaluation method focuses on determining whether a response is factual with respect to external established knowledge (factuality) rather than whether the response is consistent with the model's internal knowledge (hallucination)"* (page 1, footnote 2). It further states *"it is still unclear how to reliably measure hallucination... in long-form settings"* — i.e., a NeurIPS 2024 paper says outright that what KidsNutriBite's formula measures (external-knowledge-grounding) is a **different concept** from what it calls itself ("hallucination").
- **URL**: https://arxiv.org/abs/2403.18802

### 4.5 Li et al. (2023) — HaluEval, EMNLP 2023, arXiv:2305.11747
- **Metric name**: (detection) Accuracy.
- **Formula**: `Accuracy of classifying whether a sample output contains hallucinated content` (Table 5) — a binary, whole-response classification accuracy, not a ratio over claims within one response. Their headline "19.5%" figure is `977/5000` **whole responses** labeled as containing any hallucination, not a claim-level ratio.
- **Numerator/Denominator**: correctly-classified samples / total samples (a detector's accuracy, not a per-response hallucination degree).
- **Claim unit**: none — unit of analysis is the whole response/sample.
- **Reference-free/based**: uses human-annotated ground-truth hallucination labels.
- **RAG/LLM applicability**: Tests whether an LLM *judge* can detect hallucination, not a RAG response-scoring metric itself.
- **Directly defines vs. related concept**: Different metric entirely — measures a detector's classification accuracy, not a claims-ratio hallucination degree.
- **URL**: https://arxiv.org/abs/2305.11747

### 4.6 Manakul et al. (2023) — SelfCheckGPT, EMNLP 2023, arXiv:2303.08896
- **Metric name**: per-sentence hallucination score `S(i)`.
- **Formula** (Section 5, page 3-4, Eq. 1 for the BERTScore variant): `S(i) ∈ [0.0, 1.0]`, e.g. `S_BERT(i) = 1 - (1/N)·Σ_n max_k B(r_i, s_n^k)` — a continuous score from disagreement across `N` stochastically sampled responses to the same prompt.
- **Numerator/Denominator**: not a discrete count ratio — a continuous consistency score derived from sentence-similarity across samples.
- **Claim unit**: sentence.
- **Evidence source**: **no external reference or retrieved context at all** — purely self-consistency across multiple samples from the same model.
- **Reference-free/based**: reference-free, and crucially *evidence-free* too (no RAG context, no knowledge base).
- **RAG/LLM applicability**: Applicable to any LLM generation; not RAG-specific and does not use retrieved context as evidence at all (fundamentally different mechanism from what KidsNutriBite does).
- **Directly defines vs. related concept**: Defines its own hallucination score directly, but via an entirely different mechanism (self-consistency, continuous score) than KidsNutriBite's (evidence-grounding, binary judgment).
- **URL**: https://arxiv.org/abs/2303.08896

### 4.7 Pal et al. (2023) — Med-HALT, CoNLL 2023, arXiv:2307.15343
- **Metric name**: Accuracy; Pointwise Score.
- **Formula** (Section 5.3, page 6-7, Eq. 1): `S = (1/N)·Σ_i [I(y_i=ŷ_i)·P_c + I(y_i≠ŷ_i)·P_w]` — correct answers on a benchmark task earn `+1`, incorrect answers `-0.25`, averaged.
- **Numerator/Denominator**: not a claims-ratio — a signed-scoring average over multiple-choice/reasoning/retrieval **benchmark questions**.
- **Claim unit**: none — unit of analysis is a benchmark question (reasoning, memory-recall, or "fake test" MCQ item).
- **Reference-free/based**: reference-based against known-correct benchmark answers.
- **RAG/LLM applicability**: Tests LLM medical knowledge/reasoning robustness via structured question sets, not open-ended RAG response scoring.
- **Directly defines vs. related concept**: The clinical-domain hallucination benchmark most relevant to KidsNutriBite's subject matter, but its metric is **not applicable** to this specific formula question — it scores structured-task correctness, not atomic-claim support in a free-text response.
- **URL**: https://arxiv.org/abs/2307.15343

## 5. Paper-by-Paper Comparison

| Paper | Classification |
|---|---|
| Ji et al. (2022/2023) | **DIFFERENT METRIC** — no formula proposed; taxonomy-only. |
| RAGAS / Es et al. (2023) | **COMPLEMENTARY FORMULATION** — `1-F` is arithmetically identical, but the paper itself never makes or endorses this equivalence. |
| FActScore / Min et al. (2023) | **COMPLEMENTARY FORMULATION** — `1-f(y)` is arithmetically identical; paper frames it as precision, never as hallucination (word appears once, only in a bibliography title). |
| SAFE / Wei et al. (2024) | **COMPLEMENTARY FORMULATION, EXPLICITLY REJECTED BY THE AUTHORS AS A HALLUCINATION MEASURE** — `1-Prec(y)` is arithmetically identical; the authors explicitly state their factuality metric is *not* hallucination, and that reliably measuring hallucination in long-form generation is still an open problem. |
| HaluEval (2023) | **DIFFERENT METRIC** — binary whole-response classification accuracy, not a claims ratio. |
| SelfCheckGPT (2023) | **DIFFERENT METRIC** — continuous self-consistency score, no external evidence, different unit and mechanism. |
| Med-HALT (2023) | **NOT APPLICABLE** — structured benchmark-question scoring, not open-ended claim-level response scoring. |

## 6. Best-Supported Methodology

No paper in this search — spanning RAG evaluation (RAGAS), general LLM factuality (FActScore, SAFE), hallucination-specific benchmarks (HaluEval, SelfCheckGPT), and clinical hallucination testing (Med-HALT) — defines a metric literally named "hallucination rate" computed as `unsupported_claims / total_claims`. The closest structural matches (FActScore, SAFE) define the **precision** direction and are silent on or, in SAFE's case, **explicitly opposed to** calling the complement "hallucination." The best-supported methodology for KidsNutriBite's actual mechanism (atomic claim decomposition → binary support judgment against retrieved evidence → ratio) is the FActScore/SAFE precision pattern — which is already what `calculate_faithfulness` implements. `calculate_overall_hallucination_rate` is its arithmetic mirror image, not an independently-sourced metric.

## 7. Recommendation

**B. KEEP BUT RENAME / REFRAME.**

The arithmetic (`unsupported/total`) is not wrong or unjustified — it's the direct complement of a pattern used by two strong, peer-reviewed, highly-cited papers (FActScore, EMNLP 2023; SAFE, NeurIPS 2024). But calling it "Overall Hallucination Rate" is not literature-supported, and one of those two papers explicitly warns against exactly this conflation: SAFE's own authors distinguish "factuality" (external-knowledge grounding — what this metric actually measures) from "hallucination" (internal-consistency — what SelfCheckGPT measures, via a completely different mechanism) and say measuring the latter reliably in long-form settings remains unsolved. Continuing to call KidsNutriBite's grounding-based ratio a "hallucination rate" adopts terminology that a directly relevant NeurIPS 2024 paper says is imprecise for what this kind of metric actually does.

## 8. Exact Citation(s)

- Ji, Z. et al. (2022/2023). "Survey of Hallucination in Natural Language Generation." *ACM Computing Surveys*. arXiv:2202.03629. Section 2.1, page 4 — cite for the intrinsic/extrinsic taxonomy only.
- Min, S. et al. (2023). "FActScore: Fine-grained Atomic Evaluation of Factual Precision in Long Form Text Generation." *EMNLP 2023*. arXiv:2305.14251. Section 3.1, page 3 — cite as the structural precedent for the claim-support ratio pattern (precision framing).
- Wei, J. et al. (2024). "Long-form factuality in large language models." *NeurIPS 2024*. arXiv:2403.18802. Section 5, page 6, Eq. 1; footnote 2, page 1 — cite both for the `Prec(y)=S/(S+N)` structural precedent and for the explicit factuality-vs-hallucination distinction motivating the renaming recommendation.

## 9. Worked Example

Same 3-claim example used for Faithfulness: 2 supported, 1 unsupported.
- Faithfulness (`supported/total`) = 2/3 = 0.6667 — matches RAGAS `F = |V|/|S|` exactly.
- Current "Overall Hallucination Rate" (`unsupported/total`) = 1/3 = 0.3333 — arithmetically `1 - Faithfulness`, matching the structural complement of FActScore's `f(y)` and SAFE's `Prec(y)`, but not a formula either paper names "hallucination rate."

## 10. Implications for KidsNutriBite — judging the current formula fairly

Working through the fairness checklist directly against the code (`evaluation/metrics/grounding_metrics.py`, current state):

- **Whether unsupported claims are defined properly**: **Found a real, previously-unflagged bug here.** `calculate_faithfulness_details` uses `c.get("is_supported", False)` (a claim missing the `is_supported` key defaults to *not* supported), while `calculate_overall_hallucination_rate` uses `not c.get("is_supported", True)` (the same missing key defaults to *supported*, i.e., excluded from the unsupported count). These are supposed to be exact complements on the same `claims_list`, but their opposite default-handling for malformed claims means `faithfulness + overall_hallucination_rate` is **not guaranteed to equal 1.0** when a claim dict is missing the key — a genuine implementation inconsistency, independent of the naming question.
- **Whether every extracted claim should count equally**: Yes, by design — this matches FActScore's explicit assumption #2 ("every atomic fact... has an equal weight of importance"), so unweighted counting is literature-consistent.
- **Whether reference-free grounding is acceptable**: Yes — FActScore, SAFE, and RAGAS all accept "reference-free" to mean "no gold answer required," while still requiring *some* evidence source (knowledge base, search, or retrieved context) to check against. KidsNutriBite's RAG+Planner evidence source fits this same category.
- **Whether planner output counts as evidence**: Not addressed by any of the 7 papers (none combine a deterministic planner with RAG), so this is a genuine KidsNutriBite-specific extension beyond the literature — a documented adaptation (already flagged during the Faithfulness audit), not something the literature endorses or forbids.
- **Whether claim extraction methodology affects the metric**: Yes, substantially — all evidence-based papers (RAGAS, FActScore, SAFE) note this as a real limitation (SAFE: *"since SAFE uses language models to do this, there is the possibility that SAFE can miss certain facts or output incomplete/hallucinated facts"*). KidsNutriBite's single merged extraction+verification LLM call inherits the same class of risk, unquantified.
- **Whether a hallucination "rate" should be claim-weighted**: The literature (FActScore) says claims should be equally weighted, not that the rate itself needs additional weighting — no source suggests a different weighting scheme for this use case.
- **Whether the metric overlaps completely with Faithfulness**: Yes, exactly — `unsupported/total = 1 - supported/total` on the identical claims list. It is mathematically redundant with Faithfulness by construction (aside from the default-handling bug above, which makes them not-quite-exact complements in practice).
- **Whether reporting both Faithfulness and Hallucination Rate is redundant**: Given the above, yes, numerically — but the two names read as independent measurements to a report consumer, so keeping both under clearer, explicitly-linked framing (rather than removing one) is likely more useful for downstream dashboards than confusing.
- **Whether recent RAG papers still use this formulation**: RAGAS (2023) uses the precision framing (Faithfulness) and never separately reports a "hallucination rate." FActScore (2023) and SAFE (2024) both use precision framing exclusively and either don't mention hallucination (FActScore) or explicitly reject conflating it with their formula (SAFE). No paper found in this search reports a metric under the "hallucination rate" name using this ratio.

## 11. What Should Be Changed (pending your approval — not implemented)

1. **Rename/reframe**, not replace, the formula. Suggested direction: something that names what it actually measures (e.g. "Unsupported Claim Rate" or "Ungrounded Claim Rate"), or keep "Hallucination Rate" but with an explicit docstring qualifier making clear it is a grounding-based, project-operational proxy — not the internal-consistency sense of "hallucination" used by SelfCheckGPT/SAFE.
2. **Correct the citation** to stop presenting Ji et al. (2023) as the source of the formula (it isn't) — cite it for the taxonomy only, and cite FActScore/SAFE as the structural precedent for the ratio pattern, with SAFE's own factuality-vs-hallucination distinction noted as the reason for the reframing.
3. **Fix the default-value asymmetry bug** between `calculate_faithfulness_details` (`is_supported` defaults to `False`) and `calculate_overall_hallucination_rate` (`is_supported` defaults to `True`) so the two functions are genuine, guaranteed complements on malformed data.
4. Apply the same silent-zero status-enum fix already done for Faithfulness/Answer Relevancy (not part of this research step, but the natural next step once the naming/citation question is settled — this was the original reason this audit turn started).

None of the above has been implemented. Awaiting your decision on the renaming/reframing direction before touching any code.

## 12. Final Verdict

**KEEP WITH REFRAMING**
