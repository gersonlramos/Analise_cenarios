import argparse
import csv
import math
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple


ENGENHEIROS_POR_LAKE = 8
ANALISTAS_POR_LAKE = 2
CAPACIDADE_ESPECIAL_POR_LAKE = {
    "BMC": {"engenheiros": 1, "analistas": 1},
}
DATA_INICIO_PADRAO = "09/03/2026"


def ler_csv_historias(caminho_csv: Path) -> List[Dict[str, object]]:
    registros: List[Dict[str, object]] = []

    with caminho_csv.open("r", encoding="utf-8", newline="") as arquivo:
        reader = csv.DictReader(arquivo)
        for linha in reader:
            registros.append(
                {
                    "arquivo": linha["arquivo"],
                    "id_historia": linha["id_historia"],
                    "lake": linha["lake"],
                    "numero": int(linha["numero"]),
                    "titulo": linha["titulo"],
                    "engenheiro_dias": float(linha["engenheiro_dias"] or 0),
                    "analista_dias": float(linha["analista_dias"] or 0),
                }
            )

    return registros


def agrupar_por_lake(registros: List[Dict[str, object]]) -> Dict[str, List[Dict[str, object]]]:
    agrupado: Dict[str, List[Dict[str, object]]] = defaultdict(list)

    for registro in registros:
        lake = str(registro["lake"])
        agrupado[lake].append(registro)

    for historias in agrupado.values():
        historias.sort(key=lambda item: int(item["numero"]))

    return dict(sorted(agrupado.items(), key=lambda item: item[0].lower()))


def obter_capacidade_lake(lake: str) -> Tuple[int, int]:
    configuracao = CAPACIDADE_ESPECIAL_POR_LAKE.get(lake, {})
    engenheiros = int(configuracao.get("engenheiros", ENGENHEIROS_POR_LAKE))
    analistas = int(configuracao.get("analistas", ANALISTAS_POR_LAKE))
    return engenheiros, analistas


def parse_data_br(valor: str) -> datetime.date:
    return datetime.strptime(valor, "%d/%m/%Y").date()


def adicionar_dias_uteis(data_inicio: datetime.date, deslocamento_dias_uteis: int) -> datetime.date:
    data_atual = data_inicio
    dias_restantes = deslocamento_dias_uteis

    while dias_restantes > 0:
        data_atual += timedelta(days=1)
        if data_atual.weekday() < 5:
            dias_restantes -= 1

    return data_atual


def data_para_offset_util(data_inicio: datetime.date, offset_dias_uteis: float) -> datetime.date:
    deslocamento = int(math.floor(offset_dias_uteis + 1e-9))
    return adicionar_dias_uteis(data_inicio, deslocamento)


def data_fim_por_duracao(data_inicio: datetime.date, inicio_offset_dias_uteis: float, duracao_dias_uteis: float) -> datetime.date:
    if duracao_dias_uteis <= 0:
        return data_para_offset_util(data_inicio, inicio_offset_dias_uteis)

    inicio_real = data_para_offset_util(data_inicio, inicio_offset_dias_uteis)
    dias_ocupados = max(1, int(math.ceil(duracao_dias_uteis - 1e-9)))
    return adicionar_dias_uteis(inicio_real, dias_ocupados - 1)


def simular_fila(
    historias: List[Dict[str, object]],
    campo_dias: str,
    quantidade_pessoas: int,
    prefixo: str,
    data_inicio: datetime.date,
) -> Tuple[float, List[Dict[str, object]]]:
    disponibilidade = [0.0] * quantidade_pessoas
    atribuicoes: List[Dict[str, object]] = []

    for historia in historias:
        duracao = float(historia[campo_dias])
        if duracao <= 0:
            continue

        indice_pessoa = min(range(quantidade_pessoas), key=lambda indice: (disponibilidade[indice], indice))
        inicio = disponibilidade[indice_pessoa]
        fim = inicio + duracao
        disponibilidade[indice_pessoa] = fim
        data_inicio_historia = data_para_offset_util(data_inicio, inicio)
        data_fim_historia = data_fim_por_duracao(data_inicio, inicio, duracao)

        atribuicoes.append(
            {
                "lake": historia["lake"],
                "id_historia": historia["id_historia"],
                "numero": historia["numero"],
                "titulo": historia["titulo"],
                "papel": prefixo,
                "recurso": f"{prefixo} {indice_pessoa + 1}",
                "duracao_dias_uteis": duracao,
                "inicio_dias_uteis": inicio,
                "fim_dias_uteis": fim,
                "data_inicio": data_inicio_historia.strftime("%d/%m/%Y"),
                "data_fim": data_fim_historia.strftime("%d/%m/%Y"),
            }
        )

    return max(disponibilidade, default=0.0), atribuicoes


