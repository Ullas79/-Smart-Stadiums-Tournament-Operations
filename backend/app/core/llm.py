"""LLM client factory.

Selects the correct LLM adapter (Gemini or Ollama) based on configuration.
"""
from __future__ import annotations

from .config import settings
from ..agent.loop import LLMClientProtocol

def make_llm_client() -> LLMClientProtocol:
    """Creates and returns the appropriate LLMClientProtocol based on config."""
    if settings.llm_provider.lower() == "ollama":
        from .ollama_client import make_ollama_client
        return make_ollama_client()
    else:
        from .gemini import make_client
        return make_client()
