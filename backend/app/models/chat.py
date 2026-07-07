"""Chat API request/response and conversation message types."""
from __future__ import annotations

from pydantic import BaseModel, Field

from .roles import Role


class Message(BaseModel):
    role: str  # "user" | "assistant" | "tool"
    content: str = ""


class ChatRequest(BaseModel):
    role: Role = Role.FAN
    message: str
    history: list[Message] = Field(default_factory=list)
    language: str = "en"


class ToolEvent(BaseModel):
    """A single tool invocation recorded in the response trace."""

    name: str
    args: dict
    result: dict | str
    error: bool = False


class ChatResponse(BaseModel):
    reply: str
    role: Role
    language: str
    tool_events: list[ToolEvent] = Field(default_factory=list)
    snapshot_summary: str = ""


class RoleInfo(BaseModel):
    role: Role
    description: str
    tools: list[str]


class RolesResponse(BaseModel):
    roles: list[RoleInfo]
