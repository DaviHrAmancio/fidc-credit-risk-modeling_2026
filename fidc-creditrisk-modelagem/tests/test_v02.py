"""Testes dos módulos novos da v0.2.0: LGD, cópula t calibrada, análise de lote e dados da CVM."""
import json
import tempfile
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from fidc_risk import cvm
from fidc_risk.copula import (calibrar_rho_t, correlacao_default_gaussiana,
                              correlacao_default_t, simular_copula)
from fidc_risk.creditriskplus import bandas, simular_crplus
from fidc_risk.lgd import lgd_economico, parametros_beta, sorteador_beta
from fidc_risk.lote import (agregar_por_sacado, analisar_lote, desagio_exigido, ler_duplicatas,
                            unidade_auto)
from fidc_risk.waterfall import Estrutura

RAIZ = Path(__file__).resolve().parents[1]
CFG = json.loads((RAIZ / "config_snapshot.json").read_text(encoding="utf-8"))
EXEMPLO = RAIZ / "templates" / "duplicatas_exemplo.csv"


# ------------------------------------------------------------------------------------ LGD
def test_lgd_economico_valor_conhecido():
    # 1 - 0,5*0,85 / 1,14^(240/360)
    esperado = 1.0 - 0.5 * 0.85 / 1.14 ** (240 / 360)
    assert lgd_economico(0.5, 240, 0.14, 0.15) == pytest.approx(esperado, rel=1e-12)


def test_lgd_economico_extremos_e_validacao():
    assert lgd_economico(1.0, 0, 0.14, 0.0) == 0.0          # recupera tudo, na hora, sem custo
    assert lgd_economico(0.0, 100, 0.14) == 1.0              # não recupera nada
    with pytest.raises(ValueError):
        lgd_economico(1.2, 10, 0.1)
    with pytest.raises(ValueError):
        lgd_economico(0.5, -1, 0.1)


def test_beta_momentos_e_inviabilidade():
    a, b = parametros_beta(0.6, 0.25)
    assert a / (a + b) == pytest.approx(0.6, rel=1e-12)
    assert a * b / ((a + b) ** 2 * (a + b + 1)) == pytest.approx(0.25 ** 2, rel=1e-12)
    with pytest.raises(ValueError):
        parametros_beta(0.6, 0.6)                             # desvio acima do máximo da Beta
    mult = sorteador_beta(0.6, 0.25)(np.random.default_rng(1), (400_000,))
    assert mult.mean() == pytest.approx(1.0, abs=5e-3)
    assert (mult * 0.6).max() <= 1.0


def _carteira_pequena():
    rng = np.random.default_rng(3)
    n = 200
    face = rng.lognormal(np.log(1e5), 0.7, n)
    pdh = np.full(n, 0.02)
    setor = rng.integers(0, 2, n)
    return face, pdh, setor


def test_lgd_beta_preserva_media_e_aumenta_dispersao_na_copula():
    face, pdh, setor = _carteira_pequena()
    perda = 0.6 * face
    rho = np.array([0.1, 0.1])
    det = simular_copula(pdh, perda, setor, rho, 60_000, np.random.default_rng(5))
    sto = simular_copula(pdh, perda, setor, rho, 60_000, np.random.default_rng(5),
                         mult_sev=sorteador_beta(0.6, 0.25))
    ep = sto.std(ddof=1) / np.sqrt(len(sto))
    assert abs(sto.mean() - perda @ pdh) < 4 * ep             # EL preservada
    assert sto.std() > det.std()                              # dispersão maior


def test_lgd_beta_preserva_media_e_aumenta_dispersao_no_crplus():
    face, pdh, setor = _carteira_pequena()
    v, lam = bandas(0.6 * face, pdh, 10_000.0)
    s2 = np.array([0.5, 0.5])
    det = simular_crplus(v, lam, setor, s2, 10_000.0, 60_000, np.random.default_rng(8))
    sto = simular_crplus(v, lam, setor, s2, 10_000.0, 60_000, np.random.default_rng(8),
                         mult_sev=sorteador_beta(0.6, 0.25))
    ep = sto.std(ddof=1) / np.sqrt(len(sto))
    assert abs(sto.mean() - det.mean()) < 5 * ep + 0.01 * det.mean()
    assert sto.std() > det.std()


# ------------------------------------------------------------------------- cópula t calibrada
def test_correlacao_t_converge_para_gaussiana_com_nu_grande():
    p, rho = 0.05, 0.2
    g = correlacao_default_gaussiana(p, rho)
    assert correlacao_default_t(p, rho, 5000.0) == pytest.approx(g, rel=0.05)


