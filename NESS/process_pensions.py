import os
import glob
import json
import csv
import logging
from datetime import datetime
import xml.etree.ElementTree as ET

try:
    import pandas as pd  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    pd = None

MANAGING_COMPANY_TAGS = [
    'SHEM-METAFEL',
    'SHEM-YATZRAN',
    'SHEM_HA_MOSAD',
    'Provider',
    'Company',
    'KOD-MEZAHE-METAFEL',
    'KOD-MEZAHE-YATZRAN',
    'KOD-YATZRAN',
    'MEZAHE-YATZRAN'
]

PLAN_TYPE_TAGS = [
    'SUG-TOCHNIT-O-CHESHBON',
    'SUG-POLISA',
    'SUG-MUTZAR',
    'SUG-KEREN-PENSIA',
    'SUG-KUPA',
    'SUG-HAFRASHA'
]

BALANCE_EXPLICIT_TAGS = [
    'TOTAL-CHISACHON-MTZBR',
    'TOTAL-ERKEI-PIDION',
    'YITRAT-KASPEY-TAGMULIM',
    'YITRAT-PITZUIM',
    'YITRAT-PITZUIM-MAASIK-NOCHECHI',
    'YITRAT-PITZUIM-LEKITZBA-MAAVIDIM-KODMIM',
    'ERECH-PIDION-PITZUIM-MAASIK-NOCHECHI',
    'ERECH-PIDION-PITZUIM-LEKITZBA-MAAVIDIM-KODMIM',
    'TOTAL-HAFKADOT-OVED-TAGMULIM-SHANA-NOCHECHIT',
    'TOTAL-HAFKADOT-MAAVID-TAGMULIM-SHANA-NOCHECHIT',
    'TOTAL-HAFKADOT-PITZUIM-SHANA-NOCHECHIT',
    'SCHUM-HAFKADA-SHESHULAM',
    'SCHUM-TAGMULIM',
    'SCHUM-PITURIM'
]

BALANCE_KEYWORDS = ['TAGMUL', 'PITZ', 'PITZU', 'PITZUI']

TAGMUL_PERIOD_COLUMNS = {
    ('employee', 'before_2000'): 'תגמולי עובד עד 2000',
    ('employee', 'after_2000'): 'תגמולי עובד אחרי 2000',
    ('employee', 'after_2008_non_paying'): 'תגמולי עובד אחרי 2008 (קצבה לא משלמת)',
    ('employer', 'before_2000'): 'תגמולי מעביד עד 2000',
    ('employer', 'after_2000'): 'תגמולי מעביד אחרי 2000',
    ('employer', 'after_2008_non_paying'): 'תגמולי מעביד אחרי 2008 (קצבה לא משלמת)'
}

TECHULAT_CODE_PERIOD = {
    '1': 'before_2000',
    '2': 'after_2000',
    '7': 'after_2008_non_paying'
}

EMPLOYER_NAME_TAGS = [
    'SHEM-MAASIK',
    'SHEM-MESHALEM',
    'SHEM-BAAL-POLISA-SHEEINO-MEVUTAH',
    'SHEM-BAAL-POLISA',
    'SHEM-MAFKID',
    'SHEM-BEALIM',
    'SHEM-HAMESHALLEM'
]

PRODUCT_TYPE_MAP = {
    '1': 'פוליסת ביטוח חיים משולב חיסכון',
    '2': 'פוליסת ביטוח חיים',
    '3': 'קופת גמל',
    '4': 'קרן פנסיה',
    '5': 'פוליסת חיסכון טהור'
}

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

