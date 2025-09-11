"""
Client model - Core client entity with personal information
"""
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from .base import Base, TimestampMixin, IdMixin
import datetime

class Client(Base, IdMixin, TimestampMixin):
    __tablename__ = "client"
    
    # Identity fields
    id_number_raw = Column(String(20), nullable=False, unique=True)
    id_number_normalized = Column(String(20), nullable=False, index=True)
    
    # Personal information
    full_name = Column(String(255), nullable=False)
    sex = Column(String(10))
    marital_status = Column(String(20))
    
    # Address information
    address_city = Column(String(100))
    address_street = Column(String(100))
    address_number = Column(String(20))
    
    # Employment information
    employer_name = Column(String(255))
    
    # Relationships
    existing_products = relationship("ExistingProduct", back_populates="client")
    
    def __repr__(self):
        return f"<Client(id={self.id}, name='{self.full_name}', id_number='{self.id_number_normalized}')>"
