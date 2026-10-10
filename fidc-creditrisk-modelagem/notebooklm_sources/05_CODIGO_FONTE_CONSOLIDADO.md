# Código-fonte consolidado (v0.2.0)

Cada seção é um arquivo do repositório.

## pipeline_fidc_creditrisk.py

```python
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
```

## config_snapshot.json

```json
{
  "versao": "0.2.0",
  "seed": 20261003,
  "carteira": {
    "n_sacados": 600,
    "exposicao_mediana": 120000,
    "exposicao_sigma_log": 0.9,
    "exposicao_max": 1500000,
    "ratings": {
      "A": {"peso": 0.35, "pd_anual": 0.006},
      "B": {"peso": 0.35, "pd_anual": 0.018},
      "C": {"peso": 0.20, "pd_anual": 0.045},
      "D": {"peso": 0.10, "pd_anual": 0.100}
    },
    "setores": [
      {"nome": "Varejo", "peso": 0.30, "sigma": 0.8},
      {"nome": "Industria", "peso": 0.30, "sigma": 0.7},
      {"nome": "Agro", "peso": 0.20, "sigma": 1.0},
      {"nome": "Servicos", "peso": 0.20, "sigma": 0.6}
    ],
    "lgd": 0.60
  },
  "horizonte": {"dias": 50.8, "dias_ano": 360},
  "precificacao": {
    "desconto_mensal": 0.0292,
    "prazo_dias": 50.8,
    "origem": "Quick Soft, setembro/2026 (ver data/mercado_quicksoft.csv)"
  },
  "mercado": {
    "serie": "data/mercado_quicksoft.csv",
    "macro": "data/contexto_macro.csv",
    "fontes": "data/fontes_mercado.csv",
    "mes_referencia": "2026-09",
    "selic_meta_anual": 0.1375,
    "cdi_menos_selic_meta": -0.001
  },
  "estrutura": {
    "cdi_anual": 0.1365,
    "spread_senior_anual": 0.03,
    "despesas_anuais": 0.02,
    "cota_subordinada": 0.20
  },
  "panjer": {"unidade": 10000, "tol_massa": 1e-10, "n_max_teto": 60000},
  "monte_carlo": {"n_sims": 100000, "n_sims_rapido": 10000, "chunk": 2000},
  "copula": {"t_graus_liberdade": 5},
  "subordinacao": {
    "alvo_el_senior_ciclo": 0.0001,
    "grade_min": 0.0,
    "grade_max": 0.5,
    "grade_passo": 0.005,
    "multiplos_el": [3, 4, 5]
  },
  "quantis": [0.95, 0.99, 0.999],
  "cenarios": {
    "base": {"mult_pd": 1.0, "mult_sigma": 1.0},
    "estresse": {"mult_pd": 3.0, "mult_sigma": 1.5}
  }
}
```

## src/fidc_risk/__init__.py

```python
"""Risco de crédito em FIDCs de duplicatas: CreditRisk+, cópulas e cascata de cotas."""

__version__ = "0.2.0"
```

## src/fidc_risk/copula.py

```python
"""Modelos de fator latente (Merton/Vasicek): cópula gaussiana e cópula t, por setor.

Cada setor k tem um fator sistêmico próprio e independente dos demais:
    X_i = sqrt(rho_k) * Z_k + sqrt(1 - rho_k) * eps_i,   default se X_i < c_i.
Na cópula t, X_i é dividido por sqrt(W/nu), com W ~ qui-quadrado(nu) comum a todos os
setores, o que gera dependência de cauda também ENTRE setores.

Para comparar com o CreditRisk+ em pé de igualdade, ``rho_k`` é calibrado por casamento de
correlação de default: no CreditRisk+ homogêneo, corr(1_i, 1_j) = p * sigma2 / (1 - p).
"""
from __future__ import annotations

import numpy as np
from numpy.polynomial.hermite_e import hermegauss
from scipy.optimize import brentq
from scipy.stats import norm, t as student_t

_NOS, _PESOS = hermegauss(160)
_PESOS = _PESOS / np.sqrt(2.0 * np.pi)


def correlacao_default_gaussiana(p: float, rho: float) -> float:
    """Correlação de default de um par homogêneo na cópula gaussiana de um fator."""
    c = norm.ppf(p)
    cond = norm.cdf((c - np.sqrt(rho) * _NOS) / np.sqrt(1.0 - rho))
    conjunta = float(np.sum(_PESOS * cond ** 2))
    return (conjunta - p * p) / (p * (1.0 - p))


def correlacao_default_alvo(p: float, sigma2: float) -> float:
    """Correlação de default implícita no CreditRisk+ (Gamma de variância sigma2)."""
    return p * sigma2 / (1.0 - p)


def calibrar_rho(p: float, sigma2: float) -> float:
    """Acha a correlação de ativos rho tal que a correlação de default case com o CreditRisk+."""
    alvo = correlacao_default_alvo(p, sigma2)
    if alvo <= 0.0:
        return 0.0
    f = lambda r: correlacao_default_gaussiana(p, r) - alvo
    return float(brentq(f, 1e-10, 0.999, xtol=1e-12))


def simular_copula(p, perda, setor_idx, rho_k, n_sims: int, rng: np.random.Generator,
                   tipo: str = "gaussiana", nu: float = 5.0, chunk: int = 2000) -> np.ndarray:
    """Monte Carlo da perda total (em moeda) com perda dado default determinística."""
    p = np.asarray(p, dtype=float)
    perda = np.asarray(perda, dtype=float)
    setor_idx = np.asarray(setor_idx)
    rho_k = np.asarray(rho_k, dtype=float)
    n, K = len(p), len(rho_k)
    if tipo == "gaussiana":
        limiar = norm.ppf(p)
    elif tipo == "t":
        limiar = student_t.ppf(p, df=nu)
    else:
        raise ValueError("tipo deve ser 'gaussiana' ou 't'")
    sr = np.sqrt(rho_k)[setor_idx]
    sq = np.sqrt(1.0 - rho_k)[setor_idx]

    out = np.empty(n_sims)
    for ini in range(0, n_sims, chunk):
        m = min(chunk, n_sims - ini)
        Z = rng.standard_normal((m, K))[:, setor_idx]
        E = rng.standard_normal((m, n))
        X = sr * Z + sq * E
        if tipo == "t":
            W = rng.chisquare(nu, size=(m, 1))
            X = X / np.sqrt(W / nu)
        out[ini:ini + m] = (X < limiar) @ perda
    return out


def vasicek_quantil_fracao_perda(p: float, rho: float, lgd: float, q: float) -> float:
    """Quantil q da fração de perda de uma carteira homogênea infinitamente granular (ASRF)."""
    return lgd * float(norm.cdf((norm.ppf(p) + np.sqrt(rho) * norm.ppf(q)) / np.sqrt(1.0 - rho)))
```

