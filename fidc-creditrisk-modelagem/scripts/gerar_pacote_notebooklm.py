"""Gera notebooklm_sources/: arquivos nos formatos que o NotebookLM aceita (md, csv, png).

O NotebookLM NÃO aceita .zip como fonte. Esta pasta é o que deve ser enviado (descompacte o zip do
repositório, abra notebooklm_sources/ e arraste os arquivos). Limite do plano gratuito: 50 fontes por notebook,
até 500 mil palavras ou 200 MB por arquivo.

Rode depois do pipeline:  python scripts/gerar_pacote_notebooklm.py
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DEST = RAIZ / "notebooklm_sources"
LIMITE_FONTES = 50

LEIA_ME = """# Leia primeiro: como usar as fontes deste notebook

Este notebook reúne o repositório `fidc-creditrisk-modelagem` (v0.2.0), do trabalho de Davi H. S. Amâncio (IFC Camboriú) sobre
risco de crédito em FIDCs de duplicatas. A pergunta central: quanto do deságio cobrado na compra de duplicatas paga o risco de crédito
e quanto sobra, e como a escolha do modelo (CreditRisk+, cópulas) muda a cauda de perdas e a subordinação necessária.

## Mapa dos arquivos

| Arquivo | Para que serve |
|---|---|
| 01_README.md | Resumo do projeto e tabelas de resultados (geradas pelo pipeline) |
| 02_METODOLOGIA.md | Fórmulas e hipóteses: CreditRisk+, Panjer, cópulas, cascata, decomposição da taxa |
| 03_MANIFESTO_DE_EVIDENCIAS.md | De onde vem cada número e como foi verificado |
| 04_FONTES_EXTERNAS.md | Fontes de mercado e referências, com classificação de confiabilidade |
| 05_CODIGO_FONTE_CONSOLIDADO.md | Todo o código Python (módulos, pipeline, scripts, testes) |
| 06 a 13 (csv) | Resultados: perdas por modelo, cotas, decomposição da taxa, efeito taxa x prazo, série de mercado, macro, calibração das cópulas, regra de múltiplos |
| 14_resultados_chave.md | Métricas de validação e subordinação mínima (JSON em bloco de código) |
| 15 a 20 (png) | Figuras de cauda, subordinação e validação, nos cenários base e estresse |

## Glossário

* **FIDC**: fundo de investimento em direitos creditórios. **Cedente**: quem vende a duplicata. **Sacado**: devedor da duplicata.
* **Deságio**: desconto sobre a face na compra do recebível. **PL**: patrimônio líquido (soma dos preços pagos).
* **EL** (perda esperada), **VaR** e **ES** (perda no quantil e média além dele). **LGD**: perda dado o default. **PD**: probabilidade de default.
* **Cota sênior / subordinada**: a subordinada absorve as primeiras perdas. **Excesso de spread**: deságio menos funding e custos do ciclo.
* **Capacidade de perda**: receita de deságio menos funding da sênior e custos, em % do PL. **Margem residual**: capacidade menos a EL do modelo.
* **CreditRisk+**: modelo atuarial de perdas (Poisson com mistura Gamma por setor); **Panjer**: recursão que calcula a distribuição exata.
* **Cópula gaussiana / t**: modelos de variável latente (família Merton/Vasicek) usados como comparativo.

## Regras de leitura (importante)

* Classes de resultado: **empírico** (dado de mercado, fonte única, não auditado), **hipotético** (carteira sintética e premissas),
  **estimado**, **calculado (analítico)** e **simulado**. Diga sempre a classe ao citar um número.
