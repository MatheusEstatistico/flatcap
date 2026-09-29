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
  `PlantGrowth` e o `InsectSprays` são os bancos dos exemplos da documentação do R;
* o **exemplo da documentação do `t.test`**: os dados do sono de Student (1908), o
  `sleep` do R. O t pareado que a documentação imprime — t = 4,0621, 9 gl,
  p = 0,002833 — é o t de uma amostra sobre as diferenças, que é a razão de o motor
  morar fora da análise;
* as **fórmulas**, escritas aqui de novo com a biblioteca padrão: a média, o desvio e
  o erro-padrão pelo `statistics`, e só o quantil e a cauda da t pelo `scipy`.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import FrozenInstanceError

import pytest
from scipy import stats

import flatcap.hipoteses as hipoteses
from flatcap.hipoteses import (
    ANOVA,
    ANOVA_DE_MEDIDAS_REPETIDAS,
    ANOVA_DE_WELCH,
    CONFIANCA,
    MINIMO_STUDENT,
    MINIMO_T,
    T_DE_STUDENT,
    T_DE_WELCH,
    Resultado,
    anova_de_medidas_repetidas,
    anova_de_um_fator,
    anova_de_welch,
    sem_variacao,
    sem_variacao_em_duas,
    sem_variacao_entre_medidas,
    sem_variacao_nos_grupos,
    t_de_student,
    t_de_welch,
    t_uma_amostra,
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
