"""Food Verse AI workflows: lookup, image/video analysis, Chef AI, suggestions.

Each function takes an ``LLMClient`` so providers can be swapped or faked in
tests. Model output is validated (``validators``) and then re-checked against
deterministic safety rules (``safety``) before it is returned.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Callable, Iterable
from uuid import uuid4

from . import prompts, safety, schemas, validators as v
from .llm import AIError, LLMClient
from .media import MAX_IMAGES, MAX_VIDEO_FRAMES, MediaItem, image_blocks, parse_images

NutritionLookup = Callable[[str], dict[str, Any] | None]
ALLERGY_FOOTER = "Always check ingredient labels and ask about cross-contact; this tool cannot confirm a food is safe for an allergy."


def _data(label: str, text: str) -> str:
    return f"<{label}>\n{text.strip()}\n</{label}>"


def _context_lines(diet: str, allergies: list[str], goal: str | None = None) -> str:
    lines = [f"Diet convention: {safety.normalize_diet(diet)}"]
    lines.append("Allergies/exclusions: " + (", ".join(allergies) if allergies else "none stated"))
    if goal:
        lines.append(f"Goal: {goal}")
    return "\n".join(lines)


def _clean_list(values: Iterable[str] | None, *, limit: int = 20) -> list[str]:
    return v.str_list(list(values or []), max_items=limit, limit=60)


# ------------------------------------------------------------------ lookup
def search_food(
    llm: LLMClient,
    query: str,
    *,
    diet: str = "none",
    allergies: list[str] | None = None,
    ingredient_list: list[str] | None = None,
    nutrition_lookup: NutritionLookup | None = None,
) -> dict[str, Any]:
    query = " ".join((query or "").split())
    if len(query) < 2:
        raise AIError("invalid_input", "Type a food name or a question (at least two characters).")
    if len(query) > 400:
        raise AIError("invalid_input", "That question is too long. Please keep it under 400 characters.")
    allergies = _clean_list(allergies)
    provided = _clean_list(ingredient_list, limit=40)
    text = _data("user_query", query) + "\n" + _context_lines(diet, allergies)
    if provided:
        text += "\n" + _data("user_supplied_ingredients", ", ".join(provided))
    raw = llm.complete_json(
        system=prompts.FOOD_INFO,
        content=[{"type": "text", "text": text}],
        tool_name="food_answer",
        tool_description="Return the structured answer about the food or question.",
        schema=schemas.FOOD_INFO,
        max_tokens=3000,
    )
    result = v.food_info(raw)
    food = result.get("food")
    if food:
        label, certainty, note = safety.reconcile_diet(
            food["dietLabel"], food["ingredients"], visual_only=False,
            ingredient_list_provided=bool(provided) or food["ingredientsKnown"],
        )
        food["dietLabel"], food["dietCertainty"] = label, certainty
        if note:
            food["dietNotes"] = " ".join(filter(None, [food.get("dietNotes"), note]))
        if food["confidence"] < 50 and certainty == "confirmed" and label != "non_vegetarian":
            food["dietCertainty"] = "likely"
        food["fitsYourDiet"] = safety.fits_diet(label, diet, food["ingredients"])
        hits = safety.allergen_hits(allergies, food["ingredients"] + food["allergens"])
        food["allergyAlerts"] = sorted({f"May contain {a.lower()} ({term})." for a, term, _ in hits})
        food["nutritionBasis"] = "ai_estimate"
        food["verifiedReference"] = nutrition_lookup(food["name"]) if nutrition_lookup else None
    result["disclaimer"] = (
        "Nutrition values are AI estimates unless a verified reference is shown. " + ALLERGY_FOOTER
    )
    return result


# ------------------------------------------------------ image / video / text
def _health_breakdown(nutrition: dict[str, Any], ingredient_count: int) -> list[dict[str, Any]]:
    calories = max(int(nutrition["calories"]), 1)
    macro_energy = nutrition["protein"] * 4 + nutrition["carbs"] * 4 + nutrition["fat"] * 9
    return [
        {"label": "Protein", "score": min(100, round(nutrition["protein"] / 30 * 100)), "detail": f"{nutrition['protein']} g estimated"},
        {"label": "Fiber", "score": min(100, round(nutrition["fiber"] / 14 * 100)), "detail": f"{nutrition['fiber']} g estimated"},
        {"label": "Ingredient variety", "score": min(100, 40 + ingredient_count * 12), "detail": f"{ingredient_count} ingredients identified"},
        {"label": "Macro estimate", "score": max(0, min(100, round(100 - abs(macro_energy - calories) / calories * 100))), "detail": "Macro energy compared with estimated calories"},
    ]


def _freshness(cues: list[str]) -> dict[str, Any]:
    text = " ".join(cues).lower()
    unsafe = ("mold", "mould", "slimy", "rotten", "fuzzy", "black spots")
    aging = ("soft", "brown", "wilting", "wrinkled", "bruised", "dry edges", "discolor")
    if any(t in text for t in unsafe):
        status, label, guidance = "unsafe", "Visible spoilage cues", "The image shows cues that can indicate spoilage. Do not taste it; discard it if in doubt."
    elif any(t in text for t in aging):
        status, label, guidance = "consume_soon", "Signs of aging", "Some visible cues suggest it is past its best. Check smell and texture and use it soon, or discard it if anything seems off."
    else:
        status, label, guidance = "fresh", "No visible spoilage cues", "Nothing obviously wrong is visible, but a photo cannot confirm freshness or safety. Check storage time, smell and texture."
    return {
        "status": status, "label": label, "guidance": guidance, "confidence": 40,
        "storageTip": "Refrigerate perishable food promptly and keep raw and ready-to-eat items apart.",
        "analyzedAt": datetime.now(timezone.utc).isoformat(),
    }


def analyze_media(
    llm: LLMClient,
    kind: str,
    *,
    images: list[dict[str, Any]] | None = None,
    description: str = "",
    diet: str = "none",
    allergies: list[str] | None = None,
    goal: str | None = None,
    file_name: str | None = None,
) -> dict[str, Any]:
    """Run analysis and return an object shaped like the app's ``FoodScan`` plus an ``analysis`` block."""
    if kind not in ("image", "video", "text", "audio"):
        raise AIError("invalid_input", "Unsupported input type.")
    description = (description or "").strip()
    allergies = _clean_list(allergies)
    media: list[MediaItem] = []
    if kind in ("image", "video"):
        limit = MAX_VIDEO_FRAMES if kind == "video" else MAX_IMAGES
        media = parse_images(images, max_items=limit, label="frame" if kind == "video" else "photo")
    elif len(description) < 3:
        raise AIError("invalid_input", "Describe the meal in a few words so it can be analyzed.")
    if len(description) > 1000:
        raise AIError("invalid_input", "The description is too long. Please keep it under 1000 characters.")

    content: list[dict[str, Any]] = []
    if media:
        content += image_blocks(media, caption_prefix="Video frame" if kind == "video" else "Photo")
    intro = {
        "image": "Analyze the food in the photo(s) above.",
        "video": f"Analyze the {len(media)} sampled video frames above. They are snapshots in time order, not the full video, and there is no audio.",
        "text": "Analyze the meal described by the user.",
        "audio": "Analyze the meal described in this transcribed voice question.",
    }[kind]
    parts = [intro, _context_lines(diet, allergies, goal)]
    if description:
        parts.append(_data("user_description", description))
    content.append({"type": "text", "text": "\n".join(parts)})

    raw = llm.complete_json(
        system=prompts.MEDIA,
        content=content,
        tool_name="food_analysis",
        tool_description="Return the structured food analysis.",
        schema=schemas.MEDIA_ANALYSIS,
        max_tokens=5000,
    )
    analysis = v.media_analysis(raw, is_video=kind == "video")

    visual_only = kind in ("image", "video")
    nutrition_parts: list[dict[str, Any]] = []
    for item in analysis["items"]:
        names = [i["name"] for i in item["ingredients"]]
        label, certainty, note = safety.reconcile_diet(item["dietLabel"], names + [item["name"]], visual_only=visual_only)
        item["dietLabel"], item["dietCertainty"] = label, certainty
        item["dietBasis"] = " ".join(filter(None, [item["dietBasis"], note]))[:400] or None
        item["fitsYourDiet"] = safety.fits_diet(label, diet, names)
        # Allergy alerts come from the user's own list, matched deterministically against what was identified.
        hits = safety.allergen_hits(allergies, names + [item["name"]])
        observed = {i["name"].lower() for i in item["ingredients"] if i["evidence"] == "observed"}
        item["allergyAlerts"] = [
            {"allergen": a, "ingredient": ing, "basis": "visible in the food" if ing.lower() in observed else "inferred or typical for this dish"}
            for a, _term, ing in hits
        ]
        if item["nutrition"]:
            nutrition_parts.append(item["nutrition"])

    analysis["nutritionAvailable"] = bool(nutrition_parts)
    analysis["totals"] = v.sum_nutrition(nutrition_parts) if nutrition_parts else None
    analysis["nutritionBasis"] = "ai_estimate"
    analysis["method"] = {"image": "vision", "video": "frame_sampling", "text": "text", "audio": "text"}[kind]
    analysis["framesAnalyzed"] = len(media)
    analysis["frameTimestamps"] = [m.timestamp for m in media if m.timestamp is not None] if kind == "video" else []
    analysis["modelCaveats"] = [
        "Image-based estimates are approximate; portions and hidden ingredients (oil, sugar, sauces) can change the numbers a lot.",
        ALLERGY_FOOTER,
    ] + (["Analysis used sampled frames only, without audio or the moments between frames."] if kind == "video" else [])
    analysis["allergyAlertsPresent"] = any(item["allergyAlerts"] for item in analysis["items"])

    return _to_food_scan(analysis, kind, file_name)


