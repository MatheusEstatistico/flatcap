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

## Este módulo desenha para qualquer análise, e nunca escolhe a pasta

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

# A fonte dos gráficos.
#
# Arial primeiro, e a ordem é a correção: a lista anterior começava por
# `DejaVu Sans`, que vem dentro do próprio matplotlib e por isso está **sempre**
# instalado — o Arial nunca chegava a ser tentado. O resultado era um relatório
# com o texto em uma fonte e as figuras em outra, sem nada no código dizendo que
# a escolha tinha sido essa.
#
# Os três nomes do meio são rede, na ordem em que fazem sentido: `Liberation
# Sans` tem as mesmas métricas do Arial e é o que existe em Linux, `Helvetica`
# cobre o macOS, e o `DejaVu Sans` fecha a lista porque não desenhar é pior do
# que desenhar com outra fonte.
FONTE = ("Arial", "Liberation Sans", "Helvetica", "DejaVu Sans", "sans-serif")

# A configuração de aparência mora aqui em cima, com a paleta, onde se acha sem
# procurar — mas ela **não** é escrita no `rcParams` global, e essa é a correção.
#
# `rcParams` é estado do processo inteiro. Escrevê-lo no import fazia o simples
# ato de `import flatcap.graficos` mudar a fonte de qualquer figura que qualquer
# outra parte do processo viesse a desenhar — um notebook que importasse o
# FlatCap para olhar um manifesto sairia com os próprios gráficos em Arial, sem
# nada dizendo por quê. Um módulo que desenha não tem o direito de decidir pelo
# processo; ele decide pela figura dele.
#
# O `rc_context` do `desenhar` aplica isto enquanto a figura é montada **e**
# salva, e devolve o estado no fim. Os dois dentro do mesmo contexto de
# propósito: o matplotlib só resolve a fonte na hora de desenhar, e quem desenha
# é o `savefig`.
APARENCIA: dict[str, object] = {
    "font.family": "sans-serif",
    "font.sans-serif": list(FONTE),
}

import matplotlib.pyplot as plt  # noqa: E402 - obrigatoriamente depois do `use`
from matplotlib.ticker import MaxNLocator  # noqa: E402

if TYPE_CHECKING:  # só para a anotação; em tempo de execução nada disto é carregado
    from .manifesto import Grafico

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
SERIE = "#4b9b69"

LARGURA_POLEGADAS = 6.3  # ~16 cm: a largura útil de uma página A4 com margens
ALTURA_PADRAO = 3.4
ALTURA_MAXIMA = 8.5
DPI = 600

_ESPESSURA_BARRA = 0.58  # o resto da faixa é ar, que é o que separa as barras
_ESPESSURA_COLUNA = 0.78  # a série no tempo é lida como um perfil, e pede menos ar
_LIMITE_ROTULOS_COLUNAS = 12  # acima disso o eixo carrega os valores
_LARGURA_ROTULO = 28  # caracteres antes de quebrar o rótulo de uma categoria

# O ponto do Q-Q. Pequeno e sem contorno: em uma amostra de duzentos casos os
# pontos do miolo se encostam, e um contorno escuro em cada um transformaria o
# centro da nuvem em um borrão — que é justamente a parte que precisa ser lida
# como uma linha reta.
_PONTO_QQ = 9
_ALTURA_QQ = 3.6  # um dedo a mais que o padrão: o Q-Q é lido como um quadrado

# O ponto da dispersão. A área cresce com o número de casos que caem no mesmo lugar
# — área, e não raio, porque é a área que o olho compara —, e o maior ponto tem um
# teto: numa escala de 0 a 5 com 500 casos, um ponto de área proporcional sem teto
# cobriria o gráfico. Quando o teto aperta, todos encolhem na mesma proporção, e o
# ponto de um caso só continua visível.
_PONTO_DISPERSAO = 12
_AREA_MAXIMA_DISPERSAO = 320
_ALTURA_DISPERSAO = 3.6


def versao_do_matplotlib() -> str:
    """
    A versão que desenhou. Vai para o `ambiente` do manifesto.
    """
    return matplotlib.__version__


def fonte_dos_graficos() -> str:
    """
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
    """
    from matplotlib import font_manager

    caminho = font_manager.findfont(font_manager.FontProperties(family=list(FONTE)))
    return font_manager.FontProperties(fname=caminho).get_name()


def desenhar(grafico: Grafico, caminho: Path) -> Path:
    """
    Escreve o `.png` de um `Grafico`, onde quer que o chamador tenha pedido.

    O caminho é parâmetro, e é a razão de este módulo servir a qualquer análise
    sem saber que elas existem: a descritiva passa `3. Análises/descritiva/`, a
    normalidade passa `3. Análises/normalidade/`, e a decisão de onde o arquivo
    mora continua sendo de quem calculou os números.

    Espécie que não está no registro estoura, e de propósito — ver o topo do
    módulo. A mensagem diz a espécie pedida e as que existem, porque o erro
    acontece enquanto alguém escreve uma análise nova e o que ele precisa ler é
    "você escreveu `qqplot` e o nome é `qq`".
    """
    caminho = Path(caminho)

    forma = _FORMAS.get(grafico.especie)
    if forma is None:
        raise ValueError(
            f"Espécie de gráfico desconhecida: {grafico.especie!r} "
            f"(em `{grafico.nome}`). As que existem: "
            f"{', '.join(sorted(_FORMAS))}."
        )

    # Montar e salvar dentro do mesmo contexto. A aparência vale para esta figura
    # e não fica no processo depois dela — ver `APARENCIA`.
    with plt.rc_context(APARENCIA):
        figura = forma(grafico)
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


