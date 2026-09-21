"""
A associação — qui-quadrado ou exato de Fisher, escolhido pela regra de Cochran.

Responde ao passo 2b do fluxo, e é o primeiro teste de hipótese entre duas
variáveis da Fase 7. Para cada par de categóricas pedido na ficha, uma linha de
tabela:

    variável 1  variável 2     n  teste                               p-valor  V de Cramér
    Grupo       Desfecho      79  Qui-quadrado com correção de Yates    0,017         0,29
    Grupo       Complicação   80  Exato de Fisher                       0,201         0,19
    Grupo       Escolaridade  80  Exato de Fisher                       0,480         0,19
    Grupo       Faixa etária  80  Qui-quadrado                          0,596         0,11

Segue o padrão das Fases 2 a 6, decidir e escrever separados:

    plano = preparar_associacao(raiz)   # abre o banco, testa, não toca no disco
    executar_associacao(plano)          # só escreve

E, como elas, **não fala com o REDCap**. Recebe `Path`, não `Config`.

## Quais pares

Os que estiverem escritos na ficha, e só eles, em duas formas:

    associacao:
      - [sexo, desfecho]                            # par único
      - desfecho: [sexo, escolaridade, tabagismo]   # uma contra várias

A segunda é a primeira escrita três vezes: `desfecho` fica na coluna `variável 1`
e cada uma das outras entra na `variável 2`, na ordem da lista. As duas formas
podem conviver na mesma lista, e a tabela sai na ordem em que os pares foram
escritos.

Sem a lista, o comando recusa — pelo mesmo motivo do cruzamento: trinta
categóricas dão 435 pares, e testar todos é *p-hacking* feito por máquina. Qual
par testar é hipótese, e hipótese se escreve na reunião.

## A decisão central: quem escolhe o teste é a tabela

A escolha entre qui-quadrado e Fisher **não** depende de normalidade — categórica
não tem normalidade a testar, e nada aqui olha para o `normalidade.py`. Depende de
quão bem a distribuição do qui-quadrado aproxima a estatística naquela tabela, e
isso se mede pelas frequências esperadas sob independência. A regra é a de
Cochran, a mesma que o `fisher.test` do R chama de *Cochran's conditions*
(`hybridPars = c(expect = 5, percent = 80, Emin = 1)`):

* **qui-quadrado** quando nenhuma frequência esperada é menor que 1 **e** no
  máximo 20% das caselas têm esperada menor que 5;
* **exato de Fisher** em qualquer outro caso.

Numa tabela 2×2 os 20% são menos de uma casela, então a regra vira "todas as
esperadas pelo menos 5" — a forma como ela costuma ser ensinada.

A justificativa de cada escolha — a dimensão da tabela, a menor esperada e
quantas caselas ficaram abaixo de 5 — sai escrita no `.csv` e no manifesto. Um
teste escolhido sem o motivo escrito é uma decisão que ninguém consegue conferir.

## Como o R faz, e por que isso pede aritmética escrita aqui

**O qui-quadrado é o `chisq.test(x)`**, com o padrão dele, `correct = TRUE`: a
correção de continuidade de Yates entra só nas tabelas 2×2, e nunca maior do que
a própria diferença — `min(0.5, abs(x - E))`, que numa tabela em que o observado
já está a menos de meio caso do esperado dá estatística zero e p = 1. Nas maiores,
Pearson sem correção.

**O Fisher é o `fisher.test(x)`**, bilateral:

* **na 2×2**, pela distribuição hipergeométrica, somando as tabelas com
  probabilidade menor ou igual à observada, com a folga relativa de `1e-7` que o
  código do R usa para não perder, por erro de arredondamento, a tabela simétrica
  que tem exatamente a mesma probabilidade;
* **nas maiores**, **exato** pelo algoritmo de rede de Mehta e Patel (1983) — o
  FEXACT que o R chama por baixo —, com a folga de `3.45254e-7` no logaritmo que o
  FEXACT usa, e **sem simulação**.

O `scipy` faz a 2×2 do mesmo jeito. A maior, não: desde a versão 1.15 ele aceita
tabela r × c, mas calcula o p por **simulação de Monte Carlo**, sem semente — o
mesmo banco dá um p diferente a cada rodada, e diferente do que o R imprime. Numa
2×3 cujo p exato é 0,0930, cinco chamadas ao `scipy` 1.17 deram de 0,0931 a
0,0957. Um relatório que muda de número sem o banco mudar é o que este projeto
existe para impedir.

Então o cálculo exato está escrito aqui, e o `scipy` entra só na distribuição do
qui-quadrado. É a exceção à regra da normalidade — "importar a aritmética,
escrever as decisões" —, e ela tem a conferência que aquela regra pedia: o
`test_associacao.py` compara este cálculo com a força bruta, com o `scipy` na
2×2, e com os exemplos da documentação do `fisher.test` do R (`Job`, 4×4,
p = 0,7827; `MP6`, 5×7, p = 0,03929; `TeaTasting`; `Convictions`).

**O limite do cálculo exato.** Numa tabela grande com n na casa das centenas, o
número de tabelas com as mesmas margens explode. O R tem um teto para isso — o
`workspace` do `fisher.test` —, e para com `FEXACT error` quando passa dele,
mandando aumentar o `workspace` ou simular. Aqui o teto é
`LIMITE_DO_CALCULO_EXATO`, contado em operações e não em segundos, para que a
mesma tabela tenha a mesma resposta em qualquer máquina. Passou dele, a linha sai
com o p **não calculado** e um aviso dizendo o que fazer. Simular em silêncio
seria trocar o teste que você escolheu por outro.

## O que ele reaproveita, e por quê

**A categoria é a da descritiva e a do cruzamento.** Os valores passam pela
`serie_de_texto` e pelo `rotulo_de` do dicionário antes de contar — e é por isso
que dois códigos com o mesmo rótulo (`1=Sim|2=Sim`) viram **uma** linha da tabela
de contingência. O agrupamento que você faz no dicionário vale para o teste do
mesmo jeito que vale para as tabelas.

**As recusas de dicionário e de tipo são as da descritiva**, com a classe de erro
deste módulo. **O p-valor sai pela mesma função da normalidade**: três casas, e
`< 0,001` abaixo disso — nunca `0,000`.

## O que ele deliberadamente não faz

**Não imprime a tabela de contingência.** Ela é o cruzamento: os mesmos pares,
escritos na chave `cruzamento:` — lá, um par por linha —, a põem no documento. O
manifesto desta rodada guarda as contagens de cada par, para conferência.

**Não corrige para comparações múltiplas.** Cada linha é um teste, com o p dele, e
isso está escrito na nota do `.csv`. A correção é decisão sua, e depende de quais
hipóteses são confirmatórias.

**Não desenha.**

## O tamanho da associação: o V de Cramér

O p responde se há evidência de associação, e depende do n: com n grande, uma
associação irrelevante sai significante. O V responde o **tamanho** dela, de 0 a
1, e é por isso que ele sai ao lado do p — é o argumento da normalidade, de que o
valor-p sozinho não responde à pergunta. Na forma "uma contra várias" ele é o que
permite comparar os pares entre si.

Três decisões, escritas também na nota do `.csv`:

* **o X² do V é sempre o de Pearson sem correção**, qualquer que seja o teste da
  linha. É a definição, e é o que mantém o V comparável: com o X² de Yates, a
  mesma 2×2 teria um V diferente conforme o teste escolhido;
* **ele sai em toda tabela testável**, inclusive nas do Fisher e nas que passaram
  do limite do cálculo exato — o V não depende do p;
* **duas casas fixas**, que é como tamanho de efeito se escreve; o manifesto
  guarda o número inteiro, e o X² de onde ele saiu.

O que ele não faz é dizer se a associação é "pequena" ou "grande": os cortes de
Cohen dependem dos graus de liberdade, e o V superestima em tabela pequena — as
que vão para o Fisher. A leitura é sua, como a da normalidade.
"""

from __future__ import annotations

import math
import sys
from bisect import bisect_right
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from fractions import Fraction
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from . import __version__
from .banco import Banco, abrir
from .descritiva import arquivamento as arquivamento_da_rodada
from .descritiva import (
    conferir_dicionario,
    numero,
    percentual,
    recusar_incompativeis,
    serie_de_texto,
)
from .dicionario import ARQUIVO_DICIONARIO, CATEGORICA, IGNORAR, NUMERICA, Linha
from .ficha import Ficha, bloco, escrever_atomico
from .ficha import ler as ler_ficha
from .manifesto import (
    ANALISE_ASSOCIACAO,
    ARQUIVO_MANIFESTO,
    SEMENTE,
    Artefato,
    ItemDoManifesto,
    Manifesto,
    Tabela,
    texto_do_manifesto,
)
from .nomes import rotulo_do_projeto
from .normalidade import MENOR_P, valor_p
from .projeto import (
    ARQUIVO_PROJETO,
    PASTA_ANALISES,
    PASTA_ANTIGAS,
    PASTA_ASSOCIACAO,
    anotar,
    pasta_da_analise,
)

