# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
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

## As decisões de apresentação

**Legenda acima da tabela e acima da figura.** É a convenção da ABNT, e é a única
que mantém tabela e figura com a mesma cara em um documento que tem as duas
alternadas. A numeração é contínua e separada — `Tabela 1`, `Tabela 2`,
`Figura 1` — porque é assim que se cita um número no corpo de um e-mail: "veja a
Tabela 3".

**A primeira página é título, subtítulo, alertas e o texto padrão.** Nessa ordem:
o alerta vem antes do texto de abertura porque ele é a única coisa da página que
pode fazer alguém parar de enviar o documento.

**A última linha da tabela sai em negrito quando é o `Total`.** Uma tabela de
frequência é lida de cima para baixo até o total; é a linha em que o olho para.

**A figura ocupa a largura útil da página, seja qual for o modelo.** A margem é
lida da seção do documento, e não fixada em centímetros: um modelo institucional
com margem de 3 cm receberia uma imagem estourando a mancha se o número fosse
fixo.
"""

from __future__ import annotations

import re
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

from .projeto import ARQUIVO_TEMPLATE

if TYPE_CHECKING:  # só para as anotações: importar `relatorio` aqui criaria um ciclo
    from .relatorio import Relatorio, TabelaLida

# As filas de estilo. O primeiro nome de cada uma é o do FlatCap, que só existe
# se você o criou no modelo; o segundo é o nativo do Word, que existe em quase
# todo `.docx`; o terceiro degrau é a formatação à mão, mais abaixo.
ESTILO_TITULO = ("FlatCap Titulo", "FlatCap Título", "Title")
ESTILO_SUBTITULO = ("FlatCap Subtitulo", "FlatCap Subtítulo", "Subtitle")
ESTILO_SECAO = ("FlatCap Secao", "FlatCap Seção", "Heading 1")
ESTILO_CORPO = ("FlatCap Corpo", "Normal")
ESTILO_LEGENDA = ("FlatCap Legenda", "Caption")
ESTILO_TABELA = ("FlatCap Tabela", "Table Grid")

# `ARQUIVO_TEMPLATE` é importado do `projeto.py`, lá em cima, e reexportado por
# este módulo — é daqui que ele sempre foi importado. Ele estava escrito duas
# vezes: aqui e no `relatorio.py`, que não pode importar este módulo no topo sem
# trazer o `python-docx` para uma simulação que não escreve documento nenhum.
# Duas grafias do mesmo nome de arquivo é como um comando passa a procurar um
# modelo que o outro comando não grava.

# A folha de decisões que mora ao lado do modelo.
#
# Existe porque um `.docx` é binário: não aceita comentário, não entra no Git e
# não conta a ninguém por que está do jeito que está. O corpo do modelo também
# não serve para isso — ele é impresso em todo relatório. Então as razões moram
# em um arquivo de texto ao lado, que é onde a próxima pessoa vai olhar.
ARQUIVO_DECISOES = "template-decisoes.md"

# A mesma paleta do `graficos.py`, para que a figura e a página não briguem.
TINTA = RGBColor(0x0B, 0x0B, 0x0B)
TINTA_SECUNDARIA = RGBColor(0x52, 0x51, 0x4E)
TINTA_APAGADA = RGBColor(0x89, 0x87, 0x81)
FUNDO_AVISO = "FBEFC8"  # o amarelo do painel de aviso da CLI, em papel
BORDA = "C3C2B7"
TINTA_LINHA = "0B0B0B"  # as réguas da tabela, na mesma tinta do texto

# O fundo da linha `Total`.
#
# Esta cor mora no código, e não no `template.docx`, e a exceção tem motivo. O
# Word sabe pintar a última linha de uma tabela — é a banda «Última linha» do
# estilo. Mas a última linha nem sempre é o `Total`: no resumo de uma numérica
# ela é `Q3`, e a banda pintaria o desvio-padrão de verde. O destaque depende do
# **conteúdo** da célula, e conteúdo é justamente o que o estilo não enxerga.
#
# O texto por cima é escrito em `TINTA`, e isso também precisa ser dito. Sem cor
# explícita o Word usa a cor «automática», que ele inverte para branco sobre
# fundo escuro — e branco sobre este verde dá contraste 3,4:1, abaixo dos 4,5:1
# que se pede para texto de corpo. Em preto o contraste é 6,2:1.
FUNDO_TOTAL = "4B9B69"

# As três linhas da tabela: topo, sob o cabeçalho, base. Nenhuma vertical.
_REGUA_GROSSA = 12  # oitavos de ponto — topo e base
_REGUA_FINA = 4     # sob o cabeçalho

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
#
# É a mesma do `graficos.FONTE`, e tem de continuar sendo: o texto do documento e
# os rótulos das figuras ficam a dois centímetros um do outro na mesma página.
FONTE = "Arial"

# O que vai escrito no cabeçalho do modelo padrão. Uma linha, discreta, no canto
# direito — é onde a identidade institucional entra sem custar uma página inteira.
# Quem tiver logotipo troca esta linha por ele, no Word.
CABECALHO_PADRAO = "Assessoria estatística"

# Até este tamanho, a tabela não se parte na quebra de página. Acima dele, ela
# se parte e o cabeçalho se repete — uma distribuição no tempo de dois anos tem
# 24 linhas, e forçá-la inteira para a página seguinte deixaria meia página em
# branco para não ganhar nada.
_LINHAS_PARA_MANTER_JUNTA = 12

# A largura da primeira coluna das tabelas, em fração da mancha. A primeira
# coluna é rótulo — `(abaixo da primeira faixa)`, `Ensino fundamental` — e as
# outras são número. Repartir a largura em partes iguais espremeria o texto e
# daria à coluna `n` um palmo de espaço vazio.
_FATIA_DO_ROTULO = 0.34
_FATIA_MINIMA = 0.18

# A repartição pelo conteúdo, das tabelas com mais de uma coluna de texto. São
# estimativas para Arial 9,5 — a fonte das tabelas —, com folga: um número que
# quebra no meio é pior do que uma coluna um pouco mais larga do que precisava.
_EMU_POR_CM = 360000
_CM_POR_CARACTERE = 0.19
_RESPIRO_CM = 0.4           # as margens da célula, 0,12 de cada lado, e um fio de ar
_MINIMO_NUMERICO_CM = 1.2   # para a coluna `n` não virar um fio
_TEXTO_NATURAL = 40         # caracteres: acima disto, a coluna de texto aceita quebrar

# Um caractere a mais para a palavra mais longa de uma coluna de texto. Os 0,19 cm
# são a média, e palavra com `m`, `w` ou maiúscula passa dela: `Spearman`, na coluna
# `método` da correlação, pedia 1,55 cm de texto e recebia 1,52 — e saía partida em
# `Spearma` e `n`. A folga vale só para o piso, que é a promessa de "palavra curta
# não quebra"; o resto da repartição continua na média.
_FOLGA_DA_PALAVRA = 1


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
    subtitulo: str | None = None
    secao: str | None = None
    corpo: str | None = None
    legenda: str | None = None
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
        espaco_depois=2,
    )

    if relatorio.subtitulo:
        _paragrafo(
            documento,
            relatorio.subtitulo,
            estilos.subtitulo,
            tamanho=13,
            cor=TINTA_SECUNDARIA,
            espaco_depois=16,
        )

    for alerta in relatorio.alertas:
        _caixa_de_aviso(documento, alerta, estilos)

    # A primeira página já tem conteúdo? É disso que depende a quebra antes da
    # primeira seção, mais abaixo. O texto de abertura responde quase sempre; o
    # alerta responde no caso em que ele não existe, porque uma página com uma
    # caixa amarela dentro não é uma página em branco.
    abriu = _texto_padrao(documento, relatorio, estilos) or bool(relatorio.alertas)

    numero_tabela = 0
    numero_figura = 0

    for posicao, secao in enumerate(relatorio.secoes):
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

        # A primeira variável começa em página nova, para que a abertura fique
        # sozinha na primeira. É `page_break_before` no título, e não um
        # parágrafo de quebra atrás dele: um parágrafo a mais deixaria a marca
        # dele no alto da página seguinte, empurrando o título para baixo, e
        # sobraria no documento se um dia o texto de abertura sumisse.
        if posicao == 0 and abriu:
            cabecalho.paragraph_format.page_break_before = True

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
    _fonte_do_estilo(normal)
    normal.font.size = Pt(_CORPO_PT)
    normal.paragraph_format.space_after = Pt(6)

    _fixar_tema(documento)
    _definir_estilos(documento)
    return documento


# As peças do documento


def _texto_padrao(documento, relatorio: Relatorio, estilos: Estilos) -> bool:
    """
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
    """
    escreveu = False
    for paragrafo in relatorio.texto:
        if not paragrafo.strip():
            continue
        escrito = documento.add_paragraph()
        if estilos.corpo:
            escrito.style = estilos.corpo
        _texto(escrito, paragrafo.strip(), aplicar_estilo=False)
        escrito.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        escrito.paragraph_format.space_after = Pt(8)
        escreveu = True
    return escreveu


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


def _escrever_tabela(
    documento, tabela: TabelaLida, numero: int, estilos: Estilos
) -> None:
    """
    Uma tabela do `.csv`, com a legenda em cima. As notas do `.csv` não vêm
    junto: ver o comentário no fim da função.

    O texto das células atravessa intacto: `28,7` no arquivo é `28,7` no Word. A
    única decisão de apresentação é o alinhamento — texto à esquerda, porque se lê
    pelo começo, e número à direita, porque se lê pela unidade. Ver
    `_colunas_de_texto`.
    """
    _legenda(documento, f"Tabela {numero}. {tabela.titulo}", estilos)
    de_texto = _colunas_de_texto(tabela)

    quadro = documento.add_table(rows=1, cols=max(1, tabela.largura))
    if estilos.tabela:
        quadro.style = estilos.tabela
    else:
        quadro.style = None
        _bordas_de_tres_linhas(quadro, cor=TINTA_LINHA)
    quadro.alignment = WD_TABLE_ALIGNMENT.LEFT

    for posicao, nome in enumerate(tabela.colunas):
        celula = quadro.rows[0].cells[posicao]
        paragrafo = celula.paragraphs[0]
        _texto(paragrafo, nome, tamanho=_TABELA_PT, negrito=True, cor=TINTA,
               estilo=estilos.corpo)
        _alinhar(paragrafo, posicao in de_texto)
        paragrafo.paragraph_format.space_after = Pt(0)
    _repetir_cabecalho(quadro.rows[0])

    for valores in tabela.linhas:
        linha = quadro.add_row()
        destaque = bool(valores) and valores[0].strip() == _ROTULO_TOTAL
        for posicao in range(tabela.largura):
            valor = valores[posicao] if posicao < len(valores) else ""
            if destaque:
                _sombrear(linha.cells[posicao], FUNDO_TOTAL)
            paragrafo = linha.cells[posicao].paragraphs[0]
            _texto(
                paragrafo,
                valor,
                tamanho=_TABELA_PT,
                negrito=destaque,
                cor=TINTA if destaque else TINTA_SECUNDARIA,
                estilo=estilos.corpo,
            )
            _alinhar(paragrafo, posicao in de_texto)
            paragrafo.paragraph_format.space_after = Pt(0)

    # Um rótulo e números — toda tabela da descritiva — ficam na repartição de
    # sempre. Mais de uma coluna de texto é outra tabela, e reparte pelo conteúdo.
    larguras = (
        _larguras_pelo_conteudo(tabela, de_texto, _largura_util(documento))
        if len(de_texto) > 1
        else None
    )
    if larguras is None:
        _repartir_larguras(quadro, _largura_util(documento), tabela.largura)
    else:
        _fixar_larguras(quadro, larguras)
    _manter_junta(quadro)

    # As notas do `.csv` — os dois denominadores, a convenção de fechamento das
    # faixas — são lidas pelo `relatorio.py` e **não** são impressas: saíram na
    # revisão de formatação. Elas continuam no arquivo que a Fase 5 escreveu, e
    # os dois denominadores continuam nomeados no cabeçalho da tabela ("% dos
    # válidos" e "% do total"), que é onde a distinção precisa mesmo aparecer.
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


def _larguras_pelo_conteudo(
    tabela: TabelaLida, de_texto: frozenset[int], largura_util: int
) -> list[int] | None:
    """
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
    """
    def em_emu(caracteres: int) -> int:
        return int((caracteres * _CM_POR_CARACTERE + _RESPIRO_CM) * _EMU_POR_CM)

    def textos(posicao: int) -> list[str]:
        celulas = [linha[posicao] if posicao < len(linha) else "" for linha in tabela.linhas]
        return [str(texto).strip() for texto in (tabela.colunas[posicao], *celulas)]

    larguras = [0] * tabela.largura
    naturais: dict[int, int] = {}
    pisos: dict[int, int] = {}
    for posicao in range(tabela.largura):
        conteudo = textos(posicao)
        maior = max((len(texto) for texto in conteudo), default=1)
        if posicao in de_texto:
            pisos[posicao] = em_emu(
                max((len(palavra) for texto in conteudo for palavra in texto.split()), default=1)
                + _FOLGA_DA_PALAVRA
            )
            naturais[posicao] = max(em_emu(min(maior, _TEXTO_NATURAL)), pisos[posicao])
        else:
            larguras[posicao] = max(em_emu(maior), int(_MINIMO_NUMERICO_CM * _EMU_POR_CM))

    resta = int(largura_util) - sum(larguras)
    if resta < sum(pisos.values()):
        return None

    pendentes = sorted(naturais, key=naturais.__getitem__)
    while pendentes:
        parte = resta / len(pendentes)
        curtas = [p for p in pendentes if naturais[p] <= parte]
        presas = [p for p in pendentes if pisos[p] > parte]
        if curtas:
            escolhidas, medida = curtas, naturais
        elif presas:
            escolhidas, medida = presas, pisos
        else:
            for posicao in pendentes:
                larguras[posicao] = int(parte)
            resta -= int(parte) * len(pendentes)
            break
        for posicao in escolhidas:
            larguras[posicao] = medida[posicao]
            resta -= medida[posicao]
        pendentes = [p for p in pendentes if p not in escolhidas]

    if resta > 0:
        total = sum(naturais.values())
        for posicao, natural in naturais.items():
            larguras[posicao] += int(resta * natural / total)
    # A soma das palavras mais longas cabia, mas a ordem da divisão pode ter dado a
    # uma coluna curta o que faltou a uma longa. Estourar a mancha da página nunca.
    if sum(larguras) > int(largura_util):
        return None
    return larguras


def _fixar_larguras(quadro, larguras) -> None:
    """
    Aplica largura por coluna e desliga o autoajuste.

    A largura precisa ser escrita em **toda** célula da coluna, e não só no
    `w:gridCol`: o Word obedece ao grid, o LibreOffice obedece à célula, e um
    documento que sai certo em um e torto no outro é um documento que ainda dá
    trabalho.
    """
    # `autofit = False` já escreve `<w:tblLayout w:type="fixed"/>` no lugar certo
    # do `tblPr`. Acrescentar outro à mão deixava dois no mesmo elemento, o
    # segundo depois do `tblLook` — documento inválido pelo esquema do OOXML, que
    # o Word abre assim mesmo e um validador recusa. Estava em toda tabela de
    # todo relatório já entregue.
    quadro.autofit = False

    for posicao, largura in enumerate(larguras):
        quadro.columns[posicao].width = largura
        for celula in quadro.columns[posicao].cells:
            celula.width = largura


def _escrever_figura(documento, figura: Any, numero: int, estilos: Estilos) -> None:
    """
    Uma figura, na largura útil da página do modelo.

    Um `.png` que não abre — a rodada interrompida no meio da gravação, o disco
    que encheu, a sincronização da nuvem que deixou o arquivo pela metade — não
    sobe como a exceção do `python-docx` (`UnrecognizedImageError`, que nem é
    `OSError`): vira `RelatorioError` com o nome do arquivo, e o
    `executar_relatorio` devolve o relatório anterior ao lugar.
    """
    _legenda(documento, f"Figura {numero}. {figura.titulo}", estilos)

    paragrafo = documento.add_paragraph()
    paragrafo.alignment = WD_ALIGN_PARAGRAPH.LEFT
    paragrafo.paragraph_format.space_after = Pt(10)
    try:
        paragrafo.add_run().add_picture(str(figura.caminho), width=_largura_util(documento))
    except Exception as erro:  # noqa: BLE001 - a leitura de imagem estoura de várias formas
        from .relatorio import RelatorioError

        pasta = Path(figura.caminho).parent.name
        raise RelatorioError(
            f"Não consegui pôr no documento a figura `{figura.arquivo}`, da pasta "
            f"`{pasta}`: o arquivo não é uma imagem que se abra.\n"
            "Quase sempre é uma rodada interrompida no meio da gravação. Rode a "
            f"análise de novo (`flatcap {pasta} <id> --sim`) e depois o relatório.\n\n"
            f"Detalhe técnico: {type(erro).__name__}: {erro}"
        ) from erro


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


def _alinhar(paragrafo, de_texto: bool) -> None:
    paragrafo.alignment = WD_ALIGN_PARAGRAPH.LEFT if de_texto else WD_ALIGN_PARAGRAPH.RIGHT


# Uma célula que se lê como número: `15`, `26,8`, `+0,45`, `−1,2`, `< 0,001`,
# `100,0%` — e a data `01/03/2026`, que numa tabela de período se alinha com os
# números ao lado dela. O traço e a célula vazia não contam para lado nenhum: são o
# "não se aplica" de qualquer coluna.
_CELULA_NUMERICA = re.compile(
    r"^(?:[<>≤≥]\s*)?[+\-−]?\d+(?:,\d+)?%?$|^\d{2}/\d{2}/\d{4}$"
)
_CELULA_NEUTRA = frozenset({"", "—", "-"})


def _colunas_de_texto(tabela: TabelaLida) -> frozenset[int]:
    """
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
    """
    de_texto = {0}
    for posicao in range(1, tabela.largura):
        for linha in tabela.linhas:
            celula = linha[posicao].strip() if posicao < len(linha) else ""
            if celula not in _CELULA_NEUTRA and not _CELULA_NUMERICA.match(celula):
                de_texto.add(posicao)
                break
    return frozenset(de_texto)


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
        subtitulo=primeiro(ESTILO_SUBTITULO),
        secao=primeiro(ESTILO_SECAO),
        corpo=primeiro(ESTILO_CORPO),
        legenda=primeiro(ESTILO_LEGENDA),
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

    A rodada é a do manifesto principal, com o nome dela — até a 1.14.1 o texto dizia
    "a partir da descritiva" mesmo quando só a normalidade tinha rodado. E o banco
    pode não existir: o relatório da amostra sai de um projeto que só tem o
    `desenho.yaml`, e ali o certo é "sem banco", e não "banco ?".
    """
    from . import __version__

    ficha = relatorio.ficha
    manifesto = relatorio.manifesto
    banco = manifesto.banco.get("arquivo")
    propriedades = documento.core_properties
    propriedades.title = f"{relatorio.titulo} — {ficha.nome or ficha.matricula}"
    propriedades.subject = f"Matrícula {ficha.matricula} · registro {ficha.record_id}"
    propriedades.comments = (
        f"Gerado por FlatCap {__version__} · rodada {manifesto.analise} de "
        f"{manifesto.gerado_em:%d/%m/%Y %H:%M} · "
        + (f"banco {banco}" if banco else "sem banco")
    )


