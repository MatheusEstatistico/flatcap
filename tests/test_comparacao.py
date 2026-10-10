# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Os testes do `comparacao.py`.

O miolo é testado pela função pura `comparar(banco, ficha, linhas, itens)`, como o
`correlacionar` da correlação e o `avaliar` da normalidade. O caminho do disco — a
ficha com a lista `comparacao:`, a rodada escrita, o relatório que a encontra — usa
os fixtures do `conftest.py`.

**Nenhum número daqui é conferido contra o próprio módulo.** As referências são três,
e independentes dele:

* o **R 4.3.3**: `t.test(x, mu = mu)` e `shapiro.test(x)` rodados sobre os valores
  preenchidos de cada coluna do banco de referência, com o resultado copiado para
  `REFERENCIAS_DO_R`;
* a **descritiva**: a média e o desvio da tabela são conferidos contra a tabela de
  resumo que a própria descritiva monta para a mesma coluna — letra por letra;
* a **normalidade**: o p do Shapiro-Wilk que decide a regra é conferido contra o da
  tabela de normalidade da mesma variável.

O banco de referência é o `bancos.para_comparar()`: sessenta casos e uma variável
para cada caminho da regra. Entre grupos, o `bancos.para_comparar_grupos()`, com o
`t.test(y ~ sexo, var.equal = TRUE)` e o `shapiro.test` de cada grupo rodados no R
sobre ele — em `STUDENT_DO_R` —, o `t.test(y ~ sexo)`, o de Welch, em `WELCH_DO_R`, e
o `oneway.test(y ~ escolaridade, var.equal = TRUE)` em `ANOVA_DO_R` e o
`oneway.test(y ~ escolaridade)`, o de Welch, em `ANOVA_DE_WELCH_DO_R`. Nas medidas
repetidas, o `bancos.para_comparar_repetidas()`, com o `aov` e o ε de Greenhouse-Geisser
do R em `REPETIDAS_DO_R`.

Os testes de postos sobre os mesmos bancos: o `wilcox.test(x, mu = mu, conf.int = TRUE)`
em `WILCOXON_DO_R`, o `wilcox.test(x ~ sexo, conf.int = TRUE)` em `MANN_WHITNEY_DO_R`, o
`kruskal.test` em `KRUSKAL_DO_R` e o `friedman.test` em `FRIEDMAN_DO_R` — com a mediana e
os quartis do `quantile` do R, o tipo 7, que é o do `pandas`.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

import bancos
from conftest import (
    AGORA,
    RECORD_ID,
    acrescentar_a_ficha,
    banco_em_memoria,
    ficha_em_memoria,
    linhas_do_historico,
)
from flatcap.comparacao import (
    ANOVA,
    ANOVA_DE_MEDIDAS_REPETIDAS,
    ANOVA_DE_WELCH,
    ARQUIVO_DOIS_GRUPOS,
    ARQUIVO_K_GRUPOS,
    ARQUIVO_REPETIDAS,
    ARQUIVO_TABELA,
    COLUNA_DA_MEDIA,
    COLUNA_DA_MEDIANA,
    COLUNA_DA_DIFERENCA,
    COLUNA_DA_DIFERENCA_DE_LOCACAO,
    COLUNA_DAS_DUAS,
    COLUNA_DAS_DUAS_DIFERENCAS,
    COLUNA_DO_IC,
    COLUNA_DO_IC_DA_MEDIA,
    COLUNA_DO_IC_DA_PSEUDOMEDIANA,
    DOIS_GRUPOS,
    FRIEDMAN,
    K_GRUPOS,
    KRUSKAL_WALLIS,
    MANN_WHITNEY,
    REGRA,
    REPETIDAS,
    T_DE_WELCH,
    UMA_AMOSTRA,
    WILCOXON,
    Grupo,
    ItemInvalidoError,
    Normal,
    Pedido,
    SemItensError,
    VariavelIncompativelError,
    comparar,
    executar_comparacao,
    itens_da_ficha,
    linhas_da_tabela,
    metodo_escrito,
    montar_manifesto,
    preparar_comparacao,
    referencia_escrita,
    regra,
)
from flatcap.dicionario import CATEGORICA, DATA, IGNORAR, NUMERICA, Linha
from flatcap.hipoteses import T_DE_STUDENT
from flatcap.manifesto import (
    ANALISE_COMPARACAO,
    ANALISE_CORRELACAO,
    ARQUIVO_MANIFESTO,
    ORDEM_PADRAO_DAS_ANALISES,
)
from flatcap.manifesto import ler as ler_manifesto
from flatcap.normalidade import valor_p
from flatcap.projeto import ARQUIVO_PROJETO, PASTA_ANALISES, PASTA_ANTIGAS, PASTA_COMPARACAO

IMC = Linha("imc", "IMC (kg/m²)", NUMERICA)
RENDA = Linha("renda", "Renda", NUMERICA)
PAS = Linha("pas", "PAS (mmHg)", NUMERICA)
DOR = Linha("dor", "Dor", NUMERICA)
SERVICO = Linha("servico", "Serviço", NUMERICA)
SEXO = Linha(
    "sexo",
    "Sexo",
    CATEGORICA,
    ("1", "2"),
    rotulos_das_categorias=(("1", "Feminino"), ("2", "Masculino")),
)
DICIONARIO = (IMC, RENDA, PAS, DOR, SERVICO, SEXO)

# Um item para cada caminho da regra, na ordem em que a ficha os escreveria.
ITENS = (("imc", 25), ("renda", 2500), ("pas", 120), ("dor", 2), ("servico", 1))

# O que se escreve na ficha para o banco de referência do `conftest`, que tem `imc`
# numérica com 24 valores perto da normal — o item vai para o t.
BLOCO = "comparacao:\n  - [imc, 25]\n"

# `t.test(x, mu = mu)` e `shapiro.test(x)` no R 4.3.3, sobre os valores preenchidos
# de cada coluna do `bancos.para_comparar()`:
#
#     (variável, referência, n, t, gl, p, IC 95%, média, DP, W, p do Shapiro-Wilk)
REFERENCIAS_DO_R = [
    ("imc", 25, 57, 2.1589496648908169, 56, 0.035153771078460752,
     (25.067061314497252, 26.792587808309769), 25.92982456140351, 3.2515910892252151,
     0.99868524068270148, 0.99999999575494525),
    ("pas", 120, 12, 2.0211646105596457, 11, 0.068279558890011458,
     (119.28824976019266, 136.71175023980734), 128, 13.711309200802088,
     0.99761500059351005, 0.99999999982982346),
    ("renda", 3000, 60, 1.0465304628501841, 59, 0.2995847745738931,
     (2629.6063424797826, 4182.6356575202171), 3406.1210000000001, 3005.9323170801404,
     0.78198395803984677, 4.9334558793744215e-08),
    ("renda", 2500, 60, 2.3349770869476623, 59, 0.022966391527098378,
     (2629.6063424797826, 4182.6356575202171), 3406.1210000000001, 3005.9323170801404,
     0.78198395803984677, 4.9334558793744215e-08),
    ("dor", 2, 60, 3.1894221722913145, 59, 0.0022832007322331699,
     (2.1863075394232414, 2.813692460576759), 2.5, 1.214321321226981,
     0.93849726755535645, 0.0046416092729572398),
]


ESCOLARIDADE = Linha(
    "escolaridade", "Escolaridade", CATEGORICA, ("Fundamental", "Médio", "Superior")
)
UNICO = Linha("unico", "Único", CATEGORICA, ("Sim", "Não"))
NOTA = Linha("nota", "Nota", NUMERICA)
DICIONARIO_DOS_GRUPOS = (IMC, RENDA, PAS, NOTA, SEXO, ESCOLARIDADE, UNICO)

# `t.test(y ~ sexo, var.equal = TRUE)` e `shapiro.test` de cada grupo no R 4.3.3,
# sobre os casos com as duas respostas de `bancos.para_comparar_grupos()`:
#
#     (variável, t, gl, p, IC 95% da diferença, diferença,
#      (n, média, DP, W, p do Shapiro-Wilk) de Feminino, e de Masculino)
STUDENT_DO_R = [
    ("imc", -2.4618783619938953, 55, 0.016984290698757613,
     (-4.2106960953985766, -0.4316684366211293), -2.3211822660098527,
     (29, 25.093103448275862, 2.991169269041642, 0.99818204123713317, 0.99999999852886789),
     (28, 27.414285714285715, 4.0642719985634423, 0.99749191686668337, 0.99999994602138065)),
    ("renda", -1.3648620657924699, 56, 0.17775536880382911,
     (-3667.5803695350742, 695.1406076303125), -1486.2198809523807,
     (30, 4027.2683333333334, 3446.6945090363411, 0.80787831480217842,
      9.1554482106078337e-05),
     (28, 5513.4882142857141, 4780.9913942186704, 0.80993134361523256,
      0.00016056404374919313)),
    ("pas", -1.6947084199135862, 56, 0.09568549835895368,
     (-10.988211946722654, 0.91678337529406928), -5.0357142857142918,
     (30, 120, 5.0172117548598099, 0.99680258517098719, 0.99999886442708763),
     (28, 125.03571428571429, 15.433206485816951, 0.99656497471796757, 0.99999845897126383)),
]


# `t.test(y ~ sexo)` — o de Welch, o padrão do R — sobre os mesmos casos:
#
#     (variável, t, gl, p, IC 95% da diferença)
WELCH_DO_R = [
    ("imc", -2.4488369544641682, 49.555531555674087, 0.01791411670863783,
     (-4.2254609788177149, -0.41690355320198996)),
    ("renda", -1.3498028089754837, 48.84623085210292, 0.18330168372893915,
     (-3699.0679276236488, 726.62816571888789)),
    ("pas", -1.6472381629313293, 32.296650638913157, 0.10920625091215552,
     (-11.26050969312937, 1.1890811217007851)),
]


# `oneway.test(y ~ escolaridade, var.equal = TRUE)` e `shapiro.test` de cada grupo no
# R 4.3.3, sobre os casos com as duas respostas de `bancos.para_comparar_grupos()`:
#
#     (variável, F, gl, p, ((n, média, DP, W, p do Shapiro-Wilk) de cada escolaridade))
ANOVA_DO_R = [
    ("nota", 6.387986103328477, (2, 57), 0.0031391736550230066, (
        (20, 6, 1.0052493799000692, 0.99781599578856017, 0.99999999881473456),
        (20, 7, 1.4853672237779061, 0.99757496054163186, 0.9999999957732697),
        (20, 8, 2.4851135735986416, 0.99834812318513499, 0.9999999999677488),
    )),
    ("imc", 0.11624423716069375, (2, 56), 0.89047201374920881, (
        (20, 25.954999999999998, 3.766119739829954, 0.99669095554062048, 0.99999985724646479),
        (19, 26.331578947368421, 3.6157145646283388, 0.99168933343034105, 0.99957916454533602),
        (20, 26.515000000000001, 3.8354681317244292, 0.97605184600851136, 0.87368281207131027),
    )),
]


# `oneway.test(y ~ escolaridade)` — a ANOVA de Welch, o padrão do R:
#
#     (variável, F, gl, p)
ANOVA_DE_WELCH_DO_R = [
    ("nota", 7.1088234461909936, (2, 34.461935431552092), 0.0026015438081409816),
    ("imc", 0.11146986509410804, (2, 37.324143867146049), 0.89481500877396836),
]


PAS_0 = Linha("pas_0", "PAS basal", NUMERICA)
PAS_1 = Linha("pas_1", "PAS 30 dias", NUMERICA)
PAS_2 = Linha("pas_2", "PAS 90 dias", NUMERICA)
DICIONARIO_DAS_REPETIDAS = (
    PAS_0,
    PAS_1,
    PAS_2,
    *(Linha(f"dor_{j}", f"Dor {j}", NUMERICA) for j in range(3)),
    *(Linha(f"peso_{j}", f"Peso {j}", NUMERICA) for j in range(3)),
    SEXO,
)
ITEM_PAS = ("repetidas", ["pas_0", "pas_1", "pas_2"])
ITEM_DOR = ("repetidas", ["dor_0", "dor_1", "dor_2"])

# O F do `aov(y ~ t + Error(id / t))`, o ε de Greenhouse-Geisser, o p com os gl
# corrigidos, e de cada medida o n, a média, o DP e o Shapiro-Wilk — no R 4.3.3, sobre
# os casos completos de `bancos.para_comparar_repetidas()`:
#
#     (medidas, n, F, ε, gl corrigidos, p, ((n, média, DP, W, p) de cada medida))
REPETIDAS_DO_R = [
    ("pas", 38, 37.039678284182543, 0.91843540650364708,
     (1.8368708130072942, 67.964220081269886), 4.3421958447113387e-11, (
         (38, 130, 11.793264225017648, 0.9822655892357709, 0.7961345117822366),
         (38, 126.81578947368421, 12.089430861255437, 0.9840043274168192, 0.85184392453344859),
         (38, 124.28947368421052, 12.595382883651265, 0.97763079287965116, 0.63337362446588985),
     )),
    ("dor", 40, 1.9436744323208446, 0.97681901825756734,
     (1.9536380365151347, 76.19188342409025), 0.15118716398253323, (
         (40, 0.875, 1.0423715563744347, 0.79668827962160405, 5.7828308311489843e-06),
         (40, 0.675, 0.88831445113910201, 0.74783655435326679, 6.5318723163127651e-07),
         (40, 0.5, 0.78446454055273618, 0.67595376665524665, 4.0119023533906341e-08),
     )),
]


# `wilcox.test(x, mu = mu, conf.int = TRUE)` e os quartis do `quantile` no R 4.3.3, sobre
# os valores preenchidos de cada coluna do `bancos.para_comparar()`. Os quatro saem pelo
# caminho aproximado: o `imc`, a `pas` e a `dor` têm empates, e a `renda` tem 60 valores.
#
#     (variável, referência, n, V, p, intervalo, pseudomediana, (Q1, mediana, Q3))
WILCOXON_DO_R = [
    ("imc", 25, 57, 1045, 0.04434606447362853, (25.049954259748258, 26.850055606284094),
     25.949974346305162, (23.800000000000001, 25.899999999999999, 28.100000000000001)),
    ("renda", 2500, 60, 1080, 0.22590165422430941, (2294.1549745390657, 3571.2350523829291),
     2859.9133692828482, (1472.8099999999999, 2500.3500000000004, 4245.0025000000005)),
    ("renda", 3000, 60, 857, 0.67208210447232886, (2294.1549745390657, 3571.2350523829291),
     2859.9133692828482, (1472.8099999999999, 2500.3500000000004, 4245.0025000000005)),
    ("pas", 120, 12, 53.5, 0.075224005505574107, (118.00001225906372, 139.00004409673397),
     128.98295551117241, (119.25, 128, 136.75)),
    ("dor", 2, 60, 676.5, 0.0036106760940327327, (2.0000324580139814, 3.0000592965142925),
     2.9999702707384235, (2, 2.5, 3)),
]

# `wilcox.test(y ~ sexo, conf.int = TRUE)` no R 4.3.3, sobre os casos com as duas
# respostas de `bancos.para_comparar_grupos()` — a `renda`, sem empates, pelo caminho
# exato —, e a mediana e os quartis de cada grupo:
#
#     (variável, W, p, intervalo, diferença de locação, p exato,
#      (n, mediana, Q1, Q3) de Feminino, e de Masculino)
MANN_WHITNEY_DO_R = [
    ("imc", 262, 0.021968988265092266, (-4.2999906773165968, -0.30004771234261629),
     -2.3000693220893584, False,
     (29, 25.100000000000001, 23.300000000000001, 27),
     (28, 27.399999999999999, 24.900000000000002, 30.200000000000003)),
    ("renda", 331, 0.1697319562818404, (-2414.4799999999996, 406.9699999999998),
     -921.57000000000005, True,
     (30, 2982.625, 1774.6175000000001, 5013.5425000000005),
     (28, 4026.1199999999999, 2445.7425000000003, 7059.4100000000008)),
    ("pas", 313, 0.097252628477293851, (-11.000003542479366, 1.0000082369992551), -5, False,
     (30, 120, 117, 123), (28, 125, 115.25, 135.5)),
]

# `kruskal.test(y ~ escolaridade)` no R 4.3.3, e a mediana e os quartis de cada grupo:
#
#     (variável, qui-quadrado, gl, p, ((n, mediana, Q1, Q3) de cada escolaridade))
KRUSKAL_DO_R = [
    ("nota", 10.593673894912445, 2, 0.0050074075772655784, (
        (20, 6, 5.3500000000000005, 6.6499999999999995),
        (20, 7, 6.0499999999999989, 7.9500000000000011),
        (20, 8, 6.4000000000000004, 9.5999999999999996),
    )),
    ("imc", 0.16688558031346395, 2, 0.91994371500154348, (
        (20, 25.899999999999999, 23.525000000000002, 28.149999999999999),
        (19, 26.399999999999999, 24.200000000000003, 28.600000000000001),
        (20, 26.199999999999999, 23.800000000000001, 28.474999999999998),
    )),
    ("renda", 0.13114754098361914, 2, 0.93652995593578336, (
        (20, 3360.6599999999999, 1965.4549999999999, 5641.915),
        (20, 3463.96, 2083.6849999999999, 5775.3400000000001),
        (20, 3593.8900000000003, 2131.23, 6127.8599999999997),
    )),
]

# `friedman.test` no R 4.3.3, sobre os casos completos de
# `bancos.para_comparar_repetidas()`, e a mediana e os quartis de cada medida. O `peso`
# é o caso em que a ANOVA não pode: cada caso ganha um quilo por medida, e o Friedman tem
# os mesmos postos em todo caso — o qui-quadrado é n(k − 1), o maior que existe.
#
#     (base, n, qui-quadrado, gl, p, ((mediana, Q1, Q3) de cada medida))
FRIEDMAN_DO_R = [
    ("pas", 38, 40.013888888888886, 2, 2.0468896406542972e-09,
     ((130, 124, 136.75), (126.5, 119.25, 135), (124.5, 116.5, 131.75))),
    ("dor", 40, 2.0808080808080809, 2, 0.35331190083288583,
     ((1, 0, 1.25), (0, 0, 1), (0, 0, 1))),
    ("peso", 40, 80, 2, 4.2483542552915889e-18,
     ((70, 64.125, 75.875), (71, 65.125, 76.875), (72, 66.125, 77.875))),
]


def _repetidas(itens, quadro=None, linhas=DICIONARIO_DAS_REPETIDAS):
    quadro = bancos.para_comparar_repetidas() if quadro is None else quadro
    return comparar(banco_em_memoria(quadro), ficha_em_memoria(), linhas, itens, AGORA)


def _comparar(quadro=None, linhas=DICIONARIO, itens=ITENS):
    quadro = bancos.para_comparar() if quadro is None else quadro
    return comparar(banco_em_memoria(quadro), ficha_em_memoria(), linhas, itens, AGORA)


def _linha(resultado, variavel: str, referencia: float | None = None):
    return next(
        v
        for v in resultado.variaveis
        if v.variavel == variavel and (referencia is None or v.referencia == referencia)
    )


def _como_a_descritiva(valor: float) -> str:
    """A estatística com até duas casas, sem os zeros do fim — escrita aqui de novo."""
    texto = f"{round(valor, 2):.2f}".rstrip("0").rstrip(".")
    return texto.replace(".", ",")


def _duas_casas(valor: float) -> str:
    texto = f"{valor:.2f}"
    return ("0.00" if float(texto) == 0 else texto).replace(".", ",")


def _mediana_quartis(mediana: float, q1: float, q3: float) -> str:
    """`25,9 [23,8 a 28,1]`, com cada número como a descritiva o escreve."""
    return (
        f"{_como_a_descritiva(mediana)} [{_como_a_descritiva(q1)} a "
        f"{_como_a_descritiva(q3)}]"
    )


def _quartis_conferidos(resumo: dict[str, float], mediana: float, q1: float, q3: float) -> str:
    """
    Confere a mediana e os quartis do resumo com os do R e devolve a célula esperada.

    O `quantile` do R e o do numpy chegam ao mesmo número por contas diferentes, e às
    vezes a um bit um do outro: o Q3 de 28,475 é 28,474999999999998 no R e
    28,475000000000001 aqui — e as duas casas de cada um são 28,47 e 28,48. Os números
    conferem com o R; a célula, com a descritiva escrevendo os números do próprio
    resumo, que é o que a descritiva escreveria no relatório.
    """
    assert (resumo["mediana"], resumo["q1"], resumo["q3"]) == pytest.approx(
        (mediana, q1, q3), rel=1e-14
    )
    return _mediana_quartis(resumo["mediana"], resumo["q1"], resumo["q3"])


