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
    return os.getenv("FIXATION_ALLOW_JSON_FALLBACK", "true").lower() in ("true", "1", "yes")
