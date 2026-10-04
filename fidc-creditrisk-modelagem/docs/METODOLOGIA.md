# Metodologia

Este documento descreve o que o código implementa, com a notação do código. Tudo o que
aparece em `outputs/` é derivado de uma **carteira sintética**: nada aqui é dado de fundo real.

## 1. Objeto de estudo

Um FIDC de duplicatas compra, a cada ciclo de `h` dias, um conjunto de recebíveis com deságio.
O risco de crédito do ciclo é a perda de face `L` (devedor que não paga, descontada a recuperação).
O trabalho estuda a distribuição de `L` e como ela é repartida entre a cota subordinada e a sênior.

Agregamos as duplicatas por **sacado** `i`:

| Símbolo | Significado | No código |
|---|---|---|
| `E_i` | valor de face em aberto | `face` |
| `LGD` | perda dado default (constante) | `lgd` |
| `nu_i = E_i * LGD` | perda se o sacado falhar | `perda_dado_default` |
| `p_i` | PD do ciclo: `1 - (1 - PD_anual)^(h/dias_ano)` | `pd_horizonte` |
| `L = sum_i 1{default_i} * nu_i` | perda de crédito do ciclo | |

Perda esperada do ciclo: `EL = sum_i p_i * nu_i`.

## 2. CreditRisk+ (`creditriskplus.py`)

**Bandas.** Fixa-se uma unidade `U` (R$ 10 mil na configuração padrão) e `v_i = max(1, round(nu_i/U))`.
Para não distorcer a média, a intensidade é ajustada: `lam_i = p_i * nu_i / (v_i * U)`, de modo que
`lam_i * v_i * U = p_i * nu_i`. O arredondamento só afeta momentos de ordem superior.

**Poisson.** O número de defaults de cada sacado é Poisson(`lam_i`) (aproximação de Bernoulli com `p_i` pequeno).

**Setores e mistura Gamma.** Cada sacado pertence a um setor `k`. O fator `Gamma_k` tem média 1 e variância
`sigma_k^2`, e multiplica as intensidades do setor. Setores são independentes. Dado o setor, com
`mu_k = sum lam_i`, `alpha = 1/sigma_k^2` e `delta = sigma_k^2 mu_k / (1 + sigma_k^2 mu_k)`:

    G_k(z) = [ (1 - delta) / (1 - delta * P_k(z)) ]^alpha,    P_k(z) = sum_v q_v z^v,   q_v = mu_{k,v} / mu_k

Isto é uma binomial negativa composta, da classe (a, b, 0) de Panjer com `a = delta`, `b = (alpha - 1) * delta`
e `f(0) = (1 - delta)^alpha`:

    f(n) = sum_{v=1}^{n} (a + b*v/n) * q_v * f(n - v)

No caso Poisson (`sigma_k^2 = 0`): `a = 0`, `b = mu_k`, `f(0) = exp(-mu_k)`. A pmf total é a convolução das pmfs
dos setores. O comprimento da grade é dobrado até que a massa truncada fique abaixo de `tol_massa`.

**Momentos exatos** (usados na verificação):

    E[L]   = U * sum_i lam_i v_i
    Var[L] = U^2 * sum_i lam_i v_i^2  +  sum_k sigma_k^2 * (EL_k)^2

O primeiro termo da variância é o ruído idiossincrático; o segundo é a contribuição sistêmica dos setores
e é ele que engorda a cauda em relação ao Poisson puro.

## 3. Modelos de fator latente (`copula.py`)

Comparativos de mercado. Cada setor `k` tem um fator `Z_k ~ N(0, 1)` independente:

    X_i = sqrt(rho_k) * Z_k + sqrt(1 - rho_k) * eps_i,     default se X_i < c_i

* **Gaussiana:** `c_i = Phi^{-1}(p_i)`.
* **t:** `X_i` é dividido por `sqrt(W / nu)`, com `W ~ chi²(nu)` **comum a todos os setores**, e `c_i = t_nu^{-1}(p_i)`.
  Isso introduz dependência de cauda também entre setores.
