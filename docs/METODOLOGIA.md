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
> é um teste de robustez à hipótese de cauda. Calibrar a cópula t pela mesma correlação de default é um próximo passo.

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

## 5. Validação interna

1. A pmf de Panjer reproduz **exatamente** média e variância da fórmula fechada.
2. O Monte Carlo do **mesmo** modelo (Gamma-Poisson) tem distribuição compatível com a pmf (KS abaixo do limite DKW).
3. A média do MC converge à EL a taxa `n^{-1/2}` (inclinação medida em `convergencia.csv`).
4. Teste de unidade: cópula gaussiana em carteira homogênea e grande reproduz o quantil de Vasicek (`tests/test_core.py`).
5. Teste de unidade: Panjer de um devedor reproduz a pmf de Poisson de `scipy`.

## 6. Limitações (declaradas)

* Carteira **sintética**; PDs por rating e `sigma_k` são premissas, não estimativas. Não há calibração com dados da CVM nesta versão.
* LGD constante; sem incerteza de recuperação.
* **Diluição** (devoluções/abatimentos) e **coobrigação** do cedente ainda não são modeladas.
* Um ciclo por vez: a **revolvência** não é modelada (cada ciclo é uma realização independente).
* Aproximação de Poisson para defaults de Bernoulli; setores independentes e um setor por sacado.
* Calendário simplificado: horizonte em dias corridos sobre base 360, sem calendário de dias úteis.
* Os retornos da subordinada (`ret_sub_ciclo`) decorrem do deságio de 2,5% a.m. e da alavancagem 80/20 escolhidos para o exemplo; não são projeção de retorno de fundo algum.

## 7. Referências para o trabalho final

* Credit Suisse First Boston (1997). *CreditRisk+: A Credit Risk Management Framework.*
* Gordy, M. (2000). A comparative anatomy of credit risk models. *Journal of Banking & Finance.*
* Koyluoglu, H. U.; Hickman, A. (1998). Reconcilable differences. *Risk.*
* Vasicek, O. (2002). The distribution of loan portfolio value. *Risk.*
* Li, D. X. (2000). On default correlation: a copula function approach. *Journal of Fixed Income.*

*(Confira os dados bibliográficos completos antes de citar no trabalho.)*
