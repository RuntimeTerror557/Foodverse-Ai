# Food Verse AI

Food Verse AI helps people explore nutrition, estimate freshness, review kitchen practices, cook with guidance, and plan meals around their goals.

## Run & Operate

- `pnpm --filter @workspace/food-verse-ai run dev` — run the web app
- `pnpm --filter @workspace/api-server run dev` — run the FastAPI server through Uvicorn
- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from the OpenAPI spec
- `pnpm --filter @workspace/db run push` — push DB schema changes (dev only)
- `cd artifacts/api-server/src && python -m unittest discover -s ../tests -v` — offline AI tests (fake model, no network or key needed)
- Required env: `DATABASE_URL` — Postgres connection string; `SESSION_SECRET` — signs browser session cookies
- AI env (server-side only): one of `GEMINI_API_KEY` (free tier available), `XAI_API_KEY` or `ANTHROPIC_API_KEY` (required for AI features; `FOODVERSE_AI_PROVIDER` picks one if several are set; without it `/api/v1/ai/*` returns 503 and the UI shows a setup notice); optional `FOODVERSE_AI_MODEL` (defaults: `gemini-flash-latest`, `grok-4`, `claude-sonnet-5-5`), `FOODVERSE_AI_TIMEOUT` (seconds, default 90), `FOODVERSE_AI_RATE_LIMIT` (calls per 10 min per browser session, default 30), `USDA_API_KEY` (adds a USDA FoodData Central per-100 g reference to food lookups)

## Stack

- pnpm workspaces, Node.js 24, TypeScript 5.9
- Frontend: React, Vite, Tailwind CSS, TanStack Query
- API: FastAPI, Pydantic, Uvicorn
- DB: PostgreSQL + Drizzle ORM
- Validation: Pydantic on the API, generated Zod schemas for TypeScript
- API codegen: Orval (from OpenAPI spec)
- Python environment: uv (`pyproject.toml`, `uv.lock`)

## Where things live

- `artifacts/food-verse-ai` — dashboard and user-facing app
- `artifacts/api-server/src/main.py` — FastAPI routes, profile, meal plan, and persistence
- `artifacts/api-server/src/services/analysis.py` — deterministic demo handlers (hygiene audit, freshness text check, legacy chef guide)
- `artifacts/api-server/src/services/food_ai.py` — AI workflows: food lookup, image/video/text analysis, ingredient photos, recipes, suggestions
- `services/llm.py` (provider client, retries, structured output), `validators.py` (model-output validation), `safety.py` (allergy/diet guards), `media.py` (upload checks), `nutrition_db.py` (USDA reference), `prompts.py`, `schemas.py`
- `artifacts/food-verse-ai/src/lib/food-ai.ts` and `components/ai-panels.tsx` — client, frame extraction and AI UI panels
- `lib/api-spec/openapi.yaml` — API contract source of truth
- `lib/db/src/schema/food-verse.ts` — PostgreSQL schema
- `artifacts/food-verse-ai/src/index.css` — app theme

## Architecture decisions

- API and generated client share the OpenAPI contract under `/api`.
- Scan and audit records, profile settings, and weekly plans persist in PostgreSQL.
- A signed, HTTP-only browser session keeps anonymous visitors' saved data separate; there is no account sign-in or cross-device sync.
- Scanner photos (downscaled JPEG) and sampled video frames (up to 6) are sent to the server and on to the AI provider for analysis; videos are never uploaded whole, and audio files are not analyzed (voice queries use browser speech-to-text).
- Model output is validated, then re-checked by deterministic allergy/diet guards that can only make answers more conservative.
- AI endpoints are additive under `/api/v1/ai/*`; they are not yet in the generated client (hand-written `food-ai.ts` is used until `codegen` is run).
- Food lookup, scans and recipes are AI estimates; the freshness text check and hygiene audit are still deterministic demo handlers. None are safety certifications.

## Product

The app combines nutrition scans, freshness estimates, kitchen hygiene scorecards, allergy-aware cooking guidance, and personalized weekly meal planning. Each browser session receives its own demo records on first use.

## User preferences

- Modern food-tech theme with dark/light toggle, emerald/teal, amber accents, and slate-dark surfaces.

## Gotchas

- Regenerate API client and Zod files after changing `lib/api-spec/openapi.yaml`.
- Run the database schema push in development after changing `lib/db/src/schema/`.
- Hygiene audit and the typed freshness check remain mocked. AI paths were tested offline against a fake model only; verify against the real API before shipping.

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
