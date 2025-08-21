"""Service for Capital Asset calculations and management."""

import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
from dateutil.relativedelta import relativedelta

from sqlalchemy.orm import Session

from app.models.capital_asset import CapitalAsset, PaymentFrequency, IndexationMethod, TaxTreatment
from app.providers.tax_params import TaxParamsProvider, InMemoryTaxParamsProvider
from app.schemas.capital_asset import CapitalAssetCashflowItem

logger = logging.getLogger(__name__)


class CapitalAssetService:
    """Service for capital asset calculations."""

    def __init__(self, tax_params_provider: Optional[TaxParamsProvider] = None):
        """Initialize the service with tax parameters provider."""
        self.tax_params_provider = tax_params_provider or InMemoryTaxParamsProvider()

    def calculate_monthly_return(self, asset: CapitalAsset) -> Decimal:
        """Calculate monthly return based on frequency."""
        annual_return = asset.current_value * asset.annual_return_rate
        
        if asset.payment_frequency == PaymentFrequency.MONTHLY:
            return annual_return / Decimal('12')
        elif asset.payment_frequency == PaymentFrequency.QUARTERLY:
            return annual_return / Decimal('4')
        elif asset.payment_frequency == PaymentFrequency.ANNUALLY:
            return annual_return
        else:
            raise ValueError(f"Unsupported frequency: {asset.payment_frequency}")

    def apply_indexation(
        self, 
        base_return: Decimal, 
        asset: CapitalAsset, 
        target_date: date,
        reference_date: Optional[date] = None
    ) -> Decimal:
        """Apply indexation to the base return."""
        if asset.indexation_method == IndexationMethod.NONE:
            return base_return

        start_date = reference_date or asset.start_date
        years_diff = self._calculate_years_between(start_date, target_date)
        
        if years_diff <= 0:
            return base_return

        if asset.indexation_method == IndexationMethod.FIXED:
            if asset.fixed_rate is None:
                raise ValueError("Fixed rate is required for fixed indexation")
            indexation_factor = (Decimal('1') + asset.fixed_rate) ** years_diff
            return base_return * indexation_factor

        elif asset.indexation_method == IndexationMethod.CPI:
            # Get CPI data from tax params provider
            tax_params = self.tax_params_provider.get_params()
            cpi_factor = self._calculate_cpi_factor(
                tax_params.cpi_series, start_date, target_date
            )
            return base_return * cpi_factor

        else:
            raise ValueError(f"Unsupported indexation method: {asset.indexation_method}")

    def calculate_tax(self, gross_return: Decimal, asset: CapitalAsset) -> Decimal:
        """Calculate tax on the gross return."""
        if asset.tax_treatment == TaxTreatment.EXEMPT:
            return Decimal('0')
        
        elif asset.tax_treatment == TaxTreatment.FIXED_RATE:
            if asset.tax_rate is None:
                raise ValueError("Tax rate is required for fixed rate tax")
            return gross_return * asset.tax_rate
        
        elif asset.tax_treatment == TaxTreatment.TAXABLE:
            # For capital gains, typically lower tax rate
            # This can be enhanced with more sophisticated tax calculations
            tax_params = self.tax_params_provider.get_params()
            # Apply capital gains tax rate (simplified)
            return gross_return * Decimal('0.25')  # 25% capital gains rate as example
        
        else:
            raise ValueError(f"Unsupported tax treatment: {asset.tax_treatment}")

    def project_cashflow(
        self,
        asset: CapitalAsset,
        start_date: date,
        end_date: date,
        reference_date: Optional[date] = None
    ) -> List[CapitalAssetCashflowItem]:
        """Project cashflow for the capital asset."""
        logger.debug(f"Projecting cashflow for asset {asset.id} from {start_date} to {end_date}")
        
        cashflow_items = []
        current_date = self._align_to_first_of_month(max(start_date, asset.start_date))
        
        # Determine actual end date
        actual_end_date = end_date
        if asset.end_date:
            actual_end_date = min(end_date, asset.end_date)

        # Calculate payment intervals based on frequency
        payment_interval = self._get_payment_interval(asset.payment_frequency)
        
        while current_date <= actual_end_date:
            # Check if this is a payment date
            if self._is_payment_date(current_date, asset.start_date, asset.payment_frequency):
                # Calculate base return for this period
                base_return = self._calculate_period_return(asset, current_date)
                
                # Apply indexation
                indexed_return = self.apply_indexation(
                    base_return, asset, current_date, reference_date
                )
                
                # Calculate tax
                tax_amount = self.calculate_tax(indexed_return, asset)
                net_return = indexed_return - tax_amount
                
                # Create cashflow item
                cashflow_item = CapitalAssetCashflowItem(
                    date=current_date,
                    gross_return=indexed_return,
                    tax_amount=tax_amount,
                    net_return=net_return,
                    asset_type=asset.asset_type,
                    description=asset.description
                )
                cashflow_items.append(cashflow_item)
            
            # Move to next month
            current_date = self._add_months(current_date, 1)
        
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
        """Generate combined cashflow for all client's capital assets."""
        logger.debug(f"Generating combined capital asset cashflow for client {client_id}")
        
        # Get all capital assets for the client
        assets = db_session.query(CapitalAsset).filter(
            CapitalAsset.client_id == client_id
        ).all()
        
        if not assets:
            logger.debug("No capital assets found for client")
            return []
        
        # Generate cashflow for each asset
        all_cashflow_items = []
        for asset in assets:
            cashflow_items = self.project_cashflow(
                asset, start_date, end_date, reference_date
            )
            all_cashflow_items.extend(cashflow_items)
        
        # Aggregate by date
        aggregated_cashflow = {}
        for item in all_cashflow_items:
            date_key = item.date
            if date_key not in aggregated_cashflow:
                aggregated_cashflow[date_key] = {
                    'date': date_key,
                    'gross_return': Decimal('0'),
                    'tax_amount': Decimal('0'),
                    'net_return': Decimal('0')
                }
            
            aggregated_cashflow[date_key]['gross_return'] += item.gross_return
            aggregated_cashflow[date_key]['tax_amount'] += item.tax_amount
            aggregated_cashflow[date_key]['net_return'] += item.net_return
        
        # Convert to sorted list
        result = sorted(aggregated_cashflow.values(), key=lambda x: x['date'])
        logger.debug(f"Generated {len(result)} aggregated cashflow items")
        return result

    def _calculate_period_return(self, asset: CapitalAsset, payment_date: date) -> Decimal:
        """Calculate return for a specific payment period."""
        annual_return = asset.current_value * asset.annual_return_rate
        
        if asset.payment_frequency == PaymentFrequency.MONTHLY:
            return annual_return / Decimal('12')
        elif asset.payment_frequency == PaymentFrequency.QUARTERLY:
            return annual_return / Decimal('4')
        elif asset.payment_frequency == PaymentFrequency.ANNUALLY:
            return annual_return
        else:
            raise ValueError(f"Unsupported frequency: {asset.payment_frequency}")

    def _get_payment_interval(self, frequency: PaymentFrequency) -> int:
        """Get payment interval in months."""
        if frequency == PaymentFrequency.MONTHLY:
            return 1
        elif frequency == PaymentFrequency.QUARTERLY:
            return 3
        elif frequency == PaymentFrequency.ANNUALLY:
            return 12
        else:
            raise ValueError(f"Unsupported frequency: {frequency}")

    def _is_payment_date(self, current_date: date, start_date: date, frequency: PaymentFrequency) -> bool:
        """Check if current date is a payment date based on frequency."""
        if frequency == PaymentFrequency.MONTHLY:
            return True  # Every month
        
        months_diff = (current_date.year - start_date.year) * 12 + (current_date.month - start_date.month)
        
        if frequency == PaymentFrequency.QUARTERLY:
            return months_diff % 3 == 0
        elif frequency == PaymentFrequency.ANNUALLY:
            return months_diff % 12 == 0
        
        return False

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
