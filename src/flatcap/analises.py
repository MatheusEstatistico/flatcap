# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
"""
O lote — as análises da lista `analises:` do projeto.yaml, de uma vez.

Cada análise tem o seu comando, e todos continuam existindo: `flatcap descritiva`,
`flatcap correlacao` e os outros quatro. Este módulo é para o dia em que a reunião
combinou quatro delas — em vez de quatro comandos, um, o `flatcap analisar`:

    plano = preparar_analises(raiz)   # prepara todas; se uma recusa, nada é escrito
    executar_analises(plano)          # escreve todas, na ordem da lista

E, como as análises que ele chama, **não fala com o REDCap**. Recebe `Path`, não
`Config`.

## A soma dos comandos, e nada além

Não há aqui uma segunda forma de descrever, testar ou arquivar. Cada análise é
preparada pelo `preparar_*` dela e escrita pelo `executar_*` dela, com os mesmos
argumentos que o comando dela passaria — e por isso a rodada que o lote escreve é,
byte a byte, a que o comando dela escreveria no mesmo minuto. É o critério de pronto
deste módulo, e há teste com esse nome. No dia em que a correlação mudar, o lote muda
junto sem que uma linha daqui mude.

O preço é o banco aberto uma vez por análise, e não uma vez só: cada `preparar_*`
chama o `banco.abrir` dele, com a conferência do `sha256`. Num banco de algumas
centenas de linhas são décimos de segundo por análise — os gráficos a 600 DPI custam
mais do que isso. Abrir uma vez só pediria um parâmetro novo em seis módulos e
entregaria o mesmo `DataFrame` a seis análises, e a primeira que o alterasse por
engano mudaria as outras cinco. Seis leituras dão seis quadros independentes, que é
o que cada comando já faz sozinho.

## As três regras, do plano da Fase 7

**Obedece à lista, e não escolhe.** Quais análises rodam é decisão do estatístico,
tomada na reunião e escrita na ficha — a mesma regra que faz cada análise ler os pares
da ficha em vez de deduzi-los do dicionário. Lista vazia recusa, e a recusa escreve a
linha pronta para copiar a partir dos blocos que a ficha já tem. Nome que o FlatCap
não conhece recusa com a grafia certa. Nome repetido recusa, porque a posição na lista
é a posição da seção no relatório, e uma análise não tem duas.

**Prepara todas antes de escrever qualquer uma.** É o `preparar`/`executar` da casa
aplicado à corrente. Se a correlação vai recusar porque uma variável não existe, isso
precisa aparecer antes de a descritiva arquivar a rodada anterior — senão sobra uma
rodada velha arquivada e metade da nova escrita. As recusas saem **todas de uma vez**,
pelo motivo da descritiva: descobrir a segunda depois de corrigir a primeira é o jeito
mais lento de arrumar uma ficha. A exceção é o que vale para todas — a ficha, o banco,
o dicionário —, que para na primeira: seis painéis dizendo que o `dicionario.csv` não
existe não ensinam nada que o primeiro não tenha ensinado.

**Um registro nome → módulo, com import preguiçoso.** O `REGISTRO` é o que faz a
sétima análise custar uma linha aqui. Preguiçoso porque importar este módulo não pode
trazer o `pandas`: a CLI o evita no topo de propósito, e o `listar` roda várias vezes
por dia.

## O que ele não faz

**Não gera o relatório.** Entre rodar as análises e montar o documento há uma leitura
sua — e a simulação não teria como mostrar um relatório montado sobre rodadas que
ainda não foram escritas.

**Não desfaz as análises que já escreveu quando uma falha no meio.** A que falhou se
desfaz sozinha, como no comando dela; as anteriores são rodadas completas, cada uma
coerente consigo mesma, e ficam. O `historico.md` ganha a linha que diz onde o lote
parou, e a mesma frase vai presa ao erro, para o terminal dizer o que o disco diz.
"""

from __future__ import annotations

import difflib
import importlib
import re
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import Any

from .ficha import ARQUIVO_PROJETO, Ficha, bloco
from .ficha import ler as ler_ficha
from .manifesto import (
    ANALISE_ASSOCIACAO,
    ANALISE_COMPARACAO,
    ANALISE_CORRELACAO,
    ANALISE_CRUZAMENTO,
    ANALISE_DESCRITIVA,
    ANALISE_NORMALIDADE,
    ARQUIVO_MANIFESTO,
)
from .projeto import PASTA_ANALISES, PASTA_ANTIGAS, anotar, pastas_das_analises

# A chave da ficha. É a mesma que o `ficha.Ficha.analises` lê e que o relatório usa
# para ordenar as seções — o lote só passou a obedecê-la.
CHAVE_DA_LISTA = "analises"


# O registro


