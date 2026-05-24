import argparse
import csv
import math
from collections import defaultdict
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Dict, List, Tuple


DATA_INICIO_SQUAD_1 = "09/03/2026"
DATA_INICIO_DEMAIS = "01/04/2026"


def parse_data_br(valor: str) -> date:
    return datetime.strptime(valor, "%d/%m/%Y").date()


def formatar_data_br(valor: date) -> str:
    return valor.strftime("%d/%m/%Y")


def proximo_dia_util(valor: date) -> date:
    data_atual = valor + timedelta(days=1)
    while data_atual.weekday() >= 5:
        data_atual += timedelta(days=1)
    return data_atual


def adicionar_dias_uteis(data_inicio: date, quantidade: int) -> date:
    data_atual = data_inicio
    restantes = quantidade
    while restantes > 0:
        data_atual += timedelta(days=1)
        if data_atual.weekday() < 5:
            restantes -= 1
    return data_atual


def data_fim_trabalho(data_inicio: date, duracao_dias_uteis: float) -> date:
    if duracao_dias_uteis <= 0:
        return data_inicio
    dias_ocupados = max(1, int(math.ceil(duracao_dias_uteis - 1e-9)))
    return adicionar_dias_uteis(data_inicio, dias_ocupados - 1)


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


def criar_recursos(squad: str, papel: str, quantidade: int, data_inicio: date) -> List[Dict[str, object]]:
    return [
        {
            "squad": squad,
            "papel": papel,
            "recurso": f"{papel} {indice + 1}",
            "disponivel_em": data_inicio,
        }
        for indice in range(quantidade)
    ]


def escolher_recurso(recursos: List[Dict[str, object]]) -> Dict[str, object]:
    return min(recursos, key=lambda item: (item["disponivel_em"], item["squad"], item["recurso"]))


def simular_lakes_exclusivos(
    squad: str,
    lakes: List[str],
    historias_por_lake: Dict[str, List[Dict[str, object]]],
    data_inicio: date,
    engenheiros: int = 8,
    analistas: int = 2,
) -> Tuple[List[Dict[str, object]], List[Dict[str, object]], date]:
    recursos_eng = criar_recursos(squad, "Engenheiro", engenheiros, data_inicio)
    recursos_ana = criar_recursos(squad, "Analista", analistas, data_inicio)
    atribuicoes: List[Dict[str, object]] = []
    resumo_lakes: List[Dict[str, object]] = []
    fim_fase = data_inicio

    for lake in lakes:
        historias = historias_por_lake.get(lake, [])
        inicio_lake = data_inicio
        fim_lake = data_inicio
        historias_alocadas = 0

        for historia in historias:
            fim_historia = data_inicio
            teve_trabalho = False

            duracao_eng = float(historia["engenheiro_dias"])
            if duracao_eng > 0:
                recurso = escolher_recurso(recursos_eng)
                inicio = recurso["disponivel_em"]
                fim = data_fim_trabalho(inicio, duracao_eng)
                recurso["disponivel_em"] = proximo_dia_util(fim)
                fim_historia = max(fim_historia, fim)
                teve_trabalho = True
                atribuicoes.append(
                    {
                        "squad": squad,
                        "lake": lake,
                        "id_historia": historia["id_historia"],
                        "numero": historia["numero"],
                        "titulo": historia["titulo"],
                        "papel": "Engenheiro",
                        "recurso": recurso["recurso"],
                        "duracao_dias_uteis": duracao_eng,
                        "data_inicio": formatar_data_br(inicio),
                        "data_fim": formatar_data_br(fim),
                    }
                )

            duracao_ana = float(historia["analista_dias"])
            if duracao_ana > 0:
                recurso = escolher_recurso(recursos_ana)
                inicio = recurso["disponivel_em"]
                fim = data_fim_trabalho(inicio, duracao_ana)
                recurso["disponivel_em"] = proximo_dia_util(fim)
                fim_historia = max(fim_historia, fim)
                teve_trabalho = True
                atribuicoes.append(
                    {
                        "squad": squad,
                        "lake": lake,
                        "id_historia": historia["id_historia"],
                        "numero": historia["numero"],
                        "titulo": historia["titulo"],
                        "papel": "Analista",
                        "recurso": recurso["recurso"],
                        "duracao_dias_uteis": duracao_ana,
                        "data_inicio": formatar_data_br(inicio),
                        "data_fim": formatar_data_br(fim),
                    }
                )

            if teve_trabalho:
                historias_alocadas += 1
                fim_lake = max(fim_lake, fim_historia)
                fim_fase = max(fim_fase, fim_historia)

        resumo_lakes.append(
            {
                "squad": squad,
                "lake": lake,
                "historias": len(historias),
                "historias_alocadas": historias_alocadas,
                "data_inicio": formatar_data_br(inicio_lake),
                "data_fim": formatar_data_br(fim_lake),
                "prazo_total_dias_corridos": (fim_lake - inicio_lake).days + 1,
            }
        )

    return resumo_lakes, atribuicoes, fim_fase


