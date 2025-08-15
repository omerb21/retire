from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.pension_fund import PensionFund
from app.schemas.pension_fund import PensionFundCreate, PensionFundUpdate, PensionFundOut
from app.services.pension_fund_service import compute_and_persist

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
    for k, v in payload.dict(exclude_unset=True).items():
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

@router.post("/pension-funds/{fund_id}/compute", response_model=PensionFundOut)
def compute_pension_fund(fund_id: int, db: Session = Depends(get_db)):
    fund = db.get(PensionFund, fund_id)
    if not fund:
        raise HTTPException(status_code=404, detail={"error": "מקור קצבה לא נמצא"})
    return compute_and_persist(db, fund)