@dataclass(frozen=True)
class Analise:
    """
    Uma análise que o lote sabe rodar.

    O nome é um só para quatro coisas — a lista `analises:`, o bloco da ficha, a
    pasta em `3. Análises/` e o campo `analise` do manifesto — e é dele que saem os
    nomes do resto: o módulo `<nome>.py`, as funções `preparar_<nome>` e
    `executar_<nome>`, e a classe de erro `<Nome>Error`. A convenção existe desde a
    normalidade, e o teste do registro é o que impede uma análise nova de quebrá-la
    em silêncio.

    O título é o do painel, com acento — "Associação" —, o mesmo que o comando da
    análise usa quando ela recusa.
    """

    nome: str
    titulo: str
    desenha: bool  # o `preparar_*` dela aceita `com_graficos`

    @property
    def modulo(self) -> ModuleType:
        # Aqui, e não no topo do arquivo: é o import preguiçoso da terceira regra.
        # O módulo da análise traz o `pandas` e o `scipy`, e só quem roda paga.
        return importlib.import_module(f"{__package__}.{self.nome}")

    @property
    def erro(self) -> type[Exception]:
        """A classe que a análise levanta quando recusa: `CorrelacaoError`."""
        return getattr(self.modulo, f"{self.nome.capitalize()}Error")

    @property
    def erros_do_projeto(self) -> tuple[type[Exception], ...]:
        """
        As recusas da análise que valem para todas: o dicionário ausente, e o que não
        descreve o banco. As seis análises obedecem ao mesmo dicionário pela mesma
        função, `descritiva.conferir_dicionario`, e a recusa de uma é a de todas.
        """
        modulo = self.modulo
        return (modulo.DicionarioAusenteError, modulo.DicionarioDesatualizadoError)

    def preparar(
        self,
        raiz: Path,
        *,
        aba: str | None,
        conferir: bool,
        com_graficos: bool,
        agora: datetime,
    ) -> Any:
        """
        Chama o `preparar_*` da análise com os argumentos que o comando dela passaria.

        O `com_graficos` só vai para quem desenha: o `preparar_cruzamento` não o
        aceita, e um argumento a mais seria um `TypeError` em vez de um plano.
        """
        funcao = getattr(self.modulo, f"preparar_{self.nome}")
        extras = {"com_graficos": com_graficos} if self.desenha else {}
        return funcao(raiz, aba=aba, conferir=conferir, agora=agora, **extras)

    def executar(self, plano: Any) -> Any:
        return getattr(self.modulo, f"executar_{self.nome}")(plano)


# Na ordem padrão do relatório (`manifesto.ORDEM_PADRAO_DAS_ANALISES`), e há teste que
# exige as duas iguais: uma análise nova que entre num dos dois registros e não no
# outro roda sem ter lugar no documento, ou tem lugar no documento e não roda.
REGISTRO: tuple[Analise, ...] = (
    Analise(ANALISE_DESCRITIVA, "Descritiva", desenha=True),
    Analise(ANALISE_CRUZAMENTO, "Cruzamento", desenha=False),
    Analise(ANALISE_ASSOCIACAO, "Associação", desenha=False),
    Analise(ANALISE_NORMALIDADE, "Normalidade", desenha=True),
    Analise(ANALISE_CORRELACAO, "Correlação", desenha=True),
    Analise(ANALISE_COMPARACAO, "Comparação", desenha=False),
)

_POR_NOME: dict[str, Analise] = {registro.nome: registro for registro in REGISTRO}


# Erros


class AnalisesError(RuntimeError):
    """
    Falha do lote, já traduzida para o usuário.

    Erro próprio pelo mesmo motivo de todo módulo do pacote: a CLI captura esta
    classe e transforma em painel; qualquer outra exceção é bug e sobe com o
    traceback inteiro.
    """


class ListaVaziaError(AnalisesError):
    """
    A lista `analises:` está vazia — como o `flatcap novo` a deixa em toda ficha.
    """


class ListaMalEscritaError(AnalisesError):
    """
    A chave `analises:` não é uma lista de nomes.

    Recusa em vez de ignorar, pelo motivo que a normalidade escreveu para a lista
    dela: ignorar seria rodar como se a linha não estivesse lá — você escreveu, e não
    valeu.
    """


class AnaliseDesconhecidaError(AnalisesError):
    """
    A lista pede uma análise que o FlatCap não tem — quase sempre uma grafia.
    """


class AnaliseRepetidaError(AnalisesError):
    """
    A lista pede a mesma análise duas vezes.
    """


class DicionarioDoLoteError(AnalisesError):
    """
    O dicionário recusou a primeira análise, e recusaria todas.
    """


