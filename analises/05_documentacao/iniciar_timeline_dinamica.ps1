param(
    [int]$Port = 8000,
    [string]$HtmlPath = "docs\index.html"
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repoRoot

$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    $pythonCmd = $venvPython
} else {
    $pythonCmd = "python"
}

$htmlRel = $HtmlPath -replace "\\", "/"
$htmlFull = Join-Path $repoRoot ($HtmlPath -replace "/", "\")

if (-not (Test-Path $htmlFull)) {
    Write-Error "Arquivo HTML não encontrado: $HtmlPath"
}

$url = "http://localhost:$Port/$htmlRel"

Write-Host "Iniciando servidor local em http://localhost:$Port ..."
Write-Host "Abrindo timeline: $url"
Start-Process $url

& $pythonCmd -m http.server $Port
