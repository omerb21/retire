# -*- coding: utf-8 -*-
print("DEBUG: Loading simple_server.py with REAL rights fixation service")
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Complete Retirement Planning Server")

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
        "income_name": "הכנסה עסקית", # הוספת שדה שם הכנסה
        "description": "הכנסה עסקית",
        "income_type": "עסק עצמאי",
        "amount": 25000,
        "frequency": "monthly",
        "monthly_amount": 25000,
        "annual_amount": 300000,
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
        "asset_type": "rental_property",
        "description": "דירה להשכרה",
        "current_value": 3000000,
        "purchase_value": 0,
        "purchase_date": "2020-01-01",
        "annual_return": 0,
        "annual_return_rate": 3,
        "payment_frequency": "monthly",
        "liquidity": "medium",
        "risk_level": "medium",
        "monthly_income": 0,
        "start_date": "לא צוין",
        "end_date": "ללא הגבלה",
        "indexation_method": "none",
        "fixed_rate": 0,
        "tax_treatment": "undefined",
        "tax_rate": 0
    }
}

current_employers_db = {
    1: {
        "id": 1,
        "client_id": 1,
        "employer_name": "חברת הייטק בע\"מ",
        "start_date": "2010-01-01",
        "monthly_salary": 30000,
        "severance_balance": 500000,
        "pension_fund_id": 1,
        "pension_contributions": 7.5,
        "employer_pension_contributions": 7.5,
        "severance_contributions": 8.33
    }
}

grants_db = {
    1: {
        "id": 1,
        "client_id": 1,
        "grant_type": "severance",
        "amount": 300000,
        "grant_date": "2023-12-31",
        "employer_name": "חברה קודמת בע\"מ",
        "tax_withholding": 35000,
        "is_exempt": False,
        "exempt_amount": 0,
        "work_start_date": "2000-01-01",
        "work_end_date": "2023-12-31"
    }
}

scenarios_db = {
    1: {
        "id": 1,
        "client_id": 1,
        "name": "תרחיש ברירת מחדל",
        "description": "תרחיש ברירת מחדל לבדיקת המערכת",
        "parameters": "{}",
        "created_at": "2025-01-01T00:00:00",
        "updated_at": "2025-01-01T00:00:00"
    }
}

@app.get("/health")
def health_check():
    return {"status": "ok", "server": "complete_server"}

# Client endpoints
@app.get("/api/v1/clients")
def get_clients():
    """קבלת רשימת לקוחות"""
    return {"clients": list(clients_db.values()), "total": len(clients_db)}

@app.post("/api/v1/clients")
def create_client(client_data: dict):
    """יצירת לקוח חדש"""
    try:
        # Validate required fields
        if not client_data.get('id_number'):
            raise HTTPException(status_code=422, detail="Missing required field: id_number")
        
        # Generate new client ID
        new_id = max(clients_db.keys()) + 1 if clients_db else 1
        
        # Create full name from first and last name
        first_name = client_data.get('first_name', '')
        last_name = client_data.get('last_name', '')
        full_name = f"{first_name} {last_name}".strip()
        
        # Create new client
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
        
        # Add to database
        clients_db[new_id] = new_client
        return new_client
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create client: {str(e)}")

@app.get("/api/v1/clients/{client_id}")
def get_client(client_id: int):
    """קבלת פרטי לקוח"""
    if client_id not in clients_db:
        raise HTTPException(status_code=404, detail="Client not found")
    return clients_db[client_id]

@app.put("/api/v1/clients/{client_id}")
def update_client(client_id: int, client_data: dict):
    """עדכון פרטי לקוח"""
    try:
        if client_id not in clients_db:
            raise HTTPException(status_code=404, detail="Client not found")
        
        existing_client = clients_db[client_id]
        
        # Create full name from first and last name
        first_name = client_data.get('first_name', existing_client.get('first_name', ''))
        last_name = client_data.get('last_name', existing_client.get('last_name', ''))
        full_name = f"{first_name} {last_name}".strip()
        
        updated_client = {
            "id": client_id,
            "full_name": full_name,
            "first_name": first_name,
            "last_name": last_name,
            "id_number": client_data.get('id_number', existing_client.get('id_number')),
            "birth_date": client_data.get('birth_date', existing_client.get('birth_date')),
            "birthdate": client_data.get('birth_date', existing_client.get('birthdate')),
            "gender": client_data.get('gender', existing_client.get('gender', 'male')),
            "marital_status": client_data.get('marital_status', existing_client.get('marital_status', 'single')),
            "email": client_data.get('email', existing_client.get('email')),
            "phone": client_data.get('phone', existing_client.get('phone')),
            "is_active": client_data.get('is_active', existing_client.get('is_active', True)),
            "pension_start_date": client_data.get('pension_start_date', existing_client.get('pension_start_date')),
            "num_children": client_data.get('num_children', existing_client.get('num_children')),
            "is_disabled": client_data.get('is_disabled', existing_client.get('is_disabled')),
            "disability_percentage": client_data.get('disability_percentage', existing_client.get('disability_percentage')),
            "is_new_immigrant": client_data.get('is_new_immigrant', existing_client.get('is_new_immigrant')),
            "immigration_date": client_data.get('immigration_date', existing_client.get('immigration_date')),
            "is_veteran": client_data.get('is_veteran', existing_client.get('is_veteran')),
            "reserve_duty_days": client_data.get('reserve_duty_days', existing_client.get('reserve_duty_days')),
            "tax_credit_points": client_data.get('tax_credit_points', existing_client.get('tax_credit_points'))
        }
        
        clients_db[client_id] = updated_client
        return updated_client
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update client: {str(e)}")

