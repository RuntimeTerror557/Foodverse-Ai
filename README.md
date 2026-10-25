[README (2).md](https://github.com/user-attachments/files/33921749/README.2.md)
# 🥗 Food Verse AI

Food Verse AI helps people explore nutrition, estimate food freshness, review kitchen hygiene, cook with allergy-aware guidance, and plan weekly meals around their goals.

> ⚠️ **Disclaimer:** Food lookups, scans and recipes are AI estimates. The freshness text check and hygiene audit are currently deterministic demo handlers. Nothing in this app is a food-safety certification or medical advice.

---

## ✨ Features

- **Nutrition scans** – analyze food from photos, short video (sampled frames), or text, and look up nutrition information.
- **Freshness estimates** – estimate how fresh a food item is.
- **Kitchen hygiene scorecards** – audit kitchen practices and get a score.
- **Allergy-aware cooking guidance** – recipes and suggestions that respect your allergies and diet.
- **Ingredient photos → recipes** – snap your ingredients and get recipe ideas.
- **Personalized weekly meal planning** – plans built around your profile and goals.
- **Voice queries** – uses the browser's built-in speech-to-text.
- **Safety guards** – model output is validated, then re-checked by deterministic allergy/diet rules that can only make answers *more* conservative.
- **Modern UI** – dark/light toggle with an emerald/teal theme and amber accents.

---

## 🧱 Tech Stack

| Layer | Technology |
|---|---|
| Monorepo | pnpm workspaces, Node.js 24, TypeScript 5.9 |
| Frontend | React, Vite, Tailwind CSS, TanStack Query |
| API | FastAPI, Pydantic, Uvicorn |
| Database | PostgreSQL + Drizzle ORM |
| Validation | Pydantic (API) and generated Zod schemas (TypeScript) |
| API codegen | Orval, from an OpenAPI spec |
| Python env | uv (`pyproject.toml`, `uv.lock`) |
| AI providers | Google Gemini, xAI Grok, or Anthropic Claude (pick one) |

---

## 📁 Project Structure

```
Foodverse-Ai/
├── artifacts/
│   ├── food-verse-ai/          # Dashboard & user-facing web app (React + Vite)
│   │   └── src/
│   │       ├── lib/food-ai.ts          # AI client, frame extraction
│   │       ├── components/ai-panels.tsx # AI UI panels
│   │       └── index.css               # App theme
│   └── api-server/             # FastAPI backend
│       ├── src/
│       │   ├── main.py                 # Routes, profile, meal plan, persistence
│       │   └── services/
│       │       ├── analysis.py         # Deterministic demo handlers (hygiene audit, freshness text check)
│       │       ├── food_ai.py          # AI workflows: lookup, image/video/text analysis, recipes, suggestions
│       │       ├── llm.py              # Provider client, retries, structured output
│       │       ├── validators.py       # Model-output validation
│       │       ├── safety.py           # Allergy/diet guards
│       │       ├── media.py            # Upload checks
│       │       ├── nutrition_db.py     # USDA reference data
│       │       ├── prompts.py
│       │       └── schemas.py
│       └── tests/                      # Offline AI tests (fake model)
├── lib/
│   ├── api-spec/openapi.yaml   # API contract (source of truth)
│   └── db/src/schema/food-verse.ts  # PostgreSQL schema
├── scripts/
├── .env.example
├── pnpm-workspace.yaml
├── pyproject.toml / uv.lock
└── replit.md
```

---

## 🚀 Getting Started

### Prerequisites

- [Node.js 24](https://nodejs.org/) and [pnpm](https://pnpm.io/)
- [Python](https://www.python.org/) and [uv](https://docs.astral.sh/uv/)
- A PostgreSQL database
- An API key for **one** AI provider (Gemini has a free tier)

### 1. Clone & install

```bash
git clone https://github.com/RuntimeTerror557/Foodverse-Ai.git
cd Foodverse-Ai

pnpm install      # JavaScript/TypeScript dependencies
uv sync           # Python dependencies
```

### 2. Configure environment

```bash
cp .env.example .env
```

Then edit `.env`:

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | ✅ | PostgreSQL connection string |
| `SESSION_SECRET` | ✅ | Secret used to sign browser session cookies |
| `GEMINI_API_KEY` / `XAI_API_KEY` / `ANTHROPIC_API_KEY` | ✅ (one) | AI provider key. Gemini has a [free tier](https://aistudio.google.com/apikey) |
| `FOODVERSE_AI_PROVIDER` | Optional | `gemini`, `xai` or `anthropic` – only needed if several keys are set |
| `FOODVERSE_AI_MODEL` | Optional | Override the default model (must support images + tool calling). Defaults: `gemini-flash-latest`, `grok-4`, `claude-sonnet-5-5` |
| `FOODVERSE_AI_TIMEOUT` | Optional | Seconds before an AI call times out (default `90`) |
| `FOODVERSE_AI_RATE_LIMIT` | Optional | AI calls per 10 min per browser session (default `30`) |
| `USDA_API_KEY` | Optional | Adds a USDA FoodData Central per-100 g reference to food lookups |

> 🔒 These are **server-side only**. Never expose them in frontend code. Without an AI key, `/api/v1/ai/*` returns `503` and the UI shows a setup notice.

### 3. Set up the database

```bash
pnpm --filter @workspace/db run push   # development only
```

### 4. Run the app

In two terminals:

```bash
# Terminal 1 – FastAPI server (Uvicorn)
pnpm --filter @workspace/api-server run dev

# Terminal 2 – Web app
pnpm --filter @workspace/food-verse-ai run dev
```

---

## 🛠️ Useful Commands

| Command | What it does |
|---|---|
| `pnpm run typecheck` | Typecheck all packages |
| `pnpm run build` | Typecheck + build all packages |
| `pnpm --filter @workspace/api-spec run codegen` | Regenerate API hooks and Zod schemas from the OpenAPI spec |
| `pnpm --filter @workspace/db run push` | Push DB schema changes (dev only) |
| `cd artifacts/api-server/src && python -m unittest discover -s ../tests -v` | Run offline AI tests (fake model – no network or API key needed) |

---

## 🏗️ Architecture Notes

- The API and generated client share one OpenAPI contract under `/api`.
- Scan and audit records, profile settings, and weekly plans are persisted in PostgreSQL.
- A signed, HTTP-only browser session keeps each anonymous visitor's data separate. There is **no account sign-in or cross-device sync**; each session gets its own demo records on first use.
- Scanner photos (downscaled JPEG) and up to 6 sampled video frames are sent to the server and on to the AI provider. Videos are never uploaded whole, and audio files are not analyzed.
- AI endpoints live under `/api/v1/ai/*` and are not yet in the generated client – the hand-written `food-ai.ts` is used until `codegen` is run.
---

## ⚠️ Known Limitations

- The **hygiene audit** and **typed freshness check** are still mocked (deterministic demo handlers).
- AI paths have been tested offline against a fake model only – verify against a real provider API before shipping.
- After changing `lib/api-spec/openapi.yaml`, re-run `codegen`; after changing `lib/db/src/schema/`, re-run the DB `push`.

---

## 🤝 Contributing

Contributions are welcome, whether it's a bug fix, a new feature, better docs, or a test. Here's how to get started.

### Ways to contribute

- 🐛 **Report bugs** – open an [issue](https://github.com/RuntimeTerror557/Foodverse-Ai/issues) with steps to reproduce, what you expected, and what happened (screenshots help).
- 💡 **Suggest features** – open an issue describing the problem you want solved and your idea for solving it.
- 🔧 **Fix or build** – pick an open issue, or propose your own change before starting on something large.
- 📝 **Improve docs** – clarify setup steps, add examples, fix typos.
- 🧪 **Add tests** – especially for the AI safety guards, validators, and media checks.

### Contribution workflow

1. **Fork** the repository and clone your fork.
2. **Create a branch** from `main` with a descriptive name:
   ```bash
   git checkout -b feature/short-description   # or fix/short-description
   ```
3. **Set up the project** by following [Getting Started](#-getting-started).
4. **Make your changes**, keeping each pull request focused on one thing.
5. **Run the checks** before committing:
   ```bash
   pnpm run typecheck
   cd artifacts/api-server/src && python -m unittest discover -s ../tests -v
   ```
6. **Commit** with a clear message, for example `fix: handle empty ingredient photo upload`.
7. **Push** your branch and **open a pull request** against `main`. Describe what changed, why, and how you tested it. Link any related issue (e.g. `Closes #12`).

### Guidelines

- **Keep the OpenAPI spec in sync.** If you change `lib/api-spec/openapi.yaml`, run `pnpm --filter @workspace/api-spec run codegen` and commit the regenerated files.
- **Database changes.** If you edit `lib/db/src/schema/`, run `pnpm --filter @workspace/db run push` locally and mention the schema change in your PR.
- **Never commit secrets.** Keep API keys and `SESSION_SECRET` in `.env` (already git-ignored). Only add placeholders to `.env.example`.
- **Respect the safety design.** The allergy/diet guards must only ever make AI answers *more* conservative. Changes to `safety.py`, `validators.py`, or prompts should include tests.
- **Test offline when possible.** The AI tests use a fake model, so they need no network or API key. Please don't write tests that depend on live provider calls.
- **Be honest about AI limits.** Don't present estimates as certified food-safety or medical guidance in the UI or docs.
- **Match the existing style.** Use TypeScript types on the frontend and Pydantic models on the API, and keep the existing theme and component patterns.

### Pull request checklist

- [ ] The PR is focused on one change and describes what, why, and how it was tested
- [ ] `pnpm run typecheck` and the offline Python tests pass
- [ ] `pnpm run build` succeeds if you touched build or config files
- [ ] API client and Zod files were regenerated if `openapi.yaml` changed
- [ ] DB schema changes are mentioned in the PR description
- [ ] No secrets, `.env` files, or personal data are committed
- [ ] New behavior has tests, and docs (this README or `replit.md`) are updated
- [ ] UI changes include a before/after screenshot, in both dark and light mode

### Commit message convention

Use short, imperative messages with a type prefix:

| Prefix | Use for |
|---|---|
| `feat:` | A new feature |
| `fix:` | A bug fix |
| `docs:` | Documentation only |
| `test:` | Adding or updating tests |
| `refactor:` | Code changes that don't alter behavior |
| `chore:` | Tooling, dependencies, config |

### Good first contributions

- Replace the mocked **hygiene audit** with a real implementation.
- Replace the mocked **typed freshness check** with an AI-backed one.
- Move the hand-written `/api/v1/ai/*` client (`food-ai.ts`) into the generated OpenAPI client.
- Add more tests for `safety.py`, `validators.py`, and `media.py`.
- Improve accessibility (keyboard navigation, ARIA labels, color contrast) in the AI panels.
- Add support for more AI providers or models in `llm.py`.

### Review process

- A maintainer will review your PR as soon as they can; please be patient.
- Reviewers may request changes. Push follow-up commits to the same branch and the PR will update automatically.
- Once approved and checks pass, a maintainer will merge it.
- Keep discussion on the PR or issue so others can follow along.

### Reporting security issues

If you find a vulnerability (for example, a way to bypass the allergy guards, leak API keys, or access another session's data), please **don't open a public issue**. Contact the maintainer privately through GitHub, using the repository's Security tab if private reporting is enabled.

### Troubleshooting for contributors

- **AI endpoints return 503:** no AI provider key is set. Add one to `.env`, or work on non-AI features and use the offline tests.
- **Type errors after pulling changes:** run `pnpm install`, then `pnpm --filter @workspace/api-spec run codegen`.
- **Database errors:** confirm `DATABASE_URL` is correct, then run `pnpm --filter @workspace/db run push`.

### Code of conduct

Be respectful and constructive in issues, pull requests, and reviews. Harassment or discrimination of any kind won't be tolerated.

### Questions?

Not sure where to start? Open an issue with the `question` label and we'll help you out.

## 📄 License

