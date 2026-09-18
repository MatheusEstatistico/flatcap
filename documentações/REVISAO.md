# Revisão FlatCap — problemas encontrados

Revisão de todos os arquivos de `src/flatcap/` e `tests/`, mais `pyproject.toml`, `.gitignore` e `README.md`.
Ambiente conferido: Python 3.13.5, pandas 3.0.5, numpy 2.5.2, scipy 1.18.1, matplotlib 3.11.1, openpyxl 3.1.5.

**Estado da suíte: `75 falharam, 543 passaram, 19 não foram coletados`** (`pytest -q`).
**`ruff check .`: passa sem nenhum achado.**

---

## Bloqueadores para o próximo módulo de análise

### 1. `relatorio.py` — a normalidade nunca chega ao documento

`preparar_relatorio` lê uma pasta fixa (linha 400):

```python
pasta = raiz / PASTA_ANALISES / PASTA_DESCRITIVA
```

Rodei o fluxo inteiro (perfil → descritiva → normalidade → relatorio) num projeto de teste:

```
pastas em 3. Análises: ['descritiva', 'normalidade']
SEÇÕES DO RELATÓRIO: ['idade', 'sexo', 'imc']
normalidade.csv no relatório? False
Q-Q no relatório?        False
analises da ficha: ('descritiva', 'normalidade')
```

O `normalidade.csv` e os `qq_*.png` são escritos no disco e **não entram no `.docx`**. Todo módulo novo (teste t, qui-quadrado) vai cair no mesmo buraco: escreve a pasta, e o relatório ignora.

### 2. `Ficha.analises` não é lida por ninguém

`ficha.py:226` declara o campo, `ficha.py:574` o preenche, `projeto.py:665` grava `analises: []` na ficha nova, o cabeçalho do `projeto.yaml` promete *"a Fase 7 lê esta lista para saber quais módulos rodar"*, e a docstring da `Ficha` diz que é *"a ordem das seções do relatório quando há mais de uma rodada"*.

Nenhum módulo consulta `ficha.analises`. A lista não dirige nada.

### 3. `Manifesto.colunas_usadas` é código morto

`manifesto.py:289` e `manifesto.py:349`. O campo `colunas` é gravado no JSON, mas `relatorio._conferir_dicionario` (linha 1002) continua usando `item.variavel`:

```python
conhecidas = {item.variavel: item for item in manifesto.itens}
```

A docstring do `manifesto.py` (linhas 33-39) afirma o contrário — que a conferência compara "a união das colunas". Só o `test_normalidade.py:376` toca a propriedade.

Consequência prática: se o relatório passar a ler a pasta `normalidade/` sem antes trocar essa linha, o item da normalidade tem `variavel=""` e a conferência vai reportar "`` saiu da descritiva depois da rodada" em todo relatório.

---

## Suíte de testes

### `tests/conftest.py`

- **`projeto_vazio` monta o layout anterior à 1.1.0**: cria `root/00742 - José Antônio de Sá/projeto.yaml`, sem o nível `Projeto NNN`. Causa direta de ~30 falhas — tudo que passa por `localizar_projeto` levanta `LayoutAntigoError`. É a origem isolada do maior bloco de falhas em `test_cli.py`, `test_dados.py`, `test_ficha.py` e `test_projeto.py`.
- **`escrever_ficha` nunca escreve `finalidade` nem `objetivos`**: todo relatório montado em teste dispara o alerta `texto_ausente`. Quebra `test_relatorio.py:150` e `test_relatorio.py:205`.
- **`congelar_relogio`** percorre `("dados", "descritiva", "perfil", "projeto", "relatorio")` — `normalidade` ficou de fora.
- **`__all__`** exporta `shutil`, `os` e `date`: são módulos importados, não auxiliares da fixture.

### Testes desatualizados em relação ao código (o código está certo)

