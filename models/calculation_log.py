"""
CalculationLog model - Audit trail for all calculations with input/output snapshots
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from .base import Base, TimestampMixin, IdMixin
import uuid

class CalculationLog(Base, IdMixin, TimestampMixin):
    __tablename__ = "calculation_log"
    
    # Trace identifier for grouping related calculations
    trace_id = Column(String(36), default=lambda: str(uuid.uuid4()), nullable=False, index=True)
    
    # Client reference
    client_id = Column(Integer, ForeignKey("client.id"), nullable=True)
    
    # Function identification
    function_name = Column(String(255), nullable=False)
    
    # Calculation snapshots stored as JSON
    input_snapshot = Column(Text)  # JSON string of input parameters
    output_snapshot = Column(Text)  # JSON string of output results
    tax_snapshot = Column(Text)  # JSON string of tax parameters used
    
    # Execution metadata
    execution_time_ms = Column(Integer)  # Execution time in milliseconds
    status = Column(String(20), default="success")  # success, error, warning
    error_message = Column(Text)  # Error details if status is error
    
    def __repr__(self):
        return f"<CalculationLog(id={self.id}, trace_id='{self.trace_id}', function='{self.function_name}', status='{self.status}')>"
