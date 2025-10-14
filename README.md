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

## Pension Portfolio Processing

### File Format Support

The system supports processing pension portfolio data files in two formats:
- **XML files** - Standard XML format from clearing house (מסלקה)
- **DAT files** - Manipulated XML files with DAT extension

### Processing Features

1. **Multi-encoding Support**: Automatically detects and handles various text encodings:
   - UTF-8
   - Windows-1255 (Hebrew)
   - ISO-8859-8
   - Latin1

2. **Robust XML Parsing**: Three-tier parsing strategy:
   - **Tier 1**: Direct XML parsing
   - **Tier 2**: XML repair and retry (handles common DAT file issues)
   - **Tier 3**: Regex fallback extraction for severely malformed files

3. **Data Extraction**: Automatically extracts:
   - Account numbers and plan names
   - Managing companies
   - Balances and dates
   - Product types (pension fund, insurance policy, provident fund, education fund)
   - Compensation components (current employer, after settlement, etc.)
   - Benefits by period (pre-2000, post-2000, post-2008)

### API Endpoint

```bash
# Process XML/DAT files
POST /api/v1/clients/{client_id}/pension-portfolio/process-xml

# Upload multiple files
curl -X POST "http://localhost:8000/api/v1/clients/1/pension-portfolio/process-xml" \
     -F "files=@file1.xml" \
     -F "files=@file2.dat"
```

**Response:**
```json
{
  "total_accounts": 15,
  "processed_files_count": 2,
  "skipped_files_count": 0,
  "processed_files": [
    {
      "file": "pension_data.xml",
      "file_type": "XML",
      "accounts_count": 8,
      "processed_at": "2025-01-14T15:30:00"
    },
    {
      "file": "pension_data.dat",
      "file_type": "DAT",
      "accounts_count": 7,
      "processed_at": "2025-01-14T15:30:01"
    }
  ],
  "accounts": [...]
}
```

### Frontend Usage

In the Pension Portfolio page (`/clients/{id}/pension-portfolio`):
1. Click "בחר קבצים" to select XML or DAT files
2. System accepts both `.xml` and `.dat` extensions
3. Processing status shown in real-time
4. Results displayed in interactive table

### Error Handling

The system provides detailed error messages for:
- **Unsupported file types**: Clear message about accepted formats
- **Encoding issues**: Tries multiple encodings before failing
- **Parse errors**: Attempts repair and fallback extraction
- **Malformed files**: Specific error details for debugging

## Fixation API

The Fixation API provides rights fixation calculations for clients.

### Compute Rights Fixation

Calculate exempt capital remaining and used commutation for a client:

```bash
# Basic computation
curl -X POST "http://localhost:8000/api/v1/fixation/1/compute" \
     -H "Content-Type: application/json"

# With optional parameters
curl -X POST "http://localhost:8000/api/v1/fixation/1/compute" \
     -H "Content-Type: application/json" \
     -d '{
       "scenario_id": 2,
       "params": {
         "custom_param": "value"
       }
     }'
```

**Response:**
```json
{
  "client_id": 1,
  "persisted_id": 123,
  "outputs": {
    "exempt_capital_remaining": 0.0,
    "used_commutation": 0.0,
    "annex_161d_ready": false
  },
  "engine_version": "fixation-sprint2-1"
}
```

**Key Fields:**
- `client_id`: Client identifier
- `persisted_id`: Database record ID for this calculation
- `outputs.exempt_capital_remaining`: Remaining exempt capital amount
- `outputs.used_commutation`: Amount of commutation used
- `outputs.annex_161d_ready`: Whether 161d form data is ready
- `engine_version`: Calculation engine version

## Version
Current version: v0.5-stage5-green
