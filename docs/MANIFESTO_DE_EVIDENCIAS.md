# Manifesto de evidências

Mapeia cada afirmação numérica (README, slides, artigo) ao arquivo que a sustenta e ao código que a gera.
Regra do repositório: **nenhum número vai para um slide sem uma linha nesta tabela.**

Reprodução: `python pipeline_fidc_creditrisk.py && python scripts/verify_output.py && python scripts/generate_figures.py`

## Natureza dos resultados

| Tipo | O que é neste repositório |
|---|---|
| **Empírico** | *Nada nesta versão.* A calibração com informes da CVM está no roteiro (ver README). |
| **Hipotético** | Carteira de duplicatas, PDs por rating, `sigma` dos setores, LGD, deságio, estrutura 80/20 e custos. |
| **Estimado** | `rho_ativos` das cópulas (calibrados por casamento de correlação de default). |
| **Calculado (analítico)** | Pmf de perdas do CreditRisk+ (Panjer), momentos exatos. |
| **Simulado** | Monte Carlo do CreditRisk+, cópula gaussiana e cópula t. |

## Mapa de evidências

| Afirmação | Arquivo | Gerado por |
|---|---|---|
| Composição da carteira sintética (face, PD, preço, EL por sacado) | `outputs/carteira_<cenario>.csv` | `portfolio.gerar_carteira`, `aplicar_cenario` |
| Parâmetros e seed da execução | `config_snapshot.json`, `outputs/run_metadata.json` (hash SHA-256) | `pipeline_fidc_creditrisk.py` |
| Distribuição de perdas do CreditRisk+ (Poisson e Gamma) | `outputs/pmf_crplus_<cenario>.csv` | `creditriskplus.pmf_perda` |
| EL, desvio, VaR e ES por modelo | `outputs/resumo_perdas.csv` | `metrics.resumo_distribuicao` |
| Curvas de quantis (figuras de cauda) | `outputs/curvas_quantis.csv` | `metrics.curva_quantis` |
| Calibração `rho` das cópulas | `outputs/calibracao_copula.csv` | `copula.calibrar_rho` |
| EL e perdas por cota (sênior/subordinada), com e sem excesso de spread | `outputs/cotas.csv` | `waterfall.estatisticas_cotas` |
| Curva EL da sênior × subordinação; subordinação mínima | `outputs/curvas_subordinacao.csv`, `outputs/resultados_chave.json` | `waterfall.curva_subordinacao`, `menor_subordinacao` |
| Regra de mercado (múltiplos da EL) | `outputs/regra_multiplos_el.csv` | `pipeline_fidc_creditrisk.py` |
| Validação: Panjer × Monte Carlo (KS), momentos exatos | `outputs/resultados_chave.json` | `ks_contra_pmf`, `momentos_analiticos` |
| Convergência n^(-1/2) do MC | `outputs/convergencia.csv`, `figures/fig_validacao_<cenario>.png` | `convergencia` |
| Figuras de cauda | `figures/fig_cauda_<cenario>.png` | `scripts/generate_figures.py` |
| Figuras de subordinação | `figures/fig_subordinacao_<cenario>.png` | `scripts/generate_figures.py` |

## Checagens automáticas (`scripts/verify_output.py`)

Config corresponde à execução; EL = soma(PD × face × LGD); massa das pmfs ≈ 1; média da pmf = EL;
média e variância da pmf = fórmula fechada; MC do CreditRisk+ com média dentro de 4 erros-padrão;
KS(Panjer, MC) abaixo do limite DKW; cauda Gamma ≥ Poisson; ES ≥ VaR; excesso de spread só reduz a EL da sênior;
EL da sênior não cresce com a subordinação.

## Testes de unidade (`tests/test_core.py`)

Panjer de um devedor = Poisson; bandas preservam EL; momentos da pmf = fórmula fechada (Poisson e Gamma);
cauda Gamma > Poisson; Panjer × MC do mesmo modelo; calibração casa correlação de default;
cópula sem correlação tem média/variância de Bernoulli independentes; cópula gaussiana → Vasicek em carteira
homogênea grande; identidades da cascata.
