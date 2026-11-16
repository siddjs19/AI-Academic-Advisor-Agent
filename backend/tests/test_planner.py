"""Planner: the properties that make a schedule legal, not merely plausible."""
from datetime import datetime, timedelta

import pytest

from app.planner.solver import Availability, Committed, TopicIn, plan

NOW = datetime(2026, 11, 16, 8, 0)  # Monday


def evenings():
    return [Availability(weekday=d, start_min=18 * 60, end_min=22 * 60) for d in range(5)]


def topic(tid, hours, *, course=1, pri=1.0, deadline=None, prereqs=()):
    return TopicIn(
        id=tid, course_id=course, name=f"T{tid}", est_hours=hours, difficulty=3,
        weight_pct=25.0, prereq_ids=tuple(prereqs), priority=pri, deadline=deadline,
    )


def test_no_overlaps_and_effort_met():
    res = plan([topic(1, 6.0, pri=1.2), topic(2, 4.0, course=2, pri=0.8)], evenings(), now=NOW, horizon_days=28)
    assert res.status == "ok"
    blocks = sorted(res.blocks, key=lambda b: b.start)
    for a, b in zip(blocks, blocks[1:]):
        assert a.end <= b.start
    hours = res.hours_by_topic()
    assert hours[1] == pytest.approx(6.0)
    assert hours[2] == pytest.approx(4.0)


def test_daily_and_per_course_caps():
    res = plan(
        [topic(1, 20.0, course=1, pri=2.0), topic(2, 20.0, course=2, pri=1.0)],
        evenings(), now=NOW, horizon_days=28, max_minutes_per_day=180, max_course_minutes_per_day=90,
    )
    per_day, per_course = {}, {}
    for b in res.blocks:
        per_day[b.start.date()] = per_day.get(b.start.date(), 0) + b.minutes
        key = (b.start.date(), b.topic_id)
        per_course[key] = per_course.get(key, 0) + b.minutes
    assert max(per_day.values()) <= 180
    assert max(per_course.values()) <= 90


def test_nothing_after_the_deadline():
    deadline = NOW + timedelta(days=3)
    res = plan([topic(1, 4.0, deadline=deadline)], evenings(), now=NOW, horizon_days=14)
    assert res.blocks and all(b.end <= deadline for b in res.blocks)


def test_prerequisite_ordering():
    res = plan([topic(1, 3.0, pri=0.5), topic(2, 3.0, pri=2.0, prereqs=(1,))], evenings(), now=NOW, horizon_days=21)
    days_1 = {b.start.date() for b in res.blocks if b.topic_id == 1}
    days_2 = {b.start.date() for b in res.blocks if b.topic_id == 2}
    assert max(days_1) <= min(days_2)


def test_overload_is_reported_with_the_weakest_topic_dropped():
    res = plan(
        [topic(1, 10.0, pri=2.0), topic(2, 10.0, pri=1.5), topic(3, 10.0, pri=0.3)],
        evenings(), now=NOW, horizon_days=7,
    )
    assert res.status == "overloaded"
    assert res.capacity_hours < res.required_hours
    assert max(res.shortfall, key=res.shortfall.get) == 3


def test_replan_keeps_most_of_the_calendar():
    topics = [topic(1, 6.0), topic(2, 6.0, course=2)]
    first = plan(topics, evenings(), now=NOW, horizon_days=21)
    committed = [Committed(b.topic_id, b.start, b.end) for b in first.blocks]
    again = plan(topics, evenings(), now=NOW, horizon_days=21, committed=committed)
    kept = [b for b in again.blocks if b.kept]
    assert len(kept) >= len(again.blocks) * 0.5


def test_no_availability_is_explained_not_crashed():
    res = plan([topic(1, 4.0)], [], now=NOW, horizon_days=14)
    assert res.status == "overloaded"
    assert "No free slots" in res.notes[0]
