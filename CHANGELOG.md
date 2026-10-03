# Changelog

## [0.1.0] — 2026-10-03

- Esqueleto inicial do repositório.
- Carteira sintética de duplicatas agregadas por sacado (parametrizável em `config_snapshot.json`).
- CreditRisk+: bandas de exposição, recursão de Panjer (Poisson e Gamma-Poisson por setor), momentos analíticos.
- Cópula gaussiana e cópula t por setor, calibradas por correlação de default; referência analítica de Vasicek.
- Cascata de cotas (sênior/subordinada) com e sem excesso de spread; curva de subordinação.
- Pipeline com cenários `base` e `estresse`, verificação (`scripts/verify_output.py`) e figuras.
