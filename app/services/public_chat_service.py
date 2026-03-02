import hmac
import json
import logging
import math
import os
import re
import secrets
from typing import Any

from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.public_chat import PublicChatMessage, PublicChatSession
from app.models.scenario import Scenario
from app.schemas.llm_chat import ChatMessage, ChatRequest
from app.schemas.public_chat import PublicChatMessageDto
from app.services.client_service import normalize_id_number
from app.services.llm_chat.chat_orchestration import run_pension_chat_stream
from app.services.llm_chat.orchestration_utils import sanitize_user_visible_text
from app.services.pension_portfolio.snapshot_loader import (
    dedupe_pension_portfolio_snapshot,
    load_latest_pension_portfolio_snapshot_models,
    upsert_snapshot,
)
from app.utils.llm_chat_log import get_current_request_id

logger = logging.getLogger(__name__)


def _strip_stream_markers_for_public_chat(text: str) -> str:
    if not isinstance(text, str) or not text:
        return text

    updated = text

    # Remove computed data block
    try:
        updated = re.sub(
            r"###COMPUTED_DATA###.*?###END_COMPUTED_DATA###\n?",
            "",
            updated,
            flags=re.DOTALL,
        )
    except Exception:
        pass

    # Remove portfolio update blocks (used by internal UI to mutate local storage)
    try:
        updated = re.sub(
            r"###PENSION_PORTFOLIO_UPDATE###.*?###END_PENSION_PORTFOLIO_UPDATE###\n?",
            "",
            updated,
            flags=re.DOTALL,
        )
    except Exception:
        pass

    # Remove severance reset blocks
    try:
        updated = re.sub(
            r"###SEVERANCE_RESET###.*?###END_SEVERANCE_RESET###\n?",
            "",
            updated,
            flags=re.DOTALL,
        )
    except Exception:
        pass

    return updated.strip()


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return int(math.ceil(len(text) / 4))


def _load_snapshot_accounts(db: Session, client_id: int) -> list[dict[str, Any]] | None:
    snapshot = (
        db.query(Scenario)
        .filter(Scenario.client_id == client_id)
        .filter(Scenario.scenario_name == "pension_portfolio_snapshot")
        .order_by(Scenario.created_at.desc())
        .first()
    )
    if snapshot is None or not snapshot.parameters:
        return None
    try:
        params = json.loads(snapshot.parameters)
    except Exception:
        return None
    portfolio = params.get("pension_portfolio")
    if not isinstance(portfolio, list):
        return None
    accounts: list[dict[str, Any]] = []
    for item in portfolio:
        if isinstance(item, dict):
            accounts.append(item)
    return accounts or None


def _save_snapshot_accounts(
    db: Session, client_id: int, accounts: list[dict[str, Any]]
) -> None:
    upsert_snapshot(
        db,
        client_id,
        accounts,
        meta={"operation_type": "portfolio_import"},
    )
    dedupe_pension_portfolio_snapshot(db, client_id)


