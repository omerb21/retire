from sqlalchemy import Column, Integer, String, Date, Float, ForeignKey, Enum, CheckConstraint, DateTime, func, event
from sqlalchemy.orm import relationship
from app.database import Base
import traceback

InputMode = Enum("calculated", "manual", name="pension_input_mode")
IndexationMethod = Enum("none", "cpi", "fixed", name="pension_indexation_method")

class PensionFund(Base):
    __tablename__ = "pension_funds"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("client.id", ondelete="CASCADE"), nullable=False, index=True)

    fund_name = Column(String(200), nullable=False)
    fund_type = Column(String(50), nullable=True)

    input_mode = Column(InputMode, nullable=False)              # calculated / manual
    balance = Column(Float, nullable=True)                      # נדרש ב-calculated
    annuity_factor = Column(Float, nullable=True)               # נדרש ב-calculated
    pension_amount = Column(Float, nullable=True)               # נשמר/מחושב

    pension_start_date = Column(Date, nullable=True)

    indexation_method = Column(IndexationMethod, nullable=False, default="none")  # none/cpi/fixed
    fixed_index_rate = Column(Float, nullable=True)            # שיעור שנתי לדוגמה 0.02

    indexed_pension_amount = Column(Float, nullable=True)

    remarks = Column(String(500), nullable=True)
    deduction_file = Column(String(200), nullable=True)  # תיק ניכויים
    
    # Conversion tracking - מעקב אחר המרה מתיק פנסיוני
    conversion_source = Column(String(1000), nullable=True)  # JSON עם פרטי המקור

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Relationship to Client
    client = relationship("Client", back_populates="pension_funds")

    __table_args__ = (
        CheckConstraint("(balance IS NULL OR balance >= 0)", name="pf_balance_nonneg"),
        CheckConstraint("(annuity_factor IS NULL OR annuity_factor > 0)", name="pf_annuity_pos"),
        CheckConstraint("(pension_amount IS NULL OR pension_amount >= 0)", name="pf_pension_nonneg"),
        CheckConstraint("(fixed_index_rate IS NULL OR fixed_index_rate >= 0)", name="pf_fixed_rate_nonneg"),
    )


# Event listener to track balance changes
@event.listens_for(PensionFund, "before_update")
def log_balance_change(mapper, connection, target):
    """Log when balance is being changed"""
    if hasattr(target, '_sa_instance_state'):
        history = target._sa_instance_state.get_history('balance', True)
        if history.has_changes():
            old_balance = history.deleted[0] if history.deleted else None
            new_balance = target.balance
            print(f"🔴🔴🔴 BALANCE CHANGE DETECTED!")
            print(f"  Fund ID: {target.id}")
            print(f"  Old Balance: {old_balance}")
            print(f"  New Balance: {new_balance}")
            print(f"  Input Mode: {target.input_mode}")
            print(f"  Stack trace:")
            for line in traceback.format_stack()[-5:]:
                print(f"    {line.strip()}")
            print()
