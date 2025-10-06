@app.post("/api/v1/clients/{client_id}/cashflow/integrate-pension-funds")
def integrate_pension_funds(client_id: int, cashflow_data: List = None):
    """שילוב קרנות פנסיה בתזרים מזומנים"""
    try:
        # קבלת קרנות הפנסיה של הלקוח
        client_funds = [fund for fund in pension_funds_db.values() if fund.get("client_id") == client_id]
        
        cashflow_entries = []
        
        for fund in client_funds:
            # חישוב קצבה חודשית
            monthly_amount = fund.get("monthly_amount", 0)
            if monthly_amount == 0 and "computed_monthly_amount" in fund:
                monthly_amount = fund.get("computed_monthly_amount", 0)
            
            # אם אין סכום חודשי מחושב, נחשב אותו לפי הסכום הצבור
            if monthly_amount == 0 and "accumulated_amount" in fund:
                accumulated = fund.get("accumulated_amount", 0)
                # הנחה: מקדם המרה של 200 (סטנדרט בתעשייה)
                monthly_amount = accumulated / 200
            
            # יצירת רשומות תזרים ל-12 חודשים
            for month in range(1, 13):
                date_str = f"2025-{month:02d}-10"  # קצבאות פנסיה משולמות בד״כ ב-10 לחודש
                
                fund_type = fund.get("fund_type", "pension")
                
                # תרגום סוג קרן לעברית
                fund_map = {
                    "pension": "קצבת פנסיה",
                    "provident": "קופת גמל",
                    "advanced_training": "קרן השתלמות",
                    "insurance": "ביטוח מנהלים",
                    "other": "קרן אחרת"
                }
                
                source_name = fund_map.get(fund_type, "קצבת פנסיה")
                
                cashflow_entries.append({
                    "date": date_str,
                    "amount": round(monthly_amount),
                    "source": source_name
                })
        
        return cashflow_entries
        
    except Exception as e:
        logger.error(f"Error integrating pension funds: {e}")
        return []

@app.post("/api/v1/clients/{client_id}/cashflow/integrate-all")
def integrate_all(client_id: int, cashflow_data: List = None):
    """שילוב כל המקורות בתזרים מזומנים"""
    try:
        # שילוב הכנסות נוספות
        incomes_cashflow = integrate_incomes(client_id, cashflow_data)
        
        # שילוב נכסי הון
        assets_cashflow = integrate_assets(client_id, cashflow_data)
        
        # שילוב קרנות פנסיה
        pension_cashflow = integrate_pension_funds(client_id, cashflow_data)
        
        # איחוד כל הרשומות
        all_cashflow = incomes_cashflow + assets_cashflow + pension_cashflow
        
        # מיון לפי תאריך
        all_cashflow.sort(key=lambda x: x["date"])
        
        return all_cashflow
        
    except Exception as e:
        logger.error(f"Error integrating all sources: {e}")
        return []
