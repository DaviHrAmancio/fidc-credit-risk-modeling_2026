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