* **Vasicek / ASRF:** para uma carteira homogênea e infinitamente granular, o quantil da fração de perda é
  `LGD * Phi( (Phi^{-1}(p) + sqrt(rho) * Phi^{-1}(q)) / sqrt(1 - rho) )`. Serve de caso limite analítico.

**Calibração de `rho_k` (casamento de correlação de default).** No CreditRisk+ homogêneo,
`corr(1_i, 1_j) = p * sigma^2 / (1 - p)`. Na cópula gaussiana, a correlação de default é
`(P(X_i < c, X_j < c) - p²) / (p(1-p))`, calculada por quadratura de Gauss-Hermite (160 nós).
Resolve-se por Brent para `rho_k` em cada setor, usando a PD média do setor.
Resultado em `outputs/calibracao_copula.csv`.

> **Atenção (comparabilidade).** A calibração casa a correlação de default **da cópula gaussiana** com o
> CreditRisk+. A cópula t usa o **mesmo `rho_k`**, mas com `nu = 5` sua correlação de default e sua
> dependência de cauda são bem maiores. Portanto ela **não é** um comparativo "à mesma correlação de default":
> é um teste de robustez à hipótese de cauda.
>
> **Por que não dá para "calibrar a t" com `nu = 5` (v0.2.0).** Como o fator `W` é comum a todos, a cópula t já
> gera correlação de default mesmo com `rho = 0`. Chamando esse valor de *piso*, `calibrar_rho_t` só encontra um
> `rho >= 0` se o piso for menor que o alvo do CreditRisk+. Com os parâmetros da config, o piso é ≈ 0,06 (`nu = 5`),
> ≈ 0,023 (`nu = 10`), ≈ 0,006 (`nu = 30`), contra alvos de 0,0017–0,0049: **só `nu = 100` é calibrável**
> (`outputs/t_calibracao_nu.csv`). A `correlacao_default_t` é validada contra Monte Carlo em `tests/test_v02.py`.
> Em vez de calibrar, o pipeline mostra a **sensibilidade da cauda a `nu`** (`outputs/t_sensibilidade_nu.csv`).

## 4. Cascata de cotas (`waterfall.py`)

Por ciclo, com `PL = soma dos preços pagos`, `s` = fração subordinada:

    XS = (face_total - PL) - (1 - s) * PL * [ (1 + CDI + spread)^(h/ano) - 1 ] - PL * [ (1 + despesas)^(h/ano) - 1 ]
    perda_sub = min( max(L - XS, 0), s * PL )
    perda_sen = min( max(L - XS - s * PL, 0), (1 - s) * PL )

Duas leituras:

* **com excesso de spread (`com_xs`)**: o ciclo paga primeiro as perdas com a receita de deságio que sobra
  depois do custo da sênior e das despesas.
* **sem excesso de spread (`sem_xs`)**: `XS = 0`; a subordinada é só colchão de capital.
  É a leitura conservadora usada em rating de cauda.

A **subordinação mínima** é a menor `s` na grade tal que `EL_sen / sênior <= alvo` (padrão: 0,01% por ciclo).
A `regra_multiplos_el.csv` traz a regra de mercado (subordinação = `k × EL`) para comparação.

## 4.1 LGD: derivação econômica e incerteza de recuperação (`lgd.py`, v0.2.0)

**LGD econômica.** Em vez de um número solto, a LGD é a perda de valor presente da recuperação. Dado o default, recupera-se
a fração `R` da face depois de `lag` dias, com custo de cobrança `c` sobre o recuperado, descontado à taxa `d`:

    LGD = 1 - R (1 - c) / (1 + d)^(lag / dias_ano)

Com `R = 50%`, `lag = 240` dias, `c = 15%`, `d = 14% a.a.` resulta **61,05%**, compatível com os 60% da config
(`resultados_chave.json["_lgd_economico"]`). Todos esses valores são **hipóteses**, não estimativas.

**LGD aleatória (Beta).** Cada default sorteia `LGD ~ Beta(a, b)` de média `m` (a da config) e desvio `s` (método dos momentos;
exige `s² < m(1-m)`). O simulador recebe o multiplicador `LGD/m` (média 1), de modo que a **EL é preservada** e só a dispersão muda.
Hipótese: sorteios independentes entre sacados e independentes do default. No CreditRisk+ usa-se um sorteio por (simulação, sacado),
exato quando P(2 ou mais defaults do mesmo sacado no ciclo) é desprezível.

