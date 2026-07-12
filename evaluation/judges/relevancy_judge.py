from .base_judge import BaseJudge

class RelevancyJudge(BaseJudge):
    """
    Layer 1 LLM Judge for Answer Relevancy.
    This judge is responsible ONLY for reverse-engineering hypothetical questions from the generated answer.
    No embedding mathematics or cosine similarities are calculated here.
    """
    def __init__(self, llm_client, model_name="gemini"):
        super().__init__(llm_client, model_name)

    def generate_hypothetical_questions(self, generated_answer, num_questions=3, q_id="N/A"):
        """
        Reads the generated answer and generates N hypothetical questions that this answer appears to resolve.
        Forces deterministic LLM generation parameters for reproducibility.
        """
        # Save original generation config
        original_temp = self.llm_client.gen_config.get("temperature", 0.1)
        original_top_p = self.llm_client.gen_config.get("top_p", 0.9)
        
        # Force deterministic generation
        self.llm_client.gen_config["temperature"] = 0.0
        self.llm_client.gen_config["top_p"] = 1.0

        prompt = f"""
You are an expert in Information Retrieval and Semantic Evaluation.
Your task is to reverse-engineer a set of hypothetical questions based strictly on the provided answer.

GENERATED ANSWER:
"{generated_answer}"

TASK:
Assume you do not know what the original user asked. 
Based ONLY on the information provided in the GENERATED ANSWER, generate exactly {num_questions} potential hypothetical questions that this answer perfectly resolves.
If the answer is rambling or evasive, the hypothetical questions should reflect that rambling nature.

Output a JSON object with a single key "generated_questions".
The value must be an array of exactly {num_questions} objects, each containing a "question_id" (e.g., "Q1", "Q2") and "text" (the string question).

Example:
{{
  "generated_questions": [
    {{
      "question_id": "Q1",
      "text": "What is the recommended dosage of amoxicillin for a 5-year-old?"
    }},
    {{
      "question_id": "Q2",
      "text": "How often should amoxicillin be administered?"
    }}
  ]
}}
"""
        try:
            response_json = self.call_llm_with_retry(prompt, max_retries=3, q_id=q_id, model_response=generated_answer)
            self.log_intermediate_output("relevancy_judge", response_json)
            return response_json
        finally:
            # Revert to original config
            self.llm_client.gen_config["temperature"] = original_temp
            self.llm_client.gen_config["top_p"] = original_top_p
