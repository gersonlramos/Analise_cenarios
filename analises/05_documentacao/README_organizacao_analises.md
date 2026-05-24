# Organização da pasta `analises`

## Como gerar `prazo_squads_dividido_alocacoes.csv`

Opção rápida (1 comando):

```powershell
& "c:/Users/gerson.ramos/OneDrive - Compass UOL/Projetos/Stellantis/Jira_novo/.venv/Scripts/python.exe" "analises/simular_prazo_squads_comercial_dividido.py" --saida-lakes "analises/03_otimizacao/prazo_squads_dividido_lakes.csv" --saida-squads "analises/03_otimizacao/prazo_squads_dividido_resumo.csv" --saida-detalhe "analises/03_otimizacao/prazo_squads_dividido_alocacoes.csv" --saida-relatorio "analises/03_otimizacao/prazo_squads_dividido_relatorio.md"
```

Pipeline recomendado (recalcula base + simulação):

```powershell
.\analises\05_documentacao\pipeline_prazo_squads_dividido.ps1
```

Arquivo gerado:

- `analises/03_otimizacao/prazo_squads_dividido_alocacoes.csv`

---

## Estrutura temática (assuntos interligados)

### `00_fontes`

- Base de dados por história usada nas análises.
- Ex.: `00_fontes/tempos_desenvolvimento_historias.csv`

### `01_extracao`

- Resultados de extração de métricas por lake (objetos técnicos).
- Ex.: `01_extracao/quantidades_objetos_lakes.csv`, `01_extracao/quantidades_objetos_lakes.md`

### `02_simulacoes`

- Simulações-base de prazo por lake e por squad (antes de otimizações).
- Ex.: `02_simulacoes/prazo_squads_resumo.csv`, `02_simulacoes/prazo_lakes_simulado.csv`

### `03_otimizacao`

- Cenários comparativos e otimizações (ex.: COMERCIAL dividido, Squad 5 ajudando RH/Supply).
- Ex.: `03_otimizacao/prazo_squads_dividido_*.csv`, `03_otimizacao/alternativas_minimas_projeto.csv`

### `04_visualizacoes`

- Timelines e gráficos para apresentação (Mermaid e HTML interativo).
- Ex.: `04_visualizacoes/timeline_historias_gantt.md`, `04_visualizacoes/timeline_historias_interativo.html`

### `05_documentacao`

- Guias e scripts utilitários de execução do pipeline.

---

## Fluxo recomendado (dependências)

1. `extrair_tempos_desenvolvimento.py`  
   gera `00_fontes/tempos_desenvolvimento_historias.csv` (ou caminho definido em `--saida`)
2. `simular_prazo_squads_comercial_dividido.py`  
   gera `03_otimizacao/prazo_squads_dividido_alocacoes.csv` e resumos (quando informado via argumentos)
3. Visualização:
   - `gerar_timeline_historias_gantt.py` (Mermaid, salvar em `04_visualizacoes`)
   - `gerar_timeline_html_plotly.py` (HTML interativo, salvar em `04_visualizacoes`)

---

## Estado atual da raiz de `analises`

- Na raiz ficam somente scripts (`.py`) e pastas temáticas.
- Artefatos de resultado (`.csv`, `.md`, `.html`) foram movidos para as subpastas `00` a `04`.
