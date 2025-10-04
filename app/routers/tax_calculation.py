"""
API endpoints לחישוב מס הכנסה
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
import logging

from ..schemas.tax_schemas import (
    TaxCalculationInput, TaxCalculationResult, 
    ComprehensiveTaxAnalysis, AnnualTaxProjection,
    TaxOptimizationSuggestion
)
from ..services.tax_calculator import TaxCalculator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tax", tags=["Tax Calculation"])

def get_tax_calculator(tax_year: Optional[int] = None) -> TaxCalculator:
    """יוצר instance של מחשבון המס"""
    return TaxCalculator(tax_year)

@router.post("/calculate", response_model=TaxCalculationResult)
async def calculate_tax(
    input_data: TaxCalculationInput,
    calculator: TaxCalculator = Depends(get_tax_calculator)
) -> TaxCalculationResult:
    """
    מחשב מס הכנסה מקיף
    
    Args:
        input_data: נתוני הקלט לחישוב המס
        
    Returns:
        תוצאת חישוב מס מפורטת
    """
    try:
        logger.info(f"מתחיל חישוב מס לשנת {input_data.tax_year}")
        
        # עדכון שנת המס במחשבון אם נדרש
        if calculator.tax_year != input_data.tax_year:
            calculator = TaxCalculator(input_data.tax_year)
        
        result = calculator.calculate_comprehensive_tax(input_data)
        
        logger.info(f"הושלם חישוב מס בהצלחה: מס נטו {result.net_tax:,.2f} ש\"ח")
        return result
        
    except Exception as e:
        logger.error(f"שגיאה בחישוב מס: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"שגיאה בחישוב מס: {str(e)}"
        )

@router.post("/analyze", response_model=ComprehensiveTaxAnalysis)
async def analyze_tax_comprehensive(
    input_data: TaxCalculationInput,
    projection_years: int = Query(default=5, ge=1, le=20, description="מספר שנים לתחזית"),
    calculator: TaxCalculator = Depends(get_tax_calculator)
) -> ComprehensiveTaxAnalysis:
    """
    ניתוח מס מקיף כולל תחזיות והצעות אופטימיזציה
    
    Args:
        input_data: נתוני הקלט
        projection_years: מספר שנים לתחזית
        
    Returns:
        ניתוח מס מקיף
    """
    try:
        logger.info(f"מתחיל ניתוח מס מקיף לשנת {input_data.tax_year}")
        
        # חישוב נוכחי
        current_calculation = calculator.calculate_comprehensive_tax(input_data)
        
        # יצירת תחזיות שנתיות
        annual_projections = []
        for year_offset in range(1, projection_years + 1):
            future_year = input_data.tax_year + year_offset
            
            # יצירת נתוני קלט עתידיים (עם הצמדה)
            future_input = input_data.copy(deep=True)
            future_input.tax_year = future_year
            
            # הצמדה של 3% בשנה (ברירת מחדל)
            indexation_rate = 1.03 ** year_offset
            future_input.salary_income *= indexation_rate
            future_input.pension_income *= indexation_rate
            future_input.rental_income *= indexation_rate
            
            # חישוב מס עתידי
            future_calculator = TaxCalculator(future_year)
            future_result = future_calculator.calculate_comprehensive_tax(future_input)
            
            annual_projections.append(AnnualTaxProjection(
                year=future_year,
                projected_income=future_result.total_income,
                projected_tax=future_result.net_tax
            ))
        
        # הצעות אופטימיזציה
        optimization_suggestions = calculator.generate_optimization_suggestions(
            input_data, current_calculation
        )
        
        analysis = ComprehensiveTaxAnalysis(
            current_calculation=current_calculation,
            annual_projections=annual_projections,
            optimization_suggestions=optimization_suggestions
        )
        
        logger.info(f"הושלם ניתוח מס מקיף בהצלחה")
        return analysis
        
    except Exception as e:
        logger.error(f"שגיאה בניתוח מס מקיף: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"שגיאה בניתוח מס מקיף: {str(e)}"
        )

@router.get("/brackets/{year}")
async def get_tax_brackets(year: int):
    """
    מחזיר את מדרגות המס לשנה מסוימת
    
    Args:
        year: שנת המס
        
    Returns:
        מדרגות המס לשנה המבוקשת
    """
    try:
        calculator = TaxCalculator(year)
        brackets = [
            {
                "min_income": bracket.min_income,
                "max_income": bracket.max_income,
                "rate": bracket.rate,
                "rate_percentage": bracket.rate * 100,
                "description": bracket.description
            }
            for bracket in calculator.tax_brackets
        ]
        
        return {
            "year": year,
            "brackets": brackets,
            "currency": "ILS"
        }
        
    except Exception as e:
        logger.error(f"שגיאה בקבלת מדרגות מס לשנת {year}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"שגיאה בקבלת מדרגות מס: {str(e)}"
        )

@router.get("/credits/{year}")
async def get_available_tax_credits(year: int):
    """
    מחזיר את נקודות הזיכוי הזמינות לשנה מסוימת
    
    Args:
        year: שנת המס
        
    Returns:
        נקודות זיכוי זמינות
    """
    try:
        calculator = TaxCalculator(year)
        credits = [
            {
                "code": credit.code,
                "name": credit.name,
                "amount": credit.amount,
                "description": credit.description,
                "conditions": credit.conditions
            }
            for credit in calculator.available_credits
        ]
        
        return {
            "year": year,
            "credits": credits,
            "currency": "ILS"
        }
        
    except Exception as e:
        logger.error(f"שגיאה בקבלת נקודות זיכוי לשנת {year}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"שגיאה בקבלת נקודות זיכוי: {str(e)}"
        )

@router.post("/simulate")
async def simulate_tax_scenarios(
    base_input: TaxCalculationInput,
    scenarios: List[dict]
):
    """
    מדמה תרחישי מס שונים
    
    Args:
        base_input: נתוני בסיס
        scenarios: רשימת תרחישים לבדיקה
        
    Returns:
        השוואת תרחישים
    """
    try:
        calculator = TaxCalculator(base_input.tax_year)
        results = {}
        
        # חישוב תרחיש בסיס
        base_result = calculator.calculate_comprehensive_tax(base_input)
        results["base"] = {
            "description": "תרחיש בסיס",
            "result": base_result
        }
        
        # חישוב תרחישים נוספים
        for i, scenario in enumerate(scenarios):
            scenario_input = base_input.copy(deep=True)
            
            # עדכון נתונים לפי התרחיש
            for field, value in scenario.items():
                if hasattr(scenario_input, field):
                    setattr(scenario_input, field, value)
            
            scenario_result = calculator.calculate_comprehensive_tax(scenario_input)
            results[f"scenario_{i+1}"] = {
                "description": scenario.get("description", f"תרחיש {i+1}"),
                "changes": scenario,
                "result": scenario_result,
                "savings": base_result.net_tax - scenario_result.net_tax
            }
        
        return {
            "base_scenario": results["base"],
            "alternative_scenarios": {k: v for k, v in results.items() if k != "base"},
            "comparison_summary": {
                "best_scenario": min(
                    results.items(), 
                    key=lambda x: x[1]["result"].net_tax
                )[0],
                "max_savings": max(
                    [v.get("savings", 0) for v in results.values() if "savings" in v],
                    default=0
                )
            }
        }
        
    except Exception as e:
        logger.error(f"שגיאה בסימולציית תרחישים: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"שגיאה בסימולציית תרחישים: {str(e)}"
        )

@router.get("/health")
async def health_check():
    """בדיקת תקינות שירות חישוב המס"""
    try:
        # בדיקה בסיסית של המחשבון
        calculator = TaxCalculator()
        
        return {
            "status": "healthy",
            "service": "Tax Calculator",
            "version": "1.0.0",
            "tax_year": calculator.tax_year,
            "available_brackets": len(calculator.tax_brackets),
            "available_credits": len(calculator.available_credits)
        }
        
    except Exception as e:
        logger.error(f"שגיאה בבדיקת תקינות: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail=f"שירות חישוב המס אינו זמין: {str(e)}"
        )
