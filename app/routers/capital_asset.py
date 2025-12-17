"""API router for Capital Asset management."""

from typing import List
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.capital_asset import CapitalAsset, AssetType, PaymentFrequency
from app.schemas.capital_asset import (
    CapitalAssetCreate,
    CapitalAssetUpdate,
    CapitalAssetResponse
)

router = APIRouter(prefix="/clients/{client_id}/capital-assets", tags=["capital-assets"])
logger = logging.getLogger("app.capital_asset")


@router.post("/", response_model=CapitalAssetResponse, status_code=status.HTTP_201_CREATED)
def create_capital_asset(
    client_id: int,
    asset_data: CapitalAssetCreate,
    db: Session = Depends(get_db)
):
    """Create a new capital asset for a client."""
    # Verify client exists
    from app.models.client import Client
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client with id {client_id} not found"
        )
    
    # Create capital asset
    db_asset = CapitalAsset(
        client_id=client_id,
        **asset_data.dict()
    )
    
    db.add(db_asset)
    db.commit()
    db.refresh(db_asset)
    
    return db_asset


@router.get("/", response_model=List[CapitalAssetResponse])
def get_capital_assets(
    client_id: int,
    db: Session = Depends(get_db)
):
    """Get all capital assets for a client - FAST VERSION."""
    try:
        assets = db.query(CapitalAsset).filter(
            CapitalAsset.client_id == client_id
        ).all()

        asset_type_values = {t.value for t in AssetType}
        frequency_values = {f.value for f in PaymentFrequency}

        normalized: List[CapitalAssetResponse] = []
        for asset in assets:
            try:
                normalized.append(CapitalAssetResponse.model_validate(asset, from_attributes=True))
            except Exception:
                raw_asset_type = getattr(asset, "asset_type", None)
                raw_frequency = getattr(asset, "payment_frequency", None)

                if raw_asset_type == "savings":
                    asset_type = AssetType.SAVINGS_ACCOUNT.value
                elif raw_asset_type in asset_type_values:
                    asset_type = raw_asset_type
                else:
                    asset_type = AssetType.OTHER.value

                if raw_frequency in frequency_values:
                    payment_frequency = raw_frequency
                else:
                    payment_frequency = PaymentFrequency.ANNUALLY.value

                payload = {
                    "id": getattr(asset, "id", None),
                    "client_id": getattr(asset, "client_id", None),
                    "asset_name": getattr(asset, "asset_name", None),
                    "asset_type": asset_type,
                    "description": getattr(asset, "description", None),
                    "current_value": getattr(asset, "current_value", 0),
                    "monthly_income": getattr(asset, "monthly_income", None),
                    "rental_income": getattr(asset, "rental_income", None),
                    "monthly_rental_income": getattr(asset, "monthly_rental_income", None),
                    "annual_return_rate": getattr(asset, "annual_return_rate", 0),
                    "payment_frequency": payment_frequency,
                    "start_date": getattr(asset, "start_date", None),
                    "end_date": getattr(asset, "end_date", None),
                    "indexation_method": getattr(asset, "indexation_method", None),
                    "fixed_rate": getattr(asset, "fixed_rate", None),
                    "tax_treatment": getattr(asset, "tax_treatment", None),
                    "tax_rate": getattr(asset, "tax_rate", None),
                    "spread_years": getattr(asset, "spread_years", None),
                    "original_principal": getattr(asset, "original_principal", None),
                    "remarks": getattr(asset, "remarks", None),
                    "conversion_source": getattr(asset, "conversion_source", None),
                }
                normalized.append(CapitalAssetResponse.model_validate(payload))

        return normalized
    except Exception as e:
        logger.exception("Error getting capital assets for client_id=%s: %s", client_id, e)
        return []


@router.get("/{asset_id}", response_model=CapitalAssetResponse)
def get_capital_asset(
    client_id: int,
    asset_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific capital asset."""
    asset = db.query(CapitalAsset).filter(
        CapitalAsset.id == asset_id,
        CapitalAsset.client_id == client_id
    ).first()
    
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Capital asset with id {asset_id} not found for client {client_id}"
        )
    
    return asset


@router.put("/{asset_id}", response_model=CapitalAssetResponse)
def update_capital_asset(
    client_id: int,
    asset_id: int,
    asset_data: CapitalAssetUpdate,
    db: Session = Depends(get_db)
):
    """Update a capital asset."""
    asset = db.query(CapitalAsset).filter(
        CapitalAsset.id == asset_id,
        CapitalAsset.client_id == client_id
    ).first()
    
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Capital asset with id {asset_id} not found for client {client_id}"
        )
    
    # Update fields
    update_data = asset_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(asset, field, value)
    
    db.commit()
    db.refresh(asset)
    
    return asset


@router.delete("/{asset_id}", status_code=status.HTTP_200_OK)
def delete_capital_asset(
    client_id: int,
    asset_id: int,
    db: Session = Depends(get_db)
):
    """Delete a capital asset with balance restoration if applicable."""
    from app.services.asset_deletion_service import delete_capital_asset_with_restoration
    
    result = delete_capital_asset_with_restoration(db, asset_id, client_id)
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result["error"]
        )
    
    db.commit()
    
    return result
