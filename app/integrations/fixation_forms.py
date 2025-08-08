from pathlib import Path
from sqlalchemy.orm import Session
from app.models.client import Client
import logging
import re
import os

# Template paths - standardized
TEMPLATE_161D = Path("templates/fixation/161d.pdf")
TEMPLATE_GRANTS = Path("templates/fixation/grants_appendix.pdf")
TEMPLATE_COMMUT = Path("templates/fixation/commutations_appendix.pdf")

# Environment variable for fallback control
FIXATION_ALLOW_JSON_FALLBACK = os.getenv("FIXATION_ALLOW_JSON_FALLBACK", "true").lower() == "true"

def slug(text: str) -> str:
    """
    Convert Hebrew/English text with spaces to safe filename slug
    
    Args:
        text: Input text (may contain Hebrew, spaces, special chars)
        
    Returns:
        Safe filename string with hyphens instead of spaces
    """
    if not text:
        return ""
    
    # Replace spaces and problematic characters with hyphens
    text = re.sub(r'[\s\\/:*?"<>|]+', '-', text)
    # Remove leading/trailing hyphens
    text = text.strip('-')
    # Collapse multiple hyphens
    text = re.sub(r'-+', '-', text)
    
    return text

def build_161d_fields(client: Client) -> dict:
    """
    ׳׳׳₪׳” ׳׳•׳‘׳™׳™׳§׳˜ Client ׳׳©׳“׳•׳× ׳”-FILLABLE ׳‘׳˜׳•׳₪׳¡ 161׳“.
    """
    return {
        "full_name": client.full_name or "",
        "id_number": client.id_number or "",
        "birth_date": client.birth_date.isoformat() if client.birth_date else "",
        "address_city": client.address_city or "",
        "address_street": client.address_street or "",
        "address_postal_code": client.address_postal_code or "",
        "email": client.email or "",
        "phone": client.phone or "",
        # ׳”׳•׳¡׳£/׳¢׳“׳›׳ ׳׳₪׳™ ׳©׳׳•׳× ׳”-FILLABLE ׳‘׳˜׳•׳₪׳¡ 161׳“
    }

def build_grants_fields(client: Client) -> dict:
    """
    ׳׳׳₪׳” ׳׳•׳‘׳™׳™׳§׳˜ Client ׳׳©׳“׳•׳× ׳ ׳¡׳₪׳— ׳׳¢׳ ׳§׳™׳.
    """
    return {
        "full_name": client.full_name or "",
        "id_number": client.id_number or "",
        # ׳©׳“׳•׳× ׳™׳™׳¢׳•׳“׳™׳™׳ ׳׳ ׳¡׳₪׳— ׳׳¢׳ ׳§׳™׳...
    }

def build_commutations_fields(client: Client) -> dict:
    """
    ׳׳׳₪׳” ׳׳•׳‘׳™׳™׳§׳˜ Client ׳׳©׳“׳•׳× ׳ ׳¡׳₪׳— ׳”׳™׳•׳•׳ ׳™׳.
    """
    return {
        "full_name": client.full_name or "",
        "id_number": client.id_number or "",
        # ׳©׳“׳•׳× ׳™׳™׳¢׳•׳“׳™׳™׳ ׳׳ ׳¡׳₪׳— ׳”׳™׳•׳•׳ ׳™׳...
    }

def get_client_output_dir(client_id: int, client_name: str = None) -> Path:
    """
    Get standardized output directory for client files
    
    Args:
        client_id: Client ID
        client_name: Client full name (optional)
        
    Returns:
        Path to client's package directory
    """
    if client_name:
        dir_name = f"client_{client_id}_{slug(client_name)}"
    else:
        dir_name = f"client_{client_id}"
    
    return Path("packages") / dir_name

def get_versioned_filename(output_dir: Path, base_name: str, extension: str) -> str:
    """
    Get versioned filename if file already exists
    
    Args:
        output_dir: Output directory
        base_name: Base filename without extension
        extension: File extension (with dot)
        
    Returns:
        Versioned filename
    """
    filename = f"{base_name}{extension}"
    filepath = output_dir / filename
    
    if not filepath.exists():
        return filename
    
    # Find next available version
    version = 2
    while True:
        versioned_filename = f"{base_name}_v{version}{extension}"
        versioned_filepath = output_dir / versioned_filename
        if not versioned_filepath.exists():
            return versioned_filename
        version += 1
        if version > 100:  # Safety limit
            break
    
    return filename  # Fallback to original

def _fill_form(template: Path, output_dir: Path, file_name: str, fields: dict) -> Path:
    """
    Generic form filling function with improved fallback logic
    
    Args:
        template: Template PDF path
        output_dir: Output directory
        file_name: Base filename without extension
        fields: Form fields to fill
        
    Returns:
        Path to generated file (PDF or JSON)
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(__name__)
    
    # Try PDF generation first
    try:
        import pdf_filler as fixation_pdf
        if hasattr(fixation_pdf, "fill_acroform"):
            pdf_filename = get_versioned_filename(output_dir, file_name, ".pdf")
            out_pdf = output_dir / pdf_filename
            fixation_pdf.fill_acroform(template, out_pdf, fields)
            logger.debug(f"PDF generated successfully: {out_pdf}")
            return out_pdf
    except ImportError:
        logger.debug("pdf_filler module not available")
    except Exception as e:
        logger.debug(f"PDF generation failed: {e}")
    
    # Fallback to JSON
    if FIXATION_ALLOW_JSON_FALLBACK:
        json_filename = get_versioned_filename(output_dir, file_name, ".json")
        out_json = output_dir / json_filename
        import json
        out_json.write_text(json.dumps(fields, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.debug(f"JSON fallback generated: {out_json}")
        return out_json
    else:
        # If fallback disabled, raise error
        from fastapi import HTTPException
        raise HTTPException(
            status_code=503,
            detail={"error": "׳¡׳₪׳¨׳™׳•׳× PDF ׳׳™׳ ׳ ׳–׳׳™׳ ׳•׳× ׳•-fallback ׳-JSON ׳׳ ׳•׳˜׳¨׳"}
        )

def fill_161d_form(db: Session, client_id: int, template_path: Path, output_dir: Path) -> Path:
    """
    ׳׳׳׳ ׳˜׳•׳₪׳¡ 161׳“.
    """
    client = db.query(Client).filter(Client.id == client_id, Client.is_active == True).one()
    return _fill_form(template_path, output_dir, f"161d_{client.id}", build_161d_fields(client))

def fill_grants_appendix(db: Session, client_id: int, template_path: Path, output_dir: Path) -> Path:
    """
    ׳׳׳׳ ׳ ׳¡׳₪׳— ׳׳¢׳ ׳§׳™׳.
    """
    client = db.query(Client).filter(Client.id == client_id, Client.is_active == True).one()
    return _fill_form(template_path, output_dir, f"grants_appendix_{client.id}", build_grants_fields(client))

def fill_commutations_appendix(db: Session, client_id: int, template_path: Path, output_dir: Path) -> Path:
    """
    ׳׳׳׳ ׳ ׳¡׳₪׳— ׳”׳™׳•׳•׳ ׳™׳.
    """
    client = db.query(Client).filter(Client.id == client_id, Client.is_active == True).one()
    return _fill_form(template_path, output_dir, f"commutations_appendix_{client.id}", build_commutations_fields(client))

