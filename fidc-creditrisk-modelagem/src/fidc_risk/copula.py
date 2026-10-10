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