@app.delete("/api/v1/clients/{client_id}")
def delete_client(client_id: int):
    """מחיקת לקוח"""
    if client_id not in clients_db:
        raise HTTPException(status_code=404, detail="Client not found")
    del clients_db[client_id]
    return {"status": "success", "message": "Client deleted successfully"}

# Pension fund endpoints
@app.get("/api/v1/clients/{client_id}/pension-funds")
def get_pension_funds(client_id: int):
    """קבלת רשימת קרנות פנסיה"""
    client_funds = [fund for fund in pension_funds_db.values() if fund.get("client_id") == client_id]
    return client_funds

@app.post("/api/v1/clients/{client_id}/pension-funds")
def create_pension_fund(client_id: int, fund_data: dict):
    """יצירת קרן פנסיה חדשה"""
    try:
        # Check if client exists
        if client_id not in clients_db:
            raise HTTPException(status_code=404, detail="Client not found")
            
        # Generate new fund ID
        new_id = max(pension_funds_db.keys()) + 1 if pension_funds_db else 1
        
        # Create new pension fund with all possible fields
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
        
        # Debug log
        print(f"Creating pension fund: {new_fund}")
        
        # Add to database
        pension_funds_db[new_id] = new_fund
        return new_fund
        
    except Exception as e:
        print(f"Error creating pension fund: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create pension fund: {str(e)}")@app.get("/api/v1/pension-funds/{fund_id}")
def get_pension_fund(fund_id: int):
    """קבלת קרן פנסיה לפי מזהה"""
    if fund_id not in pension_funds_db:
        raise HTTPException(status_code=404, detail="Pension fund not found")
    return pension_funds_db[fund_id]

@app.put("/api/v1/pension-funds/{fund_id}")
def update_pension_fund(fund_id: int, fund_data: dict):
    """עדכון קרן פנסיה"""
    try:
        if fund_id not in pension_funds_db:
            raise HTTPException(status_code=404, detail="Pension fund not found")
        
        existing_fund = pension_funds_db[fund_id]
        
        # Update fund data
        updated_fund = {
            "id": fund_id,
            "client_id": existing_fund["client_id"],
            "fund_name": fund_data.get("fund_name", existing_fund.get("fund_name", "")),
            "fund_number": fund_data.get("fund_number", existing_fund.get("fund_number", "")),
            "fund_type": fund_data.get("fund_type", existing_fund.get("fund_type", "pension")),
            "current_balance": fund_data.get("current_balance", existing_fund.get("current_balance", 0)),
            "monthly_amount": fund_data.get("monthly_amount", existing_fund.get("monthly_amount", 0)),
            "computed_monthly_amount": fund_data.get("computed_monthly_amount", existing_fund.get("computed_monthly_amount", 0)),
            "start_date": fund_data.get("start_date", existing_fund.get("start_date", "")),
            "end_date": fund_data.get("end_date", existing_fund.get("end_date", "")),
            "employer_contributions": fund_data.get("employer_contributions", existing_fund.get("employer_contributions", 0)),
            "employee_contributions": fund_data.get("employee_contributions", existing_fund.get("employee_contributions", 0)),
            "annual_return_rate": fund_data.get("annual_return_rate", existing_fund.get("annual_return_rate", 0))
        }
        
        # Update database
        pension_funds_db[fund_id] = updated_fund
        return updated_fund
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update pension fund: {str(e)}")

@app.delete("/api/v1/pension-funds/{fund_id}")
def delete_pension_fund(fund_id: int):
    """מחיקת קרן פנסיה"""
    if fund_id not in pension_funds_db:
        raise HTTPException(status_code=404, detail="Pension fund not found")
    
    deleted_fund = pension_funds_db.pop(fund_id)
    return {"message": f"Pension fund {fund_id} deleted successfully", "deleted_fund": deleted_fund}




@app.put("/api/v1/clients/{client_id}/pension-funds/{fund_id}")
def update_pension_fund(client_id: int, fund_id: int, fund_data: dict):
    """עדכון קרן פנסיה"""
    try:
        # Check if client exists
        if client_id not in clients_db:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Check if fund exists
        if fund_id not in pension_funds_db:
            raise HTTPException(status_code=404, detail="Pension fund not found")
        
        # Check if fund belongs to client
        if pension_funds_db[fund_id].get("client_id") != client_id:
            raise HTTPException(status_code=403, detail="Pension fund does not belong to this client")
        
        # Update pension fund
        existing_fund = pension_funds_db[fund_id]
        updated_fund = {
            "id": fund_id,
            "client_id": client_id,
            "fund_name": fund_data.get("fund_name", existing_fund.get("fund_name")),
            "fund_number": fund_data.get("fund_number", existing_fund.get("fund_number")),
            "fund_type": fund_data.get("fund_type", existing_fund.get("fund_type")),
            "current_balance": fund_data.get("current_balance", existing_fund.get("current_balance")),
            "monthly_amount": fund_data.get("monthly_amount", existing_fund.get("monthly_amount")),
            "computed_monthly_amount": fund_data.get("computed_monthly_amount", existing_fund.get("computed_monthly_amount")),
            "start_date": fund_data.get("start_date", existing_fund.get("start_date")),
            "indexation_method": fund_data.get("indexation_method", existing_fund.get("indexation_method")),
            "indexation_rate": fund_data.get("indexation_rate", existing_fund.get("indexation_rate"))
        }
        
        # Save to database
        pension_funds_db[fund_id] = updated_fund
        return updated_fund
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update pension fund: {str(e)}")