def test_correlacao_t_bate_com_monte_carlo():
    p, rho, nu = 0.05, 0.3, 5.0
    rng = np.random.default_rng(11)
    n = 600_000
    Z = rng.standard_normal(n)
    e1, e2 = rng.standard_normal(n), rng.standard_normal(n)
    W = rng.chisquare(nu, n)
    x1 = (np.sqrt(rho) * Z + np.sqrt(1 - rho) * e1) / np.sqrt(W / nu)
    x2 = (np.sqrt(rho) * Z + np.sqrt(1 - rho) * e2) / np.sqrt(W / nu)
    from scipy.stats import t as st
    c = st.ppf(p, nu)
    d1, d2 = x1 < c, x2 < c
    emp = (np.mean(d1 & d2) - np.mean(d1) * np.mean(d2)) / (p * (1 - p))
    assert correlacao_default_t(p, rho, nu) == pytest.approx(emp, abs=0.01)


def test_cola_t_com_nu_pequeno_nao_calibra_e_com_nu_grande_calibra():
    p, s2 = 0.003, 0.64
    rho5, viavel5, piso5 = calibrar_rho_t(p, s2, 5.0)
    assert not viavel5 and rho5 == 0.0 and piso5 > p * s2 / (1 - p)
    rho100, viavel100, _ = calibrar_rho_t(p, s2, 100.0)
    assert viavel100 and rho100 > 0
    assert correlacao_default_t(p, rho100, 100.0) == pytest.approx(p * s2 / (1 - p), rel=1e-6)


# ------------------------------------------------------------------------------------ lote
def test_unidade_auto_escala_1_2_5():
    assert unidade_auto(104e6) == 20_000.0                    # 104e6/1e4 = 10.400 -> próximo 1-2-5: 20.000
    assert unidade_auto(5.67e6) == 1_000.0
    assert unidade_auto(100.0) == 1.0


def test_exemplo_le_e_agrega_preservando_face():
    dup = ler_duplicatas(EXEMPLO, CFG)
    sac = agregar_por_sacado(dup, CFG, 0.025)
    assert sac["face"].sum() == pytest.approx(dup["valor_face"].sum(), rel=1e-12)
    assert sac["n_duplicatas"].sum() == len(dup)
    assert (sac["prazo_dias"] >= 1).all() and sac["pd_anual_base"].between(0, 1).all()


def test_lote_media_da_pmf_igual_a_el_e_pd_do_prazo():
    dup = ler_duplicatas(EXEMPLO, CFG)
    r = analisar_lote(dup, CFG, "base", n_sims=20_000)
    s = r["sacados"]
    pdh = 1.0 - (1.0 - s["pd_anual"]) ** (s["prazo_dias"] / CFG["horizonte"]["dias_ano"])
    assert np.allclose(pdh, s["pd_horizonte"], rtol=1e-12)
    assert r["el"] == pytest.approx((s["pd_horizonte"] * s["face"] * s["lgd"]).sum(), rel=1e-12)
    assert r["massa_pmf_gamma"] == pytest.approx(1.0, abs=1e-8)
    assert r["media_analitica"] == pytest.approx(r["el"], rel=1e-9)
    ry = r["resumo"].set_index("modelo")
    assert ry.loc["crplus_gamma", "var_0.999"] >= ry.loc["crplus_poisson", "var_0.999"]
    assert (ry["es_0.999"] >= ry["var_0.999"] - 1e-6).all()


def test_lote_estresse_tem_el_maior_e_desagio_exigido_maior():
    dup = ler_duplicatas(EXEMPLO, CFG)
    b = analisar_lote(dup, CFG, "base", n_sims=10_000)
    e = analisar_lote(dup, CFG, "estresse", n_sims=10_000)
    assert e["el"] > b["el"]
    assert e["desagio"]["desagio_exigido_ciclo"] > b["desagio"]["desagio_exigido_ciclo"]


def test_desagio_exigido_soma_dos_componentes():
    est = Estrutura(face_total=105.0, preco_total=100.0, cdi_anual=0.14, spread_senior_anual=0.03,
                    despesas_anuais=0.02, horizonte_dias=60, dias_ano=360)
    d = desagio_exigido(est, el_ciclo=0.5, share_sub=0.2, retorno_sub_anual=0.30, margem_anual=0.02)
    soma = sum(d[k] for k in ("custo_senior", "retorno_sub", "despesas", "perda_esperada", "margem"))
    assert d["desagio_exigido_ciclo"] == pytest.approx(soma, rel=1e-12)
    assert d["desagio_praticado_ciclo"] == pytest.approx(0.05, rel=1e-12)
    assert d["folga_ciclo"] == pytest.approx(0.05 - soma, rel=1e-12)


def _csv_temp(texto: str) -> Path:
    d = tempfile.mkdtemp()
    p = Path(d) / "x.csv"
    p.write_text(texto, encoding="utf-8")
    return p


