# Prompt para a IA de slides (NotebookLM, Gamma ou similar)

> **Como usar:** suba como fontes os arquivos da pasta `notebooklm_sources/` do repositório (00 a 06) e, se a ferramenta aceitar, `docs/METODOLOGIA.md`
> e `README.md`. Cole o texto abaixo como instrução. Troque `[URL_DO_NOVO_REPO]` pelo link do repositório novo depois de subir.

---

## INSTRUÇÃO

Você é um designer de apresentações acadêmicas com formação em matemática financeira. Crie uma apresentação em **português do Brasil** sobre o trabalho
**"Risco de crédito em FIDCs de duplicatas: PD, LGD, CreditRisk+, cópulas e dimensionamento da subordinação"**, de Davi Henrique de Souza Amâncio
(Licenciatura em Matemática, IFC Campus Camboriú). Versão prévia (v0.3.0).

**Fontes (use SOMENTE estas):**
1. Os arquivos anexados (`notebooklm_sources/00` a `07`), que resumem o repositório de código `[URL_DO_NOVO_REPO]`.
2. Como referência de **formato e rigor** (estrutura de repositório, manifesto de evidências, separação empírico/estimado/simulado/hipotético):
   https://github.com/DaviHrAmancio/fice-2026-modelagem-estocastica
4. Como fonte primária do caso observado (slides 14 e 15): relatório de monitoramento da Austin Rating de 09/08/2024 sobre o FIC FIDC Via Multicrédito, `https://www.austin.com.br/Relatorio/Rating/FIC_FIDC_Via_Multicr%C3%A9dito/11037` (dado de jun/2024; defasado).
3. Como exemplo de FIDC usado no estudo de caso crítico: https://fidcs.com.br/fundo/65473848000183?tab=carteira (PAN Auto FIDC, BTG Pactual).

### Regras inegociáveis
- **Nenhum número fora das fontes.** Todo número deve vir de `02_resultados.md`, `03_lote_exemplo.md` ou dos demais arquivos. Se faltar um dado, escreva "não disponível" e não estime.
- **Rotule a natureza de cada resultado** em um selo pequeno no canto do slide: `HIPOTÉTICO`, `ESTIMADO`, `CALCULADO`, `SIMULADO` ou `OBSERVADO`. A carteira dos resultados principais é **sintética**; deixe isso explícito já no slide 2 e nas legendas dos gráficos. Só o caso do FIC FIDC Via Multicrédito (arquivo `07`) usa dados `OBSERVADOS`, de **jun/2024** (defasados), e isso deve aparecer em todo slide dele.
- **Não apresente o PAN Auto como FIDC de duplicatas.** Ele é do segmento financeiro (provável financiamento de veículos, a confirmar). Nenhum número do PAN Auto entra nos resultados.
- **Via Multicrédito:** não diga que a cota sênior é "para varejo" (não verificado), não diga quem detém as subordinadas (só há contagem de cotistas), e não trate o dado de 2024 como situação atual do fundo.
- **Não faça recomendação de investimento** nem diga que o modelo "prevê perdas de fundo real".
- Cada slide com número deve ter, no rodapé, a fonte no formato `fonte: outputs/<arquivo>.csv` (ou `outputs_caso/via_multicredito/<arquivo>.csv` nos slides do caso observado).
- Linguagem sóbria, sem adjetivos de marketing. Evite listas longas: no máximo 4 tópicos por slide.

