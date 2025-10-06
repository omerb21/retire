# Canonical Test Run Instructions

## Overview
This document provides instructions for running the canonical test suite for the retirement planning system.

## Prerequisites
1. Python environment with required packages installed
2. PostgreSQL database running (if using database features)
3. API server running on localhost:8000

## Test Scripts

### 1. New Canonical Test (new_canonical_test.py)
**Purpose**: Full integration test of the new FastAPI system
**Flow**: create client → create employer → create scenario → generate cashflow → export PDF → consistency check → create ZIP

**Usage**:
```bash
# Start API server first
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Run canonical test
python new_canonical_test.py
```

**Expected Output**:
- Client creation: PASS
- Employer creation: PASS  
- Scenario with cashflow: PASS (12 months)
- PDF generation: PASS (>1KB, valid PDF)
- Consistency check: PASS (difference ≤ 0.01)
- ZIP creation: PASS with SHA256

### 2. Legacy Canonical Test (quick_canonical_test.py)
**Purpose**: Tests existing Sprint11 system endpoints
**Usage**: 
```bash
python quick_canonical_test.py
```

## Artifacts Generated

Each test run creates timestamped artifacts in the `artifacts/` directory:

### New System Artifacts:
- `cashflow_YYYYMMDD_HHMMSS.json` - Generated cashflow data
- `test_report_YYYYMMDD_HHMMSS.pdf` - PDF report
- `consistency_check_YYYYMMDD_HHMMSS.txt` - Numeric consistency verification
- `canonical_test_artifacts_YYYYMMDD_HHMMSS.zip` - All artifacts packaged
- `zip_sha256_YYYYMMDD_HHMMSS.txt` - SHA256 checksum
- `canonical_run_YYYYMMDD_HHMMSS.json` - Test results summary
- `commit_sha.txt` - Current commit SHA

### Legacy System Artifacts:
- `cashflow_live_YYYYMMDD_HHMMSS.json`
- `compare_live_YYYYMMDD_HHMMSS.json`
- `test_YYYYMMDD_HHMMSS.pdf`
- `yearly_totals_verification_YYYYMMDD_HHMMSS.zip`

## Success Criteria

### For PASS verdict:
1. **API Health**: Server responds to health check
2. **Client Creation**: POST /clients creates client successfully
3. **Employer Creation**: POST /clients/{id}/current-employer works
4. **Scenario Creation**: POST /clients/{id}/scenarios generates cashflow
5. **Month Count**: Cashflow contains exactly 12 months
6. **PDF Generation**: Creates valid PDF file >1KB starting with %PDF
7. **Consistency Check**: |sum(monthly.net) - yearly.net| ≤ 0.01
8. **ZIP Creation**: Successfully packages all artifacts with SHA256

### For FAIL verdict:
- Any of the above steps fails
- API server not responding
- Invalid data structures returned
- File generation errors

## Troubleshooting

### Common Issues:

1. **Connection Refused**
   - Ensure API server is running: `uvicorn app.main:app --reload --port 8000`
   - Check firewall settings
   - Verify port 8000 is available

2. **Import Errors**
   - Ensure all dependencies installed: `pip install -r requirements.txt`
   - Check Python path includes project root
   - Verify ReportLab installed for PDF generation

3. **Database Errors**
   - Run migration: `psql -f migrations/001_init.sql`
   - Check database connection settings
   - Ensure PostgreSQL service running

4. **PDF Generation Fails**
   - Install ReportLab: `pip install reportlab`
   - Check file permissions in artifacts directory
   - Verify sufficient disk space

## Manual Verification

After successful run, manually verify:

1. **PDF File**: Open generated PDF, confirm it displays properly
2. **Cashflow Data**: Check JSON contains 12 monthly entries
3. **Consistency**: Verify monthly totals sum equals yearly total
4. **ZIP Archive**: Extract and verify all files present

## Integration with CI/CD

For automated testing:
```bash
#!/bin/bash
# Start server in background
uvicorn app.main:app --host 127.0.0.1 --port 8000 &
SERVER_PID=$!

# Wait for server to start
sleep 5

# Run test
python new_canonical_test.py
TEST_RESULT=$?

# Cleanup
kill $SERVER_PID

# Exit with test result
exit $TEST_RESULT
```

## Commit Requirements

Before running canonical tests:
1. Commit all changes locally
2. Update commit SHA in test script if needed
3. Ensure working directory is clean
4. Tag important releases after successful runs