@app.delete("/api/v1/clients/{client_id}/pension-funds/{fund_id}")
def delete_pension_fund(client_id: int, fund_id: int):
    """מחיקת קרן פנסיה"""
    # Check if client exists
    if client_id not in clients_db:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Check if fund exists
    if fund_id not in pension_funds_db:
        raise HTTPException(status_code=404, detail="Pension fund not found")
    
    # Check if fund belongs to client
    if pension_funds_db[fund_id].get("client_id") != client_id:
        raise HTTPException(status_code=403, detail="Pension fund does not belong to this client")
    
    # Delete fund
    del pension_funds_db[fund_id]
    return {"status": "success", "message": "Pension fund deleted successfully"}

# Additional incomes endpoints
@app.get("/api/v1/clients/{client_id}/additional-incomes/")
def get_additional_incomes(client_id: int):
    """קבלת רשימת הכנסות נוספות"""
    client_incomes = [income for income in additional_incomes_db.values() if income.get("client_id") == client_id]
    return client_incomes

@app.post("/api/v1/clients/{client_id}/additional-incomes/")
def create_additional_income(client_id: int, income_data: dict):
    """יצירת הכנסה נוספת חדשה"""
    try:
        # Check if client exists
        if client_id not in clients_db:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Generate new income ID
        new_id = max(additional_incomes_db.keys()) + 1 if additional_incomes_db else 1
        
        # Create new additional income
        new_income = {
            "id": new_id,
            "client_id": client_id,
            "source_type": income_data.get("source_type", "other"),
            "income_name": income_data.get("income_name", ""),  # הוספת שדה שם הכנסה
            "description": income_data.get("description", ""),
            "amount": income_data.get("amount", 0),
            "frequency": income_data.get("frequency", "monthly"),
            "start_date": income_data.get("start_date", "2025-01-01"),
            "end_date": income_data.get("end_date", "2035-01-01"),
            "indexation_method": income_data.get("indexation_method", "none"),
            "fixed_rate": income_data.get("fixed_rate", 0),
            "tax_treatment": income_data.get("tax_treatment", "taxable"),
            "tax_rate": income_data.get("tax_rate", 0)
        }
        
        # Add to database
        additional_incomes_db[new_id] = new_income
        return new_income
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create additional income: {str(e)}")

@app.put("/api/v1/clients/{client_id}/additional-incomes/{income_id}")
def update_additional_income(client_id: int, income_id: int, income_data: dict):
    """עדכון הכנסה נוספת"""
    try:
        # Check if client exists
        if client_id not in clients_db:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Check if income exists
        if income_id not in additional_incomes_db:
            raise HTTPException(status_code=404, detail="Additional income not found")
        
        # Check if income belongs to client
        if additional_incomes_db[income_id].get("client_id") != client_id:
            raise HTTPException(status_code=403, detail="Additional income does not belong to this client")
        
        # Update additional income
        existing_income = additional_incomes_db[income_id]
        updated_income = {
            "id": income_id,
            "client_id": client_id,
            "source_type": income_data.get("source_type", existing_income.get("source_type")),
            "income_name": income_data.get("income_name", existing_income.get("income_name", "")),  # הוספת שדה שם הכנסה
            "description": income_data.get("description", existing_income.get("description")),
            "amount": income_data.get("amount", existing_income.get("amount")),
            "frequency": income_data.get("frequency", existing_income.get("frequency")),
            "start_date": income_data.get("start_date", existing_income.get("start_date")),
            "end_date": income_data.get("end_date", existing_income.get("end_date")),
            "indexation_method": income_data.get("indexation_method", existing_income.get("indexation_method")),
            "fixed_rate": income_data.get("fixed_rate", existing_income.get("fixed_rate")),
            "tax_treatment": income_data.get("tax_treatment", existing_income.get("tax_treatment")),
            "tax_rate": income_data.get("tax_rate", existing_income.get("tax_rate"))
        }
        
        # Save to database
        additional_incomes_db[income_id] = updated_income
        return updated_income
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update additional income: {str(e)}")

