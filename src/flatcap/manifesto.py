# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
"""
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

## O que a Fase 7 acrescentou aqui, e por quê

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

## Por que este módulo não importa o `pandas` nem o `matplotlib`

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

## O número de formato

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
"""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .dicionario import SEPARADOR_CAMPO

ARQUIVO_MANIFESTO = "manifesto.json"

FORMATO = 1

# O nome da análise de cada rodada. Vive aqui, e não em cada módulo, porque é o
# valor que o `relatorio.py` vai casar com a lista `analises:` da ficha — e duas
# grafias para a mesma análise é como uma rodada deixa de aparecer no documento
# sem que nada diga por quê.
ANALISE_DESCRITIVA = "descritiva"
ANALISE_NORMALIDADE = "normalidade"
ANALISE_CRUZAMENTO = "cruzamento"
ANALISE_ASSOCIACAO = "associacao"
ANALISE_CORRELACAO = "correlacao"
ANALISE_COMPARACAO = "comparacao"

# A amostragem também escreve um manifesto, e se declara nele — mas não é uma análise
# de `3. Análises/`. Ela mora em `4. Amostragem/` e tem o relatório dela, e por isso
# não entra na `ORDEM_PADRAO_DAS_ANALISES` de baixo nem no `analises.REGISTRO`: o
# relatório das análises varre só `3. Análises/`, e nunca a vê.
ANALISE_AMOSTRAGEM = "amostragem"

# A ordem em que as análises aparecem no documento quando a ficha não manda.
#
# A lista `analises:` do `projeto.yaml` tem a primeira palavra — é o que foi
# combinado na reunião, e o relatório obedece. Esta é a ordem de quem não
# escreveu nada lá: a descritiva primeiro, porque é ela que apresenta cada
# variável, e os pressupostos depois, porque falam de variáveis já apresentadas.
# Rodada que não estiver nem na ficha nem aqui entra no fim, em ordem
# alfabética — determinística, e visivelmente no fim, que é o lugar certo para
# uma análise que ninguém disse onde queria.
#
# O cruzamento entra logo depois da descritiva, e não no fim nem em ordem
# alfabética — que o poria antes dela. Sem teste, ele ainda é descrição: são as
# mesmas categóricas da descritiva, duas de cada vez, e se lê melhor junto delas
# do que depois dos pressupostos das numéricas.
#
# A associação vem logo depois do cruzamento: ela testa os pares de categóricas
# que o cruzamento acabou de mostrar, e não depende da normalidade — categórica
# não tem normalidade a testar. Os pressupostos das numéricas ficam depois dela,
# perto dos testes que vão precisar deles.
#
# A correlação vem logo depois da normalidade: é o primeiro teste que precisa dos
# pressupostos das numéricas, e é na tabela de normalidade que o leitor acabou de
# ver a forma das variáveis que ela vai cruzar.
#
# A comparação vem no fim, depois da correlação. Ela também precisa dos
# pressupostos, e poderia vir antes; no fim, a posição não mexe no raciocínio
# escrito para nenhuma das outras — e a lista `analises:` da ficha manda de
# qualquer jeito quando o cliente for ler as comparações primeiro.
#
# Uma análise nova acrescenta uma linha aqui e nada mais. É o mesmo tipo de
# registro que o `_FORMAS` do `graficos.py`, e existe pelo mesmo motivo: com
# `if/elif` espalhado, a análise nova aparece no documento em um lugar que
# ninguém escolheu.
ORDEM_PADRAO_DAS_ANALISES: tuple[str, ...] = (
    ANALISE_DESCRITIVA,
    ANALISE_CRUZAMENTO,
    ANALISE_ASSOCIACAO,
    ANALISE_NORMALIDADE,
    ANALISE_CORRELACAO,
    ANALISE_COMPARACAO,
)

