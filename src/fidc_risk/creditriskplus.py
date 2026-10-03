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
