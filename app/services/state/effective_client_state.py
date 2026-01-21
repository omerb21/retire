from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(frozen=True)
class EffectiveClientState:
    client_id: int
    mode: Literal["PRE_CONVERSION", "POST_CONVERSION_LOCKED"]
    last_state_change_at_utc: datetime | None
    last_operation_type: str | None
    last_trace_id: str | None
    counts: dict
    has_any_conversion_assets: bool
    has_any_commutation_assets: bool
    has_any_capital_assets: bool
    latest_snapshot_id: int | None
    latest_snapshot_at_utc: datetime | None
    unlock_reason: str | None = None