# A semente.
#
# Ela mora aqui desde a Fase 7, e não no `descritiva.py` onde nasceu, pelo mesmo
# motivo de sempre: é um valor que **todo** manifesto registra, e um segundo
# módulo com uma segunda semente é como duas rodadas do mesmo projeto deixam de
# ser reproduzíveis uma contra a outra. Uma descritiva não sorteia nada e uma
# tabela de normalidade também não; quem vai precisar dela é o bootstrap e o
# teste de permutação, e quando precisarem ela já está escrita em todo manifesto
# já gerado. O `descritiva.py` reexporta o nome.
SEMENTE = 42

# O BOM, o mesmo do `dicionario.csv` e pela mesma razão: é ele que faz o Excel em
# português abrir o arquivo em UTF-8 em vez de cp1252.
_BOM = "\ufeff"


class ManifestoError(RuntimeError):
    """
    Falha ao ler o `manifesto.json`, já traduzida para o usuário.
    """


class ManifestoInvalidoError(ManifestoError):
    """
    O arquivo existe e não dá para interpretar — ou é de um formato mais novo.
    """

    def __init__(self, mensagem: str, caminho: Path | None = None) -> None:
        super().__init__(mensagem)
        self.caminho = caminho


# O contrato de saída de uma análise


@dataclass(frozen=True)
class Tabela:
    """
    Uma tabela pronta para virar `.csv`. Texto, não `DataFrame`.

    O conteúdo já vem montado como linhas de texto para que o `executar` de cada
    análise não decida mais nada e para que a simulação mostre exatamente o que
    seria gravado — a mesma invariante do `texto_do_dicionario` da Fase 4: o texto
    é o arquivo.

    Mora aqui desde a Fase 7. Era do `descritiva.py`, e uma análise nova que
    quisesse escrever um `.csv` teria de importar do módulo da descritiva — o que
    acoplaria duas análises que não têm nada a ver uma com a outra, e faria a
    segunda pagar o `pandas` só para conhecer uma `dataclass` de texto.
    """

    nome: str
    especie: str
    variavel: str
    titulo: str
    colunas: tuple[str, ...]
    linhas: tuple[tuple[str, ...], ...]
    notas: tuple[str, ...] = ()

    def texto(self) -> str:
        """
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
        """
        buffer = io.StringIO(newline="")
        escritor = csv.writer(
            buffer,
            delimiter=SEPARADOR_CAMPO,
            lineterminator="\n",
            quoting=csv.QUOTE_MINIMAL,
        )
        escritor.writerow(list(self.colunas))
        for linha in self.linhas:
            escritor.writerow(list(linha))

        cabecalho = [f"# {_uma_linha(self.titulo)}"]
        if self.variavel:
            cabecalho.append(f"# variável: {_uma_linha(self.variavel)}")
        cabecalho += [f"# {_uma_linha(nota)}" for nota in self.notas]
        return f"{_BOM}" + "\n".join(cabecalho) + "\n" + buffer.getvalue()


# Toda quebra de linha, com os espaços em volta dela: o `\n`, o `\r\n`, e os
# separadores que o `str.splitlines` também reconhece — o `\x0b` e o ` ` que
# chegam colando do Word. A mesma lista do `banco.nome_de_coluna`, que este módulo
# não importa: o `banco.py` carrega o `pandas`, e este não pode.
_QUEBRAS = re.compile(r"\s*[\n\r\v\f\x1c\x1d\x1e\x85  ]+\s*")


def _uma_linha(texto: str) -> str:
    """O texto de um comentário numa linha só: a quebra e o espaço em volta viram um espaço."""
    return _QUEBRAS.sub(" ", str(texto))


@dataclass(frozen=True)
class Grafico:
    """
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
    """

    nome: str
    especie: str  # barras | histograma | colunas | qq | dispersao
    variavel: str
    titulo: str
    subtitulo: str = ""
    rotulo_categoria: str = ""
    rotulo_valor: str = "n"
    categorias: tuple[str, ...] = ()
    valores: tuple[float, ...] = ()
    rotulos: tuple[str, ...] = ()
    bordas: tuple[float, ...] = ()
    contagens: tuple[int, ...] = ()
    # O Q-Q da Fase 7. `reta` é (intercepto, inclinação) — a reta de referência,
    # calculada por quem sabe estatística e não por quem desenha.
    pontos_x: tuple[float, ...] = ()
    pontos_y: tuple[float, ...] = ()
    reta: tuple[float, float] | None = None