**O que a sensibilidade mostra** (`outputs/lgd_sensibilidade.csv`): (i) EL e VaR escalam ~linearmente com a LGD determinística;
(ii) a incerteza de recuperação (Beta, desvio 15 e 25 p.p.) engorda a cauda sem mexer na EL. A conclusão **não** deve ser lida como
"LGD estocástica é irrelevante": a LGD **sistêmica** (pior justamente quando há muitos defaults) não está modelada e tende a pesar mais.

## 5. Validação interna

1. A pmf de Panjer reproduz **exatamente** média e variância da fórmula fechada.
2. O Monte Carlo do **mesmo** modelo (Gamma-Poisson) tem distribuição compatível com a pmf (KS abaixo do limite DKW).
3. A média do MC converge à EL a taxa `n^{-1/2}` (inclinação medida em `convergencia.csv`).
4. Teste de unidade: cópula gaussiana em carteira homogênea e grande reproduz o quantil de Vasicek (`tests/test_core.py`).
5. Teste de unidade: Panjer de um devedor reproduz a pmf de Poisson de `scipy`.

## 5.1 Validação adicionada na v0.2.0

6. `outputs/lgd_sensibilidade.csv`: a linha LGD = 60% (Panjer) é idêntica ao resultado principal; EL/LGD é constante; a LGD Beta preserva a EL dentro de 5 erros-padrão.
7. `correlacao_default_t` bate com a correlação de default estimada por Monte Carlo (`tests/test_v02.py`) e converge para a gaussiana com `nu` grande.
8. Análise de lote: a média da pmf de Panjer é igual à EL do lote; PD do prazo = `1-(1-PD)^(prazo/360)`; Gamma ≥ Poisson na cauda.
9. Módulo CVM: testado **apenas com arquivos sintéticos**; nenhum teste acessa a CVM e o schema real **não foi validado** (ver seção 7).

## 6. Análise de um lote de duplicatas de um cedente (`lote.py`, `scripts/analisar_lote.py`)

Objetivo: simular a decisão de compra ativa. Entrada: uma linha por duplicata (`templates/duplicatas_exemplo.csv`, **sintético**).

1. **Agregação por sacado:** face somada; prazo médio ponderado pela face; PD anual ponderada pela face (de `rating` ou de `pd_anual` explícita); LGD ponderada.
2. **PD do ciclo** de cada sacado: `p_i = 1 - (1 - PD_anual)^(prazo_i / dias_ano)` (aproxima o risco como o de um recebível único no prazo médio).
3. **Distribuição de perdas:** CreditRisk+ Poisson e Gamma por setor (Panjer, com unidade de banda ≈ face/10.000 em escala 1-2-5) e cópula gaussiana (Monte Carlo) como conferência.
4. **Deságio exigido no ciclo** (% do preço):

        desagio = (1-s) * custo_senior + s * retorno_alvo_sub + despesas + EL/preco + margem

   A EL é a média; a cauda (perda inesperada) é remunerada pelo `retorno_alvo_sub_anual` e limitada pelo tamanho da subordinada. `retorno_alvo_sub_anual`
   (30% a.a.) e `margem_alvo_anual` (2% a.a.) são **hipóteses** da config (`lote`), a calibrar com a política de quem compra.
5. **Subordinação mínima** com e sem excesso de spread, como na seção 4.
6. **Concentração:** maior sacado, top 5/10, HHI e número efetivo de sacados.

**Achado:** com poucos sacados a cauda é dominada pela concentração, não pela correlação setorial. O lote de exemplo (35 sacados, ~R$ 5,7 mi) tem
VaR 99,9% de ~6,9% da face no cenário base, contra ~2,0% da carteira sintética de 600 sacados.

**Não cobre:** coobrigação do cedente, diluição, fraude/duplicidade de lastro, risco de performance do cedente, revolvência.

## 7. Dados públicos e calibração com a CVM (`cvm.py`, `scripts/baixar_cvm.py`)

