from typing import List, Literal, Optional, Dict, Any

from pydantic import BaseModel, ConfigDict


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

    model_config = ConfigDict(extra="allow")


class ChatRequest(BaseModel):
    """בקשת צ'אט לסוכן ה-LLM, כולל היסטוריית הודעות ולקוח אופציונלי."""

    messages: List[ChatMessage]
    client_id: int | None = None
    pension_portfolio: Optional[List[PensionPortfolioAccount]] = None


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