# O índice da rodada


@dataclass(frozen=True)
class Artefato:
    """
    Um arquivo escrito por uma análise.

    `especie` é o que o `relatorio.py` usa para decidir onde ele entra no
    documento: uma `frequencia` vira tabela, um `histograma` vira figura. É por
    isso que ela é um campo próprio e não uma dedução a partir da extensão.
    """

    arquivo: str
    especie: str
    formato: str
    titulo: str = ""

    @property
    def e_tabela(self) -> bool:
        return self.formato == "csv"

    @property
    def e_figura(self) -> bool:
        return self.formato == "png"


@dataclass(frozen=True)
class ItemDoManifesto:
    """
    Uma seção da rodada, com os arquivos que ela gerou.

    Era "uma variável descrita", e a Fase 7 alargou o conceito sem mudar o campo:
    na descritiva um item continua sendo uma variável, e em uma análise que fala de
    várias — ou de um par — ele é **uma seção do documento**. `variavel` fica vazia
    nesse caso, `rotulo` é o que encabeça a seção, e `colunas` diz quais colunas do
    banco entraram.

    `colunas` é o campo que faz as conferências do relatório continuarem
    funcionando com mais de uma análise; ver a nota no topo do módulo. Item antigo,
    sem o campo, devolve a própria `variavel` — que é o que ele sempre quis dizer.
    """

    variavel: str
    slug: str
    rotulo: str
    tipo: str
    n: int
    faltantes: int
    artefatos: tuple[Artefato, ...] = ()
    detalhes: dict[str, Any] = field(default_factory=dict)
    avisos: tuple[str, ...] = ()
    colunas: tuple[str, ...] = ()

    @property
    def preenchidos(self) -> int:
        return self.n - self.faltantes

    @property
    def colunas_usadas(self) -> tuple[str, ...]:
        """
        As colunas do banco que este item usou.

        Cai na `variavel` quando `colunas` está vazia, que é o caso de todo
        manifesto escrito antes da Fase 7. É o que permite ao `relatorio.py`
        fazer uma pergunta só — "quais colunas esta rodada usou?" — sem saber de
        qual versão do FlatCap o arquivo veio.
        """
        if self.colunas:
            return self.colunas
        return (self.variavel,) if self.variavel else ()

    def artefato(self, especie: str) -> Artefato | None:
        for artefato in self.artefatos:
            if artefato.especie == especie:
                return artefato
        return None


