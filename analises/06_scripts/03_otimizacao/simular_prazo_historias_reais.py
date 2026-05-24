"""
Simula o prazo das histórias ainda não finalizadas usando as medianas reais
de Dev e QA por squad, medidas a partir do histórico do Jira.

Premissas:
- Cada Dev de uma squad só pode trabalhar em 1 história por vez (fila greedy)
- Os 23 QAs são cross-squad: cada QA só pode testar 1 história por vez (fila greedy)
- Medianas em dias corridos (conforme medido em medir_tempo_status_historias.py)
- Feriados nacionais de 2026 são respeitados para dias úteis (mas os tempos já
  são corridos — usamos dias corridos para avançar datas também)

Cenários gerados:
  A) Dev restante = mediana completa a partir de hoje (independente do tempo já gasto)
  B) Dev restante = mediana − tempo já decorrido desde entrada em IN DEVELOPMENT
     (mínimo = 0, ou seja, já pode ir direto para QA se passou mais que a mediana)

Saídas:
  - analises/03_otimizacao/prazo_historias_reais_alocacoes_A.csv
  - analises/03_otimizacao/prazo_historias_reais_alocacoes_B.csv
  - analises/04_visualizacoes/prazo_historias_reais.html
  - analises/04_visualizacoes/prazo_historias_reais.json
"""

import argparse
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.express as px
from plotly.utils import PlotlyJSONEncoder

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
FUSO = ZoneInfo("America/Sao_Paulo")
HOJE = datetime.now(tz=FUSO).replace(tzinfo=None).replace(hour=9, minute=0, second=0, microsecond=0)

FERIADOS: set[date] = {
    date(2026,  4,  3),
    date(2026,  4, 21),
    date(2026,  5,  1),
    date(2026,  6,  4),
    date(2026,  9,  7),
    date(2026, 10, 12),
    date(2026, 11,  2),
    date(2026, 11, 15),
    date(2026, 11, 20),
}

# Tamanho de cada squad (devs) — conforme calcular_cenarios_squads.py
# Squad 2 (10 devs) → reforça SUPPLYCHAIN  (ratio 2.60 stories/dev antes do reforço)
# Squad 3 (10 devs) → reforça FINANCE      (ratio 3.40 stories/dev — maior gargalo)
DEVS_POR_SQUAD: dict[str, int] = {
    "SQUAD_1": 10,
    "SQUAD_2": 10,   # reforço SUPPLYCHAIN
    "SQUAD_3": 10,   # reforço FINANCE
    "SQUAD_4": 10,
    "SQUAD_5": 10,
    "SQUAD_6": 20,
    "SQUAD_7":  5,
    "SQUAD_8":  5,
}

# Lakes atendidos por cada squad (incluindo reforços de Squad 2 e 3)
# Squad 2 e 3 não têm histórias próprias; elas pegam histórias dos lakes que reforçam
LAKE_REFORCO: dict[str, str] = {
    "SQUAD_2": "SUPPLYCHAIN",
    "SQUAD_3": "FINANCE",
}

# Ordem dos lakes para exibição no Gantt (de cima para baixo)
LAKES_ORDEM = [
    "BMC", "COMPRAS", "MOPAR", "CLIENTE",
    "SHAREDSERVICES", "RH", "FINANCE", "SUPPLYCHAIN", "COMERCIAL",
]

TOTAL_QAS = 23

# Medianas por squad (dias corridos) — lidas do CSV gerado pelo script de medição
# Se uma squad não tiver mediana própria, usa a mediana geral
MEDIANA_GERAL_DEV = 7.01
MEDIANA_GERAL_QA  = 3.14

# Medianas de Dev e QA por lake para cenários C e D
# Calculadas sobre histórias com ciclo Dev+QA completo no histórico do Jira
# BMC (n=1) e COMERCIAL (distorção: histórias paradas) usam a mediana geral
MEDIANA_DEV_POR_LAKE: dict[str, float] = {
    "BMC":            MEDIANA_GERAL_DEV,   # n=1 — amostra insuficiente
    "COMPRAS":        20.95,
    "MOPAR":           5.98,
    "CLIENTE":         7.69,
    "SHAREDSERVICES":  7.16,
    "RH":              2.22,
    "FINANCE":         6.11,
    "SUPPLYCHAIN":     7.16,
    "COMERCIAL":      MEDIANA_GERAL_DEV,   # distorção histórica (histórias paradas)
}

