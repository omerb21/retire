"""
Client entity model for SQLAlchemy ORM
"""
from datetime import date
from sqlalchemy import Column, BigInteger, String, Date, Boolean, Text, Index
from sqlalchemy.sql import func

from app.database import Base


class Client(Base):
    """Client entity model"""
    __tablename__ = "client"
    
    # Primary key
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # ID number fields
    id_number_raw = Column(String(20), nullable=False)
    id_number = Column(String(9), nullable=False, unique=True, index=True)
    
    # Name fields
    full_name = Column(String(100), nullable=False, index=True)
    first_name = Column(String(50))
    last_name = Column(String(50))
    
    # Personal details
    birth_date = Column(Date, nullable=False)
    gender = Column(String(10))  # male, female, other
    marital_status = Column(String(20))  # single, married, divorced, widowed
    
    # Employment details
    self_employed = Column(Boolean, default=False)
    current_employer_exists = Column(Boolean, default=False)
    planned_termination_date = Column(Date)
    
    # Contact information
    email = Column(String(100))
    phone = Column(String(20))
    
    # Address
    address_street = Column(String(100))
    address_city = Column(String(50))
    address_postal_code = Column(String(10))
    
    # Retirement planning
    retirement_target_date = Column(Date)
    
    # Record management
    is_active = Column(Boolean, default=True, nullable=False)
    notes = Column(Text)
    created_at = Column(Date, default=func.now(), nullable=False)
    updated_at = Column(Date, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Indexes
    __table_args__ = (
        Index('ix_client_full_name_id_number', 'full_name', 'id_number'),
        Index('ix_client_is_active', 'is_active'),
    )
    
    def __repr__(self):
        return f"<Client(id={self.id}, id_number={self.id_number}, full_name='{self.full_name}')>"
