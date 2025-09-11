"""
ScenarioCashflow model - Yearly cashflow projections for scenarios
"""
from sqlalchemy import Column, Integer, Float, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base, TimestampMixin, IdMixin

class ScenarioCashflow(Base, IdMixin, TimestampMixin):
    __tablename__ = "scenario_cashflow"
    
    # Foreign key to scenario
    scenario_id = Column(Integer, ForeignKey("scenario.id"), nullable=False)
    
    # Year for this cashflow entry
    year = Column(Integer, nullable=False)
    
    # Financial projections
    gross_income = Column(Float, default=0.0)  # Total gross income for the year
    tax = Column(Float, default=0.0)  # Total tax liability
    net_income = Column(Float, default=0.0)  # Net income after tax
    
    # Additional breakdown fields
    pension_income = Column(Float, default=0.0)  # Income from pension funds
    grant_income = Column(Float, default=0.0)  # Income from grants/severance
    other_income = Column(Float, default=0.0)  # Other sources of income
    
    # Relationships
    scenario = relationship("Scenario", back_populates="cashflows")
    
    def __repr__(self):
        return f"<ScenarioCashflow(id={self.id}, scenario_id={self.scenario_id}, year={self.year}, net={self.net_income})>"
