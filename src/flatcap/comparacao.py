"""
A comparação — o t de uma amostra, e o lugar onde os outros testes de comparação vão
entrar.

Responde ao passo 2b do fluxo. Para cada item da ficha, uma linha de tabela:

    variável       n  média (DP)         IC 95% da média  referência  teste         p-valor
    IMC (kg/m²)  116  26,43 (4,59)       25,58 a 27,27    25          t de Student    0,001
    Renda (R$)   120  3098,64 (2139,03)  —                3000        não testado*        —

    * não testado: normal rejeitada — a regra escolhe o Wilcoxon, que ainda não está no
      FlatCap, e a linha sai com o motivo no lugar do teste.

Segue o padrão das Fases 2 a 6, decidir e escrever separados:

    plano = preparar_comparacao(raiz)   # abre o banco, calcula, não toca no disco
    executar_comparacao(plano)          # só escreve

E, como elas, **não fala com o REDCap**. Recebe `Path`, não `Config`.

## Uma análise, e o teste escolhido dentro dela

`comparacao` é uma análise só — uma chave na ficha, um comando, uma pasta em
`3. Análises/`, uma seção no documento —, e cada teste é uma entrada num registro
dentro dela, e não um módulo por teste. O que se escreve na reunião é a **pergunta**
("a média do IMC difere de 25?"), e não o teste: qual teste responde é consequência
do **delineamento**, que sai dos tipos do dicionário, e dos **pressupostos**, que
saem do banco. É a lição da correlação — a ficha lista os pares, a regra escolhe o
método, e o terceiro nome discorda quando você discordar.

O registro são dois dicionários aqui em cima. A `REGRA` diz, para cada delineamento,
o teste quando a normal se sustenta e o teste quando não; o `_CALCULO` diz quais deles
já têm a aritmética no `hipoteses.py`. Um teste que está na regra e não no cálculo é
um teste que a regra sabe escolher e o FlatCap ainda não sabe fazer — é o Wilcoxon
nesta versão, e a linha dele sai sem teste, com o motivo escrito. Quando ele chegar,
entra uma linha no `_CALCULO`, e as linhas "não testado" viram linhas de Wilcoxon.

## O delineamento, e o desta versão

A forma do item e os tipos das variáveis dizem qual comparação é:

    [imc, 25]                  numérica, e um número     uma amostra
    [pas_antes, pas_depois]    numérica, numérica        pareado (depois)
    [imc, sexo]                numérica, categórica      grupos (depois)

Esta versão faz a primeira: a média de uma variável numérica contra um valor de
referência escrito no item. As outras duas formas são recusadas com a frase que diz
que elas ainda não existem, e não interpretadas como outra coisa.

## A regra dos pressupostos

Três passos, como na correlação:

1. **o Shapiro-Wilk sobre o vetor do delineamento.** Na uma amostra, são os valores
   preenchidos da variável. Não rejeitou a normal → o t de Student;
2. **rejeitou, ou não pôde ser verificado** (dois valores) → o Wilcoxon, que ainda
   não está no FlatCap: a linha sai **sem teste**, com o motivo na coluna `teste`;
3. **o método escrito no item manda**: `[imc, 25, t]` roda o t contra a regra, com um
   aviso e a frase nas notas do `.csv`.

**A normalidade é a função, e não a rodada.** O teste é o `normalidade.shapiro`, o
mesmo que a correlação chama, com as mesmas barreiras e os mesmos avisos — e não o
`manifesto.json` da rodada de normalidade. O vetor que se testa muda com o
delineamento (a amostra aqui; as diferenças no pareado; cada grupo nos grupos), e uma
escolha que dependesse da outra rodada dependeria da ordem dos comandos e da idade
dela. Na uma amostra o vetor **é** a coluna sem os faltantes, então o p que decide é
o mesmo da tabela de normalidade — por construção.

**O Shapiro-Wilk não garante o pressuposto**, e o módulo não finge que garante: é a
regra que o projeto adotou, com os limites dela escritos no topo do `normalidade.py`.
Abaixo de 20 valores ele quase não rejeita, e o t escolhido ali sai com aviso; com n
grande ele rejeita desvio irrelevante, e a linha que sai sem teste diz como escrever
`t` no item quando você concluir que o t vale — n grande e assimetria pequena, por
exemplo. A decisão é sua, e fica registrada contra a regra.

## A ficha

    comparacao:
      - [imc, 25]          # a média do IMC difere de 25?
      - [pas, 120, t]      # o t, mesmo que a regra discorde

**A referência é obrigatória.** O padrão do R é `mu = 0`, que nunca é a hipótese de
uma variável clínica; o valor vem da literatura ou do protocolo, e é decidido na
reunião. **A vírgula decimal quebra a lista**: `[imc, 24,9]` é lido como três itens,
`imc`, `24` e `9`, e a recusa reconhece esse caso e escreve a forma certa —
`[imc, 24.9]`, ou `[imc, "24,9"]`, que entre aspas é aceito. **Sempre bilateral**:
um teste unilateral escolhido depois de olhar os dados é o p dividido por dois.

## O que ele reaproveita

As recusas de dicionário e de tipo são as da descritiva, com a classe de erro deste
módulo. O Shapiro-Wilk e o formatador do p são os da normalidade. A média e o desvio
padrão saem pelo `descritiva.resumo_numerico` e pelo `numero()`: a média desta tabela
é, letra por letra, a do `resumo_<variável>.csv`. A aritmética do teste é a do
`hipoteses.py`, que confere com o `t.test` do R.

## O que ele deliberadamente não faz

**Não desenha.** O histograma da descritiva e o Q-Q da normalidade são as figuras
desta variável, e uma terceira com a média e o intervalo repetiria a tabela.

**Não imprime o d de Cohen.** O intervalo da média, lido contra a coluna
`referência`, já é o tamanho do efeito — na unidade que o cliente entende.

**Não corrige para comparações múltiplas.** Cada linha é um teste, e isso está
escrito nas notas e no terminal.
"""

from __future__ import annotations

import math
import re
import sys
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from . import __version__
from .banco import Banco, abrir
from .descritiva import arquivamento as arquivamento_da_rodada
from .descritiva import conferir_dicionario, numero, recusar_incompativeis, resumo_numerico
from .dicionario import ARQUIVO_DICIONARIO, CATEGORICA, IGNORAR, NUMERICA, Linha
from .ficha import Ficha, bloco, escrever_atomico
from .ficha import ler as ler_ficha
from .hipoteses import CONFIANCA, MINIMO_T, T_DE_STUDENT, Resultado, sem_variacao, t_uma_amostra
from .manifesto import (
    ANALISE_COMPARACAO,
    ARQUIVO_MANIFESTO,
    SEMENTE,
    Artefato,
    ItemDoManifesto,
    Manifesto,
    Tabela,
    texto_do_manifesto,
)
from .nomes import rotulo_do_projeto
from .normalidade import ALFA, MENOR_P, MINIMO_CONFIAVEL, POUCOS_DISTINTOS, shapiro, valor_p
from .projeto import (
    ARQUIVO_PROJETO,
    PASTA_ANALISES,
    PASTA_ANTIGAS,
    PASTA_COMPARACAO,
    anotar,
    pasta_da_analise,
)

ARQUIVO_TABELA = "uma_amostra.csv"

# Os delineamentos. Um só nesta versão; os outros entram aqui, com a linha deles na
# `REGRA` e a forma do item em `itens_da_ficha`.
UMA_AMOSTRA = "uma_amostra"

# Os testes que a regra conhece pelo nome. O t vem do `hipoteses.py`, que é quem
# calcula; o Wilcoxon é só um nome por enquanto — a regra o escolhe, e o FlatCap
# ainda não o faz.
WILCOXON = "Wilcoxon"

# A regra: para cada delineamento, o teste quando a normal se sustenta e o teste
# quando não.
REGRA: dict[str, tuple[str, str]] = {
    UMA_AMOSTRA: (T_DE_STUDENT, WILCOXON),
}

# O que já tem aritmética. Um teste da `REGRA` que não está aqui é escolhido pela
# regra e sai sem teste, com o motivo; a entrada do Wilcoxon de uma amostra é a
# próxima linha deste registro.
_CALCULO: dict[tuple[str, str], Callable[..., Resultado]] = {
    (UMA_AMOSTRA, T_DE_STUDENT): t_uma_amostra,
}

