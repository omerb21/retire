#!/usr/bin/env python
"""
Yearly Totals Verification Tool
-------------------------------
Validates yearly totals against monthly cashflows and generates proof summary.
"""

import base64
import datetime
import hashlib
import json
import os
import random
import zipfile
from decimal import Decimal, getcontext
from typing import Dict, List, Optional, Set, Tuple, Union, Any

# Set decimal precision for financial calculations
getcontext().prec = 28

# Constants
TOLERANCE = Decimal('0.01')
ISO_DATE_FORMAT = "%Y-%m-%d"
MONTHLY_DATE_FORMAT = "%Y-%m-01"
ARTIFACT_DIR = "artifacts"
MAX_ERRORS_PER_SCENARIO = 5


class YearlyTotalsVerifier:
    """Verifies yearly totals against monthly cashflows and generates proof."""

    def __init__(self):
        """Initialize the verifier with empty data structures."""
        self.nonce = base64.b64encode(os.urandom(16)).decode('utf-8')
        self.timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        self.artifacts = {}
        self.api_status = {}
        self.validation_results = {}
        self.errors = []
        self.global_verdict = "PASS"
        self.release_timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
        self.zip_path = f"{ARTIFACT_DIR}/release-{self.release_timestamp}-s11.zip"
        
        # Ensure artifact directory exists
        os.makedirs(ARTIFACT_DIR, exist_ok=True)

    def validate_date_format(self, date_str: str) -> bool:
        """Validate that a date string is in YYYY-MM-01 format."""
        try:
            dt = datetime.datetime.strptime(date_str, ISO_DATE_FORMAT)
            return dt.day == 1 and date_str.endswith("-01")
        except (ValueError, TypeError):
            return False

    def extract_year_month(self, date_str: str) -> Tuple[int, int]:
        """Extract year and month from a date string."""
        try:
            dt = datetime.datetime.strptime(date_str, ISO_DATE_FORMAT)
            return dt.year, dt.month
        except (ValueError, TypeError):
            return 0, 0

    def check_monthly_net(self, row: Dict) -> Tuple[bool, Decimal]:
        """Check if monthly net matches the formula."""
        try:
            inflow = Decimal(str(row.get('inflow', 0)))
            outflow = Decimal(str(row.get('outflow', 0)))
            add_income = Decimal(str(row.get('additional_income_net', 0)))
            cap_return = Decimal(str(row.get('capital_return_net', 0)))
            net = Decimal(str(row.get('net', 0)))
            
            calculated_net = inflow - outflow + add_income + cap_return
            diff = abs(net - calculated_net)
            
            return diff <= TOLERANCE, diff
        except (TypeError, ValueError):
            return False, Decimal('999999')

    def validate_monthly_data(self, scenario_id: str, monthly_data: List[Dict]) -> List[Dict]:
        """Validate monthly data for a scenario and return errors."""
        errors = []
        months_seen = set()
        
        for row in monthly_data:
            # Check date format
            date_str = row.get('date')
            if not self.validate_date_format(date_str):
                errors.append({
                    "error_type": "invalid_date_format",
                    "scenario_id": scenario_id,
                    "date": date_str,
                    "expected": "YYYY-MM-01",
                    "actual": date_str
                })
                continue
                
            # Check for duplicate months
            year, month = self.extract_year_month(date_str)
            month_key = f"{year}-{month:02d}"
            if month_key in months_seen:
                errors.append({
                    "error_type": "duplicate_month",
                    "scenario_id": scenario_id,
                    "year": year,
                    "month": month,
                    "date": date_str
                })
            months_seen.add(month_key)
            
            # Check for non-numeric values
            for field in ['inflow', 'outflow', 'additional_income_net', 'capital_return_net', 'net']:
                value = row.get(field)
                if not isinstance(value, (int, float, Decimal)) or (isinstance(value, float) and (value != value)):  # NaN check
                    errors.append({
                        "error_type": "invalid_value_type",
                        "scenario_id": scenario_id,
                        "date": date_str,
                        "field": field,
                        "expected": "numeric",
                        "actual": str(type(value))
                    })
            
            # Check monthly net formula
            net_valid, diff = self.check_monthly_net(row)
            if not net_valid:
                errors.append({
                    "error_type": "monthly_net_mismatch",
                    "scenario_id": scenario_id,
                    "date": date_str,
                    "expected": str(round(Decimal(str(row.get('inflow', 0))) - 
                                         Decimal(str(row.get('outflow', 0))) + 
                                         Decimal(str(row.get('additional_income_net', 0))) + 
                                         Decimal(str(row.get('capital_return_net', 0))), 2)),
                    "actual": str(row.get('net')),
                    "diff": str(round(diff, 2))
                })
        
        # Check for missing months
        if monthly_data:
            # Sort by date
            sorted_data = sorted(monthly_data, key=lambda x: x.get('date', ''))
            start_date = sorted_data[0].get('date')
            end_date = sorted_data[-1].get('date')
            
            if self.validate_date_format(start_date) and self.validate_date_format(end_date):
                start_year, start_month = self.extract_year_month(start_date)
                end_year, end_month = self.extract_year_month(end_date)
                
                # Generate all expected months
                expected_months = set()
                current_year, current_month = start_year, start_month
                
                while (current_year < end_year) or (current_year == end_year and current_month <= end_month):
                    expected_months.add(f"{current_year}-{current_month:02d}")
                    current_month += 1
                    if current_month > 12:
                        current_month = 1
                        current_year += 1
                
                # Find missing months
                for expected in expected_months:
                    if expected not in months_seen:
                        year, month = map(int, expected.split('-'))
                        errors.append({
                            "error_type": "missing_month",
                            "scenario_id": scenario_id,
                            "year": year,
                            "month": month,
                            "date": f"{year}-{month:02d}-01"
                        })
        
        return errors

    def compute_yearly_totals(self, monthly_data: List[Dict]) -> Dict[int, Dict]:
        """Compute yearly totals from monthly data."""
        yearly_totals = {}
        
        for row in monthly_data:
            date_str = row.get('date')
            if not self.validate_date_format(date_str):
                continue
                
            year, _ = self.extract_year_month(date_str)
            
            if year not in yearly_totals:
                yearly_totals[year] = {
                    'inflow': Decimal('0'),
                    'outflow': Decimal('0'),
                    'additional_income_net': Decimal('0'),
                    'capital_return_net': Decimal('0'),
                    'net': Decimal('0'),
                    'months_found': 0
                }
            
            # Add values to yearly totals
            for field in ['inflow', 'outflow', 'additional_income_net', 'capital_return_net', 'net']:
                try:
                    value = Decimal(str(row.get(field, 0)))
                    yearly_totals[year][field] += value
                except (TypeError, ValueError):
                    pass  # Skip invalid values
            
            yearly_totals[year]['months_found'] += 1
        
        return yearly_totals

    def validate_yearly_totals(self, scenario_id: str, computed: Dict[int, Dict], 
                              reported: Dict[str, Dict]) -> List[Dict]:
        """Validate reported yearly totals against computed values."""
        errors = []
        
        for year, computed_values in computed.items():
            str_year = str(year)
            
            # Check if year exists in reported totals
            if str_year not in reported:
                errors.append({
                    "error_type": "missing_yearly_total",
                    "scenario_id": scenario_id,
                    "year": year
                })
                continue
            
            # Check each field
            for field in ['inflow', 'outflow', 'additional_income_net', 'capital_return_net', 'net']:
                computed_value = computed_values[field]
                
                try:
                    reported_value = Decimal(str(reported[str_year].get(field, 0)))
                    diff = abs(reported_value - computed_value)
                    
                    if diff > TOLERANCE:
                        errors.append({
                            "error_type": "yearly_total_mismatch",
                            "scenario_id": scenario_id,
                            "year": year,
                            "field": field,
                            "expected": str(round(computed_value, 2)),
                            "actual": str(round(reported_value, 2)),
                            "diff": str(round(diff, 2))
                        })
                except (TypeError, ValueError):
                    errors.append({
                        "error_type": "invalid_yearly_value_type",
                        "scenario_id": scenario_id,
                        "year": year,
                        "field": field,
                        "expected": "numeric",
                        "actual": str(type(reported[str_year].get(field)))
                    })
        
        return errors

    def validate_scenario(self, scenario_id: str, monthly_data: List[Dict], 
                         yearly_totals: Dict[str, Dict]) -> Dict:
        """Validate a scenario's yearly totals against monthly data."""
        # Validate monthly data
        monthly_errors = self.validate_monthly_data(scenario_id, monthly_data)
        
        # Compute yearly totals from monthly data
        computed_totals = self.compute_yearly_totals(monthly_data)
        
        # Validate yearly totals
        yearly_errors = self.validate_yearly_totals(
            scenario_id, computed_totals, yearly_totals)
        
        # Combine errors
        all_errors = monthly_errors + yearly_errors
        
        # Prepare validation results
        validation_result = {
            "scenario_id": scenario_id,
            "years": {},
            "status": "PASS" if not all_errors else "FAIL",
            "errors": all_errors[:MAX_ERRORS_PER_SCENARIO]
        }
        
        # Add detailed year information
        for year, computed in computed_totals.items():
            str_year = str(year)
            reported = yearly_totals.get(str_year, {})
            
            year_result = {
                "months_expected": 12,  # Assuming full years
                "months_found": computed["months_found"],
                "computed": {},
                "reported": {},
                "diff": {},
                "status": "PASS"
            }
            
            # Check each field
            for field in ['inflow', 'outflow', 'additional_income_net', 'capital_return_net', 'net']:
                computed_value = computed[field]
                try:
                    reported_value = Decimal(str(reported.get(field, 0)))
                    diff = reported_value - computed_value
                    
                    year_result["computed"][field] = str(round(computed_value, 2))
                    year_result["reported"][field] = str(round(reported_value, 2))
                    year_result["diff"][field] = str(round(diff, 2))
                    
                    if abs(diff) > TOLERANCE:
                        year_result["status"] = "FAIL"
                except (TypeError, ValueError):
                    year_result["computed"][field] = str(round(computed_value, 2))
                    year_result["reported"][field] = "INVALID"
                    year_result["diff"][field] = "N/A"
                    year_result["status"] = "FAIL"
            
            # Set year status based on months found
            if year_result["months_found"] != year_result["months_expected"]:
                year_result["status"] = "FAIL"
                
            validation_result["years"][year] = year_result
        
        return validation_result

    def add_artifact(self, filename: str, content: Union[str, bytes]) -> str:
        """Add an artifact file and return its SHA256 hash."""
        if isinstance(content, str):
            content = content.encode('utf-8')
            
        file_hash = hashlib.sha256(content).hexdigest()
        file_size = len(content)
        
        filepath = os.path.join(ARTIFACT_DIR, filename)
        with open(filepath, 'wb') as f:
            f.write(content)
        
        self.artifacts[filename] = {
            "path": filepath,
            "hash": file_hash,
            "size": file_size
        }
        
        return file_hash

    def set_api_status(self, endpoint: str, status_code: int, **details) -> None:
        """Set the status of an API endpoint."""
        self.api_status[endpoint] = {
            "status_code": status_code,
            **details
        }

    def create_zip_artifact(self) -> Dict:
        """Create a ZIP artifact containing all files and return its details."""
        with zipfile.ZipFile(self.zip_path, 'w') as zipf:
            for filename, details in self.artifacts.items():
                zipf.write(details["path"], arcname=filename)
        
        with open(self.zip_path, 'rb') as f:
            content = f.read()
            
        zip_hash = hashlib.sha256(content).hexdigest()
        zip_size = len(content)
        
        return {
            "path": self.zip_path,
            "hash": zip_hash,
            "size": zip_size
        }

    def generate_proof_summary(self) -> str:
        """Generate the proof summary text."""
        # Create ZIP artifact
        zip_details = self.create_zip_artifact()
        
        # Start building summary
        summary = [
            "=== SPRINT 11 YEARLY TOTALS PROOF ===",
            f"Nonce: {self.nonce}",
            f"Timestamp: {self.timestamp}",
            "",
            "Datasets:"
        ]
        
        # Add artifacts
        for filename, details in self.artifacts.items():
            summary.append(f"- {filename:<25} SHA256={details['hash']}  bytes={details['size']}")
        
        summary.append("")
        summary.append("API Status:")
        
        # Add API status
        for endpoint, details in self.api_status.items():
            status_line = f"- {endpoint:<15} {details['status_code']}"
            for key, value in details.items():
                if key != "status_code":
                    status_line += f"  {key}={value}"
            summary.append(status_line)
        
        summary.append("")
        summary.append("Yearly Totals Validation:")
        
        # Add validation results
        for scenario_id, result in self.validation_results.items():
            summary.append(f"Scenario {scenario_id}")
            
            for year, year_result in result["years"].items():
                summary.append(f"  {year}: months_expected={year_result['months_expected']} "
                              f"months_found={year_result['months_found']}  {year_result['status']}")
                
                for field in ['inflow', 'outflow', 'add_income', 'cap_return', 'net']:
                    display_field = field
                    if field == 'add_income':
                        source_field = 'additional_income_net'
                    elif field == 'cap_return':
                        source_field = 'capital_return_net'
                    else:
                        source_field = field
                        
                    if source_field in year_result["reported"] and source_field in year_result["computed"]:
                        summary.append(f"        {display_field}: reported={year_result['reported'][source_field]} "
                                      f"computed={year_result['computed'][source_field]} "
                                      f"diff={year_result['diff'][source_field]}")
        
        # Add global verdict
        summary.append("")
        summary.append(f"Global Verdict: {self.global_verdict}")
        
        # Add errors if any
        if self.global_verdict == "FAIL" and self.errors:
            summary.append("Errors:")
            for error in self.errors[:5]:  # Limit to 5 errors
                error_str = f"- Scenario {error['scenario_id']}"
                if 'year' in error:
                    error_str += f", Year {error['year']}"
                error_str += f": {error['error_type']}"
                
                if 'date' in error:
                    error_str += f"={error['date']}"
                elif 'field' in error:
                    error_str += f"={error['field']}"
                
                if 'diff' in error:
                    error_str += f" diff={error['diff']}"
                    
                summary.append(error_str)
        
        # Add ZIP info
        summary.append(f"ZIP: {zip_details['path']}  SHA256={zip_details['hash']}  bytes={zip_details['size']}")
        summary.append("=== END PROOF ===")
        
        return "\n".join(summary)

    def verify_data(self, data: Dict) -> str:
        """
        Verify the data and generate a proof summary.
        
        Expected data format:
        {
            "scenarios": [
                {
                    "scenario_id": "sid1",
                    "monthly_data": [...],
                    "yearly_totals": {...}
                },
                ...
            ],
            "api_status": {
                "CASE DETECT": {"status_code": 200, "case": "standard"},
                ...
            }
        }
        """
        # Process each scenario
        for scenario in data.get("scenarios", []):
            scenario_id = scenario.get("scenario_id")
            monthly_data = scenario.get("monthly_data", [])
            yearly_totals = scenario.get("yearly_totals", {})
            
            # Validate scenario
            validation_result = self.validate_scenario(
                scenario_id, monthly_data, yearly_totals)
            
            # Store validation result
            self.validation_results[scenario_id] = validation_result
            
            # Add errors to global list
            if validation_result["errors"]:
                self.errors.extend(validation_result["errors"])
                self.global_verdict = "FAIL"
            
            # Add monthly data as artifact
            self.add_artifact(
                f"cashflow_{scenario_id}.json", 
                json.dumps(monthly_data, indent=2)
            )
            
            # Add yearly totals as artifact
            self.add_artifact(
                f"yearly_totals_{scenario_id}.json", 
                json.dumps(yearly_totals, indent=2)
            )
        
        # Set API status
        for endpoint, details in data.get("api_status", {}).items():
            self.set_api_status(endpoint, **details)
        
        # Add any additional artifacts
        for name, content in data.get("artifacts", {}).items():
            self.add_artifact(name, content)
        
        # Generate and return proof summary
        return self.generate_proof_summary()


