param([int]$Port=8766,[switch]$Demo)
$ErrorActionPreference='Stop'
$ProjectRoot=Split-Path -Parent $PSScriptRoot
$PythonPath=Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if(-not(Test-Path -LiteralPath $PythonPath)){
    throw 'Python environment missing. Run: powershell -ExecutionPolicy Bypass -File scripts/setup.ps1 -Python <python.exe>'
}
if(-not(Test-Path -LiteralPath (Join-Path $ProjectRoot 'frontend\dist\index.html'))){
    throw 'Frontend build missing. Run: pnpm --dir frontend install --frozen-lockfile; pnpm --dir frontend build'
}
Set-Location -LiteralPath $ProjectRoot
if($Demo){
    $DemoDatabase=Join-Path $ProjectRoot 'artifacts\review-phase\demo.sqlite'
    if(-not(Test-Path -LiteralPath $DemoDatabase)){throw 'Demo database missing. Run scripts/setup.ps1 first.'}
    $env:ASPHALT_DATABASE=$DemoDatabase
}
$env:PYTHONPATH=Join-Path $ProjectRoot 'backend'
& $PythonPath -X utf8 -m app.importer (Join-Path $ProjectRoot '再生沥青混合料实验数据表.xlsx') | Out-Null
if($LASTEXITCODE -ne 0){throw 'Workbook import failed.'}
Write-Host "Material workbench: http://127.0.0.1:$Port/"
& $PythonPath -X utf8 -m uvicorn app.main:app --host 127.0.0.1 --port $Port
exit $LASTEXITCODE
