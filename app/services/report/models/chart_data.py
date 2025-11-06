"""
Chart data models
"""
from typing import List, Dict, Any
from pydantic import BaseModel


class ChartData(BaseModel):
    """Chart data container"""
    dates: List[str]
    net_values: List[float]
    
    class Config:
        arbitrary_types_allowed = True


class SeriesData(BaseModel):
    """Time series data for charts"""
    label: str
    values: List[float]
    color: str = '#2E86AB'
    
    class Config:
        arbitrary_types_allowed = True