def _to_food_scan(analysis: dict[str, Any], kind: str, file_name: str | None) -> dict[str, Any]:
    items = analysis["items"]
    if items:
        dish = items[0]["name"] if len(items) == 1 else f"{items[0]['name']} + {len(items) - 1} more"
    else:
        dish = "Unidentified meal"
    seen: set[str] = set()
    ingredients: list[str] = []
    for item in items:
        for ing in sorted(item["ingredients"], key=lambda i: i["evidence"] == "inferred"):
            if ing["name"].lower() not in seen:
                seen.add(ing["name"].lower())
                ingredients.append(ing["name"])
    totals = analysis["totals"]
    nutrition = {
        "calories": totals["calories"] if totals else 0,
        "protein": totals["protein"] if totals else 0.0,
        "carbs": totals["carbs"] if totals else 0.0,
        "fat": totals["fat"] if totals else 0.0,
        "fiber": totals["fiber"] if totals else 0.0,
        "micronutrients": v.str_list([m for item in items for m in item["micronutrients"]], max_items=8, limit=40),
    }
    breakdown = _health_breakdown(nutrition, len(ingredients)) if totals else []
    health = round(sum(b["score"] for b in breakdown) / len(breakdown)) if breakdown else 0
    cues = [c for item in items for c in item["visibleCues"]]
    return {
        "id": str(uuid4()),
        "dishName": dish[:120],
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "source": "audio" if kind == "audio" else kind,
        "fileName": file_name,
        "ingredients": ingredients[:25],
        "confidence": round(sum(i["confidence"] for i in items) / len(items)) if items else 0,
        "nutrition": nutrition,
        "healthScore": health,
        "healthBreakdown": breakdown,
        "freshness": _freshness(cues),
        "analysis": analysis,
    }


