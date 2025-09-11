"""
Scenario Engine - Core calculation engine for retirement planning scenarios
"""
from sqlalchemy.orm import Session
from models.client import Client
from models.scenario import Scenario
from models.scenario_cashflow import ScenarioCashflow
from models.existing_product import ExistingProduct
from utils.logging_decorators import log_calculation
import json
from typing import Dict, List, Any
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP

def build_context(client: Client, scenario: Scenario) -> Dict[str, Any]:
    """Build calculation context with all necessary data"""
    
    # Parse scenario parameters
    parameters = json.loads(scenario.parameters_json) if scenario.parameters_json else {}
    
    context = {
        "client": client,
        "scenario": scenario,
        "parameters": parameters,
        "current_year": datetime.now().year,
        "retirement_age": parameters.get("retirement_age", 67),
        "life_expectancy": parameters.get("life_expectancy", 85),
        "indexation_rate": parameters.get("indexation_rate", 0.02),  # 2% default
        "tax_parameters": get_current_tax_parameters(),
        "products": [],
        "grants": [],
        "reservations": []
    }
    
    return context

@log_calculation
def apply_grants_and_reservations(context: Dict[str, Any]) -> Dict[str, Any]:
    """Apply grant calculations and reservations with 1.35 multiplier"""
    
    grants = context.get("grants", [])
    processed_grants = []
    
    for grant in grants:
        # Calculate reservation impact (grant × 1.35 reduces pension exemption)
        grant_amount = Decimal(str(grant.get("amount", 0)))
        reservation_impact = grant_amount * Decimal("1.35")
        
        processed_grant = {
            "original_amount": grant_amount,
            "reservation_impact": reservation_impact,
            "net_pension_reduction": reservation_impact,
            "grant_type": grant.get("type", "severance"),
            "payment_year": grant.get("payment_year", context["current_year"])
        }
        
        processed_grants.append(processed_grant)
    
    context["processed_grants"] = processed_grants
    context["total_reservation_impact"] = sum(g["reservation_impact"] for g in processed_grants)
    
    return context

@log_calculation
def apply_indexation(context: Dict[str, Any]) -> Dict[str, Any]:
    """Apply indexation to monetary amounts based on index series"""
    
    indexation_rate = context.get("indexation_rate", 0.02)
    current_year = context["current_year"]
    
    # Apply indexation to grants
    for grant in context.get("processed_grants", []):
        payment_year = grant["payment_year"]
        years_to_index = payment_year - current_year
        
        if years_to_index > 0:
            indexation_factor = (1 + indexation_rate) ** years_to_index
            grant["indexed_amount"] = grant["original_amount"] * Decimal(str(indexation_factor))
        else:
            grant["indexed_amount"] = grant["original_amount"]
    
    # Apply indexation to pension funds and other assets
    for product in context.get("products", []):
        if "current_balance" in product:
            # Project balance growth
            years_to_retirement = context["retirement_age"] - (current_year - context["client"].created_at.year + 25)  # Assume 25 as starting work age
            if years_to_retirement > 0:
                growth_factor = (1 + indexation_rate) ** years_to_retirement
                product["projected_balance"] = Decimal(str(product["current_balance"])) * Decimal(str(growth_factor))
            else:
                product["projected_balance"] = Decimal(str(product["current_balance"]))
    
    return context

