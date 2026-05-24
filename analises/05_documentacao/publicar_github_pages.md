# Publicar timeline no GitHub Pages

## Arquivos já preparados

Os arquivos de publicação já foram gerados na pasta [docs](../../docs):

- [docs/index.html](../../docs/index.html)
- [docs/timeline_gantt_detalhada_historias.json](../../docs/timeline_gantt_detalhada_historias.json)
- [docs/cenarios_resumo.csv](../../docs/cenarios_resumo.csv)
- [docs/validacao_timeline_historias.csv](../../docs/validacao_timeline_historias.csv)
- [docs/.nojekyll](../../docs/.nojekyll)

## Regerar a publicação

Sempre que recalcular cenários ou recriar o gráfico, execute:

```powershell
powershell -ExecutionPolicy Bypass -File .\analises\05_documentacao\preparar_github_pages.ps1 -PythonExe ".\.venv\Scripts\python.exe"
```

## Publicar no GitHub

1. Suba o repositório para o GitHub.
2. Abra **Settings** > **Pages**.
3. Em **Build and deployment**, escolha **Deploy from a branch**.
4. Selecione a branch principal e a pasta **/docs**.
5. Salve.
6. Aguarde a URL pública ser gerada pelo GitHub Pages.

## Observação

O [docs/index.html](../../docs/index.html) já está preparado para buscar o JSON relativo da própria pasta, então funciona direto no GitHub Pages sem ajuste adicional.
