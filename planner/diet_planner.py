import os
import json
import re

class KidsNutriDatabase:
    def __init__(self, data_dir=None):
        if data_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            data_dir = os.path.join(base_dir, "data", "structured_db")
            
        self.foods_path = os.path.join(data_dir, "foods.json")
        self.conditions_path = os.path.join(data_dir, "conditions.json")
        self.goals_path = os.path.join(data_dir, "goals.json")
        self.allergies_path = os.path.join(data_dir, "allergies.json")
        
        self.foods = self._load_json(self.foods_path)
        self.conditions = self._load_json(self.conditions_path)
        self.goals = self._load_json(self.goals_path)
        self.allergies = self._load_json(self.allergies_path)
        
        # Clean numerical fields in foods
        self._clean_foods()

    def _load_json(self, path):
        if not os.path.exists(path):
            raise FileNotFoundError(f"Database file not found at {path}")
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _clean_foods(self):
        for food in self.foods:
            # Helper to parse float or return default
            def to_float(val, default=0.0):
                if val is None or str(val).strip() == "":
                    return default
                if isinstance(val, list):
                    if not val:
                        return default
                    val = val[0]
                try:
                    return float(val)
                except (ValueError, TypeError):
                    return default
            
            food['energy_kcal_per_100g'] = to_float(food.get('energy_kcal_per_100g'))
            food['protein_g'] = to_float(food.get('protein_g'))
            food['fat_g'] = to_float(food.get('fat_g'))
            food['carbs_g'] = to_float(food.get('carbs_g'))
            food['iron_mg'] = to_float(food.get('iron_mg'))
            
            food['portion_energy_kcal'] = to_float(food.get('portion_energy_kcal'))
            food['portion_protein_g'] = to_float(food.get('portion_protein_g'))
            
            # If energy_per_100g is 0 but portion_energy is available, estimate energy_per_100g
            # Standard portion weights can be estimated from unit
            portion_unit = str(food.get('portion_unit', '')).lower()
            weight_g = 100.0
            match = re.search(r'~(\d+)\s*g', portion_unit)
            if match:
                weight_g = float(match.group(1))
            elif "ml" in portion_unit:
                match_ml = re.search(r'(\d+)\s*ml', portion_unit)
                if match_ml:
                    weight_g = float(match_ml.group(1))
            
            if food['energy_kcal_per_100g'] == 0.0 and food['portion_energy_kcal'] > 0.0:
                food['energy_kcal_per_100g'] = (food['portion_energy_kcal'] / weight_g) * 100.0
            
            if food['protein_g'] == 0.0 and food['portion_protein_g'] > 0.0:
                food['protein_g'] = (food['portion_protein_g'] / weight_g) * 100.0

            # Set age_min default to 1 if not present
            if 'age_min' not in food or food['age_min'] == "" or food['age_min'] is None:
                food['age_min'] = 1
            else:
                try:
                    food['age_min'] = int(food['age_min'])
                except ValueError:
                    food['age_min'] = 1

    # Data layer functions
    def get_food(self, food_name):
        name_clean = str(food_name).strip().lower().replace(" ", "_")
        for food in self.foods:
            if food['food_name'].strip().lower().replace(" ", "_") == name_clean:
                return food
        return None

    def get_food_nutrition(self, food_name):
        food = self.get_food(food_name)
        if food:
            return {
                "food_name": food["food_name"],
                "category": food["category"],
                "energy_kcal_per_100g": food["energy_kcal_per_100g"],
                "protein_g": food["protein_g"],
                "fat_g": food["fat_g"],
                "carbs_g": food["carbs_g"],
                "iron_mg": food["iron_mg"]
            }
        return None

    def get_foods_by_category(self, category):
        cat_clean = str(category).strip().lower()
        return [f for f in self.foods if f['category'].strip().lower() == cat_clean]

    def get_foods_by_tags(self, tags):
        if isinstance(tags, str):
            tags = [tags]
        tags_clean = [t.strip().lower() for t in tags]
        results = []
        for food in self.foods:
            food_tags = [t.strip().lower() for t in food.get('tags', [])]
            if any(t in food_tags for t in tags_clean):
                results.append(food)
        return results

    def get_condition(self, condition_name):
        cond_clean = str(condition_name).strip().lower()
        matched = None
        # Merge if multiple exist
        for cond in self.conditions:
            if cond['condition_name'].strip().lower() == cond_clean:
                if matched is None:
                    matched = {
                        "condition_name": cond["condition_name"],
                        "required_tags": list(cond.get("required_tags", [])),
                        "avoid_tags": list(cond.get("avoid_tags", [])),
                        "meal_pattern": cond.get("meal_pattern", "")
                    }
                else:
                    # Merge tags
                    matched["required_tags"] = list(set(matched["required_tags"] + list(cond.get("required_tags", []))))
                    matched["avoid_tags"] = list(set(matched["avoid_tags"] + list(cond.get("avoid_tags", []))))
                    if not matched["meal_pattern"] and cond.get("meal_pattern"):
                        matched["meal_pattern"] = cond.get("meal_pattern")
        return matched

    def get_goal(self, goal_name):
        goal_clean = str(goal_name).strip().lower()
        matched = None
        # Merge if multiple exist
        for goal in self.goals:
            if goal['goal_name'].strip().lower() == goal_clean:
                if matched is None:
                    matched = {
                        "goal_name": goal["goal_name"],
                        "required_tags": list(goal.get("required_tags", [])),
                        "avoid_tags": list(goal.get("avoid_tags", [])),
                        "meal_frequency": goal.get("meal_frequency", 3)
                    }
                else:
                    matched["required_tags"] = list(set(matched["required_tags"] + list(goal.get("required_tags", []))))
                    matched["avoid_tags"] = list(set(matched["avoid_tags"] + list(goal.get("avoid_tags", []))))
        return matched

    def get_allergy(self, allergy_name):
        all_clean = str(allergy_name).strip().lower()
        matched = None
        for alg in self.allergies:
            if alg['allergy'].strip().lower() == all_clean:
                if matched is None:
                    matched = {
                        "allergy": alg["allergy"],
                        "avoid_foods": list(alg.get("avoid_foods", [])),
                        "severity": alg.get("severity", "moderate")
                    }
                else:
                    matched["avoid_foods"] = list(set(matched["avoid_foods"] + list(alg.get("avoid_foods", []))))
        return matched


