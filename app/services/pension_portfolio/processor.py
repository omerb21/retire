import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET

MANAGING_COMPANY_TAGS = [
    "SHEM-METAFEL",
    "SHEM-YATZRAN",
    "SHEM_HA_MOSAD",
    "Provider",
    "Company",
    "KOD-MEZAHE-METAFEL",
    "KOD-MEZAHE-YATZRAN",
    "KOD-YATZRAN",
    "MEZAHE-YATZRAN",
]

PLAN_TYPE_TAGS = [
    "SUG-TOCHNIT-O-CHESHBON",
    "SUG-POLISA",
    "SUG-MUTZAR",
    "SUG-KEREN-PENSIA",
    "SUG-KUPA",
    "SUG-HAFRASHA",
]

BALANCE_EXPLICIT_TAGS = [
    "TOTAL-CHISACHON-MTZBR",
    "TOTAL-ERKEI-PIDION",
    "YITRAT-KASPEY-TAGMULIM",
    "YITRAT-PITZUIM",
    "YITRAT-PITZUIM-MAASIK-NOCHECHI",
    "YITRAT-PITZUIM-LEKITZBA-MAAVIDIM-KODMIM",
    "ERECH-PIDION-PITZUIM-MAASIK-NOCHECHI",
    "ERECH-PIDION-PITZUIM-LEKITZBA-MAAVIDIM-KODMIM",
    "TOTAL-HAFKADOT-OVED-TAGMULIM-SHANA-NOCHECHIT",
    "TOTAL-HAFKADOT-MAAVID-TAGMULIM-SHANA-NOCHECHIT",
    "TOTAL-HAFKADOT-PITZUIM-SHANA-NOCHECHIT",
    "SCHUM-HAFKADA-SHESHULAM",
    "SCHUM-TAGMULIM",
    "SCHUM-PITURIM",
]

BALANCE_KEYWORDS = ["TAGMUL", "PITZ", "PITZU", "PITZUI"]

TAGMUL_PERIOD_COLUMNS: Dict[Tuple[str, str], str] = {
    ("employee", "before_2000"): "תגמולי עובד עד 2000",
    ("employee", "after_2000"): "תגמולי עובד אחרי 2000",
    ("employee", "after_2008_non_paying"): "תגמולי עובד אחרי 2008 (קצבה לא משלמת)",
    ("employer", "before_2000"): "תגמולי מעביד עד 2000",
    ("employer", "after_2000"): "תגמולי מעביד אחרי 2000",
    ("employer", "after_2008_non_paying"): "תגמולי מעביד אחרי 2008 (קצבה לא משלמת)",
}

TECHULAT_CODE_PERIOD = {
    "1": "before_2000",
    "2": "after_2000",
    "7": "after_2008_non_paying",
    "9": "after_2008_non_paying",
    "13": "after_2008_non_paying",
}

EMPLOYER_NAME_TAGS = [
    "SHEM-MAASIK",
    "SHEM-MESHALEM",
    "SHEM-BAAL-POLISA-SHEEINO-MEVUTAH",
    "SHEM-BAAL-POLISA",
    "SHEM-MAFKID",
    "SHEM-BEALIM",
    "SHEM-HAMESHALLEM",
]

PRODUCT_TYPE_MAP = {
    "1": "פוליסת ביטוח חיים משולב חיסכון",
    "2": "פוליסת ביטוח חיים",
    "3": "קופת גמל",
    "4": "קרן פנסיה",
    "5": "פוליסת חיסכון טהור",
}

SEVERANCE_COLUMN_TAGS: Dict[str, List[str]] = {
    "פיצויים מעסקי נוכחי": [
        "ERECH-PIDION-PITZUIM-MAASIK-NOCHECHI",
        "YITRAT-PITZUIM-MAASIK-NOCHECHI",
    ],
    "פיצויים לאחר התחשבנות": [
        "ERECH-PIDION-PITZUIM-LEKITZBA-MAAVIDIM-KODMIM",
    ],
    "פיצויים שלא עברו התחשבנות": [
        "TZVIRAT-PITZUIM-PTURIM-MAAVIDIM-KODMIM",
        "YITRAT-PITZUIM-LELO-HITCHASHBENOT",
    ],
    "פיצויים ממעסיקים קודמים ברצף זכויות": [
        "TZVIRAT-PITZUIM-MAAVIDIM-KODMIM-BERETZEF-ZECHUYOT",
    ],
    "פיצויים ממעסיקים קודמים ברצף קצבה": [
        "TZVIRAT-PITZUIM-MAAVIDIM-KODMIM-BERETZEF-KITZBA",
    ],
}

