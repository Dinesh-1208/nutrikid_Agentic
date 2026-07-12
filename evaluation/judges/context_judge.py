from .base_judge import BaseJudge

class ContextJudge(BaseJudge):
    """
    Layer 1 LLM Judge for Context metrics (Precision and Recall).
    Outputs ONLY binary semantic reasoning in JSON format.
    No mathematical computations (MAP@5, etc.) are performed here.
    """
    def __init__(self, llm_client, model_name="gemini"):
        super().__init__(llm_client, model_name)

    def evaluate_precision(self, query, retrieved_contexts, q_id="N/A"):
        """
        Evaluates binary relevance of retrieved chunks for Context Precision.
        Uses MAP@5 methodology (Binary True/False, not graded).
        """
        if not retrieved_contexts:
            return {"relevance_map": []}

        chunks_str = ""
        for i, chunk in enumerate(retrieved_contexts):
            chunks_str += f"[Chunk {i}]: {chunk['text']}\n"

        prompt = f"""
You are an expert pediatric AI reviewer evaluating Information Retrieval.
Your task is to determine if each retrieved chunk is relevant to answering the user's query.

QUERY: "{query}"

RETRIEVED CHUNKS:
{chunks_str}

Evaluate each chunk strictly on whether it contains information that is useful and relevant to answering the query.

Output a JSON object with a single key "relevance_map". 
The value must be a list of objects containing "chunk_id" (integer) and "is_relevant" (boolean true or false).
Example:
{{
  "relevance_map": [
    {{"chunk_id": 0, "is_relevant": true}},
    {{"chunk_id": 1, "is_relevant": false}}
  ]
}}
"""
        response_json = self.call_llm_with_retry(prompt, max_retries=3, q_id=q_id, question=query)
        self.log_intermediate_output("context_precision_judge", response_json)
        return response_json

    def evaluate_recall(self, retrieved_contexts, expected_contexts, q_id="N/A", question="N/A"):
        """
        Evaluates Context Recall using RAGAS statement extraction methodology.
        Extracts facts from expected ground truth and verifies them against retrieved chunks.
        """
        if not expected_contexts:
            return {"facts": []} # Nothing expected
            
        if not retrieved_contexts:
            # If nothing was retrieved, we must still extract facts but they will all be false
            chunks_str = "None"
        else:
            chunks_str = "\n".join([f"[Chunk {i}]: {c['text']}" for i, c in enumerate(retrieved_contexts)])

        expected_str = "\n".join([f"- {e}" for e in expected_contexts])

        prompt = f"""
You are an expert pediatric AI reviewer evaluating Information Retrieval.

EXPECTED CLINICAL KNOWLEDGE (Ground Truth):
{expected_str}

RETRIEVED CHUNKS:
{chunks_str}

TASK:
1. Break down the EXPECTED CLINICAL KNOWLEDGE into atomic, individual factual statements.
2. For each atomic fact, verify whether it is explicitly stated or strongly supported by the RETRIEVED CHUNKS.

Output a JSON object with a single key "facts". 
The value must be a list of objects containing "fact" (string) and "is_present" (boolean true or false).
Example:
{{
  "facts": [
    {{"fact": "Patient requires 5mg amoxicillin.", "is_present": true}},
    {{"fact": "Patient has a peanut allergy.", "is_present": false}}
  ]
}}
"""
        response_json = self.call_llm_with_retry(prompt, max_retries=3, q_id=q_id, question=question)
        self.log_intermediate_output("context_recall_judge", response_json)
        return response_json
