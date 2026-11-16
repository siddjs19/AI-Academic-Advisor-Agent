"""Assessment agent: question generation, grading, evidence hand-off.

Generation needs a model. Grading does not: objective types are graded by rules,
short answers by keyword coverage, and descriptive answers are marked
`graded_by=pending` rather than given a made-up score when no model is available.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import memory, models
from .llm import LLM, LLMError

QTYPES = {"mcq", "multi", "truefalse", "numerical", "short", "descriptive"}

SYSTEM = """You write exam questions for an Indian engineering undergraduate.
Rules:
- Use only the given topic names; never invent a topic.
- One correct answer per objective question; distractors must be plausible and wrong.
- `answer.value` must exactly equal one of the `options` for mcq/truefalse, and be a
  list of option strings for `multi`. For `numerical` give the number and a tolerance.
  For `short`/`descriptive` give `answer.keywords`, the concepts a good answer must mention.
- Return JSON only: {"questions": [...]}"""

PROMPT = """Course: {course}
Topics: {topics}
Difficulty: {difficulty}
Write {count} questions mixing types: {types}.
Schema per question:
{{"qtype":"mcq|multi|truefalse|numerical|short|descriptive","stem":"...","options":["..."],
  "answer":{{"value":...,"tolerance":0.01}},"explanation":"...","difficulty":"{difficulty}",
  "topic":"<one of the topics>","marks":1}}"""


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --------------------------------------------------------------------------- generation
def _validate(raw: dict) -> dict | None:
    qtype = str(raw.get("qtype", "mcq")).lower()
    if qtype not in QTYPES:
        return None
    stem = str(raw.get("stem", "")).strip()
    if len(stem) < 8:
        return None
    options = [str(o) for o in (raw.get("options") or [])]
    answer = raw.get("answer") or {}
    if qtype in ("mcq", "truefalse"):
        if len(options) < 2:
            return None
        if str(answer.get("value")) not in options:
            return None
    if qtype == "multi":
        vals = answer.get("value") or []
        if len(options) < 2 or not isinstance(vals, list) or not all(str(v) in options for v in vals):
            return None
    if qtype == "numerical":
        try:
            float(answer.get("value"))
        except (TypeError, ValueError):
            return None
    if qtype in ("short", "descriptive") and not (answer.get("keywords") or []):
        return None
    return {
        "qtype": qtype,
        "stem": stem,
        "options": options,
        "answer": answer,
        "explanation": str(raw.get("explanation", ""))[:1200],
        "difficulty": str(raw.get("difficulty", "intermediate")),
        "marks": float(raw.get("marks", 1) or 1),
        "topic": str(raw.get("topic", "")),
    }


def _match_topic(topics: list[models.Topic], name: str) -> models.Topic | None:
    name = (name or "").lower().strip()
    for t in topics:
        if t.name.lower() == name:
            return t
    for t in topics:
        if name and (name in t.name.lower() or t.name.lower() in name):
            return t
    return None


def generate(db: Session, student_id: int, *, topics: list[models.Topic], mode: str, difficulty: str,
             count: int, llm: LLM) -> models.QuizSet:
    course = topics[0].course
    quiz = models.QuizSet(
        student_id=student_id,
        title=f"{course.code or course.name} · {', '.join(t.name for t in topics[:2])}"
        + (" …" if len(topics) > 2 else ""),
        mode=mode,
        difficulty=difficulty,
        topic_ids=[t.id for t in topics],
        source="llm" if llm.enabled else "bank",
        time_limit_min=count * 2 if mode == "mock" else None,
    )
    db.add(quiz)
    db.flush()

    created = 0
    if llm.enabled:
        try:
            data = llm.complete_json(
                SYSTEM,
                PROMPT.format(
                    course=f"{course.name} ({course.code})",
                    topics="; ".join(t.name for t in topics),
                    difficulty=difficulty,
                    count=count,
                    types="mcq, truefalse, numerical, short",
                ),
            )
            for raw in (data.get("questions") or [])[:count]:
                q = _validate(raw)
                if not q:
                    continue
                topic = _match_topic(topics, q.pop("topic"))
                db.add(
                    models.Question(
                        quiz_set_id=quiz.id,
                        topic_id=topic.id if topic else topics[0].id,
                        qtype=q["qtype"],
                        stem=q["stem"],
                        options=q["options"],
                        answer=q["answer"],
                        explanation=q["explanation"],
                        difficulty=q["difficulty"],
                        marks=q["marks"],
                    )
                )
                created += 1
        except LLMError:
            pass  # fall through to the sample bank

    if created == 0:
        created = _from_bank(db, quiz, topics, count)
    if created == 0:
        db.rollback()
        raise LLMError(
            "No questions available: this topic has no sample-bank questions and no model is "
            "configured. Set LLM_PROVIDER + LLM_API_KEY to generate questions."
        )
    db.commit()
    return quiz


# --------------------------------------------------------------------------- sample bank
BANK: list[dict] = [
    # --- Data Structures & Algorithms
    {"match": "arrays", "qtype": "mcq", "stem": "What is the average time complexity of a hash table lookup with a good hash function?",
     "options": ["O(1)", "O(log n)", "O(n)", "O(n log n)"], "answer": {"value": "O(1)"},
     "explanation": "Hashing maps keys to buckets directly, so the expected lookup cost is constant.", "difficulty": "beginner"},
    {"match": "trees", "qtype": "mcq", "stem": "A binary search tree with n nodes has a worst-case height of:",
     "options": ["n", "log n", "n/2", "sqrt(n)"], "answer": {"value": "n"},
     "explanation": "Inserting sorted keys degenerates the tree into a linked list.", "difficulty": "intermediate"},
    {"match": "trees", "qtype": "truefalse", "stem": "In-order traversal of a binary search tree visits keys in sorted order.",
     "options": ["True", "False"], "answer": {"value": "True"},
     "explanation": "In-order visits left subtree, node, right subtree — which is sorted for a BST.", "difficulty": "beginner"},
    {"match": "graphs", "qtype": "mcq", "stem": "Dijkstra's algorithm fails to give correct shortest paths when the graph has:",
     "options": ["negative edge weights", "cycles", "more than 1000 nodes", "self loops"], "answer": {"value": "negative edge weights"},
     "explanation": "A negative edge can make a longer path cheaper after it has been finalised.", "difficulty": "intermediate"},
    {"match": "dynamic programming", "qtype": "short", "stem": "State the two properties a problem must have for dynamic programming to apply.",
     "options": [], "answer": {"keywords": ["optimal substructure", "overlapping subproblems"]},
     "explanation": "Optimal substructure lets you compose solutions; overlapping subproblems make memoisation worthwhile.", "difficulty": "intermediate"},
    {"match": "dynamic programming", "qtype": "numerical", "stem": "How many distinct ways can you climb 5 stairs taking 1 or 2 steps at a time?",
     "options": [], "answer": {"value": 8, "tolerance": 0}, "explanation": "Fibonacci: f(5) = 8.", "difficulty": "beginner"},
    # --- DBMS
    {"match": "normalisation", "qtype": "mcq", "stem": "A relation is in 3NF but a non-prime attribute depends transitively on a candidate key. Which normal form does it violate?",
     "options": ["2NF", "3NF", "BCNF", "4NF"], "answer": {"value": "3NF"},
     "explanation": "3NF forbids transitive dependencies of non-prime attributes on candidate keys.", "difficulty": "intermediate"},
    {"match": "sql", "qtype": "mcq", "stem": "Which join returns rows from the left table even when there is no match on the right?",
     "options": ["INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "CROSS JOIN"], "answer": {"value": "LEFT JOIN"},
     "explanation": "LEFT JOIN keeps unmatched left rows and fills NULLs on the right.", "difficulty": "beginner"},
    {"match": "transactions", "qtype": "short", "stem": "Name the four ACID properties of a database transaction.",
     "options": [], "answer": {"keywords": ["atomicity", "consistency", "isolation", "durability"]},
     "explanation": "Atomicity, Consistency, Isolation, Durability.", "difficulty": "beginner"},
    {"match": "er modelling", "qtype": "truefalse", "stem": "In an ER diagram, a weak entity can exist without its identifying owner.",
     "options": ["True", "False"], "answer": {"value": "False"},
     "explanation": "A weak entity is existence-dependent on its identifying owner.", "difficulty": "intermediate"},
    # --- OS
    {"match": "synchronisation", "qtype": "mcq", "stem": "Which condition is NOT required for a deadlock?",
     "options": ["Mutual exclusion", "Hold and wait", "Preemption", "Circular wait"], "answer": {"value": "Preemption"},
     "explanation": "Deadlock requires NO preemption; preemption breaks the cycle.", "difficulty": "intermediate"},
    {"match": "memory management", "qtype": "mcq", "stem": "A page fault occurs when:",
     "options": ["the page is not in memory", "the page is dirty", "TLB is flushed", "the process is swapped out"],
     "answer": {"value": "the page is not in memory"},
     "explanation": "The referenced page is absent from physical frames, so the OS must fetch it.", "difficulty": "beginner"},
    {"match": "processes", "qtype": "mcq", "stem": "Which scheduling algorithm can cause starvation of long jobs?",
     "options": ["Shortest Job First", "First Come First Serve", "Round Robin", "FIFO"], "answer": {"value": "Shortest Job First"},
     "explanation": "Short jobs keep arriving and jump the queue, so long jobs may never run.", "difficulty": "intermediate"},
    {"match": "file systems", "qtype": "short", "stem": "What does an inode store, and what does it deliberately not store?",
     "options": [], "answer": {"keywords": ["metadata", "file name", "blocks", "permissions"]},
     "explanation": "Inodes hold metadata and block pointers; the filename lives in the directory entry.", "difficulty": "advanced"},
    {"match": "synchronisation", "qtype": "mcq", "stem": "A semaphore initialised to 3 allows how many processes into the critical section at once?",
     "options": ["1", "3", "0", "unlimited"], "answer": {"value": "3"},
     "explanation": "A counting semaphore permits N concurrent holders, where N is its initial value.", "difficulty": "beginner"},
    {"match": "synchronisation", "qtype": "truefalse", "stem": "A spinlock wastes CPU cycles while waiting, but avoids a context switch.",
     "options": ["True", "False"], "answer": {"value": "True"},
     "explanation": "Spinning burns cycles; the trade-off is no scheduler overhead, which pays off for very short critical sections.", "difficulty": "intermediate"},
    {"match": "synchronisation", "qtype": "short", "stem": "Why can a semaphore cause priority inversion, and how does priority inheritance help?",
     "options": [], "answer": {"keywords": ["low priority", "lock", "high priority", "inheritance"]},
     "explanation": "A high-priority task blocks on a lock held by a low-priority task; inheritance temporarily raises the holder's priority.", "difficulty": "advanced"},
    {"match": "memory management", "qtype": "mcq", "stem": "The TLB exists to speed up:",
     "options": ["virtual to physical translation", "disk scheduling", "page replacement", "context switching"],
     "answer": {"value": "virtual to physical translation"},
     "explanation": "The TLB caches page-table entries, avoiding a memory walk per access.", "difficulty": "beginner"},
    {"match": "memory management", "qtype": "mcq", "stem": "Belady's anomaly can occur with which page replacement policy?",
     "options": ["FIFO", "LRU", "Optimal", "Clock"], "answer": {"value": "FIFO"},
     "explanation": "FIFO can produce more faults with more frames; LRU and Optimal are stack algorithms and cannot.", "difficulty": "intermediate"},
    {"match": "transactions", "qtype": "mcq", "stem": "Which isolation level allows non-repeatable reads?",
     "options": ["READ COMMITTED", "SERIALIZABLE", "REPEATABLE READ", "Snapshot"], "answer": {"value": "READ COMMITTED"},
     "explanation": "READ COMMITTED re-reads rows per statement, so a value can change between reads in one transaction.", "difficulty": "advanced"},
    {"match": "trees", "qtype": "mcq", "stem": "Deleting a node with two children from a BST requires replacing it with:",
     "options": ["its in-order successor or predecessor", "its left child", "its right child", "the root"],
     "answer": {"value": "its in-order successor or predecessor"},
     "explanation": "Either keeps the in-order sequence sorted.", "difficulty": "intermediate"},
    {"match": "graphs", "qtype": "mcq", "stem": "BFS on a graph with V vertices and E edges runs in:",
     "options": ["O(V + E)", "O(V log V)", "O(E^2)", "O(V * E)"], "answer": {"value": "O(V + E)"},
     "explanation": "Each vertex and edge is examined a constant number of times.", "difficulty": "beginner"},
    {"match": "normalisation", "qtype": "mcq", "stem": "2NF removes which kind of dependency?",
     "options": ["partial dependency on a composite key", "transitive dependency", "multivalued dependency", "join dependency"],
     "answer": {"value": "partial dependency on a composite key"},
     "explanation": "2NF requires every non-prime attribute to depend on the whole candidate key.", "difficulty": "intermediate"},
    # --- Theory of computation
    {"match": "finite automata", "qtype": "truefalse", "stem": "Every regular language can be recognised by a deterministic finite automaton.",
     "options": ["True", "False"], "answer": {"value": "True"},
     "explanation": "DFA and NFA recognise exactly the regular languages.", "difficulty": "beginner"},
    {"match": "turing machines", "qtype": "mcq", "stem": "The halting problem is:",
     "options": ["decidable", "undecidable", "regular", "context free"], "answer": {"value": "undecidable"},
     "explanation": "Turing proved no general algorithm decides halting for all program-input pairs.", "difficulty": "intermediate"},
]


def _from_bank(db: Session, quiz: models.QuizSet, topics: list[models.Topic], count: int) -> int:
    created = 0
    for topic in topics:
        for item in BANK:
            if created >= count:
                return created
            if item["match"] not in topic.name.lower():
                continue
            db.add(
                models.Question(
                    quiz_set_id=quiz.id,
                    topic_id=topic.id,
                    qtype=item["qtype"],
                    stem=item["stem"],
                    options=item["options"],
                    answer=item["answer"],
                    explanation=item["explanation"],
                    difficulty=item["difficulty"],
                    marks=1.0,
                )
            )
            created += 1
    return created


def bank_has(topic: models.Topic) -> bool:
    return any(item["match"] in topic.name.lower() for item in BANK)


# --------------------------------------------------------------------------- grading
def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", str(text).lower()).split()


def _keyword_coverage(keywords: list[str], response: str) -> float:
    if not keywords:
        return 0.0
    words = set(_norm(response))
    hits = 0
    for kw in keywords:
        parts = set(_norm(kw))
        if parts and parts.issubset(words):
            hits += 1
    return hits / len(keywords)


def grade(question: models.Question, response: dict, llm: LLM | None = None) -> dict:
    """Deterministic wherever it can be. Returns correct/awarded/feedback/graded_by."""
    value = response.get("value")
    answer = question.answer or {}
    qtype = question.qtype

    if qtype in ("mcq", "truefalse"):
        ok = str(value) == str(answer.get("value"))
        return {
            "correct": ok,
            "awarded": question.marks if ok else 0.0,
            "feedback": question.explanation if ok else f"Correct answer: {answer.get('value')}. {question.explanation}",
            "graded_by": "rule",
        }

    if qtype == "multi":
        chosen = {str(v) for v in (value or [])}
        expected = {str(v) for v in (answer.get("value") or [])}
        ok = chosen == expected
        partial = len(chosen & expected) / len(expected) if expected else 0.0
        return {
            "correct": ok,
            "awarded": round(question.marks * (1.0 if ok else max(0.0, partial - 0.25 * len(chosen - expected))), 2),
            "feedback": ("All correct options selected." if ok else f"Expected {sorted(expected)}.")
            + (f" {question.explanation}" if question.explanation else ""),
            "graded_by": "rule",
        }

    if qtype == "numerical":
        try:
            got = float(value)
            want = float(answer.get("value"))
        except (TypeError, ValueError):
            return {"correct": False, "awarded": 0.0, "feedback": "Not a number.", "graded_by": "rule"}
        tol = float(answer.get("tolerance") or 0.0)
        ok = abs(got - want) <= tol + 1e-9
        return {
            "correct": ok,
            "awarded": question.marks if ok else 0.0,
            "feedback": ("Correct." if ok else f"Expected {want}.") + (f" {question.explanation}" if question.explanation else ""),
            "graded_by": "rule",
        }

    # written answers
    text = str(value or "")
    if len(text.split()) < 3:
        return {"correct": False, "awarded": 0.0, "feedback": "Too short to assess.", "graded_by": "rule"}

    keywords = answer.get("keywords") or []
    if keywords:
        coverage = _keyword_coverage(keywords, text)
        ok = coverage >= 0.6
        missed = [k for k in keywords if not set(_norm(k)).issubset(set(_norm(text)))]
        return {
            "correct": ok,
            "awarded": round(question.marks * coverage, 2),
            "feedback": (
                f"Covered {round(coverage * 100)}% of the expected concepts."
                + (f" Missing: {', '.join(missed[:4])}." if missed else "")
                + (f" {question.explanation}" if question.explanation else "")
            ),
            "graded_by": "rule",
        }

    if llm and llm.enabled:
        try:
            data = llm.complete_json(
                "You grade an exam answer against a rubric. Be strict but fair. "
                'Return JSON {"score":0..1,"correct":bool,"feedback":"one or two sentences"}.',
                f"Question: {question.stem}\nExpected: {question.explanation}\nStudent answer: {text}",
            )
            score = max(0.0, min(1.0, float(data.get("score", 0))))
            return {
                "correct": bool(data.get("correct", score >= 0.6)),
                "awarded": round(question.marks * score, 2),
                "feedback": str(data.get("feedback", ""))[:400],
                "graded_by": "llm",
            }
        except (LLMError, ValueError, TypeError):
            pass

    return {
        "correct": None,
        "awarded": 0.0,
        "feedback": "Descriptive answer saved for review — no rubric and no model available to grade it.",
        "graded_by": "pending",
    }


# --------------------------------------------------------------------------- attempt flow
def submit_attempt(db: Session, student_id: int, quiz_set_id: int, responses: dict[str, dict], llm: LLM) -> dict:
    quiz = db.get(models.QuizSet, quiz_set_id)
    if quiz is None or quiz.student_id != student_id:
        raise ValueError("quiz not found")
    questions = list(db.scalars(select(models.Question).where(models.Question.quiz_set_id == quiz_set_id)))
    if not questions:
        raise ValueError("quiz has no questions")

    attempt = models.Attempt(
        quiz_set_id=quiz_set_id,
        student_id=student_id,
        submitted_at=utcnow(),
        max_score=sum(q.marks for q in questions),
    )
    db.add(attempt)
    db.flush()

    graded = []
    for q in questions:
        response = responses.get(str(q.id), {})
        result = grade(q, response, llm)
        db.add(
            models.Answer(
                attempt_id=attempt.id,
                question_id=q.id,
                response=response,
                correct=result["correct"],
                awarded=result["awarded"],
                feedback=result["feedback"],
                graded_by=result["graded_by"],
            )
        )
        attempt.score += result["awarded"]
        if q.topic_id and result["correct"] is not None:
            memory.record_evidence(db, student_id, q.topic_id, result["correct"], q.difficulty)
        graded.append(
            {
                "question_id": q.id,
                "stem": q.stem,
                "qtype": q.qtype,
                "correct": result["correct"],
                "awarded": result["awarded"],
                "marks": q.marks,
                "feedback": result["feedback"],
                "graded_by": result["graded_by"],
                "correct_answer": q.answer,
                "explanation": q.explanation,
            }
        )

    db.commit()
    accuracy = round(100 * attempt.score / attempt.max_score, 1) if attempt.max_score else 0.0
    return {
        "attempt_id": attempt.id,
        "score": round(attempt.score, 2),
        "max_score": attempt.max_score,
        "accuracy_pct": accuracy,
        "results": graded,
        "weakest_topics": [w["topic"] for w in memory.weak_topics(db, student_id, 3)],
    }
