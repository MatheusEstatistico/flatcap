# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
"""
A amostragem — o plano da amostra de um projeto, na pasta dela, com o relatório dela.

O projeto costuma começar com a amostragem e evoluir depois para a análise. O fluxo
começa sempre no `flatcap novo`, e a amostragem vem depois dele:

    flatcap novo 23 --sim          o projeto, como sempre: ficha, histórico, três pastas
    flatcap amostragem 23 --sim    cria a `4. Amostragem/` e o `desenho.yaml`, e para
      (preencher o desenho.yaml)
    flatcap amostragem 23 --sim    a conta, o `tamanho.csv` e o relatório da amostra

Segue o padrão da casa, decidir e escrever separados:

    plano = preparar_amostragem(raiz)   # lê o desenho.yaml, calcula, monta o documento
    executar_amostragem(plano)          # só escreve

E, como as análises, **não fala com o REDCap**. Recebe `Path`, não `Config`.

## Uma pasta própria, e não uma análise

Tudo da amostra mora em `4. Amostragem/`: a ficha (`desenho.yaml`), a conta
(`tamanho.csv`), o índice da rodada (`manifesto.json`), o relatório da amostra e as
versões antigas dele, em `4. Amostragem/Versões antigas/`. As pastas 1, 2 e 3 ficam para
a análise que vem depois.

Por isso a amostragem não está no `analises.REGISTRO`, na `ORDEM_PADRAO_DAS_ANALISES`
nem no `flatcap analisar`. O relatório das análises varre só `3. Análises/`, e nunca vê a
amostra; o relatório da amostra nunca vê as análises.

A pasta nasce no primeiro `flatcap amostragem`, e não no `novo`. O `novo` não tem como
saber se o pedido é de amostragem — o formulário do REDCap não tem essa opção —, o
projeto que nunca amostra não ganha uma pasta vazia, e o projeto que já existia ganha a
pasta do mesmo jeito, sem migração. A amostragem não cria projeto: sem a pasta do `novo`,
o `localizar_projeto` recusa, como em todo comando.

## A ficha é o `desenho.yaml`, preenchido à mão

A primeira rodada escreve o modelo comentado e para. O modelo já vem com o caso de todo
dia — 95% de confiança, margem de 5 pontos, proporção esperada de 50% —, e o pedido mais
comum, o do cliente que informa só o tamanho da população, é preencher a `populacao` e
rodar de novo.

O FlatCap escreve o modelo uma vez e, dali em diante, só lê. É a regra do
`dicionario.csv` aplicada a outro arquivo: o que está escrito ali é decisão sua. Quem o lê
é o `ficha.ler_yaml`, para que um YAML quebrado ganhe o diagnóstico da ficha.

As recusas saem todas de uma vez, como nas análises: descobrir o segundo engano depois de
corrigir o primeiro é o jeito mais lento de arrumar uma ficha.

## O espaço para os outros desenhos

O desenho é escolhido dentro da análise, como o teste é dentro da comparação: cada um é
uma entrada no `DESENHOS`, com as chaves dele no `desenho.yaml` e a conta dele. Hoje há
um, a aleatória simples; os previstos (`PREVISTOS`) recusam dizendo que ainda não
existem, e não que não são conhecidos. O sorteio de uma lista também tem o lugar dele no
registro, e nenhum desenho sorteia ainda.

## O relatório da amostra

Montado com as peças do relatório das análises: um `relatorio.Relatorio` com a seção do
tamanho, escrito pelo `documento.escrever`, com o mesmo modelo `.docx` e a mesma primeira
página — a finalidade e os objetivos do `projeto.yaml`. **Não recalcula nada**: a tabela
do documento é lida, pelo `relatorio.tabela_do_texto`, do mesmo texto que vai para o
`tamanho.csv`.

O texto de metodologia sobre a amostra feita tem o lugar dele, o `METODOLOGIA`, e ele
está vazio de propósito — a regra do `TEXTO_PADRAO` do relatório: nada de parágrafo de
mentira guardando o lugar.
"""

from __future__ import annotations

import difflib
import re
import sys
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from . import __version__
from .amostral import (
    TOLERANCIA,
    Tamanho,
    para_cima,
    tamanho_aas,
    tamanho_decidido,
    variancia_da_proporcao,
)
from .ficha import Ficha, FichaInvalidaError, escrever_atomico, ler_yaml, numero_escrito
from .ficha import ler as ler_ficha
from .manifesto import (
    ANALISE_AMOSTRAGEM,
    ARQUIVO_MANIFESTO,
    Artefato,
    ItemDoManifesto,
    Manifesto,
    ManifestoError,
    Tabela,
    texto_do_manifesto,
)
from .manifesto import ler as ler_manifesto
from .nomes import rotulo_do_projeto, sanitizar
from .projeto import (
    ARQUIVO_DESENHO,
    PASTA_AMOSTRAGEM,
    PASTA_ANTIGAS_DA_AMOSTRAGEM,
    anotar,
    pasta_da_amostragem,
)
from .relatorio import (
    Relatorio,
    Rodada,
    Secao,
    conferir_texto,
    localizar_template,
    montar_abertura,
    tabela_do_texto,
)

# O nome do único desenho de hoje, como se escreve no `desenho.yaml`.
DESENHO_AAS = "aas"

# Os desenhos que vêm depois, na ordem do `claude/amostragem-tipos.md`. Escrever um deles
# no `desenho.yaml` recusa dizendo que ainda não existe — e não que não é conhecido, que
# mandaria procurar um erro de digitação que não está lá.
PREVISTOS: tuple[str, ...] = (
    "sistematica",
    "estratificada",
    "conglomerados",
    "ppt",
    "dois_estagios",
)

# As chaves que todo desenho aceita. Cada desenho acrescenta as dele (`Desenho.chaves`).
CHAVES_COMUNS: tuple[str, ...] = (
    "desenho",
    "populacao",
    "confianca",
    "margem",
    "proporcao",
    "desvio",
    "perda",
    "n",
)

# As que fazem a conta. Com o `n` escrito à mão, elas ficam em branco.
CHAVES_DA_CONTA: tuple[str, ...] = ("confianca", "margem", "proporcao", "desvio")

# A margem de uma proporção que, escrita em pontos, parece uma fração: `0.05` é a margem de 5%
# escrita como fração, e é 0,05 ponto. Até 0,2 — a fração de uma margem de 20% —, a conta sai
# com aviso; acima disso, a leitura em fração daria uma margem que ninguém pede.
MARGEM_QUE_PARECE_FRACAO = 0.002

ARQUIVO_TAMANHO = "tamanho.csv"
ESPECIE_TAMANHO = "tamanho"
ROTULO_DO_TAMANHO = "Tamanho da amostra"

TITULO_DA_AMOSTRA = "Relatório de Amostragem"

# O prefixo do relatório da amostra, como o `Relatorio_` do relatório das análises. Os
# dois nunca se encontram: este mora em `4. Amostragem/`, e aquele na raiz do projeto.
PREFIXO_RELATORIO_DA_AMOSTRA = "Amostragem_"