class AnalisesRecusadasError(AnalisesError):
    """
    Uma ou mais análises da lista recusaram. Carrega todas as recusas.

    Nada foi escrito: é a segunda regra, a de preparar tudo antes de escrever.
    """

    def __init__(self, recusas: Sequence[Recusa], prontas: Sequence[str]) -> None:
        self.recusas = tuple(recusas)
        self.prontas = tuple(prontas)
        partes = [f"{recusa.titulo}: {recusa.mensagem}" for recusa in self.recusas]
        super().__init__("\n\n".join([*partes, self.resumo]))

    @property
    def resumo(self) -> str:
        """A frase que fecha a lista de recusas, no terminal e no `str` do erro."""
        recusadas = [recusa.nome for recusa in self.recusas]
        total = len(recusadas) + len(self.prontas)
        if not self.prontas:
            abertura = (
                "A única análise da lista recusou."
                if total == 1
                else f"As {total} análises da lista recusaram."
            )
            return f"{abertura} Nada foi escrito nem arquivado."

        uma_recusa = len(recusadas) == 1
        uma_pronta = len(self.prontas) == 1
        return (
            f"{len(recusadas)} das {total} análises da lista "
            f"{'recusou' if uma_recusa else 'recusaram'} ({_em_texto(recusadas)}). "
            "Nada foi escrito nem arquivado: o lote só escreve quando todas podem ser "
            f"escritas. {'A outra' if uma_pronta else 'As outras'} "
            f"({_em_texto(self.prontas)}) {'está pronta' if uma_pronta else 'estão prontas'}"
            f" — rode o lote de novo depois de resolver "
            f"{'a recusa' if uma_recusa else 'as recusas'}, ou "
            f"{'o comando dela' if uma_pronta else 'o comando de cada uma'}, à parte."
        )


# O plano


@dataclass(frozen=True)
class Recusa:
    """Uma análise da lista que recusou, com o erro dela."""

    analise: Analise
    erro: Exception

    @property
    def nome(self) -> str:
        return self.analise.nome

    @property
    def titulo(self) -> str:
        return self.analise.titulo

    @property
    def mensagem(self) -> str:
        return str(self.erro)


@dataclass(frozen=True)
class Etapa:
    """
    Uma análise da lista, preparada: o registro dela e o plano que o `preparar_*`
    dela devolveu — o mesmo objeto que o comando dela mostraria e escreveria.
    """

    analise: Analise
    plano: Any

    @property
    def nome(self) -> str:
        return self.analise.nome

    @property
    def titulo(self) -> str:
        return self.analise.titulo

    @property
    def conteudo(self) -> Any:
        """
        O que a análise calculou — `plano.descritiva`, `plano.correlacao`… Todo plano
        de análise guarda o resultado num atributo com o nome dela, e é ali que moram
        a ficha, o banco e os avisos.
        """
        return getattr(self.plano, self.nome)

    @property
    def pasta(self) -> Path:
        return self.plano.pasta

    @property
    def arquivamento(self) -> tuple[Path, Path] | None:
        return self.plano.arquivamento

    @property
    def arquivos(self) -> tuple[str, ...]:
        return self.plano.arquivos


@dataclass(frozen=True)
class PlanoAnalises:
    """
    Tudo o que o `analisar` faria, decidido e ainda não escrito.

    Imutável como os planos que ele carrega. Entre a simulação e a execução ninguém
    troca uma etapa de lugar: a árvore do terminal é lida deste objeto, e a execução
    percorre o mesmo.
    """

    raiz: Path
    ficha: Ficha
    etapas: tuple[Etapa, ...]
    quando: datetime
    com_graficos: bool
    # As análises com bloco escrito na ficha e sem o nome na lista: ficam de fora
    # deste lote, e o histórico diz isso.
    fora_da_lista: tuple[str, ...] = ()
    avisos: tuple[str, ...] = ()

    @property
    def nomes(self) -> tuple[str, ...]:
        return tuple(etapa.nome for etapa in self.etapas)

    @property
    def banco(self) -> Any:
        """
        O banco que as análises leram — o da primeira etapa. Cada uma o abriu por
        conta própria, e todas abriram a mesma versão vigente da ficha.
        """
        return self.etapas[0].conteudo.banco

    @property
    def desenha(self) -> bool:
        """Alguma análise do lote desenharia, se os gráficos estivessem ligados."""
        return any(etapa.analise.desenha for etapa in self.etapas)


@dataclass(frozen=True)
class Feita:
    """Uma análise que a execução escreveu, e o que o `executar_*` dela devolveu."""

    etapa: Etapa
    resultado: Any

    @property
    def nome(self) -> str:
        return self.etapa.nome

    @property
    def arquivado(self) -> tuple[Path, Path] | None:
        return self.resultado.arquivado

    @property
    def avisos(self) -> tuple[str, ...]:
        return self.resultado.avisos


@dataclass(frozen=True)
class ResultadoAnalises:
    """O que a execução de fato escreveu."""

    feitas: tuple[Feita, ...] = ()
    avisos: tuple[str, ...] = ()


# Casos de uso


