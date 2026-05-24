import argparse
import json
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from itertools import permutations, product
from pathlib import Path
from typing import Dict, List

import pandas as pd


DATA_INICIO_ANTECIPADA = "09/03/2026"
DATA_INICIO_PADRAO = "01/04/2026"

LAKES_ORDEM = [
    "BMC",
    "COMPRAS",
    "MOPAR",
    "CLIENTE",
    "SHARED SERVICES",
    "FINANCE",
    "RH",
    "COMERCIAL",
    "SUPPLY CHAIN",
]


@dataclass
class Story:
    id_historia: str
    lake: str
    numero: int
    titulo: str
    engenheiro_dias: float
    analista_dias: float


def parse_data_br(valor: str) -> date:
    return datetime.strptime(valor, "%d/%m/%Y").date()


FERIADOS = {
    date(2026,  4,  3),  # Paixão de Cristo
    date(2026,  4, 21),  # Tiradentes
    date(2026,  5,  1),  # Dia do Trabalho
    date(2026,  6,  4),  # Corpus Christi (ponto facultativo)
    date(2026,  9,  7),  # Independência do Brasil
    date(2026, 10, 12),  # Nossa Senhora Aparecida
    date(2026, 11,  2),  # Finados
    date(2026, 11, 15),  # Proclamação da República
    date(2026, 11, 20),  # Consciência Negra
}


def is_dia_util(d: date) -> bool:
    return d.weekday() < 5 and d not in FERIADOS


def adicionar_dias_uteis(inicio: date, dias: int) -> date:
    atual = inicio
    restantes = dias
    while restantes > 0:
        atual += timedelta(days=1)
        if is_dia_util(atual):
            restantes -= 1
    return atual


def fim_trabalho(inicio: date, duracao_dias_uteis: float) -> date:
    if duracao_dias_uteis <= 0:
        return inicio
    dias_ocupados = max(1, int(math.ceil(duracao_dias_uteis - 1e-9)))
    return adicionar_dias_uteis(inicio, dias_ocupados - 1)


def proximo_dia_util(valor: date) -> date:
    atual = valor + timedelta(days=1)
    while not is_dia_util(atual):
        atual += timedelta(days=1)
    return atual


def carregar_historias(caminho_csv: Path) -> List[Story]:
    df = pd.read_csv(caminho_csv)
    historias: List[Story] = []
    for _, row in df.iterrows():
        historias.append(
            Story(
                id_historia=str(row["id_historia"]),
                lake=str(row["lake"]).strip().upper(),
                numero=int(row["numero"]),
                titulo=str(row["titulo"]),
                engenheiro_dias=float(row["engenheiro_dias"] or 0),
                analista_dias=float(row["analista_dias"] or 0),
            )
        )
    return historias


def obter_inicio_por_lake(lake: str) -> date:
    if lake in {"BMC", "COMPRAS"}:
        return parse_data_br(DATA_INICIO_ANTECIPADA)
    return parse_data_br(DATA_INICIO_PADRAO)


def ordenar_historias(historias: List[Story]) -> List[Story]:
    ordem_map = {nome: idx for idx, nome in enumerate(LAKES_ORDEM)}
    # Lakes virtuais de SHARED SERVICES herdam a posição do lake original
    pos_shared = ordem_map.get("SHARED SERVICES", 999)
    ordem_map["SHARED SERVICES A"] = pos_shared
    ordem_map["SHARED SERVICES B"] = pos_shared
    return sorted(
        historias,
        key=lambda h: (
            obter_inicio_por_lake(h.lake),
            ordem_map.get(h.lake, 999),
            h.numero,
        ),
    )


def escolher_recurso_disponivel(recursos: List[date]) -> int:
    melhor_idx = 0
    melhor_data = recursos[0]
    for i in range(1, len(recursos)):
        if recursos[i] < melhor_data:
            melhor_idx = i
            melhor_data = recursos[i]
    return melhor_idx


def simular_cenario_papeis(
    historias: List[Story],
    lake_para_squads: Dict[str, List[str]],
    engenheiros_por_squad: int,
    analistas_por_squad: int,
) -> Dict[str, object]:
    squads = sorted({sq for lista in lake_para_squads.values() for sq in lista})
    if not squads:
        raise ValueError("Cenário sem squads configuradas")

    recursos_eng = {sq: [parse_data_br(DATA_INICIO_ANTECIPADA)] * engenheiros_por_squad for sq in squads}
    recursos_ana = {sq: [parse_data_br(DATA_INICIO_ANTECIPADA)] * analistas_por_squad for sq in squads}

    alocacoes = []
    fim_projeto = parse_data_br(DATA_INICIO_ANTECIPADA)

    for historia in ordenar_historias(historias):
        candidatos = lake_para_squads.get(historia.lake)
        if not candidatos:
            continue

        inicio_lake = obter_inicio_por_lake(historia.lake)
        melhor = None

        for squad in candidatos:
            idx_eng = None
            idx_ana = None
            ini_eng = inicio_lake
            ini_ana = inicio_lake
            fim_eng = inicio_lake
            fim_ana = inicio_lake

            if historia.engenheiro_dias > 0:
                idx_eng = escolher_recurso_disponivel(recursos_eng[squad])
                ini_eng = max(recursos_eng[squad][idx_eng], inicio_lake)
                fim_eng = fim_trabalho(ini_eng, historia.engenheiro_dias)

            if historia.analista_dias > 0:
                idx_ana = escolher_recurso_disponivel(recursos_ana[squad])
                ini_ana = max(recursos_ana[squad][idx_ana], inicio_lake)
                fim_ana = fim_trabalho(ini_ana, historia.analista_dias)

            fim_hist = max(fim_eng, fim_ana)
            candidato = {
                "squad": squad,
                "idx_eng": idx_eng,
                "idx_ana": idx_ana,
                "ini_eng": ini_eng,
                "fim_eng": fim_eng,
                "ini_ana": ini_ana,
                "fim_ana": fim_ana,
                "fim_hist": fim_hist,
            }
            if melhor is None or (candidato["fim_hist"], candidato["squad"]) < (melhor["fim_hist"], melhor["squad"]):
                melhor = candidato

        if melhor is None:
            continue

        squad = melhor["squad"]
        if historia.engenheiro_dias > 0 and melhor["idx_eng"] is not None:
            recursos_eng[squad][melhor["idx_eng"]] = proximo_dia_util(melhor["fim_eng"])
            alocacoes.append(
                {
                    "squad": squad,
                    "lake": historia.lake,
                    "id_historia": historia.id_historia,
                    "numero": historia.numero,
                    "titulo": historia.titulo,
                    "papel": "Engenheiro",
                    "recurso": f"Engenheiro {melhor['idx_eng'] + 1}",
                    "duracao_dias_uteis": historia.engenheiro_dias,
                    "data_inicio": melhor["ini_eng"].strftime("%d/%m/%Y"),
                    "data_fim": melhor["fim_eng"].strftime("%d/%m/%Y"),
                }
            )

        if historia.analista_dias > 0 and melhor["idx_ana"] is not None:
            recursos_ana[squad][melhor["idx_ana"]] = proximo_dia_util(melhor["fim_ana"])
            alocacoes.append(
                {
                    "squad": squad,
                    "lake": historia.lake,
                    "id_historia": historia.id_historia,
                    "numero": historia.numero,
                    "titulo": historia.titulo,
                    "papel": "Analista",
                    "recurso": f"Analista {melhor['idx_ana'] + 1}",
                    "duracao_dias_uteis": historia.analista_dias,
                    "data_inicio": melhor["ini_ana"].strftime("%d/%m/%Y"),
                    "data_fim": melhor["fim_ana"].strftime("%d/%m/%Y"),
                }
            )

        fim_projeto = max(fim_projeto, melhor["fim_hist"])

    return {
        "fim_projeto": fim_projeto,
        "prazo_corridos": (fim_projeto - parse_data_br(DATA_INICIO_ANTECIPADA)).days + 1,
        "alocacoes": alocacoes,
    }


