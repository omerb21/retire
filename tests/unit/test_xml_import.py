"""
Unit tests for XML import functionality
"""
import pytest
import tempfile
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.base import Base
from models.client import Client
from models.saving_product import SavingProduct
from models.existing_product import ExistingProduct
from models.new_product import NewProduct
from services.xml_import import (
    parse_xml_file, normalize_identifiers, save_to_saving_product,
    map_saving_to_existing_new, process_xml_import
)

@pytest.fixture
def db_session():
    """Create in-memory SQLite database for testing"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()

@pytest.fixture
def sample_xml_content():
    """Sample XML content for testing"""
    return """<?xml version="1.0" encoding="UTF-8"?>
<FundData>
    <FundCode>001234</FundCode>
    <FundName>Test Pension Fund</FundName>
    <Company>Test Insurance Company</Company>
    <FundType>Pension</FundType>
    <Yield1yr>5.2</Yield1yr>
    <Yield3yr>4.8</Yield3yr>
    <ClientId>123456789</ClientId>
    <ClientName>John Doe</ClientName>
    <Balance>50000.00</Balance>
    <MonthlyContribution>1000.00</MonthlyContribution>
</FundData>"""

@pytest.fixture
def sample_xml_file(sample_xml_content):
    """Create temporary XML file for testing"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
        f.write(sample_xml_content)
        temp_path = f.name
    yield temp_path
    os.unlink(temp_path)

def test_parse_xml_file_returns_expected_fields(sample_xml_file):
    """Test that parse_xml_file extracts all expected fields"""
    result = parse_xml_file(sample_xml_file)
    
    assert result["fund_code"] == "001234"
    assert result["fund_name"] == "Test Pension Fund"
    assert result["company_name"] == "Test Insurance Company"
    assert result["fund_type"] == "Pension"
    assert result["yield_1yr"] == 5.2
    assert result["yield_3yr"] == 4.8
    assert result["client_id_raw"] == "123456789"
    assert result["client_name"] == "John Doe"
    assert result["current_balance"] == 50000.0
    assert result["monthly_contribution"] == 1000.0
    assert "raw_xml" in result

def test_normalize_identifiers_strips_leading_zeros():
    """Test that normalize_identifiers removes leading zeros"""
    rec = {
        "fund_code": "000123",
        "client_id_raw": "000123456789"
    }
    
    result = normalize_identifiers(rec)
    
    assert result["fund_code"] == "123"
    assert result["client_id_normalized"] == "123456789"

def test_save_to_saving_product(db_session):
    """Test saving parsed data to saving_product table"""
    rec = {
        "fund_code": "123",
        "fund_name": "Test Fund",
        "company_name": "Test Company",
        "fund_type": "Pension",
        "yield_1yr": 5.0,
        "yield_3yr": 4.5,
        "raw_xml": "<test>xml</test>"
    }
    
    sp = save_to_saving_product(db_session, rec)
    
    assert sp.id is not None
    assert sp.fund_code == "123"
    assert sp.fund_name == "Test Fund"
    assert sp.yield_1yr == 5.0

def test_map_to_existing_product_when_client_exists(db_session):
    """Test mapping to existing product when client is found"""
    # Create a client first
    client = Client(
        id_number_raw="123456789",
        id_number_normalized="123456789",
        full_name="John Doe"
    )
    db_session.add(client)
    db_session.commit()
    
    # Create saving product
    sp = SavingProduct(
        fund_code="123",
        fund_name="Test Fund",
        company_name="Test Company"
    )
    db_session.add(sp)
    db_session.commit()
    
    # Test mapping
    client_info = {
        "client_id_normalized": "123456789",
        "current_balance": 50000.0,
        "monthly_contribution": 1000.0
    }
    
    result = map_saving_to_existing_new(db_session, sp, client_info)
    
    assert isinstance(result, ExistingProduct)
    assert result.client_id == client.id
    assert result.current_balance == 50000.0

def test_map_to_new_product_when_client_not_found(db_session):
    """Test mapping to new product when client is not found"""
    # Create saving product
    sp = SavingProduct(
        fund_code="123",
        fund_name="Test Fund",
        company_name="Test Company"
    )
    db_session.add(sp)
    db_session.commit()
    
    # Test mapping with non-existent client
    client_info = {
        "client_id_raw": "999999999",
        "client_id_normalized": "999999999",
        "client_name": "Unknown Client",
        "current_balance": 25000.0
    }
    
    result = map_saving_to_existing_new(db_session, sp, client_info)
    
    assert isinstance(result, NewProduct)
    assert result.potential_client_id == "999999999"
    assert result.potential_client_name == "Unknown Client"
    assert result.status == "pending"
    assert result.match_confidence > 0

def test_full_import_process(db_session, sample_xml_file):
    """Test complete import process end-to-end"""
    # Create a client that matches the XML
    client = Client(
        id_number_raw="123456789",
        id_number_normalized="123456789",
        full_name="John Doe"
    )
    db_session.add(client)
    db_session.commit()
    
    # Process import
    result = process_xml_import(db_session, sample_xml_file)
    
    assert result["success"] is True
    assert "saving_product_id" in result
    assert result["mapped_to"] == "ExistingProduct"
    assert result["client_matched"] is True
    
    # Verify data was saved correctly
    sp = db_session.query(SavingProduct).filter(
        SavingProduct.id == result["saving_product_id"]
    ).first()
    assert sp is not None
    assert sp.fund_code == "1234"  # Leading zeros removed
    
    ep = db_session.query(ExistingProduct).filter(
        ExistingProduct.id == result["mapped_id"]
    ).first()
    assert ep is not None
    assert ep.client_id == client.id

def test_import_counts_match_expectations(db_session):
    """Test that import produces expected number of records"""
    initial_saving_count = db_session.query(SavingProduct).count()
    initial_existing_count = db_session.query(ExistingProduct).count()
    initial_new_count = db_session.query(NewProduct).count()
    
    # Create sample XML files and import them
    xml_contents = [
        """<?xml version="1.0"?>
        <FundData>
            <FundCode>001</FundCode>
            <FundName>Fund 1</FundName>
            <Company>Company 1</Company>
            <ClientId>111111111</ClientId>
        </FundData>""",
        """<?xml version="1.0"?>
        <FundData>
            <FundCode>002</FundCode>
            <FundName>Fund 2</FundName>
            <Company>Company 2</Company>
            <ClientId>222222222</ClientId>
        </FundData>"""
    ]
    
    # Create client for first XML
    client = Client(
        id_number_raw="111111111",
        id_number_normalized="111111111",
        full_name="Test Client"
    )
    db_session.add(client)
    db_session.commit()
    
    # Process both XML files
    for xml_content in xml_contents:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
            f.write(xml_content)
            temp_path = f.name
        
        try:
            process_xml_import(db_session, temp_path)
        finally:
            os.unlink(temp_path)
    
    # Check counts
    final_saving_count = db_session.query(SavingProduct).count()
    final_existing_count = db_session.query(ExistingProduct).count()
    final_new_count = db_session.query(NewProduct).count()
    
    assert final_saving_count == initial_saving_count + 2
    assert final_existing_count == initial_existing_count + 1  # One matched client
    assert final_new_count == initial_new_count + 1  # One unmatched
