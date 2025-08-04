from datetime import date
from sqlalchemy.orm import Session
from app.models import Client, Employment
from app.providers.tax_params import TaxParamsProvider
from app.schemas.scenario import ScenarioIn, ScenarioOut
from app.calculation.seniority import calc_seniority_years
from app.calculation.indexation import index_factor, index_amount
from app.calculation.grants import calc_grant_components
from app.calculation.pensions import calc_monthly_pension_from_capital
from app.calculation.cashflow import make_simple_cashflow

class CalculationEngine:
    def __init__(self, db: Session, tax_provider: TaxParamsProvider):
        self.db = db
        self.tax_provider = tax_provider

    def run(self, client_id: int, scenario: ScenarioIn) -> ScenarioOut:
        client = self.db.query(Client).get(client_id)
        if not client:
            raise ValueError("לקוח לא נמצא")
        if not client.is_active:
            raise ValueError("הלקוח אינו פעיל")

        # נאתר employment נוכחי לצורך ותק (או נבחר ראשון אם אין flag)
        employment = (self.db.query(Employment)
                      .filter(Employment.client_id==client_id, Employment.is_current==True)
                      .first())
        if not employment:
            # fallback: אין נוכחי – ניקח היסטורי ראשון (פשטני)
            employment = (self.db.query(Employment)
                          .filter(Employment.client_id==client_id)
                          .order_by(Employment.start_date.asc())
                          .first())
        if not employment:
            raise ValueError("אין נתוני תעסוקה לחישוב")

        params = self.tax_provider.get_params()
        # 1) ותק
        end_for_seniority = scenario.planned_termination_date or date.today()
        seniority = calc_seniority_years(employment.start_date, end_for_seniority)

        # 2) הצמדה (דוגמה: מצמידים מענק בסיס של 100,000 מתאריך תחילת עבודה לאנ. החישוב)
        base_amount = 100_000.0
        f = index_factor(params, employment.start_date, end_for_seniority)
        indexed_amount = index_amount(base_amount, f)

        # 3) מענק/מס
        exempt, taxable, tax = calc_grant_components(indexed_amount, params)
        grant_net = round(indexed_amount - tax, 2)

        # 4) קצבה (פשטני: ממירים את הנטו להון → פנסיה חודשית)
        pension_monthly = calc_monthly_pension_from_capital(grant_net, params)

        # 5) תזרים פשטני: 12 חודשים קדימה
        income = scenario.other_incomes_monthly or pension_monthly
        expense = scenario.monthly_expenses or 0.0
        cashflow = make_simple_cashflow(end_for_seniority, 12, income, expense)

        return ScenarioOut(
            seniority_years=seniority,
            grant_gross=round(indexed_amount, 2),
            grant_exempt=exempt,
            grant_tax=tax,
            grant_net=grant_net,
            pension_monthly=pension_monthly,
            indexation_factor=f,
            cashflow=cashflow,
        )