class DietPlanner:
    def __init__(self, db: KidsNutriDatabase):
        self.db = db

    def calculate_calories(self, age, weight=None, condition=None, goal=None):
        # 1. Estimate weight if not provided using anthropometric expected norms
        if weight is None or weight <= 0:
            if age < 1:
                # Under 1 year (age in months, let's assume age is years, so age * 12 is months)
                months = max(1.0, age * 12.0)
                weight = (months + 9.0) / 2.0
            elif 1 <= age <= 6:
                weight = (age * 2.0) + 8.0
            elif 7 <= age <= 12:
                weight = (age * 7.0 - 5.0) / 2.0
            else:
                # Standard school age/adolescence weight projection
                weight = age * 3.0
                
        # 2. Calculate base calories using Holliday-Segar formula
        if weight <= 10:
            base_calories = weight * 100.0
        elif weight <= 20:
            base_calories = 1000.0 + (weight - 10.0) * 50.0
        else:
            base_calories = 1500.0 + (weight - 20.0) * 20.0
            
        # 3. Adjust calories based on goal
        goal_record = self.db.get_goal(goal) if goal else None
        goal_surplus = 0.0
        if goal:
            g_lower = goal.lower()
            if "gain" in g_lower or "growth" in g_lower or "boost" in g_lower:
                goal_surplus = 300.0  # Weight gain surplus
            elif "loss" in g_lower or "management" in g_lower or "obesity" in g_lower:
                goal_surplus = -200.0 # Calorie restriction
                
        # 4. Adjust calories based on condition
        condition_record = self.db.get_condition(condition) if condition else None
        cond_multiplier = 1.0
        if condition:
            c_lower = condition.lower()
            if "fever" in c_lower or "infection" in c_lower or "diarrhea" in c_lower:
                cond_multiplier = 1.12 # +12% increase for hypermetabolism in illness

        final_calories = (base_calories * cond_multiplier) + goal_surplus
        return round(final_calories, 1), round(weight, 1)

    def generate_meal_plan(self, profile):
        age = profile.get("age", 5)
        weight = profile.get("weight")
        goal = profile.get("goal")
        condition = profile.get("condition")
        allergies = profile.get("allergies", [])
        
        # 1. Calorie calculations
        target_calories, calculated_weight = self.calculate_calories(age, weight, condition, goal)
        
        # 2. Gather required and avoid tags
        required_tags = set()
        avoid_tags = set()
        avoid_food_names = set()
        
        if condition:
            cond_rec = self.db.get_condition(condition)
            if cond_rec:
                required_tags.update(cond_rec.get("required_tags", []))
                avoid_tags.update(cond_rec.get("avoid_tags", []))
                
        if goal:
            goal_rec = self.db.get_goal(goal)
            if goal_rec:
                required_tags.update(goal_rec.get("required_tags", []))
                avoid_tags.update(goal_rec.get("avoid_tags", []))
                
        # 3. Gather allergy exclusions
        for allergy in allergies:
            alg_rec = self.db.get_allergy(allergy)
            if alg_rec:
                avoid_food_names.update([f.strip().lower().replace(" ", "_") for f in alg_rec.get("avoid_foods", [])])
                
        # 4. Filter foods
        candidate_foods = []
        for food in self.db.foods:
            # Age filter
            if food.get("age_min") and age < food["age_min"]:
                continue
                
            # Allergy filter (check direct names, category, or allergy tags)
            f_name_clean = food["food_name"].strip().lower().replace(" ", "_")
            f_cat_clean = food["category"].strip().lower().replace(" ", "_")
            
            is_allergic = False
            if f_name_clean in avoid_food_names or f_cat_clean in avoid_food_names:
                is_allergic = True
                
            # Check allergy tags
            f_all_tags = [t.strip().lower() for t in food.get("allergy_tags", [])]
            for alg in allergies:
                alg_clean = alg.strip().lower()
                if alg_clean in f_all_tags:
                    is_allergic = True
                # Match partials like nut/lactose
                if "nut" in alg_clean and "nut" in f_name_clean:
                    is_allergic = True
                if "milk" in alg_clean and ("milk" in f_name_clean or "dairy" in f_cat_clean):
                    is_allergic = True
                    
            if is_allergic:
                continue
                
            # Condition / Goal avoid tags filter
            f_tags = [t.strip().lower() for t in food.get("tags", [])]
            if any(tag in avoid_tags for tag in f_tags):
                continue
                
            candidate_foods.append(food)
            
        # 5. Segment foods into meal types
        meals = {"breakfast": [], "lunch": [], "dinner": [], "snack": []}
        
        # Split target calories
        meal_targets = {
            "breakfast": target_calories * 0.25,
            "snack": target_calories * 0.10,
            "lunch": target_calories * 0.35,
            "dinner": target_calories * 0.30
        }
        
        # Build diet plan
        for m_type in meals.keys():
            m_target = meal_targets[m_type]
            # Filter candidates for this meal type
            meal_candidates = []
            for f in candidate_foods:
                meal_types = [mt.strip().lower() for mt in f.get("meal_types", [])]
                if m_type in meal_types or "all" in meal_types:
                    meal_candidates.append(f)
                    
            if not meal_candidates:
                # Fallback to category based
                if m_type == "breakfast":
                    meal_candidates = [f for f in candidate_foods if f["category"] in ["cereal", "dairy", "fruit"]]
                elif m_type == "snack":
                    meal_candidates = [f for f in candidate_foods if f["category"] in ["fruit", "fat", "dairy"]]
                else:
                    meal_candidates = [f for f in candidate_foods if f["category"] in ["cereal", "protein", "vegetable"]]
                    
            if not meal_candidates:
                meal_candidates = candidate_foods # Last resort fallback
                
            # Sort candidates: prioritize those with required tags, high digestibility, low fat if overweight
            def score_food(food_item):
                score = 0
                f_tags = [t.strip().lower() for t in food_item.get("tags", [])]
                # Prioritize required tags
                score += sum(5 for tag in f_tags if tag in required_tags)
                # Digestibility
                if food_item.get("digestibility_boiled") == "high":
                    score += 2
                if food_item.get("digestibility_fried") == "low":
                    score -= 2
                return score
                
            meal_candidates = sorted(meal_candidates, key=score_food, reverse=True)
            
            # Select 2-3 foods to meet target
            selected = []
            accumulated_cal = 0.0
            
            for food in meal_candidates:
                if accumulated_cal >= m_target * 0.95:
                    break
                    
                energy_per_100 = food["energy_kcal_per_100g"]
                if energy_per_100 <= 0.0:
                    energy_per_100 = 100.0 # Default fallback
                    
                # Calculate portion size to meet remaining calories
                rem_cal = m_target - accumulated_cal
                portion_g = 100.0
                
                # Check default portion
                if food["portion_energy_kcal"] > 0.0:
                    default_portion_cal = food["portion_energy_kcal"]
                    # If default portion fits, use it or scale it
                    scale = min(2.0, max(0.5, rem_cal / default_portion_cal))
                    portion_g = scale * 100.0 # Estimate default portion weight around 100g scaled
                    cal_added = scale * default_portion_cal
                else:
                    portion_g = min(200.0, max(30.0, (rem_cal / energy_per_100) * 100.0))
                    cal_added = (portion_g / 100.0) * energy_per_100
                    
                portion_g = round(portion_g, 1)
                cal_added = round(cal_added, 1)
                
                pro_added = round((portion_g / 100.0) * food["protein_g"], 2)
                fat_added = round((portion_g / 100.0) * food["fat_g"], 2)
                carbs_added = round((portion_g / 100.0) * food["carbs_g"], 2)
                iron_added = round((portion_g / 100.0) * food["iron_mg"], 2)
                
                selected.append({
                    "food_name": food["food_name"],
                    "category": food["category"],
                    "portion_size_g": portion_g,
                    "portion_unit": food.get("portion_unit", "g"),
                    "calories_kcal": cal_added,
                    "protein_g": pro_added,
                    "fat_g": fat_added,
                    "carbs_g": carbs_added,
                    "iron_mg": iron_added
                })
                accumulated_cal += cal_added
                
            meals[m_type] = selected
            
        # 6. Calculate total nutrients of the plan
        total_calories = 0.0
        total_protein = 0.0
        total_fat = 0.0
        total_carbs = 0.0
        total_iron = 0.0
        
        for m_type, items in meals.items():
            for it in items:
                total_calories += it["calories_kcal"]
                total_protein += it["protein_g"]
                total_fat += it["fat_g"]
                total_carbs += it["carbs_g"]
                total_iron += it["iron_mg"]
                
        plan = {
            "profile": {
                "age": age,
                "weight_kg": calculated_weight,
                "goal": goal,
                "condition": condition,
                "allergies": allergies
            },
            "targets": {
                "calories_kcal": target_calories
            },
            "totals": {
                "calories_kcal": round(total_calories, 1),
                "protein_g": round(total_protein, 2),
                "fat_g": round(total_fat, 2),
                "carbs_g": round(total_carbs, 2),
                "iron_mg": round(total_iron, 2)
            },
            "meal_plan": meals
        }
        return plan

if __name__ == '__main__':
    # Test Planner
    db = KidsNutriDatabase()
    planner = DietPlanner(db)
    profile = {
        "age": 7,
        "weight": 22.0,
        "condition": "fever",
        "goal": "healthy_growth",
        "allergies": ["egg_protein"]
    }
    plan = planner.generate_meal_plan(profile)
    print(json.dumps(plan, indent=2))