# --------------------------------------------------------- ingredient photos
def identify_ingredients(
    llm: LLMClient, *, images: list[dict[str, Any]] | None, note: str = "",
) -> dict[str, Any]:
    media = parse_images(images, max_items=MAX_IMAGES, label="photo")
    text = "List the ingredients visible in the photo(s) above."
    if note.strip():
        text += "\n" + _data("user_note", note[:300])
    raw = llm.complete_json(
        system=prompts.INGREDIENTS,
        content=image_blocks(media, caption_prefix="Photo") + [{"type": "text", "text": text}],
        tool_name="ingredient_list",
        tool_description="Return the identified ingredients.",
        schema=schemas.INGREDIENT_ID,
        max_tokens=2500,
    )
    result = v.ingredient_identification(raw)
    result["photosAnalyzed"] = len(media)
    return result


# ------------------------------------------------------------------ recipes
_STAPLES = {"salt", "water", "oil", "cooking oil", "pepper", "black pepper", "sugar"}


def _stem(word: str) -> str:
    if len(word) <= 3:
        return word
    if word.endswith("ies"):
        return word[:-3] + "y"
    if word.endswith("oes"):
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _norm(text: str) -> str:
    text = re.sub(r"\([^)]*\)", " ", text.lower())
    return " ".join(_stem(w) for w in re.findall(r"[a-z]+", text))


