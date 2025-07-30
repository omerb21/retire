import unittest
from datetime import date, datetime, timedelta
from app.services.client_service import (
    normalize_id_number,
    validate_id_number,
    validate_birth_date,
    validate_employment_flags,
    normalize_text,
    normalize_phone,
    validate_email,
    prepare_client_payload
)


class TestClientService(unittest.TestCase):
    """Unit tests for client service validation and normalization functions"""

    def test_normalize_id_number(self):
        """Test ID number normalization"""
        # Test padding with leading zeros
        self.assertEqual(normalize_id_number("123456789"), "123456789")
        self.assertEqual(normalize_id_number("12345678"), "012345678")
        self.assertEqual(normalize_id_number("1234567"), "001234567")
        
        # Test removing non-digits
        self.assertEqual(normalize_id_number("123-456-789"), "123456789")
        self.assertEqual(normalize_id_number("12 34 56 78 9"), "123456789")
        
        # Test empty or None input
        self.assertEqual(normalize_id_number(""), "")
        self.assertEqual(normalize_id_number(None), "")

    def test_validate_id_number(self):
        """Test Israeli ID number validation with checksum"""
        # Valid ID numbers
        self.assertTrue(validate_id_number("123456782"))  # Valid checksum
        self.assertTrue(validate_id_number("305567663"))  # Valid checksum
        
        # Invalid ID numbers
        self.assertFalse(validate_id_number("123456789"))  # Invalid checksum
        self.assertFalse(validate_id_number("12345678"))   # Too short
        self.assertFalse(validate_id_number("1234567890")) # Too long
        self.assertFalse(validate_id_number(""))           # Empty
        self.assertFalse(validate_id_number(None))         # None

    def test_validate_birth_date(self):
        """Test birth date validation with age limits"""
        today = date.today()
        
        # Valid birth dates (between 18 and 120 years old)
        valid_date_18 = today - timedelta(days=18*365 + 5)  # 18 years + 5 days
        valid_date_65 = today - timedelta(days=65*365)      # 65 years
        valid_date_120 = today - timedelta(days=120*365 - 5)  # Just under 120 years
        
        self.assertTrue(validate_birth_date(valid_date_18))
        self.assertTrue(validate_birth_date(valid_date_65))
        self.assertTrue(validate_birth_date(valid_date_120))
        
        # Invalid birth dates
        too_young = today - timedelta(days=18*365 - 5)  # Just under 18 years
        too_old = today - timedelta(days=120*365 + 5)   # Just over 120 years
        future_date = today + timedelta(days=5)         # Future date
        
        self.assertFalse(validate_birth_date(too_young))
        self.assertFalse(validate_birth_date(too_old))
        self.assertFalse(validate_birth_date(future_date))
        self.assertFalse(validate_birth_date(None))

    def test_validate_employment_flags(self):
        """Test employment flags logical validation"""
        # Valid combinations
        self.assertTrue(validate_employment_flags(self_employed=True, current_employer_exists=False))
        self.assertTrue(validate_employment_flags(self_employed=False, current_employer_exists=True))
        self.assertTrue(validate_employment_flags(self_employed=False, current_employer_exists=False))
        
        # Invalid combination: both self-employed and has current employer
        self.assertFalse(validate_employment_flags(self_employed=True, current_employer_exists=True))

    def test_normalize_text(self):
        """Test text normalization (trimming, whitespace collapsing, Unicode NFC)"""
        # Test trimming and whitespace collapsing
        self.assertEqual(normalize_text("  hello  world  "), "hello world")
        self.assertEqual(normalize_text("\t\nhello\t\nworld\t\n"), "hello world")
        self.assertEqual(normalize_text("multiple   spaces   between   words"), "multiple spaces between words")
        
        # Test Unicode NFC normalization (Hebrew example)
        hebrew_text = "שלום עולם"  # Already in NFC form for this example
        self.assertEqual(normalize_text(hebrew_text), hebrew_text)
        
        # Test empty or None input
        self.assertEqual(normalize_text(""), "")
        self.assertEqual(normalize_text(None), "")

    def test_normalize_phone(self):
        """Test phone number normalization"""
        # Test keeping digits, plus, hyphens, spaces
        self.assertEqual(normalize_phone("+972-50-1234567"), "+972-50-1234567")
        self.assertEqual(normalize_phone("+972 50 1234567"), "+972 50 1234567")
        self.assertEqual(normalize_phone("050-1234567"), "050-1234567")
        
        # Test removing invalid characters
        self.assertEqual(normalize_phone("(050)1234567"), "0501234567")
        self.assertEqual(normalize_phone("050.123.4567"), "0501234567")
        self.assertEqual(normalize_phone("050/123/4567"), "0501234567")
        
        # Test empty or None input
        self.assertEqual(normalize_phone(""), "")
        self.assertEqual(normalize_phone(None), "")

    def test_validate_email(self):
        """Test email format validation"""
        # Valid emails
        self.assertTrue(validate_email("user@example.com"))
        self.assertTrue(validate_email("user.name@example.co.il"))
        self.assertTrue(validate_email("user+tag@example.com"))
        self.assertTrue(validate_email("user-name@example.com"))
        self.assertTrue(validate_email("123@example.com"))
        
        # Invalid emails
        self.assertFalse(validate_email("user@"))
        self.assertFalse(validate_email("@example.com"))
        self.assertFalse(validate_email("user@example"))
        self.assertFalse(validate_email("user@.com"))
        self.assertFalse(validate_email("user@example..com"))
        self.assertFalse(validate_email(""))
        self.assertFalse(validate_email(None))

    def test_prepare_client_payload(self):
        """Test client payload preparation with normalization"""
        # Test payload with all fields
        input_payload = {
            "id_number_raw": " 123456782 ",
            "full_name": "  ישראל ישראלי  ",
            "first_name": " ישראל ",
            "last_name": " ישראלי ",
            "birth_date": "1980-01-01",
            "gender": "male",
            "marital_status": "married",
            "self_employed": True,
            "current_employer_exists": False,
            "email": " USER@EXAMPLE.COM ",
            "phone": " (050) 123-4567 ",
            "address_street": " רחוב הרצל ",
            "address_city": " תל אביב ",
            "address_postal_code": " 12345 ",
            "retirement_target_date": "2045-01-01",
            "is_active": True,
            "notes": " הערות כלליות "
        }
        
        expected_payload = {
            "id_number_raw": "123456782",
            "id_number": "123456782",
            "full_name": "ישראל ישראלי",
            "first_name": "ישראל",
            "last_name": "ישראלי",
            "birth_date": date(1980, 1, 1),
            "gender": "male",
            "marital_status": "married",
            "self_employed": True,
            "current_employer_exists": False,
            "email": "user@example.com",
            "phone": "050-123-4567",
            "address_street": "רחוב הרצל",
            "address_city": "תל אביב",
            "address_postal_code": "12345",
            "retirement_target_date": date(2045, 1, 1),
            "is_active": True,
            "notes": "הערות כלליות"
        }
        
        result = prepare_client_payload(input_payload)
        
        # Check that all keys in expected_payload are in result with correct values
        for key, value in expected_payload.items():
            self.assertIn(key, result)
            self.assertEqual(result[key], value)
        
        # Test minimal payload with only required fields
        minimal_input = {
            "id_number_raw": "123456782",
            "full_name": "ישראל ישראלי",
            "birth_date": "1980-01-01",
            "is_active": True
        }
        
        minimal_result = prepare_client_payload(minimal_input)
        
        self.assertEqual(minimal_result["id_number_raw"], "123456782")
        self.assertEqual(minimal_result["id_number"], "123456782")
        self.assertEqual(minimal_result["full_name"], "ישראל ישראלי")
        self.assertEqual(minimal_result["birth_date"], date(1980, 1, 1))
        self.assertEqual(minimal_result["is_active"], True)


if __name__ == "__main__":
    unittest.main()
