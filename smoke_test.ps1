# Smoke Test Script for Fixation API
# Run this after each deployment to verify basic functionality
# Usage: .\smoke_test.ps1 [baseUrl]
# Default baseUrl: http://localhost:8000

param (
    [string]$baseUrl = "http://localhost:8000"
)

Write-Host "Starting Fixation API Smoke Tests at $baseUrl" -ForegroundColor Cyan

# Set error action preference
$ErrorActionPreference = "Stop"

# Test results tracking
$totalTests = 0
$passedTests = 0
$failedTests = 0

function Run-Test {
    param (
        [string]$name,
        [scriptblock]$test
    )
    
    $totalTests++
    Write-Host "Test $totalTests : $name" -ForegroundColor Yellow
    
    try {
        & $test
        Write-Host "  ✓ PASSED" -ForegroundColor Green
        $script:passedTests++
    }
    catch {
        Write-Host "  ✗ FAILED: $_" -ForegroundColor Red
        $script:failedTests++
    }
    
    Write-Host ""
}

# Helper function to check response
function Check-Response {
    param (
        [PSObject]$response,
        [string]$expectedField,
        [string]$errorMessage
    )
    
    if (-not $response.$expectedField) {
        throw $errorMessage
    }
}

# Test 1: Create test client
Run-Test -name "Create Test Client" -test {
    $client = @{
        id_number = "111111118"
        full_name = "ישראל ישראלי"
        birth_date = "1980-01-01"
        email = "test@example.com"
        phone = "0501234567"
        address_city = "תל אביב"
        address_street = "רחוב הברוש 5"
        address_postal_code = "6100000"
    } | ConvertTo-Json
    
    $response = Invoke-RestMethod -Method POST -Uri "$baseUrl/api/v1/clients" -ContentType "application/json" -Body $client
    
    Check-Response -response $response -expectedField "id" -errorMessage "Client creation failed, no ID returned"
    
    # Store client ID for later tests
    $script:clientId = $response.id
    Write-Host "  Created client with ID: $script:clientId"
}

# Test 2: Generate 161d form
Run-Test -name "Generate 161d Form" -test {
    $response = Invoke-RestMethod -Method POST -Uri "$baseUrl/api/v1/fixation/$script:clientId/161d"
    
    Check-Response -response $response -expectedField "success" -errorMessage "161d generation failed"
    Check-Response -response $response -expectedField "file_path" -errorMessage "No file path returned"
    
    # Verify file path format
    if (-not $response.file_path.StartsWith("packages/")) {
        throw "Invalid file path format: $($response.file_path)"
    }
    
    # Verify file exists
    $filePath = Join-Path -Path (Get-Location) -ChildPath $response.file_path.Replace("/", "\")
    if (-not (Test-Path $filePath)) {
        throw "Generated file does not exist: $filePath"
    }
    
    Write-Host "  Generated file: $($response.file_path)"
    $script:form161dPath = $response.file_path
}

# Test 3: Generate grants appendix
Run-Test -name "Generate Grants Appendix" -test {
    $response = Invoke-RestMethod -Method POST -Uri "$baseUrl/api/v1/fixation/$script:clientId/grants-appendix"
    
    Check-Response -response $response -expectedField "success" -errorMessage "Grants appendix generation failed"
    Check-Response -response $response -expectedField "file_path" -errorMessage "No file path returned"
    
    # Verify file path format
    if (-not $response.file_path.StartsWith("packages/")) {
        throw "Invalid file path format: $($response.file_path)"
    }
    
    # Verify file exists
    $filePath = Join-Path -Path (Get-Location) -ChildPath $response.file_path.Replace("/", "\")
    if (-not (Test-Path $filePath)) {
        throw "Generated file does not exist: $filePath"
    }
    
    Write-Host "  Generated file: $($response.file_path)"
    $script:grantsPath = $response.file_path
}

# Test 4: Generate commutations appendix
Run-Test -name "Generate Commutations Appendix" -test {
    $response = Invoke-RestMethod -Method POST -Uri "$baseUrl/api/v1/fixation/$script:clientId/commutations-appendix"
    
    Check-Response -response $response -expectedField "success" -errorMessage "Commutations appendix generation failed"
    Check-Response -response $response -expectedField "file_path" -errorMessage "No file path returned"
    
    # Verify file path format
    if (-not $response.file_path.StartsWith("packages/")) {
        throw "Invalid file path format: $($response.file_path)"
    }
    
    # Verify file exists
    $filePath = Join-Path -Path (Get-Location) -ChildPath $response.file_path.Replace("/", "\")
    if (-not (Test-Path $filePath)) {
        throw "Generated file does not exist: $filePath"
    }
    
    Write-Host "  Generated file: $($response.file_path)"
    $script:commutationsPath = $response.file_path
}

# Test 5: Generate complete package
Run-Test -name "Generate Complete Package" -test {
    $response = Invoke-RestMethod -Method POST -Uri "$baseUrl/api/v1/fixation/$script:clientId/package"
    
    Check-Response -response $response -expectedField "success" -errorMessage "Package generation failed"
    
    # Check files array
    if (-not $response.files -or $response.files.Count -lt 3) {
        throw "Package should contain at least 3 files, got $($response.files.Count)"
    }
    
    # Verify all files exist
    foreach ($file in $response.files) {
        $filePath = Join-Path -Path (Get-Location) -ChildPath $file.Replace("/", "\")
        if (-not (Test-Path $filePath)) {
            throw "Generated file does not exist: $filePath"
        }
        Write-Host "  Package file: $file"
    }
}

# Test 6: Test file download endpoint
Run-Test -name "Test File Download Endpoint" -test {
    if (-not $script:form161dPath) {
        throw "No 161d file path available for testing download"
    }
    
    # Extract relative path
    $relativePath = $script:form161dPath
    
    # Test download endpoint
    $downloadUrl = "$baseUrl/api/v1/files?path=$relativePath"
    Write-Host "  Testing download URL: $downloadUrl"
    
    $tempFile = New-TemporaryFile
    Invoke-WebRequest -Uri $downloadUrl -OutFile $tempFile
    
    # Verify file was downloaded
    if ((Get-Item $tempFile).Length -eq 0) {
        throw "Downloaded file is empty"
    }
    
    Write-Host "  Successfully downloaded file ($((Get-Item $tempFile).Length) bytes)"
    Remove-Item $tempFile
}

# Print summary
Write-Host "Smoke Test Summary:" -ForegroundColor Cyan
Write-Host "  Total Tests: $totalTests" -ForegroundColor White
Write-Host "  Passed: $passedTests" -ForegroundColor Green
Write-Host "  Failed: $failedTests" -ForegroundColor Red

# Return exit code based on test results
if ($failedTests -gt 0) {
    Write-Host "SMOKE TESTS FAILED!" -ForegroundColor Red
    exit 1
} else {
    Write-Host "SMOKE TESTS PASSED!" -ForegroundColor Green
    exit 0
}
