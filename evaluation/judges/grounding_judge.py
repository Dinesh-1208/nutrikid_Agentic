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
You are an expert pediatric clinical reviewer. 
Your task is to deconstruct a pediatric chatbot's answer into individual factual claims and verify them against the provided source materials to evaluate Faithfulness and Hallucination.

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
3. For each claim, check if it is explicitly supported by SOURCE 1 (RAG) or SOURCE 2 (Planner). Set `is_supported` to true or false.
4. Set `support_source` to "RAG", "Planner", "Both", or "None".
5. If `is_supported` is true, you MUST include evidence references:
   - If `support_source` is "RAG" or "Both", include `"support_chunk_ids": ["RAG Chunk 0", ...]`
   - If `support_source` is "Planner" or "Both", include `"planner_fields": ["key1", "key2", ...]`
6. If `is_supported` is false, you MUST include a key `hallucination_type`. The value must be either:
   - "Intrinsic": The claim directly contradicts information provided in the sources.
   - "Extrinsic": The claim is an unverified addition not present in the sources.

Output a JSON object with a single key "claims".
Example:
{{
  "claims": [
    {{
      "claim_id": "C001",
      "claim": "The patient requires 5mg amoxicillin.",
      "is_supported": true,
      "support_source": "RAG",
      "support_chunk_ids": ["RAG Chunk 0"]
    }},
    {{
      "claim_id": "C002",
      "claim": "Eggs contain protein.",
      "is_supported": true,
      "support_source": "Planner",
      "planner_fields": ["breakfast", "protein"]
    }},
    {{
      "claim_id": "C003",
      "claim": "Peanut butter is safe.",
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
