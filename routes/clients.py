"""
FastAPI routes for Client CRUD operations
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from db.session import get_db
from models.client import Client
from schemas.client import ClientCreate, ClientUpdate, ClientResponse, ClientListResponse

router = APIRouter(prefix="/clients", tags=["clients"])

def normalize_id(id_raw: str) -> str:
    """Normalize ID number by removing leading zeros and whitespace"""
    return id_raw.strip().lstrip("0")

@router.post("/", response_model=dict)
def create_client(payload: ClientCreate, db: Session = Depends(get_db)):
    """Create a new client"""
    normalized = normalize_id(payload.id_number_raw)
    
    # Check if client already exists
    existing = db.query(Client).filter(Client.id_number_normalized == normalized).first()
    if existing:
        raise HTTPException(status_code=400, detail="Client with this ID number already exists")
    
    # Create new client
    client = Client(
        id_number_raw=payload.id_number_raw,
        id_number_normalized=normalized,
        full_name=payload.full_name,
        sex=payload.sex,
        marital_status=payload.marital_status,
        address_city=payload.address_city,
        address_street=payload.address_street,
        address_number=payload.address_number,
        employer_name=payload.employer_name
    )
    
    db.add(client)
    db.commit()
    db.refresh(client)
    
    return {"id": client.id, "message": "Client created successfully"}

@router.get("/{client_id}", response_model=ClientResponse)
def get_client(client_id: int, db: Session = Depends(get_db)):
    """Get a specific client by ID"""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client

@router.get("/", response_model=ClientListResponse)
def list_clients(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    search: Optional[str] = Query(None, description="Search by name or ID number"),
    db: Session = Depends(get_db)
):
    """List clients with optional search and pagination"""
    query = db.query(Client)
    
    # Apply search filter if provided
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Client.full_name.ilike(search_term)) |
            (Client.id_number_raw.ilike(search_term)) |
            (Client.id_number_normalized.ilike(search_term))
        )
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    clients = query.offset(skip).limit(limit).all()
    
    return ClientListResponse(clients=clients, total=total)

@router.put("/{client_id}", response_model=ClientResponse)
def update_client(client_id: int, payload: ClientUpdate, db: Session = Depends(get_db)):
    """Update an existing client"""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Update only provided fields
    update_data = payload.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(client, field, value)
    
    db.commit()
    db.refresh(client)
    
    return client

@router.delete("/{client_id}")
def delete_client(client_id: int, db: Session = Depends(get_db)):
    """Delete a client"""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    db.delete(client)
    db.commit()
    
    return {"message": "Client deleted successfully"}
