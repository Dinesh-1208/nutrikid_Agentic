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
    
    system_prompt = "You are a helpful pediatric assistant."
    user_prompt = "What is the capital of France? Answer in one word."

    models_to_test = ["groq_llama8b", "groq_llama70b", "groq_qwen"]
    
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
