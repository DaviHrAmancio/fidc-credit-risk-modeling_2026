# Exemplo de análise de lote de duplicatas (SINTÉTICO)

Lote fictício de 66 duplicatas de 35 sacados, gerado com seed fixa em `templates/duplicatas_exemplo.csv`. Ilustra o fluxo `scripts/analisar_lote.py`; **não é um cedente real**.

## Cenário `base`

Face R$ 5.668.946; EL 0,199% da face.

| Modelo | VaR 99% | VaR 99,9% | ES 99,9% |
|---|---|---|---|
| CreditRisk+ Poisson | 3,21% | 6,72% | 7,25% |
| CreditRisk+ Gamma (setores) | 3,21% | 6,86% | 7,30% |
| Cópula gaussiana | 3,21% | 5,87% | 7,22% |

| Modelo | Sub. mín. com XS | Sub. mín. sem XS |
|---|---|---|
| Cópula gaussiana | 1,5% | 3,5% |
| CreditRisk+ Gamma (setores) | 1,5% | 3,5% |
| CreditRisk+ Poisson | 1,5% | 3,5% |

Deságio exigido no ciclo (% do preço): custo_senior 2,085%, retorno_sub 0,879%, despesas 0,325%, perda_esperada 0,209%, margem 0,325%. Soma exigida 3,823% contra praticado 4,928% (1,93% a.m. exigido vs 2,48% a.m. praticado).

## Cenário `estresse`

Face R$ 5.668.946; EL 0,621% da face.

| Modelo | VaR 99% | VaR 99,9% | ES 99,9% |
|---|---|---|---|
| CreditRisk+ Poisson | 4,89% | 7,92% | 9,14% |
| CreditRisk+ Gamma (setores) | 5,47% | 8,66% | 10,17% |
| Cópula gaussiana | 5,19% | 8,46% | 9,73% |

| Modelo | Sub. mín. com XS | Sub. mín. sem XS |
|---|---|---|
| Cópula gaussiana | 4,5% | 6,5% |
| CreditRisk+ Gamma (setores) | 4,5% | 7,0% |
| CreditRisk+ Poisson | 4,0% | 6,0% |

Deságio exigido no ciclo (% do preço): custo_senior 2,085%, retorno_sub 0,879%, despesas 0,325%, perda_esperada 0,651%, margem 0,325%. Soma exigida 4,265% contra praticado 4,928% (2,15% a.m. exigido vs 2,48% a.m. praticado).

## Concentração

Maior sacado 11,75% da face; top 5 34,38%; top 10 54,99%; número efetivo de sacados 22,4.
