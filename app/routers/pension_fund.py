from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
from app.database import get_db
from app.models.pension_fund import PensionFund
from app.schemas.pension_fund import PensionFundCreate, PensionFundUpdate, PensionFundOut
from app.services.pension_fund_service import compute_and_persist, compute_and_persist_fund, compute_all_pension_funds

router = APIRouter(prefix="/api/v1", tags=["pension-funds"])

@router.post("/clients/{client_id}/pension-funds", response_model=PensionFundOut, status_code=status.HTTP_201_CREATED)
def create_pension_fund(client_id: int, payload: PensionFundCreate, db: Session = Depends(get_db)):
    if payload.client_id != client_id:
        raise HTTPException(status_code=422, detail={"error": "client_id mismatch"})

    fund = PensionFund(**payload.model_dump())
    db.add(fund)
    db.commit()
    db.refresh(fund)
    return fund

@router.get("/pension-funds/{fund_id}", response_model=PensionFundOut)
def get_pension_fund(fund_id: int, db: Session = Depends(get_db)):
    fund = db.get(PensionFund, fund_id)
    if not fund:
        raise HTTPException(status_code=404, detail={"error": "מקור קצבה לא נמצא"})
    return fund

@router.put("/pension-funds/{fund_id}", response_model=PensionFundOut)
def update_pension_fund(fund_id: int, payload: PensionFundUpdate, db: Session = Depends(get_db)):
    fund = db.get(PensionFund, fund_id)
    if not fund:
        raise HTTPException(status_code=404, detail={"error": "מקור קצבה לא נמצא"})
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(fund, k, v)
    db.add(fund)
    db.commit()
    db.refresh(fund)
    return fund

@router.delete("/pension-funds/{fund_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pension_fund(fund_id: int, db: Session = Depends(get_db)):
    fund = db.get(PensionFund, fund_id)
    if not fund:
        raise HTTPException(status_code=404, detail={"error": "מקור קצבה לא נמצא"})
    db.delete(fund)
    db.commit()
    return

@router.delete("/clients/{client_id}/pension-funds/{fund_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client_pension_fund(client_id: int, fund_id: int, db: Session = Depends(get_db)):
    fund = db.get(PensionFund, fund_id)
    if not fund:
        raise HTTPException(status_code=404, detail={"error": "מקור קצבה לא נמצא"})
    if fund.client_id != client_id:
        raise HTTPException(status_code=404, detail={"error": "מקור קצבה לא נמצא עבור לקוח זה"})
    db.delete(fund)
    db.commit()
    return

@router.post("/pension-funds/{fund_id}/compute", response_model=PensionFundOut)
def compute_pension_fund(
    fund_id: int, 
    reference_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    try:
        fund = compute_and_persist_fund(db, fund_id)
        return fund
    except ValueError as e:
        raise HTTPException(status_code=404, detail={"error": str(e)})

@router.post("/clients/{client_id}/pension-funds/{fund_id}/compute", response_model=PensionFundOut)
def compute_client_pension_fund(
    client_id: int,
    fund_id: int, 
    reference_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    try:
        fund = db.get(PensionFund, fund_id)
        if not fund:
            raise HTTPException(status_code=404, detail={"error": "מקור קצבה לא נמצא"})
        if fund.client_id != client_id:
            raise HTTPException(status_code=404, detail={"error": "מקור קצבה לא נמצא עבור לקוח זה"})
        
        fund = compute_and_persist_fund(db, fund_id)
        return fund
    except ValueError as e:
        raise HTTPException(status_code=404, detail={"error": str(e)})

@router.post("/clients/{client_id}/pension-funds/compute-all", response_model=List[PensionFundOut])
def compute_all_client_pension_funds(
    client_id: int,
    reference_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """Compute all pension funds for a client"""
    # Check if client exists
    from app.models.client import Client
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail={"error": "לקוח לא נמצא"})
    
    # Get all pension funds for the client
    funds = db.query(PensionFund).filter(PensionFund.client_id == client_id).all()
    if not funds:
        return []
    
    # Compute and update all funds
    updated_funds = []
    for fund in funds:
        updated_fund = compute_and_persist(db, fund, reference_date)
        updated_funds.append(updated_fund)
    
    return updated_funds

@router.get("/clients/{client_id}/pension-funds", response_model=List[PensionFundOut])
def get_client_pension_funds(client_id: int, db: Session = Depends(get_db)):
    """Get all pension funds for a client - FAST VERSION"""
    try:
        funds = db.query(PensionFund).filter(PensionFund.client_id == client_id).all()
        return funds
    except Exception as e:
        print(f"Error getting pension funds: {e}")
        return []