def simular_cenario_somente_devs(
    historias: List[Story],
    lake_para_squads: Dict[str, List[str]],
    devs_por_squad: int,
) -> Dict[str, object]:
    squads = sorted({sq for lista in lake_para_squads.values() for sq in lista})
    recursos_devs = {sq: [parse_data_br(DATA_INICIO_ANTECIPADA)] * devs_por_squad for sq in squads}

    alocacoes = []
    fim_projeto = parse_data_br(DATA_INICIO_ANTECIPADA)

    for historia in ordenar_historias(historias):
        candidatos = lake_para_squads.get(historia.lake)
        if not candidatos:
            continue

        inicio_lake = obter_inicio_por_lake(historia.lake)
        duracao_total = float(historia.engenheiro_dias) + float(historia.analista_dias)
        melhor = None

        for squad in candidatos:
            idx = escolher_recurso_disponivel(recursos_devs[squad])
            inicio = max(recursos_devs[squad][idx], inicio_lake)
            fim = fim_trabalho(inicio, duracao_total)
            candidato = {"squad": squad, "idx": idx, "inicio": inicio, "fim": fim}
            if melhor is None or (candidato["fim"], candidato["squad"]) < (melhor["fim"], melhor["squad"]):
                melhor = candidato

        if melhor is None:
            continue

        squad = melhor["squad"]
        recursos_devs[squad][melhor["idx"]] = proximo_dia_util(melhor["fim"])
        alocacoes.append(
            {
                "squad": squad,
                "lake": historia.lake,
                "id_historia": historia.id_historia,
                "numero": historia.numero,
                "titulo": historia.titulo,
                "papel": "Dev Fullstack",
                "recurso": f"Dev {melhor['idx'] + 1}",
                "duracao_dias_uteis": duracao_total,
                "data_inicio": melhor["inicio"].strftime("%d/%m/%Y"),
                "data_fim": melhor["fim"].strftime("%d/%m/%Y"),
            }
        )
        fim_projeto = max(fim_projeto, melhor["fim"])

    return {
        "fim_projeto": fim_projeto,
        "prazo_corridos": (fim_projeto - parse_data_br(DATA_INICIO_ANTECIPADA)).days + 1,
        "alocacoes": alocacoes,
    }


def simular_cenario_somente_devs_flex(
    historias: List[Story],
    lake_para_squads: Dict[str, List[str]],
    devs_por_squad: Dict[str, int],
    inicio_por_squad: Dict[str, date] = None,
) -> Dict[str, object]:
    """Versão flexível: permite número de devs e data de início diferente por squad."""
    squads = sorted({sq for lista in lake_para_squads.values() for sq in lista})
    data_inicio_global = parse_data_br(DATA_INICIO_ANTECIPADA)

    recursos_devs = {}
    for sq in squads:
        n = devs_por_squad.get(sq, 10)
        inicio_sq = (inicio_por_squad or {}).get(sq, data_inicio_global)
        recursos_devs[sq] = [inicio_sq] * n

    alocacoes = []
    fim_projeto = data_inicio_global

    for historia in ordenar_historias(historias):
        candidatos = lake_para_squads.get(historia.lake)
        if not candidatos:
            continue

        inicio_lake = obter_inicio_por_lake(historia.lake)
        # Para Squad 6 em COMERCIAL, respeita também o inicio da squad
        duracao_total = float(historia.engenheiro_dias) + float(historia.analista_dias)
        melhor = None

        for squad in candidatos:
            inicio_squad = (inicio_por_squad or {}).get(squad, data_inicio_global)
            idx = escolher_recurso_disponivel(recursos_devs[squad])
            inicio = max(recursos_devs[squad][idx], inicio_lake, inicio_squad)
            fim = fim_trabalho(inicio, duracao_total)
            candidato = {"squad": squad, "idx": idx, "inicio": inicio, "fim": fim}
            if melhor is None or (candidato["fim"], candidato["squad"]) < (melhor["fim"], melhor["squad"]):
                melhor = candidato

        if melhor is None:
            continue

        squad = melhor["squad"]
        recursos_devs[squad][melhor["idx"]] = proximo_dia_util(melhor["fim"])
        alocacoes.append(
            {
                "squad": squad,
                "lake": historia.lake,
                "id_historia": historia.id_historia,
                "numero": historia.numero,
                "titulo": historia.titulo,
                "papel": "Dev Fullstack",
                "recurso": f"Dev {melhor['idx'] + 1}",
                "duracao_dias_uteis": duracao_total,
                "data_inicio": melhor["inicio"].strftime("%d/%m/%Y"),
                "data_fim": melhor["fim"].strftime("%d/%m/%Y"),
            }
        )
        fim_projeto = max(fim_projeto, melhor["fim"])

    return {
        "fim_projeto": fim_projeto,
        "prazo_corridos": (fim_projeto - data_inicio_global).days + 1,
        "alocacoes": alocacoes,
    }


