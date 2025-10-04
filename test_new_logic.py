import requests
import json

def test_new_logic():
    """בדיקת הלוגיקה החדשה של קיבוע זכויות"""
    try:
        response = requests.post('http://localhost:8005/api/v1/rights-fixation/calculate', 
                               json={'client_id': 2})
        
        if response.status_code == 200:
            result = response.json()
            print('=== הלוגיקה החדשה עובדת! ===')
            
            if result.get('grants'):
                grant = result['grants'][0]
                print('\nפרטי מענק:')
                print('- מענק מקורי:', grant.get('grant_amount'))
                print('- יחס 32 שנים:', grant.get('grant_ratio'))
                print('- סכום מוצמד:', grant.get('grant_indexed_amount'))
                print('- השפעה על פטור:', grant.get('impact_on_exemption'))
                
                if grant.get('exclusion_reason'):
                    print('- סיבת החרגה:', grant['exclusion_reason'])
            
            if result.get('exemption_summary'):
                summary = result['exemption_summary']
                print('\nסיכום פטור:')
                print('- הון פטור ראשוני:', summary.get('exempt_capital_initial'))
                print('- סהכ השפעה:', summary.get('total_impact'))
                print('- הון פטור נותר:', summary.get('remaining_exempt_capital'))
                
            print('\nתאריך זכאות:', result.get('eligibility_date'))
            print('שנת זכאות:', result.get('eligibility_year'))
                
        else:
            print('שגיאה:', response.status_code)
            print(response.text)
            
    except Exception as e:
        print('שגיאה:', e)

if __name__ == "__main__":
    test_new_logic()
