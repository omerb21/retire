# Testing Instructions for Frontend API Integration Fixes

This document provides step-by-step instructions for testing the frontend API integration fixes we've implemented.

## Prerequisites

1. Backend server running locally
2. Frontend development server running

## Setting Up the Environment

### 1. Start the Backend Server

```powershell
cd c:\Users\USER\OneDrive\AI PROJECTS\WINSURDF\dev\retire
python -m uvicorn app.main:app --reload
```

The backend server should start on http://localhost:8000

### 2. Start the Frontend Development Server

```powershell
cd c:\Users\USER\OneDrive\AI PROJECTS\WINSURDF\dev\retire\frontend
npm run dev
```

The frontend server should start on http://localhost:5173

## Test 1: Using the Frontend Client Form

1. Open your browser and navigate to http://localhost:5173/clients
2. Fill in the client form with the following test data:
   - ID Number: `123456782` (valid Israeli ID)
   - First Name: `ישראל`
   - Last Name: `ישראלי`
   - Birth Date: Select a date between 18-120 years ago (e.g., 1980-01-01)
   - Email: `test@example.com`
   - Phone: `0501234567`
3. Click "שמור" (Save)
4. Verify:
   - Success message appears
   - Client appears in the clients list below
   - All fields are displayed correctly in the table

## Test 2: Using the Direct HTML Test Page

1. Open the test HTML page in your browser:
   ```
   c:\Users\USER\OneDrive\AI PROJECTS\WINSURDF\dev\retire\test_client_direct.html
   ```

2. Fill in the client form with different test data:
   - ID Number: `305567663` (another valid Israeli ID)
   - First Name: `משה`
   - Last Name: `כהן`
   - Birth Date: Select a date between 18-120 years ago (e.g., 1990-01-01)
   - Email: `moshe@example.com`
   - Phone: `0521234567`
3. Click "צור לקוח" (Create Client)
4. Verify:
   - Success message appears
   - JSON response is displayed
   - Client appears in the clients list below

## Test 3: Using the Python Test Script

1. Open a PowerShell terminal
2. Run the Python test script:
   ```powershell
   cd c:\Users\USER\OneDrive\AI PROJECTS\WINSURDF\dev\retire
   python test_api_direct.py
   ```
3. Verify:
   - Script connects to the backend server
   - Client creation requests succeed
   - Clients list is displayed

## Test 4: Checking Browser Network Requests

1. Open your browser's Developer Tools (F12)
2. Go to the Network tab
3. Navigate to http://localhost:5173/clients
4. Fill in and submit the client form
5. Look for the POST request to `/api/v1/clients`
6. Verify:
   - Request payload contains the correct data
   - Response has status code 201 (Created)
   - Response body contains the created client data

## Test 5: Testing ID and Birth Date Validation

1. Go to http://localhost:5173/clients
2. Try submitting the form with an invalid ID (e.g., `123456789`)
3. Verify:
   - Error message appears about invalid ID
   - Form is not submitted

4. Try submitting with a birth date less than 18 years ago (e.g., today's date minus 10 years)
5. Verify:
   - Error message appears about invalid birth date (minimum age 18)
   - Form is not submitted

6. Try submitting with a birth date more than 120 years ago
7. Verify:
   - Error message appears about invalid birth date (maximum age 120)
   - Form is not submitted

## Test 6: Testing Required Fields

1. Go to http://localhost:5173/clients
2. Try submitting the form with some required fields empty
3. Verify:
   - Error message appears about required fields
   - Form is not submitted

## Troubleshooting

If you encounter issues:

1. **Backend Connection Issues**:
   - Verify backend server is running on http://localhost:8000
   - Check backend logs for errors
   - Test backend API directly with `curl` or Postman

2. **Frontend Form Issues**:
   - Check browser console for JavaScript errors
   - Verify form state in React DevTools
   - Check network requests in browser DevTools

3. **API Integration Issues**:
   - Verify Vite proxy configuration in `vite.config.ts`
   - Check `.env.development` for correct API base path
   - Test API endpoints directly with the test script

## Expected Results

After all tests, you should have:

1. Multiple clients created in the database
2. All clients displayed correctly in the frontend table
3. No errors in the browser console
4. Successful API responses in the network tab
