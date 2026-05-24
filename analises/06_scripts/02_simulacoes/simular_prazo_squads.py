import argparse
import csv
import math
from collections import defaultdict
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Dict, List, Tuple


DATA_INICIO_PADRAO = "09/03/2026"
ENGENHEIROS_POR_SQUAD = 8
ANALISTAS_POR_SQUAD = 2

SQUADS = [
    {
        "squad": "Squad 1",
        "engenheiros": 8,
        "analistas": 2,
        "data_inicio": "09/03/2026",
        "fases": [
            {"nome": "BMC + COMPRAS", "lakes": ["BMC", "COMPRAS"]},
            {"nome": "COMERCIAL", "lakes": ["COMERCIAL"]},
        ],
    },
    {
        "squad": "Squad 2",
        "engenheiros": 8,
        "analistas": 2,
        "data_inicio": "01/04/2026",
        "fases": [
            {"nome": "MOPAR", "lakes": ["MOPAR"]},
            {"nome": "RH", "lakes": ["RH"]},
        ],
    },
    {
        "squad": "Squad 3",
        "engenheiros": 8,
        "analistas": 2,
        "data_inicio": "01/04/2026",
        "fases": [
            {"nome": "CLIENTE", "lakes": ["CLIENTE"]},
            {"nome": "FINANCE", "lakes": ["FINANCE"]},
        ],
    },
    {
        "squad": "Squad 4",
        "engenheiros": 8,
        "analistas": 2,
        "data_inicio": "01/04/2026",
        "fases": [
            {"nome": "SUPPLY CHAIN", "lakes": ["SUPPLY CHAIN"]},
        ],
    },
    {
        "squad": "Squad 5",
        "engenheiros": 8,
        "analistas": 2,
        "data_inicio": "01/04/2026",
        "fases": [],
    },
]


def parse_data_br(valor: str) -> date:
    return datetime.strptime(valor, "%d/%m/%Y").date()


def formatar_data_br(valor: date) -> str:
    return valor.strftime("%d/%m/%Y")


def proximo_dia_util(valor: date) -> date:
    data_atual = valor + timedelta(days=1)
    while data_atual.weekday() >= 5:
        data_atual += timedelta(days=1)
    return data_atual


def adicionar_dias_uteis(data_inicio: date, deslocamento_dias_uteis: int) -> date:
    data_atual = data_inicio
    dias_restantes = deslocamento_dias_uteis

    while dias_restantes > 0:
        data_atual += timedelta(days=1)
        if data_atual.weekday() < 5:
            dias_restantes -= 1

    return data_atual


def data_para_offset_util(data_inicio: date, offset_dias_uteis: float) -> date:
    deslocamento = int(math.floor(offset_dias_uteis + 1e-9))
    return adicionar_dias_uteis(data_inicio, deslocamento)


def data_fim_por_duracao(data_inicio: date, inicio_offset_dias_uteis: float, duracao_dias_uteis: float) -> date:
    if duracao_dias_uteis <= 0:
        return data_para_offset_util(data_inicio, inicio_offset_dias_uteis)

    inicio_real = data_para_offset_util(data_inicio, inicio_offset_dias_uteis)
    dias_ocupados = max(1, int(math.ceil(duracao_dias_uteis - 1e-9)))
    return adicionar_dias_uteis(inicio_real, dias_ocupados - 1)


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


def agrupar_historias_por_lake(registros: List[Dict[str, object]]) -> Dict[str, List[Dict[str, object]]]:
    agrupado: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for registro in registros:
        agrupado[str(registro["lake"])].append(registro)

    for historias in agrupado.values():
        historias.sort(key=lambda item: int(item["numero"]))

    return dict(agrupado)


def simular_papel_fase(
    squad: str,
    lakes: List[str],
    historias_por_lake: Dict[str, List[Dict[str, object]]],
    campo_dias: str,
    quantidade_pessoas: int,
    prefixo: str,
    data_inicio_fase: date,
) -> Tuple[Dict[str, date], List[Dict[str, object]], float]:
    disponibilidade = [0.0] * quantidade_pessoas
    atribuicoes: List[Dict[str, object]] = []
    fim_por_lake: Dict[str, date] = {}

    fila: List[Tuple[str, Dict[str, object]]] = []
    for lake in lakes:
        for historia in historias_por_lake.get(lake, []):
            if float(historia[campo_dias]) > 0:
                fila.append((lake, historia))

    for lake, historia in fila:
        duracao = float(historia[campo_dias])
        indice_pessoa = min(range(quantidade_pessoas), key=lambda indice: (disponibilidade[indice], indice))
        inicio_offset = disponibilidade[indice_pessoa]
        fim_offset = inicio_offset + duracao
        disponibilidade[indice_pessoa] = fim_offset

        data_inicio = data_para_offset_util(data_inicio_fase, inicio_offset)
        data_fim = data_fim_por_duracao(data_inicio_fase, inicio_offset, duracao)

        atribuicoes.append(
            {
                "squad": squad,
                "lake": lake,
                "id_historia": historia["id_historia"],
                "numero": historia["numero"],
                "titulo": historia["titulo"],
                "papel": prefixo,
                "recurso": f"{prefixo} {indice_pessoa + 1}",
                "duracao_dias_uteis": duracao,
                "inicio_dias_uteis": inicio_offset,
                "fim_dias_uteis": fim_offset,
                "data_inicio": formatar_data_br(data_inicio),
                "data_fim": formatar_data_br(data_fim),
            }
        )

        fim_por_lake[lake] = max(fim_por_lake.get(lake, data_fim), data_fim)

    return fim_por_lake, atribuicoes, max(disponibilidade, default=0.0)


