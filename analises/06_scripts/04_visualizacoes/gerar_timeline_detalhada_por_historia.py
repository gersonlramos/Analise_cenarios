import argparse
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
from plotly.utils import PlotlyJSONEncoder


def carregar_e_consolidar(caminho_csv: Path) -> pd.DataFrame:
    """Carregar alocações por papel (Engenheiro/Analista) para timeline detalhada."""
    df = pd.read_csv(caminho_csv)

    for coluna in ["data_inicio", "data_fim"]:
        df[coluna] = pd.to_datetime(df[coluna], format="%d/%m/%Y", errors="coerce")

    alocacoes = df.dropna(subset=["data_inicio", "data_fim"]).copy()
    alocacoes["duracao_dias_uteis"] = alocacoes["duracao_dias_uteis"].fillna(1).astype(int)
    alocacoes["id_historia_curto"] = alocacoes["id_historia"]

    # Ordenar pelos lakes na ordem especificada
    ordem_lakes = ["BMC", "COMPRAS", "MOPAR", "CLIENTE", "SHARED SERVICES", "SHARED SERVICES A", "SHARED SERVICES B", "RH", "FINANCE", "SUPPLY CHAIN", "COMERCIAL"]
    alocacoes["lake_order"] = alocacoes["lake"].map({lake: idx for idx, lake in enumerate(ordem_lakes)})
    ordem_papel = {"Engenheiro": 0, "Analista": 1}
    alocacoes["papel_order"] = alocacoes["papel"].map(ordem_papel).fillna(9)
    
    # Preencher com um valor alto para lakes desconhecidos
    alocacoes["lake_order"] = alocacoes["lake_order"].fillna(999)
    
    # Ordenar (BMC em cima, Commercial embaixo)
    alocacoes = alocacoes.sort_values(["lake_order", "numero", "papel_order", "recurso"], ascending=[True, True, True, True])

    # Adicionar ordem para o eixo Y (agrupado por Lake, sem título longo)
    alocacoes["y_label"] = (
        alocacoes["lake"] + " / " + alocacoes["id_historia_curto"] + " " + alocacoes["papel"]
    )

    # Colunas de validação e exibição (evita NaN no hover)
    alocacoes["dias_uteis_no_intervalo"] = alocacoes.apply(
        lambda row: len(pd.bdate_range(start=row["data_inicio"], end=row["data_fim"])),
        axis=1,
    )
    alocacoes["status_validacao"] = alocacoes.apply(
        lambda row: "OK_INTERVALO" if row["dias_uteis_no_intervalo"] >= 1 else "DATA_INVALIDA",
        axis=1,
    )
    alocacoes["data_inicio_fmt"] = alocacoes["data_inicio"].dt.strftime("%d/%m/%Y").fillna("N/A")
    alocacoes["data_fim_fmt"] = alocacoes["data_fim"].dt.strftime("%d/%m/%Y").fillna("N/A")

    return alocacoes


def mapas_cores():
    """Definir cores para squads."""
    cores_squad = {
        "Squad 1": "#80FF00",  # verde lima
        "Squad 2": "#FFD700",  # amarelo
        "Squad 3": "#FF8C00",  # laranja
        "Squad 4": "#228B22",  # verde escuro
        "Squad 5": "#00CED1",  # ciano/azul claro
        "Squad 6": "#7B2D8B",  # roxo escuro
        "Squad 7": "#CC99FF",  # lilás claro
        "Squad 8": "#C0C0C0",  # cinza
    }
    return cores_squad


def _criar_timeline_cenario(df: pd.DataFrame, nome_cenario: str, cores_squad: dict):
    fig = px.timeline(
        df,
        x_start="data_inicio",
        x_end="data_fim",
        y="y_label",
        color="squad",
        color_discrete_map=cores_squad,
        custom_data=[
            "id_historia",
            "titulo",
            "lake",
            "papel",
            "recurso",
            "duracao_dias_uteis",
            "data_inicio_fmt",
            "data_fim_fmt",
            "dias_uteis_no_intervalo",
            "status_validacao",
        ],
    )

    fig.update_traces(
        marker=dict(
            line=dict(color="rgba(0,0,0,0.18)", width=1),
            pattern=dict(shape="", solidity=0),
        ),
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "<b>%{customdata[1]}</b><br>"
            "Cenário: " + nome_cenario + "<br>"
            "Squad: %{fullData.name}<br>"
            "Lake: %{customdata[2]}<br>"
            "Papel: %{customdata[3]}<br>"
            "Recurso: %{customdata[4]}<br>"
            "Início: %{customdata[6]}<br>"
            "Fim: %{customdata[7]}<br>"
            "Duração (útil no input): %{customdata[5]} dias<br>"
            "Dias úteis (Início→Fim): %{customdata[8]} dias<br>"
            "Validação: %{customdata[9]}<extra></extra>"
        )
    )
    return fig


