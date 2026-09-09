"""
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

## O contrato com o `template.docx`

A separação template/código é o ponto central da fase no roteiro: *"formatação —
fonte, cores, logotipo, margens, estilos de tabela — vive no `template.docx` e é
ajustada no próprio Word, visualmente. O Python cuida só do conteúdo."*

Aqui isso é levado a sério de um jeito específico: **o modelo manda, e o código se
adapta ao que encontra.** Para cada peça do documento há uma fila de nomes de
estilo, e vence o primeiro que existir no modelo:

    peça       procura, nesta ordem                         se não achar nenhum
    ────────────────────────────────────────────────────────────────────────────
    título     FlatCap Titulo · Title                       negrito 20
    seção      FlatCap Secao · Heading 1                    negrito 14
    corpo      FlatCap Corpo · Normal                       o padrão do modelo
    legenda    FlatCap Legenda · Caption                    itálico 9, cinza
    nota       FlatCap Nota · Caption                       itálico 8,5, cinza
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

## As decisões de apresentação

**Legenda acima da tabela e acima da figura.** É a convenção da ABNT, e é a única
que mantém tabela e figura com a mesma cara em um documento que tem as duas
alternadas. A numeração é contínua e separada — `Tabela 1`, `Tabela 2`,
`Figura 1` — porque é assim que se cita um número no corpo de um e-mail: "veja a
Tabela 3".

**As notas do `.csv` viram uma linha pequena embaixo da tabela.** São os
denominadores, e a resposta do roteiro para *"quando o cliente lê 45%, ele precisa
saber se o denominador incluiu os casos sem resposta"* precisa viajar junto da
tabela — não do arquivo que ficou no disco.

**A última linha da tabela sai em negrito quando é o `Total`.** Uma tabela de
frequência é lida de cima para baixo até o total; é a linha em que o olho para.

**A figura ocupa a largura útil da página, seja qual for o modelo.** A margem é
lida da seção do documento, e não fixada em centímetros: um modelo institucional
com margem de 3 cm receberia uma imagem estourando a mancha se o número fosse
fixo.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import docx
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

if TYPE_CHECKING:  # só para as anotações: importar `relatorio` aqui criaria um ciclo
    from .relatorio import Relatorio, Secao, TabelaLida

# As filas de estilo. O primeiro nome de cada uma é o do FlatCap, que só existe
# se você o criou no modelo; o segundo é o nativo do Word, que existe em quase
# todo `.docx`; o terceiro degrau é a formatação à mão, mais abaixo.
ESTILO_TITULO = ("FlatCap Titulo", "FlatCap Título", "Title")
ESTILO_SECAO = ("FlatCap Secao", "FlatCap Seção", "Heading 1")
ESTILO_CORPO = ("FlatCap Corpo", "Normal")
ESTILO_LEGENDA = ("FlatCap Legenda", "Caption")
ESTILO_NOTA = ("FlatCap Nota", "FlatCap Legenda", "Caption")
ESTILO_TABELA = ("FlatCap Tabela", "Table Grid")

ARQUIVO_TEMPLATE = "template.docx"

# A mesma paleta do `graficos.py`, para que a figura e a página não briguem.
TINTA = RGBColor(0x0B, 0x0B, 0x0B)
TINTA_SECUNDARIA = RGBColor(0x52, 0x51, 0x4E)
TINTA_APAGADA = RGBColor(0x89, 0x87, 0x81)
FUNDO_AVISO = "FBEFC8"  # o amarelo do painel de aviso da CLI, em papel
BORDA = "C3C2B7"

_CORPO_PT = 10.5
_LEGENDA_PT = 9
_NOTA_PT = 8.5
_TABELA_PT = 9.5

_ROTULO_TOTAL = "Total"

# A fonte do documento padrão. Escrita explicitamente, e não herdada do tema do
# `.docx`, porque o tema é o que muda quando o arquivo passa por outra versão do
# Word — e um relatório que sai com serifa numa máquina e sem serifa na outra é
# um relatório que parece defeituoso sem que nada esteja errado. Um modelo
# institucional manda no lugar disto: aqui só se decide o que ninguém decidiu.
FONTE = "Calibri"

# A largura da primeira coluna das tabelas, em fração da mancha. A primeira
# coluna é rótulo — `(abaixo da primeira faixa)`, `Ensino fundamental` — e as
# outras são número. Repartir a largura em partes iguais espremeria o texto e
# daria à coluna `n` um palmo de espaço vazio.
_FATIA_DO_ROTULO = 0.34
_FATIA_MINIMA = 0.18


def versao_do_python_docx() -> str:
    """
    A versão que escreveu o documento. Vai para o `doctor` e para o histórico.
    """
    return getattr(docx, "__version__", "?")


@dataclass(frozen=True)
class Estilos:
    """
    Os estilos que este modelo oferece, já resolvidos.

    `None` quer dizer "o modelo não tem nenhum dos nomes da fila" — e é aí que a
    formatação à mão entra. Resolver tudo de uma vez, antes de escrever a
    primeira linha, é o que impede o documento de sair com metade das legendas
    em um estilo e metade em outro.
    """

    titulo: str | None = None
    secao: str | None = None
    corpo: str | None = None
    legenda: str | None = None
    nota: str | None = None
    tabela: str | None = None


# Escrita


def escrever(relatorio: Relatorio, caminho: Path, template: Path | None = None) -> Path:
    """
    Escreve o `.docx` do relatório. Devolve o caminho escrito.

    Args:
        relatorio: o documento já decidido pelo `relatorio.py`.
        caminho: onde gravar.
        template: o `.docx` que empresta estilos, cabeçalho, rodapé e capa.
            Sem ele, o documento sai com os estilos padrão desta função.
    """
    caminho = Path(caminho)
    documento = _abrir(template)
    estilos = _resolver_estilos(documento)

    _limpar_fim(documento)
    _propriedades(documento, relatorio)

    _paragrafo(
        documento,
        relatorio.titulo,
        estilos.titulo,
        tamanho=20,
        negrito=True,
        cor=TINTA,
        espaco_depois=4,
    )

    _identificacao(documento, relatorio, estilos)

    for alerta in relatorio.alertas:
        _caixa_de_aviso(documento, alerta, estilos)

    numero_tabela = 0
    numero_figura = 0

    for secao in relatorio.secoes:
        cabecalho = _paragrafo(
            documento,
            secao.rotulo,
            estilos.secao,
            tamanho=14,
            negrito=True,
            cor=TINTA,
            espaco_antes=14,
            espaco_depois=2,
        )
        cabecalho.paragraph_format.keep_with_next = True
        _linha_da_variavel(documento, secao, estilos)

        for tabela in secao.tabelas:
            numero_tabela += 1
            _escrever_tabela(documento, tabela, numero_tabela, estilos)

        for figura in secao.figuras:
            numero_figura += 1
            _escrever_figura(documento, figura, numero_figura, estilos)

    _salvar_atomico(documento, caminho)
    return caminho


def _abrir(template: Path | None):
    """
    Abre o modelo, ou monta o documento padrão quando não há modelo.

    Um modelo que não abre — arquivo corrompido, `.doc` antigo renomeado — não
    vira exceção crua: o `python-docx` estoura com `PackageNotFoundError`, que
    não diz nada a quem escolheu o arquivo. Vira `RelatorioError`, com o que
    fazer.
    """
    from .relatorio import RelatorioError

    if template is None:
        return _documento_padrao()

    try:
        return Document(str(template))
    except Exception as erro:  # noqa: BLE001 - o docx estoura de várias formas
        raise RelatorioError(
            f"Não consegui abrir o modelo `{Path(template).name}`.\n\n"
            "As causas comuns são um `.doc` antigo renomeado para `.docx` (abra no "
            "Word e salve como `.docx`), arquivo corrompido, ou um documento "
            "protegido por senha.\n"
            "Rode `flatcap template --sim` para escrever um modelo novo, ou aponte "
            "outro com `--template`.\n\n"
            f"Detalhe técnico: {type(erro).__name__}: {erro}"
        ) from erro


def _documento_padrao():
    """
    O documento de quem ainda não tem modelo: A4, margens de 2,5 cm, rodapé com o
    número da página.

    Deliberadamente sóbrio e sem identidade visual nenhuma. Ele não é o modelo
    institucional nem quer ser: é o que faz o comando funcionar no primeiro dia,
    antes de o `template.docx` existir.

    É exatamente o que o `flatcap template` grava — inclusive os estilos
    `FlatCap *`, que assim ganham a fila e mandam no documento padrão. Sem eles,
    o relatório sem modelo herdaria o `Title` azul de 28 pontos do Word, e o
    documento do primeiro dia sairia com uma cara que ninguém escolheu.
    """
    documento = Document()
    for secao in documento.sections:
        secao.page_height = Cm(29.7)
        secao.page_width = Cm(21.0)
        secao.left_margin = Cm(2.5)
        secao.right_margin = Cm(2.5)
        secao.top_margin = Cm(2.5)
        secao.bottom_margin = Cm(2.0)
        _rodape_com_pagina(secao)

    normal = documento.styles["Normal"]
    normal.font.name = FONTE
    normal.font.size = Pt(_CORPO_PT)
    normal.paragraph_format.space_after = Pt(6)

    _definir_estilos(documento)
    return documento


# As peças do documento


def _identificacao(documento, relatorio: Relatorio, estilos: Estilos) -> None:
    """
    Quem, qual banco, de quando. Uma tabela de duas colunas, sem bordas.

    A linha do banco é a que importa e é o motivo de este bloco existir: é a
    resposta, dentro do documento entregue, para "de qual versão saíram estes
    números?". Sem ela, a decisão de gerar o relatório mesmo quando a rodada está
    velha seria uma decisão sem contrapartida.
    """
    linhas = relatorio.identificacao
    tabela = documento.add_table(rows=len(linhas), cols=2)
    tabela.style = None
    tabela.alignment = WD_TABLE_ALIGNMENT.LEFT
    tabela.autofit = True

    for posicao, (rotulo, valor) in enumerate(linhas):
        esquerda = tabela.cell(posicao, 0).paragraphs[0]
        _texto(esquerda, rotulo, tamanho=_NOTA_PT, cor=TINTA_APAGADA, estilo=estilos.corpo)
        direita = tabela.cell(posicao, 1).paragraphs[0]
        _texto(direita, valor, tamanho=_NOTA_PT, cor=TINTA_SECUNDARIA, estilo=estilos.corpo)
        for celula in (tabela.cell(posicao, 0), tabela.cell(posicao, 1)):
            celula.paragraphs[0].paragraph_format.space_after = Pt(0)

    _fixar_larguras(tabela, (Cm(4.2), _largura_util(documento) - Cm(4.2)))
    documento.add_paragraph()


def _caixa_de_aviso(documento, alerta: Any, estilos: Estilos) -> None:
    """
    Um alerta, em uma caixa amarela de uma célula só.

    Caixa, e não parágrafo em itálico, porque este aviso precisa sobreviver a
    duas coisas: à leitura na diagonal e à impressão em preto e branco. O fundo
    resolve a primeira e o negrito do título resolve a segunda.
    """
    tabela = documento.add_table(rows=1, cols=1)
    tabela.style = None
    celula = tabela.cell(0, 0)
    _sombrear(celula, FUNDO_AVISO)
    _bordas_da_tabela(tabela, cor=BORDA)

    primeiro = celula.paragraphs[0]
    _texto(
        primeiro,
        f"Atenção — {alerta.titulo}",
        tamanho=_NOTA_PT,
        negrito=True,
        cor=TINTA,
        estilo=estilos.corpo,
    )
    primeiro.paragraph_format.space_after = Pt(2)

    for linha in str(alerta.detalhe or "").splitlines():
        if not linha.strip():
            continue
        paragrafo = celula.add_paragraph()
        _texto(paragrafo, linha.strip(), tamanho=_NOTA_PT, cor=TINTA_SECUNDARIA,
               estilo=estilos.corpo)
        paragrafo.paragraph_format.space_after = Pt(0)

    _fixar_larguras(tabela, (_largura_util(documento),))
    documento.add_paragraph()


def _linha_da_variavel(documento, secao: Secao, estilos: Estilos) -> None:
    """
    Uma linha de contexto embaixo do título da seção: n, faltantes e tipo.

    É a única frase que o documento escreve sozinho, e ela não interpreta nada —
    conta. Os números vêm do manifesto, que os recebeu da mesma contagem que
    escreveu as tabelas, então não há como esta linha discordar da tabela logo
    abaixo dela.
    """
    partes = [f"{secao.preenchidos} caso(s) com informação"]
    if secao.faltantes:
        proporcao = secao.faltantes / secao.n if secao.n else 0.0
        partes.append(
            f"{secao.faltantes} sem informação "
            f"({str(round(proporcao * 100, 1)).replace('.', ',')}%)"
        )
    partes.append(f"de {secao.n} linha(s) do banco")

    paragrafo = documento.add_paragraph()
    _texto(
        paragrafo,
        " · ".join(partes),
        tamanho=_NOTA_PT,
        cor=TINTA_APAGADA,
        estilo=estilos.nota or estilos.corpo,
    )
    paragrafo.paragraph_format.space_after = Pt(6)
    paragrafo.paragraph_format.keep_with_next = True


def _escrever_tabela(
    documento, tabela: TabelaLida, numero: int, estilos: Estilos
) -> None:
    """
    Uma tabela do `.csv`, com a legenda em cima e as notas embaixo.

    O texto das células atravessa intacto: `28,7` no arquivo é `28,7` no Word. A
    única decisão de apresentação é o alinhamento — a primeira coluna à esquerda,
    porque é rótulo, e as demais à direita, porque são número e número se lê pela
    unidade.
    """
    _legenda(documento, f"Tabela {numero}. {tabela.titulo}", estilos)

    quadro = documento.add_table(rows=1, cols=max(1, tabela.largura))
    if estilos.tabela:
        quadro.style = estilos.tabela
    else:
        quadro.style = None
        _bordas_da_tabela(quadro, cor=BORDA)
    quadro.alignment = WD_TABLE_ALIGNMENT.LEFT

    for posicao, nome in enumerate(tabela.colunas):
        celula = quadro.rows[0].cells[posicao]
        paragrafo = celula.paragraphs[0]
        _texto(paragrafo, nome, tamanho=_TABELA_PT, negrito=True, cor=TINTA,
               estilo=estilos.corpo)
        _alinhar(paragrafo, posicao)
        paragrafo.paragraph_format.space_after = Pt(0)
    _repetir_cabecalho(quadro.rows[0])

    for valores in tabela.linhas:
        linha = quadro.add_row()
        destaque = bool(valores) and valores[0].strip() == _ROTULO_TOTAL
        for posicao in range(tabela.largura):
            valor = valores[posicao] if posicao < len(valores) else ""
            paragrafo = linha.cells[posicao].paragraphs[0]
            _texto(
                paragrafo,
                valor,
                tamanho=_TABELA_PT,
                negrito=destaque,
                cor=TINTA if destaque else TINTA_SECUNDARIA,
                estilo=estilos.corpo,
            )
            _alinhar(paragrafo, posicao)
            paragrafo.paragraph_format.space_after = Pt(0)

    _repartir_larguras(quadro, _largura_util(documento), tabela.largura)

    if tabela.notas:
        _nota(documento, " · ".join(tabela.notas), estilos)
    else:
        documento.add_paragraph().paragraph_format.space_after = Pt(4)


def _repartir_larguras(quadro, largura_util: int, colunas: int) -> None:
    """
    Dá à coluna do rótulo o espaço que ela precisa, e reparte o resto.

    O Word decide a largura das colunas sozinho quando a tabela está em
    `autofit`, e a conta que ele faz é sobre o texto que está lá: em uma tabela
    de frequência, `% dos válidos` no cabeçalho é mais largo do que qualquer
    número da coluna, e o resultado é uma coluna de rótulos espremida quebrando
    `(sem informação)` em duas linhas ao lado de três colunas de números
    folgadas. Fixar a repartição resolve, e é a única decisão de largura que
    este módulo toma.
    """
    if colunas <= 0 or largura_util <= 0:
        return

    if colunas == 1:
        fatias = [1.0]
    elif colunas == 2:
        fatias = [0.5, 0.5]
    else:
        rotulo = max(_FATIA_MINIMA, min(_FATIA_DO_ROTULO, 1.0 - _FATIA_MINIMA))
        fatias = [rotulo] + [(1.0 - rotulo) / (colunas - 1)] * (colunas - 1)

    _fixar_larguras(quadro, [int(largura_util * fatia) for fatia in fatias])


def _fixar_larguras(quadro, larguras) -> None:
    """
    Aplica largura por coluna e desliga o autoajuste.

    A largura precisa ser escrita em **toda** célula da coluna, e não só no
    `w:gridCol`: o Word obedece ao grid, o LibreOffice obedece à célula, e um
    documento que sai certo em um e torto no outro é um documento que ainda dá
    trabalho.
    """
    quadro.autofit = False
    disposicao = OxmlElement("w:tblLayout")
    disposicao.set(qn("w:type"), "fixed")
    quadro._tbl.tblPr.append(disposicao)

    for posicao, largura in enumerate(larguras):
        quadro.columns[posicao].width = largura
        for celula in quadro.columns[posicao].cells:
            celula.width = largura


def _escrever_figura(documento, figura: Any, numero: int, estilos: Estilos) -> None:
    """
    Uma figura, na largura útil da página do modelo.
    """
    _legenda(documento, f"Figura {numero}. {figura.titulo}", estilos)

    paragrafo = documento.add_paragraph()
    paragrafo.alignment = WD_ALIGN_PARAGRAPH.LEFT
    paragrafo.paragraph_format.space_after = Pt(10)
    paragrafo.add_run().add_picture(str(figura.caminho), width=_largura_util(documento))


def _legenda(documento, texto: str, estilos: Estilos) -> None:
    """
    A legenda de uma tabela ou de uma figura, sempre acima do objeto.

    Quando o modelo tem um estilo de legenda, ele manda inteiro — nem tamanho,
    nem cor, nem negrito são forçados por aqui. É o degrau de baixo da fila que
    escreve à mão, e só ele.
    """
    paragrafo = documento.add_paragraph()
    proprio = bool(estilos.legenda)
    if proprio:
        paragrafo.style = estilos.legenda
    _texto(
        paragrafo,
        texto,
        tamanho=_LEGENDA_PT,
        negrito=not proprio,
        cor=TINTA_SECUNDARIA,
        aplicar_estilo=not proprio,
    )
    paragrafo.paragraph_format.space_before = Pt(8)
    paragrafo.paragraph_format.space_after = Pt(3)
    # Legenda nunca fica órfã no pé da página: ela anda com o objeto que nomeia.
    # Sem isto, `Figura 2. Escolaridade` termina uma página e a figura começa a
    # seguinte — e quem lê passa a página procurando o que a legenda prometeu.
    paragrafo.paragraph_format.keep_with_next = True


def _nota(documento, texto: str, estilos: Estilos) -> None:
    paragrafo = documento.add_paragraph()
    proprio = bool(estilos.nota)
    if proprio:
        paragrafo.style = estilos.nota
    _texto(
        paragrafo,
        texto,
        tamanho=_NOTA_PT,
        italico=not proprio,
        cor=TINTA_APAGADA,
        aplicar_estilo=not proprio,
    )
    paragrafo.paragraph_format.space_before = Pt(2)
    paragrafo.paragraph_format.space_after = Pt(8)


# Peças de baixo nível


def _paragrafo(
    documento,
    texto: str,
    estilo: str | None,
    tamanho: float | None = None,
    negrito: bool = False,
    italico: bool = False,
    cor: RGBColor | None = None,
    espaco_antes: float | None = None,
    espaco_depois: float | None = None,
):
    paragrafo = documento.add_paragraph()
    if estilo:
        paragrafo.style = estilo
    _texto(paragrafo, texto, tamanho, negrito, italico, cor, aplicar_estilo=not estilo)
    if espaco_antes is not None:
        paragrafo.paragraph_format.space_before = Pt(espaco_antes)
    if espaco_depois is not None:
        paragrafo.paragraph_format.space_after = Pt(espaco_depois)
    return paragrafo


def _texto(
    paragrafo,
    conteudo: str,
    tamanho: float | None = None,
    negrito: bool = False,
    italico: bool = False,
    cor: RGBColor | None = None,
    estilo: str | None = None,
    aplicar_estilo: bool = True,
):
    """
    Escreve o texto e formata à mão só o que o estilo não resolveu.

    O `aplicar_estilo` é o degrau de baixo da fila de estilos: quando a peça
    encontrou um estilo no modelo, a formatação à mão **não** é aplicada — senão
    o código passaria por cima da decisão que você tomou no Word, que é
    exatamente o que a separação template/código existe para impedir. Tamanho e
    cor só entram quando não há estilo para mandar neles.
    """
    if estilo:
        try:
            paragrafo.style = estilo
        except KeyError:  # pragma: no cover - o estilo veio da resolução
            pass

    trecho = paragrafo.add_run(str(conteudo))
    if negrito:
        trecho.bold = True
    if italico:
        trecho.italic = True
    if aplicar_estilo:
        if tamanho is not None:
            trecho.font.size = Pt(tamanho)
        if cor is not None:
            trecho.font.color.rgb = cor
    return trecho


def _alinhar(paragrafo, posicao: int) -> None:
    paragrafo.alignment = (
        WD_ALIGN_PARAGRAPH.LEFT if posicao == 0 else WD_ALIGN_PARAGRAPH.RIGHT
    )


def _largura_util(documento):
    """
    A mancha da página: largura menos as duas margens, lida da seção.
    """
    secao = documento.sections[-1]
    return secao.page_width - secao.left_margin - secao.right_margin


def _resolver_estilos(documento) -> Estilos:
    """
    Percorre as filas e devolve o primeiro nome que o modelo tem.
    """
    disponiveis = {estilo.name for estilo in documento.styles}

    def primeiro(fila: tuple[str, ...]) -> str | None:
        for nome in fila:
            if nome in disponiveis:
                return nome
        return None

    return Estilos(
        titulo=primeiro(ESTILO_TITULO),
        secao=primeiro(ESTILO_SECAO),
        corpo=primeiro(ESTILO_CORPO),
        legenda=primeiro(ESTILO_LEGENDA),
        nota=primeiro(ESTILO_NOTA),
        tabela=primeiro(ESTILO_TABELA),
    )


def _limpar_fim(documento) -> None:
    """
    Descarta os parágrafos vazios do fim do modelo.

    Todo `.docx` salvo pelo Word termina com pelo menos um parágrafo vazio, e
    alguns modelos terminam com meia dúzia. Sem isto, o relatório começaria
    depois de um punhado de linhas em branco — às vezes depois de uma página
    inteira em branco, o que faz o documento parecer defeituoso já na abertura.
    """
    for paragrafo in reversed(documento.paragraphs):
        if paragrafo.text.strip() or paragrafo._element.findall(qn("w:r")):
            break
        pai = paragrafo._element.getparent()
        if pai is not None:
            pai.remove(paragrafo._element)


def _propriedades(documento, relatorio: Relatorio) -> None:
    """
    Os metadados do arquivo, que o Windows mostra sem ninguém abrir o documento.
    """
    from . import __version__

    ficha = relatorio.ficha
    propriedades = documento.core_properties
    propriedades.title = f"{relatorio.titulo} — {ficha.nome or ficha.matricula}"
    propriedades.subject = f"Matrícula {ficha.matricula} · registro {ficha.record_id}"
    propriedades.comments = (
        f"Gerado por FlatCap {__version__} a partir da descritiva de "
        f"{relatorio.manifesto.gerado_em:%d/%m/%Y %H:%M} · banco "
        f"{relatorio.manifesto.banco.get('arquivo', '?')}"
    )


def _salvar_atomico(documento, caminho: Path) -> None:
    """
    Grava o documento inteiro ou não grava nada.

    Mesma garantia do `escrever_atomico` do `ficha.py`, e pelo mesmo motivo: o
    temporário é criado na **mesma pasta** do destino, porque `os.replace` só é
    atômico dentro do mesmo sistema de arquivos. Meio `.docx` não é um documento
    incompleto — é um arquivo que o Word se recusa a abrir.
    """
    import os
    import tempfile

    caminho = Path(caminho)
    temporario: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=caminho.parent,
            prefix=caminho.name + ".",
            suffix=".tmp",
            delete=False,
        ) as arquivo:
            temporario = Path(arquivo.name)
        documento.save(str(temporario))
        os.replace(temporario, caminho)
        temporario = None
    finally:
        if temporario is not None and temporario.exists():
            temporario.unlink(missing_ok=True)


# XML que a API do python-docx não expõe


def _repetir_cabecalho(linha) -> None:
    """
    Marca a primeira linha como cabeçalho, para o Word repeti-la a cada página.

    A tabela de distribuição no tempo de um estudo de dois anos tem 24 linhas e
    atravessa a quebra de página com frequência. Sem o cabeçalho repetido, a
    metade de baixo é uma coluna de números sem nome.
    """
    propriedades = linha._tr.get_or_add_trPr()
    marca = OxmlElement("w:tblHeader")
    marca.set(qn("w:val"), "true")
    propriedades.append(marca)


def _sombrear(celula, cor: str) -> None:
    sombra = OxmlElement("w:shd")
    sombra.set(qn("w:val"), "clear")
    sombra.set(qn("w:color"), "auto")
    sombra.set(qn("w:fill"), cor)
    celula._tc.get_or_add_tcPr().append(sombra)


def _bordas_da_tabela(tabela, cor: str, espessura: int = 4) -> None:
    """
    Bordas escritas à mão, para quando o modelo não tem estilo de tabela.

    É o último degrau da fila de estilos. Um modelo institucional em que ninguém
    nunca inseriu uma tabela não traz a definição do `Table Grid` — o Word só
    grava os estilos que o documento usou —, e sem isto o relatório sairia com
    tabelas sem nenhuma linha separando as colunas.
    """
    propriedades = tabela._tbl.tblPr
    bordas = OxmlElement("w:tblBorders")
    for lado in ("top", "left", "bottom", "right", "insideH", "insideV"):
        elemento = OxmlElement(f"w:{lado}")
        elemento.set(qn("w:val"), "single")
        elemento.set(qn("w:sz"), str(espessura))
        elemento.set(qn("w:space"), "0")
        elemento.set(qn("w:color"), cor)
        bordas.append(elemento)
    propriedades.append(bordas)


def _rodape_com_pagina(secao) -> None:
    """
    O rodapé do documento padrão: `página N`, centralizado.

    O número da página é um campo do Word, e campo não é texto: ele é escrito
    como instrução (`PAGE`) e o Word calcula na hora de exibir. Escrever o número
    à mão daria "página 1" em todas as páginas.
    """
    paragrafo = secao.footer.paragraphs[0]
    paragrafo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    trecho = paragrafo.add_run("página ")
    trecho.font.size = Pt(_NOTA_PT)
    trecho.font.color.rgb = TINTA_APAGADA
    _campo(paragrafo, "PAGE", tamanho=_NOTA_PT)


def _campo(paragrafo, instrucao: str, tamanho: float | None = None) -> None:
    trecho = paragrafo.add_run()
    if tamanho is not None:
        trecho.font.size = Pt(tamanho)
        trecho.font.color.rgb = TINTA_APAGADA

    inicio = OxmlElement("w:fldChar")
    inicio.set(qn("w:fldCharType"), "begin")
    texto = OxmlElement("w:instrText")
    texto.set(qn("xml:space"), "preserve")
    texto.text = f" {instrucao} "
    fim = OxmlElement("w:fldChar")
    fim.set(qn("w:fldCharType"), "end")

    trecho._r.append(inicio)
    trecho._r.append(texto)
    trecho._r.append(fim)


# O modelo


def escrever_template(caminho: Path) -> Path:
    """
    Escreve um `template.docx` com os estilos do FlatCap já definidos.

    O corpo sai **vazio**, de propósito: tudo o que estiver no corpo do modelo
    aparece antes do relatório, em todo relatório. Um modelo com instruções
    dentro imprimiria as instruções em cima do documento que você entrega.

    O que ele traz é o que se ajusta no Word: página, margens, cabeçalho,
    rodapé com o número da página, e os cinco estilos `FlatCap *` que o relatório
    procura antes de qualquer outro. Mude a fonte de `FlatCap Corpo` e o
    documento inteiro muda; ponha o logotipo no cabeçalho e ele aparece em todas
    as páginas de todos os relatórios.
    """
    caminho = Path(caminho)
    documento = _documento_padrao()

    cabecalho = documento.sections[0].header.paragraphs[0]
    trecho = cabecalho.add_run("Assessoria estatística")
    trecho.font.size = Pt(_NOTA_PT)
    trecho.font.color.rgb = TINTA_APAGADA
    cabecalho.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    _salvar_atomico(documento, caminho)
    return caminho


def _definir_estilos(documento) -> None:
    """
    Cria os estilos `FlatCap *`, cada um herdando de um nativo do Word.

    Herdar importa: um estilo criado do zero não tem fonte, tamanho nem idioma, e
    o Word preenche esses buracos com o que estiver por perto — o que faz o
    documento mudar de cara quando você mexe em outra coisa. Herdando de `Normal`
    e dos títulos nativos, cada estilo começa exatamente igual ao que o Word já
    faria, e a personalização é uma diferença explícita a partir dali.
    """
    from docx.enum.style import WD_STYLE_TYPE

    estilos = documento.styles

    def criar(nome: str, base: str, tipo=WD_STYLE_TYPE.PARAGRAPH):
        if nome in {estilo.name for estilo in estilos}:
            return estilos[nome]
        novo = estilos.add_style(nome, tipo)
        try:
            novo.base_style = estilos[base]
        except KeyError:  # pragma: no cover - as bases são nativas do Word
            pass
        return novo

    corpo = criar("FlatCap Corpo", "Normal")
    corpo.font.name = FONTE
    corpo.font.size = Pt(_CORPO_PT)
    corpo.font.color.rgb = TINTA
    corpo.paragraph_format.space_after = Pt(6)

    titulo = criar("FlatCap Titulo", "Title")
    titulo.font.name = FONTE
    titulo.font.size = Pt(20)
    titulo.font.bold = True
    titulo.font.color.rgb = TINTA

    secao = criar("FlatCap Secao", "Heading 1")
    secao.font.name = FONTE
    secao.font.size = Pt(14)
    secao.font.bold = True
    secao.font.color.rgb = TINTA
    secao.paragraph_format.space_before = Pt(14)
    secao.paragraph_format.space_after = Pt(2)

    legenda = criar("FlatCap Legenda", "Caption")
    legenda.font.name = FONTE
    legenda.font.size = Pt(_LEGENDA_PT)
    legenda.font.bold = True
    legenda.font.italic = False
    legenda.font.color.rgb = TINTA_SECUNDARIA

    nota = criar("FlatCap Nota", "Caption")
    nota.font.name = FONTE
    nota.font.size = Pt(_NOTA_PT)
    nota.font.italic = True
    nota.font.color.rgb = TINTA_APAGADA


__all__ = [
    "ARQUIVO_TEMPLATE",
    "Estilos",
    "escrever",
    "escrever_template",
    "versao_do_python_docx",
]
