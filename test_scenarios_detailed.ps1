Write-Host "Testing Retirement Scenarios..." -ForegroundColor Cyan

$body = @{
    retirement_age = 67
} | ConvertTo-Json

try {
    $response = Invoke-WebRequest -Uri "http://localhost:8005/api/v1/clients/4/retirement-scenarios" `
        -Method POST `
        -ContentType "application/json" `
        -Body $body
    
    $json = $response.Content | ConvertFrom-Json
    
    Write-Host "`n========================================" -ForegroundColor Green
    Write-Host "SCENARIO 1: $($json.scenarios.scenario_1_max_pension.scenario_name)" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "Pension Monthly: $($json.scenarios.scenario_1_max_pension.total_pension_monthly) ILS"
    Write-Host "Capital: $($json.scenarios.scenario_1_max_pension.total_capital) ILS"
    Write-Host "Additional Income: $($json.scenarios.scenario_1_max_pension.total_additional_income_monthly) ILS"
    Write-Host "NPV: $($json.scenarios.scenario_1_max_pension.estimated_npv) ILS"
    Write-Host "Pension Funds: $($json.scenarios.scenario_1_max_pension.pension_funds_count)"
    Write-Host "Capital Assets: $($json.scenarios.scenario_1_max_pension.capital_assets_count)"
    
    Write-Host "`n========================================" -ForegroundColor Yellow
    Write-Host "SCENARIO 2: $($json.scenarios.scenario_2_max_capital.scenario_name)" -ForegroundColor Yellow
    Write-Host "========================================" -ForegroundColor Yellow
    Write-Host "Pension Monthly: $($json.scenarios.scenario_2_max_capital.total_pension_monthly) ILS"
    Write-Host "Capital: $($json.scenarios.scenario_2_max_capital.total_capital) ILS"
    Write-Host "Additional Income: $($json.scenarios.scenario_2_max_capital.total_additional_income_monthly) ILS"
    Write-Host "NPV: $($json.scenarios.scenario_2_max_capital.estimated_npv) ILS"
    Write-Host "Pension Funds: $($json.scenarios.scenario_2_max_capital.pension_funds_count)"
    Write-Host "Capital Assets: $($json.scenarios.scenario_2_max_capital.capital_assets_count)"
    
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "SCENARIO 3: $($json.scenarios.scenario_3_max_npv.scenario_name)" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "Pension Monthly: $($json.scenarios.scenario_3_max_npv.total_pension_monthly) ILS"
    Write-Host "Capital: $($json.scenarios.scenario_3_max_npv.total_capital) ILS"
    Write-Host "Additional Income: $($json.scenarios.scenario_3_max_npv.total_additional_income_monthly) ILS"
    Write-Host "NPV: $($json.scenarios.scenario_3_max_npv.estimated_npv) ILS"
    Write-Host "Pension Funds: $($json.scenarios.scenario_3_max_npv.pension_funds_count)"
    Write-Host "Capital Assets: $($json.scenarios.scenario_3_max_npv.capital_assets_count)"
    
    Write-Host "`n========================================" -ForegroundColor Magenta
    Write-Host "NPV COMPARISON" -ForegroundColor Magenta
    Write-Host "========================================" -ForegroundColor Magenta
    $npv1 = $json.scenarios.scenario_1_max_pension.estimated_npv
    $npv2 = $json.scenarios.scenario_2_max_capital.estimated_npv
    $npv3 = $json.scenarios.scenario_3_max_npv.estimated_npv
    
    $maxNPV = [Math]::Max([Math]::Max($npv1, $npv2), $npv3)
    
    if ($npv1 -eq $maxNPV) { Write-Host "WINNER: Scenario 1 (Max Pension) with NPV: $npv1" -ForegroundColor Green }
    if ($npv2 -eq $maxNPV) { Write-Host "WINNER: Scenario 2 (Max Capital) with NPV: $npv2" -ForegroundColor Green }
    if ($npv3 -eq $maxNPV) { Write-Host "WINNER: Scenario 3 (Max NPV) with NPV: $npv3" -ForegroundColor Green }
    
    if ($npv3 -lt $maxNPV) {
        Write-Host "ERROR: Scenario 3 (Max NPV) does not have the highest NPV!" -ForegroundColor Red
        Write-Host "Expected: >= $maxNPV, Got: $npv3" -ForegroundColor Red
    }
    
    if ($json.scenarios.scenario_2_max_capital.total_pension_monthly -lt 5500) {
        Write-Host "ERROR: Scenario 2 violates minimum pension rule (5500 ILS)!" -ForegroundColor Red
        Write-Host "Current pension: $($json.scenarios.scenario_2_max_capital.total_pension_monthly)" -ForegroundColor Red
    }
    
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
}
