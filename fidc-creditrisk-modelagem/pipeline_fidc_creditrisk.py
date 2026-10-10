"""Pipeline principal: carteira sintética -> CreditRisk+ vs cópulas -> cascata de cotas.

Uso:
    python pipeline_fidc_creditrisk.py            # execução completa
    python pipeline_fidc_creditrisk.py --rapido   # menos simulações (CI)

Saídas em ``outputs/`` (ver docs/MANIFESTO_DE_EVIDENCIAS.md).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import scipy

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "src"))

from fidc_risk import __version__  # noqa: E402
from fidc_risk.copula import calibrar_rho, simular_copula  # noqa: E402
from fidc_risk.creditriskplus import (bandas, momentos_analiticos, pmf_perda,  # noqa: E402
                                      simular_crplus)
from fidc_risk.mercado import (carregar_serie, decompor, el_pct_pl,  # noqa: E402
                               fator_face_sobre_preco, pd_anual_equilibrio)
from fidc_risk.metrics import curva_quantis, resumo_distribuicao  # noqa: E402
from fidc_risk.portfolio import aplicar_cenario, gerar_carteira, sigmas2_setores  # noqa: E402
from fidc_risk.waterfall import (Estrutura, curva_subordinacao,  # noqa: E402
                                 estatisticas_cotas, menor_subordinacao)

MODELOS = ["crplus_poisson", "crplus_gamma", "mc_crplus_gamma", "copula_gaussiana", "copula_t"]
NIVEIS_CURVA = 1.0 - np.logspace(-0.3, -3.7, 80)


def carregar_config(caminho: Path) -> tuple[dict, str]:
    bruto = caminho.read_bytes()
    return json.loads(bruto), hashlib.sha256(bruto).hexdigest()


def ks_contra_pmf(amostra: np.ndarray, pmf: np.ndarray, unidade: float) -> float:
    """Distância de Kolmogorov entre a ECDF da amostra (múltiplos da unidade) e a CDF da pmf."""
    n_un = np.rint(amostra / unidade).astype(int)
    n_un = np.minimum(n_un, len(pmf) - 1)
    freq = np.bincount(n_un, minlength=len(pmf)) / len(amostra)
    return float(np.max(np.abs(np.cumsum(freq) - np.cumsum(pmf))))


def convergencia(amostra: np.ndarray, el_analitica: float) -> tuple[pd.DataFrame, float]:
    """RMSE da média amostral por blocos de tamanho n contra a EL analítica; inclinação log-log."""
    N = len(amostra)
    tamanhos = np.unique(np.geomspace(max(100, N // 1000), N // 10, 6).astype(int))
    linhas = []
    for n in tamanhos:
        k = N // n
        medias = amostra[: k * n].reshape(k, n).mean(axis=1)
        linhas.append({"n": int(n), "blocos": int(k),
                       "rmse": float(np.sqrt(np.mean((medias - el_analitica) ** 2)))})
    df = pd.DataFrame(linhas)
    inclinacao = float(np.polyfit(np.log(df["n"]), np.log(df["rmse"]), 1)[0])
    return df, inclinacao


ROTULO_MODELO = {"crplus_poisson": "CreditRisk+ Poisson", "crplus_gamma": "CreditRisk+ Gamma (setores)",
                 "copula_gaussiana": "Cópula gaussiana", "copula_t": "Cópula t (ν = 5)"}
MODELOS_TABELA = list(ROTULO_MODELO)


def pct(x: float, casas: int = 2) -> str:
    return f"{100 * x:.{casas}f}".replace(".", ",")


def efeito_taxa_prazo(serie_ok: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Decompõe a variação da capacidade de perda ANUALIZADA entre meses consecutivos em efeito de
    taxa (deságio a.m.), efeito de prazo e interação. Independe da EL (e do cenário)."""
    e, dias_ano = cfg["estrutura"], cfg["horizonte"]["dias_ano"]

    def cap_anual(d: float, h: float) -> float:
        r = decompor(d, h, 0.0, e["cdi_anual"], e["spread_senior_anual"], e["despesas_anuais"],
                     e["cota_subordinada"], dias_ano)
        return r["capacidade_perda_anual"]

    linhas = []
    s = serie_ok.sort_values("mes").reset_index(drop=True)
    for i in range(1, len(s)):
        a, b = s.iloc[i - 1], s.iloc[i]
        if (pd.Period(b["mes"]) - pd.Period(a["mes"])).n != 1:
            continue
        d0, h0, d1, h1 = a["desagio_am"], a["prazo_medio_dias"], b["desagio_am"], b["prazo_medio_dias"]
        total = cap_anual(d1, h1) - cap_anual(d0, h0)
        taxa = cap_anual(d1, h0) - cap_anual(d0, h0)
        prazo = cap_anual(d0, h1) - cap_anual(d0, h0)
        linhas.append({"de": a["mes"], "para": b["mes"], "desagio_de": d0, "desagio_para": d1,
                       "prazo_de": h0, "prazo_para": h1,
                       "delta_capacidade_anual": total, "efeito_taxa": taxa,
                       "efeito_prazo": prazo, "interacao": total - taxa - prazo})
    return pd.DataFrame(linhas)