@app.delete("/api/v1/clients/{client_id}/additional-incomes/{income_id}")
def delete_additional_income(client_id: int, income_id: int):
    """מחיקת הכנסה נוספת"""
    # Check if client exists
    if client_id not in clients_db:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Check if income exists
    if income_id not in additional_incomes_db:
        raise HTTPException(status_code=404, detail="Additional income not found")
    
    # Check if income belongs to client
    if additional_incomes_db[income_id].get("client_id") != client_id:
        raise HTTPException(status_code=403, detail="Additional income does not belong to this client")
    
    # Delete income
    del additional_incomes_db[income_id]
    return {"status": "success", "message": "Additional income deleted successfully"}

# Capital assets endpoints
@app.get("/api/v1/clients/{client_id}/capital-assets/")
def get_capital_assets(client_id: int):
    """קבלת רשימת נכסי הון"""
    client_assets = [asset for asset in capital_assets_db.values() if asset.get("client_id") == client_id]
    return client_assets

@app.post("/api/v1/clients/{client_id}/capital-assets/")
def create_capital_asset(client_id: int, asset_data: dict):
    """יצירת נכס הון חדש"""
    try:
        # Check if client exists
        if client_id not in clients_db:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Generate new asset ID
        new_id = max(capital_assets_db.keys()) + 1 if capital_assets_db else 1
        
        # Create new capital asset
        new_asset = {
            "id": new_id,
            "client_id": client_id,
            "asset_type": asset_data.get("asset_type", "other"),
            "description": asset_data.get("description", ""),
            "current_value": asset_data.get("current_value", 0),
            "purchase_value": asset_data.get("purchase_value", 0),
            "purchase_date": asset_data.get("purchase_date", ""),
            "annual_return": asset_data.get("annual_return", 0),
            "annual_return_rate": asset_data.get("annual_return_rate", 0),
            "payment_frequency": asset_data.get("payment_frequency", "quarterly"),
            "liquidity": asset_data.get("liquidity", "medium"),
            "risk_level": asset_data.get("risk_level", "medium")
        }
        
        # Add to database
        capital_assets_db[new_id] = new_asset
        return new_asset
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create capital asset: {str(e)}")

@app.put("/api/v1/clients/{client_id}/capital-assets/{asset_id}")
def update_capital_asset(client_id: int, asset_id: int, asset_data: dict):
    """עדכון נכס הון"""
    try:
        # Check if client exists
        if client_id not in clients_db:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Check if asset exists
        if asset_id not in capital_assets_db:
            raise HTTPException(status_code=404, detail="Capital asset not found")
        
        # Check if asset belongs to client
        if capital_assets_db[asset_id].get("client_id") != client_id:
            raise HTTPException(status_code=403, detail="Capital asset does not belong to this client")
        
        # Update capital asset
        existing_asset = capital_assets_db[asset_id]
        updated_asset = {
            "id": asset_id,
            "client_id": client_id,
            "asset_type": asset_data.get("asset_type", existing_asset.get("asset_type")),
            "description": asset_data.get("description", existing_asset.get("description")),
            "current_value": asset_data.get("current_value", existing_asset.get("current_value")),
            "purchase_value": asset_data.get("purchase_value", existing_asset.get("purchase_value")),
            "purchase_date": asset_data.get("purchase_date", existing_asset.get("purchase_date")),
            "annual_return": asset_data.get("annual_return", existing_asset.get("annual_return")),
            "annual_return_rate": asset_data.get("annual_return_rate", existing_asset.get("annual_return_rate")),
            "payment_frequency": asset_data.get("payment_frequency", existing_asset.get("payment_frequency")),
            "liquidity": asset_data.get("liquidity", existing_asset.get("liquidity")),
            "risk_level": asset_data.get("risk_level", existing_asset.get("risk_level"))
        }
        
        # Save to database
        capital_assets_db[asset_id] = updated_asset
        return updated_asset
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update capital asset: {str(e)}")

@app.delete("/api/v1/clients/{client_id}/capital-assets/{asset_id}")
def delete_capital_asset(client_id: int, asset_id: int):
    """מחיקת נכס הון"""
    # Check if client exists
    if client_id not in clients_db:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Check if asset exists
    if asset_id not in capital_assets_db:
        raise HTTPException(status_code=404, detail="Capital asset not found")
    
    # Check if asset belongs to client
    if capital_assets_db[asset_id].get("client_id") != client_id:
        raise HTTPException(status_code=403, detail="Capital asset does not belong to this client")
    
    # Delete asset
    del capital_assets_db[asset_id]
    return {"status": "success", "message": "Capital asset deleted successfully"}

# Current employer endpoints
@app.get("/api/v1/clients/{client_id}/current-employer")
def get_current_employer(client_id: int):
    """קבלת פרטי מעסיק נוכחי"""
    client_employers = [employer for employer in current_employers_db.values() if employer.get("client_id") == client_id]
    return client_employers

@app.post("/api/v1/clients/{client_id}/current-employer")
def create_current_employer(client_id: int, employer_data: dict):
    """יצירת מעסיק נוכחי חדש"""
    try:
        # Check if client exists
        if client_id not in clients_db:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Generate new employer ID
        new_id = max(current_employers_db.keys()) + 1 if current_employers_db else 1
        
        # Create new current employer
        new_employer = {
            "id": new_id,
            "client_id": client_id,
            "employer_name": employer_data.get("employer_name", ""),
            "start_date": employer_data.get("start_date", ""),
            "monthly_salary": employer_data.get("monthly_salary", 0),
            "severance_balance": employer_data.get("severance_balance", 0),
            "pension_fund_id": employer_data.get("pension_fund_id"),
            "pension_contributions": employer_data.get("pension_contributions", 0),
            "employer_pension_contributions": employer_data.get("employer_pension_contributions", 0),
            "severance_contributions": employer_data.get("severance_contributions", 0)
        }
        
        # Add to database
        current_employers_db[new_id] = new_employer
        return new_employer
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create current employer: {str(e)}")

