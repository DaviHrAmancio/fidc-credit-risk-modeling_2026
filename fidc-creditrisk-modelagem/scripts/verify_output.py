"""Verifica invariantes dos outputs gerados por pipeline_fidc_creditrisk.py.

Cada checagem é independente do pipeline: relê os CSVs e recalcula o que dá.
Sai com código 1 se alguma falhar.
"""
from __future__ import annotations

import hashlib
import json
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

    resumo = pd.read_csv(OUT / "resumo_perdas.csv")
    cotas = pd.read_csv(OUT / "cotas.csv")
    curvas = pd.read_csv(OUT / "curvas_subordinacao.csv")

    for cen, r in chave.items():
        if cen.startswith("_"):
            continue
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

    # ------------------------------------------------------------ v0.2.0: LGD e hipótese de cauda
    lgd = pd.read_csv(OUT / "lgd_sensibilidade.csv")
    tn = pd.read_csv(OUT / "t_sensibilidade_nu.csv")
    cal = pd.read_csv(OUT / "t_calibracao_nu.csv")
    for cen, r in chave.items():
        if cen.startswith("_"):
            continue
        face = r["face_total"]
        g = lgd[(lgd["cenario"] == cen) & (lgd["modelo"] == "crplus_gamma")].sort_values("lgd_media")
        checar(f"{cen}: EL/LGD constante na grade de LGD (EL linear)",
               np.allclose(g["el"] / g["lgd_media"], (g["el"] / g["lgd_media"]).iloc[0], rtol=2e-3))
        checar(f"{cen}: VaR 99,9% cresce com a LGD", g["var_0.999"].is_monotonic_increasing)
        s0 = resumo[(resumo["cenario"] == cen) & (resumo["modelo"] == "crplus_gamma")].iloc[0]
        g6 = g[np.isclose(g["lgd_media"], 0.6)].iloc[0]
        checar(f"{cen}: linha LGD=60% da sensibilidade = resultado principal (Panjer)",
               np.isclose(g6["var_0.999"], s0["var_0.999"], rtol=1e-9))
        b = lgd[(lgd["cenario"] == cen) & (lgd["lgd_desvio"] > 0)]
        checar(f"{cen}: LGD Beta preserva a EL (dentro de 5 erros-padrão)",
               bool((abs(b["el"] - r["el_carteira"]) < 5 * b["el_erro_padrao"]).all()))
        for m in ("mc_crplus_gamma", "copula_gaussiana"):
            e = lgd[(lgd["cenario"] == cen) & (lgd["modelo"] == m)].sort_values("lgd_desvio")
            # tolerância de 2% com 100 mil simulações; cresce com 1/sqrt(n) (ruído do MC na cauda)
            tol_es = 0.02 * max(1.0, (1.0e5 / meta["n_sims"]) ** 0.5)
            checar(f"{cen}: ES 99,9% não cai com a dispersão da LGD ({m})",
                   bool((np.diff(e["es_0.999"].to_numpy()) > -tol_es * e["es_0.999"].iloc[0]).all()),
                   f"(tol {tol_es:.1%}, n_sims={meta['n_sims']})")
        t = tn[tn["cenario"] == cen].sort_values("nu")
        checar(f"{cen}: VaR 99,9% da cópula t cai quando nu cresce", t["var_0.999"].is_monotonic_decreasing)
        t5 = t[t["nu"] == 5].iloc[0]
        ct = resumo[(resumo["cenario"] == cen) & (resumo["modelo"] == "copula_t")].iloc[0]
        checar(f"{cen}: linha nu=5 da sensibilidade = copula_t principal",
               np.isclose(t5["var_0.999"], ct["var_0.999"], rtol=1e-12))
        c5 = cal[(cal["cenario"] == cen) & (cal["nu"] == 5)]
        checar(f"{cen}: com nu=5 não existe rho que case a correlação de default (piso > alvo)",
               bool((~c5["viavel"]).all() and (c5["piso_corr_default_t"] > c5["corr_default_alvo"]).all()))
    ec = chave["_lgd_economico"]
    checar("LGD econômica implícita compatível com a LGD da config (±5 p.p.)",
           abs(ec["lgd_implicita"] - ec["lgd_config"]) < 0.05,
           f"({ec['lgd_implicita']:.3f} vs {ec['lgd_config']:.3f})")

    # ------------------------------------------------------------ v0.3.0: caso observado (se existir)
    caso = RAIZ / "outputs_caso" / "via_multicredito"
    if (caso / "metricas_por_classe.csv").exists():
        aud = pd.read_csv(caso / "auditoria_acumulado.csv")
        checar("caso: acumulado reportado pela fonte = recalculado dos retornos mensais (±0,02 pp)",
               bool((aud["max_abs_dif_pp"] < 0.02).all()), f"(máx {aud['max_abs_dif_pp'].max():.4f} pp)")
        met = pd.read_csv(caso / "metricas_por_classe.csv")
        checar("caso: PL das classes soma 100% do PL total", abs(met["pl_pct_do_total"].sum() - 1.0) < 2e-3)
        sub = pd.read_csv(caso / "subordinacao_mensal.csv")
        checar("caso: pct das classes soma 1 em todos os meses",
               bool(np.allclose(sub[[c for c in sub.columns if c.startswith("pct_")]].sum(axis=1), 1.0, atol=2e-3)))
        cv = pd.read_csv(caso / "curva_absorcao.csv")
        tot = cv[["perda_senior_pct_pl", "perda_mezanino_pct_pl", "perda_junior_pct_pl"]].sum(axis=1)
        checar("caso: cascata de 3 classes conserva a perda (soma = min(perda, PL))",
               bool(np.allclose(tot, np.minimum(cv["perda_carteira_pct_pl"], 1.0), atol=1e-12)))
        pon = pd.read_csv(caso / "ponte_modelo_por_classe.csv")
        car = pd.read_csv(caso / "ponte_modelo_carteira.csv").set_index("cenario")
        for cen, g in pon.groupby("cenario"):
            checar(f"caso {cen}: soma da EL das classes = EL da carteira (sem XS)",
                   bool(np.isclose(g["el_pct_pl"].sum(), car.loc[cen, "el_pct_pl"], rtol=1e-9, atol=1e-12)))
            e = g.set_index("classe")["el_pct_classe"]
            checar(f"caso {cen}: EL (% da classe) não cresce da júnior para a sênior",
                   bool(e["junior"] >= e["mezanino"] >= e["senior"]))
        base_pl = resumo[(resumo["cenario"] == "base") & (resumo["modelo"] == "crplus_gamma")]["preco_total"].iloc[0]
        checar("caso: EL da carteira (% do PL) bate com outputs/resumo_perdas.csv (base, CreditRisk+ Gamma)",
               bool(np.isclose(car.loc["base", "el_pct_pl"],
                               resumo[(resumo["cenario"] == "base") & (resumo["modelo"] == "crplus_gamma")]["el"].iloc[0] / base_pl,
                               rtol=1e-9)))

    print()
    print("TODAS AS CHECAGENS PASSARAM" if not falhas else f"{len(falhas)} FALHA(S): {falhas}")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
