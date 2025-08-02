"""
Pension entity model for SQLAlchemy ORM - compatible with rights fixation system
"""
from sqlalchemy import Column, Integer, ForeignKey, String, Date, DateTime, func
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base

def utcnow():
    return datetime.now(timezone.utc)

class Pension(Base):
    __tablename__ = "pension"

    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(Integer, ForeignKey("client.id", ondelete="CASCADE"), nullable=False)
    payer_name = Column(String(200), nullable=True)
    start_date = Column(Date, nullable=True)  # תחילת קצבה

    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow, server_default=func.now())

    client = relationship("Client", backref="pensions")
    
    def to_dict(self):
        return {
            "id": self.id,
            "client_id": self.client_id,
            "payer_name": self.payer_name,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "commutations": [c.to_dict() for c in self.commutations] if hasattr(self, 'commutations') else []
        }
