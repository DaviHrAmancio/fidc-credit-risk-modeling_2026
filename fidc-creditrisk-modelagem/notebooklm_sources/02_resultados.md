# Resultados (gerado automaticamente a partir de `outputs/`)

Versão 0.3.0, seed 20261003, 100.000 simulações por modelo, hash da config `287ef87ecb801984…`. **Todos os dados são sintéticos (hipotéticos).** Perdas em % da face da carteira (perda de crédito de um ciclo de 60 dias).

## Cenário `base`

600 sacados; face R$ 103.904.527; preço (PL) R$ 98.897.825; EL da carteira 0,315% da face.

| Modelo | EL | VaR 99% | VaR 99,9% | ES 99,9% |
|---|---|---|---|---|
| CreditRisk+ Poisson | 0,315% | 1,28% | 1,82% | 2,03% |
| CreditRisk+ Gamma (setores) | 0,315% | 1,39% | 2,00% | 2,25% |
| MC do CreditRisk+ (validação) | 0,315% | 1,39% | 2,03% | 2,24% |
| Cópula gaussiana | 0,316% | 1,37% | 1,93% | 2,18% |
| Cópula t (nu = 5) | 0,312% | 4,71% | 11,49% | 14,07% |

Subordinação mínima (EL da sênior ≤ 0,01% por ciclo; % do PL):

| Modelo | com excesso de spread | sem excesso de spread |
|---|---|---|
| CreditRisk+ Poisson | 0,0% | 1,5% |
| CreditRisk+ Gamma (setores) | 0,0% | 1,5% |
| Cópula gaussiana | 0,0% | 1,5% |
| Cópula t (nu = 5) | 6,5% | 8,5% |

Validação: KS entre Panjer e Monte Carlo = 0,0021 (limite DKW 0,0062); inclinação de convergência do MC = -0,491 (teórica −0,500).

### LGD determinística (CreditRisk+ Gamma, Panjer) — `base`

| LGD | EL | VaR 99,9% | ES 99,9% | Sub. mín. com XS | Sub. mín. sem XS |
|---|---|---|---|---|---|
| 40% | 0,210% | 1,33% | 1,50% | 0,0% | 1,0% |
| 50% | 0,262% | 1,66% | 1,87% | 0,0% | 1,0% |
| 60% | 0,315% | 2,00% | 2,25% | 0,0% | 1,5% |
| 70% | 0,367% | 2,33% | 2,62% | 0,0% | 1,5% |
| 80% | 0,420% | 2,67% | 3,00% | 0,0% | 2,0% |

### LGD Beta (média 60%) — incerteza de recuperação — `base`

| Modelo | Desvio da LGD | EL | VaR 99,9% | ES 99,9% |
|---|---|---|---|---|
| Cópula gaussiana | 0 (determinística) | 0,316% | 1,93% | 2,18% |
| Cópula gaussiana | 15% | 0,314% | 2,04% | 2,30% |
| Cópula gaussiana | 25% | 0,313% | 2,17% | 2,47% |
| MC do CreditRisk+ (validação) | 0 (determinística) | 0,315% | 2,03% | 2,24% |
| MC do CreditRisk+ (validação) | 15% | 0,316% | 2,10% | 2,38% |
| MC do CreditRisk+ (validação) | 25% | 0,317% | 2,29% | 2,64% |

### Cópula t: sensibilidade a nu — `base`

| nu | VaR 99,9% | ES 99,9% | Piso de corr. de default (média dos setores) | Alvo CreditRisk+ (média) | Calibrável? |
|---|---|---|---|---|---|
| 5 | 11,49% | 14,07% | 0,0601 | 0,0031 | não |
| 10 | 6,59% | 8,26% | 0,0233 | 0,0031 | não |
| 30 | 3,23% | 3,77% | 0,0057 | 0,0031 | não |
| 100 | 2,24% | 2,56% | 0,0015 | 0,0031 | sim |

## Cenário `estresse`

600 sacados; face R$ 103.904.527; preço (PL) R$ 98.897.825; EL da carteira 1,004% da face.

| Modelo | EL | VaR 99% | VaR 99,9% | ES 99,9% |
|---|---|---|---|---|
| CreditRisk+ Poisson | 1,004% | 2,49% | 3,20% | 3,48% |
| CreditRisk+ Gamma (setores) | 1,004% | 3,64% | 5,15% | 5,80% |
| MC do CreditRisk+ (validação) | 1,002% | 3,61% | 5,15% | 5,79% |
| Cópula gaussiana | 1,005% | 3,41% | 4,81% | 5,47% |
| Cópula t (nu = 5) | 1,014% | 9,15% | 16,55% | 19,74% |

Subordinação mínima (EL da sênior ≤ 0,01% por ciclo; % do PL):

| Modelo | com excesso de spread | sem excesso de spread |
|---|---|---|
| CreditRisk+ Poisson | 0,5% | 2,5% |
| CreditRisk+ Gamma (setores) | 1,5% | 4,0% |
| Cópula gaussiana | 1,5% | 3,5% |
| Cópula t (nu = 5) | 12,0% | 14,5% |

Validação: KS entre Panjer e Monte Carlo = 0,0034 (limite DKW 0,0062); inclinação de convergência do MC = -0,472 (teórica −0,500).

### LGD determinística (CreditRisk+ Gamma, Panjer) — `estresse`

| LGD | EL | VaR 99,9% | ES 99,9% | Sub. mín. com XS | Sub. mín. sem XS |
|---|---|---|---|---|---|
| 40% | 0,669% | 3,44% | 3,87% | 0,5% | 2,5% |
| 50% | 0,837% | 4,29% | 4,83% | 1,0% | 3,0% |
| 60% | 1,004% | 5,15% | 5,80% | 1,5% | 4,0% |
| 70% | 1,171% | 6,01% | 6,76% | 2,5% | 4,5% |
| 80% | 1,339% | 6,86% | 7,73% | 3,0% | 5,5% |

### LGD Beta (média 60%) — incerteza de recuperação — `estresse`

| Modelo | Desvio da LGD | EL | VaR 99,9% | ES 99,9% |
|---|---|---|---|---|
| Cópula gaussiana | 0 (determinística) | 1,005% | 4,81% | 5,47% |
| Cópula gaussiana | 15% | 1,002% | 4,87% | 5,48% |
| Cópula gaussiana | 25% | 1,003% | 4,95% | 5,61% |
| MC do CreditRisk+ (validação) | 0 (determinística) | 1,002% | 5,15% | 5,79% |
| MC do CreditRisk+ (validação) | 15% | 1,003% | 5,31% | 6,05% |
| MC do CreditRisk+ (validação) | 25% | 1,004% | 5,41% | 6,18% |

### Cópula t: sensibilidade a nu — `estresse`

| nu | VaR 99,9% | ES 99,9% | Piso de corr. de default (média dos setores) | Alvo CreditRisk+ (média) | Calibrável? |
|---|---|---|---|---|---|
| 5 | 16,55% | 19,74% | 0,0659 | 0,0225 | não |
| 10 | 11,04% | 13,13% | 0,0292 | 0,0225 | não |
| 30 | 7,05% | 8,28% | 0,0085 | 0,0225 | sim |
| 100 | 5,43% | 6,16% | 0,0024 | 0,0225 | sim |

## LGD econômica (hipótese)

R = 50%, atraso de recuperação 240 dias, desconto 14% a.a., custo de cobrança 15% ⇒ LGD = 61,05% (config usa 60%).
