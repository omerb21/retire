"""
IndexSeries model - Historical and projected index values for indexation calculations
"""
from sqlalchemy import Column, Integer, String, Float, Date, Boolean
from .base import Base, TimestampMixin, IdMixin

class IndexSeries(Base, IdMixin, TimestampMixin):
    __tablename__ = "index_series"
    
    # Index identification
    index_name = Column(String(100), nullable=False)  # e.g., "CPI", "Average_Wage"
    index_code = Column(String(20), nullable=False)   # e.g., "CPI", "AWG"
    
    # Date and value
    reference_date = Column(Date, nullable=False)
    index_value = Column(Float, nullable=False)
    
    # Data source and quality
    is_actual = Column(Boolean, default=True)  # True for actual, False for projected
    source = Column(String(255))  # e.g., "Central Bureau of Statistics"
    
    # Metadata
    base_period = Column(String(50))  # e.g., "2020=100"
    
    def __repr__(self):
        return f"<IndexSeries(id={self.id}, index='{self.index_code}', date='{self.reference_date}', value={self.index_value})>"
