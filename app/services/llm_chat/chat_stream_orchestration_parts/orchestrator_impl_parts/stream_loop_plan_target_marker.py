import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.scenario import Scenario


def extract_target_net_ils(user_text: str) -> int | None:
    if not isinstance(user_text, str) or not user_text.strip():
        return None

    cleaned = user_text.replace(",", "").replace(".", "")
    lowered = cleaned.lower()

    nums: list[tuple[int, int, int]] = []
    for m in re.finditer(r"\b\d{4,6}\b", cleaned):
        try:
            nums.append((m.start(), m.end(), int(m.group(0))))
        except Exception:
            continue
    if not nums:
        return None

    net_positions = [m.start() for m in re.finditer(r"נטו|\bnet\b", lowered)]
    if net_positions:
        best = None
        best_dist = None
        for s, _e, val in nums:
            d = min(abs(s - p) for p in net_positions)
            if best_dist is None or d < best_dist:
                best = val
                best_dist = d
        return best

    keyword_positions: list[int] = []
    for kw in (
        "קצבת יעד",
        "יעד הכנסה",
        "יעד",
    ):
        keyword_positions.extend([m.start() for m in re.finditer(re.escape(kw), lowered)])

    if not keyword_positions:
        return None

    best = None
    best_dist = None
    for s, _e, val in nums:
        d = min(abs(s - p) for p in keyword_positions)
        if best_dist is None or d < best_dist:
            best = val
            best_dist = d
    return best


@dataclass(frozen=True)
class PendingPlanTargetMarker:
    row: Scenario
    session: Session
    expires_at: datetime | None

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        expires_at = self.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) >= expires_at


def load_pending_plan_target_marker_direct(
    *, session: Session, client_id: int | None
) -> PendingPlanTargetMarker | None:
    if client_id is None:
        return None
    try:
        row = (
            session.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "pending_plan_target")
            .order_by(Scenario.created_at.desc())
            .first()
        )
    except Exception:
        row = None
    if row is None or not getattr(row, "parameters", None):
        return None
    try:
        parsed = json.loads(row.parameters)
    except Exception:
        return None
    if not isinstance(parsed, dict):
        return None
    if str(parsed.get("kind") or "").strip() != "pending_plan_target":
        return None
    if parsed.get("active", True) is False:
        return None

    expires_at = None
    expires_raw = parsed.get("expires_at")
    if isinstance(expires_raw, str) and expires_raw.strip():
        try:
            expires_at = datetime.fromisoformat(expires_raw.strip())
        except Exception:
            expires_at = None

    return PendingPlanTargetMarker(row=row, session=session, expires_at=expires_at)


def delete_marker(marker: PendingPlanTargetMarker) -> None:
    try:
        parsed = json.loads(marker.row.parameters or "{}")
    except Exception:
        parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}
    parsed["active"] = False
    marker.row.parameters = json.dumps(parsed, ensure_ascii=False)
    try:
        marker.session.add(marker.row)
        marker.session.commit()
    except Exception:
        try:
            marker.session.rollback()
        except Exception:
            pass
