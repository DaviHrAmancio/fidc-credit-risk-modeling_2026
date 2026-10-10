# Guia: montar o notebook e gerar os slides

Dados de limites conferidos em setembro/2026 (veja as fontes ao final). Limites de plano mudam: confira em Configurações → Uso.

## 1. O que o NotebookLM aceita (e não aceita)

* **Não aceita .zip.** Descompacte o zip do repositório e envie os arquivos de `notebooklm_sources/`.
* Aceita: `.md`, `.txt`, `.csv`, `.pdf`, `.docx`, `.pptx`, imagens (png/jpg), Google Docs/Slides/Sheets, URLs de páginas (só o texto), YouTube com legenda.
* Plano gratuito: 50 fontes por notebook, até 500 mil palavras ou 200 MB por arquivo; 50 chats por dia; slides em categoria "limitada" (sem número publicado).

## 2. Passo a passo

1. Crie um notebook novo no NotebookLM.
2. **Fontes → Adicionar → Enviar arquivos:** selecione todos os 21 arquivos de `notebooklm_sources/` (00 a 20). Comece pelo `00_LEIA_ME_PRIMEIRO.md`.
3. **Fontes → Adicionar → Site:** cole as URLs da seção 3, uma por vez (a seção 3 diz quais eu li).
4. **Chat:** abra a opção de personalizar o chat (o nome e a posição do botão podem variar) e cole o conteúdo de `docs/prompts_notebooklm/01_instrucao_do_chat.txt` (2,6 mil caracteres; o limite reportado é 10 mil).
5. **Studio:** escolha gerar a apresentação de slides, abra a opção de personalizar e cole `02_slides_completo.txt` (1,5 mil caracteres). Se a caixa truncar, use `03_slides_curto.txt` (0,4 mil).
6. Teste a fidelidade antes de gerar: pergunte "Qual é a capacidade de perda anual em % do PL em setembro/2026 e de que arquivo vem?" A resposta deve vir com o arquivo e a classe do dado.
7. Gere os slides, abra cada um e confira os números contra `outputs/tabelas_readme.md`. Não use nenhum número que não esteja ali.

## 3. Fontes de URL para adicionar

| Nº | O que é | URL | Li o conteúdo? |
|---|---|---|---|
| 1 | Fidc News: deságio sobe para 2,92% a.m. (07/10/2026) | https://fidcnews.com.br/desagio-dos-recebiveis-sobe-para-2-92-ao-mes-em-setembro-e-registra-maior-alta-mensal-desde-setembro-de-2025 | sim |
| 2 | Madeira Total: deságio após seis meses de queda (11/06/2026) | https://www.madeiratotal.com.br/desagio-em-operacoes-com-duplicatas-da-sinal-de-acomodacao-apos-seis-meses-de-queda/ | sim |
| 3 | Brasil Inovador: deságio atinge 2,92% a.m. (09/10/2026) | https://brasilinovador.com.br/desagio-em-antecipacao-de-recebiveis-atinge-292-ao-mes-e-reflete-desaceleracao-economica/ | sim (declara produção com apoio de IA) |
| 4 | FGV/IBRE: metodologia do ICE (2017) | https://portalibre.fgv.br/sites/default/files/2020-03/indicadores-de-confian_a-empresarial-fgv-ibre_aspectos-metodol_gicos-06_2017-_1_.pdf | sim. Se o NotebookLM não importar o PDF por link, baixe e envie o arquivo |
| 5 | Wikipedia: Purchasing Managers' Index | https://en.wikipedia.org/wiki/Purchasing_Managers'_Index | sim (fonte secundária) |
| 6 | Gordy, comparação de modelos de crédito (FEDS 1998-47) | https://www.federalreserve.gov/pubs/feds/1998/199847/199847pap.pdf | não (veio de busca) |
| 7 | Bonelli, Schiozer, Vasconcelos (2021), redução de risco com duplicatas (FGV EAESP) | https://eaesp.fgv.br/sites/default/files/legacy/pesquisa-eaesp-files/arquivos/sch2_bonelli_schiozer_vasconcelos_2021_reducao-de-risco-no-credito-co_62882.pdf | não (veio de busca) |
| 8 | CVM: Informes Mensais de FIDC (dados abertos) | https://dados.cvm.gov.br/dataset/fidc-doc-inf_mensal | não (veio de busca) |
| 9 | CreditRisk+ (CSFB), página de referência | http://www.defaultrisk.com/pp_model_21.htm | não (veio de busca) |

O Associated News tem uma matéria sobre o prazo médio de julho (46,5 dias), mas bloqueia leitura automática; não a incluí.
As fontes 6 a 9 entram como referência: remova qualquer uma que o NotebookLM não consiga importar.

## 4. Perguntas para iniciar o notebook

1. "Resuma em 5 linhas o que o repositório mostra, classificando cada número (empírico, hipotético, estimado, calculado, simulado)."
2. "Explique a recursão de Panjer com a notação do arquivo de metodologia."
3. "Quais limitações do trabalho a banca provavelmente vai questionar? Responda só com o que está nas fontes."
4. "Monte o roteiro de 14 slides e, para cada um, diga qual arquivo sustenta o número principal."

## 5. Qual ferramenta usar para os slides

Comparação resumida (planos gratuitos, informações de fontes públicas de setembro/2026):

| Ferramenta | Parte forte | Limites no plano gratuito |
|---|---|---|
| **NotebookLM** | Gera a partir das suas fontes e responde com citação; é a melhor opção gratuita para fidelidade às fontes | 50 fontes; slides em categoria limitada; limite do prompt de slides não publicado |
| **Gamma** | Visual mais trabalhado; exporta PPTX e PDF | 400 créditos no cadastro (não renovam), até 10 slides por prompt, marca do Gamma; upload de documentos não documentado no plano gratuito (cole o texto) |
| **Claude (Slides)** | Monta um deck editável direto dos CSVs e das tabelas do repositório, com cada número vindo do output | Sujeito aos limites do seu plano |

Sugestão de fluxo: NotebookLM para o rascunho e para estudar as fontes; se quiser os números travados nos outputs e o deck editável, peça o deck ao Claude a partir do repositório.

## Fontes deste guia

* [Limites do NotebookLM em 2026 (notebooklm-guide.com, 02/09/2026)](https://notebooklm-guide.com/notebooklm-system-limits-benchmarks/)
* [NotebookLM amplia personalização de chat para 10.000 caracteres (05/12/2025)](https://www.robertodiasduarte.com.br/notebooklm-amplia-personalizacao-de-chat-para-10-000-caracteres/)
* [Formatos de fonte aceitos (Google, página de suporte)](https://support.google.com/notebooklm/answer/16215270): a página que li descreve o "Gemini Notebook", não o NotebookLM; os formatos podem diferir, então confirme no próprio app.
* [10 melhores criadores de apresentação com IA gratuitos (SaaS CRM Review, 03/09/2026)](https://saascrmreview.com/best-free-ai-presentation-makers/)
