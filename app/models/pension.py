"""
Pension entity model for SQLAlchemy ORM - compatible with rights fixation system
"""

from datetime import datetime, timezone

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Pension(Base):
    __tablename__ = "pension"

    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(
        Integer, ForeignKey("client.id", ondelete="CASCADE"), nullable=False
    )
    payer_name = Column(String(200), nullable=True)
    start_date = Column(Date, nullable=True)  # ׳×׳—׳™׳׳× ׳§׳¦׳‘׳”

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
    )

    client = relationship("Client", backref="pensions")

    def to_dict(self):
        return {
            "id": self.id,
            "client_id": self.client_id,
            "payer_name": self.payer_name,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "commutations": (
                [c.to_dict() for c in self.commutations]
                if hasattr(self, "commutations")
                else []
            ),
        }