ARQUIVO_TABELA = "associacao.csv"

# A regra de Cochran. Com nome e aqui em cima, pelo motivo de sempre: número solto
# no meio de uma função é decisão que ninguém consegue rever. Os três valores são
# os `hybridPars` do `fisher.test` do R.
ESPERADA_MINIMA = 1.0      # nenhuma esperada abaixo disto
ESPERADA_DE_REFERENCIA = 5.0
PROPORCAO_TOLERADA = 0.20  # no máximo esta fração das caselas abaixo de 5

# Os nomes que vão para a coluna `teste`.
TESTE_QUI_QUADRADO = "Qui-quadrado"
TESTE_YATES = "Qui-quadrado com correção de Yates"
TESTE_FISHER = "Exato de Fisher"

# As folgas do R. Existem para que duas tabelas com a mesma probabilidade não
# fiquem de lados diferentes do limiar por erro de arredondamento.
FOLGA_2X2 = 1e-7          # `relErr <- 1 + 10^(-7)` no fisher.test, relativa
FOLGA_RXC = 3.45254e-7    # `tol` do FEXACT, somada ao logaritmo

# Quantas operações o cálculo exato pode gastar em uma tabela — colunas
# enumeradas mais passados levados adiante. É o papel do `workspace` do
# `fisher.test`, contado de um jeito que não depende da máquina: a mesma tabela
# tem a mesma resposta em qualquer computador. Um milhão e meio cobre os exemplos
# da documentação do R e as tabelas pequenas e médias em que a regra de Cochran
# costuma mandar para o Fisher — uma 3 × 4 com n = 400 leva uns dois segundos —,
# e limita a espera, quando a tabela não cabe, a poucos segundos.
LIMITE_DO_CALCULO_EXATO = 1_500_000

# O V de Cramér sai com duas casas, que é como tamanho de efeito se escreve num
# artigo; o manifesto guarda o número inteiro.
CASAS_V = 2

# O sinal entre os dois rótulos nas notas e nos avisos. O mesmo do cruzamento.
SINAL = " × "

_AUSENTE = "—"

# O exemplo que as mensagens escrevem. Um lugar só, para a recusa e o `--help`
# nunca ensinarem duas formas diferentes de escrever a mesma lista.
EXEMPLO_DA_FICHA = f"""  {PASTA_ASSOCIACAO}:
    - [sexo, desfecho]
    - desfecho: [sexo, escolaridade, tabagismo]"""


class AssociacaoError(RuntimeError):
    """
    Falha ao gerar a associação, já traduzida para o usuário.

    Erro próprio pela regra da casa: a CLI captura esta classe e transforma em
    painel com o nome do comando que o usuário rodou. Qualquer outra exceção é bug
    de verdade e deve subir com o traceback inteiro.
    """


class DicionarioAusenteError(AssociacaoError):
    """
    O projeto não tem `dicionario.csv`. Não há o que obedecer.
    """


class DicionarioDesatualizadoError(AssociacaoError):
    """
    O banco tem colunas que o dicionário desconhece.
    """


class VariavelIncompativelError(AssociacaoError):
    """
    O dicionário declara uma variável que o banco não tem.

    A mesma recusa da Fase 5, pela mesma função — como no cruzamento, aplicada só
    às variáveis dos pares.
    """


class SemParesError(AssociacaoError):
    """
    A ficha não diz quais pares testar.
    """


class ParInvalidoError(AssociacaoError):
    """
    A lista `associacao:` da ficha tem item que não serve.

    Formato errado, nome fora do dicionário, variável que não é `categorica`, a
    mesma variável duas vezes ou o mesmo par duas vezes. A mensagem lista **todos**
    de uma vez, pela regra da Fase 5.
    """


class CalculoExatoGrandeError(AssociacaoError):
    """
    A tabela passou do `LIMITE_DO_CALCULO_EXATO` no Fisher exato.

    Não chega ao usuário como painel: o `associar` a captura e a linha sai com o p
    não calculado e um aviso. É pública para que o `fisher_exato` possa ser usado
    sozinho — em teste, ou no dia em que outra análise precisar dele.
    """


# O que sai no disco


@dataclass(frozen=True)
class Par:
    """
    Um par pedido na ficha, já conferido contra o dicionário.

    `primeira` vai para a coluna `variável 1`, e é a variável da frente na forma
    "uma contra várias".
    """

    primeira: Linha
    segunda: Linha


@dataclass(frozen=True)
class Contingencia:
    """
    A tabela de contingência de um par, com as caselas zeradas.

    As categorias são os **rótulos** que apareceram entre os casos com as duas
    respostas, na ordem do dicionário — e só elas: uma categoria declarada e sem
    nenhum caso não é linha da tabela do teste, porque a frequência esperada dela
    seria zero e o qui-quadrado deixaria de existir.

    As caselas zeradas, ao contrário, ficam: numa tabela de contingência o zero é
    informação, e é justamente o caso em que o Fisher costuma ser chamado.
    """

    categorias_1: tuple[str, ...]
    categorias_2: tuple[str, ...]
    contagens: tuple[tuple[int, ...], ...]

    @property
    def n(self) -> int:
        return sum(sum(linha) for linha in self.contagens)

    @property
    def dimensoes(self) -> str:
        return f"{len(self.categorias_1)}×{len(self.categorias_2)}"

    @property
    def testavel(self) -> bool:
        return len(self.categorias_1) >= 2 and len(self.categorias_2) >= 2

    def esperadas(self) -> tuple[tuple[float, ...], ...]:
        """
        `total da linha × total da coluna ÷ n`, casela por casela.
        """
        return _esperadas(self.contagens)


@dataclass(frozen=True)
class Cochran:
    """
    O que a regra de Cochran olhou numa tabela, e o que ela decidiu.
    """

    menor_esperada: float
    abaixo: int  # caselas com esperada menor que 5
    caselas: int

    @property
    def atende(self) -> bool:
        """
        Nenhuma esperada abaixo de 1, e no máximo 20% das caselas abaixo de 5.

        A proporção é comparada em frações exatas, e não em ponto flutuante: com dez
        caselas e duas abaixo de 5 a tabela está **exatamente** nos 20%, e atende —
        uma conta em `float` poderia pôr esse caso do lado errado da fronteira.
        """
        return self.menor_esperada >= ESPERADA_MINIMA and Fraction(
            self.abaixo, self.caselas
        ) <= Fraction(str(PROPORCAO_TOLERADA))


