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

    def _calculate_tax_by_brackets(self, taxable_income: Decimal) -> Decimal:
        """חישוב מס לפי מדרגות מס ישראליות (2024)."""
        if taxable_income <= 0:
            return Decimal('0')
        
        # מדרגות מס ישראליות (בשקלים שנתיים)
        brackets = [
            (Decimal('84120'), Decimal('0.10')),   # עד 84,120 - 10%
            (Decimal('120720'), Decimal('0.14')),  # 84,121-120,720 - 14%
            (Decimal('193800'), Decimal('0.20')),  # 120,721-193,800 - 20%
            (Decimal('269280'), Decimal('0.31')),  # 193,801-269,280 - 31%
            (Decimal('560280'), Decimal('0.35')),  # 269,281-560,280 - 35%
            (Decimal('721560'), Decimal('0.47')),  # 560,281-721,560 - 47%
            (None, Decimal('0.50'))                 # 721,561+ - 50%
        ]
        
        total_tax = Decimal('0')
        remaining_income = taxable_income
        prev_threshold = Decimal('0')
        
        for threshold, rate in brackets:
            if threshold is None:
                # מדרגה אחרונה - כל מה שנשאר
                total_tax += remaining_income * rate
                break
            
            if remaining_income <= 0:
                break
            
            # חישוב הכנסה במדרגה הנוכחית
            income_in_bracket = min(remaining_income, threshold - prev_threshold)
            total_tax += income_in_bracket * rate
            remaining_income -= income_in_bracket
            prev_threshold = threshold
        
        return total_tax
    
    def calculate_spread_tax(
        self, 
        taxable_amount: Decimal, 
        spread_years: int,
        annual_regular_income: Decimal = Decimal('0')
    ) -> Decimal:
        """
        חישוב מס עם פריסה לפי מדרגות.
        
        Args:
            taxable_amount: הסכום הכולל החייב במס
            spread_years: מספר שנות הפריסה
            annual_regular_income: הכנסה שנתית רגילה (אם ידועה)
        
        Returns:
            סכום המס הכולל לאחר פריסה
        """
        if spread_years <= 0:
            raise ValueError("spread_years must be positive")
        
        # חלוקה שווה של הסכום על השנים
        annual_portion = taxable_amount / Decimal(spread_years)
        
        total_spread_tax = Decimal('0')
        
        # חישוב המס לכל שנה
        for year in range(spread_years):
            # מס על הכנסה רגילה + חלק מהמענק
            tax_with_severance = self._calculate_tax_by_brackets(
                annual_regular_income + annual_portion
            )
            
            # מס על הכנסה רגילה בלבד
            tax_without_severance = self._calculate_tax_by_brackets(
                annual_regular_income
            )
            
            # ההפרש = המס על חלק המענק של השנה
            year_tax = tax_with_severance - tax_without_severance
            total_spread_tax += year_tax
            
            logger.debug(
                f"Year {year+1}: regular={annual_regular_income}, "
                f"with_sev={annual_regular_income + annual_portion}, "
                f"tax_diff={year_tax}"
            )
        
        return total_spread_tax

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
            tax_params = self.tax_params_provider.get_params()
            return gross_return * Decimal('0.25')  # 25% capital gains rate
        
        elif asset.tax_treatment == TaxTreatment.TAX_SPREAD:
            # פריסת מס - החישוב המלא יתבצע ב-project_cashflow
            # כאן רק placeholder
            if not asset.spread_years or asset.spread_years <= 0:
                raise ValueError("spread_years is required for tax spread")
            return Decimal('0')  # יחושב ב-project_cashflow
        
        else:
            raise ValueError(f"Unsupported tax treatment: {asset.tax_treatment}")

    def project_cashflow(
        self,
        asset: CapitalAsset,
        start_date: date,
        end_date: date,
        reference_date: Optional[date] = None
    ) -> List[CapitalAssetCashflowItem]:
        """
        Project cashflow for the capital asset.
        
        For TAX_SPREAD treatment:
        - Divides taxable amount equally across spread_years
        - Calculates tax per year using marginal brackets
        - Full accumulated tax is paid in first payment
        - Subsequent years show tax=0 (for display only)
        - Uses Israeli tax brackets (2024)
        
        Args:
            asset: The capital asset to project
            start_date: Start date for projection
            end_date: End date for projection
            reference_date: Optional reference date for indexation
            
        Returns:
            List of cashflow items with dates, amounts, and tax
        """
        logger.debug(f"Projecting cashflow for asset {asset.id} from {start_date} to {end_date}")
        
        cashflow_items = []
        current_date = self._align_to_first_of_month(max(start_date, asset.start_date))
        
        # נכסי הון הם תמיד תשלום חד פעמי - התעלם מ-end_date
        # Determine actual end date (for spread display only)
        actual_end_date = end_date

        # חישוב מס מצטבר לפריסה (אם רלוונטי)
        total_spread_tax = Decimal('0')
        is_tax_spread = asset.tax_treatment == TaxTreatment.TAX_SPREAD
        
        if is_tax_spread and asset.spread_years:
            # הסכום החייב במס הוא current_value של הנכס (לדוגמה מענק פרישה)
            taxable_amount = asset.current_value
            
            # הכנסה שנתית רגילה משוערת (יכול לבוא מהלקוח - כרגע 0)
            # בעתיד ניתן לחשב מקצבאות והכנסות נוספות
            annual_regular_income = Decimal('0')
            
            # אם יש monthly_income, נניח שזו הכנסה שנתית רגילה
            if asset.monthly_income and asset.monthly_income > 0:
                annual_regular_income = asset.monthly_income * Decimal('12')
            
            # חישוב מס לפי מדרגות עם פריסה
            total_spread_tax = self.calculate_spread_tax(
                taxable_amount=taxable_amount,
                spread_years=asset.spread_years,
                annual_regular_income=annual_regular_income
            )
            
            logger.info(
                f"Tax spread calculation: taxable={taxable_amount}, "
                f"years={asset.spread_years}, regular_income={annual_regular_income}, "
                f"total_tax={total_spread_tax}"
            )
        
        # ⚠️ נכס הון הוא תמיד תשלום חד פעמי - לא תזרים מתמשך! ⚠️
        logger.warning(f"🔴 CAPITAL ASSET ONE-TIME PAYMENT: asset_id={asset.id}, type={asset.asset_type}, value={asset.current_value}")
        
        # נכס הון הוא תשלום חד פעמי בתאריך התחלה בלבד
        # יוצרים cashflow item אחד בלבד לתאריך התשלום
        payment_date = self._align_to_first_of_month(asset.start_date)
        
        # חישוב הסכום (current_value הוא הסכום החד פעמי)
        gross_amount = asset.current_value
        
        # Apply indexation if needed (בדרך כלל לא רלוונטי לתשלום חד פעמי)
        indexed_amount = self.apply_indexation(
            gross_amount, asset, payment_date, reference_date
        )
        
        # חישוב מס - לפי סוג המיסוי
        if is_tax_spread:
            # פריסת מס - כל המס המצטבר משולם בפועל
            tax_amount = total_spread_tax
            logger.info(f"One-time payment with tax spread: gross={indexed_amount}, tax={tax_amount}")
        else:
            # מס רגיל
            tax_amount = self.calculate_tax(indexed_amount, asset)
        
        net_amount = indexed_amount - tax_amount
        
        # Create single cashflow item for the payment date
        cashflow_item = CapitalAssetCashflowItem(
            date=payment_date,
            gross_return=indexed_amount,
            tax_amount=tax_amount,
            net_return=net_amount,
            asset_type=asset.asset_type,
            description=asset.description or f"תשלום חד פעמי - {asset.asset_type}"
        )
        cashflow_items.append(cashflow_item)
        
        # אם יש פריסת מס, נוסיף items נוספים עם מס 0 לשנים הבאות (רק להצגה)
        if is_tax_spread and asset.spread_years and asset.spread_years > 1:
            annual_portion = indexed_amount / Decimal(asset.spread_years)
            
            for year in range(1, asset.spread_years):
                # תאריך שנה לאחר
                future_date = self._add_months(payment_date, year * 12)
                
                if future_date > actual_end_date:
                    break
                
                # item להצגה בלבד - מס = 0
                display_item = CapitalAssetCashflowItem(
                    date=future_date,
                    gross_return=Decimal('0'),  # אין תשלום בפועל
                    tax_amount=Decimal('0'),  # מס = 0 (כבר שולם)
                    net_return=Decimal('0'),
                    asset_type=asset.asset_type,
                    description=f"{asset.description} - פריסה שנה {year + 1} (הצגה בלבד)"
                )
                cashflow_items.append(display_item)
        
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
