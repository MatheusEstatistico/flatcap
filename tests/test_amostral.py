# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Os testes do `amostral.py` — a aritmética da amostra, sem projeto, ficha nem banco.

**Nenhum número daqui é conferido contra o próprio módulo.** As referências são três, e
independentes dele:

* os **tamanhos publicados** para 95%, margem de 5 pontos e p = 50% — a tabela de
  Krejcie e Morgan (1970) e as calculadoras do OpenEpi e da Raosoft, que dão 80 para
  N = 100, 278 para N = 1.000 e 370 para N = 10.000. Em N = 500 elas discordam entre si
  por arredondamento: a tabela dá 217, porque arredonda para o mais próximo, e as
  calculadoras dão 218, porque arredondam para cima — que é a regra do FlatCap;
* o **`qnorm` do R**, nos três quantis de sempre: 1,959963984540054 (95%),
  2,575829303548901 (99%) e 1,644853626951472 (90%);
* a **fórmula escrita aqui de novo**, com o quantil do `scipy`, e a forma de Cochran,
  `n₀ / [1 + (n₀ − 1)/N]`, que tem de dar o mesmo número que a do OpenEpi.
"""

from __future__ import annotations

import math
from dataclasses import FrozenInstanceError

import pytest
from scipy import stats

from flatcap.amostral import (
    TOLERANCIA,
    Tamanho,
    com_perda,
    para_cima,
    tamanho_aas,
    tamanho_decidido,
    variancia_da_proporcao,
    z_da_confianca,
)

# O caso de todo dia: 95% de confiança, margem de 5 pontos e p = 50%.
PADRAO = {"confianca": 0.95, "margem": 0.05, "variancia": 0.25}

# O `qnorm` do R, como ele imprime os três quantis de sempre:
#
#     print(qnorm(c(0.975, 0.995, 0.95)), digits = 16)
#     [1] 1.959963984540054 2.575829303548901 1.644853626951472
QNORM_DO_R = {0.95: 1.959963984540054, 0.99: 2.575829303548901, 0.90: 1.644853626951472}


# ── O z ─────────────────────────────────────────────────────────────────────


class TestZ:
    @pytest.mark.parametrize(("confianca", "do_r"), sorted(QNORM_DO_R.items()))
    def test_e_o_qnorm_do_r(self, confianca, do_r):
        assert z_da_confianca(confianca) == pytest.approx(do_r, rel=1e-14)

    @pytest.mark.parametrize("confianca", [0.8, 0.9, 0.95, 0.975, 0.99, 0.999])
    def test_e_o_quantil_do_scipy(self, confianca):
        esperado = stats.norm.ppf(1 - (1 - confianca) / 2)
        assert z_da_confianca(confianca) == pytest.approx(esperado, rel=1e-14)

    @pytest.mark.parametrize("confianca", [0, 1, 95, -0.5, 1.5])
    def test_a_confianca_e_uma_fracao(self, confianca):
        with pytest.raises(ValueError, match="fração"):
            z_da_confianca(confianca)


# ── O arredondamento ────────────────────────────────────────────────────────


class TestParaCima:
    def test_sempre_para_cima(self):
        assert para_cima(277.1) == 278
        assert para_cima(277.9) == 278
        assert para_cima(1.0000001) == 2

    def test_o_inteiro_fica_como_esta(self):
        assert para_cima(278.0) == 278

    def test_o_resto_de_ponto_flutuante_nao_vira_uma_unidade(self):
        """
        Um 278 exato que a conta entrega como 278,00000000000006: o `math.ceil` cru daria
        279, e o cliente iria a campo com uma pessoa a mais por causa da representação de
        um número.
        """
        valor = 278 + 2e-13
        assert math.ceil(valor) == 279
        assert para_cima(valor) == 278

    def test_a_folga_e_muito_menor_que_uma_pessoa(self):
        assert TOLERANCIA < 1e-6


# ── A variância de uma proporção ────────────────────────────────────────────


class TestVarianciaDaProporcao:
    def test_meio_e_o_maior(self):
        assert variancia_da_proporcao(0.5) == 0.25
        assert variancia_da_proporcao(0.3) == pytest.approx(0.21)
        assert all(variancia_da_proporcao(p / 100) < 0.25 for p in range(1, 100) if p != 50)

    @pytest.mark.parametrize("proporcao", [0, 1, 50, -0.1])
    def test_e_uma_fracao_sem_as_pontas(self, proporcao):
        with pytest.raises(ValueError, match="fração"):
            variancia_da_proporcao(proporcao)


# ── O tamanho ───────────────────────────────────────────────────────────────


class TestTamanhoAAS:
    @pytest.mark.parametrize(
        ("populacao", "esperado"),
        [(100, 80), (500, 218), (1000, 278), (1200, 292), (10_000, 370)],
    )
    def test_os_tamanhos_publicados(self, populacao, esperado):
        assert tamanho_aas(**PADRAO, populacao=populacao).n == esperado

    def test_sem_populacao_e_o_n0(self):
        tamanho = tamanho_aas(**PADRAO)
        assert tamanho.n0 == pytest.approx(384.14588206941244, rel=1e-12)
        assert tamanho.n == 385
        assert tamanho.n_corrigido is None
        assert tamanho.populacao is None

    @pytest.mark.parametrize("populacao", [2, 10, 100, 777, 1200, 50_000])
    def test_a_formula_escrita_de_novo(self, populacao):
        z = stats.norm.ppf(0.975)
        termo = z * z * 0.25
        esperado = populacao * termo / ((populacao - 1) * 0.05**2 + termo)
        tamanho = tamanho_aas(**PADRAO, populacao=populacao)
        assert tamanho.n_corrigido == pytest.approx(esperado, rel=1e-12)

    @pytest.mark.parametrize("populacao", [50, 1000, 123_456])
    def test_e_a_correcao_de_cochran(self, populacao):
        """
        A forma do OpenEpi e a de Cochran, `n₀ / [1 + (n₀ − 1)/N]`, são a mesma conta.
        """
        tamanho = tamanho_aas(**PADRAO, populacao=populacao)
        cochran = tamanho.n0 / (1 + (tamanho.n0 - 1) / populacao)
        assert tamanho.n_corrigido == pytest.approx(cochran, rel=1e-12)

    def test_a_media(self):
        """σ = 10 e margem 2, com 95%: n₀ = (1,96 × 10 / 2)² = 96,04 → 97."""
        tamanho = tamanho_aas(confianca=0.95, margem=2, variancia=100)
        assert tamanho.n0 == pytest.approx(96.03647, rel=1e-6)
        assert tamanho.n == 97

    def test_a_perda_entra_por_ultimo(self):
        tamanho = tamanho_aas(**PADRAO, populacao=1200, perda=0.1)
        assert tamanho.n == 292
        assert tamanho.n_final == 325
        assert not tamanho.censo

    def test_a_populacao_toda_e_um_censo(self):
        tamanho = tamanho_aas(**PADRAO, populacao=2)
        assert tamanho.n == 2
        assert tamanho.n_final == 2
        assert tamanho.censo

    def test_a_perda_nao_passa_da_populacao(self):
        """169 de 300, com metade de perda, dariam 338: a amostra é a população inteira."""
        tamanho = tamanho_aas(**PADRAO, populacao=300, perda=0.5)
        assert tamanho.n == 169
        assert tamanho.n_final == 300
        assert tamanho.censo

    def test_uma_unidade(self):
        tamanho = tamanho_aas(**PADRAO, populacao=1)
        assert (tamanho.n, tamanho.n_final, tamanho.censo) == (1, 1, True)

    def test_o_z_fica_guardado(self):
        assert tamanho_aas(**PADRAO).z == pytest.approx(1.959963984540054, rel=1e-14)

    @pytest.mark.parametrize(
        ("campo", "valor", "frase"),
        [
            ("margem", 0, "margem"),
            ("margem", -0.05, "margem"),
            ("variancia", 0, "variância"),
            ("populacao", 0, "população"),
            ("confianca", 95, "fração"),
            ("perda", 1, "perda"),
        ],
    )
    def test_fora_do_dominio_e_valueerror(self, campo, valor, frase):
        argumentos = {**PADRAO, "populacao": 100, campo: valor}
        with pytest.raises(ValueError, match=frase):
            tamanho_aas(**argumentos)

    def test_e_imutavel(self):
        with pytest.raises(FrozenInstanceError):
            tamanho_aas(**PADRAO).n = 1  # type: ignore[misc]


class TestComPerda:
    def test_dez_por_cento(self):
        assert com_perda(292, 0.1) == 325
        assert com_perda(385, 0.1) == 428

    def test_sem_perda_e_o_mesmo(self):
        assert com_perda(292, 0) == 292

    def test_o_que_sobra_cobre_o_necessario(self):
        for n in (1, 7, 80, 292, 1000):
            for perda in (0.05, 0.1, 0.2, 0.33):
                assert com_perda(n, perda) * (1 - perda) >= n - 1e-9

    @pytest.mark.parametrize("perda", [1, 1.5, -0.1, 10])
    def test_a_perda_e_uma_fracao_sem_o_um(self, perda):
        with pytest.raises(ValueError, match="perda"):
            com_perda(100, perda)


class TestTamanhoDecidido:
    def test_sem_conta(self):
        tamanho = tamanho_decidido(300)
        assert (tamanho.n, tamanho.n_final) == (300, 300)
        assert tamanho.decidido
        assert tamanho.z is None and tamanho.n0 is None and tamanho.n_corrigido is None

    def test_a_perda_soma(self):
        assert tamanho_decidido(300, perda=0.1).n_final == 334

    def test_a_perda_nao_passa_da_populacao(self):
        tamanho = tamanho_decidido(300, populacao=320, perda=0.1)
        assert tamanho.n_final == 320
        assert tamanho.censo

    def test_maior_que_a_populacao_e_valueerror(self):
        with pytest.raises(ValueError, match="passa da população"):
            tamanho_decidido(500, populacao=300)

    def test_zero_e_valueerror(self):
        with pytest.raises(ValueError, match="pelo menos 1"):
            tamanho_decidido(0)

    def test_a_conta_nao_e_decidida(self):
        assert not tamanho_aas(**PADRAO).decidido


def test_o_tamanho_se_monta_a_mao():
    """O `Tamanho` é um dado: o `amostragem.py` e os testes o montam sem passar pela conta."""
    tamanho = Tamanho(n=10, n_final=12, populacao=100, perda=0.15)
    assert not tamanho.censo
    assert tamanho.decidido


def test_o_modulo_nao_traz_o_pandas_nem_o_scipy():
    """
    Só biblioteca padrão: é o que deixa o comando da amostragem partir rápido. Conferido em
    processo limpo, porque nesta sessão de teste os dois já foram importados por outros.
    """
    import subprocess
    import sys

    codigo = (
        "import sys; import flatcap.amostral; "
        "print(sorted(m for m in ('pandas', 'scipy', 'numpy') if m in sys.modules))"
    )
    saida = subprocess.run(
        [sys.executable, "-c", codigo], capture_output=True, text=True, check=True
    ).stdout.strip()
    assert saida == "[]"
