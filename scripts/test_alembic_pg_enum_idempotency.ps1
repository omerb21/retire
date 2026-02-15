$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Push-Location $repoRoot

try {
    if (-not $env:TEST_DATABASE_URL -or -not $env:TEST_DATABASE_URL.Trim()) {
        throw "Missing TEST_DATABASE_URL. Set it to a safe Postgres URL (not production)."
    }

    python scripts\test_alembic_pg_enum_idempotency.py
    if ($LASTEXITCODE -ne 0) {
        throw "Alembic enum idempotency test failed"
    }
} finally {
    Pop-Location
}