## src/fidc_risk/creditriskplus.py

```python
"""CreditRisk+ (Credit Suisse First Boston, 1997): bandas de exposição e recursão de Panjer.

Notação
-------
* ``v_i``  : perda dado default do sacado i, em múltiplos inteiros da unidade ``L`` (>= 1).
* ``lam_i``: intensidade de default do ciclo, ajustada para preservar a perda esperada
             (``lam_i * v_i * L = PD_i * perda_dado_default_i``).
* Setor k  : fator Gamma de média 1 e variância ``sigma2_k``. Cada sacado pertence a um só
             setor e os setores são independentes; ``sigma2_k = 0`` recai em Poisson puro.

Dado o setor, a perda é Poisson composto com mistura Gamma, ou seja, binomial negativa
composta, cuja f.g.p. é ``[(1-d)/(1-d*P(z))]^alpha`` com ``alpha = 1/sigma2``,
``d = sigma2*mu/(1+sigma2*mu)`` e ``P(z) = sum_v q_v z^v``. Isso pertence à classe (a, b, 0)
de Panjer com ``a = d`` e ``b = (alpha-1)*d``; no caso Poisson, ``a = 0`` e ``b = mu``.
"""
from __future__ import annotations

import numpy as np


def bandas(perda_dado_default, pd_h, unidade: float):
    """Arredonda perdas para múltiplos da unidade e ajusta a intensidade (preserva a EL)."""
    perda = np.asarray(perda_dado_default, dtype=float)
    pd_h = np.asarray(pd_h, dtype=float)
    v = np.maximum(1, np.rint(perda / unidade)).astype(int)
    lam = pd_h * perda / (v * unidade)
    return v, lam


def momentos_analiticos(v, lam, setor_idx, sigmas2, unidade: float):
    """Média e variância exatas da perda total do modelo (em moeda)."""
    v = np.asarray(v)
    lam = np.asarray(lam)
    setor_idx = np.asarray(setor_idx)
    media = unidade * float(np.sum(lam * v))
    var = unidade ** 2 * float(np.sum(lam * v.astype(float) ** 2))
    for k, s2 in enumerate(sigmas2):
        m = setor_idx == k
        el_k = unidade * float(np.sum(lam[m] * v[m]))
        var += s2 * el_k ** 2
    return media, var


def _panjer(a: float, b: float, f0: float, q: np.ndarray, n_max: int) -> np.ndarray:
    """Recursão de Panjer para soma composta: f(n) = sum_{v=1}^{n} (a + b v/n) q_v f(n-v)."""
    vmax = len(q) - 1
    f = np.zeros(n_max + 1)
    f[0] = f0
    for n in range(1, n_max + 1):
        m = min(n, vmax)
        v = np.arange(1, m + 1)
        f[n] = np.sum((a + b * v / n) * q[1:m + 1] * f[n - v])
    return f


def _pmf_setor(v, lam, sigma2: float, n_max: int) -> np.ndarray:
    mu = float(lam.sum())
    q = np.bincount(v, weights=lam, minlength=int(v.max()) + 1) / mu
    q[0] = 0.0
    if sigma2 <= 0.0:
        a, b, f0 = 0.0, mu, np.exp(-mu)
    else:
        alpha = 1.0 / sigma2
        delta = sigma2 * mu / (1.0 + sigma2 * mu)
        a, b, f0 = delta, (alpha - 1.0) * delta, (1.0 - delta) ** alpha
    if f0 < 1e-300:
        raise ValueError("f(0) sofreu underflow: reduza a carteira ou aumente a unidade.")
    return _panjer(a, b, f0, q, n_max)


def pmf_perda(v, lam, setor_idx, sigmas2, unidade: float,
              tol: float = 1e-10, n_max_teto: int = 60000) -> np.ndarray:
    """Distribuição da perda total em unidades (índice n = perda de n*unidade).

    Calcula a pmf de cada setor por Panjer e convolui (setores independentes). O
    comprimento é dobrado até que a massa truncada fique abaixo de ``tol``.
    """
    v = np.asarray(v)
    lam = np.asarray(lam)
    setor_idx = np.asarray(setor_idx)
    media, var = momentos_analiticos(v, lam, setor_idx, sigmas2, unidade)
    n = int(np.ceil((media + 12.0 * np.sqrt(var)) / unidade)) + 10

    while True:
        pmf = None
        for k, s2 in enumerate(sigmas2):
            m = setor_idx == k
            if not m.any():
                continue
            f = _pmf_setor(v[m], lam[m], float(s2), n)
            pmf = f if pmf is None else np.convolve(pmf, f)[:n + 1]
        if 1.0 - pmf.sum() <= tol or n >= n_max_teto:
            return pmf
        n = min(2 * n, n_max_teto)


def simular_crplus(v, lam, setor_idx, sigmas2, unidade: float, n_sims: int,
                   rng: np.random.Generator, chunk: int = 2000) -> np.ndarray:
    """Monte Carlo do MESMO modelo (Gamma-Poisson) para validar a recursão de Panjer."""
    v = np.asarray(v)
    lam = np.asarray(lam)
    setor_idx = np.asarray(setor_idx)
    sev = v * unidade
    K = len(sigmas2)
    out = np.empty(n_sims)
    for ini in range(0, n_sims, chunk):
        m = min(chunk, n_sims - ini)
        g = np.ones((m, K))
        for k, s2 in enumerate(sigmas2):
            if s2 > 0.0:
                g[:, k] = rng.gamma(shape=1.0 / s2, scale=s2, size=m)
        contagem = rng.poisson(g[:, setor_idx] * lam)
        out[ini:ini + m] = contagem @ sev
    return out
```

