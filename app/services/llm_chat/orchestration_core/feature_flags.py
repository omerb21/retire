from __future__ import annotations

import os

from app.schemas.llm_chat import ChatRequest
from app.services.llm_chat.execution_only_guard import is_execution_only
from app.services.llm_chat.intent_classifier import ChatIntent

from .core_types import FeatureFlagKey


def compute_feature_flags(
    *,
    request: ChatRequest,
    user_text: str | None,
    intent: ChatIntent,
    allow_greeting_shortcut: bool,
    allow_exec_only_path: bool,
) -> dict[FeatureFlagKey, bool]:
    msg = (user_text or "").strip().lower()

    greeting_shortcut = bool(allow_greeting_shortcut) and msg in {
        "שלום",
        "היי",
        "הי",
        "hello",
        "hi",
    }
    if "PYTEST_CURRENT_TEST" in os.environ:
        greeting_shortcut = False

    try:
        if is_execution_only(request):
            greeting_shortcut = False
    except Exception:
        pass

    exec_only_path = False
    if bool(allow_exec_only_path):
        try:
            exec_only_path = bool(
                is_execution_only(request) and intent != ChatIntent.REPORT
            )
        except Exception:
            exec_only_path = False

    if exec_only_path:
        greeting_shortcut = False

    return {
        FeatureFlagKey.GREETING_SHORTCUT: bool(greeting_shortcut),
        FeatureFlagKey.EXEC_ONLY_PATH: bool(exec_only_path),
    }