def _salvar_atomico(documento, caminho: Path) -> None:
    """
    Grava o documento inteiro ou não grava nada.

    Mesma garantia do `escrever_atomico` do `ficha.py`, e pelo mesmo motivo: o
    temporário é criado na **mesma pasta** do destino, porque `os.replace` só é
    atômico dentro do mesmo sistema de arquivos. Meio `.docx` não é um documento
    incompleto — é um arquivo que o Word se recusa a abrir.

    O temporário é o do `ficha.temporario_ao_lado`, que respeita o `umask`: o
    `.docx` sai com a permissão de qualquer arquivo novo, e não só para o dono.
    """
    import os

    from .ficha import temporario_ao_lado

    caminho = Path(caminho)
    descritor, temporario = temporario_ao_lado(caminho)
    os.close(descritor)
    try:
        documento.save(str(temporario))
        os.replace(temporario, caminho)
    except BaseException:
        temporario.unlink(missing_ok=True)
        raise


# XML que a API do python-docx não expõe


def _manter_junta(quadro) -> None:
    """
    Impede que uma tabela curta se parta na quebra de página.

    Uma tabela de frequência de cinco linhas partida entre duas páginas — as
    categorias em uma e o `Total` na outra — é lida como duas tabelas incompletas.
    O `keep_with_next` vai em todas as linhas menos a última: na última, ele
    arrastaria junto o parágrafo seguinte, que é a legenda da figura.

    Acima de `_LINHAS_PARA_MANTER_JUNTA` a tabela se parte de propósito, e é o
    cabeçalho repetido que resolve a leitura do outro lado.
    """
    linhas = list(quadro.rows)

    def prender(linha) -> None:
        for celula in linha.cells:
            for paragrafo in celula.paragraphs:
                paragrafo.paragraph_format.keep_with_next = True

    if len(linhas) <= _LINHAS_PARA_MANTER_JUNTA:
        for linha in linhas[:-1]:
            prender(linha)
        return

    # A tabela longa parte, e é o cabeçalho repetido que resolve a leitura do
    # outro lado. Com uma exceção: o `Total`. Sozinho no alto de uma página,
    # embaixo do cabeçalho repetido, ele vira uma página que só tem um título e
    # uma faixa verde — e quem lê volta atrás procurando os números que somam
    # nela. As duas categorias antes dele vão junto, o que basta para a faixa
    # nunca aparecer desacompanhada.
    if len(linhas) >= 4 and linhas[-1].cells[0].text.strip() == _ROTULO_TOTAL:
        prender(linhas[-2])
        prender(linhas[-3])


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
    Uma borda em volta de tudo. Serve a caixa de aviso, que é uma célula só.
    """
    _escrever_bordas(
        tabela,
        {
            lado: (espessura, cor)
            for lado in ("top", "left", "bottom", "right", "insideH", "insideV")
        },
    )


def _bordas_de_tres_linhas(quadro, cor: str) -> None:
    """
    Topo, sob o cabeçalho, base. Nenhuma vertical.

    É o último degrau da fila para as tabelas do relatório, e ele mudou junto com
    o estilo `FlatCap Tabela` que o `flatcap template` grava: os dois precisam ter
    a mesma cara, senão um projeto sem modelo sai com uma tabela diferente da de
    todos os outros — que é exatamente o tipo de diferença que ninguém percebe até
    o cliente pôr dois relatórios lado a lado.
    """
    _escrever_bordas(quadro, {"top": (_REGUA_GROSSA, cor), "bottom": (_REGUA_GROSSA, cor)})
    for celula in quadro.rows[0].cells:
        propriedades = celula._tc.get_or_add_tcPr()
        bordas = OxmlElement("w:tcBorders")
        bordas.append(_lado_da_borda("bottom", _REGUA_FINA, cor))
        propriedades.append(bordas)


def _lado_da_borda(nome: str, espessura: int, cor: str) -> OxmlElement:
    elemento = OxmlElement(f"w:{nome}")
    elemento.set(qn("w:val"), "single" if espessura else "none")
    elemento.set(qn("w:sz"), str(espessura))
    elemento.set(qn("w:space"), "0")
    elemento.set(qn("w:color"), cor)
    return elemento


def _escrever_bordas(tabela, lados: dict[str, tuple[int, str]]) -> None:
    """
    Escreve `w:tblBorders`, com `none` explícito no que não foi pedido.

    O `none` precisa ser escrito: sem ele, o lado herda a borda do estilo de
    tabela do modelo, e uma tabela de três linhas herdaria as verticais de um
    `Table Grid` institucional sem nada no código dizendo de onde elas vieram.
    """
    propriedades = tabela._tbl.tblPr
    antigo = propriedades.find(qn("w:tblBorders"))
    if antigo is not None:
        propriedades.remove(antigo)

    bordas = OxmlElement("w:tblBorders")
    for lado in ("top", "left", "bottom", "right", "insideH", "insideV"):
        espessura, cor = lados.get(lado, (0, "auto"))
        bordas.append(_lado_da_borda(lado, espessura, cor))

    # `tblBorders` vem antes de `tblLayout` e `tblLook` no esquema do OOXML.
    for filho in propriedades:
        if filho.tag.split("}")[-1] in {"shd", "tblLayout", "tblCellMar", "tblLook"}:
            filho.addprevious(bordas)
            return
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
    rodapé com o número da página, e os seis estilos `FlatCap *` que o relatório
    procura antes de qualquer outro. Mude a fonte de `FlatCap Corpo` e o
    documento inteiro muda; ponha o logotipo no cabeçalho e ele aparece em todas
    as páginas de todos os relatórios.
    """
    caminho = Path(caminho)
    documento = _documento_padrao()

    cabecalho = documento.sections[0].header.paragraphs[0]
    trecho = cabecalho.add_run(CABECALHO_PADRAO)
    trecho.font.size = Pt(_NOTA_PT)
    trecho.font.color.rgb = TINTA_APAGADA
    cabecalho.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    # As propriedades do arquivo são o único lugar de dentro do `.docx` em que
    # cabe uma explicação: elas aparecem no Word em Arquivo → Informações, não são
    # impressas, e o `_propriedades` as reescreve em cada relatório gerado — então
    # o que está escrito aqui não tem como vazar para o documento do cliente.
    propriedades = documento.core_properties
    propriedades.title = "Modelo de relatório do FlatCap"
    propriedades.comments = _NOTA_DO_MODELO

    _salvar_atomico(documento, caminho)
    _escrever_decisoes(caminho.parent / ARQUIVO_DECISOES)
    return caminho