## src/fidc_risk/mercado.py

```python
"""Dados de mercado (Quick Soft) e decomposição da taxa de deságio.

Decompõe, POR CICLO e em % do PL, a receita de deságio em

    deságio = funding da sênior + custos + perda esperada (EL) + margem residual

que é a fórmula discutida no projeto ("taxa = custo do dinheiro + perda esperada + custos + margem"),
agora com o deságio e o prazo médio publicados pela Quick Soft.

ATENÇÃO sobre o que a série de mercado representa: é a taxa média das operações processadas na
plataforma da Quick Soft (fundos, securitizadoras, factorings), paga pelo CEDENTE. Não é o retorno
líquido de um FIDC. A "margem residual" calculada aqui absorve tudo o que o modelo ainda não
cobre: diluição, risco do cedente, custos operacionais e tributos adicionais, caixa ocioso e lucro.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def carregar_serie(caminho: Path) -> pd.DataFrame:
    df = pd.read_csv(caminho)
    df["mes"] = df["mes"].astype(str)
    return df


def fator_face_sobre_preco(desagio_am: float, prazo_dias: float) -> float:
    """face / preço de compra para um deságio composto de ``desagio_am`` ao mês."""
    return (1.0 + desagio_am) ** (prazo_dias / 30.0)


def desagio_sobre_face(desagio_am: float, prazo_dias: float) -> float:
    """Desconto como fração da FACE (o que o cedente deixa de receber por 1 de face)."""
    return 1.0 - 1.0 / fator_face_sobre_preco(desagio_am, prazo_dias)


def taxa_ciclo(taxa_anual: float, prazo_dias: float, dias_ano: int = 360) -> float:
    return (1.0 + taxa_anual) ** (prazo_dias / dias_ano) - 1.0


def el_pct_pl(carteira: pd.DataFrame, desagio_am: float, prazo_dias: float,
              lgd: float, dias_ano: int = 360) -> float:
    """EL do ciclo em % do PL, recalculada para o prazo e o deságio informados.

    Usa as faces relativas da carteira sintética e a PD anual de cada sacado convertida
    para o prazo dado. PL = face_total / (face/preço).
    """
    w = carteira["face"].to_numpy()
    w = w / w.sum()
    pd_h = 1.0 - (1.0 - carteira["pd_anual"].to_numpy()) ** (prazo_dias / dias_ano)
    el_sobre_face = lgd * float(np.sum(w * pd_h))
    return el_sobre_face * fator_face_sobre_preco(desagio_am, prazo_dias)


def decompor(desagio_am: float, prazo_dias: float, el_pl: float, cdi_anual: float,
             spread_senior_anual: float, despesas_anuais: float, share_sub: float,
             dias_ano: int = 360) -> dict:
    """Decomposição do ciclo em % do PL. Vale: receita = funding + custos + el + margem."""
    receita = fator_face_sobre_preco(desagio_am, prazo_dias) - 1.0
    funding = (1.0 - share_sub) * taxa_ciclo(cdi_anual + spread_senior_anual, prazo_dias, dias_ano)
    custos = taxa_ciclo(despesas_anuais, prazo_dias, dias_ano)
    capacidade = receita - funding - custos            # o que sobra para pagar perdas + margem
    margem = capacidade - el_pl
    ciclos_ano = dias_ano / prazo_dias
    return {
        "receita_desagio_ciclo": receita,
        "funding_senior_ciclo": funding,
        "custos_ciclo": custos,
        "capacidade_perda_ciclo": capacidade,
        "el_ciclo": el_pl,
        "margem_residual_ciclo": margem,
        "ciclos_por_ano": ciclos_ano,
        "capacidade_perda_anual": capacidade * ciclos_ano,
        "el_anual": el_pl * ciclos_ano,
        "margem_residual_anual": margem * ciclos_ano,
        "el_sobre_capacidade": el_pl / capacidade if capacidade > 0 else np.nan,
        "retorno_sub_ciclo_antes_inesperada": margem / share_sub if share_sub > 0 else np.nan,
    }


def pd_anual_equilibrio(capacidade_ciclo_pl: float, fator_face_preco: float, lgd: float,
                        prazo_dias: float, dias_ano: int = 360) -> float:
    """PD anual MÉDIA (homogênea) para a qual a margem residual é zero.

    EL/PL = lgd * pd_ciclo * (face/preço)  =>  pd_ciclo = capacidade / (lgd * face/preço).
    """
    pd_ciclo = capacidade_ciclo_pl / (lgd * fator_face_preco)
    pd_ciclo = float(np.clip(pd_ciclo, 0.0, 0.999999))
    return 1.0 - (1.0 - pd_ciclo) ** (dias_ano / prazo_dias)
```

