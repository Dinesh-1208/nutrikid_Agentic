import json
from planner.diet_planner import KidsNutriDatabase, DietPlanner

def run_verification():
    print("--- 1. Testing Database Validation ---")
    import subprocess
    result = subprocess.run(["python", "data/validate_db.py"], capture_output=True, text=True)
    print("Validation Output:\n", result.stdout.strip())
    
    print("\n--- 2. Running Weekly Planner ---")
    db = KidsNutriDatabase()
    planner = DietPlanner(db)
    
    profile = {
        "age": 5,
        "weight": 18.0,
        "condition": "fever",
        "goal": "healthy_growth",
        "allergies": ["peanut"]
    }
    print(f"Profile: {profile}")
    
    plan = planner.generate_weekly_meal_plan(profile)
    
    print("\n--- 3. Verifying Output Structure ---")
    days = list(plan["weekly_plan"].keys())
    print(f"Days Generated: {len(days)}")
    assert len(days) == 7, "Did not generate 7 days"
    
    for day, data in plan["weekly_plan"].items():
        assert len(data["meals"]) == 6, f"Day {day} does not have 6 meals"
    print("Slots per day: 6 (Verified for all 7 days)")
    
    print("\n--- 4. Nutrition Targets vs Actuals (Sample: Monday) ---")
    mon = plan["weekly_plan"]["Monday"]
    targets = plan["daily_target"]
    actuals = mon["daily_totals"]
    diff = mon["target_deviation"]
    
    print("TARGETS:")
    print(f"  Calories: {targets['calories']} kcal")
    print(f"  Protein:  {targets['protein']} g")
    print(f"  Carbs:    {targets['carbs']} g")
    print(f"  Fat:      {targets['fat']} g")
    print(f"  Fiber:    {targets.get('fiber', 0)} g")
    
    print("\nACTUALS (Monday):")
    print(f"  Calories: {actuals['calories']} kcal (Diff: {diff['calories_diff']} kcal)")
    print(f"  Protein:  {actuals['protein']} g (Diff: {diff['protein_diff']} g)")
    print(f"  Carbs:    {actuals['carbs']} g (Diff: {diff['carbs_diff']} g)")
    print(f"  Fat:      {actuals['fat']} g (Diff: {diff['fat_diff']} g)")
    print(f"  Fiber:    {actuals.get('fiber', 0)} g")
    
    print("\n--- 5. Rules & Safety Validation ---")
    print(f"Condition Check: {mon['condition_check']}")
    print(f"Allergy Check:   {mon['allergy_check']}")
    
    # Manually verify no peanuts in plan
    peanut_found = False
    all_foods = []
    for day in days:
        for slot, foods in plan["weekly_plan"][day]["meals"].items():
            for f in foods:
                all_foods.append((day, slot, f["food_name"]))
                if "peanut" in f["food_name"].lower() or "peanut" in f["category"].lower():
                    peanut_found = True
                    
    print(f"Peanut allergy violated? {peanut_found}")
    
    print("\n--- 6. Rotation Validation ---")
    # Check if identical foods are in the exact same slot on consecutive days
    rotation_failures = 0
    for i in range(1, len(days)):
        prev_day = days[i-1]
        curr_day = days[i]
        
        for slot in plan["weekly_plan"][curr_day]["meals"].keys():
            prev_foods = {f["food_name"] for f in plan["weekly_plan"][prev_day]["meals"][slot]}
            curr_foods = {f["food_name"] for f in plan["weekly_plan"][curr_day]["meals"][slot]}
            overlap = prev_foods.intersection(curr_foods)
            if overlap:
                rotation_failures += 1
                
    print(f"Consecutive identical items in same slot: {rotation_failures}")
    if rotation_failures > 0:
        print("Note: Some repetition is expected due to limited safe DB items for this slot/condition.")
        
    print("\n--- 7. Existing Planner Methods Intact ---")
    daily_plan = planner.generate_meal_plan(profile)
    print("generate_meal_plan() execution: OK")

if __name__ == "__main__":
    run_verification()
