# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
"""
A caracterização dos participantes — a "Tabela 1" de um artigo: as variáveis escolhidas,
uma coluna por grupo, o Total e o p.

    Característica              Feminino (n = 104)  Masculino (n = 76)  Total (n = 180)  p-valor
    Idade (anos), média (DP)    58,5 (10,49)        62,24 (11,43)       60,08 (11,02)    0,026a
    Escolaridade, n (%)                                                                  0,146b
      Fundamental               39 (38,2)           38 (50,7)           77 (43,5)
      Médio                     41 (40,2)           20 (26,7)           61 (34,5)
      Superior                  22 (21,6)           17 (22,7)           39 (22,0)
      (sem informação)          2                   1                   3

    a t de Welch; b Qui-quadrado.
    Percentuais sobre os casos com resposta.

Segue o padrão das outras análises, decidir e escrever separados:

    plano = preparar_caracterizacao(raiz)   # abre o banco, calcula, não toca no disco
    executar_caracterizacao(plano)          # só escreve

E, como elas, **não fala com o REDCap**. Recebe `Path`, não `Config`.

## A ficha

    caracterizacao:
      - sexo: [idade, pas, imc, escolaridade]   # por sexo, com o p
      - por: grupo                              # todas as variáveis, por grupo
        p: nao                                  # sem o p
      - [idade, imc, sexo]                      # sem grupo: só o Total

**Uma tabela por item.** O grupo vem antes dos dois-pontos, como na comparação, e a
lista depois dele é a ordem das linhas. `por:` toma todas as variáveis analisáveis do
dicionário, na ordem dele, menos o grupo. Sem grupo, a tabela tem só a coluna Total e
nenhum p: é a tabela de um estudo descritivo. `p: nao` na linha de baixo do item tira a
coluna do p e a legenda dos testes — num ensaio randomizado, em que o CONSORT 2025
desaconselha testar a linha de base: lá a diferença entre os grupos é acaso, por
construção. `não`, `no` e `false` valem o mesmo, escritos como texto ou como booleano.

`por` e `p` são chaves da caracterização, e por isso o grupo não pode se chamar `por`
nem `p`: escrito assim, ele é lido como a chave.

## Sem conta nova

Cada linha é o que outra análise já faz, pela função dela:

* **a numérica é a comparação entre grupos** — o `comparacao.comparar_grupos`, sem
  método escrito: o Shapiro-Wilk em cada grupo; a média e o desvio, e o t de Welch (a
  ANOVA de Welch com três grupos ou mais), quando ele não rejeita a normal em nenhum; a
  mediana e os quartis, e o Mann-Whitney (o Kruskal-Wallis), quando rejeita em algum ou
  não pôde verificá-la. A forma vai no rótulo da linha — `Idade (anos), média (DP)` —, e
  o Total segue a forma da linha;
* **a categórica é a associação** — o `associacao.testar_par`, com o grupo como a
  variável 1: a regra de Cochran entre o qui-quadrado e o Fisher, a correção de Yates só
  na 2×2, e o Fisher que passa do limite do cálculo exato sem p.

O p de cada linha é, letra por letra, o que a comparação ou a associação dariam para o
mesmo par — há teste que confere isso. As células saem pelos formatadores delas: o
`comparacao.media_e_desvio` e o `mediana_e_quartis`, com as casas da coluna, que são as
do `resumo_<variável>.csv`; o `descritiva.percentual`; e o p pelo `normalidade.valor_p`.
Sem grupo, a forma da numérica sai do Shapiro-Wilk da variável inteira, pela mesma
`regra` da comparação.

**A regra dos pressupostos manda sempre**, mesmo quando a lista `comparacao:` escreve
outro método para o mesmo par: a Tabela 1 descreve, e a forma de cada linha é a que os
dados pedem. A nota do `.csv` diz isso.

## As colunas e os casos

Uma coluna por categoria do grupo com pelo menos um caso, na ordem do dicionário — a
`associacao.na_ordem_do_dicionario`: o código conta, o rótulo imprime —, com o n no
cabeçalho; depois o Total e o p. **Quem não tem o grupo fica fora da tabela inteira**, e
os grupos somam o Total: um Total com casos que nenhuma coluna mostra não fecharia. O
preço é o Total poder diferir do n da descritiva, e o aviso, a nota do `.csv` e o
manifesto dizem quantos casos ficaram fora.

Dentro de cada coluna, os faltantes de cada variável vão na linha `(sem informação)`, só
com o n, e só quando há. Os percentuais das categóricas são sobre os casos com resposta
naquela coluna; a categoria declarada no dicionário e sem caso sai `0 (0,0)` e fica fora
do teste, como na associação; o valor que o dicionário não declara entra no fim, com
aviso, como na descritiva.

## O p e as letras

O p sai com a letra do teste colada — `0,026a` —, e a legenda embaixo da tabela diz
qual teste é cada letra. As letras seguem a ordem em que cada teste aparece na tabela, e
a legenda lista só os que apareceram. A linha sem teste — uma barreira do teste, um
valor só, o Fisher além do limite do cálculo — sai com o traço, sem letra, e o motivo
vai para o aviso e para o manifesto.

## O que se escreve

`3. Análises/caracterizacao/caracterizacao_<grupo>.csv`, um por item —
`caracterizacao_geral.csv` sem grupo —, e o `manifesto.json`. O `.csv` tem as células
como no documento, com a letra do p simples e colada ao número, e nenhum espaço de
recuo: o recuo das categorias, a legenda e a página em paisagem — a tabela de três
grupos ou mais — são apresentação, e vão no artefato do manifesto (`recuo`, `rodape` e
`deitada`). No Excel o p com a letra vira texto; o p inteiro está no manifesto, com o
teste, a letra, a frase da escolha, o resumo e o Shapiro-Wilk de cada grupo, e a
contingência.

## As recusas

Como nas outras análises. O formato do item, antes de abrir o banco — e com ele o grupo
dentro da própria lista e a mesma variável duas vezes, que não precisam do dicionário.
Logo depois do dicionário conferido contra o banco, e antes de qualquer conta, a lista
vazia, o nome fora do dicionário, o grupo que não é `categorica` e a variável `ignorar`
ou com `no_banco = nao`. Com os casos contados, o grupo com uma categoria só. Cada leva
sai de uma vez, com o conserto escrito. A variável `data` não é recusa: vai para a lista
`fora`, com o motivo — a Tabela 1 descreve numéricas e categóricas.

## O que ficou decidido aqui

* **Sem o p, nenhum teste aparece.** A comparação calcula o teste dela de qualquer jeito
  — é a função dela, e a caracterização não a reescreve —, mas com `p: nao` o resultado
  fica de fora da tabela, das notas, do manifesto e dos avisos. Sobram os avisos do
  Shapiro-Wilk, que decidiu a forma.
* **O rodapé tem o que a tabela pede**: a legenda, quando algum teste rodou, e
  `Percentuais sobre os casos com resposta.`, quando a tabela tem categórica.
* **A coluna sem nenhuma resposta sai com o traço**, e não com `0 (—)`: não há o que
  descrever ali, e a linha `(sem informação)` diz quantos casos a coluna tem.
* **As categorias que o dicionário não declara** vêm depois das declaradas na ordem da
  associação, alfabética, e não na da frequência, da descritiva: a contingência que o
  manifesto guarda é a da associação, e as duas precisam ter a mesma ordem.
* **O item que não deixa linha nenhuma** — só datas, ou `por:` num dicionário em que só
  sobra o grupo — recusa: uma tabela vazia não diz nada.
"""

from __future__ import annotations

import sys
import unicodedata
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from . import __version__
from .associacao import (
    LIMITE_DO_CALCULO_EXATO,
    Par,
    contingencia,
    na_ordem_do_dicionario,
    testar_par,
)
from .banco import Banco, abrir
from .comparacao import (
    COLUNA_DA_MEDIA,
    COLUNA_DA_MEDIANA,
    GRUPOS,
    TESTES_DE_POSTOS,
    UMA_AMOSTRA,
    Normal,
    Pergunta,
    VariavelComparada,
    casas_da_coluna,
    comparar_grupos,
    de_postos,
    media_e_desvio,
    mediana_e_quartis,
    regra,
    resumo_no_manifesto,
    shapiro_no_manifesto,
)
from .descritiva import (
    ROTULO_FALTANTE,
    conferir_dicionario,
    escrever_rodada,
    numero,
    percentual,
    recusar_incompativeis,
    resumo_numerico,
    serie_de_texto,
    slug,
)
from .descritiva import arquivamento as arquivamento_da_rodada
from .dicionario import ARQUIVO_DICIONARIO, CATEGORICA, DATA, IGNORAR, NUMERICA, Linha
from .ficha import Ficha, bloco
from .ficha import ler as ler_ficha
from .manifesto import (
    ANALISE_CARACTERIZACAO,
    ARQUIVO_MANIFESTO,
    SEMENTE,
    Artefato,
    ItemDoManifesto,
    Manifesto,
    Tabela,
    texto_do_manifesto,
)
from .nomes import rotulo_do_projeto
from .normalidade import ALFA, MENOR_P, shapiro, valor_p
from .projeto import (
    ARQUIVO_PROJETO,
    PASTA_ANALISES,
    PASTA_ANTIGAS,
    PASTA_CARACTERIZACAO,
    pasta_da_analise,
)