MEDIANA_QA_POR_LAKE: dict[str, float] = {
    "BMC":            1.24,
    "COMPRAS":        4.27,
    "MOPAR":          3.19,
    "CLIENTE":        1.07,
    "SHAREDSERVICES": 3.13,
    "RH":             1.93,
    "FINANCE":        5.34,
    "SUPPLYCHAIN":    4.10,
    "COMERCIAL":      3.54,
}

# Cores para o gráfico
COR_DEV = "#4C9BE8"   # azul
COR_QA  = "#F28E2B"   # laranja
COR_DEV_PENDENTE = "#A8C8F0"  # azul claro (status pré-dev)


# ---------------------------------------------------------------------------
# Helpers de data
# ---------------------------------------------------------------------------

def is_dia_util(d: date) -> bool:
    return d.weekday() < 5 and d not in FERIADOS


def avancar_dias_corridos(inicio: datetime, dias: float) -> datetime:
    """Avança `dias` corridos a partir de `inicio`.
    Dias corridos = dias de calendário (incluindo fins de semana),
    pois as medianas foram medidas assim no histórico do Jira.
    """
    if dias <= 0:
        return inicio
    return inicio + timedelta(days=dias)


def proximo_dia_util_dt(dt: datetime) -> datetime:
    """Retorna o próximo dia útil a partir de dt (inclusive se já for útil)."""
    d = dt
    while not is_dia_util(d.date()):
        d += timedelta(days=1)
    return d


def dias_corridos_decorridos(inicio: datetime, fim: datetime) -> float:
    """Dias corridos (úteis) entre dois datetimes."""
    delta = (fim - inicio).total_seconds() / 86400
    return max(0.0, delta)


# ---------------------------------------------------------------------------
# Carga de dados
# ---------------------------------------------------------------------------

def carregar_medianas(caminho: Path) -> tuple[dict, dict]:
    """Retorna dicts {squad: mediana_dev} e {squad: mediana_qa}."""
    res = pd.read_csv(caminho)
    med_dev: dict[str, float] = {}
    med_qa:  dict[str, float] = {}
    for _, row in res.iterrows():
        fase = row["fase"]
        val  = row["mediana_dias_corridos"]
        if "SQUAD_" not in fase:
            continue
        squad = fase.split("[")[1].rstrip("]").strip()
        if fase.startswith("Dev"):
            med_dev[squad] = val
        elif fase.startswith("QA"):
            med_qa[squad] = val
    return med_dev, med_qa


def carregar_historias(caminho: Path) -> pd.DataFrame:
    df = pd.read_csv(caminho)
    df["Data Status"] = df["Data Status"].apply(
        lambda v: datetime.fromisoformat(v).astimezone(FUSO).replace(tzinfo=None)
    )
    return df


# ---------------------------------------------------------------------------
# Simulador greedy
# ---------------------------------------------------------------------------

