"""Dados OBSERVADOS de um fundo real (por classe de cota): retorno, PL e subordinação.

Natureza dos dados: tudo aqui vem de uma FONTE EXTERNA citada na config do caso (ex.: relatório de
monitoramento de agência de rating, informe mensal da CVM). Nenhum número é gerado pelo modelo.
O que este módulo faz é só aritmética sobre a tabela observada e a AUDITORIA dela:
recalcula o acumulado a partir dos retornos mensais e compara com o acumulado que a fonte reporta.

Formato do CSV (``dados_observados.csv``; uma linha por mês, ordem cronológica)::

    competencia, cdi_pct_mes,
    rent_senior_pct, rent_mezanino_pct, rent_junior_pct,            # % no mês
    acum_cdi_reportado_pct, acum_senior_reportado_pct, ...           # opcional (auditoria)
    pl_senior_mil, pl_mezanino_mil, pl_junior_mil, pl_total_mil       # R$ mil, fim do mês

A classe mezanino é opcional (fundos sem mezanino omitem as colunas ``*_mezanino_*``).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

CLASSES = ("senior", "mezanino", "junior")


def ler_observado(caminho: str | Path) -> pd.DataFrame:
    """Lê e valida o CSV observado. Levanta ``ValueError`` listando os problemas."""
    df = pd.read_csv(caminho, dtype={"competencia": str})
    erros = []
    if "competencia" not in df.columns or "cdi_pct_mes" not in df.columns:
        raise ValueError("colunas obrigatórias: competencia, cdi_pct_mes")
    if df["competencia"].duplicated().any():
        erros.append("competências repetidas")
    ordem = pd.PeriodIndex(df["competencia"], freq="M")
    if not ordem.is_monotonic_increasing:
        erros.append("competências fora de ordem cronológica")
    cls = classes_presentes(df)
    if not cls:
        erros.append("nenhuma coluna rent_<classe>_pct encontrada")
    for c in cls:
        r = pd.to_numeric(df[f"rent_{c}_pct"], errors="coerce")
        if r.isna().any():
            erros.append(f"rent_{c}_pct com valores ausentes/inválidos")
        if (r <= -100).any():
            erros.append(f"rent_{c}_pct <= -100%")
        pl = f"pl_{c}_mil"
        if pl in df.columns and (pd.to_numeric(df[pl], errors="coerce") < 0).any():
            erros.append(f"{pl} negativo")
    if "pl_total_mil" in df.columns:
        soma = sum(df[f"pl_{c}_mil"] for c in cls if f"pl_{c}_mil" in df.columns)
        dif = (soma - df["pl_total_mil"]).abs()
        if (dif > 1.5).any():  # tolerância de arredondamento (R$ mil)
            erros.append("soma do PL das classes difere do PL total em mais de R$ 1,5 mil")
    if erros:
        raise ValueError("dados observados inválidos: " + "; ".join(erros))
    return df


def classes_presentes(df: pd.DataFrame) -> list[str]:
    return [c for c in CLASSES if f"rent_{c}_pct" in df.columns]


def acumulado(retornos_pct) -> np.ndarray:
    """Retorno acumulado (em %) mês a mês, por capitalização composta."""
    r = np.asarray(retornos_pct, dtype=float) / 100.0
    return (np.cumprod(1.0 + r) - 1.0) * 100.0


def auditoria_acumulado(df: pd.DataFrame, tol_pp: float = 0.02) -> pd.DataFrame:
    """Compara o acumulado reportado pela fonte com o recalculado dos retornos mensais.

    ``tol_pp`` (pontos percentuais) cobre o arredondamento de 2 casas dos retornos mensais
    (erro acumulado de até ~0,005 pp por mês, em 12 meses ~0,06 pp no pior caso; por isso o teste
    usa a MAIOR diferença absoluta e reporta quantas linhas excedem a tolerância).
    """
    linhas = []
    pares = [("cdi", "cdi_pct_mes")] + [(c, f"rent_{c}_pct") for c in classes_presentes(df)]
    for nome, col in pares:
        rep = f"acum_{nome}_reportado_pct"
        if rep not in df.columns:
            continue
        calc = acumulado(df[col])
        dif = calc - pd.to_numeric(df[rep], errors="coerce").to_numpy()
        linhas.append({"serie": nome, "max_abs_dif_pp": float(np.nanmax(np.abs(dif))),
                       "dif_ultimo_mes_pp": float(dif[-1]),
                       "n_meses_acima_tol": int(np.sum(np.abs(dif) > tol_pp)),
                       "tolerancia_pp": tol_pp})
    return pd.DataFrame(linhas)


def metricas_classe(df: pd.DataFrame) -> pd.DataFrame:
    """Resumo por classe: PL, rentabilidade 12M e do último mês, % do CDI, risco e subordinação.

    Janela = todas as linhas do CSV (a config do caso declara que são 12 meses). ``excesso`` é o
    retorno em excesso ao CDI (geométrico, em pontos percentuais). ``razao_excesso_vol`` é a média
    do excesso mensal sobre o desvio-padrão do excesso mensal (NÃO anualizada; descritiva, não é
    índice de Sharpe formal: 12 observações não sustentam inferência).
    """
    n = len(df)
    cdi_m = df["cdi_pct_mes"].to_numpy(dtype=float)
    cdi_ac = float(acumulado(cdi_m)[-1])
    ult = df.iloc[-1]
    linhas = []
    for c in classes_presentes(df):
        r = df[f"rent_{c}_pct"].to_numpy(dtype=float)
        ac = float(acumulado(r)[-1])
        exc_m = r - cdi_m
        idx = np.cumprod(1.0 + r / 100.0)
        pico = np.maximum.accumulate(np.concatenate([[1.0], idx]))[1:]
        dd = float(np.min(idx / pico - 1.0) * 100.0)
        pl_c = f"pl_{c}_mil"
        linhas.append({
            "classe": c,
            "pl_ultimo_mes_mil": float(ult[pl_c]) if pl_c in df.columns else np.nan,
            "pl_pct_do_total": (float(ult[pl_c] / ult["pl_total_mil"])
                                if pl_c in df.columns and "pl_total_mil" in df.columns else np.nan),
            "rent_ultimo_mes_pct": float(r[-1]),
            "rent_acum_pct": ac,
            "cdi_acum_pct": cdi_ac,
            "pct_cdi_acum": 100.0 * ac / cdi_ac if cdi_ac else np.nan,
            "excesso_vs_cdi_pp": float(((1 + ac / 100) / (1 + cdi_ac / 100) - 1) * 100.0),
            "media_mensal_pct": float(r.mean()),
            "vol_mensal_pct": float(r.std(ddof=1)) if n > 1 else np.nan,
            "melhor_mes_pct": float(r.max()), "pior_mes_pct": float(r.min()),
            "meses_negativos": int((r < 0).sum()), "meses_abaixo_cdi": int((r < cdi_m).sum()),
            "max_queda_pct": dd,
            "razao_excesso_vol": (float(exc_m.mean() / exc_m.std(ddof=1))
                                  if n > 1 and exc_m.std(ddof=1) > 0 else np.nan),
        })
    return pd.DataFrame(linhas)


def subordinacao(df: pd.DataFrame) -> pd.DataFrame:
    """Série mensal de subordinação: % do PL em cada classe e subordinação total/júnior."""
    out = pd.DataFrame({"competencia": df["competencia"]})
    tot = df["pl_total_mil"] if "pl_total_mil" in df.columns else sum(
        df[f"pl_{c}_mil"] for c in classes_presentes(df))
    for c in classes_presentes(df):
        out[f"pct_{c}"] = df[f"pl_{c}_mil"] / tot
    out["subordinacao_total"] = 1.0 - out["pct_senior"]
    return out


def retorno_ponderado_proxy(df: pd.DataFrame) -> pd.DataFrame:
    """PROXY do retorno do fundo: média dos retornos de classe ponderada pelo PL do FIM do mês anterior.

    ESTIMADO. Ignora captações/resgates dentro do mês. A 1ª competência é descartada por não haver
    PL do mês anterior para ponderar.
    """
    cls = classes_presentes(df)
    rows = []
    for i in range(1, len(df)):
        pl_ant = {c: float(df[f"pl_{c}_mil"].iloc[i - 1]) for c in cls}
        tot = sum(pl_ant.values())
        r = sum(pl_ant[c] / tot * float(df[f"rent_{c}_pct"].iloc[i]) for c in cls)
        rows.append({"competencia": df["competencia"].iloc[i], "rent_proxy_fundo_pct": r,
                     "cdi_pct_mes": float(df["cdi_pct_mes"].iloc[i])})
    out = pd.DataFrame(rows)
    out["acum_proxy_pct"] = acumulado(out["rent_proxy_fundo_pct"])
    out["acum_cdi_pct"] = acumulado(out["cdi_pct_mes"])
    return out