def _qq(grafico: Grafico):
    """
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
    """
    figura, eixo = _figura(_ALTURA_QQ)

    eixo.scatter(
        list(grafico.pontos_x),
        list(grafico.pontos_y),
        s=_PONTO_QQ,
        color=SERIE,
        linewidths=0,
        zorder=3,
    )

    if grafico.reta is not None and grafico.pontos_x:
        # Os pontos primeiro, e o limite do eixo lido **deles** antes de a reta
        # entrar. A reta é uma referência infinita cortada nos extremos do eixo x,
        # e nos extremos ela sai do intervalo de valores que a variável tem: em uma
        # escala de dor de 0 a 5, a reta desce até −3 e o matplotlib alargava o eixo
        # para caber, oferecendo `−2,5` de dor a quem lê. É o mesmo defeito que o
        # eixo de `12,5 casos` da Fase 5, e a correção é a mesma — o eixo mostra o
        # que a variável tem, e o que sobra da reta é cortado.
        limites = eixo.get_ylim()
        intercepto, inclinacao = grafico.reta
        extremos = (min(grafico.pontos_x), max(grafico.pontos_x))
        eixo.plot(
            extremos,
            [intercepto + inclinacao * x for x in extremos],
            color=TINTA_APAGADA,
            linewidth=1.0,
            zorder=2,
        )
        eixo.set_ylim(limites)

    eixo.set_xlabel(
        grafico.rotulo_categoria or "quantis esperados da normal",
        fontsize=8.5,
        color=TINTA_SECUNDARIA,
    )
    eixo.set_ylabel(grafico.rotulo_valor, fontsize=8.5, color=TINTA_SECUNDARIA)
    # `inteiro=False`: aqui o eixo carrega os valores da variável, e `12,5 kg`
    # existe. A regra das marcas inteiras é do eixo que conta casos.
    _eixo_de_valores(eixo, inteiro=False)
    _titulo(eixo, grafico)
    return figura


def _dispersao(grafico: Grafico):
    """
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
    """
    figura, eixo = _figura(_ALTURA_DISPERSAO)

    xs = list(grafico.pontos_x)
    ys = list(grafico.pontos_y)
    quantos = list(grafico.contagens) or [1] * len(xs)
    maior = max(quantos, default=1)
    unidade = min(_PONTO_DISPERSAO, _AREA_MAXIMA_DISPERSAO / maior)

    eixo.scatter(
        xs,
        ys,
        s=[unidade * q for q in quantos],
        color=SERIE,
        alpha=0.8,
        edgecolors=SUPERFICIE,
        linewidths=0.5 if maior > 1 else 0,
        zorder=3,
    )

    eixo.set_xlabel(grafico.rotulo_categoria, fontsize=8.5, color=TINTA_SECUNDARIA)
    eixo.set_ylabel(grafico.rotulo_valor, fontsize=8.5, color=TINTA_SECUNDARIA)
    _eixo_de_valores(eixo, inteiro=_todos_inteiros(ys))
    eixo.xaxis.set_major_locator(MaxNLocator(integer=_todos_inteiros(xs), nbins=6))
    _titulo(eixo, grafico)
    return figura


def _todos_inteiros(valores: list[float]) -> bool:
    return bool(valores) and all(float(valor).is_integer() for valor in valores)


# O registro das espécies.
#
# Aqui embaixo, e não no topo do arquivo, porque ele nomeia funções que precisam
# já existir. É a única coisa do módulo que a espécie nova toca: escrever a função
# e acrescentar uma linha aqui é o trabalho inteiro — foi o que a dispersão da
# correlação fez.
_FORMAS = {
    "barras": _barras,
    "histograma": _histograma,
    "colunas": _colunas,
    "qq": _qq,
    "dispersao": _dispersao,
}


# Peças comuns


def _figura(altura: float):
    figura, eixo = plt.subplots(figsize=(LARGURA_POLEGADAS, altura), dpi=DPI)
    figura.patch.set_facecolor(SUPERFICIE)
    eixo.set_facecolor(SUPERFICIE)
    return figura, eixo


def _eixo_de_valores(eixo, inteiro: bool = True) -> None:
    """
    Grade horizontal fina e sólida, atrás das barras, e nenhuma moldura.

    O eixo conta casos, então as marcas são inteiras: `12,5 casos` não existe, e um
    eixo que oferece meio caso faz o leitor procurar o que ele significa.

    `inteiro=False` é para o eixo que **não** conta casos. No Q-Q ele carrega os
    valores da própria variável, onde `12,5 kg` existe e é o que se quer ler —
    forçar marcas inteiras ali daria um eixo de `70, 71, 72` em uma variável que
    vai de 70,1 a 72,4, e a nuvem inteira caberia entre duas marcas.
    """
    if inteiro:
        eixo.yaxis.set_major_locator(MaxNLocator(integer=True, nbins=6))
    else:
        eixo.yaxis.set_major_locator(MaxNLocator(nbins=6))
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
        # `bold`, e não `semibold`: o Arial tem Regular e Bold e mais nada. Um
        # peso 600 pedido a uma família que não o tem é resolvido pelo matplotlib
        # por aproximação, e a aproximação muda conforme as fontes instaladas na
        # máquina — o mesmo banco sairia com o título mais gordo no seu Windows
        # do que no de outra pessoa.
        fontweight="bold",
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
