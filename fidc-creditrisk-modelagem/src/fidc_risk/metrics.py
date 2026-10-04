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
