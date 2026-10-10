# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Os testes do `hipoteses.py` — a aritmética, sem projeto, banco nem ficha.

**Nenhum número daqui é conferido contra o próprio módulo.** As referências são três,
e independentes dele:

* o **R 4.3.3**: `t.test(x, mu = mu)`, `t.test(x, y, var.equal = TRUE)`,
  `t.test(x, y)`, `oneway.test(y ~ g, var.equal = TRUE)` e `oneway.test(y ~ g)` rodados
  sobre os mesmos números, com o resultado copiado para `REFERENCIAS_DO_R`,
  `REFERENCIAS_DO_R_STUDENT`, `REFERENCIAS_DO_R_WELCH`, `REFERENCIAS_DO_R_ANOVA` e
  `REFERENCIAS_DO_R_ANOVA_DE_WELCH` — e as medidas repetidas, com o F do
  `aov(y ~ t + Error(id / t))` e o ε de Greenhouse-Geisser do `anova.mlm`, em
  `REFERENCIAS_DO_R_REPETIDAS` — a estatística, os graus de
  liberdade, o p, os dois limites do intervalo e a estimativa, quando há. O
  `PlantGrowth` e o `InsectSprays` são os bancos dos exemplos da documentação do R.
  Os testes de postos, com `wilcox.test(x, mu = mu, conf.int = TRUE)`,
  `wilcox.test(x, y, conf.int = TRUE)`, `kruskal.test` e `friedman.test`, em
  `REFERENCIAS_DO_R_WILCOXON`, `REFERENCIAS_DO_R_MANN_WHITNEY`,
  `REFERENCIAS_DO_R_KRUSKAL` e `REFERENCIAS_DO_R_FRIEDMAN`, com dezessete algarismos —
  o intervalo e a estimativa inclusive, e o nível do intervalo quando o R o baixa;
* o **exemplo da documentação do `t.test`**: os dados do sono de Student (1908), o
  `sleep` do R. O t pareado que a documentação imprime — t = 4,0621, 9 gl,
  p = 0,002833 — é o t de uma amostra sobre as diferenças, que é a razão de o motor
  morar fora da análise. E os exemplos das documentações do `wilcox.test`, do
  `kruskal.test` e do `friedman.test`, de Hollander e Wolfe (1973);
* as **fórmulas**, escritas aqui de novo com a biblioteca padrão: a média, o desvio e
  o erro-padrão pelo `statistics`, e só o quantil e a cauda da t pelo `scipy`. E a
  **força bruta**: as distribuições exatas dos postos contadas permutação por
  permutação, e a estimativa de Hodges-Lehmann pela definição;
* o **`scipy`**, como conferência: o `wilcoxon` e o `mannwhitneyu` dão o p do R quando
  recebem a escolha do R, e o `friedmanchisquare` dá o mesmo qui-quadrado.