def resumir_lakes(registros: List[Dict[str, object]], data_inicio: datetime.date) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    por_lake = agrupar_por_lake(registros)
    resumo: List[Dict[str, object]] = []
    atribuicoes_detalhadas: List[Dict[str, object]] = []

    for lake, historias in por_lake.items():
        qtd_engenheiros, qtd_analistas = obter_capacidade_lake(lake)
        prazo_engenharia_uteis, atribuicoes_eng = simular_fila(
            historias,
            "engenheiro_dias",
            qtd_engenheiros,
            "Engenheiro",
            data_inicio,
        )
        prazo_analise_uteis, atribuicoes_ana = simular_fila(
            historias,
            "analista_dias",
            qtd_analistas,
            "Analista",
            data_inicio,
        )

        prazo_total_uteis = max(prazo_engenharia_uteis, prazo_analise_uteis)
        data_fim = data_fim_por_duracao(data_inicio, 0.0, prazo_total_uteis)
        prazo_total_corridos = (data_fim - data_inicio).days + 1 if prazo_total_uteis > 0 else 0.0

        resumo.append(
            {
                "lake": lake,
                "historias": len(historias),
                "engenheiros": qtd_engenheiros,
                "analistas": qtd_analistas,
                "data_inicio": data_inicio.strftime("%d/%m/%Y"),
                "data_fim": data_fim.strftime("%d/%m/%Y"),
                "total_engenheiro_dias": sum(float(historia["engenheiro_dias"]) for historia in historias),
                "total_analista_dias": sum(float(historia["analista_dias"]) for historia in historias),
                "prazo_engenharia_dias_uteis": prazo_engenharia_uteis,
                "prazo_analise_dias_uteis": prazo_analise_uteis,
                "prazo_total_dias_uteis": prazo_total_uteis,
                "prazo_total_dias_corridos": prazo_total_corridos,
            }
        )

        atribuicoes_detalhadas.extend(atribuicoes_eng)
        atribuicoes_detalhadas.extend(atribuicoes_ana)

    resumo.sort(key=lambda item: (-float(item["prazo_total_dias_corridos"]), str(item["lake"])))
    atribuicoes_detalhadas.sort(key=lambda item: (str(item["lake"]), str(item["papel"]), float(item["inicio_dias_uteis"]), str(item["recurso"])))

    return resumo, atribuicoes_detalhadas


def salvar_csv(caminho: Path, linhas: List[Dict[str, object]], campos: List[str]) -> None:
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        writer = csv.DictWriter(arquivo, fieldnames=campos)
        writer.writeheader()
        writer.writerows(linhas)


def salvar_relatorio_markdown(caminho: Path, resumo: List[Dict[str, object]]) -> None:
    linhas = [
        "# Simulação de Prazo por Lake",
        "",
        "Premissas:",
        "- 8 engenheiros e 2 analistas por lake, exceto BMC com 1 engenheiro e 1 analista",
        "- histórias distribuídas na ordem numérica para o próximo recurso livre",
        "- início real em 09/03/2026",
        "- datas finais calculadas considerando apenas dias úteis (segunda a sexta)",
        "",
        "| Lake | Eng. | Anal. | Histórias | Início | Fim | Prazo Eng. (úteis) | Prazo Anal. (úteis) | Prazo Total (úteis) | Prazo Total (corridos) |",
        "|---|---:|---:|---:|---|---|---:|---:|---:|---:|",
    ]

    for item in resumo:
        linhas.append(
            f"| {item['lake']} | {item['engenheiros']} | {item['analistas']} | {item['historias']} | {item['data_inicio']} | {item['data_fim']} | {item['prazo_engenharia_dias_uteis']:.1f} | {item['prazo_analise_dias_uteis']:.1f} | {item['prazo_total_dias_uteis']:.1f} | {item['prazo_total_dias_corridos']:.1f} |"
        )

    caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Simula prazo de desenvolvimento por lake com filas paralelas de engenheiros e analistas.")
    parser.add_argument(
        "--entrada",
        default="analises/tempos_desenvolvimento_historias.csv",
        help="CSV de entrada com tempos por história",
    )
    parser.add_argument(
        "--saida-resumo",
        default="analises/prazo_lakes_simulado.csv",
        help="CSV de saída com resumo por lake",
    )
    parser.add_argument(
        "--saida-detalhe",
        default="analises/prazo_lakes_alocacoes.csv",
        help="CSV de saída com alocação detalhada por recurso",
    )
    parser.add_argument(
        "--saida-relatorio",
        default="analises/prazo_lakes_simulado.md",
        help="Relatório markdown de saída",
    )
    parser.add_argument(
        "--data-inicio",
        default=DATA_INICIO_PADRAO,
        help="Data de início da simulação no formato dd/mm/aaaa",
    )
    args = parser.parse_args()

    registros = ler_csv_historias(Path(args.entrada))
    data_inicio = parse_data_br(args.data_inicio)
    resumo, atribuicoes = resumir_lakes(registros, data_inicio)

    salvar_csv(
        Path(args.saida_resumo),
        resumo,
        [
            "lake",
            "engenheiros",
            "analistas",
            "historias",
            "data_inicio",
            "data_fim",
            "total_engenheiro_dias",
            "total_analista_dias",
            "prazo_engenharia_dias_uteis",
            "prazo_analise_dias_uteis",
            "prazo_total_dias_uteis",
            "prazo_total_dias_corridos",
        ],
    )
    salvar_csv(
        Path(args.saida_detalhe),
        atribuicoes,
        [
            "lake",
            "id_historia",
            "numero",
            "titulo",
            "papel",
            "recurso",
            "duracao_dias_uteis",
            "inicio_dias_uteis",
            "fim_dias_uteis",
            "data_inicio",
            "data_fim",
        ],
    )
    salvar_relatorio_markdown(Path(args.saida_relatorio), resumo)

    print(f"Lakes simulados: {len(resumo)}")
    print(f"Resumo gerado em: {args.saida_resumo}")
    print(f"Detalhe gerado em: {args.saida_detalhe}")
    print(f"Relatório gerado em: {args.saida_relatorio}")


if __name__ == "__main__":
    main()
