"""
O relatório — o passo final do fluxo, e o que a Fase 6 automatiza.

Este módulo **monta o conteúdo** do documento e não escreve `.docx` nenhum. Quem
escreve é o `documento.py`, que recebe um `Relatorio` pronto e não decide mais
nada. É a mesma divisão da Fase 5 entre `descritiva.py` e `graficos.py`, pelo
mesmo motivo: se o gerador do documento recalculasse qualquer coisa, bastaria uma
diferença de arredondamento para o `.docx` dizer 37 e o `.csv` ao lado dizer 38 —
e ninguém confere documento contra planilha.

Aqui a regra é ainda mais forte, porque é o que sustenta a decisão de arquitetura
nº 3 do roteiro:

    **O relatório não abre o banco.** Nunca.

Ele lê o `manifesto.json` e os `.csv` que a Fase 5 escreveu, e é só isso. Não
importa o `pandas`, não importa o `matplotlib`, não recalcula uma média sequer.
Um número que aparece no documento é, byte a byte, o número que está no arquivo
que você pode abrir no Excel e conferir. Se o relatório recalculasse, existiriam
duas fontes para o mesmo 37% — e o dia em que elas discordassem seria o dia em que
o cliente perguntaria.

A consequência prática aparece no relógio: `flatcap relatorio` parte em ~0,1 s,
porque nenhuma das bibliotecas caras entra. Foi para manter isso que
`versao_vigente` desceu para o `ficha.py` e `PASTA_DESCRITIVA` para o
`projeto.py` — as duas moravam em módulos que importam o `pandas` e são, as duas,
perguntas que não precisam dele.

## O que este módulo decide

**De qual rodada o documento fala.** A vigente, em `3. Análises/descritiva/`. Uma
rodada arquivada em `2. Versões antigas/` continua legível pelo `manifesto.ler`,
mas não é o que este comando monta: o relatório é o da descritiva de agora.

**Se ela ainda descreve o que está na pasta.** Quatro conferências, e nenhuma
delas recusa o comando — a decisão da fase foi **gerar com o aviso dentro do
documento**:

    * a versão vigente do banco é outra desde a rodada;
    * o arquivo do banco foi alterado no disco depois de registrado;
    * o `dicionario.csv` mudou depois da rodada (variável nova, tipo trocado,
      rótulo reescrito, faixas diferentes);
    * um artefato listado no manifesto não está mais na pasta.

Cada uma vira um `Alerta`, e o `Alerta` viaja para dentro do `.docx`, logo abaixo
da identificação. Um aviso que fica só no terminal é um aviso que ninguém lê
depois de anexar o documento ao e-mail.

**Como cada tabela vira tabela.** Os `.csv` da Fase 5 já trazem os números
formatados em português e um cabeçalho de comentário com o denominador. A leitura
aqui é fiel: separa os comentários das linhas de dados e não converte nada — o
texto que está na célula do `.csv` é o texto que vai para a célula do Word.

## O que sai na primeira página

Título, subtítulo com `matrícula - nome`, os alertas quando houver, e o
`TEXTO_PADRAO` — os parágrafos fixos que abrem todo relatório, definidos logo
abaixo, em um bloco só, para serem reescritos sem se procurar código.

## O que este módulo deliberadamente não faz

Não escreve prosa sobre os números. Não monta uma "Tabela 1" consolidada. Não
escreve apêndice técnico. As três foram decisões suas, e as três continuam a um
argumento de distância — o `Relatorio` já carrega tudo o que elas precisariam.

E não imprime mais a tabela de identificação nem os rodapés de denominador das
tabelas: as duas saíram na revisão de formatação, e o que elas diziam sobre a
procedência ficou nos metadados do arquivo (`documento._propriedades`) e no
`manifesto.json` da rodada.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .dados import linha_do_tempo
from .dicionario import ARQUIVO_DICIONARIO
from .dicionario import ler as ler_dicionario
from .ficha import Ficha, Versao, versao_vigente
from .ficha import ler as ler_ficha
from .manifesto import ARQUIVO_MANIFESTO, Manifesto
from .manifesto import ler as ler_manifesto
from .nomes import SEPARADOR, sanitizar
from .projeto import PASTA_ANALISES, PASTA_ANTIGAS, PASTA_DESCRITIVA, anotar

PREFIXO_RELATORIO = "Relatorio_"

TITULO_PADRAO = "Relatório Estatístico"


# ─────────────────────────────────────────────────────────────────────────────
#  O TEXTO PADRÃO DA PRIMEIRA PÁGINA — é aqui que se escreve.
#
#  Uma linha da tupla, um parágrafo do documento, na ordem em que estão. Eles
#  entram entre o subtítulo e a primeira variável, em todo relatório de todo
#  projeto: é o texto que não muda de cliente para cliente.
#
#  Trocar o `xxxxx` pelo texto de verdade é a única edição necessária — nada
#  mais no código sabe o que está escrito aqui, e a estrutura do documento não
#  muda quando o texto crescer, encolher ou ganhar parágrafos.
#
#  `()` não escreve nada: é assim que a seção inteira sai.
# ─────────────────────────────────────────────────────────────────────────────

TEXTO_PADRAO: tuple[str, ...] = (
    "xxxxxxxxxxxx xxxxxxx xxxxxxxxxxxxxx xxxxxxxx xxxxx xxxxxxxxxxx xxxxxxxx "
    "xxxxxxxxxxxxx xxxxxx xxxxxxxxx xxxxxxxxxxxx xxxxx xxxxxxxxxx xxxxxxx "
    "xxxxxxxxxxxxxxx xxxxxxxx xxxxx xxxxxxxxxxxx xxxxxxxxx xxxxxxx xxxxxxxxxx.",
    "xxxxxxxx xxxxxxxxxxxxx xxxxx xxxxxxxxxx xxxxxxxxxxxx xxxxxxx xxxxxxxxxxx "
    "xxxxx xxxxxxxxxxxxxx xxxxxxxxx xxxxxxx xxxxxxxxxxxx xxxxxxxxxx xxxxxxx "
    "xxxxxxxxxxx xxxxxxxxxxxxx xxxxxxx xxxxx xxxxxxxxxxxxxxxx xxxxxxxxxxx "
    "xxxxxxxx xxxxxxxxxxxxx xxxxxxxxx xxxxxxxxxxx xxxxxxx xxxxxxxxxxxxxx.",
    "xxxxxxxxxxxxxxx xxxxxxxxx xxxxxxxxxxx xxxxxxxx xxxxxxxxxxxxx xxxxx "
    "xxxxxxxxxxxx xxxxxxxxxxx xxxxxxx xxxxxxxxxxxxxx xxxxxxxx xxxxxxxxxxxxxx "
    "xxxxxxxxxxx xxxxxxx xxxxxxxxxxxx xxxxxxxxxxxxx xxxxxxxxx xxxxxxxxxxxxx.",
    "xxxxxxxxx xxxxxxxxxxxxxx xxxxxxxxxxx xxxxxxxxx xxxxxxx xxxxxxxxxxxxx "
    "xxxxxxxxxxxxx xxxxxxxxxx xxxxxxx xxxxxxxxxxxxxxx xxxxxxxxxxx xxxxxxxxx "
    "xxxxxxxxxxxxxx xxxxxxxx xxxxxxxxxxx xxxxxxxxxxxxxxx xxxxxxxxxx xxxxxxx.",
)

# A nota de comentário que todo `.csv` da Fase 5 traz na segunda linha. Ela é
# descartada na leitura porque o título da seção já diz de qual variável se trata,
# e repetir "variável: escolaridade" embaixo de uma tabela chamada "Escolaridade"
# é ruído em um documento que vai para o cliente.
_NOTA_REDUNDANTE = re.compile(r"^vari[áa]vel:", re.IGNORECASE)

_SEPARADOR_CAMPO = ";"


class RelatorioError(RuntimeError):
    """
    Falha ao montar o relatório, já traduzida para o usuário.

    Erro próprio pelo mesmo motivo de `ConfigError`, `RedcapError`, `ProjetoError`,
    `FichaError`, `DadosError`, `BancoError`, `DicionarioError`, `DescritivaError`
    e `ManifestoError`: a CLI captura esta classe e transforma em painel. Qualquer
    outra exceção é bug de verdade e deve subir com o traceback inteiro.
    """


class DescritivaAusenteError(RelatorioError):
    """
    O projeto não tem uma rodada de descritiva para relatar.

    É a única recusa desta fase, e ela não é uma escolha entre gerar e não gerar:
    sem manifesto não há o que montar. Todas as outras divergências viram aviso
    dentro do documento.
    """


class TabelaIlegivelError(RelatorioError):
    """
    Um `.csv` da rodada existe e não dá para interpretar.
    """


class ModeloAusenteError(RelatorioError):
    """
    O `template.docx` indicado em `--template` não existe.
    """


@dataclass(frozen=True)
class Alerta:
    """
    Uma divergência entre a rodada e o que está na pasta hoje.

    Vai para o terminal **e** para dentro do documento. A duplicação é o ponto:
    o terminal você vê agora, o documento é o que sobra depois de o arquivo ser
    anexado a um e-mail e aberto por outra pessoa em outro dia.
    """

    codigo: str
    titulo: str
    detalhe: str = ""


@dataclass(frozen=True)
class TabelaLida:
    """
    Um `.csv` da descritiva, separado em cabeçalho de comentário e dados.

    Os valores são texto e continuam texto. Converter `28,7` para `0.287` e
    formatar de novo na hora de escrever seria reintroduzir, no último passo do
    fluxo, exatamente o arredondamento que a Fase 5 já resolveu.
    """

    arquivo: str
    especie: str
    titulo: str
    notas: tuple[str, ...] = ()
    colunas: tuple[str, ...] = ()
    linhas: tuple[tuple[str, ...], ...] = ()

    @property
    def largura(self) -> int:
        return len(self.colunas)

    @property
    def total(self) -> int:
        return len(self.linhas)


@dataclass(frozen=True)
class Figura:
    """
    Um `.png` da descritiva, com o caminho já conferido.
    """

    arquivo: str
    caminho: Path
    especie: str
    titulo: str


@dataclass(frozen=True)
class Secao:
    """
    Uma variável no documento: o que ela mostra, na ordem em que mostra.

    A ordem das seções é a do manifesto, que é a do dicionário, que é a das
    colunas do banco. Reordenar o `dicionario.csv` reordena o documento, sem
    tocar em código — é a decisão da Fase 5 aparecendo aqui.
    """

    variavel: str
    rotulo: str
    tipo: str
    n: int
    faltantes: int
    tabelas: tuple[TabelaLida, ...] = ()
    figuras: tuple[Figura, ...] = ()

    @property
    def preenchidos(self) -> int:
        return self.n - self.faltantes


@dataclass(frozen=True)
class ForaDoRelatorio:
    """
    Uma variável do dicionário que não gerou nada, e por quê.

    Não entra no `.docx` — é diagnóstico seu, não conteúdo do cliente —, mas
    aparece no terminal pelo mesmo motivo da Fase 5: "não está no relatório" e
    "ninguém reparou que ela existia" são coisas diferentes.
    """

    variavel: str
    tipo: str
    motivo: str


@dataclass(frozen=True)
class Relatorio:
    """
    O documento inteiro, decidido. É daqui que saem o `.docx` e o terminal.
    """

    ficha: Ficha
    manifesto: Manifesto
    titulo: str
    secoes: tuple[Secao, ...]
    texto: tuple[str, ...] = ()
    fora: tuple[ForaDoRelatorio, ...] = ()
    alertas: tuple[Alerta, ...] = ()
    avisos: tuple[str, ...] = ()
    quando: datetime = None  # type: ignore[assignment]

    @property
    def raiz(self) -> Path:
        return self.ficha.raiz

    @property
    def subtitulo(self) -> str:
        """
        `00742 - José Antônio de Sá`, embaixo do título.

        Monta com o mesmo separador do `nomes.py`, e não com o nome da pasta,
        por dois motivos. O nome da pasta passou pela `sanitizar` — perdeu a
        barra, o dois-pontos, o que o Windows não aceita — e o documento não tem
        essa limitação; e a matrícula e o nome são campos da ficha, que é onde
        eles são a informação, enquanto na pasta são um caminho.

        Cliente sem nome (o cadastro incompleto que o `listar` marca em amarelo)
        sai só com a matrícula, em vez de sair com um separador solto no fim.
        """
        partes = [parte for parte in (self.ficha.matricula, self.ficha.nome) if parte]
        return SEPARADOR.join(partes)

    @property
    def tabelas(self) -> tuple[TabelaLida, ...]:
        return tuple(t for secao in self.secoes for t in secao.tabelas)

    @property
    def figuras(self) -> tuple[Figura, ...]:
        return tuple(f for secao in self.secoes for f in secao.figuras)


@dataclass(frozen=True)
class PlanoRelatorio:
    """
    Tudo o que o `relatorio` faria, decidido e ainda não escrito.

    Imutável como os planos das outras fases, e pela mesma razão: entre a
    simulação e a execução ninguém altera um caminho em trânsito. A árvore que
    aparece no terminal é lida deste objeto.
    """

    relatorio: Relatorio
    destino: Path
    arquivamentos: tuple[tuple[Path, Path], ...] = ()
    template: Path | None = None

    @property
    def raiz(self) -> Path:
        return self.relatorio.raiz

    @property
    def secoes(self) -> tuple[Secao, ...]:
        return self.relatorio.secoes

    @property
    def total_tabelas(self) -> int:
        return len(self.relatorio.tabelas)

    @property
    def total_figuras(self) -> int:
        return len(self.relatorio.figuras)


@dataclass(frozen=True)
class ResultadoRelatorio:
    """
    O que a execução de fato escreveu.
    """

    caminho: Path
    arquivados: tuple[tuple[Path, Path], ...] = ()
    avisos: tuple[str, ...] = ()


# Casos de uso


def preparar_relatorio(
    raiz: Path,
    template: Path | str | None = None,
    conferir: bool = True,
    agora: datetime | None = None,
    titulo: str = TITULO_PADRAO,
) -> PlanoRelatorio:
    """
    Lê a rodada da descritiva e monta o documento inteiro. Não escreve nada.

    Args:
        raiz: a pasta do projeto (a que tem o `projeto.yaml`).
        template: um `.docx` para herdar estilos, cabeçalho e rodapé. Sem isso, o
            `template.docx` do `FLATCAP_ROOT`, e sem ele os estilos padrão.
        conferir: reler o `sha256` do banco e comparar com a ficha. É a única
            leitura cara deste comando, e `--rapido` a desliga.
        agora: relógio injetável — sem ele os testes não teriam como comparar o
            nome do arquivo, que carrega a data.

    Raises:
        FichaError: a ficha do projeto não abre.
        DescritivaAusenteError: não há rodada para relatar.
        ManifestoInvalidoError: o `manifesto.json` não abre ou é de formato novo.
        DicionarioInvalidoError: o `dicionario.csv` que está lá não é interpretável.
        TabelaIlegivelError: um `.csv` da rodada não abre.
        ModeloAusenteError: o `--template` indicado não existe.
    """
    raiz = Path(raiz)
    quando = agora or datetime.now()

    ficha = ler_ficha(raiz)
    pasta = raiz / PASTA_ANALISES / PASTA_DESCRITIVA
    manifesto = _manifesto_da_rodada(pasta)

    alertas: list[Alerta] = []
    avisos: list[str] = []

    secoes, ausentes = _secoes(pasta, manifesto)
    if ausentes:
        quais = ", ".join(f"`{nome}`" for nome in ausentes[:6])
        resto = f" e mais {len(ausentes) - 6}" if len(ausentes) > 6 else ""
        alertas.append(
            Alerta(
                codigo="artefato_ausente",
                titulo=f"{len(ausentes)} arquivo(s) da descritiva não estão na pasta",
                detalhe=(
                    f"O manifesto lista {quais}{resto}, e o arquivo não está em "
                    f"{PASTA_ANALISES}/{PASTA_DESCRITIVA}/. O documento saiu sem essa "
                    "tabela ou figura. Rode `flatcap descritiva` de novo para refazer "
                    "a rodada inteira."
                ),
            )
        )

    alertas += _conferir_banco(raiz, ficha, manifesto, conferir)
    alerta_dicionario, aviso_dicionario = _conferir_dicionario(raiz, manifesto)
    if alerta_dicionario is not None:
        alertas.append(alerta_dicionario)
    if aviso_dicionario:
        avisos.append(aviso_dicionario)

    relatorio = Relatorio(
        ficha=ficha,
        manifesto=manifesto,
        titulo=titulo,
        secoes=secoes,
        # O texto padrão entra no `Relatorio` como dado, e não é lido pelo
        # `documento.py` da constante. É o que mantém a divisão da fase: quem
        # escreve o `.docx` não sabe de onde o texto veio, e um dia em que ele
        # passar a vir do `projeto.yaml` ou de um arquivo por cliente, só esta
        # linha muda.
        texto=TEXTO_PADRAO,
        fora=tuple(
            ForaDoRelatorio(
                variavel=str(entrada.get("variavel", "")),
                tipo=str(entrada.get("tipo", "")),
                motivo=str(entrada.get("motivo", "")),
            )
            for entrada in manifesto.fora
        ),
        alertas=tuple(alertas),
        avisos=tuple(avisos),
        quando=quando,
    )

    destino = raiz / nome_do_relatorio(ficha.matricula, quando.date())
    return PlanoRelatorio(
        relatorio=relatorio,
        destino=destino,
        arquivamentos=_arquivamentos(raiz, destino),
        template=_localizar_template(raiz, template),
    )


def executar_relatorio(plano: PlanoRelatorio) -> ResultadoRelatorio:
    """
    Escreve o documento no disco. Não decide mais nada.

    A ordem é a das outras fases: arquiva o relatório anterior **antes** de
    escrever o novo, porque os dois têm o mesmo nome quando a rodada é do mesmo
    dia — e escrever primeiro seria escrever por cima do que se queria guardar.

    Uma falha no meio desfaz o que já foi feito, inclusive devolvendo o relatório
    arquivado ao lugar. Sem isso, a versão anterior teria sumido em troca de nada.
    É o mesmo cuidado do `executar_adicao` da Fase 3 e do `executar_descritiva`
    da Fase 5.

    O `documento.py` entra aqui dentro, e não no topo do arquivo, pelo mesmo
    motivo que o `matplotlib` entra dentro do `executar_descritiva`: a simulação
    não desenha documento nenhum e não deve pagar pelo `python-docx`.
    """
    from .documento import escrever

    arquivados: list[tuple[Path, Path]] = []
    avisos: list[str] = []
    desfazer: list[Any] = []

    try:
        for de, para in plano.arquivamentos:
            para.parent.mkdir(parents=True, exist_ok=True)
            de.rename(para)
            arquivados.append((de, para))
            desfazer.append(lambda d=de, p=para: p.rename(d))

        escrever(plano.relatorio, plano.destino, plano.template)
        desfazer.append(lambda p=plano.destino: p.unlink(missing_ok=True))

        try:
            anotar(plano.raiz, _acao_do_historico(plano), plano.relatorio.quando)
        except OSError as erro:
            avisos.append(
                f"O relatório foi escrito, mas não consegui escrever no "
                f"historico.md: {erro}"
            )

    except (OSError, RelatorioError):
        for passo in reversed(desfazer):
            try:
                passo()
            except OSError:
                avisos.append(
                    "Falhei ao desfazer uma etapa. Confira a pasta do projeto e "
                    f"{PASTA_ANTIGAS} antes de rodar de novo."
                )
        raise

    return ResultadoRelatorio(
        caminho=plano.destino,
        arquivados=tuple(arquivados),
        avisos=tuple(avisos),
    )


# Nome e lugar do arquivo


def nome_do_relatorio(matricula: str, quando: date) -> str:
    """
    Monta `Relatorio_00742_2026-09-20.docx`, como o roteiro pede.

    A matrícula vem da ficha e passa pela mesma limpeza dos nomes de pasta: ela
    é digitada por outra pessoa, em outro sistema, e o que vem de fora não monta
    caminho.
    """
    limpa = sanitizar(str(matricula)) or "sem_matricula"
    limpa = Path(limpa).name
    return f"{PREFIXO_RELATORIO}{limpa}_{quando:%Y-%m-%d}.docx"


def relatorios_na_pasta(raiz: Path) -> tuple[Path, ...]:
    """
    Os relatórios que já estão na raiz do projeto, em ordem.

    O `.docx` mora na raiz da pasta do projeto, e não em uma `4. Relatórios/`. É
    um desvio deliberado do apêndice A do roteiro, já registrado no `projeto.py`:
    o relatório é o produto que se entrega, e ele fica onde a mão alcança
    primeiro ao abrir a pasta.
    """
    raiz = Path(raiz)
    if not raiz.is_dir():
        return ()
    return tuple(
        sorted(
            arquivo
            for arquivo in raiz.iterdir()
            if arquivo.is_file()
            and arquivo.name.startswith(PREFIXO_RELATORIO)
            and arquivo.suffix.lower() == ".docx"
            and not arquivo.name.startswith("~$")  # o lixo que o Word deixa aberto
        )
    )


def _arquivamentos(raiz: Path, destino: Path) -> tuple[tuple[Path, Path], ...]:
    """
    O que sai da raiz e vai para `2. Versões antigas/`.

    **Todos** os relatórios anteriores, não só o de hoje. A raiz do projeto fica
    com um relatório só — o vigente —, que é a mesma regra que `1. Dados
    originais/` segue para o banco. Uma pasta com três `.docx` de datas
    diferentes é uma pasta em que alguém vai anexar o errado no e-mail.

    Duas rodadas no mesmo dia colidiriam no destino, porque o nome carrega a data
    e não a hora. O desempate é o sufixo numérico da Fase 5.
    """
    pares: list[tuple[Path, Path]] = []
    ocupados: set[Path] = set()

    for anterior in relatorios_na_pasta(raiz):
        alvo = raiz / PASTA_ANTIGAS / anterior.name
        sufixo = 2
        while alvo.exists() or alvo in ocupados:
            alvo = alvo.with_name(f"{anterior.stem}_{sufixo}{anterior.suffix}")
            sufixo += 1
        ocupados.add(alvo)
        pares.append((anterior, alvo))

    # O destino ainda não existe no disco quando o plano é montado, mas se ele
    # for um dos anteriores (mesma data, mesma matrícula) já está na lista acima.
    _ = destino
    return tuple(pares)


def _localizar_template(raiz: Path, template: Path | str | None) -> Path | None:
    """
    Qual `.docx` empresta os estilos, e nesta ordem.

    1. o `--template` que você passou;
    2. o `template.docx` da **pasta do projeto**, para o cliente que exige um
       modelo próprio;
    3. o `template.docx` do `FLATCAP_ROOT`, que é onde o modelo institucional
       mora — fora do repositório, como todo o resto que não é código;
    4. nenhum: o documento sai com os estilos padrão do `documento.py`.

    O modelo mora fora do repositório de propósito. Ele carrega logotipo e
    identidade visual da instituição, muda sem pedir licença a ninguém, e é
    binário — três razões pelas quais ele não é código.
    """
    if template is not None:
        caminho = Path(template).expanduser()
        if not caminho.is_file():
            raise ModeloAusenteError(
                f"O modelo indicado em `--template` não existe:\n  {caminho}\n"
                "Confira o caminho. Se ele tiver espaço no nome, ponha entre aspas."
            )
        return caminho

    raiz = Path(raiz)
    for candidato in (raiz / "template.docx", raiz.parent / "template.docx"):
        if candidato.is_file():
            return candidato
    return None


# A rodada


def _manifesto_da_rodada(pasta: Path) -> Manifesto:
    """
    O manifesto da descritiva vigente, com a recusa quando não há rodada.
    """
    if not (pasta / ARQUIVO_MANIFESTO).is_file():
        raise DescritivaAusenteError(
            f"Este projeto não tem uma descritiva para relatar.\n"
            f"Esperado em: {pasta}/{ARQUIVO_MANIFESTO}\n\n"
            "O relatório monta os arquivos que a descritiva escreveu — ele não "
            "abre o banco e não recalcula nada, que é o que garante que o "
            "documento e as tabelas digam o mesmo número.\n"
            "Rode `flatcap descritiva <id> --sim` antes."
        )
    return ler_manifesto(pasta)


def _secoes(pasta: Path, manifesto: Manifesto) -> tuple[tuple[Secao, ...], list[str]]:
    """
    Uma seção por variável do manifesto, na ordem dele.

    Artefato que sumiu da pasta não interrompe nada: ele é anotado e o documento
    sai sem aquela tabela ou figura, com o alerta dizendo qual. O contrário —
    recusar por causa de um `.png` apagado — seria transformar um acidente
    reversível em um comando que não roda.
    """
    secoes: list[Secao] = []
    ausentes: list[str] = []

    for item in manifesto.itens:
        tabelas: list[TabelaLida] = []
        figuras: list[Figura] = []

        for artefato in item.artefatos:
            caminho = pasta / artefato.arquivo
            if not caminho.is_file():
                ausentes.append(artefato.arquivo)
                continue
            if artefato.e_tabela:
                tabelas.append(ler_tabela(caminho, artefato.especie, artefato.titulo))
            elif artefato.e_figura:
                figuras.append(
                    Figura(
                        arquivo=artefato.arquivo,
                        caminho=caminho,
                        especie=artefato.especie,
                        titulo=artefato.titulo or item.rotulo or item.variavel,
                    )
                )

        secoes.append(
            Secao(
                variavel=item.variavel,
                rotulo=item.rotulo or item.variavel,
                tipo=item.tipo,
                n=item.n,
                faltantes=item.faltantes,
                tabelas=tuple(tabelas),
                figuras=tuple(figuras),
            )
        )

    return tuple(secoes), ausentes


def ler_tabela(caminho: Path, especie: str = "", titulo: str = "") -> TabelaLida:
    """
    Lê um `.csv` da descritiva sem o `pandas` e sem converter valor nenhum.

    O formato é o que a Fase 5 escreve: BOM, algumas linhas de comentário com o
    título e os denominadores, e a tabela separada por `;`. As linhas de
    comentário viram `notas` — elas carregam os dois denominadores da tabela de
    frequência, que é a resposta do roteiro para "quando o cliente lê 45%, ele
    precisa saber se o denominador incluiu os casos sem resposta".

    Sem `pandas` de propósito. Não é economia de dependência — o `pandas` está
    instalado —, é economia de conversão: `pd.read_csv` leria `28,7` como texto
    ou como número dependendo do `decimal=`, e das duas uma sairia diferente do
    que está no arquivo. Aqui o texto atravessa intacto.
    """
    caminho = Path(caminho)
    try:
        texto = caminho.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        try:
            texto = caminho.read_text(encoding="cp1252")
        except (OSError, UnicodeDecodeError) as erro:
            raise TabelaIlegivelError(_mensagem_ilegivel(caminho, erro)) from erro
    except OSError as erro:
        raise TabelaIlegivelError(_mensagem_ilegivel(caminho, erro)) from erro

    comentarios: list[str] = []
    corpo: list[str] = []
    for linha in texto.splitlines():
        if linha.lstrip().startswith("#"):
            comentarios.append(linha.lstrip().lstrip("#").strip())
        elif linha.strip():
            corpo.append(linha)

    if not corpo:
        raise TabelaIlegivelError(
            f"O arquivo `{caminho.name}` da descritiva não tem nenhuma linha de "
            "dados — só o cabeçalho de comentário.\n"
            "Rode `flatcap descritiva <id> --sim` para refazer a rodada."
        )

    leitor = csv.reader(io.StringIO("\n".join(corpo)), delimiter=_SEPARADOR_CAMPO)
    linhas = [tuple(campo.strip() for campo in registro) for registro in leitor]
    colunas, dados = linhas[0], linhas[1:]

    # O primeiro comentário é o título do arquivo; o título do manifesto é o
    # mesmo texto e tem precedência, para que o documento e o índice não possam
    # divergir. O resto vira nota, menos a linha `variável:`.
    notas = [
        nota
        for nota in comentarios[1:]
        if nota and not _NOTA_REDUNDANTE.match(nota)
    ]

    return TabelaLida(
        arquivo=caminho.name,
        especie=especie,
        titulo=titulo or (comentarios[0] if comentarios else caminho.stem),
        notas=tuple(notas),
        colunas=colunas,
        linhas=tuple(dados),
    )


# As conferências


def _conferir_banco(
    raiz: Path, ficha: Ficha, manifesto: Manifesto, conferir: bool
) -> list[Alerta]:
    """
    A rodada ainda descreve a versão vigente do banco?

    Duas perguntas diferentes, e vale separá-las porque o que fazer é diferente:

    * **outra versão** — o cliente mandou o banco revisado e a descritiva não foi
      refeita. O documento fala de uma versão que não é mais a de trabalho.
    * **arquivo alterado** — o mesmo arquivo foi aberto e salvo por cima depois
      de registrado. Aí nem a ficha descreve mais o que está no disco.

    A comparação é de `sha256`, e o da rodada está no próprio manifesto. Não há
    releitura do banco aqui: o `sha256` da versão vigente vem da ficha, e a
    conferência contra o disco é a mesma `linha_do_tempo` da Fase 3 — porque duas
    implementações da mesma conferência é como um comando diz "confere" enquanto
    o outro diz "ALTERADO" sobre o mesmo arquivo.
    """
    alertas: list[Alerta] = []
    da_rodada = str(manifesto.banco.get("sha256") or "").lower()
    arquivo_da_rodada = str(manifesto.banco.get("arquivo") or "?")

    vigente: Versao | None = versao_vigente(ficha)
    if vigente is None:
        return alertas

    if da_rodada and vigente.sha256 and da_rodada != vigente.sha256.lower():
        alertas.append(
            Alerta(
                codigo="banco_mudou",
                titulo="a descritiva foi feita sobre outra versão do banco",
                detalhe=(
                    f"Os números deste documento saíram de `{arquivo_da_rodada}`, e a "
                    f"versão vigente do projeto hoje é `{vigente.arquivo}`. "
                    "Para que o documento fale da versão atual, rode "
                    "`flatcap descritiva <id> --sim` e gere o relatório de novo."
                ),
            )
        )

    if not conferir:
        return alertas

    try:
        tempo = linha_do_tempo(raiz, conferir=True)
    except OSError:  # pragma: no cover - o disco já foi lido várias vezes até aqui
        return alertas

    for item in tempo.itens:
        if item.versao.arquivo != arquivo_da_rodada:
            continue
        if item.caminho is None:
            alertas.append(
                Alerta(
                    codigo="banco_ausente",
                    titulo="o banco descrito não está mais no disco",
                    detalhe=(
                        f"`{arquivo_da_rodada}` está registrado na ficha e não está na "
                        "pasta. As tabelas continuam válidas — elas foram escritas "
                        "quando o arquivo existia —, mas não há como conferi-las "
                        "contra a origem."
                    ),
                )
            )
        elif item.confere is False:
            alertas.append(
                Alerta(
                    codigo="banco_alterado",
                    titulo="o arquivo do banco foi alterado depois de registrado",
                    detalhe=(
                        f"`{arquivo_da_rodada}` está no disco com conteúdo diferente do "
                        "que foi registrado na ficha. Alguém o abriu e salvou por cima. "
                        "Trate o arquivo alterado como versão nova: rode "
                        "`flatcap dados adicionar` e refaça a descritiva."
                    ),
                )
            )

    return alertas


def _conferir_dicionario(
    raiz: Path, manifesto: Manifesto
) -> tuple[Alerta | None, str]:
    """
    O `dicionario.csv` de hoje é o que dirigiu a rodada?

    É a divergência mais fácil de acontecer e a mais difícil de perceber: você
    corrige um rótulo ou muda uma faixa depois de rodar a descritiva, gera o
    documento, e ele sai com os títulos antigos e os cortes antigos — bonito, e
    descrevendo uma decisão que você já revogou.

    Quatro diferenças são procuradas: variável que entrou, variável que saiu,
    tipo trocado e rótulo reescrito, mais as faixas, que o manifesto guarda em
    `detalhes`. Um dicionário ilegível **não** interrompe o relatório: ele já
    cumpriu o papel dele quando a rodada foi gerada, e recusar aqui seria travar
    o documento por causa de um arquivo que o documento não usa.
    """
    try:
        linhas = ler_dicionario(raiz)
    except Exception as erro:  # noqa: BLE001 - ver a justificativa acima
        return None, (
            f"Não consegui ler o {ARQUIVO_DICIONARIO} para conferir se ele mudou "
            f"depois da rodada: {erro}"
        )

    if not linhas:
        return (
            Alerta(
                codigo="dicionario_ausente",
                titulo=f"o {ARQUIVO_DICIONARIO} não está mais na pasta",
                detalhe=(
                    "As tabelas deste documento obedeceram a um dicionário que não "
                    "está mais lá. Não há como conferir se elas descrevem as decisões "
                    "que valem hoje."
                ),
            ),
            "",
        )

    conhecidas = {item.variavel: item for item in manifesto.itens}
    vazias = {
        str(entrada.get("variavel", ""))
        for entrada in manifesto.fora
        if "sem nenhum valor" in str(entrada.get("motivo", ""))
    }
    analisaveis = {linha.variavel: linha for linha in linhas if linha.analisavel}

    mudancas: list[str] = []

    for nome in analisaveis:
        if nome not in conhecidas and nome not in vazias:
            mudancas.append(f"`{nome}` entrou no dicionário depois da rodada")
    for nome in conhecidas:
        if nome not in analisaveis:
            mudancas.append(f"`{nome}` saiu da descritiva depois da rodada")

    for nome, linha in analisaveis.items():
        item = conhecidas.get(nome)
        if item is None:
            continue
        if linha.tipo != item.tipo:
            mudancas.append(
                f"`{nome}` era `{item.tipo}` na rodada e é `{linha.tipo}` hoje"
            )
        rotulo = linha.rotulo or linha.variavel
        if rotulo != item.rotulo:
            mudancas.append(
                f"`{nome}` mudou de rótulo: «{item.rotulo}» → «{rotulo}»"
            )
        diferenca = _faixas_mudaram(linha.faixas, item.detalhes)
        if diferenca:
            mudancas.append(f"`{nome}` {diferenca}")

    if not mudancas:
        return None, ""

    return (
        Alerta(
            codigo="dicionario_mudou",
            titulo=f"o {ARQUIVO_DICIONARIO} mudou depois desta rodada",
            detalhe=(
                "As tabelas deste documento obedecem ao dicionário de quando a "
                "descritiva foi gerada, e ele mudou desde então:\n"
                + "\n".join(f"— {mudanca}" for mudanca in mudancas[:8])
                + (
                    f"\n— e mais {len(mudancas) - 8} diferença(s)."
                    if len(mudancas) > 8
                    else ""
                )
                + "\nRode `flatcap descritiva <id> --sim` e gere o relatório de novo."
            ),
        ),
        "",
    )


def _faixas_mudaram(faixas: tuple[str, ...], detalhes: dict[str, Any]) -> str:
    """
    Compara os cortes do dicionário com os que a rodada usou.

    O manifesto guarda `origem` (`dicionario` ou `quartis`) e os `cortes` já
    arredondados. As três formas de divergir são: faixas preenchidas depois de a
    rodada ter usado quartis, faixas apagadas, e cortes diferentes.
    """
    registradas = detalhes.get("faixas")
    if not isinstance(registradas, dict):
        return ""

    origem = registradas.get("origem")
    cortes = registradas.get("cortes") or []

    if faixas and origem != "dicionario":
        return "ganhou faixas no dicionário depois da rodada, que usou os quartis"
    if not faixas and origem == "dicionario":
        return "perdeu as faixas do dicionário; a rodada usou os cortes que estavam lá"
    if not faixas:
        return ""

    try:
        pedidos = [float(str(corte).replace(",", ".")) for corte in faixas]
    except ValueError:  # pragma: no cover - o dicionario.py já validou na leitura
        return ""

    usados = [float(corte) for corte in cortes if corte is not None]
    if len(pedidos) != len(usados) or any(
        abs(a - b) > 1e-9 for a, b in zip(pedidos, usados, strict=True)
    ):
        return "está com outros cortes de faixa do que os usados na rodada"
    return ""


# Mensagens


def _mensagem_ilegivel(caminho: Path, erro: Exception) -> str:
    return (
        f"Não consegui ler `{caminho.name}`, que a descritiva escreveu.\n"
        "Os arquivos da rodada não são feitos para ser editados à mão — se você "
        "precisou mexer em um, apague a pasta e rode `flatcap descritiva <id> --sim` "
        "de novo.\n\n"
        f"Detalhe técnico: {type(erro).__name__}: {erro}"
    )


def _acao_do_historico(plano: PlanoRelatorio) -> str:
    relatorio = plano.relatorio
    partes = [
        f"`flatcap relatorio {relatorio.ficha.record_id}` — `{plano.destino.name}` "
        f"escrito a partir da descritiva de "
        f"{relatorio.manifesto.gerado_em:%d/%m/%Y %H:%M}: "
        f"{len(relatorio.secoes)} seção(ões), {plano.total_tabelas} tabela(s) e "
        f"{plano.total_figuras} figura(s)."
    ]
    for _, para in plano.arquivamentos:
        partes.append(f"`{para.name}` foi para `{PASTA_ANTIGAS}/`.")
    if plano.template is not None:
        partes.append(f"Modelo: `{plano.template.name}`.")
    if relatorio.alertas:
        quais = ", ".join(alerta.codigo for alerta in relatorio.alertas)
        partes.append(f"Com aviso no documento: {quais}.")
    return " ".join(partes)


__all__ = [
    "Alerta",
    "Figura",
    "PlanoRelatorio",
    "Relatorio",
    "RelatorioError",
    "DescritivaAusenteError",
    "ModeloAusenteError",
    "ResultadoRelatorio",
    "Secao",
    "TabelaIlegivelError",
    "TabelaLida",
    "executar_relatorio",
    "ler_tabela",
    "nome_do_relatorio",
    "preparar_relatorio",
    "relatorios_na_pasta",
]