def _uma(nome: str, valores: list) -> tuple[pd.DataFrame, tuple[Linha, ...]]:
    """Um banco de uma coluna só, com a linha do dicionário que a declara numérica."""
    return pd.DataFrame({nome: valores}), (Linha(nome, nome.upper(), NUMERICA),)


def _grupos(itens, quadro=None, linhas=DICIONARIO_DOS_GRUPOS):
    quadro = bancos.para_comparar_grupos() if quadro is None else quadro
    return comparar(banco_em_memoria(quadro), ficha_em_memoria(), linhas, itens, AGORA)


def _dois(a: list, b: list) -> tuple[pd.DataFrame, tuple[Linha, ...]]:
    """Um banco de dois grupos escritos à mão: `y` numérica, `g` com `A` e `B`."""
    quadro = pd.DataFrame({"y": [*a, *b], "g": ["A"] * len(a) + ["B"] * len(b)})
    return quadro, (Linha("y", "Y", NUMERICA), Linha("g", "G", CATEGORICA, ("A", "B")))


def _tres(a: list, b: list, c: list) -> tuple[pd.DataFrame, tuple[Linha, ...]]:
    """Três grupos escritos à mão: `y` numérica, `g` com `A`, `B` e `C`."""
    quadro = pd.DataFrame(
        {"y": [*a, *b, *c], "g": ["A"] * len(a) + ["B"] * len(b) + ["C"] * len(c)}
    )
    return quadro, (Linha("y", "Y", NUMERICA), Linha("g", "G", CATEGORICA, ("A", "B", "C")))


# ── O R ─────────────────────────────────────────────────────────────────────


class TestReferenciasDoR:
    @pytest.mark.parametrize(
        ("variavel", "mu", "n", "t", "gl", "p", "ic", "media", "dp", "w", "p_shapiro"),
        REFERENCIAS_DO_R,
        ids=[f"{variavel}-mu{mu}" for variavel, mu, *_ in REFERENCIAS_DO_R],
    )
    def test_o_t_test_e_o_shapiro_test_do_r(
        self, variavel, mu, n, t, gl, p, ic, media, dp, w, p_shapiro
    ):
        """
        Com `t` escrito no item, a linha tem o t mesmo onde a regra não o escolheria —
        e aí dá para conferir o t de todas as colunas contra o R.
        """
        linha = _comparar(itens=((variavel, mu, "t"),)).variaveis[0]
        resultado = linha.resultado
        assert linha.validos == n
        assert resultado.estatistica == pytest.approx(t, rel=1e-12)
        assert resultado.gl == (gl,)
        assert resultado.p == pytest.approx(p, rel=1e-10)
        assert resultado.ic == pytest.approx(ic, rel=1e-12)
        assert resultado.estimativa == pytest.approx(media, rel=1e-12)
        assert linha.resumo["media"] == pytest.approx(media, rel=1e-12)
        assert linha.resumo["desvio"] == pytest.approx(dp, rel=1e-12)
        assert linha.normal.w == pytest.approx(w, rel=1e-6)
        assert linha.normal.p == pytest.approx(p_shapiro, rel=1e-4)

    def test_o_shapiro_da_escolha_e_o_da_tabela_de_normalidade(self):
        """
        A mesma função sobre os mesmos valores: o p que decide a regra é, número por
        número, o que a tabela de normalidade imprime para a variável.
        """
        from flatcap.normalidade import avaliar

        quadro = bancos.para_comparar()
        normalidade = avaliar(
            banco_em_memoria(quadro), ficha_em_memoria(), DICIONARIO, (), AGORA, False
        )
        comparacao = _comparar(quadro)
        for nome in ("imc", "renda", "pas", "dor"):
            testada = next(v for v in normalidade.variaveis if v.variavel == nome)
            assert _linha(comparacao, nome).normal.p == testada.p
            assert _linha(comparacao, nome).normal.w == testada.w


# ── A regra ─────────────────────────────────────────────────────────────────


class TestRegra:
    def test_a_normal_que_se_sustenta_vai_para_o_t(self):
        linha = _linha(_comparar(), "imc")
        assert linha.metodo == T_DE_STUDENT
        assert linha.escolha.motivo == "o Shapiro-Wilk não rejeita a normal (p = 1,000)"
        assert not linha.escolha.pela_ficha

    def test_a_normal_rejeitada_vai_para_o_wilcoxon(self):
        """
        `wilcox.test(renda, mu = 2500)`: V = 1080, p = 0,2259 — pela aproximação normal,
        porque são 60 valores. O t da mesma linha daria p = 0,023: a renda é assimétrica,
        e a mediana dela é a referência.
        """
        linha = _linha(_comparar(), "renda")
        assert linha.metodo == WILCOXON
        assert (linha.escolha.metodo, linha.escolha.da_regra) == (WILCOXON, WILCOXON)
        assert linha.escolha.motivo == "o Shapiro-Wilk rejeita a normal (p < 0,001)"
        assert linha.celula_do_teste == WILCOXON
        assert linha.resultado.estatistica == 1080
        assert linha.resultado.p == pytest.approx(0.22590165422430941, rel=1e-12)

    def test_o_p_do_shapiro_fica_na_nota_e_nao_na_celula(self):
        """
        Na coluna estreita do documento, `(p < 0,001)` quebrava entre o `<` e o número.
        A célula diz o motivo; o p que decidiu fica na frase da nota.
        """
        comparacao = _comparar()
        linha = _linha(comparacao, "dor")
        assert linha.celula_do_teste == WILCOXON
        assert "o Shapiro-Wilk rejeita a normal (p = 0,005)" in linha.justificativa
        texto = comparacao.tabela_de(UMA_AMOSTRA).texto()
        assert "o Shapiro-Wilk rejeita a normal (p = 0,005)" in texto

    def test_o_teste_de_postos_que_falta_no_registro(self, monkeypatch):
        """
        O caminho de quando o teste da regra ainda não tem aritmética — o de todo teste
        novo que entra na regra antes do cálculo, e o do Wilcoxon até a 1.14.0. Tirado
        ele do registro, a linha sai sem teste, e o aviso ensina a escrever o t.
        """
        import flatcap.comparacao as modulo

        calculo = {k: v for k, v in modulo._CALCULO.items() if k != (UMA_AMOSTRA, WILCOXON)}
        monkeypatch.setattr(modulo, "_CALCULO", calculo)
        comparacao = _comparar()
        linha = _linha(comparacao, "renda")
        assert linha.celula_do_teste == "não testado: normal rejeitada"
        assert any(
            "a regra escolheria Wilcoxon, que ainda não está no FlatCap" in aviso
            and "`[renda, 2500, t]`" in aviso
            for aviso in comparacao.avisos
        )
        tabela = comparacao.tabela_de(UMA_AMOSTRA)
        assert "O Wilcoxon ainda não está no FlatCap" in tabela.texto()
        # O resumo da linha é o do teste que a regra escolheu, mesmo sem ele ter rodado.
        resumo = linha.resumo
        celula = next(c for c in tabela.linhas if c[0] == linha.rotulo)[2]
        assert celula == _mediana_quartis(resumo["mediana"], resumo["q1"], resumo["q3"])
        assert tabela.colunas[2] == COLUNA_DAS_DUAS

    def test_a_linha_do_wilcoxon_nao_ensina_o_t(self):
        """Com o teste de postos na linha, não há buraco a tapar com o t."""
        assert not any("escreva o método no item" in aviso for aviso in _comparar().avisos)

    def test_dois_valores_nao_verificam_a_normalidade(self):
        """
        O Shapiro-Wilk precisa de três: com dois, a regra vai para o Wilcoxon, que o R
        calcula — `wilcox.test(c(24, 27), mu = 25)`: V = 2, p = 1, e o intervalo de 50%.
        Com dois valores o menor p possível é 0,5, e o aviso diz isso; o intervalo, que
        não chega a 95%, fica fora da tabela.
        """
        quadro, linhas = _uma("a", [24.0, 27.0, None])
        comparacao = _comparar(quadro, linhas, (("a", 25),))
        linha = comparacao.variaveis[0]
        assert linha.celula_do_teste == WILCOXON
        assert "a normalidade não pôde ser verificada" in linha.escolha.motivo
        assert (linha.resultado.estatistica, linha.resultado.p) == (2.0, 1.0)
        assert linha.resultado.confianca_do_ic == 0.5
        assert comparacao.tabela_de(UMA_AMOSTRA).linhas[0][3] == "—"
        assert any(
            "`a`: Wilcoxon com 2 valores — o menor p que ele pode dar é 0,500, acima de "
            "0,05, e o intervalo de 95% não é alcançável — o mais largo que existe tem "
            "50%. Com tão poucos valores, o teste não rejeita a igualdade com dado "
            "nenhum. A célula do intervalo sai com —." in aviso
            for aviso in comparacao.avisos
        )

    def test_dois_valores_com_o_t_escrito_dao_o_t_do_r(self):
        """`t.test(c(24, 27), mu = 25)`: t = 0,3333, 1 gl, p = 0,7952."""
        quadro, linhas = _uma("a", [24.0, 27.0])
        resultado = _comparar(quadro, linhas, (("a", 25, "t"),)).variaveis[0].resultado
        assert resultado.estatistica == pytest.approx(1 / 3, rel=1e-12)
        assert resultado.gl == (1.0,)
        assert resultado.p == pytest.approx(0.79516723530086653, rel=1e-10)

    def test_t_com_menos_de_20_valores_avisa(self):
        resultado = _comparar()
        assert _linha(resultado, "pas").metodo == T_DE_STUDENT
        assert any("`pas`: t de Student com 12 valores" in aviso for aviso in resultado.avisos)
        assert not any("`imc`: t de Student com" in aviso for aviso in resultado.avisos)

    def test_a_escala_com_a_normal_rejeitada_avisa_que_e_discreta(self):
        avisos = _comparar().avisos
        assert any("`dor`: 6 valores distintos em 60 casos" in aviso for aviso in avisos)
        assert not any("`renda`: 60 valores distintos" in aviso for aviso in avisos)

    def test_o_registro_da_regra(self):
        """O Wilcoxon está na regra e no cálculo desde a 1.14.0."""
        assert REGRA[UMA_AMOSTRA] == (T_DE_STUDENT, WILCOXON)
        rejeitada = regra(UMA_AMOSTRA, Normal(w=0.9, p=0.01))
        assert (rejeitada.metodo, rejeitada.da_regra) == (WILCOXON, WILCOXON)
        sustentada = regra(UMA_AMOSTRA, Normal(w=0.99, p=0.5))
        assert (sustentada.metodo, sustentada.da_regra) == (T_DE_STUDENT, T_DE_STUDENT)

    def test_o_limite_da_regra_e_o_alfa_da_normalidade(self):
        """p = 0,05 não rejeita: é o `p < ALFA` da normalidade, e não `≤`."""
        assert regra(UMA_AMOSTRA, Normal(w=0.97, p=0.05)).metodo == T_DE_STUDENT
        assert regra(UMA_AMOSTRA, Normal(w=0.97, p=0.0499)).metodo == WILCOXON

    def test_a_escolha_de_cada_linha_esta_escrita_na_nota(self):
        texto = _comparar().tabela_de(UMA_AMOSTRA).texto()
        assert (
            "IMC (kg/m²): n = 57; o Shapiro-Wilk não rejeita a normal (p = 1,000) → "
            "t de Student (t = 2,16; 56 gl)." in texto
        )
        assert (
            "Renda: n = 60; o Shapiro-Wilk rejeita a normal (p < 0,001) → Wilcoxon (V = 1080; "
            "p aproximado pela normal, com correção de continuidade, porque há 50 valores "
            "ou mais)." in texto
        )
        assert "Serviço: não testado — um valor só em todas as linhas." in texto


# ── O método escrito na ficha ───────────────────────────────────────────────


class TestMetodoNaFicha:
    def test_o_t_escrito_manda_contra_a_regra_e_a_nota_diz_o_que_ela_faria(self):
        resultado = _comparar(itens=(("renda", 3000, "t"),))
        linha = resultado.variaveis[0]
        assert linha.metodo == T_DE_STUDENT
        assert linha.escolha.contra_a_regra
        assert (
            "t de Student escrito na ficha (t = 1,05; 59 gl), contra a regra — ela "
            "escolheria Wilcoxon: o Shapiro-Wilk rejeita a normal (p < 0,001)."
        ) in linha.justificativa
        assert any("contra a regra" in aviso for aviso in resultado.avisos)
        assert not any("escreva o método no item" in aviso for aviso in resultado.avisos)

    def test_o_t_escrito_igual_ao_da_regra_nao_avisa(self):
        resultado = _comparar(itens=(("imc", 25, "t"),))
        linha = resultado.variaveis[0]
        assert linha.escolha.pela_ficha and not linha.escolha.contra_a_regra
        assert "o mesmo que a regra escolheria" in linha.justificativa
        assert not any("contra a regra" in aviso for aviso in resultado.avisos)

    def test_o_t_escrito_nao_passa_pelas_barreiras_do_r(self):
        """Um valor só não tem t, escrito na ficha ou não — é o `stop()` do R."""
        linha = _comparar(itens=(("servico", 1, "t"),)).variaveis[0]
        assert linha.resultado is None
        assert linha.celula_do_teste == "não testado: um valor só em todas as linhas"

    def test_o_metodo_se_escreve_de_qualquer_jeito(self):
        assert metodo_escrito("t") == T_DE_STUDENT
        assert metodo_escrito(" T ") == T_DE_STUDENT
        assert metodo_escrito("Student") == T_DE_STUDENT
        assert metodo_escrito("wilcoxon") == WILCOXON
        assert metodo_escrito("Wilcox") == WILCOXON
        assert metodo_escrito("tt") == ""


# ── Quando não há teste ─────────────────────────────────────────────────────


class TestSemTeste:
    def test_um_valor_so_em_todas_as_linhas(self):
        resultado = _comparar()
        assert _linha(resultado, "servico").resultado is None
        assert resultado.tabela_de(UMA_AMOSTRA).linhas[4] == (
            "Serviço", "60", "1 (0)", "—", "1", "não testado: um valor só em todas as linhas",
            "—",
        )
        assert any("critério de inclusão" in aviso for aviso in resultado.avisos)

    def test_nenhum_valor_preenchido(self):
        quadro, linhas = _uma("a", [None, None, None])
        linha = _comparar(quadro, linhas, (("a", 25),)).tabela_de(UMA_AMOSTRA).linhas[0]
        assert linha == ("A", "0", "—", "—", "25", "não testado: nenhum valor preenchido", "—")

    def test_um_valor_preenchido(self):
        quadro, linhas = _uma("a", [None, 30.0, None])
        linha = _comparar(quadro, linhas, (("a", 25, "t"),)).tabela_de(UMA_AMOSTRA).linhas[0]
        assert linha[5] == "não testado: 1 valor — o teste precisa de pelo menos 2"

    def test_valores_que_so_variam_no_ultimo_bit(self):
        """O `data are essentially constant` do R: variar no último bit não é variar."""
        base = 1e6
        quadro, linhas = _uma("a", [base, math.nextafter(base, math.inf), base, base])
        linha = _comparar(quadro, linhas, (("a", 25, "t"),)).tabela_de(UMA_AMOSTRA).linhas[0]
        assert linha[5] == "não testado: os valores praticamente não variam"

    def test_o_resumo_sai_mesmo_sem_teste(self):
        """
        O resumo descreve a variável, e não depende de pressuposto: um valor só não tem
        teste, e tem a média — sem teste escolhido, o resumo é o de sempre.
        """
        quadro, linhas = _uma("a", [None, 30.0, None])
        linha = _comparar(quadro, linhas, (("a", 25),)).tabela_de(UMA_AMOSTRA).linhas[0]
        assert linha[:3] == ("A", "1", "30 (0)")
        assert (linha[3], linha[6]) == ("—", "—")


# ── As recusas ──────────────────────────────────────────────────────────────


class TestRecusas:
    def test_sem_itens_recusa_e_ensina_a_forma(self):
        with pytest.raises(SemItensError) as erro:
            _comparar(itens=())
        mensagem = str(erro.value)
        assert "- [imc, 25]" in mensagem
        assert "- [pas, 120, t]" in mensagem
        assert "imc, renda, pas, dor, servico" in mensagem
        assert "o FlatCap não inventa uma" in mensagem

    def test_categorica_recusa(self):
        with pytest.raises(ItemInvalidoError, match="a média de um código não é uma média"):
            _comparar(itens=(("sexo", 1),))

    def test_data_recusa(self):
        linhas = (*DICIONARIO, Linha("coleta", "Coleta", DATA))
        quadro = bancos.para_comparar().assign(coleta="01/02/2026")
        with pytest.raises(ItemInvalidoError, match="`coleta` está marcada `data`"):
            _comparar(quadro, linhas, (("coleta", 1),))

    def test_nome_fora_do_dicionario(self):
        with pytest.raises(ItemInvalidoError, match="`imcc` não está no dicionario.csv"):
            _comparar(itens=(("imcc", 25),))

    def test_ignorar_e_fora_do_banco(self):
        linhas = (
            *DICIONARIO,
            Linha("prontuario", "Prontuário", IGNORAR),
            Linha("peso", "Peso", NUMERICA, no_banco=False),
        )
        with pytest.raises(ItemInvalidoError) as erro:
            _comparar(linhas=linhas, itens=(("prontuario", 1), ("peso", 70)))
        assert "marcada `ignorar`" in str(erro.value)
        assert "no_banco = nao" in str(erro.value)

    def test_o_mesmo_item_duas_vezes_mesmo_com_outro_metodo(self):
        """A mesma comparação duas vezes é ficar com o p que convier."""
        with pytest.raises(ItemInvalidoError, match=r"repete \[imc, 25\]"):
            _comparar(itens=(("imc", 25), ("imc", 25.0, "t")))

    def test_a_mesma_variavel_contra_outra_referencia_e_outra_pergunta(self):
        resultado = _comparar(itens=(("imc", 25), ("imc", 26)))
        assert [v.referencia for v in resultado.variaveis] == [25, 26]

    def test_todos_os_problemas_de_uma_vez(self):
        with pytest.raises(ItemInvalidoError) as erro:
            _comparar(itens=(("imcc", 25), ("sexo", 1), ("imc", 25), ("imc", 25)))
        mensagem = str(erro.value)
        assert "3 item(ns)" in mensagem
        assert "[imcc, 25]" in mensagem and "[sexo, 1]" in mensagem
        assert "repete [imc, 25]" in mensagem

    def test_numerica_que_chegou_como_texto(self):
        """A recusa da descritiva, pela mesma função."""
        quadro = bancos.para_comparar().assign(renda=lambda q: q["renda"].astype(str))
        with pytest.raises(VariavelIncompativelError, match="chegou como texto"):
            _comparar(quadro)


# ── A lista da ficha ────────────────────────────────────────────────────────


def _itens(projeto_vazio, texto: str):
    acrescentar_a_ficha(projeto_vazio, "comparacao:\n" + texto)
    return itens_da_ficha(projeto_vazio)


def _recusa(projeto_vazio, texto: str) -> str:
    with pytest.raises(ItemInvalidoError) as erro:
        _itens(projeto_vazio, texto)
    return str(erro.value)


