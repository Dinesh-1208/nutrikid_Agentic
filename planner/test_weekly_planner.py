"""
Unit tests for KidsNutriBite Deterministic Diet Planner.
Run: python -m pytest planner/test_weekly_planner.py -v
or simply: python planner/test_weekly_planner.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running from repo root or planner/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from planner.diet_planner import (
    DietPlanner,
    KidsNutriDatabase,
    generate_diet_plan,
    CONDITION_ADJUSTMENTS,
    MEAL_SLOTS,
)


def test_basic_plan_generation():
    plan = generate_diet_plan(
        age=6,
        weight_kg=20,
        sex="girl",
        condition="healthy_growth",
        region="south",
        diet_type="vegetarian",
        days=3,
    )
    assert plan.targets.energy_kcal > 1000
    assert plan.targets.protein_g > 10
    assert len(plan.weekly_plan) == 3
    for day in plan.weekly_plan:
        assert set(day.meals.keys()) == set(MEAL_SLOTS)
        assert day.day_totals["kcal"] > 500
    print("✓ test_basic_plan_generation passed")


def test_allergy_exclusion():
    plan = generate_diet_plan(
        age=5,
        weight_kg=18,
        diet_type="vegetarian",
        allergies=["milk", "wheat"],
        region="north",
        days=2,
    )
    for day in plan.weekly_plan:
        for slot_items in day.meals.values():
            for item in slot_items:
                name_l = item.name.lower()
                assert "milk" not in name_l or "buttermilk" in name_l  # buttermilk still dairy but filtered by allergen tag
                # Stronger: check food allergens via database
    # Re-check via internal DB
    db = KidsNutriDatabase()
    for day in plan.weekly_plan:
        for slot_items in day.meals.values():
            for item in slot_items:
                food = db.get_food(item.food_id)
                if food:
                    assert "milk" not in food.allergens
                    assert "wheat" not in food.allergens
    print("✓ test_allergy_exclusion passed")


def test_region_preference():
    for region in ("north", "south", "east", "west", "pan"):
        plan = generate_diet_plan(
            age=8,
            weight_kg=25,
            region=region,
            diet_type="eggetarian",
            days=1,
        )
        assert plan.region in ("north", "south", "east", "west", "pan")
        assert len(plan.weekly_plan[0].meals["lunch"]) >= 1
    print("✓ test_region_preference passed")


def test_condition_adjustments():
    base = generate_diet_plan(age=7, weight_kg=22, condition="healthy_growth", days=1)
    under = generate_diet_plan(age=7, weight_kg=22, condition="underweight", days=1)
    over = generate_diet_plan(age=7, weight_kg=22, condition="obesity", days=1)

    assert under.targets.energy_kcal > base.targets.energy_kcal
    assert over.targets.energy_kcal < base.targets.energy_kcal
    assert under.targets.protein_g >= base.targets.protein_g
    print("✓ test_condition_adjustments passed")


def test_likes_dislikes():
    plan = generate_diet_plan(
        age=9,
        weight_kg=28,
        likes=["paneer", "banana", "roti"],
        dislikes=["fish", "mutton"],
        diet_type="vegetarian",
        days=2,
    )
    # Dislikes should not appear
    for day in plan.weekly_plan:
        for slot_items in day.meals.values():
            for item in slot_items:
                assert "fish" not in item.name.lower()
                assert "mutton" not in item.name.lower()
    print("✓ test_likes_dislikes passed")


def test_non_vegetarian():
    plan = generate_diet_plan(
        age=10,
        weight_kg=30,
        sex="boy",
        diet_type="non_vegetarian",
        region="east",
        days=2,
    )
    has_flesh_or_egg = False
    for day in plan.weekly_plan:
        for slot_items in day.meals.values():
            for item in slot_items:
                if any(k in item.name.lower() for k in ("chicken", "fish", "egg", "mutton")):
                    has_flesh_or_egg = True
    assert has_flesh_or_egg, "Non-veg plan should include at least one flesh/egg item"
    print("✓ test_non_vegetarian passed")


def test_targets_only():
    planner = DietPlanner()
    t = planner.calculate_targets_only(age=4, weight_kg=15, sex="any")
    assert t.energy_kcal > 1000
    assert t.protein_g > 10
    print("✓ test_targets_only passed")


def test_summary_and_dict():
    plan = generate_diet_plan(age=5, weight_kg=17, days=1)
    text = plan.summary_text()
    assert "7-Day" in text or "Day 1" in text
    d = plan.to_dict()
    assert "targets" in d and "weekly_plan" in d
    print("✓ test_summary_and_dict passed")


if __name__ == "__main__":
    test_basic_plan_generation()
    test_allergy_exclusion()
    test_region_preference()
    test_condition_adjustments()
    test_likes_dislikes()
    test_non_vegetarian()
    test_targets_only()
    test_summary_and_dict()
    print("\n✅ All diet planner tests passed.")