TAGMUL_ROLE_BY_REKIV = {
    "2": "employee",
    "3": "employer",
    "8": "employee",
    "9": "employer",
}

TAGMUL_FIELD_MAP = {
    "תגמולי עובד עד 2000": "תגמולי_עובד_עד_2000",
    "תגמולי עובד אחרי 2000": "תגמולי_עובד_אחרי_2000",
    "תגמולי עובד אחרי 2008 (קצבה לא משלמת)": "תגמולי_עובד_אחרי_2008_לא_משלמת",
    "תגמולי מעביד עד 2000": "תגמולי_מעביד_עד_2000",
    "תגמולי מעביד אחרי 2000": "תגמולי_מעביד_אחרי_2000",
    "תגמולי מעביד אחרי 2008 (קצבה לא משלמת)": "תגמולי_מעביד_אחרי_2008_לא_משלמת",
}

EMPLOYEE_SUG_CODES = {"2", "4", "8", "10"}
EMPLOYER_SUG_CODES = {"3", "7", "9", "11"}

BALANCE_TOLERANCE = 0.5
NUMERIC_SENTINELS = {"", "0", "0.0", "0.00", "NIL", "None", "none"}


class PensionPortfolioProcessor:
    """Service wrapper around the XML processing pipeline used in the misłaka tool."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)

    def process_file(self, content: str, file_name: str) -> dict:
        processor = _PensionFileProcessor(content=content, file_name=file_name, logger=self.logger)
        return processor.process()


class _PensionFileProcessor:
    """Processes the content of a single pension clearing house file."""

    def __init__(self, content: str, file_name: str, logger: logging.Logger):
        self.content = content
        self.file_name = file_name
        self.logger = logger
        self.tree: Optional[ET.ElementTree] = None
        self.root: Optional[ET.Element] = None
        self.parent_map: Dict[ET.Element, ET.Element] = {}
        self._global_cache: Dict[str, str] = {}

    def process(self) -> Optional[dict]:
        if not self._load_content():
            return None
        return self._extract_data()

    def _load_content(self) -> bool:
        cleaned = self.content.replace("\x1a", "").replace("\x00", "").strip()
        if not cleaned:
            self.logger.warning("Empty content received for %s", self.file_name)
            return False

        for attempt, payload in enumerate((cleaned, self._try_fix_xml(cleaned)), start=1):
            if payload is None:
                continue
            try:
                self.tree = ET.ElementTree(ET.fromstring(payload))
                self.root = self.tree.getroot()
                self.parent_map = {child: parent for parent in self.root.iter() for child in parent}
                if attempt > 1:
                    self.logger.info("Successfully repaired XML for %s", self.file_name)
                return True
            except ET.ParseError as exc:
                self.logger.warning("XML parse attempt %s failed for %s: %s", attempt, self.file_name, exc)
                continue
            except Exception as exc:  # pragma: no cover - defensive
                self.logger.exception("Unexpected error loading %s: %s", self.file_name, exc)
                return False
        return False

    def _extract_data(self) -> Optional[dict]:
        if self.root is None:
            return None

        account_nodes = self._locate_account_nodes(self.root)
        accounts: List[Dict[str, Any]] = []

        for account_elem in account_nodes:
            account = self._extract_account(account_elem)
            if account:
                accounts.append(account)

        return {
            "file": self.file_name,
            "accounts": accounts,
            "processed_at": datetime.now().isoformat(),
        }

    def _locate_account_nodes(self, root: ET.Element) -> List[ET.Element]:
        candidates = [
            "HeshbonOPolisa",
            "Heshbon",
            "Account",
            "Policy",
            "Polisa",
            "PensionAccount",
            "PensionPolicy",
            "KupatGemel",
            "BituachMenahalim",
            "KerenPensia",
        ]
        nodes: List[ET.Element] = []
        for name in candidates:
            nodes.extend(root.findall(f".//{name}"))

        if not nodes:
            for elem in root.iter():
                if self._has_account_children(elem):
                    nodes.append(elem)

        if not nodes and self._has_account_data(root):
            nodes = [root]

        return nodes

    @staticmethod
    def _has_account_children(elem: ET.Element) -> bool:
        account_tags = {
            "MISPAR-POLISA-O-HESHBON",
            "MISPAR-HESHBON",
            "MISPAR-POLISA",
            "SHEM-YATZRAN",
            "YATZRAN",
            "SHEM-TOCHNIT",
            "TOCHNIT",
        }
        return any(child.tag in account_tags for child in elem)

    @staticmethod
    def _has_account_data(elem: ET.Element) -> bool:
        tag_candidates = [
            "MISPAR-POLISA-O-HESHBON",
            "MISPAR-HESHBON",
            "MISPAR-POLISA",
        ]
        return any(elem.find(f".//{tag}") is not None for tag in tag_candidates)

    def _extract_account(self, account_elem: ET.Element) -> Optional[Dict[str, Any]]:
        account_number = self._get_first_text(account_elem, [
            "MISPAR-POLISA-O-HESHBON",
            "MISPAR-HESHBON",
            "MISPAR-POLISA",
        ]) or "לא ידוע"

        plan_name = self._get_first_text(account_elem, [
            "SHEM-TOCHNIT",
            "TOCHNIT",
            "SHEM_TOCHNIT",
        ]) or "לא ידוע"

        managing_company = self._resolve_managing_company(account_elem)

        managing_code = self._get_first_text(account_elem, [
            "KOD-MEZAHE-YATZRAN",
            "KOD-YATZRAN",
            "MEZAHE-YATZRAN",
        ])

        balance = self._find_balance(account_elem)
        balance_date = self._get_first_text(account_elem, [
            "TAARICH-NECHONUT-YITROT",
            "TAARICH-YITROT",
            "TAARICH-NECHONUT",
        ]) or "לא ידוע"

        start_date = self._get_first_text(account_elem, [
            "TAARICH-TCHILAT-HAFRASHA",
            "TAARICH-TCHILA",
            "TAARICH-HITZTARFUT-RISHON",
            "TAARICH-HITZTARFUT",
        ])

        product_type_code = self._get_first_text(account_elem, [
            "SUG-MUTZAR",
            "SUG-TOCHNIT-O-CHESHBON",
            "SUG-POLISA",
        ])
        product_type = self._resolve_product_type(account_elem, product_type_code, plan_name)

        employers = self._collect_employer_names(account_elem)
        balance_fields = self._collect_balance_related_fields(account_elem)
        severance_components = self._extract_severance_components(balance_fields)
        tagmul_periods = self._collect_tagmul_periods(account_elem)

        total_contributions = sum(tagmul_periods.values())
        total_severance = sum(severance_components.values())
        total_components = total_contributions + total_severance
        discrepancy = balance - total_components
        if abs(discrepancy) <= BALANCE_TOLERANCE:
            discrepancy = 0.0

        if (
            account_number == "לא ידוע"
            and plan_name == "לא ידוע"
            and balance == 0
        ):
            return None

        account = {
            "מספר_חשבון": account_number,
            "שם_תכנית": plan_name,
            "חברה_מנהלת": managing_company,
            "קוד_חברה_מנהלת": managing_code or "",
            "יתרה": balance,
            "תאריך_נכונות_יתרה": balance_date,
            "תאריך_התחלה": start_date or "",
            "סוג_מוצר": product_type,
            "מעסיקים_היסטוריים": ", ".join(employers),
            "רכיבי_פיצויים": severance_components,
            "תגמולים_לפי_תקופה": tagmul_periods,
            "סך_תגמולים": total_contributions,
            "סך_פיצויים": total_severance,
            "סך_רכיבים": total_components,
            "פער_יתרה_מול_רכיבים": discrepancy,
            "שדות_פיצויים_תגמולים": balance_fields,
            "selected": False,
            "selected_amounts": {},
            "debug_plan_name": plan_name,
            "קובץ_מקור": self.file_name,
        }

        # Flatten severance components into top-level keys. Use normalized field names
        account.update({
            "פיצויים_מעסיק_נוכחי": severance_components.get("פיצויים מעסקי נוכחי", 0.0),
            "פיצויים_לאחר_התחשבנות": severance_components.get("פיצויים לאחר התחשבנות", 0.0),
            "פיצויים_שלא_עברו_התחשבנות": severance_components.get("פיצויים שלא עברו התחשבנות", 0.0),
            "פיצויים_ממעסיקים_קודמים_רצף_זכויות": severance_components.get("פיצויים ממעסיקים קודמים ברצף זכויות", 0.0),
            "פיצויים_ממעסיקים_קודמים_רצף_קצבה": severance_components.get("פיצויים ממעסיקים קודמים ברצף קצבה", 0.0),
        })

        # Flatten tagmul periods into known columns
        for column_name, field_name in TAGMUL_FIELD_MAP.items():
            account[field_name] = tagmul_periods.get(column_name, 0.0)

        # Primary tagmul column (used elsewhere in the app)
        account["תגמולים"] = self._extract_primary_tagmul(balance_fields, total_contributions, severance_components)

        return account

    def _find_balance(self, account_elem: ET.Element) -> float:
        total, count = self._sum_fields(
            account_elem,
            ".//BlockItrot//PerutYitrot",
            ["TOTAL-CHISACHON-MTZBR", "TOTAL-ERKEI-PIDION"],
        )
        if count > 0:
            if total > BALANCE_TOLERANCE:
                return total
            if abs(total) <= BALANCE_TOLERANCE:
                return 0.0

        total, count = self._sum_fields(
            account_elem,
            ".//PerutMasluleiHashkaa",
            ["SCHUM-TZVIRA-BAMASLUL", "TOTAL-CHISACHON-MTZBR"],
        )
        if count > 0:
            if total > BALANCE_TOLERANCE:
                return total
            if abs(total) <= BALANCE_TOLERANCE:
                return 0.0

        total, count = self._sum_fields(
            account_elem,
            ".//PerutYitrotLesofShanaKodemet",
            ["YITRAT-SOF-SHANA", "TOTAL-CHISACHON-MTZBR"],
        )
        if count > 0:
            if total > BALANCE_TOLERANCE:
                return total
            if abs(total) <= BALANCE_TOLERANCE:
                return 0.0

        for field in [
            "SCHUM-TZVIRA-BAMASLUL",
            "YITRAT-KASPEY-TAGMULIM",
            "TOTAL-CHISACHON-MTZBR",
            "TOTAL-ERKEI-PIDION",
            "SCHUM-HON-EFSHAR",
            "SCHUM-CHISACHON",
            "SCHUM-TAGMULIM",
            "SCHUM-PITURIM",
            "ERECH-PIDION-PITZUIM-LEKITZBA-MAAVIDIM-KODMIM",
            "ERECH-PIDION-PITZUIM-MAASIK-NOCHECHI",
        ]:
            value = self._get_float(account_elem, field)
            if value and value > 0:
                return value

        potential: List[Tuple[float, float, str]] = []
        for elem in account_elem.iter():
            if elem.text and any(ch.isdigit() for ch in elem.text):
                try:
                    numeric = float(elem.text.replace(",", ""))
                except (ValueError, AttributeError):
                    continue
                if numeric <= 0:
                    continue
                tag_upper = elem.tag.upper()
                weight = 2.0 if any(keyword in tag_upper for keyword in ["SCHUM", "YITRAT", "ERECH"]) else 1.0
                potential.append((weight, numeric, elem.tag))
        if potential:
            potential.sort(key=lambda item: (-item[0], -item[1]))
            return potential[0][1]

        return 0.0

    def _sum_fields(self, base_elem: ET.Element, xpath: str, field_candidates: List[str]) -> Tuple[float, int]:
        total = 0.0
        count = 0
        for node in base_elem.findall(xpath):
            value: Optional[float] = None
            for field in field_candidates:
                value = self._get_float(node, field)
                if value is not None:
                    break
            if value is not None:
                total += value
                count += 1
        return total, count

    def _get_first_text(self, elem: ET.Element, tags: List[str]) -> Optional[str]:
        for tag in tags:
            text = self._get_text(elem, tag)
            if text:
                return text
        return None

    def _get_text(self, elem: ET.Element, tag: str) -> str:
        child = elem.find(tag)
        if child is not None and child.text:
            return child.text.strip()
        return ""

    def _get_float(self, elem: ET.Element, tag: str) -> Optional[float]:
        text = self._get_text(elem, tag)
        if not text:
            return None
        try:
            return float(text.replace(",", ""))
        except ValueError:
            return None

    def _collect_tag_values(self, start_elem: ET.Element, tag: str, include_parents: bool = True) -> List[str]:
        values: List[str] = []
        current = start_elem
        visited: set[int] = set()
        while current is not None and id(current) not in visited:
            visited.add(id(current))
            for node in current.findall(f".//{tag}"):
                if node.text and node.text.strip():
                    values.append(node.text.strip())
            if not include_parents:
                break
            current = self.parent_map.get(current)
        seen: set[str] = set()
        unique_values: List[str] = []
        for value in values:
            if value not in seen:
                seen.add(value)
                unique_values.append(value)
        return unique_values

    def _collect_specific_tags(self, start_elem: ET.Element, tags: List[str], include_parents: bool = True) -> Dict[str, str]:
        collected: Dict[str, str] = {}
        for tag in tags:
            values = self._collect_tag_values(start_elem, tag, include_parents=include_parents)
            if values:
                collected[tag] = " | ".join(values)
        return collected

    def _collect_balance_related_fields(self, account_elem: ET.Element) -> Dict[str, str]:
        collected: Dict[str, List[str]] = {}
        explicit = set(BALANCE_EXPLICIT_TAGS)
        for node in account_elem.iter():
            if not node.text or not node.text.strip():
                continue
            tag_upper = node.tag.upper()
            is_explicit = node.tag in explicit
            has_keyword = any(keyword in tag_upper for keyword in BALANCE_KEYWORDS)
            if not (is_explicit or has_keyword):
                continue
            value = node.text.strip()
            collected.setdefault(node.tag, []).append(value)

        result: Dict[str, str] = {}
        for tag, values in collected.items():
            seen: set[str] = set()
            unique_values: List[str] = []
            for value in values:
                if value not in seen:
                    seen.add(value)
                    unique_values.append(value)
            result[tag] = " | ".join(unique_values)
        return result

    def _collect_tagmul_periods(self, account_elem: ET.Element) -> Dict[str, float]:
        totals: Dict[Tuple[str, str], float] = {key: 0.0 for key in TAGMUL_PERIOD_COLUMNS}
        has_period_data = {"employee": False, "employer": False}

        for period in account_elem.findall(".//BlockItrot//PerutYitraLeTkufa"):
            rekiv = self._get_text(period, "REKIV-ITRA-LETKUFA")
            techulat = self._get_text(period, "KOD-TECHULAT-SHICHVA")
            amount = self._get_float(period, "SACH-ITRA-LESHICHVA-BESHACH")
            if amount is None:
                continue
            role = TAGMUL_ROLE_BY_REKIV.get(rekiv)
            if role is None:
                continue
            period_key = TECHULAT_CODE_PERIOD.get(techulat)
            if not period_key:
                continue
            has_period_data[role] = True
            totals[(role, period_key)] += amount

        if not all(has_period_data.values()):
            for yitrot in account_elem.findall(".//BlockItrot//PerutYitrot"):
                sug = self._get_text(yitrot, "KOD-SUG-HAFRASHA")
                amount = self._get_float(yitrot, "TOTAL-CHISACHON-MTZBR")
                if amount is None or not sug:
                    continue
                role: Optional[str] = None
                if not has_period_data["employee"] and sug in EMPLOYEE_SUG_CODES:
                    role = "employee"
                elif not has_period_data["employer"] and sug in EMPLOYER_SUG_CODES:
                    role = "employer"
                if role is None:
                    continue
                totals[(role, "after_2000")] += amount

        result: Dict[str, float] = {}
        for key, total in totals.items():
            if total:
                column_name = TAGMUL_PERIOD_COLUMNS[key]
                result[column_name] = total
        return result

    def _collect_employer_names(self, account_elem: ET.Element) -> List[str]:
        names: List[str] = []
        seen: set[str] = set()
        for tag in EMPLOYER_NAME_TAGS:
            values = self._collect_tag_values(account_elem, tag, include_parents=True)
            for value in values:
                clean = value.strip().strip("\"").strip("'").replace(" | ", " ").strip()
                if clean and clean not in seen:
                    seen.add(clean)
                    names.append(clean)
        return names

    def _resolve_managing_company(self, account_elem: ET.Element) -> str:
        # חיפוש קודם כל ברמת החשבון וההורים
        for tag in ["SHEM-YATZRAN", "SHEM-METAFEL", "SHEM_HA_MOSAD", "Provider", "Company"]:
            values = self._collect_tag_values(account_elem, tag, include_parents=True)
            for value in values:
                clean = value.strip()
                if clean:
                    return clean

        # fallback גלובלי
        for tag in ["SHEM-YATZRAN", "SHEM-METAFEL", "SHEM_HA_MOSAD", "Provider", "Company"]:
            global_value = self._get_global_text(tag)
            if global_value:
                return global_value

        return "לא ידוע"

    def _resolve_product_type(self, account_elem: ET.Element, product_type_code: Optional[str], plan_name: str) -> str:
        """Determine product type using the same rules as the mislaka PensionFileProcessor._get_product_type.

        The product_type_code argument is intentionally ignored to avoid overriding SUG-MUTZAR
        with less reliable fields like SUG-TOCHNIT-O-CHESHBON or SUG-POLISA.
        """

        # 1. Try to infer from plan names (SHEM-TOCHNIT/TOCHNIT/SHEM_TOCHNIT)
        plan_name_tags = ["SHEM-TOCHNIT", "TOCHNIT", "SHEM_TOCHNIT"]
        plan_names: List[str] = []
        for tag in plan_name_tags:
            names = self._collect_tag_values(account_elem, tag, include_parents=True)
            for name in names:
                normalized = (name or "").strip()
                if normalized:
                    plan_names.append(normalized)

        normalized_plan_name = (plan_name or "").strip()
        if normalized_plan_name and normalized_plan_name not in plan_names:
            plan_names.insert(0, normalized_plan_name)

        name_type: Optional[str] = None
        for name in plan_names:
            name_lower = name.lower()
            if "גמל להשקעה" in name or "קופת גמל להשקעה" in name:
                name_type = "גמל להשקעה"
                break
            if "השתלמות" in name:
                name_type = "קרן השתלמות"
                break
            if "פנסיה" in name or "מקפת" in name or "עתודות" in name:
                name_type = "קרן פנסיה"
                break
            if "גמל" in name:
                name_type = "קופת גמל"
                break
            if "ביטוח" in name and ("חיים" in name or "מנהלים" in name or "מנהל" in name):
                if "מקפת" in name or "פנסיה" in name:
                    name_type = "קרן פנסיה"
                    break
                name_type = "פוליסת ביטוח חיים"
                break
            if "חיסכון" in name or "savings" in name_lower:
                name_type = "פוליסת חיסכון טהור"
                break

        # 2. Try to infer from SUG-MUTZAR codes only (no overrides from other type codes)
        codes = self._collect_tag_values(account_elem, "SUG-MUTZAR", include_parents=True)
        if not codes:
            code = self._get_text(account_elem, "SUG-MUTZAR")
            codes = [code] if code else []

        code_type: Optional[str] = None
        for code in codes:
            normalized_code = (code or "").strip()
            if not normalized_code:
                continue
            mapped = PRODUCT_TYPE_MAP.get(normalized_code)
            if mapped:
                code_type = mapped
                break

        # 3. Reconcile name-based and code-based types, following mislaka rules
        if code_type and name_type:
            if code_type == name_type:
                return code_type
            if code_type in {
                "פוליסת ביטוח חיים משולב חיסכון",
                "פוליסת ביטוח חיים",
                "פוליסת חיסכון טהור",
            }:
                if name_type in {"קרן פנסיה", "קרן השתלמות"}:
                    return name_type
                return code_type
            return name_type

        # 4. Fallbacks matching mislaka behavior
        if name_type:
            return name_type

        if code_type:
            return code_type

        if plan_names:
            return plan_names[0]

        for code in codes:
            normalized_code = (code or "").strip()
            if normalized_code:
                return normalized_code

        return ""

    def _get_global_text(self, tag: str) -> Optional[str]:
        if tag in self._global_cache:
            return self._global_cache[tag]

        if self.root is None:
            return None

        node = self.root.find(f".//{tag}")
        value = node.text.strip() if node is not None and node.text else None
        if value:
            self._global_cache[tag] = value
        else:
            self._global_cache[tag] = None  # type: ignore
        return value

    @staticmethod
    def _infer_product_from_name(name: str) -> Optional[str]:
        lower = name.lower()
        if "השתלמות" in lower:
            return "קרן השתלמות"
        if "פנס" in lower:
            return "קרן פנסיה"
        if "קופת גמל" in lower or "ק' גמל" in lower or "גמל" in lower:
            return "קופת גמל"
        if "קופ" in lower and "גמל" in lower:
            return "קופת גמל"
        if "ביטוח מנה" in lower:
            return "ביטוח מנהלים"
        if "משולב חיסכון" in lower or "ביטוח חיים משולב" in lower:
            return "פוליסת ביטוח חיים משולב חיסכון"
        if "ביטוח" in lower and "חיים" in lower:
            return "פוליסת ביטוח חיים"
        if "חיסכון טהור" in lower or "חסכון טהור" in lower:
            return "פוליסת חיסכון טהור"
        if "השתלמות" in lower or "חינוך" in lower:
            return "קרן השתלמות"
        return name.strip() if name.strip() else None

    def _extract_severance_components(self, balance_fields: Dict[str, str]) -> Dict[str, float]:
        components: Dict[str, float] = {}
        for column, tags in SEVERANCE_COLUMN_TAGS.items():
            total = 0.0
            for tag in tags:
                raw = balance_fields.get(tag)
                total += self._safe_sum_values(raw)
            if total:
                components[column] = total
        return components

    def _safe_sum_values(self, value: Any) -> float:
        if value is None:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            parts = [part.strip() for part in value.split("|") if part.strip()]
            total = 0.0
            for part in parts:
                normalized = part.replace(",", "")
                if normalized in NUMERIC_SENTINELS:
                    continue
                try:
                    total += float(normalized)
                except ValueError:
                    continue
            return total
        if isinstance(value, list):
            return sum(self._safe_sum_values(item) for item in value)
        return 0.0

    def _extract_primary_tagmul(
        self,
        balance_fields: Dict[str, str],
        total_contributions: float,
        severance_components: Dict[str, float],
    ) -> float:
        raw = balance_fields.get("YITRAT-KASPEY-TAGMULIM")
        primary = self._safe_sum_values(raw)
        if primary:
            deductions = (
                severance_components.get("פיצויים מעסקי נוכחי", 0.0)
                + severance_components.get("פיצויים לאחר התחשבנות", 0.0)
                + severance_components.get("פיצויים שלא עברו התחשבנות", 0.0)
            )
            adjusted = primary - deductions
            return adjusted if adjusted > 0 else max(primary, total_contributions)
        return total_contributions

    def _try_fix_xml(self, content: str) -> Optional[str]:
        try:
            sanitized = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", content)
            if not sanitized.strip().startswith("<?xml"):
                sanitized = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n" + sanitized
            sanitized = re.sub(r"<\s+", "<", sanitized)
            sanitized = re.sub(r"\s+>", ">", sanitized)
            open_tags = re.findall(r"<([A-Za-z0-9\-]+)[^>]*>", sanitized)
            close_tags = re.findall(r"</([A-Za-z0-9\-]+)>", sanitized)
            if len(open_tags) > len(close_tags) and not re.search(r"<root", sanitized, re.IGNORECASE):
                xml_decl_end = sanitized.find("?>") + 2 if "?>" in sanitized else 0
                before = sanitized[:xml_decl_end]
                after = sanitized[xml_decl_end:]
                sanitized = before + "\n<root>\n" + after.strip() + "\n</root>"
            return sanitized
        except Exception:  # pragma: no cover - defensive
            self.logger.exception("Failed to auto-repair XML for %s", self.file_name)
            return None



__all__ = ["PensionPortfolioProcessor"]
