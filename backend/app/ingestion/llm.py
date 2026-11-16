"""Compatibility shim: the syllabus extractor imports its provider from here."""
from __future__ import annotations

from ..agents.llm import LLM, LLMError, StubLLM, get_llm  # noqa: F401
