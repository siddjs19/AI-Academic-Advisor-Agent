"""Planner service: DB <-> CP-SAT solver, drift detection, replanning.

The solver (`solver.py`) is unchanged from the earlier build: 30-minute units,
hard constraints on caps, overlaps, deadlines, prerequisite order and minimum
block length, plus slack variables so an impossible workload is reported rather
than hidden.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import memory, models
from ..config import settings
from . import priority, solver


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --------------------------------------------------------------------------- reads
def topic_deadline(db: Session, topic: models.Topic, now: datetime) -> datetime | None:
    for a in db.scalars(
        select(models.Assessment)
        .where(models.Assessment.course_id == topic.course_id)
        .where(models.Assessment.due_at >= now)
        .order_by(models.Assessment.due_at)
    ):
        if topic.id in (a.covers or []) or not a.covers:
            return a.due_at
    course = db.get(models.Course, topic.course_id)
    if course and course.exam_at and course.exam_at >= now:
        return course.exam_at
    return None


def build_inputs(db: Session, student_id: int, now: datetime) -> tuple[list[solver.TopicIn], dict[int, models.Topic]]:
    topics = list(
        db.scalars(
            select(models.Topic)
            .join(models.Course, models.Course.id == models.Topic.course_id)
            .where(models.Course.student_id == student_id)
        )
    )
    inputs: list[solver.TopicIn] = []
    by_id: dict[int, models.Topic] = {}
    for t in topics:
        mastery, _ = memory.effective_mastery(db, student_id, t)
        deadline = topic_deadline(db, t, now)
        inputs.append(
            solver.TopicIn(
                id=t.id,
                course_id=t.course_id,
                name=t.name,
                est_hours=t.est_hours,
                difficulty=t.difficulty,
                weight_pct=t.weight_pct,
                prereq_ids=tuple(t.prereq_ids or ()),
                priority=priority.topic_priority(
                    weight_pct=t.weight_pct,
                    mastery=mastery,
                    deadline=deadline,
                    now=now,
                    difficulty=t.difficulty,
                    horizon_days=settings.horizon_days,
                ),
                deadline=deadline,
            )
        )
        by_id[t.id] = t
    return inputs, by_id


def build_availability(db: Session, student_id: int) -> tuple[list[solver.Availability], set[date]]:
    windows = [
        solver.Availability(w.weekday, w.start_min, w.end_min)
        for w in db.scalars(select(models.Availability).where(models.Availability.student_id == student_id))
    ]
    blackouts = {
        b.on_date.date() for b in db.scalars(select(models.Blackout).where(models.Blackout.student_id == student_id))
    }
    return windows, blackouts


def current_blocks(db: Session, student_id: int, now: datetime) -> list[models.Block]:
    return list(
        db.scalars(
            select(models.Block)
            .where(models.Block.student_id == student_id)
            .where(models.Block.status == "planned")
            .where(models.Block.end >= now)
            .order_by(models.Block.start)
        )
    )


# --------------------------------------------------------------------------- writes
def run_planner(
    db: Session,
    student_id: int,
    *,
    now: datetime | None = None,
    trigger: str = "initial",
    horizon_days: int | None = None,
) -> tuple[models.PlanRun, list[models.Block], solver.PlanResult]:
    now = now or utcnow()
    horizon = horizon_days or settings.horizon_days
    student = db.get(models.Student, student_id)
    if student is None:
        raise ValueError("unknown student")

    topic_inputs, topic_by_id = build_inputs(db, student_id, now)
    windows, blackouts = build_availability(db, student_id)
    existing = current_blocks(db, student_id, now)
    committed = [solver.Committed(b.topic_id, b.start, b.end) for b in existing]

    result = solver.plan(
        topic_inputs,
        windows,
        now=now,
        horizon_days=horizon,
        slot_minutes=settings.slot_minutes,
        blackout_dates=blackouts,
        committed=committed,
        max_minutes_per_day=student.daily_minutes or settings.max_minutes_per_day,
        max_course_minutes_per_day=settings.max_course_minutes_per_day,
        churn_bonus=settings.churn_bonus,
        min_block_slots=settings.min_block_slots,
        time_limit_s=settings.solver_time_limit_s,
    )

    run = models.PlanRun(
        student_id=student_id,
        trigger=trigger,
        status=result.status,
        objective=result.objective,
        required_hours=result.required_hours,
        capacity_hours=result.capacity_hours,
        shortfall={str(k): v for k, v in result.shortfall.items()},
        notes=result.notes,
    )
    db.add(run)
    db.flush()

    for b in existing:
        b.status = "superseded"

    new_blocks: list[models.Block] = []
    for pb in result.blocks:
        topic = topic_by_id.get(pb.topic_id)
        block = models.Block(
            plan_run_id=run.id,
            student_id=student_id,
            topic_id=pb.topic_id,
            start=pb.start,
            end=pb.end,
            kind="study",
            status="planned",
            label=f"{topic.course.name} · {topic.name}" if topic else "Study",
        )
        db.add(block)
        new_blocks.append(block)

    db.commit()
    return run, new_blocks, result


def detect_drift(db: Session, student_id: int, now: datetime | None = None) -> dict:
    now = now or utcnow()
    missed = list(
        db.scalars(
            select(models.Block)
            .where(models.Block.student_id == student_id)
            .where(models.Block.status == "planned")
            .where(models.Block.end < now)
        )
    )
    done = list(
        db.scalars(
            select(models.Block)
            .where(models.Block.student_id == student_id)
            .where(models.Block.status == "done")
            .where(models.Block.end >= now - timedelta(days=7))
        )
    )
    planned_hours = sum((b.end - b.start).total_seconds() / 3600 for b in missed + done)
    done_hours = sum((b.actual_minutes or 0) / 60 for b in done)
    upcoming = current_blocks(db, student_id, now)
    return {
        "missed_blocks": len(missed),
        "missed_hours": round(sum((b.end - b.start).total_seconds() / 3600 for b in missed), 2),
        "completed_blocks": len(done),
        "completed_hours": round(done_hours, 2),
        "adherence_pct": round(100 * done_hours / planned_hours, 1) if planned_hours else None,
        "upcoming_blocks": len(upcoming),
        "next_block": (
            {"id": upcoming[0].id, "label": upcoming[0].label, "start": upcoming[0].start.isoformat()}
            if upcoming
            else None
        ),
    }


def replan(db: Session, student_id: int, *, now: datetime | None = None, trigger: str = "drift") -> dict:
    now = now or utcnow()
    missed = list(
        db.scalars(
            select(models.Block)
            .where(models.Block.student_id == student_id)
            .where(models.Block.status == "planned")
            .where(models.Block.end < now)
        )
    )
    for b in missed:
        b.status = "missed"
    db.commit()

    before = {(b.topic_id, b.start) for b in current_blocks(db, student_id, now)}
    run, new_blocks, result = run_planner(db, student_id, now=now, trigger=trigger)
    after = {(b.topic_id, b.start) for b in new_blocks}
    added = [b for b in new_blocks if (b.topic_id, b.start) not in before]
    kept = [b for b in new_blocks if (b.topic_id, b.start) in before]

    return {
        "plan_run_id": run.id,
        "status": result.status,
        "missed_marked": len(missed),
        "blocks_kept": len(kept),
        "blocks_added": len(added),
        "blocks_dropped": len(before - after),
        "churn_pct": round(100 * len(added) / max(len(new_blocks), 1), 1),
        "notes": result.notes,
    }


def plan_payload(db: Session, student_id: int) -> dict:
    run = db.scalars(
        select(models.PlanRun)
        .where(models.PlanRun.student_id == student_id)
        .order_by(models.PlanRun.id.desc())
        .limit(1)
    ).first()
    if run is None:
        return {"plan": None, "blocks": []}
    blocks = list(db.scalars(select(models.Block).where(models.Block.plan_run_id == run.id).order_by(models.Block.start)))
    return {
        "plan": {
            "plan_run_id": run.id,
            "created_at": run.created_at.isoformat(),
            "trigger": run.trigger,
            "status": run.status,
            "objective": run.objective,
            "required_hours": run.required_hours,
            "capacity_hours": run.capacity_hours,
            "shortfall": run.shortfall,
            "notes": run.notes,
        },
        "blocks": [
            {
                "id": b.id,
                "topic_id": b.topic_id,
                "label": b.label,
                "kind": b.kind,
                "start": b.start.isoformat(),
                "end": b.end.isoformat(),
                "status": b.status,
                "minutes": int((b.end - b.start).total_seconds() // 60),
            }
            for b in blocks
        ],
    }
