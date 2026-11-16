"""Revision: SM-2 behaviour — intervals must grow on success and reset on failure."""
from datetime import datetime, timedelta

from app import models
from app.agents import revision as revision_agent


def _card(**kwargs):
    defaults = dict(id=1, student_id=1, topic_id=1, front="Q", back="A", ease=2.5, interval_days=0.0, reps=0, lapses=0)
    defaults.update(kwargs)
    return models.Flashcard(**defaults)


def test_again_resets_to_one_day_and_drops_ease():
    card = _card(reps=4, interval_days=12.0, ease=2.5)
    revision_agent.schedule(card, 0)
    assert card.interval_days == 1.0
    assert card.lapses == 1
    assert card.ease < 2.5


def test_easy_grows_faster_than_hard():
    hard = _card(reps=3, interval_days=6.0)
    easy = _card(reps=3, interval_days=6.0)
    revision_agent.schedule(hard, 1)
    revision_agent.schedule(easy, 3)
    assert easy.interval_days > hard.interval_days


def test_first_review_is_short_then_expands():
    card = _card(reps=0)
    revision_agent.schedule(card, 2)
    first = card.interval_days
    revision_agent.schedule(card, 2)
    second = card.interval_days
    revision_agent.schedule(card, 2)
    assert first < second < card.interval_days


def test_ease_never_leaves_safe_bounds():
    card = _card(reps=5, interval_days=10.0, ease=1.3)
    for _ in range(6):
        revision_agent.schedule(card, 0)
    assert card.ease >= 1.3

    card = _card(reps=5, interval_days=10.0, ease=2.8)
    for _ in range(6):
        revision_agent.schedule(card, 3)
    assert card.ease <= 2.8


def test_due_date_moves_into_the_future():
    card = _card(reps=2, interval_days=3.0)
    revision_agent.schedule(card, 2)
    assert card.due_at > datetime.now() + timedelta(hours=12)
