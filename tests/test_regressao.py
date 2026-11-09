# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Os testes do `regressao.py`.

O miolo é testado pela função pura `regredir(banco, ficha, linhas, modelos)`, como o
`correlacionar` da correlação. O caminho do disco — a ficha com a lista `regressao:`,
a rodada escrita, o relatório que a encontra — usa os fixtures do `conftest.py`.

**Nenhum número daqui é conferido contra o próprio módulo.** A referência é o **R
4.5.0**: `lm` e `glm(family = binomial)` sobre os mesmos números, com os resultados
copiados para as constantes `*_DO_R` — os coeficientes, os erros-padrão, as
estatísticas, os p e os IC do `summary` e do `confint` (`confint.default` na
logística), o R², o F, a deviance, o AIC e o Shapiro-Wilk dos resíduos —, com os
fatores nos níveis da ordem do dicionário: `factor(sexo, levels = c(1, 2), labels =
c("Feminino", "Masculino"))`, e o mesmo para a escolaridade e o óbito.

O banco de referência é o `bancos.para_regredir()`: sessenta casos, um desfecho
numérico, um categórico e os preditores de cada tipo.
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
from flatcap.dicionario import CATEGORICA, DATA, IGNORAR, NUMERICA, Linha
from flatcap.manifesto import (
    ANALISE_REGRESSAO,
    ARQUIVO_MANIFESTO,
    ORDEM_PADRAO_DAS_ANALISES,
)
from flatcap.manifesto import ler as ler_manifesto
from flatcap.projeto import ARQUIVO_PROJETO, PASTA_ANALISES, PASTA_ANTIGAS, PASTA_REGRESSAO
from flatcap.regressao import (
    INTERCEPTO,
    LINEAR_MULTIPLA,
    LINEAR_SIMPLES,
    LOGISTICA,
    MAXIMO_DE_ITERACOES,
    REFERENCIA,
    ModeloInvalidoError,
    Pedido,
    SemModelosError,
    VariavelIncompativelError,
    colunas_colineares,
    executar_regressao,
    logistica,
    modelos_da_ficha,
    montar_manifesto,
    preparar_regressao,
    regredir,
    separacao,
)

PAS = Linha("pas", "Pressão sistólica", NUMERICA)
IDADE = Linha("idade", "Idade", NUMERICA)
IMC = Linha("imc", "IMC", NUMERICA)
SEXO = Linha(
    "sexo",
    "Sexo",
    CATEGORICA,
    ("1", "2"),
    rotulos_das_categorias=(("1", "Feminino"), ("2", "Masculino")),
)
ESCOLARIDADE = Linha(
    "escolaridade", "Escolaridade", CATEGORICA, ("Fundamental", "Médio", "Superior")
)
OBITO = Linha(
    "obito", "Óbito", CATEGORICA, ("0", "1"), rotulos_das_categorias=(("0", "Não"), ("1", "Sim"))
)
SERVICO = Linha("servico", "Serviço", CATEGORICA, ("1",))
DICIONARIO = (PAS, IDADE, IMC, SEXO, ESCOLARIDADE, OBITO, SERVICO)

SIMPLES = ("pas", ["idade"])
MULTIPLA = ("pas", ["idade", "imc", "sexo", "escolaridade"])
LOGISTICA_SIMPLES = ("obito", ["idade"])
LOGISTICA_MULTIPLA = ("obito", ["idade", "sexo", "escolaridade"])

# O que se escreve na ficha para o banco do `conftest` — o `bancos.completo()`, com
# `idade` e `imc` numéricas e `sexo` categórica em texto.
BLOCO = "regressao:\n  - imc: [idade, sexo]\n"


