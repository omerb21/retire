$body = @{
    retirement_age = 67
} | ConvertTo-Json

$response = Invoke-WebRequest -Uri "http://localhost:8005/api/v1/clients/4/retirement-scenarios" `
    -Method POST `
    -ContentType "application/json" `
    -Body $body

$json = $response.Content | ConvertFrom-Json

Write-Host "`n=== SCENARIO 1: $($json.scenarios.scenario_1_max_pension.scenario_name) ===" -ForegroundColor Green
Write-Host "Pension: $($json.scenarios.scenario_1_max_pension.total_pension_monthly)"
Write-Host "Capital: $($json.scenarios.scenario_1_max_pension.total_capital)"
Write-Host "NPV: $($json.scenarios.scenario_1_max_pension.estimated_npv)"

Write-Host "`n=== SCENARIO 2: $($json.scenarios.scenario_2_max_capital.scenario_name) ===" -ForegroundColor Yellow
Write-Host "Pension: $($json.scenarios.scenario_2_max_capital.total_pension_monthly)"
Write-Host "Capital: $($json.scenarios.scenario_2_max_capital.total_capital)"
Write-Host "NPV: $($json.scenarios.scenario_2_max_capital.estimated_npv)"

Write-Host "`n=== SCENARIO 3: $($json.scenarios.scenario_3_max_npv.scenario_name) ===" -ForegroundColor Cyan
Write-Host "Pension: $($json.scenarios.scenario_3_max_npv.total_pension_monthly)"
Write-Host "Capital: $($json.scenarios.scenario_3_max_npv.total_capital)"
Write-Host "NPV: $($json.scenarios.scenario_3_max_npv.estimated_npv)"
Write-Host ""