# Como cada método se escreve no item — o terceiro nome. Minúsculo e sem acento, que
# é como se digita; a tabela sai com o nome próprio.
METODOS: dict[str, str] = {"t": T_DE_STUDENT, "student": T_DE_STUDENT}

# Os que a regra conhece e esta versão ainda não calcula. Escritos na ficha, recusam
# com a frase certa, em vez de "não é um método".
PREVISTOS: dict[str, str] = {"wilcoxon": WILCOXON}

# O intervalo sai com casas fixas: ele não existe na descritiva, e uma célula com
# `25,8 a 27,02` — um limite com uma casa, outro com duas — não se lê de relance. A
# média e o desvio não: eles têm de sair letra por letra como no `resumo`.
CASAS_IC = 2

# A referência sai como foi escrita, sem arredondar para duas casas: um `0,125` da
# ficha impresso `0,12` seria uma hipótese que ninguém testou.
CASAS_REFERENCIA = 6

_AUSENTE = "—"

# Um número escrito como texto na ficha: `"24,9"`, `"24.9"`, `" 25 "`. Sem separador
# de milhar — `1.234,5` é ambíguo, e ambiguidade numa hipótese se recusa.
_NUMERO_ESCRITO = re.compile(r"^[+\-]?\d+(?:[.,]\d+)?$")

# O exemplo que as mensagens escrevem. Um lugar só, para a recusa e o `--help` nunca
# ensinarem duas formas diferentes de escrever a mesma lista.
EXEMPLO_DA_FICHA = f"""  {PASTA_COMPARACAO}:
    - [imc, 25]
    - [pas, 120, t]"""


class ComparacaoError(RuntimeError):
    """
    Falha ao gerar a comparação, já traduzida para o usuário.

    Erro próprio pela regra da casa: a CLI captura esta classe e transforma em painel
    com o nome do comando que o usuário rodou. Qualquer outra exceção é bug de
    verdade e deve subir com o traceback inteiro.
    """


class DicionarioAusenteError(ComparacaoError):
    """
    O projeto não tem `dicionario.csv`. Não há o que obedecer.
    """


class DicionarioDesatualizadoError(ComparacaoError):
    """
    O banco tem colunas que o dicionário desconhece.
    """


class VariavelIncompativelError(ComparacaoError):
    """
    O dicionário promete `numerica` e a coluna chegou como texto, ou declara uma
    variável que o banco não tem.

    A mesma recusa da Fase 5, pela mesma função — aplicada só às variáveis da lista,
    como na correlação.
    """


class SemItensError(ComparacaoError):
    """
    A ficha não diz o que comparar.
    """


class ItemInvalidoError(ComparacaoError):
    """
    A lista `comparacao:` da ficha tem item que não serve.

    Formato errado, referência que não é número, a vírgula decimal que partiu o
    número em dois, método que não existe, nome fora do dicionário, variável que não é
    numérica, ou a mesma comparação duas vezes. A mensagem lista **todos** de uma
    vez, pela regra da Fase 5.
    """


# O que sai no disco


@dataclass(frozen=True)
class Pedido:
    """
    Um item como a ficha o escreve: a variável, a referência e, quando houver, o
    método — já com o nome próprio, ou vazio para "a regra escolhe".
    """

    variavel: str
    referencia: float
    metodo: str = ""

    @property
    def escrito(self) -> str:
        """O item de volta na forma da ficha, para as mensagens."""
        metodo = f", {_como_se_escreve(self.metodo)}" if self.metodo else ""
        return f"[{self.variavel}, {_referencia_em_texto(self.referencia, ponto=True)}{metodo}]"


@dataclass(frozen=True)
class Pergunta:
    """
    Um item da ficha, já conferido contra o dicionário. É a pergunta da reunião — "a
    média desta variável difere desta referência?" — com o delineamento que ela tem.
    """

    linha: Linha
    referencia: float
    metodo: str = ""
    delineamento: str = UMA_AMOSTRA


@dataclass(frozen=True)
class Normal:
    """
    O Shapiro-Wilk do vetor do delineamento.

    Os quatro campos são o que o `normalidade.shapiro` devolve: o W e o p quando o
    teste rodou, a frase do impedimento quando não rodou, e o aviso do `scipy` quando
    houve um.
    """

    w: float | None
    p: float | None
    impedimento: str = ""
    aviso: str = ""

    @property
    def testada(self) -> bool:
        return self.p is not None

    @property
    def rejeita(self) -> bool:
        return self.p is not None and self.p < ALFA


@dataclass(frozen=True)
class Escolha:
    """
    Qual teste rodou, e de onde ele veio.

    `da_regra` é o que a regra escolhe mesmo quando a ficha mandou outro, e mesmo
    quando o FlatCap ainda não o faz — é o que permite escrever "contra a regra" na
    nota, e dizer qual teste faltou. `metodo` vazio quer dizer que nenhum teste rodou:
    a regra escolheu um que ainda não tem aritmética, e a ficha não mandou outro.
    """

    metodo: str
    da_regra: str
    motivo: str
    pela_ficha: bool = False

    @property
    def contra_a_regra(self) -> bool:
        return self.pela_ficha and self.metodo != self.da_regra


@dataclass(frozen=True)
class VariavelComparada:
    """
    Uma variável, comparada com a referência. É uma linha da tabela.

    `resultado` fica `None` quando não houve teste; o motivo está em `motivo`, e a
    linha **sai assim mesmo** — um item pedido que sumisse da tabela seria a falta em
    que ninguém repara. A média e o desvio saem mesmo sem teste: eles descrevem a
    variável, e não dependem de pressuposto nenhum.
    """

    variavel: str
    rotulo: str
    referencia: float
    total: int
    validos: int
    distintos: int = 0
    delineamento: str = UMA_AMOSTRA
    resumo: dict[str, float] | None = None
    normal: Normal | None = None
    escolha: Escolha | None = None
    resultado: Resultado | None = None
    motivo: str = ""
    avisos: tuple[str, ...] = ()

    @property
    def faltantes(self) -> int:
        return self.total - self.validos

    @property
    def testada(self) -> bool:
        return self.resultado is not None

    @property
    def metodo(self) -> str:
        return self.resultado.metodo if self.resultado is not None else ""

    @property
    def celula_do_teste(self) -> str:
        """
        O que vai para a coluna `teste`: o nome do teste, ou o motivo no lugar dele —
        como a coluna `método` da correlação e a `teste` da associação.
        """
        if self.resultado is not None:
            return self.resultado.metodo
        return f"não testado: {self.motivo}"

    @property
    def justificativa(self) -> str:
        """
        A frase que explica a linha — a nota do `.csv` e a linha do terminal.

        Uma frase só, montada aqui, para que o arquivo e a tela digam a mesma coisa
        com as mesmas casas.
        """
        cabeca = f"{self.rotulo}: "
        escolha = self.escolha
        if escolha is None:
            return f"{cabeca}não testado — {self.motivo}."
        faltou = "" if _disponivel(self.delineamento, escolha.da_regra) else (
            ", que ainda não está no FlatCap"
        )
        if self.resultado is None:
            return (
                f"{cabeca}n = {self.validos}; {escolha.motivo} → {escolha.da_regra}"
                f"{faltou}: a linha sai sem teste."
            )
        estatistica = _estatistica_em_texto(self.resultado)
        if not escolha.pela_ficha:
            return (
                f"{cabeca}n = {self.validos}; {escolha.motivo} → {escolha.metodo} "
                f"({estatistica})."
            )
        if escolha.contra_a_regra:
            return (
                f"{cabeca}n = {self.validos}; {escolha.metodo} escrito na ficha "
                f"({estatistica}), contra a regra — ela escolheria {escolha.da_regra}"
                f"{faltou}: {escolha.motivo}."
            )
        return (
            f"{cabeca}n = {self.validos}; {escolha.metodo} escrito na ficha "
            f"({estatistica}), o mesmo que a regra escolheria: {escolha.motivo}."
        )

    def como_detalhe(self) -> dict[str, Any]:
        """
        Os números desta linha, para o manifesto — o que responde "de onde saiu esse
        teste, e esse p?" sem reabrir o banco.
        """
        resultado = self.resultado
        escolha = self.escolha
        normal = self.normal
        resumo = self.resumo or {}
        return {
            "delineamento": self.delineamento,
            "variavel": self.variavel,
            "referencia": self.referencia,
            "n": self.validos,
            "faltantes": self.faltantes,
            "distintos": self.distintos,
            "media": _arredondar(resumo.get("media")),
            "desvio": _arredondar(resumo.get("desvio")),
            "shapiro": (
                {
                    "w": _arredondar(normal.w),
                    "p": _significativos(normal.p),
                    "rejeita": normal.rejeita if normal.testada else None,
                    "impedimento": normal.impedimento or None,
                }
                if normal is not None
                else None
            ),
            "teste": resultado.metodo if resultado else None,
            "teste_da_regra": escolha.da_regra if escolha else None,
            "escrito_na_ficha": escolha.pela_ficha if escolha else None,
            "motivo_da_regra": escolha.motivo if escolha else None,
            "estatistica": (
                {
                    "nome": resultado.nome_da_estatistica,
                    "valor": _arredondar(resultado.estatistica),
                    "gl": [_arredondar(gl) for gl in resultado.gl],
                }
                if resultado
                else None
            ),
            "estimativa": (
                {"nome": resultado.nome_da_estimativa, "valor": _arredondar(resultado.estimativa)}
                if resultado
                else None
            ),
            "ic_95": (
                [_arredondar(resultado.ic[0]), _arredondar(resultado.ic[1])]
                if resultado and resultado.ic
                else None
            ),
            "p": _significativos(resultado.p) if resultado else None,
            "calculo_do_p": resultado.calculo_do_p if resultado else None,
            "motivo": self.motivo or None,
        }