# `coef(summary(m))` e o IC, no R 4.5.0, linha a linha:
#
#     (estimativa, erro-padrão, t ou z, p, (IC 2,5%, IC 97,5%))
#
# `confint(m)` na linear e `confint.default(m)` na logística.
COEFICIENTES_DO_R = {
    # lm(pas ~ idade)
    "simples": [
        (89.5691938491472, 4.32695036959375, 20.7003053417404, 3.42149524251079e-28,
         (80.9046251899693, 98.2337625083252)),
        (0.767367633030421, 0.0839372500081491, 9.14215837373658, 9.0535150287686e-13,
         (0.599286189141229, 0.935449076919613)),
    ],
    # lm(pas ~ idade + imc + sexo + escolaridade)
    "multipla": [
        (71.3844729680639, 10.5522397727443, 6.7648645695528, 1.4001698445462e-08,
         (50.1896756194462, 92.5792703166816)),
        (0.626856639032773, 0.104532068164579, 5.99678787609779, 2.21423652663235e-07,
         (0.416897801014071, 0.836815477051475)),
        (0.991953854460588, 0.494495763138273, 2.0059906037723, 0.0502825967909334,
         (-0.0012701164860095, 1.98517782540719)),
        (3.79009036351802, 1.9789757624581, 1.91517775781666, 0.061198643099094,
         (-0.184799436793754, 7.76498016382979)),
        (-2.33114762853477, 2.4111463357696, -0.966821297385382, 0.338286750969845,
         (-7.17407757185316, 2.51178231478361)),
        (-5.09203480909948, 2.34970260432805, -2.16709757214389, 0.0350171319275037,
         (-9.81155138574947, -0.372518232449495)),
    ],
    # glm(obito ~ idade, family = binomial)
    "logistica_simples": [
        (-5.03438911784764, 1.56840592916207, -3.20987636187865, 0.00132792076975098,
         (-8.10840825214436, -1.96036998355091)),
        (0.093947066009105, 0.0300649787464903, 3.12480067926448, 0.00177925577089631,
         (0.0350207904700218, 0.152873341548188)),
    ],
    # glm(obito ~ idade + sexo + escolaridade, family = binomial)
    "logistica_multipla": [
        (-5.60833173918774, 1.7151368766196, -3.26990330371843, 0.00107584253615379,
         (-8.96993824591867, -2.24672523245681)),
        (0.0980744063596855, 0.0309675491610089, 3.16700575333777, 0.0015401727126331,
         (0.0373791253146345, 0.158769687404736)),
        (1.1226484602378, 0.614908169788076, 1.82571726218032, 0.0678928616107205,
         (-0.0825494063462688, 2.32784632682187)),
        (-0.112910285634291, 0.737562195661151, -0.153085782186923, 0.878330627887944,
         (-1.55850562548843, 1.33268505421985)),
        (-0.494568280666804, 0.749145970501324, -0.660176120730973, 0.50914081437647,
         (-1.9628674020127, 0.973730840679096)),
    ],
    # a mesma múltipla com `relevel(sexo, ref = "Masculino")`
    "multipla_masculino": [
        (75.1745633315819, 10.3765332541814, 7.24467040100213, 2.48701086204847e-09,
         (54.3326829118794, 96.0164437512845)),
        (0.626856639032773, 0.104532068164579, 5.99678787609779, 2.21423652663235e-07,
         (0.416897801014071, 0.836815477051475)),
        (0.991953854460588, 0.494495763138273, 2.0059906037723, 0.0502825967909334,
         (-0.0012701164860095, 1.98517782540719)),
        (-3.79009036351802, 1.9789757624581, -1.91517775781666, 0.0611986430990939,
         (-7.76498016382979, 0.184799436793754)),
        (-2.33114762853477, 2.4111463357696, -0.966821297385383, 0.338286750969845,
         (-7.17407757185316, 2.51178231478361)),
        (-5.09203480909948, 2.34970260432805, -2.16709757214389, 0.0350171319275037,
         (-9.81155138574947, -0.372518232449495)),
    ],
    # a logística simples com `relevel(obito, ref = "Sim")`: o evento é o Não
    "logistica_evento_nao": [
        (5.03438911784763, 1.56840592916207, 3.20987636187864, 0.00132792076975102,
         (1.9603699835509, 8.10840825214437)),
        (-0.0939470660091049, 0.0300649787464904, -3.12480067926447, 0.00177925577089636,
         (-0.152873341548188, -0.0350207904700216)),
    ],
    # lm(pas ~ escolaridade): uma variável, duas indicadoras
    "simples_categorica": [
        (129.29, 2.7073470423126, 47.7552371304277, 4.57180771791093e-47,
         (123.866532164787, 134.713467835213)),
        (-0.842631578947406, 3.87881827021169, -0.217239251815069, 0.828811454487907,
         (-8.61283827884653, 6.92757512095172)),
        (-2.84000000000004, 3.82876690528916, -0.74175317282355, 0.461336550031701,
         (-10.5099417676524, 4.82994176765236)),
    ],
}

# `summary.lm` e `shapiro.test(residuals(m))`:
#
#     (n, R², R² ajustado, F, (gl1, gl2), p do F, sigma, W, p do W)
LINEARES_DO_R = {
    "simples": (59, 0.594534206522079, 0.587420771548782, 83.5790597304822, (1, 57),
                9.05351502876795e-13, 7.68118320796086, 0.995771882014131, 0.999301617699235),
    "multipla": (56, 0.66352332480519, 0.629875657285709, 19.7197420718993, (5, 50),
                 8.40050236449744e-11, 7.30204774784418, 0.992806908409462, 0.983589541038877),
    "simples_categorica": (59, 0.0102420474639839, -0.0251064508408738, 0.289744910113378,
                           (2, 56), 0.749569657024961, 12.1076240505879, 0.992555419510824,
                           0.975984551312564),
}

# O `glm`, com a razão de verossimilhança contra o nulo:
#
#     (n, deviance nula, deviance, razão, gl, p, AIC, iterações)
LOGISTICAS_DO_R = {
    "logistica_simples": (60, 82.107811815636, 68.8942642206536, 13.2135475949824, 1,
                          0.000277932793603886, 72.8942642206536, 4),
    "logistica_multipla": (60, 82.107811815636, 65.0176969768371, 17.0901148387989, 4,
                           0.00185655260979575, 75.0176969768371, 4),
}

def _regredir(pedidos, quadro=None, linhas=DICIONARIO, **opcoes):
    quadro = bancos.para_regredir() if quadro is None else quadro
    return regredir(
        banco_em_memoria(quadro), ficha_em_memoria(), linhas, pedidos, AGORA, **opcoes
    )


def _um(pedido, quadro=None, linhas=DICIONARIO):
    return _regredir([pedido], quadro, linhas).modelos[0]


def _celulas(tabela, termo: str) -> tuple[str, ...]:
    return next(linha for linha in tabela.linhas if linha[0] == termo)


# ── O R ─────────────────────────────────────────────────────────────────────


