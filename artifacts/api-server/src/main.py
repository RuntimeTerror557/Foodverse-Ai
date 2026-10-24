from __future__ import annotations

import base64
import hmac
import logging
import os
import secrets
import time
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal
from uuid import uuid4
from zoneinfo import ZoneInfo

import psycopg
from fastapi import APIRouter, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from services import food_ai
from services.analysis import (
    analyze_food,
    analyze_hygiene,
    estimate_freshness,
    make_chef_guide,
)
from services.llm import AIError, ai_settings, get_llm
from services.nutrition_db import get_nutrition_lookup

logger = logging.getLogger("food-verse.api")
LOCAL_ZONE = ZoneInfo("Asia/Kolkata")
DATABASE_URL = os.environ.get("DATABASE_URL")
SESSION_SECRET = os.environ.get("SESSION_SECRET", "")
if not SESSION_SECRET:
    raise RuntimeError("SESSION_SECRET must be configured.")
_SEEDED_SESSIONS: set[str] = set()

Goal = Literal["balanced", "keto", "vegan", "muscle_gain", "low_carb", "weight_loss"]
Source = Literal["image", "video", "audio", "text"]
FreshnessStatus = Literal["fresh", "consume_soon", "unsafe"]
RiskLevel = Literal["low", "moderate", "high"]


class Nutrition(BaseModel):
    calories: int
    protein: float
    carbs: float
    fat: float
    fiber: float
    micronutrients: list[str]


class FreshnessResult(BaseModel):
    status: FreshnessStatus
    label: str
    guidance: str
    storageTip: str
    confidence: int
    analyzedAt: datetime


class HealthScoreSignal(BaseModel):
    label: str
    score: int
    detail: str


class FoodScan(BaseModel):
    id: str
    dishName: str
    createdAt: datetime
    source: Source
    fileName: str | None
    ingredients: list[str]
    confidence: int
    nutrition: Nutrition
    healthScore: int
    healthBreakdown: list[HealthScoreSignal]
    freshness: FreshnessResult
    # Present for scans produced by the AI pipeline (items, diet labels, caveats, ...).
    analysis: dict[str, Any] | None = None


class FoodScanInput(BaseModel):
    source: Source
    fileName: str | None = None
    description: str = Field(max_length=1000)


class FreshnessInput(BaseModel):
    food: str = Field(min_length=1, max_length=120)
    fileName: str | None = None
    notes: str = Field(default="", max_length=1000)


class HygieneAudit(BaseModel):
    id: str
    kitchenName: str
    createdAt: datetime
    videoName: str | None
    gloveCompliance: int
    hairnetCompliance: int
    cleanlinessScore: int
    contaminationRisk: RiskLevel
    safetyScore: int
    alerts: list[str]


class HygieneAuditInput(BaseModel):
    kitchenName: str = Field(min_length=1, max_length=120)
    videoName: str | None = None
    mode: Literal["sample", "upload"]


class NutritionProfile(BaseModel):
    calorieTarget: int = Field(ge=800, le=6000)
    goal: Goal
    allergies: list[str]
    dietaryNotes: str


class NutritionProfileInput(NutritionProfile):
    dietaryNotes: str = Field(max_length=500)


class PlannedMeal(BaseModel):
    id: str
    name: str
    slot: Literal["breakfast", "lunch", "dinner"]
    calories: int
    protein: float
    carbs: float
    fat: float
    completed: bool
    tags: list[str]


class MealDay(BaseModel):
    date: date
    label: str
    meals: list[PlannedMeal]


class GroceryItem(BaseModel):
    id: str
    name: str
    quantity: str
    checked: bool
    category: str


class MealPlan(BaseModel):
    weekOf: date
    days: list[MealDay]
    groceryList: list[GroceryItem]


class MealPlanInput(BaseModel):
    weekOf: date | None


class MealCompletionInput(BaseModel):
    completed: bool


class GroceryItemInput(BaseModel):
    checked: bool


class ChefGuideInput(BaseModel):
    dish: str = Field(min_length=1, max_length=120)
    ingredients: list[str]
    allergies: list[str]


class ChefGuide(BaseModel):
    dish: str
    prepMinutes: int
    cookMinutes: int
    servings: int
    steps: list[str]
    substitutions: list[str]
    allergyWarnings: list[str]
    voiceScript: str


class RecentActivity(BaseModel):
    id: str
    title: str
    subtitle: str
    kind: Literal["scan", "freshness", "audit"]
    createdAt: datetime
    score: int


class DashboardSummary(BaseModel):
    calorieTarget: int
    caloriesConsumed: int
    proteinConsumed: float
    carbsConsumed: float
    fatConsumed: float
    healthScore: int
    mealsLogged: int
    mealsPlanned: int
    weeklyCalories: list[int]
    recentActivity: list[RecentActivity]
    nextMeal: PlannedMeal


