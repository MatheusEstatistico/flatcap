"""
Abrir o banco de dados de um projeto.

Três fases diferentes precisam da mesma resposta para a mesma pergunta — *qual
arquivo é o banco deste projeto, agora?*. A Fase 4 diagnostica, a Fase 5 analisa
e a Fase 6 relata, e todas as três abrem o mesmo arquivo. Se cada uma decidisse
por conta própria, bastaria uma discordância para a descritiva ser feita sobre
uma versão e o relatório sobre outra — divergência que ninguém percebe, porque
os dois documentos saem bonitos.

Por isso a resposta mora aqui, sozinha, e as camadas de cima recebem um `Banco`
já aberto.

## O que este módulo decide

**Qual versão.** A vigente é a de maior número de sequência registrada em
`dados:` — a revisada quando existe, e o `00_redcap_*` enquanto ela não chegar.
A busca é pela ficha, não pela pasta: um arquivo largado à mão em
`1. Dados originais/` não vira banco por estar lá.

**Se dá para confiar nela.** A conferência reusa `dados.linha_do_tempo`, que é
onde a Fase 3 já respondia "este arquivo ainda é o que foi registrado?". Não há
uma segunda leitura de `sha256` neste módulo de propósito: duas implementações
da mesma conferência é como um comando passa a dizer "confere" enquanto o outro
diz "ALTERADO" sobre o mesmo arquivo.

    * **ausente** — a ficha registra e o disco não tem: recusa. Não há o que
      perfilar, e prosseguir produziria um relatório sobre um arquivo que não
      existe.
    * **alterado** — está lá com conteúdo diferente do registrado: abre, avisa
      e o aviso viaja dentro do `Banco` até o `perfil.md`. É diagnóstico, e
      diagnóstico não bloqueia; mas fica escrito no documento que você leva para
      a reunião que o banco perfilado não é o que a ficha descreve.

**Como ler.** `.xlsx` e `.csv`, que é o que o cliente manda. Formato fora dessa
lista é recusado com o que fazer — e não com o estouro do `pandas`.

## O que este módulo deliberadamente não faz

Não conserta nada. Vírgula decimal, número guardado como texto e data escrita à
mão continuam exatamente como estão no arquivo: quem lê passando `decimal=","`
não vê o problema, e o problema é justamente o produto da Fase 4. A leitura é
fiel ao que o cliente mandou, e é o `perfil.py` que aponta o que está torto.
"""

from __future__ import annotations

import csv
import warnings
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .dados import ItemDaLinha, linha_do_tempo
from .ficha import Versao, versao_vigente
from .projeto import PASTA_ANTIGAS, PASTA_DADOS, tamanho_legivel

EXTENSOES_SUPORTADAS = (".xlsx", ".csv")

# Formato que aparece na prática, que a gente reconhece e mesmo assim não abre.
# A mensagem diz o que fazer, porque "formato não suportado" sozinho não ajuda
# ninguém que acabou de receber o arquivo do cliente.
_CONVERSAO = {
    ".xls": "Excel antigo. Abra no Excel e salve como `.xlsx`.",
    ".xlsm": "Planilha com macros. Abra no Excel e salve como `.xlsx`.",
    ".xlsb": "Planilha binária. Abra no Excel e salve como `.xlsx`.",
    ".ods": "Planilha do LibreOffice. Salve como `.xlsx`.",
    ".sav": "Banco do SPSS. Exporte como `.xlsx` ou `.csv`.",
    ".zsav": "Banco do SPSS comprimido. Exporte como `.xlsx` ou `.csv`.",
    ".dta": "Banco do Stata. Exporte como `.xlsx` ou `.csv`.",
    ".rdata": "Objeto do R. Exporte com `write.csv()`.",
    ".rds": "Objeto do R. Exporte com `write.csv()`.",
    ".json": "Exporte como `.csv` a tabela que interessa.",
    ".txt": "Se for uma tabela, renomeie para `.csv`.",
    ".pdf": "PDF não é banco de dados. Peça o arquivo original ao cliente.",
    ".docx": "Documento de texto não é banco de dados. Peça o arquivo original.",
}

