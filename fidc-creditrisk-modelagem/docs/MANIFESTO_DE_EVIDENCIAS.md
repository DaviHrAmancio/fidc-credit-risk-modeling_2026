# Manifesto de evidências

Mapeia cada afirmação numérica (README, slides, artigo) ao arquivo que a sustenta e ao código que a gera.
Regra do repositório: **nenhum número vai para um slide sem uma linha nesta tabela.**

Reprodução: `python pipeline_fidc_creditrisk.py && python scripts/verify_output.py && python scripts/generate_figures.py`

## Natureza dos resultados

| Tipo | O que é neste repositório |
|---|---|
| **Empírico** | *Nada nesta versão.* O módulo CVM existe, mas nenhum número da CVM entra nos resultados. |
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
| Sensibilidade à LGD (determinística e Beta) | `outputs/lgd_sensibilidade.csv`, `figures/fig_lgd_<cenario>.png` | `pipeline_fidc_creditrisk.bloco_lgd`, `lgd.sorteador_beta` |
| LGD econômica implícita (61%) | `outputs/resultados_chave.json["_lgd_economico"]` | `lgd.lgd_economico` |
| Cópula t: piso de correlação e viabilidade da calibração | `outputs/t_calibracao_nu.csv` | `copula.calibrar_rho_t`, `correlacao_default_t` |
| Cauda × ν da cópula t | `outputs/t_sensibilidade_nu.csv`, `figures/fig_nu_<cenario>.png` | `pipeline_fidc_creditrisk.bloco_nu` |
| Lote de exemplo (sintético): EL, VaR, deságio, subordinação, concentração | `outputs_lote/exemplo_sintetico/*` | `scripts/analisar_lote.py`, `lote.analisar_lote` |
| Tabelas numéricas para slides | `notebooklm_sources/02_resultados.md`, `03_lote_exemplo.md` | `scripts/gerar_notebooklm_sources.py` |
| Retorno 12M, último mês, PL e subordinação por classe (OBSERVADO, jun/2024) | `outputs_caso/via_multicredito/metricas_por_classe.csv`, `subordinacao_mensal.csv` | `scripts/analisar_caso.py` + `src/fidc_risk/observado.py`; dados em `casos/via_multicredito/dados_observados.csv` (proveniência em `PROVENIENCIA.md`) |
| Auditoria da transcrição (recalculado × reportado) | `outputs_caso/via_multicredito/auditoria_acumulado.csv` | `observado.auditoria_acumulado` |
| Ponte com o modelo (SIMULADO): EL/anexação por classe | `outputs_caso/via_multicredito/ponte_modelo_por_classe.csv`, `ponte_modelo_carteira.csv`, `curva_absorcao.csv` | `waterfall.absorcao_tres_classes` + `scripts/analisar_caso.py` |
| Indicadores da CVM (quando você rodar) | `data/cvm/<cnpj>/indicadores_cvm.csv` + `indicadores_log.csv` | `scripts/baixar_cvm.py` (**regex não validadas**) |

## Checagens automáticas (`scripts/verify_output.py`)

Config corresponde à execução; EL = soma(PD × face × LGD); massa das pmfs ≈ 1; média da pmf = EL;
média e variância da pmf = fórmula fechada; MC do CreditRisk+ com média dentro de 4 erros-padrão;
KS(Panjer, MC) abaixo do limite DKW; cauda Gamma ≥ Poisson; ES ≥ VaR; excesso de spread só reduz a EL da sênior;
EL da sênior não cresce com a subordinação; (v0.2.0) EL linear na LGD, linha LGD=60% = resultado principal, LGD Beta preserva a EL, VaR da cópula t cai com ν, piso de correlação > alvo em ν=5, LGD econômica ≈ LGD da config.

(v0.3.0, se `outputs_caso/` existir) auditoria do acumulado dentro da tolerância; PL das classes soma 100%; conservação da cascata de 3 classes na curva de absorção;
soma da EL das classes = EL da carteira (sem XS).

## Testes de unidade (`tests/test_core.py`)

Panjer de um devedor = Poisson; bandas preservam EL; momentos da pmf = fórmula fechada (Poisson e Gamma);
cauda Gamma > Poisson; Panjer × MC do mesmo modelo; calibração casa correlação de default;
cópula sem correlação tem média/variância de Bernoulli independentes; cópula gaussiana → Vasicek em carteira
homogênea grande; identidades da cascata.


## Testes da v0.2.0 (`tests/test_v02.py`)

LGD econômica e Beta; LGD aleatória preserva EL e aumenta dispersão (cópula e CreditRisk+); correlação de default da cópula t × Monte Carlo e × gaussiana; calibração t inviável/viável; lote (agregação, PD do prazo, média da pmf = EL, validação de entrada, datas); módulo CVM com **arquivos sintéticos** (nenhum teste acessa a rede).

## Testes da v0.3.0 (`tests/test_v03.py`)

Cascata de 3 classes (conservação da perda, ordem de absorção, XS, redução ao caso de 2 classes, validação, EL por classe numa pmf conferida à mão);
dados observados (validação do CSV, soma do PL, retorno composto, métricas conferidas com os valores reportados pela fonte, subordinação, fundo sem mezanino, rejeição de dados ruins);
correção do lote (linhas mistas rating/`pd_anual`, erro claro quando não há PD).