# ─────────────────────────────────────────────────────────────────────────────
#  O TEXTO DE METODOLOGIA DE CADA DESENHO — é aqui que se escreve.
#
#  Uma linha da tupla, um parágrafo do documento. Ele entra na primeira página do
#  relatório da amostra, depois da finalidade e dos objetivos, e cada parágrafo pode
#  usar os campos da conta entre chaves:
#
#      {desenho} {populacao} {confianca} {z} {margem} {proporcao} {desvio}
#      {n0} {n} {perda} {n_final}
#
#  Os campos chegam escritos como na tabela (`95%`, `5 pontos percentuais`, `1200`), e
#  o que a conta não usou chega vazio — a média não tem `{proporcao}`, o tamanho
#  decidido à mão não tem `{z}`. Por isso o texto de cada desenho vai precisar de uma
#  frase por situação: proporção ou média, com ou sem N, com ou sem perda.
#
#  `()` é o estado de hoje: ainda não escrito. É a regra do `TEXTO_PADRAO` do
#  relatório — nada de parágrafo de mentira guardando o lugar: um `xxxxx` esquecido
#  aqui chega impresso na mão do cliente.
# ─────────────────────────────────────────────────────────────────────────────

METODOLOGIA: dict[str, tuple[str, ...]] = {
    DESENHO_AAS: (),
}

# O `desenho.yaml` que a primeira rodada escreve. Já vem com o caso de todo dia, para que
# o pedido mais comum — o cliente que informa só o tamanho da população — seja preencher a
# `populacao` e rodar de novo. Lido como está, ele é válido: dá a conta de população
# grande.
MODELO_DO_DESENHO = """\
# desenho.yaml — o plano da amostra deste projeto, escrito pelo `flatcap amostragem`.
#
# Este arquivo é seu: preencha à mão. O FlatCap lê o que está aqui e não o
# sobrescreve. Percentuais vão em % (95, e não 0.95), e a vírgula decimal
# vale (2,5). O caso mais comum é preencher só a `populacao` e rodar de novo.
#
#   desenho     aas — amostragem aleatória simples, sem reposição. O único,
#               por enquanto.
#   populacao   N, o tamanho da população que o cliente informou, sem ponto
#               de milhar (12000). Em branco, a conta é a de população
#               grande, sem correção.
#   confianca   o nível de confiança, em %.
#   margem      a margem de erro: em pontos percentuais, para proporção; na
#               unidade da variável, para média.
#   proporcao   a proporção esperada, em %. 50 quando não se sabe: é o valor
#               que dá o maior tamanho.
#   desvio      no lugar de `proporcao`, para estimar uma média: o
#               desvio-padrão esperado, de estudo anterior ou piloto.
#   perda       a perda esperada, em %. 0 quando não há.
#   n           o tamanho já decidido, no lugar da conta: com ele, deixe
#               `confianca`, `margem` e `proporcao` em branco.

desenho: aas
populacao:
confianca: 95
margem: 5
proporcao: 50
perda: 0
"""


# Erros


class AmostragemError(RuntimeError):
    """
    Falha da amostragem, já traduzida para o usuário.

    Erro próprio pela regra da casa: a CLI captura esta classe e transforma em painel.
    Qualquer outra exceção é bug de verdade e deve subir com o traceback inteiro.
    """


class DesenhoInvalidoError(AmostragemError):
    """
    O `desenho.yaml` tem o que não serve. A mensagem lista **todos** os problemas.
    """


class DesenhoExistenteError(AmostragemError):
    """
    O `desenho.yaml` apareceu entre a simulação e a execução, e o modelo não o
    sobrescreve: o arquivo é seu.
    """


# O que circula


@dataclass(frozen=True)
class Pedido:
    """
    O `desenho.yaml` lido, conferido e convertido.

    Os percentuais viram frações aqui (95 → 0,95), porque o `amostral.py` trabalha em
    frações. A margem só vira fração quando é de uma proporção; de uma média, ela é na
    unidade da variável e fica como veio. `escrito` é o arquivo como estava, para o
    manifesto guardar o que você escreveu, e não só o que o FlatCap entendeu; `texto` é o
    arquivo inteiro, comentários incluídos, para a cópia que acompanha a rodada quando
    ela for para as versões antigas.
    """

    desenho: str
    populacao: int | None = None
    confianca: float | None = None
    margem: float | None = None
    proporcao: float | None = None
    desvio: float | None = None
    perda: float = 0.0
    n: int | None = None
    escrito: dict[str, Any] | None = None
    texto: str = ""

    @property
    def estima(self) -> str:
        """`proporcao`, `media`, ou vazio quando o tamanho foi decidido à mão."""
        if self.n is not None:
            return ""
        return "proporcao" if self.proporcao is not None else "media"


@dataclass(frozen=True)
class Calculo:
    """
    O tamanho, e a tabela que o apresenta.

    `linhas` são os pares `parâmetro;valor` do `tamanho.csv`, na ordem da leitura: o
    desenho e a população, a precisão pedida, e os tamanhos até o da amostra, que é
    sempre a última linha. `notas` vão para o cabeçalho do `.csv` e para o manifesto, e
    não para o documento. `campos` são os mesmos valores escritos, para o texto de
    metodologia.
    """

    tamanho: Tamanho
    linhas: tuple[tuple[str, str], ...]
    notas: tuple[str, ...] = ()
    avisos: tuple[str, ...] = ()
    campos: dict[str, str] | None = None


@dataclass(frozen=True)
class Desenho:
    """
    Um desenho que a amostragem sabe calcular — e, um dia, sortear.

    O nome é o que se escreve em `desenho:`. As `chaves` são as do `desenho.yaml` que só
    ele aceita, além das `CHAVES_COMUNS`; vazio na aleatória simples. O `sortear` chega
    com o sorteio de uma lista, num passo seguinte, e até lá nenhum desenho sorteia.
    """

    nome: str
    titulo: str
    calcular: Callable[[Pedido], Calculo]
    chaves: frozenset[str] = frozenset()
    sortear: Callable[..., Any] | None = None


@dataclass(frozen=True)
class Amostragem:
    """A rodada inteira, decidida. É daqui que saem os arquivos e o terminal."""

    ficha: Ficha
    pedido: Pedido
    desenho: Desenho
    calculo: Calculo
    tabela: Tabela
    quando: datetime
    avisos: tuple[str, ...] = ()

    @property
    def raiz(self) -> Path:
        return self.ficha.raiz

    @property
    def tamanho(self) -> Tamanho:
        return self.calculo.tamanho


@dataclass(frozen=True)
class Arquivamento:
    """
    A rodada anterior, a caminho de `4. Amostragem/Versões antigas/`.

    Arquivo por arquivo, e não a pasta inteira como nas análises: aqui a rodada divide a
    pasta com o `desenho.yaml`, que é seu e fica onde está.

    Vai junto o `desenho.yaml` **de então** (`desenho`), para a pergunta "com que ficha
    saiu aquele relatório?" ter resposta exata. Ele vem do manifesto daquela rodada, que
    guarda o texto que ela leu — e não do arquivo que está na pasta, que a esta altura
    você já mudou: copiar o de agora poria a ficha nova ao lado do relatório velho. Sem
    um manifesto legível, a rodada vai sem ele, e não com o errado.
    """

    destino: Path
    arquivos: tuple[Path, ...]
    desenho: str | None = None


