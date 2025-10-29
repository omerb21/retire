# 🛡️ Server Startup Guide - Safe Process Management

## Problem Solved
Previously, the server would fail to start due to:
- Multiple Python processes listening on port 8005
- Processes not terminating properly
- Port conflicts causing "Address already in use" errors
- Wasted development time and API credits

## Solution: Safe Server Start

We've implemented **automatic process cleanup** that ensures:
✅ All existing Python processes are killed before startup
✅ Port 8005 is verified to be free
✅ Clean server startup every time
✅ No more port conflicts

---

## How to Start the Server

### Option 1: Batch File (Recommended for Windows)
```bash
START_SERVER.bat
```

### Option 2: PowerShell Script
```powershell
.\START_SERVER.ps1
```

### Option 3: Python Script (Manual)
```bash
python scripts/safe_server_start.py
```

### Option 4: Direct Command (Not Recommended)
```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8005
```

---

## What Happens When You Start

1. **Process Cleanup** 🔍
   - Detects all Python processes on port 8005
   - Kills them forcefully
   - Waits 3 seconds for cleanup

2. **Port Verification** ✅
   - Confirms port 8005 is free
   - Retries if port is still in use

3. **Server Startup** 🚀
   - Activates virtual environment
   - Starts Uvicorn with reload enabled
   - Server ready at `http://localhost:8005`

---

## Server Endpoints

| Endpoint | Purpose |
|----------|---------|
| `http://localhost:8005` | API Root |
| `http://localhost:8005/docs` | **Swagger UI (Interactive API Docs)** |
| `http://localhost:8005/redoc` | ReDoc (Alternative API Docs) |
| `http://localhost:8005/health` | Health Check |

---

## Troubleshooting

### Server Still Won't Start
1. **Manual Process Kill**
   ```powershell
   Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
   ```

2. **Check Port Status**
   ```powershell
   netstat -ano | findstr :8005
   ```

3. **Force Kill by PID**
   ```powershell
   taskkill /PID <PID> /F /T
   ```

### Port 8005 Still in Use
```powershell
# Find what's using the port
netstat -ano | findstr :8005

# Kill the process (replace XXXX with PID)
taskkill /PID XXXX /F /T
```

### Virtual Environment Issues
```bash
# Recreate venv
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

---

## Important Notes

⚠️ **DO NOT** use `redirect_slashes=False` in FastAPI - it breaks all routes
⚠️ **DO NOT** manually start multiple server instances
✅ **ALWAYS** use `START_SERVER.bat` or `START_SERVER.ps1`
✅ **ALWAYS** wait for "Application startup complete" message

---

## Files Involved

- `START_SERVER.bat` - Batch file for Windows (Recommended)
- `START_SERVER.ps1` - PowerShell script
- `scripts/safe_server_start.py` - Python cleanup script
- `app/main.py` - FastAPI application entry point
- `venv/` - Virtual environment

---

## Backend Port Configuration

**Standard Port**: `8005`
**Frontend Proxy**: Points to `http://localhost:8005`
**Never use port 8000** - it's deprecated

---

Last Updated: October 29, 2025