class TestReferenciasDoR:
    @pytest.mark.parametrize(
        ("caso", "pedido", "linhas"),
        [
            ("simples", SIMPLES, DICIONARIO),
            ("multipla", MULTIPLA, DICIONARIO),
            ("logistica_simples", LOGISTICA_SIMPLES, DICIONARIO),
            ("logistica_multipla", LOGISTICA_MULTIPLA, DICIONARIO),
            ("simples_categorica", ("pas", ["escolaridade"]), DICIONARIO),
        ],
    )
    def test_os_coeficientes_do_summary(self, caso, pedido, linhas):
        ajuste = _um(pedido, linhas=linhas).ajuste
        assert len(ajuste.coeficientes) == len(COEFICIENTES_DO_R[caso])
        for coeficiente, (estimativa, erro, estatistica, p, ic) in zip(
            ajuste.coeficientes, COEFICIENTES_DO_R[caso], strict=True
        ):
            assert coeficiente.estimativa == pytest.approx(estimativa, rel=1e-9, abs=1e-12)
            assert coeficiente.erro_padrao == pytest.approx(erro, rel=1e-9)
            assert coeficiente.estatistica == pytest.approx(estatistica, rel=1e-9)
            assert coeficiente.p == pytest.approx(p, rel=1e-7)
            assert coeficiente.ic == pytest.approx(ic, rel=1e-9, abs=1e-12)

    @pytest.mark.parametrize("caso", ["simples", "multipla", "simples_categorica"])
    def test_o_ajuste_da_linear(self, caso):
        pedido = {"simples": SIMPLES, "multipla": MULTIPLA,
                  "simples_categorica": ("pas", ["escolaridade"])}[caso]
        modelo = _um(pedido)
        ajuste = modelo.ajuste
        n, r2, ajustado, f, gl, p, sigma, w, p_w = LINEARES_DO_R[caso]
        assert ajuste.n == modelo.validos == n
        assert ajuste.r2 == pytest.approx(r2, rel=1e-10)
        assert ajuste.r2_ajustado == pytest.approx(ajustado, rel=1e-10)
        assert ajuste.teste == pytest.approx(f, rel=1e-10)
        assert ajuste.gl_do_teste == gl
        assert ajuste.p_do_teste == pytest.approx(p, rel=1e-7)
        assert ajuste.sigma == pytest.approx(sigma, rel=1e-10)
        assert modelo.normal.w == pytest.approx(w, rel=1e-6)
        assert modelo.normal.p == pytest.approx(p_w, rel=1e-5)

    @pytest.mark.parametrize("caso", ["logistica_simples", "logistica_multipla"])
    def test_o_ajuste_da_logistica(self, caso):
        pedido = {"logistica_simples": LOGISTICA_SIMPLES,
                  "logistica_multipla": LOGISTICA_MULTIPLA}[caso]
        modelo = _um(pedido)
        ajuste = modelo.ajuste
        n, nula, deviance, razao, gl, p, aic, iteracoes = LOGISTICAS_DO_R[caso]
        assert ajuste.n == n
        assert ajuste.deviance_nula == pytest.approx(nula, rel=1e-10)
        assert ajuste.deviance == pytest.approx(deviance, rel=1e-10)
        assert ajuste.teste == pytest.approx(razao, rel=1e-9)
        assert ajuste.gl_do_teste == (gl,)
        assert ajuste.p_do_teste == pytest.approx(p, rel=1e-8)
        assert ajuste.aic == pytest.approx(aic, rel=1e-10)
        assert ajuste.iteracoes == iteracoes
        assert ajuste.convergiu and not ajuste.extremos
        assert modelo.normal is None

    def test_o_or_e_o_ic_de_wald_na_tabela(self):
        """
        `exp(cbind(coef(m), confint.default(m)))` do R: OR 1,0985 (1,0356 a 1,1652). A
        meia largura do IC é 0,065, e dois algarismos dela pedem três casas.
        """
        tabela = _regredir([LOGISTICA_SIMPLES]).coeficientes[0]
        estimativa, _, _, _, (baixo, alto) = COEFICIENTES_DO_R["logistica_simples"][1]
        assert _celulas(tabela, "Idade") == (
            "Idade",
            _casas(math.exp(estimativa), 3),
            f"{_casas(math.exp(baixo), 3)} a {_casas(math.exp(alto), 3)}",
            "0,002",
        )


def _casas(valor: float, casas: int) -> str:
    """O número como a tabela o escreve — escrito aqui de novo, e não importado."""
    texto = f"{valor:.{casas}f}"
    return (texto.lstrip("-") if float(texto) == 0 else texto).replace(".", ",")


class TestSeparacao:
    """
    `glm(y ~ x, family = binomial)` no R 4.5.0, com `x = 1:10`.
    """

    X = [[1.0, float(x)] for x in range(1, 11)]

    def test_a_separacao_completa_nao_converge_como_no_r(self):
        """
        `y = c(0,0,0,0,0,1,1,1,1,1)`: o R avisa "algoritmo não convergiu" e
        "probabilidades ajustadas numericamente 0 ou 1", com `iter = 25` e os
        coeficientes −245,847 e 44,6995 — que crescem sem fim.
        """
        ajuste = logistica(self.X, [0, 0, 0, 0, 0, 1, 1, 1, 1, 1])
        assert not ajuste.convergiu
        assert ajuste.iteracoes == MAXIMO_DE_ITERACOES == 25
        assert ajuste.extremos
        assert [c.estimativa for c in ajuste.coeficientes] == pytest.approx(
            [-245.847322304006, 44.699513147486], rel=1e-6
        )

    def test_com_sobreposicao_converge(self):
        """`y = c(0,0,0,0,1,0,1,1,1,1)`: converge em 6 iterações, sem aviso."""
        ajuste = logistica(self.X, [0, 0, 0, 0, 1, 0, 1, 1, 1, 1])
        assert ajuste.convergiu and ajuste.iteracoes == 6 and not ajuste.extremos
        estimativas = [
            numero for c in ajuste.coeficientes for numero in (c.estimativa, c.erro_padrao, c.p)
        ]
        assert estimativas == pytest.approx(
            [
                -7.15901065675967, 4.759070327393425, 0.132507320972647,
                1.30163830122903, 0.839982839056657, 0.121237297408861,
            ],
            rel=1e-9,
        )

    def test_o_modelo_separado_sai_sem_numeros(self):
        quadro = pd.DataFrame(
            {"obito": [0, 0, 0, 0, 0, 1, 1, 1, 1, 1], "idade": [float(i) for i in range(1, 11)]}
        )
        modelo = _um(LOGISTICA_SIMPLES, quadro, (OBITO, IDADE))
        assert not modelo.ajustado
        assert modelo.motivo.startswith(
            "separação — algum preditor, ou uma combinação deles, separa os eventos dos não "
            "eventos. O OR é infinito"
        )

    def test_a_separacao_que_o_r_ajusta_sem_aviso(self):
        """
        O `bancos.completo()`: a escolaridade `Médio` é sempre do sexo masculino, e as
        outras duas, sempre do feminino. O `glm(sexo ~ escolaridade, family =
        binomial)` do R 4.5.0 "converge" em 24 iterações, **sem aviso nenhum**, com o
        coeficiente do `Médio` em 51,13, erro-padrão de 108 000 e p = 0,9996 — o OR
        de 10²² que a tabela imprimiria. Aqui o modelo sai sem números, e o motivo diz
        qual categoria separa.
        """
        sexo = Linha("sexo", "Sexo", CATEGORICA, ("Feminino", "Masculino"))
        modelo = _um(("sexo", ["escolaridade"]), bancos.completo(), (sexo, ESCOLARIDADE))
        assert not modelo.ajustado
        assert modelo.motivo.startswith(
            "separação — nenhum caso de Escolaridade: Fundamental é Masculino; todo caso de "
            "Escolaridade: Médio é Masculino; nenhum caso de Escolaridade: Superior é "
            "Masculino. O OR é infinito"
        )

    @pytest.mark.parametrize(
        ("caso", "y", "separa"),
        [
            ("completa", [0, 0, 0, 0, 0, 1, 1, 1, 1, 1], True),
            ("quase: o 5 dos dois lados", [0, 0, 0, 0, 0, 1, 1, 1, 1, 1], True),
            ("sobreposta", [0, 0, 0, 0, 1, 0, 1, 1, 1, 1], False),
        ],
    )
    def test_o_programa_linear_de_konis(self, caso, y, separa):
        x = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        if caso.startswith("quase"):
            x = [1, 2, 3, 4, 5, 5, 6, 7, 8, 9]
        assert separacao([[1.0, float(valor)] for valor in x], y) is separa

    def test_a_categoria_so_com_eventos_e_quase_completa(self):
        """Um grupo todo evento, o outro misturado: a separação quase completa."""
        x = [[1.0, 0.0]] * 10 + [[1.0, 1.0]] * 10
        y = [0, 1, 0, 1, 0, 1, 0, 0, 1, 0] + [1] * 10
        assert separacao(x, y)

    def test_os_modelos_de_referencia_nao_separam(self):
        """As duas logísticas conferidas contra o R não são acusadas de separação."""
        assert all(
            modelo.ajustado for modelo in _regredir([LOGISTICA_SIMPLES, LOGISTICA_MULTIPLA]).modelos
        )


