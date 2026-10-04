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
from fidc_risk.copula import calibrar_rho, calibrar_rho_t, simular_copula  # noqa: E402
from fidc_risk.lgd import lgd_economico, sorteador_beta  # noqa: E402
from fidc_risk.creditriskplus import (bandas, momentos_analiticos, pmf_perda,  # noqa: E402
                                      simular_crplus)
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


def _min_sub(vals, probs, est, grade, alvo):
    """Subordinação mínima com e sem excesso de spread para uma distribuição de perdas."""
    out = {}
    for usar_xs, nome in ((True, "com_xs"), (False, "sem_xs")):
        cv = curva_subordinacao(vals, probs, est, grade, usar_xs)
        out[nome] = menor_subordinacao(cv, alvo)
    return out


def _linha(cen, modelo, vals, probs, quantis, est, grade, alvo, **extra):
    r = resumo_distribuicao(vals, probs, quantis)
    ms = _min_sub(vals, probs, est, grade, alvo)
    r.update({"cenario": cen, "modelo": modelo, "sub_min_com_xs": ms["com_xs"],
              "sub_min_sem_xs": ms["sem_xs"]})
    r.update(extra)
    return r


def bloco_lgd(df, cfg, cen, i_cen, s2, est, calib, am_cr_det, am_g_det, args):
    """Sensibilidade da cauda e da subordinação à LGD (determinística e Beta).

    * LGD determinística: refaz bandas e recursão de Panjer (CreditRisk+ Gamma) para cada LGD.
    * LGD Beta (média = LGD da config): Monte Carlo do CreditRisk+ Gamma e da cópula gaussiana
      com sorteio de LGD por default; a linha de desvio 0 reaproveita o Monte Carlo principal.
    """
    (unidade, tol, teto, n_sims, chunk, quantis, grade, alvo, seed, nu) = args
    setor = df["setor_idx"].to_numpy()
    pdh = df["pd_horizonte"].to_numpy()
    face = df["face"].to_numpy()
    lgd0 = float(cfg["carteira"]["lgd"])
    linhas = []
    for lgd in cfg["lgd"]["grade"]:
        v, lam = bandas(face * lgd, pdh, unidade)
        pmf = pmf_perda(v, lam, setor, s2, unidade, tol, teto)
        vals = np.arange(len(pmf)) * unidade
        linhas.append(_linha(cen, "crplus_gamma", vals, pmf, quantis, est, grade, alvo,
                             lgd_media=lgd, lgd_desvio=0.0, metodo="panjer"))
    v0, lam0 = bandas(face * lgd0, pdh, unidade)
    unif = np.full(n_sims, 1.0 / n_sims)
    linhas.append(_linha(cen, "mc_crplus_gamma", am_cr_det, unif, quantis, est, grade, alvo,
                         lgd_media=lgd0, lgd_desvio=0.0, metodo="mc"))
    linhas.append(_linha(cen, "copula_gaussiana", am_g_det, unif, quantis, est, grade, alvo,
                         lgd_media=lgd0, lgd_desvio=0.0, metodo="mc"))
    for j, sd in enumerate(cfg["lgd"]["beta_desvios"], start=1):
        mult = sorteador_beta(lgd0, float(sd))
        am1 = simular_crplus(v0, lam0, setor, s2, unidade, n_sims,
                             np.random.default_rng([seed, i_cen, 20 + j, 1]), chunk, mult_sev=mult)
        am2 = simular_copula(pdh, face * lgd0, setor, calib, n_sims,
                             np.random.default_rng([seed, i_cen, 20 + j, 2]), "gaussiana", nu, chunk,
                             mult_sev=mult)
        for nome, am in (("mc_crplus_gamma", am1), ("copula_gaussiana", am2)):
            linhas.append(_linha(cen, nome, am, unif, quantis, est, grade, alvo,
                                 lgd_media=lgd0, lgd_desvio=float(sd), metodo="mc",
                                 el_erro_padrao=float(am.std(ddof=1) / np.sqrt(n_sims))))
    return linhas