class ImagePayload(BaseModel):
    data: str = Field(max_length=8_000_000, description="Base64 image bytes or a data: URL")
    mimeType: str | None = Field(default=None, max_length=60)
    timestamp: float | None = Field(default=None, ge=0, le=36000, description="Video time in seconds (frames only)")


class AnalyzeMediaInput(BaseModel):
    kind: Literal["image", "video", "text", "audio"]
    images: list[ImagePayload] = Field(default_factory=list, max_length=8)
    description: str = Field(default="", max_length=1000)
    fileName: str | None = Field(default=None, max_length=200)
    dietConvention: str = Field(default="none", max_length=30)
    goal: str | None = Field(default=None, max_length=120)
    allergies: list[str] = Field(default_factory=list, max_length=20)


class FoodInfoInput(BaseModel):
    query: str = Field(min_length=1, max_length=400)
    dietConvention: str = Field(default="none", max_length=30)
    allergies: list[str] = Field(default_factory=list, max_length=20)
    ingredientList: list[str] = Field(default_factory=list, max_length=40)


class IdentifyIngredientsInput(BaseModel):
    images: list[ImagePayload] = Field(default_factory=list, max_length=4)
    note: str = Field(default="", max_length=300)


class RecipePreferences(BaseModel):
    cuisine: str | None = Field(default=None, max_length=60)
    spiceLevel: Literal["mild", "medium", "hot"] | None = None
    maxMinutes: int | None = Field(default=None, ge=5, le=480)
    difficulty: Literal["easy", "medium", "hard"] | None = None
    servings: int | None = Field(default=None, ge=1, le=20)
    equipment: list[str] = Field(default_factory=list, max_length=15)
    variation: str | None = Field(default=None, max_length=60)


class RecipeRequestInput(BaseModel):
    ingredients: list[str] = Field(default_factory=list, max_length=60)
    dish: str = Field(default="", max_length=120)
    dietConvention: str = Field(default="none", max_length=30)
    allergies: list[str] = Field(default_factory=list, max_length=20)
    excludeIngredients: list[str] = Field(default_factory=list, max_length=30)
    preferences: RecipePreferences = Field(default_factory=RecipePreferences)
    previousRecipe: dict[str, Any] | None = None
    followUp: str = Field(default="", max_length=300)
    assumePantryStaples: bool = True


class SuggestionsInput(BaseModel):
    goal: str = Field(default="", max_length=120)
    dietConvention: str = Field(default="none", max_length=30)
    allergies: list[str] = Field(default_factory=list, max_length=20)
    ingredients: list[str] = Field(default_factory=list, max_length=40)
    context: str = Field(default="", max_length=300)


def db_connect() -> psycopg.Connection[Any]:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is required for Food Verse AI persistence.")
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def local_today() -> date:
    return datetime.now(LOCAL_ZONE).date()


def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def default_profile() -> dict[str, Any]:
    return {
        "calorieTarget": 2000,
        "goal": "balanced",
        "allergies": [],
        "dietaryNotes": "",
    }


