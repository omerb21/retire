"""
Service for deleting pension funds and capital assets with balance restoration
"""

import logging
import json
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.pension_fund import PensionFund
from app.models.capital_asset import CapitalAsset

logger = logging.getLogger("app.asset_deletion")


def restore_balance_from_pension_fund(
    db: Session, pension_fund: "PensionFund"
) -> Optional[Dict[str, Any]]:
    """
    Restore balance to pension portfolio when deleting a converted pension/capital asset

    Returns dict with restoration info if successful, None otherwise
    """
    logger.info(
        f"🔍 restore_balance_from_pension_fund called for fund ID: {pension_fund.id}"
    )
    logger.info(f"🔍 conversion_source exists: {bool(pension_fund.conversion_source)}")
    logger.info(f"🔍 deduction_file exists: {bool(pension_fund.deduction_file)}")

    # First check conversion_source
    if pension_fund.conversion_source:
        logger.info(
            f"🔍 conversion_source value: {pension_fund.conversion_source[:200]}"
        )
        try:
            source_data = json.loads(pension_fund.conversion_source)
            logger.info(f"🔍 Parsed source_data: {source_data}")
            logger.info(f"🔍 source_data.get('type'): {source_data.get('type')}")
            logger.info(f"🔍 source_data.get('source'): {source_data.get('source')}")

            # Check if this was from termination event
            if source_data.get("source") == "termination_event":
                logger.info(
                    f"  ℹ️ Termination-sourced pension - balance restoration handled separately"
                )
                return {
                    "restored": False,
                    "reason": "termination_event",
                    "message": "יתרת פיצויים תוחזר דרך מנגנון עזיבת העבודה",
                }

            # Check if this was from pension portfolio conversion
            source_type = source_data.get("type") or source_data.get("source")
            if source_type == "pension_portfolio":
                account_number = (
                    source_data.get("account_number") or pension_fund.deduction_file
                )
                logger.info(
                    f"  📋 Pension fund from portfolio (account: {account_number})"
                )
                logger.info(
                    f"  ⚠️ Balance restoration to pension portfolio must be handled by client-side"
                )

                # החזרת מידע מפורט על הרכיבים שהומרו (אם קיים), כדי שהלקוח יחזיר לטורי המשנה הנכונים
                specific_amounts = source_data.get("specific_amounts", {})

                balance_raw = source_data.get("amount")
                if balance_raw is None:
                    balance_raw = source_data.get("original_balance")
                if balance_raw is None:
                    balance_raw = pension_fund.balance
                balance_to_restore = float(balance_raw or 0)

                return {
                    "restored": False,
                    "reason": "pension_portfolio",
                    "account_number": account_number,
                    "balance_to_restore": balance_to_restore,
                    "message": f"יש להחזיר ₪{balance_to_restore:,.0f} לחשבון {account_number} בתיק הפנסיוני",
                    "specific_amounts": specific_amounts,
                }
        except Exception as e:
            logger.warning(f"  ⚠️ Failed to parse conversion_source: {e}")

    # Fallback: Check deduction_file
    if pension_fund.deduction_file:
        logger.info(
            f"  📋 Pension fund from portfolio (account: {pension_fund.deduction_file})"
        )
        logger.info(
            f"  ⚠️ Balance restoration to pension portfolio must be handled by client-side"
        )

        return {
            "restored": False,
            "reason": "pension_portfolio",
            "account_number": pension_fund.deduction_file,
            "balance_to_restore": float(pension_fund.balance or 0),
            "message": f"יש להחזיר ₪{float(pension_fund.balance or 0):,.0f} לחשבון {pension_fund.deduction_file} בתיק הפנסיוני",
        }

    return None


