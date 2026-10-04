# Limites declarados e próximos passos

## O que NÃO está no estudo (e por quê isso importa)
- **Dados reais:** a carteira é sintética. PDs por rating e σ dos setores são premissas. A comparação com informes da CVM é o próximo passo, não um resultado.
- **Diluição** (devoluções, abatimentos) e **coobrigação** do cedente: em FIDC de duplicatas, a perda não vem só de sacado que não paga.
- **Fraude e duplicidade de lastro**, risco operacional do cedente e do originador.
- **LGD sistêmica:** a LGD aleatória Beta é independente do default; na vida real a recuperação piora justamente nas crises.
- **Revolvência e gatilhos:** cada ciclo é independente; não há composição de ciclos nem eventos de avaliação/liquidação.
- **Calendário:** dias corridos sobre base 360, sem dias úteis.
- Um setor por sacado, setores independentes, aproximação de Poisson para defaults de Bernoulli.

## Achados que o estudo sustenta (todos sobre carteira sintética)
1. A EL é praticamente igual entre os modelos por construção; o que muda é a **cauda**.
2. Ignorar a correlação setorial (Poisson) subestima o VaR 99,9% em ~9% (base) e ~38% (estresse) frente ao Gamma por setor.
3. Com a correlação de default casada, CreditRisk+ Gamma e cópula gaussiana ficam próximos (3–7% de diferença no VaR 99,9%).
4. A conclusão sobre subordinação é **muito sensível à hipótese de cauda**: a cópula t com ν = 5 multiplica o VaR 99,9% por ~6 (base) ou ~3 (estresse).
5. **Com ν = 5 (e 10, 30) não existe ρ ≥ 0 que case a correlação de default do CreditRisk+**: o fator W comum impõe um piso de correlação maior que o alvo.
   Só ν = 100 é calibrável. Logo, "calibrar a cópula t" exige mudar a estrutura, não só o ρ.
6. LGD: EL e VaR escalam ~linearmente com a LGD; incerteza de recuperação (Beta) aumenta a cauda sem alterar a EL.
7. **Granularidade:** com poucos sacados (lote de 35), o VaR 99,9% é ~3,4× o da carteira de 600 sacados (6,9% vs 2,0% da face): a cauda é dominada por concentração.

## Dados públicos: o que existe
O Informe Mensal de FIDC da CVM é **agregado** (PL, carteira por segmento, inadimplência por faixa, PDD, prazos, subclasses). **Devedores e duplicatas individuais
em geral não são públicos.** A estratégia: calibrar agregados com dado real e manter a micro-carteira sintética.

## Próximos passos
- Calibração agregada com informes CVM (roll-rate/vintage) em fundo de duplicatas com histórico longo.
- Diluição como segundo componente de perda; coobrigação; revolvência e gatilhos.
- LGD sistêmica (correlacionada com o fator de default); cópula de Clayton como terceiro comparativo.
- Artigo e slides.
