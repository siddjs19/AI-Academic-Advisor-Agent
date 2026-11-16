# Architecture

## Shape

```
React SPA ──HTTP/JSON──► FastAPI ──► services ──► SQLAlchemy ──► SQLite / Postgres
   │                       │
   │                       ├──► supervisor ──► specialist agents ──► LLM (optional)
   │                       └──► planner ──► CP-SAT solver (in-process, no network)
   └── JWT (HS256) ─────────┘
```

One process serves the JSON API under `/api` and the built SPA everywhere else. That is a deliberate
deviation from the reference three-service stack — see `STATUS.md`.

## Why the solver plans and the model doesn't

An LLM asked for a study plan will double-book you, forget a prerequisite, and promise 40 hours of work
in 12 available hours. You cannot tell by reading the output. So:

* **Planning is a constraint problem.** `planner/solver.py` discretises free time into 30-minute units
  and assigns `x[unit, topic]` booleans under hard constraints.
* **The model parses and explains.** Syllabus → structured JSON; question → explanation. Both are
  validated before they touch the database.
* **Infeasibility is a first-class output.** Each topic carries a slack variable; the objective penalises
  uncovered hours, so the solver returns a plan *and* names the lowest-value topics it had to drop.

## Agents

| Agent | Module | Needs a model? |
|---|---|---|
| Supervisor (routing, context, delegation) | `agents/supervisor.py` | no (rules first) |
| Planning | `planner/service.py` + `solver.py` | no |
| Teaching | `agents/tutor.py` | yes for explanations |
| Assessment | `agents/quiz.py` | yes for generation, no for grading |
| Communication / viva | `agents/tutor.py` | optional (rule-scored fallback) |
| Revision | `agents/revision.py` | optional (bank fallback) |
| Assignment | `agents/assignments.py` | optional (templates fallback) |
| Analytics | `memory.py` | no |

Routing is deterministic first: `classify()` matches intents by pattern so an obvious request never
burns a model call. Every delegation writes an `agent_events` row, which is why the UI can label each
reply with the specialist that produced it.

## Shared memory

`memory.py` is the only place mastery is computed, and everything reads from it:

* `record_evidence()` — exponential update, α ≈ 0.18 scaled by difficulty. One correct answer moves a
  topic by less than 0.2; `confident` requires ≥ 3 data points.
* `effective_mastery()` — blends quiz evidence with marks; quiz evidence dominates once it exists.
* `weak_topics()` — ranked by `(1 − mastery) × weight`.
* `repeated_mistakes()` — the same topic missed ≥ 2 times, with the question stems.
* `exam_readiness()` — weighted mastery per course against days remaining.
* `analytics()` — series, adherence, retention, all recomputed from rows.

## Data model

23 tables. The ones that matter:

```
users ─1:1─ students ─┬─ courses ─┬─ topics ──┬─ topic_mastery (evidence)
                      │           │           └─ flashcards ── review_logs
                      │           └─ assessments ── marks
                      ├─ availability / blackouts
                      ├─ plan_runs ── blocks
                      ├─ quiz_sets ── questions ── attempts ── answers
                      ├─ viva_sessions
                      ├─ assignments ── assignment_tasks
                      ├─ conversations ── messages
                      ├─ documents (syllabus / notes text)
                      ├─ recommendations
                      └─ agent_events
```

`blocks` are never mutated once past: a replan marks the old row `superseded` and writes a new one, so
planned-versus-actual history stays intact.

## Planning model in one page

Variables: `x[u,t] ∈ {0,1}` (unit `u` spent on topic `t`), `short[t] ∈ [0, required_units[t]]`.

Hard constraints:
- one topic per unit; per-topic cap at its required hours (no over-study)
- daily cap and per-course daily cap
- no `1-0-1` fragmentation inside a window; no isolated 30-minute block
- `unit.end ≤ topic.deadline`
- prerequisite `p` of `t`: for every pair of days `dp > dt`, `y[t,dt] + y[p,dp] ≤ 1`, and `used[t] ≤ used[p]`
- `Σ x[u,t] + short[t] ≥ required_units[t]`

Objective: `Σ priority(t) · x · earliness + churn_bonus · kept − 5·max_priority · short`.

`priority = weight × urgency × (1 − mastery) × difficulty_factor`.

## Auth

Passwords: PBKDF2-HMAC-SHA256, 260k rounds, per-user salt. Tokens: HS256 JWT carrying `sub`, `tv`
(token version), `exp` (7 days). `POST /api/auth/logout` increments `users.token_version`, so every
token minted earlier fails verification on the next request — a real server-side logout with stateless
tokens. Every data route resolves the student from the token; `student_id` is never accepted from the
client.
