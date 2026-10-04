# Risco de crédito em FIDCs de duplicatas — CreditRisk+, cópulas e subordinação

Repositório de **código, metodologia, outputs e artefatos reprodutíveis** do estudo sobre perda esperada, perda
inesperada e dimensionamento da subordinação em FIDCs de recebíveis (duplicatas), usando o **CreditRisk+** como
modelo principal e **cópulas gaussiana e t** (família Merton/Vasicek) como comparativo.

> **Transparência:** o objetivo é permitir que cada número apresentado seja rastreado até a execução
> computacional que o produziu. Veja `docs/MANIFESTO_DE_EVIDENCIAS.md`.

> **Natureza dos dados:** a carteira dos resultados principais (`outputs/`) é **sintética (hipotética)**. A `v0.3.0` acrescenta um
> **caso à parte** (`casos/via_multicredito`, `outputs_caso/`) com dados **observados** de um FIC FIDC administrado pela BTG Pactual
> Serviços Financeiros (fonte externa, **jun/2024**, defasado), sempre rotulado como OBSERVADO e separado do que é simulado.
> Nenhum número da CVM entra nos resultados (o módulo CVM segue sem schema validado).

## Pergunta de pesquisa

O deságio cobrado na compra de duplicatas precisa cobrir `custo do dinheiro + perda esperada + custos + margem`.
A perda esperada (EL) é a **média** da distribuição de perdas; o **tamanho da subordinação** depende da **cauda**.
O estudo mede como a escolha do modelo (Poisson, Gamma por setor, cópulas) muda a cauda e, com ela, a subordinação
necessária para proteger a cota sênior.

## Snapshot (`v0.2.0`; os números do `v0.1.0` foram preservados bit a bit)

- seed: **20261003**; 600 sacados; ciclo de 60 dias; LGD 60%; 100.000 simulações por modelo;
- PL ≈ R$ 98,9 mi, face ≈ R$ 103,9 mi (deságio de 5,06% sobre o preço = 2,5% a.m. por 2 meses);
- estrutura de exemplo: 80% sênior (CDI + 3%), 20% subordinada, despesas de 2% a.a.;
- cenários: `base` e `estresse` (PD × 3 e volatilidade dos fatores setoriais × 1,5).

### Resultados-chave (perda de crédito do ciclo, % da face)

| Cenário | Modelo | EL | VaR 99% | VaR 99,9% | ES 99,9% |
|---|---|---|---|---|---|
| base | CreditRisk+ Poisson | 0,315 | 1,28 | 1,82 | 2,03 |
| base | **CreditRisk+ Gamma (setores)** | 0,315 | 1,39 | 2,00 | 2,25 |
| base | Cópula gaussiana | 0,316 | 1,37 | 1,93 | 2,18 |
| base | Cópula t (ν = 5)* | 0,312 | 4,71 | 11,49 | 14,07 |
| estresse | CreditRisk+ Poisson | 1,004 | 2,49 | 3,20 | 3,48 |
| estresse | **CreditRisk+ Gamma (setores)** | 1,004 | 3,64 | 5,15 | 5,80 |
| estresse | Cópula gaussiana | 1,005 | 3,41 | 4,81 | 5,47 |
| estresse | Cópula t (ν = 5)* | 1,014 | 9,15 | 16,55 | 19,74 |

\* A cópula t usa o **mesmo `rho` de ativos** das gaussiana, mas tem correlação de default e dependência de cauda
muito maiores; ela é um teste de robustez, **não** um comparativo à mesma correlação de default (ver `docs/METODOLOGIA.md`, seção 3).

Leituras que o snapshot sustenta:

1. A **EL é praticamente idêntica** entre os modelos (por construção); o que muda é a **cauda**.
2. Ignorar a correlação setorial (Poisson puro) **subestima** o VaR 99,9% em ~9% no cenário base e ~38% no estresse, em relação ao Gamma por setor.
3. Com a correlação de default casada, **CreditRisk+ Gamma e cópula gaussiana ficam próximos** (diferença de 4–7% no VaR 99,9%), como a literatura de comparação de modelos sugere.
4. A conclusão sobre subordinação é **muito sensível à hipótese de cauda** (cópula t).

### Subordinação mínima (EL da sênior ≤ 0,01% por ciclo, % do PL)

| Cenário | Modelo | com excesso de spread | sem excesso de spread |
|---|---|---|---|
| base | CreditRisk+ Poisson / Gamma / cópula gaussiana | 0,0% / 0,0% / 0,0% | 1,5% / 1,5% / 1,5% |
| base | Cópula t | 6,5% | 8,5% |
| estresse | CreditRisk+ Poisson | 0,5% | 2,5% |
| estresse | CreditRisk+ Gamma | 1,5% | 4,0% |
| estresse | Cópula gaussiana | 1,5% | 3,5% |
| estresse | Cópula t | 12,0% | 14,5% |