# ── A regra ─────────────────────────────────────────────────────────────────


class TestRegra:
    def test_o_desfecho_escolhe_o_modelo(self):
        resultado = _regredir([SIMPLES, MULTIPLA, LOGISTICA_SIMPLES])
        assert [modelo.modelo for modelo in resultado.modelos] == [
            LINEAR_SIMPLES, LINEAR_MULTIPLA, LOGISTICA,
        ]

    def test_conta_variaveis_e_nao_coeficientes(self):
        """`pas: [escolaridade]` é simples, com as duas indicadoras da escolaridade."""
        modelo = _um(("pas", ["escolaridade"]))
        assert modelo.modelo == LINEAR_SIMPLES
        assert len(modelo.ajuste.coeficientes) == 3

    def test_o_desfecho_numerico_de_dois_valores_avisa(self):
        obito = Linha("obito", "Óbito", NUMERICA)
        modelo = _um(LOGISTICA_SIMPLES, linhas=(obito, IDADE))
        assert modelo.modelo == LINEAR_SIMPLES
        assert any("tem dois valores só" in aviso and "`categorica`" in aviso
                   for aviso in modelo.avisos)

    def test_a_categorica_de_tres_categorias_nao_tem_logistica(self):
        modelo = _um(("escolaridade", ["idade"]))
        assert modelo.modelo == LOGISTICA
        assert not modelo.ajustado
        assert "tem 3 categorias" in modelo.motivo
        assert "multinomial" in modelo.motivo

    def test_os_faltantes_sao_por_modelo(self):
        """A simples não perde os casos sem IMC que a múltipla perde."""
        simples, multipla = _regredir([SIMPLES, MULTIPLA]).modelos
        assert (simples.validos, simples.faltantes) == (59, 1)
        assert (multipla.validos, multipla.faltantes) == (56, 4)


# ── As categóricas ──────────────────────────────────────────────────────────


class TestCategoricas:
    def test_a_referencia_e_a_primeira_do_dicionario(self):
        modelo = _um(MULTIPLA)
        assert modelo.referencias == (("sexo", "Feminino"), ("escolaridade", "Fundamental"))
        assert [termo.rotulo for termo in modelo.termos] == [
            INTERCEPTO,
            "Idade",
            "IMC",
            "Sexo: Feminino",
            "Sexo: Masculino",
            "Escolaridade: Fundamental",
            "Escolaridade: Médio",
            "Escolaridade: Superior",
        ]
        assert [termo.referencia for termo in modelo.termos] == [
            False, False, False, True, False, True, False, False,
        ]

    def test_a_ordem_do_dicionario_troca_a_referencia_como_o_relevel(self):
        sexo = Linha(
            "sexo", "Sexo", CATEGORICA, ("2", "1"),
            rotulos_das_categorias=(("1", "Feminino"), ("2", "Masculino")),
        )
        linhas = tuple(sexo if linha.variavel == "sexo" else linha for linha in DICIONARIO)
        ajuste = _um(MULTIPLA, linhas=linhas).ajuste
        assert ajuste.coeficientes[3].nome == "Sexo: Feminino"
        for coeficiente, (estimativa, erro, _, p, ic) in zip(
            ajuste.coeficientes, COEFICIENTES_DO_R["multipla_masculino"], strict=True
        ):
            assert coeficiente.estimativa == pytest.approx(estimativa, rel=1e-9)
            assert coeficiente.erro_padrao == pytest.approx(erro, rel=1e-9)
            assert coeficiente.p == pytest.approx(p, rel=1e-7)
            assert coeficiente.ic == pytest.approx(ic, rel=1e-9)

    def test_o_codigo_conta_e_o_rotulo_imprime(self):
        """
        Dois códigos com o mesmo rótulo são uma categoria, e uma indicadora só — o
        modelo é o do sexo de duas categorias, com os mesmos números.
        """
        quadro = bancos.para_regredir()
        quadro["sexo"] = [3 if (i % 4 == 0 and s == 2) else s for i, s in enumerate(quadro["sexo"])]
        sexo = Linha(
            "sexo", "Sexo", CATEGORICA, ("1", "2", "3"),
            rotulos_das_categorias=(("1", "Feminino"), ("2", "Masculino"), ("3", "Masculino")),
        )
        linhas = tuple(sexo if linha.variavel == "sexo" else linha for linha in DICIONARIO)
        ajuste = _um(MULTIPLA, quadro, linhas).ajuste
        assert [c.nome for c in ajuste.coeficientes][3] == "Sexo: Masculino"
        assert len(ajuste.coeficientes) == 6
        assert ajuste.coeficientes[3].estimativa == pytest.approx(
            COEFICIENTES_DO_R["multipla"][3][0], rel=1e-9
        )

    def test_a_categorica_em_texto_entra_sem_codigo(self):
        """A escolaridade chega em texto, e não precisa de ordem para virar indicadora."""
        assert _um(("pas", ["escolaridade"])).ajustado


