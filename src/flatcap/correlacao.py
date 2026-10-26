# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-FileCopyrightText: 1995-2024 The R Core Team
# SPDX-FileCopyrightText: 2003-2024 The R Foundation
# SPDX-FileCopyrightText: 1975 Royal Statistical Society
# SPDX-License-Identifier: GPL-3.0-or-later
"""
A correlação — Pearson, Spearman ou Kendall, escolhido pelos pressupostos de cada par.

Responde ao passo 2b do fluxo, e é a primeira análise entre duas numéricas da Fase
7. Para cada par pedido na ficha, uma linha de tabela:

    variável 1  variável 2    n  método    coeficiente  IC 95%         p-valor
    Idade       IMC         178  Pearson          0,31  0,17 a 0,44    < 0,001
    Idade       Renda       150  Spearman         0,12  -0,04 a 0,28     0,142
    Dor         Ansiedade   180  Kendall          0,27  0,17 a 0,36    < 0,001

E um gráfico de dispersão por par, que é a parte da verificação dos pressupostos
que nenhum teste faz: linearidade, valor extremo, grupos.

Segue o padrão das Fases 2 a 6, decidir e escrever separados:

    plano = preparar_correlacao(raiz)   # abre o banco, calcula, não toca no disco
    executar_correlacao(plano)          # só escreve

E, como elas, **não fala com o REDCap**. Recebe `Path`, não `Config`.

## Quais pares

Os que estiverem escritos na ficha, e só eles, nas duas formas da associação —
mais um terceiro nome opcional no par, que é o método:

    correlacao:
      - [idade, imc]                    # a regra escolhe o método
      - idade: [pressao, colesterol]    # uma contra várias, pela regra
      - [dor, ansiedade, kendall]       # o método escrito manda

Sem a lista, o comando recusa, pelo motivo de sempre: trinta numéricas dão 435
pares, e correlacionar tudo com tudo é *p-hacking* feito por máquina. Qual par
correlacionar é hipótese, e hipótese se escreve na reunião.

## A decisão central: a regra dos pressupostos escolhe, e a ficha pode discordar

É a pergunta que abriu esta análise — dá para escolher o coeficiente sozinho? — e
a resposta é a que a associação deu com a regra de Cochran: dá, se a regra estiver
escrita, for a mesma para todo par e deixar o motivo impresso. Três passos, nesta
ordem:

1. **Kendall** quando alguma das duas variáveis tem **até 10 valores distintos, com
   repetição** — uma escala ou um código. Numa escala de 0 a 5 a maior parte dos
   pares de casos empata, e o tau-b é o coeficiente que conta os empates na própria
   variância.
2. **Spearman** quando alguma das duas é `categorica` — ela entra pela ordem dos
   códigos, e ordem não é distância — ou quando o **Shapiro-Wilk rejeita a
   normal** em alguma das duas, sobre os casos do par.
3. **Pearson** nos outros casos: as duas contínuas, e nenhuma com a normal
   rejeitada.

O limite de 10 é o `POUCOS_DISTINTOS` da normalidade, que é o `LIMITE_UNICOS_CODIGO`
do perfil: é a mesma pergunta — isto é contínuo ou é código? — feita pela terceira
vez, e três limites para ela é como o perfil propõe uma coisa e a correlação faz
outra sobre a mesma coluna.

**O método escrito no par tem precedência.** A regra é um ponto de partida
defensável, e não um veredito, e ela tem o limite que o `normalidade.py` descreve
no topo: o p do Shapiro-Wilk depende do n. Com poucos casos ele quase não rejeita,
e a regra escolheria o Pearson por falta de evidência; com muitos ele rejeita
desvio irrelevante, e tudo vira Spearman — o que custa pouco, porque o Spearman
continua válido. Por isso três coisas saem escritas: a frase de cada escolha, com
os números que a decidiram, nas notas do `.csv` e no terminal; um aviso quando a
regra escolhe o Pearson com menos de 20 pares; e outro quando o método escrito na
ficha contraria a regra — a decisão é sua, e fica registrado que foi contra ela.

## Como o R faz

Os três são o `cor.test` do R, bilaterais, com os padrões dele:

* **Pearson**: t com n − 2 graus de liberdade. O `scipy` faz igual.
* **Spearman**: o ρ é o Pearson dos postos médios. O p é **exato** até n = 1290
  sem empates — pela contagem das permutações até n = 9 e pela série de Edgeworth
  do algoritmo AS 89 acima disso —, e pela aproximação t com empates ou acima de
  1290. **O `scipy` não faz isso**: ele usa sempre a aproximação t, e no exemplo do
  atum da documentação do R (Hollander e Wolfe, n = 9) dá p = 0,088 onde o R dá
  0,097. Então o AS 89 está transcrito aqui, do `prho.c` do R, linha por linha — a
  exceção à regra "importar a aritmética, escrever as decisões", pelo mesmo motivo
  do Fisher da associação.
* **Kendall**: o tau-b. O p é exato abaixo de n = 50 sem empates, e pela
  aproximação normal com a variância corrigida para empates nos outros casos, sem
  correção de continuidade. O `scipy` calcula os dois como o R, mas o critério
  automático dele troca de um para o outro em n = 33, e não em 50 — então quem
  escolhe é este módulo, com o critério do R.

O `test_correlacao.py` confere os três contra números tirados do próprio R.

## O intervalo de confiança

95%, pela transformação de Fisher nos três. O `cor.test` só dá intervalo para o
Pearson, com erro-padrão `1/√(n − 3)`, e é esse o daqui. Nos outros dois o
erro-padrão da transformação é outro, e usar o do Pearson daria um intervalo
estreito demais:

* Spearman: `√((1 + ρ²/2) / (n − 3))`, de Bonett e Wright (2000);
* Kendall: `√(0,437 / (n − 4))`, de Fieller, Hartley e Pearson (1957), que é o
  que Bonett e Wright recomendam.

As duas fórmulas vão para as notas do `.csv`, para o intervalo poder ser refeito
à mão.

## A categórica que entra

Uma escala marcada `categorica` no dicionário — dor de 0 a 5, um item Likert —
entra, porque é o caso típico do Spearman e do Kendall. Com três condições:

* **pela ordem numérica dos códigos**, e só se o código for número. Uma categórica
  em texto (`Fundamental`, `Médio`, `Superior`) é recusada: a ordem do
  `categorias_ordem` pode ser a de frequência, que é a que o perfil propõe, e uma
  correlação calculada sobre ela sairia com cara de resultado;
* **nunca pelo Pearson** — nem pela regra, nem escrito na ficha;
* **o agrupamento do dicionário não vale aqui**: dois códigos com o mesmo rótulo
  continuam sendo dois valores da escala. Sai um aviso dizendo isso.

Uma categórica nominal (sexo, estado civil) não tem ordem, e não tem correlação. O
FlatCap não tem como saber qual é qual, e a nota do `.csv` diz isso.

## O que ele reaproveita, e por quê

**As recusas de dicionário e de tipo são as da descritiva**, com a classe de erro
deste módulo. **O Shapiro-Wilk é o da normalidade**, pela mesma função — as
barreiras e os avisos dele valem aqui também. **O p-valor sai pela mesma função da
normalidade e da associação**: três casas, e `< 0,001` abaixo disso.

A normalidade aqui é medida **sobre os casos do par**, e não sobre a coluna
inteira, porque é sobre eles que o coeficiente é calculado. Sem faltante no par, o
p é o mesmo da tabela de normalidade; com faltante, pode ser outro, e o n do par
está na linha.

## O que ele deliberadamente não faz

**Não diz se a correlação é fraca ou forte.** Os cortes (Cohen, Mukaka) são
convenções de área, e o Kendall sai tipicamente menor que o Spearman para a mesma
relação — um corte único para os dois estaria errado para um deles. A leitura é
sua, como a do V de Cramér.

**Não corrige para comparações múltiplas.** Cada linha é um teste.

**Não desenha reta.** Ela afirma uma linearidade que o Spearman e o Kendall não
afirmam, e no Pearson repete o que o coeficiente já diz. A dispersão mostra os
pontos, e o ponto cresce onde vários casos coincidem — o que numa escala é quase
sempre.
"""

from __future__ import annotations

import math
import sys
import unicodedata
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from functools import cache
from itertools import permutations
from pathlib import Path
from typing import Any

import pandas as pd

from . import __version__
from .banco import Banco, abrir
from .descritiva import arquivamento as arquivamento_da_rodada
from .descritiva import conferir_dicionario, numero, recusar_incompativeis
from .descritiva import slug as slug_do_nome
from .dicionario import ARQUIVO_DICIONARIO, CATEGORICA, IGNORAR, NUMERICA, Linha
from .ficha import Ficha, bloco, escrever_atomico
from .ficha import ler as ler_ficha
from .manifesto import (
    ANALISE_CORRELACAO,
    ARQUIVO_MANIFESTO,
    SEMENTE,
    Artefato,
    Grafico,
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
    PASTA_CORRELACAO,
    anotar,
    pasta_da_analise,
)

ARQUIVO_TABELA = "correlacao.csv"
PREFIXO_FIGURA = "disp_"

# Os nomes que vão para a coluna `método`.
PEARSON = "Pearson"
SPEARMAN = "Spearman"
KENDALL = "Kendall"

# Como cada método se escreve na ficha — o terceiro nome do par. Minúsculo e sem
# acento, que é como se digita; a tabela sai com o nome próprio.
METODOS: dict[str, str] = {"pearson": PEARSON, "spearman": SPEARMAN, "kendall": KENDALL}

# A regra. Todos com nome e aqui em cima, pelo motivo de sempre: número solto no
# meio de uma função é decisão que ninguém consegue rever.
#
# Até este número de valores distintos, com repetição, a variável é escala ou
# código, e o par vai para o Kendall. É o mesmo limite da normalidade e do perfil.
POUCOS_VALORES = POUCOS_DISTINTOS

# Abaixo disto não há teste: com dois pontos, qualquer par está sobre uma reta. É
# também o mínimo do Shapiro-Wilk e o do `cor.test` para o Pearson.
MINIMO_DE_PARES = 3

# Os limites do `cor.test` do R, com o nome que eles têm lá.
MAXIMO_EXATO_SPEARMAN = 1290  # `n <= 1290`: acima disso n(n² − 1) estoura o inteiro do C
LIMITE_EXATO_KENDALL = 50  # `exact <- (n < 50)`
PERMUTACOES_SPEARMAN = 9  # `n_small` do `prho.c`: até aqui, a contagem exata

