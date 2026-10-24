"""Validation / normalisation of model output.

Everything the model returns is treated as untrusted input: strings are
trimmed and length-capped, numbers are coerced and range-checked, enums fall
back to a conservative value, and anything structurally unusable raises
``AIError('bad_response')`` instead of being rendered.
"""
from __future__ import annotations

from typing import Any

from .llm import AIError
from .safety import DIET_LABELS

CATEGORIES = ("fruit", "vegetable", "grain", "legume", "dairy", "snack", "beverage", "dessert", "meat", "seafood", "egg", "mixed_dish", "condiment", "other")
EVIDENCE = ("observed", "inferred", "user_provided")
DIFFICULTY = ("easy", "medium", "hard")
QUALITY = ("good", "fair", "poor")


def bad(message: str = "The AI answer was incomplete. Please try again.") -> AIError:
    return AIError("bad_response", message)


def s(value: Any, limit: int = 400, default: str = "") -> str:
    if value is None:
        return default
    text = " ".join(str(value).split())
    return text[:limit] if text else default


def num(value: Any, lo: float, hi: float, default: float | None = None) -> float | None:
    try:
        if isinstance(value, bool):
            raise ValueError
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number != number or number in (float("inf"), float("-inf")):
        return default
    return max(lo, min(hi, number))


def enum(value: Any, allowed: tuple[str, ...], default: str) -> str:
    text = s(value, 40).lower().replace("-", "_").replace(" ", "_")
    return text if text in allowed else default


def str_list(value: Any, *, max_items: int = 20, limit: int = 200) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = s(item, limit)
        if text and text.lower() not in (o.lower() for o in out):
            out.append(text)
        if len(out) >= max_items:
            break
    return out


def dict_list(value: Any, *, max_items: int = 20) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)][:max_items]


def nutrition(raw: Any, *, required: bool) -> dict[str, Any] | None:
    """Per-serving nutrition. Returns None when absent and not required."""
    if not isinstance(raw, dict):
        if required:
            raise bad("The AI answer did not include nutrition estimates. Please try again.")
        return None
    calories = num(raw.get("calories"), 0, 5000)
    protein = num(raw.get("protein"), 0, 300)
    carbs = num(raw.get("carbs"), 0, 600)
    fat = num(raw.get("fat"), 0, 400)
    if required and None in (calories, protein, carbs, fat):
        raise bad("The AI answer had incomplete nutrition estimates. Please try again.")
    if None in (calories, protein, carbs, fat):
        return None
    assert calories is not None and protein is not None and carbs is not None and fat is not None
    result: dict[str, Any] = {
        "calories": int(round(calories)),
        "protein": round(protein, 1),
        "carbs": round(carbs, 1),
        "fat": round(fat, 1),
        "fiber": round(num(raw.get("fiber"), 0, 150, 0.0) or 0.0, 1),
        "sugar": None if raw.get("sugar") is None else round(num(raw.get("sugar"), 0, 400, 0.0) or 0.0, 1),
        "sodiumMg": None if raw.get("sodiumMg") is None else int(round(num(raw.get("sodiumMg"), 0, 20000, 0.0) or 0.0)),
    }
    macro_energy = protein * 4 + carbs * 4 + fat * 9
    result["consistent"] = calories == 0 or macro_energy == 0 or abs(macro_energy - calories) / max(calories, 1) <= 0.35
    return result


def sum_nutrition(parts: list[dict[str, Any]]) -> dict[str, Any]:
    keys = ("calories", "protein", "carbs", "fat", "fiber")
    total = {k: sum(p.get(k) or 0 for p in parts) for k in keys}
    return {
        "calories": int(round(total["calories"])),
        "protein": round(total["protein"], 1),
        "carbs": round(total["carbs"], 1),
        "fat": round(total["fat"], 1),
        "fiber": round(total["fiber"], 1),
        "sugar": round(sum(p.get("sugar") or 0 for p in parts), 1) if any(p.get("sugar") is not None for p in parts) else None,
        "sodiumMg": int(sum(p.get("sodiumMg") or 0 for p in parts)) if any(p.get("sodiumMg") is not None for p in parts) else None,
        "consistent": all(p.get("consistent", True) for p in parts),
    }


def confidence(value: Any, default: int = 50) -> int:
    return int(round(num(value, 0, 100, default) or 0))