def exportar_dados_cenarios_json(cenarios: list[tuple[str, pd.DataFrame]], saida_json: Path) -> dict:
    """Exporta dados de cenários para JSON externo consumido pelo HTML dinâmico."""
    cores_squad = mapas_cores()
    if not cenarios:
        raise ValueError("Nenhum cenário disponível para exportar")

    data_min = None
    data_max = None
    cenarios_json = []

    for nome_cenario, df in cenarios:
        fig_cenario = _criar_timeline_cenario(df, nome_cenario, cores_squad)
        fig_json = fig_cenario.to_plotly_json()

        inicio_projeto = df["data_inicio"].min()
        fim_projeto = df["data_fim"].max()

        data_min = inicio_projeto if data_min is None else min(data_min, inicio_projeto)
        data_max = fim_projeto if data_max is None else max(data_max, fim_projeto)

        cenarios_json.append(
            {
                "nome": nome_cenario,
                "inicio_projeto": inicio_projeto.strftime("%d/%m/%Y"),
                "fim_projeto": fim_projeto.strftime("%d/%m/%Y"),
                "y_labels": df["y_label"].tolist(),
                "height": max(1000, len(df) * 20 + 220),
                "traces": fig_json["data"],
            }
        )

    payload = {
        "titulo": "Timeline de Histórias por Lake e Desenvolvimento",
        "x_range_min": data_min.strftime("%Y-%m-%d"),
        "x_range_max": data_max.strftime("%Y-%m-%d"),
        "cenarios": cenarios_json,
    }

    saida_json.parent.mkdir(parents=True, exist_ok=True)
    saida_json.write_text(
        json.dumps(payload, ensure_ascii=False, cls=PlotlyJSONEncoder),
        encoding="utf-8",
    )
    return payload