class TestFicha:
    def test_sem_a_chave_devolve_vazio(self, projeto_vazio):
        assert itens_da_ficha(projeto_vazio) == ()

    def test_as_formas_na_ordem_em_que_foram_escritas(self, projeto_vazio):
        itens = _itens(
            projeto_vazio,
            "  - [imc, 25]\n"
            "  - [pas, 120.5, t]\n"
            '  - [imc, "24,9"]\n'
            "  - [delta, -1.5, Student]\n",
        )
        assert [(i.variavel, i.referencia, i.metodo) for i in itens] == [
            ("imc", 25.0, ""),
            ("pas", 120.5, "t"),
            ("imc", 24.9, ""),
            ("delta", -1.5, "student"),
        ]
        assert {metodo_escrito(i.metodo) for i in itens if i.metodo} == {T_DE_STUDENT}

    def test_a_virgula_decimal_recusa_e_escreve_o_numero_certo(self, projeto_vazio):
        mensagem = _recusa(projeto_vazio, "  - [imc, 24,9]\n")
        assert "a vírgula decimal partiu o número" in mensagem
        assert "`[imc, 24.9]`" in mensagem
        assert '`[imc, "24,9"]`' in mensagem

    def test_o_zero_da_parte_decimal_nao_se_perde(self, projeto_vazio):
        """
        O YAML lê `05` como o inteiro 5: sem cuidado, a recusa ensinaria `24.5` para
        quem escreveu `24,05` — um número errado pronto para copiar.
        """
        mensagem = _recusa(projeto_vazio, "  - [imc, 24,05]\n  - [taxa, 1,005]\n")
        assert "`[imc, 24.05]`" in mensagem
        assert "`[taxa, 1.005]`" in mensagem
        assert "24.5" not in mensagem

    def test_o_sinal_de_menos_zero_se_perde_e_a_recusa_avisa(self, projeto_vazio):
        mensagem = _recusa(projeto_vazio, "  - [delta, -0,5]\n")
        assert "`[delta, 0.5]`" in mensagem
        assert "ou `-0.5`, se ele era negativo" in mensagem

    def test_o_negativo_com_virgula_guarda_o_sinal(self, projeto_vazio):
        mensagem = _recusa(projeto_vazio, "  - [delta, -1,5]\n")
        assert "`[delta, -1.5]`" in mensagem
        assert "se ele era negativo" not in mensagem

    def test_a_virgula_decimal_com_o_metodo(self, projeto_vazio):
        mensagem = _recusa(projeto_vazio, "  - [imc, 24,9, t]\n")
        assert "`[imc, 24.9, t]`" in mensagem

    def test_falta_a_referencia(self, projeto_vazio):
        assert "falta o valor de referência" in _recusa(projeto_vazio, "  - [imc]\n")

    def test_o_wilcoxon_escrito(self, projeto_vazio):
        itens = _itens(projeto_vazio, "  - [imc, 25, Wilcoxon]\n  - [pas, 120, wilcox]\n")
        assert [(i.variavel, i.metodo) for i in itens] == [
            ("imc", "wilcoxon"),
            ("pas", "wilcoxon"),
        ]

    @pytest.mark.parametrize(
        ("escrito", "delineamento", "teste"),
        [
            ("wilcox", UMA_AMOSTRA, WILCOXON),
            ("wilcox", DOIS_GRUPOS, MANN_WHITNEY),
            ("Mann-Whitney U", DOIS_GRUPOS, MANN_WHITNEY),
            ("U de Mann-Whitney", DOIS_GRUPOS, MANN_WHITNEY),
            ("Mann-Whitney-Wilcoxon", DOIS_GRUPOS, MANN_WHITNEY),
            ("Wilcoxon rank sum", DOIS_GRUPOS, MANN_WHITNEY),
            ("Wilcoxon rank sum", UMA_AMOSTRA, ""),
            ("Kruskal-Wallis", K_GRUPOS, KRUSKAL_WALLIS),
            ("Friedmann", REPETIDAS, FRIEDMAN),
        ],
    )
    def test_as_outras_grafias_dos_testes_de_postos(self, escrito, delineamento, teste):
        """
        Os nomes dos livros e do R, como se escrevem — e a soma de postos é dos grupos: na
        uma amostra ela não quer dizer nada.
        """
        assert metodo_escrito(escrito, delineamento) == teste

    @pytest.mark.parametrize("delineamento", [UMA_AMOSTRA, DOIS_GRUPOS])
    def test_o_posto_sinalizado_nao_vira_o_mann_whitney(self, delineamento):
        """
        `wilcoxon` entre dois grupos é o Mann-Whitney, como no R; o posto sinalizado
        escrito por extenso não é sinônimo dele, para não chegar à soma de postos sem
        ninguém pedir. Recusa, e a recusa ensina o `wilcoxon`.
        """
        assert metodo_escrito("Wilcoxon signed rank", delineamento) == ""

    def test_o_posto_sinalizado_por_extenso_recusa_e_ensina(self, projeto_vazio):
        mensagem = _recusa(projeto_vazio, "  - [imc, 25, wilcoxon signed rank]\n")
        assert (
            "`wilcoxon signed rank` não é um método. O terceiro item, quando vem, é o "
            "método: `t`, `student` ou `wilcoxon`."
        ) in mensagem

    def test_o_item_montado_fora_da_ficha_recusa_com_os_metodos(self):
        """
        O item que chega pronto — de quem chama a comparação sem a ficha — passa pela
        mesma porta, e a recusa diz os métodos da uma amostra.
        """
        with pytest.raises(ItemInvalidoError) as erro:
            _comparar(itens=(("imc", 25, "mediana"),))
        assert str(erro.value) == (
            "`mediana` não é um método contra uma referência: `t`, `student` ou `wilcoxon`."
        )

    def test_o_metodo_de_grupos_contra_uma_referencia(self, projeto_vazio):
        mensagem = _recusa(projeto_vazio, "  - [imc, 25, mann-whitney]\n")
        assert "não se aplica à comparação com um valor de referência" in mensagem
        assert "`t`, `student` ou `wilcoxon`" in mensagem

    def test_o_terceiro_nome_que_nao_e_metodo(self, projeto_vazio):
        assert "`mediana` não é um método" in _recusa(projeto_vazio, "  - [imc, 25, mediana]\n")

    def test_a_referencia_depois_dos_dois_pontos_recusa_e_ensina(self, projeto_vazio):
        mensagem = _recusa(projeto_vazio, "  - imc: 25\n  - sexo: [imc, pas]\n")
        assert "1 item(ns) fora do formato" in mensagem
        assert "vai dentro dos colchetes, junto do nome: `[imc, 25]`" in mensagem

    def test_texto_solto_recusa(self, projeto_vazio):
        mensagem = _recusa(projeto_vazio, "  - imc 25\n")
        assert "1º item: `imc 25`" in mensagem
        assert "- [pas, 120, t]" in mensagem

    def test_a_chave_que_nao_e_lista(self, projeto_vazio):
        acrescentar_a_ficha(projeto_vazio, "comparacao: imc\n")
        with pytest.raises(ItemInvalidoError, match="deveria ser uma lista"):
            itens_da_ficha(projeto_vazio)

    def test_separador_de_milhar_recusa(self, projeto_vazio):
        mensagem = _recusa(projeto_vazio, '  - [renda, "2.500,00"]\n')
        assert "sem ambiguidade" in mensagem

    def test_o_numero_na_frente(self, projeto_vazio):
        mensagem = _recusa(projeto_vazio, "  - [25, imc]\n")
        assert "a variável vem primeiro e a referência depois: `[imc, 25]`" in mensagem

    def test_quatro_itens(self, projeto_vazio):
        assert "4 itens" in _recusa(projeto_vazio, "  - [imc, 25, t, x]\n")

    def test_todos_os_itens_errados_de_uma_vez(self, projeto_vazio):
        mensagem = _recusa(projeto_vazio, "  - [imc]\n  - [pas, 120]\n  - [dor, true]\n")
        assert "2 item(ns) fora do formato" in mensagem
        assert "1º item" in mensagem and "3º item" in mensagem

    def test_a_referencia_escrita(self):
        assert referencia_escrita(25) == 25.0
        assert referencia_escrita(24.9) == 24.9
        assert referencia_escrita("24,9") == 24.9
        assert referencia_escrita(" 25 ") == 25.0
        assert referencia_escrita("-1,5") == -1.5
        assert referencia_escrita(True) is None
        assert referencia_escrita("2.500,00") is None
        assert referencia_escrita(float("nan")) is None
        assert referencia_escrita(None) is None


# ── A tabela ────────────────────────────────────────────────────────────────


class TestATabela:
    def test_as_sete_colunas(self):
        """O banco de referência mistura o t e o Wilcoxon: o cabeçalho diz os dois."""
        assert _comparar().tabela_de(UMA_AMOSTRA).colunas == (
            "variável",
            "n",
            "média (DP) ou mediana [Q1 a Q3]",
            "IC 95%",
            "referência",
            "teste",
            "p-valor",
        )

    def test_so_o_t_tem_o_cabecalho_de_sempre(self):
        """Uma tabela só de t sai como saía antes dos testes de postos, letra por letra."""
        colunas = _comparar(itens=(("imc", 25), ("pas", 120))).tabela_de(UMA_AMOSTRA).colunas
        assert colunas[2:4] == (COLUNA_DA_MEDIA, COLUNA_DO_IC_DA_MEDIA)
        assert colunas[2:4] == ("média (DP)", "IC 95% da média")

    def test_so_o_wilcoxon_tem_o_cabecalho_dele(self):
        colunas = _comparar(itens=(("renda", 2500), ("dor", 2))).tabela_de(UMA_AMOSTRA).colunas
        assert colunas[2:4] == (COLUNA_DA_MEDIANA, COLUNA_DO_IC_DA_PSEUDOMEDIANA)
        assert (COLUNA_DAS_DUAS, COLUNA_DO_IC) == ("média (DP) ou mediana [Q1 a Q3]", "IC 95%")

    def test_a_linha_sem_resumo_nao_decide_o_cabecalho(self):
        """O traço de quem não tem valor não é média nem mediana."""
        quadro = bancos.para_comparar().assign(vazia=None)
        linhas = (*DICIONARIO, Linha("vazia", "Vazia", NUMERICA))
        comparacao = _comparar(quadro, linhas, (("renda", 2500), ("vazia", 1)))
        assert comparacao.tabela_de(UMA_AMOSTRA).colunas[2] == COLUNA_DA_MEDIANA

    def test_a_tabela_do_banco_de_referencia(self):
        """
        Linha por linha, com cada número tirado do R e formatado aqui: a média e o
        desvio como a descritiva escreve, o intervalo com duas casas fixas.
        """
        imc = REFERENCIAS_DO_R[0]
        pas = REFERENCIAS_DO_R[1]
        renda = next(r for r in WILCOXON_DO_R if r[:2] == ("renda", 2500))
        dor = next(r for r in WILCOXON_DO_R if r[0] == "dor")

        def media_dp(referencia):
            return f"{_como_a_descritiva(referencia[7])} ({_como_a_descritiva(referencia[8])})"

        def mediana(referencia):
            q1, meio, q3 = referencia[7]
            return _mediana_quartis(meio, q1, q3)

        def faixa(ic):
            return f"{_duas_casas(ic[0])} a {_duas_casas(ic[1])}"

        assert _comparar().tabela_de(UMA_AMOSTRA).linhas == (
            ("IMC (kg/m²)", "57", media_dp(imc), faixa(imc[6]), "25", T_DE_STUDENT,
             valor_p(imc[5])),
            ("Renda", "60", mediana(renda), faixa(renda[5]), "2500", WILCOXON,
             valor_p(renda[4])),
            ("PAS (mmHg)", "12", media_dp(pas), faixa(pas[6]), "120", T_DE_STUDENT,
             valor_p(pas[5])),
            ("Dor", "60", mediana(dor), faixa(dor[5]), "2", WILCOXON, valor_p(dor[4])),
            ("Serviço", "60", "1 (0)", "—", "1", "não testado: um valor só em todas as linhas",
             "—"),
        )
        assert _comparar().tabela_de(UMA_AMOSTRA).linhas[1][2:4] == (
            "2500,35 [1472,81 a 4245]",
            "2294,15 a 3571,24",
        )

    def test_o_resumo_e_letra_por_letra_o_da_descritiva(self):
        """
        A média e o desvio — e a mediana e os quartis — saem pela função e pelo
        formatador da descritiva: a célula do resumo é, letra por letra, o que o
        `resumo_<variável>.csv` imprime, na forma do teste da linha.
        """
        from flatcap.descritiva import descrever

        quadro = bancos.para_comparar()
        descritiva = descrever(banco_em_memoria(quadro), ficha_em_memoria(), DICIONARIO, AGORA)
        comparacao = _comparar(quadro)
        de_postos = {"renda", "dor"}
        for nome in ("imc", "renda", "pas", "dor", "servico"):
            resumo = next(v for v in descritiva.variaveis if v.variavel == nome).tabelas[0]
            celulas = dict(resumo.linhas)
            posicao = [v.variavel for v in comparacao.variaveis].index(nome)
            linha = comparacao.tabela_de(UMA_AMOSTRA).linhas[posicao]
            if nome in de_postos:
                assert linha[2] == f"{celulas['mediana']} [{celulas['q1']} a {celulas['q3']}]"
            else:
                assert linha[2] == f"{celulas['média']} ({celulas['desvio padrão']})"

    def test_o_intervalo_tem_casas_fixas_e_nunca_menos_zero(self):
        from flatcap.comparacao import _fixo, _intervalo

        assert _intervalo((25.8, 27.02)) == "25,80 a 27,02"
        assert _intervalo((-0.004, 0.31)) == "0,00 a 0,31"
        assert _intervalo((-1.234, -0.5)) == "-1,23 a -0,50"
        assert _fixo(-0.005001) == "-0,01"
        assert _intervalo(None) == "—"

    def test_a_referencia_sai_como_foi_escrita(self):
        from flatcap.comparacao import _referencia_em_texto

        assert _referencia_em_texto(25.0) == "25"
        assert _referencia_em_texto(24.9) == "24,9"
        assert _referencia_em_texto(0.125) == "0,125"
        assert _referencia_em_texto(-1.5) == "-1,5"
        assert _referencia_em_texto(24.9, ponto=True) == "24.9"

    def test_n_e_quem_respondeu(self):
        imc = _linha(_comparar(), "imc")
        assert (imc.validos, imc.faltantes) == (57, 3)

    def test_o_p_nunca_sai_zero(self):
        linha = _comparar(itens=(("imc", 20),)).tabela_de(UMA_AMOSTRA).linhas[0]
        assert linha[6] == "< 0,001"

    def test_a_tabela_nao_e_de_uma_variavel(self):
        tabela = _comparar().tabela_de(UMA_AMOSTRA)
        assert (tabela.variavel, tabela.nome) == ("", ARQUIVO_TABELA)
        texto = tabela.texto()
        assert "# variável:" not in texto
        assert "t.test do R" in texto
        assert "wilcox.test do R" in texto
        assert "pseudomediana de Hodges-Lehmann" in texto
        assert "ainda não está no FlatCap" not in texto
        assert "não há correção para comparações múltiplas" in texto


# ── O manifesto ─────────────────────────────────────────────────────────────


class TestManifesto:
    def test_um_item_para_a_analise_inteira(self):
        manifesto = montar_manifesto(_comparar(), DICIONARIO)
        assert manifesto.analise == ANALISE_COMPARACAO
        (item,) = manifesto.itens
        assert (item.variavel, item.rotulo) == ("", "Comparação")
        assert item.colunas == ("imc", "renda", "pas", "dor", "servico")
        assert [a.arquivo for a in item.artefatos] == [ARQUIVO_TABELA]

    def test_os_detalhes_levam_o_pressuposto_e_a_escolha(self):
        detalhes = montar_manifesto(_comparar(), DICIONARIO).itens[0].detalhes
        imc, renda, _, _, servico = detalhes[UMA_AMOSTRA]
        assert imc["shapiro"]["rejeita"] is False
        assert imc["estatistica"] == {"nome": "t", "valor": 2.15895, "gl": [56.0]}
        assert imc["ic_95"] == [25.067061, 26.792588]
        assert (imc["exato"], imc["ic_alcancavel"]) == (None, None)
        assert (renda["teste"], renda["teste_da_regra"]) == (WILCOXON, WILCOXON)
        assert renda["shapiro"]["rejeita"] is True
        assert renda["estatistica"] == {"nome": "V", "valor": 1080.0, "gl": []}
        assert renda["estimativa"] == {"nome": "pseudomediana", "valor": 2859.913369}
        assert renda["ic_95"] == [2294.154975, 3571.235052]
        assert renda["exato"] is False
        assert "50 valores ou mais" in renda["calculo_do_p"]
        assert (servico["shapiro"], servico["motivo"]) == (None, "um valor só em todas as linhas")
        assert (detalhes["testadas"], detalhes["sem_teste"]) == (4, 1)

    def test_o_p_pequeno_nao_vira_zero_no_manifesto(self):
        """Seis algarismos significativos, e não seis casas."""
        detalhes = montar_manifesto(_comparar(itens=(("imc", 20),)), DICIONARIO).itens[0]
        p = detalhes.detalhes[UMA_AMOSTRA][0]["p"]
        assert 0 < p < 1e-6

    def test_o_ambiente_declara_o_scipy_e_nenhuma_figura(self):
        ambiente = montar_manifesto(_comparar(), DICIONARIO).ambiente
        assert ambiente["scipy"] == __import__("scipy").__version__
        assert (ambiente["matplotlib"], ambiente["fonte"]) == (None, None)

    def test_as_regras_dizem_como_o_r_faz(self):
        regras = montar_manifesto(_comparar(), DICIONARIO).regras
        assert "t.test do R" in regras["t_de_student"]
        escolha = regras["escolha_do_teste"][UMA_AMOSTRA]
        assert escolha == (
            "t de Student se o Shapiro-Wilk não rejeita a normal (p ≥ 0.05) sobre os valores "
            "preenchidos; senão Wilcoxon. O método escrito na ficha tem precedência."
        )
        assert "wilcox.test do R com conf.int = TRUE" in regras["wilcoxon"]
        assert "mediana [Q1 a Q3]" in regras["resumo"]
        assert regras["hipotese"] == "bilateral"

    def test_fora_lista_quem_nao_esta_em_item(self):
        manifesto = montar_manifesto(_comparar(), DICIONARIO)
        assert {entrada["variavel"] for entrada in manifesto.fora} == {"sexo"}

    def test_a_ordem_padrao_poe_a_comparacao_depois_da_correlacao(self):
        posicao = ORDEM_PADRAO_DAS_ANALISES.index
        assert posicao(ANALISE_COMPARACAO) == posicao(ANALISE_CORRELACAO) + 1
        assert ORDEM_PADRAO_DAS_ANALISES[-1] == ANALISE_COMPARACAO


# ── Entre dois grupos: o R ──────────────────────────────────────────────────


class TestGruposDoR:
    @pytest.mark.parametrize(
        ("variavel", "t", "gl", "p", "ic", "diferenca", "feminino", "masculino"),
        STUDENT_DO_R,
        ids=[variavel for variavel, *_ in STUDENT_DO_R],
    )
    def test_o_t_test_e_o_shapiro_test_de_cada_grupo(
        self, variavel, t, gl, p, ic, diferenca, feminino, masculino
    ):
        """
        Com `student` escrito, o t de Student sai em todas as colunas — mesmo onde a
        regra não o escolheria —, e dá para conferir cada uma contra o R: o t, os gl,
        o p, o intervalo e a diferença, e de cada grupo o n, a média, o desvio e o
        Shapiro-Wilk.
        """
        comparada = _grupos(((variavel, "sexo", "student"),)).variaveis[0]
        resultado = comparada.resultado
        assert resultado.estatistica == pytest.approx(t, rel=1e-12)
        assert resultado.gl == (gl,)
        assert resultado.p == pytest.approx(p, rel=1e-10)
        assert resultado.ic == pytest.approx(ic, rel=1e-12)
        assert resultado.estimativa == pytest.approx(diferenca, rel=1e-12)
        assert [g.rotulo for g in comparada.grupos] == ["Feminino", "Masculino"]
        for grupo, (n, media, dp, w, p_shapiro) in zip(
            comparada.grupos, (feminino, masculino), strict=True
        ):
            assert grupo.n == n
            assert grupo.resumo["media"] == pytest.approx(media, rel=1e-12)
            assert grupo.resumo["desvio"] == pytest.approx(dp, rel=1e-12)
            assert grupo.normal.w == pytest.approx(w, rel=1e-6)
            assert grupo.normal.p == pytest.approx(p_shapiro, rel=1e-4)

    @pytest.mark.parametrize(
        ("variavel", "t", "gl", "p", "ic"), WELCH_DO_R, ids=[v for v, *_ in WELCH_DO_R]
    )
    def test_o_t_de_welch_do_r(self, variavel, t, gl, p, ic):
        """
        `t` escrito entre grupos é o de Welch, como o `t.test` sem argumento: os gl
        fracionários, o p e o intervalo do R — e a diferença, que é a mesma do de
        Student, porque as médias são as mesmas.
        """
        comparada = _grupos(((variavel, "sexo", "t"),)).variaveis[0]
        resultado = comparada.resultado
        assert resultado.metodo == T_DE_WELCH
        assert resultado.estatistica == pytest.approx(t, rel=1e-12)
        assert resultado.gl == pytest.approx((gl,), rel=1e-12)
        assert resultado.p == pytest.approx(p, rel=1e-10)
        assert resultado.ic == pytest.approx(ic, rel=1e-12)
        de_student = next(r for r in STUDENT_DO_R if r[0] == variavel)
        assert resultado.estimativa == pytest.approx(de_student[5], rel=1e-12)

    def test_o_um_valor_num_grupo_do_r(self):
        """
        `t.test(30, y, var.equal = TRUE)`: o R aceita um grupo de um valor no de
        Student — t = 0,1163, 11 gl, p = 0,9095. A normalidade desse grupo não se
        verifica, e o teste roda porque está escrito no item.
        """
        y = [26.5, 29.9, 31.2, 24.8, 33.0, 28.1, 30.4, 27.6, 35.2, 26.3, 29.8, 32.7]
        quadro, linhas = _dois([30.0], y)
        comparada = _grupos((("y", "g", "student"),), quadro, linhas).variaveis[0]
        assert comparada.resultado.estatistica == pytest.approx(0.1162591710745048, rel=1e-12)
        assert comparada.resultado.gl == (11.0,)
        assert comparada.resultado.p == pytest.approx(0.90954249918663643, rel=1e-10)
        assert comparada.escolha.da_regra == MANN_WHITNEY


