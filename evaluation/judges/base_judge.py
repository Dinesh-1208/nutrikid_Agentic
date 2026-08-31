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

    @staticmethod
    def _classify_api_error(exc):
        """
        Phase 4F: best-effort classification of a judge-call exception, used only
        to decide whether retrying is worth attempting - it never changes what a
        failure ultimately reports (still {"parse_failed": True, "error": ...},
        never a fake 0.0 - see evaluator.py's status-enum handling).

        - "daily_quota_exhausted": the provider's error text names a per-day
          token/request limit (e.g. Groq TPD). Retrying within the same run
          cannot help this - the quota resets on a daily cycle, not by waiting
          seconds - so callers should fail fast instead of burning further
          retries/requests against an already-exhausted daily budget.
        - "rate_limited_transient": a per-minute/short-window throttle (e.g.
          Groq TPM/RPM, generic 429 without a daily-limit phrase). Backoff and
          retry is the correct response here.
        - "other": anything else (network error, malformed response, invalid
          request, etc.) - handled by the existing uniform backoff/retry path.

        This is intentionally a string-matching heuristic, not a dependency on
        provider-specific exception classes, since the project talks to Groq/
        Gemini/OpenRouter/local Transformers through one shared judge interface.
        """
        text = str(exc).lower()
        is_429 = "429" in text or "rate" in text or "ratelimiterror" in type(exc).__name__.lower()
        if is_429 and ("per day" in text or "tpd" in text or "daily" in text or "requests per day" in text):
            return "daily_quota_exhausted"
        if is_429:
            return "rate_limited_transient"
        return "other"

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
                error_class = self._classify_api_error(e)
                print(f"[!] API or Parse Error (Attempt {attempt + 1}/{max_retries}, classified as '{error_class}'): {e}")
                self._log_metadata(attempt, latency, str(e), success=False)

                if error_class == "daily_quota_exhausted":
                    # Phase 4F: a daily token/request quota does not recover within
                    # this run's lifetime - unlike a transient/per-minute throttle,
                    # exponential backoff of a few seconds cannot help, and retrying
                    # only spends further requests against an already-exhausted
                    # daily budget. Fail fast instead of exhausting max_retries.
                    print("[!] Daily quota exhaustion detected - not retryable within this run. Failing fast.")
                    return {"parse_failed": True, "error": str(e), "error_class": error_class}

                if attempt < max_retries - 1:
                    backoff_time = 2 ** attempt  # 1s, 2s, 4s...
                    print(f"[*] Retrying in {backoff_time} seconds...")
                    time.sleep(backoff_time)
                else:
                    print("[!] Max retries reached. Returning failure.")
                    return {"parse_failed": True, "error": str(e), "error_class": error_class}

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
