"""
Employment Service Module
מודול שירותי העסקה
"""
from typing import Optional
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.client import Client
from app.models.current_employer import CurrentEmployer
from app.schemas.current_employer import CurrentEmployerCreate, CurrentEmployerUpdate


class EmploymentService:
    """שירות ניהול העסקה"""
    
    def __init__(self, db: Session):
        """
        אתחול שירות העסקה
        
        Args:
            db: סשן מסד נתונים
        """
        self.db = db
    
    def create_or_update_employer(
        self,
        client_id: int,
        employer_data: CurrentEmployerCreate
    ) -> CurrentEmployer:
        """
        יצירה או עדכון מעסיק נוכחי
        
        Args:
            client_id: מזהה לקוח
            employer_data: נתוני מעסיק
            
        Returns:
            CurrentEmployer - מעסיק נוכחי
            
        Raises:
            ValueError: אם הלקוח לא נמצא
        """
        # בדיקת קיום לקוח
        client = self.db.query(Client).filter(Client.id == client_id).first()
        if not client:
            raise ValueError("לקוח לא נמצא")
        
        # בדיקה אם מעסיק נוכחי כבר קיים - קבלת האחרון
        ce = self.db.scalar(
            select(CurrentEmployer)
            .where(CurrentEmployer.client_id == client_id)
            .order_by(CurrentEmployer.updated_at.desc(), CurrentEmployer.id.desc())
        )
        
        if ce:
            # עדכון מעסיק קיים
            return self._update_existing_employer(ce, employer_data)
        else:
            # יצירת מעסיק חדש
            return self._create_new_employer(client_id, employer_data)
    
    def _update_existing_employer(
        self,
        ce: CurrentEmployer,
        employer_data: CurrentEmployerCreate
    ) -> CurrentEmployer:
        """
        עדכון מעסיק קיים
        
        Args:
            ce: מעסיק נוכחי קיים
            employer_data: נתונים חדשים
            
        Returns:
            CurrentEmployer מעודכן
        """
        # חשוב! לא לדרוס עם None
        data = employer_data.model_dump(exclude_none=True)
        
        # מיפוי שדות Frontend ל-DB
        if 'monthly_salary' in data and data['monthly_salary'] is not None:
            data['last_salary'] = data['monthly_salary']
            
        if 'severance_balance' in data and data['severance_balance'] is not None:
            data['severance_accrued'] = data['severance_balance']
        
        # הסרת שדות שלא קיימים בסכמת DB הנוכחית
        data.pop('monthly_salary', None)
        data.pop('severance_balance', None)
        
        # עדכון שדות
        for k, v in data.items():
            setattr(ce, k, v)
        ce.last_update = date.today()  # תמיד עדכון לפי שרת
        
        self.db.add(ce)
        self.db.commit()
        self.db.refresh(ce)
        return ce
    
    def _create_new_employer(
        self,
        client_id: int,
        employer_data: CurrentEmployerCreate
    ) -> CurrentEmployer:
        """
        יצירת מעסיק חדש
        
        Args:
            client_id: מזהה לקוח
            employer_data: נתוני מעסיק
            
        Returns:
            CurrentEmployer חדש
        """
        # יצירה חדשה מהנתונים - מיפוי שדות Frontend ל-DB
        data = employer_data.model_dump(exclude_none=True)
        
        # מיפוי שדות
        if 'monthly_salary' in data and data['monthly_salary'] is not None:
            data['last_salary'] = data['monthly_salary']
            
        if 'severance_balance' in data and data['severance_balance'] is not None:
            data['severance_accrued'] = data['severance_balance']
        
        # הסרת שדות שלא קיימים בסכמת DB הנוכחית
        data.pop('monthly_salary', None)
        data.pop('severance_balance', None)
        
        ce = CurrentEmployer(
            client_id=client_id,
            **data
        )
        ce.last_update = date.today()
        
        self.db.add(ce)
        self.db.commit()
        self.db.refresh(ce)
        return ce
    
    def get_employer(self, client_id: int) -> Optional[CurrentEmployer]:
        """
        קבלת מעסיק נוכחי ללקוח
        
        Args:
            client_id: מזהה לקוח
            
        Returns:
            CurrentEmployer או None אם לא נמצא
            
        Raises:
            ValueError: אם הלקוח לא נמצא
        """
        # בדיקת קיום לקוח
        client = self.db.get(Client, client_id)
        if client is None:
            raise ValueError("לקוח לא נמצא")
        
        # שליפת המעסיק הנוכחי (האחרון)
        ce = self.db.scalar(
            select(CurrentEmployer)
            .where(CurrentEmployer.client_id == client_id)
            .order_by(CurrentEmployer.updated_at.desc(), CurrentEmployer.id.desc())
        )
        
        if ce is None:
            raise ValueError("אין מעסיק נוכחי רשום ללקוח")
        
        return ce
    
    def update_employer_end_date(
        self,
        employer: CurrentEmployer,
        end_date: date
    ) -> CurrentEmployer:
        """
        עדכון תאריך סיום העסקה
        
        Args:
            employer: מעסיק נוכחי
            end_date: תאריך סיום
            
        Returns:
            CurrentEmployer מעודכן
        """
        employer.end_date = end_date
        self.db.add(employer)
        self.db.flush()
        return employer
    
    def clear_employer_end_date(self, employer: CurrentEmployer) -> CurrentEmployer:
        """
        ביטול תאריך סיום העסקה (ביטול עזיבה)
        
        Args:
            employer: מעסיק נוכחי
            
        Returns:
            CurrentEmployer מעודכן
        """
        employer.end_date = None
        self.db.add(employer)
        return employer
