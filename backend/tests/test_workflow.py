"""End-to-end workflows from the brief, exercised through the real HTTP API."""
SYLLABUS = """CS305 Compiler Design
Unit 1: Lexical analysis and tokens (25%)
Unit 2: Parsing and grammars (30%)
Unit 3: Intermediate code generation (25%)
Unit 4: Optimisation passes (20%)
Mid-semester exam: 30/11/2026
End-semester exam: 20/12/2026
"""


def _setup(auth):
    c, h = auth["client"], auth["headers"]
    r = c.post("/api/syllabus/parse", headers=h, data={"text": SYLLABUS})
    assert r.status_code == 200, r.text
    draft = r.json()["draft"]
    r = c.post("/api/syllabus/confirm", headers=h, json={"draft": draft})
    assert r.status_code == 200, r.text
    return draft


def test_workflow_1_onboarding_and_syllabus(auth):
    draft = _setup(auth)
    assert len(draft["topics"]) >= 4
    courses = auth["client"].get("/api/courses", headers=auth["headers"]).json()["courses"]
    assert len(courses) == 1
    assert courses[0]["code"] == "CS305" or courses[0]["name"].startswith("CS305")
    assert len(courses[0]["topics"]) >= 4


def test_workflow_5_planning_and_rescheduling(auth):
    _setup(auth)
    c, h = auth["client"], auth["headers"]
    plan = c.post("/api/plan/build", headers=h).json()
    assert plan["blocks"] > 0
    assert plan["status"] in {"ok", "partial", "overloaded"}

    current = c.get("/api/plan", headers=h).json()
    assert current["blocks"]
    block_id = current["blocks"][0]["id"]
    assert c.post(f"/api/blocks/{block_id}/log?done=true", headers=h).status_code == 200

    diff = c.post("/api/plan/replan", headers=h).json()
    assert "blocks_kept" in diff


def test_workflow_3_assessment_updates_memory(auth):
    _setup(auth)
    c, h = auth["client"], auth["headers"]
    courses = c.get("/api/courses", headers=h).json()["courses"]
    topic = courses[0]["topics"][0]

    before = topic["mastery"]
    gen = c.post("/api/practice/generate", headers=h, json={"topic_ids": [topic["id"]], "count": 3})
    if gen.status_code == 409:  # no bank entry and no model: honest refusal
        assert "no model" in gen.json()["detail"].lower() or "sample-bank" in gen.json()["detail"].lower()
        return

    quiz = gen.json()
    assert quiz["questions"], "a generated set must contain questions"
    assert all("answer" not in q for q in quiz["questions"]), "answers must not leak to the client"

    responses = {str(q["id"]): {"value": (q["options"][0] if q["options"] else "x")} for q in quiz["questions"]}
    result = c.post(f"/api/practice/{quiz['quiz_set_id']}/submit", headers=h, json={"responses": responses}).json()
    assert result["max_score"] > 0
    assert len(result["results"]) == len(quiz["questions"])
    assert all(r["graded_by"] in {"rule", "llm", "pending"} for r in result["results"])

    after = c.get("/api/courses", headers=h).json()["courses"][0]["topics"][0]
    assert after["evidence"]["attempts"] > 0
    assert after["mastery"] != before or result["accuracy_pct"] == 0


def test_workflow_6_viva_turn_taking(auth):
    _setup(auth)
    c, h = auth["client"], auth["headers"]
    topic = c.get("/api/courses", headers=h).json()["courses"][0]["topics"][0]

    started = c.post("/api/viva/start", headers=h, json={"topic_id": topic["id"]})
    assert started.status_code == 200
    session = started.json()
    assert session["question"]

    turn = c.post(
        f"/api/viva/{session['session_id']}/answer",
        headers=h,
        json={"answer": "Lexical analysis converts characters into tokens. It removes whitespace and comments first."},
    ).json()
    assert 0.0 <= turn["score"] <= 1.0
    assert turn["feedback"]

    history = c.get("/api/viva/history", headers=h).json()["sessions"]
    assert len(history) == 1


def test_workflow_7_revision_queue(auth):
    _setup(auth)
    c, h = auth["client"], auth["headers"]
    topic = c.get("/api/courses", headers=h).json()["courses"][0]["topics"][0]

    made = c.post("/api/revision/generate", headers=h, json={"topic_ids": [topic["id"]], "count": 3})
    if made.status_code == 409:
        return  # nothing in the sample bank and no model — the API says so instead of inventing cards

    due = c.get("/api/revision/due", headers=h).json()
    assert due["total_cards"] >= 1
    card = due["cards"][0]
    reviewed = c.post("/api/revision/review", headers=h, json={"card_id": card["id"], "rating": 2})
    assert reviewed.status_code == 200
    assert reviewed.json()["interval_days"] >= 1


def test_workflow_8_proactive_recommendations(auth):
    _setup(auth)
    c, h = auth["client"], auth["headers"]
    recs = c.get("/api/recommendations", headers=h).json()["recommendations"]
    assert isinstance(recs, list)
    if recs:
        rec = recs[0]
        assert rec["severity"] in {"info", "warn", "critical"}
        assert rec["action"]["type"]
        acted = c.post(f"/api/recommendations/{rec['id']}/act", headers=h, json={"status": "dismissed"})
        assert acted.json()["status"] == "dismissed"
        remaining = c.get("/api/recommendations", headers=h).json()["recommendations"]
        assert all(r["id"] != rec["id"] for r in remaining)


def test_advisor_routes_intents(auth):
    _setup(auth)
    c, h = auth["client"], auth["headers"]
    for message, expected in [
        ("make me a study plan", {"plan", "replan"}),
        ("how am I doing overall?", {"analytics", "status"}),
        ("I missed two sessions", {"replan"}),
    ]:
        body = c.post("/api/advisor/chat", headers=h, json={"message": message}).json()
        assert body["intent"] in expected, (message, body["intent"])
        assert body["answer"]

    history = c.get("/api/advisor/history", headers=h).json()["messages"]
    assert len(history) >= 6


def test_tutor_is_honest_without_a_model(auth):
    _setup(auth)
    c, h = auth["client"], auth["headers"]
    body = c.post("/api/tutor/ask", headers=h, json={"question": "explain lexical analysis"}).json()
    assert body["answer"]
    if body["llm_required"]:
        assert "LLM_PROVIDER" in body["answer"]
