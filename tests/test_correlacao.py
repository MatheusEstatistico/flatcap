# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Os testes do `correlacao.py`.

O miolo é testado pela função pura `correlacionar(banco, ficha, linhas, pares)`, como
o `associar` da associação e o `avaliar` da normalidade. O caminho do disco — a
ficha com a lista `correlacao:`, a rodada escrita, o relatório que a encontra — usa
os fixtures do `conftest.py`.

**Nenhum número daqui é conferido contra o próprio módulo.** As referências são
quatro, e independentes dele:

* o **R 4.3.3**: `cor.test(x, y, method = m)` rodado sobre os mesmos números, com o
  resultado copiado para `REFERENCIAS_DO_R` — o coeficiente, a estatística com o
  nome que o R dá a ela, o p e, no Pearson, o intervalo;
* a **documentação do `cor.test`**: o exemplo do atum de Hollander e Wolfe, com os
  p unilaterais que ela publica;
* a **força bruta**: a distribuição exata do S de Spearman e do T de Kendall,
  contada permutação por permutação em frações exatas;
* as **fórmulas publicadas** dos intervalos do Spearman e do Kendall, escritas aqui
  de novo.

O banco de referência é o `bancos.para_correlacionar()`: sessenta casos e uma
variável para cada caminho da regra dos pressupostos.
"""

from __future__ import annotations

import math
from fractions import Fraction
from itertools import permutations
from statistics import NormalDist

import pandas as pd
import pytest
from scipy import stats

import bancos
from conftest import (
    AGORA,
    RECORD_ID,
    acrescentar_a_ficha,
    banco_em_memoria,
    ficha_em_memoria,
    linhas_do_historico,
)
from flatcap.correlacao import (
    KENDALL,
    LIMITE_EXATO_KENDALL,
    MAXIMO_EXATO_SPEARMAN,
    METODOS,
    PEARSON,
    POUCOS_VALORES,
    SPEARMAN,
    CategoricaSemCodigoError,
    ParInvalidoError,
    SemParesError,
    VariavelIncompativelError,
    calcular,
    correlacionar,
    executar_correlacao,
    intervalo,
    kendall,
    metodo_escrito,
    montar_manifesto,
    pares_da_ficha,
    pearson,
    preparar_correlacao,
    prho,
    spearman,
)
from flatcap.dicionario import CATEGORICA, DATA, IGNORAR, NUMERICA, Linha
from flatcap.manifesto import (
    ANALISE_CORRELACAO,
    ANALISE_NORMALIDADE,
    ARQUIVO_MANIFESTO,
    ORDEM_PADRAO_DAS_ANALISES,
)
from flatcap.manifesto import ler as ler_manifesto
from flatcap.normalidade import valor_p
from flatcap.projeto import ARQUIVO_PROJETO, PASTA_ANALISES, PASTA_ANTIGAS, PASTA_CORRELACAO

IDADE = Linha("idade", "Idade", NUMERICA)
IMC = Linha("imc", "IMC", NUMERICA)
RENDA = Linha("renda", "Renda", NUMERICA)
DOR = Linha("dor", "Dor", CATEGORICA, ("0", "1", "2", "3", "4", "5"))
ESCOLARIDADE = Linha("escolaridade", "Escolaridade", CATEGORICA)
SERVICO = Linha(
    "servico", "Serviço", CATEGORICA, ("1",), rotulos_das_categorias=(("1", "Ambulatório"),)
)
DICIONARIO = (IDADE, IMC, RENDA, DOR, ESCOLARIDADE, SERVICO)

# Um par para cada caminho da regra, na ordem em que a ficha os escreveria.
PARES = (("idade", "imc"), ("idade", "renda"), ("dor", "idade"))

# O que se escreve na ficha para o banco de referência do `conftest`, que tem
# `idade` e `imc` numéricas — as duas normais, e o par vai para o Pearson.
BLOCO = "correlacao:\n  - [idade, imc]\n"

# O exemplo da documentação do `cor.test`: Hollander e Wolfe (1973), a luminosidade
# de Hunter contra a nota do painel de consumidores em nove lotes de atum.
ATUM_X = [44.4, 45.9, 41.9, 53.3, 44.7, 44.1, 50.7, 45.2, 60.1]
ATUM_Y = [2.6, 3.1, 2.5, 5.0, 3.6, 4.0, 5.2, 2.8, 3.8]


def _sem_empate(n: int) -> tuple[list[float], list[float]]:
    """
    Uma permutação de 0..n−1 com um desvio que impede empate — o mesmo gerador que
    produziu os casos `sem_empate_*` no R. É o que põe um banco dos dois lados de
    cada limite do R: n = 49 e 50 no Kendall, 1290 e 1291 no Spearman.
    """
    return [float(i) for i in range(n)], [((i * 7919) % n) + i / (n + 1) for i in range(n)]


def _duas_escalas() -> tuple[list[float], list[float]]:
    """
    A `dor` do banco de referência contra uma segunda escala, de 0 a 4, tirada dela.
    As duas têm valores repetidos três vezes ou mais, que é o único caso em que o
    último termo da variância do Kendall — o `v2` do `cor.test` — não é zero.
    """
    dor = bancos.para_correlacionar()["dor"].tolist()
    outra = [min(4, max(0, d + ((i * 5) % 3) - 1)) for i, d in enumerate(dor)]
    return [float(d) for d in dor], [float(o) for o in outra]


def _dados(caso: str) -> tuple[list[float], list[float]]:
    quadro = bancos.para_correlacionar()
    pares = {
        "idade_imc": ("idade", "imc"),
        "idade_renda": ("idade", "renda"),
        "dor_idade": ("dor", "idade"),
        "imc_renda": ("imc", "renda"),
    }
    if caso in pares:
        a, b = pares[caso]
        completos = quadro[[a, b]].dropna()
        return completos[a].tolist(), completos[b].tolist()
    if caso.startswith("idade_renda_"):
        cabeca = quadro.head(int(caso.rsplit("_", 1)[1]))
        return cabeca["idade"].tolist(), cabeca["renda"].tolist()
    if caso.startswith("sem_empate_"):
        return _sem_empate(int(caso.rsplit("_", 1)[1]))
    if caso == "duas_escalas":
        return _duas_escalas()
    assert caso == "atum"
    return ATUM_X, ATUM_Y


# `cor.test(x, y, method = m)` no R 4.3.3, sobre os números de `_dados(caso)`:
#
#     (caso, método, estimativa, estatística, valor, p, IC 95% do Pearson)
#
# Os casos cobrem os caminhos de cada método: o Spearman exato pelas permutações
# (n = 9), pela série de Edgeworth (n = 12, 49, 60 e 1290) e pela aproximação t (com
# empates, e em n = 1291); o Kendall exato (n = 9, 12 e 49) e pela aproximação
# normal (com empates numa das variáveis, nas duas, e em n = 50).
REFERENCIAS_DO_R = [
    ("idade_imc", "pearson", 0.682346521581946, "t", 6.92232191410233, 5.05617145902812e-09,
     (0.512986559105305, 0.800574148613513)),
    ("idade_imc", "spearman", 0.600379186933682, "S", 12330.6998079743, 7.94660374543341e-07,
     None),
    ("idade_imc", "kendall", 0.468191812397775, "z", 5.14235698877931, 2.71312953802991e-07,
     None),
    ("idade_renda", "pearson", 0.459809291921412, "t", 3.94339356597116, 0.000218992061236352,
     (0.233100715174073, 0.639113105357184)),
    ("idade_renda", "spearman", 0.460405668241178, "S", 19420, 0.000250703075464788, None),
    ("idade_renda", "kendall", 0.336723163841808, "z", 3.80124511269395, 0.000143970791588012,
     None),
    ("dor_idade", "pearson", 0.773470977524615, "t", 9.29360159828287, 4.36178410996568e-13,
     (0.646526213802438, 0.858736852819173)),
    ("dor_idade", "spearman", 0.735310586239028, "S", 9526.17200125739, 2.22449262603928e-11,
     None),
    ("dor_idade", "kendall", 0.610881874352969, "z", 6.39036820933173, 1.65486779372007e-10,
     None),
    ("imc_renda", "pearson", 0.299353555419979, "t", 2.32676560100348, 0.0236882405950123,
     (0.0420672202824556, 0.519406538576897)),
    ("imc_renda", "spearman", 0.278653724656183, "S", 22257.8606720088, 0.0358211946263755,
     None),
    ("imc_renda", "kendall", 0.193669705530003, "z", 2.12715971825008, 0.0334068147887126,
     None),
    ("idade_renda_12", "pearson", 0.203753534634541, "t", 0.658131389663402, 0.52531441917446,
     (-0.419162650166217, 0.696240615258045)),
    ("idade_renda_12", "spearman", 0.174825174825175, "S", 236, 0.588259894923335, None),
    ("idade_renda_12", "kendall", 0.151515151515152, "T", 38, 0.545204700777618, None),
    ("idade_renda_9", "pearson", 0.466981054943144, "t", 1.39721972026036, 0.205039919010034,
     (-0.28576586546464, 0.863350060943273)),
    ("idade_renda_9", "spearman", 0.5, "S", 60, 0.177662037037037, None),
    ("idade_renda_9", "kendall", 0.444444444444445, "T", 26, 0.1194389329806, None),
    ("sem_empate_49", "pearson", 0.0998204845465779, "t", 0.687769856275548, 0.494978119599806,
     (-0.18661420878935, 0.370614232772823)),
    ("sem_empate_49", "spearman", 0.08, "S", 18032, 0.583716221301241, None),
    ("sem_empate_49", "kendall", 0.0612244897959184, "T", 624, 0.5424885542387, None),
    ("sem_empate_50", "pearson", 0.0974713292014106, "t", 0.678532121670433, 0.500692795383061,
     (-0.185920586270992, 0.365892058784181)),
    ("sem_empate_50", "spearman", 0.078031212484994, "S", 19200, 0.589106008957766, None),
    ("sem_empate_50", "kendall", 0.0595918367346939, "z", 0.610634617073511, 0.541441499971367,
     None),
    ("sem_empate_1290", "pearson", 0.00488190409127815, "t", 0.175207361685171,
     0.860944238427262, (-0.0497105232150645, 0.0594452468065114)),
    ("sem_empate_1290", "spearman", 0.00410732774913031, "S", 356311760, 0.882817022942977,
     None),
    ("sem_empate_1290", "kendall", 0.00333531792568002, "z", 0.179446310964695,
     0.857587270594155, None),
    ("sem_empate_1291", "pearson", 0.00665631444995146, "t", 0.2389845966535,
     0.811155517107168, (-0.0479191199600831, 0.0611921245202895)),
    ("sem_empate_1291", "spearman", 0.00588235294117647, "S", 356504486, 0.832767957450996,
     None),
    ("sem_empate_1291", "kendall", 0.00511231603408211, "z", 0.275158993440796,
     0.783194089842329, None),
    ("duas_escalas", "pearson", 0.845311347312456, "t", 12.0494338305184, 1.98978450589277e-17,
     (0.753018660912765, 0.904985126096529)),
    ("duas_escalas", "spearman", 0.849934656431912, "S", 5400.8517150155, 8.82867856570109e-18,
     None),
    ("duas_escalas", "kendall", 0.757558581184679, "z", 7.25353233816674, 4.06040378793591e-13,
     None),
    ("atum", "pearson", 0.571181557563829, "t", 1.84108263811534, 0.108173054349494,
     (-0.149742633036757, 0.895579461838739)),
    ("atum", "spearman", 0.6, "S", 48, 0.0967978395061728, None),
    ("atum", "kendall", 0.444444444444445, "T", 26, 0.1194389329806, None),
]


def _correlacionar(quadro=None, linhas=DICIONARIO, pedidos=PARES, **opcoes):
    quadro = bancos.para_correlacionar() if quadro is None else quadro
    return correlacionar(
        banco_em_memoria(quadro), ficha_em_memoria(), linhas, pedidos, AGORA, **opcoes
    )


def _par(resultado, variavel_1: str, variavel_2: str):
    return next(
        par
        for par in resultado.pares
        if (par.variavel_1, par.variavel_2) == (variavel_1, variavel_2)
    )


def _duas_casas(valor: float) -> str:
    """O coeficiente como a tabela o escreve — escrito aqui de novo, e não importado."""
    texto = f"{valor:.2f}"
    return ("0.00" if float(texto) == 0 else texto).replace(".", ",")


# ── O R ─────────────────────────────────────────────────────────────────────


class TestReferenciasDoR:
    @pytest.mark.parametrize(
        ("caso", "metodo", "estimativa", "nome", "estatistica", "p", "ic"),
        REFERENCIAS_DO_R,
        ids=[f"{caso}-{metodo}" for caso, metodo, *_ in REFERENCIAS_DO_R],
    )
    def test_o_cor_test_do_r(self, caso, metodo, estimativa, nome, estatistica, p, ic):
        x, y = _dados(caso)
        resultado = calcular(METODOS[metodo], x, y)
        assert resultado.valor == pytest.approx(estimativa, abs=1e-12)
        assert resultado.nome_da_estatistica == nome
        assert resultado.estatistica == pytest.approx(estatistica, rel=1e-10)
        assert resultado.p == pytest.approx(p, rel=1e-9, abs=1e-15)
        if ic is not None:
            assert resultado.ic == pytest.approx(ic, abs=1e-12)

    def test_os_p_unilaterais_publicados_na_documentacao(self):
        """
        A documentação do `cor.test` publica os unilaterais do atum: 0,05409 no
        Pearson, 0,0484 no Spearman e 0,05972 no Kendall exato. Com o coeficiente
        positivo, o bilateral é o dobro.
        """
        assert pearson(ATUM_X, ATUM_Y).p / 2 == pytest.approx(0.05409, abs=5e-6)
        assert spearman(ATUM_X, ATUM_Y).p / 2 == pytest.approx(0.0484, abs=5e-5)
        assert kendall(ATUM_X, ATUM_Y).p / 2 == pytest.approx(0.05972, abs=5e-6)
        assert pearson(ATUM_X, ATUM_Y).ic[0] == pytest.approx(-0.1497426, abs=1e-7)

    def test_o_scipy_da_outro_p_no_spearman_e_por_isso_o_as89_esta_aqui(self):
        """
        O `spearmanr` usa sempre a aproximação t: 0,088 no atum, onde o R dá 0,097.
        Se um dia ele passar a dar o do R, o AS 89 transcrito pode sair.
        """
        do_scipy = stats.spearmanr(ATUM_X, ATUM_Y).pvalue
        assert do_scipy == pytest.approx(0.0876, abs=1e-4)
        assert spearman(ATUM_X, ATUM_Y).p == pytest.approx(0.0968, abs=1e-4)

    def test_o_criterio_do_kendall_exato_e_o_do_r_e_nao_o_do_scipy(self):
        """
        O R é exato abaixo de n = 50 sem empates; o critério automático do `scipy`
        passa para a aproximação acima de 33.
        """
        x, y = _sem_empate(40)
        assert kendall(x, y).nome_da_estatistica == "T"
        assert kendall(x, y).calculo_do_p == "exato"
        x, y = _sem_empate(LIMITE_EXATO_KENDALL)
        assert kendall(x, y).nome_da_estatistica == "z"

    def test_o_limite_do_spearman_exato(self):
        x, y = _sem_empate(MAXIMO_EXATO_SPEARMAN)
        assert "Edgeworth" in spearman(x, y).calculo_do_p
        x, y = _sem_empate(MAXIMO_EXATO_SPEARMAN + 1)
        assert "aproximação t" in spearman(x, y).calculo_do_p


# ── O AS 89 e o Kendall exato, contra a força bruta ─────────────────────────


def _s_de_cada_permutacao(n: int) -> list[int]:
    return [
        sum((i - v) ** 2 for i, v in enumerate(permutacao))
        for permutacao in permutations(range(n))
    ]


def _concordantes(xs, ys) -> int:
    return sum(
        1
        for i in range(len(xs))
        for j in range(i + 1, len(xs))
        if (xs[i] - xs[j]) * (ys[i] - ys[j]) > 0
    )


class TestExatos:
    @pytest.mark.parametrize("n", [3, 4, 5, 6, 7, 8])
    def test_o_as89_ate_n_9_e_a_contagem_das_permutacoes(self, n):
        todos = _s_de_cada_permutacao(n)
        total = math.factorial(n)
        for s in range(0, n * (n * n - 1) // 3 + 1, 2):
            acima = Fraction(sum(1 for valor in todos if valor >= s), total)
            if s > 0:
                assert prho(n, s, inferior=False) == pytest.approx(float(acima), abs=1e-15)
                assert prho(n, s, inferior=True) == pytest.approx(float(1 - acima), abs=1e-15)

    def test_as_duas_saidas_do_comeco_do_as89(self):
        """`is <= 0` e `is` acima do máximo: as duas voltam antes de contar nada."""
        assert prho(8, 0, inferior=False) == 1.0
        assert prho(8, 0, inferior=True) == 0.0
        assert prho(8, 200, inferior=False) == 0.0
        assert prho(8, 200, inferior=True) == 1.0
        assert prho(30, 10**9, inferior=False) == 0.0

    def test_a_serie_de_edgeworth_fica_entre_0_e_1(self):
        for s in (1, 2, 50, 4000, 8990):
            assert 0.0 <= prho(30, s, inferior=False) <= 1.0
            assert 0.0 <= prho(30, s, inferior=True) <= 1.0

    @pytest.mark.parametrize("n", [4, 5, 6, 7])
    def test_o_spearman_bilateral_ate_n_9_e_a_forca_bruta(self, n):
        """
        O p bilateral do R pela definição: o dobro da cauda do lado em que o S
        observado caiu, contada em todas as permutações.
        """
        todos = _s_de_cada_permutacao(n)
        total = math.factorial(n)
        centro = (n**3 - n) / 6
        for permutacao in list(permutations(range(n)))[:: max(1, total // 40)]:
            y = [float(v) for v in permutacao]
            s = sum((i - v) ** 2 for i, v in enumerate(permutacao))
            if s > centro:
                cauda = Fraction(sum(1 for v in todos if v >= s), total)
            else:
                cauda = Fraction(sum(1 for v in todos if v <= s), total)
            esperado = min(Fraction(1), 2 * cauda)
            x = [float(i) for i in range(n)]
            if len(set(y)) > 1:
                assert spearman(x, y).p == pytest.approx(float(esperado), abs=1e-12)

    @pytest.mark.parametrize("n", [4, 5, 6, 7])
    def test_o_kendall_exato_e_a_forca_bruta(self, n):
        x = list(range(n))
        todas = [_concordantes(x, p) for p in permutations(range(n))]
        total = math.factorial(n)
        pares = n * (n - 1) / 4
        for permutacao in list(permutations(range(n)))[:: max(1, total // 40)]:
            t = _concordantes(x, permutacao)
            if t > pares:
                cauda = Fraction(sum(1 for v in todas if v >= t), total)
            else:
                cauda = Fraction(sum(1 for v in todas if v <= t), total)
            esperado = min(Fraction(1), 2 * cauda)
            resultado = kendall([float(v) for v in x], [float(v) for v in permutacao])
            assert resultado.p == pytest.approx(float(esperado), abs=1e-12)
            assert resultado.estatistica == t


# ── O intervalo ─────────────────────────────────────────────────────────────


def _fisher(r: float, erro: float) -> tuple[float, float]:
    z = NormalDist().inv_cdf(0.975)
    return math.tanh(math.atanh(r) - z * erro), math.tanh(math.atanh(r) + z * erro)


class TestIntervalo:
    def test_o_do_spearman_e_o_de_bonett_e_wright(self):
        x, y = _dados("idade_renda")
        rho = spearman(x, y).valor
        esperado = _fisher(rho, math.sqrt((1 + rho**2 / 2) / (len(x) - 3)))
        assert spearman(x, y).ic == pytest.approx(esperado, abs=1e-12)

    def test_o_do_kendall_e_o_de_fieller_hartley_e_pearson(self):
        x, y = _dados("dor_idade")
        tau = kendall(x, y).valor
        esperado = _fisher(tau, math.sqrt(0.437 / (len(x) - 4)))
        assert kendall(x, y).ic == pytest.approx(esperado, abs=1e-12)

    def test_o_do_spearman_e_mais_largo_que_o_do_pearson_para_o_mesmo_coeficiente(self):
        """É o motivo de não usar o erro-padrão do Pearson nos outros dois."""
        baixo_p, alto_p = intervalo(PEARSON, 0.5, 40)
        baixo_s, alto_s = intervalo(SPEARMAN, 0.5, 40)
        assert alto_s - baixo_s > alto_p - baixo_p

    def test_sem_intervalo_quando_o_n_nao_da(self):
        """O R não dá intervalo ao Pearson com n = 3; o Kendall precisa de n > 4."""
        assert intervalo(PEARSON, 0.5, 3) is None
        assert intervalo(SPEARMAN, 0.5, 3) is None
        assert intervalo(KENDALL, 0.5, 4) is None
        assert intervalo(PEARSON, 0.5, 4) is not None
        assert pearson([1.0, 2.0, 4.0], [1.0, 3.0, 2.0]).ic is None

    def test_coeficiente_1_da_o_proprio_ponto_como_no_r(self):
        """
        Nem o R chega a 1 exato numa reta perfeita — `cor(1:5, 2 * (1:5))` dá
        0,99999999999999978, e o `cor.test` sai com t = 82191237 e o intervalo
        `1 1`. O que importa é o que se imprime.
        """
        assert intervalo(PEARSON, 1.0, 10) == (1.0, 1.0)
        assert intervalo(KENDALL, -1.0, 10) == (-1.0, -1.0)
        quadro = pd.DataFrame({"a": [1.0, 2.0, 3.0, 4.0, 5.0], "b": [2.0, 4.0, 6.0, 8.0, 10.0]})
        linhas = (Linha("a", "A", NUMERICA), Linha("b", "B", NUMERICA))
        par = _correlacionar(quadro, linhas, (("a", "b", "pearson"),))
        assert par.tabela.linhas[0][4:] == ("1,00", "1,00 a 1,00", "< 0,001")


# ── A regra ─────────────────────────────────────────────────────────────────


class TestRegra:
    def test_as_duas_normais_vao_para_o_pearson(self):
        par = _par(_correlacionar(), "idade", "imc")
        assert par.metodo == PEARSON
        assert par.escolha.motivo == (
            "o Shapiro-Wilk não rejeita a normal em nenhuma das duas (p = 1,000 e 0,935)"
        )

    def test_a_normal_rejeitada_vai_para_o_spearman(self):
        par = _par(_correlacionar(), "idade", "renda")
        assert par.metodo == SPEARMAN
        assert par.escolha.motivo == "o Shapiro-Wilk rejeita a normal em Renda (p < 0,001)"

    def test_a_escala_vai_para_o_kendall(self):
        par = _par(_correlacionar(), "dor", "idade")
        assert par.metodo == KENDALL
        assert par.escolha.motivo.startswith("Dor tem 6 valores distintos")

    def test_numerica_de_poucos_valores_tambem_e_escala(self):
        quadro = pd.DataFrame({"a": [1, 2, 3, 4] * 10, "b": [float(i) for i in range(40)]})
        linhas = (Linha("a", "A", NUMERICA), Linha("b", "B", NUMERICA))
        par = _correlacionar(quadro, linhas, (("a", "b"),)).pares[0]
        assert par.metodo == KENDALL
        assert par.escolha.motivo.startswith("A tem 4 valores distintos")

    def test_poucos_valores_sem_repeticao_nao_e_escala(self):
        """
        Com oito casos, uma contínua tem no máximo oito valores e nenhum empate: não
        é escala, e a regra segue para o Shapiro-Wilk.
        """
        x, y = _dados("idade_renda_9")
        quadro = pd.DataFrame({"a": x[:8], "b": y[:8]})
        linhas = (Linha("a", "A", NUMERICA), Linha("b", "B", NUMERICA))
        par = _correlacionar(quadro, linhas, (("a", "b"),)).pares[0]
        assert par.metodo != KENDALL
        assert "Shapiro-Wilk" in par.escolha.motivo

    def test_o_limite_e_o_mesmo_da_normalidade_e_do_perfil(self):
        """A mesma pergunta — isto é contínuo ou é código? — com um limite só."""
        from flatcap.normalidade import POUCOS_DISTINTOS
        from flatcap.perfil import LIMITE_UNICOS_CODIGO

        assert POUCOS_VALORES == POUCOS_DISTINTOS == LIMITE_UNICOS_CODIGO

    def test_categorica_de_muitos_codigos_vai_para_o_spearman_e_nunca_para_o_pearson(self):
        quadro = pd.DataFrame(
            {"escore": [i % 15 for i in range(60)], "idade": bancos.para_correlacionar()["idade"]}
        )
        linhas = (Linha("escore", "Escore", CATEGORICA), IDADE)
        par = _correlacionar(quadro, linhas, (("escore", "idade"),)).pares[0]
        assert par.metodo == SPEARMAN
        assert par.escolha.motivo == "Escore é categórica, e entra pela ordem dos códigos"

    def test_a_normalidade_e_medida_sobre_os_casos_do_par(self):
        """
        `idade` tem 60 valores, e só 57 entram no par com `imc`: o Shapiro-Wilk da
        escolha é o dos 57.
        """
        quadro = bancos.para_correlacionar()
        completos = quadro[["idade", "imc"]].dropna()
        par = _par(_correlacionar(), "idade", "imc")
        assert par.pressupostos.normal_1.p == pytest.approx(
            stats.shapiro(completos["idade"]).pvalue, abs=1e-12
        )
        assert par.pressupostos.normal_2.p == pytest.approx(
            stats.shapiro(completos["imc"]).pvalue, abs=1e-12
        )

    def test_pearson_com_menos_de_20_pares_avisa(self):
        x, y = _dados("idade_imc")
        quadro = pd.DataFrame({"a": x[:15], "b": y[:15]})
        linhas = (Linha("a", "A", NUMERICA), Linha("b", "B", NUMERICA))
        resultado = _correlacionar(quadro, linhas, (("a", "b"),))
        assert resultado.pares[0].metodo == PEARSON
        assert any("Pearson com 15 pares" in aviso for aviso in resultado.avisos)

    def test_a_escolha_de_cada_par_esta_escrita_na_nota(self):
        texto = _correlacionar().tabela.texto()
        assert (
            "Idade × IMC: n = 57; o Shapiro-Wilk não rejeita a normal em nenhuma das duas "
            "(p = 1,000 e 0,935) → Pearson (t = 6,92; 55 gl)." in texto
        )
        assert "Idade × Renda: n = 60; o Shapiro-Wilk rejeita a normal em Renda (p < 0,001)" in (
            texto
        )
        assert "→ Kendall (z = 6,39)." in texto


# ── O método escrito na ficha ───────────────────────────────────────────────


class TestMetodoNaFicha:
    def test_o_metodo_escrito_manda_e_a_nota_diz_o_que_a_regra_faria(self):
        resultado = _correlacionar(pedidos=(("idade", "renda", "pearson"),))
        par = resultado.pares[0]
        assert par.metodo == PEARSON
        assert par.escolha.contra_a_regra
        assert par.escolha.da_regra == SPEARMAN
        assert (
            "Pearson escrito na ficha (t = 3,94; 58 gl), contra a regra — ela escolheria "
            "Spearman: o Shapiro-Wilk rejeita a normal em Renda (p < 0,001)."
        ) in par.justificativa
        assert any("contra a regra" in aviso for aviso in resultado.avisos)

    def test_o_metodo_igual_ao_da_regra_nao_avisa(self):
        resultado = _correlacionar(pedidos=(("idade", "renda", "spearman"),))
        par = resultado.pares[0]
        assert par.escolha.pela_ficha and not par.escolha.contra_a_regra
        assert "o mesmo que a regra escolheria" in par.justificativa
        assert not any("contra a regra" in aviso for aviso in resultado.avisos)

    def test_o_kendall_escrito_vale_numa_numerica_continua(self):
        par = _correlacionar(pedidos=(("idade", "imc", "kendall"),)).pares[0]
        x, y = _dados("idade_imc")
        assert par.coeficiente.valor == pytest.approx(kendall(x, y).valor)

    def test_pearson_escrito_sobre_uma_categorica_recusa(self):
        with pytest.raises(ParInvalidoError) as erro:
            _correlacionar(pedidos=(("dor", "idade", "pearson"),))
        assert "Pearson supõe variável numérica, e `dor` está marcada `categorica`" in str(
            erro.value
        )

    def test_o_metodo_se_escreve_de_qualquer_jeito(self):
        assert metodo_escrito("Spearman") == SPEARMAN
        assert metodo_escrito(" KENDALL ") == KENDALL
        assert metodo_escrito("pearsón") == PEARSON
        assert metodo_escrito("spearmann") == ""
        assert metodo_escrito("idade") == ""


# ── A categórica ────────────────────────────────────────────────────────────


class TestCategorica:
    def test_a_escala_entra_pela_ordem_dos_codigos(self):
        """
        O coeficiente é o dos códigos como estão no banco — `0 < 1 < … < 5` —, sem
        passar pela ordem do `categorias_ordem`.
        """
        embaralhada = Linha("dor", "Dor", CATEGORICA, ("3", "0", "5", "1", "4", "2"))
        linhas = (IDADE, IMC, RENDA, embaralhada, ESCOLARIDADE, SERVICO)
        par = _par(_correlacionar(linhas=linhas), "dor", "idade")
        x, y = _dados("dor_idade")
        assert par.coeficiente.valor == pytest.approx(kendall(x, y).valor, abs=1e-12)

    def test_o_codigo_lido_como_decimal_entra_igual(self):
        """Uma célula vazia faz a coluna de código chegar decimal: `1.0` é `1`."""
        quadro = bancos.para_correlacionar()
        quadro["dor"] = quadro["dor"].astype("float64")
        quadro.loc[7, "dor"] = None
        par = _par(_correlacionar(quadro), "dor", "idade")
        assert (par.validos, par.metodo) == (59, KENDALL)

    def test_categorica_em_texto_recusa_e_diz_como_resolver(self):
        with pytest.raises(CategoricaSemCodigoError) as erro:
            _correlacionar(pedidos=(("escolaridade", "idade"),))
        mensagem = str(erro.value)
        assert "escolaridade — valores: Fundamental · Médio · Superior" in mensagem
        assert "1=Fundamental|2=Médio|3=Superior" in mensagem

    def test_o_agrupamento_do_dicionario_avisa_e_nao_muda_a_escala(self):
        agrupada = Linha(
            "dor",
            "Dor",
            CATEGORICA,
            ("0", "1", "2", "3", "4", "5"),
            rotulos_das_categorias=(("0", "Nenhuma"), ("1", "Leve"), ("2", "Leve")),
        )
        linhas = (IDADE, IMC, RENDA, agrupada, ESCOLARIDADE, SERVICO)
        resultado = _correlacionar(linhas=linhas)
        assert any("junta códigos num rótulo só (`1=Leve|2=Leve`)" in a for a in resultado.avisos)
        x, y = _dados("dor_idade")
        assert _par(resultado, "dor", "idade").coeficiente.valor == pytest.approx(
            kendall(x, y).valor, abs=1e-12
        )


# ── Quando não há teste ─────────────────────────────────────────────────────


class TestSemTeste:
    def test_um_valor_so(self):
        resultado = _correlacionar(pedidos=(("idade", "servico"),))
        assert resultado.tabela.linhas == (
            ("Idade", "Serviço", "60", "não testado: um valor só em Serviço", "—", "—", "—"),
        )
        assert any("critério de inclusão" in aviso for aviso in resultado.avisos)
        assert resultado.graficos == ()

    def test_ninguem_respondeu_as_duas(self):
        quadro = pd.DataFrame({"a": [1.0, 2.0, None, None], "b": [None, None, 3.0, 4.0]})
        linhas = (Linha("a", "A", NUMERICA), Linha("b", "B", NUMERICA))
        linha = _correlacionar(quadro, linhas, (("a", "b"),)).tabela.linhas[0]
        assert linha[2:4] == ("0", "não testado: nenhum caso com resposta nas duas variáveis")

    def test_menos_de_tres_pares(self):
        quadro = pd.DataFrame({"a": [1.0, 2.0, 3.0, None], "b": [5.0, 1.0, None, 2.0]})
        linhas = (Linha("a", "A", NUMERICA), Linha("b", "B", NUMERICA))
        linha = _correlacionar(quadro, linhas, (("a", "b"),)).tabela.linhas[0]
        assert "o teste precisa de pelo menos 3" in linha[3]

    def test_as_funcoes_recusam_o_que_nao_da_correlacao(self):
        with pytest.raises(ValueError, match="não varia"):
            pearson([1.0, 1.0, 1.0], [1.0, 2.0, 3.0])
        with pytest.raises(ValueError, match="pelo menos 3"):
            spearman([1.0, 2.0], [2.0, 1.0])


# ── As recusas ──────────────────────────────────────────────────────────────


class TestRecusas:
    def test_sem_pares_recusa_e_ensina_as_tres_formas(self):
        with pytest.raises(SemParesError) as erro:
            _correlacionar(pedidos=())
        mensagem = str(erro.value)
        assert "- [idade, imc]" in mensagem
        assert "- idade: [pressao, colesterol]" in mensagem
        assert "- [dor, ansiedade, kendall]" in mensagem
        assert "idade, imc, renda" in mensagem
        assert "435" in mensagem

    def test_data_recusa(self):
        linhas = (*DICIONARIO, Linha("coleta", "Coleta", DATA))
        quadro = bancos.para_correlacionar().assign(coleta="01/02/2026")
        with pytest.raises(ParInvalidoError, match="`coleta` está marcada `data`"):
            _correlacionar(quadro, linhas, (("idade", "coleta"),))

    def test_a_mesma_variavel_duas_vezes(self):
        with pytest.raises(ParInvalidoError, match="a mesma variável duas vezes"):
            _correlacionar(pedidos=(("idade", "idade"),))

    def test_nome_fora_do_dicionario(self):
        with pytest.raises(ParInvalidoError, match="`idad` não está no dicionario.csv"):
            _correlacionar(pedidos=(("idad", "imc"),))

    def test_o_mesmo_par_em_outra_ordem_ou_com_outro_metodo(self):
        """Correlacionar o mesmo par duas vezes é ficar com o p que convier."""
        with pytest.raises(ParInvalidoError, match=r"repete \[idade, renda\]"):
            _correlacionar(pedidos=(("idade", "renda"), ("renda", "idade", "kendall")))

    def test_ignorar_e_fora_do_banco(self):
        linhas = (
            *DICIONARIO,
            Linha("prontuario", "Prontuário", IGNORAR),
            Linha("peso", "Peso", NUMERICA, no_banco=False),
        )
        with pytest.raises(ParInvalidoError) as erro:
            _correlacionar(linhas=linhas, pedidos=(("idade", "prontuario"), ("idade", "peso")))
        assert "marcada `ignorar`" in str(erro.value)
        assert "no_banco = nao" in str(erro.value)

    def test_todos_os_problemas_de_uma_vez(self):
        with pytest.raises(ParInvalidoError) as erro:
            _correlacionar(
                pedidos=(("idade", "idade"), ("idad", "imc"), ("dor", "renda", "pearson"))
            )
        mensagem = str(erro.value)
        assert "3 par(es)" in mensagem
        assert "[idade, idade]" in mensagem and "[idad, imc]" in mensagem
        assert "[dor, renda, pearson]" in mensagem

    def test_numerica_que_chegou_como_texto(self):
        """A recusa da descritiva, pela mesma função."""
        quadro = bancos.para_correlacionar().assign(renda=lambda q: q["renda"].astype(str))
        with pytest.raises(VariavelIncompativelError, match="chegou como texto"):
            _correlacionar(quadro)


# ── A lista da ficha ────────────────────────────────────────────────────────


class TestFicha:
    def test_sem_a_chave_devolve_vazio(self, projeto_vazio):
        assert pares_da_ficha(projeto_vazio) == ()

    def test_as_tres_formas_na_ordem_em_que_foram_escritas(self, projeto_vazio):
        acrescentar_a_ficha(
            projeto_vazio,
            "correlacao:\n"
            "  - [idade, imc]\n"
            "  - idade: [pressao, colesterol]\n"
            "  - [dor, ansiedade, Kendall]\n",
        )
        assert [
            (p.primeira, p.segunda, p.metodo) for p in pares_da_ficha(projeto_vazio)
        ] == [
            ("idade", "imc", ""),
            ("idade", "pressao", ""),
            ("idade", "colesterol", ""),
            ("dor", "ansiedade", KENDALL),
        ]

    def test_uma_contra_varias_em_bloco_e_um_nome_so(self, projeto_vazio):
        acrescentar_a_ficha(
            projeto_vazio,
            "correlacao:\n  - idade:\n      - imc\n      - renda\n  - dor: ansiedade\n",
        )
        assert [(p.primeira, p.segunda) for p in pares_da_ficha(projeto_vazio)] == [
            ("idade", "imc"),
            ("idade", "renda"),
            ("dor", "ansiedade"),
        ]

    def test_o_terceiro_nome_que_nao_e_metodo_recusa_e_mostra_a_outra_forma(self, projeto_vazio):
        acrescentar_a_ficha(projeto_vazio, "correlacao:\n  - [idade, imc, renda]\n")
        with pytest.raises(ParInvalidoError) as erro:
            pares_da_ficha(projeto_vazio)
        assert "`renda` não é um método" in str(erro.value)
        assert "`- idade: [imc, renda]`" in str(erro.value)

    def test_metodo_com_erro_de_digitacao_recusa(self, projeto_vazio):
        acrescentar_a_ficha(projeto_vazio, "correlacao:\n  - [idade, imc, spearmann]\n")
        with pytest.raises(ParInvalidoError, match="`spearmann` não é um método"):
            pares_da_ficha(projeto_vazio)

    def test_metodo_na_forma_uma_contra_varias_recusa_e_ensina(self, projeto_vazio):
        acrescentar_a_ficha(projeto_vazio, "correlacao:\n  - idade: [imc, spearman]\n")
        with pytest.raises(ParInvalidoError) as erro:
            pares_da_ficha(projeto_vazio)
        assert "`spearman` é um método" in str(erro.value)
        assert "`- [idade, imc, spearman]`" in str(erro.value)

    def test_quatro_nomes_recusa(self, projeto_vazio):
        acrescentar_a_ficha(projeto_vazio, "correlacao:\n  - [idade, imc, renda, dor]\n")
        with pytest.raises(ParInvalidoError, match="4 nomes; um par tem dois"):
            pares_da_ficha(projeto_vazio)

    def test_lista_vazia_depois_dos_dois_pontos_recusa(self, projeto_vazio):
        acrescentar_a_ficha(projeto_vazio, "correlacao:\n  - idade: []\n")
        with pytest.raises(ParInvalidoError, match="pelo menos um nome"):
            pares_da_ficha(projeto_vazio)

    def test_texto_solto_recusa_com_as_formas(self, projeto_vazio):
        acrescentar_a_ficha(projeto_vazio, "correlacao:\n  - idade x imc\n")
        with pytest.raises(ParInvalidoError) as erro:
            pares_da_ficha(projeto_vazio)
        assert "1º item: `idade x imc`" in str(erro.value)
        assert "- [dor, ansiedade, kendall]" in str(erro.value)

    def test_a_chave_que_nao_e_lista(self, projeto_vazio):
        acrescentar_a_ficha(projeto_vazio, "correlacao: idade\n")
        with pytest.raises(ParInvalidoError, match="deveria ser uma lista"):
            pares_da_ficha(projeto_vazio)


# ── A tabela ────────────────────────────────────────────────────────────────


class TestATabela:
    def test_as_sete_colunas(self):
        assert _correlacionar().tabela.colunas == (
            "variável 1",
            "variável 2",
            "n",
            "método",
            "coeficiente",
            "IC 95%",
            "p-valor",
        )

    def test_a_tabela_do_banco_de_referencia(self):
        """
        Linha por linha, com cada número tirado do R e formatado aqui. O IC do
        Spearman e o do Kendall, que o R não dá, pelas fórmulas publicadas.
        """
        r_imc = REFERENCIAS_DO_R[0]
        rho = REFERENCIAS_DO_R[4][2]
        tau = REFERENCIAS_DO_R[8][2]
        ic_rho = _fisher(rho, math.sqrt((1 + rho**2 / 2) / 57))
        ic_tau = _fisher(tau, math.sqrt(0.437 / 56))

        def faixa(ic):
            return f"{_duas_casas(ic[0])} a {_duas_casas(ic[1])}"

        assert _correlacionar().tabela.linhas == (
            ("Idade", "IMC", "57", PEARSON, _duas_casas(r_imc[2]), faixa(r_imc[6]),
             valor_p(r_imc[5])),
            ("Idade", "Renda", "60", SPEARMAN, _duas_casas(rho), faixa(ic_rho),
             valor_p(REFERENCIAS_DO_R[4][5])),
            ("Dor", "Idade", "60", KENDALL, _duas_casas(tau), faixa(ic_tau),
             valor_p(REFERENCIAS_DO_R[8][5])),
        )

    def test_o_negativo_leva_o_hifen_e_o_zero_nao_leva(self):
        quadro = pd.DataFrame(
            {"a": [float(i) for i in range(30)], "b": [float(30 - i) for i in range(30)]}
        )
        linhas = (Linha("a", "A", NUMERICA), Linha("b", "B", NUMERICA))
        linha = _correlacionar(quadro, linhas, (("a", "b"),)).tabela.linhas[0]
        assert linha[4] == "-1,00"
        assert "-0,00" not in _correlacionar(
            pd.DataFrame({"a": [1.0, 2.0, 3.0, 4.0], "b": [1.0, 3.0, 3.0, 1.0]}),
            linhas,
            (("a", "b"),),
        ).tabela.texto()

    def test_o_quase_zero_negativo_sai_sem_sinal(self):
        """`-0,004` com duas casas é `0,00`, e não `-0,00` — um zero não tem direção."""
        from flatcap.correlacao import _formatar_coeficiente, _formatar_intervalo

        assert _formatar_coeficiente(-0.004) == "0,00"
        assert _formatar_coeficiente(-0.005001) == "-0,01"
        assert _formatar_intervalo((-0.004, 0.31)) == "0,00 a 0,31"

    def test_n_e_quem_respondeu_as_duas(self):
        resultado = _correlacionar()
        idade_imc = _par(resultado, "idade", "imc")
        assert (idade_imc.validos, idade_imc.faltantes) == (57, 3)
        assert _par(resultado, "idade", "renda").validos == 60

    def test_o_p_nunca_sai_zero(self):
        assert _correlacionar().tabela.linhas[0][6] == "< 0,001"

    def test_a_tabela_nao_e_de_uma_variavel(self):
        tabela = _correlacionar().tabela
        assert (tabela.variavel, tabela.nome) == ("", "correlacao.csv")
        texto = tabela.texto()
        assert "# variável:" not in texto
        assert "não há correção para comparações múltiplas" in texto
        assert "Bonett e Wright (2000)" in texto
        assert "cor.test do R" in texto


# ── A dispersão ─────────────────────────────────────────────────────────────


class TestDispersao:
    def test_uma_figura_por_par_testado(self):
        resultado = _correlacionar(pedidos=(*PARES, ("idade", "servico")))
        assert [g.nome for g in resultado.graficos] == [
            "disp_idade_x_imc.png",
            "disp_idade_x_renda.png",
            "disp_dor_x_idade.png",
        ]
        assert {g.especie for g in resultado.graficos} == {"dispersao"}

    def test_os_pontos_contam_os_casos_que_coincidem(self):
        quadro = pd.DataFrame({"a": [1, 1, 1, 2, 2, 3] * 5, "b": [1, 1, 2, 2, 3, 3] * 5})
        linhas = (Linha("a", "A", CATEGORICA), Linha("b", "B", CATEGORICA))
        grafico = _correlacionar(quadro, linhas, (("a", "b"),)).graficos[0]
        pontos = dict(zip(zip(grafico.pontos_x, grafico.pontos_y, strict=True),
                          grafico.contagens, strict=True))
        assert pontos == {(1.0, 1.0): 10, (1.0, 2.0): 5, (2.0, 2.0): 5, (2.0, 3.0): 5,
                          (3.0, 3.0): 5}
        assert sum(grafico.contagens) == 30
        assert "o tamanho do ponto é o número de casos" in grafico.subtitulo

    def test_o_eixo_x_e_a_primeira_variavel_e_o_subtitulo_e_o_das_outras_figuras(self):
        grafico = _correlacionar().graficos[0]
        assert (grafico.rotulo_categoria, grafico.rotulo_valor) == ("Idade", "IMC")
        assert grafico.titulo == "Dispersão — Idade × IMC"
        assert grafico.subtitulo == "n = 57 · 3 sem informação"

    def test_sem_graficos_nem_conta_os_pontos(self):
        resultado = _correlacionar(com_graficos=False)
        assert resultado.graficos == ()
        assert all(par.pontos == () for par in resultado.pares)

    def test_o_png_sai(self, tmp_path):
        from flatcap.graficos import desenhar

        grafico = _correlacionar().graficos[2]
        caminho = desenhar(grafico, tmp_path / grafico.nome)
        assert caminho.read_bytes().startswith(b"\x89PNG")


# ── O manifesto ─────────────────────────────────────────────────────────────


class TestManifesto:
    def test_um_item_para_a_analise_inteira(self):
        manifesto = montar_manifesto(_correlacionar(), DICIONARIO)
        assert manifesto.analise == ANALISE_CORRELACAO
        (item,) = manifesto.itens
        assert (item.variavel, item.rotulo) == ("", "Correlação")
        assert item.colunas == ("idade", "imc", "renda", "dor")
        assert [a.arquivo for a in item.artefatos] == [
            "correlacao.csv",
            "disp_idade_x_imc.png",
            "disp_idade_x_renda.png",
            "disp_dor_x_idade.png",
        ]

    def test_os_detalhes_levam_os_pressupostos_e_a_escolha(self):
        detalhes = montar_manifesto(_correlacionar(), DICIONARIO).itens[0].detalhes
        idade_imc, idade_renda, dor_idade = detalhes["pares"]
        assert idade_imc["shapiro_2"]["rejeita"] is False
        assert idade_imc["estatistica"] == {"nome": "t", "valor": 6.922322, "gl": 55}
        assert idade_renda["shapiro_2"]["rejeita"] is True
        assert (dor_idade["distintos_1"], dor_idade["shapiro_1"]) == (6, None)
        assert dor_idade["calculo_do_p"].startswith("aproximação normal")
        assert (detalhes["pearson"], detalhes["spearman"], detalhes["kendall"]) == (1, 1, 1)

    def test_o_p_pequeno_nao_vira_zero_no_manifesto(self):
        """Seis algarismos significativos, e não seis casas: 5,06e-09 não é 0."""
        detalhes = montar_manifesto(_correlacionar(), DICIONARIO).itens[0].detalhes
        assert detalhes["pares"][0]["p"] == pytest.approx(5.05617e-09, rel=1e-5)

    def test_o_ambiente_declara_o_scipy_e_o_matplotlib_so_com_figura(self):
        com = montar_manifesto(_correlacionar(), DICIONARIO, com_graficos=True).ambiente
        sem = montar_manifesto(
            _correlacionar(com_graficos=False), DICIONARIO, com_graficos=False
        ).ambiente
        assert com["scipy"] == __import__("scipy").__version__
        assert com["matplotlib"] and sem["matplotlib"] is None

    def test_as_regras_dizem_como_o_r_faz(self):
        regras = montar_manifesto(_correlacionar(), DICIONARIO).regras
        assert "Kendall se alguma das duas tem até 10 valores distintos" in regras[
            "escolha_do_metodo"
        ]
        assert "AS 89" in regras["spearman"]
        assert "Bonett e Wright" in regras["intervalo"]

    def test_fora_lista_quem_nao_esta_em_par(self):
        manifesto = montar_manifesto(_correlacionar(), DICIONARIO)
        fora = {entrada["variavel"] for entrada in manifesto.fora}
        assert fora == {"escolaridade", "servico"}

    def test_a_ordem_padrao_poe_a_correlacao_logo_depois_da_normalidade(self):
        posicao = ORDEM_PADRAO_DAS_ANALISES.index
        assert posicao(ANALISE_CORRELACAO) == posicao(ANALISE_NORMALIDADE) + 1


# ── No disco ────────────────────────────────────────────────────────────────


@pytest.fixture
def projeto_para_correlacionar(projeto_com_rodada):
    """
    Projeto com banco, dicionário, uma rodada de descritiva e a lista na ficha.
    """

    def montar(bloco: str = BLOCO):
        raiz = projeto_com_rodada()
        acrescentar_a_ficha(raiz, bloco)
        return raiz

    return montar


class TestEscrita:
    def test_preparar_nao_toca_no_disco(self, projeto_para_correlacionar):
        raiz = projeto_para_correlacionar()
        antes = len(linhas_do_historico(raiz))
        preparar_correlacao(raiz, agora=AGORA)
        assert not (raiz / PASTA_ANALISES / PASTA_CORRELACAO).exists()
        assert len(linhas_do_historico(raiz)) == antes

    def test_executar_escreve_a_tabela_as_figuras_e_o_manifesto(self, projeto_para_correlacionar):
        raiz = projeto_para_correlacionar()
        executar_correlacao(preparar_correlacao(raiz, agora=AGORA))
        pasta = raiz / PASTA_ANALISES / PASTA_CORRELACAO

        assert sorted(p.name for p in pasta.iterdir()) == [
            "correlacao.csv",
            "disp_idade_x_imc.png",
            ARQUIVO_MANIFESTO,
        ]
        manifesto = ler_manifesto(pasta)
        assert manifesto.analise == ANALISE_CORRELACAO
        assert manifesto.itens[0].colunas == ("idade", "imc")

    def test_sem_graficos_escreve_so_a_tabela(self, projeto_para_correlacionar):
        raiz = projeto_para_correlacionar()
        executar_correlacao(preparar_correlacao(raiz, com_graficos=False, agora=AGORA))
        pasta = raiz / PASTA_ANALISES / PASTA_CORRELACAO
        assert sorted(p.name for p in pasta.iterdir()) == ["correlacao.csv", ARQUIVO_MANIFESTO]

    def test_escreve_uma_linha_no_historico(self, projeto_para_correlacionar):
        raiz = projeto_para_correlacionar()
        antes = len(linhas_do_historico(raiz))
        executar_correlacao(preparar_correlacao(raiz, agora=AGORA))
        linhas = linhas_do_historico(raiz)
        assert len(linhas) == antes + 1
        assert f"flatcap correlacao {RECORD_ID}" in linhas[-1]
        assert "1 Pearson" in linhas[-1]

    def test_regerar_arquiva_a_rodada_anterior(self, projeto_para_correlacionar):
        raiz = projeto_para_correlacionar()
        executar_correlacao(preparar_correlacao(raiz, agora=AGORA))
        resultado = executar_correlacao(
            preparar_correlacao(raiz, agora=AGORA.replace(hour=16))
        )
        arquivada = raiz / PASTA_ANTIGAS / "correlacao_2026-09-09_1630"
        assert resultado.arquivado == (raiz / PASTA_ANALISES / PASTA_CORRELACAO, arquivada)
        assert (arquivada / ARQUIVO_MANIFESTO).is_file()

    def test_a_falha_do_desenho_devolve_a_rodada_anterior(
        self, projeto_para_correlacionar, monkeypatch
    ):
        """O `matplotlib` estoura com exceção própria, e o desfazer precisa pegá-la."""
        import flatcap.graficos as graficos

        raiz = projeto_para_correlacionar()
        executar_correlacao(preparar_correlacao(raiz, agora=AGORA))
        pasta = raiz / PASTA_ANALISES / PASTA_CORRELACAO
        antes = {p.name: p.read_bytes() for p in pasta.iterdir()}

        def estoura(*_a, **_k):
            raise RuntimeError("o matplotlib caiu")

        monkeypatch.setattr(graficos, "desenhar", estoura)
        plano = preparar_correlacao(raiz, agora=AGORA.replace(hour=16))
        with pytest.raises(RuntimeError, match="o matplotlib caiu"):
            executar_correlacao(plano)

        assert {p.name: p.read_bytes() for p in pasta.iterdir()} == antes
        assert not list((raiz / PASTA_ANTIGAS).glob("correlacao_*"))

    def test_a_lista_mal_escrita_recusa_antes_de_abrir_o_banco(
        self, projeto_para_correlacionar, monkeypatch
    ):
        raiz = projeto_para_correlacionar("correlacao:\n  - idade e imc\n")

        def nao_abra(*_a, **_k):
            raise AssertionError("o banco foi aberto antes de a lista ser conferida")

        monkeypatch.setattr("flatcap.correlacao.abrir", nao_abra)
        with pytest.raises(ParInvalidoError):
            preparar_correlacao(raiz, agora=AGORA)

    def test_a_simulacao_e_a_execucao_dao_o_mesmo_arquivo(self, projeto_para_correlacionar):
        raiz = projeto_para_correlacionar()
        plano = preparar_correlacao(raiz, agora=AGORA)
        executar_correlacao(plano)
        escrito = (raiz / PASTA_ANALISES / PASTA_CORRELACAO / "correlacao.csv").read_text(
            encoding="utf-8"
        )
        assert escrito == plano.tabela.texto()


# ── O relatório, que não muda uma linha ─────────────────────────────────────


class TestRelatorio:
    def test_o_relatorio_encontra_a_rodada_sem_nenhum_alerta(self, projeto_para_correlacionar):
        from flatcap.relatorio import preparar_relatorio

        raiz = projeto_para_correlacionar()
        executar_correlacao(preparar_correlacao(raiz, agora=AGORA))
        relatorio = preparar_relatorio(raiz, agora=AGORA).relatorio

        assert relatorio.analises == ("descritiva", "correlacao")
        assert relatorio.alertas == ()
        secao = next(s for s in relatorio.secoes if s.rotulo == "Correlação")
        assert secao.tabelas[0].colunas[3:5] == ("método", "coeficiente")
        assert secao.tabelas[0].linhas[0][:4] == ("idade", "imc", "24", PEARSON)
        assert [f.titulo for f in secao.figuras] == ["Dispersão — idade × imc"]

    def test_sem_ficha_mandando_vem_depois_da_normalidade(self, projeto_para_correlacionar):
        from flatcap.normalidade import executar_normalidade, preparar_normalidade
        from flatcap.relatorio import preparar_relatorio

        raiz = projeto_para_correlacionar()
        executar_correlacao(preparar_correlacao(raiz, agora=AGORA))
        executar_normalidade(preparar_normalidade(raiz, com_graficos=False, agora=AGORA))
        relatorio = preparar_relatorio(raiz, agora=AGORA).relatorio
        assert relatorio.analises == ("descritiva", "normalidade", "correlacao")

    def test_a_ficha_manda_na_ordem(self, projeto_para_correlacionar):
        from flatcap.relatorio import preparar_relatorio

        raiz = projeto_para_correlacionar()
        ficha = raiz / ARQUIVO_PROJETO
        ficha.write_text(
            ficha.read_text(encoding="utf-8").replace(
                "analises: []", "analises:\n  - correlacao\n  - descritiva"
            ),
            encoding="utf-8",
        )
        executar_correlacao(preparar_correlacao(raiz, agora=AGORA))
        relatorio = preparar_relatorio(raiz, agora=AGORA).relatorio
        assert relatorio.analises == ("correlacao", "descritiva")
        assert relatorio.secoes[0].rotulo == "Correlação"


def test_o_que_so_se_ve_abrindo_a_figura():
    """
    Lembrete, não teste. O que nenhuma asserção daqui pega: a marca `1,5` num eixo
    de escala de 1 a 3, o ponto grande tampando o vizinho, o rótulo comprido do eixo
    cortado. Antes de mesclar, abrir as dispersões de um projeto de verdade — uma
    com escala, uma contínua — e olhar.
    """
    assert True
