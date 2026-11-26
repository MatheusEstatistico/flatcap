# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
"""
As fórmulas do documento — o que uma equação é, antes de virar equação do Word.

O relatório da amostra mostra a conta que fez: a fórmula com as letras, a mesma fórmula
com os números do projeto no lugar delas, e o resultado. Este módulo diz **o que** a
fórmula é; quem a escreve no `.docx` é o `documento.py`, como equação do Word. É a divisão
do resto do documento — quem monta não formata —, e pelo mesmo motivo: o texto da conta é
decidido na simulação, que não escreve documento nenhum.

## Uma árvore, e não texto

Uma fração tem numerador e denominador, uma potência tem base e expoente, e é essa
estrutura que o Word precisa para desenhar a fração empilhada. Escrita como texto, com
barras, a conta não se lê como fórmula; desenhada como imagem, não se edita. Como equação
do Word, ela se copia para o artigo e se corrige lá, e é para isso que o texto padrão
existe.

Cinco peças bastam para as contas da amostra:

    Simbolo      uma letra, em itálico, com o índice embaixo: z, p, n₀, σ
    Texto        o que sai em pé: número, operador, palavra — 1,96 · = · × · perda
    Fracao       o numerador sobre o denominador
    Potencia     a base com o expoente: 1,96²
    Delimitada   entre parênteses, ou entre os colchetes do teto: (1 − p), ⌈x⌉

E dois blocos de texto, que é o que o documento recebe: o `Paragrafo`, texto corrido com
fórmula no meio da linha, e a `Equacao`, a fórmula em destaque, numa linha só dela.

## A fórmula no meio da frase

Uma frase pode trazer uma fórmula curta, escrita entre cifrões, como no LaTeX:
`com $N = 1700$ unidades`. É assim que as frases editáveis da amostragem a escrevem, sem
código. Entre os cifrões vale uma escrita mínima, a que as frases usam:

    N, z, σ        a letra sozinha é um símbolo, em itálico
    n_0, n_f       o índice, depois do sublinhado
    z^2            o expoente, depois do acento circunflexo
    perda          a palavra sai em pé, como texto
    1700, 0,05     os números, com a vírgula decimal
    =, +, (, )     como estão; `-` sai −, e `*` sai ×

A fração não cabe na linha, e fica para a fórmula em destaque, montada no código. Um
cifrão de verdade, como o de R$, se escreve `\\$`.

## A fórmula da linha sai como texto

A fórmula no meio da frase, quando não tem fração, sai no documento como texto formatado —
a letra em itálico, o índice embaixo, o expoente em cima —, e não como equação do Word:
`trechos_de` a reparte nos pedaços de texto e na formatação de cada um. Dois motivos. A
equação do Word na linha estica a altura dela — a fonte das equações, a Cambria Math, tem
ascendentes altos —, e a legenda do «Onde:», que é uma fórmula por linha, empurraria a
tabela para a segunda página. E o texto se cola em qualquer editor, enquanto a equação nem
sempre. A fórmula em destaque, com a fração, é sempre equação do Word.

## O texto da fórmula

`texto_de` escreve qualquer peça numa linha só — `n₀ = (1,96² × 0,5 × 0,5) / 0,05²` —, para
o terminal e para os testes: o `python-docx` não devolve o texto de uma equação no
`paragraph.text`, e um teste que lesse só o texto corrido não veria a conta.

## Sem dependência

Só a biblioteca padrão. A amostragem monta o documento inteiro na simulação, e o teste em
subprocesso confere que ela não carrega o `python-docx` — que este módulo, por isso, não
importa.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# As peças


@dataclass(frozen=True)
class Simbolo:
    """Uma letra da fórmula, em itálico, com o índice embaixo quando há: `n₀`, `n_f`."""

    letra: str
    indice: str = ""


@dataclass(frozen=True)
class Texto:
    """O que sai em pé: um número, um operador, uma palavra. `1,96`, `=`, `×`, `perda`."""

    texto: str


@dataclass(frozen=True)
class Fracao:
    """O numerador sobre o denominador, empilhados."""

    numerador: Formula
    denominador: Formula


@dataclass(frozen=True)
class Potencia:
    """A base com o expoente em cima: `1,96²`."""

    base: Formula
    expoente: Formula


@dataclass(frozen=True)
class Delimitada:
    """O conteúdo entre parênteses — ou entre os colchetes do teto, `⌈` e `⌉`."""

    conteudo: Formula
    abre: str = "("
    fecha: str = ")"


Elemento = Simbolo | Texto | Fracao | Potencia | Delimitada


@dataclass(frozen=True)
class Formula:
    """Uma fórmula: as peças, na ordem em que se leem."""

    elementos: tuple[Elemento, ...] = ()

    def __bool__(self) -> bool:
        return bool(self.elementos)


# Os blocos de texto


@dataclass(frozen=True)
class Paragrafo:
    """
    Um parágrafo de texto corrido, com fórmula no meio da linha.

    `junto` é a linha de uma lista — a legenda do «Onde:» —: sai colada à de baixo, sem o
    respiro de um parágrafo, e presa a ela na quebra de página.
    """

    partes: tuple[str | Formula, ...]
    junto: bool = False

    def __bool__(self) -> bool:
        return any(
            parte.strip() if isinstance(parte, str) else bool(parte) for parte in self.partes
        )


@dataclass(frozen=True)
class Equacao:
    """Uma fórmula em destaque, numa linha só dela, centralizada."""

    formula: Formula

    def __bool__(self) -> bool:
        return bool(self.formula)


Bloco = Paragrafo | Equacao


# Para montar


def formula(*partes: str | Elemento | Formula) -> Formula:
    """
    Junta as partes numa fórmula. O texto vira `Texto`, e uma fórmula dentro de outra se
    desfaz nos elementos dela — `formula(a, "=", b)` é uma linha só, e não uma dentro da
    outra.
    """
    elementos: list[Elemento] = []
    for parte in partes:
        if isinstance(parte, Formula):
            elementos.extend(parte.elementos)
        elif isinstance(parte, str):
            elementos.append(Texto(parte))
        else:
            elementos.append(parte)
    return Formula(tuple(elementos))


def fracao(numerador: str | Elemento | Formula, denominador: str | Elemento | Formula) -> Fracao:
    return Fracao(formula(numerador), formula(denominador))


def potencia(base: str | Elemento | Formula, expoente: str | Elemento | Formula) -> Potencia:
    return Potencia(formula(base), formula(expoente))


def parenteses(*partes: str | Elemento | Formula) -> Delimitada:
    return Delimitada(formula(*partes))


def teto(*partes: str | Elemento | Formula) -> Delimitada:
    """`⌈x⌉`, o arredondamento para cima."""
    return Delimitada(formula(*partes), abre="⌈", fecha="⌉")


# A fórmula entre cifrões

# Um cifrão que não vem depois de uma barra abre ou fecha a fórmula; `\$` é o cifrão de
# verdade, e sai sem a barra.
_ENTRE_CIFROES = re.compile(r"(?<!\\)\$(.*?)(?<!\\)\$")

_PECA = re.compile(
    r"(?P<espaco>\s+)"
    r"|(?P<numero>\d+(?:[.,]\d+)*)"
    r"|(?P<palavra>[^\W\d_]+)(?:_(?P<indice>\{[^}]*\}|[^\W_]+))?"
    r"|\^(?P<expoente>\{[^}]*\}|[^\W_]+)"
    r"|(?P<outro>.)"
)

# Os operadores que se digitam com o que o teclado tem, e o que sai no documento.
_OPERADORES = {"-": "−", "*": "×"}


def paragrafo(texto: str, junto: bool = False) -> Paragrafo:
    """
    O parágrafo de uma frase que pode trazer fórmulas entre cifrões.

    `"com $N = 1700$ unidades"` vira o texto `com `, a fórmula `N = 1700` e o texto
    ` unidades`. Sem cifrão, é um parágrafo de texto só.
    """
    partes: list[str | Formula] = []
    inicio = 0
    for achado in _ENTRE_CIFROES.finditer(texto):
        if achado.start() > inicio:
            partes.append(_sem_escape(texto[inicio : achado.start()]))
        partes.append(ler_formula(achado.group(1)))
        inicio = achado.end()
    if inicio < len(texto):
        partes.append(_sem_escape(texto[inicio:]))
    return Paragrafo(tuple(parte for parte in partes if parte != ""), junto=junto)


def ler_formula(texto: str) -> Formula:
    """
    A fórmula escrita na linha: `N = 1700`, `n_0`, `z^2`, `292 / (1 - 0,1)`. Ver o
    docstring do módulo.

    Tolerante de propósito: o que não é número, letra, expoente nem parêntese sai como
    está, em pé, e o parêntese sem par também. Uma fórmula de frase é curta, e um
    caractere inesperado impresso é mais fácil de ver e corrigir do que uma recusa.
    """
    pecas = [peca for peca in _PECA.finditer(texto) if not peca.group("espaco")]
    elementos, _, _ = _ler(pecas, 0, fecha="")
    return Formula(tuple(elementos))


def _ler(pecas: list[re.Match[str]], inicio: int, fecha: str) -> tuple[list[Elemento], int, bool]:
    """
    As peças a partir de `inicio`, até o `fecha` — o `)` de um parêntese aberto, ou o fim.

    Devolve os elementos, a posição seguinte e se o `fecha` apareceu. O que está entre
    parênteses vira `Delimitada`, para os parênteses crescerem com o que têm dentro.
    """
    elementos: list[Elemento] = []
    posicao = inicio
    while posicao < len(pecas):
        peca = pecas[posicao]
        posicao += 1
        outro = peca.group("outro")
        if fecha and outro == fecha:
            return elementos, posicao, True
        if outro == "(":
            dentro, posicao, fechou = _ler(pecas, posicao, fecha=")")
            if fechou:
                elementos.append(Delimitada(Formula(tuple(dentro))))
            else:
                elementos.append(Texto("("))
                elementos.extend(dentro)
        elif peca.group("numero"):
            elementos.append(Texto(peca.group("numero")))
        elif peca.group("palavra"):
            palavra = peca.group("palavra")
            indice = _sem_chaves(peca.group("indice") or "")
            if len(palavra) == 1 or indice:
                elementos.append(Simbolo(palavra, indice))
            else:
                elementos.append(Texto(palavra))
        elif peca.group("expoente"):
            expoente = ler_formula(_sem_chaves(peca.group("expoente")))
            if elementos:
                elementos[-1] = Potencia(formula(elementos[-1]), expoente)
            else:
                elementos.append(Texto("^"))
                elementos.extend(expoente.elementos)
        else:
            elementos.append(Texto(_OPERADORES.get(outro, outro)))
    return elementos, posicao, False


def _sem_chaves(texto: str) -> str:
    return texto[1:-1] if texto.startswith("{") and texto.endswith("}") else texto


def _sem_escape(texto: str) -> str:
    return texto.replace("\\$", "$")


# A fórmula da linha como texto


@dataclass(frozen=True)
class Trecho:
    """
    Um pedaço da fórmula escrita como texto, com a formatação dele: a letra em itálico, o
    índice (`posicao="indice"`) e o expoente (`posicao="expoente"`).
    """

    texto: str
    italico: bool = False
    posicao: str = ""


def tem_fracao(formula_: Formula) -> bool:
    """Se a fórmula tem fração em algum lugar — e por isso não se escreve como texto."""
    for elemento in formula_.elementos:
        if isinstance(elemento, Fracao):
            return True
        if isinstance(elemento, Potencia) and (
            tem_fracao(elemento.base) or tem_fracao(elemento.expoente)
        ):
            return True
        if isinstance(elemento, Delimitada) and tem_fracao(elemento.conteudo):
            return True
    return False


# O espaço de dentro da fórmula escrita como texto: o inquebrável, para a linha não se
# partir no meio da conta — `292 / (1 − 0,1) =` numa linha e `324,44` na outra.
ESPACO_DA_FORMULA = "\u00a0"


def trechos_de(formula_: Formula) -> tuple[Trecho, ...]:
    """
    A fórmula como texto formatado: `N = 1700` é o `N` em itálico, ` = ` e `1700`. Os
    elementos se separam por um espaço, como no `texto_de`, mas o inquebrável
    (`ESPACO_DA_FORMULA`); a fração, que aqui não deveria chegar, sai com barra.
    """
    trechos: list[Trecho] = []
    for posicao, elemento in enumerate(formula_.elementos):
        if posicao:
            trechos.append(Trecho(ESPACO_DA_FORMULA))
        trechos.extend(_trechos_do_elemento(elemento))
    return tuple(trechos)


def _trechos_do_elemento(elemento: Elemento) -> list[Trecho]:
    if isinstance(elemento, Simbolo):
        trechos = [Trecho(elemento.letra, italico=True)]
        if elemento.indice:
            # O índice de letra é itálico, como a letra; o de número, não: n_f e n₀.
            trechos.append(
                Trecho(elemento.indice, italico=not elemento.indice.isdigit(), posicao="indice")
            )
        return trechos
    if isinstance(elemento, Texto):
        return [Trecho(elemento.texto)]
    if isinstance(elemento, Potencia):
        return [*_trechos_agrupados(elemento.base), Trecho(texto_de(elemento.expoente),
                                                            posicao="expoente")]
    if isinstance(elemento, Delimitada):
        return [Trecho(elemento.abre), *trechos_de(elemento.conteudo), Trecho(elemento.fecha)]
    if isinstance(elemento, Fracao):
        return [
            *_trechos_agrupados(elemento.numerador),
            Trecho(f"{ESPACO_DA_FORMULA}/{ESPACO_DA_FORMULA}"),
            *_trechos_agrupados(elemento.denominador),
        ]
    raise TypeError(f"não é uma peça de fórmula: {elemento!r}")


def _trechos_agrupados(formula_: Formula) -> list[Trecho]:
    trechos = list(trechos_de(formula_))
    return [Trecho("("), *trechos, Trecho(")")] if len(formula_.elementos) > 1 else trechos


# O texto de uma fórmula

_SUBSCRITOS = str.maketrans("0123456789+-−=()aehiklmnoprstuvx", "₀₁₂₃₄₅₆₇₈₉₊₋₋₌₍₎ₐₑₕᵢₖₗₘₙₒₚᵣₛₜᵤᵥₓ")
_SOBRESCRITOS = str.maketrans("0123456789+-−=()n", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁻⁼⁽⁾ⁿ")


def texto_de(objeto: str | Elemento | Formula | Bloco) -> str:
    """
    A peça numa linha só, com os índices e os expoentes em caractere Unicode quando ele
    existe: `n₀ = (1,96² × 0,5 × 0,5) / 0,05²`.

    A fração vira barra, com parênteses em volta do lado que tem mais de uma peça. É o
    texto do terminal e dos testes; no documento, a fórmula é equação do Word.
    """
    if isinstance(objeto, str):
        return objeto
    if isinstance(objeto, Simbolo):
        return objeto.letra + _escrito_em(objeto.indice, _SUBSCRITOS, "_")
    if isinstance(objeto, Texto):
        return objeto.texto
    if isinstance(objeto, Fracao):
        return f"{_agrupado(objeto.numerador)} / {_agrupado(objeto.denominador)}"
    if isinstance(objeto, Potencia):
        return _agrupado(objeto.base) + _escrito_em(texto_de(objeto.expoente), _SOBRESCRITOS, "^")
    if isinstance(objeto, Delimitada):
        return f"{objeto.abre}{texto_de(objeto.conteudo)}{objeto.fecha}"
    if isinstance(objeto, Formula):
        return " ".join(texto_de(elemento) for elemento in objeto.elementos)
    if isinstance(objeto, Paragrafo):
        return "".join(texto_de(parte) for parte in objeto.partes)
    if isinstance(objeto, Equacao):
        return texto_de(objeto.formula)
    raise TypeError(f"não é uma peça de fórmula: {objeto!r}")


def _agrupado(formula_: Formula) -> str:
    texto = texto_de(formula_)
    return f"({texto})" if len(formula_.elementos) > 1 else texto


def _escrito_em(texto: str, tabela: dict[int, int], marca: str) -> str:
    """O índice ou o expoente em caractere Unicode, ou depois da marca quando falta algum."""
    if not texto:
        return ""
    convertido = texto.replace(" ", "").translate(tabela)
    alvos = {chr(codigo) for codigo in tabela.values()}
    if all(caractere in alvos for caractere in convertido):
        return convertido
    return f"{marca}{texto}" if len(texto) == 1 else f"{marca}({texto})"


__all__ = [
    "ESPACO_DA_FORMULA",
    "Bloco",
    "Delimitada",
    "Elemento",
    "Equacao",
    "Formula",
    "Fracao",
    "Paragrafo",
    "Potencia",
    "Simbolo",
    "Texto",
    "Trecho",
    "formula",
    "fracao",
    "ler_formula",
    "paragrafo",
    "parenteses",
    "potencia",
    "tem_fracao",
    "teto",
    "texto_de",
    "trechos_de",
]
