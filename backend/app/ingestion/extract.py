"""Syllabus -> structured JSON.

Two paths, same output contract:
  * real LLM  -> schema-constrained JSON extraction
  * StubLLM   -> deterministic regex extraction (no key, no network)

Neither path is trusted: everything comes back with a per-field confidence and
a `needs_review` flag, and nothing is written to the database until the student
confirms. A wrong exam date poisons every downstream decision, so the confirm
step is not optional.
"""
from __future__ import annotations

import io
import re
from datetime import datetime
from typing import Any

from .llm import LLM, StubLLM

MAX_PAGES = 40

SYLLABUS_SYSTEM = """You extract structured course data from a syllabus document.
Rules:
- Copy dates exactly; never invent a date that is not in the text.
- `weight_pct` is the share of the final grade (0 if unknown).
- `est_hours` is self-study effort, not lecture hours. Estimate 1.5x lecture hours.
- `difficulty` is 1-5, based on prerequisites and abstraction level.
- Put topic names in `topics`, every graded event in `assessments`.
- If a value is missing, use null rather than guessing.
Return JSON only."""

SYLLABUS_USER = """Extract the course name, code, exam date, topics and assessments from
this syllabus text. Schema:

{schema}

Text:
---
{text}
---"""

SCHEMA_HINT = """{
  "course": {"name": str, "code": str|null, "exam_at": "YYYY-MM-DD HH:MM"|null},
  "topics": [{"name": str, "est_hours": float, "difficulty": int, "weight_pct": float}],
  "assessments": [{"kind": "exam|quiz|assignment|midterm", "title": str,
                   "due_at": "YYYY-MM-DD HH:MM", "weight_pct": float}]
}"""


# --------------------------------------------------------------------------
# text in
# --------------------------------------------------------------------------
def pdf_to_text(raw: bytes) -> str:
    """PyMuPDF. Raises a clear error rather than returning garbage."""
    try:
        import pymupdf as fitz  # PyMuPDF >= 1.24
    except ImportError:  # pragma: no cover
        try:
            import fitz  # older PyMuPDF
        except ImportError as exc:
            raise RuntimeError("PyMuPDF is required for PDF ingestion (pip install pymupdf)") from exc

    doc = fitz.open(stream=io.BytesIO(raw), filetype="pdf")
    try:
        if doc.page_count > MAX_PAGES:
            raise ValueError(f"syllabus has {doc.page_count} pages; expected <= {MAX_PAGES}")
        text = "\n".join(page.get_text("text") for page in doc)
    finally:
        doc.close()
    if len(text.strip()) < 40:
        raise ValueError(
            "No extractable text — this looks like a scanned PDF. OCR it first "
            "(ocrmypdf is free) or paste the syllabus as text."
        )
    return text


# --------------------------------------------------------------------------
# deterministic fallback parser
# --------------------------------------------------------------------------
_DATE_PATTERNS = [
    (r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", "dmy"),
    (r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", "ymd"),
    (r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{4})\b", "dMy"),
    (r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{1,2}),?\s+(\d{4})\b", "Mdy"),
]
_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}

_ASSESSMENT_WORDS = re.compile(
    r"\b(exam|examination|midterm|mid-sem|midsem|end-sem|endsem|quiz|test|assignment|viva|practical|project|presentation)\b",
    re.I,
)
_TOPIC_WORDS = re.compile(r"^\s*(unit|module|topic|chapter|part)\s*[-:.]?\s*", re.I)


def _parse_date(text: str) -> datetime | None:
    for pattern, kind in _DATE_PATTERNS:
        m = re.search(pattern, text, re.I)
        if not m:
            continue
        try:
            if kind == "dmy":
                d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            elif kind == "ymd":
                y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            elif kind == "dMy":
                d, mo, y = int(m.group(1)), _MONTHS[m.group(2).lower()[:3]], int(m.group(3))
            else:
                mo, d, y = _MONTHS[m.group(1).lower()[:3]], int(m.group(2)), int(m.group(3))
            return datetime(y, mo, d, 9, 0)
        except (ValueError, KeyError):
            continue
    return None


_DATE_STRIP = re.compile(
    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}-\d{1,2}-\d{1,2}\b"
    r"|\b\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*\d{0,4}\b"
    r"|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},?\s*\d{0,4}\b",
    re.I,
)


def _clean_title(line: str) -> str:
    """Drop the date and dangling separators from an assessment title."""
    cleaned = _DATE_STRIP.sub(" ", line)
    cleaned = re.sub(r"\b(due|on|by|date)\b\s*[:\-]?\s*$", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" -:·|,.")
    return cleaned or line[:120]


