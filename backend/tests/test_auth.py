"""Auth: registration, login, logout revocation, and cross-account isolation."""
import os


def _register(client, email=None, password="testpass123"):
    email = email or f"u{os.urandom(4).hex()}@test.app"
    r = client.post("/api/auth/register", json={"email": email, "password": password, "name": "A"})
    assert r.status_code == 200, r.text
    return email, password, r.json()


def test_register_and_me(client):
    email, _, body = _register(client)
    headers = {"Authorization": f"Bearer {body['token']}"}
    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["name"] == "A"
    assert me.json()["onboarded"] is False


def test_duplicate_email_rejected(client):
    email, _, _ = _register(client)
    r = client.post("/api/auth/register", json={"email": email, "password": "testpass123", "name": "B"})
    assert r.status_code == 409


def test_short_password_rejected(client):
    r = client.post("/api/auth/register", json={"email": "x@test.app", "password": "short", "name": "B"})
    assert r.status_code == 422


def test_login_wrong_password(client):
    email, _, _ = _register(client)
    r = client.post("/api/auth/login", json={"email": email, "password": "nottherightone"})
    assert r.status_code == 401


def test_unknown_account_login_is_401_not_404(client):
    """Never leak whether an email exists."""
    r = client.post("/api/auth/login", json={"email": "ghost@test.app", "password": "testpass123"})
    assert r.status_code == 401


def test_missing_token_is_401(client):
    assert client.get("/api/dashboard").status_code == 401
    assert client.get("/api/dashboard", headers={"Authorization": "Bearer nonsense"}).status_code == 401


def test_logout_revokes_every_existing_token(client):
    _, _, body = _register(client)
    headers = {"Authorization": f"Bearer {body['token']}"}
    assert client.get("/api/dashboard", headers=headers).status_code == 200

    assert client.post("/api/auth/logout", headers=headers).status_code == 200
    # same token, now stale: the token_version bump invalidates it
    assert client.get("/api/dashboard", headers=headers).status_code == 401

    # and a fresh login works again
    email, password, _ = _register(client)
    again = client.post("/api/auth/login", json={"email": email, "password": password})
    assert again.status_code == 200
    fresh = {"Authorization": f"Bearer {again.json()['token']}"}
    assert client.get("/api/dashboard", headers=fresh).status_code == 200


def test_students_cannot_read_each_others_courses(client):
    _, _, a = _register(client)
    _, _, b = _register(client)
    ha = {"Authorization": f"Bearer {a['token']}"}
    hb = {"Authorization": f"Bearer {b['token']}"}

    client.post(
        "/api/syllabus/confirm",
        headers=ha,
        json={"draft": {
            "course": {"name": "A's Private Course", "code": "XX1"},
            "topics": [{"name": "Secret topic", "est_hours": 2, "difficulty": 3, "weight_pct": 50}],
            "assessments": [{"kind": "exam", "title": "Final", "due_at": "2026-12-20T09:00:00", "weight_pct": 100}],
        }},
    )
    a_courses = client.get("/api/courses", headers=ha).json()["courses"]
    b_courses = client.get("/api/courses", headers=hb).json()["courses"]
    assert len(a_courses) == 1
    assert b_courses == []

    course_id = a_courses[0]["id"]
    assert client.delete(f"/api/courses/{course_id}", headers=hb).status_code == 404
    assert client.delete(f"/api/courses/{course_id}", headers=ha).status_code == 200