# ── Entre dois grupos: a regra ──────────────────────────────────────────────


class TestRegraEntreGrupos:
    def test_a_normal_nos_dois_grupos_vai_para_o_welch(self):
        comparada = _grupos((("imc", "sexo"),)).variaveis[0]
        assert comparada.metodo == T_DE_WELCH
        assert (comparada.escolha.da_regra, comparada.escolha.pela_ficha) == (T_DE_WELCH, False)
        assert comparada.escolha.motivo == (
            "o Shapiro-Wilk não rejeita a normal em nenhum dos dois grupos "
            "(Feminino: p = 1,000; Masculino: p = 1,000)"
        )
        assert comparada.celula_do_teste == T_DE_WELCH
        assert comparada.resultado.p == pytest.approx(WELCH_DO_R[0][3], rel=1e-10)

    def test_a_linha_sem_teste_ensina_a_escrever_t(self, monkeypatch):
        """
        Com o Mann-Whitney fora do registro — o caminho de um teste da regra sem
        aritmética —, o aviso ensina o t, que entre grupos é o de Welch.
        """
        import flatcap.comparacao as modulo

        calculo = {
            k: v for k, v in modulo._CALCULO.items() if k != (DOIS_GRUPOS, MANN_WHITNEY)
        }
        monkeypatch.setattr(modulo, "_CALCULO", calculo)
        avisos = _grupos((("renda", "sexo"),)).avisos
        assert any(
            "a regra escolheria Mann-Whitney, que ainda não está no FlatCap" in aviso
            and "Se o t de Welch vale aqui" in aviso
            and "`[renda, sexo, t]`" in aviso
            for aviso in avisos
        )

    def test_a_normal_rejeitada_em_algum_grupo_escolhe_o_mann_whitney(self):
        comparada = _grupos((("renda", "sexo"),)).variaveis[0]
        assert (comparada.escolha.metodo, comparada.escolha.da_regra) == (
            MANN_WHITNEY,
            MANN_WHITNEY,
        )
        assert comparada.escolha.motivo == (
            "o Shapiro-Wilk rejeita a normal em Feminino (p < 0,001) e Masculino (p < 0,001)"
        )
        assert comparada.celula_do_teste == MANN_WHITNEY
        assert comparada.resultado.p == pytest.approx(0.1697319562818404, rel=1e-12)

    def test_basta_um_grupo_rejeitar(self):
        rejeita = regra(
            DOIS_GRUPOS,
            (
                Grupo("A", 30, normal=Normal(w=0.98, p=0.61)),
                Grupo("B", 30, normal=Normal(w=0.91, p=0.012)),
            ),
        )
        assert rejeita.da_regra == MANN_WHITNEY
        assert rejeita.motivo == "o Shapiro-Wilk rejeita a normal em B (p = 0,012)"

    def test_o_limite_da_regra_e_o_alfa_da_normalidade_em_cada_grupo(self):
        def com(p):
            return (
                Grupo("A", 30, normal=Normal(w=0.97, p=0.5)),
                Grupo("B", 30, normal=Normal(w=0.97, p=p)),
            )

        assert regra(DOIS_GRUPOS, com(0.05)).da_regra == T_DE_WELCH
        assert regra(DOIS_GRUPOS, com(0.0499)).da_regra == MANN_WHITNEY

    def test_um_grupo_com_dois_valores_nao_verifica_a_normalidade(self):
        """
        A regra vai para o Mann-Whitney, que o R calcula com dois valores num grupo —
        `wilcox.test(c(24, 27), c(25, 26.5, 28, 30.1, 27.2))`: W = 2, p = 0,381 —, e o
        aviso diz que, com dois e cinco valores, o menor p possível é 0,095.
        """
        quadro, linhas = _dois([24.0, 27.0], [25.0, 26.5, 28.0, 30.1, 27.2])
        comparada = _grupos((("y", "g"),), quadro, linhas).variaveis[0]
        assert comparada.escolha.da_regra == MANN_WHITNEY
        assert "a normalidade não pôde ser verificada em A (2 valor(es)" in (
            comparada.escolha.motivo
        )
        assert comparada.celula_do_teste == MANN_WHITNEY
        assert comparada.resultado.estatistica == 2
        assert comparada.resultado.p == pytest.approx(0.38095238095238093, rel=1e-12)
        assert any(
            "Mann-Whitney com 2 valores em A e 5 valores em B — o menor p que ele pode dar é "
            "0,095, acima de 0,05" in aviso
            for aviso in comparada.avisos
        )

    def test_um_grupo_que_nao_varia_nao_verifica_a_normalidade(self):
        """A frase é do grupo, e não a da coluna que o `normalidade.shapiro` escreveria."""
        quadro, linhas = _dois([5.0, 5.0, 5.0, 5.0], [4.0, 6.0, 7.0, 5.5])
        comparada = _grupos((("y", "g"),), quadro, linhas).variaveis[0]
        assert "em A (um valor só no grupo)" in comparada.escolha.motivo
        assert not any("a coluna tem um valor só" in aviso for aviso in comparada.avisos)

    def test_o_student_escrito_contra_a_regra_diz_o_que_ela_faria(self):
        comparacao = _grupos((("renda", "sexo", "student"),))
        comparada = comparacao.variaveis[0]
        assert comparada.metodo == "t de Student"
        assert comparada.escolha.contra_a_regra
        assert any(
            "`renda` por `sexo`: t de Student escrito na ficha, contra a regra" in aviso
            for aviso in comparacao.avisos
        )
        assert comparada.justificativa == (
            "Renda por Sexo: n = 58 (30 em Feminino e 28 em Masculino); t de Student escrito "
            "na ficha (t = -1,36; 56 gl), contra a regra — ela escolheria Mann-Whitney: o "
            "Shapiro-Wilk rejeita a normal em Feminino (p < 0,001) e Masculino (p < 0,001)."
        )

    def test_o_student_no_lugar_do_welch_tambem_e_contra_a_regra(self):
        """
        A regra escolheria o de Welch; o de Student escrito é uma escolha sua, e a
        nota diz qual seria a da regra.
        """
        comparada = _grupos((("imc", "sexo", "student"),)).variaveis[0]
        assert comparada.escolha.contra_a_regra
        assert "contra a regra — ela escolheria t de Welch: o Shapiro-Wilk" in (
            comparada.justificativa
        )

    def test_o_t_escrito_igual_ao_da_regra(self):
        comparada = _grupos((("imc", "sexo", "t"),)).variaveis[0]
        assert comparada.escolha.pela_ficha and not comparada.escolha.contra_a_regra
        assert "t de Welch escrito na ficha (t = -2,45; 49,56 gl), o mesmo que a regra" in (
            comparada.justificativa
        )

    def test_o_metodo_quer_dizer_um_teste_em_cada_delineamento(self):
        assert metodo_escrito("student", DOIS_GRUPOS) == "t de Student"
        assert metodo_escrito("t", UMA_AMOSTRA) == "t de Student"
        assert metodo_escrito("t", DOIS_GRUPOS) == T_DE_WELCH
        assert metodo_escrito("Welch", DOIS_GRUPOS) == T_DE_WELCH
        assert metodo_escrito("welsh", DOIS_GRUPOS) == T_DE_WELCH
        assert metodo_escrito("t de Welch", DOIS_GRUPOS) == T_DE_WELCH
        assert metodo_escrito("welch", UMA_AMOSTRA) == ""
        assert metodo_escrito("T de Student", DOIS_GRUPOS) == "t de Student"

    def test_o_registro_da_regra_entre_dois_grupos(self):
        assert REGRA[DOIS_GRUPOS] == (T_DE_WELCH, MANN_WHITNEY)


# ── Entre dois grupos: os avisos ────────────────────────────────────────────


class TestAvisosEntreGrupos:
    def test_o_student_com_desvios_muito_diferentes_avisa(self):
        """
        O de Student supõe a mesma variância; na `pas`, o desvio de um grupo é três
        vezes o do outro, e o aviso escreve os dois e a razão.
        """
        avisos = _grupos((("pas", "sexo", "student"),)).avisos
        assert any(
            "o desvio padrão de Masculino (15,43) é 3,1 vezes o de Feminino (5,02)" in aviso
            and "O t de Welch não supõe" in aviso
            for aviso in avisos
        )

    def test_o_welch_pela_regra_com_grupos_pequenos_avisa(self):
        """
        Oito e nove valores: o Shapiro-Wilk não rejeita em nenhum, e a regra escolhe o de
        Welch por falta de evidência contra a normal — não por evidência a favor.
        """
        quadro, linhas = _dois(
            [24.1, 26.8, 25.5, 23.9, 27.2, 25.0, 26.1, 24.7],
            [28.3, 30.1, 26.9, 31.4, 29.2, 27.8, 30.6, 28.9, 29.5],
        )
        comparacao = _grupos((("y", "g"),), quadro, linhas)
        assert comparacao.variaveis[0].metodo == T_DE_WELCH
        assert comparacao.variaveis[0].resultado.p == pytest.approx(
            2.7059244891768163e-05, rel=1e-9
        )
        assert any(
            "`y` por `g`: t de Welch com 8 valores em A e 9 valores em B" in aviso
            for aviso in comparacao.avisos
        )

    def test_o_welch_nao_fala_de_variancias(self):
        """O aviso das variâncias é do de Student: o de Welch não as supõe iguais."""
        avisos = _grupos((("pas", "sexo", "welch"),)).avisos
        assert not any("vezes o de" in aviso for aviso in avisos)

    def test_o_student_com_desvios_parecidos_nao_avisa(self):
        avisos = _grupos((("imc", "sexo", "student"),)).avisos
        assert not any("vezes o de" in aviso for aviso in avisos)

    def test_o_student_com_um_grupo_que_nao_varia_avisa(self):
        quadro, linhas = _dois([5.0, 5.0, 5.0], [4.0, 6.0, 7.0])
        avisos = _grupos((("y", "g", "student"),), quadro, linhas).avisos
        assert any("e A não varia" in aviso for aviso in avisos)

    def test_a_escala_com_a_normal_rejeitada_avisa_que_e_discreta(self):
        escala = [0] * 14 + [1] * 4 + [2] * 2
        quadro, linhas = _dois(escala, list(reversed(escala)))
        avisos = _grupos((("y", "g"),), quadro, linhas).avisos
        assert any("`y` por `g`: 3 valores distintos em 40 casos" in a for a in avisos)

    def test_cada_linha_tem_a_frase_da_escolha_na_nota(self):
        texto = _grupos((("imc", "sexo"), ("renda", "sexo"))).tabela_de(DOIS_GRUPOS).texto()
        assert (
            "IMC (kg/m²) por Sexo: n = 57 (29 em Feminino e 28 em Masculino); o Shapiro-Wilk "
            "não rejeita a normal em nenhum dos dois grupos (Feminino: p = 1,000; Masculino: "
            "p = 1,000) → t de Welch (t = -2,45; 49,56 gl)."
        ) in texto
        assert (
            "Renda por Sexo: n = 58 (30 em Feminino e 28 em Masculino); o Shapiro-Wilk "
            "rejeita a normal em Feminino (p < 0,001) e Masculino (p < 0,001) → Mann-Whitney "
            "(W = 331; p exato)."
        ) in texto


# ── Entre dois grupos: o que o banco decide ─────────────────────────────────


class TestGruposNoBanco:
    def test_os_faltantes_sao_por_comparacao(self):
        """Uma célula vazia no IMC e duas no sexo: 57 casos com as duas respostas."""
        comparada = _grupos((("imc", "sexo", "student"),)).variaveis[0]
        assert (comparada.validos, comparada.faltantes) == (57, 3)
        assert [g.n for g in comparada.grupos] == [29, 28]

    def test_a_ordem_dos_grupos_e_a_do_dicionario_e_decide_o_sinal(self):
        invertido = Linha(
            "sexo",
            "Sexo",
            CATEGORICA,
            ("2", "1"),
            rotulos_das_categorias=(("1", "Feminino"), ("2", "Masculino")),
        )
        linhas = (IMC, RENDA, PAS, invertido, ESCOLARIDADE, UNICO)
        comparada = _grupos((("imc", "sexo", "student"),), linhas=linhas).variaveis[0]
        assert [g.rotulo for g in comparada.grupos] == ["Masculino", "Feminino"]
        assert comparada.resultado.estimativa == pytest.approx(2.3211822660098527, rel=1e-12)
        assert comparada.resultado.p == pytest.approx(0.016984290698757613, rel=1e-10)

    def test_dois_codigos_com_o_mesmo_rotulo_sao_um_grupo(self):
        agrupada = Linha(
            "escolaridade",
            "Escolaridade",
            CATEGORICA,
            ("Fundamental", "Médio", "Superior"),
            rotulos_das_categorias=(("Fundamental", "Básico"), ("Médio", "Básico")),
        )
        linhas = (IMC, RENDA, PAS, SEXO, agrupada, UNICO)
        comparada = _grupos((("pas", "escolaridade", "student"),), linhas=linhas).variaveis[0]
        assert [(g.rotulo, g.n) for g in comparada.grupos] == [("Básico", 40), ("Superior", 20)]
        assert comparada.testada

    def test_o_numero_de_grupos_e_o_do_banco_e_nao_o_do_dicionario(self):
        """Uma categórica sem `categorias_ordem` preenchida: o banco é que diz que são três."""
        sem_ordem = Linha("escolaridade", "Escolaridade", CATEGORICA)
        linhas = (IMC, RENDA, PAS, NOTA, SEXO, sem_ordem, UNICO)
        comparada = _grupos((("nota", "escolaridade", "anova"),), linhas=linhas).variaveis[0]
        assert comparada.delineamento == K_GRUPOS
        assert [g.rotulo for g in comparada.grupos] == ["Fundamental", "Médio", "Superior"]

    def test_tres_grupos_vao_para_a_tabela_dos_k_grupos(self):
        comparacao = _grupos((("imc", "escolaridade"), ("imc", "sexo")))
        assert [v.delineamento for v in comparacao.variaveis] == [K_GRUPOS, DOIS_GRUPOS]
        assert [t.nome for t in comparacao.tabelas] == [ARQUIVO_DOIS_GRUPOS, ARQUIVO_K_GRUPOS]

    def test_os_problemas_do_banco_saem_todos_de_uma_vez(self):
        """O método de dois grupos numa variável de três: só o banco sabe quantos são."""
        with pytest.raises(ItemInvalidoError) as erro:
            _grupos(
                (("imc", "escolaridade", "student"), ("imc", "sexo"), ("pas", "escolaridade", "t"))
            )
        mensagem = str(erro.value)
        assert "2 item(ns) que este banco não deixa comparar" in mensagem
        assert "[imc, escolaridade, student] — `student` não se aplica a 3 grupos" in mensagem
        assert "o t de Student compara dois grupos; escreva `anova`" in mensagem


# ── Entre dois grupos: quando não há teste ──────────────────────────────────


class TestSemTesteEntreGrupos:
    def test_um_grupo_so(self):
        comparada = _grupos((("imc", "unico", "student"),)).variaveis[0]
        assert comparada.celula_do_teste == "não testado: um grupo só"
        assert any("são todos Sim" in aviso for aviso in comparada.avisos)

    def test_nenhum_caso_com_as_duas_respostas(self):
        quadro = bancos.para_comparar_grupos().assign(sexo=None)
        comparada = _grupos((("imc", "sexo"),), quadro).variaveis[0]
        assert comparada.celula_do_teste == "não testado: nenhum caso com as duas respostas"
        assert linhas_da_tabela(comparada) == (
            ("IMC (kg/m²)", "Sexo", "0", "", "—", comparada.celula_do_teste, "—"),
        )

    def test_um_valor_so_em_todas_as_linhas(self):
        quadro, linhas = _dois([5.0, 5.0], [5.0, 5.0, 5.0])
        comparada = _grupos((("y", "g", "student"),), quadro, linhas).variaveis[0]
        assert comparada.celula_do_teste == "não testado: um valor só em todas as linhas"

    def test_um_valor_em_cada_grupo_nao_da_o_student(self):
        """O `not enough observations` do R, com o método escrito e tudo."""
        quadro, linhas = _dois([24.0], [27.0])
        comparada = _grupos((("y", "g", "student"),), quadro, linhas).variaveis[0]
        assert comparada.celula_do_teste == (
            "não testado: um valor em cada grupo — o t de Student precisa de pelo menos 3 "
            "no total"
        )
        assert "t de Student escrito na ficha, que não pôde ser calculado" in (
            comparada.justificativa
        )

    def test_dois_grupos_que_nao_variam_por_dentro(self):
        """As médias diferem, e o R recusa assim mesmo: o t seria uma divisão por zero."""
        quadro, linhas = _dois([5.0, 5.0, 5.0], [6.0, 6.0, 6.0])
        for metodo in ("student", "welch"):
            comparada = _grupos((("y", "g", metodo),), quadro, linhas).variaveis[0]
            assert comparada.celula_do_teste == (
                "não testado: os valores não variam dentro dos grupos"
            )

    def test_um_valor_num_grupo_nao_da_o_welch(self):
        """O `not enough 'x' observations` do R: o de Welch pede dois em cada grupo."""
        quadro, linhas = _dois([30.0], [26.5, 29.9, 31.2, 24.8, 33.0])
        comparada = _grupos((("y", "g", "welch"),), quadro, linhas).variaveis[0]
        assert comparada.celula_do_teste == (
            "não testado: A tem 1 valor — o t de Welch precisa de pelo menos 2 em cada grupo"
        )
        assert any("A linha saiu sem teste" in aviso for aviso in comparada.avisos)

    def test_o_welch_com_um_grupo_que_nao_varia(self):
        """
        `t.test(c(5, 5, 5), c(4, 6, 7))`: o R calcula, com os gl do outro grupo — t =
        −0,756, 2 gl, p = 0,5286. A variância zero é de verdade, e o `scipy` avisa à
        toa; o aviso não chega ao terminal.
        """
        import warnings

        quadro, linhas = _dois([5.0, 5.0, 5.0], [4.0, 6.0, 7.0])
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            resultado = _grupos((("y", "g", "welch"),), quadro, linhas).variaveis[0].resultado
        assert resultado.gl == pytest.approx((2.0,), rel=1e-12)
        assert resultado.p == pytest.approx(0.5285954792089681, rel=1e-10)


# ── Entre dois grupos: a tabela ─────────────────────────────────────────────