# ---------------------------------------------------------------- food info
def food_info(raw: dict[str, Any]) -> dict[str, Any]:
    answer = s(raw.get("answer"), 1500)
    if not answer:
        raise bad()
    out: dict[str, Any] = {
        "answer": answer,
        "isSingleFood": bool(raw.get("isSingleFood")),
        "clarifyingQuestion": s(raw.get("clarifyingQuestion"), 300) or None,
    }
    food = raw.get("food")
    if out["isSingleFood"] and isinstance(food, dict) and s(food.get("name"), 120):
        servings = []
        for item in dict_list(food.get("servingSizes"), max_items=6):
            label = s(item.get("label"), 80)
            if label:
                servings.append({
                    "label": label,
                    "grams": num(item.get("grams"), 0, 5000),
                    "calories": None if item.get("calories") is None else int(num(item.get("calories"), 0, 5000, 0) or 0),
                })
        out["food"] = {
            "name": s(food.get("name"), 120),
            "alternativeNames": str_list(food.get("alternativeNames"), max_items=8, limit=80),
            "description": s(food.get("description"), 700),
            "origin": s(food.get("origin"), 200) or None,
            "category": enum(food.get("category"), CATEGORIES, "other"),
            "dietLabel": enum(food.get("dietLabel"), DIET_LABELS, "uncertain"),
            "dietNotes": s(food.get("dietNotes"), 400) or None,
            "ingredients": str_list(food.get("ingredients"), max_items=25, limit=80),
            "ingredientsKnown": bool(food.get("ingredientsKnown")),
            "preparation": str_list(food.get("preparation"), max_items=8, limit=200),
            "nutritionPerServing": nutrition(food.get("nutritionPerServing"), required=False),
            "servingDescription": s(food.get("servingDescription"), 120) or None,
            "servingSizes": servings,
            "allergens": str_list(food.get("allergens"), max_items=12, limit=60),
            "healthNotes": str_list(food.get("healthNotes"), max_items=6, limit=240),
            "regionalNotes": s(food.get("regionalNotes"), 400) or None,
            "similarFoods": str_list(food.get("similarFoods"), max_items=6, limit=80),
            "healthierAlternatives": str_list(food.get("healthierAlternatives"), max_items=6, limit=120),
            "dietaryAlternatives": str_list(food.get("dietaryAlternatives"), max_items=6, limit=120),
            "confidence": confidence(food.get("confidence"), 60),
        }
    return out


# ------------------------------------------------------------ media analysis
def media_analysis(raw: dict[str, Any], *, is_video: bool) -> dict[str, Any]:
    items_in = dict_list(raw.get("items"), max_items=12)
    quality = enum(raw.get("imageQuality"), QUALITY, "fair")
    items: list[dict[str, Any]] = []
    for entry in items_in:
        name = s(entry.get("name"), 100)
        if not name:
            continue
        ingredients = []
        for ing in dict_list(entry.get("ingredients"), max_items=20):
            ing_name = s(ing.get("name"), 80)
            if ing_name:
                ingredients.append({"name": ing_name, "evidence": enum(ing.get("evidence"), EVIDENCE, "inferred")})
        portion = entry.get("portion") if isinstance(entry.get("portion"), dict) else {}
        items.append({
            "name": name,
            "confidence": confidence(entry.get("confidence"), 40),
            "portion": {
                "description": s(portion.get("description"), 120, "portion unclear"),
                "grams": num(portion.get("grams"), 0, 5000),
                "estimated": True,
            },
            "dietLabel": enum(entry.get("dietLabel"), DIET_LABELS, "uncertain"),
            "dietBasis": s(entry.get("dietBasis"), 300) or None,
            "ingredients": ingredients,
            "nutrition": nutrition(entry.get("nutrition"), required=False),
            "micronutrients": str_list(entry.get("micronutrients"), max_items=6, limit=40),
            "allergenFlags": [
                {"allergen": s(a.get("allergen"), 40), "basis": s(a.get("basis"), 200)}
                for a in dict_list(entry.get("allergenFlags"), max_items=8)
                if s(a.get("allergen"), 40)
            ],
            "visibleCues": str_list(entry.get("visibleCues"), max_items=6, limit=100),
        })
    out: dict[str, Any] = {
        "summary": s(raw.get("summary"), 500),
        "items": items,
        "imageQuality": quality,
        "needsClearerImage": bool(raw.get("needsClearerImage")) or (quality == "poor" and not items),
        "clarifyingQuestions": str_list(raw.get("clarifyingQuestions"), max_items=4, limit=200),
        "mealBalance": s(raw.get("mealBalance"), 500) or None,
        "suggestions": [
            {"category": s(x.get("category"), 40, "general"), "text": s(x.get("text"), 300)}
            for x in dict_list(raw.get("suggestions"), max_items=8)
            if s(x.get("text"), 300)
        ],
        "caveats": str_list(raw.get("caveats"), max_items=6, limit=240),
    }
    if is_video:
        steps = []
        for index, step in enumerate(dict_list(raw.get("preparationSteps"), max_items=20), start=1):
            text = s(step.get("description"), 300)
            if text:
                steps.append({
                    "order": index,
                    "timestamp": num(step.get("timestamp"), 0, 36000),
                    "description": text,
                    "ingredientsAdded": str_list(step.get("ingredientsAdded"), max_items=8, limit=60),
                })
        out["preparationSteps"] = steps
        out["processSummary"] = s(raw.get("processSummary"), 800) or None
    if not items and not out["needsClearerImage"]:
        raise bad("No food could be identified. Try a clearer photo with the food in view, or describe it in words.")
    return out