def gerar_tabelas(resumo: pd.DataFrame, chave: dict, decomp: pd.DataFrame, mes_ref: str,
                  efeito: pd.DataFrame) -> dict:
    """Tabelas em markdown usadas no README (verify_output confere que o README as contém)."""
    t = {}
    linhas = ["| Cenário | Modelo | EL | VaR 99% | VaR 99,9% | ES 99,9% |", "|---|---|---|---|---|---|"]
    for cen in chave:
        for m in MODELOS_TABELA:
            r = resumo[(resumo["cenario"] == cen) & (resumo["modelo"] == m)].iloc[0]
            f = r["face_total"]
            linhas.append(f"| {cen} | {ROTULO_MODELO[m]} | {pct(r['el'] / f, 3)} | {pct(r['var_0.99'] / f)} "
                          f"| {pct(r['var_0.999'] / f)} | {pct(r['es_0.999'] / f)} |")
    t["tabela_perdas"] = "\n".join(linhas)

    linhas = ["| Cenário | Modelo | com excesso de spread | sem excesso de spread |", "|---|---|---|---|"]
    for cen, r in chave.items():
        for m in MODELOS_TABELA:
            a = r["subordinacao_minima"][f"{m}|com_xs"]
            b = r["subordinacao_minima"][f"{m}|sem_xs"]
            linhas.append(f"| {cen} | {ROTULO_MODELO[m]} | {pct(a, 1)}% | {pct(b, 1)}% |")
    t["tabela_subordinacao"] = "\n".join(linhas)

    linhas = ["| Cenário | Mês | Deságio a.m. | Prazo (dias) | Receita de deságio | Funding sênior | Custos "
              "| **Capacidade de perda** | EL do modelo | Margem residual | EL / capacidade |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for _, d in decomp.iterrows():
        linhas.append(f"| {d['cenario']} | {d['mes']} | {pct(d['desagio_am'])}% | {d['prazo_medio_dias']:.2f}".replace(".", ",")
                      + f" | {pct(d['receita_desagio_ciclo'])}% | {pct(d['funding_senior_ciclo'])}% "
                        f"| {pct(d['custos_ciclo'])}% | **{pct(d['capacidade_perda_ciclo'])}%** "
                        f"| {pct(d['el_ciclo'])}% | {pct(d['margem_residual_ciclo'])}% "
                        f"| {pct(d['el_sobre_capacidade'], 1)}% |")
    t["tabela_decomposicao"] = "\n".join(linhas)

    ref = decomp[decomp["mes"] == mes_ref]
    linhas = ["| Cenário | Capacidade de perda por ano (% do PL) | EL do modelo por ano (% do PL) "
              "| PD anual de equilíbrio (homogênea) | PD anual média da carteira |", "|---|---|---|---|---|"]
    for _, d in ref.iterrows():
        linhas.append(f"| {d['cenario']} | {pct(d['capacidade_perda_anual'], 1)}% | {pct(d['el_anual'], 1)}% "
                      f"| {pct(d['pd_anual_equilibrio'], 1)}% | {pct(d['pd_anual_media_carteira'], 1)}% |")
    t["tabela_equilibrio"] = "\n".join(linhas)

    linhas = ["| Variação | Deságio a.m. | Prazo (dias) | Δ capacidade de perda anual (p.p. do PL) "
              "| efeito da taxa | efeito do prazo | interação |", "|---|---|---|---|---|---|---|"]
    for _, d in efeito.iterrows():
        pp = lambda x: ("0,00" if abs(round(100 * x, 2)) == 0 else f"{100 * x:+.2f}".replace(".", ","))  # noqa: E731
        linhas.append(f"| {d['de']} → {d['para']} | {pct(d['desagio_de'])}% → {pct(d['desagio_para'])}% "
                      f"| {d['prazo_de']:.2f} → {d['prazo_para']:.2f}".replace(".", ",")
                      + f" | {pp(d['delta_capacidade_anual'])} | {pp(d['efeito_taxa'])} "
                        f"| {pp(d['efeito_prazo'])} | {pp(d['interacao'])} |")
    t["tabela_efeito_taxa_prazo"] = "\n".join(linhas)
    return t


def executar(cfg: dict, cfg_hash: str, rapido: bool, saida: Path) -> dict:
    saida.mkdir(parents=True, exist_ok=True)
    seed = int(cfg["seed"])
    unidade = float(cfg["panjer"]["unidade"])
    tol = float(cfg["panjer"]["tol_massa"])
    teto = int(cfg["panjer"]["n_max_teto"])
    mc = cfg["monte_carlo"]
    n_sims = int(mc["n_sims_rapido"] if rapido else mc["n_sims"])
    chunk = int(mc["chunk"])
    quantis = cfg["quantis"]
    nu = float(cfg["copula"]["t_graus_liberdade"])
    sub_cfg = cfg["subordinacao"]
    grade = np.arange(sub_cfg["grade_min"], sub_cfg["grade_max"] + 1e-12, sub_cfg["grade_passo"])
    share_base = float(cfg["estrutura"]["cota_subordinada"])
    h = cfg["horizonte"]

    base = gerar_carteira(cfg, np.random.default_rng([seed, 0]))

    resumos, tranches, curvas, calibracoes, convs, quant_curvas = [], [], [], [], [], []
    regras, chave, decomp = [], {}, []
    serie = carregar_serie(RAIZ / cfg["mercado"]["serie"])
    serie_ok = serie.dropna(subset=["desagio_am", "prazo_medio_dias"])
    est_cfg = cfg["estrutura"]
    lgd = float(cfg["carteira"]["lgd"])

    for i_cen, (nome_cen, cen) in enumerate(cfg["cenarios"].items(), start=1):
        df = aplicar_cenario(base, cfg, cen)
        s2 = sigmas2_setores(cfg, cen)
        setor = df["setor_idx"].to_numpy()
        pdh = df["pd_horizonte"].to_numpy()
        perda_dd = df["perda_dado_default"].to_numpy()
        face_total = float(df["face"].sum())
        preco_total = float(df["preco"].sum())
        el_carteira = float(df["perda_esperada"].sum())

        df.to_csv(saida / f"carteira_{nome_cen}.csv", index=False)

        # --- CreditRisk+ (analítico) ---------------------------------------------------
        v, lam = bandas(perda_dd, pdh, unidade)
        media_a, var_a = momentos_analiticos(v, lam, setor, s2, unidade)
        pmf_p = pmf_perda(v, lam, setor, np.zeros_like(s2), unidade, tol, teto)
        pmf_g = pmf_perda(v, lam, setor, s2, unidade, tol, teto)
        n_grade = max(len(pmf_p), len(pmf_g))
        pmf_p = np.pad(pmf_p, (0, n_grade - len(pmf_p)))
        pmf_g = np.pad(pmf_g, (0, n_grade - len(pmf_g)))
        unidades = np.arange(n_grade)
        pd.DataFrame({"unidades": unidades, "perda": unidades * unidade,
                      "pmf_poisson": pmf_p, "pmf_gamma": pmf_g}
                     ).to_csv(saida / f"pmf_crplus_{nome_cen}.csv", index=False)
        valores_pmf = unidades * unidade

        # --- Monte Carlo ---------------------------------------------------------------
        am_cr = simular_crplus(v, lam, setor, s2, unidade, n_sims,
                               np.random.default_rng([seed, i_cen, 1]), chunk)

        calib = []
        for k, sec in enumerate(cfg["carteira"]["setores"]):
            m = setor == k
            p_med = float(pdh[m].mean())
            rho = calibrar_rho(p_med, float(s2[k]))
            calib.append(rho)
            calibracoes.append({"cenario": nome_cen, "setor": sec["nome"], "n_sacados": int(m.sum()),
                                "pd_media_ciclo": p_med, "sigma": float(np.sqrt(s2[k])),
                                "corr_default_alvo": p_med * s2[k] / (1 - p_med), "rho_ativos": rho})
        calib = np.array(calib)
        am_g = simular_copula(pdh, perda_dd, setor, calib, n_sims,
                              np.random.default_rng([seed, i_cen, 2]), "gaussiana", nu, chunk)
        am_t = simular_copula(pdh, perda_dd, setor, calib, n_sims,
                              np.random.default_rng([seed, i_cen, 3]), "t", nu, chunk)

        dist = {
            "crplus_poisson": (valores_pmf, pmf_p),
            "crplus_gamma": (valores_pmf, pmf_g),
            "mc_crplus_gamma": (am_cr, np.full(n_sims, 1.0 / n_sims)),
            "copula_gaussiana": (am_g, np.full(n_sims, 1.0 / n_sims)),
            "copula_t": (am_t, np.full(n_sims, 1.0 / n_sims)),
        }

        est = Estrutura(face_total=face_total, preco_total=preco_total,
                        cdi_anual=cfg["estrutura"]["cdi_anual"],
                        spread_senior_anual=cfg["estrutura"]["spread_senior_anual"],
                        despesas_anuais=cfg["estrutura"]["despesas_anuais"],
                        horizonte_dias=h["dias"], dias_ano=h["dias_ano"])

        min_sub = {}
        for modelo in MODELOS:
            vals, probs = dist[modelo]
            r = resumo_distribuicao(vals, probs, quantis)
            r.update({"cenario": nome_cen, "modelo": modelo, "face_total": face_total,
                      "preco_total": preco_total})
            resumos.append(r)
            for q, x in zip(NIVEIS_CURVA, curva_quantis(vals, probs, NIVEIS_CURVA)):
                quant_curvas.append({"cenario": nome_cen, "modelo": modelo, "q": q, "perda": x})
            for usar_xs in (True, False):
                t = estatisticas_cotas(vals, probs, est, share_base, usar_xs)
                t.update({"cenario": nome_cen, "modelo": modelo})
                tranches.append(t)
                cv = curva_subordinacao(vals, probs, est, grade, usar_xs)
                cv["cenario"], cv["modelo"] = nome_cen, modelo
                curvas.append(cv)
                min_sub[(modelo, usar_xs)] = menor_subordinacao(cv, sub_cfg["alvo_el_senior_ciclo"])

        # regra de múltiplos da EL (prática de mercado) vs. subordinação mínima do modelo
        el_sobre_pl = el_carteira / preco_total
        for k_mult in sub_cfg["multiplos_el"]:
            regras.append({"cenario": nome_cen, "multiplo": k_mult,
                           "subordinacao_exigida_pct_pl": k_mult * el_sobre_pl})

        conv, incl = convergencia(am_cr, media_a)
        conv["cenario"] = nome_cen
        convs.append(conv)

        # --- decomposição do deságio de mercado (Quick Soft) -------------------------------
        pd_media = float((df["face"] * df["pd_anual"]).sum() / df["face"].sum())
        for _, m in serie_ok.iterrows():
            el_pl = el_pct_pl(df, m["desagio_am"], m["prazo_medio_dias"], lgd, h["dias_ano"])
            d = decompor(m["desagio_am"], m["prazo_medio_dias"], el_pl, est_cfg["cdi_anual"],
                         est_cfg["spread_senior_anual"], est_cfg["despesas_anuais"], share_base,
                         h["dias_ano"])
            d.update({"cenario": nome_cen, "mes": m["mes"], "desagio_am": float(m["desagio_am"]),
                      "prazo_medio_dias": float(m["prazo_medio_dias"]),
                      "pd_anual_media_carteira": pd_media,
                      "pd_anual_equilibrio": pd_anual_equilibrio(
                          d["capacidade_perda_ciclo"],
                          fator_face_sobre_preco(m["desagio_am"], m["prazo_medio_dias"]),
                          lgd, m["prazo_medio_dias"], h["dias_ano"])})
            decomp.append(d)

        ks = ks_contra_pmf(am_cr, pmf_g, unidade)
        se_mc = float(am_cr.std(ddof=1) / np.sqrt(n_sims))
        chave[nome_cen] = {
            "n_sacados": int(len(df)),
            "face_total": face_total,
            "preco_total": preco_total,
            "desagio_total_pct_preco": (face_total - preco_total) / preco_total,
            "defaults_esperados_ciclo": float(pdh.sum()),
            "el_carteira": el_carteira,
            "el_pct_face": el_carteira / face_total,
            "unidade": unidade,
            "pmf_massa_poisson": float(pmf_p.sum()),
            "pmf_massa_gamma": float(pmf_g.sum()),
            "media_analitica": media_a,
            "var_analitica": var_a,
            "media_pmf_gamma": float(np.sum(valores_pmf * pmf_g)),
            "var_pmf_gamma": float(np.sum(pmf_g * (valores_pmf - np.sum(valores_pmf * pmf_g)) ** 2)),
            "mc_crplus_media": float(am_cr.mean()),
            "mc_crplus_erro_padrao": se_mc,
            "ks_panjer_vs_mc": ks,
            "ks_limite_dkw_alpha1e-3": float(np.sqrt(np.log(2 / 1e-3) / (2 * n_sims))),
            "inclinacao_convergencia": incl,
            "n_sims": n_sims,
            "subordinacao_minima": {
                f"{m}|{'com_xs' if xs else 'sem_xs'}": min_sub[(m, xs)]
                for m in MODELOS for xs in (True, False)},
            "xs_ciclo_pct_preco": est.excesso_spread(share_base) / preco_total,
        }

    pd.DataFrame(resumos).to_csv(saida / "resumo_perdas.csv", index=False)
    pd.DataFrame(tranches).to_csv(saida / "cotas.csv", index=False)
    pd.concat(curvas).to_csv(saida / "curvas_subordinacao.csv", index=False)
    pd.DataFrame(calibracoes).to_csv(saida / "calibracao_copula.csv", index=False)
    pd.concat(convs).to_csv(saida / "convergencia.csv", index=False)
    pd.DataFrame(quant_curvas).to_csv(saida / "curvas_quantis.csv", index=False)
    pd.DataFrame(regras).to_csv(saida / "regra_multiplos_el.csv", index=False)
    decomp_df = pd.DataFrame(decomp)
    colunas = ["cenario", "mes", "desagio_am", "prazo_medio_dias"] + [
        c for c in decomp_df.columns if c not in ("cenario", "mes", "desagio_am", "prazo_medio_dias")]
    decomp_df = decomp_df[colunas]
    decomp_df.to_csv(saida / "decomposicao_taxa.csv", index=False)
    resumo_df = pd.DataFrame(resumos)
    efeito_df = efeito_taxa_prazo(serie_ok, cfg)
    efeito_df.to_csv(saida / "efeito_taxa_prazo.csv", index=False)
    tabelas = gerar_tabelas(resumo_df, chave, decomp_df, cfg["mercado"]["mes_referencia"], efeito_df)
    (saida / "tabelas_readme.md").write_text(
        "\n\n".join(f"<!-- BEGIN:{k} -->\n{v}\n<!-- END:{k} -->" for k, v in tabelas.items()) + "\n",
        encoding="utf-8")
    (saida / "resultados_chave.json").write_text(
        json.dumps(chave, indent=2, ensure_ascii=False), encoding="utf-8")
    dados_hash = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in sorted((RAIZ / "data").glob("*.csv"))}
    (saida / "run_metadata.json").write_text(json.dumps({
        "versao": __version__, "config_sha256": cfg_hash, "dados_sha256": dados_hash,
        "seed": seed, "rapido": rapido,
        "n_sims": n_sims, "python": platform.python_version(), "numpy": np.__version__,
        "scipy": scipy.__version__, "pandas": pd.__version__,
    }, indent=2), encoding="utf-8")
    return chave


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rapido", action="store_true", help="usa n_sims_rapido (CI)")
    ap.add_argument("--config", default=str(RAIZ / "config_snapshot.json"))
    ap.add_argument("--saida", default=str(RAIZ / "outputs"))
    args = ap.parse_args()
    cfg, h = carregar_config(Path(args.config))
    chave = executar(cfg, h, args.rapido, Path(args.saida))
    for nome, r in chave.items():
        print(f"[{nome}] EL={r['el_pct_face']:.4%} da face | KS(Panjer,MC)={r['ks_panjer_vs_mc']:.4f} "
              f"| inclinação={r['inclinacao_convergencia']:.3f}")
    print("OK")


if __name__ == "__main__":
    main()