MEAL_OPTIONS: dict[str, list[dict[str, Any]]] = {
    "balanced": [
        {"name": "Berry chia breakfast bowl", "calories": 390, "protein": 16, "carbs": 55, "fat": 12, "tags": ["High fiber", "Balanced"]},
        {"name": "Chickpea quinoa salad", "calories": 520, "protein": 22, "carbs": 72, "fat": 16, "tags": ["Plant-forward", "High fiber"]},
        {"name": "Herb-roasted chicken and vegetables", "calories": 640, "protein": 44, "carbs": 50, "fat": 28, "tags": ["Lean protein", "Balanced"]},
    ],
    "vegan": [
        {"name": "Coconut chia breakfast bowl", "calories": 380, "protein": 13, "carbs": 42, "fat": 18, "tags": ["Vegan", "High fiber"]},
        {"name": "Lentil quinoa bowl", "calories": 540, "protein": 25, "carbs": 76, "fat": 14, "tags": ["Vegan", "Iron-rich"]},
        {"name": "Roasted chickpea and vegetable plate", "calories": 610, "protein": 24, "carbs": 78, "fat": 18, "tags": ["Vegan", "Plant protein"]},
    ],
    "keto": [
        {"name": "Avocado herb breakfast plate", "calories": 430, "protein": 22, "carbs": 18, "fat": 32, "tags": ["Keto", "Low carb"]},
        {"name": "Lemon chicken greens bowl", "calories": 560, "protein": 43, "carbs": 20, "fat": 38, "tags": ["Keto", "Lean protein"]},
        {"name": "Roasted salmon and cauliflower", "calories": 650, "protein": 42, "carbs": 18, "fat": 46, "tags": ["Keto", "Omega-3"]},
    ],
    "muscle_gain": [
        {"name": "Berry oat protein bowl", "calories": 540, "protein": 30, "carbs": 68, "fat": 16, "tags": ["Muscle gain", "High protein"]},
        {"name": "Chicken quinoa power bowl", "calories": 690, "protein": 48, "carbs": 70, "fat": 22, "tags": ["Muscle gain", "High protein"]},
        {"name": "Lentil and roasted chicken plate", "calories": 760, "protein": 52, "carbs": 68, "fat": 28, "tags": ["Muscle gain", "Recovery"]},
    ],
    "low_carb": [
        {"name": "Avocado and berry breakfast plate", "calories": 390, "protein": 18, "carbs": 30, "fat": 25, "tags": ["Low carb", "Fiber"]},
        {"name": "Grilled chicken garden bowl", "calories": 510, "protein": 42, "carbs": 24, "fat": 29, "tags": ["Low carb", "Lean protein"]},
        {"name": "Herbed salmon with greens", "calories": 610, "protein": 40, "carbs": 21, "fat": 42, "tags": ["Low carb", "Omega-3"]},
    ],
    "weight_loss": [
        {"name": "Warm berry chia bowl", "calories": 330, "protein": 14, "carbs": 39, "fat": 13, "tags": ["Goal-aligned", "High fiber"]},
        {"name": "Lentil garden salad", "calories": 440, "protein": 23, "carbs": 54, "fat": 14, "tags": ["Goal-aligned", "Plant protein"]},
        {"name": "Lemon chicken vegetable plate", "calories": 520, "protein": 42, "carbs": 32, "fat": 24, "tags": ["Goal-aligned", "Lean protein"]},
    ],
}

GROCERY_SEEDS = [
    ("Chia seeds", "1 small bag", "Pantry"),
    ("Seasonal berries", "2 cups", "Produce"),
    ("Quinoa", "1 cup dry", "Pantry"),
    ("Chickpeas", "2 cans", "Pantry"),
    ("Baby spinach", "1 large bag", "Produce"),
    ("Chicken breast", "450 g", "Protein"),
    ("Salmon fillets", "2 portions", "Protein"),
    ("Cauliflower", "1 head", "Produce"),
    ("Lentils", "1 cup dry", "Pantry"),
    ("Avocados", "3", "Produce"),
    ("Lemons", "3", "Produce"),
    ("Fresh herbs", "1 bunch", "Produce"),
]

ALLERGY_SYNONYMS: dict[str, tuple[str, ...]] = {
    "dairy": ("milk", "cheese", "yogurt", "butter", "cream"),
    "milk": ("dairy", "cheese", "yogurt", "butter", "cream"),
    "peanut": ("peanuts", "groundnut"),
    "peanuts": ("peanut", "groundnut"),
    "tree nut": ("almond", "cashew", "walnut", "pistachio", "hazelnut"),
    "nuts": ("almond", "cashew", "walnut", "pistachio", "hazelnut", "peanut"),
    "egg": ("eggs",),
    "eggs": ("egg",),
    "wheat": ("gluten", "bread", "pasta", "flour", "oat"),
    "gluten": ("wheat", "bread", "pasta", "flour", "oat"),
    "soy": ("soya", "tofu", "edamame"),
    "fish": ("salmon", "tuna", "cod"),
    "shellfish": ("shrimp", "prawn", "crab", "lobster"),
    "legume": ("lentil", "chickpea", "bean", "peanut"),
    "chicken": ("poultry",),
    "poultry": ("chicken",),
    "coconut": ("coconut",),
}


def allergy_tokens(allergies: list[str]) -> set[str]:
    tokens: set[str] = set()
    for allergy in allergies:
        normalized = allergy.lower().strip()
        if not normalized:
            continue
        tokens.add(normalized)
        for key, related in ALLERGY_SYNONYMS.items():
            if normalized == key or normalized in related or key in normalized:
                tokens.add(key)
                tokens.update(related)
    return tokens


def meal_option_for_profile(
    option: dict[str, Any], slot: str, allergies: list[str]
) -> dict[str, Any]:
    tokens = allergy_tokens(allergies)
    if not any(token in option["name"].lower() for token in tokens):
        return option
    safe_options = {
        "breakfast": {
            "name": "Warm berry chia bowl",
            "calories": 350,
            "protein": 14,
            "carbs": 42,
            "fat": 15,
        },
        "lunch": {
            "name": "Quinoa and roasted vegetable bowl",
            "calories": 500,
            "protein": 18,
            "carbs": 66,
            "fat": 16,
        },
        "dinner": {
            "name": "Lemon-herb vegetable and quinoa plate",
            "calories": 560,
            "protein": 20,
            "carbs": 72,
            "fat": 19,
        },
    }
    replacement = safe_options[slot].copy()
    replacement["tags"] = list(option["tags"]) + ["Adjusted for saved allergy"]
    return replacement


