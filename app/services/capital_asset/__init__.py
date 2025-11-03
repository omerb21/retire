"""
Capital Asset Service Package - מנועי חישוב מודולריים לנכסי הון

חבילה זו מכילה מנועי חישוב מיוחדים לניהול נכסי הון, כולל:
- חישובי הצמדה (CPI, קבוע)
- חישובי מס (פטור, קבוע, שולי, פריסה)
- חישובי תזרים מזומנים
- ניהול לוחות תשלומים

הקובץ המקורי capital_asset_service.py נשאר ללא שינוי לתאימות לאחור.
"""

from app.services.capital_asset.service import CapitalAssetService

__all__ = ['CapitalAssetService']
