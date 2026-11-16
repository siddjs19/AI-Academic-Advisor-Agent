"""Assessment: deterministic grading, honest handling of ungradable answers, and
mastery that does not overreact to a single answer."""
from app import memory, models
from app.agents import quiz as quiz_agent
from app.db import SessionLocal


def _q(**kwargs):
    defaults = dict(id=1, qtype="mcq", stem="s", options=["A", "B"], answer={"value": "A"},
                    explanation="because", marks=1.0, difficulty="intermediate", topic_id=None)
    defaults.update(kwargs)
    return models.Question(**defaults)


def test_mcq_grading():
    q = _q()
    assert quiz_agent.grade(q, {"value": "A"})["correct"] is True
    wrong = quiz_agent.grade(q, {"value": "B"})
    assert wrong["correct"] is False
    assert wrong["awarded"] == 0.0
    assert "A" in wrong["feedback"]


def test_multi_select_partial_credit_and_penalty():
    q = _q(qtype="multi", options=["A", "B", "C", "D"], answer={"value": ["A", "C"]}, marks=2.0)
    perfect = quiz_agent.grade(q, {"value": ["A", "C"]})
    assert perfect["correct"] is True and perfect["awarded"] == 2.0

    half = quiz_agent.grade(q, {"value": ["A"]})
    assert half["correct"] is False
    assert 0.0 < half["awarded"] < 2.0

    over_selected = quiz_agent.grade(q, {"value": ["A", "C", "D"]})
    assert over_selected["awarded"] < perfect["awarded"]


def test_numerical_tolerance():
    q = _q(qtype="numerical", options=[], answer={"value": 8, "tolerance": 0.5})
    assert quiz_agent.grade(q, {"value": "8.4"})["correct"] is True
    assert quiz_agent.grade(q, {"value": "9.0"})["correct"] is False
    assert quiz_agent.grade(q, {"value": "not a number"})["correct"] is False


def test_short_answer_keyword_coverage():
    q = _q(qtype="short", options=[], answer={"keywords": ["atomicity", "isolation"]}, marks=2.0)
    good = quiz_agent.grade(q, {"value": "ACID means atomicity, consistency, isolation and durability."})
    assert good["correct"] is True
    assert good["awarded"] == 2.0

    partial = quiz_agent.grade(q, {"value": "It is about atomicity mostly."})
    assert partial["correct"] is False
    assert 0.0 < partial["awarded"] < 2.0
    assert "Missing" in partial["feedback"]


def test_descriptive_without_rubric_or_model_is_marked_pending_not_scored():
    """Rule 5: never claim a grade we cannot justify."""
    q = _q(qtype="descriptive", options=[], answer={}, marks=5.0)
    result = quiz_agent.grade(q, {"value": "A long paragraph of plausible writing about the topic."})
    assert result["correct"] is None
    assert result["awarded"] == 0.0
    assert result["graded_by"] == "pending"


def test_mastery_moves_slowly_and_needs_evidence():
    with SessionLocal() as db:
        user = models.User(email=f"m{__import__('os').urandom(4).hex()}@t.app", password_hash="x")
        db.add(user)
        db.flush()
        student = models.Student(user_id=user.id, name="M")
        db.add(student)
        db.flush()
        course = models.Course(student_id=student.id, name="C")
        db.add(course)
        db.flush()
        topic = models.Topic(course_id=course.id, name="T")
        db.add(topic)
        db.flush()

        start, _ = memory.effective_mastery(db, student.id, topic)
        assert start == memory.PRIOR

        memory.record_evidence(db, student.id, topic.id, True)
        one, evidence = memory.effective_mastery(db, student.id, topic)
        assert one > start
        assert one - start < 0.2, "one correct answer must not look like mastery"
        assert evidence["confident"] is False

        for _ in range(3):
            memory.record_evidence(db, student.id, topic.id, True)
        four, evidence = memory.effective_mastery(db, student.id, topic)
        assert four > one
        assert evidence["confident"] is True
        db.rollback()


def test_generated_questions_are_validated():
    bad = quiz_agent._validate({"qtype": "mcq", "stem": "short", "options": ["A"], "answer": {"value": "Z"}})
    assert bad is None
    good = quiz_agent._validate(
        {"qtype": "mcq", "stem": "Which option is correct here?", "options": ["A", "B"], "answer": {"value": "A"}}
    )
    assert good is not None and good["qtype"] == "mcq"
