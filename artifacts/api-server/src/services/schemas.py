"""JSON Schemas handed to the model as forced tool inputs."""
from __future__ import annotations

from typing import Any

STR: dict[str, Any] = {"type": "string"}
NUM: dict[str, Any] = {"type": "number"}
BOOL: dict[str, Any] = {"type": "boolean"}


def obj(props: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {"type": "object", "properties": props, "required": required or []}


def arr(item: dict[str, Any]) -> dict[str, Any]:
    return {"type": "array", "items": item}


def enum(*values: str) -> dict[str, Any]:
    return {"type": "string", "enum": list(values)}


DIET = enum("vegan", "vegetarian", "eggetarian", "non_vegetarian", "uncertain")
NUTRITION = obj(
    {
        "calories": NUM, "protein": NUM, "carbs": NUM, "fat": NUM, "fiber": NUM, "sugar": NUM, "sodiumMg": NUM,
    },
    ["calories", "protein", "carbs", "fat"],
)

FOOD_INFO = obj(
    {
        "answer": {**STR, "description": "Direct answer to the user's question, 1-4 sentences, plain language."},
        "isSingleFood": {**BOOL, "description": "True when the query is about one identifiable food or dish."},
        "clarifyingQuestion": STR,
        "food": obj(
            {
                "name": STR, "alternativeNames": arr(STR), "description": STR, "origin": STR,
                "category": enum("fruit", "vegetable", "grain", "legume", "dairy", "snack", "beverage", "dessert", "meat", "seafood", "egg", "mixed_dish", "condiment", "other"),
                "dietLabel": DIET, "dietNotes": STR,
                "ingredients": arr(STR), "ingredientsKnown": {**BOOL, "description": "True only if the ingredient list is standard/known for this food or supplied by the user."},
                "preparation": arr(STR),
                "servingDescription": {**STR, "description": "What one serving is, e.g. '1 medium roti (40 g)'."},
                "nutritionPerServing": NUTRITION,
                "servingSizes": arr(obj({"label": STR, "grams": NUM, "calories": NUM}, ["label"])),
                "allergens": arr(STR), "healthNotes": arr(STR), "regionalNotes": STR,
                "similarFoods": arr(STR), "healthierAlternatives": arr(STR), "dietaryAlternatives": arr(STR),
                "confidence": {**NUM, "description": "0-100 confidence in the facts above."},
            },
            ["name", "dietLabel", "ingredients", "confidence"],
        ),
    },
    ["answer", "isSingleFood"],
)

MEDIA_ITEM = obj(
    {
        "name": STR, "confidence": {**NUM, "description": "0-100 confidence in the identification."},
        "portion": obj({"description": STR, "grams": NUM}),
        "dietLabel": DIET, "dietBasis": STR,
        "ingredients": arr(obj({"name": STR, "evidence": enum("observed", "inferred", "user_provided")}, ["name", "evidence"])),
        "nutrition": {**NUTRITION, "description": "Approximate nutrition for the estimated portion. Omit if it cannot be estimated."},
        "micronutrients": arr(STR),
        "allergenFlags": arr(obj({"allergen": STR, "basis": STR}, ["allergen", "basis"])),
        "visibleCues": {**arr(STR), "description": "Visible appearance cues only (e.g. 'browning on edges'). Never conclude safety."},
    },
    ["name", "confidence", "dietLabel", "ingredients"],
)

MEDIA_ANALYSIS = obj(
    {
        "summary": STR,
        "items": arr(MEDIA_ITEM),
        "imageQuality": enum("good", "fair", "poor"),
        "needsClearerImage": BOOL,
        "clarifyingQuestions": arr(STR),
        "mealBalance": STR,
        "suggestions": arr(obj({"category": STR, "text": STR}, ["text"])),
        "caveats": arr(STR),
        "preparationSteps": {**arr(obj({"timestamp": NUM, "description": STR, "ingredientsAdded": arr(STR)}, ["description"])), "description": "Video only: visible steps in chronological order."},
        "processSummary": {**STR, "description": "Video only: short summary of what the frames show."},
    },
    ["items", "imageQuality", "needsClearerImage"],
)

INGREDIENT_ID = obj(
    {
        "ingredients": arr(obj({"name": STR, "confidence": NUM, "quantityEstimate": STR, "needsConfirmation": BOOL, "note": STR}, ["name", "confidence"])),
        "imageQuality": enum("good", "fair", "poor"),
        "clarifyingQuestions": arr(STR),
    },
    ["ingredients", "imageQuality"],
)

RECIPE = obj(
    {
        "name": STR, "description": STR, "cuisine": STR, "dietLabel": DIET,
        "prepMinutes": NUM, "cookMinutes": NUM, "difficulty": enum("easy", "medium", "hard"), "servings": NUM,
        "ingredients": arr(obj({"name": STR, "quantity": STR, "optional": BOOL, "pantryStaple": BOOL}, ["name", "quantity"])),
        "steps": arr(obj({"text": STR, "heat": STR, "timerMinutes": NUM}, ["text"])),
        "nutritionPerServing": NUTRITION,
        "substitutions": arr(obj({"for": STR, "use": STR, "note": STR}, ["for", "use"])),
        "servingSuggestions": arr(STR), "storage": STR, "safetyNotes": arr(STR), "tags": arr(STR),
    },
    ["name", "dietLabel", "prepMinutes", "cookMinutes", "difficulty", "servings", "ingredients", "steps"],
)
RECIPES = obj({"recipes": arr(RECIPE), "notes": STR, "clarifyingQuestion": STR}, ["recipes"])

SUGGESTIONS = obj(
    {
        "ideas": arr(obj({"name": STR, "why": STR, "dietLabel": DIET, "tags": arr(STR), "approxCalories": NUM, "ingredients": arr(STR)}, ["name", "why", "dietLabel", "ingredients"])),
        "notes": STR,
    },
    ["ideas"],
)