_AMOSTRA_BYTES = 64 * 1024
_SEPARADORES = (";", ",", "\t", "|")
_CODIFICACOES = ("utf-8", "cp1252", "latin-1")

# Os formatos de data escritos à mão, na ordem em que são testados. Moram aqui, e
# não em quem os usa, porque este é o módulo que sabe como o arquivo do cliente
# chega — e porque a Fase 4, que denuncia a data escrita como texto, e a Fase 5,
# que precisa convertê-la para descrever o período, têm de dar exatamente a mesma
# resposta. Duas listas de formatos é como um comando lê `03/04` como 3 de abril
# e o outro como 4 de março.
FORMATOS_DATA: tuple[str, ...] = (
    "%d/%m/%Y",
    "%d/%m/%y",
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%Y/%m/%d",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y %H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
)

PROPORCAO_PARA_AFIRMAR = 0.9  # a partir daqui dá para afirmar "a coluna é isto"


class BancoError(RuntimeError):
    """
    Falha ao abrir o banco, já traduzida para o usuário.

    Erro próprio pelo mesmo motivo de `ConfigError`, `RedcapError`, `ProjetoError`
    e `FichaError`: a CLI captura esta classe e transforma em painel. Qualquer
    outra exceção é bug de verdade e deve subir com o traceback inteiro.
    """


class BancoNaoRegistradoError(BancoError):
    """
    O projeto existe, mas nenhuma versão do banco foi registrada na ficha.
    """


class BancoAusenteError(BancoError):
    """
    A ficha registra a versão vigente e ela não está no disco.
    """


class FormatoNaoSuportadoError(BancoError):
    """
    O arquivo existe e o FlatCap não abre esse formato.
    """


class BancoIlegivelError(BancoError):
    """
    O formato é suportado, mas o arquivo não abriu — corrompido, protegido por
    senha, ou não é o que a extensão diz.
    """


class BancoVazioError(BancoError):
    """
    O arquivo abriu e não tem linha nenhuma, ou não tem coluna nenhuma.
    """


class AbaInexistenteError(BancoError):
    """
    A planilha pedida em `--aba` não existe na pasta de trabalho.
    """


@dataclass(frozen=True)
class Leitura:
    """
    Como o arquivo foi lido. Vai inteiro para o cabeçalho do `perfil.md`.

    Registrar a planilha, o separador e a codificação não é preciosismo: são as
    três decisões que o leitor tomou sozinho, e a única forma de descobrir que
    ele tomou a errada é vê-las escritas. Um `perfil.md` de 800 linhas gerado a
    partir da aba "Dicionário" em vez da aba "Dados" parece perfeitamente
    normal até alguém reparar no cabeçalho.
    """

    caminho: Path
    aba: str | None = None
    abas: tuple[str, ...] = ()
    separador: str | None = None
    codificacao: str | None = None
    avisos: tuple[str, ...] = ()  # o que o leitor teve de relevar para abrir

    @property
    def formato(self) -> str:
        return self.caminho.suffix.lower()

    @property
    def outras_abas(self) -> tuple[str, ...]:
        return tuple(nome for nome in self.abas if nome != self.aba)

    def descrever(self) -> str:
        """
        Uma linha dizendo de onde os dados vieram, com o que for pertinente.
        """
        partes = [f"`{self.caminho.name}`"]
        if self.aba:
            partes.append(f'planilha "{self.aba}"')
        if self.separador:
            legivel = {"\t": "tabulação"}.get(self.separador, f"`{self.separador}`")
            partes.append(f"separador {legivel}")
        if self.codificacao:
            partes.append(f"codificação {self.codificacao}")
        return " · ".join(partes)


@dataclass(frozen=True)
class Banco:
    """
    O banco aberto, com a procedência junto.

    O `quadro` é o único objeto mutável que circula pelo FlatCap, e é assim
    porque um `DataFrame` copiado a cada camada custa memória à toa. As camadas
    de cima leem e não escrevem.
    """

    quadro: pd.DataFrame
    versao: Versao
    leitura: Leitura
    confere: bool | None
    avisos: tuple[str, ...] = ()

    @property
    def linhas(self) -> int:
        return int(self.quadro.shape[0])

    @property
    def colunas(self) -> int:
        return int(self.quadro.shape[1])

    @property
    def tamanho_legivel(self) -> str:
        return tamanho_legivel(self.versao.tamanho_bytes)