def simular_fase(
    squad: str,
    lakes: List[str],
    historias_por_lake: Dict[str, List[Dict[str, object]]],
    engenheiros: int,
    analistas: int,
    data_inicio_fase: date,
) -> Tuple[List[Dict[str, object]], List[Dict[str, object]], date]:
    fim_eng, atribuicoes_eng, prazo_eng = simular_papel_fase(
        squad,
        lakes,
        historias_por_lake,
        "engenheiro_dias",
        engenheiros,
        "Engenheiro",
        data_inicio_fase,
    )
    fim_ana, atribuicoes_ana, prazo_ana = simular_papel_fase(
        squad,
        lakes,
        historias_por_lake,
        "analista_dias",
        analistas,
        "Analista",
        data_inicio_fase,
    )

    resumo_lakes: List[Dict[str, object]] = []
    data_fim_fase = data_inicio_fase

    for lake in lakes:
        data_fim_eng = fim_eng.get(lake)
        data_fim_ana = fim_ana.get(lake)

        if data_fim_eng and data_fim_ana:
            data_fim_lake = max(data_fim_eng, data_fim_ana)
        elif data_fim_eng:
            data_fim_lake = data_fim_eng
        elif data_fim_ana:
            data_fim_lake = data_fim_ana
        else:
            data_fim_lake = data_inicio_fase

        data_fim_fase = max(data_fim_fase, data_fim_lake)

        historias = historias_por_lake.get(lake, [])
        resumo_lakes.append(
            {
                "squad": squad,
                "lake": lake,
                "historias": len(historias),
                "data_inicio": formatar_data_br(data_inicio_fase),
                "data_fim": formatar_data_br(data_fim_lake),
                "prazo_total_dias_corridos": (data_fim_lake - data_inicio_fase).days + 1,
                "total_engenheiro_dias": sum(float(historia["engenheiro_dias"]) for historia in historias),
                "total_analista_dias": sum(float(historia["analista_dias"]) for historia in historias),
            }
        )

    return resumo_lakes, atribuicoes_eng + atribuicoes_ana, data_fim_fase


def simular_squads(registros: List[Dict[str, object]], data_inicio_projeto: date) -> Tuple[List[Dict[str, object]], List[Dict[str, object]], List[Dict[str, object]]]:
    historias_por_lake = agrupar_historias_por_lake(registros)
    resumo_lakes: List[Dict[str, object]] = []
    atribuicoes: List[Dict[str, object]] = []
    resumo_squads: List[Dict[str, object]] = []

    for configuracao in SQUADS:
        squad = str(configuracao["squad"])
        engenheiros = int(configuracao.get("engenheiros", ENGENHEIROS_POR_SQUAD))
        analistas = int(configuracao.get("analistas", ANALISTAS_POR_SQUAD))
        fases = configuracao.get("fases", [])

        data_inicio_squad = parse_data_br(str(configuracao.get("data_inicio", formatar_data_br(data_inicio_projeto))))

        if not fases:
            resumo_squads.append(
                {
                    "squad": squad,
                    "engenheiros": engenheiros,
                    "analistas": analistas,
                    "data_inicio": formatar_data_br(data_inicio_squad),
                    "data_fim": "",
                    "lakes": "",
                }
            )
            continue

        inicio_fase = data_inicio_squad
        fim_squad = data_inicio_squad
        lakes_squad: List[str] = []

        for indice, fase in enumerate(fases):
            lakes = list(fase["lakes"])
            lakes_squad.extend(lakes)
            resumo_fase, atribuicoes_fase, fim_fase = simular_fase(
                squad,
                lakes,
                historias_por_lake,
                engenheiros,
                analistas,
                inicio_fase,
            )
            resumo_lakes.extend(resumo_fase)
            atribuicoes.extend(atribuicoes_fase)
            fim_squad = max(fim_squad, fim_fase)

            if indice < len(fases) - 1:
                inicio_fase = proximo_dia_util(fim_fase)

        resumo_squads.append(
            {
                "squad": squad,
                "engenheiros": engenheiros,
                "analistas": analistas,
                    "data_inicio": formatar_data_br(data_inicio_squad),
                "data_fim": formatar_data_br(fim_squad),
                "lakes": " -> ".join(lakes_squad),
            }
        )

    resumo_lakes.sort(key=lambda item: (item["squad"], datetime.strptime(item["data_inicio"], "%d/%m/%Y"), item["lake"]))
    atribuicoes.sort(key=lambda item: (item["squad"], item["lake"], item["papel"], datetime.strptime(item["data_inicio"], "%d/%m/%Y"), item["recurso"]))

    return resumo_lakes, atribuicoes, resumo_squads