@dataclass(frozen=True)
class ParTestado:
    """
    Um par, testado. É uma linha da tabela.

    `teste` fica vazio e `p` fica `None` quando não houve teste; o motivo está em
    `motivo`, e a linha **sai assim mesmo** — um par pedido que sumisse da tabela
    seria a falta em que ninguém repara. `p` também fica `None` quando o Fisher foi
    escolhido e passou do limite do cálculo exato: aí `teste` diz qual era, e o V de
    Cramér sai assim mesmo, porque ele não depende do p.
    """

    variavel_1: str
    variavel_2: str
    rotulo_1: str
    rotulo_2: str
    total: int
    validos: int
    contingencia: Contingencia
    teste: str = ""
    p: float | None = None
    estatistica: float | None = None  # X², só no qui-quadrado
    gl: int | None = None
    cochran: Cochran | None = None
    # O V de Cramér e o X² sem correção de onde ele sai. Existem em toda tabela
    # testável — inclusive nas do Fisher, e nas que passaram do limite do cálculo
    # exato: o V não depende do p.
    x2_sem_correcao: float | None = None
    v_de_cramer: float | None = None
    motivo: str = ""
    avisos: tuple[str, ...] = ()

    @property
    def faltantes(self) -> int:
        return self.total - self.validos

    @property
    def colunas(self) -> tuple[str, str]:
        return (self.variavel_1, self.variavel_2)

    @property
    def rotulo(self) -> str:
        return f"{self.rotulo_1}{SINAL}{self.rotulo_2}"

    @property
    def testado(self) -> bool:
        return self.p is not None

    @property
    def celula_do_teste(self) -> str:
        """
        O que vai para a coluna `teste` da tabela.

        O nome do teste, quando houve; e o motivo no lugar dele quando não houve,
        como a coluna `leitura` da normalidade faz com o impedimento — o motivo
        ocupa o lugar do resultado, e não some junto com ele.
        """
        if self.teste and self.p is not None:
            return self.teste
        if self.teste:
            return f"{self.teste} (não calculado)"
        return f"não testado: {self.motivo}"

    @property
    def justificativa(self) -> str:
        """
        A frase que explica a linha — a nota do `.csv` e a linha do terminal.

        Uma frase só, montada aqui, para que o arquivo e a tela digam a mesma coisa
        com as mesmas casas.
        """
        cabeca = f"{self.rotulo}: "
        if self.cochran is None:
            return f"{cabeca}não testado — {self.motivo}."
        cochran = self.cochran
        partes = [
            f"{self.contingencia.dimensoes}, n = {self.validos}",
            f"menor esperada {numero(cochran.menor_esperada, 2)}",
            f"{cochran.abaixo} de {cochran.caselas} caselas com esperada abaixo de "
            f"{numero(ESPERADA_DE_REFERENCIA)} ({percentual(cochran.abaixo, cochran.caselas)}%)",
        ]
        escolha = f"{self.teste[0].lower()}{self.teste[1:]}"
        if self.estatistica is not None and self.gl is not None:
            escolha += f" (X² = {numero(self.estatistica, 2)}; {self.gl} gl)"
        if self.p is None:
            escolha += f" — não calculado: {self.motivo}"
        return f"{cabeca}{'; '.join(partes)} → {escolha}."

    def como_detalhe(self) -> dict[str, Any]:
        """
        Os números deste par, para o manifesto.

        A tabela de contingência vai inteira: é pouco, e é o que responde "de onde
        saiu esse p?" sem reabrir o banco.
        """
        cochran = self.cochran
        return {
            "variavel_1": self.variavel_1,
            "variavel_2": self.variavel_2,
            "n": self.validos,
            "faltantes": self.faltantes,
            "dimensoes": self.contingencia.dimensoes,
            "categorias_1": list(self.contingencia.categorias_1),
            "categorias_2": list(self.contingencia.categorias_2),
            "contagens": [list(linha) for linha in self.contingencia.contagens],
            "menor_esperada": _arredondar(cochran.menor_esperada) if cochran else None,
            "caselas_abaixo_de_5": cochran.abaixo if cochran else None,
            "caselas": cochran.caselas if cochran else None,
            "cochran": cochran.atende if cochran else None,
            "teste": self.teste or None,
            "estatistica": _arredondar(self.estatistica),
            "gl": self.gl,
            "p": _arredondar(self.p),
            "x2_sem_correcao": _arredondar(self.x2_sem_correcao),
            "v_de_cramer": _arredondar(self.v_de_cramer),
            "motivo": self.motivo or None,
        }


@dataclass(frozen=True)
class ForaDaAssociacao:
    """
    Uma variável do dicionário que não está em par nenhum, e por quê.
    """

    variavel: str
    tipo: str
    motivo: str


@dataclass(frozen=True)
class Associacao:
    """
    A rodada inteira, decidida. É daqui que saem os arquivos e o terminal.
    """

    ficha: Ficha
    banco: Banco
    pares: tuple[ParTestado, ...]
    fora: tuple[ForaDaAssociacao, ...]
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
        for par in self.pares:
            for coluna in par.colunas:
                if coluna not in vistas:
                    vistas.append(coluna)
        return tuple(vistas)

    @property
    def testados(self) -> tuple[ParTestado, ...]:
        return tuple(par for par in self.pares if par.testado)

    def quantos(self, teste: str) -> int:
        """
        Quantos pares **foram testados** com este teste. O Fisher que passou do
        limite do cálculo não conta: a soma tem de bater com `testados`.
        """
        return sum(1 for par in self.pares if par.teste == teste and par.testado)


@dataclass(frozen=True)
class PlanoAssociacao:
    """
    Tudo o que a `associacao` faria, decidido e ainda não escrito.

    Imutável como os planos das outras fases, e pela mesma razão: entre a simulação
    e a execução ninguém altera um caminho em trânsito.
    """

    associacao: Associacao
    pasta: Path
    arquivamento: tuple[Path, Path] | None
    manifesto: Manifesto
    texto_manifesto: str

    @property
    def raiz(self) -> Path:
        return self.associacao.raiz

    @property
    def tabela(self) -> Tabela:
        return self.associacao.tabela

    @property
    def arquivos(self) -> tuple[str, ...]:
        return (self.tabela.nome, ARQUIVO_MANIFESTO)


@dataclass(frozen=True)
class ResultadoAssociacao:
    """
    O que a execução de fato escreveu.
    """

    criados: tuple[Path, ...] = ()
    arquivado: tuple[Path, Path] | None = None
    avisos: tuple[str, ...] = ()


# Casos de uso


def preparar_associacao(
    raiz: Path,
    aba: str | None = None,
    conferir: bool = True,
    agora: datetime | None = None,
) -> PlanoAssociacao:
    """
    Lê os pares da ficha, abre o banco, testa cada par e monta o plano. Não
    escreve nada.

    A lista da ficha é conferida **antes** de abrir o banco, como no cruzamento: um
    par escrito fora do formato é o engano mais provável deste comando, e
    descobri-lo não deve custar a releitura do `sha256` de um banco grande.

    Raises:
        FichaError, BancoError, DicionarioInvalidoError e as recusas declaradas
        acima.
    """
    raiz = Path(raiz)
    quando = agora or datetime.now()

    pedidos = pares_da_ficha(raiz)

    banco = abrir(raiz, aba=aba, conferir=conferir)
    ficha = ler_ficha(raiz)
    linhas = conferir_dicionario(
        raiz,
        banco,
        ausente=DicionarioAusenteError,
        desatualizado=DicionarioDesatualizadoError,
        analise="a associação",
    )
    associacao = associar(banco, ficha, linhas, pedidos, quando)

    pasta = pasta_da_analise(raiz, PASTA_ASSOCIACAO)
    manifesto = montar_manifesto(associacao, linhas)

    return PlanoAssociacao(
        associacao=associacao,
        pasta=pasta,
        arquivamento=arquivamento_da_rodada(raiz, pasta, quando, PASTA_ASSOCIACAO),
        manifesto=manifesto,
        texto_manifesto=texto_do_manifesto(manifesto),
    )