@dataclass(frozen=True)
class Manifesto:
    """
    Uma rodada inteira de uma análise.

    A ordem de `itens` é a ordem das variáveis no dicionário, que por sua vez é a
    ordem das colunas no banco. Ela é o sumário da seção no relatório — e é por
    isso que reordenar o `dicionario.csv` reordena o documento, sem tocar em código.

    `analise` tem default para que um `Manifesto` montado à mão em teste antigo
    continue válido, e para que o arquivo escrito antes da Fase 7 seja lido como o
    que ele era.
    """

    flatcap: str
    gerado_em: datetime
    projeto: dict[str, Any]
    banco: dict[str, Any]
    dicionario: dict[str, Any]
    ambiente: dict[str, Any]
    regras: dict[str, Any]
    itens: tuple[ItemDoManifesto, ...] = ()
    fora: tuple[dict[str, Any], ...] = ()
    avisos: tuple[str, ...] = ()
    formato: int = FORMATO
    analise: str = ANALISE_DESCRITIVA

    @property
    def total_artefatos(self) -> int:
        return sum(len(item.artefatos) for item in self.itens)

    @property
    def tabelas(self) -> tuple[Artefato, ...]:
        return tuple(a for item in self.itens for a in item.artefatos if a.e_tabela)

    @property
    def figuras(self) -> tuple[Artefato, ...]:
        return tuple(a for item in self.itens for a in item.artefatos if a.e_figura)

    @property
    def colunas_usadas(self) -> tuple[str, ...]:
        """
        Todas as colunas do banco que esta rodada tocou, sem repetir e em ordem.

        É o que a conferência `dicionario_mudou` do relatório precisa perguntar
        quando há mais de uma rodada na pasta: "as colunas de que esta rodada fala
        ainda são analisáveis no dicionário de hoje?".
        """
        vistas: list[str] = []
        for item in self.itens:
            for coluna in item.colunas_usadas:
                if coluna and coluna not in vistas:
                    vistas.append(coluna)
        return tuple(vistas)

    def item(self, variavel: str) -> ItemDoManifesto | None:
        for item in self.itens:
            if item.variavel == variavel:
                return item
        return None

    def por_tipo(self, tipo: str) -> tuple[ItemDoManifesto, ...]:
        return tuple(item for item in self.itens if item.tipo == tipo)

    def como_dicionario(self) -> dict[str, Any]:
        """
        A forma serializável, na ordem em que ela sai no arquivo.

        `analise` vem logo depois de `formato` de propósito: as duas primeiras
        linhas do arquivo respondem "que arquivo é este?" e "do que ele fala?",
        que são as duas perguntas de quem o abre sem contexto.
        """
        return {
            "formato": self.formato,
            "analise": self.analise,
            "flatcap": self.flatcap,
            "gerado_em": self.gerado_em.isoformat(timespec="seconds"),
            "projeto": self.projeto,
            "banco": self.banco,
            "dicionario": self.dicionario,
            "ambiente": self.ambiente,
            "regras": self.regras,
            "variaveis": [
                {
                    "variavel": item.variavel,
                    "slug": item.slug,
                    "rotulo": item.rotulo,
                    "tipo": item.tipo,
                    "colunas": list(item.colunas_usadas),
                    "n": item.n,
                    "faltantes": item.faltantes,
                    "artefatos": [
                        {
                            "arquivo": artefato.arquivo,
                            "especie": artefato.especie,
                            "formato": artefato.formato,
                            "titulo": artefato.titulo,
                        }
                        for artefato in item.artefatos
                    ],
                    "detalhes": item.detalhes,
                    "avisos": list(item.avisos),
                }
                for item in self.itens
            ],
            "fora": [dict(entrada) for entrada in self.fora],
            "avisos": list(self.avisos),
        }


# Escrita


def texto_do_manifesto(manifesto: Manifesto) -> str:
    """
    O conteúdo do arquivo. Sem tocar no disco, para o `--sim` poder mostrá-lo.

    `ensure_ascii=False` porque o arquivo tem nome de variável e rótulo em
    português, e `\\u00e7` no lugar de `ç` transforma um índice legível em um
    despejo de máquina. Indentado de dois porque ele é lido por gente — quem lê
    por programa não se importa.
    """
    corpo = json.dumps(
        manifesto.como_dicionario(), ensure_ascii=False, indent=2, sort_keys=False
    )
    return corpo + "\n"


# Leitura


def ler(caminho: Path | str) -> Manifesto:
    """
    Lê o `manifesto.json` de uma rodada.

    Raises:
        ManifestoInvalidoError: o arquivo não existe, não é JSON, ou é de um
            formato mais novo do que esta versão do FlatCap conhece.
    """
    caminho = Path(caminho)
    if caminho.is_dir():
        caminho = caminho / ARQUIVO_MANIFESTO

    if not caminho.is_file():
        raise ManifestoInvalidoError(
            f"Não há {ARQUIVO_MANIFESTO} em {caminho.parent}.\n"
            "Sem ele não dá para saber de qual variável saiu cada arquivo da pasta. "
            "Rode a análise de novo para gerar a rodada.",
            caminho,
        )

    try:
        corpo = json.loads(caminho.read_text(encoding="utf-8"))
    except UnicodeDecodeError as erro:
        raise ManifestoInvalidoError(
            f"{caminho.name} não está em UTF-8.\nDetalhe técnico: {erro}", caminho
        ) from erro
    except json.JSONDecodeError as erro:
        raise ManifestoInvalidoError(
            f"{caminho.name} não é um JSON válido.\n"
            "O arquivo é escrito pelo FlatCap e não é feito para ser editado à mão — "
            "se você precisou mexer nele, apague-o e rode a análise de novo.\n"
            f"Detalhe técnico: {erro}",
            caminho,
        ) from erro

    return de_dicionario(corpo, caminho)