def _safe_number(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            cleaned = value.replace(",", "").replace("₪", "").strip()
            if not cleaned:
                return 0.0
            return float(cleaned)
        return float(value)
    except Exception:
        return 0.0


def _apply_severance_reset_to_accounts(
    accounts: list[dict[str, Any]], reset_info: dict[str, Any]
) -> list[dict[str, Any]]:
    if not (
        isinstance(reset_info, dict) and reset_info.get("portfolio_severance_to_reset")
    ):
        return accounts
    updated: list[dict[str, Any]] = []
    for acc in accounts:
        if not isinstance(acc, dict):
            continue
        copy = dict(acc)
        copy["פיצויים_מעסיק_נוכחי"] = 0
        updated.append(copy)
    return updated


def _apply_portfolio_updates_to_accounts(
    accounts: list[dict[str, Any]], payload: dict[str, Any]
) -> list[dict[str, Any]]:
    if not (
        isinstance(payload, dict) and payload.get("type") == "pension_portfolio_updates"
    ):
        return accounts
    updates = payload.get("updates")
    if not isinstance(updates, list) or not updates:
        return accounts

    def _extract_account_number(raw: dict[str, Any]) -> str:
        if not isinstance(raw, dict):
            return ""
        return str(
            raw.get("מספר_חשבון")
            or raw.get("מספר חשבון")
            or raw.get("מספר-חשבון")
            or raw.get("account_number")
            or ""
        ).strip()

    by_account_number: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    unkeyed_accounts: list[dict[str, Any]] = []
    for acc in accounts:
        if not isinstance(acc, dict):
            continue
        num = _extract_account_number(acc)
        if not num:
            unkeyed_accounts.append(dict(acc))
            continue
        copy = dict(acc)
        copy["מספר_חשבון"] = num
        copy["מספר חשבון"] = num
        by_account_number[num] = copy
        order.append(num)

    for upd in updates:
        if not isinstance(upd, dict):
            continue
        num = str(upd.get("account_number") or "").strip()
        if not num:
            continue
        acc = by_account_number.get(num)
        if not isinstance(acc, dict):
            continue

        acc["מספר_חשבון"] = num
        acc["מספר חשבון"] = num

        specific = upd.get("specific_amounts")
        if isinstance(specific, dict) and specific:
            for field, raw_delta in specific.items():
                if not isinstance(field, str) or not field:
                    continue
                delta = _safe_number(raw_delta)
                if delta <= 0:
                    continue
                current_val = _safe_number(acc.get(field))
                remaining = max(0.0, current_val - delta)
                acc[field] = 0 if abs(remaining) < 0.01 else remaining

            edu_delta = _safe_number(specific.get("קרן_השתלמות"))
            if edu_delta > 0:
                for field in list(acc.keys()):
                    if field.startswith("תגמולי_") or field in {
                        "תגמולים",
                        "סך_תגמולים",
                        "קרן_השתלמות",
                    }:
                        acc[field] = 0
                acc["יתרה"] = 0
                acc["balance"] = 0
        else:
            converted_amount = _safe_number(upd.get("converted_amount"))
            if converted_amount > 0:
                for key in ("יתרה", "balance"):
                    if key in acc:
                        current_val = _safe_number(acc.get(key))
                        remaining = max(0.0, current_val - converted_amount)
                        acc[key] = 0 if abs(remaining) < 0.01 else remaining

        by_account_number[num] = acc

    updated_accounts: list[dict[str, Any]] = []
    seen: set[str] = set()
    for num in order:
        acc = by_account_number.get(num)
        if isinstance(acc, dict):
            updated_accounts.append(acc)
            seen.add(num)
    for num, acc in by_account_number.items():
        if num in seen:
            continue
        if isinstance(acc, dict):
            updated_accounts.append(acc)
    if unkeyed_accounts:
        updated_accounts.extend(unkeyed_accounts)
    return updated_accounts


def _apply_marker_payloads_to_snapshot_accounts(
    *,
    accounts: list[dict[str, Any]],
    portfolio_payloads: list[dict[str, Any]],
    severance_payloads: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    updated_accounts = accounts
    for sev in severance_payloads:
        updated_accounts = _apply_severance_reset_to_accounts(updated_accounts, sev)
    for upd in portfolio_payloads:
        if isinstance(upd, dict) and upd.get("operation") == "converted_to_assets":
            continue
        updated_accounts = _apply_portfolio_updates_to_accounts(updated_accounts, upd)
    return updated_accounts


def _extract_marker_payloads(
    text: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not isinstance(text, str) or not text:
        return [], []
    portfolio_payloads: list[dict[str, Any]] = []
    severance_payloads: list[dict[str, Any]] = []

    try:
        for match in re.findall(
            r"###PENSION_PORTFOLIO_UPDATE###(.*?)###END_PENSION_PORTFOLIO_UPDATE###",
            text,
            flags=re.DOTALL,
        ):
            raw = (match or "").strip()
            if not raw:
                continue
            try:
                parsed = json.loads(raw)
            except Exception:
                continue
            if isinstance(parsed, dict):
                portfolio_payloads.append(parsed)
    except Exception:
        pass

    try:
        for match in re.findall(
            r"###SEVERANCE_RESET###(.*?)###END_SEVERANCE_RESET###",
            text,
            flags=re.DOTALL,
        ):
            raw = (match or "").strip()
            if not raw:
                continue
            try:
                parsed = json.loads(raw)
            except Exception:
                continue
            if isinstance(parsed, dict):
                severance_payloads.append(parsed)
    except Exception:
        pass

    return portfolio_payloads, severance_payloads


def _generate_session_key() -> str:
    return secrets.token_urlsafe(32)


def _default_initial_tokens() -> int:
    raw = os.getenv("PUBLIC_CHAT_INITIAL_TOKENS", "5000")
    try:
        value = int(raw)
        return max(0, value)
    except Exception:
        return 5000


def _ensure_client_credit_initialized(
    client: Client, initial_tokens: int | None = None
) -> None:
    if client.public_chat_token_balance is None:
        client.public_chat_token_balance = 0
    if client.public_chat_tokens_spent is None:
        client.public_chat_tokens_spent = 0

    if bool(getattr(client, "public_chat_credit_initialized", False)):
        return

    token_balance = (
        _default_initial_tokens()
        if initial_tokens is None
        else max(0, int(initial_tokens))
    )
    client.public_chat_token_balance = int(token_balance)
    client.public_chat_tokens_spent = 0
    client.public_chat_credit_initialized = True


def start_or_get_session(
    db: Session, id_number: str, initial_tokens: int | None = None
) -> PublicChatSession:
    normalized = normalize_id_number(id_number)
    if not normalized:
        raise ValueError("invalid_id_number")

    client = db.query(Client).filter(Client.id_number == normalized).first()
    if not client:
        raise ValueError("client_not_found")

    if not bool(getattr(client, "public_chat_credit_initialized", False)):
        latest_session = (
            db.query(PublicChatSession)
            .filter(PublicChatSession.client_id == client.id)
            .order_by(PublicChatSession.id.desc())
            .first()
        )
        if latest_session is not None:
            client.public_chat_token_balance = int(latest_session.token_balance or 0)
            client.public_chat_tokens_spent = int(latest_session.tokens_spent or 0)
            client.public_chat_credit_initialized = True
        else:
            _ensure_client_credit_initialized(client, initial_tokens=initial_tokens)
    else:
        _ensure_client_credit_initialized(client, initial_tokens=None)
    db.add(client)
    db.commit()
    db.refresh(client)

    existing = (
        db.query(PublicChatSession)
        .filter(PublicChatSession.client_id == client.id)
        .filter(PublicChatSession.is_active.is_(True))
        .order_by(PublicChatSession.id.desc())
        .first()
    )
    if existing:
        desired_balance = int(client.public_chat_token_balance or 0)
        desired_spent = int(client.public_chat_tokens_spent or 0)

        if (
            existing.token_balance != desired_balance
            or existing.tokens_spent != desired_spent
        ):
            existing.token_balance = desired_balance
            existing.tokens_spent = desired_spent
            db.add(existing)
            db.commit()
            db.refresh(existing)
        return existing

    token_balance = int(client.public_chat_token_balance or 0)
    tokens_spent = int(client.public_chat_tokens_spent or 0)

    session = PublicChatSession(
        session_key=_generate_session_key(),
        client_id=client.id,
        token_balance=token_balance,
        tokens_spent=tokens_spent,
        is_active=True,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session_by_key(db: Session, session_key: str) -> PublicChatSession:
    session = (
        db.query(PublicChatSession)
        .filter(PublicChatSession.session_key == session_key)
        .first()
    )
    if not session:
        raise ValueError("session_not_found")
    return session


def get_session_by_key_with_password(
    db: Session, session_key: str, password: str | None
) -> PublicChatSession:
    session = get_session_by_key(db, session_key)

    client = (
        session.client
        or db.query(Client).filter(Client.id == session.client_id).first()
    )
    if not client:
        raise ValueError("client_not_found")

    normalized = normalize_id_number(password or "")
    if not normalized or not hmac.compare_digest(
        normalized, str(client.id_number or "")
    ):
        raise ValueError("invalid_public_chat_password")

    return session


def get_history(db: Session, session: PublicChatSession) -> list[PublicChatMessageDto]:
    rows = (
        db.query(PublicChatMessage)
        .filter(PublicChatMessage.session_id == session.id)
        .order_by(PublicChatMessage.id.asc())
        .all()
    )
    return [
        PublicChatMessageDto(
            role=r.role,
            content=r.content,
            estimated_tokens=int(r.estimated_tokens or 0),
        )
        for r in rows
    ]


def _append_message(
    db: Session, session: PublicChatSession, role: str, content: str
) -> PublicChatMessage:
    msg = PublicChatMessage(
        session_id=session.id,
        role=role,
        content=content,
        estimated_tokens=_estimate_tokens(content),
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def _load_latest_pension_portfolio(
    db: Session, client_id: int
) -> tuple[list[dict], str] | None:
    result = load_latest_pension_portfolio_snapshot_models(db, client_id)
    if result is None:
        return None

    portfolio_models, snapshot_at = result
    return [item.model_dump() for item in portfolio_models], snapshot_at


async def send_message(
    db: Session, session: PublicChatSession, user_content: str
) -> tuple[str, int]:
    trimmed = (user_content or "").strip()
    if not trimmed:
        raise ValueError("empty_message")

    if not session.is_active:
        raise ValueError("session_inactive")

    client = (
        session.client
        or db.query(Client).filter(Client.id == session.client_id).first()
    )
    if not client:
        raise ValueError("client_not_found")

    if not bool(getattr(client, "public_chat_credit_initialized", False)):
        client.public_chat_token_balance = int(session.token_balance or 0)
        client.public_chat_tokens_spent = int(session.tokens_spent or 0)
        client.public_chat_credit_initialized = True

    _ensure_client_credit_initialized(client)

    if int(client.public_chat_token_balance or 0) <= 0:
        raise ValueError("tokens_depleted")

    _append_message(db, session, "user", trimmed)

    history = get_history(db, session)
    chat_messages: list[ChatMessage] = [
        ChatMessage(role=m.role, content=m.content) for m in history
    ]

    pension_portfolio = None
    pension_portfolio_snapshot_at = None
    loaded_portfolio = _load_latest_pension_portfolio(db, session.client_id)
    if loaded_portfolio is not None:
        pension_portfolio, pension_portfolio_snapshot_at = loaded_portfolio
    request = ChatRequest(
        messages=chat_messages,
        client_id=session.client_id,
        pension_portfolio=pension_portfolio,
        pension_portfolio_snapshot_at=pension_portfolio_snapshot_at,
    )

    stream_response = run_pension_chat_stream(request, db)
    chunks: list[str] = []
    stream_error_id: str | None = None
    try:
        async for chunk in stream_response.body_iterator:
            if isinstance(chunk, (bytes, bytearray)):
                try:
                    chunks.append(chunk.decode("utf-8", errors="ignore"))
                except Exception:
                    chunks.append(str(chunk))
            else:
                chunks.append(str(chunk))
    except Exception:
        stream_error_id = secrets.token_urlsafe(8)
        logger.exception(
            "Public chat stream failed (error_id=%s, request_id=%s, client_id=%s, session_key=%s)",
            stream_error_id,
            get_current_request_id(),
            getattr(session, "client_id", None),
            getattr(session, "session_key", None)
            or getattr(session, "key", None)
            or "",
        )
        chunks = []

    reply_text = "".join(chunks).strip()
    if not reply_text:
        if stream_error_id:
            reply_text = (
                "שגיאה: לא התקבלה תשובה מהמערכת (כשל זמני). נסה שוב בעוד רגע. "
                f"(קוד שגיאה: {stream_error_id})"
            )
        else:
            empty_error_id = secrets.token_urlsafe(8)
            logger.error(
                "Public chat stream returned empty reply (error_id=%s, request_id=%s, client_id=%s, session_key=%s)",
                empty_error_id,
                get_current_request_id(),
                getattr(session, "client_id", None),
                getattr(session, "session_key", None)
                or getattr(session, "key", None)
                or "",
            )
            reply_text = (
                "שגיאה: לא התקבלה תשובה מהמערכת (כשל זמני). נסה שוב בעוד רגע. "
                f"(קוד שגיאה: {empty_error_id})"
            )

    portfolio_payloads, severance_payloads = _extract_marker_payloads(reply_text)
    if portfolio_payloads or severance_payloads:
        try:
            accounts = _load_snapshot_accounts(db, session.client_id)
            if accounts is not None:
                updated_accounts = _apply_marker_payloads_to_snapshot_accounts(
                    accounts=accounts,
                    portfolio_payloads=portfolio_payloads,
                    severance_payloads=severance_payloads,
                )
                if updated_accounts is not None:
                    _save_snapshot_accounts(db, session.client_id, updated_accounts)
        except Exception:
            marker_error_id = secrets.token_urlsafe(8)
            logger.exception(
                "Public chat marker apply failed (error_id=%s, request_id=%s, client_id=%s, session_key=%s)",
                marker_error_id,
                get_current_request_id(),
                getattr(session, "client_id", None),
                getattr(session, "session_key", None)
                or getattr(session, "key", None)
                or "",
            )

    reply_text = _strip_stream_markers_for_public_chat(reply_text)
    reply_text = sanitize_user_visible_text(reply_text)

    _append_message(db, session, "assistant", reply_text)

    tokens_used = _estimate_tokens(trimmed) + _estimate_tokens(reply_text)
    if tokens_used < 0:
        tokens_used = 0

    current_balance = int(client.public_chat_token_balance or 0)
    to_deduct = min(current_balance, int(tokens_used))
    client.public_chat_token_balance = current_balance - to_deduct
    client.public_chat_tokens_spent = (
        int(client.public_chat_tokens_spent or 0) + to_deduct
    )

    session.token_balance = int(client.public_chat_token_balance or 0)
    session.tokens_spent = int(client.public_chat_tokens_spent or 0)

    db.add(client)
    db.add(session)
    db.commit()
    db.refresh(session)

    return reply_text, tokens_used


def top_up(db: Session, session_key: str, tokens: int) -> PublicChatSession:
    if tokens <= 0:
        raise ValueError("invalid_topup")

    session = get_session_by_key(db, session_key)

    client = (
        session.client
        or db.query(Client).filter(Client.id == session.client_id).first()
    )
    if not client:
        raise ValueError("client_not_found")

    if not bool(getattr(client, "public_chat_credit_initialized", False)):
        client.public_chat_token_balance = int(session.token_balance or 0)
        client.public_chat_tokens_spent = int(session.tokens_spent or 0)
        client.public_chat_credit_initialized = True

    _ensure_client_credit_initialized(client)
    client.public_chat_token_balance = int(client.public_chat_token_balance or 0) + int(
        tokens
    )

    session.token_balance = int(client.public_chat_token_balance or 0)
    session.tokens_spent = int(client.public_chat_tokens_spent or 0)

    db.add(client)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def clear_history(db: Session, session: PublicChatSession) -> int:
    deleted = (
        db.query(PublicChatMessage)
        .filter(PublicChatMessage.session_id == session.id)
        .delete(synchronize_session=False)
    )
    db.commit()
    return int(deleted or 0)