# O `dc:description` do OOXML tem limite de 255 caracteres — daí a nota ser um
# ponteiro para a folha de decisões, e não a explicação inteira.
_NOTA_DO_MODELO = (
    "Modelo de relatório do FlatCap. As razões de cada decisão estão em "
    f"{ARQUIVO_DECISOES}, nesta pasta — leia antes de mexer. A aparência se ajusta "
    "nos estilos FlatCap *, pelo Word. O corpo deste arquivo sai impresso em todo "
    "relatório: deixe-o vazio."
)


def _escrever_decisoes(caminho: Path) -> Path:
    """
    Escreve a folha de decisões ao lado do modelo, se ela ainda não existir.

    **Não sobrescreve.** O `.docx` é regerável e o comando avisa que vai
    substituí-lo; este arquivo é texto que alguém escreveu, e a segunda coisa que
    um usuário faz com ele é acrescentar as decisões da própria instituição.
    Perder isso em um `flatcap template --sim` distraído seria o mesmo defeito que
    a fusão do `dicionario.csv` existe para impedir.
    """
    caminho = Path(caminho)
    if not caminho.exists():
        caminho.write_text(_TEXTO_DAS_DECISOES, encoding="utf-8", newline="\n")
    return caminho


def _fonte_do_estilo(estilo, nome: str = FONTE) -> None:
    """
    Escreve a fonte nos quatro atributos do `w:rFonts`, e não só em dois.

    O `style.font.name` do `python-docx` preenche `w:ascii` e `w:hAnsi` — o texto
    latino comum — e deixa `w:cs` e `w:eastAsia` como estavam. Um caractere que
    caia em um desses é desenhado com a fonte do **tema**, no meio de um parágrafo
    que deveria ser todo da mesma fonte. Acontece pouco e é impossível de
    diagnosticar quando acontece.

    Os atributos `*Theme` são removidos no mesmo movimento: quando os dois
    convivem, quem vence depende da versão do Word.
    """
    propriedades = estilo._element.get_or_add_rPr()
    fontes = propriedades.get_or_add_rFonts()
    for atributo in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        fontes.set(qn(atributo), nome)
    for tema in ("w:asciiTheme", "w:hAnsiTheme", "w:cstheme", "w:eastAsiaTheme"):
        if fontes.get(qn(tema)) is not None:
            del fontes.attrib[qn(tema)]