# ── O evento da logística ───────────────────────────────────────────────────


class TestEvento:
    def test_o_evento_e_a_segunda_categoria_do_dicionario(self):
        modelo = _um(LOGISTICA_SIMPLES)
        assert (modelo.evento, modelo.evento_pela_ficha, modelo.eventos) == ("Sim", False, 26)
        assert modelo.nome_do_modelo == "Logística — evento: Sim"

    @pytest.mark.parametrize("escrito", ["Não", "nao", "NÃO", "0"])
    def test_o_evento_escrito_pelo_rotulo_ou_pelo_codigo(self, escrito):
        """O `relevel(obito, ref = "Sim")` do R: o mesmo modelo, com o sinal trocado."""
        modelo = _um(("obito", ["idade"], escrito))
        assert (modelo.evento, modelo.evento_pela_ficha, modelo.eventos) == ("Não", True, 34)
        for coeficiente, (estimativa, erro, _, p, ic) in zip(
            modelo.ajuste.coeficientes, COEFICIENTES_DO_R["logistica_evento_nao"], strict=True
        ):
            assert coeficiente.estimativa == pytest.approx(estimativa, rel=1e-9)
            assert coeficiente.erro_padrao == pytest.approx(erro, rel=1e-9)
            assert coeficiente.p == pytest.approx(p, rel=1e-7)
            assert coeficiente.ic == pytest.approx(ic, rel=1e-9)

    def test_o_evento_que_nao_e_categoria_sai_sem_modelo(self):
        modelo = _um(("obito", ["idade"], "Talvez"))
        assert not modelo.ajustado
        assert modelo.motivo == (
            "`evento: Talvez` não é categoria de Óbito, que tem Não e Sim"
        )

    def test_o_evento_vai_para_a_frase(self):
        assert "evento: Não (escrito na ficha), em 34 caso(s)" in _um(
            ("obito", ["idade"], "Não")
        ).justificativa
        assert "evento: Sim (a segunda categoria do dicionário)" in _um(
            LOGISTICA_SIMPLES
        ).justificativa


# ── Sem modelo, e os avisos ─────────────────────────────────────────────────


class TestSemModelo:
    def test_um_valor_so_no_preditor(self):
        modelo = _um(("pas", ["servico"]))
        assert not modelo.ajustado
        assert modelo.motivo == "um valor só em Serviço"

    def test_a_linha_sai_assim_mesmo(self):
        resultado = _regredir([SIMPLES, ("pas", ["servico"])])
        assert len(resultado.tabela.linhas) == 2
        assert resultado.tabela.linhas[1][5] == "sem modelo: um valor só em Serviço"
        assert len(resultado.coeficientes) == 1

    def test_nenhum_caso_completo(self):
        quadro = bancos.para_regredir()
        quadro["imc"] = [None] * len(quadro)
        quadro["imc"] = quadro["imc"].astype("float64")
        modelo = _um(MULTIPLA, quadro)
        assert modelo.motivo == "nenhum caso com resposta em todas as variáveis do modelo"

    def test_menos_casos_que_coeficientes(self):
        """As cinco primeiras linhas, e a quinta sem IMC: quatro casos completos."""
        modelo = _um(MULTIPLA, bancos.para_regredir().head(5))
        assert modelo.motivo.startswith("4 caso(s) completo(s) para 6 coeficientes")

    def test_a_colinearidade_perfeita_nomeia_a_segunda_como_o_r(self):
        """`lm(pas ~ idade + dobro)` no R dá `NA` ao `dobro`: é a segunda que sai."""
        quadro = bancos.para_regredir()
        quadro["dobro"] = quadro["idade"] * 2
        dobro = Linha("dobro", "Dobro da idade", NUMERICA)
        modelo = _um(("pas", ["idade", "dobro"]), quadro, (*DICIONARIO, dobro))
        assert not modelo.ajustado
        assert modelo.motivo.startswith("Dobro da idade é combinação exata dos outros")

    def test_colunas_colineares_acha_a_indicadora_que_soma_um(self):
        x = [[1.0, 1.0, 0.0], [1.0, 0.0, 1.0], [1.0, 1.0, 0.0], [1.0, 0.0, 1.0]]
        assert colunas_colineares(x) == (2,)


class TestAvisos:
    def test_poucos_eventos_por_coeficiente(self):
        """26 eventos e 34 não eventos: 26 na mais rara, para 4 coeficientes."""
        modelo = _um(LOGISTICA_MULTIPLA)
        assert any(
            "26 caso(s) na categoria mais rara do desfecho para 4 coeficiente(s) — 6,5 por "
            "coeficiente" in aviso
            for aviso in modelo.avisos
        )
        assert not any("categoria mais rara" in aviso for aviso in _um(LOGISTICA_SIMPLES).avisos)

    def test_os_residuos_que_nao_sao_normais(self):
        quadro = bancos.para_regredir()
        quadro["pas"] = [
            None if pas is None or pd.isna(pas) else 100 + (i % 7) ** 4
            for i, pas in enumerate(quadro["pas"])
        ]
        modelo = _um(SIMPLES, quadro)
        assert modelo.normal.rejeita
        assert any("rejeita a normal dos resíduos" in aviso for aviso in modelo.avisos)

    def test_os_residuos_normais_nao_avisam(self):
        assert _um(SIMPLES).avisos == ()


