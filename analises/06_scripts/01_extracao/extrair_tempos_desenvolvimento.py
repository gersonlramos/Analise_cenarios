import argparse
import csv
import re
from pathlib import Path
from typing import Dict, List, Optional


REGEX_CABECALHO_HISTORIA = re.compile(
    r"^\[(?P<lake>[A-Za-zÀ-ÿ0-9_ ]+?)[ \t]*(?:-|\s)[ \t]*(?P<numero>\d+)\][ \t]*(?P<titulo>.*?(?:TAMANHO|Tamanho)\s*:?[ \t]*[A-Z].*)$",
    re.MULTILINE,
)
REGEX_SECAO_ESTIMATIVA = re.compile(
    r"Estimativa de Esforço(?P<conteudo>.*?)(?:\n\s*Quantidade de Objetos|\Z)",
    re.IGNORECASE | re.DOTALL,
)
REGEX_ENGENHEIRO = re.compile(
    r"Engenheiro(?:\s+de\s+[A-Za-zÀ-ÿ]+)*\s*:\s*([0-9]+(?:[.,][0-9]+)?)\b",
    re.IGNORECASE,
)
REGEX_ANALISTA = re.compile(
    r"Analista(?:\s+de\s+[A-Za-zÀ-ÿ]+)*\s*:\s*([0-9]+(?:[.,][0-9]+)?)\b",
    re.IGNORECASE,
)


def normalizar_numero(valor: str) -> float:
    return float(valor.replace(",", ".").strip())


def extrair_secao_estimativa(bloco: str) -> str:
    match = REGEX_SECAO_ESTIMATIVA.search(bloco)
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
        titulo = match.group("titulo").strip()
        secao_estimativa = extrair_secao_estimativa(bloco)

        engenheiro_match = REGEX_ENGENHEIRO.search(secao_estimativa)
        analista_match = REGEX_ANALISTA.search(secao_estimativa)

        if not engenheiro_match:
            engenheiro_match = REGEX_ENGENHEIRO.search(bloco)
        if not analista_match:
            analista_match = REGEX_ANALISTA.search(bloco)

        engenheiro: Optional[float] = None
        analista: Optional[float] = None

        if engenheiro_match:
            engenheiro = normalizar_numero(engenheiro_match.group(1))

        if analista_match:
            analista = normalizar_numero(analista_match.group(1))

        historias.append(
            {
                "id_historia": f"[{match.group('lake')} - {match.group('numero')}]",
                "lake": match.group("lake"),
                "numero": int(match.group("numero")),
                "titulo": titulo,
                "engenheiro_dias": engenheiro,
                "analista_dias": analista,
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


def salvar_csv(registros: List[Dict[str, object]], caminho_saida: Path) -> None:
    campos = [
        "arquivo",
        "id_historia",
        "lake",
        "numero",
        "titulo",
        "engenheiro_dias",
        "analista_dias",
    ]

    with caminho_saida.open("w", encoding="utf-8", newline="") as arquivo_csv:
        writer = csv.DictWriter(arquivo_csv, fieldnames=campos)
        writer.writeheader()
        writer.writerows(registros)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extrai tempo de desenvolvimento de Engenheiro e Analista de histórias em arquivos .txt."
    )
    parser.add_argument(
        "--entidades",
        default="entidades",
        help="Pasta com os arquivos .txt das entidades (default: entidades)",
    )
    parser.add_argument(
        "--saida",
        default="analises/01_extracao/tempos_desenvolvimento_historias.csv",
        help="Arquivo CSV de saída (default: analises/01_extracao/tempos_desenvolvimento_historias.csv)",
    )

    args = parser.parse_args()

    pasta_entidades = Path(args.entidades)
    if not pasta_entidades.exists() or not pasta_entidades.is_dir():
        raise FileNotFoundError(f"Pasta de entidades não encontrada: {pasta_entidades}")

    registros = extrair_de_pasta(pasta_entidades)

    caminho_saida = Path(args.saida)
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)
    salvar_csv(registros, caminho_saida)

    # Sincronizar também a pasta 00_fontes usada pelo cálculo de cenários
    caminho_fontes = Path("analises/00_fontes/tempos_desenvolvimento_historias.csv")
    caminho_fontes.parent.mkdir(parents=True, exist_ok=True)
    salvar_csv(registros, caminho_fontes)

    total = len(registros)
    com_engenheiro = sum(1 for registro in registros if registro["engenheiro_dias"] is not None)
    com_analista = sum(1 for registro in registros if registro["analista_dias"] is not None)

    print(f"Histórias processadas: {total}")
    print(f"Com tempo de Engenheiro: {com_engenheiro}")
    print(f"Com tempo de Analista: {com_analista}")
    print(f"CSV gerado em: {caminho_saida}")
    print(f"CSV sincronizado em: {caminho_fontes}")


if __name__ == "__main__":
    main()