@dataclass(frozen=True)
class ForaDaComparacao:
    """
    Uma variável do dicionário que não está em item nenhum, e por quê.
    """

    variavel: str
    tipo: str
    motivo: str


@dataclass(frozen=True)
class Comparacao:
    """
    A rodada inteira, decidida. É daqui que saem os arquivos e o terminal.
    """

    ficha: Ficha
    banco: Banco
    variaveis: tuple[VariavelComparada, ...]
    fora: tuple[ForaDaComparacao, ...]
    avisos: tuple[str, ...]
    quando: datetime
    tabela: Tabela

    @property
    def raiz(self) -> Path:
        return self.ficha.raiz

    @property
    def linhas(self) -> int:
        return self.banco.linhas

    @property
    def colunas_usadas(self) -> tuple[str, ...]:
        vistas: list[str] = []
        for variavel in self.variaveis:
            if variavel.variavel not in vistas:
                vistas.append(variavel.variavel)
        return tuple(vistas)

    @property
    def testadas(self) -> tuple[VariavelComparada, ...]:
        return tuple(v for v in self.variaveis if v.testada)

    @property
    def sem_teste(self) -> tuple[VariavelComparada, ...]:
        return tuple(v for v in self.variaveis if not v.testada)

    @property
    def pela_ficha(self) -> tuple[VariavelComparada, ...]:
        return tuple(v for v in self.variaveis if v.escolha and v.escolha.pela_ficha)

    def quantos(self, metodo: str) -> int:
        return sum(1 for v in self.variaveis if v.metodo == metodo)


@dataclass(frozen=True)
class PlanoComparacao:
    """
    Tudo o que a `comparacao` faria, decidido e ainda não escrito.

    Imutável como os planos das outras fases, e pela mesma razão: entre a simulação e
    a execução ninguém altera um caminho em trânsito.
    """

    comparacao: Comparacao
    pasta: Path
    arquivamento: tuple[Path, Path] | None
    manifesto: Manifesto
    texto_manifesto: str

    @property
    def raiz(self) -> Path:
        return self.comparacao.raiz

    @property
    def tabela(self) -> Tabela:
        return self.comparacao.tabela

    @property
    def arquivos(self) -> tuple[str, ...]:
        return (self.tabela.nome, ARQUIVO_MANIFESTO)


@dataclass(frozen=True)
class ResultadoComparacao:
    """
    O que a execução de fato escreveu.
    """

    criados: tuple[Path, ...] = ()
    arquivado: tuple[Path, Path] | None = None
    avisos: tuple[str, ...] = ()


# Casos de uso


def preparar_comparacao(
    raiz: Path,
    aba: str | None = None,
    conferir: bool = True,
    agora: datetime | None = None,
) -> PlanoComparacao:
    """
    Lê os itens da ficha, abre o banco, compara cada variável e monta o plano. Não
    escreve nada.

    A lista da ficha é conferida **antes** de abrir o banco, como na correlação: um
    item escrito fora do formato — a vírgula decimal, principalmente — é o engano
    mais provável deste comando, e descobri-lo não deve custar a releitura do
    `sha256` de um banco grande.

    Args:
        raiz: a pasta do projeto (a que tem o `projeto.yaml`).
        aba: planilha do `.xlsx`, quando houver mais de uma.
        conferir: reler o `sha256` das versões e comparar com a ficha.
        agora: relógio injetável, como nas outras fases.

    Raises:
        FichaError, BancoError, DicionarioInvalidoError e as recusas declaradas
        acima.
    """
    raiz = Path(raiz)
    quando = agora or datetime.now()

    pedidos = itens_da_ficha(raiz)

    banco = abrir(raiz, aba=aba, conferir=conferir)
    ficha = ler_ficha(raiz)
    linhas = conferir_dicionario(
        raiz,
        banco,
        ausente=DicionarioAusenteError,
        desatualizado=DicionarioDesatualizadoError,
        analise="a comparação",
    )
    comparacao = comparar(banco, ficha, linhas, pedidos, quando)

    pasta = pasta_da_analise(raiz, PASTA_COMPARACAO)
    manifesto = montar_manifesto(comparacao, linhas)

    return PlanoComparacao(
        comparacao=comparacao,
        pasta=pasta,
        arquivamento=arquivamento_da_rodada(raiz, pasta, quando, PASTA_COMPARACAO),
        manifesto=manifesto,
        texto_manifesto=texto_do_manifesto(manifesto),
    )


def executar_comparacao(plano: PlanoComparacao) -> ResultadoComparacao:
    """
    Escreve o plano no disco. Não decide mais nada.

    A ordem é a da Fase 5: arquiva a rodada anterior, cria a pasta, escreve a tabela,
    e só então o `manifesto.json` — o recibo vem depois do que ele descreve. Uma
    falha no meio desfaz o que já foi feito, inclusive devolvendo a pasta arquivada ao
    lugar, e a exceção continua subindo inteira.
    """
    criados: list[Path] = []
    avisos: list[str] = []
    desfazer: list[Any] = []
    arquivado: tuple[Path, Path] | None = None

    try:
        if plano.arquivamento is not None:
            de, para = plano.arquivamento
            para.parent.mkdir(parents=True, exist_ok=True)
            de.rename(para)
            arquivado = (de, para)
            desfazer.append(lambda d=de, p=para: p.rename(d))

        # `existia` antes do `mkdir`: a pasta só entra no desfazer quando foi este
        # comando que a criou, e o `rmdir` é registrado antes dos arquivos — o
        # desfazer roda ao contrário e a pasta sai vazia, a única forma de sair.
        existia = plano.pasta.is_dir()
        plano.pasta.mkdir(parents=True, exist_ok=True)
        criados.append(plano.pasta)
        if not existia:
            desfazer.append(lambda p=plano.pasta: p.rmdir())

        caminho = plano.pasta / plano.tabela.nome
        escrever_atomico(caminho, plano.tabela.texto())
        criados.append(caminho)
        desfazer.append(lambda p=caminho: p.unlink(missing_ok=True))

        caminho = plano.pasta / ARQUIVO_MANIFESTO
        escrever_atomico(caminho, plano.texto_manifesto)
        criados.append(caminho)
        desfazer.append(lambda p=caminho: p.unlink(missing_ok=True))

        try:
            anotar(plano.raiz, _acao_do_historico(plano), plano.comparacao.quando)
        except OSError as erro:
            avisos.append(
                "A comparação foi escrita, mas não consegui escrever no "
                f"historico.md: {erro}"
            )

    except Exception:
        for passo in reversed(desfazer):
            try:
                passo()
            except OSError:
                avisos.append(
                    "Falhei ao desfazer uma etapa. Confira "
                    f"{PASTA_ANALISES}/{PASTA_COMPARACAO} e {PASTA_ANTIGAS} antes "
                    "de rodar de novo."
                )
        raise

    return ResultadoComparacao(
        criados=tuple(criados), arquivado=arquivado, avisos=tuple(avisos)
    )


