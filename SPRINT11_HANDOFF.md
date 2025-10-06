# Sprint 11 Handoff Document - Yearly Totals Verification

## Current Status Summary

### ✅ Completed
- **Case Detection**: Router + service + tests implemented
- **Full Month Grid**: `ensure_full_month_grid` in cashflow_service.py working (12/12 months)
- **Net Calculation**: Fixed to include `capital_return_net` in both monthly and yearly totals
- **isinstance Fixes**: Resolved runtime type errors (`datetime.date` → `date`)
- **Decimal Precision**: Implemented proper `_to_decimal`, `_round2`, `_compute_yearly_from_months`
- **API Structure**: `compare_scenarios` returns correct format with `scenarios[]` and `yearly_totals`
- **Clean UI Architecture**: Modular `api_verification_clean.html` + `ytv-core.js`

### ❌ Outstanding Issues
1. **Data Source Inconsistency**: Artifacts show old/partial data vs live API
2. **PDF Generation Error**: "Invalid URI: The hostname could not be parsed"
3. **Units/Scaling**: Large values suggest unit mismatch (₪ vs ₪*1000 vs agorot)
4. **Proof Still FAIL**: Likely using stale artifacts instead of fresh API data

## Technical Details

### Files Modified
```
app/services/compare_service.py     - isinstance fix, decimal precision, new structure
app/services/cashflow_service.py    - ensure_full_month_grid implementation
app/utils/contract_adapter.py       - response format standardization
app/routers/scenario_compare.py     - direct service call, JSONResponse
frontend/public/api_verification_clean.html - clean modular UI
frontend/public/ytv-core.js         - single source of truth logic
```

### Key Functions Fixed
```python
# compare_service.py
def _to_decimal(v: Any) -> Decimal:          # Handles None/empty values
def _round2(v: Decimal) -> float:            # Precise 2-decimal rounding
def _compute_yearly_from_months(monthly_rows): # Consistent yearly calculation
def compare_scenarios(...) -> Dict[str, Any]: # Returns scenarios[] format

# cashflow_service.py  
def ensure_full_month_grid(rows, from_ym, to_ym): # 12-month completion
```

### Expected API Response Structure
```json
{
  "scenarios": [
    {
      "scenario_id": 24,
      "monthly": [
        {
          "date": "2025-01-01",
          "inflow": 2625.0,
          "outflow": 2058.33,
          "additional_income_net": 137.5,
          "capital_return_net": 54.17,
          "net": 758.34
        }
        // ... 11 more months
      ],
      "yearly_totals": {
        "2025": {
          "inflow": 31500.0,
          "outflow": 24700.0,
          "additional_income_net": 1650.0,
          "capital_return_net": 650.0,
          "net": 9100.0
        }
      }
    }
  ],
  "meta": {
    "client_id": 1,
    "from": "2025-01",
    "to": "2025-12",
    "frequency": "monthly"
  }
}
```

## Critical Issues to Resolve

### 1. Data Source Inconsistency
**Problem**: UI/artifacts show different data than live API
**Root Cause**: Artifacts generated from stale data or different calculation path
**Solution**: Ensure artifact generation uses same API calls as verification

### 2. PDF Generation Error
**Problem**: `Invalid URI: The hostname could not be parsed`
**Investigation Needed**: 
- Check uvicorn logs for full stacktrace
- Identify which asset/URL is malformed
- Add URL validation before PDF generation

### 3. Units/Scaling Mismatch
**Problem**: Values in millions suggest unit inconsistency
**Decision Needed**: Standardize on ₪ (shekels) throughout system
**Implementation**: Add unit normalization at service boundaries

## Immediate Next Steps

### Phase 1: Diagnostic (30 min)
1. Start uvicorn server with full logging
2. Run API calls and capture exact responses
3. Generate fresh artifacts and compare with API data
4. Identify PDF generation failure point

### Phase 2: Fix Data Consistency (1 hour)
1. Ensure UI uses live API data, not cached artifacts
2. Implement single source of truth for calculations
3. Add unit normalization layer

### Phase 3: Integration Test (30 min)
1. Create end-to-end test script
2. Verify: monthly count = 12, sum(monthly.net) = yearly.net
3. Generate proof summary with PASS verdict

## Test Commands

### Manual API Testing
```powershell
# Test cashflow endpoint
$BASE="http://127.0.0.1:8000"; $CID=1; $SID=24
$body = @{ from="2025-01"; to="2025-12"; frequency="monthly" } | ConvertTo-Json
$cashflow = Invoke-RestMethod -Method POST -Uri "$BASE/api/v1/scenarios/$SID/cashflow/generate?client_id=$CID" -ContentType "application/json" -Body $body
Write-Host "Cashflow months: $($cashflow.Count)"

# Test compare endpoint  
$body = @{ scenarios=@($SID); from="2025-01"; to="2025-12"; frequency="monthly" } | ConvertTo-Json
$compare = Invoke-RestMethod -Method POST -Uri "$BASE/api/v1/clients/$CID/scenarios/compare" -ContentType "application/json" -Body $body
Write-Host "Compare structure: scenarios[$($compare.scenarios.Count)], monthly[$($compare.scenarios[0].monthly.Count)]"
Write-Host "Yearly net: $($compare.scenarios[0].yearly_totals['2025'].net)"
```

### Expected Results
- Cashflow months: 12
- Compare structure: scenarios[1], monthly[12]  
- Yearly net: 9100.0 (or consistent with monthly sum)

## Success Criteria for Sprint Closure

### Technical Validation
- [ ] API returns 12 months consistently
- [ ] `sum(monthly.net) == yearly_totals.net` (within 0.01 tolerance)
- [ ] PDF generation succeeds without URI errors
- [ ] Units consistent across all endpoints

### Proof Summary Requirements
```
=== YEARLY TOTALS VERIFICATION PROOF SUMMARY ===
...
--- YEARLY TOTALS VALIDATION ---
Scenario 24: PASS
  Year 2025: PASS
    Months: 12/12
    net: reported=9100.00, computed=9100.00, diff=0.00

--- GLOBAL VERDICT ---
Result: PASS
```

## Handoff Checklist

- [ ] All isinstance errors resolved
- [ ] API returns consistent 12-month data
- [ ] Yearly totals calculation verified
- [ ] PDF generation error diagnosed and fixed
- [ ] Units normalized across system
- [ ] Fresh proof summary generated with PASS verdict
- [ ] Integration test script created and passing
- [ ] Documentation updated with final API structure

## Contact Points
- **Architecture**: Clean modular UI (ytv-core.js) eliminates HTML patch loops
- **Data Flow**: cashflow → compare → yearly_totals (single source of truth)
- **Precision**: Decimal arithmetic for financial calculations
- **Testing**: In-process TestClient reduces network dependencies

---
*Generated: 2025-09-07 Sprint 11 Closure Phase*
