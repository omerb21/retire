"""
SavingProduct model - Raw imported data from XML files
"""
from sqlalchemy import Column, Integer, String, Float, Text, DateTime
from .base import Base, TimestampMixin, IdMixin
import datetime

class SavingProduct(Base, IdMixin, TimestampMixin):
    __tablename__ = "saving_product"
    
    # Fund identification
    fund_type = Column(String(50))
    company_name = Column(String(255))
    fund_name = Column(String(255))
    fund_code = Column(String(50), index=True)
    
    # Performance data
    yield_1yr = Column(Float, default=0.0)
    yield_3yr = Column(Float, default=0.0)
    
    # Raw XML storage
    raw_xml_blob = Column(Text)
    imported_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    def __repr__(self):
        return f"<SavingProduct(id={self.id}, fund_code='{self.fund_code}', company='{self.company_name}')>"