def comparar(
    banco: Banco,
    ficha: Ficha,
    linhas_do_dicionario: Sequence[Linha],
    pedidos: Sequence[Pedido | tuple[Any, ...]],
    quando: datetime | None = None,
) -> Comparacao:
    """
    Compara cada item pedido, obedecendo ao dicionário. Função pura.

    O miolo testável, como o `correlacionar` da correlação e o `avaliar` da
    normalidade: um `DataFrame` montado à mão, uma lista de `Linha` e os itens
    entram, e as afirmações são sobre a tabela — sem pasta de projeto e sem disco.

    Args:
        pedidos: os itens como `itens_da_ficha` os devolve — ou tuplas de nome e
            referência, com o método como terceiro elemento quando houver, que é como
            um teste os escreve.

    Raises:
        SemItensError, ItemInvalidoError, VariavelIncompativelError
    """
    quadro = banco.quadro
    total = int(quadro.shape[0])

    if not pedidos:
        raise SemItensError(_mensagem_sem_itens(linhas_do_dicionario))

    perguntas = _conferir_itens(
        [_como_pedido(item) for item in pedidos], linhas_do_dicionario
    )

    # Só as variáveis da lista vão para a recusa: a conferência é a da Fase 5, e o
    # escopo é deste comando.
    envolvidas: list[Linha] = []
    for pergunta in perguntas:
        if pergunta.linha not in envolvidas:
            envolvidas.append(pergunta.linha)
    recusar_incompativeis(quadro, envolvidas, erro=VariavelIncompativelError)

    variaveis = tuple(_comparar_uma_amostra(quadro, pergunta, total) for pergunta in perguntas)

    nas_perguntas = {variavel.variavel for variavel in variaveis}
    fora = tuple(
        ForaDaComparacao(linha.variavel, linha.tipo, _motivo_de_fora(linha))
        for linha in linhas_do_dicionario
        if linha.variavel not in nas_perguntas
    )

    avisos = list(banco.avisos)
    avisos += [aviso for variavel in variaveis for aviso in variavel.avisos]

    return Comparacao(
        ficha=ficha,
        banco=banco,
        variaveis=variaveis,
        fora=fora,
        avisos=tuple(avisos),
        quando=quando or datetime.now(),
        tabela=_tabela(variaveis, total),
    )


# Uma variável, contra a referência


def _comparar_uma_amostra(
    quadro: pd.DataFrame, pergunta: Pergunta, total: int
) -> VariavelComparada:
    """
    Mede o pressuposto, aplica a regra (ou obedece à ficha) e calcula.

    Os faltantes são **por variável**: entram os valores preenchidos desta coluna, e o
    `n` da linha é quantos são. É o mesmo tratamento da normalidade e da descritiva, e
    é o que faz a média daqui ser a do `resumo` e o p do Shapiro-Wilk ser o da tabela
    de normalidade.

    Três barreiras vêm antes da regra, e as três deixam a linha sem teste qualquer que
    seja o método escrito na ficha — são as do próprio `t.test` do R: nenhum valor,
    um valor só, e valores que não variam.
    """
    linha = pergunta.linha
    serie = _coluna(quadro, linha.variavel)
    if serie is None:  # pragma: no cover - `recusar_incompativeis` já barrou
        raise VariavelIncompativelError(f"`{linha.variavel}` não existe no banco.")

    valores = serie.dropna().astype("float64")
    validos = int(valores.shape[0])
    base: dict[str, Any] = {
        "variavel": linha.variavel,
        "rotulo": _rotulo(linha),
        "referencia": pergunta.referencia,
        "total": total,
        "validos": validos,
        "distintos": int(valores.nunique()),
        "delineamento": pergunta.delineamento,
        "resumo": resumo_numerico(valores) if validos else None,
    }
    nome = f"`{linha.variavel}`"

    impedimento = _impedimento(valores, validos, base["distintos"])
    if impedimento:
        aviso = f"{nome}: {impedimento}. A linha saiu sem teste."
        if base["distintos"] == 1:
            aviso += " Uma variável que não varia costuma ser critério de inclusão do estudo."
        return VariavelComparada(**base, motivo=impedimento, avisos=(aviso,))

    normal = _normal(linha.variavel, valores)
    escolha = regra(pergunta.delineamento, normal)
    if pergunta.metodo:
        escolha = replace(escolha, metodo=pergunta.metodo, pela_ficha=True)

    avisos = _avisos_da_linha(nome, pergunta, escolha, normal, validos, base["distintos"])

    if not escolha.metodo:
        return VariavelComparada(
            **base,
            normal=normal,
            escolha=escolha,
            motivo=_motivo_sem_teste(normal, validos),
            avisos=avisos,
        )

    calcular = _CALCULO[(pergunta.delineamento, escolha.metodo)]
    return VariavelComparada(
        **base,
        normal=normal,
        escolha=escolha,
        resultado=calcular(valores.to_numpy(), pergunta.referencia),
        avisos=avisos,
    )


def _impedimento(valores: pd.Series, validos: int, distintos: int) -> str:
    """
    O motivo de não haver teste nenhum, ou vazio.

    As barreiras do `t.test`, com a frase de cada uma no lugar do `stop()` do R. A
    terceira usa o critério do R, e não "todos iguais": ver `hipoteses.sem_variacao`.
    """
    if not validos:
        return "nenhum valor preenchido"
    if validos < MINIMO_T:
        return f"{validos} valor — o teste precisa de pelo menos {MINIMO_T}"
    if sem_variacao(valores.to_numpy()):
        if distintos < 2:
            return "um valor só em todas as linhas"
        return "os valores praticamente não variam"
    return ""


def _normal(variavel: str, valores: pd.Series) -> Normal:
    """
    O Shapiro-Wilk da normalidade, pela mesma função, sobre os valores preenchidos.
    """
    w, p, impedimento, aviso = shapiro(variavel, valores, int(valores.shape[0]))
    return Normal(w=w, p=p, impedimento=impedimento, aviso=aviso)


def _motivo_sem_teste(normal: Normal, validos: int) -> str:
    """
    O motivo curto, para a célula da coluna `teste`, quando a regra escolheu um teste
    que ainda não existe. A frase inteira, com o p do Shapiro-Wilk, vai para as notas.

    **Sem o p na célula**, e foi a página que decidiu: na coluna estreita do documento
    `(p < 0,001)` quebrava entre o `<` e o número, e a célula ocupava quatro linhas
    para repetir o que a tabela de normalidade do mesmo documento já imprime.
    """
    if normal.testada:
        return "normal rejeitada"
    return f"normalidade não verificável com {validos} valores"


