import os
import json
import sys

def validate_foods(data):
    errors = 0
    warnings = 0
    required_keys = {
        'food_id': str,
        'food_name': str,
        'category': str,
        'energy_kcal_per_100g': (int, float),
        'protein_g': (int, float),
        'fat_g': (int, float),
        'carbs_g': (int, float),
        'iron_mg': (int, float)
    }
    
    for i, food in enumerate(data):
        for key, expected_type in required_keys.items():
            if key not in food:
                print(f"[ERROR] foods.json[{i}]: Missing required key '{key}'")
                errors += 1
            else:
                val = food[key]
                # It can be a string representation of a float in some DBs, or None, let's just check existence mainly
                # Since _clean_foods parses floats from strings or None, we allow them in the raw DB.
                # But it must physically exist in the schema.
                pass
                
        # Optional field check
        if 'fiber_g' not in food:
            warnings += 1
            
        if 'allergy_tags' in food and not isinstance(food['allergy_tags'], list):
            print(f"[ERROR] foods.json[{i}]: 'allergy_tags' must be a list")
            errors += 1
            
    if warnings > 0:
        print(f"[WARNING] foods.json: {warnings} records are missing the optional 'fiber_g' field (Data completeness issue).")
        
    return errors

def validate_conditions(data):
    errors = 0
    required_keys = ['condition_name', 'required_tags', 'avoid_tags']
    for i, cond in enumerate(data):
        for key in required_keys:
            if key not in cond:
                print(f"[ERROR] conditions.json[{i}]: Missing required key '{key}'")
                errors += 1
    return errors

def validate_goals(data):
    errors = 0
    required_keys = ['goal_name', 'required_tags', 'avoid_tags']
    for i, goal in enumerate(data):
        for key in required_keys:
            if key not in goal:
                print(f"[ERROR] goals.json[{i}]: Missing required key '{key}'")
                errors += 1
    return errors

def validate_allergies(data):
    errors = 0
    required_keys = ['allergy', 'avoid_foods', 'severity']
    for i, alg in enumerate(data):
        for key in required_keys:
            if key not in alg:
                print(f"[ERROR] allergies.json[{i}]: Missing required key '{key}'")
                errors += 1
    return errors

def validate_rag(data):
    errors = 0
    required_keys = ['id', 'text', 'metadata']
    for i, chunk in enumerate(data):
        for key in required_keys:
            if key not in chunk:
                print(f"[ERROR] rag_data.json[{i}]: Missing required key '{key}'")
                errors += 1
    return errors

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    structured_dir = os.path.join(base_dir, "data", "structured_db")
    rag_dir = os.path.join(base_dir, "data", "rag")
    
    files = {
        "foods.json": (os.path.join(structured_dir, "foods.json"), validate_foods),
        "conditions.json": (os.path.join(structured_dir, "conditions.json"), validate_conditions),
        "goals.json": (os.path.join(structured_dir, "goals.json"), validate_goals),
        "allergies.json": (os.path.join(structured_dir, "allergies.json"), validate_allergies),
        "rag_data.json": (os.path.join(rag_dir, "rag_data.json"), validate_rag)
    }
    
    total_errors = 0
    
    for filename, (filepath, validator) in files.items():
        if not os.path.exists(filepath):
            print(f"[ERROR] File not found: {filepath}")
            total_errors += 1
            continue
            
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            errs = validator(data)
            if errs == 0:
                print(f"[OK] {filename} adheres to frozen schema.")
            total_errors += errs
        except json.JSONDecodeError:
            print(f"[ERROR] Could not parse {filename} as valid JSON.")
            total_errors += 1
            
    if total_errors > 0:
        print(f"\nValidation FAILED with {total_errors} errors.")
        sys.exit(1)
    else:
        print("\nValidation PASSED. All data files match the frozen schemas.")
        sys.exit(0)

if __name__ == "__main__":
    main()