class PensionFileProcessor:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.tree = None
        self.root = None
        self.parent_map = {}
    
    def process(self) -> dict:
        try:
            if not self._load_file():
                return None
            return self._extract_data()
        except Exception as e:
            logging.error(f"Error processing {self.file_path}: {str(e)}")
            return None
    
    def _load_file(self) -> bool:
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            content = content.replace('\x1a', '')  # Clean up any special characters
            self.tree = ET.ElementTree(ET.fromstring(content))
            self.root = self.tree.getroot()
            self.parent_map = {child: parent for parent in self.root.iter() for child in parent}
            return True
        except Exception as e:
            logging.error(f"Failed to load {self.file_path}: {str(e)}")
            return False
    
    def _extract_data(self) -> dict:
        """Extract account data from the XML file using a generic approach."""
        accounts = []
        
        # Try different possible account element names
        account_elements = [
            'HeshbonOPolisa',  # Common in many pension files
            'Heshbon',         # Common in many pension files
            'Account',         # Generic account element
            'Policy',          # Insurance policy
            'Polisa',          # Policy in Hebrew
            'PensionAccount',  # Generic pension account
            'PensionPolicy',   # Generic pension policy
            'KupatGemel',     # קופת גמל
            'BituachMenahalim', # ביטוח מנהלים
            'KerenPensia'     # קרן פנסיה
        ]
        
        # Find all account elements using different possible names
        account_nodes = []
        for elem_name in account_elements:
            account_nodes.extend(self.root.findall(f'.//{elem_name}'))
        
        # If no accounts found, try to find any element that looks like an account
        if not account_nodes:
            for elem in self.root.iter():
                # If the element has common account-like child elements
                has_account_like_children = any(
                    child.tag in ['MISPAR-POLISA-O-HESHBON', 'MISPAR-HESHBON', 'MISPAR-POLISA', 
                                 'SHEM-YATZRAN', 'YATZRAN', 'SHEM-TOCHNIT', 'TOCHNIT']
                    for child in elem
                )
                if has_account_like_children:
                    account_nodes.append(elem)
        
        # If still no accounts found, use the root element as the account
        if not account_nodes and (self.root.find('.//MISPAR-POLISA-O-HESHBON') is not None or 
                                 self.root.find('.//MISPAR-HESHBON') is not None or
                                 self.root.find('.//MISPAR-POLISA') is not None):
            account_nodes = [self.root]
        
        for account in account_nodes:
            # Get account number from common field names
            acc_number = self._get_text(account, 'MISPAR-POLISA-O-HESHBON') or \
                        self._get_text(account, 'MISPAR-HESHBON') or \
                        self._get_text(account, 'MISPAR-POLISA') or \
                        self._get_text(account, 'AccountNumber') or \
                        self._get_text(account, 'AccountId') or \
                        self._get_text(account, 'PolicyNumber') or \
                        'לא ידוע'
            
            # Get company name from common field names (fallback)
            company = self._get_text(account, 'SHEM-YATZRAN') or \
                     self._get_text(account, 'YATZRAN') or \
                     self._get_text(account, 'SHEM_HA_MOSAD') or \
                     self._get_text(account, 'Company') or \
                     self._get_text(account, 'Provider') or \
                     'לא ידוע'
            
            # Get plan name from common field names
            plan = self._get_text(account, 'SHEM-TOCHNIT') or \
                  self._get_text(account, 'TOCHNIT') or \
                  self._get_text(account, 'SHEM_TOCHNIT') or \
                  'לא ידוע'
            
            # Get plan type
            plan_type = self._get_plan_type(account)

            # Get balance
            balance = self._find_balance(account)

            # Get balance valuation date
            balance_date = self._get_balance_date(account)

            # Get managing company details (name/code)
            managing_company_name, managing_company_code = self._get_managing_company(account, fallback_name=company)

            # Collect all managing company tag values
            managing_company_fields = self._collect_specific_tags(account, MANAGING_COMPANY_TAGS)

            # Collect all plan type related tag values
            plan_type_fields = self._collect_specific_tags(account, PLAN_TYPE_TAGS, include_parents=False)

            # Collect balances related to tagmulim/pitzuyim
            balance_related_fields = self._collect_balance_related_fields(account)
            tagmul_periods = self._collect_tagmul_periods(account)
            employer_names = self._collect_employer_names(account)
            start_date = self._get_start_date(account)
            product_type = self._get_product_type(account)

            acc_data = {
                'מספר_חשבון': acc_number,
                'שם_תכנית': plan,
                'חברה_מנהלת': managing_company_fields.get('SHEM-YATZRAN', managing_company_name),
                'קוד_חברה_מנהלת': managing_company_code,
                'יתרה': balance,
                'תאריך_נכונות_יתרה': balance_date if balance_date else 'לא ידוע',
                'תאריך_התחלה': start_date,
                'סוג_מוצר': product_type,
                'מעסיקים_היסטוריים': '.'.join(employer_names)
            }

            acc_data['שדות_חברה_מנהלת'] = managing_company_fields
            acc_data['שדות_סוג_תוכנית'] = plan_type_fields
            acc_data['שדות_פיצויים_תגמולים'] = balance_related_fields
            acc_data['תגמולים_לפי_תקופה'] = tagmul_periods
            acc_data['שמות_מעסיקים'] = employer_names
            accounts.append(acc_data)
        
        return {
            'file': os.path.basename(self.file_path),
            'accounts': accounts,
            'processed_at': datetime.now().isoformat()
        }
    
    def _find_balance(self, account_elem) -> float:
        """Return the best-estimate balance for an account."""
        # 1. Sum balances reported per track in BlockItrot/PerutYitrot sections
        yitrot_total, yitrot_count = self._sum_fields(
            account_elem,
            './/BlockItrot//PerutYitrot',
            ['TOTAL-CHISACHON-MTZBR', 'TOTAL-ERKEI-PIDION']
        )
        if yitrot_total > 0 and yitrot_count > 0:
            return yitrot_total

        # 2. Sum balances from investment track details if BlockItrot missing
        maslul_total, maslul_count = self._sum_fields(
            account_elem,
            './/PerutMasluleiHashkaa',
            ['SCHUM-TZVIRA-BAMASLUL', 'TOTAL-CHISACHON-MTZBR']
        )
        if maslul_total > 0 and maslul_count > 0:
            return maslul_total

        # 3. Look for end-of-year balance summaries
        end_year_total, end_year_count = self._sum_fields(
            account_elem,
            './/PerutYitrotLesofShanaKodemet',
            ['YITRAT-SOF-SHANA', 'TOTAL-CHISACHON-MTZBR']
        )
        if end_year_total > 0 and end_year_count > 0:
            return end_year_total

        # 4. Generic search for common balance fields anywhere under the account
        generic_fields = [
            'SCHUM-TZVIRA-BAMASLUL',
            'YITRAT-KASPEY-TAGMULIM',
            'TOTAL-CHISACHON-MTZBR',
            'TOTAL-ERKEI-PIDION',
            'SCHUM-HON-EFSHAR',
            'SCHUM-CHISACHON',
            'SCHUM-TAGMULIM',
            'SCHUM-PITURIM',
            'ERECH-PIDION-PITZUIM-LEKITZBA-MAAVIDIM-KODMIM',
            'ERECH-PIDION-PITZUIM-MAASIK-NOCHECHI'
        ]
        for field in generic_fields:
            value = self._get_float(account_elem, field)
            if value is not None and value > 0:
                return value

        # 5. Fall back to scanning numeric values as a last resort
        potential_balances = []
        for elem in account_elem.iter():
            if elem.text and any(c.isdigit() for c in elem.text):
                try:
                    value = float(elem.text.replace(',', ''))
                    if value > 0:
                        tag = elem.tag.upper()
                        weight = 1.0
                        if 'SCHUM' in tag or 'YITRAT' in tag or 'ERECH' in tag:
                            weight = 2.0
                        potential_balances.append((weight, value, elem.tag))
                except (ValueError, AttributeError):
                    continue

        if potential_balances:
            potential_balances.sort(key=lambda x: (-x[0], -x[1]))
            return potential_balances[0][1]

        return 0.0

    def _sum_fields(self, base_elem, xpath: str, field_candidates: list[str]) -> tuple[float, int]:
        """Sum numeric values for the first available field in each matched node."""
        total = 0.0
        count = 0
        for node in base_elem.findall(xpath):
            value = None
            for field in field_candidates:
                value = self._get_float(node, field)
                if value is not None:
                    break
            if value is not None:
                total += value
                count += 1
        return total, count
    
    def _get_text(self, elem, tag: str, default: str = '') -> str:
        child = elem.find(tag)
        return child.text.strip() if child is not None and child.text else default

    def _find_text_anywhere(self, elem, tag: str) -> str:
        node = elem.find(f'.//{tag}')
        return node.text.strip() if node is not None and node.text else ''

    def _collect_tag_values(self, start_elem, tag: str, include_parents: bool = True) -> list[str]:
        values: list[str] = []
        current = start_elem
        visited: set[int] = set()
        while current is not None and id(current) not in visited:
            visited.add(id(current))
            for node in current.findall(f'.//{tag}'):
                if node.text and node.text.strip():
                    values.append(node.text.strip())
            if not include_parents:
                break
            current = self.parent_map.get(current)
        # Deduplicate preserving order
        seen = set()
        unique_values = []
        for value in values:
            if value not in seen:
                seen.add(value)
                unique_values.append(value)
        return unique_values

    def _collect_specific_tags(self, start_elem, tags: list[str], include_parents: bool = True) -> dict[str, str]:
        collected: dict[str, str] = {}
        for tag in tags:
            values = self._collect_tag_values(start_elem, tag, include_parents=include_parents)
            if values:
                collected[tag] = ' | '.join(values)
        return collected

    def _get_managing_company(self, account_elem, fallback_name: str = 'לא ידוע') -> tuple[str, str]:
        name = ''
        code = ''
        name_tags = [tag for tag in MANAGING_COMPANY_TAGS if not tag.startswith('KOD') and 'MEZAHE' not in tag.upper()]
        code_tags = [tag for tag in MANAGING_COMPANY_TAGS if tag.startswith('KOD') or 'MEZAHE' in tag.upper()]

        for tag in name_tags:
            values = self._collect_tag_values(account_elem, tag)
            if values:
                name = values[0]
                break

        for tag in code_tags:
            values = self._collect_tag_values(account_elem, tag)
            if values:
                code = values[0]
                break

        if not name:
            name = fallback_name or 'לא ידוע'
        if not code:
            code = 'לא ידוע'

        return name, code
    
    def _get_plan_type(self, account_elem) -> str:
        """Try to determine the plan type based on available fields."""
        type_fields = [
            'SUG-TOCHNIT-O-CHESHBON',
            'SUG-POLISA',
            'SUG-MUTZAR',
            'SUG-KEREN-PENSIA',
            'SUG-KUPA',
            'SUG-HAFRASHA'
        ]

        for field in type_fields:
            value = self._get_text(account_elem, field)
            if value:
                return value

        # Check for known indicators
        if account_elem.find('.//HODAAT-LEKULAM') is not None:
            return 'קופת גמל'
        if account_elem.find('.//HODAAT-LEPENSIA') is not None:
            return 'קרן פנסיה'
        if account_elem.find('.//HODAAT-LIBRAT') is not None:
            return 'ביטוח מנהלים'

        return 'לא ידוע'

    def _get_balance_date(self, account_elem) -> str:
        date_fields = [
            'TAARICH-NECHONUT',
            'TAARICH-ERECH-TZVIROT',
            'TAARICH-ERECH',
            'TAARICH-MADAD',
            'TAARICH-ERECH-HAFKADA'
        ]

        for field in date_fields:
            value = self._get_text(account_elem, field)
            if value:
                return self._format_date(value)

        yitrot_date = account_elem.find('.//BlockItrot//TAARICH-ERECH-TZVIROT')
        if yitrot_date is not None and yitrot_date.text:
            return self._format_date(yitrot_date.text)

        return ''
        
    def _get_float(self, elem, tag: str) -> float:
        try:
            text = self._get_text(elem, tag)
            return float(text.replace(',', '')) if text else None
        except (ValueError, AttributeError):
            return None

    def _format_date(self, value: str) -> str:
        if not value:
            return ''
        value = value.strip()
        if value.isdigit():
            if len(value) == 8:
                return f"{value[:4]}-{value[4:6]}-{value[6:]}"
            if len(value) == 6:
                return f"{value[:4]}-{value[4:6]}"
        return value

    def _collect_balance_related_fields(self, account_elem) -> dict[str, str]:
        collected: dict[str, list[str]] = {}
        explicit_set = set(BALANCE_EXPLICIT_TAGS)
        for node in account_elem.iter():
            if not node.text or not node.text.strip():
                continue
            tag_upper = node.tag.upper()
            is_explicit = node.tag in explicit_set
            has_keyword = any(keyword in tag_upper for keyword in BALANCE_KEYWORDS)
            if not (is_explicit or has_keyword):
                continue
            value = node.text.strip()
            collected.setdefault(node.tag, []).append(value)

        result: dict[str, str] = {}
        for tag, values in collected.items():
            seen = set()
            unique_values = []
            for value in values:
                if value not in seen:
                    seen.add(value)
                    unique_values.append(value)
            result[tag] = ' | '.join(unique_values)
        return result

    def _collect_tagmul_periods(self, account_elem) -> dict[str, float]:
        totals_by_key: dict[tuple[str, str], float] = {key: 0.0 for key in TAGMUL_PERIOD_COLUMNS}

        for period in account_elem.findall('.//BlockItrot//PerutYitraLeTkufa'):
            rekiv = self._get_text(period, 'REKIV-ITRA-LETKUFA')
            techulat = self._get_text(period, 'KOD-TECHULAT-SHICHVA')
            amount = self._get_float(period, 'SACH-ITRA-LESHICHVA-BESHACH')

            if amount is None:
                continue

            if rekiv == '2':
                role = 'employee'
            elif rekiv == '3':
                role = 'employer'
            else:
                continue

            period_key = TECHULAT_CODE_PERIOD.get(techulat)
            if not period_key:
                continue

            totals_by_key[(role, period_key)] += amount

        result: dict[str, float] = {}
        for key, total in totals_by_key.items():
            if total:
                column_name = TAGMUL_PERIOD_COLUMNS[key]
                result[column_name] = total

        return result

    def _get_start_date(self, account_elem) -> str:
        date_value = self._get_text(account_elem, 'TAARICH-HITZTARFUT-RISHON')
        if date_value:
            return self._format_date(date_value)
        return ''

    def _get_product_type(self, account_elem) -> str:
        codes = self._collect_tag_values(account_elem, 'SUG-MUTZAR', include_parents=True)
        if not codes:
            code = self._get_text(account_elem, 'SUG-MUTZAR')
            codes = [code] if code else []

        for code in codes:
            if code in PRODUCT_TYPE_MAP:
                return PRODUCT_TYPE_MAP[code]

        return codes[0] if codes else ''

    def _collect_employer_names(self, account_elem) -> list[str]:
        names: list[str] = []
        seen: set[str] = set()

        for tag in EMPLOYER_NAME_TAGS:
            values = self._collect_tag_values(account_elem, tag, include_parents=True)
            for value in values:
                clean_value = value.strip().strip('"').strip("'")
                clean_value = clean_value.replace(' | ', ' ').strip()
                if not clean_value or clean_value in seen:
                    continue
                seen.add(clean_value)
                names.append(clean_value)

        return names

