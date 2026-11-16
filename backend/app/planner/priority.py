"""Topic priority + mastery estimation.

This is deliberately plain arithmetic, not a model call. It runs on every
solver invocation, so it must be cheap, deterministic and inspectable.

    priority = weight * urgency * (1 - mastery) * difficulty
"""
from __future__ import annotations

from datetime import datetime

PRIOR_Mastery = 0.35  # neutral prior when we have no marks for a topic


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def mastery_from_marks(ratios: list[float], prior: float = PRIOR_Mastery, k: float = 2.0) -> float:
    """Blend observed score ratios towards a prior.

    `k` is a pseudo-count: with one mark you barely move off the prior, with
    five consistent marks the observed value dominates. Marks are too sparse
    to justify anything fancier.
    """
    if not ratios:
        return prior
    obs = sum(ratios) / len(ratios)
    n = len(ratios)
    return clamp((obs * n + prior * k) / (n + k), 0.0, 1.0)


def days_until(when: datetime | None, now: datetime) -> float | None:
    if when is None:
        return None
    return max(0.0, (when - now).total_seconds() / 86400.0)


def urgency(when: datetime | None, now: datetime, horizon_days: int = 28) -> float:
    d = days_until(when, now)
    if d is None:
        return 1.0
    return 1.0 + 1.5 * clamp((horizon_days - d) / max(horizon_days, 1), 0.0, 1.0)


def difficulty_factor(difficulty: int) -> float:
    return 1.0 + 0.15 * (clamp(difficulty, 1, 5) - 1)


def topic_priority(
    *,
    weight_pct: float,
    mastery: float,
    deadline: datetime | None,
    now: datetime,
    difficulty: int,
    horizon_days: int = 28,
) -> float:
    weight_norm = weight_pct / 100.0 if weight_pct > 0 else 0.10  # uniform fallback
    score = (
        weight_norm
        * 10.0
        * urgency(deadline, now, horizon_days)
        * (1.0 - clamp(mastery, 0.0, 1.0))
        * difficulty_factor(difficulty)
    )
    return round(score, 4)


def estimate_hours(lecture_hours: float, difficulty: int, self_study_ratio: float = 1.5) -> float:
    """Crude but honest effort heuristic: self-study ≈ 1.5x lecture time,
    nudged by difficulty. Replace with per-student calibration later."""
    return round(lecture_hours * self_study_ratio * (0.8 + 0.1 * clamp(difficulty, 1, 5)), 2)
