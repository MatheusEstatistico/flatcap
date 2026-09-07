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
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .dados import ItemDaLinha, linha_do_tempo
from .ficha import Ficha, Versao
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


def versao_vigente(ficha: Ficha) -> Versao | None:
    """
    A versão que vale hoje: a de maior número de sequência.

    Não é `ficha.dados[-1]`. A ordem da lista é a ordem em que as versões foram
    registradas, e a ficha é editada à mão — uma entrada acrescentada fora de
    ordem faria a última da lista deixar de ser a mais nova. O número do prefixo,
    esse, é o índice da versão por construção da Fase 3.

    Empate (duas entradas sem prefixo reconhecível) resolve pela ordem da lista,
    que é a melhor informação que sobra.
    """
    if not ficha.dados:
        return None
    return max(
        ficha.dados,
        key=lambda versao: (
            versao.sequencia if versao.sequencia is not None else -1,
            ficha.dados.index(versao),
        ),
    )


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

    avisos: list[str] = []
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

    try:
        quadro = pd.read_csv(
            caminho,
            sep=separador,
            encoding=codificacao,
            engine="python",  # tolera linha com número de campos diferente do cabeçalho
            skip_blank_lines=True,
        )
    except pd.errors.EmptyDataError as erro:
        raise BancoVazioError(
            f"O arquivo `{caminho.name}` não tem nem a linha de cabeçalho — são "
            f"{caminho.stat().st_size} bytes.\n"
            "Download interrompido ou exportação que não chegou a escrever nada."
        ) from erro
    except Exception as erro:  # noqa: BLE001 - mesma justificativa do `.xlsx`
        raise BancoIlegivelError(_mensagem_ilegivel(caminho, erro)) from erro

    return quadro, Leitura(caminho=caminho, separador=separador, codificacao=codificacao)


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
    recusa a decidir — acontece com cabeçalho de uma coluna só — a contagem
    resolve, e o empate cai em `,`, que é o padrão do formato.
    """
    linha = next((linha for linha in amostra.splitlines() if linha.strip()), "")

    try:
        dialeto = csv.Sniffer().sniff(linha, delimiters="".join(_SEPARADORES))
    except csv.Error:
        pass
    else:
        if dialeto.delimiter in _SEPARADORES:
            return dialeto.delimiter

    contagens = {separador: linha.count(separador) for separador in _SEPARADORES}
    melhor = max(contagens, key=lambda separador: contagens[separador])
    return melhor if contagens[melhor] else ","


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


def _mensagem_ilegivel(caminho: Path, erro: Exception) -> str:
    return (
        f"Não consegui abrir `{caminho.name}`.\n\n"
        "As causas comuns são arquivo protegido por senha, download interrompido pela "
        "metade e arquivo com a extensão trocada (um `.csv` renomeado para `.xlsx` não "
        "vira planilha).\n"
        "Abra o arquivo no Excel para confirmar que ele abre lá.\n\n"
        f"Detalhe técnico: {type(erro).__name__}: {erro}"
    )