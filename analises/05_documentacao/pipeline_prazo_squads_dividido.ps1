# Pipeline para gerar prazo_squads_dividido_alocacoes.csv
# Executar da raiz do projeto: Jira_novo

& "c:/Users/gerson.ramos/OneDrive - Compass UOL/Projetos/Stellantis/Jira_novo/.venv/Scripts/python.exe" "analises/extrair_tempos_desenvolvimento.py" --saida "analises/00_fontes/tempos_desenvolvimento_historias.csv"
& "c:/Users/gerson.ramos/OneDrive - Compass UOL/Projetos/Stellantis/Jira_novo/.venv/Scripts/python.exe" "analises/simular_prazo_squads_comercial_dividido.py" --entrada "analises/00_fontes/tempos_desenvolvimento_historias.csv" --saida-lakes "analises/03_otimizacao/prazo_squads_dividido_lakes.csv" --saida-squads "analises/03_otimizacao/prazo_squads_dividido_resumo.csv" --saida-detalhe "analises/03_otimizacao/prazo_squads_dividido_alocacoes.csv" --saida-relatorio "analises/03_otimizacao/prazo_squads_dividido_relatorio.md"

# (Opcional) Atualizar visualizações
& "c:/Users/gerson.ramos/OneDrive - Compass UOL/Projetos/Stellantis/Jira_novo/.venv/Scripts/python.exe" "analises/gerar_timeline_historias_gantt.py" --entrada "analises/03_otimizacao/prazo_squads_dividido_alocacoes.csv" --saida "analises/04_visualizacoes/timeline_historias_gantt.md"
& "c:/Users/gerson.ramos/OneDrive - Compass UOL/Projetos/Stellantis/Jira_novo/.venv/Scripts/python.exe" "analises/gerar_timeline_html_plotly.py" --entrada "analises/03_otimizacao/prazo_squads_dividido_alocacoes.csv" --saida "analises/04_visualizacoes/timeline_historias_interativo.html"