| Teste | Situação |
|---|---|
| `test_modelo.py:163` | espera 7 campos em `CAMPOS_REDCAP`; hoje são 10 (entraram `fin`, `outros1`, `obj1`) |
| `test_manifesto.py:167` | espera a frase `flatcap descritiva`; a mensagem foi generalizada para "Rode a análise de novo" |
| `test_ficha.py:121` | espera `reparar_fichas` no diagnóstico; a docstring de `_diagnostico` diz que o script foi aposentado de propósito |
| `test_cli.py:240` | espera `projeto.yaml` na pasta do cliente (layout pré-1.1.0) |
| `test_projeto.py:130` | espera `00742 - José Antônio de Sá`; `_destino` devolve `Projeto 042` |

### Testes que apontam defeito real no código

- `test_dados.py:381` — `test_o_relatorio_arquivado_nao_e_uma_versao_desconhecida_do_banco`
- `test_dicionario.py:211` e `:222` — round-trip do `dicionario.csv`
- `test_documento.py:92` — quebra de página sem texto de abertura
- `test_perfil.py:569` — detector sem classificação
- `test_config.py:204` (×7) — erros de grafia

Detalhados abaixo, por arquivo.

### `tests/test_e2e.py`

`pyproject.toml` fixa `addopts = "-m 'not e2e'"`. Os 19 testes e2e nunca rodam no comando padrão — podem estar quebrados há tempo sem ninguém notar.

---

## Por arquivo

### `pyproject.toml`

- **Versão divergente**: `version = "1.2.0"` contra `__init__.__version__ = "1.3.1"`. O número que vai gravado em todo `manifesto.json` (campo `flatcap` e `ambiente.flatcap`) é o 1.3.1; o pacote instalado se declara 1.2.0. Duas fontes para o mesmo número — exatamente o que o projeto evita em todo o resto.
- `pandas>=3.0` sem teto. Piso numa versão recém-lançada: o pacote não instala em nenhum ambiente com pandas 2.x.
- `addopts = "-m 'not e2e'"` esconde 19 testes do comando padrão.

### `src/flatcap/config.py`

Sete erros de grafia em texto que o usuário lê (é o que `test_nao_ha_erro_de_digitacao_conhecido` pega):

| Linha | Está | Deveria ser |
|---|---|---|
| 29 | `NÃO É O LINK DO SERVEY` | SURVEY |
| 32 | `obtido no meu 'API'` | menu |
| 33 | `Preciisa` | Precisa |
| 33 | `registros medatados` | metadados |
| 80 | `Raíses:` | Raises: |
| 129 | `é o link do syrvey` | survey |
| 154 | `FLATCAP_ROOT não exisite` | existe |
| 177 | `Configuração incompleta. Fatam:` | Faltam |
| 185 | `Crie aquivo .env` | arquivo |

### `src/flatcap/dados.py`

- **`linha_do_tempo` trata qualquer arquivo de `2. Versões antigas/` como versão não registrada do banco** (linhas 351-359). Depois de `flatcap relatorio`, o `Relatorio_*.docx` arquivado aparece em `flatcap dados listar` como "arquivo que a ficha não conhece". Falha em `test_dados.py:381`. O filtro só descarta diretórios e arquivos ocultos — não filtra por extensão nem pela convenção `NN_`.

### `src/flatcap/dicionario.py`

- **`_lista` (linha 542) aceita `;` como separador de lista mesmo num arquivo cujo separador de campos é `;`.** A escrita está correta (o `csv.writer` põe entre aspas); a leitura parte. Uma categoria `Alta; a pedido` volta do disco como duas: `('Alta', 'a pedido')`. Round-trip quebrado (`test_dicionario.py:211`).
- **`_lista` apara espaços das categorias** (`parte.strip()`). `"Sim "` volta `"Sim"`. Como `"Sim "` e `"Sim"` são categorias diferentes para a contagem — é o que o detector `espaco_sobrando` do perfil denuncia —, a categoria declarada deixa de casar com o valor do banco e a linha sai com `n = 0` (`test_dicionario.py:222`).

### `src/flatcap/perfil.py`

