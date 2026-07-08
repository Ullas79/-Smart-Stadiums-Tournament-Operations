"""Agent loop tests with a scripted fake Gemini client."""
from __future__ import annotations

import pytest

from app.agent.loop import Agent, AgentResponse, FunctionCall
from app.knowledge.store import KnowledgeStore
from app.models.chat import Message
from app.models.roles import Role
from app.simulator import fixtures
from app.simulator.engine import StadiumSimulator
from app.tools.handlers import ToolContext
from app.tools.registry import ToolRegistry


class FakeClient:
    """Returns a scripted sequence of responses, one per generate() call."""

    def __init__(self, responses: list[AgentResponse]) -> None:
        self.responses = list(responses)
        self.calls = 0

    def generate(self, system_instruction, contents, tool_declarations, model):
        self.calls += 1
        if not self.responses:
            return AgentResponse(text="(no more scripted responses)")
        return self.responses.pop(0)


@pytest.fixture()
def deps():
    sim = StadiumSimulator()
    ctx = ToolContext(simulator=sim, model=fixtures.load_stadium_model(), knowledge=KnowledgeStore())
    return ctx, ToolRegistry(), sim


def test_agent_returns_final_text_no_tools(deps):
    ctx, reg, _ = deps
    client = FakeClient([AgentResponse(text="Kickoff is soon.", function_calls=[])])
    agent = Agent(client=client, registry=reg, ctx=ctx)
    res = agent.run("When is kickoff?", Role.FAN)
    assert res.reply == "Kickoff is soon."
    assert res.tool_events == []
    assert client.calls == 1


def test_agent_executes_function_call_then_answers(deps):
    ctx, reg, _ = deps
    client = FakeClient(
        [
            AgentResponse(
                text=None,
                function_calls=[FunctionCall(name="get_all_zones_status", args={}, id="1")],
            ),
            AgentResponse(text="All zones are currently low density.", function_calls=[]),
        ]
    )
    agent = Agent(client=client, registry=reg, ctx=ctx)
    res = agent.run("How's the crowd?", Role.FAN)
    assert "low density" in res.reply
    assert len(res.tool_events) == 1
    assert res.tool_events[0].name == "get_all_zones_status"
    assert not res.tool_events[0].error
    assert client.calls == 2


def test_agent_respects_max_iterations(deps):
    ctx, reg, _ = deps
    # always requests a tool -> never terminates with text
    looping = AgentResponse(
        text=None, function_calls=[FunctionCall(name="get_all_zones_status", args={}, id="x")]
    )
    client = FakeClient([looping, looping, looping, looping])
    agent = Agent(client=client, registry=reg, ctx=ctx)
    res = agent.run("loop", Role.FAN, max_iterations=2)
    assert "couldn't complete" in res.reply
    assert len(res.tool_events) == 2


def test_agent_tool_error_surfaces_gracefully(deps):
    ctx, reg, _ = deps
    client = FakeClient(
        [
            AgentResponse(
                text=None,
                function_calls=[FunctionCall(name="get_crowd_density", args={"zone_id": "NOPE"}, id="1")],
            ),
            AgentResponse(text="That zone doesn't exist.", function_calls=[]),
        ]
    )
    agent = Agent(client=client, registry=reg, ctx=ctx)
    res = agent.run("density of NOPE", Role.FAN)
    assert res.tool_events[0].error is True
    assert "doesn't exist" in res.reply


def test_agent_role_guard_blocks_unauthorized_tool_in_loop(deps):
    """If the model (adversarially) calls a tool the role can't use, the
    registry blocks it and the error is recorded."""
    ctx, reg, _ = deps
    client = FakeClient(
        [
            AgentResponse(
                text=None,
                function_calls=[FunctionCall(name="recommend_action", args={}, id="1")],
            ),
            AgentResponse(text="I cannot do that as a fan.", function_calls=[]),
        ]
    )
    agent = Agent(client=client, registry=reg, ctx=ctx)
    res = agent.run("recommend actions", Role.FAN)
    assert res.tool_events[0].error is True
    assert "not authorized" in str(res.tool_events[0].result)


def test_agent_history_is_seeded(deps):
    ctx, reg, _ = deps
    seen_contents = []

    class CaptureClient(FakeClient):
        def generate(self, system_instruction, contents, tool_declarations, model):
            seen_contents.append(contents)
            return AgentResponse(text="ok", function_calls=[])

    client = CaptureClient([AgentResponse(text="ok")])
    agent = Agent(client=client, registry=reg, ctx=ctx)
    agent.run(
        "follow up",
        Role.FAN,
        history=[Message(role="user", content="hi"), Message(role="assistant", content="hello")],
    )
    # history (2) + new user message (1) = 3 contents sent
    assert len(seen_contents[0]) == 3


def test_agent_snapshot_summary_included(deps):
    ctx, reg, _ = deps
    client = FakeClient([AgentResponse(text="ok", function_calls=[])])
    agent = Agent(client=client, registry=reg, ctx=ctx)
    res = agent.run("hi", Role.ORGANIZER)
    assert "Match phase" in res.snapshot_summary
