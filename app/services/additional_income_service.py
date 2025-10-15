"""Service for Additional Income calculations and management."""

import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
from dateutil.relativedelta import relativedelta

from sqlalchemy.orm import Session

from app.models.additional_income import AdditionalIncome, PaymentFrequency, IndexationMethod, TaxTreatment
from app.providers.tax_params import TaxParamsProvider, InMemoryTaxParamsProvider
from app.schemas.additional_income import AdditionalIncomeCashflowItem

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

    def calculate_tax(self, gross_amount: Decimal, income: AdditionalIncome) -> Decimal:
        """Calculate tax on the gross amount."""
        if income.tax_treatment == TaxTreatment.EXEMPT:
            return Decimal('0')
        
        elif income.tax_treatment == TaxTreatment.FIXED_RATE:
            if income.tax_rate is None:
                raise ValueError("Tax rate is required for fixed rate tax")
            return gross_amount * income.tax_rate
        
        elif income.tax_treatment == TaxTreatment.TAXABLE:
            # For now, apply a basic tax calculation
            # This can be enhanced with more sophisticated tax brackets
            tax_params = self.tax_params_provider.get_params()
            # Apply basic marginal tax rate (simplified)
            return gross_amount * Decimal('0.31')  # 31% marginal rate as example
        
        else:
            raise ValueError(f"Unsupported tax treatment: {income.tax_treatment}")

    def project_cashflow(
        self,
        income: AdditionalIncome,
        start_date: date,
        end_date: date,
        reference_date: Optional[date] = None
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
                tax_amount = self.calculate_tax(indexed_amount, income)
                net_amount = indexed_amount - tax_amount
            else:
                # No payment this month
                indexed_amount = Decimal('0')
                tax_amount = Decimal('0')
                net_amount = Decimal('0')
            
            # Create cashflow item (even for zero months, for consistency)
            cashflow_item = AdditionalIncomeCashflowItem(
                date=current_date,
                gross_amount=indexed_amount,
                tax_amount=tax_amount,
                net_amount=net_amount,
                source_type=income.source_type,
                description=income.description
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
        
        if not incomes:
            logger.debug("No additional incomes found for client")
            return []
        
        # Generate cashflow for each income
        all_cashflow_items = []
        for income in incomes:
            cashflow_items = self.project_cashflow(
                income, start_date, end_date, reference_date
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
                    'net_amount': Decimal('0')
                }
            
            aggregated_cashflow[date_key]['gross_amount'] += item.gross_amount
            aggregated_cashflow[date_key]['tax_amount'] += item.tax_amount
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