# --------------------------------------------------------------- ingredients
def ingredient_identification(raw: dict[str, Any]) -> dict[str, Any]:
    found = []
    for entry in dict_list(raw.get("ingredients"), max_items=40):
        name = s(entry.get("name"), 80)
        if not name:
            continue
        conf = confidence(entry.get("confidence"), 50)
        found.append({
            "name": name,
            "confidence": conf,
            "quantityEstimate": s(entry.get("quantityEstimate"), 60) or None,
            "needsConfirmation": bool(entry.get("needsConfirmation")) or conf < 70,
            "note": s(entry.get("note"), 160) or None,
        })
    quality = enum(raw.get("imageQuality"), QUALITY, "fair")
    result = {
        "ingredients": found,
        "imageQuality": quality,
        "clarifyingQuestions": str_list(raw.get("clarifyingQuestions"), max_items=4, limit=200),
    }
    if not found and quality != "poor":
        raise bad("No ingredients could be identified in that photo. Try a clearer, closer shot or type them in.")
    return result


# ------------------------------------------------------------------- recipes
def recipe(entry: dict[str, Any]) -> dict[str, Any] | None:
    name = s(entry.get("name"), 120)
    ingredients = []
    for ing in dict_list(entry.get("ingredients"), max_items=40):
        ing_name = s(ing.get("name"), 80)
        if ing_name:
            ingredients.append({
                "name": ing_name,
                "quantity": s(ing.get("quantity"), 60) or None,
                "optional": bool(ing.get("optional")),
                "pantryStaple": bool(ing.get("pantryStaple")),
            })
    steps = []
    for step in dict_list(entry.get("steps"), max_items=25):
        text = s(step.get("text"), 500)
        if text:
            steps.append({
                "text": text,
                "heat": s(step.get("heat"), 60) or None,
                "timerMinutes": None if step.get("timerMinutes") is None else int(num(step.get("timerMinutes"), 0, 1440, 0) or 0),
            })
    if not name or not ingredients or not steps:
        return None
    return {
        "name": name,
        "description": s(entry.get("description"), 400),
        "cuisine": s(entry.get("cuisine"), 60) or "Unspecified",
        "dietLabel": enum(entry.get("dietLabel"), DIET_LABELS, "uncertain"),
        "prepMinutes": int(num(entry.get("prepMinutes"), 0, 1440, 15) or 0),
        "cookMinutes": int(num(entry.get("cookMinutes"), 0, 1440, 20) or 0),
        "difficulty": enum(entry.get("difficulty"), DIFFICULTY, "easy"),
        "servings": int(num(entry.get("servings"), 1, 50, 2) or 2),
        "ingredients": ingredients,
        "steps": steps,
        "nutritionPerServing": nutrition(entry.get("nutritionPerServing"), required=False),
        "substitutions": [
            {"for": s(x.get("for"), 80), "use": s(x.get("use"), 120), "note": s(x.get("note"), 200) or None}
            for x in dict_list(entry.get("substitutions"), max_items=8)
            if s(x.get("for"), 80) and s(x.get("use"), 120)
        ],
        "servingSuggestions": str_list(entry.get("servingSuggestions"), max_items=5, limit=200),
        "storage": s(entry.get("storage"), 300) or None,
        "safetyNotes": str_list(entry.get("safetyNotes"), max_items=5, limit=240),
        "tags": str_list(entry.get("tags"), max_items=8, limit=40),
    }


def recipes(raw: dict[str, Any]) -> dict[str, Any]:
    cleaned = [r for r in (recipe(e) for e in dict_list(raw.get("recipes"), max_items=6)) if r]
    return {
        "recipes": cleaned,
        "notes": s(raw.get("notes"), 600) or None,
        "clarifyingQuestion": s(raw.get("clarifyingQuestion"), 300) or None,
    }


# --------------------------------------------------------------- suggestions
def suggestions(raw: dict[str, Any]) -> dict[str, Any]:
    ideas = []
    for entry in dict_list(raw.get("ideas"), max_items=10):
        name = s(entry.get("name"), 120)
        if not name:
            continue
        ideas.append({
            "name": name,
            "why": s(entry.get("why"), 300),
            "dietLabel": enum(entry.get("dietLabel"), DIET_LABELS, "uncertain"),
            "tags": str_list(entry.get("tags"), max_items=6, limit=40),
            "approxCalories": None if entry.get("approxCalories") is None else int(num(entry.get("approxCalories"), 0, 4000, 0) or 0),
            "ingredients": str_list(entry.get("ingredients"), max_items=15, limit=80),
        })
    if not ideas:
        raise bad()
    return {"ideas": ideas, "notes": s(raw.get("notes"), 500) or None}
