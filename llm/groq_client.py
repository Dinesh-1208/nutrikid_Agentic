import os

try:
    from groq import Groq
except ImportError:
    Groq = None

class KidsNutriGroqClient:
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

    def generate_response(self, model_id, system_prompt, user_prompt, temperature=0.1, top_p=0.9, max_tokens=1024):
        if self.client is None:
            if Groq is None:
                raise ImportError("The 'groq' library is not installed. Please install it using 'pip install groq'.")
            if not self.api_key:
                raise ValueError("GROQ_API_KEY is not set. Please set it in your environment.")

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
        
        return response.choices[0].message.content