def bloco_nu(df, cfg, cen, i_cen, s2, est, calib, am_t_main, args):
    """Sensibilidade à hipótese de cauda: cópula t com vários graus de liberdade.

    Mantém o ``rho`` de ativos calibrado na cópula gaussiana (como em ``copula_t``) e registra,
    para cada setor, se seria POSSÍVEL casar a correlação de default do CreditRisk+ com a
    cópula t (``calibrar_rho_t``): como o fator W é comum, há um piso de correlação em rho = 0.
    """
    (unidade, tol, teto, n_sims, chunk, quantis, grade, alvo, seed, nu_main) = args
    setor = df["setor_idx"].to_numpy()
    pdh = df["pd_horizonte"].to_numpy()
    perda_dd = df["perda_dado_default"].to_numpy()
    unif = np.full(n_sims, 1.0 / n_sims)
    cal, res = [], []
    for j, nu in enumerate(cfg["sensibilidade_nu"]["graus_liberdade"], start=1):
        for k, sec in enumerate(cfg["carteira"]["setores"]):
            p_med = float(pdh[setor == k].mean())
            rho_t, viavel, piso = calibrar_rho_t(p_med, float(s2[k]), float(nu))
            cal.append({"cenario": cen, "nu": nu, "setor": sec["nome"], "pd_media_ciclo": p_med,
                        "corr_default_alvo": p_med * s2[k] / (1 - p_med),
                        "piso_corr_default_t": piso, "viavel": viavel, "rho_t": rho_t,
                        "rho_gaussiana": float(calib[k])})
        if float(nu) == nu_main:
            am = am_t_main
        else:
            am = simular_copula(pdh, perda_dd, setor, calib, n_sims,
                                np.random.default_rng([seed, i_cen, 40 + j]), "t", float(nu), chunk)
        res.append(_linha(cen, f"copula_t_nu{nu}", am, unif, quantis, est, grade, alvo, nu=nu))
    return cal, res


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
    regras, chave = [], {}
    lgd_linhas, nu_cal, nu_res = [], [], []

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

        # --- sensibilidades (v0.2.0): LGD e hipótese de cauda ----------------------------
        args_blocos = (unidade, tol, teto, n_sims, chunk, quantis, grade,
                       sub_cfg["alvo_el_senior_ciclo"], seed, nu)
        lgd_linhas += bloco_lgd(df, cfg, nome_cen, i_cen, s2, est, calib, am_cr, am_g, args_blocos)
        cal_nu, res_nu = bloco_nu(df, cfg, nome_cen, i_cen, s2, est, calib, am_t, args_blocos)
        nu_cal += cal_nu
        nu_res += res_nu

        # regra de múltiplos da EL (prática de mercado) vs. subordinação mínima do modelo
        el_pct_pl = el_carteira / preco_total
        for k_mult in sub_cfg["multiplos_el"]:
            regras.append({"cenario": nome_cen, "multiplo": k_mult,
                           "subordinacao_exigida_pct_pl": k_mult * el_pct_pl})

        conv, incl = convergencia(am_cr, media_a)
        conv["cenario"] = nome_cen
        convs.append(conv)

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
    pd.DataFrame(lgd_linhas).to_csv(saida / "lgd_sensibilidade.csv", index=False)
    pd.DataFrame(nu_cal).to_csv(saida / "t_calibracao_nu.csv", index=False)
    pd.DataFrame(nu_res).to_csv(saida / "t_sensibilidade_nu.csv", index=False)
    ec = cfg["lgd"]["economico"]
    chave["_lgd_economico"] = {**ec, "lgd_implicita": lgd_economico(
        ec["taxa_recuperacao"], ec["lag_dias"], ec["taxa_desconto_anual"],
        ec["custo_cobranca"], h["dias_ano"]), "lgd_config": cfg["carteira"]["lgd"]}
    (saida / "resultados_chave.json").write_text(
        json.dumps(chave, indent=2, ensure_ascii=False), encoding="utf-8")
    (saida / "run_metadata.json").write_text(json.dumps({
        "versao": __version__, "config_sha256": cfg_hash, "seed": seed, "rapido": rapido,
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
        if nome.startswith("_"):
            continue
        print(f"[{nome}] EL={r['el_pct_face']:.4%} da face | KS(Panjer,MC)={r['ks_panjer_vs_mc']:.4f} "
              f"| inclinação={r['inclinacao_convergencia']:.3f}")
    print("OK")


if __name__ == "__main__":
    main()
