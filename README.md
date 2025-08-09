# Retirement Benefits Calculator

## Repository Structure

This repository contains the following main components:

- **Main Application**: Backend API and calculation engine
- **Frontend**: React-based user interface
- **Rights Fixation System**: Separate submodule for rights fixation functionality

## PDF Smoke Test

To verify the PDF generation functionality, run the smoke test script:

```powershell
# Set Python path and run the smoke test
$env:PYTHONPATH="$PWD"
python tools/report_smoke.py

# Verify the PDF was generated
if (Test-Path .\report_smoke.pdf) {
    Write-Host "PDF generated successfully:"
    Get-Item .\report_smoke.pdf | Select-Object Name,Length,LastWriteTime
} else {
    Write-Host "PDF generation failed"
}
```

### Expected Output
- A `report_smoke.pdf` file should be generated in the project root
- File size should be >30KB (typically ~49KB)
- The PDF should contain client information, scenario details, and charts

### Troubleshooting
1. If you get a 422 error, ensure:
   - The database is properly initialized with `python create_db.py`
   - The client has active employment data
   - CPI data is available for the calculation period

2. If you see font warnings, they can be safely ignored as long as the PDF generates correctly.

## Backend Setup and Running

### Prerequisites
- Python 3.11+
- SQLite3
- Node.js 16+ (for frontend)

### Installation

#### Automated Installation (CI/Development)

Use the CI dependency installation script to set up all dependencies:

```powershell
# Install all dependencies
.\ci_install_deps.ps1

# Install only backend dependencies
.\ci_install_deps.ps1 -Backend

# Install only frontend dependencies
.\ci_install_deps.ps1 -Frontend

# Install only Rights Fixation System dependencies
.\ci_install_deps.ps1 -FixationSystem
```

#### Manual Installation

1. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   .\.venv\Scripts\activate  # On Windows
   source .venv/bin/activate  # On Unix/macOS
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

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Set the API base URL in your frontend `.env` file:
   ```
   VITE_API_BASE_URL=http://localhost:8000
   ```

4. Start the development server:
   ```bash
   npm run dev
   ```

## Repository Maintenance

### Cleanup Script

Use the cleanup script to remove unnecessary artifacts:

```bash
python clean.py
```

This will remove:
- Build artifacts
- Python cache files
- Node modules
- Temporary files

### Pre-commit Hooks

This repository uses pre-commit hooks for code quality checks. Install them with:

```bash
pip install pre-commit
pre-commit install
```

### Rights Fixation System as Submodule

The Rights Fixation System is maintained as a separate submodule. Use the setup script to configure it:

```powershell
# Dry run to see what would happen
.\setup_fixation_submodule.ps1 -DryRun

# Set up with a remote URL
.\setup_fixation_submodule.ps1 -RemoteUrl "https://your-git-repo-url.git"
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
