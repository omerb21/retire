import os
import xml.etree.ElementTree as ET
import pandas as pd
import glob

def find_client_balances():
    """מערכת למציאת יתרות הלקוח מיכאל לנדסמן בקבצי המסלקה"""
    print("🔍 מחפש את יתרות הלקוח מיכאל לנדסמן בקבצים...")
    print("=" * 90)

    # הנתונים האמיתיים של הלקוח מיכאל לנדסמן
    client_accounts = {
        '391117': 157642.02,
        '421789': 46031.88,
        '8557281': 2779.62,
        '56544653': 437662.00,
        '2887123': 1605668.32,
        '6029331': 170639.80,
        '6504775': 380295.12,
        '4337198': 597172.19,
        '1873538': 544863.59,
        '1880186': 585086.53,
        '9675237': 27197.84
    }

    print(f"📋 חשבונות הלקוח לאיתור: {len(client_accounts)} חשבונות")
    print("מספרי החשבונות:", ', '.join(client_accounts.keys()))

    # חיפוש קבצי XML
    search_paths = [os.getcwd(), os.path.join(os.getcwd(), 'DATA')]
    xml_files = []

    for path in search_paths:
        if os.path.exists(path):
            pattern = os.path.join(path, '*.xml')
            files = glob.glob(pattern)
            xml_files.extend(files)

    print(f"📄 נמצאו {len(xml_files)} קבצי XML לחיפוש")

    if not xml_files:
        print("❌ לא נמצאו קבצי XML")
        return None

    found_accounts = {}
    all_balance_fields = {}

    # רשימה מקיפה של שדות יתרה אפשריים
    balance_field_patterns = [
        'YITRAT', 'SCHUM', 'ERECH', 'TOTAL', 'KISUY', 'CHISACHON', 'KITZVOT', 'GEMEL', 'HASHTALMUT'
    ]

    for xml_file in xml_files:
        display_name = os.path.basename(xml_file)
        print(f"\n📄 מחפש בחשבונות בקובץ: {display_name}")

        try:
            with open(xml_file, 'r', encoding='utf-8') as f:
                content = f.read()

            content = content.replace('\x1a', '')
            root = ET.fromstring(content)

            # חיפוש כל החשבונות בקובץ
            accounts = root.findall('.//HeshbonOPolisa')
            print(f"   נמצאו {len(accounts)} חשבונות בקובץ")

            for account in accounts:
                # חיפוש מספר חשבון
                account_num_elem = account.find('MISPAR-POLISA-O-HESHBON')
                if account_num_elem is None or not account_num_elem.text:
                    continue

                account_num = account_num_elem.text.strip()
                # בדיקה אם זה אחד מהחשבונות של הלקוח
                if account_num in client_accounts:
                    print(f"   🎯 נמצא חשבון הלקוח: {account_num}")

                    # חיפוש כל האלמנטים בחשבון למציאת יתרות
                    account_balances = {}

                    # רשימה מקיפה של שדות יתרה אפשריים
                    balance_field_patterns = [
                        'YITRAT', 'SCHUM', 'ERECH', 'TOTAL', 'KISUY', 'CHISACHON', 'KITZVOT', 'GEMEL', 'HASHTALMUT'
                    ]

                    for elem in root.iter():
                        if elem.text and any(char.isdigit() for char in elem.text):
                            try:
                                value = float(elem.text.replace(',', ''))
                                if value > 0:
                                    field_name = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                                    
                                    # עדכון רשימת השדות הכללית
                                    if field_name not in all_balance_fields:
                                        all_balance_fields[field_name] = []
                                    all_balance_fields[field_name].append((account_num, value))
                                    
                                    # הוספת הערך למילון החשבון הנוכחי
                                    if field_name not in account_balances:
                                        account_balances[field_name] = []
                                    account_balances[field_name].append(value)
                                    
                                    # דיווח על שדות בעלי ערך זהה ליתרה האמיתית
                                    if account_num in client_accounts and abs(value - client_accounts[account_num]) < 0.01:
                                        print(f"      🔍 התאמה מדויקת: {field_name} = {value:,.2f} (צפוי: {client_accounts[account_num]:,.2f})")
                                        
                            except (ValueError, AttributeError):
                                continue

                    if account_balances:
                        # בחירת היתרה הטובה ביותר עבור החשבון
                        best_balance = 0
                        best_field = 'לא נמצא'

                        for field, values in account_balances.items():
                            max_value = max(values)
                            if max_value > best_balance:
                                best_balance = max_value
                                best_field = field

                        found_accounts[account_num] = {
                            'יתרה_נמצאה': best_balance,
                            'מקור_היתרה': best_field,
                            'כל_השדות': account_balances,
                            'קובץ': display_name,
                            'יתרה_אמיתית': client_accounts[account_num]
                        }

                        print(f"      ✅ יתרה נמצאה: {best_balance:,.2f} מתוך {best_field}")

        except Exception as e:
            print(f"   ❌ שגיאה בעיבוד {display_name}: {e}")

    # ניתוח התוצאות
    print(f"\n{'='*120}")
    print("תוצאות חיפוש יתרות הלקוח מיכאל לנדסמן")
    print(f"{'='*120}")

    found_count = 0
    correct_count = 0
    total_real_balance = 0

    print(f"{'מספר חשבון':<15} {'יתרה אמיתית':>15} {'יתרה נמצאה':>15} {'מקור':<25} {'סטטוס':<10}")
    print("-" * 140)

    for account_num in sorted(client_accounts.keys()):
        real_balance = client_accounts[account_num]
        total_real_balance += real_balance

        if account_num in found_accounts:
            found_balance = found_accounts[account_num]['יתרה_נמצאה']
            source = found_accounts[account_num]['מקור_היתרה']
            found_count += 1

            # בדיקה אם היתרה נכונה (סטייה של עד 1%)
            if abs(found_balance - real_balance) / real_balance < 0.01:
                status = "✅ נכון"
                correct_count += 1
            else:
                status = "❌ שגוי"
        else:
            found_balance = 0
            source = "לא נמצא"
            status = "❌ חסר"

        print(f"{account_num:<15} {real_balance:>13,.2f} {found_balance:>13,.2f} {source:<25} {status:<10}")

    print("-" * 140)
    print(f"{'סיכום:':<15} {total_real_balance:>13,.2f} {sum(acc['יתרה_נמצאה'] for acc in found_accounts.values()):>13,.2f} ({found_count}/{len(client_accounts)} נמצאו, {correct_count} נכונות)")

    # הצגת כל השדות שנמצאו
    print(f"\n📋 שדות יתרה שנמצאו בכל הקבצים:")
    for field, values in sorted(all_balance_fields.items()):
        unique_accounts = set(acc for acc, val in values)
        print(f"   {field}: נמצא ב-{len(unique_accounts)} חשבונות, ערכים: {[val for acc, val in values[:3]]}{'...' if len(values) > 3 else ''}")

    return found_accounts

if __name__ == "__main__":
    results = find_client_balances()

    if results:
        print("\n✅ המערכת מצאה את חשבונות הלקוח! ניתן להשתמש בתוצאות לשיפור המערכת הכללית.")
    else:
        print("\n❌ לא נמצאו חשבונות הלקוח בקבצים")