def executar_associacao(plano: PlanoAssociacao) -> ResultadoAssociacao:
    """
    Escreve o plano no disco. Não decide mais nada.

    A ordem é a da Fase 5: arquiva a rodada anterior, cria a pasta, escreve a
    tabela, e só então o `manifesto.json` — o recibo vem depois do que ele
    descreve. Uma falha no meio desfaz o que já foi feito, inclusive devolvendo a
    pasta arquivada ao lugar, e a exceção continua subindo inteira.
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
            anotar(plano.raiz, _acao_do_historico(plano), plano.associacao.quando)
        except OSError as erro:
            avisos.append(
                "A associação foi escrita, mas não consegui escrever no "
                f"historico.md: {erro}"
            )

    except Exception:
        for passo in reversed(desfazer):
            try:
                passo()
            except OSError:
                avisos.append(
                    "Falhei ao desfazer uma etapa. Confira "
                    f"{PASTA_ANALISES}/{PASTA_ASSOCIACAO} e {PASTA_ANTIGAS} antes "
                    "de rodar de novo."
                )
        raise

    return ResultadoAssociacao(
        criados=tuple(criados), arquivado=arquivado, avisos=tuple(avisos)
    )


def associar(
    banco: Banco,
    ficha: Ficha,
    linhas_do_dicionario: Sequence[Linha],
    pedidos: Sequence[tuple[str, str]],
    quando: datetime | None = None,
    limite: int = LIMITE_DO_CALCULO_EXATO,
) -> Associacao:
    """
    Testa cada par pedido, obedecendo ao dicionário. Função pura.

    O miolo testável, como o `cruzar` do cruzamento e o `avaliar` da normalidade:
    um `DataFrame` montado à mão, uma lista de `Linha` e os pares entram, e as
    afirmações são sobre a tabela — sem pasta de projeto e sem disco.

    Args:
        pedidos: os pares como `pares_da_ficha` os devolve — a forma "uma contra
            várias" já desdobrada, na ordem da ficha.
        limite: o `LIMITE_DO_CALCULO_EXATO`, injetável para o teste que confere o
            que acontece quando ele é atingido.

    Raises:
        SemParesError, ParInvalidoError, VariavelIncompativelError
    """
    quadro = banco.quadro
    total = int(quadro.shape[0])

    if not pedidos:
        raise SemParesError(_mensagem_sem_pares(linhas_do_dicionario))

    pares = _conferir_pares(pedidos, linhas_do_dicionario)

    # Só as variáveis dos pares vão para a recusa: a conferência é a da Fase 5, e o
    # escopo é deste comando.
    envolvidas: list[Linha] = []
    for par in pares:
        for linha in (par.primeira, par.segunda):
            if linha not in envolvidas:
                envolvidas.append(linha)
    recusar_incompativeis(quadro, envolvidas, erro=VariavelIncompativelError)

    testados = tuple(_testar_par(quadro, par, total, limite) for par in pares)

    nos_pares = {coluna for par in testados for coluna in par.colunas}
    fora = tuple(
        ForaDaAssociacao(linha.variavel, linha.tipo, _motivo_de_fora(linha))
        for linha in linhas_do_dicionario
        if linha.variavel not in nos_pares
    )

    avisos = list(banco.avisos)
    avisos += [aviso for par in testados for aviso in par.avisos]

    return Associacao(
        ficha=ficha,
        banco=banco,
        pares=testados,
        fora=fora,
        avisos=tuple(avisos),
        quando=quando or datetime.now(),
        tabela=_tabela(testados, total),
    )


# Um par


def contingencia(quadro: pd.DataFrame, primeira: Linha, segunda: Linha) -> Contingencia:
    """
    A tabela de contingência de um par, contada como o cruzamento conta.

    **O código conta, o rótulo imprime** — a regra do `_cruzar_par`. Os valores
    passam pela `serie_de_texto` da descritiva (o código lido como `1.0` vira `1`)
    e pelo `rotulo_de` do dicionário (o `1` vira `Feminino`), e a contagem é feita
    **sobre os rótulos**: dois códigos com o mesmo rótulo somam na mesma linha.

    Os faltantes são por par: entra quem respondeu as duas, e ninguém mais.
    """
    serie_1 = _coluna(quadro, primeira.variavel)
    serie_2 = _coluna(quadro, segunda.variavel)
    if serie_1 is None or serie_2 is None:  # pragma: no cover - a recusa já barrou
        raise VariavelIncompativelError(
            f"`{primeira.variavel}` ou `{segunda.variavel}` não existe no banco."
        )

    respondeu = serie_1.notna() & serie_2.notna()
    rotulos_1 = [primeira.rotulo_de(v) for v in serie_de_texto(serie_1[respondeu])]
    rotulos_2 = [segunda.rotulo_de(v) for v in serie_de_texto(serie_2[respondeu])]
    contagem = Counter(zip(rotulos_1, rotulos_2, strict=True))

    categorias_1 = _na_ordem_do_dicionario(set(rotulos_1), primeira)
    categorias_2 = _na_ordem_do_dicionario(set(rotulos_2), segunda)
    return Contingencia(
        categorias_1=categorias_1,
        categorias_2=categorias_2,
        contagens=tuple(
            tuple(contagem.get((a, b), 0) for b in categorias_2) for a in categorias_1
        ),
    )


def _testar_par(quadro: pd.DataFrame, par: Par, total: int, limite: int) -> ParTestado:
    """
    Conta, aplica a regra de Cochran e roda o teste que ela escolheu.
    """
    tabela = contingencia(quadro, par.primeira, par.segunda)
    validos = tabela.n
    base = {
        "variavel_1": par.primeira.variavel,
        "variavel_2": par.segunda.variavel,
        "rotulo_1": par.primeira.rotulo or par.primeira.variavel,
        "rotulo_2": par.segunda.rotulo or par.segunda.variavel,
        "total": total,
        "validos": validos,
        "contingencia": tabela,
    }
    nome_do_par = f"`{par.primeira.variavel}`{SINAL}`{par.segunda.variavel}`"

    if not validos:
        motivo = "nenhum caso com resposta nas duas variáveis"
        return ParTestado(
            **base,
            motivo=motivo,
            avisos=(f"{nome_do_par}: {motivo}. A linha saiu sem teste.",),
        )

    if not tabela.testavel:
        uma_so = (
            base["rotulo_1"] if len(tabela.categorias_1) < 2 else base["rotulo_2"]
        )
        motivo = f"uma categoria só em {uma_so}"
        return ParTestado(
            **base,
            motivo=motivo,
            avisos=(
                f"{nome_do_par}: entre os {validos} caso(s) com as duas respostas, "
                f"{uma_so} tem uma categoria só — não há associação a testar. A "
                "linha saiu sem teste. Uma variável que não varia costuma ser "
                "critério de inclusão do estudo.",
            ),
        )

    esperadas = tabela.esperadas()
    cochran = regra_de_cochran(esperadas)
    sem_correcao = _estatistica_de_pearson(tabela.contagens, esperadas)
    base["x2_sem_correcao"] = sem_correcao
    base["v_de_cramer"] = _v_de_cramer(sem_correcao, tabela.contagens)

    if cochran.atende:
        estatistica, gl, p, yates = qui_quadrado(tabela.contagens)
        return ParTestado(
            **base,
            teste=TESTE_YATES if yates else TESTE_QUI_QUADRADO,
            p=p,
            estatistica=estatistica,
            gl=gl,
            cochran=cochran,
        )

    try:
        p = fisher_exato(tabela.contagens, limite)
    except CalculoExatoGrandeError:
        motivo = "tabela grande demais para o cálculo exato"
        operacoes = f"{limite:,}".replace(",", ".")
        return ParTestado(
            **base,
            teste=TESTE_FISHER,
            cochran=cochran,
            motivo=motivo,
            avisos=(
                f"{nome_do_par}: a regra de Cochran mandou para o exato de Fisher, e a "
                f"tabela {tabela.dimensoes} com {validos} casos passou do limite do "
                f"cálculo exato ({operacoes} operações). O p não foi calculado. O "
                "`fisher.test` do R tem o mesmo tipo de teto — o `workspace` — e para "
                "com `FEXACT error` quando passa dele. Agrupar categorias no "
                f"{ARQUIVO_DICIONARIO} — dois códigos com o mesmo rótulo, `1=Sim|2=Sim` "
                "— encurta a tabela e costuma resolver.",
            ),
        )
    return ParTestado(**base, teste=TESTE_FISHER, p=p, cochran=cochran)


def _na_ordem_do_dicionario(observados: set[str], linha: Linha) -> tuple[str, ...]:
    """
    Os rótulos observados, na ordem declarada no dicionário; o resto depois, em
    ordem alfabética.

    A ordem não muda nenhum p — o qui-quadrado e o Fisher são os mesmos para
    qualquer permutação de linhas e colunas —, mas muda o manifesto, e duas rodadas
    sobre o mesmo banco precisam dar o mesmo arquivo.
    """
    ordem: list[str] = []
    for codigo in linha.categorias_ordem:
        rotulo = linha.rotulo_de(codigo)
        if rotulo in observados and rotulo not in ordem:
            ordem.append(rotulo)
    return tuple(ordem + sorted(observados - set(ordem)))


# A regra e os testes


def regra_de_cochran(esperadas: Sequence[Sequence[float]]) -> Cochran:
    """
    Mede a tabela pela regra de Cochran. A decisão está em `Cochran.atende`.
    """
    todas = [float(e) for linha in esperadas for e in linha]
    return Cochran(
        menor_esperada=min(todas),
        abaixo=sum(1 for e in todas if e < ESPERADA_DE_REFERENCIA),
        caselas=len(todas),
    )


def qui_quadrado(contagens: Sequence[Sequence[int]]) -> tuple[float, int, float, bool]:
    """
    O `chisq.test(x)` do R, com o padrão `correct = TRUE`. Devolve
    `(X², graus de liberdade, p, com_yates)`.

    Transcrito do código do R, linha por linha, porque é curto e porque o detalhe
    está numa linha só:

        if (correct && nrow(x) == 2L && ncol(x) == 2L) {
            YATES <- min(0.5, abs(x - E))
        } else YATES <- 0
        STATISTIC <- sum((abs(x - E) - YATES)^2 / E)

    A correção de Yates entra **só na 2×2**, e nunca é maior do que a própria
    diferença: o `min` é sobre a tabela inteira, então quando o observado já está a
    menos de meio caso do esperado a estatística dá zero e o p dá 1. O `scipy` faz
    a mesma coisa desde a versão 1.7 — o teste confere os dois.

    O `scipy` entra só na distribuição do qui-quadrado, e dentro da função, como no
    `normalidade.py`: nenhum comando que não testa nada paga o import.
    """
    from scipy import stats

    esperadas = _esperadas(contagens)
    linhas, colunas = len(contagens), len(contagens[0])
    diferencas = [
        abs(contagens[i][j] - esperadas[i][j])
        for i in range(linhas)
        for j in range(colunas)
    ]
    yates = linhas == 2 and colunas == 2
    correcao = min(0.5, min(diferencas)) if yates else 0.0

    estatistica = _estatistica_de_pearson(contagens, esperadas, correcao)
    gl = (linhas - 1) * (colunas - 1)
    p = float(stats.chi2.sf(estatistica, gl))
    return estatistica, gl, p, yates


def v_de_cramer(contagens: Sequence[Sequence[int]]) -> float:
    """
    O V de Cramér: `√(X² / (n · (k − 1)))`, com `k` o menor número de categorias
    entre as duas variáveis.

    **O X² é o de Pearson sem correção de continuidade** — o do
    `chisq.test(x, correct = FALSE)` do R —, e isso vale para toda linha da tabela,
    qualquer que seja o teste que a regra de Cochran escolheu para ela. É a
    definição do V, e é o que o mantém comparável entre os pares: com o X² corrigido
    por Yates, o V de uma 2×2 mudaria conforme o teste, e duas tabelas iguais
    teriam dois tamanhos de associação.

    Vai de 0 a 1, não tem sinal, e na 2×2 é o |φ|. O `min(1, …)` só segura o erro
    de arredondamento de uma associação perfeita — o V nunca passa de 1.
    """
    return _v_de_cramer(_estatistica_de_pearson(contagens, _esperadas(contagens)), contagens)


def _v_de_cramer(sem_correcao: float, contagens: Sequence[Sequence[int]]) -> float:
    n = sum(sum(linha) for linha in contagens)
    menor = min(len(contagens), len(contagens[0]))
    return min(1.0, math.sqrt(sem_correcao / (n * (menor - 1))))


def _estatistica_de_pearson(
    contagens: Sequence[Sequence[int]],
    esperadas: Sequence[Sequence[float]],
    correcao: float = 0.0,
) -> float:
    """
    `Σ (|O − E| − correção)² / E` — a do qui-quadrado com Yates quando a correção
    vem, e a do V de Cramér quando não vem. Uma conta só para as duas.
    """
    return math.fsum(
        (abs(contagens[i][j] - esperadas[i][j]) - correcao) ** 2 / esperadas[i][j]
        for i in range(len(contagens))
        for j in range(len(contagens[0]))
    )


def fisher_exato(
    contagens: Sequence[Sequence[int]], limite: int = LIMITE_DO_CALCULO_EXATO
) -> float:
    """
    O `fisher.test(x)` do R, bilateral: a 2×2 pela hipergeométrica, a maior pelo
    algoritmo de rede, exato.

    O p é a soma das probabilidades de todas as tabelas com as mesmas margens e
    probabilidade **menor ou igual** à da tabela observada — a definição do R, e a
    que o `test_associacao.py` confere contra a força bruta.

    Raises:
        CalculoExatoGrandeError: a tabela maior que 2×2 passou do `limite`.
    """
    tabela = [[int(x) for x in linha] for linha in contagens]
    if len(tabela) == 2 and len(tabela[0]) == 2:
        return _fisher_2x2(tabela)
    return _fisher_rede(tabela, limite)


def _fisher_2x2(tabela: list[list[int]]) -> float:
    """
    A 2×2, transcrita do `fisher.test` do R.

        m <- sum(x[, 1L]); n <- sum(x[, 2L]); k <- sum(x[1L, ]); x <- x[1L, 1L]
        lo <- max(0L, k - n); hi <- min(k, m)
        logdc <- dhyper(lo:hi, m, n, k, log = TRUE)
        d <- exp(logdc - max(logdc)); d <- d / sum(d)
        relErr <- 1 + 10^(-7)
        sum(d[d <= d[x - lo + 1] * relErr])

    A normalização por `max(logdc)` antes do `exp` é a do R, e é o que mantém a
    conta de pé em tabela com n na casa dos milhares.
    """
    (a, b), (c, d) = tabela
    m, n, k = a + c, b + d, a + b
    lo, hi = max(0, k - n), min(k, m)

    def log_hiper(x: int) -> float:
        return (
            _log_combinacoes(m, x) + _log_combinacoes(n, k - x) - _log_combinacoes(m + n, k)
        )

    logdc = [log_hiper(x) for x in range(lo, hi + 1)]
    maior = max(logdc)
    densidades = [math.exp(v - maior) for v in logdc]
    soma = math.fsum(densidades)
    densidades = [v / soma for v in densidades]
    observada = densidades[a - lo]
    p = math.fsum(v for v in densidades if v <= observada * (1 + FOLGA_2X2))
    return max(0.0, min(1.0, p))


def _fisher_rede(tabela: list[list[int]], limite: int) -> float:
    """
    A tabela maior que 2×2, exata, pelo algoritmo de rede de Mehta e Patel (1983).

    **A rede.** As tabelas com as margens observadas são montadas uma coluna de
    cada vez. O que falta distribuir depois de k colunas — os totais de linha
    restantes — é um **nó** da rede, e cada forma de preencher a coluna seguinte é
    um **arco**. Toda tabela é um caminho do primeiro nó ao último, e a
    probabilidade dela é o produto dos arcos: `c_j! / Π n_ij!` por coluna, vezes a
    constante `Π r_i! / n!`. O que falta distribuir é guardado em ordem crescente,
    porque o futuro de um nó só depende do conjunto dos totais restantes, e não de
    qual linha tem qual — é o que faz caminhos diferentes se encontrarem no mesmo
    nó.

    **O passado.** Cada nó guarda os valores de passado que chegaram a ele, e dois
    caminhos com o mesmo passado viram um só, com a massa somada.

    **A poda.** Para cada nó há um teto para o melhor futuro possível e um piso
    para o pior. Um passado que, somado ao melhor futuro, ainda fica abaixo do
    limiar tem **todas** as continuações contando para o p — e a massa delas tem
    forma fechada, `N'! / Π r'_i!`. Um que, somado ao pior futuro, fica acima, não
    tem nenhuma. Só o que fica entre os dois segue para o nó seguinte.

    O teto e o piso são calculados coluna por coluna, cada uma sozinha — a mais
    equilibrada possível para o teto, a mais concentrada para o piso. São mais
    frouxos do que os do FEXACT, que resolve a rede inteira para achá-los; o preço
    é podar um pouco menos, e o ganho é não percorrer a rede toda antes de começar.
    A resposta é a mesma: a poda só descarta o que tem certeza de descartar.

    **A folga** é a do FEXACT, somada ao logaritmo da probabilidade observada.

    As massas são guardadas já multiplicadas pelo futuro do nó — a probabilidade de
    todas as tabelas que passam por ali —, e por isso ficam sempre entre 0 e 1:
    nada estoura, e só some por arredondamento o que não mudaria a terceira casa de
    p-valor nenhum.
    """
    # O estado da rede é a dimensão menor: menos linhas por nó, menos nós.
    if len(tabela) > len(tabela[0]):
        tabela = [list(coluna) for coluna in zip(*tabela, strict=True)]

    linhas = [sum(linha) for linha in tabela]
    por_coluna = [list(coluna) for coluna in zip(*tabela, strict=True)]
    n = sum(linhas)
    lf = [math.lgamma(i + 1) for i in range(n + 1)]

    constante = math.fsum(lf[r] for r in linhas) - lf[n]
    observada = constante + math.fsum(
        lf[sum(coluna)] - math.fsum(lf[x] for x in coluna) for coluna in por_coluna
    )
    limiar = observada + FOLGA_RXC

    # As colunas maiores primeiro: é a ordem que menos nós criou nas tabelas de
    # referência. A ordem não muda o p — as tabelas são as mesmas.
    colunas = sorted((sum(coluna) for coluna in por_coluna), reverse=True)
    ultima = len(colunas) - 1
    gasto = 0

    def equilibrada(total: int, tetos: tuple[int, ...]) -> float:
        # A coluna mais equilibrada que cabe nos tetos: o maior arco possível.
        falta, restantes, soma = total, len(tetos), 0.0
        for teto in tetos:  # em ordem crescente
            if teto <= falta // restantes:
                soma += lf[teto]
                falta -= teto
                restantes -= 1
            else:
                q, r = divmod(falta, restantes)
                return lf[total] - soma - (restantes - r) * lf[q] - r * lf[q + 1]
        return lf[total] - soma

    def concentrada(total: int, tetos: tuple[int, ...]) -> float:
        # A coluna mais concentrada que cabe nos tetos: o menor arco possível.
        falta, soma = total, 0.0
        for teto in reversed(tetos):
            parte = teto if teto < falta else falta
            soma += lf[parte]
            falta -= parte
            if not falta:
                break
        return lf[total] - soma

    @lru_cache(maxsize=None)
    def limites(k: int, resto: tuple[int, ...]) -> tuple[float, float]:
        # (teto do melhor futuro, piso do pior) depois de k colunas.
        if k > ultima:
            return 0.0, 0.0
        if k == ultima:  # a última coluna é forçada: leva o que sobrou
            valor = lf[colunas[k]] - math.fsum(lf[x] for x in resto)
            return valor, valor
        teto = sum(equilibrada(colunas[j], resto) for j in range(k, ultima + 1))
        piso = sum(concentrada(colunas[j], resto) for j in range(k, ultima + 1))
        return teto, piso

    def log_futuro(resto: tuple[int, ...]) -> float:
        return lf[sum(resto)] - math.fsum(lf[x] for x in resto)

    p = 0.0
    raiz = tuple(sorted(linhas))
    futuros = {raiz: log_futuro(raiz)}
    # Nó -> {passado arredondado: (passado, massa)}.
    atual: dict[tuple[int, ...], dict[float, tuple[float, float]]] = {
        raiz: {0.0: (constante, 1.0)}
    }

    for k, total in enumerate(colunas):
        proximo: dict[tuple[int, ...], dict[float, tuple[float, float]]] = {}
        for resto, entradas in atual.items():
            ordenadas = sorted(entradas.values())
            passados = [passado for passado, _ in ordenadas]
            acumuladas: list[float] = []
            soma = 0.0
            for _, massa in ordenadas:
                soma += massa
                acumuladas.append(soma)

            arcos, enumeradas = _arcos(resto, total, lf)
            gasto += enumeradas
            if gasto > limite:
                raise CalculoExatoGrandeError(
                    f"o cálculo exato passou de {limite} operações"
                )

            for (filho, arco), multiplicidade in arcos.items():
                teto, piso = limites(k + 1, filho)
                futuro = futuros.get(filho)
                if futuro is None:
                    futuro = futuros[filho] = log_futuro(filho)
                fator = multiplicidade * math.exp(arco + futuro - futuros[resto])

                entram = bisect_right(passados, limiar - arco - teto)
                if entram:
                    p += acumuladas[entram - 1] * fator
                seguem = bisect_right(passados, limiar - arco - piso, lo=entram)
                if seguem > entram:
                    gasto += seguem - entram
                    if gasto > limite:
                        raise CalculoExatoGrandeError(
                            f"o cálculo exato passou de {limite} operações"
                        )
                    destino = proximo.setdefault(filho, {})
                    for passado, massa in ordenadas[entram:seguem]:
                        novo = passado + arco
                        chave = round(novo, 9)
                        anterior = destino.get(chave)
                        if anterior is None:
                            destino[chave] = (novo, massa * fator)
                        else:
                            destino[chave] = (anterior[0], anterior[1] + massa * fator)
        atual = proximo

    return max(0.0, min(1.0, p))


def _arcos(
    resto: tuple[int, ...], total: int, lf: list[float]
) -> tuple[dict[tuple[tuple[int, ...], float], int], int]:
    """
    As formas de preencher a próxima coluna a partir de um nó, já agrupadas.

    Duas colunas que levam ao mesmo nó com o mesmo arco — o que acontece sempre
    que dois totais restantes são iguais — viram uma entrada só, com a
    multiplicidade contada. A chave leva o arco arredondado, porque dois arcos
    iguais somados em ordens diferentes podem diferir na última casa.

    Devolve `{(nó seguinte, arco): quantas colunas}` — o arco da chave é o valor
    exato da primeira coluna encontrada — e quantas colunas foram enumeradas, que
    é o trabalho que o limite do cálculo conta.
    """
    agrupados: dict[tuple[tuple[int, ...], float], list] = {}
    for filho, arco in _colunas_possiveis(resto, total, lf):
        chave = (filho, round(arco, 9))
        grupo = agrupados.get(chave)
        if grupo is None:
            agrupados[chave] = [arco, 1]
        else:
            grupo[1] += 1

    enumeradas = sum(quantas for _, quantas in agrupados.values())
    arcos = {(filho, arco): quantas for (filho, _), (arco, quantas) in agrupados.items()}
    return arcos, enumeradas


def _colunas_possiveis(resto: tuple[int, ...], total: int, lf: list[float]):
    """
    Cada forma de preencher a próxima coluna: `(nó seguinte, arco)`.

    Com duas e três linhas — as tabelas 2 × k e 3 × k, as mais comuns — o laço é
    escrito por extenso, porque é aqui que o cálculo passa quase todo o tempo e o
    caminho genérico gasta mais montando tuplas do que fazendo conta. O genérico
    serve a qualquer número de linhas, e o teste confere os dois contra a força
    bruta.
    """
    base = lf[total]
    if len(resto) == 2:
        r0, r1 = resto
        for x0 in range(max(0, total - r1), min(r0, total) + 1):
            x1 = total - x0
            a, b = r0 - x0, r1 - x1
            yield ((a, b) if a <= b else (b, a)), base - lf[x0] - lf[x1]
        return

    if len(resto) == 3:
        r0, r1, r2 = resto
        for x0 in range(max(0, total - r1 - r2), min(r0, total) + 1):
            falta = total - x0
            a = r0 - x0
            parcial = base - lf[x0]
            for x1 in range(max(0, falta - r2), min(r1, falta) + 1):
                x2 = falta - x1
                b, c = r1 - x1, r2 - x2
                if a <= b:
                    filho = (a, b, c) if b <= c else ((a, c, b) if a <= c else (c, a, b))
                else:
                    filho = (b, a, c) if a <= c else ((b, c, a) if b <= c else (c, b, a))
                yield filho, parcial - lf[x1] - lf[x2]
        return

    linhas = len(resto)
    sufixo = [0] * (linhas + 1)
    for i in range(linhas - 1, -1, -1):
        sufixo[i] = sufixo[i + 1] + resto[i]
    pilha: list[tuple[int, int, tuple[int, ...]]] = [(0, total, ())]
    while pilha:
        i, falta, prefixo = pilha.pop()
        if i == linhas - 1:
            coluna = (*prefixo, falta)
            arco = base
            for x in coluna:
                arco -= lf[x]
            yield tuple(sorted([r - x for r, x in zip(resto, coluna, strict=True)])), arco
            continue
        menor = max(0, falta - sufixo[i + 1])
        maior = min(resto[i], falta)
        for x in range(maior, menor - 1, -1):
            pilha.append((i + 1, falta - x, (*prefixo, x)))


def _esperadas(contagens: Sequence[Sequence[int]]) -> tuple[tuple[float, ...], ...]:
    linhas = [sum(linha) for linha in contagens]
    colunas = [sum(coluna) for coluna in zip(*contagens, strict=True)]
    n = sum(linhas)
    return tuple(tuple(r * c / n for c in colunas) for r in linhas)


def _log_combinacoes(n: int, k: int) -> float:
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


# A tabela


def _tabela(pares: tuple[ParTestado, ...], total: int) -> Tabela:
    """
    Uma tabela só, com uma linha por par, na ordem da ficha.

    As seis colunas pedidas — `variável 1`, `variável 2`, `n`, `teste`, `p-valor` e
    `V de Cramér` —, com os **rótulos** do dicionário nas duas primeiras, que é o que
    o cliente lê. O resto do que decide cada linha — a dimensão da tabela, a menor
    esperada, quantas caselas abaixo de 5, o X² e os graus de liberdade — vai para
    as notas do `.csv`, uma frase por par, e para o manifesto.
    """
    corpo = tuple(
        (
            par.rotulo_1,
            par.rotulo_2,
            str(par.validos),
            par.celula_do_teste,
            valor_p(par.p),
            _formatar_v(par.v_de_cramer),
        )
        for par in pares
    )
    notas = (
        "teste escolhido pela regra de Cochran, a do fisher.test do R: qui-quadrado "
        f"quando nenhuma frequência esperada é menor que {numero(ESPERADA_MINIMA)} e no "
        f"máximo {PROPORCAO_TOLERADA:.0%} das caselas têm esperada menor que "
        f"{numero(ESPERADA_DE_REFERENCIA)}; senão, exato de Fisher.",
        "qui-quadrado de Pearson, como o chisq.test do R: nas tabelas 2×2, com a "
        "correção de continuidade de Yates.",
        "exato de Fisher bilateral, como o fisher.test do R: nas tabelas 2×2 pela "
        "distribuição hipergeométrica; nas maiores, exato pelo algoritmo de rede, sem "
        "simulação.",
        f"n: casos com resposta nas duas variáveis, de {total} linhas do banco; os "
        "faltantes são por par.",
        f"valor-p abaixo de {numero(MENOR_P, 3)} sai como `< {numero(MENOR_P, 3)}`; ele "
        "nunca é zero.",
        "cada linha é um teste; não há correção para comparações múltiplas.",
        "V de Cramér: √(X² / (n × (k − 1))), com k o menor número de categorias entre "
        "as duas variáveis e o X² de Pearson sem correção de continuidade — o do "
        "chisq.test(x, correct = FALSE) do R —, em toda linha, qualquer que seja o "
        "teste dela.",
        "o V vai de 0 (nenhuma associação) a 1 (associação perfeita), não indica "
        "direção e, na tabela 2×2, é o |φ|. Em tabela pequena — a que a regra de "
        "Cochran manda para o Fisher — ele tende a superestimar a associação.",
    ) + tuple(par.justificativa for par in pares)

    return Tabela(
        nome=ARQUIVO_TABELA,
        especie="associacao",
        # Vazia de propósito: esta tabela fala de vários pares.
        variavel="",
        titulo="Testes de associação",
        colunas=("variável 1", "variável 2", "n", "teste", "p-valor", "V de Cramér"),
        linhas=corpo,
        notas=notas,
    )


# Os pares da ficha


def pares_da_ficha(raiz: Path) -> tuple[tuple[str, str], ...]:
    """
    A lista `associacao:` do `projeto.yaml`, conferida na forma e desdobrada.

    Duas formas de item, e as duas podem conviver:

        - [sexo, desfecho]                            # um par
        - desfecho: [sexo, escolaridade, tabagismo]   # uma contra várias

    A segunda devolve um par por nome da lista, com `desfecho` na frente, na ordem
    em que foram escritos. Um nome só depois dos dois-pontos (`- desfecho: sexo`)
    vale como a lista de um nome.

    Devolve vazio quando a chave não existe ou está vazia — quem recusa isso é o
    `associar`, que tem o dicionário na mão para escrever quais categóricas
    existem. Formato errado recusa em vez de ignorar: um item que o comando pulasse
    em silêncio é o pior dos dois mundos — você escreveu, e não valeu.

    Lida pelo `ficha.bloco`, e não abrindo o YAML aqui: o `ficha.py` é o único
    módulo do pacote que abre o `projeto.yaml`.

    Raises:
        ParInvalidoError
    """
    bruto = bloco(raiz, PASTA_ASSOCIACAO)
    if bruto is None:
        return ()
    if not isinstance(bruto, list):
        raise ParInvalidoError(
            f"A chave `{PASTA_ASSOCIACAO}:` do {ARQUIVO_PROJETO} deveria ser uma lista, "
            f"e é {_descrever_valor(bruto)}.\n\n"
            f"Escreva assim, um item por linha:\n\n{EXEMPLO_DA_FICHA}"
        )

    pares: list[tuple[str, str]] = []
    problemas: list[str] = []
    for posicao, item in enumerate(bruto, start=1):
        if isinstance(item, list):
            nomes = [_nome(nome) for nome in item]
            if len(item) != 2 or not all(nomes):
                problemas.append(
                    f"  {posicao}º item: {_descrever_valor(item)} — "
                    + (
                        f"{len(item)} nomes; um par tem dois. Para testar uma variável "
                        f"contra várias, escreva `- {nomes[0] or 'desfecho'}: "
                        f"[{', '.join(n for n in nomes[1:] if n) or 'sexo, escolaridade'}]`."
                        if len(item) > 2
                        else "um par tem dois nomes, e os dois preenchidos."
                    )
                )
                continue
            pares.append((nomes[0], nomes[1]))
        elif isinstance(item, dict) and item:
            for chave, valor in item.items():
                primeira = _nome(chave)
                outras = valor if isinstance(valor, list) else [valor]
                nomes = [_nome(nome) for nome in outras]
                if not primeira or not nomes or not all(nomes):
                    problemas.append(
                        f"  {posicao}º item: `{chave}: {_descrever_valor(valor)}` — "
                        "depois dos dois-pontos vem a lista das variáveis a testar "
                        f"contra `{chave}`, com pelo menos um nome."
                    )
                    continue
                pares += [(primeira, outra) for outra in nomes]
        else:
            problemas.append(
                f"  {posicao}º item: {_descrever_valor(item)} — um par se escreve entre "
                "colchetes, `[sexo, desfecho]`, e uma variável contra várias com "
                "dois-pontos, `desfecho: [sexo, escolaridade]`."
            )

    if problemas:
        raise ParInvalidoError(
            f"A lista `{PASTA_ASSOCIACAO}:` do {ARQUIVO_PROJETO} tem "
            f"{len(problemas)} item(ns) fora do formato. Nada foi gerado.\n\n"
            + "\n".join(problemas)
            + f"\n\nEscreva assim, um item por linha:\n\n{EXEMPLO_DA_FICHA}"
        )
    return tuple(pares)


def _nome(valor: Any) -> str:
    """
    O nome de uma variável, como a ficha o trouxe; vazio quando não é um nome.

    Lista e bloco dentro da lista não são nome — é o `[[sexo, desfecho]]` digitado
    com um colchete a mais.
    """
    if valor is None or isinstance(valor, list | dict | bool):
        return ""
    return str(valor).strip()


def _conferir_pares(
    pedidos: Sequence[tuple[str, str]], linhas: Sequence[Linha]
) -> list[Par]:
    """
    Confere cada par contra o dicionário, e recusa listando todos os problemas.

    As mesmas cinco coisas do cruzamento, com o mesmo conserto cada uma: o nome não
    está no dicionário; a variável está marcada `ignorar` ou fora desta versão do
    banco; ela não é `categorica`; é a mesma variável duas vezes; ou o par já foi
    pedido — inclusive na ordem inversa, ou uma vez na forma de par e outra dentro
    de uma "uma contra várias". O teste é simétrico, e o mesmo par duas vezes daria
    duas linhas com o mesmo p.
    """
    por_nome = {linha.variavel: linha for linha in linhas}
    pares: list[Par] = []
    problemas: list[str] = []
    vistos: dict[frozenset[str], str] = {}

    for primeira, segunda in pedidos:
        escrito = f"[{primeira}, {segunda}]"

        if primeira == segunda:
            problemas.append(f"  {escrito} — a mesma variável duas vezes")
            continue

        chave = frozenset((primeira, segunda))
        if chave in vistos:
            problemas.append(
                f"  {escrito} — repete {vistos[chave]}; o teste é o mesmo nas duas "
                "ordens, e a tabela sairia com duas linhas iguais"
            )
            continue
        vistos[chave] = escrito

        motivos = [
            motivo
            for motivo in (
                _motivo_de_recusa(nome, por_nome.get(nome)) for nome in (primeira, segunda)
            )
            if motivo
        ]
        if motivos:
            problemas.append(f"  {escrito} — " + "; ".join(motivos))
            continue

        pares.append(Par(primeira=por_nome[primeira], segunda=por_nome[segunda]))

    if problemas:
        raise ParInvalidoError(
            f"A lista `{PASTA_ASSOCIACAO}:` do {ARQUIVO_PROJETO} tem {len(problemas)} "
            "par(es) que não podem ser testados. Nada foi gerado.\n\n"
            + "\n".join(problemas)
            + "\n\nA associação é entre duas categóricas. Uma numérica de poucos "
            "valores — código 0/1, escala de 1 a 5 — entra se estiver marcada "
            f"`categorica` no {ARQUIVO_DICIONARIO}, que é o que o `flatcap perfil` "
            "propõe para ela.\n\n"
            f"Corrija o nome na lista do {ARQUIVO_PROJETO} — ele é o da coluna "
            f"`variavel` do {ARQUIVO_DICIONARIO} —, ou o `tipo` no dicionário, e rode "
            "de novo."
        )
    return pares


def _motivo_de_recusa(nome: str, linha: Linha | None) -> str:
    if linha is None:
        return f"`{nome}` não está no {ARQUIVO_DICIONARIO}"
    if not linha.no_banco:
        return f"`{nome}` não está nesta versão do banco (`no_banco = nao`)"
    if linha.tipo == IGNORAR:
        return f"`{nome}` está marcada `ignorar` no {ARQUIVO_DICIONARIO}"
    if linha.tipo != CATEGORICA:
        return f"`{nome}` está marcada `{linha.tipo}` no {ARQUIVO_DICIONARIO}"
    return ""


def _descrever_valor(valor: Any) -> str:
    if isinstance(valor, list):
        return "[" + ", ".join(str(item) for item in valor) + "]"
    if isinstance(valor, dict):
        return "um bloco `chave: valor`"
    if valor is None:
        return "vazio"
    if isinstance(valor, str):
        return f"`{valor}`"
    return f"`{valor}` ({type(valor).__name__})"


# O manifesto


def montar_manifesto(associacao: Associacao, linhas: Sequence[Linha]) -> Manifesto:
    """
    Traduz a rodada para o índice que o relatório vai ler.

    **Um item só**, como na normalidade: a seção do documento é uma tabela que fala
    de todos os pares. O `colunas` do item diz quais colunas do banco entraram — a
    união dos pares —, que é o que mantém as conferências do relatório certas para
    uma seção que não é de uma variável. Os números de cada par, com a tabela de
    contingência inteira, vão em `detalhes`.
    """
    banco = associacao.banco
    leitura = banco.leitura
    ficha = associacao.ficha

    item = ItemDoManifesto(
        variavel="",
        slug=PASTA_ASSOCIACAO,
        rotulo="Associação",
        tipo=ANALISE_ASSOCIACAO,
        n=banco.linhas,
        faltantes=0,
        colunas=associacao.colunas_usadas,
        artefatos=(
            Artefato(
                arquivo=associacao.tabela.nome,
                especie=associacao.tabela.especie,
                formato="csv",
                titulo=associacao.tabela.titulo,
            ),
        ),
        detalhes={
            "pares": [par.como_detalhe() for par in associacao.pares],
            "testados": len(associacao.testados),
            "qui_quadrado": associacao.quantos(TESTE_QUI_QUADRADO),
            "qui_quadrado_com_yates": associacao.quantos(TESTE_YATES),
            "fisher": associacao.quantos(TESTE_FISHER),
        },
        avisos=tuple(aviso for par in associacao.pares for aviso in par.avisos),
    )

    return Manifesto(
        analise=ANALISE_ASSOCIACAO,
        flatcap=__version__,
        gerado_em=associacao.quando,
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
            "pares": f"os da lista `{PASTA_ASSOCIACAO}:` do {ARQUIVO_PROJETO}",
            "escolha_do_teste": (
                "regra de Cochran: qui-quadrado se nenhuma esperada < "
                f"{ESPERADA_MINIMA:g} e no máximo {PROPORCAO_TOLERADA:.0%} das caselas "
                f"com esperada < {ESPERADA_DE_REFERENCIA:g}; senão, exato de Fisher"
            ),
            "qui_quadrado": "Pearson; correção de Yates só nas 2×2 (chisq.test do R, "
            "correct = TRUE)",
            "fisher": "bilateral; 2×2 pela hipergeométrica (fisher.test do R, relErr "
            f"1 + {FOLGA_2X2:g}); maiores exato pelo algoritmo de rede (FEXACT, tol "
            f"{FOLGA_RXC:g}), sem simulação",
            "v_de_cramer": "√(X² / (n × (min(linhas, colunas) − 1))), com o X² de "
            "Pearson sem correção de continuidade, em todo par testável",
            "limite_do_calculo_exato": LIMITE_DO_CALCULO_EXATO,
            "faltantes": "por par",
            "comparacoes_multiplas": "nenhuma correção",
            "semente": SEMENTE,
        },
        itens=(item,),
        fora=tuple(
            {"variavel": f.variavel, "tipo": f.tipo, "motivo": f.motivo}
            for f in associacao.fora
        ),
        avisos=associacao.avisos,
    )


def _ambiente() -> dict[str, Any]:
    """
    As versões que produziram estes números.

    O `scipy` entra, porque a distribuição do qui-quadrado é dele. O `matplotlib` e
    a `fonte` saem `None` — a rodada não desenha —, e as chaves continuam lá para o
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


