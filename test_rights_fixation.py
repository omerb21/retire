"""
בדיקת מערכת קיבוע זכויות
"""
import requests
import json
from datetime import datetime

def test_rights_fixation_system():
    """בדיקה מקיפה של מערכת קיבוע זכויות"""
    
    base_url = "http://localhost:8005"
    
    print("🔍 בדיקת מערכת קיבוע זכויות...")
    
    # 1. בדיקת בריאות השרת
    try:
        response = requests.get(f"{base_url}/health")
        print(f"✅ בריאות השרת: {response.json()}")
    except Exception as e:
        print(f"❌ שגיאה בבדיקת בריאות השרת: {e}")
        return False
    
    # 2. בדיקת API של הלמ"ס
    try:
        response = requests.get(f"{base_url}/api/v1/rights-fixation/test")
        result = response.json()
        print(f"✅ בדיקת API למ\"ס: {result}")
    except Exception as e:
        print(f"❌ שגיאה בבדיקת API למ\"ס: {e}")
    
    # 3. בדיקת תקרות לשנה
    try:
        response = requests.get(f"{base_url}/api/v1/rights-fixation/caps/2025")
        caps = response.json()
        print(f"✅ תקרות 2025: {caps}")
    except Exception as e:
        print(f"❌ שגיאה בקבלת תקרות: {e}")
    
    # 4. בדיקת חישוב קיבוע זכויות מלא
    test_data = {
        "grants": [
            {
                "grant_amount": 100000,
                "work_start_date": "2010-01-01",
                "work_end_date": "2020-12-31",
                "employer_name": "חברה א'",
                "grant_date": "2021-01-01"
            },
            {
                "grant_amount": 50000,
                "work_start_date": "2015-06-01",
                "work_end_date": "2022-05-31",
                "employer_name": "חברה ב'",
                "grant_date": "2022-06-01"
            }
        ],
        "eligibility_date": "2025-01-01",
        "eligibility_year": 2025
    }
    
    try:
        response = requests.post(
            f"{base_url}/api/v1/rights-fixation/calculate",
            json=test_data
        )
        
        if response.status_code == 200:
            result = response.json()
            print("\n🎯 תוצאות חישוב קיבוע זכויות:")
            print(f"📅 תאריך זכאות: {result.get('eligibility_date')}")
            print(f"📊 שנת זכאות: {result.get('eligibility_year')}")
            
            print("\n📋 מענקים מעובדים:")
            for i, grant in enumerate(result.get('grants', []), 1):
                print(f"  {i}. {grant.get('employer_name')}:")
                print(f"     💰 סכום מקורי: ₪{grant.get('grant_amount'):,}")
                print(f"     📈 סכום מוצמד: ₪{grant.get('indexed_full', 0):,.2f}")
                print(f"     📊 יחס 32 שנים: {grant.get('ratio_32y', 0):.2%}")
                print(f"     🎯 סכום מוגבל: ₪{grant.get('limited_indexed_amount', 0):,.2f}")
                print(f"     💥 פגיעה בפטור: ₪{grant.get('impact_on_exemption', 0):,.2f}")
            
            exemption = result.get('exemption_summary', {})
            print("\n💡 סיכום פטור:")
            print(f"  🏛️ הון פטור התחלתי: ₪{exemption.get('exempt_capital_initial', 0):,.2f}")
            print(f"  💥 סך פגיעה: ₪{exemption.get('total_impact', 0):,.2f}")
            print(f"  💰 הון פטור נותר: ₪{exemption.get('remaining_exempt_capital', 0):,.2f}")
            print(f"  📅 פטור חודשי נותר: ₪{exemption.get('remaining_monthly_exemption', 0):,.2f}")
            print(f"  📊 אחוז פטור: {exemption.get('exemption_percentage', 0):.1%}")
            
            print("\n✅ בדיקת מערכת קיבוע זכויות הושלמה בהצלחה!")
            return True
            
        else:
            print(f"❌ שגיאה בחישוב קיבוע זכויות: {response.status_code}")
            print(f"   תגובה: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ שגיאה בבדיקת חישוב קיבוע זכויות: {e}")
        return False

if __name__ == "__main__":
    success = test_rights_fixation_system()
    if success:
        print("\n🎉 כל הבדיקות עברו בהצלחה!")
    else:
        print("\n⚠️ יש בעיות במערכת קיבוע זכויות")