class TestTabelaDoisGrupos:
    def test_as_sete_colunas(self):
        tabela = _grupos((("imc", "sexo"),)).tabela_de(DOIS_GRUPOS)
        assert tabela.colunas == (
            "variável",
            "grupo",
            "n",
            "média (DP)",
            "diferença (IC 95%)",
            "teste",
            "p-valor",
        )
        assert (tabela.nome, tabela.especie, tabela.variavel) == (
            ARQUIVO_DOIS_GRUPOS,
            DOIS_GRUPOS,
            "",
        )

    def test_o_bloco_de_uma_comparacao(self):
        """
        A linha da comparação e uma por grupo, com cada número tirado do R: a
        diferença e o intervalo com duas casas fixas, a média e o desvio como a
        descritiva escreve.
        """
        imc = STUDENT_DO_R[0]
        _, _, _, p, ic, diferenca, feminino, masculino = imc

        def media_dp(grupo):
            return f"{_como_a_descritiva(grupo[1])} ({_como_a_descritiva(grupo[2])})"

        assert _grupos((("imc", "sexo", "student"),)).tabela_de(DOIS_GRUPOS).linhas == (
            ("IMC (kg/m²)", "Sexo", "57", "",
             f"{_duas_casas(diferenca)} ({_duas_casas(ic[0])} a {_duas_casas(ic[1])})",
             "t de Student", valor_p(p)),
            ("", "Feminino", "29", media_dp(feminino), "", "", ""),
            ("", "Masculino", "28", media_dp(masculino), "", "", ""),
        )

    def test_sem_teste_a_diferenca_e_o_p_saem_com_o_traco(self):
        """Um grupo só: sem teste nenhum escolhido, e o resumo de sempre, a média."""
        cabeca, *grupos = linhas_da_tabela(_grupos((("imc", "unico"),)).variaveis[0])
        assert (cabeca[4], cabeca[5], cabeca[6]) == ("—", "não testado: um grupo só", "—")
        assert [linha[3] for linha in grupos] == ["26,27 (3,68)"]

    def test_o_bloco_do_mann_whitney(self):
        """
        A diferença de locação e o intervalo do R, com duas casas fixas, e a mediana e os
        quartis de cada grupo como a descritiva os escreve — e o cabeçalho que diz isso.
        """
        _, w, p, ic, diferenca, _, feminino, masculino = MANN_WHITNEY_DO_R[1]
        tabela = _grupos((("renda", "sexo"),)).tabela_de(DOIS_GRUPOS)
        assert tabela.colunas[3] == COLUNA_DA_MEDIANA
        assert tabela.linhas == (
            ("Renda", "Sexo", "58", "",
             f"{_duas_casas(diferenca)} ({_duas_casas(ic[0])} a {_duas_casas(ic[1])})",
             MANN_WHITNEY, valor_p(p)),
            ("", "Feminino", "30", _mediana_quartis(*feminino[1:]), "", "", ""),
            ("", "Masculino", "28", _mediana_quartis(*masculino[1:]), "", "", ""),
        )
        assert tabela.linhas[0][4] == "-921,57 (-2414,48 a 406,97)"
        assert tabela.linhas[1][3] == "2982,62 [1774,62 a 5013,54]"

    def test_a_tabela_e_as_linhas_do_terminal_sao_as_mesmas(self):
        comparacao = _grupos((("imc", "sexo"), ("pas", "sexo", "student")))
        tabela = comparacao.tabela_de(DOIS_GRUPOS)
        assert tabela.linhas == tuple(
            linha for comparada in comparacao.variaveis for linha in linhas_da_tabela(comparada)
        )

    def test_as_notas_dizem_como_o_r_faz_e_o_que_falta(self):
        texto = _grupos((("imc", "sexo"),)).tabela_de(DOIS_GRUPOS).texto()
        assert "var.equal = TRUE" in texto
        assert "graus de liberdade de Welch-Satterthwaite" in texto
        assert "a média do primeiro grupo menos a do segundo" in texto
        assert "wilcox.test do R para duas amostras" in texto
        assert "que não é a diferença das medianas" in texto
        assert "ainda não está no FlatCap" not in texto
        assert "os faltantes são por comparação" in texto

    def test_uma_tabela_por_delineamento_na_ordem(self):
        comparacao = _grupos((("imc", "sexo"), ("imc", 25)))
        assert [t.nome for t in comparacao.tabelas] == [ARQUIVO_TABELA, ARQUIVO_DOIS_GRUPOS]
        assert [v.delineamento for v in comparacao.variaveis] == [DOIS_GRUPOS, UMA_AMOSTRA]

    def test_so_grupos_nao_tem_a_tabela_da_uma_amostra(self):
        comparacao = _grupos((("imc", "sexo"),))
        assert comparacao.tabela_de(UMA_AMOSTRA) is None
        assert [t.nome for t in comparacao.tabelas] == [ARQUIVO_DOIS_GRUPOS]


# ── Entre dois grupos: as recusas do dicionário ─────────────────────────────


class TestRecusasEntreGrupos:
    def _recusa(self, *itens, linhas=DICIONARIO_DOS_GRUPOS) -> str:
        with pytest.raises(ItemInvalidoError) as erro:
            _grupos(itens, linhas=linhas)
        return str(erro.value)

    def test_os_dois_trocados(self):
        mensagem = self._recusa(("sexo", "imc"))
        assert "os dois estão trocados" in mensagem
        assert "`[imc, sexo]`" in mensagem

    def test_duas_numericas_sao_uma_correlacao(self):
        mensagem = self._recusa(("imc", "pas"))
        assert "a variável de grupo é categórica" in mensagem
        assert "`correlacao:`" in mensagem

    def test_duas_categoricas_sao_uma_associacao(self):
        mensagem = self._recusa(("sexo", "escolaridade"))
        assert "`associacao:`" in mensagem

    def test_a_mesma_variavel_duas_vezes(self):
        assert "duas vezes" in self._recusa(("sexo", "sexo"))

    def test_o_mesmo_item_com_e_sem_metodo(self):
        mensagem = self._recusa(("imc", "sexo"), ("imc", "sexo", "student"))
        assert "repete [imc, sexo]" in mensagem

    def test_a_variavel_de_grupo_fora_do_dicionario(self):
        assert "`sexoo` não está no dicionario.csv" in self._recusa(("imc", "sexoo"))

    def test_a_data_nao_forma_grupos(self):
        linhas = (*DICIONARIO_DOS_GRUPOS, Linha("coleta", "Coleta", DATA))
        mensagem = self._recusa(("imc", "coleta"), linhas=linhas)
        assert "`coleta` está marcada `data`" in mensagem

    def test_contra_uma_referencia_e_entre_grupos_sao_duas_perguntas(self):
        comparacao = _grupos((("imc", 25), ("imc", "sexo")))
        assert len(comparacao.variaveis) == 2


# ── Entre dois grupos: a ficha ──────────────────────────────────────────────


class TestFichaEntreGrupos:
    def test_as_formas_entre_grupos(self, projeto_vazio):
        itens = _itens(
            projeto_vazio,
            "  - [imc, sexo]\n"
            "  - [pas, sexo, Student]\n"
            "  - sexo: [renda, idade]\n"
            "  - [imc, pas_0]\n",
        )
        assert itens == (
            Pedido("imc", grupos="sexo"),
            Pedido("pas", metodo="student", grupos="sexo"),
            Pedido("renda", grupos="sexo"),
            Pedido("idade", grupos="sexo"),
            Pedido("imc", grupos="pas_0"),
        )

    def test_t_e_welch_entre_grupos(self, projeto_vazio):
        itens = _itens(projeto_vazio, "  - [imc, sexo, t]\n  - [pas, sexo, welsh]\n")
        assert [(i.variavel, i.metodo) for i in itens] == [("imc", "t"), ("pas", "welch")]

    def test_o_mann_whitney_escrito(self, projeto_vazio):
        itens = _itens(
            projeto_vazio, "  - [imc, sexo, mann-whitney]\n  - [pas, sexo, U de Mann-Whitney]\n"
        )
        assert [(i.variavel, i.metodo) for i in itens] == [
            ("imc", "mannwhitney"),
            ("pas", "mannwhitney"),
        ]

    def test_o_metodo_que_nao_existe_lista_os_que_existem(self, projeto_vazio):
        mensagem = _recusa(projeto_vazio, "  - [imc, sexo, mediana]\n")
        assert (
            "`t`, `student`, `welch`, `anova`, `wilcoxon`, `mannwhitney` ou `kruskal`"
            in mensagem
        )

    def test_o_kruskal_wallis_escrito(self, projeto_vazio):
        itens = _itens(projeto_vazio, "  - [imc, escolaridade, Kruskal-Wallis]\n")
        assert itens == (Pedido("imc", metodo="kruskal", grupos="escolaridade"),)

    def test_o_friedman_nao_e_de_grupos(self, projeto_vazio):
        mensagem = _recusa(projeto_vazio, "  - [imc, sexo, friedman]\n")
        assert "`friedman` não se aplica à comparação entre grupos" in mensagem

    def test_a_anova_entre_grupos(self, projeto_vazio):
        itens = _itens(projeto_vazio, "  - [imc, escolaridade, ANOVA]\n")
        assert itens == (Pedido("imc", metodo="anova", grupos="escolaridade"),)

    def test_o_wilcoxon_entre_grupos_e_o_mann_whitney(self, projeto_vazio):
        """O `wilcox.test` de duas amostras do R é o Mann-Whitney — e a ficha lê assim."""
        itens = _itens(projeto_vazio, "  - [imc, sexo, wilcoxon]\n")
        assert itens == (Pedido("imc", metodo="wilcoxon", grupos="sexo"),)
        assert metodo_escrito("wilcoxon", DOIS_GRUPOS) == MANN_WHITNEY
        assert metodo_escrito("wilcoxon", K_GRUPOS) == ""

    def test_uma_terceira_variavel_ensina_a_forma_uma_contra_varias(self, projeto_vazio):
        mensagem = _recusa(projeto_vazio, "  - [imc, sexo, idade]\n")
        assert "`idade` não é um método" in mensagem
        assert "`- sexo: [imc, idade]`" in mensagem

    def test_o_metodo_na_forma_uma_contra_varias(self, projeto_vazio):
        mensagem = _recusa(projeto_vazio, "  - sexo: [imc, student]\n")
        assert "`student` é um método" in mensagem
        assert "`- [imc, sexo, student]`" in mensagem

    def test_quatro_itens_entre_grupos(self, projeto_vazio):
        mensagem = _recusa(projeto_vazio, "  - [imc, sexo, student, pas]\n")
        assert "4 itens" in mensagem
        assert "`- sexo: [imc, pas]`" in mensagem

    def test_a_lista_vazia_depois_dos_dois_pontos(self, projeto_vazio):
        mensagem = _recusa(projeto_vazio, "  - sexo: []\n")
        assert "com pelo menos um nome" in mensagem


# ── Entre três grupos ou mais ───────────────────────────────────────────────


class TestKGruposDoR:
    @pytest.mark.parametrize(
        ("variavel", "f", "gl", "p", "grupos"), ANOVA_DO_R, ids=[v for v, *_ in ANOVA_DO_R]
    )
    def test_o_oneway_test_e_o_shapiro_test_de_cada_grupo(self, variavel, f, gl, p, grupos):
        comparada = _grupos(((variavel, "escolaridade", "anova"),)).variaveis[0]
        resultado = comparada.resultado
        assert resultado.metodo == ANOVA
        assert resultado.estatistica == pytest.approx(f, rel=1e-12)
        assert resultado.gl == gl
        assert resultado.p == pytest.approx(p, rel=1e-10)
        assert [g.rotulo for g in comparada.grupos] == ["Fundamental", "Médio", "Superior"]
        for grupo, (n, media, dp, w, p_shapiro) in zip(comparada.grupos, grupos, strict=True):
            assert grupo.n == n
            assert grupo.resumo["media"] == pytest.approx(media, rel=1e-12)
            assert grupo.resumo["desvio"] == pytest.approx(dp, rel=1e-12)
            assert grupo.normal.w == pytest.approx(w, rel=1e-6)
            assert grupo.normal.p == pytest.approx(p_shapiro, rel=1e-4)

    @pytest.mark.parametrize(
        ("variavel", "f", "gl", "p"),
        ANOVA_DE_WELCH_DO_R,
        ids=[v for v, *_ in ANOVA_DE_WELCH_DO_R],
    )
    def test_a_anova_de_welch_do_r(self, variavel, f, gl, p):
        """Sem método escrito: a normal se sustenta nos três grupos, e a regra a escolhe."""
        comparada = _grupos(((variavel, "escolaridade"),)).variaveis[0]
        resultado = comparada.resultado
        assert (resultado.metodo, comparada.escolha.pela_ficha) == (ANOVA_DE_WELCH, False)
        assert resultado.estatistica == pytest.approx(f, rel=1e-12)
        assert resultado.gl == pytest.approx(gl, rel=1e-12)
        assert resultado.p == pytest.approx(p, rel=1e-10)

    def test_o_grupo_constante_nao_barra_a_anova(self):
        """`oneway.test` com um grupo de valores iguais: F = 10,5, 2 e 6 gl, p = 0,01097."""
        quadro, linhas = _tres([5.0, 5.0, 5.0], [4.0, 6.0, 7.0], [8.0, 9.0, 11.0])
        resultado = _grupos((("y", "g", "anova"),), quadro, linhas).variaveis[0].resultado
        assert resultado.estatistica == pytest.approx(10.5, rel=1e-12)
        assert resultado.p == pytest.approx(0.010973936899862832, rel=1e-10)


class TestKGruposRegra:
    def test_a_normal_em_todos_vai_para_a_anova_de_welch(self):
        comparada = _grupos((("nota", "escolaridade"),)).variaveis[0]
        assert comparada.delineamento == K_GRUPOS
        assert comparada.metodo == ANOVA_DE_WELCH
        assert comparada.escolha.motivo == (
            "o Shapiro-Wilk não rejeita a normal em nenhum dos 3 grupos (Fundamental: "
            "p = 1,000; Médio: p = 1,000; Superior: p = 1,000)"
        )
        assert comparada.celula_do_teste == ANOVA_DE_WELCH
        assert comparada.justificativa.endswith("→ ANOVA de Welch (F = 7,11; 2 e 34,46 gl).")

    def test_a_de_welch_pela_regra_com_um_grupo_pequeno_avisa(self):
        """O IMC tem dezenove valores no Médio: abaixo de vinte, o aviso."""
        avisos = _grupos((("imc", "escolaridade"),)).avisos
        assert any(
            "`imc` por `escolaridade`: ANOVA de Welch com 19 valores em Médio" in aviso
            for aviso in avisos
        )

    def test_a_normal_rejeitada_escolhe_o_kruskal_wallis(self):
        """
        A renda rejeita a normal nos três grupos (p = 0,006, 0,002 e < 0,001, no R), e o
        `kruskal.test` dá qui-quadrado = 0,131, 2 gl, p = 0,937.
        """
        comparacao = _grupos((("renda", "escolaridade"),))
        comparada = comparacao.variaveis[0]
        assert (comparada.escolha.metodo, comparada.escolha.da_regra) == (
            KRUSKAL_WALLIS,
            KRUSKAL_WALLIS,
        )
        assert comparada.celula_do_teste == KRUSKAL_WALLIS
        assert comparada.resultado.estatistica == pytest.approx(0.13114754098361914, rel=1e-12)
        assert comparada.resultado.p == pytest.approx(0.93652995593578336, rel=1e-12)
        assert comparada.justificativa.endswith("→ Kruskal-Wallis (χ² = 0,13; 2 gl).")
        assert not any("escreva o método no item" in aviso for aviso in comparacao.avisos)

    def test_a_anova_com_desvios_muito_diferentes_avisa(self):
        avisos = _grupos((("nota", "escolaridade", "anova"),)).avisos
        assert any(
            "`nota` por `escolaridade`: a ANOVA supõe a mesma variância nos grupos, e o "
            "desvio padrão de Superior (2,49) é 2,5 vezes o de Fundamental (1,01). A ANOVA "
            "de Welch não supõe." in aviso
            for aviso in avisos
        )

    def test_a_anova_escrita_contra_a_regra(self):
        comparacao = _grupos((("nota", "escolaridade", "anova"),))
        comparada = comparacao.variaveis[0]
        assert comparada.escolha.contra_a_regra
        assert any("ANOVA escrita na ficha, contra a regra" in a for a in comparacao.avisos)
        assert "ANOVA escrita na ficha (F = 6,39; 2 e 57 gl), contra a regra — ela " in (
            comparada.justificativa
        )

    def test_o_historico_concorda_o_artigo_da_anova(self):
        """
        REGRESSÃO da 1.13.0: o `historico.md` dizia "1 com o ANOVA". A frase usa o
        `_com_artigo`, como as outras frases do módulo.
        """
        from types import SimpleNamespace

        from flatcap.comparacao import _acao_do_historico

        comparacao = _grupos((("nota", "escolaridade", "anova"),))
        acao = _acao_do_historico(SimpleNamespace(comparacao=comparacao, arquivamento=None))
        assert "1 com a ANOVA" in acao
        assert "com o ANOVA" not in acao

    def test_o_metodo_de_dois_grupos_em_tres(self):
        with pytest.raises(ItemInvalidoError) as erro:
            _grupos((("imc", "escolaridade", "t"),))
        assert "`t` não se aplica a 3 grupos" in str(erro.value)
        assert "o t compara dois grupos; escreva `welch`" in str(erro.value)

    def test_a_anova_em_dois_grupos(self):
        with pytest.raises(ItemInvalidoError) as erro:
            _grupos((("imc", "sexo", "anova"),))
        mensagem = str(erro.value)
        assert "`anova` não se aplica a 2 grupos" in mensagem
        assert "o F da ANOVA é o t de Student ao quadrado; escreva `student`" in mensagem

    def test_o_parametrico_que_falta_no_registro(self, monkeypatch):
        """
        O caminho de quando o paramétrico da regra ainda não tem aritmética — o de todo
        teste novo que entra na regra antes do cálculo. Tirada a ANOVA de Welch do
        registro, a linha sai sem teste, com o motivo, e o aviso ensina a clássica.
        """
        import flatcap.comparacao as modulo

        calculo = {k: v for k, v in modulo._CALCULO.items() if k != (K_GRUPOS, ANOVA_DE_WELCH)}
        monkeypatch.setattr(modulo, "_CALCULO", calculo)
        comparacao = _grupos((("nota", "escolaridade"),))
        comparada = comparacao.variaveis[0]
        assert comparada.celula_do_teste == (
            "não testado: ANOVA de Welch ainda não está no FlatCap"
        )
        assert any(
            "A ANOVA, que supõe a mesma variância nos grupos, roda com o método escrito no "
            "item: `[nota, escolaridade, anova]`" in aviso
            for aviso in comparacao.avisos
        )
        assert (
            "A ANOVA de Welch ainda não está no FlatCap, e onde a regra a escolhe a linha sai "
            "sem teste." in comparacao.tabela_de(K_GRUPOS).texto()
        )

    def test_a_troca_que_falta_no_registro_cai_na_que_existe(self, monkeypatch):
        """Sem a ANOVA de Welch, o `t` numa variável de três grupos ensina a `anova`."""
        import flatcap.comparacao as modulo

        calculo = {k: v for k, v in modulo._CALCULO.items() if k != (K_GRUPOS, ANOVA_DE_WELCH)}
        monkeypatch.setattr(modulo, "_CALCULO", calculo)
        with pytest.raises(ItemInvalidoError) as erro:
            _grupos((("imc", "escolaridade", "t"),))
        assert "o t compara dois grupos; escreva `anova`" in str(erro.value)

    def test_welch_e_o_t_com_dois_grupos_e_a_anova_com_tres(self):
        """O mesmo nome, e o teste que o número de grupos do banco pede."""
        comparacao = _grupos((("imc", "sexo", "welch"), ("imc", "escolaridade", "welch")))
        assert [v.metodo for v in comparacao.variaveis] == [T_DE_WELCH, ANOVA_DE_WELCH]
        assert all(not v.escolha.contra_a_regra for v in comparacao.variaveis)

    def test_o_registro_da_regra_entre_tres_grupos_ou_mais(self):
        assert REGRA[K_GRUPOS] == (ANOVA_DE_WELCH, KRUSKAL_WALLIS)
        assert metodo_escrito("anova", K_GRUPOS) == ANOVA
        assert metodo_escrito("anova", DOIS_GRUPOS) == ""
        assert metodo_escrito("welch", K_GRUPOS) == ANOVA_DE_WELCH
        assert metodo_escrito("ANOVA de Welch", K_GRUPOS) == ANOVA_DE_WELCH


class TestKGruposSemTeste:
    def test_um_valor_num_grupo_nao_da_a_de_welch(self):
        quadro, linhas = _tres([30.0], [24.1, 27.3, 22.8], [26.5, 29.9, 31.2])
        comparada = _grupos((("y", "g", "welch"),), quadro, linhas).variaveis[0]
        assert comparada.celula_do_teste == (
            "não testado: A tem 1 valor — a ANOVA de Welch precisa de pelo menos 2 em cada "
            "grupo"
        )

    def test_um_grupo_que_nao_varia_nao_da_a_de_welch(self):
        """O R devolve `NaN`: o peso do grupo constante é n/0. A clássica roda."""
        quadro, linhas = _tres([5.0, 5.0, 5.0], [4.0, 6.0, 7.0], [8.0, 9.0, 11.0])
        comparacao = _grupos((("y", "g", "welch"),), quadro, linhas)
        assert comparacao.variaveis[0].celula_do_teste == (
            "não testado: A não varia — a ANOVA de Welch divide pela variância de cada grupo"
        )

    def test_um_valor_num_grupo_nao_da_a_anova(self):
        """O `not enough observations` do `oneway.test`, que o `aov` aceitaria."""
        quadro, linhas = _tres([30.0], [24.1, 27.3, 22.8], [26.5, 29.9, 31.2])
        comparada = _grupos((("y", "g", "anova"),), quadro, linhas).variaveis[0]
        assert comparada.celula_do_teste == (
            "não testado: A tem 1 valor — a ANOVA precisa de pelo menos 2 em cada grupo"
        )
        assert "ANOVA escrita na ficha, que não pôde ser calculada" in comparada.justificativa

    def test_grupos_que_nao_variam_por_dentro(self):
        """O R devolveria F infinito e p zero; aqui a linha sai sem teste."""
        quadro, linhas = _tres([5.0, 5.0], [6.0, 6.0], [7.0, 7.0, 7.0])
        comparada = _grupos((("y", "g", "anova"),), quadro, linhas).variaveis[0]
        assert comparada.celula_do_teste == "não testado: os valores não variam dentro dos grupos"

    def test_um_grupo_so_na_tabela_que_o_dicionario_promete(self):
        """
        O dicionário declara três escolaridades, e o banco só tem uma: a linha sai sem
        teste, na tabela dos k grupos.
        """
        quadro = bancos.para_comparar_grupos().assign(escolaridade="Médio")
        comparacao = _grupos((("imc", "escolaridade"),), quadro)
        assert comparacao.variaveis[0].delineamento == K_GRUPOS
        assert comparacao.variaveis[0].celula_do_teste == "não testado: um grupo só"
        assert [t.nome for t in comparacao.tabelas] == [ARQUIVO_K_GRUPOS]