def _mensagem_sem_pares(linhas: Sequence[Linha]) -> str:
    categoricas = [
        linha.variavel for linha in linhas if linha.analisavel and linha.tipo == CATEGORICA
    ]
    if categoricas:
        disponiveis = (
            f"As categóricas deste {ARQUIVO_DICIONARIO} são: "
            + ", ".join(categoricas[:20])
            + (f" e mais {len(categoricas) - 20}" if len(categoricas) > 20 else "")
            + "."
        )
    else:
        disponiveis = (
            f"Nenhuma variável deste {ARQUIVO_DICIONARIO} está marcada `categorica` "
            "ainda — reveja a coluna `tipo` antes."
        )
    return (
        f"O {ARQUIVO_PROJETO} deste projeto não diz quais pares testar.\n\n"
        "Escreva a lista na ficha — um par entre colchetes, ou uma variável contra "
        f"várias com dois-pontos:\n\n{EXEMPLO_DA_FICHA}\n\n"
        f"{disponiveis} Uma numérica de poucos valores, como uma escala de 0 a 5, "
        "entra se estiver marcada `categorica`.\n\n"
        "Quais pares testar é decisão da reunião: o FlatCap não testa tudo com tudo, "
        "porque trinta variáveis dariam 435 testes."
    )


def _motivo_de_fora(linha: Linha) -> str:
    if not linha.no_banco:
        return "não está nesta versão do banco (`no_banco = nao`)"
    if linha.tipo == IGNORAR:
        return "marcada `ignorar` no dicionário"
    return f"não está em nenhum par da lista `{PASTA_ASSOCIACAO}:` do {ARQUIVO_PROJETO}"