Regra de mercado "subordinação = k × EL" (`outputs/regra_multiplos_el.csv`): base 1,0–1,7% do PL; estresse 3,2–5,3% (k = 3 a 5).
O excesso de spread do ciclo (≈ 2,6% do PL nas premissas) é o primeiro colchão; **na leitura sem XS** (conservadora) a subordinação
mínima é a que fica comparável com a regra de múltiplos.

### Validação da implementação

| Checagem | Base | Estresse |
|---|---|---|
| Distância KS entre Panjer e Monte Carlo do mesmo modelo (limite DKW α=10⁻³: 0,0062) | 0,0021 | 0,0034 |
| Inclinação log-log do RMSE da EL do MC (referência teórica −0,500) | −0,491 | −0,472 |
| Média e variância da pmf vs. fórmula fechada | coincidem | coincidem |

![Cauda — estresse](figures/fig_cauda_estresse.png)
![Subordinação — estresse](figures/fig_subordinacao_estresse.png)

## Novidades da v0.2.0

**1. LGD** (`lgd.py`, `outputs/lgd_sensibilidade.csv`). EL e VaR escalam ~linearmente com a LGD (VaR 99,9% do CreditRisk+ Gamma: 1,33% a 2,67% da face no base para LGD de 40% a 80%).
LGD Beta (média 60%, desvio 25 p.p.) preserva a EL e eleva o VaR 99,9% de 2,03% para 2,29% (MC do CreditRisk+, base). LGD **sistêmica** não está modelada.

**2. A cópula t não é calibrável com ν pequeno** (`outputs/t_calibracao_nu.csv`). O fator W comum impõe um piso de correlação de default (≈ 0,060 com ν = 5; ≈ 0,006 com ν = 30)
acima do alvo do CreditRisk+ (≈ 0,003). Só ν = 100 é calibrável. O VaR 99,9% (base) cai de 11,49% (ν = 5) para 2,24% (ν = 100). Isso fecha o item do roteiro "calibrar a cópula t".

**3. Análise de lote de duplicatas** (`scripts/analisar_lote.py`, `templates/duplicatas_exemplo.csv`). Dado um CSV de duplicatas, devolve EL, VaR/ES, deságio exigido, subordinação mínima e concentração.
No lote sintético de exemplo (35 sacados) o VaR 99,9% é 6,9% da face contra 2,0% na carteira de 600 sacados: **a granularidade domina a cauda**.

**4. Dados abertos da CVM** (`cvm.py`, `scripts/baixar_cvm.py`). Download, filtro por CNPJ, relatório de schema e indicadores rastreáveis. **Testado só com arquivos sintéticos; o schema real não foi validado** (veja `docs/METODOLOGIA.md`, seção 7).

**5. Escolha do fundo-exemplo** (`docs/ESCOLHA_DO_FUNDO.md`). O PAN Auto FIDC (BTG) é do segmento financeiro, não de duplicatas, e é recente; o documento explica o descasamento e as opções.

## Novidades da v0.3.0

**1. Caso observado: FIC FIDC Via Multicrédito** (`casos/via_multicredito/`, `outputs_caso/via_multicredito/RELATORIO.md`). PL, rentabilidade de 12 meses e do último mês
**por classe** (sênior, mezanino, júnior) em jul/2023 a jun/2024, transcritos de relatório de rating (Austin, 09/08/2024). Retorno 12M: sênior 14,45%, mezanino 15,54%, júnior 21,62%
contra CDI de 11,68%; a júnior teve 2 meses negativos, a sênior e a mezanino nenhum. Subordinação total de 57,4% do PL em jun/2024. Os 12 retornos mensais recompõem o acumulado
reportado pela fonte (diferença máxima de 0,0105 pp): isto valida a transcrição, não a fonte.

**2. Ponte com o modelo de perdas** (`waterfall.absorcao_tres_classes`, `scripts/analisar_caso.py`). Cascata de 3 classes aplicada à distribuição de perdas da carteira **sintética**:
com a subordinação observada, a sênior e a mezanino não perdem nas simulações (anexação em 27× o VaR 99,9% no base e 10,6× no estresse para a sênior), logo o excesso delas sobre o CDI
**não é explicado pela perda esperada de crédito do modelo**; o prêmio da júnior (8,9 pp) é da ordem da EL anual aproximada dela no base (9,8%) e menor no estresse (31,3%), sem excesso de spread.
É ordem de grandeza, não previsão: ver as ressalvas no relatório.

