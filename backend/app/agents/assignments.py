"""Assignment agent: decompose a brief into tasks and feed the planner."""
from __future__ import annotations

from sqlalchemy.orm import Session

from .. import models
from .llm import LLM, LLMError

TEMPLATES = {
    "assignment": [
        ("Re-read the question and mark the deliverables", 20),
        ("Collect sources / references", 40),
        ("Draft the solution", 90),
        ("Check against the rubric", 30),
        ("Finalise formatting and submit", 20),
    ],
    "project": [
        ("Write the problem statement and scope", 40),
        ("Design the approach and split the work", 45),
        ("Implement the core module", 120),
        ("Test and fix edge cases", 60),
        ("Prepare the report and demo", 60),
    ],
    "lab": [
        ("Read the lab manual and note the procedure", 20),
        ("Complete the pre-lab calculations", 30),
        ("Run the experiment / implement the code", 90),
        ("Record observations and analyse results", 40),
        ("Write the lab file", 45),
    ],
    "presentation": [
        ("Outline the narrative", 30),
        ("Build slides", 90),
        ("Rehearse once, timed", 30),
        ("Prepare for likely questions", 30),
    ],
}

SYSTEM = """Break an academic brief into 4-6 concrete tasks a student can tick off.
Return JSON only: {"tasks":[{"title":"...","est_minutes":45}]}"""


def decompose(db: Session, assignment: models.Assignment, llm: LLM) -> list[models.AssignmentTask]:
    items: list[tuple[str, int]] = []

    if llm.enabled and assignment.notes.strip():
        try:
            data = llm.complete_json(
                SYSTEM,
                f"Type: {assignment.kind}\nTitle: {assignment.title}\nBrief: {assignment.notes[:2000]}\n"
                f"Due in days: {(assignment.due_at - assignment.created_at).days if assignment.due_at else 'unknown'}",
            )
            items = [(str(t["title"])[:180], int(t.get("est_minutes", 45))) for t in data.get("tasks", [])][:6]
        except (LLMError, KeyError, ValueError, TypeError):
            items = []

    if not items:
        items = TEMPLATES.get(assignment.kind, TEMPLATES["assignment"])

    tasks = []
    for order, (title, minutes) in enumerate(items):
        task = models.AssignmentTask(
            assignment_id=assignment.id, title=title, est_minutes=minutes, order=order
        )
        db.add(task)
        tasks.append(task)
    db.commit()
    return tasks


def progress(assignment: models.Assignment) -> dict:
    tasks = assignment.tasks or []
    done = sum(1 for t in tasks if t.done)
    return {
        "tasks": len(tasks),
        "done": done,
        "pct": round(100 * done / len(tasks), 0) if tasks else 0,
        "minutes_left": sum(t.est_minutes for t in tasks if not t.done),
    }
