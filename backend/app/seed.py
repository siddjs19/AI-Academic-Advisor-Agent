"""Demo data: one student, three courses, a real plan, some history.

Everything here is optional demonstration data — the app works the same for a
student who registers and uploads their own syllabus.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import auth, memory, models
from .agents import quiz as quiz_agent
from .agents import revision as revision_agent
from .config import settings
from .planner import service as planner


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


COURSES = [
    ("Data Structures & Algorithms", "CS301", 4.0, [
        ("Arrays, hashing and complexity", 6.0, 2, 20.0, []),
        ("Trees and traversals", 8.0, 4, 25.0, [0]),
        ("Graphs: BFS, DFS, shortest paths", 9.0, 5, 30.0, [1]),
        ("Dynamic programming", 8.0, 5, 25.0, [1]),
    ], 12, 34),
    ("Database Management Systems", "CS302", 3.0, [
        ("ER modelling and relational algebra", 4.0, 2, 20.0, []),
        ("Normalisation and functional dependencies", 5.0, 4, 25.0, [0]),
        ("SQL, joins and query plans", 5.0, 3, 25.0, [1]),
        ("Transactions and concurrency control", 6.0, 4, 30.0, [2]),
    ], 14, 32),
    ("Operating Systems", "CS303", 4.0, [
        ("Processes, threads and scheduling", 5.0, 3, 25.0, []),
        ("Synchronisation and deadlocks", 6.0, 5, 25.0, [0]),
        ("Memory management and paging", 6.0, 4, 25.0, [0]),
        ("File systems and I/O", 4.0, 3, 25.0, [2]),
    ], 9, 36),
]


def seed(db: Session) -> int:
    """Idempotent: returns the demo student id."""
    existing = db.scalars(select(models.Student).order_by(models.Student.id)).first()
    if existing:
        return existing.id

    now = _now()
    user = models.User(
        email=settings.demo_email, password_hash=auth.hash_password(settings.demo_password), is_demo=True
    )
    db.add(user)
    db.flush()

    student = models.Student(
        user_id=user.id,
        name="Sidd",
        college="VJTI, Mumbai",
        programme="B.E. Computer Engineering",
        semester=5,
        target_grade="8.5 CGPA",
        daily_minutes=240,
        onboarded=True,
        preferences={"explanation_level": "intermediate", "reminders": True},
    )
    db.add(student)
    db.flush()

    for weekday in range(5):
        db.add(models.Availability(student_id=student.id, weekday=weekday, start_min=18 * 60, end_min=22 * 60))
    db.add(models.Availability(student_id=student.id, weekday=5, start_min=9 * 60, end_min=13 * 60))
    db.add(models.Blackout(student_id=student.id, on_date=now + timedelta(days=6), reason="college fest"))

    for colour, (name, code, credits, topics, mid_days, end_days) in enumerate(COURSES):
        course = models.Course(
            student_id=student.id, name=name, code=code, credits=credits,
            exam_at=now + timedelta(days=end_days), colour=colour,
        )
        db.add(course)
        db.flush()

        created: list[models.Topic] = []
        for topic_name, hours, difficulty, weight, prereqs in topics:
            topic = models.Topic(
                course_id=course.id, name=topic_name, est_hours=hours, difficulty=difficulty,
                weight_pct=weight, prereq_ids=[created[i].id for i in prereqs],
            )
            db.add(topic)
            created.append(topic)
        db.flush()

        quiz = models.Assessment(
            course_id=course.id, kind="quiz", title=f"{code} quiz 1",
            due_at=now - timedelta(days=9), weight_pct=20.0, covers=[created[0].id],
        )
        db.add(quiz)
        db.flush()
        db.add(models.Mark(assessment_id=quiz.id, score={"CS301": 78, "CS302": 61, "CS303": 55}[code], max_score=100))

        db.add(models.Assessment(
            course_id=course.id, kind="midterm", title=f"{code} mid-semester",
            due_at=now + timedelta(days=mid_days, hours=2), weight_pct=30.0,
            covers=[t.id for t in created[:2]],
        ))
        db.add(models.Assessment(
            course_id=course.id, kind="exam", title=f"{code} end-semester",
            due_at=now + timedelta(days=end_days, hours=2), weight_pct=50.0,
            covers=[t.id for t in created],
        ))
    db.commit()

    # --- one past practice attempt, so mastery and "repeated mistakes" have evidence
    os_course = db.scalars(select(models.Course).where(models.Course.code == "CS303")).first()
    os_topics = list(db.scalars(select(models.Topic).where(models.Topic.course_id == os_course.id)))
    sync_topic = next(t for t in os_topics if "Synchronisation" in t.name)
    questions = [q for q in quiz_agent.BANK if q["match"] in sync_topic.name.lower()]

    quiz_set = models.QuizSet(
        student_id=student.id, title="CS303 · Synchronisation", mode="topic",
        difficulty="intermediate", topic_ids=[sync_topic.id], source="bank",
    )
    db.add(quiz_set)
    db.flush()
    q_rows = []
    for item in questions:
        q = models.Question(
            quiz_set_id=quiz_set.id, topic_id=sync_topic.id, qtype=item["qtype"], stem=item["stem"],
            options=item["options"], answer=item["answer"], explanation=item["explanation"],
            difficulty=item["difficulty"], marks=1.0,
        )
        db.add(q)
        q_rows.append(q)
    db.flush()

    attempt = models.Attempt(
        quiz_set_id=quiz_set.id, student_id=student.id, submitted_at=now - timedelta(days=2),
        max_score=float(len(q_rows)),
    )
    db.add(attempt)
    db.flush()
    for i, q in enumerate(q_rows):
        wrong = i % 2 == 0  # miss every other one, twice over
        correct_value = q.answer.get("value")
        response = {"value": "mutual exclusion" if wrong else correct_value}
        result = quiz_agent.grade(q, response)
        db.add(models.Answer(
            attempt_id=attempt.id, question_id=q.id, response=response,
            correct=result["correct"], awarded=result["awarded"],
            feedback=result["feedback"], graded_by=result["graded_by"],
        ))
        attempt.score += result["awarded"]
        memory.record_evidence(db, student.id, sync_topic.id, bool(result["correct"]), q.difficulty)
    db.commit()

    # --- flashcards, some already due
    memory_topic = next(t for t in os_topics if "Memory management" in t.name)
    revision_agent.generate_cards(db, student.id, [sync_topic, memory_topic], 6, llm=_NoLLM())
    cards = list(db.scalars(select(models.Flashcard).where(models.Flashcard.student_id == student.id)))
    for i, card in enumerate(cards):
        card.due_at = now - timedelta(days=1) if i % 2 == 0 else now + timedelta(days=2)
        card.interval_days = 1.0 if i % 2 == 0 else 4.0
    db.commit()

    # --- an open assignment with tasks
    dbms = db.scalars(select(models.Course).where(models.Course.code == "CS302")).first()
    assignment = models.Assignment(
        student_id=student.id, course_id=dbms.id, title="DBMS lab file — transactions unit",
        kind="lab", due_at=now + timedelta(days=3), weight_pct=10.0,
        notes="Submit ER diagram, normalisation steps and a transaction trace for the given schema.",
    )
    db.add(assignment)
    db.flush()
    for order, (title, minutes) in enumerate([
        ("Read the lab manual and note the procedure", 20),
        ("Complete the pre-lab calculations", 30),
        ("Run the experiment / implement the code", 90),
        ("Record observations and analyse results", 40),
        ("Write the lab file", 45),
    ]):
        db.add(models.AssignmentTask(assignment_id=assignment.id, title=title, est_minutes=minutes, order=order))

    db.commit()
    planner.run_planner(db, student.id, now=now, trigger="seed")
    return student.id


class _NoLLM:
    """Seed-time helper: forces the sample-bank path without importing a provider."""

    name = "stub"
    enabled = False

    def complete_json(self, system, user):  # pragma: no cover
        raise RuntimeError("no llm during seeding")

    def complete_text(self, system, user):  # pragma: no cover
        raise RuntimeError("no llm during seeding")


if __name__ == "__main__":  # python -m app.seed
    from .db import SessionLocal, init_db

    init_db()
    with SessionLocal() as session:
        print("seeded student", seed(session))