O Informe Mensal de FIDC (dados abertos da CVM) traz dados **agregados** por fundo/classe e competência: PL, carteira por segmento, inadimplência por faixa
de atraso, PDD, prazos, substituições/recompras e cotas por subclasse. **Não traz devedores nem duplicatas individuais.** A estratégia é
**calibrar o que for agregado com dado real e manter a micro-carteira sintética**: o dado público informa a ordem de grandeza (inadimplência, PDD,
subordinação), não os sacados.

* `baixar_cvm.py` baixa `inf_mensal_fidc_AAAAMM.zip`, filtra o CNPJ em todos os csv, grava `schema_report.csv` (colunas reais) e extrai indicadores por regex de `casos/*/config_cvm.json`.
* `indicadores_log.csv` registra qual coluna da CVM originou cada número. Regras sem colunas definidas geram `NaN` (nunca zero).
* **Status:** o layout mudou com a RCVM 175. As regex que acompanham o repositório são um **ponto de partida não validado**; o passo 1 de qualquer uso é conferir `schema_report.csv`.
* Para PD a partir de dados agregados o método correto é **roll-rate/vintage** sobre séries mensais (fluxo entre faixas de atraso), não a razão inadimplência/carteira, que é um estoque. Isso exige histórico: fundos novos têm poucas competências.

## 7.1 Cascata de três classes e ponte com dados observados (v0.3.0)

Com fração do PL `j` (júnior) e `m` (mezanino), a perda líquida `L' = max(L − XS, 0)` é absorvida na ordem
`júnior = min(L', j)`, `mezanino = min(max(L' − j, 0), m)`, `sênior = min(max(L' − j − m, 0), 1 − j − m)`; a soma é `min(L', 1)` (testado).
O ponto de **anexação** de cada classe é a soma das classes abaixo dela (júnior 0; mezanino `j`; sênior `j + m`).
A ponte (`scripts/analisar_caso.py`) aplica essa cascata, **sem XS** (leitura conservadora, não exige premissa de deságio), à pmf de perdas da carteira
sintética (CreditRisk+ Gamma) e compara a EL anual aproximada de cada classe (EL do ciclo × 6 ciclos, linear) com o excesso de retorno **observado** sobre o CDI.
Limites: a carteira simulada não é a do fundo; o prêmio observado já é líquido de perdas realizadas e do XS real; o fundo-exemplo é um FIC (duas camadas de subordinação, só uma modelada);
12 observações mensais não sustentam inferência estatística.

## 8. Limitações (declaradas)

* Carteira **sintética**; PDs por rating e `sigma_k` são premissas, não estimativas. O módulo CVM existe, mas **nenhum número empírico da CVM entra nos resultados**. O caso `via_multicredito` (v0.3.0) usa dados **observados de um relatório de rating de jun/2024**, separados dos resultados sintéticos.
* LGD: determinística no caso principal; incerteza de recuperação (Beta) só como sensibilidade, **independente** do default. LGD sistêmica (pior em crise) não está modelada.
* **Diluição** (devoluções/abatimentos) e **coobrigação** do cedente ainda não são modeladas.
* Um ciclo por vez: a **revolvência** não é modelada (cada ciclo é uma realização independente).
* Aproximação de Poisson para defaults de Bernoulli; setores independentes e um setor por sacado.
* Calendário simplificado: horizonte em dias corridos sobre base 360, sem calendário de dias úteis.
* Os retornos da subordinada (`ret_sub_ciclo`) decorrem do deságio de 2,5% a.m. e da alavancagem 80/20 escolhidos para o exemplo; não são projeção de retorno de fundo algum.

## 9. Referências para o trabalho final

* Credit Suisse First Boston (1997). *CreditRisk+: A Credit Risk Management Framework.*
* Gordy, M. (2000). A comparative anatomy of credit risk models. *Journal of Banking & Finance.*
* Koyluoglu, H. U.; Hickman, A. (1998). Reconcilable differences. *Risk.*
* Vasicek, O. (2002). The distribution of loan portfolio value. *Risk.*
* Li, D. X. (2000). On default correlation: a copula function approach. *Journal of Fixed Income.*

*(Confira os dados bibliográficos completos antes de citar no trabalho.)*