def process_directory(directory: str, output_file: str = None) -> list:
    print(f"Scanning directory: {directory}")
    xml_files = glob.glob(os.path.join(directory, '**/*.xml'), recursive=True)
    
    if not xml_files:
        print(f"No XML files found in {directory} or its subdirectories")
        print("Available files and directories:")
        for item in os.listdir(directory):
            print(f"- {item}")
        return []
    results = []
    xml_files = glob.glob(os.path.join(directory, '*.xml'))

    if not xml_files:
        print(f"No XML files found in {directory}")
        return []

    print(f"Found {len(xml_files)} XML files to process...")

    for xml_file in xml_files:
        print(f"\nProcessing {os.path.basename(xml_file)}...")
        processor = PensionFileProcessor(xml_file)
        result = processor.process()
        if result:
            results.append(result)
            print(f"  Found {len(result['accounts'])} accounts")

    # Save results
    if results:
        output_file = os.path.join(directory, 'pension_results')

        # Save as JSON
        json_file = f"{output_file}.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\nResults saved to: {json_file}")

        # Prepare flattened rows once for CSV/Excel
        flattened_rows = []
        for result in results:
            for account in result.get('accounts', []):
                row = {}
                for field in ['חברה מנהלת', 'מספר_חשבון', 'שם_תכנית', 'יתרה', 'תאריך_נכונות_יתרה']:
                    row[field] = account.get(field, '')

                balance_tags = account.get('שדות_פיצויים_תגמולים', {})
                row['חברה מנהלת'] = account.get('חברה_מנהלת', '')

                row['פיצויים מעסקי נוכחי'] = balance_tags.get('ERECH-PIDION-PITZUIM-MAASIK-NOCHECHI', '')
                row['פיצויים לאחר התחשבנות'] = balance_tags.get('ERECH-PIDION-PITZUIM-LEKITZBA-MAAVIDIM-KODMIM', '')
                row['פיצויים שלא עברו התחשבנות'] = balance_tags.get('TZVIRAT-PITZUIM-PTURIM-MAAVIDIM-KODMIM', '')
                row['פיצויים ממעסיקים קודמים ברצף זכויות'] = balance_tags.get('TZVIRAT-PITZUIM-MAAVIDIM-KODMIM-BERETZEF-ZECHUYOT', '')
                row['פיצויים ממעסיקים קודמים ברצף קצבה'] = balance_tags.get('TZVIRAT-PITZUIM-MAAVIDIM-KODMIM-BERETZEF-KITZBA', '')
                employer_list = account.get('שמות_מעסיקים', [])
                if isinstance(employer_list, list):
                    row['מעסיקים היסטוריים'] = '.'.join(employer_list)
                else:
                    row['מעסיקים היסטוריים'] = account.get('מעסיקים_היסטוריים', '')
                row['תאריך התחלה'] = account.get('תאריך_התחלה', '')
                row['סוג מוצר'] = account.get('סוג_מוצר', '')

                tagmul_periods = account.get('תגמולים_לפי_תקופה', {})
                for column_name in TAGMUL_PERIOD_COLUMNS.values():
                    value = tagmul_periods.get(column_name)
                    row[column_name] = f"{value:.2f}" if value is not None and value != 0 else ''

                flattened_rows.append(row)

        fieldnames = [
            'חברה מנהלת',
            'מספר_חשבון',
            'שם_תכנית',
            'יתרה',
            'תאריך_נכונות_יתרה',
            'תאריך התחלה',
            'סוג מוצר',
            'מעסיקים היסטוריים',
            'פיצויים מעסקי נוכחי',
            'פיצויים לאחר התחשבנות',
            'פיצויים שלא עברו התחשבנות',
            'פיצויים ממעסיקים קודמים ברצף זכויות',
            'פיצויים ממעסיקים קודמים ברצף קצבה'
        ]

        fieldnames.extend(TAGMUL_PERIOD_COLUMNS.values())
        # Save as CSV
        csv_file = f"{output_file}.csv"
        with open(csv_file, 'w', encoding='utf-8-sig', newline='') as f:
            if flattened_rows:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for row in flattened_rows:
                    writer.writerow({field: row.get(field, '') for field in fieldnames})
        print(f"CSV results saved to: {csv_file}")

        # Save as Excel if pandas is available
        if pd is not None and flattened_rows:
            excel_file = f"{output_file}.xlsx"
            df = pd.DataFrame([{field: row.get(field, '') for field in fieldnames} for row in flattened_rows], columns=fieldnames)
            df.to_excel(excel_file, index=False)
            print(f"Excel results saved to: {excel_file}")
        elif pd is None:
            print("Pandas is not installed; skipping Excel export. Install with 'pip install pandas openpyxl' to enable it.")

    return results

def main():
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Look for XML files in the DATA subdirectory
    data_dir = os.path.join(script_dir, 'DATA')

    if not os.path.exists(data_dir):
        print(f"Error: The DATA directory was not found at: {data_dir}")
        print("Please make sure the DATA directory exists and contains your XML files.")
        return

    print(f"Looking for XML files in: {data_dir}")
    process_directory(data_dir)

if __name__ == "__main__":
    main()
