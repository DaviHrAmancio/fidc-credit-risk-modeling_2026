<!-- BEGIN:tabela_perdas -->
| Cenário | Modelo | EL | VaR 99% | VaR 99,9% | ES 99,9% |
|---|---|---|---|---|---|
| base | CreditRisk+ Poisson | 0,267 | 1,18 | 1,68 | 1,90 |
| base | CreditRisk+ Gamma (setores) | 0,267 | 1,27 | 1,85 | 2,08 |
| base | Cópula gaussiana | 0,267 | 1,25 | 1,78 | 2,00 |
| base | Cópula t (ν = 5) | 0,264 | 4,22 | 10,89 | 13,47 |
| estresse | CreditRisk+ Poisson | 0,853 | 2,25 | 2,92 | 3,19 |
| estresse | CreditRisk+ Gamma (setores) | 0,853 | 3,18 | 4,51 | 5,09 |
| estresse | Cópula gaussiana | 0,853 | 3,02 | 4,28 | 4,86 |
| estresse | Cópula t (ν = 5) | 0,861 | 8,39 | 15,93 | 18,89 |
<!-- END:tabela_perdas -->

<!-- BEGIN:tabela_subordinacao -->
| Cenário | Modelo | com excesso de spread | sem excesso de spread |
|---|---|---|---|
| base | CreditRisk+ Poisson | 0,0% | 1,0% |
| base | CreditRisk+ Gamma (setores) | 0,0% | 1,0% |
| base | Cópula gaussiana | 0,0% | 1,0% |
| base | Cópula t (ν = 5) | 5,5% | 8,0% |
| estresse | CreditRisk+ Poisson | 0,0% | 2,0% |
| estresse | CreditRisk+ Gamma (setores) | 1,0% | 3,5% |
| estresse | Cópula gaussiana | 0,5% | 3,0% |
| estresse | Cópula t (ν = 5) | 11,0% | 14,0% |
<!-- END:tabela_subordinacao -->

<!-- BEGIN:tabela_decomposicao -->
| Cenário | Mês | Deságio a.m. | Prazo (dias) | Receita de deságio | Funding sênior | Custos | **Capacidade de perda** | EL do modelo | Margem residual | EL / capacidade |
|---|---|---|---|---|---|---|---|---|---|---|
| base | 2026-04 | 2,75% | 50,89 | 4,71% | 1,76% | 0,28% | **2,67%** | 0,28% | 2,39% | 10,5% |
| base | 2026-05 | 2,77% | 50,44 | 4,70% | 1,75% | 0,28% | **2,68%** | 0,28% | 2,40% | 10,4% |
| base | 2026-08 | 2,74% | 49,20 | 4,53% | 1,70% | 0,27% | **2,56%** | 0,27% | 2,29% | 10,6% |
| base | 2026-09 | 2,92% | 50,80 | 4,99% | 1,76% | 0,28% | **2,96%** | 0,28% | 2,68% | 9,5% |
| estresse | 2026-04 | 2,75% | 50,89 | 4,71% | 1,76% | 0,28% | **2,67%** | 0,89% | 1,77% | 33,5% |
| estresse | 2026-05 | 2,77% | 50,44 | 4,70% | 1,75% | 0,28% | **2,68%** | 0,89% | 1,79% | 33,1% |
| estresse | 2026-08 | 2,74% | 49,20 | 4,53% | 1,70% | 0,27% | **2,56%** | 0,86% | 1,70% | 33,7% |
| estresse | 2026-09 | 2,92% | 50,80 | 4,99% | 1,76% | 0,28% | **2,96%** | 0,90% | 2,06% | 30,3% |
<!-- END:tabela_decomposicao -->

<!-- BEGIN:tabela_equilibrio -->
| Cenário | Capacidade de perda por ano (% do PL) | EL do modelo por ano (% do PL) | PD anual de equilíbrio (homogênea) | PD anual média da carteira |
|---|---|---|---|---|
| base | 21,0% | 2,0% | 28,9% | 3,1% |
| estresse | 21,0% | 6,3% | 28,9% | 9,2% |
<!-- END:tabela_equilibrio -->

<!-- BEGIN:tabela_efeito_taxa_prazo -->
| Variação | Deságio a.m. | Prazo (dias) | Δ capacidade de perda anual (p.p. do PL) | efeito da taxa | efeito do prazo | interação |
|---|---|---|---|---|---|---|
| 2026-04 → 2026-05 | 2,75% → 2,77% | 50,89 → 50,44 | +0,24 | +0,24 | -0,01 | 0,00 |
| 2026-08 → 2026-09 | 2,74% → 2,92% | 49,20 → 50,80 | +2,22 | +2,20 | +0,02 | 0,00 |
<!-- END:tabela_efeito_taxa_prazo -->
