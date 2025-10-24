"""בדיקה מהירה של לקוח 6"""
import sys
sys.path.insert(0, '.')

from app.database import SessionLocal
from app.models.grant import Grant
from app.models.client import Client
from app.services.rights_fixation import calculate_full_fixation
from datetime import date

db = SessionLocal()

try:
    # בדיקת לקוח
    client = db.query(Client).filter(Client.id == 6).first()
    if not client:
        print("❌ לקוח 6 לא קיים")
        sys.exit(1)
    
    print(f"✅ לקוח 6: {client.first_name} {client.last_name}")
    print(f"   תאריך לידה: {client.birth_date}")
    print(f"   מגדר: {client.gender}")
    print(f"   תאריך תחילת קצבה: {client.pension_start_date}")
    
    # בדיקת מענקים
    grants = db.query(Grant).filter(Grant.client_id == 6).all()
    print(f"\n📊 מענקים: {len(grants)}")
    
    if len(grants) == 0:
        print("❌ אין מענקים ללקוח 6!")
        sys.exit(1)
    
    for g in grants:
        print(f"   - {g.employer_name}: {g.grant_amount:,.0f} ₪")
        print(f"     עבודה: {g.work_start_date} עד {g.work_end_date}")
        print(f"     תאריך מענק: {g.grant_date}")
    
    # חישוב קיבוע זכויות
    print("\n🔄 מחשב קיבוע זכויות...")
    
    formatted_data = {
        "id": 6,
        "birth_date": client.birth_date.isoformat() if client.birth_date else None,
        "gender": client.gender,
        "grants": [
            {
                "grant_amount": grant.grant_amount,
                "work_start_date": grant.work_start_date.isoformat() if grant.work_start_date else None,
                "work_end_date": grant.work_end_date.isoformat() if grant.work_end_date else None,
                "grant_date": grant.grant_date.isoformat() if hasattr(grant, 'grant_date') and grant.grant_date else None,
                "employer_name": grant.employer_name
            }
            for grant in grants
        ],
        "eligibility_date": client.pension_start_date.isoformat() if client.pension_start_date else date.today().isoformat(),
        "eligibility_year": client.pension_start_date.year if client.pension_start_date else date.today().year
    }
    
    result = calculate_full_fixation(formatted_data)
    
    print("\n📋 תוצאות:")
    print(f"   מענקים מעובדים: {len(result.get('grants', []))}")
    
    exemption = result.get('exemption_summary', {})
    print(f"\n💰 סיכום פטור:")
    print(f"   יתרת הון פטורה ראשונית: {exemption.get('exempt_capital_initial', 0):,.0f} ₪")
    print(f"   סך פגיעה בפטור: {exemption.get('total_impact', 0):,.0f} ₪")
    print(f"   יתרה נותרת: {exemption.get('remaining_exempt_capital', 0):,.0f} ₪")
    print(f"   קצבה פטורה חודשית: {exemption.get('remaining_monthly_exemption', 0):,.2f} ₪")
    print(f"   אחוז פטור: {exemption.get('exemption_percentage', 0) * 100:.2f}%")
    
    if exemption.get('exempt_capital_initial', 0) == 0:
        print("\n❌ בעיה: יתרת הון פטורה ראשונית = 0!")
        print("   בודק את הפונקציה calc_exempt_capital...")
        
        from app.services.rights_fixation import calc_exempt_capital
        year = formatted_data['eligibility_year']
        test_capital = calc_exempt_capital(year)
        print(f"   calc_exempt_capital({year}) = {test_capital:,.0f} ₪")
        
        if test_capital == 0:
            print("   ❌ הפונקציה מחזירה 0!")
        else:
            print("   ✅ הפונקציה עובדת, הבעיה במקום אחר")
    
finally:
    db.close()

print("\n✅ בדיקה הושלמה")
