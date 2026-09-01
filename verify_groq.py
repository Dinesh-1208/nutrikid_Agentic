import os
from llm.llm_client import KidsNutriLLMClient

def verify_groq():
    print("=== Groq Integration Diagnostics ===")

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("[!] GROQ_API_KEY is not set. Please set it in your environment.")
        return
    else:
        print("[*] GROQ_API_KEY found.")

    try:
        import groq
        print(f"[*] 'groq' module found (version: {getattr(groq, '__version__', 'unknown')}).")
    except ImportError:
        print("[!] 'groq' module is not installed. Please install it with 'pip install groq'.")
        return

    client = KidsNutriLLMClient()

    # Phase 4F: print the account's actual live model catalog before testing
    # anything, so a stale symbolic-name mapping can never go unnoticed again
    # (this is exactly the check that would have caught the old
    # "groq_llama70b" -> "llama-3.3-70b-versatile" mismatch ahead of time -
    # see docs/phase4f_groq_judge_configuration.md).
    try:
        from groq import Groq
        raw_client = Groq(api_key=api_key)
        live_models = sorted(m.id for m in raw_client.models.list().data)
        print(f"[*] Live Groq model catalog for this account ({len(live_models)} models):")
        for m in live_models:
            print(f"    - {m}")
    except Exception as e:
        print(f"[!] Could not fetch live model catalog: {e}")

    system_prompt = "You are a helpful pediatric assistant."
    user_prompt = "What is the capital of France? Answer in one word."

    # groq_judge is the project's real default judge backend; groq_llama8b is
    # the optional smaller/faster alternative; groq_llama70b is kept only to
    # prove the deprecated alias still works (it now routes to the same real
    # model as groq_judge, not the old nonexistent llama-3.3-70b-versatile).
    models_to_test = ["groq_judge", "groq_llama8b", "groq_llama70b"]

    for model_name in models_to_test:
        print(f"\n--- Testing Model: {model_name} ---")
        try:
            response, latency = client.generate_response(system_prompt, user_prompt, model_name)
            print(f"Response: {response}")
            print(f"Latency: {latency:.2f} seconds")
            print("[*] Success!")
        except Exception as e:
            print(f"[!] Error calling {model_name}: {e}")

if __name__ == "__main__":
    verify_groq()
