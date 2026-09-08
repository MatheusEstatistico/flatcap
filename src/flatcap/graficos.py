"""
Os `.png` da descritiva.

Este módulo **desenha e não calcula**. Ele recebe um `Grafico` com as contagens já
prontas — as barras já contadas, as classes do histograma já cortadas — e o
transforma em imagem. A divisão não é organização: é o que impede o gráfico de
discordar da tabela ao lado dele. Se o desenho recontasse, bastaria uma diferença
de arredondamento para o `.png` dizer 37 e o `.csv` dizer 38 sobre a mesma coisa,
e ninguém confere gráfico contra tabela.

É também o único módulo do pacote que importa o `matplotlib`, e por isso ele é
importado **de dentro** de `executar_descritiva`, e não no topo do `descritiva.py`.
Meio segundo de partida é o preço da biblioteca de desenho, e `--sem-graficos`
existe para não pagá-lo. Mesma decisão que a Fase 4 tomou com o `pandas` na CLI.

Não declara erro próprio, como o `perfil.py`: o que pode falhar aqui é escrita em
disco, que é `OSError`, e quem sabe o que fazer com ela é o `executar_descritiva`
— que desfaz a rodada inteira.

## As decisões de desenho

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
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import TYPE_CHECKING

import matplotlib

# `Agg` antes de qualquer outro import do matplotlib: sem isso a biblioteca
# procura um servidor gráfico, que não existe em terminal nem em servidor, e o
# comando morre por um motivo que não tem nada a ver com estatística.
matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402 - obrigatoriamente depois do `use`
from matplotlib.ticker import MaxNLocator  # noqa: E402

if TYPE_CHECKING:  # só para a anotação: importar `descritiva` aqui criaria um ciclo
    from .descritiva import Grafico

# A paleta. Fundo, tintas e grade de um sistema de visualização conferido; a série
# é a cor de identidade nº 1 dele. Ficam com nome aqui em cima porque trocar a cor
# do FlatCap um dia deve ser trocar estas oito linhas, e não caçar hexadecimal
# dentro das funções.
SUPERFICIE = "#fcfcfb"
TINTA = "#0b0b0b"
TINTA_SECUNDARIA = "#52514e"
TINTA_APAGADA = "#898781"
GRADE = "#e1e0d9"
BASE = "#c3c2b7"
SERIE = "#2a78d6"

LARGURA_POLEGADAS = 6.3  # ~16 cm: a largura útil de uma página A4 com margens
ALTURA_PADRAO = 3.4
ALTURA_MAXIMA = 8.5
DPI = 200

_ESPESSURA_BARRA = 0.58  # o resto da faixa é ar, que é o que separa as barras
_ESPESSURA_COLUNA = 0.78  # a série no tempo é lida como um perfil, e pede menos ar
_LIMITE_ROTULOS_COLUNAS = 12  # acima disso o eixo carrega os valores
_LARGURA_ROTULO = 28  # caracteres antes de quebrar o rótulo de uma categoria

_FONTE = ["DejaVu Sans", "Arial", "sans-serif"]


def versao_do_matplotlib() -> str:
    """
    A versão que desenhou. Vai para o `ambiente` do manifesto.
    """
    return matplotlib.__version__


def desenhar(grafico: Grafico, caminho: Path) -> Path:
    """
    Escreve o `.png` de um `Grafico`. Devolve o caminho escrito.
    """
    caminho = Path(caminho)
    if grafico.especie == "barras":
        figura = _barras(grafico)
    elif grafico.especie == "histograma":
        figura = _histograma(grafico)
    else:
        figura = _colunas(grafico)

    try:
        figura.savefig(
            caminho,
            dpi=DPI,
            facecolor=SUPERFICIE,
            bbox_inches="tight",
            pad_inches=0.18,
        )
    finally:
        plt.close(figura)
    return caminho


# Uma forma por espécie


def _barras(grafico: Grafico):
    """
    Categórica: barras horizontais, na ordem da tabela, com o valor na ponta.

    Horizontais e não verticais porque o rótulo é texto — "Ensino fundamental
    incompleto" cabe deitado e não cabe em pé. A ordem é a de cima para baixo, que
    é a ordem em que a tabela é lida.
    """
    quantas = max(1, len(grafico.categorias))
    altura = min(ALTURA_MAXIMA, max(1.9, 1.15 + 0.34 * quantas))
    figura, eixo = _figura(altura)

    rotulos = [textwrap.fill(str(c), _LARGURA_ROTULO) for c in grafico.categorias]
    posicoes = range(len(rotulos))

    barras = eixo.barh(
        list(posicoes),
        list(grafico.valores),
        height=_ESPESSURA_BARRA,
        color=SERIE,
        linewidth=0,
        zorder=2,
    )
    eixo.bar_label(
        barras,
        labels=list(grafico.rotulos) or None,
        padding=5,
        fontsize=8,
        color=TINTA_SECUNDARIA,
    )

    eixo.set_yticks(list(posicoes))
    eixo.set_yticklabels(rotulos, fontsize=8.5, color=TINTA)
    eixo.invert_yaxis()

    # Sem eixo de valores: todo valor já está escrito na ponta da sua barra, e o
    # eixo seria a mesma informação uma segunda vez.
    eixo.set_xticks([])
    maximo = max(list(grafico.valores) or [1])
    eixo.set_xlim(0, maximo * 1.22 if maximo else 1)

    for lado in ("top", "right", "bottom"):
        eixo.spines[lado].set_visible(False)
    eixo.spines["left"].set_color(BASE)
    eixo.tick_params(axis="y", length=0, pad=6)

    _titulo(eixo, grafico)
    return figura


def _histograma(grafico: Grafico):
    """
    Numérica: a forma da distribuição, em classes calculadas pelo `descritiva.py`.

    As barras se tocam, porque a variável é contínua — o que as separa é um fio da
    cor do fundo, e não um contorno escuro, que acrescentaria tinta sem dado.
    """
    figura, eixo = _figura(ALTURA_PADRAO)

    bordas = list(grafico.bordas)
    larguras = [bordas[i + 1] - bordas[i] for i in range(len(bordas) - 1)]

    eixo.bar(
        bordas[:-1],
        list(grafico.contagens),
        width=larguras,
        align="edge",
        color=SERIE,
        edgecolor=SUPERFICIE,
        linewidth=0.8,
        zorder=2,
    )

    eixo.set_xlabel(grafico.rotulo_categoria, fontsize=8.5, color=TINTA_SECUNDARIA)
    eixo.set_ylabel(grafico.rotulo_valor, fontsize=8.5, color=TINTA_SECUNDARIA)
    _eixo_de_valores(eixo)
    _titulo(eixo, grafico)
    return figura


def _colunas(grafico: Grafico):
    """
    Data: casos por mês ou por ano, em ordem cronológica.

    Verticais, aqui sim: o tempo anda da esquerda para a direita, e um leitor que
    vê meses empilhados na vertical precisa parar para entender a direção.
    """
    figura, eixo = _figura(ALTURA_PADRAO)

    rotulos = [str(c) for c in grafico.categorias]
    posicoes = range(len(rotulos))

    barras = eixo.bar(
        list(posicoes),
        list(grafico.valores),
        width=_ESPESSURA_COLUNA,
        color=SERIE,
        linewidth=0,
        zorder=2,
    )

    if len(rotulos) <= _LIMITE_ROTULOS_COLUNAS and grafico.rotulos:
        eixo.bar_label(
            barras,
            labels=list(grafico.rotulos),
            padding=3,
            fontsize=8,
            color=TINTA_SECUNDARIA,
        )

    eixo.set_xticks(list(posicoes))
    eixo.set_xticklabels(
        rotulos,
        fontsize=8,
        color=TINTA_SECUNDARIA,
        rotation=45 if max((len(r) for r in rotulos), default=0) > 4 else 0,
        ha="right" if max((len(r) for r in rotulos), default=0) > 4 else "center",
    )
    eixo.set_ylabel(grafico.rotulo_valor, fontsize=8.5, color=TINTA_SECUNDARIA)
    _eixo_de_valores(eixo)
    _titulo(eixo, grafico)
    return figura


# Peças comuns


def _figura(altura: float):
    figura, eixo = plt.subplots(figsize=(LARGURA_POLEGADAS, altura), dpi=DPI)
    figura.patch.set_facecolor(SUPERFICIE)
    eixo.set_facecolor(SUPERFICIE)
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = _FONTE
    return figura, eixo


def _eixo_de_valores(eixo) -> None:
    """
    Grade horizontal fina e sólida, atrás das barras, e nenhuma moldura.

    O eixo conta casos, então as marcas são inteiras: `12,5 casos` não existe, e um
    eixo que oferece meio caso faz o leitor procurar o que ele significa.
    """
    eixo.yaxis.set_major_locator(MaxNLocator(integer=True, nbins=6))
    eixo.grid(axis="y", color=GRADE, linewidth=0.8, linestyle="-", zorder=1)
    eixo.set_axisbelow(True)
    for lado in ("top", "right"):
        eixo.spines[lado].set_visible(False)
    eixo.spines["left"].set_color(BASE)
    eixo.spines["bottom"].set_color(BASE)
    eixo.tick_params(colors=TINTA_APAGADA, labelsize=8, length=0)


def _titulo(eixo, grafico: Grafico) -> None:
    """
    Título e subtítulo alinhados à esquerda, acima da área do gráfico.

    Alinhados à esquerda porque a figura vai para dentro de um documento de texto,
    onde tudo o mais começa na margem esquerda — um título centralizado sobre uma
    página justificada lê como um cartaz.
    """
    eixo.set_title(
        grafico.titulo,
        loc="left",
        fontsize=11,
        fontweight="semibold",
        color=TINTA,
        # Folga suficiente para o subtítulo caber embaixo **e** para o rabo de um
        # `_` no nome da variável não cair em cima dele — nome de coluna de banco
        # é cheio de sublinhado, e `data_coleta` sobre `n = 240` risca o número.
        pad=26 if grafico.subtitulo else 10,
    )
    if grafico.subtitulo:
        eixo.annotate(
            grafico.subtitulo,
            xy=(0, 1),
            xytext=(0, 7),
            xycoords="axes fraction",
            textcoords="offset points",
            fontsize=8.5,
            color=TINTA_APAGADA,
            ha="left",
            va="bottom",
        )
