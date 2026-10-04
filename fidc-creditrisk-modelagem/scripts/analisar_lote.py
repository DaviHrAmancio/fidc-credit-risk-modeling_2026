"""Analisa um lote de duplicatas de um cedente e grava relatório + CSVs rastreáveis.

Uso:
    python scripts/analisar_lote.py templates/duplicatas_exemplo.csv
    python scripts/analisar_lote.py meu_lote.csv --nome cedente_x --desconto-mensal 0.03 --sims 100000

Saída em ``outputs_lote/<nome>/``: RELATORIO.md, sacados.csv, por_setor.csv, resumo_perdas.csv,
subordinacao_minima.csv, desagio.json, metadata.json (hash do arquivo de entrada e da config).
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from fidc_risk import __version__  # noqa: E402
from fidc_risk.lote import analisar_lote, ler_duplicatas, sha256_arquivo  # noqa: E402

pct = lambda x, n=2: f"{100 * x:.{n}f}%".replace(".", ",")
brl = lambda x: "R$ " + f"{x:,.0f}".replace(",", ".")


def relatorio_md(nome: str, res: dict, meta: dict) -> str:
    L = [f"# Relatório de risco do lote `{nome}`", "",
         "> **Natureza:** estimativa de modelo com premissas explícitas (ver `metadata.json` e "
         "`docs/METODOLOGIA.md`). Não é recomendação de compra nem parecer de rating.", "",
         f"- arquivo de entrada: `{meta['arquivo']}` (SHA-256 `{meta['sha256_entrada'][:16]}…`)",
         f"- config: `config_snapshot.json` (SHA-256 `{meta['sha256_config'][:16]}…`), versão {meta['versao']}",
         f"- seed {meta['seed']}, {format(meta['n_sims'], ',').replace(',', '.')} simulações (cópula), prazo médio ponderado "
         f"{res[0]['prazo_medio_ponderado_dias']:.0f} dias, deságio praticado "
         f"{pct(res[0]['desconto_mensal'])} a.m.", ""]
    c = res[0]["concentracao"]
    L += ["## Composição e concentração", "",
          f"- {c['n_duplicatas']} duplicatas, {c['n_sacados']} sacados, face {brl(res[0]['face_total'])}, "
          f"preço {brl(res[0]['preco_total'])}",
          f"- maior sacado {pct(c['maior_sacado_pct_face'])} da face; top 5 {pct(c['top5_pct_face'])}; "
          f"top 10 {pct(c['top10_pct_face'])}",
          f"- número efetivo de sacados (1/HHI): {c['n_efetivo_sacados']:.1f}".replace(".", ","), ""]
    for r in res:
        cen = r["cenario"]
        L += [f"## Cenário `{cen}`", "",
              f"**Perda esperada (EL):** {brl(r['el'])} = {pct(r['el_pct_face'], 3)} da face.", "",
              "| Modelo | EL | VaR 99% | VaR 99,9% | ES 99,9% |", "|---|---|---|---|---|"]
        for _, x in r["resumo"].iterrows():
            L.append(f"| {x['modelo']} | {pct(x['el_pct_face'], 3)} | {pct(x['var_0.99_pct_face'])} | "
                     f"{pct(x['var_0.999_pct_face'])} | {pct(x['es_0.999_pct_face'])} |")
        L += ["", "*(% da face; VaR e ES da perda de crédito do ciclo)*", "",
              "**Subordinação mínima** (EL da sênior ≤ alvo por ciclo, % do PL):", "",
              "| Modelo | com excesso de spread | sem excesso de spread |", "|---|---|---|"]
        sm = r["subordinacao_minima"].pivot(index="modelo", columns="leitura",
                                            values="subordinacao_minima")
        for modelo, x in sm.iterrows():
            L.append(f"| {modelo} | {pct(x['com_xs'], 1)} | {pct(x['sem_xs'], 1)} |")
        d = r["desagio"]
        L += ["", "**Deságio exigido no ciclo** (% do preço) para cobrir o risco:", "",
              "| Componente | % do preço |", "|---|---|"]
        for k in ("custo_senior", "retorno_sub", "despesas", "perda_esperada", "margem"):
            L.append(f"| {k} | {pct(d[k], 3)} |")
        L += [f"| **exigido (soma)** | **{pct(d['desagio_exigido_ciclo'], 3)}** |",
              f"| praticado | {pct(d['desagio_praticado_ciclo'], 3)} |",
              f"| folga (praticado − exigido) | {pct(d['folga_ciclo'], 3)} |", "",
              f"Equivale a {pct(d['taxa_mensal_exigida'])} a.m. exigido contra {pct(d['taxa_mensal_praticada'])} a.m. "
              "praticado.", ""]
    L += ["## O que este relatório NÃO cobre", "",
          "Coobrigação do cedente, diluição (devoluções/abatimentos), fraude e duplicidade de "
          "lastro, risco de performance do cedente, revolvência e calendário de dias úteis. "
          "PDs por rating e `sigma` dos setores são **premissas** da config, não estimativas.", ""]
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--nome", default=None)
    ap.add_argument("--config", default=str(RAIZ / "config_snapshot.json"))
    ap.add_argument("--desconto-mensal", type=float, default=None)
    ap.add_argument("--cenarios", nargs="+", default=["base", "estresse"])
    ap.add_argument("--sims", type=int, default=50_000)
    ap.add_argument("--saida", default=str(RAIZ / "outputs_lote"))
    a = ap.parse_args()

    cfg_path = Path(a.config)
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    nome = a.nome or Path(a.csv).stem
    try:
        dup = ler_duplicatas(a.csv, cfg)
    except ValueError as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return 2
    res = [analisar_lote(dup, cfg, c, a.desconto_mensal, a.sims) for c in a.cenarios]

    out = Path(a.saida) / nome
    out.mkdir(parents=True, exist_ok=True)
    pd.concat([r["sacados"].assign(cenario=r["cenario"]) for r in res]).to_csv(out / "sacados.csv", index=False)
    pd.concat([r["por_setor"].assign(cenario=r["cenario"]) for r in res]).to_csv(out / "por_setor.csv", index=False)
    pd.concat([r["resumo"] for r in res]).to_csv(out / "resumo_perdas.csv", index=False)
    pd.concat([r["subordinacao_minima"] for r in res]).to_csv(out / "subordinacao_minima.csv", index=False)
    pd.concat([r["curvas"] for r in res]).to_csv(out / "curvas_subordinacao.csv", index=False)
    (out / "desagio.json").write_text(json.dumps({r["cenario"]: r["desagio"] for r in res},
                                                 indent=2, ensure_ascii=False), encoding="utf-8")
    meta = {"versao": __version__, "arquivo": str(a.csv), "sha256_entrada": sha256_arquivo(a.csv),
            "sha256_config": sha256_arquivo(cfg_path), "seed": cfg["seed"], "n_sims": a.sims,
            "cenarios": a.cenarios, "python": platform.python_version(), "numpy": np.__version__,
            "pandas": pd.__version__}
    (out / "metadata.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "RELATORIO.md").write_text(relatorio_md(nome, res, meta), encoding="utf-8")
    for r in res:
        print(f"[{r['cenario']}] EL={r['el_pct_face']:.3%} da face | desagio exigido "
              f"{r['desagio']['desagio_exigido_ciclo']:.3%} vs praticado {r['desagio']['desagio_praticado_ciclo']:.3%}")
    print(f"OK -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
