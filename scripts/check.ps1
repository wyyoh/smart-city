$ErrorActionPreference='Stop'
$ProjectRoot=Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $ProjectRoot
$env:PYTHONPATH=Join-Path $ProjectRoot 'backend'
& .venv\Scripts\python.exe -X utf8 -m pytest -q
if($LASTEXITCODE -ne 0){throw 'Python checks failed.'}
pnpm --dir frontend build
if($LASTEXITCODE -ne 0){throw 'Frontend build failed.'}
& .venv\Scripts\python.exe -X utf8 planning/validate_plan.py
if($LASTEXITCODE -ne 0){throw 'Planning consistency failed.'}