def caminho_da_versao(raiz: Path, versao: Versao) -> Path | None:
    """
    Onde está, no disco, o arquivo de uma versão registrada.
    """
    for pasta in (Path(raiz) / PASTA_DADOS, Path(raiz) / PASTA_ANTIGAS):
        candidato = pasta / versao.arquivo
        if candidato.is_file():
            return candidato
    return None


# `versao_vigente` desceu para o `ficha.py` na Fase 6 e continua acessível daqui
# como `banco.versao_vigente`, porque é deste módulo que os chamadores a importam
# desde a Fase 4. O motivo da mudança de casa está na docstring dela: responder
# "qual versão vale?" é ler a ficha, e o `relatorio.py` precisa dessa resposta sem
# carregar o `pandas`. Mesma manobra que a Fase 5 fez com `formato_de_data`, na
# direção contrária.


def abrir(raiz: Path, aba: str | None = None, conferir: bool = True) -> Banco:
    """
    Abre a versão vigente do banco de um projeto.

    Args:
        raiz: a pasta do projeto (a que tem o `projeto.yaml`).
        aba: nome da planilha, para `.xlsx` com mais de uma. Sem isso, a primeira.
        conferir: reler o `sha256` e comparar com o registrado.

    Raises:
        FichaAusenteError, FichaInvalidaError: a ficha do projeto não abre.
        BancoNaoRegistradoError: nenhuma versão em `dados:`.
        BancoAusenteError: a versão vigente não está no disco.
        FormatoNaoSuportadoError, BancoIlegivelError, BancoVazioError,
        AbaInexistenteError.
    """
    raiz = Path(raiz)
    tempo = linha_do_tempo(raiz, conferir=conferir)
    versao = versao_vigente(tempo.ficha)

    if versao is None:
        raise BancoNaoRegistradoError(_mensagem_sem_versao(tempo.nao_registrados))

    item = _item_da_versao(tempo.itens, versao)
    caminho = item.caminho if item is not None else caminho_da_versao(raiz, versao)

    if caminho is None:
        raise BancoAusenteError(
            f"A versão vigente do banco está registrada na ficha e não está no disco:\n"
            f"  {versao.arquivo}\n\n"
            "Alguém apagou ou renomeou o arquivo. O registro continua valendo como prova "
            "de que a versão existiu — não apague a entrada da ficha.\n"
            "Rode `flatcap dados listar` para ver a divergência inteira."
        )

    quadro, leitura = abrir_arquivo(caminho, aba=aba)

    avisos: list[str] = list(leitura.avisos)
    confere = item.confere if item is not None else None
    if confere is False:
        avisos.append(
            f"O arquivo `{versao.arquivo}` está no disco com conteúdo diferente do que "
            "foi registrado na ficha. Alguém o abriu e salvou por cima depois do "
            "registro. O perfil descreve o arquivo que está lá, não o que a ficha "
            "descreve — trate o arquivo alterado como versão nova e rode "
            "`flatcap dados adicionar`."
        )
    if leitura.outras_abas:
        quais = ", ".join(f'"{nome}"' for nome in leitura.outras_abas)
        avisos.append(
            f'A pasta de trabalho tem mais de uma planilha. Foi lida "{leitura.aba}"; '
            f"as outras ({quais}) ficaram de fora. Use `--aba` para escolher."
        )

    return Banco(
        quadro=quadro,
        versao=versao,
        leitura=leitura,
        confere=confere,
        avisos=tuple(avisos),
    )


