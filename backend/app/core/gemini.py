"""Gemini client adapter.

Wraps the `google-genai` SDK behind the simple `GeminiClientProtocol` used by
the agent loop. Converts the loop's normalized contents representation to/from
SDK `types.Content` / `types.Part` objects.

If no API key is configured (tests / offline demo), `make_client` returns a
`OfflineClient` that returns a deterministic fallback response instead of
calling the network.
"""
from __future__ import annotations

import logging
from typing import Any

from ..agent.loop import AgentResponse, Contents, FunctionCall, LLMClientProtocol
from ..core.config import settings

logger = logging.getLogger(__name__)


def _build_genai_client() -> Any | None:
    """Builds and returns the Google GenAI client based on configuration settings.

    Returns:
        An initialized google.genai.Client, or None if offline mode is active.

    """
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


def _to_sdk_contents(contents: Contents) -> list[Any]:
    """Converts normalized agent contents to Google GenAI SDK Content objects.

    Args:
        contents: The normalized conversation representation.

    Returns:
        A list of Google GenAI SDK Content objects.

    """
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


def _from_sdk_response(resp: Any) -> AgentResponse:
    """Converts a Google GenAI SDK response to a normalized AgentResponse.

    Args:
        resp: The response object returned by the Google GenAI SDK.

    Returns:
        A normalized AgentResponse instance.

    """
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
        except (AttributeError, IndexError, TypeError, ValueError) as e:
            logger.warning("Failed to parse candidate parts from SDK response: %s", e)
    if not calls and not text_parts:
        text_parts.append(getattr(resp, "text", "") or "")
    return AgentResponse(text="\n".join(text_parts) if text_parts else None, function_calls=calls)


class RealGeminiClient(LLMClientProtocol):
    """Active Gemini client that communicates with the Google GenAI API."""

    def __init__(self, client: Any) -> None:
        """Initializes the RealGeminiClient with a GenAI client.

        Args:
            client: The initialized Google GenAI client.

        """
        self._client = client

    def generate(
        self,
        system_instruction: str,
        contents: Contents,
        tool_declarations: list[Any],
        model: str,
    ) -> AgentResponse:
        """Generates a response from the Google GenAI model using the API.

        Args:
            system_instruction: The instruction governing the model's behavior.
            contents: The current conversation history including tool calls/responses.
            tool_declarations: A list of functions/tools the model is allowed to call.
            model: The model identifier to query.

        Returns:
            The response from the agent.

        """
        from google.genai import types

        # Convert generic OpenAI-style dicts back to Google types.FunctionDeclaration
        genai_tools = []
        for d in tool_declarations:
            if isinstance(d, dict) and "function" in d:
                f = d["function"]
                genai_tools.append(
                    types.FunctionDeclaration(
                        name=f["name"],
                        description=f.get("description", ""),
                        parameters=f.get("parameters", {}),
                    )
                )
            else:
                genai_tools.append(d)

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=[types.Tool(function_declarations=genai_tools)] if genai_tools else [],
            temperature=0.3,
        )
        resp = self._client.models.generate_content(
            model=model,
            contents=_to_sdk_contents(contents),
            config=config,
        )
        return _from_sdk_response(resp)


class OfflineClient(LLMClientProtocol):
    """Used when no Gemini key is configured (tests / offline demo).

    Returns a deterministic answer and never calls tools, so the loop terminates
    immediately with a clearly-marked offline notice.
    """

    def generate(
        self,
        system_instruction: str,
        contents: Contents,
        tool_declarations: list[Any],
        model: str,
    ) -> AgentResponse:
        """Generates a mock offline response without calling the Gemini API.

        Args:
            system_instruction: The instruction governing the model's behavior.
            contents: The current conversation history including tool calls/responses.
            tool_declarations: A list of functions/tools the model is allowed to call.
            model: The model identifier to query.

        Returns:
            A mock AgentResponse with offline notices.

        """
        return AgentResponse(
            text=(
                "[OFFLINE MODE] No Gemini API key configured. The assistant is running "
                "without a language model. Set GOOGLE_API_KEY to enable live responses."
            ),
            function_calls=[],
        )


def make_client() -> LLMClientProtocol:
    """Creates and returns either a RealGeminiClient or OfflineClient based on configuration.

    Returns:
        An instance of LLMClientProtocol.

    """
    client = _build_genai_client()
    if client is None:
        return OfflineClient()
    return RealGeminiClient(client)

