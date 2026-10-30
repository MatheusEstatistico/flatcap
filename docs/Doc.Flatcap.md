# FlatCap — a documentação

> **Versão 1.18.0.** Este documento tem duas partes. A **Parte I** é escrita à mão: o que o
> FlatCap é, como se instala, configura e usa, como as pastas se organizam, como o código se
> divide, e como se testa e se fecha uma versão. A **Parte II** é gerada a partir do código:
> todo docstring e todo comentário de `src/flatcap/`, módulo por módulo, na ordem do arquivo.
> Para mexer na Parte II, mude o comentário no código e rode `python tools/gerar_doc.py`.

**Parte I — o projeto**

1. [O que é o FlatCap](#1-o-que-é-o-flatcap)
2. [Instalação](#2-instalação)
3. [Configuração](#3-configuração)
4. [O formulário do REDCap](#4-o-formulário-do-redcap)
5. [O fluxo de trabalho](#5-o-fluxo-de-trabalho)
6. [Os comandos](#6-os-comandos)
7. [As pastas e os arquivos](#7-as-pastas-e-os-arquivos)
8. [A arquitetura](#8-a-arquitetura)
9. [Os testes](#9-os-testes)
10. [As versões](#10-as-versões)
11. [Licença e avisos](#11-licença-e-avisos)
12. [Como este documento é feito](#12-como-este-documento-é-feito)

**Parte II — o código, comentário por comentário** — [ir para a Parte II](#parte-ii--o-código-comentário-por-comentário)

---

# Parte I — O projeto

## 1. O que é o FlatCap

Uma ferramenta de linha de comando para o fluxo de trabalho de um serviço de assessoria
estatística que recebe as solicitações por um formulário do REDCap:

**REDCap (entrada) → organização de pastas → versionamento dos bancos → análises → relatório `.docx`**

O princípio é **automatizar o que é repetitivo e mecânico e manter manual o que é decisão
técnica**. O FlatCap cria a pasta de cada projeto, baixa o banco que o cliente anexou,
guarda cada versão do banco, descreve o banco para a reunião, roda as análises que a reunião
decidiu e monta o relatório — e, quando o pedido é de amostragem, calcula o tamanho da amostra
e escreve o relatório dela. O que ele **não** faz é decidir: o tipo de cada variável, os
rótulos das categorias, os pares que se cruzam e as comparações que se testam são escritos por
você, em dois arquivos de texto do projeto — o `dicionario.csv` e o `projeto.yaml` —, e as
análises obedecem a eles. O plano da amostra mora num terceiro, o `desenho.yaml`.

Cinco ideias atravessam o projeto:

- **Simula por padrão.** Todo comando que escreve em disco primeiro mostra o que faria; o
  `--sim` executa. A simulação e a execução percorrem o mesmo plano.
- **Nada se apaga.** O que deixa de valer vai para `2. Versões antigas/`, com data e hora no
  nome. Um número que o cliente já viu não some sem rastro.
- **Tudo fica documentado em disco.** A ficha do projeto, o histórico de cada comando, o
  manifesto de cada rodada: um projeto reaberto seis meses depois se explica sozinho.
- **O que se analisa está escrito.** Trinta variáveis dão 435 pares, e testar todos é
  *p-hacking* feito por máquina. Sem a lista escrita na ficha, a análise recusa.
- **Conferido contra o R.** Os testes estatísticos reproduzem o R 4.3.3, e a suíte compara
  com valores calculados no R — nunca com o próprio FlatCap.

O FlatCap foi escrito para o formulário de um serviço específico, mas o acoplamento mora num
lugar só (o `modelo.py`), e um formulário com os mesmos nomes de campo funciona sem mudar o
código — ver a [seção 4](#4-o-formulário-do-redcap). Não é afiliado à Vanderbilt
University nem ao REDCap Consortium.

## 2. Instalação

O FlatCap precisa do **Python 3.11 ou mais novo** e roda no Windows, no macOS e no Linux.
Ele é um programa de terminal, e o jeito recomendado de instalá-lo é **como ferramenta**: num
ambiente isolado, com o comando `flatcap` disponível em qualquer pasta. A instalação vem
direto do repositório no GitHub, sem cloná-lo — o código é baixado para uma pasta
temporária, instalado e descartado —, e por isso pede o [Git](https://git-scm.com/downloads)
na máquina.

### 2.1 Como ferramenta, com o `uv` (recomendado)

O [`uv`](https://docs.astral.sh/uv/) é um executável só, e baixa até o Python, se a máquina
não tiver um.

1. **Instale o `uv`.** No Windows, no PowerShell:

   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

   No macOS e no Linux:

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Instale o FlatCap:**

   ```bash
   uv tool install git+https://github.com/MatheusEstatistico/flatcap
   ```

   Se o terminal disser que não acha o comando `flatcap`, rode `uv tool update-shell` e abra
   um terminal novo.

3. **Configure** — ver a [seção 3](#3-configuração):

   ```bash
   flatcap doctor --criar-env     # escreve o .env da sua conta e diz onde ele está
   flatcap doctor                 # depois de preencher as três chaves
   ```

### 2.2 Como ferramenta, com o `pipx`

Com o Python já instalado (o instalador do [python.org](https://www.python.org/downloads/), ou
`winget install Python.Python.3.12` no Windows):

```bash
python -m pip install --user pipx
python -m pipx ensurepath          # abra um terminal novo depois
pipx install git+https://github.com/MatheusEstatistico/flatcap
```

### 2.3 Atualizar e desinstalar

| | `uv` | `pipx` |
|---|---|---|
| atualizar para o que está no `main` | `uv tool upgrade flatcap` | `pipx upgrade flatcap` |
| desinstalar | `uv tool uninstall flatcap` | `pipx uninstall flatcap` |
| ver o que está instalado | `uv tool list` | `pipx list` |

O `.env` da sua conta e o `FLATCAP_ROOT` não são tocados por nenhum desses comandos. A
versão instalada aparece no `flatcap --version`.

### 2.4 Para desenvolver

```bash
git clone https://github.com/MatheusEstatistico/flatcap.git
cd flatcap
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pre-commit install
```

A instalação é *editável*: uma mudança em `src/` vale na hora, sem reinstalar. Toda versão
que traz dependência nova pede o `pip install -e ".[dev]"` de novo — o `flatcap doctor` acusa
a biblioteca que falta, pelo nome do pip.

## 3. Configuração

O FlatCap precisa de três chaves:

| Chave | O que é, e onde obter |
|---|---|
| `REDCAP_API_URL` | A URL da API, no formato `https://<servidor>/redcap/api/`, na página **API Playground** do projeto no REDCap. **Não** é o link curto do survey (`redcap.link/...`), que o FlatCap recusa com uma mensagem própria. A barra final é acrescentada quando falta. |
| `REDCAP_TOKEN` | O token do projeto, no menu **API** → *Request API token*. Precisa de permissão para exportar **registros, metadados e arquivos** — a última é a que se esquece, e é a que baixa o banco. |
| `FLATCAP_ROOT` | O caminho **absoluto** da pasta onde ficam as pastas dos clientes. Fora de qualquer repositório Git, porque é onde moram os dados. Se ela não existir, o FlatCap recusa — quase sempre é a nuvem que não montou; `flatcap doctor --criar-root` a cria. |

As chaves vêm de um arquivo `.env`, procurado nesta ordem — o primeiro que existir é o lido:

1. o arquivo indicado com `--env CAMINHO`, que todo comando aceita;
2. um `.env` na pasta atual ou em alguma acima dela — o de quem trabalha num clone do
   repositório, que o guarda na raiz do clone;
3. o **`.env` da sua conta**, na pasta de configuração do sistema — o de quem instalou o
   FlatCap como ferramenta:

   | Sistema | Onde |
   |---|---|
   | Windows | `C:\Users\<você>\AppData\Roaming\flatcap\.env` |
   | macOS | `~/Library/Application Support/flatcap/.env` |
   | Linux | `~/.config/flatcap/.env` (ou `$XDG_CONFIG_HOME/flatcap/.env`) |

`flatcap doctor --criar-env` escreve o terceiro com as três chaves em branco — no Linux e no
macOS, legível só por você — e nunca o sobrescreve. Variáveis de ambiente com os mesmos nomes
valem mais que qualquer `.env`, o que permite rodar num servidor sem arquivo nenhum.

O `flatcap doctor` confere tudo de uma vez — o `.env` que foi lido, as três chaves, a pasta, as
bibliotecas e a conexão com o REDCap — e diz se o problema está na configuração, na rede ou no
token.

**O `.env` guarda o token, e o token é uma senha.** Ele nunca vai para o Git, para uma issue
ou para um e-mail. Se vazar, troque-o no REDCap (*API* → *Regenerate token*): o antigo deixa
de valer na hora.

## 4. O formulário do REDCap

O FlatCap lê estes campos do formulário de solicitação (`modelo.CAMPOS_REDCAP`), sempre como
valores crus (`rawOrLabel = raw`):

| Campo | Tipo | Para quê |
|---|---|---|
| `record_id` | — | identifica a solicitação; vira a pasta `Projeto NNN` |
| `intro` | radio: `1` professor/colaborador, `2` aluno | decide de quais campos vêm a matrícula e o nome |
| `matricula1`, `prof1` | texto | matrícula e nome do professor (`intro = 1`) |
| `matricula2`, `aluno2` | texto | matrícula e nome do aluno (`intro = 2`) |
| `fin` | radio | a finalidade, impressa na primeira página do relatório; o rótulo vem do `content=metadata` |
| `outros1` | texto | o que o cliente escreveu quando a finalidade marcada é "Outro" |
| `obj1` | texto longo | os objetivos do estudo, também impressos no relatório |
| `database` | arquivo | o banco de dados, baixado pelo `flatcap novo` |

Duas armadilhas que o código já conhece, e que um formulário novo precisa respeitar:

- **O `prof1` não tem ramificação.** Numa solicitação de aluno ele guarda o nome do
  orientador; quem desempata um `intro` em branco é a matrícula preenchida.
- **A matrícula é texto, nunca número.** `00742` não pode virar `742`, e a pasta do cliente
  é procurada pela matrícula no começo do nome.

O arquivo [`docs/redcap/formulario-minimo.csv`](redcap/formulario-minimo.csv) é o dicionário de
dados de um formulário com esses campos e mais nada, pronto para importar no REDCap
(*Designer* → *Upload Data Dictionary*). Os campos de identificação vêm marcados como
identificadores, para as exportações desidentificadas do REDCap os deixarem de fora.

## 5. O fluxo de trabalho

```
REDCap ──listar──▶ o que chegou, e o que já virou pasta
   │
   └──novo──▶ 00742 - José Antônio de Sá/Projeto 006/     a pasta, o banco baixado, a ficha
                   │
           amostragem ──▶ 4. Amostragem/      quando o pedido é de amostragem: o desenho.yaml,
                   │                          a conta e Amostragem_00742_AAAA-MM-DD.docx
                   │
        dados adicionar ──▶ 01_revisado_…     a versão que o cliente corrigiu
                   │
               perfil ──▶ perfil.md           o que levar para a reunião
                       └▶ dicionario.csv      as decisões da reunião, escritas
                   │
           descritiva ──▶ 3. Análises/descritiva/
          normalidade ──▶ 3. Análises/normalidade/
           cruzamento ──▶ 3. Análises/cruzamento/   ┐
           associacao ──▶ 3. Análises/associacao/   │  os pares e os itens vêm das
           correlacao ──▶ 3. Análises/correlacao/   │  listas escritas no projeto.yaml
           comparacao ──▶ 3. Análises/comparacao/   ┘
             analisar ──▶ as da lista `analises:`, de uma vez
                   │
            relatorio ──▶ Relatorio_00742_AAAA-MM-DD.docx
```

Um dia típico:

```bash
flatcap doctor                                   # a configuração está de pé?
flatcap listar -n 10                             # o que chegou de novo?
flatcap status                                   # como está cada projeto, e o que atrasou
flatcap novo 42 --sim                            # cria a pasta do projeto
flatcap perfil 42 --sim                          # perfil.md + dicionario.csv
#   reunião: revise o dicionario.csv e escreva as listas no projeto.yaml
flatcap dados adicionar 42 banco_revisado.xlsx --sim   # se veio uma versão nova
flatcap analisar 42 --sim                        # as análises da lista `analises:`
#   leia as tabelas antes de seguir
flatcap relatorio 42 --sim                       # o .docx
```

Um pedido de amostragem começa do mesmo jeito, e a amostragem vem depois do `novo`:

```bash
flatcap novo 23 --sim                            # a pasta do projeto, como sempre
#   depois da reunião: status: cálculo amostral, no projeto.yaml
flatcap amostragem 23 --sim                      # 4. Amostragem/ e o desenho.yaml
#   preencha o desenho.yaml — quase sempre, só a populacao
flatcap amostragem 23 --sim                      # a conta e o relatório da amostra
```

Fora o `doctor`, o `listar` e o `novo`, **nada toca a rede**: a pasta já sabe de quem ela é, e
os testes rodam esses comandos com um token inválido de propósito. O que continua manual é o que
deve continuar: decidir o que analisar, escrever o dicionário e as listas na reunião, e ler o
documento antes de enviar.

## 6. Os comandos

Ajuda de qualquer um: `flatcap <comando> --help`. O `<id>` é o `record_id` **ou** a matrícula
do projeto — esta só quando o cliente tem um projeto.

| Comando | Rede | Escreve | O que faz |
|---|:---:|---|---|
| `flatcap doctor` | sim | nada (ou o `FLATCAP_ROOT`, o `.env` da conta) | confere a configuração, as bibliotecas e a conexão |
| `flatcap listar [-n N]` | sim | nada | as solicitações do REDCap, e quais já viraram pasta |
| `flatcap status` | não | nada | os projetos com pasta — matrícula, nome, status e prazo; os finalizados não aparecem |
| `flatcap novo <record_id>` | sim | a pasta do projeto | cria a pasta, baixa o anexo, escreve a ficha e o histórico |
| `flatcap amostragem <id>` | não | `4. Amostragem/` | o `desenho.yaml` na primeira vez; depois, o tamanho da amostra e o relatório dela |
| `flatcap dados adicionar <id> <arquivo>` | não | `1. Dados originais/` | registra uma versão nova do banco |
| `flatcap dados listar <id>` | não | nada | a linha do tempo das versões, conferida contra o disco |
| `flatcap perfil <id>` | não | `perfil.md`, `dicionario.csv` | descreve o banco e propõe o dicionário |
| `flatcap descritiva <id>` | não | `3. Análises/descritiva/` | frequências, resumos, faixas, períodos e gráficos |
| `flatcap normalidade <id>` | não | `3. Análises/normalidade/` | Shapiro-Wilk, assimetria, curtose e Q-Q |
| `flatcap cruzamento <id>` | não | `3. Análises/cruzamento/` | uma tabela cruzada por par da lista `cruzamento:` |
| `flatcap associacao <id>` | não | `3. Análises/associacao/` | qui-quadrado ou Fisher, pela regra de Cochran |
| `flatcap correlacao <id>` | não | `3. Análises/correlacao/` | Pearson, Spearman ou Kendall, pelos pressupostos |
| `flatcap comparacao <id>` | não | `3. Análises/comparacao/` | testes t e ANOVAs, ou Wilcoxon, Mann-Whitney, Kruskal-Wallis e Friedman, pelos pressupostos: contra referência, entre grupos, entre medidas |
| `flatcap analisar <id>` | não | as pastas das análises | as análises da lista `analises:`, de uma vez |
| `flatcap relatorio <id>` | não | `Relatorio_<matrícula>_<data>.docx` | o documento, montado das rodadas |
| `flatcap template` | não | `template.docx`, `template-decisoes.md` | o modelo do relatório, para ajustar no Word |

As opções que se repetem:

| Opção | Em quais | Efeito |
|---|---|---|
| `--sim` | os que escrevem | executa de fato; sem ele, o comando só mostra o que faria |
| `--env CAMINHO` | todos | usa outro `.env` |
| `--aba NOME` | perfil e análises | a planilha a ler, quando o `.xlsx` tem mais de uma |
| `--rapido` | dados listar, perfil, análises, relatório | não reconfere o `sha256` das versões do banco |
| `--sem-graficos` | descritiva, normalidade, correlação, analisar | escreve só as tabelas, sem carregar o `matplotlib` |
| `--resumo` | analisar | mostra só a tabela do lote |
| `--criar-root`, `--criar-env` | doctor | criam a pasta de dados e o `.env` da conta |
| `--template ARQUIVO`, `--titulo TEXTO` | relatorio, amostragem | o modelo e o título do documento |
| `--saida ARQUIVO` | template | onde escrever o modelo |
| `--version`, `-V` | — | a versão e a licença |

O código de saída é escolhido: **1** quando o comando recusa (configuração faltando, dicionário
inválido, lista vazia, `desenho.yaml` com problema), **0** quando não há nada a fazer (a pasta já existe, o arquivo é igual
ao já registrado), e o traceback só aparece quando é defeito do FlatCap.

## 7. As pastas e os arquivos

### 7.1 Os quatro lugares

| Lugar | O que guarda | Versionado? | Quem protege |
|---|---|---|---|
| o repositório | código, testes, documentação, `.env.example` | sim, no GitHub | o Git |
| a instalação | o `flatcap` instalado (`uv`, `pipx` ou `.venv`) | não | refaz-se com um comando |
| o `.env` | as três chaves | **nunca** | você; o token se pede de novo no REDCap |
| o `FLATCAP_ROOT` | bancos, fichas, dicionários, análises, relatórios, o modelo `.docx` | **nunca** | um backup próprio — o único dos quatro cuja perda não tem volta |

### 7.2 O `FLATCAP_ROOT`

```
FLATCAP_ROOT/                                    fora do Git · backup próprio
├── template.docx                                o modelo institucional do relatório
├── template-decisoes.md                         o que se ajusta no modelo, e onde
│
└── 00742 - José Antônio de Sá/                  o CLIENTE: matrícula - nome
    ├── template.docx                            opcional: o modelo deste cliente
    └── Projeto 006/                             o PROJETO: o record_id, em três dígitos
        ├── projeto.yaml                         a ficha
        ├── historico.md                         uma linha por ação do FlatCap
        ├── perfil.md                            o documento da reunião — regerável
        ├── dicionario.csv                       as decisões da reunião — nunca sobrescrito
        ├── template.docx                        opcional: o modelo só deste projeto
        ├── Relatorio_00742_2026-09-20.docx      o que se entrega — um só aqui
        ├── 1. Dados originais/
        │   ├── 00_redcap_2026-09-01_banco.xlsx       o que veio do REDCap — somente leitura
        │   └── 02_revisado_2026-09-10_banco.xlsx     a versão vigente
        ├── 2. Versões antigas/                       versões do banco, rodadas e relatórios anteriores
        ├── 3. Análises/                              uma pasta por análise, a rodada vigente
        │   ├── descritiva/     manifesto.json · freq_* · graf_* · resumo_* · faixas_* · hist_* · data_* · periodo_*
        │   ├── normalidade/    manifesto.json · normalidade.csv · qq_<variável>.png
        │   ├── cruzamento/     manifesto.json · cruz_<a>_x_<b>.csv
        │   ├── associacao/     manifesto.json · associacao.csv
        │   ├── correlacao/     manifesto.json · correlacao.csv · disp_<a>_x_<b>.png
        │   └── comparacao/     manifesto.json · uma_amostra.csv · dois_grupos.csv · k_grupos.csv · repetidas.csv
        └── 4. Amostragem/                            só com amostragem: nasce no primeiro `flatcap amostragem`
            ├── desenho.yaml                          o plano da amostra — seu, nunca sobrescrito
            ├── tamanho.csv · manifesto.json          a conta e o índice da rodada
            ├── Amostragem_00742_2026-09-05.docx      o relatório da amostra
            └── Versões antigas/                      as rodadas anteriores, cada uma com o desenho.yaml de então
```

Três regras de arrumação: **a pasta vigente guarda uma versão só**; **o que deixa de ser
vigente vai para `2. Versões antigas/`**, com data e hora no nome quando é pasta e `_2` quando o
nome colide; e **o `.docx` fica na raiz do projeto**, onde a mão alcança primeiro. Uma pasta
dentro de `3. Análises/` com `manifesto.json` é uma rodada; sem ele, é pasta sua, e ninguém a
toca.

A amostragem é a exceção às duas últimas, de propósito: **tudo da amostra fica em
`4. Amostragem/`** — o relatório dela e as versões antigas dela também —, e as pastas 1, 2 e 3
ficam para a análise que vem depois. O relatório das análises não vê a amostra, e o da amostra
não vê as análises. Em `4. Amostragem/`, o FlatCap só move o que ele escreveu (`tamanho.csv`,
`manifesto.json`, `Amostragem_*.docx`); o resto da pasta é seu.

### 7.3 O `projeto.yaml`

A ficha do atendimento: quem é o cliente, o que foi combinado e a cronologia dos bancos. O
`novo` a escreve uma vez, com um cabeçalho que explica cada campo; daí em diante o FlatCap só
acrescenta versões em `dados:` e, quando o relatório é escrito, passa o `status:` para
`pronto` — preservando os seus comentários. Um exemplo com todos os blocos:

```yaml
record_id: '6'
tipo: professor                 # professor | aluno
matricula: '00742'              # entre aspas: sem elas, voltaria como o número 742
nome: José Antônio de Sá
criado_em: 2026-09-01
prazo: 2026-09-15               # a data final: 10 dias úteis da reunião — ou 15/09/2026
status: em andamento            # um dos seis: ver abaixo
finalidade: Artigo científico   # sai na primeira página do relatório
objetivos: Avaliar a pressão…   # corrija aqui o que veio truncado do formulário
analises: [descritiva, normalidade, comparacao]   # o que o `analisar` roda, e a ordem do relatório
dados:                          # uma entrada por versão do banco, em ordem
- arquivo: 00_redcap_2026-09-01_banco.xlsx
  origem: redcap
  sha256: a3f1…
  tamanho_bytes: 184320
  data: 2026-09-01

normalidade: [idade, imc, pas]  # opcional: sem ela, todas as numéricas
cruzamento:
  - [sexo, escolaridade]
associacao:
  - [sexo, desfecho]
  - desfecho: [escolaridade, tabagismo]      # uma contra várias
correlacao:
  - [idade, imc]                # a regra escolhe o método
  - [dor, ansiedade, kendall]   # o método escrito manda
comparacao:
  - [imc, 25]                   # uma amostra, contra a referência
  - [imc, sexo]                 # dois grupos: o t de Welch ou, sem a normal, o Mann-Whitney
  - [pas, escolaridade, anova]  # três grupos ou mais: a ANOVA clássica, escrita
  - repetidas: [pas_0, pas_1, pas_2]         # a mesma medida, três vezes
    metodo: anova
```

O **`status:`** é um de seis, e é o que o `flatcap status` mostra:

| Status | Quem escreve | No `flatcap status` |
|---|---|---|
| `não iniciado` | o `flatcap novo`, quando cria a pasta | branco |
| `cálculo amostral` | você, enquanto calcula o tamanho da amostra | ciano |
| `aguardando banco de dados` | você, depois da reunião | amarelo |
| `em andamento` | você | azul |
| `pronto` | o `flatcap relatorio`, quando escreve o documento | verde |
| `finalizado` | você, quando o atendimento termina | não aparece |

Maiúscula, acento e `_` não importam (`Em andamento` e `calculo amostral` valem), e o `novo` e
o `em_analise` das fichas anteriores à 1.17.0 são lidos como `não iniciado` e `em andamento`.
O **`prazo:`** é a data final, escrita à mão depois da reunião, como `2026-09-15` ou
`15/09/2026`; o `flatcap status` mostra a data, e **ATRASADO**, em vermelho, quando ela passa
sem o projeto estar `pronto`. O status fora da lista aparece como está escrito, em magenta, e o
prazo que não é data, em amarelo — os dois com o aviso do que escrever no lugar. As cores
moram no `cli.CORES_DO_STATUS`.

O YAML tem armadilhas com número, e a comparação as reconhece: `[imc, 24,9]` são três itens (a
vírgula decimal separa), `05` é o inteiro 5, e o sinal de `-0,5` não sobrevive à leitura. A
recusa escreve o número certo para copiar; `"24,9"` entre aspas é aceito.

### 7.4 O `dicionario.csv`

As decisões da reunião, escritas: uma linha por variável do banco, em seis colunas, separadas
por `;` e com BOM, para abrir certo no Excel em português.

| variavel | rotulo | tipo | categorias_ordem | faixas | no_banco |
|---|---|---|---|---|---|
| sexo | Sexo | categorica | 1=Feminino\|2=Masculino | | sim |
| escolaridade | Escolaridade | categorica | Fundamental\|Médio\|Superior | | sim |
| idade | Idade (anos) | numerica | | 0\|18\|30\|45\|60\|120 | sim |
| data_coleta | Data da coleta | data | | | sim |
| prontuario | Prontuário | ignorar | | | sim |

- `tipo` é `categorica`, `numerica`, `data` ou `ignorar`.
- `categorias_ordem` é a ordem das categorias na tabela; numa coluna de código, o rótulo vem
  depois do `=`. Dois códigos com o mesmo rótulo se somam, com aviso.
- `faixas` são os cortes de uma numérica, na convenção `[a a b)`; em branco, os quartis.
- `no_banco` é a única coluna que o FlatCap reescreve: `nao` quando a coluna sumiu do banco.

**A linha que você editou nunca é sobrescrita**: o `perfil` só acrescenta as variáveis novas.
E **a ordem das linhas é a ordem do relatório**: reordenar o dicionário reordena o documento.
As linhas começadas por `#` no topo do arquivo explicam a sintaxe e são reescritas a cada
gravação; depois do cabeçalho das colunas, `#` é dado.

### 7.5 O que cada análise escreve

| Pasta | Arquivo | O que mostra |
|---|---|---|
| `descritiva/` | `freq_<var>.csv`, `graf_<var>.png` | categoria · n · % dos válidos · % do total, com `(sem informação)` e `Total`; as barras com `n (%)` |
| | `resumo_<var>.csv`, `faixas_<var>.csv`, `hist_<var>.png` | n, faltantes, mínimo, quartis, máximo, média e desvio; as faixas; o histograma |
| | `data_<var>.csv`, `periodo_<var>.csv`, `graf_periodo_<var>.png` | o período e a distribuição por mês ou por ano |
| `normalidade/` | `normalidade.csv`, `qq_<var>.png` | n, faltantes, assimetria, curtose, W, p e uma leitura em palavras; o Q-Q |
| `cruzamento/` | `cruz_<a>_x_<b>.csv` | cada combinação, com n e % — uma tabela por par |
| `associacao/` | `associacao.csv` | o par, n, o teste, o p e o V de Cramér |
| `correlacao/` | `correlacao.csv`, `disp_<a>_x_<b>.png` | o par, n, o método, o coeficiente, o IC 95% e o p; a dispersão |
| `comparacao/` | `uma_amostra.csv`, `dois_grupos.csv`, `k_grupos.csv`, `repetidas.csv` | uma tabela por delineamento pedido |

Todos os `.csv` seguem uma convenção: UTF-8 com BOM, `;` entre os campos, vírgula decimal, sem
separador de milhar, e as primeiras linhas, começadas por `#`, com o título, a variável, os
denominadores e — nos testes — qual teste rodou e por que a regra o escolheu.

### 7.6 O `manifesto.json`

Um por rodada, escrito por último: o índice que o relatório percorre. Responde, sem depender da
memória, de qual variável saiu cada arquivo, sobre qual banco (arquivo, `sha256`, integridade),
com quais versões de biblioteca, com quais regras e quais colunas do banco — e o que ficou de
fora, e por quê. O número de `formato` na primeira chave faz um manifesto de outra versão ser
recusado com uma frase, e não lido errado.

É também de onde sai o texto padrão de metodologia da primeira página do relatório — o
subtítulo "Metodologia Estatística (texto padrão)" e um parágrafo, depois da finalidade e dos
objetivos. Os testes de cada par, item e delineamento estão nos `detalhes`, o alfa e a
correção para comparações múltiplas nas `regras`, e a versão do Python no `ambiente`; o
parágrafo nomeia só o que está ali, e acompanha a rodada quando ela é refeita. A redação se
ajusta no bloco editável do topo de `src/flatcap/metodologia.py`.

### 7.7 O `historico.md` e o `perfil.md`

O `historico.md` ganha uma linha por ação do FlatCap na pasta, e nunca é reescrito: é a
resposta a "o que eu fiz aqui?" seis meses depois. O `perfil.md` é o documento que vai impresso
para a reunião: o cabeçalho (arquivo, separador, codificação, integridade), **o que levar para
a reunião** — os achados em *corrigir antes de começar*, *confirmar com o cliente* e *notas* —,
e as consultas (variáveis, valores observados, resumo das numéricas, o dicionário).

### 7.8 O `desenho.yaml`

O plano da amostra, preenchido à mão. O `flatcap amostragem` escreve o modelo comentado na
primeira vez e, dali em diante, só lê. O modelo já vem com o caso mais comum, e quase sempre
basta a população:

| Chave | O que é |
|---|---|
| `desenho` | `aas` — amostragem aleatória simples, sem reposição, o único por enquanto. `AAS` e `Aleatória simples` valem |
| `populacao` | N, sem ponto de milhar (`12000`). Em branco, a conta é a de população grande, sem a correção |
| `confianca` | o nível de confiança, em % (`95`, e não `0.95`) |
| `margem` | a margem de erro: em pontos percentuais, para uma proporção; na unidade da variável, para uma média. A vírgula decimal vale (`2,5`) |
| `proporcao` | a proporção esperada, em %: `50` quando não se sabe, que dá o maior tamanho |
| `desvio` | no lugar da `proporcao`, para estimar uma média: o desvio-padrão esperado |
| `perda` | a perda esperada, em %, de 0 a 100 sem o 100 |
| `n` | o tamanho já decidido, no lugar da conta — com ele, `confianca`, `margem` e `proporcao` ficam em branco |

A conta é a do OpenEpi: n₀ = z²·V/e², com V = p(1 − p) ou σ²; com a população,
n = N·z²·V/[(N − 1)·e² + z²·V], que é o n₀ corrigido; com a perda, ⌈n/(1 − perda)⌉. Cada passo
arredonda para cima, e o tamanho nunca passa de N — quando chega a ele, é um censo, e o comando
avisa. O z é o `qnorm(1 − α/2)` do R. Com N = 1200, 95%, 5 pontos, 50% e perda de 10%, o
`tamanho.csv` diz n₀ = 385, n = 292 e 325.

As recusas são as do engano que muda o número em silêncio, e saem todas de uma vez: `12.000`,
que no YAML é doze; a confiança ou a proporção escritas como fração (`0.95`, `0.5`); a
confiança escrita como o α (`5`); a margem que não cabe na proporção; a chave com acento; e os
desenhos previstos e ainda não feitos — sistemática, estratificada, conglomerados, PPT e dois
estágios —, que dizem isso, e não que não existem. A margem escrita como fração
(`margem: 0.05`) passa por todas, porque 0,05 ponto existe, e sai com aviso.

## 8. A arquitetura

### 8.1 As camadas

O pacote é uma lista de módulos em que **cada um só conhece os de cima** (a exceção é o
`documento`, que o `relatorio` e a `amostragem` chamam de dentro da execução — ver o docstring
do `__init__.py` na Parte II):

| Camada | Módulos | Bibliotecas de fora |
|---|---|---|
| a configuração e o REDCap | `config`, `redcap`, `modelo`, `nomes` | `python-dotenv`, `requests` |
| a pasta e a ficha | `projeto`, `ficha`, `dados`, `painel` | `pyyaml`, `ruamel.yaml` |
| o banco e a reunião | `banco`, `dicionario`, `perfil` | `pandas`, `openpyxl` |
| o contrato de saída | `manifesto`, `graficos` | `matplotlib` (só o `graficos`) |
| as análises | `descritiva`, `normalidade`, `cruzamento`, `associacao`, `correlacao`, `hipoteses`, `comparacao`, `analises` | `pandas`, `scipy` |
| o documento | `metodologia`, `relatorio`, `documento` | `python-docx` (só o `documento`) |
| a amostragem | `amostral`, `amostragem` | nenhuma: a conta é da biblioteca padrão, e o `.docx` sai pelo `documento` |
| a interface | `cli` | `typer`, `rich` |

As bibliotecas caras ficam presas a poucos módulos, e entram **dentro da função que as usa**:
a simulação não desenha nada e não paga pelo `matplotlib`; o `listar`, que roda várias vezes
por dia, não paga pelo `pandas`.

### 8.2 As regras que explicam o resto

- **Código no Git, dados fora.** Nenhum caminho fixo no código: tudo deriva do
  `FLATCAP_ROOT`, lido num lugar só, o `config.py`.
- **Decidir e escrever são funções separadas.** `preparar_*` lê, calcula e devolve um plano
  imutável; `executar_*` só escreve. A simulação é o mesmo plano sem o `executar`.
- **Tudo o que circula é imutável** (`frozen`) — a exceção é o `DataFrame` dentro do `Banco`.
- **Cada módulo tem o seu erro.** A CLI captura as classes declaradas e as mostra num painel;
  qualquer outra exceção é defeito, e sobe com o traceback.
- **Quem só mexe em arquivo local recebe `Path`, e não `Config`**: do `dados` em diante,
  nenhum comando pode falhar por token expirado.
- **Quem calcula não desenha, e quem monta não formata.** O `descritiva.py` conta e o
  `graficos.py` desenha; o `relatorio.py` monta e o `documento.py` formata.
- **O relatório não abre o banco.** Ele lê os manifestos e os `.csv`, e um número do `.docx` é,
  letra por letra, o número do `.csv`.
- **O que se analisa está escrito na ficha.** A única análise com padrão é a normalidade, que é
  pressuposto, e não resultado.
- **Importar a aritmética, escrever as decisões — e conferir contra o R.** O `scipy` entra onde
  calcula igual ao R; onde não calcula, a conta é escrita ou transcrita no módulo (ver a
  [seção 11](#11-licença-e-avisos)).
- **Nada se sobrescreve em silêncio.** A gravação é atômica — temporário na mesma pasta,
  `fsync`, `os.replace` —, o texto sai em UTF-8 com `\n`, e o que deixa de valer vai para
  `2. Versões antigas/` — ou, na amostragem, para `4. Amostragem/Versões antigas/`. Uma falha
  no meio desfaz o que já foi feito.

## 9. Os testes

```bash
pytest              # a suíte offline — alguns minutos: os gráficos são desenhados a 600 DPI
pytest -m e2e       # a ponta a ponta: o flatcap como subprocesso contra um REDCap falso
pytest -m ""        # as duas
ruff check src tests tools
python tools/gerar_doc.py --conferir   # este documento em dia com os comentários do código
```

- **Um módulo em `src/flatcap/` pede um `test_` de mesmo nome** em `tests/`.
- **Nenhum número estatístico é conferido contra o próprio módulo**: as referências são o R
  4.3.3 (constantes `*_DO_R`), os exemplos da documentação do R e a força bruta em frações.
- **Nada toca a rede, e o relógio é injetado**: a suíte roda com um token inválido, e todo
  `preparar_*` aceita `agora=`.
- Os ajudantes moram em `tests/conftest.py` (as fixtures em escada: `projeto_vazio`,
  `projeto_com_banco`, `projeto_com_rodada`), `tests/bancos.py` (os bancos de mentira, feios de
  propósito) e `tests/servidor_falso.py` (o REDCap de mentira, para a ponta a ponta).
- Os testes `test_o_que_so_se_ve_*` não testam nada: lembram que um `.docx` e um `.png` se
  conferem abrindo.

O repositório não tem integração contínua: essas conferências rodam na máquina de quem muda o
código, antes do commit, e são elas que mantêm o `main` de pé. O **pre-commit**
(`.pre-commit-config.yaml`) roda o `ruff`, as conferências de arquivo, o `gitleaks` e um gancho
que barra banco, relatório e `.env` mesmo com `git add -f`.

O ritual completo de uma mudança está no [`CONTRIBUTING.md`](../CONTRIBUTING.md).

## 10. As versões

Uma versão é o número em `src/flatcap/__init__.py` (`__version__`) — o **único lugar**: o
`pyproject.toml` o lê de lá, e o `flatcap --version` o mostra. Por enquanto, o FlatCap não
publica pacotes nem etiquetas: quem instala pelo repositório ([seção 2](#2-instalação))
recebe o que está no `main`, e o `uv tool upgrade flatcap` traz o que entrou depois.

Para fechar uma versão:

1. Suba o `__version__` no `__init__.py`.
2. Escreva a seção da versão no docstring do `__init__.py` (o porquê) e no `CHANGELOG.md` (o
   quê, em uma linha por mudança).
3. Rode `python tools/gerar_doc.py` e o ritual do [`CONTRIBUTING.md`](../CONTRIBUTING.md), e
   faça o commit no `main`.

**E um executável, sem Python?** Dá para empacotar o FlatCap com o PyInstaller num executável
por sistema, mas com o `pandas`, o `scipy` e o `matplotlib` dentro ele costuma passar de 100 MB,
precisa ser construído em cada sistema, e antivírus costumam desconfiar de executável novo. O
`uv` resolve o mesmo problema — instalar sem ter o Python — sem nenhum desses custos.

## 11. Licença e avisos

O FlatCap é software livre, sob a **GNU General Public License, versão 3 ou posterior**
(`GPL-3.0-or-later`): qualquer pessoa pode usar, estudar, modificar e redistribuir, e quem
redistribuir uma versão modificada precisa distribuí-la sob a mesma licença, com o
código-fonte.

- O texto integral está no [`LICENSE`](../LICENSE); o titular, os avisos e as atribuições, no
  [`NOTICE.md`](../NOTICE.md).
- Todo arquivo de código começa com o cabeçalho SPDX:

  ```python
  # SPDX-FileCopyrightText: 2026 Matheus Fernandes
  # SPDX-License-Identifier: GPL-3.0-or-later
  ```

- **Os trechos transcritos do R.** O R é distribuído sob a GPL-2.0-or-later, e a GPL-3.0 é uma
  das licenças que o "or later" permite. Cada trecho diz de onde veio, no docstring e no
  `NOTICE.md`:

  | No FlatCap | No R |
  |---|---|
  | `correlacao.prho` — o p exato do Spearman | `src/library/stats/src/prho.c` (o AS 89, Best e Roberts, 1975) |
  | `correlacao.spearman`, `correlacao.kendall` | `src/library/stats/R/cor.test.R` |
  | `associacao.qui_quadrado` | `src/library/stats/R/chisq.test.R` |
  | `associacao._fisher_2x2` | `src/library/stats/R/fisher.test.R` |
  | `hipoteses.anova_de_medidas_repetidas` | o `anova.mlm`, em `src/library/stats/R/mlm.R` |
  | `hipoteses.wilcoxon_uma_amostra`, `hipoteses.mann_whitney` — a escolha entre o p exato e a aproximação, e o intervalo e a estimativa de Hodges-Lehmann | o `wilcox.test.default`, em `src/library/stats/R/wilcox.test.R`, na versão do R até a 4.5 |
  | `hipoteses._raiz` — a busca de raiz do `uniroot`, pelo método de Brent | o `R_zeroin2`, em `src/library/stats/src/zeroin.c` |
  | `hipoteses._quantil` — o quantil das distribuições exatas | o `qsignrank` e o `qwilcox`, em `src/nmath/signrank.c` e `src/nmath/wilcox.c` |
  | `hipoteses.friedman` | `src/library/stats/R/friedman.test.R` |

  O Fisher das tabelas maiores que 2×2 é uma implementação própria do algoritmo de rede de
  Mehta e Patel (1983), e não uma transcrição do `fexact.c`. As distribuições exatas do posto
  sinalizado e da soma dos postos também são próprias — contagens em inteiros —, e não a
  recursão do `csignrank` e do `cwilcox`.

- `flatcap --version` mostra a licença, no formato dos programas GNU.
- O FlatCap não é afiliado à Vanderbilt University nem ao REDCap Consortium.

## 12. Como este documento é feito

A Parte I é escrita à mão, aqui. A Parte II é gerada por `tools/gerar_doc.py`, que lê os
arquivos de `src/flatcap/` com o `ast` e o `tokenize` da biblioteca padrão e escreve, módulo
por módulo e na ordem do arquivo:

- o **docstring do módulo**, com os títulos internos rebaixados para caber debaixo do título
  do módulo;
- cada **classe e cada função**, com os parâmetros e a linha, e o docstring logo abaixo;
- os **comentários de uma linha que separam trechos do código** (`# Camada de rede`), como
  títulos;
- o **comentário logo acima de uma constante** do módulo, debaixo de um título com o nome
  dela;
- os **outros comentários**, em citação, com a linha — os do módulo marcados como tal, para não
  parecerem da função de cima;
- os **comentários no fim de uma linha de código**, numa lista, ao lado do código;
- as **strings soltas** usadas como comentário, como os comentários.

```bash
python tools/gerar_doc.py             # reescreve a Parte II
python tools/gerar_doc.py --conferir  # não escreve; falha se a Parte II estiver velha
                                      # ou se algum comentário do código não estiver aqui
```

O `--conferir` faz parte do ritual de cada mudança, no [`CONTRIBUTING.md`](../CONTRIBUTING.md):
ele acusa o comentário mudado sem o documento regerado. E confere, independentemente da
formatação, que **todo** comentário `#`, todo docstring e toda string solta de `src/flatcap/`
aparece neste documento.

<!-- Daqui para baixo, o documento é gerado por tools/gerar_doc.py a partir dos comentários de src/flatcap/. Não edite à mão: mude o comentário no código e rode o script. -->

# Parte II — O código, comentário por comentário

Tudo o que o código de `src/flatcap/` diz de si mesmo: o docstring de cada módulo, de cada classe e de cada função, e cada comentário, na ordem em que aparecem no arquivo, com a linha. Os módulos vêm na ordem das camadas — cada um só conhece os de cima.

- [`flatcap/__init__.py`](#flatcap__init__py)
- [`flatcap/config.py`](#flatcapconfigpy)
- [`flatcap/redcap.py`](#flatcapredcappy)
- [`flatcap/modelo.py`](#flatcapmodelopy)
- [`flatcap/nomes.py`](#flatcapnomespy)
- [`flatcap/projeto.py`](#flatcapprojetopy)
- [`flatcap/ficha.py`](#flatcapfichapy)
- [`flatcap/dados.py`](#flatcapdadospy)
- [`flatcap/painel.py`](#flatcappainelpy)
- [`flatcap/banco.py`](#flatcapbancopy)
- [`flatcap/dicionario.py`](#flatcapdicionariopy)
- [`flatcap/perfil.py`](#flatcapperfilpy)
- [`flatcap/manifesto.py`](#flatcapmanifestopy)
- [`flatcap/graficos.py`](#flatcapgraficospy)
- [`flatcap/descritiva.py`](#flatcapdescritivapy)
- [`flatcap/normalidade.py`](#flatcapnormalidadepy)
- [`flatcap/cruzamento.py`](#flatcapcruzamentopy)
- [`flatcap/associacao.py`](#flatcapassociacaopy)
- [`flatcap/correlacao.py`](#flatcapcorrelacaopy)
- [`flatcap/hipoteses.py`](#flatcaphipotesespy)
- [`flatcap/comparacao.py`](#flatcapcomparacaopy)
- [`flatcap/analises.py`](#flatcapanalisespy)
- [`flatcap/metodologia.py`](#flatcapmetodologiapy)
- [`flatcap/relatorio.py`](#flatcaprelatoriopy)
- [`flatcap/documento.py`](#flatcapdocumentopy)
- [`flatcap/amostral.py`](#flatcapamostralpy)
- [`flatcap/amostragem.py`](#flatcapamostragempy)
- [`flatcap/cli.py`](#flatcapclipy)
- [`flatcap/__main__.py`](#flatcap__main__py)

## `flatcap/__init__.py`

`SPDX-FileCopyrightText: 2026 Matheus Fernandes` · `SPDX-License-Identifier: GPL-3.0-or-later`

*686 linhas.*

FlatCap — o pacote é organizado em camadas finas, cada uma com uma responsabilidade:

    config.py      lê e valida credenciais e caminhos (.env)
    redcap.py      conversa com a API do REDCap
    modelo.py      traduz o questionário para o domínio (Cliente)
    nomes.py       regra de nomenclatura das pastas (cliente e projeto) e busca no disco
    projeto.py     monta a pasta do projeto: decide um Plano e depois o escreve
    ficha.py       lê e escreve o projeto.yaml; encontra o projeto a partir de um id
    dados.py       versiona os bancos: adiciona, roda a anterior, confere o disco
    painel.py      o painel do `flatcap status`: o status e o prazo de cada projeto
    banco.py       abre a versão vigente do banco como um quadro do pandas
    dicionario.py  lê, funde e escreve o dicionario.csv
    perfil.py      diagnostica o banco e escreve o perfil.md
    manifesto.py   o formato do manifesto.json e o contrato de saída das análises
    graficos.py    desenha os .png a partir das tabelas já calculadas
    descritiva.py  obedece ao dicionário: conta, resume e monta as tabelas
    normalidade.py testa a normalidade das numéricas (Shapiro-Wilk, forma, Q-Q)
    cruzamento.py  cruza pares de categóricas: uma tabela por par
    associacao.py  testa a associação entre pares de categóricas (qui-quadrado ou Fisher)
    correlacao.py  correlaciona pares de numéricas (Pearson, Spearman ou Kendall)
    hipoteses.py   a aritmética dos testes de comparação, como o R (sem pandas)
    comparacao.py  compara contra uma referência, entre grupos e entre medidas repetidas
    analises.py    o lote: roda as análises da lista `analises:` da ficha, em ordem
    metodologia.py o parágrafo de metodologia da primeira página, a partir dos manifestos
    relatorio.py   lê o manifesto e monta o conteúdo do documento
    documento.py   escreve o .docx a partir do conteúdo já montado
    amostral.py    a aritmética do tamanho da amostra, só com a biblioteca padrão
    amostragem.py  o desenho.yaml, a conta e o relatório da amostra, em 4. Amostragem/

    cli.py         expõe os comandos no terminal

A dependência anda sempre para cima nessa lista: `dados` conhece `ficha`, `ficha` conhece
`projeto`, `painel` conhece só `ficha` e `projeto`, `perfil` conhece `banco` e `dicionario`,
`descritiva` conhece `banco`, `dicionario` e `manifesto`, `metodologia` conhece só o
`manifesto`, `relatorio` conhece `manifesto`, `metodologia`, `dicionario`, `dados` e `ficha`,
e nenhuma delas conhece a `cli`. A exceção é o par `relatorio`–`documento`: o `documento`
conhece o `Relatorio` que recebe, e o `relatorio` só chama o `documento` de dentro do
`executar_relatorio`. A `amostragem` conhece `amostral`, `ficha`, `manifesto` e `relatorio`,
e chama o `documento` do mesmo jeito, de dentro do `executar_amostragem`.

É o que permite testar tudo sem simular terminal — e trocar a implementação de `ficha.py` sem
que nenhum outro módulo perceba.

Duas divisões da Fase 4 valem ser lidas juntas: `banco.py` é o único módulo que abre o arquivo
do cliente, para que as Fases 5 e 6 não voltem a decidir qual arquivo é o banco; e
`dicionario.py` não importa o `pandas`, porque o formato do arquivo que guarda as decisões da
reunião não depende de como o banco foi lido.

A Fase 5 repete a divisão em outro eixo: `descritiva.py` calcula e não desenha, `graficos.py`
desenha e não calcula, e `manifesto.py` não importa nem o `pandas` nem o `matplotlib` — é o
índice que a Fase 6 lê para montar o `.docx` sem reabrir o banco.

A Fase 6 repete a divisão pela terceira vez, e cobra a promessa da segunda: `relatorio.py`
monta o conteúdo e não formata, `documento.py` formata e não decide, e **nenhum dos dois abre
o banco**. Um número que aparece no `.docx` é, letra por letra, o número que está no `.csv`
que a Fase 5 escreveu — não há uma segunda fonte para o mesmo 37%. Foi por isso que
`versao_vigente` desceu para `ficha.py` e `PASTA_DESCRITIVA` para `projeto.py`: as duas
perguntas moravam em módulos que carregam o `pandas`, e nenhuma das duas precisa dele.

### 1.1.0 — um cliente, vários projetos

A pasta do cliente deixou de ser a pasta do projeto:

    FLATCAP_ROOT/00742 - José Antônio de Sá/Projeto 006/projeto.yaml

O mesmo professor volta ao REDCap com um estudo novo e recebe um `record_id`
novo para a mesma matrícula. Antes, a segunda solicitação batia em "já existe
pasta para essa matrícula" e não tinha para onde ir.

A consequência que atravessa o pacote é de **identidade**: a matrícula
identifica a pessoa e parou de identificar o trabalho. Quem identifica o
trabalho é o `record_id`. Onde os dois eram intercambiáveis — a busca do
`ficha.localizar_projeto`, a coluna "Pasta local" do `listar`, a recusa de
duplicata do `novo` — agora há uma ordem: `record_id` primeiro, matrícula
depois e só quando ela não for ambígua.

`nomes.py` ganhou o segundo nível (`nome_do_projeto`, `projetos_do_cliente`,
`caminho_do_projeto`, `rotulo_do_projeto`) e continua sendo o único módulo que
sabe como uma pasta se chama. Pasta no formato antigo é reconhecida e
diagnosticada, nos dois módulos que esbarram nela, com um texto só
(`projeto.texto_da_migracao`) — a migração é manual, e de propósito: mover
pasta do usuário é coisa que o FlatCap nunca fez sozinho.

### 1.2.0 — a segunda análise, e o que ela cobrou

A Fase 7 acrescenta um módulo (`normalidade.py`) e um comando, e o resto da
versão é o preço de deixar de ter uma análise só. Quatro coisas mudaram de casa,
todas na mesma direção de sempre — para baixo, para o módulo que é dono da
pergunta:

**`Tabela` e `Grafico` desceram para o `manifesto.py`.** Eles são o contrato de
saída de **qualquer** análise, e moravam no módulo que importa o `pandas`. Deixá-los
lá obrigaria toda análise nova a importar a descritiva, acoplando duas análises
que não têm nada a ver uma com a outra. O `descritiva.py` reexporta os dois.

**A `SEMENTE` desceu junto**, pelo mesmo motivo que `versao_vigente` e
`formato_de_data` já tinham descido: é um valor que todo manifesto registra, e
duas sementes em dois módulos é como duas rodadas do mesmo projeto deixam de ser
reproduzíveis uma contra a outra.

**As duas recusas do dicionário ficaram públicas no `descritiva.py`**, com a
classe de erro como parâmetro. Duas regras da casa se cruzam ali: a conferência
precisa ser **uma só** (senão um comando aceita o que o outro recusou) e o painel
precisa levar o nome do comando que o usuário rodou. Passar a classe resolve as
duas sem escolher entre elas.

**O `manifesto.json` ganhou `analise` e `colunas`.** O primeiro diz de qual
análise é a rodada, sem depender do nome da pasta. O segundo diz **quais colunas
do banco** o item usou — e é ele que faz as conferências do relatório continuarem
valendo quando um item não é uma variável, como a tabela de normalidade, que fala
de todas de uma vez. O número de formato continua em `1`: os dois campos são
aditivos e não produzem interpretação errada nenhuma em quem não os conhece.

E uma que não mudou, contra a expectativa: **o `graficos.py` nunca escolheu a
pasta.** O `desenhar` sempre recebeu o caminho como parâmetro, e por isso a
normalidade escreve em `3. Análises/normalidade/` sem que uma linha dele mude. O
que ele ganhou foi a espécie `qq` e um registro de espécies no lugar do
`if/elif/else` — que, com mais de uma análise, desenhava espécie desconhecida como
gráfico de colunas em silêncio.

### 1.3.1 — o relatório passa a enxergar a segunda análise

A Fase 7 escreveu a normalidade no disco e **não** no documento. O
`preparar_relatorio` lia uma pasta de nome fixo, `3. Análises/descritiva/`, e o
`normalidade.csv` e os `qq_*.png` ficavam no disco sem que nada os apanhasse — os
dois comandos saindo com código 0, e a falta aparecendo só para quem abrisse o
`.docx` procurando. O teste t e o qui-quadrado cairiam no mesmo buraco.

São três peças, e elas se sustentam:

**O relatório varre `3. Análises/*/`.** Quem responde onde as rodadas moram é o
`projeto.pastas_das_analises`, ao lado do `pasta_da_analise` que a Fase 7 já tinha
criado para isso. Pasta com `manifesto.json` dentro é rodada; pasta sem, é pasta
sua. Nenhum nome de análise está escrito no `relatorio.py` — a próxima análise
entra no documento sem que uma linha dele mude, que era a promessa da arquitetura.

**A lista `analises:` da ficha dirige a ordem das seções.** Ela é prometida desde
a Fase 2 — *"o que foi combinado na reunião"* — e até aqui não era lida por
ninguém. O que não estiver nela sai na `ORDEM_PADRAO_DAS_ANALISES` do
`manifesto.py`, e nome escrito na ficha sem rodada no disco vira aviso no
terminal, porque quase sempre é a análise que você combinou e ainda não rodou.

**A conferência do dicionário pergunta por `colunas_usadas`.** O campo
`ItemDoManifesto.colunas` existia desde a Fase 7 e nada o lia. Comparar por
`item.variavel` funcionava enquanto todo item era uma variável; com a tabela de
normalidade, que fala de doze de uma vez e sai com `variavel=""`, todo relatório
passaria a dizer «`` saiu da descritiva depois da rodada».

O `Relatorio` ganhou `rodadas`, e `manifesto` passou a ser o **principal** — o da
descritiva quando ela existe. As propriedades do `.docx` e o cabeçalho do terminal
precisam de um banco e de uma data, e com mais de uma rodada isso deixou de ser
automático.

### 1.4.0 — o cruzamento

**`cruzamento.py`: uma tabela por par de categóricas.** Cada combinação de
categorias, quantos casos e o percentual sobre quem respondeu as duas — o `cruz()`
que se fazia à mão. Os pares vêm da lista `cruzamento:` da ficha, e a numérica de
poucos valores entra marcada `categorica` no dicionário. Sem teste e sem gráfico.

É a terceira análise e a primeira a entrar sem que o `relatorio.py` mude uma
linha: a varredura de `3. Análises/*/` da 1.3.1 a encontra sozinha. E o campo
`colunas` do manifesto, que a 1.2.0 criou esperando um par, é o que mantém as
conferências do relatório certas para uma seção que fala de duas colunas.

**`serie_de_texto` e `percentual` ficaram públicas no `descritiva.py`.** A
categoria do cruzamento sai escrita pelas mesmas funções que escrevem a tabela de
frequência da mesma variável: `1` vira `Feminino` do mesmo jeito nas duas, e um
código que o Excel leu como `1.0` não sai `1.0` em nenhuma delas.

**O `documento.py` alinha pelo conteúdo, e não pela posição.** Texto à esquerda,
número à direita. Até aqui só a primeira coluna ia à esquerda, e a segunda coluna
do cruzamento — que também é rótulo — sairia empurrada para a direita. A coluna
`leitura` da normalidade já saía assim, e passa a sair à esquerda.

### 1.5.0 — a associação

**`associacao.py`: qui-quadrado ou exato de Fisher, escolhido pela regra de
Cochran.** Os pares vêm da lista `associacao:` da ficha, em duas formas — o par
`[sexo, desfecho]` e a variável contra várias, `desfecho: [sexo, escolaridade]` —,
e saem numa tabela só: variável 1, variável 2, n, teste, p-valor e o V de Cramér.
A justificativa de cada escolha — a menor esperada e quantas caselas ficaram
abaixo de 5 — vai para as notas do `.csv` e para o manifesto, com a tabela de
contingência inteira.

**O V de Cramér sai ao lado do p**, porque o p depende do n e o V mede o tamanho
da associação. Ele usa sempre o X² de Pearson sem correção, qualquer que seja o
teste da linha, e sai também nas linhas do Fisher.

Os dois testes são os do R. O qui-quadrado é o `chisq.test` com o padrão dele:
Yates só na 2×2, e nunca maior do que a diferença. O Fisher é o `fisher.test`:
2×2 pela hipergeométrica e as maiores **exatas**, pelo algoritmo de rede. Essa
aritmética está escrita no módulo, e não importada, porque o `scipy` calcula a
tabela maior que 2×2 por simulação, sem semente — o p mudaria a cada rodada. A
conferência é contra os exemplos da documentação do R e contra a força bruta.

É a quarta análise, e de novo o `relatorio.py` não muda uma linha. Ela entra na
`ORDEM_PADRAO_DAS_ANALISES` logo depois do cruzamento, e o `valor_p` da
normalidade ficou público: o p sai escrito do mesmo jeito nas duas tabelas.

### 1.6.0 — a correlação

**`correlacao.py`: Pearson, Spearman ou Kendall, escolhido pelos pressupostos de
cada par.** Os pares vêm da lista `correlacao:` da ficha, nas duas formas da
associação, e o par aceita um terceiro nome, que é o método: `[dor, ansiedade,
kendall]`. Sem ele, a regra escolhe — Kendall quando alguma das duas tem até 10
valores distintos, com repetição; Spearman quando alguma é categórica ou quando o
Shapiro-Wilk rejeita a normal em alguma; Pearson nos outros casos. A frase de cada
escolha vai para as notas do `.csv`, para o terminal e para o manifesto, e o
método escrito contra a regra sai com aviso.

Sai uma tabela só — variável 1, variável 2, n, método, coeficiente, IC 95% e
p-valor — e uma dispersão por par, em que o ponto cresce onde vários casos
coincidem. Os três são o `cor.test` do R, e o Spearman pede aritmética escrita
aqui: o `scipy` usa sempre a aproximação t, e o R é exato até n = 1290 sem
empates, pelo algoritmo AS 89 — transcrito do `prho.c`. O intervalo do Spearman e
o do Kendall, que o R não dá, saem pela transformação de Fisher com os
erros-padrão de Bonett e Wright.

Uma escala marcada `categorica` entra, se o código for número: pela ordem dos
códigos, e só por Spearman ou Kendall.

É a quinta análise, e o `relatorio.py` continua sem mudar uma linha. O
`graficos.py` ganhou a espécie `dispersao`, o Shapiro-Wilk da normalidade ficou
público — a tabela de normalidade e a escolha da correlação saem da mesma
chamada —, e a correlação entra na `ORDEM_PADRAO_DAS_ANALISES` logo depois da
normalidade.

### 1.7.0 — a comparação

**`comparacao.py`: a média de uma numérica contra um valor de referência — o t de
Student para uma amostra.** Os itens vêm da lista `comparacao:` da ficha, `[imc,
25]`, e um terceiro nome, `t`, força o teste. Sai uma tabela só — variável, n,
média (DP), IC 95% da média, referência, teste e p-valor —, com a frase de cada
escolha nas notas do `.csv`, no terminal e no manifesto.

**Uma análise para todos os testes de comparação**, e não um módulo por teste: o
que se escreve na reunião é a pergunta, e o teste sai do delineamento e dos
pressupostos. A regra é a da correlação: o Shapiro-Wilk sobre os valores da
variável, pela mesma função da normalidade; o t quando ele não rejeita a normal, e
o Wilcoxon quando rejeita. O Wilcoxon está na regra e ainda não no cálculo: a linha
dele sai sem teste, com o motivo, e o aviso ensina a escrever `t` no item quando o
t valer ali.

**`hipoteses.py`: a aritmética dos testes, fora da análise.** Recebe números e
devolve um `Resultado`, que é o `htest` do R. O t de uma amostra é o `t.test`, pelo
`scipy`, que aqui faz igual. A fronteira existe porque o pareado é a uma amostra
sobre as diferenças, e o motor precisa estar onde os próximos delineamentos o
alcancem.

**A vírgula decimal da ficha.** `[imc, 24,9]` é lido pelo YAML como três itens, e a
recusa reconhece o engano e escreve o número certo para copiar — com o zero à
esquerda da parte decimal, que o `24,05` perderia, e o aviso de que o sinal de
`-0,5` não sobrevive à leitura.

**`descritiva.resumo_numerico` ficou pública**, com o apelido privado: a média da
tabela da comparação é, letra por letra, a do `resumo_<variável>.csv`.

É a sexta análise, e o `relatorio.py` continua sem mudar uma linha. Ela entra na
`ORDEM_PADRAO_DAS_ANALISES` no fim, depois da correlação.

### 1.8.0 — dois grupos, e o t de Student

**A comparação entre os dois grupos de uma categórica.** `[imc, sexo]` na lista
`comparacao:`, ou `sexo: [imc, idade]` para várias de uma vez. Os grupos saem do
banco, e não do dicionário: os rótulos com resposta entre os casos que responderam
as duas variáveis, pelas mesmas `serie_de_texto` e `rotulo_de` da associação, na
ordem do dicionário — que decide o sinal da diferença. Três ou mais grupos ainda não
estão no FlatCap, e o item é recusado com a frase que diz isso.

**A regra é a mesma, grupo a grupo.** O Shapiro-Wilk em cada grupo; a normal se
sustenta quando se sustenta em todos. O paramétrico da regra é o **t de Welch** — o
padrão do `t.test` do R, que não supõe variâncias iguais e dispensa o Levene —, e
ele ainda não está no FlatCap: sem método escrito, a linha sai sem teste, e o aviso
ensina a escrever `student`. **O t de Student** roda quando está escrito no item, é o
`t.test(var.equal = TRUE)` do R pelo `scipy`, e sai com o aviso de quanto o maior
desvio padrão passa do menor quando passa de duas vezes.

**Uma tabela por delineamento, na mesma pasta.** `uma_amostra.csv`, como antes, e
`dois_grupos.csv`, com um bloco por item: a linha da comparação — n, diferença das
médias com o IC 95%, teste e p — e uma linha por grupo, com n, média e desvio. O
manifesto ganha um artefato por tabela, e o documento, as duas tabelas na mesma
seção. O `relatorio.py` não mudou.

**`associacao.na_ordem_do_dicionario` ficou pública**, com o apelido privado: os
grupos da comparação saem na mesma ordem das categorias da associação.

### 1.9.0 — o t de Welch

**O paramétrico da regra entre dois grupos passa a rodar.** `[imc, sexo]` sem método
dá o t de Welch quando o Shapiro-Wilk não rejeita a normal em nenhum dos grupos: o
`t.test(x, y)` do R, o padrão dele, pelo `scipy` — cada grupo com a sua variância, os
graus de liberdade de Welch-Satterthwaite, fracionários, e o IC 95% da diferença. As
linhas que saíam sem teste por falta dele viram linhas de Welch; as que saem sem
teste agora são as da normal rejeitada, onde a regra escolhe o Mann-Whitney.

**`t` entre grupos é o de Welch**, como o `t.test` sem argumento; `welch` também, e
`welsh` é lido como ele. O de Student continua escrito, `student`, com o aviso das
variâncias — que agora diz que o de Welch não as supõe, sem o "ainda não está".

**A barreira do R para ele**: dois valores em cada grupo, porque cada grupo entra com a
sua variância, e a de um valor só não existe — o `not enough 'x' observations`. Um
grupo que não varia não barra: o t existe, com os gl do outro grupo, e o aviso de
«perda de precisão» que o `scipy` emite nesse caso é calado, porque ali a conta está
certa.

### 1.10.0 — três grupos ou mais, e a ANOVA

**A comparação entre três grupos ou mais.** O mesmo item, `[imc, escolaridade]`: o
banco diz quantos grupos há, e com três ou mais a comparação vai para a tabela
`k_grupos.csv` — o bloco da comparação e uma linha por grupo, sem a coluna da
diferença, que com k grupos não é uma só. A recusa dos três grupos, da 1.8.0, saiu.

**A regra escolhe a ANOVA de Welch**, o padrão do `oneway.test` do R, pela razão do t
de Welch — e ela ainda não está no FlatCap: sem método escrito, a linha sai sem teste,
e o aviso ensina a escrever `anova`. **A ANOVA clássica** roda quando está escrita no
item: o `oneway.test(var.equal = TRUE)`, escrito no `hipoteses.py` — quatro linhas —
porque o `f_oneway` do `scipy` dá o F e o p do R, mas não os graus de liberdade, e eles
vão para a nota. O aviso das variâncias vale para ela como para o t de Student.

**A barreira do R é a do `oneway.test`**: dois valores em cada grupo — o `aov`
aceitaria um. E uma que o R não tem: grupos que não variam por dentro, onde ele
devolve F infinito e p zero, saem sem teste.

**O método do número errado de grupos recusa e ensina a troca**: `student` numa
variável de três grupos pede `anova`; `anova` numa de dois pede `student` — com dois
grupos, o F é o t ao quadrado. Só o banco sabe quantos grupos há, e por isso essa
recusa vem depois de abri-lo, junto das outras do mesmo tipo.

**A ANOVA diz se as médias diferem, e não quais.** O pós-teste — Tukey depois da
clássica, Games-Howell depois da de Welch — fica para depois, e a nota da tabela diz
isso.

### 1.11.0 — a ANOVA de Welch

**O paramétrico da regra entre três grupos ou mais passa a rodar.** `[imc,
escolaridade]` sem método dá a ANOVA de Welch quando o Shapiro-Wilk não rejeita a
normal em nenhum dos grupos: o `oneway.test(y ~ g)` do R, o padrão dele — cada grupo
pesado pelo inverso da variância da média, e os graus de liberdade do denominador de
Welch, fracionários. Escrita no `hipoteses.py`, como a clássica, pela mesma razão: o
`f_oneway(equal_var=False)` dá o F e o p do R, e não os gl.

**`welch` escrito é o de Welch do número de grupos que o banco trouxer**: o t com dois,
a ANOVA com três ou mais. E o `t` escrito numa variável de três grupos passa a ensinar
`welch`, que agora existe.

**A barreira que o R não tem**: um grupo que não varia. O peso dele é n/0, e o R
devolve `NaN`; aqui a linha sai sem teste, com o nome do grupo. A clássica, que usa a
variância combinada dos outros, roda sobre os mesmos dados.

### 1.12.0 — as medidas repetidas

**A mesma medida, três vezes ou mais, nos mesmos casos.** O item tem a marca
`repetidas:` — `- repetidas: [pas_0, pas_1, pas_2]` —, e o método, quando vier, numa
chave ao lado, `metodo: anova`, porque a lista das medidas não tem um terceiro lugar.
Duas numéricas soltas seriam um pareado, ou um `[idade, imc]` escrito por engano; a
marca diz que são a mesma medida. Com duas medidas a recusa diz que a pergunta é a do
t pareado, que ainda não está no FlatCap e vai usar esta mesma forma.

**A ANOVA de medidas repetidas, sempre com a correção de Greenhouse-Geisser**, pela
razão do Welch: a correção custa pouco quando a esfericidade vale, protege quando não
vale, e o Mauchly sai da frente. É o `anova.mlm` do R com `test = "Spherical"` — o F do
`aov` com `Error(caso / medida)`, e o p da coluna `G-G Pr` —, transcrito no
`hipoteses.py`, porque o `scipy` não tem; o ε e o F conferem com a conta em frações
melhor do que o próprio `anova.mlm`, que erra na décima casa. O `Resultado` ganha o
campo `epsilon`, e a frase da escolha o traz: `F = 37,04; 1,84 e 67,96 gl; ε = 0,918`.

**A regra olha cada medida**: o Shapiro-Wilk em cada uma, sobre os casos completos; a
normal rejeitada em alguma leva ao Friedman, que ainda não está no FlatCap.

**Os faltantes são por item, e inteiros**: entra quem tem todas as medidas. A média de
cada medida na tabela é a desses casos — e difere da do `resumo` da descritiva quando
alguma medida tem faltante, o que a nota diz.

**A tabela `repetidas.csv`**: uma linha por medida, com o teste e o p na primeira. E
uma barreira que o R não tem: medidas que não variam dentro dos casos — cada caso
mudando o mesmo tanto —, em que o R devolve um F de 10²⁹ feito de arredondamento.

### 1.13.0 — o lote

**`flatcap analisar <id>`: as análises da lista `analises:` da ficha, de uma vez.**
A lista existia desde a Fase 2 e ordenava as seções do relatório desde a 1.3.1; agora
ela também diz o que roda. O comando obedece e não escolhe: lista vazia recusa, e a
recusa escreve a linha pronta para copiar a partir dos blocos que a ficha já tem;
nome que o FlatCap não conhece recusa com a grafia certa — `associação` pede
`associacao`, `anova` ensina que o teste roda dentro da `comparacao`; nome repetido
recusa, porque a posição na lista é a posição da seção no documento. Os seis comandos
de cada análise continuam iguais.

**`analises.py` é a soma dos comandos, e nada além.** Cada análise é preparada e
escrita pelas funções dela, com os argumentos que o comando dela passaria e o mesmo
relógio para todas — e a rodada sai, byte a byte, a que o comando dela escreveria. É
o critério de pronto, e o primeiro teste do `test_analises.py`. As três regras vêm do
plano da Fase 7: **prepara todas antes de escrever qualquer uma** (se uma recusar,
nada é arquivado, e as recusas saem todas juntas; o que vale para todas — a ficha, o
banco, o dicionário — para na primeira); **um registro nome → módulo, com import
preguiçoso** (importar o `analises.py` não traz o `pandas`); e **o relatório fica de
fora**, porque entre as análises e o documento há uma leitura sua. Nenhum dos seis
módulos de análise mudou uma linha.

**Uma falha no meio para o lote.** A análise que falhou se desfaz sozinha, como no
comando dela; as anteriores ficam; as seguintes não rodam. A frase de onde ele parou
vai para o `historico.md` e presa ao erro, e um Ctrl+C sai com 130 e a mesma frase —
dizendo que a pasta da análise interrompida pode ter ficado pela metade, porque o
desfazer de cada `executar_*` pega `Exception`, e o Ctrl+C não é uma.

**Na CLI, a saída de cada análise é a do comando dela.** O que cada comando mostrava
antes de escrever virou uma `_mostrar_*`, e o que dizia depois, a `_rodada_escrita`:
o `analisar` chama as mesmas funções, uma análise depois da outra, e fecha com uma
tabela do lote. `--resumo` mostra só a tabela. O `_NA_TELA` é o registro da tela, e
há teste que o exige igual ao `analises.REGISTRO`.

### 1.13.1 — a revisão antes da abertura do código

Uma revisão de todos os arquivos antes de o repositório virar público, e nenhuma
funcionalidade nova. Cada correção tem o seu teste de regressão.

**O perfil escreve as categorias como as análises.** Uma coluna de código com uma
célula vazia chega como `float64`, e o perfil escrevia `1.0|2.0` no `dicionario.csv` e
`1.0=Feminino` na dica; a descritiva escreve `1`, e a tabela saía com `Feminino 0` ao
lado de `1 20`. A `serie_de_texto` desceu para o `banco.py`, ao lado dos
`FORMATOS_DATA` e pelo mesmo motivo deles. O dicionário já escrito com `1.0=` não é
reescrito — a fusão nunca toca linha existente —, e o conserto é à mão.

**O `#` só é comentário no começo do arquivo.** No dicionário, a variável `#id` sumia a
cada leitura; na tabela de uma análise, a categoria `#N/D` saía do `.docx` e o `Total`
deixava de fechar. E as mensagens do dicionário passam a dar a linha do arquivo.

**O que o disco e o terminal mostram.** O cifrão do banco não vira fórmula nos
gráficos; o arquivo gravado segue o `umask`, e não `0o600`; todo erro HTTP do REDCap
vira `RedcapError`; a falha inesperada no relatório devolve o anterior ao lugar; e a
codificação do `.csv` é confirmada no arquivo inteiro, e não só nos primeiros 64 KiB.

**A distribuição por pacote.** O `.env` da sua conta é o terceiro degrau da procura,
para quem instala o FlatCap com o `pipx` ou o `uv` e roda o comando de qualquer pasta;
`flatcap doctor --criar-env` o escreve. A versão passou a morar só aqui — o
`pyproject.toml` a lê com `dynamic = ["version"]`.

**A abertura.** `LICENSE` com a GPL-3.0, `NOTICE.md` com os trechos derivados do R, o
cabeçalho SPDX em todo arquivo de código, e o `flatcap --version` dizendo a licença.

### 1.14.0 — os testes de postos

**Onde a normal não se sustenta, a comparação passa a ter teste.** O Wilcoxon contra uma
referência, o Mann-Whitney entre dois grupos, o Kruskal-Wallis entre três ou mais e o
Friedman nas medidas repetidas — os quatro que a regra já nomeava desde a 1.7.0, e que
deixavam a linha sem teste. A regra não mudou: o Shapiro-Wilk em cada vetor do
delineamento, o paramétrico quando ele não rejeita, o de postos quando rejeita ou não pode
ser verificado, e o método escrito no item por cima dos dois — `wilcoxon`, `mannwhitney`,
`kruskal`, `metodo: friedman`.

**Os quatro são os do R, com a escolha do R escrita.** O `wilcox.test` decide o p exato com
menos de 50 valores, sem empate e sem zero, e a aproximação normal com as correções de
empate e de continuidade nos outros casos; o `scipy` decide por outro critério, e por isso
a aritmética do Wilcoxon e do Mann-Whitney está no `hipoteses.py` — as distribuições exatas
contadas em inteiros, servindo ao p e ao intervalo. O Kruskal-Wallis é o `kruskal` do
`scipy`, igual ao do R; o Friedman é escrito, como a ANOVA, porque o `scipy` recusa duas
medidas, que o R aceita.

**O Wilcoxon e o Mann-Whitney saem com a estimativa de Hodges-Lehmann e o intervalo de 95%
dela** — o `conf.int = TRUE` do R: a pseudomediana na uma amostra, a diferença de locação
entre dois grupos, que não é a diferença das medianas. No caminho aproximado, o R acha os
limites com o `uniroot`, e ele está transcrito — o `R_zeroin2` —, para os limites saírem
os do R, e não outros a menos de 1e-4 deles. Com poucos valores, o intervalo de 95% pode
não existir na distribuição exata, e o menor p possível pode passar de 0,05: os dois saem
com aviso, e o intervalo que não chega a 95% fica fora da tabela.

**O resumo, linha a linha.** `média (DP)` nas linhas do t e da ANOVA, `mediana [Q1 a Q3]`
nas dos testes de postos, como o `compareGroups` — o cabeçalho diz o que a coluna tem, e
uma tabela só de paramétricos sai como antes. O mesmo no intervalo da uma amostra (`IC 95%
da média`, `da pseudomediana`, ou `IC 95%` quando a tabela tem os dois) e na diferença
entre dois grupos: `diferença de locação (IC 95%)` no Mann-Whitney, porque o documento não
leva as notas do `.csv`, e a de locação, ao lado da mediana de cada grupo, seria lida como
a diferença das duas. O manifesto guarda as duas formas do resumo de cada linha, de cada
grupo e de cada medida.

**Cada teste com a sua barreira.** O Friedman roda onde a ANOVA de medidas repetidas não
pode — cada caso mudando o mesmo tanto entre as medidas —, e o aviso da ANOVA ensina a
escrevê-lo; e recusa o caso em que cada caso tem o mesmo valor em todas as medidas, onde o
R devolve `NaN`.

**Os nomes.** `wilcoxon` é o `wilcox.test` do R: o do posto sinalizado contra uma
referência, e o Mann-Whitney entre dois grupos. O `signed rank` escrito por extenso recusa,
em vez de levar ao Mann-Whitney quem pediu o posto sinalizado; as outras grafias dos livros
— `U de Mann-Whitney`, `Wilcoxon rank sum`, `Kruskal-Wallis` — valem.

O `relatorio.py` não mudou uma linha.

### 1.14.1 — o que chega do Excel

As quatro correções de gravidade alta da varredura do repositório público, cada uma
com o seu teste de regressão. Nenhuma funcionalidade nova; as quatro são entradas comuns
que o FlatCap lia errado.

**A vírgula decimal do `.csv` do Excel em português é lida como número.** É o formato
mais comum de chegar — `;` entre campos, `70,5` na célula —, e a coluna chegava como
texto: o perfil mandava o cliente "corrigir" um arquivo certo, e toda análise recusava a
coluna. A decisão "a leitura é fiel ao que o cliente mandou" continua valendo para todo o
resto; aqui ela cede pela razão que já fazia a data escrita como texto ser convertida —
exigir do cliente o conserto de um formato que o Excel dele sempre escreve é exigir o
impossível. A conversão é da coluna inteira ou de nada, só vale onde a vírgula não separa
campos, e fica escrita no perfil e no manifesto. As condições estão no `banco.py`.

**Número de escala pequena não sai mais zero.** As estatísticas tinham duas casas fixas, e
uma concentração na casa de 0,003 saía `0` no resumo inteiro, com faixas `[0 a 0)`, e a
comparação imprimia "média 0 (0)" nos dois grupos ao lado de uma diferença "0,00 (0,00 a
0,00)" e de um p < 0,001. O `banco.casas_do_resumo` decide as casas de cada variável pela
escala dela; de 0,01 para cima nada muda.

**O nome de coluna sai numa linha e sem espaço nas pontas.** `Idade ` travava o projeto: o
perfil gravava o nome com o espaço, a leitura do dicionário o aparava, a descritiva não
achava a coluna e mandava rodar o perfil, que a acrescentava de novo — e na volta a
variável aparecia duas vezes. `Peso` e `(kg)` em duas linhas partiam o comentário das
tabelas, e o relatório saía com tabelas de uma coluna só, sem aviso. O leitor limpa os
dois, e o comentário das tabelas sai sempre numa linha só, mesmo quando o rótulo ou uma
categoria trazem a quebra.

### 1.15.0 — a amostragem

**`flatcap amostragem <id>`: o tamanho da amostra, na pasta dela, com o relatório dela.** O
projeto costuma começar com a amostragem e evoluir depois para a análise, e o fluxo começa
sempre no `flatcap novo`, que não muda — as três pastas de sempre. A amostragem vem depois
dele. A primeira rodada cria `4. Amostragem/` e escreve o `desenho.yaml`, o plano da amostra,
para preencher à mão, e para; as seguintes leem o `desenho.yaml`, fazem a conta e escrevem o
`tamanho.csv`, o `manifesto.json` e o relatório da amostra,
`Amostragem_<matrícula>_AAAA-MM-DD.docx`. Tudo da amostra mora em `4. Amostragem/`, inclusive
as versões antigas dela, e as pastas 1, 2 e 3 ficam para a análise que vem depois.

**A pasta nasce na amostragem, e não no `novo`.** O `novo` não tem como saber se o pedido é de
amostragem — o formulário do REDCap não tem essa opção —, o projeto que nunca amostra não
ganha uma pasta vazia, e o que já existia ganha a pasta do mesmo jeito, sem migração. A
amostragem não cria projeto: sem a pasta do `novo`, recusa e diz isso.

**A amostragem não é uma análise.** Não está no `analises.REGISTRO`, na
`ORDEM_PADRAO_DAS_ANALISES` nem no `flatcap analisar`. O relatório das análises varre só
`3. Análises/` e nunca vê a amostra, e o relatório da amostra nunca vê as análises. O
`ANALISE_AMOSTRAGEM` do `manifesto.py` existe para o manifesto dela dizer de que ele é.

**Um desenho, e o espaço para os outros.** A aleatória simples, sem reposição: a do pedido
mais comum, o do cliente que informa só o tamanho da população. O modelo do `desenho.yaml` já
vem com 95% de confiança, margem de 5 pontos e proporção esperada de 50%, e preencher a
`populacao` basta. A média entra com o `desvio` no lugar da `proporcao`; o tamanho decidido à
mão, no `n`; a perda esperada, na `perda`. Cada desenho é uma entrada no
`amostragem.DESENHOS`, com as chaves e a conta dele, e os previstos — sistemática,
estratificada, conglomerados, PPT, dois estágios — recusam dizendo que ainda não estão no
FlatCap, e não que não existem.

**A conta é a do OpenEpi.** n₀ = z²·V/e², corrigido pela população na forma
n = N·z²·V/[(N − 1)·e² + z²·V], arredondado para cima em cada passo, com a perda somada no fim
e o tamanho nunca maior que N. O z é o `qnorm` do R, pelo `statistics.NormalDist`. A
aritmética mora no `amostral.py`, só com a biblioteca padrão, e o teste a confere contra os
tamanhos publicados e contra o `qnorm`.

**As recusas são as do engano que muda o número em silêncio.** `12.000` é doze no YAML, e não
doze mil; `confianca: 0.95` é a confiança escrita como fração, e `confianca: 5`, o α no lugar
dela; `proporcao: 0.5` querendo 50% é meio por cento, e daria n = 8 sem erro nenhum. Saem
todas de uma vez, como nas análises. A margem escrita como fração, `margem: 0.05`, passa por
todas — 0,05 ponto existe —, e por isso sai com aviso, e não recusada. A vírgula decimal vale,
e `AAS` ou `Aleatória simples` são lidos como `aas`.

**O relatório da amostra é montado com as peças do das análises**, e três delas ficaram
públicas no `relatorio.py`: o `tabela_do_texto` — o miolo do `ler_tabela`, para a tabela do
documento ser lida do mesmo texto que vai para o `tamanho.csv` —, o `localizar_template` e o
`conferir_texto`, com os nomes privados como apelido. A primeira página é a mesma, com a
finalidade e os objetivos da ficha. O texto de metodologia tem o lugar dele, o
`amostragem.METODOLOGIA`, vazio de propósito, pela regra do `TEXTO_PADRAO`.

**O `desenho.yaml` é seu.** O FlatCap escreve o modelo uma vez e, dali em diante, só lê — e
quem lê é o `ficha.ler_yaml`, para um YAML quebrado ganhar o diagnóstico da ficha. Refazer a
rodada arquiva a anterior em `4. Amostragem/Versões antigas/`, com o `desenho.yaml` de então:
o texto que ela leu, guardado no manifesto dela, e não o da pasta, que a essa altura já é o
novo. O tamanho que muda em relação à rodada vigente sai com aviso, antes de escrever.

**O número escrito à mão desceu para o `ficha.py`.** A regra do `numero_escrito` era a do
`comparacao.referencia_escrita`, e a amostragem lê o `desenho.yaml` por ela.

**As propriedades do `.docx` dizem de qual rodada ele é.** O comentário dizia "a partir da
descritiva" em todo documento e, sem banco, "banco ?"; passa a dizer a análise do manifesto,
e "sem banco" quando não há.
### 1.16.0 — a metodologia na primeira página

**O relatório ganha um texto padrão de metodologia, para o cliente levar para o artigo.** Ele
fecha a primeira página, depois da finalidade e dos objetivos que vieram do REDCap, e antes da
quebra que abre a primeira seção: o subtítulo "Metodologia Estatística (texto padrão)" e um
parágrafo que diz, no registro de uma seção de métodos, como os números do documento foram
produzidos — como cada tipo de variável foi descrito, quais testes rodaram, o nível de
significância — e termina com "As análises foram feitas usando a linguagem Python versão
3.11.", com a versão das rodadas.

**O parágrafo sai das rodadas, e não de um texto fixo.** Um texto fixo citaria todos os testes
que o FlatCap sabe fazer, e um artigo que nomeia nos métodos um teste que não aparece em
resultado nenhum é a primeira coisa que o parecerista marca. Cada análise com rodada em
`3. Análises/` contribui com uma frase, e a frase nomeia só os testes que rodaram — o
Mann-Whitney entra quando alguma linha da comparação saiu com ele, o Fisher quando algum par da
associação foi para ele. A explicação da regra entra só quando ela escolheu: com mais de um
método na correlação, ou com o paramétrico e o de postos na comparação; e o teste escrito na
ficha não é atribuído à regra.

**Nada aqui abre o banco.** Tudo o que o parágrafo afirma está nos manifestos: o teste de cada
par, item e delineamento nos `detalhes`, o alfa e a falta de correção para comparações
múltiplas nas `regras`, e a versão do Python no `ambiente`, sem o último número. Rodar uma
análise de novo reescreve o manifesto dela, e o parágrafo acompanha sem ninguém lembrar de
editá-lo. Duas versões no parágrafo ("versões 3.11 e 3.13") são de propósito: dizem que uma
rodada foi feita noutra máquina.

**Um módulo novo, `metodologia.py`, e o subtítulo no `documento.py`.** A redação mora num bloco
emoldurado no topo do módulo, como o `TEXTO_PADRAO`: o subtítulo, a frase de cada análise, o
nome de cada teste, a frase do Python. O `Relatorio` leva a metodologia em dois campos dela,
`metodologia` e `titulo_da_metodologia`, e não no `texto`, porque o subtítulo é um título: o
`documento.py` o escreve no estilo de subtítulo — o `FlatCap Subtitulo` da linha
`matrícula - nome`, que se ajusta no Word —, preso ao parágrafo que vem depois, e o parágrafo
como o texto corrido da abertura. O módulo não importa as análises — elas trazem o `pandas`, e
o `relatorio.py`, que o importa, tem o teste em subprocesso que falha se o `pandas` for
carregado —, e por isso os nomes que os manifestos gravam estão escritos nele como texto; o
`test_metodologia.py` confere que são, letra por letra, as constantes das análises.

**Rodada sem frase é aviso, e não texto inventado.** Uma análise cujo manifesto não diz o que
rodou — uma que esta versão não conheça — sai do parágrafo, e o terminal diz qual. A que não
testou nada (toda linha "não testado") sai sem frase e sem aviso: a tabela dela já diz o
motivo.

### 1.17.0 — o painel de status

**`flatcap status`: os projetos que já têm pasta, com o status e o prazo de cada um.** Uma
tabela como a do `listar` — id, matrícula, nome, pasta local, status e prazo —, uma linha por
`Projeto NNN`, na ordem do `record_id`. O `listar` parte do REDCap e procura a pasta de cada
solicitação; o `status` faz o caminho inverso, ficha por ficha, e não fala com o REDCap: fica
de pé quando o servidor cai, e mostra a pasta cuja matrícula foi corrigida no REDCap depois de
ela existir.

**O status tem cinco valores**: `não iniciado`, `aguardando banco de dados`, `em andamento`,
`pronto` e `finalizado`, no `projeto.STATUS`. O `flatcap novo` escreve o primeiro, o
`flatcap relatorio` escreve o `pronto` quando escreve o documento, e os outros três são
escritos à mão. O `finalizado` tira o projeto do painel. A leitura é tolerante e a escrita é
estrita (`ficha.status_reconhecido`): `Em Andamento` e `nao iniciado` são os de sempre, e os
dois do cabeçalho de antes — `novo` e `em_analise` — também, porque toda ficha criada até a
1.16 diz `novo`. O terceiro de antes, `entregue`, pode ser o `pronto` ou o `finalizado`, e não
é adivinhado: sai como está escrito, em magenta, com o aviso do que escrever no lugar. Cada um
dos quatro que aparecem tem a sua cor (`cli.CORES_DO_STATUS`): branco, amarelo, azul e verde,
do `não iniciado` ao `pronto`; o magenta do que não é nenhum deles não se confunde com o
amarelo do `aguardando banco de dados`.

**O prazo é a data final**, escrita à mão depois da reunião, como `2026-11-04` ou
`04/11/2026` (`ficha.data_escrita`). O painel mostra a data, e ATRASADO, em vermelho, quando
ela passou sem o projeto estar `pronto` — o prazo é o do relatório, e o projeto pronto já o
tem. O dia do prazo ainda não é atraso. A palavra vai escrita, e não só a cor, para o painel
dizer o mesmo sem cor nenhuma. O prazo que não é data aparece como está escrito, em amarelo;
o `Ficha.prazo` entra como texto para um prazo digitado errado não impedir a ficha de abrir.

**O relatório é a única escrita nova na ficha** (`ficha.definir_status`), e a exceção que o
cabeçalho de toda ficha nova passa a dizer: o resto continua intocado, e o comentário escrito
ao lado do `status:` também. O documento vem primeiro; o status que não se escreve vira aviso
e não desfaz o relatório, e uma falha depois dele devolve a ficha ao texto que tinha. A
simulação diz que o status vai mudar, e o histórico diz que mudou.

**Um módulo novo, `painel.py`**, que monta dados e não texto: uma `LinhaDoPainel` por projeto,
com o prazo como data e o atraso como um sim ou não. A CLI os desenha; uma interface gráfica
pode ordenar, filtrar e abrir a pasta sem ler a tabela do terminal. O painel parte do
`ficha.varrer`, a mesma varredura de dois níveis do `localizar_projeto`, e lista a ficha que
não abre e a pasta no formato de antes da 1.1.0, em vez de deixá-las sumir.

### 1.18.0 — o status do cálculo amostral

**Um sexto status, `cálculo amostral`, entre o `não iniciado` e o
`aguardando banco de dados`.** É o projeto cujo tamanho da amostra está sendo calculado: o
pedido que chega com a finalidade "Cálculo amostral", ou o projeto que começa pela amostra e
só depois recebe o banco. A ordem do `projeto.STATUS` é a do atendimento, e o cálculo vem
antes da coleta. É escrito à mão, como o `aguardando banco de dados` e o `em andamento`, e
atrasa como eles: o prazo que passou sem o projeto estar `pronto` sai ATRASADO.

**A cor é o ciano, `#00d7d7`**: 11,7:1 de contraste com o fundo preto, e a cor 44 das 256 do
xterm, como o azul do `em andamento`. Num terminal de 16 cores, vira o ciano do tema, que
nenhuma outra cor do painel usa, e numa simulação de daltonismo continua distinta das outras
quatro. Das outras duas oferecidas, o laranja ficava perto do verde do `pronto` no
daltonismo vermelho-verde mais comum, e o rosa salmão, em 16 cores, virava o vizinho do
magenta do status fora da lista.

**As fichas de antes continuam valendo**: o cabeçalho delas lista cinco status, e o sexto é
lido nelas do mesmo jeito — `calculo amostral`, sem acento, também. E o próximo status que
entrar na lista sem cor quebra um teste, em vez de sair sem cor no painel.

## `flatcap/config.py`

`SPDX-FileCopyrightText: 2026 Matheus Fernandes` · `SPDX-License-Identifier: GPL-3.0-or-later`

*285 linhas.*

Leitura e validação da configuração do FlatCap.

Este é o único lugar do sistema que lê variáveis de ambiente. Todo o resto recebe
um objeto `Config` pronto. Consequência prática: nenhum caminho fixo e nenhum
`os.environ` espalhado pelo código.
Regra de precedência: variáveis já definidas no ambiente do sistema prevalecem
sobre o `.env` (`override=False`). Isso permite rodar em outra máquina, em um
servidor ou em um teste sem editar arquivo nenhum.

### Qual `.env`

Nesta ordem, e o primeiro que existir é o lido:

1. o arquivo do `--env`, quando o comando o recebe;
2. um `.env` na pasta atual ou em alguma acima dela — é o de quem trabalha num
   clone do repositório, na raiz dele;
3. o `.env` da sua conta, na pasta de configuração do sistema
   (`pasta_de_configuracao`) — é o de quem instalou o FlatCap por um pacote, com
   o `pipx` ou o `uv`, e roda o comando de qualquer pasta.

O terceiro degrau entrou na 1.13.1, junto com a distribuição por pacote: sem ele,
o FlatCap instalado só achava a configuração quando o comando rodava de dentro da
pasta certa. `flatcap doctor --criar-env` escreve esse arquivo com as três chaves
em branco.

### `CHAVES`

*linha 38*

> Chave: explicação mostrada quando ela falta.
> As mensagens são o produto principal deste módulo: um erro de configuração precisa
> dizer o que fazer.

### `TEXTO_DO_ENV`

*linha 62*

> O modelo do `.env`, com as três chaves em branco. É o que o `doctor --criar-env`
> escreve, e o `.env.example` da raiz do repositório tem de ser igual a ele — o
> `test_config.py` confere. Em branco, e não com valores de exemplo: com o exemplo
> copiado sem preencher, a falta não era acusada e o `doctor` ia tentar falar com
> `https://<seu-servidor>`.

### `class ConfigError(RuntimeError)`

*linha 84*

Configuração ausente ou inválida!

Erro próprio (e não ValueError genérico) para que a CLI possa capturá-lo e
transformar em mensagem amigável, sem engolir bugs de verdade.

### `class Config`

*linha 93*

Configuração válida. Imutável de propósito: ninguém altera em trânsito.

- *linha 100* — `origem_env: str | None = None` — caminho do .env efetivamente carregado

#### `def token_mascarado(self)`

*linha 103*

Versão segura para imprimir no terminal e em logs.

### `def carregar(env_file, criar_root)`

*linha 111*

Lê o `.env`, valida as três chaves e devolve um `Config`.

Args:

    env_file: caminho explícito de um `.env`. Se omitido, procura a partir do
        diretório atual e sobe na árvore; não achando, usa o `.env` da sua
        conta, se ele existir. Ver o docstring do módulo.
    criar_root: se True, cria `FLATCAP_ROOT` caso não exista. O padrão é False
        de propósito — um caminho digitado errado deve dar erro, não virar uma
        pasta vazia silenciosa em lugar nenhum.

Raises:

    ConfigError: com a lista do que falta e por quê cada item importa.

### O `.env` da sua conta

### `def pasta_de_configuracao()`

*linha 149*

A pasta de configuração da sua conta, onde mora o `.env` de quem instalou o
FlatCap por um pacote:

    Windows   C:\Users\<você>\AppData\Roaming\flatcap
    macOS     ~/Library/Application Support/flatcap
    Linux     ~/.config/flatcap   (ou $XDG_CONFIG_HOME/flatcap)

Quem calcula é o `typer.get_app_dir`, a regra de cada sistema escrita uma vez —
nenhuma dependência nova.

### `def arquivo_env_da_conta()`

*linha 166*

O `.env` da sua conta: o terceiro degrau da procura, e o que o
`doctor --criar-env` escreve.

### `def criar_env_da_conta()`

*linha 174*

Escreve o `.env` da sua conta com as três chaves em branco. Devolve o caminho,
ou `None` quando ele já existe — o arquivo é seu, e nunca é sobrescrito.

No Linux e no macOS o arquivo nasce `0o600`, legível só por você: ele guarda o
token do REDCap, e um token é uma senha.

### Validações individuais

### `def _localizar_env(env_file)`

*linha 194*

Decide qual `.env` carregar. Devolve uma string vazia quando não tem nenhum.

Um `--env` apontado para um arquivo que não existe é barrado.

### `def _validar_api_url(valor)`

*linha 215*

Normaliza a URL da API e barra os dois enganos mais comuns.

*linha 228*

> A barra final serve para o servidor não responder "301".

### `def _validar_root(valor, criar)`

*linha 231*

Expande `~`, resolve o caminho e confirma que dá para escrevê-lo.

### Mensagens

### `def _mensagem_faltando(faltando, caminho_env)`

*linha 265*

Monta o texto do erro de chaves ausentes, com o próximo passo explícito.

## `flatcap/redcap.py`

`SPDX-FileCopyrightText: 2026 Matheus Fernandes` · `SPDX-License-Identifier: GPL-3.0-or-later`

*366 linhas.*

Camada fina sobre a API do REDCap.
A API tem três particularidades que este módulo isola, para que nenhuma delas vaze para o resto do
sistema:

    1. tudo é POST com `application/x-www-form-urlencoded` no mesmo endpoint; o que muda é o campo
       `content` do corpo;
    2. erros vêm como HTTP 400 com um JSON {"error": "..."} — não como exceção de rede. Sem
       tratamento, viram um KeyError incompreensível três camadas acima.
    3. `content = file` devolve bytes, não JSON. Por isso a aquisição foi separada em duas camadas:
        a) `_requisitar` faz a rede e devolve a resposta crua;
        b) `_post` é a leitura JSON em cima dela.

### `_SEM_ARQUIVO`

*linha 29*

> Mensagens com que o REDCap sinaliza "este registro não tem arquivo neste campo".
> É ausência esperada, não falha: um cliente pode simplesmente não ter anexado o banco.
> Comparação em minúsculas e por trecho, porque o texto exato varia entre versões e idiomas do
> servidor.

### `class RedcapError(RuntimeError)`

*linha 43*

Falha na conversa com a API do REDCap, já traduzida.

### `class ArquivoAusenteError(RedcapError)`

*linha 48*

O campo de arquivo existe, mas o registro não tem nada anexado.
Subclasse do `RedcapError`.

### `class ArquivoRedcap`

*linha 55*

O anexo baixado, ainda em memória.
`nome` é o nome original do arquivo do jeito que o cliente o nomeou.

### Camada de rede

### `def _requisitar(cfg, payload)`

*linha 66*

Faz a requisição da chamada autenticada e devolve só a resposta.
Traduz as falhas de rede que não dependem do corpo.

*linha 90*

> Precisa vir **depois** do SSLError e do Timeout: no `requests`, o
> `SSLError` e o `ConnectTimeout` são subclasses desta. Sem esta cláusula,
> máquina sem rede, VPN caída ou proxy recusando derrubavam o `doctor` com o
> traceback inteiro do `urllib3` — que é exatamente o oposto do que o
> `doctor` existe para fazer.

*linha 102*

> O resto da família do `requests`: a conexão que cai no meio do download
> de um anexo grande (`ChunkedEncodingError`), o servidor que redireciona
> em círculo, a URL que o `requests` não aceita. Por último, porque é a
> mãe de todas as de cima.

### `def _erro_no_corpo(resposta)`

*linha 119*

Devolve a mensagem de erro do REDCap, se o corpo for um erro de aplicação.

### `def _conferir_status(resposta, contexto)`

*linha 134*

Recusa a resposta HTTP de erro que não trouxe o `{"error": ...}` do REDCap.

Até a 1.13.0 quem fazia isto era o `raise_for_status()` do `requests`, e a
exceção dele, `requests.HTTPError`, não é `RedcapError`: um 500 do servidor,
ou o 502 de um proxy institucional em manutenção, derrubava o `novo` e o
`listar --conferir-anexos` com o traceback inteiro — que é o que esta camada
existe para impedir. O erro de aplicação, com o JSON, já foi traduzido antes
de chegar aqui, pelo `_erro_no_corpo`.

### `def _post(cfg, payload)`

*linha 164*

Chamada autenticada com resposta JSON, já decodificada.

### `def _lista_de_dicionarios(corpo, rotulo)`

*linha 201*

Confere se a resposta do corpo é uma lista.

### `def _lista(valores)`

*linha 212*

Converte ['a', 'b'] na string 'a,b', que é como o REDCap recebe listas.

### Chamadas Gerais

### `def exportar_projeto(cfg)`

*linha 221*

Devolve os metadados do projeto (`content = project`).
É a chamada mais barata da API e não depende de nenhum registro existir, por isso serve como
teste de conexão no `flatcap doctor`.

### `def exportar_registros(cfg, fields, records)`

*linha 234*

Devolve as respostas do questionário (`content = record`).
  Args:

    fields: campos a trazer. Pedir só o necessário reduz a resposta e evita trafegar campos que
    o FlatCap não usa.
    records: limita a registros específicos.

Os valores vêm crus (`rawOrLabel = raw`), então `intro` chega como "1"/"2" e não como
"Professor/Colaborador".

### `def exportar_metadados(cfg, fields)`

*linha 265*

Devolve o dicionário de variáveis do projeto (`content = metadata`).

### `def exportar_arquivo(cfg, record_id, campo)`

*linha 275*

Baixa o anexo de um campo de arquivo (`content = file`, `action = export`).
Raises:
  ArquivoAusenteError: o registro existe, mas não tem arquivo neste campo.
  RedcapError: qualquer outra falha — token sem permissão de exportar arquivos, registro
  inexistente, campo que não é do tipo file.

### `def tem_arquivo(cfg, record_id, campo)`

*linha 312*

Responde se existe anexo, sem que quem pergunta precise tratar exceção.
Custa um download completo: a API do REDCap não oferece uma consulta que responda "existe?"
sem trazer o conteúdo. Por isso é usada apenas sob demanda, pela opção `--conferir-anexos` do
`flatcap listar`, e não no caminho normal.

### Auxiliares

*linha 329*

> Content-Disposition: attachment; filename="banco.xlsx"

*linha 333*

> Content-Type: application/vnd...; name="banco.xlsx"  (é onde o REDCap põe)

### `def _nome_do_anexo(resposta)`

*linha 338*

Extrai o nome original do arquivo dos cabeçalhos da resposta.

### `def _limpar_nome_de_arquivo(bruto)`

*linha 357*

Reduz o nome anunciado pelo servidor ao nome de arquivo puro.
Descarta qualquer componente de caminho (`../`, `C:\`, `/etc/`) antes que ele chegue perto de
um `open()`. O nome vem de fora, e o que vem de fora não monta caminho.

## `flatcap/modelo.py`

`SPDX-FileCopyrightText: 2026 Matheus Fernandes` · `SPDX-License-Identifier: GPL-3.0-or-later`

*316 linhas.*

Esse módulo serve para transformar professores/colaboradores e alunos em apenas `Cliente`.
Sua principal utilidade é que caso a variável `intro` receba outras categorias, só vai ser
necessário acrescentar aqui e todo o resto vai funcionar.
Todo o resto do sistema só trata `Cliente`.

Além da identificação, o `Cliente` carrega dois campos que o cliente escreve no
formulário e que saem impressos na primeira página do relatório: a **finalidade**
(`fin`) e os **objetivos** (`obj1`). Eles entram aqui, e não direto no
`relatorio.py`, por uma razão de arquitetura: o relatório não fala com o REDCap.
O caminho é sempre o mesmo — o `flatcap novo` traz do formulário, o
`projeto.yaml` guarda, e o relatório lê a ficha.

Uma armadilha do formulário atual, que vale ler antes de mexer aqui: `fin` é um
campo `radio`, então o que chega da API é um **código** (`"1"`, `"2"`…), nunca o
texto. O rótulo vem do `content=metadata` e é resolvido em `mapa_de_rotulos`.
E a opção "Outros" tem a resposta de verdade em outro campo, o `outros1` —
por isso são três campos do REDCap para um campo da ficha.

- *linha 34* — `CAMPO_ANEXO = 'database'` — campo de anexo do questionário

- *linha 35* — `CAMPO_FINALIDADE = 'fin'` — radio: para que o cliente quer a análise

- *linha 36* — `CAMPO_FINALIDADE_OUTROS = 'outros1'` — text: o que ele escreveu ao marcar "Outros"

- *linha 37* — `CAMPO_OBJETIVOS = 'obj1'` — notes: objetivo geral e específicos

### `_PARES`

*linha 44*

> Os pares tentados quando `intro` não responde, na ordem.

### `_SEPARADOR_OPCOES`

*linha 63*

> Como o REDCap escreve as opções de um `radio` ou `checkbox` no `content=metadata`:
>     "1, Artigo científico | 2, Projeto de iniciação científica | 4, Outros: {outros1}"
> O separador de opções é `|`, e o código vai até a **primeira** vírgula — o
> rótulo pode ter vírgulas dentro e frequentemente tem.

### `_PIPING`

*linha 69*

> `{outros1}` é *piping*: o REDCap mostra ali o que foi digitado no outro campo.
> No texto do relatório ele não serve para nada, então sai — junto com os dois
> pontos que sobrariam pendurados em "Outros: ".

### `class Cliente`

*linha 79*

Imutável de propósito igual no `Config`

`finalidade` e `objetivos` têm default vazio porque nem todo caminho até aqui
tem como preenchê-los: o `flatcap listar` normaliza centenas de registros sem
pedir os metadados do projeto, e não precisa deles para montar a tabela.
Campo vazio não é erro — é o que o relatório denuncia com o alerta
`texto_ausente`, em vez de imprimir um código ou um marcador de banco de dados.

#### `def identificado(self)`

*linha 98*

Testa se da pra criar a pasta automaticamente.

### `def normalizar(registro, rotulos)`

*linha 104*

Converte um registro cru do REDCap para `Cliente`

Mostra que o registro está incompleto direto e não apenas quebra...

Args:

    rotulos: o mapa `campo → {código: rótulo}` do `mapa_de_rotulos`. Sem ele,
        `finalidade` sai vazia em vez de sair com o código cru: `"2"` na
        primeira página de um relatório é pior do que um campo em branco, que
        pelo menos dispara o alerta.

### `def normalizar_varios(registros, rotulos)`

*linha 138*

Aplica a função `normalizar` à resposta toda mantendo a ordem do REDCap.

### `def mapa_de_rotulos(metadados, campos)`

*linha 147*

Traduz o `content=metadata` do REDCap em `campo → {código: rótulo}`.

Função pura: recebe a resposta já baixada e não fala com a rede. Quem baixa é
o `projeto.py`, que é a camada que compõe — este módulo continua sendo só
"questionário → Cliente".

Ler o rótulo do servidor, e não de um dicionário escrito no código, é o que
evita o defeito silencioso: no dia em que alguém acrescentar uma quinta opção
ao `fin` no REDCap, um mapa fixo devolveria vazio sem avisar ninguém.

Args:

    campos: quais campos interessam. Sem isso, todos os que tiverem opções.

### `def mais_recentes(clientes, quantos)`

*linha 178*

Os `quantos` registros mais recentes, **na ordem em que o REDCap os devolveu**.

Duas coisas de uma vez, e a segunda é a que surpreende: a função escolhe
pelo `record_id` (maior é mais novo, porque o REDCap numera em sequência) e
devolve na ordem original, não na ordem do sorteio. É o que faz o
`flatcap listar --ultimos 10` mostrar dez linhas na mesma ordem em que as
outras aparecem quando o limite não é usado — uma tabela que muda de ordem
quando encolhe é uma tabela que ninguém reencontra.

`quantos <= 0` ou maior do que a lista devolve a lista inteira: pedir mais do
que existe não é erro, é não ter filtro nenhum.

`record_id` que não é número vai para o fim (ver `_chave_recencia`) e o
desempate é a posição original, para que duas chamadas iguais produzam
exatamente a mesma lista.

### Funções auxiliares

### `def _chave_recencia(indice, cliente)`

*linha 210*

Ordena o `record_id`.

### `def _texto(registro, chave)`

*linha 219*

Lê um campo como texto limpo, tolerando ausência, None e espaços de sobra.

### `def _texto_longo(registro, chave)`

*linha 230*

Lê um campo `notes` preservando os parágrafos que o cliente escreveu.

Três limpezas, e cada uma tem um motivo concreto:

* **CRLF vira LF.** O REDCap devolve quebra de linha do Windows, e um `\r`
  sobrevivente faz o PyYAML desistir do bloco literal e gravar os objetivos
  como uma string entre aspas com `\n` no meio — YAML válido e ilegível num
  arquivo que existe para ser aberto no editor.
* **Espaço no fim da linha some.** Pelo mesmo motivo: linha terminada em
  espaço também derruba o bloco literal.
* **Três linhas em branco viram uma.** O cliente aperta Enter várias vezes;
  cada uma viraria um parágrafo vazio no documento.

### `def _finalidade(registro, rotulos)`

*linha 252*

Resolve o `fin` para o texto que vai impresso no documento.

O campo é `radio`: chega `"3"`, e `"3"` não se imprime em relatório. A ordem
de preferência é:

1. o que o cliente **escreveu** em `outros1`, quando a opção marcada é a de
   "Outros" — é a resposta de verdade, e o rótulo seria só a palavra "Outros";
2. o rótulo da opção, vindo dos metadados;
3. nada.

O `outros1` só é usado quando a opção é a de "Outros" (ou quando o código não
tem rótulo nenhum): o REDCap **guarda** o que foi digitado mesmo depois de a
ramificação esconder o campo, então um `outros1` de uma resposta anterior
apareceria no lugar da finalidade escolhida.

### `def _e_outros(rotulo)`

*linha 283*

### `def _opcoes(bruto)`

*linha 286*

`"1, Artigo | 4, Outros: {outros1}"` → `{"1": "Artigo", "4": "Outros"}`.

A divisão do código é na **primeira** vírgula, e só nela: rótulo com vírgula
dentro é comum ("Artigo científico, revisão ou capítulo") e partir em todas
devolveria um rótulo cortado no meio.

### `def _primeiro_par_preenchido(registro)`

*linha 305*

Procura nos campos de nome e matricula mesmo quando o `intro` estiver em branco.

## `flatcap/nomes.py`

`SPDX-FileCopyrightText: 2026 Matheus Fernandes` · `SPDX-License-Identifier: GPL-3.0-or-later`

*261 linhas.*

Construção das funções sobre regras de nomenclatura das pastas dos `Clientes` e
dos seus projetos, e como reencontrá-las no disco.

São dois níveis, e a separação é a mudança da versão 1.1.0:

    FLATCAP_ROOT/
    └── 00742 - José Antônio de Sá/      a pasta do CLIENTE — `nome_pasta`
        ├── Projeto 006/                 a pasta do PROJETO — `nome_do_projeto`
        └── Projeto 041/                 o mesmo cliente, outra solicitação

Até a 1.0.0 as duas eram a mesma pasta, porque a premissa era um projeto por
cliente. Ela não se sustenta: o mesmo professor volta ao REDCap com um estudo
novo, e o formulário gera um `record_id` novo para a mesma matrícula. A
matrícula continua identificando **a pessoa** e passa a não identificar mais
**o trabalho** — quem faz isso agora é o `record_id`, que é único por
solicitação.

Daí as duas regras deste módulo:

**A pasta do cliente é procurada pela matrícula**, e por prefixo, porque ela
pode ter sido criada à mão, renomeada, ou ter a grafia do nome corrigida
depois. A matrícula é a parte que não muda.

**A pasta do projeto é nomeada pelo `record_id`**, com zero à esquerda até três
dígitos. O zero não é enfeite: o Explorer e o Finder ordenam nome de pasta como
texto, e sem ele `Projeto 10` aparece antes de `Projeto 6`. Acima de 999 o
número cresce sozinho — `Projeto 1234` —, e aí a ordenação volta a depender do
acaso; é o preço de não truncar um identificador, que seria pior.

- *linha 39* — `PROIBIDOS = r'/\:*?"<>|'` — caracteres proibidos para fazer nome de pasta no windows

- *linha 43* — `_CONTROLE = re.compile(r"[\x00-\x08\x0e-\x1f\x7f]")` — caracteres de controle

- *linha 45* — `_ESPACOS = re.compile(r"\s+")` — espaços escritos em "formato de sistema"

- *linha 47* — `SEPARADOR = " - "` — separador do número de matrícula e do nome completo

- *linha 49* — `PREFIXO_PROJETO = "Projeto "` — o que abre o nome da pasta de um projeto

- *linha 51* — `LARGURA_DO_NUMERO = 3` — zeros à esquerda: 6 -> 006. Acima de 999 o número cresce

- *linha 53* — `SEPARADOR_ROTULO = " · "` — entre o cliente e o projeto, no que vai para a tela

### `class NomeInvalidoError(ValueError)`

*linha 56*

Não sobrou caractere para nomear a pasta.

### `def sanitizar(texto)`

*linha 61*

Limpar o texto antes de criar o nome da pasta. Ajusta:
1. remove caracteres de controle;
2. remove caracteres proibidos (windows);
3. corrige espaços em excesso;
4. tira os espaços das duas pontas e os pontos do final — que o Windows
   apagaria em silêncio, e a pasta deixaria de ter o nome que o FlatCap procura.

### `def nome_pasta(matricula, nome)`

*linha 76*

Monta o nome da pasta do cliente: `123456789 - Matheus Fernandes`

Raises:

    NomeInvalidoError: erro para quando não tem número de matrícula válido.

*linha 92*

> Nome vazio não impede o trabalho, apenas a matrícula é indispensável.

### `def nome_do_projeto(record_id)`

*linha 100*

Monta o nome da pasta do projeto: `6` vira `Projeto 006`.

O zero à esquerda existe para a ordenação alfabética do Explorer bater com a
numérica: sem ele, `Projeto 10` vem antes de `Projeto 6` na tela, e a pasta
de um cliente com quatro trabalhos deixa de ser lida de cima para baixo.

`int()` antes de formatar torna a função idempotente: tanto `"6"` quanto
`"006"` produzem `Projeto 006`, o que é o que permite reencontrar a pasta
quando você digita o número como ele aparece no nome dela em vez de como ele
aparece no `flatcap listar`.

`record_id` que não é número — nenhum REDCap comum gera um, mas o campo é
texto e o FlatCap nunca assumiu o contrário — passa pela mesma `sanitizar`
das pastas e entra como está.

Raises:

    NomeInvalidoError: `record_id` vazio, ou sem nada depois da limpeza.

### `def e_pasta_de_projeto(nome_da_pasta)`

*linha 131*

Este nome de pasta foi escrito pelo `nome_do_projeto`?

Serve para separar as subpastas de projeto das outras coisas que moram na
pasta do cliente — um `template.docx`, uma pasta de anotações suas. Exige
algo depois do prefixo: uma pasta chamada exatamente `Projeto` não é um.

### `def localizar_pasta(root, matricula)`

*linha 144*

Procura a pasta do CLIENTE dentro do `FLATCAP_ROOT`.

Busca por prefixo para garantir que não perca quando a pasta foi criada ou
renomeada à mão. Continua devolvendo a pasta do cliente, e não a do projeto:
quem desce o segundo nível é `caminho_do_projeto` (por nome) ou
`ficha.localizar_projeto` (lendo as fichas).

### `def _combina(nome_da_pasta, matricula)`

*linha 164*

Função que diz o resultado da busca pela pasta usando a matrícula.
Busca só a matrícula, então aceita vários formatos de nomes, para garantir que
não quebre com pastas feitas a mão ou com mudanças de configurações em server.

### `def projetos_do_cliente(pasta_do_cliente)`

*linha 176*

As pastas `Projeto *` que existem dentro da pasta de um cliente, em ordem.

Só pelo nome — não abre `projeto.yaml` nenhum. É o que o `flatcap listar`
usa, e ele roda várias vezes por dia sobre o root inteiro: ler uma ficha por
projeto para desenhar uma coluna da tabela seria pagar caro por uma pergunta
que o nome da pasta já responde.

### `def caminho_do_projeto(root, matricula, record_id)`

*linha 196*

A pasta deste projeto deste cliente, se ela já estiver no disco.

Só pelo nome, como `projetos_do_cliente` e pelo mesmo motivo. Devolve `None`
quando o cliente não tem pasta, ou tem e ainda não tem **este** projeto — e
essa distinção é justamente a que o `listar` precisava passar a fazer: até a
1.0.0 ele respondia "este cliente já tem pasta", e com mais de um projeto por
cliente essa resposta faria a segunda solicitação parecer já atendida.

### `def localizar_projeto_por_record(root, record_id)`

*linha 217*

Procura `Projeto NNN` em **todas** as pastas de cliente do root.

Existe para uma situação só, e ela acontece: a matrícula foi corrigida no
REDCap depois de a pasta ter sido criada. O `localizar_pasta` não encontra
mais o cliente pela matrícula nova, o `novo` acharia que é um cliente
inédito, e o mesmo `record_id` ganharia uma segunda pasta em outro lugar —
duas pastas para o mesmo trabalho, cada uma com metade da história.

Pelo nome, e não lendo fichas, porque este módulo é o de baixo: `ficha.py`
importa daqui, então importar `ficha.py` aqui fecharia um ciclo. A busca por
nome é suficiente para o que ela precisa impedir.

### `def rotulo_do_projeto(raiz)`

*linha 246*

Como um projeto se chama na tela e nos documentos:
`00742 - José Antônio de Sá · Projeto 006`.

Só o nome da pasta não serve mais. Ele era `00742 - José Antônio de Sá` e
passou a ser `Projeto 006`, que não identifica ninguém — e é esse texto que
encabeça o `perfil.md` impresso que vai para a reunião.

Pasta fora da convenção (uma raiz de teste, uma pasta que você montou à mão)
sai com o próprio nome, sem inventar um cliente que não existe.

## `flatcap/projeto.py`

`SPDX-FileCopyrightText: 2026 Matheus Fernandes` · `SPDX-License-Identifier: GPL-3.0-or-later`

*873 linhas.*

A pasta do projeto no disco: decidir o que criar e depois criar.

Primeira camada que **compõe** as outras: junta `config`, `redcap`, `modelo` e
`nomes` para responder a uma pergunta só — o que acontece quando chega uma
solicitação nova. A separação interna é a regra da casa:

    plano = preparar(cfg, record_id)   # lê o REDCap, decide tudo, não toca no disco
    executar(plano)                    # só escreve; não decide mais nada

É o que faz a simulação valer alguma coisa: sem `--sim` e com `--sim` o
comando percorre o mesmo `Plano`, e a simulação apenas não chama `executar`.

### O que mudou na 1.1.0: a pasta do cliente deixou de ser a pasta do projeto

    FLATCAP_ROOT/
    └── 00742 - José Antônio de Sá/      do CLIENTE — pode já existir
        └── Projeto 006/                 do PROJETO — é esta que o `novo` cria
            ├── projeto.yaml
            ├── historico.md
            ├── 1. Dados originais/
            ├── 2. Versões antigas/
            └── 3. Análises/

O mesmo cliente volta ao REDCap com um estudo novo, e o formulário lhe dá um
`record_id` novo. Antes, a segunda solicitação batia na recusa "já existe pasta
para essa matrícula" e não tinha para onde ir.

**A idempotência mudou de sujeito, e não de regra.** Ela continua sendo "o
`novo` nunca escreve sobre pasta existente" — o que mudou é qual pasta responde
pela pergunta. Pasta do cliente já existente passou a ser o caso normal (é o
cliente que voltou) e é reaproveitada; quem faz o comando sair com código 0
avisando é a pasta `Projeto NNN`.

Uma consequência que vale registrar: a pasta do cliente é reaproveitada **como
ela estiver no disco**, mesmo que o nome não seja mais o que `nome_pasta`
produziria hoje — nome corrigido à mão, grafia arrumada depois. É a mesma
decisão da Fase 2 (a matrícula é a parte que não muda), e é o que impede o
FlatCap de criar uma segunda pasta para um cliente que já tem uma.

- *linha 92* — `PASTA_DADOS = SUBPASTAS[0]` — onde vive a versão vigente do banco

- *linha 93* — `PASTA_ANTIGAS = SUBPASTAS[1]` — para onde a versão anterior é rodada na Fase 3

- *linha 94* — `PASTA_ANALISES = SUBPASTAS[2]` — onde a Fase 5 escreve a pasta `descritiva/`

*No módulo, linha 95:*

> O .docx da Fase 6 fica na raiz da pasta do projeto — não há `4. Relatórios/`.

### `PASTA_DESCRITIVA`

*linha 97*

> A rodada da descritiva. Mora aqui, e não no `descritiva.py` onde nasceu, desde
> a Fase 6: o desenho da pasta é assunto deste módulo, e o `relatorio.py` precisa
> saber onde a rodada está sem importar o módulo que carrega o `pandas` para
> calculá-la. O `descritiva.py` reexporta o nome, então nenhum chamador mudou.

### `PASTA_NORMALIDADE`

*linha 103*

> A rodada da normalidade, a primeira análise da Fase 7. Mora ao lado da
> descritiva pelo mesmo motivo: o desenho da pasta é assunto deste módulo, e o
> `relatorio.py` precisa saber onde as rodadas estão sem importar os módulos que
> carregam o `pandas` e o `scipy` para calculá-las.

### `PASTA_CRUZAMENTO`

*linha 109*

> A rodada do cruzamento. Mesmo motivo das duas de cima, e o mesmo nome em três
> lugares: a pasta, o campo `analise` do manifesto e a chave da ficha — a lista
> `analises:` e o bloco `cruzamento:` com os pares.

### `PASTA_ASSOCIACAO`

*linha 114*

> A rodada da associação. O mesmo nome nos três lugares, como o cruzamento: a
> pasta, o campo `analise` do manifesto e a chave da ficha — a lista `analises:` e
> o bloco `associacao:` com os pares.

### `PASTA_CORRELACAO`

*linha 119*

> A rodada da correlação. O mesmo nome nos três lugares, como as duas de cima: a
> pasta, o campo `analise` do manifesto e a chave da ficha — a lista `analises:` e
> o bloco `correlacao:` com os pares.

### `PASTA_COMPARACAO`

*linha 124*

> A rodada da comparação. O mesmo nome nos três lugares, como as de cima: a pasta,
> o campo `analise` do manifesto e a chave da ficha — a lista `analises:` e o bloco
> `comparacao:` com os itens. Uma pasta só para todos os testes de comparação: o
> teste é escolhido dentro da análise, e não é uma análise por teste.

### `PASTA_AMOSTRAGEM`

*linha 130*

> A pasta da amostragem, a quarta do projeto — e a única que o `novo` não cria.
>
> O projeto costuma começar com a amostragem e evoluir depois para a análise, e tudo
> da amostra mora aqui: a ficha (`desenho.yaml`), a conta, o relatório da amostra e as
> versões antigas dele. As três pastas de cima ficam para a análise.
>
> Fica fora do `SUBPASTAS` de propósito. O fluxo começa sempre no `flatcap novo`, e a
> pasta nasce no primeiro `flatcap amostragem`, que vem depois dele: o `novo` não tem
> como saber se o pedido é de amostragem — o formulário do REDCap não tem essa opção —,
> o projeto que nunca amostra não ganha uma pasta vazia, e o projeto que já existia
> ganha a pasta do mesmo jeito, sem migração.

### `ARQUIVO_DESENHO`

*linha 143*

> A ficha da amostra, dentro da pasta dela. É o `projeto.yaml` da amostragem: escrita
> pelo FlatCap uma vez, como modelo, e preenchida à mão daí em diante.

### `PASTA_ANTIGAS_DA_AMOSTRAGEM`

*linha 147*

> As versões antigas da amostra moram dentro da pasta dela, e não em
> `2. Versões antigas/`: tudo da amostra fica na pasta da amostra.

### `ARQUIVO_TEMPLATE`

*linha 151*

> O modelo do relatório. Mora aqui pelo mesmo motivo das pastas: o nome de um
> arquivo que o FlatCap procura dentro da pasta do projeto é desenho de pasta.
> Ele estava escrito duas vezes — no `documento.py`, que é quem o grava, e no
> `relatorio.py`, que não podia importar o `documento.py` sem trazer o
> `python-docx` junto para uma simulação que não escreve documento nenhum. Os
> dois passaram a importá-lo daqui, e o `documento.py` reexporta o nome.

### `EXTENSOES_DE_BANCO`

*linha 159*

> As extensões que um banco do cliente pode ter.
>
> Moram aqui, e não no `banco.py` que as usa para abrir, pelo mesmo motivo que
> `PASTA_DESCRITIVA`: quem precisa da resposta **sem** abrir o banco é o
> `dados.py`, que confronta a ficha com o disco e precisa distinguir o que, na
> pasta, é candidato a versão do que é um relatório arquivado. E o `dados.py`
> não pode importar o `banco.py` — é o `banco.py` que importa o `dados.py`.

### `def pastas_das_analises(raiz)`

*linha 169*

As pastas de rodada que existem em `3. Análises/`, em ordem de nome.

É a varredura que o `relatorio.py` faz para descobrir **quais** análises
foram rodadas neste projeto, em vez de procurar uma pasta de nome fixo. Foi
a falta dela que deixou a normalidade escrever `normalidade.csv` e os
`qq_*.png` no disco sem que nada disso entrasse no `.docx` — e teria feito o
mesmo com o teste t e o qui-quadrado.

Só o primeiro nível, e só diretório: o que está **dentro** de uma rodada é
assunto do `manifesto.json` dela. Quem decide se a pasta é mesmo uma rodada é
quem a lê — aqui a pergunta é só qual pasta existe.

### `def pasta_da_analise(raiz, analise)`

*linha 189*

Onde mora a rodada vigente de uma análise: `3. Análises/<analise>/`.

Uma função e não uma concatenação em cada módulo, porque é aqui que a resposta
muda no dia em que ela mudar — e porque é ela que o `relatorio.py` vai usar
para varrer `3. Análises/*/` em vez de procurar uma pasta com nome fixo.

O nome da análise é o mesmo que vai escrito no `manifesto.json` (o campo
`analise`) e o mesmo que se escreve na lista `analises:` da ficha. Um nome só
para as três coisas é o que faz a lista da reunião, a pasta no disco e a ordem
das seções do documento se encontrarem sem tradução no meio.

### `def pasta_da_amostragem(raiz)`

*linha 205*

Onde mora tudo da amostra deste projeto: `4. Amostragem/`.

Ao lado de `3. Análises/`, e não dentro dela: a amostragem não é uma análise da
lista `analises:`, e o relatório das análises, que varre `3. Análises/`, não a vê.
Uma função, como a `pasta_da_analise`, porque é aqui que a resposta muda no dia em
que ela mudar.

- *linha 216* — `PREFIXO_REDCAP = "00_redcap_"` — feito dessa forma para manter uma ordem cronológica

### `STATUS_NAO_INICIADO`

*linha 218*

> O `status:` do `projeto.yaml`: os seis valores, na ordem do atendimento.
>
> Dois são escritos pelo FlatCap. O `não iniciado`, pelo `flatcap novo`, que cria a
> ficha; e o `pronto`, pelo `flatcap relatorio`, quando escreve o documento. Os outros
> quatro são seus, escritos à mão: o `cálculo amostral`, enquanto o tamanho da amostra
> é calculado, antes da coleta; o `aguardando banco de dados` e o `em andamento`,
> depois da reunião; e o `finalizado`, quando o atendimento termina — e aí o projeto
> sai do `flatcap status`.
>
> Moram aqui pelo motivo das pastas: este módulo é o dono dos nomes que atravessam o
> pacote. A ficha os lê, o relatório escreve um deles e o painel mostra os outros.

### `class ProjetoError(RuntimeError)`

*linha 249*

Falha ao montar a pasta do projeto, já traduzida para o usuário.

Erro próprio pelo mesmo motivo de `ConfigError` e `RedcapError`: a CLI captura
esta classe e transforma em painel; qualquer outra exceção é bug de verdade e
deve subir com o traceback inteiro.

### `class RegistroNaoEncontradoError(ProjetoError)`

*linha 259*

O REDCap não tem nenhum registro com este `record_id`.

### `class LayoutAntigoError(ProjetoError)`

*linha 265*

A pasta do cliente ainda tem o `projeto.yaml` na raiz — o formato anterior
à 1.1.0, de quando um cliente tinha um projeto só.

Recusa e não conserta: mover pasta do usuário é operação que o FlatCap
nunca fez sozinho, e a mensagem diz exatamente o que mover. O `ficha.py`
tem um erro homônimo, com o mesmo texto, para o mesmo diagnóstico do lado
de quem só lê o disco — ver `texto_da_migracao`.

### `class ClienteIncompletoError(ProjetoError)`

*linha 277*

O registro existe, mas não dá para nomear a pasta a partir dele.

A automação cria pasta apenas para registro bem formado. Quem diagnostica é o
`flatcap listar`, que já marca esses casos em amarelo; o `novo` apenas se
recusa a produzir uma pasta que você teria de renomear depois.

### `class ProjetoExistenteError(ProjetoError)`

*linha 287*

Já existe pasta para **este projeto**. Nada foi mudado.

Até a 1.0.0 a pergunta era "esta matrícula já tem pasta?". Agora é "este
`record_id` já tem pasta?", porque a matrícula passou a poder ter várias:
recusar pela matrícula tornaria impossível criar o segundo projeto de um
cliente, que é justamente o caso que esta versão existe para atender.

O caminho fica gravado em `.pasta`, isso previne erros de quando a pasta é criada manualmente.

#### `def __init__(self, mensagem, pasta)`

*linha 299*

### `class ArquivoPlanejado`

*linha 305*

Um arquivo já baixado com destino e o recibo pronto -> ainda na memória.

O `sha256` é calculado aqui. É a diferença entre o recibo e uma anotação.

#### `def tamanho(self)`

*linha 316*

#### `def tamanho_legivel(self)`

*linha 320*

Tamanho formatado para o terminal e para o `historico.md`.

### `class Plano`

*linha 328*

Tudo o que será criado, decidido e pronto para escrever.

Imutável como `Config` e `Cliente`: entre a simulação e a execução ninguém altera um caminho em
trânsito.
O conteúdo dos dois arquivos de texto já vem montado, para que `executar` não precise tomar
nenhuma decisão.

#### `def tem_anexo(self)`

*linha 348*

#### `def pasta_do_cliente(self)`

*linha 352*

A pasta do cliente, que é onde a pasta do projeto vai morar.

Deduzida da raiz quando não vier no plano: `pasta_cliente` tem default
para que um `Plano` montado à mão em teste antigo continue válido.

### `class Resultado`

*linha 363*

O que `executar` de fato criou, e o que não foi planejado.

O `avisos` existe para o caso de somente-leitura: em unidades de rede ou pasta sincronizada em
nuvem o `chmod` pode não pegar.

### `def preparar(cfg, record_id, agora)`

*linha 375*

*linha 374*

> Casos de uso

Lê o REDCap e devolve o plano completo da pasta. Não escreve nada no disco.

Args:

    agora: relógio injetável. Sem ele, os testes não teriam como comparar o nome do arquivo, que
    carrega a data.

Raises:

    RegistroNaoEncontradoError, ClienteIncompletoError, ProjetoExistenteError
    RedcapError: falha de rede, token ou permissão.

### `def executar(plano)`

*linha 398*

Escreve o plano no disco. Escritor puro: não decide, não consulta a rede.

*linha 405*

> `parents=True` cria a pasta do cliente quando ela não existe e a aceita
> quando existe — mas continua estourando `FileExistsError` se a **última**
> pasta do caminho já estiver lá. É exatamente a regra que se quer aqui: o
> cliente que voltou reaproveita a pasta dele, e o projeto repetido recusa.

### `def anotar(raiz, acao, agora)`

*linha 447*

Acrescenta uma linha para o `historico.md`.

### `def marcar_somente_leitura(caminho)`

*linha 454*

Tira a permissão de escrita do arquivo. Devolve se conseguiu.

### `def nome_do_banco(anexo, quando, record_id)`

*linha 465*

Monta `00_redcap_AAAA-MM-DD_<nome original>`.

### Backend de `preparar`

### `def _buscar_cliente(cfg, record_id)`

*linha 479*

Traz um único registro do REDCap e normaliza.

*linha 493*

> O `record_id` normalizado vem do corpo da resposta; se por alguma razão vier
> vazio, o que o usuário digitou é a melhor identificação que temos.

### `def _rotulos_do_formulario(cfg)`

*linha 497*

Os rótulos das opções do `fin`, para que a ficha guarde texto e não código.

Uma segunda chamada à API, e é a única do fluxo que pode falhar sozinha: há
token do REDCap com permissão de exportar registros e sem permissão de
exportar o dicionário de variáveis. Falhar aqui derrubaria o `flatcap novo`
inteiro por causa de uma linha da primeira página, então a falha é engolida
e a `finalidade` sai vazia.

Vazia, e não com o código cru: `finalidade: 2` na ficha é um valor que
ninguém consegue ler e que ninguém percebe estar errado, enquanto o campo em
branco cai no alerta `texto_ausente` do relatório e aparece na sua frente.

### `def _conferir_identificacao(cliente)`

*linha 518*

Recusa registro sem matrícula ou sem nome, dizendo qual dos dois falta.

### `def _destino(cfg, cliente)`

*linha 538*

Decide onde a pasta vai ficar. Devolve (pasta do cliente, raiz, cliente é novo).

Três conferências, nesta ordem, e cada uma responde a uma pergunta diferente:

1. **O cliente já tem pasta?** Por matrícula, via `localizar_pasta`. Se tem,
   é reaproveitada — é o cliente voltando com um trabalho novo, e é o caso
   que esta versão existe para atender. Se não tem, o nome é montado agora.

2. **A pasta do cliente ainda está no formato antigo?** `projeto.yaml` na
   raiz dela quer dizer que a migração para dois níveis não chegou ali.
   Criar `Projeto NNN` dentro mesmo assim deixaria a pasta com duas fichas
   em níveis diferentes, e a busca do `ficha.localizar_projeto` passaria a
   encontrar a nova e ignorar a antiga — a história do primeiro trabalho
   some da vista sem nada dizer que sumiu. Recusa, com o conserto escrito.

3. **Este `record_id` já tem pasta em algum lugar?** Não só dentro desta
   pasta de cliente: em todo o root. É o caso da matrícula corrigida no
   REDCap depois de a pasta existir — a busca por matrícula não acha mais o
   cliente, e sem esta conferência o mesmo trabalho ganharia duas pastas,
   cada uma com metade da história.

### `def texto_da_migracao(pasta_do_cliente, record_id)`

*linha 611*

O diagnóstico da pasta que ficou no formato de antes da 1.1.0.

Mora aqui, e é usado também pelo `ficha.py`, porque a mensagem descreve o
**desenho da pasta**, que é assunto deste módulo. Cada um dos dois levanta o
seu próprio erro — a regra da casa continua sendo um erro por módulo —, e
nenhum dos dois reescreve o texto por conta própria: duas versões da mesma
instrução de conserto é como uma delas fica desatualizada.

### `def _baixar_anexo(cfg, cliente)`

*linha 648*

Baixa o banco anexado. Devolve `None` quando o registro não tem anexo.

### `def _montar_plano(cliente, pasta_cliente, raiz, cliente_novo, anexo, quando)`

*linha 657*

Converte cliente + anexo em um `Plano` inteiramente resolvido.

### Conteúdo de arquivos de texto

### `class _SemAncoras(yaml.SafeDumper)`

*linha 693*

Dumper que nunca cria âncora nem alias.

O PyYAML deduplica valores repetidos: como `criado_em` e a `data` do banco são a mesma data, o
arquivo saía com `criado_em: &id001 2026-08-29` e `data: *id001`.
Subclasse de `SafeDumper`, então a garantia de não instanciar objeto arbitrário na leitura
continua valendo.

#### `def ignore_aliases(self, data)`

*linha 702*

- *linha 702* — `def ignore_aliases(self, data: object) -> bool:` — noqa: ARG002

### `def _texto_em_bloco(dumper, dado)`

*linha 706*

Texto com quebra de linha sai como bloco literal, e não entre aspas.

Sem isso os `objetivos` do cliente saem assim:

    objetivos: "Objetivo geral: avaliar o perfil.\n\nObjetivos específicos:\n..."

que é YAML perfeitamente válido e ilegível num arquivo cujo cabeçalho convida
a editá-lo. Com isso saem assim:

    objetivos: |
      Objetivo geral: avaliar o perfil.

      Objetivos específicos:
      ...

O PyYAML só aceita o bloco literal se nenhuma linha terminar em espaço e não
houver `\r` no meio — quem garante isso é o `modelo._texto_longo`, na
fronteira onde o texto entra.

### `def _texto_projeto_yaml(cliente, banco, hoje)`

*linha 765*

Monta o `projeto.yaml`.

*linha 789*

> `or None` para que o campo em branco saia `finalidade: null`, do mesmo
> jeito que o `prazo` — uma linha terminada em dois-pontos parece uma
> linha que alguém começou e não terminou.

### `def _texto_historico(cliente, banco, quando)`

*linha 807*

Monta o `historico.md` com a primeira linha de log já escrita.

O título carrega cliente **e** projeto desde a 1.1.0: um `historico.md` que
se apresentasse só como `Projeto 006` não diria de quem ele é, e o arquivo
existe justamente para ser aberto seis meses depois.

### `def _linha_historico(acao, quando)`

*linha 840*

### Funções auxiliares

### `def _escrever_texto(caminho, conteudo)`

*linha 846*

Escreve texto sempre em UTF-8 e sempre com `\n`.

### `def _extensao_do_mime(tipo_mime)`

*linha 852*

### `def tamanho_legivel(bytes_)`

*linha 858*

Formata o tamanho para leitura humana, com vírgula decimal.

Pública porque a Fase 3 imprime a mesma coluna na linha do tempo das
versões: dois formatadores diferentes para a mesma grandeza é como um
relatório acaba com "1,5 MiB" numa tabela e "1572864" na seguinte.

## `flatcap/ficha.py`

`SPDX-FileCopyrightText: 2026 Matheus Fernandes` · `SPDX-License-Identifier: GPL-3.0-or-later`

*1270 linhas.*

Leitura e escrita do `projeto.yaml` — a ficha do atendimento.

Este é o primeiro módulo do FlatCap que **lê** o disco. Até a Fase 2 o disco era
só destino: o `novo` decidia tudo a partir do REDCap e escrevia. Da Fase 3 em
diante a pasta do projeto passa a ser uma fonte de informação — qual é a versão
vigente do banco, o que já foi registrado, o que o cliente combinou. É a mesma
ideia que a Fase 8 chama de "índice reconstruível": a fonte da verdade é sempre
o disco, e qualquer cache pode ser jogado fora e refeito.

Duas consequências de projeto vêm daí:

1. **O `dados adicionar` não fala com o REDCap.** A pasta já sabe de quem é.
   Pedir a rede para uma operação de arquivo local acrescentaria uma forma de
   falhar (token, VPN, servidor fora do ar) a um comando que não precisa dela.
   Por isso as funções daqui recebem `Path`, e não `Config`: a assinatura diz
   que este módulo não tem nada a ver com credenciais.

2. **A escrita é atômica.** O `projeto.yaml` é a memória do projeto. Um
   `write_text` que morre na metade — falta de espaço, unidade de rede que cai,
   OneDrive sincronizando — deixa o arquivo truncado e a ficha perdida. Aqui a
   gravação escreve um arquivo temporário ao lado e só então o troca de nome por
   cima do original, com `os.replace`, que é uma operação atômica no POSIX e no
   Windows: ou o arquivo antigo continua inteiro, ou o novo está inteiro. Nunca
   metade dos dois.

### Por que ruamel.yaml e não o PyYAML

Os dois convivem no projeto, e a divisão de trabalho é clara: o `projeto.py`
escreve a ficha do zero com o PyYAML, e este módulo a **altera** com o
`ruamel.yaml` em modo round-trip.

A diferença está em quem lê o arquivo de volta. O PyYAML descarta comentário no
parser — para ele, comentário não é dado —, então um `safe_load` seguido de
`dump` devolveria os mesmos valores e nenhuma das anotações que você escreveu
ao lado de `prazo` ou de `analises`. O ruamel em `typ="rt"` carrega os
comentários, a ordem das chaves e o estilo de aspas presos aos dados, e os
devolve na gravação. É o que sustenta literalmente a promessa do cabeçalho da
ficha: "edite à vontade, o FlatCap não sobrescreve o que você escreveu".

Toda a persistência do `projeto.yaml` está atrás das funções públicas abaixo —
`ler`, `bloco`, `acrescentar_versao`, `definir_status`, `localizar_projeto`,
`projetos_da_matricula`, `varrer`, `caminho_da_ficha`, `versao_vigente` e
`sequencia_do_nome`. Quem importa este módulo não sabe qual biblioteca de YAML está
em uso. Desde a 1.15.0, o `ler_yaml` estende o mesmo leitor aos outros YAML editados
à mão — o `desenho.yaml` da amostragem é o primeiro —, e o `numero_escrito` é a regra
de ler um número escrito num deles. Desde a 1.17.0, o `status_reconhecido` e o
`data_escrita` são as regras de ler o `status:` e o `prazo:` que você escreve.

Duas outras funções públicas, `escrever_atomico` e `temporario_ao_lado`, **não**
fazem parte desse contrato: são o utilitário de gravação que a Fase 4 passou a
compartilhar — o `dicionario.csv`, o `perfil.md`, as tabelas e os manifestos das
análises, e o `.docx` do relatório. Moram aqui porque foi aqui que a garantia
precisou existir primeiro, e porque duas implementações de escrita atômica no
mesmo pacote é como uma delas deixa de receber a próxima correção. Quem trocar
esta implementação de YAML por outra precisa levá-las junto.

### `CAMPOS_VERSAO`

*linha 98*

> Ordem em que os campos de uma versão aparecem no arquivo. Fixa de propósito:
> o `projeto.yaml` é lido por humanos, e coluna que muda de lugar cansa.

### `class FichaError(RuntimeError)`

*linha 103*

Falha ao lidar com o `projeto.yaml`, já traduzida para o usuário.

Erro próprio pelo mesmo motivo de `ConfigError`, `RedcapError` e
`ProjetoError`: a CLI captura esta classe e transforma em painel. Qualquer
outra exceção é bug de verdade e deve subir com o traceback inteiro.

### `class ProjetoNaoEncontradoError(FichaError)`

*linha 113*

Nenhuma pasta em `FLATCAP_ROOT` corresponde ao identificador pedido.

### `class FichaAusenteError(FichaError)`

*linha 119*

A pasta existe, mas não tem `projeto.yaml`.

Acontece com pasta criada à mão, antes do FlatCap existir. Não é erro do
usuário: é um projeto que ainda não foi adotado pela ferramenta.

#### `def __init__(self, mensagem, pasta)`

*linha 127*

### `class ProjetoAmbiguoError(FichaError)`

*linha 132*

A matrícula pedida tem mais de um projeto, e nenhum deles é "o" projeto.

**Não é erro de disco**, e a distinção importa: até a 1.0.0 dois achados
para o mesmo identificador só podiam ser pasta duplicada, e a mensagem
mandava resolver no disco. Desde a 1.1.0 é o caso normal de um cliente com
dois trabalhos, e o que falta é o usuário dizer de qual deles ele está
falando — por isso a lista dos projetos viaja no erro, em `.projetos`.

`record_id` repetido continua sendo erro de disco, e sai por
`ProjetoNaoEncontradoError` como antes: ele é único por construção do
REDCap, e dois iguais querem dizer pasta copiada.

#### `def __init__(self, mensagem, projetos)`

*linha 147*

### `class LayoutAntigoError(FichaError)`

*linha 152*

A pasta do cliente ainda tem o `projeto.yaml` na raiz — o formato anterior
à 1.1.0.

Homônimo do erro de `projeto.py` de propósito: é o mesmo diagnóstico visto
de dois lados (quem cria a pasta e quem a procura), e a regra da casa é um
erro por módulo, para que a CLI capture a classe daquela camada. O texto é
um só, e mora em `projeto.texto_da_migracao`.

#### `def __init__(self, mensagem, pasta)`

*linha 163*

### `class FichaInvalidaError(FichaError)`

*linha 168*

O `projeto.yaml` existe mas não é YAML válido, ou não tem o formato esperado.

#### `def __init__(self, mensagem, caminho)`

*linha 173*

### `class Versao`

*linha 179*

Uma versão do banco, do jeito que ela é registrada em `dados:`.

Imutável como `Config`, `Cliente` e `Plano`. O `sha256` é o recibo: é o que
responde "o arquivo que o cliente reenviou é diferente do anterior, ou ele
mandou o mesmo de novo?" sem abrir planilha nenhuma.

#### `def sequencia(self)`

*linha 195*

O número do prefixo (`00`, `01`, `02`...), ou `None` se o nome não seguir
a convenção. É o índice da versão na história do projeto.

### `class Ficha`

*linha 204*

O conteúdo do `projeto.yaml` que o FlatCap precisa conhecer.

Deliberadamente **não** carrega tudo o que está no arquivo: os blocos de cada
análise são seus, e quem precisa de um o lê pelo `bloco`. O que entra aqui é o
mínimo para identificar o projeto e versionar o banco.

A exceção são `finalidade` e `objetivos`, e ela tem uma regra por trás: entra
aqui o que alguma camada de cima **imprime**. Os dois saem na primeira página
de todo relatório, e o `relatorio.py` existe justamente para não abrir o banco
nem falar com o REDCap — se ele não pudesse lê-los da ficha, não teria de onde.

Os dois têm default vazio porque ficha criada antes deste campo existir
continua abrindo. Vazio não é erro: é o que faz o documento sair com o
marcador e o alerta `texto_ausente`, em vez de sair mais curto em silêncio.

`analises` é a terceira exceção, e entrou na Fase 7 por uma razão de outra
natureza: ela não é impressa, ela **dirige**. É a lista que o `flatcap novo`
grava vazia e que o cabeçalho da ficha promete desde a Fase 2 — *"o que foi
combinado na reunião. A Fase 7 lê esta lista para saber quais módulos rodar"*.
Ela entra na `Ficha` porque é a única coisa da ficha que **toda** camada de
cima consulta: é a ordem das seções do relatório quando há mais de uma rodada
na pasta.

`prazo` é a quarta, pela regra da primeira: o `flatcap status` o imprime, e lê
todas as fichas do `FLATCAP_ROOT` de uma vez — pedir o prazo pelo `bloco`
abriria cada arquivo duas vezes. Entra como está escrito (`2026-11-04`,
`04/11/2026`, ou o que estiver lá), e quem o lê como data é o `data_escrita`: um
prazo digitado errado não pode fazer a ficha inteira deixar de abrir. O `status`
entra do mesmo jeito, como texto, e quem o reconhece é o `status_reconhecido`.

Os parâmetros de cada análise — os pares da correlação, a lista de variáveis
da normalidade — **não** entram aqui. Eles são de um módulo só, e um campo na
`Ficha` por análise faria esta classe crescer a cada análise nova. Quem os lê é
o `bloco(raiz, chave)`, mais abaixo.

#### `def versao_redcap(self)`

*linha 255*

A versão baixada do REDCap — a intocável. Identificada pela origem, e não
pelo prefixo `00_`, porque a origem é o fato e o nome é convenção.

#### `def ultima_versao(self)`

*linha 266*

### `def versao_vigente(ficha)`

*linha 270*

A versão do banco que vale hoje: a de maior número de sequência.

Não é `ficha.dados[-1]`. A ordem da lista é a ordem em que as versões foram
registradas, e a ficha é editada à mão — uma entrada acrescentada fora de
ordem faria a última da lista deixar de ser a mais nova. O número do prefixo,
esse, é o índice da versão por construção da Fase 3.

Empate (duas entradas sem prefixo reconhecível) resolve pela ordem da lista,
que é a melhor informação que sobra — e o desempate é a **posição**, lida
de um `enumerate`, não um `ficha.dados.index(versao)` dentro da chave do
`max`: o `index` percorre a lista de novo a cada comparação (O(n²)) e, com
duas `Versao` idênticas, devolve o mesmo índice para as duas — que é
justamente o empate que ele deveria desfazer.

Mora aqui desde a Fase 6, e não no `banco.py`, onde nasceu. A pergunta "qual
versão vale?" se responde lendo a ficha: não precisa do `pandas`, não abre
arquivo nenhum. Deixá-la no módulo que importa o `pandas` obrigava o
`relatorio.py` — que existe justamente para **não** abrir o banco — a pagar
meio segundo de partida para consultar uma lista que ele já tinha na mão. O
`banco.py` reexporta o nome, então nenhum chamador mudou.

### Localização do projeto no disco

### `def caminho_da_ficha(raiz)`

*linha 308*

### `def localizar_projeto(root, identificador)`

*linha 312*

Encontra a pasta do projeto a partir de um `record_id` ou de uma matrícula.

A busca é feita **no disco**, lendo o `record_id` e a `matricula` de cada
`projeto.yaml`. Aceitar os dois identificadores não é conveniência gratuita:
o `record_id` é o que aparece no `flatcap listar` e o que você tem em mãos
logo depois de criar a pasta; a matrícula é o que está no nome da pasta e o
que você tem em mãos seis meses depois, olhando para o disco.

#### O que a 1.1.0 mudou aqui

A varredura desceu um nível: era `FLATCAP_ROOT/*/projeto.yaml` e passou a
ser `FLATCAP_ROOT/*/Projeto */projeto.yaml`.

E os dois identificadores deixaram de ser equivalentes, porque um deles
deixou de ser único. **O `record_id` identifica o projeto; a matrícula
identifica a pessoa.** Daí a ordem de resolução:

1. bate por `record_id` em um projeto → é esse, e ponto;
2. bate por `record_id` em mais de um → pasta duplicada no disco, que é
   erro de verdade: o REDCap não emite dois registros com o mesmo número;
3. bate por matrícula em um projeto → é esse (o caso comum, do cliente que
   só tem um trabalho — a busca por matrícula continua servindo para ele);
4. bate por matrícula em vários → `ProjetoAmbiguoError`, com a lista. Não é
   falha: é o usuário tendo dado o nome da pessoa quando a pergunta era
   sobre o trabalho.

O `record_id` vence a matrícula quando os dois batem porque ele é o mais
específico dos dois — e porque a única forma de isso acontecer é uma
matrícula que por acaso tem o mesmo número de um registro.

Raises:

    ProjetoNaoEncontradoError: nada bateu, ou `record_id` duplicado.
    ProjetoAmbiguoError: a matrícula tem mais de um projeto.
    LayoutAntigoError: a pasta do cliente está no formato anterior à 1.1.0.
    FichaAusenteError: a pasta foi encontrada pelo nome, mas não tem ficha.
    FichaInvalidaError: há ficha que não abre, e pode ser justamente a pedida.

*linha 387*

> Nada bateu. Antes de dizer "não existe", os três diagnósticos que dizem o
> que fazer, em vez de mandar o usuário procurar erro de digitação.

*linha 390*

> 1. A pasta do cliente ficou no formato de antes da 1.1.0.

*linha 401*

> 2. A pasta existe pelo nome, e não tem projeto dentro.

*linha 421*

> 3. Uma ficha ilegível não é uma nota de rodapé: enquanto houver uma, a
> busca não pode afirmar que o projeto não existe — ele pode ser justamente
> aquele que não deu para ler. Então o erro que sobe é o diagnóstico da ficha
> quebrada, que diz o que fazer, e não um "não encontrei".

### `def projetos_da_matricula(root, matricula)`

*linha 445*

Todos os projetos de um cliente, em ordem, lendo as fichas.

Pública porque é a pergunta que a `ProjetoAmbiguoError` responde. Lê as fichas,
ao contrário do `nomes.projetos_do_cliente`, que só olha nomes: aqui a matrícula
vem da ficha, então uma pasta renomeada à mão continua sendo encontrada. O painel
de todos os projetos, que a Fase 8 previa aqui, é o `varrer`, logo abaixo.

### `class Varredura`

*linha 462*

O que há no `FLATCAP_ROOT`, lido ficha por ficha.

As três listas do `_varrer`, cada item com o que já carrega: a `Ficha` sabe a
pasta dela (`raiz`), e a `FichaInvalidaError`, o arquivo que não abriu
(`caminho`).

- *linha 473* — `antigas: tuple[Path, ...] = ()` — as pastas de cliente no formato anterior à 1.1.0

### `def varrer(root)`

*linha 476*

Todos os projetos do `FLATCAP_ROOT`, lendo as fichas: o painel do
`flatcap status` parte daqui.

É a varredura do `localizar_projeto` e do `projetos_da_matricula`, e não uma
segunda: dois níveis, explícitos, para uma ficha esquecida em
`2. Versões antigas/` não virar projeto. A ficha que não abre não interrompe a
varredura — volta em `ilegiveis`, para quem pediu dizer o que fazer com ela, e o
mesmo vale para a pasta no formato antigo.

### `def _varrer(root)`

*linha 495*

Percorre o `FLATCAP_ROOT` inteiro e devolve o que encontrou, em três listas:
os projetos legíveis, as fichas que não abrem, e as pastas de cliente que
ficaram no formato anterior à 1.1.0.

Duas voltas, e não um `rglob`, para que a profundidade seja explícita: um
`projeto.yaml` só conta como projeto no segundo nível. Isso é o que impede
uma ficha esquecida dentro de `2. Versões antigas/` de ser confundida com um
projeto — e é o que permite reconhecer o layout antigo em vez de ignorá-lo.

*linha 524*

> A ficha antiga não abrir não impede o diagnóstico de layout;
> só tira dele o número do projeto a criar.

### `def _mesmo_record(da_ficha, procurado)`

*linha 539*

O `record_id` da ficha é o que o usuário digitou?

Igualdade de texto, e — quando os dois são número — igualdade de valor. O
segundo caso existe porque a pasta se chama `Projeto 006` e o `listar`
mostra `6`: digitar o que está na frente dos olhos tem de funcionar nos dois
casos.

A matrícula **não** recebe o mesmo tratamento, e a assimetria é deliberada:
lá o zero à esquerda é parte do identificador. A matrícula `00742` não é a
matrícula `742`, e tratá-las como iguais faria a busca entregar a pasta de
outra pessoa.

### `def _mensagem_ambigua(identificador, projetos, achados)`

*linha 562*

A lista de projetos do cliente, com o que distingue um do outro.

Status e banco vigente, e não só o número: o que o usuário precisa para
escolher é "qual deles é o que eu estava mexendo", e o número do registro
sozinho não responde isso seis meses depois.

### Leitura

### `def ler(raiz)`

*linha 603*

Lê o `projeto.yaml` de uma pasta de projeto.

Raises:

    FichaAusenteError, FichaInvalidaError

### `def bloco(raiz, chave)`

*linha 643*

O bloco cru de uma chave qualquer do `projeto.yaml`, ou `None`.

Existe porque **este é o único módulo do pacote que abre o `projeto.yaml`**, e
é bom que continue sendo. A Fase 7 pôs os parâmetros de cada análise na ficha —
`normalidade:` com a lista de variáveis, `correlacao:` com os pares —, e sem
esta função cada módulo de análise importaria o `ruamel` e viraria um segundo
leitor de YAML. No dia em que a implementação de YAML mudar (a decisão está em
aberto nas pendências do roteiro), quebrariam cinco lugares em vez de um.

Devolve tipos comuns de Python, e não os objetos do `ruamel`: eles são
subclasses de `dict` e `list` e funcionam do mesmo jeito, mas carregam junto os
comentários e a formatação do arquivo — e um módulo de análise que recebesse
isso poderia alterar a ficha sem querer, por uma linha que parece inofensiva.

O valor **não é validado aqui**. O formato do bloco é assunto de quem o usa:
o que é um par de variáveis para a correlação não é o que é uma lista de nomes
para a normalidade, e este módulo não tem como saber qual é qual. A recusa por
formato errado é de cada análise, com o nome dela no painel.

Raises:

    FichaAusenteError, FichaInvalidaError

### `def _simples(valor)`

*linha 682*

Converte o que o `ruamel` devolveu para `dict`, `list` e escalares comuns.

### `def _analises(documento)`

*linha 693*

A lista `analises:`, com o que não for texto descartado.

Descarta em silêncio, e a escolha é deliberada. Esta lista é editada à mão, e
o estrago de uma entrada malformada é pequeno e local: a seção correspondente
não aparece na ordem pedida. Recusar a ficha inteira por causa dela travaria
`flatcap dados listar` e `flatcap relatorio` — comandos que não têm nada a ver
com a lista — por um erro de digitação em uma linha que nenhum deles lê.

### `def ler_yaml(caminho)`

*linha 713*

O conteúdo de outro YAML editado à mão, em tipos comuns de Python.

O `desenho.yaml` da amostragem é o primeiro. Existe pelo motivo do `bloco`: este é
o único módulo do pacote que abre YAML. E o `desenho.yaml` quebra pelos mesmos
motivos da ficha — tabulação, dois-pontos dentro de um valor sem aspas —; lido por
aqui, ele ganha o mesmo diagnóstico, em vez da mensagem crua do parser.

O valor **não é validado aqui**, como no `bloco`: o que é um desenho válido é
assunto de quem o usa.

Raises:

    FichaAusenteError: o arquivo não existe.
    FichaInvalidaError: o arquivo não é um YAML válido.

### `_NUMERO_ESCRITO`

*linha 737*

> Um número escrito como texto num YAML editado à mão: `"24,9"`, `"24.9"`, `" 25 "`.
> Sem separador de milhar — `1.234,5` é ambíguo, e ambiguidade numa ficha se recusa.

### `def numero_escrito(valor)`

*linha 742*

Um número, a partir de como o YAML o trouxe; `None` quando não é um.

Número do YAML entra como está. Texto entra quando é um número escrito — com
vírgula ou ponto decimal, e sem separador de milhar: é o `margem: 2,5` do
`desenho.yaml`, que o YAML lê como texto, e o `"24,9"` entre aspas que a recusa
da comparação ensina a escrever. Lógico não é número, embora o Python ache que
`True` vale 1.

Morava na comparação, como `referencia_escrita`, e desceu para cá na 1.15.0: a
amostragem lê o `desenho.yaml` com a mesma regra, e duas regras para o mesmo
número escrito à mão é como uma ficha aceita `2,5` e a outra o recusa.

### `_DATA_ISO`

*linha 768*

> As duas formas de escrever uma data à mão que a ficha aceita: a do YAML
> (`2026-11-04`, que ele já entrega como data) e a do Brasil (`04/11/2026`, que ele
> entrega como texto). Dia e mês com um algarismo só valem nas duas.

### `def data_escrita(valor)`

*linha 775*

Uma data, a partir de como o YAML a trouxe; `None` quando não é uma.

É a regra do `prazo:`, que se escreve à mão depois da reunião. Sem aspas,
`2026-11-04` chega do YAML como data, e entra como está; `04/11/2026` chega como
texto, e é lido como dia, mês e ano — a ordem de quem escreve em português. O ano
tem quatro algarismos nas duas formas: `04/11/26` é 2026 ou 1926, e ambiguidade
numa ficha se recusa, como no `numero_escrito`. A data que não existe —
`31/02/2026` — também não é data.

### `_STATUS_DE_ANTES`

*linha 805*

> Os status que o cabeçalho de toda ficha anterior à 1.17.0 sugeria. O `novo` é o que
> o `flatcap novo` escrevia, e é o `não iniciado` de hoje; o `em_analise` é o
> `em andamento`. O terceiro, `entregue`, fica de fora de propósito: ele pode ser o
> `pronto` ou o `finalizado`, e adivinhar o segundo tiraria do painel um projeto que
> ainda não terminou.

### `def _chave_do_status(texto)`

*linha 816*

O status reduzido ao que se compara: minúsculas, sem acento, `_` e `-` como
espaço, e um espaço só entre as palavras.

### `def status_reconhecido(escrito)`

*linha 832*

Qual dos status do `projeto.STATUS` está escrito na ficha; `None` quando não é
nenhum deles.

A leitura é tolerante e a escrita é estrita, como no `dicionario.csv`: o status se
digita à mão, e `Em andamento`, `EM ANDAMENTO` e `nao iniciado` são os de sempre —
o que volta é sempre a grafia do `projeto.STATUS`. Os dois que a ficha anterior à
1.17.0 sugeria no cabeçalho, `novo` e `em_analise`, também são reconhecidos,
porque toda ficha criada até ali diz `novo`.

O que não é nenhum deles volta `None`, e não um palpite: quem mostra o status é
quem decide o que fazer com um texto que não se reconhece — o painel o mostra como
está, marcado.

### Escrita

### `def acrescentar_versao(raiz, versao)`

*linha 853*

Acrescenta uma entrada ao fim da lista `dados:`, preservando o resto.

Não é um "reescreve o arquivo com os campos que eu conheço". O `projeto.yaml`
é editado à mão — o cabeçalho gerado pelo `novo` promete isso literalmente —
e um comando que apagasse o `prazo` que você preencheu, ou a lista `analises`
que você combinou na reunião, tornaria a promessa falsa.

*linha 878*

> Chave ausente, `dados:` vazio (que vira None) ou sobrescrito por engano.

*linha 884*

> Uma lista que veio do arquivo como `dados: []` mantém o estilo em linha, e
> a entrada nova sairia toda espremida em uma linha só. Bloco é o formato em
> que este arquivo é lido e editado.

### `def definir_status(raiz, status)`

*linha 893*

Escreve o `status:` da ficha, preservando o resto — os comentários, as aspas e a
ordem das chaves, como o `acrescentar_versao`.

É a exceção à promessa do cabeçalho — "o FlatCap não sobrescreve o que você
escreveu" —, e o cabeçalho de toda ficha nova a diz: o `flatcap relatorio`,
quando escreve o documento, passa o projeto para `pronto`. Por isso o valor é
sempre um dos do `projeto.STATUS`, na grafia de lá: um texto qualquer aqui
seria o FlatCap escrevendo na ficha um status que o painel não reconhece.

O comentário escrito ao lado do `status:` fica onde está. A ficha sem a chave a
ganha logo depois do `prazo`, que é onde o `flatcap novo` a escreve; sem `prazo`,
no fim.

Raises:

    FichaAusenteError, FichaInvalidaError
    ValueError: o status não é um do `projeto.STATUS` — defeito de quem chamou, e
        não do arquivo.

### Backend: ruamel.yaml

### `RECUO_PADRAO`

*linha 941*

> O `indent()` do ruamel vale para o documento inteiro — não há como preservar o
> recuo de cada lista separadamente. Então a escolha é entre impor um estilo e
> adotar o que o arquivo já usa. Impor era o que transformava um
> `  - descritiva` escrito à mão em `- descritiva`: YAML idêntico, e um diff
> gratuito num arquivo que o cabeçalho da ficha promete não mexer.

- *linha 946* — `RECUO_PADRAO = 0` — o `-` na coluna da chave — o que o PyYAML do `projeto.py` escreve

### `_ABRE_BLOCO`

*linha 948*

> Uma chave que termina em `|` ou `>` abre um bloco literal. O `[-+]?\d*` cobre
> os indicadores (`|-`, `>+`, `|2`) e o `(#.*)?` o comentário na mesma linha.

### `def _recuo_das_listas(texto)`

*linha 953*

Em que coluna, em relação à chave que as contém, este arquivo escreve o `-`.

Devolve `0` para o estilo que o `flatcap novo` grava::

    dados:
    - arquivo: 00_redcap_2026-09-01_banco.xlsx

e `2` para o que se escreve à mão sem pensar::

    analises:
      - descritiva

Vence a **primeira** lista do arquivo. Um arquivo que mistura os dois estilos
não tem como manter os dois — o recuo do ruamel é do documento inteiro — e na
ficha do FlatCap `analises:` vem antes de `dados:`, então quem vence é o bloco
que você editou à mão. É o lado certo de errar: a lista `dados:` é escrita
pela ferramenta e ninguém decora a coluna dela.

Linha dentro de bloco literal (`objetivos: |`) é pulada: um `- ` ali é prosa
do cliente, não item de lista.

### `def _construtor(recuo_da_lista)`

*linha 1005*

O leitor/escritor round-trip, configurado.

`typ="rt"` é o modo que carrega comentários e formatação junto com os dados
e os devolve na hora de gravar. `preserve_quotes` mantém `matricula: "00742"`
entre aspas — sem isso a matrícula voltaria como o número 742 e a pasta
deixaria de bater com o registro. E `width` alto impede que o ruamel quebre
um nome de arquivo longo em duas linhas: é YAML válido, mas ilegível em um
arquivo feito para ser aberto no editor.

O `recuo_da_lista` é o único parâmetro porque é a única coisa aqui que não se
decide no código: ela vem do arquivo que está sendo reescrito. Ver
`_recuo_das_listas`.

### `def _representar_nulo(dumper, _dados)`

*linha 1028*

Escreve o vazio como `null`, e não como uma linha terminada em dois-pontos.

O ruamel, por padrão, grava `prazo:` — que o parser lê como nulo, mas que
parece uma linha que alguém começou e não terminou. `prazo: null` diz que o
campo está deliberadamente vazio. É também o que o PyYAML do `projeto.py`
escreve quando cria a ficha, e os dois lados produzem o mesmo arquivo.

### `def _carregar_documento(caminho)`

*linha 1040*

### `def _gravar_documento(caminho, documento)`

*linha 1048*

*linha 1051*

> O recuo é lido do arquivo que está no disco, e não do documento carregado:
> o ruamel prende os comentários aos dados, mas não a coluna em que as listas
> foram escritas.

### `def _mapa_da_versao(versao)`

*linha 1061*

Converte a `Versao` no mapeamento que vai para o arquivo, na ordem fixa.

### Auxiliares de leitura e gravação

### `def sequencia_do_nome(nome)`

*linha 1077*

Extrai o prefixo numérico de `02_revisado_2026-03-14_banco.xlsx` → 2.

Devolve `None` para nome que não segue a convenção — arquivo que o cliente
largou na pasta à mão, por exemplo. `None` e `0` são coisas diferentes aqui,
e é por isso que a função não devolve `-1` nem `0` como "não sei".

### `def _ler_texto(caminho)`

*linha 1091*

Lê sempre em UTF-8, nunca na codificação do sistema.

No Windows em português o padrão é cp1252, e o campo `nome` com acento
voltaria diferente do que foi gravado — ou estouraria na leitura.

### `def escrever_atomico(caminho, texto)`

*linha 1110*

Grava o arquivo inteiro ou não grava nada.

Pública desde a Fase 4: o `dicionario.csv` guarda as decisões da reunião e o
`perfil.md` é o documento que você leva para ela. Os dois merecem a mesma
garantia que o `projeto.yaml`, e duas implementações de escrita atômica no
mesmo pacote é como uma delas deixa de receber a próxima correção.

O temporário é criado **na mesma pasta** do destino de propósito: `os.replace`
só é atômico dentro do mesmo sistema de arquivos, e um temporário em `/tmp`
poderia estar em outro disco — aí a troca vira cópia, que pode falhar pela
metade. O `fsync` força o conteúdo para o disco antes da troca; sem ele, uma
queda de energia logo depois pode deixar o nome novo apontando para um
arquivo vazio.

### `def temporario_ao_lado(destino)`

*linha 1139*

Cria um arquivo vazio, de nome único, na pasta do destino. Devolve o
descritor aberto para escrita e o caminho.

O modo pedido é `0o666`, e o sistema tira dele o `umask` do processo — o que
acontece com qualquer arquivo que um programa cria. Até a 1.13.0 quem criava
o temporário era o `tempfile.NamedTemporaryFile`, que usa `0o600` de propósito
(um temporário não é para mais ninguém ler), e o `os.replace` levava esse modo
para o destino: todo `projeto.yaml`, `dicionario.csv`, `perfil.md`, tabela,
manifesto e `.docx` saía legível só pelo dono. Num `FLATCAP_ROOT` dividido pela
equipe num servidor Linux ou num Mac, os colegas não abriam nada. No Windows
quem decide é a permissão da pasta, e nada mudou por lá.

Pública porque o `documento.py` grava o `.docx` atomicamente com o mesmo
temporário — e duas formas de criá-lo é como uma delas fica com o defeito.

*linha 1157*

> `O_BINARY` só existe no Windows: sem ele a biblioteca C trocaria cada `\n`
> por `\r\n` na escrita, por baixo do `newline="\n"`.

### `def _texto(documento, chave)`

*linha 1169*

### `def _versoes(documento, caminho)`

*linha 1176*

Traduz a lista `dados:` para objetos, recusando o que não dá para interpretar.

### `def _inteiro(valor)`

*linha 1211*

### `def _data(valor)`

*linha 1218*

O YAML já entrega `date` quando a data está sem aspas. Com aspas vem texto,
e é isso que esta função resgata — o arquivo é editado à mão, e digitar
`data: "2026-03-14"` é natural.

### `def _diagnostico(texto, caminho, erro)`

*linha 1236*

Traduz o estouro do parser, com um caso especial que vale ouro.

Versões do `flatcap novo` anteriores à 0.4.0 escreviam uma barra solta na
primeira linha do arquivo (uma continuação de linha `\` digitada como `/`
no cabeçalho). O YAML gerado é sintaticamente impossível, e a mensagem crua
do parser fala de `<document start>` — que não diz nada a quem abrir o
arquivo e vir um `/` inofensivo na primeira linha.

O `reparar_fichas.py`, que consertava todas as pastas de uma vez, foi
aposentado quando a migração da Fase 3 terminou. Este diagnóstico **não** vai
junto: a ficha quebrada reaparece toda vez que alguém restaura uma pasta de um
backup anterior à 0.4.0, e aí o conserto é manual — e precisa estar escrito
aqui, porque não há mais script para indicar.

## `flatcap/dados.py`

`SPDX-FileCopyrightText: 2026 Matheus Fernandes` · `SPDX-License-Identifier: GPL-3.0-or-later`

*587 linhas.*

Versionamento dos bancos de dados de um projeto.

Responde ao passo 3c do fluxo: conviver com a versão que veio do REDCap e a
versão revisada que o cliente manda depois da reunião, sem nunca perder o rastro
de qual é qual.

Segue o mesmo padrão da Fase 2 — decidir e escrever são funções separadas:

    plano = preparar_adicao(root, identificador, caminho)  # só lê
    executar_adicao(plano)                                 # só escreve

E a diferença que vale registrar em relação à Fase 2: **nada aqui fala com o
REDCap**. A pasta do projeto já sabe de quem ela é, e a resposta está no
`projeto.yaml`. Por isso as funções recebem `root: Path` e não `Config`: um
comando que só mexe em arquivo local não deve poder falhar por token expirado.

### As três regras que sustentam a cronologia

1. **O `00_redcap_*` nunca se move e nunca se apaga.** Há uma verificação
   explícita antes de qualquer rotação, e um teste com o nome disso.

2. **O número do prefixo é o índice da versão e nunca se repete.** A primeira
   revisão é `01_`, a segunda `02_`, a terceira `03_`. `1. Dados originais/`
   fica sempre com o `00_redcap_*` e a versão vigente; `2. Versões antigas/`
   acumula as anteriores em ordem. É um desvio deliberado do texto do roteiro,
   que escreve `01_revisado_` sempre: com o número fixo, duas versões diferentes
   levariam o mesmo prefixo e a ordem passaria a depender só da data no nome —
   que empata quando o cliente reenvia duas vezes no mesmo dia.

3. **Reenvio idêntico não vira versão.** O `sha256` do arquivo é comparado com o
   de todas as versões já registradas antes de qualquer escrita. É exatamente a
   pergunta que o roteiro levanta: "o arquivo que o cliente reenviou é realmente
   diferente do anterior, ou ele mandou o mesmo de novo?".

- *linha 72* — `SEQUENCIA_MAXIMA = 99` — o prefixo tem dois dígitos

- *linha 74* — `_BLOCO = 1024 * 1024` — 1 MiB por leitura ao calcular o hash

### `class DadosError(RuntimeError)`

*linha 77*

Falha ao versionar um banco, já traduzida para o usuário.

### `class ArquivoOrigemError(DadosError)`

*linha 83*

O arquivo que você mandou registrar não serve — não existe, é uma pasta,
está vazio ou já está dentro do próprio projeto.

### `class VersaoDuplicadaError(DadosError)`

*linha 90*

O arquivo é byte a byte idêntico a uma versão já registrada.

Não é erro: é a resposta certa para "ele reenviou o mesmo arquivo". Sai com
código 0, como a pasta já existente da Fase 2, para não quebrar script.

#### `def __init__(self, mensagem, versao)`

*linha 98*

### `class DestinoOcupadoError(DadosError)`

*linha 103*

O nome calculado para a versão nova já existe no disco.

### `class PlanoDados`

*linha 110*

Tudo o que o `dados adicionar` faria, decidido e ainda não escrito.

Imutável, como o `Plano` da Fase 2, e pela mesma razão: entre a simulação e a
execução ninguém altera um caminho em trânsito. A árvore que aparece no
terminal é lida deste objeto, não de uma lista escrita à parte — é isso que
faz a simulação valer alguma coisa.

#### `def raiz(self)`

*linha 131*

#### `def tamanho_legivel(self)`

*linha 135*

### `class ResultadoDados`

*linha 140*

O que a execução de fato fez.

### `class ItemDaLinha`

*linha 151*

Uma versão registrada, confrontada com o que está de fato no disco.

- *linha 159* — `confere: bool | None` — None = não conferido, ou arquivo ausente

#### `def presente(self)`

*linha 162*

### `class LinhaDoTempo`

*linha 167*

A cronologia das versões, mais as divergências entre a ficha e o disco.

#### `def ausentes(self)`

*linha 178*

#### `def alterados(self)`

*linha 182*

#### `def integra(self)`

*linha 186*

### Caso de uso: adicionar uma versão

### `def preparar_adicao(root, identificador, caminho, agora, origem_rotulo)`

*linha 193*

Decide tudo o que a adição faria. Não escreve nada, não move nada.

Args:

    root: o `FLATCAP_ROOT`.
    identificador: `record_id` ou matrícula.
    caminho: o arquivo revisado, onde quer que ele esteja.
    agora: relógio injetável — sem ele os testes não teriam como comparar o
        nome do arquivo, que carrega a data.

Raises:

    ProjetoNaoEncontradoError, FichaAusenteError, FichaInvalidaError,
    ArquivoOrigemError, VersaoDuplicadaError, DestinoOcupadoError

### `def executar_adicao(plano)`

*linha 253*

Escreve o plano no disco. Não decide mais nada.

A ordem das operações não é arbitrária. A cópia do arquivo novo vem primeiro
porque é a etapa lenta e a que mais tem como falhar (espaço em disco, unidade
de rede, nuvem sincronizando). Se o processo morrer entre a cópia e a
rotação, o estado que fica no disco é "as duas versões estão em
`1. Dados originais/`" — nada foi perdido, e o `dados listar` mostra
exatamente isso. A ordem inversa deixaria a versão de trabalho já arquivada e
a nova ainda não escrita, que assusta muito mais ao abrir a pasta.

Quando dá para desfazer, desfaz: cada etapa registra como voltar atrás, e uma
falha no meio reverte o que já foi feito antes de propagar o erro.

*linha 280*

> 1. A versão nova, copiada (nunca movida: o arquivo do cliente continua
>    onde ele estava, na sua pasta de downloads ou no anexo do e-mail).

*linha 286*

> 2. Conferência do que foi escrito. Um `sha256` gravado na ficha sobre
>    uma cópia truncada seria um recibo falso — pior do que recibo nenhum.

*linha 299*

> 3. Rotação da versão anterior. Renomear dentro da mesma pasta de projeto
>    é operação de sistema de arquivos, instantânea e sem cópia.

*linha 306*

> 4. A ficha. Escrita atômica, dentro de `ficha.py`.

*linha 309*

> 5. O histórico. Última porque é a única etapa que, se falhar, não
>    invalida nada: o registro está na ficha, e a linha do histórico é
>    conveniência de leitura.

### Caso de uso: a linha do tempo

### `def linha_do_tempo(raiz, conferir)`

*linha 339*

Confronta a lista `dados:` da ficha com o que está de fato no disco.

Não basta imprimir a ficha. A ficha diz o que foi registrado; a pergunta do
critério de pronto — "dá para reconstruir a cronologia sem depender da minha
memória?" — só tem resposta se o que está registrado for confrontado com o
que existe. Três divergências aparecem aqui:

* **ausente**: a ficha registra um arquivo que não está mais no disco;
* **alterado**: o arquivo está lá, mas o `sha256` não é mais o registrado —
  alguém abriu e salvou por cima;
* **não registrado**: há arquivo na pasta que a ficha desconhece **e que
  poderia ser um banco** — ver `e_candidato_a_banco`.

A conferência de `sha256` é o padrão porque, nesta configuração, só o
`00_redcap_*` é somente-leitura: as versões revisadas continuam editáveis, e
a releitura do hash é o que transforma "editei sem querer" em algo visível.
Use `conferir=False` quando os bancos forem grandes e você só quiser a lista.

*linha 382*

> O que sobrou de `presentes` é o que a ficha não conhece — e nem tudo o que
> a ficha não conhece é banco. As duas pastas guardam outras coisas: o
> `Relatorio_*.docx` que o `flatcap relatorio` arquiva, um `.txt` de
> anotações. O filtro fica **aqui**, e não na varredura acima, porque a
> varredura também serve para encontrar as versões registradas: uma versão
> com nome fora da convenção precisa continuar sendo achada no disco, em vez
> de virar `ausente` por causa de um filtro.

### `def e_candidato_a_banco(caminho)`

*linha 403*

Este arquivo, achado na pasta de dados, poderia ser uma versão do banco?

A pergunta existe porque `2. Versões antigas/` deixou de guardar só banco: a
Fase 5 passou a arquivar lá a rodada anterior da descritiva e a Fase 6 o
relatório anterior. Sem este filtro, o `Relatorio_00742_2026-09-20.docx` que
o `flatcap relatorio` acabou de arquivar aparece no `flatcap dados listar`
como «arquivo que a ficha não conhece» — um alarme que o FlatCap dispara
contra si mesmo, e que ensina o usuário a ignorar a lista inteira.

Duas formas de responder que sim, e basta uma:

* **o nome segue a convenção** (`NN_`), que é como toda versão escrita pelo
  FlatCap se chama — inclusive uma que tenha perdido a extensão;
* **a extensão é a de um banco**, que é o caso da planilha que você largou
  na pasta à mão e ainda não registrou. É justamente o que a mensagem de
  `banco._mensagem_sem_versao` existe para apontar, e por isso ela não pode
  ser filtrada aqui.

### Backend

### `def _conferir_origem(caminho, raiz)`

*linha 432*

Recusa, com o motivo, tudo o que não pode virar versão.

### `def _hash_e_tamanho(caminho)`

*linha 470*

Calcula o `sha256` lendo o arquivo em blocos, e devolve o tamanho junto.

Ler em blocos e não de uma vez importa aqui e não importava na Fase 2: lá os
bytes já vinham inteiros da rede; aqui a origem é um arquivo em disco que
pode ter centenas de megabytes, e `read_bytes()` carregaria tudo na memória
de uma vez só para calcular um hash de 32 bytes.

### `def _recusar_duplicata(ficha, sha256)`

*linha 488*

### `def _proxima_sequencia(ficha, raiz)`

*linha 502*

O próximo número de versão: um a mais que o maior já usado.

O maior é procurado na ficha **e** no disco. Só na ficha seria suficiente se
nada além do FlatCap tocasse na pasta — e a premissa do projeto é a
contrária, a de que a pasta é sua e você mexe nela. Um arquivo `03_` que
exista no disco sem estar registrado precisa impedir que um novo `03_` seja
criado, senão dois arquivos diferentes carregariam o mesmo índice.

### `def _rotacoes(raiz)`

*linha 533*

Decide o que sai de `1. Dados originais/` e vai para `2. Versões antigas/`.

Só entram arquivos que seguem a convenção de nome (`NN_`) e cujo número não
é zero. As duas condições são deliberadas: o `00_redcap_*` é intocável por
regra, e um arquivo com nome fora da convenção — um `notas.txt`, um
`dicionario.csv` que você deixou ali — não é versão de banco e não deve ser
movido por um comando que o usuário chamou para outra coisa.

### `def _nome_da_versao(sequencia, nome_original, quando)`

*linha 567*

Monta `01_revisado_AAAA-MM-DD_<nome original>`.

O nome original é preservado e passa pela mesma `sanitizar` das pastas — ele
vem de fora, e o que vem de fora não monta caminho.

- *linha 575* — `base = Path(base).name` — segunda barreira contra `../` no nome

### `def _acao_do_historico(plano)`

*linha 579*

## `flatcap/painel.py`

`SPDX-FileCopyrightText: 2026 Matheus Fernandes` · `SPDX-License-Identifier: GPL-3.0-or-later`

*176 linhas.*

O painel do `flatcap status`: os projetos que já têm pasta, com o status e o prazo.

O `flatcap listar` responde "o que chegou?" a partir do REDCap, e procura a pasta de
cada solicitação. Este módulo responde outra pergunta — "como está cada projeto, e qual
passou do prazo?" — e faz o caminho inverso: parte do disco, ficha por ficha, e não
fala com o REDCap. É o que deixa o painel de pé quando o servidor cai ou o token
expira, e o que mantém no painel a pasta cuja matrícula foi corrigida no REDCap depois
de ela existir.

### O que entra

Toda pasta `Projeto NNN` do `FLATCAP_ROOT` com um `projeto.yaml` que abre, menos as
`finalizado`: essas saem do painel e entram só na contagem. A ficha que não abre e a
pasta de cliente no formato anterior à 1.1.0 também ficam de fora, mas não em
silêncio — o painel as lista, para o terminal dizer o que fazer com elas. A ordem é a
do `flatcap listar`, pelo `record_id`.

### O status e o prazo

Os dois saem da ficha, como estão escritos. O status é um dos do `projeto.STATUS`,
reconhecido pelo `ficha.status_reconhecido` sem distinguir maiúscula, acento ou `_`. O
que não é nenhum deles aparece como está escrito, marcado: escondê-lo seria esconder
justamente o projeto que precisa de atenção.

O prazo é a data final, escrita à mão depois da reunião e lida pelo
`ficha.data_escrita`. Quando a data passa e o projeto não está `pronto`, ele está
atrasado: o prazo é o do relatório, e o projeto pronto já o tem. O dia do prazo ainda
não é atraso. A data de hoje vem de `agora=`, como em todo `preparar*`, porque um teste
que lê o relógio quebra à meia-noite.

### O que este módulo não faz

Não escreve nada e não decide status nenhum: quem escreve o `status:` é você, o
`flatcap novo` (`não iniciado`) e o `flatcap relatorio` (`pronto`). E monta dados, e não
texto: o painel é uma lista de `LinhaDoPainel`, com o prazo como data e o atraso como
um sim ou não. A CLI as desenha, e uma interface gráfica pode ordenar, filtrar e abrir
a pasta de cada uma sem ler a tabela do terminal.

### `class LinhaDoPainel`

*linha 54*

Um projeto no painel: o que vai para cada coluna, ainda como dado.

- *linha 59* — `pasta: Path` — a pasta do projeto: `.../00742 - José Antônio de Sá/Projeto 006`

*linha 62*

> O nome da ficha, e não o da pasta: o da pasta passou pela limpeza dos caracteres
> que o Windows recusa, e o da ficha é o que o REDCap trouxe, com a sua correção.

*linha 65*

> Um dos do `projeto.STATUS`, na grafia de lá; ou, quando não é nenhum deles, o
> que está escrito na ficha — e aí `status_reconhecido` é falso.

*linha 70*

> O `prazo:` como está escrito, quando ele não é uma data — `semana que vem`. Vazio
> quando é uma data, e quando não há prazo nenhum.

#### `def pasta_local(self)`

*linha 76*

`Projeto 006` — a coluna "Pasta local" do `flatcap listar`.

#### `def sem_prazo(self)`

*linha 83*

### `class Painel`

*linha 88*

O painel inteiro, decidido. É daqui que sai a tabela do `flatcap status`.

- *linha 96* — `ilegiveis: tuple[Path, ...] = ()` — as pastas de projeto cuja ficha não abre

- *linha 97* — `antigas: tuple[Path, ...] = ()` — as pastas de cliente no formato anterior à 1.1.0

#### `def atrasados(self)`

*linha 100*

#### `def sem_prazo(self)`

*linha 104*

#### `def status_fora_da_lista(self)`

*linha 108*

#### `def prazos_que_nao_sao_data(self)`

*linha 112*

### `def montar_painel(root, agora)`

*linha 116*

Lê todas as fichas do `FLATCAP_ROOT` e monta o painel. Não escreve nada.

Args:

    root: o `FLATCAP_ROOT`.
    agora: relógio injetável — é ele que diz o que está atrasado.

### `def _ordem(linha)`

*linha 159*

A ordem do `flatcap listar`: pelo `record_id`, como número — o `6` antes do `41`.

O `record_id` que não é número (nenhum REDCap comum gera um, mas o campo é texto)
vai para o fim, em ordem alfabética. A pasta desempata: dois projetos com o mesmo
`record_id` são pasta duplicada, e saem um embaixo do outro.

## `flatcap/banco.py`

`SPDX-FileCopyrightText: 2026 Matheus Fernandes` · `SPDX-License-Identifier: GPL-3.0-or-later`

*907 linhas.*

Abrir o banco de dados de um projeto.

Três fases diferentes precisam da mesma resposta para a mesma pergunta — *qual
arquivo é o banco deste projeto, agora?*. A Fase 4 diagnostica, a Fase 5 analisa
e a Fase 6 relata, e todas as três abrem o mesmo arquivo. Se cada uma decidisse
por conta própria, bastaria uma discordância para a descritiva ser feita sobre
uma versão e o relatório sobre outra — divergência que ninguém percebe, porque
os dois documentos saem bonitos.

Por isso a resposta mora aqui, sozinha, e as camadas de cima recebem um `Banco`
já aberto.

### O que este módulo decide

**Qual versão.** A vigente é a de maior número de sequência registrada em
`dados:` — a revisada quando existe, e o `00_redcap_*` enquanto ela não chegar.
A busca é pela ficha, não pela pasta: um arquivo largado à mão em
`1. Dados originais/` não vira banco por estar lá.

**Se dá para confiar nela.** A conferência reusa `dados.linha_do_tempo`, que é
onde a Fase 3 já respondia "este arquivo ainda é o que foi registrado?". Não há
uma segunda leitura de `sha256` neste módulo de propósito: duas implementações
da mesma conferência é como um comando passa a dizer "confere" enquanto o outro
diz "ALTERADO" sobre o mesmo arquivo.

    * **ausente** — a ficha registra e o disco não tem: recusa. Não há o que
      perfilar, e prosseguir produziria um relatório sobre um arquivo que não
      existe.
    * **alterado** — está lá com conteúdo diferente do registrado: abre, avisa
      e o aviso viaja dentro do `Banco` até o `perfil.md`. É diagnóstico, e
      diagnóstico não bloqueia; mas fica escrito no documento que você leva para
      a reunião que o banco perfilado não é o que a ficha descreve.

**Como ler.** `.xlsx` e `.csv`, que é o que o cliente manda. Formato fora dessa
lista é recusado com o que fazer — e não com o estouro do `pandas`.

### O que este módulo deliberadamente não faz

Não conserta nada. Vírgula decimal, número guardado como texto e data escrita à
mão continuam exatamente como estão no arquivo: quem lê passando `decimal=","`
não vê o problema, e o problema é justamente o produto da Fase 4. A leitura é
fiel ao que o cliente mandou, e é o `perfil.py` que aponta o que está torto.

**A exceção é o nome da coluna**, desde a 1.14.1. O espaço nas pontas (`Idade `) e
a quebra de linha do Alt+Enter do Excel (`Peso` e `(kg)` em duas linhas) não são
um dado que o cliente mandou: são acidentes do cabeçalho, invisíveis na tela, e
cada um quebrava uma coisa diferente. O espaço travava o projeto num laço entre o
`perfil` e a descritiva; a quebra de linha partia o comentário das tabelas, e o
relatório saía com tabelas de uma coluna só. O leitor tira o espaço das pontas e
troca a quebra por um espaço — `Idade`, `Peso (kg)` —, e o que ele trocou viaja na
`Leitura` até o `perfil.md`. Um nome que ficaria igual ao de outra coluna fica como
veio: renomear seria juntar duas variáveis, e o `perfil` já denuncia a colisão.

**E a vírgula decimal de um `.csv` que não é separado por vírgula**, também desde a
1.14.1. É o formato que o Excel em português salva — `;` entre campos, `70,5` na
célula —, e nele a vírgula não é defeito: é a convenção do arquivo. Até a 1.14.0 o
leitor entregava a coluna como texto, o perfil mandava o cliente "corrigir" um
arquivo certo, e toda análise recusava a coluna. A razão é a mesma da exceção das
datas na descritiva: exigir do cliente o conserto de um formato que o Excel dele
sempre escreve é exigir o impossível. A conversão tem três condições que a mantêm
honesta. É **da coluna inteira ou de nada**: um valor que não seja número à
brasileira — `não sei`, `12.5`, `70,5 kg` — deixa a coluna como veio, e o perfil
aponta o que está torto como sempre apontou. Só vale **quando a vírgula não separa
campos**: num `.csv` com `,`, um `"70,5"` entre aspas é outra história, e fica
texto. E **fica escrita**: as colunas convertidas viajam na `Leitura` até o
cabeçalho do `perfil.md` e o manifesto de cada análise.

### `EXTENSOES_SUPORTADAS`

*linha 93*

> O nome por onde este módulo é conhecido desde a Fase 4. A lista desceu para o
> `projeto.py` porque o `dados.py` passou a precisar dela para saber o que, na
> pasta, é candidato a versão do banco — e ele não pode importar este módulo.

### `_CONVERSAO`

*linha 98*

> Formato que aparece na prática, que a gente reconhece e mesmo assim não abre.
> A mensagem diz o que fazer, porque "formato não suportado" sozinho não ajuda
> ninguém que acabou de receber o arquivo do cliente.

### `FORMATOS_DATA`

*linha 121*

> Os formatos de data escritos à mão, na ordem em que são testados. Moram aqui, e
> não em quem os usa, porque este é o módulo que sabe como o arquivo do cliente
> chega — e porque a Fase 4, que denuncia a data escrita como texto, e a Fase 5,
> que precisa convertê-la para descrever o período, têm de dar exatamente a mesma
> resposta. Duas listas de formatos é como um comando lê `03/04` como 3 de abril
> e o outro como 4 de março.

- *linha 139* — `PROPORCAO_PARA_AFIRMAR = 0.9` — a partir daqui dá para afirmar "a coluna é isto"

### `class BancoError(RuntimeError)`

*linha 142*

Falha ao abrir o banco, já traduzida para o usuário.

Erro próprio pelo mesmo motivo de `ConfigError`, `RedcapError`, `ProjetoError`
e `FichaError`: a CLI captura esta classe e transforma em painel. Qualquer
outra exceção é bug de verdade e deve subir com o traceback inteiro.

### `class BancoNaoRegistradoError(BancoError)`

*linha 152*

O projeto existe, mas nenhuma versão do banco foi registrada na ficha.

### `class BancoAusenteError(BancoError)`

*linha 158*

A ficha registra a versão vigente e ela não está no disco.

### `class FormatoNaoSuportadoError(BancoError)`

*linha 164*

O arquivo existe e o FlatCap não abre esse formato.

### `class BancoIlegivelError(BancoError)`

*linha 170*

O formato é suportado, mas o arquivo não abriu — corrompido, protegido por
senha, ou não é o que a extensão diz.

### `class BancoVazioError(BancoError)`

*linha 177*

O arquivo abriu e não tem linha nenhuma, ou não tem coluna nenhuma.

### `class AbaInexistenteError(BancoError)`

*linha 183*

A planilha pedida em `--aba` não existe na pasta de trabalho.

### `class Leitura`

*linha 190*

Como o arquivo foi lido. Vai inteiro para o cabeçalho do `perfil.md`.

Registrar a planilha, o separador e a codificação não é preciosismo: são as
três decisões que o leitor tomou sozinho, e a única forma de descobrir que
ele tomou a errada é vê-las escritas. Um `perfil.md` de 800 linhas gerado a
partir da aba "Dicionário" em vez da aba "Dados" parece perfeitamente
normal até alguém reparar no cabeçalho.

- *linha 206* — `avisos: tuple[str, ...] = ()` — o que o leitor teve de relevar para abrir

*linha 207*

> Os nomes de coluna que o leitor limpou, como `(antes, depois)`. Ver o fim da
> docstring do módulo e o `nome_de_coluna`.

*linha 210*

> As colunas lidas com vírgula decimal. Ver o fim da docstring do módulo.

#### `def formato(self)`

*linha 214*

#### `def outras_abas(self)`

*linha 218*

#### `def descrever(self)`

*linha 221*

Uma linha dizendo de onde os dados vieram, com o que for pertinente.

### `class Banco`

*linha 239*

O banco aberto, com a procedência junto.

O `quadro` é o único objeto mutável que circula pelo FlatCap, e é assim
porque um `DataFrame` copiado a cada camada custa memória à toa. As camadas
de cima leem e não escrevem.

#### `def linhas(self)`

*linha 255*

#### `def colunas(self)`

*linha 259*

#### `def tamanho_legivel(self)`

*linha 263*

### `def caminho_da_versao(raiz, versao)`

*linha 267*

Onde está, no disco, o arquivo de uma versão registrada.

*No módulo, linha 278:*

> `versao_vigente` desceu para o `ficha.py` na Fase 6 e continua acessível daqui
> como `banco.versao_vigente`, porque é deste módulo que os chamadores a importam
> desde a Fase 4. O motivo da mudança de casa está na docstring dela: responder
> "qual versão vale?" é ler a ficha, e o `relatorio.py` precisa dessa resposta sem
> carregar o `pandas`. Mesma manobra que a Fase 5 fez com `formato_de_data`, na
> direção contrária.

### `def abrir(raiz, aba, conferir)`

*linha 286*

Abre a versão vigente do banco de um projeto.

Args:

    raiz: a pasta do projeto (a que tem o `projeto.yaml`).
    aba: nome da planilha, para `.xlsx` com mais de uma. Sem isso, a primeira.
    conferir: reler o `sha256` e comparar com o registrado.

Raises:

    FichaAusenteError, FichaInvalidaError: a ficha do projeto não abre.
    BancoNaoRegistradoError: nenhuma versão em `dados:`.
    BancoAusenteError: a versão vigente não está no disco.
    FormatoNaoSuportadoError, BancoIlegivelError, BancoVazioError,
    AbaInexistenteError.

### `def abrir_arquivo(caminho, aba)`

*linha 349*

Lê um arquivo solto, sem passar pela ficha. Devolve o quadro e como ele foi lido.

### `_QUEBRA_NO_NOME`

*linha 384*

> A quebra de linha dentro de um nome de coluna, com os espaços em volta dela: o
> `\n` do Alt+Enter, o `\r\n` que alguns exportadores deixam, e os separadores de
> linha que o `str.splitlines` também reconhece — os que chegam colando do Word.

### `def nome_de_coluna(nome)`

*linha 390*

O nome de uma coluna como o FlatCap o usa: numa linha só e sem espaço nas pontas.

`"Idade "` vira `Idade`; `"Peso\n(kg)"` vira `Peso (kg)`. O espaço de dentro do
nome fica: `pressão sistólica` é o nome que o cliente escolheu.

### `def _limpar_nomes(quadro)`

*linha 400*

Aplica o `nome_de_coluna` ao cabeçalho, no lugar, e devolve o que mudou.

Três casos ficam como vieram: o nome que não é texto (o `2023` de um cabeçalho
do Excel), o que ficaria vazio (um cabeçalho que é só um espaço, que o `perfil`
denuncia como coluna sem nome), e o que ficaria igual ao de outra coluna — `Sexo`
e `Sexo ` são duas colunas no arquivo, e renomear a segunda juntaria as duas
numa variável só. Essa colisão é o `cabecalho_repetido` do `perfil`.

*No módulo, linha 430:*

> Um número escrito à brasileira, inteiro numa célula: `70,5`, `-0,25`, `1.234,56`,
> `1,5E-05` — e o inteiro `70`, que divide a coluna com eles. O ponto só vale como
> separador de milhar, em grupos de três: `12.5` não casa, e a coluna fica como veio.

### `def _ler_virgula_decimal(quadro, separador)`

*linha 436*

Converte, no lugar, as colunas de texto que são inteiras números com vírgula
decimal, e devolve os nomes delas. Ver o fim da docstring do módulo.

Só num `.csv` cujo separador não é a vírgula — no `.xlsx` o número já vem número,
e um `"22,5"` lá é uma célula de texto, que o perfil denuncia. A coluna precisa
ter pelo menos uma vírgula, e todo valor preenchido precisa casar com
`_NUMERO_PT_BR`; se um só não casa, nada muda.

### `def _numero_pt_br(texto)`

*linha 474*

### Leitura por formato

### `def _ler_xlsx(caminho, aba)`

*linha 481*

Lê uma planilha. Sem `--aba`, lê a primeira e diz quais ficaram de fora.

Ler a primeira é uma escolha, não a única possível: dava para chutar a de
mais células, ou a que se chama "dados". Ficou a primeira porque é
determinística e explicável — o aviso sobre as outras abas é o que impede
que a escolha passe despercebida, e isso vale mais do que acertar sozinho na
maioria das vezes e errar em silêncio no resto.

O `except Exception` aqui é deliberado, e é a única exceção à regra da casa de
que exceção não prevista é bug e deve subir com o traceback. Um arquivo
corrompido, protegido por senha ou com a extensão trocada estoura em lugares
diferentes de duas bibliotecas de terceiros — `BadZipFile`, `KeyError`,
`InvalidFileException`, `struct.error` —, e a lista não é fechada nem
documentada. O que interessa a quem acabou de receber o arquivo do cliente é
sempre a mesma frase, e não o nome da exceção. O `try` cobre só as duas
chamadas de leitura, para que bug daqui de dentro continue subindo inteiro.

- *linha 512* — `except AbaInexistenteError:` — noqa: BLE001 - ver a justificativa acima

### `def _ler_csv(caminho)`

*linha 518*

Lê um `.csv` descobrindo a codificação e o separador.

Um `.csv` exportado do Excel em português vem com `;` e em cp1252. Um `.csv`
exportado do R ou do Python vem com `,` e em UTF-8. Os dois chegam aqui com a
mesma extensão e nenhuma marca que os distinga, então ou o leitor descobre,
ou metade dos arquivos abre como uma coluna só de texto — o que produziria um
perfil perfeitamente formatado e completamente errado.

A ordem das codificações importa: UTF-8 primeiro porque é a única que **falha**
quando o palpite está errado (byte inválido estoura), o que a torna um teste de
verdade. `latin-1` fica por último porque decodifica qualquer byte sem
reclamar: tentada antes, aceitaria um arquivo UTF-8 e devolveria "JosÃ©".

- *linha 541* — `avis` — O `pandas` avisa por `warnings` que perdeu campo, e um `warning` impresso

- *linha 542* — `try:` — no meio da saída de um comando é um recado que o usuário aprende a

*linha 543*

> ignorar. Capturado aqui, ele vira um aviso do FlatCap e viaja até o
> `perfil.md` e o manifesto da descritiva, junto do resto.

- *linha 551* — `sep=separador,` — tolera linha com número de campos diferente do cabeçalho

*linha 553*

> Sem isto, uma linha com mais campos do que o cabeçalho faz o
> `pandas` promover a primeira coluna a índice — e a tabela inteira
> anda uma casa para a esquerda sem que nada avise. Melhor perder o
> campo sobrando, que fica avisado, do que deslocar tudo em silêncio.

- *linha 572* — `"Download interromp` — noqa: BLE001 - mesma justificativa do `.xlsx`

### `def _decodificar(bruto)`

*linha 583*

Descobre a codificação da amostra. Devolve o nome e o texto decodificado.

A amostra é um prefixo de 64 KiB cortado num byte qualquer, e é aí que mora
a armadilha: quando o corte cai **dentro** de um caractere de dois bytes, o
UTF-8 estrito falha na sequência truncada — e a falha é justamente o teste
que decide a codificação. O palpite caía em cp1252 e o arquivo inteiro era
lido em cp1252, entregando `SÃ£o Paulo` à tabela, ao `dicionario.csv` e ao
documento do cliente.

Recuar até a última linha inteira remove a única fonte de falso negativo
sem enfraquecer o teste: um `.csv` é feito de linhas, e nenhum caractere
atravessa um `\n`.

- *linha 605* — `for nome` — `strict` de propósito: o erro é o que descarta o palpite.

### `def _confirmar_no_arquivo_inteiro(conteudo, codificacao)`

*linha 613*

Confirma no arquivo inteiro a codificação que a amostra escolheu.

A amostra decide pelos primeiros 64 KiB. Num `.csv` do Excel em cp1252 cujo
primeiro acento só aparece depois deles — um banco grande de códigos, com o
`Não` numa coluna de observação lá embaixo —, o UTF-8 passa no teste da
amostra sem ter sido testado de verdade, e o `pandas` estourava no meio da
leitura: "não consegui abrir" sobre um arquivo que abre no Excel. O arquivo já
está na memória, e decodificá-lo inteiro custa uma passada.

Só o palpite que pode estar errado é conferido: com BOM, o arquivo se declarou
UTF-8; `latin-1` aceita qualquer byte.

### `def _ate_a_ultima_linha(bruto)`

*linha 638*

O prefixo cortado no último `\n`, ou ele inteiro se não houver nenhum.

Arquivo de uma linha só — cabeçalho sem dados, ou um `.csv` menor que a
amostra e sem quebra final — devolve o que veio: não há o que recuar, e
encurtar até zero seria pior do que arriscar o corte.

### `def _separador(amostra)`

*linha 650*

Descobre o separador pela primeira linha não vazia.

O `csv.Sniffer` tem a primeira palavra porque entende aspas. Quando ele se
recusa a decidir, a contagem no cabeçalho resolve.

O caso que sobra é o cabeçalho **sem separador nenhum** — um arquivo de uma
coluna só. Cair em `,` ali é o que quebrava: um `.csv` de uma coluna com
`peso` no cabeçalho e `70,5` nas linhas era partido em duas colunas, e o
`pandas`, vendo mais campos do que nomes, promovia a primeira metade a índice
em silêncio. O que chegava à análise era a coluna `peso` valendo 5, 2, 0 — e
nada na saída denunciava. Então, quando o cabeçalho não tem separador, o
escolhido é um que também não apareça no resto da amostra: o arquivo tem uma
coluna, e é assim que ele é lido.

### Mensagens

### `def _item_da_versao(itens, versao)`

*linha 692*

### `def _mensagem_sem_versao(nao_registrados)`

*linha 699*

O projeto existe e o banco não. Duas situações diferentes, dois caminhos.

### `def _mensagem_formato(caminho)`

*linha 719*

### `def formato_de_data(textos, proporcao)`

*linha 741*

Descobre se uma coluna de texto é uma data escrita à mão, e em que formato.

Devolve o formato e quantos valores ele explica; `(None, 0)` quando nenhum
formato explica a coluna inteira.

Testa um formato por vez, explícito, em vez de deixar o `pandas` adivinhar: o
palpite dele aceita formatos misturados na mesma coluna e inverte dia com mês
sem avisar. Para a Fase 4 isso é o detector `data_como_texto`; para a Fase 5 é
a diferença entre converter uma coluna e inventar datas — e por isso a
exigência é que **um único** formato explique a coluna quase toda. Coluna com
dois formatos misturados não é convertida por ninguém: é devolvida como
indecidível, que é o que ela é.

*No módulo, linha 774:*

> Como um valor do banco se escreve como texto
>
> Mora aqui pelo mesmo motivo dos `FORMATOS_DATA`: o perfil, que propõe as
> categorias do `dicionario.csv`, e as análises, que as conferem contra o banco,
> têm de escrever o mesmo valor do mesmo jeito. Até a 1.13.0 a escrita das
> análises morava na descritiva e o perfil fazia a dele com `str()`: numa coluna
> de código com uma célula vazia — que o `pandas` lê como `float64` —, o perfil
> propunha `1.0|2.0`, a dica mandava escrever `1.0=Feminino`, e a descritiva, que
> escreve `1`, saía com `Feminino 0` e `1 15` na mesma tabela.

*No módulo, linha 785:*

> As casas de sempre, e o teto das que uma variável de escala pequena pode ganhar.

### `def casas_do_resumo(resumo, minimo)`

*linha 790*

Quantas casas decimais mostram uma variável numérica: as `minimo` de sempre, ou
mais quando a escala dela é pequena demais para elas.

Até a 1.14.0 as estatísticas saíam sempre com duas casas, e uma concentração na
casa de 0,003 virava `0` no resumo inteiro — mínimo, quartis, média e desvio —,
as faixas saíam `[0 a 0)`, e a comparação imprimia "média 0 (0)" nos dois grupos
e "diferença 0,00 (0,00 a 0,00)" ao lado de um p < 0,001.

A escala é o menor entre o desvio padrão e a mediana, em valor absoluto — os dois
que precisam aparecer: o desvio, para os números da tabela não saírem todos
iguais, e a mediana, para o valor típico não sair zero. Enquanto ela for de 0,01
para cima, as duas casas de sempre já a mostram, e nada muda — idade, peso, IMC e
altura em metros continuam como sempre saíram. Abaixo disso, a variável ganha as
casas que mostram dois algarismos da escala: 0,0006 pede cinco.

`resumo` é o do `descritiva.resumo_numerico` e do `perfil`, com `desvio`,
`mediana`, `minimo` e `maximo`; com desvio e mediana zerados, vale o maior valor
em módulo. Todas as estatísticas de uma variável saem com as mesmas casas, e por
isso a conta é por variável, e não por número.

#### `def modulo(chave)`

*linha 815*

*linha 823*

> Um desvio de 1e-17 numa coluna de valores iguais é resto de ponto flutuante, e
> não escala: contado, ele pediria doze casas para mostrar `0,3`.

### `def texto_de_numero(valor, casas)`

*linha 841*

Número no formato brasileiro, sem separador de milhar e sem zero à toa.

É a conta do `descritiva.numero`, que desceu para cá junto com a
`serie_de_texto`: as duas escrevem o mesmo número, e uma conta só é o que
impede o `0,5` da tabela de virar `0.5` no dicionário.

### `def serie_de_texto(serie)`

*linha 861*

Os valores preenchidos como texto, do jeito que eles devem aparecer na tabela.

Um código lido como número (`1`, `2`) viraria `"1.0"` e `"2.0"` num
`astype(str)` cru — e código como categórica é justamente o que o perfil
sugere para essas colunas. Lógico vira Sim/Não, e data vira `dd/mm/aaaa`:
os dois são o que se escreve em uma tabela em português, e o dicionário é
quem decidiu que a coluna é categórica.

Pública desde a 1.4.0, quando morava no `descritiva.py`, que continua a
exportá-la com o mesmo nome. O `cruzamento.py` escreve a mesma categoria na
tabela dele, e uma segunda conversão é como o `1` da tabela de frequência
vira `1.0` no cruzamento da página seguinte — o `1.0` que o `pd.crosstab`
imprime quando a coluna de código tem uma célula vazia. Desceu para cá na
1.13.1, para o perfil propor as categorias com a mesma escrita.

### `def _mensagem_ilegivel(caminho, erro)`

*linha 897*

## `flatcap/dicionario.py`

`SPDX-FileCopyrightText: 2026 Matheus Fernandes` · `SPDX-License-Identifier: GPL-3.0-or-later`

*889 linhas.*

O `dicionario.csv` — a decisão da reunião, escrita em um arquivo.

É a decisão de arquitetura nº 2 do roteiro: "esta variável é categórica, aquela é
numérica, esta eu ignoro, aquelas faixas são estas" é decisão sua, tomada com o
cliente na frente. Mas ela não pode ficar só na sua cabeça nem espalhada em
condicionais dentro do script. Aqui ela vira uma tabela, e a partir da Fase 5 a
automação inteira obedece a essa tabela.

Três coisas ao mesmo tempo: a **entrada** que dirige a descritiva, a
**documentação** do que foi combinado, e o **ponto de ajuste** quando o cliente
pedir mudança — reagrupar categorias vira editar uma célula, não caçar código.

### A regra que manda em tudo aqui: a automação propõe, você decide

O `flatcap perfil` roda mais de uma vez no mesmo projeto — antes da reunião, e de
novo quando o cliente mandar o banco revisado. Entre uma vez e outra, você
preencheu o arquivo. Então a segunda passada **funde**, e a fusão tem uma regra
só:

    Linha que já existe no arquivo não é tocada. Nunca. Nem um campo.

Variável nova do banco entra no fim com a sugestão automática; variável que sumiu
do banco **continua no arquivo**, marcada em `no_banco`, porque apagá-la jogaria
fora a decisão que você tomou na reunião — e o cliente que removeu uma coluna
sem avisar costuma devolvê-la na versão seguinte.

É a mesma regra do `acrescentar_versao` da Fase 3: alterar a ficha sem destruir o
que o usuário escreveu.

### Formato

Seis colunas. As cinco primeiras são as do roteiro; `no_banco` é do FlatCap.

    variavel           o nome exato da coluna no banco. É a chave.
    rotulo             como a variável aparece nas tabelas e no relatório.
    tipo               categorica | numerica | data | ignorar
    categorias_ordem   a ordem das categorias, separadas por `|`, e o rótulo de
                       cada uma depois de um `=` quando a coluna for de código
    faixas             os cortes das faixas etárias e afins, separados por `|`
    no_banco           sim | nao — recalculado a cada perfil; não é decisão sua

**Colunas a mais que você acrescentar são preservadas.** Se você criar uma coluna
`nota` para anotar o que foi combinado sobre cada variável, ela volta intacta na
gravação seguinte, na mesma posição.

#### O rótulo de cada categoria, e por que ele mora dentro do `categorias_ordem`

Metade dos bancos chega com a categórica codificada: `sexo` vale `1` e `2`, e o
que cada um quer dizer está na cabeça do cliente. Até a 1.2.0 não havia onde
escrever isso, e a tabela, o gráfico e o documento saíam com `1` e `2` — a lacuna
mais visível da ferramenta para quem lê o relatório.

    sexo;Sexo;categorica;1=Feminino|2=Masculino;;sim
    escolaridade;Escolaridade;categorica;Fundamental|Médio|Superior;;sim

A regra é uma linha: **`codigo=rótulo` quando houver `=`; sem `=`, o valor é o
próprio rótulo.** A segunda linha acima é um dicionário de antes desta versão, e
continua valendo sem mudar um caractere — a fusão nunca toca linha preenchida,
então o rótulo entra quando você chegar nele, e não há migração.

Dentro da mesma célula, e **não** em uma sétima coluna. Uma sétima coluna ligaria
`1|2` a `Feminino|Masculino` pela posição, e reordenar uma sem a outra poria
`Feminino` em cima da contagem de `2` — sem erro, sem aviso, e conferível só
lendo o banco. Na mesma célula o desalinhamento é impossível: a ordem e o rótulo
são a mesma decisão, tomada de uma vez, na frente do cliente.

**Os rótulos não vêm do REDCap.** O `DataDictionary.xlsx` descreve o formulário
de solicitação, não o banco do cliente — que chega como anexo e não tem
dicionário nenhum. Eles são digitados por você, na reunião, olhando a tabela
"Valores observados" do `perfil.md`, que existe exatamente para essa pergunta.

#### Por que `;` entre campos e `|` dentro das listas

O roteiro escreve `Feminino;Masculino` em `categorias_ordem`, e isso pressupõe
que o separador de campos seja a vírgula. Só que este arquivo é editado no Excel
em português, onde o separador de listas do sistema é `;` — um `.csv` com vírgula
aberto com dois cliques cai todo em uma coluna só. Um arquivo que você precisa
editar em toda reunião não pode abrir errado.

Com `;` entre campos, o `;` dentro da lista precisaria de aspas, e um arquivo cujo
significado depende de aspas digitadas à mão é um arquivo que quebra na primeira
edição em bloco de notas. Daí `|` dentro das listas, que não aparece em nome de
categoria de banco de saúde nenhum.

A leitura é tolerante e a escrita é estrita: na leitura, o separador de campos é
descoberto (`;` ou `,`) e o `;` só vale dentro das listas **quando não for o
separador de campos daquele arquivo**; na gravação, sempre `;` e `|`. Assim um
arquivo salvo por outra ferramenta continua abrindo, e o arquivo que o FlatCap
escreve é sempre o mesmo.

A ressalva do `;` é o conserto de um round-trip quebrado. Com `;` entre campos, o
`csv.writer` grava `Alta; a pedido` entre aspas — corretamente, e a categoria é
uma só. A leitura, aceitando `;` dentro da lista, devolvia duas: `Alta` e
`a pedido`. O arquivo voltava do disco diferente do que tinha sido gravado, que é
exatamente o que a fusão existe para impedir.

### `SEPARADOR_ROTULO`

*linha 133*

> Entre o valor que está no banco e o texto que sai na tabela:
> `categorias_ordem = 1=Feminino|2=Masculino`.
>
> Dentro da mesma célula do `categorias_ordem`, e não em uma sétima coluna. A
> justificativa inteira está em `_categorias`, e o resumo é que uma sétima coluna
> ligaria `1|2` a `Feminino|Masculino` **pela posição** — e reordenar uma sem a
> outra trocaria os rótulos no relatório sem erro nenhum.

### `_BOM`

*linha 143*

> O BOM vai no texto, e não na codificação da gravação, porque quem grava é o
> `escrever_atomico` do `ficha.py` — que existe para o `projeto.yaml` e escreve
> sempre em UTF-8. Com o caractere no começo da string, o arquivo sai com os
> mesmos bytes e a invariante "o texto é o arquivo" continua valendo, que é o que
> faz a simulação mostrar o que será gravado. É ele que faz o Excel em português
> abrir o arquivo em UTF-8 em vez de cp1252 — sem isso, `Condição` vira `CondiÃ§Ã£o`
> no arquivo que você mais edita à mão.

### `class DicionarioError(RuntimeError)`

*linha 174*

Falha ao ler ou escrever o `dicionario.csv`, já traduzida para o usuário.

### `class DicionarioInvalidoError(DicionarioError)`

*linha 180*

O arquivo existe e não dá para interpretar.

Recusar é deliberado. Um dicionário meio lido produziria uma descritiva com
metade das variáveis, e nada na saída denunciaria a metade que faltou.

#### `def __init__(self, mensagem, caminho)`

*linha 188*

### `class Linha`

*linha 194*

Uma variável no dicionário.

Imutável como todo dado que circula no FlatCap. A fusão não altera linha:
ela escolhe entre a que existe e a proposta, e a que existe sempre ganha.

*linha 205*

> Os **códigos**, na ordem, do jeito que eles aparecem no banco. É por eles
> que a descritiva casa a tabela com a coluna; o rótulo é outra coisa e mora
> logo abaixo.

*linha 212*

> `(código, rótulo)`, só para os códigos que ganharam um. Pares e não `dict`
> porque tudo o que circula no FlatCap é imutável, e um `dict` dentro de uma
> `dataclass` frozen é imutável só por educação.

#### `def analisavel(self)`

*linha 218*

Se esta variável entra na descritiva da Fase 5.

#### `def tem_rotulos(self)`

*linha 225*

#### `def rotulo_de(self, codigo)`

*linha 228*

Como esta categoria se escreve na tabela e no gráfico.

Cai no próprio código quando não há rótulo, e é isso que faz uma coluna
de texto (`Feminino|Masculino`) e uma coluna de código
(`1=Feminino|2=Masculino`) atravessarem o mesmo caminho: na primeira o
valor **é** o rótulo, e não há nada a resolver.

Quem chama não precisa saber qual das duas está lidando — que é a razão
de isto ser um método aqui e não um `if` em cada lugar que imprime.

*linha 242*

> `1=` (o `=` digitado e o rótulo esquecido) cai no código. O
> par continua guardado, porque é ele que permite à descritiva
> avisar que você começou a escrever e não terminou — e é ele
> que faz o arquivo voltar ao disco do jeito que você o deixou.

### `class Fusao`

*linha 251*

O resultado de cruzar o dicionário que existe com o que o banco mostra agora.

#### `def total(self)`

*linha 265*

#### `def mudou(self)`

*linha 269*

### Localização

### `def caminho_do_dicionario(raiz)`

*linha 276*

### Leitura

### `def ler(raiz)`

*linha 283*

Lê o `dicionario.csv` de um projeto. Devolve vazio quando o arquivo não existe.

Raises:

    DicionarioInvalidoError: cabeçalho irreconhecível, tipo fora da lista,
        variável repetida, faixas que não são números em ordem crescente, ou
        linha com mais campos do que o cabeçalho.

### `def ler_arquivo(caminho)`

*linha 298*

Lê um `dicionario.csv` a partir do caminho, sem passar pela pasta do projeto.

*linha 310*

> O nome não é aparado: ele é a chave que casa a linha com a coluna do banco,
> e o `perfil` o grava exatamente como a coluna se chama — `Idade `, com o
> espaço. Até a 1.14.0 a leitura aparava, a descritiva procurava `Idade`, o
> perfil acrescentava `Idade ` de novo, e o projeto entrava num laço sem
> saída. É a regra do `"Sim "` das categorias, aplicada ao nome.

### Fusão

### `def fundir(existentes, sugestoes)`

*linha 358*

Cruza o dicionário que já existe com o que o banco mostra agora.

Args:

    existentes: o que está no arquivo hoje. Vazio na primeira vez.
    sugestoes: uma por coluna do banco, na ordem em que elas aparecem lá.

A ordem de saída segue a ordem das colunas no banco, e as variáveis que não
estão mais no banco vão para o fim, na ordem em que estavam. Isso mantém o
arquivo lado a lado com a planilha na tela — e junta no rodapé o que já não
tem correspondência, em vez de deixar buracos no meio.

*linha 385*

> A linha que existe vence inteira; `no_banco` é o único campo que o
> FlatCap mantém, porque não é decisão de ninguém — é um fato do banco.

### Escrita

### `def texto_do_dicionario(linhas, colunas)`

*linha 411*

Monta o conteúdo do arquivo. Sem tocar no disco, para o `--sim` poder mostrá-lo.

### `def escrever(raiz, fusao)`

*linha 428*

Grava o `dicionario.csv`. Escrita atômica, pela mesma razão do `projeto.yaml`:
o arquivo guarda as decisões da reunião, e meio arquivo é pior do que nenhum.

### Backend: leitura

### `def _ler_texto(caminho)`

*linha 441*

Lê aceitando UTF-8 com e sem BOM, e cp1252 para o arquivo salvo pelo Excel.

### `def _tabela(texto, caminho)`

*linha 454*

Separa cabeçalho e registros, descobrindo o separador de campos.

Devolve o separador junto, e não só a tabela: quem lê uma célula de lista
precisa saber qual caractere já foi gasto para separar campos, senão volta a
partir `Alta; a pedido` em duas categorias. Ver `_lista`.

As linhas iniciadas por `#` **no começo do arquivo** são o cabeçalho explicativo
que o FlatCap escreve: são descartadas na leitura e reescritas na gravação.
Depois do cabeçalho das colunas, uma linha começada por `#` é uma variável —
`#`, `#id` e `# paciente` são nomes de coluna que existem em banco de verdade.
Até a 1.13.0 elas eram descartadas em qualquer lugar do arquivo: a variável
sumia do dicionário a cada leitura, o perfil a acrescentava de novo a cada
rodada, e a descritiva recusava o banco por uma coluna "que o dicionário não
conhece".

O número de cada registro é a **linha do arquivo**, contando o cabeçalho
explicativo — o que o editor de texto e o Excel mostram. Até a 1.13.0 era a
posição depois dos comentários, e "linhas 2 e 4" eram as linhas 17 e 19.

- *linha 495* — `except StopIteration:` — pragma: no cover - `conteudo` não vazio garante uma linha

*linha 509*

> `line_num` conta as linhas físicas que o leitor já consumiu, e um campo
> entre aspas pode atravessar mais de uma; somado ao que foi pulado, é a
> linha do arquivo em que o registro termina.

### `def linhas_de_comentario(linhas)`

*linha 525*

Quantas linhas do começo são cabeçalho explicativo: as começadas por `#` e as
vazias, até a primeira que não é nenhuma das duas.

Só o começo, e é essa a regra inteira. O FlatCap escreve os comentários dos
seus `.csv` — este dicionário e as tabelas das análises — sempre antes do
cabeçalho das colunas, e depois dele o `#` no início de uma linha é dado: a
coluna `#` de um banco, a categoria `#N/D` que o Excel deixa numa célula com
erro de fórmula. Pública porque o `relatorio.ler_tabela` lê as tabelas das
análises com a mesma regra — duas regras para o mesmo formato é como uma
categoria some do documento e continua no `.csv`.

### `def _separador_de_campos(linhas)`

*linha 545*

`;` ou `,`. Decide pela linha de cabeçalho, que é a que tem os dois nomes fixos.

### `def _normalizar_nome(nome)`

*linha 553*

`Categorias_Ordem` e `categorias ordem` são a mesma coluna. O arquivo é editado
no Excel, e o Excel ajuda a mudar maiúscula sem que ninguém peça.

### `def _sem_acento(texto)`

*linha 562*

### `def _tipo(valor, variavel, numero, caminho)`

*linha 567*

Aceita `Categórica`, `CATEGORICA` e `categorica`; recusa o resto, dizendo o que vale.

### `def _lista(valor, separador_de_campos, aparar)`

*linha 590*

Quebra `Feminino|Masculino` — e também `Feminino;Masculino`, que é o que o
roteiro escreve e o que sai quando o campo vem entre aspas de outra ferramenta.

#### O `;` só é separador de lista quando não é separador de campos

Aceitá-lo sempre quebrava o round-trip do arquivo que o próprio FlatCap
grava. Com `;` entre campos, uma categoria chamada `Alta; a pedido` sai do
`csv.writer` entre aspas, que é o certo — e voltava da leitura como duas
categorias, `Alta` e `a pedido`. O arquivo lido deixava de ser o arquivo
escrito, e a fusão, que nunca reescreve linha preenchida, gravava a divisão
de volta no disco.

Num arquivo separado por vírgula o `;` continua valendo dentro da lista: lá
ele não é ambíguo, e é o que o roteiro escreve.

#### `aparar` — e por que a categoria não é aparada

`faixas` são números, e `  18` é o mesmo corte que `18`: ali o espaço é
digitação. Uma categoria não: `"Sim "` e `"Sim"` são duas contagens
diferentes no banco — é o que o detector `espaco_sobrando` do `perfil.py`
denuncia —, e aparar a declarada fazia a linha do relatório sair com `n = 0`
justamente na coluna suja que se estava tentando descrever.

O preço é conhecido e vale registrar: quem escrever `Sim | Não` por estética
declara as categorias `"Sim "` e `" Não"`, que não casam com o banco. A
descritiva avisa — `valor(es) no banco fora da ordem declarada` e
`categoria(s) do dicionário sem nenhum caso` —, e é um aviso que aponta para
a célula certa. O contrário não tem conserto: aparando, a categoria com
espaço fica impossível de declarar, e nada na saída diz por quê.

### `def _categorias(valor, variavel, numero, caminho, separador_de_campos)`

*linha 643*

Separa `1=Feminino|2=Masculino` no código e no rótulo de cada categoria.

Devolve `(códigos, pares)`. Os códigos são o que a descritiva compara com a
coluna do banco; os pares são o que ela imprime. Uma célula sem `=` devolve
os códigos e nenhum par — e é assim que um dicionário escrito antes desta
versão continua valendo sem mudar um caractere.

#### Por que o rótulo mora aqui, e não em uma sétima coluna

Foi a decisão de 17/09/2026, e o argumento é o desalinhamento. Uma sétima
coluna guardaria `1|2` numa célula e `Feminino|Masculino` na outra, ligadas
**pela posição** — e no dia em que alguém reordenasse uma e esquecesse a
outra, o relatório sairia com `Feminino` em cima da contagem de `2`. Sem erro,
sem aviso, e conferível só lendo o banco.

Na mesma célula isso é impossível por construção: a ordem e o rótulo são a
mesma decisão, tomada de uma vez, na frente do cliente.

#### A divisão é no primeiro `=`, e só nele

Mesma regra que o `modelo._opcoes` usa para a primeira vírgula dos rótulos do
REDCap, e pelo mesmo motivo: `1=Sim = confirmado` é um rótulo com `=` dentro,
não duas categorias. Partir em todos devolveria um rótulo cortado no meio.

#### O espaço é do valor, menos ao redor do `=`

Sem `=`, a parte inteira é o valor como ele está no banco, espaço e tudo:
`"Sim "` e `"Sim"` são duas colunas diferentes de uma tabela de frequência,
e o `espaco_sobrando` do `perfil.py` existe justamente para você poder
declarar a primeira. Com `=`, o sinal é a fronteira e o espaço ao redor dele
é digitação: `1 = Feminino` é o código `1`.

Raises:

    DicionarioInvalidoError: código repetido na mesma célula, ou `=` sem
        código antes dele.

### `def _faixas(valor, variavel, numero, caminho, separador_de_campos)`

*linha 732*

As faixas precisam ser números em ordem crescente, e é aqui que isso é conferido.

Conferir na leitura e não na Fase 5 é deliberado: o erro é de digitação, e o
momento de descobrir uma digitação errada é enquanto o arquivo está aberto na
sua frente — não daqui a duas semanas, no meio da geração das tabelas.

### `def _booleano(valor)`

*linha 775*

`no_banco` ausente vale `sim`: um dicionário escrito à mão, ou herdado de uma
versão anterior do formato, descreve variáveis que existem.

### `def _mensagem_campos_demais(caminho, numero, campos, valores)`

*linha 786*

### Backend: escrita

### `def _com_no_banco(linha, presente)`

*linha 804*

### `def _colunas_de(linhas)`

*linha 819*

As seis colunas do formato, mais as que o usuário tenha criado, na ordem em
que apareceram.

### `def _escrever_categoria(linha, codigo)`

*linha 832*

### `def _campo(linha, nome)`

*linha 839*

*linha 847*

> Remonta `codigo=rotulo` para os que têm rótulo, e devolve o código
> sozinho para os que não têm. É o que faz o arquivo voltar ao disco
> exatamente como você o deixou — a promessa do cabeçalho da ficha vale
> aqui também, e um `=` que some na primeira gravação é uma edição sua
> desfeita pelo programa.

*No módulo, linha 862:*

> Usado pelo `perfil.py` para montar a sugestão sem conhecer o formato do arquivo.

### `class Sugestao`

*linha 866*

O que a automação propõe para uma variável, antes de encontrar o que já existe.

Existe para que `perfil.py` não precise construir `Linha` diretamente: quem
propõe não deveria saber que o arquivo tem uma coluna `no_banco` nem que as
listas são separadas por `|`.

#### `def como_linha(self)`

*linha 881*

## `flatcap/perfil.py`

`SPDX-FileCopyrightText: 2026 Matheus Fernandes` · `SPDX-License-Identifier: GPL-3.0-or-later`

*1726 linhas.*

O perfil do banco — o que você leva para a reunião.

Responde ao passo 2c do fluxo: abrir o banco com o cliente e apontar os ajustes
necessários. A diferença que a fase faz é de dinâmica, não de tecnologia. Sem
ela, a reunião é rolar a planilha procurando problema ao vivo. Com ela, você
chega com a lista pronta — "há 12% de faltantes em `idade`, a coluna `peso` está
como texto, e `sexo` tem quatro grafias diferentes" — e o cliente sai sabendo
exatamente o que corrigir.

Segue o padrão das Fases 2 e 3, decidir e escrever separados:

    plano = preparar_perfil(root, identificador)   # abre o banco, diagnostica
    executar_perfil(plano)                         # só escreve

E, como a Fase 3, **não fala com o REDCap**. A pasta do projeto já tem tudo: a
ficha diz qual é a versão vigente, e o banco está em `1. Dados originais/`. Um
comando que só lê arquivo local não deve poder falhar por token expirado — há
teste que roda o `perfil` com token inválido de propósito.

### Dois produtos, um comando

**`perfil.md`** é para a reunião: um documento impresso, ordenado pelo que exige
decisão, com os valores observados de cada categórica e o resumo de cada
numérica — que é exatamente o que se precisa ter na frente para decidir a ordem
das categorias e os cortes das faixas.

**`dicionario.csv`** é para a máquina: a partir da Fase 5, a descritiva obedece a
ele e a nada mais. Sai preenchido com uma sugestão por variável, e a sugestão é
palpite — a coluna `tipo` existe para você corrigir. A automação propõe, você
decide.

### O que o diagnóstico não faz

Não conserta. Vírgula decimal continua vírgula decimal, número guardado como
texto continua texto. Duas razões: o arquivo é do cliente e a correção é dele —
consertar aqui deixaria a versão dele diferente da sua para sempre; e a Fase 3
já tem o lugar certo para uma versão corrigida entrar, que é o
`flatcap dados adicionar`, com número de sequência e `sha256`.

### Um módulo sem erro próprio

Todos os outros módulos do FlatCap declaram uma exceção própria — `ConfigError`,
`RedcapError`, `ProjetoError`, `FichaError`, `DadosError`, `BancoError`,
`DicionarioError` — que a CLI captura e transforma em painel. Este não declara
nenhuma, e a ausência é informação: **o perfil não tem como falhar por conta
própria**. Ou o projeto não abre (`FichaError`), ou o banco não abre
(`BancoError`), ou o dicionário que está lá não é interpretável
(`DicionarioError`). O que sobra aqui é contar, medir e formatar, e nada disso
recusa nada.

### Simula por padrão

Como o `novo` e o `dados adicionar`, e pelo mesmo motivo, que aqui é um só e é
específico: o `perfil.md` é um documento que você leva impresso para a reunião e
onde você **rabisca**. Regerá-lo apaga o rabisco. A simulação mostra o
diagnóstico inteiro na tela — nunca é uma rodada perdida — e diz quando o
`perfil.md` que está lá vai ser substituído, e de quando ele é.

### `CORRIGIR`

*linha 105*

> Gravidade de um achado. Não é "erro/aviso": é o que fazer com ele na reunião.

- *linha 106* — `CORRIGIR = "corrigir"` — o banco precisa mudar antes de a análise começar

- *linha 107* — `CONFIRMAR = "confirmar"` — é decisão do cliente, e ele precisa ser perguntado

- *linha 108* — `NOTA = "nota"` — fica registrado, não exige conversa

### `CODIGOS_VOLATEIS`

*linha 112*

> Os achados cujos valores **vão deixar de existir** quando o banco for
> corrigido. É um eixo diferente da gravidade, e confundir os dois foi um
> defeito real: `variacao_de_grafia` é `CONFIRMAR` (a decisão é do cliente) e
> mesmo assim as quatro grafias somem quando ele padroniza. Propor uma ordem de
> categorias sobre valores voláteis enche o `dicionario.csv` de linha para
> apagar — e, como a fusão nunca reescreve linha existente, elas ficam lá para
> sempre e reaparecem no relatório com `n = 0`.
>
> Todo achado de gravidade CORRIGIR entra aqui por definição. Os de CONFIRMAR
> entram um a um, e a lista é conferida por teste: um detector novo não pode
> ficar sem classificação.

### `CODIGOS_ESTAVEIS`

*linha 131*

> O outro lado da trava: os achados de `CONFIRMAR` cujos valores **continuam**
> existindo depois de o cliente decidir.
>
> A lista dos voláteis sozinha não classifica nada: «não está nela» é o estado
> de um detector deliberadamente estável e o de um detector que alguém esqueceu
> de classificar, e os dois são indistinguíveis. Com as duas listas, a pergunta
> passa a ter resposta — é o que `codigo_classificado` responde, e é o que o
> teste da trava estrutural pergunta.
>
> `categoria_sem_rotulo` é o caso que obrigou a escrever isto. Ele é `CONFIRMAR`
> e é estável de propósito: o que falta nessa coluna é uma decisão do cliente, e
> os valores não mudam quando ele a toma — rotular `1` como «Feminino» não apaga
> o `1` da coluna. Pô-lo entre os voláteis faria a ordem das categorias deixar de
> ser proposta justamente nas colunas que mais precisam dela.

### `def codigo_classificado(codigo)`

*linha 157*

Este detector já foi classificado em volátil ou estável?

Pública para o teste que trava a regra: um detector novo de gravidade
`CONFIRMAR` precisa entrar em uma das duas listas, e a escolha precisa ser
consciente — dela depende se a ordem das categorias é proposta ou não na
coluna que ele denuncia.

### `PROPORCAO_PARA_AFIRMAR`

*linha 174*

> Limiares. Todos aqui em cima, com nome, porque um número solto no meio de uma
> função é uma decisão que ninguém consegue rever depois.

- *linha 176* — `PROPORCAO_PARA_AFIRMAR = 0.9` — "esta coluna é número/data escrito como texto"

- *linha 177* — `LIMITE_CATEGORIAS = 25` — acima disso, a lista de valores não vai por extenso

- *linha 179* — `LIMITE_UNICOS_CODIGO = 10` — numérica inteira com até 10 valores: candidata a código

- *linha 180* — `LIMITE_VALOR_CODIGO = 20` — ...e valores pequenos: código é 0/1, 1/2, 1 a 5

- *linha 181* — `LIMITE_FALTANTES = 0.20` — a partir daqui, faltante vira assunto de reunião

- *linha 182* — `PROPORCAO_TEXTO_LIVRE = 0.90` — quase todo valor diferente: texto livre ou identificador

- *linha 183* — `MINIMO_PARA_HEURISTICA = 20` — abaixo disso, proporção não quer dizer nada

### `_formato_de_data`

*linha 228*

> A lista de formatos de data e a detecção passaram para `banco.py` na Fase 5: o
> detector `data_como_texto` daqui e a conversão que a descritiva faz precisam dar
> a mesma resposta, e duas listas é como uma delas deixa de receber a próxima
> correção. Ver a justificativa em `banco.formato_de_data`.

### `_NUMERO_PTBR`

*linha 234*

> `1.234,56` e `1234,56` — o jeito brasileiro.

### `_NUMERO_EN`

*linha 236*

> `1,234.56` e `1234.56` — o jeito que sai de ferramenta em inglês.

### `class Achado`

*linha 245*

Uma coisa observada no banco que exige atenção.

`exemplos` não é enfeite: "a coluna sexo tem quatro grafias" faz o cliente
procurar; "a coluna sexo tem F, f, Feminino e feminino " faz ele achar.

#### `def peso(self)`

*linha 261*

### `class Coluna`

*linha 266*

Uma variável do banco, já medida.

#### `def preenchidos(self)`

*linha 287*

#### `def proporcao_faltante(self)`

*linha 291*

#### `def resumo_numerico(self)`

*linha 295*

#### `def como_sugestao(self)`

*linha 298*

### `class Perfil`

*linha 308*

O banco inteiro, medido. É daqui que saem o `perfil.md` e o terminal.

#### `def raiz(self)`

*linha 326*

#### `def total_colunas(self)`

*linha 330*

#### `def tamanho_legivel(self)`

*linha 334*

#### `def por_gravidade(self, gravidade)`

*linha 337*

#### `def a_corrigir(self)`

*linha 341*

#### `def a_confirmar(self)`

*linha 345*

#### `def limpo(self)`

*linha 349*

### `class PlanoPerfil`

*linha 354*

Tudo o que o `perfil` faria, decidido e ainda não escrito.

O conteúdo dos dois arquivos já vem montado, como no `Plano` da Fase 2, para
que `executar_perfil` não decida mais nada — e para que a simulação mostre
exatamente o que seria gravado, e não uma aproximação.

#### `def raiz(self)`

*linha 372*

#### `def dicionario_existia(self)`

*linha 376*

### `class ResultadoPerfil`

*linha 381*

O que a execução de fato escreveu.

### Casos de uso

### `def preparar_perfil(raiz, aba, conferir, agora)`

*linha 393*

Abre a versão vigente do banco, diagnostica e monta os dois arquivos.

Não escreve nada. Não toca na rede.

Args:

    raiz: a pasta do projeto.
    aba: planilha do `.xlsx`, quando houver mais de uma.
    conferir: reler o `sha256` das versões e comparar com a ficha.
    agora: relógio injetável — sem ele os testes não teriam como comparar o
        cabeçalho do `perfil.md`, que carrega a data.

Raises:

    FichaError, BancoError, DicionarioInvalidoError

### `def executar_perfil(plano)`

*linha 437*

Escreve o `dicionario.csv` e o `perfil.md`. Não decide mais nada.

O dicionário vem primeiro porque é o arquivo que guarda decisão; o `perfil.md`
é um relatório e sempre pode ser regerado. Nenhum dos dois precisa de reversão
como a da Fase 3: os dois são idempotentes — a fusão preserva o que já existe
e o relatório descreve o que acabou de ser lido —, então rodar de novo depois
de uma falha no meio resolve, em vez de agravar.

### `def perfilar(banco, ficha, quando)`

*linha 466*

Mede o banco. Função pura: recebe o quadro aberto, devolve o diagnóstico.

Separada de `preparar_perfil` porque é o miolo testável — dá para jogar um
`DataFrame` montado à mão aqui dentro e afirmar sobre os achados, sem pasta de
projeto, sem ficha e sem disco.

*linha 477*

> `quadro.iloc[:, i]` e não `quadro[nome]`: nome repetido devolveria um
> `DataFrame` no lugar de uma coluna, e o perfil quebraria justamente no banco
> que mais precisa de diagnóstico.

### Perfil de uma coluna

### `def _perfilar_coluna(serie, nome, posicao, linhas)`

*linha 509*

*linha 535*

> A coluna que precisa de rótulo, e o momento em que se descobre que ela
> precisa.
>
> `_sugerir` acabou de propor `categorica` para uma coluna que o leitor trouxe
> como número — é a regra dos "inteiros pequenos que se repetem", e ela acerta
> em cheio no código de 0/1 e na escala de 1 a 5. São exatamente as colunas em
> que a tabela, o gráfico e o documento saem com `0` e `1` se ninguém escrever
> o que eles querem dizer.
>
> Sem este achado, a sintaxe `1=Feminino` fica documentada no cabeçalho do
> `dicionario.csv` e ninguém descobre que ela existe. É a simetria da Fase 4
> mais uma vez: o perfil propõe, você decide, a análise obedece.
>
> `CONFIRMAR` e em `CODIGOS_ESTAVEIS`, não em `CODIGOS_VOLATEIS`: o que falta
> aqui é uma decisão do cliente, e os valores não vão mudar quando ele a
> tomar — rotular `1` não apaga o `1` da coluna. Se entrasse entre os
> voláteis, a ordem das categorias deixaria de ser proposta justamente nas
> colunas que mais precisam dela.
> `unicos > 1` porque a coluna de um valor só já tem o achado dela
> (`coluna_constante`, que manda deixá-la fora das tabelas). Pedir um rótulo
> para ela seria mandar o usuário decidir o nome de uma categoria que não vai
> aparecer em lugar nenhum — e um detector que dispara onde não precisa é
> como a lista inteira passa a ser ignorada. Encontrado rodando.

### Detectores

### `def _achados_gerais(quadro, colunas, duplicadas, linhas, ajustados)`

*linha 618*

O que se vê olhando o banco inteiro, e não uma coluna de cada vez.

`ajustados` são os nomes de coluna que o leitor limpou (`banco.nome_de_coluna`):
o quadro já chega com o nome novo, e é por aqui que o antigo continua aparecendo
no checklist.

*linha 685*

> Os que o leitor limpou, com o nome de antes e o de agora; e os que ficaram como
> vieram porque a limpeza os faria colidir com outra coluna.

### `def _achados_numericos(nome, preenchidos)`

*linha 753*

O código de faltante disfarçado de número — 99, 999 — é o achado clássico.

### `def _achados_textuais(nome, textos)`

*linha 786*

Os detectores do roteiro que se aplicam a coluna de texto, mais os que
aparecem sempre junto com eles.

*linha 801*

> Num `.csv` separado por `;` a vírgula já é lida como decimal (`banco.py`),
> coluna inteira ou nada. Se a coluna chegou aqui como texto, o motivo
> costuma ser o valor que não é número, e é ele que precisa aparecer.

### `def _achados_de_preenchimento(nome, faltantes, linhas, unicos)`

*linha 916*

### `def _achados_mistos(nome, serie)`

*linha 969*

Tipos misturados na mesma coluna: número e texto convivendo.

A pergunta é quantas naturezas convivem na coluna, e quem responde é
`_tipos_de` — nunca o `dtype`. O `dtype` diz como o `pandas` guardou, o que
é outra coisa: no pandas 2 toda coluna de texto é `object`, no pandas 3 só
a que ele não conseguiu uniformizar. Perguntar pelo `dtype` acerta em uma
das duas versões e erra na outra, em silêncio.

### Sugestão de tipo

### `def _sugerir(nome, serie, textos, unicos, faltantes, linhas)`

*linha 1027*

A sugestão que vai para o `dicionario.csv`, e o motivo dela.

A ordem das regras é a decisão: a primeira que casa vence. O motivo viaja
junto porque uma sugestão sem justificativa não dá para conferir — e conferir
é literalmente o que se pede que você faça com este arquivo.

*linha 1054*

> Três testes, e os dois últimos são o que segura o palpite. Só "poucos
> valores distintos" classificaria como código toda coluna numérica de um
> banco de seis linhas. Os valores também precisam **se repetir**, e
> precisam ser **pequenos**: código é 0/1, 1/2, uma escala de 1 a 5 —
> nunca 27, 38, 61, que é a cara de uma idade em um banco pequeno.

### `def _categorias_sugeridas(tipo, categorias, unicos, achados)`

*linha 1101*

A ordem proposta para `categorias_ordem`: da mais frequente para a menos.

Coluna cujos valores vão mudar não recebe proposta nenhuma: `120` e
`não realizado` na mesma coluna, `Sim` e `sim ` contados em separado, são
exatamente os que vão deixar de existir quando o cliente corrigir. Propor
uma ordem sobre eles é encher o arquivo de linha para apagar.

O critério é `CODIGOS_VOLATEIS`, e **não** a gravidade. Os dois eixos se
parecem e não são o mesmo: `variacao_de_grafia` é `CONFIRMAR`, porque a
escolha de qual grafia vale é do cliente — e as outras três somem assim que
ele escolher. Barrar só por `CORRIGIR` deixava passar justamente o exemplo
que este parágrafo cita.

Frequência decrescente porque é a ordem em que uma tabela descritiva nominal
se lê. Escala ordinal — Fundamental, Médio, Superior — sai errada de
propósito: não há como adivinhar ordem de grandeza a partir dos dados, e uma
ordem errada que você corrige é melhor do que uma coluna em branco que você
precisa preencher do zero. Empate resolve em ordem alfabética, para que duas
execuções seguidas produzam o mesmo arquivo.

Fica em branco quando algum valor contém `|`, que é o separador da lista.

### Auxiliares de leitura da série

### `def _e_numerica(serie)`

*linha 1145*

### `def _e_data(serie)`

*linha 1151*

### `def _e_booleana(serie)`

*linha 1155*

### `def _tipos_de(serie)`

*linha 1159*

Quantos tipos de Python convivem na coluna. Um só, quase sempre.

### `def _tipo_lido(serie)`

*linha 1168*

Como o leitor entendeu a coluna, em português, para a tabela do perfil.

*linha 1173*

> Coluna sem nenhum valor chega como `float64` por convenção do pandas, e
> anunciá-la como "decimal" seria descrever a convenção, não o banco.

*linha 1182*

> `_tipos_de` e não `serie.dtype == object`: o dtype responde "como o pandas
> guardou isto", e a pergunta é "quantas naturezas convivem aqui". No pandas
> 2 toda coluna de texto é `object`, e a resposta pelo dtype marcava **todas**
> as categóricas do banco como `misto` — em vermelho, no documento que vai
> para a reunião. No pandas 3 o mesmo código acerta por acidente, porque
> texto puro passou a ter dtype `str`.

### `def _so_inteiros(preenchidos)`

*linha 1193*

### `def _textos(preenchidos)`

*linha 1204*

Os valores como texto, sem tirar espaço: o espaço sobrando é um dos achados.

### `def _exemplos(preenchidos)`

*linha 1213*

Alguns valores para reconhecer a coluna.

Número sai no formato brasileiro. Ele não veio de um texto — veio já como
número —, então não há fidelidade a preservar: `20.5` em um documento em
português ao lado de `20,5` na tabela do resumo é ruído, e ruído em um
documento que vai para a mesa da reunião custa uma pergunta.

### `def _contagem(preenchidos)`

*linha 1234*

Valores e quantas vezes cada um aparece, do mais frequente para o menos.

Empate em ordem alfabética, e não na ordem que o `value_counts` devolver: o
`dicionario.csv` é gerado a partir daqui, e um arquivo que muda de ordem
entre duas execuções idênticas é um arquivo que produz diff falso.

Os valores são escritos pela `serie_de_texto` do `banco.py`, a mesma das
análises: o que o perfil propõe em `categorias_ordem` é o que a descritiva
vai procurar no banco. Com `str()`, uma coluna de código com uma célula
vazia — `float64` para o `pandas` — saía como `1.0|2.0`, e a dica do
`categoria_sem_rotulo` ensinava a escrever `1.0=Feminino`, um rótulo que a
tabela nunca encontrava.

### `def _resumo_numerico(preenchidos)`

*linha 1254*

- *linha 1259* — `except (TypeError, ValueError):` — pragma: no cover - dtype numérico sempre converte

### Auxiliares de texto

### `def _e_numero(texto)`

*linha 1275*

### `def _variacoes_de_grafia(textos)`

*linha 1282*

Agrupa valores que só diferem em acento, caixa ou espaço.

### `def _chave(texto)`

*linha 1298*

A forma canônica de um texto: sem acento, sem caixa, sem espaço sobrando.

### `def _parece_identificador(nome)`

*linha 1307*

### `def _nomes_repetidos(nomes)`

*linha 1312*

Nomes de coluna que colidem, das duas formas em que isso acontece.

A primeira é o leitor já ter resolvido por conta própria: duas colunas
`sexo` chegam como `sexo` e `sexo.1`, e o `.1` é a única pista de que houve
colisão. A segunda é a colisão que só existe para quem lê: `Sexo` e `sexo `
são nomes diferentes para o `pandas` e a mesma variável para o cliente.

### `def _encurtar(texto, limite)`

*linha 1342*

### `def _porcentagem(fracao)`

*linha 1347*

### `def _numero(valor, casas)`

*linha 1351*

Número no formato brasileiro, sem zero à toa: `52,5` e não `52,50`.

Com as casas da coluna (`banco.casas_do_resumo`): duas, ou mais quando a escala
dela é pequena. Até a 1.14.0 eram sempre duas, e uma concentração na casa de
0,003 aparecia na reunião como `0 · 0,01` nos exemplos e `0` no resumo.

### O perfil.md

### `def texto_do_perfil(perfil, fusao)`

*linha 1373*

Monta o `perfil.md` inteiro. Sem tocar no disco, para o `--sim` mostrá-lo.

### `def _md_cabecalho(perfil)`

*linha 1389*

*linha 1391*

> `rotulo_do_projeto` e não `raiz.name`: desde a 1.1.0 o nome da pasta é
> `Projeto 006`, que não identifica ninguém — e este título encabeça o
> documento impresso que vai para a mesa da reunião.

### `def _md_avisos(perfil)`

*linha 1435*

### `def _md_checklist(perfil)`

*linha 1445*

A parte que existe para ser lida em voz alta na reunião.

Vem antes das tabelas de propósito: é o que exige decisão. As tabelas são
consulta, e consulta se procura quando precisa.

*linha 1475*

> Mais folgado do que na tabela: aqui o exemplo é o que faz o
> cliente encontrar o valor na planilha, e cortado pela metade
> ele deixa de servir para isso.

### `def _md_variaveis(perfil)`

*linha 1485*

### `def _md_categoricas(perfil, fusao)`

*linha 1523*

Os valores observados de cada categórica, que é o que se olha para preencher
`categorias_ordem`.

**É esta a tabela que se aponta na reunião para perguntar "o que é 1 e o que
é 2?".** Por isso ela ganhou a coluna `rótulo`: quando o dicionário já
responde, a resposta aparece do lado do valor, e a conferência com o cliente
vira ler a tabela em voz alta. Enquanto ele não responde, a coluna não existe
— uma coluna vazia em toda linha seria ruído em um documento impresso.

### `def _md_numericas(perfil)`

*linha 1592*

O resumo de cada numérica, que é o que se olha para decidir as faixas.

### `def _md_dicionario(perfil, fusao)`

*linha 1625*

### `def _celula(texto)`

*linha 1675*

Um valor do banco dentro de uma célula de tabela markdown.

A barra vertical é o separador de coluna: um valor que a contenha parte a
linha em duas e desalinha a tabela inteira. É o mesmo cuidado que o `cli.py`
toma com colchete e o `rich`.

### `def _geracao_anterior(caminho)`

*linha 1686*

Quando o `perfil.md` que está no disco foi gerado.

Serve para a simulação dizer *o que* vai ser substituído, e não só que algo
será. Um `perfil.md` de hoje de manhã é uma coisa; um de três semanas atrás,
com as suas anotações da reunião, é outra.

### `def _acao_do_historico(plano)`

*linha 1711*

## `flatcap/manifesto.py`

`SPDX-FileCopyrightText: 2026 Matheus Fernandes` · `SPDX-License-Identifier: GPL-3.0-or-later`

*657 linhas.*

O `manifesto.json` — o índice de uma rodada de análise, e o contrato entre uma
análise e quem escreve os arquivos dela.

O roteiro é direto sobre por que ele existe: *"o manifesto é o que torna a Fase 6
simples. Sem ele, o gerador de relatório teria que adivinhar arquivos por nome; com
ele, apenas percorre uma lista ordenada."* Este módulo é esse formato, e só ele.

Três coisas ele responde, e nenhuma delas é adivinhável a partir da pasta:

**De qual variável saiu cada arquivo.** `freq_idade_anos.csv` pode ter vindo de
`Idade (anos)` ou de `idade_anos` — os dois dão o mesmo pedaço de nome, e o
desempate é um sufixo numérico. Só o manifesto sabe qual é qual.

**Sobre qual banco.** Arquivo, `sha256` e integridade, para que a pergunta "esse
37% saiu de qual versão?" tenha resposta sem depender de memória.

**Com quais versões de biblioteca.** É o pedido do roteiro, com a justificativa
dele: no dia em que um gráfico sair diferente do que saía antes, isto é o que
responde se mudaram os dados ou mudou o `matplotlib`.

### O que a Fase 7 acrescentou aqui, e por quê

Até a Fase 6 havia uma análise só, e o manifesto podia falar dela sem se nomear.
Com a segunda, três coisas mudaram de casa para cá:

**`Manifesto.analise` — de qual análise é esta rodada.** Uma pasta
`3. Análises/normalidade/` com um manifesto que não diz o que é seria um arquivo
que depende do nome da pasta para ser interpretado — e nome de pasta é o que o
usuário renomeia. Manifesto antigo, sem o campo, é lido como `descritiva`: era o
que ele era.

**`ItemDoManifesto.colunas` — quais colunas do banco o item usou.** O campo
`variavel` é singular, e existe análise que não é de uma variável: uma correlação
é um par, e uma tabela de normalidade fala de todas de uma vez. Sem este campo, a
conferência `dicionario_mudou` do `relatorio.py` compararia `idade × imc` com as
variáveis do dicionário, não acharia, e diria «`idade × imc` saiu da descritiva» —
em todo relatório, para sempre. Com ele, a conferência compara a **união das
colunas** de todas as rodadas, e a pergunta volta a ter resposta.

**`Tabela` e `Grafico` — o contrato de saída de qualquer análise.** Eles moravam
no `descritiva.py`, que importa o `pandas`. Ou cada análise nova importava de lá,
acoplando duas análises que não têm nada a ver uma com a outra, ou os dois
desciam para um lugar neutro. Este módulo é o lugar: ele já era dono do
`Artefato`, e continua sem importar `pandas` nem `matplotlib`. O `descritiva.py`
reexporta os dois nomes, então nenhum chamador mudou.

### Por que este módulo não importa o `pandas` nem o `matplotlib`

Pela mesma razão que o `dicionario.py` não importa o `pandas`: o formato de um
arquivo de índice não depende de como o banco foi lido nem de como o gráfico foi
desenhado. A Fase 6 importa este módulo para montar o `.docx` e não precisa de
nenhum dos dois — nem de meio segundo de partida para descobrir. Há teste em
subprocesso que falha se qualquer um dos dois for carregado pelo `relatorio.py`.

O `dicionario.py` entrou como import novo e **não fere essa invariante**: ele
existe justamente por não importar `pandas`. Ele é quem sabe que o separador de
campos é `;` e que o arquivo abre com BOM — e a `Tabela`, que agora mora aqui,
precisa dos dois para escrever o `.csv`.

Ele também **não escreve no disco**. Monta o texto; quem grava é cada análise,
com a escrita atômica do `ficha.py`. É a mesma invariante das outras fases: o texto
é o arquivo, e por isso a simulação pode mostrá-lo inteiro antes de existir.

### O número de formato

`"formato": 1` na primeira chave. Custa uma linha e compra a única coisa que um
arquivo lido por outra versão do programa precisa: a possibilidade de ser recusado
com uma frase em vez de interpretado errado em silêncio.

**Ele continua em 1 depois da Fase 7, e isso é decisão, não esquecimento.** O
número existe para impedir interpretação errada, e os dois campos novos não
produzem nenhuma: uma versão anterior lendo um manifesto de descritiva escrito
hoje encontra exatamente os campos que ela conhece, ignora `analise` e `colunas`,
e monta o mesmo documento. Subir para 2 recusaria esse arquivo sem que houvesse o
que recusar. O número sobe no dia em que um campo **mudar de significado** — não
quando um campo novo aparecer.

### `ANALISE_DESCRITIVA`

*linha 99*

> O nome da análise de cada rodada. Vive aqui, e não em cada módulo, porque é o
> valor que o `relatorio.py` vai casar com a lista `analises:` da ficha — e duas
> grafias para a mesma análise é como uma rodada deixa de aparecer no documento
> sem que nada diga por quê.

### `ANALISE_AMOSTRAGEM`

*linha 110*

> A amostragem também escreve um manifesto, e se declara nele — mas não é uma análise
> de `3. Análises/`. Ela mora em `4. Amostragem/` e tem o relatório dela, e por isso
> não entra na `ORDEM_PADRAO_DAS_ANALISES` de baixo nem no `analises.REGISTRO`: o
> relatório das análises varre só `3. Análises/`, e nunca a vê.

### `ORDEM_PADRAO_DAS_ANALISES`

*linha 116*

> A ordem em que as análises aparecem no documento quando a ficha não manda.
>
> A lista `analises:` do `projeto.yaml` tem a primeira palavra — é o que foi
> combinado na reunião, e o relatório obedece. Esta é a ordem de quem não
> escreveu nada lá: a descritiva primeiro, porque é ela que apresenta cada
> variável, e os pressupostos depois, porque falam de variáveis já apresentadas.
> Rodada que não estiver nem na ficha nem aqui entra no fim, em ordem
> alfabética — determinística, e visivelmente no fim, que é o lugar certo para
> uma análise que ninguém disse onde queria.
>
> O cruzamento entra logo depois da descritiva, e não no fim nem em ordem
> alfabética — que o poria antes dela. Sem teste, ele ainda é descrição: são as
> mesmas categóricas da descritiva, duas de cada vez, e se lê melhor junto delas
> do que depois dos pressupostos das numéricas.
>
> A associação vem logo depois do cruzamento: ela testa os pares de categóricas
> que o cruzamento acabou de mostrar, e não depende da normalidade — categórica
> não tem normalidade a testar. Os pressupostos das numéricas ficam depois dela,
> perto dos testes que vão precisar deles.
>
> A correlação vem logo depois da normalidade: é o primeiro teste que precisa dos
> pressupostos das numéricas, e é na tabela de normalidade que o leitor acabou de
> ver a forma das variáveis que ela vai cruzar.
>
> A comparação vem no fim, depois da correlação. Ela também precisa dos
> pressupostos, e poderia vir antes; no fim, a posição não mexe no raciocínio
> escrito para nenhuma das outras — e a lista `analises:` da ficha manda de
> qualquer jeito quando o cliente for ler as comparações primeiro.
>
> Uma análise nova acrescenta uma linha aqui e nada mais. É o mesmo tipo de
> registro que o `_FORMAS` do `graficos.py`, e existe pelo mesmo motivo: com
> `if/elif` espalhado, a análise nova aparece no documento em um lugar que
> ninguém escolheu.

### `SEMENTE`

*linha 158*

> A semente.
>
> Ela mora aqui desde a Fase 7, e não no `descritiva.py` onde nasceu, pelo mesmo
> motivo de sempre: é um valor que **todo** manifesto registra, e um segundo
> módulo com uma segunda semente é como duas rodadas do mesmo projeto deixam de
> ser reproduzíveis uma contra a outra. Uma descritiva não sorteia nada e uma
> tabela de normalidade também não; quem vai precisar dela é o bootstrap e o
> teste de permutação, e quando precisarem ela já está escrita em todo manifesto
> já gerado. O `descritiva.py` reexporta o nome.

### `_BOM`

*linha 169*

> O BOM, o mesmo do `dicionario.csv` e pela mesma razão: é ele que faz o Excel em
> português abrir o arquivo em UTF-8 em vez de cp1252.

### `class ManifestoError(RuntimeError)`

*linha 174*

Falha ao ler o `manifesto.json`, já traduzida para o usuário.

### `class ManifestoInvalidoError(ManifestoError)`

*linha 180*

O arquivo existe e não dá para interpretar — ou é de um formato mais novo.

#### `def __init__(self, mensagem, caminho)`

*linha 185*

### O contrato de saída de uma análise

### `class Tabela`

*linha 194*

Uma tabela pronta para virar `.csv`. Texto, não `DataFrame`.

O conteúdo já vem montado como linhas de texto para que o `executar` de cada
análise não decida mais nada e para que a simulação mostre exatamente o que
seria gravado — a mesma invariante do `texto_do_dicionario` da Fase 4: o texto
é o arquivo.

Mora aqui desde a Fase 7. Era do `descritiva.py`, e uma análise nova que
quisesse escrever um `.csv` teria de importar do módulo da descritiva — o que
acoplaria duas análises que não têm nada a ver uma com a outra, e faria a
segunda pagar o `pandas` só para conhecer uma `dataclass` de texto.

#### `def texto(self)`

*linha 217*

O arquivo inteiro, com o cabeçalho explicativo em linhas de comentário.

O comentário existe para o dia em que alguém abrir `freq_sexo.csv` sozinho,
fora de qualquer contexto, e precisar saber de qual variável e de qual
denominador ele fala.

Uma tabela que fala de várias variáveis — a de normalidade é a primeira —
deixa `variavel` vazia, e a linha `# variável:` simplesmente não sai. O
`relatorio.ler_tabela` já descarta essa linha na leitura, então os dois
casos chegam iguais ao documento.

**Cada comentário ocupa uma linha só**, e a quebra de linha que vier no meio
dele vira espaço. O título leva o rótulo do dicionário e as notas levam
categorias do banco, e qualquer um dos dois pode trazer uma quebra — o
Alt+Enter numa célula do Excel, um texto colado do Word. Até a 1.14.0 a
segunda metade saía numa linha sem `#`, e o relatório a lia como o cabeçalho
da tabela: o `.docx` saía com uma tabela de uma coluna, com `# variável:`
dentro, e sem aviso nenhum. O corpo da tabela não precisa disso: o `csv` põe
entre aspas a célula que tem quebra, e a leitura a devolve inteira.

*No módulo, linha 257:*

> Toda quebra de linha, com os espaços em volta dela: o `\n`, o `\r\n`, e os
> separadores que o `str.splitlines` também reconhece — o `\x0b` e o ` ` que
> chegam colando do Word. A mesma lista do `banco.nome_de_coluna`, que este módulo
> não importa: o `banco.py` carrega o `pandas`, e este não pode.

### `def _uma_linha(texto)`

*linha 264*

O texto de um comentário numa linha só: a quebra e o espaço em volta viram um espaço.

### `class Grafico`

*linha 270*

Um gráfico decidido e ainda não desenhado.

Carrega os números já calculados — as contagens das barras, as bordas e as
alturas do histograma, os pontos do Q-Q —, e não a coluna do banco. Duas
consequências: o `graficos.py` não recalcula nada (e por isso não pode
discordar da tabela ao lado), e o plano não segura o banco inteiro na memória
por variável.

Os campos são a união do que cada espécie precisa, e cada uma usa os seus:
`categorias`/`valores`/`rotulos` nas barras e nas colunas, `bordas`/`contagens`
no histograma, `pontos_x`/`pontos_y`/`reta` no Q-Q, e `pontos_x`/`pontos_y`/
`contagens` na dispersão — onde `contagens` é quantos casos caem em cada ponto,
que é a mesma pergunta que ela responde no histograma: quantos casos há ali.
Uma `dataclass` por espécie daria um despacho por tipo no `graficos.py`, que é
mais código para dizer o que o campo `especie` já diz.

- *linha 290* — `"""` — barras | histograma | colunas | qq | dispersao

*linha 301*

> O Q-Q da Fase 7. `reta` é (intercepto, inclinação) — a reta de referência,
> calculada por quem sabe estatística e não por quem desenha.

### O índice da rodada

### `class Artefato`

*linha 312*

Um arquivo escrito por uma análise.

`especie` é o que o `relatorio.py` usa para decidir onde ele entra no
documento: uma `frequencia` vira tabela, um `histograma` vira figura. É por
isso que ela é um campo próprio e não uma dedução a partir da extensão.

#### `def e_tabela(self)`

*linha 327*

#### `def e_figura(self)`

*linha 331*

### `class ItemDoManifesto`

*linha 336*

Uma seção da rodada, com os arquivos que ela gerou.

Era "uma variável descrita", e a Fase 7 alargou o conceito sem mudar o campo:
na descritiva um item continua sendo uma variável, e em uma análise que fala de
várias — ou de um par — ele é **uma seção do documento**. `variavel` fica vazia
nesse caso, `rotulo` é o que encabeça a seção, e `colunas` diz quais colunas do
banco entraram.

`colunas` é o campo que faz as conferências do relatório continuarem
funcionando com mais de uma análise; ver a nota no topo do módulo. Item antigo,
sem o campo, devolve a própria `variavel` — que é o que ele sempre quis dizer.

#### `def preenchidos(self)`

*linha 363*

#### `def colunas_usadas(self)`

*linha 367*

As colunas do banco que este item usou.

Cai na `variavel` quando `colunas` está vazia, que é o caso de todo
manifesto escrito antes da Fase 7. É o que permite ao `relatorio.py`
fazer uma pergunta só — "quais colunas esta rodada usou?" — sem saber de
qual versão do FlatCap o arquivo veio.

#### `def artefato(self, especie)`

*linha 380*

### `class Manifesto`

*linha 388*

Uma rodada inteira de uma análise.

A ordem de `itens` é a ordem das variáveis no dicionário, que por sua vez é a
ordem das colunas no banco. Ela é o sumário da seção no relatório — e é por
isso que reordenar o `dicionario.csv` reordena o documento, sem tocar em código.

`analise` tem default para que um `Manifesto` montado à mão em teste antigo
continue válido, e para que o arquivo escrito antes da Fase 7 seja lido como o
que ele era.

#### `def total_artefatos(self)`

*linha 415*

#### `def tabelas(self)`

*linha 419*

#### `def figuras(self)`

*linha 423*

#### `def colunas_usadas(self)`

*linha 427*

Todas as colunas do banco que esta rodada tocou, sem repetir e em ordem.

É o que a conferência `dicionario_mudou` do relatório precisa perguntar
quando há mais de uma rodada na pasta: "as colunas de que esta rodada fala
ainda são analisáveis no dicionário de hoje?".

#### `def item(self, variavel)`

*linha 442*

#### `def por_tipo(self, tipo)`

*linha 448*

#### `def como_dicionario(self)`

*linha 451*

A forma serializável, na ordem em que ela sai no arquivo.

`analise` vem logo depois de `formato` de propósito: as duas primeiras
linhas do arquivo respondem "que arquivo é este?" e "do que ele fala?",
que são as duas perguntas de quem o abre sem contexto.

### Escrita

### `def texto_do_manifesto(manifesto)`

*linha 500*

O conteúdo do arquivo. Sem tocar no disco, para o `--sim` poder mostrá-lo.

`ensure_ascii=False` porque o arquivo tem nome de variável e rótulo em
português, e `\u00e7` no lugar de `ç` transforma um índice legível em um
despejo de máquina. Indentado de dois porque ele é lido por gente — quem lê
por programa não se importa.

### Leitura

### `def ler(caminho)`

*linha 518*

Lê o `manifesto.json` de uma rodada.

Raises:

    ManifestoInvalidoError: o arquivo não existe, não é JSON, ou é de um
        formato mais novo do que esta versão do FlatCap conhece.

### `def de_dicionario(corpo, caminho)`

*linha 556*

Converte o JSON já decodificado em `Manifesto`.

*linha 604*

> Manifesto escrito antes da Fase 7 não tem o campo, e era de uma

- *linha 605* — `retu` — descritiva: era a única análise que existia.

### `def _data_e_hora(valor, caminho)`

*linha 622*

## `flatcap/graficos.py`

`SPDX-FileCopyrightText: 2026 Matheus Fernandes` · `SPDX-License-Identifier: GPL-3.0-or-later`

*576 linhas.*

Os `.png` das análises: as barras, os histogramas e as colunas da descritiva, o
Q-Q da normalidade e a dispersão da correlação.

Este módulo **desenha e não calcula**. Ele recebe um `Grafico` com as contagens já
prontas — as barras já contadas, as classes do histograma já cortadas — e o
transforma em imagem. A divisão não é organização: é o que impede o gráfico de
discordar da tabela ao lado dele. Se o desenho recontasse, bastaria uma diferença
de arredondamento para o `.png` dizer 37 e o `.csv` dizer 38 sobre a mesma coisa,
e ninguém confere gráfico contra tabela.

É também o único módulo do pacote que importa o `matplotlib`, e por isso ele é
importado **de dentro** do `executar_*` de cada análise que desenha, e não no
topo do módulo dela.
Meio segundo de partida é o preço da biblioteca de desenho, e `--sem-graficos`
existe para não pagá-lo. Mesma decisão que a Fase 4 tomou com o `pandas` na CLI.

Não declara erro próprio, como o `perfil.py`: o que pode falhar aqui é escrita em
disco, que é `OSError`, e quem sabe o que fazer com ela é o `executar_*` que o
chamou — que desfaz a rodada inteira.

### As decisões de desenho

Uma figura que vai para um `.docx` impresso não tem tooltip, não tem hover e não
tem modo escuro. Isso muda o que é certo:

**Uma cor só, e ela não significa nada.** Toda barra da mesma cor. Colorir cada
barra de um tom diferente codificaria o tamanho da barra duas vezes — no
comprimento e na cor —, gastando o único canal livre para repetir o que o gráfico
já mostra. A cor é a de identidade nº 1 de uma paleta conferida para daltonismo,
e como há uma série só não há legenda: o título diz o que está plotado.

**O valor fica escrito na barra.** A regra geral é rotular pouco e deixar o eixo
carregar o resto; ela pressupõe que exista um tooltip para consultar o número
exato. Aqui não existe: o leitor tem o papel na mão. Então a categórica sai com
`n (%)` em cada barra e **sem eixo de valores** — o eixo seria a mesma informação
uma segunda vez. No histograma, onde as barras são muitas, é o contrário: eixo e
grade, e nenhum rótulo.

**O faltante não vira barra.** O gráfico mostra como se distribui quem respondeu;
quantos não responderam é o subtítulo (`n = 240 · 12 sem informação`) e uma linha
da tabela. Uma barra "sem informação" no meio das categorias faz o leitor comparar
proporções com denominadores diferentes.

**Grade e eixos discretos, marcas finas, texto em tinta.** Barra fina com ar entre
elas em vez de bloco grosso; grade sólida de um passo acima do fundo, nunca
tracejada; e nenhum texto na cor da série — rótulo e valor são tinta, a identidade
vem da barra ao lado deles.

### Este módulo desenha para qualquer análise, e nunca escolhe a pasta

Vale dizer em voz alta porque parece o contrário: o `desenhar` recebe o **caminho
como parâmetro**, e sempre recebeu. Quem decidia `3. Análises/descritiva/` era o
`executar_descritiva`, não este arquivo. A normalidade passa
`3. Análises/normalidade/qq_idade.png` e nada aqui muda por causa disso — foi a
divisão da Fase 5 pagando antes de a conta chegar.

O que a Fase 7 mudou foram duas coisas, e nenhuma é a pasta.

**As espécies `qq` e `dispersao`**, para as figuras que acompanham a normalidade e
a correlação.

**O despacho virou um registro, e espécie desconhecida estoura.** Antes era um
`if/elif/else` com `_colunas` no fim, o que significava que uma espécie nova
escrita com um typo saía como **gráfico de colunas** — bonito e errado, e ninguém
confere figura contra manifesto. Com uma análise só isso era conveniência; com
três é o defeito silencioso que este projeto passa o tempo caçando. Estourar é o
comportamento certo: espécie desconhecida é bug de programação, não engano do
usuário, e a regra da casa manda bug subir com o traceback inteiro — que é também
por que este módulo continua sem erro próprio.

### `matplotlib.use("Agg")`

*linha 83*

> `Agg` antes de qualquer outro import do matplotlib: sem isso a biblioteca
> procura um servidor gráfico, que não existe em terminal nem em servidor, e o
> comando morre por um motivo que não tem nada a ver com estatística.

### `FONTE`

*linha 88*

> A fonte dos gráficos.
>
> Arial primeiro, e a ordem é a correção: a lista anterior começava por
> `DejaVu Sans`, que vem dentro do próprio matplotlib e por isso está **sempre**
> instalado — o Arial nunca chegava a ser tentado. O resultado era um relatório
> com o texto em uma fonte e as figuras em outra, sem nada no código dizendo que
> a escolha tinha sido essa.
>
> Os três nomes do meio são rede, na ordem em que fazem sentido: `Liberation
> Sans` tem as mesmas métricas do Arial e é o que existe em Linux, `Helvetica`
> cobre o macOS, e o `DejaVu Sans` fecha a lista porque não desenhar é pior do
> que desenhar com outra fonte.

### `APARENCIA`

*linha 102*

> A configuração de aparência mora aqui em cima, com a paleta, onde se acha sem
> procurar — mas ela **não** é escrita no `rcParams` global, e essa é a correção.
>
> `rcParams` é estado do processo inteiro. Escrevê-lo no import fazia o simples
> ato de `import flatcap.graficos` mudar a fonte de qualquer figura que qualquer
> outra parte do processo viesse a desenhar — um notebook que importasse o
> FlatCap para olhar um manifesto sairia com os próprios gráficos em Arial, sem
> nada dizendo por quê. Um módulo que desenha não tem o direito de decidir pelo
> processo; ele decide pela figura dele.
>
> O `rc_context` do `desenhar` aplica isto enquanto a figura é montada **e**
> salva, e devolve o estado no fim. Os dois dentro do mesmo contexto de
> propósito: o matplotlib só resolve a fonte na hora de desenhar, e quem desenha
> é o `savefig`.
>
> `text.parse_math` desligado porque nenhum texto destas figuras é fórmula, e
> todos vêm do banco do cliente. Ligado — o padrão do matplotlib —, dois `$` na
> mesma etiqueta abrem e fecham uma expressão matemática: a faixa de renda
> `R$ 1.000 a R$ 2.000` saía desenhada `R1.000aR 2.000`, em itálico e sem os
> espaços, ao lado da tabela que dizia certo.

- *linha 128* — `import matplotlib.pyplot as plt` — noqa: E402 - obrigatoriamente depois do `use`

- *linha 129* — `from matplotlib.ticker import MaxNLocator` — noqa: E402

- *linha 131* — `if TYPE_CHECKING:` — só para a anotação; em tempo de execução nada disto é carregado

### `SUPERFICIE`

*linha 134*

> A paleta. Fundo, tintas e grade de um sistema de visualização conferido; a série
> é a cor de identidade nº 1 dele. Ficam com nome aqui em cima porque trocar a cor
> do FlatCap um dia deve ser trocar estas oito linhas, e não caçar hexadecimal
> dentro das funções.

- *linha 146* — `LARGURA_POLEGADAS = 6.3` — ~16 cm: a largura útil de uma página A4 com margens

- *linha 151* — `_ESPESSURA_BARRA = 0.58` — o resto da faixa é ar, que é o que separa as barras

- *linha 152* — `_ESPESSURA_COLUNA = 0.78` — a série no tempo é lida como um perfil, e pede menos ar

- *linha 153* — `_LIMITE_ROTULOS_COLUNAS = 12` — acima disso o eixo carrega os valores

- *linha 154* — `_LARGURA_ROTULO = 28` — caracteres antes de quebrar o rótulo de uma categoria

### `_PONTO_QQ`

*linha 156*

> O ponto do Q-Q. Pequeno e sem contorno: em uma amostra de duzentos casos os
> pontos do miolo se encostam, e um contorno escuro em cada um transformaria o
> centro da nuvem em um borrão — que é justamente a parte que precisa ser lida
> como uma linha reta.

- *linha 161* — `_ALTURA_QQ = 3.6` — um dedo a mais que o padrão: o Q-Q é lido como um quadrado

### `_PONTO_DISPERSAO`

*linha 163*

> O ponto da dispersão. A área cresce com o número de casos que caem no mesmo lugar
> — área, e não raio, porque é a área que o olho compara —, e o maior ponto tem um
> teto: numa escala de 0 a 5 com 500 casos, um ponto de área proporcional sem teto
> cobriria o gráfico. Quando o teto aperta, todos encolhem na mesma proporção, e o
> ponto de um caso só continua visível.

### `def versao_do_matplotlib()`

*linha 173*

A versão que desenhou. Vai para o `ambiente` do manifesto.

### `def fonte_dos_graficos()`

*linha 180*

A fonte que o matplotlib **de fato** resolveu — não a que foi pedida.

Existe porque esta é a falha mais silenciosa do módulo: sem o Arial instalado,
o matplotlib escreve um aviso em `stderr`, que ninguém lê, e desenha com o
próximo nome da lista. O gráfico sai bonito, com a fonte errada, e a única
forma de descobrir é pôr a figura ao lado do texto do documento e reparar.

É a mesma ideia da codificação impressa no `perfil.md`: a única forma de saber
que a escolha foi outra é vê-la escrita. Ela vai para o campo `fonte` do
`ambiente` de todo manifesto que tem figura — `descritiva._ambiente` e
`normalidade._ambiente` —, e é o que responde, no dia em que uma rodada antiga
sair com outra cara, se mudou a máquina ou mudou o código. Ficou escrita e não
chamada por duas fases, que é o defeito silencioso que ela existia para expor,
aplicado a si mesma.

### `def desenhar(grafico, caminho)`

*linha 203*

Escreve o `.png` de um `Grafico`, onde quer que o chamador tenha pedido.

O caminho é parâmetro, e é a razão de este módulo servir a qualquer análise
sem saber que elas existem: a descritiva passa `3. Análises/descritiva/`, a
normalidade passa `3. Análises/normalidade/`, e a decisão de onde o arquivo
mora continua sendo de quem calculou os números.

Espécie que não está no registro estoura, e de propósito — ver o topo do
módulo. A mensagem diz a espécie pedida e as que existem, porque o erro
acontece enquanto alguém escreve uma análise nova e o que ele precisa ler é
"você escreveu `qqplot` e o nome é `qq`".

*linha 227*

> Montar e salvar dentro do mesmo contexto. A aparência vale para esta figura
> e não fica no processo depois dela — ver `APARENCIA`.

### Uma forma por espécie

### `def _barras(grafico)`

*linha 247*

Categórica: barras horizontais, na ordem da tabela, com o valor na ponta.

Horizontais e não verticais porque o rótulo é texto — "Ensino fundamental
incompleto" cabe deitado e não cabe em pé. A ordem é a de cima para baixo, que
é a ordem em que a tabela é lida.

*linha 282*

> Sem eixo de valores: todo valor já está escrito na ponta da sua barra, e o
> eixo seria a mesma informação uma segunda vez.

### `def _histograma(grafico)`

*linha 297*

Numérica: a forma da distribuição, em classes calculadas pelo `descritiva.py`.

As barras se tocam, porque a variável é contínua — o que as separa é um fio da
cor do fundo, e não um contorno escuro, que acrescentaria tinta sem dado.

### `def _colunas(grafico)`

*linha 327*

Data: casos por mês ou por ano, em ordem cronológica.

Verticais, aqui sim: o tempo anda da esquerda para a direita, e um leitor que
vê meses empilhados na vertical precisa parar para entender a direção.

### `def _qq(grafico)`

*linha 371*

Q-Q: o valor observado contra o valor que a normal previa para aquela posição.

É a figura que responde o que o valor-p não responde. O Shapiro-Wilk devolve
um número — "rejeita" ou "não rejeita" — que depende do tamanho da amostra: com
n = 30 quase nada é rejeitado, com n = 3000 quase tudo. O Q-Q mostra **onde** e
**quanto** a distribuição se afasta, e isso não muda com o n. Cauda pesada à
direita, assimetria, um caso extremo sozinho lá em cima: as três têm forma
própria aqui e nenhuma tem forma nenhuma em um p.

**A reta é de referência e vem calculada de fora.** Ela passa pelos quartis —
é a `qqline` do R —, e não é um ajuste por mínimos quadrados. A diferença
aparece justamente no caso em que a figura é consultada: um valor extremo
inclina a reta dos mínimos quadrados o bastante para o resto dos pontos parecer
curvo, e o que se queria ver era o valor extremo. Quem a calcula é o
`normalidade.py`, porque escolher a reta é decisão estatística — aqui só se
desenha o que chegou.

Os pontos ficam **por cima** da reta (`zorder`), porque são eles o dado; a reta
é a régua. E ela é tinta apagada, não a cor da série, pela regra da casa: a
identidade vem do dado, e nenhum outro elemento usa a cor da série.

*linha 406*

> Os pontos primeiro, e o limite do eixo lido **deles** antes de a reta
> entrar. A reta é uma referência infinita cortada nos extremos do eixo x,
> e nos extremos ela sai do intervalo de valores que a variável tem: em uma
> escala de dor de 0 a 5, a reta desce até −3 e o matplotlib alargava o eixo
> para caber, oferecendo `−2,5` de dor a quem lê. É o mesmo defeito que o
> eixo de `12,5 casos` da Fase 5, e a correção é a mesma — o eixo mostra o
> que a variável tem, e o que sobra da reta é cortado.

*linha 431*

> `inteiro=False`: aqui o eixo carrega os valores da variável, e `12,5 kg`
> existe. A regra das marcas inteiras é do eixo que conta casos.

### `def _dispersao(grafico)`

*linha 438*

Dispersão: um ponto por caso, a primeira variável do par no eixo x.

É a figura que acompanha a correlação, e pelo motivo do Q-Q: o coeficiente é um
número, e o número não mostra a curva, o caso extremo sozinho num canto ou os
dois grupos que juntos parecem uma reta. A dispersão mostra.

**Sem reta.** Ela afirmaria uma linearidade que o Spearman e o Kendall não
afirmam, e no Pearson repetiria o que o coeficiente, duas linhas acima na mesma
seção, já diz.

**O ponto cresce onde vários casos coincidem.** Numa escala de 0 a 5 cruzada
com outra, 180 casos caem em 36 lugares, e um ponto desenhado por cima do outro
esconde justamente onde os casos estão. As contagens vêm prontas do
`correlacao.py`; aqui elas só viram área. O contorno é a cor do fundo, para dois
pontos grandes vizinhos não virarem uma mancha.

**Eixo de código com marcas inteiras.** Quando todos os valores de um eixo são
inteiros — escala, código, contagem —, as marcas também são: `1,5` numa escala
de 1 a 3 é o `12,5 casos` da Fase 5 com outro nome.

### `def _todos_inteiros(valores)`

*linha 487*

### `_FORMAS`

*linha 491*

> O registro das espécies.
>
> Aqui embaixo, e não no topo do arquivo, porque ele nomeia funções que precisam
> já existir. É a única coisa do módulo que a espécie nova toca: escrever a função
> e acrescentar uma linha aqui é o trabalho inteiro — foi o que a dispersão da
> correlação fez.

### Peças comuns

### `def _figura(altura)`

*linha 509*

### `def _eixo_de_valores(eixo, inteiro)`

*linha 516*

Grade horizontal fina e sólida, atrás das barras, e nenhuma moldura.

O eixo conta casos, então as marcas são inteiras: `12,5 casos` não existe, e um
eixo que oferece meio caso faz o leitor procurar o que ele significa.

`inteiro=False` é para o eixo que **não** conta casos. No Q-Q ele carrega os
valores da própria variável, onde `12,5 kg` existe e é o que se quer ler —
forçar marcas inteiras ali daria um eixo de `70, 71, 72` em uma variável que
vai de 70,1 a 72,4, e a nuvem inteira caberia entre duas marcas.

### `def _titulo(eixo, grafico)`

*linha 541*

Título e subtítulo alinhados à esquerda, acima da área do gráfico.

Alinhados à esquerda porque a figura vai para dentro de um documento de texto,
onde tudo o mais começa na margem esquerda — um título centralizado sobre uma
página justificada lê como um cartaz.

*linha 553*

> `bold`, e não `semibold`: o Arial tem Regular e Bold e mais nada. Um
> peso 600 pedido a uma família que não o tem é resolvido pelo matplotlib
> por aproximação, e a aproximação muda conforme as fontes instaladas na
> máquina — o mesmo banco sairia com o título mais gordo no seu Windows
> do que no de outra pessoa.

*linha 560*

> Folga suficiente para o subtítulo caber embaixo **e** para o rabo de um
> `_` no nome da variável não cair em cima dele — nome de coluna de banco
> é cheio de sublinhado, e `data_coleta` sobre `n = 240` risca o número.

## `flatcap/descritiva.py`

`SPDX-FileCopyrightText: 2026 Matheus Fernandes` · `SPDX-License-Identifier: GPL-3.0-or-later`

*1883 linhas.*

A descritiva — o passo 2a do fluxo, o que se repete em todos os projetos.

Este módulo obedece ao `dicionario.csv` e a mais nada. É a decisão de arquitetura
nº 2 do roteiro levada até o fim: o que é categórica, o que é numérica, o que se
ignora, em que ordem as categorias aparecem e onde ficam os cortes das faixas foi
decidido por você, na reunião, com o cliente na frente — e está escrito em um
arquivo. Aqui a automação apenas cumpre.

A consequência prática é a que vale registrar: **não há nenhuma heurística neste
módulo.** Nenhum palpite de tipo, nenhuma inferência de categoria, nenhuma
adivinhação de formato. Tudo isso é da Fase 4, e ela existe justamente para que
esta fase não precise decidir nada. Quando a descritiva sai errada, o conserto é
uma célula do `dicionario.csv` — não uma condicional aqui dentro.

Segue o padrão das Fases 2, 3 e 4, decidir e escrever separados:

    plano = preparar_descritiva(raiz)   # abre o banco, lê o dicionário, calcula
    executar_descritiva(plano)          # só escreve

E, como as Fases 3 e 4, **não fala com o REDCap**. Recebe `Path`, não `Config`.

### As quatro decisões desta fase

**Faixas sem `faixas` preenchida: quartis.** Quatro faixas com aproximadamente um
quarto dos casos cada, cortadas em mínimo, Q1, mediana, Q3 e máximo. É a regra que
não inventa nada sobre a variável: ela descreve a distribuição que está lá, em vez
de impor cortes redondos que pareceriam decisão clínica sem terem sido. Quando o
cliente pedir cortes específicos, eles entram na coluna `faixas` e esta regra sai
de cena — e o `perfil.md` já traz os quartis de cada numérica exatamente para essa
conversa.

**Numérica que chegou como texto: recusa.** Se o dicionário diz `numerica` e a
coluna veio como texto — número em célula de texto no `.xlsx`, `12 (repetido)` no
meio, vírgula decimal ao lado de um `não sei` —, o comando não gera nada e diz
quais são as colunas. A alternativa seria converter em silêncio, e converter em
silêncio é como uma média sai de 80% dos casos sem que nada na tabela diga que os
outros 20% não entraram. O caminho é o que a Fase 3 já tem: o cliente corrige,
você registra a versão nova com `flatcap dados adicionar`, e a descritiva roda
sobre ela.

    A vírgula decimal do `.csv` do Excel em português não chega aqui como texto
    desde a 1.14.1: o `banco.py` a lê como número, a coluna inteira ou nada, e
    registra quais colunas leu assim. Até a 1.14.0 ela era recusada, e todo
    projeto que chegava nesse formato — o mais comum — parava na descritiva.

    A exceção é a data, e a razão é do formato, não da regra. Em um `.csv` não
    existe tipo data: o `pandas` infere número a partir do texto e nunca infere
    data. Exigir que o cliente "conserte" isso seria exigir o impossível. Então a
    data escrita como texto é convertida — mas só quando **um único** formato
    explica a coluna quase inteira (a mesma função que a Fase 4 usa para
    denunciá-la), e o formato usado sai escrito no manifesto. Coluna com dois
    formatos misturados não é convertida: é recusada como as numéricas.

**Regerar arquiva a rodada anterior.** `3. Análises/descritiva/` inteira vai para
`2. Versões antigas/descritiva_AAAA-MM-DD_HHMM/` antes de a nova ser escrita. É a
mesma ideia da rotação de bancos da Fase 3, pelo mesmo motivo: um número que o
cliente já viu não pode sumir sem deixar rastro. Se ele perguntar "esse 37% não
era 41% no relatório passado?", a resposta está no disco.

**Data ganha resumo e distribuição no tempo.** O roteiro só fala de categóricas e
numéricas. Uma data descrita como categórica viraria uma tabela de frequência com
uma linha por dia; descrita como numérica, uma média de datas. As duas são inúteis.
O que serve é o período (de quando a quando) e como os casos se distribuem nele —
por mês quando o período é curto, por ano quando é longo.

### O que sai no disco

Uma pasta por rodada, com um arquivo por artefato e um `manifesto.json` que lista
todos eles. O manifesto é o que torna a Fase 6 simples: sem ele, o gerador de
relatório teria de adivinhar arquivos por nome; com ele, percorre uma lista
ordenada e sabe de qual variável cada arquivo saiu. É também o que registra as
versões de biblioteca — o que responde, no dia em que um gráfico sair diferente,
se mudaram os dados ou mudou o `matplotlib`.

Os `.csv` seguem a convenção do `dicionario.csv`: `;` entre campos, UTF-8 com BOM
e vírgula decimal, que é o que faz o arquivo abrir certo com dois cliques no Excel
em português. Sem separador de milhar, de propósito: `1.234,5` em uma célula é a
forma mais fácil de um número virar texto na volta.

### O que este módulo não faz

Não desenha — quem desenha é o `graficos.py`, que recebe as contagens já
calculadas e não recalcula nada. Não conhece o formato do manifesto — quem conhece
é o `manifesto.py`, que não importa nem o `pandas` nem o `matplotlib`. E não
escolhe qual arquivo é o banco: isso é do `banco.py` desde a Fase 4, e é o que
garante que a descritiva e o relatório falem da mesma versão.

*No módulo, linha 147:*

> Nada nesta fase sorteia coisa nenhuma — uma descritiva é contagem, e contagem
> não tem aleatoriedade. A semente existe declarada e registrada no manifesto
> assim mesmo, por dois motivos: o roteiro pede, e a Fase 7 (bootstrap, testes de
> permutação, imputação) vai precisar de uma.
>
> Ela **desceu para o `manifesto.py`** na Fase 7 e é reexportada daqui, para que
> nenhum chamador mude. O motivo está na docstring dela: é um valor que todo
> manifesto registra, e uma segunda semente em um segundo módulo é como duas
> rodadas do mesmo projeto deixam de ser reproduzíveis uma contra a outra. Mesma
> manobra que `versao_vigente` e `formato_de_data` já fizeram.

### `LIMITE_BARRAS`

*linha 158*

> Regras de apresentação. Todas com nome, aqui em cima, pelo mesmo motivo da Fase
> 4: número solto no meio de uma função é decisão que ninguém consegue rever.

- *linha 160* — `LIMITE_BARRAS = 15` — acima disso o gráfico junta a cauda em "Outras"

- *linha 161* — `LIMITE_COLUNAS_TEMPO = 30` — acima disso a distribuição no tempo sai sem gráfico

- *linha 162* — `MESES_PARA_MENSAL = 24` — período até 24 meses é contado por mês; acima, por ano

- *linha 163* — `MINIMO_PARA_FAIXAS = 4` — abaixo disso, quartil não descreve nada

- *linha 164* — `CASAS_RESUMO = 2` — casas das estatísticas; mais na escala pequena (casas_do_resumo)

### `class DescritivaError(RuntimeError)`

*linha 182*

Falha ao gerar a descritiva, já traduzida para o usuário.

Erro próprio pelo mesmo motivo de `ConfigError`, `RedcapError`, `ProjetoError`,
`FichaError`, `DadosError`, `BancoError` e `DicionarioError`: a CLI captura
esta classe e transforma em painel. Qualquer outra exceção é bug de verdade e
deve subir com o traceback inteiro.

A Fase 4 não declarou erro próprio porque o perfil não tinha como falhar
sozinho — ele mede o que estiver lá. Esta fase tem: ela **recusa**, e as
recusas abaixo são o conteúdo da decisão.

### `class DicionarioAusenteError(DescritivaError)`

*linha 197*

O projeto não tem `dicionario.csv`. A descritiva não tem o que obedecer.

### `class DicionarioDesatualizadoError(DescritivaError)`

*linha 203*

O banco tem colunas que o dicionário desconhece.

Recusar é deliberado, e é a mesma escolha do `DicionarioInvalidoError` da Fase
4: uma descritiva com metade das variáveis sai perfeitamente formatada, e nada
nela denuncia a metade que ficou de fora.

### `class VariavelIncompativelError(DescritivaError)`

*linha 213*

O dicionário promete um tipo que a coluna não tem.

É a recusa da numérica que chegou como texto — a decisão central da fase.
Lista **todas** as colunas de uma vez: descobrir a segunda depois de corrigir
a primeira é o jeito mais lento possível de arrumar um banco.

### `class NadaParaAnalisarError(DescritivaError)`

*linha 223*

Nenhuma variável do dicionário entra na descritiva.

### O que sai no disco

*No módulo, linha 232:*

> `Tabela` e `Grafico` moram no `manifesto.py` desde a Fase 7, e são reexportados
> daqui — `from .descritiva import Tabela` continua funcionando.
>
> Eles são o **contrato de saída de qualquer análise**, e não da descritiva: a
> normalidade escreve `.csv` e desenha `.png` com as mesmas duas classes. Deixá-los
> aqui obrigaria toda análise nova a importar o módulo da descritiva — acoplando
> duas análises que não têm nada a ver uma com a outra, e fazendo a segunda pagar
> meio segundo de `pandas` só para conhecer uma `dataclass` de texto. O
> `manifesto.py` já era dono do `Artefato`, não importa `pandas` nem `matplotlib`,
> e é o módulo que a Fase 6 lê para montar o documento: é o lugar.

### `class VariavelDescrita`

*linha 245*

Uma variável do dicionário, já descrita: as tabelas e os gráficos que ela gera.

#### `def preenchidos(self)`

*linha 262*

### `class ForaDaDescritiva`

*linha 267*

Uma variável do dicionário que não gerou artefato, e por quê.

Ela aparece no manifesto de propósito. "Não está no relatório" e "ninguém
reparou que ela existia" são coisas diferentes, e só a primeira é uma decisão.

### `class Descritiva`

*linha 281*

O banco inteiro descrito. É daqui que saem os arquivos e o terminal.

#### `def raiz(self)`

*linha 294*

#### `def linhas(self)`

*linha 298*

#### `def tabelas(self)`

*linha 302*

#### `def graficos(self)`

*linha 306*

#### `def por_tipo(self, tipo)`

*linha 309*

### `class PlanoDescritiva`

*linha 314*

Tudo o que o `descritiva` faria, decidido e ainda não escrito.

#### `def raiz(self)`

*linha 327*

#### `def tabelas(self)`

*linha 331*

#### `def graficos(self)`

*linha 335*

#### `def arquivos(self)`

*linha 339*

### `class ResultadoDescritiva`

*linha 345*

O que a execução de fato escreveu.

### Casos de uso

### `def preparar_descritiva(raiz, aba, conferir, com_graficos, agora)`

*linha 358*

Abre o banco, lê o dicionário, calcula tudo e monta o plano. Não escreve nada.

Args:

    raiz: a pasta do projeto (a que tem o `projeto.yaml`).
    aba: planilha do `.xlsx`, quando houver mais de uma.
    conferir: reler o `sha256` das versões e comparar com a ficha.
    com_graficos: desenhar os `.png`. Desligado, o `matplotlib` nem é importado.
    agora: relógio injetável — sem ele os testes não teriam como comparar o
        nome da pasta arquivada nem o manifesto, que carregam a data.

Raises:

    FichaError, BancoError, DicionarioInvalidoError e as quatro recusas
    declaradas acima.

*linha 389*

> `pasta_da_analise` e não a concatenação à mão: a mesma pergunta é feita
> pela normalidade e pelo relatório, e é o `projeto.py` que responde por
> onde uma rodada mora. Duas formas de montar o mesmo caminho é como uma
> delas deixa de acompanhar a próxima mudança no desenho da pasta.

### `def executar_descritiva(plano)`

*linha 406*

Escreve o plano no disco. Não decide mais nada.

A ordem é a da Fase 3, e pelo mesmo motivo: o recibo vem depois do que ele
descreve. Arquiva a rodada anterior, cria a pasta, escreve as tabelas, desenha
os gráficos, e só então o `manifesto.json` — que é o índice, e um índice que
aponta para arquivo inexistente é pior do que índice nenhum.

Cada etapa registra como voltar atrás. Uma falha no meio desfaz o que já foi
feito, inclusive devolvendo a pasta arquivada ao lugar — senão a rodada
anterior teria sumido em troca de nada.

*linha 432*

> `existia` antes do `mkdir`: a pasta só entra no desfazer quando foi
> este comando que a criou. O `rmdir` é registrado **antes** dos
> arquivos e o desfazer roda ao contrário, então os arquivos saem
> primeiro e a pasta sai vazia, que é a única forma de ela sair.

*linha 449*

> O `matplotlib` entra aqui dentro, e não no topo do arquivo: ele custa
> perto de meio segundo para carregar, e `--sem-graficos` não deve
> pagar por ele. É a mesma decisão que a Fase 4 tomou com o `pandas` na
> CLI.

*linha 474*

> Qualquer falha, e não só `OSError` e `DescritivaError`. O que roda
> aqui dentro inclui o `matplotlib`, que estoura com exceções próprias
> — e uma delas subindo sem passar por aqui deixava a rodada anterior
> arquivada em troca de nada, que é exatamente o que o desfazer existe
> para impedir. O erro continua subindo inteiro: o que muda é que o
> disco volta ao estado de antes antes de ele subir.

### `def descrever(banco, ficha, linhas_do_dicionario, quando)`

*linha 496*

Descreve o banco obedecendo ao dicionário. Função pura.

Separada de `preparar_descritiva` porque é o miolo testável, como o `perfilar`
da Fase 4: dá para jogar um `DataFrame` montado à mão e uma lista de `Linha`
aqui dentro e afirmar sobre as tabelas, sem pasta de projeto e sem disco.

Raises:

    VariavelIncompativelError, NadaParaAnalisarError

- *linha 529* — `if serie is None:` — pragma: no cover - `_recusar_incompativeis` já barrou

### Uma variável

### `def _descrever_variavel(linha, serie, slug, total)`

*linha 564*

Despacha para o tipo declarado no dicionário. Devolve `None` para coluna vazia.

### `def _descrever_categorica(linha, serie, slug, total, faltantes)`

*linha 581*

Frequência absoluta e relativa, com e sem faltantes, mais o gráfico de barras.

A ordem das linhas é a do dicionário quando `categorias_ordem` está preenchida
— é a decisão da reunião, e é o que faz duas tabelas do mesmo estudo
apresentarem "Feminino" sempre antes de "Masculino". Sem ela, frequência
decrescente com desempate alfabético, que é a ordem em que uma tabela nominal
se lê e é determinística.

Categoria declarada e ausente do banco sai com `n = 0`, em vez de sumir: a
tabela do relatório precisa ser a mesma antes e depois de o cliente mandar a
versão em que aquela categoria não apareceu. E valor que está no banco e não
foi declarado entra no fim, com aviso — é assim que um `"Sim "` com espaço se
denuncia sozinho.

*linha 633*

> O código conta, o rótulo imprime.
>
> `ordem` são os valores como eles estão na coluna do banco — é por eles que
> `observadas` é consultada. O que vai para a tabela e para o gráfico é o
> rótulo, que cai no próprio código quando não há um. Uma coluna de texto
> atravessa isto sem nada acontecer: lá o valor **é** o rótulo.
> Nome próprio, e não `contagem` de novo: o `value_counts` acima devolvia uma
> `Series` indexada pelo valor do banco, e isto é um `dict` indexado pelo
> rótulo. São duas coisas diferentes, e reaproveitar o nome fazia o miolo da
> função mais importante do módulo depender de qual das duas era a da linha.

*linha 652*

> Dois códigos com o mesmo rótulo viram **uma linha só, somada**. Não é
> tolerância a erro de digitação: é a promessa que o cabeçalho deste módulo
> faz desde a Fase 4 — *"reagrupar categorias vira editar uma célula, não
> caçar código"*. Escrever `1=Sim|2=Sim` é o jeito de dizer "some estes dois",
> e duas linhas chamadas «Sim» na mesma tabela seriam a promessa quebrada.
>
> O aviso abaixo é o que impede o agrupamento acidental de passar: ele nomeia
> quais códigos foram somados em qual rótulo, e aparece na tela e no manifesto.

*linha 741*

> O mapa vai para o manifesto de propósito: é ele que responde, seis
> meses depois, de onde saiu a palavra «Feminino» em uma tabela cuja
> coluna no banco só tem `1` e `2`.

### `def _descrever_numerica(linha, serie, slug, total, faltantes)`

*linha 753*

Resumo, tabela por faixas e histograma.

O resumo traz mais do que o mínimo e o máximo que o roteiro pede, e é
deliberado: média, desvio, mediana e quartis são o que o relatório da Fase 6
escreve sobre uma numérica, e tê-los aqui é o que impede a Fase 6 de reabrir o
banco para recalcular — que é a porta pela qual o relatório passa a discordar
da tabela.

*linha 770*

> As casas da variável, e não as duas de sempre: numa concentração na casa de
> 0,003, duas casas faziam o resumo inteiro sair `0`. Ver `banco.casas_do_resumo`.

*linha 801*

> O corte escrito no dicionário sai como foi escrito: `0,00255` impresso com
> as casas da variável seria um corte que ninguém pediu.

*linha 814*

> Os do dicionário vão inteiros: o relatório os compara com o dicionário
> de hoje, e `0,00255` gravado como `0.0026` era um "dicionário mudou" falso.

### `def _descrever_data(linha, serie, slug, total, faltantes)`

*linha 864*

O período (de quando a quando) e como os casos se distribuem dentro dele.

Devolve `None` quando não sobrou nenhuma data válida, como a coluna vazia:
sem data não há período a descrever.

*linha 876*

> Sem nenhuma data válida não há período: `minimo` e `maximo` saem `NaT`
> e `(maximo - minimo).days` estoura. Hoje é inalcançável — a recusa de
> `recusar_incompativeis` exige um formato que explique 90% da coluna —,
> e a guarda existe porque «inalcançável» é uma propriedade de outro
> módulo, não desta função. `None` a manda para a lista `fora`, que é
> onde as colunas sem valor já são registradas.

### Faixas

### `def _cortes_das_faixas(linha, valores)`

*linha 993*

Os cortes que valem para esta variável, e de onde eles vieram.

A coluna `faixas` do dicionário manda. Ela já chegou conferida pela Fase 4 —
números em ordem crescente —, então aqui não há o que validar de novo.

Sem ela, os quartis: mínimo, Q1, mediana, Q3 e máximo, sem repetir. O que
sobra depois de tirar os repetidos precisa ser **pelo menos três cortes** —
isto é, duas faixas —, e não cinco: uma variável em que só a mediana coincide
com Q1 ainda produz três faixas honestas, e recusá-la seria jogar fora uma
tabela correta por causa de um empate.

Abaixo de três, não sai tabela nenhuma e o motivo fica escrito no manifesto:
com dois cortes sobraria uma faixa só, que é a variável inteira e não
descreve nada. Uma variável assim é categórica disfarçada de número, e a
decisão de tratá-la como tal é sua, no dicionário.

### `def _tabela_de_faixas(linha, slug, valores, cortes, origem, total, faltantes, casas)`

*linha 1039*

Conta os casos em cada faixa, com uma convenção só e escrita no arquivo.

`[a a b)` inclui `a` e exclui `b`; a última faixa inclui os dois extremos. É a
convenção das faixas etárias — `0|18|30` são "menor de 18", "de 18 a 29" —, e
é a única que não deixa um caso em duas faixas nem fora de todas.

A contagem é feita à mão, e não com `pd.cut`, por causa dessa última faixa: o
`pd.cut` fecha todos os intervalos do mesmo lado, e o máximo da variável cairia
fora do último. Um caso perdido em silêncio no extremo é exatamente o tipo de
erro que ninguém confere.

### `def _histograma(valores)`

*linha 1136*

As classes do histograma, calculadas aqui e não no `graficos.py`.

Quantas classes usar é decisão estatística, não de desenho: Freedman-Diaconis
quando o intervalo interquartil existe (é robusto a valor extremo, que em banco
de saúde é regra), Sturges quando ele é zero. O número de classes sai no
manifesto, que é o que permite descobrir depois por que um histograma mudou de
cara entre duas rodadas.

Deliberadamente **não** são as faixas da tabela: a tabela responde "quantos em
cada grupo que interessa"; o histograma mostra a forma da distribuição. Fazer
os dois com os mesmos cortes é publicar a mesma informação duas vezes.

### Gráfico de barras

### `def _grafico_de_barras(linha, slug, pares, preenchidos, faltantes)`

*linha 1184*

O gráfico da categórica: uma barra por categoria, na ordem da tabela.

Acima de `LIMITE_BARRAS` categorias a cauda vira uma barra "Outras". Um gráfico
de sessenta barras não é lido por ninguém, e a tabela ao lado continua com
todas — o gráfico é a leitura rápida, a tabela é a fonte.

Os faltantes não viram barra. O gráfico descreve a distribuição da variável
entre quem respondeu; quantos não responderam é uma frase do subtítulo e uma
linha da tabela.

### O manifesto

### `def montar_manifesto(descritiva, linhas, com_graficos)`

*linha 1233*

Traduz a descritiva para o índice que a Fase 6 vai ler.

*linha 1254*

> Uma seção da descritiva usa exatamente uma coluna, e é por isso que
> o campo parecia redundante até existir a segunda análise. Ele é
> escrito aqui porque a conferência do relatório passou a perguntar
> "quais colunas esta rodada usou?" a **toda** rodada — e uma pergunta
> que só algumas respondem é uma pergunta que não se pode fazer.

*linha 1269*

> Cliente **e** projeto. Desde a 1.1.0 `raiz.name` é `Projeto 006`,
> e o manifesto é o recibo da rodada: um recibo que não diz de quem
> é o trabalho não serve para conferir coisa nenhuma depois.

*linha 1297*

> Mesmo campo, mesmo esquema que o manifesto da normalidade. Dois
> blocos `dicionario` com chaves diferentes obrigariam quem lê os
> dois — o relatório, e você — a saber de qual análise é o arquivo
> antes de saber o que perguntar a ele.

### `def _artefatos(variavel, com_graficos)`

*linha 1322*

### `def _ambiente(com_graficos)`

*linha 1345*

As versões que produziram estes números.

O roteiro pede isso, e a justificativa dele é literal: no dia em que um gráfico
sair diferente do que saía antes, é o que responde se mudaram os dados ou mudou
a biblioteca. O `matplotlib` só é consultado quando há gráfico — perguntar a
versão custaria importar a biblioteca que o `--sem-graficos` existe para evitar.

A **fonte** entra junto, e ela não é uma versão: é a fonte que o matplotlib de
fato resolveu, que pode não ser a que o `graficos.py` pediu. Sem o Arial
instalado ele escreve um aviso em `stderr`, que ninguém lê, e desenha com o
próximo nome da lista — o gráfico sai bonito, com a fonte errada, e a única
forma de descobrir é pôr a figura ao lado do texto do documento e reparar.
Escrita aqui, a pergunta «mudou a máquina ou mudou o código?» tem resposta.

### Recusas

### `def conferir_dicionario(raiz, banco, ausente, desatualizado, analise)`

*linha 1382*

Lê o `dicionario.csv` e confere que ele descreve **este** banco.

Pública desde a Fase 7, e com as duas classes de erro como parâmetro. A razão
é que duas regras da casa se cruzam aqui:

* **uma implementação só.** Toda análise obedece ao mesmo dicionário e
  pergunta a mesma coisa sobre o mesmo banco. Duas cópias desta conferência é
  como um comando aceita rodar sobre um dicionário que o outro recusou — e aí
  o relatório monta uma seção sobre variáveis que a outra seção não tem.
* **um erro por módulo.** A CLI captura `DescritivaError` no comando
  `descritiva` e `NormalidadeError` no comando `normalidade`, e é isso que faz
  o painel sair com o título certo. Se esta função levantasse sempre
  `DescritivaError`, `flatcap normalidade` abriria um painel escrito
  "Descritiva" — sobre um comando que o usuário não rodou.

Passar a classe resolve as duas sem escolher entre elas. O default é o da
descritiva, então o chamador antigo não mudou.

O `analise` entra só no texto, e entra porque a frase muda de dono: "a
descritiva não tem o que obedecer" é a mesma informação que "a normalidade não
tem o que obedecer", e nenhuma das duas deve dizer o nome da outra.

*linha 1427*

> Entre aspas quando o nome tem espaço nas pontas ou quebra de linha: `Idade `
> impresso solto é indistinguível de `Idade`, e a diferença é a recusa inteira.

### `_dicionario_do_projeto`

*linha 1446*

> O nome privado que o resto deste módulo usa. Mesma manobra do
> `perfil._formato_de_data`: a função mudou de visibilidade, e nenhum chamador
> interno mudou de linha.

### `def recusar_incompativeis(quadro, analisaveis, erro)`

*linha 1452*

Recusa o comando inteiro quando o dicionário promete um tipo que a coluna não tem.

É a decisão central da fase, e a razão dela é o denominador. Converter
`"12,5"` em silêncio funciona nos valores que convertem e transforma os outros
em faltantes — e uma média calculada sobre 80% dos casos sai com a mesma cara
de uma calculada sobre 100%. O relatório não teria como denunciar isso, porque
a conversão aconteceu antes de a contagem começar.

Recusar devolve a decisão para onde ela pertence: o arquivo é do cliente, a
correção é dele, e a Fase 3 tem o lugar certo para a versão corrigida entrar.
A coluna inteira em vírgula decimal de um `.csv` separado por `;` não chega
aqui: o `banco.py` já a leu como número, sem perder nenhum valor.
Se a coluna não vai ser corrigida, o dicionário aceita `categorica` ou
`ignorar` — as duas são decisões suas, escritas, e nenhuma delas é silenciosa.

Pública desde a Fase 7, e com a classe de erro como parâmetro, pelo mesmo
motivo do `conferir_dicionario` acima: a conferência precisa ser uma só e o
painel precisa levar o nome do comando que o usuário rodou. Se a descritiva
recusasse `peso` e a normalidade a aceitasse, o relatório sairia com um teste
de normalidade sobre uma coluna que nenhuma tabela descreve.

**Cada análise passa as variáveis que ela vai tocar**, e é por isso que a
função recebe a lista em vez de ler o dicionário por conta própria. A
normalidade só usa as `numerica`, então uma coluna `data` com dois formatos
misturados — que recusa a descritiva — não bloqueia um teste que nunca a
abriria. A regra é a mesma; o escopo é de quem chama.

### `def _mensagem_incompativel(problemas)`

*linha 1526*

### `def _mensagem_nada_a_analisar(linhas)`

*linha 1555*

### `def _motivo_de_fora(linha)`

*linha 1568*

### Arquivamento

### `def arquivamento(raiz, pasta, quando, analise)`

*linha 1577*

Onde a rodada anterior vai parar, se houver uma.

Arquivar a pasta inteira, e não sobrescrever arquivo por arquivo, é o que
mantém cada rodada coerente consigo mesma: o `manifesto.json` de dentro
descreve exatamente os arquivos que estão ao lado dele. Uma pasta sobrescrita
pela metade teria a tabela nova de `sexo` ao lado do gráfico velho de `idade`,
e nada diria qual é qual.

O nome carrega data e hora porque duas rodadas no mesmo dia são o caso comum —
você roda, olha, corrige o dicionário e roda de novo.

Pública desde a Fase 7, com o nome da análise como parâmetro: a regra de
arquivar é do desenho da pasta e vale para qualquer rodada, e o prefixo
`descritiva_` era o único pedaço dela que sabia de qual análise se tratava.
Com o parâmetro, `normalidade_2026-09-17_1500/` sai da mesma função — e a
pasta `2. Versões antigas/` continua se lendo de cima para baixo, com o nome
da análise na frente da data.

### `def _acao_do_historico(plano)`

*linha 1614*

### Leitura da série

### `def _coluna(quadro, nome)`

*linha 1634*

A coluna do banco pelo nome, ou `None`.

Pela posição, e não por `quadro[nome]`: nome repetido devolveria um `DataFrame`
no lugar de uma coluna. A Fase 4 denuncia nome repetido como `cabecalho_repetido`
e pede a correção; aqui a primeira ocorrência é usada, que é a que o dicionário
descreve.

### `def _e_numerica(serie)`

*linha 1649*

### `def _e_data(serie)`

*linha 1655*

### `_serie_de_texto`

*linha 1659*

> A `serie_de_texto` desceu para o `banco.py` na 1.13.1, para o perfil propor as
> categorias com a mesma escrita das análises. Ela continua importável daqui —
> `from .descritiva import serie_de_texto` é como as outras análises a chamam —,
> e com o apelido privado que este módulo usa.

### `def _como_data(serie)`

*linha 1666*

A coluna como data. Devolve a série, o formato usado e quantos não converteram.

Já passou por `_recusar_incompativeis`, então ou a coluna é data no arquivo
(`formato = None`), ou existe um formato único que explica quase toda ela.

### `def resumo_numerico(valores)`

*linha 1683*

Mínimo, quartis, mediana, máximo, média e desvio padrão de uma coluna já sem os
faltantes.

Pública desde a 1.7.0, com o apelido privado que este módulo usa. A comparação
imprime a média e o desvio da mesma variável na tabela dela, e uma segunda conta
é como a média do `resumo_imc.csv` diz `26,41` e a da comparação, na página
seguinte, `26,4` — a manobra do `numero` e do `percentual`.

### `def _contar_periodos(datas, passo)`

*linha 1707*

Conta os casos por mês ou por ano, sem buracos.

Período sem nenhum caso entra com zero de propósito: em um estudo, três meses
sem recrutamento é informação — e uma tabela que simplesmente pula esses meses
esconde justamente o que se queria ver.

### Formatação

### `def numero(valor, casas)`

*linha 1734*

Número no formato brasileiro, sem separador de milhar.

Sem milhar de propósito: `1.234,5` numa célula é a forma mais fácil de um
número virar texto na volta, e estes arquivos existem para serem lidos de volta
— pela Fase 6 e por você, no Excel.

Pública desde a Fase 7 pelo mesmo motivo do `tamanho_legivel` do `projeto.py`:
dois formatadores diferentes para a mesma grandeza é como um relatório sai com
`20,5` em uma tabela e `20.5` na seguinte, na mesma página. Pelo mesmo motivo,
a conta mora no `banco.texto_de_numero` desde a 1.13.1: a `serie_de_texto`
desceu para lá e escreve os números com ela.

### `def percentual(parte, total)`

*linha 1754*

Percentual com casas fixas: `5,0` e `100,0`, nunca `5` e `100`.

Ao contrário das estatísticas, aqui o zero à direita não é ruído: uma coluna
de percentuais em que uns valores têm casa decimal e outros não é uma coluna
que não alinha, e desalinhada ela deixa de ser lida de cima para baixo — que é
a única forma de ler uma tabela de frequência.

Pública desde a 1.4.0, pelo mesmo motivo do `numero`: o cruzamento imprime
`% dos válidos` ao lado das tabelas de frequência, e dois formatadores para o
mesmo percentual é como um documento sai com `26,8` numa página e `26.8%` na
seguinte.

### `def _arredondar(valor)`

*linha 1779*

O número do manifesto: quatro casas, ou quatro algarismos significativos quando
ele é menor que 0,1 — com quatro casas, o desvio de 0,00062 era gravado `0.0006`.

### `def _casas_escritas(textos)`

*linha 1794*

As casas do corte mais preciso que o dicionário escreveu: `0,00255` tem cinco.

### `def _data(valor)`

*linha 1805*

- *linha 1808* — `except (ValueError, TypeError):` — pragma: no cover - já validado antes

### `def _integridade(confere)`

*linha 1812*

### `def _subtitulo(preenchidos, faltantes)`

*linha 1820*

### `def _distintos(valores, quantos)`

*linha 1827*

Alguns valores diferentes, na ordem em que aparecem.

Diferentes, e não os primeiros: em uma coluna com dois formatos de data
misturados, os cinco primeiros são cinco vezes o mesmo formato — e o exemplo
existe justamente para mostrar a mistura.

### `def _encurtar(texto, limite)`

*linha 1845*

### `def slug(nome, usados)`

*linha 1850*

O pedaço do nome do arquivo que vem da variável.

O nome da variável vem do banco do cliente: tem acento, espaço, parêntese,
barra e às vezes cem caracteres. Nada disso monta nome de arquivo — é o mesmo
cuidado que a `sanitizar` do `nomes.py` toma com a pasta, aplicado aqui porque
a regra é outra: um nome de arquivo que precisa sobreviver a `.csv`, ao Windows
e a um `%` de URL no dia em que o relatório virar HTML.

Colisão (`Idade (anos)` e `idade_anos` dão o mesmo pedaço) resolve com sufixo
numérico, na ordem das colunas do banco. É o `manifesto.json` que diz qual
arquivo é de qual variável — e é por isso que ele existe.

Pública desde a Fase 7: duas análises escrevendo `hist_idade.png` e
`qq_idade_anos.png` para a mesma coluna, cada uma com a sua regra de limpeza,
é como um `.png` deixa de ser encontrável pelo nome da variável que o gerou.
O `usados` é por rodada — o desempate vale dentro de uma pasta, não entre elas.

## `flatcap/normalidade.py`

`SPDX-FileCopyrightText: 2026 Matheus Fernandes` · `SPDX-License-Identifier: GPL-3.0-or-later`

*1451 linhas.*

A normalidade — a primeira análise da Fase 7.

Responde ao passo 2b do fluxo: as análises que variam de projeto para projeto.
Esta é a que vem primeiro, e não por acaso. Ela é **pressuposto**, não resultado:
Pearson ou Spearman, teste t ou Mann-Whitney, a média ou a mediana no texto — as
três perguntas seguintes começam aqui. Uma correlação implementada antes desta
seria uma correlação escolhida no escuro.

Segue o padrão das Fases 2 a 6, decidir e escrever separados:

    plano = preparar_normalidade(raiz)   # abre o banco, calcula, não toca no disco
    executar_normalidade(plano)          # só escreve

E, como elas, **não fala com o REDCap**. Recebe `Path`, não `Config`.

### A decisão central: o valor-p sozinho não responde à pergunta

É o risco real desta análise, e ele não é técnico. O valor-p do Shapiro-Wilk é
função do tamanho da amostra: com n = 30 quase nada é rejeitado, porque o teste
não tem poder para rejeitar; com n = 3000 quase tudo é, porque qualquer desvio
irrelevante vira significante. Um módulo que imprimisse `p = 0,003 → não normal`
automatizaria má prática dentro de um documento assinado que vai para um professor
de medicina.

Então cada variável sai com quatro coisas, e nenhuma delas sozinha:

    n                     em coluna própria, porque é ele que calibra o resto
    assimetria e curtose  medem o **tamanho** do desvio, e não dependem do n
    W e o valor-p         o teste, com os limites dele escritos no arquivo
    o Q-Q                 onde a distribuição se afasta, que é o que o p não diz

Mais uma leitura em palavras, na última coluna, como o `motivo` do `perfil.md` da
Fase 4. Ela descreve a **forma** da distribuição — "assimétrica à direita",
"caudas pesadas" — e nunca escolhe um teste para você. Escolher o teste depende da
comparação que se vai fazer, e este módulo não sabe qual é: ele olha uma coluna,
não um delineamento.

### O que ele deliberadamente não faz

**Não imprime média nem desvio padrão.** Eles são o `resumo_<variável>.csv` da
descritiva. Duas fontes para o mesmo número é o que este projeto gasta energia
impedindo desde a Fase 5, e a média impressa em duas tabelas da mesma página
discordando na segunda casa é exatamente o defeito que ninguém confere.

**Não testa resíduo nem subgrupo.** O que este módulo mede é a distribuição da
coluna como ela está. Para um teste t o que importa é a normalidade **dentro de
cada grupo**, e para uma regressão é a dos **resíduos** — as duas são outra
análise, e nenhuma das duas se deduz desta. Está escrito na nota do `.csv`, porque
é o engano mais fácil de cometer lendo a tabela.

**Não converte nada.** Numérica que chegou como texto é recusada, com a mesma
função e a mesma mensagem da descritiva — se as duas discordassem, o relatório
sairia com um teste de normalidade sobre uma coluna que nenhuma tabela descreve.

### Quais variáveis entram

Todas as `numerica` analisáveis do dicionário, e a lista `normalidade:` da ficha
restringe quando você quiser.

A assimetria com a correlação é deliberada e vale registrar. Um par de variáveis é
uma **hipótese**, e um dicionário de 30 variáveis dá 435 pares: rodar todos e
imprimir os valores-p é *p-hacking* feito por máquina, e é por isso que os pares da
correlação virão escritos na ficha, um a um. Uma varredura de normalidade é outra
coisa — é diagnóstico sobre variáveis que já têm seção própria no relatório, e não
produz achado nenhum. Com uma condição, que é a razão de a tabela se chamar
*Pressupostos* no documento: ela não é resultado, e não deve ser lida como um.

### O `scipy`

É a dependência nova da fase, e a primeira desde a Fase 6. O `pandas` calcula
assimetria e curtose; o que ele não tem é a distribuição do W de Shapiro-Wilk.

Implementá-la à mão seria transcrever o AS R94 (Royston, 1992) — aproximações
polinomiais das estatísticas de ordem esperadas da normal, coeficientes tabelados,
e uma transformação normalizadora com ramos diferentes para n ≤ 11 e n ≥ 12 —, e a
única forma de conferir a transcrição seria comparar com o `scipy`, que é a
biblioteca que se estaria evitando importar. Além disso, "de onde saiu esse p?"
precisa ter como resposta uma **versão**: `scipy 1.17.1`, escrita no `ambiente` do
manifesto desta rodada. Uma função escrita à mão não tem versão.

Ele é importado **dentro** da função que calcula, como o `matplotlib` no
`graficos.py` e o `python-docx` no `documento.py`, e pelo mesmo motivo: nenhum
comando que não faz teste de normalidade deve pagar o import.

*No módulo, linha 133:*

> Os limites do teste. Todos com nome, aqui em cima, pelo mesmo motivo das Fases 4
> e 5: número solto no meio de uma função é decisão que ninguém consegue rever.

### `MINIMO_SHAPIRO`

*linha 136*

> O Shapiro-Wilk não existe abaixo de três observações: com duas, quaisquer dois
> pontos estão perfeitamente sobre uma reta.

### `MINIMO_CONFIAVEL`

*linha 140*

> Abaixo disto o teste roda e quase não rejeita. Não é recusa — é aviso, porque o
> resultado continua sendo verdadeiro sobre o que ele mede; o que muda é o que ele
> permite concluir. "Não rejeitou" com n = 8 não é evidência de normalidade, é
> ausência de evidência de qualquer coisa, e é o engano mais comum com este teste.

### `MAXIMO_CONFIAVEL`

*linha 146*

> Acima disto o próprio `scipy` avisa que o valor-p deixa de ser exato. O aviso
> dele vai para `stderr`, onde ninguém lê; aqui ele é capturado e vira aviso do
> FlatCap, que viaja para o manifesto e para o terminal — mesma manobra do
> `ParserWarning` do `banco.py`.

### `MENOR_P`

*linha 154*

> O menor valor-p que se imprime como número. Abaixo dele sai `< 0,001`, e nunca
> `0,000`: um valor-p é sempre maior que zero, e imprimi-lo como zero é escrever no
> relatório um número que não existe.

- *linha 161* — `CASAS_FORMA = 2` — assimetria e curtose

### `ASSIMETRIA_LEVE`

*linha 163*

> Os cortes da leitura em palavras. São convenções de leitura, não fronteiras da
> natureza — daí estarem nomeadas aqui, onde se discute se mudam.

### `POUCOS_DISTINTOS`

*linha 169*

> Até este número de valores distintos, a variável é avisada como discreta.
>
> O Shapiro-Wilk supõe uma variável **contínua**, e uma escala de 0 a 5 respondida
> por 180 pessoas não é uma. Ele rejeita a normal nesse caso quase sempre, e o
> motivo não é a forma da distribuição estar errada — é ela ser discreta. Sem o
> aviso, a linha sai igual à de uma variável contínua assimétrica, e as duas pedem
> decisões opostas.
>
> O limite é o mesmo `LIMITE_UNICOS_CODIGO` que o `perfil.py` usa para propor
> `categorica` a uma coluna de inteiros pequenos: é a mesma pergunta, feita duas
> fases depois, e dois limites diferentes para ela é como o perfil sugere uma coisa
> e a análise aponta outra sobre a mesma coluna.

### `class NormalidadeError(RuntimeError)`

*linha 186*

Falha ao gerar a análise de normalidade, já traduzida para o usuário.

Erro próprio pela regra da casa: a CLI captura esta classe e transforma em
painel com o nome do comando que o usuário rodou. Qualquer outra exceção é bug
de verdade e deve subir com o traceback inteiro.

As recusas de dicionário e de tipo são compartilhadas com o `descritiva.py` —
uma implementação só —, e mesmo assim chegam aqui como subclasses destas: as
duas funções de lá recebem a classe de erro como parâmetro exatamente para
isso. Ver `descritiva.conferir_dicionario`.

### `class DicionarioAusenteError(NormalidadeError)`

*linha 201*

O projeto não tem `dicionario.csv`. Não há o que obedecer.

### `class DicionarioDesatualizadoError(NormalidadeError)`

*linha 207*

O banco tem colunas que o dicionário desconhece.

### `class VariavelIncompativelError(NormalidadeError)`

*linha 213*

O dicionário promete `numerica` e a coluna chegou como texto.

A mesma recusa da Fase 5, com a mesma mensagem e pela mesma função. Se as duas
discordassem, `flatcap descritiva` recusaria `peso` e `flatcap normalidade`
calcularia um W sobre ela — e o relatório sairia com um teste sobre uma coluna
que nenhuma tabela do documento descreve.

### `class NadaParaAnalisarError(NormalidadeError)`

*linha 224*

Nenhuma variável do dicionário é `numerica`.

Recusa, e não uma pasta com uma tabela vazia dentro: uma rodada que não mede
nada mas existe no disco é uma rodada que o relatório vai encontrar, montar uma
seção para, e imprimir vazia no documento do cliente.

### `class VariavelPedidaInexistenteError(NormalidadeError)`

*linha 234*

A lista `normalidade:` da ficha nomeia uma variável que não serve.

Recusa em vez de ignorar, e é a mesma escolha que a Fase 5 fez com o dicionário
desatualizado: rodar sem ela produziria uma tabela com uma linha a menos, e
nada na saída diria que a variável que você escreveu na ficha não entrou.

### O que sai no disco

### `class VariavelTestada`

*linha 248*

Uma variável numérica, medida. É a linha da tabela.

`w` e `p` são `None` quando o teste não pôde rodar — n abaixo de três, ou
coluna constante. A linha **sai assim mesmo**, com o motivo escrito em
`leitura`. Uma variável que simplesmente não aparecesse na tabela seria uma
variável que ninguém repara que faltou, e essa distinção é a mesma que a lista
`fora` da Fase 5 existe para marcar.

#### `def testada(self)`

*linha 276*

#### `def rejeita(self)`

*linha 280*

O teste rejeitou a normal neste nível?

`False` quando não houve teste — "não rejeitou" e "não foi testada" são
coisas diferentes, e quem precisa distinguir olha `testada`.

#### `def como_detalhe(self)`

*linha 289*

Os números desta variável, para o manifesto.

### `class ForaDaNormalidade`

*linha 307*

Uma variável do dicionário que não entra, e por quê.

Aqui é quase toda a tabela do dicionário: categórica, data e `ignorar` não têm
normalidade para testar. Elas aparecem no manifesto pelo mesmo motivo da Fase
5 — "não está no relatório" e "ninguém reparou que ela existia" são coisas
diferentes, e só a primeira é uma decisão.

### `class Normalidade`

*linha 323*

A rodada inteira, decidida. É daqui que saem os arquivos e o terminal.

- *linha 336* — `pedidas: tuple[str, ...] = ()` — a lista da ficha, quando houver

#### `def raiz(self)`

*linha 339*

#### `def linhas(self)`

*linha 343*

#### `def colunas_usadas(self)`

*linha 347*

#### `def rejeitadas(self)`

*linha 351*

#### `def nao_testadas(self)`

*linha 355*

### `class PlanoNormalidade`

*linha 360*

Tudo o que o `normalidade` faria, decidido e ainda não escrito.

Imutável como os planos das outras fases, e pela mesma razão: entre a simulação
e a execução ninguém altera um caminho em trânsito. A árvore que aparece no
terminal é lida deste objeto.

#### `def raiz(self)`

*linha 377*

#### `def tabela(self)`

*linha 381*

#### `def graficos(self)`

*linha 385*

#### `def arquivos(self)`

*linha 389*

### `class ResultadoNormalidade`

*linha 395*

O que a execução de fato escreveu.

### Casos de uso

### `def preparar_normalidade(raiz, aba, conferir, com_graficos, agora)`

*linha 408*

Abre o banco, testa cada numérica e monta o plano. Não escreve nada.

Args:

    raiz: a pasta do projeto (a que tem o `projeto.yaml`).
    aba: planilha do `.xlsx`, quando houver mais de uma.
    conferir: reler o `sha256` das versões e comparar com a ficha.
    com_graficos: desenhar os Q-Q. Desligado, o `matplotlib` nem é importado.
    agora: relógio injetável — sem ele os testes não teriam como comparar o
        nome da pasta arquivada nem o manifesto, que carregam a data.

Raises:

    FichaError, BancoError, DicionarioInvalidoError e as cinco recusas
    declaradas acima.

### `def executar_normalidade(plano)`

*linha 459*

Escreve o plano no disco. Não decide mais nada.

A ordem é a da Fase 5, e pelo mesmo motivo: o recibo vem depois do que ele
descreve. Arquiva a rodada anterior, cria a pasta, escreve a tabela, desenha os
Q-Q, e só então o `manifesto.json` — que é o índice, e um índice que aponta
para arquivo inexistente é pior do que índice nenhum.

Cada etapa registra como voltar atrás. Uma falha no meio desfaz o que já foi
feito, inclusive devolvendo a pasta arquivada ao lugar — senão a rodada
anterior teria sumido em troca de nada.

*linha 485*

> `existia` antes do `mkdir`: a pasta só entra no desfazer quando foi
> este comando que a criou. O `rmdir` é registrado **antes** dos
> arquivos e o desfazer roda ao contrário, então os arquivos saem
> primeiro e a pasta sai vazia, que é a única forma de ela sair.

*linha 501*

> O `matplotlib` entra aqui dentro, e não no topo do arquivo, pela
> mesma razão que na Fase 5: `--sem-graficos` não deve pagar por uma
> biblioteca que ele existe para não usar.

*linha 525*

> Qualquer falha, e não só `OSError` e `NormalidadeError`. O que roda
> aqui dentro inclui o `matplotlib`, que estoura com exceções próprias —
> e uma delas subindo sem passar por aqui deixava a rodada anterior
> arquivada em troca de nada, que é exatamente o que o desfazer existe
> para impedir. O erro continua subindo inteiro: o que muda é que o
> disco volta ao estado de antes antes de ele subir.

### `def avaliar(banco, ficha, linhas_do_dicionario, pedidas, quando, com_graficos)`

*linha 547*

Avalia a normalidade das numéricas do dicionário. Função pura.

Separada de `preparar_normalidade` porque é o miolo testável, como o `perfilar`
da Fase 4 e o `descrever` da Fase 5: dá para jogar um `DataFrame` montado à mão
e uma lista de `Linha` aqui dentro e afirmar sobre a tabela, sem pasta de
projeto e sem disco.

`com_graficos` chega até aqui porque os pontos do Q-Q são calculados por
variável e descartados inteiros quando não há figura: com `--sem-graficos`,
`_pontos_do_qq` ordenava a coluna, chamava o `scipy` uma vez por variável e
guardava N pontos que o `PlanoNormalidade.graficos` jogava fora. É o mesmo
argumento do import do `matplotlib` lá embaixo — quem desligou o gráfico não
deve pagar por ele.

**Chama-se `avaliar` e não `testar`, e o motivo é prático.** O `pytest` coleta
como teste qualquer objeto chamado `test*` no espaço de nomes de um arquivo de
teste — inclusive um que tenha sido importado de outro módulo. Com o nome
`testar`, o `from flatcap.normalidade import testar` do `test_normalidade.py`
fazia o `pytest` tentar rodar a função como se ela fosse um caso de teste, e a
suíte saía com um `ERROR` de fixture não encontrada que não tem nada a ver com
o código. Foi encontrado rodando, e não lendo.

Raises:

    VariavelIncompativelError, NadaParaAnalisarError,
    VariavelPedidaInexistenteError

*linha 588*

> Só as numéricas vão para a recusa, e não `analisaveis` inteiro. A conferência
> é a mesma da Fase 5; o escopo é desta análise. Uma coluna `data` com dois
> formatos misturados recusa a descritiva e não tem por que bloquear um teste
> que nunca a abriria. Ver `descritiva.recusar_incompativeis`.

*linha 594*

> Por nome, e não `if linha not in numericas`: a comparação de `Linha` é por
> valor e a busca é linear, o que dava O(n²) — e, com duas linhas idênticas,
> a segunda seria dada como numérica sem ser. A variável é a chave do
> dicionário, e o `ler_arquivo` já recusa duas linhas com o mesmo nome.

- *linha 628* — `if serie is None:` — pragma: no cover - `recusar_incompativeis` já barrou

### Uma variável

### `def _testar_variavel(linha, serie, slug, total, com_graficos)`

*linha 661*

Mede uma coluna: forma, teste, e os pontos do Q-Q.

Os faltantes são tratados **por variável**: cada uma é testada sobre os
próprios valores preenchidos, e por isso o `n` muda de linha para linha da
tabela. É o oposto do descarte por lista completa, que jogaria fora a linha
inteira do banco por causa de uma célula vazia em uma coluna — e faria o teste
de `idade` depender de quem respondeu `imc`. A coluna `n` está na tabela
justamente porque ele varia; escondê-la seria deixar o leitor supor que é o
mesmo denominador em todas.

*linha 685*

> `nunique() >= 2` antes de pedir a forma, e não é precaução: em uma coluna
> constante a assimetria é 0/0, e o `pandas` devolve **0,0** para ela em vez de
> `nan`. Impresso na tabela, esse zero se lê como "perfeitamente simétrica"
> sobre uma coluna que não tem forma nenhuma — e é indistinguível do zero de
> uma variável que é mesmo simétrica. O traço é a resposta certa.

*linha 722*

> Sem figura, sem pontos. Eles só existem para o Q-Q, e calculá-los custa
> ordenar a coluna e uma chamada ao `scipy` por variável — para guardar N
> pontos que o `PlanoNormalidade.graficos` descarta em seguida.

### `def shapiro(variavel, valores, preenchidos)`

*linha 749*

O Shapiro-Wilk, com os dois casos em que ele não existe barrados antes.

Pública desde a 1.6.0, com o apelido privado que este módulo usa: a correlação
escolhe entre Pearson e Spearman por este teste, e uma segunda chamada ao
`scipy` com outras barreiras e outro tratamento de aviso é como a tabela de
normalidade e a nota da correlação passam a discordar sobre a mesma coluna.

Devolve `(W, p, impedimento, aviso)`. `impedimento` é a frase que vai para a
coluna `leitura` quando não houve teste — ela ocupa o lugar do resultado, e não
some junto com ele.

Duas barreiras antes da chamada, e as duas são condições do teste e não
precaução: abaixo de três observações o W não é definido, e uma coluna com um
valor só tem variância zero, onde a estatística é uma divisão por zero. O
`scipy` sinaliza os dois, mas cada versão dele sinaliza de um jeito — em umas
levanta `ValueError`, em outras devolve `nan` com um aviso —, e um módulo que
dependesse de qual é o comportamento de hoje é um módulo que muda de resposta
quando o `pip` resolve outra versão.

O aviso do próprio `scipy` para n grande é capturado, e não deixado ir para o
`stderr`: um aviso impresso no meio da saída de um comando é um recado que o
usuário aprende a ignorar. Capturado aqui, ele vira aviso do FlatCap e viaja
até o manifesto junto do resto — mesma manobra que o `banco.py` faz com o
`ParserWarning` do `pandas`, **inclusive no filtro por categoria**, que é o
que faltava: um `simplefilter("always")` sem categoria recolhe qualquer aviso
que qualquer biblioteca emita dentro do bloco, e o `or capturados` que estava
aqui transformava um deles na frase «o teste rodou sobre N valores, acima de
5000» dentro do manifesto — sobre uma amostra de trinta. Uma frase falsa no
recibo da rodada é pior do que aviso nenhum.

Quando o `scipy` avisa de outra coisa, o texto dele vai junto, como ele
escreveu. O FlatCap repassa o recado; ele não inventa o motivo.

- *linha 812* — `except (ValueError, TypeError) as erro:` — pragma: no cover - as duas barreiras acima

### `def _pontos_do_qq(valores, preenchidos)`

*linha 844*

Os pontos do Q-Q e a reta de referência, calculados aqui e não no `graficos.py`.

É a mesma divisão que a Fase 5 fez com as classes do histograma, pela mesma
razão: qual quantil teórico corresponde à i-ésima observação é decisão
estatística, não de desenho. A posição usada é a de Blom, `(i − 3/8) / (n + 1/4)`
— a mesma do `scipy.stats.probplot`, para que a figura do FlatCap e a que
alguém desenhar por fora do FlatCap tenham os mesmos pontos.

**A reta passa pelos quartis**, e não é um ajuste por mínimos quadrados. É a
`qqline` do R, e a diferença aparece justamente no caso em que se consulta a
figura: um valor extremo inclina a reta dos mínimos quadrados o bastante para o
resto dos pontos parecer curvo — e o que se queria ver era o valor extremo.

Devolve vazio quando não há reta possível: menos de três valores, ou Q1 igual a
Q3, que é a variável discreta com duas ou três categorias disfarçada de número.
Sem reta a figura não sai, e o motivo vai para o manifesto — mesma decisão que
a Fase 5 tomou com os quartis que coincidem.

### `def _grafico(variavel)`

*linha 892*

O Q-Q de uma variável.

O subtítulo é `n = 180 · 12 sem informação`, o mesmo das figuras da Fase 5, e
**não** traz o W nem o valor-p. Os dois estão na tabela, que fica na mesma
seção do documento, duas linhas acima: repeti-los na figura seria publicar o
mesmo número duas vezes na mesma página — que é o argumento pelo qual a
categórica saiu sem eixo de valores.

### A leitura em palavras

### `def _leitura(assimetria, curtose, p)`

*linha 919*

O que os números dizem, em português, na última coluna da tabela.

Descreve a **forma** e o que o teste concluiu, e nunca escolhe um teste para
você. "Use Mann-Whitney" depende da comparação que se vai fazer — de quantos
grupos, pareados ou não, de que tamanho —, e este módulo olha uma coluna, não
um delineamento. Sugerir dali seria a mesma ultrapassagem que a Fase 5 recusou
quando decidiu não escrever prosa sobre os números.

A ordem das partes é a da leitura: primeiro a forma, que vale em qualquer n,
depois o veredito do teste, que não vale.

### A tabela

### `def _tabela(variaveis, total)`

*linha 962*

Uma tabela só, com uma linha por variável.

É a diferença de forma em relação à descritiva, e ela tem razão: uma tabela de
normalidade é lida **atravessando** as variáveis — "quais destas eu posso
tratar como normais?" —, e uma linha por arquivo daria doze arquivos de uma
linha e doze cabeçalhos repetidos no documento. A descritiva escreve um arquivo
por variável porque lá cada um é uma tabela de verdade.

A consequência no manifesto é a que o `colunas` da Fase 7 resolve: esta rodada
tem **um item** com muitas colunas, em vez de um item por coluna.

A primeira coluna é o **rótulo**, e não o nome da coluna do banco: é o que o
cliente lê, e é o mesmo texto que encabeça a seção da variável na descritiva.
O nome técnico está no manifesto, que é quem liga arquivo a variável.

*linha 996*

> Vazia de propósito: esta tabela não é de uma variável. É o campo que a
> linha `# variável:` do cabeçalho do `.csv` usa, e escrever ali a primeira
> das doze seria uma legenda mentindo.

### O manifesto

### `def montar_manifesto(normalidade, linhas, com_graficos)`

*linha 1033*

Traduz a rodada para o índice que o relatório vai ler.

**Um item só**, e é a novidade de forma da Fase 7. Na descritiva um item é uma
variável, porque lá cada variável é uma seção do documento com a tabela dela.
Aqui a seção é uma: uma tabela que fala de todas e um Q-Q por variável abaixo
dela. O item declara em `colunas` quais colunas do banco entraram — é o campo
que faz as conferências do relatório continuarem funcionando quando a pasta tem
mais de uma rodada.

`n` é o número de linhas do banco e `faltantes` é zero, porque a rodada cobre o
banco inteiro; o `n` que varia é o de cada variável, e ele está na tabela e nos
`detalhes`, que é onde ele quer dizer alguma coisa.

### `def _artefatos(normalidade, com_graficos)`

*linha 1130*

### `def _ambiente(com_graficos)`

*linha 1152*

As versões que produziram estes números.

O `scipy` entra aqui e **não** entra no `ambiente` da descritiva, e a assimetria
é deliberada: cada rodada declara o que ela usou. Uma descritiva que anunciasse
uma versão de `scipy` estaria dizendo que um daqueles números passou por ele, e
nenhum passou — e o `ambiente` existe justamente para responder "mudaram os
dados ou mudou a biblioteca?" sobre os números **daquele** arquivo.

O `matplotlib` só é consultado quando há gráfico, como na Fase 5: perguntar a
versão custaria importar a biblioteca que o `--sem-graficos` existe para evitar.
A `fonte` entra junto e pela mesma razão que na descritiva: ela é a que o
matplotlib resolveu, que pode não ser a que o `graficos.py` pediu.

### A lista da ficha

### `def _variaveis_pedidas(raiz)`

*linha 1190*

A lista `normalidade:` do `projeto.yaml`, quando ela existir.

Ausente ou vazia quer dizer "todas as numéricas", que é o padrão e o caso
comum: a normalidade é diagnóstico, e o diagnóstico é sobre o banco inteiro.
A lista existe para o projeto em que só algumas variáveis vão para o teste —
porque só elas entram em uma comparação depois.

Lida pelo `ficha.bloco`, e não abrindo o YAML aqui: o `ficha.py` é o único
módulo do pacote que abre o `projeto.yaml`, e é bom que continue sendo.

Formato errado recusa em vez de ignorar. Um `normalidade: idade` (um texto, não
uma lista) é engano fácil de cometer, e ignorá-lo rodaria a análise inteira
como se a linha não estivesse lá — que é o pior dos dois mundos: você escreveu,
e não valeu.

### `def _conferir_pedidas(pedidas, numericas, linhas)`

*linha 1227*

Recusa a rodada quando a lista da ficha nomeia algo que não serve.

Duas situações, e a mensagem separa as duas porque o conserto é diferente: a
variável não existe no dicionário (erro de digitação, ou coluna que sumiu do
banco) ou existe e não é `numerica` (o tipo está errado em um dos dois lugares).

### Mensagens

### `def _motivo_de_fora(linha)`

*linha 1280*

### `def _mensagem_nada_a_analisar(linhas)`

*linha 1288*

### `def _acao_do_historico(plano)`

*linha 1310*

### Leitura da série e formatação

### `def _coluna(quadro, nome)`

*linha 1336*

A coluna do banco pelo nome, ou `None`.

Pela posição, e não por `quadro[nome]`, pela mesma razão da Fase 5: nome
repetido devolveria um `DataFrame` no lugar de uma coluna.

### `def _finito(valor)`

*linha 1349*

O número, ou `None` quando ele não é um número.

O `pandas` devolve `nan` para assimetria com menos de três valores e para
curtose com menos de quatro, e `nan` impresso em uma tabela é a palavra `nan`
dentro de uma célula do Word.

### `def _arredondar(valor)`

*linha 1364*

### `def _forma(valor)`

*linha 1370*

Assimetria e curtose com sinal, sempre com as mesmas casas.

Com as casas fixas de propósito, ao contrário das estatísticas da descritiva:
esta coluna é lida **de cima para baixo**, comparando variáveis entre si, e uma
coluna em que uns valores têm casa decimal e outros não é uma coluna que não
alinha. É o mesmo argumento dos percentuais da Fase 5.

### `def _estatistica(valor)`

*linha 1384*

### `def valor_p(valor)`

*linha 1390*

O valor-p, com três casas e nunca como zero.

`< 0,001` em vez de `0,000` não é preciosismo de formatação: um valor-p é
estritamente maior que zero, e `p = 0,000` impresso em um relatório assinado é
um número que não existe. É a convenção de qualquer revista da área, e é a
única regra de formatação deste módulo que alguém vai conferir.

Pública desde a 1.5.0, com o apelido privado que este módulo usa: a associação
imprime p-valor na mesma página, e dois formatadores para o mesmo p é como um
documento sai com `< 0,001` numa tabela e `0,000` na seguinte.

### `def _integridade(confere)`

*linha 1413*

### `def _subtitulo(preenchidos, faltantes)`

*linha 1421*

## `flatcap/cruzamento.py`

`SPDX-FileCopyrightText: 2026 Matheus Fernandes` · `SPDX-License-Identifier: GPL-3.0-or-later`

*1086 linhas.*

O cruzamento — uma tabela por par de variáveis categóricas.

Responde ao passo 2b do fluxo, e é a análise mais simples da Fase 7: duas
categóricas lado a lado, cada combinação de categorias com quantos casos e o
percentual. Sem teste e sem gráfico. É o `cruz()` que se fazia à mão, dentro do
FlatCap:

    Sexo              Escolaridade   n  % dos válidos
    Feminino          Superior      15           26,8
    Feminino          Médio         12           21,4
    ...
    (sem informação)                 4              —
    Total                           60          100,0

Segue o padrão das Fases 2 a 6, decidir e escrever separados:

    plano = preparar_cruzamento(raiz)   # abre o banco, conta, não toca no disco
    executar_cruzamento(plano)          # só escreve

E, como elas, **não fala com o REDCap**. Recebe `Path`, não `Config`.

### Quais pares

Os que estiverem escritos na ficha, e só eles:

    cruzamento:
      - [sexo, escolaridade]
      - [grupo, desfecho]

Sem a lista, o comando recusa. É a assimetria com a normalidade, e é deliberada:
lá "todas as numéricas" é um padrão que não produz achado nenhum; aqui não existe
padrão razoável. Trinta categóricas dão 435 pares, e cruzar todas é trocar a
pergunta do estudo por um laço aninhado. Quais pares cruzar é decisão da reunião,
e mora onde as decisões da reunião moram.

A variável numérica de poucos valores — escala de 0 a 5, código 1/2 — entra
marcada `categorica` no dicionário. O `flatcap perfil` já propõe isso para
"inteiros pequenos que se repetem", e este módulo não precisa saber que a coluna
era número: ele obedece ao `tipo`, como a descritiva.

### A decisão central: o denominador do par

Uma tabela de cruzamento é sobre quem respondeu **as duas** perguntas. Quem
respondeu uma só não tem combinação — e, se saísse da tabela inteira, como o
`pd.crosstab` faz em silêncio, o `Total` do cruzamento ficaria menor do que o das
duas tabelas de frequência que estão duas páginas antes, no mesmo documento. Quem
somasse acharia que faltou gente.

Então:

* **o percentual é sobre quem respondeu as duas.** Os números das combinações são
  os do `cruz()`, e a coluna se chama `% dos válidos` — o mesmo nome e o mesmo
  cálculo da primeira coluna de percentual da descritiva;
* **quem não respondeu uma delas vira a linha `(sem informação)`**, e o `Total` é
  o do banco, igual ao das tabelas de frequência;
* **os faltantes são por par**, e não por lista completa do banco: o cruzamento de
  `sexo` com `escolaridade` não depende de quem respondeu `renda`.

### O que ele reaproveita, e por quê

A categoria sai escrita **igual** à da tabela de frequência da mesma variável. O
código `1` vira `Feminino` pelo rótulo do dicionário (`Linha.rotulo_de`), e uma
coluna de código que o Excel leu como decimal não sai `1.0`. As duas coisas passam
pelas mesmas funções da descritiva — `serie_de_texto` e `percentual` —, porque duas
tabelas do mesmo documento escrevendo a mesma categoria de dois jeitos é o defeito
que ninguém confere. Pelo mesmo motivo, dois códigos com o mesmo rótulo
(`1=Sim|2=Sim`) viram uma combinação só: o agrupamento que a descritiva faz é o
que o cruzamento faz.

As recusas de dicionário e de tipo também são as da descritiva, com a classe de
erro deste módulo. Se as duas discordassem, `flatcap descritiva` recusaria uma
coluna que `flatcap cruzamento` aceitaria.

### O que ele deliberadamente não faz

**Não testa independência.** Qui-quadrado e Fisher são outra análise, a
`associacao`, com os pressupostos dela — frequência esperada, tamanho da tabela —
e as recusas dela.

**Não desenha.** O `graficos.py` tem uma cor de série só, e de propósito. Um
gráfico de duas variáveis precisa de uma paleta, e essa é uma decisão de desenho
que vale para toda figura futura com mais de uma série — merece a conversa dela.

**Não põe a tabela em grade.** O formato é a lista de combinações, da mais
frequente para a menos, que é como o `cruz()` a entrega e como ela se lê: "quais
combinações são as mais comuns?".

### `SINAL`

*linha 141*

> O sinal entre os dois rótulos, no título da seção e da tabela. É o "vezes" de
> "sexo × escolaridade", que é como se fala de um cruzamento em voz alta.

### `LIMITE_COMBINACOES`

*linha 145*

> Acima disto a tabela sai inteira, e com aviso. Duas variáveis de dez categorias
> cada dão até cem combinações, e uma lista desse tamanho atravessa páginas e se
> lê mal — é o `LIMITE_BARRAS` da descritiva aplicado a outra forma. O conserto
> não é cortar a tabela: é agrupar categorias no dicionário, que é decisão sua.

### `EXEMPLO_DA_FICHA`

*linha 153*

> O exemplo que as mensagens escrevem. Um lugar só, para a recusa e o `--help`
> nunca ensinarem duas formas diferentes de escrever a mesma lista.

### `class CruzamentoError(RuntimeError)`

*linha 160*

Falha ao gerar o cruzamento, já traduzida para o usuário.

Erro próprio pela regra da casa: a CLI captura esta classe e transforma em
painel com o nome do comando que o usuário rodou. Qualquer outra exceção é bug
de verdade e deve subir com o traceback inteiro.

As recusas de dicionário e de tipo são as da descritiva — uma implementação
só —, e chegam aqui como subclasses desta porque as duas funções de lá recebem
a classe de erro como parâmetro. Ver `descritiva.conferir_dicionario`.

### `class DicionarioAusenteError(CruzamentoError)`

*linha 174*

O projeto não tem `dicionario.csv`. Não há o que obedecer.

### `class DicionarioDesatualizadoError(CruzamentoError)`

*linha 180*

O banco tem colunas que o dicionário desconhece.

### `class VariavelIncompativelError(CruzamentoError)`

*linha 186*

O dicionário declara uma variável que o banco não tem.

A mesma recusa da Fase 5, pela mesma função. Para uma categórica ela só tem uma
forma de disparar — a coluna não existe —, porque texto, número, data e lógico
viram categoria do mesmo jeito que viram na tabela de frequência.

### `class SemParesError(CruzamentoError)`

*linha 196*

A ficha não diz quais pares cruzar.

Recusa, e não uma rodada com todos os pares possíveis: ver o topo do módulo.

### `class ParInvalidoError(CruzamentoError)`

*linha 204*

A lista `cruzamento:` da ficha tem par que não serve.

Formato errado, nome que não está no dicionário, variável que não é
`categorica`, a mesma variável duas vezes ou o mesmo par duas vezes. A
mensagem lista **todos** de uma vez: descobrir o segundo depois de corrigir o
primeiro é o jeito mais lento de arrumar uma lista — a regra que a Fase 5
escreveu para as colunas incompatíveis.

### O que sai no disco

### `class Par`

*linha 220*

Um par pedido na ficha, já conferido contra o dicionário.

`linha` é a primeira coluna da tabela, `coluna` a segunda — a ordem em que os
dois nomes foram escritos na ficha.

### `class ParCruzado`

*linha 233*

Um par, contado. É uma seção do relatório.

`combinacoes` são os rótulos das duas categorias e o número de casos, na ordem
da tabela. `validos` é quem respondeu as duas, e é o denominador do percentual;
`total` é o banco inteiro, e é o `Total` da tabela.

#### `def faltantes(self)`

*linha 254*

#### `def rotulo(self)`

*linha 258*

#### `def colunas(self)`

*linha 262*

### `class ForaDoCruzamento`

*linha 267*

Uma variável do dicionário que não está em par nenhum, e por quê.

Vai para o manifesto pelo mesmo motivo da Fase 5 — "não está no relatório" e
"ninguém reparou que ela existia" são coisas diferentes. O `relatorio.py` só a
anuncia quando **nenhuma** rodada a descreve, então a lista pode ser longa sem
virar ruído no terminal de quem rodou a descritiva.

### `class Cruzamento`

*linha 283*

A rodada inteira, decidida. É daqui que saem os arquivos e o terminal.

#### `def raiz(self)`

*linha 296*

#### `def linhas(self)`

*linha 300*

#### `def tabelas(self)`

*linha 304*

#### `def colunas_usadas(self)`

*linha 308*

### `class PlanoCruzamento`

*linha 318*

Tudo o que o `cruzamento` faria, decidido e ainda não escrito.

Imutável como os planos das outras fases, e pela mesma razão: entre a simulação
e a execução ninguém altera um caminho em trânsito. A árvore que aparece no
terminal é lida deste objeto.

#### `def raiz(self)`

*linha 334*

#### `def tabelas(self)`

*linha 338*

#### `def arquivos(self)`

*linha 342*

### `class ResultadoCruzamento`

*linha 347*

O que a execução de fato escreveu.

### Casos de uso

### `def preparar_cruzamento(raiz, aba, conferir, agora)`

*linha 360*

Lê os pares da ficha, abre o banco, conta cada par e monta o plano. Não
escreve nada.

A lista da ficha é conferida **antes** de abrir o banco: um par escrito fora do
formato é o engano mais provável deste comando, e descobri-lo não deve custar a
releitura do `sha256` de um banco grande.

Args:

    raiz: a pasta do projeto (a que tem o `projeto.yaml`).
    aba: planilha do `.xlsx`, quando houver mais de uma.
    conferir: reler o `sha256` das versões e comparar com a ficha.
    agora: relógio injetável — sem ele os testes não teriam como comparar o
        nome da pasta arquivada nem o manifesto, que carregam a data.

Raises:

    FichaError, BancoError, DicionarioInvalidoError e as recusas declaradas
    acima.

### `def executar_cruzamento(plano)`

*linha 413*

Escreve o plano no disco. Não decide mais nada.

A ordem é a da Fase 5, e pelo mesmo motivo: o recibo vem depois do que ele
descreve. Arquiva a rodada anterior, cria a pasta, escreve as tabelas, e só
então o `manifesto.json` — que é o índice, e um índice que aponta para arquivo
inexistente é pior do que índice nenhum.

Cada etapa registra como voltar atrás. Uma falha no meio desfaz o que já foi
feito, inclusive devolvendo a pasta arquivada ao lugar — senão a rodada
anterior teria sumido em troca de nada. O desfazer roda para **qualquer**
exceção, como na descritiva e na normalidade desde a revisão 1.3.1, e a exceção
continua subindo inteira.

*linha 441*

> `existia` antes do `mkdir`: a pasta só entra no desfazer quando foi este
> comando que a criou. O `rmdir` é registrado **antes** dos arquivos e o
> desfazer roda ao contrário, então os arquivos saem primeiro e a pasta
> sai vazia, que é a única forma de ela sair.

### `def cruzar(banco, ficha, linhas_do_dicionario, pedidos, quando)`

*linha 487*

Conta cada par pedido, obedecendo ao dicionário. Função pura.

Separada de `preparar_cruzamento` porque é o miolo testável, como o `descrever`
da Fase 5 e o `avaliar` da normalidade: um `DataFrame` montado à mão, uma lista
de `Linha` e os pares entram, e as afirmações são sobre as tabelas — sem pasta
de projeto e sem disco.

Args:

    pedidos: os pares como a ficha os escreve — `(linha, coluna)`, pelos nomes
        das colunas do banco. É o que `pares_da_ficha` devolve.

Raises:

    SemParesError, ParInvalidoError, VariavelIncompativelError

*linha 517*

> Só as variáveis dos pares vão para a recusa, e não o dicionário inteiro. A
> conferência é a da Fase 5; o escopo é deste comando — a docstring de
> `recusar_incompativeis` diz isso com todas as letras.

### Um par

### `def _cruzar_par(quadro, par, slug, total)`

*linha 561*

Conta as combinações de um par e monta a tabela dele.

**O código conta, o rótulo imprime** — a regra do `_descrever_categorica`. Os
valores do banco passam pela `serie_de_texto` da descritiva, que é o que faz um
código lido como `1.0` virar `1`, e o `1` vira `Feminino` pelo `rotulo_de` do
dicionário. A contagem é feita **sobre os rótulos**, e é isso que junta numa
combinação só os códigos que o dicionário agrupou.

As duas séries são filtradas pela mesma máscara e depois lidas por posição: um
índice de banco com rótulo repetido não tem como parear a linha errada.

- *linha 576* — `if serie_linha is None or serie_coluna is None:` — pragma: no cover - a recusa já barrou

*linha 634*

> Vazia de propósito: esta tabela não é de uma variável, e a linha
> `# variável:` do cabeçalho do `.csv` mentiria com qualquer uma das duas.

### `def _notas(par, validos, faltantes, total)`

*linha 657*

O cabeçalho de comentário do `.csv`: de onde sai cada número da tabela.

As notas não vão para o `.docx` desde a revisão de formatação da Fase 6; elas
são para quem abre o arquivo sozinho, fora do documento, e precisa saber qual é
o denominador do percentual sem reabrir o banco.

### `def _ordem_dos_rotulos(linha)`

*linha 685*

Os rótulos na ordem declarada no dicionário — o desempate da tabela.

Frequência decrescente sozinha não é determinística: duas combinações com o
mesmo `n` sairiam na ordem em que o `Counter` as viu, que é a ordem das linhas
do banco. Desempatar pela ordem do dicionário é o que faz duas rodadas sobre o
mesmo banco darem o mesmo arquivo, e é também a ordem que a tabela de
frequência da variável usa.

### `def _posicao(ordem, rotulo)`

*linha 698*

Onde o rótulo está na ordem do dicionário; o que não foi declarado vai depois.

### Os pares da ficha

### `def pares_da_ficha(raiz)`

*linha 708*

A lista `cruzamento:` do `projeto.yaml`, conferida na forma.

Devolve vazio quando a chave não existe ou está vazia — quem recusa isso é o
`cruzar`, que tem o dicionário na mão para escrever na mensagem quais
categóricas existem. Aqui a recusa é só de formato: uma lista que não é de
pares, ou um par que não tem dois nomes.

Lida pelo `ficha.bloco`, e não abrindo o YAML aqui: o `ficha.py` é o único
módulo do pacote que abre o `projeto.yaml`, e é bom que continue sendo.

Formato errado recusa em vez de ignorar, como a lista `normalidade:`. Um par
que o comando pulasse em silêncio é o pior dos dois mundos: você escreveu, e
não valeu.

Raises:

    ParInvalidoError

### `def _conferir_pares(pedidos, linhas)`

*linha 770*

Confere cada par contra o dicionário, e recusa listando todos os problemas.

Cinco coisas podem estar erradas, e cada uma tem um conserto diferente — é por
isso que a mensagem diz qual, par a par: o nome não está no dicionário
(digitação, ou coluna que sumiu do banco); a variável está marcada `ignorar` ou
fora desta versão do banco; ela não é `categorica`; é a mesma variável duas
vezes; ou o par já foi pedido — inclusive na ordem inversa, que muda só qual
coluna vem primeiro e daria duas seções com os mesmos números no documento.

### `def _motivo_de_recusa(nome, linha)`

*linha 833*

### `def _descrever_valor(valor)`

*linha 845*

O que estava escrito, do jeito que o YAML entregou, para a mensagem mostrar.

### O manifesto

### `def montar_manifesto(cruzamento, linhas)`

*linha 861*

Traduz a rodada para o índice que o relatório vai ler.

**Um item por par**, e é a terceira forma de item do manifesto: na descritiva um
item é uma variável, na normalidade é a análise inteira, e aqui é um par. O
campo `colunas`, que a Fase 7 criou esperando exatamente este caso, diz quais
duas colunas do banco o item usou — e é ele que mantém as conferências do
relatório certas para uma seção que não é de uma variável.

`n` é o banco inteiro e `faltantes` é quem não respondeu uma das duas, que é o
que a linha `(sem informação)` da tabela mostra.

*linha 936*

> Mesmo esquema do bloco da descritiva e da normalidade: três rodadas
> com três blocos `dicionario` diferentes obrigariam quem lê a saber de
> qual análise é o arquivo antes de saber o que perguntar a ele.

### `def _ambiente()`

*linha 962*

As versões que produziram estes números.

Cada rodada declara o que ela usou. Esta não desenha e não testa nada, então
o `matplotlib` e a `fonte` saem `None` — as chaves continuam lá para o bloco
ter a mesma forma do da descritiva rodada com `--sem-graficos` —, e o `scipy`
não aparece: anunciar uma versão dele seria dizer que um destes números passou
por ele.

### Mensagens

### `def _mensagem_sem_pares(linhas)`

*linha 987*

### `def _motivo_de_fora(linha)`

*linha 1014*

### `def _acao_do_historico(plano)`

*linha 1022*

### Leitura da série

### `def _coluna(quadro, nome)`

*linha 1040*

A coluna do banco pelo nome, ou `None`.

Pela posição, e não por `quadro[nome]`, pela mesma razão da Fase 5: nome
repetido devolveria um `DataFrame` no lugar de uma coluna. É a terceira cópia
destas cinco linhas — a descritiva e a normalidade têm a delas —, e ficou assim
de propósito: é uma busca, não uma decisão de apresentação, e não tem como duas
cópias discordarem sobre um número.

### `def _integridade(confere)`

*linha 1056*

## `flatcap/associacao.py`

`SPDX-FileCopyrightText: 2026 Matheus Fernandes` · `SPDX-FileCopyrightText: 1995-2026 The R Core Team` · `SPDX-License-Identifier: GPL-3.0-or-later`

*1827 linhas.*

A associação — qui-quadrado ou exato de Fisher, escolhido pela regra de Cochran.

Responde ao passo 2b do fluxo, e é o primeiro teste de hipótese entre duas
variáveis da Fase 7. Para cada par de categóricas pedido na ficha, uma linha de
tabela:

    variável 1  variável 2     n  teste                               p-valor  V de Cramér
    Grupo       Desfecho      79  Qui-quadrado com correção de Yates    0,017         0,29
    Grupo       Complicação   80  Exato de Fisher                       0,201         0,19
    Grupo       Escolaridade  80  Exato de Fisher                       0,480         0,19
    Grupo       Faixa etária  80  Qui-quadrado                          0,596         0,11

Segue o padrão das Fases 2 a 6, decidir e escrever separados:

    plano = preparar_associacao(raiz)   # abre o banco, testa, não toca no disco
    executar_associacao(plano)          # só escreve

E, como elas, **não fala com o REDCap**. Recebe `Path`, não `Config`.

### Quais pares

Os que estiverem escritos na ficha, e só eles, em duas formas:

    associacao:
      - [sexo, desfecho]                            # par único
      - desfecho: [sexo, escolaridade, tabagismo]   # uma contra várias

A segunda é a primeira escrita três vezes: `desfecho` fica na coluna `variável 1`
e cada uma das outras entra na `variável 2`, na ordem da lista. As duas formas
podem conviver na mesma lista, e a tabela sai na ordem em que os pares foram
escritos.

Sem a lista, o comando recusa — pelo mesmo motivo do cruzamento: trinta
categóricas dão 435 pares, e testar todos é *p-hacking* feito por máquina. Qual
par testar é hipótese, e hipótese se escreve na reunião.

### A decisão central: quem escolhe o teste é a tabela

A escolha entre qui-quadrado e Fisher **não** depende de normalidade — categórica
não tem normalidade a testar, e nada aqui olha para o `normalidade.py`. Depende de
quão bem a distribuição do qui-quadrado aproxima a estatística naquela tabela, e
isso se mede pelas frequências esperadas sob independência. A regra é a de
Cochran, a mesma que o `fisher.test` do R chama de *Cochran's conditions*
(`hybridPars = c(expect = 5, percent = 80, Emin = 1)`):

* **qui-quadrado** quando nenhuma frequência esperada é menor que 1 **e** no
  máximo 20% das caselas têm esperada menor que 5;
* **exato de Fisher** em qualquer outro caso.

Numa tabela 2×2 os 20% são menos de uma casela, então a regra vira "todas as
esperadas pelo menos 5" — a forma como ela costuma ser ensinada.

A justificativa de cada escolha — a dimensão da tabela, a menor esperada e
quantas caselas ficaram abaixo de 5 — sai escrita no `.csv` e no manifesto. Um
teste escolhido sem o motivo escrito é uma decisão que ninguém consegue conferir.

### Como o R faz, e por que isso pede aritmética escrita aqui

**O qui-quadrado é o `chisq.test(x)`**, com o padrão dele, `correct = TRUE`: a
correção de continuidade de Yates entra só nas tabelas 2×2, e nunca maior do que
a própria diferença — `min(0.5, abs(x - E))`, que numa tabela em que o observado
já está a menos de meio caso do esperado dá estatística zero e p = 1. Nas maiores,
Pearson sem correção.

**O Fisher é o `fisher.test(x)`**, bilateral:

* **na 2×2**, pela distribuição hipergeométrica, somando as tabelas com
  probabilidade menor ou igual à observada, com a folga relativa de `1e-7` que o
  código do R usa para não perder, por erro de arredondamento, a tabela simétrica
  que tem exatamente a mesma probabilidade;
* **nas maiores**, **exato** pelo algoritmo de rede de Mehta e Patel (1983) — o
  FEXACT que o R chama por baixo —, com a folga de `3.45254e-7` no logaritmo que o
  FEXACT usa, e **sem simulação**.

O `scipy` faz a 2×2 do mesmo jeito. A maior, não: desde a versão 1.15 ele aceita
tabela r × c, mas calcula o p por **simulação de Monte Carlo**, sem semente — o
mesmo banco dá um p diferente a cada rodada, e diferente do que o R imprime. Numa
2×3 cujo p exato é 0,0930, cinco chamadas ao `scipy` 1.17 deram de 0,0931 a
0,0957. Um relatório que muda de número sem o banco mudar é o que este projeto
existe para impedir.

Então o cálculo exato está escrito aqui, e o `scipy` entra só na distribuição do
qui-quadrado. É a exceção à regra da normalidade — "importar a aritmética,
escrever as decisões" —, e ela tem a conferência que aquela regra pedia: o
`test_associacao.py` compara este cálculo com a força bruta, com o `scipy` na
2×2, e com os exemplos da documentação do `fisher.test` do R (`Job`, 4×4,
p = 0,7827; `MP6`, 5×7, p = 0,03929; `TeaTasting`; `Convictions`).

**O limite do cálculo exato.** Numa tabela grande com n na casa das centenas, o
número de tabelas com as mesmas margens explode. O R tem um teto para isso — o
`workspace` do `fisher.test` —, e para com `FEXACT error` quando passa dele,
mandando aumentar o `workspace` ou simular. Aqui o teto é
`LIMITE_DO_CALCULO_EXATO`, contado em operações e não em segundos, para que a
mesma tabela tenha a mesma resposta em qualquer máquina. Passou dele, a linha sai
com o p **não calculado** e um aviso dizendo o que fazer. Simular em silêncio
seria trocar o teste que você escolheu por outro.

### O que ele reaproveita, e por quê

**A categoria é a da descritiva e a do cruzamento.** Os valores passam pela
`serie_de_texto` e pelo `rotulo_de` do dicionário antes de contar — e é por isso
que dois códigos com o mesmo rótulo (`1=Sim|2=Sim`) viram **uma** linha da tabela
de contingência. O agrupamento que você faz no dicionário vale para o teste do
mesmo jeito que vale para as tabelas.

**As recusas de dicionário e de tipo são as da descritiva**, com a classe de erro
deste módulo. **O p-valor sai pela mesma função da normalidade**: três casas, e
`< 0,001` abaixo disso — nunca `0,000`.

### O que ele deliberadamente não faz

**Não imprime a tabela de contingência.** Ela é o cruzamento: os mesmos pares,
escritos na chave `cruzamento:` — lá, um par por linha —, a põem no documento. O
manifesto desta rodada guarda as contagens de cada par, para conferência.

**Não corrige para comparações múltiplas.** Cada linha é um teste, com o p dele, e
isso está escrito na nota do `.csv`. A correção é decisão sua, e depende de quais
hipóteses são confirmatórias.

**Não desenha.**

### O tamanho da associação: o V de Cramér

O p responde se há evidência de associação, e depende do n: com n grande, uma
associação irrelevante sai significante. O V responde o **tamanho** dela, de 0 a
1, e é por isso que ele sai ao lado do p — é o argumento da normalidade, de que o
valor-p sozinho não responde à pergunta. Na forma "uma contra várias" ele é o que
permite comparar os pares entre si.

Três decisões, escritas também na nota do `.csv`:

* **o X² do V é sempre o de Pearson sem correção**, qualquer que seja o teste da
  linha. É a definição, e é o que mantém o V comparável: com o X² de Yates, a
  mesma 2×2 teria um V diferente conforme o teste escolhido;
* **ele sai em toda tabela testável**, inclusive nas do Fisher e nas que passaram
  do limite do cálculo exato — o V não depende do p;
* **duas casas fixas**, que é como tamanho de efeito se escreve; o manifesto
  guarda o número inteiro, e o X² de onde ele saiu.

O que ele não faz é dizer se a associação é "pequena" ou "grande": os cortes de
Cohen dependem dos graus de liberdade, e o V superestima em tabela pequena — as
que vão para o Fisher. A leitura é sua, como a da normalidade.

### `ESPERADA_MINIMA`

*linha 201*

> A regra de Cochran. Com nome e aqui em cima, pelo motivo de sempre: número solto
> no meio de uma função é decisão que ninguém consegue rever. Os três valores são
> os `hybridPars` do `fisher.test` do R.

- *linha 204* — `ESPERADA_MINIMA = 1.0` — nenhuma esperada abaixo disto

- *linha 206* — `PROPORCAO_TOLERADA = 0.20` — no máximo esta fração das caselas abaixo de 5

### `TESTE_QUI_QUADRADO`

*linha 208*

> Os nomes que vão para a coluna `teste`.

### `FOLGA_2X2`

*linha 213*

> As folgas do R. Existem para que duas tabelas com a mesma probabilidade não
> fiquem de lados diferentes do limiar por erro de arredondamento.

- *linha 215* — `FOLGA_2X2 = 1e-7` — `relErr <- 1 + 10^(-7)` no fisher.test, relativa

- *linha 216* — `FOLGA_RXC = 3.45254e-7` — `tol` do FEXACT, somada ao logaritmo

### `LIMITE_DO_CALCULO_EXATO`

*linha 218*

> Quantas operações o cálculo exato pode gastar em uma tabela — colunas
> enumeradas mais passados levados adiante. É o papel do `workspace` do
> `fisher.test`, contado de um jeito que não depende da máquina: a mesma tabela
> tem a mesma resposta em qualquer computador. Um milhão e meio cobre os exemplos
> da documentação do R e as tabelas pequenas e médias em que a regra de Cochran
> costuma mandar para o Fisher — uma 3 × 4 com n = 400 leva uns dois segundos —,
> e limita a espera, quando a tabela não cabe, a poucos segundos.

### `CASAS_V`

*linha 227*

> O V de Cramér sai com duas casas, que é como tamanho de efeito se escreve num
> artigo; o manifesto guarda o número inteiro.

### `SINAL`

*linha 231*

> O sinal entre os dois rótulos nas notas e nos avisos. O mesmo do cruzamento.

### `EXEMPLO_DA_FICHA`

*linha 236*

> O exemplo que as mensagens escrevem. Um lugar só, para a recusa e o `--help`
> nunca ensinarem duas formas diferentes de escrever a mesma lista.

### `class AssociacaoError(RuntimeError)`

*linha 243*

Falha ao gerar a associação, já traduzida para o usuário.

Erro próprio pela regra da casa: a CLI captura esta classe e transforma em
painel com o nome do comando que o usuário rodou. Qualquer outra exceção é bug
de verdade e deve subir com o traceback inteiro.

### `class DicionarioAusenteError(AssociacaoError)`

*linha 253*

O projeto não tem `dicionario.csv`. Não há o que obedecer.

### `class DicionarioDesatualizadoError(AssociacaoError)`

*linha 259*

O banco tem colunas que o dicionário desconhece.

### `class VariavelIncompativelError(AssociacaoError)`

*linha 265*

O dicionário declara uma variável que o banco não tem.

A mesma recusa da Fase 5, pela mesma função — como no cruzamento, aplicada só
às variáveis dos pares.

### `class SemParesError(AssociacaoError)`

*linha 274*

A ficha não diz quais pares testar.

### `class ParInvalidoError(AssociacaoError)`

*linha 280*

A lista `associacao:` da ficha tem item que não serve.

Formato errado, nome fora do dicionário, variável que não é `categorica`, a
mesma variável duas vezes ou o mesmo par duas vezes. A mensagem lista **todos**
de uma vez, pela regra da Fase 5.

### `class CalculoExatoGrandeError(AssociacaoError)`

*linha 290*

A tabela passou do `LIMITE_DO_CALCULO_EXATO` no Fisher exato.

Não chega ao usuário como painel: o `associar` a captura e a linha sai com o p
não calculado e um aviso. É pública para que o `fisher_exato` possa ser usado
sozinho — em teste, ou no dia em que outra análise precisar dele.

### O que sai no disco

### `class Par`

*linha 304*

Um par pedido na ficha, já conferido contra o dicionário.

`primeira` vai para a coluna `variável 1`, e é a variável da frente na forma
"uma contra várias".

### `class Contingencia`

*linha 317*

A tabela de contingência de um par, com as caselas zeradas.

As categorias são os **rótulos** que apareceram entre os casos com as duas
respostas, na ordem do dicionário — e só elas: uma categoria declarada e sem
nenhum caso não é linha da tabela do teste, porque a frequência esperada dela
seria zero e o qui-quadrado deixaria de existir.

As caselas zeradas, ao contrário, ficam: numa tabela de contingência o zero é
informação, e é justamente o caso em que o Fisher costuma ser chamado.

#### `def n(self)`

*linha 335*

#### `def dimensoes(self)`

*linha 339*

#### `def testavel(self)`

*linha 343*

#### `def esperadas(self)`

*linha 346*

`total da linha × total da coluna ÷ n`, casela por casela.

### `class Cochran`

*linha 354*

O que a regra de Cochran olhou numa tabela, e o que ela decidiu.

- *linha 360* — `abaixo: int` — caselas com esperada menor que 5

#### `def atende(self)`

*linha 364*

Nenhuma esperada abaixo de 1, e no máximo 20% das caselas abaixo de 5.

A proporção é comparada em frações exatas, e não em ponto flutuante: com dez
caselas e duas abaixo de 5 a tabela está **exatamente** nos 20%, e atende —
uma conta em `float` poderia pôr esse caso do lado errado da fronteira.

### `class ParTestado`

*linha 378*

Um par, testado. É uma linha da tabela.

`teste` fica vazio e `p` fica `None` quando não houve teste; o motivo está em
`motivo`, e a linha **sai assim mesmo** — um par pedido que sumisse da tabela
seria a falta em que ninguém repara. `p` também fica `None` quando o Fisher foi
escolhido e passou do limite do cálculo exato: aí `teste` diz qual era, e o V de
Cramér sai assim mesmo, porque ele não depende do p.

- *linha 398* — `estatistica: float | None = None` — X², só no qui-quadrado

*linha 401*

> O V de Cramér e o X² sem correção de onde ele sai. Existem em toda tabela
> testável — inclusive nas do Fisher, e nas que passaram do limite do cálculo
> exato: o V não depende do p.

#### `def faltantes(self)`

*linha 410*

#### `def colunas(self)`

*linha 414*

#### `def rotulo(self)`

*linha 418*

#### `def testado(self)`

*linha 422*

#### `def celula_do_teste(self)`

*linha 426*

O que vai para a coluna `teste` da tabela.

O nome do teste, quando houve; e o motivo no lugar dele quando não houve,
como a coluna `leitura` da normalidade faz com o impedimento — o motivo
ocupa o lugar do resultado, e não some junto com ele.

#### `def justificativa(self)`

*linha 441*

A frase que explica a linha — a nota do `.csv` e a linha do terminal.

Uma frase só, montada aqui, para que o arquivo e a tela digam a mesma coisa
com as mesmas casas.

#### `def como_detalhe(self)`

*linha 465*

Os números deste par, para o manifesto.

A tabela de contingência vai inteira: é pouco, e é o que responde "de onde
saiu esse p?" sem reabrir o banco.

### `class ForaDaAssociacao`

*linha 497*

Uma variável do dicionário que não está em par nenhum, e por quê.

### `class Associacao`

*linha 508*

A rodada inteira, decidida. É daqui que saem os arquivos e o terminal.

#### `def raiz(self)`

*linha 522*

#### `def linhas(self)`

*linha 526*

#### `def colunas_usadas(self)`

*linha 530*

#### `def testados(self)`

*linha 539*

#### `def quantos(self, teste)`

*linha 542*

Quantos pares **foram testados** com este teste. O Fisher que passou do
limite do cálculo não conta: a soma tem de bater com `testados`.

### `class PlanoAssociacao`

*linha 551*

Tudo o que a `associacao` faria, decidido e ainda não escrito.

Imutável como os planos das outras fases, e pela mesma razão: entre a simulação
e a execução ninguém altera um caminho em trânsito.

#### `def raiz(self)`

*linha 566*

#### `def tabela(self)`

*linha 570*

#### `def arquivos(self)`

*linha 574*

### `class ResultadoAssociacao`

*linha 579*

O que a execução de fato escreveu.

### Casos de uso

### `def preparar_associacao(raiz, aba, conferir, agora)`

*linha 592*

Lê os pares da ficha, abre o banco, testa cada par e monta o plano. Não
escreve nada.

A lista da ficha é conferida **antes** de abrir o banco, como no cruzamento: um
par escrito fora do formato é o engano mais provável deste comando, e
descobri-lo não deve custar a releitura do `sha256` de um banco grande.

Raises:

    FichaError, BancoError, DicionarioInvalidoError e as recusas declaradas
    acima.

### `def executar_associacao(plano)`

*linha 638*

Escreve o plano no disco. Não decide mais nada.

A ordem é a da Fase 5: arquiva a rodada anterior, cria a pasta, escreve a
tabela, e só então o `manifesto.json` — o recibo vem depois do que ele
descreve. Uma falha no meio desfaz o que já foi feito, inclusive devolvendo a
pasta arquivada ao lugar, e a exceção continua subindo inteira.

*linha 660*

> `existia` antes do `mkdir`: a pasta só entra no desfazer quando foi este
> comando que a criou, e o `rmdir` é registrado antes dos arquivos — o
> desfazer roda ao contrário e a pasta sai vazia, a única forma de sair.

### `def associar(banco, ficha, linhas_do_dicionario, pedidos, quando, limite)`

*linha 704*

Testa cada par pedido, obedecendo ao dicionário. Função pura.

O miolo testável, como o `cruzar` do cruzamento e o `avaliar` da normalidade:
um `DataFrame` montado à mão, uma lista de `Linha` e os pares entram, e as
afirmações são sobre a tabela — sem pasta de projeto e sem disco.

Args:

    pedidos: os pares como `pares_da_ficha` os devolve — a forma "uma contra
        várias" já desdobrada, na ordem da ficha.
    limite: o `LIMITE_DO_CALCULO_EXATO`, injetável para o teste que confere o
        que acontece quando ele é atingido.

Raises:

    SemParesError, ParInvalidoError, VariavelIncompativelError

*linha 736*

> Só as variáveis dos pares vão para a recusa: a conferência é a da Fase 5, e o
> escopo é deste comando.

### Um par

### `def contingencia(quadro, primeira, segunda)`

*linha 771*

A tabela de contingência de um par, contada como o cruzamento conta.

**O código conta, o rótulo imprime** — a regra do `_cruzar_par`. Os valores
passam pela `serie_de_texto` da descritiva (o código lido como `1.0` vira `1`)
e pelo `rotulo_de` do dicionário (o `1` vira `Feminino`), e a contagem é feita
**sobre os rótulos**: dois códigos com o mesmo rótulo somam na mesma linha.

Os faltantes são por par: entra quem respondeu as duas, e ninguém mais.

- *linha 784* — `if serie_1 is None or serie_2 is None:` — pragma: no cover - a recusa já barrou

### `def _testar_par(quadro, par, total, limite)`

*linha 805*

Conta, aplica a regra de Cochran e roda o teste que ela escolheu.

### `def na_ordem_do_dicionario(observados, linha)`

*linha 886*

Os rótulos observados, na ordem declarada no dicionário; o resto depois, em
ordem alfabética.

A ordem não muda nenhum p — o qui-quadrado e o Fisher são os mesmos para
qualquer permutação de linhas e colunas —, mas muda o manifesto, e duas rodadas
sobre o mesmo banco precisam dar o mesmo arquivo.

Pública desde a 1.8.0, com o apelido privado que este módulo usa. A comparação
entre grupos põe os grupos na tabela nesta mesma ordem — e é ela que decide o
sinal da diferença de médias, o primeiro grupo menos o segundo. Uma segunda regra
de ordem seria como o `Feminino` vem antes na associação e depois na comparação,
na mesma página.

### A regra e os testes

### `def regra_de_cochran(esperadas)`

*linha 915*

Mede a tabela pela regra de Cochran. A decisão está em `Cochran.atende`.

### `def qui_quadrado(contagens)`

*linha 927*

O `chisq.test(x)` do R, com o padrão `correct = TRUE`. Devolve
`(X², graus de liberdade, p, com_yates)`.

Transcrito do código do R, linha por linha, porque é curto e porque o detalhe
está numa linha só:

    if (correct && nrow(x) == 2L && ncol(x) == 2L) {
        YATES <- min(0.5, abs(x - E))
    } else YATES <- 0
    STATISTIC <- sum((abs(x - E) - YATES)^2 / E)

A correção de Yates entra **só na 2×2**, e nunca é maior do que a própria
diferença: o `min` é sobre a tabela inteira, então quando o observado já está a
menos de meio caso do esperado a estatística dá zero e o p dá 1. O `scipy` faz
a mesma coisa desde a versão 1.7 — o teste confere os dois.

O `scipy` entra só na distribuição do qui-quadrado, e dentro da função, como no
`normalidade.py`: nenhum comando que não testa nada paga o import.

Derivado de `src/library/stats/R/chisq.test.R`, do R — (C) 1995-2013 The R
Core Team, GPL-2.0-or-later. Origem, e os direitos autorais do original: ver o
`NOTICE.md`.

### `def v_de_cramer(contagens)`

*linha 970*

O V de Cramér: `√(X² / (n · (k − 1)))`, com `k` o menor número de categorias
entre as duas variáveis.

**O X² é o de Pearson sem correção de continuidade** — o do
`chisq.test(x, correct = FALSE)` do R —, e isso vale para toda linha da tabela,
qualquer que seja o teste que a regra de Cochran escolheu para ela. É a
definição do V, e é o que o mantém comparável entre os pares: com o X² corrigido
por Yates, o V de uma 2×2 mudaria conforme o teste, e duas tabelas iguais
teriam dois tamanhos de associação.

Vai de 0 a 1, não tem sinal, e na 2×2 é o |φ|. O `min(1, …)` só segura o erro
de arredondamento de uma associação perfeita — o V nunca passa de 1.

### `def _v_de_cramer(sem_correcao, contagens)`

*linha 988*

### `def _estatistica_de_pearson(contagens, esperadas, correcao)`

*linha 994*

`Σ (|O − E| − correção)² / E` — a do qui-quadrado com Yates quando a correção
vem, e a do V de Cramér quando não vem. Uma conta só para as duas.

### `def fisher_exato(contagens, limite)`

*linha 1010*

O `fisher.test(x)` do R, bilateral: a 2×2 pela hipergeométrica, a maior pelo
algoritmo de rede, exato.

O p é a soma das probabilidades de todas as tabelas com as mesmas margens e
probabilidade **menor ou igual** à da tabela observada — a definição do R, e a
que o `test_associacao.py` confere contra a força bruta.

Raises:

    CalculoExatoGrandeError: a tabela maior que 2×2 passou do `limite`.

### `def _fisher_2x2(tabela)`

*linha 1030*

A 2×2, transcrita do `fisher.test` do R.

    m <- sum(x[, 1L]); n <- sum(x[, 2L]); k <- sum(x[1L, ]); x <- x[1L, 1L]
    lo <- max(0L, k - n); hi <- min(k, m)
    logdc <- dhyper(lo:hi, m, n, k, log = TRUE)
    d <- exp(logdc - max(logdc)); d <- d / sum(d)
    relErr <- 1 + 10^(-7)
    sum(d[d <= d[x - lo + 1] * relErr])

A normalização por `max(logdc)` antes do `exp` é a do R, e é o que mantém a
conta de pé em tabela com n na casa dos milhares.

Derivado de `src/library/stats/R/fisher.test.R`, do R — (C) 1995-2026 The R
Core Team, GPL-2.0-or-later. Origem, e os direitos autorais do original: ver o
`NOTICE.md`.

#### `def log_hiper(x)`

*linha 1052*

### `def _fisher_rede(tabela, limite)`

*linha 1067*

A tabela maior que 2×2, exata, pelo algoritmo de rede de Mehta e Patel (1983).

**A rede.** As tabelas com as margens observadas são montadas uma coluna de
cada vez. O que falta distribuir depois de k colunas — os totais de linha
restantes — é um **nó** da rede, e cada forma de preencher a coluna seguinte é
um **arco**. Toda tabela é um caminho do primeiro nó ao último, e a
probabilidade dela é o produto dos arcos: `c_j! / Π n_ij!` por coluna, vezes a
constante `Π r_i! / n!`. O que falta distribuir é guardado em ordem crescente,
porque o futuro de um nó só depende do conjunto dos totais restantes, e não de
qual linha tem qual — é o que faz caminhos diferentes se encontrarem no mesmo
nó.

**O passado.** Cada nó guarda os valores de passado que chegaram a ele, e dois
caminhos com o mesmo passado viram um só, com a massa somada.

**A poda.** Para cada nó há um teto para o melhor futuro possível e um piso
para o pior. Um passado que, somado ao melhor futuro, ainda fica abaixo do
limiar tem **todas** as continuações contando para o p — e a massa delas tem
forma fechada, `N'! / Π r'_i!`. Um que, somado ao pior futuro, fica acima, não
tem nenhuma. Só o que fica entre os dois segue para o nó seguinte.

O teto e o piso são calculados coluna por coluna, cada uma sozinha — a mais
equilibrada possível para o teto, a mais concentrada para o piso. São mais
frouxos do que os do FEXACT, que resolve a rede inteira para achá-los; o preço
é podar um pouco menos, e o ganho é não percorrer a rede toda antes de começar.
A resposta é a mesma: a poda só descarta o que tem certeza de descartar.

**A folga** é a do FEXACT, somada ao logaritmo da probabilidade observada.

As massas são guardadas já multiplicadas pelo futuro do nó — a probabilidade de
todas as tabelas que passam por ali —, e por isso ficam sempre entre 0 e 1:
nada estoura, e só some por arredondamento o que não mudaria a terceira casa de
p-valor nenhum.

*linha 1103*

> O estado da rede é a dimensão menor: menos linhas por nó, menos nós.

*linha 1118*

> As colunas maiores primeiro: é a ordem que menos nós criou nas tabelas de
> referência. A ordem não muda o p — as tabelas são as mesmas.

#### `def equilibrada(total, tetos)`

*linha 1124*

*linha 1125*

> A coluna mais equilibrada que cabe nos tetos: o maior arco possível.

- *linha 1127* — `for teto in tetos:` — em ordem crescente

#### `def concentrada(total, tetos)`

*linha 1137*

*linha 1138*

> A coluna mais concentrada que cabe nos tetos: o menor arco possível.

#### `def limites(k, resto)`

*linha 1149*

*linha 1150*

> (teto do melhor futuro, piso do pior) depois de k colunas.

- *linha 1153* — `if k == ultima:` — a última coluna é forçada: leva o que sobrou

#### `def log_futuro(resto)`

*linha 1160*

*linha 1166*

> Nó -> {passado arredondado: (passado, massa)}.

### `def _arcos(resto, total, lf)`

*linha 1220*

As formas de preencher a próxima coluna a partir de um nó, já agrupadas.

Duas colunas que levam ao mesmo nó com o mesmo arco — o que acontece sempre
que dois totais restantes são iguais — viram uma entrada só, com a
multiplicidade contada. A chave leva o arco arredondado, porque dois arcos
iguais somados em ordens diferentes podem diferir na última casa.

Devolve `{(nó seguinte, arco): quantas colunas}` — o arco da chave é o valor
exato da primeira coluna encontrada — e quantas colunas foram enumeradas, que
é o trabalho que o limite do cálculo conta.

### `def _colunas_possiveis(resto, total, lf)`

*linha 1249*

Cada forma de preencher a próxima coluna: `(nó seguinte, arco)`.

Com duas e três linhas — as tabelas 2 × k e 3 × k, as mais comuns — o laço é
escrito por extenso, porque é aqui que o cálculo passa quase todo o tempo e o
caminho genérico gasta mais montando tuplas do que fazendo conta. O genérico
serve a qualquer número de linhas, e o teste confere os dois contra a força
bruta.

### `def _esperadas(contagens)`

*linha 1304*

### `def _log_combinacoes(n, k)`

*linha 1311*

### A tabela

### `def _tabela(pares, total)`

*linha 1318*

Uma tabela só, com uma linha por par, na ordem da ficha.

As seis colunas pedidas — `variável 1`, `variável 2`, `n`, `teste`, `p-valor` e
`V de Cramér` —, com os **rótulos** do dicionário nas duas primeiras, que é o que
o cliente lê. O resto do que decide cada linha — a dimensão da tabela, a menor
esperada, quantas caselas abaixo de 5, o X² e os graus de liberdade — vai para
as notas do `.csv`, uma frase por par, e para o manifesto.

*linha 1366*

> Vazia de propósito: esta tabela fala de vários pares.

### Os pares da ficha

### `def pares_da_ficha(raiz)`

*linha 1378*

A lista `associacao:` do `projeto.yaml`, conferida na forma e desdobrada.

Duas formas de item, e as duas podem conviver:

    - [sexo, desfecho]                            # um par
    - desfecho: [sexo, escolaridade, tabagismo]   # uma contra várias

A segunda devolve um par por nome da lista, com `desfecho` na frente, na ordem
em que foram escritos. Um nome só depois dos dois-pontos (`- desfecho: sexo`)
vale como a lista de um nome.

Devolve vazio quando a chave não existe ou está vazia — quem recusa isso é o
`associar`, que tem o dicionário na mão para escrever quais categóricas
existem. Formato errado recusa em vez de ignorar: um item que o comando pulasse
em silêncio é o pior dos dois mundos — você escreveu, e não valeu.

Lida pelo `ficha.bloco`, e não abrindo o YAML aqui: o `ficha.py` é o único
módulo do pacote que abre o `projeto.yaml`.

Raises:

    ParInvalidoError

### `def _nome(valor)`

*linha 1460*

O nome de uma variável, como a ficha o trouxe; vazio quando não é um nome.

Lista e bloco dentro da lista não são nome — é o `[[sexo, desfecho]]` digitado
com um colchete a mais.

### `def _conferir_pares(pedidos, linhas)`

*linha 1472*

Confere cada par contra o dicionário, e recusa listando todos os problemas.

As mesmas cinco coisas do cruzamento, com o mesmo conserto cada uma: o nome não
está no dicionário; a variável está marcada `ignorar` ou fora desta versão do
banco; ela não é `categorica`; é a mesma variável duas vezes; ou o par já foi
pedido — inclusive na ordem inversa, ou uma vez na forma de par e outra dentro
de uma "uma contra várias". O teste é simétrico, e o mesmo par duas vezes daria
duas linhas com o mesmo p.

### `def _motivo_de_recusa(nome, linha)`

*linha 1535*

### `def _descrever_valor(valor)`

*linha 1547*

### O manifesto

### `def montar_manifesto(associacao, linhas)`

*linha 1562*

Traduz a rodada para o índice que o relatório vai ler.

**Um item só**, como na normalidade: a seção do documento é uma tabela que fala
de todos os pares. O `colunas` do item diz quais colunas do banco entraram — a
união dos pares —, que é o que mantém as conferências do relatório certas para
uma seção que não é de uma variável. Os números de cada par, com a tabela de
contingência inteira, vão em `detalhes`.

### `def _ambiente()`

*linha 1665*

As versões que produziram estes números.

O `scipy` entra, porque a distribuição do qui-quadrado é dele. O `matplotlib` e
a `fonte` saem `None` — a rodada não desenha —, e as chaves continuam lá para o
bloco ter a forma dos outros.

### Mensagens

### `def _mensagem_sem_pares(linhas)`

*linha 1690*

### `def _motivo_de_fora(linha)`

*linha 1717*

### `def _acao_do_historico(plano)`

*linha 1725*

### Leitura da série e formatação

### `def _coluna(quadro, nome)`

*linha 1750*

A coluna do banco pelo nome, ou `None` — pela posição, como nas outras
análises: nome repetido devolveria um `DataFrame` no lugar de uma coluna.

### `def _formatar_v(valor)`

*linha 1761*

O V com casas fixas: `0,10` e não `0,1`.

Casas fixas pelo motivo dos percentuais da Fase 5: a coluna é lida de cima para
baixo, comparando pares, e uma coluna em que uns valores têm duas casas e outros
uma é uma coluna que não alinha.

### `def _arredondar(valor)`

*linha 1774*

### `def _integridade(confere)`

*linha 1780*

## `flatcap/correlacao.py`

`SPDX-FileCopyrightText: 2026 Matheus Fernandes` · `SPDX-FileCopyrightText: 1995-2024 The R Core Team` · `SPDX-FileCopyrightText: 2003-2024 The R Foundation` · `SPDX-FileCopyrightText: 1975 Royal Statistical Society` · `SPDX-License-Identifier: GPL-3.0-or-later`

*2286 linhas.*

A correlação — Pearson, Spearman ou Kendall, escolhido pelos pressupostos de cada par.

Responde ao passo 2b do fluxo, e é a primeira análise entre duas numéricas da Fase
7. Para cada par pedido na ficha, uma linha de tabela:

    variável 1  variável 2    n  método    coeficiente  IC 95%         p-valor
    Idade       IMC         178  Pearson          0,31  0,17 a 0,44    < 0,001
    Idade       Renda       150  Spearman         0,12  -0,04 a 0,28     0,142
    Dor         Ansiedade   180  Kendall          0,27  0,17 a 0,36    < 0,001

E um gráfico de dispersão por par, que é a parte da verificação dos pressupostos
que nenhum teste faz: linearidade, valor extremo, grupos.

Segue o padrão das Fases 2 a 6, decidir e escrever separados:

    plano = preparar_correlacao(raiz)   # abre o banco, calcula, não toca no disco
    executar_correlacao(plano)          # só escreve

E, como elas, **não fala com o REDCap**. Recebe `Path`, não `Config`.

### Quais pares

Os que estiverem escritos na ficha, e só eles, nas duas formas da associação —
mais um terceiro nome opcional no par, que é o método:

    correlacao:
      - [idade, imc]                    # a regra escolhe o método
      - idade: [pressao, colesterol]    # uma contra várias, pela regra
      - [dor, ansiedade, kendall]       # o método escrito manda

Sem a lista, o comando recusa, pelo motivo de sempre: trinta numéricas dão 435
pares, e correlacionar tudo com tudo é *p-hacking* feito por máquina. Qual par
correlacionar é hipótese, e hipótese se escreve na reunião.

### A decisão central: a regra dos pressupostos escolhe, e a ficha pode discordar

É a pergunta que abriu esta análise — dá para escolher o coeficiente sozinho? — e
a resposta é a que a associação deu com a regra de Cochran: dá, se a regra estiver
escrita, for a mesma para todo par e deixar o motivo impresso. Três passos, nesta
ordem:

1. **Kendall** quando alguma das duas variáveis tem **até 10 valores distintos, com
   repetição** — uma escala ou um código. Numa escala de 0 a 5 a maior parte dos
   pares de casos empata, e o tau-b é o coeficiente que conta os empates na própria
   variância.
2. **Spearman** quando alguma das duas é `categorica` — ela entra pela ordem dos
   códigos, e ordem não é distância — ou quando o **Shapiro-Wilk rejeita a
   normal** em alguma das duas, sobre os casos do par.
3. **Pearson** nos outros casos: as duas contínuas, e nenhuma com a normal
   rejeitada.

O limite de 10 é o `POUCOS_DISTINTOS` da normalidade, que é o `LIMITE_UNICOS_CODIGO`
do perfil: é a mesma pergunta — isto é contínuo ou é código? — feita pela terceira
vez, e três limites para ela é como o perfil propõe uma coisa e a correlação faz
outra sobre a mesma coluna.

**O método escrito no par tem precedência.** A regra é um ponto de partida
defensável, e não um veredito, e ela tem o limite que o `normalidade.py` descreve
no topo: o p do Shapiro-Wilk depende do n. Com poucos casos ele quase não rejeita,
e a regra escolheria o Pearson por falta de evidência; com muitos ele rejeita
desvio irrelevante, e tudo vira Spearman — o que custa pouco, porque o Spearman
continua válido. Por isso três coisas saem escritas: a frase de cada escolha, com
os números que a decidiram, nas notas do `.csv` e no terminal; um aviso quando a
regra escolhe o Pearson com menos de 20 pares; e outro quando o método escrito na
ficha contraria a regra — a decisão é sua, e fica registrado que foi contra ela.

### Como o R faz

Os três são o `cor.test` do R, bilaterais, com os padrões dele:

* **Pearson**: t com n − 2 graus de liberdade. O `scipy` faz igual.
* **Spearman**: o ρ é o Pearson dos postos médios. O p é **exato** até n = 1290
  sem empates — pela contagem das permutações até n = 9 e pela série de Edgeworth
  do algoritmo AS 89 acima disso —, e pela aproximação t com empates ou acima de
  1290. **O `scipy` não faz isso**: ele usa sempre a aproximação t, e no exemplo do
  atum da documentação do R (Hollander e Wolfe, n = 9) dá p = 0,088 onde o R dá
  0,097. Então o AS 89 está transcrito aqui, do `prho.c` do R, linha por linha — a
  exceção à regra "importar a aritmética, escrever as decisões", pelo mesmo motivo
  do Fisher da associação.
* **Kendall**: o tau-b. O p é exato abaixo de n = 50 sem empates, e pela
  aproximação normal com a variância corrigida para empates nos outros casos, sem
  correção de continuidade. O `scipy` calcula os dois como o R, mas o critério
  automático dele troca de um para o outro em n = 33, e não em 50 — então quem
  escolhe é este módulo, com o critério do R.

O `test_correlacao.py` confere os três contra números tirados do próprio R.

### O intervalo de confiança

95%, pela transformação de Fisher nos três. O `cor.test` só dá intervalo para o
Pearson, com erro-padrão `1/√(n − 3)`, e é esse o daqui. Nos outros dois o
erro-padrão da transformação é outro, e usar o do Pearson daria um intervalo
estreito demais:

* Spearman: `√((1 + ρ²/2) / (n − 3))`, de Bonett e Wright (2000);
* Kendall: `√(0,437 / (n − 4))`, de Fieller, Hartley e Pearson (1957), que é o
  que Bonett e Wright recomendam.

As duas fórmulas vão para as notas do `.csv`, para o intervalo poder ser refeito
à mão.

### A categórica que entra

Uma escala marcada `categorica` no dicionário — dor de 0 a 5, um item Likert —
entra, porque é o caso típico do Spearman e do Kendall. Com três condições:

* **pela ordem numérica dos códigos**, e só se o código for número. Uma categórica
  em texto (`Fundamental`, `Médio`, `Superior`) é recusada: a ordem do
  `categorias_ordem` pode ser a de frequência, que é a que o perfil propõe, e uma
  correlação calculada sobre ela sairia com cara de resultado;
* **nunca pelo Pearson** — nem pela regra, nem escrito na ficha;
* **o agrupamento do dicionário não vale aqui**: dois códigos com o mesmo rótulo
  continuam sendo dois valores da escala. Sai um aviso dizendo isso.

Uma categórica nominal (sexo, estado civil) não tem ordem, e não tem correlação. O
FlatCap não tem como saber qual é qual, e a nota do `.csv` diz isso.

### O que ele reaproveita, e por quê

**As recusas de dicionário e de tipo são as da descritiva**, com a classe de erro
deste módulo. **O Shapiro-Wilk é o da normalidade**, pela mesma função — as
barreiras e os avisos dele valem aqui também. **O p-valor sai pela mesma função da
normalidade e da associação**: três casas, e `< 0,001` abaixo disso.

A normalidade aqui é medida **sobre os casos do par**, e não sobre a coluna
inteira, porque é sobre eles que o coeficiente é calculado. Sem faltante no par, o
p é o mesmo da tabela de normalidade; com faltante, pode ser outro, e o n do par
está na linha.

### O que ele deliberadamente não faz

**Não diz se a correlação é fraca ou forte.** Os cortes (Cohen, Mukaka) são
convenções de área, e o Kendall sai tipicamente menor que o Spearman para a mesma
relação — um corte único para os dois estaria errado para um deles. A leitura é
sua, como a do V de Cramér.

**Não corrige para comparações múltiplas.** Cada linha é um teste.

**Não desenha reta.** Ela afirma uma linearidade que o Spearman e o Kendall não
afirmam, e no Pearson repete o que o coeficiente já diz. A dispersão mostra os
pontos, e o ponto cresce onde vários casos coincidem — o que numa escala é quase
sempre.

### `PEARSON`

*linha 200*

> Os nomes que vão para a coluna `método`.

### `METODOS`

*linha 205*

> Como cada método se escreve na ficha — o terceiro nome do par. Minúsculo e sem
> acento, que é como se digita; a tabela sai com o nome próprio.

### `POUCOS_VALORES`

*linha 209*

> A regra. Todos com nome e aqui em cima, pelo motivo de sempre: número solto no
> meio de uma função é decisão que ninguém consegue rever.
>
> Até este número de valores distintos, com repetição, a variável é escala ou
> código, e o par vai para o Kendall. É o mesmo limite da normalidade e do perfil.

### `MINIMO_DE_PARES`

*linha 216*

> Abaixo disto não há teste: com dois pontos, qualquer par está sobre uma reta. É
> também o mínimo do Shapiro-Wilk e o do `cor.test` para o Pearson.

### `MAXIMO_EXATO_SPEARMAN`

*linha 220*

> Os limites do `cor.test` do R, com o nome que eles têm lá.

- *linha 221* — `MAXIMO_EXATO_SPEARMAN = 1290` — `n <= 1290`: acima disso n(n² − 1) estoura o inteiro do C

- *linha 222* — `LIMITE_EXATO_KENDALL = 50` — `exact <- (n < 50)`

- *linha 223* — `PERMUTACOES_SPEARMAN = 9` — `n_small` do `prho.c`: até aqui, a contagem exata

### `CONFIANCA`

*linha 225*

> O intervalo.

- *linha 227* — `VARIANCIA_KENDALL = 0.437` — Fieller, Hartley e Pearson (1957), com n − 4

### `CASAS_COEFICIENTE`

*linha 229*

> O coeficiente sai com duas casas, que é como correlação se escreve num artigo; o
> manifesto guarda o número inteiro.

### `SINAL`

*linha 233*

> O sinal entre os dois rótulos nas notas e nos avisos. O mesmo do cruzamento e
> da associação.

### `_EDGEWORTH`

*linha 237*

> Os coeficientes da série de Edgeworth do AS 89, como estão no `prho.c` do R —
> (C) 2000-2024 The R Core Team; ver o `NOTICE.md`.

### `EXEMPLO_DA_FICHA`

*linha 246*

> O exemplo que as mensagens escrevem. Um lugar só, para a recusa e o `--help`
> nunca ensinarem duas formas diferentes de escrever a mesma lista.

### `class CorrelacaoError(RuntimeError)`

*linha 254*

Falha ao gerar a correlação, já traduzida para o usuário.

Erro próprio pela regra da casa: a CLI captura esta classe e transforma em
painel com o nome do comando que o usuário rodou. Qualquer outra exceção é bug
de verdade e deve subir com o traceback inteiro.

### `class DicionarioAusenteError(CorrelacaoError)`

*linha 264*

O projeto não tem `dicionario.csv`. Não há o que obedecer.

### `class DicionarioDesatualizadoError(CorrelacaoError)`

*linha 270*

O banco tem colunas que o dicionário desconhece.

### `class VariavelIncompativelError(CorrelacaoError)`

*linha 276*

O dicionário promete `numerica` e a coluna chegou como texto, ou declara uma
variável que o banco não tem.

A mesma recusa da Fase 5, pela mesma função — aplicada só às variáveis dos
pares, como no cruzamento e na associação.

### `class SemParesError(CorrelacaoError)`

*linha 286*

A ficha não diz quais pares correlacionar.

### `class ParInvalidoError(CorrelacaoError)`

*linha 292*

A lista `correlacao:` da ficha tem item que não serve.

Formato errado, método que não existe, nome fora do dicionário, variável que
não é numérica nem categórica, Pearson pedido sobre uma categórica, a mesma
variável duas vezes ou o mesmo par duas vezes. A mensagem lista **todos** de
uma vez, pela regra da Fase 5.

### `class CategoricaSemCodigoError(CorrelacaoError)`

*linha 303*

Uma categórica de um par chegou em texto, e não tem ordem numérica.

Recusa, e não conversão pela ordem do `categorias_ordem`: aquela ordem pode ser
a de frequência, que é a que o perfil propõe, e uma correlação calculada sobre
ela sairia com cara de resultado.

### O que sai no disco

### `class Pedido`

*linha 317*

Um par como a ficha o escreve: dois nomes e, quando houver, o método.

`metodo` vazio quer dizer "a regra escolhe"; preenchido, é um dos três de
`METODOS`, já com o nome próprio.

### `class Par`

*linha 331*

Um par pedido na ficha, já conferido contra o dicionário.

`primeira` vai para a coluna `variável 1` e para o eixo x da dispersão, e é a
variável da frente na forma "uma contra várias".

### `class Normal`

*linha 345*

O Shapiro-Wilk de uma variável, sobre os casos do par.

Os quatro campos são o que o `normalidade.shapiro` devolve: o W e o p quando o
teste rodou, a frase do impedimento quando não rodou, e o aviso do `scipy`
quando houve um.

#### `def testada(self)`

*linha 360*

#### `def rejeita(self)`

*linha 364*

### `class Pressupostos`

*linha 369*

O que a regra olhou num par.

`normal_1` e `normal_2` ficam `None` para a categórica: ela não tem
normalidade a testar, e é a própria categoria que a manda para fora do
Pearson.

#### `def escala(self, lado)`

*linha 384*

Até `POUCOS_VALORES` valores distintos, **com repetição**.

A repetição é a metade que importa: com oito casos, uma variável contínua
tem no máximo oito valores distintos e nenhum empate — e não é escala.

### `class Escolha`

*linha 396*

Qual método rodou, e de onde ele veio.

`da_regra` é o que a regra escolheria mesmo quando a ficha mandou outro: é o
que permite escrever "contra a regra" na nota, com o motivo dela.
`pela_normalidade` diz se foi o Shapiro-Wilk que decidiu — é quando o aviso
dele, se houver, precisa ir junto.

#### `def contra_a_regra(self)`

*linha 413*

### `class Coeficiente`

*linha 418*

O resultado de um dos três, como o `cor.test` do R o devolveria.

`estatistica` é a do R: t no Pearson, S no Spearman, T (exato) ou z no Kendall
— com o nome em `nome_da_estatistica`. `calculo_do_p` diz em palavras como o p
saiu, porque no Spearman e no Kendall são dois caminhos diferentes conforme o
n e os empates.

### `class ParCorrelacionado`

*linha 439*

Um par, correlacionado. É uma linha da tabela, e uma figura.

`coeficiente` fica `None` quando não houve teste; o motivo está em `motivo`, e a
linha **sai assim mesmo** — um par pedido que sumisse da tabela seria a falta em
que ninguém repara.

*linha 462*

> Os pontos da dispersão: (x, y, quantos casos caem ali). Calculados aqui, e
> não no `graficos.py`, pela divisão de sempre — contar é deste lado.

#### `def faltantes(self)`

*linha 467*

#### `def colunas(self)`

*linha 471*

#### `def rotulo(self)`

*linha 475*

#### `def testado(self)`

*linha 479*

#### `def metodo(self)`

*linha 483*

#### `def celula_do_metodo(self)`

*linha 487*

O que vai para a coluna `método`: o nome do método, ou o motivo no lugar
dele — como a coluna `teste` da associação.

#### `def justificativa(self)`

*linha 497*

A frase que explica a linha — a nota do `.csv` e a linha do terminal.

Uma frase só, montada aqui, para que o arquivo e a tela digam a mesma coisa
com as mesmas casas.

#### `def como_detalhe(self)`

*linha 525*

Os números deste par, para o manifesto — o que responde "de onde saiu esse
método, e esse p?" sem reabrir o banco.

### `class ForaDaCorrelacao`

*linha 570*

Uma variável do dicionário que não está em par nenhum, e por quê.

### `class Correlacao`

*linha 581*

A rodada inteira, decidida. É daqui que saem os arquivos e o terminal.

#### `def raiz(self)`

*linha 596*

#### `def linhas(self)`

*linha 600*

#### `def colunas_usadas(self)`

*linha 604*

#### `def testados(self)`

*linha 613*

#### `def pela_ficha(self)`

*linha 617*

#### `def quantos(self, metodo)`

*linha 620*

### `class PlanoCorrelacao`

*linha 625*

Tudo o que a `correlacao` faria, decidido e ainda não escrito.

Imutável como os planos das outras fases, e pela mesma razão: entre a simulação
e a execução ninguém altera um caminho em trânsito.

#### `def raiz(self)`

*linha 641*

#### `def tabela(self)`

*linha 645*

#### `def graficos(self)`

*linha 649*

#### `def arquivos(self)`

*linha 653*

### `class ResultadoCorrelacao`

*linha 659*

O que a execução de fato escreveu.

### Casos de uso

### `def preparar_correlacao(raiz, aba, conferir, com_graficos, agora)`

*linha 672*

Lê os pares da ficha, abre o banco, correlaciona cada par e monta o plano. Não
escreve nada.

A lista da ficha é conferida **antes** de abrir o banco, como no cruzamento e
na associação: um par escrito fora do formato é o engano mais provável deste
comando, e descobri-lo não deve custar a releitura do `sha256` de um banco
grande.

Args:

    com_graficos: desenhar as dispersões. Desligado, os pontos nem são
        contados e o `matplotlib` nem é importado.
    agora: relógio injetável, como nas outras fases.

Raises:

    FichaError, BancoError, DicionarioInvalidoError e as recusas declaradas
    acima.

### `def executar_correlacao(plano)`

*linha 726*

Escreve o plano no disco. Não decide mais nada.

A ordem é a da Fase 5: arquiva a rodada anterior, cria a pasta, escreve a
tabela, desenha as dispersões, e só então o `manifesto.json` — o recibo vem
depois do que ele descreve. Uma falha no meio desfaz o que já foi feito,
inclusive devolvendo a pasta arquivada ao lugar, e a exceção continua subindo
inteira — o `matplotlib` incluído, que estoura com exceções próprias.

*linha 749*

> `existia` antes do `mkdir`: a pasta só entra no desfazer quando foi este
> comando que a criou, e o `rmdir` é registrado antes dos arquivos — o
> desfazer roda ao contrário e a pasta sai vazia, a única forma de sair.

*linha 764*

> O `matplotlib` entra aqui dentro, e não no topo do arquivo, pela
> mesma razão que na Fase 5: `--sem-graficos` não deve pagar por uma
> biblioteca que ele existe para não usar.

### `def correlacionar(banco, ficha, linhas_do_dicionario, pedidos, quando, com_graficos)`

*linha 805*

Correlaciona cada par pedido, obedecendo ao dicionário. Função pura.

O miolo testável, como o `associar` da associação e o `avaliar` da
normalidade: um `DataFrame` montado à mão, uma lista de `Linha` e os pares
entram, e as afirmações são sobre a tabela — sem pasta de projeto e sem disco.

Args:

    pedidos: os pares como `pares_da_ficha` os devolve — ou tuplas de dois
        nomes, ou de dois nomes e o método, que é como um teste os escreve.
    com_graficos: contar os pontos das dispersões.

Raises:

    SemParesError, ParInvalidoError, VariavelIncompativelError,
    CategoricaSemCodigoError

*linha 837*

> Só as variáveis dos pares vão para a recusa: a conferência é a da Fase 5, e o
> escopo é deste comando.

### Um par

### `def valores_do_par(quadro, par)`

*linha 889*

Os valores das duas variáveis, como número, só dos casos que responderam as
duas.

Os faltantes são **por par**: entra quem respondeu as duas, e ninguém mais —
o `complete.cases(x, y)` do `cor.test`. É o oposto do descarte por lista
completa, que faria a correlação de `idade × imc` depender de quem respondeu
`renda`.

- *linha 901* — `if serie_1 is None or serie_2 is None:` — pragma: no cover - a recusa já barrou

### `def _correlacionar_par(quadro, par, total, slug, com_graficos)`

*linha 912*

Mede os pressupostos, aplica a regra (ou obedece à ficha) e calcula.

### `def _normal(linha, valores)`

*linha 989*

O Shapiro-Wilk da normalidade, sobre os casos do par. `None` para a
categórica, que não tem normalidade a testar.

### `def _avisos_do_par(nome_do_par, escolha, pressupostos)`

*linha 1000*

O que a escolha precisa levar junto para o terminal e para o manifesto.

Três casos, e cada um é um engano conhecido:

* **Pearson pela regra com poucos pares.** Abaixo de `MINIMO_CONFIAVEL` o
  Shapiro-Wilk quase não rejeita, e a regra escolheu o Pearson por falta de
  evidência contra ele — não por evidência a favor;
* **a ficha contra a regra.** A decisão é sua, e o aviso é o registro de que
  ela foi tomada contra o que a regra diria;
* **o recado do `scipy` sobre o Shapiro-Wilk**, quando o teste participou da
  escolha — é o mesmo aviso da normalidade, repassado como ele veio.

### `def _pontos(x, y)`

*linha 1041*

Os pontos da dispersão, com quantos casos caem em cada um.

Numa escala de 0 a 5 cruzada com outra, 180 casos caem em 36 lugares, e um
ponto desenhado por cima do outro esconde exatamente o que se queria ver: onde
os casos estão. Contados aqui, o `graficos.py` só transforma a contagem em
tamanho. Em ordem, para duas rodadas darem a mesma figura.

### A regra

### `def regra(par, pressupostos)`

*linha 1059*

A regra dos pressupostos: o método que ela escolhe para o par, e o motivo.

Os três passos do topo do módulo, na ordem. O motivo é a metade da frase que
vai para as notas do `.csv` — os números que decidiram, com os rótulos do
dicionário, que é o que se lê na tabela.

Não olha o método escrito na ficha: quem o aplica é o `_correlacionar_par`, por
cima do que a regra devolveu — e é assim que a nota consegue dizer o que a
regra teria escolhido.

### `def _pela_regra(metodo, motivo, pela_normalidade)`

*linha 1127*

### Os três coeficientes, como o `cor.test` do R

### `def calcular(metodo, x, y)`

*linha 1136*

O coeficiente, o p bilateral e o intervalo do método pedido.

### `def pearson(x, y)`

*linha 1144*

O `cor.test(x, y)` do R: t com n − 2 graus de liberdade, bilateral.

    STATISTIC <- c(t = sqrt(df) * r / sqrt(1 - r^2))
    PVAL <- 2 * min(pt(STATISTIC, df), pt(STATISTIC, df, lower.tail=FALSE))

### `def spearman(x, y)`

*linha 1171*

O `cor.test(x, y, method = "spearman")` do R, bilateral.

O ρ é o Pearson dos postos médios. A estatística é o S, a soma dos quadrados das
diferenças de posto — `S = (n³ − n)(1 − ρ)/6` —, e o p vem do AS 89 quando não
há empate e n ≤ 1290, e da aproximação t nos outros casos. Transcrito do
`cor.test.R`:

    pspearman <- function(q, n, lower.tail = TRUE) {
        if(n <= 1290 && exact)
            .Call(C_pRho, round(q) + 2*lower.tail, n, lower.tail)
        else {
            den <- (n*(n^2-1))/6
            r <- 1 - q/den
            pt(r / sqrt((1 - r^2)/(n-2)), df = n-2, lower.tail = !lower.tail)
        }
    }
    p <- if(q > (n^3 - n) / 6) pspearman(q, n, lower.tail = FALSE)
         else pspearman(q, n, lower.tail = TRUE)
    min(2 * p, 1)

O `+ 2*lower.tail` não é enfeite: sem empate o S é sempre par, e é ele que
transforma o "menor que" do AS 89 no "menor ou igual" da cauda inferior.

Derivado de `src/library/stats/R/cor.test.R`, do R — (C) 1995-2022 The R Core
Team, GPL-2.0-or-later. Origem, e os direitos autorais do original: ver o
`NOTICE.md`.

#### `def cauda(inferior)`

*linha 1209*

### `def kendall(x, y)`

*linha 1239*

O `cor.test(x, y, method = "kendall")` do R, bilateral: o tau-b.

**Exato** abaixo de n = 50 sem empate — o `exact <- (n < 50)` do R —, pela
distribuição do número de pares concordantes, que é a que o `scipy` calcula
quando se pede `method="exact"`. Nos outros casos, pela aproximação normal com a
variância corrigida para empates, sem correção de continuidade, transcrita do
`cor.test.R`:

    S <- r * sqrt((T0 - T1) * (T0 - T2))
    var_S <- (v0 - vt - vu) / 18 +
        v1 / (2 * n * (n - 1)) +
            v2 / (9 * n * (n - 1) * (n - 2))
    STATISTIC <- c(z = S / sqrt(var_S))

O `scipy` sabe fazer os dois; o critério automático dele é que é outro — ele
passa para a aproximação acima de n = 33. Quem escolhe aqui é o critério do R.

Derivado de `src/library/stats/R/cor.test.R`, do R — (C) 1995-2022 The R Core
Team, GPL-2.0-or-later. Origem, e os direitos autorais do original: ver o
`NOTICE.md`.

*linha 1274*

> O T do R: quantos dos n(n − 1)/2 pares são concordantes.

### `def prho(n, s, inferior)`

*linha 1299*

O AS 89 (Best e Roberts, 1975), como o `prho.c` do R: `Pr[S ≥ s]`, ou
`Pr[S < s]` quando `inferior`.

Até n = 9, **exato**: a proporção das n! permutações com S do lado pedido — o R
chama esse limite de `n_small`, e ele era 6 no algoritmo original. Acima disso,
a série de Edgeworth, com os doze coeficientes do artigo:

    x = (6 (s − 1) / (n (n² − 1)) − 1) · √(n − 1)
    u = x/n · (c1 + (c2 + c3/n)/n + x² (−c4 + (c5 + c6/n)/n
          − x²/n (c7 + c8/n − x² (c9 − c10/n + x²/n (c11 − c12 x²)))))
    p = ± u · e^(−x²/2) + Φ(x)

Transcrito linha por linha, inclusive nas duas saídas do começo — `s ≤ 0` e `s`
acima do máximo — e no corte do fim em [0, 1], e conferido contra o R.

Derivado de `src/library/stats/src/prho.c`, do R — (C) 2000-2024 The R Core
Team e (C) 2003-2024 The R Foundation, GPL-2.0-or-later —, que se baseia no
AS 89, (C) 1975 Royal Statistical Society. Origem, e os direitos autorais
do original: ver o `NOTICE.md`.

### `def _permutacoes_por_s(n)`

*linha 1359*

Quantas das n! permutações dão cada valor de S = Σ (i − σ(i))².

Contadas uma vez por n e guardadas: com n = 9 são 362.880 permutações, e a
mesma rodada pode ter vários pares pequenos.

### `def intervalo(metodo, coeficiente, n)`

*linha 1375*

O intervalo de 95% pela transformação de Fisher: `tanh(atanh(r) ± z · EP)`.

O erro-padrão é o que muda de um método para o outro:

* Pearson: `1/√(n − 3)` — o do `cor.test` do R;
* Spearman: `√((1 + ρ²/2)/(n − 3))` — Bonett e Wright (2000);
* Kendall: `√(0,437/(n − 4))` — Fieller, Hartley e Pearson (1957).

`None` quando o n não dá: até 3 casos no Pearson e no Spearman — o R também
não dá intervalo aí —, e até 4 no Kendall. Com o coeficiente em ±1 a
transformação vai ao infinito, e o intervalo é o próprio ponto, como no R.

### `def _vetores(x, y)`

*linha 1410*

As duas variáveis como vetores, com as três condições do cálculo conferidas.

Quem chega aqui pelo `_correlacionar_par` já passou por elas, uma a uma, com a
frase de cada impedimento. O `ValueError` é para quem chamar os três métodos
direto — em teste, ou no dia em que outra análise precisar deles —, e é erro
de programação: dado que não dá correlação não é resultado.

### `def _correlacao_linear(x, y)`

*linha 1432*

O r de Pearson, preso em [−1, 1] contra o arredondamento de uma relação
perfeita.

### `def _t_de(r, gl)`

*linha 1442*

### `def _tem_empates(x, y)`

*linha 1448*

O `TIES` do R: alguma das duas tem valor repetido.

### `def _z_de_kendall(x, y, tau)`

*linha 1456*

### A tabela e a figura

### `def _tabela(pares, total)`

*linha 1482*

Uma tabela só, com uma linha por par, na ordem da ficha.

As sete colunas — `variável 1`, `variável 2`, `n`, `método`, `coeficiente`,
`IC 95%` e `p-valor` —, com os **rótulos** do dicionário nas duas primeiras. O
que decidiu cada método — os valores distintos, os p do Shapiro-Wilk — vai para
as notas do `.csv`, uma frase por par, e para o manifesto.

*linha 1536*

> Vazia de propósito: esta tabela fala de vários pares.

### `def _grafico(par)`

*linha 1553*

A dispersão de um par: a primeira variável no eixo x, a segunda no y.

O subtítulo é o `n = 178 · 2 sem informação` das outras figuras, e **não** traz
o coeficiente nem o p: os dois estão na tabela da mesma seção, e repeti-los na
figura seria publicar o mesmo número duas vezes na mesma página — o argumento
do Q-Q. Quando algum ponto junta mais de um caso, o subtítulo diz o que o
tamanho do ponto quer dizer, porque o documento impresso não tem legenda
interativa.

*linha 1572*

> Vazia pelo motivo da tabela: a figura é de um par.

### Os pares da ficha

### `def pares_da_ficha(raiz)`

*linha 1587*

A lista `correlacao:` do `projeto.yaml`, conferida na forma e desdobrada.

Três formas de item, e todas podem conviver:

    - [idade, imc]                    # um par; a regra escolhe o método
    - [dor, ansiedade, kendall]       # um par, com o método
    - idade: [pressao, colesterol]    # uma contra várias; a regra escolhe

A terceira devolve um par por nome da lista, com `idade` na frente, na ordem em
que foram escritos. O método só se escreve na forma de par: numa "uma contra
várias" ele ficaria misturado aos nomes, e `idade: [imc, spearman]` é
exatamente o que se escreve querendo uma coisa e dizendo outra.

Devolve vazio quando a chave não existe ou está vazia — quem recusa isso é o
`correlacionar`, que tem o dicionário na mão para escrever quais variáveis
existem. Formato errado recusa em vez de ignorar: um item que o comando pulasse
em silêncio é o pior dos dois mundos — você escreveu, e não valeu.

Lida pelo `ficha.bloco`, e não abrindo o YAML aqui: o `ficha.py` é o único
módulo do pacote que abre o `projeto.yaml`.

Raises:

    ParInvalidoError

### `def metodo_escrito(texto)`

*linha 1681*

O método como a tabela o escreve, a partir de como ele foi digitado na ficha;
vazio quando o texto não é um método.

Tolerante na leitura, como o dicionário: `Spearman`, `SPEARMAN` e `spearman`
são o mesmo, e o acento de quem escreveu `Pearsón` por engano não conta.

### `def _o_que_falta(nomes)`

*linha 1694*

### `def _como_pedido(item)`

*linha 1711*

### `def _nome(valor)`

*linha 1721*

O nome de uma variável, como a ficha o trouxe; vazio quando não é um nome.

Lista e bloco dentro da lista não são nome — é o `[[idade, imc]]` digitado com
um colchete a mais.

### `def _conferir_pares(pedidos, linhas)`

*linha 1733*

Confere cada par contra o dicionário, e recusa listando todos os problemas.

As cinco coisas da associação, mais uma: o nome não está no dicionário; a
variável está marcada `ignorar` ou fora desta versão do banco; ela não é
numérica nem categórica; é a mesma variável duas vezes; o par já foi pedido —
inclusive na ordem inversa, ou com outro método, que seria correlacionar o
mesmo par duas vezes e ficar com o p que convier. E a sexta: Pearson escrito
sobre uma categórica, que só tem ordem.

### `def _motivo_de_recusa(nome, linha)`

*linha 1809*

### `def _conferir_codigos(quadro, envolvidas)`

*linha 1821*

Recusa a rodada quando uma categórica de um par chegou em texto.

Depois do banco aberto, porque a pergunta é sobre a coluna: `1`, `2`, `3` têm
ordem; `Fundamental`, `Médio`, `Superior` também têm, mas ela não está em lugar
nenhum que o FlatCap possa ler sem adivinhar.

- *linha 1834* — `if serie is None:` — pragma: no cover - `recusar_incompativeis` já barrou

### `def _e_codigo_numerico(serie)`

*linha 1859*

### `def _avisos_de_agrupamento(envolvidas)`

*linha 1865*

Uma frase por categórica cujo dicionário junta dois códigos num rótulo só.

Na tabela de frequência, `1=Discordo|2=Discordo` é uma linha só, e na
associação também. Aqui não: a correlação usa a escala como ela está no banco,
e o 1 continua abaixo do 2. É aviso, e não recusa, porque o resultado está
certo — o que muda é o que se esperava dele.

### `def _descrever_valor(valor)`

*linha 1893*

### O manifesto

### `def montar_manifesto(correlacao, linhas, com_graficos)`

*linha 1908*

Traduz a rodada para o índice que o relatório vai ler.

**Um item só**, como na normalidade e na associação: a seção do documento é
uma tabela que fala de todos os pares, e uma dispersão por par abaixo dela. O
`colunas` do item diz quais colunas do banco entraram — a união dos pares —,
que é o que mantém as conferências do relatório certas para uma seção que não é
de uma variável. O que decidiu cada método vai em `detalhes`.

### `def _ambiente(com_graficos)`

*linha 2041*

As versões que produziram estes números.

O `scipy` entra, porque as distribuições são dele. O `matplotlib` e a `fonte`
só quando há figura, como na normalidade: perguntar a versão custaria importar
a biblioteca que o `--sem-graficos` existe para evitar.

### Mensagens

### `def _mensagem_sem_pares(linhas)`

*linha 2072*

### `def _motivo_de_fora(linha)`

*linha 2100*

### `def _acao_do_historico(plano)`

*linha 2108*

### Leitura da série e formatação

### `def _coluna(quadro, nome)`

*linha 2137*

A coluna do banco pelo nome, ou `None` — pela posição, como nas outras
análises: nome repetido devolveria um `DataFrame` no lugar de uma coluna.

### `def _rotulo(linha)`

*linha 2148*

### `def _p_na_frase(p, com_nome)`

*linha 2152*

O p dentro de uma frase: `p = 0,412`, ou `p < 0,001` — nunca `p = < 0,001`.

### `def _estatistica_em_texto(coeficiente)`

*linha 2162*

### `def _normal_como_detalhe(normal)`

*linha 2171*

### `def _formatar_coeficiente(valor)`

*linha 2182*

O coeficiente com duas casas fixas e o sinal quando é negativo: `0,45` e
`-0,45`, nunca `-0,00`.

Casas fixas pelo motivo do V de Cramér: a coluna é lida de cima para baixo. O
sinal é o hífen do teclado, e não o `−` tipográfico, para o Excel em português
ler a célula como número quando alguém abrir o `.csv`.

### `def _formatar_intervalo(intervalo_)`

*linha 2199*

### `def _encurtar(texto, limite)`

*linha 2206*

### `def _arredondar(valor)`

*linha 2210*

### `def _significativos(valor)`

*linha 2217*

O p no manifesto, com seis algarismos significativos, e não seis casas.

Com seis casas, um p de 2,5e-08 é gravado como `0.0` — o número que o
`valor_p` existe para nunca escrever na tabela, escrito no recibo da rodada.

### `def _integridade(confere)`

*linha 2230*

## `flatcap/hipoteses.py`

`SPDX-FileCopyrightText: 2026 Matheus Fernandes` · `SPDX-FileCopyrightText: 1995-2024 The R Core Team` · `SPDX-FileCopyrightText: 1998 B. D. Ripley` · `SPDX-License-Identifier: GPL-3.0-or-later`

*1471 linhas.*

A aritmética dos testes de hipótese — como o R os calcula, e mais nada.

Recebe números e devolve um `Resultado`. Não sabe o que é ficha, dicionário, banco,
manifesto nem formatação: quem decide **qual** teste rodar, sobre **quais** valores,
e o que escrever na tabela é o `comparacao.py`. Este módulo responde uma pergunta
só — "dado este vetor e esta referência, o que o R diria?" — e responde do mesmo
jeito para qualquer análise que um dia precisar dele.

### Por que a aritmética mora fora da análise

Na correlação e na associação a conta ficou dentro do módulo da análise, e lá
funcionou: cada uma tem uma pergunta e três ou dois métodos. A comparação vai
crescer em outra direção — uma amostra, pareado, dois grupos, k grupos, cada um com
um teste paramétrico e um sem o pressuposto da normal —, e três coisas pedem a
fronteira:

* **o pareado é a uma amostra sobre as diferenças.** `t.test(x, y, paired = TRUE)`
  é `t.test(x - y, mu = 0)`, e o Wilcoxon pareado é o de uma amostra sobre `x - y`.
  O motor que entra agora é o do pareado depois, e ele precisa estar num lugar que
  os dois delineamentos alcancem;
* **o `test_hipoteses.py` confere contra o R sem projeto, banco nem ficha.** A
  referência entra, o número sai — é onde cabem os valores do R que cada teste novo
  traz;
* **o `comparacao.py` não vira um arquivo de cinco mil linhas** quando a lista de
  testes estiver inteira.

É o "importar a aritmética, escrever as decisões" da normalidade, virando fronteira
de arquivo.

### O `Resultado` é o `htest` do R

`t.test`, `wilcox.test`, `oneway.test`, `kruskal.test` e `friedman.test` devolvem o
mesmo objeto — `statistic`, `parameter`, `p.value`, `conf.int`, `estimate`,
`null.value` e `method` —, e é por isso que ele serve de contrato para todos os testes
de comparação. Os campos do `Resultado` são esses, com os nomes da casa. O
`Coeficiente` da correlação já era quase ele.

**Sempre bilateral.** Como na correlação: um teste unilateral escolhido depois de
olhar os dados é o p dividido por dois, e a ficha não tem como dizer que a direção
foi decidida antes.

### Os testes de postos

Os quatro que dispensam a normal — o Wilcoxon de uma amostra, o Mann-Whitney, o
Kruskal-Wallis e o Friedman — trocam os valores pelos postos deles, com o posto médio
nos empates, como o `rank` do R. Os dois primeiros são o `wilcox.test` do R, e os dois
saem **com a estimativa e o intervalo**, o `conf.int = TRUE` — que não é o padrão do
R, e é o que dá o tamanho do efeito na unidade da variável, como o intervalo do t: a
pseudomediana de Hodges-Lehmann no Wilcoxon, a diferença de locação no Mann-Whitney.
O Kruskal-Wallis e o Friedman não estimam nada, como a ANOVA.

**O caminho do p é a escolha do R, escrita**: exato — pela distribuição do posto
sinalizado ou da soma dos postos — com menos de 50 valores (na uma amostra, os que não
são iguais à referência; no Mann-Whitney, em cada grupo), sem empate e sem zero; nos
outros casos, a aproximação normal, com a variância corrigida para os empates e a
correção de continuidade. O Kruskal-Wallis e o Friedman só têm a aproximação do
qui-quadrado, no R e aqui.

### Quando importar, e quando escrever

A régua é a que a Fase 7 aprendeu teste a teste, em três degraus:

1. **o `scipy` faz o que o R faz** → importar. É o caso do t: `ttest_1samp`,
   `ttest_ind` e o `confidence_interval()` deles dão o t, os graus de liberdade, o p e
   o intervalo do `t.test`, conferidos até a décima quarta casa — no de duas amostras,
   inclusive com um grupo de um valor só. E do Kruskal-Wallis: o `kruskal` dá o
   qui-quadrado e o p do `kruskal.test`, com a mesma correção para empates;
2. **o `scipy` dá o número, mas não tudo o que vai para a tabela** → escrever a
   fórmula, e do `scipy` importar só a cauda. O `f_oneway` dá o F e o p do
   `oneway.test`, mas não os graus de liberdade: ver `anova_de_um_fator`. O
   `friedmanchisquare` dá o qui-quadrado do `friedman.test`, mas recusa duas medidas,
   que o R aceita: ver `friedman`. A função do `scipy` fica nos testes, como
   conferência;
3. **nem isso basta** → transcrever a aritmética do R, como o AS 89 do Spearman e o
   algoritmo de rede do Fisher — e a ANOVA de medidas repetidas, que o `scipy` não
   tem: ver `anova_de_medidas_repetidas`. **O Wilcoxon e o Mann-Whitney estão aqui**,
   e não no segundo degrau, como o desenho previa: o `wilcoxon` e o `mannwhitneyu` do
   `scipy` dão o p do R quando recebem a escolha do R, mas o intervalo pede os quantis
   das distribuições exatas — que o `scipy` não expõe — e, no caminho aproximado, a
   busca de raiz do `wilcox.test`, que o R faz com o `uniroot`. As distribuições são
   contadas aqui, em inteiros, e servem ao p e ao intervalo ao mesmo tempo; a busca é
   o `uniroot` do R transcrito: ver `_raiz`.

### O que ele recusa

Com `ValueError`, e só o que o próprio R recusa: menos de dois valores (`not enough
'x' observations`), valores que não variam (`data are essentially constant`), e
valor ausente ou infinito no vetor. No t de Student de duas amostras, o mínimo é o do
R para ele: um valor em cada grupo e três no total (`not enough observations`); no de
Welch, dois em cada grupo (`not enough 'x' observations`), porque cada grupo entra com
a sua variância, e a de um valor só não existe; na ANOVA — as duas —, dois em cada grupo
também, que é o `not enough observations` do `oneway.test`; nas medidas repetidas, dois
casos com todas as medidas. Nos testes de postos, os mínimos do R são menores — um
valor no Wilcoxon, um em cada grupo no Mann-Whitney e no Kruskal-Wallis; no Friedman,
dois casos, como na ANOVA —, e as barreiras que o R não tem são as do resultado sem
sentido, onde ele devolve `NaN`: todos os valores iguais à referência no Wilcoxon,
todos iguais no Kruskal-Wallis, e cada caso com as medidas todas iguais no Friedman. Quem
chega aqui pelo `comparacao.py` já passou por essas barreiras, uma a uma, com a frase
de cada uma na tabela; o `ValueError` é para quem chamar a função direto — em teste,
ou no dia em que outra análise precisar dela —, e é erro de programação: dado que não
dá teste não é resultado.

**Nenhuma função daqui começa com `test`.** `t_uma_amostra`, e não `teste_t`: o
`pytest` coleta como caso de teste qualquer objeto `test*` importado num arquivo de
teste, que é a armadilha em que o `testar` da normalidade caiu antes de virar
`avaliar`.

O `scipy` é importado **dentro** de cada função, como no resto do pacote: nenhum
comando que não faz teste deve pagar o import. O `numpy` não é dependência nova — o
`pandas` já o exige.

### `CONFIANCA`

*linha 130*

> O nível do intervalo. O mesmo 95% da correlação e do `conf.level` padrão do R.

### `MINIMO_T`

*linha 133*

> O menor número de valores com que o `t.test` do R calcula o t de uma amostra.

### `MINIMO_STUDENT`

*linha 136*

> O menor número de valores, somados os dois grupos, com que o `t.test` do R calcula o
> t de Student de duas amostras: um em cada grupo, e um grau de liberdade que sobre.

### `T_DE_STUDENT`

*linha 140*

> O nome de cada teste, como ele vai para a coluna `teste` da tabela. É o `method`
> do `htest`, em português — e, nos testes de postos, o nome pelo qual cada um é
> conhecido: o `wilcox.test` de duas amostras, que o R chama de soma de postos de
> Wilcoxon, é o Mann-Whitney.

### `LIMITE_DO_EXATO`

*linha 154*

> O `exact <- (n < 50)` do `wilcox.test` do R: com menos valores do que isto — na uma
> amostra, os que não são iguais à referência; no Mann-Whitney, em cada grupo —, sem
> empate e sem zero, o p é exato; nos outros casos, a aproximação normal.

### `TOLERANCIA_DA_RAIZ`

*linha 159*

> A busca do intervalo e da estimativa no caminho aproximado: o `tol.root = 1e-4` do
> `wilcox.test` e o `maxiter = 1000` do `uniroot`. O intervalo aproximado do R é exato
> até essa tolerância, e não além dela — e o daqui é o mesmo número, e não um melhor.

### `class Resultado`

*linha 167*

O que um teste de hipótese devolve — o `htest` do R, com os nomes da casa.

`estatistica` é a do R, com o nome dela em `nome_da_estatistica`: t no t de
Student, V no Wilcoxon, W no Mann-Whitney, F na ANOVA, o qui-quadrado no
Kruskal-Wallis e no Friedman. `gl` é uma tupla porque o número de graus de
liberdade muda de teste para teste: `(14.0,)` no t, fracionário no de Welch,
`(2.0, 25.0)` na ANOVA, vazio no Wilcoxon e no Mann-Whitney. `calculo_do_p` diz em
palavras como o p saiu, porque nos testes de postos são dois caminhos conforme o n
e os empates; `exato` diz qual deles — o `exact` do `method` do R —, e fica `None`
nos testes que só têm um.

`estimativa` é o que o teste estima — a média, a diferença de médias, a
pseudomediana —, com o nome em `nome_da_estimativa`; `ic` é o intervalo dela,
como o `conf.int` do R, e `confianca_do_ic`, o nível dele — o 95% pedido, ou menos,
quando o R não o alcança: com poucos valores, a distribuição exata não tem um
intervalo de 95%, e o R devolve o de nível mais alto que ela tem, com um aviso.
`referencia` é o `mu` da hipótese nula.

`epsilon` é o ε de Greenhouse-Geisser das medidas repetidas — o quanto a correção
encolheu os graus de liberdade, que em `gl` já saem corrigidos. É o único campo que
não está no `htest`: o R o dá no `anova.mlm`, que não é um.

### O t de Student

### `def t_uma_amostra(x, mu)`

*linha 210*

O `t.test(x, mu = mu)` do R: bilateral, t com n − 1 graus de liberdade e o
intervalo de 95% **da média** — não da diferença para a referência, que é como o
R o dá na uma amostra.

    t = (média − mu) / (DP / √n)
    IC = média ± t(0,975; n − 1) · DP / √n

Pelo `scipy`, que faz o mesmo que o R aqui: é o primeiro degrau da régua do topo
do módulo.

Raises:

    ValueError: menos de dois valores, valores que não variam, valor ausente ou
        infinito, ou referência que não é um número finito.

### `def t_de_student(x, y)`

*linha 257*

O `t.test(x, y, var.equal = TRUE)` do R: duas amostras independentes, a variância
dos dois grupos combinada, bilateral, n₁ + n₂ − 2 graus de liberdade, e o intervalo
de 95% **da diferença das médias**, `média(x) − média(y)` — a ordem dos dois
vetores é a do sinal.

    s² = [(n₁ − 1) s₁² + (n₂ − 1) s₂²] / (n₁ + n₂ − 2)
    t  = (x̄ − ȳ) / √[s² (1/n₁ + 1/n₂)]

Pelo `scipy`, como o de uma amostra: `ttest_ind(equal_var=True)` e o
`confidence_interval()` dele dão o t, os gl, o p e os dois limites do R. Conferido
também no caso de canto que o R aceita e o de Welch não: um grupo de um valor só,
em que a variância combinada é toda do outro grupo.

Raises:

    ValueError: grupo vazio, menos de três valores somados os dois grupos, valores
        que não variam, ou valor ausente ou infinito.

### `def t_de_welch(x, y)`

*linha 310*

O `t.test(x, y)` do R — o padrão dele, `var.equal = FALSE`: cada grupo com a sua
variância, bilateral, os graus de liberdade de Welch-Satterthwaite, fracionários, e
o intervalo de 95% da diferença das médias, `média(x) − média(y)`.

    t  = (x̄ − ȳ) / √(s₁²/n₁ + s₂²/n₂)
    gl = (s₁²/n₁ + s₂²/n₂)² / [(s₁²/n₁)² / (n₁ − 1) + (s₂²/n₂)² / (n₂ − 1)]

Pelo `scipy`, `ttest_ind(equal_var=False)`, que dá os gl fracionários, o p e o
intervalo do R — o primeiro degrau da régua. Um grupo que não varia entra com
variância zero, e o t existe, com os gl do outro grupo: o R calcula, e aqui também.

Raises:

    ValueError: menos de dois valores em algum grupo, valores que não variam, ou
        valor ausente ou infinito.

### A ANOVA

### `def anova_de_um_fator(grupos)`

*linha 360*

O `oneway.test(y ~ g, var.equal = TRUE)` do R — a ANOVA de um fator, a clássica: a
variância dentro dos grupos combinada, e o F com k − 1 e N − k graus de liberdade.

    F = [Σ nᵢ (x̄ᵢ − x̄)² / (k − 1)] / [Σ (nᵢ − 1) sᵢ² / (N − k)]

É o `aov` também, sempre que cada grupo tem dois valores ou mais — o `oneway.test`
recusa grupo de um valor, e o `aov` não; a régua aqui é o primeiro, que é o mesmo
da ANOVA de Welch.

**Escrita, e não importada.** O `f_oneway` do `scipy` dá o F e o p do R, mas não
devolve os graus de liberdade, e eles vão para a nota da tabela. Com a fórmula do
`oneway.test` escrita aqui — são quatro linhas —, os gl impressos são os mesmos que
deram o p, e não uma segunda conta ao lado da do `scipy`; o `f_oneway` fica nos
testes, como conferência. Do `scipy` vem só a cauda da F.

Raises:

    ValueError: menos de dois grupos, menos de dois valores em algum grupo, valores
        que não variam dentro dos grupos, ou valor ausente ou infinito.

### `def anova_de_welch(grupos)`

*linha 411*

O `oneway.test(y ~ g)` do R — o padrão dele, `var.equal = FALSE`: cada grupo pesado
pelo inverso da variância da sua média, e os graus de liberdade do denominador pela
aproximação de Welch (1951), fracionários.

    wᵢ = nᵢ / sᵢ²            x̃ = Σ wᵢ x̄ᵢ / Σ wᵢ
    λ  = Σ [(1 − wᵢ / Σw)² / (nᵢ − 1)] / (k² − 1)
    F  = [Σ wᵢ (x̄ᵢ − x̃)² / (k − 1)] / [1 + 2 (k − 2) λ]
    gl = k − 1  e  1 / (3 λ)

Escrita pela mesma razão da clássica: o `f_oneway(equal_var=False)` do `scipy` dá o
F e o p do R, e não os graus de liberdade — que aqui, além de irem para a nota, são
fracionários e ninguém os adivinha. Com dois grupos, o F é o t de Welch ao quadrado,
com os mesmos gl.

Raises:

    ValueError: menos de dois grupos, menos de dois valores em algum grupo, um grupo
        que não varia — onde o R devolve `NaN` —, ou valor ausente ou infinito.

### `def anova_de_medidas_repetidas(medidas)`

*linha 462*

A ANOVA de um fator de medidas repetidas — as mesmas pessoas medidas k vezes —,
**sempre com a correção de Greenhouse-Geisser**: o `anova(lm(Y ~ 1), X = ~1,
test = "Spherical")` do R, a coluna `G-G Pr`. É o F do `aov(y ~ tempo +
Error(id / tempo))`, com os graus de liberdade multiplicados pelo ε.

    SS_medidas = n Σ (x̄ⱼ − x̄)²                      gl = k − 1
    SS_erro    = Σ (xᵢⱼ − x̄ᵢ − x̄ⱼ + x̄)²             gl = (n − 1)(k − 1)
    F          = [SS_medidas / (k − 1)] / [SS_erro / (n − 1)(k − 1)]
    ε          = (tr D)² / [(k − 1) tr D²],  D = a covariância das medidas centrada
                 nas linhas e nas colunas
    p          = cauda da F com ε (k − 1) e ε (n − 1)(k − 1) graus de liberdade

**Greenhouse-Geisser sempre, e sem o Mauchly antes**, pela razão do Welch: a
correção custa pouco quando a esfericidade vale, protege quando não vale, e tira um
teste preliminar da frente do teste que interessa. Com a esfericidade perfeita, ε
é 1 e o p é o da ANOVA sem correção.

**Transcrita, e não importada**: o `scipy` não tem ANOVA de medidas repetidas — é
o terceiro degrau da régua do topo. Do `scipy` vem só a cauda da F. Derivada do
`anova.mlm`, em `src/library/stats/R/mlm.R`, do R — (C) 1998-2018 The R Core Team
e (C) 1998 B. D. Ripley, GPL-2.0-or-later. Origem, e os direitos autorais do
original: ver o `NOTICE.md`.

`medidas` são as k colunas, cada uma com os mesmos n casos, na mesma ordem: quem
chama tira antes os casos com alguma medida faltando, como o `lm` do R faz.

Raises:

    ValueError: menos de duas medidas, medidas de tamanhos diferentes, menos de dois
        casos, medidas que não variam dentro dos casos, ou valor ausente ou
        infinito.

### `def sem_variacao_entre_medidas(medidas)`

*linha 539*

As medidas não variam dentro dos casos: cada caso muda o mesmo tanto de uma medida
para outra, ou não muda nada.

Aí a variação que sobra depois de tirar a média de cada caso e a de cada medida é
zero, e o F é uma divisão por zero. O R não barra: devolve um F de 10²³ feito de
ruído de arredondamento, ou um F de 72 para medidas idênticas — conferido. O
critério é o do `t.test`, levado para cá: o desvio padrão residual abaixo de dez
épsilons vezes a maior média em valor absoluto.

Recebe as colunas, ou a matriz n × k já montada.

### `def _matriz_das_medidas(medidas, conferir, teste)`

*linha 564*

As medidas como matriz n × k — os casos nas linhas, as medidas nas colunas —, com
as barreiras: duas medidas ou mais, todas do mesmo tamanho, e dois casos ou mais —
o mínimo do R na ANOVA de medidas repetidas e no Friedman. `teste` é o nome que vai
para a frase.

### `def sem_variacao_nos_grupos(grupos, variancias_iguais)`

*linha 598*

Os valores não variam dentro dos grupos, para a ANOVA.

O `oneway.test` do R não tem critério nenhum: com a variância dentro dos grupos
zero, ele devolve F infinito, e p zero, e a tabela sairia com um `< 0,001` que é
uma divisão por zero. O critério aqui é o do `t.test`, levado para a ANOVA: o
desvio padrão combinado abaixo de dez épsilons vezes a maior média em valor
absoluto — zero, ou só o último bit.

Com `variancias_iguais=False` — a ANOVA de Welch —, basta **um** grupo que não
varia: o Welch pesa cada grupo por n/s², e o peso de um grupo constante é
infinito; o R devolve `NaN`.

### `def _grupos_da_anova(grupos)`

*linha 630*

Os grupos como vetores, com as duas barreiras do `oneway.test`: dois grupos ou mais
(`not enough groups`), e dois valores ou mais em cada um (`not enough
observations`).

### Os testes de postos

### `def wilcoxon_uma_amostra(x, mu)`

*linha 651*

O `wilcox.test(x, mu = mu, conf.int = TRUE)` do R: o teste do posto sinalizado de
Wilcoxon, bilateral, com a pseudomediana de Hodges-Lehmann e o intervalo de 95% dela.

    d = x − mu, sem os zeros            V = Σ postos de |d| onde d > 0

Os valores iguais à referência saem antes de tudo, como no R: um zero não tem
sinal. O p é exato — pela distribuição do posto sinalizado — com menos de
`LIMITE_DO_EXATO` valores restantes, sem empate em |d| e sem zero; nos outros casos,
a aproximação normal, com a variância corrigida para os empates e a correção de
continuidade:

    z = [V − n(n + 1)/4 − ½ sinal(V − n(n + 1)/4)] / √[n(n + 1)(2n + 1)/24 − Σ(t³ − t)/48]

**A estimativa e o intervalo.** No caminho exato, a mediana das médias de Walsh —
(xᵢ + xⱼ)/2, com i ≤ j — e o intervalo entre duas delas, nas posições que o quantil
da mesma distribuição dá. No aproximado, o valor que zera a estatística padronizada
e os que a levam aos quantis da normal, achados como o R os acha: ver
`_ic_assintotico_da_pseudomediana`. Os valores iguais à referência ficam de fora do
intervalo também, como no R.

Derivada do `wilcox.test.default`, em `src/library/stats/R/wilcox.test.R`, do R —
(C) 1995-2019 The R Core Team, GPL-2.0-or-later. Origem, e os direitos autorais do
original: ver o `NOTICE.md`.

Raises:

    ValueError: nenhum valor, todos iguais à referência — onde o R devolve `NaN` —,
        valor ausente ou infinito, ou referência que não é um número finito.

*linha 704*

> O `x <- x + mu` do R: o intervalo é sobre os valores, e não sobre as diferenças —
> refeitos pela mesma conta dele, e não lidos de novo do vetor original.

*linha 733*

> Sem o `min(1.0, …)` dos outros testes: o teto de 1 já veio do `_p_exato`, como no
> R, e a aproximação normal dobra uma cauda que não passa de ½.

### `def mann_whitney(x, y)`

*linha 750*

O `wilcox.test(x, y, conf.int = TRUE)` do R — que ele chama de teste da soma de
postos de Wilcoxon, e que é o de Mann-Whitney —: bilateral, com a diferença de
locação de Hodges-Lehmann e o intervalo de 95% dela.

    W = Σ postos de x − n₁(n₁ + 1)/2

W é o U de Mann-Whitney do primeiro grupo, como o R o imprime: quantos pares
(xᵢ, yⱼ) têm xᵢ > yⱼ, com meio ponto por empate. O p é exato — pela distribuição da
soma dos postos — com menos de `LIMITE_DO_EXATO` valores em cada grupo e sem
empate; nos outros casos, a aproximação normal, com a variância corrigida para os
empates e a correção de continuidade:

    z = [W − n₁n₂/2 − ½ sinal(W − n₁n₂/2)] / σ
    σ² = n₁n₂/12 · [n₁ + n₂ + 1 − Σ(t³ − t) / ((n₁ + n₂)(n₁ + n₂ − 1))]

**A estimativa e o intervalo.** No caminho exato, a mediana das n₁n₂ diferenças
xᵢ − yⱼ e o intervalo entre duas delas, nas posições que o quantil da mesma
distribuição dá; no aproximado, como o R os acha: ver
`_ic_assintotico_da_diferenca`. **A diferença de locação não é a diferença das
medianas** dos dois grupos: é a mediana das diferenças entre um valor de cada um, e
estima o deslocamento de um grupo em relação ao outro quando as duas distribuições
têm a mesma forma. A ordem dos dois vetores é a do sinal, como no t.

Derivada do `wilcox.test.default`, em `src/library/stats/R/wilcox.test.R`, do R —
(C) 1995-2019 The R Core Team, GPL-2.0-or-later. Origem: ver o `NOTICE.md`.

Raises:

    ValueError: grupo vazio, ou valor ausente ou infinito.

*linha 825*

> O teto de 1, como no Wilcoxon, já veio do `_p_exato`.

### `def kruskal_wallis(grupos)`

*linha 841*

O `kruskal.test` do R: os postos de todos os valores juntos, e

    H = [12 / (N(N + 1)) · Σ Rᵢ²/nᵢ − 3(N + 1)] / [1 − Σ(t³ − t)/(N³ − N)]

com k − 1 graus de liberdade, pela cauda do qui-quadrado — o R não tem caminho
exato. Rᵢ é a soma dos postos do grupo i, e o denominador é a correção para os
empates. Pelo `scipy`, que faz o mesmo: é o primeiro degrau da régua do topo. Não
estima nada, como a ANOVA: com k grupos não há uma diferença só.

Raises:

    ValueError: menos de dois grupos, grupo vazio, todos os valores iguais — onde o
        R devolve `NaN` —, ou valor ausente ou infinito.

### `def friedman(medidas)`

*linha 887*

O `friedman.test` do R — as mesmas pessoas medidas k vezes, sem a normal: em cada
caso, os postos das k medidas; Rⱼ a soma dos postos da medida j, e

    χ² = 12 Σ [Rⱼ − n(k + 1)/2]² / [n k (k + 1) − Σ(t³ − t)/(k − 1)]

com k − 1 graus de liberdade, pela cauda do qui-quadrado, como no R. Os empates
são os de dentro de cada caso.

**Escrita, e não importada**, pela razão da ANOVA: o `friedmanchisquare` do `scipy`
dá o mesmo qui-quadrado, mas recusa duas medidas, que o R aceita — e a função daqui
é o `friedman.test`. Do `scipy` vêm só os postos e a cauda; o `friedmanchisquare`
fica nos testes, como conferência. A fórmula é a do `friedman.test`, em
`src/library/stats/R/friedman.test.R`, do R — (C) 1995-2015 The R Core Team,
GPL-2.0-or-later. Origem: ver o `NOTICE.md`.

`medidas` são as k colunas, cada uma com os mesmos n casos, na mesma ordem: quem
chama tira antes os casos com alguma medida faltando, como o `complete.cases` do R.

O mínimo é o do R: dois casos com todas as medidas. Com um caso só, o
`friedman.test` para com erro — a seleção dos casos completos tira a dimensão da
matriz de uma linha, e o `apply` não tem sobre o que andar.

Raises:

    ValueError: menos de duas medidas, medidas de tamanhos diferentes, menos de dois
        casos, cada caso com o mesmo valor em todas as medidas — onde o R devolve
        `NaN` —, ou valor ausente ou infinito.

### `def medidas_iguais_em_cada_caso(medidas)`

*linha 941*

Cada caso tem o mesmo valor em todas as medidas — e não há o que ordenar dentro de
caso nenhum.

É a barreira do Friedman, e não a mesma da ANOVA de medidas repetidas
(`sem_variacao_entre_medidas`): cada caso mudando o mesmo tanto de uma medida para
outra deixa a ANOVA sem variação de erro, e dá ao Friedman os mesmos postos em todo
caso — o qui-quadrado mais alto que ele tem, e não uma divisão por zero. Aqui é o
contrário: o denominador do Friedman é zero quando todo caso está empatado inteiro,
e o R devolve `NaN`.

Recebe as colunas, ou a matriz n × k já montada.

### `_APROXIMADO`

*linha 959*

> A frase do cálculo do p dos testes de postos: o caminho, como a frase da tabela o diz
> — `p exato`, `p aproximado pela normal, …`.

### `def _ic_exato(ordenadas, contagens, total, arredondar)`

*linha 967*

O intervalo exato do `wilcox.test`: entre dois valores de `ordenadas` — as médias de
Walsh na uma amostra, as diferenças entre os grupos no Mann-Whitney —, nas posições
que o quantil da distribuição exata dá, e o nível dele.

A posição de baixo é o `qsignrank(α/2, n)` — ou o `qwilcox` —, e a de cima, a que
sobra do outro lado. Com poucos valores, nem o intervalo mais largo, do menor ao
maior, chega a 95%: o R fica com ele e baixa o nível, avisando, quando o α que ele
alcança passa de 1,5 α. `arredondar` é a diferença entre os dois ramos do R: a uma
amostra escreve o nível com o α em dois algarismos significativos (`signif`), e o
Mann-Whitney, com o α inteiro.

### `def _ic_assintotico_da_pseudomediana(x)`

*linha 994*

O intervalo e a estimativa da uma amostra no caminho aproximado, como o
`wilcox.test` os acha — o algoritmo que o próprio R diz não estar publicado, e por
isso documenta no código.

A estatística padronizada de `x − d` cai à medida que `d` cresce, em degraus. O
limite de baixo é o `d` em que ela cruza o quantil de cima da normal, e o de cima, o
`d` em que cruza o de baixo; a estimativa, o `d` em que ela cruza o zero — sem a
correção de continuidade. Os três são achados pelo `uniroot` do R, entre o menor e o
maior valor (`_raiz`). Quando nem nos extremos a estatística alcança os quantis, o R
dobra o α até alcançar, e baixa o nível do intervalo.

Devolve o intervalo, a estimativa e o nível; os três `None` quando os valores — sem
os iguais à referência — são todos iguais: não há degrau a cruzar, e o R devolve
`NaN` no intervalo e o ponto médio dos valores no lugar da pseudomediana, que aqui
não se imprime com o nome de outra coisa.

#### `def padronizada(d, correcao)`

*linha 1017*

*linha 1027*

> Só quando não sobra valor nenhum — o desvio é pelo menos √(n(n + 1)²/16),
> com todos empatados. O núcleo é zero também, e o R devolve o NaN de 0/0.

### `def _ic_assintotico_da_diferenca(x, y)`

*linha 1074*

O intervalo e a estimativa do Mann-Whitney no caminho aproximado, como o
`wilcox.test` os acha: a estatística padronizada dos postos de `x − d` contra `y`,
e os `d` em que ela cruza os quantis da normal e — sem a correção de continuidade —
o zero, entre a menor e a maior diferença possível. Quando nem no extremo ela
alcança o quantil, o limite é o próprio extremo, como no R; aqui o nível não baixa.

Devolve os três `None` quando os dois grupos não variam por dentro: todo valor de
um empata com todo valor do outro num dos extremos, a estatística é 0/0, e o R para
com erro.

#### `def padronizada(d, correcao)`

*linha 1093*

*linha 1102*

> Só quando todos os valores empatam: cada posto é (N + 1)/2, o núcleo é zero
> também, e o R devolve o NaN de 0/0.

#### `def limite(quantil)`

*linha 1113*

### `def _raiz(funcao, a, b, fa, fb, tolerancia, iteracoes)`

*linha 1138*

O `uniroot(f, lower = a, upper = b, f.lower = fa, f.upper = fb, tol = 1e-4)$root` do
R: o método de Brent — bisseção, com interpolação linear ou quadrática inversa
quando ela cai dentro do intervalo —, como o `R_zeroin2` o escreve.

**Transcrito linha a linha**, e não trocado pelo `brentq` do `scipy`, que é o mesmo
método com outros passos: a função aqui é uma escada — a estatística dos postos só
muda quando `d` cruza uma média de Walsh ou uma diferença entre os grupos —, a raiz
está num degrau, e a tolerância de 1e-4 deixa o ponto devolvido em qualquer lugar a
até 1e-4 dele. Com outros passos, o número sai outro, e a segunda casa do intervalo
pode virar quando o degrau cai num `,xx5`. Com os mesmos, sai o do R.

A função é finita em todo o intervalo, e só por isso o `fcn2` e o `truncate` do
`uniroot` — que trocam o ±∞ e o `NaN` pelo maior `double` — não estão aqui: a
estatística padronizada só deixa de ser finita nos casos degenerados, sem valor que
não empate, e quem chama sai antes da busca.

Transcrito do `R_zeroin2`, em `src/library/stats/src/zeroin.c`, do R — (C)
1999-2016 The R Core Team, GPL-2.0-or-later, a partir do `zeroin` do NETLIB
(`c/brent.shar`), com o número máximo de iterações de Peter Dalgaard. Algoritmo de
G. Forsythe, M. Malcolm e C. Moler, *Computer methods for mathematical
computations* (1977). Origem: ver o `NOTICE.md`.

### `def _contagens_do_posto_sinalizado(n)`

*linha 1220*

De quantas das 2ⁿ atribuições de sinal sai cada soma V = 0, 1, …, n(n + 1)/2 — a
distribuição exata do posto sinalizado, em inteiros: quantos subconjuntos de
{1, …, n} somam cada valor. É o `csignrank` do R, que guarda as mesmas contagens em
`double`.

### `def _contagens_da_soma_dos_postos(m, n)`

*linha 1236*

De quantas das C(m + n, m) maneiras de escolher os postos do primeiro grupo sai cada
W = 0, 1, …, m·n — a distribuição exata da estatística de Mann-Whitney, em
inteiros. São os coeficientes do binômio gaussiano [m + n, m], pelo produto

    Π (1 − q^(n + i)) / (1 − q^i),  i = 1, …, m

multiplicando e dividindo como séries de potências — exato, porque o resultado é
um polinômio de grau m·n. É o `cwilcox` do R, que guarda as contagens em `double`,
pela recursão de Mann e Whitney. A distribuição é a mesma com os grupos trocados, e
quem chama passa o menor primeiro.

### `def _p_exato(contagens, total, estatistica, centro)`

*linha 1260*

O p bilateral exato do `wilcox.test`: a cauda do lado em que a estatística está —
P(S ≥ s) acima do centro da distribuição, P(S ≤ s) até ele —, dobrada, e nunca
acima de 1. Sem empates a estatística é inteira.

### `def _probabilidade(contagens, total, de, ate)`

*linha 1276*

P(de ≤ S ≤ ate), em frações exatas, e um `float` só no fim: as contagens são
inteiras, e a soma delas sobre o total não erra casa nenhuma.

### `def _quantil(contagens, total, probabilidade)`

*linha 1291*

O menor q com P(S ≤ q) ≥ `probabilidade` — o `qsignrank` e o `qwilcox` do R, com a
folga de dez épsilons que os dois dão à probabilidade, no ramo de até ½, que é o
único que o intervalo usa. A conta da acumulada é exata; a folga é a do R, para o
quantil ser o dele também no caso em que a acumulada cai em cima do alvo.

A busca é a do `qsignrank`, em `src/nmath/signrank.c`, e a do `qwilcox`, em
`src/nmath/wilcox.c`, do R — (C) 1999-2024 The R Core Team, GPL-2.0-or-later.
Origem: ver o `NOTICE.md`.

### `def _postos(valores)`

*linha 1311*

Os postos, com o posto médio nos empates — o `rank` do R, pelo `rankdata` do
`scipy`, que dá os mesmos números.

### `def _soma_dos_empates(postos)`

*linha 1321*

Σ (t³ − t) sobre os grupos de postos iguais — o `sum(NTIES^3 - NTIES)` do R, com o
`table(r)` dele: t é quantos valores empatam em cada posto. Zero sem empate.

### `def _sinal(valor)`

*linha 1332*

O `sign` do R: −1, 0 ou 1.

### `def _em_frase(itens)`

*linha 1337*

`A`, `A e B`, `A, B e C`.

### `def sem_variacao(x)`

*linha 1345*

Os valores não variam — o `data are essentially constant` do `t.test`.

O critério é o do R, e não "todos iguais": o erro-padrão abaixo de dez vezes o
épsilon da máquina vezes a média. Todos iguais é o caso de todo dia, e fica
dentro dele; o que ele acrescenta é o vetor que varia só no último bit, onde o
t sairia um número enorme e sem sentido. Pública porque o `comparacao.py` faz a
mesma pergunta antes de chamar o teste, para a linha sair com o motivo escrito
em vez de um `ValueError`.

### `def sem_variacao_em_duas(x, y, variancias_iguais)`

*linha 1365*

Os valores dos dois grupos não variam — o `data are essentially constant` do
`t.test` de duas amostras.

O critério é o do R: o erro-padrão da diferença abaixo de dez épsilons vezes a
maior das duas médias em valor absoluto. O erro-padrão é o do teste — com a
variância combinada no de Student, com a soma das duas no de Welch —, e por isso
a pergunta leva o teste junto. Dois grupos que não variam por dentro, cada um com
o seu valor, param aqui mesmo com médias diferentes: o R recusa esse t, e não o
devolve infinito.

Com menos valores do que o teste exige, devolve `False`: a barreira do tamanho
vem antes, com a frase dela.

### `def _sem_o_aviso_de_precisao()`

*linha 1404*

Cala o «Precision loss occurred in moment calculation» do `scipy` — e só ele.

O `scipy` o emite quando um grupo não varia, e ali a conta está certa: a variância
de um grupo constante é zero de verdade, e o t sai igual ao do R, conferido. O caso
em que o aviso diria a verdade — valores que variam só no último bit — para antes,
na barreira do R (`sem_variacao_em_duas`). Solto, ele iria para o `stderr` no meio
da saída do comando, que é o recado que o usuário aprende a ignorar; é a manobra do
`normalidade.shapiro`, com o filtro pela mensagem.

### `def _vetor(x)`

*linha 1422*

O vetor como `float64`, com as duas condições que nenhum teste daqui aceita.

Valor ausente não chega aqui pelo caminho da análise — os faltantes saem antes,
por variável —, e um `nan` que chegasse viraria um t `nan` sem aviso nenhum.

## `flatcap/comparacao.py`

`SPDX-FileCopyrightText: 2026 Matheus Fernandes` · `SPDX-License-Identifier: GPL-3.0-or-later`

*3997 linhas.*

A comparação — uma variável contra um valor de referência, entre os grupos de outra,
ou entre medidas repetidas nos mesmos casos —, com o teste que os pressupostos pedem:
o paramétrico, ou o de postos, que dispensa a normal.

Responde ao passo 2b do fluxo. Cada item da ficha é uma pergunta, e cada delineamento
tem a sua tabela, na mesma pasta:

    uma_amostra.csv
    variável       n  média (DP)         IC 95% da média  referência  teste         p-valor
    IMC (kg/m²)  116  26,43 (4,59)       25,58 a 27,27    25          t de Student    0,001
    PAS (mmHg)   120  128,4 (14,2)       125,83 a 130,97  120         t de Student  < 0,001

    dois_grupos.csv
    variável     grupo        n  média (DP)    diferença (IC 95%)     teste         p-valor
    IMC (kg/m²)  Sexo       116                -1,52 (-3,24 a 0,20)   t de Welch      0,083
                 Feminino    60  25,70 (4,41)
                 Masculino   56  27,22 (4,70)

    k_grupos.csv
    variável     grupo          n  média (DP)    teste            p-valor
    PAS (mmHg)   Escolaridade 114                ANOVA de Welch     0,011
                 Fundamental   34  128,1 (15,2)
                 Médio         52  131,0 (16,9)
                 Superior      28  138,4 (16,1)

    repetidas.csv
    medida        n  média (DP)     teste                        p-valor
    PAS basal    40  131,2 (16,6)   ANOVA de medidas repetidas     0,003
    PAS 30 dias  40  128,4 (15,1)
    PAS 90 dias  40  125,9 (14,8)

Nas linhas de um teste de postos — o Wilcoxon, o Mann-Whitney, o Kruskal-Wallis e o
Friedman —, o resumo é a mediana e os quartis, `2982,62 [1774,62 a 5013,54]`, e o
intervalo é o de Hodges-Lehmann: o da pseudomediana na uma amostra, e o da diferença de
locação entre dois grupos, `-921,57 (-2414,48 a 406,97)`. O cabeçalho de cada coluna diz
o que ela tem — ver "O resumo, linha a linha", abaixo.

Segue o padrão das Fases 2 a 6, decidir e escrever separados:

    plano = preparar_comparacao(raiz)   # abre o banco, calcula, não toca no disco
    executar_comparacao(plano)          # só escreve

E, como elas, **não fala com o REDCap**. Recebe `Path`, não `Config`.

### Uma análise, e o teste escolhido dentro dela

`comparacao` é uma análise só — uma chave na ficha, um comando, uma pasta em
`3. Análises/`, uma seção no documento —, e cada teste é uma entrada num registro
dentro dela, e não um módulo por teste. O que se escreve na reunião é a **pergunta**
("a média do IMC difere de 25?", "o IMC difere entre os sexos?"), e não o teste: qual
teste responde é consequência do **delineamento**, que sai da forma do item e dos
tipos do dicionário, e dos **pressupostos**, que saem do banco. É a lição da
correlação — a ficha lista as perguntas, a regra escolhe o método, e o terceiro nome
discorda quando você discordar.

O registro são três dicionários aqui em cima. A `REGRA` diz, para cada delineamento,
o teste quando a normal se sustenta e o teste quando não; o `_CALCULO` diz quais deles
já têm a aritmética no `hipoteses.py`; o `METODOS` diz o que cada nome escrito no item
quer dizer em cada delineamento. Um teste que está na regra e não no cálculo é um
teste que a regra sabe escolher e o FlatCap ainda não sabe fazer, e a linha dele sai
sem teste, com o motivo escrito; quando ele chega, entra uma linha no `_CALCULO`, e
as linhas "não testado" viram linhas dele. Foi assim que os paramétricos e, na 1.14.0,
os quatro testes de postos entraram, um por um; desde ela, todo teste da regra tem a
aritmética, e o caminho fica para o próximo que entrar.

### O delineamento

A forma do item e os tipos das variáveis dizem qual comparação é:

    [imc, 25]                  numérica, e um número       uma amostra
    [imc, sexo]                numérica, categórica        dois grupos
    [imc, escolaridade]        numérica, categórica        três grupos ou mais
    repetidas: [pas_0, pas_1, pas_2]   três numéricas ou mais      medidas repetidas
    repetidas: [pas_0, pas_1]          duas numéricas              pareado (depois)

**O número de grupos sai do banco, e não do dicionário.** Os grupos são os rótulos
com resposta entre os casos que responderam as duas variáveis — pelas mesmas
`serie_de_texto` e `rotulo_de` do cruzamento e da associação: dois códigos com o
mesmo rótulo (`1=Sim|2=Sim`) são um grupo só, e uma categoria declarada que ninguém
marcou não é grupo. Dois grupos são a tabela dos dois grupos; três ou mais, a dos k
grupos. Um grupo só dá linha sem teste, na tabela que o dicionário promete.

**Os faltantes são por comparação**: entra quem respondeu as duas variáveis. É o
`na.omit` da fórmula do R. Nas medidas repetidas, entra quem tem todas as medidas do
item: a ANOVA compara cada pessoa com ela mesma, e um caso com uma medida faltando sai
inteiro — como no `lm` do R.

**As medidas repetidas têm a marca na ficha.** Duas numéricas lado a lado,
`[pas_0, pas_1]`, seriam um pareado — ou `[idade, imc]` escrito por engano,
comparando médias de unidades diferentes sem erro nenhum. A marca `repetidas:` diz que
são a mesma medida, feita mais de uma vez nas mesmas pessoas.

### A regra dos pressupostos

Três passos, como na correlação:

1. **o Shapiro-Wilk sobre o vetor do delineamento.** Na uma amostra, os valores
   preenchidos da variável; entre grupos, **cada grupo**, separado — é a normalidade
   que o t supõe, e não a da coluna inteira. Não rejeitou em nenhum → o paramétrico;
2. **rejeitou em algum, ou não pôde ser verificado em algum** (menos de três valores,
   ou um grupo que não varia) → o teste de postos, que dispensa a normal: o Wilcoxon
   na uma amostra, o Mann-Whitney entre dois grupos, o Kruskal-Wallis entre três ou
   mais, o Friedman nas medidas repetidas;
3. **o método escrito no item manda**: `[imc, 25, t]` roda o t contra a regra, e
   `[imc, 25, wilcoxon]` o Wilcoxon, com um aviso e a frase nas notas do `.csv`.

**Entre dois grupos, o paramétrico da regra é o t de Welch**, e não o de Student: é o
padrão do `t.test` do R, perde pouco quando as variâncias são iguais e protege quando
não são (Delacre, Lakens e Leys, 2017) — e dispensa o teste de Levene, que seria um
teste preliminar a mais antes do teste que interessa. O de Student roda quando está
escrito no item, `[imc, sexo, student]`, e o aviso diz quanto os desvios padrão dos
grupos diferem.

**Entre três grupos ou mais, pela mesma razão, a ANOVA de Welch** — o padrão do
`oneway.test` do R —, e a clássica, de Fisher, quando está escrita no item:
`[imc, escolaridade, anova]`, com o mesmo aviso das variâncias do t de Student. A
ANOVA diz se as médias diferem, e não quais: o pós-teste ainda não está no FlatCap.

**Nas medidas repetidas, a ANOVA com a correção de Greenhouse-Geisser, sempre** — a
mesma lógica do Welch: a correção custa pouco quando a esfericidade vale e protege
quando não vale, e o teste de Mauchly, preliminar, sai da frente. O Shapiro-Wilk roda
em cada medida, sobre os casos completos.

**A normalidade é a função, e não a rodada.** O teste é o `normalidade.shapiro`, o
mesmo que a correlação chama, com as mesmas barreiras e os mesmos avisos — e não o
`manifesto.json` da rodada de normalidade. O vetor que se testa muda com o
delineamento, e uma escolha que dependesse da outra rodada dependeria da ordem dos
comandos e da idade dela. Na uma amostra o vetor **é** a coluna sem os faltantes, então
o p que decide é o mesmo da tabela de normalidade — por construção.

**O Shapiro-Wilk não garante o pressuposto**, e o módulo não finge que garante: é a
regra que o projeto adotou, com os limites dela escritos no topo do `normalidade.py`.
Abaixo de 20 valores ele quase não rejeita, e o paramétrico escolhido ali sai com
aviso; com n grande ele rejeita desvio irrelevante, e a linha vai para o teste de
postos — que continua valendo, e custa pouco. Quando você concluir que o paramétrico
vale ali — n grande e assimetria pequena, por exemplo —, o método escrito no item
manda. A decisão é sua, e fica registrada contra a regra.

### Os testes de postos

São os do R, pela aritmética do `hipoteses.py`: o `wilcox.test` — de uma amostra e de
duas, que é o Mann-Whitney —, o `kruskal.test` e o `friedman.test`. O Wilcoxon e o
Mann-Whitney saem **com a estimativa de Hodges-Lehmann e o intervalo dela**, o
`conf.int = TRUE` do R: a pseudomediana, lida contra a referência como o intervalo da
média; a diferença de locação entre dois grupos, lida contra o zero como a diferença
das médias. **A diferença de locação não é a diferença das medianas** dos grupos — é a
mediana das diferenças entre um valor de cada grupo —, e a nota da tabela diz isso. O
Kruskal-Wallis e o Friedman, como a ANOVA, dizem se há diferença, e não quanto.

Com poucos valores, a distribuição exata pode não ter um intervalo de 95% — o mais
largo, do menor ao maior valor, fica abaixo disso —, e o menor p que o teste consegue
dar pode passar de 0,05: o teste não rejeita com dado nenhum. Os dois casos saem com
aviso, e o intervalo que não chega a 95% fica fora da tabela, que promete 95%.

### O resumo, linha a linha

Cada linha descreve a variável na medida que o teste dela usa: **média (DP)** nas
linhas do t e da ANOVA, **mediana [Q1 a Q3]** nas dos testes de postos — como o
`compareGroups` do R faz. O teste é o da linha: o que rodou, ou o que a regra escolheu
quando ele não pôde rodar; sem teste nenhum, a média. As duas formas saem pelo
`descritiva.resumo_numerico` e pelo `numero()`, letra por letra as do
`resumo_<variável>.csv`. Os colchetes separam os quartis do desvio padrão na leitura de
relance, e o cabeçalho diz o que a coluna tem: `média (DP)`, `mediana [Q1 a Q3]`, ou as
duas, quando a tabela mistura. O mesmo vale para o intervalo da uma amostra — `IC 95% da
média`, `da pseudomediana`, ou só `IC 95%` — e para a diferença entre dois grupos:
`diferença (IC 95%)` no t, `diferença de locação (IC 95%)` no Mann-Whitney. As notas,
que dizem o que é a diferença de locação, ficam no `.csv`; o documento leva a tabela, e
é o cabeçalho que impede a leitura dela como a diferença das medianas ao lado. Uma tabela
só de paramétricos sai com os cabeçalhos de antes.

### A ficha

    comparacao:
      - [imc, 25]                # a média do IMC difere de 25?
      - [pas, 120, t]            # o t, mesmo que a regra discorde
      - [renda, 3000, wilcoxon]  # o Wilcoxon, mesmo que a regra escolhesse o t
      - [imc, sexo]              # o IMC difere entre os sexos?
      - [pas, sexo, student]     # pelo t de Student, que supõe variâncias iguais
      - sexo: [imc, idade]       # uma contra várias: imc e idade, entre os sexos
      - repetidas: [pas_0, pas_1, pas_2]   # a PAS mudou entre as três medidas?
      - repetidas: [pad_0, pad_1, pad_2]
        metodo: anova                      # a ANOVA, mesmo que a regra discorde

**A referência é obrigatória.** O padrão do R é `mu = 0`, que nunca é a hipótese de
uma variável clínica; o valor vem da literatura ou do protocolo, e é decidido na
reunião. **A vírgula decimal quebra a lista**: `[imc, 24,9]` é lido como três itens,
`imc`, `24` e `9`, e a recusa reconhece esse caso e escreve a forma certa —
`[imc, 24.9]`, ou `[imc, "24,9"]`, que entre aspas é aceito. **A variável comparada
vem primeiro**, e a de grupo depois; na forma com dois-pontos, a de grupo vem antes
deles, e o método não se escreve — ele ficaria misturado aos nomes. **Sempre
bilateral**: um teste unilateral escolhido depois de olhar os dados é o p dividido por
dois.

### O que ele reaproveita

As recusas de dicionário e de tipo são as da descritiva, com a classe de erro deste
módulo. O Shapiro-Wilk e o formatador do p são os da normalidade. A média e o desvio
padrão — e a mediana e os quartis — saem pelo `descritiva.resumo_numerico` e pelo
`numero()`: o resumo da uma amostra é, letra por letra, o do `resumo_<variável>.csv`.
Os grupos saem pela `serie_de_texto` da descritiva, pelo `rotulo_de` do dicionário e
pela ordem da associação. A aritmética dos testes é a do `hipoteses.py`, que confere
com o `t.test`, o `oneway.test`, o `wilcox.test`, o `kruskal.test` e o `friedman.test`
do R.

### O que ele deliberadamente não faz

**Não desenha.** O histograma da descritiva e o Q-Q da normalidade são as figuras
destas variáveis; as caixas por grupo são uma espécie nova no `graficos.py`, e ficam
para quando a comparação entre grupos estiver inteira.

**Não imprime o d de Cohen**, nem um r de efeito nos testes de postos. O intervalo —
da média ou da pseudomediana, lido contra a referência; da diferença, lido contra o
zero — já é o tamanho do efeito, na unidade que o cliente entende.

**Não roda o Levene**, pela razão do Welch, acima.

**Não corrige para comparações múltiplas.** Cada comparação é um teste, e isso está
escrito nas notas e no terminal.

### `UMA_AMOSTRA`

*linha 312*

> Os delineamentos, na ordem em que as tabelas saem. Cada um tem a sua tabela, porque
> as colunas mudam de um para outro: a uma amostra tem a referência; os grupos, uma
> linha por grupo e a diferença.

### `CHAVE_REPETIDAS`

*linha 321*

> As chaves do item de medidas repetidas — a marca, e o método, que ali não tem um
> terceiro lugar na lista para morar:
>
>     - repetidas: [pas_0, pas_1, pas_2]
>       metodo: anova

### `MINIMO_DE_MEDIDAS`

*linha 329*

> O menor número de medidas da ANOVA de medidas repetidas nesta versão. Com duas, a
> pergunta é a do t pareado, que usa a mesma forma de item e ainda não está no FlatCap.

### `GRUPOS`

*linha 333*

> A forma do item entre grupos, antes de o banco dizer quantos são. A `Pergunta` sai
> da ficha com ela, e a `VariavelComparada` sai do banco com o delineamento de fato.

### `REGRA`

*linha 349*

> A regra: para cada delineamento, o teste quando a normal se sustenta e o teste
> quando não — o de postos. Entre grupos o paramétrico é o de Welch — o padrão do
> `t.test` e do `oneway.test` do R. Os nomes, e a aritmética, vêm do `hipoteses.py`.

### `_CALCULO`

*linha 359*

> O que já tem aritmética. Um teste da `REGRA` que não está aqui é escolhido pela
> regra e sai sem teste, com o motivo. O t de Student e a ANOVA clássica estão aqui
> sem estar na regra: eles rodam quando o item os pede.

### `TESTES_DE_POSTOS`

*linha 375*

> Os testes de postos: os que dispensam a normal, e cujas linhas resumem a variável
> pela mediana e pelos quartis, e não pela média e pelo desvio.

### `METODOS`

*linha 381*

> Como cada método se escreve no item — o terceiro nome —, e o teste que ele quer
> dizer em cada delineamento. Sem acento, minúsculo e sem hífen, que é como `_chave`
> deixa o que se digitou. `t` é o t que o R roda sem argumento: o de uma amostra, e o
> de Welch entre dois grupos — o `var.equal = FALSE` padrão do `t.test`. `welch` é o
> de Welch do número de grupos que o banco trouxer: o t com dois, a ANOVA com mais.
> `wilcoxon` é o `wilcox.test` do R: o do posto sinalizado contra uma referência, e o
> Mann-Whitney entre dois grupos — que o R chama de soma de postos de Wilcoxon.

### `PREVISTOS`

*linha 399*

> Os nomes que a regra ainda não conhece em delineamento nenhum desta versão. Escritos
> na ficha, recusam com a frase certa, em vez de "não é um método". Vazio nesta versão:
> cada nome conhecido tem o seu delineamento; o lugar fica para o próximo.

### `_EQUIVALENTES`

*linha 404*

> O método de um número de grupos escrito para outro: o que se escreve no lugar dele,
> e por quê. O banco é que diz quantos grupos há, e a recusa ensina a troca.

### `_SINONIMOS`

*linha 421*

> Outras grafias do mesmo método. `welsh` é a troca mais comum de letra no nome do
> Welch, e ninguém a escreve querendo outra coisa.

*No módulo, linha 441:*

> O `signed rank` fica de fora de propósito: o `wilcoxon` entre dois grupos é o
> Mann-Whitney, e um sinônimo dele levaria quem escreveu o posto sinalizado — o teste
> de uma amostra, ou do pareado — ao da soma de postos sem aviso. Escrito, ele recusa,
> e a recusa ensina o `wilcoxon`.

### `_VARIANCIAS_IGUAIS`

*linha 446*

> Os testes que supõem a mesma variância nos grupos. Quando um deles roda, o aviso diz
> quanto o maior desvio padrão passa do menor — acima de duas vezes, a regra de bolso
> que os livros dão para a igualdade de variâncias ainda valer.

### `CASAS_IC`

*linha 454*

> O intervalo sai com casas fixas: ele não existe na descritiva, e uma célula com
> `25,8 a 27,02` — um limite com uma casa, outro com duas — não se lê de relance. A
> média e o desvio não: eles têm de sair letra por letra como no `resumo`. As casas
> são duas, ou as da variável quando a escala dela é pequena: até a 1.14.0, uma
> concentração na casa de 0,003 saía «0,00 (0,00 a 0,00)» ao lado de um p < 0,001.

### `COLUNA_DA_MEDIA`

*linha 461*

> O cabeçalho da coluna do resumo, conforme o que ela tem: a média e o desvio nas
> linhas do t e da ANOVA, a mediana e os quartis nas dos testes de postos — e as duas
> formas no cabeçalho quando a tabela mistura. Os colchetes separam os quartis do
> desvio padrão, que vem entre parênteses, na leitura de relance.

### `COLUNA_DO_IC_DA_MEDIA`

*linha 469*

> O cabeçalho do intervalo da uma amostra, pela mesma regra: o da média no t, o da
> pseudomediana no Wilcoxon, e só o nível quando a tabela tem os dois.

### `COLUNA_DA_DIFERENCA`

*linha 475*

> O cabeçalho da diferença entre dois grupos, pela mesma regra: o de sempre no t, a de
> locação no Mann-Whitney — que não é a diferença das medianas, e que a célula ao lado
> da mediana de cada grupo convidaria a ler como tal —, e as duas quando a tabela mistura.

### `CASAS_REFERENCIA`

*linha 482*

> A referência sai como foi escrita, sem arredondar para duas casas: um `0,125` da
> ficha impresso `0,12` seria uma hipótese que ninguém testou.

### `_PARECE_NUMERO`

*linha 488*

> Um texto que quer ser número e não é um que se leia sem ambiguidade: `"2.500,00"`.
> Só algarismos, pontos, vírgulas e espaços — `pas_0` tem algarismo e é um nome.

### `EXEMPLO_DA_FICHA`

*linha 492*

> O exemplo que as mensagens escrevem. Um lugar só, para a recusa e o `--help` nunca
> ensinarem duas formas diferentes de escrever a mesma lista.

### `class ComparacaoError(RuntimeError)`

*linha 501*

Falha ao gerar a comparação, já traduzida para o usuário.

Erro próprio pela regra da casa: a CLI captura esta classe e transforma em painel
com o nome do comando que o usuário rodou. Qualquer outra exceção é bug de
verdade e deve subir com o traceback inteiro.

### `class DicionarioAusenteError(ComparacaoError)`

*linha 511*

O projeto não tem `dicionario.csv`. Não há o que obedecer.

### `class DicionarioDesatualizadoError(ComparacaoError)`

*linha 517*

O banco tem colunas que o dicionário desconhece.

### `class VariavelIncompativelError(ComparacaoError)`

*linha 523*

O dicionário promete `numerica` e a coluna chegou como texto, ou declara uma
variável que o banco não tem.

A mesma recusa da Fase 5, pela mesma função — aplicada só às variáveis da lista,
como na correlação.

### `class SemItensError(ComparacaoError)`

*linha 533*

A ficha não diz o que comparar.

### `class ItemInvalidoError(ComparacaoError)`

*linha 539*

A lista `comparacao:` da ficha tem item que não serve.

Formato errado, referência que não é número, a vírgula decimal que partiu o
número em dois, método que não existe, nome fora do dicionário, tipos que não
formam uma comparação, a mesma comparação duas vezes — ou, já com o banco aberto,
uma variável de grupo com mais grupos do que esta versão compara. A mensagem lista
**todos** de uma vez, pela regra da Fase 5.

### O que sai no disco

### `class Pedido`

*linha 555*

Um item como a ficha o escreve: a variável e, conforme a forma, a referência ou a
variável de grupo — e, quando houver, o método.

`metodo` é o nome como se escreve na ficha, já na forma de `_chave` (`t`,
`student`), e não o teste: o que `t` quer dizer depende do delineamento, e entre
grupos o delineamento só se conhece com o banco aberto.

Nas medidas repetidas, `medidas` são as variáveis, na ordem da ficha, e `variavel`
é a primeira delas.

#### `def escrito(self)`

*linha 575*

O item de volta na forma da ficha, para as mensagens. O de medidas repetidas com
método sai na forma de uma linha só, `{repetidas: [...], metodo: anova}`, que o
YAML lê igual à de duas linhas.

#### `def chave(self)`

*linha 591*

O que faz dois itens serem a mesma comparação: o método não entra — o mesmo
item com outro método é a mesma pergunta feita duas vezes.

### `class Pergunta`

*linha 604*

Um item da ficha, já conferido contra o dicionário. É a pergunta da reunião — "a
média desta variável difere desta referência?", "difere entre estes grupos?" —
com a forma que ela tem.

`delineamento` é `UMA_AMOSTRA`, `GRUPOS` ou `REPETIDAS`: entre grupos, quantos são
só se sabe com o banco aberto. `metodo` é o nome escrito na ficha, como no
`Pedido`. Nas medidas repetidas, `medidas` são as linhas do dicionário de cada uma.

#### `def linhas(self)`

*linha 623*

### `class Normal`

*linha 630*

O Shapiro-Wilk do vetor do delineamento.

Os quatro campos são o que o `normalidade.shapiro` devolve: o W e o p quando o
teste rodou, a frase do impedimento quando não rodou, e o aviso do `scipy` quando
houve um.

#### `def testada(self)`

*linha 645*

#### `def rejeita(self)`

*linha 649*

### `class Grupo`

*linha 654*

Um grupo de uma comparação entre grupos: o rótulo, quantos casos, a média e o
desvio, e o Shapiro-Wilk dos valores dele.

### `class Escolha`

*linha 667*

Qual teste rodou, e de onde ele veio.

`da_regra` é o que a regra escolhe mesmo quando a ficha mandou outro, e mesmo
quando o FlatCap ainda não o faz — é o que permite escrever "contra a regra" na
nota, e dizer qual teste faltou. `metodo` vazio quer dizer que nenhum teste rodou:
a regra escolheu um que ainda não tem aritmética, e a ficha não mandou outro.

#### `def contra_a_regra(self)`

*linha 683*

### `class VariavelComparada`

*linha 688*

Uma pergunta respondida. Na uma amostra é uma linha da tabela; entre grupos, um
bloco — a linha da comparação e uma linha por grupo.

`resultado` fica `None` quando não houve teste; o motivo está em `motivo`, e a
comparação **sai assim mesmo** — um item pedido que sumisse da tabela seria a falta
em que ninguém repara. O resumo sai mesmo sem teste: ele descreve a variável, e não
depende de pressuposto nenhum.

Na uma amostra, `referencia`, `resumo` e `normal` são da variável inteira; entre
grupos, `referencia` é `None`, e o resumo e o Shapiro-Wilk estão em cada `Grupo`.

*linha 719*

> As casas decimais da variável, as do `resumo_<variável>.csv` da descritiva: as
> duas de sempre, ou mais numa variável de escala pequena. Ver `_casas_da_coluna`.

#### `def faltantes(self)`

*linha 724*

#### `def testada(self)`

*linha 728*

#### `def entre_grupos(self)`

*linha 732*

#### `def repetidas(self)`

*linha 736*

#### `def metodo(self)`

*linha 740*

#### `def colunas(self)`

*linha 744*

As colunas do banco que esta comparação usou.

#### `def cabeca(self)`

*linha 753*

Como a comparação se chama nas frases: `IMC (kg/m²) por Sexo`; nas medidas
repetidas, os rótulos delas — `PAS basal, PAS 30 dias e PAS 90 dias`.

#### `def n_na_frase(self)`

*linha 765*

`n = 57`, e entre grupos `n = 57 (29 em Feminino e 28 em Masculino)`. Nas medidas
repetidas o n é um só — os casos com todas as medidas.

#### `def celula_do_teste(self)`

*linha 778*

O que vai para a coluna `teste`: o nome do teste, ou o motivo no lugar dele —
como a coluna `método` da correlação e a `teste` da associação.

#### `def justificativa(self)`

*linha 788*

A frase que explica a comparação — a nota do `.csv` e a linha do terminal.

Uma frase só, montada aqui, para que o arquivo e a tela digam a mesma coisa
com as mesmas casas.

#### `def como_detalhe(self)`

*linha 834*

Os números desta comparação, para o manifesto — o que responde "de onde saiu
esse teste, e esse p?" sem reabrir o banco.

O intervalo vai em `ic_95` quando é o de 95% que a tabela imprime; quando o
teste de postos não o alcança, o de nível menor que o R devolve vai em
`ic_alcancavel`, com o nível — fora da tabela, e não perdido.

### `def _casas_da_coluna(*colunas)`

*linha 933*

As casas decimais da variável, decididas como a descritiva as decide: pela coluna
inteira, e não pelos casos da comparação — a média da uma amostra sai, letra por
letra, a do `resumo_<variável>.csv`, e a de cada grupo sai com as mesmas casas.
Nas medidas repetidas, as da medida que pede mais, para a tabela não misturar.

### `def _resumo_no_manifesto(resumo)`

*linha 948*

As duas formas do resumo, sempre — a média e o desvio, a mediana e os quartis: a
tabela imprime a do teste da linha, e o manifesto guarda as duas, para a mediana de
um grupo, que a descritiva não tem, não morar só na célula.

### `class ForaDaComparacao`

*linha 962*

Uma variável do dicionário que não está em item nenhum, e por quê.

### `class Comparacao`

*linha 973*

A rodada inteira, decidida. É daqui que saem os arquivos e o terminal.

`tabelas` tem uma tabela por delineamento que apareceu na ficha, na ordem de
`DELINEAMENTOS`; um delineamento sem item não tem tabela.

#### `def raiz(self)`

*linha 990*

#### `def linhas(self)`

*linha 994*

#### `def colunas_usadas(self)`

*linha 998*

#### `def testadas(self)`

*linha 1007*

#### `def sem_teste(self)`

*linha 1011*

#### `def pela_ficha(self)`

*linha 1015*

#### `def quantos(self, metodo)`

*linha 1018*

#### `def do_delineamento(self, delineamento)`

*linha 1021*

#### `def tabela_de(self, delineamento)`

*linha 1024*

### `class PlanoComparacao`

*linha 1029*

Tudo o que a `comparacao` faria, decidido e ainda não escrito.

Imutável como os planos das outras fases, e pela mesma razão: entre a simulação e
a execução ninguém altera um caminho em trânsito.

#### `def raiz(self)`

*linha 1044*

#### `def tabelas(self)`

*linha 1048*

#### `def arquivos(self)`

*linha 1052*

### `class ResultadoComparacao`

*linha 1057*

O que a execução de fato escreveu.

### Casos de uso

### `def preparar_comparacao(raiz, aba, conferir, agora)`

*linha 1070*

Lê os itens da ficha, abre o banco, compara cada item e monta o plano. Não
escreve nada.

A lista da ficha é conferida **antes** de abrir o banco, como na correlação: um
item escrito fora do formato — a vírgula decimal, principalmente — é o engano
mais provável deste comando, e descobri-lo não deve custar a releitura do
`sha256` de um banco grande.

Args:

    raiz: a pasta do projeto (a que tem o `projeto.yaml`).
    aba: planilha do `.xlsx`, quando houver mais de uma.
    conferir: reler o `sha256` das versões e comparar com a ficha.
    agora: relógio injetável, como nas outras fases.

Raises:

    FichaError, BancoError, DicionarioInvalidoError e as recusas declaradas
    acima.

### `def executar_comparacao(plano)`

*linha 1123*

Escreve o plano no disco. Não decide mais nada.

A ordem é a da Fase 5: arquiva a rodada anterior, cria a pasta, escreve as
tabelas, e só então o `manifesto.json` — o recibo vem depois do que ele descreve.
Uma falha no meio desfaz o que já foi feito, inclusive devolvendo a pasta
arquivada ao lugar, e a exceção continua subindo inteira.

*linha 1145*

> `existia` antes do `mkdir`: a pasta só entra no desfazer quando foi este
> comando que a criou, e o `rmdir` é registrado antes dos arquivos — o
> desfazer roda ao contrário e a pasta sai vazia, a única forma de sair.

### `def comparar(banco, ficha, linhas_do_dicionario, pedidos, quando)`

*linha 1190*

Compara cada item pedido, obedecendo ao dicionário. Função pura.

O miolo testável, como o `correlacionar` da correlação e o `avaliar` da
normalidade: um `DataFrame` montado à mão, uma lista de `Linha` e os itens
entram, e as afirmações são sobre as tabelas — sem pasta de projeto e sem disco.

Duas conferências: a da ficha contra o dicionário, antes de tocar nos valores, e a
dos grupos contra o banco — quantos grupos a variável tem entre os casos com as
duas respostas —, que só se faz com os valores na mão. As duas listam todos os
problemas de uma vez.

Args:

    pedidos: os itens como `itens_da_ficha` os devolve — ou tuplas, que é como um
        teste os escreve: `("imc", 25)`, `("imc", 25, "t")`, `("imc", "sexo")`,
        `("imc", "sexo", "student")`.

Raises:

    SemItensError, ItemInvalidoError, VariavelIncompativelError

*linha 1227*

> Só as variáveis da lista vão para a recusa: a conferência é a da Fase 5, e o
> escopo é deste comando.

### Uma variável, contra a referência

### `def _comparar_uma_amostra(quadro, pergunta, total)`

*linha 1283*

Mede o pressuposto, aplica a regra (ou obedece à ficha) e calcula.

Os faltantes são **por variável**: entram os valores preenchidos desta coluna, e o
`n` da linha é quantos são. É o mesmo tratamento da normalidade e da descritiva, e
é o que faz a média daqui ser a do `resumo` e o p do Shapiro-Wilk ser o da tabela
de normalidade.

Três barreiras vêm antes da regra, e as três deixam a linha sem teste qualquer que
seja o método escrito na ficha — são as do próprio `t.test` do R: nenhum valor,
um valor só, e valores que não variam. Valem para o Wilcoxon também, que o R
calcularia com um valor só, ou com todos iguais: um valor não é uma amostra, e uma
variável que não varia não tem o que comparar.

- *linha 1302* — `if serie is None:` — pragma: no cover - `recusar_incompativeis` já barrou

### `def _impedimento(valores, validos, distintos)`

*linha 1357*

O motivo de não haver teste nenhum, ou vazio.

As barreiras do `t.test`, com a frase de cada uma no lugar do `stop()` do R. A
terceira usa o critério do R, e não "todos iguais": ver `hipoteses.sem_variacao`.

### `def _normal(variavel, valores)`

*linha 1375*

O Shapiro-Wilk da normalidade, pela mesma função, sobre os valores preenchidos.

### `def _motivo_sem_teste(normal, validos)`

*linha 1383*

O motivo curto, para a célula da coluna `teste`, quando a regra escolheu um teste
que ainda não existe. A frase inteira, com o p do Shapiro-Wilk, vai para as notas.

**Sem o p na célula**, e foi a página que decidiu: na coluna estreita do documento
`(p < 0,001)` quebrava entre o `<` e o número, e a célula ocupava quatro linhas
para repetir o que a tabela de normalidade do mesmo documento já imprime.

### `def _avisos_da_linha(nome, pergunta, escolha, normal, validos, distintos)`

*linha 1397*

O que a escolha precisa levar junto para o terminal e para o manifesto.

Cinco casos, e cada um é um engano conhecido ou uma decisão que precisa de rastro:

* **a linha sem teste porque o teste da regra ainda não existe.** O aviso diz como
  escrever `t` no item, para quando você concluir que ele vale ali;
* **a ficha contra a regra.** A decisão é sua, e o aviso é o registro de que ela
  foi tomada contra o que a regra diria;
* **o t pela regra com poucos valores.** Abaixo de `MINIMO_CONFIAVEL` o
  Shapiro-Wilk quase não rejeita, e a regra escolheu o t por falta de evidência
  contra ele — não por evidência a favor;
* **a variável discreta com a normal rejeitada.** Numa escala o Shapiro-Wilk
  rejeita quase sempre, e a rejeição diz «discreta», e não «forma errada»;
* **o recado do `scipy` sobre o Shapiro-Wilk**, repassado como ele veio.

### `def _aviso_contra_a_regra(nome, escolha, faltou)`

*linha 1452*

### `def _aviso_de_discreta(nome, distintos, validos)`

*linha 1461*

### `def _avisos_do_resultado(nome, resultado, tamanhos, valores)`

*linha 1470*

O que o Wilcoxon e o Mann-Whitney devolvem e precisa de rastro — os três casos são
de amostra pequena, ou de amostra sem variação, e nenhum deles é erro:

* **o menor p possível acima do α.** No caminho exato, o p mais extremo que a
  distribuição tem é 2/2ⁿ no Wilcoxon e 2/C(n₁ + n₂, n₁) no Mann-Whitney; com cinco
  valores ou menos no Wilcoxon — e, no Mann-Whitney, com um valor contra até 38,
  dois contra até sete, ou três contra até quatro —, ele passa de 0,05, e o teste não
  rejeita a igualdade com dado nenhum. Um p de 0,125 ali não é «nenhuma diferença»:
  é o menor que existe;
* **o intervalo que não chega a 95%** — o R baixa o nível e avisa. A tabela promete
  95%, e a célula sai com o traço;
* **o intervalo que não existe**: sem os valores iguais à referência, os que sobram
  são todos iguais; ou os dois grupos não variam por dentro. O p sai, e a célula,
  com o traço.

`tamanhos` são os n do teste — o da uma amostra, ou o de cada grupo —, e `valores`,
como eles se escrevem na frase.

### `def _menor_p_exato(metodo, tamanhos)`

*linha 1534*

O menor p bilateral que o caminho exato dá: as duas caudas mais extremas da
distribuição, com uma combinação cada — 2/2ⁿ no Wilcoxon, 2/C(n₁ + n₂, n₁) no
Mann-Whitney —, e nunca acima de 1.

### Uma variável, entre os grupos de outra

### `def _comparar_grupos(quadro, pergunta, total)`

*linha 1549*

Separa os grupos, mede o pressuposto em cada um, aplica a regra (ou obedece à
ficha) e calcula. Devolve a comparação, ou `None` e a frase do que este banco não
deixa comparar — que o `comparar` junta às dos outros itens numa recusa só.

**Os faltantes são por comparação**: entra quem respondeu as duas variáveis, e o
`n` da comparação é quantos são. **O código conta, o rótulo imprime**, como no
cruzamento e na associação: os grupos são os rótulos, e dois códigos com o mesmo
rótulo somam no mesmo grupo. A ordem é a do dicionário, e é ela que decide o sinal
da diferença: o primeiro grupo menos o segundo, como o `t.test` da fórmula do R
faz com os níveis do fator.

Três barreiras vêm antes da regra — nenhum caso com as duas respostas, um grupo
só, um valor só em todas as linhas —, e as do teste escolhido vêm depois dela:
cada teste tem o seu mínimo no R.

- *linha 1573* — `if serie is None or coluna_do_grupo is None:` — pragma: no cover - a recusa já barrou

### `def _delineamento_dos_grupos(quantos, de_grupo)`

*linha 1676*

O delineamento pelo número de grupos com resposta: dois, ou três ou mais.

Com nenhum grupo ou um só, não há teste, e a linha sai na tabela que o dicionário
promete — a dos k grupos quando ele declara três rótulos ou mais, e a dos dois nos
outros casos: a pergunta foi feita sobre aqueles grupos, e o banco não os tem.

### `def _impedimento_dos_grupos(validos, quantos, distintos)`

*linha 1692*

O motivo de não haver teste nenhum entre grupos, ou vazio. Vale para qualquer
teste, escrito na ficha ou não.

### `def _impedimento_do_teste(metodo, amostras, grupos)`

*linha 1706*

O motivo de o teste escolhido não rodar, ou vazio — as barreiras do R para ele,
que mudam de teste para teste.

O t de Student aceita um grupo de um valor só, desde que haja três no total: a
variância combinada é toda do outro grupo, e o R calcula. O de Welch não: cada
grupo entra com a sua variância, e a de um valor só não existe. Os dois recusam,
como o R, dois grupos que não variam por dentro — mesmo com médias diferentes, o t
seria uma divisão por zero.

A ANOVA pede dois valores em cada grupo, como o `oneway.test` — que recusa o grupo
de um valor, embora o `aov` o aceite. E grupos que não variam por dentro a barram
aqui, e não no R: lá o F sai infinito, e o p, zero. Na de Welch basta **um** grupo
que não varia — o peso dele é n/0, e o R devolve `NaN`; a clássica, com a variância
combinada dos outros, roda.

O Mann-Whitney e o Kruskal-Wallis não têm barreira além das que valem para todos:
pedem um valor em cada grupo, como o R, e grupos que não variam por dentro, cada um
com o seu valor, são para eles a separação mais clara que existe — e não uma divisão
por zero.

### `def _sem_variacao_nos_grupos(amostras)`

*linha 1779*

### `def _normal_do_grupo(variavel, rotulo, valores, onde)`

*linha 1785*

O Shapiro-Wilk de um grupo — ou de uma medida, nas repetidas —, pela mesma função
da normalidade.

O grupo que não varia é barrado aqui, e não lá: a frase e o aviso do
`normalidade.shapiro` para esse caso falam da **coluna** ("a coluna tem um valor
só"), e aqui a coluna varia — quem não varia é o grupo, ou a medida entre os casos
completos.

### `def _motivo_sem_teste_dos_grupos(escolha, grupos, delineamento)`

*linha 1805*

O motivo curto, para a célula, quando a regra escolheu um teste que ainda não
existe. Sem o p, pela mesma razão da uma amostra; a frase inteira vai para as
notas.

### `def _avisos_dos_grupos(nome, pergunta, escolha, grupos, delineamento, validos, distintos)`

*linha 1823*

Os avisos da uma amostra, na forma dos grupos, e um a mais.

* **a linha sem teste** diz qual método escrever no item: o paramétrico da regra
  quando ele existe, senão o que existe — a `anova` clássica, onde a de Welch
  ainda falta;
* **a ficha contra a regra**, como na uma amostra;
* **o paramétrico pela regra com um grupo pequeno** — o Shapiro-Wilk de cada
  grupo é que quase não rejeita abaixo de `MINIMO_CONFIAVEL`;
* **a variável discreta com a normal rejeitada**, como na uma amostra;
* **o teste que supõe variâncias iguais**, com o maior desvio padrão contra o
  menor: é o que o de Welch dispensaria, e o número fica escrito para quem
  escolheu o de Student;
* **o recado do `scipy`**, de cada grupo.

### `def _aviso_de_variancias(nome, metodo, grupos, delineamento)`

*linha 1892*

O maior desvio padrão contra o menor, quando o teste supõe variâncias iguais e
eles passam de `RAZAO_DE_DESVIOS` — ou quando um grupo não varia.

Só os grupos com dois valores ou mais: o desvio de um valor só sai zero no
`resumo`, e não diz nada sobre a variância.

### `def _metodo_sugerido(delineamento)`

*linha 1929*

O método para o aviso ensinar a escrever: o paramétrico da regra, quando ele
existe, e senão o primeiro paramétrico que existe — o nome como se escreve e o
teste.

### `def _problema_do_metodo(chave, teste, delineamento, de_grupo, quantos)`

*linha 1947*

O método escrito que não serve para o número de grupos que o banco trouxe, ou
vazio. A ficha é conferida antes de abrir o banco, mas só o banco diz quantos
grupos há — e um método de dois grupos numa variável de três é recusado aqui.

### As medidas repetidas

### `def _comparar_repetidas(quadro, pergunta, total)`

*linha 1973*

As mesmas pessoas, medidas k vezes: mede o pressuposto em cada medida, aplica a
regra (ou obedece à ficha) e calcula.

**Os faltantes são por item, e inteiros**: entra quem tem todas as medidas — o
caso com uma faltando sai do item, como no `lm` do R, porque a ANOVA de medidas
repetidas compara cada pessoa com ela mesma. O Shapiro-Wilk roda em cada medida,
sobre esses casos: é a normalidade que o teste usa, e é a checagem por momento que
se faz no R antes de uma ANOVA de medidas repetidas.

Duas barreiras antes da regra — nenhum caso completo, ou um só, e um valor só em
todas as células —, e a do teste escolhido depois dela: na ANOVA, medidas que não
variam dentro dos casos, em que o F é uma divisão por zero; no Friedman, cada caso
com o mesmo valor em todas as medidas, em que não há o que ordenar. Ver
`_impedimento_das_medidas`.

- *linha 1994* — `if any(coluna is None for coluna in colunas):` — pragma: no cover - a recusa já barrou

### `def _impedimento_das_medidas(metodo, vetores, pergunta)`

*linha 2067*

A barreira do teste das medidas repetidas — o motivo curto e o aviso —, ou dois
vazios. Cada teste tem a sua, e uma não é a outra:

* **a ANOVA, quando as medidas não variam dentro dos casos** — cada caso mudando o
  mesmo tanto de uma medida para outra. A variação de erro é zero, e o F, uma
  divisão por zero. É justamente o caso em que o Friedman tem mais a dizer: todo
  caso ordena as medidas do mesmo jeito. O aviso ensina a escrevê-lo;
* **o Friedman, quando cada caso tem o mesmo valor em todas as medidas.** Não há o
  que ordenar dentro de caso nenhum, e o qui-quadrado é 0/0 — o R devolve `NaN`.

### `def _impedimento_das_repetidas(validos, distintos)`

*linha 2099*

### `def _avisos_das_repetidas(nome, pergunta, escolha, grupos, validos, distintos)`

*linha 2109*

Os avisos dos grupos, na forma das medidas: a linha sem teste ensina a escrever o
método no item — `metodo: anova`, na linha de baixo —; a ficha contra a regra; o
teste pela regra com menos de `MINIMO_CONFIAVEL` casos; a variável discreta; e o
recado do `scipy`. O das variâncias não entra: a ANOVA de medidas repetidas não
supõe variâncias iguais entre as medidas, e a correção de Greenhouse-Geisser é
justamente para quando a covariância foge da esfericidade.

### A regra

### `def regra(delineamento, normal)`

*linha 2158*

A regra dos pressupostos: o teste que ela escolhe, e o motivo.

O Shapiro-Wilk não rejeitou → o paramétrico do delineamento. Rejeitou, ou não
pôde ser verificado → o que dispensa a normal. Se esse ainda não tem aritmética,
a `Escolha` sai com `metodo` vazio e `da_regra` preenchido: a linha fica sem teste,
e a nota diz qual faltou.

Na uma amostra recebe o `Normal` da variável; entre grupos, os `Grupo`, cada um
com o seu — e a normal se sustenta quando se sustenta **em todos**: um grupo que
rejeita basta para o paramétrico não valer.

Não olha o método escrito na ficha: quem o aplica é quem chama, por cima do que a
regra devolveu — e é assim que a nota consegue dizer o que a regra teria
escolhido.

### `def _pela_regra(delineamento, teste, motivo)`

*linha 2222*

### `def _disponivel(delineamento, teste)`

*linha 2227*

### As tabelas

### `def _tabelas(variaveis, total)`

*linha 2234*

Uma tabela por delineamento que apareceu na ficha, na ordem de `DELINEAMENTOS`, e
os itens de cada uma na ordem da ficha.

### `def linhas_da_tabela(variavel)`

*linha 2253*

As linhas de uma comparação na tabela do delineamento dela.

Na uma amostra, uma linha. Entre grupos, um bloco: a linha da comparação — o
rótulo da variável, o da variável de grupo, o n dos casos com as duas respostas, a
diferença (entre dois grupos), o teste e o p — e uma linha por grupo, com o n, a
média e o desvio. Nas medidas repetidas, uma linha por medida, com o teste e o p na
primeira: não há variável de grupo para uma linha de cabeça.

Pública porque o terminal desenha as mesmas linhas, item por item, com os
destaques dele: as células saem daqui, e de mais lugar nenhum.

O resumo de cada linha é o do teste dela — a média e o desvio, ou a mediana e os
quartis —, e o intervalo só entra quando é o de 95% que o cabeçalho promete.

### `def _teste_da_linha(variavel)`

*linha 2322*

O teste que a linha mostra, ou que teria mostrado: o que rodou; o escolhido, quando
uma barreira dele o impediu de rodar; o da regra, quando ela escolheu um que ainda
não tem aritmética. Vazio quando nenhum teste chegou a ser escolhido.

### `def _de_postos(variavel)`

*linha 2334*

### `def _resumo_da_linha(variavel, resumo)`

*linha 2338*

O resumo de um grupo, de uma medida ou da variável, na medida que o teste da linha
usa: a mediana e os quartis nos testes de postos, a média e o desvio nos outros — e
quando não há teste nenhum, que é como a tabela sempre resumiu.

### `def _coluna_do_resumo(variaveis)`

*linha 2349*

O cabeçalho da coluna do resumo, pelo que ela tem: as linhas sem resumo nenhum — o
traço de quem não tem valor — não contam.

### `def _coluna_do_intervalo(variaveis)`

*linha 2366*

O cabeçalho do intervalo da uma amostra, pelo teste de cada linha — o que rodou, ou
o que a regra escolheu —, como o do resumo: o traço de um intervalo que não chega a
95% fica debaixo do nome do intervalo que faltou, e não do da média. As linhas sem
teste nenhum não contam, e uma tabela só delas fica com o da média, de sempre.

### `def _coluna_da_diferenca(variaveis)`

*linha 2381*

O cabeçalho da diferença entre dois grupos, pelo teste de cada linha, como o do
intervalo da uma amostra: as linhas sem teste nenhum não contam, e uma tabela só do
t — ou sem teste nenhum — fica com o de sempre.

### `def _ic_da_tabela(resultado)`

*linha 2395*

O intervalo que vai para a tabela: o de 95%, e só ele. Quando o R não o alcança —
poucos valores num teste de postos —, ele devolve um de nível menor, que fica no
manifesto e no aviso, e não numa coluna que promete 95%.

### `def _tabela_uma_amostra(variaveis, total)`

*linha 2408*

Uma linha por item, na ordem da ficha.

As sete colunas — `variável`, `n`, o resumo, o intervalo, `referência`, `teste` e
`p-valor` —, com o **rótulo** do dicionário na primeira. O resumo e o intervalo têm
o cabeçalho do que levam: `média (DP)` e `IC 95% da média` quando todas as linhas
são do t, e os do Wilcoxon quando ele aparece. O que decidiu cada teste — o p do
Shapiro-Wilk, a estatística, os graus de liberdade, o caminho do p — vai para as
notas do `.csv`, uma frase por linha, e para o manifesto.

*linha 2450*

> Vazia de propósito: esta tabela fala de várias variáveis.

### `def _tabela_dois_grupos(variaveis, total)`

*linha 2467*

Um bloco por item, na ordem da ficha: a linha da comparação e uma linha por grupo.

Sete colunas, como a da uma amostra — `variável`, `grupo`, `n`, o resumo, a
diferença, `teste` e `p-valor`. A coluna `grupo` leva o rótulo da
variável de grupo na linha da comparação e o de cada grupo nas seguintes, que é
como uma tabela descritiva põe uma categórica: o nome, e as categorias embaixo.
A diferença é a do teste da linha, com o intervalo dele — o do de Welch não é o do
de Student, e a diferença de locação do Mann-Whitney não é nenhuma das duas —, e o
cabeçalho dela diz qual: `diferença (IC 95%)` quando todas as linhas são do t, como
sempre foi, `diferença de locação (IC 95%)` quando são do Mann-Whitney.

### `def _tabela_k_grupos(variaveis, total)`

*linha 2535*

Um bloco por item, como a dos dois grupos, sem a coluna da diferença: com três
grupos ou mais não há uma diferença só. Seis colunas — `variável`, `grupo`, `n`, o
resumo, `teste` e `p-valor` —; o F, o qui-quadrado e os graus de liberdade vão para
as notas, com o resto do que decidiu cada teste.

### `def _tabela_repetidas(variaveis, total)`

*linha 2590*

Um bloco por item: uma linha por medida, na ordem da ficha, e o teste e o p na
primeira. Cinco colunas — `medida`, `n`, o resumo, `teste` e `p-valor`.

O n é o mesmo em todas as linhas do bloco — os casos com todas as medidas, que são
os que entram no teste —, e o resumo de cada medida é o desses casos: com faltante
em alguma medida, ele difere do `resumo` da descritiva, e a nota diz isso.

### `def _ainda_nao(delineamento)`

*linha 2641*

A frase das notas sobre os testes da regra que ainda não têm aritmética — com o
espaço do fim, para entrar entre duas frases —, ou vazio, que é o caso de todos os
delineamentos desde a 1.14.0.

### Os itens da ficha

### `def itens_da_ficha(raiz)`

*linha 2662*

A lista `comparacao:` do `projeto.yaml`, conferida na forma e desdobrada.

Quatro formas de item, e todas podem conviver:

    - [imc, 25]                # contra uma referência; a regra escolhe o método
    - [imc, sexo, student]     # entre os grupos de outra variável, com o método
    - sexo: [imc, idade]       # uma contra várias: cada uma entre os grupos de sexo
    - repetidas: [pas_0, pas_1, pas_2]   # a mesma medida, três vezes nos mesmos casos
      metodo: anova                      # o método, quando vier, na chave ao lado

A terceira devolve um item por nome da lista, na ordem em que foram escritos. O
método não se escreve nela: ficaria misturado aos nomes, como na correlação. Na
quarta ele tem a chave dele, porque a lista das medidas não tem um terceiro lugar.

Devolve vazio quando a chave não existe ou está vazia — quem recusa isso é o
`comparar`, que tem o dicionário na mão para escrever quais variáveis existem.
Formato errado recusa em vez de ignorar: um item que o comando pulasse em silêncio
é o pior dos dois mundos — você escreveu, e não valeu.

Lida pelo `ficha.bloco`, e não abrindo o YAML aqui: o `ficha.py` é o único módulo
do pacote que abre o `projeto.yaml`.

Raises:

    ItemInvalidoError

### `def _ler_item(item)`

*linha 2725*

Um item da lista: os `Pedido` que ele escreve, ou a frase do que está errado nele.

### `def _ler_grupos(item, escrito, nome, grupo)`

*linha 2813*

O item entre grupos: `[imc, sexo]`, ou `[imc, sexo, student]`.

### `def _ler_repetidas(item)`

*linha 2844*

O item de medidas repetidas — a marca `repetidas:` e a lista das medidas, na ordem
em que foram feitas, e o método numa chave ao lado, quando vier:

    - repetidas: [pas_0, pas_1, pas_2]
      metodo: anova

Três medidas ou mais: com duas, a pergunta é a do t pareado, que usa esta mesma
forma e ainda não está no FlatCap — e a recusa diz isso, em vez de rodar uma ANOVA
que é o t pareado ao quadrado.

### `def _ler_uma_contra_varias(item)`

*linha 2894*

A forma com dois-pontos: `sexo: [imc, idade]` — cada variável da lista entre os
grupos da que vem antes dos dois-pontos.

### `def _metodo_na_ficha(escrito, texto, familia)`

*linha 2928*

O método escrito no item, conferido contra a forma dele: devolve o nome na forma
de `_chave`, ou a frase do que está errado.

A forma diz a família de delineamentos — a uma amostra, ou os grupos —, e o
método precisa querer dizer um teste que existe em algum deles. Entre grupos, se
ele serve para o número de grupos que o banco tem só se sabe depois: ver
`_problema_do_metodo`.

### `def _metodos_de(familia)`

*linha 3002*

Os nomes que se escrevem no item e têm teste com aritmética na família.

### `def _e_metodo(texto)`

*linha 3012*

### `def _teste_da_chave(chave, delineamento)`

*linha 3017*

### `def metodo_escrito(texto, delineamento)`

*linha 3021*

O teste que o método escrito na ficha quer dizer no delineamento, como a tabela o
escreve; vazio quando o texto não é um método dele, ou quando o teste ainda não
está no FlatCap.

Tolerante na leitura, como o da correlação: `T`, `t` e `Student` são o mesmo, e
`mann-whitney` e `Mann Whitney` também. O delineamento muda o sentido: `t` é o de
Student contra uma referência, e o de Welch entre dois grupos.

### `def referencia_escrita(valor)`

*linha 3035*

O valor de referência, a partir de como a ficha o trouxe; `None` quando não é um
número.

Número do YAML entra como está. Texto entra quando é um número escrito — com
vírgula ou ponto decimal, e sem separador de milhar: é o `"24,9"` entre aspas que
a recusa da vírgula decimal ensina a escrever. Lógico não é número, embora o
Python ache que `True` vale 1.

A regra mora no `ficha.numero_escrito` desde a 1.15.0, quando a amostragem passou a
ler o `desenho.yaml` com ela; o nome continua aqui, porque é o que esta análise
pergunta — "qual é a referência?".

### `def _numero_partido(item)`

*linha 3052*

O `[imc, 24,9]` que o YAML leu como `[imc, 24, 9]`: o número de volta, com ponto
— `24.9` —, e se o sinal dele se perdeu; `None` quando o item não tem essa forma.

A forma é um inteiro depois do nome, e depois dele os algarismos da parte decimal
— e o que vier depois, quando vier, sendo um método: `[imc, 24,9, t]` é o mesmo
engano. A recusa sugere o número para copiar, e por isso ele precisa sair
**exato**: com o zero à esquerda da parte decimal (ver `_digitos`), e com o aviso
de que o sinal de `-0,5` não sobrevive à leitura — o YAML lê `-0` e `0` como o
mesmo inteiro.

### `def _digitos(valor)`

*linha 3075*

Os algarismos de um inteiro sem sinal como foram digitados — `05`, e não `5` —, ou
vazio quando o valor não é um.

O zero à esquerda é o que separa `24,05` de `24,5` quando a vírgula decimal parte o
número, e a recusa não pode sugerir o número errado para copiar. O `ruamel` guarda
a largura de um inteiro escrito com zero à esquerda no `_width` do `ScalarInt`, que
o `ficha.bloco` deixa passar; sem ela, os algarismos são os do próprio número — e
é o caso de todo inteiro escrito sem zero à esquerda. Um texto só de algarismos
também serve: é como outra biblioteca de YAML leria o `09`.

### `def _inteiro(valor)`

*linha 3101*

### `def _como_pedido(item)`

*linha 3105*

### `def _metodos_da_chave(chave, familia)`

*linha 3134*

### `def _pedido_de(pergunta)`

*linha 3140*

### `def _conferir_itens(pedidos, linhas)`

*linha 3151*

Confere cada item contra o dicionário, e recusa listando todos os problemas.

Contra uma referência, quatro coisas: o nome não está no dicionário; a variável
está marcada `ignorar` ou fora desta versão do banco; ela não é numérica — a média
de um código não é uma média, e uma data tem média, mas a comparação dela com uma
referência não quer dizer nada —; o item repete outro, mesmo com outro método, que
seria fazer a mesma comparação duas vezes e ficar com o p que convier.

Entre grupos, as mesmas para as duas variáveis, e os tipos precisam formar a
comparação: a primeira numérica, a segunda categórica. Os outros arranjos são
outras análises, e a recusa diz qual — duas categóricas são uma associação, duas
numéricas são uma correlação —, ou diz que os dois nomes estão trocados.

### `def _motivo_de_recusa(nome, linha)`

*linha 3240*

### `def _motivo_de_ausencia(nome, linha)`

*linha 3254*

### `def _motivo_de_recusa_das_medidas(nomes, por_nome)`

*linha 3264*

O que impede as medidas repetidas, pelo dicionário — ou vazio. As medidas com o
mesmo problema saem numa frase só: três medidas marcadas `categorica` são uma
decisão do dicionário, e não três.

### `def _crases(nomes)`

*linha 3311*

### `def _verbo(nomes, singular, plural)`

*linha 3315*

### `def _motivo_de_recusa_entre_grupos(pedido, por_nome)`

*linha 3319*

O que impede o item entre grupos, pelo dicionário — ou vazio.

### O manifesto

### `def montar_manifesto(comparacao, linhas)`

*linha 3373*

Traduz a rodada para o índice que o relatório vai ler.

**Um item só**, como na normalidade, na associação e na correlação: a seção do
documento é uma seção de comparação, com uma tabela por delineamento. O `colunas`
do item diz quais colunas do banco entraram — as de grupo também —, que é o que
mantém as conferências do relatório certas para uma seção que não é de uma
variável. O que decidiu cada teste vai em `detalhes`, sob o nome do delineamento.

### `def _regras()`

*linha 3466*

As regras desta versão, escritas por extenso no manifesto — as mesmas das notas
das tabelas, sem os números de uma rodada.

#### `def escolha(delineamento, onde, depois)`

*linha 3471*

### `def _ambiente()`

*linha 3607*

As versões que produziram estes números.

O `scipy` entra, porque o Shapiro-Wilk e a distribuição t são dele. O `matplotlib`
e a `fonte` saem `None` — a rodada não desenha —, e as chaves continuam lá para o
bloco ter a forma dos outros.

### `def _shapiro_no_manifesto(normal)`

*linha 3629*

### Mensagens

### `def _mensagem_sem_itens(linhas)`

*linha 3643*

### `def _motivo_de_fora(linha)`

*linha 3680*

### `def _acao_do_historico(plano)`

*linha 3688*

### Leitura da série e formatação

### `def _coluna(quadro, nome)`

*linha 3716*

A coluna do banco pelo nome, ou `None` — pela posição, como nas outras análises:
nome repetido devolveria um `DataFrame` no lugar de uma coluna.

### `def _rotulo(linha)`

*linha 3727*

### `def _nome(valor)`

*linha 3731*

Um nome, como a ficha o trouxe; vazio quando não é um nome.

Número não é nome: é a referência escrita no lugar errado. Lista e bloco dentro
da lista também não — é o `[[imc, 25]]` digitado com um colchete a mais.

### `def _simplificado(texto)`

*linha 3743*

### `def _chave(texto)`

*linha 3748*

O método como ele se procura no `METODOS`: sem acento, minúsculo, e só letras e
algarismos — `Mann-Whitney`, `mann whitney` e `MANN_WHITNEY` são o mesmo —, com as
outras grafias do `_SINONIMOS` trocadas pela da casa.

### `def _concorda(teste, participio)`

*linha 3758*

`t de Welch escrito`, `ANOVA escrita`: o participio no gênero do teste.

### `def _com_artigo(teste, maiuscula)`

*linha 3763*

`o t de Welch`, `a ANOVA` — e, no começo da frase, `O t de Welch`, `A ANOVA`.

### `def _em_frase(itens)`

*linha 3769*

`A`, `A e B`, `A, B e C`.

### `def _ou(nomes)`

*linha 3777*

`` `t` ``, `` `t` ou `student` ``, com as crases.

### `def _unidades(delineamento)`

*linha 3785*

O que se compara no delineamento, no singular e no plural.

### `def _nenhum(delineamento, quantos)`

*linha 3790*

`nenhum dos dois grupos`, `nenhum dos 3 grupos`, `nenhuma das 3 medidas`.

### `def _p_na_frase(p)`

*linha 3797*

O p dentro de uma frase: `p = 0,412`, ou `p < 0,001` — nunca `p = < 0,001`.

### `def _estatistica_em_texto(resultado)`

*linha 3805*

`t = 2,16; 56 gl`, `F = 6,39; 2 e 57 gl` — e, nas medidas repetidas, o ε de
Greenhouse-Geisser que corrigiu os gl: `F = 35,44; 1,62 e 14,55 gl; ε = 0,808`. No
Wilcoxon e no Mann-Whitney, o caminho do p, que muda com o n e com os empates:
`V = 70; p exato`, `W = 25,5; p aproximado pela normal, …, porque há empates`.

### `def _media_e_desvio(resumo, casas)`

*linha 3820*

`26,41 (4,12)` — a média e o desvio como o `resumo_<variável>.csv` os escreve,
pelo mesmo `numero()` e com as mesmas casas.

### `def _mediana_e_quartis(resumo, casas)`

*linha 3830*

`25,9 [23,1 a 28,7]` — a mediana e os quartis como o `resumo_<variável>.csv` os
escreve, pelo mesmo `numero()` e com as mesmas casas, com os quartis entre
colchetes e o `a` do intervalo.

### `def _intervalo(intervalo, casas)`

*linha 3842*

### `def _diferenca(resultado, casas)`

*linha 3849*

`-1,52 (-3,21 a 0,17)` — a estimativa do teste e o intervalo dela, com as casas
fixas do intervalo da uma amostra: a diferença das médias no t, a diferença de
locação no Mann-Whitney. Sem o intervalo de 95%, o traço na célula inteira.

### `def _fixo(valor, casas)`

*linha 3861*

Casas fixas — as duas de sempre, ou as da variável quando a escala dela é pequena
—, o hífen do teclado no negativo, e nunca `-0,00` — o formato do coeficiente da
correlação: o Excel em português lê a célula como número, e um zero não tem
direção.

### `def _referencia_em_texto(valor, ponto)`

*linha 3874*

A referência como foi escrita, sem os zeros do fim: `25`, `24,9`, `0,125`.

Com `ponto`, a forma da ficha — `24.9` —, para as mensagens ensinarem a escrever
o que funciona.

### `def _descrever_valor(valor)`

*linha 3885*

### `def _descrever_solto(valor)`

*linha 3897*

Um valor como ele apareceria dentro dos colchetes da ficha.

### `def _arredondar(valor)`

*linha 3906*

### `def _significativos(valor)`

*linha 3913*

O p no manifesto, com seis algarismos significativos, e não seis casas — o da
correlação. Com seis casas, um p de 2,5e-08 seria gravado como `0.0`.

### `def _integridade(confere)`

*linha 3924*

## `flatcap/analises.py`

`SPDX-FileCopyrightText: 2026 Matheus Fernandes` · `SPDX-License-Identifier: GPL-3.0-or-later`

*1009 linhas.*

O lote — as análises da lista `analises:` do projeto.yaml, de uma vez.

Cada análise tem o seu comando, e todos continuam existindo: `flatcap descritiva`,
`flatcap correlacao` e os outros quatro. Este módulo é para o dia em que a reunião
combinou quatro delas — em vez de quatro comandos, um, o `flatcap analisar`:

    plano = preparar_analises(raiz)   # prepara todas; se uma recusa, nada é escrito
    executar_analises(plano)          # escreve todas, na ordem da lista

E, como as análises que ele chama, **não fala com o REDCap**. Recebe `Path`, não
`Config`.

### A soma dos comandos, e nada além

Não há aqui uma segunda forma de descrever, testar ou arquivar. Cada análise é
preparada pelo `preparar_*` dela e escrita pelo `executar_*` dela, com os mesmos
argumentos que o comando dela passaria — e por isso a rodada que o lote escreve é,
byte a byte, a que o comando dela escreveria no mesmo minuto. É o critério de pronto
deste módulo, e há teste com esse nome. No dia em que a correlação mudar, o lote muda
junto sem que uma linha daqui mude.

O preço é o banco aberto uma vez por análise, e não uma vez só: cada `preparar_*`
chama o `banco.abrir` dele, com a conferência do `sha256`. Num banco de algumas
centenas de linhas são décimos de segundo por análise — os gráficos a 600 DPI custam
mais do que isso. Abrir uma vez só pediria um parâmetro novo em seis módulos e
entregaria o mesmo `DataFrame` a seis análises, e a primeira que o alterasse por
engano mudaria as outras cinco. Seis leituras dão seis quadros independentes, que é
o que cada comando já faz sozinho.

### As três regras, do plano da Fase 7

**Obedece à lista, e não escolhe.** Quais análises rodam é decisão do estatístico,
tomada na reunião e escrita na ficha — a mesma regra que faz cada análise ler os pares
da ficha em vez de deduzi-los do dicionário. Lista vazia recusa, e a recusa escreve a
linha pronta para copiar a partir dos blocos que a ficha já tem. Nome que o FlatCap
não conhece recusa com a grafia certa. Nome repetido recusa, porque a posição na lista
é a posição da seção no relatório, e uma análise não tem duas.

**Prepara todas antes de escrever qualquer uma.** É o `preparar`/`executar` da casa
aplicado à corrente. Se a correlação vai recusar porque uma variável não existe, isso
precisa aparecer antes de a descritiva arquivar a rodada anterior — senão sobra uma
rodada velha arquivada e metade da nova escrita. As recusas saem **todas de uma vez**,
pelo motivo da descritiva: descobrir a segunda depois de corrigir a primeira é o jeito
mais lento de arrumar uma ficha. A exceção é o que vale para todas — a ficha, o banco,
o dicionário —, que para na primeira: seis painéis dizendo que o `dicionario.csv` não
existe não ensinam nada que o primeiro não tenha ensinado.

**Um registro nome → módulo, com import preguiçoso.** O `REGISTRO` é o que faz a
sétima análise custar uma linha aqui. Preguiçoso porque importar este módulo não pode
trazer o `pandas`: a CLI o evita no topo de propósito, e o `listar` roda várias vezes
por dia.

### O que ele não faz

**Não gera o relatório.** Entre rodar as análises e montar o documento há uma leitura
sua — e a simulação não teria como mostrar um relatório montado sobre rodadas que
ainda não foram escritas.

**Não desfaz as análises que já escreveu quando uma falha no meio.** A que falhou se
desfaz sozinha, como no comando dela; as anteriores são rodadas completas, cada uma
coerente consigo mesma, e ficam. O `historico.md` ganha a linha que diz onde o lote
parou, e a mesma frase vai presa ao erro, para o terminal dizer o que o disco diz.

### `CHAVE_DA_LISTA`

*linha 94*

> A chave da ficha. É a mesma que o `ficha.Ficha.analises` lê e que o relatório usa
> para ordenar as seções — o lote só passou a obedecê-la.

### O registro

### `class Analise`

*linha 103*

Uma análise que o lote sabe rodar.

O nome é um só para quatro coisas — a lista `analises:`, o bloco da ficha, a
pasta em `3. Análises/` e o campo `analise` do manifesto — e é dele que saem os
nomes do resto: o módulo `<nome>.py`, as funções `preparar_<nome>` e
`executar_<nome>`, e a classe de erro `<Nome>Error`. A convenção existe desde a
normalidade, e o teste do registro é o que impede uma análise nova de quebrá-la
em silêncio.

O título é o do painel, com acento — "Associação" —, o mesmo que o comando da
análise usa quando ela recusa.

- *linha 120* — `desenha: bool` — o `preparar_*` dela aceita `com_graficos`

#### `def modulo(self)`

*linha 123*

*linha 124*

> Aqui, e não no topo do arquivo: é o import preguiçoso da terceira regra.
> O módulo da análise traz o `pandas` e o `scipy`, e só quem roda paga.

#### `def erro(self)`

*linha 129*

A classe que a análise levanta quando recusa: `CorrelacaoError`.

#### `def erros_do_projeto(self)`

*linha 134*

As recusas da análise que valem para todas: o dicionário ausente, e o que não
descreve o banco. As seis análises obedecem ao mesmo dicionário pela mesma
função, `descritiva.conferir_dicionario`, e a recusa de uma é a de todas.

#### `def preparar(self, raiz, *, aba, conferir, com_graficos, agora)`

*linha 143*

Chama o `preparar_*` da análise com os argumentos que o comando dela passaria.

O `com_graficos` só vai para quem desenha: o `preparar_cruzamento` não o
aceita, e um argumento a mais seria um `TypeError` em vez de um plano.

#### `def executar(self, plano)`

*linha 162*

### `REGISTRO`

*linha 166*

> Na ordem padrão do relatório (`manifesto.ORDEM_PADRAO_DAS_ANALISES`), e há teste que
> exige as duas iguais: uma análise nova que entre num dos dois registros e não no
> outro roda sem ter lugar no documento, ou tem lugar no documento e não roda.

### Erros

### `class AnalisesError(RuntimeError)`

*linha 184*

Falha do lote, já traduzida para o usuário.

Erro próprio pelo mesmo motivo de todo módulo do pacote: a CLI captura esta
classe e transforma em painel; qualquer outra exceção é bug e sobe com o
traceback inteiro.

### `class ListaVaziaError(AnalisesError)`

*linha 194*

A lista `analises:` está vazia — como o `flatcap novo` a deixa em toda ficha.

### `class ListaMalEscritaError(AnalisesError)`

*linha 200*

A chave `analises:` não é uma lista de nomes.

Recusa em vez de ignorar, pelo motivo que a normalidade escreveu para a lista
dela: ignorar seria rodar como se a linha não estivesse lá — você escreveu, e não
valeu.

### `class AnaliseDesconhecidaError(AnalisesError)`

*linha 210*

A lista pede uma análise que o FlatCap não tem — quase sempre uma grafia.

### `class AnaliseRepetidaError(AnalisesError)`

*linha 216*

A lista pede a mesma análise duas vezes.

### `class DicionarioDoLoteError(AnalisesError)`

*linha 222*

O dicionário recusou a primeira análise, e recusaria todas.

### `class AnalisesRecusadasError(AnalisesError)`

*linha 228*

Uma ou mais análises da lista recusaram. Carrega todas as recusas.

Nada foi escrito: é a segunda regra, a de preparar tudo antes de escrever.

#### `def __init__(self, recusas, prontas)`

*linha 235*

#### `def resumo(self)`

*linha 242*

A frase que fecha a lista de recusas, no terminal e no `str` do erro.

### O plano

### `class Recusa`

*linha 272*

Uma análise da lista que recusou, com o erro dela.

#### `def nome(self)`

*linha 279*

#### `def titulo(self)`

*linha 283*

#### `def mensagem(self)`

*linha 287*

### `class Etapa`

*linha 292*

Uma análise da lista, preparada: o registro dela e o plano que o `preparar_*`
dela devolveu — o mesmo objeto que o comando dela mostraria e escreveria.

#### `def nome(self)`

*linha 302*

#### `def titulo(self)`

*linha 306*

#### `def conteudo(self)`

*linha 310*

O que a análise calculou — `plano.descritiva`, `plano.correlacao`… Todo plano
de análise guarda o resultado num atributo com o nome dela, e é ali que moram
a ficha, o banco e os avisos.

#### `def pasta(self)`

*linha 319*

#### `def arquivamento(self)`

*linha 323*

#### `def arquivos(self)`

*linha 327*

### `class PlanoAnalises`

*linha 332*

Tudo o que o `analisar` faria, decidido e ainda não escrito.

Imutável como os planos que ele carrega. Entre a simulação e a execução ninguém
troca uma etapa de lugar: a árvore do terminal é lida deste objeto, e a execução
percorre o mesmo.

*linha 346*

> As análises com bloco escrito na ficha e sem o nome na lista: ficam de fora
> deste lote, e o histórico diz isso.

#### `def nomes(self)`

*linha 352*

#### `def banco(self)`

*linha 356*

O banco que as análises leram — o da primeira etapa. Cada uma o abriu por
conta própria, e todas abriram a mesma versão vigente da ficha.

#### `def desenha(self)`

*linha 364*

Alguma análise do lote desenharia, se os gráficos estivessem ligados.

### `class Feita`

*linha 370*

Uma análise que a execução escreveu, e o que o `executar_*` dela devolveu.

#### `def nome(self)`

*linha 377*

#### `def arquivado(self)`

*linha 381*

#### `def avisos(self)`

*linha 385*

### `class ResultadoAnalises`

*linha 390*

O que a execução de fato escreveu.

### Casos de uso

### `def preparar_analises(raiz, aba, conferir, com_graficos, agora)`

*linha 400*

Lê a lista, prepara cada análise dela e monta o plano. Não escreve nada.

Cada análise recebe o que o comando dela receberia, e o mesmo relógio: as rodadas
do lote saem com a mesma hora no manifesto e no nome da pasta arquivada, e é
assim que se reconhece em `2. Versões antigas/` o que foi arquivado junto.

Args:

    raiz: a pasta do projeto (a que tem o `projeto.yaml`).
    aba: planilha do `.xlsx`, quando houver mais de uma — a mesma para todas.
    conferir: reler o `sha256` das versões e comparar com a ficha.
    com_graficos: desenhar os `.png` das análises que desenham.
    agora: relógio injetável, como em todo `preparar*`.

Raises:

    FichaError, BancoError, DicionarioError e `OSError`, que valem para todas as
    análises e param na primeira; os erros da lista (`ListaVaziaError`,
    `ListaMalEscritaError`, `AnaliseDesconhecidaError`,
    `AnaliseRepetidaError`); `DicionarioDoLoteError`; e
    `AnalisesRecusadasError`, com todas as recusas de uma vez.

*linha 447*

> Antes do `registro.erro`, porque são subclasses dele.

### `def executar_analises(plano, ao_escrever)`

*linha 474*

Escreve as análises do plano, uma por uma, na ordem da lista. Não decide nada.

Cada uma é escrita pelo `executar_*` dela, que arquiva a rodada anterior, escreve a
nova, anota o histórico — e se desfaz sozinha quando falha no meio. Por último, a
linha do lote no `historico.md`, que diz que as linhas de cima foram uma execução
só.

Args:

    plano: o que o `preparar_analises` devolveu.
    ao_escrever: chamado depois de cada análise escrita. É por onde a CLI mostra o
        andamento, uma análise por vez, em vez de ficar muda até o fim.

Uma falha no meio para o lote. A análise que falhou já se desfez; as anteriores
ficam; as seguintes não rodam. O `historico.md` ganha a linha que diz isso, e a
mesma frase vai presa ao erro como nota (`add_note`), que o erro continua subindo
como veio: `OSError` é falha de disco, e a CLI a transforma em painel; qualquer
outra exceção é bug e sobe com o traceback — e com a nota junto.

*linha 508*

> `BaseException`, e não só `Exception`: um Ctrl+C no meio do lote também
> merece a linha no histórico dizendo o que ficou escrito e o que não rodou.

*linha 512*

> Minúscula depois do travessão, como toda linha do histórico.

### A lista

### `def lista_da_ficha(raiz)`

*linha 534*

Os nomes da lista `analises:`, conferidos: todos conhecidos, nenhum repetido.

Lê o bloco cru pelo `ficha.bloco`, e não a `Ficha.analises`, de propósito. A
`Ficha` descarta em silêncio o que não reconhece, e para o relatório ela está
certa: lá a lista só ordena seções, e uma entrada malformada é um estrago pequeno
e local. Aqui a lista **dirige** — uma entrada que some em silêncio é uma análise
combinada na reunião que não roda, sem que ninguém fique sabendo. O que a `Ficha`
perdoa, o lote recusa, com a frase do conserto.

Raises:

    ListaVaziaError, ListaMalEscritaError, AnaliseDesconhecidaError,
    AnaliseRepetidaError, FichaError

*linha 551*

> `analises:` sem nada, e a chave ausente, chegam como `None`; `analises: []`,
> como a lista vazia. Os três são a lista vazia.

- *linha 566* — `if item is None:` — `- ` sem nada: a `Ficha` também o pula

### `def _blocos_escritos(raiz)`

*linha 587*

As análises do registro que têm bloco escrito na ficha — na ordem do registro.

Escrito é não vazio: `cruzamento: []` é a chave sem par nenhum, e a análise dela
recusaria. A descritiva não tem bloco; entra aqui só se alguém escrever um.

### `def _rodadas_no_disco(raiz)`

*linha 597*

As rodadas vigentes em `3. Análises/`: pasta com `manifesto.json` dentro.

Pelo nome da pasta, que é o nome da análise — o mesmo critério e a mesma
varredura do relatório, sem abrir manifesto nenhum.

### `def _avisos_fora_da_lista(nomes, escritos, no_disco)`

*linha 611*

O que a ficha e o disco têm de análise fora da lista.

Aviso, e não recusa: é a lista que manda, e uma análise pode ter ficado de fora
de propósito. Mas "ficou de fora" e "ninguém reparou que ela existia" são coisas
diferentes — é a mesma razão da lista `fora` de toda análise. E a rodada antiga no
disco pesa mais do que parece: o relatório a inclui depois das seções da lista,
com os números de quando ela rodou.

### As mensagens da lista

### `def _mensagem_de_lista_vazia(raiz)`

*linha 658*

### `def _mensagem_de_texto(texto)`

*linha 695*

*linha 696*

> Vírgula, ponto e vírgula ou espaço: nome de análise não tem nenhum dos três, e
> quem escreveu um texto no lugar da lista separou os nomes com algum deles.

### `def _mensagem_de_item(item, sozinho)`

*linha 710*

O item que não é um nome. Cada forma tem o engano provável que a produz.

*linha 724*

> O engano provável: os pares escritos dentro da lista, debaixo do nome.
> A resposta mostra o mesmo conteúdo no lugar dele.

### `def _itens_do_bloco(valor)`

*linha 752*

Os itens de um bloco como se escrevem na ficha: `[idade, imc]`, `sexo: [imc]`.

### `def _mensagem_de_desconhecidos(desconhecidos)`

*linha 776*

### `_TESTES`

*linha 800*

> Os nomes de teste que alguém escreve no lugar da análise que os roda. A análise é a
> pergunta, e o teste sai da regra de cada uma — é o desenho da comparação e da
> correlação, e a recusa ensina isso em vez de só dizer "não conheço".

### `def _sugestao(nome)`

*linha 826*

O conserto de um nome desconhecido, do mais certo para o mais provável.

Acento e maiúscula primeiro, porque são o engano mais comum de quem escreve em
português — `associação` é a palavra certa e o nome errado. Depois o nome de um
teste no lugar da análise que o roda. Por último a grafia parecida.

### `def _mensagem_de_repetidos(repetidos)`

*linha 851*

### O histórico

### `def _comando(plano)`

*linha 864*

### `def _acao_do_historico(plano)`

*linha 868*

A linha do lote, escrita depois das linhas das análises.

Cada análise escreve a sua, a mesma que o comando dela escreveria — é o que o
lote é. Esta diz que elas foram uma execução só, e o que ficou de fora.

### `def situacao_da_parada(plano, feitas, em_curso, erro)`

*linha 898*

Onde o lote parou, o que ficou escrito e o que não rodou — numa frase.

A mesma frase vai para o `historico.md` e presa ao erro, e é por isso que ela é
pública: a CLI a imprime no painel sem precisar recontar as etapas.

"Foi desfeita" só vale para exceção comum. Um Ctrl+C (`KeyboardInterrupt`) não
passa pelo desfazer do `executar_*` da análise, que pega `Exception`, e a pasta
dela pode ter ficado pela metade — e a frase diz isso em vez de prometer o que
não aconteceu.

*linha 920*

> Entre duas análises — no `ao_escrever` da CLI, que roda depois de cada uma.
> Nenhuma pasta ficou pela metade, e a frase diz isso.

### Texto

### `def _em_texto(nomes)`

*linha 971*

`["descritiva", "normalidade"]` → «`descritiva` e `normalidade`».

Sem artigo antes do nome, pelo motivo que o relatório escreveu na função dele:
`a descritiva` funciona, e `a cruzamento` não.

### `def _sem_acento(texto)`

*linha 984*

## `flatcap/metodologia.py`

`SPDX-FileCopyrightText: 2026 Matheus Fernandes` · `SPDX-License-Identifier: GPL-3.0-or-later`

*518 linhas.*

A metodologia — o parágrafo da primeira página que o cliente leva para o artigo.

O relatório abre com a finalidade e os objetivos, que vieram do REDCap. Este módulo
escreve o que vem logo depois: um subtítulo — "Metodologia Estatística (texto padrão)" —
e um parágrafo curto, no registro de uma seção de métodos, dizendo como os números do
documento foram produzidos — para o cliente copiar, ajustar e levar para o artigo.

### O parágrafo sai das rodadas, e não de um texto fixo

Um texto fixo diria "qui-quadrado ou exato de Fisher, Pearson, Spearman ou Kendall,
t, ANOVA, Mann-Whitney, Kruskal-Wallis…" em todo relatório, e a seção de métodos de
um artigo que cita um teste que não aparece em resultado nenhum é a primeira coisa que
o parecerista marca. Então cada análise com rodada em `3. Análises/` contribui com uma
frase, e a frase nomeia **só os testes que rodaram** — lidos do manifesto, onde cada
análise já escreve o teste de cada par, de cada item e de cada delineamento.

É a mesma régua do resto do relatório: **nada aqui abre o banco.** O que o parágrafo
afirma está no `manifesto.json` da rodada — o teste de cada linha (`detalhes`), o alfa
e a correção para comparações múltiplas (`regras`), a versão do Python (`ambiente`).
Rodar a análise de novo reescreve o manifesto, e o parágrafo acompanha sem ninguém
lembrar de editá-lo.

### O que se edita, e onde

A redação mora no bloco emoldurado logo abaixo, como o `TEXTO_PADRAO` do
`relatorio.py`: o subtítulo, a frase de cada análise, o nome de cada teste. Mudar uma
palavra é mudar uma string. O que muda de projeto para projeto — quais testes, a versão
do Python, o alfa — vem do manifesto e não se escreve à mão.

O subtítulo sai separado do parágrafo, no `Metodologia.titulo`, e não colado na frente
dele: é o `documento.py` quem o escreve no estilo de subtítulo do modelo (o
`FlatCap Subtitulo`, o mesmo da linha `matrícula - nome`), que se ajusta no Word.

### Os nomes dos testes são os do manifesto

Este módulo não importa as análises: elas trazem o `pandas` e o `scipy`, e o
`relatorio.py` — que importa este — tem um teste em subprocesso que falha se o
`pandas` for carregado. Os nomes que o manifesto grava (`t de Welch`,
`Kruskal-Wallis`, `Qui-quadrado com correção de Yates`) estão escritos aqui como
texto, e o `test_metodologia.py` confere que são, letra por letra, as constantes das
análises. Um teste novo que entre numa análise sem entrar aqui aparece nesse teste,
e não num artigo.

*No módulo, linha 65:*

> ─────────────────────────────────────────────────────────────────────────────
>  O TEXTO DA METODOLOGIA — é aqui que se escreve.
>
>  O parágrafo é a soma das frases das análises que têm rodada, na ordem da
>  `ORDEM` abaixo, mais a do nível de significância e a do Python. Cada frase
>  só nomeia o que rodou: os testes saem do manifesto, e os nomes deles, deste
>  bloco. Mudar a redação é mudar as strings; nada no resto do módulo depende do
>  que está escrito nelas.
>
>  Em `{}`, o que o manifesto preenche. Uma chave escrita errada aqui é um
>  `KeyError` no primeiro teste, e não um `{versao}` impresso no documento.
> ─────────────────────────────────────────────────────────────────────────────

### `TITULO`

*linha 78*

> O subtítulo acima do parágrafo, no estilo de subtítulo do documento. `""` tira o
> subtítulo, e o parágrafo vem logo depois dos objetivos.

### `ORDEM`

*linha 82*

> A ordem das frases é a de uma seção de métodos — descrever, cruzar, testar —, e não
> a das seções do relatório, que é a da lista `analises:` da ficha.

### `DESCRICAO`

*linha 93*

> A descritiva: como cada tipo do dicionário foi resumido. Com mais de um tipo, o
> primeiro vira o sujeito da frase e os outros vêm depois dele, elípticos: «As
> variáveis categóricas foram descritas por …, e as numéricas, por …». Cada tipo traz
> as duas formas — a de sujeito e a elíptica — e o como.

### `FISHER_PELA_REGRA`

*linha 119*

> Quando os dois rodaram, a frase diz quando foi um e quando foi o outro: a regra de
> Cochran, como o `associacao.py` a aplica.

### `POR_QUE`

*linha 137*

> Por que a regra escolheu cada um. Saem só quando mais de um método rodou e a ficha
> não escreveu nenhum: com um método só não há escolha a explicar, e com o método
> escrito na ficha a escolha não foi da regra.

### `DELINEAMENTOS`

*linha 147*

> A comparação: o que se comparou, e com quais testes. As chaves de dentro são os
> nomes que o manifesto grava; os valores, como eles se escrevem na frase.

### `FRASE_REGRA_DA_COMPARACAO`

*linha 177*

> Sai quando a regra escolheu algum teste. Com algum escrito na ficha, a frase abre
> com a exceção, porque ali a escolha não foi da regra.

### `FRASE_PROGRAMAS`

*linha 188*

> A última frase. `{versao}` é o `VERSAO` com a versão do Python das rodadas — o
> `VERSOES`, quando elas rodaram em Pythons diferentes —, e some quando o manifesto
> não registra o Python.

*No módulo, linha 195:*

> ─────────────────────────────────────────────────────────────────────────────

### `_TESTAM`

*linha 197*

> As análises que testam hipótese, e por isso pedem a frase do nível de significância.

### `_ALFA_PADRAO`

*linha 200*

> O alfa de quem não o registra: a associação só relata o p. É o das outras análises.

### `class Metodologia`

*linha 209*

O subtítulo, o parágrafo, e o que ficou sem frase.

`paragrafos` é o que vai para a primeira página — um parágrafo, ou nenhum —, e
`titulo` o subtítulo que vem acima dele, vazio quando não há parágrafo. `sem_frase`
são as análises com rodada que não deram frase porque o manifesto delas não diz o que
rodou: um aviso de terminal, e não um texto inventado no documento.

#### `def texto(self)`

*linha 224*

### `def montar_metodologia(manifestos)`

*linha 228*

O parágrafo de metodologia das rodadas, na ordem de uma seção de métodos.

Recebe os manifestos — e não o banco, nem a ficha: o que o parágrafo afirma é o que
as rodadas registraram. Uma análise fora da `ORDEM` (uma que venha depois desta
versão) não quebra nada: ela fica sem frase e aparece em `sem_frase`.

*linha 258*

> O nível de significância só quando alguma frase nomeou um teste: uma comparação
> em que toda linha saiu "não testado" não tem p a ler contra ele.

### As frases

### `def _descritiva(manifesto)`

*linha 273*

### `def _cruzamento(manifesto)`

*linha 287*

### `def _associacao(manifesto)`

*linha 291*

### `def _normalidade(manifesto)`

*linha 307*

### `def _correlacao(manifesto)`

*linha 314*

*linha 323*

> «pelo coeficiente de Pearson ou, quando …, pelo de Spearman»: o primeiro é o da
> regra quando nada a desvia; os outros vêm com o porquê, e sem repetir o nome.

### `def _comparacao(manifesto)`

*linha 338*

*linha 356*

> O verbo concorda com os testes do primeiro delineamento, que é o sujeito dele; nos
> outros ele fica subentendido: «usou-se o t para uma amostra; entre dois grupos, …».

### `def _significancia(manifestos)`

*linha 389*

### `def _programas(manifestos)`

*linha 406*

"As análises foram feitas usando a linguagem Python versão 3.11."

A versão vem do `ambiente` de cada rodada, sem o último número: o 3.11.15 de uma
máquina e o 3.11.9 de outra são o mesmo Python para quem lê o artigo.

### Miúdos

### `def _detalhes(manifesto)`

*linha 433*

Os `detalhes` do item da rodada. As análises que testam escrevem um item só, com
todos os pares, linhas e delineamentos dentro dele.

### `def _linhas(manifesto, chave)`

*linha 444*

### `def _testados(manifesto)`

*linha 451*

Quantos testes de hipótese a rodada fez — para a frase das comparações múltiplas.

A normalidade não conta: o Shapiro-Wilk ali é pressuposto, e não resultado.

### `def _nada_testado(manifesto)`

*linha 466*

A rodada não deu frase porque não testou nada — e o manifesto diz isso.

É o caso da comparação em que toda linha saiu "não testado": a tabela está no
documento com o motivo, e o parágrafo não tem teste a nomear. Diferente de um
manifesto que não registra o que rodou, que vira aviso.

### `def _sem_repetir_teste(testes)`

*linha 478*

«o teste t de Welch e o de Mann-Whitney»: o segundo «teste» fica subentendido.

### `def _maiuscula(texto)`

*linha 489*

### `def _lista(itens)`

*linha 493*

`["a"]` → «a»; `["a", "b", "c"]` → «a, b e c».

### `def _numero(valor)`

*linha 501*

5.0 → «5»; 2.5 → «2,5». O alfa em percentual, sem zero sobrando.

### `def _chave_de_versao(versao)`

*linha 506*

## `flatcap/relatorio.py`

`SPDX-FileCopyrightText: 2026 Matheus Fernandes` · `SPDX-License-Identifier: GPL-3.0-or-later`

*1564 linhas.*

O relatório — o passo final do fluxo, e o que a Fase 6 automatiza.

Este módulo **monta o conteúdo** do documento e não escreve `.docx` nenhum. Quem
escreve é o `documento.py`, que recebe um `Relatorio` pronto e não decide mais
nada. É a mesma divisão da Fase 5 entre `descritiva.py` e `graficos.py`, pelo
mesmo motivo: se o gerador do documento recalculasse qualquer coisa, bastaria uma
diferença de arredondamento para o `.docx` dizer 37 e o `.csv` ao lado dizer 38 —
e ninguém confere documento contra planilha.

Aqui a regra é ainda mais forte, porque é o que sustenta a decisão de arquitetura
nº 3 do roteiro:

    **O relatório não abre o banco.** Nunca.

Ele lê o `manifesto.json` e os `.csv` que a Fase 5 escreveu, e é só isso. Não
importa o `pandas`, não importa o `matplotlib`, não recalcula uma média sequer.
Um número que aparece no documento é, byte a byte, o número que está no arquivo
que você pode abrir no Excel e conferir. Se o relatório recalculasse, existiriam
duas fontes para o mesmo 37% — e o dia em que elas discordassem seria o dia em que
o cliente perguntaria.

A consequência prática aparece no relógio: `flatcap relatorio` parte em ~0,1 s,
porque nenhuma das bibliotecas caras entra. Foi para manter isso que
`versao_vigente` desceu para o `ficha.py` e `PASTA_DESCRITIVA` para o
`projeto.py` — as duas moravam em módulos que importam o `pandas` e são, as duas,
perguntas que não precisam dele.

### O que este módulo decide

**De quais rodadas o documento fala.** De **todas** as que estiverem em
`3. Análises/*/` com um `manifesto.json` dentro. Não há nome de pasta fixo no
código: a descritiva, a normalidade e a análise que vier depois entram pelo
mesmo caminho, e o comando que a escreveu não precisa dizer nada a este módulo.
Uma rodada arquivada em `2. Versões antigas/` continua legível pelo
`manifesto.ler`, mas não é o que este comando monta: o relatório é o das
rodadas de agora.

Foi este o buraco que a Fase 7 abriu e que a 1.3.1 fecha. O `flatcap
normalidade` escrevia `normalidade.csv` e os `qq_*.png` no disco, o relatório
lia uma pasta de nome fixo, e nada disso chegava ao `.docx` — sem erro, sem
aviso, com o comando saindo com código 0 nas duas pontas.

**Em que ordem.** Na da lista `analises:` do `projeto.yaml`, que é o que foi
combinado na reunião — a ficha promete isso desde a Fase 2 e ninguém lia. O que
não estiver na lista entra depois, na `ORDEM_PADRAO_DAS_ANALISES` do
`manifesto.py`, e o que não estiver em nenhuma das duas entra no fim, em ordem
alfabética. Análise escrita na ficha e sem rodada no disco não é erro: vira um
aviso no terminal, porque quase sempre é a análise que você combinou e ainda
não rodou.

**Se elas ainda descrevem o que está na pasta.** Quatro conferências, e nenhuma
delas recusa o comando — a decisão da fase foi **gerar com o aviso dentro do
documento**:

    * a versão vigente do banco é outra desde a rodada;
    * o arquivo do banco foi alterado no disco depois de registrado;
    * o `dicionario.csv` mudou depois da rodada (variável nova, tipo trocado,
      rótulo reescrito, faixas diferentes);
    * um artefato listado em algum manifesto não está mais na pasta.

Cada uma vira um `Alerta`, e o `Alerta` viaja para dentro do `.docx`, logo abaixo
da identificação. Um aviso que fica só no terminal é um aviso que ninguém lê
depois de anexar o documento ao e-mail.

**Que o projeto fica pronto.** Escrito o documento, o `status:` da ficha passa para
`pronto` — é o que o `flatcap status` mostra, e o que tira dele o ATRASADO. É a
única linha da ficha que este módulo escreve, e a simulação diz que vai escrevê-la.
O documento vem primeiro: um status que não se escreve vira aviso, e não desfaz o
relatório.

**Como cada tabela vira tabela.** Os `.csv` da Fase 5 já trazem os números
formatados em português e um cabeçalho de comentário com o denominador. A leitura
aqui é fiel: separa os comentários das linhas de dados e não converte nada — o
texto que está na célula do `.csv` é o texto que vai para a célula do Word.

### O que sai na primeira página

Título, subtítulo com `matrícula - nome`, os alertas quando houver, a
**abertura** — três pedaços que `montar_abertura` junta, nesta ordem:

    1. o `TEXTO_PADRAO`, os parágrafos fixos que abrem todo relatório de todo
       projeto, definidos logo abaixo em um bloco só para serem reescritos sem
       se procurar código;
    2. a **finalidade** do estudo;
    3. os **objetivos**, geral e específicos —

e, fechando a página, a **metodologia**: o subtítulo "Metodologia Estatística
(texto padrão)" e um parágrafo para o cliente levar para o artigo.

Os dois do meio vêm da ficha, que os recebeu do formulário do REDCap (`fin` e
`obj1`) quando o `flatcap novo` criou a pasta — e que você pode corrigir à mão,
porque o `projeto.yaml` é seu.

A metodologia vem das rodadas, pelo `metodologia.py`: cada análise com rodada dá
uma frase que nomeia só os testes que rodaram, lidos do manifesto, e a versão do
Python fecha o parágrafo. Também não abre o banco — o que ela afirma é o que os
manifestos registraram. Viaja em dois campos próprios do `Relatorio`, e não no
`texto`, porque o subtítulo dela é um título, e o `documento.py` precisa saber
disso para escrevê-lo no estilo de subtítulo.

Campo da ficha em branco não encolhe a página em silêncio: vira um marcador
visível **e** um `Alerta` de código `texto_ausente`. Nada disso fere a regra da
casa: ler a ficha é ler YAML, não é abrir o banco.

### O que este módulo deliberadamente não faz

Não escreve prosa sobre os números. Não monta uma "Tabela 1" consolidada. Não
escreve apêndice técnico. As três foram decisões suas, e as três continuam a um
argumento de distância — o `Relatorio` já carrega tudo o que elas precisariam.

E não imprime mais a tabela de identificação nem os rodapés de denominador das
tabelas: as duas saíram na revisão de formatação, e o que elas diziam sobre a
procedência ficou nos metadados do arquivo (`documento._propriedades`) e no
`manifesto.json` da rodada.

*No módulo, linha 169:*

> `ARQUIVO_TEMPLATE` vem do `projeto.py`, e não mais escrito aqui uma segunda
> vez. A duplicação existia porque importar o `documento.py` no topo traria o
> `python-docx` junto, e a simulação deste comando não escreve documento nenhum;
> a constante desceu para o dono do desenho da pasta, que é o mesmo caminho que
> `versao_vigente` e `PASTA_DESCRITIVA` já tinham feito. O `documento.py`
> reexporta o nome, então quem o importava de lá não mudou.

*No módulo, linha 177:*

> ─────────────────────────────────────────────────────────────────────────────
>  O TEXTO FIXO DA PRIMEIRA PÁGINA — é aqui que se escreve.
>
>  Uma linha da tupla, um parágrafo do documento, na ordem em que estão. É a
>  parte que não muda de cliente para cliente, e ela abre a página: a finalidade
>  e os objetivos, que são deste projeto, vêm logo depois.
>
>  `()` é o estado de hoje: ainda não escrito. A primeira página continua saindo
>  — com a finalidade e os objetivos —, só ainda não tem a parte institucional.
>  Escrever é acrescentar strings aqui, e nada mais: nada no código sabe o que
>  está escrito, e a estrutura do documento não muda quando o texto crescer,
>  encolher ou ganhar parágrafos.
>
>  O que **não** se faz é deixar um parágrafo de mentira guardando o lugar. Um
>  `xxxxx` ou um `[a definir]` esquecido aqui não é feio: é um defeito que
>  atravessa a conferência e chega impresso na mão de um professor de medicina.
> ─────────────────────────────────────────────────────────────────────────────

### `_NOTA_REDUNDANTE`

*linha 197*

> A nota de comentário que todo `.csv` da Fase 5 traz na segunda linha. Ela é
> descartada na leitura porque o título da seção já diz de qual variável se trata,
> e repetir "variável: escolaridade" embaixo de uma tabela chamada "Escolaridade"
> é ruído em um documento que vai para o cliente.

### `class RelatorioError(RuntimeError)`

*linha 206*

Falha ao montar o relatório, já traduzida para o usuário.

Erro próprio pelo mesmo motivo de `ConfigError`, `RedcapError`, `ProjetoError`,
`FichaError`, `DadosError`, `BancoError`, `DicionarioError`, `DescritivaError`
e `ManifestoError`: a CLI captura esta classe e transforma em painel. Qualquer
outra exceção é bug de verdade e deve subir com o traceback inteiro.

### `class AnaliseAusenteError(RelatorioError)`

*linha 217*

O projeto não tem nenhuma rodada de análise para relatar.

É a única recusa desta fase, e ela não é uma escolha entre gerar e não gerar:
sem manifesto nenhum não há o que montar. Todas as outras divergências viram
aviso dentro do documento.

Chamava-se `DescritivaAusenteError` quando a descritiva era a única análise
que existia. O nome antigo continua apontando para esta classe, logo abaixo:
ele está em `except` de quem chama, e um `raise` que nenhum `except` pega é
um traceback na cara do usuário.

### `class TabelaIlegivelError(RelatorioError)`

*linha 235*

Um `.csv` da rodada existe e não dá para interpretar.

### `class ModeloAusenteError(RelatorioError)`

*linha 241*

O `template.docx` indicado em `--template` não existe.

### `class Alerta`

*linha 248*

Uma divergência entre a rodada e o que está na pasta hoje.

Vai para o terminal **e** para dentro do documento. A duplicação é o ponto:
o terminal você vê agora, o documento é o que sobra depois de o arquivo ser
anexado a um e-mail e aberto por outra pessoa em outro dia.

### `class TabelaLida`

*linha 263*

Um `.csv` da descritiva, separado em cabeçalho de comentário e dados.

Os valores são texto e continuam texto. Converter `28,7` para `0.287` e
formatar de novo na hora de escrever seria reintroduzir, no último passo do
fluxo, exatamente o arredondamento que a Fase 5 já resolveu.

#### `def largura(self)`

*linha 280*

#### `def total(self)`

*linha 284*

### `class Figura`

*linha 289*

Um `.png` da descritiva, com o caminho já conferido.

### `class Secao`

*linha 301*

Uma variável no documento: o que ela mostra, na ordem em que mostra.

A ordem das seções é a do manifesto, que é a do dicionário, que é a das
colunas do banco. Reordenar o `dicionario.csv` reordena o documento, sem
tocar em código — é a decisão da Fase 5 aparecendo aqui.

#### `def preenchidos(self)`

*linha 319*

### `class Rodada`

*linha 324*

Uma rodada de análise encontrada em `3. Análises/`, já lida.

O nome vem do campo `analise` do manifesto, e não do nome da pasta: nome de
pasta é o que o usuário renomeia, e é ele que teria de bater com a lista
`analises:` da ficha para a ordem do documento funcionar. A pasta entra só
como o lugar onde os artefatos moram — e como o nome que sobra quando um
manifesto antigo não declara a análise dele.

### `class ForaDoRelatorio`

*linha 342*

Uma variável do dicionário que não gerou nada, e por quê.

Não entra no `.docx` — é diagnóstico seu, não conteúdo do cliente —, mas
aparece no terminal pelo mesmo motivo da Fase 5: "não está no relatório" e
"ninguém reparou que ela existia" são coisas diferentes.

### `class Relatorio`

*linha 357*

O documento inteiro, decidido. É daqui que saem o `.docx` e o terminal.

*linha 363*

> O manifesto que responde pelo documento quando a pergunta é uma só — a
> data da rodada nas propriedades do `.docx`, o banco no cabeçalho do
> terminal. É o da descritiva quando ela existe; ver `_manifesto_principal`.
> As rodadas todas estão em `rodadas`.

*linha 371*

> A metodologia da primeira página: os parágrafos e o subtítulo acima deles. Fora
> do `texto` porque o subtítulo é um título, e não texto corrido; vazios, a
> página fecha nos objetivos, como antes da 1.16.0.

*linha 379*

> Sem `type: ignore`: o campo tem default e o default é `None`, então o tipo
> é `datetime | None`. Declarar `datetime` e atribuir `None` era pedir ao
> verificador para não olhar exatamente a linha em que ele estava certo.

#### `def raiz(self)`

*linha 386*

#### `def analises(self)`

*linha 390*

As análises que entraram no documento, na ordem em que entraram.

#### `def subtitulo(self)`

*linha 397*

`00742 - José Antônio de Sá`, embaixo do título.

Monta com o mesmo separador do `nomes.py`, e não com o nome da pasta,
por dois motivos. O nome da pasta passou pela `sanitizar` — perdeu a
barra, o dois-pontos, o que o Windows não aceita — e o documento não tem
essa limitação; e a matrícula e o nome são campos da ficha, que é onde
eles são a informação, enquanto na pasta são um caminho.

Cliente sem nome (o cadastro incompleto que o `listar` marca em amarelo)
sai só com a matrícula, em vez de sair com um separador solto no fim.

#### `def tabelas(self)`

*linha 414*

#### `def figuras(self)`

*linha 418*

### `class PlanoRelatorio`

*linha 423*

Tudo o que o `relatorio` faria, decidido e ainda não escrito.

Imutável como os planos das outras fases, e pela mesma razão: entre a
simulação e a execução ninguém altera um caminho em trânsito. A árvore que
aparece no terminal é lida deste objeto.

*linha 436*

> A ficha passa para `pronto` depois do documento? Falso quando ela já está: um
> arquivo que não muda não é reescrito.

#### `def raiz(self)`

*linha 441*

#### `def secoes(self)`

*linha 445*

#### `def total_tabelas(self)`

*linha 449*

#### `def total_figuras(self)`

*linha 453*

### `class ResultadoRelatorio`

*linha 458*

O que a execução de fato escreveu.

- *linha 466* — `status_trocado: bool = False` — a ficha passou para `pronto` nesta execução

### Casos de uso

### `def preparar_relatorio(raiz, template, conferir, agora, titulo)`

*linha 472*

Lê as rodadas de análise da pasta e monta o documento inteiro. Não escreve nada.

Args:

    raiz: a pasta do projeto (a que tem o `projeto.yaml`).
    template: um `.docx` para herdar estilos, cabeçalho e rodapé. Sem isso, o
        `template.docx` do `FLATCAP_ROOT`, e sem ele os estilos padrão.
    conferir: reler o `sha256` do banco e comparar com a ficha. É a única
        leitura cara deste comando, e `--rapido` a desliga.
    agora: relógio injetável — sem ele os testes não teriam como comparar o
        nome do arquivo, que carrega a data.

Raises:

    FichaError: a ficha do projeto não abre.
    AnaliseAusenteError: não há rodada nenhuma para relatar.
    ManifestoInvalidoError: o `manifesto.json` não abre ou é de formato novo.
    DicionarioInvalidoError: o `dicionario.csv` que está lá não é interpretável.
    TabelaIlegivelError: um `.csv` da rodada não abre.
    ModeloAusenteError: o `--template` indicado não existe.

*linha 530*

> Análise combinada na reunião e ainda não rodada. Aviso de terminal, e não
> `Alerta`: quem precisa saber é você, agora, antes de enviar — e o que está
> escrito no documento continua verdadeiro sem ela. Pôr isto dentro do
> `.docx` seria contar ao cliente uma combinação que é sua com ele.

*linha 542*

> Por último de propósito: os quatro alertas acima falam da validade dos
> números, e este fala do acabamento do documento. Um alerta de dado errado
> não deve ficar abaixo de um alerta de texto por preencher.

*linha 549*

> A metodologia sai das rodadas, e não da ficha: o que ela afirma é o que os
> manifestos registraram. Análise com rodada e sem frase é aviso de terminal —
> o parágrafo sai sem ela, e quem precisa saber disso antes de enviar é você.

*linha 567*

> O texto entra no `Relatorio` como dado, e o `documento.py` não lê
> constante nenhuma. É o que mantém a divisão da fase — e é o que fez
> esta mudança caber em uma linha: o dia previsto na Fase 6, em que a
> primeira página passaria a vir do `projeto.yaml`, é este. A
> metodologia entra do mesmo jeito, como dado, em dois campos dela.

### `def executar_relatorio(plano)`

*linha 590*

Escreve o documento no disco. Não decide mais nada.

A ordem é a das outras fases: arquiva o relatório anterior **antes** de
escrever o novo, porque os dois têm o mesmo nome quando a rodada é do mesmo
dia — e escrever primeiro seria escrever por cima do que se queria guardar.

Uma falha no meio desfaz o que já foi feito, inclusive devolvendo o relatório
arquivado ao lugar. Sem isso, a versão anterior teria sumido em troca de nada.
É o mesmo cuidado do `executar_adicao` da Fase 3 e do `executar_descritiva`
da Fase 5.

Depois do documento, e antes do histórico, a ficha passa para `pronto` — e a
linha do histórico diz isso só quando a troca aconteceu. O que se desfaz inclui a
ficha: ela volta ao texto que tinha, letra por letra.

O `documento.py` entra aqui dentro, e não no topo do arquivo, pelo mesmo
motivo que o `matplotlib` entra dentro do `executar_descritiva`: a simulação
não desenha documento nenhum e não deve pagar pelo `python-docx`.

*linha 643*

> `Exception`, como no `executar_*` de cada análise, e não só `OSError` e
> `RelatorioError`: até a 1.13.0 um `.png` ilegível estourava o `python-docx`
> com uma exceção que não é nenhuma das duas, e o relatório anterior ficava em
> `2. Versões antigas/` sem o novo no lugar dele. O erro sobe do mesmo jeito.

### `def _marcar_pronto(raiz, avisos, desfazer)`

*linha 666*

Passa a ficha para `pronto`, depois de o documento estar no disco. Devolve se
passou.

O documento é o produto e o status é o recibo dele: um `projeto.yaml` que não se
deixa escrever — aberto noutro programa, a ficha que deixou de abrir entre a
simulação e a execução — vira aviso, com o que escrever à mão, e o relatório fica.
É a regra do somente-leitura do `flatcap novo`: perder a marca é aceitável,
perder o produto por causa dela não.

*linha 679*

> `newline=""` para o desfazer devolver o arquivo como estava, até o `\r\n` de
> uma ficha editada no Windows.

### Nome e lugar do arquivo

### `def nome_do_relatorio(matricula, quando)`

*linha 698*

Monta `Relatorio_00742_2026-09-20.docx`, como o roteiro pede.

A matrícula vem da ficha e passa pela mesma limpeza dos nomes de pasta: ela
é digitada por outra pessoa, em outro sistema, e o que vem de fora não monta
caminho.

### `def relatorios_na_pasta(raiz)`

*linha 711*

Os relatórios que já estão na raiz do projeto, em ordem.

O `.docx` mora na raiz da pasta do projeto, e não em uma `4. Relatórios/`. É
um desvio deliberado do apêndice A do roteiro, já registrado no `projeto.py`:
o relatório é o produto que se entrega, e ele fica onde a mão alcança
primeiro ao abrir a pasta.

- *linha 730* — `and not arquivo.name.startswith("~$")` — o lixo que o Word deixa aberto

### `def _arquivamentos(raiz)`

*linha 735*

O que sai da raiz e vai para `2. Versões antigas/`.

**Todos** os relatórios anteriores, não só o de hoje. A raiz do projeto fica
com um relatório só — o vigente —, que é a mesma regra que `1. Dados
originais/` segue para o banco. Uma pasta com três `.docx` de datas
diferentes é uma pasta em que alguém vai anexar o errado no e-mail.

Duas rodadas no mesmo dia colidiriam no destino, porque o nome carrega a data
e não a hora. O desempate é o sufixo numérico da Fase 5.

Não recebe o destino, e é por isso que ele não aparece aqui: o relatório que
está para ser escrito ou ainda não existe no disco, ou tem o nome de um dos
anteriores — e aí já está na lista, achado pela varredura. A linha
`_ = destino` que morava no fim desta função dizia isso e não fazia nada;
dizer está na docstring, que é onde se diz.

### `def localizar_template(raiz, template)`

*linha 768*

Qual `.docx` empresta os estilos, e nesta ordem.

1. o `--template` que você passou;
2. o `template.docx` da **pasta do projeto**, para o trabalho que exige um
   modelo próprio;
3. o `template.docx` da **pasta do cliente**, que vale para todos os
   projetos dele — o degrau novo da 1.1.0;
4. o `template.docx` do `FLATCAP_ROOT`, que é onde o modelo institucional
   mora — fora do repositório, como todo o resto que não é código;
5. nenhum: o documento sai com os estilos padrão do `documento.py`.

**Esta função tinha um degrau a menos e teria quebrado em silêncio.** Até a
1.0.0 `raiz.parent` era o `FLATCAP_ROOT`; com a pasta do projeto um nível
abaixo, `raiz.parent` passou a ser a pasta do cliente, e o modelo
institucional deixaria de ser encontrado — sem erro, sem aviso, só com todo
relatório saindo de repente sem o logotipo. O degrau que se ganha no meio é
a parte boa do acidente: um cliente com identidade visual própria agora tem
onde guardar o modelo dele.

O modelo mora fora do repositório de propósito. Ele carrega logotipo e
identidade visual da instituição, muda sem pedir licença a ninguém, e é
binário — três razões pelas quais ele não é código.

Pública desde a 1.15.0, com o apelido privado de antes: o relatório da amostra
procura o modelo pelos mesmos degraus, e dois caminhos de busca é como um dos
dois relatórios sai sem o logotipo.

*linha 808*

> O terceiro degrau só existe quando há um terceiro nível acima: numa raiz
> de teste montada direto em `tmp_path`, `parent.parent` sairia da árvore.

### A rodada

### `def _rodadas(raiz, ficha)`

*linha 825*

As rodadas de `3. Análises/`, na ordem do documento.

Devolve as rodadas, os artefatos que os manifestos prometem e não estão no
disco, e os nomes que a ficha pede e que não têm rodada nenhuma.

**Varre, e não procura nome fixo.** É a diferença que faz a normalidade
entrar no documento sem uma linha deste módulo saber que ela existe — e é o
que a próxima análise vai encontrar pronto. Pasta sem `manifesto.json`
dentro é ignorada em silêncio: `3. Análises/` é uma pasta do usuário, e uma
subpasta de rascunho dele não é uma rodada mal formada.

Raises:

    AnaliseAusenteError: não há rodada nenhuma.
    ManifestoInvalidoError: uma rodada tem manifesto e ele não abre.

### `def _ordenar(rodadas, analises_da_ficha)`

*linha 873*

A ordem das seções do documento: a ficha primeiro, o padrão depois.

É o que a lista `analises:` sempre prometeu e nunca dirigiu. O cabeçalho da
ficha diz literalmente *«o que foi combinado na reunião»*, e o que foi
combinado tem uma ordem — a descritiva antes dos pressupostos em um
relatório, o contrário em outro, conforme o que o cliente vai ler primeiro.
Sem isto a ordem era a do `sorted` do sistema de arquivos, que é alfabética
por acidente.

Três degraus, e o terceiro é o que torna a saída determinística: a posição
na lista da ficha, a posição na `ORDEM_PADRAO_DAS_ANALISES`, e o nome. Nome
escrito na ficha e sem rodada no disco não entra aqui — ele vira aviso, em
`_rodadas`.

### `def _manifesto_principal(rodadas)`

*linha 907*

O manifesto que responde pelo documento quando a pergunta é uma só.

As propriedades do `.docx` e o cabeçalho do terminal precisam de **um** banco
e de **uma** data de rodada, e com mais de uma análise na pasta isso deixou
de ser automático. A escolha é a descritiva: é ela que descreve o banco
inteiro, e é a data dela que responde «de quando são estes números?» para
quem abre o arquivo no Windows sem abri-lo no Word. Sem descritiva, a
primeira rodada da ordem — que é a que o documento apresenta primeiro.

### `def _variaveis_de_fora(rodadas)`

*linha 924*

As variáveis do dicionário que **nenhuma** rodada descreveu.

A conta é entre rodadas, e precisa ser: a lista `fora` da normalidade tem
toda categórica do banco — «a normalidade só se pergunta de numérica» —, e
imprimir isso no terminal diria que `sexo` ficou fora do relatório logo
acima da seção `Sexo` do próprio relatório. Fora do documento é quem não
aparece em rodada nenhuma.

### `def _mensagem_sem_rodada(raiz)`

*linha 951*

### `def _analises_em_texto(analises)`

*linha 962*

`["descritiva", "normalidade"]` → «`descritiva` e `normalidade`».

Sem artigo antes do nome de propósito: `a descritiva` e `a normalidade`
funcionam, e `a teste t` não. O nome da análise vem do manifesto, e o
manifesto é escrito por quem escreveu a análise.

### `def _secoes(pasta, manifesto)`

*linha 976*

Uma seção por variável do manifesto, na ordem dele.

Artefato que sumiu da pasta não interrompe nada: ele é anotado e o documento
sai sem aquela tabela ou figura, com o alerta dizendo qual. O contrário —
recusar por causa de um `.png` apagado — seria transformar um acidente
reversível em um comando que não roda.

### `def ler_tabela(caminho, especie, titulo)`

*linha 1024*

Lê um `.csv` de uma análise sem o `pandas` e sem converter valor nenhum.

O formato é o que a Fase 5 escreveu primeiro, e o `manifesto.Tabela` de toda
análise escreve desde a Fase 7: BOM, algumas linhas de comentário com o
título e os denominadores, e a tabela separada por `;`. As linhas de
comentário viram `notas` — elas carregam os dois denominadores da tabela de
frequência, que é a resposta do roteiro para "quando o cliente lê 45%, ele
precisa saber se o denominador incluiu os casos sem resposta".

Sem `pandas` de propósito. Não é economia de dependência — o `pandas` está
instalado —, é economia de conversão: `pd.read_csv` leria `28,7` como texto
ou como número dependendo do `decimal=`, e das duas uma sairia diferente do
que está no arquivo. Aqui o texto atravessa intacto.

### `def tabela_do_texto(texto, especie, titulo, caminho)`

*linha 1054*

O miolo do `ler_tabela`: o texto de um `.csv` de análise, já lido, virando tabela.

Separado desde a 1.15.0, para a amostragem: ela monta o relatório da amostra a
partir do texto do `tamanho.csv` **antes** de ele ir ao disco — o `preparar` decide
o documento inteiro, e o `executar` só escreve. É o mesmo texto que vai para o
arquivo, lido pela mesma função que o lê do disco, e por isso o documento e a
tabela não têm como dizer números diferentes.

O `caminho` só dá o nome ao arquivo e às mensagens; nada é lido dele. O BOM que o
`manifesto.Tabela.texto` escreve é tirado aqui, como o `utf-8-sig` o tira na leitura.

*linha 1072*

> Os comentários são só os do começo, como no `dicionario.csv`: depois do
> cabeçalho das colunas, uma linha começada por `#` é uma categoria — o `#N/D`
> que o Excel deixa numa célula com erro de fórmula. Até a 1.13.0 ela saía da
> tabela do documento e virava nota, e o `Total` deixava de somar.

*linha 1094*

> O primeiro comentário é o título do arquivo; o título do manifesto é o
> mesmo texto e tem precedência, para que o documento e o índice não possam
> divergir. O resto vira nota, menos a linha `variável:`.

### A primeira página

### `_MARCADOR`

*linha 1118*

> O que ocupa o lugar de um campo que veio em branco.
>
> Não é `[NULL]`, e a escolha tem três razões, em ordem de importância. O risco
> real não é o marcador ser feio: é ele **escapar** para a entrega, e aí ele
> precisa ser legível para quem abrir o documento sem nunca ter ouvido falar do
> FlatCap. `[NULL]` é vocabulário de banco de dados. E as aspas angulares fazem
> o que o colchete não faz: é impossível confundir isto com o texto do cliente.
>
> O marcador nunca vem sozinho — o `Alerta` de código `texto_ausente` sobe junto,
> e é ele a caixa amarela no alto da página. O marcador é para o seu olho na
> releitura; o alerta é o que sobrevive ao arquivo ser anexado a um e-mail.

### `def montar_abertura(ficha, texto_padrao)`

*linha 1135*

Os parágrafos da primeira página: o texto fixo, a finalidade, os objetivos.

A ordem é a da leitura. O parágrafo institucional enquadra, a finalidade diz
para que o estudo serve, e os objetivos dizem o que se quer saber — do geral
para o particular, que é como um cliente lê a própria primeira página.

Campo em branco não some: vira marcador. Uma seção que simplesmente encolhe é
uma falta em que ninguém repara, e é o mesmo argumento que a Fase 4 usou para
imprimir a codificação no `perfil.md` — a única forma de descobrir que a
escolha foi errada é vê-la escrita.

Recebe a `Ficha`, e não a `Config`: montar a primeira página é ler YAML, não
é falar com o REDCap. O teste em subprocesso que afirma que este módulo não
carrega `pandas` nem `matplotlib` continua valendo, e o `texto_padrao`
injetável existe para o teste poder afirmar a composição sem depender do que
estiver escrito na constante hoje.

### `def _paragrafos(texto)`

*linha 1167*

Cada quebra de linha do campo `notes` vira um parágrafo do documento.

Quebra de linha ali é intenção: numa caixa de texto do REDCap a linha quebra
sozinha ao chegar na borda, e só existe um `\n` onde a pessoa apertou Enter.
Linha em branco entre dois parágrafos é descartada — parágrafo vazio no Word
é um espaço que ninguém pediu e que reaparece na revisão como "sobrou uma
linha aqui".

### As conferências

### `def conferir_texto(ficha)`

*linha 1183*

Quais campos da primeira página vieram em branco.

É a quinta conferência da fase, e a única que não fala de dados: as outras
quatro perguntam se a rodada ainda descreve a pasta, esta pergunta se o
documento está pronto para ser enviado. Ela não recusa nada, pelo mesmo
motivo das outras — o documento sai, com o aviso dentro dele.

Pública desde a 1.15.0, com o apelido privado de antes: o relatório da amostra
abre com a mesma primeira página, e o campo em branco precisa do mesmo aviso lá.

### `def _conferir_banco(raiz, ficha, rodadas, conferir)`

*linha 1224*

As rodadas ainda descrevem a versão vigente do banco?

Duas perguntas diferentes, e vale separá-las porque o que fazer é diferente:

* **outra versão** — o cliente mandou o banco revisado e a descritiva não foi
  refeita. O documento fala de uma versão que não é mais a de trabalho.
* **arquivo alterado** — o mesmo arquivo foi aberto e salvo por cima depois
  de registrado. Aí nem a ficha descreve mais o que está no disco.

A comparação é de `sha256`, e o da rodada está no próprio manifesto. Não há
releitura do banco aqui: o `sha256` da versão vigente vem da ficha, e a
conferência contra o disco é a mesma `linha_do_tempo` da Fase 3 — porque duas
implementações da mesma conferência é como um comando diz "confere" enquanto
o outro diz "ALTERADO" sobre o mesmo arquivo.

Com mais de uma rodada na pasta, a conta é por **banco usado**, e não por
rodada: duas análises da mesma versão são um alerta só, e duas análises de
versões diferentes são dois — que é a informação que interessa, porque aí o
documento está misturando números de dois bancos e as análises que ele nomeia
são as que precisam ser refeitas.

- *linha 1290* — `except OSError:` — pragma: no cover - o disco já foi lido várias vezes até aqui

### `def _conferir_dicionario(raiz, rodadas)`

*linha 1328*

O `dicionario.csv` de hoje é o que dirigiu as rodadas?

É a divergência mais fácil de acontecer e a mais difícil de perceber: você
corrige um rótulo ou muda uma faixa depois de rodar a descritiva, gera o
documento, e ele sai com os títulos antigos e os cortes antigos — bonito, e
descrevendo uma decisão que você já revogou.

Quatro diferenças são procuradas: variável que entrou, variável que saiu,
tipo trocado e rótulo reescrito, mais as faixas, que o manifesto guarda em
`detalhes`. Um dicionário ilegível **não** interrompe o relatório: ele já
cumpriu o papel dele quando a rodada foi gerada, e recusar aqui seria travar
o documento por causa de um arquivo que o documento não usa.

#### `colunas_usadas`, e não `item.variavel`

É a troca que faz esta conferência sobreviver à segunda análise. O campo
`variavel` é singular e existe análise que não é de uma variável: a tabela de
normalidade fala de todas de uma vez e sai do manifesto com `variavel=""`.
Comparando por ele, o item da normalidade viraria a variável de nome vazio, e
todo relatório sairia com «`` saiu da descritiva depois da rodada» — em todo
projeto, para sempre. `colunas_usadas` responde a pergunta que se queria
fazer, «quais colunas do banco esta rodada tocou?», e responde igual para uma
seção de uma variável e para uma de doze.

#### Quem responde por «entrou no dicionário depois»

Só a descritiva, e a assimetria é deliberada. Ela é a análise que descreve
**todas** as variáveis analisáveis; a normalidade só olha as numéricas.
Perguntar a pergunta a todas as rodadas faria toda categórica do dicionário
ser dada como «entrou depois» em um projeto que só rodou a normalidade —
um alerta dentro do documento do cliente, sobre nada.

- *linha 1366* — `except Exception as erro:` — noqa: BLE001 - ver a justificativa acima

*linha 1388*

> Quais colunas do banco cada rodada tocou, e qual rodada tocou primeiro.

*linha 1394*

> Os itens que **são** uma variável. O tipo, o rótulo e as faixas só existem
> para eles: uma seção que fala de doze colunas não tem um tipo do
> dicionário para comparar, e a de normalidade se chama «Normalidade».

### `def _faixas_mudaram(faixas, detalhes)`

*linha 1469*

Compara os cortes do dicionário com os que a rodada usou.

O manifesto guarda `origem` (`dicionario` ou `quartis`) e os `cortes` já
arredondados. As três formas de divergir são: faixas preenchidas depois de a
rodada ter usado quartis, faixas apagadas, e cortes diferentes.

- *linha 1493* — `except ValueError:` — pragma: no cover - o dicionario.py já validou na leitura

### Mensagens

### `def _mensagem_ilegivel(caminho, erro)`

*linha 1507*

### `def _acao_do_historico(plano, status_trocado)`

*linha 1518*

## `flatcap/documento.py`

`SPDX-FileCopyrightText: 2026 Matheus Fernandes` · `SPDX-License-Identifier: GPL-3.0-or-later`

*1473 linhas.*

O `.docx` do relatório.

Este módulo **escreve e não decide**. Ele recebe um `Relatorio` já montado — as
tabelas lidas, as figuras localizadas, os alertas resolvidos — e o transforma em
documento. É a mesma divisão que a Fase 5 fez entre `descritiva.py` e
`graficos.py`, e a razão é a mesma: se o gerador do documento reabrisse um `.csv`
ou recalculasse um percentual, existiriam duas fontes para o mesmo número.

É também o único módulo do pacote que importa o `python-docx`, e por isso ele é
importado **de dentro** do `executar_relatorio`, e não no topo do `relatorio.py`.
A simulação não escreve documento nenhum e não deve pagar por uma biblioteca que
ela não usa. Mesma decisão que o `matplotlib` recebeu na Fase 5.

Não declara erro próprio, como o `graficos.py`: o que pode falhar aqui é escrita
em disco, que é `OSError`, e quem sabe o que fazer com ela é o
`executar_relatorio` — que desfaz o arquivamento e devolve o relatório anterior
ao lugar.

### O contrato com o `template.docx`

A separação template/código é o ponto central da fase no roteiro: *"formatação —
fonte, cores, logotipo, margens, estilos de tabela — vive no `template.docx` e é
ajustada no próprio Word, visualmente. O Python cuida só do conteúdo."*

Aqui isso é levado a sério de um jeito específico: **o modelo manda, e o código se
adapta ao que encontra.** Para cada peça do documento há uma fila de nomes de
estilo, e vence o primeiro que existir no modelo:

    peça       procura, nesta ordem                         se não achar nenhum
    ────────────────────────────────────────────────────────────────────────────
    título     FlatCap Titulo · Title                       negrito 20
    subtítulo  FlatCap Subtitulo · Subtitle                 13, cinza
    seção      FlatCap Secao · Heading 1                    negrito 14
    corpo      FlatCap Corpo · Normal                       o padrão do modelo
    legenda    FlatCap Legenda · Caption                    itálico 9, cinza
    tabela     FlatCap Tabela · Table Grid                  bordas escritas à mão

A fila existe porque o modelo institucional vem depois, e vem de fora. Um
`.docx` que a instituição já usa pode não ter o estilo `Table Grid` definido —
o Word só grava a definição dos estilos que o documento chegou a usar —, e um
relatório de tabelas sem borda nenhuma é um relatório que ninguém aceita. Então
o último degrau de cada fila é formatação escrita à mão, e o comando nunca
quebra por causa de um estilo ausente.

Criar os estilos `FlatCap *` no modelo é o que dá controle total: enquanto eles
não existirem, o documento usa os estilos nativos do Word e fica parecido com
qualquer outro; criados, eles mandam. `flatcap template` escreve um modelo com
todos eles já definidos, para você abrir no Word e ajustar.

**O corpo do modelo é preservado, e o relatório entra depois dele.** É assim que
uma capa institucional continua sendo a capa: o que estiver escrito no
`template.docx` aparece antes do título do relatório. Parágrafos vazios no fim do
modelo são descartados, senão o documento começaria com uma página em branco.

### As decisões de apresentação

**Legenda acima da tabela e acima da figura.** É a convenção da ABNT, e é a única
que mantém tabela e figura com a mesma cara em um documento que tem as duas
alternadas. A numeração é contínua e separada — `Tabela 1`, `Tabela 2`,
`Figura 1` — porque é assim que se cita um número no corpo de um e-mail: "veja a
Tabela 3".

**A primeira página é título, subtítulo, alertas, o texto padrão e a
metodologia.** Nessa ordem: o alerta vem antes do texto de abertura porque ele é a
única coisa da página que pode fazer alguém parar de enviar o documento; e a
metodologia fecha a página, com o subtítulo dela no mesmo estilo da linha
`matrícula - nome`.

**A última linha da tabela sai em negrito quando é o `Total`.** Uma tabela de
frequência é lida de cima para baixo até o total; é a linha em que o olho para.

**A figura ocupa a largura útil da página, seja qual for o modelo.** A margem é
lida da seção do documento, e não fixada em centímetros: um modelo institucional
com margem de 3 cm receberia uma imagem estourando a mancha se o número fosse
fixo.

- *linha 98* — `if TYPE_CHECKING:` — só para as anotações: importar `relatorio` aqui criaria um ciclo

### `ESTILO_TITULO`

*linha 101*

> As filas de estilo. O primeiro nome de cada uma é o do FlatCap, que só existe
> se você o criou no modelo; o segundo é o nativo do Word, que existe em quase
> todo `.docx`; o terceiro degrau é a formatação à mão, mais abaixo.

*No módulo, linha 111:*

> `ARQUIVO_TEMPLATE` é importado do `projeto.py`, lá em cima, e reexportado por
> este módulo — é daqui que ele sempre foi importado. Ele estava escrito duas
> vezes: aqui e no `relatorio.py`, que não pode importar este módulo no topo sem
> trazer o `python-docx` para uma simulação que não escreve documento nenhum.
> Duas grafias do mesmo nome de arquivo é como um comando passa a procurar um
> modelo que o outro comando não grava.

### `ARQUIVO_DECISOES`

*linha 118*

> A folha de decisões que mora ao lado do modelo.
>
> Existe porque um `.docx` é binário: não aceita comentário, não entra no Git e
> não conta a ninguém por que está do jeito que está. O corpo do modelo também
> não serve para isso — ele é impresso em todo relatório. Então as razões moram
> em um arquivo de texto ao lado, que é onde a próxima pessoa vai olhar.

### `TINTA`

*linha 126*

> A mesma paleta do `graficos.py`, para que a figura e a página não briguem.

- *linha 130* — `FUNDO_AVISO = "FBEFC8"` — o amarelo do painel de aviso da CLI, em papel

- *linha 132* — `TINTA_LINHA = "0B0B0B"` — as réguas da tabela, na mesma tinta do texto

### `FUNDO_TOTAL`

*linha 134*

> O fundo da linha `Total`.
>
> Esta cor mora no código, e não no `template.docx`, e a exceção tem motivo. O
> Word sabe pintar a última linha de uma tabela — é a banda «Última linha» do
> estilo. Mas a última linha nem sempre é o `Total`: no resumo de uma numérica
> ela é `Q3`, e a banda pintaria o desvio-padrão de verde. O destaque depende do
> **conteúdo** da célula, e conteúdo é justamente o que o estilo não enxerga.
>
> O texto por cima é escrito em `TINTA`, e isso também precisa ser dito. Sem cor
> explícita o Word usa a cor «automática», que ele inverte para branco sobre
> fundo escuro — e branco sobre este verde dá contraste 3,4:1, abaixo dos 4,5:1
> que se pede para texto de corpo. Em preto o contraste é 6,2:1.

### `_REGUA_GROSSA`

*linha 148*

> As três linhas da tabela: topo, sob o cabeçalho, base. Nenhuma vertical.

- *linha 149* — `_REGUA_GROSSA = 12` — oitavos de ponto — topo e base

- *linha 150* — `_REGUA_FINA = 4` — sob o cabeçalho

### `FONTE`

*linha 159*

> A fonte do documento padrão. Escrita explicitamente, e não herdada do tema do
> `.docx`, porque o tema é o que muda quando o arquivo passa por outra versão do
> Word — e um relatório que sai com serifa numa máquina e sem serifa na outra é
> um relatório que parece defeituoso sem que nada esteja errado. Um modelo
> institucional manda no lugar disto: aqui só se decide o que ninguém decidiu.
>
> É a mesma do `graficos.FONTE`, e tem de continuar sendo: o texto do documento e
> os rótulos das figuras ficam a dois centímetros um do outro na mesma página.

### `CABECALHO_PADRAO`

*linha 169*

> O que vai escrito no cabeçalho do modelo padrão. Uma linha, discreta, no canto
> direito — é onde a identidade institucional entra sem custar uma página inteira.
> Quem tiver logotipo troca esta linha por ele, no Word.

### `_LINHAS_PARA_MANTER_JUNTA`

*linha 174*

> Até este tamanho, a tabela não se parte na quebra de página. Acima dele, ela
> se parte e o cabeçalho se repete — uma distribuição no tempo de dois anos tem
> 24 linhas, e forçá-la inteira para a página seguinte deixaria meia página em
> branco para não ganhar nada.

### `_FATIA_DO_ROTULO`

*linha 180*

> A largura da primeira coluna das tabelas, em fração da mancha. A primeira
> coluna é rótulo — `(abaixo da primeira faixa)`, `Ensino fundamental` — e as
> outras são número. Repartir a largura em partes iguais espremeria o texto e
> daria à coluna `n` um palmo de espaço vazio.

### `_EMU_POR_CM`

*linha 187*

> A repartição pelo conteúdo, das tabelas com mais de uma coluna de texto. São
> estimativas para Arial 9,5 — a fonte das tabelas —, com folga: um número que
> quebra no meio é pior do que uma coluna um pouco mais larga do que precisava.

- *linha 192* — `_RESPIRO_CM = 0.4` — as margens da célula, 0,12 de cada lado, e um fio de ar

- *linha 193* — `_MINIMO_NUMERICO_CM = 1.2` — para a coluna `n` não virar um fio

- *linha 194* — `_TEXTO_NATURAL = 40` — caracteres: acima disto, a coluna de texto aceita quebrar

### `_FOLGA_DA_PALAVRA`

*linha 196*

> Um caractere a mais para a palavra mais longa de uma coluna de texto. Os 0,19 cm
> são a média, e palavra com `m`, `w` ou maiúscula passa dela: `Spearman`, na coluna
> `método` da correlação, pedia 1,55 cm de texto e recebia 1,52 — e saía partida em
> `Spearma` e `n`. A folga vale só para o piso, que é a promessa de "palavra curta
> não quebra"; o resto da repartição continua na média.

### `def versao_do_python_docx()`

*linha 204*

A versão que escreveu o documento. Vai para o `doctor` e para o histórico.

### `class Estilos`

*linha 212*

Os estilos que este modelo oferece, já resolvidos.

`None` quer dizer "o modelo não tem nenhum dos nomes da fila" — e é aí que a
formatação à mão entra. Resolver tudo de uma vez, antes de escrever a
primeira linha, é o que impede o documento de sair com metade das legendas
em um estilo e metade em outro.

### Escrita

### `def escrever(relatorio, caminho, template)`

*linha 233*

Escreve o `.docx` do relatório. Devolve o caminho escrito.

Args:

    relatorio: o documento já decidido pelo `relatorio.py`.
    caminho: onde gravar.
    template: o `.docx` que empresta estilos, cabeçalho, rodapé e capa.
        Sem ele, o documento sai com os estilos padrão desta função.

*linha 273*

> A primeira página já tem conteúdo? É disso que depende a quebra antes da
> primeira seção, mais abaixo. O texto de abertura responde quase sempre; a
> metodologia e o alerta respondem no caso em que ele não existe, porque uma
> página com um parágrafo ou uma caixa amarela dentro não é uma página em
> branco. As duas funções são chamadas antes do `or`: as duas escrevem.

*linha 298*

> A primeira variável começa em página nova, para que a abertura fique
> sozinha na primeira. É `page_break_before` no título, e não um
> parágrafo de quebra atrás dele: um parágrafo a mais deixaria a marca
> dele no alto da página seguinte, empurrando o título para baixo, e
> sobraria no documento se um dia o texto de abertura sumisse.

### `def _abrir(template)`

*linha 318*

Abre o modelo, ou monta o documento padrão quando não há modelo.

Um modelo que não abre — arquivo corrompido, `.doc` antigo renomeado — não
vira exceção crua: o `python-docx` estoura com `PackageNotFoundError`, que
não diz nada a quem escolheu o arquivo. Vira `RelatorioError`, com o que
fazer.

- *linha 334* — `except Exception as erro:` — noqa: BLE001 - o docx estoura de várias formas

### `def _documento_padrao()`

*linha 346*

O documento de quem ainda não tem modelo: A4, margens de 2,5 cm, rodapé com o
número da página.

Deliberadamente sóbrio e sem identidade visual nenhuma. Ele não é o modelo
institucional nem quer ser: é o que faz o comando funcionar no primeiro dia,
antes de o `template.docx` existir.

É exatamente o que o `flatcap template` grava — inclusive os estilos
`FlatCap *`, que assim ganham a fila e mandam no documento padrão. Sem eles,
o relatório sem modelo herdaria o `Title` azul de 28 pontos do Word, e o
documento do primeiro dia sairia com uma cara que ninguém escolheu.

### As peças do documento

### `def _texto_padrao(documento, relatorio, estilos)`

*linha 383*

Os parágrafos fixos que abrem todo relatório. Devolve se escreveu algum.

O texto vem no `Relatorio`, e não de uma constante lida aqui: quem escreve o
documento não sabe de onde ele veio, e no dia em que ele passar a vir do
`projeto.yaml` ou de um arquivo por cliente, este módulo não muda.

Sem estilo próprio de propósito. É texto corrido, e texto corrido é o estilo
`FlatCap Corpo` — que é justamente o que se ajusta no Word para mudar a cara
de todos os relatórios de uma vez.

O `bool` de volta existe para a quebra de página: sem texto de abertura, a
primeira página seria só o título e o subtítulo, e quebrar ali produziria
uma página quase em branco que ninguém pediu.

Ele diz só o que este módulo sabe — «escrevi algum parágrafo» —, e quem
decide a quebra é o `escrever`, que soma a isto os alertas. A distinção
importa porque o caminho do `flatcap relatorio` nunca chega aqui com o texto
vazio: o `relatorio.montar_abertura` devolve pelo menos os dois marcadores
`«a preencher: …»` quando os campos da ficha estão em branco, de propósito.
Este ramo é para o `Relatorio` montado à mão — em teste, ou pela camada de
cima que um dia decida não imprimir marcador nenhum.

### `def _metodologia(documento, relatorio, estilos)`

*linha 416*

O subtítulo da metodologia e o parágrafo dela. Devolve se escreveu algum.

O subtítulo vai no estilo de subtítulo — o mesmo da linha `matrícula - nome`,
ajustável no Word pelo `FlatCap Subtitulo` —, preso ao parágrafo que vem depois,
para nunca terminar uma página sozinho. Sem parágrafo, ele não sai: um título
sem nada embaixo é o tipo de sobra que só aparece no papel.

O parágrafo é texto corrido, como o da abertura. O que ele diz é decisão do
`metodologia.py`; aqui, só a forma.

### `def _corrido(documento, texto, estilos)`

*linha 447*

Um parágrafo de texto corrido: o estilo do corpo, justificado, 8 pt depois.

### `def _caixa_de_aviso(documento, alerta, estilos)`

*linha 458*

Um alerta, em uma caixa amarela de uma célula só.

Caixa, e não parágrafo em itálico, porque este aviso precisa sobreviver a
duas coisas: à leitura na diagonal e à impressão em preto e branco. O fundo
resolve a primeira e o negrito do título resolve a segunda.

### `def _escrever_tabela(documento, tabela, numero, estilos)`

*linha 495*

Uma tabela do `.csv`, com a legenda em cima. As notas do `.csv` não vêm
junto: ver o comentário no fim da função.

O texto das células atravessa intacto: `28,7` no arquivo é `28,7` no Word. A
única decisão de apresentação é o alinhamento — texto à esquerda, porque se lê
pelo começo, e número à direita, porque se lê pela unidade. Ver
`_colunas_de_texto`.

*linha 546*

> Um rótulo e números — toda tabela da descritiva — ficam na repartição de
> sempre. Mais de uma coluna de texto é outra tabela, e reparte pelo conteúdo.

*linha 559*

> As notas do `.csv` — os dois denominadores, a convenção de fechamento das
> faixas — são lidas pelo `relatorio.py` e **não** são impressas: saíram na
> revisão de formatação. Elas continuam no arquivo que a Fase 5 escreveu, e
> os dois denominadores continuam nomeados no cabeçalho da tabela ("% dos
> válidos" e "% do total"), que é onde a distinção precisa mesmo aparecer.

### `def _repartir_larguras(quadro, largura_util, colunas)`

*linha 567*

Dá à coluna do rótulo o espaço que ela precisa, e reparte o resto.

O Word decide a largura das colunas sozinho quando a tabela está em
`autofit`, e a conta que ele faz é sobre o texto que está lá: em uma tabela
de frequência, `% dos válidos` no cabeçalho é mais largo do que qualquer
número da coluna, e o resultado é uma coluna de rótulos espremida quebrando
`(sem informação)` em duas linhas ao lado de três colunas de números
folgadas. Fixar a repartição resolve, e é a única decisão de largura que
este módulo toma.

### `def _larguras_pelo_conteudo(tabela, de_texto, largura_util)`

*linha 593*

A repartição das tabelas com mais de uma coluna de texto: cada coluna pelo que
ela carrega.

A repartição de sempre — um terço para o rótulo, o resto em partes iguais —
foi desenhada para a tabela de frequência, que tem **um** rótulo e números. O
cruzamento tem dois rótulos, a normalidade tem uma frase na última coluna e a
associação tem o nome do teste, e nas três a regra dava o espaço à coluna
errada: `Qui-quadrado com correção de Yates` quebrava em três linhas ao lado de
uma `variável 1` quase vazia, e o cabeçalho `faltantes` quebrava no meio da
palavra.

A regra, em três passos:

* **número não quebra.** Cada coluna de número recebe a largura do texto mais
  longo dela, cabeçalho incluído — com um mínimo, para `n` não virar um fio;
* **texto curto não quebra.** O que sobra vai para as colunas de texto, e a
  que precisa de menos recebe tudo o que precisa antes de as longas dividirem
  o resto em partes iguais. Nenhuma fica abaixo da sua palavra mais longa;
* **sobrando espaço**, ele vai para as colunas de texto, na proporção do que
  cada uma carrega.

As larguras são estimativas para a fonte das tabelas, com folga. Quando nem as
palavras mais longas cabem, devolve `None`, e a tabela fica na repartição de
sempre — que pelo menos é previsível.

#### `def em_emu(caracteres)`

*linha 622*

#### `def textos(posicao)`

*linha 625*

*linha 671*

> A soma das palavras mais longas cabia, mas a ordem da divisão pode ter dado a
> uma coluna curta o que faltou a uma longa. Estourar a mancha da página nunca.

### `def _fixar_larguras(quadro, larguras)`

*linha 678*

Aplica largura por coluna e desliga o autoajuste.

A largura precisa ser escrita em **toda** célula da coluna, e não só no
`w:gridCol`: o Word obedece ao grid, o LibreOffice obedece à célula, e um
documento que sai certo em um e torto no outro é um documento que ainda dá
trabalho.

*linha 687*

> `autofit = False` já escreve `<w:tblLayout w:type="fixed"/>` no lugar certo
> do `tblPr`. Acrescentar outro à mão deixava dois no mesmo elemento, o
> segundo depois do `tblLook` — documento inválido pelo esquema do OOXML, que
> o Word abre assim mesmo e um validador recusa. Estava em toda tabela de
> todo relatório já entregue.

### `def _escrever_figura(documento, figura, numero, estilos)`

*linha 700*

Uma figura, na largura útil da página do modelo.

Um `.png` que não abre — a rodada interrompida no meio da gravação, o disco
que encheu, a sincronização da nuvem que deixou o arquivo pela metade — não
sobe como a exceção do `python-docx` (`UnrecognizedImageError`, que nem é
`OSError`): vira `RelatorioError` com o nome do arquivo, e o
`executar_relatorio` devolve o relatório anterior ao lugar.

- *linha 717* — `except Exception as erro:` — noqa: BLE001 - a leitura de imagem estoura de várias formas

### `def _legenda(documento, texto, estilos)`

*linha 730*

A legenda de uma tabela ou de uma figura, sempre acima do objeto.

Quando o modelo tem um estilo de legenda, ele manda inteiro — nem tamanho,
nem cor, nem negrito são forçados por aqui. É o degrau de baixo da fila que
escreve à mão, e só ele.

*linha 752*

> Legenda nunca fica órfã no pé da página: ela anda com o objeto que nomeia.
> Sem isto, `Figura 2. Escolaridade` termina uma página e a figura começa a
> seguinte — e quem lê passa a página procurando o que a legenda prometeu.

### Peças de baixo nível

### `def _paragrafo(documento, texto, estilo, tamanho, negrito, italico, cor, espaco_antes, espaco_depois)`

*linha 761*

### `def _texto(paragrafo, conteudo, tamanho, negrito, italico, cor, estilo, aplicar_estilo)`

*linha 783*

Escreve o texto e formata à mão só o que o estilo não resolveu.

O `aplicar_estilo` é o degrau de baixo da fila de estilos: quando a peça
encontrou um estilo no modelo, a formatação à mão **não** é aplicada — senão
o código passaria por cima da decisão que você tomou no Word, que é
exatamente o que a separação template/código existe para impedir. Tamanho e
cor só entram quando não há estilo para mandar neles.

- *linha 805* — `except KeyError:` — pragma: no cover - o estilo veio da resolução

### `def _alinhar(paragrafo, de_texto)`

*linha 821*

### `_CELULA_NUMERICA`

*linha 825*

> Uma célula que se lê como número: `15`, `26,8`, `+0,45`, `−1,2`, `< 0,001`,
> `100,0%` — e a data `01/03/2026`, que numa tabela de período se alinha com os
> números ao lado dela. O traço e a célula vazia não contam para lado nenhum: são o
> "não se aplica" de qualquer coluna.

### `def _colunas_de_texto(tabela)`

*linha 835*

As posições das colunas que são texto e vão à esquerda.

A primeira sempre: é o rótulo da linha. As outras, pelo **conteúdo**: basta uma
célula que não se leia como número para a coluna ser de texto.

Até a 1.4.0 a regra era a posição — a primeira à esquerda, o resto à direita —,
e ela valia porque toda tabela tinha um rótulo e depois números. O cruzamento
tem **dois** rótulos, `Sexo` e `Escolaridade`, e a segunda coluna sairia
empurrada para a direita, com `Fundamental` alinhado pela última letra. A
coluna `leitura` da normalidade já saía assim.

Pelo conteúdo, e não por uma marca no `.csv`, porque o `.csv` é o que a análise
escreve e o que você abre no Excel — acrescentar a ele uma linha de metadado de
alinhamento seria pôr apresentação dentro do dado.

### `def _largura_util(documento)`

*linha 862*

A mancha da página: largura menos as duas margens, lida da seção.

### `def _resolver_estilos(documento)`

*linha 870*

Percorre as filas e devolve o primeiro nome que o modelo tem.

#### `def primeiro(fila)`

*linha 876*

### `def _limpar_fim(documento)`

*linha 892*

Descarta os parágrafos vazios do fim do modelo.

Todo `.docx` salvo pelo Word termina com pelo menos um parágrafo vazio, e
alguns modelos terminam com meia dúzia. Sem isto, o relatório começaria
depois de um punhado de linhas em branco — às vezes depois de uma página
inteira em branco, o que faz o documento parecer defeituoso já na abertura.

### `def _propriedades(documento, relatorio)`

*linha 909*

Os metadados do arquivo, que o Windows mostra sem ninguém abrir o documento.

A rodada é a do manifesto principal, com o nome dela — até a 1.14.1 o texto dizia
"a partir da descritiva" mesmo quando só a normalidade tinha rodado. E o banco
pode não existir: o relatório da amostra sai de um projeto que só tem o
`desenho.yaml`, e ali o certo é "sem banco", e não "banco ?".

### `def _salvar_atomico(documento, caminho)`

*linha 933*

Grava o documento inteiro ou não grava nada.

Mesma garantia do `escrever_atomico` do `ficha.py`, e pelo mesmo motivo: o
temporário é criado na **mesma pasta** do destino, porque `os.replace` só é
atômico dentro do mesmo sistema de arquivos. Meio `.docx` não é um documento
incompleto — é um arquivo que o Word se recusa a abrir.

O temporário é o do `ficha.temporario_ao_lado`, que respeita o `umask`: o
`.docx` sai com a permissão de qualquer arquivo novo, e não só para o dono.

### XML que a API do python-docx não expõe

### `def _manter_junta(quadro)`

*linha 963*

Impede que uma tabela curta se parta na quebra de página.

Uma tabela de frequência de cinco linhas partida entre duas páginas — as
categorias em uma e o `Total` na outra — é lida como duas tabelas incompletas.
O `keep_with_next` vai em todas as linhas menos a última: na última, ele
arrastaria junto o parágrafo seguinte, que é a legenda da figura.

Acima de `_LINHAS_PARA_MANTER_JUNTA` a tabela se parte de propósito, e é o
cabeçalho repetido que resolve a leitura do outro lado.

#### `def prender(linha)`

*linha 977*

*linha 987*

> A tabela longa parte, e é o cabeçalho repetido que resolve a leitura do
> outro lado. Com uma exceção: o `Total`. Sozinho no alto de uma página,
> embaixo do cabeçalho repetido, ele vira uma página que só tem um título e
> uma faixa verde — e quem lê volta atrás procurando os números que somam
> nela. As duas categorias antes dele vão junto, o que basta para a faixa
> nunca aparecer desacompanhada.

### `def _repetir_cabecalho(linha)`

*linha 998*

Marca a primeira linha como cabeçalho, para o Word repeti-la a cada página.

A tabela de distribuição no tempo de um estudo de dois anos tem 24 linhas e
atravessa a quebra de página com frequência. Sem o cabeçalho repetido, a
metade de baixo é uma coluna de números sem nome.

### `def _sombrear(celula, cor)`

*linha 1012*

### `def _bordas_da_tabela(tabela, cor, espessura)`

*linha 1020*

Uma borda em volta de tudo. Serve a caixa de aviso, que é uma célula só.

### `def _bordas_de_tres_linhas(quadro, cor)`

*linha 1033*

Topo, sob o cabeçalho, base. Nenhuma vertical.

É o último degrau da fila para as tabelas do relatório, e ele mudou junto com
o estilo `FlatCap Tabela` que o `flatcap template` grava: os dois precisam ter
a mesma cara, senão um projeto sem modelo sai com uma tabela diferente da de
todos os outros — que é exatamente o tipo de diferença que ninguém percebe até
o cliente pôr dois relatórios lado a lado.

### `def _lado_da_borda(nome, espessura, cor)`

*linha 1051*

### `def _escrever_bordas(tabela, lados)`

*linha 1060*

Escreve `w:tblBorders`, com `none` explícito no que não foi pedido.

O `none` precisa ser escrito: sem ele, o lado herda a borda do estilo de
tabela do modelo, e uma tabela de três linhas herdaria as verticais de um
`Table Grid` institucional sem nada no código dizendo de onde elas vieram.

*linha 1078*

> `tblBorders` vem antes de `tblLayout` e `tblLook` no esquema do OOXML.

### `def _rodape_com_pagina(secao)`

*linha 1086*

O rodapé do documento padrão: `página N`, centralizado.

O número da página é um campo do Word, e campo não é texto: ele é escrito
como instrução (`PAGE`) e o Word calcula na hora de exibir. Escrever o número
à mão daria "página 1" em todas as páginas.

### `def _campo(paragrafo, instrucao, tamanho)`

*linha 1102*

### O modelo

### `def escrever_template(caminho)`

*linha 1124*

Escreve um `template.docx` com os estilos do FlatCap já definidos.

O corpo sai **vazio**, de propósito: tudo o que estiver no corpo do modelo
aparece antes do relatório, em todo relatório. Um modelo com instruções
dentro imprimiria as instruções em cima do documento que você entrega.

O que ele traz é o que se ajusta no Word: página, margens, cabeçalho,
rodapé com o número da página, e os seis estilos `FlatCap *` que o relatório
procura antes de qualquer outro. Mude a fonte de `FlatCap Corpo` e o
documento inteiro muda; ponha o logotipo no cabeçalho e ele aparece em todas
as páginas de todos os relatórios.

*linha 1147*

> As propriedades do arquivo são o único lugar de dentro do `.docx` em que
> cabe uma explicação: elas aparecem no Word em Arquivo → Informações, não são
> impressas, e o `_propriedades` as reescreve em cada relatório gerado — então
> o que está escrito aqui não tem como vazar para o documento do cliente.

### `_NOTA_DO_MODELO`

*linha 1160*

> O `dc:description` do OOXML tem limite de 255 caracteres — daí a nota ser um
> ponteiro para a folha de decisões, e não a explicação inteira.

### `def _escrever_decisoes(caminho)`

*linha 1170*

Escreve a folha de decisões ao lado do modelo, se ela ainda não existir.

**Não sobrescreve.** O `.docx` é regerável e o comando avisa que vai
substituí-lo; este arquivo é texto que alguém escreveu, e a segunda coisa que
um usuário faz com ele é acrescentar as decisões da própria instituição.
Perder isso em um `flatcap template --sim` distraído seria o mesmo defeito que
a fusão do `dicionario.csv` existe para impedir.

### `def _fonte_do_estilo(estilo, nome)`

*linha 1186*

Escreve a fonte nos quatro atributos do `w:rFonts`, e não só em dois.

O `style.font.name` do `python-docx` preenche `w:ascii` e `w:hAnsi` — o texto
latino comum — e deixa `w:cs` e `w:eastAsia` como estavam. Um caractere que
caia em um desses é desenhado com a fonte do **tema**, no meio de um parágrafo
que deveria ser todo da mesma fonte. Acontece pouco e é impossível de
diagnosticar quando acontece.

Os atributos `*Theme` são removidos no mesmo movimento: quando os dois
convivem, quem vence depende da versão do Word.

### `def _fixar_tema(documento)`

*linha 1208*

Põe a mesma fonte também no tema do documento.

O tema é o que o Word usa para todo estilo que **não** diz a fonte dele. O que
vem no modelo base do `python-docx` traz `minorFont` Cambria e `majorFont`
Calibri — uma serifa esperando a vez. Os estilos `FlatCap *` dizem a fonte
deles e não dependem do tema; o `Título 1` nativo, o `Legenda` nativo e
qualquer estilo que alguém aplique à mão no Word dependem.

Sem isto o modelo é um arquivo em que a fonte muda sozinha quando o usuário
mexe em outra coisa — e ele não tem como descobrir por quê.

### `def _definir_estilos(documento)`

*linha 1231*

Cria os estilos `FlatCap *`, cada um herdando de um nativo do Word.

Herdar importa: um estilo criado do zero não tem fonte, tamanho nem idioma, e
o Word preenche esses buracos com o que estiver por perto — o que faz o
documento mudar de cara quando você mexe em outra coisa. Herdando de `Normal`,
cada estilo começa igual ao corpo do documento, e a personalização é uma
diferença explícita a partir dali.

**De qual nativo se herda é decisão, não detalhe.** O `Titulo` e o `Subtitulo`
herdavam do `Title` e do `Subtitle` do Word, e vinha junto o que ninguém pediu:
o `Title` traz uma régua azul embaixo do título, e o `Subtitle` traz
espacejamento entre letras. Os dois apareciam em todo relatório entregue, e
nenhum deles está escrito em lugar nenhum do código — herança é isso.

Os dois passaram a herdar de `Normal`. Ficaram de herança nativa só os dois em
que ela paga: `FlatCap Secao` de `Heading 1`, que é o que põe o nome da
variável no painel de navegação do Word e num sumário, e `FlatCap Legenda` de
`Caption`, que é o estilo que o Word usa para legenda de tabela e figura.

#### `def criar(nome, base, tipo)`

*linha 1256*

- *linha 1262* — `except KeyError:` — pragma: no cover - as bases são nativas do Word

### `def _estilo_de_tabela(documento)`

*linha 1305*

Cria `FlatCap Tabela` — as três linhas, dentro do modelo.

É o estilo que faltava. A fila do `_resolver_estilos` procura `FlatCap Tabela`
antes de `Table Grid`, mas o `flatcap template` nunca escreveu nenhum dos dois:
o resultado é que "ajuste a borda da tabela no Word" não tinha onde acontecer —
não havia estilo para abrir, e a tabela caía no `Table Grid` nativo, que é a
grade completa.

Com ele no modelo, a borda passa a ser sua: abra o `template.docx`, mude o
estilo, e todo relatório muda. O código deixa de tocar em borda de tabela —
que é o que o contrato deste módulo promete.

O XML é escrito à mão porque o `python-docx` não expõe borda de estilo de
tabela. São duas peças: o `w:tblPr` do estilo, que vale para a tabela inteira,
e a banda `firstRow`, que é como o OOXML diz "a régua fina vai sob o
cabeçalho" sem precisar saber quantas linhas a tabela tem.

### `def _margens_da_celula(cm)`

*linha 1354*

O respiro entre a régua e o texto. Sem ele a tabela de três linhas fica
apertada — sem verticais, é o espaço que separa as colunas.

## `flatcap/amostral.py`

`SPDX-FileCopyrightText: 2026 Matheus Fernandes` · `SPDX-License-Identifier: GPL-3.0-or-later`

*227 linhas.*

A aritmética da amostragem — o z, o tamanho e a perda —, como números.

É a fronteira do `hipoteses.py` com o `comparacao.py`, aplicada à amostra. Este módulo
recebe números e devolve números; quem lê o `desenho.yaml`, converte os percentuais, monta a
tabela e escreve o relatório da amostra é o `amostragem.py`. Três consequências:

* **só biblioteca padrão** — `math` e `statistics`. Sem `pandas`, `numpy` nem `scipy`: o
  comando da amostragem parte rápido, e o `test_amostral.py` confere as contas sem projeto,
  ficha nem banco;
* **frações, e não percentuais** — 0,95, 0,05, 0,5. O `95` é como o cliente fala e como a
  ficha se escreve; a conversão é de quem lê a ficha, e uma conta que aceitasse as duas
  formas teria de adivinhar qual veio;
* **nenhuma formatação** — o 278 sai daqui como `int`, e a forma dele na tabela é decisão de
  quem escreve a tabela.

### A conta

Para estimar uma proporção, com V = p(1 − p); para estimar uma média, com V = σ²:

    n₀ = z²·V / e²                            população grande, sem correção
    n  = N·z²·V / [(N − 1)·e² + z²·V]          com a população N

A segunda é o n₀ corrigido pela população, na forma que o OpenEpi usa, e é igual a
`n₀ / [1 + (n₀ − 1)/N]`. A perda esperada entra por último — `⌈n / (1 − perda)⌉` —, e o
resultado nunca passa de N: uma amostra do tamanho da população é um censo.

### Por que `NormalDist`, e não o `scipy`

O z é o quantil bilateral da normal, o `qnorm(1 − α/2)` do R. O `statistics.NormalDist` da
biblioteca padrão implementa o mesmo algoritmo do `qnorm` — o AS241 de Wichura (1988) —, e
trazer o `scipy` só para um quantil faria o comando pagar a partida dele por nada.

### `TOLERANCIA`

*linha 43*

> A folga do arredondamento para cima. Ver `para_cima`.

### `class Tamanho`

*linha 48*

O tamanho da amostra, e como ele saiu.

`n` é o tamanho que dá a precisão pedida — corrigido pela população quando há uma —, e
`n_final` é o que vai a campo: com a perda somada e no máximo N. Os dois já arredondados
para cima. `n0` e `n_corrigido` guardam as contas sem arredondar, para o manifesto.

No tamanho escrito à mão (`tamanho_decidido`) não há conta: `z`, `n0` e `n_corrigido`
ficam `None`, e `n` é o que foi escrito.

#### `def censo(self)`

*linha 69*

A amostra é a população inteira.

#### `def decidido(self)`

*linha 74*

O tamanho foi escrito à mão, e não calculado.

### `def z_da_confianca(confianca)`

*linha 79*

O quantil bilateral da normal padrão: o `qnorm(1 − (1 − confianca)/2)` do R.

`confianca` é uma fração, entre 0 e 1 sem as pontas: 0,95 dá 1,959964.

### `def variancia_da_proporcao(proporcao)`

*linha 90*

O p(1 − p) da conta de uma proporção: 0,25 com p = 0,5, que é o maior possível.

Por isso 50% é o valor de quem não sabe o que esperar — é o que dá o maior tamanho.

### `def para_cima(valor)`

*linha 101*

Arredonda para cima, sem que o resto de ponto flutuante vire uma unidade a mais.

Um tamanho de amostra se arredonda sempre para cima: 277,1 pessoas não dão a precisão
pedida, e 278 dão. Mas uma conta que devia dar 278 exatos pode chegar como
278,00000000000006, e o `math.ceil` cru faria dela 279. A folga de 1e-9 está muito abaixo
de qualquer diferença que importe numa contagem de pessoas, e muito acima do resto de
ponto flutuante de uma conta destas.

### `def com_perda(n, perda)`

*linha 114*

O tamanho que vai a campo para que, perdida a fração `perda`, sobrem `n`.

`⌈n / (1 − perda)⌉`: com perda de 10%, 292 viram 325 — e 325 × 0,9 = 292,5.

### `def tamanho_aas(*, confianca, margem, variancia, populacao, perda)`

*linha 127*

O tamanho da amostra aleatória simples, sem reposição.

Args:

    confianca: o nível de confiança, em fração — 0,95.
    margem: a margem de erro, na escala da estimativa: 0,05 (5 pontos percentuais) para
        uma proporção; na unidade da variável para uma média.
    variancia: p(1 − p) para uma proporção (`variancia_da_proporcao`); σ² para uma
        média.
    populacao: o N; `None` é a população grande, sem correção.
    perda: a fração que se espera perder, de 0 a 1 sem o 1.

Raises:

    ValueError: um valor fora do domínio. Quem chega aqui pelo `amostragem.py` já passou
        pelas recusas da ficha, com a frase de cada uma.

### `def tamanho_decidido(n, *, populacao, perda)`

*linha 167*

O tamanho escrito à mão, no lugar da conta, com a perda somada a ele.

A perda soma porque o `n` escrito é o tamanho necessário — o que precisa sobrar no fim —,
como na conta. Quem quer o número que vai a campo escreve a perda zero.

### `def _conferir_populacao(populacao)`

*linha 182*

### `def _fechar(n, populacao, perda, *, z, n0, n_corrigido)`

*linha 187*

A perda somada, e o teto de N.

O teto vale para o `n_final`, e não para o `n`: com a correção de população finita o `n`
nunca passa de N, e no tamanho decidido isso já foi recusado. Quem passa é o `n` com a
perda — 169 de 300 com metade de perda dariam 338 —, e aí a amostra é a população
inteira.

## `flatcap/amostragem.py`

`SPDX-FileCopyrightText: 2026 Matheus Fernandes` · `SPDX-License-Identifier: GPL-3.0-or-later`

*1436 linhas.*

A amostragem — o plano da amostra de um projeto, na pasta dela, com o relatório dela.

O projeto costuma começar com a amostragem e evoluir depois para a análise. O fluxo
começa sempre no `flatcap novo`, e a amostragem vem depois dele:

    flatcap novo 23 --sim          o projeto, como sempre: ficha, histórico, três pastas
    flatcap amostragem 23 --sim    cria a `4. Amostragem/` e o `desenho.yaml`, e para
      (preencher o desenho.yaml)
    flatcap amostragem 23 --sim    a conta, o `tamanho.csv` e o relatório da amostra

Segue o padrão da casa, decidir e escrever separados:

    plano = preparar_amostragem(raiz)   # lê o desenho.yaml, calcula, monta o documento
    executar_amostragem(plano)          # só escreve

E, como as análises, **não fala com o REDCap**. Recebe `Path`, não `Config`.

### Uma pasta própria, e não uma análise

Tudo da amostra mora em `4. Amostragem/`: a ficha (`desenho.yaml`), a conta
(`tamanho.csv`), o índice da rodada (`manifesto.json`), o relatório da amostra e as
versões antigas dele, em `4. Amostragem/Versões antigas/`. As pastas 1, 2 e 3 ficam para
a análise que vem depois.

Por isso a amostragem não está no `analises.REGISTRO`, na `ORDEM_PADRAO_DAS_ANALISES`
nem no `flatcap analisar`. O relatório das análises varre só `3. Análises/`, e nunca vê a
amostra; o relatório da amostra nunca vê as análises.

A pasta nasce no primeiro `flatcap amostragem`, e não no `novo`. O `novo` não tem como
saber se o pedido é de amostragem — o formulário do REDCap não tem essa opção —, o
projeto que nunca amostra não ganha uma pasta vazia, e o projeto que já existia ganha a
pasta do mesmo jeito, sem migração. A amostragem não cria projeto: sem a pasta do `novo`,
o `localizar_projeto` recusa, como em todo comando.

### A ficha é o `desenho.yaml`, preenchido à mão

A primeira rodada escreve o modelo comentado e para. O modelo já vem com o caso de todo
dia — 95% de confiança, margem de 5 pontos, proporção esperada de 50% —, e o pedido mais
comum, o do cliente que informa só o tamanho da população, é preencher a `populacao` e
rodar de novo.

O FlatCap escreve o modelo uma vez e, dali em diante, só lê. É a regra do
`dicionario.csv` aplicada a outro arquivo: o que está escrito ali é decisão sua. Quem o lê
é o `ficha.ler_yaml`, para que um YAML quebrado ganhe o diagnóstico da ficha.

As recusas saem todas de uma vez, como nas análises: descobrir o segundo engano depois de
corrigir o primeiro é o jeito mais lento de arrumar uma ficha.

### O espaço para os outros desenhos

O desenho é escolhido dentro da análise, como o teste é dentro da comparação: cada um é
uma entrada no `DESENHOS`, com as chaves dele no `desenho.yaml` e a conta dele. Hoje há
um, a aleatória simples; os previstos (`PREVISTOS`) recusam dizendo que ainda não
existem, e não que não são conhecidos. O sorteio de uma lista também tem o lugar dele no
registro, e nenhum desenho sorteia ainda.

### O relatório da amostra

Montado com as peças do relatório das análises: um `relatorio.Relatorio` com a seção do
tamanho, escrito pelo `documento.escrever`, com o mesmo modelo `.docx` e a mesma primeira
página — a finalidade e os objetivos do `projeto.yaml`. **Não recalcula nada**: a tabela
do documento é lida, pelo `relatorio.tabela_do_texto`, do mesmo texto que vai para o
`tamanho.csv`.

O texto de metodologia sobre a amostra feita tem o lugar dele, o `METODOLOGIA`, e ele
está vazio de propósito — a regra do `TEXTO_PADRAO` do relatório: nada de parágrafo de
mentira guardando o lugar.

### `DESENHO_AAS`

*linha 125*

> O nome do único desenho de hoje, como se escreve no `desenho.yaml`.

### `PREVISTOS`

*linha 128*

> Os desenhos que vêm depois, na ordem do `claude/amostragem-tipos.md`. Escrever um deles
> no `desenho.yaml` recusa dizendo que ainda não existe — e não que não é conhecido, que
> mandaria procurar um erro de digitação que não está lá.

### `CHAVES_COMUNS`

*linha 139*

> As chaves que todo desenho aceita. Cada desenho acrescenta as dele (`Desenho.chaves`).

### `CHAVES_DA_CONTA`

*linha 151*

> As que fazem a conta. Com o `n` escrito à mão, elas ficam em branco.

### `MARGEM_QUE_PARECE_FRACAO`

*linha 154*

> A margem de uma proporção que, escrita em pontos, parece uma fração: `0.05` é a margem de 5%
> escrita como fração, e é 0,05 ponto. Até 0,2 — a fração de uma margem de 20% —, a conta sai
> com aviso; acima disso, a leitura em fração daria uma margem que ninguém pede.

### `PREFIXO_RELATORIO_DA_AMOSTRA`

*linha 165*

> O prefixo do relatório da amostra, como o `Relatorio_` do relatório das análises. Os
> dois nunca se encontram: este mora em `4. Amostragem/`, e aquele na raiz do projeto.

*No módulo, linha 169:*

> ─────────────────────────────────────────────────────────────────────────────
>  O TEXTO DE METODOLOGIA DE CADA DESENHO — é aqui que se escreve.
>
>  Uma linha da tupla, um parágrafo do documento. Ele entra na primeira página do
>  relatório da amostra, depois da finalidade e dos objetivos, e cada parágrafo pode
>  usar os campos da conta entre chaves:
>
>      {desenho} {populacao} {confianca} {z} {margem} {proporcao} {desvio}
>      {n0} {n} {perda} {n_final}
>
>  Os campos chegam escritos como na tabela (`95%`, `5 pontos percentuais`, `1200`), e
>  o que a conta não usou chega vazio — a média não tem `{proporcao}`, o tamanho
>  decidido à mão não tem `{z}`. Por isso o texto de cada desenho vai precisar de uma
>  frase por situação: proporção ou média, com ou sem N, com ou sem perda.
>
>  `()` é o estado de hoje: ainda não escrito. É a regra do `TEXTO_PADRAO` do
>  relatório — nada de parágrafo de mentira guardando o lugar: um `xxxxx` esquecido
>  aqui chega impresso na mão do cliente.
> ─────────────────────────────────────────────────────────────────────────────

### `MODELO_DO_DESENHO`

*linha 193*

> O `desenho.yaml` que a primeira rodada escreve. Já vem com o caso de todo dia, para que
> o pedido mais comum — o cliente que informa só o tamanho da população — seja preencher a
> `populacao` e rodar de novo. Lido como está, ele é válido: dá a conta de população
> grande.

### Erros

### `class AmostragemError(RuntimeError)`

*linha 232*

Falha da amostragem, já traduzida para o usuário.

Erro próprio pela regra da casa: a CLI captura esta classe e transforma em painel.
Qualquer outra exceção é bug de verdade e deve subir com o traceback inteiro.

### `class DesenhoInvalidoError(AmostragemError)`

*linha 241*

O `desenho.yaml` tem o que não serve. A mensagem lista **todos** os problemas.

### `class DesenhoExistenteError(AmostragemError)`

*linha 247*

O `desenho.yaml` apareceu entre a simulação e a execução, e o modelo não o
sobrescreve: o arquivo é seu.

### O que circula

### `class Pedido`

*linha 258*

O `desenho.yaml` lido, conferido e convertido.

Os percentuais viram frações aqui (95 → 0,95), porque o `amostral.py` trabalha em
frações. A margem só vira fração quando é de uma proporção; de uma média, ela é na
unidade da variável e fica como veio. `escrito` é o arquivo como estava, para o
manifesto guardar o que você escreveu, e não só o que o FlatCap entendeu; `texto` é o
arquivo inteiro, comentários incluídos, para a cópia que acompanha a rodada quando
ela for para as versões antigas.

#### `def estima(self)`

*linha 282*

`proporcao`, `media`, ou vazio quando o tamanho foi decidido à mão.

### `class Calculo`

*linha 290*

O tamanho, e a tabela que o apresenta.

`linhas` são os pares `parâmetro;valor` do `tamanho.csv`, na ordem da leitura: o
desenho e a população, a precisão pedida, e os tamanhos até o da amostra, que é
sempre a última linha. `notas` vão para o cabeçalho do `.csv` e para o manifesto, e
não para o documento. `campos` são os mesmos valores escritos, para o texto de
metodologia.

### `class Desenho`

*linha 309*

Um desenho que a amostragem sabe calcular — e, um dia, sortear.

O nome é o que se escreve em `desenho:`. As `chaves` são as do `desenho.yaml` que só
ele aceita, além das `CHAVES_COMUNS`; vazio na aleatória simples. O `sortear` chega
com o sorteio de uma lista, num passo seguinte, e até lá nenhum desenho sorteia.

### `class Amostragem`

*linha 326*

A rodada inteira, decidida. É daqui que saem os arquivos e o terminal.

#### `def raiz(self)`

*linha 338*

#### `def tamanho(self)`

*linha 342*

### `class Arquivamento`

*linha 347*

A rodada anterior, a caminho de `4. Amostragem/Versões antigas/`.

Arquivo por arquivo, e não a pasta inteira como nas análises: aqui a rodada divide a
pasta com o `desenho.yaml`, que é seu e fica onde está.

Vai junto o `desenho.yaml` **de então** (`desenho`), para a pergunta "com que ficha
saiu aquele relatório?" ter resposta exata. Ele vem do manifesto daquela rodada, que
guarda o texto que ela leu — e não do arquivo que está na pasta, que a esta altura
você já mudou: copiar o de agora poria a ficha nova ao lado do relatório velho. Sem
um manifesto legível, a rodada vai sem ele, e não com o errado.

### `class PlanoAmostragem`

*linha 367*

Tudo o que a amostragem faria, decidido e ainda não escrito.

Dois casos, e o `amostragem` diz qual: `None` é a primeira rodada, que só escreve o
modelo do `desenho.yaml`; preenchido, é a rodada que calcula e escreve o relatório.

#### `def so_o_modelo(self)`

*linha 390*

A primeira rodada: o `desenho.yaml` ainda não existe.

#### `def desenho_yaml(self)`

*linha 395*

#### `def arquivos(self)`

*linha 399*

### `class ResultadoAmostragem`

*linha 406*

O que a execução de fato escreveu.

### Casos de uso

### `def preparar_amostragem(raiz, titulo, template, agora)`

*linha 417*

Lê o `desenho.yaml`, faz a conta e monta o relatório da amostra. Não escreve nada.

Sem o `desenho.yaml`, o plano é o da primeira rodada: criar a `4. Amostragem/`, se
ainda não existir, e escrever o modelo para preencher.

Args:

    raiz: a pasta do projeto (a que tem o `projeto.yaml`).
    titulo: o título na primeira linha do relatório da amostra.
    template: um `.docx` de onde herdar estilos; sem ele, os degraus de sempre — o
        `template.docx` do projeto, do cliente e do `FLATCAP_ROOT`.
    agora: relógio injetável, como em todo `preparar*`.

Raises:

    FichaError (a ficha do projeto), `DesenhoInvalidoError` (o `desenho.yaml`, com
    todos os problemas de uma vez) e `ModeloAusenteError` (o `template` indicado não
    existe).

### `def executar_amostragem(plano)`

*linha 491*

Escreve o plano no disco. Não decide mais nada.

Na primeira rodada, a pasta e o modelo. Nas outras, a ordem das análises: arquiva a
rodada anterior, escreve a tabela, o relatório da amostra e, por último, o
`manifesto.json` — o recibo vem depois do que ele descreve.

Cada etapa registra como voltar atrás. Uma falha no meio desfaz o que já foi feito,
inclusive devolvendo a rodada anterior ao lugar, e a exceção continua subindo
inteira. O `python-docx` entra aqui dentro, e não no topo do módulo, pelo motivo do
`executar_relatorio`: a simulação não escreve documento nenhum e não deve pagar por
ele.

### `def _executar_modelo(plano)`

*linha 552*

A primeira rodada: a pasta, se faltar, e o modelo do `desenho.yaml`.

O modelo nunca escreve por cima de um `desenho.yaml`, nem do que apareceu entre a
simulação e a execução: o arquivo é seu.

### `def _arquivar(arquivamento, desfazer)`

*linha 595*

Move a rodada anterior para `Versões antigas/`, com o `desenho.yaml` de então.

O `rmdir` de cada pasta criada aqui entra no desfazer **antes** dos arquivos, e o
desfazer roda ao contrário: os arquivos voltam primeiro, e a pasta sai vazia, que é
a única forma de ela sair.

### `def _desfazer(desfazer, avisos)`

*linha 624*

### O desenho.yaml

### `def ler_desenho(caminho)`

*linha 638*

Lê e confere o `desenho.yaml`. Recusa listando **todos** os problemas de uma vez.

A leitura é tolerante onde o engano é inofensivo — `AAS` ou `Aleatória simples`
no desenho, `2,5` com vírgula na margem — e estrita onde ele mudaria o número em
silêncio: o `12.000` que no YAML é doze, a confiança escrita como fração, a
proporção que a margem não cabe.

Raises:

    DesenhoInvalidoError: com todos os problemas — e também quando o arquivo não é
        um YAML válido, com o diagnóstico da ficha.

*linha 689*

> Sem desenho, `problemas` já tem a frase dele; o `is None` é para quem lê o tipo.

*linha 709*

> Já se sabe que é UTF-8: o `ler_yaml` acabou de ler o mesmo arquivo.

### `def _desenho_escrito(valor, problemas)`

*linha 715*

O desenho pelo nome, sem caixa nem acento: `AAS`, `aas` e `Aleatória simples` são o
mesmo. Previsto e ainda não feito recusa dizendo isso.

### `def _chaves_desconhecidas(bruto, desenho, problemas)`

*linha 747*

### `def _conferir_n(bruto, n, populacao, problemas)`

*linha 769*

Com o tamanho escrito à mão, a conta fica em branco, e o `n` cabe na população.

### `def _conferir_conta(bruto, confianca, margem, proporcao, desvio, problemas)`

*linha 784*

A precisão pedida: confiança, margem, e a proporção ou o desvio — um dos dois.

*linha 812*

> O α escrito no lugar da confiança: `confianca: 5` querendo 95% daria z = 0,06 e
> uma amostra de uma unidade, sem erro nenhum.

*linha 845*

> A margem é em pontos percentuais. Maior que a proporção, o intervalo passaria
> de 0% — e é assim que o `proporcao: 0.5` escrito querendo 50% se denuncia,
> em vez de dar n = 8 sem erro nenhum.

### A leitura dos valores

### `_APELIDOS`

*linha 860*

> Os nomes por extenso que querem dizer um desenho que existe.

### `def _chave(texto)`

*linha 869*

`Aleatória Simples` → `aleatoria_simples`: sem acento, sem caixa, com sublinhado.

### `def _vazio(valor)`

*linha 875*

### `def _numero(bruto, chave, problemas)`

*linha 879*

O número da chave, ou `None` quando ela falta ou está em branco.

### `def _inteiro(bruto, chave, problemas)`

*linha 893*

Um inteiro, escrito como inteiro.

Estrito de propósito. No YAML o ponto é a casa decimal, e o `12.000` que em português
é doze mil chega como doze — aceitá-lo daria uma população de 12 sem erro nenhum.

### `def _texto(valor)`

*linha 919*

O valor como ele aparece na mensagem: o que está no arquivo.

### `def _simples(valor)`

*linha 924*

O valor escrito, para o manifesto: o escalar do YAML como escalar do Python.

### `def _em_texto(nomes)`

*linha 935*

### A conta da aleatória simples

### `def calcular_aas(pedido)`

*linha 944*

O tamanho da aleatória simples, sem reposição, e a tabela dele.

Com o `n` escrito, não há conta: o tamanho é o escrito, com a perda somada.

*linha 953*

> O `ler_desenho` garante os três; um `Pedido` montado à mão sem eles é bug.

*linha 977*

> Aviso, e não recusa: uma margem pequena existe, nas pesquisas grandes. Mas é
> também como chega a margem escrita em fração — `0.05` querendo 5% —, que passa
> por todas as conferências e dá uma amostra cem vezes maior.

### `def _campos(pedido, tamanho)`

*linha 1000*

Os valores escritos como na tabela, para a tabela e para o texto de metodologia.

### `def _linhas(pedido, tamanho, campos)`

*linha 1026*

As linhas da tabela, do que se pediu ao que saiu. A última é sempre o tamanho da
amostra, que é a resposta — quem procura o número procura no fim.

### `def _notas(pedido, tamanho)`

*linha 1070*

O como da conta, para quem abrir o `.csv` sozinho. Não vai para o documento.

### `def _formatar(valor)`

*linha 1095*

Um número como se escreve numa tabela em português: `95`, `2,5`, `0,001`.

Sem o `banco.texto_de_numero` de propósito: o `banco.py` traz o `pandas`, e a
amostragem da v1 não abre banco nenhum.

### `def _percentual(fracao)`

*linha 1106*

### `def _pontos(valor)`

*linha 1110*

`5 pontos percentuais`, e `1,5 ponto percentual`: abaixo de dois, no singular.

*No módulo, linha 1116:*

> O registro. Depois das funções, que ele nomeia.

### A tabela, o manifesto e o relatório

### `def montar_tabela(desenho, calculo)`

*linha 1130*

O `tamanho.csv`. Duas colunas, e a última linha é a resposta.

### `def montar_manifesto(amostragem)`

*linha 1143*

O índice da rodada, no formato do das análises.

`banco` e `dicionario` vazios: a amostragem da v1 não abre banco nem obedece a
dicionário. O item tem `variavel` vazia e `colunas` vazias pelo mesmo motivo. Em
`detalhes`, os números sem arredondar, os valores como foram escritos (`escrito`) e
o `desenho.yaml` inteiro (`desenho_yaml`) — de onde sai a cópia que acompanha esta
rodada quando ela for para as versões antigas.

### `def montar_relatorio(amostragem, manifesto, pasta, titulo)`

*linha 1225*

O relatório da amostra, com as peças do relatório das análises.

A primeira página é a dele — a finalidade e os objetivos da ficha, com o marcador e
o alerta quando estão em branco —, e o texto de metodologia entra depois, quando
existir. A tabela é lida do texto do `tamanho.csv` pelo `tabela_do_texto`, a mesma
função que lê o arquivo do disco.

### `def texto_de_metodologia(amostragem)`

*linha 1264*

Os parágrafos do `METODOLOGIA` do desenho, com os campos da conta preenchidos.

### `def nome_do_relatorio_da_amostra(matricula, quando)`

*linha 1273*

`Amostragem_123465_2026-10-26.docx`, como o `relatorio.nome_do_relatorio`.

A matrícula passa pela mesma limpeza dos nomes de pasta: ela é digitada por outra
pessoa, em outro sistema, e o que vem de fora não monta caminho.

### `def resumo_do_tamanho(tamanho)`

*linha 1284*

`325 de 1200`, `385` ou `120 de 120 — a população inteira`: a linha do terminal.

### A rodada anterior

### `def _arquivamento(pasta, quando, anterior)`

*linha 1295*

O que a rodada vigente escreveu, e para onde vai quando ela for refeita.

Os nomes que esta versão escreve — a tabela, o manifesto e os relatórios da amostra
—, e só eles: o resto da pasta é seu. Pelos nomes, e não pelo manifesto da rodada,
porque ler um manifesto que pode ser de outra versão só para saber o que mover é
trocar uma regra simples por uma que falha. Do manifesto vem só o `desenho.yaml` de
então, e a falta dele não impede o arquivamento.

### `def _rodada_vigente(pasta)`

*linha 1332*

O manifesto da rodada que está no alto da pasta, quando há um legível e da amostragem.

Lido uma vez, para duas coisas que não são indispensáveis: o aviso de mudança e o
`desenho.yaml` de então. Por isso o manifesto quebrado ou de outra coisa não recusa
a rodada nova: ela sai sem o aviso e sem a cópia.

### `def _mudanca(anterior, tamanho)`

*linha 1349*

O aviso de quando o tamanho muda em relação à rodada vigente.

Um tamanho de amostra entregue ao cliente que muda em silêncio é o pior jeito de ele
mudar. A rodada anterior vai para as versões antigas de qualquer jeito — o aviso é
para você saber, antes de escrever, que o número que o cliente tem vai deixar de ser
o vigente.

### `def _acao_do_historico(plano)`

*linha 1372*

## `flatcap/cli.py`

`SPDX-FileCopyrightText: 2026 Matheus Fernandes` · `SPDX-License-Identifier: GPL-3.0-or-later`

*4231 linhas.*

Interface de linha de comando do FlatCap.

Esta camada não contém regras de negócio:
    ela lê argumentos, chama as camadas de baixo,
    formata a saída e escolhe o código de saída do processo.

- *linha 85* — `if TYPE_CHECKING:` — só para as anotações: ver o comentário em `perfil`

### `_AVISO_DE_LICENCA`

*linha 117*

> O aviso que a GPL pede que um programa mostre, no formato dos programas GNU. O
> titular dos direitos autorais é o mesmo do `NOTICE.md` e dos cabeçalhos SPDX.

### `def _versao(valor)`

*linha 128*

### `def _plural(quantidade, singular, plural)`

*linha 134*

Devolve o substantivo já concordado com o número.

### `def _abortar(titulo, mensagem)`

*linha 140*

Imprime o erro em um painel e devolve a exceção que encerra o comando.

`Text(...)` em vez de uma string crua:
    impede que colchetes vindos da mensagem
    de erro sejam interpretados como marcação do rich.

### `def _nada_a_fazer(mensagem)`

*linha 151*

Painel amarelo e saída com código 0: houve uma recusa, mas nada deu errado.

### `def _configuracao(env, criar_root)`

*linha 157*

Carrega a configuração ou encerra o comando com a mensagem do `config.py`.

### `def _rodada_escrita(frase, plano, resultado)`

*linha 166*

O que o comando de uma análise diz depois de escrevê-la.

As seis análises diziam a mesma coisa com seis cópias das mesmas linhas, e o
`analisar` diz o mesmo depois de cada uma do lote. Uma função só é o que impede
a sétima cópia — e a primeira a divergir das outras.

### `def principal(_)`

*linha 193*

Ponto de entrada. Existe para hospedar as opções globais.

### `def doctor(criar_root, criar_env, env)`

*linha 204*

Testar as credenciais, a conexão com o REDCap e a pasta de dados.
Responde se o problema está na configuração, na rede ou no token.

*linha 223*

> Como o `--criar-root`, não simula: criar é o pedido. E não sobrescreve
> nunca — o arquivo guarda o token, e um token perdido se pede de novo.

*linha 233*

> 1. Configuração

*linha 252*

> 2. Conexão com o REDCap

*linha 265*

> A instalação incompleta é diagnosticada **depois** da tabela inteira, e não
> no lugar dela: saber que a rede está de pé faz parte do diagnóstico mesmo
> quando falta biblioteca. O `doctor` é o comando que responde "o que está
> errado?" — ele não pode morrer no meio do próprio diagnóstico.

*linha 270*

> O `uv tool upgrade --reinstall` reinstala da origem guardada na instalação — o
> repositório. O `uv tool install --reinstall flatcap` procura o nome no PyPI, onde
> o FlatCap não está: falha, ou instala o pacote de quem registrar o nome. O
> `pipx reinstall` já usa a origem guardada.

### `def _criar_env_da_conta()`

*linha 286*

O `doctor --criar-env`: o `.env` de quem instalou o FlatCap por um pacote.

### `_BIBLIOTECAS`

*linha 317*

> As bibliotecas que abrem o banco, calculam, desenham e escrevem o documento.
> A ordem é a do fluxo: ler, calcular, desenhar, entregar.
>
> O `scipy` entrou na Fase 7 e é a primeira dependência nova desde a Fase 6. Ele
> está aqui pelo mesmo motivo que os outros quatro: uma biblioteca que falta
> precisa sair como `FALHA` nesta tabela, e não como `ModuleNotFoundError` no meio
> de um comando — foi assim que o `matplotlib` derrubou o `doctor` na Fase 5, no
> comando que existe justamente para responder "o que está errado?".

### `_NOME_NO_PIP`

*linha 327*

> `import docx` é o pacote `python-docx`, e o nome de instalação não é o nome de
> import. Quem lê "falta `docx`" no terminal vai procurar por `docx` no pip e
> instalar outro pacote — que existe, e não é este.

### `def _bibliotecas()`

*linha 333*

Quais versões abrem o banco, desenham os gráficos e escrevem o documento hoje.

Registrar isso no `doctor` é barato e evita a pergunta mais difícil de
responder da Fase 5: um gráfico saiu diferente do que saía antes — mudaram os
dados ou mudou a biblioteca? A resposta completa está no `manifesto.json` de
cada rodada; esta linha é a de agora, para comparar com ela.

Cada import é tentado por si, e a falta de uma não esconde as outras. Foi um
defeito real: numa máquina sem `matplotlib` o comando estourava com
`ModuleNotFoundError` em vez de dizer o que faltava — e escapou dos testes
porque a máquina que os roda é a única em que ele nunca falha.

### `def listar(ultimos, env, conferir_anexos)`

*linha 363*

Lista as solicitações no REDCap, e o que já foi para o disco.
    É o que coordena o fluxo diário de trabalho.
    Mostra o que chegou de novo de um lado e o que já virou pasta.

*linha 404*

> A busca no disco é feita **uma vez** por cliente e o resultado é passado
> adiante. A tabela e o resumo faziam a mesma varredura em separado, o que já
> era trabalho dobrado — e ficaria pior agora, que a busca desce dois níveis.

### `def _reconferir_anexos(cfg, clientes)`

*linha 415*

Confirma na API os anexos que o export de registros não declarou.

### `def _tabela_de_clientes(clientes, pastas)`

*linha 447*

Monta a tabela que sai do comando `listar`.
Valores que vêm do REDCap entram como `Text`, nunca como string crua:
    um nome com colchete viraria marcação do rich e sumiria da tela.

A coluna "Pasta local" responde **pelo projeto**, e não pelo cliente. É a
correção que a 1.1.0 obrigou e é o ponto em que ela se vê no dia a dia: até a
1.0.0 a pergunta era "esta matrícula já tem pasta?", e com um cliente podendo
ter vários trabalhos essa pergunta faria a segunda solicitação dele aparecer
como já atendida — e ela nunca viraria pasta, porque o `listar` é o comando
que diz o que ainda falta fazer.

*linha 476*

> Só o nome do projeto: a matrícula e o nome do cliente já têm coluna
> própria duas casas atrás, e repeti-los aqui espremeria a tabela inteira
> para dizer o que já está dito.

### `def _resumo(clientes, pastas, total)`

*linha 484*

Uma linha com o que exige atenção, para não ter que contar a tabela na mão.

### flatcap status

### `CORES_DO_STATUS`

*linha 522*

> A cor de cada status no `flatcap status`. O `finalizado` não tem cor porque não
> aparece. A cor ajuda o olho a separar as linhas, e só: o nome do status vai sempre
> escrito, porque quem recebe a saída sem cor — um e-mail, uma interface que a lê —
> precisa dele.
>
> Contra o fundo preto, as cinco passam do mínimo de 4,5:1 de contraste: 21, 11,7, 15,7,
> 6,4 e 9,5. O azul pedido primeiro, #4461d5, dava 3,9:1, e foi trocado pelo #5f87ff, que
> além disso é uma das 256 cores do xterm — sai igual nos terminais que não têm 24 bits.
> O ciano do `cálculo amostral`, #00d7d7, também é uma delas; num terminal de 16 cores,
> vira o ciano do tema, que nenhuma outra cor do painel usa, e continua distinto das
> outras quatro para quem tem daltonismo.

### `COR_DO_STATUS_FORA_DA_LISTA`

*linha 541*

> O status fora da lista. Era amarelo, a cor que a CLI usa para o que pede atenção,
> até o amarelo passar a ser o do `aguardando banco de dados`: os dois se confundiriam
> na mesma coluna.

### `def status_dos_projetos(env)`

*linha 550*

*linha 546*

> O nome da função não é o do comando, como no `dados_listar`: `status` é também o
> campo da ficha, e uma função com esse nome no módulo inteiro da CLI é um engano
> esperando para acontecer.

Mostra os projetos que já têm pasta, com o status e o prazo de cada um.
    Lê o projeto.yaml de cada projeto do FLATCAP_ROOT, sem falar com o REDCap e
    sem escrever nada. O prazo que passou sem o projeto estar pronto sai como
    ATRASADO, e os projetos finalizados não aparecem.

### `def _tabela_do_status(painel)`

*linha 578*

As quatro colunas do `listar` que dizem de quem é a pasta, e as duas que dizem
como o projeto está.

O significado vai escrito, e não só na cor: um painel copiado para um e-mail, ou
lido por um programa que recebe a saída sem as cores, continua dizendo ATRASADO.

Com uns 95 caracteres de largura, cada projeto cabe numa linha. Num terminal mais
estreito, o nome e o status quebram entre palavras, e o resto não quebra; o
`min_width` do nome impede que ele vire uma coluna de uma letra por linha.

### `def _celula_do_status(linha)`

*linha 611*

Um dos status do `projeto.STATUS`, na grafia de lá e na cor dele; o que não é
nenhum deles, como está escrito na ficha, em magenta.

### `def _celula_do_prazo(linha)`

*linha 621*

A data final, ou ATRASADO quando ela passou sem o projeto estar pronto.

### `def _resumo_do_status(painel)`

*linha 634*

Uma linha com o que exige atenção, como a do `listar`.

### `def _avisos_do_status(painel)`

*linha 663*

O que está no painel sem poder ser lido, e o que ficou fora dele — cada um com o
que fazer.

Um status ou um prazo que não se lê não tira o projeto do painel: ele aparece como
está escrito — o status em magenta, o prazo em amarelo —, e o aviso diz o que
escrever no lugar. A ficha que não abre e a pasta no formato antigo não têm como
aparecer na tabela, e aparecem aqui.

### `def novo(record_id, sim, env)`

*linha 736*

Cria a pasta do projeto a partir de uma solicitação do REDCap.
POR PADRÃO APENAS SIMULA:
    Desenha a árvore que seria criada e não escreve nada.
    Repita com --sim para executar.

### `def _cabecalho_do_plano(plano)`

*linha 812*

Uma linha identificando de quem é a solicitação, antes de desenhar a árvore.
Confirma que o `record_id` digitado é mesmo o cliente que você tinha em mente.

### `def _arvore_do_plano(cfg, plano)`

*linha 825*

Desenha exatamente o que `executar` criaria, lendo o próprio `Plano`.

Três níveis desde a 1.1.0, e a linha do cliente diz se ela é nova ou se já
estava lá. É a informação que a simulação passou a dever: "vou criar uma
pasta" e "vou acrescentar um projeto ao cliente que já tem dois" são coisas
diferentes, e só uma delas pede conferência antes do `--sim`.

### flatcap amostragem

### `def amostragem(identificador, titulo, template, sim, env)`

*linha 875*

Calcula o tamanho da amostra e escreve o relatório da amostra.

Vem depois do `flatcap novo`: o projeto precisa existir. Tudo da amostra mora
em `4. Amostragem/`, dentro da pasta do projeto.

A primeira rodada cria a pasta e o `desenho.yaml` — o plano da amostra, para
preencher à mão — e para. O modelo já vem com 95% de confiança, margem de 5
pontos e proporção esperada de 50%: o caso mais comum é preencher só a
`populacao` e rodar de novo.

As rodadas seguintes leem o `desenho.yaml`, fazem a conta e escrevem o
`tamanho.csv`, o `manifesto.json` e o relatório da amostra,
`Amostragem_<matrícula>_AAAA-MM-DD.docx`. Rodar de novo arquiva a rodada
anterior em `4. Amostragem/Versões antigas/`, com o `desenho.yaml` de então. O
`desenho.yaml` é seu: o FlatCap nunca o reescreve.

Por enquanto, um desenho: a aleatória simples, sem reposição. Não abre banco
e não fala com o REDCap.

POR PADRÃO APENAS SIMULA. Repita com --sim para escrever.

*linha 920*

> O `python-docx` entra só na execução, dentro do `executar_amostragem`. O
> `pandas` não entra nunca: a amostragem da v1 não abre banco.

### `def _cabecalho_da_amostragem(plano)`

*linha 1043*

Quem, e o que esta rodada faz: escrever o modelo, ou fazer a conta.

Na rodada da conta, o desenho, o modelo `.docx` e o título entram aqui pelo
motivo do `_cabecalho_do_relatorio`: sem eles, `--titulo` e `--template` só se
confeririam depois de executar.

### `def _modelo_do_desenho(plano)`

*linha 1085*

O `desenho.yaml` que a primeira rodada escreve, inteiro.

Inteiro, e não resumido: é um arquivo que você vai abrir e preencher, e a
simulação existe para mostrar o que seria gravado.

### `def _tabela_da_amostragem(amostragem)`

*linha 1099*

A conta, linha por linha, como sai no `tamanho.csv` e no documento.

A última linha é a resposta, e sai em destaque: quem procura o número procura
no fim.

### `def _arvore_da_amostragem(plano)`

*linha 1120*

Desenha o que `executar_amostragem` escreveria, lendo o próprio plano.

### flatcap dados

### `def dados_adicionar(identificador, caminho, sim, env)`

*linha 1171*

Registra uma nova versão do banco na pasta do projeto.

Copia o arquivo para `1. Dados originais/` com o próximo número da série,
manda a versão de trabalho anterior para `2. Versões antigas/` e acrescenta a
entrada em `dados:` no projeto.yaml. O `00_redcap_*` nunca é tocado.

POR PADRÃO APENAS SIMULA. Repita com --sim para executar.

### `def dados_listar(identificador, rapido, env)`

*linha 1249*

Mostra a linha do tempo das versões do banco de um projeto.

Além do que está registrado em `dados:`, confronta a ficha com o disco: aponta
versão registrada que sumiu, arquivo alterado depois do registro e arquivo
presente na pasta que a ficha desconhece.

### `def _cabecalho_dos_dados(plano)`

*linha 1297*

### `def _cabecalho_da_ficha(tempo)`

*linha 1306*

### `def _arvore_da_adicao(plano)`

*linha 1316*

Desenha o que `executar_adicao` faria, lendo o próprio plano.

### `def _tabela_da_linha_do_tempo(tempo)`

*linha 1365*

A cronologia. Nomes de arquivo entram como `Text` pelo mesmo motivo de sempre.

### `def _divergencias(tempo)`

*linha 1409*

As três formas de a ficha e o disco discordarem, cada uma com o que fazer.

### flatcap perfil

### `def perfil(identificador, aba, rapido, sim, env)`

*linha 1470*

Descreve o banco e prepara a reunião com o cliente.

Abre a versão vigente registrada na ficha, mede cada variável, aponta os
problemas conhecidos e escreve dois arquivos na pasta do projeto: o `perfil.md`,
que é o documento que você leva para a conversa, e o `dicionario.csv`, que dirige
a descritiva daqui em diante.

O dicionário que já existir não é sobrescrito: as linhas que você preencheu
ficam intactas, e só entram as variáveis novas.

POR PADRÃO APENAS SIMULA. Repita com --sim para escrever.

*linha 1505*

> O `pandas` sai de dentro deste import e não do topo do arquivo: ele custa uns
> 0,4 s para carregar, contra 0,08 s do typer com o rich. O `listar`, que roda
> várias vezes por dia e não abre banco nenhum, não deve pagar por isso.

### `def _cabecalho_do_perfil(perfil)`

*linha 1564*

Quem, qual arquivo, e se dá para confiar nele. Nessa ordem.

*linha 1589*

> As colunas que o leitor converteu: é uma decisão dele, e decisão do leitor
> sai escrita, como o separador e a codificação. Ver o `banco.py`.

### `def _tabela_do_perfil(perfil)`

*linha 1609*

Uma linha por variável. Valores do banco entram como `Text`, nunca como string
crua, pelo mesmo motivo do `listar`.

### `def _achados_no_terminal(perfil)`

*linha 1645*

Os achados agrupados pelo que fazer com eles, do mais urgente para o menos.

### `def _lista_de_achados(achados)`

*linha 1682*

### `def _arvore_do_perfil(plano)`

*linha 1697*

Desenha o que `executar_perfil` escreveria, lendo o próprio plano.

### flatcap descritiva

### `def descritiva(identificador, aba, sem_graficos, rapido, sim, env)`

*linha 1736*

Gera a análise descritiva obedecendo ao dicionario.csv.

Uma tabela de frequência e um gráfico de barras por categórica; resumo, tabela
por faixas e histograma por numérica; período e distribuição no tempo por data.
Tudo em `3. Análises/descritiva/`, com um `manifesto.json` que diz de qual
variável saiu cada arquivo.

Sem `faixas` preenchida no dicionário, as faixas saem pelos quartis da própria
variável. Numérica que chegou como texto faz o comando recusar: o caminho é
pedir a correção ao cliente e registrar a versão nova com `dados adicionar`.

Rodar de novo arquiva a rodada anterior inteira em `2. Versões antigas/`.

POR PADRÃO APENAS SIMULA. Repita com --sim para escrever.

*linha 1778*

> Mesmo motivo do `perfil`: o `pandas` custa perto de meio segundo para
> carregar e o `matplotlib` outro tanto. O `listar`, que roda várias vezes por
> dia, não deve pagar por um comando que ele não usa.

### `def _mostrar_descritiva(plano)`

*linha 1829*

O que a descritiva mostra antes de escrever — no comando dela e no `analisar`.

Uma função, e não as mesmas linhas nos dois comandos: a simulação do lote é a
soma das simulações das análises, e duas cópias da mesma sequência é como uma
delas esquece o painel `Fora da descritiva` na próxima mudança. As cinco
análises seguintes têm a sua `_mostrar_*` pelo mesmo motivo.

### `def _cabecalho_da_descritiva(plano)`

*linha 1847*

Quem, qual banco, se dá para confiar nele, e quanto do dicionário entra.

### `def _tabela_da_descritiva(descritiva)`

*linha 1891*

Uma linha por variável, com os arquivos que ela gera.

A coluna dos arquivos é a que importa: é o `manifesto.json` na tela, e é o que
responde "de qual variável saiu este .csv?" antes de o .csv existir.

### `def _fora_da_descritiva(descritiva)`

*linha 1928*

As variáveis que não geraram artefato, e por quê.

Aparecem na tela pelo mesmo motivo que aparecem no manifesto: "não está no
relatório" e "ninguém reparou que ela existia" são coisas diferentes.

### `def _arvore_da_descritiva(plano)`

*linha 1954*

Desenha o que `executar_descritiva` escreveria, lendo o próprio plano.

### flatcap normalidade

### `def normalidade(identificador, aba, sem_graficos, rapido, sim, env)`

*linha 2009*

Testa a normalidade das variáveis numéricas do dicionario.csv.

Para cada `numerica`: o teste de Shapiro-Wilk, a assimetria, a curtose e um
gráfico Q-Q. Tudo em `3. Análises/normalidade/`, com um `manifesto.json`.

Sai uma tabela só, com uma linha por variável — é como uma tabela de
pressupostos se lê. O valor-p **depende do tamanho da amostra**: com poucos
casos o teste quase não rejeita, e com muitos rejeita desvios irrelevantes. Por
isso a assimetria, a curtose e o Q-Q saem ao lado dele, e não no lugar dele.

Por padrão entram todas as numéricas. Uma lista `normalidade:` no projeto.yaml
restringe às variáveis que você escrever nela.

Rodar de novo arquiva a rodada anterior inteira em `2. Versões antigas/`.

POR PADRÃO APENAS SIMULA. Repita com --sim para escrever.

*linha 2053*

> Mesmo motivo do `perfil` e da `descritiva`: `pandas`, `scipy` e `matplotlib`
> custam perto de um segundo somados, e o `listar`, que roda várias vezes por
> dia, não deve pagar por um comando que ele não usa.

### `def _mostrar_normalidade(plano)`

*linha 2104*

O que a normalidade mostra antes de escrever — no comando dela e no `analisar`.

### `def _cabecalho_da_normalidade(plano)`

*linha 2118*

Quem, qual banco, se dá para confiar nele, e quantas variáveis entram.

### `def _tabela_da_normalidade(normalidade)`

*linha 2164*

Uma linha por variável, na mesma ordem e com os mesmos números do `.csv`.

O `n` vem antes de tudo de propósito: ele é o que calibra a leitura do valor-p,
e uma tabela que o escondesse deixaria a coluna `p` parecer uma resposta. Pelo
mesmo motivo a assimetria e a curtose vêm **antes** do W e do p, e não depois:
elas medem o tamanho do desvio e não mudam com o tamanho da amostra.

*linha 2184*

> A tabela do terminal lê as mesmas células do `.csv` que vai para o disco, e
> não reformata número nenhum: dois formatadores para a mesma grandeza é como
> o terminal passa a dizer `0.05` enquanto o arquivo diz `0,05`.

### `def _nota_da_normalidade(normalidade)`

*linha 2213*

A frase que impede a tabela de ser lida como um veredito.

Ela sai sempre, inclusive quando nada foi rejeitado, e é a mesma coisa que a nota
do `.csv` diz. O terminal é onde você olha a tabela pela primeira vez, e é aí que
a advertência serve para alguma coisa — depois de o documento estar pronto, ela
vira leitura de conferência.

### `def _fora_da_normalidade(normalidade)`

*linha 2261*

As variáveis que não entraram, e por quê.

Aparecem pelo mesmo motivo da Fase 5, e aqui elas são quase todo o dicionário:
categórica, data e `ignorar` não têm normalidade a testar. Um painel `dim` com a
lista é o que impede a pergunta "por que `sexo` não está na tabela?".

### `def _arvore_da_normalidade(plano)`

*linha 2288*

Desenha o que `executar_normalidade` escreveria, lendo o próprio plano.

### flatcap cruzamento

### `def cruzamento(identificador, aba, rapido, sim, env)`

*linha 2349*

Cruza pares de variáveis categóricas: uma tabela por par.

Para cada par da lista `cruzamento:` do projeto.yaml, uma tabela com cada
combinação de categorias, quantos casos e o percentual sobre quem respondeu as
duas. Quem não respondeu uma delas sai numa linha própria, e o Total é o do
banco — o mesmo das tabelas de frequência. Tudo em `3. Análises/cruzamento/`,
com um `manifesto.json`.

Os pares se escrevem na ficha, um por linha:

    cruzamento:
      - \[sexo, escolaridade]

As duas variáveis precisam estar marcadas `categorica` no dicionario.csv —
inclusive uma numérica de poucos valores, como uma escala de 0 a 5.

Rodar de novo arquiva a rodada anterior inteira em `2. Versões antigas/`.

POR PADRÃO APENAS SIMULA. Repita com --sim para escrever.

*linha 2392*

> O `pandas` entra aqui dentro, como em todo comando que abre o banco: o
> `listar`, que roda várias vezes por dia, não deve pagar por ele.

### `def _mostrar_cruzamento(plano)`

*linha 2436*

O que o cruzamento mostra antes de escrever — no comando dele e no `analisar`.

### `def _cabecalho_do_cruzamento(plano)`

*linha 2448*

Quem, qual banco, se dá para confiar nele, e quantos pares entram.

### `def _tabela_do_cruzamento(par)`

*linha 2490*

A tabela de um par, com as mesmas células do `.csv`.

Inteira, e não um resumo por par como o da descritiva: a tabela é o produto
deste comando, e a simulação existe para você ler o que vai para o documento
antes de escrevê-lo. A linha do `Total` em negrito e a `(sem informação)`
apagada são as mesmas marcas que o `.docx` vai dar a elas.

*linha 2501*

> `Text` no título e nos cabeçalhos, e não a string: são rótulos do
> dicionário, e um `Idade [anos]` perderia o colchete como marcação do rich —
> o cuidado que o `_abortar` já toma com as mensagens de erro.

### `def _arvore_do_cruzamento(plano)`

*linha 2524*

Desenha o que `executar_cruzamento` escreveria, lendo o próprio plano.

### flatcap associacao

### `def associacao(identificador, aba, rapido, sim, env)`

*linha 2568*

Testa a associação entre pares de variáveis categóricas.

Para cada par da lista `associacao:` do projeto.yaml, o teste que a regra de
Cochran escolhe: qui-quadrado quando nenhuma frequência esperada é menor que 1
e no máximo 20% das caselas têm esperada menor que 5 — com a correção de Yates
nas tabelas 2×2 —, e exato de Fisher nos outros casos. Os dois como o R faz.
Sai uma tabela só, com variável 1, variável 2, n, teste, p-valor e o V de
Cramér — o tamanho da associação, de 0 a 1 —, em `3. Análises/associacao/`,
com um `manifesto.json`.

Os pares se escrevem na ficha — um par, ou uma variável contra várias:

    associacao:
      - \[sexo, desfecho]
      - desfecho: \[sexo, escolaridade, tabagismo]

As variáveis precisam estar marcadas `categorica` no dicionario.csv —
inclusive uma numérica de poucos valores, como uma escala de 0 a 5.

Rodar de novo arquiva a rodada anterior inteira em `2. Versões antigas/`.

POR PADRÃO APENAS SIMULA. Repita com --sim para escrever.

*linha 2614*

> O `pandas` e o `scipy` entram aqui dentro, como em todo comando que abre o
> banco: o `listar`, que roda várias vezes por dia, não deve pagar por eles.

### `def _mostrar_associacao(plano)`

*linha 2658*

O que a associação mostra antes de escrever — no comando dela e no `analisar`.

### `def _cabecalho_da_associacao(plano)`

*linha 2670*

Quem, qual banco, se dá para confiar nele, e quantos pares entram.

### `def _tabela_da_associacao(associacao)`

*linha 2712*

Uma linha por par, com as mesmas células do `.csv`.

A tabela do terminal lê as células que vão para o disco e não reformata nada —
dois formatadores para o mesmo p é como o terminal diz `0.042` enquanto o
arquivo diz `0,042`. O p abaixo de 0,05 sai em negrito: é o destaque de quem
lê a simulação, e ele fica no terminal — o documento não marca nada.

- *linha 2725* — `if posicao in (2, 4, 5):` — n, p-valor e V: números, à direita

### `def _nota_da_associacao(associacao)`

*linha 2748*

Por que cada par foi para o teste em que foi, e quantos testes são.

As frases são as mesmas das notas do `.csv` — uma por par, montadas num lugar
só —, e saem na simulação porque é nela que se confere a escolha antes de ela
ir para o documento.

### `def _arvore_da_associacao(plano)`

*linha 2785*

Desenha o que `executar_associacao` escreveria, lendo o próprio plano.

### flatcap correlacao

### `def correlacao(identificador, aba, sem_graficos, rapido, sim, env)`

*linha 2828*

Correlaciona pares de variáveis: Pearson, Spearman ou Kendall.

Para cada par da lista `correlacao:` do projeto.yaml, o método que a regra dos
pressupostos escolhe: Kendall quando alguma das duas tem até 10 valores
distintos, com repetição (escala ou código); Spearman quando alguma é
categórica ou quando o Shapiro-Wilk rejeita a normal em alguma das duas; e
Pearson nos outros casos. Os três como o cor.test do R. Sai uma tabela só, com
variável 1, variável 2, n, método, coeficiente, IC 95% e p-valor, e uma
dispersão por par, em `3. Análises/correlacao/`, com um `manifesto.json`.

Os pares se escrevem na ficha — um par, um par com o método, ou uma variável
contra várias:

    correlacao:
      - \[idade, imc]
      - idade: \[pressao, colesterol]
      - \[dor, ansiedade, kendall]

O terceiro nome do par, quando vem, manda no método: pearson, spearman ou
kendall. Uma escala marcada `categorica` entra se o código for número — pela
ordem dos códigos, e só por Spearman ou Kendall.

Rodar de novo arquiva a rodada anterior inteira em `2. Versões antigas/`.

POR PADRÃO APENAS SIMULA. Repita com --sim para escrever.

*linha 2881*

> O `pandas`, o `scipy` e o `matplotlib` entram aqui dentro, como em todo
> comando que abre o banco: o `listar`, que roda várias vezes por dia, não deve
> pagar por eles.

### `def _mostrar_correlacao(plano)`

*linha 2928*

O que a correlação mostra antes de escrever — no comando dela e no `analisar`.

### `def _cabecalho_da_correlacao(plano)`

*linha 2940*

Quem, qual banco, se dá para confiar nele, e quantos pares entram.

### `def _tabela_da_correlacao(correlacao)`

*linha 2982*

Uma linha por par, com as mesmas células do `.csv`.

A tabela do terminal lê as células que vão para o disco e não reformata nada —
dois formatadores para o mesmo coeficiente é como o terminal diz `0.31` enquanto
o arquivo diz `0,31`. O p abaixo de 0,05 sai em negrito, e o método escrito na
ficha contra a regra sai em amarelo: são destaques de quem lê a simulação, e
ficam no terminal — o documento não marca nada.

- *linha 2996* — `if posicao in (2, 4, 5, 6):` — n, coeficiente, IC e p-valor: números, à direita

### `def _nota_da_correlacao(correlacao)`

*linha 3021*

Por que cada par foi para o método em que foi, e quantos testes são.

As frases são as mesmas das notas do `.csv` — uma por par, montadas num lugar
só —, e saem na simulação porque é nela que se confere a escolha antes de ela
ir para o documento. Quando a ficha escolheu contra a regra, a frase diz o que
a regra teria escolhido.

### `def _arvore_da_correlacao(plano)`

*linha 3065*

Desenha o que `executar_correlacao` escreveria, lendo o próprio plano.

### flatcap comparacao

### `def comparacao(identificador, aba, rapido, sim, env)`

*linha 3123*

Compara: contra um valor de referência, entre grupos ou entre medidas.

Para cada item da lista `comparacao:` do projeto.yaml, o teste que a regra dos
pressupostos escolhe: o paramétrico quando o Shapiro-Wilk não rejeita a normal, e o
de postos quando rejeita. Contra um valor de referência, o t de Student para uma
amostra, ou o Wilcoxon. Entre os dois grupos de uma variável categórica, o t de
Welch — o padrão do t.test —, ou o Mann-Whitney; o t de Student roda quando está
escrito no item. Entre três grupos ou mais, a ANOVA de Welch — o padrão do
oneway.test —, ou o Kruskal-Wallis; a clássica roda quando está escrita no item. Nas
medidas repetidas — a mesma medida, três vezes ou mais, nos mesmos casos —, a ANOVA
de medidas repetidas, sempre com a correção de Greenhouse-Geisser, ou o Friedman.
Todos como o R os calcula; o Wilcoxon e o Mann-Whitney com o intervalo de
Hodges-Lehmann. Sai uma tabela por delineamento em `3. Análises/comparacao/`, com um
`manifesto.json`.

Os itens se escrevem na ficha — a variável e a referência, com ponto decimal; a
variável e a de grupo; ou as medidas repetidas, com a marca:

    comparacao:
      - \[imc, 25]
      - \[pas, 120, t]
      - \[imc, sexo]
      - repetidas: \[pas_0, pas_1, pas_2]

O terceiro nome, quando vem, manda no teste: `t` roda o t mesmo contra a regra, e
`wilcoxon`, `mannwhitney` ou `kruskal`, o de postos. Nas medidas repetidas, o método
vem na chave `metodo:`, na linha de baixo — `anova` ou `friedman`.

Rodar de novo arquiva a rodada anterior inteira em `2. Versões antigas/`.

POR PADRÃO APENAS SIMULA. Repita com --sim para escrever.

*linha 3178*

> O `pandas` e o `scipy` entram aqui dentro, como em todo comando que abre o
> banco: o `listar`, que roda várias vezes por dia, não deve pagar por eles.

### `def _mostrar_comparacao(plano)`

*linha 3222*

O que a comparação mostra antes de escrever — no comando dela e no `analisar`.

### `def _cabecalho_da_comparacao(plano)`

*linha 3235*

Quem, qual banco, se dá para confiar nele, e quantos itens entram.

### `def _tabelas_da_comparacao(comparacao)`

*linha 3277*

Uma tabela por delineamento, com as mesmas células do `.csv`.

A tabela do terminal lê as células que vão para o disco e não reformata nada —
dois formatadores para a mesma média é como o terminal diz `25.93` enquanto o
arquivo diz `25,93`. As linhas de cada item saem da mesma `linhas_da_tabela` que
monta o arquivo: uma na uma amostra, o bloco da comparação e dos grupos entre
grupos.

O p abaixo de 0,05 sai em negrito, e a linha sem teste ou com o método escrito
contra a regra sai com a coluna `teste` em amarelo: são destaques de quem lê a
simulação, e ficam no terminal — o documento não marca nada.

*linha 3294*

> n, referência e p-valor: números, à direita. Pelo nome, e não pela posição —
> cada delineamento tem as suas colunas.

### `def _nota_da_comparacao(comparacao)`

*linha 3338*

Por que cada item foi para o teste em que foi, e quantos testes são.

As frases são as mesmas das notas do `.csv` — uma por item, montadas num lugar
só —, e saem na simulação porque é nela que se confere a escolha antes de ela ir
para o documento. Quando a ficha escolheu contra a regra, ou quando a regra
escolheu um teste que ainda não existe, a frase sai em amarelo.

### `def _arvore_da_comparacao(plano)`

*linha 3378*

Desenha o que `executar_comparacao` escreveria, lendo o próprio plano.

### flatcap analisar

### `class _Tela`

*linha 3426*

O que o terminal sabe de uma análise: como mostrá-la antes de escrever, a frase
de depois de escrita e a linha dela na tabela do lote.

### `def _sem_teste(quantos)`

*linha 3437*

### `def _resumo_da_descritiva(plano)`

*linha 3441*

### `def _resumo_da_normalidade(plano)`

*linha 3448*

### `def _resumo_do_cruzamento(plano)`

*linha 3456*

### `def _resumo_da_associacao(plano)`

*linha 3461*

### `def _resumo_da_correlacao(plano)`

*linha 3469*

### `def _resumo_da_comparacao(plano)`

*linha 3477*

### `_NA_TELA`

*linha 3485*

> Pelo nome da análise, o mesmo do `analises.REGISTRO` — e há teste que exige os dois
> iguais: uma análise que o lote rodasse sem estar aqui seria uma análise que ele não
> saberia mostrar. As funções `_mostrar_*` são as que o comando de cada análise chama,
> e a frase é a mesma que ele diz: o lote é a soma dos comandos também na tela.

### `def analisar(identificador, aba, sem_graficos, rapido, resumo, sim, env)`

*linha 3512*

Roda, de uma vez, as análises da lista `analises:` do projeto.yaml.

Na ordem da lista, que é também a ordem das seções do relatório. Cada análise
roda como o comando dela: a mesma saída no terminal, os mesmos arquivos em
`3. Análises/`, a mesma linha no `historico.md`. No fim, uma tabela com uma
linha por análise.

A lista se escreve na ficha, com os nomes das análises:

    analises: \[descritiva, normalidade, correlacao, comparacao]

Os pares e os itens continuam nos blocos de cada análise — `correlacao:`,
`comparacao:`. Lista vazia faz o comando recusar: ele obedece à ficha, e não
escolhe análise nenhuma.

Todas são preparadas antes de qualquer uma ser escrita. Se uma recusar, nada é
escrito nem arquivado, e as recusas saem todas juntas. O relatório fica de
fora: leia as tabelas e rode `flatcap relatorio` depois.

Para rodar uma análise só, o comando dela continua valendo.

POR PADRÃO APENAS SIMULA. Repita com --sim para escrever.

*linha 3567*

> O `analises.py` não traz o `pandas`; quem traz é cada análise, no `preparar_*`
> dela. O import fica aqui dentro pelo mesmo motivo dos outros comandos.

*linha 3594*

> Um painel por recusa, com o título da análise — o mesmo painel que o
> comando dela abriria —, e o fecho do lote por último.

#### `def ao_escrever(feita)`

*linha 3633*

*linha 3645*

> Ctrl+C no meio do lote. O `click` diria só «Aborted!», e aqui a pergunta
> que sobra é qual análise ficou escrita e qual ficou pela metade — a mesma
> frase que acabou de ir para o `historico.md`.

### `def _notas(erro)`

*linha 3670*

As notas que o `executar_analises` prende ao erro: onde o lote parou.

### `def _regua_da_etapa(posicao, total, etapa)`

*linha 3677*

A linha que abre a saída de cada análise, com a posição dela no lote.

### `def _cabecalho_do_lote(plano)`

*linha 3688*

Quem, qual banco, se dá para confiar nele, e quantas análises a lista pede.

O banco é o de todas: cada análise o abriu por conta própria, e todas abriram a
versão vigente da ficha.

### `def _tabela_do_lote(plano)`

*linha 3732*

Uma linha por análise, na ordem da lista: o que entra nela, quantos arquivos, e
se a rodada é a primeira ou refaz uma anterior.

«Sem teste» aparece aqui porque é o que se procura primeiro depois de uma
simulação longa: a linha que a regra escolheu e o FlatCap ainda não calcula, ou o
par que não tinha casos para o teste.

### `def _avisos_das_etapas(plano)`

*linha 3760*

Os avisos de cada análise, para o `--resumo`, que não mostra a saída delas.

Os do banco saem uma vez só: toda análise os repete no começo da lista dela, e
seis cópias do mesmo aviso de leitura esconderiam o que é de cada uma.

### `def _arvore_do_lote(plano)`

*linha 3781*

Desenha o que `executar_analises` escreveria, lendo o próprio plano.

As pastas, e não os arquivos: os arquivos de cada análise estão na árvore dela,
logo acima. Aqui é o lote inteiro de uma vez — o que vai para
`2. Versões antigas/` e o que nasce ou se refaz em `3. Análises/`.

### flatcap relatorio

### `def relatorio(identificador, template, titulo, rapido, sim, env)`

*linha 3827*

Monta o relatório .docx a partir das análises já rodadas.

Varre `3. Análises/`, lê o `manifesto.json` de cada rodada que estiver lá e
monta um documento com as seções de todas elas, cada uma com as tabelas e as
figuras que a análise escreveu. A descritiva dá uma seção por variável, na
ordem do dicionário; o cruzamento, uma seção por par; a normalidade, a
tabela de pressupostos e os Q-Q. As notas dos `.csv` ficam nos `.csv`.

A ordem das análises é a da lista `analises:` do `projeto.yaml` — o que foi
combinado na reunião. O que não estiver na lista entra depois, e o que
estiver na lista sem rodada no disco vira um aviso aqui no terminal.

Não abre o banco e não recalcula nada: os números do documento são, letra
por letra, os dos `.csv` que estão em `3. Análises/`.

O documento sai na raiz da pasta do projeto como
`Relatorio_<matrícula>_AAAA-MM-DD.docx`, e o relatório anterior vai para
`2. Versões antigas/`.

Quando uma rodada já não descreve o que está na pasta — banco novo, arquivo
alterado, dicionário mexido — o documento é gerado assim mesmo, com o aviso
escrito dentro dele.

Escrito o documento, o `status:` do projeto.yaml passa para `pronto`.

POR PADRÃO APENAS SIMULA. Repita com --sim para escrever.

*linha 3882*

> Nem `pandas` nem `matplotlib` entram neste comando: o relatório lê os
> manifestos e os `.csv` das rodadas, e é só isso. O `python-docx` entra só
> na execução, dentro do `executar_relatorio`.

### `def template(saida, sim, env)`

*linha 3968*

Escreve o modelo .docx que o relatório usa, para você ajustar no Word.

O modelo sai com o corpo vazio e com os seis estilos `FlatCap Titulo`,
`FlatCap Subtitulo`, `FlatCap Secao`, `FlatCap Corpo`, `FlatCap Legenda` e
`FlatCap Tabela` já definidos. Ajuste-os no Word — fonte, cor, tamanho —,
ponha o logotipo no cabeçalho e salve. Todo relatório gerado daí em diante
sai com essa cara, sem uma linha de Python.

Tudo o que você escrever no corpo do modelo aparece **antes** do relatório, em
todo relatório. É assim que uma capa institucional continua sendo a capa.

POR PADRÃO APENAS SIMULA. Repita com --sim para escrever.

### `def _cabecalho_do_relatorio(plano)`

*linha 4040*

Quem, de quais análises, sobre qual banco, com qual modelo e qual título.

As análises entram nomeadas e na ordem em que saem no documento, porque é
aqui que se descobre — antes de abrir o `.docx` — que a normalidade não
entrou porque ninguém a rodou.

O título entra pelo mesmo motivo: sem ele, `--titulo` só se conferia depois
de executar, que é exatamente o que a simulação existe para evitar.

### `def _tabela_do_relatorio(relatorio)`

*linha 4081*

Uma linha por seção do documento, com os arquivos que entram nela.

É a mesma coluna de arquivos da descritiva, e serve para a mesma conferência:
saber de qual variável saiu cada tabela **antes** de abrir o documento.

A coluna `Análise` entrou quando a pasta passou a ter mais de uma rodada: a
pergunta deixou de ser «o que entrou?» e passou a ser «o que entrou, e de
qual rodada?». O nome aparece uma vez por bloco, e não repetido em toda
linha — o que se lê na tela é onde uma análise acaba e a outra começa.

*linha 4102*

> `rodadas` vazio é o `Relatorio` montado à mão — em teste, ou por uma
> camada de cima que não passou pela varredura. A tabela continua saindo,
> sem o nome da análise, em vez de sair vazia.

### `def _alertas_no_terminal(relatorio)`

*linha 4139*

Os avisos que também vão para dentro do documento.

Aparecem aqui **e** lá de propósito: o terminal você vê agora, o documento é o
que sobra depois de o arquivo ser anexado a um e-mail.

### `def _fora_do_relatorio(relatorio)`

*linha 4166*

As variáveis que **nenhuma** análise descreveu, e por quê.

Nenhuma, e não «a descritiva»: a lista `fora` da normalidade tem toda
categórica do banco, e imprimi-la aqui diria que `sexo` ficou de fora do
documento logo acima da linha da seção `Sexo`. Quem faz essa conta é o
`relatorio._variaveis_de_fora`.

Não entram no `.docx` — são diagnóstico seu, não conteúdo do cliente —, mas
aparecem aqui pelo mesmo motivo da Fase 5: "não está no relatório" e "ninguém
reparou que ela existia" são coisas diferentes.

### `def _arvore_do_relatorio(plano)`

*linha 4198*

Desenha o que `executar_relatorio` escreveria, lendo o próprio plano.

## `flatcap/__main__.py`

`SPDX-FileCopyrightText: 2026 Matheus Fernandes` · `SPDX-License-Identifier: GPL-3.0-or-later`

*13 linhas.*

Permite rodar `python -m flatcap` sem depender do executável instalado.

Útil quando o .venv não está ativado ou quando algo deu errado com o entry point
declarado no pyproject.toml.