def preparar_analises(
    raiz: Path,
    aba: str | None = None,
    conferir: bool = True,
    com_graficos: bool = True,
    agora: datetime | None = None,
) -> PlanoAnalises:
    """
    Lê a lista, prepara cada análise dela e monta o plano. Não escreve nada.

    Cada análise recebe o que o comando dela receberia, e o mesmo relógio: as rodadas
    do lote saem com a mesma hora no manifesto e no nome da pasta arquivada, e é
    assim que se reconhece em `2. Versões antigas/` o que foi arquivado junto.

    Args:
        raiz: a pasta do projeto (a que tem o `projeto.yaml`).
        aba: planilha do `.xlsx`, quando houver mais de uma — a mesma para todas.
        conferir: reler o `sha256` das versões e comparar com a ficha.
        com_graficos: desenhar os `.png` das análises que desenham.
        agora: relógio injetável, como em todo `preparar*`.

    Raises:
        FichaError, BancoError, DicionarioError e `OSError`, que valem para todas as
        análises e param na primeira; os erros da lista (`ListaVaziaError`,
        `ListaMalEscritaError`, `AnaliseDesconhecidaError`,
        `AnaliseRepetidaError`); `DicionarioDoLoteError`; e
        `AnalisesRecusadasError`, com todas as recusas de uma vez.
    """
    raiz = Path(raiz)
    quando = agora or datetime.now()

    ficha = ler_ficha(raiz)
    nomes = lista_da_ficha(raiz)

    etapas: list[Etapa] = []
    recusas: list[Recusa] = []
    for nome in nomes:
        registro = _POR_NOME[nome]
        try:
            plano = registro.preparar(
                raiz,
                aba=aba,
                conferir=conferir,
                com_graficos=com_graficos,
                agora=quando,
            )
        except registro.erros_do_projeto as erro:
            # Antes do `registro.erro`, porque são subclasses dele.
            raise DicionarioDoLoteError(
                f"{erro}\n\nVale para todas as análises da lista — elas obedecem ao "
                "mesmo dicionário —, e nenhuma foi preparada."
            ) from erro
        except registro.erro as erro:
            recusas.append(Recusa(registro, erro))
            continue
        etapas.append(Etapa(registro, plano))

    if recusas:
        raise AnalisesRecusadasError(recusas, prontas=[etapa.nome for etapa in etapas])

    escritos = _blocos_escritos(raiz)
    no_disco = _rodadas_no_disco(raiz)
    fora = tuple(nome for nome in escritos if nome not in nomes)
    return PlanoAnalises(
        raiz=raiz,
        ficha=ficha,
        etapas=tuple(etapas),
        quando=quando,
        com_graficos=com_graficos,
        fora_da_lista=fora,
        avisos=tuple(_avisos_fora_da_lista(nomes, escritos, no_disco)),
    )


def executar_analises(
    plano: PlanoAnalises,
    ao_escrever: Callable[[Feita], None] | None = None,
) -> ResultadoAnalises:
    """
    Escreve as análises do plano, uma por uma, na ordem da lista. Não decide nada.

    Cada uma é escrita pelo `executar_*` dela, que arquiva a rodada anterior, escreve a
    nova, anota o histórico — e se desfaz sozinha quando falha no meio. Por último, a
    linha do lote no `historico.md`, que diz que as linhas de cima foram uma execução
    só.

    Args:
        plano: o que o `preparar_analises` devolveu.
        ao_escrever: chamado depois de cada análise escrita. É por onde a CLI mostra o
            andamento, uma análise por vez, em vez de ficar muda até o fim.

    Uma falha no meio para o lote. A análise que falhou já se desfez; as anteriores
    ficam; as seguintes não rodam. O `historico.md` ganha a linha que diz isso, e a
    mesma frase vai presa ao erro como nota (`add_note`), que o erro continua subindo
    como veio: `OSError` é falha de disco, e a CLI a transforma em painel; qualquer
    outra exceção é bug e sobe com o traceback — e com a nota junto.
    """
    feitas: list[Feita] = []
    em_curso: Etapa | None = None
    try:
        for etapa in plano.etapas:
            em_curso = etapa
            resultado = etapa.analise.executar(etapa.plano)
            em_curso = None
            feitas.append(Feita(etapa, resultado))
            if ao_escrever is not None:
                ao_escrever(feitas[-1])
    except BaseException as erro:
        # `BaseException`, e não só `Exception`: um Ctrl+C no meio do lote também
        # merece a linha no histórico dizendo o que ficou escrito e o que não rodou.
        situacao = situacao_da_parada(plano, feitas, em_curso, erro)
        try:
            # Minúscula depois do travessão, como toda linha do histórico.
            acao = f"{_comando(plano)} — {situacao[0].lower()}{situacao[1:]}"
            anotar(plano.raiz, acao, plano.quando)
        except OSError:
            situacao += " (Esta frase não chegou ao historico.md: a escrita falhou.)"
        erro.add_note(situacao)
        raise

    avisos: list[str] = []
    try:
        anotar(plano.raiz, _acao_do_historico(plano), plano.quando)
    except OSError as erro:
        avisos.append(
            f"As análises foram escritas, mas não consegui escrever a linha do lote no "
            f"historico.md: {erro}"
        )
    return ResultadoAnalises(feitas=tuple(feitas), avisos=tuple(avisos))


# A lista