## src/fidc_risk/metrics.py

```python
"""Estatísticas de uma distribuição de perdas, discreta (pmf) ou amostral (Monte Carlo)."""
from __future__ import annotations

import numpy as np


def _ordenar(valores, probs):
    valores = np.asarray(valores, dtype=float)
    probs = np.asarray(probs, dtype=float)
    ordem = np.argsort(valores, kind="stable")
    v = valores[ordem]
    p = probs[ordem]
    return v, p / p.sum()


def resumo_distribuicao(valores, probs, quantis) -> dict:
    """Média, desvio, VaR e ES nos quantis pedidos.

    ES_q = (1/(1-q)) * [ sum_{v_j > VaR} v_j p_j + VaR * (F(VaR) - q) ], válido para
    distribuições discretas.
    """
    v, p = _ordenar(valores, probs)
    media = float(np.sum(v * p))
    desvio = float(np.sqrt(np.sum(p * (v - media) ** 2)))
    cdf = np.cumsum(p)
    res = {"el": media, "desvio": desvio}
    for q in quantis:
        i = int(min(np.searchsorted(cdf, q - 1e-12), len(v) - 1))
        var = float(v[i])
        cauda = float(np.sum(v[i + 1:] * p[i + 1:]) + var * (cdf[i] - q))
        res[f"var_{q:g}"] = var
        res[f"es_{q:g}"] = cauda / (1.0 - q)
    return res


def curva_quantis(valores, probs, niveis) -> np.ndarray:
    """VaR em uma grade de níveis (para figuras de cauda)."""
    v, p = _ordenar(valores, probs)
    cdf = np.cumsum(p)
    idx = np.minimum(np.searchsorted(cdf, np.asarray(niveis) - 1e-12), len(v) - 1)
    return v[idx]
```

## src/fidc_risk/portfolio.py

```python
"""Carteira sintética de duplicatas, agregadas por sacado.

Todos os dados deste módulo são HIPOTÉTICOS: a carteira é gerada por sorteio
a partir dos parâmetros de ``config_snapshot.json``. Nenhuma informação de
fundo real é usada aqui.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def pd_horizonte(pd_anual, dias: int, dias_ano: int):
    """Converte PD anual em PD do horizonte (ciclo), assumindo taxa de falha constante."""
    pd_anual = np.asarray(pd_anual, dtype=float)
    return 1.0 - (1.0 - pd_anual) ** (dias / dias_ano)


def gerar_carteira(cfg: dict, rng: np.random.Generator) -> pd.DataFrame:
    """Sorteia sacados com face lognormal (truncada), rating e setor independentes."""
    c = cfg["carteira"]
    n = int(c["n_sacados"])

    face = rng.lognormal(mean=np.log(c["exposicao_mediana"]),
                         sigma=c["exposicao_sigma_log"], size=n)
    face = np.minimum(face, c["exposicao_max"])

    nomes_r = list(c["ratings"])
    pesos_r = np.array([c["ratings"][r]["peso"] for r in nomes_r], dtype=float)
    rating = rng.choice(nomes_r, size=n, p=pesos_r / pesos_r.sum())

    nomes_s = [s["nome"] for s in c["setores"]]
    pesos_s = np.array([s["peso"] for s in c["setores"]], dtype=float)
    setor_idx = rng.choice(len(nomes_s), size=n, p=pesos_s / pesos_s.sum())

    df = pd.DataFrame({
        "sacado_id": np.arange(n),
        "face": face,
        "rating": rating,
        "setor_idx": setor_idx,
        "setor": [nomes_s[i] for i in setor_idx],
    })
    df["pd_anual_base"] = df["rating"].map(lambda r: c["ratings"][r]["pd_anual"])
    return df


def aplicar_cenario(df: pd.DataFrame, cfg: dict, cenario: dict) -> pd.DataFrame:
    """Aplica multiplicador de PD e calcula PD do ciclo, perda dado default e preço de compra."""
    h = cfg["horizonte"]
    out = df.copy()
    out["pd_anual"] = np.clip(out["pd_anual_base"] * cenario["mult_pd"], 0.0, 0.95)
    out["pd_horizonte"] = pd_horizonte(out["pd_anual"], h["dias"], h["dias_ano"])
    out["lgd"] = cfg["carteira"]["lgd"]
    out["perda_dado_default"] = out["face"] * out["lgd"]
    out["perda_esperada"] = out["pd_horizonte"] * out["perda_dado_default"]

    p = cfg["precificacao"]
    out["preco"] = out["face"] / (1.0 + p["desconto_mensal"]) ** (p["prazo_dias"] / 30.0)
    return out


def sigmas2_setores(cfg: dict, cenario: dict) -> np.ndarray:
    """Variância do fator Gamma (média 1) de cada setor, já com o multiplicador do cenário."""
    return np.array([(s["sigma"] * cenario["mult_sigma"]) ** 2
                     for s in cfg["carteira"]["setores"]], dtype=float)
```