def simular_cenario_devs_por_lake(
    historias: List[Story],
    lake_para_squads: Dict[str, List[str]],
    devs_dedicados_por_lake: Dict[str, Dict[str, int]],
    inicio_global: date,
    inicio_por_squad: Dict[str, date] = None,
    tamanho_total_squad: Dict[str, int] = None,
    inicio_reforco: date = None,
    inicio_minimo_por_lake: Dict[str, date] = None,
) -> Dict[str, object]:
    """
    Simula cenário com squads dedicadas e reforço cross-squad.

    Regras:
    - Cada squad tem um lake primário (onde todos os seus devs trabalham desde inicio_global).
    - devs_dedicados_por_lake define quantos devs de squads de REFORÇO participam
      de cada lake desde inicio_global. A squad primária usa todos os seus devs.
    - Os devs de reforço ficam disponíveis a partir de inicio_reforco (ex: 01/04).
    - Quando a squad primária termina seu lake, os devs ficam disponíveis para
      outros lakes onde a squad aparece como reforço.

    devs_dedicados_por_lake: {lake: {squad_reforco: n_devs_desde_inicio_global}}
      Para a squad primária do lake, este valor é ignorado (usa tamanho_total_squad).

    tamanho_total_squad: {squad: n_devs_total}
    inicio_reforco: data de disponibilidade dos devs de reforço.
    """
    squads = sorted({sq for lista in lake_para_squads.values() for sq in lista})
    data_ref = inicio_global
    data_reforco = inicio_reforco if inicio_reforco else inicio_global

    # Total de devs por squad
    total_devs: Dict[str, int] = {}
    for sq in squads:
        if tamanho_total_squad and sq in tamanho_total_squad:
            total_devs[sq] = tamanho_total_squad[sq]
        else:
            total_devs[sq] = max(
                (lake_devs.get(sq, 0) for lake_devs in devs_dedicados_por_lake.values()),
                default=1,
            )

    # Identifica TODOS os lakes primários de cada squad (todos os lakes onde ela é a squad principal)
    # Um squad é "primária" de um lake se aparece como index 0 nesse lake
    lakes_primarios_de_squad: Dict[str, set] = {}
    for lake, squads_list in lake_para_squads.items():
        if squads_list:
            sq_principal = squads_list[0]
            if sq_principal not in lakes_primarios_de_squad:
                lakes_primarios_de_squad[sq_principal] = set()
            lakes_primarios_de_squad[sq_principal].add(lake)

    # Monta os slots de disponibilidade dos devs de cada squad.
    # Slots 0..n_dedicados-1: devs que começam em inicio_global (23/03)
    #   - Para cada lake na tabela, atribui slots dedicados sequencialmente
    # Slots n_dedicados..n_total-1: devs que começam em data_reforco (01/04)
    #   - Primeiro ficam disponíveis para o lake PRIMÁRIO da squad (auto-reforço)
    #   - Depois para lakes externos (COMERCIAL, RH etc.) — tratado pelo mapa
    recursos_devs: Dict[str, List[date]] = {}
    slots_por_lake_dedicado: Dict[str, Dict[str, List[int]]] = {}
    # slots_reforco_primario[squad] = slots de reforço do lake primário (chegam em 01/04)
    # slots_reforco_externo[squad]  = slots para reforço de outros lakes (chegam em 01/04)
    # Como os slots são compartilhados (um dev pode ir para qualquer lake após estar livre),
    # usamos a mesma lista mas separamos quais lakes podem usá-los inicialmente.
    slots_reforco_primario: Dict[str, List[int]] = {}
    slots_reforco_externo: Dict[str, List[int]] = {}

    for sq in squads:
        inicio_sq = (inicio_por_squad or {}).get(sq, data_ref)
        n_total = total_devs[sq]
        slots_por_lake_dedicado[sq] = {}
        meus_lakes_primarios = lakes_primarios_de_squad.get(sq, set())

        # Para lakes primários da squad: todos os devs estão disponíveis desde inicio_global.
        # O número de devs "dedicados" (que começam em 23/03) é dado pela tabela;
        # os restantes chegam em data_reforco (01/04).
        # Para lakes de reforço externo: slots chegam em data_reforco.
        n_dedicados_primarios = sum(
            devs_dedicados_por_lake.get(lake, {}).get(sq, 0)
            for lake in meus_lakes_primarios
        )
        # Slots 0..n_ded-1 começam em 23/03; slots n_ded..n_total-1 começam em 01/04
        # Todos ficam no(s) lake(s) primário(s) da squad até terminarem.
        # Reforço externo usa apenas os slots que chegam em 01/04 (não roubar dedicados).
        n_dedicados = min(n_dedicados_primarios, n_total)
        reforco_slots = list(range(n_dedicados, n_total))
        slots_reforco_primario[sq] = reforco_slots
        slots_reforco_externo[sq]  = reforco_slots

        slots = [inicio_sq] * n_dedicados + [data_reforco] * (n_total - n_dedicados)
        recursos_devs[sq] = slots

    alocacoes = []
    fim_projeto = data_ref
    # Rastreia o fim do último trabalho de cada squad em cada lake primário
    # para garantir que reforço externo só começa após o squad terminar seus lakes primários.
    fim_lake_primario_por_squad: Dict[str, date] = {sq: data_ref for sq in squads}

    for historia in ordenar_historias(historias):
        candidatos = lake_para_squads.get(historia.lake)
        if not candidatos:
            continue

        duracao_total = float(historia.engenheiro_dias) + float(historia.analista_dias)
        melhor = None

        for squad in candidatos:
            # Determina quais índices esta squad pode usar para este lake:
            # - Lake primário da squad (pode ser mais de um): usa TODOS os slots
            #   Os slots dedicados (23/03) chegam primeiro; os de reforço (01/04) depois.
            # - Reforço externo (outros lakes): usa apenas os slots de reforço externo (01/04),
            #   e somente após o squad ter terminado todos os seus lakes primários.
            meus_lakes_primarios = lakes_primarios_de_squad.get(squad, set())
            if historia.lake in meus_lakes_primarios:
                # Lake primário: todos os devs da squad trabalham aqui
                indices_disponiveis = list(range(total_devs[squad]))
            else:
                # Reforço externo: todos os slots disponíveis, mas só após terminar os lakes primários
                # (o inicio_minimo abaixo garante que não começam antes do fim dos lakes primários)
                indices_disponiveis = list(range(total_devs[squad]))

            if not indices_disponiveis:
                continue

            inicio_squad = (inicio_por_squad or {}).get(squad, data_ref)
            inicio_minimo = max(inicio_squad, inicio_global)
            # Aplica início mínimo por lake (ex: COMPRAS não pode começar antes de 23/03)
            if inicio_minimo_por_lake and historia.lake in inicio_minimo_por_lake:
                inicio_minimo = max(inicio_minimo, inicio_minimo_por_lake[historia.lake])
            # Para reforço externo, o dev não pode começar antes de o squad terminar seus lakes primários
            if historia.lake not in meus_lakes_primarios:
                inicio_minimo = max(inicio_minimo, fim_lake_primario_por_squad.get(squad, data_ref))

            idx = min(indices_disponiveis, key=lambda i: recursos_devs[squad][i])
            inicio = max(recursos_devs[squad][idx], inicio_minimo)
            fim = fim_trabalho(inicio, duracao_total)
            candidato = {"squad": squad, "idx": idx, "inicio": inicio, "fim": fim}
            if melhor is None or (candidato["fim"], candidato["squad"]) < (melhor["fim"], melhor["squad"]):
                melhor = candidato

        if melhor is None:
            continue

        squad = melhor["squad"]
        recursos_devs[squad][melhor["idx"]] = proximo_dia_util(melhor["fim"])
        # Atualiza o fim do lake primário para bloquear reforço externo prematuro
        if historia.lake in lakes_primarios_de_squad.get(squad, set()):
            fim_lake_primario_por_squad[squad] = max(fim_lake_primario_por_squad[squad], melhor["fim"])
        alocacoes.append(
            {
                "squad": squad,
                "lake": historia.lake,
                "id_historia": historia.id_historia,
                "numero": historia.numero,
                "titulo": historia.titulo,
                "papel": "Dev Fullstack",
                "recurso": f"Dev {melhor['idx'] + 1}",
                "duracao_dias_uteis": duracao_total,
                "data_inicio": melhor["inicio"].strftime("%d/%m/%Y"),
                "data_fim": melhor["fim"].strftime("%d/%m/%Y"),
            }
        )
        fim_projeto = max(fim_projeto, melhor["fim"])

    return {
        "fim_projeto": fim_projeto,
        "prazo_corridos": (fim_projeto - data_ref).days + 1,
        "alocacoes": alocacoes,
    }


def montar_cenario_base_5() -> Dict[str, List[str]]:
    return {
        "BMC": ["Squad 1"],
        "COMPRAS": ["Squad 1"],
        "MOPAR": ["Squad 2"],
        "CLIENTE": ["Squad 3"],
        "SHARED SERVICES": ["Squad 1", "Squad 4"],
        "RH": ["Squad 2"],
        "FINANCE": ["Squad 3"],
        "SUPPLY CHAIN": ["Squad 5"],
        "COMERCIAL": ["Squad 1", "Squad 4"],
    }


def montar_cenario_devs_6_squads() -> Dict[str, List[str]]:
    """Base 5 squads + Squad 6 reforçando COMERCIAL (gargalo real identificado)."""
    return {
        "BMC": ["Squad 1"],
        "COMPRAS": ["Squad 1"],
        "MOPAR": ["Squad 2"],
        "CLIENTE": ["Squad 3"],
        "SHARED SERVICES": ["Squad 1", "Squad 4"],
        "RH": ["Squad 2"],
        "FINANCE": ["Squad 3"],
        "SUPPLY CHAIN": ["Squad 5"],
        "COMERCIAL": ["Squad 1", "Squad 4", "Squad 6"],
    }


def montar_cenario_devs_7_squads() -> Dict[str, List[str]]:
    """Base 5 squads + Squad 6 e Squad 7 reforçando os lakes mais pesados."""
    return {
        "BMC": ["Squad 1"],
        "COMPRAS": ["Squad 1"],
        "MOPAR": ["Squad 2"],
        "CLIENTE": ["Squad 3"],
        "SHARED SERVICES": ["Squad 1", "Squad 4"],
        "RH": ["Squad 2", "Squad 7"],
        "FINANCE": ["Squad 3", "Squad 7"],
        "SUPPLY CHAIN": ["Squad 5", "Squad 6"],
        "COMERCIAL": ["Squad 1", "Squad 4", "Squad 6"],
    }


