from planner.diet_planner import generate_diet_plan

plan = generate_diet_plan(
    age=7,
    weight_kg=22,
    sex="boy",
    condition="anemia",          # or healthy_growth, underweight...
    region="south",              # north / south / east / west / pan
    diet_type="eggetarian",      # vegetarian / eggetarian / non_vegetarian
    allergies=["peanut"],
    likes=["idli", "egg", "banana"],
    dislikes=[],
    days=3
)

print(plan.summary_text())