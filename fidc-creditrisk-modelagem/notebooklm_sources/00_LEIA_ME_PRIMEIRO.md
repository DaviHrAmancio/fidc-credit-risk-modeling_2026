# Leia primeiro: como usar as fontes deste notebook

Este notebook reúne o repositório `fidc-creditrisk-modelagem` (v0.2.0), do trabalho de Davi H. S. Amâncio (IFC Camboriú) sobre
risco de crédito em FIDCs de duplicatas. A pergunta central: quanto do deságio cobrado na compra de duplicatas paga o risco de crédito
e quanto sobra, e como a escolha do modelo (CreditRisk+, cópulas) muda a cauda de perdas e a subordinação necessária.

## Mapa dos arquivos

| Arquivo | Para que serve |
|---|---|
| 01_README.md | Resumo do projeto e tabelas de resultados (geradas pelo pipeline) |
| 02_METODOLOGIA.md | Fórmulas e hipóteses: CreditRisk+, Panjer, cópulas, cascata, decomposição da taxa |
| 03_MANIFESTO_DE_EVIDENCIAS.md | De onde vem cada número e como foi verificado |
| 04_FONTES_EXTERNAS.md | Fontes de mercado e referências, com classificação de confiabilidade |
| 05_CODIGO_FONTE_CONSOLIDADO.md | Todo o código Python (módulos, pipeline, scripts, testes) |
| 06 a 13 (csv) | Resultados: perdas por modelo, cotas, decomposição da taxa, efeito taxa x prazo, série de mercado, macro, calibração das cópulas, regra de múltiplos |
| 14_resultados_chave.md | Métricas de validação e subordinação mínima (JSON em bloco de código) |
| 15 a 20 (png) | Figuras de cauda, subordinação e validação, nos cenários base e estresse |

## Glossário

* **FIDC**: fundo de investimento em direitos creditórios. **Cedente**: quem vende a duplicata. **Sacado**: devedor da duplicata.
* **Deságio**: desconto sobre a face na compra do recebível. **PL**: patrimônio líquido (soma dos preços pagos).
* **EL** (perda esperada), **VaR** e **ES** (perda no quantil e média além dele). **LGD**: perda dado o default. **PD**: probabilidade de default.
* **Cota sênior / subordinada**: a subordinada absorve as primeiras perdas. **Excesso de spread**: deságio menos funding e custos do ciclo.
* **Capacidade de perda**: receita de deságio menos funding da sênior e custos, em % do PL. **Margem residual**: capacidade menos a EL do modelo.
* **CreditRisk+**: modelo atuarial de perdas (Poisson com mistura Gamma por setor); **Panjer**: recursão que calcula a distribuição exata.
* **Cópula gaussiana / t**: modelos de variável latente (família Merton/Vasicek) usados como comparativo.

## Regras de leitura (importante)

* Classes de resultado: **empírico** (dado de mercado, fonte única, não auditado), **hipotético** (carteira sintética e premissas),
  **estimado**, **calculado (analítico)** e **simulado**. Diga sempre a classe ao citar um número.
* A série de deságio é da Quick Soft (via imprensa), com cerca de 13 meses e sem metodologia pública. É a taxa paga pelo cedente, não retorno de FIDC.
* PMI é da S&P Global; ICE (Confiança Empresarial) é da FGV/IBRE. Aparecem só como contexto, ainda fora do modelo.
* A margem residual não é lucro nem alfa. A carteira de sacados é sintética.
