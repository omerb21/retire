# Start services script for API and frontend verification
# This script starts both the API server and static file server

# Kill any existing Python processes that might be using the ports
Write-Host "Terminating any existing Python processes..."
taskkill /F /IM python.exe 2>$null

# Wait for processes to terminate
Start-Sleep -Seconds 2

# Start API server (uvicorn)
Write-Host "Starting API server at http://127.0.0.1:8000 ..."
Start-Process powershell -ArgumentList "-Command python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

# Wait for API server to initialize
Write-Host "Waiting for API server to initialize..."
Start-Sleep -Seconds 3

# Start static file server for frontend
$frontendPath = Join-Path $PSScriptRoot "frontend\public"
Write-Host "Starting static file server at http://127.0.0.1:8001 ..."
Write-Host "Serving files from: $frontendPath"
Start-Process powershell -ArgumentList "-Command cd '$frontendPath'; python -m http.server 8001"

# Final instructions
Write-Host "`nServices started successfully!"
Write-Host "API server: http://127.0.0.1:8000"
Write-Host "Frontend verification tool: http://127.0.0.1:8001/api_verification_clean.html"
Write-Host "`nTest PDF endpoint:"
Write-Host '$headers = @{ "Content-Type" = "application/json" }; $body = @{ from="2025-01"; to="2025-12"; frequency="monthly" } | ConvertTo-Json; Invoke-RestMethod -Method POST -Uri "http://127.0.0.1:8000/api/v1/scenarios/24/report/pdf?client_id=1" -Headers $headers -Body $body -OutFile test.pdf'
Write-Host "`nTo stop services, run: taskkill /F /IM python.exe"
