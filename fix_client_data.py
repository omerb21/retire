from app.database import SessionLocal
from app.models.client import Client
from app.models.pension_fund import PensionFund
from datetime import date

def fix_client_data():
    db = SessionLocal()
    try:
        # תיקון נתוני הלקוח
        client = db.query(Client).filter(Client.id_number == '123456789').first()
        if client:
            print(f"מתקן נתוני לקוח: {client.full_name}")
            
            # 1. תיקון מין לזכר
            client.gender = "זכר"
            print("✓ מין עודכן לזכר")
            
            # 2. תיקון תאריך התחלת קצבה
            client.pension_start_date = date(2024, 1, 1)
            print("✓ תאריך התחלת קצבה עודכן ל-01/01/2024")
            
            # 3. תיקון נקודות זיכוי
            client.tax_credit_points = 2.25
            print("✓ נקודות זיכוי עודכנו ל-2.25")
            
            db.commit()
            
            # 4. תיקון סכומי קרנות פנסיה
            pension_funds = db.query(PensionFund).filter(PensionFund.client_id == client.id).all()
            for fund in pension_funds:
                if fund.fund_name == "מקפת":
                    fund.pension_amount = 5000.0
                    print("✓ קרן מקפת עודכנה ל-5000")
                elif fund.fund_name == "מנורה":
                    fund.pension_amount = 6666.0
                    print("✓ קרן מנורה עודכנה ל-6666")
            
            db.commit()
            print("כל התיקונים הושלמו בהצלחה!")
            
        else:
            print("לקוח לא נמצא!")
            
    except Exception as e:
        print(f"שגיאה: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_client_data()
