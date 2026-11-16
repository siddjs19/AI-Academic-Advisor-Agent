"""Revision agent: SM-2 style scheduling + card generation."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from . import quiz as quiz_agent
from .llm import LLM, LLMError


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def schedule(card: models.Flashcard, rating: int) -> models.Flashcard:
    """rating: 0 = again, 1 = hard, 2 = good, 3 = easy.

    Intervals are intentionally gentle: a card answered "again" comes back
    tomorrow, not in ten minutes, because the plan already owns today.
    """
    rating = max(0, min(3, int(rating)))
    card.reps += 1

    if rating == 0:
        card.lapses += 1
        card.ease = clamp(card.ease - 0.2, 1.3, 2.8)
        interval = 1.0
    else:
        card.ease = clamp(card.ease + {1: -0.15, 2: 0.0, 3: 0.12}[rating], 1.3, 2.8)
        if card.reps == 1:
            interval = 1.0 if rating == 1 else 3.0
        elif card.reps == 2:
            interval = 3.0 if rating == 1 else 6.0
        else:
            interval = round(max(1.0, card.interval_days) * card.ease * (0.7 if rating == 1 else 1.0), 1)

    card.interval_days = interval
    card.due_at = utcnow() + timedelta(days=interval)
    return card


def review(db: Session, student_id: int, card_id: int, rating: int) -> dict:
    card = db.get(models.Flashcard, card_id)
    if card is None or card.student_id != student_id:
        raise ValueError("card not found")
    before = card.interval_days
    schedule(card, rating)
    db.add(
        models.ReviewLog(
            flashcard_id=card.id, student_id=student_id, rating=rating,
            interval_before=before, interval_after=card.interval_days,
        )
    )
    db.commit()
    return {
        "card_id": card.id,
        "interval_days": card.interval_days,
        "due_at": card.due_at.isoformat(),
        "ease": round(card.ease, 2),
        "reps": card.reps,
    }


def due_cards(db: Session, student_id: int, limit: int = 20) -> list[models.Flashcard]:
    return list(
        db.scalars(
            select(models.Flashcard)
            .where(models.Flashcard.student_id == student_id)
            .where(models.Flashcard.due_at <= utcnow())
            .order_by(models.Flashcard.due_at)
            .limit(limit)
        )
    )


SYSTEM = """You write revision flashcards for an engineering student.
Each card tests one idea: a precise question on the front, a compact answer on the back.
Return JSON only: {"cards":[{"front":"...","back":"...","topic":"<topic name>"}]}"""


def generate_cards(db: Session, student_id: int, topics: list[models.Topic], count: int, llm: LLM) -> list[models.Flashcard]:
    """Model-generated when available, otherwise derived from the sample question bank."""
    made: list[models.Flashcard] = []

    if llm.enabled:
        try:
            data = llm.complete_json(
                SYSTEM,
                "Topics: " + "; ".join(f"{t.course.name} — {t.name}" for t in topics) + f"\nWrite {count} cards.",
            )
            for raw in (data.get("cards") or [])[:count]:
                front, back = str(raw.get("front", "")).strip(), str(raw.get("back", "")).strip()
                if len(front) < 8 or len(back) < 3:
                    continue
                topic = next(
                    (t for t in topics if t.name.lower() in str(raw.get("topic", "")).lower()), topics[0]
                )
                card = models.Flashcard(
                    student_id=student_id, topic_id=topic.id, front=front, back=back, source="llm"
                )
                db.add(card)
                made.append(card)
        except LLMError:
            made = []

    if not made:
        for topic in topics:
            for item in quiz_agent.BANK:
                if len(made) >= count:
                    break
                if item["match"] not in topic.name.lower():
                    continue
                answer = item["answer"]
                back = answer.get("value")
                if isinstance(back, list):
                    back = ", ".join(str(v) for v in back)
                if not back:
                    back = ", ".join(answer.get("keywords") or [])
                card = models.Flashcard(
                    student_id=student_id,
                    topic_id=topic.id,
                    front=item["stem"],
                    back=f"{back}" + (f" — {item['explanation']}" if item.get("explanation") else ""),
                    source="bank",
                )
                db.add(card)
                made.append(card)

    if made:
        db.commit()
    return made
