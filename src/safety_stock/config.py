"""Runtime configuration resolved from environment variables."""

from __future__ import annotations

import os


class Settings:
    """Application settings populated from environment variables with sensible defaults."""

    # API server
    host: str = os.environ.get("SS_HOST", "0.0.0.0")
    port: int = int(os.environ.get("SS_PORT", "8000"))
    workers: int = int(os.environ.get("SS_WORKERS", "1"))
    reload: bool = os.environ.get("SS_RELOAD", "false").lower() == "true"

    # Logging
    log_level: str = os.environ.get("SS_LOG_LEVEL", "INFO").upper()
    log_json: bool = os.environ.get("SS_LOG_JSON", "false").lower() == "true"

    # Docs
    docs_enabled: bool = os.environ.get("SS_DOCS_ENABLED", "true").lower() == "true"


settings = Settings()