@log_calculation
def calculate_pension_income(context: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate annual pension income based on accumulated funds"""
    
    retirement_age = context["retirement_age"]
    life_expectancy = context["life_expectancy"]
    years_in_retirement = life_expectancy - retirement_age
    
    total_pension_capital = Decimal("0")
    
    # Sum up all projected pension balances
    for product in context.get("products", []):
        if product.get("projected_balance"):
            total_pension_capital += product["projected_balance"]
    
    # Apply reservation reductions
    total_reservation_impact = context.get("total_reservation_impact", Decimal("0"))
    effective_pension_capital = total_pension_capital - total_reservation_impact
    
    # Calculate annual pension (simple annuity calculation)
    if years_in_retirement > 0 and effective_pension_capital > 0:
        annual_pension = effective_pension_capital / Decimal(str(years_in_retirement))
    else:
        annual_pension = Decimal("0")
    
    pension_data = {
        "total_capital": total_pension_capital,
        "reservation_impact": total_reservation_impact,
        "effective_capital": effective_pension_capital,
        "years_in_retirement": years_in_retirement,
        "annual_pension": annual_pension,
        "monthly_pension": annual_pension / 12
    }
    
    context["pension_calculation"] = pension_data
    
    return context

def calculate_taxes(context: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate taxes based on tax parameters and income"""
    
    tax_brackets = context["tax_parameters"]["brackets"]
    
    def calculate_tax_for_income(annual_income: Decimal) -> Decimal:
        """Calculate tax for given annual income using progressive brackets"""
        tax = Decimal("0")
        remaining_income = annual_income
        
        for bracket in tax_brackets:
            bracket_min = Decimal(str(bracket["min"]))
            bracket_max = Decimal(str(bracket.get("max", float("inf"))))
            bracket_rate = Decimal(str(bracket["rate"]))
            
            if remaining_income <= 0:
                break
                
            taxable_in_bracket = min(remaining_income, bracket_max - bracket_min)
            if taxable_in_bracket > 0:
                tax += taxable_in_bracket * bracket_rate
                remaining_income -= taxable_in_bracket
        
        return tax.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    context["tax_calculator"] = calculate_tax_for_income
    
    return context

@log_calculation
def generate_cashflow(context: Dict[str, Any], pension_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate yearly cashflow projections"""
    
    cashflow = []
    current_year = context["current_year"]
    retirement_age = context["retirement_age"]
    life_expectancy = context["life_expectancy"]
    
    # Calculate starting year for projections
    client_birth_year = current_year - 30  # Assume 30 years old (simplified)
    retirement_year = client_birth_year + retirement_age
    
    tax_calculator = context.get("tax_calculator")
    
    for year in range(retirement_year, client_birth_year + life_expectancy + 1):
        # Calculate income for this year
        gross_income = Decimal("0")
        pension_income = Decimal("0")
        grant_income = Decimal("0")
        other_income = Decimal("0")
        
        # Add pension income
        if year >= retirement_year:
            pension_income = pension_data["annual_pension"]
            gross_income += pension_income
        
        # Add grant income (if applicable for this year)
        for grant in context.get("processed_grants", []):
            if grant["payment_year"] == year:
                grant_amount = grant.get("indexed_amount", grant["original_amount"])
                grant_income += grant_amount
                gross_income += grant_amount
        
        # Calculate tax
        tax = tax_calculator(gross_income) if tax_calculator and gross_income > 0 else Decimal("0")
        
        # Calculate net income
        net_income = gross_income - tax
        
        cashflow_entry = {
            "year": year,
            "gross_income": float(gross_income),
            "pension_income": float(pension_income),
            "grant_income": float(grant_income),
            "other_income": float(other_income),
            "tax": float(tax),
            "net_income": float(net_income)
        }
        
        cashflow.append(cashflow_entry)
    
    return cashflow

def persist_cashflow(db: Session, scenario_id: int, cashflow_list: List[Dict[str, Any]]) -> None:
    """Save cashflow projections to database"""
    
    # Delete existing cashflow for this scenario
    db.query(ScenarioCashflow).filter(ScenarioCashflow.scenario_id == scenario_id).delete()
    
    # Insert new cashflow entries
    for entry in cashflow_list:
        cashflow_record = ScenarioCashflow(
            scenario_id=scenario_id,
            year=entry["year"],
            gross_income=entry["gross_income"],
            pension_income=entry["pension_income"],
            grant_income=entry["grant_income"],
            other_income=entry["other_income"],
            tax=entry["tax"],
            net_income=entry["net_income"]
        )
        db.add(cashflow_record)
    
    db.commit()

def get_current_tax_parameters() -> Dict[str, Any]:
    """Get current tax parameters (simplified version)"""
    return {
        "brackets": [
            {"min": 0, "max": 75960, "rate": 0.10},      # 10% up to 75,960 NIS
            {"min": 75960, "max": 108840, "rate": 0.14}, # 14% from 75,960 to 108,840
            {"min": 108840, "max": 174840, "rate": 0.20}, # 20% from 108,840 to 174,840
            {"min": 174840, "max": 243720, "rate": 0.31}, # 31% from 174,840 to 243,720
            {"min": 243720, "max": 507600, "rate": 0.35}, # 35% from 243,720 to 507,600
            {"min": 507600, "rate": 0.47}                 # 47% above 507,600
        ],
        "year": datetime.now().year
    }

def run_scenario(db: Session, client_id: int, scenario_id: int) -> List[Dict[str, Any]]:
    """Main function to run complete scenario calculation"""
    
    # Load client and scenario
    client = db.query(Client).filter(Client.id == client_id).first()
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    
    if not client or not scenario:
        raise ValueError("Client or scenario not found")
    
    # Load client's existing products
    products = db.query(ExistingProduct).filter(ExistingProduct.client_id == client_id).all()
    
    # Build context
    context = build_context(client, scenario)
    context["products"] = [
        {
            "id": p.id,
            "fund_code": p.fund_code,
            "current_balance": p.current_balance,
            "monthly_contribution": p.monthly_contribution
        }
        for p in products
    ]
    
    # Apply calculations step by step
    context = apply_grants_and_reservations(context)
    context = apply_indexation(context)
    context = calculate_pension_income(context)
    context = calculate_taxes(context)
    
    # Generate cashflow
    pension_data = context["pension_calculation"]
    cashflow = generate_cashflow(context, pension_data)
    
    # Persist to database
    persist_cashflow(db, scenario_id, cashflow)
    
    # Update scenario status
    scenario.status = "completed"
    db.commit()
    
    return cashflow