def plan_for_week(
    week_start: date, profile: dict[str, Any], seed_progress: bool = False
) -> dict[str, Any]:
    goal = profile.get("goal", "balanced")
    options = MEAL_OPTIONS.get(goal, MEAL_OPTIONS["balanced"])
    days: list[dict[str, Any]] = []
    today = local_today()
    labels = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    for day_index, label in enumerate(labels):
        day_date = week_start + timedelta(days=day_index)
        meals = []
        for slot_index, option in enumerate(options):
            slot = ["breakfast", "lunch", "dinner"][slot_index]
            safe_option = meal_option_for_profile(option, slot, profile.get("allergies", []))
            meals.append(
                {
                    "id": str(uuid4()),
                    "name": safe_option["name"],
                    "slot": slot,
                    "calories": safe_option["calories"],
                    "protein": safe_option["protein"],
                    "carbs": safe_option["carbs"],
                    "fat": safe_option["fat"],
                    "completed": bool(seed_progress and day_date == today and slot_index == 0),
                    "tags": safe_option["tags"],
                }
            )
        days.append({"date": day_date.isoformat(), "label": label, "meals": meals})

    tokens = allergy_tokens(profile.get("allergies", []))
    grocery_items = []
    for name, quantity, category in GROCERY_SEEDS:
        lowered = name.lower()
        if any(term in lowered for term in tokens):
            continue
        grocery_items.append(
            {
                "id": str(uuid4()),
                "name": name,
                "quantity": quantity,
                "checked": False,
                "category": category,
            }
        )

    return {
        "weekOf": week_start.isoformat(),
        "days": days,
        "groceryList": grocery_items,
    }


def seed_session_data(owner_id: str) -> None:
    now = datetime.now(timezone.utc)
    profile = default_profile()
    week_start = monday_of(local_today())
    sample_scans = [
        {
            "id": f"{owner_id}-demo-scan-lentil-bowl",
            "dishName": "Red lentil curry",
            "createdAt": (now - timedelta(hours=3)).isoformat(),
            "source": "image",
            "fileName": "lentil-curry.jpg",
            "ingredients": ["red lentils", "tomato", "ginger", "coconut milk", "spinach"],
            "confidence": 94,
            "nutrition": {
                "calories": 430,
                "protein": 22,
                "carbs": 57,
                "fat": 13,
                "fiber": 16,
                "micronutrients": ["Iron", "Folate", "Potassium", "Vitamin A"],
            },
            "healthScore": 94,
            "healthBreakdown": [
                {"label": "Protein", "score": 73, "detail": "22 g per serving"},
                {"label": "Fiber", "score": 100, "detail": "16 g per serving"},
                {"label": "Ingredient variety", "score": 100, "detail": "5 possible ingredients"},
                {"label": "Macro estimate", "score": 99, "detail": "Estimated macro energy compared with listed calories"},
            ],
            "freshness": estimate_freshness("red lentil curry"),
        },
        {
            "id": f"{owner_id}-demo-scan-grain-bowl",
            "dishName": "Garden grain bowl",
            "createdAt": (now - timedelta(days=1, hours=2)).isoformat(),
            "source": "text",
            "fileName": None,
            "ingredients": ["quinoa", "chickpeas", "baby spinach", "cucumber", "tahini"],
            "confidence": 90,
            "nutrition": {
                "calories": 485,
                "protein": 19,
                "carbs": 61,
                "fat": 18,
                "fiber": 12,
                "micronutrients": ["Iron", "Folate", "Magnesium", "Vitamin K"],
            },
            "healthScore": 91,
            "healthBreakdown": [
                {"label": "Protein", "score": 63, "detail": "19 g per serving"},
                {"label": "Fiber", "score": 86, "detail": "12 g per serving"},
                {"label": "Ingredient variety", "score": 100, "detail": "5 possible ingredients"},
                {"label": "Macro estimate", "score": 98, "detail": "Estimated macro energy compared with listed calories"},
            ],
            "freshness": estimate_freshness("garden grain bowl"),
        },
    ]
    sample_audit = analyze_hygiene("Home kitchen", "evening-prep-sample.mp4")
    sample_audit["id"] = f"{owner_id}-demo-audit-home-kitchen"
    sample_audit["createdAt"] = (now - timedelta(days=1)).isoformat()
    sample_plan = plan_for_week(week_start, profile, seed_progress=True)

    with db_connect() as connection:
        for scan in sample_scans:
            connection.execute(
                """
                INSERT INTO food_scans (id, owner_id, dish_name, created_at, payload)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    scan["id"],
                    owner_id,
                    scan["dishName"],
                    scan["createdAt"],
                    Jsonb(scan),
                ),
            )
        connection.execute(
            """
            INSERT INTO hygiene_audits (id, owner_id, kitchen_name, created_at, payload)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (
                sample_audit["id"],
                owner_id,
                sample_audit["kitchenName"],
                sample_audit["createdAt"],
                Jsonb(sample_audit),
            ),
        )
        connection.execute(
            """
            INSERT INTO nutrition_profiles (profile_id, payload, updated_at)
            VALUES (%s, %s, %s)
            ON CONFLICT (profile_id) DO NOTHING
            """,
            (owner_id, Jsonb(profile), now),
        )
        connection.execute(
            """
            INSERT INTO user_meal_plans (owner_id, week_of, payload, updated_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (owner_id, week_of) DO NOTHING
            """,
            (owner_id, week_start.isoformat(), Jsonb(sample_plan), now),
        )


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


