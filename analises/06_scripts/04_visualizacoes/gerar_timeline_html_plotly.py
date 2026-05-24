import argparse
from pathlib import Path

import pandas as pd
import plotly.express as px


def carregar_e_consolidar(caminho_csv: Path) -> pd.DataFrame:
    df = pd.read_csv(caminho_csv)

    for coluna in ["data_inicio", "data_fim"]:
        df[coluna] = pd.to_datetime(df[coluna], format="%d/%m/%Y", errors="coerce")

    agrupado = (
        df.groupby(["squad", "lake", "id_historia", "numero", "titulo"], as_index=False)
        .agg(
            data_inicio=("data_inicio", "min"),
            data_fim=("data_fim", "max"),
        )
        .sort_values(["squad", "lake", "numero"])
    )

    agrupado["historia_label"] = agrupado["id_historia"] + " - " + agrupado["titulo"].str.slice(0, 80)
    agrupado["squad_lake"] = agrupado["squad"] + " | " + agrupado["lake"]

    return agrupado


def gerar_html(df: pd.DataFrame, saida_html: Path) -> None:
    fig = px.timeline(
        df,
        x_start="data_inicio",
        x_end="data_fim",
        y="squad_lake",
        color="squad",
        hover_name="id_historia",
        hover_data={
            "titulo": True,
            "numero": True,
            "data_inicio": "|%d/%m/%Y",
            "data_fim": "|%d/%m/%Y",
            "squad": True,
            "lake": True,
            "squad_lake": False,
        },
        title="Timeline do Projeto por História (HTML Interativo)",
    )

    fig.update_yaxes(autorange="reversed")
    fig.update_layout(
        xaxis_title="Data",
        yaxis_title="Squad | Lake",
        legend_title="Squad",
        hoverlabel_align="left",
        height=max(700, int(df["squad_lake"].nunique() * 120)),
    )

    fig.write_html(str(saida_html), include_plotlyjs="cdn")


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera timeline HTML interativo por história usando Plotly.")
    parser.add_argument(
        "--entrada",
        default="analises/prazo_squads_dividido_alocacoes.csv",
        help="CSV de alocações por história",
    )
    parser.add_argument(
        "--saida",
        default="analises/timeline_historias_interativo.html",
        help="Arquivo HTML de saída",
    )
    args = parser.parse_args()

    entrada = Path(args.entrada)
    saida = Path(args.saida)

    df = carregar_e_consolidar(entrada)
    gerar_html(df, saida)

    print(f"Histórias consolidadas: {len(df)}")
    print(f"HTML gerado em: {saida}")


if __name__ == "__main__":
    main()
