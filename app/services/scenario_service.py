"""
Scenario service for managing calculation scenarios
"""
import json
import logging
import time
from datetime import date, datetime
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.scenario import Scenario
from app.models.client import Client
from app.models.employment import Employment
from app.schemas.scenario import ScenarioCreateIn, ScenarioOut, CashflowPoint, ScenarioListItem
from app.calculation.engine.calculation_engine import CalculationEngine
from app.providers.tax_params import InMemoryTaxParamsProvider

logger = logging.getLogger("app.scenario")


class ScenarioService:
    @staticmethod
    def create_scenario(db: Session, client_id: int, data: ScenarioCreateIn) -> Scenario:
        """Create a new scenario for a client"""
        start_time = time.time()
        
        try:
            # Verify client exists and is active
            client = db.get(Client, client_id)
            if not client:
                raise ValueError("׳׳§׳•׳— ׳׳ ׳ ׳׳¦׳")
            if not client.is_active:
                raise ValueError("׳׳§׳•׳— ׳׳ ׳₪׳¢׳™׳")
            
            # Prepare parameters JSON
            parameters = {
                "planned_termination_date": data.planned_termination_date.isoformat() if data.planned_termination_date else None,
                "monthly_expenses": data.monthly_expenses,
                **data.other_parameters
            }
            
            # Create scenario
            scenario = Scenario(
                client_id=client_id,
                scenario_name=data.scenario_name,
                apply_tax_planning=data.apply_tax_planning,
                apply_capitalization=data.apply_capitalization,
                apply_exemption_shield=data.apply_exemption_shield,
                parameters=json.dumps(parameters, ensure_ascii=False)
            )
            
            db.add(scenario)
            db.commit()
            db.refresh(scenario)
            
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(json.dumps({
                "event": "scenario.create",
                "client_id": client_id,
                "scenario_id": scenario.id,
                "ok": True,
                "duration_ms": duration_ms
            }, ensure_ascii=False))
            
            return scenario
            
        except Exception as e:
            db.rollback()
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(json.dumps({
                "event": "scenario.create",
                "client_id": client_id,
                "ok": False,
                "error": str(e),
                "duration_ms": duration_ms
            }, ensure_ascii=False))
            raise

    @staticmethod
    def run_scenario(db: Session, scenario_id: int) -> ScenarioOut:
        """Run a scenario calculation and save results"""
        start_time = time.time()
        
        try:
            # Load scenario
            scenario = db.get(Scenario, scenario_id)
            if not scenario:
                raise ValueError("׳×׳¨׳—׳™׳© ׳׳ ׳ ׳׳¦׳")
            
            # Load client and verify active
            client = db.get(Client, scenario.client_id)
            if not client or not client.is_active:
                raise ValueError("׳׳§׳•׳— ׳׳ ׳ ׳׳¦׳ ׳׳• ׳׳ ׳₪׳¢׳™׳")
            
            # Load current employment (is_current = True)
            employment = db.query(Employment).filter(
                and_(Employment.client_id == scenario.client_id, Employment.is_current == True)
            ).first()
            
            if not employment:
                # Try to find most recent employment if no current employment
                employment = db.query(Employment).filter(
                    Employment.client_id == scenario.client_id
                ).order_by(Employment.start_date.desc()).first()
                
            if not employment:
                raise ValueError("׳׳™׳ ׳ ׳×׳•׳ ׳™ ׳×׳¢׳¡׳•׳§׳” ׳׳—׳™׳©׳•׳‘")
            
            # Parse scenario parameters
            parameters = json.loads(scenario.parameters) if scenario.parameters else {}
            planned_termination_date = None
            if parameters.get("planned_termination_date"):
                planned_termination_date = datetime.fromisoformat(parameters["planned_termination_date"]).date()
            
            # Determine termination date for calculation
            termination_date = planned_termination_date or employment.planned_termination_date or date.today()
            
            # Initialize calculation engine with tax parameters provider
            tax_provider = InMemoryTaxParamsProvider()
            calc_engine = CalculationEngine(db=db, tax_provider=tax_provider)
            
            # Prepare scenario input for calculation
            from app.schemas.scenario import ScenarioIn
            scenario_in = ScenarioIn(
                planned_termination_date=termination_date,
                monthly_expenses=parameters.get("monthly_expenses")
            )
            
            # Run calculation (planning flags are for future enhancement)
            try:
                result = calc_engine.run(client_id=scenario.client_id, scenario=scenario_in)
            except Exception as calc_error:
                if "׳¡׳“׳¨׳× ׳׳“׳“ ׳—׳¡׳¨׳”" in str(calc_error) or "׳׳™׳ ׳ ׳×׳•׳ ׳™ ׳×׳¢׳¡׳•׳§׳” ׳׳—׳™׳©׳•׳‘" in str(calc_error):
                    raise ValueError(str(calc_error))
                raise
            
            # Generate cashflow projection (12+ months)
            cashflow_projection = ScenarioService._generate_cashflow_projection(
                result, parameters.get("monthly_expenses", 0)
            )
            
            # Prepare summary results
            summary_results = {
                "seniority_years": result.seniority_years,
                "grant_gross": result.grant_gross,
                "grant_exempt": result.grant_exempt,
                "grant_tax": result.grant_tax,
                "grant_net": result.grant_net,
                "pension_monthly": result.pension_monthly,
                "indexation_factor": result.indexation_factor
            }
            
            # Save results to database
            scenario.cashflow_projection = json.dumps([
                {
                    "date": point.date.isoformat(),
                    "inflow": point.inflow,
                    "outflow": point.outflow,
                    "net": point.net
                }
                for point in cashflow_projection
            ], ensure_ascii=False)
            
            scenario.summary_results = json.dumps(summary_results, ensure_ascii=False)
            
            db.commit()
            db.refresh(scenario)
            
            # Prepare response
            scenario_out = ScenarioOut(
                seniority_years=result.seniority_years,
                grant_gross=result.grant_gross,
                grant_exempt=result.grant_exempt,
                grant_tax=result.grant_tax,
                grant_net=result.grant_net,
                pension_monthly=result.pension_monthly,
                indexation_factor=result.indexation_factor,
                cashflow=cashflow_projection
            )
            
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(json.dumps({
                "event": "scenario.run",
                "scenario_id": scenario_id,
                "client_id": scenario.client_id,
                "ok": True,
                "duration_ms": duration_ms
            }, ensure_ascii=False))
            
            return scenario_out
            
        except Exception as e:
            db.rollback()
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(json.dumps({
                "event": "scenario.run",
                "scenario_id": scenario_id,
                "ok": False,
                "error": str(e),
                "duration_ms": duration_ms
            }, ensure_ascii=False))
            raise

    @staticmethod
    def get_scenario(db: Session, scenario_id: int) -> Optional[ScenarioOut]:
        """Get a scenario with its saved results"""
        scenario = db.get(Scenario, scenario_id)
        if not scenario:
            return None
        
        # Parse saved results
        summary_results = json.loads(scenario.summary_results) if scenario.summary_results else {}
        cashflow_data = json.loads(scenario.cashflow_projection) if scenario.cashflow_projection else []
        
        # Convert cashflow data back to CashflowPoint objects
        cashflow = [
            CashflowPoint(
                date=datetime.fromisoformat(point["date"]).date(),
                inflow=point["inflow"],
                outflow=point["outflow"],
                net=point["net"]
            )
            for point in cashflow_data
        ]
        
        return ScenarioOut(
            seniority_years=summary_results.get("seniority_years", 0.0),
            grant_gross=summary_results.get("grant_gross", 0.0),
            grant_exempt=summary_results.get("grant_exempt", 0.0),
            grant_tax=summary_results.get("grant_tax", 0.0),
            grant_net=summary_results.get("grant_net", 0.0),
            pension_monthly=summary_results.get("pension_monthly", 0.0),
            indexation_factor=summary_results.get("indexation_factor", 1.0),
            cashflow=cashflow
        )

    @staticmethod
    def list_scenarios(db: Session, client_id: int) -> List[ScenarioListItem]:
        """List all scenarios for a client"""
        scenarios = db.query(Scenario).filter(
            Scenario.client_id == client_id
        ).order_by(Scenario.created_at.desc()).all()
        
        return [
            ScenarioListItem(
                id=scenario.id,
                scenario_name=scenario.scenario_name,
                apply_tax_planning=scenario.apply_tax_planning,
                apply_capitalization=scenario.apply_capitalization,
                apply_exemption_shield=scenario.apply_exemption_shield,
                created_at=scenario.created_at
            )
            for scenario in scenarios
        ]

    @staticmethod
    def _generate_cashflow_projection(result, monthly_expenses: float = 0) -> List[CashflowPoint]:
        """Generate 12+ months cashflow projection"""
        cashflow = []
        base_date = date.today()
        
        # Generate 12 months of cashflow
        for month in range(12):
            # Simple projection - in real implementation this would be more sophisticated
            month_date = date(base_date.year + (base_date.month + month - 1) // 12,
                            ((base_date.month + month - 1) % 12) + 1, 1)
            
            # Monthly pension as inflow
            inflow = result.pension_monthly
            
            # Monthly expenses as outflow
            outflow = monthly_expenses
            
            # Net cashflow
            net = inflow - outflow
            
            cashflow.append(CashflowPoint(
                date=month_date,
                inflow=inflow,
                outflow=outflow,
                net=net
            ))
        
        return cashflow