"""

from __future__ import annotations

import itertools
import math
import statistics
import sys
from dataclasses import FrozenInstanceError

import pytest
from scipy import stats

import flatcap.hipoteses as hipoteses
from flatcap.hipoteses import (
    ANOVA,
    ANOVA_DE_MEDIDAS_REPETIDAS,
    ANOVA_DE_WELCH,
    CONFIANCA,
    FRIEDMAN,
    KRUSKAL_WALLIS,
    LIMITE_DO_EXATO,
    MANN_WHITNEY,
    MINIMO_STUDENT,
    MINIMO_T,
    T_DE_STUDENT,
    T_DE_WELCH,
    WILCOXON,
    Resultado,
    anova_de_medidas_repetidas,
    anova_de_um_fator,
    anova_de_welch,
    friedman,
    kruskal_wallis,
    mann_whitney,
    medidas_iguais_em_cada_caso,
    sem_variacao,
    sem_variacao_em_duas,
    sem_variacao_entre_medidas,
    sem_variacao_nos_grupos,
    t_de_student,
    t_de_welch,
    t_uma_amostra,
    wilcoxon_uma_amostra,
)

# O `sleep` do R: o sono a mais, em horas, de dez pacientes com dois soníferos.
SONO_1 = [0.7, -1.6, -0.2, -1.2, -0.1, 3.4, 3.7, 0.8, 0.0, 2.0]
SONO_2 = [1.9, 0.8, 1.1, 0.1, -0.1, 4.4, 5.5, 1.6, 4.6, 3.4]


def _dados(caso: str) -> list[float]:
    """
    Os vetores de `REFERENCIAS_DO_R`, gerados aqui como foram gerados no R.

    Nada sorteado: o `grande` e o `quarenta` são permutações de uma grade fixa —
    `(7919 i) mod 1000` e `(37 i) mod 41` —, que o R e o Python calculam em inteiros e
    produzem idênticas, casa por casa.
    """
    if caso == "sleep_dif":
        return [b - a for a, b in zip(SONO_1, SONO_2, strict=True)]
    if caso == "sleep_extra":
        return SONO_1 + SONO_2
    if caso == "grande":
        return [100 + ((i * 7919) % 1000) / 10 for i in range(1000)]
    if caso == "quarenta":
        return [50 + ((i * 37) % 41) / 4 for i in range(40)]
    fixos = {
        "dois": [24.0, 27.0],
        "abaixo": [-3.1, -2.2, -4.0, -1.5, -2.8, -3.3],
        "no_centro": [1.0, 2.0, 3.0, 4.0, 5.0],
        "imc15": [
            22.5, 27.1, 24.3, 31.2, 19.8, 28.4, 26.0, 23.7,
            30.1, 21.9, 25.5, 29.3, 22.1, 26.8, 24.9,
        ],
    }
    return fixos[caso]


# `t.test(x, mu = mu)` no R 4.3.3, sobre os números de `_dados(caso)`:
#
#     (caso, mu, t, gl, p, limite inferior, limite superior, média)
#
# Os casos cobrem n = 2 (o menor que o R aceita), a média abaixo da referência, a
# média exatamente na referência (t = 0, p = 1), n = 1000, e o mesmo vetor contra
# duas referências — o intervalo, que é da média, não muda.
REFERENCIAS_DO_R = [
    ("sleep_dif", 0, 4.0621276833820366, 9, 0.0028328901973842702,
     0.70011423672301754, 2.4598857632769824, 1.5800000000000001),
    ("sleep_extra", 0, 3.4129649952701091, 19, 0.0029176204041541161,
     0.59558449961960391, 2.484415500380396, 1.54),
    ("sleep_extra", 1, 1.1967539593804279, 19, 0.2461224180402265,
     0.59558449961960402, 2.484415500380396, 1.54),
    ("dois", 25, 0.33333333333333331, 1, 0.79516723530086653,
     6.4406928957379606, 44.559307104262047, 25.5),
    ("abaixo", 0, -7.8848095746652707, 5, 0.00052755903264713763,
     -3.7349478377985625, -1.8983854955347697, -2.8166666666666664),
    ("no_centro", 3, 0, 4, 1, 1.0367568385224428, 4.963243161477557, 3),
    ("imc15", 25, 0.67396735393805574, 14, 0.51130721720700434,
     23.748797331867163, 27.397869334799505, 25.573333333333334),
    ("grande", 148, 2.1350507156602876, 999, 0.032999634644297116,
     148.15774006858811, 151.74225993141187, 149.94999999999999),
    ("quarenta", 55, 0.21346522382300015, 39, 0.83207613965549476,
     54.152449441734852, 56.047550558265151, 55.100000000000001),
]


# Os pares de `REFERENCIAS_DO_R_STUDENT`. O `sleep` é o exemplo da documentação do
# `t.test` como dois grupos, e o `um_so` é o caso de canto que o R aceita no de
# Student: um grupo de um valor, com a variância combinada toda do outro.
DUAS_AMOSTRAS: dict[str, tuple[list[float], list[float]]] = {
    "grupos": (
        [24.1, 27.3, 22.8, 30.2, 25.5, 26.9, 23.4, 28.8, 25.0, 27.7],
        [26.5, 29.9, 31.2, 24.8, 33.0, 28.1, 30.4, 27.6, 35.2, 26.3, 29.8, 32.7],
    ),
    "sleep": (SONO_1, SONO_2),
    "um_so": (
        [30.0],
        [26.5, 29.9, 31.2, 24.8, 33.0, 28.1, 30.4, 27.6, 35.2, 26.3, 29.8, 32.7],
    ),
    "mesma_media": ([1.0, 2.0, 3.0], [1.5, 2.5]),
    "um_constante": ([5.0, 5.0, 5.0], [4.0, 6.0, 7.0]),
    "desiguais": (
        [10.2, 11.5, 9.8, 12.1],
        [20.5, 35.2, 18.9, 42.3, 25.6, 30.1, 22.2, 38.8],
    ),
}

# `t.test(x, y, var.equal = TRUE)` no R 4.3.3:
#
#     (caso, t, gl, p, limite inferior, limite superior, diferença das médias)
REFERENCIAS_DO_R_STUDENT = [
    ("grupos", -2.8701134295652397, 20, 0.0094640119779283785,
     -5.9660518755334566, -0.94394812446654075, -3.4549999999999983),
    ("sleep", -1.8608134674868528, 18, 0.079186714215938175,
     -3.3638740322875984, 0.20387403228759859, -1.5800000000000001),
    ("um_so", 0.1162591710745048, 11, 0.90954249918663643,
     -6.7243920514487918, 7.4743920514487909, 0.375),
    ("mesma_media", 0, 3, 1, -2.6520385877364232, 2.6520385877364232, 0),
    ("um_constante", -0.75592894601845484, 4, 0.4917670010221688,
     -3.1152610923919757, 1.7819277590586422, -0.66666666666666696),
    ("desiguais", -4.0375369892520725, 10, 0.0023705935415861629,
     -28.398964071386029, -8.2010359286139671, -18.299999999999997),
]


# `t.test(x, y)` no R 4.3.3 — o de Welch, o padrão —, sobre os mesmos pares; o
# `um_so` fica de fora, porque o R recusa (`not enough 'x' observations`):
#
#     (caso, t, gl, p, limite inferior, limite superior, diferença das médias)
REFERENCIAS_DO_R_WELCH = [
    ("grupos", -2.9378999464179807, 19.933726537810411, 0.0081540304894174315,
     -5.908637029243204, -1.0013629707567926, -3.4549999999999983),
    ("sleep", -1.8608134674868531, 17.776473516178498, 0.079394140187358173,
     -3.3654832307117104, 0.20548323071171018, -1.5800000000000001),
    ("mesma_media", 0, 2.8823529411764697, 1, -2.4877337982053822, 2.4877337982053822, 0),
    ("um_constante", -0.75592894601845484, 2, 0.5285954792089681,
     -4.4612497002634264, 3.1279163669300925, -0.66666666666666696),
    ("desiguais", -5.7835953376020939, 7.4108290451050332, 0.00054793544032704473,
     -25.698692720456485, -10.901307279543509, -18.299999999999997),
]


# Os grupos de `REFERENCIAS_DO_R_ANOVA`: o `PlantGrowth` e o `InsectSprays` do R,
# copiados, e três casos à mão — um grupo que não varia, e médias iguais.
VARIOS_GRUPOS: dict[str, list[list[float]]] = {
    "plantas": [
        [4.17, 5.58, 5.18, 6.11, 4.5, 4.61, 5.17, 4.53, 5.33, 5.14],
        [4.81, 4.17, 4.41, 3.59, 5.87, 3.83, 6.03, 4.89, 4.32, 4.69],
        [6.31, 5.12, 5.54, 5.5, 5.37, 5.29, 4.92, 6.15, 5.8, 5.26],
    ],
    "insetos": [
        [10, 7, 20, 14, 14, 12, 10, 23, 17, 20, 14, 13],
        [11, 17, 21, 11, 16, 14, 17, 17, 19, 21, 7, 13],
        [0, 1, 7, 2, 3, 1, 2, 1, 3, 0, 1, 4],
        [3, 5, 12, 6, 4, 3, 5, 5, 5, 5, 2, 4],
        [3, 5, 3, 5, 3, 6, 1, 1, 3, 2, 6, 4],
        [11, 9, 15, 22, 15, 16, 13, 10, 26, 26, 24, 13],
    ],
    "tres": [
        DUAS_AMOSTRAS["grupos"][0],
        DUAS_AMOSTRAS["grupos"][1],
        [28.2, 31.5, 30.0, 33.3, 29.1, 34.6, 27.9, 32.2],
    ],
    "um_constante": [[5.0, 5.0, 5.0], [4.0, 6.0, 7.0], [8.0, 9.0, 11.0]],
    "medias_iguais": [[1.0, 2.0, 3.0], [0.0, 2.0, 4.0], [1.5, 2.0, 2.5]],
}

# `oneway.test(y ~ g, var.equal = TRUE)` no R 4.3.3:
#
#     (caso, F, gl do numerador, gl do denominador, p)
REFERENCIAS_DO_R_ANOVA = [
    ("plantas", 4.8460878623801369, 2, 27, 0.015909958325622912),
    ("insetos", 34.702282055491708, 5, 66, 3.1825837261451404e-17),
    ("tres", 7.493179208968324, 2, 27, 0.0025789920123191904),
    ("um_constante", 10.500000000000002, 2, 6, 0.010973936899862832),
    ("medias_iguais", 0, 2, 6, 1),
]

# `oneway.test(y ~ g)` no R 4.3.3 — a ANOVA de Welch, o padrão —, sobre os mesmos
# grupos; o `um_constante` fica de fora, porque o R devolve `NaN`:
#
#     (caso, F, gl do numerador, gl do denominador, p)
REFERENCIAS_DO_R_ANOVA_DE_WELCH = [
    ("plantas", 5.1809724081131892, 2, 17.128418616644129, 0.017392821490170001),
    ("insetos", 36.065443893577253, 5, 30.04256050876738, 7.9993794556733478e-12),
    ("tres", 8.7738753291135048, 2, 17.341354929364982, 0.002330898076787043),
    ("medias_iguais", 0, 2, 3.2941176470588234, 1),
]


# As medidas de `REFERENCIAS_DO_R_REPETIDAS`, uma lista por medida, os casos na mesma
# ordem. O `vinte` é gerado como no R: `base = 50 + (7 i mod 20)` e três medidas a mais,
# cada uma com o seu passo.
def _medidas(caso: str) -> list[list[float]]:
    pas = [
        [132, 140, 128, 150, 138, 126, 145, 133, 129, 141],
        [128, 135, 127, 142, 131, 124, 139, 130, 126, 133],
        [125, 136, 121, 139, 128, 125, 132, 124, 123, 130],
    ]
    quarta = [120, 131, 119, 137, 127, 120, 130, 120, 121, 126]
    if caso == "pas":
        return pas
    if caso == "quatro":
        return [*pas, quarta]
    if caso == "dois_casos":
        return [medida[:2] for medida in pas]
    if caso == "tres_casos_quatro_medidas":
        return [medida[:3] for medida in (*pas, quarta)]
    base = [50 + (i * 7) % 20 for i in range(20)]
    return [
        base,
        [b + 2 + ((i * 3) % 5) / 2 for i, b in enumerate(base)],
        [b + 3 + ((i * 11) % 7) / 2 for i, b in enumerate(base)],
        [b + 5 + (i * 13) % 9 for i, b in enumerate(base)],
    ]


# O F do `aov(y ~ t + Error(id / t))`, o ε de Greenhouse-Geisser do `anova.mlm`, e o p
# da F com os graus de liberdade multiplicados pelo ε — no R 4.3.3:
#
#     (caso, F, ε, gl do numerador corrigido, p)
#
# O F vem do `aov`, e não do `anova.mlm`: o `anova.mlm` chega a ele por outro caminho, e
# no `pas` erra na décima casa — o do `aov` e o daqui batem com a conta em frações.
REFERENCIAS_DO_R_REPETIDAS = [
    ("pas", 35.438902743142577, 0.8080641757064535, 1.616128351412907,
     5.4960377561965596e-06),
    ("quatro", 61.873563218390821, 0.62401792513726873, 1.8720537754118061,
     2.3709405744829341e-08),
    ("dois_casos", 7.9230769230769331, 0.5, 1.0, 0.21731524321988152),
    ("tres_casos_quatro_medidas", 20.774193548386979, 0.48461926374180081,
     1.4538577912254025, 0.019901211578070056),
    ("vinte", 130.61587708066605, 0.48050003558028331, 1.4415001067408499,
     2.0847458777942073e-13),
]


# ── Os testes de postos: os dados ────────────────────────────────────────────

# O exemplo da documentação do `wilcox.test`: a escala de depressão de Hamilton antes e
# depois de um tranquilizante, em nove pacientes (Hollander e Wolfe, 1973, p. 29).
DEPRESSAO_X = [1.83, 0.50, 1.62, 2.48, 1.68, 1.88, 1.55, 3.06, 1.30]
DEPRESSAO_Y = [0.878, 0.647, 0.598, 2.05, 1.06, 1.29, 1.06, 3.14, 1.29]


def _irracionais(n: int, inicio: int = 1) -> list[float]:
    """
    Valores sem empate, gerados como no R: a parte fracionária de i vezes a razão áurea,
    vezes dez, com seis casas. A rotação irracional não repete valor — é o que deixa o
    caminho exato aberto até n = 49 e o fecha em 50 só pelo tamanho.
    """
    return [round((i * 0.6180339887498949) % 1 * 10, 6) for i in range(inicio, inicio + n)]


# Os vetores de `REFERENCIAS_DO_R_WILCOXON`, com a referência de cada um. O `sono` tem um
# zero e um empate; o `quarenta`, empates e um valor igual à referência; o `grande`, mil
# valores; o `quarenta_e_nove` e o `cinquenta` são o limite do caminho exato; o `quatro`
# não alcança o intervalo de 95%; os três de empates fazem o R dobrar o α do intervalo
# aproximado até ele caber — uma vez no `trinca`, duas no `empates_poucos`, até passar de
# 1 nos outros dois; o `zero_sem_empate` vai para a aproximação só pelo valor igual à
# referência; e o `no_centro` tem o V no centro da distribuição, onde a cauda dobrada
# passa de 1 e o R corta.
UMA_AMOSTRA_DE_POSTOS: dict[str, tuple[list[float], float]] = {
    "depressao": ([a - b for a, b in zip(DEPRESSAO_X, DEPRESSAO_Y, strict=True)], 0),
    "imc15": (_dados("imc15"), 25),
    "sono": (_dados("sleep_dif"), 0),
    "quarenta": (_dados("quarenta"), 55),
    "grande": (_dados("grande"), 148),
    "quarenta_e_nove": (_irracionais(49), 5),
    "cinquenta": (_irracionais(50), 5),
    "quatro": ([1.2, 3.4, 2.2, 5.1], 0),
    "cinco": ([1.2, 3.4, 2.2, 5.1, -0.7], 0),
    "empates_poucos": ([1.0, 2.0, 2.0, 3.0], 0),
    "empates_tres": ([1.0, 2.0, 2.0], 0),
    "zero_e_empate": ([0.0, 1.0, 2.0, 2.0], 0),
    "trinca": ([3.0, 3.0, 3.0, 4.0, 1.0], 0),
    "zero_sem_empate": ([25.0, 26.1, 23.4, 27.9, 28.3, 22.6, 29.9, 24.2], 25),
    "no_centro": ([1.0, 2.0, 3.0, 4.0, -5.0, -6.0, -7.0, 8.0], 0),
}

# `wilcox.test(x, mu = mu, conf.int = TRUE)` no R 4.3.3:
#
#     (caso, V, p, intervalo, pseudomediana, nível do intervalo, p exato)
REFERENCIAS_DO_R_WILCOXON = [
    ("depressao", 40, 0.0390625, (0.010000000000000009, 0.78600000000000003),
     0.46000000000000008, 0.94999999999999996, True),
    ("imc15", 70, 0.59948730468750011, (23.699999999999999, 27.5), 25.524999999999999,
     0.94999999999999996, True),
    ("sono", 45, 0.0090906980159250559, (1.0500179906645428, 2.9499207995407808),
     1.4000208422698908, 0.94999999999999996, False),
    ("quarenta", 405.5, 0.83415676157638485, (54.124971776907202, 56.125073797247353),
     55.124964247527465, 0.94999999999999996, False),
    ("grande", 268860, 0.036178756251472863, (148.14996384845051, 151.79994860273732),
     149.95009987422648, 0.94999999999999996, False),
    ("quarenta_e_nove", 590, 0.82830691812031543, (4.0576474999999999, 5.7952684999999997),
     4.8935690000000003, 0.94999999999999996, True),
    ("cinquenta", 635, 0.98459655289653825, (4.1234499896960068, 5.861089624506068),
     4.9594214090413296, 0.94999999999999996, False),
    ("quatro", 10, 0.125, (1.2, 5.0999999999999996), 2.9749999999999996, 0.88, True),
    ("cinco", 14, 0.125, (-0.69999999999999996, 5.0999999999999996), 2.2000000000000002,
     0.94999999999999996, True),
    ("empates_poucos", 10, 0.097512538178109592, (1.4999754447981466, 2.5000245552018527),
     2, 0.79999999999999982, False),
    ("empates_tres", 6, 0.17356816655592155, (2, 2), 1.5857864376269051, 0, False),
    ("zero_e_empate", 6, 0.17356816655592155, (2, 2), 1.5857864376269051, 0, False),
    ("trinca", 15, 0.054474035106195577, (1.9999422942695482, 3.5000494567817499),
     2.9999467856054207, 0.89999999999999991, False),
    ("zero_sem_empate", 20, 0.35254213749971297, (23.000031910335082, 29.099999499036411),
     26.069609142576144, 0.94999999999999996, False),
    ("no_centro", 18, 1, (-6, 5), 0, 0.94999999999999996, True),
]


# Os pares de `REFERENCIAS_DO_R_MANN_WHITNEY`. O `documentacao` é o exemplo do
# `wilcox.test`; o `sono` tem empates; o `um_so` e o `dois_e_tres` não alcançam o
# intervalo de 95%; o `um_contra_59` é o caso extremo que o código do R cita, em que o
# limite é o próprio extremo; o `quarenta_e_nove` e o `cinquenta`, o limite do exato; e o
# `no_centro` tem o W no centro, onde a cauda dobrada passa de 1 e o R corta.
DUAS_DE_POSTOS: dict[str, tuple[list[float], list[float]]] = {
    "documentacao": (
        [0.80, 0.83, 1.89, 1.04, 1.45, 1.38, 1.91, 1.64, 0.73, 1.46],
        [1.15, 0.88, 0.90, 0.74, 1.21],
    ),
    "grupos": DUAS_AMOSTRAS["grupos"],
    "sono": DUAS_AMOSTRAS["sleep"],
    "desiguais": DUAS_AMOSTRAS["desiguais"],
    "um_so": DUAS_AMOSTRAS["um_so"],
    "dois_e_tres": ([1.5, 2.7], [3.1, 4.4, 2.0]),
    "um_contra_59": ([1.0], [float(v) for v in range(2, 61)]),
    "quarenta_e_nove": (_irracionais(49), [v + 0.7 for v in _irracionais(49, 200)]),
    "cinquenta": (_irracionais(50), [v + 0.7 for v in _irracionais(49, 200)]),
    "no_centro": ([1.0, 4.0, 5.0, 8.0], [2.0, 3.0, 6.0, 7.0]),
}

# `wilcox.test(x, y, conf.int = TRUE)` no R 4.3.3:
#
#     (caso, W, p, intervalo, diferença de locação, nível do intervalo, p exato)
REFERENCIAS_DO_R_MANN_WHITNEY = [
    ("documentacao", 35, 0.2544122544122544, (-0.15000000000000002, 0.7599999999999999),
     0.30500000000000005, 0.94999999999999996, True),
    ("grupos", 24, 0.016899509159571079, (-6.1999999999999993, -0.80000000000000071),
     -3.3000000000000007, 0.94999999999999996, True),
    ("sono", 25.5, 0.069327575433626581, (-3.5999470910369937, 0.099953559880887527),
     -1.3463884924878704, 0.94999999999999996, False),
    ("desiguais", 0, 0.0040404040404040404, (-28.999999999999996, -9), -16.899999999999999,
     0.94999999999999996, True),
    ("um_so", 7, 0.92307692307692291, (-5.2000000000000028, 5.1999999999999993),
     0.15000000000000036, 0.84615384615384615, True),
    ("dois_e_tres", 1, 0.40000000000000002, (-2.9000000000000004, 0.70000000000000018),
     -1.05, 0.80000000000000004, True),
    ("um_contra_59", 0, 0.094022875902539105, (-59, -1), -30, 0.94999999999999996, False),
    ("quarenta_e_nove", 1050, 0.28791601404352413, (-1.833755, 0.65847999999999995),
     -0.58763799999999833, 0.94999999999999996, True),
    ("cinquenta", 1092, 0.35376724854756586, (-1.7022115387818326, 0.65853209440451477),
     -0.58761110383173853, 0.94999999999999996, False),
    ("no_centro", 8, 1, (-6, 6), 0, 0.94999999999999996, True),
]


# Os grupos de `REFERENCIAS_DO_R_KRUSKAL`: o exemplo da documentação do `kruskal.test` —
# a eficiência mucociliar de sujeitos normais, com doença obstrutiva e com asbestose
# (Hollander e Wolfe, 1973, p. 116) —, o `PlantGrowth` e o `InsectSprays`, com empates,
# um grupo de um valor só, que o R aceita, e dois grupos.
KRUSKAL: dict[str, list[list[float]]] = {
    "documentacao": [
        [2.9, 3.0, 2.5, 2.6, 3.2],
        [3.8, 2.7, 4.0, 2.4],
        [2.8, 3.4, 3.7, 2.2, 2.0],
    ],
    "plantas": VARIOS_GRUPOS["plantas"],
    "insetos": VARIOS_GRUPOS["insetos"],
    "um_valor": [[30.0], [1.0, 2.0], [3.0, 4.0]],
    "dois": [[24.1, 27.3, 22.8, 30.2, 25.5], [26.5, 29.9, 31.2, 24.8, 33.0, 28.1]],
}

# `kruskal.test(lista)` no R 4.3.3:
#
#     (caso, qui-quadrado, gl, p)
REFERENCIAS_DO_R_KRUSKAL = [
    ("documentacao", 0.77142857142857224, 2, 0.67996477357889362),
    ("plantas", 7.9882287494437154, 2, 0.01842375573147197),
    ("insetos", 54.691344622371446, 5, 1.5108444394185103e-10),
    ("um_valor", 3.6000000000000014, 2, 0.16529888822158642),
    ("dois", 2.1333333333333329, 1, 0.14412703481601624),
]


# O exemplo da documentação do `friedman.test`: o tempo de três métodos de contornar a
# base no beisebol, em 22 jogadores (Hollander e Wolfe, 1973, p. 140), com empates
# dentro dos casos. As linhas são os jogadores.
CONTORNO_DA_BASE = [
    [5.40, 5.50, 5.55], [5.85, 5.70, 5.75], [5.20, 5.60, 5.50], [5.55, 5.50, 5.40],
    [5.90, 5.85, 5.70], [5.45, 5.55, 5.60], [5.40, 5.40, 5.35], [5.45, 5.50, 5.35],
    [5.25, 5.15, 5.00], [5.85, 5.80, 5.70], [5.25, 5.20, 5.10], [5.65, 5.55, 5.45],
    [5.60, 5.35, 5.45], [5.05, 5.00, 4.95], [5.50, 5.50, 5.40], [5.45, 5.55, 5.50],
    [5.55, 5.55, 5.35], [5.45, 5.50, 5.55], [5.50, 5.45, 5.25], [5.65, 5.60, 5.40],
    [5.70, 5.65, 5.55], [6.30, 6.30, 6.25],
]

# Cada caso muda o mesmo tanto de uma medida para a seguinte: a ANOVA de medidas
# repetidas fica sem variação de erro, e o Friedman tem os mesmos postos em todo caso.
ADITIVAS = [[10.0, 12.0, 15.0, 11.0], [11.0, 13.0, 16.0, 12.0], [13.0, 15.0, 18.0, 14.0]]


def _friedman(caso: str) -> list[list[float]]:
    """As medidas de `REFERENCIAS_DO_R_FRIEDMAN`, uma lista por medida."""
    if caso == "contorno_da_base":
        return [[linha[j] for linha in CONTORNO_DA_BASE] for j in range(3)]
    if caso == "aditivas":
        return ADITIVAS
    if caso == "duas_medidas":
        return _medidas("pas")[:2]
    return _medidas(caso)


# `friedman.test(matriz)` no R 4.3.3, com os casos nas linhas:
#
#     (caso, qui-quadrado, gl, p)
REFERENCIAS_DO_R_FRIEDMAN = [
    ("pas", 16.800000000000001, 2, 0.00022486732417884819),
    ("quatro", 28.079999999999998, 3, 3.4942815908612314e-06),
    ("duas_medidas", 10, 1, 0.0015654022580025519),
    ("contorno_da_base", 11.142857142857142, 2, 0.003805040775511363),
    ("aditivas", 8, 2, 0.018315638888734179),
    ("vinte", 59.223350253807105, 3, 8.6130169000145924e-13),
]


# ── O R ─────────────────────────────────────────────────────────────────────


class TestReferenciasDoR:
    @pytest.mark.parametrize(
        ("caso", "mu", "t", "gl", "p", "baixo", "alto", "media"),
        REFERENCIAS_DO_R,
        ids=[f"{caso}-mu{mu}" for caso, mu, *_ in REFERENCIAS_DO_R],
    )
    def test_o_t_test_do_r(self, caso, mu, t, gl, p, baixo, alto, media):
        resultado = t_uma_amostra(_dados(caso), mu)
        assert resultado.estatistica == pytest.approx(t, rel=1e-12, abs=1e-12)
        assert resultado.gl == (gl,)
        assert resultado.p == pytest.approx(p, rel=1e-10)
        assert resultado.ic == pytest.approx((baixo, alto), rel=1e-12)
        assert resultado.estimativa == pytest.approx(media, rel=1e-12)
        assert resultado.referencia == mu

    def test_o_exemplo_da_documentacao_e_o_pareado_de_student(self):
        """
        A documentação do `t.test` imprime o pareado do sono — t = −4,0621, 9 gl,
        p = 0,002833, com a diferença na ordem grupo 1 − grupo 2. O t de uma amostra
        sobre as diferenças é o mesmo teste, com o sinal da ordem em que se subtrai.
        """
        diferencas = [a - b for a, b in zip(SONO_1, SONO_2, strict=True)]
        resultado = t_uma_amostra(diferencas, 0)
        assert round(resultado.estatistica, 4) == -4.0621
        assert resultado.gl == (9.0,)
        assert round(resultado.p, 6) == 0.002833
        assert resultado.ic == pytest.approx((-2.4598858, -0.7001142), abs=1e-7)

    def test_o_intervalo_e_da_media_e_nao_muda_com_a_referencia(self):
        """
        O `conf.int` da uma amostra é o da média: o mesmo vetor contra 0 e contra 1
        dá o mesmo intervalo — é a linha `sleep_extra` duas vezes no R.
        """
        contra_zero = t_uma_amostra(_dados("sleep_extra"), 0)
        contra_um = t_uma_amostra(_dados("sleep_extra"), 1)
        assert contra_zero.ic == pytest.approx(contra_um.ic, rel=1e-14)
        assert contra_zero.p != contra_um.p


class TestStudentDoR:
    @pytest.mark.parametrize(
        ("caso", "t", "gl", "p", "baixo", "alto", "diferenca"),
        REFERENCIAS_DO_R_STUDENT,
        ids=[caso for caso, *_ in REFERENCIAS_DO_R_STUDENT],
    )
    def test_o_t_test_do_r_com_var_equal(self, caso, t, gl, p, baixo, alto, diferenca):
        x, y = DUAS_AMOSTRAS[caso]
        resultado = t_de_student(x, y)
        assert resultado.estatistica == pytest.approx(t, rel=1e-12, abs=1e-12)
        assert resultado.gl == (gl,)
        assert resultado.p == pytest.approx(p, rel=1e-10)
        assert resultado.ic == pytest.approx((baixo, alto), rel=1e-12)
        assert resultado.estimativa == pytest.approx(diferenca, rel=1e-12, abs=1e-12)
        assert resultado.referencia == 0.0

    def test_o_exemplo_da_documentacao(self):
        """
        `t.test(extra ~ group, data = sleep, var.equal = TRUE)`: t = −1,8608, 18 gl,
        p = 0,07919 — o sono como dois grupos, e não como pareado.
        """
        resultado = t_de_student(SONO_1, SONO_2)
        assert round(resultado.estatistica, 4) == -1.8608
        assert resultado.gl == (18.0,)
        assert round(resultado.p, 5) == 0.07919

    def test_trocar_a_ordem_troca_o_sinal_e_mais_nada(self):
        x, y = DUAS_AMOSTRAS["desiguais"]
        ida, volta = t_de_student(x, y), t_de_student(y, x)
        assert volta.estatistica == pytest.approx(-ida.estatistica, rel=1e-14)
        assert volta.p == pytest.approx(ida.p, rel=1e-14)
        assert volta.ic == pytest.approx((-ida.ic[1], -ida.ic[0]), rel=1e-14)


class TestWelchDoR:
    @pytest.mark.parametrize(
        ("caso", "t", "gl", "p", "baixo", "alto", "diferenca"),
        REFERENCIAS_DO_R_WELCH,
        ids=[caso for caso, *_ in REFERENCIAS_DO_R_WELCH],
    )
    def test_o_t_test_do_r(self, caso, t, gl, p, baixo, alto, diferenca):
        x, y = DUAS_AMOSTRAS[caso]
        resultado = t_de_welch(x, y)
        assert resultado.estatistica == pytest.approx(t, rel=1e-12, abs=1e-12)
        assert resultado.gl == pytest.approx((gl,), rel=1e-12)
        assert resultado.p == pytest.approx(p, rel=1e-10)
        assert resultado.ic == pytest.approx((baixo, alto), rel=1e-12)
        assert resultado.estimativa == pytest.approx(diferenca, rel=1e-12, abs=1e-12)

    def test_o_exemplo_da_documentacao(self):
        """
        `t.test(extra ~ group, data = sleep)`, o exemplo que a documentação imprime:
        t = −1,8608, 17,776 gl, p = 0,07939.
        """
        resultado = t_de_welch(SONO_1, SONO_2)
        assert round(resultado.estatistica, 4) == -1.8608
        assert round(resultado.gl[0], 3) == 17.776
        assert round(resultado.p, 5) == 0.07939

    def test_com_as_variancias_iguais_os_gl_do_welch_sao_os_do_student(self):
        """
        Mesmo n e mesma variância nos dois grupos: a fórmula de Welch-Satterthwaite dá
        n₁ + n₂ − 2, e os dois testes coincidem.
        """
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [2.0, 3.0, 4.0, 5.0, 6.0]
        welch, student = t_de_welch(x, y), t_de_student(x, y)
        assert welch.gl == pytest.approx(student.gl, rel=1e-12)
        assert welch.p == pytest.approx(student.p, rel=1e-12)


class TestAnovaDoR:
    @pytest.mark.parametrize(
        ("caso", "f", "gl1", "gl2", "p"),
        REFERENCIAS_DO_R_ANOVA,
        ids=[caso for caso, *_ in REFERENCIAS_DO_R_ANOVA],
    )
    def test_o_oneway_test_do_r(self, caso, f, gl1, gl2, p):
        resultado = anova_de_um_fator(VARIOS_GRUPOS[caso])
        assert resultado.estatistica == pytest.approx(f, rel=1e-12, abs=1e-12)
        assert resultado.gl == (gl1, gl2)
        assert resultado.p == pytest.approx(p, rel=1e-10)

    def test_o_exemplo_da_documentacao(self):
        """`anova(lm(weight ~ group, PlantGrowth))`: F = 4,8461, 2 e 27 gl, p = 0,01591."""
        resultado = anova_de_um_fator(VARIOS_GRUPOS["plantas"])
        assert round(resultado.estatistica, 4) == 4.8461
        assert round(resultado.p, 5) == 0.01591

    def test_com_dois_grupos_o_f_e_o_t_de_student_ao_quadrado(self):
        """A mesma pergunta, o mesmo p: é por isso que a `anova` com dois grupos recusa."""
        x, y = DUAS_AMOSTRAS["grupos"]
        anova, student = anova_de_um_fator([x, y]), t_de_student(x, y)
        assert anova.estatistica == pytest.approx(student.estatistica**2, rel=1e-12)
        assert anova.gl == (1.0, student.gl[0])
        assert anova.p == pytest.approx(student.p, rel=1e-12)

    @pytest.mark.parametrize("caso", ["plantas", "insetos", "tres", "um_constante"])
    def test_o_f_oneway_do_scipy_confere(self, caso):
        """O `scipy` dá o mesmo F e o mesmo p — só não dá os graus de liberdade."""
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            esperado = stats.f_oneway(*VARIOS_GRUPOS[caso])
        resultado = anova_de_um_fator(VARIOS_GRUPOS[caso])
        assert resultado.estatistica == pytest.approx(float(esperado.statistic), rel=1e-12)
        assert resultado.p == pytest.approx(float(esperado.pvalue), rel=1e-10)


class TestAnovaDeWelchDoR:
    @pytest.mark.parametrize(
        ("caso", "f", "gl1", "gl2", "p"),
        REFERENCIAS_DO_R_ANOVA_DE_WELCH,
        ids=[caso for caso, *_ in REFERENCIAS_DO_R_ANOVA_DE_WELCH],
    )
    def test_o_oneway_test_do_r(self, caso, f, gl1, gl2, p):
        resultado = anova_de_welch(VARIOS_GRUPOS[caso])
        assert resultado.estatistica == pytest.approx(f, rel=1e-12, abs=1e-12)
        assert resultado.gl == pytest.approx((gl1, gl2), rel=1e-12)
        assert resultado.p == pytest.approx(p, rel=1e-10)

    def test_o_exemplo_da_documentacao(self):
        """`oneway.test(weight ~ group, PlantGrowth)`: F = 5,181, 2 e 17,128 gl, p = 0,01739."""
        resultado = anova_de_welch(VARIOS_GRUPOS["plantas"])
        assert round(resultado.estatistica, 3) == 5.181
        assert round(resultado.gl[1], 3) == 17.128
        assert round(resultado.p, 5) == 0.01739

    def test_com_dois_grupos_o_f_e_o_t_de_welch_ao_quadrado(self):
        """E com os mesmos graus de liberdade: 19,93 nos dois — o R dá os mesmos."""
        x, y = DUAS_AMOSTRAS["grupos"]
        anova, welch = anova_de_welch([x, y]), t_de_welch(x, y)
        assert anova.estatistica == pytest.approx(welch.estatistica**2, rel=1e-12)
        assert anova.gl[1] == pytest.approx(welch.gl[0], rel=1e-12)
        assert anova.p == pytest.approx(welch.p, rel=1e-12)

    @pytest.mark.parametrize("caso", ["plantas", "insetos", "tres"])
    def test_o_f_oneway_do_scipy_confere(self, caso):
        esperado = stats.f_oneway(*VARIOS_GRUPOS[caso], equal_var=False)
        resultado = anova_de_welch(VARIOS_GRUPOS[caso])
        assert resultado.estatistica == pytest.approx(float(esperado.statistic), rel=1e-12)
        assert resultado.p == pytest.approx(float(esperado.pvalue), rel=1e-10)


class TestRepetidasDoR:
    @pytest.mark.parametrize(
        ("caso", "f", "epsilon", "gl1", "p"),
        REFERENCIAS_DO_R_REPETIDAS,
        ids=[caso for caso, *_ in REFERENCIAS_DO_R_REPETIDAS],
    )
    def test_o_aov_e_o_anova_mlm_do_r(self, caso, f, epsilon, gl1, p):
        """
        O ε e o p com tolerância de 1e-9: o `sphericity` do R, que dá o ε, erra na
        décima segunda casa — a conta daqui bate com a em frações até a décima quinta.
        """
        medidas = _medidas(caso)
        n, k = len(medidas[0]), len(medidas)
        resultado = anova_de_medidas_repetidas(medidas)
        assert resultado.estatistica == pytest.approx(f, rel=1e-12)
        assert resultado.epsilon == pytest.approx(epsilon, rel=1e-9)
        assert resultado.gl == pytest.approx((gl1, gl1 * (n - 1)), rel=1e-9)
        assert resultado.gl[0] == pytest.approx(resultado.epsilon * (k - 1), rel=1e-14)
        assert resultado.p == pytest.approx(p, rel=1e-8)

    def test_com_duas_medidas_e_o_t_pareado_ao_quadrado(self):
        """
        Com duas medidas o ε é 1 — não há esfericidade a violar —, e o F é o t pareado
        ao quadrado: `t.test(pas_0, pas_1, paired = TRUE)`, t² = 35,4385, p = 0,0002145.
        """
        pas = _medidas("pas")[:2]
        resultado = anova_de_medidas_repetidas(pas)
        assert resultado.epsilon == pytest.approx(1.0, rel=1e-12)
        assert resultado.estatistica == pytest.approx(35.438502673796798, rel=1e-12)
        assert resultado.p == pytest.approx(0.00021453897703870372, rel=1e-9)
        diferencas = [a - b for a, b in zip(pas[0], pas[1], strict=True)]
        assert resultado.estatistica == pytest.approx(
            t_uma_amostra(diferencas, 0).estatistica ** 2, rel=1e-12
        )

    def test_o_epsilon_fica_entre_os_limites(self):
        """Entre 1/(k − 1) — o limite inferior de Greenhouse e Geisser — e 1."""
        for caso in ("pas", "quatro", "dois_casos", "vinte"):
            medidas = _medidas(caso)
            epsilon = anova_de_medidas_repetidas(medidas).epsilon
            assert 1 / (len(medidas) - 1) - 1e-12 <= epsilon <= 1 + 1e-12


class TestWilcoxonDoR:
    @pytest.mark.parametrize(
        ("caso", "v", "p", "ic", "estimativa", "nivel", "exato"),
        REFERENCIAS_DO_R_WILCOXON,
        ids=[caso for caso, *_ in REFERENCIAS_DO_R_WILCOXON],
    )
    def test_o_wilcox_test_do_r(self, caso, v, p, ic, estimativa, nivel, exato):
        """
        O V, o p, o caminho do p, a pseudomediana, o intervalo e o nível dele. No caminho
        exato, o intervalo e a estimativa são médias de Walsh, e saem iguais ao R até o
        último bit; no aproximado, a busca é o `uniroot` dele, e a diferença que sobra é
        a do quantil da normal do `scipy`, que difere do `qnorm` em um ou dois bits.
        """
        x, mu = UMA_AMOSTRA_DE_POSTOS[caso]
        resultado = wilcoxon_uma_amostra(x, mu)
        assert resultado.estatistica == v
        assert resultado.p == pytest.approx(p, rel=1e-12)
        assert resultado.exato is exato
        assert resultado.confianca_do_ic == pytest.approx(nivel, abs=1e-15)
        if exato:
            assert resultado.ic == ic
            assert resultado.estimativa == estimativa
        else:
            assert resultado.ic == pytest.approx(ic, rel=1e-12)
            assert resultado.estimativa == pytest.approx(estimativa, rel=1e-12)
        assert resultado.referencia == mu

    def test_o_exemplo_da_documentacao(self):
        """
        `wilcox.test(x, y, paired = TRUE, alternative = "greater")`: V = 40, p = 0,01953 —
        o de uma amostra sobre as diferenças, com metade do p bilateral.
        """
        diferencas = [a - b for a, b in zip(DEPRESSAO_X, DEPRESSAO_Y, strict=True)]
        resultado = wilcoxon_uma_amostra(diferencas, 0)
        assert resultado.estatistica == 40
        assert round(resultado.p / 2, 5) == 0.01953

    def test_os_valores_iguais_a_referencia_saem_do_intervalo_tambem(self):
        """
        `wilcox.test(c(25, 27, 27, 27), mu = 25, conf.int = TRUE)`: sem o 25, os valores
        são todos iguais, e o R devolve o p — V = 6, p = 0,1489 —, `NaN` no intervalo e o
        ponto médio no lugar da pseudomediana. Aqui o intervalo e a estimativa saem
        `None`: o ponto médio não é a pseudomediana, e não se imprime com o nome dela.
        """
        resultado = wilcoxon_uma_amostra([25.0, 27.0, 27.0, 27.0], 25)
        assert resultado.estatistica == 6
        assert resultado.p == pytest.approx(0.14891467317876567, rel=1e-12)
        assert (resultado.ic, resultado.estimativa, resultado.confianca_do_ic) == (
            None,
            None,
            None,
        )

    @pytest.mark.parametrize("caso", list(UMA_AMOSTRA_DE_POSTOS))
    def test_o_wilcoxon_do_scipy_confere_com_a_escolha_do_r(self, caso):
        """
        O `wilcoxon` do `scipy` dá o p do R quando recebe a escolha do R — e só então: o
        critério dele para o exato é outro, e ele não corrige a continuidade por padrão.
        """
        x, mu = UMA_AMOSTRA_DE_POSTOS[caso]
        resultado = wilcoxon_uma_amostra(x, mu)
        esperado = stats.wilcoxon(
            [valor - mu for valor in x],
            zero_method="wilcox",
            correction=not resultado.exato,
            method="exact" if resultado.exato else "approx",
        )
        assert resultado.p == pytest.approx(float(esperado.pvalue), rel=1e-10)


class TestMannWhitneyDoR:
    @pytest.mark.parametrize(
        ("caso", "w", "p", "ic", "estimativa", "nivel", "exato"),
        REFERENCIAS_DO_R_MANN_WHITNEY,
        ids=[caso for caso, *_ in REFERENCIAS_DO_R_MANN_WHITNEY],
    )
    def test_o_wilcox_test_do_r(self, caso, w, p, ic, estimativa, nivel, exato):
        x, y = DUAS_DE_POSTOS[caso]
        resultado = mann_whitney(x, y)
        assert resultado.estatistica == w
        assert resultado.p == pytest.approx(p, rel=1e-12)
        assert resultado.exato is exato
        assert resultado.confianca_do_ic == pytest.approx(nivel, abs=1e-15)
        if exato:
            assert resultado.ic == ic
            assert resultado.estimativa == estimativa
        else:
            assert resultado.ic == pytest.approx(ic, rel=1e-12)
            assert resultado.estimativa == pytest.approx(estimativa, rel=1e-12)
        assert resultado.referencia == 0.0

    def test_o_exemplo_da_documentacao(self):
        """`wilcox.test(x, y, alternative = "g")`: W = 35, p = 0,1272."""
        resultado = mann_whitney(*DUAS_DE_POSTOS["documentacao"])
        assert resultado.estatistica == 35
        assert round(resultado.p / 2, 4) == 0.1272

    def test_dois_grupos_que_nao_variam_por_dentro(self):
        """
        `wilcox.test(c(5, 5, 5), c(6, 6, 6))`: W = 0, p = 0,04685 — o R calcula o p; com
        `conf.int = TRUE` ele para com erro, porque todo valor empata com todo valor no
        extremo da busca. Aqui o p sai, e o intervalo e a estimativa saem `None`.
        """
        resultado = mann_whitney([5.0, 5.0, 5.0], [6.0, 6.0, 6.0])
        assert resultado.estatistica == 0
        assert resultado.p == pytest.approx(0.046854177603873753, rel=1e-12)
        assert (resultado.ic, resultado.estimativa, resultado.confianca_do_ic) == (
            None,
            None,
            None,
        )

    @pytest.mark.parametrize("caso", list(DUAS_DE_POSTOS))
    def test_o_mannwhitneyu_do_scipy_confere_com_a_escolha_do_r(self, caso):
        """O U do primeiro grupo é o W do R, e o p é o mesmo com a escolha do R."""
        x, y = DUAS_DE_POSTOS[caso]
        resultado = mann_whitney(x, y)
        esperado = stats.mannwhitneyu(
            x,
            y,
            use_continuity=not resultado.exato,
            method="exact" if resultado.exato else "asymptotic",
        )
        assert resultado.estatistica == float(esperado.statistic)
        assert resultado.p == pytest.approx(float(esperado.pvalue), rel=1e-10)


class TestKruskalWallisDoR:
    @pytest.mark.parametrize(
        ("caso", "qui", "gl", "p"),
        REFERENCIAS_DO_R_KRUSKAL,
        ids=[caso for caso, *_ in REFERENCIAS_DO_R_KRUSKAL],
    )
    def test_o_kruskal_test_do_r(self, caso, qui, gl, p):
        resultado = kruskal_wallis(KRUSKAL[caso])
        assert resultado.estatistica == pytest.approx(qui, rel=1e-13)
        assert resultado.gl == (gl,)
        assert resultado.p == pytest.approx(p, rel=1e-12)

    def test_o_exemplo_da_documentacao(self):
        """`kruskal.test(list(x, y, z))`: qui-quadrado = 0,77143, 2 gl, p = 0,68."""
        resultado = kruskal_wallis(KRUSKAL["documentacao"])
        assert round(resultado.estatistica, 5) == 0.77143
        assert round(resultado.p, 2) == 0.68


class TestFriedmanDoR:
    @pytest.mark.parametrize(
        ("caso", "qui", "gl", "p"),
        REFERENCIAS_DO_R_FRIEDMAN,
        ids=[caso for caso, *_ in REFERENCIAS_DO_R_FRIEDMAN],
    )
    def test_o_friedman_test_do_r(self, caso, qui, gl, p):
        resultado = friedman(_friedman(caso))
        assert resultado.estatistica == pytest.approx(qui, rel=1e-13)
        assert resultado.gl == (gl,)
        assert resultado.p == pytest.approx(p, rel=1e-12)

    def test_o_exemplo_da_documentacao(self):
        """`friedman.test(RoundingTimes)`: qui-quadrado = 11,143, 2 gl, p = 0,003805."""
        resultado = friedman(_friedman("contorno_da_base"))
        assert round(resultado.estatistica, 3) == 11.143
        assert round(resultado.p, 6) == 0.003805

    @pytest.mark.parametrize("caso", ["pas", "quatro", "contorno_da_base", "aditivas", "vinte"])
    def test_o_friedmanchisquare_do_scipy_confere(self, caso):
        """O mesmo qui-quadrado — o `scipy` só não aceita duas medidas, que o R aceita."""
        medidas = _friedman(caso)
        esperado = stats.friedmanchisquare(*medidas)
        resultado = friedman(medidas)
        assert resultado.estatistica == pytest.approx(float(esperado.statistic), rel=1e-12)
        assert resultado.p == pytest.approx(float(esperado.pvalue), rel=1e-10)

    def test_o_scipy_recusa_as_duas_medidas_que_o_r_aceita(self):
        """É a razão de o Friedman estar escrito aqui, e não importado."""
        with pytest.raises(ValueError):
            stats.friedmanchisquare(*_friedman("duas_medidas"))
        assert friedman(_friedman("duas_medidas")).gl == (1.0,)


class TestRaizDoR:
    """
    O `uniroot` do R transcrito, conferido sozinho: `uniroot(f, c(a, b), tol = tol)$root`
    no R 4.3.3, com dezessete algarismos, e a raiz daqui igual até o último bit — os
    mesmos passos, as mesmas comparações.
    """

    def test_o_exemplo_de_forsythe_malcolm_e_moler(self):
        """x³ − 2x − 5 entre 2 e 3, com a tolerância do `wilcox.test` e com uma apertada."""

        def f(x):
            return x * x * x - 2 * x - 5

        assert hipoteses._raiz(f, 2.0, 3.0, f(2.0), f(3.0)) == 2.0945512665841388
        assert (
            hipoteses._raiz(f, 2.0, 3.0, f(2.0), f(3.0), tolerancia=1e-10)
            == 2.0945514815361843
        )

    def test_o_cosseno(self):
        def f(x):
            return math.cos(x) - x

        assert hipoteses._raiz(f, 0.0, 1.0, f(0.0), f(1.0)) == 0.73909105828536981

    def test_a_raiz_num_extremo(self):
        """O `R_zeroin2` devolve o extremo em que a função já é zero, sem procurar."""
        assert hipoteses._raiz(lambda x: x, 0.0, 1.0, 0.0, 1.0) == 0.0
        assert hipoteses._raiz(lambda x: x - 1, 0.0, 1.0, -1.0, 0.0) == 1.0


# ── As fórmulas, escritas de novo ───────────────────────────────────────────


class TestFormula:
    @pytest.mark.parametrize("caso", ["sleep_extra", "abaixo", "imc15", "quarenta"])
    def test_o_t_o_p_e_o_intervalo_pela_formula(self, caso):
        valores = _dados(caso)
        mu = statistics.median(valores)
        n = len(valores)
        media = statistics.fmean(valores)
        erro = statistics.stdev(valores) / math.sqrt(n)
        t = (media - mu) / erro
        quantil = stats.t.ppf((1 + CONFIANCA) / 2, n - 1)

        resultado = t_uma_amostra(valores, mu)
        assert resultado.estatistica == pytest.approx(t, rel=1e-10, abs=1e-12)
        assert resultado.p == pytest.approx(2 * stats.t.sf(abs(t), n - 1), rel=1e-9)
        assert resultado.ic == pytest.approx(
            (media - quantil * erro, media + quantil * erro), rel=1e-12
        )

    @pytest.mark.parametrize("caso", ["pas", "quatro", "vinte"])
    def test_as_medidas_repetidas_em_fracoes(self, caso):
        """
        O F e o ε pela definição, em aritmética exata com `Fraction`: as somas de
        quadrados do modelo caso + medida, e o ε pela covariância centrada nas linhas e
        nas colunas.
        """
        from fractions import Fraction

        medidas = [[Fraction(valor) for valor in medida] for medida in _medidas(caso)]
        k, n = len(medidas), len(medidas[0])
        geral = sum(sum(medida) for medida in medidas) / (n * k)
        por_medida = [sum(medida) / n for medida in medidas]
        por_caso = [sum(medida[i] for medida in medidas) / k for i in range(n)]
        ss_medidas = n * sum((m - geral) ** 2 for m in por_medida)
        ss_erro = sum(
            (medidas[j][i] - por_caso[i] - por_medida[j] + geral) ** 2
            for i in range(n)
            for j in range(k)
        )
        f = (ss_medidas / (k - 1)) / (ss_erro / ((n - 1) * (k - 1)))
        desvios = [[valor - por_medida[j] for valor in medidas[j]] for j in range(k)]
        cov = [
            [sum(x * y for x, y in zip(desvios[a], desvios[b], strict=True)) / (n - 1)
             for b in range(k)]
            for a in range(k)
        ]
        linha = [sum(c) / k for c in cov]
        coluna = [sum(cov[a][b] for a in range(k)) / k for b in range(k)]
        media = sum(linha) / k
        centrada = [[cov[a][b] - linha[a] - coluna[b] + media for b in range(k)] for a in range(k)]
        traco = sum(centrada[a][a] for a in range(k))
        traco_quadrado = sum(centrada[a][b] * centrada[b][a] for a in range(k) for b in range(k))
        epsilon = traco**2 / ((k - 1) * traco_quadrado)

        resultado = anova_de_medidas_repetidas(_medidas(caso))
        assert resultado.estatistica == pytest.approx(float(f), rel=1e-13)
        assert resultado.epsilon == pytest.approx(float(epsilon), rel=1e-13)

    def test_a_referencia_na_media_da_t_zero_e_p_um(self):
        resultado = t_uma_amostra(_dados("no_centro"), 3)
        assert (resultado.estatistica, resultado.p) == (0.0, 1.0)

    @pytest.mark.parametrize("caso", ["grupos", "sleep", "desiguais"])
    def test_o_de_welch_pela_formula(self, caso):
        """As variâncias separadas e os gl de Welch-Satterthwaite, com o `statistics`."""
        x, y = DUAS_AMOSTRAS[caso]
        a = statistics.variance(x) / len(x)
        b = statistics.variance(y) / len(y)
        erro = math.sqrt(a + b)
        gl = (a + b) ** 2 / (a**2 / (len(x) - 1) + b**2 / (len(y) - 1))
        diferenca = statistics.fmean(x) - statistics.fmean(y)
        t = diferenca / erro
        quantil = stats.t.ppf((1 + CONFIANCA) / 2, gl)

        resultado = t_de_welch(x, y)
        assert resultado.estatistica == pytest.approx(t, rel=1e-10)
        assert resultado.gl == pytest.approx((gl,), rel=1e-10)
        assert resultado.p == pytest.approx(2 * stats.t.sf(abs(t), gl), rel=1e-9)
        assert resultado.ic == pytest.approx(
            (diferenca - quantil * erro, diferenca + quantil * erro), rel=1e-12
        )

    @pytest.mark.parametrize("caso", ["grupos", "sleep", "um_so", "desiguais"])
    def test_o_de_student_pela_formula(self, caso):
        """A variância combinada, escrita com o `statistics`; o `scipy` só na cauda."""
        x, y = DUAS_AMOSTRAS[caso]
        n1, n2 = len(x), len(y)
        soma = sum((n - 1) * statistics.variance(v) for n, v in ((n1, x), (n2, y)) if n > 1)
        combinada = soma / (n1 + n2 - 2)
        erro = math.sqrt(combinada * (1 / n1 + 1 / n2))
        diferenca = statistics.fmean(x) - statistics.fmean(y)
        t = diferenca / erro
        quantil = stats.t.ppf((1 + CONFIANCA) / 2, n1 + n2 - 2)

        resultado = t_de_student(x, y)
        assert resultado.estatistica == pytest.approx(t, rel=1e-10)
        assert resultado.p == pytest.approx(2 * stats.t.sf(abs(t), n1 + n2 - 2), rel=1e-9)
        assert resultado.ic == pytest.approx(
            (diferenca - quantil * erro, diferenca + quantil * erro), rel=1e-12
        )


class TestPostosPelaDefinicao:
    """
    As distribuições exatas e as estimativas pela definição, permutação por permutação,
    em inteiros — sem a recursão do módulo, sem o R e sem o `scipy`.
    """

    @pytest.mark.parametrize("n", range(1, 13))
    def test_a_distribuicao_do_posto_sinalizado(self, n):
        """Cada um dos 2ⁿ sinais, e a soma dos postos dos positivos."""
        contagens = [0] * (n * (n + 1) // 2 + 1)
        for sinais in itertools.product((0, 1), repeat=n):
            contagens[sum(posto * sinal for posto, sinal in enumerate(sinais, start=1))] += 1
        assert hipoteses._contagens_do_posto_sinalizado(n) == tuple(contagens)

    @pytest.mark.parametrize(("m", "n"), [(1, 1), (1, 4), (2, 3), (3, 3), (3, 5), (4, 6), (6, 6)])
    def test_a_distribuicao_da_soma_dos_postos(self, m, n):
        """Cada escolha dos m postos do primeiro grupo entre os m + n, e o W dela."""
        contagens = [0] * (m * n + 1)
        for escolhidos in itertools.combinations(range(1, m + n + 1), m):
            contagens[sum(escolhidos) - m * (m + 1) // 2] += 1
        assert hipoteses._contagens_da_soma_dos_postos(m, n) == tuple(contagens)
        assert sum(contagens) == math.comb(m + n, m)

    def test_o_quantil_e_o_menor_com_a_acumulada_ate_o_alvo_inclusive(self):
        """
        O `qsignrank` e o `qwilcox` do R: o menor q com P(S ≤ q) ≥ p — com o igual. Com
        dois postos, S vai de 0 a 3, um jeito cada, e P(S ≤ 1) é ½ exato: o quantil de ½
        é 1, e não 2. A folga de dez épsilons sai do p dentro da função — somada aqui, o
        alvo fica em ½ exato.
        """
        contagens = hipoteses._contagens_do_posto_sinalizado(2)
        assert contagens == (1, 1, 1, 1)
        meio = 0.5 + 10 * sys.float_info.epsilon
        assert hipoteses._quantil(contagens, 4, meio) == 1

    def test_o_quantil_com_a_folga_do_r(self):
        """
        `qwilcox((1 - 0.95)/2, 1, 39)` é 0 no R: P(W ≤ 0) é 1/40, que em `double` dá o
        próprio 0,025. Aqui a acumulada é a fração exata — um tico abaixo do `double`
        0,025 —, e é a folga de dez épsilons do R que deixa o quantil igual ao dele. No
        intervalo, o `qu == 0` vira 1 do mesmo jeito; o quantil é que precisa ser o do R.
        """
        contagens = hipoteses._contagens_da_soma_dos_postos(1, 39)
        assert hipoteses._quantil(contagens, 40, (1 - 0.95) / 2) == 0
        assert hipoteses._quantil(contagens, 40, 0.025) == 0

    def test_o_p_exato_do_wilcoxon_pela_permutacao(self):
        """
        Os 2⁹ sinais trocados nas diferenças da depressão: o p é a fração dos que dão um
        V tão longe do centro quanto o observado, dos dois lados.
        """
        diferencas = [a - b for a, b in zip(DEPRESSAO_X, DEPRESSAO_Y, strict=True)]
        ordem = sorted(range(9), key=lambda i: abs(diferencas[i]))
        postos = {i: posto for posto, i in enumerate(ordem, start=1)}
        observado = sum(postos[i] for i in range(9) if diferencas[i] > 0)
        centro = 9 * 10 / 4
        distancia = abs(observado - centro)
        extremos = sum(
            1
            for sinais in itertools.product((0, 1), repeat=9)
            if abs(sum(postos[i] for i in range(9) if sinais[i]) - centro) >= distancia
        )
        assert wilcoxon_uma_amostra(diferencas, 0).p == pytest.approx(extremos / 2**9, rel=1e-15)

    def test_a_pseudomediana_e_a_mediana_das_medias_de_walsh(self):
        x = _dados("imc15")
        walsh = [(a + b) / 2 for a, b in itertools.combinations_with_replacement(x, 2)]
        assert wilcoxon_uma_amostra(x, 25).estimativa == statistics.median(walsh)

    def test_a_diferenca_de_locacao_e_a_mediana_das_diferencas(self):
        """E não a diferença das medianas dos dois grupos — que aqui é outro número."""
        x, y = DUAS_DE_POSTOS["grupos"]
        diferencas = [a - b for a in x for b in y]
        resultado = mann_whitney(x, y)
        assert resultado.estimativa == statistics.median(diferencas)
        assert resultado.estimativa != statistics.median(x) - statistics.median(y)

    def test_o_intervalo_exato_contem_a_estimativa_e_cobre_95(self):
        """
        Os limites são dois valores da lista ordenada, e o p da referência num limite é
        o maior que o intervalo ainda deixa de fora: abaixo de 0,05, por pouco.
        """
        x = _dados("imc15")
        resultado = wilcoxon_uma_amostra(x, 25)
        baixo, alto = resultado.ic
        walsh = sorted((a + b) / 2 for a, b in itertools.combinations_with_replacement(x, 2))
        assert baixo in walsh and alto in walsh
        assert baixo < resultado.estimativa < alto

    def test_o_v_dos_dois_lados_soma_o_total(self):
        """V de x − mu mais V de mu − x é n(n + 1)/2, e o p é o mesmo."""
        x = _dados("imc15")
        ida = wilcoxon_uma_amostra(x, 25)
        volta = wilcoxon_uma_amostra([50 - valor for valor in x], 25)
        assert ida.estatistica + volta.estatistica == 15 * 16 / 2
        assert ida.p == pytest.approx(volta.p, rel=1e-15)

    def test_trocar_os_grupos_troca_o_w_e_o_sinal(self):
        """W vira n₁n₂ − W, a diferença troca de sinal, e o p não muda."""
        x, y = DUAS_DE_POSTOS["grupos"]
        ida, volta = mann_whitney(x, y), mann_whitney(y, x)
        assert ida.estatistica + volta.estatistica == len(x) * len(y)
        assert volta.estimativa == pytest.approx(-ida.estimativa, rel=1e-15)
        assert volta.ic == pytest.approx((-ida.ic[1], -ida.ic[0]), rel=1e-15)
        assert volta.p == pytest.approx(ida.p, rel=1e-15)

    def test_o_kruskal_wallis_com_dois_grupos_e_o_z_do_mann_whitney_ao_quadrado(self):
        """
        Com dois grupos, o qui-quadrado de Kruskal-Wallis é o z do Mann-Whitney sem a
        correção de continuidade, ao quadrado — conferido sem empates.
        """
        x, y = KRUSKAL["dois"]
        n1, n2 = len(x), len(y)
        w = mann_whitney(x, y).estatistica
        z = (w - n1 * n2 / 2) / math.sqrt(n1 * n2 * (n1 + n2 + 1) / 12)
        assert kruskal_wallis([x, y]).estatistica == pytest.approx(z**2, rel=1e-12)

    def test_o_friedman_das_aditivas_e_o_maior_que_existe(self):
        """
        Todos os casos com os mesmos postos: o qui-quadrado é n(k − 1), o máximo — onde a
        ANOVA de medidas repetidas fica sem variação de erro.
        """
        resultado = friedman(ADITIVAS)
        assert resultado.estatistica == 4 * (3 - 1)
        assert sem_variacao_entre_medidas(ADITIVAS)
        assert not medidas_iguais_em_cada_caso(ADITIVAS)


# ── O que ele recusa ────────────────────────────────────────────────────────


class TestRecusas:
    def test_um_valor_so_como_o_r(self):
        """O `not enough 'x' observations` do R."""
        with pytest.raises(ValueError, match="pelo menos 2 valores"):
            t_uma_amostra([5.0], 1)
        with pytest.raises(ValueError, match="pelo menos 2 valores"):
            t_uma_amostra([], 1)

    def test_valores_que_nao_variam_como_o_r(self):
        """O `data are essentially constant` do R."""
        with pytest.raises(ValueError, match="não variam"):
            t_uma_amostra([5.0, 5.0, 5.0], 1)

    def test_o_criterio_de_constante_e_o_do_r_e_nao_so_todos_iguais(self):
        """
        O R recusa o erro-padrão abaixo de 10 ε |média|: um vetor que varia só no
        último bit é constante para ele, e o t sairia enorme e sem sentido.
        """
        base = 1e6
        quase = [base, math.nextafter(base, math.inf), base]
        assert len(set(quase)) == 2
        assert sem_variacao(quase)
        assert not sem_variacao([base, base + 0.01, base])
        with pytest.raises(ValueError, match="não variam"):
            t_uma_amostra(quase, 0)

    def test_zeros_nao_variam(self):
        """Todos zero: o erro-padrão é 0 e a média também — o R devolveria `NaN`."""
        assert sem_variacao([0.0, 0.0, 0.0])

    def test_valor_ausente_ou_infinito(self):
        with pytest.raises(ValueError, match="ausente ou infinito"):
            t_uma_amostra([1.0, float("nan"), 3.0], 0)
        with pytest.raises(ValueError, match="ausente ou infinito"):
            t_uma_amostra([1.0, math.inf, 3.0], 0)

    def test_referencia_que_nao_e_numero_finito(self):
        with pytest.raises(ValueError, match="número finito"):
            t_uma_amostra([1.0, 2.0, 3.0], math.nan)

    def test_matriz_nao_e_vetor(self):
        with pytest.raises(ValueError, match="vetor"):
            t_uma_amostra([[1.0, 2.0], [3.0, 4.0]], 0)

    def test_o_de_student_com_um_grupo_vazio(self):
        with pytest.raises(ValueError, match="um valor em cada grupo"):
            t_de_student([], [1.0, 2.0, 3.0])

    def test_o_de_student_com_dois_valores_no_total(self):
        """O `not enough observations` do R: um em cada grupo não deixa grau de liberdade."""
        with pytest.raises(ValueError, match="pelo menos 3 valores"):
            t_de_student([1.0], [2.0])

    def test_dois_grupos_que_nao_variam_por_dentro(self):
        """
        Cada grupo com o seu valor: as médias diferem, e o R recusa assim mesmo — o
        erro-padrão combinado é zero, e o t seria infinito.
        """
        with pytest.raises(ValueError, match="não variam"):
            t_de_student([5.0, 5.0, 5.0], [6.0, 6.0, 6.0, 6.0])
        assert sem_variacao_em_duas([5.0, 5.0, 5.0], [6.0, 6.0, 6.0, 6.0])
        assert sem_variacao_em_duas([5.0, 5.0], [6.0, 6.0], variancias_iguais=False)

    def test_o_welch_com_um_valor_num_grupo_como_o_r(self):
        """O `not enough 'x' observations` do R — que o de Student aceitaria."""
        x, y = DUAS_AMOSTRAS["um_so"]
        with pytest.raises(ValueError, match="pelo menos 2 valores em cada grupo"):
            t_de_welch(x, y)
        with pytest.raises(ValueError, match="pelo menos 2 valores em cada grupo"):
            t_de_welch(y, x)
        assert t_de_student(x, y).gl == (11.0,)

    def test_o_criterio_de_constante_e_o_erro_padrao_do_proprio_teste(self):
        """
        Um grupo de dois valores que diferem por 1e-8 em torno de um milhão, contra mil
        valores iguais. No de Student a variância combinada dilui o grupo pequeno, o
        erro-padrão cai abaixo do critério e o R recusa; no de Welch cada grupo entra com
        a sua, e o R calcula: t = 1, 1 gl, p = 0,5 — conferido nos dois.
        """
        x, y = [1e6, 1e6 + 1e-8], [1e6] * 1000
        assert sem_variacao_em_duas(x, y, variancias_iguais=True)
        assert not sem_variacao_em_duas(x, y, variancias_iguais=False)
        with pytest.raises(ValueError, match="não variam"):
            t_de_student(x, y)
        resultado = t_de_welch(x, y)
        assert (resultado.gl[0], resultado.p) == pytest.approx((1.0, 0.5), rel=1e-9)

    def test_o_welch_de_dois_grupos_que_nao_variam(self):
        with pytest.raises(ValueError, match="não variam"):
            t_de_welch([5.0, 5.0, 5.0], [6.0, 6.0, 6.0, 6.0])

    def test_a_anova_com_um_grupo_so(self):
        with pytest.raises(ValueError, match="pelo menos 2 grupos"):
            anova_de_um_fator([[1.0, 2.0, 3.0]])

    def test_a_anova_com_um_valor_num_grupo_como_o_oneway_test(self):
        """O `not enough observations` do `oneway.test` — o `aov` aceitaria."""
        with pytest.raises(ValueError, match="pelo menos 2 valores em cada grupo"):
            anova_de_um_fator([[30.0], [1.0, 2.0], [3.0, 4.0]])

    def test_a_anova_de_grupos_que_nao_variam_por_dentro(self):
        """O R devolveria F infinito; aqui é recusa, como no t."""
        assert sem_variacao_nos_grupos([[5.0, 5.0], [6.0, 6.0], [7.0, 7.0]])
        with pytest.raises(ValueError, match="não variam dentro dos grupos"):
            anova_de_um_fator([[5.0, 5.0], [6.0, 6.0], [7.0, 7.0]])

    def test_a_de_welch_com_um_grupo_que_nao_varia(self):
        """Onde o R devolve `NaN`; a clássica, sobre os mesmos grupos, roda."""
        with pytest.raises(ValueError, match="um grupo não varia"):
            anova_de_welch(VARIOS_GRUPOS["um_constante"])
        assert anova_de_um_fator(VARIOS_GRUPOS["um_constante"]).gl == (2.0, 6.0)

    def test_a_de_welch_com_um_valor_num_grupo(self):
        with pytest.raises(ValueError, match="pelo menos 2 valores em cada grupo"):
            anova_de_welch([[30.0], [1.0, 2.0], [3.0, 4.0]])

    def test_o_criterio_dos_grupos_para_cada_anova(self):
        """
        Um grupo constante não barra a clássica — a variância combinada é a dos outros —
        e barra a de Welch, que divide por ela.
        """
        grupos = VARIOS_GRUPOS["um_constante"]
        assert not sem_variacao_nos_grupos(grupos, variancias_iguais=True)
        assert sem_variacao_nos_grupos(grupos, variancias_iguais=False)
        base = 1e6
        quase = [[base, math.nextafter(base, math.inf)], [base, base], [base, base]]
        assert sem_variacao_nos_grupos(quase)

    def test_as_repetidas_com_uma_medida(self):
        with pytest.raises(ValueError, match="pelo menos 2 medidas"):
            anova_de_medidas_repetidas([[1.0, 2.0, 3.0]])

    def test_as_repetidas_com_tamanhos_diferentes(self):
        """Medidas de casos diferentes não são repetidas — quem chama tira os faltantes."""
        with pytest.raises(ValueError, match="os mesmos casos"):
            anova_de_medidas_repetidas([[1.0, 2.0, 3.0], [1.0, 2.0], [4.0, 5.0, 6.0]])

    def test_as_repetidas_com_um_caso(self):
        with pytest.raises(ValueError, match="pelo menos 2 casos"):
            anova_de_medidas_repetidas([[1.0], [2.0], [3.0]])

    def test_medidas_que_nao_variam_dentro_dos_casos(self):
        """
        Cada caso muda o mesmo tanto — o F é uma divisão por zero. O R devolve um F de
        10²³ feito de arredondamento; aqui é recusa.
        """
        aditivas = [[10.0, 12.0, 15.0, 11.0], [11.0, 13.0, 16.0, 12.0], [13.0, 15.0, 18.0, 14.0]]
        assert sem_variacao_entre_medidas(aditivas)
        with pytest.raises(ValueError, match="não variam dentro dos casos"):
            anova_de_medidas_repetidas(aditivas)
        iguais = [[10.0, 12.0, 15.0]] * 3
        assert sem_variacao_entre_medidas(iguais)
        assert not sem_variacao_entre_medidas(_medidas("pas"))

    def test_as_repetidas_com_valor_ausente(self):
        with pytest.raises(ValueError, match="ausente ou infinito"):
            anova_de_medidas_repetidas([[1.0, math.nan, 3.0], [1.0, 2.0, 3.0], [4.0, 5.0, 7.0]])

    def test_um_grupo_que_nao_varia_nao_basta(self):
        """
        A variância combinada é a do outro grupo, e o t existe — o `um_constante` das
        referências. E sai calado: o «Precision loss» que o `scipy` emite para o grupo
        constante não vai para o terminal, porque ali a conta está certa.
        """
        import warnings

        assert not sem_variacao_em_duas([5.0, 5.0, 5.0], [4.0, 6.0, 7.0])
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            assert t_de_student([5.0, 5.0, 5.0], [4.0, 6.0, 7.0]).gl == (4.0,)

    def test_o_criterio_de_duas_amostras_e_o_do_r(self):
        """O último bit de diferença não é variação, nem com dois grupos."""
        base = 1e6
        quase = [base, math.nextafter(base, math.inf), base]
        assert sem_variacao_em_duas(quase, [base, base])
        assert not sem_variacao_em_duas([base, base + 0.01, base], [base, base])

    def test_abaixo_do_minimo_a_pergunta_da_constante_nao_se_faz(self):
        """O tamanho barra antes, com a frase dele."""
        assert not sem_variacao_em_duas([1.0], [1.0])
        assert not sem_variacao_em_duas([1.0], [1.0, 1.0], variancias_iguais=False)

    def test_o_wilcoxon_sem_valor(self):
        """O `not enough (non-missing) 'x' observations` do R."""
        with pytest.raises(ValueError, match="pelo menos 1 valor"):
            wilcoxon_uma_amostra([], 0)

    def test_o_wilcoxon_com_um_valor_so_roda_como_no_r(self):
        """`wilcox.test(30, mu = 25)`: V = 1, p = 1 — o R aceita, e aqui também."""
        resultado = wilcoxon_uma_amostra([30.0], 25)
        assert (resultado.estatistica, resultado.p, resultado.exato) == (1.0, 1.0, True)

    def test_o_wilcoxon_com_todos_iguais_a_referencia(self):
        """Sem diferença nenhuma, não há posto: o R devolve `NaN`, e aqui é recusa."""
        with pytest.raises(ValueError, match="iguais à referência"):
            wilcoxon_uma_amostra([25.0, 25.0, 25.0], 25)

    def test_o_wilcoxon_com_valor_ausente_ou_referencia_infinita(self):
        with pytest.raises(ValueError, match="ausente ou infinito"):
            wilcoxon_uma_amostra([1.0, math.nan, 3.0], 0)
        with pytest.raises(ValueError, match="número finito"):
            wilcoxon_uma_amostra([1.0, 2.0, 3.0], math.inf)

    def test_o_mann_whitney_com_um_grupo_vazio(self):
        with pytest.raises(ValueError, match="pelo menos 1 valor em cada grupo"):
            mann_whitney([], [1.0, 2.0])
        with pytest.raises(ValueError, match="pelo menos 1 valor em cada grupo"):
            mann_whitney([1.0, 2.0], [])

    def test_o_kruskal_wallis_com_um_grupo_so(self):
        """O `all observations are in the same group` do R."""
        with pytest.raises(ValueError, match="pelo menos 2 grupos"):
            kruskal_wallis([[1.0, 2.0, 3.0]])

    def test_o_kruskal_wallis_com_um_grupo_vazio(self):
        with pytest.raises(ValueError, match="pelo menos 1 valor em cada grupo"):
            kruskal_wallis([[1.0, 2.0], [], [3.0]])

    def test_o_kruskal_wallis_com_todos_os_valores_iguais(self):
        """O R devolve `NaN`: os postos são todos o mesmo, e a correção dos empates é zero."""
        with pytest.raises(ValueError, match="todos os valores são iguais"):
            kruskal_wallis([[5.0, 5.0], [5.0], [5.0, 5.0, 5.0]])

    def test_o_friedman_com_uma_medida(self):
        with pytest.raises(ValueError, match="o Friedman precisa de pelo menos 2 medidas"):
            friedman([[1.0, 2.0, 3.0]])

    def test_o_friedman_com_um_caso_como_o_r(self):
        """O `friedman.test` para com erro numa matriz de uma linha — aqui, com a frase."""
        with pytest.raises(ValueError, match="pelo menos 2 casos"):
            friedman([[1.0], [2.0], [3.0]])

    def test_o_friedman_com_tamanhos_diferentes(self):
        with pytest.raises(ValueError, match="os mesmos casos"):
            friedman([[1.0, 2.0, 3.0], [1.0, 2.0], [4.0, 5.0, 6.0]])

    def test_o_friedman_com_cada_caso_empatado_inteiro(self):
        """
        Cada caso com o mesmo valor nas três medidas — mesmo que os casos difiram entre
        si: não há o que ordenar, o denominador é zero, e o R devolve `NaN`.
        """
        iguais = [[1.0, 5.0, 9.0], [1.0, 5.0, 9.0], [1.0, 5.0, 9.0]]
        assert medidas_iguais_em_cada_caso(iguais)
        with pytest.raises(ValueError, match="o mesmo valor em todas as medidas"):
            friedman(iguais)

    def test_um_caso_empatado_nao_basta(self):
        """
        Um caso empatado não ordena nada, e os outros ordenam: o Friedman roda — o
        qui-quadrado é 4, como o do `friedman.test` sobre a mesma matriz.
        """
        medidas = [[1.0, 5.0, 2.0], [1.0, 6.0, 3.0], [1.0, 7.0, 4.0]]
        assert not medidas_iguais_em_cada_caso(medidas)
        assert friedman(medidas).estatistica == pytest.approx(4.0, rel=1e-15)

    def test_as_perguntas_das_barreiras_respondem_com_um_caso_so(self):
        """
        Quem recusa o caso único é o teste, com a frase dele; as perguntas que vêm antes
        respondem, para a barreira de quem chama ser a que o teste daria.
        """
        assert medidas_iguais_em_cada_caso([[5.0], [5.0], [5.0]])
        assert not medidas_iguais_em_cada_caso([[5.0], [6.0], [7.0]])
        assert not sem_variacao_entre_medidas([[5.0], [6.0], [7.0]])


# ── O contrato ──────────────────────────────────────────────────────────────


class TestContrato:
    def test_o_resultado_tem_a_forma_do_htest(self):
        resultado = t_uma_amostra(_dados("imc15"), 25)
        assert isinstance(resultado, Resultado)
        assert resultado.metodo == T_DE_STUDENT == "t de Student"
        assert resultado.nome_da_estatistica == "t"
        assert resultado.nome_da_estimativa == "média"
        assert resultado.calculo_do_p == "t de Student com n − 1 graus de liberdade"

    def test_o_resultado_e_imutavel(self):
        resultado = t_uma_amostra(_dados("dois"), 25)
        with pytest.raises(FrozenInstanceError):
            resultado.p = 0.0  # type: ignore[misc]

    def test_o_minimo_e_o_do_r(self):
        assert MINIMO_T == 2
        assert t_uma_amostra([24.0, 27.0], 25).gl == (1.0,)
        assert MINIMO_STUDENT == 3
        assert t_de_student([24.0], [27.0, 28.0]).gl == (1.0,)

    def test_a_anova_nao_estima_nada(self):
        """O `oneway.test` não tem `estimate` nem `conf.int`: com k grupos, não há uma diferença."""
        resultado = anova_de_um_fator(VARIOS_GRUPOS["plantas"])
        assert resultado.metodo == ANOVA == "ANOVA"
        assert resultado.nome_da_estatistica == "F"
        assert (resultado.estimativa, resultado.ic, resultado.referencia) == (None, None, None)
        assert resultado.calculo_do_p == "F com k − 1 e N − k graus de liberdade"

    def test_as_repetidas_devolvem_o_epsilon(self):
        """
        O único campo fora do `htest`: o ε que corrigiu os gl, que já saem corrigidos.
        Nos outros testes ele fica `None`.
        """
        resultado = anova_de_medidas_repetidas(_medidas("pas"))
        assert resultado.metodo == ANOVA_DE_MEDIDAS_REPETIDAS == "ANOVA de medidas repetidas"
        assert resultado.nome_da_estatistica == "F"
        assert (resultado.estimativa, resultado.ic) == (None, None)
        assert "Greenhouse-Geisser" in resultado.calculo_do_p
        assert 0 < resultado.epsilon < 1
        assert anova_de_welch(VARIOS_GRUPOS["plantas"]).epsilon is None
        assert t_uma_amostra(_dados("imc15"), 25).epsilon is None

    def test_a_de_welch_tambem_nao_estima_nada(self):
        resultado = anova_de_welch(VARIOS_GRUPOS["plantas"])
        assert resultado.metodo == ANOVA_DE_WELCH == "ANOVA de Welch"
        assert (resultado.estimativa, resultado.ic) == (None, None)
        assert "graus de liberdade do denominador de Welch" in resultado.calculo_do_p

    def test_o_de_welch_estima_a_diferenca(self):
        resultado = t_de_welch(*DUAS_AMOSTRAS["grupos"])
        assert resultado.metodo == T_DE_WELCH == "t de Welch"
        assert resultado.nome_da_estimativa == "diferença de médias"
        assert resultado.referencia == 0.0
        assert "Welch-Satterthwaite" in resultado.calculo_do_p

    def test_o_de_student_estima_a_diferenca(self):
        resultado = t_de_student(*DUAS_AMOSTRAS["grupos"])
        assert resultado.metodo == T_DE_STUDENT
        assert resultado.nome_da_estimativa == "diferença de médias"
        assert resultado.calculo_do_p == "t de Student com n₁ + n₂ − 2 graus de liberdade"

    def test_os_testes_de_postos_tem_a_forma_do_htest(self):
        """
        O nome da estatística é o do R — V, W, o qui-quadrado —, a estimativa tem o nome
        dela, e o caminho do p está em `exato` e escrito em `calculo_do_p`.
        """
        wilcoxon = wilcoxon_uma_amostra(_dados("imc15"), 25)
        assert (wilcoxon.metodo, wilcoxon.nome_da_estatistica) == (WILCOXON, "V")
        assert wilcoxon.nome_da_estimativa == "pseudomediana"
        assert (wilcoxon.exato, wilcoxon.calculo_do_p, wilcoxon.gl) == (True, "exato", ())
        mann = mann_whitney(*DUAS_DE_POSTOS["grupos"])
        assert (mann.metodo, mann.nome_da_estatistica) == (MANN_WHITNEY, "W")
        assert mann.nome_da_estimativa == "diferença de locação"
        for resultado, metodo in (
            (kruskal_wallis(KRUSKAL["plantas"]), KRUSKAL_WALLIS),
            (friedman(_friedman("pas")), FRIEDMAN),
        ):
            assert (resultado.metodo, resultado.nome_da_estatistica) == (metodo, "χ²")
            assert (resultado.estimativa, resultado.ic, resultado.exato) == (None, None, None)
            assert "correção para empates" in resultado.calculo_do_p

    def test_o_calculo_do_p_diz_por_que_saiu_aproximado(self):
        """O R escolhe o caminho em silêncio; a frase daqui diz o que o fechou."""
        assert wilcoxon_uma_amostra(_dados("sleep_dif"), 0).calculo_do_p == (
            "aproximado pela normal, com correção de continuidade, porque há empates e "
            "valores iguais à referência"
        )
        assert wilcoxon_uma_amostra(_irracionais(50), 5).calculo_do_p == (
            "aproximado pela normal, com correção de continuidade, porque há 50 valores "
            "ou mais"
        )
        assert mann_whitney(*DUAS_DE_POSTOS["cinquenta"]).calculo_do_p == (
            "aproximado pela normal, com correção de continuidade, porque há 50 valores "
            "ou mais num grupo"
        )
        assert mann_whitney(*DUAS_DE_POSTOS["sono"]).calculo_do_p == (
            "aproximado pela normal, com correção de continuidade, porque há empates"
        )

    def test_o_limite_do_exato_e_o_do_r(self):
        """O `exact <- (n < 50)`: 49 valores sem empate são exatos, 50 não."""
        assert LIMITE_DO_EXATO == 50
        assert wilcoxon_uma_amostra(_irracionais(49), 5).exato is True
        assert wilcoxon_uma_amostra(_irracionais(50), 5).exato is False

    def test_o_nivel_do_intervalo(self):
        """
        O t dá sempre o de 95%. Os testes de postos também, quando a distribuição o
        alcança; com quatro valores, o mais largo tem 88% — o R escreve o α alcançado em
        dois algarismos, 0,12, e avisa.
        """
        assert t_uma_amostra(_dados("imc15"), 25).confianca_do_ic == CONFIANCA
        assert t_de_welch(*DUAS_AMOSTRAS["grupos"]).confianca_do_ic == CONFIANCA
        assert wilcoxon_uma_amostra(_dados("imc15"), 25).confianca_do_ic == CONFIANCA
        assert wilcoxon_uma_amostra([1.2, 3.4, 2.2, 5.1], 0).confianca_do_ic == 0.88
        assert anova_de_welch(VARIOS_GRUPOS["plantas"]).confianca_do_ic is None

    def test_nenhum_nome_publico_comeca_com_test(self):
        """
        O `pytest` coleta como caso de teste qualquer objeto `test*` importado num
        arquivo de teste — a armadilha do `testar` da normalidade.
        """
        publicos = [nome for nome in dir(hipoteses) if not nome.startswith("_")]
        assert not [nome for nome in publicos if nome.lower().startswith("test")]

    def test_nao_importa_o_pandas(self):
        """A aritmética recebe números; quem abre o banco é a análise."""
        import ast
        import inspect

        arvore = ast.parse(inspect.getsource(hipoteses))
        importados = {
            alias.name.split(".")[0]
            for no in ast.walk(arvore)
            if isinstance(no, ast.Import)
            for alias in no.names
        } | {
            no.module.split(".")[0]
            for no in ast.walk(arvore)
            if isinstance(no, ast.ImportFrom) and no.module
        }
        assert "pandas" not in importados
