import os
import json
import time
import re

def safe_parse_json(response_text, q_id="N/A", question="N/A", model_response="N/A"):
    # 1. Save raw response to reports/judge_raw_outputs.log
    try:
        os.makedirs("reports", exist_ok=True)
        with open("reports/judge_raw_outputs.log", "a", encoding="utf-8") as f:
            f.write(f"--- TIMESTAMP: {time.strftime('%Y-%m-%d %H:%M:%S')} | Q_ID: {q_id} ---\n")
            f.write(response_text)
            f.write("\n\n")
    except Exception as log_err:
        print(f"[!] Warning: Failed to write to raw outputs log: {log_err}")
        
    extracted = response_text.strip()
    
    # 2. Extract JSON from markdown or text wrapper
    code_block_match = re.search(r'```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```', extracted, re.DOTALL | re.IGNORECASE)
    if code_block_match:
        extracted = code_block_match.group(1)
    else:
        # Match either an object or an array
        brace_match = re.search(r'(\{.*\}|\[.*\])', extracted, re.DOTALL)
        if brace_match:
            extracted = brace_match.group(1)
            
    # 3. Parse JSON
    try:
        return json.loads(extracted)
    except json.JSONDecodeError as err:
        print(f"[!] JSON parsing failed: {err}. Attempting repair...")
        
        # Simple repair logic for unescaped quotes inside known keys
        repaired = extracted
        keys_to_check = ["reason", "reasoning", "claim", "relevance_map", "claims", "classification", "violation_type"]
        for key in keys_to_check:
            pattern = rf'("{key}"\s*:\s*")(.*?)("\s*(?:,|\Z|\n|\r|}}))'
            def replace_quotes(match):
                prefix, val, suffix = match.groups()
                val_clean = val.replace('\\"', 'TEMP_ESC_QUOTE')
                val_clean = val_clean.replace('"', "'")
                val_clean = val_clean.replace('TEMP_ESC_QUOTE', '\\"')
                return f"{prefix}{val_clean}{suffix}"
            repaired = re.sub(pattern, replace_quotes, repaired, flags=re.DOTALL)
            
        # Clean invalid control characters/tabs
        repaired = repaired.replace('\t', ' ')
            
        try:
            return json.loads(repaired)
        except json.JSONDecodeError as final_err:
            print(f"[!] JSON parsing failed after repair. Logging failure to reports/judge_parse_failures.csv.")
            try:
                csv_path = "reports/judge_parse_failures.csv"
                file_exists = os.path.exists(csv_path)
                with open(csv_path, "a", encoding="utf-8", newline="") as csvfile:
                    import csv
                    writer = csv.writer(csvfile)
                    if not file_exists:
                        writer.writerow(["Question ID", "Question", "Raw Output", "Parse Error"])
                    writer.writerow([q_id, question, response_text, f"{final_err}"])
            except Exception as csv_err:
                pass
            return {"parse_failed": True}

class BaseJudge:
    """
    Base class for all LLM Judges. 
    Handles API calls, robust JSON parsing, intermediate file logging, and retries.
    """
    def __init__(self, llm_client, model_name="gemini"):
        self.llm_client = llm_client
        self.model_name = model_name
        self.debug_dir = "reports/debug"
        os.makedirs(self.debug_dir, exist_ok=True)

    def log_intermediate_output(self, metric_name, data):
        """Saves intermediate JSON responses for debugging/tracing."""
        try:
            filepath = os.path.join(self.debug_dir, f"{metric_name}_latest.json")
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[!] Warning: Failed to write debug log for {metric_name}: {e}")

    def call_llm_with_retry(self, prompt, max_retries=3, q_id="N/A", question="N/A", model_response="N/A"):
        """Calls the LLM with exponential backoff and parses JSON."""
        if self.model_name == "gemini" and not self.llm_client.gemini_key:
            raise ValueError("Error: GEMINI_API_KEY not found. Real Gemini inference is required for evaluator judge.")
            
        enforced_prompt = (
            prompt + 
            "\n\nReturn ONLY valid JSON. Do not use markdown wrappers unless specifying json. "
            "Do not include explanations outside the JSON."
        )
        
        system_instruction = "You are an objective AI evaluator. Return ONLY valid JSON."
        
        for attempt in range(max_retries):
            start_time = time.time()
            try:
                res_text, _ = self.llm_client.generate_response(
                    system_instruction, 
                    enforced_prompt, 
                    model_name=self.model_name
                )
                
                latency = time.time() - start_time
                
                # Check for empty response
                if not res_text or not res_text.strip():
                    raise ValueError("Received empty response from API.")
                
                parsed_json = safe_parse_json(res_text, q_id=q_id, question=question, model_response=model_response)
                
                if isinstance(parsed_json, dict) and parsed_json.get("parse_failed"):
                    raise ValueError("JSON parsing failed (malformed JSON returned).")
                
                # Log success metadata
                self._log_metadata(attempt, latency, res_text, success=True)
                
                return parsed_json
                
            except Exception as e:
                latency = time.time() - start_time
                print(f"[!] API or Parse Error (Attempt {attempt + 1}/{max_retries}): {e}")
                self._log_metadata(attempt, latency, str(e), success=False)
                
                if attempt < max_retries - 1:
                    backoff_time = 2 ** attempt  # 1s, 2s, 4s...
                    print(f"[*] Retrying in {backoff_time} seconds...")
                    time.sleep(backoff_time)
                else:
                    print("[!] Max retries reached. Returning failure.")
                    return {"parse_failed": True, "error": str(e)}

    def _log_metadata(self, attempt, latency, response, success):
        """Logs latency, retries, and raw text."""
        log_entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "model_name": self.model_name,
            "attempt": attempt + 1,
            "latency_sec": round(latency, 2),
            "success": success,
            "response_snippet": response[:200] + "..." if len(response) > 200 else response
        }
        self.log_intermediate_output("llm_call_metadata", log_entry)

    def _call_judge(self, prompt, q_id="N/A", question="N/A", model_response="N/A"):
        """Deprecated: Use call_llm_with_retry instead. Kept for short-term compatibility if needed."""
        return self.call_llm_with_retry(prompt, 1, q_id, question, model_response)
