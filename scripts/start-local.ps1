$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Create .venv and install requirements.lock.txt first. See README.md.'
}
New-Item -ItemType Directory -Path (Join-Path $projectRoot 'data') -Force | Out-Null
$tokenPath = Join-Path $projectRoot 'data\local-api-token'
if (-not (Test-Path -LiteralPath $tokenPath)) {
    $tokenBytes = New-Object byte[] 32
    $tokenGenerator = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $tokenGenerator.GetBytes($tokenBytes) } finally { $tokenGenerator.Dispose() }
    $localToken = [Convert]::ToBase64String($tokenBytes)
    Set-Content -LiteralPath $tokenPath -Value $localToken -NoNewline
}
$env:LOCAL_DEVELOPMENT = '1'
$env:LOCAL_API_TOKEN = (Get-Content -LiteralPath $tokenPath -Raw).Trim()
if (-not $env:DATABASE_URL) { $env:DATABASE_URL = 'sqlite:///./data/local.db' }
& $pythonPath -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Database migration failed.' }
& $pythonPath -m backend.seed
if ($LASTEXITCODE -ne 0) { throw 'Content import failed.' }
Write-Host 'Mastrr API: http://127.0.0.1:8000/docs'
Write-Host 'Local developer mode. All seed questions remain draft.'
& $pythonPath -m uvicorn backend.api:create_app --factory --host 127.0.0.1 --port 8000
