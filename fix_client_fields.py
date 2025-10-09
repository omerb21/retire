#!/usr/bin/env python3
"""
תיקון שדות הלקוח החסרים
"""
from datetime import date
from app.database import get_db
from app.models.client import Client

def fix_client_fields():
    """תיקון שדות הלקוח החסרים"""
    db = next(get_db())
    
    try:
        # מציאת לקוח 1
        client = db.query(Client).filter(Client.id == 1).first()
        if client:
            print(f"מעדכן לקוח: {client.first_name} {client.last_name}")
            
            # עדכון השדות החסרים
            client.pension_start_date = date(2024, 1, 1)
            client.tax_credit_points = 2.25
            
            db.commit()
            print("✅ השדות עודכנו בהצלחה")
            
            # בדיקה
            db.refresh(client)
            print(f"תאריך התחלת קצבה: {client.pension_start_date}")
            print(f"נקודות זיכוי: {client.tax_credit_points}")
            
        else:
            print("❌ לקוח לא נמצא")
            
    except Exception as e:
        print(f"❌ שגיאה: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_client_fields()
