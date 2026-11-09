# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
"""
A regressão — linear simples, linear múltipla e logística, escolhidas pelo desfecho.

É a primeira análise de modelo do FlatCap: até aqui toda análise testava um par ou
um grupo de cada vez, e a regressão põe um desfecho contra vários preditores juntos,
cada um ajustado pelos outros. Para cada modelo pedido na ficha, uma linha no resumo
e uma tabela de coeficientes:

    desfecho           modelo           n   ajuste                     teste global      p-valor
    Pressão sistólica  Linear simples   59  R² = 0,59; ajustado = 0,59 F = 83,58; 1 e 57 gl  < 0,001
    Óbito              Logística — …    60  26 eventos; AIC = 75,0     χ² = 17,09; 4 gl  0,002

    termo                coeficiente  IC 95%           p-valor
    (intercepto)               71,38  50,19 a 92,58    < 0,001
    Idade                       0,63  0,42 a 0,84      < 0,001
    Sexo: Feminino       referência   —                —
    Sexo: Masculino             3,79  -0,18 a 7,76       0,061

E, nos modelos lineares, duas figuras dos resíduos: contra os valores ajustados, e o
Q-Q. São a parte da verificação dos pressupostos que nenhum número faz sozinho.

Segue o padrão das outras análises, decidir e escrever separados:

    plano = preparar_regressao(raiz)   # abre o banco, ajusta, não toca no disco
    executar_regressao(plano)          # só escreve

E, como elas, **não fala com o REDCap**. Recebe `Path`, não `Config`.

## Quais modelos

Os escritos na ficha, e só eles — o desfecho antes dos dois-pontos, os preditores
depois:

    regressao:
      - pas: [idade]                  # linear simples
      - pas: [idade, imc, sexo]       # linear múltipla
      - obito: [idade, sexo]          # logística
        evento: Sim                   # a categoria que é o evento, quando a regra não serve

Sem a lista, o comando recusa, pelo motivo da correlação: quais preditores entram é
hipótese, e hipótese se escreve na reunião. **O FlatCap não escolhe preditor** — não
há *stepwise*, nem seleção pelo p. Um modelo escolhido pelos dados dá p que não
querem dizer o que dizem, e é exatamente o que a lista escrita evita.

## A regra: o tipo do desfecho no dicionário escolhe o modelo

* desfecho **`numerica`** → regressão **linear**: **simples** com um preditor,
  **múltipla** com dois ou mais. A contagem é de variáveis, e não de coeficientes:
  `pas: [escolaridade]` é linear simples mesmo com as três categorias da
  escolaridade dando dois coeficientes;
* desfecho **`categorica` de duas categorias** → regressão **logística**. Três ou
  mais categorias pedem a multinomial ou a ordinal, que ainda não estão aqui, e a
  linha sai sem modelo, com o motivo.

Não há método a escrever na ficha, como há na correlação: aqui não existe a escolha
entre um paramétrico e um de postos. O tipo é decisão do dicionário, e uma `obito`
marcada `numerica` sai pela linear — com o aviso de que ela tem dois valores só, e
de que a logística pede o `tipo` `categorica`.

## As categóricas entre os preditores

Entram como **indicadoras**: uma coluna de 0 e 1 por categoria, menos a de
**referência**, que é a **primeira na ordem do dicionário** entre as que têm caso no
modelo. É o `factor` do R com os níveis nessa ordem — o `contr.treatment` —, e é a
mesma ordem que decide o primeiro grupo da comparação e a ordem das categorias da
associação: a mesma categoria não pode vir primeiro numa seção e depois na seguinte.

**O código conta, o rótulo imprime**, como no cruzamento: dois códigos com o mesmo
rótulo são a mesma categoria, e a indicadora é uma só. Uma categórica em texto entra
do mesmo jeito que uma de código — indicadora não precisa de ordem, e ao contrário
da correlação nada aqui é recusado por isso.

A tabela traz a linha da referência, com `referência` no lugar do coeficiente: o
coeficiente de `Sexo: Masculino` é uma diferença, e a tabela precisa dizer contra
quem.

## O evento da logística

**A segunda categoria do desfecho na ordem do dicionário**, como o `glm` do R com os
níveis do fator nessa ordem: o primeiro nível é o "não", o segundo é o evento. Num
`0=Não|1=Sim` é o `Sim`. A chave `evento:` ao lado do item manda, pelo código ou
pelo rótulo — `evento: 1` e `evento: Sim` são o mesmo —, e o evento sai escrito na
coluna do modelo, porque um OR lido para o evento errado é o inverso do que se quis
dizer, com a mesma cara.

## Os faltantes

**Casos completos, modelo a modelo**: entra quem respondeu o desfecho e todos os
preditores daquele modelo. É o `na.omit` do `lm` e do `glm`. A conta é por modelo, e
não da rodada: a linear simples pela idade não perde os casos sem IMC da múltipla ao
lado.

## Como o R faz

**A linear é o `lm`**, pela decomposição QR, e os números são os do `summary.lm` e do
`confint`: cada coeficiente com o t de n − p graus de liberdade, bilateral, e o IC 95%
pelo t; o R², o R² ajustado e o F do modelo contra o modelo só com o intercepto.

**A logística é o `glm(family = binomial)`**, pelo mesmo IRLS do `glm.fit` — o mesmo
ponto de partida, `(y + 0,5)/2`, as mesmas travas da inversa do logit em ±30, o mesmo
critério de convergência sobre a deviance, `1e-8`, e o mesmo teto de 25 iterações.
Os coeficientes saem como **razão de chances** (OR), com o p do z de Wald do
`summary.glm`. O modelo inteiro é testado pela razão de verossimilhança contra o
modelo nulo — o `anova(modelo, test = "Chisq")` —, com o AIC ao lado.

**O IC 95% do OR é o de Wald**, `exp(β ± 1,96·EP)` — o `confint.default` —, e não o
de verossimilhança perfilada que o `confint` do R dá a um `glm`. Por coerência com o
p da mesma linha, que é o de Wald: os dois dizem a mesma coisa, e o IC cruza o 1
exatamente quando p ≥ 0,05. Com o perfilado, a tabela pode sair com p = 0,048 e um
IC que passa pelo 1 — e explicar isso ao cliente é explicar uma diferença entre dois
métodos, e não um resultado. Em amostras pequenas, ou com OR muito longe de 1, o
perfilado é o melhor dos dois, e a nota do `.csv` diz qual foi usado.

O `test_regressao.py` confere todos esses números contra o `lm` e o `glm` do R.

## O que sai junto, e por quê

**Nas lineares, o Shapiro-Wilk dos resíduos**, pela função da normalidade, e as duas
figuras. O teste vai para as notas e para o manifesto, e vira aviso quando rejeita. A
normal que o t e o F supõem é a dos resíduos, e não a do desfecho — um desfecho
assimétrico explicado por um preditor assimétrico pode ter resíduos normais.

**Na logística, os eventos por coeficiente.** Menos de 10 — o critério de Peduzzi e
colegas (1996) — vira aviso: os OR saem enviesados para longe de 1, e o IC de Wald
fica otimista. O que se conta são os casos da categoria mais rara, evento ou não.

**A separação, também na logística — uma barreira que o R não tem.** Quando um
preditor, ou uma combinação deles, separa os eventos dos não eventos — toda
escolaridade `Médio` é evento, por exemplo —, o OR é infinito. O `glm` do R às vezes
para por não convergir, e às vezes "converge" com coeficientes enormes, erro-padrão
na casa dos milhares e p perto de 1, **sem aviso nenhum**: a tabela sairia com um
OR de 10²² e um IC de 0 a infinito. Aqui a separação é procurada antes do ajuste,
pela programação linear de Konis (2007) — a ideia do `detect_separation` do pacote
`detectseparation` do R —, e o modelo sai sem números, com o motivo; quando a causa é
uma categoria de preditor só com eventos, ou sem nenhum, o motivo diz qual. Quando o
ajuste converge com alguma probabilidade ajustada em 0 ou 1 — o aviso "fitted
probabilities numerically 0 or 1" do R — sem separação, os números saem, com o
aviso.

## O que ele deliberadamente não faz

**Não escolhe preditores**, já dito. **Não ajusta interação**, nem termo quadrático:
os dois são escolhas de modelo que pedem a forma da ficha para escrevê-los, e ela
ainda não existe. **Não padroniza os coeficientes**: o coeficiente sai na unidade
do preditor, que é a que o cliente sabe ler. **Não corrige para comparações
múltiplas.** **Não diz se o R² é bom**: como o tamanho da correlação, é convenção de
área.
"""

from __future__ import annotations

