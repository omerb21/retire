"""
State management service for retirement scenarios
שירות ניהול מצב לתרחישי פרישה
"""
import logging
from typing import Dict
from sqlalchemy.orm import Session
from app.models.pension_fund import PensionFund
from app.models.capital_asset import CapitalAsset
from app.models.additional_income import AdditionalIncome
from app.models.termination_event import TerminationEvent
from ..utils.serialization_utils import (
    serialize_pension_fund,
    serialize_capital_asset,
    serialize_additional_income,
    serialize_termination_event
)

logger = logging.getLogger("app.scenarios.state")


class StateService:
    """שירות לשמירה ושחזור מצב נתונים"""
    
    def __init__(self, db: Session, client_id: int):
        self.db = db
        self.client_id = client_id
    
    def save_current_state(self) -> Dict:
        """שומר את מצב הנתונים הנוכחי"""
        pension_funds = self.db.query(PensionFund).filter(
            PensionFund.client_id == self.client_id
        ).all()
        
        capital_assets = self.db.query(CapitalAsset).filter(
            CapitalAsset.client_id == self.client_id
        ).all()
        
        additional_incomes = self.db.query(AdditionalIncome).filter(
            AdditionalIncome.client_id == self.client_id
        ).all()
        
        termination_events = self.db.query(TerminationEvent).filter(
            TerminationEvent.client_id == self.client_id
        ).all()
        
        state = {
            "pension_funds": [serialize_pension_fund(pf) for pf in pension_funds],
            "capital_assets": [serialize_capital_asset(ca) for ca in capital_assets],
            "additional_incomes": [serialize_additional_income(ai) for ai in additional_incomes],
            "termination_events": [serialize_termination_event(te) for te in termination_events]
        }
        
        logger.info(f"  💾 Saved state: {len(pension_funds)} pension funds, {len(capital_assets)} capital assets")
        return state
    
    def restore_state(self, state: Dict):
        """משחזר את מצב הנתונים"""
        # Delete all current records
        self.db.query(PensionFund).filter(PensionFund.client_id == self.client_id).delete()
        self.db.query(CapitalAsset).filter(CapitalAsset.client_id == self.client_id).delete()
        self.db.query(AdditionalIncome).filter(AdditionalIncome.client_id == self.client_id).delete()
        self.db.query(TerminationEvent).filter(TerminationEvent.client_id == self.client_id).delete()
        
        # Restore from state
        for pf_data in state["pension_funds"]:
            pf = PensionFund(**pf_data)
            self.db.add(pf)
        
        for ca_data in state["capital_assets"]:
            ca = CapitalAsset(**ca_data)
            self.db.add(ca)
        
        for ai_data in state["additional_incomes"]:
            ai = AdditionalIncome(**ai_data)
            self.db.add(ai)
        
        for te_data in state["termination_events"]:
            te = TerminationEvent(**te_data)
            self.db.add(te)
        
        self.db.flush()
        logger.info(f"  🔄 Restored state: {len(state['pension_funds'])} pension funds, {len(state['capital_assets'])} capital assets")