def _matches(have: str, needed: str) -> bool:
    """Does an ingredient the user listed cover a recipe ingredient?

    Deliberately conservative: equal, or one is the head noun of the other
    ("onion" covers "red onion"). "rice" does not cover "rice flour", and
    "chicken" does not cover "chicken breast" - an over-reported shortfall is
    safer than claiming the user already has something they don't.
    """
    a, b = _norm(have), _norm(needed)
    if not a or not b:
        return False
    return a == b or b.endswith(" " + a) or a.endswith(" " + b)


def _screen_recipe(recipe: dict[str, Any], *, diet: str, allergies: list[str], exclude: list[str], have: list[str], assume_staples: bool) -> tuple[dict[str, Any] | None, str | None]:
    """Remove conflicting optional ingredients; reject the recipe on a conflicting required one."""
    kept = []
    for ing in recipe["ingredients"]:
        name = ing["name"]
        problem = None
        hits = safety.allergen_hits(allergies, [name])
        if hits:
            problem = f"{hits[0][1]} conflicts with the allergy '{hits[0][0]}'"
        elif safety.diet_conflict(diet, [name]):
            problem = safety.diet_conflict(diet, [name])
        elif any(_matches(term, name) for term in exclude):
            problem = f"{name} was excluded"
        if problem:
            if ing["optional"] and not hits:
                continue
            return None, f"{recipe['name']}: {problem}"
        kept.append(ing)
    recipe["ingredients"] = kept
    names = [i["name"] for i in kept if not i["optional"]]
    label, _certainty, _note = safety.reconcile_diet(recipe["dietLabel"], names, visual_only=False, ingredient_list_provided=True)
    recipe["dietLabel"] = label
    missing, assumed = [], []
    for ing in kept:
        owned = any(_matches(h, ing["name"]) for h in have)
        ing["have"] = owned
        if owned:
            continue
        if assume_staples and (ing["pantryStaple"] or _norm(ing["name"]) in _STAPLES):
            ing["assumedStaple"] = True
            assumed.append(ing["name"])
        elif not ing["optional"]:
            missing.append(ing["name"])
        else:
            ing["optionalMissing"] = True
    recipe["missingIngredients"] = missing
    recipe["assumedPantryStaples"] = assumed
    recipe["availableIngredients"] = [i["name"] for i in kept if i["have"]]
    recipe["usesOnlyWhatYouHave"] = not missing
    recipe["nutritionBasis"] = "ai_estimate"
    return recipe, None