def main():
    """Main function to demonstrate usage."""
    # Example usage
    verifier = YearlyTotalsVerifier()
    
    # Example data (would be loaded from API responses in real usage)
    example_data = {
        "scenarios": [
            {
                "scenario_id": "scenario1",
                "monthly_data": [
                    {
                        "date": "2025-01-01",
                        "inflow": 1000,
                        "outflow": 500,
                        "additional_income_net": 100,
                        "capital_return_net": 50,
                        "net": 650
                    },
                    # More monthly data...
                ],
                "yearly_totals": {
                    "2025": {
                        "inflow": 12000,
                        "outflow": 6000,
                        "additional_income_net": 1200,
                        "capital_return_net": 600,
                        "net": 7800
                    }
                }
            }
        ],
        "api_status": {
            "CASE DETECT": {"status_code": 200, "case": "standard"},
            "CASHFLOW": {"status_code": 200, "rows": 12, "range": "2025-01..2025-12"},
            "COMPARE": {"status_code": 200, "yearly_totals": "present"},
            "PDF": {"status_code": 200, "magic": "%PDF"}
        },
        "artifacts": {
            "report_ok.pdf": b"%PDF-1.4\n...sample PDF content..."
        }
    }
    
    # Verify data and generate proof summary
    proof_summary = verifier.verify_data(example_data)
    print(proof_summary)
    
    # Save proof summary
    with open(os.path.join(ARTIFACT_DIR, "proof_summary.txt"), "w") as f:
        f.write(proof_summary)


if __name__ == "__main__":
    main()