def simular_lake_compartilhado(
    lake: str,
    historias: List[Dict[str, object]],
    participantes: List[Dict[str, object]],
) -> Tuple[List[Dict[str, object]], List[Dict[str, object]], date]:
    recursos_por_squad: Dict[str, Dict[str, List[Dict[str, object]]]] = {}
    atribuicoes: List[Dict[str, object]] = []
    por_squad = defaultdict(lambda: {"inicio": None, "fim": None, "historias": set()})

    inicio_geral = min(parse_data_br(str(item["data_inicio"])) for item in participantes)
    fim_geral = inicio_geral

    for participante in participantes:
        squad = str(participante["squad"])
        data_inicio = parse_data_br(str(participante["data_inicio"]))
        recursos_por_squad[squad] = {
            "engenheiros": criar_recursos(squad, "Engenheiro", int(participante["engenheiros"]), data_inicio),
            "analistas": criar_recursos(squad, "Analista", int(participante["analistas"]), data_inicio),
        }
        if por_squad[squad]["inicio"] is None:
            por_squad[squad]["inicio"] = data_inicio

    for historia in historias:
        melhor_opcao = None
        duracao_eng = float(historia["engenheiro_dias"])
        duracao_ana = float(historia["analista_dias"])

        for participante in participantes:
            squad = str(participante["squad"])
            recursos_eng = recursos_por_squad[squad]["engenheiros"]
            recursos_ana = recursos_por_squad[squad]["analistas"]

            recurso_eng = escolher_recurso(recursos_eng)
            recurso_ana = escolher_recurso(recursos_ana)

            inicio_eng = recurso_eng["disponivel_em"] if duracao_eng > 0 else por_squad[squad]["inicio"]
            fim_eng = data_fim_trabalho(inicio_eng, duracao_eng) if duracao_eng > 0 else por_squad[squad]["inicio"]
            inicio_ana = recurso_ana["disponivel_em"] if duracao_ana > 0 else por_squad[squad]["inicio"]
            fim_ana = data_fim_trabalho(inicio_ana, duracao_ana) if duracao_ana > 0 else por_squad[squad]["inicio"]
            fim_historia = max(fim_eng, fim_ana)

            candidato = {
                "squad": squad,
                "recurso_eng": recurso_eng,
                "recurso_ana": recurso_ana,
                "inicio_eng": inicio_eng,
                "fim_eng": fim_eng,
                "inicio_ana": inicio_ana,
                "fim_ana": fim_ana,
                "fim_historia": fim_historia,
            }

            if melhor_opcao is None or (candidato["fim_historia"], candidato["squad"]) < (melhor_opcao["fim_historia"], melhor_opcao["squad"]):
                melhor_opcao = candidato

        if melhor_opcao is None:
            continue

        squad = str(melhor_opcao["squad"])
        por_squad[squad]["historias"].add(historia["id_historia"])

        if duracao_eng > 0:
            melhor_opcao["recurso_eng"]["disponivel_em"] = proximo_dia_util(melhor_opcao["fim_eng"])
            atribuicoes.append(
                {
                    "squad": squad,
                    "lake": lake,
                    "id_historia": historia["id_historia"],
                    "numero": historia["numero"],
                    "titulo": historia["titulo"],
                    "papel": "Engenheiro",
                    "recurso": melhor_opcao["recurso_eng"]["recurso"],
                    "duracao_dias_uteis": duracao_eng,
                    "data_inicio": formatar_data_br(melhor_opcao["inicio_eng"]),
                    "data_fim": formatar_data_br(melhor_opcao["fim_eng"]),
                }
            )

        if duracao_ana > 0:
            melhor_opcao["recurso_ana"]["disponivel_em"] = proximo_dia_util(melhor_opcao["fim_ana"])
            atribuicoes.append(
                {
                    "squad": squad,
                    "lake": lake,
                    "id_historia": historia["id_historia"],
                    "numero": historia["numero"],
                    "titulo": historia["titulo"],
                    "papel": "Analista",
                    "recurso": melhor_opcao["recurso_ana"]["recurso"],
                    "duracao_dias_uteis": duracao_ana,
                    "data_inicio": formatar_data_br(melhor_opcao["inicio_ana"]),
                    "data_fim": formatar_data_br(melhor_opcao["fim_ana"]),
                }
            )

        por_squad[squad]["fim"] = melhor_opcao["fim_historia"] if por_squad[squad]["fim"] is None else max(por_squad[squad]["fim"], melhor_opcao["fim_historia"])
        fim_geral = max(fim_geral, melhor_opcao["fim_historia"])

    resumo: List[Dict[str, object]] = []
    for participante in participantes:
        squad = str(participante["squad"])
        inicio = por_squad[squad]["inicio"]
        fim = por_squad[squad]["fim"] or inicio
        resumo.append(
            {
                "squad": squad,
                "lake": f"{lake} (parcial)",
                "historias": len(por_squad[squad]["historias"]),
                "historias_alocadas": len(por_squad[squad]["historias"]),
                "data_inicio": formatar_data_br(inicio),
                "data_fim": formatar_data_br(fim),
                "prazo_total_dias_corridos": (fim - inicio).days + 1,
            }
        )

    resumo.append(
        {
            "squad": "Squad 1 + Squad 5",
            "lake": lake,
            "historias": len(historias),
            "historias_alocadas": len(historias),
            "data_inicio": formatar_data_br(inicio_geral),
            "data_fim": formatar_data_br(fim_geral),
            "prazo_total_dias_corridos": (fim_geral - inicio_geral).days + 1,
        }
    )

    return resumo, atribuicoes, fim_geral


