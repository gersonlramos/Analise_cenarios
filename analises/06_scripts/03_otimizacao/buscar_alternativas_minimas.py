import csv
import importlib.util
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List


ROOT = Path(__file__).resolve().parent
MOD_PATH = ROOT / "simular_prazo_squads_comercial_dividido.py"
SPEC = importlib.util.spec_from_file_location("sim_div", MOD_PATH)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)

ARQUIVO_TEMPOS = ROOT / "tempos_desenvolvimento_historias.csv"
SAIDA_CSV = ROOT / "alternativas_minimas_projeto.csv"


def max_date(*datas: date) -> date:
    return max(datas)


def fmt(valor: date) -> str:
    return MOD.formatar_data_br(valor)


def simulate_base_lakes(por_lake: Dict[str, List[Dict[str, object]]]):
    data_s1 = MOD.parse_data_br("09/03/2026")
    data_others = MOD.parse_data_br("01/04/2026")

    resumo_bmc_compras, _, fim_bmc_compras = MOD.simular_lakes_exclusivos("Squad 1", ["BMC", "COMPRAS"], por_lake, data_s1)
    fim_compras = max(MOD.parse_data_br(item["data_fim"]) for item in resumo_bmc_compras if item["lake"] == "COMPRAS")

    resumo_mopar, _, fim_mopar = MOD.simular_lakes_exclusivos("Squad 2", ["MOPAR"], por_lake, data_others)
    inicio_rh = MOD.proximo_dia_util(fim_mopar)

    resumo_cliente, _, fim_cliente = MOD.simular_lakes_exclusivos("Squad 3", ["CLIENTE"], por_lake, data_others)
    inicio_finance = MOD.proximo_dia_util(fim_cliente)
    resumo_finance, _, fim_finance = MOD.simular_lakes_exclusivos("Squad 3", ["FINANCE"], por_lake, inicio_finance)

    return {
        "data_s1": data_s1,
        "data_others": data_others,
        "fim_compras": fim_compras,
        "inicio_rh": inicio_rh,
        "fim_finance": fim_finance,
        "fim_cliente": fim_cliente,
    }


def finish_of_squad(resumo: List[Dict[str, object]], squad: str) -> date:
    datas = [MOD.parse_data_br(item["data_fim"]) for item in resumo if item["squad"] == squad]
    if not datas:
        raise RuntimeError(f"Sem resumo para {squad}")
    return max(datas)


def finish_of_combined(resumo: List[Dict[str, object]], lake: str) -> date:
    datas = [MOD.parse_data_br(item["data_fim"]) for item in resumo if item["lake"] == lake]
    if not datas:
        raise RuntimeError(f"Sem resumo para {lake}")
    return max(datas)


def simulate_comercial(mode: str, por_lake: Dict[str, List[Dict[str, object]]], base: Dict[str, object]):
    inicio_comercial_s1 = MOD.proximo_dia_util(base["fim_compras"])
    if mode == "split":
        resumo, _, _ = MOD.simular_lake_compartilhado(
            "COMERCIAL",
            por_lake["COMERCIAL"],
            [
                {"squad": "Squad 1", "data_inicio": fmt(inicio_comercial_s1), "engenheiros": 8, "analistas": 2},
                {"squad": "Squad 5", "data_inicio": fmt(base["data_others"]), "engenheiros": 8, "analistas": 2},
            ],
        )
        return {
            "mode": mode,
            "resumo": resumo,
            "fim_comercial": finish_of_combined(resumo, "COMERCIAL"),
            "livre_s1": finish_of_squad(resumo, "Squad 1"),
            "livre_s5": finish_of_squad(resumo, "Squad 5"),
        }
    if mode == "s5_only":
        resumo, _, fim = MOD.simular_lakes_exclusivos("Squad 5", ["COMERCIAL"], por_lake, base["data_others"])
        return {
            "mode": mode,
            "resumo": resumo,
            "fim_comercial": fim,
            "livre_s1": base["fim_compras"],
            "livre_s5": fim,
        }
    raise ValueError(mode)


