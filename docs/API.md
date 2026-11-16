# API

All routes are under `/api` and require `Authorization: Bearer <jwt>` except `auth/*` and `health`.

## Auth & profile

| Method | Path | Body / notes |
|---|---|---|
| GET | `/auth/demo` | demo credentials (only when seeding is on) |
| POST | `/auth/register` | `{email, password, name}` → `{token, student}` |
| POST | `/auth/login` | `{email, password}` → `{token, student}` |
| POST | `/auth/logout` | bumps `token_version`, revoking all tokens |
| GET | `/auth/me` | current student |
| PUT | `/profile` | partial update of profile fields |
| POST | `/onboarding` | `{profile, windows[]}` — marks `onboarded` |
| GET | `/availability` | weekly windows |

## Academics

| Method | Path | Notes |
|---|---|---|
| POST | `/syllabus/parse` | multipart: `file` (PDF) **or** `text` → draft, writes nothing |
| POST | `/syllabus/confirm` | `{draft}` → creates course, topics, assessments, then replans |
| GET | `/courses` | courses with topics, mastery and evidence |
| DELETE | `/courses/{id}` | cascade delete |
| POST | `/courses/{id}/topics` | manual topic entry |
| POST | `/marks` | `{assessment_id, score, max_score}` |

## Planning

| Method | Path | Notes |
|---|---|---|
| GET | `/plan` | latest run + blocks |
| POST | `/plan/build` | solve from scratch |
| POST | `/plan/replan` | close out misses, re-solve, report churn |
| GET | `/drift` | missed/completed hours, adherence, next block |
| POST | `/blocks/{id}/log?done=true&minutes=30` | mark done or skipped |

## Assessment

| Method | Path | Notes |
|---|---|---|
| POST | `/practice/generate` | `{topic_ids[], mode, difficulty, count}` → questions **without answers** |
| POST | `/practice/{id}/submit` | `{responses: {"<question_id>": {"value": ...}}}` → graded results |
| GET | `/practice/history` | past attempts |

## Teaching, viva, revision

| Method | Path | Notes |
|---|---|---|
| POST | `/tutor/ask` | `{question, topic_id?, level}` |
| GET | `/tutor/history` | |
| POST | `/viva/start` | `{topic_id, kind}` → first question |
| POST | `/viva/{id}/answer` | `{answer}` → feedback, next question, or final report |
| GET | `/viva/history` | |
| GET | `/revision/due` | cards due now |
| POST | `/revision/review` | `{card_id, rating 0-3}` |
| POST | `/revision/generate` | `{topic_ids[], count}` |

## Insights & workflow

| Method | Path | Notes |
|---|---|---|
| GET | `/analytics` | series, courses, study, revision, weak topics, repeated mistakes |
| GET | `/dashboard` | everything the dashboard needs in one call (also runs the proactive rules) |
| GET | `/recommendations` | evaluates rules, returns ranked active recommendations |
| POST | `/recommendations/{id}/act` | `{status: "accepted" \| "dismissed"}` |
| GET/POST | `/assignments` | list / create (auto-decomposed into tasks) |
| POST | `/assignments/{id}/tasks/{task_id}/toggle` | |
| DELETE | `/assignments/{id}` | |
| POST | `/advisor/chat` | `{message}` → `{answer, agent, intent, actions, context}` |
| GET | `/advisor/history` | |
| GET | `/health` | provider name, whether generation is enabled |

## Errors

`401` unauthenticated or revoked token · `404` not found **or not yours** · `409` conflict (duplicate
email, no questions available for a topic) · `422` validation.
