"""Gemini client adapter.

Wraps the `google-genai` SDK behind the simple `GeminiClientProtocol` used by
the agent loop. Converts the loop's normalized contents representation to/from
SDK `types.Content` / `types.Part` objects.

If no API key is configured (tests / offline demo), `make_client` returns a
`OfflineClient` that returns a deterministic fallback response instead of
calling the network.
"""
from __future__ import annotations

from ..core.config import settings
from ..agent.loop import AgentResponse, FunctionCall, GeminiClientProtocol, Contents


def _build_genai_client():
    from google import genai

    if settings.google_genai_use_vertexai:
        return genai.Client(
            vertexai=True,
            project=settings.google_cloud_project,
            location=settings.google_cloud_location,
        )
    if settings.google_api_key and not settings.google_api_key.startswith("test"):
        return genai.Client(api_key=settings.google_api_key)
    return None


def _to_sdk_contents(contents: Contents):
    from google.genai import types

    out = []
    for item in contents:
        parts = []
        for p in item["parts"]:
            if "text" in p:
                parts.append(types.Part.from_text(text=p["text"]))
            elif "function_call" in p:
                fc = p["function_call"]
                parts.append(
                    types.Part.from_function_call(name=fc["name"], args=fc.get("args") or {})
                )
            elif "function_response" in p:
                fr = p["function_response"]
                parts.append(
                    types.Part.from_function_response(name=fr["name"], response=fr.get("response") or {})
                )
        out.append(types.Content(role=item["role"], parts=parts))
    return out


def _from_sdk_response(resp) -> AgentResponse:
    text_parts: list[str] = []
    calls: list[FunctionCall] = []
    # Prefer the structured function_calls helper when present.
    raw_calls = getattr(resp, "function_calls", None) or []
    for fc in raw_calls:
        calls.append(FunctionCall(name=fc.name, args=dict(fc.args or {}), id=getattr(fc, "id", "") or ""))
    if not calls:
        # fall back to inspecting candidate parts
        try:
            cand = resp.candidates[0]
            for part in cand.content.parts:
                if getattr(part, "text", None):
                    text_parts.append(part.text)
                elif getattr(part, "function_call", None):
                    calls.append(
                        FunctionCall(
                            name=part.function_call.name,
                            args=dict(part.function_call.args or {}),
                            id=getattr(part.function_call, "id", "") or "",
                        )
                    )
        except Exception:
            pass
    if not calls and not text_parts:
        text_parts.append(getattr(resp, "text", "") or "")
    return AgentResponse(text="\n".join(text_parts) if text_parts else None, function_calls=calls)


class RealGeminiClient(GeminiClientProtocol):
    def __init__(self, client) -> None:
        self._client = client

    def generate(self, system_instruction, contents, tool_declarations, model):
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=[types.Tool(function_declarations=tool_declarations)] if tool_declarations else [],
            temperature=0.3,
        )
        resp = self._client.models.generate_content(
            model=model,
            contents=_to_sdk_contents(contents),
            config=config,
        )
        return _from_sdk_response(resp)


class OfflineClient(GeminiClientProtocol):
    """Used when no Gemini key is configured (tests / offline demo).

    Returns a deterministic answer and never calls tools, so the loop terminates
    immediately with a clearly-marked offline notice.
    """

    def generate(self, system_instruction, contents, tool_declarations, model):
        return AgentResponse(
            text=(
                "[OFFLINE MODE] No Gemini API key configured. The assistant is running "
                "without a language model. Set GOOGLE_API_KEY to enable live responses."
            ),
            function_calls=[],
        )


def make_client() -> GeminiClientProtocol:
    client = _build_genai_client()
    if client is None:
        return OfflineClient()
    return RealGeminiClient(client)
