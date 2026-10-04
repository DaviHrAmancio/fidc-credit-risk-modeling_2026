# Visão geral do estudo

**Título:** Risco de crédito em FIDCs de duplicatas: PD, LGD, CreditRisk+, cópulas e dimensionamento da subordinação.
**Autor:** Davi Henrique de Souza Amâncio, Licenciatura em Matemática, IFC Campus Camboriú. Versão do repositório: 0.3.0 (prévia).

## Pergunta de pesquisa
O deságio cobrado na compra de duplicatas precisa cobrir custo do dinheiro + perda esperada + custos + margem. A perda esperada (EL) é a **média**
da distribuição de perdas; o **tamanho da subordinação** depende da **cauda**. O estudo mede como a escolha do modelo (Poisson, Gamma por setor,
cópulas) e das hipóteses de PD, LGD e dependência muda a cauda e, com ela, a subordinação necessária para proteger a cota sênior.

## Objetivo prático
Poder analisar o risco de crédito "como se estivesse comprando as duplicatas de um cedente": dado um lote (sacado, valor, prazo, rating, setor),
estimar perda esperada, cauda (VaR/ES), deságio mínimo e subordinação mínima, com **todo o código, os parâmetros e as hipóteses abertos**.

## Como o trabalho está organizado
1. Carteira **sintética** de 600 sacados, ciclo de 60 dias, LGD 60%, dois cenários (base e estresse: PD × 3 e volatilidade setorial × 1,5).
2. Três famílias de modelos: CreditRisk+ (Poisson e Gamma por setor, recursão de Panjer exata), cópula gaussiana e cópula t.
3. Cascata sênior/subordinada com e sem excesso de spread; subordinação mínima.
4. v0.2.0: sensibilidade à **LGD** (determinística e Beta), análise da **cópula t** (por que não dá para calibrá-la com poucos graus de liberdade),
   **analisador de lote** de duplicatas e **módulo de dados abertos da CVM**.
5. v0.3.0: **caso observado** de um FIC FIDC administrado pela BTG Pactual Serviços Financeiros, com PL, rentabilidade 12M e do último mês por classe
   (sênior, mezanino, júnior), cascata de 3 classes e ponte com o modelo de perdas (`07_caso_via_multicredito.md`).

## Princípio de transparência
Cada número dos slides aponta para um arquivo em `outputs/` e para o código que o gerou (`docs/MANIFESTO_DE_EVIDENCIAS.md`). Distinguimos sempre:
**hipotético** (carteira, PDs, LGD, estrutura), **estimado** (correlações calibradas), **calculado** (Panjer, momentos exatos) e **simulado** (Monte Carlo).
**Os resultados principais (`outputs/`) continuam 100% sintéticos.** A v0.3.0 acrescenta um caso à parte (`outputs_caso/via_multicredito/`) com dados **observados** de um fundo real (jun/2024, fonte externa), rotulado como OBSERVADO e separado do que é simulado.

## Aviso
Finalidade acadêmica e educacional. Resultados vêm de carteira sintética e premissas ilustrativas; não são estimativa de perdas de fundo real,
recomendação de investimento nem oferta de produto financeiro.
