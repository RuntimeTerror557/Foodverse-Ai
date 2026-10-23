# Food Verse AI

Food Verse AI helps people explore nutrition, estimate freshness, review kitchen practices, cook with guidance, and plan meals around their goals.

## Run & Operate

- `pnpm --filter @workspace/food-verse-ai run dev` — run the web app
- `pnpm --filter @workspace/api-server run dev` — run the FastAPI server through Uvicorn
- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from the OpenAPI spec
- `pnpm --filter @workspace/db run push` — push DB schema changes (dev only)
- Required env: `DATABASE_URL` — Postgres connection string

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
- `artifacts/api-server/src/services/analysis.py` — deterministic demo analysis handlers
- `lib/api-spec/openapi.yaml` — API contract source of truth
- `lib/db/src/schema/food-verse.ts` — PostgreSQL schema
- `artifacts/food-verse-ai/src/index.css` — app theme

## Architecture decisions

- API and generated client share the OpenAPI contract under `/api`.
- Scan and audit records, profile settings, and weekly plans persist in PostgreSQL.
- Upload previews stay in the browser; the demo API receives descriptions and filenames, not media bytes.
- Food, freshness, and hygiene outputs are estimates from deterministic mock handlers, not certified safety assessments.

## Product

The app combines nutrition scans, freshness estimates, kitchen hygiene scorecards, allergy-aware cooking guidance, and personalized weekly meal planning. It includes demo records so the dashboard is populated on first run.

## User preferences

- Modern food-tech theme with dark/light toggle, emerald/teal, amber accents, and slate-dark surfaces.

## Gotchas

- Regenerate API client and Zod files after changing `lib/api-spec/openapi.yaml`.
- Run the database schema push in development after changing `lib/db/src/schema/`.
- The scan and safety flows are mocked; they do not inspect uploaded media or certify food safety.

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