def test_validacao_lista_todos_os_erros_de_uma_vez():
    p = _csv_temp("sacado_id,valor_face,prazo_dias,rating,setor\nA,-5,30,Z,Pesca\nB,10,0,A,Agro\n")
    with pytest.raises(ValueError) as e:
        ler_duplicatas(p, CFG)
    msg = str(e.value)
    assert "linha 2" in msg and "linha 3" in msg and "Pesca" in msg


def test_sacado_com_dois_setores_e_rejeitado():
    p = _csv_temp("sacado_id,valor_face,prazo_dias,rating,setor\nA,100,30,A,Agro\nA,100,30,A,Varejo\n")
    dup = ler_duplicatas(p, CFG)
    with pytest.raises(ValueError):
        agregar_por_sacado(dup, CFG, 0.025)


def test_datas_geram_prazo():
    p = _csv_temp("sacado_id,valor_face,data_cessao,vencimento,rating,setor\n"
                  "A,100,2026-10-05,2026-12-04,A,Agro\n")
    assert ler_duplicatas(p, CFG)["prazo_dias"].iloc[0] == 60


# ------------------------------------------------------------------------------------- CVM
def _zip_sintetico() -> Path:
    d = Path(tempfile.mkdtemp())
    zp = d / "inf_mensal_fidc_202604.zip"
    tab4 = ("TP_FUNDO_CLASSE;CNPJ_FUNDO_CLASSE;DT_COMPTC;TAB_IV_A_VL_PL\n"
            "FIDC;65.473.848/0001-83;2026-04-30;1000.50\n"
            "FIDC;11.111.111/0001-11;2026-04-30;999\n")
    tab1 = ("CNPJ_FUNDO_CLASSE;DT_COMPTC;TAB_I2_VL_CARTEIRA;TAB_I2_VL_REDUCAO\n"
            "65473848000183;2026-04-30;2000,25;50\n")
    outro = "OUTRA_COLUNA;VALOR\nx;1\n"
    with zipfile.ZipFile(zp, "w") as zf:
        zf.writestr("inf_mensal_fidc_tab_IV_202604.csv", tab4.encode("latin-1"))
        zf.writestr("inf_mensal_fidc_tab_I_202604.csv", tab1.encode("latin-1"))
        zf.writestr("inf_mensal_fidc_sem_cnpj_202604.csv", outro.encode("latin-1"))
    return zp


def test_cvm_url_e_cnpj():
    assert cvm.url_informe("202604").endswith("/INF_MENSAL/DADOS/inf_mensal_fidc_202604.zip")
    with pytest.raises(ValueError):
        cvm.url_informe("2026-04")
    assert cvm.normaliza_cnpj("65.473.848/0001-83") == "65473848000183"


def test_cvm_filtra_cnpj_em_formatos_diferentes():
    t = cvm.filtrar_cnpj(_zip_sintetico(), "65.473.848/0001-83")
    assert set(t) == {"inf_mensal_fidc_tab_IV_202604.csv", "inf_mensal_fidc_tab_I_202604.csv"}
    assert len(t["inf_mensal_fidc_tab_IV_202604.csv"]) == 1        # linha do outro fundo fora


def test_cvm_indicadores_razoes_e_rastreio():
    t = cvm.filtrar_cnpj(_zip_sintetico(), "65473848000183")
    regras = {"pl": {"arquivo": "tab_IV", "colunas": ["TAB_IV_A_VL_PL$"]},
              "carteira": {"arquivo": "tab_I_", "colunas": ["TAB_I2_VL_CARTEIRA$"]},
              "pdd": {"arquivo": "tab_I_", "colunas": ["TAB_I2_VL_REDUCAO$"]},
              "inad": {"arquivo": "tab_V", "colunas": []}}
    ind, log = cvm.extrair_indicadores(t, regras)
    v = ind.set_index("indicador")["valor"]
    assert v["pl"] == pytest.approx(1000.50) and v["carteira"] == pytest.approx(2000.25)  # vírgula decimal
    assert np.isnan(v["inad"])                                    # regra sem colunas -> NaN, não zero
    assert set(log["coluna"]) == {"TAB_IV_A_VL_PL", "TAB_I2_VL_CARTEIRA", "TAB_I2_VL_REDUCAO"}
    der = cvm.razoes_derivadas(ind, {"pdd_pct": ["pdd", "carteira"], "x": ["inad", "carteira"]})
    assert der.set_index("indicador").loc["pdd_pct", "valor"] == pytest.approx(50 / 2000.25)
    assert np.isnan(der.set_index("indicador").loc["x", "valor"])


def test_cvm_schema_report_lista_colunas_reais():
    s = cvm.relatorio_schema(_zip_sintetico())
    assert {"arquivo", "coluna", "exemplo"} <= set(s.columns)
    assert "TAB_IV_A_VL_PL" in set(s["coluna"])
