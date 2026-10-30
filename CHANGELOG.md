# Mudanças

O que mudou em cada versão, em uma linha por mudança. O porquê de cada uma — o texto longo,
com as decisões e os defeitos que elas evitam — está no docstring de
[`src/flatcap/__init__.py`](src/flatcap/__init__.py), reproduzido na
[documentação](docs/Doc.Flatcap.md). O formato segue o
[Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/), e as versões, o
[versionamento semântico](https://semver.org/lang/pt-BR/).

## [1.18.1] — a matrícula com zero na frente

### Corrigido
- A matrícula com zero na frente e um 8 ou um 9 — `0189`, `01928` — perdia o zero em tudo
  que lê o `projeto.yaml`: o `flatcap status` mostrava `1928` (o `listar`, que a lê do
  REDCap, mostrava `01928`), o relatório saía `Relatorio_1928_….docx`, e o `<id>` pela
  matrícula não achava o projeto. O `flatcap novo` passa a escrevê-la entre aspas, e a ficha
  escrita antes, sem elas, é lida com o zero: **nenhuma ficha precisa ser editada**. O
  relatório já gerado sem o zero vai para `2. Versões antigas/` no próximo
  `flatcap relatorio`, como qualquer anterior.

## [1.18.0] — o status do cálculo amostral

### Acrescentado
- O status `cálculo amostral`, entre o `não iniciado` e o `aguardando banco de dados`: o
  projeto cujo tamanho da amostra está sendo calculado, antes da coleta. É escrito à mão,
  como o `aguardando banco de dados` e o `em andamento`, e sai em ciano no `flatcap status`.

### Mudado
- O cabeçalho da ficha nova lista os seis status. As fichas criadas antes não precisam ser
  editadas: o sexto é lido nelas do mesmo jeito.

## [1.17.0] — o painel de status

### Acrescentado
- `flatcap status`: os projetos que já têm pasta, numa tabela como a do `listar` — id,
  matrícula, nome, pasta local, status e prazo —, na ordem do `record_id`. Lê as fichas do
  `FLATCAP_ROOT`, não fala com o REDCap e não escreve nada.
- Os cinco status do `projeto.yaml`: `não iniciado`, `aguardando banco de dados`,
  `em andamento`, `pronto` e `finalizado`. O `finalizado` tira o projeto do painel, e os
  outros quatro saem cada um na sua cor — branco, amarelo, azul e verde.
- O prazo no painel: a data final escrita no `prazo:` depois da reunião, como `2026-11-04` ou
  `04/11/2026`, e ATRASADO, em vermelho, quando ela passou sem o projeto estar `pronto`.
- Os avisos do painel: status fora da lista, prazo que não é data, ficha que não abre e pasta
  no formato anterior à 1.1.0.

### Mudado
- O `flatcap novo` escreve `status: não iniciado`, no lugar de `status: novo`, e o cabeçalho
  da ficha explica os cinco status e os dois formatos do prazo.
- O `flatcap relatorio`, quando escreve o documento, passa o `status:` da ficha para `pronto`,
  preservando o resto do arquivo; a simulação mostra a troca, e o histórico a registra.
- O `novo` e o `em_analise` das fichas de antes são lidos como `não iniciado` e
  `em andamento`; nenhuma ficha precisa ser editada.

## [1.16.0] — a metodologia na primeira página

### Acrescentado
- O texto padrão de metodologia na primeira página do relatório, depois da finalidade e dos
  objetivos, para o cliente levar para a seção de métodos do artigo: o subtítulo
  "Metodologia Estatística (texto padrão)", no estilo de subtítulo do documento, e um
  parágrafo que diz como as variáveis foram descritas, quais testes rodaram e o nível de
  significância, e termina com a versão do Python ("As análises foram feitas usando a
  linguagem Python versão 3.11.").
- O parágrafo é montado dos manifestos das rodadas, e nomeia só os testes que de fato rodaram;
  a regra que escolheu entre eles só é explicada quando escolheu. A redação mora no bloco
  editável no topo do `metodologia.py`.
- O aviso de terminal quando uma rodada não diz quais testes rodaram e fica fora do parágrafo.

## [1.15.0] — a amostragem

### Acrescentado
- `flatcap amostragem <id>`: o tamanho da amostra de um projeto, com o relatório da amostra.
  Vem depois do `flatcap novo`, e tudo dela mora em `4. Amostragem/`, dentro da pasta do
  projeto: o `desenho.yaml`, o `tamanho.csv`, o `manifesto.json`, o
  `Amostragem_<matrícula>_AAAA-MM-DD.docx` e as versões antigas, em
  `4. Amostragem/Versões antigas/`.
- O `desenho.yaml`, a ficha da amostra, preenchida à mão: a primeira rodada escreve o modelo
  comentado — 95% de confiança, margem de 5 pontos, proporção esperada de 50% —, e o FlatCap
  nunca o reescreve. Percentuais em %, e a vírgula decimal vale.
- A amostragem aleatória simples, sem reposição: para uma proporção ou, com o `desvio`, para
  uma média; com ou sem a população (`populacao`); com a perda esperada (`perda`); ou com o
  tamanho decidido à mão (`n`). A conta é a do OpenEpi, arredondada para cima, e o tamanho
  nunca passa de N — quando chega a ele, é um censo, e o comando avisa.
- As recusas do `desenho.yaml`, todas de uma vez: o `12.000` que no YAML é doze, a confiança
  ou a proporção escritas como fração, a confiança escrita como o α (`5`), a margem que não
  cabe na proporção, a chave com acento, e os desenhos que ainda não estão no FlatCap
  (sistemática, estratificada, conglomerados, PPT, dois estágios).
- Os avisos da margem que parece fração (`margem: 0.05`) e de quando o tamanho da amostra
  muda em relação à rodada vigente.

### Mudado
- As propriedades do `.docx` dizem a análise da rodada e, sem banco, "sem banco" — no lugar
  de "a partir da descritiva" e de "banco ?".
- `relatorio.tabela_do_texto`, `relatorio.localizar_template`, `relatorio.conferir_texto`,
  `ficha.ler_yaml` e `ficha.numero_escrito` são públicos. Os nomes privados continuam valendo.

## [1.14.1] — o que chega do Excel

### Corrigido
- O `.csv` do Excel em português (`;` entre campos e `70,5` na célula) tem as colunas de
  vírgula decimal lidas como número, a coluna inteira ou nada. O perfil mandava "corrigir"
  um arquivo certo, e toda análise recusava a coluna. As colunas lidas assim aparecem no
  cabeçalho do perfil e no manifesto de cada análise.
- Número de escala pequena — uma concentração na casa de 0,003 — não sai mais zero: a
  descritiva, a comparação e o perfil escrevem a variável com as casas que a escala dela
  pede. Idade, peso, IMC e altura em metros continuam com as duas casas de sempre.
- O corte de faixa escrito no dicionário sai como foi escrito, no rótulo e no manifesto; com
  mais de quatro casas ele era arredondado, e o relatório acusava um "dicionário mudou"
  falso.
- O nome de coluna com espaço nas pontas (`Idade `) não trava mais o projeto num laço entre o
  perfil e a descritiva, e o com quebra de linha (`Peso` e `(kg)` em duas linhas) não
  estraga mais as tabelas do relatório: o leitor limpa os dois (`Idade`, `Peso (kg)`), e o
  perfil mostra o nome de antes.
- O comentário dos `.csv` das análises sai sempre numa linha só, mesmo quando o rótulo ou uma
  categoria trazem uma quebra de linha.
- O achado `virgula_decimal` do perfil mostra o valor que impediu a leitura da coluna, e
  `1234,5` deixa de ser diagnosticado como "número guardado como texto".

## [1.14.0] — os testes de postos

### Acrescentado
- Os testes de postos na comparação: o Wilcoxon contra uma referência, o Mann-Whitney entre
  dois grupos, o Kruskal-Wallis entre três ou mais e o Friedman nas medidas repetidas. A
  regra dos pressupostos os escolhe onde o Shapiro-Wilk rejeita a normal, e essas linhas
  deixam de sair "não testado".
- No item: `wilcoxon` (entre dois grupos, o Mann-Whitney, como no R), `mannwhitney`,
  `kruskal`, e `metodo: friedman` nas medidas repetidas.
- O Wilcoxon e o Mann-Whitney com a estimativa de Hodges-Lehmann e o intervalo de 95% dela —
  a pseudomediana e a diferença de locação —, como o `wilcox.test` do R até a 4.5 com
  `conf.int = TRUE`. O R 4.6 passou a dar o p exato também com empates; seguir o 4.6 fica
  para decidir.
- Avisos para o intervalo que não chega a 95% (ele sai da tabela e fica no manifesto) e para
  o menor p possível acima de 0,05, nas amostras pequenas.
- No manifesto da comparação, a mediana e os quartis de cada linha, grupo e medida, e o
  caminho do p dos testes de postos.

### Mudado
- O resumo de cada linha é o do teste dela: `média (DP)` no t e na ANOVA, `mediana [Q1 a Q3]`
  nos testes de postos. Os cabeçalhos do resumo, do intervalo da uma amostra e da diferença
  entre dois grupos dizem o que a coluna tem; uma tabela só de paramétricos sai como antes.
- A ANOVA de medidas repetidas que não pode rodar — cada caso mudando o mesmo tanto entre as
  medidas — ensina a escrever o Friedman.
- `wilcoxon`, `mannwhitney`, `kruskal` e `friedman` escritos em `analises:` ensinam que são
  testes da `comparacao`.

### Removido
- A pasta `.github`: a CI, a publicação de versões no GitHub, o Dependabot e os modelos de
  issue e de pull request. As conferências rodam na máquina de quem muda o código, e a
  instalação vem direto do repositório (`uv tool install git+https://…`).

### Corrigido
- A dica do `doctor` para reinstalar pelo `uv` é `uv tool upgrade --reinstall flatcap`, que
  reinstala de onde o FlatCap veio. O `uv tool install --reinstall flatcap` procurava o nome
  no PyPI, onde o FlatCap não está.
- Os anos do R no `hipoteses.py`: o cabeçalho passa a `1995-2024 The R Core Team`, e o
  docstring do `_quantil`, a `1999-2024` — os do `signrank.c` e do `wilcox.c`, de onde vem o
  quantil das distribuições exatas.

## [1.13.1] — a revisão antes da abertura do código

### Corrigido
- O `perfil` propõe as categorias com a mesma escrita das análises: numa coluna de código
  com uma célula vazia, ele propunha `1.0|2.0` e ensinava `1.0=Feminino`, que a descritiva
  nunca encontrava. **Dicionários já escritos com `1.0=` precisam ser corrigidos à mão.**
- O `#` só é comentário no cabeçalho do `dicionario.csv` e das tabelas: a variável `#id` e a
  categoria `#N/D` deixaram de sumir. As mensagens do dicionário dão a linha do arquivo.
- O cifrão do banco (`R$ 1.000 a R$ 2.000`) não vira fórmula matemática nos gráficos.
- Os arquivos gravados seguem o `umask`, e não `0600` — num `FLATCAP_ROOT` dividido pela
  equipe, no Linux e no macOS, só o dono os abria.
- Todo erro HTTP do REDCap, e toda falha do `requests`, vira mensagem, e não traceback.
- Uma falha inesperada ao escrever o `.docx` devolve o relatório anterior ao lugar; uma
  figura ilegível vira mensagem com o nome do arquivo.
- A codificação de um `.csv` é confirmada no arquivo inteiro, e não só nos primeiros 64 KiB.
- Mensagens: frases coladas no `novo`, o resumo do `listar`, "com a ANOVA" no histórico, a
  ajuda do `template` e do `relatorio`, e nenhuma "Fase 5" no texto que o usuário lê.

### Acrescentado
- O `.env` da sua conta, para quem instala o FlatCap com o `pipx` ou o `uv`, e
  `flatcap doctor --criar-env`, que o escreve.
- `LICENSE` (GPL-3.0-or-later), `NOTICE.md`, cabeçalhos SPDX, e a licença no
  `flatcap --version`.
- CI, publicação de versões no GitHub, `pre-commit`, e os modelos de issue e de pull request.

## [1.13.0] — o lote
- `flatcap analisar`: as análises da lista `analises:` da ficha, de uma vez, preparadas
  todas antes de qualquer uma ser escrita.

## [1.12.0] — as medidas repetidas
- A ANOVA de medidas repetidas, sempre com a correção de Greenhouse-Geisser
  (`- repetidas: [pas_0, pas_1, pas_2]`), e a tabela `repetidas.csv`.

## [1.11.0] — a ANOVA de Welch
- Entre três grupos ou mais, a ANOVA de Welch é o paramétrico da regra, como o `oneway.test`.

## [1.10.0] — três grupos ou mais, e a ANOVA
- A comparação entre três grupos ou mais (`k_grupos.csv`) e a ANOVA clássica, quando escrita.

## [1.9.0] — o t de Welch
- Entre dois grupos, o t de Welch é o paramétrico da regra, como o `t.test` sem argumento.

## [1.8.0] — dois grupos, e o t de Student
- A comparação entre os dois grupos de uma categórica (`dois_grupos.csv`) e o t de Student,
  quando escrito.

## [1.7.0] — a comparação
- `flatcap comparacao`: a média contra um valor de referência, pelo t de uma amostra, e o
  `hipoteses.py` com a aritmética dos testes, conferida contra o R.

## [1.6.0] — a correlação
- `flatcap correlacao`: Pearson, Spearman ou Kendall pelos pressupostos, com o Spearman
  exato do AS 89 e uma dispersão por par.

## [1.5.0] — a associação
- `flatcap associacao`: qui-quadrado ou Fisher exato pela regra de Cochran, com o V de Cramér.

## [1.4.0] — o cruzamento
- `flatcap cruzamento`: uma tabela cruzada por par de categóricas.

## [1.3.1] — o relatório enxerga todas as análises
- O relatório varre `3. Análises/*/`, e a lista `analises:` da ficha ordena as seções.

## [1.3.0] — os rótulos de categoria
- `1=Feminino|2=Masculino` em `categorias_ordem` dá nome aos códigos de uma coluna.

## [1.2.0] — a normalidade
- `flatcap normalidade`: Shapiro-Wilk, assimetria, curtose e Q-Q das numéricas.

## [1.1.0] — um cliente, vários projetos
- A pasta do cliente (`matrícula - nome`) passa a guardar uma pasta por projeto
  (`Projeto NNN`).

## [1.0.0] — o relatório
- `flatcap relatorio` e `flatcap template`: o `.docx` montado a partir das análises.

## [0.6.0] — a descritiva
- `flatcap descritiva`: frequências, resumos, faixas, períodos e gráficos, obedecendo ao
  `dicionario.csv`.

## [0.5.0] — o perfil
- `flatcap perfil`: o `perfil.md` para a reunião e o `dicionario.csv`.

## [0.4.0] — o versionamento dos bancos
- `flatcap dados adicionar` e `flatcap dados listar`.

## [0.3.0] — a pasta do projeto
- `flatcap novo`: a pasta, o banco baixado do REDCap, a ficha e o histórico.

## [0.2.0] — as solicitações
- `flatcap listar`.

## [0.1.0] — a fundação
- `flatcap doctor`: a configuração e a conexão com o REDCap.
