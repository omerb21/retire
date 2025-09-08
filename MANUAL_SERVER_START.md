# Manual Server Startup Instructions

The automated server startup is not working reliably. Please start the servers manually:

## Step 1: Start API Server
Open a new PowerShell terminal and run:
```powershell
cd "C:\Users\USER\OneDrive\AI PROJECTS\WINSURDF\dev\retire"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Wait for the message: "Uvicorn running on http://127.0.0.1:8000"

## Step 2: Start Frontend Server  
Open another PowerShell terminal and run:
```powershell
cd "C:\Users\USER\OneDrive\AI PROJECTS\WINSURDF\dev\retire\frontend\public"
python -m http.server 8001
```

Wait for the message: "Serving HTTP on :: port 8001"

## Step 3: Test API
In a third terminal, test the API:
```powershell
python test_compare_api_direct.py
```

This should show "✓ SUCCESS: 12 months returned as expected"

## Step 4: Test Frontend
Open browser to: http://127.0.0.1:8001/api_verification_clean.html

- Enter Client ID: 1
- Enter Scenario ID: 24  
- Click "אמת סיכומים שנתיים"
- Should show "Months: 12/12" and "Result: PASS"

## Current Issue
The frontend verification tool is still showing 3/12 months despite the backend fix. The ytv-core.js has been modified to force real data mode for debugging.

## Files Modified
- `app/services/cashflow_service.py` - Fixed to return 12 months instead of skipping empty months
- `frontend/public/ytv-core.js` - Forced to use real API data instead of mock data
- `frontend/public/ytv-data-fix.js` - Added data fixing module
- `frontend/public/ytv-mock-pdf.js` - Added PDF mock module
