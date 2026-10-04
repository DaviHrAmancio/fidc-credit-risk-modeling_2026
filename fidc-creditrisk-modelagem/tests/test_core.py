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