def _avisos_da_linha(
    nome: str,
    pergunta: Pergunta,
    escolha: Escolha,
    normal: Normal,
    validos: int,
    distintos: int,
) -> tuple[str, ...]:
    """
    O que a escolha precisa levar junto para o terminal e para o manifesto.

    Cinco casos, e cada um é um engano conhecido ou uma decisão que precisa de rastro:

    * **a linha sem teste porque o teste da regra ainda não existe.** O aviso diz como
      escrever `t` no item, para quando você concluir que ele vale ali;
    * **a ficha contra a regra.** A decisão é sua, e o aviso é o registro de que ela
      foi tomada contra o que a regra diria;
    * **o t pela regra com poucos valores.** Abaixo de `MINIMO_CONFIAVEL` o
      Shapiro-Wilk quase não rejeita, e a regra escolheu o t por falta de evidência
      contra ele — não por evidência a favor;
    * **a variável discreta com a normal rejeitada.** Numa escala o Shapiro-Wilk
      rejeita quase sempre, e a rejeição diz «discreta», e não «forma errada»;
    * **o recado do `scipy` sobre o Shapiro-Wilk**, repassado como ele veio.
    """
    avisos: list[str] = []
    faltou = "" if _disponivel(pergunta.delineamento, escolha.da_regra) else (
        ", que ainda não está no FlatCap"
    )
    if not escolha.metodo:
        avisos.append(
            f"{nome}: {escolha.motivo} — a regra escolheria {escolha.da_regra}{faltou}, e "
            "a linha saiu sem teste. Se o t vale aqui — n grande e assimetria pequena, "
            "por exemplo —, escreva o método no item: "
            f"`{replace(_pedido_de(pergunta), metodo=T_DE_STUDENT).escrito}`."
        )
    if escolha.contra_a_regra:
        avisos.append(
            f"{nome}: {escolha.metodo} escrito na ficha, contra a regra — ela escolheria "
            f"{escolha.da_regra}{faltou}: {escolha.motivo}. Fica o que está na ficha, e a "
            "frase vai para as notas do .csv."
        )
    if (
        escolha.metodo == T_DE_STUDENT
        and not escolha.pela_ficha
        and validos < MINIMO_CONFIAVEL
    ):
        avisos.append(
            f"{nome}: t de Student com {validos} valores. Abaixo de {MINIMO_CONFIAVEL} o "
            "Shapiro-Wilk quase não rejeita — «não rejeitou» aí não é evidência de "
            "normalidade. Confira o histograma da descritiva e o Q-Q da normalidade "
            "antes de ficar com ele."
        )
    if normal.rejeita and distintos <= POUCOS_DISTINTOS and distintos < validos:
        avisos.append(
            f"{nome}: {distintos} valores distintos em {validos} casos. O Shapiro-Wilk "
            "supõe variável contínua e rejeita a normal quase sempre numa escala — a "
            "rejeição aí diz «esta variável é discreta», e não «a forma dela está "
            "errada»."
        )
    if normal.aviso and normal.aviso not in avisos:
        avisos.append(normal.aviso)
    return tuple(avisos)


# A regra


def regra(delineamento: str, normal: Normal) -> Escolha:
    """
    A regra dos pressupostos: o teste que ela escolhe, e o motivo.

    O Shapiro-Wilk não rejeitou → o paramétrico do delineamento. Rejeitou, ou não
    pôde ser verificado → o que dispensa a normal. Se esse ainda não tem aritmética,
    a `Escolha` sai com `metodo` vazio e `da_regra` preenchido: a linha fica sem teste,
    e a nota diz qual faltou.

    Não olha o método escrito na ficha: quem o aplica é o `_comparar_uma_amostra`, por
    cima do que a regra devolveu — e é assim que a nota consegue dizer o que a regra
    teria escolhido.
    """
    parametrico, sem_normal = REGRA[delineamento]
    if not normal.testada:
        return _pela_regra(
            delineamento,
            sem_normal,
            f"a normalidade não pôde ser verificada ({normal.impedimento})",
        )
    if normal.rejeita:
        return _pela_regra(
            delineamento,
            sem_normal,
            f"o Shapiro-Wilk rejeita a normal ({_p_na_frase(normal.p)})",
        )
    return _pela_regra(
        delineamento,
        parametrico,
        f"o Shapiro-Wilk não rejeita a normal ({_p_na_frase(normal.p)})",
    )


def _pela_regra(delineamento: str, teste: str, motivo: str) -> Escolha:
    metodo = teste if _disponivel(delineamento, teste) else ""
    return Escolha(metodo=metodo, da_regra=teste, motivo=motivo)


def _disponivel(delineamento: str, teste: str) -> bool:
    return (delineamento, teste) in _CALCULO


# A tabela


def _tabela(variaveis: tuple[VariavelComparada, ...], total: int) -> Tabela:
    """
    Uma tabela só, com uma linha por item, na ordem da ficha.

    As sete colunas — `variável`, `n`, `média (DP)`, `IC 95% da média`, `referência`,
    `teste` e `p-valor` —, com o **rótulo** do dicionário na primeira. O que decidiu
    cada teste — o p do Shapiro-Wilk, a estatística e os graus de liberdade — vai para
    as notas do `.csv`, uma frase por linha, e para o manifesto.
    """
    corpo = tuple(
        (
            variavel.rotulo,
            str(variavel.validos),
            _media_e_desvio(variavel.resumo),
            _intervalo(variavel.resultado.ic if variavel.resultado else None),
            _referencia_em_texto(variavel.referencia),
            variavel.celula_do_teste,
            valor_p(variavel.resultado.p if variavel.resultado else None),
        )
        for variavel in variaveis
    )
    menor_p = numero(MENOR_P, 3)
    notas = (
        "t de Student para uma amostra, bilateral, como o t.test do R: "
        "t = (média − referência) / (DP / √n), com n − 1 graus de liberdade; o IC 95% "
        "é o da média, com o quantil da mesma t.",
        "teste escolhido pela regra dos pressupostos: o t quando o Shapiro-Wilk não "
        f"rejeita a normal (p ≥ {numero(ALFA)}) sobre os valores preenchidos da "
        "variável; quando rejeita, ou quando a normalidade não pode ser verificada, a "
        f"regra escolhe o {WILCOXON}, que ainda não está no FlatCap, e a linha sai sem "
        "teste. O método escrito na ficha tem precedência sobre a regra.",
        "média e desvio padrão calculados como no resumo da descritiva; n: valores "
        f"preenchidos, de {total} linhas do banco — os faltantes são por variável.",
        "a referência é o valor escrito na ficha, na unidade da variável.",
        f"valor-p abaixo de {menor_p} sai como `< {menor_p}`; ele nunca é zero.",
        "cada linha é um teste; não há correção para comparações múltiplas.",
    ) + tuple(variavel.justificativa for variavel in variaveis)

    return Tabela(
        nome=ARQUIVO_TABELA,
        especie=UMA_AMOSTRA,
        # Vazia de propósito: esta tabela fala de várias variáveis.
        variavel="",
        titulo="Comparação com valor de referência",
        colunas=(
            "variável",
            "n",
            "média (DP)",
            "IC 95% da média",
            "referência",
            "teste",
            "p-valor",
        ),
        linhas=corpo,
        notas=notas,
    )


# Os itens da ficha


def itens_da_ficha(raiz: Path) -> tuple[Pedido, ...]:
    """
    A lista `comparacao:` do `projeto.yaml`, conferida na forma.

    Um item é uma lista entre colchetes — a variável, a referência e, quando quiser
    escolher, o método:

        - [imc, 25]
        - [pas, 120, t]

    Devolve vazio quando a chave não existe ou está vazia — quem recusa isso é o
    `comparar`, que tem o dicionário na mão para escrever quais variáveis existem.
    Formato errado recusa em vez de ignorar: um item que o comando pulasse em silêncio
    é o pior dos dois mundos — você escreveu, e não valeu.

    Lida pelo `ficha.bloco`, e não abrindo o YAML aqui: o `ficha.py` é o único módulo
    do pacote que abre o `projeto.yaml`.

    Raises:
        ItemInvalidoError
    """
    bruto = bloco(raiz, PASTA_COMPARACAO)
    if bruto is None:
        return ()
    if not isinstance(bruto, list):
        raise ItemInvalidoError(
            f"A chave `{PASTA_COMPARACAO}:` do {ARQUIVO_PROJETO} deveria ser uma lista, "
            f"e é {_descrever_valor(bruto)}.\n\n"
            f"Escreva assim, um item por linha:\n\n{EXEMPLO_DA_FICHA}"
        )

    pedidos: list[Pedido] = []
    problemas: list[str] = []
    for posicao, item in enumerate(bruto, start=1):
        pedido, problema = _ler_item(item)
        if pedido is not None:
            pedidos.append(pedido)
        else:
            problemas.append(f"  {posicao}º item: {problema}")

    if problemas:
        raise ItemInvalidoError(
            f"A lista `{PASTA_COMPARACAO}:` do {ARQUIVO_PROJETO} tem "
            f"{len(problemas)} item(ns) fora do formato. Nada foi gerado.\n\n"
            + "\n".join(problemas)
            + f"\n\nEscreva assim, um item por linha:\n\n{EXEMPLO_DA_FICHA}\n\n"
            "O primeiro nome é a variável, como na coluna `variavel` do "
            f"{ARQUIVO_DICIONARIO}; o segundo é o valor de referência, com ponto "
            "decimal; o terceiro, quando vem, é o método — `t`. Sem ele, a regra dos "
            "pressupostos escolhe."
        )
    return tuple(pedidos)


