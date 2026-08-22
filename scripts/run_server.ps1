$ErrorActionPreference = "Stop"

if (-not (Test-Path ".env")) {
    Write-Host "ERROR: .env not found. Copy .env.example to .env and configure."
    exit 1
}

python -m uvicorn app.main:app --host 0.0.0.0 --port 9001
