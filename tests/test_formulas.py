# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Os testes do `formulas.py` — a árvore de uma fórmula, a fórmula entre cifrões, e os dois
textos dela: o de uma linha, do terminal, e o formatado, da fórmula no meio da frase.

Como a fórmula vira equação do Word é do `test_documento.py`; o que a amostragem escreve
com ela, do `test_amostragem.py`.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from flatcap.formulas import (
    ESPACO_DA_FORMULA,
    Delimitada,
    Equacao,
    Formula,
    Fracao,
    Paragrafo,
    Potencia,
    Simbolo,
    Texto,
    Trecho,
    formula,
    fracao,
    ler_formula,
    paragrafo,
    parenteses,
    potencia,
    tem_fracao,
    teto,
    texto_de,
    trechos_de,
)

N0 = Simbolo("n", "0")
Z = Simbolo("z")
P = Simbolo("p")
E = Simbolo("e")


def n0_da_proporcao() -> Formula:
    """A fórmula do n₀ do relatório da amostra, montada à mão."""
    return formula(
        N0,
        "=",
        fracao(formula(potencia(Z, "2"), "×", P, "×", parenteses("1", "−", P)), potencia(E, "2")),
        "=",
        fracao(formula(potencia("1,96", "2"), "×", "0,5", "×", "0,5"), potencia("0,05", "2")),
        "=",
        "384,16",
    )


# ── As peças ────────────────────────────────────────────────────────────────


class TestPecas:
    def test_o_texto_vira_texto_e_a_formula_de_dentro_se_desfaz(self):
        dentro = formula(Z, "=", "1,96")
        assert formula(N0, dentro, "+", "1") == Formula(
            (N0, Z, Texto("="), Texto("1,96"), Texto("+"), Texto("1"))
        )

    def test_a_fracao_a_potencia_e_os_parenteses_guardam_formulas(self):
        assert fracao("1", Z) == Fracao(Formula((Texto("1"),)), Formula((Z,)))
        assert potencia(Z, "2") == Potencia(Formula((Z,)), Formula((Texto("2"),)))
        assert parenteses("1", "−", P) == Delimitada(
            Formula((Texto("1"), Texto("−"), P))
        )

    def test_o_teto_e_entre_os_colchetes_do_teto(self):
        assert teto("348,89") == Delimitada(Formula((Texto("348,89"),)), "⌈", "⌉")

    def test_vazio_e_falso(self):
        assert not Formula()
        assert not Equacao(Formula())
        assert not paragrafo("")
        assert not paragrafo("   ")
        assert paragrafo("Onde:")
        assert paragrafo("$N$")


# ── A fórmula entre cifrões ─────────────────────────────────────────────────


class TestEntreCifroes:
    def test_a_frase_com_a_populacao(self):
        """A frase da correção, como a amostragem a escreve."""
        lido = paragrafo("Como a população é finita, com $N = 1700$ unidades, foi corrigido:")
        assert lido == Paragrafo(
            (
                "Como a população é finita, com ",
                Formula((Simbolo("N"), Texto("="), Texto("1700"))),
                " unidades, foi corrigido:",
            )
        )

    def test_sem_cifrao_e_texto_so(self):
        assert paragrafo("Onde:") == Paragrafo(("Onde:",))

    def test_a_formula_no_comeco_e_o_junto(self):
        lido = paragrafo("$n_0$ = tamanho da amostra;", junto=True)
        assert lido.partes == (Formula((N0,)), " = tamanho da amostra;")
        assert lido.junto

    def test_o_cifrao_de_verdade(self):
        assert paragrafo(r"custa R\$ 10 e \$ 20") == Paragrafo(("custa R$ 10 e $ 20",))

    def test_o_cifrao_sem_par_fica_como_esta(self):
        assert paragrafo("custa R$ 10") == Paragrafo(("custa R$ 10",))

    @pytest.mark.parametrize(
        ("escrito", "lido"),
        [
            ("z", (Z,)),
            ("n_0", (N0,)),
            ("n_f", (Simbolo("n", "f"),)),
            ("x_{ab}", (Simbolo("x", "ab"),)),
            ("σ", (Simbolo("σ"),)),
            ("perda", (Texto("perda"),)),
            ("0,05", (Texto("0,05"),)),
            ("1700", (Texto("1700"),)),
            ("z^2", (Potencia(Formula((Z,)), Formula((Texto("2"),))),)),
            ("e^{n-1}", (
                Potencia(
                    Formula((E,)),
                    Formula((Simbolo("n"), Texto("−"), Texto("1"))),
                ),
            )),
            ("2 * 3", (Texto("2"), Texto("×"), Texto("3"))),
            ("1 - p", (Texto("1"), Texto("−"), P)),
        ],
    )
    def test_a_escrita_minima(self, escrito, lido):
        assert ler_formula(escrito) == Formula(lido)

    def test_o_parentese_e_um_grupo(self):
        """Para os parênteses crescerem com o que têm dentro, no Word."""
        assert ler_formula("292 / (1 - 0,1)") == Formula(
            (
                Texto("292"),
                Texto("/"),
                Delimitada(Formula((Texto("1"), Texto("−"), Texto("0,1")))),
            )
        )
        assert ler_formula("(a + b)^2") == formula(
            potencia(parenteses(Simbolo("a"), "+", Simbolo("b")), "2")
        )

    def test_o_parentese_sem_par_sai_como_esta(self):
        assert texto_de(ler_formula("1 - (2")) == "1 − ( 2"
        assert texto_de(ler_formula(") a")) == ") a"

    def test_o_expoente_sem_base_sai_como_esta(self):
        assert ler_formula("^2") == Formula((Texto("^"), Texto("2")))


