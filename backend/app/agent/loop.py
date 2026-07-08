"""Function-calling agent loop.

The loop is synchronous and SDK-agnostic: it depends on a `generate` callable
that accepts a normalized contents representation and returns an
`AgentResponse`. `app.core.gemini.RealGeminiClient` adapts this to the
google-genai SDK; tests inject a fake.

Loop:
  1. Build role-aware system prompt from the live snapshot.
  2. Send the conversation (with the role's tool declarations) to Gemini.
  3. If Gemini returns function calls, execute each via the tool registry
     (server-side role guard), append the function responses, and repeat.
  4. Stop when Gemini returns a final text answer, or the max iteration count
     is reached (return a graceful fallback).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..core.config import settings
from ..models.chat import Message, ToolEvent
from ..models.roles import Role
from ..models.state import StadiumSnapshot
from ..tools.handlers import ToolContext
from ..tools.registry import ToolRegistry
from .prompt import build_system_prompt


@dataclass
class FunctionCall:
    name: str
    args: dict
    id: str = ""


@dataclass
class AgentResponse:
    text: str | None = None
    function_calls: list[FunctionCall] = field(default_factory=list)


# A normalized "part" is one of:
#   {"text": str}
#   {"function_call": {"name": str, "args": dict, "id": str}}
#   {"function_response": {"name": str, "response": dict}}
# A content item is {"role": "user"|"model", "parts": [part, ...]}.
Contents = list[dict]


class GeminiClientProtocol:
    def generate(
        self,
        system_instruction: str,
        contents: Contents,
        tool_declarations: list,
        model: str,
    ) -> AgentResponse:  # pragma: no cover - interface only
        raise NotImplementedError


@dataclass
class AgentResult:
    reply: str
    tool_events: list[ToolEvent]
    snapshot_summary: str


class Agent:
    def __init__(
        self,
        client: GeminiClientProtocol,
        registry: ToolRegistry,
        ctx: ToolContext,
    ) -> None:
        self.client = client
        self.registry = registry
        self.ctx = ctx

    def run(
        self,
        message: str,
        role: Role,
        history: list[Message] | None = None,
        language: str = "en",
        max_iterations: int | None = None,
    ) -> AgentResult:
        snapshot: StadiumSnapshot = self.ctx.snapshot()
        system_instruction = build_system_prompt(role, snapshot, language)
        tool_declarations = self.registry.declarations_for_role(role)
        max_iters = max_iterations or settings.agent_max_tool_iterations

        contents: Contents = self._seed_history(history)
        contents.append({"role": "user", "parts": [{"text": message}]})

        events: list[ToolEvent] = []
        for _ in range(max_iters):
            response = self.client.generate(
                system_instruction=system_instruction,
                contents=contents,
                tool_declarations=tool_declarations,
                model=settings.gemini_model,
            )
            if not response.function_calls:
                return AgentResult(
                    reply=response.text or "",
                    tool_events=events,
                    snapshot_summary=snapshot.summary(),
                )
            # record the model's function-call turn
            model_parts: list[dict] = []
            for fc in response.function_calls:
                model_parts.append({"function_call": {"name": fc.name, "args": fc.args, "id": fc.id}})
            contents.append({"role": "model", "parts": model_parts})

            # execute each call and append responses
            response_parts: list[dict] = []
            for fc in response.function_calls:
                result = self.registry.execute(fc.name, fc.args or {}, role, self.ctx)
                error = isinstance(result, dict) and "error" in result
                events.append(ToolEvent(name=fc.name, args=fc.args or {}, result=result, error=error))
                response_parts.append({"function_response": {"name": fc.name, "response": result}})
            contents.append({"role": "user", "parts": response_parts})

        # exceeded max iterations
        return AgentResult(
            reply=(
                "I'm working on that but couldn't complete the lookup in time. "
                "Here's what I know so far based on live stadium state: "
                + snapshot.summary()
            ),
            tool_events=events,
            snapshot_summary=snapshot.summary(),
        )

    def _seed_history(self, history: list[Message] | None) -> Contents:
        contents: Contents = []
        for m in history or []:
            if not m.content:
                continue
            contents.append({"role": m.role, "parts": [{"text": m.content}]})
        return contents
