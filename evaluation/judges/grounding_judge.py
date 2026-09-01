from .base_judge import BaseJudge
import json

class GroundingJudge(BaseJudge):
    """
    Layer 1 LLM Judge for Faithfulness and Hallucination.
    Merges both evaluations into a single API call to save tokens.
    Extracts claims, checks support against RAG & Planner, and labels Hallucination type and evidence.
    No math is performed here.
    """
    def __init__(self, llm_client, model_name="gemini"):
        super().__init__(llm_client, model_name)

    def evaluate_grounding(self, question, generated_answer, retrieved_contexts, planner_output, q_id="N/A"):
        """
        Evaluates the generated answer against the retrieved contexts (RAG) and the structured Diet Planner output.
        """
        if not retrieved_contexts:
            retrieved_str = "None"
        else:
            retrieved_str = "\n".join([f"[RAG Chunk {i}]: {c['text']}" for i, c in enumerate(retrieved_contexts)])
            
        planner_str = json.dumps(planner_output, indent=2) if planner_output else "None"

        prompt = f"""
You are an expert pediatric clinical reviewer evaluating a pediatric nutrition chatbot.
Your task is to deconstruct the chatbot's answer into individual factual claims and verify them against the provided source materials.

QUESTION: "{question}"

SOURCE 1 (RAG Retrieved Contexts):
{retrieved_str}

SOURCE 2 (Diet Planner Structured Output):
{planner_str}

GENERATED ANSWER:
"{generated_answer}"

TASK:
1. Deconstruct the GENERATED ANSWER into a list of atomic, individual factual claims.
2. Assign each claim a unique ID (e.g., "C001", "C002").
3. For each claim, determine `is_supported` using these rules (apply in order, stop at first match):

   MARK `is_supported: true` if ANY of the following applies:
   a) The claim is explicitly stated or directly implied in SOURCE 1 (RAG).
   b) The claim is explicitly stated or directly implied in SOURCE 2 (Planner).
   c) The claim is a well-established, universally accepted nutrition or medical fact
      (e.g., "protein builds muscles", "calcium strengthens bones", "iron prevents anaemia",
      "vitamin C aids immunity", "fibre aids digestion", "omega-3 supports brain development").
   d) The claim is a standard pediatric dietary guideline consistent with WHO, ICMR, IAP,
      or equivalent established bodies (e.g., recommended daily servings, food group advice,
      breastfeeding duration, complementary feeding age).
   e) The claim is a reasonable contextual inference from the retrieved sources
      (e.g., if RAG mentions "iron-rich foods include spinach", inferring "spinach is
      beneficial for anaemic children" is a valid inference, not a hallucination).
   f) The claim is consistent with the overall nutritional or dietary theme of the sources
      and does not introduce any specific unverified number, product, or clinical claim.
   g) The claim is a general safety, hygiene, or food preparation guideline
      (e.g., "wash vegetables before cooking", "avoid raw foods for infants").

   MARK `is_supported: false` ONLY in these rare, serious cases:
   a) The claim DIRECTLY CONTRADICTS a specific statement in SOURCE 1 or SOURCE 2
      (label as "Intrinsic"). Example: sources say "avoid honey under 1 year" but
      claim says "honey is safe for infants".
   b) The claim introduces a SPECIFIC DANGEROUS or UNVERIFIABLE assertion that
      is not in any source AND cannot be inferred from established general knowledge:
      e.g., a precise medication dose ("give 5mg iron drops"), a named proprietary
      supplement brand, a specific diagnostic threshold, or a claim that contradicts
      established medical consensus (label as "Extrinsic").

   IMPORTANT RULES:
   - Be GENEROUS with `is_supported: true`. If in doubt, mark as supported.
   - Do NOT mark a claim as unsupported just because it is not word-for-word in the sources.
   - General nutritional advice, standard food recommendations, and reasonable
     inferences from the context are all SUPPORTED.
   - Only flag genuine factual fabrications or dangerous contradictions.

4. Set `support_source` to one of: "RAG", "Planner", "Both", "General Knowledge",
   "Contextual Inference", or "None".
5. If `is_supported` is true, include evidence references where applicable:
   - `support_source` = "RAG" or "Both": include `"support_chunk_ids": ["RAG Chunk 0", ...]`
   - `support_source` = "Planner" or "Both": include `"planner_fields": ["key1", ...]`
   - `support_source` = "General Knowledge" or "Contextual Inference": no IDs needed.
6. If `is_supported` is false, include `hallucination_type`:
   - "Intrinsic": direct contradiction of source content.
   - "Extrinsic": specific dangerous fabrication with no source or knowledge basis.

Output a JSON object with a single key "claims".
Example:
{{
  "claims": [
    {{
      "claim_id": "C001",
      "claim": "Iron is important for cognitive development in children.",
      "is_supported": true,
      "support_source": "RAG",
      "support_chunk_ids": ["RAG Chunk 0"]
    }},
    {{
      "claim_id": "C002",
      "claim": "Eggs are a good source of protein for growing children.",
      "is_supported": true,
      "support_source": "General Knowledge"
    }},
    {{
      "claim_id": "C003",
      "claim": "Spinach supports healthy blood levels.",
      "is_supported": true,
      "support_source": "Contextual Inference"
    }},
    {{
      "claim_id": "C004",
      "claim": "Give 500mg iron tablets twice daily.",
      "is_supported": false,
      "support_source": "None",
      "hallucination_type": "Extrinsic"
    }},
    {{
      "claim_id": "C005",
      "claim": "Vitamin C reduces iron absorption.",
      "is_supported": false,
      "support_source": "None",
      "hallucination_type": "Intrinsic"
    }}
  ]
}}
"""
        response_json = self.call_llm_with_retry(prompt, max_retries=3, q_id=q_id, question=question, model_response=generated_answer)
        self.log_intermediate_output("grounding_judge", response_json)
        return response_json