**3. Auditoria do código** (ver `CHANGELOG.md`): corrigido o `KeyError` do lote com linhas mistas (rating vazio + `pd_anual`) e a checagem de LGD que **fazia o CI falhar** no modo `--rapido`.

**4. Candidatos BTG PSF** (`casos/candidatos_btg_psf.csv`, `docs/ESCOLHA_DO_FUNDO.md`) e molde reutilizável (`casos/_modelo/`) para repetir a análise com outro fundo.

```bash
python scripts/analisar_caso.py                       # caso Via Multicrédito (precisa de outputs/ gerado pelo pipeline)
python scripts/analisar_caso.py --caso casos/_modelo/config_caso.json --dados meu_fundo.csv
```

## Como analisar um lote

```bash
python scripts/analisar_lote.py templates/duplicatas_exemplo.csv --nome exemplo
python scripts/analisar_lote.py meu_lote.csv --nome cedente_x --desconto-mensal 0.03 --sims 100000
```

Colunas: `sacado_id, valor_face, setor`, `prazo_dias` (ou `data_cessao` + `vencimento`) e `rating` (A–D) ou `pd_anual`; opcional `lgd`. Saída em `outputs_lote/<nome>/RELATORIO.md`.

## Como reproduzir

Python 3.11+ recomendado.

```bash
python -m pip install -r requirements.txt
python -m pytest -q                       # testes de unidade
python pipeline_fidc_creditrisk.py        # ~45 s; use --rapido para uma execução curta
python scripts/verify_output.py           # invariantes dos outputs
python scripts/generate_figures.py        # figuras de auditoria
python scripts/analisar_caso.py           # caso observado (v0.3.0)
python scripts/gerar_notebooklm_sources.py  # atualiza fontes numéricas dos slides
```

## Estrutura

```
fidc-creditrisk-modelagem/
├── pipeline_fidc_creditrisk.py     # orquestra cenários, modelos e outputs
├── config_snapshot.json            # TODOS os parâmetros e a seed
├── requirements.txt
├── src/fidc_risk/
│   ├── portfolio.py                # carteira sintética, cenários, PD do ciclo
│   ├── creditriskplus.py           # bandas, recursão de Panjer, setores Gamma, MC do mesmo modelo
│   ├── copula.py                   # cópulas gaussiana/t por setor, calibração, Vasicek
│   ├── waterfall.py                # cascata sênior/subordinada (2 classes) e sênior/mezanino/júnior (3 classes)
│   ├── observado.py                # dados observados por classe: retorno, PL, subordinação, auditoria
│   ├── metrics.py                  # EL, VaR, ES (discreto e amostral)
│   ├── lgd.py                      # LGD econômica e LGD Beta
│   ├── lote.py                     # análise de lote de duplicatas
│   └── cvm.py                      # dados abertos da CVM (informe mensal)
├── tests/                          # testes de unidade
├── scripts/                        # verify_output.py, generate_figures.py, analisar_lote.py, analisar_caso.py
├── outputs/                        # CSV/JSON gerados (ver manifesto)
├── figures/
├── docs/                           # METODOLOGIA, MANIFESTO_DE_EVIDENCIAS, ESCOLHA_DO_FUNDO
├── templates/ casos/ outputs_lote/ # lote de exemplo; casos (PAN Auto, Via Multicrédito, molde); relatório do exemplo
├── outputs_caso/                   # saídas do caso observado (v0.3.0)
├── notebooklm_sources/             # fontes para gerar slides
├── .github/workflows/ci.yml
├── CITATION.cff
└── CHANGELOG.md
```

## Roteiro

- [x] ~~Cópula t calibrada pela mesma correlação de default~~: **inviável com ν pequeno** (ver acima); resta decidir outra estrutura de cauda.
- [x] LGD estocástica independente (Beta).
- [ ] Calibração agregada com os **informes mensais da CVM** em fundo de duplicatas com histórico longo (validar regex contra `schema_report.csv`).
- [ ] LGD **sistêmica** (correlacionada com o fator de default).
- [ ] **Diluição** como segundo componente de perda; **coobrigação** do cedente; **revolvência** e gatilhos.
- [ ] Cópula de Clayton como terceiro comparativo.
- [ ] Artigo.

## Autor

**Davi Henrique de Souza Amâncio** — Licenciatura em Matemática, IFC Campus Camboriú.

## Aviso

Finalidade acadêmica e educacional. Os resultados vêm de uma carteira sintética e de premissas ilustrativas; não constituem
estimativa de perdas de fundo real, recomendação de investimento nem oferta de produto financeiro.
