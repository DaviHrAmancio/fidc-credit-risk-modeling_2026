"""Verifica invariantes dos outputs gerados por pipeline_fidc_creditrisk.py.

Cada checagem é independente do pipeline: relê os CSVs e recalcula o que dá.
Sai com código 1 se alguma falhar.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
OUT = RAIZ / "outputs"

falhas = []


def checar(nome: str, ok: bool, detalhe: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {nome} {detalhe}")
    if not ok:
        falhas.append(nome)


def main() -> int:
    chave = json.loads((OUT / "resultados_chave.json").read_text(encoding="utf-8"))
    meta = json.loads((OUT / "run_metadata.json").read_text(encoding="utf-8"))
    cfg_hash = hashlib.sha256((RAIZ / "config_snapshot.json").read_bytes()).hexdigest()
    checar("config_snapshot.json corresponde à execução", cfg_hash == meta["config_sha256"])
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((RAIZ / "data").glob("*.csv"))}
    checar("arquivos em data/ correspondem à execução", hashes == meta["dados_sha256"])

    # --- decomposição do deságio de mercado ---------------------------------------------
    dec = pd.read_csv(OUT / "decomposicao_taxa.csv")
    ident = (dec["funding_senior_ciclo"] + dec["custos_ciclo"] + dec["el_ciclo"] + dec["margem_residual_ciclo"]
             - dec["receita_desagio_ciclo"]).abs().max()
    checar("decomposição: receita = funding + custos + EL + margem", ident < 1e-12, f"(erro máx {ident:.1e})")
    cap = (dec["capacidade_perda_ciclo"] - (dec["receita_desagio_ciclo"] - dec["funding_senior_ciclo"]
                                            - dec["custos_ciclo"])).abs().max()
    checar("decomposição: capacidade = receita - funding - custos", cap < 1e-12)
    pd_c = 1 - (1 - dec["pd_anual_equilibrio"]) ** (dec["prazo_medio_dias"] / 360)
    lgd = json.loads((RAIZ / "config_snapshot.json").read_text(encoding="utf-8"))["carteira"]["lgd"]
    fator = (1 + dec["desagio_am"]) ** (dec["prazo_medio_dias"] / 30)
    checar("PD de equilíbrio zera a margem (lgd x PD x face/preço = capacidade)",
           bool(np.allclose(lgd * pd_c * fator, dec["capacidade_perda_ciclo"], rtol=1e-9)))
    serie = pd.read_csv(RAIZ / "data" / "mercado_quicksoft.csv").dropna(subset=["desagio_am", "prazo_medio_dias"])
    checar("decomposição usa exatamente os meses da série (deságio e prazo publicados)",
           set(dec["mes"]) == set(serie["mes"].astype(str)))
    ef = pd.read_csv(OUT / "efeito_taxa_prazo.csv")
    checar("efeito taxa + prazo + interação = variação total",
           bool(np.allclose(ef["efeito_taxa"] + ef["efeito_prazo"] + ef["interacao"],
                            ef["delta_capacidade_anual"], atol=1e-12)))

    # --- README contém exatamente as tabelas geradas -----------------------------------
    padrao = re.compile(r"<!-- BEGIN:(\w+) -->\n(.*?)\n<!-- END:\1 -->", re.S)
    gerado = {m.group(1): m.group(2) for m in padrao.finditer((OUT / "tabelas_readme.md").read_text(encoding="utf-8"))}
    no_readme = {m.group(1): m.group(2) for m in padrao.finditer((RAIZ / "README.md").read_text(encoding="utf-8"))}
    checar("README contém todas as tabelas geradas", set(gerado) <= set(no_readme), f"(faltam {set(gerado) - set(no_readme)})")
    for k in gerado:
        checar(f"README: tabela '{k}' igual à gerada pelo pipeline", no_readme.get(k) == gerado[k])

    resumo = pd.read_csv(OUT / "resumo_perdas.csv")
    cotas = pd.read_csv(OUT / "cotas.csv")
    curvas = pd.read_csv(OUT / "curvas_subordinacao.csv")

    for cen, r in chave.items():
        carteira = pd.read_csv(OUT / f"carteira_{cen}.csv")
        pmf = pd.read_csv(OUT / f"pmf_crplus_{cen}.csv")
        el = carteira["perda_esperada"].sum()

        checar(f"{cen}: EL = soma(PD x face x LGD)", np.isclose(el, r["el_carteira"], rtol=1e-12))
        for col in ("pmf_poisson", "pmf_gamma"):
            checar(f"{cen}: massa de {col} ~ 1", abs(pmf[col].sum() - 1) < 1e-8,
                   f"(1-massa={1 - pmf[col].sum():.1e})")
            media = (pmf["perda"] * pmf[col]).sum()
            checar(f"{cen}: média de {col} = EL da carteira", np.isclose(media, el, rtol=1e-6),
                   f"({media:,.0f} vs {el:,.0f})")
        checar(f"{cen}: média e variância da pmf Gamma = fórmula fechada",
               np.isclose(r["media_pmf_gamma"], r["media_analitica"], rtol=1e-6)
               and np.isclose(r["var_pmf_gamma"], r["var_analitica"], rtol=1e-5))
        checar(f"{cen}: MC do CreditRisk+ com EL dentro de 4 erros-padrão",
               abs(r["mc_crplus_media"] - r["el_carteira"]) < 4 * r["mc_crplus_erro_padrao"])
        checar(f"{cen}: KS(Panjer, MC) abaixo do limite DKW",
               r["ks_panjer_vs_mc"] < r["ks_limite_dkw_alpha1e-3"],
               f"({r['ks_panjer_vs_mc']:.4f} < {r['ks_limite_dkw_alpha1e-3']:.4f})")

        s = resumo[(resumo["cenario"] == cen)].set_index("modelo")
        checar(f"{cen}: cauda Gamma >= Poisson (VaR 99,9%)",
               s.loc["crplus_gamma", "var_0.999"] >= s.loc["crplus_poisson", "var_0.999"])
        checar(f"{cen}: ES >= VaR em todos os modelos",
               bool(((s["es_0.99"] >= s["var_0.99"] - 1e-6) & (s["es_0.999"] >= s["var_0.999"] - 1e-6)).all()))

        c = cotas[cotas["cenario"] == cen]
        checar(f"{cen}: o excesso de spread só reduz a EL da sênior",
               bool((c[c["usar_xs"]].set_index("modelo")["el_senior"]
                     <= c[~c["usar_xs"]].set_index("modelo")["el_senior"] + 1e-6).all()))

        cv = curvas[(curvas["cenario"] == cen)]
        mono = all(g.sort_values("share_sub")["el_senior_taxa"].is_monotonic_decreasing
                   for _, g in cv.groupby(["modelo", "usar_xs"]))
        checar(f"{cen}: EL da sênior não cresce com a subordinação", mono)

    print()
    print("TODAS AS CHECAGENS PASSARAM" if not falhas else f"{len(falhas)} FALHA(S): {falhas}")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
