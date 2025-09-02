# Test script for API fixes
# This script tests the three fixed API endpoints:
# 1. Pension Fund Creation
# 2. Fixation Compute
# 3. Scenarios Integration

# Base URL for API
$baseUrl = "http://localhost:8000/api/v1"
$clientId = 1  # Change this if needed

Write-Host "API Fixes Test Script" -ForegroundColor Cyan
Write-Host "=====================" -ForegroundColor Cyan

# Function to make API calls
function Invoke-ApiCall {
    param (
        [string]$Endpoint,
        [string]$Method = "GET",
        [object]$Body = $null
    )
    
    $url = "$baseUrl$Endpoint"
    $headers = @{
        "Content-Type" = "application/json"
    }
    
    Write-Host "Calling $Method $url" -ForegroundColor Yellow
    
    if ($Body) {
        $bodyJson = $Body | ConvertTo-Json -Depth 10
        Write-Host "Request Body: $bodyJson" -ForegroundColor Gray
        
        try {
            $response = Invoke-RestMethod -Uri $url -Method $Method -Headers $headers -Body $bodyJson -ErrorAction Stop
            return $response
        }
        catch {
            Write-Host "Error: $_" -ForegroundColor Red
            Write-Host "Status Code: $($_.Exception.Response.StatusCode.value__)" -ForegroundColor Red
            
            # Try to get error details
            try {
                $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
                $errorContent = $reader.ReadToEnd()
                $reader.Close()
                Write-Host "Error Details: $errorContent" -ForegroundColor Red
            }
            catch {
                Write-Host "Could not read error details" -ForegroundColor Red
            }
            
            return $null
        }
    }
    else {
        try {
            $response = Invoke-RestMethod -Uri $url -Method $Method -Headers $headers -ErrorAction Stop
            return $response
        }
        catch {
            Write-Host "Error: $_" -ForegroundColor Red
            Write-Host "Status Code: $($_.Exception.Response.StatusCode.value__)" -ForegroundColor Red
            
            # Try to get error details
            try {
                $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
                $errorContent = $reader.ReadToEnd()
                $reader.Close()
                Write-Host "Error Details: $errorContent" -ForegroundColor Red
            }
            catch {
                Write-Host "Could not read error details" -ForegroundColor Red
            }
            
            return $null
        }
    }
}

# 1. Test Pension Fund Creation
Write-Host "`n1. Testing Pension Fund Creation" -ForegroundColor Green

# Align date to first of month
$startDate = Get-Date
$startDate = $startDate.AddDays(-($startDate.Day - 1))
$formattedDate = $startDate.ToString("yyyy-MM-dd")

# Test calculated mode
$calculatedPayload = @{
    client_id = $clientId
    fund_name = "Test Calculated Fund"
    input_mode = "calculated"
    balance = 100000
    annuity_factor = 220
    pension_start_date = $formattedDate
    indexation_method = "none"
}

Write-Host "`nTesting calculated mode pension fund creation..." -ForegroundColor Cyan
$calculatedResult = Invoke-ApiCall -Endpoint "/clients/$clientId/pension-funds" -Method "POST" -Body $calculatedPayload

if ($calculatedResult) {
    Write-Host "Calculated mode pension fund created successfully!" -ForegroundColor Green
    Write-Host "Fund ID: $($calculatedResult.id)" -ForegroundColor Green
}

# Test manual mode
$manualPayload = @{
    client_id = $clientId
    fund_name = "Test Manual Fund"
    input_mode = "manual"
    pension_amount = 5000
    pension_start_date = $formattedDate
    indexation_method = "fixed"
    fixed_index_rate = 0.02
}

Write-Host "`nTesting manual mode pension fund creation..." -ForegroundColor Cyan
$manualResult = Invoke-ApiCall -Endpoint "/clients/$clientId/pension-funds" -Method "POST" -Body $manualPayload

if ($manualResult) {
    Write-Host "Manual mode pension fund created successfully!" -ForegroundColor Green
    Write-Host "Fund ID: $($manualResult.id)" -ForegroundColor Green
}

# 2. Test Fixation Compute
Write-Host "`n2. Testing Fixation Compute" -ForegroundColor Green
Write-Host "`nCalling fixation compute endpoint..." -ForegroundColor Cyan

$fixationResult = Invoke-ApiCall -Endpoint "/fixation/$clientId/compute" -Method "POST"

if ($fixationResult) {
    Write-Host "Fixation compute successful!" -ForegroundColor Green
    
    if ($fixationResult.summary) {
        Write-Host "Summary:" -ForegroundColor Cyan
        Write-Host "  Total Pension: $($fixationResult.summary.total_pension)" -ForegroundColor White
        Write-Host "  Total Grants: $($fixationResult.summary.total_grants)" -ForegroundColor White
        Write-Host "  Net Amount: $($fixationResult.summary.net_amount)" -ForegroundColor White
    }
}

# 3. Test Scenarios Integration
Write-Host "`n3. Testing Scenarios Integration" -ForegroundColor Green

# Create a scenario
$scenarioPayload = @{
    name = "Test Scenario $(Get-Date -Format 'yyyyMMdd-HHmmss')"
    description = "Created from API test script"
}

Write-Host "`nCreating a new scenario..." -ForegroundColor Cyan
$scenarioResult = Invoke-ApiCall -Endpoint "/clients/$clientId/scenarios" -Method "POST" -Body $scenarioPayload

if ($scenarioResult -and $scenarioResult.id) {
    $scenarioId = $scenarioResult.id
    Write-Host "Scenario created successfully!" -ForegroundColor Green
    Write-Host "Scenario ID: $scenarioId" -ForegroundColor Green
    
    # List scenarios
    Write-Host "`nListing all scenarios..." -ForegroundColor Cyan
    $scenariosList = Invoke-ApiCall -Endpoint "/clients/$clientId/scenarios"
    
    if ($scenariosList -and $scenariosList.Count -gt 0) {
        Write-Host "Found $($scenariosList.Count) scenarios" -ForegroundColor Green
        
        # Integrate all
        Write-Host "`nIntegrating all with scenario_id=$scenarioId..." -ForegroundColor Cyan
        $integrateResult = Invoke-ApiCall -Endpoint "/clients/$clientId/cashflow/integrate-all?scenario_id=$scenarioId" -Method "POST"
        
        if ($integrateResult) {
            Write-Host "Integration successful!" -ForegroundColor Green
            Write-Host "Received $($integrateResult.Count) cashflow entries" -ForegroundColor Green
            
            if ($integrateResult.Count -gt 0) {
                Write-Host "First few entries:" -ForegroundColor Cyan
                $integrateResult | Select-Object -First 3 | Format-Table -AutoSize
            }
        }
    }
}

Write-Host "`nAPI Tests Complete!" -ForegroundColor Cyan
