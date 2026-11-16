import os
import pathlib

DB = pathlib.Path(__file__).parent / "test_preppilot.db"
if DB.exists():
    DB.unlink()

# must be set before app.config is imported
os.environ["DATABASE_URL"] = f"sqlite:///{DB}"
os.environ["AUTO_SEED"] = "false"
os.environ["LLM_PROVIDER"] = "stub"
os.environ["SOLVER_TIME_LIMIT_S"] = "5"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough-for-hs256"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import init_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema():
    init_db()
    yield
    if DB.exists():
        DB.unlink()


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth(client):
    """A logged-in student with a syllabus, availability and a plan."""
    r = client.post(
        "/api/auth/register",
        json={"email": f"student{os.urandom(4).hex()}@test.app", "password": "testpass123", "name": "Test Student"},
    )
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    client.post(
        "/api/onboarding",
        headers=headers,
        json={
            "profile": {"name": "Test Student", "daily_minutes": 240},
            "windows": [{"weekday": d, "start_min": 18 * 60, "end_min": 22 * 60} for d in range(5)],
        },
    )
    return {"client": client, "headers": headers, "token": token, "student": r.json()["student"]}
