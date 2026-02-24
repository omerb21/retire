"""
Configuration module for application settings
"""

import os
from typing import Dict, Any, Optional, Callable


# Environment-based configuration
def allow_json_fallback() -> bool:
    """
    Check if JSON fallback is allowed for fixation documents

    Returns:
        bool: True if JSON fallback is allowed, False otherwise
    """
    return os.getenv("FIXATION_ALLOW_JSON_FALLBACK", "true").lower() in (
        "true",
        "1",
        "yes",
    )


def cors_allow_origins() -> list[str]:
    allow_all = os.getenv("CORS_ALLOW_ALL", "false").lower() in ("true", "1", "yes")
    if allow_all:
        return ["*"]

    origins = [
        "http://localhost:3000",
        "http://localhost:8000",
        "https://retire-1.onrender.com",
        "https://retire.onrender.com",
        "https://retapp-production.up.railway.app",
    ]
    extra = os.getenv("CORS_ALLOW_ORIGINS", "")
    if extra.strip():
        origins.extend([o.strip() for o in extra.split(",") if o.strip()])
    return origins


def cors_allow_origin_regex() -> str | None:
    value = os.getenv("CORS_ALLOW_ORIGIN_REGEX", "").strip()
    return value or None


def cors_allow_credentials() -> bool:
    allow_all = os.getenv("CORS_ALLOW_ALL", "false").lower() in ("true", "1", "yes")
    if allow_all:
        return False
    return os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() in ("true", "1", "yes")
