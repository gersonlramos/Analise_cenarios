# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Contexto do Projeto

Projeto de análise de planejamento de prazo para migração de data-lakes Stellantis. O sistema extrai estimativas de desenvolvimento de histórias definidas em arquivos `.txt` por lake (BMC, COMPRAS, MOPAR, CLIENTE, SHARED SERVICES, FINANCE, RH, COMERCIAL, SUPPLY CHAIN), simula alocações de squads e gera cenários de prazo comparativos com visualização interativa (Gantt HTML + Plotly).

## Ambiente Python

O virtualenv fica em `.venv/` na raiz. Use sempre:

```powershell
.\.venv\Scripts\python.exe <script.py>
```

Instalar dependências (além de `requests`, `urllib3`, `pytest`, `dotenv` do `requirements.txt`, os scripts de análise também usam `pandas` e `plotly` — instale se necessário):

```powershell
.\.venv\Scripts\pip.exe install pandas plotly
```

## Comandos Principais

### Pipeline completo (recalcula tudo do zero)

```powershell
powershell -ExecutionPolicy Bypass -File "analises\05_documentacao\executar_pipeline_completo.ps1"
```

Etapas executadas em sequência:
1. Extrai tempos de desenvolvimento → `analises/00_fontes/tempos_desenvolvimento_historias.csv`
2. Extrai quantidades de objetos por lake → `analises/01_extracao/`
3. Calcula todos os cenários → `analises/03_otimizacao/cenarios_resumo.csv` + `*_alocacoes.csv`
4. Gera timeline interativa → `analises/04_visualizacoes/timeline_gantt_detalhada_historias.html` + `.json`
5. Copia para `docs/` (GitHub Pages)

### Recalcular somente cenários (dados-fonte já existem)

```powershell
.\.venv\Scripts\python.exe analises\06_scripts\03_otimizacao\calcular_cenarios_squads.py
```

### Regenerar somente a timeline (cenários já calculados)

```powershell
.\.venv\Scripts\python.exe analises\06_scripts\04_visualizacoes\gerar_timeline_detalhada_por_historia.py
```

### Abrir timeline interativa no navegador

```powershell
powershell -ExecutionPolicy Bypass -File "analises\05_documentacao\iniciar_timeline_dinamica.ps1"
```

> Após rodar o pipeline, pressione **Ctrl + Shift + R** no navegador para limpar o cache do JSON.

### Testes

```powershell
.\.venv\Scripts\python.exe -m pytest tests/
```

## Arquitetura da pasta `analises`

```
analises/
├── 00_fontes/          # Dados-fonte imutáveis (base das simulações)
├── 01_extracao/        # Resultados de extração de métricas por lake
├── 02_simulacoes/      # Simulações-base antes das otimizações
├── 03_otimizacao/      # Cenários comparativos e CSVs de alocação (*_alocacoes.csv)
├── 04_visualizacoes/   # Timeline Gantt (HTML + JSON) e Mermaid
├── 05_documentacao/    # Scripts PowerShell de pipeline e documentação
└── 06_scripts/         # Scripts Python organizados por etapa
    ├── 01_extracao/
    ├── 02_simulacoes/
    ├── 03_otimizacao/
    └── 04_visualizacoes/
```

Os artefatos de resultado (`.csv`, `.md`, `.html`) ficam nas pastas `00`–`04`; os scripts (`.py`) ficam em `06_scripts/`.

## Fonte de Dados

Os arquivos `.txt` em `entidades/` definem as histórias de cada lake:

```
entidades/bmc.txt, compras.txt, mopar.txt, cliente.txt,
sharedservices.txt, finance.txt, rh.txt, comercial.txt, supplychain.txt
```

Cada história segue o padrão `[LAKE - N] TITULO TAMANHO: X` e contém seções `Estimativa de Esforço` (com `Engenheiro: X dias` e/ou `Analista: Y dias`) e `Quantidade de Objetos` (com `Tabelas: N` e `Views: N`).

## Fluxo de Dados (dependências)

```
entidades/*.txt
  └─► extrair_tempos_desenvolvimento.py  →  00_fontes/tempos_desenvolvimento_historias.csv
  └─► extrair_quantidades_objetos.py     →  01_extracao/quantidades_objetos_*.csv

00_fontes/tempos_desenvolvimento_historias.csv
  └─► calcular_cenarios_squads.py        →  03_otimizacao/*_alocacoes.csv
                                            03_otimizacao/cenarios_resumo.csv

03_otimizacao/*_alocacoes.csv
  └─► gerar_timeline_detalhada_por_historia.py  →  04_visualizacoes/*.html + *.json
```

## Lógica Central de Simulação (`calcular_cenarios_squads.py`)

O arquivo `analises/06_scripts/03_otimizacao/calcular_cenarios_squads.py` é o núcleo analítico. Ele implementa um **escalonador greedy de recursos** que:

- Representa cada **Squad** como uma fila de recursos (engenheiros e/ou analistas), cada um com data de disponibilidade
- Para cada história (ordenadas por lake e número), escolhe a squad/recurso que termina mais cedo
- Respeita datas de início diferentes por lake: BMC e COMPRAS iniciam em **09/03/2026**; demais em **01/04/2026**
- Desconta **feriados nacionais de 2026** configurados no topo do arquivo (conjunto `FERIADOS`)
- Suporta três modos de simulação:
  - `simular_cenario_papeis`: separa engenheiro e analista com pools independentes
  - `simular_cenario_somente_devs`: um único pool de devs fullstack (engenheiro_dias + analista_dias)
  - `simular_cenario_devs_por_lake`: squads dedicadas por lake com reforço cross-squad após término

**SHARED SERVICES** é dividido virtualmente em dois grupos (histórias 1–64 → Squad 4; histórias 65+ → Squad 1) para balancear carga nos cenários refinados pior/esperado/otimista.

Cada cenário produz um arquivo `*_alocacoes.csv` com colunas: `squad, lake, id_historia, numero, titulo, papel, recurso, duracao_dias_uteis, data_inicio, data_fim`.

## Visualização (`gerar_timeline_detalhada_por_historia.py`)

Lê todos os `*_alocacoes.csv` de `03_otimizacao/`, gera um JSON consolidado com os traces Plotly de cada cenário e um HTML leve que carrega esse JSON via `fetch`. O dropdown no canto superior esquerdo permite alternar entre cenários sem recarregar a página. O HTML depende de `plotly-2.35.2.min.js` via CDN — abrir via `iniciar_timeline_dinamica.ps1` (que sobe um servidor HTTP local) em vez de duplo-clique no arquivo.

## Integração com Jira

Scripts na raiz (fora de `analises/`) manipulam o Jira via API REST:
- `criar_historias_jira.py` — criação em lote
- `alterar_historia_jira.py`, `deletar_historia_jira.py` — manutenção
- `exportar_historia_jira.py`, `buscar_historias_com_flag.py` — consultas
- `atualizar_datas_jira.py`, `atualizar_subtarefas_devops.py` — sync de datas

Credenciais e URL do Jira são carregadas via `.env` (não versionado). Use `dotenv` para carregar.