# ── O texto de uma linha ────────────────────────────────────────────────────


class TestTextoDe:
    def test_a_formula_do_n0(self):
        assert texto_de(n0_da_proporcao()) == (
            "n₀ = (z² × p × (1 − p)) / e² = (1,96² × 0,5 × 0,5) / 0,05² = 384,16"
        )

    def test_a_fracao_dentro_da_fracao(self):
        n = formula(
            Simbolo("n"),
            "=",
            fracao(N0, formula("1", "+", fracao(formula(N0, "−", "1"), Simbolo("N")))),
        )
        assert texto_de(n) == "n = n₀ / (1 + (n₀ − 1) / N)"

    def test_o_indice_e_o_expoente_sem_caractere_unicode(self):
        assert texto_de(Simbolo("n", "f")) == "n_f"
        assert texto_de(Simbolo("x", "ab")) == "x_(ab)"
        assert texto_de(potencia(E, "z")) == "e^z"
        assert texto_de(potencia(E, formula("n", "−", "1"))) == "eⁿ⁻¹"

    def test_os_blocos(self):
        assert texto_de(paragrafo("com $N = 1700$ unidades")) == "com N = 1700 unidades"
        assert texto_de(Equacao(formula(Z, "=", "1,96"))) == "z = 1,96"
        assert texto_de(teto("348,89")) == "⌈348,89⌉"

    def test_o_que_nao_e_formula(self):
        with pytest.raises(TypeError):
            texto_de(3.14)  # type: ignore[arg-type]


# ── A fórmula da linha como texto formatado ─────────────────────────────────


class TestTrechos:
    def test_a_populacao(self):
        """`N = 1700`: o N em itálico, e os espaços inquebráveis."""
        assert trechos_de(ler_formula("N = 1700")) == (
            Trecho("N", italico=True),
            Trecho(ESPACO_DA_FORMULA),
            Trecho("="),
            Trecho(ESPACO_DA_FORMULA),
            Trecho("1700"),
        )
        assert ESPACO_DA_FORMULA == " "

    def test_o_indice_de_numero_e_em_pe_e_o_de_letra_em_italico(self):
        assert trechos_de(Formula((N0,))) == (
            Trecho("n", italico=True),
            Trecho("0", posicao="indice"),
        )
        assert trechos_de(Formula((Simbolo("n", "f"),))) == (
            Trecho("n", italico=True),
            Trecho("f", italico=True, posicao="indice"),
        )

    def test_o_expoente_e_os_parenteses(self):
        assert trechos_de(formula(potencia("1,96", "2"))) == (
            Trecho("1,96"),
            Trecho("2", posicao="expoente"),
        )
        texto = "".join(t.texto for t in trechos_de(ler_formula("292 / (1 - 0,1) = 324,44")))
        assert texto.replace(ESPACO_DA_FORMULA, " ") == "292 / (1 − 0,1) = 324,44"

    def test_o_texto_dos_trechos_e_o_de_uma_linha(self):
        """Fora a formatação e os espaços, os dois textos dizem o mesmo."""
        for escrito in ("N = 1700", "n_0", "1 - 0,5", "292 / (1 - 0,1) = 324,44"):
            formula_ = ler_formula(escrito)
            juntos = "".join(t.texto for t in trechos_de(formula_))
            assert juntos.replace(ESPACO_DA_FORMULA, " ").replace("n0", "n₀") == texto_de(
                formula_
            )

    def test_a_fracao_e_o_que_nao_cabe_no_texto(self):
        assert tem_fracao(n0_da_proporcao())
        assert tem_fracao(formula(parenteses(fracao("1", "2"))))
        assert tem_fracao(formula(potencia(Z, fracao("1", "2"))))
        assert not tem_fracao(ler_formula("292 / (1 - 0,1) = 324,44"))
        assert not tem_fracao(ler_formula("z^2"))


# ── A arquitetura ───────────────────────────────────────────────────────────


def test_nao_traz_dependencia_nenhuma():
    """A amostragem monta o documento na simulação, sem o `python-docx`."""
    codigo = (
        "import sys; import flatcap.formulas; "
        "print(sorted(m for m in ('docx', 'pandas', 'lxml') if m in sys.modules))"
    )
    saida = subprocess.run(
        [sys.executable, "-c", codigo], capture_output=True, text=True, check=True
    ).stdout.strip()
    assert saida == "[]"