def montar_cenario_8_referencia() -> Dict[str, List[str]]:
    return {
        "BMC": ["Squad 1"],
        "COMPRAS": ["Squad 1"],
        "MOPAR": ["Squad 2"],
        "CLIENTE": ["Squad 3"],
        "SHARED SERVICES": ["Squad 1", "Squad 4"],
        "RH": ["Squad 5"],
        "FINANCE": ["Squad 6"],
        "SUPPLY CHAIN": ["Squad 7"],
        "COMERCIAL": ["Squad 1", "Squad 8"],
    }


def calcular_melhor_5_squads(historias: List[Story]) -> List[Dict[str, object]]:
    resultados = []
    base_fixa = {
        "BMC": ["Squad 1"],
        "COMPRAS": ["Squad 1"],
        "MOPAR": ["Squad 2"],
        "CLIENTE": ["Squad 3"],
        "SHARED SERVICES": ["Squad 1", "Squad 4"],
    }

    squads = [f"Squad {i}" for i in range(1, 6)]
    squads_helper_comercial = [f"Squad {i}" for i in range(2, 6)]

    for squad_rh, squad_fin, squad_sc, squad_comercial in product(squads, squads, squads, squads_helper_comercial):
        cenario = dict(base_fixa)
        cenario.update(
            {
                "RH": [squad_rh],
                "FINANCE": [squad_fin],
                "SUPPLY CHAIN": [squad_sc],
                "COMERCIAL": ["Squad 1", squad_comercial],
            }
        )
        sim = simular_cenario_papeis(historias, cenario, engenheiros_por_squad=8, analistas_por_squad=2)
        resultados.append(
            {
                "tipo": "melhor_5_squads",
                "fim_projeto": sim["fim_projeto"],
                "prazo_dias_corridos": sim["prazo_corridos"],
                "RH": squad_rh,
                "FINANCE": squad_fin,
                "SUPPLY_CHAIN": squad_sc,
                "COMERCIAL_2": squad_comercial,
                "config": cenario,
            }
        )

    resultados.sort(key=lambda x: (x["fim_projeto"], x["prazo_dias_corridos"]))
    return resultados


def calcular_melhor_8_squads(historias: List[Story]) -> List[Dict[str, object]]:
    resultados = []
    base_fixa = {
        "BMC": ["Squad 1"],
        "COMPRAS": ["Squad 1"],
        "MOPAR": ["Squad 2"],
        "CLIENTE": ["Squad 3"],
        "SHARED SERVICES": ["Squad 1", "Squad 4"],
    }

    squads_variaveis = ["Squad 5", "Squad 6", "Squad 7", "Squad 8"]

    for squad_rh, squad_fin, squad_sc, squad_comercial in permutations(squads_variaveis, 4):
        cenario = dict(base_fixa)
        cenario.update(
            {
                "RH": [squad_rh],
                "FINANCE": [squad_fin],
                "SUPPLY CHAIN": [squad_sc],
                "COMERCIAL": ["Squad 1", squad_comercial],
            }
        )
        sim = simular_cenario_papeis(historias, cenario, engenheiros_por_squad=8, analistas_por_squad=2)
        resultados.append(
            {
                "tipo": "melhor_8_squads",
                "fim_projeto": sim["fim_projeto"],
                "prazo_dias_corridos": sim["prazo_corridos"],
                "RH": squad_rh,
                "FINANCE": squad_fin,
                "SUPPLY_CHAIN": squad_sc,
                "COMERCIAL_2": squad_comercial,
                "config": cenario,
            }
        )

    resultados.sort(key=lambda x: (x["fim_projeto"], x["prazo_dias_corridos"]))
    return resultados


def normalizar_config_para_lakes_existentes(config: Dict[str, List[str]], lakes_existentes: set[str]) -> Dict[str, List[str]]:
    return {lake: squads for lake, squads in config.items() if lake in lakes_existentes}


