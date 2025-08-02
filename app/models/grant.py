"""
Grant entity model for SQLAlchemy ORM - compatible with rights fixation system
"""
from sqlalchemy import Column, Integer, ForeignKey, String, Float, Date, DateTime, func
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base

def utcnow():
    return datetime.now(timezone.utc)

class Grant(Base):
    __tablename__ = "grant"

    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(Integer, ForeignKey("client.id", ondelete="CASCADE"), nullable=False)
    employer_name = Column(String(200), nullable=True)
    work_start_date = Column(Date, nullable=True)
    work_end_date = Column(Date, nullable=True)
    grant_amount = Column(Float, nullable=True)  # נומינלי
    grant_date = Column(Date, nullable=True)
    grant_indexed_amount = Column(Float, nullable=True)  # סכום מוצמד ("מענק פטור צמוד")
    limited_indexed_amount = Column(Float, nullable=True)  # סכום מוגבל ל-32 שנים ("מענק פטור צמוד (32 שנים)")
    grant_ratio = Column(Float, nullable=True)  # חלק יחסי
    impact_on_exemption = Column(Float, nullable=True)  # פגיעה בתקרה

    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow, server_default=func.now())

    client = relationship("Client", backref="grants")
    
    def to_dict(self):
        return {
            "id": self.id,
            "client_id": self.client_id,
            "employer_name": self.employer_name,
            "work_start_date": self.work_start_date.isoformat() if self.work_start_date else None,
            "work_end_date": self.work_end_date.isoformat() if self.work_end_date else None,
            "grant_amount": self.grant_amount,
            "grant_date": self.grant_date.isoformat() if self.grant_date else None,
            "grant_indexed_amount": self.grant_indexed_amount,
            "limited_indexed_amount": self.limited_indexed_amount,
            "grant_ratio": self.grant_ratio,
            "impact_on_exemption": self.impact_on_exemption
        }