# As duas chaves do item que não são o grupo: `por:` põe todas as variáveis do
# dicionário na tabela, e `p:` tira a coluna do p.
CHAVE_POR = "por"
CHAVE_P = "p"

# O que se escreve no `p:` para tirar o p, e para deixá-lo — sem acento e em minúsculas,
# como o `_simplificado` deixa o que se digitou. `no` e `false` chegam como texto e como
# booleano conforme a versão do YAML, e o booleano é lido antes.
_SEM_P = frozenset({"nao", "no", "false"})
_COM_P = frozenset({"sim", "yes", "true"})

# Os nomes do documento: a seção, a legenda e as colunas — os do exemplo da Tabela 1 de
# um artigo em português.
ROTULO_DA_SECAO = "Caracterização dos participantes"
TITULO = "Características dos participantes"
COLUNA_DA_CARACTERISTICA = "Característica"
COLUNA_DO_TOTAL = "Total"
COLUNA_DO_P = "p-valor"
FORMA_DA_CATEGORICA = "n (%)"
PERCENTUAIS = "Percentuais sobre os casos com resposta."

# O nome do arquivo da tabela sem grupo, no lugar do nome do grupo.
SEM_GRUPO = "geral"

# A partir de quantos grupos a tabela pede a página em paisagem: com três grupos, são
# seis colunas — a característica, os três, o Total e o p —, e a página em pé espremeria
# cada resumo em três linhas.
GRUPOS_PARA_DEITAR = 3

_LETRAS = "abcdefghijklmnopqrstuvwxyz"
_AUSENTE = "—"

# O exemplo que as mensagens escrevem. Um lugar só, para a recusa e o `--help` nunca
# ensinarem duas formas diferentes de escrever a mesma lista.
EXEMPLO_DA_FICHA = f"""  {PASTA_CARACTERIZACAO}:
    - sexo: [idade, imc, escolaridade]
    - {CHAVE_POR}: sexo
      {CHAVE_P}: nao
    - [idade, imc, sexo]"""


class CaracterizacaoError(RuntimeError):
    """
    Falha ao gerar a caracterização, já traduzida para o usuário.

    Erro próprio pela regra da casa: a CLI captura esta classe e transforma em painel
    com o nome do comando que o usuário rodou. Qualquer outra exceção é bug de verdade
    e deve subir com o traceback inteiro.
    """


class DicionarioAusenteError(CaracterizacaoError):
    """
    O projeto não tem `dicionario.csv`. Não há o que obedecer.
    """


class DicionarioDesatualizadoError(CaracterizacaoError):
    """
    O banco tem colunas que o dicionário desconhece.
    """


class VariavelIncompativelError(CaracterizacaoError):
    """
    O dicionário promete `numerica` e a coluna chegou como texto, ou declara uma
    variável que o banco não tem.

    A mesma recusa da descritiva, pela mesma função, aplicada só às variáveis das tabelas.
    """


class SemItensError(CaracterizacaoError):
    """
    A ficha não diz o que caracterizar.
    """


class ItemInvalidoError(CaracterizacaoError):
    """
    A lista `caracterizacao:` da ficha tem item que não serve.

    Formato errado, o grupo dentro da própria lista, a mesma variável duas vezes, nome
    fora do dicionário, grupo que não é categórica, variável fora da análise — ou, já
    com os casos contados, o grupo com uma categoria só. A mensagem lista **todos** de
    uma vez, pela regra da Fase 5.
    """


# Os itens


@dataclass(frozen=True)
class Pedido:
    """
    Um item como a ficha o escreve, antes do dicionário: o grupo — vazio na tabela sem
    grupo —, as variáveis na ordem da lista, ou `todas`, no `por:`, e se a tabela sai com
    o p.
    """

    grupo: str = ""
    variaveis: tuple[str, ...] = ()
    todas: bool = False
    com_p: bool = True

    @property
    def escrito(self) -> str:
        """O item de volta na forma da ficha, para as mensagens."""
        if self.todas:
            texto = f"{CHAVE_POR}: {self.grupo}"
        elif self.grupo:
            texto = f"{self.grupo}: [{', '.join(self.variaveis)}]"
        else:
            return f"[{', '.join(self.variaveis)}]"
        return texto if self.com_p else f"{{{texto}, {CHAVE_P}: nao}}"


@dataclass(frozen=True)
class Item:
    """
    Um item conferido contra o dicionário: a linha do grupo, as das variáveis da tabela,
    na ordem, e as datas que ele pediu e que ficam de fora.
    """

    pedido: Pedido
    grupo: Linha | None
    linhas: tuple[Linha, ...]
    datas: tuple[Linha, ...] = ()


# O que sai no disco


@dataclass(frozen=True)
class Coluna:
    """Uma categoria do grupo, que é uma coluna da tabela: o rótulo e quantos casos."""

    rotulo: str
    n: int

    @property
    def cabecalho(self) -> str:
        return f"{self.rotulo} (n = {self.n})"


@dataclass(frozen=True)
class Caracteristica:
    """
    Uma variável da tabela: as linhas dela — a da variável, as categorias embaixo, e a
    `(sem informação)` —, sem a coluna do p, que leva a letra, e a letra é da tabela.

    `p` fica `None` quando a linha não tem teste, com o motivo em `motivo`, e quando a
    tabela não leva o p. `teste` diz o teste mesmo sem o p quando ele foi escolhido e não
    pôde ser calculado — o Fisher além do limite.
    """

    variavel: str
    rotulo: str
    tipo: str
    forma: str
    validos: int
    faltantes: int
    linhas: tuple[tuple[str, ...], ...]
    teste: str = ""
    p: float | None = None
    escolha: str = ""
    motivo: str = ""
    avisos: tuple[str, ...] = ()
    # O resto do que vai para o manifesto: o resumo e o Shapiro-Wilk de cada grupo nas
    # numéricas, as categorias e a contingência nas categóricas.
    detalhe: dict[str, Any] = field(default_factory=dict)

    @property
    def testada(self) -> bool:
        return self.p is not None