* A série de deságio é da Quick Soft (via imprensa), com cerca de 13 meses e sem metodologia pública. É a taxa paga pelo cedente, não retorno de FIDC.
* PMI é da S&P Global; ICE (Confiança Empresarial) é da FGV/IBRE. Aparecem só como contexto, ainda fora do modelo.
* A margem residual não é lucro nem alfa. A carteira de sacados é sintética.
"""

CSVS = [
    ("06_resumo_perdas.csv", "outputs/resumo_perdas.csv"),
    ("07_cotas_senior_subordinada.csv", "outputs/cotas.csv"),
    ("08_decomposicao_taxa.csv", "outputs/decomposicao_taxa.csv"),
    ("09_efeito_taxa_prazo.csv", "outputs/efeito_taxa_prazo.csv"),
    ("10_mercado_quicksoft.csv", "data/mercado_quicksoft.csv"),
    ("11_contexto_macro.csv", "data/contexto_macro.csv"),
    ("12_calibracao_copula.csv", "outputs/calibracao_copula.csv"),
    ("13_regra_multiplos_el.csv", "outputs/regra_multiplos_el.csv"),
]
DOCS = [
    ("01_README.md", "README.md"),
    ("02_METODOLOGIA.md", "docs/METODOLOGIA.md"),
    ("03_MANIFESTO_DE_EVIDENCIAS.md", "docs/MANIFESTO_DE_EVIDENCIAS.md"),
    ("04_FONTES_EXTERNAS.md", "docs/FONTES_EXTERNAS.md"),
]
FIGURAS = ["fig_cauda_base", "fig_cauda_estresse", "fig_subordinacao_base",
           "fig_subordinacao_estresse", "fig_validacao_base", "fig_validacao_estresse"]


def codigo_consolidado() -> str:
    arquivos = ([RAIZ / "pipeline_fidc_creditrisk.py", RAIZ / "config_snapshot.json"]
                + sorted((RAIZ / "src" / "fidc_risk").glob("*.py"))
                + sorted((RAIZ / "scripts").glob("*.py"))
                + sorted((RAIZ / "tests").glob("*.py")))
    partes = ["# Código-fonte consolidado (v0.2.0)\n\nCada seção é um arquivo do repositório.\n"]
    for a in arquivos:
        lang = "json" if a.suffix == ".json" else "python"
        partes.append(f"\n## {a.relative_to(RAIZ).as_posix()}\n\n```{lang}\n{a.read_text(encoding='utf-8').rstrip()}\n```\n")
    return "".join(partes)


def main() -> int:
    if DEST.exists():
        shutil.rmtree(DEST)
    DEST.mkdir()
    (DEST / "00_LEIA_ME_PRIMEIRO.md").write_text(LEIA_ME, encoding="utf-8")
    for novo, origem in DOCS + CSVS:
        shutil.copyfile(RAIZ / origem, DEST / novo)
    (DEST / "05_CODIGO_FONTE_CONSOLIDADO.md").write_text(codigo_consolidado(), encoding="utf-8")
    chave = json.loads((RAIZ / "outputs" / "resultados_chave.json").read_text(encoding="utf-8"))
    (DEST / "14_resultados_chave.md").write_text(
        "# Resultados-chave e validação (resultados_chave.json)\n\n```json\n"
        + json.dumps(chave, indent=2, ensure_ascii=False) + "\n```\n", encoding="utf-8")
    for i, f in enumerate(FIGURAS, start=15):
        shutil.copyfile(RAIZ / "figures" / f"{f}.png", DEST / f"{i}_{f}.png")

    arquivos = sorted(p for p in DEST.iterdir() if p.is_file())
    palavras = {p.name: len(p.read_text(encoding="utf-8").split()) for p in arquivos if p.suffix in (".md", ".csv")}
    maior = max(palavras.items(), key=lambda kv: kv[1])
    print(f"{len(arquivos)} arquivos em {DEST.relative_to(RAIZ)} (limite do plano gratuito: {LIMITE_FONTES} fontes por notebook)")
    print(f"maior arquivo de texto: {maior[0]} com {maior[1]:,} palavras (limite: 500.000)".replace(",", "."))
    if len(arquivos) > LIMITE_FONTES or maior[1] > 500_000:
        print("ERRO: pacote excede os limites do NotebookLM")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