# ── A ficha ─────────────────────────────────────────────────────────────────


class TestFicha:
    def _ler(self, projeto_vazio, texto: str):
        acrescentar_a_ficha(projeto_vazio, texto)
        return modelos_da_ficha(projeto_vazio)

    def test_as_tres_formas(self, projeto_vazio):
        pedidos = self._ler(
            projeto_vazio,
            "regressao:\n"
            "  - pas: [idade]\n"
            "  - pas: [idade, imc, sexo]\n"
            "  - obito: [idade, sexo]\n"
            "    evento: Sim\n"
            "  - obito: idade\n"
            "    evento: 1\n",
        )
        assert pedidos == (
            Pedido("pas", ("idade",)),
            Pedido("pas", ("idade", "imc", "sexo")),
            Pedido("obito", ("idade", "sexo"), "Sim"),
            Pedido("obito", ("idade",), "1"),
        )

    def test_sem_a_chave_e_vazio(self, projeto_vazio):
        assert modelos_da_ficha(projeto_vazio) == ()

    def test_a_chave_que_nao_e_lista(self, projeto_vazio):
        with pytest.raises(ModeloInvalidoError, match="deveria ser uma lista"):
            self._ler(projeto_vazio, "regressao: pas\n")

    def test_todos_os_itens_errados_de_uma_vez(self, projeto_vazio):
        with pytest.raises(ModeloInvalidoError) as erro:
            self._ler(
                projeto_vazio,
                "regressao:\n"
                "  - [pas, idade]\n"
                "  - pas: []\n"
                "  - {pas: [idade], imc: [idade]}\n"
                "  - obito: [idade]\n"
                "    evento: [Sim]\n"
                "  - evento: Sim\n",
            )
        mensagem = str(erro.value)
        assert "5 item(ns) fora do formato" in mensagem
        assert "1º item: [pas, idade] — um modelo se escreve com dois-pontos" in mensagem
        assert "`- pas: [idade]`" in mensagem
        assert "2º item: `pas: []`" in mensagem
        assert "3º item: 2 desfechos no mesmo item (pas, imc)" in mensagem
        assert "4º item: `evento: [Sim]`" in mensagem
        assert "5º item: `evento:` sem o modelo" in mensagem

    def test_uma_variavel_chamada_evento_e_um_desfecho(self, projeto_vazio):
        assert self._ler(projeto_vazio, "regressao:\n  - evento: [idade]\n") == (
            Pedido("evento", ("idade",)),
        )


class TestRecusas:
    def test_sem_modelos(self):
        with pytest.raises(SemModelosError) as erro:
            _regredir([])
        assert "não diz quais modelos ajustar" in str(erro.value)
        assert "pas, idade, imc, sexo" in str(erro.value)

    def test_todos_os_problemas_de_uma_vez(self):
        data = Linha("coleta", "Coleta", DATA)
        fora = Linha("anotacao", "Anotação", IGNORAR)
        with pytest.raises(ModeloInvalidoError) as erro:
            _regredir(
                [
                    ("pas", ["peso"]),
                    ("pas", ["pas", "idade"]),
                    ("pas", ["idade", "idade"]),
                    ("pas", ["idade"], "Sim"),
                    ("pas", ["coleta", "anotacao"]),
                    ("pas", ["imc", "idade"]),
                    ("pas", ["idade", "imc"]),
                ],
                linhas=(*DICIONARIO, data, fora),
            )
        mensagem = str(erro.value)
        assert "6 modelo(s) que não podem ser ajustados" in mensagem
        assert "pas: [peso] — `peso` não está no dicionario.csv" in mensagem
        assert "`pas` é o desfecho e está entre os preditores" in mensagem
        assert "`idade` duas vezes entre os preditores" in mensagem
        assert "`evento:` só vale na logística" in mensagem
        assert "`coleta` está marcada `data`" in mensagem
        assert "`anotacao` está marcada `ignorar`" in mensagem
        assert "pas: [idade, imc] — repete `pas: [imc, idade]`" in mensagem

    def test_a_numerica_que_chegou_como_texto(self):
        quadro = bancos.para_regredir()
        quadro["idade"] = quadro["idade"].astype(str).str.replace(".", ",")
        with pytest.raises(VariavelIncompativelError):
            _regredir([SIMPLES], quadro)


# ── As tabelas ──────────────────────────────────────────────────────────────