@dataclass(frozen=True)
class TabelaCaracterizada:
    """
    Uma tabela, decidida: o item, os grupos que viraram colunas, e as variáveis. É dela
    que saem o `.csv`, o artefato do manifesto e a tabela do terminal.

    `n` é quantos casos estão na tabela — os que têm o grupo —, e `fora_do_grupo`,
    quantos ficaram de fora por não tê-lo.
    """

    pedido: Pedido
    grupo: Linha | None
    colunas: tuple[Coluna, ...]
    n: int
    fora_do_grupo: int
    caracteristicas: tuple[Caracteristica, ...]
    arquivo: str
    datas: tuple[Linha, ...] = ()
    avisos: tuple[str, ...] = ()

    @property
    def com_p(self) -> bool:
        return self.grupo is not None and self.pedido.com_p

    @property
    def deitada(self) -> bool:
        return len(self.colunas) >= GRUPOS_PARA_DEITAR

    @property
    def rotulo_do_grupo(self) -> str:
        return _rotulo(self.grupo) if self.grupo is not None else ""

    @property
    def titulo(self) -> str:
        """`Características dos participantes, por Sexo` — o rótulo como no dicionário."""
        return f"{TITULO}, por {self.rotulo_do_grupo}" if self.grupo is not None else TITULO

    @property
    def colunas_usadas(self) -> tuple[str, ...]:
        grupo = (self.grupo.variavel,) if self.grupo is not None else ()
        return (*grupo, *(caracteristica.variavel for caracteristica in self.caracteristicas))

    @property
    def cabecalho(self) -> tuple[str, ...]:
        return (
            COLUNA_DA_CARACTERISTICA,
            *(coluna.cabecalho for coluna in self.colunas),
            f"{COLUNA_DO_TOTAL} (n = {self.n})",
            *((COLUNA_DO_P,) if self.com_p else ()),
        )

    @property
    def letras(self) -> dict[str, str]:
        """O teste e a letra dele, na ordem em que cada teste aparece na tabela."""
        letras: dict[str, str] = {}
        if self.com_p:
            for caracteristica in self.caracteristicas:
                if caracteristica.testada and caracteristica.teste not in letras:
                    letras[caracteristica.teste] = _LETRAS[len(letras)]
        return letras

    def letra(self, caracteristica: Caracteristica) -> str:
        """A letra do teste da linha, ou vazio quando ela não tem p."""
        if not (self.com_p and caracteristica.testada):
            return ""
        return self.letras[caracteristica.teste]

    def celula_do_p(self, caracteristica: Caracteristica) -> str:
        """`0,026a`: o p pelo `valor_p`, com a letra do teste colada; sem teste, o traço."""
        if not caracteristica.testada:
            return _AUSENTE
        return f"{valor_p(caracteristica.p)}{self.letra(caracteristica)}"

    def linhas_de(self, caracteristica: Caracteristica) -> tuple[tuple[str, ...], ...]:
        """As linhas de uma variável, com o p na primeira quando a tabela o leva."""
        if not self.com_p:
            return caracteristica.linhas
        primeira, *resto = caracteristica.linhas
        return (
            (*primeira, self.celula_do_p(caracteristica)),
            *((*linha, "") for linha in resto),
        )

    @property
    def linhas(self) -> tuple[tuple[str, ...], ...]:
        return tuple(
            linha
            for caracteristica in self.caracteristicas
            for linha in self.linhas_de(caracteristica)
        )

    @property
    def recuo(self) -> tuple[int, ...]:
        """As linhas recuadas, a partir de zero: todas as de uma variável menos a primeira."""
        posicoes: list[int] = []
        inicio = 0
        for caracteristica in self.caracteristicas:
            posicoes += range(inicio + 1, inicio + len(caracteristica.linhas))
            inicio += len(caracteristica.linhas)
        return tuple(posicoes)

    @property
    def rodape(self) -> tuple[str, ...]:
        """
        O que sai embaixo da tabela: a legenda dos testes e a frase dos percentuais.

        A letra vem na frente do nome do teste, separada por um espaço, e os testes por
        `; ` — `a t de Welch; b Mann-Whitney.`: é a forma que o documento procura para
        pôr a letra sobrescrita.
        """
        linhas: list[str] = []
        if self.letras:
            linhas.append(
                "; ".join(f"{letra} {teste}" for teste, letra in self.letras.items()) + "."
            )
        if any(caracteristica.tipo == CATEGORICA for caracteristica in self.caracteristicas):
            linhas.append(PERCENTUAIS)
        return tuple(linhas)

    @property
    def notas(self) -> tuple[str, ...]:
        """
        As notas do `.csv`: os denominadores, as regras, o rodapé, e a frase da escolha
        de cada linha — as mesmas da comparação e da associação.
        """
        tipos = {caracteristica.tipo for caracteristica in self.caracteristicas}
        menor_p = numero(MENOR_P, 3)
        notas: list[str] = []
        if self.grupo is None:
            notas.append(
                f"sem grupo: só a coluna Total, sobre as {self.n} linhas do banco, e sem p."
            )
            onde = "sobre os valores preenchidos da variável"
        else:
            notas.append(
                f"uma coluna por categoria de {self.rotulo_do_grupo} com pelo menos um "
                "caso, na ordem do dicionário, com o n no cabeçalho; o Total é a soma delas."
            )
            if self.fora_do_grupo:
                notas.append(
                    f"{self.fora_do_grupo} caso(s) sem resposta em {self.rotulo_do_grupo} "
                    "ficaram fora da tabela inteira; por isso o Total pode diferir do n da "
                    "descritiva."
                )
            onde = "em nenhum grupo"
        if NUMERICA in tipos:
            notas.append(
                f"numéricas: {COLUNA_DA_MEDIA} quando o Shapiro-Wilk não rejeita a normal "
                f"(p ≥ {numero(ALFA)}) {onde}, e {COLUNA_DA_MEDIANA} quando rejeita ou não "
                "pode verificá-la — a regra da comparação; o Total segue a forma da linha."
            )
        if CATEGORICA in tipos:
            notas.append(
                f"categóricas: {FORMA_DA_CATEGORICA}, com o percentual sobre os casos com "
                "resposta na coluna; a categoria declarada no dicionário e sem caso sai com 0"
                + (" e fica fora do teste." if self.com_p else ".")
            )
        notas.append(
            f"{ROTULO_FALTANTE}: os casos sem resposta na variável, em cada coluna, só com "
            "o n, e só quando há."
        )
        if self.com_p:
            if NUMERICA in tipos:
                notas.append(
                    "p-valor das numéricas: o teste da comparação entre grupos — o t de "
                    "Welch ou o Mann-Whitney, a ANOVA de Welch ou o Kruskal-Wallis com três "
                    "grupos ou mais —, pela regra dos pressupostos, que manda mesmo quando "
                    "a lista `comparacao:` escreve outro método para o mesmo par."
                )
            if CATEGORICA in tipos:
                notas.append(
                    "p-valor das categóricas: o teste da associação, pela regra de Cochran — "
                    "o qui-quadrado, com a correção de Yates só na 2×2, ou o exato de Fisher."
                )
            notas.append(
                f"valor-p abaixo de {menor_p} sai como `< {menor_p}`; ele nunca é zero. A "
                "letra colada a ele é a do teste, na legenda."
            )
            notas.append("cada linha é um teste; não há correção para comparações múltiplas.")
        elif self.grupo is not None:
            notas.append(f"sem a coluna do p: `{CHAVE_P}: nao` no item da ficha.")
        notas += self.rodape
        notas += [c.escolha for c in self.caracteristicas if c.escolha]
        return tuple(notas)

    def tabela(self) -> Tabela:
        return Tabela(
            nome=self.arquivo,
            especie=ANALISE_CARACTERIZACAO,
            # Vazia de propósito: esta tabela fala de várias variáveis.
            variavel="",
            titulo=self.titulo,
            colunas=self.cabecalho,
            linhas=self.linhas,
            notas=self.notas,
        )

    def artefato(self) -> Artefato:
        return Artefato(
            arquivo=self.arquivo,
            especie=ANALISE_CARACTERIZACAO,
            formato="csv",
            titulo=self.titulo,
            recuo=self.recuo,
            rodape=self.rodape,
            deitada=self.deitada,
        )


@dataclass(frozen=True)
class ForaDaCaracterizacao:
    """
    Uma variável do dicionário que não está em tabela nenhuma, e por quê.
    """

    variavel: str
    tipo: str
    motivo: str


@dataclass(frozen=True)
class Caracterizacao:
    """
    A rodada inteira, decidida. É daqui que saem os arquivos e o terminal.
    """

    ficha: Ficha
    banco: Banco
    tabelas: tuple[TabelaCaracterizada, ...]
    fora: tuple[ForaDaCaracterizacao, ...]
    avisos: tuple[str, ...]
    quando: datetime

    @property
    def raiz(self) -> Path:
        return self.ficha.raiz

    @property
    def linhas(self) -> int:
        return self.banco.linhas

    @property
    def colunas_usadas(self) -> tuple[str, ...]:
        vistas: list[str] = []
        for tabela in self.tabelas:
            for coluna in tabela.colunas_usadas:
                if coluna not in vistas:
                    vistas.append(coluna)
        return tuple(vistas)

    @property
    def testadas(self) -> tuple[Caracteristica, ...]:
        """As linhas que saíram com p."""
        return tuple(
            caracteristica
            for tabela in self.tabelas
            if tabela.com_p
            for caracteristica in tabela.caracteristicas
            if caracteristica.testada
        )

    @property
    def sem_teste(self) -> tuple[Caracteristica, ...]:
        """As linhas que saíram com o traço numa tabela que leva o p."""
        return tuple(
            caracteristica
            for tabela in self.tabelas
            if tabela.com_p
            for caracteristica in tabela.caracteristicas
            if not caracteristica.testada
        )


@dataclass(frozen=True)
class PlanoCaracterizacao:
    """
    Tudo o que a `caracterizacao` faria, decidido e ainda não escrito.

    Imutável como os planos das outras fases, e pela mesma razão: entre a simulação e a
    execução ninguém altera um caminho em trânsito.
    """

    caracterizacao: Caracterizacao
    pasta: Path
    arquivamento: tuple[Path, Path] | None
    manifesto: Manifesto
    texto_manifesto: str

    @property
    def raiz(self) -> Path:
        return self.caracterizacao.raiz

    @property
    def tabelas(self) -> tuple[Tabela, ...]:
        return tuple(tabela.tabela() for tabela in self.caracterizacao.tabelas)

    @property
    def arquivos(self) -> tuple[str, ...]:
        return (
            *(tabela.arquivo for tabela in self.caracterizacao.tabelas),
            ARQUIVO_MANIFESTO,
        )