app = FastAPI(
    title="Food Verse AI API",
    version="1.0.0",
    description="Food and nutrition API with AI-powered food lookup, photo/video analysis and recipe generation. Results are estimates, not professional certification.",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)
router = APIRouter(prefix="/api")

def sign_session(session_id: str) -> str:
    signature = hmac.new(
        SESSION_SECRET.encode("utf-8"), session_id.encode("utf-8"), "sha256"
    ).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
    return f"{session_id}.{encoded_signature}"


def verify_session(value: str | None) -> str | None:
    if not value or "." not in value:
        return None
    session_id, supplied_signature = value.rsplit(".", 1)
    if not session_id or not supplied_signature:
        return None
    expected = sign_session(session_id).rsplit(".", 1)[1]
    if hmac.compare_digest(supplied_signature, expected):
        return session_id
    return None


@app.middleware("http")
async def browser_session(request: Request, call_next):
    session_id = verify_session(request.cookies.get("food_verse_session"))
    new_session = session_id is None
    if session_id is None:
        session_id = secrets.token_urlsafe(24)
    request.state.owner_id = session_id
    response = await call_next(request)
    if new_session:
        forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip()
        response.set_cookie(
            key="food_verse_session",
            value=sign_session(session_id),
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            secure=forwarded_proto == "https" or request.url.scheme == "https",
            samesite="lax",
            path="/api",
        )
    return response


def ensure_session_seeded(owner_id: str) -> None:
    if owner_id in _SEEDED_SESSIONS:
        return
    seed_session_data(owner_id)
    _SEEDED_SESSIONS.add(owner_id)


def profile_from_db(
    connection: psycopg.Connection[Any], owner_id: str
) -> dict[str, Any]:
    row = connection.execute(
        "SELECT payload FROM nutrition_profiles WHERE profile_id = %s",
        (owner_id,),
    ).fetchone()
    return row["payload"] if row else default_profile()


def plan_from_db(
    connection: psycopg.Connection[Any],
    owner_id: str,
    week_start: date | None = None,
) -> dict[str, Any]:
    start = week_start or monday_of(local_today())
    row = connection.execute(
        "SELECT payload FROM user_meal_plans WHERE owner_id = %s AND week_of = %s",
        (owner_id, start.isoformat()),
    ).fetchone()
    if row:
        return row["payload"]
    profile = profile_from_db(connection, owner_id)
    plan = plan_for_week(start, profile)
    connection.execute(
        """
        INSERT INTO user_meal_plans (owner_id, week_of, payload, updated_at)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (owner_id, week_of) DO NOTHING
        """,
        (owner_id, start.isoformat(), Jsonb(plan), datetime.now(timezone.utc)),
    )
    return plan


