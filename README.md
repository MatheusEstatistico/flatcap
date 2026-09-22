# FlatCap 
Ferramenta para orquestrar o fluxo de trabalho estatístico com Python e REDCap: 

**REDCap (entrada) → organização de pastas → versionamento dos bancos → análises gerais → relatório `.docx`**.

## Princípio norteador 
Automatizar o que é repetitivo e mecânico e manter manual o que é decisão técnica. Tudo que é automatizado fica documentado em disco, para que qualquer projeto possa ser reaberto meses depois e compreendido sem depender da memória. Nada é apagado, as versões antigas são documentadas na pasta do cliente/projeto. 

> A documentação completa pode ser encontrada em [`Doc.Flatcap`](https://github.com/MatheusEstatistico/flatcap/blob/main/documenta%C3%A7%C3%B5es/Doc.Flatcap.md).
---

## Instalação 
Requer **Python 3.11+** <br>
Requer **Git** <br>
Requer **_** <br>

```bash
git clone git@github.com:<usuario>/flatcap.git
cd flatcap
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```
 
## Configuração 
Copie `.env.example` para `.env` e preencha: 
```env
REDCAP_API_URL=https://<servidor-institucional>/redcap/api/
REDCAP_TOKEN=32caracteres
FLATCAP_ROOT=pasta_local
```

| Chave | Onde obter |
|---|---|
| `REDCAP_API_URL` | Página **API Playground** do projeto. **Não** é o link curto do survey. |
| `REDCAP_TOKEN` | Menu **API** do projeto → *Request API token*. <br>Precisa de permissão para exportar **registros, metadados e arquivos**. |
| `FLATCAP_ROOT` | Caminho absoluto da pasta onde os projetos vivem. |
--- 

## Comandos disponíveis

Ajuda de qualquer comando: `flatcap <comando> --help`.

| Comando | Função |
|---|---|
| `flatcap doctor` | Testa credenciais, conexão com o REDCap, `FLATCAP_ROOT` e as bibliotecas instaladas. |
| `flatcap listar` | Lista as solicitações do REDCap e diz quais já viraram pasta local. |
| `flatcap novo <record_id>` | Cria a pasta do projeto a partir de uma solicitação. |
| `flatcap dados adicionar <id> <arquivo>` | Registra uma nova versão do banco na pasta do projeto. |
| `flatcap dados listar <id>` | Mostra a linha do tempo das versões do banco. |
| `flatcap perfil <id>` | Descreve o banco e escreve o `perfil.md` e o `dicionario.csv`. |
| `flatcap descritiva <id>` | Gera a análise descritiva obedecendo ao `dicionario.csv`. |
| `flatcap normalidade <id>` | Testa a normalidade das variáveis numéricas. |
| `flatcap relatorio <id>` | Monta o relatório `.docx` a partir das análises já rodadas. |
| `flatcap template` | Escreve o modelo `.docx` que o relatório usa. |

> Comandos que escrevem em disco **simulam por padrão**: eles desenham a árvore do que seria feito e não tocam em nada. Use `--sim` para executar de fato.

**Opções globais**

| Opção | Efeito |
|---|---|
| `--version`, `-V` | Mostra a versão e sai. |
| `--help` | Mostra a ajuda do comando e sai. |

O `<id>` é o `record_id` **ou** a matrícula do projeto, como aparece no `flatcap listar`. <br>
Todo comando aceita `--env CAMINHO` para usar um `.env` alternativo.

---

### `flatcap doctor`
Testa as credenciais, a conexão com o REDCap e a pasta de dados. Responde se o problema está na configuração, na rede ou no token, e confere se `pandas`, `openpyxl`, `scipy`, `matplotlib` e `python-docx` estão instalados.

| Opção | Efeito |
|---|---|
| `--criar-root` | Cria a pasta `FLATCAP_ROOT` se ela ainda não existir. |
| `--env CAMINHO` | Caminho de um `.env` alternativo. |

```bash
flatcap doctor
flatcap doctor --criar-root
```

### `flatcap listar`
Lista as solicitações no REDCap e o que já foi para o disco. É o comando que coordena o fluxo diário: mostra o que chegou de novo de um lado e o que já virou pasta do outro.

| Opção | Efeito |
|---|---|
| `-n N`, `--ultimos N` | Mostra apenas as N solicitações mais recentes (maior `record_id`). Sem isso, mostra todas. |
| `--conferir-anexos` | Confirma cada anexo na API. Mais lento, e só necessário se a coluna `anexo` vier vazia para todo mundo. |
| `--env CAMINHO` | Caminho de um `.env` alternativo. |

```bash
flatcap listar
flatcap listar -n 10
```

### `flatcap novo <record_id>`
Cria a pasta do projeto a partir de uma solicitação do REDCap, já com o anexo baixado em `1. Dados originais/` como `00_redcap_AAAA-MM-DD_<nome original>`, somente leitura. Sem anexo no registro, a pasta é criada assim mesmo e o banco entra depois pelo `flatcap dados adicionar`.

| Argumento / Opção | Efeito |
|---|---|
| `record_id` | `record_id` da solicitação, como aparece no `flatcap listar`. |
| `--sim` | Executa de fato. Sem isso, apenas simula. |
| `--env CAMINHO` | Caminho de um `.env` alternativo. |

```bash
flatcap novo 42          # simula
flatcap novo 42 --sim    # cria
```

### `flatcap dados adicionar <id> <arquivo>`
Registra uma nova versão do banco na pasta do projeto. Copia o arquivo para `1. Dados originais/` com o próximo número da série, manda a versão de trabalho anterior para `2. Versões antigas/` e acrescenta a entrada em `dados:` no `projeto.yaml`. O `00_redcap_*` nunca é tocado.

| Argumento / Opção | Efeito |
|---|---|
| `id` | `record_id` ou matrícula do projeto. |
| `arquivo` | O arquivo revisado que o cliente mandou. |
| `--sim` | Executa de fato. Sem isso, apenas simula. |
| `--env CAMINHO` | Caminho de um `.env` alternativo. |

```bash
flatcap dados adicionar 42 ~/Downloads/banco_revisado.xlsx --sim
```

### `flatcap dados listar <id>`
Mostra a linha do tempo das versões do banco. Além do que está registrado em `dados:`, confronta a ficha com o disco: aponta versão registrada que sumiu, arquivo alterado depois do registro e arquivo presente na pasta que a ficha desconhece.

| Argumento / Opção | Efeito |
|---|---|
| `id` | `record_id` ou matrícula do projeto. |
| `--rapido` | Não reconfere o `sha256` dos arquivos. Útil com bancos muito grandes. |
| `--env CAMINHO` | Caminho de um `.env` alternativo. |

```bash
flatcap dados listar 42
```

### `flatcap perfil <id>`
Descreve o banco e prepara a reunião com o cliente. Abre a versão vigente registrada na ficha, mede cada variável, aponta os problemas conhecidos e escreve dois arquivos: o `perfil.md`, que é o documento que você leva para a conversa, e o `dicionario.csv`, que dirige a descritiva daqui em diante.

O dicionário que já existir **não é sobrescrito**: as linhas que você preencheu ficam intactas e só entram as variáveis novas.

| Argumento / Opção | Efeito |
|---|---|
| `id` | `record_id` ou matrícula do projeto. |
| `--aba NOME` | Planilha a ler, quando o `.xlsx` tiver mais de uma. Sem isso, a primeira. |
| `--rapido` | Não reconfere o `sha256` dos arquivos. |
| `--sim` | Executa de fato. Sem isso, apenas simula. |
| `--env CAMINHO` | Caminho de um `.env` alternativo. |

```bash
flatcap perfil 42 --sim
flatcap perfil 42 --aba "Dados 2024" --sim
```

### `flatcap descritiva <id>`
Gera a análise descritiva obedecendo ao `dicionario.csv`: uma tabela de frequência e um gráfico de barras por categórica; resumo, tabela por faixas e histograma por numérica; período e distribuição no tempo por data. Tudo em `3. Análises/descritiva/`, com um `manifesto.json` que diz de qual variável saiu cada arquivo.

Sem `faixas` preenchida no dicionário, as faixas saem pelos quartis da própria variável. Rodar de novo arquiva a rodada anterior inteira em `2. Versões antigas/`.

| Argumento / Opção | Efeito |
|---|---|
| `id` | `record_id` ou matrícula do projeto. |
| `--aba NOME` | Planilha a ler, quando o `.xlsx` tiver mais de uma. |
| `--sem-graficos` | Escreve só as tabelas. Mais rápido, e o `matplotlib` nem é carregado. |
| `--rapido` | Não reconfere o `sha256` dos arquivos. |
| `--sim` | Executa de fato. Sem isso, apenas simula. |
| `--env CAMINHO` | Caminho de um `.env` alternativo. |

```bash
flatcap descritiva 42 --sim
flatcap descritiva 42 --sem-graficos --sim
```

### `flatcap normalidade <id>`
Testa a normalidade das variáveis numéricas do `dicionario.csv`. Para cada `numerica`: o teste de Shapiro-Wilk, a assimetria, a curtose e um gráfico Q-Q, em `3. Análises/normalidade/` com o seu `manifesto.json`.

Por padrão entram todas as numéricas; uma lista `normalidade:` no `projeto.yaml` restringe às variáveis que você escrever nela. Rodar de novo arquiva a rodada anterior inteira.

| Argumento / Opção | Efeito |
|---|---|
| `id` | `record_id` ou matrícula do projeto. |
| `--aba NOME` | Planilha a ler, quando o `.xlsx` tiver mais de uma. |
| `--sem-graficos` | Escreve só a tabela. Mais rápido, e o `matplotlib` nem é carregado. |
| `--rapido` | Não reconfere o `sha256` dos arquivos. |
| `--sim` | Executa de fato. Sem isso, apenas simula. |
| `--env CAMINHO` | Caminho de um `.env` alternativo. |

```bash
flatcap normalidade 42 --sim
```

### `flatcap relatorio <id>`
Monta o relatório `.docx` a partir das análises já rodadas. Varre `3. Análises/`, lê o `manifesto.json` de cada rodada e monta o documento com as seções de todas elas, na ordem da lista `analises:` do `projeto.yaml`.

Não abre o banco e não recalcula nada: os números do documento são, letra por letra, os dos `.csv` que estão em `3. Análises/`. O documento sai na raiz da pasta do projeto como `Relatorio_<matrícula>_AAAA-MM-DD.docx`, e o anterior vai para `2. Versões antigas/`.

| Argumento / Opção | Efeito |
|---|---|
| `id` | `record_id` ou matrícula do projeto. |
| `--template ARQUIVO` | Um `.docx` para herdar estilos, cabeçalho e capa. Sem isso, o `template.docx` da pasta do projeto ou do `FLATCAP_ROOT`. |
| `--titulo TEXTO` | O título na primeira linha do documento. |
| `--rapido` | Não reconfere o `sha256` do banco. |
| `--sim` | Executa de fato. Sem isso, apenas simula. |
| `--env CAMINHO` | Caminho de um `.env` alternativo. |

```bash
flatcap relatorio 42 --sim
flatcap relatorio 42 --titulo "Análise descritiva preliminar" --sim
```

### `flatcap template`
Escreve o modelo `.docx` que o relatório usa, para você ajustar no Word. Sai com o corpo vazio e com os estilos `FlatCap Titulo`, `FlatCap Secao`, `FlatCap Corpo`, `FlatCap Legenda` e `FlatCap Nota` já definidos. Tudo o que você escrever no corpo do modelo aparece **antes** do relatório, em todo relatório — é assim que uma capa institucional continua sendo a capa.

| Opção | Efeito |
|---|---|
| `--saida ARQUIVO` | Onde escrever. Sem isso, `template.docx` na raiz do `FLATCAP_ROOT`. |
| `--sim` | Executa de fato. Sem isso, apenas simula. |
| `--env CAMINHO` | Caminho de um `.env` alternativo. |

```bash
flatcap template --sim
flatcap template --saida ~/modelos/institucional.docx --sim
```

---

## Fluxo típico

```bash
flatcap doctor                                   # a instalação está de pé?
flatcap listar -n 10                             # o que chegou de novo?
flatcap novo 42 --sim                            # cria a pasta do projeto
flatcap perfil 42 --sim                          # perfil.md + dicionario.csv
#   revise a coluna `tipo` do dicionario.csv e converse com o cliente
flatcap dados adicionar 42 banco_revisado.xlsx --sim   # se veio versão nova
flatcap descritiva 42 --sim                      # tabelas e gráficos
flatcap normalidade 42 --sim                     # pressupostos
flatcap relatorio 42 --sim                       # o .docx final
```