def de_dicionario(corpo: Any, caminho: Path | None = None) -> Manifesto:
    """
    Converte o JSON já decodificado em `Manifesto`.
    """
    if not isinstance(corpo, dict):
        raise ManifestoInvalidoError(
            f"O manifesto deveria ser um objeto JSON e é um {type(corpo).__name__}.",
            caminho,
        )

    formato = corpo.get("formato")
    if not isinstance(formato, int) or formato > FORMATO:
        raise ManifestoInvalidoError(
            f"Este manifesto está no formato {formato!r} e esta versão do FlatCap "
            f"conhece até o {FORMATO}.\n"
            "Ele foi escrito por uma versão mais nova. Atualize o FlatCap, ou rode a "
            "análise de novo para regerar a rodada neste formato.",
            caminho,
        )

    itens = tuple(
        ItemDoManifesto(
            variavel=str(item.get("variavel", "")),
            slug=str(item.get("slug", "")),
            rotulo=str(item.get("rotulo", "")),
            tipo=str(item.get("tipo", "")),
            n=int(item.get("n", 0)),
            faltantes=int(item.get("faltantes", 0)),
            artefatos=tuple(
                Artefato(
                    arquivo=str(artefato.get("arquivo", "")),
                    especie=str(artefato.get("especie", "")),
                    formato=str(artefato.get("formato", "")),
                    titulo=str(artefato.get("titulo", "")),
                )
                for artefato in item.get("artefatos", [])
                if isinstance(artefato, dict)
            ),
            detalhes=dict(item.get("detalhes") or {}),
            avisos=tuple(str(aviso) for aviso in item.get("avisos", [])),
            colunas=tuple(str(coluna) for coluna in item.get("colunas", []) if coluna),
        )
        for item in corpo.get("variaveis", [])
        if isinstance(item, dict)
    )

    return Manifesto(
        formato=formato,
        # Manifesto escrito antes da Fase 7 não tem o campo, e era de uma
        # descritiva: era a única análise que existia.
        analise=str(corpo.get("analise") or ANALISE_DESCRITIVA),
        flatcap=str(corpo.get("flatcap", "")),
        gerado_em=_data_e_hora(corpo.get("gerado_em"), caminho),
        projeto=dict(corpo.get("projeto") or {}),
        banco=dict(corpo.get("banco") or {}),
        dicionario=dict(corpo.get("dicionario") or {}),
        ambiente=dict(corpo.get("ambiente") or {}),
        regras=dict(corpo.get("regras") or {}),
        itens=itens,
        fora=tuple(
            dict(entrada) for entrada in corpo.get("fora", []) if isinstance(entrada, dict)
        ),
        avisos=tuple(str(aviso) for aviso in corpo.get("avisos", [])),
    )


def _data_e_hora(valor: Any, caminho: Path | None) -> datetime:
    try:
        return datetime.fromisoformat(str(valor))
    except (TypeError, ValueError) as erro:
        raise ManifestoInvalidoError(
            f"O campo `gerado_em` do manifesto não é uma data e hora: {valor!r}.",
            caminho,
        ) from erro


__all__ = [
    "ANALISE_AMOSTRAGEM",
    "ANALISE_ASSOCIACAO",
    "ANALISE_COMPARACAO",
    "ANALISE_CORRELACAO",
    "ANALISE_CRUZAMENTO",
    "ANALISE_DESCRITIVA",
    "ANALISE_NORMALIDADE",
    "ARQUIVO_MANIFESTO",
    "FORMATO",
    "ORDEM_PADRAO_DAS_ANALISES",
    "SEMENTE",
    "Artefato",
    "Grafico",
    "Manifesto",
    "ManifestoError",
    "ManifestoInvalidoError",
    "ItemDoManifesto",
    "Tabela",
    "de_dicionario",
    "ler",
    "texto_do_manifesto",
]
