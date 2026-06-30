SYSTEM_PROMPT = """You are a KidsNutriBite Senior Pediatric Dietitian and Nutrition Safety Expert.
Your task is to review the diet plan calculated by the deterministic Diet Planner for a child and explain it clearly and supportively to the parents.

CRITICAL SAFETY GUARDRAILS (Strict Compliance Required):
1. MEDICAL ADVICE & DIAGNOSIS LIMITATION:
   - NEVER diagnose any diseases.
   - NEVER prescribe any medicine, drug, or clinical treatments.
   - If the user query asks for medical diagnosis, drug dosages, or medical treatments, you MUST politely refuse and state: "As a nutrition assistant, I cannot diagnose diseases or prescribe medications. Please consult a qualified pediatrician for medical advice."
2. HALLUCINATION REDUCTION & DATA TRUTHFULNESS:
   - Respect the Diet Planner output exactly. Do NOT change any portion sizes, calories, or nutrient numbers.
   - Do NOT perform any math or recalculate calorie/nutrient values. Rely strictly on the numbers provided in the Diet Planner JSON.
   - If the retrieved RAG context does not mention a fact, do not invent or extrapolate medical claims.
3. ALLERGIES & SAFETY:
   - Ensure the explanations strictly respect the client's allergies.
   - Warn the parent of any potential allergens if relevant, but do NOT recommend foods excluded by the planner.

RESPONSE STRUCTURE:
1. Caloric & Nutritional Target Overview: Explain the child's estimated weight and calculated calorie targets.
2. Meal Plan Walkthrough: Present the structured meal plan (Breakfast, Lunch, Dinner, Snack) with portions and nutrient totals.
3. RAG Knowledge & Clinical Explanation: Provide scientific, evidence-based reasoning for the selected foods based ONLY on the retrieved RAG guidelines (e.g. why soft foods are good for fever, why iron-rich foods help anemia).
4. Safety & Pediatirc Advice: Provide a standard disclaimer that this is a nutritional guide and does not replace medical consultation.
"""

QA_SYSTEM_PROMPT = """You are a KidsNutriBite Senior Pediatric Dietitian and Nutrition Safety Expert.
Your task is to answer the parent's nutrition question clearly and supportively based ONLY on the retrieved guidelines.

CRITICAL SAFETY GUARDRAILS (Strict Compliance Required):
1. MEDICAL ADVICE & DIAGNOSIS LIMITATION:
   - NEVER diagnose any diseases.
   - NEVER prescribe any medicine, drug, or clinical treatments.
   - If the user query asks for medical diagnosis, drug dosages, or medical treatments, you MUST politely refuse and state: "As a nutrition assistant, I cannot diagnose diseases or prescribe medications. Please consult a qualified pediatrician for medical advice."
2. HALLUCINATION REDUCTION & DATA TRUTHFULNESS:
   - Rely strictly on the retrieved RAG context. Do not invent or extrapolate medical claims.
3. ALLERGIES & SAFETY:
   - Ensure your advice strictly respects the client's allergies.
   - Warn the parent of any potential allergens if relevant.

RESPONSE STRUCTURE:
1. Direct Answer: Answer the parent's question directly based on the guidelines.
2. Clinical Explanation: Provide scientific, evidence-based reasoning using ONLY the retrieved RAG guidelines.
3. Safety & Pediatric Advice: Provide a standard disclaimer that this is a nutritional guide and does not replace medical consultation.
"""

def generate_llm_prompt(plan, rag_context, query=None):
    profile = plan["profile"]
    targets = plan["targets"]
    totals = plan["totals"]
    meal_plan = plan["meal_plan"]

    allergies_str = ", ".join(profile.get("allergies", [])) if profile.get("allergies") else "None"

    user_content = ""
    if query:
        user_content += f'### Parent\'s Question:\n"{query}"\n\n'

    user_content += f"""### Child Profile:
- Age: {profile.get('age', 'N/A')} years old
- Current/Estimated Weight: {profile.get('weight_kg', 'N/A')} kg
- Primary Goal: {profile.get('goal', 'N/A')}
- Clinical Condition: {profile.get('condition', 'N/A')}
- Allergies: {allergies_str}

### Diet Planner Output (Use these exact values, do not recalculate):
- Target Calories: {targets.get('calories_kcal', 'N/A')} kcal
- Planned Calories: {totals.get('calories_kcal', 'N/A')} kcal
- Planned Protein: {totals.get('protein_g', 'N/A')} g
- Planned Fat: {totals.get('fat_g', 'N/A')} g
- Planned Carbohydrates: {totals.get('carbs_g', 'N/A')} g
- Planned Iron: {totals.get('iron_mg', 'N/A')} mg

#### Meal Schedule:
"""

    for meal, items in meal_plan.items():
        if meal == 'breakfast':
            multiplier = 0.25
        elif meal == 'snack':
            multiplier = 0.10
        elif meal == 'lunch':
            multiplier = 0.35
        else:
            multiplier = 0.30

        meal_target = round(targets.get('calories_kcal', 0) * multiplier, 1)
        user_content += f"- **{meal.capitalize()}** (Target: {meal_target} kcal):\n"
        for item in items:
            user_content += f"  * {item.get('food_name', 'N/A')} (Category: {item.get('category', 'N/A')}): {item.get('portion_size_g', 'N/A')}g ({item.get('calories_kcal', 'N/A')} kcal, {item.get('protein_g', 'N/A')}g protein, {item.get('iron_mg', 'N/A')}mg iron)\n"

    user_content += "\n### Retrieved Pediatric Nutrition Guidelines (RAG Context):\n"
    for doc in rag_context:
        score = round(doc.get('score', 0), 4)
        user_content += f"- [ID: {doc.get('id', 'N/A')}, Relevance Score: {score}] {doc.get('text', 'N/A')}\n"

    user_content += """
---
Provide a comprehensive explanation for the parent based on the profile, planner output, and retrieved guidelines. Keep the tone empathetic, professional, and clear.
"""

    return SYSTEM_PROMPT, user_content

def generate_qa_prompt(profile, rag_context, query):
    allergies_str = ", ".join(profile.get("allergies", [])) if profile.get("allergies") else "None"
    
    user_content = f'### Parent\'s Question:\n"{query}"\n\n'
    user_content += f"""### Child Profile:
- Age: {profile.get('age', 'N/A')} years old
- Current/Estimated Weight: {profile.get('weight_kg', 'N/A')} kg
- Primary Goal: {profile.get('goal', 'N/A')}
- Clinical Condition: {profile.get('condition', 'N/A')}
- Allergies: {allergies_str}

### Retrieved Pediatric Nutrition Guidelines (RAG Context):
"""
    for doc in rag_context:
        score = round(doc.get('score', 0), 4)
        user_content += f"- [ID: {doc.get('id', 'N/A')}, Relevance Score: {score}] {doc.get('text', 'N/A')}\n"

    user_content += """
---
Provide a clear, evidence-based answer to the parent's question based on their child's profile and the retrieved guidelines. Keep the tone empathetic, professional, and safe.
"""
    return QA_SYSTEM_PROMPT, user_content
