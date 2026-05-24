import csv
from collections import defaultdict
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Dict, List, Tuple


ARQUIVO_TEMPOS = Path("analises/tempos_desenvolvimento_historias.csv")
ARQUIVO_COMERCIAL_DIVIDIDO = Path("analises/prazo_squads_dividido_alocacoes.csv")


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
    dias_ocupados = int(round(duracao_dias_uteis))
    dias_ocupados = max(1, dias_ocupados)
    return adicionar_dias_uteis(data_inicio, dias_ocupados - 1)


def ler_historias() -> Dict[str, List[Dict[str, object]]]:
    por_lake: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    with ARQUIVO_TEMPOS.open("r", encoding="utf-8", newline="") as arquivo:
        reader = csv.DictReader(arquivo)
        for linha in reader:
            registro = {
                "id_historia": linha["id_historia"],
                "lake": linha["lake"],
                "numero": int(linha["numero"]),
                "titulo": linha["titulo"],
                "engenheiro_dias": float(linha["engenheiro_dias"] or 0),
                "analista_dias": float(linha["analista_dias"] or 0),
            }
            por_lake[str(linha["lake"])].append(registro)

    for historias in por_lake.values():
        historias.sort(key=lambda item: int(item["numero"]))
    return dict(por_lake)


def ler_comercial_dividido() -> Tuple[date, date]:
    fim_squad1 = None
    fim_squad5 = None
    with ARQUIVO_COMERCIAL_DIVIDIDO.open("r", encoding="utf-8", newline="") as arquivo:
        reader = csv.DictReader(arquivo)
        for linha in reader:
            if linha["lake"] != "COMERCIAL":
                continue
            # ignore consolidated row in detail file; this file has no consolidated row
        
    # derive from summary file instead
    resumo = Path("analises/prazo_squads_dividido_resumo.csv")
    with resumo.open("r", encoding="utf-8", newline="") as arquivo:
        reader = csv.DictReader(arquivo)
        for linha in reader:
            if linha["squad"] == "Squad 1":
                fim_squad1 = parse_data_br(linha["data_fim"])
            elif linha["squad"] == "Squad 5":
                fim_squad5 = parse_data_br(linha["data_fim"])
    if fim_squad1 is None or fim_squad5 is None:
        raise RuntimeError("Não foi possível ler datas de fim das squads 1 e 5.")
    return fim_squad1, fim_squad5


def criar_recursos(squad: str, papel: str, quantidade: int, data_inicio: date) -> List[Dict[str, object]]:
    return [
        {"squad": squad, "papel": papel, "recurso": f"{papel} {i+1}", "disponivel_em": data_inicio}
        for i in range(quantidade)
    ]


def escolher_recurso(recursos: List[Dict[str, object]]) -> Dict[str, object]:
    return min(recursos, key=lambda item: (item["disponivel_em"], item["squad"], item["recurso"]))


def simular_lake_compartilhado(lake: str, historias: List[Dict[str, object]], participantes: List[Dict[str, object]]) -> Dict[str, object]:
    recursos_por_squad: Dict[str, Dict[str, List[Dict[str, object]]]] = {}
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
        por_squad[squad]["inicio"] = data_inicio

    for historia in historias:
        duracao_eng = float(historia["engenheiro_dias"])
        duracao_ana = float(historia["analista_dias"])
        melhor = None

        for participante in participantes:
            squad = str(participante["squad"])
            recurso_eng = escolher_recurso(recursos_por_squad[squad]["engenheiros"])
            recurso_ana = escolher_recurso(recursos_por_squad[squad]["analistas"])

            inicio_eng = recurso_eng["disponivel_em"] if duracao_eng > 0 else por_squad[squad]["inicio"]
            fim_eng = data_fim_trabalho(inicio_eng, duracao_eng) if duracao_eng > 0 else por_squad[squad]["inicio"]
            inicio_ana = recurso_ana["disponivel_em"] if duracao_ana > 0 else por_squad[squad]["inicio"]
            fim_ana = data_fim_trabalho(inicio_ana, duracao_ana) if duracao_ana > 0 else por_squad[squad]["inicio"]
            fim_historia = max(fim_eng, fim_ana)
            candidato = {
                "squad": squad,
                "recurso_eng": recurso_eng,
                "recurso_ana": recurso_ana,
                "fim_eng": fim_eng,
                "fim_ana": fim_ana,
                "fim_historia": fim_historia,
            }
            if melhor is None or (candidato["fim_historia"], candidato["squad"]) < (melhor["fim_historia"], melhor["squad"]):
                melhor = candidato

        squad = str(melhor["squad"])
        por_squad[squad]["historias"].add(historia["id_historia"])
        if duracao_eng > 0:
            melhor["recurso_eng"]["disponivel_em"] = proximo_dia_util(melhor["fim_eng"])
        if duracao_ana > 0:
            melhor["recurso_ana"]["disponivel_em"] = proximo_dia_util(melhor["fim_ana"])
        por_squad[squad]["fim"] = melhor["fim_historia"] if por_squad[squad]["fim"] is None else max(por_squad[squad]["fim"], melhor["fim_historia"])
        fim_geral = max(fim_geral, melhor["fim_historia"])

    retorno = {
        "lake": lake,
        "fim_global": fim_geral,
        "squads": {},
    }
    for participante in participantes:
        squad = str(participante["squad"])
        inicio = por_squad[squad]["inicio"]
        fim = por_squad[squad]["fim"] or inicio
        retorno["squads"][squad] = {
            "inicio": inicio,
            "fim": fim,
            "historias": len(por_squad[squad]["historias"]),
        }
    return retorno


