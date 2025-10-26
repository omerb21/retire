"""בדיקת API לקיבוע זכויות של לקוח 6"""
import requests
import json

# קריאה ל-API
url = "http://localhost:8005/api/v1/rights-fixation/calculate"
data = {"client_id": 6}

print("🔄 שולח בקשה ל-API...")
print(f"URL: {url}")
print(f"Data: {data}")

try:
    response = requests.post(url, json=data)
    print(f"\n📡 תגובה: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        
        print("\n📋 מענקים:")
        for grant in result.get('grants', []):
            print(f"\n  {grant.get('employer_name', 'N/A')}:")
            print(f"    סכום מקורי: ₪{grant.get('grant_amount', 0):,.0f}")
            print(f"    מוצמד מלא: ₪{grant.get('indexed_full', 0):,.0f}")
            print(f"    יחס 32 שנים: {grant.get('ratio_32y', 0):.4f} ({grant.get('ratio_32y', 0) * 100:.2f}%)")
            print(f"    סכום מוגבל (ליצוא פקיד): ₪{grant.get('limited_indexed_amount', 0):,.0f}")
            print(f"    פגיעה בפטור: ₪{grant.get('impact_on_exemption', 0):,.0f}")
            
            # בדיקה אם יש קיזוז
            ratio = grant.get('ratio_32y', 1.0)
            if ratio < 1.0:
                reduction = (1.0 - ratio) * 100
                print(f"    ✅ קיזוז: {reduction:.2f}% (שנים מעל גיל פרישה)")
            else:
                print(f"    ❌ אין קיזוז - היחס הוא 100%!")
        
        print("\n💰 סיכום פטור:")
        exemption = result.get('exemption_summary', {})
        print(f"  יתרה ראשונית: ₪{exemption.get('exempt_capital_initial', 0):,.0f}")
        print(f"  סך פגיעה: ₪{exemption.get('total_impact', 0):,.0f}")
        print(f"  יתרה נותרת: ₪{exemption.get('remaining_exempt_capital', 0):,.0f}")
        
    else:
        print(f"❌ שגיאה: {response.text}")
        
except Exception as e:
    print(f"❌ שגיאה בקריאה ל-API: {e}")

print("\n✅ בדיקה הושלמה")