def abrir_arquivo(caminho: Path, aba: str | None = None) -> tuple[pd.DataFrame, Leitura]:
    """
    Lê um arquivo solto, sem passar pela ficha. Devolve o quadro e como ele foi lido.
    """
    caminho = Path(caminho)
    extensao = caminho.suffix.lower()

    if extensao not in EXTENSOES_SUPORTADAS:
        raise FormatoNaoSuportadoError(_mensagem_formato(caminho))

    if extensao == ".xlsx":
        quadro, leitura = _ler_xlsx(caminho, aba)
    else:
        quadro, leitura = _ler_csv(caminho)

    if quadro.shape[1] == 0:
        raise BancoVazioError(
            f"O arquivo `{caminho.name}` abriu sem nenhuma coluna.\n"
            "Isso costuma ser uma planilha vazia ou uma aba de rascunho."
        )
    if quadro.shape[0] == 0:
        raise BancoVazioError(
            f"O arquivo `{caminho.name}` tem cabeçalho e nenhuma linha de dados.\n"
            "Confira se o cliente mandou o arquivo certo, ou se os dados estão em "
            "outra planilha da mesma pasta de trabalho."
        )

    return quadro, leitura


# Leitura por formato


def _ler_xlsx(caminho: Path, aba: str | None) -> tuple[pd.DataFrame, Leitura]:
    """
    Lê uma planilha. Sem `--aba`, lê a primeira e diz quais ficaram de fora.

    Ler a primeira é uma escolha, não a única possível: dava para chutar a de
    mais células, ou a que se chama "dados". Ficou a primeira porque é
    determinística e explicável — o aviso sobre as outras abas é o que impede
    que a escolha passe despercebida, e isso vale mais do que acertar sozinho na
    maioria das vezes e errar em silêncio no resto.

    O `except Exception` aqui é deliberado, e é a única exceção à regra da casa de
    que exceção não prevista é bug e deve subir com o traceback. Um arquivo
    corrompido, protegido por senha ou com a extensão trocada estoura em lugares
    diferentes de duas bibliotecas de terceiros — `BadZipFile`, `KeyError`,
    `InvalidFileException`, `struct.error` —, e a lista não é fechada nem
    documentada. O que interessa a quem acabou de receber o arquivo do cliente é
    sempre a mesma frase, e não o nome da exceção. O `try` cobre só as duas
    chamadas de leitura, para que bug daqui de dentro continue subindo inteiro.
    """
    try:
        with pd.ExcelFile(caminho, engine="openpyxl") as planilha:
            abas = tuple(str(nome) for nome in planilha.sheet_names)
            if aba is not None and aba not in abas:
                raise AbaInexistenteError(
                    f'A pasta de trabalho não tem a planilha "{aba}".\n'
                    f"Planilhas deste arquivo: {', '.join(abas)}"
                )
            escolhida = aba if aba is not None else abas[0]
            quadro = pd.read_excel(planilha, sheet_name=escolhida)
    except AbaInexistenteError:
        raise
    except Exception as erro:  # noqa: BLE001 - ver a justificativa acima
        raise BancoIlegivelError(_mensagem_ilegivel(caminho, erro)) from erro

    return quadro, Leitura(caminho=caminho, aba=str(escolhida), abas=abas)