def lista_da_ficha(raiz: Path) -> tuple[str, ...]:
    """
    Os nomes da lista `analises:`, conferidos: todos conhecidos, nenhum repetido.

    Lê o bloco cru pelo `ficha.bloco`, e não a `Ficha.analises`, de propósito. A
    `Ficha` descarta em silêncio o que não reconhece, e para o relatório ela está
    certa: lá a lista só ordena seções, e uma entrada malformada é um estrago pequeno
    e local. Aqui a lista **dirige** — uma entrada que some em silêncio é uma análise
    combinada na reunião que não roda, sem que ninguém fique sabendo. O que a `Ficha`
    perdoa, o lote recusa, com a frase do conserto.

    Raises:
        ListaVaziaError, ListaMalEscritaError, AnaliseDesconhecidaError,
        AnaliseRepetidaError, FichaError
    """
    bruto = bloco(raiz, CHAVE_DA_LISTA)

    # `analises:` sem nada, e a chave ausente, chegam como `None`; `analises: []`,
    # como a lista vazia. Os três são a lista vazia.
    if bruto is None:
        itens: list[Any] = []
    elif isinstance(bruto, str):
        if bruto.strip():
            raise ListaMalEscritaError(_mensagem_de_texto(bruto))
        itens = []
    elif isinstance(bruto, list):
        itens = bruto
    else:
        raise ListaMalEscritaError(_mensagem_de_item(bruto, sozinho=True))

    nomes: list[str] = []
    for item in itens:
        if item is None:  # `- ` sem nada: a `Ficha` também o pula
            continue
        if not isinstance(item, str):
            raise ListaMalEscritaError(_mensagem_de_item(item))
        if item.strip():
            nomes.append(item.strip())

    if not nomes:
        raise ListaVaziaError(_mensagem_de_lista_vazia(raiz))

    desconhecidos = [nome for nome in dict.fromkeys(nomes) if nome not in _POR_NOME]
    if desconhecidos:
        raise AnaliseDesconhecidaError(_mensagem_de_desconhecidos(desconhecidos))

    repetidos = [nome for nome in dict.fromkeys(nomes) if nomes.count(nome) > 1]
    if repetidos:
        raise AnaliseRepetidaError(_mensagem_de_repetidos(repetidos))

    return tuple(nomes)


def _blocos_escritos(raiz: Path) -> tuple[str, ...]:
    """
    As análises do registro que têm bloco escrito na ficha — na ordem do registro.

    Escrito é não vazio: `cruzamento: []` é a chave sem par nenhum, e a análise dela
    recusaria. A descritiva não tem bloco; entra aqui só se alguém escrever um.
    """
    return tuple(registro.nome for registro in REGISTRO if bloco(raiz, registro.nome))


def _rodadas_no_disco(raiz: Path) -> tuple[str, ...]:
    """
    As rodadas vigentes em `3. Análises/`: pasta com `manifesto.json` dentro.

    Pelo nome da pasta, que é o nome da análise — o mesmo critério e a mesma
    varredura do relatório, sem abrir manifesto nenhum.
    """
    return tuple(
        pasta.name
        for pasta in pastas_das_analises(raiz)
        if (pasta / ARQUIVO_MANIFESTO).is_file()
    )


def _avisos_fora_da_lista(
    nomes: Sequence[str], escritos: Sequence[str], no_disco: Sequence[str]
) -> list[str]:
    """
    O que a ficha e o disco têm de análise fora da lista.

    Aviso, e não recusa: é a lista que manda, e uma análise pode ter ficado de fora
    de propósito. Mas "ficou de fora" e "ninguém reparou que ela existia" são coisas
    diferentes — é a mesma razão da lista `fora` de toda análise. E a rodada antiga no
    disco pesa mais do que parece: o relatório a inclui depois das seções da lista,
    com os números de quando ela rodou.
    """
    avisos: list[str] = []
    for registro in REGISTRO:
        nome = registro.nome
        if nome in nomes:
            continue
        com_bloco = nome in escritos
        com_rodada = nome in no_disco
        pasta = f"`{PASTA_ANALISES}/{nome}/`"
        if com_bloco and com_rodada:
            avisos.append(
                f"`{nome}` não está na lista `analises:`, mas o bloco `{nome}:` está "
                f"escrito na ficha e há uma rodada dela em {pasta}. Ela não roda neste "
                "lote, e o relatório inclui a rodada antiga depois das seções da lista. "
                "Acrescente o nome à lista para refazê-la, ou mova a pasta para "
                f"`{PASTA_ANTIGAS}/` se ela não vai para o documento."
            )
        elif com_bloco:
            avisos.append(
                f"`{nome}` não está na lista `analises:`, e o bloco `{nome}:` está "
                "escrito na ficha — ela não roda neste lote. Acrescente o nome à lista, "
                f"ou rode `flatcap {nome} <id>` à parte."
            )
        elif com_rodada:
            avisos.append(
                f"`{nome}` não está na lista `analises:`, e há uma rodada dela em "
                f"{pasta}. O lote não a toca, e o relatório a inclui depois das seções "
                "da lista, com os números de quando ela rodou — se ela não vai para o "
                f"documento, mova a pasta para `{PASTA_ANTIGAS}/`."
            )
    return avisos