@router.get("/healthz")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/v1/dashboard", response_model=DashboardSummary)
def get_dashboard(request: Request) -> dict[str, Any]:
    owner_id = request.state.owner_id
    ensure_session_seeded(owner_id)
    today = local_today()
    with db_connect() as connection:
        profile = profile_from_db(connection, owner_id)
        plan = plan_from_db(connection, owner_id)
        today_plan = next(
            (entry for entry in plan["days"] if entry["date"] == today.isoformat()),
            None,
        )
        if today_plan is None:
            today_plan = plan["days"][min(today.weekday(), len(plan["days"]) - 1)]
        completed = [meal for meal in today_plan["meals"] if meal["completed"]]
        upcoming = [meal for meal in today_plan["meals"] if not meal["completed"]]
        if not upcoming:
            upcoming = [
                meal
                for day in plan["days"]
                for meal in day["meals"]
                if not meal["completed"]
            ]
        next_meal = upcoming[0] if upcoming else today_plan["meals"][0]
        scans = connection.execute(
            "SELECT payload FROM food_scans WHERE owner_id = %s ORDER BY created_at DESC LIMIT 5",
            (owner_id,),
        ).fetchall()
        audits = connection.execute(
            "SELECT payload FROM hygiene_audits WHERE owner_id = %s ORDER BY created_at DESC LIMIT 5",
            (owner_id,),
        ).fetchall()

        activity: list[dict[str, Any]] = []
        for row in scans:
            scan = row["payload"]
            activity.append(
                {
                    "id": scan["id"],
                    "title": scan["dishName"],
                    "subtitle": f"Food scan · {scan['confidence']}% confidence",
                    "kind": "scan",
                    "createdAt": scan["createdAt"],
                    "score": scan["healthScore"],
                }
            )
        for row in audits:
            audit = row["payload"]
            activity.append(
                {
                    "id": audit["id"],
                    "title": audit["kitchenName"],
                    "subtitle": "Kitchen hygiene estimate",
                    "kind": "audit",
                    "createdAt": audit["createdAt"],
                    "score": audit["safetyScore"],
                }
            )
        activity.sort(key=lambda item: item["createdAt"], reverse=True)
        average_score = round(
            sum(row["payload"]["healthScore"] for row in scans) / len(scans)
        ) if scans else 0
        weekly_calories = [
            sum(meal["calories"] for meal in day["meals"])
            for day in plan["days"]
        ]
        nutrition = [meal for meal in completed]
        return {
            "calorieTarget": profile["calorieTarget"],
            "caloriesConsumed": sum(meal["calories"] for meal in nutrition),
            "proteinConsumed": round(sum(meal["protein"] for meal in nutrition), 1),
            "carbsConsumed": round(sum(meal.get("carbs", 0) for meal in nutrition), 1),
            "fatConsumed": round(sum(meal.get("fat", 0) for meal in nutrition), 1),
            "healthScore": average_score,
            "mealsLogged": len(completed),
            "mealsPlanned": len(today_plan["meals"]),
            "weeklyCalories": weekly_calories,
            "recentActivity": activity[:6],
            "nextMeal": next_meal,
        }


@router.get("/v1/scans", response_model=list[FoodScan])
def list_scans(request: Request) -> list[dict[str, Any]]:
    owner_id = request.state.owner_id
    ensure_session_seeded(owner_id)
    with db_connect() as connection:
        rows = connection.execute(
            "SELECT payload FROM food_scans WHERE owner_id = %s ORDER BY created_at DESC LIMIT 30",
            (owner_id,),
        ).fetchall()
        return [row["payload"] for row in rows]


@router.post("/v1/scan-food", response_model=FoodScan, status_code=201)
def scan_food(body: FoodScanInput, request: Request) -> dict[str, Any]:
    owner_id = request.state.owner_id
    ensure_session_seeded(owner_id)
    scan = analyze_food(body.source, body.fileName, body.description)
    with db_connect() as connection:
        connection.execute(
            """
            INSERT INTO food_scans (id, owner_id, dish_name, created_at, payload)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                scan["id"],
                owner_id,
                scan["dishName"],
                scan["createdAt"],
                Jsonb(scan),
            ),
        )
    return scan


@router.post("/v1/detect-freshness", response_model=FreshnessResult)
def detect_freshness(body: FreshnessInput) -> dict[str, Any]:
    return estimate_freshness(body.food, body.notes)


@router.get("/v1/audits", response_model=list[HygieneAudit])
def list_audits(request: Request) -> list[dict[str, Any]]:
    owner_id = request.state.owner_id
    ensure_session_seeded(owner_id)
    with db_connect() as connection:
        rows = connection.execute(
            "SELECT payload FROM hygiene_audits WHERE owner_id = %s ORDER BY created_at DESC LIMIT 30",
            (owner_id,),
        ).fetchall()
        return [row["payload"] for row in rows]


@router.post("/v1/analyze-hygiene", response_model=HygieneAudit, status_code=201)
def analyze_kitchen(body: HygieneAuditInput, request: Request) -> dict[str, Any]:
    owner_id = request.state.owner_id
    ensure_session_seeded(owner_id)
    audit = analyze_hygiene(body.kitchenName.strip(), body.videoName)
    with db_connect() as connection:
        connection.execute(
            """
            INSERT INTO hygiene_audits (id, owner_id, kitchen_name, created_at, payload)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                audit["id"],
                owner_id,
                audit["kitchenName"],
                audit["createdAt"],
                Jsonb(audit),
            ),
        )
    return audit


@router.get("/v1/profile", response_model=NutritionProfile)
def get_profile(request: Request) -> dict[str, Any]:
    owner_id = request.state.owner_id
    ensure_session_seeded(owner_id)
    with db_connect() as connection:
        return profile_from_db(connection, owner_id)


