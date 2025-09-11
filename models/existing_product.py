"""
ExistingProduct model - Products mapped to existing clients
"""
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from .base import Base, TimestampMixin, IdMixin

class ExistingProduct(Base, IdMixin, TimestampMixin):
    __tablename__ = "existing_product"
    
    # Foreign keys
    client_id = Column(Integer, ForeignKey("client.id"), nullable=False)
    saving_product_id = Column(Integer, ForeignKey("saving_product.id"), nullable=False)
    
    # Product details
    fund_code = Column(String(50))
    fund_name = Column(String(255))
    company_name = Column(String(255))
    
    # Financial data
    current_balance = Column(Float, default=0.0)
    monthly_contribution = Column(Float, default=0.0)
    yield_1yr = Column(Float, default=0.0)
    yield_3yr = Column(Float, default=0.0)
    
    # Status
    status = Column(String(20), default="active")  # active, inactive, closed
    
    # Relationships
    client = relationship("Client", back_populates="existing_products")
    saving_product = relationship("SavingProduct")
    
    def __repr__(self):
        return f"<ExistingProduct(id={self.id}, client_id={self.client_id}, fund_code='{self.fund_code}')>"
