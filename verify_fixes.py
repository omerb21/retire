from app.database import SessionLocal
from app.models.client import Client
from app.models.pension_fund import PensionFund

def verify_fixes():
    db = SessionLocal()
    try:
        client = db.query(Client).filter(Client.id_number == '123456789').first()
        if client:
            print("=== בדיקת תיקונים ===")
            print(f"שם: {client.first_name} {client.last_name}")
            print(f"מין: {client.gender}")
            print(f"תאריך התחלת קצבה: {client.pension_start_date}")
            print(f"נקודות זיכוי: {client.tax_credit_points}")
            
            print("\n=== קרנות פנסיה ===")
            pension_funds = db.query(PensionFund).filter(PensionFund.client_id == client.id).all()
            for fund in pension_funds:
                print(f"{fund.fund_name}: {fund.pension_amount} ש\"ח")
                
        else:
            print("לקוח לא נמצא!")
            
    finally:
        db.close()

if __name__ == "__main__":
    verify_fixes()
