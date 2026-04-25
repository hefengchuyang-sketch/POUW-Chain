$ErrorActionPreference='Stop'

$mdPath='thiel-site/THIEL_ADDITIONAL_MATERIALS.md'
$outPath='thiel-site/THIEL_ADDITIONAL_MATERIALS.docx'
$tmp='thiel-site/.docx_tmp'

if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
New-Item -ItemType Directory -Path $tmp | Out-Null
New-Item -ItemType Directory -Path (Join-Path $tmp '_rels') | Out-Null
New-Item -ItemType Directory -Path (Join-Path $tmp 'word') | Out-Null

$contentTypes = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
'@
$contentTypesPath = Join-Path $tmp '`[Content_Types`].xml'
$contentTypes | Out-File -FilePath $contentTypesPath -Encoding utf8

$rels = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
'@
$rels | Out-File -FilePath (Join-Path $tmp '_rels/.rels') -Encoding utf8

function Escape-Xml([string]$s) {
  return $s.Replace('&','&amp;').Replace('<','&lt;').Replace('>','&gt;').Replace('"','&quot;').Replace("'",'&apos;')
}

$lines = Get-Content -Path $mdPath
$paras = New-Object System.Collections.Generic.List[string]

foreach ($line in $lines) {
  $t = $line.TrimEnd()
  if ($t -eq '---') { continue }

  if ($t.StartsWith('# ')) {
    $text = Escape-Xml($t.Substring(2))
    $paras.Add("<w:p><w:r><w:rPr><w:b/><w:sz w:val='36'/></w:rPr><w:t>$text</w:t></w:r></w:p>")
    continue
  }

  if ($t.StartsWith('## ')) {
    $text = Escape-Xml($t.Substring(3))
    $paras.Add("<w:p><w:r><w:rPr><w:b/><w:sz w:val='30'/></w:rPr><w:t>$text</w:t></w:r></w:p>")
    continue
  }

  if ($t.StartsWith('- ')) {
    $text = Escape-Xml([string]::Concat([char]8226,' ',$t.Substring(2)))
    $paras.Add("<w:p><w:r><w:t xml:space='preserve'>$text</w:t></w:r></w:p>")
    continue
  }

  if ([string]::IsNullOrWhiteSpace($t)) {
    $paras.Add("<w:p/>")
    continue
  }

  $text = Escape-Xml($t)
  $paras.Add("<w:p><w:r><w:t xml:space='preserve'>$text</w:t></w:r></w:p>")
}

$docXml = "<?xml version='1.0' encoding='UTF-8' standalone='yes'?><w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'><w:body>" + ($paras -join '') + "<w:sectPr/></w:body></w:document>"
$docXml | Out-File -FilePath (Join-Path $tmp 'word/document.xml') -Encoding utf8

$zipPath='thiel-site/THIEL_ADDITIONAL_MATERIALS.zip'
if (Test-Path $zipPath) { Remove-Item -Force $zipPath }
if (Test-Path $outPath) { Remove-Item -Force $outPath }

Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory((Resolve-Path $tmp).Path,(Resolve-Path 'thiel-site').Path + '\THIEL_ADDITIONAL_MATERIALS.zip')
Rename-Item -Path $zipPath -NewName 'THIEL_ADDITIONAL_MATERIALS.docx'
Remove-Item -Recurse -Force $tmp

Get-Item $outPath | Select-Object FullName,Length