def salvar_alocacoes(caminho: Path, alocacoes: List[Dict[str, object]]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(alocacoes).to_csv(caminho, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Calcula cenários (base, 8 squads, melhores combinações e só devs).")
    parser.add_argument(
        "--entrada",
        default="analises/00_fontes/tempos_desenvolvimento_historias.csv",
        help="CSV fonte de tempos por história",
    )
    parser.add_argument(
        "--saida-resumo",
        default="analises/03_otimizacao/cenarios_resumo.csv",
        help="CSV resumo dos cenários principais",
    )
    parser.add_argument(
        "--saida-ranking-5",
        default="analises/03_otimizacao/cenarios_melhor_5_squads_ranking.csv",
        help="CSV ranking combinações 5 squads",
    )
    parser.add_argument(
        "--saida-ranking-8",
        default="analises/03_otimizacao/cenarios_melhor_8_squads_ranking.csv",
        help="CSV ranking combinações 8 squads",
    )
    parser.add_argument(
        "--saida-melhores-json",
        default="analises/03_otimizacao/cenarios_melhores.json",
        help="JSON com melhores configurações",
    )
    parser.add_argument(
        "--saida-base-alocacoes",
        default="analises/03_otimizacao/cenario_base_5_alocacoes.csv",
        help="CSV de alocações do cenário base 5 squads",
    )
    parser.add_argument(
        "--saida-ref8-alocacoes",
        default="analises/03_otimizacao/cenario_referencia_8_alocacoes.csv",
        help="CSV de alocações do cenário referência 8 squads",
    )
    parser.add_argument(
        "--saida-melhor5-alocacoes",
        default="analises/03_otimizacao/cenario_melhor_5_alocacoes.csv",
        help="CSV de alocações do melhor cenário 5 squads",
    )
    parser.add_argument(
        "--saida-melhor8-alocacoes",
        default="analises/03_otimizacao/cenario_melhor_8_alocacoes.csv",
        help="CSV de alocações do melhor cenário 8 squads",
    )
    parser.add_argument(
        "--saida-devs-alocacoes",
        default="analises/03_otimizacao/cenario_somente_devs_5_alocacoes.csv",
        help="CSV de alocações do cenário só desenvolvedores",
    )
    parser.add_argument(
        "--saida-devs11-alocacoes",
        default="analises/03_otimizacao/cenario_devs11_prazo30jun_alocacoes.csv",
        help="CSV de alocações do cenário 11 devs/squad (meta 30/06/2026)",
    )
    parser.add_argument(
        "--saida-devs6sq-alocacoes",
        default="analises/03_otimizacao/cenario_devs_6squads_alocacoes.csv",
        help="CSV de alocações do cenário 6 squads +10 devs",
    )
    parser.add_argument(
        "--saida-devs7sq-alocacoes",
        default="analises/03_otimizacao/cenario_devs_7squads_alocacoes.csv",
        help="CSV de alocações do cenário 7 squads +20 devs",
    )
    parser.add_argument(
        "--saida-devs12-alocacoes",
        default="analises/03_otimizacao/cenario_devs_12por5squads_alocacoes.csv",
        help="CSV de alocações do cenário 5 squads com 12 devs cada",
    )
    parser.add_argument(
        "--saida-devs20-alocacoes",
        default="analises/03_otimizacao/cenario_devs_20por5squads_alocacoes.csv",
        help="CSV de alocações do cenário 5 squads com 20 devs cada",
    )
    parser.add_argument(
        "--saida-sq6ant-alocacoes",
        default="analises/03_otimizacao/cenario_sq6_antecipada_comercial_alocacoes.csv",
        help="CSV de alocações do cenário Squad 6 antecipada em COMERCIAL",
    )
    parser.add_argument(
        "--saida-8sq-dedicadas-alocacoes",
        default="analises/03_otimizacao/cenario_8sq_dedicadas_alocacoes.csv",
        help="CSV de alocações do cenário 8 squads dedicadas com Comercial Squad 6",
    )
    parser.add_argument(
        "--saida-8sq-reforco-sc-alocacoes",
        default="analises/03_otimizacao/cenario_8sq_reforco_supply_chain_alocacoes.csv",
        help="CSV de alocações do cenário 8 squads dedicadas com reforço no Supply Chain",
    )
    parser.add_argument(
        "--saida-pior-alocacoes",
        default="analises/03_otimizacao/cenario_pior_alocacoes.csv",
        help="CSV de alocações do cenário pior caso (inicio 23/03)",
    )
    parser.add_argument(
        "--saida-esperado-alocacoes",
        default="analises/03_otimizacao/cenario_esperado_alocacoes.csv",
        help="CSV de alocações do cenário esperado (inicio 23/03)",
    )
    parser.add_argument(
        "--saida-otimista-alocacoes",
        default="analises/03_otimizacao/cenario_otimista_alocacoes.csv",
        help="CSV de alocações do cenário otimista (inicio 23/03)",
    )
    args = parser.parse_args()

    entrada = Path(args.entrada)
    historias = carregar_historias(entrada)
    lakes_existentes = {h.lake for h in historias}

    cenario_base_5 = normalizar_config_para_lakes_existentes(montar_cenario_base_5(), lakes_existentes)
    cenario_8_ref = normalizar_config_para_lakes_existentes(montar_cenario_8_referencia(), lakes_existentes)

    sim_base = simular_cenario_papeis(historias, cenario_base_5, engenheiros_por_squad=8, analistas_por_squad=2)
    sim_8_ref = simular_cenario_papeis(historias, cenario_8_ref, engenheiros_por_squad=8, analistas_por_squad=2)

    ranking_5 = calcular_melhor_5_squads(historias)
    ranking_8 = calcular_melhor_8_squads(historias)

    melhor_5 = ranking_5[0]
    melhor_8 = ranking_8[0]

    cenario_devs = normalizar_config_para_lakes_existentes(montar_cenario_base_5(), lakes_existentes)
    sim_devs = simular_cenario_somente_devs(historias, cenario_devs, devs_por_squad=10)
    sim_devs_11 = simular_cenario_somente_devs(historias, cenario_devs, devs_por_squad=11)

    cenario_devs_6sq = normalizar_config_para_lakes_existentes(montar_cenario_devs_6_squads(), lakes_existentes)
    sim_devs_6sq = simular_cenario_somente_devs(historias, cenario_devs_6sq, devs_por_squad=10)

    cenario_devs_7sq = normalizar_config_para_lakes_existentes(montar_cenario_devs_7_squads(), lakes_existentes)
    sim_devs_7sq = simular_cenario_somente_devs(historias, cenario_devs_7sq, devs_por_squad=10)

    # Cenário: 5 squads com 12 devs cada (mesmo total de +10 via Squad 6, mas distribuído)
    sim_devs_12sq5 = simular_cenario_somente_devs(historias, cenario_devs, devs_por_squad=12)

    # Cenário: 5 squads com 20 devs cada
    sim_devs_20sq5 = simular_cenario_somente_devs(historias, cenario_devs, devs_por_squad=20)

    # Cenário: Squad 6 com 5 devs começa COMERCIAL em 23/03/2026; demais squads em 01/04/2026
    cenario_sq6_antecipada = normalizar_config_para_lakes_existentes(
        {
            "BMC": ["Squad 1"],
            "COMPRAS": ["Squad 1"],
            "MOPAR": ["Squad 2"],
            "CLIENTE": ["Squad 3"],
            "SHARED SERVICES": ["Squad 1", "Squad 4"],
            "RH": ["Squad 2"],
            "FINANCE": ["Squad 3"],
            "SUPPLY CHAIN": ["Squad 5"],
            "COMERCIAL": ["Squad 1", "Squad 4", "Squad 6"],
        },
        lakes_existentes,
    )
    sim_devs_sq6_antecipada = simular_cenario_somente_devs_flex(
        historias,
        cenario_sq6_antecipada,
        devs_por_squad={
            "Squad 1": 10, "Squad 2": 10, "Squad 3": 10,
            "Squad 4": 10, "Squad 5": 10, "Squad 6": 5,
        },
        inicio_por_squad={
            "Squad 1": parse_data_br("09/03/2026"),
            "Squad 2": parse_data_br("01/04/2026"),
            "Squad 3": parse_data_br("01/04/2026"),
            "Squad 4": parse_data_br("01/04/2026"),
            "Squad 5": parse_data_br("01/04/2026"),
            "Squad 6": parse_data_br("23/03/2026"),
        },
    )

    # Cenário: 8 squads dedicadas, COMERCIAL com Squad 6 (20 devs, início 23/03)
    # Squad 6 começa com 5 devs em 23/03; os 20 devs totais ficam disponíveis desde 23/03
    cenario_8sq_dedicadas = normalizar_config_para_lakes_existentes(
        {
            "BMC": ["Squad 1"],
            "COMPRAS": ["Squad 1"],
            "MOPAR": ["Squad 2"],
            "CLIENTE": ["Squad 3"],
            "SHARED SERVICES": ["Squad 4", "Squad 1"],
            "RH": ["Squad 7"],
            "FINANCE": ["Squad 8"],
            "SUPPLY CHAIN": ["Squad 5"],
            "COMERCIAL": ["Squad 6"],
        },
        lakes_existentes,
    )
    sim_8sq_dedicadas = simular_cenario_somente_devs_flex(
        historias,
        cenario_8sq_dedicadas,
        devs_por_squad={
            "Squad 1": 10, "Squad 2": 10, "Squad 3": 10, "Squad 4": 10,
            "Squad 5": 10, "Squad 6": 20, "Squad 7": 10, "Squad 8": 10,
        },
        inicio_por_squad={
            "Squad 1": parse_data_br("09/03/2026"),
            "Squad 2": parse_data_br("01/04/2026"),
            "Squad 3": parse_data_br("01/04/2026"),
            "Squad 4": parse_data_br("01/04/2026"),
            "Squad 5": parse_data_br("01/04/2026"),
            "Squad 6": parse_data_br("23/03/2026"),
            "Squad 7": parse_data_br("01/04/2026"),
            "Squad 8": parse_data_br("01/04/2026"),
        },
    )

    # Cenário: igual ao anterior + squads livres reforçam Supply Chain quando terminam seus lakes
    # Squads que ficam livres antes de 10/06: Sq2(08/05), Sq3(18/05), Sq8(20/05), Sq4(22/05), Sq6(22/05), Sq1(25/05), Sq7(27/05)
    cenario_8sq_reforco_sc = normalizar_config_para_lakes_existentes(
        {
            "BMC": ["Squad 1"],
            "COMPRAS": ["Squad 1"],
            "MOPAR": ["Squad 2"],
            "CLIENTE": ["Squad 3"],
            "SHARED SERVICES": ["Squad 4", "Squad 1"],
            "RH": ["Squad 7"],
            "FINANCE": ["Squad 8"],
            "SUPPLY CHAIN": ["Squad 5", "Squad 2", "Squad 3", "Squad 8", "Squad 4", "Squad 1", "Squad 7"],
            "COMERCIAL": ["Squad 6"],
        },
        lakes_existentes,
    )
    sim_8sq_reforco_sc = simular_cenario_somente_devs_flex(
        historias,
        cenario_8sq_reforco_sc,
        devs_por_squad={
            "Squad 1": 10, "Squad 2": 10, "Squad 3": 10, "Squad 4": 10,
            "Squad 5": 10, "Squad 6": 20, "Squad 7": 10, "Squad 8": 10,
        },
        inicio_por_squad={
            "Squad 1": parse_data_br("09/03/2026"),
            "Squad 2": parse_data_br("01/04/2026"),
            "Squad 3": parse_data_br("01/04/2026"),
            "Squad 4": parse_data_br("01/04/2026"),
            "Squad 5": parse_data_br("01/04/2026"),
            "Squad 6": parse_data_br("23/03/2026"),
            "Squad 7": parse_data_br("01/04/2026"),
            "Squad 8": parse_data_br("01/04/2026"),
        },
    )

    # -------------------------------------------------------------------------
    # Cenários pior / esperado / otimista — todos iniciam em 23/03/2026
    # Configuração de squads por lake:
    #   BMC         -> Squad 1
    #   Compras     -> Squad 1
    #   Mopar       -> Squad 2
    #   Cliente     -> Squad 3
    #   Shared Svc  -> Squad 4 + Squad 1
    #   RH          -> Squad 7  (reforço das squads livres ao terminar)
    #   Finance     -> Squad 8  (reforço das squads livres ao terminar)
    #   Supply Chain-> Squad 5
    #   Comercial   -> Squad 6  (reforço das squads livres ao terminar)
    # -------------------------------------------------------------------------
    # -------------------------------------------------------------------------
    # Cenários pior / esperado / otimista — início 23/03/2026
    #
    # Regra: os devs dedicadso da squad 1 começam em 09/03/2026 para BMC e Compras com todos os devs; os demais devs de todas as squads começam em 23/03/2026.
    # os devs da tabela (dedicados ao lake) começam em 23/03.
    # O reforço de squads que terminam seus lakes também começa em 23/03 porque
    # as squads inteiras iniciam em 23/03 — o reforço chega naturalmente após
    # cada squad concluir suas histórias primárias.
    #
    # Mapa de alocações:
    #   Squad 1 (10 devs): BMC, Compras, Shared Services → reforça Comercial e RH
    #   Squad 2 (10 devs): Mopar                        → reforça Comercial e RH
    #   Squad 3 (10 devs): Cliente                      → reforça Comercial e RH
    #   Squad 4 (10 devs): Shared Services              → reforça Comercial e RH
    #   Squad 5 (10 devs): Supply Chain                 → reforça Comercial e RH
    #   Squad 6 (20 devs): Comercial (dedicada)
    #   Squad 7 ( 5 devs): RH (dedicada)                → reforça Comercial
    #   Squad 8 ( 5 devs): Finance                      → reforça Comercial e RH
    # -------------------------------------------------------------------------
    DATA_INICIO_NOVO = parse_data_br("23/03/2026")
    DATA_INICIO_BMC_COMPRAS = parse_data_br("09/03/2026")
    DATA_INICIO_REFORCO = parse_data_br("01/04/2026")

    # SHARED SERVICES dividido em dois grupos por número de história:
    #   histórias 1–64  → "SHARED SERVICES A" → Squad 4 (primária)
    #   histórias 65+   → "SHARED SERVICES B" → Squad 1 (secundária)
    CORTE_SHARED = 64
    historias_refinados = []
    for h in historias:
        if h.lake == "SHARED SERVICES":
            lake_virtual = "SHARED SERVICES A" if h.numero <= CORTE_SHARED else "SHARED SERVICES B"
            historias_refinados.append(
                Story(
                    id_historia=h.id_historia,
                    lake=lake_virtual,
                    numero=h.numero,
                    titulo=h.titulo,
                    engenheiro_dias=h.engenheiro_dias,
                    analista_dias=h.analista_dias,
                )
            )
        else:
            historias_refinados.append(h)

    lakes_existentes_refinados = {h.lake for h in historias_refinados}

    # Mapa de squads por lake.
    # Squad 4 é primária de SHARED SERVICES A (histórias 1–64).
    # Squad 1 é primária de SHARED SERVICES B (histórias 65+), BMC e COMPRAS.
    # Squad 1 começa em 09/03 com todos os devs em BMC e COMPRAS.
    lake_para_squads_novo = normalizar_config_para_lakes_existentes(
        {
            "BMC":               ["Squad 1"],
            "COMPRAS":           ["Squad 1"],
            "MOPAR":             ["Squad 2"],
            "CLIENTE":           ["Squad 3"],
            "SHARED SERVICES A": ["Squad 4"],
            "SHARED SERVICES B": ["Squad 1"],
            "RH":                ["Squad 7", "Squad 2", "Squad 3", "Squad 4"],
            "FINANCE":           ["Squad 8", "Squad 2", "Squad 3", "Squad 4"],
            "SUPPLY CHAIN":      ["Squad 5", "Squad 6"],
            "COMERCIAL":         ["Squad 6", "Squad 2", "Squad 3", "Squad 4", "Squad 7", "Squad 8"],
        },
        lakes_existentes_refinados,
    )

    # Tamanho fixo de cada squad (total de devs)
    tamanho_squads = {
        "Squad 1": 10, "Squad 2": 10, "Squad 3": 10, "Squad 4": 10,
        "Squad 5": 10, "Squad 6": 20, "Squad 7": 5,  "Squad 8": 5,
    }

    # Squad 1 começa em 09/03 (BMC e COMPRAS com todos os devs); demais em 23/03.
    inicio_squads_novo = {f"Squad {i}": DATA_INICIO_NOVO for i in range(1, 9)}
    inicio_squads_novo["Squad 1"] = DATA_INICIO_BMC_COMPRAS

    # Devs dedicados por lake desde início da squad — pior cenário (mínimo)
    devs_pior = {
        "BMC":               {"Squad 1": 10},
        "COMPRAS":           {"Squad 1": 10},
        "MOPAR":             {"Squad 2": 1},
        "CLIENTE":           {"Squad 3": 1},
        "SHARED SERVICES A": {"Squad 4": 1},
        "SHARED SERVICES B": {"Squad 1": 1},
        "SUPPLY CHAIN":      {"Squad 5": 1},
        "RH":                {"Squad 7": 1},
        "FINANCE":           {"Squad 8": 1},
        "COMERCIAL":         {"Squad 6": 2},
    }

    # Devs dedicados por lake — cenário esperado
    devs_esperado = {
        "BMC":               {"Squad 1": 10},
        "COMPRAS":           {"Squad 1": 10},
        "MOPAR":             {"Squad 2": 2},
        "CLIENTE":           {"Squad 3": 2},
        "SHARED SERVICES A": {"Squad 4": 4},
        "SHARED SERVICES B": {"Squad 1": 4},
        "SUPPLY CHAIN":      {"Squad 5": 4},
        "RH":                {"Squad 7": 2},
        "FINANCE":           {"Squad 8": 4},
        "COMERCIAL":         {"Squad 6": 5},
    }

    # Devs dedicados por lake — cenário otimista
    devs_otimista = {
        "BMC":               {"Squad 1": 10},
        "COMPRAS":           {"Squad 1": 10},
        "MOPAR":             {"Squad 2": 4},
        "CLIENTE":           {"Squad 3": 4},
        "SHARED SERVICES A": {"Squad 4": 4},
        "SHARED SERVICES B": {"Squad 1": 4},
        "SUPPLY CHAIN":      {"Squad 5": 4},
        "RH":                {"Squad 7": 4},
        "FINANCE":           {"Squad 8": 4},
        "COMERCIAL":         {"Squad 6": 8},
    }

    inicio_minimo_lakes_refinados = {"COMPRAS": DATA_INICIO_NOVO}

    sim_pior = simular_cenario_devs_por_lake(
        historias_refinados, lake_para_squads_novo, devs_pior, DATA_INICIO_BMC_COMPRAS,
        inicio_squads_novo, tamanho_squads, DATA_INICIO_REFORCO,
        inicio_minimo_por_lake=inicio_minimo_lakes_refinados,
    )
    sim_esperado = simular_cenario_devs_por_lake(
        historias_refinados, lake_para_squads_novo, devs_esperado, DATA_INICIO_BMC_COMPRAS,
        inicio_squads_novo, tamanho_squads, DATA_INICIO_REFORCO,
        inicio_minimo_por_lake=inicio_minimo_lakes_refinados,
    )
    sim_otimista = simular_cenario_devs_por_lake(
        historias_refinados, lake_para_squads_novo, devs_otimista, DATA_INICIO_BMC_COMPRAS,
        inicio_squads_novo, tamanho_squads, DATA_INICIO_REFORCO,
        inicio_minimo_por_lake=inicio_minimo_lakes_refinados,
    )

    print(f"Pior caso    (inicio 23/03): {sim_pior['fim_projeto'].strftime('%d/%m/%Y')}")
    print(f"Esperado     (inicio 23/03): {sim_esperado['fim_projeto'].strftime('%d/%m/%Y')}")
    print(f"Otimista     (inicio 23/03): {sim_otimista['fim_projeto'].strftime('%d/%m/%Y')}")

    saida_resumo = Path(args.saida_resumo)
    saida_resumo.parent.mkdir(parents=True, exist_ok=True)

    resumo = pd.DataFrame(
        [
            {
                "cenario": "Base (5 squads)",
                "inicio_projeto": DATA_INICIO_ANTECIPADA,
                "fim_projeto": sim_base["fim_projeto"].strftime("%d/%m/%Y"),
                "prazo_dias_corridos": sim_base["prazo_corridos"],
                "observacao": "Mapa fixo informado pelo usuário",
            },
            {
                "cenario": "Referência (8 squads)",
                "inicio_projeto": DATA_INICIO_ANTECIPADA,
                "fim_projeto": sim_8_ref["fim_projeto"].strftime("%d/%m/%Y"),
                "prazo_dias_corridos": sim_8_ref["prazo_corridos"],
                "observacao": "Mapa 8 squads informado pelo usuário",
            },
            {
                "cenario": "Melhor combinação (5 squads)",
                "inicio_projeto": DATA_INICIO_ANTECIPADA,
                "fim_projeto": melhor_5["fim_projeto"].strftime("%d/%m/%Y"),
                "prazo_dias_corridos": melhor_5["prazo_dias_corridos"],
                "observacao": f"RH={melhor_5['RH']}; FINANCE={melhor_5['FINANCE']}; SUPPLY={melhor_5['SUPPLY_CHAIN']}; COMERCIAL+={melhor_5['COMERCIAL_2']}",
            },
            {
                "cenario": "Melhor combinação (8 squads)",
                "inicio_projeto": DATA_INICIO_ANTECIPADA,
                "fim_projeto": melhor_8["fim_projeto"].strftime("%d/%m/%Y"),
                "prazo_dias_corridos": melhor_8["prazo_dias_corridos"],
                "observacao": f"RH={melhor_8['RH']}; FINANCE={melhor_8['FINANCE']}; SUPPLY={melhor_8['SUPPLY_CHAIN']}; COMERCIAL+={melhor_8['COMERCIAL_2']}",
            },
            {
                "cenario": "Só desenvolvedores (5 squads, 10 devs por squad)",
                "inicio_projeto": DATA_INICIO_ANTECIPADA,
                "fim_projeto": sim_devs["fim_projeto"].strftime("%d/%m/%Y"),
                "prazo_dias_corridos": sim_devs["prazo_corridos"],
                "observacao": "Duração por história = engenheiro_dias + analista_dias",
            },
            {
                "cenario": "Só desenvolvedores - prazo 30/06 (5 squads, 11 devs por squad)",
                "inicio_projeto": DATA_INICIO_ANTECIPADA,
                "fim_projeto": sim_devs_11["fim_projeto"].strftime("%d/%m/%Y"),
                "prazo_dias_corridos": sim_devs_11["prazo_corridos"],
                "observacao": "Cenário mínimo para terminar até 30/06/2026",
            },
            {
                "cenario": "Só devs +10 (6 squads, 10 devs por squad)",
                "inicio_projeto": DATA_INICIO_ANTECIPADA,
                "fim_projeto": sim_devs_6sq["fim_projeto"].strftime("%d/%m/%Y"),
                "prazo_dias_corridos": sim_devs_6sq["prazo_corridos"],
                "observacao": "Squad 6 reforça COMERCIAL (gargalo real identificado)",
            },
            {
                "cenario": "Só devs +20 (7 squads, 10 devs por squad)",
                "inicio_projeto": DATA_INICIO_ANTECIPADA,
                "fim_projeto": sim_devs_7sq["fim_projeto"].strftime("%d/%m/%Y"),
                "prazo_dias_corridos": sim_devs_7sq["prazo_corridos"],
                "observacao": "Squad 6 reforça COMERCIAL/SUPPLY CHAIN; Squad 7 reforça RH e FINANCE",
            },
            {
                "cenario": "5 squads 12 devs cada (60 devs total)",
                "inicio_projeto": DATA_INICIO_ANTECIPADA,
                "fim_projeto": sim_devs_12sq5["fim_projeto"].strftime("%d/%m/%Y"),
                "prazo_dias_corridos": sim_devs_12sq5["prazo_corridos"],
                "observacao": "+2 devs por squad distribuído nas 5 squads",
            },
            {
                "cenario": "5 squads 20 devs cada (100 devs total)",
                "inicio_projeto": DATA_INICIO_ANTECIPADA,
                "fim_projeto": sim_devs_20sq5["fim_projeto"].strftime("%d/%m/%Y"),
                "prazo_dias_corridos": sim_devs_20sq5["prazo_corridos"],
                "observacao": "+10 devs por squad distribuído nas 5 squads",
            },
            {
                "cenario": "Squad 6 antecipada 23/03 em COMERCIAL (5 devs) + 5 squads 01/04",
                "inicio_projeto": DATA_INICIO_ANTECIPADA,
                "fim_projeto": sim_devs_sq6_antecipada["fim_projeto"].strftime("%d/%m/%Y"),
                "prazo_dias_corridos": sim_devs_sq6_antecipada["prazo_corridos"],
                "observacao": "Squad 6 com 5 devs inicia COMERCIAL em 23/03; squads 2-5 iniciam em 01/04",
            },
            {
                "cenario": "8 squads dedicadas - Comercial Squad 6 (20 devs desde 23/03)",
                "inicio_projeto": DATA_INICIO_ANTECIPADA,
                "fim_projeto": sim_8sq_dedicadas["fim_projeto"].strftime("%d/%m/%Y"),
                "prazo_dias_corridos": sim_8sq_dedicadas["prazo_corridos"],
                "observacao": "Sq1=BMC/Compras/SS, Sq2=Mopar, Sq3=Cliente, Sq4=SS, Sq5=Supply, Sq6=Comercial(20devs,23/03), Sq7=RH, Sq8=Finance",
            },
            {
                "cenario": "8 squads dedicadas + squads livres reforçam Supply Chain",
                "inicio_projeto": DATA_INICIO_ANTECIPADA,
                "fim_projeto": sim_8sq_reforco_sc["fim_projeto"].strftime("%d/%m/%Y"),
                "prazo_dias_corridos": sim_8sq_reforco_sc["prazo_corridos"],
                "observacao": "Igual ao anterior, squads 2/3/4/6/7/8 reforçam Supply Chain ao terminarem seus lakes",
            },
            {
                "cenario": "Pior caso - 8 squads (inicio 23/03)",
                "inicio_projeto": "23/03/2026",
                "fim_projeto": sim_pior["fim_projeto"].strftime("%d/%m/%Y"),
                "prazo_dias_corridos": sim_pior["prazo_corridos"],
                "observacao": "BMC:1dev, Compras:1, Mopar:1, Cliente:1, SS:1, RH:1(Sq7)+reforco, Finance:1(Sq8)+reforco, SC:1(Sq5), Comercial:2(Sq6)+reforco",
            },
            {
                "cenario": "Esperado - 8 squads (inicio 23/03)",
                "inicio_projeto": "23/03/2026",
                "fim_projeto": sim_esperado["fim_projeto"].strftime("%d/%m/%Y"),
                "prazo_dias_corridos": sim_esperado["prazo_corridos"],
                "observacao": "BMC:1dev, Compras:2, Mopar:2, Cliente:2, SS:4, RH:2(Sq7)+reforco, Finance:4(Sq8)+reforco, SC:4(Sq5), Comercial:5(Sq6)+reforco",
            },
            {
                "cenario": "Otimista - 8 squads (inicio 23/03)",
                "inicio_projeto": "23/03/2026",
                "fim_projeto": sim_otimista["fim_projeto"].strftime("%d/%m/%Y"),
                "prazo_dias_corridos": sim_otimista["prazo_corridos"],
                "observacao": "BMC:1dev, Compras:4, Mopar:4, Cliente:4, SS:4, RH:4(Sq7)+reforco, Finance:4(Sq8)+reforco, SC:4(Sq5), Comercial:8(Sq6)+reforco",
            },
        ]
    )
    resumo.to_csv(saida_resumo, index=False)

    ranking5_df = pd.DataFrame(
        [
            {
                "fim_projeto": row["fim_projeto"].strftime("%d/%m/%Y"),
                "prazo_dias_corridos": row["prazo_dias_corridos"],
                "RH": row["RH"],
                "FINANCE": row["FINANCE"],
                "SUPPLY_CHAIN": row["SUPPLY_CHAIN"],
                "COMERCIAL_2": row["COMERCIAL_2"],
            }
            for row in ranking_5
        ]
    )
    Path(args.saida_ranking_5).parent.mkdir(parents=True, exist_ok=True)
    ranking5_df.to_csv(args.saida_ranking_5, index=False)

    ranking8_df = pd.DataFrame(
        [
            {
                "fim_projeto": row["fim_projeto"].strftime("%d/%m/%Y"),
                "prazo_dias_corridos": row["prazo_dias_corridos"],
                "RH": row["RH"],
                "FINANCE": row["FINANCE"],
                "SUPPLY_CHAIN": row["SUPPLY_CHAIN"],
                "COMERCIAL_2": row["COMERCIAL_2"],
            }
            for row in ranking_8
        ]
    )
    Path(args.saida_ranking_8).parent.mkdir(parents=True, exist_ok=True)
    ranking8_df.to_csv(args.saida_ranking_8, index=False)

    salvar_alocacoes(Path(args.saida_base_alocacoes), sim_base["alocacoes"])
    salvar_alocacoes(Path(args.saida_ref8_alocacoes), sim_8_ref["alocacoes"])

    sim_melhor_5 = simular_cenario_papeis(historias, melhor_5["config"], engenheiros_por_squad=8, analistas_por_squad=2)
    sim_melhor_8 = simular_cenario_papeis(historias, melhor_8["config"], engenheiros_por_squad=8, analistas_por_squad=2)
    salvar_alocacoes(Path(args.saida_melhor5_alocacoes), sim_melhor_5["alocacoes"])
    salvar_alocacoes(Path(args.saida_melhor8_alocacoes), sim_melhor_8["alocacoes"])
    salvar_alocacoes(Path(args.saida_devs_alocacoes), sim_devs["alocacoes"])
    salvar_alocacoes(Path(args.saida_devs11_alocacoes), sim_devs_11["alocacoes"])
    salvar_alocacoes(Path(args.saida_devs6sq_alocacoes), sim_devs_6sq["alocacoes"])
    salvar_alocacoes(Path(args.saida_devs7sq_alocacoes), sim_devs_7sq["alocacoes"])
    salvar_alocacoes(Path(args.saida_devs12_alocacoes), sim_devs_12sq5["alocacoes"])
    salvar_alocacoes(Path(args.saida_devs20_alocacoes), sim_devs_20sq5["alocacoes"])
    salvar_alocacoes(Path(args.saida_sq6ant_alocacoes), sim_devs_sq6_antecipada["alocacoes"])
    salvar_alocacoes(Path(args.saida_8sq_dedicadas_alocacoes), sim_8sq_dedicadas["alocacoes"])
    salvar_alocacoes(Path(args.saida_8sq_reforco_sc_alocacoes), sim_8sq_reforco_sc["alocacoes"])
    salvar_alocacoes(Path(args.saida_pior_alocacoes), sim_pior["alocacoes"])
    salvar_alocacoes(Path(args.saida_esperado_alocacoes), sim_esperado["alocacoes"])
    salvar_alocacoes(Path(args.saida_otimista_alocacoes), sim_otimista["alocacoes"])

    melhores_payload = {
        "base_5_squads": {
            "fim_projeto": sim_base["fim_projeto"].strftime("%d/%m/%Y"),
            "prazo_dias_corridos": sim_base["prazo_corridos"],
            "config": cenario_base_5,
        },
        "referencia_8_squads": {
            "fim_projeto": sim_8_ref["fim_projeto"].strftime("%d/%m/%Y"),
            "prazo_dias_corridos": sim_8_ref["prazo_corridos"],
            "config": cenario_8_ref,
        },
        "melhor_5_squads": {
            "fim_projeto": melhor_5["fim_projeto"].strftime("%d/%m/%Y"),
            "prazo_dias_corridos": melhor_5["prazo_dias_corridos"],
            "RH": melhor_5["RH"],
            "FINANCE": melhor_5["FINANCE"],
            "SUPPLY_CHAIN": melhor_5["SUPPLY_CHAIN"],
            "COMERCIAL_2": melhor_5["COMERCIAL_2"],
            "config": melhor_5["config"],
        },
        "melhor_8_squads": {
            "fim_projeto": melhor_8["fim_projeto"].strftime("%d/%m/%Y"),
            "prazo_dias_corridos": melhor_8["prazo_dias_corridos"],
            "RH": melhor_8["RH"],
            "FINANCE": melhor_8["FINANCE"],
            "SUPPLY_CHAIN": melhor_8["SUPPLY_CHAIN"],
            "COMERCIAL_2": melhor_8["COMERCIAL_2"],
            "config": melhor_8["config"],
        },
        "somente_devs_5_squads": {
            "fim_projeto": sim_devs["fim_projeto"].strftime("%d/%m/%Y"),
            "prazo_dias_corridos": sim_devs["prazo_corridos"],
            "config": cenario_devs,
        },
        "devs11_prazo30jun": {
            "fim_projeto": sim_devs_11["fim_projeto"].strftime("%d/%m/%Y"),
            "prazo_dias_corridos": sim_devs_11["prazo_corridos"],
            "config": cenario_devs,
            "devs_por_squad": 11,
        },
        "observacoes": {
            "inicio_bmc_compras": DATA_INICIO_ANTECIPADA,
            "inicio_demais_lakes": DATA_INICIO_PADRAO,
            "lakes_sem_dados_no_csv": sorted(set(["SHARED SERVICES"]) - lakes_existentes),
        },
    }

    saida_json = Path(args.saida_melhores_json)
    saida_json.parent.mkdir(parents=True, exist_ok=True)
    saida_json.write_text(json.dumps(melhores_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Cálculo de cenários concluído.")
    print(f"Resumo: {Path(args.saida_resumo)}")
    print(f"Ranking 5 squads: {Path(args.saida_ranking_5)}")
    print(f"Ranking 8 squads: {Path(args.saida_ranking_8)}")
    print(f"Melhores cenários (json): {saida_json}")


if __name__ == "__main__":
    main()