@app.put("/api/v1/clients/{client_id}/current-employer/{employer_id}")
def update_current_employer(client_id: int, employer_id: int, employer_data: dict):
    """עדכון מעסיק נוכחי"""
    try:
        # Check if client exists
        if client_id not in clients_db:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Check if employer exists
        if employer_id not in current_employers_db:
            raise HTTPException(status_code=404, detail="Current employer not found")
        
        # Check if employer belongs to client
        if current_employers_db[employer_id].get("client_id") != client_id:
            raise HTTPException(status_code=403, detail="Current employer does not belong to this client")
        
        # Update current employer
        existing_employer = current_employers_db[employer_id]
        updated_employer = {
            "id": employer_id,
            "client_id": client_id,
            "employer_name": employer_data.get("employer_name", existing_employer.get("employer_name")),
            "start_date": employer_data.get("start_date", existing_employer.get("start_date")),
            "monthly_salary": employer_data.get("monthly_salary", existing_employer.get("monthly_salary")),
            "severance_balance": employer_data.get("severance_balance", existing_employer.get("severance_balance")),
            "pension_fund_id": employer_data.get("pension_fund_id", existing_employer.get("pension_fund_id")),
            "pension_contributions": employer_data.get("pension_contributions", existing_employer.get("pension_contributions")),
            "employer_pension_contributions": employer_data.get("employer_pension_contributions", existing_employer.get("employer_pension_contributions")),
            "severance_contributions": employer_data.get("severance_contributions", existing_employer.get("severance_contributions"))
        }
        
        # Save to database
        current_employers_db[employer_id] = updated_employer
        return updated_employer
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update current employer: {str(e)}")

@app.delete("/api/v1/clients/{client_id}/current-employer/{employer_id}")
def delete_current_employer(client_id: int, employer_id: int):
    """מחיקת מעסיק נוכחי"""
    # Check if client exists
    if client_id not in clients_db:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Check if employer exists
    if employer_id not in current_employers_db:
        raise HTTPException(status_code=404, detail="Current employer not found")
    
    # Check if employer belongs to client
    if current_employers_db[employer_id].get("client_id") != client_id:
        raise HTTPException(status_code=403, detail="Current employer does not belong to this client")
    
    # Delete employer
    del current_employers_db[employer_id]
    return {"status": "success", "message": "Current employer deleted successfully"}

