"""
Client router module for API endpoints
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_, and_

from app.database import get_db
from app.models.client import Client
from app.schemas.client import ClientCreate, ClientUpdate, ClientResponse, ClientList
from app.schemas import APIResponse
from app.services.client_service import prepare_client_payload, validate_client_data

# Create router with prefix
router = APIRouter(
    prefix="/api/v1/clients",
    tags=["clients"],
    responses={404: {"description": "Not found"}},
)


@router.post("", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
def create_client(client: ClientCreate, db: Session = Depends(get_db)):
    """
    Create a new client
    """
    # Prepare client data
    client_data = prepare_client_payload(client.model_dump())
    
    # Validate client data
    errors = validate_client_data(client_data)
    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=errors
        )
    
    # ׳‘׳“׳™׳§׳× ׳›׳₪׳™׳׳•׳× ׳׳₪׳ ׳™ ׳”-INSERT
    if "id_number" in client_data:
        db_id = db.query(Client.id).filter(Client.id_number == client_data["id_number"]).scalar()
        if db_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"id_number_raw": "׳×׳¢׳•׳“׳× ׳–׳”׳•׳× ׳›׳‘׳¨ ׳§׳™׳™׳׳× ׳‘׳׳¢׳¨׳›׳×"}
            )
    
    # Create new client
    db_client = Client(**client_data)
    db.add(db_client)
    
    try:
        db.commit()
        db.refresh(db_client)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"id_number_raw": "׳×׳¢׳•׳“׳× ׳–׳”׳•׳× ׳›׳‘׳¨ ׳§׳™׳™׳׳× ׳‘׳׳¢׳¨׳›׳×"}
        )
    
    return db_client


@router.get("/{client_id}", response_model=ClientResponse)
def get_client(client_id: int = Path(..., description="Client ID"), db: Session = Depends(get_db)):
    """
    Get client by ID
    """
    db_client = db.query(Client).filter(Client.id == client_id).first()
    if not db_client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="׳׳§׳•׳— ׳׳ ׳ ׳׳¦׳"
        )
    return db_client


@router.patch("/{client_id}", response_model=ClientResponse)
def update_client(
    client: ClientUpdate,
    client_id: int = Path(..., description="Client ID"),
    db: Session = Depends(get_db)
):
    """
    Update client by ID
    """
    # Get client
    db_client = db.query(Client).filter(Client.id == client_id).first()
    if not db_client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="׳׳§׳•׳— ׳׳ ׳ ׳׳¦׳"
        )
    
    # Prepare client data
    client_data = prepare_client_payload(client.model_dump(exclude_unset=True))
    
    # Check if ID number is being changed and if it already exists
    if "id_number" in client_data and client_data["id_number"] != db_client.id_number:
        existing_client = db.query(Client).filter(Client.id_number == client_data["id_number"]).first()
        if existing_client:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"id_number_raw": "׳×׳¢׳•׳“׳× ׳–׳”׳•׳× ׳›׳‘׳¨ ׳§׳™׳™׳׳× ׳‘׳׳¢׳¨׳›׳×"}
            )
    
    # Validate client data
    errors = validate_client_data(client_data)
    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=errors
        )
    
    # Update client
    for key, value in client_data.items():
        setattr(db_client, key, value)
    
    try:
        db.commit()
        db.refresh(db_client)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"id_number_raw": "׳×׳¢׳•׳“׳× ׳–׳”׳•׳× ׳›׳‘׳¨ ׳§׳™׳™׳׳× ׳‘׳׳¢׳¨׳›׳×"}
        )
    
    return db_client


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(client_id: int = Path(..., description="Client ID"), db: Session = Depends(get_db)):
    """
    Delete client by ID
    """
    db_client = db.query(Client).filter(Client.id == client_id).first()
    if not db_client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="׳׳§׳•׳— ׳׳ ׳ ׳׳¦׳"
        )
    
    db.delete(db_client)
    db.commit()
    
    return None


@router.get("", response_model=ClientList)
@router.get("/", response_model=ClientList)
def list_clients(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    gender: Optional[str] = Query(None, description="Filter by gender"),
    search: Optional[str] = Query(None, description="Search by name or ID number"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of records to return"),
    sort: Optional[str] = Query("id", description="Sort field"),
    db: Session = Depends(get_db)
):
    """
    List clients with filtering, pagination, and sorting
    """
    # Base query
    query = db.query(Client)
    
    # Apply filters
    if is_active is not None:
        query = query.filter(Client.is_active == is_active)
    
    if gender:
        query = query.filter(Client.gender == gender)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Client.full_name.ilike(search_term),
                Client.id_number.ilike(search_term)
            )
        )
    
    # Get total count
    total = query.count()
    
    # Apply sorting
    if sort:
        query = query.order_by(getattr(Client, sort))
    
    # Apply pagination
    query = query.offset(skip).limit(limit)
    
    # Get results
    clients = query.all()
    
    return {
        "items": clients,
        "total": total,
        "page": skip // limit + 1 if limit > 0 else 1,
        "page_size": limit
    }