class TestKGruposTabela:
    def test_as_seis_colunas(self):
        tabela = _grupos((("imc", "escolaridade"),)).tabela_de(K_GRUPOS)
        assert tabela.colunas == ("variável", "grupo", "n", "média (DP)", "teste", "p-valor")
        assert (tabela.nome, tabela.especie, tabela.titulo) == (
            ARQUIVO_K_GRUPOS,
            K_GRUPOS,
            "Comparação entre três grupos ou mais",
        )

    def test_o_bloco_de_uma_comparacao(self):
        _, _, _, p, grupos = ANOVA_DO_R[0]

        def media_dp(grupo):
            return f"{_como_a_descritiva(grupo[1])} ({_como_a_descritiva(grupo[2])})"

        assert _grupos((("nota", "escolaridade", "anova"),)).tabela_de(K_GRUPOS).linhas == (
            ("Nota", "Escolaridade", "60", "", "ANOVA", valor_p(p)),
            ("", "Fundamental", "20", media_dp(grupos[0]), "", ""),
            ("", "Médio", "20", media_dp(grupos[1]), "", ""),
            ("", "Superior", "20", media_dp(grupos[2]), "", ""),
        )

    def test_as_notas_dizem_como_o_r_faz_e_o_que_falta(self):
        texto = _grupos((("nota", "escolaridade"),)).tabela_de(K_GRUPOS).texto()
        assert "oneway.test do R com var.equal = TRUE" in texto
        assert "os graus de liberdade de Welch no denominador" in texto
        assert "Kruskal-Wallis, como o kruskal.test do R" in texto
        assert "Kruskal-Wallis ainda não está" not in texto
        assert "o pós-teste — ainda não está no FlatCap" in texto
        assert (
            "Nota por Escolaridade: n = 60 (20 em Fundamental, 20 em Médio e 20 em "
            "Superior); o Shapiro-Wilk não rejeita a normal em nenhum dos 3 grupos"
        ) in texto

    def test_as_tres_tabelas_na_ordem(self):
        comparacao = _grupos((("nota", "escolaridade"), ("imc", 25), ("imc", "sexo")))
        assert [t.nome for t in comparacao.tabelas] == [
            ARQUIVO_TABELA,
            ARQUIVO_DOIS_GRUPOS,
            ARQUIVO_K_GRUPOS,
        ]
        (item,) = montar_manifesto(comparacao, DICIONARIO_DOS_GRUPOS).itens
        assert [a.arquivo for a in item.artefatos] == [
            ARQUIVO_TABELA,
            ARQUIVO_DOIS_GRUPOS,
            ARQUIVO_K_GRUPOS,
        ]
        assert set(item.detalhes) >= {UMA_AMOSTRA, DOIS_GRUPOS, K_GRUPOS}

    def test_os_detalhes_da_anova(self):
        comparacao = _grupos((("nota", "escolaridade", "anova"),))
        (nota,) = montar_manifesto(comparacao, DICIONARIO_DOS_GRUPOS).itens[0].detalhes[K_GRUPOS]
        assert nota["estatistica"] == {"nome": "F", "valor": 6.387986, "gl": [2.0, 57.0]}
        assert (nota["estimativa"]["valor"], nota["ic_95"]) == (None, None)
        assert [g["n"] for g in nota["por_grupo"]] == [20, 20, 20]


# ── Medidas repetidas ───────────────────────────────────────────────────────


class TestRepetidasDoR:
    @pytest.mark.parametrize(
        ("base", "n", "f", "epsilon", "gl", "p", "medidas"),
        REPETIDAS_DO_R,
        ids=[base for base, *_ in REPETIDAS_DO_R],
    )
    def test_o_aov_o_epsilon_e_o_shapiro_test_de_cada_medida(
        self, base, n, f, epsilon, gl, p, medidas
    ):
        """
        Com `metodo: anova` escrito, a ANOVA sai também onde a regra não a escolheria —
        e dá para conferir as duas contra o R: o F, o ε, os gl corrigidos, o p e, de
        cada medida, o n, a média, o DP e o Shapiro-Wilk sobre os casos completos.
        """
        nomes = [f"{base}_{j}" for j in range(3)]
        comparada = _repetidas((("repetidas", nomes, "anova"),)).variaveis[0]
        resultado = comparada.resultado
        assert resultado.metodo == ANOVA_DE_MEDIDAS_REPETIDAS
        assert resultado.estatistica == pytest.approx(f, rel=1e-12)
        assert resultado.epsilon == pytest.approx(epsilon, rel=1e-9)
        assert resultado.gl == pytest.approx(gl, rel=1e-9)
        assert resultado.p == pytest.approx(p, rel=1e-8)
        assert comparada.validos == n
        for grupo, (m, media, dp, w, p_shapiro) in zip(comparada.grupos, medidas, strict=True):
            assert grupo.n == m
            assert grupo.resumo["media"] == pytest.approx(media, rel=1e-12)
            assert grupo.resumo["desvio"] == pytest.approx(dp, rel=1e-12)
            assert grupo.normal.w == pytest.approx(w, rel=1e-6)
            assert grupo.normal.p == pytest.approx(p_shapiro, rel=1e-4)


class TestRepetidasRegra:
    def test_a_normal_em_todas_vai_para_a_anova_de_medidas_repetidas(self):
        comparada = _repetidas((ITEM_PAS,)).variaveis[0]
        assert comparada.delineamento == REPETIDAS
        assert (comparada.metodo, comparada.escolha.pela_ficha) == (
            ANOVA_DE_MEDIDAS_REPETIDAS,
            False,
        )
        assert comparada.escolha.motivo == (
            "o Shapiro-Wilk não rejeita a normal em nenhuma das 3 medidas (PAS basal: "
            "p = 0,796; PAS 30 dias: p = 0,852; PAS 90 dias: p = 0,633)"
        )
        assert comparada.justificativa == (
            "PAS basal, PAS 30 dias e PAS 90 dias: n = 38 com todas as medidas; "
            f"{comparada.escolha.motivo} → ANOVA de medidas repetidas (F = 37,04; 1,84 e "
            "67,96 gl; ε = 0,918)."
        )

    def test_a_normal_rejeitada_escolhe_o_friedman(self):
        """
        A escala de dor rejeita a normal nas três medidas, e o `friedman.test` dá
        qui-quadrado = 2,081, 2 gl, p = 0,353 — com a mediana e os quartis de cada medida.
        """
        _, n, qui, gl, p, medidas = next(r for r in FRIEDMAN_DO_R if r[0] == "dor")
        comparacao = _repetidas((ITEM_DOR,))
        comparada = comparacao.variaveis[0]
        assert (comparada.escolha.metodo, comparada.escolha.da_regra) == (FRIEDMAN, FRIEDMAN)
        assert comparada.celula_do_teste == FRIEDMAN
        assert comparada.validos == n
        assert comparada.resultado.estatistica == pytest.approx(qui, rel=1e-12)
        assert comparada.resultado.gl == (gl,)
        assert comparada.resultado.p == pytest.approx(p, rel=1e-12)
        tabela = comparacao.tabela_de(REPETIDAS)
        assert tabela.colunas[2] == COLUNA_DA_MEDIANA
        assert [linha[2] for linha in tabela.linhas] == [
            _mediana_quartis(*medida) for medida in medidas
        ]
        assert [linha[2] for linha in tabela.linhas] == ["1 [0 a 1,25]", "0 [0 a 1]", "0 [0 a 1]"]
        assert not any("escreva o método no item" in aviso for aviso in comparacao.avisos)

    def test_a_anova_pela_regra_com_poucos_casos_avisa(self):
        """
        Dez casos: o Shapiro-Wilk não rejeita em nenhuma medida, e a regra escolhe a
        ANOVA por falta de evidência contra a normal — não por evidência a favor.
        """
        quadro = pd.DataFrame(
            {
                "pas_0": [132, 140, 128, 150, 138, 126, 145, 133, 129, 141],
                "pas_1": [128, 135, 127, 142, 131, 124, 139, 130, 126, 133],
                "pas_2": [125, 136, 121, 139, 128, 125, 132, 124, 123, 130],
            }
        )
        comparacao = _repetidas((ITEM_PAS,), quadro, (PAS_0, PAS_1, PAS_2))
        assert comparacao.variaveis[0].metodo == ANOVA_DE_MEDIDAS_REPETIDAS
        assert any(
            "`repetidas: [pas_0, pas_1, pas_2]`: ANOVA de medidas repetidas com 10 casos" in a
            for a in comparacao.avisos
        )
        assert not any("com 38 casos" in a for a in _repetidas((ITEM_PAS,)).avisos)

    def test_a_escala_com_a_normal_rejeitada_avisa_que_e_discreta(self):
        avisos = _repetidas((ITEM_DOR,)).avisos
        assert any(
            "`repetidas: [dor_0, dor_1, dor_2]`: 5 valores distintos em 120 casos" in a
            for a in avisos
        )

    def test_a_anova_escrita_contra_a_regra(self):
        comparacao = _repetidas((("repetidas", ["dor_0", "dor_1", "dor_2"], "anova"),))
        comparada = comparacao.variaveis[0]
        assert comparada.escolha.contra_a_regra
        assert (
            "ANOVA de medidas repetidas escrita na ficha (F = 1,94; 1,95 e 76,19 gl; "
            "ε = 0,977), contra a regra — ela escolheria Friedman: o Shapiro-Wilk rejeita"
        ) in comparada.justificativa
        assert any("escrita na ficha, contra a regra" in a for a in comparacao.avisos)

    def test_o_registro_da_regra_das_medidas_repetidas(self):
        assert REGRA[REPETIDAS] == (ANOVA_DE_MEDIDAS_REPETIDAS, FRIEDMAN)
        assert metodo_escrito("anova", REPETIDAS) == ANOVA_DE_MEDIDAS_REPETIDAS
        assert metodo_escrito("friedman", REPETIDAS) == FRIEDMAN
        assert metodo_escrito("Friedmann", REPETIDAS) == FRIEDMAN
        assert metodo_escrito("welch", REPETIDAS) == ""


class TestRepetidasNoBanco:
    def test_so_os_casos_com_todas_as_medidas(self):
        """
        Duas células vazias, em casos diferentes: 38 casos completos, e a média de
        cada medida é a desses 38 — a da `pas_0` é 130, e não os 129,95 dos quarenta.
        """
        comparada = _repetidas((ITEM_PAS,)).variaveis[0]
        assert (comparada.validos, comparada.faltantes) == (38, 2)
        assert [g.n for g in comparada.grupos] == [38, 38, 38]
        assert comparada.grupos[0].resumo["media"] == pytest.approx(130.0, rel=1e-12)

    def test_medidas_que_nao_variam_dentro_dos_casos(self):
        """Cada caso ganha um quilo por medida: o R daria F = 10²⁹. Aqui, sem teste."""
        comparacao = _repetidas((("repetidas", ["peso_0", "peso_1", "peso_2"], "anova"),))
        comparada = comparacao.variaveis[0]
        assert comparada.celula_do_teste == "não testado: as medidas não variam dentro dos casos"
        assert any("cada caso muda o mesmo tanto" in a for a in comparacao.avisos)

    def test_nenhum_caso_completo(self):
        quadro = bancos.para_comparar_repetidas().assign(pas_2=None)
        comparada = _repetidas((ITEM_PAS,), quadro).variaveis[0]
        assert comparada.celula_do_teste == "não testado: nenhum caso com todas as medidas"
        assert [linha[2] for linha in linhas_da_tabela(comparada)] == ["—", "—", "—"]

    def test_um_caso_completo(self):
        quadro = bancos.para_comparar_repetidas()
        quadro.loc[1:, "pas_2"] = None
        comparada = _repetidas((ITEM_PAS,), quadro).variaveis[0]
        assert comparada.celula_do_teste == (
            "não testado: 1 caso com todas as medidas — o teste precisa de pelo menos 2"
        )

    def test_um_valor_so_em_todas_as_linhas(self):
        quadro = bancos.para_comparar_repetidas().assign(pas_0=120.0, pas_1=120.0, pas_2=120.0)
        comparada = _repetidas((ITEM_PAS,), quadro).variaveis[0]
        assert comparada.celula_do_teste == "não testado: um valor só em todas as linhas"


class TestRepetidasTabela:
    def test_as_cinco_colunas_e_uma_linha_por_medida(self):
        _, n, _, _, _, p, medidas = REPETIDAS_DO_R[0]
        tabela = _repetidas((ITEM_PAS,)).tabela_de(REPETIDAS)
        assert (tabela.nome, tabela.especie, tabela.titulo) == (
            ARQUIVO_REPETIDAS,
            REPETIDAS,
            "Comparação entre medidas repetidas",
        )
        assert tabela.colunas == ("medida", "n", "média (DP)", "teste", "p-valor")

        def media_dp(medida):
            return f"{_como_a_descritiva(medida[1])} ({_como_a_descritiva(medida[2])})"

        assert tabela.linhas == (
            ("PAS basal", "38", media_dp(medidas[0]), ANOVA_DE_MEDIDAS_REPETIDAS, valor_p(p)),
            ("PAS 30 dias", "38", media_dp(medidas[1]), "", ""),
            ("PAS 90 dias", "38", media_dp(medidas[2]), "", ""),
        )

    def test_as_notas_dizem_como_o_r_faz_e_o_que_falta(self):
        texto = _repetidas((ITEM_PAS, ITEM_DOR)).tabela_de(REPETIDAS).texto()
        assert "sempre com a correção de Greenhouse-Geisser" in texto
        assert "Sem o teste de Mauchly antes" in texto
        assert "Friedman, como o friedman.test do R" in texto
        assert "`metodo: anova` ou `metodo: friedman`" in texto
        assert "Friedman ainda não está" not in texto
        assert "um caso com uma medida faltando sai do item inteiro" in texto

    def test_as_quatro_tabelas_na_ordem(self):
        quadro = bancos.para_comparar_repetidas().assign(
            imc=[20.0 + (i % 7) for i in range(40)],
            escolaridade=["A", "B", "C", "D"] * 10,
        )
        linhas = (
            *DICIONARIO_DAS_REPETIDAS,
            IMC,
            Linha("escolaridade", "Escolaridade", CATEGORICA, ("A", "B", "C", "D")),
        )
        comparacao = _repetidas(
            (ITEM_PAS, ("imc", 25), ("imc", "sexo"), ("imc", "escolaridade")), quadro, linhas
        )
        assert [t.nome for t in comparacao.tabelas] == [
            ARQUIVO_TABELA,
            ARQUIVO_DOIS_GRUPOS,
            ARQUIVO_K_GRUPOS,
            ARQUIVO_REPETIDAS,
        ]

    def test_os_detalhes_das_medidas_repetidas(self):
        comparacao = _repetidas((ITEM_PAS,))
        (item,) = montar_manifesto(comparacao, DICIONARIO_DAS_REPETIDAS).itens
        (pas,) = item.detalhes[REPETIDAS]
        assert pas["medidas"] == ["pas_0", "pas_1", "pas_2"]
        assert (pas["n"], pas["faltantes"]) == (38, 2)
        assert [m["rotulo"] for m in pas["por_medida"]] == [
            "PAS basal",
            "PAS 30 dias",
            "PAS 90 dias",
        ]
        assert pas["epsilon"] == pytest.approx(0.918435, abs=1e-6)
        assert item.colunas == ("pas_0", "pas_1", "pas_2")
        assert [a.arquivo for a in item.artefatos] == [ARQUIVO_REPETIDAS]

    def test_as_medidas_nao_estao_fora(self):
        manifesto = montar_manifesto(_repetidas((ITEM_PAS,)), DICIONARIO_DAS_REPETIDAS)
        fora = {f["variavel"] for f in manifesto.fora}
        assert not fora & {"pas_0", "pas_1", "pas_2"}
        assert "dor_0" in fora


class TestRepetidasRecusas:
    def _recusa(self, *itens, linhas=DICIONARIO_DAS_REPETIDAS) -> str:
        with pytest.raises(ItemInvalidoError) as erro:
            _repetidas(itens, linhas=linhas)
        return str(erro.value)

    def test_medida_fora_do_dicionario(self):
        mensagem = self._recusa(("repetidas", ["pas_0", "pas_1", "pas_9"]))
        assert "repetidas: [pas_0, pas_1, pas_9] — `pas_9` não está no dicionario.csv" in mensagem

    def test_medida_categorica(self):
        mensagem = self._recusa(("repetidas", ["pas_0", "pas_1", "sexo"]))
        assert "`sexo` está marcada `categorica`" in mensagem
        assert "a média de um código não é uma média" in mensagem

    def test_as_medidas_com_o_mesmo_problema_numa_frase_so(self):
        codigos = tuple(Linha(f"dor_{j}", f"Dor {j}", CATEGORICA) for j in range(3))
        mensagem = self._recusa(
            ("repetidas", ["dor_0", "dor_1", "dor_2"]),
            linhas=(*DICIONARIO_DAS_REPETIDAS[:3], *codigos),
        )
        assert "`dor_0`, `dor_1` e `dor_2` estão marcadas `categorica`" in mensagem

    def test_as_mesmas_medidas_em_outra_ordem_repetem(self):
        mensagem = self._recusa(ITEM_PAS, ("repetidas", ["pas_2", "pas_1", "pas_0"]))
        assert "repete repetidas: [pas_0, pas_1, pas_2]" in mensagem

    def test_duas_numericas_entre_grupos_ensinam_as_repetidas(self):
        mensagem = self._recusa(("pas_0", "pas_1"))
        assert "`- repetidas: [pas_0, pas_1, ...]`" in mensagem


class TestRepetidasFicha:
    def test_as_formas_das_repetidas(self, projeto_vazio):
        itens = _itens(
            projeto_vazio,
            "  - repetidas: [pas_0, pas_1, pas_2]\n"
            "  - repetidas: [dor_0, dor_1, dor_2]\n"
            "    metodo: ANOVA\n"
            "  - {repetidas: [peso_0, peso_1, peso_2], metodo: anova}\n",
        )
        assert itens == (
            Pedido("pas_0", medidas=("pas_0", "pas_1", "pas_2")),
            Pedido("dor_0", metodo="anova", medidas=("dor_0", "dor_1", "dor_2")),
            Pedido("peso_0", metodo="anova", medidas=("peso_0", "peso_1", "peso_2")),
        )

    def test_duas_medidas_sao_o_t_pareado(self, projeto_vazio):
        mensagem = _recusa(projeto_vazio, "  - repetidas: [pas_0, pas_1]\n")
        assert "duas medidas: a comparação é o t pareado, que ainda não está" in mensagem

    def test_uma_medida_so(self, projeto_vazio):
        mensagem = _recusa(projeto_vazio, "  - repetidas: pas_0\n")
        assert "uma medida só" in mensagem

    def test_a_mesma_medida_duas_vezes(self, projeto_vazio):
        mensagem = _recusa(projeto_vazio, "  - repetidas: [pas_0, pas_1, pas_0]\n")
        assert "`pas_0` duas vezes" in mensagem

    def test_chave_que_nao_existe(self, projeto_vazio):
        mensagem = _recusa(
            projeto_vazio, "  - repetidas: [pas_0, pas_1, pas_2]\n    metodos: anova\n"
        )
        assert "`metodos` não é uma chave do item de medidas repetidas" in mensagem

    def test_o_friedman_escrito(self, projeto_vazio):
        itens = _itens(
            projeto_vazio, "  - repetidas: [pas_0, pas_1, pas_2]\n    metodo: Friedman\n"
        )
        assert itens == (
            Pedido("pas_0", metodo="friedman", medidas=("pas_0", "pas_1", "pas_2")),
        )

    def test_o_metodo_que_nao_e_das_repetidas_lista_os_que_sao(self, projeto_vazio):
        mensagem = _recusa(
            projeto_vazio, "  - repetidas: [pas_0, pas_1, pas_2]\n    metodo: kruskal\n"
        )
        assert "`kruskal` não é um método das medidas repetidas" in mensagem
        assert "o método que se escreve é `anova` ou `friedman`" in mensagem

    def test_o_welch_nao_e_das_repetidas(self, projeto_vazio):
        mensagem = _recusa(
            projeto_vazio, "  - repetidas: [pas_0, pas_1, pas_2]\n    metodo: welch\n"
        )
        assert "`welch` não é um método das medidas repetidas" in mensagem

    def test_numero_na_lista(self, projeto_vazio):
        mensagem = _recusa(projeto_vazio, "  - repetidas: [pas_0, 120, pas_2]\n")
        assert "depois de `repetidas:` vem a lista das medidas" in mensagem


