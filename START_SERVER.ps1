# Safe Server Start Script (PowerShell)
# Kills existing processes and starts clean server

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "🛡️  SAFE SERVER START - Killing existing processes first" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Kill all Python processes
Write-Host "🔍 Killing any existing Python processes..." -ForegroundColor Yellow
$pythonProcesses = Get-Process python -ErrorAction SilentlyContinue
if ($pythonProcesses) {
    $pythonProcesses | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-Host "✅ Python processes killed" -ForegroundColor Green
    Start-Sleep -Seconds 3
} else {
    Write-Host "✅ No Python processes found" -ForegroundColor Green
}

# Verify port is free
Write-Host "🔍 Verifying port 8005 is free..." -ForegroundColor Yellow
$portInUse = netstat -ano | Select-String ":8005.*LISTENING"
if ($portInUse) {
    Write-Host "⚠️  Port 8005 still in use, waiting..." -ForegroundColor Yellow
    Start-Sleep -Seconds 2
}

# Activate virtual environment
Write-Host ""
Write-Host "📦 Activating virtual environment..." -ForegroundColor Yellow
& ".\venv\Scripts\Activate.ps1"

# Start the server
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "🚀 Starting server on port 8005..." -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "📍 API Documentation: http://localhost:8005/docs" -ForegroundColor Green
Write-Host "📍 Health Check: http://localhost:8005/health" -ForegroundColor Green
Write-Host ""
Write-Host "⏹️  Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

python scripts\safe_server_start.py
