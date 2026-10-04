"""Testes da v0.3.0: cascata de 3 classes, dados observados (auditoria) e correção do lote."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from fidc_risk import observado as obs
from fidc_risk.lote import agregar_por_sacado, ler_duplicatas
from fidc_risk.waterfall import absorcao_tres_classes, estatisticas_tres_classes

RAIZ = Path(__file__).resolve().parents[1]
CFG = json.loads((RAIZ / "config_snapshot.json").read_text(encoding="utf-8"))
CASO = RAIZ / "casos" / "via_multicredito" / "dados_observados.csv"


# ------------------------------------------------------------------ cascata de 3 classes
@pytest.mark.parametrize("mez,jun", [(0.37, 0.20), (0.0, 0.2), (0.3, 0.0), (0.1, 0.05)])
def test_tres_classes_conserva_perda(mez, jun):
    x = np.linspace(0, 1.4, 57)
    s, m, j = absorcao_tres_classes(x, 1.0, mez, jun)
    assert np.allclose(s + m + j, np.minimum(x, 1.0))


def test_tres_classes_ordem_de_absorcao():
    s, m, j = absorcao_tres_classes([0.10, 0.30, 0.70], 1.0, 0.37, 0.20)
    assert np.allclose(j, [0.10, 0.20, 0.20])
    assert np.allclose(m, [0.0, 0.10, 0.37])
    assert np.allclose(s, [0.0, 0.0, 0.13])


def test_tres_classes_xs_reduz_perda_liquida():
    s, m, j = absorcao_tres_classes([0.05], 1.0, 0.3, 0.2, excesso_spread=0.03)
    assert j[0] == pytest.approx(0.02) and m[0] == 0 and s[0] == 0


def test_tres_classes_reduz_a_duas_classes():
    from fidc_risk.waterfall import Estrutura, resultado_cotas
    est = Estrutura(1.05, 1.0, 0.14, 0.03, 0.02, 60, 360)
    x = np.linspace(0, 0.9, 40)
    ps, pb, _, _, _ = resultado_cotas(x, est, 0.2, usar_xs=False)
    s, m, j = absorcao_tres_classes(x, 1.0, 0.0, 0.2)
    assert np.allclose(s, ps) and np.allclose(j, pb) and np.allclose(m, 0)


def test_tres_classes_validacao():
    with pytest.raises(ValueError):
        absorcao_tres_classes([0.1], 1.0, 0.6, 0.5)


def test_estatisticas_tres_classes_pmf_simples():
    # perda 0 (p=.5), 10% (p=.3), 30% (p=.2): junior=20%, mezanino=30%
    df = estatisticas_tres_classes([0, 0.1, 0.3], [0.5, 0.3, 0.2], 1.0, 0.3, 0.2).set_index("classe")
    assert df.loc["junior", "p_perda"] == pytest.approx(0.5)
    assert df.loc["junior", "p_zerada"] == pytest.approx(0.2)           # perda 30% > 20%
    assert df.loc["junior", "el_pct_pl"] == pytest.approx(0.3 * 0.1 + 0.2 * 0.2)
    assert df.loc["mezanino", "el_pct_pl"] == pytest.approx(0.2 * 0.1)
    assert df.loc["senior", "p_perda"] == 0.0
    assert df.loc["senior", "anexacao_pct_pl"] == pytest.approx(0.5)


# ------------------------------------------------------------------ dados observados
def test_observado_caso_valida_e_audita():
    df = obs.ler_observado(CASO)
    assert len(df) == 12 and obs.classes_presentes(df) == ["senior", "mezanino", "junior"]
    aud = obs.auditoria_acumulado(df)
    assert (aud["n_meses_acima_tol"] == 0).all()
    assert aud["max_abs_dif_pp"].max() < 0.02


def test_observado_pl_soma_total():
    df = obs.ler_observado(CASO)
    soma = df["pl_senior_mil"] + df["pl_mezanino_mil"] + df["pl_junior_mil"]
    assert (soma - df["pl_total_mil"]).abs().max() <= 1.5


def test_acumulado_composto():
    assert obs.acumulado([10, 10])[-1] == pytest.approx(21.0)
    assert obs.acumulado([-50, 100])[-1] == pytest.approx(0.0)


def test_metricas_caso_valores_conferidos_a_mao():
    m = obs.metricas_classe(obs.ler_observado(CASO)).set_index("classe")
    assert m.loc["senior", "rent_acum_pct"] == pytest.approx(14.44, abs=0.02)   # reportado: 14,44
    assert m.loc["junior", "rent_acum_pct"] == pytest.approx(21.62, abs=0.02)   # reportado: 21,62
    assert m.loc["senior", "cdi_acum_pct"] == pytest.approx(11.68, abs=0.02)
    assert m.loc["junior", "meses_negativos"] == 2 and m.loc["senior", "meses_negativos"] == 0
    assert m.loc["junior", "pior_mes_pct"] == -1.66
    assert m.loc["junior", "rent_ultimo_mes_pct"] == 0.94
    assert m["pl_pct_do_total"].sum() == pytest.approx(1.0, abs=1e-3)


def test_subordinacao_confere_com_fonte():
    s = obs.subordinacao(obs.ler_observado(CASO)).iloc[-1]
    assert s["subordinacao_total"] == pytest.approx(0.574, abs=0.001)   # fonte: 57,4%
    assert s["pct_junior"] == pytest.approx(0.202, abs=0.001)           # fonte: 20,2%


def test_observado_rejeita_dados_ruins(tmp_path):
    ruim = pd.read_csv(CASO)
    ruim.loc[3, "rent_junior_pct"] = np.nan
    ruim.loc[5, "pl_total_mil"] += 100
    p = tmp_path / "ruim.csv"
    ruim.to_csv(p, index=False)
    with pytest.raises(ValueError) as e:
        obs.ler_observado(p)
    assert "rent_junior_pct" in str(e.value) and "PL total" in str(e.value)


def test_observado_aceita_fundo_sem_mezanino(tmp_path):
    d = pd.read_csv(CASO).drop(columns=[c for c in pd.read_csv(CASO).columns if "mezanino" in c])
    d["pl_total_mil"] = d["pl_senior_mil"] + d["pl_junior_mil"]
    p = tmp_path / "sem_mez.csv"
    d.to_csv(p, index=False)
    df = obs.ler_observado(p)
    assert obs.classes_presentes(df) == ["senior", "junior"]
    assert len(obs.metricas_classe(df)) == 2


# ------------------------------------------------------------------ correção do lote (v0.3.0)
def test_lote_linhas_mistas_rating_e_pd(tmp_path):
    setor = CFG["carteira"]["setores"][0]["nome"]
    p = tmp_path / "mix.csv"
    p.write_text(f"sacado_id,valor_face,prazo_dias,rating,pd_anual,setor\n"
                 f"A,1000,60,B,,{setor}\nB,2000,60,,0.05,{setor}\n", encoding="utf-8")
    d = ler_duplicatas(p, CFG)
    g = agregar_por_sacado(d, CFG, 0.025).set_index("sacado_id")
    assert g.loc["A", "pd_anual_base"] == pytest.approx(CFG["carteira"]["ratings"]["B"]["pd_anual"])
    assert g.loc["B", "pd_anual_base"] == pytest.approx(0.05)


def test_lote_sem_pd_nem_rating_valido_levanta_erro_claro():
    setor = CFG["carteira"]["setores"][0]["nome"]
    d = pd.DataFrame({"sacado_id": ["A"], "valor_face": [1000.0], "prazo_dias": [60.0],
                      "rating": [np.nan], "setor": [setor]})
    with pytest.raises(ValueError, match="sem PD"):
        agregar_por_sacado(d, CFG, 0.025)