def _acao_do_historico(plano: PlanoAssociacao) -> str:
    associacao = plano.associacao
    contagem = [
        (associacao.quantos(TESTE_QUI_QUADRADO), "qui-quadrado"),
        (associacao.quantos(TESTE_YATES), "qui-quadrado com Yates"),
        (associacao.quantos(TESTE_FISHER), "exato de Fisher"),
    ]
    testes = ", ".join(f"{quantos} {nome}" for quantos, nome in contagem if quantos)
    partes = [
        f"`flatcap associacao {associacao.ficha.record_id}` — associação de "
        f"`{associacao.banco.versao.arquivo}`: {len(associacao.pares)} par(es) da "
        f"lista `{PASTA_ASSOCIACAO}:`"
        + (f" ({testes})" if testes else "")
        + f", em `{PASTA_ANALISES}/{PASTA_ASSOCIACAO}/`."
    ]
    if plano.arquivamento is not None:
        partes.append(
            f"A rodada anterior foi para `{PASTA_ANTIGAS}/{plano.arquivamento[1].name}/`."
        )
    return " ".join(partes)


# Leitura da série e formatação


def _coluna(quadro: pd.DataFrame, nome: str) -> pd.Series | None:
    """
    A coluna do banco pelo nome, ou `None` — pela posição, como nas outras
    análises: nome repetido devolveria um `DataFrame` no lugar de uma coluna.
    """
    for posicao, coluna in enumerate(quadro.columns):
        if str(coluna) == nome:
            return quadro.iloc[:, posicao]
    return None


