"""
Current Employer API router - Sprint 3
Endpoints for managing current employer and grants
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import date, datetime
from decimal import Decimal
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
from app.models.pension_fund import PensionFund
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
        
        # Parse source accounts if provided
        source_account_names = []
        if decision.source_accounts:
            try:
                source_account_names = json.loads(decision.source_accounts)
                print(f"📋 Source accounts: {source_account_names}")
            except:
                pass
        
        # Parse plan details if provided
        plan_details_list = []
        if hasattr(decision, 'plan_details') and decision.plan_details:
            try:
                plan_details_list = json.loads(decision.plan_details)
                print(f"📋 Plan details: {plan_details_list}")
            except Exception as e:
                print(f"⚠️ Failed to parse plan_details: {e}")
        
        # Create source suffix for names
        source_suffix = ""
        if source_account_names:
            if len(source_account_names) == 1:
                source_suffix = f" - נוצר מ: {source_account_names[0]}"
            else:
                source_suffix = f" - נוצר מ: {', '.join(source_account_names[:2])}"
                if len(source_account_names) > 2:
                    source_suffix += f" ועוד {len(source_account_names) - 2}"
        
        # Update current employer end_date
        ce.end_date = decision.termination_date
        # TODO: Save severance_before_termination after running migration
        # if decision.severance_before_termination:
        #     ce.severance_before_termination = decision.severance_before_termination
        #     print(f"💾 Saved severance_before_termination: {decision.severance_before_termination}")
        db.add(ce)  # Mark for update
        db.flush()  # Ensure end_date is saved
        print(f"✅ Updated CurrentEmployer end_date to: {decision.termination_date}")
        
        # Create EmployerGrant for each plan
        from app.models.employer_grant import EmployerGrant, GrantType
        from datetime import datetime
        
        if plan_details_list:
            print(f"🔨 Creating EmployerGrant for each plan...")
            for plan_detail in plan_details_list:
                plan_name = plan_detail.get('plan_name')
                plan_start_date_str = plan_detail.get('plan_start_date')
                product_type = plan_detail.get('product_type', 'קופת גמל')
                amount = plan_detail.get('amount', 0)
                
                if amount > 0:
                    # Parse plan_start_date
                    plan_start_date = None
                    if plan_start_date_str:
                        try:
                            # Try parsing DD/MM/YYYY format
                            plan_start_date = datetime.strptime(plan_start_date_str, '%d/%m/%Y').date()
                        except:
                            try:
                                # Try parsing ISO format
                                plan_start_date = datetime.fromisoformat(plan_start_date_str).date()
                            except:
                                print(f"⚠️ Could not parse plan_start_date: {plan_start_date_str}")
                    
                    employer_grant = EmployerGrant(
                        employer_id=ce.id,
                        grant_type=GrantType.severance,
                        grant_amount=amount,
                        grant_date=decision.termination_date,
                        plan_name=plan_name,
                        plan_start_date=plan_start_date,
                        product_type=product_type
                    )
                    db.add(employer_grant)
                    print(f"  ✅ Created EmployerGrant: {plan_name} ({product_type}) - {amount} ₪ (start: {plan_start_date})")
            
            db.flush()
            print(f"✅ Created {len(plan_details_list)} EmployerGrants")
        else:
            print(f"⚠️ No plan_details provided, creating single EmployerGrant for total amount")
            # Fallback: create single grant for total amount
            total_amount = decision.exempt_amount + decision.taxable_amount
            if total_amount > 0:
                employer_grant = EmployerGrant(
                    employer_id=ce.id,
                    grant_type=GrantType.severance,
                    grant_amount=total_amount,
                    grant_date=decision.termination_date,
                    plan_name="ללא תכנית",
                    plan_start_date=ce.start_date
                )
                db.add(employer_grant)
                db.flush()
                print(f"  ✅ Created single EmployerGrant: {total_amount} ₪")
        
        # Process exempt amount decision
        if decision.exempt_amount > 0:
            print(f"🟡 PROCESSING EXEMPT AMOUNT: {decision.exempt_amount}")
            print(f"🟡 exempt_choice = '{decision.exempt_choice}'")
            
            if decision.exempt_choice == 'redeem_with_exemption':
                # Create Grant for exempt amount
                grant = Grant(
                    client_id=client_id,
                    employer_name=f"מענק פיצויים פטור - {ce.employer_name}{source_suffix}",
                    work_start_date=ce.start_date,
                    work_end_date=decision.termination_date,
                    grant_amount=decision.exempt_amount,
                    grant_date=decision.termination_date,
                    grant_indexed_amount=decision.exempt_amount,
                    limited_indexed_amount=decision.exempt_amount
                )
                db.add(grant)
                db.flush()
                result["created_grant_id"] = grant.id
                
                # Also create Capital Asset for exempt amount (no tax spread - it's exempt!)
                capital_asset = CapitalAsset(
                    client_id=client_id,
                    asset_name=f"מענק פיצויים פטור ({ce.employer_name}){source_suffix}",
                    asset_type="other",
                    current_value=Decimal("0"),  # ✅ תוקן: ערך נוכחי = 0
                    monthly_income=decision.exempt_amount,  # ✅ תוקן: הערך הכספי נכנס לתשלום חודשי
                    annual_return_rate=0.0,
                    payment_frequency="annually",
                    start_date=decision.termination_date,
                    indexation_method="none",
                    tax_treatment="exempt",
                    remarks=f"מענק פיצויים פטור ממס - {decision.exempt_amount:,.0f} ₪"
                )
                db.add(capital_asset)
                db.flush()
                result["created_capital_asset_id"] = capital_asset.id
                
                print(f"🟢 CREATED EXEMPT GRANT ID: {grant.id} + CAPITAL ASSET ID: {capital_asset.id}")
            
            elif decision.exempt_choice == 'redeem_no_exemption':
                # Create Capital Asset for exempt amount WITH TAX SPREAD
                spread_years = decision.max_spread_years or 1
                
                print(f"🟢 CREATING EXEMPT CAPITAL ASSET WITH TAX_SPREAD:")
                print(f"  - spread_years: {spread_years}")
                
                capital_asset = CapitalAsset(
                    client_id=client_id,
                    asset_name=f"מענק פיצויים פטור ({ce.employer_name}){source_suffix}",
                    asset_type="other",
                    current_value=Decimal("0"),  # ✅ תוקן: ערך נוכחי = 0
                    monthly_income=decision.exempt_amount,  # ✅ תוקן: הערך הכספי נכנס לתשלום חודשי
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
                # Create separate PensionFund for each plan (not aggregated)
                print(f"🟡 CREATING SEPARATE PENSION FUNDS FROM EXEMPT AMOUNT: {decision.exempt_amount}")
                
                # Get all EmployerGrants for this termination (created earlier)
                from app.models.employer_grant import EmployerGrant, GrantType
                grants = db.query(EmployerGrant).filter(
                    EmployerGrant.employer_id == ce.id,
                    EmployerGrant.grant_type == GrantType.severance
                ).all()
                
                print(f"  📦 Found {len(grants)} severance grants to process")
                
                # Group grants by plan
                grants_by_plan = {}
                for grant in grants:
                    plan_key = grant.plan_name or "ללא תכנית"
                    if plan_key not in grants_by_plan:
                        grants_by_plan[plan_key] = {
                            'grants': [],
                            'plan_start_date': grant.plan_start_date,
                            'plan_name': grant.plan_name,
                            'product_type': grant.product_type or 'קופת גמל'
                        }
                    grants_by_plan[plan_key]['grants'].append(grant)
                
                # Create separate pension for each plan
                from app.services.annuity_coefficient_service import get_annuity_coefficient
                
                for plan_key, plan_data in grants_by_plan.items():
                    plan_grants = plan_data['grants']
                    plan_start_date = plan_data['plan_start_date']
                    plan_name = plan_data['plan_name'] or "תכנית ללא שם"
                    product_type = plan_data['product_type']
                    
                    # Calculate proportion of exempt amount for this plan
                    total_grant_amount = sum(g.grant_amount for g in grants)
                    plan_grant_amount = sum(g.grant_amount for g in plan_grants)
                    plan_exempt_amount = (plan_grant_amount / total_grant_amount) * decision.exempt_amount if total_grant_amount > 0 else 0
                    
                    print(f"  📊 Processing plan: {plan_name} ({product_type}), exempt_amount: {plan_exempt_amount}, start_date: {plan_start_date}")
                    
                    # Calculate dynamic annuity factor based on plan start date
                    try:
                        coefficient_result = get_annuity_coefficient(
                            product_type=product_type,
                            start_date=plan_start_date if plan_start_date else (ce.start_date if ce.start_date else decision.termination_date),
                            gender=client.gender if client.gender else 'זכר',
                            retirement_age=67,
                            survivors_option='תקנוני',
                            spouse_age_diff=0,
                            birth_date=client.birth_date if client.birth_date else None,
                            pension_start_date=decision.termination_date
                        )
                        annuity_factor = coefficient_result['factor_value']
                        factor_source = coefficient_result['source_table']
                        print(f"    📊 Dynamic annuity coefficient: {annuity_factor} (source: {factor_source})")
                    except Exception as e:
                        print(f"    ⚠️ Failed to calculate dynamic coefficient: {e}, using default 200")
                        annuity_factor = 200
                        factor_source = "default"
                    
                    monthly_amount = plan_exempt_amount / annuity_factor
                    
                    pension_fund = PensionFund(
                        client_id=client_id,
                        fund_name=f"קצבה ממענק פיצויים פטור - {plan_name} ({ce.employer_name})",
                        fund_type="monthly_pension",
                        input_mode="manual",
                        balance=plan_exempt_amount,
                        annuity_factor=annuity_factor,
                        pension_amount=monthly_amount,
                        pension_start_date=decision.termination_date,
                        indexation_method="none",
                        tax_treatment="exempt",
                        remarks=f"מקדם קצבה: {annuity_factor:.2f} (מקור: {factor_source}), תכנית: {plan_name}"
                    )
                    db.add(pension_fund)
                    db.flush()
                    
                    print(f"    🟢 CREATED PENSION FUND ID: {pension_fund.id}, balance: {plan_exempt_amount}, monthly: {monthly_amount}, factor: {annuity_factor}")
                    
                    if not result.get("created_pension_id"):
                        result["created_pension_id"] = pension_fund.id
        
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
                    asset_name=f"מענק פיצויים חייב במס ({ce.employer_name}){source_suffix}",
                    asset_type="other",
                    current_value=Decimal("0"),  # ✅ תוקן: ערך נוכחי = 0
                    monthly_income=decision.taxable_amount,  # ✅ תוקן: הערך הכספי נכנס לתשלום חודשי
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
                # Create separate PensionFund for each plan (not aggregated)
                print(f"🔵 CREATING SEPARATE PENSION FUNDS FROM TAXABLE AMOUNT: {decision.taxable_amount}")
                
                # Get all EmployerGrants for this termination (created earlier)
                from app.models.employer_grant import EmployerGrant, GrantType
                grants = db.query(EmployerGrant).filter(
                    EmployerGrant.employer_id == ce.id,
                    EmployerGrant.grant_type == GrantType.severance
                ).all()
                
                print(f"  📦 Found {len(grants)} severance grants to process")
                
                # Group grants by plan
                grants_by_plan = {}
                for grant in grants:
                    plan_key = grant.plan_name or "ללא תכנית"
                    if plan_key not in grants_by_plan:
                        grants_by_plan[plan_key] = {
                            'grants': [],
                            'plan_start_date': grant.plan_start_date,
                            'plan_name': grant.plan_name,
                            'product_type': grant.product_type or 'קופת גמל'
                        }
                    grants_by_plan[plan_key]['grants'].append(grant)
                
                # Create separate pension for each plan
                from app.services.annuity_coefficient_service import get_annuity_coefficient
                
                for plan_key, plan_data in grants_by_plan.items():
                    plan_grants = plan_data['grants']
                    plan_start_date = plan_data['plan_start_date']
                    plan_name = plan_data['plan_name'] or "תכנית ללא שם"
                    product_type = plan_data['product_type']
                    
                    # Sum amounts for this plan
                    plan_taxable_amount = sum(g.grant_amount for g in plan_grants)
                    
                    print(f"  📊 Processing plan: {plan_name} ({product_type}), amount: {plan_taxable_amount}, start_date: {plan_start_date}")
                    
                    # Calculate dynamic annuity factor based on plan start date
                    try:
                        coefficient_result = get_annuity_coefficient(
                            product_type=product_type,
                            start_date=plan_start_date if plan_start_date else (ce.start_date if ce.start_date else decision.termination_date),
                            gender=client.gender if client.gender else 'זכר',
                            retirement_age=67,
                            survivors_option='תקנוני',
                            spouse_age_diff=0,
                            birth_date=client.birth_date if client.birth_date else None,
                            pension_start_date=decision.termination_date
                        )
                        annuity_factor = coefficient_result['factor_value']
                        factor_source = coefficient_result['source_table']
                        print(f"    📊 Dynamic annuity coefficient: {annuity_factor} (source: {factor_source})")
                    except Exception as e:
                        print(f"    ⚠️ Failed to calculate dynamic coefficient: {e}, using default 200")
                        annuity_factor = 200
                        factor_source = "default"
                    
                    monthly_amount = plan_taxable_amount / annuity_factor
                    
                    pension_fund = PensionFund(
                        client_id=client_id,
                        fund_name=f"קצבה ממענק פיצויים חייב - {plan_name} ({ce.employer_name})",
                        fund_type="monthly_pension",
                        input_mode="manual",
                        balance=plan_taxable_amount,
                        annuity_factor=annuity_factor,
                        pension_amount=monthly_amount,
                        pension_start_date=decision.termination_date,
                        indexation_method="none",
                        tax_treatment="taxable",
                        remarks=f"מקדם קצבה: {annuity_factor:.2f} (מקור: {factor_source}), תכנית: {plan_name}"
                    )
                    db.add(pension_fund)
                    db.flush()
                    
                    print(f"    🟢 CREATED PENSION FUND ID: {pension_fund.id}, balance: {plan_taxable_amount}, monthly: {monthly_amount}, factor: {annuity_factor}")
                    
                    if not result.get("created_pension_id"):
                        result["created_pension_id"] = pension_fund.id
        
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
        print(f"❌ ValueError: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=400,
            detail={"error": f"שגיאה בעיבוד החלטות עזיבה: {str(e)}"}
        )
    except Exception as e:
        db.rollback()
        print(f"❌ EXCEPTION: {e}")
        print(f"❌ Exception type: {type(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail={"error": f"שגיאה בעיבוד החלטות עזיבה: {str(e)}"}
        )

@router.post(
    "/current-employer/calculate-severance",
    status_code=status.HTTP_200_OK
)
def calculate_severance(
    request_data: dict,
    db: Session = Depends(get_db)
):
    """
    Calculate severance payment based on employment details
    """
    try:
        from datetime import datetime
        
        # Extract data from request
        start_date_str = request_data.get('start_date')
        end_date_str = request_data.get('end_date')
        last_salary = request_data.get('last_salary', 0)
        continuity_years = request_data.get('continuity_years', 0)
        
        # Convert dates
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else None
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else date.today()
        
        if not start_date:
            raise ValueError("חסר תאריך התחלת עבודה")
        
        # Calculate service years
        service_years = CurrentEmployerService.calculate_service_years(
            start_date=start_date,
            end_date=end_date,
            continuity_years=continuity_years
        )
        
        # Calculate severance: last_salary * service_years
        severance_amount = last_salary * service_years
        
        # Calculate tax exempt and taxable amounts
        # Exemption cap: 13,750 * service_years
        exemption_cap_per_year = 13750  # התקרה החודשית שהיא למעשה התקרה לחישוב הפטור
        exempt_cap = exemption_cap_per_year * service_years
        exempt_amount = min(severance_amount, exempt_cap)
        
        # Taxable amount is the remainder
        taxable_amount = max(0, severance_amount - exempt_amount)
        
        # For API response - include the cap used
        annual_exemption_cap = exemption_cap_per_year
        
        return {
            "service_years": round(service_years, 2),
            "severance_amount": round(severance_amount, 2),
            "last_salary": last_salary,
            "exempt_amount": round(exempt_amount, 2),
            "taxable_amount": round(taxable_amount, 2),
            "annual_exemption_cap": annual_exemption_cap
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={"error": f"שגיאה בחישוב פיצויים: {str(e)}"}
        )

@router.delete(
    "/clients/{client_id}/delete-termination",
    status_code=status.HTTP_200_OK
)
def delete_termination_decision(
    client_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete all entities created by termination decision:
    - Grants
    - Pension Funds 
    - Capital Assets
    
    Also restores severance balance in pension portfolio (client-side)
    Returns the severance amount that should be restored
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
        deleted_count = 0
        # TODO: Use severance_before_termination after running migration
        # severance_to_restore = ce.severance_before_termination or ce.severance_accrued or 0
        severance_to_restore = ce.severance_accrued or 0
        
        print(f"🔵 DELETE TERMINATION: client_id={client_id}, employer_name={ce.employer_name}")
        print(f"💾 severance_to_restore: {severance_to_restore}")
        
        # אם אין שם מעסיק, לא נוכל למחוק לפי שם
        if not ce.employer_name:
            print(f"⚠️ אין שם מעסיק, מדלג על מחיקת מענקים/נכסים/קצבאות")
        else:
            # Delete all grants related to this employer
            # מענקים שנוצרו מעזיבה מכילים את שם המעסיק
            grants = db.query(Grant).filter(
                Grant.client_id == client_id,
                Grant.employer_name.like(f"%{ce.employer_name}%")
            ).all()
            
            print(f"  Found {len(grants)} grants to delete")
            for grant in grants:
                print(f"    - Deleting grant: {grant.employer_name}")
                db.delete(grant)
                deleted_count += 1
            
            # Delete all capital assets related to this employer
            capital_assets = db.query(CapitalAsset).filter(
                CapitalAsset.client_id == client_id,
                CapitalAsset.asset_name.like(f"%{ce.employer_name}%")
            ).all()
            
            print(f"  Found {len(capital_assets)} capital assets to delete")
            for asset in capital_assets:
                print(f"    - Deleting asset: {asset.asset_name}")
                db.delete(asset)
                deleted_count += 1
            
            # Delete all pension funds related to this employer
            pension_funds = db.query(PensionFund).filter(
                PensionFund.client_id == client_id,
                PensionFund.fund_name.like(f"%{ce.employer_name}%")
            ).all()
            
            print(f"  Found {len(pension_funds)} pension funds to delete")
            for pension in pension_funds:
                print(f"    - Deleting pension: {pension.fund_name}")
                db.delete(pension)
                deleted_count += 1
        
        # Clear end_date from current employer (unmark termination)
        ce.end_date = None
        # TODO: Clear severance_before_termination after running migration
        # ce.severance_before_termination = None
        db.add(ce)
        
        db.commit()
        
        print(f"✅ DELETED {deleted_count} entities related to termination")
        print(f"✅ Severance to restore: {severance_to_restore}")
        
        return {
            "success": True,
            "deleted_count": deleted_count,
            "severance_to_restore": severance_to_restore,
            "message": f"נמחקו {deleted_count} אלמנטים הקשורים לעזיבה"
        }
        
    except Exception as e:
        db.rollback()
        print(f"❌ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail={"error": f"שגיאה במחיקת החלטות עזיבה: {str(e)}"}
        )
