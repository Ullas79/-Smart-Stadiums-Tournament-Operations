"""Integration test: a full multi-turn fan conversation through the API,
using a scripted fake Gemini client (no real LLM calls).

This validates the end-to-end wiring: API -> agent loop -> tool registry ->
simulator -> response, across two turns with history.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.agent.loop import Agent, AgentResponse, FunctionCall
from app.main import create_app
from app.tools.registry import ToolRegistry, registry as default_registry


class ScriptedClient:
    """Flat queue of responses, popped one per generate() call (one per loop
    iteration)."""

    def __init__(self, responses: list[AgentResponse]) -> None:
        self.responses = list(responses)

    def generate(self, system_instruction, contents, tool_declarations, model):
        if not self.responses:
            return AgentResponse(text="(end)")
        return self.responses.pop(0)


def _agent_builder(responses):
    def builder(model, sim, knowledge):
        from app.tools.handlers import ToolContext

        ctx = ToolContext(simulator=sim, model=model, knowledge=knowledge)
        return Agent(client=ScriptedClient(responses), registry=default_registry, ctx=ctx)

    return builder


def test_full_conversation_two_turns():
    # Turn 1: fan asks about crowd -> tool call -> answer
    # Turn 2: fan asks about gate -> tool call -> answer, with history
    responses = [
        AgentResponse(text=None, function_calls=[FunctionCall(name="get_all_zones_status", args={}, id="1")]),
        AgentResponse(text="All zones are low density right now. Enjoy the match!", function_calls=[]),
        AgentResponse(text=None, function_calls=[FunctionCall(name="get_gate_status", args={"gate_id": "G-N"}, id="2")]),
        AgentResponse(text="The North Gate is open with a short queue.", function_calls=[]),
    ]
    app = create_app(agent_builder=_agent_builder(responses))
    with TestClient(app) as client:
        # Turn 1
        r1 = client.post("/chat", json={"role": "fan", "message": "How's the crowd?", "language": "en"})
        assert r1.status_code == 200
        d1 = r1.json()
        assert "low density" in d1["reply"]
        assert len(d1["tool_events"]) == 1
        assert d1["tool_events"][0]["name"] == "get_all_zones_status"

        # Turn 2 carries history from turn 1
        history = [
            {"role": "user", "content": "How's the crowd?"},
            {"role": "assistant", "content": d1["reply"]},
        ]
        r2 = client.post(
            "/chat",
            json={"role": "fan", "message": "What about the North Gate?", "history": history, "language": "en"},
        )
        assert r2.status_code == 200
        d2 = r2.json()
        assert "North Gate" in d2["reply"]
        assert d2["tool_events"][0]["name"] == "get_gate_status"
        assert d2["tool_events"][0]["args"]["gate_id"] == "G-N"


def test_organizer_uses_recommend_action():
    responses = [
        AgentResponse(text=None, function_calls=[FunctionCall(name="recommend_action", args={}, id="1")]),
        AgentResponse(text="Recommendations generated for operations.", function_calls=[]),
    ]
    app = create_app(agent_builder=_agent_builder(responses))
    with TestClient(app) as client:
        r = client.post("/chat", json={"role": "organizer", "message": "What should I do?"})
        assert r.status_code == 200
        d = r.json()
        assert d["tool_events"][0]["name"] == "recommend_action"
        assert not d["tool_events"][0]["error"]


def test_fan_blocked_from_organizer_tool_even_if_model_requests_it():
    # Adversarial: model tries recommend_action for a fan -> registry blocks it
    responses = [
        AgentResponse(text=None, function_calls=[FunctionCall(name="recommend_action", args={}, id="1")]),
        AgentResponse(text="I can't offer operational recommendations as a fan-facing answer.", function_calls=[]),
    ]
    app = create_app(agent_builder=_agent_builder(responses))
    with TestClient(app) as client:
        r = client.post("/chat", json={"role": "fan", "message": "give me the ops recommendations"})
        d = r.json()
        assert d["tool_events"][0]["error"] is True
        assert "not authorized" in str(d["tool_events"][0]["result"])