### Estrutura sugerida (18 slides, ajuste se necessário)
1. **Título** e autoria; subtítulo "versão prévia, dados sintéticos".
2. **Pergunta de pesquisa e aviso de natureza dos dados** (deságio = custo do dinheiro + EL + custos + margem; EL é média, subordinação depende da cauda).
3. **Como um FIDC de duplicatas funciona** (cedente, sacado, deságio, cota sênior e subordinada, excesso de spread). Diagrama simples.
4. **Modelo de perda:** PD do ciclo, LGD, exposição, EL. Fórmulas curtas.
5. **CreditRisk+ e recursão de Panjer** (bandas, setores Gamma, por que a correlação setorial engorda a cauda). Uma fórmula, uma intuição.
6. **Cópulas gaussiana e t e a calibração por correlação de default.**
7. **Cascata de cotas** e as duas leituras (com e sem excesso de spread).
8. **Resultado 1, cauda:** tabela EL / VaR 99% / VaR 99,9% / ES 99,9% por modelo, cenários base e estresse. Mensagem: a EL é igual, a cauda não.
9. **Resultado 2, subordinação mínima** por modelo, com e sem XS, e a regra de múltiplos da EL.
10. **LGD:** derivação econômica (61% com R=50%, 240 dias, c=15%, d=14%), sensibilidade determinística e LGD Beta. Gráfico `fig_lgd_estresse`. Dizer claramente que LGD sistêmica não foi modelada.
11. **Achado principal da cópula t:** com ν = 5, 10 e 30 não existe ρ que case a correlação de default do CreditRisk+ (piso > alvo); só ν = 100 é calibrável. Gráfico `fig_nu_base`. Mensagem: a conclusão sobre subordinação depende da hipótese de cauda.
12. **Da carteira ao lote:** como analisar duplicatas de um cedente (entrada, método, saídas).
13. **Exemplo de lote (sintético):** EL, VaR, deságio exigido vs praticado, subordinação, concentração. Mensagem: com 35 sacados a cauda é dominada pela **concentração** (VaR 99,9% de 6,9% da face vs 2,0% na carteira de 600 sacados).
14. **Caso observado: FIC FIDC Via Multicrédito (OBSERVADO, jun/2024).** Tabela do arquivo `07`: PL, retorno do último mês, retorno 12M e % do CDI por classe (sênior, mezanino, júnior), subordinação de 57,4%, e gráficos `caso_via_multicredito_retorno_acumulado` e `caso_via_multicredito_retorno_mensal`. Mensagem: mais retorno, mais oscilação; a júnior teve meses negativos, a sênior não. Aviso: defasado; varejo e titulares das subordinadas não verificados.
15. **Sênior × subordinada: o que o modelo diz (SIMULADO).** Gráfico `caso_via_multicredito_absorcao` e a tabela de ponte do `07`: anexação de cada classe versus VaR 99,9% da carteira sintética; EL anual aproximada da júnior versus prêmio observado. Mensagem: a perda é absorvida primeiro pela júnior; o excesso da sênior sobre o CDI não é explicado pela perda esperada de crédito do modelo. Dizer o que isto NÃO permite concluir (preço justo, previsão, recomendação).
16. **Estudo de caso crítico: PAN Auto FIDC.** O que se sabe (cadastro), o que não se sabe, por que não é de duplicatas, o que isso implica (carteira granular → Vasicek; 1 cotista; poucas competências) e que **devedores individuais não são públicos**. Propor: usar como contraste e escolher um fundo de duplicatas multicedente com histórico longo.
17. **Validação e transparência:** Panjer × Monte Carlo (KS), convergência n^(−1/2), testes, manifesto de evidências, seed e hash da config. Mostrar o mapa "afirmação → arquivo → código".
18. **Limites e próximos passos:** diluição, coobrigação, fraude/duplicidade, LGD sistêmica, revolvência, calibração com a CVM. Fechar com o aviso acadêmico.

### Design
- Estilo acadêmico limpo: fundo claro, uma cor de destaque (azul-petróleo), tipografia sem serifa, muito espaço em branco.
- Gráficos: use as figuras do repositório (`figures/*.png`) quando existirem; para tabelas, use as de `02_resultados.md`. Não invente gráficos com dados que não estejam nas fontes.
- Notas do apresentador em cada slide (3 a 5 frases) explicando a intuição e **o que o resultado NÃO permite concluir**.
- Slide final com o link do repositório e do manifesto de evidências.

### Antes de entregar, confira
1. Todo número aparece nas fontes? 2. Todo slide com resultado tem selo de natureza e rodapé de fonte? 3. O PAN Auto não foi tratado como duplicata? 4. Ficou claro que a carteira dos resultados principais é sintética e que o único dado observado (Via Multicrédito, jun/2024) está rotulado `OBSERVADO` e separado?