def simular(
    historias: pd.DataFrame,
    med_dev: dict[str, float],
    med_qa:  dict[str, float],
    modo: str,           # "A", "B", "C" ou "D"
    data_inicio: datetime,
    med_dev_lake: dict[str, float] | None = None,  # None = usa MEDIANA_GERAL_DEV p/ todos
    med_qa_lake:  dict[str, float] | None = None,  # None = usa MEDIANA_GERAL_QA p/ todos
) -> list[dict]:
    """
    Escalonador greedy:
    - Cada squad tem N devs (slots), cada slot tem uma data de disponibilidade.
    - Há 23 slots de QA compartilhados entre todas as squads.
    - Histórias são processadas em ordem de prioridade:
        1. Test / Waiting Test  → já no QA, basta alocar QA
        2. IN DEVELOPMENT       → alocar Dev, depois QA
        3. To Do / Refined / Open → alocar Dev, depois QA
    - med_dev_lake / med_qa_lake: quando fornecidos (cenários C/D), usa a mediana
      histórica do lake da história. Caso o lake não esteja no dict, usa a geral.

    Retorna lista de dicts com as alocações (uma linha por fase por história).
    """
    # Slots de devs por squad: lista de datetimes de disponibilidade
    slots_dev: dict[str, list[datetime]] = {
        sq: [data_inicio] * n for sq, n in DEVS_POR_SQUAD.items()
    }
    # Slots de QA (cross-squad)
    slots_qa: list[datetime] = [data_inicio] * TOTAL_QAS

    # Mapa: lake → lista de squads que atendem esse lake (inclui squads de reforço)
    # Squads originais: construídas a partir dos dados de histórias
    # Squads de reforço (Squad 2 e 3): adicionadas via LAKE_REFORCO
    lake_para_squads: dict[str, list[str]] = {}
    for sq in DEVS_POR_SQUAD:
        if sq in LAKE_REFORCO:
            lake = LAKE_REFORCO[sq]
            lake_para_squads.setdefault(lake, []).append(sq)

    def melhor_slot(slots: list[datetime], nao_antes: datetime) -> tuple[int, datetime]:
        """Índice e data de início do slot disponível mais cedo (>= nao_antes)."""
        melhor_i = min(range(len(slots)), key=lambda i: max(slots[i], nao_antes))
        return melhor_i, max(slots[melhor_i], nao_antes)

    def melhor_slot_pool(pool_slots: list[list[datetime]], nao_antes: datetime) -> tuple[int, int, datetime]:
        """
        Dado um pool de listas de slots (uma por squad), retorna
        (squad_idx, slot_idx, data_inicio) do slot disponível mais cedo.
        """
        melhor = None
        for sq_i, slots in enumerate(pool_slots):
            i, dt = melhor_slot(slots, nao_antes)
            if melhor is None or dt < melhor[2]:
                melhor = (sq_i, i, dt)
        return melhor

    # Ordena: primeiro as que já estão mais avançadas no fluxo
    ordem_status = {"Test": 0, "Waiting Test": 1, "IN DEVELOPMENT": 2,
                    "To Do": 3, "Refined": 4, "Open": 5}
    df = historias.copy()
    df["_ordem"] = df["Status"].map(ordem_status).fillna(9)
    df = df.sort_values(["Squad", "_ordem", "Chave"]).reset_index(drop=True)

    alocacoes = []

    for _, row in df.iterrows():
        chave  = row["Chave"]
        titulo = row["Titulo"]
        squad  = row["Squad"]
        lake   = row["Lake"]
        status = row["Status"]
        dt_status = row["Data Status"]

        # Medianas por lake (cenários C/D) ou geral (cenários A/B)
        mediana_qa = (med_qa_lake.get(lake, MEDIANA_GERAL_QA) if med_qa_lake
                      else MEDIANA_GERAL_QA)

        # Pool de slots de Dev: squad original + squads de reforço do mesmo lake
        squads_pool = [squad]
        for sq_reforco, lake_reforco in LAKE_REFORCO.items():
            if lake_reforco == lake and sq_reforco not in squads_pool:
                squads_pool.append(sq_reforco)
        pool_slots_list = [slots_dev[sq] for sq in squads_pool]

        # ── Fase Dev ────────────────────────────────────────────────────────
        inicio_dev = None
        fim_dev    = None
        squad_dev  = squad   # squad que efetivamente executa o Dev (pode ser reforço)
        num_dev    = None    # número do Dev dentro da squad (1-based)

        def mediana_dev_para(_sq: str) -> float:
            """Retorna mediana de Dev do lake da história (ou geral se não fornecida)."""
            if med_dev_lake:
                return med_dev_lake.get(lake, MEDIANA_GERAL_DEV)
            return MEDIANA_GERAL_DEV

        if status in ("Test", "Waiting Test"):
            # Dev já terminou — fase Dev encerrada antes de hoje
            inicio_dev = None
            fim_dev    = None  # não plotamos barra de dev (já concluída)

        elif status == "IN DEVELOPMENT":
            if modo in ("A", "C"):
                # Cenários A/C: mediana completa a partir de hoje
                sq_i, slot_i, ini = melhor_slot_pool(pool_slots_list, data_inicio)
                squad_dev   = squads_pool[sq_i]
                mediana_dev = mediana_dev_para(squad_dev)
                fim = avancar_dias_corridos(ini, mediana_dev)
                pool_slots_list[sq_i][slot_i] = proximo_dia_util_dt(fim + timedelta(seconds=1))
                num_dev = slot_i + 1
                inicio_dev, fim_dev = ini, fim
            else:
                # Cenários B/D: desconta tempo já decorrido desde entrada no status
                sq_i, slot_i, ini = melhor_slot_pool(pool_slots_list, data_inicio)
                squad_dev   = squads_pool[sq_i]
                mediana_dev = mediana_dev_para(squad_dev)
                decorrido = dias_corridos_decorridos(dt_status, data_inicio)
                restante  = max(0.0, mediana_dev - decorrido)
                if restante > 0:
                    fim = avancar_dias_corridos(ini, restante)
                else:
                    fim = ini  # já pode ir para QA imediatamente
                pool_slots_list[sq_i][slot_i] = proximo_dia_util_dt(fim + timedelta(seconds=1))
                num_dev = slot_i + 1
                inicio_dev, fim_dev = ini, fim

        else:
            # To Do / Refined / Open — Dev ainda não começou
            sq_i, slot_i, ini = melhor_slot_pool(pool_slots_list, data_inicio)
            squad_dev   = squads_pool[sq_i]
            mediana_dev = mediana_dev_para(squad_dev)
            fim = avancar_dias_corridos(ini, mediana_dev)
            pool_slots_list[sq_i][slot_i] = proximo_dia_util_dt(fim + timedelta(seconds=1))
            num_dev = slot_i + 1
            inicio_dev, fim_dev = ini, fim

        # ── Fase QA ────────────────────────────────────────────────────────
        # QA sempre usa mediana geral (cross-squad, sem distinção por squad)
        num_qa = None   # número do QA (1-based)

        if status == "Test":
            # QA em andamento: considera que já começou (dt_status) e termina em mediana_qa
            if modo in ("A", "C"):
                nao_antes_qa = data_inicio
                idx_qa, ini_qa = melhor_slot(slots_qa, nao_antes_qa)
                fim_qa = avancar_dias_corridos(ini_qa, mediana_qa)
            else:
                decorrido_qa = dias_corridos_decorridos(dt_status, data_inicio)
                restante_qa  = max(0.0, mediana_qa - decorrido_qa)
                nao_antes_qa = data_inicio
                idx_qa, ini_qa = melhor_slot(slots_qa, nao_antes_qa)
                fim_qa = avancar_dias_corridos(ini_qa, restante_qa) if restante_qa > 0 else ini_qa

        elif status == "Waiting Test":
            # Aguardando QA: dev terminou, QA não começou
            nao_antes_qa   = data_inicio
            idx_qa, ini_qa = melhor_slot(slots_qa, nao_antes_qa)
            fim_qa         = avancar_dias_corridos(ini_qa, mediana_qa)

        else:
            # Dev ainda não terminou: QA começa após fim do dev
            nao_antes_qa   = fim_dev if fim_dev else data_inicio
            idx_qa, ini_qa = melhor_slot(slots_qa, nao_antes_qa)
            fim_qa         = avancar_dias_corridos(ini_qa, mediana_qa)

        num_qa = idx_qa + 1
        slots_qa[idx_qa] = proximo_dia_util_dt(fim_qa + timedelta(seconds=1))

        # Rótulo do recurso Dev: "Dev 3 - Squad 5"
        squad_dev_label = squad_dev.replace("SQUAD_", "Squad ")
        dev_label = f"Dev {num_dev} - {squad_dev_label}" if num_dev else None

        # Rótulo do recurso QA: "QA - 7"
        qa_label = f"QA - {num_qa}"

        # Mediana efetivamente usada (para exibir no hover)
        med_dev_usada = mediana_dev_para(squad_dev) if status not in ("Test", "Waiting Test") else None
        med_dev_hover = f"{med_dev_usada:.2f} dias".replace(".", ",") if med_dev_usada else "-"
        med_qa_hover  = f"{mediana_qa:.2f} dias".replace(".", ",")

        # ── Registra alocações ──────────────────────────────────────────────
        if inicio_dev is not None and fim_dev is not None and fim_dev > inicio_dev:
            alocacoes.append({
                "chave":           chave,
                "titulo":          titulo,
                "squad":           squad_dev,
                "squad_original":  squad,
                "lake":            lake,
                "fase":            "Dev",
                "recurso":         dev_label,
                "mediana_usada":   med_dev_hover,
                "data_inicio":     inicio_dev.strftime("%d/%m/%Y"),
                "data_fim":        fim_dev.strftime("%d/%m/%Y"),
                "duracao_dias":    round((fim_dev - inicio_dev).total_seconds() / 86400, 2),
                "status_atual":    status,
            })

        alocacoes.append({
            "chave":           chave,
            "titulo":          titulo,
            "squad":           squad,
            "squad_original":  squad,
            "lake":            lake,
            "fase":            "QA",
            "recurso":         qa_label,
            "mediana_usada":   med_qa_hover,
            "data_inicio":     ini_qa.strftime("%d/%m/%Y"),
            "data_fim":        fim_qa.strftime("%d/%m/%Y"),
            "duracao_dias":    round((fim_qa - ini_qa).total_seconds() / 86400, 2),
            "status_atual":    status,
        })

    return alocacoes


