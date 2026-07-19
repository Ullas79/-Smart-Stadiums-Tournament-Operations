"""Application configuration loaded from environment / .env."""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> project root is two parents up from this file's
# directory's parents: backend/app/core -> backend/app -> backend -> root.
ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Gemini / Google Gen AI
    google_api_key: str = ""
    google_genai_use_vertexai: bool = False
    google_cloud_project: str = ""
    google_cloud_location: str = "us-central1"

    # Agent
    gemini_model: str = "gemini-2.0-flash"
    agent_max_tool_iterations: int = 6
    agent_max_message_chars: int = 2000

    # Security
    max_payload_size_bytes: int = 1048576  # 1MB
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60
    trusted_proxies: str = "127.0.0.1"  # Comma-separated list of trusted proxy IPs/CIDRs

    @property
    def trusted_proxies_list(self) -> list[str]:
        """Parses the configured trusted proxies into a list of strings.

        Returns:
            A list of IP addresses or CIDR ranges.
        """
        return [p.strip() for p in self.trusted_proxies.split(",") if p.strip()]

    # Simulator
    sim_tick_seconds: int = 5
    sim_speed: int = 60

    # Server
    backend_cors_origins: str = "http://localhost:5173"

    @property
    def cors_origins(self) -> list[str]:
        """Parses the configured CORS origins into a list of strings.

        Returns:
            A list of allowed CORS origin URLs.
        """
        return [o.strip() for o in self.backend_cors_origins.split(",") if o.strip()]



settings = Settings()