- **`categoria_sem_rotulo` não está classificado.** O detector (linha 519) é `CONFIRMAR`, não entra em `CODIGOS_VOLATEIS` e não está na lista de estáveis do teste. A trava estrutural existe justamente para impedir detector sem classificação, e está falhando (`test_perfil.py:569`). O comentário das linhas 121-125 documenta a decisão de mantê-lo fora dos voláteis — falta refletir isso do outro lado.

### `src/flatcap/documento.py`

- **O `bool` de `_texto_padrao` nunca é `False`** (linha 349). Ele existe para decidir a quebra de página em `posicao == 0 and abriu` (linha 269), mas `relatorio.montar_abertura` sempre devolve pelo menos os dois marcadores (`«a preencher: ...»`) quando os campos estão vazios. O ramo é sempre verdadeiro e o caso que ele protege ficou inalcançável (`test_documento.py:92`).

### `src/flatcap/normalidade.py`

- **`_shapiro` captura qualquer aviso, não só o do scipy** (linhas 752-761). `warnings.simplefilter("always")` sem filtro de categoria + `or capturados` faz sair a frase *"o teste rodou sobre N valor(es), acima de 5000"* mesmo com N pequeno, sempre que qualquer biblioteca emitir um aviso não relacionado. Conferi com scipy 1.18.1: hoje não dispara em n = 5, 30, 200. É latente, e o texto resultante seria factualmente falso dentro do manifesto. Compare com `banco.py:402`, que filtra por `pd.errors.ParserWarning` — a manobra que a docstring diz estar imitando.
- **`executar_normalidade` só desfaz em `(OSError, NormalidadeError)`** (linha 515). Uma falha do matplotlib dentro de `desenhar` não é nenhuma das duas: sobe sem reverter nada, e a rodada anterior fica arquivada em troca de nada — que é exatamente o que o `desfazer` existe para impedir.
- **`criados.append(plano.pasta)` sem o `desfazer` correspondente** (linha 484): a pasta criada não é removida no rollback.
- **`_pontos_do_qq` roda sempre**, inclusive com `--sem-graficos`. Calcula e guarda N pontos por variável que `PlanoNormalidade.graficos` vai descartar.
- `avaliar`, linha 574: `if linha not in numericas` compara `Linha` por valor dentro de uma lista — O(n²) e frágil se duas linhas ficarem idênticas.

### `src/flatcap/descritiva.py`

- **`contagem` é reatribuída com outro tipo no mesmo escopo**: `pd.Series` na linha 563, `dict[str, int]` na 600, com anotação nova. Funciona, mas é releitura difícil no miolo da função mais importante do módulo.
- **`preparar_descritiva` monta a pasta à mão** (`raiz / PASTA_ANALISES / PASTA_DESCRITIVA`, linha 368) em vez de usar `projeto.pasta_da_analise`, que a `normalidade.py` usa. Duas formas para a mesma pergunta — e a helper foi criada justamente para isso.
- `_cortes_das_faixas`: a docstring diz "precisam ser cinco números distintos", o código exige `len(cortes) >= 3` (linha 954).
- `montar_manifesto` grava o bloco `dicionario` sem a chave `numericas` que a normalidade grava. Mesmo campo, esquemas diferentes.
- `_descrever_data` (linha 830): `(maximo - minimo).days` com `validas` vazia estoura. Hoje inalcançável (a recusa exige 90% conversível), mas sem guarda.

### `src/flatcap/graficos.py`

- **`fonte_dos_graficos()` nunca é chamada.** A docstring afirma: *"Levar isto para o `ambiente` do manifesto é uma linha no `descritiva._ambiente`"*. A linha não existe. O `ambiente` registra a versão do matplotlib e não a fonte que de fato desenhou — que é o defeito silencioso que a função foi escrita para expor.
- `matplotlib.rcParams` é alterado no import do módulo (linhas 107-108): estado global do processo mudado pelo simples ato de importar `graficos`.

### `src/flatcap/relatorio.py`

Além dos três bloqueadores do topo:

- `Relatorio.quando: datetime = None  # type: ignore[assignment]` (linha 291) — default inválido para o tipo declarado.
- `_arquivamentos`: `_ = destino` (linha 594) é linha morta.
- `_ARQUIVO_TEMPLATE` (linha 121) duplica `documento.ARQUIVO_TEMPLATE`. O próprio comentário reconhece e indica o conserto (descer a constante para `projeto.py`).

### `src/flatcap/ficha.py`

- `versao_vigente` (linha 265) chama `ficha.dados.index(versao)` dentro da chave do `max`: O(n²), e com duas `Versao` idênticas as duas recebem o mesmo índice de desempate.

### `src/flatcap/redcap.py`

Erros de grafia, alguns em texto que o usuário lê:

- linha 102: `"404: Endereço não econtrado"` → encontrado (mensagem de erro visível)
- linha 66: `requesição` / `autenditaca`; linha 49: `Sublasso`; linha 55: `baixad`; linha 107: `form um erro`; linha 10: `serparada`
- linha 163-164: falta espaço na concatenação — sai `"Deveria ser uma lista.Resposta atual dict."`
- linha 166: `str (v)` com espaço antes do parêntese

### `src/flatcap/cli.py`

- Indentação de 2 espaços; todo o resto do pacote usa 4. O `ruff` não reclama porque não há regra de largura de indentação no `select`, mas é o único arquivo assim — e é o maior do projeto (2069 linhas).

### `src/flatcap/modelo.py`

- `mais_recentes` (linha 176) está com a docstring vazia — três aspas e nada dentro.

### `.gitignore`

- **`*.csv`, `*.docx`, `*.xlsx` são ignorados globalmente e as exceções estão comentadas**:

```
# !tests/fixtures/*.csv
# !templates/*.docx
```

Qualquer fixture `.csv` (um `dicionario.csv` de exemplo, um banco de teste) que você criar não será versionada, e o git não avisa. Os próximos módulos de análise vão querer fixtures — vale destravar antes.

- `.env` aparece duas vezes (linha 225 e no bloco FlatCap). Sem efeito, só ruído.

### `README.md`

- Tabela de comandos truncada: a última linha é `| `` |---|`.
- O arquivo termina em `##`, sem conteúdo.
- Link da documentação vazio: `[`Doc.Flatcap`]()`.
- `Requer **_**` — placeholder não preenchido.
- Documenta só `doctor` e `listar`. Faltam `novo`, `dados adicionar`, `dados listar`, `perfil`, `descritiva`, `normalidade`, `relatorio`, `template`.
- O fluxo no topo para em "análise descritiva" — não menciona a normalidade.

---

## Compatibilidade

Sem problemas de compatibilidade encontrados no ambiente atual. A descritiva e a normalidade passam inteiras nos testes com pandas 3.0.5 / numpy 2.5.2 / scipy 1.18.1 / matplotlib 3.11.1 / Python 3.13.5. Nada no código usa sintaxe acima de 3.11, que é o piso declarado.

A única ressalva é a do `pyproject.toml`: `pandas>=3.0` sem teto, com piso numa versão muito recente.

---

## Ordem sugerida

1. `conftest.projeto_vazio` para o layout de dois níveis — destrava ~30 falhas de uma vez e devolve a suíte a um estado em que ela serve de rede.
2. Os defeitos reais que os testes apontam: `dados.linha_do_tempo`, `dicionario._lista` (dois), `documento`/`montar_abertura`, `perfil.categoria_sem_rotulo`, os typos do `config.py`.
3. Atualizar os cinco testes desatualizados.
4. Alinhar a versão (`pyproject.toml` ↔ `__init__.py`).
5. **Só então** os três bloqueadores: o relatório varrer `3. Análises/*/`, ler `ficha.analises` para a ordem das seções, e trocar `item.variavel` por `item.colunas_usadas` na conferência do dicionário.

O passo 5 é o que decide se o teste t e o qui-quadrado entram pelo caminho que a arquitetura já preparou ou repetem o problema da normalidade.