## src/fidc_risk/waterfall.py

```python
"""Cascata de perdas de um FIDC com cota sênior e cota subordinada, por ciclo.

Convenções (todas por ciclo de ``horizonte_dias``):

* ``preco_total``  : PL investido (soma dos preços pagos aos cedentes).
* ``face_total``   : soma dos valores de face; ``face_total - preco_total`` é a receita bruta de deságio.
* Custo da sênior  : ``sênior * ((1 + CDI + spread)^(h/ano) - 1)``.
* Excesso de spread (XS) = deságio - custo da sênior - despesas.
* Perda de crédito L : face não recebida (face x LGD dos sacados em default).

Resultado do ciclo para quem está abaixo da sênior: ``XS - L``. A subordinada absorve
primeiro o que exceder o XS; só depois de zerá-la a sênior perde. Com ``usar_xs=False`` o XS
é ignorado e a subordinada funciona apenas como colchão de capital (visão conservadora, que é
a leitura de agência de rating para a cauda).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Estrutura:
    face_total: float
    preco_total: float
    cdi_anual: float
    spread_senior_anual: float
    despesas_anuais: float
    horizonte_dias: int
    dias_ano: int

    def taxa_ciclo(self, taxa_anual: float) -> float:
        return (1.0 + taxa_anual) ** (self.horizonte_dias / self.dias_ano) - 1.0

    def custo_senior(self, share_sub: float) -> float:
        senior = self.preco_total * (1.0 - share_sub)
        return senior * self.taxa_ciclo(self.cdi_anual + self.spread_senior_anual)

    def despesas(self) -> float:
        return self.preco_total * self.taxa_ciclo(self.despesas_anuais)

    def excesso_spread(self, share_sub: float) -> float:
        return (self.face_total - self.preco_total) - self.custo_senior(share_sub) - self.despesas()


def resultado_cotas(perda, est: Estrutura, share_sub: float, usar_xs: bool):
    """Perda da sênior, perda da subordinada e resultado líquido da subordinada, por cenário de perda."""
    perda = np.asarray(perda, dtype=float)
    sub = est.preco_total * share_sub
    sen = est.preco_total * (1.0 - share_sub)
    xs = est.excesso_spread(share_sub) if usar_xs else 0.0
    liquida = np.maximum(perda - xs, 0.0)
    perda_sub = np.minimum(liquida, sub)
    perda_sen = np.minimum(np.maximum(liquida - sub, 0.0), sen)
    resultado_sub = np.maximum(xs - perda, -sub)
    return perda_sen, perda_sub, resultado_sub, sub, sen


def estatisticas_cotas(valores, probs, est: Estrutura, share_sub: float, usar_xs: bool) -> dict:
    valores = np.asarray(valores, dtype=float)
    probs = np.asarray(probs, dtype=float)
    probs = probs / probs.sum()
    ps, pb, rs, sub, sen = resultado_cotas(valores, est, share_sub, usar_xs)
    out = {
        "share_sub": share_sub,
        "usar_xs": usar_xs,
        "xs_ciclo": est.excesso_spread(share_sub) if usar_xs else 0.0,
        "el_senior": float(np.sum(probs * ps)),
        "el_senior_taxa": float(np.sum(probs * ps) / sen),
        "p_perda_senior": float(np.sum(probs[ps > 1e-9])),
        "el_sub": float(np.sum(probs * pb)),
        "el_sub_taxa": float(np.sum(probs * pb) / sub) if sub > 0 else np.nan,
        "p_perda_sub": float(np.sum(probs[pb > 1e-9])),
        "p_sub_zerada": float(np.sum(probs[pb >= sub - 1e-9])) if sub > 0 else np.nan,
    }
    if usar_xs and sub > 0:
        out["ret_sub_ciclo"] = float(np.sum(probs * rs) / sub)
    else:
        out["ret_sub_ciclo"] = np.nan
    return out


def curva_subordinacao(valores, probs, est: Estrutura, grade, usar_xs: bool) -> pd.DataFrame:
    linhas = [estatisticas_cotas(valores, probs, est, float(s), usar_xs) for s in grade]
    return pd.DataFrame(linhas)


def menor_subordinacao(curva: pd.DataFrame, alvo_el_senior: float) -> float:
    """Menor fração de subordinada cuja EL da sênior (por ciclo) fica abaixo do alvo."""
    ok = curva[curva["el_senior_taxa"] <= alvo_el_senior]
    return float(ok["share_sub"].iloc[0]) if len(ok) else float("nan")
```

## scripts/atualizar_readme.py

