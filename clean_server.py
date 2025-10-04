# -*- coding: utf-8 -*-
"""
שרת נקי עם הפונקציונליות הנכונה של קיבוע זכויות
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any
import logging
from datetime import datetime, date
import sys
import os

# הוספת הנתיב לapp כדי לייבא את המודולים
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

try:
    from app.services.rights_fixation import calculate_full_fixation
    RIGHTS_FIXATION_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import rights_fixation service: {e}")
    RIGHTS_FIXATION_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Clean Retirement Planning Server")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory databases
clients_db = {
    1: {
        "id": 1,
        "full_name": "יוסי כהן",
        "first_name": "יוסי",
        "last_name": "כהן",
        "id_number": "123456789",
        "birth_date": "1957-01-01",
        "birthdate": "1957-01-01",
        "gender": "male",
        "marital_status": "married",
        "email": None,
        "phone": None,
        "is_active": True,
        "pension_start_date": "2024-01-01",
        "num_children": 2,
        "is_disabled": False,
        "disability_percentage": None,
        "is_new_immigrant": False,
        "immigration_date": None,
        "is_veteran": False,
        "reserve_duty_days": 30,
        "tax_credit_points": None
    }
}

grants_db = {
    1: {
        "id": 1,
        "client_id": 1,
        "grant_type": "severance",
        "amount": 300000,
        "grant_date": "2023-12-31",
        "employer_name": "החברה הישראלית",
        "tax_withholding": 35000,
        "is_exempt": False,
        "exempt_amount": 0,
        "work_start_date": "2000-01-01",
        "work_end_date": "2023-12-31"
    }
}

pension_funds_db = {
    1: {
        "id": 1,
        "client_id": 1,
        "fund_name": "קרן פנסיה מנורה",
        "fund_number": "12345",
        "current_balance": 1200000,
        "monthly_amount": 5555,
        "computed_monthly_amount": 5555,
        "start_date": "2024-01-01"
    }
}

additional_incomes_db = {
    1: {
        "id": 1,
        "client_id": 1,
        "source_type": "business",
        "amount": 25000,
        "frequency": "monthly",
        "start_date": "2025-01-01",
        "end_date": "2035-01-01",
        "indexation_method": "none",
        "fixed_rate": 0,
        "tax_treatment": "taxable",
        "tax_rate": 0
    }
}

capital_assets_db = {
    1: {
        "id": 1,
        "client_id": 1,
        "asset_type": "real_estate",
        "description": "דירה להשכרה",
        "current_value": 2000000,
        "purchase_value": 1500000,
        "purchase_date": "2020-01-01",
        "annual_return": 3,
        "annual_return_rate": 0.03,
        "payment_frequency": "quarterly",
        "liquidity": "medium",
        "risk_level": "medium"
    }
}

@app.get("/health")
def health_check():
    return {"status": "ok", "server": "clean_server", "rights_fixation": RIGHTS_FIXATION_AVAILABLE}

# Client endpoints
@app.get("/api/v1/clients")
def get_clients():
    return list(clients_db.values())

@app.get("/api/v1/clients/{client_id}")
def get_client(client_id: int):
    if client_id not in clients_db:
        raise HTTPException(status_code=404, detail="Client not found")
    return clients_db[client_id]

@app.post("/api/v1/clients")
def create_client(client_data: dict):
    try:
        new_id = max(clients_db.keys()) + 1 if clients_db else 1
        first_name = client_data.get('first_name', '')
        last_name = client_data.get('last_name', '')
        full_name = f"{first_name} {last_name}".strip()
        
        new_client = {
            "id": new_id,
            "full_name": full_name,
            "first_name": first_name,
            "last_name": last_name,
            "id_number": client_data.get('id_number'),
            "birth_date": client_data.get('birth_date'),
            "birthdate": client_data.get('birth_date'),
            "gender": client_data.get('gender', 'male'),
            "marital_status": client_data.get('marital_status', 'single'),
            "email": client_data.get('email'),
            "phone": client_data.get('phone'),
            "is_active": client_data.get('is_active', True),
            "pension_start_date": client_data.get('pension_start_date'),
            "num_children": client_data.get('num_children'),
            "is_disabled": client_data.get('is_disabled'),
            "disability_percentage": client_data.get('disability_percentage'),
            "is_new_immigrant": client_data.get('is_new_immigrant'),
            "immigration_date": client_data.get('immigration_date'),
            "is_veteran": client_data.get('is_veteran'),
            "reserve_duty_days": client_data.get('reserve_duty_days'),
            "tax_credit_points": client_data.get('tax_credit_points')
        }
        
        clients_db[new_id] = new_client
        return new_client
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create client: {str(e)}")

# Grant endpoints
@app.get("/api/v1/clients/{client_id}/grants")
def get_grants(client_id: int):
    client_grants = [grant for grant in grants_db.values() if grant.get("client_id") == client_id]
    return client_grants

# Rights fixation endpoint - using the correct service
@app.post("/api/v1/rights-fixation/calculate")
def calculate_rights_fixation(data: dict):
    """חישוב קיבוע זכויות באמצעות השירות המקורי"""
    try:
        if not RIGHTS_FIXATION_AVAILABLE:
            raise HTTPException(status_code=503, detail="Rights fixation service not available")
        
        client_id = data.get("client_id")
        if not client_id or client_id not in clients_db:
            raise HTTPException(status_code=404, detail="Client not found")
        
        client = clients_db[client_id]
        
        # בדיקת זכאות
        birth_date = client.get("birth_date") or client.get("birthdate")
        if not birth_date:
            raise HTTPException(status_code=400, detail="Missing birth date")
        
        birth_date_obj = datetime.strptime(birth_date, "%Y-%m-%d").date()
        today = date.today()
        age = today.year - birth_date_obj.year - ((today.month, today.day) < (birth_date_obj.month, birth_date_obj.day))
        
        gender = client.get("gender", "male")
        eligibility_age = 67 if gender == "male" else 65
        
        if age < eligibility_age:
            reasons = [f"גיל נוכחי ({age}) נמוך מגיל הזכאות ({eligibility_age})"]
            eligibility_date = date(birth_date_obj.year + eligibility_age, birth_date_obj.month, birth_date_obj.day)
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "לא זכאי לקיבוע זכויות",
                    "reasons": reasons,
                    "eligibility_date": eligibility_date.isoformat()
                }
            )
        
        # קבלת מענקים
        grants = []
        for grant_id, grant in grants_db.items():
            if grant.get("client_id") == client_id:
                grants.append(grant)
        
        if not grants:
            return {
                "client_id": client_id,
                "grants": [],
                "exemption_summary": {
                    "exempt_capital_initial": 0,
                    "total_impact": 0,
                    "remaining_exempt_capital": 0,
                    "remaining_monthly_exemption": 0,
                    "eligibility_year": today.year,
                    "exemption_percentage": 0
                },
                "eligibility_date": today.isoformat(),
                "eligibility_year": today.year,
                "status": "no_grants"
            }
        
        # הכנת נתונים לשירות המקורי
        client_data_for_service = {
            "grants": grants,
            "eligibility_date": today.isoformat(),
            "eligibility_year": today.year
        }
        
        # קריאה לשירות המקורי
        result = calculate_full_fixation(client_data_for_service)
        
        # הוספת נתונים נוספים לתוצאה
        result["client_id"] = client_id
        result["status"] = "calculated"
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in rights fixation calculation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to calculate rights fixation: {str(e)}")

# Pension fund endpoints
@app.get("/api/v1/clients/{client_id}/pension-funds")
def get_pension_funds(client_id: int):
    client_funds = [fund for fund in pension_funds_db.values() if fund.get("client_id") == client_id]
    return client_funds

@app.post("/api/v1/clients/{client_id}/pension-funds")
def create_pension_fund(client_id: int, fund_data: dict):
    try:
        if client_id not in clients_db:
            raise HTTPException(status_code=404, detail="Client not found")
            
        new_id = max(pension_funds_db.keys()) + 1 if pension_funds_db else 1
        
        new_fund = {
            "id": new_id,
            "client_id": client_id,
            "fund_name": fund_data.get("fund_name", "קרן פנסיה"),
            "fund_number": fund_data.get("fund_number", ""),
            "fund_type": fund_data.get("fund_type", "pension"),
            "current_balance": fund_data.get("current_balance", 0) or fund_data.get("balance", 0),
            "monthly_amount": fund_data.get("monthly_amount", 0) or fund_data.get("pension_amount", 0),
            "computed_monthly_amount": fund_data.get("computed_monthly_amount", 0),
            "start_date": fund_data.get("start_date", "") or fund_data.get("pension_start_date", ""),
            "end_date": fund_data.get("end_date", ""),
            "employer_contributions": fund_data.get("employer_contributions", 0),
            "employee_contributions": fund_data.get("employee_contributions", 0),
            "annual_return_rate": fund_data.get("annual_return_rate", 0),
            "calculation_mode": fund_data.get("calculation_mode", "manual"),
            "annuity_factor": fund_data.get("annuity_factor", 0),
            "indexation_method": fund_data.get("indexation_method", "none"),
            "indexation_rate": fund_data.get("indexation_rate", 0)
        }
        
        pension_funds_db[new_id] = new_fund
        return new_fund
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create pension fund: {str(e)}")

@app.delete("/api/v1/pension-funds/{fund_id}")
def delete_pension_fund(fund_id: int):
    if fund_id not in pension_funds_db:
        raise HTTPException(status_code=404, detail="Pension fund not found")
    
    deleted_fund = pension_funds_db.pop(fund_id)
    return {"message": f"Pension fund {fund_id} deleted successfully", "deleted_fund": deleted_fund}

# Additional income and capital assets endpoints
@app.get("/api/v1/clients/{client_id}/additional-incomes/")
def get_additional_incomes(client_id: int):
    client_incomes = [income for income in additional_incomes_db.values() if income.get("client_id") == client_id]
    return client_incomes

@app.get("/api/v1/clients/{client_id}/capital-assets/")
def get_capital_assets(client_id: int):
    client_assets = [asset for asset in capital_assets_db.values() if asset.get("client_id") == client_id]
    return client_assets

# Cashflow integration endpoints
@app.post("/api/v1/clients/{client_id}/cashflow/integrate-all")
def integrate_all(client_id: int, cashflow_data: List = None):
    try:
        # Get pension funds
        pension_funds = [fund for fund in pension_funds_db.values() if fund.get("client_id") == client_id]
        
        # Get additional incomes
        additional_incomes = [income for income in additional_incomes_db.values() if income.get("client_id") == client_id]
        
        # Get capital assets
        capital_assets = [asset for asset in capital_assets_db.values() if asset.get("client_id") == client_id]
        
        all_cashflow = []
        
        # Add pension funds to cashflow
        for fund in pension_funds:
            monthly_amount = fund.get("monthly_amount", 0) or fund.get("computed_monthly_amount", 0)
            if monthly_amount > 0:
                for month in range(1, 25):  # 24 months
                    date_str = f"2025-{((month-1) % 12) + 1:02d}-10"
                    all_cashflow.append({
                        "date": date_str,
                        "amount": round(monthly_amount),
                        "source": "קצבת פנסיה"
                    })
        
        # Add additional incomes to cashflow
        for income in additional_incomes:
            amount = income.get("amount", 0)
            frequency = income.get("frequency", "monthly")
            
            if frequency == "monthly" and amount > 0:
                for month in range(1, 25):  # 24 months
                    date_str = f"2025-{((month-1) % 12) + 1:02d}-15"
                    all_cashflow.append({
                        "date": date_str,
                        "amount": round(amount),
                        "source": "הכנסה מעסק"
                    })
        
        # Add capital assets to cashflow
        for asset in capital_assets:
            current_value = asset.get("current_value", 0)
            annual_return_rate = asset.get("annual_return_rate", 0) or asset.get("annual_return", 0)
            
            if annual_return_rate > 1:
                annual_return_rate = annual_return_rate / 100
            
            if current_value > 0 and annual_return_rate > 0:
                quarterly_amount = (current_value * annual_return_rate) / 4
                
                for quarter in [1, 4, 7, 10]:  # Quarterly payments
                    date_str = f"2025-{quarter:02d}-01"
                    all_cashflow.append({
                        "date": date_str,
                        "amount": round(quarterly_amount),
                        "source": "הכנסה מנדל\"ן"
                    })
        
        # Sort by date
        all_cashflow.sort(key=lambda x: x["date"])
        
        return all_cashflow
        
    except Exception as e:
        logger.error(f"Error integrating all sources: {e}")
        return []

if __name__ == "__main__":
    import uvicorn
    print("Starting clean server with rights fixation on port 8005...")
    print(f"Rights fixation service available: {RIGHTS_FIXATION_AVAILABLE}")
    uvicorn.run(app, host="0.0.0.0", port=8005)