def _ler_csv(caminho: Path) -> tuple[pd.DataFrame, Leitura]:
    """
    Lê um `.csv` descobrindo a codificação e o separador.

    Um `.csv` exportado do Excel em português vem com `;` e em cp1252. Um `.csv`
    exportado do R ou do Python vem com `,` e em UTF-8. Os dois chegam aqui com a
    mesma extensão e nenhuma marca que os distinga, então ou o leitor descobre,
    ou metade dos arquivos abre como uma coluna só de texto — o que produziria um
    perfil perfeitamente formatado e completamente errado.

    A ordem das codificações importa: UTF-8 primeiro porque é a única que **falha**
    quando o palpite está errado (byte inválido estoura), o que a torna um teste de
    verdade. `latin-1` fica por último porque decodifica qualquer byte sem
    reclamar: tentada antes, aceitaria um arquivo UTF-8 e devolveria "JosÃ©".
    """
    bruto = caminho.read_bytes()[:_AMOSTRA_BYTES]

    codificacao, amostra = _decodificar(bruto)
    separador = _separador(amostra)

    avisos: list[str] = []
    try:
        # O `pandas` avisa por `warnings` que perdeu campo, e um `warning` impresso
        # no meio da saída de um comando é um recado que o usuário aprende a
        # ignorar. Capturado aqui, ele vira um aviso do FlatCap e viaja até o
        # `perfil.md` e o manifesto da descritiva, junto do resto.
        with warnings.catch_warnings(record=True) as capturados:
            warnings.simplefilter("always", pd.errors.ParserWarning)
            quadro = pd.read_csv(
                caminho,
                sep=separador,
                encoding=codificacao,
                engine="python",  # tolera linha com número de campos diferente do cabeçalho
                skip_blank_lines=True,
                # Sem isto, uma linha com mais campos do que o cabeçalho faz o
                # `pandas` promover a primeira coluna a índice — e a tabela inteira
                # anda uma casa para a esquerda sem que nada avise. Melhor perder o
                # campo sobrando, que fica avisado, do que deslocar tudo em silêncio.
                index_col=False,
            )
        if any(issubclass(c.category, pd.errors.ParserWarning) for c in capturados):
            avisos.append(
                f"O arquivo `{caminho.name}` tem linha com mais campos do que o "
                f"cabeçalho, e o que sobrou foi descartado. Quase sempre é um "
                f"`{separador}` digitado dentro de um campo de texto. Confira o "
                "arquivo antes de confiar nas colunas da direita."
            )
    except pd.errors.EmptyDataError as erro:
        raise BancoVazioError(
            f"O arquivo `{caminho.name}` não tem nem a linha de cabeçalho — são "
            f"{caminho.stat().st_size} bytes.\n"
            "Download interrompido ou exportação que não chegou a escrever nada."
        ) from erro
    except Exception as erro:  # noqa: BLE001 - mesma justificativa do `.xlsx`
        raise BancoIlegivelError(_mensagem_ilegivel(caminho, erro)) from erro

    return quadro, Leitura(
        caminho=caminho,
        separador=separador,
        codificacao=codificacao,
        avisos=tuple(avisos),
    )


def _decodificar(bruto: bytes) -> tuple[str, str]:
    """
    Descobre a codificação da amostra. Devolve o nome e o texto decodificado.
    """
    if bruto.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig", bruto[3:].decode("utf-8", errors="replace")

    for nome in _CODIFICACOES:
        try:
            # `strict` de propósito: o erro é o que descarta o palpite.
            return nome, bruto.decode(nome)
        except UnicodeDecodeError:
            continue

    return "latin-1", bruto.decode("latin-1", errors="replace")


def _separador(amostra: str) -> str:
    """
    Descobre o separador pela primeira linha não vazia.

    O `csv.Sniffer` tem a primeira palavra porque entende aspas. Quando ele se
    recusa a decidir, a contagem no cabeçalho resolve.

    O caso que sobra é o cabeçalho **sem separador nenhum** — um arquivo de uma
    coluna só. Cair em `,` ali é o que quebrava: um `.csv` de uma coluna com
    `peso` no cabeçalho e `70,5` nas linhas era partido em duas colunas, e o
    `pandas`, vendo mais campos do que nomes, promovia a primeira metade a índice
    em silêncio. O que chegava à análise era a coluna `peso` valendo 5, 2, 0 — e
    nada na saída denunciava. Então, quando o cabeçalho não tem separador, o
    escolhido é um que também não apareça no resto da amostra: o arquivo tem uma
    coluna, e é assim que ele é lido.
    """
    linhas = [linha for linha in amostra.splitlines() if linha.strip()]
    cabecalho = linhas[0] if linhas else ""

    try:
        dialeto = csv.Sniffer().sniff(cabecalho, delimiters="".join(_SEPARADORES))
    except csv.Error:
        pass
    else:
        if dialeto.delimiter in _SEPARADORES:
            return dialeto.delimiter

    contagens = {separador: cabecalho.count(separador) for separador in _SEPARADORES}
    melhor = max(contagens, key=lambda separador: contagens[separador])
    if contagens[melhor]:
        return melhor

    corpo = "\n".join(linhas[1:8])
    for separador in _SEPARADORES:
        if separador not in corpo:
            return separador
    return ","


