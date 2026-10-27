# FlatCap

Ferramenta de linha de comando para o fluxo de trabalho de um serviço de assessoria
estatística que recebe as solicitações pelo REDCap:

**REDCap (entrada) → organização de pastas → versionamento dos bancos → análises → relatório `.docx`**

> **In English.** FlatCap is a command-line tool that automates the routine of a statistical
> consulting service whose requests arrive through a REDCap survey: it creates one folder per
> client and project, computes sample sizes for simple random sampling, versions the client's
> datasets, profiles them, runs descriptive and
> inferential analyses (normality, cross-tabulation, chi-square/Fisher, Pearson/Spearman/Kendall,
> t-tests, ANOVAs and the rank-based Wilcoxon, Mann-Whitney, Kruskal-Wallis and Friedman tests)
> checked against R, and writes a `.docx` report. Code, messages and documentation are in
> Brazilian Portuguese. Licensed under GPL-3.0-or-later.

## Princípio

Automatizar o que é repetitivo e mecânico, e manter manual o que é decisão técnica. Tudo o
que é automatizado fica documentado em disco, para que qualquer projeto possa ser reaberto
meses depois e compreendido sem depender da memória. Nada é apagado: as versões antigas vão
para uma pasta própria dentro do projeto.

- **Simula por padrão.** Todo comando que escreve em disco primeiro mostra o que faria;
  `--sim` executa.
- **O que se analisa está escrito.** As decisões da reunião com o cliente moram no
  `dicionario.csv` e no `projeto.yaml` do projeto, e as análises obedecem a eles; o plano da
  amostra, no `desenho.yaml`.
- **Conferido contra o R.** Os testes estatísticos reproduzem o R 4.3.3, e a suíte compara
  com valores calculados no R — nunca com o próprio FlatCap.
- **O relatório não abre o banco.** Um número do `.docx` é, letra por letra, o número do
  `.csv` que a análise escreveu.

A documentação completa — o projeto inteiro, módulo por módulo, com todos os comentários do
código — está em [`docs/Doc.Flatcap.md`](docs/Doc.Flatcap.md).

> O FlatCap não é afiliado à Vanderbilt University nem ao REDCap Consortium. Ele só conversa
> com a API do servidor REDCap da sua instituição, com o token que ela concede.

---

## Instalação

