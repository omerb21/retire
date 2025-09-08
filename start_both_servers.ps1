# Kill existing Python processes
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

Write-Host "Starting API server on port 8000..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-Command", "cd 'C:\Users\USER\OneDrive\AI PROJECTS\WINSURDF\dev\retire'; python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload" -WindowStyle Normal

Start-Sleep -Seconds 5

Write-Host "Starting frontend server on port 8001..." -ForegroundColor Green  
Start-Process powershell -ArgumentList "-Command", "cd 'C:\Users\USER\OneDrive\AI PROJECTS\WINSURDF\dev\retire\frontend\public'; python -m http.server 8001" -WindowStyle Normal

Start-Sleep -Seconds 3

Write-Host "Testing API server..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/health" -TimeoutSec 10
    Write-Host "✓ API server is responding" -ForegroundColor Green
} catch {
    Write-Host "✗ API server is not responding: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "Testing frontend server..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:8001" -TimeoutSec 10
    Write-Host "✓ Frontend server is responding" -ForegroundColor Green
} catch {
    Write-Host "✗ Frontend server is not responding: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""
Write-Host "Servers started!" -ForegroundColor Green
Write-Host "API: http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host "Frontend: http://127.0.0.1:8001/api_verification_clean.html" -ForegroundColor Cyan