@dataclass(frozen=True)
class ResultadoCaracterizacao:
    """
    O que a execução de fato escreveu.
    """

    criados: tuple[Path, ...] = ()
    arquivado: tuple[Path, Path] | None = None
    avisos: tuple[str, ...] = ()


# Casos de uso


def preparar_caracterizacao(
    raiz: Path,
    aba: str | None = None,
    conferir: bool = True,
    agora: datetime | None = None,
) -> PlanoCaracterizacao:
    """
    Lê os itens da ficha, abre o banco, monta cada tabela e monta o plano. Não escreve
    nada.

    O formato dos itens é conferido **antes** de abrir o banco, como na comparação: um
    item fora do formato é o engano mais provável, e descobri-lo não deve custar a
    releitura do `sha256` de um banco grande.

    Args:
        raiz: a pasta do projeto (a que tem o `projeto.yaml`).
        aba: planilha do `.xlsx`, quando houver mais de uma.
        conferir: reler o `sha256` das versões e comparar com a ficha.
        agora: relógio injetável, como nas outras fases.

    Raises:
        FichaError, BancoError, DicionarioInvalidoError e as recusas declaradas acima.
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
        analise="a caracterização",
    )
    caracterizacao = caracterizar(banco, ficha, linhas, pedidos, quando)

    pasta = pasta_da_analise(raiz, PASTA_CARACTERIZACAO)
    manifesto = montar_manifesto(caracterizacao, linhas)

    return PlanoCaracterizacao(
        caracterizacao=caracterizacao,
        pasta=pasta,
        arquivamento=arquivamento_da_rodada(raiz, pasta, quando, PASTA_CARACTERIZACAO),
        manifesto=manifesto,
        texto_manifesto=texto_do_manifesto(manifesto),
    )


def executar_caracterizacao(plano: PlanoCaracterizacao) -> ResultadoCaracterizacao:
    """
    Escreve o plano no disco. Não decide mais nada: quem escreve, na ordem, e desfaz o
    que escreveu se falhar no meio, é o `descritiva.escrever_rodada`.
    """
    criados, arquivado, avisos = escrever_rodada(
        plano.raiz,
        plano.pasta,
        plano.arquivamento,
        plano.tabelas,
        (),
        plano.texto_manifesto,
        _acao_do_historico(plano),
        plano.caracterizacao.quando,
    )
    return ResultadoCaracterizacao(criados=criados, arquivado=arquivado, avisos=avisos)


def caracterizar(
    banco: Banco,
    ficha: Ficha,
    linhas_do_dicionario: Sequence[Linha],
    pedidos: Sequence[Pedido],
    quando: datetime | None = None,
    limite: int = LIMITE_DO_CALCULO_EXATO,
) -> Caracterizacao:
    """
    Monta cada tabela pedida, obedecendo ao dicionário. Função pura.

    O miolo testável, como o `comparar` da comparação e o `associar` da associação: um
    `DataFrame` montado à mão, uma lista de `Linha` e os pedidos entram, e as afirmações
    são sobre as tabelas — sem pasta de projeto e sem disco.

    Duas conferências: a dos itens contra o dicionário, antes de tocar nos valores, e a
    dos grupos contra o banco — quantas categorias o grupo tem entre os casos —, que só
    se faz com os valores na mão. As duas listam todos os problemas de uma vez.

    Args:
        limite: o `LIMITE_DO_CALCULO_EXATO` da associação, injetável para o teste que
            confere o Fisher que passa dele.

    Raises:
        SemItensError, ItemInvalidoError, VariavelIncompativelError
    """
    quadro = banco.quadro
    total = int(quadro.shape[0])

    if not pedidos:
        raise SemItensError(_mensagem_sem_itens(linhas_do_dicionario))

    itens = _conferir_itens(pedidos, linhas_do_dicionario)

    # Só as variáveis das tabelas vão para a recusa: a conferência é a da Fase 5, e o
    # escopo é deste comando. As datas ficam de fora — elas não entram na tabela.
    envolvidas: list[Linha] = []
    for item in itens:
        for linha in (*((item.grupo,) if item.grupo else ()), *item.linhas):
            if linha not in envolvidas:
                envolvidas.append(linha)
    recusar_incompativeis(quadro, envolvidas, erro=VariavelIncompativelError)

    usados: set[str] = set()
    tabelas: list[TabelaCaracterizada] = []
    problemas: list[str] = []
    for item in itens:
        tabela, problema = _caracterizar_item(quadro, item, total, limite, usados)
        if tabela is None:
            problemas.append(f"  {item.pedido.escrito} — {problema}")
        else:
            tabelas.append(tabela)

    if problemas:
        raise ItemInvalidoError(
            f"A lista `{PASTA_CARACTERIZACAO}:` do {ARQUIVO_PROJETO} tem {len(problemas)} "
            "item(ns) que este banco não deixa caracterizar. Nada foi gerado.\n\n"
            + "\n".join(problemas)
        )

    usadas = {coluna for tabela in tabelas for coluna in tabela.colunas_usadas}
    datas = {linha.variavel for tabela in tabelas for linha in tabela.datas}
    fora = tuple(
        ForaDaCaracterizacao(
            linha.variavel, linha.tipo, _motivo_de_fora(linha, linha.variavel in datas)
        )
        for linha in linhas_do_dicionario
        if linha.variavel not in usadas
    )

    avisos = list(banco.avisos)
    avisos += [aviso for tabela in tabelas for aviso in tabela.avisos]

    return Caracterizacao(
        ficha=ficha,
        banco=banco,
        tabelas=tuple(tabelas),
        fora=fora,
        avisos=tuple(avisos),
        quando=quando or datetime.now(),
    )


# Uma tabela


def _caracterizar_item(
    quadro: pd.DataFrame, item: Item, total: int, limite: int, usados: set[str]
) -> tuple[TabelaCaracterizada | None, str]:
    """
    As colunas do grupo e uma linha por variável. Devolve a tabela, ou `None` e a frase
    do que este banco não deixa caracterizar — o grupo com uma categoria só.

    **Quem não tem o grupo fica fora da tabela inteira**: a coluna Total é a soma das
    colunas dos grupos, e os testes já olham só os casos com as duas respostas.
    """
    grupo = item.grupo
    if grupo is None:
        no_grupo = pd.Series(True, index=quadro.index)
        colunas: tuple[Coluna, ...] = ()
    else:
        serie = _coluna(quadro, grupo.variavel)
        if serie is None:  # pragma: no cover - `recusar_incompativeis` já barrou
            raise VariavelIncompativelError(f"`{grupo.variavel}` não existe no banco.")
        no_grupo = serie.notna()
        rotulos = [grupo.rotulo_de(codigo) for codigo in serie_de_texto(serie[no_grupo])]
        contagem = Counter(rotulos)
        ordem = na_ordem_do_dicionario(set(rotulos), grupo)
        if len(ordem) < 2:
            return None, _motivo_de_um_grupo(grupo, ordem)
        colunas = tuple(Coluna(rotulo, contagem[rotulo]) for rotulo in ordem)

    n = int(no_grupo.sum())
    com_p = grupo is not None and item.pedido.com_p
    caracteristicas = tuple(
        _numerica(quadro, linha, grupo, colunas, no_grupo, n, com_p)
        if linha.tipo == NUMERICA
        else _categorica(quadro, linha, grupo, colunas, no_grupo, n, com_p, limite)
        for linha in item.linhas
    )

    avisos: list[str] = []
    fora_do_grupo = total - n
    if grupo is not None and fora_do_grupo:
        avisos.append(
            f"`{grupo.variavel}`: {fora_do_grupo} caso(s) sem resposta ficaram fora da "
            f"tabela da caracterização — os grupos somam o Total, e o Total ({n}) pode "
            f"diferir do n da descritiva, que conta as {total} linhas do banco."
        )
    avisos += [aviso for caracteristica in caracteristicas for aviso in caracteristica.avisos]

    nome = slug(grupo.variavel if grupo is not None else SEM_GRUPO, usados)
    return TabelaCaracterizada(
        pedido=item.pedido,
        grupo=grupo,
        colunas=colunas,
        n=n,
        fora_do_grupo=fora_do_grupo,
        caracteristicas=caracteristicas,
        arquivo=f"{PASTA_CARACTERIZACAO}_{nome}.csv",
        datas=item.datas,
        avisos=tuple(avisos),
    ), ""


def _numerica(
    quadro: pd.DataFrame,
    linha: Linha,
    grupo: Linha | None,
    colunas: tuple[Coluna, ...],
    no_grupo: pd.Series,
    n: int,
    com_p: bool,
) -> Caracteristica:
    """
    A linha de uma numérica: o resumo de cada grupo e do Total, na forma que a regra da
    comparação escolheu, e a `(sem informação)` quando há faltante.

    Entre grupos, a linha **é** a comparação `[variável, grupo]`, sem método escrito —
    a forma, o teste, o p, a frase e os avisos saem dela. Sem grupo, a forma sai do
    Shapiro-Wilk da variável inteira, pela mesma regra.
    """
    serie = _coluna(quadro, linha.variavel)
    if serie is None:  # pragma: no cover - `recusar_incompativeis` já barrou
        raise VariavelIncompativelError(f"`{linha.variavel}` não existe no banco.")
    rotulo = _rotulo(linha)
    valores = serie[no_grupo].dropna().astype("float64")
    validos = int(valores.shape[0])
    resumo = resumo_numerico(valores) if validos else None

    if grupo is None:
        return _numerica_sem_grupo(linha, rotulo, valores, resumo, casas_da_coluna(serie), n)

    comparada, _ = comparar_grupos(
        quadro, Pergunta(linha=linha, delineamento=GRUPOS, grupos=grupo), n
    )
    assert comparada is not None  # sem método escrito, não há método errado para recusar
    postos = de_postos(comparada)
    forma = COLUNA_DA_MEDIANA if postos else COLUNA_DA_MEDIA
    formatar = mediana_e_quartis if postos else media_e_desvio
    # Só os grupos com valor da variável estão na comparação; o que não tem sai com o
    # traço, e todos os seus casos na `(sem informação)`.
    por_rotulo = {grupo_.rotulo: grupo_ for grupo_ in comparada.grupos}
    celulas = tuple(
        formatar(por_rotulo[coluna.rotulo].resumo, comparada.casas)
        if coluna.rotulo in por_rotulo
        else _AUSENTE
        for coluna in colunas
    )
    linhas = [(f"{rotulo}, {forma}", *celulas, formatar(resumo, comparada.casas))]
    faltantes = n - validos
    if faltantes:
        com_valor = {rotulo_: grupo_.n for rotulo_, grupo_ in por_rotulo.items()}
        linhas.append(
            (
                ROTULO_FALTANTE,
                *(str(coluna.n - com_valor.get(coluna.rotulo, 0)) for coluna in colunas),
                str(faltantes),
            )
        )

    detalhe = {
        "grupos": [
            {
                "grupo": grupo_.rotulo,
                "n": grupo_.n,
                **resumo_no_manifesto(grupo_.resumo),
                "shapiro": shapiro_no_manifesto(grupo_.normal),
            }
            for grupo_ in comparada.grupos
        ],
        "total": {"n": validos, **resumo_no_manifesto(resumo)},
    }
    base = {
        "variavel": linha.variavel,
        "rotulo": rotulo,
        "tipo": NUMERICA,
        "forma": forma,
        "validos": validos,
        "faltantes": faltantes,
        "linhas": tuple(linhas),
        "detalhe": detalhe,
    }
    if not com_p:
        # O teste rodou dentro da comparação, e fica nela: sem o p, sai a forma, e só os
        # avisos do Shapiro-Wilk que a decidiu.
        return Caracteristica(
            **base,
            escolha=_frase_da_forma(comparada, forma),
            avisos=tuple(
                grupo_.normal.aviso
                for grupo_ in comparada.grupos
                if grupo_.normal is not None and grupo_.normal.aviso
            ),
        )
    resultado = comparada.resultado
    return Caracteristica(
        **base,
        teste=resultado.metodo if resultado is not None else "",
        p=float(resultado.p) if resultado is not None else None,
        escolha=comparada.justificativa,
        motivo=comparada.motivo,
        avisos=comparada.avisos,
    )


def _numerica_sem_grupo(
    linha: Linha,
    rotulo: str,
    valores: pd.Series,
    resumo: dict[str, float] | None,
    casas: int,
    n: int,
) -> Caracteristica:
    """
    A numérica da tabela sem grupo: a forma pelo Shapiro-Wilk da variável inteira, pela
    `regra` da comparação — o paramétrico quando ele não rejeita, o de postos quando
    rejeita ou não pode verificá-la —, e nenhum teste.
    """
    validos = int(valores.shape[0])
    normal: Normal | None = None
    if validos:
        normal = Normal(*shapiro(linha.variavel, valores, validos))
        escolha = regra(UMA_AMOSTRA, normal)
        postos = escolha.da_regra in TESTES_DE_POSTOS
        motivo = escolha.motivo
    else:
        postos = False
        motivo = "nenhum valor preenchido"
    forma = COLUNA_DA_MEDIANA if postos else COLUNA_DA_MEDIA
    formatar = mediana_e_quartis if postos else media_e_desvio

    linhas = [(f"{rotulo}, {forma}", formatar(resumo, casas))]
    faltantes = n - validos
    if faltantes:
        linhas.append((ROTULO_FALTANTE, str(faltantes)))
    return Caracteristica(
        variavel=linha.variavel,
        rotulo=rotulo,
        tipo=NUMERICA,
        forma=forma,
        validos=validos,
        faltantes=faltantes,
        linhas=tuple(linhas),
        escolha=f"{rotulo}: n = {validos}; {motivo} → {forma}.",
        avisos=(normal.aviso,) if normal is not None and normal.aviso else (),
        detalhe={
            "total": {
                "n": validos,
                **resumo_no_manifesto(resumo),
                "shapiro": shapiro_no_manifesto(normal),
            }
        },
    )


def _frase_da_forma(comparada: VariavelComparada, forma: str) -> str:
    """
    A frase da escolha sem o teste, para a tabela sem o p: o Shapiro-Wilk de cada grupo e
    a forma que ele decidiu.
    """
    if comparada.escolha is None:
        return f"{comparada.cabeca}: {comparada.motivo} → {forma}."
    return (
        f"{comparada.cabeca}: {comparada.n_na_frase}; {comparada.escolha.motivo} → {forma}."
    )


def _categorica(
    quadro: pd.DataFrame,
    linha: Linha,
    grupo: Linha | None,
    colunas: tuple[Coluna, ...],
    no_grupo: pd.Series,
    n: int,
    com_p: bool,
    limite: int,
) -> Caracteristica:
    """
    A linha de uma categórica, as categorias embaixo dela e a `(sem informação)`.

    Entre grupos, as contagens são a contingência da associação — o código conta, o
    rótulo imprime —, e com o p a linha **é** o par `[grupo, variável]` da associação:
    o teste, o p, a frase e os avisos saem dele.
    """
    rotulo = _rotulo(linha)
    par = None
    if grupo is None:
        serie = _coluna(quadro, linha.variavel)
        if serie is None:  # pragma: no cover - `recusar_incompativeis` já barrou
            raise VariavelIncompativelError(f"`{linha.variavel}` não existe no banco.")
        rotulos = [linha.rotulo_de(codigo) for codigo in serie_de_texto(serie)]
        contagens = {("", rotulo_): quantos for rotulo_, quantos in Counter(rotulos).items()}
        observadas = na_ordem_do_dicionario(set(rotulos), linha)
        respondidos = {"": len(rotulos)}
    else:
        if com_p:
            par = testar_par(quadro, Par(primeira=grupo, segunda=linha), n, limite)
            tabela = par.contingencia
        else:
            tabela = contingencia(quadro, grupo, linha)
        contagens = {
            (do_grupo, categoria): quantos
            for do_grupo, linha_ in zip(tabela.categorias_1, tabela.contagens, strict=True)
            for categoria, quantos in zip(tabela.categorias_2, linha_, strict=True)
        }
        observadas = tabela.categorias_2
        respondidos = {
            do_grupo: sum(linha_)
            for do_grupo, linha_ in zip(tabela.categorias_1, tabela.contagens, strict=True)
        }

    categorias, extras = _categorias(linha, observadas)
    chaves = [coluna.rotulo for coluna in colunas] if grupo is not None else []
    validos = sum(respondidos.values())

    linhas: list[tuple[str, ...]] = [
        (f"{rotulo}, {FORMA_DA_CATEGORICA}", *("" for _ in chaves), "")
    ]
    for categoria in categorias:
        por_coluna = [contagens.get((chave, categoria), 0) for chave in chaves]
        no_total = sum(por_coluna) if grupo is not None else contagens.get(("", categoria), 0)
        linhas.append(
            (
                categoria,
                *(
                    _n_e_percentual(quantos, respondidos.get(chave, 0))
                    for chave, quantos in zip(chaves, por_coluna, strict=True)
                ),
                _n_e_percentual(no_total, validos),
            )
        )
    faltantes = n - validos
    if faltantes:
        linhas.append(
            (
                ROTULO_FALTANTE,
                *(str(coluna.n - respondidos.get(coluna.rotulo, 0)) for coluna in colunas),
                str(faltantes),
            )
        )

    avisos: list[str] = []
    if linha.categorias_ordem and extras:
        avisos.append(
            f"`{linha.variavel}`: {len(extras)} valor(es) no banco fora da ordem declarada no "
            f"dicionário ({', '.join(repr(extra) for extra in extras[:5])}). Entraram no fim "
            "da tabela da caracterização. Se for grafia diferente da declarada, acerte o "
            "dicionário ou peça a padronização ao cliente."
        )

    detalhe: dict[str, Any] = {"categorias": list(categorias)}
    if grupo is not None:
        detalhe["contingencia"] = {
            "grupos": list(tabela.categorias_1),
            "categorias": list(tabela.categorias_2),
            "contagens": [list(linha_) for linha_ in tabela.contagens],
        }
    else:
        detalhe["total"] = {
            "n": validos,
            "contagens": [contagens.get(("", categoria), 0) for categoria in categorias],
        }
    base = {
        "variavel": linha.variavel,
        "rotulo": rotulo,
        "tipo": CATEGORICA,
        "forma": FORMA_DA_CATEGORICA,
        "validos": validos,
        "faltantes": faltantes,
        "linhas": tuple(linhas),
        "detalhe": detalhe,
    }
    if par is None:
        return Caracteristica(**base, avisos=tuple(avisos))
    return Caracteristica(
        **base,
        teste=par.teste,
        p=float(par.p) if par.p is not None else None,
        escolha=par.justificativa,
        motivo=par.motivo,
        avisos=(*avisos, *par.avisos),
    )


def _categorias(linha: Linha, observadas: Sequence[str]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """
    As categorias da tabela, e as que o dicionário não declara.

    As declaradas vêm primeiro, na ordem do dicionário, com caso ou sem — o rótulo de
    cada código, e uma vez só quando dois códigos têm o mesmo rótulo. Depois, as
    observadas que ele não declara, na ordem da associação.
    """
    declaradas: list[str] = []
    for codigo in linha.categorias_ordem:
        rotulo = linha.rotulo_de(codigo)
        if rotulo not in declaradas:
            declaradas.append(rotulo)
    extras = tuple(categoria for categoria in observadas if categoria not in declaradas)
    return (*declaradas, *extras), extras


def _n_e_percentual(quantos: int, respondidos: int) -> str:
    """`39 (38,2)`; o traço quando a coluna não tem resposta nenhuma."""
    if not respondidos:
        return _AUSENTE
    return f"{quantos} ({percentual(quantos, respondidos)})"


def _motivo_de_um_grupo(grupo: Linha, ordem: Sequence[str]) -> str:
    if not ordem:
        return f"`{grupo.variavel}`, o grupo, não tem resposta em caso nenhum"
    return (
        f"`{grupo.variavel}`, o grupo, tem uma categoria só entre os casos com resposta "
        f"({ordem[0]}) — não há grupos a comparar. Tire o grupo do item, `[…]`, para a "
        "tabela só com o Total, ou escolha outro grupo"
    )


# Os itens da ficha


def itens_da_ficha(raiz: Path) -> tuple[Pedido, ...]:
    """
    A lista `caracterizacao:` do `projeto.yaml`, conferida na forma.

    Três formas de item, e todas podem conviver — uma tabela por item:

        - sexo: [idade, imc, escolaridade]   # o grupo antes dos dois-pontos
        - por: sexo                          # todas as variáveis do dicionário
          p: nao                             # sem a coluna do p
        - [idade, imc, sexo]                 # sem grupo: só o Total

    Devolve vazio quando a chave não existe ou está vazia — quem recusa isso é o
    `caracterizar`, que tem o dicionário na mão para escrever quais variáveis existem.
    Formato errado recusa em vez de ignorar: um item que o comando pulasse em silêncio é
    o pior dos dois mundos — você escreveu, e não valeu.

    Lida pelo `ficha.bloco`, e não abrindo o YAML aqui: o `ficha.py` é o único módulo do
    pacote que abre o `projeto.yaml`.

    Raises:
        ItemInvalidoError
    """
    bruto = bloco(raiz, PASTA_CARACTERIZACAO)
    if bruto is None:
        return ()
    if not isinstance(bruto, list):
        raise ItemInvalidoError(
            f"A chave `{PASTA_CARACTERIZACAO}:` do {ARQUIVO_PROJETO} deveria ser uma "
            f"lista, e é {_descrever_valor(bruto)}.\n\n"
            f"Escreva assim, um item por linha:\n\n{EXEMPLO_DA_FICHA}"
        )

    pedidos: list[Pedido] = []
    problemas: list[str] = []
    for posicao, item in enumerate(bruto, start=1):
        pedido, problema = _ler_item(item)
        if pedido is None:
            problemas.append(f"  {posicao}º item: {problema}")
        else:
            pedidos.append(pedido)

    if problemas:
        raise ItemInvalidoError(
            f"A lista `{PASTA_CARACTERIZACAO}:` do {ARQUIVO_PROJETO} tem "
            f"{len(problemas)} item(ns) fora do formato. Nada foi gerado.\n\n"
            + "\n".join(problemas)
            + f"\n\nEscreva assim, um item por linha:\n\n{EXEMPLO_DA_FICHA}\n\n"
            "Cada item é uma tabela. O grupo vem antes dos dois-pontos, e as variáveis da "
            "tabela, entre colchetes, depois dele, na ordem das linhas; `por:` e o grupo "
            "põem todas as variáveis do dicionário; a lista sozinha, sem grupo, dá a tabela "
            f"só com o Total. `{CHAVE_P}: nao`, na linha de baixo do item, tira a coluna "
            "do p."
        )
    return tuple(pedidos)


def _ler_item(item: Any) -> tuple[Pedido | None, str]:
    """
    Um item da lista: o `Pedido` que ele escreve, ou a frase do que está errado nele.
    """
    if isinstance(item, list):
        variaveis, problema = _ler_variaveis(item, "", _descrever_valor(item))
        return (Pedido(variaveis=variaveis), "") if not problema else (None, problema)
    if isinstance(item, dict) and item:
        return _ler_bloco(item)
    return None, (
        f"{_descrever_valor(item)} — um item é o grupo e a lista das variáveis, "
        "`sexo: [idade, imc]`, `por:` e o grupo, `por: sexo`, ou só a lista, sem grupo, "
        "`[idade, imc]`."
    )


def _ler_bloco(item: dict[str, Any]) -> tuple[Pedido | None, str]:
    """
    O item com dois-pontos: o grupo e a lista, ou `por:` e o grupo — e o `p:` ao lado.
    """
    escrito = _descrever_bloco(item)
    com_p = True
    chaves_do_p = [chave for chave in item if _simplificado(chave) == CHAVE_P]
    for chave in chaves_do_p:
        com_p, problema = _ler_p(item[chave])
        if problema:
            return None, f"{escrito} — {problema}"

    grupos = [chave for chave in item if chave not in chaves_do_p]
    if not grupos:
        return None, (
            f"{escrito} — o `{CHAVE_P}:` vai na linha de baixo de um item com grupo: "
            f"`- sexo: [idade, imc]` e, embaixo, `{CHAVE_P}: nao`."
        )
    if len(grupos) > 1:
        return None, (
            f"{escrito} — {len(grupos)} grupos num item só; cada item é uma tabela, com um "
            f"grupo: escreva `- {grupos[0]}: […]` e `- {grupos[1]}: […]`, um em cada item."
        )

    chave = grupos[0]
    valor = item[chave]
    if _simplificado(chave) == CHAVE_POR:
        grupo = _nome(valor)
        if not grupo:
            return None, (
                f"{escrito} — depois de `{CHAVE_POR}:` vem o nome do grupo, sem colchetes: "
                f"`- {CHAVE_POR}: sexo`."
            )
        return Pedido(grupo=grupo, todas=True, com_p=com_p), ""

    grupo = _nome(chave)
    variaveis, problema = _ler_variaveis(
        valor if isinstance(valor, list) else [valor], grupo, escrito
    )
    if problema:
        return None, problema
    return Pedido(grupo=grupo, variaveis=variaveis, com_p=com_p), ""


def _ler_p(valor: Any) -> tuple[bool, str]:
    """`p: nao` tira o p; `p: sim` o deixa — como texto ou como booleano."""
    if isinstance(valor, bool):
        return valor, ""
    texto = _simplificado(str(valor)) if valor is not None else ""
    if texto in _SEM_P:
        return False, ""
    if texto in _COM_P:
        return True, ""
    return True, (
        f"`{CHAVE_P}: {_descrever_solto(valor)}` — escreva `{CHAVE_P}: nao` para tirar a "
        "coluna do p; sem a linha, a tabela sai com ele."
    )


def _ler_variaveis(
    brutas: list[Any], grupo: str, escrito: str
) -> tuple[tuple[str, ...], str]:
    """
    A lista das variáveis de um item: nomes, nenhum repetido, e sem o grupo.
    """
    if not brutas:
        return (), (
            f"{escrito} — a lista das variáveis está vazia; escreva as que vão para a tabela, "
            "`[idade, imc]`, ou `por:` e o grupo, para todas."
        )
    nomes = [_nome(valor) for valor in brutas]
    sem_nome = [valor for valor, nome in zip(brutas, nomes, strict=True) if not nome]
    if sem_nome:
        return (), (
            f"{escrito} — `{_descrever_solto(sem_nome[0])}` não é o nome de uma variável; a "
            "lista leva os nomes da coluna `variavel` do dicionário, um por item."
        )
    if grupo and grupo in nomes:
        return (), (
            f"{escrito} — `{grupo}` é o grupo e está também na lista: o grupo vira as "
            "colunas da tabela, e não uma linha dela. Tire-o da lista."
        )
    repetidos = [nome for nome in dict.fromkeys(nomes) if nomes.count(nome) > 1]
    if repetidos:
        return (), (
            f"{escrito} — `{repetidos[0]}` duas vezes; cada variável é uma linha da tabela, "
            "e sai uma vez."
        )
    return tuple(nomes), ""


def _conferir_itens(pedidos: Sequence[Pedido], linhas: Sequence[Linha]) -> list[Item]:
    """
    Confere cada item contra o dicionário, e recusa listando todos os problemas.

    O grupo precisa existir, estar no banco, não ser `ignorar` e ser `categorica`; cada
    variável da lista precisa existir, estar no banco e não ser `ignorar`. A variável
    `data` não recusa: fica de fora da tabela, na lista `fora`. No `por:`, as variáveis
    são as analisáveis do dicionário, na ordem dele, menos o grupo.
    """
    por_nome = {linha.variavel: linha for linha in linhas}
    itens: list[Item] = []
    problemas: list[str] = []

    for pedido in pedidos:
        motivos: list[str] = []
        grupo: Linha | None = None
        if pedido.grupo:
            linha = por_nome.get(pedido.grupo)
            motivo = _motivo_do_grupo(pedido.grupo, linha)
            if motivo:
                motivos.append(motivo)
            else:
                grupo = linha

        if pedido.todas:
            escolhidas = [
                linha
                for linha in linhas
                if linha.analisavel and linha.variavel != pedido.grupo
            ]
        else:
            escolhidas = []
            for nome in pedido.variaveis:
                linha = por_nome.get(nome)
                motivo = _motivo_da_variavel(nome, linha)
                if motivo:
                    motivos.append(motivo)
                elif linha is not None:
                    escolhidas.append(linha)

        if motivos:
            problemas.append(f"  {pedido.escrito} — " + "; ".join(motivos))
            continue

        da_tabela = tuple(linha for linha in escolhidas if linha.tipo != DATA)
        datas = tuple(linha for linha in escolhidas if linha.tipo == DATA)
        if not da_tabela:
            problemas.append(
                f"  {pedido.escrito} — nenhuma variável numérica ou categórica para a "
                "tabela"
                + (
                    f": {_crases(linha.variavel for linha in datas)} "
                    f"{'é data' if len(datas) == 1 else 'são datas'}, e as datas ficam fora "
                    "da caracterização"
                    if datas
                    else ""
                )
            )
            continue
        itens.append(Item(pedido=pedido, grupo=grupo, linhas=da_tabela, datas=datas))

    if problemas:
        raise ItemInvalidoError(
            f"A lista `{PASTA_CARACTERIZACAO}:` do {ARQUIVO_PROJETO} tem {len(problemas)} "
            "item(ns) que não podem ser caracterizados. Nada foi gerado.\n\n"
            + "\n".join(problemas)
            + "\n\nO grupo, antes dos dois-pontos, é uma variável marcada `categorica` no "
            f"{ARQUIVO_DICIONARIO} — uma numérica de poucos valores entra marcada "
            "`categorica`. As variáveis da tabela são as numéricas e as categóricas do "
            "dicionário.\n\n"
            f"Corrija o nome na lista do {ARQUIVO_PROJETO} — ele é o da coluna `variavel` "
            f"do {ARQUIVO_DICIONARIO} —, ou o `tipo` no dicionário, e rode de novo."
        )
    return itens


def _motivo_de_ausencia(nome: str, linha: Linha | None) -> str:
    if linha is None:
        return f"`{nome}` não está no {ARQUIVO_DICIONARIO}"
    if not linha.no_banco:
        return f"`{nome}` não está nesta versão do banco (`no_banco = nao`)"
    if linha.tipo == IGNORAR:
        return f"`{nome}` está marcada `ignorar` no {ARQUIVO_DICIONARIO}"
    return ""


def _motivo_do_grupo(nome: str, linha: Linha | None) -> str:
    ausencia = _motivo_de_ausencia(nome, linha)
    if ausencia or linha is None:
        return ausencia
    if linha.tipo != CATEGORICA:
        return (
            f"`{nome}`, o grupo, está marcada `{linha.tipo}` no {ARQUIVO_DICIONARIO}, e o "
            "grupo é uma categórica"
        )
    return ""


def _motivo_da_variavel(nome: str, linha: Linha | None) -> str:
    return _motivo_de_ausencia(nome, linha)


# O manifesto


def montar_manifesto(caracterizacao: Caracterizacao, linhas: Sequence[Linha]) -> Manifesto:
    """
    Traduz a rodada para o índice que o relatório vai ler.

    **Um item só**, como na comparação: a seção do documento é "Caracterização dos
    participantes", com uma tabela por item da ficha. O `colunas` do item diz quais
    colunas do banco entraram — os grupos também —, que é o que mantém as conferências
    do relatório certas para uma seção que não é de uma variável. Os artefatos levam a
    apresentação — o recuo, o rodapé e a página em paisagem —, e os `detalhes`, o que
    decidiu cada linha.
    """
    banco = caracterizacao.banco
    leitura = banco.leitura
    ficha = caracterizacao.ficha

    item = ItemDoManifesto(
        variavel="",
        slug=PASTA_CARACTERIZACAO,
        rotulo=ROTULO_DA_SECAO,
        tipo=ANALISE_CARACTERIZACAO,
        n=banco.linhas,
        faltantes=0,
        colunas=caracterizacao.colunas_usadas,
        artefatos=tuple(tabela.artefato() for tabela in caracterizacao.tabelas),
        detalhes={
            "tabelas": [_detalhe_da_tabela(tabela) for tabela in caracterizacao.tabelas],
            "testados": len(caracterizacao.testadas),
            "sem_teste": len(caracterizacao.sem_teste),
        },
        avisos=tuple(aviso for tabela in caracterizacao.tabelas for aviso in tabela.avisos),
    )

    return Manifesto(
        analise=ANALISE_CARACTERIZACAO,
        flatcap=__version__,
        gerado_em=caracterizacao.quando,
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
            "virgula_decimal": list(leitura.virgula_decimal),
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
        regras=_regras(),
        itens=(item,),
        fora=tuple(
            {"variavel": f.variavel, "tipo": f.tipo, "motivo": f.motivo}
            for f in caracterizacao.fora
        ),
        avisos=caracterizacao.avisos,
    )


def _detalhe_da_tabela(tabela: TabelaCaracterizada) -> dict[str, Any]:
    """
    Uma tabela no manifesto: o grupo, os casos, a legenda e, por linha, o teste, o p
    inteiro — sem o arredondamento das três casas da célula —, a letra, a frase da
    escolha, e o resto do que a decidiu.
    """
    return {
        "arquivo": tabela.arquivo,
        "grupo": tabela.grupo.variavel if tabela.grupo is not None else None,
        "rotulo_do_grupo": tabela.rotulo_do_grupo or None,
        "por": tabela.pedido.todas,
        "com_p": tabela.com_p,
        "n": tabela.n,
        "fora_do_grupo": tabela.fora_do_grupo,
        "grupos": [{"grupo": coluna.rotulo, "n": coluna.n} for coluna in tabela.colunas],
        "letras": {letra: teste for teste, letra in tabela.letras.items()},
        "linhas": [
            {
                "variavel": caracteristica.variavel,
                "rotulo": caracteristica.rotulo,
                "tipo": caracteristica.tipo,
                "forma": caracteristica.forma,
                "n": caracteristica.validos,
                "faltantes": caracteristica.faltantes,
                "teste": caracteristica.teste or None,
                "p": caracteristica.p,
                "letra": tabela.letra(caracteristica) or None,
                "escolha": caracteristica.escolha or None,
                "motivo": caracteristica.motivo or None,
                **caracteristica.detalhe,
            }
            for caracteristica in tabela.caracteristicas
        ],
        "datas_fora": [linha.variavel for linha in tabela.datas],
    }


def _regras() -> dict[str, Any]:
    """
    As regras desta versão, escritas por extenso no manifesto — as mesmas das notas das
    tabelas, sem os números de uma rodada.
    """
    return {
        "itens": (
            f"os da lista `{PASTA_CARACTERIZACAO}:` do {ARQUIVO_PROJETO}, uma tabela por item"
        ),
        "colunas": (
            "uma por categoria do grupo com pelo menos um caso, na ordem do dicionário, e o "
            "Total, a soma delas; quem não tem o grupo fica fora da tabela"
        ),
        "numericas": (
            f"{COLUNA_DA_MEDIA} se o Shapiro-Wilk não rejeita a normal (p ≥ {ALFA:g}) em "
            f"nenhum grupo, senão {COLUNA_DA_MEDIANA} — a regra da comparação entre grupos; "
            "sem grupo, a do Shapiro-Wilk da variável inteira; o Total segue a forma da linha"
        ),
        "categoricas": (
            f"{FORMA_DA_CATEGORICA} sobre os casos com resposta na coluna; a categoria "
            "declarada e sem caso sai com 0 e fica fora do teste"
        ),
        "teste": (
            "o da comparação entre grupos sem método escrito — t de Welch ou Mann-Whitney; "
            "ANOVA de Welch ou Kruskal-Wallis com três grupos ou mais — e o da associação — "
            "a regra de Cochran: qui-quadrado, com Yates só na 2×2, ou exato de Fisher. A "
            "regra dos pressupostos manda mesmo quando a lista `comparacao:` escreve outro "
            f"método; `{CHAVE_P}: nao` no item tira a coluna do p"
        ),
        "letras": "a letra colada ao p é a do teste, na ordem em que cada teste aparece",
        "alfa": ALFA,
        "faltantes": "por variável, dentro de cada coluna: a linha `(sem informação)`",
        "comparacoes_multiplas": "nenhuma correção",
        "semente": SEMENTE,
    }


def _ambiente() -> dict[str, Any]:
    """
    As versões que produziram estes números.

    O `scipy` entra, porque os testes e o Shapiro-Wilk são dele. O `matplotlib` e a
    `fonte` saem `None` — a rodada não desenha —, e as chaves continuam lá para o bloco
    ter a forma dos outros.
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
    categoricas = [
        linha.variavel for linha in linhas if linha.analisavel and linha.tipo == CATEGORICA
    ]
    if categoricas:
        disponiveis = (
            f"As categóricas deste {ARQUIVO_DICIONARIO}, que formam os grupos, são: "
            + ", ".join(categoricas[:20])
            + (f" e mais {len(categoricas) - 20}" if len(categoricas) > 20 else "")
            + "."
        )
    else:
        disponiveis = (
            f"Nenhuma variável deste {ARQUIVO_DICIONARIO} está marcada `categorica` ainda: "
            "sem grupo, a tabela sai só com o Total."
        )
    return (
        f"O {ARQUIVO_PROJETO} deste projeto não diz o que caracterizar.\n\n"
        "Escreva a lista na ficha — o grupo antes dos dois-pontos e as variáveis da tabela "
        "depois dele; `por:` e o grupo, para todas as variáveis do dicionário; ou só a "
        f"lista, sem grupo:\n\n{EXEMPLO_DA_FICHA}\n\n"
        f"{disponiveis}\n\n"
        f"`{CHAVE_P}: nao`, na linha de baixo do item, tira a coluna do p: num ensaio "
        "randomizado, o CONSORT desaconselha testar a linha de base."
    )


