param([string]$Python='python')
$ErrorActionPreference='Stop'
$ProjectRoot=Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $ProjectRoot
& $Python -c 'import sys; assert sys.version_info >= (3,12), "Python 3.12+ required"'
if($LASTEXITCODE -ne 0){throw 'Python 3.12 or later is required.'}
if(-not(Test-Path -LiteralPath '.venv\Scripts\python.exe')){
    & $Python -m venv .venv
    if($LASTEXITCODE -ne 0){throw 'venv creation failed.'}
}
& .venv\Scripts\python.exe -m pip install -r requirements.lock.txt
if($LASTEXITCODE -ne 0){throw 'Python dependency installation failed.'}
pnpm --dir frontend install --frozen-lockfile
if($LASTEXITCODE -ne 0){throw 'Frontend dependency installation failed. Install Node.js 24 and pnpm 11 first.'}
pnpm --dir frontend build
if($LASTEXITCODE -ne 0){throw 'Frontend build failed.'}
$env:PYTHONPATH=Join-Path $ProjectRoot 'backend'
& .venv\Scripts\python.exe -X utf8 -m app.importer (Join-Path $ProjectRoot '再生沥青混合料实验数据表.xlsx')
if($LASTEXITCODE -ne 0){throw 'Workbook import failed.'}
if(-not(Test-Path -LiteralPath 'artifacts\models\DS.joblib') -or -not(Test-Path -LiteralPath 'artifacts\models\strain.joblib') -or -not(Test-Path -LiteralPath 'artifacts\models\TSR.joblib') -or -not(Test-Path -LiteralPath 'artifacts\models\residual.joblib')){
    & .venv\Scripts\python.exe -X utf8 -m app.ml.train
    if($LASTEXITCODE -ne 0){throw 'Model benchmark failed. Historical screening can still run.'}
}
Write-Host 'Setup complete. Run scripts/start-local.ps1. Training: python -m app.ml.train with PYTHONPATH=backend.'
