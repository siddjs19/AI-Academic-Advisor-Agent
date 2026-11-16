"""HTTP surface. Thin: every route resolves the student from the JWT and calls a service."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import auth, memory, models, proactive
from .agents import assignments as assignments_agent
from .agents import llm as llm_module
from .agents import quiz as quiz_agent
from .agents import revision as revision_agent
from .agents import supervisor
from .agents import tutor as tutor_agent
from .config import settings
from .db import get_db
from .ingestion.extract import extract_syllabus, pdf_to_text
from .planner import service as planner

router = APIRouter(prefix="/api")


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _llm():
    return llm_module.get_llm()


# --------------------------------------------------------------------------- schemas
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(default="Student", max_length=120)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ProfileIn(BaseModel):
    name: str | None = None
    college: str | None = None
    programme: str | None = None
    semester: int | None = Field(default=None, ge=1, le=12)
    target_grade: str | None = None
    daily_minutes: int | None = Field(default=None, ge=30, le=900)


class WindowIn(BaseModel):
    weekday: int = Field(ge=0, le=6)
    start_min: int = Field(ge=0, le=1439)
    end_min: int = Field(ge=1, le=1440)


class OnboardingIn(BaseModel):
    profile: ProfileIn
    windows: list[WindowIn] = Field(default_factory=list)


class ConfirmIn(BaseModel):
    draft: dict


class MarkIn(BaseModel):
    assessment_id: int
    score: float
    max_score: float = 100.0


class PracticeIn(BaseModel):
    topic_ids: list[int] = Field(min_length=1, max_length=6)
    mode: str = "topic"
    difficulty: str = "intermediate"
    count: int = Field(default=5, ge=1, le=20)


class SubmitIn(BaseModel):
    responses: dict[str, dict]
    duration_s: int = 0


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    topic_id: int | None = None
    level: str = "intermediate"


class VivaStartIn(BaseModel):
    topic_id: int
    kind: str = "viva"


class VivaAnswerIn(BaseModel):
    answer: str = Field(min_length=1, max_length=4000)


class ReviewIn(BaseModel):
    card_id: int
    rating: int = Field(ge=0, le=3)


class CardsIn(BaseModel):
    topic_ids: list[int] = Field(default_factory=list)
    count: int = Field(default=6, ge=1, le=20)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class AssignmentIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    course_id: int | None = None
    kind: str = "assignment"
    due_at: datetime | None = None
    weight_pct: float = 0.0
    notes: str = ""


class RecActionIn(BaseModel):
    status: str


# --------------------------------------------------------------------------- auth
@router.get("/auth/demo")
def demo_credentials() -> dict:
    return {"email": settings.demo_email, "password": settings.demo_password, "enabled": settings.auto_seed}


@router.post("/auth/register")
def register(payload: RegisterIn, db: Session = Depends(get_db)) -> dict:
    email = payload.email.lower().strip()
    if db.scalars(select(models.User).where(models.User.email == email)).first():
        raise HTTPException(409, "an account with that email already exists")
    user = models.User(email=email, password_hash=auth.hash_password(payload.password))
    db.add(user)
    db.flush()
    student = models.Student(user_id=user.id, name=payload.name[:120], onboarded=False)
    db.add(student)
    db.commit()
    return {"token": auth.create_token(user), "student": _student_payload(student)}


@router.post("/auth/login")
def login(payload: LoginIn, db: Session = Depends(get_db)) -> dict:
    user = db.scalars(select(models.User).where(models.User.email == payload.email.lower().strip())).first()
    if user is None or not auth.verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "email or password is incorrect")
    student = db.scalars(select(models.Student).where(models.Student.user_id == user.id)).first()
    return {"token": auth.create_token(user), "student": _student_payload(student)}


@router.post("/auth/logout")
def logout(user: models.User = Depends(auth.current_user), db: Session = Depends(get_db)) -> dict:
    user.token_version += 1  # invalidates every token issued so far
    db.commit()
    return {"ok": True, "note": "all sessions revoked"}


@router.get("/auth/me")
def me(student: models.Student = Depends(auth.current_student)) -> dict:
    return _student_payload(student)


def _student_payload(student: models.Student | None) -> dict:
    if student is None:
        return {}
    return {
        "id": student.id,
        "name": student.name,
        "college": student.college,
        "programme": student.programme,
        "semester": student.semester,
        "target_grade": student.target_grade,
        "daily_minutes": student.daily_minutes,
        "onboarded": student.onboarded,
        "preferences": student.preferences or {},
    }


# --------------------------------------------------------------------------- profile
@router.put("/profile")
def update_profile(
    payload: ProfileIn,
    student: models.Student = Depends(auth.current_student),
    db: Session = Depends(get_db),
) -> dict:
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(student, key, value)
    db.commit()
    return _student_payload(student)


@router.post("/onboarding")
def onboarding(
    payload: OnboardingIn,
    student: models.Student = Depends(auth.current_student),
    db: Session = Depends(get_db),
) -> dict:
    for key, value in payload.profile.model_dump(exclude_none=True).items():
        setattr(student, key, value)
    if payload.windows:
        for existing in db.scalars(select(models.Availability).where(models.Availability.student_id == student.id)):
            db.delete(existing)
        for w in payload.windows:
            if w.end_min > w.start_min:
                db.add(models.Availability(student_id=student.id, **w.model_dump()))
    student.onboarded = True
    db.commit()
    return {"student": _student_payload(student), "windows": len(payload.windows)}


@router.get("/availability")
def availability(student: models.Student = Depends(auth.current_student), db: Session = Depends(get_db)) -> dict:
    rows = db.scalars(select(models.Availability).where(models.Availability.student_id == student.id))
    return {"windows": [{"weekday": w.weekday, "start_min": w.start_min, "end_min": w.end_min} for w in rows]}


# --------------------------------------------------------------------------- syllabus
@router.post("/syllabus/parse")
async def parse_syllabus(
    text: str | None = Form(None),
    file: UploadFile | None = File(None),
    student: models.Student = Depends(auth.current_student),
    db: Session = Depends(get_db),
) -> dict:
    if file is not None and file.filename:
        raw = await file.read()
        if not raw:
            raise HTTPException(400, "empty upload")
        try:
            source = pdf_to_text(raw)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(422, str(exc)) from exc
        filename = file.filename
    elif text:
        source = text
        filename = "pasted-syllabus.txt"
    else:
        raise HTTPException(400, "send a PDF file or a text field")

    draft = extract_syllabus(source, _llm())
    db.add(
        models.Document(
            student_id=student.id, filename=filename[:200], kind="syllabus",
            chars=len(source), text=source[:200_000],
        )
    )
    db.commit()
    return {"draft": draft, "source_chars": len(source), "filename": filename}


@router.post("/syllabus/confirm")
def confirm_syllabus(
    payload: ConfirmIn,
    student: models.Student = Depends(auth.current_student),
    db: Session = Depends(get_db),
) -> dict:
    draft = payload.draft
    if not draft.get("topics"):
        raise HTTPException(422, "draft has no topics")

    from .services import commit_syllabus

    result = commit_syllabus(db, student.id, draft)
    planner.run_planner(db, student.id, now=_now(), trigger="syllabus-import")
    return result


# --------------------------------------------------------------------------- courses
@router.get("/courses")
def list_courses(student: models.Student = Depends(auth.current_student), db: Session = Depends(get_db)) -> dict:
    out = []
    for course in db.scalars(
        select(models.Course).where(models.Course.student_id == student.id).order_by(models.Course.id)
    ):
        topics = list(db.scalars(select(models.Topic).where(models.Topic.course_id == course.id)))
        rows = []
        for t in topics:
            value, evidence = memory.effective_mastery(db, student.id, t)
            rows.append(
                {
                    "id": t.id,
                    "name": t.name,
                    "est_hours": t.est_hours,
                    "difficulty": t.difficulty,
                    "weight_pct": t.weight_pct,
                    "mastery": value,
                    "evidence": evidence,
                }
            )
        assessments = [
            {"id": a.id, "kind": a.kind, "title": a.title, "due_at": a.due_at.isoformat(), "weight_pct": a.weight_pct}
            for a in db.scalars(
                select(models.Assessment)
                .where(models.Assessment.course_id == course.id)
                .where(models.Assessment.due_at >= _now() - _delta(30))
                .order_by(models.Assessment.due_at)
            )
        ]
        out.append(
            {
                "id": course.id,
                "name": course.name,
                "code": course.code,
                "credits": course.credits,
                "colour": course.colour,
                "exam_at": course.exam_at.isoformat() if course.exam_at else None,
                "hours_left": round(sum(t.est_hours for t in topics), 1),
                "mastery": round(100 * sum(r["mastery"] for r in rows) / len(rows), 1) if rows else 0.0,
                "topics": rows,
                "assessments": assessments,
            }
        )
    return {"courses": out}


def _delta(days: int):
    from datetime import timedelta

    return timedelta(days=days)


@router.delete("/courses/{course_id}")
def delete_course(
    course_id: int, student: models.Student = Depends(auth.current_student), db: Session = Depends(get_db)
) -> dict:
    course = auth.owned_course(db, student.id, course_id)
    db.delete(course)
    db.commit()
    return {"deleted": course_id}


@router.post("/courses/{course_id}/topics")
def add_topics(
    course_id: int,
    payload: list[dict],
    student: models.Student = Depends(auth.current_student),
    db: Session = Depends(get_db),
) -> dict:
    auth.owned_course(db, student.id, course_id)
    created = 0
    for raw in payload:
        db.add(
            models.Topic(
                course_id=course_id,
                name=str(raw.get("name", "Topic"))[:200],
                est_hours=float(raw.get("est_hours", 2.0)),
                difficulty=int(raw.get("difficulty", 3)),
                weight_pct=float(raw.get("weight_pct", 0.0)),
            )
        )
        created += 1
    db.commit()
    return {"created": created}


@router.post("/marks")
def add_mark(
    payload: MarkIn, student: models.Student = Depends(auth.current_student), db: Session = Depends(get_db)
) -> dict:
    assessment = db.get(models.Assessment, payload.assessment_id)
    if assessment is None:
        raise HTTPException(404, "assessment not found")
    auth.owned_course(db, student.id, assessment.course_id)
    mark = models.Mark(assessment_id=assessment.id, score=payload.score, max_score=payload.max_score)
    db.add(mark)
    db.commit()
    return {"id": mark.id}


# --------------------------------------------------------------------------- plan
@router.post("/plan/build")
def build_plan(student: models.Student = Depends(auth.current_student), db: Session = Depends(get_db)) -> dict:
    run, blocks, result = planner.run_planner(db, student.id, now=_now(), trigger="manual")
    return {
        "plan_run_id": run.id,
        "status": result.status,
        "blocks": len(blocks),
        "required_hours": result.required_hours,
        "capacity_hours": result.capacity_hours,
        "shortfall": result.shortfall,
        "notes": result.notes,
    }


@router.post("/plan/replan")
def replan(student: models.Student = Depends(auth.current_student), db: Session = Depends(get_db)) -> dict:
    return planner.replan(db, student.id, now=_now())


@router.get("/plan")
def get_plan(student: models.Student = Depends(auth.current_student), db: Session = Depends(get_db)) -> dict:
    return planner.plan_payload(db, student.id)


@router.get("/drift")
def drift(student: models.Student = Depends(auth.current_student), db: Session = Depends(get_db)) -> dict:
    return planner.detect_drift(db, student.id, _now())


@router.post("/blocks/{block_id}/log")
def log_block(
    block_id: int,
    done: bool = True,
    minutes: int | None = None,
    student: models.Student = Depends(auth.current_student),
    db: Session = Depends(get_db),
) -> dict:
    block = db.get(models.Block, block_id)
    if block is None or block.student_id != student.id:
        raise HTTPException(404, "block not found")
    block.status = "done" if done else "missed"
    block.actual_minutes = minutes or int((block.end - block.start).total_seconds() // 60)
    db.commit()
    return {"id": block.id, "status": block.status}


# --------------------------------------------------------------------------- practice
@router.post("/practice/generate")
def generate_practice(
    payload: PracticeIn,
    student: models.Student = Depends(auth.current_student),
    db: Session = Depends(get_db),
) -> dict:
    topics = []
    for tid in payload.topic_ids:
        topic = db.get(models.Topic, tid)
        if topic is None:
            raise HTTPException(404, f"topic {tid} not found")
        auth.owned_course(db, student.id, topic.course_id)
        topics.append(topic)

    try:
        quiz = quiz_agent.generate(
            db, student.id, topics=topics, mode=payload.mode,
            difficulty=payload.difficulty, count=payload.count, llm=_llm(),
        )
    except llm_module.LLMError as exc:
        raise HTTPException(409, str(exc)) from exc

    questions = list(db.scalars(select(models.Question).where(models.Question.quiz_set_id == quiz.id)))
    return {
        "quiz_set_id": quiz.id,
        "title": quiz.title,
        "source": quiz.source,
        "time_limit_min": quiz.time_limit_min,
        "questions": [
            {
                "id": q.id,
                "qtype": q.qtype,
                "stem": q.stem,
                "options": q.options,
                "marks": q.marks,
                "difficulty": q.difficulty,
                "topic_id": q.topic_id,
            }
            for q in questions
        ],
    }


@router.post("/practice/{quiz_id}/submit")
def submit_practice(
    quiz_id: int,
    payload: SubmitIn,
    student: models.Student = Depends(auth.current_student),
    db: Session = Depends(get_db),
) -> dict:
    quiz = db.get(models.QuizSet, quiz_id)
    if quiz is None or quiz.student_id != student.id:
        raise HTTPException(404, "quiz not found")
    try:
        result = quiz_agent.submit_attempt(db, student.id, quiz_id, payload.responses, _llm())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    proactive.evaluate(db, student.id)
    return result


@router.get("/practice/history")
def practice_history(
    student: models.Student = Depends(auth.current_student), db: Session = Depends(get_db)
) -> dict:
    rows = list(
        db.scalars(
            select(models.Attempt)
            .where(models.Attempt.student_id == student.id)
            .order_by(models.Attempt.id.desc())
            .limit(20)
        )
    )
    out = []
    for a in rows:
        quiz = db.get(models.QuizSet, a.quiz_set_id)
        out.append(
            {
                "attempt_id": a.id,
                "quiz": quiz.title if quiz else "—",
                "at": (a.submitted_at or a.created_at).isoformat(),
                "score": round(a.score, 2),
                "max_score": a.max_score,
                "accuracy_pct": round(100 * a.score / a.max_score, 1) if a.max_score else 0.0,
            }
        )
    return {"attempts": out}


# --------------------------------------------------------------------------- tutor
@router.post("/tutor/ask")
def tutor_ask(
    payload: AskIn,
    student: models.Student = Depends(auth.current_student),
    db: Session = Depends(get_db),
) -> dict:
    topic = None
    if payload.topic_id:
        topic = db.get(models.Topic, payload.topic_id)
        if topic is None:
            raise HTTPException(404, "topic not found")
        auth.owned_course(db, student.id, topic.course_id)
    else:
        topic = supervisor.resolve_topic(db, student.id, payload.question)

    result = tutor_agent.explain(
        db, student.id, topic=topic, question=payload.question, level=payload.level, llm=_llm()
    )
    convo = supervisor.conversation(db, student.id, "tutor")
    db.add(models.Message(conversation_id=convo.id, role="user", content=payload.question))
    db.add(
        models.Message(
            conversation_id=convo.id, role="assistant", content=result["answer"],
            agent="teaching", meta={"topic_id": topic.id if topic else None},
        )
    )
    db.add(models.AgentEvent(student_id=student.id, agent="teaching", action="explain",
                             payload={"topic": topic.name if topic else None}))
    db.commit()
    result["topic"] = topic.name if topic else None
    return result


@router.get("/tutor/history")
def tutor_history(student: models.Student = Depends(auth.current_student), db: Session = Depends(get_db)) -> dict:
    return {"messages": supervisor.history(db, student.id, "tutor")}


# --------------------------------------------------------------------------- viva
@router.post("/viva/start")
def viva_start(
    payload: VivaStartIn,
    student: models.Student = Depends(auth.current_student),
    db: Session = Depends(get_db),
) -> dict:
    topic = db.get(models.Topic, payload.topic_id)
    if topic is None:
        raise HTTPException(404, "topic not found")
    auth.owned_course(db, student.id, topic.course_id)
    session = tutor_agent.start_viva(db, student.id, topic=topic, kind=payload.kind, llm=_llm())
    return {
        "session_id": session.id,
        "topic": topic.name,
        "evaluator": session.evaluator,
        "question": session.transcript[0]["text"],
        "kind": session.kind,
    }


@router.post("/viva/{session_id}/answer")
def viva_answer(
    session_id: int,
    payload: VivaAnswerIn,
    student: models.Student = Depends(auth.current_student),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return tutor_agent.answer_viva(db, student.id, session_id, payload.answer, _llm())
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/viva/history")
def viva_history(
    student: models.Student = Depends(auth.current_student), db: Session = Depends(get_db)
) -> dict:
    rows = list(
        db.scalars(
            select(models.VivaSession)
            .where(models.VivaSession.student_id == student.id)
            .order_by(models.VivaSession.id.desc())
            .limit(10)
        )
    )
    return {
        "sessions": [
            {
                "id": s.id,
                "kind": s.kind,
                "status": s.status,
                "score": s.score,
                "feedback": s.feedback,
                "at": s.created_at.isoformat(),
                "topic": (db.get(models.Topic, s.topic_id).name if s.topic_id else "—"),
            }
            for s in rows
        ]
    }


# --------------------------------------------------------------------------- revision
@router.get("/revision/due")
def revision_due(
    limit: int = 20, student: models.Student = Depends(auth.current_student), db: Session = Depends(get_db)
) -> dict:
    cards = revision_agent.due_cards(db, student.id, limit)
    total = len(db.scalars(select(models.Flashcard).where(models.Flashcard.student_id == student.id)).all())
    return {
        "cards": [
            {"id": c.id, "front": c.front, "back": c.back, "interval_days": c.interval_days, "reps": c.reps}
            for c in cards
        ],
        "total_cards": total,
    }


@router.post("/revision/review")
def revision_review(
    payload: ReviewIn,
    student: models.Student = Depends(auth.current_student),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return revision_agent.review(db, student.id, payload.card_id, payload.rating)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/revision/generate")
def revision_generate(
    payload: CardsIn,
    student: models.Student = Depends(auth.current_student),
    db: Session = Depends(get_db),
) -> dict:
    if payload.topic_ids:
        topics = []
        for tid in payload.topic_ids:
            topic = db.get(models.Topic, tid)
            if topic is None:
                raise HTTPException(404, "topic not found")
            auth.owned_course(db, student.id, topic.course_id)
            topics.append(topic)
    else:
        weak = memory.weak_topics(db, student.id, 3)
        topics = [db.get(models.Topic, w["topic_id"]) for w in weak]
        topics = [t for t in topics if t is not None]
    if not topics:
        raise HTTPException(422, "no topics to build cards from")
    cards = revision_agent.generate_cards(db, student.id, topics, payload.count, _llm())
    if not cards:
        raise HTTPException(
            409, "no cards could be generated: this topic has no sample-bank cards and no model is configured"
        )
    return {"created": len(cards), "source": cards[0].source}


# --------------------------------------------------------------------------- analytics
@router.get("/analytics")
def analytics(student: models.Student = Depends(auth.current_student), db: Session = Depends(get_db)) -> dict:
    return memory.analytics(db, student.id)


# --------------------------------------------------------------------------- assignments
@router.get("/assignments")
def list_assignments(
    student: models.Student = Depends(auth.current_student), db: Session = Depends(get_db)
) -> dict:
    rows = list(
        db.scalars(
            select(models.Assignment)
            .where(models.Assignment.student_id == student.id)
            .order_by(models.Assignment.due_at)
        )
    )
    out = []
    for a in rows:
        course = db.get(models.Course, a.course_id) if a.course_id else None
        out.append(
            {
                "id": a.id,
                "title": a.title,
                "kind": a.kind,
                "status": a.status,
                "due_at": a.due_at.isoformat() if a.due_at else None,
                "course": course.name if course else "",
                "notes": a.notes,
                "progress": assignments_agent.progress(a),
                "tasks": [
                    {"id": t.id, "title": t.title, "est_minutes": t.est_minutes, "done": t.done}
                    for t in sorted(a.tasks, key=lambda t: t.order)
                ],
            }
        )
    return {"assignments": out}


@router.post("/assignments")
def create_assignment(
    payload: AssignmentIn,
    student: models.Student = Depends(auth.current_student),
    db: Session = Depends(get_db),
) -> dict:
    if payload.course_id:
        auth.owned_course(db, student.id, payload.course_id)
    assignment = models.Assignment(
        student_id=student.id,
        course_id=payload.course_id,
        title=payload.title[:200],
        kind=payload.kind,
        due_at=payload.due_at,
        weight_pct=payload.weight_pct,
        notes=payload.notes,
    )
    db.add(assignment)
    db.flush()
    assignments_agent.decompose(db, assignment, _llm())
    db.commit()
    return {"id": assignment.id, "tasks": len(assignment.tasks)}


@router.post("/assignments/{assignment_id}/tasks/{task_id}/toggle")
def toggle_task(
    assignment_id: int,
    task_id: int,
    student: models.Student = Depends(auth.current_student),
    db: Session = Depends(get_db),
) -> dict:
    assignment = db.get(models.Assignment, assignment_id)
    if assignment is None or assignment.student_id != student.id:
        raise HTTPException(404, "assignment not found")
    task = db.get(models.AssignmentTask, task_id)
    if task is None or task.assignment_id != assignment_id:
        raise HTTPException(404, "task not found")
    task.done = not task.done
    db.commit()
    return {"id": task.id, "done": task.done, "progress": assignments_agent.progress(assignment)}


@router.delete("/assignments/{assignment_id}")
def delete_assignment(
    assignment_id: int, student: models.Student = Depends(auth.current_student), db: Session = Depends(get_db)
) -> dict:
    assignment = db.get(models.Assignment, assignment_id)
    if assignment is None or assignment.student_id != student.id:
        raise HTTPException(404, "assignment not found")
    db.delete(assignment)
    db.commit()
    return {"deleted": assignment_id}


# --------------------------------------------------------------------------- recommendations
@router.get("/recommendations")
def recommendations(
    refresh: bool = True,
    student: models.Student = Depends(auth.current_student),
    db: Session = Depends(get_db),
) -> dict:
    if refresh:
        proactive.evaluate(db, student.id)
    return {"recommendations": proactive.active(db, student.id)}


@router.post("/recommendations/{rec_id}/act")
def act_on_recommendation(
    rec_id: int,
    payload: RecActionIn,
    student: models.Student = Depends(auth.current_student),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return proactive.act(db, student.id, rec_id, payload.status)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


# --------------------------------------------------------------------------- advisor
@router.post("/advisor/chat")
def advisor_chat(
    payload: ChatIn,
    student: models.Student = Depends(auth.current_student),
    db: Session = Depends(get_db),
) -> dict:
    return supervisor.chat(db, student.id, payload.message, _llm())


@router.get("/advisor/history")
def advisor_history(
    student: models.Student = Depends(auth.current_student), db: Session = Depends(get_db)
) -> dict:
    return {"messages": supervisor.history(db, student.id, "advisor")}


# --------------------------------------------------------------------------- dashboard
@router.get("/dashboard")
def dashboard(student: models.Student = Depends(auth.current_student), db: Session = Depends(get_db)) -> dict:
    now = _now()
    plan = planner.plan_payload(db, student.id)
    drift = planner.detect_drift(db, student.id, now)
    readiness = memory.exam_readiness(db, student.id)
    weak = memory.weak_topics(db, student.id, 5)
    proactive.evaluate(db, student.id)

    today = now.date().isoformat()
    deadlines = [
        {
            "id": a.id,
            "course": a.course.name,
            "code": a.course.code,
            "title": a.title or a.kind,
            "kind": a.kind,
            "due_at": a.due_at.isoformat(),
            "days_left": max(0, (a.due_at - now).days),
            "weight_pct": a.weight_pct,
        }
        for a in db.scalars(
            select(models.Assessment)
            .join(models.Course, models.Course.id == models.Assessment.course_id)
            .where(models.Course.student_id == student.id)
            .where(models.Assessment.due_at >= now)
            .order_by(models.Assessment.due_at)
            .limit(6)
        )
    ]
    attempts = db.scalars(
        select(models.Attempt)
        .where(models.Attempt.student_id == student.id)
        .where(models.Attempt.submitted_at.is_not(None))
        .order_by(models.Attempt.submitted_at.desc())
        .limit(5)
    ).all()
    open_assignments = db.scalars(
        select(models.Assignment)
        .where(models.Assignment.student_id == student.id)
        .where(models.Assignment.status == "open")
    ).all()

    return {
        "student": _student_payload(student),
        "llm": {"enabled": _llm().enabled, "name": _llm().name},
        "stats": {
            "readiness": round(sum(r["readiness"] for r in readiness) / len(readiness), 1) if readiness else 0.0,
            "required_hours": plan["plan"]["required_hours"] if plan["plan"] else 0.0,
            "capacity_hours": plan["plan"]["capacity_hours"] if plan["plan"] else 0.0,
            "blocks": len(plan["blocks"]),
            "adherence_pct": drift["adherence_pct"],
            "attempts": len(attempts),
            "due_cards": len(revision_agent.due_cards(db, student.id, 100)),
            "open_assignments": len(open_assignments),
        },
        "readiness": readiness,
        "weak_topics": weak,
        "plan": plan["plan"],
        "blocks": plan["blocks"],
        "today_blocks": [b for b in plan["blocks"] if b["start"][:10] == today],
        "next_block": drift["next_block"],
        "deadlines": deadlines,
        "recommendations": proactive.active(db, student.id),
        "recent_attempts": [
            {
                "attempt_id": a.id,
                "accuracy_pct": round(100 * a.score / a.max_score, 1) if a.max_score else 0.0,
                "at": a.submitted_at.isoformat(),
            }
            for a in attempts
        ],
    }


@router.get("/health")
def health() -> dict:
    llm = _llm()
    return {"ok": True, "llm": llm.name, "llm_enabled": llm.enabled, "version": "1.0.0"}
