"""
Os testes do `hipoteses.py` — a aritmética, sem projeto, banco nem ficha.

**Nenhum número daqui é conferido contra o próprio módulo.** As referências são três,
e independentes dele:

* o **R 4.3.3**: `t.test(x, mu = mu)` rodado sobre os mesmos números, com o
  resultado copiado para `REFERENCIAS_DO_R` — o t, os graus de liberdade, o p, os dois
  limites do intervalo e a média;
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
    CONFIANCA,
    MINIMO_T,
    T_DE_STUDENT,
    Resultado,
    sem_variacao,
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

    def test_a_referencia_na_media_da_t_zero_e_p_um(self):
        resultado = t_uma_amostra(_dados("no_centro"), 3)
        assert (resultado.estatistica, resultado.p) == (0.0, 1.0)


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
