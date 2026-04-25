$ErrorActionPreference = 'Stop'

$srcPath = (Resolve-Path 'thiel-site/THIEL_SUPPLEMENTARY_MATERIALS_SOURCE.txt').Path
$outPath = (Resolve-Path 'thiel-site').Path + '\THIEL_SUPPLEMENTARY_MATERIALS.docx'

$word = $null
$doc = $null

try {
  $word = New-Object -ComObject Word.Application
  $word.Visible = $false
  $doc = $word.Documents.Add()

  $text = Get-Content -Path $srcPath -Raw
  $doc.Content.Text = $text

  # Global font and spacing
  $doc.Content.Font.Name = 'Calibri'
  $doc.Content.Font.Size = 11
  $doc.Content.ParagraphFormat.SpaceAfter = 6
  $doc.Content.ParagraphFormat.LineSpacingRule = 0

  # Title styling (first line)
  $firstPara = $doc.Paragraphs.Item(1).Range
  $firstPara.Font.Size = 18
  $firstPara.Font.Bold = $true

  # Style section headings that start with number + dot
  foreach ($para in $doc.Paragraphs) {
    $r = $para.Range
    $line = $r.Text.Trim()
    if ($line -match '^[0-9]+\.') {
      $r.Font.Bold = $true
      $r.Font.Size = 13
      $r.ParagraphFormat.SpaceBefore = 10
      $r.ParagraphFormat.SpaceAfter = 6
    }

    if ($line -match '^Phase [0-9]') {
      $r.Font.Bold = $true
      $r.Font.Size = 12
      $r.ParagraphFormat.SpaceBefore = 8
      $r.ParagraphFormat.SpaceAfter = 4
    }
  }

  # Convert budget block to table (find start/end lines)
  $allText = $doc.Content.Text
  $startKey = 'Category | Amount | Exact Use Case'
  $endKey = 'Total | $100,000 |'

  $startPos = $allText.IndexOf($startKey)
  $endPos = $allText.IndexOf($endKey)

  if ($startPos -ge 0 -and $endPos -ge $startPos) {
    $endPos = $endPos + $endKey.Length
    $budgetBlock = $allText.Substring($startPos, $endPos - $startPos)
    $rows = $budgetBlock -split "`r?`n" | Where-Object { $_.Trim().Length -gt 0 }

    if ($rows.Count -ge 2) {
      # Find range in document for replacement
      $findRange = $doc.Content
      $find = $findRange.Find
      $find.ClearFormatting()
      $find.Text = $budgetBlock
      if ($find.Execute()) {
        $replaceRange = $findRange.Duplicate
        $replaceRange.Text = ''

        $parts = @()
        foreach ($row in $rows) {
          $cols = $row -split '\|'
          $parts += ,($cols | ForEach-Object { $_.Trim() })
        }

        $tableRows = $rows.Count
        $tableCols = 3
        $table = $doc.Tables.Add($replaceRange, $tableRows, $tableCols)
        $table.Borders.Enable = 1
        $table.Rows.Item(1).Range.Font.Bold = $true

        for ($i = 0; $i -lt $tableRows; $i++) {
          $cols = ($rows[$i] -split '\|') | ForEach-Object { $_.Trim() }
          for ($j = 0; $j -lt [Math]::Min($tableCols, $cols.Count); $j++) {
            $table.Cell($i + 1, $j + 1).Range.Text = $cols[$j]
          }
        }
      }
    }
  }

  # Save as docx
  $wdFormatXMLDocument = 12
  $doc.SaveAs([ref]$outPath, [ref]$wdFormatXMLDocument)
  $doc.Close()
  $word.Quit()

  Get-Item $outPath | Select-Object FullName, Length
}
catch {
  if ($doc -ne $null) { $doc.Close() }
  if ($word -ne $null) { $word.Quit() }
  throw
}