# O intervalo.
CONFIANCA = 0.95
VARIANCIA_KENDALL = 0.437  # Fieller, Hartley e Pearson (1957), com n − 4

# O coeficiente sai com duas casas, que é como correlação se escreve num artigo; o
# manifesto guarda o número inteiro.
CASAS_COEFICIENTE = 2

# O sinal entre os dois rótulos nas notas e nos avisos. O mesmo do cruzamento e
# da associação.
SINAL = " × "

# Os coeficientes da série de Edgeworth do AS 89, como estão no `prho.c` do R —
# (C) 2000-2024 The R Core Team; ver o `NOTICE.md`.
_EDGEWORTH = (
    0.2274, 0.2531, 0.1745, 0.0758, 0.1033, 0.3932,
    0.0879, 0.0151, 0.0072, 0.0831, 0.0131, 4.6e-4,
)

_AUSENTE = "—"

# O exemplo que as mensagens escrevem. Um lugar só, para a recusa e o `--help`
# nunca ensinarem duas formas diferentes de escrever a mesma lista.
EXEMPLO_DA_FICHA = f"""  {PASTA_CORRELACAO}:
    - [idade, imc]
    - idade: [pressao, colesterol]
    - [dor, ansiedade, kendall]"""


class CorrelacaoError(RuntimeError):
    """
    Falha ao gerar a correlação, já traduzida para o usuário.

    Erro próprio pela regra da casa: a CLI captura esta classe e transforma em
    painel com o nome do comando que o usuário rodou. Qualquer outra exceção é bug
    de verdade e deve subir com o traceback inteiro.
    """


class DicionarioAusenteError(CorrelacaoError):
    """
    O projeto não tem `dicionario.csv`. Não há o que obedecer.
    """


class DicionarioDesatualizadoError(CorrelacaoError):
    """
    O banco tem colunas que o dicionário desconhece.
    """


class VariavelIncompativelError(CorrelacaoError):
    """
    O dicionário promete `numerica` e a coluna chegou como texto, ou declara uma
    variável que o banco não tem.

    A mesma recusa da Fase 5, pela mesma função — aplicada só às variáveis dos
    pares, como no cruzamento e na associação.
    """


class SemParesError(CorrelacaoError):
    """
    A ficha não diz quais pares correlacionar.
    """


class ParInvalidoError(CorrelacaoError):
    """
    A lista `correlacao:` da ficha tem item que não serve.

    Formato errado, método que não existe, nome fora do dicionário, variável que
    não é numérica nem categórica, Pearson pedido sobre uma categórica, a mesma
    variável duas vezes ou o mesmo par duas vezes. A mensagem lista **todos** de
    uma vez, pela regra da Fase 5.
    """


class CategoricaSemCodigoError(CorrelacaoError):
    """
    Uma categórica de um par chegou em texto, e não tem ordem numérica.

    Recusa, e não conversão pela ordem do `categorias_ordem`: aquela ordem pode ser
    a de frequência, que é a que o perfil propõe, e uma correlação calculada sobre
    ela sairia com cara de resultado.
    """


# O que sai no disco


@dataclass(frozen=True)
class Pedido:
    """
    Um par como a ficha o escreve: dois nomes e, quando houver, o método.

    `metodo` vazio quer dizer "a regra escolhe"; preenchido, é um dos três de
    `METODOS`, já com o nome próprio.
    """

    primeira: str
    segunda: str
    metodo: str = ""


@dataclass(frozen=True)
class Par:
    """
    Um par pedido na ficha, já conferido contra o dicionário.

    `primeira` vai para a coluna `variável 1` e para o eixo x da dispersão, e é a
    variável da frente na forma "uma contra várias".
    """

    primeira: Linha
    segunda: Linha
    metodo: str = ""


@dataclass(frozen=True)
class Normal:
    """
    O Shapiro-Wilk de uma variável, sobre os casos do par.

    Os quatro campos são o que o `normalidade.shapiro` devolve: o W e o p quando o
    teste rodou, a frase do impedimento quando não rodou, e o aviso do `scipy`
    quando houve um.
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
class Pressupostos:
    """
    O que a regra olhou num par.

    `normal_1` e `normal_2` ficam `None` para a categórica: ela não tem
    normalidade a testar, e é a própria categoria que a manda para fora do
    Pearson.
    """

    n: int
    distintos_1: int
    distintos_2: int
    normal_1: Normal | None = None
    normal_2: Normal | None = None

    def escala(self, lado: int) -> bool:
        """
        Até `POUCOS_VALORES` valores distintos, **com repetição**.

        A repetição é a metade que importa: com oito casos, uma variável contínua
        tem no máximo oito valores distintos e nenhum empate — e não é escala.
        """
        distintos = self.distintos_1 if lado == 1 else self.distintos_2
        return distintos <= POUCOS_VALORES and distintos < self.n


@dataclass(frozen=True)
class Escolha:
    """
    Qual método rodou, e de onde ele veio.

    `da_regra` é o que a regra escolheria mesmo quando a ficha mandou outro: é o
    que permite escrever "contra a regra" na nota, com o motivo dela.
    `pela_normalidade` diz se foi o Shapiro-Wilk que decidiu — é quando o aviso
    dele, se houver, precisa ir junto.
    """

    metodo: str
    da_regra: str
    motivo: str
    pela_ficha: bool = False
    pela_normalidade: bool = False

    @property
    def contra_a_regra(self) -> bool:
        return self.pela_ficha and self.metodo != self.da_regra


@dataclass(frozen=True)
class Coeficiente:
    """
    O resultado de um dos três, como o `cor.test` do R o devolveria.

    `estatistica` é a do R: t no Pearson, S no Spearman, T (exato) ou z no Kendall
    — com o nome em `nome_da_estatistica`. `calculo_do_p` diz em palavras como o p
    saiu, porque no Spearman e no Kendall são dois caminhos diferentes conforme o
    n e os empates.
    """

    metodo: str
    valor: float
    p: float
    estatistica: float
    nome_da_estatistica: str
    gl: int | None = None
    calculo_do_p: str = ""
    ic: tuple[float, float] | None = None


@dataclass(frozen=True)
class ParCorrelacionado:
    """
    Um par, correlacionado. É uma linha da tabela, e uma figura.

    `coeficiente` fica `None` quando não houve teste; o motivo está em `motivo`, e a
    linha **sai assim mesmo** — um par pedido que sumisse da tabela seria a falta em
    que ninguém repara.
    """

    variavel_1: str
    variavel_2: str
    rotulo_1: str
    rotulo_2: str
    tipo_1: str
    tipo_2: str
    total: int
    validos: int
    slug: str = ""
    coeficiente: Coeficiente | None = None
    pressupostos: Pressupostos | None = None
    escolha: Escolha | None = None
    motivo: str = ""
    avisos: tuple[str, ...] = ()
    # Os pontos da dispersão: (x, y, quantos casos caem ali). Calculados aqui, e
    # não no `graficos.py`, pela divisão de sempre — contar é deste lado.
    pontos: tuple[tuple[float, float, int], ...] = ()

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
        return self.coeficiente is not None

    @property
    def metodo(self) -> str:
        return self.coeficiente.metodo if self.coeficiente else ""

    @property
    def celula_do_metodo(self) -> str:
        """
        O que vai para a coluna `método`: o nome do método, ou o motivo no lugar
        dele — como a coluna `teste` da associação.
        """
        if self.coeficiente is not None:
            return self.coeficiente.metodo
        return f"não testado: {self.motivo}"

    @property
    def justificativa(self) -> str:
        """
        A frase que explica a linha — a nota do `.csv` e a linha do terminal.

        Uma frase só, montada aqui, para que o arquivo e a tela digam a mesma coisa
        com as mesmas casas.
        """
        cabeca = f"{self.rotulo}: "
        if self.escolha is None or self.coeficiente is None:
            return f"{cabeca}não testado — {self.motivo}."
        escolha = self.escolha
        estatistica = _estatistica_em_texto(self.coeficiente)
        if not escolha.pela_ficha:
            return (
                f"{cabeca}n = {self.validos}; {escolha.motivo} → "
                f"{escolha.metodo} ({estatistica})."
            )
        if escolha.contra_a_regra:
            return (
                f"{cabeca}n = {self.validos}; {escolha.metodo} escrito na ficha "
                f"({estatistica}), contra a regra — ela escolheria {escolha.da_regra}: "
                f"{escolha.motivo}."
            )
        return (
            f"{cabeca}n = {self.validos}; {escolha.metodo} escrito na ficha "
            f"({estatistica}), o mesmo que a regra escolheria: {escolha.motivo}."
        )

    def como_detalhe(self) -> dict[str, Any]:
        """
        Os números deste par, para o manifesto — o que responde "de onde saiu esse
        método, e esse p?" sem reabrir o banco.
        """
        pressupostos = self.pressupostos
        coeficiente = self.coeficiente
        escolha = self.escolha
        return {
            "variavel_1": self.variavel_1,
            "variavel_2": self.variavel_2,
            "tipo_1": self.tipo_1,
            "tipo_2": self.tipo_2,
            "n": self.validos,
            "faltantes": self.faltantes,
            "distintos_1": pressupostos.distintos_1 if pressupostos else None,
            "distintos_2": pressupostos.distintos_2 if pressupostos else None,
            "shapiro_1": _normal_como_detalhe(pressupostos.normal_1) if pressupostos else None,
            "shapiro_2": _normal_como_detalhe(pressupostos.normal_2) if pressupostos else None,
            "metodo": coeficiente.metodo if coeficiente else None,
            "metodo_da_regra": escolha.da_regra if escolha else None,
            "escrito_na_ficha": escolha.pela_ficha if escolha else None,
            "motivo_da_regra": escolha.motivo if escolha else None,
            "coeficiente": _arredondar(coeficiente.valor) if coeficiente else None,
            "ic_95": (
                [_arredondar(coeficiente.ic[0]), _arredondar(coeficiente.ic[1])]
                if coeficiente and coeficiente.ic
                else None
            ),
            "estatistica": (
                {
                    "nome": coeficiente.nome_da_estatistica,
                    "valor": _arredondar(coeficiente.estatistica),
                    "gl": coeficiente.gl,
                }
                if coeficiente
                else None
            ),
            "p": _significativos(coeficiente.p) if coeficiente else None,
            "calculo_do_p": coeficiente.calculo_do_p if coeficiente else None,
            "motivo": self.motivo or None,
        }


@dataclass(frozen=True)
class ForaDaCorrelacao:
    """
    Uma variável do dicionário que não está em par nenhum, e por quê.
    """

    variavel: str
    tipo: str
    motivo: str


@dataclass(frozen=True)
class Correlacao:
    """
    A rodada inteira, decidida. É daqui que saem os arquivos e o terminal.
    """

    ficha: Ficha
    banco: Banco
    pares: tuple[ParCorrelacionado, ...]
    fora: tuple[ForaDaCorrelacao, ...]
    avisos: tuple[str, ...]
    quando: datetime
    tabela: Tabela
    graficos: tuple[Grafico, ...] = ()

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
    def testados(self) -> tuple[ParCorrelacionado, ...]:
        return tuple(par for par in self.pares if par.testado)

    @property
    def pela_ficha(self) -> tuple[ParCorrelacionado, ...]:
        return tuple(par for par in self.pares if par.escolha and par.escolha.pela_ficha)

    def quantos(self, metodo: str) -> int:
        return sum(1 for par in self.pares if par.metodo == metodo)


@dataclass(frozen=True)
class PlanoCorrelacao:
    """
    Tudo o que a `correlacao` faria, decidido e ainda não escrito.

    Imutável como os planos das outras fases, e pela mesma razão: entre a simulação
    e a execução ninguém altera um caminho em trânsito.
    """

    correlacao: Correlacao
    pasta: Path
    arquivamento: tuple[Path, Path] | None
    com_graficos: bool
    manifesto: Manifesto
    texto_manifesto: str

    @property
    def raiz(self) -> Path:
        return self.correlacao.raiz

    @property
    def tabela(self) -> Tabela:
        return self.correlacao.tabela

    @property
    def graficos(self) -> tuple[Grafico, ...]:
        return self.correlacao.graficos if self.com_graficos else ()

    @property
    def arquivos(self) -> tuple[str, ...]:
        nomes = [self.tabela.nome] + [grafico.nome for grafico in self.graficos]
        return tuple(nomes + [ARQUIVO_MANIFESTO])


@dataclass(frozen=True)
class ResultadoCorrelacao:
    """
    O que a execução de fato escreveu.
    """

    criados: tuple[Path, ...] = ()
    arquivado: tuple[Path, Path] | None = None
    avisos: tuple[str, ...] = ()


# Casos de uso


def preparar_correlacao(
    raiz: Path,
    aba: str | None = None,
    conferir: bool = True,
    com_graficos: bool = True,
    agora: datetime | None = None,
) -> PlanoCorrelacao:
    """
    Lê os pares da ficha, abre o banco, correlaciona cada par e monta o plano. Não
    escreve nada.

    A lista da ficha é conferida **antes** de abrir o banco, como no cruzamento e
    na associação: um par escrito fora do formato é o engano mais provável deste
    comando, e descobri-lo não deve custar a releitura do `sha256` de um banco
    grande.

    Args:
        com_graficos: desenhar as dispersões. Desligado, os pontos nem são
            contados e o `matplotlib` nem é importado.
        agora: relógio injetável, como nas outras fases.

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
        analise="a correlação",
    )
    correlacao = correlacionar(banco, ficha, linhas, pedidos, quando, com_graficos)

    pasta = pasta_da_analise(raiz, PASTA_CORRELACAO)
    manifesto = montar_manifesto(correlacao, linhas, com_graficos)

    return PlanoCorrelacao(
        correlacao=correlacao,
        pasta=pasta,
        arquivamento=arquivamento_da_rodada(raiz, pasta, quando, PASTA_CORRELACAO),
        com_graficos=com_graficos,
        manifesto=manifesto,
        texto_manifesto=texto_do_manifesto(manifesto),
    )


