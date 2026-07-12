"""Chat API request/response and conversation message types."""
from __future__ import annotations

from pydantic import BaseModel, Field

from .roles import Role


class Message(BaseModel):
    """Represents a message in the chat conversation history."""

    role: str  # "user" | "assistant" | "tool"
    content: str = ""


class ChatRequest(BaseModel):
    """Schema for incoming assistant chat requests."""

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
    """Schema for outgoing assistant chat responses."""

    reply: str
    role: Role
    language: str
    tool_events: list[ToolEvent] = Field(default_factory=list)
    snapshot_summary: str = ""


class RoleInfo(BaseModel):
    """Schema detailing user role descriptions and allowed tools."""

    role: Role
    description: str
    tools: list[str]


class RolesResponse(BaseModel):
    """Schema returning a list of all role definitions."""

    roles: list[RoleInfo]

