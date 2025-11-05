# 🔌 Port Configuration - CRITICAL

## ⚠️ STANDARD PORTS - DO NOT CHANGE

The system uses the following **FIXED** ports:

- **Frontend (Vite)**: `3000`
- **Backend (FastAPI)**: `8005`

---

## 🎯 Why Port 8005?

Port `8005` is the **OFFICIAL** backend port for this project. All configuration files, documentation, and code references use this port.

**DO NOT use port 8000** - it was used in early development but has been **DEPRECATED**.

---

## 📋 Configuration Files

### 1. Frontend Proxy Configuration
**File**: `frontend/vite.config.ts`

```typescript
proxy: {
  "/api": {
    target: "http://localhost:8005",  // ⚠️ MUST be 8005
    changeOrigin: true,
    secure: false,
  },
}
```

### 2. Backend Server
**Start command**:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8005
```

---

## 🔍 Verification

After starting the servers, verify they're running on correct ports:

```bash
# Check backend
curl http://localhost:8005/health

# Check frontend
curl http://localhost:3000
```

---

## 📝 Files Updated (Oct 24, 2025)

All references to port `8000` have been replaced with `8005` in:

### Documentation:
- ✅ `README.md`
- ✅ `RETIREMENT_AGE_IMPLEMENTATION.md`
- ✅ `RESTART_SERVER_NOW.md`
- ✅ `frontend/README.md`
- ✅ `docs/INSTALL.md`

### Code:
- ✅ `frontend/vite.config.ts` (already correct)
- ✅ `app/routers/report_generation.py`

### Scripts:
- ✅ `test_fixation.py`
- ✅ `scripts/create_deliverable.py`
- ✅ `scripts/sprint11_closure.py`
- ✅ `scripts/sprint11_finalize.py`
- ✅ `scripts/sprint11_finalize_fixed.py`

---

## 🚨 IMPORTANT NOTES

1. **Frontend proxy is already configured correctly** in `vite.config.ts` - it points to port `8005`
2. **Always start the backend on port 8005** using the command above
3. **Never hardcode port 8000** in any new code or documentation
4. **This document is the source of truth** for port configuration

---

## 🔧 Troubleshooting

### Problem: 404 errors or "Failed to fetch"
**Solution**: Verify backend is running on port `8005`:
```bash
# Windows
netstat -ano | findstr :8005

# Should show: TCP 0.0.0.0:8005 LISTENING
```

### Problem: Port already in use
**Solution**: Kill the process using port 8005:
```bash
# Windows
netstat -ano | findstr :8005
# Note the PID (last column)
taskkill /PID <PID> /F
```

---

**Last Updated**: October 24, 2025  
**Status**: ✅ All files synchronized to port 8005