def gerar_html_dinamico(saida_html: Path, nome_json: str) -> None:
    """Gera HTML leve que busca dados externos via fetch (JSON)."""
    html = f"""<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Timeline Dinâmica</title>
    <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 0; background: #f6f6f8; }}
        .topbar {{ display:flex; gap:12px; align-items:flex-start; padding:10px 14px; }}
        .card {{ background:#fff; border:1px solid #bdbdbd; border-radius:4px; padding:8px 10px; }}
        #cenario {{ min-width: 220px; font-size: 14px; }}
        #datas {{ font-size: 13px; line-height: 1.45; color:#222; }}
        #chart {{ width: 100%; height: calc(100vh - 76px); }}
        #erro {{ color:#b00020; padding:8px 14px; display:none; }}
    </style>
</head>
<body>
    <div class="topbar">
        <div class="card">
            <label for="cenario"><b>Cenário</b></label><br />
            <select id="cenario"></select>
        </div>
        <div class="card" id="datas"></div>
    </div>
    <div id="erro"></div>
    <div id="chart"></div>

    <script>
        const dataUrl = "{nome_json}";
        const select = document.getElementById("cenario");
        const datas = document.getElementById("datas");
        const erro = document.getElementById("erro");
        const chart = document.getElementById("chart");

        function montarLayout(payload, cenario) {{
            return {{
                title: {{ text: payload.titulo, x: 0.12, xanchor: "left", font: {{ size: 16, color: "#333" }} }},
                xaxis: {{
                    title: "Data",
                    type: "date",
                    tickformat: "%d/%m/%Y",
                    showgrid: true,
                    gridwidth: 1,
                    gridcolor: "rgba(180, 180, 180, 0.25)",
                    range: [payload.x_range_min, payload.x_range_max],
                    side: "top"
                }},
                yaxis: {{
                    title: "Lake / História",
                    autorange: "reversed",
                    showgrid: false,
                    tickfont: {{ size: 10 }},
                    automargin: true,
                    categoryorder: "array",
                    categoryarray: cenario.y_labels
                }},
                barmode: "overlay",
                hovermode: "closest",
                height: cenario.height,
                legend: {{
                    title: {{ text: "Squad" }},
                    x: 0.99,
                    y: 0.99,
                    xanchor: "right",
                    yanchor: "top",
                    bgcolor: "rgba(255,255,255,0.95)",
                    bordercolor: "rgba(0,0,0,0.3)",
                    borderwidth: 1,
                    font: {{ size: 11 }}
                }},
                margin: {{ l: 280, r: 30, t: 70, b: 50 }},
                plot_bgcolor: "rgba(245,245,245,1)",
                paper_bgcolor: "white",
                font: {{ family: "Arial, sans-serif", size: 11 }}
            }};
        }}

        function atualizarDatas(cenario) {{
            datas.innerHTML = `<b>Início projeto:</b> ${{cenario.inicio_projeto}}<br/><b>Fim projeto:</b> ${{cenario.fim_projeto}}`;
        }}

        async function init() {{
            try {{
                const resp = await fetch(dataUrl);
                if (!resp.ok) throw new Error(`Falha ao buscar JSON (${{resp.status}})`);
                const payload = await resp.json();

                payload.cenarios.forEach((c, idx) => {{
                    const opt = document.createElement("option");
                    opt.value = String(idx);
                    opt.textContent = c.nome;
                    select.appendChild(opt);
                }});

                function render(idx) {{
                    const cenario = payload.cenarios[idx];
                    atualizarDatas(cenario);
                    Plotly.react(chart, cenario.traces, montarLayout(payload, cenario), {{ responsive: true, displaylogo: false }});
                }}

                select.addEventListener("change", () => render(Number(select.value)));
                render(0);
            }} catch (e) {{
                erro.style.display = "block";
                erro.innerHTML = `Não foi possível carregar os dados dinâmicos. Rode em servidor local. Erro: ${{e.message}}`;
            }}
        }}

        init();
    </script>
</body>
</html>
"""
    saida_html.parent.mkdir(parents=True, exist_ok=True)
    saida_html.write_text(html, encoding="utf-8")


def exportar_validacao(df: pd.DataFrame, saida_csv: Path) -> None:
    colunas = [
        "squad",
        "lake",
        "id_historia",
        "numero",
        "papel",
        "recurso",
        "data_inicio_fmt",
        "data_fim_fmt",
        "duracao_dias_uteis",
        "dias_uteis_no_intervalo",
        "status_validacao",
    ]
    saida_csv.parent.mkdir(parents=True, exist_ok=True)
    df[colunas].to_csv(saida_csv, index=False)


