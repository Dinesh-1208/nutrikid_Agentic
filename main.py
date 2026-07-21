import os
import argparse
import json

def main():
    parser = argparse.ArgumentParser(description="KidsNutriBite Research Prototype CLI")
    
    # Mode selection
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--index", action="store_true", help="Build the RAG FAISS index")
    group.add_argument("--query", type=str, help="Run semantic search query on the RAG index")
    group.add_argument("--plan", action="store_true", help="Generate a diet plan using the deterministic planner")
    group.add_argument("--ask", type=str, help="Submit a full query to the KidsNutriBite hybrid QA pipeline")
    group.add_argument("--evaluate", action="store_true", help="Run model evaluations and comparison benchmark")
    
    # Planner args
    parser.add_argument("--age", type=float, help="Age of the child (in years)")
    parser.add_argument("--weight", type=float, help="Weight of the child (in kg)")
    parser.add_argument("--condition", type=str, help="Clinical condition name")
    parser.add_argument("--goal", type=str, help="Nutrition goal name")
    parser.add_argument("--allergies", type=str, help="Comma-separated list of allergies")
    
    # Evaluator args
    parser.add_argument("--num-samples", type=int, default=100, help="Number of samples to evaluate (default: 100 for full benchmark)")
    parser.add_argument("--models", type=str, default="gemini,qwen_local", help="Comma-separated models to evaluate")
    parser.add_argument("--judge-model", type=str, default="groq_llama70b", help="Model to use as the LLM judge (default: groq_llama70b)")

    # LLM args
    parser.add_argument("--model", type=str, default="gemini", help="Active model for QA (gemini, qwen_local, groq_llama70b, groq_llama8b, groq_qwen)")

    args = parser.parse_args()
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    if args.index:
        # Build index
        from rag.indexer import build_index
        data_path = os.path.join(base_dir, "data", "rag", "rag_data.json")
        output_dir = os.path.join(base_dir, "data", "rag")
        build_index(data_path, output_dir)
        
    elif args.query:
        # Query retriever
        from rag.retriever import KidsNutriRetriever
        retriever = KidsNutriRetriever()
        retriever.debug_retrieve(args.query)
        
    elif args.plan:
        if args.age is None:
            parser.error("--age is required for --plan mode")
            
        from planner.diet_planner import KidsNutriDatabase, DietPlanner
        db = KidsNutriDatabase()
        planner = DietPlanner(db)
        
        allergies_list = [a.strip() for a in args.allergies.split(",")] if args.allergies else []
        profile = {
            "age": args.age,
            "weight": args.weight,
            "condition": args.condition,
            "goal": args.goal,
            "allergies": allergies_list
        }
        
        plan = planner.generate_meal_plan(profile)
        print("\n=== GENERATED DIET PLAN ===")
        print(json.dumps(plan, indent=2))
        
    elif args.ask:
        # Full QA pipeline
        # 1. Parse implicit profile
        from planner.diet_planner import KidsNutriDatabase, DietPlanner
        from rag.retriever import KidsNutriRetriever
        from llm.llm_client import KidsNutriLLMClient
        from llm.prompt_templates import generate_llm_prompt
        
        db = KidsNutriDatabase()
        planner = DietPlanner(db)
        retriever = KidsNutriRetriever()
        client = KidsNutriLLMClient()
        
        # Build a generic default profile based on args or heuristics
        allergies_list = [a.strip() for a in args.allergies.split(",")] if args.allergies else []
        profile = {
            "age": args.age if args.age else 7.0,
            "weight": args.weight if args.weight else 20.0,
            "condition": args.condition if args.condition else "healthy_growth",
            "goal": args.goal if args.goal else "balanced_nutrition",
            "allergies": allergies_list
        }
        
        print("\n--- Processing Query: ---")
        print(f"Query: {args.ask}")
        print(f"Profile: Age={profile['age']}, Weight={profile['weight']}, Condition={profile['condition']}, Goal={profile['goal']}, Allergies={profile['allergies']}")
        
        print("1. Retrieving RAG Knowledge...")
        contexts = retriever.retrieve(args.ask, top_k=5)
        print(f"Retrieved {len(contexts)} chunks.")
        
        # 2 & 3. Intent Routing
        query_lower = args.ask.lower()
        diet_keywords = ["plan", "diet", "meal", "menu"]
        is_diet_request = any(kw in query_lower for kw in diet_keywords)
        
        if is_diet_request:
            print("2. Generating Diet Plan...")
            plan = planner.generate_meal_plan(profile)
            
            print("3. Generating LLM Prompt (Diet Planner Mode)...")
            system_prompt, user_prompt = generate_llm_prompt(plan, contexts, query=args.ask)
        else:
            print("2. Skipping Diet Plan (General QA Query Detected)...")
            
            print("3. Generating LLM Prompt (General QA Mode)...")
            from llm.prompt_templates import generate_qa_prompt
            system_prompt, user_prompt = generate_qa_prompt(profile, contexts, query=args.ask)
        
        print(f"4. Generating Response using Model: {args.model}...")
        response, latency = client.generate_response(system_prompt, user_prompt, args.model)
        
        print("\n=== RESPONSE ===")
        print(response)
        print(f"\nResponse generated in {latency:.2f} seconds.")
        
    elif args.evaluate:
        # Run evaluations
        from planner.diet_planner import KidsNutriDatabase, DietPlanner
        from rag.retriever import KidsNutriRetriever
        from llm.llm_client import KidsNutriLLMClient
        from evaluation.evaluator import KidsNutriEvaluator
        from evaluation.comparator import KidsNutriComparator
        
        db = KidsNutriDatabase()
        planner = DietPlanner(db)
        retriever = KidsNutriRetriever()
        client = KidsNutriLLMClient()
        
        evaluator = KidsNutriEvaluator(client, retriever, planner, judge_model=args.judge_model)
        comparator = KidsNutriComparator(evaluator)
        
        models_list = [m.strip() for m in args.models.split(",")]
        comparator.run_comparison(models_list, args.num_samples)

if __name__ == '__main__':
    main()
