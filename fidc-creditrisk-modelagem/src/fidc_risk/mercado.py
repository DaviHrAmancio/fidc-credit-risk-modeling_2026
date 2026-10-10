"""Dados de mercado (Quick Soft) e decomposição da taxa de deságio.

Decompõe, POR CICLO e em % do PL, a receita de deságio em

    deságio = funding da sênior + custos + perda esperada (EL) + margem residual

que é a fórmula discutida no projeto ("taxa = custo do dinheiro + perda esperada + custos + margem"),
agora com o deságio e o prazo médio publicados pela Quick Soft.

ATENÇÃO sobre o que a série de mercado representa: é a taxa média das operações processadas na
plataforma da Quick Soft (fundos, securitizadoras, factorings), paga pelo CEDENTE. Não é o retorno
líquido de um FIDC. A "margem residual" calculada aqui absorve tudo o que o modelo ainda não
cobre: diluição, risco do cedente, custos operacionais e tributos adicionais, caixa ocioso e lucro.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def carregar_serie(caminho: Path) -> pd.DataFrame:
    df = pd.read_csv(caminho)
    df["mes"] = df["mes"].astype(str)
    return df


def fator_face_sobre_preco(desagio_am: float, prazo_dias: float) -> float:
    """face / preço de compra para um deságio composto de ``desagio_am`` ao mês."""
    return (1.0 + desagio_am) ** (prazo_dias / 30.0)


def desagio_sobre_face(desagio_am: float, prazo_dias: float) -> float:
    """Desconto como fração da FACE (o que o cedente deixa de receber por 1 de face)."""
    return 1.0 - 1.0 / fator_face_sobre_preco(desagio_am, prazo_dias)


def taxa_ciclo(taxa_anual: float, prazo_dias: float, dias_ano: int = 360) -> float:
    return (1.0 + taxa_anual) ** (prazo_dias / dias_ano) - 1.0


def el_pct_pl(carteira: pd.DataFrame, desagio_am: float, prazo_dias: float,
              lgd: float, dias_ano: int = 360) -> float:
    """EL do ciclo em % do PL, recalculada para o prazo e o deságio informados.

    Usa as faces relativas da carteira sintética e a PD anual de cada sacado convertida
    para o prazo dado. PL = face_total / (face/preço).
    """
    w = carteira["face"].to_numpy()
    w = w / w.sum()
    pd_h = 1.0 - (1.0 - carteira["pd_anual"].to_numpy()) ** (prazo_dias / dias_ano)
    el_sobre_face = lgd * float(np.sum(w * pd_h))
    return el_sobre_face * fator_face_sobre_preco(desagio_am, prazo_dias)


def decompor(desagio_am: float, prazo_dias: float, el_pl: float, cdi_anual: float,
             spread_senior_anual: float, despesas_anuais: float, share_sub: float,
             dias_ano: int = 360) -> dict:
    """Decomposição do ciclo em % do PL. Vale: receita = funding + custos + el + margem."""
    receita = fator_face_sobre_preco(desagio_am, prazo_dias) - 1.0
    funding = (1.0 - share_sub) * taxa_ciclo(cdi_anual + spread_senior_anual, prazo_dias, dias_ano)
    custos = taxa_ciclo(despesas_anuais, prazo_dias, dias_ano)
    capacidade = receita - funding - custos            # o que sobra para pagar perdas + margem
    margem = capacidade - el_pl
    ciclos_ano = dias_ano / prazo_dias
    return {
        "receita_desagio_ciclo": receita,
        "funding_senior_ciclo": funding,
        "custos_ciclo": custos,
        "capacidade_perda_ciclo": capacidade,
        "el_ciclo": el_pl,
        "margem_residual_ciclo": margem,
        "ciclos_por_ano": ciclos_ano,
        "capacidade_perda_anual": capacidade * ciclos_ano,
        "el_anual": el_pl * ciclos_ano,
        "margem_residual_anual": margem * ciclos_ano,
        "el_sobre_capacidade": el_pl / capacidade if capacidade > 0 else np.nan,
        "retorno_sub_ciclo_antes_inesperada": margem / share_sub if share_sub > 0 else np.nan,
    }


def pd_anual_equilibrio(capacidade_ciclo_pl: float, fator_face_preco: float, lgd: float,
                        prazo_dias: float, dias_ano: int = 360) -> float:
    """PD anual MÉDIA (homogênea) para a qual a margem residual é zero.

    EL/PL = lgd * pd_ciclo * (face/preço)  =>  pd_ciclo = capacidade / (lgd * face/preço).
    """
    pd_ciclo = capacidade_ciclo_pl / (lgd * fator_face_preco)
    pd_ciclo = float(np.clip(pd_ciclo, 0.0, 0.999999))
    return 1.0 - (1.0 - pd_ciclo) ** (dias_ano / prazo_dias)
