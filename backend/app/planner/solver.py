"""The planning engine: a CP-SAT constraint model over study blocks.

Why a solver instead of a prompt
--------------------------------
An LLM asked to "make a study plan" will happily double-book you, ignore a
prerequisite, or promise 40 hours of work in 12 available hours. The whole
point of this module is that the hard constraints are *actually* enforced and
that infeasibility is reported honestly instead of hidden.

Model
-----
Time is discretised into `slot_minutes` units drawn from the student's
recurring availability (minus blackout dates, minus the past).

  x[u, t] = 1  <=>  unit u is spent on topic t

  hard:
    sum_t x[u, t]            <= 1                 one topic per unit
    sum_u x[u, t]            <= required_units[t]  never over-study a topic
    per-day total            <= daily cap
    per-day per-course total <= course cap
    no 1-0-1 fragmentation inside a window
    unit.end                 <= topic deadline     (nothing after the exam)
    prereq p of t:  y[t,dt] + y[p,dp] <= 1  for every dp > dt
    used[t]                  <= used[p]            (no topic before its prereq)
    sum_u x[u, t] + short[t] >= required_units[t]  (short[t] = slack)

  objective (maximise):
    sum PRI(t) * x[u,t] * earliness(u)  +  churn_bonus * kept(u,t)
      - short_penalty * PRI(t) * short[t]

`short[t] > 0` is how infeasibility surfaces: the solver always returns a
plan, and tells you which topics did not fit. Drop the lowest-priority ones
and the arithmetic is right there in the response.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from ortools.sat.python import cp_model


# --------------------------------------------------------------------------
# inputs / outputs
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class TopicIn:
    id: int
    course_id: int
    name: str
    est_hours: float
    difficulty: int
    weight_pct: float
    prereq_ids: tuple[int, ...]
    priority: float
    deadline: datetime | None


@dataclass(frozen=True)
class Availability:
    weekday: int  # 0 = Monday
    start_min: int
    end_min: int


@dataclass(frozen=True)
class Committed:
    """A block that already exists on the calendar; leaving it alone is cheap."""

    topic_id: int
    start: datetime
    end: datetime


@dataclass
class PlanBlock:
    topic_id: int
    start: datetime
    end: datetime
    kept: bool = False

    @property
    def minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)


@dataclass
class PlanResult:
    status: str = "ok"  # ok | partial | overloaded | empty | infeasible
    blocks: list[PlanBlock] = field(default_factory=list)
    required_hours: float = 0.0
    capacity_hours: float = 0.0
    shortfall: dict[int, float] = field(default_factory=dict)
    objective: float = 0.0
    solver_status: str = ""
    notes: list[str] = field(default_factory=list)

    def hours_by_topic(self) -> dict[int, float]:
        out: dict[int, float] = {}
        for b in self.blocks:
            out[b.topic_id] = out.get(b.topic_id, 0.0) + b.minutes / 60.0
        return {k: round(v, 2) for k, v in out.items()}


@dataclass(frozen=True)
class _Unit:
    start: datetime
    end: datetime
    day: int  # index from horizon start
    group: int  # (day, window) — used for the anti-fragmentation rule


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def build_units(
    availability: list[Availability],
    *,
    now: datetime,
    horizon_days: int,
    slot_minutes: int = 30,
    blackout_dates: set[date] | None = None,
) -> list[_Unit]:
    """Expand recurring weekly availability into concrete slots."""
    blackout_dates = blackout_dates or set()
    units: list[_Unit] = []
    day0 = now.date()
    group = 0
    for d in range(horizon_days):
        day = day0 + timedelta(days=d)
        if day in blackout_dates:
            continue
        for w in sorted(availability, key=lambda a: a.start_min):
            if w.weekday != day.weekday():
                continue
            group += 1
            midnight = datetime.combine(day, time.min)
            cursor = midnight + timedelta(minutes=max(0, w.start_min))
            window_end = midnight + timedelta(minutes=min(24 * 60, w.end_min))
            while cursor + timedelta(minutes=slot_minutes) <= window_end:
                end = cursor + timedelta(minutes=slot_minutes)
                if end > now:  # never plan into the past
                    units.append(_Unit(start=cursor, end=end, day=d, group=group))
                cursor = end
    units.sort(key=lambda u: u.start)
    return units


def _ceil_units(hours: float, slot_minutes: int) -> int:
    if hours <= 0:
        return 0
    return max(1, math.ceil(hours * 60.0 / slot_minutes))


# --------------------------------------------------------------------------
# the model
# --------------------------------------------------------------------------
def plan(
    topics: list[TopicIn],
    availability: list[Availability],
    *,
    now: datetime,
    horizon_days: int = 28,
    slot_minutes: int = 30,
    blackout_dates: set[date] | None = None,
    committed: list[Committed] | None = None,
    max_minutes_per_day: int = 240,
    max_course_minutes_per_day: int = 150,
    churn_bonus: int = 400,
    min_block_slots: int = 2,
    time_limit_s: float = 10.0,
    seed: int = 7,
) -> PlanResult:
    committed = committed or []
    topics = [t for t in topics if t.est_hours > 0]
    result = PlanResult()

    if not topics:
        result.status = "empty"
        result.notes.append("No topics with estimated effort — upload a syllabus first.")
        return result

    units = build_units(
        availability,
        now=now,
        horizon_days=horizon_days,
        slot_minutes=slot_minutes,
        blackout_dates=blackout_dates,
    )
    slot_hours = slot_minutes / 60.0
    result.capacity_hours = round(len(units) * slot_hours, 2)
    result.required_hours = round(sum(t.est_hours for t in topics), 2)

    if not units:
        result.status = "overloaded"
        result.notes.append(
            f"No free slots in the next {horizon_days} days. Add availability windows "
            f"or extend the horizon; {result.required_hours:.1f}h of work is unscheduled."
        )
        return result

    # ---- priority scaling (CP-SAT needs integers) ------------------------
    pri = {t.id: max(1, int(round(t.priority * 1000))) for t in topics}
    max_pri = max(pri.values())
    short_penalty = 5 * max_pri  # covering a required hour beats any scheduling nicety

    # ---- variables ------------------------------------------------------
    model = cp_model.CpModel()
    required_units = {t.id: _ceil_units(t.est_hours, slot_minutes) for t in topics}

    x: dict[tuple[int, int], cp_model.IntVar] = {}
    for ui, u in enumerate(units):
        for t in topics:
            if t.deadline is not None and u.end > t.deadline:
                continue  # nothing scheduled after the exam
            x[(ui, t.id)] = model.NewBoolVar(f"x_{ui}_{t.id}")

    # per-unit: at most one topic
    for ui in range(len(units)):
        vars_here = [x[(ui, t.id)] for t in topics if (ui, t.id) in x]
        if vars_here:
            model.Add(sum(vars_here) <= 1)

    # per-topic cap: never over-study
    for t in topics:
        vars_t = [x[(ui, t.id)] for ui in range(len(units)) if (ui, t.id) in x]
        if vars_t:
            model.Add(sum(vars_t) <= required_units[t.id])

    # per-day caps
    max_units_day = max(1, max_minutes_per_day // slot_minutes)
    max_units_course_day = max(1, max_course_minutes_per_day // slot_minutes)
    days = sorted({u.day for u in units})
    for d in days:
        idx = [ui for ui, u in enumerate(units) if u.day == d]
        all_vars = [x[(ui, t.id)] for ui in idx for t in topics if (ui, t.id) in x]
        if all_vars:
            model.Add(sum(all_vars) <= max_units_day)
        for cid in {t.course_id for t in topics}:
            c_vars = [x[(ui, t.id)] for ui in idx for t in topics if t.course_id == cid and (ui, t.id) in x]
            if c_vars:
                model.Add(sum(c_vars) <= max_units_course_day)

    # anti-fragmentation: forbid a lone 1-0-1 pattern inside a window
    by_group: dict[int, list[int]] = {}
    for ui, u in enumerate(units):
        by_group.setdefault(u.group, []).append(ui)
    for group_idx in by_group.values():
        group_idx.sort()
        for i in range(len(group_idx) - 2):
            a, b, c = group_idx[i], group_idx[i + 1], group_idx[i + 2]
            for t in topics:
                if (a, t.id) in x and (b, t.id) in x and (c, t.id) in x:
                    model.AddBoolOr([x[(a, t.id)].Not(), x[(b, t.id)], x[(c, t.id)].Not()])

    # minimum block length: an isolated 30-minute slot is a block nobody attends
    if min_block_slots >= 2:
        for group_idx in by_group.values():
            if len(group_idx) < 2:
                continue
            for pos, ui in enumerate(group_idx):
                neighbours = []
                if pos > 0:
                    neighbours.append(group_idx[pos - 1])
                if pos + 1 < len(group_idx):
                    neighbours.append(group_idx[pos + 1])
                for t in topics:
                    if (ui, t.id) not in x:
                        continue
                    lits = [x[(ui, t.id)].Not()]
                    lits += [x[(nb, t.id)] for nb in neighbours if (nb, t.id) in x]
                    if len(lits) > 1:
                        model.AddBoolOr(lits)

    # ---- prerequisite ordering (day granularity) ------------------------
    topic_by_id = {t.id: t for t in topics}
    y: dict[tuple[int, int], cp_model.IntVar] = {}
    for t in topics:
        for d in days:
            if any((ui, t.id) in x for ui, u in enumerate(units) if u.day == d):
                y[(t.id, d)] = model.NewBoolVar(f"y_{t.id}_{d}")
                for ui, u in enumerate(units):
                    if u.day == d and (ui, t.id) in x:
                        model.Add(y[(t.id, d)] >= x[(ui, t.id)])

    used: dict[int, cp_model.IntVar] = {}
    for t in topics:
        yds = [y[(t.id, d)] for d in days if (t.id, d) in y]
        used[t.id] = model.NewBoolVar(f"used_{t.id}")
        if yds:
            for v in yds:
                model.Add(used[t.id] >= v)
            model.Add(used[t.id] <= sum(yds))
        else:
            model.Add(used[t.id] == 0)

    for t in topics:
        for pid in t.prereq_ids:
            p = topic_by_id.get(pid)
            if p is None or p.id == t.id:
                continue
            model.Add(used[t.id] <= used[p.id])
            p_days = [d for d in days if (p.id, d) in y]
            t_days = [d for d in days if (t.id, d) in y]
            for dt in t_days:
                for dp in p_days:
                    if dp > dt:
                        model.Add(y[(t.id, dt)] + y[(p.id, dp)] <= 1)

    # ---- slack for uncovered hours --------------------------------------
    short: dict[int, cp_model.IntVar] = {}
    for t in topics:
        short[t.id] = model.NewIntVar(0, required_units[t.id], f"short_{t.id}")
        vars_t = [x[(ui, t.id)] for ui in range(len(units)) if (ui, t.id) in x]
        model.Add(sum(vars_t) + short[t.id] >= required_units[t.id])

    # ---- objective ------------------------------------------------------
    objective_terms = []
    for (ui, t_id), var in x.items():
        u = units[ui]
        earliness = int(round(pri[t_id] * 0.25 * (1.0 - u.day / max(horizon_days, 1))))
        gain = pri[t_id] + earliness
        if any(c.topic_id == t_id and c.start <= u.start < c.end for c in committed):
            gain += churn_bonus  # stability: keeping an existing block is worth something
        objective_terms.append(gain * var)
    for t in topics:
        objective_terms.append(-short_penalty * short[t.id])
    model.Maximize(sum(objective_terms))

    # ---- solve ----------------------------------------------------------
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = seed
    status = solver.Solve(model)
    result.solver_status = solver.StatusName(status)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        result.status = "infeasible"
        result.notes.append(
            "No feasible plan exists with these constraints. Loosen the daily cap, "
            "add availability, or push a deadline."
        )
        return result

    result.objective = round(solver.ObjectiveValue() / 1000.0, 2)

    # ---- read the solution back out -------------------------------------
    assigned: dict[int, list[_Unit]] = {}
    for (ui, t_id), var in x.items():
        if solver.Value(var):
            assigned.setdefault(t_id, []).append(units[ui])

    blocks: list[PlanBlock] = []
    for t_id, us in assigned.items():
        us.sort(key=lambda u: u.start)
        cur_start, cur_end = us[0].start, us[0].end
        for u in us[1:]:
            if u.start == cur_end:
                cur_end = u.end
            else:
                blocks.append(PlanBlock(t_id, cur_start, cur_end))
                cur_start, cur_end = u.start, u.end
        blocks.append(PlanBlock(t_id, cur_start, cur_end))

    for b in blocks:
        b.kept = any(c.topic_id == b.topic_id and c.start < b.end and b.start < c.end for c in committed)
    blocks.sort(key=lambda b: b.start)
    result.blocks = blocks

    for t in topics:
        missing = solver.Value(short[t.id])
        if missing:
            result.shortfall[t.id] = round(missing * slot_hours, 2)

    # ---- honest status + notes ------------------------------------------
    if result.capacity_hours < result.required_hours:
        result.status = "overloaded"
        gap = result.required_hours - result.capacity_hours
        result.notes.append(
            f"Only {result.capacity_hours:.1f}h of free time against "
            f"{result.required_hours:.1f}h of work — {gap:.1f}h short."
        )
        droppable = sorted(
            (t for t in topics if t.id in result.shortfall),
            key=lambda t: t.priority,
        )[:3]
        if droppable:
            names = ", ".join(f"{t.name} ({result.shortfall[t.id]:.1f}h)" for t in droppable)
            result.notes.append(f"Lowest-value topics left uncovered: {names}. Cut scope or add hours.")
    elif result.shortfall:
        result.status = "partial"
        names = ", ".join(
            f"{topic_by_id[tid].name} ({h:.1f}h)" for tid, h in result.shortfall.items() if tid in topic_by_id
        )
        result.notes.append(f"Deadlines leave some topics short: {names}.")
    else:
        result.status = "ok"

    return result
