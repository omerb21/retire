# Retirement Benefits Calculator

## Backend Setup and Running

### Prerequisites
- Python 3.11+
- SQLite3

### Installation
1. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   .\venv\Scripts\activate  # On Windows
   source venv/bin/activate  # On Unix/macOS
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Initialize the database:
   ```bash
   alembic upgrade head
   ```

### Running the Backend
```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

## Frontend Setup

1. Set the API base URL in your frontend `.env` file:
   ```
   VITE_API_BASE_URL=http://localhost:8000
   ```

## API Endpoints

### Scenario Management
- `POST /api/v1/clients/{client_id}/scenarios` - Create new scenario
- `POST /api/v1/scenarios/{scenario_id}/run` - Run scenario calculation
- `GET /api/v1/clients/{client_id}/scenarios` - List client scenarios
- `GET /api/v1/scenarios/{scenario_id}` - Get scenario details

### Calculation
- `POST /api/v1/clients/{client_id}/calc` - Run direct calculation

## Smoke Test Scenarios

### Scenario A: Successful Calculation (200)
1. Create a new client
2. Create a current employment for the client
3. Before confirming termination, call `/calc` endpoint
   - Expected: HTTP 200 with calculation results

### Scenario B: Missing Employment Data (422)
1. Create a new client
2. Call `/calc` endpoint without setting up employment
   - Expected: HTTP 422 with error message "אין נתוני תעסוקה לחישוב"

### Scenario C: Scenario Creation and Execution
1. Create a new client with employment
2. Create a scenario with planning flags
3. Run the scenario
   - Expected: HTTP 200 with scenario results including cashflow projection

## Version
Current version: v0.5-stage5-green
