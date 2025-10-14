"""
Current Employer API router - Sprint 3
Endpoints for managing current employer and grants
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import date, datetime
from app.database import get_db
from app.models.client import Client
from app.models.current_employer import CurrentEmployer
from app.services.current_employer_service import CurrentEmployerService
from app.schemas.current_employer import (
    CurrentEmployerCreate, CurrentEmployerUpdate, CurrentEmployerOut,
    EmployerGrantCreate, GrantWithCalculation,
    TerminationDecisionCreate, TerminationDecisionOut
)
from app.models.grant import Grant
from app.models.pension import Pension
from app.models.capital_asset import CapitalAsset

router = APIRouter()

@router.post(
    "/clients/{client_id}/current-employer",
    response_model=CurrentEmployerOut,
    status_code=status.HTTP_201_CREATED
)
def create_or_update_current_employer(
    client_id: int,
    employer_data: CurrentEmployerCreate,
    db: Session = Depends(get_db)
):
    """
    Create or update current employer for a client
    Returns 201 for new creation, 200 for update
    """
    # Check if client exists
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(
            status_code=404, 
            detail={"error": "לקוח לא נמצא"}
        )
    
    # Check if current employer already exists using direct query - get latest
    ce = db.scalar(
        select(CurrentEmployer)
        .where(CurrentEmployer.client_id == client_id)
        .order_by(CurrentEmployer.updated_at.desc(), CurrentEmployer.id.desc())
    )
    
    if ce:
        # Update existing employer
        data = employer_data.model_dump(exclude_none=True)  # Important! Don't overwrite with None
        
        # Map monthly_salary to last_salary if monthly_salary is provided
        if 'monthly_salary' in data and data['monthly_salary'] is not None:
            data['last_salary'] = data['monthly_salary']
            
        # Map severance_balance to severance_accrued if provided
        if 'severance_balance' in data and data['severance_balance'] is not None:
            data['severance_accrued'] = data['severance_balance']
        
        # Remove fields that don't exist in the current DB schema
        data.pop('monthly_salary', None)
        data.pop('severance_balance', None)
        
        for k, v in data.items():
            setattr(ce, k, v)
        ce.last_update = date.today()  # Always update by server
        
        db.add(ce)
        db.commit()
        db.refresh(ce)
        return ce
    else:
        # Create new employer
        try:
            # Could try to derive data from Employment "current" here if needed
            
            # Create new from payload - map frontend fields to DB fields
            data = employer_data.model_dump(exclude_none=True)
            
            # Map monthly_salary to last_salary if monthly_salary is provided
            if 'monthly_salary' in data and data['monthly_salary'] is not None:
                data['last_salary'] = data['monthly_salary']
                
            # Map severance_balance to severance_accrued if provided
            if 'severance_balance' in data and data['severance_balance'] is not None:
                data['severance_accrued'] = data['severance_balance']
            
            # Remove fields that don't exist in the current DB schema
            data.pop('monthly_salary', None)
            data.pop('severance_balance', None)
            
            ce = CurrentEmployer(
                client_id=client_id,
                **data
            )
            ce.last_update = date.today()
            
            db.add(ce)
            db.commit()
            db.refresh(ce)
            return ce
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail={"error": str(e)}
            )

@router.get(
    "/clients/{client_id}/current-employer",
    response_model=CurrentEmployerOut
)
def get_current_employer(
    client_id: int,
    db: Session = Depends(get_db)
):
    """
    Get current employer for a client
    Returns 404 if client not found or no current employer exists
    """
    # 1) בדיקת קיום לקוח
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail={"error": "לקוח לא נמצא"})

    # 2) שליפת המעסיק הנוכחי (האחרון)
    ce = db.scalar(
        select(CurrentEmployer)
        .where(CurrentEmployer.client_id == client_id)
        .order_by(CurrentEmployer.updated_at.desc(), CurrentEmployer.id.desc())
    )
    if ce is None:
        raise HTTPException(status_code=404, detail={"error": "אין מעסיק נוכחי רשום ללקוח"})

    return CurrentEmployerOut.model_validate(ce)  # Pydantic v2

@router.post(
    "/clients/{client_id}/current-employer/grants",
    response_model=GrantWithCalculation,
    status_code=status.HTTP_201_CREATED
)
def add_grant_to_current_employer(
    client_id: int,
    grant_data: EmployerGrantCreate,
    db: Session = Depends(get_db)
):
    """
    Add a grant to current employer and return calculation results
    Includes grant_exempt, grant_taxable, tax_due in response
    """
    # Check if client exists
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(
            status_code=404,
            detail={"error": "לקוח לא נמצא"}
        )
    
    # Get current employer using direct query - get latest
    ce = db.scalar(
        select(CurrentEmployer)
        .where(CurrentEmployer.client_id == client_id)
        .order_by(CurrentEmployer.updated_at.desc(), CurrentEmployer.id.desc())
    )
    if not ce:
        raise HTTPException(
            status_code=404,
            detail={"error": "אין מעסיק נוכחי רשום ללקוח"}
        )
    
    try:
        # Add grant and calculate results
        grant, calculation = CurrentEmployerService.add_grant_to_employer(
            db, ce.id, grant_data
        )
        
        # Return grant with calculation results
        return GrantWithCalculation(
            **grant.to_dict(),
            calculation=calculation
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": str(e)}
        )

@router.post(
    "/clients/{client_id}/current-employer/termination",
    response_model=TerminationDecisionOut,
    status_code=status.HTTP_201_CREATED
)
def process_termination_decision(
    client_id: int,
    decision: TerminationDecisionCreate,
    db: Session = Depends(get_db)
):
    """
    Process employee termination decision and create appropriate entities:
    - Grant for exempt redemption with exemption usage
    - Pension for annuity choice
    - Capital Asset for tax spread choice
    
    Returns IDs of created entities
    """
    # Check if client exists
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(
            status_code=404,
            detail={"error": "לקוח לא נמצא"}
        )
    
    # Get current employer
    ce = db.scalar(
        select(CurrentEmployer)
        .where(CurrentEmployer.client_id == client_id)
        .order_by(CurrentEmployer.updated_at.desc(), CurrentEmployer.id.desc())
    )
    if not ce:
        raise HTTPException(
            status_code=404,
            detail={"error": "אין מעסיק נוכחי רשום ללקוח"}
        )
    
    try:
        import json
        print(f"🔵 TERMINATION DECISION RECEIVED: {json.dumps(decision.model_dump(), indent=2, default=str)}")
        
        result = {
            "created_grant_id": None,
            "created_pension_id": None,
            "created_capital_asset_id": None
        }
        
        # Update current employer end_date
        ce.end_date = decision.termination_date
        
        # Process exempt amount decision
        if decision.exempt_amount > 0:
            if decision.exempt_choice == 'redeem_with_exemption':
                # Create Grant for exempt amount
                grant = Grant(
                    client_id=client_id,
                    grant_name=f"מענק פיצויים פטור ({ce.employer_name})",
                    grant_type="severance_pay",
                    grant_amount=decision.exempt_amount,
                    grant_date=decision.termination_date,
                    payment_frequency="one_time",
                    indexation_method="none",
                    tax_treatment="exempt"
                )
                db.add(grant)
                db.flush()
                result["created_grant_id"] = grant.id
            
            elif decision.exempt_choice == 'redeem_no_exemption':
                # Create Capital Asset for exempt amount WITH TAX SPREAD
                spread_years = decision.max_spread_years or 1
                
                print(f"🟢 CREATING EXEMPT CAPITAL ASSET WITH TAX_SPREAD:")
                print(f"  - spread_years: {spread_years}")
                
                capital_asset = CapitalAsset(
                    client_id=client_id,
                    asset_name=f"מענק פיצויים פטור ({ce.employer_name})",
                    asset_type="other",
                    current_value=decision.exempt_amount,
                    monthly_income=decision.exempt_amount,
                    annual_return_rate=0.0,
                    payment_frequency="annually",
                    start_date=decision.termination_date,
                    indexation_method="none",
                    tax_treatment="tax_spread",
                    spread_years=spread_years,
                    remarks=f"מענק פיצויים פטור ממס עם פריסת מס ל-{spread_years} שנים"
                )
                db.add(capital_asset)
                db.flush()
                
                print(f"🟢 CREATED EXEMPT ASSET WITH ID: {capital_asset.id}, tax_treatment: {capital_asset.tax_treatment}")
                
                result["created_capital_asset_id"] = capital_asset.id
            
            elif decision.exempt_choice == 'annuity':
                # Create Pension from exempt amount
                # Calculate start date based on retirement age
                if client.birth_date:
                    age = (datetime.now().date() - client.birth_date).days // 365
                    retirement_age = 67 if client.gender == 'male' else 64
                    # For now, use termination date as start - will be adjusted in calculation
                else:
                    retirement_age = 67
                
                pension = Pension(
                    client_id=client_id,
                    payer_name=f"קצבה ממענק פיצויים ({ce.employer_name})",
                    start_date=decision.termination_date
                )
                db.add(pension)
                db.flush()
                result["created_pension_id"] = pension.id
        
        # Process taxable amount decision  
        if decision.taxable_amount > 0:
            print(f"🔵 PROCESSING TAXABLE AMOUNT: {decision.taxable_amount}")
            print(f"🔵 taxable_choice = '{decision.taxable_choice}'")
            
            if decision.taxable_choice == 'redeem_no_exemption':
                # Create Capital Asset for taxable redemption WITH TAX SPREAD
                spread_years = decision.max_spread_years or 1
                
                print(f"🟢 CREATING TAXABLE CAPITAL ASSET WITH TAX_SPREAD:")
                print(f"  - max_spread_years: {decision.max_spread_years}")
                print(f"  - spread_years: {spread_years}")
                
                capital_asset = CapitalAsset(
                    client_id=client_id,
                    asset_name=f"מענק פיצויים חייב במס ({ce.employer_name})",
                    asset_type="other",
                    current_value=decision.taxable_amount,
                    monthly_income=decision.taxable_amount,
                    annual_return_rate=0.0,
                    payment_frequency="annually",
                    start_date=decision.termination_date,
                    indexation_method="none",
                    tax_treatment="tax_spread",  # ← Changed from "taxable" to "tax_spread"
                    spread_years=spread_years,
                    remarks=f"מענק פיצויים חייב במס עם פריסת מס ל-{spread_years} שנים"
                )
                db.add(capital_asset)
                db.flush()
                
                print(f"🟢 CREATED TAXABLE ASSET WITH ID: {capital_asset.id}, tax_treatment: {capital_asset.tax_treatment}")
                
                if not result.get("created_capital_asset_id"):
                    result["created_capital_asset_id"] = capital_asset.id
            
            elif decision.taxable_choice == 'annuity':
                # Create Pension from taxable amount
                pension = Pension(
                    client_id=client_id,
                    payer_name=f"קצבה ממענק פיצויים ({ce.employer_name})",
                    start_date=decision.termination_date
                )
                db.add(pension)
                db.flush()
                result["created_pension_id"] = pension.id
        
        db.commit()
        
        print(f"✅ TRANSACTION COMMITTED")
        print(f"✅ RESULT: {result}")
        
        # Return result with created IDs
        return TerminationDecisionOut(
            **decision.model_dump(),
            **result
        )
        
    except ValueError as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail={"error": str(e)}
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail={"error": f"שגיאה בעיבוד החלטות עזיבה: {str(e)}"}
        )