# As mensagens da lista


def _mensagem_de_lista_vazia(raiz: Path) -> str:
    escritos = _blocos_escritos(raiz)
    linha = [ANALISE_DESCRITIVA] + [nome for nome in escritos if nome != ANALISE_DESCRITIVA]
    if escritos:
        origem = "Pelos blocos que a ficha já tem, a linha seria:"
    else:
        origem = (
            "A ficha não tem bloco de análise nenhum — os pares e os itens das outras "
            "análises se escrevem nos blocos delas —, então a linha mínima seria:"
        )
    partes = [
        f"A lista `{CHAVE_DA_LISTA}:` do {ARQUIVO_PROJETO} está vazia. O `flatcap "
        "analisar` roda o que está escrito nela, na ordem dela — que é também a ordem "
        "das seções do relatório —, e não escolhe análise nenhuma por conta própria.",
        "",
        origem,
        "",
        f"    {CHAVE_DA_LISTA}: [{', '.join(linha)}]",
        "",
        f"Escreva essa linha no {ARQUIVO_PROJETO}, no lugar do `{CHAVE_DA_LISTA}: []` que "
        "o `flatcap novo` deixou, e ajuste a ordem.",
    ]
    if ANALISE_NORMALIDADE not in linha:
        partes += [
            "",
            f"A `{ANALISE_NORMALIDADE}` não precisa de bloco: sem ele, ela testa todas as "
            "numéricas do dicionário. Acrescente o nome se a tabela de pressupostos for "
            "para o relatório.",
        ]
    partes += [
        "",
        "Para rodar uma análise só, o comando dela continua valendo: "
        "`flatcap descritiva <id>`.",
    ]
    return "\n".join(partes)


def _mensagem_de_texto(texto: str) -> str:
    # Vírgula, ponto e vírgula ou espaço: nome de análise não tem nenhum dos três, e
    # quem escreveu um texto no lugar da lista separou os nomes com algum deles.
    nomes = [parte for parte in re.split(r"[,;\s]+", texto.strip()) if parte]
    return (
        f"A chave `{CHAVE_DA_LISTA}:` do {ARQUIVO_PROJETO} tem um texto, e não uma "
        f"lista: `{texto.strip()}`.\n\n"
        "Escreva os nomes entre colchetes:\n\n"
        f"    {CHAVE_DA_LISTA}: [{', '.join(nomes)}]\n\n"
        "ou um por linha, com o hífen:\n\n"
        f"    {CHAVE_DA_LISTA}:\n"
        + "".join(f"      - {nome}\n" for nome in nomes)
    ).rstrip("\n")


def _mensagem_de_item(item: Any, sozinho: bool = False) -> str:
    """
    O item que não é um nome. Cada forma tem o engano provável que a produz.
    """
    onde = (
        f"A chave `{CHAVE_DA_LISTA}:` do {ARQUIVO_PROJETO} deveria ser uma lista de nomes"
        if sozinho
        else f"A lista `{CHAVE_DA_LISTA}:` do {ARQUIVO_PROJETO} tem um item que não é o "
        "nome de uma análise"
    )
    if isinstance(item, dict):
        chaves = ", ".join(f"`{chave}:`" for chave in item)
        conhecidas = [chave for chave in item if chave in _POR_NOME]
        if conhecidas:
            # O engano provável: os pares escritos dentro da lista, debaixo do nome.
            # A resposta mostra o mesmo conteúdo no lugar dele.
            nome = conhecidas[0]
            return (
                f"{onde}: {chaves}, com o que seria o bloco dela dentro.\n\n"
                "A lista leva só os nomes; os pares e os itens vão no bloco da análise, "
                "fora da lista, no nível de cima da ficha:\n\n"
                f"    {CHAVE_DA_LISTA}:\n"
                "      - …\n"
                f"      - {nome}\n\n"
                f"    {nome}:\n"
                + "\n".join(f"      - {linha}" for linha in _itens_do_bloco(item[nome]))
            )
        return f"{onde}: {chaves}.\n\nA lista leva só os nomes das análises, um por item."
    if isinstance(item, list):
        nomes = ", ".join(str(parte) for parte in item)
        return (
            f"{onde}: `[{nomes}]`, uma lista dentro da lista.\n\n"
            f"Um nome por item — `{CHAVE_DA_LISTA}: [{nomes}]` numa linha só, ou um por "
            "linha com o hífen, sem os colchetes."
        )
    return (
        f"{onde}: `{item}`.\n\n"
        "A lista leva os nomes das análises, um por item: "
        f"{_em_texto([registro.nome for registro in REGISTRO])}."
    )