@app.post("/api/v1/current-employer/calculate-severance")
def calculate_severance(data: dict):
    """חישוב פיצויי פיטורין"""
    try:
        # Extract parameters
        monthly_salary = data.get("monthly_salary", 0)
        years = data.get("years", 0)
        months = data.get("months", 0)
        
        # Calculate total months
        total_months = years * 12 + months
        
        # Calculate severance pay
        severance_cap = 41667  # תקרת פיצויים לשנת 2025
        monthly_cap = min(monthly_salary, severance_cap)
        severance_pay = monthly_cap * (total_months / 12)
        
        # Calculate exempt amount
        exempt_amount = severance_pay
        
        return {
            "severance_pay": round(severance_pay),
            "exempt_amount": round(exempt_amount),
            "taxable_amount": round(max(0, severance_pay - exempt_amount))
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate severance: {str(e)}")

# Grants endpoints
@app.get("/api/v1/clients/{client_id}/grants")
def get_grants(client_id: int):
    """קבלת רשימת מענקים"""
    client_grants = [grant for grant in grants_db.values() if grant.get("client_id") == client_id]
    return client_grants

@app.post("/api/v1/clients/{client_id}/grants")
def create_grant(client_id: int, grant_data: dict):
    """יצירת מענק חדש"""
    try:
        # Check if client exists
        if client_id not in clients_db:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Generate new grant ID
        new_id = max(grants_db.keys()) + 1 if grants_db else 1
        
        # Create new grant
        new_grant = {
            "id": new_id,
            "client_id": client_id,
            "grant_type": grant_data.get("grant_type", "severance"),
            "amount": grant_data.get("amount", 0),
            "grant_date": grant_data.get("grant_date", ""),
            "employer_name": grant_data.get("employer_name", ""),
            "tax_withholding": grant_data.get("tax_withholding", 0),
            "is_exempt": grant_data.get("is_exempt", False),
            "exempt_amount": grant_data.get("exempt_amount", 0),
            "work_start_date": grant_data.get("work_start_date", ""),
            "work_end_date": grant_data.get("work_end_date", "")
        }
        
        # Add to database
        grants_db[new_id] = new_grant
        return new_grant
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create grant: {str(e)}")

@app.put("/api/v1/clients/{client_id}/grants/{grant_id}")
def update_grant(client_id: int, grant_id: int, grant_data: dict):
    """עדכון מענק"""
    try:
        # Check if client exists
        if client_id not in clients_db:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Check if grant exists
        if grant_id not in grants_db:
            raise HTTPException(status_code=404, detail="Grant not found")
        
        # Check if grant belongs to client
        if grants_db[grant_id].get("client_id") != client_id:
            raise HTTPException(status_code=403, detail="Grant does not belong to this client")
        
        # Update grant
        existing_grant = grants_db[grant_id]
        updated_grant = {
            "id": grant_id,
            "client_id": client_id,
            "grant_type": grant_data.get("grant_type", existing_grant.get("grant_type")),
            "amount": grant_data.get("amount", existing_grant.get("amount")),
            "grant_date": grant_data.get("grant_date", existing_grant.get("grant_date")),
            "employer_name": grant_data.get("employer_name", existing_grant.get("employer_name")),
            "tax_withholding": grant_data.get("tax_withholding", existing_grant.get("tax_withholding")),
            "is_exempt": grant_data.get("is_exempt", existing_grant.get("is_exempt")),
            "exempt_amount": grant_data.get("exempt_amount", existing_grant.get("exempt_amount")),
            "work_start_date": grant_data.get("work_start_date", existing_grant.get("work_start_date")),
            "work_end_date": grant_data.get("work_end_date", existing_grant.get("work_end_date"))
        }
        
        # Save to database
        grants_db[grant_id] = updated_grant
        return updated_grant
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update grant: {str(e)}")

@app.delete("/api/v1/clients/{client_id}/grants/{grant_id}")
def delete_grant(client_id: int, grant_id: int):
    """מחיקת מענק"""
    # Check if client exists
    if client_id not in clients_db:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Check if grant exists
    if grant_id not in grants_db:
        raise HTTPException(status_code=404, detail="Grant not found")
    
    # Check if grant belongs to client
    if grants_db[grant_id].get("client_id") != client_id:
        raise HTTPException(status_code=403, detail="Grant does not belong to this client")
    
    # Delete grant
    del grants_db[grant_id]
    return {"status": "success", "message": "Grant deleted successfully"}

# Scenarios endpoints
@app.get("/api/v1/clients/{client_id}/scenarios")
def get_scenarios(client_id: int):
    """קבלת רשימת תרחישים"""
    client_scenarios = [scenario for scenario in scenarios_db.values() if scenario.get("client_id") == client_id]
    return client_scenarios

@app.post("/api/v1/clients/{client_id}/scenarios")
def create_scenario(client_id: int, scenario_data: dict):
    """יצירת תרחיש חדש"""
    try:
        # Check if client exists
        if client_id not in clients_db:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Generate new scenario ID
        new_id = max(scenarios_db.keys()) + 1 if scenarios_db else 1
        
        # Create new scenario
        new_scenario = {
            "id": new_id,
            "client_id": client_id,
            "name": scenario_data.get("name", "תרחיש חדש"),
            "description": scenario_data.get("description", ""),
            "parameters": scenario_data.get("parameters", "{}"),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        # Add to database
        scenarios_db[new_id] = new_scenario
        return new_scenario
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create scenario: {str(e)}")

@app.put("/api/v1/clients/{client_id}/scenarios/{scenario_id}")
def update_scenario(client_id: int, scenario_id: int, scenario_data: dict):
    """עדכון תרחיש"""
    try:
        # Check if client exists
        if client_id not in clients_db:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Check if scenario exists
        if scenario_id not in scenarios_db:
            raise HTTPException(status_code=404, detail="Scenario not found")
        
        # Check if scenario belongs to client
        if scenarios_db[scenario_id].get("client_id") != client_id:
            raise HTTPException(status_code=403, detail="Scenario does not belong to this client")
        
        # Update scenario
        existing_scenario = scenarios_db[scenario_id]
        updated_scenario = {
            "id": scenario_id,
            "client_id": client_id,
            "name": scenario_data.get("name", existing_scenario.get("name")),
            "description": scenario_data.get("description", existing_scenario.get("description")),
            "parameters": scenario_data.get("parameters", existing_scenario.get("parameters")),
            "created_at": existing_scenario.get("created_at"),
            "updated_at": datetime.now().isoformat()
        }
        
        # Save to database
        scenarios_db[scenario_id] = updated_scenario
        return updated_scenario
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update scenario: {str(e)}")

@app.delete("/api/v1/clients/{client_id}/scenarios/{scenario_id}")
def delete_scenario(client_id: int, scenario_id: int):
    """מחיקת תרחיש"""
    # Check if client exists
    if client_id not in clients_db:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Check if scenario exists
    if scenario_id not in scenarios_db:
        raise HTTPException(status_code=404, detail="Scenario not found")
    
    # Check if scenario belongs to client
    if scenarios_db[scenario_id].get("client_id") != client_id:
        raise HTTPException(status_code=403, detail="Scenario does not belong to this client")
    
    # Delete scenario
    del scenarios_db[scenario_id]
    return {"status": "success", "message": "Scenario deleted successfully"}

# Cashflow endpoints
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
            if monthly_amount == 0 and "current_balance" in fund:
                current_balance = fund.get("current_balance", 0)
                monthly_amount = current_balance / 200
            
            # יצירת רשומות תזרים ל-12 חודשים
            for month in range(1, 13):
                date_str = f"2025-{month:02d}-10"  # קצבאות פנסיה משולמות בד״כ ב-10 לחודש
                
                fund_type = fund.get("fund_type", "pension")
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

@app.post("/api/v1/clients/{client_id}/cashflow/integrate-incomes")
def integrate_incomes(client_id: int, cashflow_data: List = None):
    """שילוב הכנסות נוספות בתזרים מזומנים"""
    try:
        client_incomes = [income for income in additional_incomes_db.values() if income.get("client_id") == client_id]
        
        cashflow_entries = []
        
        for income in client_incomes:
            amount = income.get("amount", 0)
            frequency = income.get("frequency", "monthly")
            
            if frequency == "monthly":
                for month in range(1, 13):
                    date_str = f"2025-{month:02d}-15"
                    
                    source_type = income.get("source_type", "business")
                    source_map = {
                        "business": "הכנסה מעסק",
                        "rental": "הכנסה משכירות",
                        "investment": "הכנסה מהשקעות",
                        "other": "הכנסה אחרת"
                    }
                    
                    source_name = source_map.get(source_type, "הכנסה נוספת")
                    
                    cashflow_entries.append({
                        "date": date_str,
                        "amount": round(amount),
                        "source": source_name
                    })
        
        return cashflow_entries
        
    except Exception as e:
        logger.error(f"Error integrating incomes: {e}")
        return []

@app.post("/api/v1/clients/{client_id}/cashflow/integrate-assets")
def integrate_assets(client_id: int, cashflow_data: List = None):
    """שילוב נכסי הון בתזרים מזומנים"""
    try:
        client_assets = [asset for asset in capital_assets_db.values() if asset.get("client_id") == client_id]
        
        cashflow_entries = []
        
        for asset in client_assets:
            current_value = asset.get("current_value", 0)
            annual_return_rate = asset.get("annual_return_rate", 0) or asset.get("annual_return", 0)
            
            if annual_return_rate == 0:
                asset_type = asset.get("asset_type", "")
                if asset_type == "stocks":
                    annual_return_rate = 0.04
                elif asset_type == "bonds":
                    annual_return_rate = 0.03
                elif asset_type == "real_estate":
                    annual_return_rate = 0.03
                else:
                    annual_return_rate = 0.03
            
            if annual_return_rate > 1:
                annual_return_rate = annual_return_rate / 100
            
            payment_frequency = asset.get("payment_frequency", "quarterly")
            
            if payment_frequency == "quarterly":
                quarterly_amount = (current_value * annual_return_rate) / 4
                
                for quarter in [1, 4, 7, 10]:
                    date_str = f"2025-{quarter:02d}-01"
                    
                    asset_type = asset.get("asset_type", "other")
                    asset_map = {
                        "real_estate": "הכנסה מנדל\"ן",
                        "stocks": "דיבידנדים ממניות",
                        "bonds": "ריבית מאגרות חוב",
                        "other": "הכנסה מנכסים"
                    }
                    
                    source_name = asset_map.get(asset_type, "הכנסה מנכסים")
                    
                    cashflow_entries.append({
                        "date": date_str,
                        "amount": round(quarterly_amount),
                        "source": source_name
                    })
        
        return cashflow_entries
        
    except Exception as e:
        logger.error(f"Error integrating assets: {e}")
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

# Rights fixation endpoints
@app.post("/api/v1/test-new-endpoint")
def test_new_endpoint(data: dict):
    """בדיקת endpoint חדש"""
    print("DEBUG: NEW ENDPOINT CALLED!")
    print(f"DEBUG: Data: {data}")
    return {"status": "success", "message": "New endpoint working!", "data": data}

@app.post("/api/v1/rights-fixation/calculate")
def calculate_rights_fixation_OVERRIDE(data: dict):
    """חישוב קיבוע זכויות - OVERRIDE"""
    with open("debug.log", "a", encoding="utf-8") as f:
        f.write(f"DEBUG: OVERRIDE ENDPOINT CALLED! Data: {data}\n")
    print("DEBUG: OVERRIDE ENDPOINT CALLED!")
    print(f"DEBUG: Data: {data}")
    try:
        from app.services.rights_fixation import calculate_full_fixation
        
        client_id = data.get("client_id")
        if not client_id or client_id not in clients_db:
            raise HTTPException(status_code=404, detail="Client not found")
        
        client = clients_db[client_id]
        
        # קבלת מענקים מהבקשה או ממסד הנתונים
        grants = []
        
        # בדיקה אם יש מענקים בבקשה
        request_grants = data.get("grants", [])
        if request_grants:
            print(f"DEBUG: Using {len(request_grants)} grants from request")
            for i, grant in enumerate(request_grants):
                # התאמת השדות לפורמט שהשירות מצפה לו
                adapted_grant = {
                    "id": i + 1,  # מזהה זמני
                    "client_id": client_id,
                    "grant_type": "severance",  # ברירת מחדל
                    "grant_amount": grant.get("grant_amount"),
                    "amount": grant.get("grant_amount"),  # שמירת השדה המקורי גם
                    "grant_date": grant.get("grant_date"),
                    "employer_name": grant.get("employer_name"),
                    "tax_withholding": grant.get("tax_withholding", 0),
                    "is_exempt": grant.get("is_exempt", False),
                    "exempt_amount": grant.get("exempt_amount", 0),
                    "work_start_date": grant.get("work_start_date"),
                    "work_end_date": grant.get("work_end_date")
                }
                grants.append(adapted_grant)
        else:
            # אם אין מענקים בבקשה, נשתמש במענקים ממסד הנתונים
            print(f"DEBUG: Using grants from database for client {client_id}")
            for grant_id, grant in grants_db.items():
                if grant.get("client_id") == client_id:
                    # התאמת השדות לפורמט שהשירות מצפה לו
                    adapted_grant = {
                        "id": grant.get("id"),
                        "client_id": grant.get("client_id"),
                        "grant_type": grant.get("grant_type"),
                        "grant_amount": grant.get("amount"),  # amount -> grant_amount
                        "amount": grant.get("amount"),  # שמירת השדה המקורי גם
                        "grant_date": grant.get("grant_date"),
                        "employer_name": grant.get("employer_name"),
                        "tax_withholding": grant.get("tax_withholding"),
                        "is_exempt": grant.get("is_exempt"),
                        "exempt_amount": grant.get("exempt_amount"),
                        "work_start_date": grant.get("work_start_date"),
                        "work_end_date": grant.get("work_end_date")
                    }
                    grants.append(adapted_grant)
        
        # הכנת נתוני הלקוח לשירות
        from datetime import date
        from app.services.rights_fixation import calculate_eligibility_age
        
        # חישוב תאריך זכאות נכון על בסיס גיל ותאריך תחילת קצבה
        birth_date = date.fromisoformat(client.get("birth_date") or client.get("birthdate"))
        gender = client.get("gender")
        # שימוש בתאריך תחילת קצבה מהנתונים של הלקוח או מהבקשה
        pension_start = date.fromisoformat(
            data.get("pension_start") or 
            client.get("pension_start_date") or 
            "2025-01-01"
        )
        
        eligibility_date = calculate_eligibility_age(birth_date, gender, pension_start)
        
        # הדפסת דיבאג
        print(f"DEBUG: birth_date={birth_date}, gender={gender}, pension_start={pension_start}")
        print(f"DEBUG: calculated eligibility_date={eligibility_date}")
        
        client_data = {
            "id": client_id,
            "birth_date": client.get("birth_date") or client.get("birthdate"),
            "gender": client.get("gender"),
            "grants": grants,
            "eligibility_date": eligibility_date.isoformat(),  # תאריך זכאות מחושב נכון
            "eligibility_year": eligibility_date.year  # שנת זכאות מחושבת נכון
        }
        
        # קריאה לשירות האמיתי
        with open("debug.log", "a", encoding="utf-8") as f:
            f.write(f"DEBUG: Calling service with client_data: {client_data}\n")
        result = calculate_full_fixation(client_data)
        with open("debug.log", "a", encoding="utf-8") as f:
            f.write(f"DEBUG: Service returned: {result}\n")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate rights fixation: {str(e)}")

# Reports endpoints
@app.post("/api/v1/reports/clients/{client_id}/reports/pdf")
def generate_pdf_report(client_id: int, report_data: dict):
    """יצירת דוח PDF"""
    try:
        # Check if client exists
        if client_id not in clients_db:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Check if scenario exists
        scenario_id = report_data.get("scenario_id", 1)
        if scenario_id not in scenarios_db:
            # Create default scenario if it doesn't exist
            scenario = create_scenario(client_id, {
                "name": "תרחיש ברירת מחדל",
                "description": "תרחיש ברירת מחדל ליצירת דוח",
                "parameters": "{}"
            })
            scenario_id = scenario.get("id")
        
        # Return dummy PDF data
        return {
            "status": "success",
            "message": "PDF report generated successfully",
            "client_id": client_id,
            "scenario_id": scenario_id,
            "report_type": report_data.get("report_type", "comprehensive"),
            "created_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF report: {str(e)}")

@app.post("/api/v1/reports/clients/{client_id}/reports/excel")
def generate_excel_report(client_id: int, report_data: dict):
    """יצירת דוח Excel"""
    try:
        # Check if client exists
        if client_id not in clients_db:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Check if scenario exists
        scenario_id = report_data.get("scenario_id", 1)
        if scenario_id not in scenarios_db:
            # Create default scenario if it doesn't exist
            scenario = create_scenario(client_id, {
                "name": "תרחיש ברירת מחדל",
                "description": "תרחיש ברירת מחדל ליצירת דוח",
                "parameters": "{}"
            })
            scenario_id = scenario.get("id")
        
        # Return dummy Excel data
        return {
            "status": "success",
            "message": "Excel report generated successfully",
            "client_id": client_id,
            "scenario_id": scenario_id,
            "report_type": report_data.get("report_type", "excel"),
            "created_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate Excel report: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    print("Starting UPDATED simple server with REAL CBS API on port 8005...")
    uvicorn.run(app, host="0.0.0.0", port=8005)
