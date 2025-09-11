"""
Import sample data for testing the retirement planning system
Creates clients, employers, grants, pension funds, additional income, capital assets, and scenarios
"""
import sys
import os
from datetime import date, datetime, timedelta
from decimal import Decimal
import json
import random

# Add the project root to the path so we can import the app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, engine
from app.models.client import Client
from app.models.current_employer import CurrentEmployer, ActiveContinuityType
from app.models.employer_grant import EmployerGrant
from app.models.grant import Grant
from app.models.pension_fund import PensionFund, InputMode, IndexationMethod
from app.models.additional_income import AdditionalIncome, IncomeType
from app.models.capital_asset import CapitalAsset, AssetType
from app.models.scenario import Scenario

def create_sample_data():
    """Create sample data for testing"""
    db = SessionLocal()
    
    try:
        print("Creating sample data...")
        
        # Create clients
        clients = [
            Client(
                id_number="123456782",
                full_name="ישראל ישראלי",
                first_name="ישראל",
                last_name="ישראלי",
                birth_date=date(1970, 1, 1),
                gender="male",
                marital_status="married",
                email="israel@example.com",
                phone="054-1234567",
                address="רחוב הרצל 1, תל אביב",
                retirement_target_date=date(2030, 1, 1),
                is_active=True,
                notes="לקוח לדוגמה"
            ),
            Client(
                id_number="987654321",
                full_name="שרה כהן",
                first_name="שרה",
                last_name="כהן",
                birth_date=date(1975, 5, 15),
                gender="female",
                marital_status="single",
                email="sarah@example.com",
                phone="054-7654321",
                address="רחוב אלנבי 10, תל אביב",
                retirement_target_date=date(2035, 5, 15),
                is_active=True,
                notes="לקוחה לדוגמה"
            ),
            Client(
                id_number="555555555",
                full_name="יוסף לוי",
                first_name="יוסף",
                last_name="לוי",
                birth_date=date(1965, 10, 20),
                gender="male",
                marital_status="divorced",
                email="yosef@example.com",
                phone="054-5555555",
                address="רחוב דיזנגוף 50, תל אביב",
                retirement_target_date=date(2025, 10, 20),
                is_active=True,
                notes="לקוח לדוגמה"
            )
        ]
        
        for client in clients:
            db.add(client)
        
        db.flush()  # Flush to get client IDs
        
        # Create current employers
        employers = [
            CurrentEmployer(
                client_id=clients[0].id,
                employer_name="חברת היי-טק בע\"מ",
                employer_id_number="520123456",
                start_date=date(2010, 1, 1),
                last_salary=30000.0,
                average_salary=25000.0,
                severance_accrued=250000.0,
                active_continuity=ActiveContinuityType.severance,
                continuity_years=13.0
            ),
            CurrentEmployer(
                client_id=clients[1].id,
                employer_name="משרד עורכי דין",
                employer_id_number="520654321",
                start_date=date(2015, 6, 1),
                last_salary=22000.0,
                average_salary=20000.0,
                severance_accrued=120000.0,
                active_continuity=ActiveContinuityType.pension,
                continuity_years=8.0
            ),
            CurrentEmployer(
                client_id=clients[2].id,
                employer_name="חברת ייעוץ",
                employer_id_number="520555555",
                start_date=date(2005, 3, 15),
                last_salary=35000.0,
                average_salary=32000.0,
                severance_accrued=500000.0,
                active_continuity=ActiveContinuityType.severance,
                continuity_years=18.0
            )
        ]
        
        for employer in employers:
            db.add(employer)
        
        db.flush()  # Flush to get employer IDs
        
        # Create employer grants
        employer_grants = [
            EmployerGrant(
                employer_id=employers[0].id,
                grant_type="severance",
                grant_date=date(2023, 1, 1),
                amount=100000.0,
                reason="מענק פיצויים"
            ),
            EmployerGrant(
                employer_id=employers[0].id,
                grant_type="bonus",
                grant_date=date(2023, 6, 1),
                amount=50000.0,
                reason="בונוס שנתי"
            ),
            EmployerGrant(
                employer_id=employers[1].id,
                grant_type="severance",
                grant_date=date(2023, 3, 1),
                amount=80000.0,
                reason="מענק פיצויים"
            ),
            EmployerGrant(
                employer_id=employers[2].id,
                grant_type="adjustment",
                grant_date=date(2023, 5, 1),
                amount=20000.0,
                reason="התאמת שכר"
            )
        ]
        
        for grant in employer_grants:
            db.add(grant)
        
        # Create grants from past employers
        grants = [
            Grant(
                client_id=clients[0].id,
                employer_name="חברה קודמת בע\"מ",
                work_start_date=date(2000, 1, 1),
                work_end_date=date(2009, 12, 31),
                grant_amount=150000.0,
                grant_date=date(2010, 1, 15),
                grant_indexed_amount=180000.0,
                limited_indexed_amount=150000.0
            ),
            Grant(
                client_id=clients[1].id,
                employer_name="עסק משפחתי",
                work_start_date=date(2005, 1, 1),
                work_end_date=date(2014, 12, 31),
                grant_amount=100000.0,
                grant_date=date(2015, 1, 15),
                grant_indexed_amount=120000.0,
                limited_indexed_amount=100000.0
            ),
            Grant(
                client_id=clients[2].id,
                employer_name="חברת ייעוץ קודמת",
                work_start_date=date(1995, 1, 1),
                work_end_date=date(2004, 12, 31),
                grant_amount=200000.0,
                grant_date=date(2005, 1, 15),
                grant_indexed_amount=250000.0,
                limited_indexed_amount=200000.0
            )
        ]
        
        for grant in grants:
            db.add(grant)
        
        # Create pension funds
        pension_funds = [
            PensionFund(
                client_id=clients[0].id,
                fund_name="מנורה מבטחים",
                fund_number="12345",
                input_mode=InputMode.calculated,
                base_amount=500000.0,
                indexation_method=IndexationMethod.cpi,
                indexation_rate=0.02,
                indexed_amount=550000.0
            ),
            PensionFund(
                client_id=clients[0].id,
                fund_name="הראל פנסיה",
                fund_number="54321",
                input_mode=InputMode.manual,
                base_amount=300000.0,
                indexation_method=IndexationMethod.fixed,
                indexation_rate=0.03,
                indexed_amount=330000.0
            ),
            PensionFund(
                client_id=clients[1].id,
                fund_name="כלל פנסיה",
                fund_number="67890",
                input_mode=InputMode.calculated,
                base_amount=400000.0,
                indexation_method=IndexationMethod.cpi,
                indexation_rate=0.02,
                indexed_amount=440000.0
            ),
            PensionFund(
                client_id=clients[2].id,
                fund_name="מגדל פנסיה",
                fund_number="98765",
                input_mode=InputMode.manual,
                base_amount=700000.0,
                indexation_method=IndexationMethod.fixed,
                indexation_rate=0.025,
                indexed_amount=770000.0
            )
        ]
        
        for fund in pension_funds:
            db.add(fund)
        
        # Create additional income
        additional_incomes = [
            AdditionalIncome(
                client_id=clients[0].id,
                income_type=IncomeType.rental,
                source="דירה להשכרה",
                amount=5000.0,
                start_date=date(2020, 1, 1),
                end_date=date(2040, 1, 1),
                tax_rate=0.1
            ),
            AdditionalIncome(
                client_id=clients[1].id,
                income_type=IncomeType.dividend,
                source="תיק השקעות",
                amount=3000.0,
                start_date=date(2021, 1, 1),
                end_date=None,
                tax_rate=0.25
            ),
            AdditionalIncome(
                client_id=clients[2].id,
                income_type=IncomeType.other,
                source="ייעוץ עסקי",
                amount=10000.0,
                start_date=date(2022, 1, 1),
                end_date=date(2030, 1, 1),
                tax_rate=0.3
            )
        ]
        
        for income in additional_incomes:
            db.add(income)
        
        # Create capital assets
        capital_assets = [
            CapitalAsset(
                client_id=clients[0].id,
                asset_type=AssetType.stocks,
                name="תיק מניות",
                value=500000.0,
                purchase_date=date(2015, 1, 1),
                expected_return_rate=0.07
            ),
            CapitalAsset(
                client_id=clients[0].id,
                asset_type=AssetType.bonds,
                name="תיק אג\"ח",
                value=300000.0,
                purchase_date=date(2018, 1, 1),
                expected_return_rate=0.04
            ),
            CapitalAsset(
                client_id=clients[1].id,
                asset_type=AssetType.real_estate,
                name="דירה להשקעה",
                value=2000000.0,
                purchase_date=date(2010, 1, 1),
                expected_return_rate=0.05
            ),
            CapitalAsset(
                client_id=clients[2].id,
                asset_type=AssetType.other,
                name="קרן השקעות",
                value=1000000.0,
                purchase_date=date(2012, 1, 1),
                expected_return_rate=0.06
            )
        ]
        
        for asset in capital_assets:
            db.add(asset)
        
        # Create scenarios
        scenarios = [
            Scenario(
                client_id=clients[0].id,
                scenario_name="תרחיש בסיסי",
                apply_tax_planning=False,
                apply_capitalization=False,
                apply_exemption_shield=False,
                parameters=json.dumps({
                    "retirement_age": 67,
                    "life_expectancy": 85,
                    "monthly_expenses": 15000
                })
            ),
            Scenario(
                client_id=clients[0].id,
                scenario_name="תרחיש אופטימלי",
                apply_tax_planning=True,
                apply_capitalization=True,
                apply_exemption_shield=True,
                parameters=json.dumps({
                    "retirement_age": 67,
                    "life_expectancy": 85,
                    "monthly_expenses": 15000
                })
            ),
            Scenario(
                client_id=clients[1].id,
                scenario_name="תרחיש בסיסי",
                apply_tax_planning=False,
                apply_capitalization=False,
                apply_exemption_shield=False,
                parameters=json.dumps({
                    "retirement_age": 64,
                    "life_expectancy": 85,
                    "monthly_expenses": 12000
                })
            ),
            Scenario(
                client_id=clients[2].id,
                scenario_name="תרחיש בסיסי",
                apply_tax_planning=False,
                apply_capitalization=False,
                apply_exemption_shield=False,
                parameters=json.dumps({
                    "retirement_age": 67,
                    "life_expectancy": 85,
                    "monthly_expenses": 20000
                })
            )
        ]
        
        for scenario in scenarios:
            db.add(scenario)
        
        # Generate cashflow data for scenarios
        for scenario in scenarios:
            # Generate 12 months of cashflow data
            cashflow = []
            start_date = date.today().replace(day=1)
            
            for i in range(12):
                current_date = start_date + timedelta(days=30 * i)
                
                # Generate random inflow and outflow
                inflow = random.uniform(15000, 25000)
                outflow = random.uniform(10000, 15000)
                
                cashflow.append({
                    "date": current_date.isoformat(),
                    "inflow": inflow,
                    "outflow": outflow,
                    "net": inflow - outflow
                })
            
            # Add summary results
            summary_results = {
                "yearly_inflow": sum(cf["inflow"] for cf in cashflow),
                "yearly_outflow": sum(cf["outflow"] for cf in cashflow),
                "yearly_net": sum(cf["net"] for cf in cashflow),
                "average_monthly_net": sum(cf["net"] for cf in cashflow) / 12
            }
            
            scenario.cashflow_projection = json.dumps(cashflow)
            scenario.summary_results = json.dumps(summary_results)
        
        # Commit all changes
        db.commit()
        
        print(f"Sample data created successfully:")
        print(f"- {len(clients)} clients")
        print(f"- {len(employers)} current employers")
        print(f"- {len(employer_grants)} employer grants")
        print(f"- {len(grants)} past employer grants")
        print(f"- {len(pension_funds)} pension funds")
        print(f"- {len(additional_incomes)} additional incomes")
        print(f"- {len(capital_assets)} capital assets")
        print(f"- {len(scenarios)} scenarios")
        
    except Exception as e:
        db.rollback()
        print(f"Error creating sample data: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    create_sample_data()
