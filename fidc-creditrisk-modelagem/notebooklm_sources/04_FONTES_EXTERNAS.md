# Fontes externas

Classificação: **pública** (metodologia aberta), **secundária** (número citado por imprensa, sem acesso ao dado original),
**fonte única** (um único emissor, sem verificação independente).

## Dados de mercado usados no modelo

| Dado | Emissor | Onde foi lido | Classificação | Observação |
|---|---|---|---|---|
| Deságio médio, prazo médio, variação de VOP (set/2025–set/2026) | Quick Soft | [Fidc News, 07/10/2026](https://fidcnews.com.br/desagio-dos-recebiveis-sobe-para-2-92-ao-mes-em-setembro-e-registra-maior-alta-mensal-desde-setembro-de-2025); [Madeira Total, 11/06/2026](https://www.madeiratotal.com.br/desagio-em-operacoes-com-duplicatas-da-sinal-de-acomodacao-apos-seis-meses-de-queda/); [Brasil Inovador, 09/10/2026](https://brasilinovador.com.br/desagio-em-antecipacao-de-recebiveis-atinge-292-ao-mes-e-reflete-desaceleracao-economica/) | secundária, fonte única | Dados "agregados e anonimizados", extraídos das operações processadas pela plataforma. Amostra, ponderação e definição de deságio **não informadas**. A Quick Soft vende a infraestrutura que gera os dados. O Brasil Inovador declara produção com apoio de IA. |
| Contexto macro de setembro/2026 (PMI S&P Global, ICE FGV, Selic meta, produção industrial IBGE) | S&P Global, FGV/IBRE, Banco Central, IBGE | Fidc News, 07/10/2026 | secundária | Só registrado em `data/contexto_macro.csv`; ainda **não entra** no modelo. Verifique na fonte primária antes de citar em slides. |

Não lido: a matéria do Associated News sobre o prazo médio de julho bloqueia leitura automática; o valor de 46,50 dias
vem do Fidc News e do Brasil Inovador.

## Metodologia dos índices macro

* **ICE (FGV/IBRE):** [Indicadores de Confiança Empresarial — aspectos metodológicos (2017)](https://portalibre.fgv.br/sites/default/files/2020-03/indicadores-de-confian_a-empresarial-fgv-ibre_aspectos-metodol_gicos-06_2017-_1_.pdf).
  Média ponderada dos quatro índices setoriais, pesos pelo valor adicionado (IBGE), dessazonalização X-13 ARIMA-SEATS.
  O documento **não** traz a fórmula pergunta a pergunta nem a amostra.
* **PMI (S&P Global):** índice de difusão `P1 + 0,5·P2`; composto da indústria `0,30·Novos pedidos + 0,25·Produção + 0,20·Emprego + 0,15·(Prazo de entrega, invertido) + 0,10·Estoques`
  (pesos conforme [Wikipedia](https://en.wikipedia.org/wiki/Purchasing_Managers'_Index), fonte secundária; confirme na S&P Global).

## Referências acadêmicas e dados abertos (para o trabalho)

Os links abaixo vieram de buscas; o conteúdo **não foi lido integralmente** nesta sessão. Confira antes de citar.

* CreditRisk+ (CSFB, 1997): [página de referência com o documento técnico](http://www.defaultrisk.com/pp_model_21.htm).
* Gordy (2000), *A comparative anatomy of credit risk models*: [versão FEDS 1998-47](https://www.federalreserve.gov/pubs/feds/1998/199847/199847pap.pdf) e [SSRN](https://ssrn.com/abstract=148750).
* Bonelli, Schiozer, Vasconcelos (2021), *Redução de risco no crédito com duplicatas* (FGV EAESP): [PDF](https://eaesp.fgv.br/sites/default/files/legacy/pesquisa-eaesp-files/arquivos/sch2_bonelli_schiozer_vasconcelos_2021_reducao-de-risco-no-credito-co_62882.pdf).
* CVM — [Informes Mensais de FIDC (dados abertos)](https://dados.cvm.gov.br/dataset/fidc-doc-inf_mensal), com dicionário de dados, para a calibração empírica futura.