def _itens_do_bloco(valor: Any) -> list[str]:
    """
    Os itens de um bloco como se escrevem na ficha: `[idade, imc]`, `sexo: [imc]`.
    """
    if not isinstance(valor, list) or not valor:
        return ["…"]
    linhas = []
    for item in valor:
        if isinstance(item, list):
            linhas.append(f"[{', '.join(str(parte) for parte in item)}]")
        elif isinstance(item, dict):
            linhas.append(
                ", ".join(
                    f"{chave}: [{', '.join(str(p) for p in conteudo)}]"
                    if isinstance(conteudo, list)
                    else f"{chave}: {conteudo}"
                    for chave, conteudo in item.items()
                )
            )
        else:
            linhas.append(str(item))
    return linhas


def _mensagem_de_desconhecidos(desconhecidos: Sequence[str]) -> str:
    linhas = [
        f"A lista `{CHAVE_DA_LISTA}:` do {ARQUIVO_PROJETO} tem "
        + (
            "um nome que o FlatCap não conhece:"
            if len(desconhecidos) == 1
            else f"{len(desconhecidos)} nomes que o FlatCap não conhece:"
        ),
        "",
    ]
    for nome in desconhecidos:
        linhas.append(f"  {nome} — {_sugestao(nome)}")
    linhas += [
        "",
        "O nome é um só para a lista, para o bloco da ficha, para a pasta em "
        f"`{PASTA_ANALISES}/` e para o manifesto, e é por ele que o relatório encontra "
        "a rodada. As análises que existem: "
        f"{_em_texto([registro.nome for registro in REGISTRO])}.",
        "",
        "Nada foi preparado.",
    ]
    return "\n".join(linhas)


# Os nomes de teste que alguém escreve no lugar da análise que os roda. A análise é a
# pergunta, e o teste sai da regra de cada uma — é o desenho da comparação e da
# correlação, e a recusa ensina isso em vez de só dizer "não conheço".
_TESTES: dict[str, str] = {
    "anova": ANALISE_COMPARACAO,
    "t": ANALISE_COMPARACAO,
    "testet": ANALISE_COMPARACAO,
    "student": ANALISE_COMPARACAO,
    "welch": ANALISE_COMPARACAO,
    "wilcoxon": ANALISE_COMPARACAO,
    "mannwhitney": ANALISE_COMPARACAO,
    "kruskal": ANALISE_COMPARACAO,
    "kruskalwallis": ANALISE_COMPARACAO,
    "friedman": ANALISE_COMPARACAO,
    "quiquadrado": ANALISE_ASSOCIACAO,
    "fisher": ANALISE_ASSOCIACAO,
    "pearson": ANALISE_CORRELACAO,
    "spearman": ANALISE_CORRELACAO,
    "kendall": ANALISE_CORRELACAO,
    "shapiro": ANALISE_NORMALIDADE,
    "shapirowilk": ANALISE_NORMALIDADE,
    "frequencia": ANALISE_DESCRITIVA,
    "frequencias": ANALISE_DESCRITIVA,
}


def _sugestao(nome: str) -> str:
    """
    O conserto de um nome desconhecido, do mais certo para o mais provável.

    Acento e maiúscula primeiro, porque são o engano mais comum de quem escreve em
    português — `associação` é a palavra certa e o nome errado. Depois o nome de um
    teste no lugar da análise que o roda. Por último a grafia parecida.
    """
    chave = _sem_acento(nome).casefold()
    for registro in REGISTRO:
        if chave == registro.nome:
            if _sem_acento(nome) != nome:
                return f"escreva `{registro.nome}`, sem acento"
            return f"escreva `{registro.nome}`, em minúsculas"

    so_letras = "".join(letra for letra in chave if letra.isalnum())
    if so_letras in _TESTES:
        return f"é um teste, e ele roda dentro da `{_TESTES[so_letras]}`"

    parecidos = difflib.get_close_matches(chave, list(_POR_NOME), n=1, cutoff=0.6)
    if parecidos:
        return f"você quis dizer `{parecidos[0]}`?"
    return "não é uma análise do FlatCap"


def _mensagem_de_repetidos(repetidos: Sequence[str]) -> str:
    quais = _em_texto(repetidos)
    return (
        f"A lista `{CHAVE_DA_LISTA}:` do {ARQUIVO_PROJETO} repete {quais}.\n\n"
        "Cada análise roda uma vez, e a posição dela na lista é a posição da seção no "
        "relatório — com o nome duas vezes, não há como saber onde a seção deve sair. "
        "Deixe cada nome uma vez só, no lugar em que a seção deve aparecer."
    )


# O histórico


def _comando(plano: PlanoAnalises) -> str:
    return f"`flatcap analisar {plano.ficha.record_id}`"


