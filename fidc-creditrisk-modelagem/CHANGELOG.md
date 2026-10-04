# Changelog

## [0.3.0] — 2026-10-03

Os resultados de `outputs/` (carteira sintética) permanecem **idênticos** aos da 0.2.0 (mesma seed e config; só muda `versao` em `run_metadata.json`).
`config_snapshot.json` continua em `"versao": "0.2.0"` de propósito (parâmetros inalterados; mudar o texto mudaria o hash da config).

**Novo**
- `waterfall.absorcao_tres_classes` / `estatisticas_tres_classes`: cascata sênior/mezanino/júnior (anexação, destacamento, P(perda), EL por classe).
- `observado.py`: dados observados por classe (retorno acumulado, 12M, último mês, % CDI, volatilidade, subordinação) e **auditoria** (acumulado recalculado × reportado).
- `scripts/analisar_caso.py`, `casos/via_multicredito/` (dados do FIC FIDC Via Multicrédito, jun/2024, com `PROVENIENCIA.md`), `casos/_modelo/` (molde), `casos/candidatos_btg_psf.csv`, `outputs_caso/`, `figures/caso_*`.
- `notebooklm_sources/07_caso_via_multicredito.md` (gerado dos CSVs). 18 testes novos (48 no total).

**Corrigido (auditoria)**
- `lote.agregar_por_sacado`: CSV com linhas só com `pd_anual` (rating vazio) passava na validação e quebrava com `KeyError: nan`. Agora usa o `pd_anual` e, se faltar PD, levanta erro claro.
- `verify_output.py`: a checagem "ES 99,9% não cai com a dispersão da LGD" usava tolerância fixa de 2% e **falhava no modo `--rapido`** (10 mil simulações), que é o que o CI executa; a tolerância agora escala com 1/√n.
- A entrada `[0.1.0]` abaixo dizia "cópula t calibrada por correlação de default"; isso só vale para a gaussiana (a calibração da t é inviável com ν pequeno, achado da 0.2.0).
- Texto: "nenhum dado empírico de fundo real" deixou de valer para o caso novo; README, visão geral e metodologia foram ajustados.

## [0.2.0] — 2026-10-03

- Os resultados do 0.1.0 permanecem idênticos (mesma seed, mesmos outputs); os novos parâmetros `mult_sev` são opcionais.
- `lgd.py`: LGD econômica (valor presente da recuperação) e LGD Beta; `outputs/lgd_sensibilidade.csv`.
- `copula.py`: `correlacao_default_t` e `calibrar_rho_t`; achado: com ν ≤ 30 não existe ρ que case a correlação de default do CreditRisk+; `outputs/t_*.csv`.
- `lote.py` + `scripts/analisar_lote.py`: análise de lote de duplicatas (EL, VaR/ES, deságio exigido, subordinação, concentração) e `templates/duplicatas_exemplo.csv` (sintético).
- `cvm.py` + `scripts/baixar_cvm.py`: download/filtro/schema/indicadores do Informe Mensal de FIDC (**schema real não validado**).
- `docs/ESCOLHA_DO_FUNDO.md`, `casos/pan_auto/`, `notebooklm_sources/` e `scripts/gerar_notebooklm_sources.py`.
- 20 testes novos (30 no total); `verify_output.py` com checagens de LGD e ν; figuras `fig_lgd_*` e `fig_nu_*`.

## [0.1.0] — 2026-10-03

- Esqueleto inicial do repositório.
- Carteira sintética de duplicatas agregadas por sacado (parametrizável em `config_snapshot.json`).
- CreditRisk+: bandas de exposição, recursão de Panjer (Poisson e Gamma-Poisson por setor), momentos analíticos.
- Cópula gaussiana e cópula t por setor, calibradas por correlação de default; referência analítica de Vasicek.
- Cascata de cotas (sênior/subordinada) com e sem excesso de spread; curva de subordinação.
- Pipeline com cenários `base` e `estresse`, verificação (`scripts/verify_output.py`) e figuras.
