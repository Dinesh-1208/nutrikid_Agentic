import os
import sys
# Load env variables

def verify_gemini():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[-] Error: GEMINI_API_KEY not found in environment or .env file.")
        print("[-] Aborting Gemini API diagnostics.")
        sys.exit(1)
        
    print("[+] GEMINI_API_KEY detected in environment.")
    
    try:
        try:
            import google.generativeai as genai
        except ImportError:
            print("[-] Error: google.generativeai is not installed.")
            sys.exit(1)
        genai.configure(api_key=api_key)
        
        print("[+] Connecting to Gemini API...")
        # Add support for Gemini 2.5 Flash
        model_name = "gemini-2.5-flash"
        model = genai.GenerativeModel(model_name=model_name)
        
        print(f"[+] Querying model: {model_name}...")
        test_prompt = "Verify connection. Response with 'Success' and nothing else."
        response = model.generate_content(test_prompt)
        
        print("\n--- Diagnostic Output ---")
        print(f"* API reachable: YES")
        print(f"* Model name: {model_name}")
        print(f"* Test response: {response.text.strip()}")
        print("--------------------------")
        print("[+] Gemini API connection test passed successfully!")
        
    except Exception as e:
        print(f"[-] Gemini API connection test failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    verify_gemini()