def _ler_item(item: Any) -> tuple[Pedido | None, str]:
    """
    Um item da lista: o `Pedido`, ou a frase do que está errado nele.
    """
    if isinstance(item, dict) and item:
        chave, valor = next(iter(item.items()))
        if referencia_escrita(valor) is not None:
            return None, (
                f"`{chave}: {_descrever_solto(valor)}` — o valor de referência vai dentro "
                f"dos colchetes, junto do nome: `[{chave}, {_descrever_solto(valor)}]`."
            )
        return None, (
            f"`{chave}: {_descrever_solto(valor)}` — a forma com dois-pontos é a de uma "
            "variável contra várias, e ela chega com a comparação entre grupos. Por "
            "enquanto, um item por linha: `[imc, 25]`."
        )
    if not isinstance(item, list):
        return None, (
            f"{_descrever_valor(item)} — um item se escreve entre colchetes, com a "
            "variável e o valor de referência: `[imc, 25]`."
        )

    escrito = _descrever_valor(item)
    if not item:
        return None, f"{escrito} — lista vazia; um item tem a variável e a referência."

    nome = _nome(item[0])
    if not nome:
        if referencia_escrita(item[0]) is not None and len(item) >= 2 and _nome(item[1]):
            return None, (
                f"{escrito} — a variável vem primeiro e a referência depois: "
                f"`[{_nome(item[1])}, {_descrever_solto(item[0])}]`."
            )
        return None, f"{escrito} — o primeiro item é o nome da variável."

    if len(item) == 1:
        return None, f"{escrito} — falta o valor de referência: `[{nome}, 25]`."

    partido = _numero_partido(item)
    if partido is not None:
        com_ponto, sem_sinal = partido
        metodo = f", {_nome(item[3])}" if len(item) == 4 else ""
        sinal = (
            f" — ou `-{com_ponto}`, se ele era negativo: o sinal de um zero se perde na "
            "leitura"
            if sem_sinal
            else ""
        )
        return None, (
            f"{escrito} — a referência foi lida como dois itens, `{item[1]}` e "
            f"`{_digitos(item[2])}`: numa lista entre colchetes a vírgula separa os "
            f"itens, e a vírgula decimal partiu o número. Escreva `[{nome}, {com_ponto}"
            f'{metodo}]` ou `[{nome}, "{com_ponto.replace(".", ",")}"{metodo}]`{sinal}.'
        )

    referencia = referencia_escrita(item[1])
    if referencia is None:
        segundo = _descrever_solto(item[1])
        if isinstance(item[1], str) and any(caractere.isdigit() for caractere in item[1]):
            return None, (
                f"{escrito} — `{segundo}` não é um número que se leia sem ambiguidade. "
                "Escreva sem separador de milhar e com ponto decimal, como `1234.5`."
            )
        if _nome(item[1]):
            return None, (
                f"{escrito} — `{segundo}` não é um número. Comparar a variável entre "
                f"grupos ou com outra variável, como `[{nome}, {segundo}]`, ainda não "
                "está no FlatCap; na comparação com um valor de referência, o segundo "
                f"item é o valor: `[{nome}, 25]`."
            )
        return None, f"{escrito} — `{segundo}` não é um número; a referência é um número."

    if len(item) == 2:
        return Pedido(nome, referencia), ""

    if len(item) > 3:
        return None, (
            f"{escrito} — {len(item)} itens; um item tem a variável, a referência e, "
            "quando quiser escolher, o método."
        )

    terceiro = _nome(item[2])
    metodo = metodo_escrito(terceiro)
    if metodo:
        return Pedido(nome, referencia, metodo), ""
    previsto = PREVISTOS.get(_simplificado(terceiro))
    if previsto:
        return None, (
            f"{escrito} — o {previsto} ainda não está no FlatCap; nesta versão o método "
            "que se escreve é `t`. Sem método, a regra escolhe — e, onde ela escolheria "
            f"o {previsto}, a linha sai sem teste, com o motivo."
        )
    return None, (
        f"{escrito} — `{_descrever_solto(item[2])}` não é um método. O terceiro item, "
        "quando vem, é o método: `t`."
    )


def metodo_escrito(texto: str) -> str:
    """
    O método como a tabela o escreve, a partir de como ele foi digitado na ficha;
    vazio quando o texto não é um método desta versão.

    Tolerante na leitura, como o da correlação: `T`, `t` e `Student` são o mesmo.
    """
    return METODOS.get(_simplificado(texto), "")


def referencia_escrita(valor: Any) -> float | None:
    """
    O valor de referência, a partir de como a ficha o trouxe; `None` quando não é um
    número.

    Número do YAML entra como está. Texto entra quando é um número escrito — com
    vírgula ou ponto decimal, e sem separador de milhar: é o `"24,9"` entre aspas que
    a recusa da vírgula decimal ensina a escrever. Lógico não é número, embora o
    Python ache que `True` vale 1.
    """
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int | float):
        numero_ = float(valor)
        return numero_ if math.isfinite(numero_) else None
    if isinstance(valor, str):
        limpo = valor.strip()
        if _NUMERO_ESCRITO.match(limpo):
            return float(limpo.replace(",", "."))
    return None


def _numero_partido(item: list[Any]) -> tuple[str, bool] | None:
    """
    O `[imc, 24,9]` que o YAML leu como `[imc, 24, 9]`: o número de volta, com ponto
    — `24.9` —, e se o sinal dele se perdeu; `None` quando o item não tem essa forma.

    A forma é um inteiro depois do nome, e depois dele os algarismos da parte decimal
    — e o que vier depois, quando vier, sendo um método: `[imc, 24,9, t]` é o mesmo
    engano. A recusa sugere o número para copiar, e por isso ele precisa sair
    **exato**: com o zero à esquerda da parte decimal (ver `_digitos`), e com o aviso
    de que o sinal de `-0,5` não sobrevive à leitura — o YAML lê `-0` e `0` como o
    mesmo inteiro.
    """
    if len(item) not in (3, 4) or not _inteiro(item[1]):
        return None
    fracao = _digitos(item[2])
    if not fracao:
        return None
    if len(item) == 4 and not metodo_escrito(_nome(item[3])):
        return None
    inteiro = int(item[1])
    return f"{inteiro}.{fracao}", inteiro == 0


def _digitos(valor: Any) -> str:
    """
    Os algarismos de um inteiro sem sinal como foram digitados — `05`, e não `5` —, ou
    vazio quando o valor não é um.

    O zero à esquerda é o que separa `24,05` de `24,5` quando a vírgula decimal parte o
    número, e a recusa não pode sugerir o número errado para copiar. O `ruamel` guarda
    a largura de um inteiro escrito com zero à esquerda no `_width` do `ScalarInt`, que
    o `ficha.bloco` deixa passar; sem ela, os algarismos são os do próprio número — e
    é o caso de todo inteiro escrito sem zero à esquerda. Um texto só de algarismos
    também serve: é como outra biblioteca de YAML leria o `09`.
    """
    if isinstance(valor, bool):
        return ""
    if isinstance(valor, int):
        if valor < 0:
            return ""
        largura = getattr(valor, "_width", None)
        if isinstance(largura, int) and largura > 0:
            return f"{int(valor):0{largura}d}"
        return str(int(valor))
    if isinstance(valor, str) and valor.strip().isdigit():
        return valor.strip()
    return ""


def _inteiro(valor: Any) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool)


def _como_pedido(item: Pedido | tuple[Any, ...]) -> Pedido:
    if isinstance(item, Pedido):
        return item
    variavel, referencia, *resto = item
    numero_ = referencia_escrita(referencia)
    if numero_ is None:
        raise ItemInvalidoError(f"`{referencia}` não é um valor de referência.")
    metodo = metodo_escrito(str(resto[0])) if resto else ""
    if resto and not metodo:
        raise ItemInvalidoError(f"`{resto[0]}` não é um método: t.")
    return Pedido(str(variavel), numero_, metodo)


