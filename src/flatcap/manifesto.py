"""
O `manifesto.json` — o índice de uma rodada da descritiva.

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

## Por que este módulo não importa o `pandas` nem o `matplotlib`

Pela mesma razão que o `dicionario.py` não importa o `pandas`: o formato de um
arquivo de índice não depende de como o banco foi lido nem de como o gráfico foi
desenhado. A Fase 6 vai importar este módulo para montar o `.docx` e não precisa
de nenhum dos dois para isso — nem de meio segundo de partida para descobrir.

Ele também **não escreve no disco**. Monta o texto; quem grava é o `descritiva.py`,
com a escrita atômica do `ficha.py`. É a mesma invariante das outras fases: o texto
é o arquivo, e por isso a simulação pode mostrá-lo inteiro antes de existir.

## O número de formato

`"formato": 1` na primeira chave. Custa uma linha e compra a única coisa que um
arquivo lido por outra versão do programa precisa: a possibilidade de ser recusado
com uma frase em vez de interpretado errado em silêncio.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

ARQUIVO_MANIFESTO = "manifesto.json"

FORMATO = 1


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


@dataclass(frozen=True)
class Artefato:
    """
    Um arquivo escrito pela descritiva.

    `especie` é o que a Fase 6 vai usar para decidir onde ele entra no documento:
    uma `frequencia` vira tabela, um `histograma` vira figura. É por isso que ela
    é um campo próprio e não uma dedução a partir da extensão.
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
    Uma variável descrita, com os arquivos que ela gerou.
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

    @property
    def preenchidos(self) -> int:
        return self.n - self.faltantes

    def artefato(self, especie: str) -> Artefato | None:
        for artefato in self.artefatos:
            if artefato.especie == especie:
                return artefato
        return None


@dataclass(frozen=True)
class Manifesto:
    """
    Uma rodada inteira da descritiva.

    A ordem de `itens` é a ordem das variáveis no dicionário, que por sua vez é a
    ordem das colunas no banco. Ela é o sumário do relatório da Fase 6 — e é por
    isso que reordenar o `dicionario.csv` reordena o documento, sem tocar em código.
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

    @property
    def total_artefatos(self) -> int:
        return sum(len(item.artefatos) for item in self.itens)

    @property
    def tabelas(self) -> tuple[Artefato, ...]:
        return tuple(a for item in self.itens for a in item.artefatos if a.e_tabela)

    @property
    def figuras(self) -> tuple[Artefato, ...]:
        return tuple(a for item in self.itens for a in item.artefatos if a.e_figura)

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
        """
        return {
            "formato": self.formato,
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
            "Rode `flatcap descritiva <id> --sim` para gerar a rodada de novo.",
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
            "se você precisou mexer nele, apague-o e rode `flatcap descritiva` de "
            f"novo.\nDetalhe técnico: {erro}",
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
            "Ele foi escrito por uma versão mais nova. Atualize o FlatCap, ou rode "
            "`flatcap descritiva` de novo para regerar a rodada neste formato.",
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
        )
        for item in corpo.get("variaveis", [])
        if isinstance(item, dict)
    )

    return Manifesto(
        formato=formato,
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
