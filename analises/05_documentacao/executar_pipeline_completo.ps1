param(
    [string]$PythonExe = ".\.venv\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"
$root = "c:\Users\gerson.ramos\OneDrive - Compass UOL\Projetos\Stellantis\Jira_novo"
Set-Location $root

function Etapa($numero, $texto) {
    Write-Host ""
    Write-Host "[$numero/5] $texto" -ForegroundColor Cyan
}

function Ok($texto) {
    Write-Host "    OK: $texto" -ForegroundColor Green
}

function Erro($texto) {
    Write-Host "    ERRO: $texto" -ForegroundColor Red
    exit 1
}

# ── 1. Extrair tempos de desenvolvimento ─────────────────────────────────────
Etapa 1 "Extraindo tempos de desenvolvimento..."
& $PythonExe "analises\06_scripts\01_extracao\extrair_tempos_desenvolvimento.py"
if ($LASTEXITCODE -ne 0) { Erro "extrair_tempos_desenvolvimento.py falhou" }
Ok "tempos_desenvolvimento_historias.csv gerado"

# ── 2. Extrair quantidades de objetos ─────────────────────────────────────────
Etapa 2 "Extraindo quantidades de objetos..."
& $PythonExe "analises\06_scripts\01_extracao\extrair_quantidades_objetos.py"
if ($LASTEXITCODE -ne 0) { Erro "extrair_quantidades_objetos.py falhou" }
Ok "quantidades_objetos_historias.csv e quantidades_objetos_lakes.csv gerados"

# ── 3. Calcular cenários ───────────────────────────────────────────────────────
Etapa 3 "Calculando cenários (base, referência, melhores, só devs)..."
& $PythonExe "analises\06_scripts\03_otimizacao\calcular_cenarios_squads.py"
if ($LASTEXITCODE -ne 0) { Erro "calcular_cenarios_squads.py falhou" }
Ok "cenarios_resumo.csv e alocações de cada cenário geradas"

# ── 4. Gerar timeline interativa ──────────────────────────────────────────────
Etapa 4 "Gerando timeline interativa (HTML + JSON)..."
& $PythonExe "analises\06_scripts\04_visualizacoes\gerar_timeline_detalhada_por_historia.py"
if ($LASTEXITCODE -ne 0) { Erro "gerar_timeline_detalhada_por_historia.py falhou" }
Ok "timeline_gantt_detalhada_historias.html e .json gerados"

# ── 5. Preparar GitHub Pages ───────────────────────────────────────────────────
Etapa 5 "Preparando pasta docs/ para GitHub Pages..."
& powershell -ExecutionPolicy Bypass -File "analises\05_documentacao\preparar_github_pages.ps1" -PythonExe $PythonExe
if ($LASTEXITCODE -ne 0) { Erro "preparar_github_pages.ps1 falhou" }
Ok "Pasta docs/ atualizada"

Write-Host ""
Write-Host "Pipeline concluído com sucesso." -ForegroundColor Green
Write-Host "Abra docs/index.html localmente com: powershell -ExecutionPolicy Bypass -File .\analises\05_documentacao\iniciar_timeline_dinamica.ps1" -ForegroundColor Yellow
