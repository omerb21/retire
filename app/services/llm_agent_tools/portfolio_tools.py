import logging
from typing import Any, Dict

from app.models.capital_asset import CapitalAsset
from app.models.pension_fund import PensionFund

logger = logging.getLogger("app.llm_agent_tools")


class PortfolioToolsMixin:
    def get_pension_products(self) -> Dict[str, Any]:
        """
        מחזיר את כל המוצרים הפנסיוניים וההוניים של הלקוח בצורה מרוכזת.
        """
        client = self.client
        if not client:
            logger.warning("GET_PENSION_PRODUCTS: client %s not found", self.client_id)
            return {
                "success": False,
                "tool_name": "GET_PENSION_PRODUCTS",
                "result": {},
                "explanation": "לא נמצא לקוח.",
            }

        logger.info("GET_PENSION_PRODUCTS: client %s loaded", self.client_id)

        products: list[dict[str, Any]] = []
        pension_products: list[dict[str, Any]] = []
        capital_products: list[dict[str, Any]] = []

        # 1. קרנות פנסיה וקופות גמל
        pension_funds = (
            self.db.query(PensionFund)
            .filter(PensionFund.client_id == self.client_id)
            .all()
        )

        # 2. נכסים הוניים (ביטוח מנהלים, גמל להשקעה)
        capital_assets = (
            self.db.query(CapitalAsset)
            .filter(CapitalAsset.client_id == self.client_id)
            .all()
        )

        logger.info(
            "GET_PENSION_PRODUCTS: client %s has %d pension funds and %d capital assets",
            self.client_id,
            len(pension_funds),
            len(capital_assets),
        )

        for pf in pension_funds:
            pf_created_at = getattr(pf, "created_at", None)
            pf_updated_at = getattr(pf, "updated_at", None)
            item = {
                "category": "pension",
                "id": pf.id,
                "fund_name": pf.fund_name,
                "fund_type": pf.fund_type,
                "input_mode": pf.input_mode,
                "balance": float(pf.balance or 0),
                "annuity_factor": (
                    float(pf.annuity_factor) if pf.annuity_factor else None
                ),
                "pension_amount": (
                    float(pf.pension_amount) if pf.pension_amount else None
                ),
                "pension_start_date": (
                    pf.pension_start_date.isoformat() if pf.pension_start_date else None
                ),
                "tax_treatment": pf.tax_treatment,
                "deduction_file": pf.deduction_file,
                "conversion_source": pf.conversion_source,
                "remarks": pf.remarks,
                "created_at": pf_created_at.isoformat() if pf_created_at else None,
                "updated_at": pf_updated_at.isoformat() if pf_updated_at else None,
            }
            pension_products.append(item)
            products.append(item)

        for ca in capital_assets:
            ca_created_at = getattr(ca, "created_at", None)
            ca_updated_at = getattr(ca, "updated_at", None)
            item = {
                "category": "capital",
                "id": ca.id,
                "asset_name": ca.asset_name,
                "asset_type": ca.asset_type,
                "current_value": float(ca.current_value or 0),
                "monthly_income": (
                    float(ca.monthly_income) if ca.monthly_income else None
                ),
                "start_date": ca.start_date.isoformat() if ca.start_date else None,
                "end_date": ca.end_date.isoformat() if ca.end_date else None,
                "tax_treatment": ca.tax_treatment,
                "conversion_source": ca.conversion_source,
                "remarks": ca.remarks,
                "description": ca.description,
                "created_at": ca_created_at.isoformat() if ca_created_at else None,
                "updated_at": ca_updated_at.isoformat() if ca_updated_at else None,
            }
            capital_products.append(item)
            products.append(item)

        # מיון לפי יתרה יורדת
        products.sort(
            key=lambda x: float(x.get("balance") or x.get("current_value") or 0),
            reverse=True,
        )

        total_balance = sum(
            float(p.get("balance") or p.get("current_value") or 0) for p in products
        )

        logger.info(
            "GET_PENSION_PRODUCTS: returning %d products (total_balance=%s) for client %s",
            len(products),
            total_balance,
            self.client_id,
        )

        # יצירת הסבר טקסטואלי קצר לשימוש המודל
        explanation = (
            f"נמצאו {len(products)} מוצרים בתיק.\n"
            f'סה"כ צבירה: {total_balance:,.0f} ₪.'
        )

        return {
            "success": True,
            "tool_name": "GET_PENSION_PRODUCTS",
            "result": {
                "products": products,
                "pension_funds": pension_products,
                "capital_assets": capital_products,
                "total_balance": total_balance,
                "count": len(products),
            },
            "explanation": explanation,
        }
