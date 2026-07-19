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
        assert roles == {"fan", "volunteer", "organizer", "staff"}
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
        assert r.status_code == 403


def test_dispatch_and_resolve_api():
    app = create_app()
    with TestClient(app) as client:
        # Trigger an incident to have something to dispatch
        r_inj = client.post("/simulator/scenario", json={"scenario": "medical_emergency"})
        assert r_inj.status_code == 200
        incident_id = r_inj.json()["incident"]["incident_id"]

        # Test dispatch
        r_disp = client.post("/api/incidents/dispatch", json={
            "incident_id": incident_id,
            "volunteer_id": "V-TEST-1",
            "assigned_staff": "Staff-John"
        })
        assert r_disp.status_code == 200
        data = r_disp.json()
        assert data["status"] == "success"
        assert "Staff-John" in data["incident"]["description"]
        assert data["incident"]["assigned_staff"] == "Staff-John"

        # Test resolve
        r_res = client.post("/api/incidents/resolve", json={
            "incident_id": incident_id
        })
        assert r_res.status_code == 200
        data = r_res.json()
        assert data["status"] == "success"
        assert data["incident"]["status"] == "resolved"

        # Test resolve already resolved
        r_res_again = client.post("/api/incidents/resolve", json={
            "incident_id": incident_id
        })
        assert r_res_again.status_code == 400

        # Test dispatch already resolved
        r_disp_again = client.post("/api/incidents/dispatch", json={
            "incident_id": incident_id,
            "volunteer_id": "V-TEST-2",
            "assigned_staff": "Staff-Jane"
        })
        assert r_disp_again.status_code == 400


def test_staff_tool_handlers():
    from app.tools.registry import registry
    from app.tools.handlers import ToolContext
    from app.simulator.engine import StadiumSimulator
    from app.models.roles import Role
    
    sim = StadiumSimulator()
    ctx = ToolContext(simulator=sim, model=sim.model, knowledge=None)
    
    # 1. Test set_gate_status handler
    # Check default status is open
    assert sim._gates["G-N"].status == "open"
    res_gate = registry.execute("set_gate_status", {"gate_id": "G-N", "status": "restricted"}, Role.STAFF, ctx)
    assert res_gate["status"] == "restricted"
    assert sim._gates["G-N"].status == "restricted"

    # 2. Test mitigate_bottleneck handler
    sim._crowd["L-N"].occupancy = 100
    sim._crowd["L-N"].capacity = 100
    sim._crowd["L-N"].density = 1.0
    res_mit = registry.execute("mitigate_bottleneck", {"zone_id": "L-N", "strategy": "divert"}, Role.STAFF, ctx)
    assert res_mit["new_occupancy"] == 75
    assert res_mit["new_density"] == 0.75
    assert sim._crowd["L-N"].occupancy == 75

    # 3. Test dispatch_staff handler
    inc = sim.report_incident("medical", "Gate A", "high", "Test incident")
    res_disp = registry.execute("dispatch_staff", {"incident_id": inc.incident_id, "assigned_staff": "S-1"}, Role.STAFF, ctx)
    assert "S-1" in res_disp["description"]

