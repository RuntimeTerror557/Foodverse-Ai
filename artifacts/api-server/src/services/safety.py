"""Deterministic guards that sit *behind* the model.

The model is asked to respect allergies and dietary rules, but its output is
never trusted for safety-relevant claims: every recipe and classification is
re-checked here against ingredient keywords. The guards only ever make the
answer more conservative (drop a recipe, downgrade a label, add a warning);
they never upgrade a label.
"""
from __future__ import annotations

import re
from typing import Iterable

DIET_LABELS = ("vegan", "vegetarian", "eggetarian", "non_vegetarian", "uncertain")
DIET_CONVENTIONS = ("none", "vegetarian", "eggetarian", "vegan", "jain")

FLESH_TERMS = (
    "chicken", "mutton", "lamb", "goat", "beef", "pork", "bacon", "ham", "sausage", "salami", "turkey", "duck",
    "meat", "keema", "mince", "steak", "veal", "venison", "fish", "salmon", "tuna", "cod", "sardine", "mackerel",
    "hilsa", "rohu", "pomfret", "anchovy", "anchovies", "shrimp", "prawn", "crab", "lobster", "squid", "calamari",
    "octopus", "clam", "mussel", "oyster", "seafood", "bone broth", "chicken stock", "beef stock", "fish sauce",
    "oyster sauce", "worcestershire", "shrimp paste", "gelatin", "gelatine", "lard", "tallow", "suet", "rennet",
)
EGG_TERMS = ("egg", "eggs", "mayonnaise", "mayo", "albumen", "omelette", "omelet", "meringue", "aioli")
DAIRY_TERMS = (
    "milk", "cheese", "paneer", "ghee", "butter", "curd", "yogurt", "yoghurt", "dahi", "cream", "whey", "casein",
    "khoa", "mawa", "lassi", "buttermilk", "chaas", "kefir", "ice cream", "condensed milk", "cottage cheese",
    "parmesan", "mozzarella", "cheddar", "feta", "ricotta",
)
HONEY_TERMS = ("honey",)
JAIN_AVOID = (
    "onion", "garlic", "potato", "carrot", "radish", "beetroot", "beet", "turnip", "ginger", "sweet potato",
    "yam", "mushroom", "shallot", "spring onion", "leek", "arbi", "colocasia", "honey",
)

ALLERGEN_TERMS: dict[str, tuple[str, ...]] = {
    "milk": DAIRY_TERMS,
    "dairy": DAIRY_TERMS,
    "egg": EGG_TERMS,
    "peanut": ("peanut", "groundnut", "monkfruit nut"),
    "tree nut": ("almond", "cashew", "walnut", "pistachio", "hazelnut", "pecan", "macadamia", "brazil nut", "pine nut", "praline", "marzipan"),
    "wheat": ("wheat", "flour", "atta", "maida", "bread", "pasta", "semolina", "rava", "suji", "couscous", "seitan", "bulgur", "noodle", "chapati", "roti", "naan", "paratha"),
    "gluten": ("wheat", "flour", "atta", "maida", "bread", "pasta", "semolina", "rava", "suji", "couscous", "seitan", "bulgur", "barley", "rye", "noodle", "chapati", "roti", "naan", "paratha", "soy sauce"),
    "soy": ("soy", "soya", "tofu", "edamame", "tempeh", "miso", "soy sauce"),
    "fish": ("fish", "salmon", "tuna", "cod", "sardine", "mackerel", "anchovy", "anchovies", "fish sauce", "hilsa", "rohu", "pomfret"),
    "shellfish": ("shrimp", "prawn", "crab", "lobster", "clam", "mussel", "oyster", "scallop", "crayfish"),
    "sesame": ("sesame", "tahini", "til ", "gingelly"),
    "mustard": ("mustard", "sarson", "rai "),
    "celery": ("celery", "celeriac"),
    "lupin": ("lupin", "lupine"),
}
_ALLERGY_ALIASES = {
    "milk allergy": "milk", "lactose": "milk", "egg allergy": "egg", "eggs": "egg", "peanuts": "peanut",
    "nuts": "tree nut", "nut": "tree nut", "tree nuts": "tree nut", "treenut": "tree nut", "almond": "tree nut",
    "cashew": "tree nut", "walnut": "tree nut", "gluten-free": "gluten", "celiac": "gluten", "coeliac": "gluten",
    "soya": "soy", "soybean": "soy", "shellfish allergy": "shellfish", "seafood": "shellfish",
    "sesame seeds": "sesame",
}


def _pattern(term: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![a-z]){re.escape(term.strip())}(?:s|es)?(?![a-z])", re.IGNORECASE)


def contains_term(text: str, terms: Iterable[str]) -> str | None:
    """Return the first term found in ``text`` as a whole word (plural-tolerant)."""
    lowered = text.lower()
    for term in terms:
        if _pattern(term).search(lowered):
            return term.strip()
    return None


