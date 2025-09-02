# Frontend API Integration Fixes

## Summary of Changes

We've fixed several frontend API integration issues to ensure proper communication with the backend. Here's a summary of the changes made:

### 1. API Wrapper (`src/lib/api.ts`)

- Removed all mock implementations of `createClient`, `getClient`, and `listClients`
- Restored real API calls using relative paths (`/api/v1/clients`)
- Removed hardcoded valid Israeli ID test values from ID validation logic
- Modified `createClient` to send the original user-inputted ID as `id_number_raw` along with normalized `id_number`
- Added console logging of payloads for debugging

### 2. Client Form Components

- Updated `Clients.tsx` and `ClientForm.tsx` to use separate fields: `id_number`, `first_name`, `last_name`, `birth_date`, etc.
- Removed use of combined `full_name` field
- Updated form inputs to be controlled components bound to state fields
- Added proper validation for required fields
- Fixed form submission to send correct data to the API
- Updated client table display to show all fields properly

### 3. Testing Tools

- Created `test_client_direct.html` - a standalone HTML page to test client creation directly
- Created `test_api_direct.py` - a Python script to test the API endpoints

## Testing Procedures

### Backend Server Setup

1. Start the backend server:
   ```
   python -m uvicorn app.main:app --reload
   ```
   
2. Verify the server is running by accessing:
   - Health check: http://localhost:8000/api/v1/health
   - Swagger docs: http://localhost:8000/docs

### Frontend Testing

1. Start the frontend development server:
   ```
   cd frontend
   npm run dev
   ```

2. Open the browser to the frontend URL (typically http://localhost:5173)

3. Test client creation:
   - Fill in the client form with valid data
   - Submit the form
   - Verify in browser DevTools (Network tab) that:
     - The POST request is sent to `/api/v1/clients`
     - The payload contains the correct user input
     - The response is successful (201 Created)
   - Verify the client appears in the clients list

### Direct API Testing

1. Run the Python test script:
   ```
   python test_api_direct.py
   ```
   This will:
   - Test creating clients with different valid Israeli IDs
   - List all clients
   - Display any errors

2. Open `test_client_direct.html` in a browser to:
   - Test client creation with a user-friendly form
   - View the clients list
   - See detailed API responses

## Israeli ID Validation

The Israeli ID validation algorithm is now implemented identically in both frontend and backend:

1. Remove non-digits and trim
2. Zero-pad to 9 digits
3. Calculate checksum using the Israeli algorithm
4. Validate that sum % 10 === 0

This ensures consistent validation behavior while preserving the original user input.

## Recent API Integration Fixes

### 4. Pension Fund Creation

- Fixed pension fund payload structure to match backend schema requirements:
  - Changed `calculation_mode` to `input_mode` (values: "calculated" or "manual")
  - Added required `fund_name` field
  - Changed `monthly_amount` to `pension_amount` for manual mode
  - Changed `indexation_rate` to `fixed_index_rate` for fixed indexation
  - Ensured `client_id` is sent as a number, not a string
  - Properly formatted `pension_start_date` as ISO string

### 5. Fixation Compute Endpoint

- Fixed fixation compute endpoint path:
  - Changed from incorrect `/fixation/compute/{clientId}` to correct `/fixation/{clientId}/compute`
  - Removed trailing slash that caused 404 errors
  - Added proper error handling and response parsing

### 6. Scenarios Integration

- Fixed scenarios integration flow:
  - Updated scenario creation payload to include required fields: `scenario_name`, `monthly_expenses`, and planning flags
  - Added auto-selection of the first scenario after loading scenarios
  - Updated scenario creation to select the newly created scenario automatically
  - Added `scenario_id` query parameter to integration API calls
  - Maintained validation to ensure a scenario is selected before integration calls

### 7. Testing Tools

- Created `api_verification.html` - a comprehensive test page for all API fixes
- Created `test_api_fixes_direct.js` - a Node.js script to test API endpoints
- Created `test_api_fixes.ps1` - a PowerShell script for API testing

## Troubleshooting

If you encounter issues:

1. Check browser console for JavaScript errors
2. Verify network requests in DevTools
3. Ensure backend server is running
4. Check backend logs for validation errors
5. Verify Vite proxy configuration in `vite.config.ts`
6. Use the API verification tools to test endpoints directly

## Environment Configuration

- Frontend environment variables are in `.env.development`
- API base path is set to `/api/v1`
- Vite proxy forwards `/api` requests to `http://127.0.0.1:8000`
- Date fields are aligned to the first day of the month and formatted as ISO strings
- Numeric fields are sent as numbers, not strings
