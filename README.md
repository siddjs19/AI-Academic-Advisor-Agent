# PrepPilot AI

An academic mentor, not a timetable generator. It reads your syllabus, remembers your marks, plans your
week with a constraint solver, teaches what you ask about, tests you on what you keep getting wrong,
drills it with spaced repetition, runs mock vivas, and tells you when something is about to go wrong —
before you ask.

**Runs offline with no API key.** Planning, grading of objective questions, spaced repetition, analytics
and proactive recommendations all work with zero model access. Features that need generation say so
plainly instead of inventing content.

---

## Quick start

```bash
cd backend
pip install -r requirements.txt
cd ../frontend && npm install && npm run build && cd ..
./start.sh                      # → http://127.0.0.1:8000
```

The database seeds itself on first boot with a demo semester (three courses, a solved plan, one graded
attempt, flashcards and an open lab file). Sign in with:

```
demo@preppilot.app / demo1234
```

Or register a new account — you land in onboarding, then upload a syllabus.

### Frontend dev mode (hot reload)

```bash
# terminal 1
cd backend && uvicorn app.main:app --reload          # :8000
# terminal 2
cd frontend && npm run dev                           # :5173, proxies /api → :8000
```

### Enable a model (optional, unlocks generation)

```bash
export LLM_PROVIDER=gemini          # gemini | groq | openai (any compatible endpoint)
export LLM_API_KEY=...
export LLM_MODEL=gemini-2.0-flash
# for openai-compatible servers (vLLM, Ollama, OpenRouter):
# export LLM_BASE_URL=http://localhost:11434/v1
```

Without this, the app runs in **offline mode**: the tutor says it cannot generate an explanation, quiz
generation falls back to a labelled sample question bank, and descriptive answers are stored as
`pending` rather than scored.

---

## What's inside

| Area | What it does |
|---|---|
| **Planning** | OR-Tools CP-SAT places every topic inside your real free hours: daily caps, per-course caps, prerequisite order, nothing after an exam, minimum block length, and a churn penalty so replans stay stable. Infeasibility is reported with the topics to cut. |
| **Teaching** | Explanations pitched at your mastery level, with your uploaded notes retrieved into the prompt, ending in a Socratic check. |
| **Assessment** | MCQ, multi-select, true/false, numerical, short and descriptive questions. Objective types graded by rules; written answers by keyword coverage or a rubric; ungradable answers marked `pending`. |
| **Viva** | Turn-based oral exam scored on concept coverage, structure, completeness and clarity. |
| **Revision** | SM-2 style scheduling (ease + interval), cards generated from your weakest topics. |
| **Analytics** | Accuracy over time, mastery per course, weak topics, repeated mistakes, adherence, retention. |
| **Proactive** | Seven event rules over real rows → ranked recommendations with accept/dismiss. |
| **Assignments** | Briefs decomposed into tasks with time estimates; progress feeds the planner. |
| **Auth** | Email + password (PBKDF2), JWT with a revocation counter so logout kills every existing token. |

Full detail: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · [docs/API.md](docs/API.md) ·
[docs/STATUS.md](docs/STATUS.md) (what works, what's partial, what's missing).

---

## Screens

Landing → Auth → Onboarding → Dashboard → Study plan → Tutor → Practice → Viva → Revision → Subjects →
Assignments → Analytics → Settings. Screenshots in `docs/screenshots/`.

---

## Stack

* **Backend** — Python 3.12, FastAPI, SQLAlchemy 2, SQLite locally / Postgres in production.
* **Solver** — OR-Tools CP-SAT, in-process, ~1–3 s for a semester.
* **Agents** — one supervisor + seven specialists, custom orchestration (no LangGraph dependency).
* **Frontend** — React 18, Vite 5, Tailwind 3, Recharts.
* **Auth** — PyJWT (HS256), PBKDF2-SHA256 password hashing (stdlib, 260k rounds).

See [docs/STATUS.md](docs/STATUS.md) for where this deliberately differs from the reference stack
(Node/Express split, MongoDB, vector DB) and why.

---

## Tests

```bash
cd backend && python -m pytest        # 35 tests
```

Covers: solver properties (no overlaps, caps, deadlines, prerequisite order, overload reporting,
replan stability), grading rules, mastery that resists single answers, SM-2 intervals, auth isolation
and logout revocation, and the brief's workflows end-to-end through the HTTP API.

---

## Deployment

One container serves the API and the built SPA:

```bash
docker build -t preppilot .
docker run -p 8000:8000 -e SECRET_KEY=$(openssl rand -hex 32) preppilot
```

* **Database** — point `DATABASE_URL` at Supabase/Postgres. SQLite is for local use only.
* **Host** — Render free web service or a Hugging Face Docker Space; free instances sleep when idle.
* **Secrets** — `SECRET_KEY` must be set to a long random value in production; the default is a
  development placeholder and is not safe.
* **`AUTO_SEED=false`** in production if you don't want the demo semester created on boot.

---

## Honest limitations

Read [docs/STATUS.md](docs/STATUS.md) before treating this as finished. Short version: the vertical
slice works end-to-end, generation features need a model key, there is no voice, no vector search
(keyword retrieval over notes instead), and no rate limiting on login.
