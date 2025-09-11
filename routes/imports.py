"""
FastAPI routes for XML import operations
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
import tempfile
import os

from db.session import get_db
from services.xml_import import process_xml_import
from models.saving_product import SavingProduct
from models.existing_product import ExistingProduct
from models.new_product import NewProduct

router = APIRouter(prefix="/imports", tags=["imports"])

@router.post("/xml")
def import_xml_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Import XML file and process fund data"""
    
    # Validate file type
    if not file.filename.endswith('.xml'):
        raise HTTPException(status_code=400, detail="Only XML files are supported")
    
    # Save uploaded file temporarily
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xml') as temp_file:
            content = file.file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        # Process the XML file
        result = process_xml_import(db, temp_file_path)
        
        # Clean up temporary file
        os.unlink(temp_file_path)
        
        if result["success"]:
            return {
                "message": "XML file imported successfully",
                "filename": file.filename,
                "saving_product_id": result["saving_product_id"],
                "mapped_to": result["mapped_to"],
                "mapped_id": result["mapped_id"],
                "client_matched": result["client_matched"]
            }
        else:
            raise HTTPException(status_code=400, detail=f"Import failed: {result['error']}")
            
    except Exception as e:
        # Clean up temporary file if it exists
        if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
        raise HTTPException(status_code=500, detail=f"Import processing failed: {str(e)}")

@router.post("/xml/batch")
def import_xml_files_batch(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    """Import multiple XML files in batch"""
    
    results = []
    
    for file in files:
        if not file.filename.endswith('.xml'):
            results.append({
                "filename": file.filename,
                "success": False,
                "error": "Only XML files are supported"
            })
            continue
        
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xml') as temp_file:
                content = file.file.read()
                temp_file.write(content)
                temp_file_path = temp_file.name
            
            # Process the XML file
            result = process_xml_import(db, temp_file_path)
            
            # Clean up temporary file
            os.unlink(temp_file_path)
            
            results.append({
                "filename": file.filename,
                "success": result["success"],
                "saving_product_id": result.get("saving_product_id"),
                "mapped_to": result.get("mapped_to"),
                "client_matched": result.get("client_matched"),
                "error": result.get("error")
            })
            
        except Exception as e:
            if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
            results.append({
                "filename": file.filename,
                "success": False,
                "error": str(e)
            })
    
    successful_imports = sum(1 for r in results if r["success"])
    
    return {
        "message": f"Batch import completed: {successful_imports}/{len(files)} files processed successfully",
        "results": results,
        "total_files": len(files),
        "successful_imports": successful_imports
    }

@router.get("/saving-products")
def list_saving_products(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all imported saving products"""
    
    total = db.query(SavingProduct).count()
    products = db.query(SavingProduct).offset(skip).limit(limit).all()
    
    return {
        "products": [
            {
                "id": p.id,
                "fund_code": p.fund_code,
                "fund_name": p.fund_name,
                "company_name": p.company_name,
                "yield_1yr": p.yield_1yr,
                "yield_3yr": p.yield_3yr,
                "imported_at": p.imported_at
            }
            for p in products
        ],
        "total": total
    }

@router.get("/existing-products")
def list_existing_products(
    client_id: int = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List existing products (mapped to clients)"""
    
    query = db.query(ExistingProduct)
    if client_id:
        query = query.filter(ExistingProduct.client_id == client_id)
    
    total = query.count()
    products = query.offset(skip).limit(limit).all()
    
    return {
        "products": [
            {
                "id": p.id,
                "client_id": p.client_id,
                "fund_code": p.fund_code,
                "fund_name": p.fund_name,
                "company_name": p.company_name,
                "current_balance": p.current_balance,
                "monthly_contribution": p.monthly_contribution,
                "status": p.status
            }
            for p in products
        ],
        "total": total
    }

@router.get("/new-products")
def list_new_products(
    status: str = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List new products (pending client matching)"""
    
    query = db.query(NewProduct)
    if status:
        query = query.filter(NewProduct.status == status)
    
    total = query.count()
    products = query.offset(skip).limit(limit).all()
    
    return {
        "products": [
            {
                "id": p.id,
                "potential_client_id": p.potential_client_id,
                "potential_client_name": p.potential_client_name,
                "fund_code": p.fund_code,
                "fund_name": p.fund_name,
                "company_name": p.company_name,
                "current_balance": p.current_balance,
                "status": p.status,
                "match_confidence": p.match_confidence
            }
            for p in products
        ],
        "total": total
    }
