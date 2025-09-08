# Sprint 11 Final Checklist - Critical Path to PASS

## Immediate Actions Required (Next 2 Hours)

### 1. Diagnose PDF Error (30 min)
```bash
# Start server with full logging
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level debug

# Test PDF endpoint and capture full error
curl -X POST "http://127.0.0.1:8000/api/v1/clients/1/scenarios/24/report/pdf" \
  -H "Content-Type: application/json" \
  -d '{"from":"2025-01","to":"2025-12","sections":["summary","cashflow"]}'
```

**Expected Issue**: URL/asset path in PDF template is malformed
**Fix**: Add URL validation in report_service.py

### 2. Data Source Consistency (45 min)
```powershell
# Capture live API data
$BASE="http://127.0.0.1:8000"; $CID=1; $SID=24

# Get fresh cashflow
$cashflow = Invoke-RestMethod -Method POST -Uri "$BASE/api/v1/scenarios/$SID/cashflow/generate?client_id=$CID" -ContentType "application/json" -Body '{"from":"2025-01","to":"2025-12","frequency":"monthly"}'

# Get fresh compare
$compare = Invoke-RestMethod -Method POST -Uri "$BASE/api/v1/clients/$CID/scenarios/compare" -ContentType "application/json" -Body '{"scenarios":[24],"from":"2025-01","to":"2025-12","frequency":"monthly"}'

# Save to artifacts for comparison
$compare | ConvertTo-Json -Depth 8 | Out-File artifacts/live_compare_data.json -Encoding utf8
```

**Expected Finding**: Live API has correct 12/12 months, artifacts have 3/12
**Fix**: Ensure UI calls live API, not cached files

### 3. UI Data Source Fix (30 min)
**File**: `frontend/public/ytv-core.js`
**Issue**: UI reading from stale artifacts instead of live API
**Fix**: Force fresh API calls in verification process

### 4. Generate Fresh Proof (15 min)
- Run Yearly Totals Verification with Test Mode OFF
- Ensure it uses live API data
- Verify: Months: 12/12, net values consistent
- Expected: GLOBAL VERDICT: PASS

## Success Metrics

### Technical Validation
- [ ] `cashflow.Count == 12`
- [ ] `compare.scenarios[0].monthly.length == 12`
- [ ] `sum(monthly.net) == yearly_totals.net` (±0.01)
- [ ] PDF generates without URI error
- [ ] Proof shows "Months: 12/12"
- [ ] Global verdict: PASS

### Proof Summary Format
```
--- YEARLY TOTALS VALIDATION ---
Scenario 24: PASS
  Year 2025: PASS
    Months: 12/12
    net: reported=9100.00, computed=9100.00, diff=0.00

--- GLOBAL VERDICT ---
Result: PASS
```

## Risk Mitigation

### If PDF Still Fails
- Document the specific error
- Generate proof without PDF component
- Mark as known issue for next sprint

### If Data Still Inconsistent
- Check database state
- Verify case detection returns correct case_id
- Ensure generate_cashflow uses case_id parameter

### If Units Still Wrong
- Add logging to identify scaling factor
- Normalize at API boundary
- Document expected units (₪ vs ₪*1000)

## Handoff Package

### Files Ready
- [x] `SPRINT11_HANDOFF.md` - Complete status document
- [x] `sprint11_integration_test.py` - End-to-end test script
- [x] `test_compare_fix.py` - isinstance validation
- [x] Modified services with fixes applied

### Documentation
- [x] Technical details of all fixes
- [x] Expected API response structure
- [x] Test commands and success criteria
- [x] Outstanding issues clearly identified

## Final Validation Command
```bash
python sprint11_integration_test.py
```
**Expected Output**: "✓ INTEGRATION TEST PASSED"

---
**Sprint 11 Status**: 90% Complete - Critical path identified for final 10%
