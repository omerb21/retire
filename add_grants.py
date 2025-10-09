from app.database import SessionLocal
from app.models.grant import Grant
from datetime import date

def add_grants():
    db = SessionLocal()
    try:
        # בדיקה אם כבר יש מענקים
        existing_grants = db.query(Grant).filter(Grant.client_id == 1).all()
        if existing_grants:
            print(f"כבר קיימים {len(existing_grants)} מענקים")
            for grant in existing_grants:
                print(f"- {grant.employer_name}: {grant.grant_amount} ({grant.work_start_date} - {grant.work_end_date})")
            return
        
        # יצירת מענקים חדשים
        grants_data = [
            {
                "employer_name": "מעסיק קודם 1",
                "work_start_date": date(1980, 1, 1),
                "work_end_date": date(1999, 12, 31),
                "amount": 100000.0,
                "grant_type": "severance"
            },
            {
                "employer_name": "מעסיק קודם 2", 
                "work_start_date": date(2000, 1, 1),
                "work_end_date": date(2011, 12, 31),
                "amount": 90000.0,
                "grant_type": "severance"
            },
            {
                "employer_name": "מעסיק קודם 3",
                "work_start_date": date(2012, 1, 1),
                "work_end_date": date(2021, 12, 31),
                "amount": 80000.0,
                "grant_type": "severance"
            }
        ]
        
        for grant_data in grants_data:
            grant = Grant(
                client_id=1,
                employer_name=grant_data["employer_name"],
                work_start_date=grant_data["work_start_date"],
                work_end_date=grant_data["work_end_date"],
                grant_amount=grant_data["amount"]
            )
            db.add(grant)
            print(f"✓ נוסף מענק: {grant_data['employer_name']} - {grant_data['amount']} ש\"ח")
        
        db.commit()
        print("כל המענקים נוספו בהצלחה!")
        
    except Exception as e:
        print(f"שגיאה: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    add_grants()
