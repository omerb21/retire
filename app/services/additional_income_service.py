"""Service for Additional Income calculations and management."""

import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from dateutil.relativedelta import relativedelta

from sqlalchemy.orm import Session

from app.models.additional_income import AdditionalIncome, PaymentFrequency, IndexationMethod, TaxTreatment
from app.models.client import Client
from app.providers.tax_params import TaxParamsProvider, InMemoryTaxParamsProvider
from app.schemas.additional_income import AdditionalIncomeCashflowItem
from app.services.tax_calculator import TaxCalculator

logger = logging.getLogger(__name__)


class AdditionalIncomeService:
    """Service for additional income calculations."""

    def __init__(self, tax_params_provider: Optional[TaxParamsProvider] = None):
        """Initialize the service with tax parameters provider."""
        self.tax_params_provider = tax_params_provider or InMemoryTaxParamsProvider()

    def calculate_monthly_amount(self, income: AdditionalIncome) -> Decimal:
        """Calculate monthly amount based on frequency."""
        if income.frequency == PaymentFrequency.MONTHLY:
            return income.amount
        elif income.frequency == PaymentFrequency.QUARTERLY:
            return income.amount / Decimal('3')
        elif income.frequency == PaymentFrequency.ANNUALLY:
            return income.amount / Decimal('12')
        else:
            raise ValueError(f"Unsupported frequency: {income.frequency}")

    def apply_indexation(
        self, 
        base_amount: Decimal, 
        income: AdditionalIncome, 
        target_date: date,
        reference_date: Optional[date] = None
    ) -> Decimal:
        """Apply indexation to the base amount."""
        if income.indexation_method == IndexationMethod.NONE:
            return base_amount

        start_date = reference_date or income.start_date
        years_diff = self._calculate_years_between(start_date, target_date)
        
        if years_diff <= 0:
            return base_amount

        if income.indexation_method == IndexationMethod.FIXED:
            if income.fixed_rate is None:
                raise ValueError("Fixed rate is required for fixed indexation")
            indexation_factor = (Decimal('1') + income.fixed_rate) ** years_diff
            return base_amount * indexation_factor

        elif income.indexation_method == IndexationMethod.CPI:
            # Get CPI data from tax params provider
            tax_params = self.tax_params_provider.get_params()
            cpi_factor = self._calculate_cpi_factor(
                tax_params.cpi_series, start_date, target_date
            )
            return base_amount * cpi_factor

        else:
            raise ValueError(f"Unsupported indexation method: {income.indexation_method}")

    def calculate_tax(
        self, 
        gross_amount: Decimal, 
        income: AdditionalIncome,
        client: Optional[Client] = None,
        calculation_date: Optional[date] = None
    ) -> Tuple[Decimal, bool]:
        """Calculate tax on the gross amount based on income type and client age.
        
        Returns:
            Tuple of (tax_amount, should_include_in_total_tax)
            - tax_amount: המס המחושב
            - should_include_in_total_tax: האם לכלול את המס בסה"כ המס בתזרים
        """
        if income.tax_treatment == TaxTreatment.EXEMPT:
            return Decimal('0'), False
        
        elif income.tax_treatment == TaxTreatment.FIXED_RATE:
            if income.tax_rate is None:
                raise ValueError("Tax rate is required for fixed rate tax")
            # tax_rate is now in percentage (0-99), convert to decimal
            tax_amount = gross_amount * (income.tax_rate / Decimal('100'))
            # ⚠️ CRITICAL: מס קבוע לא נכלל בסה"כ המס בתזרים - זה מס שמוצג למידע בלבד
            return tax_amount, False
        
        elif income.tax_treatment == TaxTreatment.TAXABLE:
            # חישוב מס מתקדם לפי סוג הכנסה
            annual_amount = float(gross_amount * 12)  # המרה לסכום שנתי
            
            # בדיקת גיל פרישה
            is_retired = False
            if client and calculation_date:
                client_age = client.get_age(calculation_date)
                is_retired = client_age >= 67
            
            tax_calculator = TaxCalculator()
            
            if income.source_type == "salary":
                # שכיר: מס הכנסה + ביטוח לאומי + מס בריאות (עד גיל פרישה)
                income_tax, _ = tax_calculator.calculate_income_tax(annual_amount)
                
                if is_retired:
                    # אחרי פרישה - רק מס הכנסה
                    total_tax = income_tax
                else:
                    # לפני פרישה - מס + ביטוח לאומי + מס בריאות
                    ni_tax = tax_calculator.calculate_national_insurance(annual_amount)
                    health_tax = tax_calculator.calculate_health_tax(annual_amount)
                    total_tax = income_tax + ni_tax + health_tax
                
                # המרה חזרה לחודשי
                return Decimal(str(total_tax / 12)), True
            
            elif income.source_type == "business":
                # עסק: מס הכנסה + ביטוח לאומי (ללא מס בריאות)
                income_tax, _ = tax_calculator.calculate_income_tax(annual_amount)
                ni_tax = tax_calculator.calculate_national_insurance(annual_amount)
                total_tax = income_tax + ni_tax
                
                # המרה חזרה לחודשי
                return Decimal(str(total_tax / 12)), True
            
            else:
                # סוגי הכנסה אחרים - רק מס הכנסה
                income_tax, _ = tax_calculator.calculate_income_tax(annual_amount)
                return Decimal(str(income_tax / 12)), True
        
        else:
            raise ValueError(f"Unsupported tax treatment: {income.tax_treatment}")

    def project_cashflow(
        self,
        income: AdditionalIncome,
        start_date: date,
        end_date: date,
        reference_date: Optional[date] = None,
        client: Optional[Client] = None
    ) -> List[AdditionalIncomeCashflowItem]:
        """Project cashflow for the income source."""
        logger.debug(f"Projecting cashflow for income {income.id} from {start_date} to {end_date}")
        
        cashflow_items = []
        current_date = self._align_to_first_of_month(max(start_date, income.start_date))
        
        # Determine actual end date
        actual_end_date = end_date
        if income.end_date:
            actual_end_date = min(end_date, income.end_date)

        # Determine payment interval based on frequency
        if income.frequency == PaymentFrequency.MONTHLY:
            payment_interval = 1  # Every month
            payment_amount = income.amount
        elif income.frequency == PaymentFrequency.QUARTERLY:
            payment_interval = 3  # Every 3 months
            payment_amount = income.amount
        elif income.frequency == PaymentFrequency.ANNUALLY:
            payment_interval = 12  # Every 12 months
            payment_amount = income.amount
        else:
            raise ValueError(f"Unsupported frequency: {income.frequency}")
        
        logger.info(f"🔵 Income frequency={income.frequency}, interval={payment_interval}, amount={payment_amount}")
        
        month_counter = 0
        while current_date <= actual_end_date:
            # Check if this month should have a payment
            should_pay = (month_counter % payment_interval) == 0
            
            if should_pay:
                # Apply indexation
                indexed_amount = self.apply_indexation(
                    payment_amount, income, current_date, reference_date
                )
                
                # Calculate tax
                tax_amount, include_in_total = self.calculate_tax(indexed_amount, income, client, current_date)
                net_amount = indexed_amount - tax_amount
            else:
                # No payment this month
                indexed_amount = Decimal('0')
                tax_amount = Decimal('0')
                net_amount = Decimal('0')
                include_in_total = True  # Default for zero months
            
            # Create cashflow item (even for zero months, for consistency)
            cashflow_item = AdditionalIncomeCashflowItem(
                date=current_date,
                gross_amount=indexed_amount,
                tax_amount=tax_amount,
                net_amount=net_amount,
                source_type=income.source_type,
                description=income.description,
                include_in_total_tax=include_in_total
            )
            cashflow_items.append(cashflow_item)
            
            # Move to next month
            current_date = self._add_months(current_date, 1)
            month_counter += 1
        
        logger.debug(f"Generated {len(cashflow_items)} cashflow items")
        return cashflow_items

    def generate_combined_cashflow(
        self,
        db_session: Session,
        client_id: int,
        start_date: date,
        end_date: date,
        reference_date: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        """Generate combined cashflow for all client's additional incomes."""
        logger.debug(f"Generating combined additional income cashflow for client {client_id}")
        
        # Get all additional incomes for the client
        incomes = db_session.query(AdditionalIncome).filter(
            AdditionalIncome.client_id == client_id
        ).all()
        
        # Get client details for age calculation
        client = db_session.query(Client).filter(Client.id == client_id).first()
        
        if not incomes:
            logger.debug("No additional incomes found for client")
            return []
        
        # Generate cashflow for each income
        all_cashflow_items = []
        for income in incomes:
            cashflow_items = self.project_cashflow(
                income, start_date, end_date, reference_date, client
            )
            all_cashflow_items.extend(cashflow_items)
        
        # Aggregate by date
        aggregated_cashflow = {}
        for item in all_cashflow_items:
            date_key = item.date
            if date_key not in aggregated_cashflow:
                aggregated_cashflow[date_key] = {
                    'date': date_key,
                    'gross_amount': Decimal('0'),
                    'tax_amount': Decimal('0'),
                    'tax_amount_for_total': Decimal('0'),  # רק מסים שצריכים להיכלל בסה"כ
                    'net_amount': Decimal('0')
                }
            
            aggregated_cashflow[date_key]['gross_amount'] += item.gross_amount
            aggregated_cashflow[date_key]['tax_amount'] += item.tax_amount
            # רק מסים שצריכים להיכלל בסה"כ המס
            if item.include_in_total_tax:
                aggregated_cashflow[date_key]['tax_amount_for_total'] += item.tax_amount
            aggregated_cashflow[date_key]['net_amount'] += item.net_amount
        
        # Convert to sorted list
        result = sorted(aggregated_cashflow.values(), key=lambda x: x['date'])
        logger.debug(f"Generated {len(result)} aggregated cashflow items")
        return result

    def _calculate_years_between(self, start_date: date, end_date: date) -> int:
        """Calculate full years between two dates."""
        if end_date <= start_date:
            return 0
        
        years = end_date.year - start_date.year
        if (end_date.month, end_date.day) < (start_date.month, start_date.day):
            years -= 1
        
        return max(0, years)

    def _calculate_cpi_factor(
        self, 
        cpi_series: Dict[int, Decimal], 
        start_date: date, 
        end_date: date
    ) -> Decimal:
        """Calculate CPI indexation factor between two dates."""
        start_year = start_date.year
        end_year = end_date.year
        
        if start_year == end_year or start_year not in cpi_series or end_year not in cpi_series:
            return Decimal('1')
        
        start_cpi = cpi_series[start_year]
        end_cpi = cpi_series[end_year]
        
        if start_cpi <= 0:
            return Decimal('1')
        
        return end_cpi / start_cpi

    def _align_to_first_of_month(self, target_date: date) -> date:
        """Align date to the first day of the month."""
        return date(target_date.year, target_date.month, 1)

    def _add_months(self, target_date: date, months: int) -> date:
        """Add months to a date."""
        return target_date + relativedelta(months=months)