def _pedido_de(pergunta: Pergunta) -> Pedido:
    return Pedido(pergunta.linha.variavel, pergunta.referencia, pergunta.metodo)


def _conferir_itens(pedidos: Sequence[Pedido], linhas: Sequence[Linha]) -> list[Pergunta]:
    """
    Confere cada item contra o dicionário, e recusa listando todos os problemas.

    Quatro coisas: o nome não está no dicionário; a variável está marcada `ignorar`
    ou fora desta versão do banco; ela não é numérica — a média de um código não é uma
    média, e uma data tem média, mas a comparação dela com uma referência não quer
    dizer nada —; o item repete outro, mesmo com outro método, que seria fazer a
    mesma comparação duas vezes e ficar com o p que convier.
    """
    por_nome = {linha.variavel: linha for linha in linhas}
    perguntas: list[Pergunta] = []
    problemas: list[str] = []
    vistos: dict[tuple[str, float], str] = {}

    for pedido in pedidos:
        chave = (pedido.variavel, pedido.referencia)
        if chave in vistos:
            problemas.append(
                f"  {pedido.escrito} — repete {vistos[chave]}; a mesma comparação se faz "
                "uma vez, por um teste"
            )
            continue
        vistos[chave] = pedido.escrito

        motivo = _motivo_de_recusa(pedido.variavel, por_nome.get(pedido.variavel))
        if motivo:
            problemas.append(f"  {pedido.escrito} — {motivo}")
            continue

        perguntas.append(
            Pergunta(
                linha=por_nome[pedido.variavel],
                referencia=pedido.referencia,
                metodo=pedido.metodo,
            )
        )

    if problemas:
        raise ItemInvalidoError(
            f"A lista `{PASTA_COMPARACAO}:` do {ARQUIVO_PROJETO} tem {len(problemas)} "
            "item(ns) que não podem ser comparados. Nada foi gerado.\n\n"
            + "\n".join(problemas)
            + "\n\nA comparação com um valor de referência é sobre a média de uma "
            f"variável marcada `numerica` no {ARQUIVO_DICIONARIO}.\n\n"
            f"Corrija o nome na lista do {ARQUIVO_PROJETO} — ele é o da coluna "
            f"`variavel` do {ARQUIVO_DICIONARIO} —, ou o `tipo` no dicionário, e rode "
            "de novo."
        )
    return perguntas


def _motivo_de_recusa(nome: str, linha: Linha | None) -> str:
    if linha is None:
        return f"`{nome}` não está no {ARQUIVO_DICIONARIO}"
    if not linha.no_banco:
        return f"`{nome}` não está nesta versão do banco (`no_banco = nao`)"
    if linha.tipo == IGNORAR:
        return f"`{nome}` está marcada `ignorar` no {ARQUIVO_DICIONARIO}"
    if linha.tipo == CATEGORICA:
        return (
            f"`{nome}` está marcada `categorica` no {ARQUIVO_DICIONARIO} — a média de um "
            "código não é uma média"
        )
    if linha.tipo != NUMERICA:
        return f"`{nome}` está marcada `{linha.tipo}` no {ARQUIVO_DICIONARIO}"
    return ""


# O manifesto


def montar_manifesto(comparacao: Comparacao, linhas: Sequence[Linha]) -> Manifesto:
    """
    Traduz a rodada para o índice que o relatório vai ler.

    **Um item só**, como na normalidade, na associação e na correlação: a seção do
    documento é uma tabela que fala de todas as variáveis da lista. O `colunas` do
    item diz quais colunas do banco entraram, que é o que mantém as conferências do
    relatório certas para uma seção que não é de uma variável. O que decidiu cada
    teste vai em `detalhes`, sob o nome do delineamento — é onde os próximos vão
    morar, cada um com a sua lista.
    """
    banco = comparacao.banco
    leitura = banco.leitura
    ficha = comparacao.ficha

    item = ItemDoManifesto(
        variavel="",
        slug=PASTA_COMPARACAO,
        rotulo="Comparação",
        tipo=ANALISE_COMPARACAO,
        n=banco.linhas,
        faltantes=0,
        colunas=comparacao.colunas_usadas,
        artefatos=(
            Artefato(
                arquivo=comparacao.tabela.nome,
                especie=comparacao.tabela.especie,
                formato="csv",
                titulo=comparacao.tabela.titulo,
            ),
        ),
        detalhes={
            UMA_AMOSTRA: [variavel.como_detalhe() for variavel in comparacao.variaveis],
            "testadas": len(comparacao.testadas),
            "sem_teste": len(comparacao.sem_teste),
            "escritas_na_ficha": len(comparacao.pela_ficha),
        },
        avisos=tuple(aviso for variavel in comparacao.variaveis for aviso in variavel.avisos),
    )

    return Manifesto(
        analise=ANALISE_COMPARACAO,
        flatcap=__version__,
        gerado_em=comparacao.quando,
        projeto={
            "pasta": rotulo_do_projeto(ficha.raiz),
            "cliente": ficha.raiz.parent.name,
            "record_id": ficha.record_id,
            "matricula": ficha.matricula,
            "nome": ficha.nome,
            "tipo": ficha.tipo,
            "status": ficha.status,
        },
        banco={
            "arquivo": banco.versao.arquivo,
            "origem": banco.versao.origem,
            "sha256": banco.versao.sha256,
            "tamanho_bytes": banco.versao.tamanho_bytes,
            "linhas": banco.linhas,
            "colunas": banco.colunas,
            "planilha": leitura.aba,
            "separador": leitura.separador,
            "codificacao": leitura.codificacao,
            "integridade": _integridade(banco.confere),
        },
        dicionario={
            "arquivo": ARQUIVO_DICIONARIO,
            "variaveis": len(linhas),
            "analisaveis": sum(1 for linha in linhas if linha.analisavel),
            "numericas": sum(
                1 for linha in linhas if linha.analisavel and linha.tipo == NUMERICA
            ),
        },
        ambiente=_ambiente(),
        regras={
            "itens": f"os da lista `{PASTA_COMPARACAO}:` do {ARQUIVO_PROJETO}",
            "delineamentos": {
                UMA_AMOSTRA: "a média de uma numérica contra a referência escrita no item",
            },
            "escolha_do_teste": (
                "t de Student se o Shapiro-Wilk não rejeita a normal (p ≥ "
                f"{ALFA:g}) sobre os valores preenchidos; senão {WILCOXON}, que ainda "
                "não está no FlatCap — a linha sai sem teste. O método escrito na ficha "
                "tem precedência."
            ),
            "t_de_student": (
                "t.test do R: bilateral, t com n − 1 graus de liberdade, IC "
                f"{CONFIANCA:.0%} da média"
            ),
            "normalidade": "Shapiro-Wilk, pela mesma função da análise de normalidade",
            "alfa": ALFA,
            "minimo": MINIMO_T,
            "faltantes": "por variável",
            "hipotese": "bilateral",
            "comparacoes_multiplas": "nenhuma correção",
            "semente": SEMENTE,
        },
        itens=(item,),
        fora=tuple(
            {"variavel": f.variavel, "tipo": f.tipo, "motivo": f.motivo}
            for f in comparacao.fora
        ),
        avisos=comparacao.avisos,
    )


def _ambiente() -> dict[str, Any]:
    """
    As versões que produziram estes números.

    O `scipy` entra, porque o Shapiro-Wilk e a distribuição t são dele. O `matplotlib`
    e a `fonte` saem `None` — a rodada não desenha —, e as chaves continuam lá para o
    bloco ter a forma dos outros.
    """
    import openpyxl
    import scipy

    return {
        "python": ".".join(str(parte) for parte in sys.version_info[:3]),
        "flatcap": __version__,
        "pandas": pd.__version__,
        "openpyxl": openpyxl.__version__,
        "scipy": scipy.__version__,
        "matplotlib": None,
        "fonte": None,
    }


# Mensagens