# ---------------------------------------------------------------------------
# Visualização Gantt
# ---------------------------------------------------------------------------

# Cor única para QA (azul escuro)
COR_QA_UNICA = "#1B3A6B"

# Cores por squad para Dev — mesmas do pipeline existente (calcular_cenarios_squads)
CORES_SQUAD: dict[str, str] = {
    "SQUAD_1": "#80FF00",   # verde lima
    "SQUAD_2": "#FFD700",   # amarelo
    "SQUAD_3": "#FF8C00",   # laranja
    "SQUAD_4": "#228B22",   # verde escuro
    "SQUAD_5": "#00CED1",   # ciano
    "SQUAD_6": "#7B2D8B",   # roxo escuro
    "SQUAD_7": "#CC99FF",   # lilás
    "SQUAD_8": "#C0C0C0",   # prata
}


def gerar_gantt(
    cenarios: list[tuple[str, list[dict]]],
    saida_html: Path,
    saida_json: Path,
) -> None:
    """
    Gera Gantt via px.timeline.
    - y_label = "Lake / Chave" (uma linha por história, igual ao gráfico de referência)
    - Ordem: por lake (LAKES_ORDEM) → chave
    - Dev: cor da squad; QA: azul escuro único
    - Hover completo: chave, título, squad, lake, fase, início, fim, duração, status
    """
    color_map = {sq.replace("_", " "): cor for sq, cor in CORES_SQUAD.items()}
    color_map["QA / Teste"] = COR_QA_UNICA

    # índice de ordenação por lake
    lake_idx = {lake: i for i, lake in enumerate(LAKES_ORDEM)}

    cenarios_json = []
    data_min_global = None
    data_max_global = None

    for nome_cenario, alocacoes in cenarios:
        df = pd.DataFrame(alocacoes)
        if df.empty:
            continue

        df["data_inicio_dt"] = pd.to_datetime(df["data_inicio"], format="%d/%m/%Y")
        df["data_fim_dt"]    = pd.to_datetime(df["data_fim"],    format="%d/%m/%Y") + timedelta(days=1)
        df["data_inicio_fmt"] = df["data_inicio"]
        df["data_fim_fmt"]    = df["data_fim"]

        dm = df["data_inicio_dt"].min()
        dx = pd.to_datetime(df["data_fim"], format="%d/%m/%Y").max()
        data_min_global = dm if data_min_global is None else min(data_min_global, dm)
        data_max_global = dx if data_max_global is None else max(data_max_global, dx)

        # Grupo de cor: squad que executa o Dev, "QA / Teste" para QA
        df["legenda_grupo"] = df.apply(
            lambda r: "QA / Teste" if r["fase"] == "QA" else r["squad"].replace("_", " "),
            axis=1,
        )

        # squad_hover: para Dev mostra squad executante (com "(reforço)" se diferente)
        def squad_hover(r):
            if r["fase"] == "QA":
                return r["squad"].replace("_", " ")
            sq = r["squad"].replace("_", " ")
            orig = r.get("squad_original", r["squad"])
            if orig and orig != r["squad"]:
                return f"{sq} (reforca {orig.replace('_',' ')})"
            return sq
        df["squad_hover"] = df.apply(squad_hover, axis=1)

        # y_label = "LAKE / BF3E4-XXXX"
        df["y_label"] = df["lake"].str.upper() + " / " + df["chave"]

        # Ordenação: lake (ordem canônica) → chave → fase (Dev antes QA)
        df["_lake_ord"] = df["lake"].str.upper().map(lake_idx).fillna(99)
        df["_fase_ord"] = df["fase"].map({"Dev": 0, "QA": 1})
        df = df.sort_values(["_lake_ord", "chave", "_fase_ord"]).reset_index(drop=True)

        # y_order: ordem única de y_labels (sem duplicatas, mantendo sequência)
        y_order = list(dict.fromkeys(df["y_label"].tolist()))

        fig = px.timeline(
            df,
            x_start="data_inicio_dt",
            x_end="data_fim_dt",
            y="y_label",
            color="legenda_grupo",
            color_discrete_map=color_map,
            custom_data=[
                "chave", "titulo", "squad_hover", "lake", "fase",
                "data_inicio_fmt", "data_fim_fmt",
                "duracao_dias", "status_atual", "recurso", "mediana_usada",
            ],
        )

        fig.update_traces(
            marker=dict(line=dict(color="rgba(0,0,0,0.18)", width=1)),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "<b>%{customdata[1]}</b><br>"
                "Squad: %{customdata[2]}<br>"
                "Lake: %{customdata[3]}<br>"
                "Fase: %{customdata[4]}<br>"
                "Recurso: %{customdata[9]}<br>"
                "Mediana usada: %{customdata[10]}<br>"
                "Início: %{customdata[5]}<br>"
                "Fim: %{customdata[6]}<br>"
                "Duração: %{customdata[7]} dias<br>"
                "Status atual: %{customdata[8]}"
                "<extra></extra>"
            ),
        )

        fig_json = fig.to_plotly_json()

        cenarios_json.append({
            "nome": nome_cenario,
            "fim_projeto": dx.strftime("%d/%m/%Y"),
            "y_labels": y_order,
            "height": max(500, len(y_order) * 24 + 200),
            "traces": fig_json["data"],
        })

    payload = {
        "titulo": "Prazo Estimado — Historias em Andamento",
        "x_range_min": data_min_global.strftime("%Y-%m-%d"),
        "x_range_max": (data_max_global + timedelta(days=5)).strftime("%Y-%m-%d"),
        "cenarios": cenarios_json,
    }

    saida_json.parent.mkdir(parents=True, exist_ok=True)
    saida_json.write_text(
        json.dumps(payload, ensure_ascii=False, cls=PlotlyJSONEncoder),
        encoding="utf-8",
    )

    nome_json = saida_json.name
    med_dev_fmt = f"{MEDIANA_GERAL_DEV:.2f}".replace(".", ",")
    med_qa_fmt  = f"{MEDIANA_GERAL_QA:.2f}".replace(".", ",")
    html = f"""<!DOCTYPE html>
<html lang="pt-br">
<head>
  <meta charset="utf-8"/>
  <title>Prazo Estimado — Historias</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    body {{ font-family: Arial, sans-serif; margin:0; background:#f6f6f8; }}
    .topbar {{ display:flex; gap:10px; align-items:flex-start; padding:8px 12px; flex-wrap:wrap; }}
    .card {{ background:#fff; border:1px solid #bdbdbd; border-radius:4px; padding:7px 11px; }}
    #cenario {{ min-width:300px; font-size:14px; }}
    #info {{ font-size:13px; line-height:1.7; }}
    #metodologia {{ font-size:12px; line-height:1.8; color:#333; }}
    #metodologia b {{ color:#111; }}
    #metodologia .badge {{
      display:inline-block; border-radius:3px; padding:1px 7px;
      font-size:11px; font-weight:bold; margin-right:4px; vertical-align:middle;
    }}
    .badge-dev {{ background:#4C9BE8; color:#fff; }}
    .badge-qa  {{ background:#1B3A6B; color:#fff; }}
    #chart {{ width:100%; }}
    #erro {{ color:#b00020; padding:8px 14px; display:none; }}
  </style>
</head>
<body>
  <div class="topbar">
    <div class="card">
      <label for="cenario"><b>Cenario</b></label><br/>
      <select id="cenario"></select>
    </div>
    <div class="card" id="info"></div>
    <div class="card" id="metodologia">
      <b>Metodologia</b><br/>
      <span class="badge badge-dev">DEV</span>
      Mediana geral: <b>{med_dev_fmt} dias corridos</b>
      &nbsp;&nbsp;|&nbsp;&nbsp;
      <span class="badge badge-qa">QA</span>
      Mediana geral: <b>{med_qa_fmt} dias corridos</b><br/>
      Dias corridos = dias de calend&aacute;rio (inclui fins de semana e feriados).<br/>
      Medianas calculadas sobre <b>262 hist&oacute;rias conclu&iacute;das</b> com ciclo Dev + QA completo.<br/>
      <b>Cen&aacute;rios A/B:</b> mediana geral para todos &nbsp;|&nbsp;
      <b>Cen&aacute;rios C/D:</b> mediana hist&oacute;rica por lake (COMERCIAL usa mediana geral).<br/>
      <b>A/C</b> = mediana completa a partir de hoje &nbsp;|&nbsp;
      <b>B/D</b> = desconta tempo j&aacute; decorrido no status atual.<br/>
      Recursos: <b>Dev</b> por squad (greedy) &nbsp;|&nbsp; <b>23 QAs cross-squad</b> (greedy compartilhado).
    </div>
  </div>
  <div id="erro"></div>
  <div id="chart"></div>

  <script>
    const dataUrl = "{nome_json}";
    const select  = document.getElementById("cenario");
    const info    = document.getElementById("info");
    const erro    = document.getElementById("erro");
    const chart   = document.getElementById("chart");

    function layout(payload, c) {{
      return {{
        title: {{ text: payload.titulo + " — " + c.nome,
                  x: 0.01, xanchor: "left", font: {{ size: 15, color: "#333" }} }},
        xaxis: {{
          type: "date",
          tickformat: "%d/%m/%Y",
          showgrid: true,
          gridwidth: 1,
          gridcolor: "rgba(180,180,180,0.25)",
          side: "top",
          range: [payload.x_range_min, payload.x_range_max],
        }},
        yaxis: {{
          autorange: "reversed",
          showgrid: false,
          tickfont: {{ size: 10 }},
          automargin: true,
          categoryorder: "array",
          categoryarray: c.y_labels,
        }},
        barmode: "overlay",
        hovermode: "closest",
        height: c.height,
        legend: {{
          title: {{ text: "Legenda" }},
          x: 0.995, y: 0.995,
          xanchor: "right", yanchor: "top",
          bgcolor: "rgba(255,255,255,0.95)",
          bordercolor: "rgba(0,0,0,0.25)",
          borderwidth: 1,
          font: {{ size: 11 }},
        }},
        margin: {{ l: 160, r: 20, t: 70, b: 30 }},
        plot_bgcolor: "rgba(245,245,245,1)",
        paper_bgcolor: "white",
        font: {{ family: "Arial, sans-serif", size: 11 }},
      }};
    }}

    async function init() {{
      try {{
        const resp = await fetch(dataUrl);
        if (!resp.ok) throw new Error("HTTP " + resp.status);
        const payload = await resp.json();

        payload.cenarios.forEach((c, i) => {{
          const opt = document.createElement("option");
          opt.value = i;
          opt.textContent = c.nome;
          select.appendChild(opt);
        }});

        function render(idx) {{
          const c = payload.cenarios[idx];
          info.innerHTML =
            "<b>Fim estimado:</b> " + c.fim_projeto +
            "<br/><b>Historias restantes:</b> " + c.y_labels.length;
          Plotly.react(chart, c.traces, layout(payload, c),
                       {{ responsive: true, displaylogo: false }});
        }}

        select.addEventListener("change", () => render(+select.value));
        render(0);
      }} catch(e) {{
        erro.style.display = "block";
        erro.innerHTML = "Erro ao carregar. Rode em servidor local.<br>" + e.message;
      }}
    }}
    init();
  </script>
</body>
</html>
"""
    saida_html.parent.mkdir(parents=True, exist_ok=True)
    saida_html.write_text(html, encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--entrada",       default="analises/status_historias_filtrado.csv")
    parser.add_argument("--medianas",      default="analises/01_extracao/tempo_fases_resumo.csv")
    parser.add_argument("--saida-aloc-a",  default="analises/03_otimizacao/prazo_historias_reais_alocacoes_A.csv")
    parser.add_argument("--saida-aloc-b",  default="analises/03_otimizacao/prazo_historias_reais_alocacoes_B.csv")
    parser.add_argument("--saida-html",    default="analises/04_visualizacoes/prazo_historias_reais.html")
    parser.add_argument("--saida-json",    default="analises/04_visualizacoes/prazo_historias_reais.json")
    args = parser.parse_args()

    med_dev, med_qa = carregar_medianas(Path(args.medianas))
    historias       = carregar_historias(Path(args.entrada))

    print(f"Historias a simular: {len(historias)}")
    print(f"Data de referencia : {HOJE.strftime('%d/%m/%Y')}")
    print()
    print("Medianas Dev por lake (cenarios C e D):")
    for lk, val in MEDIANA_DEV_POR_LAKE.items():
        fonte = "geral" if val == MEDIANA_GERAL_DEV else "propria"
        print(f"  {lk:<20} Dev={val:.2f}d ({fonte})  QA={MEDIANA_QA_POR_LAKE.get(lk, MEDIANA_GERAL_QA):.2f}d")
    print()

    # Cenários A e B — mediana geral para todos
    aloc_a = simular(historias, med_dev, med_qa, modo="A", data_inicio=HOJE)
    aloc_b = simular(historias, med_dev, med_qa, modo="B", data_inicio=HOJE)

    # Cenários C e D — mediana histórica por lake
    aloc_c = simular(historias, med_dev, med_qa, modo="C", data_inicio=HOJE,
                     med_dev_lake=MEDIANA_DEV_POR_LAKE, med_qa_lake=MEDIANA_QA_POR_LAKE)
    aloc_d = simular(historias, med_dev, med_qa, modo="D", data_inicio=HOJE,
                     med_dev_lake=MEDIANA_DEV_POR_LAKE, med_qa_lake=MEDIANA_QA_POR_LAKE)

    df_a = pd.DataFrame(aloc_a)
    df_b = pd.DataFrame(aloc_b)
    df_c = pd.DataFrame(aloc_c)
    df_d = pd.DataFrame(aloc_d)

    Path(args.saida_aloc_a).parent.mkdir(parents=True, exist_ok=True)
    df_a.to_csv(args.saida_aloc_a, index=False)
    df_b.to_csv(args.saida_aloc_b, index=False)
    df_c.to_csv(args.saida_aloc_a.replace("_A.csv", "_C.csv"), index=False)
    df_d.to_csv(args.saida_aloc_b.replace("_B.csv", "_D.csv"), index=False)

    # Fim do projeto por cenário
    fim_a = pd.to_datetime(df_a["data_fim"], format="%d/%m/%Y").max()
    fim_b = pd.to_datetime(df_b["data_fim"], format="%d/%m/%Y").max()
    fim_c = pd.to_datetime(df_c["data_fim"], format="%d/%m/%Y").max()
    fim_d = pd.to_datetime(df_d["data_fim"], format="%d/%m/%Y").max()
    print(f"Cenario A (mediana geral,   completa)       : fim {fim_a.strftime('%d/%m/%Y')}")
    print(f"Cenario B (mediana geral,   descontada)     : fim {fim_b.strftime('%d/%m/%Y')}")
    print(f"Cenario C (mediana p/lake,  completa)        : fim {fim_c.strftime('%d/%m/%Y')}")
    print(f"Cenario D (mediana p/lake,  descontada)      : fim {fim_d.strftime('%d/%m/%Y')}")

    gerar_gantt(
        [
            ("Cenario A — Mediana geral | completa a partir de hoje", aloc_a),
            ("Cenario B — Mediana geral | descontando tempo ja decorrido", aloc_b),
            ("Cenario C — Mediana por lake | completa a partir de hoje", aloc_c),
            ("Cenario D — Mediana por lake | descontando tempo ja decorrido", aloc_d),
        ],
        saida_html=Path(args.saida_html),
        saida_json=Path(args.saida_json),
    )

    print(f"\nHTML : {args.saida_html}")
    print(f"JSON : {args.saida_json}")


if __name__ == "__main__":
    main()
