from sqlalchemy import Column, Integer, Float, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class FixationResult(Base):
    __tablename__ = "fixation_result"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("client.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Main calculation results
    exempt_capital_remaining = Column(Float, nullable=False, default=0.0)
    used_commutation = Column(Float, nullable=False, default=0.0)
    
    # Raw data storage
    raw_payload = Column(JSON, nullable=True)  # Input parameters
    raw_result = Column(JSON, nullable=True)   # Detailed calculation output
    
    # Additional notes
    notes = Column(String(500), nullable=True)
    
    # Relationship to client
    client = relationship("Client", back_populates="fixation_results")

    def __repr__(self):
        return f"<FixationResult(id={self.id}, client_id={self.client_id}, exempt_capital={self.exempt_capital_remaining})>"

    def __str__(self):
        return f"Fixation Result #{self.id} for Client {self.client_id}: Exempt Capital={self.exempt_capital_remaining}, Used Commutation={self.used_commutation}"
