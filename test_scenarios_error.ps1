Write-Host "Testing Scenarios Endpoint..." -ForegroundColor Cyan

$body = @{
    retirement_age = 67
} | ConvertTo-Json

Write-Host "Request body: $body"

try {
    $response = Invoke-WebRequest -Uri "http://localhost:8005/api/v1/clients/4/retirement-scenarios" `
        -Method POST `
        -ContentType "application/json" `
        -Body $body `
        -UseBasicParsing
    
    Write-Host "Status Code: $($response.StatusCode)" -ForegroundColor Green
    Write-Host "Content: $($response.Content)"
    
} catch {
    Write-Host "ERROR!" -ForegroundColor Red
    Write-Host "Status: $($_.Exception.Response.StatusCode.value__)"
    Write-Host "Message: $($_.Exception.Message)"
    
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $responseBody = $reader.ReadToEnd()
        Write-Host "Response Body: $responseBody"
    }
}