@dataclass(frozen=True)
class PlanoAmostragem:
    """
    Tudo o que a amostragem faria, decidido e ainda não escrito.

    Dois casos, e o `amostragem` diz qual: `None` é a primeira rodada, que só escreve o
    modelo do `desenho.yaml`; preenchido, é a rodada que calcula e escreve o relatório.
    """

    raiz: Path
    ficha: Ficha
    pasta: Path
    quando: datetime
    amostragem: Amostragem | None = None
    criar_pasta: bool = False
    modelo: str = MODELO_DO_DESENHO
    manifesto: Manifesto | None = None
    texto_manifesto: str = ""
    relatorio: Relatorio | None = None
    destino: Path | None = None
    template: Path | None = None
    arquivamento: Arquivamento | None = None

    @property
    def so_o_modelo(self) -> bool:
        """A primeira rodada: o `desenho.yaml` ainda não existe."""
        return self.amostragem is None

    @property
    def desenho_yaml(self) -> Path:
        return self.pasta / ARQUIVO_DESENHO

    @property
    def arquivos(self) -> tuple[str, ...]:
        if self.amostragem is None or self.destino is None:
            return (ARQUIVO_DESENHO,)
        return (ARQUIVO_TAMANHO, self.destino.name, ARQUIVO_MANIFESTO)


@dataclass(frozen=True)
class ResultadoAmostragem:
    """O que a execução de fato escreveu."""

    criados: tuple[Path, ...] = ()
    arquivado: Path | None = None
    avisos: tuple[str, ...] = ()


# Casos de uso


def preparar_amostragem(
    raiz: Path,
    titulo: str = TITULO_DA_AMOSTRA,
    template: Path | str | None = None,
    agora: datetime | None = None,
) -> PlanoAmostragem:
    """
    Lê o `desenho.yaml`, faz a conta e monta o relatório da amostra. Não escreve nada.

    Sem o `desenho.yaml`, o plano é o da primeira rodada: criar a `4. Amostragem/`, se
    ainda não existir, e escrever o modelo para preencher.

    Args:
        raiz: a pasta do projeto (a que tem o `projeto.yaml`).
        titulo: o título na primeira linha do relatório da amostra.
        template: um `.docx` de onde herdar estilos; sem ele, os degraus de sempre — o
            `template.docx` do projeto, do cliente e do `FLATCAP_ROOT`.
        agora: relógio injetável, como em todo `preparar*`.

    Raises:
        FichaError (a ficha do projeto), `DesenhoInvalidoError` (o `desenho.yaml`, com
        todos os problemas de uma vez) e `ModeloAusenteError` (o `template` indicado não
        existe).
    """
    raiz = Path(raiz)
    quando = agora or datetime.now()
    ficha = ler_ficha(raiz)
    pasta = pasta_da_amostragem(raiz)

    if not (pasta / ARQUIVO_DESENHO).is_file():
        return PlanoAmostragem(
            raiz=raiz,
            ficha=ficha,
            pasta=pasta,
            quando=quando,
            criar_pasta=not pasta.is_dir(),
        )

    pedido, desenho = ler_desenho(pasta / ARQUIVO_DESENHO)
    calculo = desenho.calcular(pedido)
    tabela = montar_tabela(desenho, calculo)

    anterior = _rodada_vigente(pasta)
    avisos = list(calculo.avisos)
    mudanca = _mudanca(anterior, calculo.tamanho)
    if mudanca:
        avisos.append(mudanca)

    amostragem = Amostragem(
        ficha=ficha,
        pedido=pedido,
        desenho=desenho,
        calculo=calculo,
        tabela=tabela,
        quando=quando,
        avisos=tuple(avisos),
    )
    manifesto = montar_manifesto(amostragem)

    return PlanoAmostragem(
        raiz=raiz,
        ficha=ficha,
        pasta=pasta,
        quando=quando,
        amostragem=amostragem,
        manifesto=manifesto,
        texto_manifesto=texto_do_manifesto(manifesto),
        relatorio=montar_relatorio(amostragem, manifesto, pasta, titulo),
        destino=pasta / nome_do_relatorio_da_amostra(ficha.matricula, quando.date()),
        template=localizar_template(raiz, template),
        arquivamento=_arquivamento(pasta, quando, anterior),
    )


def executar_amostragem(plano: PlanoAmostragem) -> ResultadoAmostragem:
    """
    Escreve o plano no disco. Não decide mais nada.

    Na primeira rodada, a pasta e o modelo. Nas outras, a ordem das análises: arquiva a
    rodada anterior, escreve a tabela, o relatório da amostra e, por último, o
    `manifesto.json` — o recibo vem depois do que ele descreve.

    Cada etapa registra como voltar atrás. Uma falha no meio desfaz o que já foi feito,
    inclusive devolvendo a rodada anterior ao lugar, e a exceção continua subindo
    inteira. O `python-docx` entra aqui dentro, e não no topo do módulo, pelo motivo do
    `executar_relatorio`: a simulação não escreve documento nenhum e não deve pagar por
    ele.
    """
    if plano.amostragem is None:
        return _executar_modelo(plano)

    from .documento import escrever

    criados: list[Path] = []
    avisos: list[str] = []
    desfazer: list[Callable[[], Any]] = []
    arquivado: Path | None = None

    try:
        if plano.arquivamento is not None:
            arquivado = _arquivar(plano.arquivamento, desfazer)

        tabela = plano.amostragem.tabela
        caminho = plano.pasta / tabela.nome
        escrever_atomico(caminho, tabela.texto())
        criados.append(caminho)
        desfazer.append(lambda p=caminho: p.unlink(missing_ok=True))

        if plano.relatorio is not None and plano.destino is not None:
            escrever(plano.relatorio, plano.destino, plano.template)
            criados.append(plano.destino)
            desfazer.append(lambda p=plano.destino: p.unlink(missing_ok=True))

        caminho = plano.pasta / ARQUIVO_MANIFESTO
        escrever_atomico(caminho, plano.texto_manifesto)
        criados.append(caminho)
        desfazer.append(lambda p=caminho: p.unlink(missing_ok=True))

        try:
            anotar(plano.raiz, _acao_do_historico(plano), plano.quando)
        except OSError as erro:
            avisos.append(
                "A amostragem foi escrita, mas não consegui escrever no historico.md: "
                f"{erro}"
            )

    except Exception:
        _desfazer(desfazer, avisos)
        raise

    return ResultadoAmostragem(
        criados=tuple(criados), arquivado=arquivado, avisos=tuple(avisos)
    )


