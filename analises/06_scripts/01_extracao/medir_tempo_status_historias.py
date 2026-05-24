"""
Mede o tempo em dias corridos que as histórias levam em:
  - Fase Dev: entrada em IN DEVELOPMENT → entrada em Waiting Test
  - Fase QA : entrada em Waiting Test   → entrada em Done

Regras:
  - Medida em dias corridos (diferença simples entre timestamps, convertida para dias)
  - Histórias que passaram por Canceled em qualquer ponto são ignoradas
  - Histórias sem os dois eventos da fase (ciclo incompleto) são ignoradas naquela fase
  - Transições com diferença < 5 minutos são ignoradas (mudanças manuais instantâneas no Jira)
"""

import argparse
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

FUSO = ZoneInfo("America/Sao_Paulo")
DELTA_MINIMO = timedelta(minutes=5)


def parse_dt(valor: str) -> datetime:
    """Parseia ISO 8601 com offset e converte para horário de Brasília (sem timezone)."""
    dt = datetime.fromisoformat(valor)
    if dt.tzinfo is not None:
        dt = dt.astimezone(FUSO).replace(tzinfo=None)
    return dt


def dias_corridos(inicio: datetime, fim: datetime) -> float:
    """Diferença em dias corridos (pode ter fração de dia)."""
    return (fim - inicio).total_seconds() / 86400


def processar(caminho_csv: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = pd.read_csv(caminho_csv)
    df["Data Mudanca"] = df["Data Mudanca"].apply(parse_dt)
    df = df.sort_values(["Chave", "Data Mudanca"])

    # Excluir histórias que passaram por Canceled em qualquer ponto
    chaves_canceladas = set(df[df["Status Novo"] == "Canceled"]["Chave"])
    df = df[~df["Chave"].isin(chaves_canceladas)].copy()

    resultados = []

    for chave, grupo in df.groupby("Chave"):
        grupo = grupo.sort_values("Data Mudanca")
        titulo = grupo["Titulo"].iloc[0]
        squad = grupo["Squad"].iloc[0]

        def primeira_entrada(status: str):
            linha = grupo[grupo["Status Novo"] == status]
            return linha["Data Mudanca"].iloc[0] if not linha.empty else None

        entrada_dev  = primeira_entrada("IN DEVELOPMENT")
        entrada_wt   = primeira_entrada("Waiting Test")
        entrada_done = primeira_entrada("Done")

        # Fase Dev: ciclo completo + delta mínimo de 5 minutos
        dias_dev = None
        if (entrada_dev is not None and entrada_wt is not None
                and (entrada_wt - entrada_dev) >= DELTA_MINIMO):
            dias_dev = round(dias_corridos(entrada_dev, entrada_wt), 4)

        # Fase QA: ciclo completo + delta mínimo de 5 minutos
        dias_qa = None
        if (entrada_wt is not None and entrada_done is not None
                and (entrada_done - entrada_wt) >= DELTA_MINIMO):
            dias_qa = round(dias_corridos(entrada_wt, entrada_done), 4)

        resultados.append({
            "chave": chave,
            "titulo": titulo,
            "squad": squad,
            "entrada_dev": entrada_dev.strftime("%d/%m/%Y %H:%M") if entrada_dev else None,
            "entrada_waiting_test": entrada_wt.strftime("%d/%m/%Y %H:%M") if entrada_wt else None,
            "entrada_done": entrada_done.strftime("%d/%m/%Y %H:%M") if entrada_done else None,
            "dias_corridos_dev": dias_dev,
            "dias_corridos_qa": dias_qa,
        })

    df_resultado = pd.DataFrame(resultados)

    # -----------------------------------------------------------------------
    # Resumo agregado — SOMENTE histórias com AMBAS as fases completas
    # (garante que ciclos parciais não distorcem nenhuma das médias)
    # -----------------------------------------------------------------------
    df_completo = df_resultado[
        df_resultado["dias_corridos_dev"].notna() &
        df_resultado["dias_corridos_qa"].notna()
    ].copy()

    linhas_resumo = []

    def resumo_fase(df_base: pd.DataFrame, coluna: str, nome: str):
        validos = df_base[coluna].dropna()
        if validos.empty:
            return
        linhas_resumo.append({
            "fase": nome,
            "historias_ciclo_completo": len(validos),
            "media_dias_corridos": round(validos.mean(), 2),
            "mediana_dias_corridos": round(validos.median(), 2),
            "min_dias_corridos": round(validos.min(), 4),
            "max_dias_corridos": round(validos.max(), 2),
            "desvio_padrao": round(validos.std(), 2),
        })

    resumo_fase(df_completo, "dias_corridos_dev", "Dev (IN DEVELOPMENT -> Waiting Test)")
    resumo_fase(df_completo, "dias_corridos_qa",  "QA  (Waiting Test -> Done)")

    for squad_nome, grp in df_completo.groupby("squad"):
        resumo_fase(grp, "dias_corridos_dev", f"Dev [{squad_nome}]")
        resumo_fase(grp, "dias_corridos_qa",  f"QA  [{squad_nome}]")

    df_resumo = pd.DataFrame(linhas_resumo)
    return df_resultado, df_resumo


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mede tempo em dias corridos por fase (Dev e QA) por historia."
    )
    parser.add_argument(
        "--entrada",
        default="analises/historico_historias_completo.csv",
    )
    parser.add_argument(
        "--saida-detalhe",
        default="analises/01_extracao/tempo_fases_por_historia.csv",
    )
    parser.add_argument(
        "--saida-resumo",
        default="analises/01_extracao/tempo_fases_resumo.csv",
    )
    args = parser.parse_args()

    entrada = Path(args.entrada)
    if not entrada.exists():
        raise FileNotFoundError(f"Arquivo nao encontrado: {entrada}")

    print(f"Lendo: {entrada}")
    df_detalhe, df_resumo = processar(entrada)

    saida_detalhe = Path(args.saida_detalhe)
    saida_resumo  = Path(args.saida_resumo)
    saida_detalhe.parent.mkdir(parents=True, exist_ok=True)

    df_detalhe.to_csv(saida_detalhe, index=False)
    df_resumo.to_csv(saida_resumo, index=False)

    print("\n" + "=" * 60)
    geral = df_resumo[df_resumo["fase"].str.startswith(("Dev (", "QA  ("))]
    print(geral.to_string(index=False))

    total = len(df_detalhe)
    completas = df_detalhe["dias_corridos_dev"].notna() & df_detalhe["dias_corridos_qa"].notna()
    print(f"\nHistorias analisadas      : {total}")
    print(f"Com ambas as fases        : {completas.sum()} ({100*completas.sum()/total:.0f}%)")
    print(f"Apenas Dev completo       : {(df_detalhe['dias_corridos_dev'].notna() & df_detalhe['dias_corridos_qa'].isna()).sum()}")
    print(f"Apenas QA completo        : {(df_detalhe['dias_corridos_dev'].isna() & df_detalhe['dias_corridos_qa'].notna()).sum()}")
    print(f"Nenhuma fase completa     : {(df_detalhe['dias_corridos_dev'].isna() & df_detalhe['dias_corridos_qa'].isna()).sum()}")
    print(f"\nDetalhe por historia  : {saida_detalhe}")
    print(f"Resumo por fase/squad : {saida_resumo}")


if __name__ == "__main__":
    main()
