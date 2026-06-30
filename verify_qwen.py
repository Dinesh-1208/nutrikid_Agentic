import sys
import torch

def verify_qwen():
    print("[+] Running Qwen Local Model Diagnostics...")
    
    # 1. Check GPU / CUDA
    cuda_available = torch.cuda.is_available()
    print(f"GPU detected: {'YES' if cuda_available else 'NO'}")
    
    if not cuda_available:
        print("[-] Error: Local open-source model execution requires a CUDA-capable GPU.")
        print("[-] Aborting Qwen local diagnostics due to missing hardware environment.")
        sys.exit(1)
        
    # 2. VRAM usage
    device_name = torch.cuda.get_device_name(0)
    total_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3) # GB
    allocated_memory = torch.cuda.memory_allocated(0) / (1024**3) # GB
    free_memory = total_memory - allocated_memory
    print(f"GPU Device Name: {device_name}")
    print(f"Total VRAM: {total_memory:.2f} GB")
    print(f"Allocated VRAM: {allocated_memory:.2f} GB")
    print(f"Free VRAM: {free_memory:.2f} GB")
    
    try:
        from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
        model_id = "Qwen/Qwen2.5-7B-Instruct"
        
        print(f"[+] Loading model and tokenizer: {model_id}...")
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        
        # Load model using torch.float16 and device_map="auto"
        model = AutoModelForCausalLM.from_pretrained(
            model_id,
            torch_dtype=torch.float16,
            device_map="auto"
        )
        print("[+] Model loaded successfully!")
        
        # 3. Print VRAM post-load
        post_allocated = torch.cuda.memory_allocated(0) / (1024**3)
        print(f"Post-load VRAM usage: {post_allocated:.2f} GB")
        
        pipe = pipeline(
            "text-generation",
            model=model,
            tokenizer=tokenizer,
            max_new_tokens=50,
            temperature=0.7,
            top_p=0.9
        )
        
        test_prompt = "Explain in one short sentence why iron is good for children."
        messages = [
            {"role": "system", "content": "You are a concise nutrition assistant."},
            {"role": "user", "content": test_prompt}
        ]
        
        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        print(f"[+] Running sample query: '{test_prompt}'...")
        outputs = pipe(prompt)
        response_text = outputs[0]["generated_text"]
        
        if response_text.startswith(prompt):
            response_text = response_text[len(prompt):]
            
        print("\n--- Diagnostic Output ---")
        print(f"* GPU detected: YES (Device: {device_name})")
        print(f"* VRAM usage: Total VRAM: {total_memory:.2f} GB, Allocated VRAM: {post_allocated:.2f} GB, Free VRAM: {total_memory - post_allocated:.2f} GB")
        print(f"* Model loaded: YES ({model_id})")
        print(f"* Sample response: {response_text.strip()}")
        print("--------------------------")
        print("[+] Qwen Local test completed successfully!")
        
    except Exception as e:
        print(f"[-] Qwen Local loading or execution failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    verify_qwen()
