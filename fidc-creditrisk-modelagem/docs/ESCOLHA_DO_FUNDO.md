# Escolha do fundo-exemplo: PAN Auto FIDC (BTG Pactual)

Consulta feita em **03/10/2026**. Este documento separa (1) o que foi verificado, (2) o que **não** foi possível obter,
(3) por que o fundo pode não ser o melhor para uma tese de **duplicatas**, e (4) o que fazer a respeito.

## 1. O que foi verificado

| Item | Valor | Fonte |
|---|---|---|
| Nome | PAN AUTO FUNDO DE INVESTIMENTO EM DIREITOS CREDITÓRIOS RESPONSABILIDADE LIMITADA | fidcs.com.br (página do fundo) |
| CNPJ / código CVM | 65.473.848/0001-83 / 226182 | idem |
| Situação | Em Funcionamento Normal | idem |
| Início | **18/03/2026** | idem |
| Gestora / administradora | BTG Pactual Gestora de Investimentos Alternativos Ltda. / BTG Pactual Serviços Financeiros S/A DTVM | idem |
| Segmento, PL, cotistas | "Financeiro"; PL "R$ 19 bi"; **1 cotista** | Mais Retorno (listagem de fundos da gestora). **Agregador; data do dado desconhecida; confira na CVM.** |
| Último informe mensal público visto | competência 202604 (publicado em jul/2026) | listagem do diretório de dados abertos da CVM, na data da consulta |

