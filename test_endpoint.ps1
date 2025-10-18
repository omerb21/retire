$body = @{
    retirement_age = 67
} | ConvertTo-Json

Invoke-WebRequest -Uri "http://localhost:8005/api/v1/clients/4/retirement-scenarios" `
    -Method POST `
    -ContentType "application/json" `
    -Body $body