def generate_recipes(
    llm: LLMClient,
    *,
    ingredients: list[str] | None = None,
    dish: str = "",
    diet: str = "none",
    allergies: list[str] | None = None,
    exclude: list[str] | None = None,
    preferences: dict[str, Any] | None = None,
    previous_recipe: dict[str, Any] | None = None,
    follow_up: str = "",
    count: int = 3,
    assume_pantry_staples: bool = True,
) -> dict[str, Any]:
    have = _clean_list(ingredients, limit=60)
    allergies = _clean_list(allergies)
    exclude = _clean_list(exclude)
    dish = " ".join((dish or "").split())[:120]
    follow_up = " ".join((follow_up or "").split())[:300]
    prefs = {k: val for k, val in (preferences or {}).items() if val not in (None, "", [])}
    if not have and not dish:
        raise AIError("invalid_input", "Add the ingredients you have, or name a dish, to get recipes.")
    if follow_up and not previous_recipe:
        raise AIError("invalid_input", "Pick a recipe first, then ask for a change.")
    count = 1 if (previous_recipe or follow_up) else max(1, min(count, 4 if dish else 4))

    request_lines = [_context_lines(diet, allergies)]
    request_lines.append("Ingredients the user has: " + (", ".join(have) if have else "not specified"))
    if exclude:
        request_lines.append("Ingredients the user does NOT have or wants to avoid: " + ", ".join(exclude))
    request_lines.append("Assume basic pantry staples (salt, water, cooking oil, common spices): " + ("yes" if assume_pantry_staples else "no"))
    for key in ("cuisine", "spiceLevel", "maxMinutes", "difficulty", "servings", "variation"):
        if key in prefs:
            request_lines.append(f"{key}: {prefs[key]}")
    if prefs.get("equipment"):
        request_lines.append("Equipment available: " + ", ".join(map(str, prefs["equipment"])))
    if dish:
        request_lines.append(_data("dish_idea", dish))
    if previous_recipe:
        import json
        request_lines.append(_data("previous_recipe_json", json.dumps({k: previous_recipe.get(k) for k in ("name", "ingredients", "steps", "servings")})[:6000]))
        request_lines.append(_data("requested_change", follow_up or "Provide an improved alternative."))
    request_lines.append(f"Return {count} recipe option(s).")
    base_text = "\n".join(request_lines)

    removed: list[str] = []
    feedback = ""
    accepted: list[dict[str, Any]] = []
    notes = clarifying = None
    for _attempt in range(2):
        raw = llm.complete_json(
            system=prompts.RECIPES,
            content=[{"type": "text", "text": base_text + feedback}],
            tool_name="recipe_options",
            tool_description="Return the recipe options.",
            schema=schemas.RECIPES,
            max_tokens=6000,
        )
        parsed = v.recipes(raw)
        notes, clarifying = parsed["notes"], parsed["clarifyingQuestion"]
        for recipe in parsed["recipes"]:
            screened, reason = _screen_recipe(recipe, diet=diet, allergies=allergies, exclude=exclude, have=have, assume_staples=assume_pantry_staples)
            if screened:
                accepted.append(screened)
            elif reason:
                removed.append(reason)
        if accepted or clarifying:
            break
        feedback = "\n\nYour previous attempt was rejected: " + "; ".join(removed[-4:]) + ". Write new recipes that avoid all of these."
    if not accepted and not clarifying:
        raise AIError("bad_response", "Couldn't build a recipe that respects your allergies, diet and ingredient limits. Try adding a few more ingredients or relaxing a preference.")
    return {
        "recipes": accepted,
        "notes": notes,
        "clarifyingQuestion": clarifying,
        "removedForSafety": removed,
        "appliedConstraints": {"diet": safety.normalize_diet(diet), "allergies": allergies, "excluded": exclude},
        "disclaimer": "Nutrition values are AI estimates. " + ALLERGY_FOOTER,
    }


# -------------------------------------------------------------- suggestions
def suggest_foods(
    llm: LLMClient,
    *,
    goal: str = "",
    diet: str = "none",
    allergies: list[str] | None = None,
    ingredients: list[str] | None = None,
    context: str = "",
    count: int = 5,
) -> dict[str, Any]:
    allergies = _clean_list(allergies)
    have = _clean_list(ingredients, limit=40)
    context = " ".join((context or "").split())[:300]
    goal = " ".join((goal or "").split())[:120]
    lines = [_context_lines(diet, allergies, goal or None)]
    if have:
        lines.append("Ingredients available: " + ", ".join(have))
    if context:
        lines.append(_data("user_request", context))
    lines.append(f"Suggest {max(1, min(count, 8))} ideas.")
    raw = llm.complete_json(
        system=prompts.SUGGESTIONS,
        content=[{"type": "text", "text": "\n".join(lines)}],
        tool_name="food_ideas",
        tool_description="Return the suggested ideas.",
        schema=schemas.SUGGESTIONS,
        max_tokens=3000,
    )
    result = v.suggestions(raw)
    kept, dropped = [], 0
    for idea in result["ideas"]:
        names = idea["ingredients"] + [idea["name"]]
        if safety.allergen_hits(allergies, names) or safety.diet_conflict(diet, names):
            dropped += 1
            continue
        label, _c, _n = safety.reconcile_diet(idea["dietLabel"], idea["ingredients"], visual_only=False)
        idea["dietLabel"] = label
        kept.append(idea)
    if not kept:
        raise AIError("bad_response", "Couldn't find ideas that fit your allergies and diet. Try a different goal or request.")
    result["ideas"] = kept
    result["removedForSafety"] = dropped
    result["disclaimer"] = "General food ideas, not medical advice. " + ALLERGY_FOOTER
    return result