class TestTabelas:
    def test_o_resumo(self):
        tabela = _regredir([SIMPLES, MULTIPLA, LOGISTICA_MULTIPLA]).tabela
        assert tabela.colunas == (
            "desfecho", "modelo", "preditores", "n", "ajuste", "teste global", "p-valor",
        )
        assert tabela.linhas == (
            ("Pressão sistólica", "Linear simples", "Idade", "59",
             "R² = 0,59; ajustado = 0,59", "F = 83,58; 1 e 57 gl", "< 0,001"),
            ("Pressão sistólica", "Linear múltipla", "Idade, IMC, Sexo, Escolaridade", "56",
             "R² = 0,66; ajustado = 0,63", "F = 19,72; 5 e 50 gl", "< 0,001"),
            ("Óbito", "Logística — evento: Sim", "Idade, Sexo, Escolaridade", "60",
             "26 eventos; AIC = 75,0", "χ² = 17,09; 4 gl", "0,002"),
        )

    def test_os_coeficientes_da_linear(self):
        tabela = _regredir([MULTIPLA]).coeficientes[0]
        assert tabela.titulo == (
            "Regressão linear múltipla — Pressão sistólica ~ Idade + IMC + Sexo + Escolaridade"
        )
        assert tabela.colunas == ("termo", "coeficiente", "IC 95%", "p-valor")
        assert tabela.linhas == (
            (INTERCEPTO, "71,38", "50,19 a 92,58", "< 0,001"),
            ("Idade", "0,63", "0,42 a 0,84", "< 0,001"),
            ("IMC", "0,99", "0,00 a 1,99", "0,050"),
            ("Sexo: Feminino", REFERENCIA, "—", "—"),
            ("Sexo: Masculino", "3,79", "-0,18 a 7,76", "0,061"),
            ("Escolaridade: Fundamental", REFERENCIA, "—", "—"),
            ("Escolaridade: Médio", "-2,33", "-7,17 a 2,51", "0,338"),
            ("Escolaridade: Superior", "-5,09", "-9,81 a -0,37", "0,035"),
        )

    def test_a_logistica_sai_em_or_e_sem_o_intercepto(self):
        tabela = _regredir([LOGISTICA_MULTIPLA]).coeficientes[0]
        assert tabela.colunas == ("termo", "OR", "IC 95%", "p-valor")
        assert [linha[0] for linha in tabela.linhas] == [
            "Idade", "Sexo: Feminino", "Sexo: Masculino", "Escolaridade: Fundamental",
            "Escolaridade: Médio", "Escolaridade: Superior",
        ]
        assert _celulas(tabela, "Sexo: Masculino") == (
            "Sexo: Masculino", "3,07", "0,92 a 10,26", "0,068"
        )
        assert _celulas(tabela, "Idade") == ("Idade", "1,103", "1,038 a 1,172", "0,002")

    def test_as_casas_vem_da_largura_do_ic(self):
        """
        A idade em milésimos: os mesmos algarismos da idade em anos — `0,77 (0,60 a
        0,94)` vira `0,00077 (0,00060 a 0,00094)` —, e não `0,00 (0,00 a 0,00)`.
        """
        quadro = bancos.para_regredir()
        quadro["renda"] = quadro["idade"] * 1000
        renda = Linha("renda", "Renda", NUMERICA)
        tabela = _regredir([("pas", ["renda"])], quadro, (*DICIONARIO, renda)).coeficientes[0]
        estimativa, _, _, _, (baixo, alto) = COEFICIENTES_DO_R["simples"][1]
        assert _celulas(tabela, "Renda") == (
            "Renda",
            f"{estimativa / 1000:.5f}".replace(".", ","),
            f"{baixo / 1000:.5f} a {alto / 1000:.5f}".replace(".", ","),
            "< 0,001",
        )

    def test_as_notas_dizem_de_onde_vem_cada_numero(self):
        resultado = _regredir([SIMPLES, LOGISTICA_SIMPLES])
        notas = " ".join(resultado.tabela.notas)
        assert "o lm do R" in notas and "o glm do R com family = binomial" in notas
        logistica_notas = " ".join(resultado.coeficientes[1].notas)
        assert "IC 95% de Wald" in logistica_notas and "confint.default" in logistica_notas
        assert "57 graus de liberdade" in " ".join(resultado.coeficientes[0].notas)


class TestGraficos:
    def test_duas_figuras_por_linear_e_nenhuma_na_logistica(self):
        resultado = _regredir([SIMPLES, LOGISTICA_SIMPLES])
        assert [(g.nome, g.especie) for g in resultado.graficos] == [
            ("residuos_pas_idade.png", "dispersao"),
            ("qq_pas_idade.png", "qq"),
        ]
        residuos = resultado.graficos[0]
        ajuste = resultado.modelos[0].ajuste
        assert residuos.pontos_x == ajuste.ajustados
        assert residuos.pontos_y == ajuste.residuos
        assert residuos.subtitulo == "n = 59 · 1 sem resposta em alguma variável"

    def test_sem_graficos(self):
        assert _regredir([SIMPLES], com_graficos=False).graficos == ()


# ── O manifesto ─────────────────────────────────────────────────────────────


class TestManifesto:
    def test_um_item_de_resumo_e_um_por_modelo_ajustado(self):
        resultado = _regredir([SIMPLES, ("pas", ["servico"]), LOGISTICA_SIMPLES])
        manifesto = montar_manifesto(resultado, DICIONARIO)
        assert manifesto.analise == ANALISE_REGRESSAO
        assert [item.rotulo for item in manifesto.itens] == [
            "Regressão",
            "Regressão linear simples — Pressão sistólica ~ Idade",
            "Regressão logística — Óbito ~ Idade",
        ]
        assert [a.arquivo for a in manifesto.itens[1].artefatos] == [
            "coef_pas_idade.csv", "residuos_pas_idade.png", "qq_pas_idade.png",
        ]
        assert manifesto.itens[0].colunas == ("pas", "idade", "servico", "obito")
        assert manifesto.itens[2].colunas == ("obito", "idade")

    def test_os_detalhes_levam_todos_os_modelos(self):
        resultado = _regredir([SIMPLES, ("pas", ["servico"]), LOGISTICA_SIMPLES])
        detalhes = montar_manifesto(resultado, DICIONARIO).itens[0].detalhes
        assert detalhes["testados"] == 2
        assert (detalhes["linear_simples"], detalhes["logistica"]) == (1, 1)
        simples, sem_modelo, logistico = detalhes["modelos"]
        assert simples["ajuste"]["r2"] == pytest.approx(0.594534, abs=1e-6)
        assert sem_modelo["motivo"] == "um valor só em Serviço"
        assert "coeficientes" not in sem_modelo
        assert logistico["evento"] == "Sim"
        assert logistico["coeficientes"][1]["or"] == pytest.approx(1.09850, rel=1e-5)


# ── No disco ────────────────────────────────────────────────────────────────


@pytest.fixture
def projeto_para_regredir(projeto_com_rodada):
    """
    Projeto com banco, dicionário, uma rodada de descritiva e a lista na ficha.
    """

    def montar(bloco: str = BLOCO):
        raiz = projeto_com_rodada()
        acrescentar_a_ficha(raiz, bloco)
        return raiz

    return montar


