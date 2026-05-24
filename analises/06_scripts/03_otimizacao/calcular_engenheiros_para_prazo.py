"""
Calcula quantos recursos por squad são necessários para terminar o projeto até 30/06/2026.

Simula dois cenários de forma incremental:
  1. Cenário normal (8 eng / 2 analistas) - variando apenas engenheiros
  2. Cenário somente devs (eng + analista = 1 dev fullstack) - variando número de devs

Saída: CSV com data_fim por número de recursos testado.
"""

import sys
from pathlib import Path
import argparse
import pandas as pd
from datetime import datetime

# Permite importar calcular_cenarios_squads de qualquer diretório de execução
_script_dir = Path(__file__).resolve().parent
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

from calcular_cenarios_squads import (
    simular_cenario_papeis,
    simular_cenario_somente_devs,
    montar_cenario_base_5,
    carregar_historias,
    normalizar_config_para_lakes_existentes,
)

META_DATA_FIM = datetime(2026, 6, 30)


def simular_variando_recursos(historias, lake_para_squads, modo, max_recursos):
    """
    Itera de 1 até max_recursos, simula cada configuração e retorna lista de resultados.

    modo:
      "engenheiros" - varia engenheiros, mantém 2 analistas
      "devs"        - varia devs fullstack (sem separação eng/analista)
    """
    resultados = []
    for n in range(1, max_recursos + 1):
        if modo == "engenheiros":
            sim = simular_cenario_papeis(
                historias, lake_para_squads,
                engenheiros_por_squad=n,
                analistas_por_squad=2,
            )
        else:  # devs
            sim = simular_cenario_somente_devs(
                historias, lake_para_squads,
                devs_por_squad=n,
            )

        fim = sim["fim_projeto"]
        atingiu_meta = fim <= META_DATA_FIM.date()
        resultados.append({
            "modo": modo,
            "recursos_por_squad": n,
            "data_fim": fim.strftime("%d/%m/%Y"),
            "prazo_dias_corridos": sim["prazo_corridos"],
            "atingiu_meta_30jun": atingiu_meta,
        })
        print(f"[{modo}] {n:>2} por squad -> fim: {fim.strftime('%d/%m/%Y')}  {'META!' if atingiu_meta else ''}")
        if atingiu_meta:
            break

    return resultados


def main():
    parser = argparse.ArgumentParser(
        description="Calcula quantos recursos por squad são necessários para terminar até 30/06/2026."
    )
    parser.add_argument("--max", type=int, default=20, help="Máximo de recursos por squad a testar (default: 20)")
    parser.add_argument(
        "--saida",
        default="analises/03_otimizacao/engenheiros_para_prazo.csv",
        help="CSV de saída com resultados",
    )
    parser.add_argument(
        "--fonte",
        default="analises/00_fontes/tempos_desenvolvimento_historias.csv",
        help="CSV de histórias",
    )
    args = parser.parse_args()

    historias = carregar_historias(Path(args.fonte))
    lakes_existentes = {h.lake for h in historias}
    lake_para_squads = normalizar_config_para_lakes_existentes(montar_cenario_base_5(), lakes_existentes)

    todos_resultados = []

    # Cenário 1: normal (variando engenheiros, 2 analistas fixos)
    print("\n=== Cenário Normal: variando engenheiros (2 analistas fixos) ===")
    r1 = simular_variando_recursos(historias, lake_para_squads, "engenheiros", args.max)
    todos_resultados.extend(r1)

    # Cenário 2: somente devs (eng + analista em 1 dev fullstack)
    print("\n=== Cenário Somente Devs: variando devs fullstack ===")
    r2 = simular_variando_recursos(historias, lake_para_squads, "devs", args.max)
    todos_resultados.extend(r2)

    df = pd.DataFrame(todos_resultados)
    Path(args.saida).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.saida, index=False)
    print(f"\nResultados salvos em: {args.saida}")

    # Resumo final
    print("\n=== RESUMO ===")
    for modo in ["engenheiros", "devs"]:
        grupo = df[df["modo"] == modo]
        meta = grupo[grupo["atingiu_meta_30jun"] == True]
        if not meta.empty:
            row = meta.iloc[0]
            print(f"[{modo}] Minimo: {int(row['recursos_por_squad'])} por squad -> fim {row['data_fim']}")
        else:
            ultimo = grupo.iloc[-1]
            print(f"[{modo}] Não atingiu meta com até {args.max} por squad (melhor: {ultimo['data_fim']})")


if __name__ == "__main__":
    main()