def executar_correlacao(plano: PlanoCorrelacao) -> ResultadoCorrelacao:
    """
    Escreve o plano no disco. Não decide mais nada.

    A ordem é a da Fase 5: arquiva a rodada anterior, cria a pasta, escreve a
    tabela, desenha as dispersões, e só então o `manifesto.json` — o recibo vem
    depois do que ele descreve. Uma falha no meio desfaz o que já foi feito,
    inclusive devolvendo a pasta arquivada ao lugar, e a exceção continua subindo
    inteira — o `matplotlib` incluído, que estoura com exceções próprias.
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

        if plano.com_graficos and plano.graficos:
            # O `matplotlib` entra aqui dentro, e não no topo do arquivo, pela
            # mesma razão que na Fase 5: `--sem-graficos` não deve pagar por uma
            # biblioteca que ele existe para não usar.
            from .graficos import desenhar

            for grafico in plano.graficos:
                caminho = plano.pasta / grafico.nome
                desenhar(grafico, caminho)
                criados.append(caminho)
                desfazer.append(lambda p=caminho: p.unlink(missing_ok=True))

        caminho = plano.pasta / ARQUIVO_MANIFESTO
        escrever_atomico(caminho, plano.texto_manifesto)
        criados.append(caminho)
        desfazer.append(lambda p=caminho: p.unlink(missing_ok=True))

        try:
            anotar(plano.raiz, _acao_do_historico(plano), plano.correlacao.quando)
        except OSError as erro:
            avisos.append(
                "A correlação foi escrita, mas não consegui escrever no "
                f"historico.md: {erro}"
            )

    except Exception:
        for passo in reversed(desfazer):
            try:
                passo()
            except OSError:
                avisos.append(
                    "Falhei ao desfazer uma etapa. Confira "
                    f"{PASTA_ANALISES}/{PASTA_CORRELACAO} e {PASTA_ANTIGAS} antes "
                    "de rodar de novo."
                )
        raise

    return ResultadoCorrelacao(
        criados=tuple(criados), arquivado=arquivado, avisos=tuple(avisos)
    )


def correlacionar(
    banco: Banco,
    ficha: Ficha,
    linhas_do_dicionario: Sequence[Linha],
    pedidos: Sequence[Pedido | tuple[str, ...]],
    quando: datetime | None = None,
    com_graficos: bool = True,
) -> Correlacao:
    """
    Correlaciona cada par pedido, obedecendo ao dicionário. Função pura.

    O miolo testável, como o `associar` da associação e o `avaliar` da
    normalidade: um `DataFrame` montado à mão, uma lista de `Linha` e os pares
    entram, e as afirmações são sobre a tabela — sem pasta de projeto e sem disco.

    Args:
        pedidos: os pares como `pares_da_ficha` os devolve — ou tuplas de dois
            nomes, ou de dois nomes e o método, que é como um teste os escreve.
        com_graficos: contar os pontos das dispersões.

    Raises:
        SemParesError, ParInvalidoError, VariavelIncompativelError,
        CategoricaSemCodigoError
    """
    quadro = banco.quadro
    total = int(quadro.shape[0])

    if not pedidos:
        raise SemParesError(_mensagem_sem_pares(linhas_do_dicionario))

    pares = _conferir_pares([_como_pedido(item) for item in pedidos], linhas_do_dicionario)

    # Só as variáveis dos pares vão para a recusa: a conferência é a da Fase 5, e o
    # escopo é deste comando.
    envolvidas: list[Linha] = []
    for par in pares:
        for linha in (par.primeira, par.segunda):
            if linha not in envolvidas:
                envolvidas.append(linha)
    recusar_incompativeis(quadro, envolvidas, erro=VariavelIncompativelError)
    _conferir_codigos(quadro, envolvidas)

    usados: set[str] = set()
    correlacionados = tuple(
        _correlacionar_par(
            quadro,
            par,
            total,
            slug_do_nome(f"{par.primeira.variavel} x {par.segunda.variavel}", usados),
            com_graficos,
        )
        for par in pares
    )

    nos_pares = {coluna for par in correlacionados for coluna in par.colunas}
    fora = tuple(
        ForaDaCorrelacao(linha.variavel, linha.tipo, _motivo_de_fora(linha))
        for linha in linhas_do_dicionario
        if linha.variavel not in nos_pares
    )

    avisos = list(banco.avisos)
    avisos += _avisos_de_agrupamento(envolvidas)
    avisos += [aviso for par in correlacionados for aviso in par.avisos]

    return Correlacao(
        ficha=ficha,
        banco=banco,
        pares=correlacionados,
        fora=fora,
        avisos=tuple(avisos),
        quando=quando or datetime.now(),
        tabela=_tabela(correlacionados, total),
        graficos=(
            tuple(_grafico(par) for par in correlacionados if par.pontos)
            if com_graficos
            else ()
        ),
    )


# Um par


def valores_do_par(quadro: pd.DataFrame, par: Par) -> tuple[pd.Series, pd.Series]:
    """
    Os valores das duas variáveis, como número, só dos casos que responderam as
    duas.

    Os faltantes são **por par**: entra quem respondeu as duas, e ninguém mais —
    o `complete.cases(x, y)` do `cor.test`. É o oposto do descarte por lista
    completa, que faria a correlação de `idade × imc` depender de quem respondeu
    `renda`.
    """
    serie_1 = _coluna(quadro, par.primeira.variavel)
    serie_2 = _coluna(quadro, par.segunda.variavel)
    if serie_1 is None or serie_2 is None:  # pragma: no cover - a recusa já barrou
        raise VariavelIncompativelError(
            f"`{par.primeira.variavel}` ou `{par.segunda.variavel}` não existe no banco."
        )
    respondeu = serie_1.notna() & serie_2.notna()
    return (
        serie_1[respondeu].astype("float64").reset_index(drop=True),
        serie_2[respondeu].astype("float64").reset_index(drop=True),
    )


def _correlacionar_par(
    quadro: pd.DataFrame,
    par: Par,
    total: int,
    slug: str,
    com_graficos: bool,
) -> ParCorrelacionado:
    """
    Mede os pressupostos, aplica a regra (ou obedece à ficha) e calcula.
    """
    x, y = valores_do_par(quadro, par)
    validos = int(x.shape[0])
    base = {
        "variavel_1": par.primeira.variavel,
        "variavel_2": par.segunda.variavel,
        "rotulo_1": _rotulo(par.primeira),
        "rotulo_2": _rotulo(par.segunda),
        "tipo_1": par.primeira.tipo,
        "tipo_2": par.segunda.tipo,
        "total": total,
        "validos": validos,
        "slug": slug,
    }
    nome_do_par = f"`{par.primeira.variavel}`{SINAL}`{par.segunda.variavel}`"

    if not validos:
        motivo = "nenhum caso com resposta nas duas variáveis"
        return ParCorrelacionado(
            **base, motivo=motivo, avisos=(f"{nome_do_par}: {motivo}. A linha saiu sem teste.",)
        )

    if validos < MINIMO_DE_PARES:
        motivo = (
            f"{validos} caso(s) com as duas respostas — o teste precisa de pelo menos "
            f"{MINIMO_DE_PARES}"
        )
        return ParCorrelacionado(
            **base, motivo=motivo, avisos=(f"{nome_do_par}: {motivo}. A linha saiu sem teste.",)
        )

    distintos_1, distintos_2 = int(x.nunique()), int(y.nunique())
    if distintos_1 < 2 or distintos_2 < 2:
        um_so = base["rotulo_1"] if distintos_1 < 2 else base["rotulo_2"]
        motivo = f"um valor só em {um_so}"
        return ParCorrelacionado(
            **base,
            motivo=motivo,
            avisos=(
                f"{nome_do_par}: entre os {validos} caso(s) com as duas respostas, "
                f"{um_so} tem um valor só — não há correlação a medir. A linha saiu sem "
                "teste. Uma variável que não varia costuma ser critério de inclusão do "
                "estudo.",
            ),
        )

    pressupostos = Pressupostos(
        n=validos,
        distintos_1=distintos_1,
        distintos_2=distintos_2,
        normal_1=_normal(par.primeira, x),
        normal_2=_normal(par.segunda, y),
    )
    escolha = regra(par, pressupostos)
    if par.metodo:
        escolha = replace(escolha, metodo=par.metodo, pela_ficha=True)
    coeficiente = calcular(escolha.metodo, x.to_numpy(), y.to_numpy())

    return ParCorrelacionado(
        **base,
        coeficiente=coeficiente,
        pressupostos=pressupostos,
        escolha=escolha,
        avisos=_avisos_do_par(nome_do_par, escolha, pressupostos),
        pontos=_pontos(x, y) if com_graficos else (),
    )


def _normal(linha: Linha, valores: pd.Series) -> Normal | None:
    """
    O Shapiro-Wilk da normalidade, sobre os casos do par. `None` para a
    categórica, que não tem normalidade a testar.
    """
    if linha.tipo != NUMERICA:
        return None
    w, p, impedimento, aviso = shapiro(linha.variavel, valores, int(valores.shape[0]))
    return Normal(w=w, p=p, impedimento=impedimento, aviso=aviso)


def _avisos_do_par(
    nome_do_par: str, escolha: Escolha, pressupostos: Pressupostos
) -> tuple[str, ...]:
    """
    O que a escolha precisa levar junto para o terminal e para o manifesto.

    Três casos, e cada um é um engano conhecido:

    * **Pearson pela regra com poucos pares.** Abaixo de `MINIMO_CONFIAVEL` o
      Shapiro-Wilk quase não rejeita, e a regra escolheu o Pearson por falta de
      evidência contra ele — não por evidência a favor;
    * **a ficha contra a regra.** A decisão é sua, e o aviso é o registro de que
      ela foi tomada contra o que a regra diria;
    * **o recado do `scipy` sobre o Shapiro-Wilk**, quando o teste participou da
      escolha — é o mesmo aviso da normalidade, repassado como ele veio.
    """
    avisos: list[str] = []
    if escolha.contra_a_regra:
        avisos.append(
            f"{nome_do_par}: {escolha.metodo} escrito na ficha, contra a regra — ela "
            f"escolheria {escolha.da_regra}: {escolha.motivo}. Fica o que está na ficha, "
            "e a frase vai para as notas do .csv."
        )
    if (
        escolha.metodo == PEARSON
        and not escolha.pela_ficha
        and pressupostos.n < MINIMO_CONFIAVEL
    ):
        avisos.append(
            f"{nome_do_par}: Pearson com {pressupostos.n} pares. Abaixo de "
            f"{MINIMO_CONFIAVEL} o Shapiro-Wilk quase não rejeita — «não rejeitou» aí não "
            "é evidência de normalidade. Confira a dispersão antes de ficar com ele; na "
            "dúvida, escreva `spearman` no par."
        )
    if escolha.pela_normalidade:
        for normal in (pressupostos.normal_1, pressupostos.normal_2):
            if normal is not None and normal.aviso and normal.aviso not in avisos:
                avisos.append(normal.aviso)
    return tuple(avisos)


def _pontos(x: pd.Series, y: pd.Series) -> tuple[tuple[float, float, int], ...]:
    """
    Os pontos da dispersão, com quantos casos caem em cada um.

    Numa escala de 0 a 5 cruzada com outra, 180 casos caem em 36 lugares, e um
    ponto desenhado por cima do outro esconde exatamente o que se queria ver: onde
    os casos estão. Contados aqui, o `graficos.py` só transforma a contagem em
    tamanho. Em ordem, para duas rodadas darem a mesma figura.
    """
    contagem = Counter(zip(x.tolist(), y.tolist(), strict=True))
    return tuple(
        (float(a), float(b), int(quantos)) for (a, b), quantos in sorted(contagem.items())
    )


# A regra


def regra(par: Par, pressupostos: Pressupostos) -> Escolha:
    """
    A regra dos pressupostos: o método que ela escolhe para o par, e o motivo.

    Os três passos do topo do módulo, na ordem. O motivo é a metade da frase que
    vai para as notas do `.csv` — os números que decidiram, com os rótulos do
    dicionário, que é o que se lê na tabela.

    Não olha o método escrito na ficha: quem o aplica é o `_correlacionar_par`, por
    cima do que a regra devolveu — e é assim que a nota consegue dizer o que a
    regra teria escolhido.
    """
    lados = (
        (_rotulo(par.primeira), par.primeira, pressupostos.distintos_1, pressupostos.normal_1, 1),
        (_rotulo(par.segunda), par.segunda, pressupostos.distintos_2, pressupostos.normal_2, 2),
    )

    escalas = [
        f"{rotulo} tem {distintos} valores distintos"
        for rotulo, _, distintos, _, lado in lados
        if pressupostos.escala(lado)
    ]
    if escalas:
        return _pela_regra(
            KENDALL, " e ".join(escalas) + " — escala ou código, com muitos empates"
        )

    categoricas = [rotulo for rotulo, linha, _, _, _ in lados if linha.tipo == CATEGORICA]
    if categoricas:
        verbo = "é categórica" if len(categoricas) == 1 else "são categóricas"
        return _pela_regra(
            SPEARMAN, f"{' e '.join(categoricas)} {verbo}, e entra pela ordem dos códigos"
        )

    sem_teste = [
        rotulo for rotulo, _, _, normal, _ in lados if normal is None or not normal.testada
    ]
    if sem_teste:
        return _pela_regra(
            SPEARMAN,
            f"a normalidade de {' e de '.join(sem_teste)} não pôde ser verificada",
            pela_normalidade=True,
        )

    rejeitadas = [
        f"{rotulo} ({_p_na_frase(normal.p)})"
        for rotulo, _, _, normal, _ in lados
        if normal is not None and normal.rejeita
    ]
    if rejeitadas:
        return _pela_regra(
            SPEARMAN,
            f"o Shapiro-Wilk rejeita a normal em {' e em '.join(rejeitadas)}",
            pela_normalidade=True,
        )

    valores = " e ".join(
        _p_na_frase(normal.p, com_nome=False)
        for _, _, _, normal, _ in lados
        if normal is not None
    )
    return _pela_regra(
        PEARSON,
        f"o Shapiro-Wilk não rejeita a normal em nenhuma das duas (p = {valores})",
        pela_normalidade=True,
    )


def _pela_regra(metodo: str, motivo: str, pela_normalidade: bool = False) -> Escolha:
    return Escolha(
        metodo=metodo, da_regra=metodo, motivo=motivo, pela_normalidade=pela_normalidade
    )


# Os três coeficientes, como o `cor.test` do R


def calcular(metodo: str, x: Sequence[float], y: Sequence[float]) -> Coeficiente:
    """
    O coeficiente, o p bilateral e o intervalo do método pedido.
    """
    funcoes = {PEARSON: pearson, SPEARMAN: spearman, KENDALL: kendall}
    return funcoes[metodo](x, y)


def pearson(x: Sequence[float], y: Sequence[float]) -> Coeficiente:
    """
    O `cor.test(x, y)` do R: t com n − 2 graus de liberdade, bilateral.

        STATISTIC <- c(t = sqrt(df) * r / sqrt(1 - r^2))
        PVAL <- 2 * min(pt(STATISTIC, df), pt(STATISTIC, df, lower.tail=FALSE))
    """
    from scipy import stats

    x, y = _vetores(x, y)
    n = len(x)
    r = _correlacao_linear(x, y)
    gl = n - 2
    t = _t_de(r, gl)
    p = min(1.0, 2 * min(float(stats.t.cdf(t, gl)), float(stats.t.sf(t, gl))))
    return Coeficiente(
        metodo=PEARSON,
        valor=r,
        p=p,
        estatistica=t,
        nome_da_estatistica="t",
        gl=gl,
        calculo_do_p="t de Student com n − 2 graus de liberdade",
        ic=intervalo(PEARSON, r, n),
    )


def spearman(x: Sequence[float], y: Sequence[float]) -> Coeficiente:
    """
    O `cor.test(x, y, method = "spearman")` do R, bilateral.

    O ρ é o Pearson dos postos médios. A estatística é o S, a soma dos quadrados das
    diferenças de posto — `S = (n³ − n)(1 − ρ)/6` —, e o p vem do AS 89 quando não
    há empate e n ≤ 1290, e da aproximação t nos outros casos. Transcrito do
    `cor.test.R`:

        pspearman <- function(q, n, lower.tail = TRUE) {
            if(n <= 1290 && exact)
                .Call(C_pRho, round(q) + 2*lower.tail, n, lower.tail)
            else {
                den <- (n*(n^2-1))/6
                r <- 1 - q/den
                pt(r / sqrt((1 - r^2)/(n-2)), df = n-2, lower.tail = !lower.tail)
            }
        }
        p <- if(q > (n^3 - n) / 6) pspearman(q, n, lower.tail = FALSE)
             else pspearman(q, n, lower.tail = TRUE)
        min(2 * p, 1)

    O `+ 2*lower.tail` não é enfeite: sem empate o S é sempre par, e é ele que
    transforma o "menor que" do AS 89 no "menor ou igual" da cauda inferior.

    Derivado de `src/library/stats/R/cor.test.R`, do R — (C) 1995-2022 The R Core
    Team, GPL-2.0-or-later. Origem, e os direitos autorais do original: ver o
    `NOTICE.md`.
    """
    from scipy import stats

    x, y = _vetores(x, y)
    n = len(x)
    rho = _correlacao_linear(stats.rankdata(x), stats.rankdata(y))
    s = (n**3 - n) * (1 - rho) / 6
    empates = _tem_empates(x, y)
    exato = not empates and n <= MAXIMO_EXATO_SPEARMAN

    def cauda(inferior: bool) -> float:
        if exato:
            return prho(n, round(s) + 2 * inferior, inferior)
        r = 1 - s / (n * (n * n - 1) / 6)
        t = _t_de(r, n - 2)
        return float(stats.t.sf(t, n - 2)) if inferior else float(stats.t.cdf(t, n - 2))

    p = cauda(inferior=False) if s > (n**3 - n) / 6 else cauda(inferior=True)

    if exato and n <= PERMUTACOES_SPEARMAN:
        calculo = "exato, pela contagem das permutações (AS 89)"
    elif exato:
        calculo = "exato pela série de Edgeworth (AS 89)"
    elif empates:
        calculo = "aproximação t com n − 2 graus de liberdade (há empates)"
    else:
        calculo = (
            f"aproximação t com n − 2 graus de liberdade (n acima de {MAXIMO_EXATO_SPEARMAN})"
        )
    return Coeficiente(
        metodo=SPEARMAN,
        valor=rho,
        p=min(2 * p, 1.0),
        estatistica=s,
        nome_da_estatistica="S",
        calculo_do_p=calculo,
        ic=intervalo(SPEARMAN, rho, n),
    )


def kendall(x: Sequence[float], y: Sequence[float]) -> Coeficiente:
    """
    O `cor.test(x, y, method = "kendall")` do R, bilateral: o tau-b.

    **Exato** abaixo de n = 50 sem empate — o `exact <- (n < 50)` do R —, pela
    distribuição do número de pares concordantes, que é a que o `scipy` calcula
    quando se pede `method="exact"`. Nos outros casos, pela aproximação normal com a
    variância corrigida para empates, sem correção de continuidade, transcrita do
    `cor.test.R`:

        S <- r * sqrt((T0 - T1) * (T0 - T2))
        var_S <- (v0 - vt - vu) / 18 +
            v1 / (2 * n * (n - 1)) +
                v2 / (9 * n * (n - 1) * (n - 2))
        STATISTIC <- c(z = S / sqrt(var_S))

    O `scipy` sabe fazer os dois; o critério automático dele é que é outro — ele
    passa para a aproximação acima de n = 33. Quem escolhe aqui é o critério do R.

    Derivado de `src/library/stats/R/cor.test.R`, do R — (C) 1995-2022 The R Core
    Team, GPL-2.0-or-later. Origem, e os direitos autorais do original: ver o
    `NOTICE.md`.
    """
    from scipy import stats

    x, y = _vetores(x, y)
    n = len(x)
    exato = n < LIMITE_EXATO_KENDALL and not _tem_empates(x, y)
    resultado = stats.kendalltau(
        x, y, variant="b", method="exact" if exato else "asymptotic"
    )
    tau = max(-1.0, min(1.0, float(resultado.statistic)))
    ic = intervalo(KENDALL, tau, n)

    if exato:
        # O T do R: quantos dos n(n − 1)/2 pares são concordantes.
        concordantes = round((tau + 1) * n * (n - 1) / 4)
        return Coeficiente(
            metodo=KENDALL,
            valor=tau,
            p=min(1.0, float(resultado.pvalue)),
            estatistica=float(concordantes),
            nome_da_estatistica="T",
            calculo_do_p="exato",
            ic=ic,
        )

    z = _z_de_kendall(x, y, tau)
    p = min(1.0, 2 * min(float(stats.norm.cdf(z)), float(stats.norm.sf(z))))
    return Coeficiente(
        metodo=KENDALL,
        valor=tau,
        p=p,
        estatistica=z,
        nome_da_estatistica="z",
        calculo_do_p="aproximação normal, com a variância corrigida para empates",
        ic=ic,
    )


def prho(n: int, s: float, inferior: bool) -> float:
    """
    O AS 89 (Best e Roberts, 1975), como o `prho.c` do R: `Pr[S ≥ s]`, ou
    `Pr[S < s]` quando `inferior`.

    Até n = 9, **exato**: a proporção das n! permutações com S do lado pedido — o R
    chama esse limite de `n_small`, e ele era 6 no algoritmo original. Acima disso,
    a série de Edgeworth, com os doze coeficientes do artigo:

        x = (6 (s − 1) / (n (n² − 1)) − 1) · √(n − 1)
        u = x/n · (c1 + (c2 + c3/n)/n + x² (−c4 + (c5 + c6/n)/n
              − x²/n (c7 + c8/n − x² (c9 − c10/n + x²/n (c11 − c12 x²)))))
        p = ± u · e^(−x²/2) + Φ(x)

    Transcrito linha por linha, inclusive nas duas saídas do começo — `s ≤ 0` e `s`
    acima do máximo — e no corte do fim em [0, 1], e conferido contra o R.

    Derivado de `src/library/stats/src/prho.c`, do R — (C) 2000-2024 The R Core
    Team e (C) 2003-2024 The R Foundation, GPL-2.0-or-later —, que se baseia no
    AS 89, (C) 1975 Royal Statistical Society. Origem, e os direitos autorais
    do original: ver o `NOTICE.md`.
    """
    from scipy import stats

    if n <= 1:
        raise ValueError(f"o AS 89 precisa de n ≥ 2, e veio {n}")
    p = 0.0 if inferior else 1.0
    if s <= 0:
        return p
    maximo = n * (n * n - 1.0) / 3.0
    if s > maximo:
        return 1.0 - p

    if n <= PERMUTACOES_SPEARMAN:
        contagem = _permutacoes_por_s(n)
        total = math.factorial(n)
        acima = sum(quantas for valor, quantas in enumerate(contagem) if valor >= s)
        return (total - acima if inferior else acima) / total

    c1, c2, c3, c4, c5, c6, c7, c8, c9, c10, c11, c12 = _EDGEWORTH
    b = 1 / n
    x = (6.0 * (s - 1) * b / (n * n - 1) - 1) * math.sqrt(n - 1)
    y = x * x
    u = x * b * (
        c1
        + b * (c2 + c3 * b)
        + y
        * (
            -c4
            + b * (c5 + c6 * b)
            - y * b * (c7 + c8 * b - y * (c9 - c10 * b + y * b * (c11 - c12 * y)))
        )
    )
    y = u / math.exp(y / 2.0)
    normal = float(stats.norm.cdf(x)) if inferior else float(stats.norm.sf(x))
    p = (-y if inferior else y) + normal
    return min(1.0, max(0.0, p))


@cache
def _permutacoes_por_s(n: int) -> tuple[int, ...]:
    """
    Quantas das n! permutações dão cada valor de S = Σ (i − σ(i))².

    Contadas uma vez por n e guardadas: com n = 9 são 362.880 permutações, e a
    mesma rodada pode ter vários pares pequenos.
    """
    contagem = [0] * (n * (n * n - 1) // 3 + 1)
    for permutacao in permutations(range(n)):
        s = 0
        for posicao, valor in enumerate(permutacao):
            s += (posicao - valor) ** 2
        contagem[s] += 1
    return tuple(contagem)


def intervalo(metodo: str, coeficiente: float, n: int) -> tuple[float, float] | None:
    """
    O intervalo de 95% pela transformação de Fisher: `tanh(atanh(r) ± z · EP)`.

    O erro-padrão é o que muda de um método para o outro:

    * Pearson: `1/√(n − 3)` — o do `cor.test` do R;
    * Spearman: `√((1 + ρ²/2)/(n − 3))` — Bonett e Wright (2000);
    * Kendall: `√(0,437/(n − 4))` — Fieller, Hartley e Pearson (1957).

    `None` quando o n não dá: até 3 casos no Pearson e no Spearman — o R também
    não dá intervalo aí —, e até 4 no Kendall. Com o coeficiente em ±1 a
    transformação vai ao infinito, e o intervalo é o próprio ponto, como no R.
    """
    from scipy import stats

    if metodo == KENDALL:
        if n <= 4:
            return None
        erro = math.sqrt(VARIANCIA_KENDALL / (n - 4))
    else:
        if n <= 3:
            return None
        if metodo == SPEARMAN:
            erro = math.sqrt((1 + coeficiente * coeficiente / 2) / (n - 3))
        else:
            erro = 1 / math.sqrt(n - 3)

    if abs(coeficiente) >= 1:
        return (coeficiente, coeficiente)
    centro = math.atanh(coeficiente)
    margem = float(stats.norm.ppf((1 + CONFIANCA) / 2)) * erro
    return (math.tanh(centro - margem), math.tanh(centro + margem))


def _vetores(x: Sequence[float], y: Sequence[float]):
    """
    As duas variáveis como vetores, com as três condições do cálculo conferidas.

    Quem chega aqui pelo `_correlacionar_par` já passou por elas, uma a uma, com a
    frase de cada impedimento. O `ValueError` é para quem chamar os três métodos
    direto — em teste, ou no dia em que outra análise precisar deles —, e é erro
    de programação: dado que não dá correlação não é resultado.
    """
    import numpy as np

    x = np.asarray(x, dtype="float64")
    y = np.asarray(y, dtype="float64")
    if x.shape != y.shape or x.ndim != 1:
        raise ValueError("as duas variáveis precisam ter o mesmo número de casos")
    if x.shape[0] < MINIMO_DE_PARES:
        raise ValueError(f"a correlação precisa de pelo menos {MINIMO_DE_PARES} pares")
    if len(set(x.tolist())) < 2 or len(set(y.tolist())) < 2:
        raise ValueError("uma das duas variáveis não varia: a correlação é 0/0")
    return x, y


def _correlacao_linear(x, y) -> float:
    """
    O r de Pearson, preso em [−1, 1] contra o arredondamento de uma relação
    perfeita.
    """
    import numpy as np

    return max(-1.0, min(1.0, float(np.corrcoef(x, y)[0, 1])))


def _t_de(r: float, gl: int) -> float:
    if abs(r) >= 1:
        return math.copysign(math.inf, r)
    return math.sqrt(gl) * r / math.sqrt(1 - r * r)


def _tem_empates(x, y) -> bool:
    """
    O `TIES` do R: alguma das duas tem valor repetido.
    """
    n = len(x)
    return min(len(set(x.tolist())), len(set(y.tolist()))) < n


def _z_de_kendall(x, y, tau: float) -> float:
    n = len(x)
    empates_x = [t for t in Counter(x.tolist()).values() if t > 1]
    empates_y = [t for t in Counter(y.tolist()).values() if t > 1]

    t0 = n * (n - 1) / 2
    t1 = sum(t * (t - 1) for t in empates_x) / 2
    t2 = sum(t * (t - 1) for t in empates_y) / 2
    s = tau * math.sqrt((t0 - t1) * (t0 - t2))

    v0 = n * (n - 1) * (2 * n + 5)
    vt = sum(t * (t - 1) * (2 * t + 5) for t in empates_x)
    vu = sum(t * (t - 1) * (2 * t + 5) for t in empates_y)
    v1 = sum(t * (t - 1) for t in empates_x) * sum(t * (t - 1) for t in empates_y)
    v2 = sum(t * (t - 1) * (t - 2) for t in empates_x) * sum(
        t * (t - 1) * (t - 2) for t in empates_y
    )
    variancia = (
        (v0 - vt - vu) / 18 + v1 / (2 * n * (n - 1)) + v2 / (9 * n * (n - 1) * (n - 2))
    )
    return s / math.sqrt(variancia)


# A tabela e a figura


def _tabela(pares: tuple[ParCorrelacionado, ...], total: int) -> Tabela:
    """
    Uma tabela só, com uma linha por par, na ordem da ficha.

    As sete colunas — `variável 1`, `variável 2`, `n`, `método`, `coeficiente`,
    `IC 95%` e `p-valor` —, com os **rótulos** do dicionário nas duas primeiras. O
    que decidiu cada método — os valores distintos, os p do Shapiro-Wilk — vai para
    as notas do `.csv`, uma frase por par, e para o manifesto.
    """
    corpo = tuple(
        (
            par.rotulo_1,
            par.rotulo_2,
            str(par.validos),
            par.celula_do_metodo,
            _formatar_coeficiente(par.coeficiente.valor if par.coeficiente else None),
            _formatar_intervalo(par.coeficiente.ic if par.coeficiente else None),
            valor_p(par.coeficiente.p if par.coeficiente else None),
        )
        for par in pares
    )
    menor_p = numero(MENOR_P, 3)
    notas = (
        "método escolhido pela regra dos pressupostos: Kendall quando alguma das duas "
        f"variáveis tem até {POUCOS_VALORES} valores distintos, com repetição (escala ou "
        "código, com muitos empates); senão Spearman quando alguma é categórica ou "
        f"quando o Shapiro-Wilk rejeita a normal (p < {numero(ALFA)}) em alguma das "
        "duas, sobre os casos do par; senão Pearson. O método escrito na ficha tem "
        "precedência sobre a regra.",
        "p-valor bilateral, como o cor.test do R: Pearson pelo t com n − 2 graus de "
        f"liberdade; Spearman exato (algoritmo AS 89) até n = {MAXIMO_EXATO_SPEARMAN} "
        "sem empates, e pela aproximação t nos outros casos; Kendall exato abaixo de "
        f"n = {LIMITE_EXATO_KENDALL} sem empates, e pela aproximação normal com a "
        "variância corrigida para empates nos outros casos.",
        "IC 95% pela transformação de Fisher: Pearson com erro-padrão 1/√(n − 3), como "
        "o cor.test do R; Spearman com √((1 + ρ²/2)/(n − 3)), de Bonett e Wright "
        "(2000); Kendall com √(0,437/(n − 4)), de Fieller, Hartley e Pearson (1957). "
        "O cor.test não dá intervalo para esses dois.",
        f"n: casos com resposta nas duas variáveis, de {total} linhas do banco; os "
        "faltantes são por par.",
        f"valor-p abaixo de {menor_p} sai como `< {menor_p}`; ele nunca é zero.",
        "cada linha é um teste; não há correção para comparações múltiplas.",
        "o coeficiente vai de -1 a 1 e diz o tamanho e a direção da relação: Pearson "
        "mede a relação linear; Spearman e Kendall, a monotônica. O Kendall costuma "
        "sair menor em módulo que o Spearman para a mesma relação — os dois não se "
        "comparam entre si.",
        "categórica entra pela ordem numérica dos códigos, e só por Spearman ou "
        "Kendall: isso tem sentido numa escala ordinal, e não numa categórica nominal "
        "(sexo, estado civil), que não tem ordem.",
    ) + tuple(par.justificativa for par in pares)

    return Tabela(
        nome=ARQUIVO_TABELA,
        especie="correlacao",
        # Vazia de propósito: esta tabela fala de vários pares.
        variavel="",
        titulo="Correlações",
        colunas=(
            "variável 1",
            "variável 2",
            "n",
            "método",
            "coeficiente",
            "IC 95%",
            "p-valor",
        ),
        linhas=corpo,
        notas=notas,
    )


def _grafico(par: ParCorrelacionado) -> Grafico:
    """
    A dispersão de um par: a primeira variável no eixo x, a segunda no y.

    O subtítulo é o `n = 178 · 2 sem informação` das outras figuras, e **não** traz
    o coeficiente nem o p: os dois estão na tabela da mesma seção, e repeti-los na
    figura seria publicar o mesmo número duas vezes na mesma página — o argumento
    do Q-Q. Quando algum ponto junta mais de um caso, o subtítulo diz o que o
    tamanho do ponto quer dizer, porque o documento impresso não tem legenda
    interativa.
    """
    partes = [f"n = {par.validos}"]
    if par.faltantes:
        partes.append(f"{par.faltantes} sem informação")
    if any(quantos > 1 for _, _, quantos in par.pontos):
        partes.append("o tamanho do ponto é o número de casos")
    return Grafico(
        nome=f"{PREFIXO_FIGURA}{par.slug}.png",
        especie="dispersao",
        # Vazia pelo motivo da tabela: a figura é de um par.
        variavel="",
        titulo=f"Dispersão — {par.rotulo}",
        subtitulo=" · ".join(partes),
        rotulo_categoria=par.rotulo_1,
        rotulo_valor=par.rotulo_2,
        pontos_x=tuple(a for a, _, _ in par.pontos),
        pontos_y=tuple(b for _, b, _ in par.pontos),
        contagens=tuple(quantos for _, _, quantos in par.pontos),
    )


# Os pares da ficha


def pares_da_ficha(raiz: Path) -> tuple[Pedido, ...]:
    """
    A lista `correlacao:` do `projeto.yaml`, conferida na forma e desdobrada.

    Três formas de item, e todas podem conviver:

        - [idade, imc]                    # um par; a regra escolhe o método
        - [dor, ansiedade, kendall]       # um par, com o método
        - idade: [pressao, colesterol]    # uma contra várias; a regra escolhe

    A terceira devolve um par por nome da lista, com `idade` na frente, na ordem em
    que foram escritos. O método só se escreve na forma de par: numa "uma contra
    várias" ele ficaria misturado aos nomes, e `idade: [imc, spearman]` é
    exatamente o que se escreve querendo uma coisa e dizendo outra.

    Devolve vazio quando a chave não existe ou está vazia — quem recusa isso é o
    `correlacionar`, que tem o dicionário na mão para escrever quais variáveis
    existem. Formato errado recusa em vez de ignorar: um item que o comando pulasse
    em silêncio é o pior dos dois mundos — você escreveu, e não valeu.

    Lida pelo `ficha.bloco`, e não abrindo o YAML aqui: o `ficha.py` é o único
    módulo do pacote que abre o `projeto.yaml`.

    Raises:
        ParInvalidoError
    """
    bruto = bloco(raiz, PASTA_CORRELACAO)
    if bruto is None:
        return ()
    if not isinstance(bruto, list):
        raise ParInvalidoError(
            f"A chave `{PASTA_CORRELACAO}:` do {ARQUIVO_PROJETO} deveria ser uma lista, "
            f"e é {_descrever_valor(bruto)}.\n\n"
            f"Escreva assim, um item por linha:\n\n{EXEMPLO_DA_FICHA}"
        )

    pedidos: list[Pedido] = []
    problemas: list[str] = []
    for posicao, item in enumerate(bruto, start=1):
        if isinstance(item, list):
            nomes = [_nome(nome) for nome in item]
            if len(item) == 3 and all(nomes) and metodo_escrito(nomes[2]):
                pedidos.append(Pedido(nomes[0], nomes[1], metodo_escrito(nomes[2])))
                continue
            if len(item) != 2 or not all(nomes):
                problemas.append(
                    f"  {posicao}º item: {_descrever_valor(item)} — {_o_que_falta(nomes)}"
                )
                continue
            pedidos.append(Pedido(nomes[0], nomes[1]))
        elif isinstance(item, dict) and item:
            for chave, valor in item.items():
                primeira = _nome(chave)
                outras = valor if isinstance(valor, list) else [valor]
                nomes = [_nome(nome) for nome in outras]
                if not primeira or not nomes or not all(nomes):
                    problemas.append(
                        f"  {posicao}º item: `{chave}: {_descrever_valor(valor)}` — "
                        "depois dos dois-pontos vem a lista das variáveis a correlacionar "
                        f"com `{chave}`, com pelo menos um nome."
                    )
                    continue
                metodos = [nome for nome in nomes if metodo_escrito(nome)]
                if metodos:
                    exemplo = next(
                        (nome for nome in nomes if not metodo_escrito(nome)), "imc"
                    )
                    problemas.append(
                        f"  {posicao}º item: `{chave}: {_descrever_valor(valor)}` — "
                        f"`{metodos[0]}` é um método, e na forma uma contra várias o método "
                        f"não se escreve. Para escolhê-lo, escreva cada par: "
                        f"`- [{primeira}, {exemplo}, {metodos[0].lower()}]`."
                    )
                    continue
                pedidos += [Pedido(primeira, outra) for outra in nomes]
        else:
            problemas.append(
                f"  {posicao}º item: {_descrever_valor(item)} — um par se escreve entre "
                "colchetes, `[idade, imc]`, e uma variável contra várias com dois-pontos, "
                "`idade: [imc, peso]`."
            )

    if problemas:
        raise ParInvalidoError(
            f"A lista `{PASTA_CORRELACAO}:` do {ARQUIVO_PROJETO} tem "
            f"{len(problemas)} item(ns) fora do formato. Nada foi gerado.\n\n"
            + "\n".join(problemas)
            + f"\n\nEscreva assim, um item por linha:\n\n{EXEMPLO_DA_FICHA}\n\n"
            "O terceiro nome do par, quando vem, é o método: pearson, spearman ou "
            "kendall. Sem ele, a regra dos pressupostos escolhe."
        )
    return tuple(pedidos)


def metodo_escrito(texto: str) -> str:
    """
    O método como a tabela o escreve, a partir de como ele foi digitado na ficha;
    vazio quando o texto não é um método.

    Tolerante na leitura, como o dicionário: `Spearman`, `SPEARMAN` e `spearman`
    são o mesmo, e o acento de quem escreveu `Pearsón` por engano não conta.
    """
    limpo = unicodedata.normalize("NFKD", str(texto or "")).lower().strip()
    limpo = "".join(c for c in limpo if not unicodedata.combining(c))
    return METODOS.get(limpo, "")


def _o_que_falta(nomes: list[str]) -> str:
    if len(nomes) == 3 and all(nomes):
        return (
            f"`{nomes[2]}` não é um método. O terceiro nome do par, quando vem, é o "
            "método — `pearson`, `spearman` ou `kendall`. Para correlacionar uma "
            f"variável com várias, escreva `- {nomes[0]}: [{nomes[1]}, {nomes[2]}]`."
        )
    if len(nomes) > 3:
        outras = ", ".join(nome for nome in nomes[1:] if nome) or "imc, peso"
        return (
            f"{len(nomes)} nomes; um par tem dois, mais o método quando houver. Para "
            f"correlacionar uma variável com várias, escreva `- {nomes[0] or 'idade'}: "
            f"[{outras}]`."
        )
    return "um par tem dois nomes, e os dois preenchidos."


def _como_pedido(item: Pedido | tuple[str, ...]) -> Pedido:
    if isinstance(item, Pedido):
        return item
    primeira, segunda, *resto = item
    metodo = metodo_escrito(resto[0]) if resto else ""
    if resto and not metodo:
        raise ParInvalidoError(f"`{resto[0]}` não é um método: pearson, spearman ou kendall.")
    return Pedido(str(primeira), str(segunda), metodo)


def _nome(valor: Any) -> str:
    """
    O nome de uma variável, como a ficha o trouxe; vazio quando não é um nome.

    Lista e bloco dentro da lista não são nome — é o `[[idade, imc]]` digitado com
    um colchete a mais.
    """
    if valor is None or isinstance(valor, list | dict | bool):
        return ""
    return str(valor).strip()


def _conferir_pares(pedidos: Sequence[Pedido], linhas: Sequence[Linha]) -> list[Par]:
    """
    Confere cada par contra o dicionário, e recusa listando todos os problemas.

    As cinco coisas da associação, mais uma: o nome não está no dicionário; a
    variável está marcada `ignorar` ou fora desta versão do banco; ela não é
    numérica nem categórica; é a mesma variável duas vezes; o par já foi pedido —
    inclusive na ordem inversa, ou com outro método, que seria correlacionar o
    mesmo par duas vezes e ficar com o p que convier. E a sexta: Pearson escrito
    sobre uma categórica, que só tem ordem.
    """
    por_nome = {linha.variavel: linha for linha in linhas}
    pares: list[Par] = []
    problemas: list[str] = []
    vistos: dict[frozenset[str], str] = {}

    for pedido in pedidos:
        escrito = f"[{pedido.primeira}, {pedido.segunda}" + (
            f", {pedido.metodo.lower()}]" if pedido.metodo else "]"
        )

        if pedido.primeira == pedido.segunda:
            problemas.append(f"  {escrito} — a mesma variável duas vezes")
            continue

        chave = frozenset((pedido.primeira, pedido.segunda))
        if chave in vistos:
            problemas.append(
                f"  {escrito} — repete {vistos[chave]}; a correlação é a mesma nas duas "
                "ordens, e um par se correlaciona uma vez, por um método"
            )
            continue
        vistos[chave] = escrito

        motivos = [
            motivo
            for motivo in (
                _motivo_de_recusa(nome, por_nome.get(nome))
                for nome in (pedido.primeira, pedido.segunda)
            )
            if motivo
        ]
        if not motivos and pedido.metodo == PEARSON:
            motivos += [
                f"Pearson supõe variável numérica, e `{nome}` está marcada `categorica` — "
                "escreva spearman ou kendall, ou deixe a regra escolher"
                for nome in (pedido.primeira, pedido.segunda)
                if por_nome[nome].tipo == CATEGORICA
            ]
        if motivos:
            problemas.append(f"  {escrito} — " + "; ".join(motivos))
            continue

        pares.append(
            Par(
                primeira=por_nome[pedido.primeira],
                segunda=por_nome[pedido.segunda],
                metodo=pedido.metodo,
            )
        )

    if problemas:
        raise ParInvalidoError(
            f"A lista `{PASTA_CORRELACAO}:` do {ARQUIVO_PROJETO} tem {len(problemas)} "
            "par(es) que não podem ser correlacionados. Nada foi gerado.\n\n"
            + "\n".join(problemas)
            + "\n\nA correlação é entre duas numéricas — ou uma escala marcada "
            f"`categorica` no {ARQUIVO_DICIONARIO}, com código numérico, que entra pela "
            "ordem dos códigos e só por Spearman ou Kendall.\n\n"
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
    if linha.tipo not in (NUMERICA, CATEGORICA):
        return f"`{nome}` está marcada `{linha.tipo}` no {ARQUIVO_DICIONARIO}"
    return ""


def _conferir_codigos(quadro: pd.DataFrame, envolvidas: Sequence[Linha]) -> None:
    """
    Recusa a rodada quando uma categórica de um par chegou em texto.

    Depois do banco aberto, porque a pergunta é sobre a coluna: `1`, `2`, `3` têm
    ordem; `Fundamental`, `Médio`, `Superior` também têm, mas ela não está em lugar
    nenhum que o FlatCap possa ler sem adivinhar.
    """
    problemas: list[str] = []
    for linha in envolvidas:
        if linha.tipo != CATEGORICA:
            continue
        serie = _coluna(quadro, linha.variavel)
        if serie is None:  # pragma: no cover - `recusar_incompativeis` já barrou
            continue
        preenchidos = serie.dropna()
        if preenchidos.empty or _e_codigo_numerico(preenchidos):
            continue
        exemplos = " · ".join(dict.fromkeys(str(valor) for valor in preenchidos.head(50)))
        problemas.append(f"  {linha.variavel} — valores: {_encurtar(exemplos)}")

    if problemas:
        raise CategoricaSemCodigoError(
            f"{len(problemas)} categórica(s) de pares da lista `{PASTA_CORRELACAO}:` "
            "chegaram em texto. Nada foi gerado.\n\n"
            + "\n".join(problemas)
            + "\n\nUma categórica entra na correlação pela ordem numérica dos códigos, e "
            "texto não tem ordem que o FlatCap possa ler: a do `categorias_ordem` pode ser "
            "a de frequência, que é a que o `flatcap perfil` propõe.\n\n"
            "Duas saídas:\n"
            "  1. peça ao cliente a coluna em código (1, 2, 3) e escreva os rótulos no "
            f"{ARQUIVO_DICIONARIO} — `1=Fundamental|2=Médio|3=Superior` —; a descritiva "
            "sai igual, e a correlação passa a ter a ordem;\n"
            f"  2. tire o par da lista `{PASTA_CORRELACAO}:` — se a variável é nominal, ela "
            "não tem correlação."
        )


def _e_codigo_numerico(serie: pd.Series) -> bool:
    return bool(
        pd.api.types.is_numeric_dtype(serie) and not pd.api.types.is_bool_dtype(serie)
    )


def _avisos_de_agrupamento(envolvidas: Sequence[Linha]) -> list[str]:
    """
    Uma frase por categórica cujo dicionário junta dois códigos num rótulo só.

    Na tabela de frequência, `1=Discordo|2=Discordo` é uma linha só, e na
    associação também. Aqui não: a correlação usa a escala como ela está no banco,
    e o 1 continua abaixo do 2. É aviso, e não recusa, porque o resultado está
    certo — o que muda é o que se esperava dele.
    """
    avisos: list[str] = []
    for linha in envolvidas:
        if linha.tipo != CATEGORICA:
            continue
        por_rotulo: dict[str, list[str]] = {}
        for codigo, rotulo in linha.rotulos_das_categorias:
            if rotulo:
                por_rotulo.setdefault(rotulo, []).append(codigo)
        juntos = [codigos for codigos in por_rotulo.values() if len(codigos) > 1]
        if juntos:
            exemplo = "|".join(f"{codigo}={linha.rotulo_de(codigo)}" for codigo in juntos[0])
            avisos.append(
                f"`{linha.variavel}`: o {ARQUIVO_DICIONARIO} junta códigos num rótulo só "
                f"(`{exemplo}`), e a correlação usa o código como ele está no banco — o "
                "agrupamento vale para as tabelas, não para a ordem da escala."
            )
    return avisos


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


def montar_manifesto(
    correlacao: Correlacao, linhas: Sequence[Linha], com_graficos: bool = True
) -> Manifesto:
    """
    Traduz a rodada para o índice que o relatório vai ler.

    **Um item só**, como na normalidade e na associação: a seção do documento é
    uma tabela que fala de todos os pares, e uma dispersão por par abaixo dela. O
    `colunas` do item diz quais colunas do banco entraram — a união dos pares —,
    que é o que mantém as conferências do relatório certas para uma seção que não é
    de uma variável. O que decidiu cada método vai em `detalhes`.
    """
    banco = correlacao.banco
    leitura = banco.leitura
    ficha = correlacao.ficha

    artefatos = [
        Artefato(
            arquivo=correlacao.tabela.nome,
            especie=correlacao.tabela.especie,
            formato="csv",
            titulo=correlacao.tabela.titulo,
        )
    ]
    if com_graficos:
        artefatos += [
            Artefato(
                arquivo=grafico.nome,
                especie=grafico.especie,
                formato="png",
                titulo=grafico.titulo,
            )
            for grafico in correlacao.graficos
        ]

    item = ItemDoManifesto(
        variavel="",
        slug=PASTA_CORRELACAO,
        rotulo="Correlação",
        tipo=ANALISE_CORRELACAO,
        n=banco.linhas,
        faltantes=0,
        colunas=correlacao.colunas_usadas,
        artefatos=tuple(artefatos),
        detalhes={
            "pares": [par.como_detalhe() for par in correlacao.pares],
            "testados": len(correlacao.testados),
            "pearson": correlacao.quantos(PEARSON),
            "spearman": correlacao.quantos(SPEARMAN),
            "kendall": correlacao.quantos(KENDALL),
            "escritos_na_ficha": len(correlacao.pela_ficha),
        },
        avisos=tuple(aviso for par in correlacao.pares for aviso in par.avisos),
    )

    return Manifesto(
        analise=ANALISE_CORRELACAO,
        flatcap=__version__,
        gerado_em=correlacao.quando,
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
        ambiente=_ambiente(com_graficos),
        regras={
            "pares": f"os da lista `{PASTA_CORRELACAO}:` do {ARQUIVO_PROJETO}",
            "escolha_do_metodo": (
                f"Kendall se alguma das duas tem até {POUCOS_VALORES} valores distintos, "
                "com repetição; senão Spearman se alguma é categórica ou se o "
                f"Shapiro-Wilk rejeita a normal (p < {ALFA:g}) em alguma, sobre os casos "
                "do par; senão Pearson. O método escrito na ficha tem precedência."
            ),
            "pearson": "cor.test do R: t com n − 2 graus de liberdade",
            "spearman": (
                f"cor.test do R: exato (AS 89) até n = {MAXIMO_EXATO_SPEARMAN} sem "
                f"empates — contagem das permutações até n = {PERMUTACOES_SPEARMAN}, "
                "série de Edgeworth acima —; aproximação t com empates ou acima do limite"
            ),
            "kendall": (
                f"cor.test do R: tau-b; exato abaixo de n = {LIMITE_EXATO_KENDALL} sem "
                "empates; aproximação normal com a variância corrigida para empates nos "
                "outros casos, sem correção de continuidade"
            ),
            "intervalo": (
                f"{CONFIANCA:.0%}, transformação de Fisher: Pearson 1/√(n − 3) (cor.test "
                "do R); Spearman √((1 + ρ²/2)/(n − 3)) (Bonett e Wright, 2000); Kendall "
                "√(0,437/(n − 4)) (Fieller, Hartley e Pearson, 1957)"
            ),
            "categorica": "pela ordem numérica dos códigos, só Spearman ou Kendall",
            "poucos_valores": POUCOS_VALORES,
            "alfa": ALFA,
            "minimo_de_pares": MINIMO_DE_PARES,
            "faltantes": "por par",
            "comparacoes_multiplas": "nenhuma correção",
            "graficos": com_graficos,
            "tamanho_do_ponto": "proporcional ao número de casos no mesmo lugar",
            "semente": SEMENTE,
        },
        itens=(item,),
        fora=tuple(
            {"variavel": f.variavel, "tipo": f.tipo, "motivo": f.motivo}
            for f in correlacao.fora
        ),
        avisos=correlacao.avisos,
    )


def _ambiente(com_graficos: bool) -> dict[str, Any]:
    """
    As versões que produziram estes números.

    O `scipy` entra, porque as distribuições são dele. O `matplotlib` e a `fonte`
    só quando há figura, como na normalidade: perguntar a versão custaria importar
    a biblioteca que o `--sem-graficos` existe para evitar.
    """
    import openpyxl
    import scipy

    ambiente: dict[str, Any] = {
        "python": ".".join(str(parte) for parte in sys.version_info[:3]),
        "flatcap": __version__,
        "pandas": pd.__version__,
        "openpyxl": openpyxl.__version__,
        "scipy": scipy.__version__,
        "matplotlib": None,
        "fonte": None,
    }
    if com_graficos:
        from .graficos import fonte_dos_graficos, versao_do_matplotlib

        ambiente["matplotlib"] = versao_do_matplotlib()
        ambiente["fonte"] = fonte_dos_graficos()
    return ambiente


# Mensagens


def _mensagem_sem_pares(linhas: Sequence[Linha]) -> str:
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
        f"O {ARQUIVO_PROJETO} deste projeto não diz quais pares correlacionar.\n\n"
        "Escreva a lista na ficha — um par entre colchetes, com o método como terceiro "
        f"nome quando quiser escolhê-lo, ou uma variável contra várias com "
        f"dois-pontos:\n\n{EXEMPLO_DA_FICHA}\n\n"
        f"{disponiveis} Uma escala marcada `categorica`, com código numérico, também "
        "entra — pela ordem dos códigos.\n\n"
        "Quais pares correlacionar é decisão da reunião: o FlatCap não correlaciona "
        "tudo com tudo, porque trinta variáveis dariam 435 testes."
    )


def _motivo_de_fora(linha: Linha) -> str:
    if not linha.no_banco:
        return "não está nesta versão do banco (`no_banco = nao`)"
    if linha.tipo == IGNORAR:
        return "marcada `ignorar` no dicionário"
    return f"não está em nenhum par da lista `{PASTA_CORRELACAO}:` do {ARQUIVO_PROJETO}"


def _acao_do_historico(plano: PlanoCorrelacao) -> str:
    correlacao = plano.correlacao
    contagem = [
        (correlacao.quantos(PEARSON), PEARSON),
        (correlacao.quantos(SPEARMAN), SPEARMAN),
        (correlacao.quantos(KENDALL), KENDALL),
    ]
    metodos = ", ".join(f"{quantos} {nome}" for quantos, nome in contagem if quantos)
    partes = [
        f"`flatcap correlacao {correlacao.ficha.record_id}` — correlação de "
        f"`{correlacao.banco.versao.arquivo}`: {len(correlacao.pares)} par(es) da "
        f"lista `{PASTA_CORRELACAO}:`"
        + (f" ({metodos})" if metodos else "")
        + f", em `{PASTA_ANALISES}/{PASTA_CORRELACAO}/`."
    ]
    if correlacao.pela_ficha:
        partes.append(f"{len(correlacao.pela_ficha)} com o método escrito na ficha.")
    if plano.arquivamento is not None:
        partes.append(
            f"A rodada anterior foi para `{PASTA_ANTIGAS}/{plano.arquivamento[1].name}/`."
        )
    if not plano.com_graficos:
        partes.append("Rodado com `--sem-graficos`.")
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


def _rotulo(linha: Linha) -> str:
    return linha.rotulo or linha.variavel


def _p_na_frase(p: float | None, com_nome: bool = True) -> str:
    """
    O p dentro de uma frase: `p = 0,412`, ou `p < 0,001` — nunca `p = < 0,001`.
    """
    texto = valor_p(p)
    if not com_nome:
        return texto
    return f"p {texto}" if texto.startswith("<") else f"p = {texto}"


def _estatistica_em_texto(coeficiente: Coeficiente) -> str:
    nome = coeficiente.nome_da_estatistica
    casas = 0 if nome in ("S", "T") else 2
    texto = f"{nome} = {numero(coeficiente.estatistica, casas)}"
    if coeficiente.gl is not None:
        texto += f"; {coeficiente.gl} gl"
    return texto


def _normal_como_detalhe(normal: Normal | None) -> dict[str, Any] | None:
    if normal is None:
        return None
    return {
        "w": _arredondar(normal.w),
        "p": _significativos(normal.p),
        "rejeita": normal.rejeita if normal.testada else None,
        "impedimento": normal.impedimento or None,
    }


def _formatar_coeficiente(valor: float | None) -> str:
    """
    O coeficiente com duas casas fixas e o sinal quando é negativo: `0,45` e
    `-0,45`, nunca `-0,00`.

    Casas fixas pelo motivo do V de Cramér: a coluna é lida de cima para baixo. O
    sinal é o hífen do teclado, e não o `−` tipográfico, para o Excel em português
    ler a célula como número quando alguém abrir o `.csv`.
    """
    if valor is None:
        return _AUSENTE
    texto = f"{valor:.{CASAS_COEFICIENTE}f}"
    if float(texto) == 0:
        texto = texto.lstrip("-")
    return texto.replace(".", ",")


def _formatar_intervalo(intervalo_: tuple[float, float] | None) -> str:
    if intervalo_ is None:
        return _AUSENTE
    baixo, alto = intervalo_
    return f"{_formatar_coeficiente(baixo)} a {_formatar_coeficiente(alto)}"


def _encurtar(texto: str, limite: int = 60) -> str:
    return texto if len(texto) <= limite else texto[: limite - 1] + "…"


def _arredondar(valor: float | None) -> float | None:
    if valor is None:
        return None
    valor = float(valor)
    return round(valor, 6) if math.isfinite(valor) else None


def _significativos(valor: float | None) -> float | None:
    """
    O p no manifesto, com seis algarismos significativos, e não seis casas.

    Com seis casas, um p de 2,5e-08 é gravado como `0.0` — o número que o
    `valor_p` existe para nunca escrever na tabela, escrito no recibo da rodada.
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
    "CASAS_COEFICIENTE",
    "CONFIANCA",
    "EXEMPLO_DA_FICHA",
    "KENDALL",
    "LIMITE_EXATO_KENDALL",
    "MAXIMO_EXATO_SPEARMAN",
    "METODOS",
    "MINIMO_DE_PARES",
    "PEARSON",
    "PERMUTACOES_SPEARMAN",
    "POUCOS_VALORES",
    "PREFIXO_FIGURA",
    "SPEARMAN",
    "VARIANCIA_KENDALL",
    "CategoricaSemCodigoError",
    "Coeficiente",
    "Correlacao",
    "CorrelacaoError",
    "DicionarioAusenteError",
    "DicionarioDesatualizadoError",
    "Escolha",
    "ForaDaCorrelacao",
    "Normal",
    "Par",
    "ParCorrelacionado",
    "ParInvalidoError",
    "Pedido",
    "PlanoCorrelacao",
    "Pressupostos",
    "ResultadoCorrelacao",
    "SemParesError",
    "VariavelIncompativelError",
    "calcular",
    "correlacionar",
    "executar_correlacao",
    "intervalo",
    "kendall",
    "metodo_escrito",
    "montar_manifesto",
    "pares_da_ficha",
    "pearson",
    "preparar_correlacao",
    "prho",
    "regra",
    "spearman",
    "valores_do_par",
]
