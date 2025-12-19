from app.schemas.llm_chat import PensionPortfolioAccount
from app.services.llm_chat.portfolio_context import build_pension_portfolio_context


def test_portfolio_context_flags_unsettled_and_rights_sequence() -> None:
    portfolio = [
        PensionPortfolioAccount(
            מספר_חשבון="123",
            שם_תכנית="בדיקה",
            חברה_מנהלת="חברה",
            סוג_מוצר="קופת גמל",
            יתרה=1000,
            תאריך_התחלה="2000-01-01",
            פיצויים_שלא_עברו_התחשבנות=10,
            פיצויים_ממעסיקים_קודמים_רצף_זכויות=20,
            תגמולי_עובד_אחרי_2000=100,
            תגמולי_מעביד_אחרי_2000=200,
        )
    ]

    lines = build_pension_portfolio_context(portfolio)
    text = "\n".join(lines)

    assert "אזהרה" in text
    assert "פיצויים שלא עברו התחשבנות" in text
    assert "רצף זכויות" in text
