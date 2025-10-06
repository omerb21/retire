# Yearly Totals Verification Guide

## Overview
The Yearly Totals Verification feature allows users to verify that the monthly cashflow data correctly adds up to the reported yearly totals in the retirement system. The verification process checks for consistency, mathematical correctness, and data completeness across all scenarios and years.

## Key Features
- Validates monthly cashflow data is present for all 12 months of each year
- Verifies that monthly cashflow values are consistent with calculated yearly totals
- Checks for mathematical errors in monthly net calculations (inflow - outflow + additional income + capital return)
- Generates cryptographically sound proof summaries for audit purposes
- Displays detailed validation results with clear error reporting

## User Interface
The yearly totals verification feature is integrated into the API verification frontend as a new tab labeled "אימות סיכומים שנתיים" (Yearly Totals Verification).

### Components
1. **Input Form**
   - Client ID field: Specifies which client's data to verify
   - Scenario ID field: Specifies which scenario to verify
   - Test Mode checkbox: When checked, uses mock data for testing (not connected to backend)

2. **Results Display**
   - Format selector: Choose between summary view, detailed view, or proof summary
   - Download buttons for proof summary and artifact ZIP (when applicable)
   - Color-coded results for quick status assessment

## How to Use
1. Navigate to the "אימות סיכומים שנתיים" tab in the API Verification UI
2. Enter a valid client ID and scenario ID
3. Choose whether to use test mode (for testing without a backend)
4. Click the "בדוק סיכומים שנתיים" (Verify Yearly Totals) button
5. View the progress bar as verification steps are completed
6. Select a format to view the results (summary, detailed, or proof)
7. Download the proof summary if needed

## Validation Rules
The verification includes the following checks:

1. **Completeness Check**
   - All 12 months must be present for each year in each scenario
   - Each month must contain all required fields (inflow, outflow, net, etc.)

2. **Monthly Net Calculation Check**
   - For each month: net = inflow - outflow + additional_income_net + capital_return_net (within tolerance)

3. **Yearly Totals Calculation Check**
   - Sum of monthly values must match the reported yearly totals (within tolerance)
   - Checks all fields: inflow, outflow, net, additional_income_net, capital_return_net

## Proof Summary
The proof summary is a cryptographically sound record of the verification process. It includes:

- Timestamp and unique verification ID (nonce)
- Dataset information (date ranges, record counts)
- API endpoint status codes
- Validation results for each scenario and year
- Error details (limited to first 5 errors per scenario/year)
- Hash values of dataset artifacts

## Implementation Details
The verification functionality is implemented in three main components:

1. `yearly_totals_verifier.js` - Core verification logic class
2. `yearly_totals_tab.html` - HTML snippet for the verification tab (integrated into main UI)
3. Integration code in `api_verification.html` - Connects the UI with the verification logic

### Test Mode
For development and testing purposes, a test mode is available that uses mock data instead of making real API calls. This allows testing the verification logic without a running backend.

## Error Handling
The verification reports the following types of errors:

- **MISSING_MONTH** - A month is missing from the yearly data
- **NET_MISMATCH** - Monthly net value does not match calculated value
- **YEARLY_TOTAL_MISMATCH** - Sum of monthly values doesn't match reported yearly total
- **DATA_FORMAT_ERROR** - Malformed data detected (e.g., invalid date format)

## Known Limitations
- ZIP artifact creation is not supported in-browser
- Limited error reporting (maximum 5 errors per scenario/year)
- Tolerance for floating-point comparisons is fixed at 0.01
