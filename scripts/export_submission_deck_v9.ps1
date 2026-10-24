param(
    [Parameter(Mandatory=$true)][string]$PptxPath,
    [Parameter(Mandatory=$true)][string]$PdfPath
)
$ErrorActionPreference = 'Stop'
$resolvedPptx = [IO.Path]::GetFullPath($PptxPath)
$resolvedPdf = [IO.Path]::GetFullPath($PdfPath)
function Get-TaskFileSha256([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $hasher = [Security.Cryptography.SHA256]::Create()
    try {
        return [BitConverter]::ToString($hasher.ComputeHash($stream)).Replace('-', '').ToLowerInvariant()
    } finally {
        $hasher.Dispose()
        $stream.Dispose()
    }
}
$beforeHash = Get-TaskFileSha256 $resolvedPptx
$office = New-Object -ComObject PowerPoint.Application
try {
    $office.DisplayAlerts = 1
    $deck = $office.Presentations.Open($resolvedPptx, $true, $false, $false)
    try {
        $deck.SaveAs($resolvedPdf, 32)
    } finally {
        $deck.Close()
        [Runtime.InteropServices.Marshal]::ReleaseComObject($deck) | Out-Null
    }
} finally {
    $office.Quit()
    [Runtime.InteropServices.Marshal]::ReleaseComObject($office) | Out-Null
}
$afterHash = Get-TaskFileSha256 $resolvedPptx
if ($beforeHash -ne $afterHash) { throw 'Source PPTX changed during PDF export.' }
if (!(Test-Path -LiteralPath $resolvedPdf)) { throw 'PDF output missing.' }
Write-Output 'PDF exported with installed PowerPoint; source PPTX unchanged.'
