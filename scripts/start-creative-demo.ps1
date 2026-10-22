param([int]$Port=8766)
$ErrorActionPreference='Stop'
$ProjectRoot=Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $ProjectRoot
$PythonPath=Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if(-not(Test-Path -LiteralPath $PythonPath)){throw 'Run scripts/setup.ps1 before starting the creative demo.'}
$env:ASPHALT_DATABASE=Join-Path $ProjectRoot 'artifacts\polish-v7\ui-demo.sqlite'
& $PythonPath -X utf8 scripts/prepare_creative_demo.py
if($LASTEXITCODE -ne 0){throw 'Creative demo database preparation failed.'}
& (Join-Path $PSScriptRoot 'start-local.ps1') -Port $Port
