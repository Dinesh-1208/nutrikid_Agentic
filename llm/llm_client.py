import os
import time
import requests
try:
    import google.generativeai as genai
except ImportError:
    genai = None
class KidsNutriLLMClient:
    def __init__(self, default_model="gemini"):
        self.default_model = default_model
        
        # Load API keys from environment
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY")
        self.groq_client_instance = None
        
        # Configure Gemini if key is present
        if self.gemini_key and genai is not None:
            genai.configure(api_key=self.gemini_key)
        elif self.gemini_key is None:
            print("WARNING: GEMINI_API_KEY not found in environment. Gemini calls will fail unless set.")
        if genai is None:
            print("WARNING: google.generativeai module not found. Gemini calls will fail unless installed.")

        # Model cache to load tokenizer and model only once (CHANGE 1)
        self.loaded_models = {}
        
        # Configurable generation settings (CHANGE 2)
        self.gen_config = {
            "temperature": 0.1,  # 0.1 for deterministic benchmarking outputs
            "top_p": 0.9,
            "max_new_tokens": 1024
        }

    def generate_response(self, system_prompt, user_prompt, model_name=None):
        if model_name is None:
            model_name = self.default_model
            
        model_name = model_name.lower().strip()
        start_time = time.time()
        
        # Enforce real model inference and abort if credentials/hardware are missing
        if model_name == "gemini":
            if not self.gemini_key:
                raise ValueError("Error: GEMINI_API_KEY not found. Real Gemini inference is required.")
            response_text = self._call_gemini(system_prompt, user_prompt)
            
        elif model_name == "qwen":
            if not self.openrouter_key:
                raise ValueError("Error: OPENROUTER_API_KEY not found. Real Qwen API inference is required.")
            response_text = self._call_openrouter("qwen/qwen-2.5-7b-instruct", system_prompt, user_prompt)
            
        elif model_name == "llama":
            if not self.openrouter_key:
                raise ValueError("Error: OPENROUTER_API_KEY not found. Real Llama API inference is required.")
            response_text = self._call_openrouter("meta-llama/llama-3.1-8b-instruct", system_prompt, user_prompt)
            
        elif model_name == "qwen_local":
            try:
                import torch
            except ImportError:
                raise ImportError("Error: 'torch' is not installed. Please run 'pip install torch'.")
            if not torch.cuda.is_available():
                raise RuntimeError("Error: CUDA GPU not detected. Real local Qwen inference requires a GPU.")
            response_text = self._call_local_transformers("Qwen/Qwen2.5-7B-Instruct", system_prompt, user_prompt)
            
        elif model_name == "llama_local":
            try:
                import torch
            except ImportError:
                raise ImportError("Error: 'torch' is not installed. Please run 'pip install torch'.")
            if not torch.cuda.is_available():
                raise RuntimeError("Error: CUDA GPU not detected. Real local Llama inference requires a GPU.")
            response_text = self._call_local_transformers("meta-llama/Llama-3.1-8B-Instruct", system_prompt, user_prompt)
            
        elif model_name == "groq_llama70b":
            response_text = self._call_groq("llama-3.3-70b-versatile", system_prompt, user_prompt)
            
        elif model_name == "groq_llama8b":
            response_text = self._call_groq("llama-3.1-8b-instant", system_prompt, user_prompt)
            
        elif model_name == "groq_qwen":
            response_text = self._call_groq("qwen/qwen3-32b", system_prompt, user_prompt)
            
        else:
            raise ValueError(f"Unknown model name: {model_name}")
            
        latency = time.time() - start_time
        return response_text, latency

    def _call_local_transformers(self, model_id, system_prompt, user_prompt):
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
            import torch
        except ImportError:
            raise ImportError("Error: The 'transformers' or 'torch' library is not installed. Please run 'pip install transformers torch' to use local models.")
        
        # 1. Model caching (CHANGE 1)
        if model_id in self.loaded_models:
            print(f"\nReusing cached local model {model_id}...")
            tokenizer = self.loaded_models[model_id]["tokenizer"]
            model = self.loaded_models[model_id]["model"]
        else:
            print(f"\nLoading local model {model_id} via transformers in 4-bit quantization...")
            tokenizer = AutoTokenizer.from_pretrained(model_id)
            
            # Configure 4-bit quantization to fit easily into 15GB VRAM GPUs (like T4/RTX4050)
            try:
                from transformers import BitsAndBytesConfig
                quantization_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_quant_type="nf4"
                )
            except ImportError:
                print("\n[WARNING] bitsandbytes is not installed. Loading in standard float16 instead. Install bitsandbytes for 4-bit compression.")
                quantization_config = None

            # Load in 4-bit using device_map="auto"
            model = AutoModelForCausalLM.from_pretrained(
                model_id,
                torch_dtype=torch.float16 if quantization_config is None else None,
                quantization_config=quantization_config,
                device_map="auto"
            )
            self.loaded_models[model_id] = {
                "tokenizer": tokenizer,
                "model": model
            }
            
            # GPU diagnostics (CHANGE 4)
            cuda_available = torch.cuda.is_available()
            gpu_name = torch.cuda.get_device_name(0) if cuda_available else "N/A"
            allocated_vram = torch.cuda.memory_allocated(0) / (1024**3) if cuda_available else 0.0
            reserved_vram = torch.cuda.memory_reserved(0) / (1024**3) if cuda_available else 0.0
            
            diag_output = (
                f"GPU Name: {gpu_name}\n"
                f"CUDA Available: {cuda_available}\n"
                f"Allocated VRAM: {allocated_vram:.4f} GB\n"
                f"Reserved VRAM: {reserved_vram:.4f} GB\n"
            )
            print("\n=== GPU Diagnostics ===")
            print(diag_output)
            print("=======================")
            
            os.makedirs("reports", exist_ok=True)
            with open("reports/gpu_diagnostics.txt", "w", encoding="utf-8") as f:
                f.write(diag_output)

        # 2. Configurable generation settings (CHANGE 2)
        # 3. EOS token handling (CHANGE 3)
        temp = self.gen_config["temperature"]
        top_p = self.gen_config["top_p"]
        max_new_tokens = self.gen_config["max_new_tokens"]
        
        if temp <= 0.0:
            pipe = pipeline(
                "text-generation",
                model=model,
                tokenizer=tokenizer,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                eos_token_id=tokenizer.eos_token_id
            )
        else:
            pipe = pipeline(
                "text-generation",
                model=model,
                tokenizer=tokenizer,
                max_new_tokens=max_new_tokens,
                temperature=temp,
                top_p=top_p,
                do_sample=True,
                eos_token_id=tokenizer.eos_token_id
            )
            
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        except Exception:
            prompt = f"System: {system_prompt}\nUser: {user_prompt}\nAssistant:"
            
        outputs = pipe(prompt)
        response_text = outputs[0]["generated_text"]
        
        if response_text.startswith(prompt):
            response_text = response_text[len(prompt):]
            
        return response_text.strip()

    def _call_gemini(self, system_prompt, user_prompt):
        if genai is None:
            raise ImportError("google.generativeai is not installed. Please install it to use Gemini.")
        if not self.gemini_key:
            raise ValueError("GEMINI_API_KEY is not set. Please set it in your environment or .env file.")
        
        # Configure GenerationConfig with our gen_config settings
        generation_config = genai.types.GenerationConfig(
            temperature=self.gen_config["temperature"],
            top_p=self.gen_config["top_p"]
        )
        
        # Safety settings configuration to allow medical-safety/allergen responses without blocking (Change)
        safety_settings = [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_NONE",
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_NONE",
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_NONE",
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_NONE",
            },
        ]
        
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            generation_config=generation_config,
            safety_settings=safety_settings
        )
        
        # Merge system and user prompt to bypass SDK system_instruction truncation bugs
        combined_prompt = f"System Instructions:\n{system_prompt}\n\nUser Input:\n{user_prompt}"
        
        max_retries = 5
        base_delay = 12.0  # Free tier quota is 5 RPM, meaning 1 request every 12 seconds
        for attempt in range(max_retries):
            try:
                response = model.generate_content(combined_prompt)
                return response.text
            except Exception as e:
                is_rate_limit = "429" in str(e) or "ResourceExhausted" in str(type(e)) or "quota" in str(e).lower()
                if is_rate_limit and attempt < max_retries - 1:
                    sleep_time = base_delay * (1.5 ** attempt)
                    print(f"\n[!] Gemini Rate limit (429 / Quota) hit. Waiting {sleep_time:.2f}s before retry (attempt {attempt+1}/{max_retries})...")
                    time.sleep(sleep_time)
                else:
                    raise e

    def _call_openrouter(self, router_model, system_prompt, user_prompt):
        if not self.openrouter_key:
            raise ValueError("OPENROUTER_API_KEY is not set. Cannot call OpenRouter.")
            
        headers = {
            "Authorization": f"Bearer {self.openrouter_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": router_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": self.gen_config["temperature"],
            "top_p": self.gen_config["top_p"],
            "max_tokens": self.gen_config["max_new_tokens"]
        }
        
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            res_json = response.json()
            return res_json["choices"][0]["message"]["content"]
        else:
            raise Exception(f"OpenRouter API error: {response.status_code} - {response.text}")

    def _call_groq(self, groq_model_id, system_prompt, user_prompt):
        if self.groq_client_instance is None:
            from llm.groq_client import KidsNutriGroqClient
            self.groq_client_instance = KidsNutriGroqClient()
            
        return self.groq_client_instance.generate_response(
            model_id=groq_model_id,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=self.gen_config["temperature"],
            top_p=self.gen_config["top_p"],
            max_tokens=self.gen_config["max_new_tokens"]
        )

if __name__ == '__main__':
    # Simple check
    client = KidsNutriLLMClient()
    print("LLM Client loaded. Gemini key set:", client.gemini_key is not None)