def main() -> None:
    historias = ler_historias()
    fim_squad1, fim_squad5 = ler_comercial_dividido()

    inicio_nova_frente_squad5 = proximo_dia_util(fim_squad5)

    cenarios = []

    rh = simular_lake_compartilhado(
        "RH",
        historias["RH"],
        [
            {"squad": "Squad 2", "data_inicio": "27/05/2026", "engenheiros": 8, "analistas": 2},
            {"squad": "Squad 5", "data_inicio": formatar_data_br(inicio_nova_frente_squad5), "engenheiros": 8, "analistas": 2},
        ],
    )
    fim_projeto_rh = max(parse_data_br("11/08/2026"), parse_data_br("31/07/2026"), rh["fim_global"], fim_squad1)
    cenarios.append(
        {
            "cenario": "Squad 5 ajuda RH",
            "fim_projeto": formatar_data_br(fim_projeto_rh),
            "fim_lake_otimizado": formatar_data_br(rh["fim_global"]),
            "squad_ajudada": "Squad 2",
            "historias_squad_original": rh["squads"]["Squad 2"]["historias"],
            "historias_squad5": rh["squads"]["Squad 5"]["historias"],
        }
    )

    supply = simular_lake_compartilhado(
        "SUPPLY CHAIN",
        historias["SUPPLY CHAIN"],
        [
            {"squad": "Squad 4", "data_inicio": "01/04/2026", "engenheiros": 8, "analistas": 2},
            {"squad": "Squad 5", "data_inicio": formatar_data_br(inicio_nova_frente_squad5), "engenheiros": 8, "analistas": 2},
        ],
    )
    fim_projeto_supply = max(parse_data_br("28/08/2026"), parse_data_br("31/07/2026"), supply["fim_global"], fim_squad1)
    cenarios.append(
        {
            "cenario": "Squad 5 ajuda SUPPLY CHAIN",
            "fim_projeto": formatar_data_br(fim_projeto_supply),
            "fim_lake_otimizado": formatar_data_br(supply["fim_global"]),
            "squad_ajudada": "Squad 4",
            "historias_squad_original": supply["squads"]["Squad 4"]["historias"],
            "historias_squad5": supply["squads"]["Squad 5"]["historias"],
        }
    )

    saida = Path("analises/comparacao_otimizacoes_squad5.csv")
    with saida.open("w", encoding="utf-8", newline="") as arquivo:
        writer = csv.DictWriter(
            arquivo,
            fieldnames=[
                "cenario",
                "fim_lake_otimizado",
                "fim_projeto",
                "squad_ajudada",
                "historias_squad_original",
                "historias_squad5",
            ],
        )
        writer.writeheader()
        writer.writerows(cenarios)

    print(f"Comparação gerada em: {saida}")
    for cenario in cenarios:
        print(f"- {cenario['cenario']}: lake até {cenario['fim_lake_otimizado']} | projeto até {cenario['fim_projeto']}")


if __name__ == "__main__":
    main()
