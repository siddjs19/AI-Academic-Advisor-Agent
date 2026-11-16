"""Syllabus commit — the single write path from an extraction draft into the DB."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from . import models
from .ingestion.extract import _norm_date


def _to_dt(value: Any) -> datetime | None:
    return value if isinstance(value, datetime) else _norm_date(value)


def _assign_coverage(topic_ids: list[int], assessments: list[dict[str, Any]]) -> None:
    """Cumulative split: a midterm covers the first slice, the end-semester everything."""
    if not topic_ids:
        return
    if len(assessments) == 1:
        assessments[0]["covers"] = list(topic_ids)
        return
    n = len(topic_ids)
    for i, a in enumerate(assessments):
        upto = max(1, round(n * (i + 1) / len(assessments)))
        a["covers"] = topic_ids[:upto] if a.get("kind") != "assignment" else []


def commit_syllabus(db: Session, student_id: int, draft: dict[str, Any]) -> dict[str, Any]:
    course_data = draft.get("course") or {}
    colour = len(db.query(models.Course).filter(models.Course.student_id == student_id).all()) % 6
    course = models.Course(
        student_id=student_id,
        name=str(course_data.get("name") or "Untitled course")[:160],
        code=str(course_data.get("code") or "")[:40],
        credits=float(course_data.get("credits") or 3.0),
        exam_at=_to_dt(course_data.get("exam_at")),
        colour=colour,
    )
    db.add(course)
    db.flush()

    topics: list[models.Topic] = []
    for t in draft.get("topics") or []:
        topic = models.Topic(
            course_id=course.id,
            name=str(t.get("name"))[:200],
            unit=str(t.get("unit") or "")[:80],
            est_hours=float(t.get("est_hours") or 2.0),
            difficulty=int(t.get("difficulty") or 3),
            weight_pct=float(t.get("weight_pct") or 0.0),
            prereq_ids=[],
            confidence=float(t.get("confidence") or 1.0),
            needs_review=bool(t.get("needs_review")),
        )
        db.add(topic)
        topics.append(topic)
    db.flush()

    assessments = [dict(a) for a in (draft.get("assessments") or [])]
    assessments = [a for a in assessments if _to_dt(a.get("due_at")) is not None]
    assessments.sort(key=lambda a: _to_dt(a["due_at"]))
    _assign_coverage([t.id for t in topics], assessments)

    for a in assessments:
        db.add(
            models.Assessment(
                course_id=course.id,
                kind=str(a.get("kind") or "exam")[:40],
                title=str(a.get("title") or "Assessment")[:160],
                due_at=_to_dt(a["due_at"]),
                weight_pct=float(a.get("weight_pct") or 0.0),
                covers=a.get("covers") or [],
            )
        )

    db.commit()
    return {
        "course_id": course.id,
        "course": course.name,
        "topics": len(topics),
        "assessments": len(assessments),
        "needs_review": sum(1 for t in topics if t.needs_review),
    }