def restore_balance_from_capital_asset(
    db: Session, capital_asset: "CapitalAsset"
) -> Optional[Dict[str, Any]]:
    """
    Restore balance to pension portfolio when deleting a converted capital asset

    Returns dict with restoration info if successful, None otherwise
    """
    logger.info(
        f"🔍 restore_balance_from_capital_asset called for asset ID: {capital_asset.id}"
    )
    logger.info(f"🔍 conversion_source exists: {bool(capital_asset.conversion_source)}")

    # Check conversion_source
    if not capital_asset.conversion_source:
        logger.info(f"  ❌ No conversion_source - returning None")
        return None

    logger.info(f"🔍 conversion_source value: {capital_asset.conversion_source[:200]}")

    try:
        source_data = json.loads(capital_asset.conversion_source)
        logger.info(f"🔍 Parsed source_data: {source_data}")
        logger.info(f"🔍 source_data.get('type'): {source_data.get('type')}")
        logger.info(f"🔍 source_data.get('source'): {source_data.get('source')}")

        # Check if this was from termination event
        if source_data.get("source") == "termination_event":
            logger.info(
                f"  ℹ️ Termination-sourced capital asset - balance restoration handled separately"
            )
            return {
                "restored": False,
                "reason": "termination_event",
                "message": "יתרת פיצויים תוחזר דרך מנגנון עזיבת העבודה",
            }

        # Check if this was from pension portfolio conversion
        if source_data.get("type") == "pension_portfolio":
            account_number = source_data.get("account_number")
            balance_raw = source_data.get("amount")
            if balance_raw is None:
                balance_raw = source_data.get("original_balance")
            if balance_raw is None:
                balance_raw = capital_asset.monthly_income
            balance_to_restore = float(balance_raw or 0)

            logger.info(
                f"  📋 Capital asset from portfolio (account: {account_number})"
            )
            logger.info(f"  📋 Balance to restore: ₪{balance_to_restore:,.2f}")
            logger.info(
                f"  ⚠️ Balance restoration to pension portfolio must be handled by client-side"
            )

            result = {
                "restored": False,
                "reason": "pension_portfolio",
                "account_number": account_number,
                "balance_to_restore": balance_to_restore,
                "message": f"יש להחזיר ₪{balance_to_restore:,.0f} לחשבון {account_number} בתיק הפנסיוני",
                "specific_amounts": source_data.get("specific_amounts", {}),
            }
            logger.info(f"  ✅ Returning restoration info: {result}")
            return result
        else:
            logger.info(f"  ❌ type is not 'pension_portfolio', returning None")

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning(f"  ⚠️ Failed to parse conversion_source: {e}")
        return None

    logger.info(f"  ❌ No matching condition - returning None")
    return None


def delete_pension_fund_with_restoration(
    db: Session, fund_id: int, client_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Delete a pension fund and restore balance if it was converted from another source

    Returns dict with deletion and restoration info
    """
    fund = db.query(PensionFund).filter(PensionFund.id == fund_id).first()

    if not fund:
        return {"success": False, "error": "מקור קצבה לא נמצא"}

    if client_id and fund.client_id != client_id:
        return {"success": False, "error": "מקור קצבה לא נמצא עבור לקוח זה"}

    fund_name = fund.fund_name

    logger.info(f"🗑️ Deleting pension fund #{fund_id}: {fund_name}")

    # Try to restore balance before deletion
    restoration_info = restore_balance_from_pension_fund(db, fund)

    # Delete the fund
    db.delete(fund)

    logger.info(f"  ✅ Deleted pension fund #{fund_id}")

    return {
        "success": True,
        "deleted_fund_id": fund_id,
        "deleted_fund_name": fund_name,
        "restoration": restoration_info,
    }


def delete_capital_asset_with_restoration(
    db: Session, asset_id: int, client_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Delete a capital asset and restore balance if it was converted from another source

    Returns dict with deletion and restoration info
    """
    asset = db.query(CapitalAsset).filter(CapitalAsset.id == asset_id).first()

    if not asset:
        return {"success": False, "error": "נכס הון לא נמצא"}

    if client_id and asset.client_id != client_id:
        return {"success": False, "error": "נכס הון לא נמצא עבור לקוח זה"}

    asset_name = asset.asset_name

    logger.info(f"🗑️ Deleting capital asset #{asset_id}: {asset_name}")

    # Try to restore balance before deletion
    restoration_info = restore_balance_from_capital_asset(db, asset)

    # Delete the asset
    db.delete(asset)

    logger.info(f"  ✅ Deleted capital asset #{asset_id}")

    return {
        "success": True,
        "deleted_asset_id": asset_id,
        "deleted_asset_name": asset_name,
        "restoration": restoration_info,
    }
