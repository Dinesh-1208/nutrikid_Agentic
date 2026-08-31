"""
KidsNutriBite — Deterministic Indian Pediatric Diet Planner
===========================================================
Uses ONLY the trusted data from:
    data/structured_db/foods.json

No hard-coded food list.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


# Default location of foods.json relative to project root
DEFAULT_FOODS_PATH = Path(__file__).resolve().parents[1] / "data" / "structured_db" / "foods.json"


# ICMR-NIN reference values (official numbers, not food data)
ICMR_ENERGY = {
    (1, 3):  {"any": 1110},
    (4, 6):  {"any": 1360},
    (7, 9):  {"any": 1700},
    (10, 12): {"boy": 2220, "girl": 2060},
    (13, 15): {"boy": 2860, "girl": 2400},
    (16, 18): {"boy": 3320, "girl": 2500},
}

ICMR_PROTEIN = {
    (1, 3):  {"any": 12.5},
    (4, 6):  {"any": 16.0},
    (7, 9):  {"any": 23.0},
    (10, 12): {"boy": 32.0, "girl": 33.0},
    (13, 15): {"boy": 45.0, "girl": 43.0},
    (16, 18): {"boy": 55.0, "girl": 46.0},
}

CONDITION_ADJUSTMENTS = {
    "healthy_growth":    {"energy_mult": 1.00, "protein_mult": 1.00},
    "underweight":       {"energy_mult": 1.20, "protein_mult": 1.30},
    "overweight":        {"energy_mult": 0.85, "protein_mult": 1.10},
    "obesity":           {"energy_mult": 0.80, "protein_mult": 1.15},
    "anemia":            {"energy_mult": 1.05, "protein_mult": 1.10},
    "constipation":      {"energy_mult": 1.00, "protein_mult": 1.00},
    "diarrhea_recovery": {"energy_mult": 1.10, "protein_mult": 1.20},
    "diabetes":          {"energy_mult": 0.95, "protein_mult": 1.10},
    "catch_up_growth":   {"energy_mult": 1.25, "protein_mult": 1.40},
    "fever_recovery":    {"energy_mult": 1.15, "protein_mult": 1.25},
    "picky_eater":       {"energy_mult": 1.00, "protein_mult": 1.00},
}

MEAL_SLOTS = ["breakfast", "mid_morning", "lunch", "evening_snack", "dinner"]

MEAL_CALORIE_SHARE = {
    "breakfast": 0.25,
    "mid_morning": 0.10,
    "lunch": 0.30,
    "evening_snack": 0.10,
    "dinner": 0.25,
}

REGION_ALIASES = {
    "north": ["north", "north_india", "punjab", "delhi", "up", "haryana", "rajasthan"],
    "south": ["south", "south_india", "tamil", "kerala", "karnataka", "andhra", "telangana"],
    "east":  ["east", "east_india", "bengal", "odisha", "bihar", "jharkhand"],
    "west":  ["west", "west_india", "gujarat", "maharashtra", "goa"],
    "pan":   ["pan", "india", "all", "any"],
}


@dataclass
class FoodItem:
    food_id: str
    food_name: str
    category: str
    energy_kcal_per_100g: float
    protein_g: float
    fat_g: float
    carbs_g: float
    iron_mg: float
    portion_unit: str
    age_min: float
    allergy_tags: List[str]
    meal_types: List[str]
    tags: List[str]
    region: List[str]
    vegetarian: bool
    eggetarian: bool = False

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "FoodItem":
        def safe_float(val, default=0.0):
            try:
                return float(val) if val not in (None, "", []) else default
            except (TypeError, ValueError):
                return default

        def safe_list(val):
            if isinstance(val, list):
                return [str(x).lower() for x in val]
            return []

        cat = str(d.get("category", "")).lower()
        vegetarian = d.get("vegetarian")
        if vegetarian is None:
            vegetarian = cat not in ("flesh", "egg", "poultry")
        eggetarian = bool(d.get("eggetarian", False))
        if cat == "egg":
            eggetarian = True
            vegetarian = False

        return cls(
            food_id=str(d.get("food_id", "")),
            food_name=str(d.get("food_name", "unknown")),
            category=cat,
            energy_kcal_per_100g=safe_float(d.get("energy_kcal_per_100g")),
            protein_g=safe_float(d.get("protein_g")),
            fat_g=safe_float(d.get("fat_g")),
            carbs_g=safe_float(d.get("carbs_g")),
            iron_mg=safe_float(d.get("iron_mg")),
            portion_unit=str(d.get("portion_unit", "1 serving")),
            age_min=safe_float(d.get("age_min"), 1),
            allergy_tags=safe_list(d.get("allergy_tags")),
            meal_types=safe_list(d.get("meal_types")),
            tags=safe_list(d.get("tags")),
            region=safe_list(d.get("region")) or ["pan"],
            vegetarian=bool(vegetarian),
            eggetarian=eggetarian,
        )


@dataclass
class NutrientTargets:
    energy_kcal: float
    protein_g: float
    fat_g: float
    carb_g: float
    notes: List[str] = field(default_factory=list)


@dataclass
class MealItem:
    food_id: str
    name: str
    portion_desc: str
    kcal: float
    protein_g: float
    fat_g: float
    carb_g: float


@dataclass
class DayMeal:
    day: int
    meals: Dict[str, List[MealItem]]
    day_totals: Dict[str, float]
    notes: List[str] = field(default_factory=list)


@dataclass
class DietPlan:
    child_profile: Dict[str, Any]
    targets: NutrientTargets
    weekly_plan: List[DayMeal]
    general_advice: List[str]
    warnings: List[str] = field(default_factory=list)
    region: str = "pan"
    diet_type: str = "vegetarian"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "child_profile": self.child_profile,
            "targets": asdict(self.targets),
            "region": self.region,
            "diet_type": self.diet_type,
            "weekly_plan": [
                {
                    "day": d.day,
                    "meals": {
                        slot: [asdict(item) for item in items]
                        for slot, items in d.meals.items()
                    },
                    "day_totals": d.day_totals,
                    "notes": d.notes,
                }
                for d in self.weekly_plan
            ],
            "general_advice": self.general_advice,
            "warnings": self.warnings,
        }

    def summary_text(self) -> str:
        lines = []
        p = self.child_profile
        lines.append("### Indian Diet Plan (from your foods.json)")
        lines.append(
            f"**Child:** Age {p.get('age')} yrs | Weight {p.get('weight_kg')} kg | "
            f"Sex: {p.get('sex', 'any')} | Condition: {p.get('condition', 'healthy_growth')}"
        )
        lines.append(f"**Region:** {self.region.title()} | **Diet type:** {self.diet_type}")
        lines.append(
            f"**Daily Targets:** {self.targets.energy_kcal:.0f} kcal | "
            f"Protein {self.targets.protein_g:.0f} g | "
            f"Fat {self.targets.fat_g:.0f} g | Carb {self.targets.carb_g:.0f} g"
        )
        if self.targets.notes:
            lines.append("**Adjustments:** " + "; ".join(self.targets.notes))
        lines.append("")

        for day in self.weekly_plan:
            lines.append(f"#### Day {day.day}")
            for slot in MEAL_SLOTS:
                items = day.meals.get(slot, [])
                if not items:
                    continue
                names = ", ".join(f"{it.name} ({it.portion_desc})" for it in items)
                slot_kcal = sum(it.kcal for it in items)
                lines.append(
                    f"- **{slot.replace('_', ' ').title()}** (~{slot_kcal:.0f} kcal): {names}"
                )
            tot = day.day_totals
            lines.append(
                f"  → Day total: {tot['kcal']:.0f} kcal | "
                f"P {tot['protein_g']:.0f} g | F {tot['fat_g']:.0f} g | C {tot['carb_g']:.0f} g"
            )
            if day.notes:
                lines.append("  Notes: " + "; ".join(day.notes))
            lines.append("")

        if self.general_advice:
            lines.append("### General Advice")
            for a in self.general_advice:
                lines.append(f"- {a}")
        if self.warnings:
            lines.append("\n### Warnings")
            for w in self.warnings:
                lines.append(f"- ⚠️ {w}")
        return "\n".join(lines)


class KidsNutriDatabase:
    """Loads foods ONLY from data/structured_db/foods.json"""

    def __init__(self, foods_path: Optional[str | Path] = None):
        self.foods_path = Path(foods_path) if foods_path else DEFAULT_FOODS_PATH
        self.foods: Dict[str, FoodItem] = {}
        self._load()

    def _load(self) -> None:
        if not self.foods_path.exists():
            raise FileNotFoundError(
                f"foods.json not found at: {self.foods_path}\n"
                "Please make sure data/structured_db/foods.json exists."
            )
        with open(self.foods_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        for item in raw:
            energy = item.get("energy_kcal_per_100g")
            if energy in (None, "", []):
                continue
            try:
                food = FoodItem.from_dict(item)
                if food.energy_kcal_per_100g > 0:
                    self.foods[food.food_id] = food
            except Exception:
                continue

        if not self.foods:
            raise ValueError("No usable foods loaded from foods.json")

    def list_foods(
        self,
        region: str = "pan",
        diet_type: str = "vegetarian",
        exclude_allergens: Optional[Set[str]] = None,
        age: float = 1,
        meal_type: Optional[str] = None,
        required_tags: Optional[List[str]] = None,
    ) -> List[FoodItem]:
        region = self._normalize_region(region)
        exclude_allergens = {a.lower() for a in (exclude_allergens or [])}
        results = []

        for f in self.foods.values():
            if f.age_min > age:
                continue
            if region != "pan" and region not in f.region and "pan" not in f.region:
                continue
            if diet_type == "vegetarian" and not f.vegetarian:
                continue
            if diet_type == "eggetarian" and not (f.vegetarian or f.eggetarian):
                continue
            if any(a in f.allergy_tags for a in exclude_allergens):
                continue
            if meal_type and f.meal_types and meal_type not in f.meal_types:
                continue
            if required_tags and not any(t in f.tags for t in required_tags):
                continue
            results.append(f)
        return results

    @staticmethod
    def _normalize_region(region: str) -> str:
        r = region.lower().strip().replace(" ", "_").replace("-", "_")
        for canon, aliases in REGION_ALIASES.items():
            if r in aliases or r == canon:
                return canon
        return "pan"


class DietPlanner:
    def __init__(self, db_or_path=None, seed: int = 42):
        """
        Accepts either:
        - KidsNutriDatabase instance  (what main.py does: DietPlanner(db))
        - path to foods.json
        - None (uses default path)
        """
        if isinstance(db_or_path, KidsNutriDatabase):
            self.db = db_or_path
        else:
            self.db = KidsNutriDatabase(db_or_path)
        self.rng = random.Random(seed)

    def generate_meal_plan(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        This method is required by main.py
        """
        age = float(profile.get("age") or profile.get("age_years") or 7)
        weight = float(profile.get("weight") or profile.get("weight_kg") or 20)
        condition = str(profile.get("condition") or "healthy_growth")
        allergies = profile.get("allergies") or []
        if isinstance(allergies, str):
            allergies = [a.strip() for a in allergies.split(",") if a.strip()]

        region = str(profile.get("region") or "pan")
        diet_type = str(profile.get("diet_type") or profile.get("diet") or "vegetarian")
        sex = str(profile.get("sex") or "any")
        likes = profile.get("likes") or []
        dislikes = profile.get("dislikes") or []
        days = int(profile.get("days") or 3)

        plan = self.create_plan(
            age=age,
            weight_kg=weight,
            sex=sex,
            condition=condition,
            region=region,
            diet_type=diet_type,
            allergies=allergies,
            likes=likes,
            dislikes=dislikes,
            days=days,
        )
        return plan.to_dict()

    def create_plan(
        self,
        age: float,
        weight_kg: float,
        sex: str = "any",
        condition: str = "healthy_growth",
        region: str = "pan",
        diet_type: str = "vegetarian",
        allergies: Optional[List[str]] = None,
        likes: Optional[List[str]] = None,
        dislikes: Optional[List[str]] = None,
        activity: str = "moderate",
        days: int = 7,
    ) -> DietPlan:
        allergies = [a.lower().strip() for a in (allergies or [])]
        likes = [l.lower().strip() for l in (likes or [])]
        dislikes = [d.lower().strip() for d in (dislikes or [])]
        sex = (sex or "any").lower().strip()
        condition = condition.lower().strip().replace(" ", "_")
        region = self.db._normalize_region(region)
        diet_type = diet_type.lower().strip()

        profile = {
            "age": age,
            "weight_kg": weight_kg,
            "sex": sex,
            "condition": condition,
            "region": region,
            "diet_type": diet_type,
            "allergies": allergies,
            "likes": likes,
            "dislikes": dislikes,
            "activity": activity,
        }

        targets = self._compute_targets(age, weight_kg, sex, condition, activity)
        warnings: List[str] = []
        advice: List[str] = []

        if age < 1:
            warnings.append(
                "This planner is for children ≥ 1 year. "
                "Infants need pediatrician guidance."
            )

        advice.extend(self._condition_advice(condition))
        advice.extend(self._region_advice(region))
        advice.append(
            "This plan uses only foods from your data/structured_db/foods.json. "
            "It does not replace medical advice."
        )

        pool = self.db.list_foods(
            region=region,
            diet_type=diet_type,
            exclude_allergens=set(allergies),
            age=age,
        )

        if dislikes:
            pool = [f for f in pool if not any(d in f.food_name.lower() for d in dislikes)]

        if not pool:
            warnings.append("No foods left after filters. Using pan-India vegetarian.")
            pool = self.db.list_foods(region="pan", diet_type="vegetarian", age=age)

        scored = self._score_foods(pool, likes)

        weekly: List[DayMeal] = []
        for day_idx in range(1, days + 1):
            day_meal = self._build_day(day_idx, targets, scored, condition)
            weekly.append(day_meal)

        return DietPlan(
            child_profile=profile,
            targets=targets,
            weekly_plan=weekly,
            general_advice=advice,
            warnings=warnings,
            region=region,
            diet_type=diet_type,
        )

    def _compute_targets(self, age, weight_kg, sex, condition, activity) -> NutrientTargets:
        notes = []
        base_energy = self._lookup(ICMR_ENERGY, age, sex) or (weight_kg * 70)
        act_mult = {"sedentary": 0.90, "moderate": 1.00, "active": 1.15}.get(activity, 1.0)
        energy = base_energy * act_mult

        adj = CONDITION_ADJUSTMENTS.get(condition, CONDITION_ADJUSTMENTS["healthy_growth"])
        energy *= adj["energy_mult"]
        if adj["energy_mult"] != 1.0:
            notes.append(f"Condition '{condition}' energy ×{adj['energy_mult']}")

        base_protein = self._lookup(ICMR_PROTEIN, age, sex) or max(12.0, weight_kg * 1.0)
        protein = max(base_protein * adj["protein_mult"], weight_kg * 0.9)

        fat_g = (energy * 0.30) / 9.0
        protein_kcal = protein * 4.0
        carb_g = max((energy - protein_kcal - fat_g * 9.0) / 4.0, 80.0)

        return NutrientTargets(
            energy_kcal=round(energy, 0),
            protein_g=round(protein, 1),
            fat_g=round(fat_g, 1),
            carb_g=round(carb_g, 1),
            notes=notes,
        )

    @staticmethod
    def _lookup(table, age, sex):
        for (lo, hi), vals in table.items():
            if lo <= age <= hi:
                if sex in vals:
                    return float(vals[sex])
                return float(vals.get("any", list(vals.values())[0]))
        return None

    def _score_foods(self, pool, likes):
        scored = []
        for f in pool:
            score = 1.0
            name = f.food_name.lower()
            for like in likes:
                if like in name or like in f.category or like in f.tags:
                    score += 2.5
            if "easy_digest" in f.tags or "soft" in f.tags:
                score += 0.5
            if "iron_rich" in f.tags:
                score += 0.4
            scored.append((score, f))
        scored.sort(key=lambda x: (-x[0], x[1].food_id))
        return scored

    def _build_day(self, day, targets, scored_pool, condition):
        meals = {s: [] for s in MEAL_SLOTS}
        used = set()
        notes = []

        def pick(categories, prefer_tags=None, n=1, meal_type=None):
            candidates = []
            for score, f in scored_pool:
                if f.food_id in used:
                    continue
                if categories and f.category not in categories:
                    continue
                if meal_type and f.meal_types and meal_type not in f.meal_types:
                    continue
                s = score
                if prefer_tags and any(t in f.tags for t in prefer_tags):
                    s += 1.0
                candidates.append((s, f))
            candidates.sort(key=lambda x: -x[0])
            chosen = []
            for _, f in candidates:
                if len(chosen) >= n:
                    break
                chosen.append(f)
                used.add(f.food_id)
            return chosen

        iron_focus = condition in ("anemia", "underweight", "catch_up_growth")
        soft_focus = condition in ("diarrhea_recovery", "fever_recovery")

        # Breakfast
        b_items = pick(["cereal", "balanced_meal"], ["soft", "easy_digest"], 1, "breakfast")
        b_items += pick(["dairy", "egg"], None, 1)
        b_items += pick(["fruit"], None, 1)
        share = targets.energy_kcal * MEAL_CALORIE_SHARE["breakfast"] / max(len(b_items), 1)
        for f in b_items:
            meals["breakfast"].append(self._to_item(f, share))

        # Mid-morning
        s_items = pick(["fruit", "snack", "dairy"], ["iron_rich"] if iron_focus else None, 1)
        share = targets.energy_kcal * MEAL_CALORIE_SHARE["mid_morning"] / max(len(s_items), 1)
        for f in s_items:
            meals["mid_morning"].append(self._to_item(f, share))

        # Lunch
        l_items = pick(["cereal", "balanced_meal"], ["soft"] if soft_focus else None, 1, "lunch")
        l_items += pick(["pulse"], ["iron_rich"] if iron_focus else None, 1)
        l_items += pick(["vegetable"], None, 1)
        l_items += pick(["dairy", "egg", "flesh"], ["protein_rich"], 1)
        share = targets.energy_kcal * MEAL_CALORIE_SHARE["lunch"] / max(len(l_items), 1)
        for f in l_items:
            meals["lunch"].append(self._to_item(f, share))

        # Evening snack
        e_items = pick(["snack", "fruit", "dairy"], None, 1)
        share = targets.energy_kcal * MEAL_CALORIE_SHARE["evening_snack"] / max(len(e_items), 1)
        for f in e_items:
            meals["evening_snack"].append(self._to_item(f, share))

        # Dinner
        d_items = pick(["cereal", "balanced_meal"], ["easy_digest", "soft"], 1, "dinner")
        d_items += pick(["pulse"], None, 1)
        d_items += pick(["vegetable"], None, 1)
        d_items += pick(["dairy", "egg", "flesh"], None, 1)
        share = targets.energy_kcal * MEAL_CALORIE_SHARE["dinner"] / max(len(d_items), 1)
        for f in d_items:
            meals["dinner"].append(self._to_item(f, share))

        totals = {"kcal": 0.0, "protein_g": 0.0, "fat_g": 0.0, "carb_g": 0.0}
        for items in meals.values():
            for it in items:
                totals["kcal"] += it.kcal
                totals["protein_g"] += it.protein_g
                totals["fat_g"] += it.fat_g
                totals["carb_g"] += it.carb_g
        for k in totals:
            totals[k] = round(totals[k], 1)

        if iron_focus:
            notes.append("Iron-rich foods prioritised.")
        if soft_focus:
            notes.append("Soft / easy-to-digest foods preferred.")

        return DayMeal(day=day, meals=meals, day_totals=totals, notes=notes)

    def _to_item(self, food: FoodItem, target_kcal: float) -> MealItem:
        if food.energy_kcal_per_100g <= 0:
            scale = 1.0
        else:
            desired_g = (target_kcal / food.energy_kcal_per_100g) * 100
            scale = max(0.3, min(2.0, desired_g / 100))
        return MealItem(
            food_id=food.food_id,
            name=food.food_name.replace("_", " ").title(),
            portion_desc=food.portion_unit,
            kcal=round(food.energy_kcal_per_100g * scale, 1),
            protein_g=round(food.protein_g * scale, 1),
            fat_g=round(food.fat_g * scale, 1),
            carb_g=round(food.carbs_g * scale, 1),
        )

    def _condition_advice(self, condition):
        advice = {
            "anemia": [
                "Include iron-rich foods (ragi, lentils, green leafy vegetables, egg).",
                "Pair with vitamin-C foods (amla, papaya) to improve iron absorption.",
                "Avoid tea/coffee with meals.",
            ],
            "underweight": [
                "Offer energy-dense foods in small frequent meals.",
                "Include full-fat dairy, banana, nuts (if age-appropriate).",
            ],
            "diarrhea_recovery": [
                "Prefer soft foods: khichdi, curd, banana, rice.",
                "Avoid spicy and oily foods until recovery.",
            ],
            "constipation": [
                "Increase fibre (fruits, vegetables, millets) and water.",
            ],
            "diabetes": [
                "Prefer millets, pulses, vegetables. Keep meal timings regular.",
            ],
        }
        return advice.get(condition, [
            "Maintain regular meal timings and include variety from all food groups."
        ])

    def _region_advice(self, region):
        tips = {
            "south": ["South Indian template: idli/dosa/rice + sambar + vegetable + curd."],
            "north": ["North Indian template: roti + dal + sabzi + curd."],
            "west":  ["Include poha, millets, and buttermilk."],
            "east":  ["Rice + dal + fish (if non-veg) + green vegetables."],
        }
        return tips.get(region, ["Rotate cereals and pulses across the week."])


def generate_diet_plan(
    age: float,
    weight_kg: float,
    sex: str = "any",
    condition: str = "healthy_growth",
    region: str = "pan",
    diet_type: str = "vegetarian",
    allergies: Optional[List[str]] = None,
    likes: Optional[List[str]] = None,
    dislikes: Optional[List[str]] = None,
    activity: str = "moderate",
    days: int = 7,
    foods_path: Optional[str] = None,
) -> DietPlan:
    planner = DietPlanner(foods_path=foods_path)
    return planner.create_plan(
        age=age,
        weight_kg=weight_kg,
        sex=sex,
        condition=condition,
        region=region,
        diet_type=diet_type,
        allergies=allergies,
        likes=likes,
        dislikes=dislikes,
        activity=activity,
        days=days,
    )


if __name__ == "__main__":
    plan = generate_diet_plan(
        age=7,
        weight_kg=22,
        sex="boy",
        condition="anemia",
        region="south",
        diet_type="eggetarian",
        allergies=["peanut"],
        likes=["idli", "egg", "banana"],
        days=2,
    )
    print(plan.summary_text())
