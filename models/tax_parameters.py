"""
TaxParameters model - Versioned tax parameters and rates
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from .base import Base, TimestampMixin, IdMixin

class TaxParameters(Base, IdMixin, TimestampMixin):
    __tablename__ = "tax_parameters"
    
    # Version identification
    version = Column(String(50), nullable=False, unique=True)
    
    # Validity period
    valid_from = Column(DateTime, nullable=False)
    valid_to = Column(DateTime, nullable=True)  # NULL means current version
    
    # Parameters stored as JSON
    json_payload = Column(Text, nullable=False)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Metadata
    description = Column(String(500))
    source = Column(String(255))  # e.g., "Ministry of Finance", "Tax Authority"
    
    def __repr__(self):
        return f"<TaxParameters(id={self.id}, version='{self.version}', valid_from='{self.valid_from}', active={self.is_active})>"