Requer **Python 3.11 ou mais novo** e o [Git](https://git-scm.com/downloads). O FlatCap é um
programa de terminal, e o jeito recomendado de instalá-lo é como uma ferramenta isolada — com
o [`uv`](https://docs.astral.sh/uv/) ou com o [`pipx`](https://pipx.pypa.io) —, direto do
repositório e sem cloná-lo: o código é baixado, instalado e descartado. O `uv` baixa até o
Python, se a máquina não tiver.

```bash
# com o uv
uv tool install git+https://github.com/MatheusEstatistico/flatcap

# ou com o pipx
pipx install git+https://github.com/MatheusEstatistico/flatcap
```

Para atualizar para o que estiver no `main`: `uv tool upgrade flatcap` ou
`pipx upgrade flatcap`. Para desinstalar: `uv tool uninstall flatcap` ou
`pipx uninstall flatcap`.

### Para desenvolver

```bash
git clone https://github.com/MatheusEstatistico/flatcap.git
cd flatcap
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pre-commit install
```

O ritual de cada mudança está no [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Configuração

O FlatCap precisa de três chaves, lidas de um arquivo `.env`:

| Chave | O que é, e onde obter |
|---|---|
| `REDCAP_API_URL` | A URL da API, no formato `https://<servidor>/redcap/api/`. Está na página **API Playground** do projeto. **Não** é o link curto do survey. |
| `REDCAP_TOKEN` | O token do projeto, no menu **API** → *Request API token*. Precisa de permissão para exportar **registros, metadados e arquivos**. |
| `FLATCAP_ROOT` | O caminho absoluto da pasta onde ficam as pastas dos clientes — fora de qualquer repositório Git, porque é onde moram os dados. |

O `.env` é procurado nesta ordem, e o primeiro que existir é o lido:

1. o arquivo indicado com `--env CAMINHO`, que todo comando aceita;
2. um `.env` na pasta atual ou em alguma acima dela — o de quem trabalha num clone do
   repositório;
3. o `.env` da sua conta — o de quem instalou o FlatCap como ferramenta:
   `%APPDATA%\flatcap\.env` no Windows, `~/.config/flatcap/.env` no Linux e
   `~/Library/Application Support/flatcap/.env` no macOS.

Para criar o da sua conta, com as três chaves em branco, e conferir tudo depois de
preenchê-lo:

```bash
flatcap doctor --criar-env
flatcap doctor
```

Variáveis de ambiente com os mesmos nomes valem mais que o `.env` — é o que permite rodar num
servidor sem arquivo nenhum. **O `.env` guarda o token: ele nunca vai para o Git.** Se um token
vazar, troque-o no REDCap; ver o [`SECURITY.md`](SECURITY.md).

## O formulário do REDCap

O FlatCap foi feito para um formulário de solicitação de análise, e lê dele estes campos
(`modelo.CAMPOS_REDCAP`):

| Campo | Tipo no REDCap | Para quê |
|---|---|---|
| `record_id` | — | identifica a solicitação; vira a pasta `Projeto NNN` |
| `intro` | radio: `1` professor/colaborador, `2` aluno | decide de quais campos vêm a matrícula e o nome |
| `matricula1`, `prof1` | texto | matrícula e nome do professor (`intro = 1`) |
| `matricula2`, `aluno2` | texto | matrícula e nome do aluno (`intro = 2`) |
| `fin` | radio | a finalidade, impressa na primeira página do relatório |
| `outros1` | texto | a finalidade escrita pelo cliente quando ele marca "Outros" |
| `obj1` | texto longo | os objetivos do estudo, também impressos no relatório |
| `database` | arquivo | o banco de dados, baixado pelo `flatcap novo` |

Um formulário com esses nomes funciona sem mudar nada no código. O dicionário de dados de um
formulário mínimo, pronto para importar no REDCap (*Designer → Upload Data Dictionary*), está
em [`docs/redcap/formulario-minimo.csv`](docs/redcap/formulario-minimo.csv). Para usar outros
nomes de campo, a tradução mora num lugar só: o `src/flatcap/modelo.py`.

---

## Comandos

Ajuda de qualquer comando: `flatcap <comando> --help`. O `<id>` é o `record_id` **ou** a
matrícula do projeto, como aparece no `flatcap listar`.

| Comando | Função |
|---|---|
| `flatcap doctor` | Testa a configuração, a conexão com o REDCap, o `FLATCAP_ROOT` e as bibliotecas. |
| `flatcap listar` | Lista as solicitações do REDCap e diz quais já viraram pasta local. |
| `flatcap novo <record_id>` | Cria a pasta do projeto a partir de uma solicitação, com o banco anexado. |
| `flatcap amostragem <id>` | Calcula o tamanho da amostra a partir do `desenho.yaml` e escreve o relatório da amostra, em `4. Amostragem/`. |
| `flatcap dados adicionar <id> <arquivo>` | Registra uma nova versão do banco. |
| `flatcap dados listar <id>` | Mostra a linha do tempo das versões do banco, conferida contra o disco. |
| `flatcap perfil <id>` | Descreve o banco: escreve o `perfil.md` e o `dicionario.csv`. |
| `flatcap descritiva <id>` | Tabelas de frequência, resumos, faixas e gráficos, obedecendo ao `dicionario.csv`. |
| `flatcap normalidade <id>` | Shapiro-Wilk, assimetria, curtose e Q-Q das numéricas. |
| `flatcap cruzamento <id>` | Uma tabela cruzada por par da lista `cruzamento:`. |
| `flatcap associacao <id>` | Qui-quadrado ou Fisher, pela regra de Cochran, para os pares da lista `associacao:`. |
| `flatcap correlacao <id>` | Pearson, Spearman ou Kendall, pelos pressupostos, para os pares da lista `correlacao:`. |
| `flatcap comparacao <id>` | Testes t e ANOVAs, ou os de postos — Wilcoxon, Mann-Whitney, Kruskal-Wallis e Friedman —, pelos pressupostos: contra uma referência, entre grupos ou entre medidas repetidas. |
| `flatcap analisar <id>` | Roda de uma vez as análises da lista `analises:` do `projeto.yaml`. |
| `flatcap relatorio <id>` | Monta o relatório `.docx` a partir das análises já rodadas. |
| `flatcap template` | Escreve o modelo `.docx` que o relatório usa, para ajustar no Word. |

> Os comandos que escrevem em disco **simulam por padrão**: mostram o que seria feito e não
> tocam em nada. Use `--sim` para executar de fato.

Opções que valem para vários comandos:

| Opção | Efeito |
|---|---|
| `--version`, `-V` | Mostra a versão e a licença, e sai. |
| `--env CAMINHO` | Usa outro `.env`. |
| `--sim` | Executa de fato (nos comandos que escrevem). |
| `--aba NOME` | A planilha a ler, quando o `.xlsx` tem mais de uma. Sem isso, a primeira. |
| `--rapido` | Não reconfere o `sha256` das versões do banco. Útil com bancos muito grandes. |
| `--sem-graficos` | Escreve só as tabelas, sem carregar o `matplotlib` (descritiva, normalidade, correlação e lote). |

### `flatcap doctor`

Testa as credenciais, a conexão com o REDCap e a pasta de dados. Responde se o problema está
na configuração, na rede ou no token, e confere se `pandas`, `openpyxl`, `scipy`, `matplotlib`
e `python-docx` estão instalados.

| Opção | Efeito |
|---|---|
| `--criar-root` | Cria a pasta `FLATCAP_ROOT` se ela ainda não existir. |
| `--criar-env` | Cria o `.env` da sua conta, com as três chaves em branco, e sai. Nunca sobrescreve. |

### `flatcap listar`

Lista as solicitações no REDCap e o que já foi para o disco. É o comando que coordena o fluxo
diário: mostra o que chegou de um lado e o que já virou pasta do outro.

| Opção | Efeito |
|---|---|
| `-n N`, `--ultimos N` | Só as N solicitações mais recentes (maior `record_id`). |
| `--conferir-anexos` | Confirma cada anexo na API. Mais lento; só necessário se a coluna `Anexo` vier vazia para todo mundo. |

### `flatcap novo <record_id>`

Cria a pasta do projeto a partir de uma solicitação do REDCap, com o anexo baixado em
`1. Dados originais/` como `00_redcap_AAAA-MM-DD_<nome original>`, somente leitura. Sem anexo,
a pasta é criada assim mesmo, e o banco entra depois pelo `flatcap dados adicionar`.

```bash
flatcap novo 42          # simula
flatcap novo 42 --sim    # cria
```

### `flatcap amostragem <id>`

Calcula o tamanho da amostra e escreve o relatório da amostra. Vem depois do `flatcap novo` —
o pedido de amostragem costuma chegar sem banco, e o `novo` cria a pasta assim mesmo —, e
tudo dele mora em `4. Amostragem/`, dentro da pasta do projeto.

A primeira rodada cria a pasta e o `desenho.yaml`, o plano da amostra, para preencher à mão. O
modelo já vem com o caso mais comum — 95% de confiança, margem de 5 pontos percentuais e
proporção esperada de 50% —, e quase sempre basta escrever a população que o cliente
informou:

```yaml
desenho: aas        # amostragem aleatória simples, sem reposição
populacao: 1200     # N, sem ponto de milhar; em branco, a conta é a de população grande
confianca: 95       # em %
margem: 5           # em pontos percentuais; para uma média, na unidade da variável
proporcao: 50       # em %; para uma média, `desvio:` no lugar dela
perda: 10           # a perda esperada, em %
```

Com esse desenho, n₀ = 385, n = 292 com a correção para N = 1200, e 325 com a perda. As
rodadas seguintes escrevem o `tamanho.csv` (a conta, linha por linha), o `manifesto.json` e o
`Amostragem_<matrícula>_AAAA-MM-DD.docx`. Rodar de novo arquiva a rodada anterior em
`4. Amostragem/Versões antigas/`, com o `desenho.yaml` de então, e avisa se o tamanho mudou. O
`desenho.yaml` nunca é sobrescrito, e um tamanho já decidido entra em `n:`, no lugar da conta.
Por enquanto, o único desenho é a aleatória simples.

```bash
flatcap amostragem 23 --sim    # a primeira vez: cria 4. Amostragem/ e o desenho.yaml
flatcap amostragem 23          # depois de preenchê-lo: simula a conta
flatcap amostragem 23 --sim    # escreve a conta e o relatório da amostra
```

| Opção | Efeito |
|---|---|
| `--template ARQUIVO` | O modelo `.docx`, como no `flatcap relatorio`. |
| `--titulo TEXTO` | O título da primeira linha do documento. Sem isso, "Relatório de Amostragem". |

### `flatcap dados adicionar <id> <arquivo>` e `flatcap dados listar <id>`

O `adicionar` registra uma nova versão do banco: copia o arquivo para `1. Dados originais/`
com o próximo número da série, manda a versão de trabalho anterior para
`2. Versões antigas/` e acrescenta a entrada em `dados:` no `projeto.yaml`. O `00_redcap_*`
nunca é tocado, e um reenvio idêntico não vira versão.

O `listar` mostra a linha do tempo e confronta a ficha com o disco: aponta versão registrada
que sumiu, arquivo alterado depois do registro e arquivo na pasta que a ficha desconhece.

```bash
flatcap dados adicionar 42 ~/Downloads/banco_revisado.xlsx --sim
flatcap dados listar 42
```

### `flatcap perfil <id>`

Descreve o banco e prepara a reunião com o cliente. Abre a versão vigente, mede cada
variável, aponta os problemas conhecidos e escreve o `perfil.md`, o documento que você leva
para a conversa, e o `dicionario.csv`, que dirige as análises daqui em diante. O dicionário
que já existir **não é sobrescrito**: as linhas que você preencheu ficam intactas, e só entram
as variáveis novas.

O `dicionario.csv` tem uma linha por variável: `tipo` (`categorica`, `numerica`, `data` ou
`ignorar`), `categorias_ordem` (a ordem das categorias, com o rótulo de cada código —
`1=Feminino|2=Masculino`) e `faixas` (os cortes de uma numérica — `0|18|30|60|120`).

### As análises

Cada análise escreve em `3. Análises/<análise>/` as suas tabelas (`.csv`), as figuras
(`.png`) e um `manifesto.json` que diz de qual variável, de qual versão do banco e com quais
bibliotecas saiu cada arquivo. Rodar de novo arquiva a rodada anterior inteira em
`2. Versões antigas/`.

| Análise | O que precisa no `projeto.yaml` |
|---|---|
| `descritiva` | nada: descreve todas as variáveis que o dicionário não marcou `ignorar` |
| `normalidade` | nada: testa todas as numéricas; uma lista `normalidade: [idade, imc]` restringe |
| `cruzamento` | `cruzamento:` com os pares — `- [sexo, escolaridade]` |
| `associacao` | `associacao:` com os pares — `- [sexo, desfecho]` ou `- desfecho: [sexo, escolaridade]` |
| `correlacao` | `correlacao:` com os pares — `- [idade, imc]`, ou `- [dor, ansiedade, kendall]` com o método |
| `comparacao` | `comparacao:` com os itens — `- [imc, 25]` (uma amostra), `- [imc, sexo]` (grupos), `- repetidas: [pas_0, pas_1, pas_2]` |

Os pares e os itens se escrevem na ficha, na reunião: trinta variáveis dão 435 pares, e
testar todos é *p-hacking* feito por máquina. Sem a lista, o comando recusa e diz o que
escrever. Um exemplo de ficha com todos os blocos:

```yaml
analises: [descritiva, normalidade, associacao, comparacao]   # a ordem das seções do relatório

normalidade: [idade, imc]
associacao:
  - [sexo, desfecho]
comparacao:
  - [imc, 25]                   # uma amostra, contra a referência
  - [imc, sexo]                 # dois grupos: o t de Welch ou, sem a normal, o Mann-Whitney
  - [pas, escolaridade, anova]  # três grupos ou mais: a ANOVA clássica, escrita
  - repetidas: [pas_0, pas_1, pas_2]
```

### `flatcap analisar <id>`

Roda de uma vez as análises da lista `analises:`, na ordem dela. Cada análise roda como o
comando dela — a mesma saída, os mesmos arquivos, a mesma linha no `historico.md`. Todas são
preparadas antes de qualquer uma ser escrita: se uma recusar, nada é escrito, e as recusas
aparecem juntas. `--resumo` mostra só a tabela do lote. O relatório fica de fora: leia as
tabelas antes.

### `flatcap relatorio <id>`

Monta o `.docx` a partir das análises já rodadas: lê o `manifesto.json` de cada rodada em
`3. Análises/` e escreve as seções na ordem da lista `analises:`. Não abre o banco e não
recalcula nada. O documento sai na raiz da pasta do projeto como
`Relatorio_<matrícula>_AAAA-MM-DD.docx`, e o anterior vai para `2. Versões antigas/`. Quando
uma rodada já não descreve o que está na pasta — banco novo, dicionário mexido —, o documento
sai assim mesmo, com o aviso escrito dentro dele.

| Opção | Efeito |
|---|---|
| `--template ARQUIVO` | Um `.docx` de onde herdar estilos, cabeçalho e capa. Sem isso, o `template.docx` da pasta do projeto, da do cliente ou do `FLATCAP_ROOT`. |
| `--titulo TEXTO` | O título da primeira linha do documento. |

### `flatcap template`

Escreve o modelo `.docx` que o relatório usa, para você ajustar no Word: A4, margens,
cabeçalho, rodapé com o número da página e os seis estilos `FlatCap Titulo`,
`FlatCap Subtitulo`, `FlatCap Secao`, `FlatCap Corpo`, `FlatCap Legenda` e `FlatCap Tabela`.
Tudo o que estiver no corpo do modelo aparece **antes** do relatório, em todo relatório — é
assim que uma capa institucional continua sendo a capa. Ao lado dele, o
`template-decisoes.md` explica o que se ajusta no Word e o que é código.

---

## Fluxo típico

```bash
flatcap doctor                                   # a configuração está de pé?
flatcap listar -n 10                             # o que chegou de novo?
flatcap novo 42 --sim                            # cria a pasta do projeto
flatcap perfil 42 --sim                          # perfil.md + dicionario.csv
#   reunião com o cliente: revise o dicionario.csv e escreva as listas no projeto.yaml
flatcap dados adicionar 42 banco_revisado.xlsx --sim   # se veio versão nova
flatcap analisar 42 --sim                        # as análises da lista `analises:`
flatcap relatorio 42 --sim                       # o .docx
```

Um pedido de amostragem:

```bash
flatcap novo 23 --sim                            # a pasta do projeto, como sempre
flatcap amostragem 23 --sim                      # 4. Amostragem/ e o desenho.yaml
#   preencha o desenho.yaml — quase sempre, só a populacao
flatcap amostragem 23 --sim                      # a conta e o relatório da amostra
```

## O que fica onde

```
FLATCAP_ROOT/                                   fora do Git
├── template.docx                               o modelo institucional do relatório
└── 00742 - José Antônio de Sá/                 o cliente: matrícula - nome
    └── Projeto 006/                            o projeto: o record_id, em três dígitos
        ├── projeto.yaml                        a ficha: o cliente, as listas, as versões
        ├── historico.md                        uma linha por ação do FlatCap
        ├── perfil.md                           o documento da reunião
        ├── dicionario.csv                      as decisões da reunião
        ├── Relatorio_00742_2026-09-20.docx     o que se entrega
        ├── 1. Dados originais/                 o banco do REDCap e a versão vigente
        ├── 2. Versões antigas/                 o que deixou de ser vigente
        ├── 3. Análises/                        uma pasta por análise
        └── 4. Amostragem/                      só com amostragem: o desenho.yaml, a conta, o
                                                relatório da amostra e as versões antigas dela
```

**Banco de pesquisa, nome de aluno e relatório não entram no Git**, nem em repositório
privado: o `.gitignore` bloqueia `*.xlsx`, `*.csv`, `*.docx` e afins, e o `FLATCAP_ROOT` mora
fora do repositório.

## Contribuir, segurança e licença

- [`CONTRIBUTING.md`](CONTRIBUTING.md) — como propor uma mudança, e o ritual de testes antes
  dela.
- [`SECURITY.md`](SECURITY.md) — token vazado, dado de cliente e como relatar uma
  vulnerabilidade.
- [`CHANGELOG.md`](CHANGELOG.md) — o que mudou em cada versão.

Copyright (C) 2026 Matheus Fernandes. O FlatCap é software livre, distribuído sob a
**GNU General Public License, versão 3 ou posterior** (`GPL-3.0-or-later`) — ver
[`LICENSE`](LICENSE). Algumas funções são transcrições de código do R, também sob a GPL; a
origem de cada uma está no [`NOTICE.md`](NOTICE.md).