# ── Os testes de postos: o R sobre os bancos ───────────────────────────────


class TestWilcoxonNoBanco:
    @pytest.mark.parametrize(
        ("variavel", "mu", "n", "v", "p", "ic", "estimativa", "quartis"),
        WILCOXON_DO_R,
        ids=[f"{variavel}-mu{mu}" for variavel, mu, *_ in WILCOXON_DO_R],
    )
    def test_o_wilcox_test_do_r(self, variavel, mu, n, v, p, ic, estimativa, quartis):
        """
        Com `wilcoxon` escrito no item, o Wilcoxon sai em todas as colunas — mesmo onde a
        regra escolheria o t —, e cada número confere com o R: o V, o p, o intervalo, a
        pseudomediana e os quartis do resumo da linha.
        """
        comparacao = _comparar(itens=((variavel, mu, "wilcoxon"),))
        linha = comparacao.variaveis[0]
        resultado = linha.resultado
        assert linha.validos == n
        assert resultado.metodo == WILCOXON
        assert resultado.estatistica == v
        assert resultado.p == pytest.approx(p, rel=1e-12)
        assert resultado.ic == pytest.approx(ic, rel=1e-12)
        assert resultado.estimativa == pytest.approx(estimativa, rel=1e-12)
        q1, mediana, q3 = quartis
        celulas = comparacao.tabela_de(UMA_AMOSTRA).linhas[0]
        assert celulas[2] == _quartis_conferidos(linha.resumo, mediana, q1, q3)
        assert celulas[3] == f"{_duas_casas(ic[0])} a {_duas_casas(ic[1])}"

    def test_o_wilcoxon_escrito_contra_a_regra(self):
        """O IMC não rejeita a normal: a regra escolheria o t, e a nota diz isso."""
        comparacao = _comparar(itens=(("imc", 25, "wilcoxon"),))
        linha = comparacao.variaveis[0]
        assert linha.escolha.contra_a_regra
        assert (
            "Wilcoxon escrito na ficha (V = 1045; p aproximado pela normal, com correção de "
            "continuidade, porque há 50 valores ou mais, empates e valores iguais à "
            "referência), contra a regra — ela escolheria t de Student: o Shapiro-Wilk não "
            "rejeita a normal (p = 1,000)."
        ) in linha.justificativa
        assert any("Wilcoxon escrito na ficha, contra a regra" in a for a in comparacao.avisos)

    def test_o_mesmo_item_pelo_t_e_pelo_wilcoxon_repete(self):
        """A mesma pergunta por dois testes é ficar com o p que convier."""
        with pytest.raises(ItemInvalidoError, match=r"repete \[renda, 2500\]"):
            _comparar(itens=(("renda", 2500), ("renda", 2500, "wilcoxon")))

    def test_o_caminho_exato_com_poucos_valores(self):
        """
        `wilcox.test(c(1.2, 3.4, 2.2, 5.1, -0.7), mu = 0, conf.int = TRUE)`: V = 14,
        p = 0,125, exato, e o intervalo de 95% do menor ao maior valor. Com cinco valores
        o menor p possível é 0,0625 — acima de 0,05 —, e o aviso diz isso; o intervalo
        sai, porque o R o dá como de 95%.
        """
        quadro, linhas = _uma("a", [1.2, 3.4, 2.2, 5.1, -0.7])
        comparacao = _comparar(quadro, linhas, (("a", 0, "wilcoxon"),))
        resultado = comparacao.variaveis[0].resultado
        assert (resultado.estatistica, resultado.p, resultado.exato) == (14, 0.125, True)
        assert resultado.ic == (-0.69999999999999996, 5.0999999999999996)
        assert comparacao.tabela_de(UMA_AMOSTRA).linhas[0][3] == "-0,70 a 5,10"
        assert "V = 14; p exato" in comparacao.variaveis[0].justificativa
        assert any(
            aviso == (
                f"`a`: Wilcoxon com 5 valores — o menor p que ele pode dar é "
                f"{valor_p(0.0625)}, acima de 0,05. Com tão poucos valores, o teste não "
                "rejeita a igualdade com dado nenhum."
            )
            for aviso in comparacao.avisos
        )

    def test_o_intervalo_que_nao_chega_a_95_fica_fora_da_tabela(self):
        """
        Com quatro valores, o intervalo mais largo tem 88% — o R o devolve com esse
        nível, e avisa. A tabela promete 95%: a célula sai com o traço, debaixo do nome
        do intervalo que faltou, e o intervalo do R vai para o manifesto, com o nível.
        """
        quadro, linhas = _uma("a", [1.2, 3.4, 2.2, 5.1])
        comparacao = _comparar(quadro, linhas, (("a", 0, "wilcoxon"),))
        assert comparacao.tabela_de(UMA_AMOSTRA).linhas[0][3] == "—"
        assert comparacao.tabela_de(UMA_AMOSTRA).colunas[3] == COLUNA_DO_IC_DA_PSEUDOMEDIANA
        assert any(
            "o intervalo de 95% não é alcançável — o mais largo que existe tem 88%" in aviso
            and "A célula do intervalo sai com —." in aviso
            for aviso in comparacao.avisos
        )
        (detalhe,) = montar_manifesto(comparacao, linhas).itens[0].detalhes[UMA_AMOSTRA]
        assert detalhe["ic_95"] is None
        assert detalhe["ic_alcancavel"] == {"confianca": 0.88, "limites": [1.2, 5.1]}

    def test_sem_os_iguais_a_referencia_os_que_sobram_nao_variam(self):
        """
        `wilcox.test(c(25, 27, 27, 27), mu = 25)`: V = 6, p = 0,1489 — e, sem o 25, o
        intervalo não existe: o R devolve `NaN`. A linha sai com o p, e o intervalo, com o
        traço e o aviso.
        """
        quadro, linhas = _uma("a", [25.0, 27.0, 27.0, 27.0])
        comparacao = _comparar(quadro, linhas, (("a", 25, "wilcoxon"),))
        resultado = comparacao.variaveis[0].resultado
        assert resultado.p == pytest.approx(0.14891467317876567, rel=1e-12)
        assert comparacao.tabela_de(UMA_AMOSTRA).linhas[0][3] == "—"
        assert any(
            "sem os valores iguais à referência, os que sobram são todos iguais" in aviso
            for aviso in comparacao.avisos
        )

    def test_os_intervalos_aproximados_que_nao_chegam_a_95(self):
        """
        Com empates, o R acha o intervalo pela aproximação normal e, quando nem os
        extremos alcançam os quantis, dobra o α até alcançar: `wilcox.test(c(3, 3, 3, 4,
        1), conf.int = TRUE)` fica com 90%, e `wilcox.test(c(1, 2, 2), conf.int = TRUE)`,
        com o α passando de 1, com nível zero — intervalo nenhum. Os dois p saem, as duas
        células do intervalo saem com o traço, e os avisos dizem o que faltou. No caminho
        aproximado não há menor p possível, e ele não entra na frase.
        """
        quadro = pd.DataFrame(
            {"a": [1.0, 2.0, 2.0, None, None], "b": [3.0, 3.0, 3.0, 4.0, 1.0]}
        )
        linhas = (Linha("a", "A", NUMERICA), Linha("b", "B", NUMERICA))
        comparacao = _comparar(quadro, linhas, (("a", 0, "wilcoxon"), ("b", 0, "wilcoxon")))
        a, b = (v.resultado for v in comparacao.variaveis)
        assert (a.p, a.confianca_do_ic) == (pytest.approx(0.17356816655592155, rel=1e-12), 0)
        assert (b.p, b.confianca_do_ic) == (
            pytest.approx(0.054474035106195577, rel=1e-12),
            pytest.approx(0.9, rel=1e-12),
        )
        tabela = comparacao.tabela_de(UMA_AMOSTRA)
        assert [linha[3] for linha in tabela.linhas] == ["—", "—"]
        assert tabela.colunas[3] == COLUNA_DO_IC_DA_PSEUDOMEDIANA
        assert (
            "`a`: Wilcoxon com 3 valores — o intervalo de 95% não é alcançável — não há "
            "intervalo nenhum. A célula do intervalo sai com —."
        ) in comparacao.avisos
        assert (
            "`b`: Wilcoxon com 5 valores — o intervalo de 95% não é alcançável — o mais "
            "largo que existe tem 90%. A célula do intervalo sai com —."
        ) in comparacao.avisos

    def test_o_cabecalho_do_intervalo_ignora_a_linha_sem_teste(self):
        """
        A linha que não chegou a teste nenhum — um valor só em todas — é resumida pela
        média, e o cabeçalho do resumo diz as duas formas; intervalo ela não tem, e o
        cabeçalho do intervalo fica o da pseudomediana, o da outra linha.
        """
        quadro = pd.DataFrame({"a": [1.2, 3.4, 2.2, 5.1, -0.7, 4.4], "s": [1.0] * 6})
        linhas = (Linha("a", "A", NUMERICA), Linha("s", "S", NUMERICA))
        comparacao = _comparar(quadro, linhas, (("a", 0, "wilcoxon"), ("s", 1)))
        tabela = comparacao.tabela_de(UMA_AMOSTRA)
        assert tabela.linhas[1][2:6] == (
            "1 (0)", "—", "1", "não testado: um valor só em todas as linhas",
        )
        assert tabela.colunas[2:4] == (COLUNA_DAS_DUAS, COLUNA_DO_IC_DA_PSEUDOMEDIANA)


class TestMannWhitneyNoBanco:
    @pytest.mark.parametrize(
        ("variavel", "w", "p", "ic", "diferenca", "exato", "feminino", "masculino"),
        MANN_WHITNEY_DO_R,
        ids=[variavel for variavel, *_ in MANN_WHITNEY_DO_R],
    )
    def test_o_wilcox_test_do_r(self, variavel, w, p, ic, diferenca, exato, feminino, masculino):
        """
        Com `mannwhitney` escrito, o Mann-Whitney sai em todas as colunas, e cada número
        confere com o R: o W, o p, o caminho, o intervalo e a diferença de locação — e
        de cada grupo o n, a mediana e os quartis.
        """
        comparacao = _grupos(((variavel, "sexo", "mannwhitney"),))
        comparada = comparacao.variaveis[0]
        resultado = comparada.resultado
        assert resultado.metodo == MANN_WHITNEY
        assert resultado.estatistica == w
        assert resultado.p == pytest.approx(p, rel=1e-12)
        assert resultado.exato is exato
        assert resultado.ic == pytest.approx(ic, rel=1e-12)
        assert resultado.estimativa == pytest.approx(diferenca, rel=1e-12)
        assert [grupo.n for grupo in comparada.grupos] == [feminino[0], masculino[0]]
        tabela = comparacao.tabela_de(DOIS_GRUPOS)
        assert tabela.colunas[3:5] == (COLUNA_DA_MEDIANA, COLUNA_DA_DIFERENCA_DE_LOCACAO)
        cabeca, *linhas = tabela.linhas
        assert cabeca[4] == (
            f"{_duas_casas(diferenca)} ({_duas_casas(ic[0])} a {_duas_casas(ic[1])})"
        )
        assert [linha[3] for linha in linhas] == [
            _quartis_conferidos(grupo.resumo, *do_r[1:])
            for grupo, do_r in zip(comparada.grupos, (feminino, masculino), strict=True)
        ]

    def test_o_wilcoxon_escrito_entre_dois_grupos_e_o_mann_whitney(self):
        """O `wilcox.test` de duas amostras: o nome do R, e o teste que a regra escolhe."""
        comparada = _grupos((("renda", "sexo", "wilcoxon"),)).variaveis[0]
        assert comparada.metodo == MANN_WHITNEY
        assert comparada.escolha.pela_ficha and not comparada.escolha.contra_a_regra

    def test_a_tabela_mistura_os_dois_resumos(self):
        """
        O IMC pelo t de Welch, a renda pelo Mann-Whitney: cada bloco no seu resumo, e os
        dois cabeçalhos dizendo as duas formas — a da diferença também, porque a de
        locação ao lado das medianas seria lida como a diferença delas.
        """
        tabela = _grupos((("imc", "sexo"), ("renda", "sexo"))).tabela_de(DOIS_GRUPOS)
        assert tabela.colunas[3:5] == (COLUNA_DAS_DUAS, COLUNA_DAS_DUAS_DIFERENCAS)
        assert COLUNA_DA_DIFERENCA == "diferença (IC 95%)"
        assert [linha[3] for linha in tabela.linhas] == [
            "", "25,09 (2,99)", "27,41 (4,06)",
            "", "2982,62 [1774,62 a 5013,54]", "4026,12 [2445,74 a 7059,41]",
        ]

    def test_o_cabecalho_da_diferenca_ignora_o_bloco_sem_teste(self):
        """
        O bloco sem teste — um grupo só — é resumido pela média, e o cabeçalho do resumo
        diz as duas formas; diferença ele não tem, e o cabeçalho dela fica o da locação.
        """
        tabela = _grupos((("renda", "sexo"), ("imc", "unico"))).tabela_de(DOIS_GRUPOS)
        assert tabela.colunas[3:5] == (COLUNA_DAS_DUAS, COLUNA_DA_DIFERENCA_DE_LOCACAO)

    def test_a_ordem_dos_grupos_decide_o_sinal_da_diferenca_de_locacao(self):
        invertido = Linha(
            "sexo",
            "Sexo",
            CATEGORICA,
            ("2", "1"),
            rotulos_das_categorias=(("1", "Feminino"), ("2", "Masculino")),
        )
        linhas = (IMC, RENDA, PAS, NOTA, invertido, ESCOLARIDADE, UNICO)
        comparada = _grupos((("renda", "sexo"),), linhas=linhas).variaveis[0]
        assert [g.rotulo for g in comparada.grupos] == ["Masculino", "Feminino"]
        assert comparada.resultado.estimativa == pytest.approx(921.57000000000005, rel=1e-12)
        assert comparada.resultado.p == pytest.approx(0.1697319562818404, rel=1e-12)

    def test_dois_grupos_que_nao_variam_por_dentro(self):
        """
        Cada grupo com o seu valor: a normalidade não se verifica, a regra vai para o
        Mann-Whitney, e o R calcula — `wilcox.test(c(5, 5, 5), c(6, 6, 6))`: W = 0,
        p = 0,04685. A diferença de locação não tem intervalo, e o R para com erro com
        `conf.int = TRUE`: a célula sai com o traço, e o aviso diz por quê.
        """
        quadro, linhas = _dois([5.0, 5.0, 5.0], [6.0, 6.0, 6.0])
        comparacao = _grupos((("y", "g"),), quadro, linhas)
        comparada = comparacao.variaveis[0]
        assert comparada.metodo == MANN_WHITNEY
        assert comparada.resultado.p == pytest.approx(0.046854177603873753, rel=1e-12)
        assert linhas_da_tabela(comparada)[0][4] == "—"
        assert any("os grupos não variam por dentro" in aviso for aviso in comparacao.avisos)

    def test_o_intervalo_que_nao_chega_a_95(self):
        """
        Dois e cinco valores: o mais largo tem 90,5% — `wilcox.test(c(24, 27), c(25,
        26.5, 28, 30.1, 27.2), conf.int = TRUE)` —, e a célula sai com o traço.
        """
        quadro, linhas = _dois([24.0, 27.0], [25.0, 26.5, 28.0, 30.1, 27.2])
        comparacao = _grupos((("y", "g"),), quadro, linhas)
        comparada = comparacao.variaveis[0]
        assert comparada.resultado.ic == (-6.1000000000000014, 2.0)
        assert comparada.resultado.confianca_do_ic == pytest.approx(0.90476190476190477)
        assert linhas_da_tabela(comparada)[0][4] == "—"
        (detalhe,) = montar_manifesto(comparacao, linhas).itens[0].detalhes[DOIS_GRUPOS]
        assert detalhe["ic_alcancavel"] == {"confianca": 0.904762, "limites": [-6.1, 2.0]}
        assert detalhe["estimativa"] == {"nome": "diferença de locação", "valor": -1.75}

    def test_os_metodos_do_numero_errado_de_grupos(self):
        """Só o banco sabe quantos grupos há, e a recusa ensina a troca."""
        with pytest.raises(ItemInvalidoError) as erro:
            _grupos(
                (
                    ("imc", "escolaridade", "mannwhitney"),
                    ("pas", "escolaridade", "wilcoxon"),
                    ("imc", "sexo", "kruskal"),
                )
            )
        mensagem = str(erro.value)
        assert "3 item(ns) que este banco não deixa comparar" in mensagem
        assert "o Mann-Whitney compara dois grupos; escreva `kruskal`" in mensagem
        assert (
            "o Wilcoxon entre grupos é o Mann-Whitney, que compara dois; escreva `kruskal`"
            in mensagem
        )
        assert "com dois grupos, o teste é o Mann-Whitney; escreva `mannwhitney`" in mensagem


class TestKruskalWallisNoBanco:
    @pytest.mark.parametrize(
        ("variavel", "qui", "gl", "p", "grupos"), KRUSKAL_DO_R, ids=[v for v, *_ in KRUSKAL_DO_R]
    )
    def test_o_kruskal_test_do_r(self, variavel, qui, gl, p, grupos):
        comparacao = _grupos(((variavel, "escolaridade", "kruskal"),))
        comparada = comparacao.variaveis[0]
        resultado = comparada.resultado
        assert resultado.metodo == KRUSKAL_WALLIS
        assert resultado.estatistica == pytest.approx(qui, rel=1e-12)
        assert resultado.gl == (gl,)
        assert resultado.p == pytest.approx(p, rel=1e-12)
        assert [g.n for g in comparada.grupos] == [grupo[0] for grupo in grupos]
        _, *linhas = comparacao.tabela_de(K_GRUPOS).linhas
        assert [linha[3] for linha in linhas] == [
            _quartis_conferidos(g.resumo, *do_r[1:])
            for g, do_r in zip(comparada.grupos, grupos, strict=True)
        ]

    def test_o_kruskal_escrito_contra_a_regra(self):
        """
        A frase da escolha, e um aviso só — o de contra a regra: os avisos do intervalo
        são do Wilcoxon e do Mann-Whitney, e um teste sem intervalo não é um intervalo
        que falta.
        """
        comparacao = _grupos((("nota", "escolaridade", "kruskal"),))
        comparada = comparacao.variaveis[0]
        assert comparada.escolha.contra_a_regra
        assert (
            "Kruskal-Wallis escrito na ficha (χ² = 10,59; 2 gl), contra a regra — ela "
            "escolheria ANOVA de Welch: o Shapiro-Wilk não rejeita a normal em nenhum dos 3 "
            "grupos"
        ) in comparada.justificativa
        (aviso,) = comparacao.avisos
        assert aviso.startswith(
            "`nota` por `escolaridade`: Kruskal-Wallis escrito na ficha, contra a regra"
        )

    def test_um_grupo_de_um_valor_vai_para_o_kruskal_wallis(self):
        """
        A normalidade não se verifica no grupo de um valor, e o Kruskal-Wallis, como no
        R, aceita o grupo — `kruskal.test(list(30, c(24.1, 27.3, 22.8), c(26.5, 29.9,
        31.2)))`: qui-quadrado = 3,286, 2 gl, p = 0,1934. A ANOVA de Welch, a paramétrica
        da regra, pediria dois valores em cada grupo.
        """
        quadro, linhas = _tres([30.0], [24.1, 27.3, 22.8], [26.5, 29.9, 31.2])
        comparada = _grupos((("y", "g"),), quadro, linhas).variaveis[0]
        assert comparada.metodo == KRUSKAL_WALLIS
        assert comparada.resultado.estatistica == pytest.approx(3.2857142857142847, rel=1e-12)
        assert comparada.resultado.p == pytest.approx(0.19342660460039263, rel=1e-12)


