from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4


FoodSource = Literal["image", "video", "audio", "text"]

FOOD_PRESETS: list[dict[str, Any]] = [
    {
        "terms": ("salad", "greens", "grain bowl", "bowl"),
        "name": "Garden grain bowl",
        "ingredients": ["quinoa", "chickpeas", "baby spinach", "cucumber", "tahini"],
        "nutrition": {
            "calories": 485,
            "protein": 19,
            "carbs": 61,
            "fat": 18,
            "fiber": 12,
            "micronutrients": ["Iron", "Folate", "Magnesium", "Vitamin K"],
        },
        "healthScore": 91,
    },
    {
        "terms": ("chicken", "rice"),
        "name": "Grilled chicken rice bowl",
        "ingredients": ["grilled chicken", "brown rice", "broccoli", "lemon", "olive oil"],
        "nutrition": {
            "calories": 560,
            "protein": 42,
            "carbs": 58,
            "fat": 17,
            "fiber": 8,
            "micronutrients": ["Vitamin C", "Selenium", "Potassium", "Vitamin B6"],
        },
        "healthScore": 88,
    },
    {
        "terms": ("lentil", "dal", "curry"),
        "name": "Red lentil curry",
        "ingredients": ["red lentils", "tomato", "ginger", "coconut milk", "spinach"],
        "nutrition": {
            "calories": 430,
            "protein": 22,
            "carbs": 57,
            "fat": 13,
            "fiber": 16,
            "micronutrients": ["Iron", "Folate", "Potassium", "Vitamin A"],
        },
        "healthScore": 94,
    },
    {
        "terms": ("toast", "avocado"),
        "name": "Avocado toast",
        "ingredients": ["whole-grain sourdough", "avocado", "hemp seeds", "lemon"],
        "nutrition": {
            "calories": 385,
            "protein": 11,
            "carbs": 44,
            "fat": 21,
            "fiber": 11,
            "micronutrients": ["Potassium", "Folate", "Vitamin E", "Magnesium"],
        },
        "healthScore": 86,
    },
    {
        "terms": ("pasta", "noodle"),
        "name": "Tomato basil pasta",
        "ingredients": ["whole-wheat pasta", "tomatoes", "basil", "parmesan", "olive oil"],
        "nutrition": {
            "calories": 510,
            "protein": 20,
            "carbs": 68,
            "fat": 17,
            "fiber": 9,
            "micronutrients": ["Lycopene", "Calcium", "Vitamin C", "Iron"],
        },
        "healthScore": 82,
    },
]


def estimate_freshness(food: str, notes: str = "") -> dict[str, Any]:
    combined = f"{food} {notes}".lower()
    unsafe_terms = ("mold", "mould", "slimy", "rotten", "fuzzy", "sour smell", "black spots")
    aging_terms = ("soft", "brown", "wilting", "wrinkled", "past date", "bruised")

    if any(term in combined for term in unsafe_terms):
        status = "unsafe"
        label = "Potentially unsafe"
        guidance = "Do not taste food that may be spoiled. Discard it if spoilage is visible or the smell or texture seems unusual."
        storage_tip = "Keep raw and ready-to-eat foods separate. Clean the storage area before placing new food inside."
        confidence = 91
    elif any(term in combined for term in aging_terms):
        status = "consume_soon"
        label = "Consume soon"
        guidance = "Use promptly if it still looks and smells normal. Discard it if you notice mold, an off smell, or a slimy texture."
        storage_tip = "Refrigerate promptly in a clean, covered container and keep it away from raw foods."
        confidence = 84
    else:
        status = "fresh"
        label = "Looks fresh"
        guidance = "No obvious spoilage cues were described. This estimate cannot confirm food safety; check storage time, temperature, smell, and texture."
        storage_tip = "Store promptly at the recommended temperature and keep raw foods separate."
        confidence = 78

    return {
        "status": status,
        "label": label,
        "guidance": guidance,
        "storageTip": storage_tip,
        "confidence": confidence,
        "analyzedAt": datetime.now(timezone.utc).isoformat(),
    }