def _executar_modelo(plano: PlanoAmostragem) -> ResultadoAmostragem:
    """
    A primeira rodada: a pasta, se faltar, e o modelo do `desenho.yaml`.

    O modelo nunca escreve por cima de um `desenho.yaml`, nem do que apareceu entre a
    simulação e a execução: o arquivo é seu.
    """
    criados: list[Path] = []
    avisos: list[str] = []
    desfazer: list[Callable[[], Any]] = []

    try:
        if not plano.pasta.is_dir():
            plano.pasta.mkdir()
            criados.append(plano.pasta)
            desfazer.append(lambda p=plano.pasta: p.rmdir())

        caminho = plano.desenho_yaml
        if caminho.exists():
            raise DesenhoExistenteError(
                f"O {ARQUIVO_DESENHO} apareceu em {PASTA_AMOSTRAGEM}/ depois da "
                "simulação, e o modelo não escreve por cima dele.\n"
                "Rode o comando de novo: agora ele vai ler o que está lá."
            )
        escrever_atomico(caminho, plano.modelo)
        criados.append(caminho)
        desfazer.append(lambda p=caminho: p.unlink(missing_ok=True))

        try:
            anotar(plano.raiz, _acao_do_historico(plano), plano.quando)
        except OSError as erro:
            avisos.append(
                f"O {ARQUIVO_DESENHO} foi escrito, mas não consegui escrever no "
                f"historico.md: {erro}"
            )

    except Exception:
        _desfazer(desfazer, avisos)
        raise

    return ResultadoAmostragem(criados=tuple(criados), avisos=tuple(avisos))


def _arquivar(arquivamento: Arquivamento, desfazer: list[Callable[[], Any]]) -> Path:
    """
    Move a rodada anterior para `Versões antigas/`, com o `desenho.yaml` de então.

    O `rmdir` de cada pasta criada aqui entra no desfazer **antes** dos arquivos, e o
    desfazer roda ao contrário: os arquivos voltam primeiro, e a pasta sai vazia, que é
    a única forma de ela sair.
    """
    destino = arquivamento.destino

    antigas = destino.parent
    if not antigas.is_dir():
        antigas.mkdir()
        desfazer.append(lambda p=antigas: p.rmdir())
    destino.mkdir()
    desfazer.append(lambda p=destino: p.rmdir())

    for arquivo in arquivamento.arquivos:
        para = destino / arquivo.name
        arquivo.rename(para)
        desfazer.append(lambda de=arquivo, para=para: para.rename(de))

    if arquivamento.desenho is not None:
        copia = destino / ARQUIVO_DESENHO
        escrever_atomico(copia, arquivamento.desenho)
        desfazer.append(lambda p=copia: p.unlink(missing_ok=True))
    return destino


def _desfazer(desfazer: Sequence[Callable[[], Any]], avisos: list[str]) -> None:
    for passo in reversed(desfazer):
        try:
            passo()
        except OSError:
            avisos.append(
                f"Falhei ao desfazer uma etapa. Confira {PASTA_AMOSTRAGEM}/ e "
                f"{PASTA_AMOSTRAGEM}/{PASTA_ANTIGAS_DA_AMOSTRAGEM}/ antes de rodar de novo."
            )


# O desenho.yaml


def ler_desenho(caminho: Path) -> tuple[Pedido, Desenho]:
    """
    Lê e confere o `desenho.yaml`. Recusa listando **todos** os problemas de uma vez.

    A leitura é tolerante onde o engano é inofensivo — `AAS` ou `Aleatória simples`
    no desenho, `2,5` com vírgula na margem — e estrita onde ele mudaria o número em
    silêncio: o `12.000` que no YAML é doze, a confiança escrita como fração, a
    proporção que a margem não cabe.

    Raises:
        DesenhoInvalidoError: com todos os problemas — e também quando o arquivo não é
            um YAML válido, com o diagnóstico da ficha.
    """
    caminho = Path(caminho)
    try:
        bruto = ler_yaml(caminho)
    except FichaInvalidaError as erro:
        raise DesenhoInvalidoError(str(erro)) from erro

    if bruto is None:
        bruto = {}
    if not isinstance(bruto, dict):
        raise DesenhoInvalidoError(
            f"O {ARQUIVO_DESENHO} deveria ser uma lista de chaves — `desenho: aas`, "
            "`populacao: 1200` —, uma por linha, e não é.\n"
            "Apague o arquivo e rode o comando de novo para receber o modelo."
        )

    problemas: list[str] = []
    desenho = _desenho_escrito(bruto.get("desenho"), problemas)
    _chaves_desconhecidas(bruto, desenho, problemas)

    populacao = _inteiro(bruto, "populacao", problemas)
    n = _inteiro(bruto, "n", problemas)
    confianca = _numero(bruto, "confianca", problemas)
    margem = _numero(bruto, "margem", problemas)
    proporcao = _numero(bruto, "proporcao", problemas)
    desvio = _numero(bruto, "desvio", problemas)
    perda = _numero(bruto, "perda", problemas)

    if perda is not None and not 0 <= perda < 100:
        problemas.append(
            f"`perda: {_texto(bruto['perda'])}` — a perda é um percentual de 0 a 100, "
            "sem o 100: 10 para dez por cento"
        )

    if n is not None:
        _conferir_n(bruto, n, populacao, problemas)
    else:
        _conferir_conta(bruto, confianca, margem, proporcao, desvio, problemas)

    # Sem desenho, `problemas` já tem a frase dele; o `is None` é para quem lê o tipo.
    if problemas or desenho is None:
        raise DesenhoInvalidoError(
            f"O {ARQUIVO_DESENHO} de {PASTA_AMOSTRAGEM}/ tem {len(problemas)} "
            "problema(s). Nada foi calculado.\n\n"
            + "\n".join(f"  — {problema}" for problema in problemas)
            + "\n\nCada chave está explicada no comentário do topo do arquivo."
        )

    em_fracao = proporcao is not None
    pedido = Pedido(
        desenho=desenho.nome,
        populacao=populacao,
        confianca=None if confianca is None else confianca / 100,
        margem=None if margem is None else (margem / 100 if em_fracao else margem),
        proporcao=None if proporcao is None else proporcao / 100,
        desvio=desvio,
        perda=0.0 if perda is None else perda / 100,
        n=n,
        escrito={chave: _simples(valor) for chave, valor in bruto.items()},
        # Já se sabe que é UTF-8: o `ler_yaml` acabou de ler o mesmo arquivo.
        texto=caminho.read_text(encoding="utf-8"),
    )
    return pedido, desenho


