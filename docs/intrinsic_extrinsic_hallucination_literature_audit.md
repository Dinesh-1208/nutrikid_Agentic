# Intrinsic / Extrinsic Hallucination Rate — Literature Research Audit

**Status: research only. No code, dataset, or notebook changes made. Awaiting your decision before any implementation.**

All sources below were fetched fresh (WebFetch + WebSearch this turn, reusing the already-fetched Ji et al./RAGAS/FActScore/SAFE full texts from prior turns) and, where the PDF was reachable, extracted directly with `pypdf` — genuine primary-source reads, not summaries. Two clinical papers could not be fetched past a login/bot wall (nature.com auth redirect, medRxiv 403, PubMed cookie wall) despite repeated attempts from different entry points; those are explicitly marked **NOT independently verified — identified via WebSearch synthesis only**, per this project's standing rule to never claim verification without actually reading the source.

---

## 1. Research Question

How do major, credible papers actually *quantify* overall, intrinsic, and extrinsic hallucination — as claim-level fractions, response-level containment rates, sentence-level rates, or something else — especially in RAG, LLM factuality, and clinical/medical evaluation? Is KidsNutriBite's `intrinsic_unsupported_claims / total_claims` formulation standard, uncommon, custom, or not generally recommended?

## 2. Major Papers

| # | Paper | Verification |
|---|---|---|
| 1 | Ji et al. (2022/2023), hallucination survey | Direct, full 59-page text (this + prior turn) |
| 2 | Es et al. (2023), RAGAS | Direct, full 8-page text (prior turns) |
| 3 | Min et al. (2023), FActScore | Direct, full 25-page text (prior turn) |
| 4 | Wei et al. (2024), SAFE | Direct, full 72-page text (prior turn) |
| 5 | Maynez et al. (2020), "On Faithfulness and Factuality in Abstractive Summarization" | Direct, full 14-page text (this turn) — **the origin of the intrinsic/extrinsic taxonomy** |
| 6 | Li et al. (2023), HaluEval | Direct (prior turn) |
| 7 | Pal et al. (2023), Med-HALT | Direct (prior turn) |
| 8 | npj Digital Medicine (2025), clinical safety/hallucination framework for medical summarisation | **NOT independently verified** — identified via WebSearch only |
| 9 | JMIR Cancer (2025), cancer-information chatbot hallucination study | **NOT independently verified** — identified via WebSearch only |

## 3. Formula Comparison

| Paper | Metric | Formula | Unit of analysis | Numerator | Denominator |
|---|---|---|---|---|---|
| Ji et al. | (none proposed) | — | — | — | — |
| RAGAS | Faithfulness | `\|V\|/\|S\|` | claim/statement | supported statements | total statements |
| FActScore | FACTSCORE | `f(y)=(1/\|A_y\|)ΣI[supported]` | atomic fact | supported facts | total facts |
| SAFE | Prec(y) | `S(y)/(S(y)+N(y))` | fact | supported facts | supported+unsupported facts |
| **Maynez et al.** | **% Intrinsic / % Extrinsic** | **% of summaries with ≥1 annotated I/E span** | **response (summary)** | **summaries containing ≥1 I or E span** | **total summaries** |
| HaluEval | detection accuracy | correct classifications/total | response | correctly classified responses | total responses |
| KidsNutriBite (current) | Intrinsic/Extrinsic Rate | `type\_unsupported/total\_claims` | claim | claims of that type | total claims |

**No paper in this search computes intrinsic or extrinsic hallucination as a claim-level fraction the way KidsNutriBite does.** The one paper that actually proposes a quantitative intrinsic/extrinsic split (Maynez et al.) does it at the response level, not the claim level.

## 4. Intrinsic Methodology Comparison

### Maynez et al. (2020) — the origin paper

**Maynez, Narayan, Bohnet, McDonald — "On Faithfulness and Factuality in Abstractive Summarization," ACL 2020, arXiv:2005.00661.** This is the paper Ji et al. cites (among others) as the source of the intrinsic/extrinsic categorization — confirmed by comparing definitions directly:

> *"Intrinsic hallucinations are consequences of synthesizing content using the information present in the input document... [terms/concepts from the document but] misrepresent information from the document, making them unfaithful to the document."* (Section 2.1, page 3)

Annotation unit: **text spans** within a summary, marked by 3 human annotators as intrinsic or extrinsic. But the **reported metric** (Table 2, Section 5.2, page 6) is response-level, not span-level or claim-level:

> *"Table 2: Intrinsic vs. Extrinsic Hallucinations. The numbers in "Hallucinated" columns show the percentage of **summaries** where at least one word was annotated by all three annotators as an intrinsic (I) or extrinsic (E) hallucination... column "Faith." [=] 100 - I∪E."*

So: **`% Intrinsic = (summaries with ≥1 intrinsic-labeled span) / (total summaries)`** — a response-level containment rate, computed independently from `% Extrinsic` (a summary can count toward *both* I and E simultaneously if it has spans of both types — I and E are not mutually exclusive partitions of a shared pool the way KidsNutriBite's per-claim labels are).

### Ji et al.'s own explicit verdict on this practice

Directly quoted, Section 6.1 "Future Directions in Metrics Design," **page 15**:

> *"Fine-grained Metrics. Most of the existing hallucination metrics measure intrinsic and extrinsic hallucinations together as a unified metric. However, it is common for a single generation to have both types... Fine-grained metrics that can distinguish between the two types of hallucinations will provide richer insight to researchers... Future work that explores an automatic method of categorization would be beneficial."*

This is decisive: **as of this survey, separately quantifying intrinsic vs. extrinsic hallucination is explicitly characterized as uncommon and as an open future-work direction**, not an established practice. The paper names exactly two exceptions that use "finer-grained metrics for intrinsic hallucination and extrinsic hallucination separately":
- Chen, Zhang, Sone, Roth (2021), "Improving Faithfulness in Abstractive Summarization with Contrast Candidate Generation and Selection," NAACL 2021.
- Nie, Yao, Wang, Pan, Lin (2019), "A Simple Recipe towards Reducing Hallucination in Neural Surface Realisation," ACL 2019.

Both are named by Ji et al. only in passing (not independently fetched/verified in this audit — flagging that limit explicitly); both are summarization/surface-realization mitigation papers, not RAG or clinical evaluation papers.

## 5. Extrinsic Methodology Comparison

Same source, same finding: Maynez et al.'s `% Extrinsic` uses the identical response-level containment-rate structure as `% Intrinsic` (see Section 4). No separate formula exists for extrinsic beyond substituting the span-type filter. Ji et al.'s own explicit "measured together as a unified metric" statement applies equally to both — there is no stronger literature support for a claim-level Extrinsic Rate than for a claim-level Intrinsic Rate.

## 6. Clinical / Medical Examples

Two candidates were identified via WebSearch as directly relevant, peer-reviewed, recent clinical hallucination-rate studies — **neither could be fetched past a login/bot wall in this session** (nature.com redirected to an auth gateway; the medRxiv preprint PDF and abstract page both returned HTTP 403; PubMed served a cookie-consent wall instead of content). Reporting what's known from the search results only, explicitly flagged as unverified against primary text:

- **"A framework to assess clinical safety and hallucination rates of LLMs for medical text summarisation," npj Digital Medicine (2025)** — per the search summary, clinical error metrics were derived from **12,999 clinician-annotated sentences**, reporting a "1.47% hallucination rate." The stated unit ("12,999... sentences") implies a **sentence-level** denominator — Outcome C in the requested denominator taxonomy — distinct from both KidsNutriBite's claim-level and Maynez's response-level approaches. **Not independently verified**; whether it splits intrinsic/extrinsic numerically is unknown from the search summary alone.
- **Cancer-information chatbot hallucination study, JMIR Cancer (2025)** — per the search summary, reports hallucination rates as percentages of *responses* (0% GPT-4/CIS-sourced, 6% GPT-3.5/CIS-sourced, 6%/10% Google-sourced, ~40% for non-RAG chatbots) — a **response-level** containment rate, matching Maynez's and HaluEval's pattern (Outcome B). **Not independently verified.**

Both data points, even unverified in detail, corroborate the same pattern already established from directly-verified sources: **real hallucination-rate reporting in the literature — including in medical contexts — tends to use response-level or sentence-level denominators, not claim-level fractions**, and I found no clinical source (verified or not) reporting a claim-level intrinsic/extrinsic split matching KidsNutriBite's exact formula.

## 7. Denominator Comparison — why these are not interchangeable

**A. Per-claim rate** (`unsupported claims / total claims`) — KidsNutriBite's current approach for Intrinsic/Extrinsic. Continuous per-response value; a response with 10 claims and 1 unsupported scores 10%.

**B. Per-response rate** (`responses with ≥1 hallucination / total responses`) — Maynez et al.'s actual methodology; also HaluEval's "19.5% of responses"; also the (unverified) cancer-chatbot study; also **already what KidsNutriBite's own `comparator.py` computes** for its separate `"Hallucination Rate"`/`"Overall Hallucination Rate"` report labels (flagged as a distinct, untouched statistic in the previous audit turn). Binary per response — the same 10-claims/1-unsupported response scores 100% ("this response is hallucinated"), not 10%.

**C. Sentence-level rate** (`hallucinated sentences / total sentences`) — the (unverified) npj Digital Medicine clinical study's apparent approach; SelfCheckGPT's continuous per-sentence score is a cousin of this (Section 4.6 of the Overall Hallucination Rate audit).

**Why they cannot be mixed**: these measure fundamentally different things and produce numbers that are not comparable or convertible into one another without additional information (how many claims/sentences per response, how hallucinations cluster within a response). A system could have a *low* per-claim rate (few claims wrong) but a *high* per-response rate (almost every response has at least one wrong claim) — both are true and neither is "the" hallucination rate. KidsNutriBite currently reports **both** kinds simultaneously under confusingly similar names — the claim-level Intrinsic/Extrinsic Rate in `grounding_metrics.py`, and the response-level containment rate in `comparator.py`'s `"Hallucination Rate"` — without documentation distinguishing them, which is itself a finding worth flagging: a reader comparing these two numbers today would reasonably (and wrongly) assume they measure the same thing at different granularities of type-breakdown.

## 8. KidsNutriBite Comparison

```
Answer → GroundingJudge → atomic claims → is_supported + hallucination_type (Intrinsic/Extrinsic) → Python ratio (type_count / total_claims)
```

- **Category labels** ("Intrinsic"/"Extrinsic" applied per-claim): **EXACT** match to Ji et al.'s and Maynez et al.'s definitions (already confirmed in the prior turn for Intrinsic specifically; Extrinsic's KidsNutriBite prompt wording — "an unverified addition not present in the sources" — is a reasonable paraphrase of Maynez's/Ji et al.'s "cannot be verified... neither supported nor contradicted").
- **The claim-level `type/total_claims` ratio formula**: **NOT SUPPORTED** by any paper found in this search as a standard or even common practice. The one paper that actually proposes a quantitative intrinsic/extrinsic split (Maynez et al.) uses a structurally different unit of analysis (response-level containment, not claim-level fraction, and not mutually-exclusive between I and E). Ji et al.'s own survey explicitly states this kind of fine-grained separate quantification is uncommon and an open future-work item, naming only two non-RAG, non-clinical exception papers.

Overall classification: **CUSTOM** — weaker literature grounding than even the (already project-operational) Unsupported Claim Rate had, because there the *arithmetic structure* was still corroborated by FActScore/SAFE at the same unit of analysis (claim-level). Here, the one paper with a comparable *quantitative* treatment uses a different unit of analysis entirely, and the survey paper itself flags separate quantification as non-standard.

## 9. Recommendation

**C. KEEP THE TAXONOMY BUT STOP REPORTING SEPARATE NUMERIC RATES** as continuous claim-level fractions.

Reasoning: the per-claim **label** ("this unsupported claim is Intrinsic/Extrinsic") is literature-exact and diagnostically valuable — it already surfaces usefully in `hallucination_analysis.md`'s per-case claims table, letting a reviewer see *why* a claim failed. But turning that label into an aggregate `type_count/total_claims` **rate**, reported as if it were a validated metric alongside Faithfulness/Unsupported Claim Rate, is not supported by the literature: Ji et al. itself calls this practice uncommon and unresolved, and the one paper that does compute quantitative intrinsic/extrinsic numbers (Maynez et al.) does so at a different, response-level unit of analysis that isn't a drop-in match for KidsNutriBite's claim-level pipeline.

**Runner-up, credible alternative — B. KEEP BUT CHANGE THE FORMULA** to Maynez et al.'s actual response-level containment-rate pattern (`% of responses containing ≥1 intrinsic claim`, `% of responses containing ≥1 extrinsic claim`). This has the advantage of being genuinely literature-backed (the strongest direct precedent found) and would make KidsNutriBite's hallucination-related reporting internally consistent, since `comparator.py` already computes an (currently undocumented, differently-named) response-level rate for the aggregate hallucination flag. If you'd rather keep numeric intrinsic/extrinsic reporting than drop it, this is the defensible way to do it — but it is a **different metric with a different denominator**, not a fix to the current formula.

Not recommending A (current formula lacks the literature support the audit was specifically checking for), D (no single published metric is a clean drop-in replacement for KidsNutriBite's specific claim-level RAG+Planner architecture), or E (the taxonomy itself remains valuable and well-supported; removing it entirely would lose real diagnostic value beyond what the numeric-rate question actually calls into doubt).

## 10. Exact Citations

- Ji, Z. et al. (2022/2023). "Survey of Hallucination in Natural Language Generation." *ACM Computing Surveys*. arXiv:2202.03629. Section 2.1 (taxonomy), page 4; Section 6.1 (explicit "measured together as a unified metric... future direction" statement), page 15.
- Maynez, J., Narayan, S., Bohnet, B., McDonald, R. (2020). "On Faithfulness and Factuality in Abstractive Summarization." *ACL 2020*. arXiv:2005.00661. Section 2.1 (definitions), page 3; Section 5.2 and Table 2 (the response-level % I/% E formula), page 6.
- Chen, S., Zhang, F., Sone, K., Roth, D. (2021). "Improving Faithfulness in Abstractive Summarization with Contrast Candidate Generation and Selection." *NAACL 2021*. (Named by Ji et al. as a fine-grained-metric exception; not independently verified in this audit.)
- Nie, F., Yao, J.-G., Wang, J., Pan, R., Lin, C.-Y. (2019). "A Simple Recipe towards Reducing Hallucination in Neural Surface Realisation." *ACL 2019*. (Same status as above.)
- (Unverified, WebSearch-identified only) "A framework to assess clinical safety and hallucination rates of LLMs for medical text summarisation." *npj Digital Medicine* (2025).
- (Unverified, WebSearch-identified only) Cancer-information chatbot hallucination study, *JMIR Cancer* (2025).

## 11. Final Decision

**C. KEEP THE TAXONOMY BUT STOP REPORTING SEPARATE NUMERIC RATES**

(Alternative if you prefer to retain numeric reporting: **B**, reformulated to match Maynez et al.'s response-level containment-rate methodology — a different denominator, not a fix to the current one.)

Nothing has been implemented. Awaiting your decision before touching `calculate_intrinsic_hallucination_rate`, `calculate_extrinsic_hallucination_rate`, or any related reporting/evaluator/comparator code.
