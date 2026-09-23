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
para cada caminho da regra.
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
    ARQUIVO_TABELA,
    REGRA,
    UMA_AMOSTRA,
    WILCOXON,
    ItemInvalidoError,
    Normal,
    SemItensError,
    VariavelIncompativelError,
    comparar,
    executar_comparacao,
    itens_da_ficha,
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


def _uma(nome: str, valores: list) -> tuple[pd.DataFrame, tuple[Linha, ...]]:
    """Um banco de uma coluna só, com a linha do dicionário que a declara numérica."""
    return pd.DataFrame({nome: valores}), (Linha(nome, nome.upper(), NUMERICA),)


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

    def test_a_normal_rejeitada_escolhe_o_wilcoxon_e_a_linha_sai_sem_teste(self):
        linha = _linha(_comparar(), "renda")
        assert linha.resultado is None
        assert (linha.escolha.metodo, linha.escolha.da_regra) == ("", WILCOXON)
        assert linha.escolha.motivo == "o Shapiro-Wilk rejeita a normal (p < 0,001)"
        assert linha.celula_do_teste == "não testado: normal rejeitada"

    def test_o_p_do_shapiro_fica_na_nota_e_nao_na_celula(self):
        """
        Na coluna estreita do documento, `(p < 0,001)` quebrava entre o `<` e o número.
        A célula diz o motivo; o p que decidiu fica na frase da nota.
        """
        comparacao = _comparar()
        linha = _linha(comparacao, "dor")
        assert linha.celula_do_teste == "não testado: normal rejeitada"
        assert "o Shapiro-Wilk rejeita a normal (p = 0,005)" in linha.justificativa
        assert "o Shapiro-Wilk rejeita a normal (p = 0,005)" in comparacao.tabela.texto()

    def test_a_linha_sem_teste_ensina_a_escrever_t_no_item(self):
        avisos = _comparar().avisos
        assert any(
            "a regra escolheria Wilcoxon, que ainda não está no FlatCap" in aviso
            and "`[renda, 2500, t]`" in aviso
            for aviso in avisos
        )

    def test_dois_valores_nao_verificam_a_normalidade(self):
        """O Shapiro-Wilk precisa de três; o t, de dois. Sem o t escrito, não há teste."""
        quadro, linhas = _uma("a", [24.0, 27.0, None])
        linha = _comparar(quadro, linhas, (("a", 25),)).variaveis[0]
        assert linha.celula_do_teste == "não testado: normalidade não verificável com 2 valores"
        assert "a normalidade não pôde ser verificada" in linha.escolha.motivo

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
        """O Wilcoxon está na regra e não no cálculo — é a próxima linha dele."""
        assert REGRA[UMA_AMOSTRA] == (T_DE_STUDENT, WILCOXON)
        rejeitada = regra(UMA_AMOSTRA, Normal(w=0.9, p=0.01))
        assert (rejeitada.metodo, rejeitada.da_regra) == ("", WILCOXON)
        sustentada = regra(UMA_AMOSTRA, Normal(w=0.99, p=0.5))
        assert (sustentada.metodo, sustentada.da_regra) == (T_DE_STUDENT, T_DE_STUDENT)

    def test_o_limite_da_regra_e_o_alfa_da_normalidade(self):
        """p = 0,05 não rejeita: é o `p < ALFA` da normalidade, e não `≤`."""
        assert regra(UMA_AMOSTRA, Normal(w=0.97, p=0.05)).metodo == T_DE_STUDENT
        assert regra(UMA_AMOSTRA, Normal(w=0.97, p=0.0499)).metodo == ""

    def test_a_escolha_de_cada_linha_esta_escrita_na_nota(self):
        texto = _comparar().tabela.texto()
        assert (
            "IMC (kg/m²): n = 57; o Shapiro-Wilk não rejeita a normal (p = 1,000) → "
            "t de Student (t = 2,16; 56 gl)." in texto
        )
        assert (
            "Renda: n = 60; o Shapiro-Wilk rejeita a normal (p < 0,001) → Wilcoxon, que "
            "ainda não está no FlatCap: a linha sai sem teste." in texto
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
            "escolheria Wilcoxon, que ainda não está no FlatCap: o Shapiro-Wilk rejeita "
            "a normal (p < 0,001)."
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
        assert metodo_escrito("wilcoxon") == ""
        assert metodo_escrito("tt") == ""


# ── Quando não há teste ─────────────────────────────────────────────────────


class TestSemTeste:
    def test_um_valor_so_em_todas_as_linhas(self):
        resultado = _comparar()
        assert _linha(resultado, "servico").resultado is None
        assert resultado.tabela.linhas[4] == (
            "Serviço", "60", "1 (0)", "—", "1", "não testado: um valor só em todas as linhas",
            "—",
        )
        assert any("critério de inclusão" in aviso for aviso in resultado.avisos)

    def test_nenhum_valor_preenchido(self):
        quadro, linhas = _uma("a", [None, None, None])
        linha = _comparar(quadro, linhas, (("a", 25),)).tabela.linhas[0]
        assert linha == ("A", "0", "—", "—", "25", "não testado: nenhum valor preenchido", "—")

    def test_um_valor_preenchido(self):
        quadro, linhas = _uma("a", [None, 30.0, None])
        linha = _comparar(quadro, linhas, (("a", 25, "t"),)).tabela.linhas[0]
        assert linha[5] == "não testado: 1 valor — o teste precisa de pelo menos 2"

    def test_valores_que_so_variam_no_ultimo_bit(self):
        """O `data are essentially constant` do R: variar no último bit não é variar."""
        base = 1e6
        quadro, linhas = _uma("a", [base, math.nextafter(base, math.inf), base, base])
        linha = _comparar(quadro, linhas, (("a", 25, "t"),)).tabela.linhas[0]
        assert linha[5] == "não testado: os valores praticamente não variam"

    def test_a_media_sai_mesmo_sem_teste(self):
        """A média e o desvio descrevem a variável, e não dependem de pressuposto."""
        linha = _comparar().tabela.linhas[1]
        assert linha[:3] == ("Renda", "60", "3406,12 (3005,93)")
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
            ("pas", 120.5, T_DE_STUDENT),
            ("imc", 24.9, ""),
            ("delta", -1.5, T_DE_STUDENT),
        ]

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

    def test_comparar_grupos_ainda_nao_existe(self, projeto_vazio):
        mensagem = _recusa(projeto_vazio, "  - [imc, sexo]\n")
        assert "`sexo` não é um número" in mensagem
        assert "ainda não está no FlatCap" in mensagem

    def test_o_wilcoxon_escrito_ainda_nao_existe(self, projeto_vazio):
        mensagem = _recusa(projeto_vazio, "  - [imc, 25, Wilcoxon]\n")
        assert "o Wilcoxon ainda não está no FlatCap" in mensagem

    def test_o_terceiro_nome_que_nao_e_metodo(self, projeto_vazio):
        assert "`mediana` não é um método" in _recusa(projeto_vazio, "  - [imc, 25, mediana]\n")

    def test_a_forma_com_dois_pontos_recusa_e_ensina(self, projeto_vazio):
        mensagem = _recusa(projeto_vazio, "  - imc: 25\n  - sexo: [imc, pas]\n")
        assert "vai dentro dos colchetes, junto do nome: `[imc, 25]`" in mensagem
        assert "chega com a comparação entre grupos" in mensagem

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
        mensagem = _recusa(projeto_vazio, "  - [imc]\n  - [pas, 120]\n  - [dor, x]\n")
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
        assert _comparar().tabela.colunas == (
            "variável",
            "n",
            "média (DP)",
            "IC 95% da média",
            "referência",
            "teste",
            "p-valor",
        )

    def test_a_tabela_do_banco_de_referencia(self):
        """
        Linha por linha, com cada número tirado do R e formatado aqui: a média e o
        desvio como a descritiva escreve, o intervalo com duas casas fixas.
        """
        imc = REFERENCIAS_DO_R[0]
        pas = REFERENCIAS_DO_R[1]
        renda = REFERENCIAS_DO_R[2]
        dor = REFERENCIAS_DO_R[4]

        def media_dp(referencia):
            return f"{_como_a_descritiva(referencia[7])} ({_como_a_descritiva(referencia[8])})"

        def faixa(ic):
            return f"{_duas_casas(ic[0])} a {_duas_casas(ic[1])}"

        assert _comparar().tabela.linhas == (
            ("IMC (kg/m²)", "57", media_dp(imc), faixa(imc[6]), "25", T_DE_STUDENT,
             valor_p(imc[5])),
            ("Renda", "60", media_dp(renda), "—", "2500", "não testado: normal rejeitada",
             "—"),
            ("PAS (mmHg)", "12", media_dp(pas), faixa(pas[6]), "120", T_DE_STUDENT,
             valor_p(pas[5])),
            ("Dor", "60", media_dp(dor), "—", "2", "não testado: normal rejeitada", "—"),
            ("Serviço", "60", "1 (0)", "—", "1", "não testado: um valor só em todas as linhas",
             "—"),
        )

    def test_a_media_e_letra_por_letra_a_do_resumo_da_descritiva(self):
        """
        A média e o desvio saem pela função e pelo formatador da descritiva: a célula
        `média (DP)` é, letra por letra, o que o `resumo_<variável>.csv` imprime.
        """
        from flatcap.descritiva import descrever

        quadro = bancos.para_comparar()
        descritiva = descrever(banco_em_memoria(quadro), ficha_em_memoria(), DICIONARIO, AGORA)
        comparacao = _comparar(quadro)
        for nome in ("imc", "renda", "pas", "dor", "servico"):
            resumo = next(v for v in descritiva.variaveis if v.variavel == nome).tabelas[0]
            celulas = dict(resumo.linhas)
            linha = comparacao.tabela.linhas[[v.variavel for v in comparacao.variaveis].index(nome)]
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
        linha = _comparar(itens=(("imc", 20),)).tabela.linhas[0]
        assert linha[6] == "< 0,001"

    def test_a_tabela_nao_e_de_uma_variavel(self):
        tabela = _comparar().tabela
        assert (tabela.variavel, tabela.nome) == ("", ARQUIVO_TABELA)
        texto = tabela.texto()
        assert "# variável:" not in texto
        assert "t.test do R" in texto
        assert "o Wilcoxon, que ainda não está no FlatCap" in texto
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
        assert (renda["teste"], renda["teste_da_regra"]) == (None, WILCOXON)
        assert renda["shapiro"]["rejeita"] is True
        assert (servico["shapiro"], servico["motivo"]) == (None, "um valor só em todas as linhas")
        assert (detalhes["testadas"], detalhes["sem_teste"]) == (2, 3)

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
        assert "Wilcoxon, que ainda não está no FlatCap" in regras["escolha_do_teste"]
        assert regras["hipotese"] == "bilateral"

    def test_fora_lista_quem_nao_esta_em_item(self):
        manifesto = montar_manifesto(_comparar(), DICIONARIO)
        assert {entrada["variavel"] for entrada in manifesto.fora} == {"sexo"}

    def test_a_ordem_padrao_poe_a_comparacao_depois_da_correlacao(self):
        posicao = ORDEM_PADRAO_DAS_ANALISES.index
        assert posicao(ANALISE_COMPARACAO) == posicao(ANALISE_CORRELACAO) + 1
        assert ORDEM_PADRAO_DAS_ANALISES[-1] == ANALISE_COMPARACAO


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

    def test_a_simulacao_e_a_execucao_dao_o_mesmo_arquivo(self, projeto_para_comparar):
        raiz = projeto_para_comparar()
        plano = preparar_comparacao(raiz, agora=AGORA)
        executar_comparacao(plano)
        escrito = (raiz / PASTA_ANALISES / PASTA_COMPARACAO / ARQUIVO_TABELA).read_text(
            encoding="utf-8"
        )
        assert escrito == plano.tabela.texto()


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
