import argparse
import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple


def parse_data_br(valor: str) -> datetime:
    return datetime.strptime(valor, "%d/%m/%Y")


def data_mermaid(valor: datetime) -> str:
    return valor.strftime("%Y-%m-%d")


def encurtar_titulo(titulo: str, limite: int = 70) -> str:
    texto = " ".join(titulo.split())
    texto = texto.replace(":", " -")
    texto = texto.replace(",", " ")
    texto = texto.replace(";", " ")
    texto = texto.replace("|", " ")
    if len(texto) <= limite:
        return texto
    return texto[: limite - 3].rstrip() + "..."


def normalizar_id_tarefa(valor: str) -> str:
    permitido = []
    for caractere in valor.lower():
        if caractere.isalnum() or caractere == "_":
            permitido.append(caractere)
        else:
            permitido.append("_")
    texto = "".join(permitido).strip("_")
    while "__" in texto:
        texto = texto.replace("__", "_")
    return texto or "tarefa"


def carregar_historias_agrupadas(caminho_csv: Path) -> Dict[str, Dict[str, List[Dict[str, object]]]]:
    agrupado: Dict[Tuple[str, str, str], Dict[str, object]] = {}

    with caminho_csv.open("r", encoding="utf-8", newline="") as arquivo:
        reader = csv.DictReader(arquivo)
        for linha in reader:
            chave = (linha["squad"], linha["lake"], linha["id_historia"])
            inicio = parse_data_br(linha["data_inicio"])
            fim = parse_data_br(linha["data_fim"])

            if chave not in agrupado:
                agrupado[chave] = {
                    "squad": linha["squad"],
                    "lake": linha["lake"],
                    "id_historia": linha["id_historia"],
                    "numero": int(linha["numero"]),
                    "titulo": linha["titulo"],
                    "inicio": inicio,
                    "fim": fim,
                }
            else:
                if inicio < agrupado[chave]["inicio"]:
                    agrupado[chave]["inicio"] = inicio
                if fim > agrupado[chave]["fim"]:
                    agrupado[chave]["fim"] = fim

    por_squad_lake: Dict[str, Dict[str, List[Dict[str, object]]]] = defaultdict(lambda: defaultdict(list))
    for item in agrupado.values():
        por_squad_lake[str(item["squad"])][str(item["lake"])].append(item)

    for squad in por_squad_lake:
        for lake in por_squad_lake[squad]:
            por_squad_lake[squad][lake].sort(key=lambda h: (h["numero"], h["id_historia"]))

    return dict(sorted(por_squad_lake.items(), key=lambda kv: kv[0]))


def gerar_mermaid_squad(squad: str, lakes: Dict[str, List[Dict[str, object]]]) -> str:
    linhas = [
        "```mermaid",
        "gantt",
        f"    title {squad} - Timeline granular por história",
        "    dateFormat  YYYY-MM-DD",
        "    axisFormat  %d/%m",
        "",
    ]

    for lake, historias in sorted(lakes.items(), key=lambda kv: kv[0]):
        linhas.append(f"    section {lake}")
        for historia in historias:
            id_hist = str(historia["id_historia"]).replace("[", "").replace("]", "")
            titulo_curto = encurtar_titulo(str(historia["titulo"]), limite=40)
            label = f"{id_hist}"
            inicio = data_mermaid(historia["inicio"])
            fim = data_mermaid(historia["fim"])
            task_id = normalizar_id_tarefa(f"{squad}_{lake}_{historia['numero']}")
            linhas.append(f"    {label} - {titulo_curto} : {task_id}, {inicio}, {fim}")
        linhas.append("")

    linhas.append("```")
    return "\n".join(linhas)


def gerar_markdown_completo(por_squad_lake: Dict[str, Dict[str, List[Dict[str, object]]]]) -> str:
    linhas = [
        "# Timeline granular por história",
        "",
        "Base: `analises/prazo_squads_dividido_alocacoes.csv`",
        "Regra: cada barra representa a história consolidada (início mínimo e fim máximo entre Engenheiro/Analista).",
        "",
    ]

    for squad, lakes in por_squad_lake.items():
        linhas.append(f"## {squad}")
        linhas.append("")
        linhas.append(gerar_mermaid_squad(squad, lakes))
        linhas.append("")

    return "\n".join(linhas).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera timeline Gantt granular por história a partir das alocações por squad.")
    parser.add_argument(
        "--entrada",
        default="analises/prazo_squads_dividido_alocacoes.csv",
        help="CSV de alocações por história",
    )
    parser.add_argument(
        "--saida",
        default="analises/timeline_historias_gantt.md",
        help="Markdown de saída com Gantt por squad",
    )
    args = parser.parse_args()

    por_squad_lake = carregar_historias_agrupadas(Path(args.entrada))
    markdown = gerar_markdown_completo(por_squad_lake)
    Path(args.saida).write_text(markdown, encoding="utf-8")

    total_historias = sum(len(historias) for lakes in por_squad_lake.values() for historias in lakes.values())
    print(f"Squads no timeline: {len(por_squad_lake)}")
    print(f"Histórias no timeline: {total_historias}")
    print(f"Arquivo gerado: {args.saida}")


if __name__ == "__main__":
    main()
