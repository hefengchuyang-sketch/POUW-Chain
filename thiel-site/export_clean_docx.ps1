$ErrorActionPreference = 'Stop'

$txtPath = (Resolve-Path 'thiel-site/THIEL_ADDITIONAL_MATERIALS_CLEAN.txt').Path
$docxPath = (Resolve-Path 'thiel-site').Path + '\THIEL_ADDITIONAL_MATERIALS.docx'

$word = $null
$doc = $null

try {
  $word = New-Object -ComObject Word.Application
  $word.Visible = $false
  $doc = $word.Documents.Open($txtPath)
  $wdFormatXMLDocument = 12
  $doc.SaveAs([ref]$docxPath, [ref]$wdFormatXMLDocument)
  $doc.Close()
  $word.Quit()

  Get-Item $docxPath | Select-Object FullName, Length
}
catch {
  if ($doc -ne $null) { $doc.Close() }
  if ($word -ne $null) { $word.Quit() }
  throw
}
