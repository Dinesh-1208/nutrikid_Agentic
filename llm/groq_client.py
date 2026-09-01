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

        # Root cause (confirmed via a live direct API test against
        # openai/gpt-oss-120b): GPT-OSS is a reasoning model, and Groq's
        # completion budget is shared between its internal reasoning tokens
        # and the final visible answer. The direct test proved this
        # concretely - with a small completion budget, the model returned
        # completion_tokens=20, reasoning_tokens=18, and empty visible
        # content: reasoning alone consumed nearly the entire budget before
        # any answer text could be produced. This is a real API-usage
        # behavior, not a bug in this project's retry/parsing logic - a
        # judge call can succeed at the HTTP level and still return nothing
        # usable.
        #
        # Two independent controls address this, both real Groq
        # chat-completions parameters (verified against the installed groq
        # SDK's actual create() signature, not assumed):
        #
        # - reasoning_effort: this project's judge tasks (binary chunk
        #   relevance, atomic-claim decomposition + support verification,
        #   a fixed safety rubric, reverse-engineering N hypothetical
        #   questions) are bounded extraction/classification tasks with an
        #   explicit output schema and a worked example in every prompt -
        #   not open-ended multi-step reasoning. "low" is deliberately
        #   chosen over the API's higher defaults so more of the completion
        #   budget goes to the visible JSON instead of internal reasoning.
        #   Raise GROQ_JUDGE_REASONING_EFFORT if judge output quality ever
        #   indicates more reasoning depth is actually needed.
        # - reasoning_format="hidden": keeps whatever reasoning the model
        #   still performs out of the returned `content` string entirely,
        #   so content is exactly the judge's final JSON - nothing to strip
        #   out before parsing.
        self.judge_reasoning_effort = os.getenv("GROQ_JUDGE_REASONING_EFFORT", "low")
        self.judge_reasoning_format = os.getenv("GROQ_JUDGE_REASONING_FORMAT", "hidden")

        # Completion budget (max_completion_tokens) must cover BOTH the
        # reasoning tokens above AND the largest judge's visible JSON. Sized
        # against this project's four judge schemas (evaluation/judges/):
        # ContextJudge (relevance_map / facts lists, ~5-15 short objects),
        # RelevancyJudge (exactly num_questions=3 short objects),
        # SafetyJudge (4 booleans + one CoT "reasoning" string field written
        # directly into the JSON schema + one classification label) - all
        # comfortably a few hundred tokens - and GroundingJudge, which is
        # the largest and previously the most failure-prone: it asks for a
        # "claims" array with one object per atomic factual claim in the
        # generated answer (claim text, support flags, evidence
        # references), which can run to a dozen or more claims for a
        # thorough answer. 2048 gives real margin over that worst case plus
        # "low"-effort reasoning overhead, without being an unbounded or
        # reckless ceiling - it is a maximum the model can stop well short
        # of, not a fixed cost. Previously this value was not Groq-specific
        # at all - it silently reused self.gen_config["max_new_tokens"]
        # (1024), a setting sized for local Transformers answer generation
        # with no relationship to Groq's reasoning-model token accounting.
        self.judge_max_completion_tokens = int(os.getenv("GROQ_JUDGE_MAX_COMPLETION_TOKENS", "2048"))

    def generate_response(self, model_id, system_prompt, user_prompt, temperature=0.1, top_p=0.9,
                           max_tokens=None, reasoning_effort=None, reasoning_format=None):
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

        # None means "use this instance's judge defaults" (see __init__) -
        # an explicit value from the caller always wins. The completion
        # budget is safe to raise for any model (it is only a ceiling the
        # model can stop well short of), so it applies universally.
        if max_tokens is None:
            max_tokens = self.judge_max_completion_tokens

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        create_kwargs = dict(
            model=model_id,
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens
        )

        # reasoning_effort/reasoning_format are GPT-OSS-specific reasoning
        # controls (see __init__) - only send them for the openai/gpt-oss-*
        # model family this project actually routes judge calls to
        # ("groq_judge"/"groq_llama70b" -> openai/gpt-oss-120b,
        # "groq_llama8b" -> openai/gpt-oss-20b). Other Groq model families
        # (e.g. "groq_qwen" -> qwen/qwen3.6-27b) are not confirmed to accept
        # these fields, so they are omitted for anything outside this
        # family rather than risk an API-level rejection on an unrelated
        # model this fix was never meant to touch.
        if model_id.startswith("openai/gpt-oss"):
            create_kwargs["reasoning_effort"] = reasoning_effort if reasoning_effort is not None else self.judge_reasoning_effort
            create_kwargs["reasoning_format"] = reasoning_format if reasoning_format is not None else self.judge_reasoning_format

        response = self.client.chat.completions.create(**create_kwargs)

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
