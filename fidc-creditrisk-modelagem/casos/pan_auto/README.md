# Caso: PAN Auto FIDC (BTG Pactual)

Leia primeiro `docs/ESCOLHA_DO_FUNDO.md`: este fundo é do segmento financeiro (provável financiamento de veículos), **não** de duplicatas.

```bash
python scripts/baixar_cvm.py                 # precisa de internet; baixa 202603 e 202604
# sem rede? baixe os zips à mão de dados.cvm.gov.br e use:
python scripts/baixar_cvm.py --zips-locais pasta_com_zips/
```

Depois: abra `data/cvm/65473848000183/schema_report.csv`, confira cada regex de `config_cvm.json` (as de inadimplência e PDD estão
**vazias de propósito**) e só então confie em `indicadores_cvm.csv`.
