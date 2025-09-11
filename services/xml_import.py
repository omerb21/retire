"""
XML Import service - Parse XML files and map to saving/existing/new products
"""
import xml.etree.ElementTree as ET
from sqlalchemy.orm import Session
from models.saving_product import SavingProduct
from models.existing_product import ExistingProduct
from models.new_product import NewProduct
from models.client import Client
from routes.clients import normalize_id
import json
import re

def parse_xml_file(file_path: str) -> dict:
    """Parse XML file and extract fund data"""
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        # Extract fund information
        rec = {
            "fund_code": root.findtext(".//FundCode") or "",
            "fund_name": root.findtext(".//FundName") or "",
            "company_name": root.findtext(".//Company") or "",
            "fund_type": root.findtext(".//FundType") or "",
            "yield_1yr": float(root.findtext(".//Yield1yr") or 0),
            "yield_3yr": float(root.findtext(".//Yield3yr") or 0),
            "raw_xml": ET.tostring(root, encoding="utf-8").decode("utf-8"),
        }
        
        # Extract client information if available
        client_info = extract_client_info_from_xml(root)
        rec.update(client_info)
        
        return rec
    except Exception as e:
        raise ValueError(f"Failed to parse XML file: {str(e)}")

def extract_client_info_from_xml(root) -> dict:
    """Extract client information from XML"""
    client_info = {}
    
    # Try different possible field names for client ID
    possible_id_fields = [".//ClientId", ".//PersonalNumber", ".//IdNumber", ".//ID"]
    for field in possible_id_fields:
        value = root.findtext(field)
        if value:
            client_info["client_id_raw"] = value.strip()
            break
    
    # Try to extract client name
    possible_name_fields = [".//ClientName", ".//Name", ".//FullName"]
    for field in possible_name_fields:
        value = root.findtext(field)
        if value:
            client_info["client_name"] = value.strip()
            break
    
    # Extract balance and contribution if available
    balance = root.findtext(".//Balance") or root.findtext(".//CurrentBalance")
    if balance:
        try:
            client_info["current_balance"] = float(balance)
        except ValueError:
            pass
    
    contribution = root.findtext(".//MonthlyContribution") or root.findtext(".//Contribution")
    if contribution:
        try:
            client_info["monthly_contribution"] = float(contribution)
        except ValueError:
            pass
    
    return client_info

def normalize_identifiers(rec: dict) -> dict:
    """Normalize fund codes and client IDs"""
    # Normalize fund code
    if rec.get("fund_code"):
        rec["fund_code"] = rec["fund_code"].strip().lstrip("0")
    
    # Normalize client ID if present
    if rec.get("client_id_raw"):
        rec["client_id_normalized"] = normalize_id(rec["client_id_raw"])
    
    return rec

def save_to_saving_product(db: Session, rec: dict) -> SavingProduct:
    """Save parsed XML data to saving_product table"""
    sp = SavingProduct(
        fund_type=rec.get("fund_type"),
        company_name=rec.get("company_name"),
        fund_name=rec.get("fund_name"),
        fund_code=rec.get("fund_code"),
        yield_1yr=rec.get("yield_1yr", 0.0),
        yield_3yr=rec.get("yield_3yr", 0.0),
        raw_xml_blob=rec.get("raw_xml")
    )
    
    db.add(sp)
    db.commit()
    db.refresh(sp)
    
    return sp

def map_saving_to_existing_new(db: Session, sp: SavingProduct, client_info: dict):
    """Map saving product to existing or new product based on client matching"""
    
    # Try to find existing client
    client = None
    if client_info.get("client_id_normalized"):
        client = db.query(Client).filter(
            Client.id_number_normalized == client_info["client_id_normalized"]
        ).first()
    
    if client:
        # Create ExistingProduct
        existing = ExistingProduct(
            client_id=client.id,
            saving_product_id=sp.id,
            fund_code=sp.fund_code,
            fund_name=sp.fund_name,
            company_name=sp.company_name,
            current_balance=client_info.get("current_balance", 0.0),
            monthly_contribution=client_info.get("monthly_contribution", 0.0),
            yield_1yr=sp.yield_1yr,
            yield_3yr=sp.yield_3yr,
            status="active"
        )
        
        db.add(existing)
        db.commit()
        db.refresh(existing)
        
        return existing
    else:
        # Create NewProduct for future matching
        new_product = NewProduct(
            saving_product_id=sp.id,
            potential_client_id=client_info.get("client_id_raw"),
            potential_client_name=client_info.get("client_name"),
            fund_code=sp.fund_code,
            fund_name=sp.fund_name,
            company_name=sp.company_name,
            current_balance=client_info.get("current_balance", 0.0),
            monthly_contribution=client_info.get("monthly_contribution", 0.0),
            yield_1yr=sp.yield_1yr,
            yield_3yr=sp.yield_3yr,
            status="pending",
            match_confidence=calculate_match_confidence(client_info),
            raw_data=json.dumps(client_info)
        )
        
        db.add(new_product)
        db.commit()
        db.refresh(new_product)
        
        return new_product

def calculate_match_confidence(client_info: dict) -> float:
    """Calculate confidence score for potential client matching"""
    confidence = 0.0
    
    # ID number present and valid format
    if client_info.get("client_id_raw"):
        id_raw = client_info["client_id_raw"]
        if re.match(r'^\d{8,9}$', id_raw.strip()):
            confidence += 0.6
        else:
            confidence += 0.2
    
    # Name present
    if client_info.get("client_name"):
        name = client_info["client_name"].strip()
        if len(name) > 2 and not name.isdigit():
            confidence += 0.3
    
    # Financial data present
    if client_info.get("current_balance", 0) > 0:
        confidence += 0.1
    
    return min(confidence, 1.0)

def process_xml_import(db: Session, file_path: str) -> dict:
    """Complete XML import process"""
    try:
        # Parse XML
        rec = parse_xml_file(file_path)
        
        # Normalize identifiers
        rec = normalize_identifiers(rec)
        
        # Save to saving_product
        sp = save_to_saving_product(db, rec)
        
        # Extract client info for mapping
        client_info = {k: v for k, v in rec.items() if k.startswith("client_") or k in ["current_balance", "monthly_contribution"]}
        
        # Map to existing or new product
        mapped_product = map_saving_to_existing_new(db, sp, client_info)
        
        return {
            "success": True,
            "saving_product_id": sp.id,
            "mapped_to": type(mapped_product).__name__,
            "mapped_id": mapped_product.id,
            "client_matched": isinstance(mapped_product, ExistingProduct)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