def normalize_diet(value: str | None) -> str:
    cleaned = (value or "none").strip().lower().replace("-", "_").replace(" ", "_")
    if cleaned in ("non_vegetarian", "non_veg", "nonveg", "omnivore", "any", ""):
        return "none"
    return cleaned if cleaned in DIET_CONVENTIONS else "none"


def allergen_terms_for(allergy: str) -> tuple[str, ...]:
    key = allergy.strip().lower()
    key = _ALLERGY_ALIASES.get(key, key)
    if key in ALLERGEN_TERMS:
        return ALLERGEN_TERMS[key]
    # Unknown allergy ("coconut", "kiwi"): match the user's own words literally.
    return (key,) if key else ()


def allergen_hits(allergies: Iterable[str], ingredient_texts: Iterable[str]) -> list[tuple[str, str, str]]:
    """List of ``(allergy, matched_term, ingredient)`` for every conflict found."""
    hits: list[tuple[str, str, str]] = []
    texts = [t for t in ingredient_texts if t]
    for allergy in allergies:
        terms = allergen_terms_for(allergy)
        for text in texts:
            term = contains_term(text, terms)
            if term:
                hits.append((allergy, term, text))
    return hits


def minimum_diet_from_ingredients(ingredients: Iterable[str]) -> tuple[str, str | None]:
    """Strictest label the ingredient *names* force, plus the keyword responsible."""
    joined = [i for i in ingredients if i]
    for text in joined:
        term = contains_term(text, FLESH_TERMS)
        if term:
            return "non_vegetarian", term
    for text in joined:
        term = contains_term(text, EGG_TERMS)
        if term:
            return "eggetarian", term
    for text in joined:
        term = contains_term(text, DAIRY_TERMS + HONEY_TERMS)
        if term:
            return "vegetarian", term
    return "vegan", None


_ORDER = {"vegan": 0, "vegetarian": 1, "eggetarian": 2, "non_vegetarian": 3}


def reconcile_diet(label: str, ingredients: Iterable[str], *, visual_only: bool, ingredient_list_provided: bool = False) -> tuple[str, str, str | None]:
    """Combine the model's label with keyword evidence.

    Returns ``(label, certainty, note)``. ``certainty`` is ``confirmed`` (flesh
    keyword present, or a user-supplied ingredient list agrees with the label),
    ``likely`` (consistent with what is visible/named but hidden ingredients
    such as ghee, stock or gelatin cannot be ruled out) or ``uncertain``.
    """
    label = label if label in DIET_LABELS else "uncertain"
    forced, term = minimum_diet_from_ingredients(ingredients)
    note: str | None = None
    if label == "uncertain":
        if forced == "non_vegetarian":
            return "non_vegetarian", "confirmed", f"Contains {term}."
        return "uncertain", "uncertain", "Not enough ingredient information to classify this reliably. Share the ingredient list for a firmer answer."
    if _ORDER[forced] > _ORDER[label]:
        note = f"Adjusted because the ingredients include {term}."
        label = forced
    if label == "non_vegetarian" and forced == "non_vegetarian":
        return label, "confirmed", note or f"Contains {term}."
    if ingredient_list_provided and not visual_only and note is None:
        return label, "confirmed", None
    return label, "likely", note or "Based on the ingredients identified; hidden ingredients (ghee, stock, gelatin, sauces) can't be ruled out."


def fits_diet(label: str, convention: str, ingredients: Iterable[str]) -> bool | None:
    """Does a classified food suit the user's diet? ``None`` means can't tell."""
    convention = normalize_diet(convention)
    if convention == "none":
        return True
    if label == "uncertain":
        return None
    if convention == "vegan":
        return label == "vegan"
    if convention == "vegetarian":
        return label in ("vegan", "vegetarian")
    if convention == "eggetarian":
        return label in ("vegan", "vegetarian", "eggetarian")
    if convention == "jain":
        if label not in ("vegan", "vegetarian"):
            return False
        return contains_term(" ; ".join(ingredients), JAIN_AVOID) is None
    return True


def diet_conflict(convention: str, ingredients: Iterable[str]) -> str | None:
    """Reason a list of ingredients breaks the user's diet, else ``None``."""
    convention = normalize_diet(convention)
    if convention == "none":
        return None
    forced, term = minimum_diet_from_ingredients(ingredients)
    if convention == "vegan" and forced != "vegan":
        return f"{term} is not vegan"
    if convention == "vegetarian" and forced in ("eggetarian", "non_vegetarian"):
        return f"{term} is not vegetarian"
    if convention == "eggetarian" and forced == "non_vegetarian":
        return f"{term} is not eggetarian"
    if convention == "jain":
        if forced in ("eggetarian", "non_vegetarian"):
            return f"{term} is not allowed in a Jain diet"
        found = contains_term(" ; ".join(ingredients), JAIN_AVOID)
        if found:
            return f"{found} is typically avoided in a Jain diet"
    return None