# Mensagens


def _item_da_versao(itens: tuple[ItemDaLinha, ...], versao: Versao) -> ItemDaLinha | None:
    for item in itens:
        if item.versao.arquivo == versao.arquivo:
            return item
    return None


def _mensagem_sem_versao(nao_registrados: tuple[Path, ...]) -> str:
    """
    O projeto existe e o banco não. Duas situações diferentes, dois caminhos.
    """
    if nao_registrados:
        quais = "\n".join(f"  {p.parent.name}/{p.name}" for p in nao_registrados)
        return (
            "Este projeto não tem nenhuma versão do banco registrada na ficha, mas há "
            f"arquivo na pasta:\n{quais}\n\n"
            "O perfil é sempre de uma versão registrada — é o que permite escrever no "
            "`perfil.md` qual arquivo foi lido e com qual `sha256`. Para registrar, mova "
            "o arquivo para fora da pasta e rode `flatcap dados adicionar`."
        )
    return (
        "Este projeto ainda não tem banco.\n"
        "O registro no REDCap não trouxe anexo e nenhuma versão foi adicionada depois. "
        "Assim que o cliente mandar o arquivo, rode `flatcap dados adicionar`."
    )


def _mensagem_formato(caminho: Path) -> str:
    extensao = caminho.suffix.lower()
    suportados = " e ".join(f"`{e}`" for e in EXTENSOES_SUPORTADAS)
    linhas = [
        f"O FlatCap abre {suportados}, e este arquivo é `{extensao or 'sem extensão'}`:",
        f"  {caminho.name}",
        "",
    ]
    if extensao in _CONVERSAO:
        linhas.append(_CONVERSAO[extensao])
        linhas.append(
            "Depois de converter, registre a versão convertida com "
            "`flatcap dados adicionar` — assim a conversão fica na cronologia."
        )
    else:
        linhas.append(
            "Converta para `.xlsx` ou `.csv` e registre a versão convertida com "
            "`flatcap dados adicionar`."
        )
    return "\n".join(linhas)


def formato_de_data(
    textos: list[str], proporcao: float = PROPORCAO_PARA_AFIRMAR
) -> tuple[str | None, int]:
    """
    Descobre se uma coluna de texto é uma data escrita à mão, e em que formato.

    Devolve o formato e quantos valores ele explica; `(None, 0)` quando nenhum
    formato explica a coluna inteira.

    Testa um formato por vez, explícito, em vez de deixar o `pandas` adivinhar: o
    palpite dele aceita formatos misturados na mesma coluna e inverte dia com mês
    sem avisar. Para a Fase 4 isso é o detector `data_como_texto`; para a Fase 5 é
    a diferença entre converter uma coluna e inventar datas — e por isso a
    exigência é que **um único** formato explique a coluna quase toda. Coluna com
    dois formatos misturados não é convertida por ninguém: é devolvida como
    indecidível, que é o que ela é.
    """
    if not textos:
        return None, 0

    candidatos = [texto for texto in textos if any(s in texto for s in "/-.")]
    if len(candidatos) / len(textos) < proporcao:
        return None, 0

    serie = pd.Series(textos, dtype="object")
    for formato in FORMATOS_DATA:
        convertidas = pd.to_datetime(serie, format=formato, errors="coerce")
        quantas = int(convertidas.notna().sum())
        if quantas / len(textos) >= proporcao:
            return formato, quantas
    return None, 0


def _mensagem_ilegivel(caminho: Path, erro: Exception) -> str:
    return (
        f"Não consegui abrir `{caminho.name}`.\n\n"
        "As causas comuns são arquivo protegido por senha, download interrompido pela "
        "metade e arquivo com a extensão trocada (um `.csv` renomeado para `.xlsx` não "
        "vira planilha).\n"
        "Abra o arquivo no Excel para confirmar que ele abre lá.\n\n"
        f"Detalhe técnico: {type(erro).__name__}: {erro}"
    )