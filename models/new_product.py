"""
NewProduct model - Products that couldn't be mapped to existing clients
"""
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base, TimestampMixin, IdMixin

class NewProduct(Base, IdMixin, TimestampMixin):
    __tablename__ = "new_product"
    
    # Source reference
    saving_product_id = Column(Integer, ForeignKey("saving_product.id"), nullable=False)
    
    # Extracted client information (for future matching)
    potential_client_id = Column(String(20))  # ID number found in XML
    potential_client_name = Column(String(255))  # Name found in XML
    
    # Product details
    fund_code = Column(String(50))
    fund_name = Column(String(255))
    company_name = Column(String(255))
    
    # Financial data
    current_balance = Column(Float, default=0.0)
    monthly_contribution = Column(Float, default=0.0)
    yield_1yr = Column(Float, default=0.0)
    yield_3yr = Column(Float, default=0.0)
    
    # Processing status
    status = Column(String(20), default="pending")  # pending, matched, rejected
    match_confidence = Column(Float, default=0.0)  # 0.0 to 1.0
    
    # Additional data for matching
    raw_data = Column(Text)  # JSON with additional fields for matching
    
    # Relationships
    saving_product = relationship("SavingProduct")
    
    def __repr__(self):
        return f"<NewProduct(id={self.id}, potential_id='{self.potential_client_id}', fund_code='{self.fund_code}')>"