def _desenho_escrito(valor: Any, problemas: list[str]) -> Desenho | None:
    """
    O desenho pelo nome, sem caixa nem acento: `AAS`, `aas` e `Aleatória simples` são o
    mesmo. Previsto e ainda não feito recusa dizendo isso.
    """
    existentes = ", ".join(f"`{nome}`" for nome in DESENHOS)
    if _vazio(valor):
        problemas.append(
            f"falta o `desenho:` — escreva `desenho: aas`. Os que existem: {existentes}"
        )
        return None

    chave = _chave(str(valor))
    chave = _APELIDOS.get(chave, chave)
    if chave in DESENHOS:
        return DESENHOS[chave]
    if chave in PREVISTOS:
        problemas.append(
            f"`desenho: {_texto(valor)}` ainda não está no FlatCap — por enquanto, só "
            f"{existentes}"
        )
        return None

    parecidos = difflib.get_close_matches(chave, [*DESENHOS, *PREVISTOS], n=1, cutoff=0.6)
    dica = f" — você quis dizer `{parecidos[0]}`?" if parecidos else ""
    problemas.append(
        f"`desenho: {_texto(valor)}` não é um desenho do FlatCap{dica} Os que existem: "
        f"{existentes}"
    )
    return None


def _chaves_desconhecidas(
    bruto: dict[str, Any], desenho: Desenho | None, problemas: list[str]
) -> None:
    validas = set(CHAVES_COMUNS) | set(desenho.chaves if desenho else ())
    for chave in bruto:
        if chave in validas:
            continue
        parecidas = difflib.get_close_matches(
            _chave(chave), sorted(validas), n=1, cutoff=0.6
        )
        if parecidas:
            problemas.append(
                f"a chave `{chave}:` não existe — você quis dizer `{parecidas[0]}:`? "
                "(sem acento e em minúsculas)"
            )
        else:
            problemas.append(
                f"a chave `{chave}:` não existe. As que valem: "
                + ", ".join(f"`{nome}`" for nome in sorted(validas))
            )


def _conferir_n(
    bruto: dict[str, Any], n: int, populacao: int | None, problemas: list[str]
) -> None:
    """Com o tamanho escrito à mão, a conta fica em branco, e o `n` cabe na população."""
    escritas = [chave for chave in CHAVES_DA_CONTA if not _vazio(bruto.get(chave))]
    if escritas:
        problemas.append(
            "com o `n` escrito, a conta não se faz — deixe em branco "
            + _em_texto([f"`{chave}`" for chave in escritas])
            + ", ou apague o `n` para o FlatCap calcular"
        )
    if populacao is not None and n > populacao:
        problemas.append(f"`n: {n}` passa da população, `populacao: {populacao}`")


def _conferir_conta(
    bruto: dict[str, Any],
    confianca: float | None,
    margem: float | None,
    proporcao: float | None,
    desvio: float | None,
    problemas: list[str],
) -> None:
    """A precisão pedida: confiança, margem, e a proporção ou o desvio — um dos dois."""
    if confianca is None:
        if _vazio(bruto.get("confianca")):
            problemas.append("falta a `confianca:` — o nível de confiança, em %: 95")
    elif 0 < confianca < 1:
        problemas.append(
            f"`confianca: {_texto(bruto['confianca'])}` — a confiança vai em %: "
            f"{_formatar(confianca * 100)}, e não {_texto(bruto['confianca'])}"
        )
    elif not confianca < 100:
        problemas.append(
            f"`confianca: {_texto(bruto['confianca'])}` — a confiança fica abaixo de "
            "100%: 90, 95 ou 99"
        )
    elif confianca <= 0:
        problemas.append(
            f"`confianca: {_texto(bruto['confianca'])}` — a confiança fica entre 50 e "
            "100%: 90, 95 ou 99"
        )
    elif confianca < 50:
        # O α escrito no lugar da confiança: `confianca: 5` querendo 95% daria z = 0,06 e
        # uma amostra de uma unidade, sem erro nenhum.
        problemas.append(
            f"`confianca: {_texto(bruto['confianca'])}` — é o nível de confiança, e não o "
            f"α: {_formatar(100 - confianca)} para um α de {_texto(bruto['confianca'])}%"
        )

    if proporcao is not None and desvio is not None:
        problemas.append(
            "`proporcao` e `desvio` juntos — a conta é de uma proporção ou de uma média: "
            "deixe só um dos dois"
        )
    elif proporcao is None and desvio is None:
        if _vazio(bruto.get("proporcao")) and _vazio(bruto.get("desvio")):
            problemas.append(
                "falta a `proporcao:` (a esperada, em %: 50 quando não se sabe) — ou o "
                "`desvio:`, para estimar uma média"
            )

    if proporcao is not None and not 0 < proporcao < 100:
        problemas.append(
            f"`proporcao: {_texto(bruto['proporcao'])}` — a proporção esperada fica "
            "entre 0 e 100%, sem as pontas"
        )
    if desvio is not None and desvio <= 0:
        problemas.append(f"`desvio: {_texto(bruto['desvio'])}` — o desvio-padrão é positivo")

    if margem is None:
        if _vazio(bruto.get("margem")):
            problemas.append("falta a `margem:` — a margem de erro: 5 para cinco pontos")
    elif margem <= 0:
        problemas.append(f"`margem: {_texto(bruto['margem'])}` — a margem é positiva")
    elif proporcao is not None and desvio is None and 0 < proporcao < 100:
        # A margem é em pontos percentuais. Maior que a proporção, o intervalo passaria
        # de 0% — e é assim que o `proporcao: 0.5` escrito querendo 50% se denuncia,
        # em vez de dar n = 8 sem erro nenhum.
        if margem >= proporcao or margem >= 100 - proporcao:
            problemas.append(
                f"`margem: {_texto(bruto['margem'])}` não cabe em "
                f"`proporcao: {_texto(bruto['proporcao'])}` — com ela, o intervalo "
                "passaria de 0% ou de 100%. A proporção vai em %: 50 é cinquenta por "
                "cento, e 0.5 é meio por cento"
            )


# A leitura dos valores


# Os nomes por extenso que querem dizer um desenho que existe.
_APELIDOS: dict[str, str] = {
    "aleatoria_simples": DESENHO_AAS,
    "amostragem_aleatoria_simples": DESENHO_AAS,
}

_SO_ALGARISMOS = re.compile(r"[0-9]+")