def _motivo_de_fora(linha: Linha, data_pedida: bool) -> str:
    if not linha.no_banco:
        return "não está nesta versão do banco (`no_banco = nao`)"
    if linha.tipo == IGNORAR:
        return "marcada `ignorar` no dicionário"
    if data_pedida:
        return "marcada `data` — a caracterização descreve numéricas e categóricas"
    return f"não está em nenhum item da lista `{PASTA_CARACTERIZACAO}:` do {ARQUIVO_PROJETO}"


def _acao_do_historico(plano: PlanoCaracterizacao) -> str:
    caracterizacao = plano.caracterizacao
    quantas = len(caracterizacao.tabelas)
    testadas = len(caracterizacao.testadas)
    sem_teste = len(caracterizacao.sem_teste)
    contagem = ", ".join(
        texto
        for quantos, texto in (
            (testadas, f"{testadas} linha(s) com p"),
            (sem_teste, f"{sem_teste} sem teste"),
        )
        if quantos
    )
    partes = [
        f"`flatcap caracterizacao {caracterizacao.ficha.record_id}` — caracterização de "
        f"`{caracterizacao.banco.versao.arquivo}`: {quantas} tabela(s) da lista "
        f"`{PASTA_CARACTERIZACAO}:`"
        + (f" ({contagem})" if contagem else "")
        + f", em `{PASTA_ANALISES}/{PASTA_CARACTERIZACAO}/`."
    ]
    if plano.arquivamento is not None:
        partes.append(
            f"A rodada anterior foi para `{PASTA_ANTIGAS}/{plano.arquivamento[1].name}/`."
        )
    return " ".join(partes)