def analyze_food(source: FoodSource, file_name: str | None, description: str) -> dict[str, Any]:
    prompt = description.strip()
    lowered = prompt.lower()
    preset = next(
        (candidate for candidate in FOOD_PRESETS if any(term in lowered for term in candidate["terms"])),
        {
            "name": "Roasted vegetable plate",
            "ingredients": ["seasonal vegetables", "olive oil", "herbs", "whole grains"],
            "nutrition": {
                "calories": 440,
                "protein": 14,
                "carbs": 54,
                "fat": 19,
                "fiber": 10,
                "micronutrients": ["Vitamin A", "Vitamin C", "Folate", "Potassium"],
            },
            "healthScore": 85,
        },
    )
    dish_name = preset["name"]
    if prompt and len(prompt.split()) < 5 and source == "text":
        dish_name = prompt.strip().title()

    confidence = min(96, 76 + len(prompt.split()) * 2)
    ingredients = preset["ingredients"]
    nutrition = preset["nutrition"]
    calorie_total = max(int(nutrition["calories"]), 1)
    macro_energy = (
        float(nutrition["protein"]) * 4
        + float(nutrition["carbs"]) * 4
        + float(nutrition["fat"]) * 9
    )
    health_breakdown = [
        {
            "label": "Protein",
            "score": min(100, round(float(nutrition["protein"]) / 30 * 100)),
            "detail": f"{nutrition['protein']} g per serving",
        },
        {
            "label": "Fiber",
            "score": min(100, round(float(nutrition["fiber"]) / 14 * 100)),
            "detail": f"{nutrition['fiber']} g per serving",
        },
        {
            "label": "Ingredient variety",
            "score": min(100, 40 + len(ingredients) * 12),
            "detail": f"{len(ingredients)} possible ingredients",
        },
        {
            "label": "Macro estimate",
            "score": max(0, min(100, round(100 - abs(macro_energy - calorie_total) / calorie_total * 100))),
            "detail": "Estimated macro energy compared with listed calories",
        },
    ]
    return {
        "id": str(uuid4()),
        "dishName": dish_name,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "fileName": file_name,
        "ingredients": ingredients,
        "confidence": confidence,
        "nutrition": nutrition,
        "healthScore": preset["healthScore"],
        "healthBreakdown": health_breakdown,
        "freshness": estimate_freshness(dish_name, prompt),
    }


def analyze_hygiene(kitchen_name: str, video_name: str | None) -> dict[str, Any]:
    return {
        "id": str(uuid4()),
        "kitchenName": kitchen_name,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "videoName": video_name,
        "gloveCompliance": 88,
        "hairnetCompliance": 94,
        "cleanlinessScore": 82,
        "contaminationRisk": "moderate",
        "safetyScore": 87,
        "alerts": [
            "Review glove changes between raw and ready-to-eat tasks.",
            "Wipe and sanitize the main preparation surface between ingredients.",
        ],
    }


def make_chef_guide(
    dish: str, ingredients: list[str], allergies: list[str]
) -> dict[str, Any]:
    allergy_tokens = {
        "milk": ("milk", "dairy", "cheese", "yogurt", "butter", "cream"),
        "peanut": ("peanut", "groundnut"),
        "tree nut": ("almond", "cashew", "walnut", "pistachio", "hazelnut"),
        "egg": ("egg", "mayonnaise"),
        "wheat": ("wheat", "flour", "bread", "pasta", "couscous"),
        "soy": ("soy", "tofu", "edamame"),
        "shellfish": ("shrimp", "prawn", "crab", "lobster", "shellfish"),
        "fish": ("salmon", "tuna", "cod", "fish"),
    }
    ingredient_text = " ".join(ingredients).lower()
    warnings: list[str] = []
    substitutions: list[str] = []
    for allergy in allergies:
        key = allergy.lower().strip()
        matched_terms = allergy_tokens.get(key, (key,) if key else ())
        if key and any(term in ingredient_text for term in matched_terms):
            warnings.append(
                f"Your ingredient list may contain {allergy}. Check every label and avoid cross-contact."
            )
            if key in ("milk", "dairy"):
                substitutions.append("Use unsweetened oat or soy milk only if it is safe for your allergy profile.")
            elif key == "egg":
                substitutions.append("Try a flaxseed or chia binder where the recipe allows.")
            elif key == "wheat":
                substitutions.append("Use a certified gluten-free grain or flour if suitable for your needs.")

    if not warnings:
        warnings.append(
            "No match was found for the saved allergy list. Always check package labels and prevent cross-contact."
        )
    if not substitutions:
        substitutions.append("Swap vegetables or herbs based on what is in season and safe for you.")

    first_ingredient = ingredients[0] if ingredients else "your ingredients"
    steps = [
        f"Gather and wash the ingredients for {dish}. Keep raw and ready-to-eat items separate.",
        f"Prepare {first_ingredient} first, then cut the remaining ingredients into even pieces.",
        "Warm a pan over medium heat and add a small amount of oil or water.",
        f"Cook the ingredients in stages until tender and thoroughly heated, then season to taste.",
        "Plate the dish, check its temperature where appropriate, and serve immediately.",
    ]
    voice_script = " ".join(
        f"Step {index}. {step}" for index, step in enumerate(steps, start=1)
    )
    return {
        "dish": dish,
        "prepMinutes": 15,
        "cookMinutes": 25,
        "servings": 2,
        "steps": steps,
        "substitutions": substitutions,
        "allergyWarnings": warnings,
        "voiceScript": voice_script,
    }