@router.put("/v1/profile", response_model=NutritionProfile)
def save_profile(body: NutritionProfileInput, request: Request) -> dict[str, Any]:
    owner_id = request.state.owner_id
    ensure_session_seeded(owner_id)
    profile = body.model_dump()
    with db_connect() as connection:
        connection.execute(
            """
            INSERT INTO nutrition_profiles (profile_id, payload, updated_at)
            VALUES (%s, %s, %s)
            ON CONFLICT (profile_id)
            DO UPDATE SET payload = EXCLUDED.payload, updated_at = EXCLUDED.updated_at
            """,
            (owner_id, Jsonb(profile), datetime.now(timezone.utc)),
        )
    return profile


@router.get("/v1/meal-plan", response_model=MealPlan)
def get_meal_plan(request: Request) -> dict[str, Any]:
    owner_id = request.state.owner_id
    ensure_session_seeded(owner_id)
    with db_connect() as connection:
        return plan_from_db(connection, owner_id)


@router.post("/v1/meal-plan", response_model=MealPlan, status_code=201)
def generate_meal_plan(body: MealPlanInput, request: Request) -> dict[str, Any]:
    owner_id = request.state.owner_id
    ensure_session_seeded(owner_id)
    start = monday_of(body.weekOf or local_today())
    with db_connect() as connection:
        profile = profile_from_db(connection, owner_id)
        plan = plan_for_week(start, profile)
        connection.execute(
            """
            INSERT INTO user_meal_plans (owner_id, week_of, payload, updated_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (owner_id, week_of)
            DO UPDATE SET payload = EXCLUDED.payload, updated_at = EXCLUDED.updated_at
            """,
            (owner_id, start.isoformat(), Jsonb(plan), datetime.now(timezone.utc)),
        )
        return plan


@router.patch("/v1/meals/{meal_id}", response_model=PlannedMeal)
def update_meal_completion(
    meal_id: str, body: MealCompletionInput, request: Request
) -> dict[str, Any]:
    owner_id = request.state.owner_id
    ensure_session_seeded(owner_id)
    with db_connect() as connection:
        rows = connection.execute(
            "SELECT week_of, payload FROM user_meal_plans WHERE owner_id = %s ORDER BY week_of DESC FOR UPDATE",
            (owner_id,),
        ).fetchall()
        for row in rows:
            plan = row["payload"]
            for day in plan["days"]:
                for meal in day["meals"]:
                    if meal["id"] == meal_id:
                        meal["completed"] = body.completed
                        connection.execute(
                            """
                            UPDATE user_meal_plans SET payload = %s, updated_at = %s
                            WHERE owner_id = %s AND week_of = %s
                            """,
                            (
                                Jsonb(plan),
                                datetime.now(timezone.utc),
                                owner_id,
                                row["week_of"],
                            ),
                        )
                        return meal
    raise HTTPException(status_code=404, detail="Planned meal not found.")


@router.patch("/v1/grocery-list/{item_id}", response_model=GroceryItem)
def update_grocery_item(
    item_id: str, body: GroceryItemInput, request: Request
) -> dict[str, Any]:
    owner_id = request.state.owner_id
    ensure_session_seeded(owner_id)
    with db_connect() as connection:
        rows = connection.execute(
            "SELECT week_of, payload FROM user_meal_plans WHERE owner_id = %s ORDER BY week_of DESC FOR UPDATE",
            (owner_id,),
        ).fetchall()
        for row in rows:
            plan = row["payload"]
            for item in plan["groceryList"]:
                if item["id"] == item_id:
                    item["checked"] = body.checked
                    connection.execute(
                        """
                        UPDATE user_meal_plans SET payload = %s, updated_at = %s
                        WHERE owner_id = %s AND week_of = %s
                        """,
                        (
                            Jsonb(plan),
                            datetime.now(timezone.utc),
                            owner_id,
                            row["week_of"],
                        ),
                    )
                    return item
    raise HTTPException(status_code=404, detail="Grocery item not found.")


@router.post("/v1/chef-guide", response_model=ChefGuide)
def create_chef_guide(body: ChefGuideInput) -> dict[str, Any]:
    return make_chef_guide(body.dish, body.ingredients, body.allergies)


# --------------------------------------------------------------------------
# AI features. Keys stay on the server; every call is validated and guarded in
# services/food_ai.py. Failures are reported as {"detail": {"code", "message"}}.
# --------------------------------------------------------------------------
_AI_CALLS: dict[str, list[float]] = {}
AI_RATE_LIMIT = int(os.environ.get("FOODVERSE_AI_RATE_LIMIT", "30"))
AI_RATE_WINDOW_SECONDS = 600