class TestEscrita:
    def test_preparar_nao_toca_no_disco(self, projeto_para_regredir):
        raiz = projeto_para_regredir()
        antes = len(linhas_do_historico(raiz))
        preparar_regressao(raiz, agora=AGORA)
        assert not (raiz / PASTA_ANALISES / PASTA_REGRESSAO).exists()
        assert len(linhas_do_historico(raiz)) == antes

    def test_executar_escreve_as_tabelas_as_figuras_e_o_manifesto(self, projeto_para_regredir):
        raiz = projeto_para_regredir()
        executar_regressao(preparar_regressao(raiz, agora=AGORA))
        pasta = raiz / PASTA_ANALISES / PASTA_REGRESSAO
        assert sorted(p.name for p in pasta.iterdir()) == [
            "coef_imc_idade_sexo.csv",
            ARQUIVO_MANIFESTO,
            "qq_imc_idade_sexo.png",
            "regressao.csv",
            "residuos_imc_idade_sexo.png",
        ]
        assert ler_manifesto(pasta).analise == ANALISE_REGRESSAO

    def test_sem_graficos_escreve_so_as_tabelas(self, projeto_para_regredir):
        raiz = projeto_para_regredir()
        executar_regressao(preparar_regressao(raiz, com_graficos=False, agora=AGORA))
        pasta = raiz / PASTA_ANALISES / PASTA_REGRESSAO
        assert sorted(p.name for p in pasta.iterdir()) == [
            "coef_imc_idade_sexo.csv", ARQUIVO_MANIFESTO, "regressao.csv",
        ]

    def test_escreve_uma_linha_no_historico(self, projeto_para_regredir):
        raiz = projeto_para_regredir()
        antes = len(linhas_do_historico(raiz))
        executar_regressao(preparar_regressao(raiz, agora=AGORA))
        linhas = linhas_do_historico(raiz)
        assert len(linhas) == antes + 1
        assert f"flatcap regressao {RECORD_ID}" in linhas[-1]
        assert "1 modelo(s) da lista `regressao:` (1 linear múltipla)" in linhas[-1]

    def test_regerar_arquiva_a_rodada_anterior(self, projeto_para_regredir):
        raiz = projeto_para_regredir()
        executar_regressao(preparar_regressao(raiz, com_graficos=False, agora=AGORA))
        resultado = executar_regressao(
            preparar_regressao(raiz, com_graficos=False, agora=AGORA.replace(hour=16))
        )
        arquivada = raiz / PASTA_ANTIGAS / "regressao_2026-09-09_1630"
        assert resultado.arquivado == (raiz / PASTA_ANALISES / PASTA_REGRESSAO, arquivada)
        assert (arquivada / ARQUIVO_MANIFESTO).is_file()

    def test_a_lista_mal_escrita_recusa_antes_de_abrir_o_banco(
        self, projeto_para_regredir, monkeypatch
    ):
        raiz = projeto_para_regredir("regressao:\n  - [imc, idade]\n")

        def nao_abra(*_a, **_k):
            raise AssertionError("o banco foi aberto antes de a lista ser conferida")

        monkeypatch.setattr("flatcap.regressao.abrir", nao_abra)
        with pytest.raises(ModeloInvalidoError):
            preparar_regressao(raiz, agora=AGORA)

    def test_a_simulacao_e_a_execucao_dao_os_mesmos_arquivos(self, projeto_para_regredir):
        raiz = projeto_para_regredir()
        plano = preparar_regressao(raiz, com_graficos=False, agora=AGORA)
        executar_regressao(plano)
        pasta = raiz / PASTA_ANALISES / PASTA_REGRESSAO
        for tabela in plano.tabelas:
            assert (pasta / tabela.nome).read_text(encoding="utf-8") == tabela.texto()


# ── O relatório, que não muda uma linha ─────────────────────────────────────


class TestRelatorio:
    def test_o_relatorio_encontra_a_rodada_sem_nenhum_alerta(self, projeto_para_regredir):
        from flatcap.relatorio import preparar_relatorio

        raiz = projeto_para_regredir()
        executar_regressao(preparar_regressao(raiz, agora=AGORA))
        relatorio = preparar_relatorio(raiz, agora=AGORA).relatorio

        assert relatorio.analises == ("descritiva", "regressao")
        assert relatorio.alertas == ()
        rotulos = [secao.rotulo for secao in relatorio.secoes]
        indice = rotulos.index("Regressão")
        resumo, modelo = relatorio.secoes[indice], relatorio.secoes[indice + 1]
        assert resumo.tabelas[0].colunas[:2] == ("desfecho", "modelo")
        assert modelo.rotulo == "Regressão linear múltipla — imc ~ idade + sexo"
        assert [tabela.colunas[1] for tabela in modelo.tabelas] == ["coeficiente"]
        assert [figura.especie for figura in modelo.figuras] == ["dispersao", "qq"]
        assert "regressão linear múltipla" in " ".join(relatorio.metodologia)

    def test_sem_ficha_mandando_vem_no_fim(self):
        assert ORDEM_PADRAO_DAS_ANALISES[-1] == ANALISE_REGRESSAO

    def test_a_ficha_manda_na_ordem(self, projeto_para_regredir):
        from flatcap.relatorio import preparar_relatorio

        raiz = projeto_para_regredir()
        ficha = raiz / ARQUIVO_PROJETO
        ficha.write_text(
            ficha.read_text(encoding="utf-8").replace(
                "analises: []", "analises:\n  - regressao\n  - descritiva"
            ),
            encoding="utf-8",
        )
        executar_regressao(preparar_regressao(raiz, com_graficos=False, agora=AGORA))
        relatorio = preparar_relatorio(raiz, agora=AGORA).relatorio
        assert relatorio.analises == ("regressao", "descritiva")
        assert relatorio.secoes[0].rotulo == "Regressão"


def test_o_que_so_se_ve_abrindo_a_figura():
    """
    Lembrete, não teste. O que nenhuma asserção daqui pega: os resíduos de um modelo
    de verdade abrindo em funil, o rótulo comprido da fórmula cortado no título, o
    Q-Q com a cauda fora da reta. Antes de mesclar, abrir as figuras de um projeto de
    verdade — uma linear simples e uma múltipla — e olhar.
    """
    assert True