def validar_fonte_linha_a_linha(caminho_csv: Path) -> tuple[int, int, int]:
    df = pd.read_csv(caminho_csv)
    for coluna in ["data_inicio", "data_fim"]:
        df[coluna] = pd.to_datetime(df[coluna], format="%d/%m/%Y", errors="coerce")

    df["dias_uteis_intervalo"] = df.apply(
        lambda row: len(pd.bdate_range(start=row["data_inicio"], end=row["data_fim"]))
        if pd.notna(row["data_inicio"]) and pd.notna(row["data_fim"]) else -1,
        axis=1,
    )
    ok = int((df["dias_uteis_intervalo"] == df["duracao_dias_uteis"]).sum())
    total = int(len(df))
    divergentes = total - ok
    return total, ok, divergentes


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gera timeline Gantt detalhada por história com datas no topo."
    )
    parser.add_argument(
        "--entrada",
        default="analises/03_otimizacao/prazo_squads_dividido_alocacoes_atualizado.csv",
        help="CSV de alocações por história",
    )
    parser.add_argument(
        "--saida",
        default="analises/04_visualizacoes/timeline_gantt_detalhada_historias.html",
        help="Arquivo HTML de saída",
    )
    parser.add_argument(
        "--saida-json",
        default="analises/04_visualizacoes/timeline_gantt_detalhada_historias.json",
        help="JSON de dados para o HTML dinâmico",
    )
    parser.add_argument(
        "--saida-validacao",
        default="analises/04_visualizacoes/validacao_timeline_historias.csv",
        help="CSV com validação de duração útil por história",
    )
    args = parser.parse_args()

    entrada = Path(args.entrada)
    saida = Path(args.saida)
    saida_json = Path(args.saida_json)
    saida_validacao = Path(args.saida_validacao)

    cenarios_preferenciais = [
        ("Pior caso (8 squads refinado)", Path("analises/03_otimizacao/cenario_pior_alocacoes.csv")),
        ("Esperado (8 squads refinado)", Path("analises/03_otimizacao/cenario_esperado_alocacoes.csv")),
        ("Otimista (8 squads refinado)", Path("analises/03_otimizacao/cenario_otimista_alocacoes.csv")),
        ("Base (5 squads)", Path("analises/03_otimizacao/cenario_base_5_alocacoes.csv")),
        ("Referencia (8 squads)", Path("analises/03_otimizacao/cenario_referencia_8_alocacoes.csv")),
        ("Melhor combinacao (5 squads)", Path("analises/03_otimizacao/cenario_melhor_5_alocacoes.csv")),
        ("Melhor combinacao (8 squads)", Path("analises/03_otimizacao/cenario_melhor_8_alocacoes.csv")),
        ("So desenvolvedores (5 squads)", Path("analises/03_otimizacao/cenario_somente_devs_5_alocacoes.csv")),
        ("Devs 11 por squad (meta 30/06)", Path("analises/03_otimizacao/cenario_devs11_prazo30jun_alocacoes.csv")),
        ("6 squads +10 devs", Path("analises/03_otimizacao/cenario_devs_6squads_alocacoes.csv")),
        ("7 squads +10 devs", Path("analises/03_otimizacao/cenario_devs_7squads_alocacoes.csv")),
        ("5 squads 12 devs", Path("analises/03_otimizacao/cenario_devs_12por5squads_alocacoes.csv")),
        ("5 squads 20 devs", Path("analises/03_otimizacao/cenario_devs_20por5squads_alocacoes.csv")),
        ("Squad 6 antecipada em Comercial", Path("analises/03_otimizacao/cenario_sq6_antecipada_comercial_alocacoes.csv")),
        ("8 squads dedicadas", Path("analises/03_otimizacao/cenario_8sq_dedicadas_alocacoes.csv")),
        ("8 squads + reforco Supply Chain", Path("analises/03_otimizacao/cenario_8sq_reforco_supply_chain_alocacoes.csv")),
    ]

    cenarios_entrada = [(nome, caminho) for nome, caminho in cenarios_preferenciais if caminho.exists()]
    if not cenarios_entrada:
        cenarios_entrada = [("Cenário Atual", entrada)]
        cenario_base = Path("analises/02_simulacoes/prazo_squads_alocacoes.csv")
        if cenario_base.exists() and cenario_base.resolve() != entrada.resolve():
            cenarios_entrada.append(("Cenário Base", cenario_base))

    cenarios_df: list[tuple[str, pd.DataFrame]] = []
    for nome, caminho in cenarios_entrada:
        if caminho.exists():
            cenarios_df.append((nome, carregar_e_consolidar(caminho)))

    if not cenarios_df:
        raise FileNotFoundError("Nenhum arquivo de cenário encontrado para gerar o gráfico")

    df = cenarios_df[0][1]
    exportar_dados_cenarios_json(cenarios_df, saida_json)
    gerar_html_dinamico(saida, saida_json.name)
    exportar_validacao(df, saida_validacao)
    total_linhas_fonte, linhas_ok_fonte, linhas_divergentes_fonte = validar_fonte_linha_a_linha(entrada)

    print(f"OK Historias consolidadas: {len(df)}")
    print(f"OK Lakes unicos: {df['lake'].nunique()}")
    print(f"OK Squads unicos: {df['squad'].nunique()}")
    print(f"OK Fonte validada (linhas): {total_linhas_fonte}")
    print(f"OK Fonte OK (linhas): {linhas_ok_fonte}")
    print(f"OK Fonte divergente (linhas): {linhas_divergentes_fonte}")
    print(f"OK JSON de cenarios gerado em: {saida_json}")
    print(f"OK HTML dinamico gerado em: {saida}")
    print(f"OK CSV de validacao gerado em: {saida_validacao}")


if __name__ == "__main__":
    main()
