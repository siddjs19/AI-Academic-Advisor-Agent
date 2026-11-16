"""Student memory: mastery from evidence, weakness, readiness, analytics.

Rules enforced here:
  * mastery never jumps on a single answer (EMA with a small alpha)
  * marks and quiz evidence are blended, and both are stored, not inferred
  * "confident" requires at least three data points
  * everything is recomputed from rows, so it is inspectable and correctable
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models

PRIOR = 0.35
ALPHA = 0.18
CONFIDENT_AFTER = 3


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


# --------------------------------------------------------------------------- mastery
def get_mastery_row(db: Session, student_id: int, topic_id: int) -> models.TopicMastery:
    row = db.scalars(
        select(models.TopicMastery).where(
            models.TopicMastery.student_id == student_id, models.TopicMastery.topic_id == topic_id
        )
    ).first()
    if row is None:
        row = models.TopicMastery(student_id=student_id, topic_id=topic_id, mastery=PRIOR)
        db.add(row)
        db.flush()
    return row


def record_evidence(
    db: Session, student_id: int, topic_id: int, correct: bool, difficulty: str = "intermediate"
) -> models.TopicMastery:
    """One graded answer is one weak data point, not a verdict."""
    row = get_mastery_row(db, student_id, topic_id)
    weight = {"beginner": 0.7, "intermediate": 1.0, "advanced": 1.35}.get(difficulty, 1.0)
    alpha = ALPHA * weight
    target = 1.0 if correct else 0.0
    row.mastery = clamp(row.mastery + alpha * (target - row.mastery))
    row.attempts += 1
    row.correct += 1 if correct else 0
    row.last_seen = utcnow()
    row.updated_at = utcnow()
    db.flush()
    return row


def marks_ratio(db: Session, topic: models.Topic) -> float | None:
    ratios: list[float] = []
    for a in db.scalars(select(models.Assessment).where(models.Assessment.course_id == topic.course_id)):
        if topic.id not in (a.covers or []):
            continue
        for m in a.marks:
            if m.max_score:
                ratios.append(clamp(m.score / m.max_score))
    return sum(ratios) / len(ratios) if ratios else None


def effective_mastery(db: Session, student_id: int, topic: models.Topic) -> tuple[float, dict]:
    """Blend quiz evidence with marks. Quiz evidence dominates once it exists."""
    row = get_mastery_row(db, student_id, topic.id)
    observed = marks_ratio(db, topic)
    if observed is None or row.attempts >= 2:
        value = row.mastery
    else:
        value = (row.mastery * 2 + observed) / 3
    return round(clamp(value), 3), {
        "attempts": row.attempts,
        "correct": row.correct,
        "last_seen": row.last_seen.isoformat() if row.last_seen else None,
        "confident": row.attempts >= CONFIDENT_AFTER,
        "marks_ratio": round(observed, 3) if observed is not None else None,
    }


# --------------------------------------------------------------------------- weakness
def weak_topics(db: Session, student_id: int, limit: int = 6) -> list[dict]:
    out = []
    for topic in db.scalars(
        select(models.Topic).join(models.Course, models.Course.id == models.Topic.course_id).where(
            models.Course.student_id == student_id
        )
    ):
        value, evidence = effective_mastery(db, student_id, topic)
        if value >= 0.6:
            continue
        out.append(
            {
                "topic_id": topic.id,
                "topic": topic.name,
                "course": topic.course.name,
                "course_code": topic.course.code,
                "mastery": value,
                "weight_pct": topic.weight_pct,
                "evidence": evidence,
                "risk": round((1 - value) * (topic.weight_pct or 10), 2),
            }
        )
    out.sort(key=lambda r: r["risk"], reverse=True)
    return out[:limit]


def repeated_mistakes(db: Session, student_id: int, limit: int = 5) -> list[dict]:
    """Topics where the same question type was missed more than once."""
    rows = db.execute(
        select(models.Answer, models.Question)
        .join(models.Question, models.Question.id == models.Answer.question_id)
        .join(models.Attempt, models.Attempt.id == models.Answer.attempt_id)
        .where(models.Attempt.student_id == student_id, models.Answer.correct.is_(False))
    ).all()
    tally: dict[int, dict] = {}
    for answer, question in rows:
        if question.topic_id is None:
            continue
        entry = tally.setdefault(
            question.topic_id, {"topic_id": question.topic_id, "misses": 0, "questions": []}
        )
        entry["misses"] += 1
        if len(entry["questions"]) < 3:
            entry["questions"].append(question.stem[:140])
    repeats = [v for v in tally.values() if v["misses"] >= 2]
    repeats.sort(key=lambda r: r["misses"], reverse=True)
    for r in repeats[:limit]:
        topic = db.get(models.Topic, r["topic_id"])
        r["topic"] = topic.name if topic else "—"
        r["course"] = topic.course.name if topic else "—"
    return repeats[:limit]


# --------------------------------------------------------------------------- analytics
def analytics(db: Session, student_id: int, days: int = 30) -> dict:
    now = utcnow()
    since = now - timedelta(days=days)

    attempts = list(
        db.scalars(
            select(models.Attempt)
            .where(models.Attempt.student_id == student_id)
            .where(models.Attempt.submitted_at.is_not(None))
            .order_by(models.Attempt.submitted_at)
        )
    )
    series = [
        {
            "at": a.submitted_at.isoformat(),
            "accuracy": round(100 * a.score / a.max_score, 1) if a.max_score else 0.0,
            "quiz_set_id": a.quiz_set_id,
        }
        for a in attempts
    ]

    courses = []
    for course in db.scalars(select(models.Course).where(models.Course.student_id == student_id)):
        topics = list(db.scalars(select(models.Topic).where(models.Topic.course_id == course.id)))
        if not topics:
            continue
        values = [effective_mastery(db, student_id, t)[0] for t in topics]
        evidence = [effective_mastery(db, student_id, t)[1] for t in topics]
        courses.append(
            {
                "course_id": course.id,
                "course": course.name,
                "code": course.code,
                "mastery": round(100 * sum(values) / len(values), 1),
                "topics": len(topics),
                "assessed_topics": sum(1 for e in evidence if e["attempts"] > 0),
                "hours_left": round(sum(t.est_hours for t in topics), 1),
            }
        )

    blocks = list(
        db.scalars(
            select(models.Block)
            .where(models.Block.student_id == student_id)
            .where(models.Block.start >= since)
        )
    )
    done = [b for b in blocks if b.status == "done"]
    missed = [b for b in blocks if b.status == "missed"]
    elapsed = [b for b in blocks if b.status in ("done", "missed") or (b.status == "planned" and b.end < now)]
    planned_hours = sum((b.end - b.start).total_seconds() / 3600 for b in elapsed)
    done_hours = sum((b.actual_minutes or 0) / 60 for b in done)

    reviews = list(
        db.scalars(
            select(models.ReviewLog).where(models.ReviewLog.student_id == student_id).where(
                models.ReviewLog.created_at >= since
            )
        )
    )
    due_cards = db.scalars(
        select(models.Flashcard)
        .where(models.Flashcard.student_id == student_id)
        .where(models.Flashcard.due_at <= now)
    ).all()

    return {
        "window_days": days,
        "attempts": len(attempts),
        "accuracy_series": series[-30:],
        "courses": courses,
        "study": {
            "blocks": len(blocks),
            "done": len(done),
            "missed": len(missed),
            "planned_hours": round(planned_hours, 1),
            "completed_hours": round(done_hours, 1),
            "adherence_pct": round(100 * done_hours / planned_hours, 1) if planned_hours else None,
        },
        "revision": {
            "reviews": len(reviews),
            "due_now": len(due_cards),
            "retention_pct": round(100 * sum(1 for r in reviews if r.rating >= 2) / len(reviews), 1)
            if reviews
            else None,
        },
        "weak_topics": weak_topics(db, student_id, 5),
        "repeated_mistakes": repeated_mistakes(db, student_id, 3),
    }


# --------------------------------------------------------------------------- readiness
def exam_readiness(db: Session, student_id: int) -> list[dict]:
    """Per-course readiness = weighted mastery against days left."""
    now = utcnow()
    out = []
    for course in db.scalars(select(models.Course).where(models.Course.student_id == student_id)):
        topics = list(db.scalars(select(models.Topic).where(models.Topic.course_id == course.id)))
        if not topics:
            continue
        total_weight = sum(t.weight_pct for t in topics) or len(topics)
        covered = 0.0
        for t in topics:
            value, _ = effective_mastery(db, student_id, t)
            covered += (t.weight_pct or 1) * value
        readiness = round(100 * covered / total_weight, 1)

        next_exam = db.scalars(
            select(models.Assessment)
            .where(models.Assessment.course_id == course.id)
            .where(models.Assessment.due_at >= now)
            .order_by(models.Assessment.due_at)
            .limit(1)
        ).first()
        days_left = (next_exam.due_at - now).days if next_exam else None
        out.append(
            {
                "course_id": course.id,
                "course": course.name,
                "code": course.code,
                "readiness": readiness,
                "days_left": days_left,
                "exam_title": (next_exam.title or next_exam.kind) if next_exam else None,
                "exam_at": next_exam.due_at.isoformat() if next_exam else None,
            }
        )
    out.sort(key=lambda r: (r["days_left"] if r["days_left"] is not None else 999))
    return out
