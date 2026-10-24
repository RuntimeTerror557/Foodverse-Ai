"""Optional reference lookup in USDA FoodData Central.

Enabled only when ``USDA_API_KEY`` is set. It is used to attach a verifiable
per-100 g reference next to the model's own estimate; it never replaces the
estimate, and any failure simply means "no reference available".
"""
from __future__ import annotations

import json
import logging
import os
import urllib.parse
import urllib.request
from typing import Any, Callable

logger = logging.getLogger("food-verse.nutrition-db")

SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"
# FoodData Central nutrient numbers
_NUTRIENTS = {"208": "calories", "203": "protein", "204": "fat", "205": "carbs", "291": "fiber", "269": "sugar", "307": "sodiumMg"}

HttpGet = Callable[[str, float], bytes]


def _urllib_get(url: str, timeout: float) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 - fixed https host
        return response.read()


class UsdaLookup:
    def __init__(self, api_key: str, http_get: HttpGet = _urllib_get, timeout: float = 8.0) -> None:
        self._key = api_key
        self._get = http_get
        self._timeout = timeout
        self._cache: dict[str, dict[str, Any] | None] = {}

    def __call__(self, name: str) -> dict[str, Any] | None:
        key = name.strip().lower()
        if not key:
            return None
        if key in self._cache:
            return self._cache[key]
        result = self._fetch(key)
        self._cache[key] = result
        return result

    def _fetch(self, name: str) -> dict[str, Any] | None:
        query = urllib.parse.urlencode({
            "query": name, "pageSize": 3, "dataType": "Foundation,SR Legacy", "api_key": self._key,
        })
        try:
            data = json.loads(self._get(f"{SEARCH_URL}?{query}", self._timeout))
        except Exception:  # network, HTTP or JSON failure: reference is optional
            logger.warning("USDA lookup failed for %r", name)
            return None
        foods = data.get("foods") if isinstance(data, dict) else None
        if not foods:
            return None
        food = foods[0]
        per100: dict[str, float] = {}
        for nutrient in food.get("foodNutrients", []):
            field = _NUTRIENTS.get(str(nutrient.get("nutrientNumber")))
            value = nutrient.get("value")
            if field and isinstance(value, (int, float)) and field not in per100:
                per100[field] = round(float(value), 1)
        if "calories" not in per100:
            return None
        return {
            "source": "USDA FoodData Central",
            "fdcId": food.get("fdcId"),
            "matchedFood": str(food.get("description", ""))[:120],
            "dataType": food.get("dataType"),
            "per100g": per100,
        }


def get_nutrition_lookup() -> Callable[[str], dict[str, Any] | None] | None:
    key = os.environ.get("USDA_API_KEY", "").strip()
    return UsdaLookup(key) if key else None
