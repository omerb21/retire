from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def _load_stream_intents_playbook_text() -> str | None:
    try:
        repo_root = Path(__file__).resolve().parents[5]
        p = repo_root / "MD" / "docs" / "agent_playbooks" / "pension_chat_stream_playbook_intents.md"
        if not p.exists():
            return None
        txt = p.read_text(encoding="utf-8")
        cleaned = (txt or "").strip()
        return cleaned or None
    except Exception:
        return None
