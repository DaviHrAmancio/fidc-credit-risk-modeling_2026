# Caso ilustrativo: PAN Auto FIDC (BTG Pactual) — leitura crítica

Fundo escolhido como exemplo de FIDC grande: PAN Auto FIDC RL, CNPJ 65.473.848/0001-83, código CVM 226182, gestora BTG Pactual Gestora de Investimentos
Alternativos, administradora BTG Pactual Serviços Financeiros DTVM, início em 18/03/2026, em funcionamento normal (fidcs.com.br, consultado em 03/10/2026).
Um agregador de fundos o lista no segmento financeiro, com 1 cotista e PL de ordem de R$ 19 bi (dado de agregador, a confirmar na CVM).

**Por que este fundo exige cautela como exemplo de FIDC de duplicatas:**
- O segmento "Financeiro" e o nome sugerem financiamento de veículos (inferência pelo nome; a confirmar no regulamento), com devedores pessoas físicas pulverizados,
  não sacados empresariais concentrados.
- Fundo iniciado em 03/2026: poucas competências no Informe Mensal público; não permite calibrar PD por roll-rate ou vintage.
- Cota com 1 cotista: a subordinação pode refletir estrutura contratual interna.
- Em carteira muito granular, o caso limite natural é Vasicek/ASRF, e a concentração (achado central do lote de duplicatas) deixa de ser o problema.

**Uso no trabalho:** estudo de contraste ("o que muda quando o ativo não é duplicata") e demonstração do pipeline de dados da CVM. Nenhum número do PAN Auto
entra nos resultados: o download dos informes exige acesso à internet e as regras de extração de colunas ainda precisam ser validadas contra o layout real.
Recomenda-se um segundo fundo, multicedente de duplicatas e com histórico longo, para o caso principal.
