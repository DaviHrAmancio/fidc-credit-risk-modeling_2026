"""Análise de risco de crédito de um LOTE de duplicatas de um cedente (visão de compra ativa).

Pergunta que este módulo responde: "se o fundo comprasse este lote, qual a perda esperada, qual a
cauda, qual o deságio mínimo para cobrir o risco e qual a subordinação necessária?"

Entrada: uma linha por duplicata (ver ``templates/duplicatas_exemplo.csv``)::

    sacado_id, valor_face, prazo_dias | (data_cessao, vencimento), rating | pd_anual, setor [, lgd]

Método (o mesmo do pipeline principal, ver docs/METODOLOGIA.md):

1. As duplicatas são agregadas por SACADO (devedor), como na carteira sintética: face somada,
   prazo médio ponderado pela face, PD do sacado e LGD ponderada pela face.
2. PD do ciclo de cada sacado = ``1 - (1 - PD_anual)^(prazo/dias_ano)``, com o prazo médio do
   sacado. Aproximação: trata o risco do sacado como o de um único recebível no prazo médio.
3. Distribuição de perdas: CreditRisk+ (Poisson e Gamma por setor, via Panjer) e cópula gaussiana
   (Monte Carlo) como conferência cruzada.
4. Deságio mínimo e subordinação mínima (cascata sênior/subordinada) com e sem excesso de spread.

Tudo que NÃO está aqui: coobrigação do cedente, diluição, fraude/duplicidade, risco de performance
do cedente, revolvência. Veja a seção "Limitações" da metodologia.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from .copula import calibrar_rho, simular_copula
from .creditriskplus import bandas, momentos_analiticos, pmf_perda
from .metrics import resumo_distribuicao
from .portfolio import pd_horizonte
from .waterfall import Estrutura, curva_subordinacao, menor_subordinacao

OBRIGATORIAS = ["sacado_id", "valor_face", "setor"]


# ----------------------------------------------------------------------------- leitura
def ler_duplicatas(caminho: str | Path, cfg: dict) -> pd.DataFrame:
    """Lê e valida o CSV de duplicatas. Levanta ``ValueError`` listando TODOS os problemas."""
    df = pd.read_csv(caminho, sep=None, engine="python", dtype={"sacado_id": str})
    df.columns = [c.strip().lower() for c in df.columns]
    erros = []

    faltam = [c for c in OBRIGATORIAS if c not in df.columns]
    if faltam:
        raise ValueError(f"colunas obrigatórias ausentes: {faltam}")

    if "prazo_dias" in df.columns:
        prazo = pd.to_numeric(df["prazo_dias"], errors="coerce")
    elif {"data_cessao", "vencimento"} <= set(df.columns):
        d0 = pd.to_datetime(df["data_cessao"], errors="coerce")
        d1 = pd.to_datetime(df["vencimento"], errors="coerce")
        prazo = (d1 - d0).dt.days.astype(float)
    else:
        raise ValueError("informe 'prazo_dias' OU as colunas 'data_cessao' e 'vencimento'")
    df["prazo_dias"] = prazo

    df["valor_face"] = pd.to_numeric(df["valor_face"], errors="coerce")
    ratings = set(cfg["carteira"]["ratings"])
    setores = {s["nome"] for s in cfg["carteira"]["setores"]}

    tem_pd = "pd_anual" in df.columns
    tem_rating = "rating" in df.columns
    if not (tem_pd or tem_rating):
        raise ValueError("informe 'rating' (A-D) ou 'pd_anual'")
    if tem_pd:
        df["pd_anual"] = pd.to_numeric(df["pd_anual"], errors="coerce")
    if tem_rating:
        df["rating"] = df["rating"].astype(str).str.strip().str.upper().replace({"NAN": np.nan})
    if "lgd" in df.columns:
        df["lgd"] = pd.to_numeric(df["lgd"], errors="coerce")

    for i, r in df.iterrows():
        lin = i + 2  # linha no arquivo (cabeçalho = 1)
        if not (r["valor_face"] > 0):
            erros.append(f"linha {lin}: valor_face inválido ({r['valor_face']})")
        if not (r["prazo_dias"] >= 1):
            erros.append(f"linha {lin}: prazo_dias inválido ({r['prazo_dias']})")
        if r["setor"] not in setores:
            erros.append(f"linha {lin}: setor '{r['setor']}' fora de {sorted(setores)}")
        pd_ok = tem_pd and pd.notna(r.get("pd_anual")) and 0.0 < r["pd_anual"] < 1.0
        rt_ok = tem_rating and pd.notna(r.get("rating")) and r["rating"] in ratings
        if not (pd_ok or rt_ok):
            erros.append(f"linha {lin}: informe rating em {sorted(ratings)} ou pd_anual em (0,1)")
        if "lgd" in df.columns and pd.notna(r["lgd"]) and not (0.0 < r["lgd"] <= 1.0):
            erros.append(f"linha {lin}: lgd fora de (0,1]")
    if erros:
        raise ValueError("duplicatas inválidas:\n  " + "\n  ".join(erros[:30])
                         + (f"\n  ... e mais {len(erros) - 30}" if len(erros) > 30 else ""))
    return df


def sha256_arquivo(caminho: str | Path) -> str:
    return hashlib.sha256(Path(caminho).read_bytes()).hexdigest()


# ----------------------------------------------------------------------------- agregação
def agregar_por_sacado(dup: pd.DataFrame, cfg: dict, desconto_mensal: float) -> pd.DataFrame:
    """Uma linha por sacado: face, preço, prazo médio ponderado, PD anual, setor, LGD."""
    c = cfg["carteira"]
    setores = [s["nome"] for s in c["setores"]]
    d = dup.copy()
    d["preco"] = d["valor_face"] / (1.0 + desconto_mensal) ** (d["prazo_dias"] / 30.0)
    d["prazo_x_face"] = d["prazo_dias"] * d["valor_face"]
    if "lgd" not in d.columns:
        d["lgd"] = np.nan
    d["lgd"] = d["lgd"].fillna(c["lgd"])
    d["lgd_x_face"] = d["lgd"] * d["valor_face"]

    # PD anual: pd_anual explícita tem prioridade; senão, a do rating
    # rating ausente (NaN) ou desconhecido vira NaN (não KeyError): linhas só com pd_anual são válidas
    pd_rating = d["rating"].map(lambda r: c["ratings"].get(r, {}).get("pd_anual", np.nan)
                                if isinstance(r, str) else np.nan) if "rating" in d.columns \
        else pd.Series(np.nan, index=d.index)
    if "pd_anual" in d.columns:
        d["pd_anual_dup"] = d["pd_anual"].fillna(pd_rating)
    else:
        d["pd_anual_dup"] = pd_rating
    if d["pd_anual_dup"].isna().any():
        raise ValueError(f"{int(d['pd_anual_dup'].isna().sum())} duplicata(s) sem PD: informe rating válido "
                         "ou pd_anual em (0,1)")
    d["pd_x_face"] = d["pd_anual_dup"] * d["valor_face"]

    # consistência: um sacado pertence a um só setor
    n_setor = d.groupby("sacado_id")["setor"].nunique()
    if (n_setor > 1).any():
        raise ValueError(f"sacado(s) com mais de um setor: {list(n_setor[n_setor > 1].index)}")

    g = d.groupby("sacado_id", sort=True).agg(
        n_duplicatas=("valor_face", "size"), face=("valor_face", "sum"), preco=("preco", "sum"),
        prazo_x_face=("prazo_x_face", "sum"), lgd_x_face=("lgd_x_face", "sum"),
        pd_x_face=("pd_x_face", "sum"), setor=("setor", "first")).reset_index()
    g["prazo_dias"] = g["prazo_x_face"] / g["face"]
    g["lgd"] = g["lgd_x_face"] / g["face"]
    g["pd_anual_base"] = g["pd_x_face"] / g["face"]
    g["setor_idx"] = g["setor"].map({n: i for i, n in enumerate(setores)})
    return g.drop(columns=["prazo_x_face", "lgd_x_face", "pd_x_face"])


def unidade_auto(face_total: float) -> float:
    """Unidade de banda do CreditRisk+ ~ face_total/10.000, arredondada para 1-2-5 x 10^k."""
    bruto = max(face_total / 1.0e4, 1.0)
    expo = 10 ** np.floor(np.log10(bruto))
    for m in (1, 2, 5, 10):
        if bruto <= m * expo:
            return float(m * expo)
    return float(10 * expo)


# ----------------------------------------------------------------------------- deságio
def desagio_exigido(est: Estrutura, el_ciclo: float, share_sub: float,
                    retorno_sub_anual: float, margem_anual: float) -> dict:
    """Deságio mínimo do ciclo (em % do preço) que cobre custo de capital, despesas, EL e margem.

        desagio = (1-s) * custo_senior + s * retorno_alvo_sub + despesas + EL/preco + margem

    A EL é a MÉDIA das perdas; a cauda (perda inesperada) é paga pelo retorno-alvo da
    subordinada e limitada pelo tamanho dela. Por isso a subordinação mínima é reportada à parte.
    """
    t = est.taxa_ciclo
    comp = {
        "custo_senior": (1.0 - share_sub) * t(est.cdi_anual + est.spread_senior_anual),
        "retorno_sub": share_sub * t(retorno_sub_anual),
        "despesas": t(est.despesas_anuais),
        "perda_esperada": el_ciclo / est.preco_total,
        "margem": t(margem_anual),
    }
    total = float(sum(comp.values()))
    prazo = est.horizonte_dias
    praticado = est.face_total / est.preco_total - 1.0
    mensal = lambda d: (1.0 + d) ** (30.0 / prazo) - 1.0
    return {**comp, "desagio_exigido_ciclo": total, "desagio_praticado_ciclo": praticado,
            "taxa_mensal_exigida": mensal(total), "taxa_mensal_praticada": mensal(praticado),
            "folga_ciclo": praticado - total}


# ----------------------------------------------------------------------------- análise
def analisar_lote(dup: pd.DataFrame, cfg: dict, cenario: str = "base",
                  desconto_mensal: float | None = None, n_sims: int = 50_000,
                  seed: int | None = None) -> dict:
    """Roda a análise de risco do lote em um cenário (``base``/``estresse`` da config)."""
    if desconto_mensal is None:
        desconto_mensal = cfg["precificacao"]["desconto_mensal"]
    cen = cfg["cenarios"][cenario]
    seed = int(cfg["seed"] if seed is None else seed)
    h = cfg["horizonte"]
    sub_cfg = cfg["subordinacao"]
    lote_cfg = cfg["lote"]

    sac = agregar_por_sacado(dup, cfg, desconto_mensal)
    sac["pd_anual"] = np.clip(sac["pd_anual_base"] * cen["mult_pd"], 0.0, 0.95)
    sac["pd_horizonte"] = pd_horizonte(sac["pd_anual"].to_numpy(), sac["prazo_dias"].to_numpy(),
                                       h["dias_ano"])
    sac["perda_dado_default"] = sac["face"] * sac["lgd"]
    sac["perda_esperada"] = sac["pd_horizonte"] * sac["perda_dado_default"]

    face_total = float(sac["face"].sum())
    preco_total = float(sac["preco"].sum())
    el = float(sac["perda_esperada"].sum())
    prazo_medio = float((dup["prazo_dias"] * dup["valor_face"]).sum() / dup["valor_face"].sum())

    sigmas2 = np.array([(s["sigma"] * cen["mult_sigma"]) ** 2 for s in cfg["carteira"]["setores"]])
    unidade = unidade_auto(face_total)
    setor = sac["setor_idx"].to_numpy()
    pdh = sac["pd_horizonte"].to_numpy()
    perda_dd = sac["perda_dado_default"].to_numpy()

    v, lam = bandas(perda_dd, pdh, unidade)
    media_a, var_a = momentos_analiticos(v, lam, setor, sigmas2, unidade)
    pmf_p = pmf_perda(v, lam, setor, np.zeros_like(sigmas2), unidade,
                      cfg["panjer"]["tol_massa"], cfg["panjer"]["n_max_teto"])
    pmf_g = pmf_perda(v, lam, setor, sigmas2, unidade,
                      cfg["panjer"]["tol_massa"], cfg["panjer"]["n_max_teto"])
    n_grade = max(len(pmf_p), len(pmf_g))
    pmf_p = np.pad(pmf_p, (0, n_grade - len(pmf_p)))
    pmf_g = np.pad(pmf_g, (0, n_grade - len(pmf_g)))
    vals = np.arange(n_grade) * unidade

    # cópula gaussiana (conferência cruzada), rho calibrado por setor presente no lote
    rho = np.zeros(len(sigmas2))
    for k in range(len(sigmas2)):
        m = setor == k
        if m.any() and sigmas2[k] > 0:
            rho[k] = calibrar_rho(float(pdh[m].mean()), float(sigmas2[k]))
    am_g = simular_copula(pdh, perda_dd, setor, rho, n_sims,
                          np.random.default_rng([seed, 7, 1]), "gaussiana", 5.0, 2000)

    quantis = cfg["quantis"]
    dist = {"crplus_poisson": (vals, pmf_p), "crplus_gamma": (vals, pmf_g),
            "copula_gaussiana": (am_g, np.full(n_sims, 1.0 / n_sims))}
    resumo = []
    for nome, (x, p) in dist.items():
        r = resumo_distribuicao(x, p, quantis)
        r.update({"modelo": nome, "cenario": cenario})
        for q in quantis:
            r[f"var_{q:g}_pct_face"] = r[f"var_{q:g}"] / face_total
            r[f"es_{q:g}_pct_face"] = r[f"es_{q:g}"] / face_total
        r["el_pct_face"] = r["el"] / face_total
        resumo.append(r)

    est = Estrutura(face_total=face_total, preco_total=preco_total,
                    cdi_anual=cfg["estrutura"]["cdi_anual"],
                    spread_senior_anual=cfg["estrutura"]["spread_senior_anual"],
                    despesas_anuais=cfg["estrutura"]["despesas_anuais"],
                    horizonte_dias=int(round(prazo_medio)), dias_ano=h["dias_ano"])
    grade = np.arange(sub_cfg["grade_min"], sub_cfg["grade_max"] + 1e-12, sub_cfg["grade_passo"])
    sub_min, curvas = [], []
    for nome, (x, p) in dist.items():
        for usar_xs in (True, False):
            cv = curva_subordinacao(x, p, est, grade, usar_xs)
            cv["modelo"], cv["cenario"] = nome, cenario
            curvas.append(cv)
            sub_min.append({"cenario": cenario, "modelo": nome,
                            "leitura": "com_xs" if usar_xs else "sem_xs",
                            "subordinacao_minima": menor_subordinacao(
                                cv, lote_cfg["alvo_el_senior_ciclo"])})

    share = float(cfg["estrutura"]["cota_subordinada"])
    desagio = desagio_exigido(est, el, share, lote_cfg["retorno_alvo_sub_anual"],
                              lote_cfg["margem_alvo_anual"])

    sac = sac.sort_values("face", ascending=False).reset_index(drop=True)
    sac["pct_face"] = sac["face"] / face_total
    sac["pct_el"] = sac["perda_esperada"] / el if el > 0 else 0.0
    por_setor = (sac.groupby("setor").agg(face=("face", "sum"), perda_esperada=("perda_esperada", "sum"),
                                          n_sacados=("sacado_id", "size")).reset_index())
    por_setor["pct_face"] = por_setor["face"] / face_total
    por_setor["pct_el"] = por_setor["perda_esperada"] / el if el > 0 else 0.0

    conc = {
        "n_duplicatas": int(len(dup)), "n_sacados": int(len(sac)),
        "maior_sacado_pct_face": float(sac["pct_face"].iloc[0]),
        "top5_pct_face": float(sac["pct_face"].head(5).sum()),
        "top10_pct_face": float(sac["pct_face"].head(10).sum()),
        "hhi_sacados": float((sac["pct_face"] ** 2).sum()),
        "n_efetivo_sacados": float(1.0 / (sac["pct_face"] ** 2).sum()),
        "top10_pct_el": float(sac["pct_el"].head(10).sum()) if el > 0 else 0.0,
    }
    return {
        "cenario": cenario, "unidade_panjer": unidade, "desconto_mensal": desconto_mensal,
        "face_total": face_total, "preco_total": preco_total, "prazo_medio_ponderado_dias": prazo_medio,
        "el": el, "el_pct_face": el / face_total, "media_analitica": media_a, "var_analitica": var_a,
        "massa_pmf_gamma": float(pmf_g.sum()), "concentracao": conc, "desagio": desagio,
        "sacados": sac, "por_setor": por_setor, "resumo": pd.DataFrame(resumo),
        "subordinacao_minima": pd.DataFrame(sub_min), "curvas": pd.concat(curvas, ignore_index=True),
    }