Contexto (não confirmado como lastro do fundo): o BTG concluiu a incorporação do Banco Pan em 23/01/2026, e o
financiamento de veículos é a principal linha do Pan (Moody's Local, jul/2025). **A ligação entre o PAN Auto FIDC e uma carteira de veículos do
Pan é inferência pelo nome**; só o regulamento e o informe confirmam.

## 2. O que NÃO foi possível obter (e por quê)

* **Carteira, inadimplência, PDD, subordinação do PAN Auto:** a página do fundo carrega os números por JavaScript e o ambiente em que este repositório foi
  montado **não tinha acesso de rede aos arquivos da CVM**. Nenhum número do PAN Auto entra nos resultados deste repositório.
  Para obtê-los: `python scripts/baixar_cvm.py` (precisa de internet) e depois conferir `data/cvm/65473848000183/schema_report.csv`.
* **Devedores individuais:** o Informe Mensal da CVM é **agregado** (por faixa de atraso, segmento, subclasse). Ele não traz devedores nem duplicatas individuais, e
  em geral esse dado não é público (sigilo, LGPD, concorrência). Portanto **a micro-carteira será sempre sintética**; o dado real calibra os agregados.
* **API da fidcs.com.br:** existe API/MCP, mas é paga (plano Premium); os dados de origem são os mesmos da CVM, que são abertos.

## 3. O descasamento com a tese (duplicatas)

| | Tese do trabalho | PAN Auto (pelo que se sabe) |
|---|---|---|
| Ativo | duplicatas (recebíveis comerciais curtos) | segmento "Financeiro", provavelmente financiamento de veículos (a confirmar) |
| Devedor | sacado empresa, carteira **concentrada** | pessoas físicas, carteira **pulverizada** |
| Prazo | ~30-90 dias, ciclos repetidos | até dezenas de meses, amortizante (a confirmar) |
| LGD | recuperação da duplicata | depende da garantia (alienação fiduciária do veículo) |
| Cotistas | vários | **1** (estrutura que sugere cessão do originador/BTG) |
| Histórico CVM | anos | **~2 competências** (fundo iniciado em 03/2026) |

Consequências para o modelo:

1. **Concentração deixa de ser o problema.** Com milhares de devedores pequenos, a cauda é quase toda sistêmica e o caso limite natural é o **Vasicek/ASRF**
   (já implementado como referência), não o CreditRisk+ por sacado. O achado do lote de exemplo ("poucos sacados → a cauda é concentração") **não se aplica**.
2. **Calibração empírica fraca:** PD por *roll-rate* ou *vintage* exige séries; com 2 competências só dá para observar **estoque** de inadimplência.
3. **Cota única:** com 1 cotista, a "subordinação" do informe pode refletir uma estrutura contratual interna, não a de um fundo aberto a terceiros.

## 4. Opções

* **A (recomendada): dois casos.** Manter o PAN Auto como **estudo de contraste** ("o que muda quando o ativo não é duplicata") e escolher **um fundo de
  duplicatas multicedente** para o caso principal. Critérios: segmentos "Comercial", "Industrial", "Serviços" e/ou "Factoring" dominantes; histórico ≥ 24 meses;
  mais de um cotista; subclasses sênior/mezanino/subordinada. A plataforma fidcs.com.br tem a demonstração pública de um fundo (RNX FIDC, jul/2026) com carteira
  mista de segmentos e 3 subclasses, que **vale avaliar como candidato** (não foi verificado aqui se é majoritariamente duplicata).
* **B:** usar só o PAN Auto e **reformular a tese** para FIDC de financiamento de veículos (muda o modelo: carteira granular, LGD com garantia, amortização).
* **C:** manter a tese de duplicatas e usar o PAN Auto apenas para demonstrar o *pipeline de dados* (download, filtro, schema, indicadores), declarando
  explicitamente que o fundo **não** é de duplicatas.

## 5. Onde achar cada tipo de informação

| Informação | Público? | Onde |
|---|---|---|
| PL, carteira por segmento, inadimplência por faixa, PDD, prazos, subclasses, rentabilidade | Sim (agregado) | CVM dados abertos (Informe Mensal de FIDC); fidcs.com.br espelha |
| Concentração por cedente | Parcial | painel na fidcs.com.br; confirmar a fonte nas colunas do schema |
| Critérios de elegibilidade, limites de concentração, subordinação mínima, gatilhos | Sim | regulamento e anexos da classe (Fundos.NET/CVM) |
| Lastro detalhado, ticket médio, ágio, estrutura-alvo | Às vezes | relatórios de rating (Moody's Local, S&P, Fitch), prospectos e lâminas de oferta |
| Devedores / duplicatas individuais | Em geral não | — |

## 6. Atualização v0.3.0: fundos da BTG Pactual Serviços Financeiros (PSF) com classes visíveis

Pedido: um fundo administrado pela BTG PSF, preferencialmente com cota sênior aberta ao varejo e com registro de quem detém mezanino e subordinada, comparando
**PL, rentabilidade 12M e rentabilidade do último mês** entre sênior e subordinadas. Consulta em 03/10/2026 por busca web (o ambiente de execução **segue sem acesso à CVM**).
Tabela completa em `casos/candidatos_btg_psf.csv`; `n/d` = não verificado.

| Fundo | PL | Classes visíveis | Cotistas | Rentab. por classe | Veredito |
|---|---|---|---|---|---|
| **FIC FIDC Via Multicrédito** | R$ 166,2 mi (jun/24) | sênior, mezanino, júnior | 770 sênior; 660 subordinados | sim, 12 meses por classe (jul/23 a jun/24) | **Usado** como caso-exemplo; dado **defasado** (2024) |
| BRM Carbyne Crédito Estruturado FIC FIDC RL | ~R$ 148 mi (Tradar) | só sênior (subordinada sem cotistas) | 855 na sênior | não coletada | candidato para a ponta varejo; falta rentabilidade |
| BTG Pactual Crédito Estruturado FIC FIDC | R$ 209,3 mi | classe única | 383 | 12M 17,91% (agregador) | descartado: público qualificado |
| BTG Agro SP FIDC | ~R$ 150 mi (sênior + mezanino) | sênior e mezanino | 1 na sênior | não | histórico de < 4 meses |
| PAN Auto FIDC | n/d | n/d | 1 | n/d | contraste (ver seções 1 a 4) |

**O que não foi possível satisfazer (e por quê)**

* **Sênior para varejo, comprovada:** nenhuma fonte que li informa o perfil (PF/PJ) dos cotistas da sênior do fundo escolhido. A RCVM 175 permite varejo em subclasses seniores de FIDC, mas
  isso é regra geral, não prova de que este fundo distribua ao varejo. O Informe Mensal da CVM tem cotistas **por tipo**; é o dado a conferir.
* **Quem detém as subordinadas:** o dado público é a **contagem** e o **tipo** de cotista (PF, PJ, fundos, etc.), **não o nome**. Se a júnior é retida pelo originador/gestor, isso
  costuma estar no regulamento, no prospecto ou na lâmina, não nos dados abertos.
* **Dado atual:** o único conjunto com retorno por classe e PL por classe que consegui ler integralmente é de jun/2024. Para atualizar, rode `python scripts/baixar_cvm.py` na sua máquina
  (os campos de PL e rentabilidade por classe estão no Informe Mensal) e preencha `casos/_modelo/dados_observados.csv`.

**Como repetir com outro fundo:** copie `casos/_modelo/`, preencha `config_caso.json` e `dados_observados.csv` (formato em `src/fidc_risk/observado.py`) e rode
`python scripts/analisar_caso.py --caso <sua_config.json>`.
