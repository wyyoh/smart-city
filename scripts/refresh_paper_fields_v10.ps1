param([Parameter(Mandatory=$true)][string]$Path)
$ErrorActionPreference = 'Stop'
$resolved = [IO.Path]::GetFullPath($Path)
$word = New-Object -ComObject Word.Application
try {
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $doc = $word.Documents.Open($resolved, $false, $false)
    try {
        $doc.Repaginate()
        foreach ($toc in $doc.TablesOfContents) { $toc.Update() }
        $doc.Fields.Update() | Out-Null
        foreach ($toc in $doc.TablesOfContents) {
            $toc.Range.Font.NameFarEast = '宋体'
            $toc.Range.Font.Name = 'Times New Roman'
            $toc.Range.Font.Size = 10.5
            $toc.Range.ParagraphFormat.LineSpacingRule = 4
            $toc.Range.ParagraphFormat.LineSpacing = 13
            $toc.Range.ParagraphFormat.SpaceBefore = 0
            $toc.Range.ParagraphFormat.SpaceAfter = 1
        }
        $doc.Repaginate()
        foreach ($toc in $doc.TablesOfContents) { $toc.UpdatePageNumbers() }
        $pages = $doc.ComputeStatistics(2)
        $doc.Save()
        Write-Output "Updated native fields; pages=$pages"
    } finally {
        $doc.Close(0)
    }
} finally {
    $word.Quit()
    [Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
}
