$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath (Join-Path $projectRoot 'frontend')
if (-not $env:NEXT_PUBLIC_SUPABASE_URL) { $env:NEXT_PUBLIC_LOCAL_DEVELOPMENT = '1' }
if (-not $env:MASTRR_API_ORIGIN) { $env:MASTRR_API_ORIGIN = 'http://127.0.0.1:8000' }
npm run dev -- --hostname 127.0.0.1
