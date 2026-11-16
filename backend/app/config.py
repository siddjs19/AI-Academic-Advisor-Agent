"""Runtime configuration. Every value has a free-tier-safe default."""
from __future__ import annotations

import os
from dataclasses import dataclass


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./preppilot.db")

    # auth
    secret_key: str = os.getenv("SECRET_KEY", "dev-only-insecure-secret-change-me")
    jwt_algorithm: str = "HS256"
    jwt_days: int = _int("JWT_DAYS", 7)

    # llm: stub | gemini | groq | openai
    llm_provider: str = os.getenv("LLM_PROVIDER", "stub")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "gemini-2.0-flash")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "")  # for openai-compatible servers

    # planner
    horizon_days: int = _int("HORIZON_DAYS", 28)
    slot_minutes: int = _int("SLOT_MINUTES", 30)
    max_minutes_per_day: int = _int("MAX_MINUTES_PER_DAY", 240)
    max_course_minutes_per_day: int = _int("MAX_COURSE_MINUTES_PER_DAY", 150)
    churn_bonus: int = _int("CHURN_BONUS", 400)
    min_block_slots: int = _int("MIN_BLOCK_SLOTS", 2)
    solver_time_limit_s: float = _float("SOLVER_TIME_LIMIT_S", 10.0)

    # demo data + first-boot bootstrap
    auto_seed: bool = _bool("AUTO_SEED", True)
    demo_email: str = os.getenv("DEMO_EMAIL", "demo@preppilot.app")
    demo_password: str = os.getenv("DEMO_PASSWORD", "demo1234")

    @property
    def llm_enabled(self) -> bool:
        return self.llm_provider != "stub" and bool(self.llm_api_key)


settings = Settings()
