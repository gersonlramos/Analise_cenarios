# Como executar o pipeline e a timeline dinâmica

## Pré-requisitos

- Python instalado no virtualenv em `.venv/` na raiz do projeto
- PowerShell disponível no terminal

Raiz do projeto:
```
c:\Users\gerson.ramos\OneDrive - Compass UOL\Projetos\Stellantis\Jira_novo
```

---

## 1. Executar o pipeline completo

Recalcula todos os cenários e regenera a timeline interativa do zero.

```powershell
powershell -ExecutionPolicy Bypass -File "analises\05_documentacao\executar_pipeline_completo.ps1"
```

O pipeline executa 5 etapas em sequência:

| Etapa | O que faz | Saída principal |
|---|---|---|
| 1 | Extrai tempos de desenvolvimento das histórias | `analises/00_fontes/tempos_desenvolvimento_historias.csv` |
| 2 | Extrai quantidades de objetos por lake | `analises/01_extracao/quantidades_objetos_lakes.csv` |
| 3 | Calcula todos os cenários (pior/esperado/otimista e variações) | `analises/03_otimizacao/cenarios_resumo.csv` + arquivos `*_alocacoes.csv` |
| 4 | Gera a timeline interativa (HTML + JSON) | `analises/04_visualizacoes/timeline_gantt_detalhada_historias.html` |
| 5 | Prepara a pasta `docs/` para publicação no GitHub Pages | `docs/index.html` |

Se quiser usar um Python diferente do padrão `.venv`:

```powershell
powershell -ExecutionPolicy Bypass -File "analises\05_documentacao\executar_pipeline_completo.ps1" -PythonExe "caminho\para\python.exe"
```

---

## 2. Iniciar a timeline dinâmica localmente

Abre o HTML interativo no navegador padrão.

```powershell
powershell -ExecutionPolicy Bypass -File "analises\05_documentacao\iniciar_timeline_dinamica.ps1"
```

> **Importante:** após rodar o pipeline, sempre pressione **Ctrl + Shift + R** no navegador para forçar o reload e garantir que o cache do JSON seja limpo.

---

## 3. Recalcular somente os cenários (sem extração)

Se os dados-fonte não mudaram e você só alterou parâmetros de cenário:

```powershell
.\.venv\Scripts\python.exe analises\06_scripts\03_otimizacao\calcular_cenarios_squads.py
```

---

## 4. Regenerar somente a timeline (sem recalcular cenários)

Se os arquivos `*_alocacoes.csv` já estão atualizados:

```powershell
.\.venv\Scripts\python.exe analises\06_scripts\04_visualizacoes\gerar_timeline_detalhada_por_historia.py
```

---

## Observações

- Os **feriados nacionais de 2026** já estão configurados no script `calcular_cenarios_squads.py` e são descontados automaticamente do calendário de dias úteis:
  - 03/04 — Paixão de Cristo
  - 21/04 — Tiradentes
  - 01/05 — Dia do Trabalho
  - 04/06 — Corpus Christi (ponto facultativo)
  - 07/09 — Independência do Brasil
  - 12/10 — Nossa Senhora Aparecida
  - 02/11 — Finados
  - 15/11 — Proclamação da República
  - 20/11 — Consciência Negra

- O gráfico exibe **todos os cenários disponíveis** em `analises/03_otimizacao/*_alocacoes.csv` via dropdown no canto superior esquerdo.