def simulate_optional_help(target: str, por_lake: Dict[str, List[Dict[str, object]]], original_squad: str, original_start: date, helpers: List[Dict[str, object]]) -> date:
    participantes = [{"squad": original_squad, "data_inicio": fmt(original_start), "engenheiros": 8, "analistas": 2}]
    participantes.extend(helpers)
    resumo, _, fim = MOD.simular_lake_compartilhado(target, por_lake[target], participantes)
    return finish_of_combined(resumo, target)


def scenario_name(comercial_mode: str, s1_help: str, s5_help: str) -> str:
    return f"COMERCIAL={comercial_mode}; Squad1->{s1_help}; Squad5->{s5_help}"


def main() -> None:
    registros = MOD.ler_csv_historias(ARQUIVO_TEMPOS)
    por_lake = MOD.agrupar_historias_por_lake(registros)
    base = simulate_base_lakes(por_lake)

    resultados = []
    commercial_modes = ["split", "s5_only"]
    helps = ["none", "RH", "SUPPLY CHAIN"]

    for comercial_mode in commercial_modes:
        comercial = simulate_comercial(comercial_mode, por_lake, base)
        for s1_help in helps:
            for s5_help in helps:
                if s1_help != "none" and s5_help != "none" and s1_help == s5_help:
                    # allowed, both can help same lake
                    pass

                fim_rh = None
                fim_supply = None

                rh_helpers = []
                if s1_help == "RH":
                    rh_helpers.append({"squad": "Squad 1", "data_inicio": fmt(MOD.proximo_dia_util(comercial["livre_s1"])), "engenheiros": 8, "analistas": 2})
                if s5_help == "RH":
                    rh_helpers.append({"squad": "Squad 5", "data_inicio": fmt(MOD.proximo_dia_util(comercial["livre_s5"])), "engenheiros": 8, "analistas": 2})
                if rh_helpers:
                    fim_rh = simulate_optional_help("RH", por_lake, "Squad 2", base["inicio_rh"], rh_helpers)
                else:
                    resumo_rh, _, fim_rh = MOD.simular_lakes_exclusivos("Squad 2", ["RH"], por_lake, base["inicio_rh"])

                supply_helpers = []
                if s1_help == "SUPPLY CHAIN":
                    supply_helpers.append({"squad": "Squad 1", "data_inicio": fmt(MOD.proximo_dia_util(comercial["livre_s1"])), "engenheiros": 8, "analistas": 2})
                if s5_help == "SUPPLY CHAIN":
                    supply_helpers.append({"squad": "Squad 5", "data_inicio": fmt(MOD.proximo_dia_util(comercial["livre_s5"])), "engenheiros": 8, "analistas": 2})
                if supply_helpers:
                    fim_supply = simulate_optional_help("SUPPLY CHAIN", por_lake, "Squad 4", base["data_others"], supply_helpers)
                else:
                    resumo_supply, _, fim_supply = MOD.simular_lakes_exclusivos("Squad 4", ["SUPPLY CHAIN"], por_lake, base["data_others"])

                fim_projeto = max_date(comercial["fim_comercial"], fim_rh, fim_supply, base["fim_finance"])
                resultados.append(
                    {
                        "cenario": scenario_name(comercial_mode, s1_help, s5_help),
                        "fim_comercial": fmt(comercial["fim_comercial"]),
                        "fim_rh": fmt(fim_rh),
                        "fim_supply_chain": fmt(fim_supply),
                        "fim_finance": fmt(base["fim_finance"]),
                        "fim_projeto": fmt(fim_projeto),
                    }
                )

    resultados.sort(key=lambda item: datetime.strptime(item["fim_projeto"], "%d/%m/%Y"))

    with SAIDA_CSV.open("w", encoding="utf-8", newline="") as arquivo:
        writer = csv.DictWriter(
            arquivo,
            fieldnames=["cenario", "fim_comercial", "fim_rh", "fim_supply_chain", "fim_finance", "fim_projeto"],
        )
        writer.writeheader()
        writer.writerows(resultados)

    print(f"Alternativas geradas em: {SAIDA_CSV}")
    for item in resultados[:8]:
        print(f"- {item['cenario']} => projeto {item['fim_projeto']}")


if __name__ == "__main__":
    main()
