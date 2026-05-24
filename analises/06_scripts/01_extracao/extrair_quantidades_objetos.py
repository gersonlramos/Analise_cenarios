import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional


REGEX_CABECALHO_HISTORIA = re.compile(
    r"^\[(?P<lake>[A-Za-zÀ-ÿ0-9_ ]+?)[ \t]*(?:-|\s)[ \t]*(?P<numero>\d+)\][ \t]*(?P<titulo>.*?(?:TAMANHO|Tamanho)\s*:?[ \t]*[A-Z].*)$",
    re.MULTILINE,
)
REGEX_SECAO_OBJETOS = re.compile(
    r"Quantidade de Objetos(?P<conteudo>.*?)(?:\n\s*\[[A-Za-zÀ-ÿ0-9_ ]+[ \t]*(?:-|\s)[ \t]*\d+\]|\Z)",
    re.IGNORECASE | re.DOTALL,
)
REGEX_TABELAS = re.compile(r"Tabelas(?:\s+[A-Za-zÀ-ÿ_]+)?\s*:\s*(\d+)\b", re.IGNORECASE)
REGEX_VIEWS = re.compile(r"Views\s*:\s*(\d+)\b", re.IGNORECASE)


def extrair_secao_objetos(bloco: str) -> str:
    match = REGEX_SECAO_OBJETOS.search(bloco)
    if match:
        return match.group("conteudo")
    return bloco


def extrair_historias(texto: str) -> List[Dict[str, object]]:
    correspondencias = list(REGEX_CABECALHO_HISTORIA.finditer(texto))
    historias: List[Dict[str, object]] = []

    for indice, match in enumerate(correspondencias):
        inicio = match.start()
        fim = correspondencias[indice + 1].start() if indice + 1 < len(correspondencias) else len(texto)
        bloco = texto[inicio:fim]
        secao_objetos = extrair_secao_objetos(bloco)

        tabelas_match = REGEX_TABELAS.search(secao_objetos)
        views_match = REGEX_VIEWS.search(secao_objetos)

        tabelas: Optional[int] = int(tabelas_match.group(1)) if tabelas_match else None
        views: Optional[int] = int(views_match.group(1)) if views_match else None

        historias.append(
            {
                "id_historia": f"[{match.group('lake').strip()} - {match.group('numero')}]",
                "lake": match.group("lake").strip(),
                "numero": int(match.group("numero")),
                "titulo": match.group("titulo").strip(),
                "tabelas": tabelas,
                "views": views,
            }
        )

    return historias


def extrair_de_arquivo(caminho: Path) -> List[Dict[str, object]]:
    texto = caminho.read_text(encoding="utf-8", errors="replace")
    historias = extrair_historias(texto)
    for historia in historias:
        historia["arquivo"] = caminho.name
    return historias


def extrair_de_pasta(pasta_entidades: Path) -> List[Dict[str, object]]:
    registros: List[Dict[str, object]] = []
    for arquivo_txt in sorted(pasta_entidades.glob("*.txt"), key=lambda p: p.name.lower()):
        registros.extend(extrair_de_arquivo(arquivo_txt))
    return registros


def resumir_por_lake(registros: List[Dict[str, object]]) -> List[Dict[str, object]]:
    acumulado: Dict[str, Dict[str, object]] = defaultdict(lambda: {
        "lake": "",
        "historias": 0,
        "tabelas_total": 0,
        "views_total": 0,
        "historias_sem_tabelas": 0,
        "historias_sem_views": 0,
    })

    for registro in registros:
        lake = str(registro["lake"])
        item = acumulado[lake]
        item["lake"] = lake
        item["historias"] = int(item["historias"]) + 1

        if registro["tabelas"] is None:
            item["historias_sem_tabelas"] = int(item["historias_sem_tabelas"]) + 1
        else:
            item["tabelas_total"] = int(item["tabelas_total"]) + int(registro["tabelas"])

        if registro["views"] is None:
            item["historias_sem_views"] = int(item["historias_sem_views"]) + 1
        else:
            item["views_total"] = int(item["views_total"]) + int(registro["views"])

    return sorted(acumulado.values(), key=lambda item: str(item["lake"]).lower())


def salvar_csv(caminho: Path, linhas: List[Dict[str, object]], campos: List[str]) -> None:
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        writer = csv.DictWriter(arquivo, fieldnames=campos)
        writer.writeheader()
        writer.writerows(linhas)


def salvar_markdown(caminho: Path, resumo: List[Dict[str, object]]) -> None:
    linhas = [
        "# Quantidade de Tabelas e Views por Lake",
        "",
        "| Lake | Histórias | Tabelas Total | Views Total | Histórias sem Tabelas | Histórias sem Views |",
        "|---|---:|---:|---:|---:|---:|",
    ]

    for item in resumo:
        linhas.append(
            f"| {item['lake']} | {item['historias']} | {item['tabelas_total']} | {item['views_total']} | {item['historias_sem_tabelas']} | {item['historias_sem_views']} |"
        )

    caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extrai quantidades de Tabelas e Views das histórias dos arquivos de entidades.")
    parser.add_argument("--entidades", default="entidades", help="Pasta com os arquivos .txt das entidades")
    parser.add_argument("--saida-historias", default="analises/01_extracao/quantidades_objetos_historias.csv", help="CSV por história")
    parser.add_argument("--saida-lakes", default="analises/01_extracao/quantidades_objetos_lakes.csv", help="CSV resumido por lake")
    parser.add_argument("--saida-relatorio", default="analises/01_extracao/quantidades_objetos_lakes.md", help="Relatório markdown resumido por lake")
    args = parser.parse_args()

    registros = extrair_de_pasta(Path(args.entidades))
    resumo = resumir_por_lake(registros)

    salvar_csv(
        Path(args.saida_historias),
        registros,
        ["arquivo", "id_historia", "lake", "numero", "titulo", "tabelas", "views"],
    )
    salvar_csv(
        Path(args.saida_lakes),
        resumo,
        ["lake", "historias", "tabelas_total", "views_total", "historias_sem_tabelas", "historias_sem_views"],
    )
    salvar_markdown(Path(args.saida_relatorio), resumo)

    print(f"Histórias processadas: {len(registros)}")
    print(f"Resumo por lake: {args.saida_lakes}")
    print(f"Detalhe por história: {args.saida_historias}")
    print(f"Relatório: {args.saida_relatorio}")


if __name__ == "__main__":
    main()