import math
import sys
import unicodedata
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from . import __version__
from .associacao import na_ordem_do_dicionario
from .banco import Banco, abrir, serie_de_texto
from .descritiva import arquivamento as arquivamento_da_rodada
from .descritiva import conferir_dicionario, escrever_rodada, recusar_incompativeis
from .descritiva import slug as slug_do_nome
from .dicionario import ARQUIVO_DICIONARIO, CATEGORICA, IGNORAR, NUMERICA, Linha
from .ficha import Ficha, bloco
from .ficha import ler as ler_ficha
from .manifesto import (
    ANALISE_REGRESSAO,
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
from .normalidade import ALFA, MENOR_P, pontos_do_qq, shapiro, valor_p
from .projeto import (
    ARQUIVO_PROJETO,
    PASTA_ANALISES,
    PASTA_ANTIGAS,
    PASTA_REGRESSAO,
    pasta_da_analise,
)

ARQUIVO_TABELA = "regressao.csv"
PREFIXO_COEFICIENTES = "coef_"
PREFIXO_RESIDUOS = "residuos_"
PREFIXO_QQ = "qq_"

# Os nomes que vão para a coluna `modelo`.
LINEAR_SIMPLES = "Linear simples"
LINEAR_MULTIPLA = "Linear múltipla"
LOGISTICA = "Logística"
MODELOS = (LINEAR_SIMPLES, LINEAR_MULTIPLA, LOGISTICA)

# A chave da ficha que escolhe o evento da logística, ao lado do item:
#
#     - obito: [idade, sexo]
#       evento: Sim
CHAVE_EVENTO = "evento"

# A linha do intercepto na tabela da linear. Entre parênteses, como o R escreve, para
# não se confundir com uma variável do banco chamada `intercepto`.
INTERCEPTO = "(intercepto)"

# O que ocupa a célula do coeficiente na linha da categoria de referência.
REFERENCIA = "referência"

CONFIANCA = 0.95

# Os controles do `glm.control()` do R, com o nome que eles têm lá.
MAXIMO_DE_ITERACOES = 25  # `maxit`
TOLERANCIA_DA_DEVIANCE = 1e-8  # `epsilon`
# A trava da inversa do logit no `binomial()$linkinv` do R (`THRESH`, no `family.c`):
# fora de ±30 a exponencial vira `DBL_EPSILON` ou o inverso dele.
TRAVA_DO_LOGIT = 30.0

# A separação: o máximo do programa linear de Konis, com as colunas na mesma escala.
# Sem separação ele é zero — o único ponto viável é a origem —, e o que sobra acima de
# zero é ruído do otimizador; com separação, ele é da ordem do número de casos.
TOLERANCIA_DA_SEPARACAO = 1e-7

# O `tol` do `lm.fit`: uma coluna cuja parte nova, depois de tirada a parte que as
# anteriores já explicam, é menor que isto do tamanho dela, é combinação das outras.
TOLERANCIA_DO_POSTO = 1e-7

# Os limites dos avisos. Com nome e aqui em cima, pela regra de sempre.
MINIMO_DE_EVENTOS_POR_COEFICIENTE = 10  # Peduzzi e colegas (1996)

# As casas do coeficiente e do IC saem da largura do IC: duas casas, e mais quando o
# IC é estreito demais para duas — um coeficiente de renda em reais é 0,00077, e
# `0,00 (0,00 a 0,00)` não diz nada. Ver `_casas`.
CASAS_MINIMAS = 2
CASAS_MAXIMAS = 6
CASAS_R2 = 2
CASAS_ESTATISTICA = 2
CASAS_AIC = 1

_AUSENTE = "—"

# O sinal entre o desfecho e os preditores nas frases, como a fórmula do R.
SINAL = " ~ "

# O exemplo que as mensagens escrevem. Um lugar só, para a recusa e o `--help`
# nunca ensinarem duas formas diferentes de escrever a mesma lista.
EXEMPLO_DA_FICHA = f"""  {PASTA_REGRESSAO}:
    - pas: [idade]
    - pas: [idade, imc, sexo]
    - obito: [idade, sexo]
      {CHAVE_EVENTO}: Sim"""


class RegressaoError(RuntimeError):
    """
    Falha ao gerar a regressão, já traduzida para o usuário.

    Erro próprio pela regra da casa: a CLI captura esta classe e transforma em
    painel com o nome do comando que o usuário rodou. Qualquer outra exceção é bug
    de verdade e deve subir com o traceback inteiro.
    """


class DicionarioAusenteError(RegressaoError):
    """
    O projeto não tem `dicionario.csv`. Não há o que obedecer.
    """


class DicionarioDesatualizadoError(RegressaoError):
    """
    O banco tem colunas que o dicionário desconhece.
    """


class VariavelIncompativelError(RegressaoError):
    """
    O dicionário promete `numerica` e a coluna chegou como texto, ou declara uma
    variável que o banco não tem. A recusa da descritiva, pela mesma função,
    aplicada só às variáveis dos modelos.
    """


class SemModelosError(RegressaoError):
    """
    A ficha não diz quais modelos ajustar.
    """


class ModeloInvalidoError(RegressaoError):
    """
    A lista `regressao:` da ficha tem item que não serve.

    Formato errado, nome fora do dicionário, variável que não é numérica nem
    categórica, o desfecho entre os próprios preditores, um preditor duas vezes,
    `evento:` num desfecho numérico ou o mesmo modelo duas vezes. A mensagem lista
    **todos** de uma vez.
    """


# O que a ficha pede


@dataclass(frozen=True)
class Pedido:
    """
    Um modelo como a ficha o escreve: o desfecho, os preditores e, quando houver, o
    evento — ainda nomes, sem o dicionário.
    """

    desfecho: str
    preditores: tuple[str, ...]
    evento: str = ""

    @property
    def escrito(self) -> str:
        """O item como ele se escreve na ficha, para as mensagens."""
        texto = f"{self.desfecho}: [{', '.join(self.preditores)}]"
        return texto + (f" ({CHAVE_EVENTO}: {self.evento})" if self.evento else "")


@dataclass(frozen=True)
class Pergunta:
    """
    Um modelo pedido na ficha, já conferido contra o dicionário.
    """

    desfecho: Linha
    preditores: tuple[Linha, ...]
    evento: str = ""

    @property
    def modelo(self) -> str:
        """A regra do topo do módulo: o tipo do desfecho, e quantos preditores."""
        if self.desfecho.tipo == CATEGORICA:
            return LOGISTICA
        return LINEAR_SIMPLES if len(self.preditores) == 1 else LINEAR_MULTIPLA

    @property
    def linhas(self) -> tuple[Linha, ...]:
        return (self.desfecho, *self.preditores)


# O que o ajuste devolve


@dataclass(frozen=True)
class Coeficiente:
    """
    Uma linha do `coef(summary(modelo))` do R, com o IC ao lado.

    `estatistica` é o t na linear e o z de Wald na logística. Na logística os quatro
    números estão na escala do logit; o OR é `exp` deles, e quem exponencia é quem
    imprime.
    """

    nome: str
    estimativa: float
    erro_padrao: float
    estatistica: float
    p: float
    ic: tuple[float, float]


@dataclass(frozen=True)
class Ajuste:
    """
    Um modelo ajustado, com os números do `summary` do R.

    Os campos são a união do que cada modelo precisa, como no `Grafico`: o R² e o
    sigma são da linear; a deviance, o AIC e as iterações, da logística. `teste` é
    o do modelo inteiro — o F da linear, a razão de verossimilhança da logística —
    com o nome em `nome_do_teste` e os graus de liberdade em `gl_do_teste`.
    """

    modelo: str
    n: int
    coeficientes: tuple[Coeficiente, ...]
    nome_da_estatistica: str
    nome_do_teste: str
    teste: float
    gl_do_teste: tuple[int, ...]
    p_do_teste: float
    gl_residuo: int
    r2: float | None = None
    r2_ajustado: float | None = None
    sigma: float | None = None
    deviance_nula: float | None = None
    deviance: float | None = None
    aic: float | None = None
    iteracoes: int | None = None
    convergiu: bool = True
    extremos: bool = False
    residuos: tuple[float, ...] = ()
    ajustados: tuple[float, ...] = ()

    @property
    def logistico(self) -> bool:
        return self.modelo == LOGISTICA


@dataclass(frozen=True)
class Termo:
    """
    Uma linha da tabela de coeficientes.

    `indice` é a posição do coeficiente em `Ajuste.coeficientes`, e fica `None` na
    linha da categoria de referência, que não tem coeficiente.
    """

    rotulo: str
    variavel: str
    categoria: str = ""
    indice: int | None = None

    @property
    def referencia(self) -> bool:
        return self.indice is None


@dataclass(frozen=True)
class Normal:
    """O Shapiro-Wilk dos resíduos: o que o `normalidade.shapiro` devolve."""

    w: float | None
    p: float | None
    impedimento: str = ""
    aviso: str = ""

    @property
    def rejeita(self) -> bool:
        return self.p is not None and self.p < ALFA


@dataclass(frozen=True)
class ModeloAjustado:
    """
    Um modelo pedido, ajustado. É uma linha do resumo, uma tabela e, na linear, duas
    figuras.

    `ajuste` fica `None` quando o modelo não saiu; o motivo está em `motivo`, e a
    linha **sai assim mesmo** — um modelo pedido que sumisse do resumo seria a falta
    em que ninguém repara.
    """

    desfecho: str
    rotulo_do_desfecho: str
    tipo_do_desfecho: str
    preditores: tuple[str, ...]
    rotulos_dos_preditores: tuple[str, ...]
    modelo: str
    total: int
    validos: int
    slug: str = ""
    evento: str = ""
    evento_pela_ficha: bool = False
    eventos: int | None = None
    referencias: tuple[tuple[str, str], ...] = ()
    termos: tuple[Termo, ...] = ()
    ajuste: Ajuste | None = None
    normal: Normal | None = None
    motivo: str = ""
    avisos: tuple[str, ...] = ()

    @property
    def faltantes(self) -> int:
        return self.total - self.validos

    @property
    def colunas(self) -> tuple[str, ...]:
        return (self.desfecho, *self.preditores)

    @property
    def ajustado(self) -> bool:
        return self.ajuste is not None

    @property
    def formula(self) -> str:
        """`Pressão sistólica ~ Idade + Sexo`: o modelo em uma linha, com os rótulos."""
        return f"{self.rotulo_do_desfecho}{SINAL}{' + '.join(self.rotulos_dos_preditores)}"

    @property
    def nome_do_modelo(self) -> str:
        """O que vai para a coluna `modelo`: com o evento, na logística."""
        if self.modelo == LOGISTICA and self.evento:
            return f"{LOGISTICA} — evento: {self.evento}"
        return self.modelo

    @property
    def titulo(self) -> str:
        """O título da seção e da tabela do modelo."""
        return f"Regressão {self.modelo.lower()} — {self.formula}"

    @property
    def justificativa(self) -> str:
        """
        A frase que explica a linha — a nota do `.csv` e a linha do terminal. Uma frase
        só, montada aqui, para o arquivo e a tela dizerem a mesma coisa.
        """
        cabeca = f"{self.formula}: "
        if self.ajuste is None:
            return f"{cabeca}sem modelo — {self.motivo}."
        quantos = len(self.preditores)
        partes = [
            f"n = {self.validos}"
            + (f" ({self.faltantes} sem resposta em alguma variável)" if self.faltantes else ""),
            f"desfecho {_tipo_por_extenso(self.tipo_do_desfecho)} com {quantos} "
            f"{'preditor' if quantos == 1 else 'preditores'} → {self.modelo.lower()}",
        ]
        if self.modelo == LOGISTICA:
            origem = "escrito na ficha" if self.evento_pela_ficha else (
                "a segunda categoria do dicionário"
            )
            partes.append(f"evento: {self.evento} ({origem}), em {self.eventos} caso(s)")
        partes += [
            f"referência de {_rotulo_da_variavel(self, variavel)}: {categoria}"
            for variavel, categoria in self.referencias
        ]
        if self.normal is not None:
            partes.append(f"Shapiro-Wilk dos resíduos: {_normal_na_frase(self.normal)}")
        return cabeca + "; ".join(partes) + "."

    def como_detalhe(self) -> dict[str, Any]:
        """
        Os números deste modelo, para o manifesto — o que responde "de onde saiu esse
        OR?" sem reabrir o banco.
        """
        ajuste = self.ajuste
        detalhe: dict[str, Any] = {
            "desfecho": self.desfecho,
            "tipo_do_desfecho": self.tipo_do_desfecho,
            "preditores": list(self.preditores),
            "modelo": self.modelo,
            "evento": self.evento or None,
            "evento_escrito_na_ficha": self.evento_pela_ficha if self.evento else None,
            "eventos": self.eventos,
            "referencias": {variavel: categoria for variavel, categoria in self.referencias},
            "n": self.validos,
            "faltantes": self.faltantes,
            "motivo": self.motivo or None,
        }
        if ajuste is None:
            return detalhe
        detalhe["coeficientes"] = [
            _coeficiente_como_detalhe(coeficiente, ajuste.logistico)
            for coeficiente in ajuste.coeficientes
        ]
        detalhe["ajuste"] = (
            {
                "deviance_nula": _arredondar(ajuste.deviance_nula),
                "deviance": _arredondar(ajuste.deviance),
                "razao_de_verossimilhanca": _arredondar(ajuste.teste),
                "gl": ajuste.gl_do_teste[0],
                "p": _significativos(ajuste.p_do_teste),
                "aic": _arredondar(ajuste.aic),
                "iteracoes": ajuste.iteracoes,
                "probabilidades_extremas": ajuste.extremos,
            }
            if ajuste.logistico
            else {
                "r2": _arredondar(ajuste.r2),
                "r2_ajustado": _arredondar(ajuste.r2_ajustado),
                "f": _arredondar(ajuste.teste),
                "gl": list(ajuste.gl_do_teste),
                "p": _significativos(ajuste.p_do_teste),
                "erro_padrao_residual": _arredondar(ajuste.sigma),
            }
        )
        if self.normal is not None:
            detalhe["shapiro_dos_residuos"] = {
                "w": _arredondar(self.normal.w),
                "p": _significativos(self.normal.p),
                "rejeita": self.normal.rejeita if self.normal.p is not None else None,
                "impedimento": self.normal.impedimento or None,
            }
        return detalhe


@dataclass(frozen=True)
class ForaDaRegressao:
    """
    Uma variável do dicionário que não está em modelo nenhum, e por quê.
    """

    variavel: str
    tipo: str
    motivo: str


@dataclass(frozen=True)
class Regressao:
    """
    A rodada inteira, decidida. É daqui que saem os arquivos e o terminal.
    """

    ficha: Ficha
    banco: Banco
    modelos: tuple[ModeloAjustado, ...]
    fora: tuple[ForaDaRegressao, ...]
    avisos: tuple[str, ...]
    quando: datetime
    tabela: Tabela
    coeficientes: tuple[Tabela, ...] = ()
    graficos: tuple[Grafico, ...] = ()

    @property
    def raiz(self) -> Path:
        return self.ficha.raiz

    @property
    def colunas_usadas(self) -> tuple[str, ...]:
        vistas: list[str] = []
        for modelo in self.modelos:
            for coluna in modelo.colunas:
                if coluna not in vistas:
                    vistas.append(coluna)
        return tuple(vistas)

    @property
    def ajustados(self) -> tuple[ModeloAjustado, ...]:
        return tuple(modelo for modelo in self.modelos if modelo.ajustado)

    def quantos(self, modelo: str) -> int:
        return sum(1 for ajustado in self.ajustados if ajustado.modelo == modelo)


@dataclass(frozen=True)
class PlanoRegressao:
    """
    Tudo o que a `regressao` faria, decidido e ainda não escrito.
    """

    regressao: Regressao
    pasta: Path
    arquivamento: tuple[Path, Path] | None
    com_graficos: bool
    manifesto: Manifesto
    texto_manifesto: str

    @property
    def raiz(self) -> Path:
        return self.regressao.raiz

    @property
    def tabela(self) -> Tabela:
        return self.regressao.tabela

    @property
    def tabelas(self) -> tuple[Tabela, ...]:
        return (self.regressao.tabela, *self.regressao.coeficientes)

    @property
    def graficos(self) -> tuple[Grafico, ...]:
        return self.regressao.graficos if self.com_graficos else ()

    @property
    def arquivos(self) -> tuple[str, ...]:
        nomes = [tabela.nome for tabela in self.tabelas]
        nomes += [grafico.nome for grafico in self.graficos]
        return tuple(nomes + [ARQUIVO_MANIFESTO])


@dataclass(frozen=True)
class ResultadoRegressao:
    """
    O que a execução de fato escreveu.
    """

    criados: tuple[Path, ...] = ()
    arquivado: tuple[Path, Path] | None = None
    avisos: tuple[str, ...] = ()


# Casos de uso


def preparar_regressao(
    raiz: Path,
    aba: str | None = None,
    conferir: bool = True,
    com_graficos: bool = True,
    agora: datetime | None = None,
) -> PlanoRegressao:
    """
    Lê os modelos da ficha, abre o banco, ajusta cada modelo e monta o plano. Não
    escreve nada.

    A lista da ficha é conferida **antes** de abrir o banco, como nas outras
    análises: um item fora do formato é o engano mais provável deste comando, e
    descobri-lo não deve custar a releitura do `sha256` de um banco grande.

    Raises:
        FichaError, BancoError, DicionarioInvalidoError e as recusas declaradas
        acima.
    """
    raiz = Path(raiz)
    quando = agora or datetime.now()

    pedidos = modelos_da_ficha(raiz)

    banco = abrir(raiz, aba=aba, conferir=conferir)
    ficha = ler_ficha(raiz)
    linhas = conferir_dicionario(
        raiz,
        banco,
        ausente=DicionarioAusenteError,
        desatualizado=DicionarioDesatualizadoError,
        analise="a regressão",
    )
    regressao = regredir(banco, ficha, linhas, pedidos, quando, com_graficos)

    pasta = pasta_da_analise(raiz, PASTA_REGRESSAO)
    manifesto = montar_manifesto(regressao, linhas, com_graficos)

    return PlanoRegressao(
        regressao=regressao,
        pasta=pasta,
        arquivamento=arquivamento_da_rodada(raiz, pasta, quando, PASTA_REGRESSAO),
        com_graficos=com_graficos,
        manifesto=manifesto,
        texto_manifesto=texto_do_manifesto(manifesto),
    )


def executar_regressao(plano: PlanoRegressao) -> ResultadoRegressao:
    """
    Escreve o plano no disco. Não decide mais nada: quem escreve, na ordem, e desfaz
    o que escreveu se falhar no meio, é o `descritiva.escrever_rodada`.
    """
    criados, arquivado, avisos = escrever_rodada(
        plano.raiz,
        plano.pasta,
        plano.arquivamento,
        plano.tabelas,
        plano.graficos,
        plano.texto_manifesto,
        _acao_do_historico(plano),
        plano.regressao.quando,
    )
    return ResultadoRegressao(criados=criados, arquivado=arquivado, avisos=avisos)


def regredir(
    banco: Banco,
    ficha: Ficha,
    linhas_do_dicionario: Sequence[Linha],
    pedidos: Sequence[Pedido | tuple[str, Sequence[str]] | tuple[str, Sequence[str], str]],
    quando: datetime | None = None,
    com_graficos: bool = True,
) -> Regressao:
    """
    Ajusta cada modelo pedido, obedecendo ao dicionário. Função pura.

    O miolo testável, como o `correlacionar` da correlação: um `DataFrame` montado à
    mão, uma lista de `Linha` e os modelos entram, e as afirmações são sobre as
    tabelas — sem pasta de projeto e sem disco.

    Args:
        pedidos: os modelos como `modelos_da_ficha` os devolve, ou tuplas
            `(desfecho, [preditores])` e `(desfecho, [preditores], evento)`, que é
            como um teste os escreve.
        com_graficos: montar as figuras dos resíduos.

    Raises:
        SemModelosError, ModeloInvalidoError, VariavelIncompativelError
    """
    quadro = banco.quadro
    total = int(quadro.shape[0])

    if not pedidos:
        raise SemModelosError(_mensagem_sem_modelos(linhas_do_dicionario))

    perguntas = _conferir_pedidos([_como_pedido(item) for item in pedidos], linhas_do_dicionario)

    envolvidas: list[Linha] = []
    for pergunta in perguntas:
        for linha in pergunta.linhas:
            if linha not in envolvidas:
                envolvidas.append(linha)
    recusar_incompativeis(quadro, envolvidas, erro=VariavelIncompativelError)

    usados: set[str] = set()
    modelos = tuple(
        _ajustar(
            quadro,
            pergunta,
            total,
            slug_do_nome(
                f"{pergunta.desfecho.variavel} "
                + " ".join(linha.variavel for linha in pergunta.preditores),
                usados,
            ),
        )
        for pergunta in perguntas
    )

    nos_modelos = {coluna for modelo in modelos for coluna in modelo.colunas}
    fora = tuple(
        ForaDaRegressao(linha.variavel, linha.tipo, _motivo_de_fora(linha))
        for linha in linhas_do_dicionario
        if linha.variavel not in nos_modelos
    )

    avisos = list(banco.avisos)
    avisos += [aviso for modelo in modelos for aviso in modelo.avisos]

    return Regressao(
        ficha=ficha,
        banco=banco,
        modelos=modelos,
        fora=fora,
        avisos=tuple(avisos),
        quando=quando or datetime.now(),
        tabela=_tabela(modelos, total),
        coeficientes=tuple(
            _tabela_de_coeficientes(modelo) for modelo in modelos if modelo.ajustado
        ),
        graficos=(
            tuple(grafico for modelo in modelos for grafico in _graficos(modelo))
            if com_graficos
            else ()
        ),
    )


# Um modelo


def _ajustar(quadro: pd.DataFrame, pergunta: Pergunta, total: int, slug: str) -> ModeloAjustado:
    """
    Monta a matriz do modelo sobre os casos completos, confere as barreiras e ajusta.

    As barreiras vêm antes do ajuste, e cada uma é um motivo de linha sem modelo:
    nenhum caso completo; um valor só no desfecho ou num preditor; mais de duas
    categorias no desfecho da logística; o evento escrito que não é categoria dele;
    menos casos que coeficientes; e a colinearidade perfeita, em que o R daria `NA`
    a um coeficiente.
    """
    import numpy as np

    series = [_coluna(quadro, linha.variavel) for linha in pergunta.linhas]
    if any(serie is None for serie in series):  # pragma: no cover - a recusa já barrou
        raise VariavelIncompativelError("Uma variável do modelo não existe no banco.")
    respondeu = pd.Series(True, index=quadro.index)
    for serie in series:
        respondeu &= serie.notna()  # type: ignore[union-attr]
    validos = int(respondeu.sum())

    desfecho = pergunta.desfecho
    modelo = pergunta.modelo
    base: dict[str, Any] = {
        "desfecho": desfecho.variavel,
        "rotulo_do_desfecho": _rotulo(desfecho),
        "tipo_do_desfecho": desfecho.tipo,
        "preditores": tuple(linha.variavel for linha in pergunta.preditores),
        "rotulos_dos_preditores": tuple(_rotulo(linha) for linha in pergunta.preditores),
        "modelo": modelo,
        "total": total,
        "validos": validos,
        "slug": slug,
    }
    nome = f"`{desfecho.variavel}{SINAL}{' + '.join(base['preditores'])}`"

    def sem_modelo(motivo: str, **extras: Any) -> ModeloAjustado:
        return ModeloAjustado(
            **base,
            **extras,
            motivo=motivo,
            avisos=(f"{nome}: {motivo}. O modelo saiu sem números.",),
        )

    if not validos:
        return sem_modelo("nenhum caso com resposta em todas as variáveis do modelo")

    casos = [serie[respondeu] for serie in series]  # type: ignore[index]

    # O desfecho.
    avisos: list[str] = []
    evento = ""
    eventos: int | None = None
    if modelo == LOGISTICA:
        rotulos = _rotulos(casos[0], desfecho)
        categorias = na_ordem_do_dicionario(set(rotulos), desfecho)
        if len(categorias) < 2:
            return sem_modelo(f"um valor só em {_rotulo(desfecho)}")
        if len(categorias) > 2:
            return sem_modelo(
                f"{_rotulo(desfecho)} tem {len(categorias)} categorias "
                f"({', '.join(categorias)}) — a logística é para duas; a multinomial e a "
                "ordinal ainda não estão no FlatCap"
            )
        evento = categorias[1]
        if pergunta.evento:
            evento = _evento_entre(pergunta.evento, categorias, desfecho)
            if not evento:
                return sem_modelo(
                    f"`{CHAVE_EVENTO}: {pergunta.evento}` não é categoria de "
                    f"{_rotulo(desfecho)}, que tem {categorias[0]} e {categorias[1]}"
                )
        y = np.array([1.0 if rotulo == evento else 0.0 for rotulo in rotulos])
        eventos = int(y.sum())
    else:
        y = casos[0].astype("float64").to_numpy()
        distintos = int(pd.Series(y).nunique())
        if distintos < 2:
            return sem_modelo(f"um valor só em {_rotulo(desfecho)}")
        if distintos == 2:
            avisos.append(
                f"{nome}: {_rotulo(desfecho)} tem dois valores só e está marcada "
                f"`{NUMERICA}`, e saiu pela regressão linear. Se ela é um sim ou não, "
                f"marque `{CATEGORICA}` no {ARQUIVO_DICIONARIO}: a regressão dela é a "
                "logística."
            )
    extras: dict[str, Any] = {"evento": evento, "eventos": eventos,
                              "evento_pela_ficha": bool(pergunta.evento)}

    # Os preditores: a coluna do intercepto, e uma por numérica ou por categoria.
    colunas: list[Any] = [np.ones(validos)]
    nomes = [INTERCEPTO]
    termos: list[Termo] = [Termo(INTERCEPTO, "", indice=0)]
    referencias: list[tuple[str, str]] = []
    for linha, valores in zip(pergunta.preditores, casos[1:], strict=True):
        rotulo = _rotulo(linha)
        if linha.tipo == NUMERICA:
            numeros = valores.astype("float64").to_numpy()
            if pd.Series(numeros).nunique() < 2:
                return sem_modelo(f"um valor só em {rotulo}", **extras)
            termos.append(Termo(rotulo, linha.variavel, indice=len(nomes)))
            colunas.append(numeros)
            nomes.append(rotulo)
            continue
        rotulos_do_preditor = _rotulos(valores, linha)
        categorias_do_preditor = na_ordem_do_dicionario(set(rotulos_do_preditor), linha)
        if len(categorias_do_preditor) < 2:
            return sem_modelo(f"um valor só em {rotulo}", **extras)
        referencia, *outras = categorias_do_preditor
        referencias.append((linha.variavel, referencia))
        termos.append(Termo(f"{rotulo}: {referencia}", linha.variavel, referencia))
        for categoria in outras:
            termos.append(
                Termo(f"{rotulo}: {categoria}", linha.variavel, categoria, indice=len(nomes))
            )
            colunas.append(
                np.array([1.0 if valor == categoria else 0.0 for valor in rotulos_do_preditor])
            )
            nomes.append(f"{rotulo}: {categoria}")
    extras["referencias"] = tuple(referencias)

    x = np.column_stack(colunas)
    coeficientes = x.shape[1]
    if validos <= coeficientes:
        return sem_modelo(
            f"{validos} caso(s) completo(s) para {coeficientes} coeficientes — o modelo "
            "precisa de mais casos que coeficientes",
            **extras,
        )
    colinear = colunas_colineares(x)
    if colinear:
        return sem_modelo(
            f"{nomes[colinear[0]]} é combinação exata dos outros preditores (colinearidade "
            "perfeita) — o R daria NA ao coeficiente dela",
            **extras,
        )

    if modelo == LOGISTICA:
        if separacao(x, y):
            return sem_modelo(_motivo_da_separacao(pergunta, casos[1:], y, evento), **extras)
        ajuste = logistica(x, y, nomes)
        if not ajuste.convergiu:
            return sem_modelo(
                f"o ajuste não convergiu em {MAXIMO_DE_ITERACOES} iterações — quase sempre "
                "é separação: algum preditor, ou uma combinação deles, separa os eventos "
                "dos não eventos, e o OR é infinito",
                **extras,
            )
    else:
        ajuste = linear(x, y, nomes, modelo)

    normal = None
    if not ajuste.logistico:
        w, p, impedimento, aviso_do_teste = shapiro(
            desfecho.variavel, pd.Series(ajuste.residuos), ajuste.n
        )
        normal = Normal(w=w, p=p, impedimento=impedimento, aviso=aviso_do_teste)

    avisos += _avisos_do_modelo(nome, ajuste, normal, eventos)
    return ModeloAjustado(
        **base,
        **extras,
        termos=tuple(termos),
        ajuste=ajuste,
        normal=normal,
        avisos=tuple(avisos),
    )


def _rotulos(valores: pd.Series, linha: Linha) -> list[str]:
    """
    As categorias de uma coluna, pelo rótulo do dicionário: o código conta, o rótulo
    imprime — como no cruzamento, na associação e nos grupos da comparação.
    """
    return [linha.rotulo_de(codigo) for codigo in serie_de_texto(valores)]


def _evento_entre(escrito: str, categorias: Sequence[str], linha: Linha) -> str:
    """
    A categoria que o `evento:` da ficha nomeia, pelo rótulo ou pelo código; vazio
    quando não nomeia nenhuma. Tolerante como a leitura do método da correlação:
    maiúscula e acento não contam.
    """
    procurado = _sem_acento(escrito)
    for categoria in categorias:
        if _sem_acento(categoria) == procurado:
            return categoria
    for codigo in linha.categorias_ordem:
        if _sem_acento(codigo) == procurado and linha.rotulo_de(codigo) in categorias:
            return linha.rotulo_de(codigo)
    return ""


def _motivo_da_separacao(
    pergunta: Pergunta, valores: Sequence[pd.Series], y: Any, evento: str
) -> str:
    """
    O motivo do modelo separado, com a causa mais comum nomeada: a categoria de um
    preditor em que todo caso é evento, ou nenhum é. A separação por uma numérica, ou
    por uma combinação de preditores, não tem categoria a apontar, e a frase fica
    geral.
    """
    pistas: list[str] = []
    for linha, serie in zip(pergunta.preditores, valores, strict=True):
        if linha.tipo != CATEGORICA:
            continue
        rotulos = _rotulos(serie, linha)
        for categoria in na_ordem_do_dicionario(set(rotulos), linha):
            dentro = [bool(alvo) for rotulo, alvo in zip(rotulos, y, strict=True)
                      if rotulo == categoria]
            if all(dentro):
                pistas.append(f"todo caso de {_rotulo(linha)}: {categoria} é {evento}")
            elif not any(dentro):
                pistas.append(f"nenhum caso de {_rotulo(linha)}: {categoria} é {evento}")
    causa = "; ".join(pistas) if pistas else (
        "algum preditor, ou uma combinação deles, separa os eventos dos não eventos"
    )
    return (
        f"separação — {causa}. O OR é infinito: o glm do R ajustaria assim mesmo, com "
        "erro-padrão enorme e p perto de 1. Junte categorias no dicionário, ou tire o "
        "preditor do modelo"
    )


def _avisos_do_modelo(
    nome: str,
    ajuste: Ajuste,
    normal: Normal | None,
    eventos: int | None,
) -> list[str]:
    """
    O que o modelo precisa levar junto para o terminal e para o manifesto. Cada
    aviso é um engano conhecido, e nenhum muda os números.
    """
    avisos: list[str] = []
    if normal is not None and normal.rejeita:
        avisos.append(
            f"{nome}: o Shapiro-Wilk rejeita a normal dos resíduos "
            f"({_normal_na_frase(normal)}). O IC e o p dos coeficientes supõem resíduos "
            "normais; com muitos casos o desvio pesa pouco, com poucos, confira o Q-Q "
            "antes de ficar com eles."
        )
    if normal is not None and normal.aviso:
        avisos.append(normal.aviso)

    if ajuste.logistico and eventos is not None:
        raros = min(eventos, ajuste.n - eventos)
        por_coeficiente = raros / max(1, len(ajuste.coeficientes) - 1)
        if por_coeficiente < MINIMO_DE_EVENTOS_POR_COEFICIENTE:
            avisos.append(
                f"{nome}: {raros} caso(s) na categoria mais rara do desfecho para "
                f"{len(ajuste.coeficientes) - 1} coeficiente(s) — "
                f"{_fixo(por_coeficiente, 1)} por coeficiente, abaixo dos "
                f"{MINIMO_DE_EVENTOS_POR_COEFICIENTE} de Peduzzi e colegas (1996). Os OR "
                "saem enviesados para longe de 1 e o IC fica estreito demais; considere "
                "menos preditores."
            )
        if ajuste.extremos:
            avisos.append(
                f"{nome}: há caso com probabilidade ajustada de 0 ou 1 — o aviso «fitted "
                "probabilities numerically 0 or 1» do R. Pode ser separação quase "
                "completa: confira os OR muito grandes ou muito perto de 0, e os IC "
                "muito largos."
            )
    return avisos


# Os ajustes, como o `lm` e o `glm` do R


def linear(x: Any, y: Any, nomes: Sequence[str] = (), modelo: str = LINEAR_MULTIPLA) -> Ajuste:
    """
    O `lm(y ~ x)` do R, com os números do `summary.lm` e do `confint`.

    A matriz `x` já traz a coluna do intercepto na frente. Os coeficientes saem pela
    QR, como no R; o erro-padrão, de `σ²(XᵀX)⁻¹`; o t, com n − p graus de liberdade;
    o F, do modelo contra o modelo só com o intercepto.
    """
    import numpy as np
    from scipy import linalg, stats

    x = np.asarray(x, dtype="float64")
    y = np.asarray(y, dtype="float64")
    n, p = x.shape
    q, r = np.linalg.qr(x)
    beta = linalg.solve_triangular(r, q.T @ y)
    ajustados = x @ beta
    residuos = y - ajustados
    gl = n - p
    rss = float(residuos @ residuos)
    sigma2 = rss / gl
    r_inversa = linalg.solve_triangular(r, np.eye(p))
    erros = np.sqrt(np.diag(r_inversa @ r_inversa.T) * sigma2)

    critico = float(stats.t.ppf(1 - (1 - CONFIANCA) / 2, gl))
    coeficientes = []
    for posicao in range(p):
        estatistica = float(beta[posicao] / erros[posicao])
        coeficientes.append(
            Coeficiente(
                nome=nomes[posicao] if nomes else str(posicao),
                estimativa=float(beta[posicao]),
                erro_padrao=float(erros[posicao]),
                estatistica=estatistica,
                p=float(2 * stats.t.sf(abs(estatistica), gl)),
                ic=(
                    float(beta[posicao] - critico * erros[posicao]),
                    float(beta[posicao] + critico * erros[posicao]),
                ),
            )
        )

    # O `summary.lm` do R mede a variação explicada em torno da média dos ajustados,
    # e não pela diferença `tss − rss`: são iguais na álgebra, e a do R é a que
    # não perde algarismos quando o R² é pequeno.
    explicada = float(((ajustados - ajustados.mean()) ** 2).sum())
    r2 = explicada / (explicada + rss)
    gl_modelo = p - 1
    f = (explicada / gl_modelo) / sigma2
    return Ajuste(
        modelo=modelo,
        n=n,
        coeficientes=tuple(coeficientes),
        nome_da_estatistica="t",
        nome_do_teste="F",
        teste=f,
        gl_do_teste=(gl_modelo, gl),
        p_do_teste=float(stats.f.sf(f, gl_modelo, gl)),
        gl_residuo=gl,
        r2=r2,
        r2_ajustado=1 - (1 - r2) * (n - 1) / gl,
        sigma=math.sqrt(sigma2),
        residuos=tuple(float(v) for v in residuos),
        ajustados=tuple(float(v) for v in ajustados),
    )


def logistica(x: Any, y: Any, nomes: Sequence[str] = ()) -> Ajuste:
    """
    O `glm(y ~ x, family = binomial)` do R, pelo IRLS do `glm.fit`.

    Passo a passo o do R, para os números baterem com ele e não só com a teoria: o
    ponto de partida `μ = (y + 0,5)/2`; em cada iteração, a resposta de trabalho
    `z = η + (y − μ)/μ'` e o peso `√(μ'²/V(μ))`, um mínimo quadrado ponderado, e a
    deviance nova; a parada quando `|D − D_antes|/(|D| + 0,1) < 1e-8`. A covariância
    dos coeficientes é a do último mínimo quadrado — com os pesos do começo da
    última iteração, como no `summary.glm`.

    O p é o do z de Wald, e o IC, `β ± 1,96·EP`: o `confint.default`. O modelo
    inteiro é testado pela razão de verossimilhança contra o nulo, com p − 1 graus
    de liberdade, e o AIC é `D + 2p` — com o desfecho de 0 e 1, a deviance é menos
    duas vezes a log-verossimilhança.
    """
    import numpy as np
    from scipy import linalg, stats

    x = np.asarray(x, dtype="float64")
    y = np.asarray(y, dtype="float64")
    n, p = x.shape

    mu = (y + 0.5) / 2
    eta = np.log(mu / (1 - mu))
    mu = _inversa_do_logit(eta)
    deviance_antes = _deviance_binomial(y, mu)

    convergiu = False
    iteracoes = 0
    beta = np.zeros(p)
    r = np.eye(p)
    while iteracoes < MAXIMO_DE_ITERACOES:
        iteracoes += 1
        derivada = _derivada_do_logit(eta)
        variancia = mu * (1 - mu)
        z = eta + (y - mu) / derivada
        peso = np.sqrt(derivada**2 / variancia)
        q, r = np.linalg.qr(x * peso[:, None])
        beta = linalg.solve_triangular(r, q.T @ (z * peso))
        eta = x @ beta
        mu = _inversa_do_logit(eta)
        deviance = _deviance_binomial(y, mu)
        if abs(deviance - deviance_antes) / (abs(deviance) + 0.1) < TOLERANCIA_DA_DEVIANCE:
            convergiu = True
            break
        deviance_antes = deviance

    r_inversa = linalg.solve_triangular(r, np.eye(p))
    erros = np.sqrt(np.diag(r_inversa @ r_inversa.T))
    critico = float(stats.norm.ppf(1 - (1 - CONFIANCA) / 2))
    coeficientes = []
    for posicao in range(p):
        estatistica = float(beta[posicao] / erros[posicao])
        coeficientes.append(
            Coeficiente(
                nome=nomes[posicao] if nomes else str(posicao),
                estimativa=float(beta[posicao]),
                erro_padrao=float(erros[posicao]),
                estatistica=estatistica,
                p=float(2 * stats.norm.sf(abs(estatistica))),
                ic=(
                    float(beta[posicao] - critico * erros[posicao]),
                    float(beta[posicao] + critico * erros[posicao]),
                ),
            )
        )

    deviance = _deviance_binomial(y, mu)
    nula = _deviance_binomial(y, np.full(n, y.mean()))
    razao = nula - deviance
    # O limite do `glm.fit` para o aviso das probabilidades extremas: dez épsilons.
    limite = 10 * np.finfo("float64").eps
    return Ajuste(
        modelo=LOGISTICA,
        n=n,
        coeficientes=tuple(coeficientes),
        nome_da_estatistica="z",
        nome_do_teste="χ²",
        teste=razao,
        gl_do_teste=(p - 1,),
        p_do_teste=float(stats.chi2.sf(razao, p - 1)),
        gl_residuo=n - p,
        deviance_nula=nula,
        deviance=deviance,
        aic=deviance + 2 * p,
        iteracoes=iteracoes,
        convergiu=convergiu,
        extremos=bool((mu > 1 - limite).any() or (mu < limite).any()),
    )


def _inversa_do_logit(eta: Any) -> Any:
    """O `binomial()$linkinv` do R, com a trava em ±30 do `family.c`."""
    import numpy as np

    eps = np.finfo("float64").eps
    dentro = np.exp(np.clip(eta, -TRAVA_DO_LOGIT, TRAVA_DO_LOGIT))
    exponencial = np.where(
        eta < -TRAVA_DO_LOGIT, eps, np.where(eta > TRAVA_DO_LOGIT, 1 / eps, dentro)
    )
    return exponencial / (1 + exponencial)


def _derivada_do_logit(eta: Any) -> Any:
    """O `binomial()$mu.eta` do R: `e^η/(1 + e^η)²`, e `DBL_EPSILON` fora de ±30."""
    import numpy as np

    eps = np.finfo("float64").eps
    exponencial = np.exp(np.clip(eta, -TRAVA_DO_LOGIT, TRAVA_DO_LOGIT))
    return np.where(
        np.abs(eta) > TRAVA_DO_LOGIT, eps, exponencial / (1 + exponencial) ** 2
    )


def _deviance_binomial(y: Any, mu: Any) -> float:
    """A soma do `binomial()$dev.resids` com peso 1: `−2 log μ` no evento, `−2 log(1 − μ)` fora."""
    import numpy as np

    return float(-2 * np.sum(np.where(y > 0.5, np.log(mu), np.log(1 - mu))))


def separacao(x: Any, y: Any) -> bool:
    """
    Se os preditores separam os eventos dos não eventos — por completo, ou quase.

    É o critério de Albert e Anderson (1984): há separação quando alguma direção `b`
    não nula põe todo evento de um lado do hiperplano `xᵀb = 0` e todo não evento do
    outro, com empate permitido. Konis (2007) o transformou num programa linear —
    maximizar `Σ x̃ᵢᵀb` com `x̃ᵢᵀb ≥ 0` e `b` numa caixa, onde `x̃` é a linha com o
    sinal trocado nos não eventos —, cujo máximo é zero sem separação e positivo com
    ela. É o que o `detect_separation` do pacote `detectseparation` do R resolve; aqui
    pelo `linprog` do `scipy`, com cada coluna dividida pelo maior valor dela, para a
    tolerância não depender da unidade do preditor.
    """
    import numpy as np
    from scipy.optimize import linprog

    x = np.asarray(x, dtype="float64")
    y = np.asarray(y, dtype="float64")
    escala = np.abs(x).max(axis=0)
    escala[escala == 0] = 1.0
    sinalizada = (x / escala) * np.where(y > 0.5, 1.0, -1.0)[:, None]
    casos, colunas = sinalizada.shape
    otimo = linprog(
        -sinalizada.sum(axis=0),
        A_ub=-sinalizada,
        b_ub=np.zeros(casos),
        bounds=[(-1.0, 1.0)] * colunas,
        method="highs",
    )
    return bool(otimo.status == 0 and -otimo.fun > TOLERANCIA_DA_SEPARACAO)


def colunas_colineares(x: Any) -> tuple[int, ...]:
    """
    As colunas da matriz que são combinação exata das anteriores, como o `lm.fit` as
    acha: a parte nova de cada coluna, depois de tirado o que as anteriores explicam,
    medida contra o tamanho da própria coluna, com o `tol = 1e-7` do R.

    É a ordem do R também: entre duas colunas iguais, a segunda é a colinear — e é
    ela que leva o `NA` no `lm`, e o nome no motivo daqui.
    """
    import numpy as np

    x = np.asarray(x, dtype="float64")
    colineares: list[int] = []
    mantidas: list[int] = []
    for coluna in range(x.shape[1]):
        vetor = x[:, coluna]
        tamanho = float(np.linalg.norm(vetor))
        if mantidas:
            base = x[:, mantidas]
            projecao, *_ = np.linalg.lstsq(base, vetor, rcond=None)
            vetor = vetor - base @ projecao
        if tamanho == 0 or float(np.linalg.norm(vetor)) < TOLERANCIA_DO_POSTO * tamanho:
            colineares.append(coluna)
        else:
            mantidas.append(coluna)
    return tuple(colineares)


# As tabelas e as figuras


def _tabela(modelos: tuple[ModeloAjustado, ...], total: int) -> Tabela:
    """
    O resumo: uma linha por modelo, na ordem da ficha.

    O ajuste e o teste global de cada um — o R² e o F na linear, os eventos, o AIC e
    a razão de verossimilhança na logística. O que decidiu cada modelo vai para as
    notas, uma frase por modelo, e para o manifesto.
    """
    corpo = tuple(
        (
            modelo.rotulo_do_desfecho,
            modelo.nome_do_modelo,
            ", ".join(modelo.rotulos_dos_preditores),
            str(modelo.validos),
            _celula_do_ajuste(modelo),
            _celula_do_teste(modelo),
            valor_p(modelo.ajuste.p_do_teste if modelo.ajuste else None),
        )
        for modelo in modelos
    )
    menor_p = _fixo(MENOR_P, 3)
    notas = (
        "modelo escolhido pelo tipo do desfecho no dicionário: numérico, regressão linear "
        "— simples com um preditor, múltipla com dois ou mais —; categórico de duas "
        "categorias, regressão logística.",
        "linear: o lm do R. R² e R² ajustado do summary.lm, e o F do modelo contra o "
        "modelo só com o intercepto.",
        "logística: o glm do R com family = binomial. O evento é a segunda categoria do "
        f"desfecho na ordem do dicionário, ou a da chave `{CHAVE_EVENTO}:` da ficha. O "
        "modelo é testado pela razão de verossimilhança contra o modelo nulo (χ²), com o "
        "AIC ao lado.",
        "categórica entre os preditores: uma indicadora por categoria, contra a primeira "
        "categoria do dicionário, que é a referência.",
        f"n: casos com resposta no desfecho e em todos os preditores do modelo, de {total} "
        "linhas do banco; os faltantes são por modelo.",
        f"valor-p abaixo de {menor_p} sai como `< {menor_p}`; ele nunca é zero.",
        "cada modelo é ajustado à parte; não há correção para comparações múltiplas.",
    ) + tuple(modelo.justificativa for modelo in modelos)

    return Tabela(
        nome=ARQUIVO_TABELA,
        especie="regressao",
        # Vazia de propósito: esta tabela fala de vários modelos.
        variavel="",
        titulo="Modelos de regressão",
        colunas=("desfecho", "modelo", "preditores", "n", "ajuste", "teste global", "p-valor"),
        linhas=corpo,
        notas=notas,
    )


def _celula_do_ajuste(modelo: ModeloAjustado) -> str:
    ajuste = modelo.ajuste
    if ajuste is None:
        return _AUSENTE
    if ajuste.logistico:
        return f"{modelo.eventos} eventos; AIC = {_fixo(ajuste.aic, CASAS_AIC)}"
    return (
        f"R² = {_fixo(ajuste.r2, CASAS_R2)}; ajustado = {_fixo(ajuste.r2_ajustado, CASAS_R2)}"
    )


def _celula_do_teste(modelo: ModeloAjustado) -> str:
    ajuste = modelo.ajuste
    if ajuste is None:
        return f"sem modelo: {modelo.motivo}"
    valor = _fixo(ajuste.teste, CASAS_ESTATISTICA)
    if ajuste.logistico:
        return f"χ² = {valor}; {ajuste.gl_do_teste[0]} gl"
    return f"F = {valor}; {ajuste.gl_do_teste[0]} e {ajuste.gl_do_teste[1]} gl"


def _tabela_de_coeficientes(modelo: ModeloAjustado) -> Tabela:
    """
    Os coeficientes de um modelo: uma linha por termo, com a da categoria de
    referência no lugar dela.

    Na linear, o coeficiente na unidade do desfecho, com o intercepto na primeira
    linha. Na logística, o OR, e **sem** o intercepto: o OR dele é a chance do evento
    com todo preditor em zero e toda categórica na referência — um caso que quase
    nunca existe, e não é razão de chances de nada. Ele continua no manifesto.
    """
    ajuste = modelo.ajuste
    assert ajuste is not None
    logistico = ajuste.logistico
    linhas = []
    for termo in modelo.termos:
        if termo.referencia:
            linhas.append((termo.rotulo, REFERENCIA, _AUSENTE, _AUSENTE))
            continue
        coeficiente = ajuste.coeficientes[termo.indice]  # type: ignore[index]
        if logistico and termo.rotulo == INTERCEPTO:
            continue
        estimativa = coeficiente.estimativa
        baixo, alto = coeficiente.ic
        if logistico:
            estimativa, baixo, alto = _exp(estimativa), _exp(baixo), _exp(alto)
        casas = _casas(baixo, alto)
        linhas.append(
            (
                termo.rotulo,
                _fixo(estimativa, casas),
                f"{_fixo(baixo, casas)} a {_fixo(alto, casas)}",
                valor_p(coeficiente.p),
            )
        )

    if logistico:
        notas = (
            f"OR: a razão de chances de {modelo.evento} em {modelo.rotulo_do_desfecho} a "
            "cada unidade do preditor numérico, ou da categoria contra a de referência, "
            "com os outros preditores fixos. OR acima de 1 aumenta a chance do evento.",
            "IC 95% de Wald, exp(β ± 1,96·EP) — o confint.default do R —, coerente com o "
            "p da mesma linha: cruza o 1 exatamente quando p ≥ 0,05. O confint do R dá o "
            "de verossimilhança perfilada, que pode diferir em amostra pequena.",
            "p-valor do z de Wald, como o summary.glm do R.",
            "o intercepto fica no manifesto, e não na tabela: o OR dele não é razão de "
            "chances de nada.",
        )
        colunas = ("termo", "OR", "IC 95%", "p-valor")
    else:
        notas = (
            f"coeficiente: quanto {modelo.rotulo_do_desfecho} muda, em média, a cada "
            "unidade do preditor numérico, ou da categoria contra a de referência, com os "
            "outros preditores fixos — na unidade do desfecho.",
            f"IC 95% e p-valor pelo t com {ajuste.gl_residuo} graus de liberdade (n − p), "
            "como o summary.lm e o confint do R.",
        )
        colunas = ("termo", "coeficiente", "IC 95%", "p-valor")

    return Tabela(
        nome=f"{PREFIXO_COEFICIENTES}{modelo.slug}.csv",
        especie="coeficientes",
        variavel="",
        titulo=modelo.titulo,
        colunas=colunas,
        linhas=tuple(linhas),
        notas=notas + (modelo.justificativa,),
    )


def _graficos(modelo: ModeloAjustado) -> tuple[Grafico, ...]:
    """
    As duas figuras dos resíduos de uma linear: contra os valores ajustados, e o Q-Q.

    A primeira mostra o que o R² não mostra — a curva que uma reta não acompanha, a
    variação que abre para um lado, o caso sozinho num canto. A segunda, a normal que
    o t e o F supõem. Os pontos e a reta do Q-Q saem da função da normalidade, para a
    figura ser a mesma que ela desenharia com os mesmos números. A logística não tem
    figura: o resíduo dela não tem a forma que estas duas leem.
    """
    ajuste = modelo.ajuste
    if ajuste is None or ajuste.logistico:
        return ()
    subtitulo = f"n = {modelo.validos}"
    if modelo.faltantes:
        subtitulo += f" · {modelo.faltantes} sem resposta em alguma variável"
    residuos = pd.Series(ajuste.residuos)
    pontos_x, pontos_y, reta = pontos_do_qq(residuos, ajuste.n)
    graficos = [
        Grafico(
            nome=f"{PREFIXO_RESIDUOS}{modelo.slug}.png",
            especie="dispersao",
            variavel="",
            titulo=f"Resíduos — {modelo.formula}",
            subtitulo=subtitulo,
            rotulo_categoria="valores ajustados",
            rotulo_valor="resíduos",
            pontos_x=ajuste.ajustados,
            pontos_y=ajuste.residuos,
        )
    ]
    if reta is not None:
        graficos.append(
            Grafico(
                nome=f"{PREFIXO_QQ}{modelo.slug}.png",
                especie="qq",
                variavel="",
                titulo=f"Q-Q dos resíduos — {modelo.formula}",
                subtitulo=subtitulo,
                rotulo_categoria="quantis esperados da normal",
                rotulo_valor="resíduos",
                pontos_x=pontos_x,
                pontos_y=pontos_y,
                reta=reta,
            )
        )
    return tuple(graficos)


# Os modelos da ficha


def modelos_da_ficha(raiz: Path) -> tuple[Pedido, ...]:
    """
    A lista `regressao:` do `projeto.yaml`, conferida na forma.

    Um item é um modelo: o desfecho, dois-pontos e a lista dos preditores, e a chave
    `evento:` ao lado quando for preciso.

        - pas: [idade, imc]
        - obito: [idade, sexo]
          evento: Sim

    Devolve vazio quando a chave não existe ou está vazia — quem recusa isso é o
    `regredir`, que tem o dicionário na mão para escrever quais variáveis existem.
    Formato errado recusa em vez de ignorar, e lista todos os itens errados de uma
    vez.

    Raises:
        ModeloInvalidoError
    """
    bruto = bloco(raiz, PASTA_REGRESSAO)
    if bruto is None:
        return ()
    if not isinstance(bruto, list):
        raise ModeloInvalidoError(
            f"A chave `{PASTA_REGRESSAO}:` do {ARQUIVO_PROJETO} deveria ser uma lista, e "
            f"é {_descrever_valor(bruto)}.\n\n"
            f"Escreva assim, um modelo por item:\n\n{EXEMPLO_DA_FICHA}"
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
        raise ModeloInvalidoError(
            f"A lista `{PASTA_REGRESSAO}:` do {ARQUIVO_PROJETO} tem {len(problemas)} "
            "item(ns) fora do formato. Nada foi gerado.\n\n"
            + "\n".join(problemas)
            + f"\n\nEscreva assim, um modelo por item:\n\n{EXEMPLO_DA_FICHA}\n\n"
            "O desfecho vem antes dos dois-pontos e os preditores depois, entre "
            f"colchetes. A chave `{CHAVE_EVENTO}:`, na linha de baixo e alinhada com o "
            "desfecho, só vale na logística, e só quando a regra não serve."
        )
    return tuple(pedidos)


def _ler_item(item: Any) -> tuple[Pedido | None, str]:
    """Um item da lista: o pedido, ou o motivo de ele não servir."""
    if isinstance(item, list):
        nomes = [_nome(nome) for nome in item]
        desfecho = nomes[0] if nomes and nomes[0] else "pas"
        preditores = ", ".join(nome for nome in nomes[1:] if nome) or "idade"
        return None, (
            f"{_descrever_valor(item)} — um modelo se escreve com dois-pontos, o desfecho "
            f"antes deles e os preditores depois: `- {desfecho}: [{preditores}]`."
        )
    if not isinstance(item, dict) or not item:
        return None, (
            f"{_descrever_valor(item)} — um modelo se escreve `desfecho: [preditores]`, "
            "como `pas: [idade, imc]`."
        )

    # `- evento: [idade]`, sozinho, é um desfecho chamado `evento`; ao lado de outro
    # desfecho, é a chave — e a lista ali é o engano de quem escreveu `[Sim]`.
    tem_evento = CHAVE_EVENTO in item and (
        len(item) > 1 or not isinstance(item[CHAVE_EVENTO], list)
    )
    desfechos = [chave for chave in item if not (tem_evento and chave == CHAVE_EVENTO)]
    if not desfechos:
        return None, (
            f"`{CHAVE_EVENTO}:` sem o modelo — ela vai na linha de baixo de um "
            f"`desfecho: [preditores]`, alinhada com ele."
        )
    if len(desfechos) > 1:
        return None, (
            f"{len(desfechos)} desfechos no mesmo item ({', '.join(desfechos)}) — um item "
            "é um modelo; escreva cada um com o seu hífen."
        )

    chave = desfechos[0]
    valor = item[chave]
    desfecho = _nome(chave)
    outros = valor if isinstance(valor, list) else [valor]
    nomes = [_nome(nome) for nome in outros]
    if not desfecho or not nomes or not all(nomes):
        return None, (
            f"`{chave}: {_descrever_valor(valor)}` — depois dos dois-pontos vem a lista dos "
            f"preditores de `{chave}`, entre colchetes, com pelo menos um nome."
        )

    evento = ""
    if tem_evento:
        evento = _evento_escrito(item[CHAVE_EVENTO])
        if not evento:
            return None, (
                f"`{CHAVE_EVENTO}: {_descrever_valor(item[CHAVE_EVENTO])}` — o evento é uma "
                f"categoria do desfecho, pelo rótulo ou pelo código: `{CHAVE_EVENTO}: Sim` "
                f"ou `{CHAVE_EVENTO}: 1`."
            )
    return Pedido(desfecho, tuple(nomes), evento), ""


def _evento_escrito(valor: Any) -> str:
    """
    O evento como a ficha o trouxe, em texto; vazio quando não é um.

    O número sai como o código sai do banco — `1`, e não `1.0` —, e o lógico não vale:
    o YAML lê `sim` e `não` como texto, e um `true` ali quase sempre é engano.
    """
    if valor is None or isinstance(valor, bool | list | dict):
        return ""
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor).strip()


def _como_pedido(item: Pedido | tuple[Any, ...]) -> Pedido:
    if isinstance(item, Pedido):
        return item
    desfecho, preditores, *resto = item
    if isinstance(preditores, str):
        preditores = (preditores,)
    evento = str(resto[0]) if resto else ""
    return Pedido(str(desfecho), tuple(str(nome) for nome in preditores), evento)


def _nome(valor: Any) -> str:
    """
    O nome de uma variável, como a ficha o trouxe; vazio quando não é um nome.
    """
    if valor is None or isinstance(valor, list | dict | bool):
        return ""
    return str(valor).strip()


def _conferir_pedidos(pedidos: Sequence[Pedido], linhas: Sequence[Linha]) -> list[Pergunta]:
    """
    Confere cada modelo contra o dicionário, e recusa listando todos os problemas.

    Os nomes fora do dicionário, marcados `ignorar` ou fora desta versão do banco; a
    variável que não é numérica nem categórica; o desfecho entre os próprios
    preditores; o preditor escrito duas vezes; o `evento:` num desfecho numérico; e
    o mesmo modelo duas vezes — com os preditores em outra ordem, que é o mesmo
    modelo.
    """
    por_nome = {linha.variavel: linha for linha in linhas}
    perguntas: list[Pergunta] = []
    problemas: list[str] = []
    vistos: dict[tuple[str, frozenset[str]], str] = {}

    for pedido in pedidos:
        motivos = [
            motivo
            for motivo in (
                _motivo_de_recusa(nome, por_nome.get(nome))
                for nome in dict.fromkeys((pedido.desfecho, *pedido.preditores))
            )
            if motivo
        ]
        if pedido.desfecho in pedido.preditores:
            motivos.append(f"`{pedido.desfecho}` é o desfecho e está entre os preditores")
        repetidos = [nome for nome, vezes in Counter(pedido.preditores).items() if vezes > 1]
        if repetidos:
            motivos.append(f"`{repetidos[0]}` duas vezes entre os preditores")
        desfecho = por_nome.get(pedido.desfecho)
        if pedido.evento and desfecho is not None and desfecho.tipo == NUMERICA:
            motivos.append(
                f"`{CHAVE_EVENTO}:` só vale na logística, e `{pedido.desfecho}` está marcada "
                f"`{NUMERICA}` — o desfecho da logística é uma `{CATEGORICA}` de duas "
                "categorias"
            )
        chave = (pedido.desfecho, frozenset(pedido.preditores))
        if chave in vistos:
            motivos.append(f"repete `{vistos[chave]}`; um modelo se ajusta uma vez")
        else:
            vistos[chave] = pedido.escrito

        if motivos:
            problemas.append(f"  {pedido.escrito} — " + "; ".join(motivos))
            continue
        perguntas.append(
            Pergunta(
                desfecho=por_nome[pedido.desfecho],
                preditores=tuple(por_nome[nome] for nome in pedido.preditores),
                evento=pedido.evento,
            )
        )

    if problemas:
        raise ModeloInvalidoError(
            f"A lista `{PASTA_REGRESSAO}:` do {ARQUIVO_PROJETO} tem {len(problemas)} "
            "modelo(s) que não podem ser ajustados. Nada foi gerado.\n\n"
            + "\n".join(problemas)
            + "\n\nO desfecho e os preditores são variáveis `numerica` ou `categorica` do "
            f"{ARQUIVO_DICIONARIO}. Corrija o nome na lista do {ARQUIVO_PROJETO} — ele é "
            f"o da coluna `variavel` do {ARQUIVO_DICIONARIO} —, ou o `tipo` no dicionário, "
            "e rode de novo."
        )
    return perguntas


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
    regressao: Regressao, linhas: Sequence[Linha], com_graficos: bool = True
) -> Manifesto:
    """
    Traduz a rodada para o índice que o relatório vai ler.

    **Um item para o resumo, e um por modelo ajustado.** As outras análises que
    testam escrevem um item só, porque a seção delas é uma tabela; aqui cada modelo
    tem a sua tabela e as suas figuras, e um item por modelo é o que põe as figuras
    de um modelo logo depois da tabela dele no documento — com um item só, o
    relatório poria todas as tabelas antes de todas as figuras. O item do resumo vem
    primeiro e leva os `detalhes` de todos os modelos: é onde a metodologia os
    procura, como nas outras análises.
    """
    banco = regressao.banco
    leitura = banco.leitura
    ficha = regressao.ficha

    tabela = regressao.tabela
    resumo = ItemDoManifesto(
        variavel="",
        slug=PASTA_REGRESSAO,
        rotulo="Regressão",
        tipo=ANALISE_REGRESSAO,
        n=banco.linhas,
        faltantes=0,
        colunas=regressao.colunas_usadas,
        artefatos=(
            Artefato(arquivo=tabela.nome, especie=tabela.especie, formato="csv",
                     titulo=tabela.titulo),
        ),
        detalhes={
            "modelos": [modelo.como_detalhe() for modelo in regressao.modelos],
            "testados": len(regressao.ajustados),
            "linear_simples": regressao.quantos(LINEAR_SIMPLES),
            "linear_multipla": regressao.quantos(LINEAR_MULTIPLA),
            "logistica": regressao.quantos(LOGISTICA),
        },
        avisos=tuple(aviso for modelo in regressao.modelos for aviso in modelo.avisos),
    )

    por_modelo = []
    coeficientes = iter(regressao.coeficientes)
    graficos = {grafico.nome: grafico for grafico in regressao.graficos}
    for modelo in regressao.ajustados:
        tabela_do_modelo = next(coeficientes)
        artefatos = [
            Artefato(
                arquivo=tabela_do_modelo.nome,
                especie=tabela_do_modelo.especie,
                formato="csv",
                titulo=tabela_do_modelo.titulo,
            )
        ]
        if com_graficos:
            artefatos += [
                Artefato(arquivo=grafico.nome, especie=grafico.especie, formato="png",
                         titulo=grafico.titulo)
                for grafico in _graficos(modelo)
                if grafico.nome in graficos
            ]
        por_modelo.append(
            ItemDoManifesto(
                variavel="",
                slug=modelo.slug,
                rotulo=modelo.titulo,
                tipo=ANALISE_REGRESSAO,
                n=modelo.total,
                faltantes=modelo.faltantes,
                colunas=modelo.colunas,
                artefatos=tuple(artefatos),
            )
        )

    return Manifesto(
        analise=ANALISE_REGRESSAO,
        flatcap=__version__,
        gerado_em=regressao.quando,
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
            "modelos": f"os da lista `{PASTA_REGRESSAO}:` do {ARQUIVO_PROJETO}",
            "escolha_do_modelo": (
                "pelo tipo do desfecho no dicionário: numérico, linear (simples com um "
                "preditor, múltipla com dois ou mais); categórico de duas categorias, "
                "logística"
            ),
            "linear": "lm do R: QR; t com n − p gl; F contra o modelo só com o intercepto",
            "logistica": (
                f"glm do R com family = binomial: IRLS do glm.fit, até {MAXIMO_DE_ITERACOES} "
                f"iterações, convergência {TOLERANCIA_DA_DEVIANCE:g} na deviance; z de Wald; "
                "razão de verossimilhança contra o modelo nulo"
            ),
            "intervalo": (
                f"{CONFIANCA:.0%}: pelo t na linear (confint do R); de Wald na logística, "
                "exp(β ± 1,96·EP) (confint.default do R)"
            ),
            "referencia": "a primeira categoria do dicionário com caso no modelo",
            "evento": (
                f"a segunda categoria do desfecho no dicionário, ou a da chave "
                f"`{CHAVE_EVENTO}:` da ficha"
            ),
            "faltantes": "casos completos, por modelo (na.omit do R)",
            "residuos": "Shapiro-Wilk dos resíduos nas lineares",
            "eventos_por_coeficiente": MINIMO_DE_EVENTOS_POR_COEFICIENTE,
            "alfa": ALFA,
            "comparacoes_multiplas": "nenhuma correção",
            "graficos": com_graficos,
            "semente": SEMENTE,
        },
        itens=(resumo, *por_modelo),
        fora=tuple(
            {"variavel": f.variavel, "tipo": f.tipo, "motivo": f.motivo}
            for f in regressao.fora
        ),
        avisos=regressao.avisos,
    )