def _acao_do_historico(plano: PlanoAnalises) -> str:
    """
    A linha do lote, escrita depois das linhas das análises.

    Cada análise escreve a sua, a mesma que o comando dela escreveria — é o que o
    lote é. Esta diz que elas foram uma execução só, e o que ficou de fora.
    """
    nomes = plano.nomes
    if len(nomes) == 1:
        partes = [
            f"{_comando(plano)} — a única análise da lista `{CHAVE_DA_LISTA}:`, "
            f"`{nomes[0]}`; a linha dela está acima."
        ]
    else:
        partes = [
            f"{_comando(plano)} — {len(nomes)} análises da lista `{CHAVE_DA_LISTA}:`, na "
            f"ordem dela: {_em_texto(nomes)}; a linha de cada uma está acima."
        ]
    if not plano.com_graficos and plano.desenha:
        partes.append("Rodado com `--sem-graficos`.")
    if plano.fora_da_lista:
        fora = plano.fora_da_lista
        partes.append(
            f"Fora da lista, e sem rodar: {_em_texto(fora)}, "
            f"{'que tem bloco escrito' if len(fora) == 1 else 'que têm bloco escrito'} "
            "na ficha."
        )
    return " ".join(partes)


def situacao_da_parada(
    plano: PlanoAnalises,
    feitas: Sequence[Feita],
    em_curso: Etapa | None,
    erro: BaseException,
) -> str:
    """
    Onde o lote parou, o que ficou escrito e o que não rodou — numa frase.

    A mesma frase vai para o `historico.md` e presa ao erro, e é por isso que ela é
    pública: a CLI a imprime no painel sem precisar recontar as etapas.

    "Foi desfeita" só vale para exceção comum. Um Ctrl+C (`KeyboardInterrupt`) não
    passa pelo desfazer do `executar_*` da análise, que pega `Exception`, e a pasta
    dela pode ter ficado pela metade — e a frase diz isso em vez de prometer o que
    não aconteceu.
    """
    escritas = [feita.nome for feita in feitas]
    posicao = len(escritas) + (1 if em_curso is not None else 0)
    faltam = [etapa.nome for etapa in plano.etapas[posicao:]]

    if em_curso is None:
        # Entre duas análises — no `ao_escrever` da CLI, que roda depois de cada uma.
        # Nenhuma pasta ficou pela metade, e a frase diz isso.
        if isinstance(erro, Exception):
            partes = [
                "Parou entre uma análise e a seguinte, por um erro inesperado "
                f"({type(erro).__name__}); nenhuma ficou pela metade."
            ]
        else:
            partes = ["Interrompido entre uma análise e a seguinte; nenhuma ficou pela metade."]
    elif isinstance(erro, Exception):
        como = (
            "falhou ao escrever em disco"
            if isinstance(erro, OSError)
            else f"falhou com um erro inesperado ({type(erro).__name__})"
        )
        volta = (
            ", com a rodada anterior de volta ao lugar"
            if em_curso.arquivamento is not None
            else ""
        )
        partes = [f"Parou na análise `{em_curso.nome}`, que {como} e foi desfeita{volta}."]
    else:
        partes = [
            f"Interrompido durante a análise `{em_curso.nome}`, que pode ter ficado pela "
            f"metade: confira `{PASTA_ANALISES}/{em_curso.nome}/` e `{PASTA_ANTIGAS}/` "
            "antes de rodar de novo."
        ]

    if escritas:
        lista = (
            f"a análise `{escritas[0]}` foi escrita."
            if len(escritas) == 1
            else f"as análises {_em_texto(escritas)} foram escritas."
        )
        partes.append(
            f"Antes dela, {lista}" if em_curso is not None else lista[0].upper() + lista[1:]
        )
    elif em_curso is not None:
        partes.append("Nenhuma análise foi escrita.")

    if faltam:
        if len(faltam) == 1:
            partes.append(f"A análise `{faltam[0]}` não rodou.")
        else:
            partes.append(f"As análises {_em_texto(faltam)} não rodaram.")
    return " ".join(partes)


# Texto


def _em_texto(nomes: Sequence[str]) -> str:
    """
    `["descritiva", "normalidade"]` → «`descritiva` e `normalidade`».

    Sem artigo antes do nome, pelo motivo que o relatório escreveu na função dele:
    `a descritiva` funciona, e `a cruzamento` não.
    """
    marcados = [f"`{nome}`" for nome in nomes]
    if len(marcados) <= 1:
        return marcados[0] if marcados else ""
    return ", ".join(marcados[:-1]) + f" e {marcados[-1]}"


def _sem_acento(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(letra for letra in decomposto if not unicodedata.combining(letra))


__all__ = [
    "CHAVE_DA_LISTA",
    "REGISTRO",
    "Analise",
    "AnaliseDesconhecidaError",
    "AnaliseRepetidaError",
    "AnalisesError",
    "AnalisesRecusadasError",
    "DicionarioDoLoteError",
    "Etapa",
    "Feita",
    "ListaMalEscritaError",
    "ListaVaziaError",
    "PlanoAnalises",
    "Recusa",
    "ResultadoAnalises",
    "executar_analises",
    "lista_da_ficha",
    "preparar_analises",
    "situacao_da_parada",
]
