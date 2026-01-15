from datetime import date, datetime
from typing import List, Literal, Optional, Dict, Any

from pydantic import BaseModel, ConfigDict, field_validator


RoleType = Literal["user", "assistant", "system"]


class ChatMessage(BaseModel):
    role: RoleType
    content: str


class PensionPortfolioAccount(BaseModel):
    """חשבון פנסיוני מהתיק הפנסיוני (מה-UI)."""
    מספר_חשבון: Optional[str] = None
    שם_תכנית: Optional[str] = None
    חברה_מנהלת: Optional[str] = None
    סוג_מוצר: Optional[str] = None
    יתרה: Optional[float] = None
    תאריך_התחלה: Optional[str] = None
    פיצויים_מעסיק_נוכחי: Optional[float] = None
    פיצויים_ממעסיקים_קודמים_רצף_קצבה: Optional[float] = None
    תגמולי_עובד_עד_2000: Optional[float] = None
    תגמולי_עובד_אחרי_2000: Optional[float] = None
    תגמולי_מעביד_עד_2000: Optional[float] = None
    תגמולי_מעביד_אחרי_2000: Optional[float] = None
    תגמולים: Optional[float] = None
    סך_תגמולים: Optional[float] = None
    סך_פיצויים: Optional[float] = None

    @field_validator(
        "מספר_חשבון",
        "שם_תכנית",
        "חברה_מנהלת",
        "סוג_מוצר",
        "תאריך_התחלה",
        mode="before",
    )
    @classmethod
    def _coerce_text(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            raw = v.strip()
            return raw if raw else None
        if isinstance(v, (date, datetime)):
            try:
                return v.date().isoformat() if isinstance(v, datetime) else v.isoformat()
            except Exception:
                return None
        try:
            s = str(v).strip()
            return s if s else None
        except Exception:
            return None

    @field_validator(
        "יתרה",
        "פיצויים_מעסיק_נוכחי",
        "פיצויים_ממעסיקים_קודמים_רצף_קצבה",
        "תגמולי_עובד_עד_2000",
        "תגמולי_עובד_אחרי_2000",
        "תגמולי_מעביד_עד_2000",
        "תגמולי_מעביד_אחרי_2000",
        "תגמולים",
        "סך_תגמולים",
        "סך_פיצויים",
        mode="before",
    )
    @classmethod
    def _coerce_numeric(cls, v):
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            raw = v.strip()
            if raw == "":
                return None
            cleaned = (
                raw.replace(",", "")
                .replace("₪", "")
                .replace("\u00a0", " ")
                .replace(" ", "")
            )
            try:
                return float(cleaned)
            except Exception:
                return None
        try:
            return float(v)
        except Exception:
            return None

    model_config = ConfigDict(extra="allow")


class ChatRequest(BaseModel):
    """בקשת צ'אט לסוכן ה-LLM, כולל היסטוריית הודעות ולקוח אופציונלי."""

    messages: List[ChatMessage]
    client_id: int | None = None
    pension_portfolio: Optional[List[PensionPortfolioAccount]] = None
    pension_portfolio_snapshot_at: Optional[str] = None
    executor_only: bool | None = None


class ComputedPensionSource(BaseModel):
    """מקור פנסיוני מחושב מהמערכת."""
    source_name: str
    source_type: str  # "pension" or "capital"
    balance: float
    monthly_pension: float
    annuity_factor: float
    tax_treatment: str


class ComputedPensionData(BaseModel):
    """נתוני פנסיה מחושבים מהמערכת - לא מה-LLM."""
    sources: List[ComputedPensionSource] = []
    target_monthly_pension: float = 0
    accumulated_pension: float = 0
    remaining_capital: float = 0
    target_achieved: bool = False
    retirement_age: int = 67


class ChatResponse(BaseModel):
    """תשובת צ'אט מהסוכן, כולל רק את הודעת הסוכן האחרונה."""

    reply: str
    computed_data: Optional[ComputedPensionData] = None


class LlmProviderUpdateRequest(BaseModel):
    provider: str
    model_name: str | None = None

    model_config = ConfigDict(protected_namespaces=())


class LlmProviderUpdateResponse(BaseModel):
    provider: str | None
    backend: str | None
    model_name: str | None

    model_config = ConfigDict(protected_namespaces=())
