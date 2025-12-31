"""
System Snapshot Service
שירות לשמירה ושחזור מצב מערכת מלא
"""
import logging
from typing import Dict, Optional
from sqlalchemy.orm import Session
from datetime import datetime, date
import json

from app.models.client import Client
from app.models.pension_fund import PensionFund
from app.models.capital_asset import CapitalAsset
from app.models.additional_income import AdditionalIncome
from app.models.grant import Grant
from app.models.current_employment import CurrentEmployer, EmployerGrant
from app.models.termination_event import TerminationEvent
from app.models.fixation_result import FixationResult
from app.services.retirement.utils.pension_utils import compute_pension_start_date_from_funds

logger = logging.getLogger("app.snapshot")


def _parse_date(date_str: Optional[str]) -> Optional[date]:
    """ממיר string של תאריך לאובייקט date"""
    if not date_str:
        return None
    if isinstance(date_str, date):
        return date_str
    try:
        return datetime.fromisoformat(date_str).date()
    except (ValueError, AttributeError):
        return None


def _parse_datetime(datetime_str: Optional[str]) -> Optional[datetime]:
    """ממיר string של תאריך ושעה לאובייקט datetime"""
    if not datetime_str:
        return None
    if isinstance(datetime_str, datetime):
        return datetime_str
    try:
        return datetime.fromisoformat(datetime_str)
    except (ValueError, AttributeError):
        return None