def _mensagem_sem_itens(linhas: Sequence[Linha]) -> str:
    numericas = [
        linha.variavel for linha in linhas if linha.analisavel and linha.tipo == NUMERICA
    ]
    if numericas:
        disponiveis = (
            f"As numéricas deste {ARQUIVO_DICIONARIO} são: "
            + ", ".join(numericas[:20])
            + (f" e mais {len(numericas) - 20}" if len(numericas) > 20 else "")
            + "."
        )
    else:
        disponiveis = (
            f"Nenhuma variável deste {ARQUIVO_DICIONARIO} está marcada `numerica` ainda "
            "— reveja a coluna `tipo` antes."
        )
    return (
        f"O {ARQUIVO_PROJETO} deste projeto não diz o que comparar.\n\n"
        "Escreva a lista na ficha — a variável e o valor de referência entre colchetes, "
        f"com o método como terceiro item quando quiser escolhê-lo:\n\n{EXEMPLO_DA_FICHA}"
        f"\n\n{disponiveis}\n\n"
        "O que comparar, e contra qual valor, é decisão da reunião: a referência vem da "
        "literatura ou do protocolo, e o FlatCap não inventa uma."
    )


def _motivo_de_fora(linha: Linha) -> str:
    if not linha.no_banco:
        return "não está nesta versão do banco (`no_banco = nao`)"
    if linha.tipo == IGNORAR:
        return "marcada `ignorar` no dicionário"
    return f"não está em nenhum item da lista `{PASTA_COMPARACAO}:` do {ARQUIVO_PROJETO}"


def _acao_do_historico(plano: PlanoComparacao) -> str:
    comparacao = plano.comparacao
    contagem = [
        (comparacao.quantos(T_DE_STUDENT), f"com o {T_DE_STUDENT}"),
        (len(comparacao.sem_teste), "sem teste"),
    ]
    resumo = ", ".join(f"{quantos} {nome}" for quantos, nome in contagem if quantos)
    partes = [
        f"`flatcap comparacao {comparacao.ficha.record_id}` — comparação de "
        f"`{comparacao.banco.versao.arquivo}`: {len(comparacao.variaveis)} item(ns) da "
        f"lista `{PASTA_COMPARACAO}:`"
        + (f" ({resumo})" if resumo else "")
        + f", em `{PASTA_ANALISES}/{PASTA_COMPARACAO}/`."
    ]
    if comparacao.pela_ficha:
        partes.append(f"{len(comparacao.pela_ficha)} com o método escrito na ficha.")
    if plano.arquivamento is not None:
        partes.append(
            f"A rodada anterior foi para `{PASTA_ANTIGAS}/{plano.arquivamento[1].name}/`."
        )
    return " ".join(partes)


# Leitura da série e formatação


def _coluna(quadro: pd.DataFrame, nome: str) -> pd.Series | None:
    """
    A coluna do banco pelo nome, ou `None` — pela posição, como nas outras análises:
    nome repetido devolveria um `DataFrame` no lugar de uma coluna.
    """
    for posicao, coluna in enumerate(quadro.columns):
        if str(coluna) == nome:
            return quadro.iloc[:, posicao]
    return None


def _rotulo(linha: Linha) -> str:
    return linha.rotulo or linha.variavel


def _nome(valor: Any) -> str:
    """
    Um nome, como a ficha o trouxe; vazio quando não é um nome.

    Número não é nome: é a referência escrita no lugar errado. Lista e bloco dentro
    da lista também não — é o `[[imc, 25]]` digitado com um colchete a mais.
    """
    if valor is None or isinstance(valor, list | dict | bool | int | float):
        return ""
    return str(valor).strip()


def _simplificado(texto: str) -> str:
    limpo = unicodedata.normalize("NFKD", str(texto or "")).lower().strip()
    return "".join(c for c in limpo if not unicodedata.combining(c))


def _como_se_escreve(metodo: str) -> str:
    """O método de volta como se digita na ficha: `t de Student` → `t`."""
    for escrito, nome in METODOS.items():
        if nome == metodo:
            return escrito
    return metodo


def _p_na_frase(p: float | None) -> str:
    """
    O p dentro de uma frase: `p = 0,412`, ou `p < 0,001` — nunca `p = < 0,001`.
    """
    texto = valor_p(p)
    return f"p {texto}" if texto.startswith("<") else f"p = {texto}"


def _estatistica_em_texto(resultado: Resultado) -> str:
    texto = f"{resultado.nome_da_estatistica} = {numero(resultado.estatistica, 2)}"
    if resultado.gl:
        texto += "; " + " e ".join(numero(gl, 2) for gl in resultado.gl) + " gl"
    return texto


def _media_e_desvio(resumo: dict[str, float] | None) -> str:
    """
    `26,41 (4,12)` — a média e o desvio como o `resumo_<variável>.csv` os escreve,
    pelo mesmo `numero()`.
    """
    if not resumo:
        return _AUSENTE
    return f"{numero(resumo['media'])} ({numero(resumo['desvio'])})"


def _intervalo(intervalo: tuple[float, float] | None) -> str:
    if intervalo is None:
        return _AUSENTE
    baixo, alto = intervalo
    return f"{_fixo(baixo)} a {_fixo(alto)}"


def _fixo(valor: float) -> str:
    """
    Duas casas fixas, o hífen do teclado no negativo, e nunca `-0,00` — o formato do
    coeficiente da correlação: o Excel em português lê a célula como número, e um
    zero não tem direção.
    """
    texto = f"{valor:.{CASAS_IC}f}"
    if float(texto) == 0:
        texto = texto.lstrip("-")
    return texto.replace(".", ",")


def _referencia_em_texto(valor: float, ponto: bool = False) -> str:
    """
    A referência como foi escrita, sem os zeros do fim: `25`, `24,9`, `0,125`.

    Com `ponto`, a forma da ficha — `24.9` —, para as mensagens ensinarem a escrever
    o que funciona.
    """
    texto = numero(valor, CASAS_REFERENCIA)
    return texto.replace(",", ".") if ponto else texto


def _descrever_valor(valor: Any) -> str:
    if isinstance(valor, list):
        return "[" + ", ".join(_descrever_solto(item) for item in valor) + "]"
    if isinstance(valor, dict):
        return "um bloco `chave: valor`"
    if valor is None:
        return "vazio"
    if isinstance(valor, str):
        return f"`{valor}`"
    return f"`{valor}` ({type(valor).__name__})"


def _descrever_solto(valor: Any) -> str:
    """Um valor como ele apareceria dentro dos colchetes da ficha."""
    if isinstance(valor, list):
        return "[" + ", ".join(_descrever_solto(item) for item in valor) + "]"
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor)


def _arredondar(valor: float | None) -> float | None:
    if valor is None:
        return None
    valor = float(valor)
    return round(valor, 6) if math.isfinite(valor) else None


def _significativos(valor: float | None) -> float | None:
    """
    O p no manifesto, com seis algarismos significativos, e não seis casas — o da
    correlação. Com seis casas, um p de 2,5e-08 seria gravado como `0.0`.
    """
    if valor is None:
        return None
    valor = float(valor)
    return float(f"{valor:.6g}") if math.isfinite(valor) else None


def _integridade(confere: bool | None) -> str:
    if confere is True:
        return "confere"
    if confere is False:
        return "ALTERADO"
    return "não conferida"


__all__ = [
    "ARQUIVO_TABELA",
    "CASAS_IC",
    "CASAS_REFERENCIA",
    "EXEMPLO_DA_FICHA",
    "METODOS",
    "PREVISTOS",
    "REGRA",
    "UMA_AMOSTRA",
    "WILCOXON",
    "Comparacao",
    "ComparacaoError",
    "DicionarioAusenteError",
    "DicionarioDesatualizadoError",
    "Escolha",
    "ForaDaComparacao",
    "ItemInvalidoError",
    "Normal",
    "Pedido",
    "Pergunta",
    "PlanoComparacao",
    "ResultadoComparacao",
    "SemItensError",
    "VariavelComparada",
    "VariavelIncompativelError",
    "comparar",
    "executar_comparacao",
    "itens_da_ficha",
    "metodo_escrito",
    "montar_manifesto",
    "preparar_comparacao",
    "referencia_escrita",
    "regra",
]
