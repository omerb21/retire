"""API router for Capital Asset management."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.capital_asset import CapitalAsset
from app.schemas.capital_asset import (
    CapitalAssetCreate,
    CapitalAssetUpdate,
    CapitalAssetResponse
)

router = APIRouter(prefix="/clients/{client_id}/capital-assets", tags=["capital-assets"])


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
    """Get all capital assets for a client."""
    # Verify client exists
    from app.models.client import Client
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client with id {client_id} not found"
        )
    
    assets = db.query(CapitalAsset).filter(
        CapitalAsset.client_id == client_id
    ).all()
    
    return assets


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


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_capital_asset(
    client_id: int,
    asset_id: int,
    db: Session = Depends(get_db)
):
    """Delete a capital asset."""
    asset = db.query(CapitalAsset).filter(
        CapitalAsset.id == asset_id,
        CapitalAsset.client_id == client_id
    ).first()
    
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Capital asset with id {asset_id} not found for client {client_id}"
        )
    
    db.delete(asset)
    db.commit()
    
    return None