class SnapshotService:
    """שירות לניהול snapshots של מצב המערכת"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def save_snapshot(self, client_id: int, snapshot_name: str = None) -> Dict:
        """
        שמירת snapshot מלא של מצב הלקוח
        
        Args:
            client_id: מזהה לקוח
            snapshot_name: שם אופציונלי ל-snapshot
            
        Returns:
            Dict עם פרטי ה-snapshot
        """
        logger.info(f"💾 Creating snapshot for client {client_id}")
        
        # בדיקת קיום לקוח
        client = self.db.query(Client).filter(Client.id == client_id).first()
        if not client:
            raise ValueError(f"לקוח {client_id} לא נמצא")
        
        timestamp = datetime.now()
        snapshot_name = snapshot_name or f"שמירה אוטומטית {timestamp.strftime('%d/%m/%Y %H:%M')}"
        
        # איסוף כל הנתונים
        snapshot_data = {
            "client_id": client_id,
            "snapshot_name": snapshot_name,
            "created_at": timestamp.isoformat(),
            "data": {
                "pension_funds": self._collect_pension_funds(client_id),
                "capital_assets": self._collect_capital_assets(client_id),
                "additional_incomes": self._collect_additional_incomes(client_id),
                "current_employer": self._collect_current_employer(client_id),
                "grants": self._collect_grants(client_id),
                "legacy_grants": self._collect_legacy_grants(client_id),
                "termination_event": self._collect_termination_event(client_id),
                "fixation_result": self._collect_fixation_result(client_id),
            },
        }
        
        # ספירת פריטים
        total_items = (
            len(snapshot_data["data"]["pension_funds"]) +
            len(snapshot_data["data"]["capital_assets"]) +
            len(snapshot_data["data"]["additional_incomes"]) +
            (1 if snapshot_data["data"]["current_employer"] else 0) +
            len(snapshot_data["data"]["grants"]) +
            len(snapshot_data["data"].get("legacy_grants", [])) +
            (1 if snapshot_data["data"]["termination_event"] else 0) +
            (1 if snapshot_data["data"]["fixation_result"] else 0)
        )

        logger.info(f"  ✅ Snapshot created: {total_items} items")
        logger.info(f"     - Pension Funds: {len(snapshot_data['data']['pension_funds'])}")
        logger.info(f"     - Capital Assets: {len(snapshot_data['data']['capital_assets'])}")
        logger.info(f"     - Additional Incomes: {len(snapshot_data['data']['additional_incomes'])}")
        logger.info(f"     - Grants (current employer): {len(snapshot_data['data']['grants'])}")
        logger.info(f"     - Legacy Grants (rights fixation): {len(snapshot_data['data']['legacy_grants'])}")

        # שמירה ב-localStorage (client-side) או בקובץ (server-side)
        # כרגע נחזיר את הנתונים, הם יישמרו ב-localStorage בצד הלקוח
        
        return {
            "success": True,
            "snapshot": snapshot_data,
            "total_items": total_items,
            "message": f"נשמרו {total_items} פריטים בהצלחה"
        }
    
    def restore_snapshot(self, client_id: int, snapshot_data: Dict) -> Dict:
        """
        שחזור מצב מ-snapshot
        
        Args:
            client_id: מזהה לקוח
            snapshot_data: נתוני ה-snapshot
            
        Returns:
            Dict עם פרטי השחזור
        """
        logger.info(f"♻️ Restoring snapshot for client {client_id}")
        
        # בדיקת קיום לקוח
        client = self.db.query(Client).filter(Client.id == client_id).first()
        if not client:
            raise ValueError(f"לקוח {client_id} לא נמצא")
        
        # בדיקת תקינות snapshot
        if not snapshot_data.get("data"):
            raise ValueError("נתוני snapshot לא תקינים")
        
        data = snapshot_data["data"]
        deleted_count = 0
        restored_count = 0
        
        try:
            # שלב 1: מחיקת כל הנתונים הקיימים
            logger.info("  🗑️ Deleting current data...")
            
            deleted_count += self.db.query(PensionFund).filter(
                PensionFund.client_id == client_id
            ).delete(synchronize_session=False)
            
            deleted_count += self.db.query(CapitalAsset).filter(
                CapitalAsset.client_id == client_id
            ).delete(synchronize_session=False)
            
            deleted_count += self.db.query(AdditionalIncome).filter(
                AdditionalIncome.client_id == client_id
            ).delete(synchronize_session=False)
            
            deleted_count += self.db.query(FixationResult).filter(
                FixationResult.client_id == client_id
            ).delete(synchronize_session=False)

            # מחיקת מענקים מטבלת grant (מערכת קיבוע זכויות הישנה)
            deleted_count += self.db.query(Grant).filter(
                Grant.client_id == client_id
            ).delete(synchronize_session=False)

            deleted_count += self.db.query(TerminationEvent).filter(
                TerminationEvent.client_id == client_id
            ).delete(synchronize_session=False)
            
            # מחיקת מענקים ומעסיק נוכחי
            employers = self.db.query(CurrentEmployer).filter(
                CurrentEmployer.client_id == client_id
            ).all()
            
            for employer in employers:
                deleted_count += self.db.query(EmployerGrant).filter(
                    EmployerGrant.employer_id == employer.id
                ).delete(synchronize_session=False)
            
            deleted_count += self.db.query(CurrentEmployer).filter(
                CurrentEmployer.client_id == client_id
            ).delete(synchronize_session=False)
            
            self.db.flush()
            logger.info(f"  ✅ Deleted {deleted_count} existing items")
            
            # שלב 2: שחזור הנתונים מה-snapshot
            logger.info("  📦 Restoring from snapshot...")
            
            # שחזור קרנות פנסיה
            for pf_data in data.get("pension_funds", []):
                pf_data = dict(pf_data)
                pf_data["pension_start_date"] = _parse_date(pf_data.get("pension_start_date"))
                pf_data.pop("created_at", None)
                pf_data.pop("updated_at", None)
                pf = PensionFund(**pf_data)
                self.db.add(pf)
                restored_count += 1
            
            # שחזור נכסי הון
            for ca_data in data.get("capital_assets", []):
                ca_data = dict(ca_data)
                ca_data["start_date"] = _parse_date(ca_data.get("start_date"))
                ca_data["end_date"] = _parse_date(ca_data.get("end_date"))
                ca_data.pop("created_at", None)
                ca_data.pop("updated_at", None)
                ca = CapitalAsset(**ca_data)
                self.db.add(ca)
                restored_count += 1
            
            # שחזור הכנסות נוספות
            for ai_data in data.get("additional_incomes", []):
                ai_data = dict(ai_data)
                ai_data["start_date"] = _parse_date(ai_data.get("start_date"))
                ai_data["end_date"] = _parse_date(ai_data.get("end_date"))
                ai_data.pop("created_at", None)
                ai_data.pop("updated_at", None)
                ai = AdditionalIncome(**ai_data)
                self.db.add(ai)
                restored_count += 1

            # שחזור מענקים מטבלת grant (legacy rights fixation)
            for grant_data in data.get("legacy_grants", []):
                grant_data = dict(grant_data)
                grant_data["client_id"] = client_id
                grant_data["work_start_date"] = _parse_date(grant_data.get("work_start_date"))
                grant_data["work_end_date"] = _parse_date(grant_data.get("work_end_date"))
                grant_data["grant_date"] = _parse_date(grant_data.get("grant_date"))
                grant_data.pop("id", None)
                grant_data.pop("created_at", None)
                grant_data.pop("updated_at", None)
                grant = Grant(**grant_data)
                self.db.add(grant)
                restored_count += 1

            # שחזור מעסיק נוכחי
            employer_data = data.get("current_employer")
            if employer_data:
                # יצירת עותק כדי לא לשנות את המקור
                employer_data = dict(employer_data)
                
                # המרת תאריכים מ-string ל-date
                employer_data["start_date"] = _parse_date(employer_data.get("start_date"))
                employer_data["end_date"] = _parse_date(employer_data.get("end_date"))
                employer_data["last_update"] = _parse_date(employer_data.get("last_update"))
                
                # הסרת שדות שלא צריך לשחזר
                employer_data.pop("created_at", None)
                employer_data.pop("updated_at", None)
                
                employer = CurrentEmployer(**employer_data)
                self.db.add(employer)
                self.db.flush()  # כדי לקבל ID
                restored_count += 1
                
                # שחזור מענקים
                for grant_data in data.get("grants", []):
                    grant_data = dict(grant_data)
                    grant_data["employer_id"] = employer.id
                    grant_data["grant_date"] = _parse_date(grant_data.get("grant_date"))
                    grant_data["plan_start_date"] = _parse_date(grant_data.get("plan_start_date"))
                    
                    # המרת grant_type מ-string ל-enum
                    if grant_data.get("grant_type") and isinstance(grant_data["grant_type"], str):
                        from app.models.current_employment.enums import GrantType
                        grant_data["grant_type"] = GrantType(grant_data["grant_type"])
                    
                    grant_data.pop("created_at", None)
                    grant_data.pop("updated_at", None)
                    grant = EmployerGrant(**grant_data)
                    self.db.add(grant)
                    restored_count += 1
            
            # שחזור עזיבת עבודה
            termination_data = data.get("termination_event")
            if termination_data and employer:
                termination_data = dict(termination_data)
                termination_data["client_id"] = client_id
                termination_data["employment_id"] = employer.id
                termination_data["planned_termination_date"] = _parse_date(
                    termination_data.get("planned_termination_date")
                )
                termination_data["actual_termination_date"] = _parse_date(
                    termination_data.get("actual_termination_date")
                )

                if termination_data.get("reason") and isinstance(
                    termination_data.get("reason"), str
                ):
                    try:
                        from app.models.termination_event import TerminationReason

                        termination_data["reason"] = TerminationReason(
                            termination_data["reason"]
                        )
                    except Exception:
                        termination_data["reason"] = None

                termination_data.pop("id", None)
                termination_data.pop("created_at", None)
                termination_data.pop("updated_at", None)

                termination = TerminationEvent(**termination_data)
                self.db.add(termination)
                restored_count += 1
            
            # שחזור קיבוע זכויות
            fixation_data = data.get("fixation_result")
            if fixation_data:
                fixation_data = dict(fixation_data)
                fixation_data["created_at"] = _parse_datetime(fixation_data.get("created_at"))
                fixation = FixationResult(**fixation_data)
                self.db.add(fixation)
                restored_count += 1
            
            # לאחר שיחזור כל הנתונים, נעדכן את תאריך תחילת הקצבה של הלקוח לפי הקצבאות
            effective_pension_start_date = compute_pension_start_date_from_funds(self.db, client)
            client.pension_start_date = effective_pension_start_date
            self.db.add(client)

            self.db.flush()
            self.db.commit()
            
            logger.info(f"  ✅ Restored {restored_count} items")
            
            return {
                "success": True,
                "deleted_count": deleted_count,
                "restored_count": restored_count,
                "message": f"המצב שוחזר בהצלחה: נמחקו {deleted_count} פריטים, שוחזרו {restored_count} פריטים"
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"  ❌ Restore failed: {e}")
            raise
    
    # Helper methods לאיסוף נתונים
    
    def _collect_pension_funds(self, client_id: int) -> list:
        """איסוף כל הקצבאות"""
        items = self.db.query(PensionFund).filter(
            PensionFund.client_id == client_id
        ).all()
        
        return [self._serialize_pension_fund(pf) for pf in items]
    
    def _collect_capital_assets(self, client_id: int) -> list:
        """איסוף כל נכסי ההון"""
        items = self.db.query(CapitalAsset).filter(
            CapitalAsset.client_id == client_id
        ).all()
        
        return [self._serialize_capital_asset(ca) for ca in items]
    
    def _collect_additional_incomes(self, client_id: int) -> list:
        """איסוף כל ההכנסות הנוספות"""
        items = self.db.query(AdditionalIncome).filter(
            AdditionalIncome.client_id == client_id
        ).all()
        
        return [self._serialize_additional_income(ai) for ai in items]
    
    def _collect_current_employer(self, client_id: int) -> Optional[Dict]:
        """איסוף מעסיק נוכחי"""
        employer = self.db.query(CurrentEmployer).filter(
            CurrentEmployer.client_id == client_id
        ).first()
        
        return self._serialize_current_employer(employer) if employer else None
    
    def _collect_grants(self, client_id: int) -> list:
        """איסוף כל המענקים"""
        employers = self.db.query(CurrentEmployer).filter(
            CurrentEmployer.client_id == client_id
        ).all()
        
        grants = []
        for employer in employers:
            employer_grants = self.db.query(EmployerGrant).filter(
                EmployerGrant.employer_id == employer.id
            ).all()
            grants.extend([self._serialize_grant(g) for g in employer_grants])
        
        return grants
    
    def _collect_legacy_grants(self, client_id: int) -> list:
        """איסוף מענקים מטבלת grant (מערכת קיבוע זכויות הישנה)"""
        items = self.db.query(Grant).filter(
            Grant.client_id == client_id
        ).all()

        return [g.to_dict() for g in items]
    
    def _collect_termination_event(self, client_id: int) -> Optional[Dict]:
        """איסוף עזיבת עבודה"""
        termination = self.db.query(TerminationEvent).filter(
            TerminationEvent.client_id == client_id
        ).first()
        
        return self._serialize_termination_event(termination) if termination else None
    
    def _collect_fixation_result(self, client_id: int) -> Optional[Dict]:
        """איסוף קיבוע זכויות"""
        fixation = self.db.query(FixationResult).filter(
            FixationResult.client_id == client_id
        ).first()
        
        return self._serialize_fixation_result(fixation) if fixation else None
    
    # Serialization methods
    
    def _serialize_pension_fund(self, pf: PensionFund) -> Dict:
        """ממיר PensionFund לדיקשנרי"""
        return {
            "client_id": pf.client_id,
            "fund_name": pf.fund_name,
            "fund_type": pf.fund_type,
            "input_mode": pf.input_mode,
            "balance": float(pf.balance) if pf.balance else None,
            "annuity_factor": float(pf.annuity_factor) if pf.annuity_factor else None,
            "pension_amount": float(pf.pension_amount) if pf.pension_amount else None,
            "pension_start_date": pf.pension_start_date.isoformat() if pf.pension_start_date else None,
            "indexation_method": pf.indexation_method,
            "fixed_index_rate": float(pf.fixed_index_rate) if pf.fixed_index_rate else None,
            "indexed_pension_amount": float(pf.indexed_pension_amount) if pf.indexed_pension_amount else None,
            "tax_treatment": pf.tax_treatment,
            "remarks": pf.remarks,
            "deduction_file": pf.deduction_file,
            "conversion_source": pf.conversion_source
        }
    
    def _serialize_capital_asset(self, ca: CapitalAsset) -> Dict:
        """ממיר CapitalAsset לדיקשנרי"""
        return {
            "client_id": ca.client_id,
            "asset_name": ca.asset_name,
            "asset_type": ca.asset_type,
            "description": ca.description,
            "current_value": float(ca.current_value),
            "monthly_income": float(ca.monthly_income) if ca.monthly_income else None,
            "annual_return_rate": float(ca.annual_return_rate),
            "payment_frequency": ca.payment_frequency,
            "start_date": ca.start_date.isoformat() if ca.start_date else None,
            "end_date": ca.end_date.isoformat() if ca.end_date else None,
            "indexation_method": ca.indexation_method,
            "fixed_rate": float(ca.fixed_rate) if ca.fixed_rate else None,
            "tax_treatment": ca.tax_treatment,
            "tax_rate": float(ca.tax_rate) if ca.tax_rate else None,
            "spread_years": ca.spread_years,
            "remarks": ca.remarks,
            "conversion_source": ca.conversion_source
        }
    
    def _serialize_additional_income(self, ai: AdditionalIncome) -> Dict:
        """ממיר AdditionalIncome לדיקשנרי"""
        return {
            "client_id": ai.client_id,
            "source_type": ai.source_type,
            "description": ai.description,
            "amount": float(ai.amount),
            "frequency": ai.frequency,
            "start_date": ai.start_date.isoformat() if ai.start_date else None,
            "end_date": ai.end_date.isoformat() if ai.end_date else None,
            "indexation_method": ai.indexation_method,
            "fixed_rate": float(ai.fixed_rate) if ai.fixed_rate else None,
            "tax_treatment": ai.tax_treatment,
            "tax_rate": float(ai.tax_rate) if ai.tax_rate else None,
            "remarks": ai.remarks
        }
    
    def _serialize_current_employer(self, ce: CurrentEmployer) -> Dict:
        """ממיר CurrentEmployer לדיקשנרי"""
        # Use getattr with fallback for compatibility with old/new schema
        start_date = getattr(ce, 'start_date', None) or getattr(ce, 'employment_start_date', None)
        
        return {
            "client_id": ce.client_id,
            "employer_name": ce.employer_name,
            "employer_id_number": getattr(ce, 'employer_id_number', None),
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": ce.end_date.isoformat() if ce.end_date else None,
            "non_continuous_periods": getattr(ce, 'non_continuous_periods', None) or [],
            "last_salary": float(ce.last_salary) if ce.last_salary else None,
            "average_salary": float(getattr(ce, 'average_salary', 0)) if getattr(ce, 'average_salary', None) else None,
            "severance_accrued": float(getattr(ce, 'severance_accrued', 0)) if getattr(ce, 'severance_accrued', None) else None,
            "other_grants": getattr(ce, 'other_grants', None) or {},
            "tax_withheld": float(getattr(ce, 'tax_withheld', 0)) if getattr(ce, 'tax_withheld', None) else None,
            "grant_installments": getattr(ce, 'grant_installments', None) or [],
            "active_continuity": ce.active_continuity.value if getattr(ce, 'active_continuity', None) else None,
            "continuity_years": float(getattr(ce, 'continuity_years', 0)),
            "pre_retirement_pension": float(getattr(ce, 'pre_retirement_pension', 0)) if getattr(ce, 'pre_retirement_pension', None) else None,
            "existing_deductions": getattr(ce, 'existing_deductions', None) or {},
            "last_update": ce.last_update.isoformat() if getattr(ce, 'last_update', None) else None,
            "indexed_severance": float(getattr(ce, 'indexed_severance', 0)) if getattr(ce, 'indexed_severance', None) else None,
            "severance_exemption_cap": float(getattr(ce, 'severance_exemption_cap', 0)) if getattr(ce, 'severance_exemption_cap', None) else None,
            "severance_exempt": float(getattr(ce, 'severance_exempt', 0)) if getattr(ce, 'severance_exempt', None) else None,
            "severance_taxable": float(getattr(ce, 'severance_taxable', 0)) if getattr(ce, 'severance_taxable', None) else None,
            "severance_tax_due": float(getattr(ce, 'severance_tax_due', 0)) if getattr(ce, 'severance_tax_due', None) else None
        }
    
    def _serialize_grant(self, grant: EmployerGrant) -> Dict:
        """ממיר EmployerGrant לדיקשנרי"""
        return {
            "grant_type": grant.grant_type.value if grant.grant_type else None,
            "grant_amount": float(grant.grant_amount),
            "grant_date": grant.grant_date.isoformat() if grant.grant_date else None,
            "plan_name": grant.plan_name,
            "plan_start_date": grant.plan_start_date.isoformat() if grant.plan_start_date else None,
            "product_type": grant.product_type,
            "tax_withheld": float(grant.tax_withheld) if grant.tax_withheld else None,
            "grant_exempt": float(grant.grant_exempt) if grant.grant_exempt else None,
            "grant_taxable": float(grant.grant_taxable) if grant.grant_taxable else None,
            "tax_due": float(grant.tax_due) if grant.tax_due else None,
            "indexed_amount": float(grant.indexed_amount) if grant.indexed_amount else None
        }
    
    def _serialize_termination_event(self, te: TerminationEvent) -> Dict:
        """ממיר TerminationEvent לדיקשנרי"""
        return {
            "client_id": te.client_id,
            "planned_termination_date": te.planned_termination_date.isoformat() if te.planned_termination_date else None,
            "actual_termination_date": te.actual_termination_date.isoformat() if te.actual_termination_date else None,
            "reason": te.reason,
            "severance_basis_nominal": float(te.severance_basis_nominal) if te.severance_basis_nominal else None,
            "package_paths": te.package_paths
        }
    
    def _serialize_fixation_result(self, fr: FixationResult) -> Dict:
        """ממיר FixationResult לדיקשנרי"""
        return {
            "client_id": fr.client_id,
            "created_at": fr.created_at.isoformat() if fr.created_at else None,
            "exempt_capital_remaining": float(fr.exempt_capital_remaining) if fr.exempt_capital_remaining else 0.0,
            "used_commutation": float(fr.used_commutation) if fr.used_commutation else 0.0,
            "raw_payload": fr.raw_payload,
            "raw_result": fr.raw_result,
            "notes": fr.notes
        }
