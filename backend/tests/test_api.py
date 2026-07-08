"""API route tests using FastAPI TestClient + a fake agent."""
from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

from app.agent.loop import AgentResult
from app.main import create_app


@dataclass
class FakeAgent:
    reply: str = "Sure thing."
    events: list = None

    def run(self, message, role, history=None, language="en"):
        from app.models.chat import ToolEvent

        return AgentResult(
            reply=self.reply,
            tool_events=self.events or [],
            snapshot_summary="Match phase: arrival. sim time.",
        )


def _app_with_fake_agent(reply="Hello from fake agent."):
    def builder(model, sim, knowledge):
        return FakeAgent(reply=reply)

    return create_app(agent_builder=builder)


def test_health():
    app = _app_with_fake_agent()
    with TestClient(app) as client:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


def test_get_roles():
    app = _app_with_fake_agent()
    with TestClient(app) as client:
        r = client.get("/role")
        assert r.status_code == 200
        data = r.json()
        roles = {x["role"] for x in data["roles"]}
        assert roles == {"fan", "volunteer", "organizer"}
        fan = next(x for x in data["roles"] if x["role"] == "fan")
        assert "recommend_action" not in fan["tools"]
        org = next(x for x in data["roles"] if x["role"] == "organizer")
        assert "recommend_action" in org["tools"]


def test_get_state():
    app = _app_with_fake_agent()
    with TestClient(app) as client:
        r = client.get("/state")
        assert r.status_code == 200
        data = r.json()
        assert data["venue_name"] == "MetLife Stadium"
        assert "crowd" in data and len(data["crowd"]) == 12
        assert "gates" in data


def test_chat_returns_fake_reply():
    app = _app_with_fake_agent(reply="Kickoff is at the scheduled time.")
    with TestClient(app) as client:
        r = client.post("/chat", json={"role": "fan", "message": "When is kickoff?", "language": "en"})
        assert r.status_code == 200
        data = r.json()
        assert data["reply"] == "Kickoff is at the scheduled time."
        assert data["role"] == "fan"
        assert "Match phase" in data["snapshot_summary"]


def test_chat_with_history():
    app = _app_with_fake_agent()
    with TestClient(app) as client:
        r = client.post(
            "/chat",
            json={
                "role": "organizer",
                "message": "Any incidents?",
                "history": [
                    {"role": "user", "content": "hi"},
                    {"role": "assistant", "content": "hello"},
                ],
                "language": "en",
            },
        )
        assert r.status_code == 200
        assert r.json()["role"] == "organizer"


def test_chat_invalid_role_rejected():
    app = _app_with_fake_agent()
    with TestClient(app) as client:
        r = client.post("/chat", json={"role": "admin", "message": "hi"})
        assert r.status_code == 422
