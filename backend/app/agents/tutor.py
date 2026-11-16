"""Teaching agent (explanations, Socratic follow-ups) and viva/communication agent.

Explanations need a model. The viva does not: with no model it runs as a
structured oral exam scored on concept coverage, and says so on every turn.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import memory, models
from . import quiz as quiz_agent
from .llm import LLM, LLMError

LEVELS = {"beginner": "assume no prior knowledge, use one concrete analogy",
          "intermediate": "assume the course basics, focus on mechanism and trade-offs",
          "advanced": "be precise, include complexity, edge cases and formal definitions"}

TUTOR_SYSTEM = """You are a patient engineering tutor for an Indian undergraduate.
- Answer the actual question first, in 2-4 short paragraphs.
- Use one worked example or analogy when it helps.
- End with a single Socratic question that checks understanding.
- Never invent facts about the student's marks or deadlines.
Plain prose, no markdown headers."""


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --------------------------------------------------------------------------- notes retrieval
def notes_context(db: Session, student_id: int, topic: models.Topic, question: str, limit: int = 2) -> str:
    """Naive keyword retrieval over uploaded notes — good enough, and honest about it."""
    docs = list(db.scalars(select(models.Document).where(models.Document.student_id == student_id)))
    if not docs:
        return ""
    terms = {w for w in re.findall(r"[a-z]{4,}", question.lower())}
    terms |= {w for w in re.findall(r"[a-z]{4,}", topic.name.lower())}
    scored = []
    for doc in docs:
        text = doc.text or ""
        score = sum(text.lower().count(term) for term in terms)
        if score:
            scored.append((score, doc, text))
    if not scored:
        return ""
    scored.sort(key=lambda r: r[0], reverse=True)
    _, doc, text = scored[0]
    low = text.lower()
    anchor = next((low.find(t) for t in terms if low.find(t) > 0), 0)
    excerpt = text[max(0, anchor - 300) : anchor + 700].strip()
    return f"From your uploaded notes ({doc.filename}):\n{excerpt}"


# --------------------------------------------------------------------------- explanation
def explain(db: Session, student_id: int, *, topic: models.Topic | None, question: str, level: str, llm: LLM) -> dict:
    mastery = None
    evidence = None
    if topic is not None:
        mastery, evidence = memory.effective_mastery(db, student_id, topic)

    context = notes_context(db, student_id, topic, question) if topic else ""

    if not llm.enabled:
        return {
            "agent": "teaching",
            "answer": (
                "I can't generate an explanation without a model configured — set LLM_PROVIDER and "
                "LLM_API_KEY and I'll teach this properly.\n\n"
                "What works right now: I can build a study plan that schedules this topic, generate "
                "practice questions from the sample bank, and run a viva on it. "
                + ("You also have notes uploaded for this course — I can quote the relevant part if you "
                   "ask a narrower question." if context else "")
            ),
            "llm_required": True,
            "context_used": bool(context),
            "mastery": mastery,
            "evidence": evidence,
        }

    prompt = [
        f"Topic: {topic.name if topic else 'general'} ({topic.course.name if topic else 'coursework'})",
        f"Student mastery estimate: {mastery:.2f} (0-1, from {evidence['attempts'] if evidence else 0} graded answers)",
        f"Level: {level} — {LEVELS.get(level, LEVELS['intermediate'])}",
        f"Question: {question}",
    ]
    if context:
        prompt.append(context)
    answer = llm.complete_text(TUTOR_SYSTEM, "\n\n".join(prompt))
    return {
        "agent": "teaching",
        "answer": answer,
        "llm_required": False,
        "context_used": bool(context),
        "mastery": mastery,
        "evidence": evidence,
    }


# --------------------------------------------------------------------------- viva
VIVA_SYSTEM = """You are conducting a college viva. Ask exactly one question at a time,
wait for the answer, then ask a follow-up that probes the weakest part of it.
Keep questions under 30 words. After the final turn, give a short verdict."""

RUBRIC = {
    "concepts": 0.4,
    "structure": 0.2,
    "completeness": 0.2,
    "clarity": 0.2,
}


def _expected_concepts(topic: models.Topic) -> list[str]:
    """Keywords the answer should touch — taken from the sample bank when it exists."""
    concepts: list[str] = []
    for item in quiz_agent.BANK:
        if item["match"] in topic.name.lower():
            answer = item["answer"]
            concepts += [str(v) for v in (answer.get("keywords") or [])]
            if answer.get("value"):
                concepts.append(str(answer["value"]))
    if not concepts:
        concepts = [w for w in re.findall(r"[a-z]{4,}", topic.name.lower())]
    return concepts[:6]


def _score_answer(answer: str, concepts: list[str]) -> dict:
    words = set(re.findall(r"[a-z0-9]+", answer.lower()))
    hits = [c for c in concepts if set(re.findall(r"[a-z0-9]+", c.lower())).issubset(words)]
    coverage = len(hits) / len(concepts) if concepts else 0.0

    sentences = [s for s in re.split(r"[.!?]+", answer) if s.strip()]
    structure = 1.0 if len(sentences) >= 2 else 0.5
    completeness = min(1.0, len(words) / 45)
    clarity = 1.0 if len(words) <= 120 else 0.6

    score = (
        RUBRIC["concepts"] * coverage
        + RUBRIC["structure"] * structure
        + RUBRIC["completeness"] * completeness
        + RUBRIC["clarity"] * clarity
    )
    missing = [c for c in concepts if c not in hits]
    notes = []
    if missing:
        notes.append(f"You didn't mention: {', '.join(missing[:3])}.")
    if structure < 1:
        notes.append("Answer in at least two sentences — a definition then a consequence.")
    if len(words) < 12:
        notes.append("Too brief for a viva; examiners expect elaboration.")
    return {"score": round(score, 2), "coverage": round(coverage, 2), "missing": missing, "notes": notes}


def start_viva(db: Session, student_id: int, *, topic: models.Topic, kind: str, llm: LLM) -> models.VivaSession:
    questions = [item for item in quiz_agent.BANK if item["match"] in topic.name.lower()]
    first = (
        f"Let's start with the basics — explain {topic.name.lower()} in your own words, "
        "and give one example where it matters."
    )
    if questions:
        first = questions[0]["stem"]

    if llm.enabled:
        try:
            first = llm.complete_text(
                VIVA_SYSTEM,
                f"Topic: {topic.name} ({topic.course.name}). Kind: {kind}. Ask your first question only.",
            )
        except LLMError:
            pass

    session = models.VivaSession(
        student_id=student_id,
        course_id=topic.course_id,
        topic_id=topic.id,
        kind=kind,
        status="active",
        transcript=[{"role": "examiner", "text": first, "at": utcnow().isoformat()}],
        evaluator="llm" if llm.enabled else "rule",
    )
    db.add(session)
    db.commit()
    return session


def answer_viva(db: Session, student_id: int, session_id: int, answer: str, llm: LLM) -> dict:
    session = db.get(models.VivaSession, session_id)
    if session is None or session.student_id != student_id:
        raise ValueError("viva session not found")
    topic = db.get(models.Topic, session.topic_id) if session.topic_id else None

    transcript = list(session.transcript or [])
    transcript.append({"role": "student", "text": answer, "at": utcnow().isoformat()})

    concepts = _expected_concepts(topic) if topic else []
    scored = _score_answer(answer, concepts)
    turn_feedback = " ".join(scored["notes"]) or "Solid answer."

    asked = sum(1 for t in transcript if t["role"] == "examiner")
    finished = asked >= 4

    next_question = ""
    if not finished:
        if llm.enabled and topic is not None:
            try:
                next_question = llm.complete_text(
                    VIVA_SYSTEM,
                    f"Topic: {topic.name}. Transcript so far:\n"
                    + "\n".join(f"{t['role']}: {t['text']}" for t in transcript[-4:])
                    + "\nAsk one follow-up question only.",
                )
            except LLMError:
                next_question = ""
        if not next_question:
            pool = [q["stem"] for q in quiz_agent.BANK if topic and q["match"] in topic.name.lower()]
            next_question = pool[asked % len(pool)] if pool else f"Go deeper: what are the trade-offs of {topic.name if topic else 'this'}?"
        transcript.append({"role": "examiner", "text": next_question, "at": utcnow().isoformat()})

    scores = [t for t in transcript if t["role"] == "student"]
    avg = scored["score"]
    session.transcript = transcript
    if finished:
        session.status = "finished"
        session.score = round(avg * 100, 1)
        session.feedback = (
            f"Concept coverage {round(scored['coverage'] * 100)}% across the last answer. "
            + ("Strong on definitions; " if scored["coverage"] > 0.6 else "Definitions are thin; ")
            + ("add an example in every answer to lift structure." if scored["structure"] < 1 else "structure was good.")
        )
        if topic is not None:
            memory.record_evidence(db, student_id, topic.id, avg >= 0.6, "intermediate")
    db.commit()

    return {
        "session_id": session.id,
        "turn": asked,
        "finished": finished,
        "feedback": turn_feedback,
        "score": scored["score"],
        "next_question": next_question,
        "report": session.feedback if finished else "",
        "evaluator": session.evaluator,
    }
