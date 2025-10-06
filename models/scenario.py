"""
Scenario model - Planning scenarios with parameters and results
"""
from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base, TimestampMixin, IdMixin

class Scenario(Base, IdMixin, TimestampMixin):
    __tablename__ = "scenario"
    
    # Foreign key to client
    client_id = Column(Integer, ForeignKey("client.id"), nullable=False)
    
    # Scenario identification
    name = Column(String(255), nullable=False)
    status = Column(String(20), default="draft")  # draft, active, completed, archived
    
    # Scenario parameters stored as JSON
    parameters_json = Column(Text)  # JSON string with all scenario parameters
    
    # Relationships
    client = relationship("Client")
    cashflows = relationship("ScenarioCashflow", back_populates="scenario", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Scenario(id={self.id}, client_id={self.client_id}, name='{self.name}', status='{self.status}')>"
