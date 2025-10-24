# Installation Guide

## Prerequisites

- Python 3.11 or higher
- PostgreSQL (optional, SQLite used by default for development)

## Quick Start

1. **Clone and navigate to project directory:**
```powershell
cd C:\Users\USER\OneDrive\AI PROJECTS\WINSURDF\dev\retire
```

2. **Create virtual environment:**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3. **Install dependencies:**
```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

4. **Run database migrations:**
```powershell
alembic upgrade head
```

5. **Run tests:**
```powershell
pytest -q
```

6. **Start the server:**
```powershell
uvicorn main:app --reload --port 8005
```

7. **Test endpoints:**
```powershell
Invoke-RestMethod http://localhost:8005/clients
```

## Environment Variables

Create `.env` file with:
```
DATABASE_URL=sqlite:///./dev.db
# For PostgreSQL: DATABASE_URL=postgresql://user:password@localhost/retire
```

## API Endpoints

- `GET /clients` - List all clients
- `POST /clients` - Create new client
- `GET /clients/{id}` - Get specific client
- `PUT /clients/{id}` - Update client
- `DELETE /clients/{id}` - Delete client

## Example Client Creation

```json
{
  "id_number_raw": "123456789",
  "full_name": "John Doe",
  "sex": "M",
  "marital_status": "Married",
  "address_city": "Tel Aviv",
  "employer_name": "Tech Corp"
}
```