def heuristic_extract(text: str) -> dict[str, Any]:
    """Line-oriented parse. Deliberately boring and inspectable."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    topics: list[dict[str, Any]] = []
    assessments: list[dict[str, Any]] = []

    course_name = ""
    for ln in lines[:8]:
        if 4 < len(ln) < 90 and not _ASSESSMENT_WORDS.search(ln) and not _parse_date(ln):
            course_name = ln
            break

    for ln in lines:
        low = ln.lower()
        date = _parse_date(ln)

        if date and _ASSESSMENT_WORDS.search(ln):
            kind = "exam"
            for k in ("quiz", "midterm", "mid-sem", "midsem", "assignment", "viva", "practical", "project"):
                if k in low:
                    kind = "midterm" if "mid" in k else k
                    break
            pct = re.search(r"(\d{1,3})\s*%", ln)
            assessments.append(
                {
                    "kind": kind,
                    "title": _clean_title(ln)[:120],
                    "due_at": date.strftime("%Y-%m-%d %H:%M"),
                    "weight_pct": float(pct.group(1)) if pct else 0.0,
                }
            )
            continue

        is_topic = bool(_TOPIC_WORDS.match(ln)) or bool(re.match(r"^\d+[.)]\s+\S", ln))
        if is_topic and 3 < len(ln) < 160 and not _ASSESSMENT_WORDS.search(ln):
            name = _TOPIC_WORDS.sub("", ln)
            name = re.sub(r"^\d+\s*[.):]\s*", "", name).strip(" -:.")
            pct = re.search(r"\(?\s*(\d{1,3})\s*%\s*\)?", name)
            weight = float(pct.group(1)) if pct else 0.0
            name = re.sub(r"\(?\s*\d{1,3}\s*%\s*\)?", "", name).strip(" -:.")
            hours = re.search(r"(\d{1,2})\s*(?:hrs?|hours?|lectures?|periods?)", name, re.I)
            est = float(hours.group(1)) * 1.5 if hours else 2.0
            if name:
                topics.append(
                    {"name": name[:140], "est_hours": round(est, 2), "difficulty": 3, "weight_pct": weight}
                )

    if not topics:
        # nothing matched: hand back the longest non-date lines as raw topics
        candidates = [ln for ln in lines[1:] if 8 < len(ln) < 120 and not _parse_date(ln)][:12]
        topics = [{"name": c, "est_hours": 2.0, "difficulty": 3, "weight_pct": 0.0} for c in candidates]

    return {
        "course": {"name": course_name or "Untitled course", "code": None, "exam_at": None},
        "topics": topics,
        "assessments": assessments,
    }


# --------------------------------------------------------------------------
# normalisation + confidence
# --------------------------------------------------------------------------
def _norm_date(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(str(value).strip(), fmt)
        except ValueError:
            continue
    return _parse_date(str(value))


def normalise(draft: dict[str, Any], source_text: str = "") -> dict[str, Any]:
    """Clamp, fill defaults, and score confidence per topic."""
    warnings: list[str] = []
    course = draft.get("course") or {}
    exam_at = _norm_date(course.get("exam_at"))

    raw_topics = draft.get("topics") or []
    topics: list[dict[str, Any]] = []
    total_weight = sum(float(t.get("weight_pct") or 0) for t in raw_topics)
    for t in raw_topics:
        name = str(t.get("name") or "").strip()
        if not name:
            continue
        weight = float(t.get("weight_pct") or 0)
        if weight <= 0 and total_weight <= 0:
            weight = round(100.0 / max(len(raw_topics), 1), 2)
        difficulty = int(max(1, min(5, int(t.get("difficulty") or 3))))
        est = float(t.get("est_hours") or 2.0)
        est = round(max(0.5, min(20.0, est)), 2)

        confidence = 1.0
        if not t.get("weight_pct"):
            confidence -= 0.25
        if not t.get("est_hours"):
            confidence -= 0.15
        if len(name) < 4:
            confidence -= 0.2
        confidence = round(max(0.1, confidence), 2)

        topics.append(
            {
                "name": name[:200],
                "est_hours": est,
                "difficulty": difficulty,
                "weight_pct": round(weight, 2),
                "confidence": confidence,
                "needs_review": confidence < 0.8,
            }
        )

    assessments: list[dict[str, Any]] = []
    for a in draft.get("assessments") or []:
        due = _norm_date(a.get("due_at"))
        if due is None:
            warnings.append(f"Dropped assessment with unreadable date: {a.get('title', '?')[:60]}")
            continue
        assessments.append(
            {
                "kind": str(a.get("kind") or "exam")[:40],
                "title": str(a.get("title") or a.get("kind") or "Assessment")[:160],
                "due_at": due,
                "weight_pct": round(float(a.get("weight_pct") or 0), 2),
            }
        )

    if not topics:
        warnings.append("No topics found. Paste the syllabus as text or add topics manually.")
    if not assessments:
        warnings.append("No dates found. Add at least one assessment date, or the planner has no deadlines.")
    if exam_at is None and assessments:
        exam_at = max(a["due_at"] for a in assessments)

    return {
        "course": {"name": str(course.get("name") or "Untitled course")[:160], "code": str(course.get("code") or "")[:40], "exam_at": exam_at},
        "topics": topics,
        "assessments": assessments,
        "warnings": warnings,
        "review_count": sum(1 for t in topics if t["needs_review"]),
    }


def extract_syllabus(text: str, llm: LLM) -> dict[str, Any]:
    """Returns a *draft*. Never writes to the database."""
    if isinstance(llm, StubLLM):
        return normalise(heuristic_extract(text), text)

    prompt = SYLLABUS_USER.format(schema=SCHEMA_HINT, text=text[:60_000])
    try:
        draft = llm.complete_json(SYLLABUS_SYSTEM, prompt)
    except Exception as exc:  # provider hiccup must not lose the upload
        draft = heuristic_extract(text)
        out = normalise(draft, text)
        out["warnings"].append(f"LLM extraction failed ({exc.__class__.__name__}); used the offline parser.")
        return out
    return normalise(draft, text)
