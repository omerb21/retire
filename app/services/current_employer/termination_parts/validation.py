import json
import re
from typing import Dict, List, Optional
from datetime import date, datetime

from app.schemas.current_employer import TerminationDecisionCreate


def _parse_source_accounts(self, source_accounts: Optional[str]) -> List[str]:
    """פרסור חשבונות מקור"""
    if not source_accounts:
        return []
    try:
        return json.loads(source_accounts)
    except:
        return []


def _parse_plan_details(self, decision: TerminationDecisionCreate) -> List[Dict]:
    """פרסור פרטי תכניות"""
    if not hasattr(decision, 'plan_details') or not decision.plan_details:
        return []
    try:
        return json.loads(decision.plan_details)
    except:
        return []


def _create_source_suffix(self, source_account_names: List[str]) -> str:
    """יצירת סיומת מקור לשמות"""
    if not source_account_names:
        return ""
    if len(source_account_names) == 1:
        return f" - נוצר מ: {source_account_names[0]}"
    suffix = f" - נוצר מ: {', '.join(source_account_names[:2])}"
    if len(source_account_names) > 2:
        suffix += f" ועוד {len(source_account_names) - 2}"
    return suffix


def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
    """פרסור תאריך"""
    if not date_str:
        return None
    raw = str(date_str).strip()
    if not raw:
        return None

    if re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except Exception:
            return None

    if re.match(r"^\d{2}/\d{2}/\d{4}$", raw):
        try:
            return datetime.strptime(raw, "%d/%m/%Y").date()
        except Exception:
            return None

    if re.match(r"^\d{2}-\d{2}-\d{4}$", raw):
        try:
            normalized = raw.replace("-", "/")
            return datetime.strptime(normalized, "%d/%m/%Y").date()
        except Exception:
            return None

    if re.match(r"^\d{8}$", raw):
        try:
            if raw.startswith("19") or raw.startswith("20"):
                return datetime.strptime(raw, "%Y%m%d").date()
            return datetime.strptime(raw, "%d%m%Y").date()
        except Exception:
            return None

    try:
        return datetime.fromisoformat(raw).date()
    except Exception:
        return None