class TestFriedmanNoBanco:
    @pytest.mark.parametrize(
        ("base", "n", "qui", "gl", "p", "medidas"),
        FRIEDMAN_DO_R,
        ids=[base for base, *_ in FRIEDMAN_DO_R],
    )
    def test_o_friedman_test_do_r(self, base, n, qui, gl, p, medidas):
        """
        Com `metodo: friedman`, o Friedman sai nas três bases — e no `peso`, em que a
        ANOVA não pode, ele dá o qui-quadrado mais alto que existe, n(k − 1) = 80.
        """
        nomes = [f"{base}_{j}" for j in range(3)]
        comparacao = _repetidas((("repetidas", nomes, "friedman"),))
        comparada = comparacao.variaveis[0]
        resultado = comparada.resultado
        assert resultado.metodo == FRIEDMAN
        assert comparada.validos == n
        assert resultado.estatistica == pytest.approx(qui, rel=1e-12)
        assert resultado.gl == (gl,)
        assert resultado.p == pytest.approx(p, rel=1e-12)
        assert [linha[2] for linha in comparacao.tabela_de(REPETIDAS).linhas] == [
            _quartis_conferidos(medida.resumo, *do_r)
            for medida, do_r in zip(comparada.grupos, medidas, strict=True)
        ]

    def test_a_anova_que_nao_pode_ensina_o_friedman(self):
        """
        O peso é normal em cada medida, e a regra escolhe a ANOVA — que não pode: cada
        caso ganha o mesmo quilo. O aviso ensina a escrever o Friedman.
        """
        comparacao = _repetidas((("repetidas", ["peso_0", "peso_1", "peso_2"]),))
        comparada = comparacao.variaveis[0]
        assert comparada.celula_do_teste == "não testado: as medidas não variam dentro dos casos"
        assert any(
            "O Friedman, que olha só a ordem das medidas dentro de cada caso, roda com o "
            "método escrito no item: `{repetidas: [peso_0, peso_1, peso_2], metodo: "
            "friedman}`." in aviso
            for aviso in comparacao.avisos
        )

    def test_cada_caso_com_o_mesmo_valor_em_todas_as_medidas(self):
        """Não há o que ordenar: o qui-quadrado é 0/0, o R devolve `NaN`, e aqui, sem teste."""
        quadro = bancos.para_comparar_repetidas().assign(
            pas_1=lambda q: q["pas_0"], pas_2=lambda q: q["pas_0"]
        )
        comparacao = _repetidas((("repetidas", ["pas_0", "pas_1", "pas_2"], "friedman"),), quadro)
        comparada = comparacao.variaveis[0]
        assert comparada.celula_do_teste == (
            "não testado: cada caso tem o mesmo valor em todas as medidas"
        )
        assert any("o qui-quadrado de Friedman é 0/0" in aviso for aviso in comparacao.avisos)

    def test_o_friedman_escrito_contra_a_regra(self):
        """A frase da escolha, e só o aviso de contra a regra — como no Kruskal-Wallis."""
        comparacao = _repetidas((("repetidas", ["pas_0", "pas_1", "pas_2"], "friedman"),))
        comparada = comparacao.variaveis[0]
        assert comparada.escolha.contra_a_regra
        assert (
            "Friedman escrito na ficha (χ² = 40,01; 2 gl), contra a regra — ela escolheria "
            "ANOVA de medidas repetidas"
        ) in comparada.justificativa
        (aviso,) = comparacao.avisos
        assert "Friedman escrito na ficha, contra a regra" in aviso


class TestPostosNoManifestoENoDocumento:
    def test_os_detalhes_do_mann_whitney(self):
        comparacao = _grupos((("renda", "sexo"),))
        (renda,) = montar_manifesto(comparacao, DICIONARIO_DOS_GRUPOS).itens[0].detalhes[
            DOIS_GRUPOS
        ]
        assert (renda["teste"], renda["teste_da_regra"], renda["exato"]) == (
            MANN_WHITNEY,
            MANN_WHITNEY,
            True,
        )
        assert renda["estatistica"] == {"nome": "W", "valor": 331.0, "gl": []}
        assert renda["estimativa"] == {"nome": "diferença de locação", "valor": -921.57}
        assert renda["ic_95"] == [-2414.48, 406.97]
        assert renda["calculo_do_p"] == "exato"
        # A mediana e os quartis de cada grupo — os da célula —, que a descritiva não
        # tem, ao lado da média e do desvio, que a célula não mostra.
        feminino = renda["por_grupo"][0]
        assert (feminino["mediana"], feminino["q1"], feminino["q3"]) == (
            2982.625,
            1774.6175,
            5013.5425,
        )
        assert (feminino["media"], feminino["desvio"]) == (
            pytest.approx(comparacao.variaveis[0].grupos[0].resumo["media"], abs=1e-6),
            pytest.approx(comparacao.variaveis[0].grupos[0].resumo["desvio"], abs=1e-6),
        )

    def test_a_mediana_da_uma_amostra_e_das_medidas_no_manifesto(self):
        quadro, linhas = _uma("a", [1.2, 3.4, 2.2, 5.1])
        comparacao = _comparar(quadro, linhas, (("a", 0, "wilcoxon"),))
        (detalhe,) = montar_manifesto(comparacao, linhas).itens[0].detalhes[UMA_AMOSTRA]
        assert (detalhe["mediana"], detalhe["q1"], detalhe["q3"]) == (2.8, 1.95, 3.825)
        comparacao = _repetidas((("repetidas", ["dor_0", "dor_1", "dor_2"]),))
        (dor,) = montar_manifesto(comparacao, DICIONARIO_DAS_REPETIDAS).itens[0].detalhes[
            REPETIDAS
        ]
        assert [(m["mediana"], m["q1"], m["q3"]) for m in dor["por_medida"]] == [
            (1, 0, 1.25), (0, 0, 1), (0, 0, 1),
        ]

    def test_o_relatorio_le_as_tabelas_dos_postos(self, projeto_com_rodada):
        """
        Pelo disco, com o banco dos grupos: o Mann-Whitney e o Kruskal-Wallis chegam à
        seção com a mediana nas células e o cabeçalho que diz isso, sem alerta — e o
        `relatorio.py` não sabe que eles existem.
        """
        from flatcap.relatorio import preparar_relatorio

        raiz = projeto_com_rodada(bancos.para_comparar_grupos())
        acrescentar_a_ficha(
            raiz, "comparacao:\n  - [renda, sexo]\n  - [renda, escolaridade]\n"
        )
        executar_comparacao(preparar_comparacao(raiz, agora=AGORA))
        relatorio = preparar_relatorio(raiz, agora=AGORA).relatorio
        assert relatorio.alertas == ()
        secao = next(s for s in relatorio.secoes if s.rotulo == "Comparação")
        dois, k = secao.tabelas
        assert (dois.colunas[3], k.colunas[3]) == (COLUNA_DA_MEDIANA, COLUNA_DA_MEDIANA)
        assert dois.linhas[0][5] == MANN_WHITNEY
        assert dois.linhas[1][3] == "2982,62 [1774,62 a 5013,54]"
        assert k.linhas[0][4] == KRUSKAL_WALLIS


# ── Entre dois grupos: o manifesto ──────────────────────────────────────────


class TestManifestoEntreGrupos:
    def test_os_detalhes_de_cada_grupo(self):
        comparacao = _grupos((("imc", "sexo", "student"), ("imc", 25)))
        detalhes = montar_manifesto(comparacao, DICIONARIO_DOS_GRUPOS).itens[0].detalhes
        (imc,) = detalhes[DOIS_GRUPOS]
        assert (imc["variavel"], imc["grupos"], imc["n"], imc["faltantes"]) == (
            "imc",
            "sexo",
            57,
            3,
        )
        assert [g["grupo"] for g in imc["por_grupo"]] == ["Feminino", "Masculino"]
        assert imc["por_grupo"][0]["shapiro"]["rejeita"] is False
        assert imc["estimativa"] == {"nome": "diferença de médias", "valor": -2.321182}
        assert (imc["teste"], imc["teste_da_regra"], imc["escrito_na_ficha"]) == (
            "t de Student",
            T_DE_WELCH,
            True,
        )
        assert len(detalhes[UMA_AMOSTRA]) == 1

    def test_um_artefato_por_tabela_e_as_colunas_de_grupo(self):
        comparacao = _grupos((("imc", 25), ("pas", "sexo")))
        (item,) = montar_manifesto(comparacao, DICIONARIO_DOS_GRUPOS).itens
        assert [a.arquivo for a in item.artefatos] == [ARQUIVO_TABELA, ARQUIVO_DOIS_GRUPOS]
        assert item.colunas == ("imc", "pas", "sexo")

    def test_a_variavel_de_grupo_nao_esta_fora(self):
        manifesto = montar_manifesto(_grupos((("imc", "sexo"),)), DICIONARIO_DOS_GRUPOS)
        assert {f["variavel"] for f in manifesto.fora} == {
            "renda", "pas", "nota", "escolaridade", "unico"
        }

    def test_as_regras_de_dois_grupos(self):
        regras = montar_manifesto(_grupos((("imc", "sexo"),)), DICIONARIO_DOS_GRUPOS).regras
        assert regras["escolha_do_teste"][DOIS_GRUPOS] == (
            "t de Welch se o Shapiro-Wilk não rejeita a normal (p ≥ 0.05) em nenhum dos dois "
            "grupos; senão Mann-Whitney. O t de Student roda quando está escrito no item; o "
            "método escrito na ficha tem precedência."
        )
        assert "var.equal = TRUE" in regras["t_de_student"]
        assert "Welch-Satterthwaite" in regras["t_de_welch"]
        assert "não é a diferença das medianas" in regras["mann_whitney"]
        assert "kruskal.test do R" in regras["kruskal_wallis"]
        assert "friedman.test do R" in regras["friedman"]
        assert regras["minimo"] == {
            "t_uma_amostra": 2,
            "t_de_welch": "2 em cada grupo",
            "t_de_student": 3,
            "anova": "2 em cada grupo",
            "anova_de_welch": "2 em cada grupo",
            "anova_de_medidas_repetidas": "3 medidas e 2 casos com todas elas",
            "wilcoxon": 2,
            "mann_whitney": "1 em cada grupo",
            "kruskal_wallis": "1 em cada grupo",
            "friedman": "3 medidas e 2 casos com todas elas",
        }


# ── No disco ────────────────────────────────────────────────────────────────


@pytest.fixture
def projeto_para_comparar(projeto_com_rodada):
    """
    Projeto com banco, dicionário, uma rodada de descritiva e a lista na ficha.
    """

    def montar(bloco: str = BLOCO):
        raiz = projeto_com_rodada()
        acrescentar_a_ficha(raiz, bloco)
        return raiz

    return montar


class TestEscrita:
    def test_preparar_nao_toca_no_disco(self, projeto_para_comparar):
        raiz = projeto_para_comparar()
        antes = len(linhas_do_historico(raiz))
        preparar_comparacao(raiz, agora=AGORA)
        assert not (raiz / PASTA_ANALISES / PASTA_COMPARACAO).exists()
        assert len(linhas_do_historico(raiz)) == antes

    def test_executar_escreve_a_tabela_e_o_manifesto(self, projeto_para_comparar):
        raiz = projeto_para_comparar()
        executar_comparacao(preparar_comparacao(raiz, agora=AGORA))
        pasta = raiz / PASTA_ANALISES / PASTA_COMPARACAO
        assert sorted(p.name for p in pasta.iterdir()) == [ARQUIVO_MANIFESTO, ARQUIVO_TABELA]
        manifesto = ler_manifesto(pasta)
        assert manifesto.analise == ANALISE_COMPARACAO
        assert manifesto.itens[0].colunas == ("imc",)

    def test_escreve_uma_linha_no_historico(self, projeto_para_comparar):
        raiz = projeto_para_comparar()
        antes = len(linhas_do_historico(raiz))
        executar_comparacao(preparar_comparacao(raiz, agora=AGORA))
        linhas = linhas_do_historico(raiz)
        assert len(linhas) == antes + 1
        assert f"flatcap comparacao {RECORD_ID}" in linhas[-1]
        assert "1 com o t de Student" in linhas[-1]

    def test_regerar_arquiva_a_rodada_anterior(self, projeto_para_comparar):
        raiz = projeto_para_comparar()
        executar_comparacao(preparar_comparacao(raiz, agora=AGORA))
        resultado = executar_comparacao(
            preparar_comparacao(raiz, agora=AGORA.replace(hour=16))
        )
        arquivada = raiz / PASTA_ANTIGAS / "comparacao_2026-09-09_1630"
        assert resultado.arquivado == (raiz / PASTA_ANALISES / PASTA_COMPARACAO, arquivada)
        assert (arquivada / ARQUIVO_MANIFESTO).is_file()

    def test_a_falha_no_meio_devolve_a_rodada_anterior(
        self, projeto_para_comparar, monkeypatch
    ):
        """
        O manifesto é o último arquivo: uma falha nele desfaz a tabela nova e devolve a
        rodada arquivada ao lugar, e a exceção continua subindo inteira.
        """
        import flatcap.comparacao as modulo

        raiz = projeto_para_comparar()
        executar_comparacao(preparar_comparacao(raiz, agora=AGORA))
        pasta = raiz / PASTA_ANALISES / PASTA_COMPARACAO
        antes = {p.name: p.read_bytes() for p in pasta.iterdir()}

        original = modulo.escrever_atomico

        def falha_no_manifesto(caminho, texto):
            if caminho.name == ARQUIVO_MANIFESTO:
                raise RuntimeError("o disco encheu")
            return original(caminho, texto)

        monkeypatch.setattr(modulo, "escrever_atomico", falha_no_manifesto)
        plano = preparar_comparacao(raiz, agora=AGORA.replace(hour=16))
        with pytest.raises(RuntimeError, match="o disco encheu"):
            executar_comparacao(plano)

        assert {p.name: p.read_bytes() for p in pasta.iterdir()} == antes
        assert not list((raiz / PASTA_ANTIGAS).glob("comparacao_*"))

    def test_a_lista_mal_escrita_recusa_antes_de_abrir_o_banco(
        self, projeto_para_comparar, monkeypatch
    ):
        raiz = projeto_para_comparar("comparacao:\n  - [imc, 24,9]\n")

        def nao_abra(*_a, **_k):
            raise AssertionError("o banco foi aberto antes de a lista ser conferida")

        monkeypatch.setattr("flatcap.comparacao.abrir", nao_abra)
        with pytest.raises(ItemInvalidoError):
            preparar_comparacao(raiz, agora=AGORA)

    def test_com_grupos_escreve_as_duas_tabelas(self, projeto_para_comparar):
        raiz = projeto_para_comparar("comparacao:\n  - [imc, 25]\n  - [imc, sexo, student]\n")
        executar_comparacao(preparar_comparacao(raiz, agora=AGORA))
        pasta = raiz / PASTA_ANALISES / PASTA_COMPARACAO
        assert sorted(p.name for p in pasta.iterdir()) == [
            ARQUIVO_DOIS_GRUPOS,
            ARQUIVO_MANIFESTO,
            ARQUIVO_TABELA,
        ]
        manifesto = ler_manifesto(pasta)
        assert manifesto.itens[0].colunas == ("imc", "sexo")
        assert len(manifesto.itens[0].artefatos) == 2

    def test_a_simulacao_e_a_execucao_dao_o_mesmo_arquivo(self, projeto_para_comparar):
        raiz = projeto_para_comparar()
        plano = preparar_comparacao(raiz, agora=AGORA)
        executar_comparacao(plano)
        escrito = (raiz / PASTA_ANALISES / PASTA_COMPARACAO / ARQUIVO_TABELA).read_text(
            encoding="utf-8"
        )
        assert escrito == plano.comparacao.tabela_de(UMA_AMOSTRA).texto()


# ── O relatório, que não muda uma linha ─────────────────────────────────────


class TestRelatorio:
    def test_o_relatorio_encontra_a_rodada_sem_nenhum_alerta(self, projeto_para_comparar):
        from flatcap.relatorio import preparar_relatorio

        raiz = projeto_para_comparar()
        executar_comparacao(preparar_comparacao(raiz, agora=AGORA))
        relatorio = preparar_relatorio(raiz, agora=AGORA).relatorio

        assert relatorio.analises == ("descritiva", "comparacao")
        assert relatorio.alertas == ()
        secao = next(s for s in relatorio.secoes if s.rotulo == "Comparação")
        assert secao.tabelas[0].colunas[2:4] == ("média (DP)", "IC 95% da média")
        assert secao.tabelas[0].linhas[0][:2] == ("imc", "24")
        assert secao.tabelas[0].linhas[0][5] == T_DE_STUDENT
        assert secao.figuras == ()

    def test_a_media_do_documento_e_a_da_tabela_de_resumo(self, projeto_para_comparar):
        """
        Pelo disco, como o relatório as lê: a média na seção da comparação é a mesma da
        tabela de resumo da seção `imc` — as duas saem do mesmo `.csv`-irmão.
        """
        from flatcap.relatorio import preparar_relatorio

        raiz = projeto_para_comparar()
        executar_comparacao(preparar_comparacao(raiz, agora=AGORA))
        relatorio = preparar_relatorio(raiz, agora=AGORA).relatorio
        resumo = next(
            t for s in relatorio.secoes if s.variavel == "imc" for t in s.tabelas
            if t.especie == "resumo"
        )
        celulas = dict(resumo.linhas)
        comparacao = next(s for s in relatorio.secoes if s.rotulo == "Comparação")
        assert comparacao.tabelas[0].linhas[0][2] == (
            f"{celulas['média']} ({celulas['desvio padrão']})"
        )

    def test_as_duas_tabelas_na_mesma_secao(self, projeto_para_comparar):
        """
        A seção Comparação é uma só, com uma tabela por delineamento, e o relatório
        não muda uma linha para ler a segunda.
        """
        from flatcap.relatorio import preparar_relatorio

        raiz = projeto_para_comparar("comparacao:\n  - [imc, 25]\n  - [imc, sexo, student]\n")
        executar_comparacao(preparar_comparacao(raiz, agora=AGORA))
        relatorio = preparar_relatorio(raiz, agora=AGORA).relatorio
        assert relatorio.alertas == ()
        secao = next(s for s in relatorio.secoes if s.rotulo == "Comparação")
        assert [t.especie for t in secao.tabelas] == [UMA_AMOSTRA, DOIS_GRUPOS]
        grupos = secao.tabelas[1]
        assert grupos.colunas[1] == "grupo"
        assert [linha[1] for linha in grupos.linhas] == ["sexo", "Feminino", "Masculino"]
        assert grupos.linhas[0][5] == "t de Student"

    def test_as_medidas_repetidas_no_documento(self, projeto_com_rodada):
        """Pelo disco, com o banco das repetidas: a tabela chega à seção, sem alerta."""
        from flatcap.relatorio import preparar_relatorio

        raiz = projeto_com_rodada(bancos.para_comparar_repetidas())
        acrescentar_a_ficha(raiz, "comparacao:\n  - repetidas: [pas_0, pas_1, pas_2]\n")
        executar_comparacao(preparar_comparacao(raiz, agora=AGORA))
        pasta = raiz / PASTA_ANALISES / PASTA_COMPARACAO
        assert sorted(p.name for p in pasta.iterdir()) == [ARQUIVO_MANIFESTO, ARQUIVO_REPETIDAS]
        relatorio = preparar_relatorio(raiz, agora=AGORA).relatorio
        assert relatorio.alertas == ()
        secao = next(s for s in relatorio.secoes if s.rotulo == "Comparação")
        (tabela,) = secao.tabelas
        assert [linha[0] for linha in tabela.linhas] == ["pas_0", "pas_1", "pas_2"]
        assert tabela.linhas[0][3] == ANOVA_DE_MEDIDAS_REPETIDAS

    def test_sem_ficha_mandando_vem_no_fim(self, projeto_para_comparar):
        from flatcap.normalidade import executar_normalidade, preparar_normalidade
        from flatcap.relatorio import preparar_relatorio

        raiz = projeto_para_comparar()
        executar_comparacao(preparar_comparacao(raiz, agora=AGORA))
        executar_normalidade(preparar_normalidade(raiz, com_graficos=False, agora=AGORA))
        relatorio = preparar_relatorio(raiz, agora=AGORA).relatorio
        assert relatorio.analises == ("descritiva", "normalidade", "comparacao")

    def test_a_ficha_manda_na_ordem(self, projeto_para_comparar):
        from flatcap.relatorio import preparar_relatorio

        raiz = projeto_para_comparar()
        ficha = raiz / ARQUIVO_PROJETO
        ficha.write_text(
            ficha.read_text(encoding="utf-8").replace(
                "analises: []", "analises:\n  - comparacao\n  - descritiva"
            ),
            encoding="utf-8",
        )
        executar_comparacao(preparar_comparacao(raiz, agora=AGORA))
        relatorio = preparar_relatorio(raiz, agora=AGORA).relatorio
        assert relatorio.analises == ("comparacao", "descritiva")
        assert relatorio.secoes[0].rotulo == "Comparação"


def test_o_que_so_se_ve_abrindo_o_documento():
    """
    Lembrete, não teste. O que nenhuma asserção daqui pega: a coluna `teste` partida
    em quatro linhas numa linha sem teste, a `média (DP)` de uma renda com cinco
    algarismos espremida, a tabela atravessando a quebra de página. Antes de mesclar,
    gerar o relatório de um projeto com uma linha testada e uma sem teste e olhar.
    """
    assert True
