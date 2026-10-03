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
