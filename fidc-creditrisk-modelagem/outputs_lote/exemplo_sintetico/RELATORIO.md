# Relatório de risco do lote `exemplo_sintetico`

> **Natureza:** estimativa de modelo com premissas explícitas (ver `metadata.json` e `docs/METODOLOGIA.md`). Não é recomendação de compra nem parecer de rating.

- arquivo de entrada: `templates/duplicatas_exemplo.csv` (SHA-256 `c73c4fcfbd3e9523…`)
- config: `config_snapshot.json` (SHA-256 `287ef87ecb801984…`), versão 0.3.0
- seed 20261003, 50.000 simulações (cópula), prazo médio ponderado 59 dias, deságio praticado 2,50% a.m.

## Composição e concentração

- 66 duplicatas, 35 sacados, face R$ 5.668.946, preço R$ 5.402.679
- maior sacado 11,75% da face; top 5 34,38%; top 10 54,99%
- número efetivo de sacados (1/HHI): 22,4

## Cenário `base`

**Perda esperada (EL):** R$ 11.275 = 0,199% da face.

| Modelo | EL | VaR 99% | VaR 99,9% | ES 99,9% |
|---|---|---|---|---|
| crplus_poisson | 0,199% | 3,21% | 6,72% | 7,25% |
| crplus_gamma | 0,199% | 3,21% | 6,86% | 7,30% |
| copula_gaussiana | 0,196% | 3,21% | 5,87% | 7,22% |

*(% da face; VaR e ES da perda de crédito do ciclo)*

**Subordinação mínima** (EL da sênior ≤ alvo por ciclo, % do PL):

| Modelo | com excesso de spread | sem excesso de spread |
|---|---|---|
| copula_gaussiana | 1,5% | 3,5% |
| crplus_gamma | 1,5% | 3,5% |
| crplus_poisson | 1,5% | 3,5% |

**Deságio exigido no ciclo** (% do preço) para cobrir o risco:

| Componente | % do preço |
|---|---|
| custo_senior | 2,085% |
| retorno_sub | 0,879% |
| despesas | 0,325% |
| perda_esperada | 0,209% |
| margem | 0,325% |
| **exigido (soma)** | **3,823%** |
| praticado | 4,928% |
| folga (praticado − exigido) | 1,106% |

Equivale a 1,93% a.m. exigido contra 2,48% a.m. praticado.

## Cenário `estresse`

**Perda esperada (EL):** R$ 35.181 = 0,621% da face.

| Modelo | EL | VaR 99% | VaR 99,9% | ES 99,9% |
|---|---|---|---|---|
| crplus_poisson | 0,621% | 4,89% | 7,92% | 9,14% |
| crplus_gamma | 0,621% | 5,47% | 8,66% | 10,17% |
| copula_gaussiana | 0,613% | 5,19% | 8,46% | 9,73% |

*(% da face; VaR e ES da perda de crédito do ciclo)*

**Subordinação mínima** (EL da sênior ≤ alvo por ciclo, % do PL):

| Modelo | com excesso de spread | sem excesso de spread |
|---|---|---|
| copula_gaussiana | 4,5% | 6,5% |
| crplus_gamma | 4,5% | 7,0% |
| crplus_poisson | 4,0% | 6,0% |

**Deságio exigido no ciclo** (% do preço) para cobrir o risco:

| Componente | % do preço |
|---|---|
| custo_senior | 2,085% |
| retorno_sub | 0,879% |
| despesas | 0,325% |
| perda_esperada | 0,651% |
| margem | 0,325% |
| **exigido (soma)** | **4,265%** |
| praticado | 4,928% |
| folga (praticado − exigido) | 0,663% |

Equivale a 2,15% a.m. exigido contra 2,48% a.m. praticado.

## O que este relatório NÃO cobre

Coobrigação do cedente, diluição (devoluções/abatimentos), fraude e duplicidade de lastro, risco de performance do cedente, revolvência e calendário de dias úteis. PDs por rating e `sigma` dos setores são **premissas** da config, não estimativas.