def salvar_csv(caminho: Path, linhas: List[Dict[str, object]], campos: List[str]) -> None:
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        writer = csv.DictWriter(arquivo, fieldnames=campos)
        writer.writeheader()
        writer.writerows(linhas)


def salvar_relatorio(caminho: Path, resumo_squads: List[Dict[str, object]], resumo_lakes: List[Dict[str, object]]) -> None:
    linhas = [
        "# Simulação por Squad com COMERCIAL dividido",
        "",
        "Premissas:",
        "- Squad 1 inicia em 09/03/2026",
        "- Squads 2, 3, 4 e 5 iniciam em 01/04/2026",
        "- Squad 1 faz BMC e COMPRAS; depois divide COMERCIAL com Squad 5",
        "- Squad 2 faz MOPAR e depois RH",
        "- Squad 3 faz CLIENTE e depois FINANCE",
        "- Squad 4 faz SUPPLY CHAIN",
        "- cada squad com 8 engenheiros e 2 analistas",
        "",
        "## Resumo por squad",
        "",
        "| Squad | Início | Fim | Lakes |",
        "|---|---|---|---|",
    ]

    for item in resumo_squads:
        linhas.append(f"| {item['squad']} | {item['data_inicio']} | {item['data_fim']} | {item['lakes']} |")

    linhas.extend([
        "",
        "## Resumo por lake",
        "",
        "| Squad | Lake | Histórias | Início | Fim | Prazo (corridos) |",
        "|---|---|---:|---|---|---:|",
    ])

    for item in resumo_lakes:
        linhas.append(
            f"| {item['squad']} | {item['lake']} | {item['historias']} | {item['data_inicio']} | {item['data_fim']} | {item['prazo_total_dias_corridos']} |"
        )

    caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Simula cenário com COMERCIAL dividido entre Squad 1 e Squad 5.")
    parser.add_argument("--entrada", default="analises/tempos_desenvolvimento_historias.csv")
    parser.add_argument("--saida-squads", default="analises/prazo_squads_dividido_resumo.csv")
    parser.add_argument("--saida-lakes", default="analises/prazo_squads_dividido_lakes.csv")
    parser.add_argument("--saida-detalhe", default="analises/prazo_squads_dividido_alocacoes.csv")
    parser.add_argument("--saida-relatorio", default="analises/prazo_squads_dividido_relatorio.md")
    args = parser.parse_args()

    registros = ler_csv_historias(Path(args.entrada))
    por_lake = agrupar_historias_por_lake(registros)

    resumo_lakes: List[Dict[str, object]] = []
    atribuicoes: List[Dict[str, object]] = []
    resumo_squads: List[Dict[str, object]] = []

    data_s1 = parse_data_br(DATA_INICIO_SQUAD_1)
    data_demais = parse_data_br(DATA_INICIO_DEMAIS)

    resumo_s1_fase1, atrib_s1_fase1, fim_s1_fase1 = simular_lakes_exclusivos("Squad 1", ["BMC", "COMPRAS"], por_lake, data_s1)
    resumo_lakes.extend(resumo_s1_fase1)
    atribuicoes.extend(atrib_s1_fase1)

    inicio_comercial_s1 = proximo_dia_util(fim_s1_fase1)
    resumo_comercial, atrib_comercial, fim_comercial = simular_lake_compartilhado(
        "COMERCIAL",
        por_lake.get("COMERCIAL", []),
        [
            {"squad": "Squad 1", "data_inicio": formatar_data_br(inicio_comercial_s1), "engenheiros": 8, "analistas": 2},
            {"squad": "Squad 5", "data_inicio": formatar_data_br(data_demais), "engenheiros": 8, "analistas": 2},
        ],
    )
    resumo_lakes.extend(resumo_comercial)
    atribuicoes.extend(atrib_comercial)

    resumo_s2, atrib_s2, fim_mopar = simular_lakes_exclusivos("Squad 2", ["MOPAR"], por_lake, data_demais)
    resumo_lakes.extend(resumo_s2)
    atribuicoes.extend(atrib_s2)
    inicio_rh = proximo_dia_util(fim_mopar)
    resumo_s2_rh, atrib_s2_rh, fim_rh = simular_lakes_exclusivos("Squad 2", ["RH"], por_lake, inicio_rh)
    resumo_lakes.extend(resumo_s2_rh)
    atribuicoes.extend(atrib_s2_rh)

    resumo_s3, atrib_s3, fim_cliente = simular_lakes_exclusivos("Squad 3", ["CLIENTE"], por_lake, data_demais)
    resumo_lakes.extend(resumo_s3)
    atribuicoes.extend(atrib_s3)
    inicio_finance = proximo_dia_util(fim_cliente)
    resumo_s3_fin, atrib_s3_fin, fim_finance = simular_lakes_exclusivos("Squad 3", ["FINANCE"], por_lake, inicio_finance)
    resumo_lakes.extend(resumo_s3_fin)
    atribuicoes.extend(atrib_s3_fin)

    resumo_s4, atrib_s4, fim_supply = simular_lakes_exclusivos("Squad 4", ["SUPPLY CHAIN"], por_lake, data_demais)
    resumo_lakes.extend(resumo_s4)
    atribuicoes.extend(atrib_s4)

    fim_squad1 = max(fim_s1_fase1, max(datetime.strptime(item["data_fim"], "%d/%m/%Y").date() for item in resumo_comercial if item["squad"] == "Squad 1"))
    fim_squad5 = max(datetime.strptime(item["data_fim"], "%d/%m/%Y").date() for item in resumo_comercial if item["squad"] == "Squad 5")

    resumo_squads = [
        {"squad": "Squad 1", "data_inicio": formatar_data_br(data_s1), "data_fim": formatar_data_br(fim_squad1), "lakes": "BMC -> COMPRAS -> COMERCIAL (dividido)"},
        {"squad": "Squad 2", "data_inicio": formatar_data_br(data_demais), "data_fim": formatar_data_br(fim_rh), "lakes": "MOPAR -> RH"},
        {"squad": "Squad 3", "data_inicio": formatar_data_br(data_demais), "data_fim": formatar_data_br(fim_finance), "lakes": "CLIENTE -> FINANCE"},
        {"squad": "Squad 4", "data_inicio": formatar_data_br(data_demais), "data_fim": formatar_data_br(fim_supply), "lakes": "SUPPLY CHAIN"},
        {"squad": "Squad 5", "data_inicio": formatar_data_br(data_demais), "data_fim": formatar_data_br(fim_squad5), "lakes": "COMERCIAL (dividido)"},
    ]

    resumo_lakes.sort(key=lambda item: (item["squad"], item["lake"], item["data_inicio"]))
    atribuicoes.sort(key=lambda item: (item["squad"], item["lake"], item["papel"], item["data_inicio"], item["recurso"]))

    salvar_csv(Path(args.saida_squads), resumo_squads, ["squad", "data_inicio", "data_fim", "lakes"])
    salvar_csv(Path(args.saida_lakes), resumo_lakes, ["squad", "lake", "historias", "historias_alocadas", "data_inicio", "data_fim", "prazo_total_dias_corridos"])
    salvar_csv(Path(args.saida_detalhe), atribuicoes, ["squad", "lake", "id_historia", "numero", "titulo", "papel", "recurso", "duracao_dias_uteis", "data_inicio", "data_fim"])
    salvar_relatorio(Path(args.saida_relatorio), resumo_squads, resumo_lakes)

    print(f"Resumo por squad: {args.saida_squads}")
    print(f"Resumo por lake: {args.saida_lakes}")
    print(f"Detalhe: {args.saida_detalhe}")
    print(f"Relatório: {args.saida_relatorio}")


if __name__ == "__main__":
    main()