# Leitura da série e texto


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
    O nome de uma variável, como a ficha o trouxe; vazio quando não é um nome.

    Lista e bloco dentro da lista não são nome — é o `[[idade, imc]]` digitado com um
    colchete a mais.
    """
    if valor is None or isinstance(valor, list | dict | bool):
        return ""
    return str(valor).strip()


def _simplificado(texto: str) -> str:
    limpo = unicodedata.normalize("NFKD", str(texto or "")).lower().strip()
    return "".join(c for c in limpo if not unicodedata.combining(c))


def _crases(nomes: Any) -> str:
    """`a`, `a` e `b`, `a`, `b` e `c` — cada um entre crases."""
    lista = [f"`{nome}`" for nome in nomes]
    if len(lista) <= 1:
        return "".join(lista)
    return ", ".join(lista[:-1]) + " e " + lista[-1]


def _descrever_valor(valor: Any) -> str:
    if isinstance(valor, list):
        return "[" + ", ".join(_descrever_solto(item) for item in valor) + "]"
    if isinstance(valor, dict):
        return _descrever_bloco(valor)
    if valor is None:
        return "vazio"
    if isinstance(valor, str):
        return f"`{valor}`"
    return f"`{valor}` ({type(valor).__name__})"


def _descrever_bloco(item: dict[str, Any]) -> str:
    """`{sexo: [idade, imc], p: nao}` — o bloco numa linha só, para as mensagens."""
    return "{" + ", ".join(
        f"{chave}: {_descrever_solto(valor)}" for chave, valor in item.items()
    ) + "}"


def _descrever_solto(valor: Any) -> str:
    """Um valor como ele apareceria dentro dos colchetes da ficha."""
    if isinstance(valor, list):
        return "[" + ", ".join(_descrever_solto(item) for item in valor) + "]"
    if isinstance(valor, bool):
        return "true" if valor else "false"
    if valor is None:
        return ""
    return str(valor)


def _integridade(confere: bool | None) -> str:
    if confere is True:
        return "confere"
    if confere is False:
        return "ALTERADO"
    return "não conferida"


__all__ = [
    "CHAVE_P",
    "CHAVE_POR",
    "COLUNA_DA_CARACTERISTICA",
    "COLUNA_DO_P",
    "COLUNA_DO_TOTAL",
    "EXEMPLO_DA_FICHA",
    "FORMA_DA_CATEGORICA",
    "GRUPOS_PARA_DEITAR",
    "PERCENTUAIS",
    "ROTULO_DA_SECAO",
    "SEM_GRUPO",
    "TITULO",
    "Caracteristica",
    "Caracterizacao",
    "CaracterizacaoError",
    "Coluna",
    "DicionarioAusenteError",
    "DicionarioDesatualizadoError",
    "ForaDaCaracterizacao",
    "Item",
    "ItemInvalidoError",
    "Pedido",
    "PlanoCaracterizacao",
    "ResultadoCaracterizacao",
    "SemItensError",
    "TabelaCaracterizada",
    "VariavelIncompativelError",
    "caracterizar",
    "executar_caracterizacao",
    "itens_da_ficha",
    "montar_manifesto",
    "preparar_caracterizacao",
]
