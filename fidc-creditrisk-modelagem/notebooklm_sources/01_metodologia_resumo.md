# Metodologia em resumo (detalhes em docs/METODOLOGIA.md)

**Perda.** Por sacado i: face E_i, perda se falhar ν_i = E_i × LGD, PD do ciclo p_i = 1 − (1 − PD_anual)^(h/360). Perda do ciclo
L = soma dos ν_i sobre os sacados em default. EL = soma de p_i ν_i.

**CreditRisk+ (CSFB, 1997).** Perdas arredondadas em bandas de R$ 10 mil; a intensidade é ajustada para **preservar a EL**. Cada setor tem um fator
Gamma de média 1 e variância σ_k² (correlação setorial). A distribuição da perda é obtida **exatamente** pela recursão de Panjer (binomial negativa
composta). Com σ_k² = 0 recai em Poisson puro. Média e variância têm fórmula fechada: Var = U² Σ λ_i v_i² + Σ σ_k² EL_k²; o segundo termo é o risco
sistêmico que engorda a cauda.

**Cópulas (família Merton/Vasicek).** X_i = √ρ Z_k + √(1−ρ) ε_i; default se X_i < limiar. A correlação de ativos ρ_k é **calibrada por casamento da
correlação de default** com o CreditRisk+. Na cópula t divide-se por √(W/ν) com W comum: nasce dependência de cauda também entre setores.
Caso limite de referência: Vasicek/ASRF (carteira homogênea e granular).

**LGD (v0.2.0).** (i) LGD econômica = 1 − R(1−c)/(1+d)^(lag/360): perda de valor presente da recuperação; com R=50%, lag=240 dias, c=15%, d=14% a.a.
dá 61%, compatível com os 60% usados. (ii) LGD aleatória Beta (média 60%, desvio 15 e 25 p.p.): preserva a EL e só aumenta a dispersão.
(iii) Não modelado: LGD sistêmica (pior quando há muitos defaults).

**Cascata de cotas.** Excesso de spread XS = deságio − custo da sênior − despesas. A subordinada absorve primeiro o que exceder XS; só depois a sênior
perde. Leitura "sem XS" (conservadora) trata a subordinada só como colchão de capital. Subordinação mínima = menor fração tal que EL da sênior ≤ 0,01% por ciclo.

**Validação.** Panjer reproduz média e variância exatas; Monte Carlo do mesmo modelo concorda com a pmf (KS abaixo do limite DKW); convergência do MC a
taxa n^(−1/2); cópula gaussiana converge ao quantil de Vasicek; correlação de default da cópula t conferida contra Monte Carlo.

**Lote de duplicatas.** Agrega por sacado, usa o prazo médio ponderado para a PD do ciclo, roda CreditRisk+ e cópula gaussiana, calcula deságio exigido
(custo sênior + retorno-alvo da subordinada + despesas + EL + margem), subordinação mínima e concentração (top 5/10, HHI, número efetivo de sacados).
