"""Cascata de perdas de um FIDC com cota sênior e cota subordinada, por ciclo.

Convenções (todas por ciclo de ``horizonte_dias``):

* ``preco_total``  : PL investido (soma dos preços pagos aos cedentes).
* ``face_total``   : soma dos valores de face; ``face_total - preco_total`` é a receita bruta de deságio.
* Custo da sênior  : ``sênior * ((1 + CDI + spread)^(h/ano) - 1)``.
* Excesso de spread (XS) = deságio - custo da sênior - despesas.
* Perda de crédito L : face não recebida (face x LGD dos sacados em default).

Resultado do ciclo para quem está abaixo da sênior: ``XS - L``. A subordinada absorve
primeiro o que exceder o XS; só depois de zerá-la a sênior perde. Com ``usar_xs=False`` o XS
é ignorado e a subordinada funciona apenas como colchão de capital (visão conservadora, que é
a leitura de agência de rating para a cauda).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Estrutura:
    face_total: float
    preco_total: float
    cdi_anual: float
    spread_senior_anual: float
    despesas_anuais: float
    horizonte_dias: int
    dias_ano: int

    def taxa_ciclo(self, taxa_anual: float) -> float:
        return (1.0 + taxa_anual) ** (self.horizonte_dias / self.dias_ano) - 1.0

    def custo_senior(self, share_sub: float) -> float:
        senior = self.preco_total * (1.0 - share_sub)
        return senior * self.taxa_ciclo(self.cdi_anual + self.spread_senior_anual)

    def despesas(self) -> float:
        return self.preco_total * self.taxa_ciclo(self.despesas_anuais)

    def excesso_spread(self, share_sub: float) -> float:
        return (self.face_total - self.preco_total) - self.custo_senior(share_sub) - self.despesas()


def resultado_cotas(perda, est: Estrutura, share_sub: float, usar_xs: bool):
    """Perda da sênior, perda da subordinada e resultado líquido da subordinada, por cenário de perda."""
    perda = np.asarray(perda, dtype=float)
    sub = est.preco_total * share_sub
    sen = est.preco_total * (1.0 - share_sub)
    xs = est.excesso_spread(share_sub) if usar_xs else 0.0
    liquida = np.maximum(perda - xs, 0.0)
    perda_sub = np.minimum(liquida, sub)
    perda_sen = np.minimum(np.maximum(liquida - sub, 0.0), sen)
    resultado_sub = np.maximum(xs - perda, -sub)
    return perda_sen, perda_sub, resultado_sub, sub, sen


def estatisticas_cotas(valores, probs, est: Estrutura, share_sub: float, usar_xs: bool) -> dict:
    valores = np.asarray(valores, dtype=float)
    probs = np.asarray(probs, dtype=float)
    probs = probs / probs.sum()
    ps, pb, rs, sub, sen = resultado_cotas(valores, est, share_sub, usar_xs)
    out = {
        "share_sub": share_sub,
        "usar_xs": usar_xs,
        "xs_ciclo": est.excesso_spread(share_sub) if usar_xs else 0.0,
        "el_senior": float(np.sum(probs * ps)),
        "el_senior_taxa": float(np.sum(probs * ps) / sen),
        "p_perda_senior": float(np.sum(probs[ps > 1e-9])),
        "el_sub": float(np.sum(probs * pb)),
        "el_sub_taxa": float(np.sum(probs * pb) / sub) if sub > 0 else np.nan,
        "p_perda_sub": float(np.sum(probs[pb > 1e-9])),
        "p_sub_zerada": float(np.sum(probs[pb >= sub - 1e-9])) if sub > 0 else np.nan,
    }
    if usar_xs and sub > 0:
        out["ret_sub_ciclo"] = float(np.sum(probs * rs) / sub)
    else:
        out["ret_sub_ciclo"] = np.nan
    return out


def curva_subordinacao(valores, probs, est: Estrutura, grade, usar_xs: bool) -> pd.DataFrame:
    linhas = [estatisticas_cotas(valores, probs, est, float(s), usar_xs) for s in grade]
    return pd.DataFrame(linhas)


def menor_subordinacao(curva: pd.DataFrame, alvo_el_senior: float) -> float:
    """Menor fração de subordinada cuja EL da sênior (por ciclo) fica abaixo do alvo."""
    ok = curva[curva["el_senior_taxa"] <= alvo_el_senior]
    return float(ok["share_sub"].iloc[0]) if len(ok) else float("nan")
