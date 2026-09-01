import os
import time

try:
    from groq import Groq
except ImportError:
    Groq = None

class KidsNutriGroqClient:
    """
    Groq Inference client. Groq is the project's official primary judge
    provider, selectable via "groq_judge" (or "groq_llama8b"/"groq_qwen" for
    smaller/alternate models, or the deprecated "groq_llama70b" alias) -
    see docs/phase4f_groq_judge_configuration.md.
    """
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        if self.api_key and Groq is not None:
            self.client = Groq(api_key=self.api_key)
        else:
            self.client = None
            if self.api_key is None:
                print("WARNING: GROQ_API_KEY not found in environment. Groq calls will fail unless set.")
            if Groq is None:
                print("WARNING: 'groq' module not found. Groq calls will fail unless installed.")

        # Phase 4F: running total of tokens Groq reports as actually consumed by
        # this client instance's calls, purely for quota-visibility/debugging
        # (e.g. comparing the pre-run estimate in docs/phase4f_groq_judge_configuration.md
        # against real usage during a run). Never used to gate/throttle calls -
        # Groq's own 429s remain the sole source of truth for quota state, and
        # this is best-effort (stays None per-call if the SDK response has no
        # usage block, which never changes call behavior).
        self.last_call_tokens = None
        self.total_tokens_used = 0

        # Proactive inter-call pacing, added after a real Kaggle run against a
        # Groq account whose actual limit turned out to be 8,000 tokens per
        # minute (TPM) - confirmed directly from a live 429 error body, not
        # assumed. This project's judge sequence fires 5 calls per evaluated
        # case back-to-back with no spacing; against an 8,000 TPM ceiling that
        # burst alone can exhaust the budget within a single case. Enforcing a
        # minimum spacing between calls keeps sustained throughput under the
        # account's real limit instead of just reacting after the fact (the
        # longer retry backoff in base_judge.py is the reactive half of this
        # fix; this is the proactive half).
        #
        # Sizing: 8,000 TPM with a safety margin (use ~80% = 6,400 tokens/60s)
        # divided by a blended per-call estimate (~800 tokens, per the
        # Context/Grounding/Relevancy/Safety prompt-size accounting in
        # docs/phase4f_groq_judge_configuration.md) works out to roughly one
        # call every 7.5 seconds; rounded up to 8s for a bit more margin.
        # Configurable via GROQ_MIN_CALL_INTERVAL_SECONDS since the real limit
        # is account-specific and this default is evidenced from one specific
        # account's observed TPM, not guaranteed to be everyone's.
        self.min_call_interval_seconds = float(os.getenv("GROQ_MIN_CALL_INTERVAL_SECONDS", "8"))
        self._last_call_started_at = None

    def generate_response(self, model_id, system_prompt, user_prompt, temperature=0.1, top_p=0.9, max_tokens=1024):
        if self.client is None:
            if Groq is None:
                raise ImportError("The 'groq' library is not installed. Please install it using 'pip install groq'.")
            if not self.api_key:
                raise ValueError("GROQ_API_KEY is not set. Please set it in your environment.")

        if self.min_call_interval_seconds > 0 and self._last_call_started_at is not None:
            elapsed = time.time() - self._last_call_started_at
            remaining = self.min_call_interval_seconds - elapsed
            if remaining > 0:
                time.sleep(remaining)
        self._last_call_started_at = time.time()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        response = self.client.chat.completions.create(
            model=model_id,
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens
        )

        # Phase 4F: capture real token usage for quota visibility, best-effort
        # only - never let a missing/unexpected usage shape break a call that
        # otherwise succeeded.
        try:
            usage = getattr(response, "usage", None)
            call_tokens = getattr(usage, "total_tokens", None) if usage is not None else None
            if call_tokens is not None:
                self.last_call_tokens = call_tokens
                self.total_tokens_used += call_tokens
        except Exception:
            pass

        return response.choices[0].message.content
