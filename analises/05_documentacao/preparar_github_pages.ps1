param(
    [string]$PythonExe = ".\.venv\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$projectRoot = Split-Path -Parent $projectRoot

$docsDir              = Join-Path $projectRoot "docs"
$scriptTimeline       = Join-Path $projectRoot "analises\06_scripts\04_visualizacoes\gerar_timeline_detalhada_por_historia.py"
$scriptPrazo          = Join-Path $projectRoot "analises\06_scripts\03_otimizacao\simular_prazo_historias_reais.py"

# Saídas da timeline de cenários de squads
$timelineHtml         = Join-Path $docsDir "timeline_gantt_detalhada_historias.html"
$timelineJson         = Join-Path $docsDir "timeline_gantt_detalhada_historias.json"
$timelineValidacao    = Join-Path $docsDir "validacao_timeline_historias.csv"
$resumoCenarios       = Join-Path $projectRoot "analises\03_otimizacao\cenarios_resumo.csv"
$destinoResumo        = Join-Path $docsDir "cenarios_resumo.csv"

# Saídas do prazo estimado por histórias reais
$prazoSrcHtml         = Join-Path $projectRoot "analises\04_visualizacoes\prazo_historias_reais.html"
$prazoSrcJson         = Join-Path $projectRoot "analises\04_visualizacoes\prazo_historias_reais.json"
$prazoDestHtml        = Join-Path $docsDir "prazo_historias_reais.html"
$prazoDestJson        = Join-Path $docsDir "prazo_historias_reais.json"

# Portal de navegação
$indexSrc             = Join-Path $projectRoot "docs\index.html"   # já gerenciado manualmente
$noJekyll             = Join-Path $docsDir ".nojekyll"

if (-not (Test-Path $docsDir)) {
    New-Item -ItemType Directory -Path $docsDir | Out-Null
}

Write-Host "Gerando timeline de cenarios de squads..." -ForegroundColor Cyan
& $PythonExe $scriptTimeline --saida $timelineHtml --saida-json $timelineJson --saida-validacao $timelineValidacao

Write-Host "Gerando prazo estimado por historias reais..." -ForegroundColor Cyan
& $PythonExe $scriptPrazo
if ($LASTEXITCODE -ne 0) { Write-Host "    AVISO: simular_prazo_historias_reais.py retornou erro" -ForegroundColor Yellow }

# Copiar prazo estimado para docs/
if (Test-Path $prazoSrcHtml) { Copy-Item $prazoSrcHtml $prazoDestHtml -Force }
if (Test-Path $prazoSrcJson) { Copy-Item $prazoSrcJson $prazoDestJson -Force }

# Copiar resumo de cenários
if (Test-Path $resumoCenarios) { Copy-Item $resumoCenarios $destinoResumo -Force }

Set-Content -Path $noJekyll -Value "" -Encoding UTF8

Write-Host ""
Write-Host "Arquivos prontos para publicacao:" -ForegroundColor Green
Write-Host " - docs/index.html                            (portal de navegacao)"
Write-Host " - docs/timeline_gantt_detalhada_historias.html + .json"
Write-Host " - docs/prazo_historias_reais.html + .json"
Write-Host " - docs/cenarios_resumo.csv"
Write-Host " - docs/.nojekyll"
Write-Host ""
Write-Host "Proximo passo no GitHub: Settings > Pages > Deploy from branch > main /docs" -ForegroundColor Yellow
