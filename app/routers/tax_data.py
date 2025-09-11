"""
Tax Data API Router - Official tax parameters from government sources
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict
from datetime import datetime
from app.services.tax_data_service import TaxDataService

router = APIRouter()

@router.get("/tax-data/severance-cap")
def get_severance_cap(year: Optional[int] = Query(None, description="Year (default: current year)")):
    """
    Get current severance payment cap from official sources
    """
    try:
        if year is None:
            year = datetime.now().year
            
        cap = TaxDataService.get_current_severance_cap(year)
        
        return {
            "year": year,
            "monthly_cap": float(cap),
            "annual_cap": float(cap * 12),
            "source": "Israeli Tax Authority",
            "fetched_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching severance cap: {str(e)}")

@router.get("/tax-data/cpi")
def get_cpi_data(
    start_year: int = Query(..., description="Start year"),
    end_year: Optional[int] = Query(None, description="End year (default: current year)")
):
    """
    Get CPI (Consumer Price Index) data from CBS
    """
    try:
        if end_year is None:
            end_year = datetime.now().year
            
        cpi_data = TaxDataService.get_cpi_data(start_year, end_year)
        
        return {
            "start_year": start_year,
            "end_year": end_year,
            "records_count": len(cpi_data),
            "data": cpi_data,
            "fetched_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching CPI data: {str(e)}")

@router.get("/tax-data/tax-brackets")
def get_tax_brackets(year: Optional[int] = Query(None, description="Year (default: current year)")):
    """
    Get tax brackets for the specified year
    """
    try:
        if year is None:
            year = datetime.now().year
            
        brackets = TaxDataService.get_tax_brackets(year)
        
        return {
            "year": year,
            "brackets_count": len(brackets),
            "brackets": brackets,
            "fetched_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching tax brackets: {str(e)}")

@router.get("/tax-data/indexation-factor")
def get_indexation_factor(
    base_year: int = Query(..., description="Base year"),
    target_year: int = Query(..., description="Target year")
):
    """
    Calculate indexation factor between two years using CPI
    """
    try:
        factor = TaxDataService.calculate_indexation_factor(base_year, target_year)
        
        return {
            "base_year": base_year,
            "target_year": target_year,
            "indexation_factor": float(factor),
            "percentage_change": float((factor - 1) * 100),
            "calculated_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating indexation factor: {str(e)}")

@router.get("/tax-data/severance-exemption")
def calculate_severance_exemption(
    service_years: float = Query(..., description="Years of service"),
    year: Optional[int] = Query(None, description="Year (default: current year)")
):
    """
    Calculate severance exemption amount based on service years
    """
    try:
        if year is None:
            year = datetime.now().year
            
        exemption = TaxDataService.get_severance_exemption_amount(service_years, year)
        monthly_cap = TaxDataService.get_current_severance_cap(year)
        
        return {
            "service_years": service_years,
            "year": year,
            "monthly_cap": float(monthly_cap),
            "total_exemption": float(exemption),
            "calculation": f"{float(monthly_cap)} × {service_years} = {float(exemption)}",
            "calculated_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating severance exemption: {str(e)}")

@router.post("/tax-data/update-cache")
def update_tax_data_cache():
    """
    Update cached tax data from all official sources
    """
    try:
        summary = TaxDataService.update_tax_data_cache()
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating tax data cache: {str(e)}")

@router.get("/tax-data/summary")
def get_tax_data_summary(year: Optional[int] = Query(None, description="Year (default: current year)")):
    """
    Get summary of all tax data for the specified year
    """
    try:
        if year is None:
            year = datetime.now().year
            
        # Get all tax data
        severance_cap = TaxDataService.get_current_severance_cap(year)
        tax_brackets = TaxDataService.get_tax_brackets(year)
        cpi_data = TaxDataService.get_cpi_data(year, year)
        
        current_cpi = None
        if cpi_data:
            current_cpi = cpi_data[-1]["index_value"]
            
        return {
            "year": year,
            "severance_cap": {
                "monthly": float(severance_cap),
                "annual": float(severance_cap * 12)
            },
            "tax_brackets_count": len(tax_brackets),
            "current_cpi": current_cpi,
            "data_sources": ["Israeli Tax Authority", "CBS", "Government Publications"],
            "last_updated": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching tax data summary: {str(e)}")
