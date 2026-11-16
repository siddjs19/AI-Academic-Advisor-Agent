"""Proactive engine.

Rules, not vibes: each recommendation is generated from a query over real rows,
carries the evidence that triggered it, and is deduped by key so the same advice
does not stack up. The system prepares the activity but never silently rewrites
a schedule or a record — accepting a recommendation is the confirmation.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import memory, models
from .planner import service as planner


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _exists(db: Session, student_id: int, key: str) -> bool:
    return (
        db.scalars(
            select(models.Recommendation)
            .where(models.Recommendation.student_id == student_id)
            .where(models.Recommendation.dedupe_key == key)
            .where(models.Recommendation.status != "dismissed")
            .limit(1)
        ).first()
        is not None
    )


def _add(db: Session, student_id: int, *, kind: str, title: str, body: str, severity: str,
         action: dict, key: str) -> models.Recommendation | None:
    if _exists(db, student_id, key):
        return None
    rec = models.Recommendation(
        student_id=student_id, kind=kind, title=title, body=body,
        severity=severity, action=action, dedupe_key=key,
    )
    db.add(rec)
    return rec


def evaluate(db: Session, student_id: int) -> list[models.Recommendation]:
    """Run every rule. Cheap enough to call on dashboard load."""
    now = utcnow()
    created: list[models.Recommendation] = []

    # 1. exam approaching and readiness low
    for row in memory.exam_readiness(db, student_id):
        if row["days_left"] is None or row["days_left"] > 10:
            continue
        if row["readiness"] >= 65:
            continue
        severity = "critical" if row["days_left"] <= 4 else "warn"
        rec = _add(
            db, student_id,
            kind="exam_risk",
            title=f"{row['course']} is in {row['days_left']} days at {row['readiness']}% readiness",
            body=(
                f"{row['exam_title']} covers material you haven't been assessed on. "
                "A focused plan for the remaining days beats a full revision sweep."
            ),
            severity=severity,
            action={"type": "build_plan", "params": {"course_id": row["course_id"]}},
            key=f"exam_risk:{row['course_id']}:{row['days_left'] // 3}",
        )
        if rec:
            created.append(rec)

    # 2. repeated mistakes on one topic
    for mistake in memory.repeated_mistakes(db, student_id, 3):
        rec = _add(
            db, student_id,
            kind="weak_topic",
            title=f"Repeated misses on {mistake['topic']}",
            body=(
                f"{mistake['misses']} wrong answers on this topic. "
                f"Latest: {mistake['questions'][0][:120] if mistake['questions'] else '—'}"
            ),
            severity="warn",
            action={"type": "start_quiz", "params": {"topic_id": mistake["topic_id"]}},
            key=f"repeated:{mistake['topic_id']}:{mistake['misses'] // 2}",
        )
        if rec:
            created.append(rec)

    # 3. revision overdue
    due = len(
        db.scalars(
            select(models.Flashcard)
            .where(models.Flashcard.student_id == student_id)
            .where(models.Flashcard.due_at <= now)
        ).all()
    )
    if due >= 5:
        rec = _add(
            db, student_id,
            kind="revision_due",
            title=f"{due} flashcards are due",
            body="Spaced repetition only works if the cards come back on time — this is a 10 minute job.",
            severity="info",
            action={"type": "open_revision", "params": {}},
            key=f"revision_due:{due // 5}",
        )
        if rec:
            created.append(rec)

    # 4. assignment deadline close
    for assignment in db.scalars(
        select(models.Assignment)
        .where(models.Assignment.student_id == student_id)
        .where(models.Assignment.status == "open")
        .where(models.Assignment.due_at.is_not(None))
        .where(models.Assignment.due_at <= now + timedelta(days=4))
    ):
        days = max(0, (assignment.due_at - now).days)
        rec = _add(
            db, student_id,
            kind="assignment",
            title=f"{assignment.title} is due in {days} day{'s' if days != 1 else ''}",
            body="Break it into tasks now, or it becomes a single impossible evening later.",
            severity="warn" if days <= 2 else "info",
            action={"type": "open_assignment", "params": {"assignment_id": assignment.id}},
            key=f"assignment:{assignment.id}:{days // 2}",
        )
        if rec:
            created.append(rec)

    # 5. mastered a unit → time to check it
    for weak in memory.weak_topics(db, student_id, 12)[:2]:
        if weak["mastery"] >= 0.5 or weak["evidence"]["attempts"] >= 1:
            continue
        if weak["evidence"]["attempts"] > 0:
            continue
        rec = _add(
            db, student_id,
            kind="assess_ready",
            title=f"{weak['topic']} has never been assessed",
            body=f"You have no evidence for this topic and it carries {weak['weight_pct']}% weight.",
            severity="info",
            action={"type": "start_quiz", "params": {"topic_id": weak["topic_id"]}},
            key=f"never_assessed:{weak['topic_id']}",
        )
        if rec:
            created.append(rec)

    # 6. no practice at all in a week
    last_attempt = db.scalars(
        select(models.Attempt)
        .where(models.Attempt.student_id == student_id)
        .where(models.Attempt.submitted_at.is_not(None))
        .order_by(models.Attempt.submitted_at.desc())
        .limit(1)
    ).first()
    if last_attempt is None or (now - last_attempt.submitted_at) > timedelta(days=7):
        rec = _add(
            db, student_id,
            kind="practice_stale",
            title="No practice attempts in the last week",
            body="Mastery estimates go stale without evidence. A five-question set is enough to refresh them.",
            severity="info",
            action={"type": "open_practice", "params": {}},
            key="practice_stale:weekly",
        )
        if rec:
            created.append(rec)

    # 7. missed sessions piling up
    drift = planner.detect_drift(db, student_id, now)
    if drift["missed_blocks"] >= 3:
        rec = _add(
            db, student_id,
            kind="drift",
            title=f"{drift['missed_blocks']} sessions missed",
            body="The plan is still achievable, but it needs a replan rather than more optimism.",
            severity="warn",
            action={"type": "replan", "params": {}},
            key=f"drift:{drift['missed_blocks'] // 3}",
        )
        if rec:
            created.append(rec)

    db.commit()
    for rec in created:
        db.refresh(rec)
    return created


def active(db: Session, student_id: int, limit: int = 6) -> list[dict]:
    rows = list(
        db.scalars(
            select(models.Recommendation)
            .where(models.Recommendation.student_id == student_id)
            .where(models.Recommendation.status == "new")
            .order_by(models.Recommendation.id.desc())
            .limit(50)
        )
    )
    # rank first, then cut — otherwise a burst of low-value notes hides the urgent ones
    order = {"critical": 0, "warn": 1, "info": 2}
    rows.sort(key=lambda r: (order.get(r.severity, 3), -r.id))
    rows = rows[:limit]
    return [
        {
            "id": r.id,
            "kind": r.kind,
            "title": r.title,
            "body": r.body,
            "severity": r.severity,
            "action": r.action,
            "at": r.created_at.isoformat(),
        }
        for r in rows
    ]


def act(db: Session, student_id: int, rec_id: int, status: str) -> dict:
    rec = db.get(models.Recommendation, rec_id)
    if rec is None or rec.student_id != student_id:
        raise ValueError("recommendation not found")
    if status not in ("accepted", "dismissed"):
        raise ValueError("bad status")
    rec.status = status
    db.commit()
    return {"id": rec.id, "status": rec.status, "action": rec.action}
