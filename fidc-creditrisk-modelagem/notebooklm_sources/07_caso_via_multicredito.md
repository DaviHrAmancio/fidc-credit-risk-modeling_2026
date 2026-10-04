# Caso observado: FIC FIDC Via Multicrédito (gerado de `outputs_caso/`)

**Natureza:** OBSERVADO (fonte: Austin Rating, relatório de 2024-08-09, janela 2023-07 a 2024-06 (12 competências)) + ponte SIMULADA com a carteira sintética. **Defasagem:** o dado mais recente é jun/2024; NÃO representa a situação atual do fundo. CNPJ 22.175.345/0001-19; FIC de FIDC (fundo que investe em cotas de outros FIDCs); administradora BTG Pactual Serviços Financeiros (cabeçalho do relatório); gestora Titan Capital Gestão de Recursos Ltda.

## Critérios: PL, rentabilidade 12M e do último mês, por classe

| Classe | PL (R$ mil) | % do PL | Último mês | 12 meses | CDI 12M | % do CDI | Excesso s/ CDI (pp) |
|---|---|---|---|---|---|---|---|
| Sênior | 70.734 | 42,6% | 0,99% | 14,45% | 11,68% | 123,7% | 2,47 |
| Mezanino | 61.907 | 37,2% | 1,06% | 15,54% | 11,68% | 133,0% | 3,45 |
| Júnior | 33.586 | 20,2% | 0,94% | 21,62% | 11,68% | 185,1% | 8,90 |

## Risco observado por classe

| Classe | Média mensal | Volatilidade mensal | Pior mês | Meses negativos | Meses abaixo do CDI |
|---|---|---|---|---|---|
| Sênior | 1,13% | 0,12% | 0,99% | 0 | 0 |
| Mezanino | 1,21% | 0,12% | 1,06% | 0 | 0 |
| Júnior | 1,66% | 1,63% | -1,66% | 2 | 2 |

Subordinação no último mês: total 57,4%; mezanino 37,2%; júnior 20,2%. Cotistas: 770 na sênior e 660 nas subordinadas. **Não verificado:** se a sênior é distribuída ao varejo e quem são os titulares das subordinadas (a fonte traz só contagens).

## Ponte com o modelo (SIMULADO; carteira sintética de duplicatas, sem excesso de spread)

| Cenário | Classe | Anexação–destacamento | EL anual aprox. (% da classe) | Prêmio observado s/ CDI |
|---|---|---|---|---|
| base | Júnior | 0,0%–20,2% | 9,82% | 8,90% |
| base | Mezanino | 20,2%–57,4% | 0,00% | 3,45% |
| base | Sênior | 57,4%–100,0% | 0,00% | 2,47% |
| estresse | Júnior | 0,0%–20,2% | 31,33% | 8,90% |
| estresse | Mezanino | 20,2%–57,4% | 0,00% | 3,45% |
| estresse | Sênior | 57,4%–100,0% | 0,00% | 2,47% |

| Cenário | VaR 99,9% da carteira (% PL) | Anexação da mezanino ÷ VaR | Anexação da sênior ÷ VaR |
|---|---|---|---|
| base | 2,10% | 9,6× | 27,3× |
| estresse | 5,41% | 3,7× | 10,6× |

Leituras que a ponte sustenta: (1) a perda de crédito é absorvida primeiro pela júnior; (2) com a subordinação observada, a sênior e a mezanino não perdem nas simulações, então o excesso delas sobre o CDI não é explicado por perda esperada de crédito do modelo; (3) o prêmio da júnior é da ordem da perda esperada no cenário base e menor que ela no estresse sem excesso de spread. **Não permite concluir:** previsão para o fundo real, preço justo ou recomendação.

## Auditoria

Maior diferença entre o acumulado reportado pela fonte e o recalculado dos retornos mensais: 0,0105 pp (arredondamento). Valida a transcrição, não a veracidade da fonte.
