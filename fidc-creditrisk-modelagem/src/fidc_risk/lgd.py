"""Perda dado o default (LGD): derivação econômica e incerteza de recuperação.

Dois blocos independentes:

1. ``lgd_economico``: LGD como perda de VALOR PRESENTE da recuperação, e não como um número
   solto. Dado que o sacado entrou em default, recupera-se uma fração ``R`` da face depois de
   ``lag`` dias, com custo de cobrança ``c`` sobre o recuperado, e desconta-se à taxa ``d``::

       LGD = 1 - R * (1 - c) / (1 + d)^(lag / dias_ano)

2. ``sorteador_beta``: LGD ALEATÓRIA com distribuição Beta de média e desvio dados. Devolve um
   multiplicador de média 1 (LGD sorteada / LGD média), que é o que os simuladores esperam;
   assim a perda esperada fica preservada e só a dispersão (a cauda) muda.

Hipótese declarada: o sorteio de LGD é independente entre sacados e independente do default.
LGD sistêmica (pior em crise, correlacionada com o fator de default) NÃO está modelada aqui;
ela tende a engordar ainda mais a cauda e fica como próximo passo.
"""
from __future__ import annotations

from typing import Callable

import numpy as np


def lgd_economico(taxa_recuperacao: float, lag_dias: float, taxa_desconto_anual: float,
                  custo_cobranca: float = 0.0, dias_ano: int = 360) -> float:
    """LGD = 1 - R (1 - c) / (1 + d)^(lag/dias_ano), limitada a [0, 1]."""
    if not 0.0 <= taxa_recuperacao <= 1.0:
        raise ValueError("taxa_recuperacao deve estar em [0, 1]")
    if not 0.0 <= custo_cobranca < 1.0:
        raise ValueError("custo_cobranca deve estar em [0, 1)")
    if lag_dias < 0 or taxa_desconto_anual <= -1.0:
        raise ValueError("lag_dias >= 0 e taxa_desconto_anual > -1")
    valor_presente = taxa_recuperacao * (1.0 - custo_cobranca) / (1.0 + taxa_desconto_anual) ** (lag_dias / dias_ano)
    return float(min(1.0, max(0.0, 1.0 - valor_presente)))


def parametros_beta(media: float, desvio: float) -> tuple[float, float]:
    """(a, b) da Beta com a média e o desvio-padrão dados (método dos momentos).

    Exige 0 < media < 1 e desvio**2 < media * (1 - media); fora disso a Beta não existe.
    """
    if not 0.0 < media < 1.0:
        raise ValueError("media deve estar em (0, 1)")
    var = desvio ** 2
    if var <= 0.0 or var >= media * (1.0 - media):
        raise ValueError(f"desvio inviável para uma Beta de média {media}: "
                         f"0 < desvio < {np.sqrt(media * (1 - media)):.4f}")
    k = media * (1.0 - media) / var - 1.0
    return media * k, (1.0 - media) * k


def sorteador_beta(media: float, desvio: float) -> Callable[[np.random.Generator, tuple], np.ndarray]:
    """Gera multiplicadores de média 1 para a perda dado default (LGD sorteada / LGD média)."""
    a, b = parametros_beta(media, desvio)

    def sortear(rng: np.random.Generator, shape) -> np.ndarray:
        return rng.beta(a, b, size=shape) / media

    return sortear
