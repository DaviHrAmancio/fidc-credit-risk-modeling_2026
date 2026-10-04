# Proveniência dos dados: FIC FIDC Via Multicrédito

Tudo em `dados_observados.csv` foi **transcrito à mão** da tabela do relatório de monitoramento de rating da
Austin Rating de **09/08/2024** (competências jul/2023 a jun/2024). Nenhum número foi estimado ou gerado pelo modelo.

| Coluna | Onde está na fonte |
|---|---|
| `cdi_pct_mes`, `rent_*_pct` | página 4, tabela "Rentabilidade Mensal do PL (em %)": CDI (%), rentabilidade mensal de sênior, mezanino e júnior |
| `acum_*_reportado_pct` | mesma tabela, colunas "Acum. (%)" (usadas só para auditoria) |
| `pl_*_mil`, `pl_total_mil` | página 3, tabela "Posição do PL (R$ Mil)" (valor total por classe e PL do fundo, fim do mês) |
| cotistas, ratings, benchmarks, subordinação mínima, carteira | páginas 1 e 2 (resumo do fundo e fundamentos dos ratings) |

## Conferências feitas (reproduzíveis: `python scripts/analisar_caso.py` e `pytest tests/test_v03.py`)

- Os 12 retornos mensais, compostos, reproduzem o acumulado reportado pela fonte com diferença máxima de 0,0105 pp
  (arredondamento): isto valida a **transcrição**.
- A soma do PL das três classes bate com o PL total (tolerância R$ 1,5 mil) e a subordinação recalculada (57,4% no total,
  20,2% a júnior em jun/2024) bate com a coluna da fonte.
- Isto **não** valida a fonte: a agência declara que não audita as informações que recebe (administrador/CVM).

## Limites e inconsistências que você deve conhecer

1. **Defasagem.** O dado mais recente é jun/2024. Não há aqui nenhuma informação de 2025 ou 2026 sobre o fundo; ele pode
   ter mudado de estrutura, gestora ou carteira, ou ter sido encerrado. Antes de citar como atual, confira na CVM
   (Informe Mensal) e no Fundos.NET.
2. **Administradora.** O cabeçalho do relatório diz "BTG Pactual Serviços Financeiros S.A." e a tabela de PL cita a mesma
   como fonte, mas a nota regulatória nº 6 do mesmo relatório menciona "Singulare Corretora ... (Administrador)". Parece
   resquício de modelo de texto, porém **não foi esclarecido**. Confirme no cadastro da CVM.
3. **Varejo.** A fonte informa 770 cotistas na sênior e 660 nas subordinadas, **sem perfil** (pessoa física, jurídica ou
   fundo). Não é possível afirmar que a sênior seja destinada ao varejo. Pela RCVM 175 as subclasses seniores de FIDC podem
   ter varejo, mas a regra do regulamento deste fundo específico não foi lida.
4. **Quem são os titulares das subordinadas.** O relatório traz só a contagem. O Informe Mensal da CVM separa cotistas por
   tipo (PF, PJ, fundos, previdência etc.) e por classe/subclasse, mas **não publica nomes**; a identidade do titular
   da júnior (por exemplo, originador/gestor) só aparece em regulamento, prospecto ou lâmina quando existe essa informação.
5. **É um FIC.** O fundo investe em cotas de outros FIDCs (97,3% do PL em jun/2024; 75,3% em um único FIDC). Há duas
   camadas de subordinação (a do fundo e a dos FIDCs investidos); a ponte com o modelo trata só a camada do fundo.
6. Os benchmarks (CDI + 2,5% e + 3,5%) e a subordinação mínima são os **do regulamento de 23/02/2022 segundo a fonte**.