def _ambiente(com_graficos: bool) -> dict[str, Any]:
    """
    As versões que produziram estes números. O `numpy` entra porque a QR é dele, e o
    `scipy` porque as distribuições são dele.
    """
    import numpy
    import openpyxl
    import scipy

    ambiente: dict[str, Any] = {
        "python": ".".join(str(parte) for parte in sys.version_info[:3]),
        "flatcap": __version__,
        "pandas": pd.__version__,
        "numpy": numpy.__version__,
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


def _mensagem_sem_modelos(linhas: Sequence[Linha]) -> str:
    analisaveis = [
        linha.variavel
        for linha in linhas
        if linha.analisavel and linha.tipo in (NUMERICA, CATEGORICA)
    ]
    if analisaveis:
        disponiveis = (
            f"As variáveis numéricas e categóricas deste {ARQUIVO_DICIONARIO} são: "
            + ", ".join(analisaveis[:20])
            + (f" e mais {len(analisaveis) - 20}" if len(analisaveis) > 20 else "")
            + "."
        )
    else:
        disponiveis = (
            f"Nenhuma variável deste {ARQUIVO_DICIONARIO} está marcada `numerica` ou "
            "`categorica` ainda — reveja a coluna `tipo` antes."
        )
    return (
        f"O {ARQUIVO_PROJETO} deste projeto não diz quais modelos ajustar.\n\n"
        "Escreva a lista na ficha — o desfecho antes dos dois-pontos, os preditores "
        f"depois:\n\n{EXEMPLO_DA_FICHA}\n\n"
        f"{disponiveis} Desfecho numérico dá a regressão linear, e categórico de duas "
        "categorias, a logística.\n\n"
        "Quais preditores entram é decisão da reunião: o FlatCap não escolhe preditor, "
        "porque um modelo escolhido pelos dados dá p que não querem dizer o que dizem."
    )


def _motivo_de_fora(linha: Linha) -> str:
    if not linha.no_banco:
        return "não está nesta versão do banco (`no_banco = nao`)"
    if linha.tipo == IGNORAR:
        return "marcada `ignorar` no dicionário"
    return f"não está em nenhum modelo da lista `{PASTA_REGRESSAO}:` do {ARQUIVO_PROJETO}"


def _acao_do_historico(plano: PlanoRegressao) -> str:
    regressao = plano.regressao
    contagem = [(regressao.quantos(modelo), modelo.lower()) for modelo in MODELOS]
    quais = ", ".join(f"{quantos} {nome}" for quantos, nome in contagem if quantos)
    partes = [
        f"`flatcap regressao {regressao.ficha.record_id}` — regressão sobre "
        f"`{regressao.banco.versao.arquivo}`: {len(regressao.modelos)} modelo(s) da lista "
        f"`{PASTA_REGRESSAO}:`"
        + (f" ({quais})" if quais else "")
        + f", em `{PASTA_ANALISES}/{PASTA_REGRESSAO}/`."
    ]
    sem_modelo = len(regressao.modelos) - len(regressao.ajustados)
    if sem_modelo:
        partes.append(f"{sem_modelo} sem modelo.")
    if plano.arquivamento is not None:
        partes.append(
            f"A rodada anterior foi para `{PASTA_ANTIGAS}/{plano.arquivamento[1].name}/`."
        )
    if not plano.com_graficos:
        partes.append("Rodado com `--sem-graficos`.")
    return " ".join(partes)


# Formatação


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


def _rotulo_da_variavel(modelo: ModeloAjustado, variavel: str) -> str:
    for nome, rotulo in zip(modelo.preditores, modelo.rotulos_dos_preditores, strict=True):
        if nome == variavel:
            return rotulo
    return variavel


def _tipo_por_extenso(tipo: str) -> str:
    return {NUMERICA: "numérico", CATEGORICA: "categórico"}.get(tipo, tipo)


def _sem_acento(texto: str) -> str:
    limpo = unicodedata.normalize("NFKD", str(texto or "")).casefold().strip()
    return "".join(c for c in limpo if not unicodedata.combining(c))


def _normal_na_frase(normal: Normal) -> str:
    if normal.p is None:
        return f"não testado — {normal.impedimento}" if normal.impedimento else "não testado"
    texto = valor_p(normal.p)
    p = f"p {texto}" if texto.startswith("<") else f"p = {texto}"
    return f"W = {_fixo(normal.w, 3)}, {p}"


def _casas(baixo: float, alto: float) -> int:
    """
    Quantas casas o coeficiente e o IC levam: as que fazem a metade da largura do IC
    aparecer com dois algarismos significativos, entre `CASAS_MINIMAS` e
    `CASAS_MAXIMAS`.

    A precisão vem da incerteza, e não do tamanho do número: a idade em anos sai
    `0,77 (0,60 a 0,94)`, e a mesma idade em milésimos de ano, `0,00077 (0,00060 a
    0,00094)` — os mesmos algarismos, e não `0,0008 (0,0006 a 0,0009)`. A mesma conta
    vale para o OR, na escala dele: um OR por ano de idade sai `1,098 (1,036 a 1,165)`.
    """
    meia = abs(alto - baixo) / 2
    if not math.isfinite(meia) or meia <= 0:
        return CASAS_MINIMAS
    return min(CASAS_MAXIMAS, max(CASAS_MINIMAS, 1 - math.floor(math.log10(meia))))


def _fixo(valor: float | None, casas: int) -> str:
    """
    O número com casas fixas, vírgula decimal e o sinal quando é negativo: `-0,18`,
    nunca `-0,00`. Casas fixas, e não as do `descritiva.numero`, que tira o zero do
    fim: a coluna se lê de cima para baixo, como a do coeficiente da correlação.
    """
    if valor is None or not math.isfinite(valor):
        return _AUSENTE
    texto = f"{valor:.{casas}f}"
    if float(texto) == 0:
        texto = texto.lstrip("-")
    return texto.replace(".", ",")


def _coeficiente_como_detalhe(coeficiente: Coeficiente, logistico: bool) -> dict[str, Any]:
    detalhe: dict[str, Any] = {
        "termo": coeficiente.nome,
        "estimativa": _arredondar(coeficiente.estimativa),
        "erro_padrao": _arredondar(coeficiente.erro_padrao),
        "estatistica": _arredondar(coeficiente.estatistica),
        "p": _significativos(coeficiente.p),
        "ic_95": [_arredondar(coeficiente.ic[0]), _arredondar(coeficiente.ic[1])],
    }
    if logistico:
        detalhe["or"] = _significativos(_exp(coeficiente.estimativa))
        detalhe["ic_95_or"] = [
            _significativos(_exp(coeficiente.ic[0])),
            _significativos(_exp(coeficiente.ic[1])),
        ]
    return detalhe


def _exp(valor: float) -> float:
    """
    O `exp` que não estoura: infinito acima do maior expoente do `float`. Um IC de
    Wald muito largo passa disso mesmo sem separação, e a célula sai `—`.
    """
    return math.exp(valor) if valor < 709 else math.inf


def _arredondar(valor: float | None) -> float | None:
    if valor is None:
        return None
    valor = float(valor)
    return round(valor, 6) if math.isfinite(valor) else None


def _significativos(valor: float | None) -> float | None:
    """
    Seis algarismos significativos, e não seis casas: um p de 2,5e-08 com seis casas
    seria gravado `0.0`, e um OR de 0,0000318 também.
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
    "CHAVE_EVENTO",
    "CONFIANCA",
    "EXEMPLO_DA_FICHA",
    "INTERCEPTO",
    "LINEAR_MULTIPLA",
    "LINEAR_SIMPLES",
    "LOGISTICA",
    "MAXIMO_DE_ITERACOES",
    "MINIMO_DE_EVENTOS_POR_COEFICIENTE",
    "MODELOS",
    "PREFIXO_COEFICIENTES",
    "PREFIXO_QQ",
    "PREFIXO_RESIDUOS",
    "REFERENCIA",
    "Ajuste",
    "Coeficiente",
    "DicionarioAusenteError",
    "DicionarioDesatualizadoError",
    "ForaDaRegressao",
    "ModeloAjustado",
    "ModeloInvalidoError",
    "Normal",
    "Pedido",
    "Pergunta",
    "PlanoRegressao",
    "Regressao",
    "RegressaoError",
    "ResultadoRegressao",
    "SemModelosError",
    "Termo",
    "VariavelIncompativelError",
    "colunas_colineares",
    "executar_regressao",
    "linear",
    "logistica",
    "modelos_da_ficha",
    "montar_manifesto",
    "preparar_regressao",
    "regredir",
    "separacao",
]
