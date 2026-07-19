"""Ollama / OpenAI-compatible client adapter.

Wraps an OpenAI-compatible REST API (like Ollama) behind the `LLMClientProtocol`.
Converts the loop's normalized contents to OpenAI `messages` format.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from ..agent.loop import AgentResponse, Contents, FunctionCall, LLMClientProtocol
from ..core.config import settings

logger = logging.getLogger(__name__)


def _to_openai_messages(system_instruction: str, contents: Contents) -> list[dict[str, Any]]:
    """Converts normalized agent contents to OpenAI messages format."""
    messages: list[dict[str, Any]] = []
    
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})

    for item in contents:
        role = item["role"]
        # Map Gemini roles to OpenAI roles
        openai_role = "assistant" if role == "model" else role

        for p in item["parts"]:
            if "text" in p:
                # If there is already a message for this role and no tool calls, we can append,
                # but standard format is to just emit a new message.
                messages.append({"role": openai_role, "content": p["text"]})
            elif "function_call" in p:
                fc = p["function_call"]
                # OpenAI uses a specific format for tool calls from the assistant
                call_id = fc.get("id") or fc["name"]  # Fallback to name if no ID provided
                tool_call = {
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": fc["name"],
                        "arguments": json.dumps(fc.get("args") or {})
                    }
                }
                messages.append({"role": "assistant", "content": None, "tool_calls": [tool_call]})
            elif "function_response" in p:
                fr = p["function_response"]
                # For tool responses, the role is "tool"
                messages.append({
                    "role": "tool",
                    "tool_call_id": fr["name"], # Note: In standard OpenAI, this needs to match the call ID
                    "name": fr["name"],
                    "content": json.dumps(fr.get("response") or {})
                })

    return messages


class OllamaClient(LLMClientProtocol):
    """Active client that communicates with an OpenAI-compatible API (e.g. Ollama)."""

    def generate(
        self,
        system_instruction: str,
        contents: Contents,
        tool_declarations: list[Any],
        model: str,
    ) -> AgentResponse:
        """Generates a response from the Ollama model using the REST API."""
        messages = _to_openai_messages(system_instruction, contents)
        
        payload: dict[str, Any] = {
            "model": settings.ollama_model,
            "messages": messages,
            "temperature": 0.3,
        }
        
        if tool_declarations:
            payload["tools"] = tool_declarations

        headers = {"Content-Type": "application/json"}
        if settings.ollama_api_key and settings.ollama_api_key != "ollama":
            headers["Authorization"] = f"Bearer {settings.ollama_api_key}"

        url = f"{settings.ollama_base_url.rstrip('/')}/chat/completions"
        
        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
        except Exception as e:
            logger.error(f"Ollama API request failed: {e}")
            raise

        choices = data.get("choices", [])
        if not choices:
            return AgentResponse(text="")
            
        message = choices[0].get("message", {})
        
        text_content = message.get("content")
        tool_calls_data = message.get("tool_calls", [])
        
        calls: list[FunctionCall] = []
        for tc in tool_calls_data:
            if tc.get("type") == "function":
                f_data = tc.get("function", {})
                name = f_data.get("name", "")
                args_str = f_data.get("arguments", "{}")
                try:
                    args = json.loads(args_str)
                except json.JSONDecodeError:
                    args = {}
                calls.append(FunctionCall(name=name, args=args, id=tc.get("id", "")))
                
        return AgentResponse(text=text_content, function_calls=calls)


def make_ollama_client() -> LLMClientProtocol:
    """Creates and returns an OllamaClient."""
    return OllamaClient()