def _chave(texto: str) -> str:
    """`Aleatória Simples` → `aleatoria_simples`: sem acento, sem caixa, com sublinhado."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[\s\-]+", "_", sem_acento.strip().lower())


def _vazio(valor: Any) -> bool:
    return valor is None or (isinstance(valor, str) and not valor.strip())


def _numero(bruto: dict[str, Any], chave: str, problemas: list[str]) -> float | None:
    """O número da chave, ou `None` quando ela falta ou está em branco."""
    valor = bruto.get(chave)
    if _vazio(valor):
        return None
    numero = numero_escrito(valor)
    if numero is None:
        problemas.append(
            f"`{chave}: {_texto(valor)}` não é um número — escreva só o número, com "
            "vírgula ou ponto decimal e sem separador de milhar"
        )
    return numero


def _inteiro(bruto: dict[str, Any], chave: str, problemas: list[str]) -> int | None:
    """
    Um inteiro, escrito como inteiro.

    Estrito de propósito. No YAML o ponto é a casa decimal, e o `12.000` que em português
    é doze mil chega como doze — aceitá-lo daria uma população de 12 sem erro nenhum.
    """
    valor = bruto.get(chave)
    if _vazio(valor):
        return None
    if isinstance(valor, bool) or not (
        isinstance(valor, int)
        or (isinstance(valor, str) and _SO_ALGARISMOS.fullmatch(valor.strip()))
    ):
        problemas.append(
            f"`{chave}: {_texto(valor)}` precisa ser um número inteiro, sem ponto nem "
            "vírgula — 12000, e não 12.000: no YAML, o ponto é a casa decimal"
        )
        return None
    inteiro = int(str(valor).strip()) if isinstance(valor, str) else int(valor)
    if inteiro < 1:
        problemas.append(f"`{chave}: {inteiro}` precisa ser pelo menos 1")
        return None
    return inteiro


def _texto(valor: Any) -> str:
    """O valor como ele aparece na mensagem: o que está no arquivo."""
    return str(valor).strip()


def _simples(valor: Any) -> Any:
    """O valor escrito, para o manifesto: o escalar do YAML como escalar do Python."""
    if valor is None or isinstance(valor, bool):
        return valor
    if isinstance(valor, int):
        return int(valor)
    if isinstance(valor, float):
        return float(valor)
    return str(valor)


def _em_texto(nomes: Sequence[str]) -> str:
    if len(nomes) <= 1:
        return "".join(nomes)
    return ", ".join(nomes[:-1]) + f" e {nomes[-1]}"


# A conta da aleatória simples


def calcular_aas(pedido: Pedido) -> Calculo:
    """
    O tamanho da aleatória simples, sem reposição, e a tabela dele.

    Com o `n` escrito, não há conta: o tamanho é o escrito, com a perda somada.
    """
    if pedido.n is not None:
        tamanho = tamanho_decidido(pedido.n, populacao=pedido.populacao, perda=pedido.perda)
    else:
        # O `ler_desenho` garante os três; um `Pedido` montado à mão sem eles é bug.
        if pedido.confianca is None or pedido.margem is None:
            raise ValueError("a conta precisa da confiança e da margem")
        if pedido.proporcao is not None:
            variancia = variancia_da_proporcao(pedido.proporcao)
        elif pedido.desvio is not None:
            variancia = pedido.desvio**2
        else:
            raise ValueError("a conta precisa da proporção ou do desvio")
        tamanho = tamanho_aas(
            confianca=pedido.confianca,
            margem=pedido.margem,
            variancia=variancia,
            populacao=pedido.populacao,
            perda=pedido.perda,
        )

    campos = _campos(pedido, tamanho)
    avisos: list[str] = []
    if (
        pedido.estima == "proporcao"
        and pedido.margem is not None
        and pedido.margem <= MARGEM_QUE_PARECE_FRACAO + TOLERANCIA
    ):
        # Aviso, e não recusa: uma margem pequena existe, nas pesquisas grandes. Mas é
        # também como chega a margem escrita em fração — `0.05` querendo 5% —, que passa
        # por todas as conferências e dá uma amostra cem vezes maior.
        avisos.append(
            f"A margem de erro é de {campos['margem']}. Ela vai em pontos percentuais, e "
            f"não em fração: se a intenção era {_formatar(pedido.margem * 10000)}%, escreva "
            f"`margem: {_formatar(pedido.margem * 10000)}`."
        )
    if tamanho.censo:
        avisos.append(
            f"A amostra é a população inteira — as {tamanho.populacao} unidades. Com "
            "esta população e esta precisão, sortear não economiza ninguém: é um censo."
        )

    return Calculo(
        tamanho=tamanho,
        linhas=_linhas(pedido, tamanho, campos),
        notas=_notas(pedido, tamanho),
        avisos=tuple(avisos),
        campos=campos,
    )


def _campos(pedido: Pedido, tamanho: Tamanho) -> dict[str, str]:
    """Os valores escritos como na tabela, para a tabela e para o texto de metodologia."""
    media = pedido.estima == "media"
    return {
        "desenho": DESENHOS[pedido.desenho].titulo,
        "populacao": "" if pedido.populacao is None else str(pedido.populacao),
        "confianca": "" if pedido.confianca is None else _percentual(pedido.confianca),
        "z": "" if tamanho.z is None else f"{tamanho.z:.2f}".replace(".", ","),
        "margem": (
            ""
            if pedido.margem is None
            else (
                f"{_formatar(pedido.margem)}, na unidade da variável"
                if media
                else _pontos(pedido.margem * 100)
            )
        ),
        "proporcao": "" if pedido.proporcao is None else _percentual(pedido.proporcao),
        "desvio": "" if pedido.desvio is None else _formatar(pedido.desvio),
        "n0": "" if tamanho.n0 is None else str(para_cima(tamanho.n0)),
        "n": str(tamanho.n),
        "perda": _percentual(tamanho.perda) if tamanho.perda else "",
        "n_final": str(tamanho.n_final),
    }


def _linhas(
    pedido: Pedido, tamanho: Tamanho, campos: dict[str, str]
) -> tuple[tuple[str, str], ...]:
    """
    As linhas da tabela, do que se pediu ao que saiu. A última é sempre o tamanho da
    amostra, que é a resposta — quem procura o número procura no fim.
    """
    linhas: list[tuple[str, str]] = [("Desenho", campos["desenho"])]
    linhas.append(
        (
            "População (N)",
            campos["populacao"]
            or "não informada — a conta é a de população grande, sem correção",
        )
    )

    if tamanho.decidido:
        if tamanho.perda:
            linhas.append(("Tamanho decidido (n)", campos["n"]))
    else:
        linhas.append(("Nível de confiança", f"{campos['confianca']} (z = {campos['z']})"))
        linhas.append(("Margem de erro", campos["margem"]))
        if pedido.estima == "proporcao":
            linhas.append(("Proporção esperada", campos["proporcao"]))
        else:
            linhas.append(("Desvio-padrão esperado", campos["desvio"]))

        if pedido.populacao is not None:
            linhas.append(("Tamanho sem a correção (n₀)", campos["n0"]))
            if tamanho.perda:
                linhas.append(("Tamanho com a correção (n)", campos["n"]))
        elif tamanho.perda:
            linhas.append(("Tamanho para população grande (n₀)", campos["n"]))

    if tamanho.perda:
        linhas.append(("Perda esperada", campos["perda"]))

    final = campos["n_final"]
    if tamanho.censo:
        final = f"{tamanho.n_final} — a população inteira (censo)"
    linhas.append((ROTULO_DO_TAMANHO, final))
    return tuple(linhas)


def _notas(pedido: Pedido, tamanho: Tamanho) -> tuple[str, ...]:
    """O como da conta, para quem abrir o `.csv` sozinho. Não vai para o documento."""
    titulo = DESENHOS[pedido.desenho].titulo
    if tamanho.decidido:
        notas = [
            f"desenho: amostragem {titulo}",
            f"o tamanho foi decidido à mão, no {ARQUIVO_DESENHO}; não há conta",
        ]
    else:
        v = "p(1−p)" if pedido.estima == "proporcao" else "σ²"
        notas = [
            f"desenho: amostragem {titulo}",
            f"fórmula: n₀ = z²·{v} / e²; com a população N, "
            f"n = N·z²·{v} / [(N − 1)·e² + z²·{v}] — o n₀ corrigido, na forma do OpenEpi",
            "z: o quantil bilateral da normal, o qnorm(1 − α/2) do R",
        ]
    if tamanho.perda:
        notas.append("perda: tamanho da amostra = ⌈n / (1 − perda)⌉, no máximo N")
    notas.append(
        "arredondamento: sempre para cima, em cada passo — o das calculadoras, como o "
        "OpenEpi; a tabela de Krejcie e Morgan arredonda para o mais próximo"
    )
    return tuple(notas)


def _formatar(valor: float) -> str:
    """
    Um número como se escreve numa tabela em português: `95`, `2,5`, `0,001`.

    Sem o `banco.texto_de_numero` de propósito: o `banco.py` traz o `pandas`, e a
    amostragem da v1 não abre banco nenhum.
    """
    texto = f"{valor:.6f}".rstrip("0").rstrip(".")
    return "0" if texto in ("", "-0") else texto.replace(".", ",")


def _percentual(fracao: float) -> str:
    return f"{_formatar(fracao * 100)}%"


def _pontos(valor: float) -> str:
    """`5 pontos percentuais`, e `1,5 ponto percentual`: abaixo de dois, no singular."""
    singular = abs(valor) < 2 - TOLERANCIA
    return f"{_formatar(valor)} {'ponto percentual' if singular else 'pontos percentuais'}"


# O registro. Depois das funções, que ele nomeia.

DESENHOS: dict[str, Desenho] = {
    DESENHO_AAS: Desenho(
        nome=DESENHO_AAS,
        titulo="aleatória simples, sem reposição",
        calcular=calcular_aas,
    ),
}


# A tabela, o manifesto e o relatório


def montar_tabela(desenho: Desenho, calculo: Calculo) -> Tabela:
    """O `tamanho.csv`. Duas colunas, e a última linha é a resposta."""
    return Tabela(
        nome=ARQUIVO_TAMANHO,
        especie=ESPECIE_TAMANHO,
        variavel="",
        titulo=ROTULO_DO_TAMANHO,
        colunas=("parâmetro", "valor"),
        linhas=calculo.linhas,
        notas=calculo.notas,
    )


def montar_manifesto(amostragem: Amostragem) -> Manifesto:
    """
    O índice da rodada, no formato do das análises.

    `banco` e `dicionario` vazios: a amostragem da v1 não abre banco nem obedece a
    dicionário. O item tem `variavel` vazia e `colunas` vazias pelo mesmo motivo. Em
    `detalhes`, os números sem arredondar, os valores como foram escritos (`escrito`) e
    o `desenho.yaml` inteiro (`desenho_yaml`) — de onde sai a cópia que acompanha esta
    rodada quando ela for para as versões antigas.
    """
    ficha = amostragem.ficha
    pedido = amostragem.pedido
    tamanho = amostragem.tamanho

    item = ItemDoManifesto(
        variavel="",
        slug=ESPECIE_TAMANHO,
        rotulo=ROTULO_DO_TAMANHO,
        tipo=ANALISE_AMOSTRAGEM,
        n=tamanho.populacao or 0,
        faltantes=0,
        artefatos=(
            Artefato(
                arquivo=ARQUIVO_TAMANHO,
                especie=ESPECIE_TAMANHO,
                formato="csv",
                titulo=ROTULO_DO_TAMANHO,
            ),
        ),
        detalhes={
            "desenho": pedido.desenho,
            "estima": pedido.estima or None,
            "populacao": tamanho.populacao,
            "confianca": pedido.confianca,
            "z": tamanho.z,
            "margem": pedido.margem,
            "proporcao": pedido.proporcao,
            "desvio": pedido.desvio,
            "n0": tamanho.n0,
            "n_corrigido": tamanho.n_corrigido,
            "n": tamanho.n,
            "perda": tamanho.perda,
            "n_final": tamanho.n_final,
            "censo": tamanho.censo,
            "decidido": tamanho.decidido,
            "escrito": pedido.escrito or {},
            "desenho_yaml": pedido.texto,
        },
        avisos=amostragem.avisos,
    )

    return Manifesto(
        analise=ANALISE_AMOSTRAGEM,
        flatcap=__version__,
        gerado_em=amostragem.quando,
        projeto={
            "pasta": rotulo_do_projeto(ficha.raiz),
            "cliente": ficha.raiz.parent.name,
            "record_id": ficha.record_id,
            "matricula": ficha.matricula,
            "nome": ficha.nome,
            "tipo": ficha.tipo,
            "status": ficha.status,
        },
        banco={},
        dicionario={},
        ambiente={
            "python": ".".join(str(parte) for parte in sys.version_info[:3]),
            "flatcap": __version__,
        },
        regras={
            "ficha": f"{PASTA_AMOSTRAGEM}/{ARQUIVO_DESENHO}",
            "desenho": amostragem.desenho.titulo,
            "formula": "n = N·z²·V / [(N − 1)·e² + z²·V]; sem N, n₀ = z²·V / e²",
            "arredondamento": "para cima, em cada passo",
            "z": "statistics.NormalDist — o AS241, o mesmo do qnorm do R",
        },
        itens=(item,),
        avisos=amostragem.avisos,
    )


def montar_relatorio(
    amostragem: Amostragem, manifesto: Manifesto, pasta: Path, titulo: str
) -> Relatorio:
    """
    O relatório da amostra, com as peças do relatório das análises.

    A primeira página é a dele — a finalidade e os objetivos da ficha, com o marcador e
    o alerta quando estão em branco —, e o texto de metodologia entra depois, quando
    existir. A tabela é lida do texto do `tamanho.csv` pelo `tabela_do_texto`, a mesma
    função que lê o arquivo do disco.
    """
    ficha = amostragem.ficha
    tabela = amostragem.tabela
    lida = tabela_do_texto(tabela.texto(), tabela.especie, tabela.titulo, pasta / tabela.nome)
    secao = Secao(
        variavel="",
        rotulo=ROTULO_DO_TAMANHO,
        tipo=ANALISE_AMOSTRAGEM,
        n=amostragem.tamanho.populacao or 0,
        faltantes=0,
        tabelas=(lida,),
    )
    alerta = conferir_texto(ficha)
    return Relatorio(
        ficha=ficha,
        manifesto=manifesto,
        titulo=titulo,
        secoes=(secao,),
        texto=montar_abertura(ficha) + texto_de_metodologia(amostragem),
        alertas=(alerta,) if alerta is not None else (),
        quando=amostragem.quando,
        rodadas=(
            Rodada(
                analise=ANALISE_AMOSTRAGEM, pasta=pasta, manifesto=manifesto, secoes=(secao,)
            ),
        ),
    )


def texto_de_metodologia(amostragem: Amostragem) -> tuple[str, ...]:
    """Os parágrafos do `METODOLOGIA` do desenho, com os campos da conta preenchidos."""
    campos = amostragem.calculo.campos or {}
    return tuple(
        paragrafo.format(**campos)
        for paragrafo in METODOLOGIA.get(amostragem.desenho.nome, ())
    )


def nome_do_relatorio_da_amostra(matricula: str, quando: date) -> str:
    """
    `Amostragem_123465_2026-10-26.docx`, como o `relatorio.nome_do_relatorio`.

    A matrícula passa pela mesma limpeza dos nomes de pasta: ela é digitada por outra
    pessoa, em outro sistema, e o que vem de fora não monta caminho.
    """
    limpa = Path(sanitizar(str(matricula)) or "sem_matricula").name
    return f"{PREFIXO_RELATORIO_DA_AMOSTRA}{limpa}_{quando:%Y-%m-%d}.docx"


def resumo_do_tamanho(tamanho: Tamanho) -> str:
    """`325 de 1200`, `385` ou `120 de 120 — a população inteira`: a linha do terminal."""
    if tamanho.populacao is None:
        return str(tamanho.n_final)
    texto = f"{tamanho.n_final} de {tamanho.populacao}"
    return f"{texto} — a população inteira" if tamanho.censo else texto


# A rodada anterior


def _arquivamento(
    pasta: Path, quando: datetime, anterior: Manifesto | None
) -> Arquivamento | None:
    """
    O que a rodada vigente escreveu, e para onde vai quando ela for refeita.

    Os nomes que esta versão escreve — a tabela, o manifesto e os relatórios da amostra
    —, e só eles: o resto da pasta é seu. Pelos nomes, e não pelo manifesto da rodada,
    porque ler um manifesto que pode ser de outra versão só para saber o que mover é
    trocar uma regra simples por uma que falha. Do manifesto vem só o `desenho.yaml` de
    então, e a falta dele não impede o arquivamento.
    """
    vigentes = [
        pasta / nome for nome in (ARQUIVO_TAMANHO, ARQUIVO_MANIFESTO) if (pasta / nome).is_file()
    ]
    vigentes += sorted(
        arquivo
        for arquivo in pasta.glob(f"{PREFIXO_RELATORIO_DA_AMOSTRA}*.docx")
        if arquivo.is_file()
    )
    if not vigentes:
        return None

    base = pasta / PASTA_ANTIGAS_DA_AMOSTRAGEM / f"{ANALISE_AMOSTRAGEM}_{quando:%Y-%m-%d_%H%M}"
    destino = base
    sufixo = 2
    while destino.exists():
        destino = base.with_name(f"{base.name}_{sufixo}")
        sufixo += 1

    desenho = None
    if anterior is not None:
        texto = anterior.itens[0].detalhes.get("desenho_yaml")
        desenho = texto if isinstance(texto, str) and texto else None
    return Arquivamento(destino=destino, arquivos=tuple(vigentes), desenho=desenho)


def _rodada_vigente(pasta: Path) -> Manifesto | None:
    """
    O manifesto da rodada que está no alto da pasta, quando há um legível e da amostragem.

    Lido uma vez, para duas coisas que não são indispensáveis: o aviso de mudança e o
    `desenho.yaml` de então. Por isso o manifesto quebrado ou de outra coisa não recusa
    a rodada nova: ela sai sem o aviso e sem a cópia.
    """
    try:
        anterior = ler_manifesto(pasta)
    except ManifestoError:
        return None
    if anterior.analise != ANALISE_AMOSTRAGEM or not anterior.itens:
        return None
    return anterior


def _mudanca(anterior: Manifesto | None, tamanho: Tamanho) -> str | None:
    """
    O aviso de quando o tamanho muda em relação à rodada vigente.

    Um tamanho de amostra entregue ao cliente que muda em silêncio é o pior jeito de ele
    mudar. A rodada anterior vai para as versões antigas de qualquer jeito — o aviso é
    para você saber, antes de escrever, que o número que o cliente tem vai deixar de ser
    o vigente.
    """
    if anterior is None:
        return None
    antes = anterior.itens[0].detalhes.get("n_final")
    if not isinstance(antes, int) or antes == tamanho.n_final:
        return None
    return (
        f"O tamanho da amostra muda em relação à rodada vigente, de "
        f"{anterior.gerado_em:%d/%m/%Y %H:%M}: era {antes}, e passa a ser "
        f"{tamanho.n_final}. A rodada anterior vai inteira para "
        f"`{PASTA_AMOSTRAGEM}/{PASTA_ANTIGAS_DA_AMOSTRAGEM}/`, com o relatório entregue "
        "com ela."
    )


def _acao_do_historico(plano: PlanoAmostragem) -> str:
    comando = f"`flatcap amostragem {plano.ficha.record_id}`"
    amostragem = plano.amostragem
    if amostragem is None or plano.destino is None:
        return (
            f"{comando} — `{PASTA_AMOSTRAGEM}/{ARQUIVO_DESENHO}` escrito, para preencher: "
            "o modelo do desenho da amostra."
        )

    tamanho = amostragem.tamanho
    campos = amostragem.calculo.campos or {}
    if tamanho.decidido:
        como = f"{tamanho.n}, decidido à mão"
    else:
        como = (
            f"{campos.get('confianca', '')} de confiança e margem de "
            f"{campos.get('margem', '')}"
        )
    partes = [
        f"{comando} — tamanho da amostra ({amostragem.desenho.titulo}): "
        f"{resumo_do_tamanho(tamanho)} ({como}"
        + (f"; perda de {campos['perda']}" if tamanho.perda else "")
        + f"). Relatório `{plano.destino.name}` em `{PASTA_AMOSTRAGEM}/`."
    ]
    if plano.arquivamento is not None:
        partes.append(
            f"A rodada anterior foi para `{PASTA_AMOSTRAGEM}/{PASTA_ANTIGAS_DA_AMOSTRAGEM}/"
            f"{plano.arquivamento.destino.name}/`."
        )
    return " ".join(partes)


__all__ = [
    "ARQUIVO_TAMANHO",
    "CHAVES_COMUNS",
    "DESENHOS",
    "DESENHO_AAS",
    "ESPECIE_TAMANHO",
    "METODOLOGIA",
    "MODELO_DO_DESENHO",
    "PREFIXO_RELATORIO_DA_AMOSTRA",
    "PREVISTOS",
    "ROTULO_DO_TAMANHO",
    "TITULO_DA_AMOSTRA",
    "Amostragem",
    "AmostragemError",
    "Arquivamento",
    "Calculo",
    "Desenho",
    "DesenhoExistenteError",
    "DesenhoInvalidoError",
    "Pedido",
    "PlanoAmostragem",
    "ResultadoAmostragem",
    "calcular_aas",
    "executar_amostragem",
    "ler_desenho",
    "montar_manifesto",
    "montar_relatorio",
    "montar_tabela",
    "nome_do_relatorio_da_amostra",
    "preparar_amostragem",
    "resumo_do_tamanho",
    "texto_de_metodologia",
]
