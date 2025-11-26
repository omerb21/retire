# Yearly Totals Verification Specification

## Input Data Structure

For each scenario, the verification process expects:

1. **Monthly Cashflow Array**: Collection of objects with the following fields:
   - `date`: ISO string in format "YYYY-MM-01" only
   - `inflow`: Numeric value
   - `outflow`: Numeric value
   - `additional_income_net`: Numeric value
   - `capital_return_net`: Numeric value
   - `net`: Numeric value

2. **Yearly Totals Object**: For each year, the same fields aggregated annually.

## Validation Rules (Invariants)

### Date Format Validation
- Every `date` field must be in format "YYYY-MM-01"
- No duplicate months within a scenario
- No missing months in the range from start to end date (monthly frequency)

### Monthly Net Calculation
- For each month, the following must be true (with rounding tolerance ±0.01):
  ```
  net == inflow - outflow + additional_income_net + capital_return_net
  ```

### Yearly Totals Validation
- For each year Y:
  ```
  inflow_Y = Σ inflow_{Y,*}
  outflow_Y = Σ outflow_{Y,*}
  additional_income_net_Y = Σ additional_income_net_{Y,*}
  capital_return_net_Y = Σ capital_return_net_{Y,*}
  net_Y = Σ net_{Y,*}
  ```

- Cross-check (with tolerance ±0.01):
  ```
  net_Y == inflow_Y - outflow_Y + additional_income_net_Y + capital_return_net_Y
  ```

- The values in `yearly_totals` must match the computed values

### Data Type and Precision
- All fields must be numeric (not strings, null, or NaN)
- Display precision: 2 decimal places
- Internal calculation: full precision without truncation

## Verification Output (Per Scenario)

For each scenario:
- `scenario_id`
- For each year:
  - `months_expected`, `months_found`
  - `sum_inflow`, `sum_outflow`, `sum_additional_income_net`, `sum_capital_return_net`, `sum_net` (computed)
  - `reported_inflow`, `reported_outflow`, `reported_additional_income_net`, `reported_capital_return_net`, `reported_net` (from yearly_totals)
  - `diff_inflow`, `diff_outflow`, `diff_additional_income_net`, `diff_capital_return_net`, `diff_net` (reported - computed)
  - `status`: "PASS" if all diffs ≤ 0.01 and no missing/duplicate months or formula errors; otherwise "FAIL" with specific error list

## Error Detection

The verification should detect and report:
1. Missing or duplicate months in the range
2. Dates not in "YYYY-MM-01" format
3. Monthly net values that don't match the formula
4. Annual discrepancies (reported vs computed) > 0.01
5. Non-numeric values, null, or NaN

Error reporting format:
```
{
  "error_type": "missing_month | duplicate_month | invalid_date_format | monthly_net_mismatch | yearly_total_mismatch | invalid_value_type",
  "year": "YYYY",
  "month": "MM" (if applicable),
  "field": "field_name" (if applicable),
  "expected": value,
  "actual": value,
  "diff": value (if applicable)
}
```

## Proof Summary Format

The verification process must produce a single text block with the following structure:

```
=== SPRINT 11 YEARLY TOTALS PROOF ===
Nonce: <random 16 bytes base64>
Timestamp: <UTC ISO>

Datasets:
- cashflow_sample.json       SHA256=<hash>  bytes=<size>
- compare_with_totals.json   SHA256=<hash>  bytes=<size>
- report_ok.pdf              SHA256=<hash>  bytes=<size>

API Status:
- CASE DETECT:   200  case=<enum>
- CASHFLOW:      200  rows=<count>  range=<YYYY-MM..YYYY-MM>
- COMPARE:       200  yearly_totals=present
- PDF:           200  magic=%PDF

Yearly Totals Validation:
Scenario <sid1>
  2025: months_expected=12 months_found=12  PASS
        inflow: reported=10000.00 computed=10000.00 diff=0.00
        outflow: reported=5000.00 computed=5000.00 diff=0.00
        add_income: reported=1200.00 computed=1200.00 diff=0.00
        cap_return: reported=500.00 computed=500.00 diff=0.00
        net: reported=6700.00 computed=6700.00 diff=0.00
Scenario <sid2>
  ...

Global Verdict: PASS
ZIP: artifacts/release-<timestamp>-s11.zip  SHA256=<hash>  bytes=<size>
=== END PROOF ===
```

If there are failures, the format should include:
```
Global Verdict: FAIL
Errors:
- Scenario <sid1>, Year 2025: missing_month=2025-03
- Scenario <sid1>, Year 2025: monthly_net_mismatch=2025-07 diff=12.34
- Scenario <sid2>, Year 2026: yearly_total_mismatch=net diff=45.67
...
```

Limited to the first 5 errors per scenario/year.

## Artifact Requirements

The verification process must:
1. Save all relevant input and output files
2. Calculate SHA256 hashes for all files
3. Package everything into a ZIP file
4. Include the ZIP location and hash in the proof summary

## Stability Gate Criteria

The "Stability Gate: Yearly Totals" is considered PASSED when:

1. All scenarios and years have PASS status according to the rules above
2. All artifacts and SHA256 hashes are included in the Proof Summary
3. All artifacts are packaged in the ZIP file
4. The PDF is valid (starts with %PDF)
5. The OpenAPI documentation includes all relevant endpoints

This verification must be self-contained and not depend on external servers.
