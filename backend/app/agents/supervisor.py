"""Supervisor agent.

One model, many workflows. The supervisor classifies intent, assembles the
student's context, delegates to a specialist, validates the result and returns
it. Every delegation is written to `agent_events`, so the UI can show which
specialist answered and why.

Routing is deterministic first: an obvious request never burns a model call.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import memory, models
from ..planner import service as planner
from . import assignments as assignments_agent
from . import quiz as quiz_agent
from . import revision as revision_agent
from . import tutor as tutor_agent
from .llm import LLM, LLMError


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --------------------------------------------------------------------------- context
def student_context(db: Session, student_id: int) -> dict:
    now = utcnow()
    drift = planner.detect_drift(db, student_id, now)
    readiness = memory.exam_readiness(db, student_id)
    weak = memory.weak_topics(db, student_id, 4)
    upcoming = [
        {
            "course": a.course.name,
            "title": a.title or a.kind,
            "due_at": a.due_at.isoformat(),
            "days_left": max(0, (a.due_at - now).days),
        }
        for a in db.scalars(
            select(models.Assessment)
            .join(models.Course, models.Course.id == models.Assessment.course_id)
            .where(models.Course.student_id == student_id)
            .where(models.Assessment.due_at >= now)
            .order_by(models.Assessment.due_at)
            .limit(5)
        )
    ]
    open_assignments = [
        {"title": a.title, "due_at": a.due_at.isoformat() if a.due_at else None}
        for a in db.scalars(
            select(models.Assignment)
            .where(models.Assignment.student_id == student_id)
            .where(models.Assignment.status == "open")
            .order_by(models.Assignment.due_at)
            .limit(5)
        )
    ]
    return {
        "readiness": readiness,
        "weak_topics": weak,
        "deadlines": upcoming,
        "assignments": open_assignments,
        "drift": drift,
        "due_cards": len(revision_agent.due_cards(db, student_id, 50)),
        "next_block": drift.get("next_block"),
    }


def resolve_topic(db: Session, student_id: int, message: str) -> models.Topic | None:
    """Find the topic the student is talking about, longest name match first."""
    topics = list(
        db.scalars(
            select(models.Topic)
            .join(models.Course, models.Course.id == models.Topic.course_id)
            .where(models.Course.student_id == student_id)
        )
    )
    low = message.lower()
    best: tuple[int, models.Topic] | None = None
    for topic in topics:
        name = topic.name.lower()
        if name in low:
            score = len(name)
        else:
            words = [w for w in re.findall(r"[a-z]{4,}", name) if w in low]
            score = sum(len(w) for w in words)
        if score and (best is None or score > best[0]):
            best = (score, topic)
    return best[1] if best else None


# --------------------------------------------------------------------------- routing
def classify(message: str) -> str:
    low = message.lower()
    rules = [
        ("viva", r"\b(viva|mock interview|interview|gd|group discussion|presentation practice)\b"),
        ("quiz", r"\b(quiz|test me|practice questions|mcq|exam questions|assess me)\b"),
        ("revision", r"\b(revis|flashcard|spaced|forget|memoris|memoriz)\b"),
        ("replan", r"\b(missed|behind|fell off|reschedul|replan|didn't do|did not do)\b"),
        ("plan", r"\b(plan|schedule|timetable|organis|organiz|workload)\b"),
        ("explain", r"\b(explain|what is|what are|how does|why does|teach|understand|doubt|derive)\b"),
        ("analytics", r"\b(progress|how am i|performance|analytics|weak|accuracy|readiness)\b"),
        ("assignment", r"\b(assignment|project|deadline submission|lab record)\b"),
    ]
    for intent, pattern in rules:
        if re.search(pattern, low):
            return intent
    return "status"


# --------------------------------------------------------------------------- dispatch
def _log(db: Session, student_id: int, agent: str, action: str, payload: dict) -> None:
    db.add(models.AgentEvent(student_id=student_id, agent=agent, action=action, payload=payload))


def handle(db: Session, student_id: int, message: str, llm: LLM) -> dict:
    intent = classify(message)
    ctx = student_context(db, student_id)
    topic = resolve_topic(db, student_id, message)
    result: dict = {"intent": intent, "agent": "supervisor", "answer": "", "data": {}, "actions": []}

    if intent == "plan":
        run, blocks, plan_result = planner.run_planner(db, student_id, now=utcnow(), trigger="agent")
        first = blocks[0] if blocks else None
        result.update(
            agent="planning",
            answer=(
                f"Planned {plan_result.required_hours}h of work into {plan_result.capacity_hours}h of free time — "
                f"{len(blocks)} blocks."
                + (f" First up: {first.label} at {first.start:%a %H:%M}." if first else "")
                + ((" " + " ".join(plan_result.notes)) if plan_result.notes else "")
            ),
            data={"plan_run_id": run.id, "blocks": len(blocks), "status": plan_result.status},
            actions=["plan_built"],
        )

    elif intent == "replan":
        diff = planner.replan(db, student_id, now=utcnow(), trigger="agent:chat")
        result.update(
            agent="planning",
            answer=(
                f"Replanned: {diff['blocks_kept']} blocks kept, {diff['blocks_added']} moved, "
                f"{diff['missed_marked']} marked missed ({diff['churn_pct']}% churn)."
                + ((" " + " ".join(diff["notes"])) if diff["notes"] else "")
            ),
            data=diff,
            actions=["plan_rebuilt"],
        )

    elif intent == "explain":
        level = "advanced" if re.search(r"\b(derive|proof|formal|advanced)\b", message.lower()) else "intermediate"
        explained = tutor_agent.explain(
            db, student_id, topic=topic, question=message, level=level, llm=llm
        )
        result.update(agent="teaching", answer=explained["answer"], data=explained)

    elif intent == "quiz":
        if topic is None:
            weak = ctx["weak_topics"]
            result.update(
                agent="assessment",
                answer=(
                    "Tell me which topic to test you on."
                    + (f" Weakest right now: {', '.join(w['topic'] for w in weak[:3])}." if weak else "")
                ),
                data={"needs_topic": True},
            )
        else:
            result.update(
                agent="assessment",
                answer=f"Ready to test you on {topic.name}. Open Practice to take it — 5 questions, "
                f"{'sample bank' if not llm.enabled else 'generated'}.",
                data={"topic_id": topic.id, "topic": topic.name},
                actions=["open_quiz"],
            )

    elif intent == "viva":
        result.update(
            agent="communication",
            answer=(
                f"Let's do a mock viva on {topic.name if topic else 'a subject of your choice'}. "
                "I'll ask one question at a time and score concept coverage, structure and clarity."
            ),
            data={"topic_id": topic.id if topic else None},
            actions=["open_viva"],
        )

    elif intent == "revision":
        due = ctx["due_cards"]
        result.update(
            agent="revision",
            answer=(
                f"You have {due} card{'s' if due != 1 else ''} due for review."
                if due
                else "Nothing is due right now. I can generate cards for your weakest topics."
            ),
            data={"due": due},
            actions=["open_revision"],
        )

    elif intent == "analytics":
        readiness = ctx["readiness"][:3]
        weak = ctx["weak_topics"][:3]
        result.update(
            agent="analytics",
            answer=(
                "Readiness: "
                + "; ".join(f"{r['course']} {r['readiness']}%{' (' + str(r['days_left']) + 'd)' if r['days_left'] is not None else ''}" for r in readiness)
                + (". Weakest: " + ", ".join(f"{w['topic']} ({round(w['mastery'] * 100)}%)" for w in weak) if weak else ".")
            ),
            data=ctx,
        )

    elif intent == "assignment":
        open_items = ctx["assignments"]
        result.update(
            agent="assignments",
            answer=(
                f"{len(open_items)} open item(s): " + "; ".join(a["title"] for a in open_items)
                if open_items
                else "No open assignments. Add one and I'll break it into tasks."
            ),
            data={"assignments": open_items},
        )

    else:
        readiness = ctx["readiness"]
        weakest = min(readiness, key=lambda r: r["readiness"]) if readiness else None
        result.update(
            agent="supervisor",
            answer=(
                (f"Next block: {ctx['next_block']['label']}." if ctx["next_block"] else "No plan yet — ask me to build one.")
                + (f" Biggest risk: {weakest['course']} at {weakest['readiness']}% readiness"
                   f"{' with ' + str(weakest['days_left']) + ' days left' if weakest['days_left'] is not None else ''}."
                   if weakest else "")
                + (f" {ctx['due_cards']} revision cards are due." if ctx["due_cards"] else "")
            ),
            data=ctx,
        )

    _log(db, student_id, result["agent"], intent, {"intent": intent, "llm": llm.name})
    db.commit()
    result["context"] = {
        "weak_topics": [w["topic"] for w in ctx["weak_topics"]],
        "due_cards": ctx["due_cards"],
        "llm_enabled": llm.enabled,
    }
    return result


# --------------------------------------------------------------------------- conversation
def conversation(db: Session, student_id: int, kind: str = "advisor") -> models.Conversation:
    convo = db.scalars(
        select(models.Conversation)
        .where(models.Conversation.student_id == student_id, models.Conversation.kind == kind)
        .order_by(models.Conversation.id.desc())
        .limit(1)
    ).first()
    if convo is None:
        convo = models.Conversation(student_id=student_id, kind=kind, title=kind.title())
        db.add(convo)
        db.flush()
    return convo


def chat(db: Session, student_id: int, message: str, llm: LLM, kind: str = "advisor") -> dict:
    convo = conversation(db, student_id, kind)
    db.add(models.Message(conversation_id=convo.id, role="user", content=message))
    db.flush()

    result = handle(db, student_id, message, llm)

    db.add(
        models.Message(
            conversation_id=convo.id,
            role="assistant",
            content=result["answer"],
            agent=result["agent"],
            meta={"intent": result["intent"], "actions": result["actions"]},
        )
    )
    db.commit()
    result["conversation_id"] = convo.id
    return result


def history(db: Session, student_id: int, kind: str = "advisor", limit: int = 40) -> list[dict]:
    convo = conversation(db, student_id, kind)
    rows = list(
        db.scalars(
            select(models.Message)
            .where(models.Message.conversation_id == convo.id)
            .order_by(models.Message.id.desc())
            .limit(limit)
        )
    )
    rows.reverse()
    return [
        {
            "role": m.role,
            "content": m.content,
            "agent": m.agent,
            "at": m.created_at.isoformat(),
        }
        for m in rows
    ]
