"""
Scenario entity model for SQLAlchemy ORM
"""
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Boolean, func
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base

def utcnow():
    return datetime.now(timezone.utc)

class Scenario(Base):
    __tablename__ = "scenario"

    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(Integer, ForeignKey("client.id", ondelete="CASCADE"), nullable=False)
    scenario_name = Column(String(255), nullable=False)
    
    # Planning flags
    apply_tax_planning = Column(Boolean, nullable=False, default=False)
    apply_capitalization = Column(Boolean, nullable=False, default=False)
    apply_exemption_shield = Column(Boolean, nullable=False, default=False)
    
    # JSON fields for storing scenario data
    parameters = Column(Text, nullable=False, default='{}')  # ScenarioIn as JSON
    summary_results = Column(Text, nullable=True)  # ScenarioOut summary as JSON
    cashflow_projection = Column(Text, nullable=True)  # Cashflow data as JSON
    
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now())
    
    # Relationship
    client = relationship("Client", lazy="joined")