def ai_http_error(error: AIError) -> HTTPException:
    headers = {"Retry-After": str(error.retry_after)} if error.retry_after else None
    return HTTPException(status_code=error.http_status, detail=error.as_detail(), headers=headers)


def check_ai_rate_limit(owner_id: str) -> None:
    now = time.monotonic()
    recent = [stamp for stamp in _AI_CALLS.get(owner_id, []) if now - stamp < AI_RATE_WINDOW_SECONDS]
    if len(recent) >= AI_RATE_LIMIT:
        wait = int(AI_RATE_WINDOW_SECONDS - (now - recent[0])) + 1
        raise ai_http_error(AIError("rate_limited", "You've reached the AI request limit for now. Please try again in a few minutes.", retry_after=wait))
    recent.append(now)
    _AI_CALLS[owner_id] = recent


def merged_allergies(owner_id: str, extra: list[str]) -> list[str]:
    """Saved profile allergies plus any sent with the request (deduplicated)."""
    with db_connect() as connection:
        saved = profile_from_db(connection, owner_id).get("allergies", [])
    merged: list[str] = []
    for item in [*saved, *extra]:
        cleaned = " ".join(str(item).split())
        if cleaned and cleaned.lower() not in (m.lower() for m in merged):
            merged.append(cleaned)
    return merged


def run_ai(request: Request, work):
    """Common wrapper: rate limit, build the model client, translate AIError."""
    owner_id = request.state.owner_id
    ensure_session_seeded(owner_id)
    try:
        llm = get_llm()
        check_ai_rate_limit(owner_id)
        return work(llm, owner_id)
    except AIError as error:
        raise ai_http_error(error) from error


@router.get("/v1/ai/status")
def ai_status() -> dict[str, Any]:
    return {
        **ai_settings(),
        "limits": {"maxImages": 4, "maxVideoFrames": 8, "maxImageBytes": 5 * 1024 * 1024},
    }


@router.post("/v1/ai/food-info")
def ai_food_info(body: FoodInfoInput, request: Request) -> dict[str, Any]:
    def work(llm, owner_id):
        return food_ai.search_food(
            llm, body.query, diet=body.dietConvention,
            allergies=merged_allergies(owner_id, body.allergies),
            ingredient_list=body.ingredientList, nutrition_lookup=get_nutrition_lookup(),
        )
    return run_ai(request, work)


@router.post("/v1/ai/analyze-media", response_model=FoodScan, status_code=201)
def ai_analyze_media(body: AnalyzeMediaInput, request: Request) -> dict[str, Any]:
    def work(llm, owner_id):
        with db_connect() as connection:
            profile = profile_from_db(connection, owner_id)
        goal = body.goal or (profile.get("goal") if profile.get("goal") != "balanced" else None)
        scan = food_ai.analyze_media(
            llm, body.kind, images=[image.model_dump() for image in body.images],
            description=body.description, diet=body.dietConvention,
            allergies=merged_allergies(owner_id, body.allergies), goal=goal, file_name=body.fileName,
        )
        with db_connect() as connection:
            connection.execute(
                """
                INSERT INTO food_scans (id, owner_id, dish_name, created_at, payload)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (scan["id"], owner_id, scan["dishName"], scan["createdAt"], Jsonb(scan)),
            )
        return scan
    return run_ai(request, work)


@router.post("/v1/ai/identify-ingredients")
def ai_identify_ingredients(body: IdentifyIngredientsInput, request: Request) -> dict[str, Any]:
    return run_ai(request, lambda llm, _owner: food_ai.identify_ingredients(
        llm, images=[image.model_dump() for image in body.images], note=body.note))


@router.post("/v1/ai/recipes")
def ai_recipes(body: RecipeRequestInput, request: Request) -> dict[str, Any]:
    def work(llm, owner_id):
        return food_ai.generate_recipes(
            llm, ingredients=body.ingredients, dish=body.dish, diet=body.dietConvention,
            allergies=merged_allergies(owner_id, body.allergies), exclude=body.excludeIngredients,
            preferences=body.preferences.model_dump(), previous_recipe=body.previousRecipe,
            follow_up=body.followUp, assume_pantry_staples=body.assumePantryStaples,
        )
    return run_ai(request, work)


@router.post("/v1/ai/suggestions")
def ai_suggestions(body: SuggestionsInput, request: Request) -> dict[str, Any]:
    def work(llm, owner_id):
        with db_connect() as connection:
            profile = profile_from_db(connection, owner_id)
        goal = body.goal or str(profile.get("goal", "")).replace("_", " ")
        return food_ai.suggest_foods(
            llm, goal=goal, diet=body.dietConvention,
            allergies=merged_allergies(owner_id, body.allergies),
            ingredients=body.ingredients, context=body.context,
        )
    return run_ai(request, work)


app.include_router(router)