def _formatar_v(valor: float | None) -> str:
    """
    O V com casas fixas: `0,10` e não `0,1`.

    Casas fixas pelo motivo dos percentuais da Fase 5: a coluna é lida de cima para
    baixo, comparando pares, e uma coluna em que uns valores têm duas casas e outros
    uma é uma coluna que não alinha.
    """
    if valor is None:
        return _AUSENTE
    return f"{valor:.{CASAS_V}f}".replace(".", ",")


def _arredondar(valor: float | None) -> float | None:
    if valor is None:
        return None
    return round(float(valor), 6) if math.isfinite(float(valor)) else None


def _integridade(confere: bool | None) -> str:
    if confere is True:
        return "confere"
    if confere is False:
        return "ALTERADO"
    return "não conferida"


__all__ = [
    "ARQUIVO_TABELA",
    "CASAS_V",
    "ESPERADA_DE_REFERENCIA",
    "ESPERADA_MINIMA",
    "EXEMPLO_DA_FICHA",
    "FOLGA_2X2",
    "FOLGA_RXC",
    "LIMITE_DO_CALCULO_EXATO",
    "PROPORCAO_TOLERADA",
    "TESTE_FISHER",
    "TESTE_QUI_QUADRADO",
    "TESTE_YATES",
    "Associacao",
    "AssociacaoError",
    "CalculoExatoGrandeError",
    "Cochran",
    "Contingencia",
    "DicionarioAusenteError",
    "DicionarioDesatualizadoError",
    "ForaDaAssociacao",
    "Par",
    "ParInvalidoError",
    "ParTestado",
    "PlanoAssociacao",
    "ResultadoAssociacao",
    "SemParesError",
    "VariavelIncompativelError",
    "associar",
    "contingencia",
    "executar_associacao",
    "fisher_exato",
    "montar_manifesto",
    "pares_da_ficha",
    "preparar_associacao",
    "qui_quadrado",
    "regra_de_cochran",
    "v_de_cramer",
]