```python
"""Copia as tabelas de outputs/tabelas_readme.md para dentro dos marcadores do README.

Os blocos <!-- BEGIN:nome --> ... <!-- END:nome --> do README são substituídos pelo texto gerado pelo
pipeline. Assim nenhum número da tabela é digitado à mão; verify_output.py confere a igualdade.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PADRAO = re.compile(r"<!-- BEGIN:(\w+) -->\n(.*?)\n<!-- END:\1 -->", re.S)


def blocos(texto: str) -> dict[str, str]:
    return {m.group(1): m.group(2) for m in PADRAO.finditer(texto)}


def main() -> int:
    gerado = blocos((RAIZ / "outputs" / "tabelas_readme.md").read_text(encoding="utf-8"))
    alvo = RAIZ / "README.md"
    texto = alvo.read_text(encoding="utf-8")
    faltando = [k for k in blocos(texto) if k not in gerado]
    if faltando:
        print("Marcadores sem tabela gerada:", faltando)
        return 1

    def troca(m: re.Match) -> str:
        return f"<!-- BEGIN:{m.group(1)} -->\n{gerado[m.group(1)]}\n<!-- END:{m.group(1)} -->"

    novo = PADRAO.sub(troca, texto)
    alvo.write_text(novo, encoding="utf-8")
    print("README atualizado:", ", ".join(sorted(blocos(novo))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

## scripts/generate_figures.py

```python
"""Gera as figuras de auditoria a partir dos CSVs em outputs/."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
OUT = RAIZ / "outputs"
FIG = RAIZ / "figures"
FIG.mkdir(exist_ok=True)

ROTULOS = {
    "crplus_poisson": "CreditRisk+ (Poisson)",
    "crplus_gamma": "CreditRisk+ (Gamma por setor)",
    "mc_crplus_gamma": "MC do CreditRisk+ (validação)",
    "copula_gaussiana": "Cópula gaussiana",
    "copula_t": "Cópula t",
}
CORES = {
    "crplus_poisson": "#8a8a8a",
    "crplus_gamma": "#1f5fa8",
    "mc_crplus_gamma": "#7fb2e5",
    "copula_gaussiana": "#c0561b",
    "copula_t": "#7a2a8f",
}
ESTILO = {"mc_crplus_gamma": ":"}


def fig_cauda(cen: str, face: float) -> None:
    q = pd.read_csv(OUT / "curvas_quantis.csv")
    q = q[q["cenario"] == cen]
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    for m, g in q.groupby("modelo"):
        ax.plot(1 - g["q"], 100 * g["perda"] / face, label=ROTULOS[m], color=CORES[m],
                ls=ESTILO.get(m, "-"), lw=1.8)
    ax.set_xscale("log")
    ax.invert_xaxis()
    ax.set_xlabel("Probabilidade de excedência (1 − nível)")
    ax.set_ylabel("Perda de crédito do ciclo (% da face)")
    ax.set_title(f"Cauda da distribuição de perdas — cenário {cen}")
    ax.grid(alpha=0.3)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / f"fig_cauda_{cen}.png", dpi=160)
    plt.close(fig)


def fig_subordinacao(cen: str) -> None:
    cv = pd.read_csv(OUT / "curvas_subordinacao.csv")
    cv = cv[(cv["cenario"] == cen) & (cv["modelo"] != "mc_crplus_gamma")]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), sharey=True)
    for ax, xs, titulo in zip(axes, (True, False), ("com excesso de spread", "sem excesso de spread")):
        for m, g in cv[cv["usar_xs"] == xs].groupby("modelo"):
            y = g["el_senior_taxa"].clip(lower=1e-9)
            ax.plot(100 * g["share_sub"], y, label=ROTULOS[m], color=CORES[m], lw=1.8)
        ax.axhline(1e-4, color="k", lw=0.8, ls="--")
        ax.set_yscale("log")
        ax.set_ylim(1e-8, 2e-2)
        ax.set_xlabel("Subordinação (% do PL)")
        ax.set_title(titulo)
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("EL da sênior por ciclo (log)")
    axes[0].legend(frameon=False, fontsize=8)
    fig.suptitle(f"Subordinação necessária — cenário {cen} (tracejado = alvo)", y=1.0)
    fig.tight_layout()
    fig.savefig(FIG / f"fig_subordinacao_{cen}.png", dpi=160)
    plt.close(fig)


def fig_validacao(cen: str) -> None:
    pmf = pd.read_csv(OUT / f"pmf_crplus_{cen}.csv")
    conv = pd.read_csv(OUT / "convergencia.csv")
    conv = conv[conv["cenario"] == cen]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    ax = axes[0]
    ax.plot(pmf["perda"] / 1e6, pmf["pmf_poisson"], color=CORES["crplus_poisson"], label="Poisson")
    ax.plot(pmf["perda"] / 1e6, pmf["pmf_gamma"], color=CORES["crplus_gamma"], label="Gamma por setor")
    corte = pmf["perda"][np.searchsorted(pmf["pmf_gamma"].cumsum().to_numpy(), 0.9999)] / 1e6
    ax.set_xlim(0, corte)
    ax.set_xlabel("Perda de crédito (R$ milhões)")
    ax.set_ylabel("Probabilidade (por unidade)")
    ax.set_title("pmf pela recursão de Panjer")
    ax.legend(frameon=False)
    ax.grid(alpha=0.3)
    ax = axes[1]
    ax.loglog(conv["n"], conv["rmse"], "o-", color=CORES["crplus_gamma"], label="RMSE da EL (MC)")
    n0, r0 = conv["n"].iloc[0], conv["rmse"].iloc[0]
    ax.loglog(conv["n"], r0 * (conv["n"] / n0) ** -0.5, "k--", lw=1, label="referência n$^{-1/2}$")
    incl = np.polyfit(np.log(conv["n"]), np.log(conv["rmse"]), 1)[0]
    ax.set_title(f"Convergência do MC (inclinação {incl:.3f})")
    ax.set_xlabel("n simulações por bloco")
    ax.set_ylabel("RMSE")
    ax.legend(frameon=False)
    ax.grid(alpha=0.3, which="both")
    fig.suptitle(f"Validação da implementação — cenário {cen}", y=1.0)
    fig.tight_layout()
    fig.savefig(FIG / f"fig_validacao_{cen}.png", dpi=160)
    plt.close(fig)


def main() -> None:
    resumo = pd.read_csv(OUT / "resumo_perdas.csv")
    for cen in resumo["cenario"].unique():
        face = float(resumo[resumo["cenario"] == cen]["face_total"].iloc[0])
        fig_cauda(cen, face)
        fig_subordinacao(cen)
        fig_validacao(cen)
    print("Figuras salvas em", FIG)


if __name__ == "__main__":
    main()
```

## scripts/gerar_pacote_notebooklm.py

```python
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
```

## scripts/verify_output.py

```python
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
```

## tests/conftest.py

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
```

## tests/test_core.py

```python
import numpy as np
import pytest
from scipy.stats import poisson

from fidc_risk.copula import (calibrar_rho, correlacao_default_alvo,
                              correlacao_default_gaussiana, simular_copula,
                              vasicek_quantil_fracao_perda)
from fidc_risk.creditriskplus import (bandas, momentos_analiticos, pmf_perda,
                                      simular_crplus)
from fidc_risk.metrics import resumo_distribuicao
from fidc_risk.waterfall import Estrutura, resultado_cotas


def carteira_pequena(seed=1, n=60, k=3):
    rng = np.random.default_rng(seed)
    perda = rng.lognormal(np.log(50_000), 0.8, n)
    pdh = rng.uniform(0.002, 0.05, n)
    setor = rng.integers(0, k, n)
    return perda, pdh, setor


def test_panjer_poisson_um_devedor_recupera_poisson():
    v = np.array([1])
    lam = np.array([0.3])
    pmf = pmf_perda(v, lam, np.array([0]), np.array([0.0]), 1.0, tol=1e-14)
    esperado = poisson.pmf(np.arange(8), 0.3)
    assert np.allclose(pmf[:8], esperado, atol=1e-12)


def test_bandas_preservam_perda_esperada():
    perda, pdh, _ = carteira_pequena()
    v, lam = bandas(perda, pdh, 5_000.0)
    assert np.all(v >= 1)
    assert np.isclose(np.sum(lam * v * 5_000.0), np.sum(pdh * perda))


@pytest.mark.parametrize("s2", [[0.0, 0.0, 0.0], [0.5, 0.8, 1.2]])
def test_panjer_momentos_batem_com_formula_fechada(s2):
    perda, pdh, setor = carteira_pequena()
    v, lam = bandas(perda, pdh, 5_000.0)
    s2 = np.array(s2)
    pmf = pmf_perda(v, lam, setor, s2, 5_000.0, tol=1e-13)
    x = np.arange(len(pmf)) * 5_000.0
    media = np.sum(x * pmf)
    var = np.sum(pmf * (x - media) ** 2)
    media_a, var_a = momentos_analiticos(v, lam, setor, s2, 5_000.0)
    assert np.isclose(pmf.sum(), 1.0, atol=1e-10)
    assert np.isclose(media, media_a, rtol=1e-8)
    assert np.isclose(var, var_a, rtol=1e-6)


def test_gamma_engorda_a_cauda_em_relacao_a_poisson():
    perda, pdh, setor = carteira_pequena()
    v, lam = bandas(perda, pdh, 5_000.0)
    pp = pmf_perda(v, lam, setor, np.zeros(3), 5_000.0)
    pg = pmf_perda(v, lam, setor, np.array([1.0, 1.0, 1.0]), 5_000.0)
    n = max(len(pp), len(pg))
    pp = np.pad(pp, (0, n - len(pp)))
    pg = np.pad(pg, (0, n - len(pg)))
    x = np.arange(n) * 5_000.0
    q_p = resumo_distribuicao(x, pp, [0.999])["var_0.999"]
    q_g = resumo_distribuicao(x, pg, [0.999])["var_0.999"]
    assert q_g > q_p


def test_panjer_vs_monte_carlo_do_mesmo_modelo():
    perda, pdh, setor = carteira_pequena()
    unidade = 5_000.0
    v, lam = bandas(perda, pdh, unidade)
    s2 = np.array([0.5, 0.8, 1.2])
    pmf = pmf_perda(v, lam, setor, s2, unidade)
    n_sims = 60_000
    am = simular_crplus(v, lam, setor, s2, unidade, n_sims, np.random.default_rng(7))
    n_un = np.minimum(np.rint(am / unidade).astype(int), len(pmf) - 1)
    ecdf = np.cumsum(np.bincount(n_un, minlength=len(pmf))) / n_sims
    ks = np.max(np.abs(ecdf - np.cumsum(pmf)))
    assert ks < np.sqrt(np.log(2 / 1e-3) / (2 * n_sims))


def test_calibracao_casa_correlacao_de_default():
    for p, s2 in [(0.005, 0.5), (0.03, 1.0), (0.02, 2.25)]:
        rho = calibrar_rho(p, s2)
        assert np.isclose(correlacao_default_gaussiana(p, rho),
                          correlacao_default_alvo(p, s2), rtol=1e-7)
    assert calibrar_rho(0.02, 0.0) == 0.0


def test_copula_sem_correlacao_tem_media_e_variancia_independentes():
    perda, pdh, setor = carteira_pequena()
    am = simular_copula(pdh, perda, setor, np.zeros(3), 80_000, np.random.default_rng(3))
    media = np.sum(pdh * perda)
    var = np.sum(pdh * (1 - pdh) * perda ** 2)
    assert abs(am.mean() - media) < 4 * am.std() / np.sqrt(len(am))
    assert np.isclose(am.var(), var, rtol=0.05)


def test_copula_gaussiana_converge_para_vasicek_em_carteira_homogenea():
    n, p, rho, lgd = 4_000, 0.02, 0.15, 0.6
    perda = np.full(n, lgd)  # face 1 por sacado
    am = simular_copula(np.full(n, p), perda, np.zeros(n, dtype=int), np.array([rho]),
                        40_000, np.random.default_rng(11), chunk=500)
    mc = np.quantile(am / n, 0.99)
    ref = vasicek_quantil_fracao_perda(p, rho, lgd, 0.99)
    assert abs(mc - ref) / ref < 0.08


def test_cascata_identidades():
    est = Estrutura(face_total=106.0, preco_total=100.0, cdi_anual=0.14,
                    spread_senior_anual=0.03, despesas_anuais=0.02,
                    horizonte_dias=60, dias_ano=360)
    perda = np.array([0.0, 1.0, 5.0, 30.0, 80.0])
    for usar_xs in (True, False):
        ps, pb, rs, sub, sen = resultado_cotas(perda, est, 0.2, usar_xs)
        xs = est.excesso_spread(0.2) if usar_xs else 0.0
        assert np.allclose(ps + pb, np.minimum(np.maximum(perda - xs, 0.0), 100.0))
        assert np.all(ps >= 0) and np.all(pb <= sub + 1e-12)
        assert ps[0] == 0 and pb[0] == 0
    # sem XS, a sênior só perde acima do tamanho da subordinada
    ps, pb, _, sub, _ = resultado_cotas(np.array([19.0, 21.0]), est, 0.2, False)
    assert ps[0] == 0 and np.isclose(ps[1], 1.0)
```

## tests/test_mercado.py

```python
import numpy as np
import pandas as pd
import pytest

from fidc_risk.mercado import (decompor, desagio_sobre_face, el_pct_pl,
                               fator_face_sobre_preco, pd_anual_equilibrio)


def test_desagio_sobre_face_exemplo_do_projeto():
    # 3% a.m. por 60 dias: preço = 100/1,03^2 = 94,26 => desconto de 5,74 sobre face 100
    assert np.isclose(desagio_sobre_face(0.03, 60), 1 - 1 / 1.03 ** 2)
    assert np.isclose(100 * desagio_sobre_face(0.03, 60), 5.74, atol=0.01)


def test_fator_e_desagio_sao_consistentes():
    d, h = 0.0292, 50.8
    assert np.isclose(desagio_sobre_face(d, h) * fator_face_sobre_preco(d, h),
                      fator_face_sobre_preco(d, h) - 1.0)


@pytest.mark.parametrize("share_sub", [0.0, 0.1, 0.2, 0.35])
def test_decomposicao_fecha_identidade(share_sub):
    r = decompor(0.0292, 50.8, 0.004, 0.1365, 0.03, 0.02, share_sub)
    soma = r["funding_senior_ciclo"] + r["custos_ciclo"] + r["el_ciclo"] + r["margem_residual_ciclo"]
    assert np.isclose(soma, r["receita_desagio_ciclo"], atol=1e-14)
    assert np.isclose(r["capacidade_perda_anual"], r["capacidade_perda_ciclo"] * 360 / 50.8)


def test_pd_de_equilibrio_zera_a_margem():
    d, h, lgd, s = 0.0292, 50.8, 0.6, 0.2
    base = decompor(d, h, 0.0, 0.1365, 0.03, 0.02, s)
    pd_a = pd_anual_equilibrio(base["capacidade_perda_ciclo"], fator_face_sobre_preco(d, h), lgd, h)
    n = 50
    cart = pd.DataFrame({"face": np.ones(n), "pd_anual": np.full(n, pd_a)})
    el = el_pct_pl(cart, d, h, lgd)
    r = decompor(d, h, el, 0.1365, 0.03, 0.02, s)
    assert abs(r["margem_residual_ciclo"]) < 1e-12


def test_el_cresce_com_o_prazo():
    cart = pd.DataFrame({"face": [1.0, 2.0, 3.0], "pd_anual": [0.01, 0.03, 0.08]})
    a = el_pct_pl(cart, 0.0292, 30, 0.6)
    b = el_pct_pl(cart, 0.0292, 60, 0.6)
    assert b > a
```

## tests/test_prompts.py

```python
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PROMPTS = RAIZ / "docs" / "prompts_notebooklm"

LIMITE_CHAT = 10_000     # personalização do chat do NotebookLM (reportado em dez/2025)
LIMITE_SLIDES = 2_000    # limite de slides não é publicado: margem conservadora própria


def texto(nome: str) -> str:
    return (PROMPTS / nome).read_text(encoding="utf-8").strip()


def test_instrucao_do_chat_cabe_no_limite():
    assert len(texto("01_instrucao_do_chat.txt")) <= LIMITE_CHAT


def test_prompts_de_slides_sao_curtos():
    assert len(texto("02_slides_completo.txt")) <= LIMITE_SLIDES
    assert len(texto("03_slides_curto.txt")) <= 800


def test_numeros_dos_prompts_estao_no_readme():
    readme = (RAIZ / "README.md").read_text(encoding="utf-8")
    slides = texto("02_slides_completo.txt")
    for numero in ["2,92%", "50,8", "2,0%", "6,3%"]:
        assert numero in slides
        assert numero in readme
```
