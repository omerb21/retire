from __future__ import annotations

import hashlib
import re


_ws_re = re.compile(r"\s+")


def normalize_user_text_v1(user_text: str) -> str:
    raw = (user_text or "").strip().lower()
    if not raw:
        return ""
    return _ws_re.sub(" ", raw)


def sha256_hex(text: str) -> str:
    h = hashlib.sha256()
    h.update((text or "").encode("utf-8"))
    return h.hexdigest()
