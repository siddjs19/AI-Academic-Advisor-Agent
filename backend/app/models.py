"""Database schema.

One relational source of truth for every academic fact. Vector search (when
added) is a retrieval aid over notes — never the authority for marks, dates or
deadlines, which is why those live in typed columns, not in embeddings.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


# --------------------------------------------------------------------------- identity
class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    token_version: Mapped[int] = mapped_column(Integer, default=1)  # bumped on logout
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    student: Mapped["Student | None"] = relationship(back_populates="user", uselist=False)


class Student(Base, TimestampMixin):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    name: Mapped[str] = mapped_column(String(120), default="Student")
    college: Mapped[str] = mapped_column(String(160), default="")
    programme: Mapped[str] = mapped_column(String(120), default="B.E. Computer Engineering")
    semester: Mapped[int] = mapped_column(Integer, default=1)
    target_grade: Mapped[str] = mapped_column(String(40), default="8.5 CGPA")
    daily_minutes: Mapped[int] = mapped_column(Integer, default=240)
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)
    onboarded: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped[User] = relationship(back_populates="student")


# --------------------------------------------------------------------------- academics
class Course(Base, TimestampMixin):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    code: Mapped[str] = mapped_column(String(40), default="")
    credits: Mapped[float] = mapped_column(Float, default=3.0)
    exam_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    colour: Mapped[int] = mapped_column(Integer, default=0)

    topics: Mapped[list["Topic"]] = relationship(back_populates="course", cascade="all, delete-orphan")
    assessments: Mapped[list["Assessment"]] = relationship(back_populates="course", cascade="all, delete-orphan")


class Topic(Base, TimestampMixin):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    unit: Mapped[str] = mapped_column(String(80), default="")
    est_hours: Mapped[float] = mapped_column(Float, default=1.5)
    difficulty: Mapped[int] = mapped_column(Integer, default=3)
    weight_pct: Mapped[float] = mapped_column(Float, default=0.0)
    prereq_ids: Mapped[list] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)

    course: Mapped[Course] = relationship(back_populates="topics")


class Assessment(Base, TimestampMixin):
    __tablename__ = "assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40), default="exam")
    title: Mapped[str] = mapped_column(String(160), default="")
    due_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    weight_pct: Mapped[float] = mapped_column(Float, default=0.0)
    covers: Mapped[list] = mapped_column(JSON, default=list)

    course: Mapped[Course] = relationship(back_populates="assessments")
    marks: Mapped[list["Mark"]] = relationship(back_populates="assessment", cascade="all, delete-orphan")


class Mark(Base, TimestampMixin):
    __tablename__ = "marks"

    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessments.id", ondelete="CASCADE"), index=True)
    score: Mapped[float] = mapped_column(Float)
    max_score: Mapped[float] = mapped_column(Float, default=100.0)

    assessment: Mapped[Assessment] = relationship(back_populates="marks")


class Availability(Base):
    __tablename__ = "availability"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    weekday: Mapped[int] = mapped_column(Integer)  # 0 = Monday
    start_min: Mapped[int] = mapped_column(Integer)
    end_min: Mapped[int] = mapped_column(Integer)


class Blackout(Base):
    __tablename__ = "blackouts"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    on_date: Mapped[datetime] = mapped_column(DateTime)
    reason: Mapped[str] = mapped_column(String(120), default="")


# --------------------------------------------------------------------------- planning
class PlanRun(Base, TimestampMixin):
    __tablename__ = "plan_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    trigger: Mapped[str] = mapped_column(String(60), default="initial")
    status: Mapped[str] = mapped_column(String(20), default="ok")
    objective: Mapped[float] = mapped_column(Float, default=0.0)
    required_hours: Mapped[float] = mapped_column(Float, default=0.0)
    capacity_hours: Mapped[float] = mapped_column(Float, default=0.0)
    shortfall: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[list] = mapped_column(JSON, default=list)


class Block(Base, TimestampMixin):
    __tablename__ = "blocks"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_run_id: Mapped[int] = mapped_column(ForeignKey("plan_runs.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    start: Mapped[datetime] = mapped_column(DateTime, index=True)
    end: Mapped[datetime] = mapped_column(DateTime)
    kind: Mapped[str] = mapped_column(String(20), default="study")  # study | revision | practice
    status: Mapped[str] = mapped_column(String(20), default="planned")  # planned|done|missed|superseded
    actual_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    label: Mapped[str] = mapped_column(Text, default="")


# --------------------------------------------------------------------------- assessment
class QuizSet(Base, TimestampMixin):
    __tablename__ = "quiz_sets"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(160), default="Practice set")
    mode: Mapped[str] = mapped_column(String(20), default="topic")  # topic|unit|mock|revision
    difficulty: Mapped[str] = mapped_column(String(20), default="intermediate")
    topic_ids: Mapped[list] = mapped_column(JSON, default=list)
    source: Mapped[str] = mapped_column(String(20), default="bank")  # llm | bank
    time_limit_min: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Question(Base, TimestampMixin):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    quiz_set_id: Mapped[int] = mapped_column(ForeignKey("quiz_sets.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id", ondelete="SET NULL"), nullable=True)
    qtype: Mapped[str] = mapped_column(String(24), default="mcq")  # mcq|multi|truefalse|numerical|short|descriptive
    stem: Mapped[str] = mapped_column(Text)
    options: Mapped[list] = mapped_column(JSON, default=list)
    answer: Mapped[dict] = mapped_column(JSON, default=dict)  # {"value": ...} | {"keywords": [...]}
    explanation: Mapped[str] = mapped_column(Text, default="")
    difficulty: Mapped[str] = mapped_column(String(20), default="intermediate")
    marks: Mapped[float] = mapped_column(Float, default=1.0)


class Attempt(Base, TimestampMixin):
    __tablename__ = "attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    quiz_set_id: Mapped[int] = mapped_column(ForeignKey("quiz_sets.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    max_score: Mapped[float] = mapped_column(Float, default=0.0)
    duration_s: Mapped[int] = mapped_column(Integer, default=0)

    answers: Mapped[list["Answer"]] = relationship(back_populates="attempt", cascade="all, delete-orphan")


class Answer(Base, TimestampMixin):
    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("attempts.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), index=True)
    response: Mapped[dict] = mapped_column(JSON, default=dict)
    correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    awarded: Mapped[float] = mapped_column(Float, default=0.0)
    feedback: Mapped[str] = mapped_column(Text, default="")
    graded_by: Mapped[str] = mapped_column(String(20), default="rule")  # rule | llm | pending

    attempt: Mapped[Attempt] = relationship(back_populates="answers")


class TopicMastery(Base, TimestampMixin):
    """Evidence-based mastery. Never moves far on a single answer."""

    __tablename__ = "topic_mastery"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    correct: Mapped[int] = mapped_column(Integer, default=0)
    mastery: Mapped[float] = mapped_column(Float, default=0.35)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


# --------------------------------------------------------------------------- revision
class Flashcard(Base, TimestampMixin):
    __tablename__ = "flashcards"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    front: Mapped[str] = mapped_column(Text)
    back: Mapped[str] = mapped_column(Text)
    ease: Mapped[float] = mapped_column(Float, default=2.5)
    interval_days: Mapped[float] = mapped_column(Float, default=0.0)
    reps: Mapped[int] = mapped_column(Integer, default=0)
    lapses: Mapped[int] = mapped_column(Integer, default=0)
    due_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    source: Mapped[str] = mapped_column(String(20), default="bank")


class ReviewLog(Base, TimestampMixin):
    __tablename__ = "review_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    flashcard_id: Mapped[int] = mapped_column(ForeignKey("flashcards.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    rating: Mapped[int] = mapped_column(Integer, default=3)  # 0 again .. 3 easy
    interval_before: Mapped[float] = mapped_column(Float, default=0.0)
    interval_after: Mapped[float] = mapped_column(Float, default=0.0)


# --------------------------------------------------------------------------- viva / communication
class VivaSession(Base, TimestampMixin):
    __tablename__ = "viva_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id", ondelete="SET NULL"), nullable=True)
    kind: Mapped[str] = mapped_column(String(24), default="viva")  # viva|interview|hr|presentation|gd
    status: Mapped[str] = mapped_column(String(20), default="active")  # active|finished
    transcript: Mapped[list] = mapped_column(JSON, default=list)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    feedback: Mapped[str] = mapped_column(Text, default="")
    evaluator: Mapped[str] = mapped_column(String(20), default="rule")


# --------------------------------------------------------------------------- assignments
class Assignment(Base, TimestampMixin):
    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(24), default="assignment")  # assignment|project|lab|presentation
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    weight_pct: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open|done
    notes: Mapped[str] = mapped_column(Text, default="")

    tasks: Mapped[list["AssignmentTask"]] = relationship(back_populates="assignment", cascade="all, delete-orphan")


class AssignmentTask(Base):
    __tablename__ = "assignment_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    est_minutes: Mapped[int] = mapped_column(Integer, default=45)
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    order: Mapped[int] = mapped_column(Integer, default=0)

    assignment: Mapped[Assignment] = relationship(back_populates="tasks")


# --------------------------------------------------------------------------- conversation + memory
class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20), default="advisor")  # advisor | tutor
    title: Mapped[str] = mapped_column(String(200), default="Conversation")


class Message(Base, TimestampMixin):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    agent: Mapped[str] = mapped_column(String(40), default="")  # which specialist answered
    meta: Mapped[dict] = mapped_column(JSON, default=dict)


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)
    filename: Mapped[str] = mapped_column(String(200), default="")
    kind: Mapped[str] = mapped_column(String(20), default="syllabus")  # syllabus | notes
    chars: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(Text, default="")


class Recommendation(Base, TimestampMixin):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40))  # exam_risk|weak_topic|revision_due|assignment|viva|assess_ready
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(16), default="info")  # info|warn|critical
    action: Mapped[dict] = mapped_column(JSON, default=dict)  # {"type": "...", "params": {...}}
    status: Mapped[str] = mapped_column(String(16), default="new")  # new|accepted|dismissed
    dedupe_key: Mapped[str] = mapped_column(String(200), default="", index=True)


class AgentEvent(Base, TimestampMixin):
    __tablename__ = "agent_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    agent: Mapped[str] = mapped_column(String(40))
    action: Mapped[str] = mapped_column(String(80))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="ok")