def salvar_csv(caminho: Path, linhas: List[Dict[str, object]], campos: List[str]) -> None:
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        writer = csv.DictWriter(arquivo, fieldnames=campos)
        writer.writeheader()
        writer.writerows(linhas)


def salvar_relatorio_markdown(caminho: Path, resumo_lakes: List[Dict[str, object]], resumo_squads: List[Dict[str, object]]) -> None:
    linhas = [
        "# Simulação por Squad",
        "",
        "Premissas:",
        "- início do projeto em 09/03/2026",
        "- cada squad com 8 engenheiros e 2 analistas",
        "- Squad 1: BMC e COMPRAS; depois COMERCIAL",
        "- Squad 2: MOPAR; depois RH",
        "- Squad 3: CLIENTE; depois FINANCE",
        "- Squad 4: SUPPLY CHAIN",
        "- Squad 5: sem alocação informada",
        "",
        "## Resumo por squad",
        "",
        "| Squad | Eng. | Anal. | Início | Fim | Lakes |",
        "|---|---:|---:|---|---|---|",
    ]

    for item in resumo_squads:
        linhas.append(
            f"| {item['squad']} | {item['engenheiros']} | {item['analistas']} | {item['data_inicio']} | {item['data_fim']} | {item['lakes']} |"
        )

    linhas.extend(
        [
            "",
            "## Resumo por lake",
            "",
            "| Squad | Lake | Histórias | Início | Fim | Prazo (corridos) |",
            "|---|---|---:|---|---|---:|",
        ]
    )

    for item in resumo_lakes:
        linhas.append(
            f"| {item['squad']} | {item['lake']} | {item['historias']} | {item['data_inicio']} | {item['data_fim']} | {item['prazo_total_dias_corridos']} |"
        )

    caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Simula cronograma por squad a partir da base de histórias por lake.")
    parser.add_argument(
        "--entrada",
        default="analises/tempos_desenvolvimento_historias.csv",
        help="CSV de entrada com tempos por história",
    )
    parser.add_argument(
        "--data-inicio",
        default=DATA_INICIO_PADRAO,
        help="Data de início da simulação no formato dd/mm/aaaa",
    )
    parser.add_argument(
        "--saida-lakes",
        default="analises/prazo_squads_lakes.csv",
        help="CSV de saída com resumo por lake",
    )
    parser.add_argument(
        "--saida-squads",
        default="analises/prazo_squads_resumo.csv",
        help="CSV de saída com resumo por squad",
    )
    parser.add_argument(
        "--saida-detalhe",
        default="analises/prazo_squads_alocacoes.csv",
        help="CSV de saída com alocação detalhada",
    )
    parser.add_argument(
        "--saida-relatorio",
        default="analises/prazo_squads_relatorio.md",
        help="Relatório markdown de saída",
    )
    args = parser.parse_args()

    registros = ler_csv_historias(Path(args.entrada))
    data_inicio = parse_data_br(args.data_inicio)
    resumo_lakes, atribuicoes, resumo_squads = simular_squads(registros, data_inicio)

    salvar_csv(
        Path(args.saida_lakes),
        resumo_lakes,
        [
            "squad",
            "lake",
            "historias",
            "data_inicio",
            "data_fim",
            "prazo_total_dias_corridos",
            "total_engenheiro_dias",
            "total_analista_dias",
        ],
    )
    salvar_csv(
        Path(args.saida_squads),
        resumo_squads,
        [
            "squad",
            "engenheiros",
            "analistas",
            "data_inicio",
            "data_fim",
            "lakes",
        ],
    )
    salvar_csv(
        Path(args.saida_detalhe),
        atribuicoes,
        [
            "squad",
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
    salvar_relatorio_markdown(Path(args.saida_relatorio), resumo_lakes, resumo_squads)

    print(f"Squads simuladas: {len(resumo_squads)}")
    print(f"Resumo por squad: {args.saida_squads}")
    print(f"Resumo por lake: {args.saida_lakes}")
    print(f"Detalhe: {args.saida_detalhe}")
    print(f"Relatório: {args.saida_relatorio}")


if __name__ == "__main__":
    main()
