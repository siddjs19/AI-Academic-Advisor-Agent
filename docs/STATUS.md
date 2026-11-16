# Implementation status

Written to be accurate rather than flattering. Anything marked partial says exactly where it stops.

## Works end-to-end (verified in a browser and by tests)

| Flow | State |
|---|---|
| Register → onboarding → dashboard | ✅ |
| Upload/paste syllabus → review with confidence → import → replan | ✅ |
| Plan build / replan / mark blocks done | ✅ (CP-SAT, 35 tests) |
| Practice set → answer → graded results → mastery update | ✅ sample bank; ✅ LLM when configured |
| Revision queue → reveal → rate → SM-2 reschedule | ✅ |
| Mock viva → turns → score + report | ✅ rule-scored; LLM when configured |
| Analytics: accuracy series, mastery bars, weak topics, repeated mistakes | ✅ |
| Assignments: create → decomposed tasks → tick off | ✅ templates; LLM when configured |
| Proactive recommendations → accept (acts) / dismiss | ✅ 7 rules |
| Advisor chat with intent routing + agent labels | ✅ rule routing; LLM loop when configured |
| Login / logout (revokes all tokens) / per-account isolation | ✅ |

## Partial — and where it stops

* **Teaching agent** needs a model. Offline it returns an explicit "no model configured" message plus
  what it *can* do. Notes retrieval is keyword-based, not embeddings.
* **Question generation** offline uses a 22-question sample bank covering the demo topics. For a topic
  outside the bank with no model, the API returns `409` and says why — it does not invent questions.
* **Descriptive grading** without a rubric or a model returns `graded_by: "pending"` and zero marks
  rather than a fabricated score.
* **Viva scoring** offline is keyword coverage + structure heuristics, not judgement of correctness.
  It says so on screen.
* **Proactive recommendations** are evaluated on dashboard load and on submission — there is no
  background scheduler, so nothing arrives while the app is closed.

## Not implemented

* Voice input/output (browser speech APIs) — the brief marks this as optional.
* Vector search / embeddings over notes and textbooks.
* Email or push notifications for recommendations.
* Password reset by email, 2FA, login rate limiting.
* Data export / account deletion endpoints (DPDP hygiene).
* Mock exams with a timer enforced server-side (`time_limit_min` is stored but not enforced).
* Mobile app.

## Deviations from the reference stack, and why

| Brief | Built | Why |
|---|---|---|
| Node/Express backend + Python AI service | one FastAPI service | The Node layer would only proxy to Python. One process is fewer moving parts, one auth boundary, and one thing to deploy on a free tier. The API is versioned under `/api`, so a split stays possible. |
| MongoDB | SQLite / Postgres | Marks, deadlines and mastery are strongly relational; joins and constraints are doing real work here. Mongo would push that into application code. |
| LangGraph | custom supervisor | The graph is one router plus seven handlers with no cycles or human-in-the-loop interrupts. A hand-written dispatcher is ~200 lines and debuggable; LangGraph adds a dependency without changing behaviour at this size. |
| Recharts | ✅ used | |

## Known rough edges

* Recharts makes the JS bundle ~650 KB (~183 KB gzipped). Route-level code splitting would fix it.
* `weak_topics` surfaces never-assessed topics at the 0.35 prior, which can look like "you're weak at
  everything". It is honest but noisy on a fresh account.
* The planner plans one horizon (28 days) at a time; there is no long-range semester view.
* SQLite has no concurrent writers — fine locally, not for production.
* The demo seed creates data relative to "today"; if the DB is old, dates drift into the past. Delete
  `preppilot.db` to reseed.
