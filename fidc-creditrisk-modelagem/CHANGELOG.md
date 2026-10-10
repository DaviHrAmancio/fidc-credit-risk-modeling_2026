# Changelog

## [0.2.0] — 2026-10-09

- **Dados de mercado:** `data/` com a série da Quick Soft (deságio, prazo médio, variação de VOP), contexto macro
  (PMI, ICE/FGV, Selic, produção industrial) e a lista de fontes de cada ponto. Hash dos arquivos em `run_metadata.json`.
- **Calibração:** deságio de 2,92% a.m. e prazo médio de 50,8 dias (setembro/2026); ciclo de 50,8 dias; CDI = Selic meta − 0,10 p.p.
- **Novo módulo `mercado.py`:** decomposição `receita de deságio = funding + custos + EL + margem`, capacidade de perda,
  PD de equilíbrio e decomposição da variação em efeito de taxa × efeito de prazo.
- **Novos outputs:** `decomposicao_taxa.csv`, `efeito_taxa_prazo.csv`, `tabelas_readme.md`.
- **README gerado:** `scripts/atualizar_readme.py` copia as tabelas do pipeline; `verify_output.py` confere a igualdade.
- **Pacote NotebookLM:** `notebooklm_sources/` (gerado por `scripts/gerar_pacote_notebooklm.py`) e `docs/GUIA_NOTEBOOKLM.md`.
- CI roda o pipeline completo.

## [0.1.0] — 2026-10-03

- Esqueleto inicial do repositório.
- Carteira sintética de duplicatas agregadas por sacado (parametrizável em `config_snapshot.json`).
- CreditRisk+: bandas de exposição, recursão de Panjer (Poisson e Gamma-Poisson por setor), momentos analíticos.
- Cópula gaussiana e cópula t por setor, calibradas por correlação de default; referência analítica de Vasicek.
- Cascata de cotas (sênior/subordinada) com e sem excesso de spread; curva de subordinação.
- Pipeline com cenários `base` e `estresse`, verificação (`scripts/verify_output.py`) e figuras.