def _fixar_tema(documento) -> None:
    """
    Põe a mesma fonte também no tema do documento.

    O tema é o que o Word usa para todo estilo que **não** diz a fonte dele. O que
    vem no modelo base do `python-docx` traz `minorFont` Cambria e `majorFont`
    Calibri — uma serifa esperando a vez. Os estilos `FlatCap *` dizem a fonte
    deles e não dependem do tema; o `Título 1` nativo, o `Legenda` nativo e
    qualquer estilo que alguém aplique à mão no Word dependem.

    Sem isto o modelo é um arquivo em que a fonte muda sozinha quando o usuário
    mexe em outra coisa — e ele não tem como descobrir por quê.
    """
    marca = re.compile(r'(<a:(?:majorFont|minorFont)>\s*<a:latin typeface=")[^"]*"')
    for parte in documento.part.package.iter_parts():
        if "theme" not in str(parte.partname):
            continue
        xml = parte.blob.decode("utf-8")
        novo, quantos = marca.subn(rf'\1{FONTE}"', xml)
        if quantos:
            parte._blob = novo.encode("utf-8")


def _definir_estilos(documento) -> None:
    """
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
    _fonte_do_estilo(corpo)
    corpo.font.size = Pt(_CORPO_PT)
    corpo.font.color.rgb = TINTA
    corpo.paragraph_format.space_after = Pt(6)

    titulo = criar("FlatCap Titulo", "Normal")
    _fonte_do_estilo(titulo)
    titulo.font.size = Pt(20)
    titulo.font.bold = True
    titulo.font.color.rgb = TINTA

    secao = criar("FlatCap Secao", "Heading 1")
    _fonte_do_estilo(secao)
    secao.font.size = Pt(14)
    secao.font.bold = True
    secao.font.color.rgb = TINTA
    secao.paragraph_format.space_before = Pt(14)
    secao.paragraph_format.space_after = Pt(2)

    subtitulo = criar("FlatCap Subtitulo", "Normal")
    _fonte_do_estilo(subtitulo)
    subtitulo.font.size = Pt(13)
    subtitulo.font.bold = False
    subtitulo.font.italic = False
    subtitulo.font.color.rgb = TINTA_SECUNDARIA
    subtitulo.paragraph_format.space_before = Pt(0)
    subtitulo.paragraph_format.space_after = Pt(16)

    legenda = criar("FlatCap Legenda", "Caption")
    _fonte_do_estilo(legenda)
    legenda.font.size = Pt(_LEGENDA_PT)
    legenda.font.bold = True
    legenda.font.italic = False
    legenda.font.color.rgb = TINTA_SECUNDARIA

    _estilo_de_tabela(documento)


def _estilo_de_tabela(documento) -> None:
    """
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
    """
    from docx.enum.style import WD_STYLE_TYPE

    estilos = documento.styles
    if "FlatCap Tabela" in {estilo.name for estilo in estilos}:
        return

    estilo = estilos.add_style("FlatCap Tabela", WD_STYLE_TYPE.TABLE)
    _fonte_do_estilo(estilo)
    estilo.font.size = Pt(_TABELA_PT)
    estilo.font.color.rgb = TINTA

    tabela = OxmlElement("w:tblPr")
    bordas = OxmlElement("w:tblBorders")
    for lado in ("top", "left", "bottom", "right", "insideH", "insideV"):
        espessura = _REGUA_GROSSA if lado in ("top", "bottom") else 0
        bordas.append(_lado_da_borda(lado, espessura, TINTA_LINHA))
    tabela.append(bordas)
    tabela.append(_margens_da_celula())
    estilo._element.append(tabela)

    banda = OxmlElement("w:tblStylePr")
    banda.set(qn("w:type"), "firstRow")
    celula = OxmlElement("w:tcPr")
    sob_o_cabecalho = OxmlElement("w:tcBorders")
    sob_o_cabecalho.append(_lado_da_borda("bottom", _REGUA_FINA, TINTA_LINHA))
    celula.append(sob_o_cabecalho)
    banda.append(celula)
    estilo._element.append(banda)


def _margens_da_celula(cm: float = 0.12) -> OxmlElement:
    """
    O respiro entre a régua e o texto. Sem ele a tabela de três linhas fica
    apertada — sem verticais, é o espaço que separa as colunas.
    """
    margens = OxmlElement("w:tblCellMar")
    for nome, fator in (("top", 1.0), ("start", 1.6), ("bottom", 1.0), ("end", 1.6)):
        elemento = OxmlElement(f"w:{nome}")
        elemento.set(qn("w:w"), str(int(cm * fator * 567)))
        elemento.set(qn("w:type"), "dxa")
        margens.append(elemento)
    return margens


_TEXTO_DAS_DECISOES = '''# O modelo do relatório — o que é decisão sua, e onde ela mora

> Escrito pelo `flatcap template`, e mora ao lado do `template.docx` porque um
> `.docx` é binário: não aceita comentário, não entra no Git e não conta a
> ninguém por que está do jeito que está.
>
> **Este arquivo é seu.** O `flatcap template` não o sobrescreve depois de criado
> — acrescente aqui as decisões da sua instituição, e a data em que as tomou.

## A regra que surpreende todo mundo uma vez

O relatório **é** este modelo, com o conteúdo acrescentado depois. Página,
margens, cabeçalho, rodapé, estilos **e o corpo** viajam inteiros para cada
documento entregue.

A consequência é a que pega: o que você escrever no corpo do `template.docx` sai
impresso em todo relatório, antes do título. É assim que uma capa institucional
funciona — e é por isso que o corpo vem vazio. Um "instruções de uso" escrito ali
dentro chega na mão do cliente.

## O que se ajusta aqui, no Word

Abra o `template.docx`, mude o estilo, salve. Nenhuma linha de Python, e vale
para todo relatório gerado daí em diante.

| peça do documento | estilo |
| --- | --- |
| título | `FlatCap Titulo` |
| subtítulo (`matrícula - nome`) | `FlatCap Subtitulo` |
| nome de cada variável | `FlatCap Secao` |
| texto corrido e células de tabela | `FlatCap Corpo` |
| `Tabela 1. …` e `Figura 1. …` | `FlatCap Legenda` |
| bordas e fundo das tabelas | `FlatCap Tabela` |

Mais o que não é estilo: tamanho da página, margens, cabeçalho — é onde o
logotipo entra sem custar uma página — e rodapé.

Os seis nomes começam com `FlatCap` de propósito: é assim que se descobre, no
painel de estilos do Word, quais são os que mandam. Nenhum outro estilo do
documento é consultado pelo relatório.

## O que não se ajusta aqui

Isto é código. Mexer no Word não muda:

| o que | onde |
| --- | --- |
| largura das colunas (34% na primeira) | `documento.py` |
| alinhamento das células | `documento.py` |
| o verde da linha `Total` | `documento.py` |
| cabeçalho de tabela repetido, tabela que não parte | `documento.py` |
| numeração `Tabela 1` / `Figura 1`, legenda acima | `documento.py` |
| **os gráficos** | `graficos.py` — eles são imagem, não texto |
| a ordem das seções | o `dicionario.csv` do projeto |
| o texto de abertura | o `projeto.yaml` do projeto |

A linha dos gráficos é a que mais custa descobrir sozinho: o `.png` já vem
desenhado quando o documento é montado, e nenhum estilo do Word o alcança. Se a
fonte do modelo mudar, a do `graficos.py` tem de mudar junto — senão o relatório
sai com duas tipografias, uma no texto e outra nos eixos.

## As decisões que este modelo carrega hoje

- **Arial em tudo**, inclusive nos gráficos. Uma fonte só na página; o tema do
  documento foi reescrito para que nenhum estilo possa cair numa serifa.
- **A4, margens de 2,5 cm** — menos a inferior, 2,0 cm, para o rodapé caber sem
  apertar a mancha.
- **A escala de tamanhos**: título 20, nome da variável 14, subtítulo 13, corpo
  10,5, tabela 9,5, legenda 9. É pouca variação de propósito: o documento é
  técnico, e a hierarquia se lê pelo peso e pelo espaço, não pelo tamanho.
- **Tabela de três linhas** — topo, sob o cabeçalho, base; nenhuma vertical. É o
  padrão de publicação científica.
- **Linha `Total` com fundo #4B9B69 e texto preto.** O preto é escolha medida:
  6,2:1 de contraste, contra 3,4:1 do branco sobre o mesmo verde.
- **Legenda acima** da tabela e da figura, numeradas em séries separadas, para
  que "veja a Tabela 3" funcione em um e-mail.
- **Cabeçalho discreto à direita, rodapé com o número da página.**

## Antes de salvar

- Não renomeie os estilos `FlatCap *`. O relatório os procura pelo nome; sem
  eles, ele cai nos estilos nativos do Word e o documento muda de cara.
- Deixe o corpo vazio, a menos que queira uma capa impressa em todo relatório.
- Gere um relatório de verdade e **abra no Word**. É o passo que nenhum teste
  substitui, e três dos quatro piores defeitos deste projeto apareceram assim.
- Imprima uma página em preto e branco. O verde do `Total` vira um cinza médio
  no papel, e é a única conferência que a tela não faz.

## Onde este arquivo mora

No `FLATCAP_ROOT`, fora do repositório e **fora de backup por padrão**. O
`.gitignore` ignora todo `.docx`, de propósito: o modelo carrega logotipo,
identidade visual e muda sem pedir licença a ninguém. Guardar uma cópia dele é
sua responsabilidade — e se um `flatcap template --sim` distraído substituir o
`template.docx`, é a cópia que salva as suas horas de Word.
'''


__all__ = [
    "ARQUIVO_DECISOES",
    "ARQUIVO_TEMPLATE",
    "Estilos",
    "escrever",
    "escrever_template",
    "versao_do_python_docx",
]
