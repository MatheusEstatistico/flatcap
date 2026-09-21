"""
Os testes do `associacao.py`.

O miolo é testado pela função pura `associar(banco, ficha, linhas, pares)`, como o
`cruzar` do cruzamento e o `avaliar` da normalidade. O caminho do disco — a ficha
com a lista `associacao:`, a rodada escrita, o relatório que a encontra — usa os
fixtures do `conftest.py`.

**Nenhum p daqui é conferido contra o próprio módulo.** As referências são três, e
independentes dele:

* os valores publicados na documentação do R — `fisher.test` com o `Job` (4×4) e
  o `MP6` (5×7), o `TeaTasting` e o `Convictions`; `chisq.test` com a tabela de
  partido por sexo;
* o `scipy` onde ele faz o mesmo que o R: o Fisher 2×2 e o qui-quadrado, com e sem
  Yates;
* a força bruta: todas as tabelas com as mesmas margens, somadas em **frações
  exatas** — sem ponto flutuante e sem folga, o que confere de passagem que a
  folga do R não deixou de fora a tabela empatada com a observada.

O banco de referência é o `bancos.para_associar()`: dois grupos de 40 e uma
variável para cada caminho da regra de Cochran.
"""

from __future__ import annotations

import math
import random
from fractions import Fraction

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
from flatcap.associacao import (
    LIMITE_DO_CALCULO_EXATO,
    TESTE_FISHER,
    TESTE_QUI_QUADRADO,
    TESTE_YATES,
    CalculoExatoGrandeError,
    ParInvalidoError,
    SemParesError,
    VariavelIncompativelError,
    associar,
    contingencia,
    executar_associacao,
    fisher_exato,
    montar_manifesto,
    pares_da_ficha,
    preparar_associacao,
    qui_quadrado,
    regra_de_cochran,
)
from flatcap.cruzamento import cruzar
from flatcap.dicionario import CATEGORICA, IGNORAR, NUMERICA, Linha
from flatcap.manifesto import (
    ANALISE_ASSOCIACAO,
    ANALISE_CRUZAMENTO,
    ARQUIVO_MANIFESTO,
    ORDEM_PADRAO_DAS_ANALISES,
)
from flatcap.manifesto import ler as ler_manifesto
from flatcap.normalidade import valor_p
from flatcap.projeto import ARQUIVO_PROJETO, PASTA_ANALISES, PASTA_ANTIGAS, PASTA_ASSOCIACAO

GRUPO = Linha("grupo", "Grupo", CATEGORICA, ("Controle", "Intervenção"))
DESFECHO = Linha(
    "desfecho",
    "Desfecho",
    CATEGORICA,
    ("0", "1"),
    rotulos_das_categorias=(("0", "Não"), ("1", "Sim")),
)
COMPLICACAO = Linha("complicacao", "Complicação", CATEGORICA, ("Não", "Sim"))
ESCOLARIDADE = Linha(
    "escolaridade",
    "Escolaridade",
    CATEGORICA,
    ("Fundamental", "Médio", "Superior", "Pós-graduação"),
)
FAIXA = Linha("faixa_etaria", "Faixa etária", CATEGORICA, ("18 a 39", "40 a 59", "60 ou mais"))
SERVICO = Linha("servico", "Serviço", CATEGORICA)
DICIONARIO = (GRUPO, DESFECHO, COMPLICACAO, ESCOLARIDADE, FAIXA, SERVICO)

# `grupo: [desfecho, complicacao, escolaridade, faixa_etaria]`, já desdobrado.
UMA_CONTRA_VARIAS = (
    ("grupo", "desfecho"),
    ("grupo", "complicacao"),
    ("grupo", "escolaridade"),
    ("grupo", "faixa_etaria"),
)

# O que se escreve na ficha para o banco de referência do `conftest`, que tem
# `sexo` e `escolaridade` em texto — as duas marcadas `categorica` pelo perfil.
BLOCO = "associacao:\n  - [sexo, escolaridade]\n"

# As tabelas da documentação do R. O `matrix(c(...), 4, 4)` do R preenche por
# coluna, então o `Job` aparece aqui já transposto para a forma de linhas.
JOB = [[1, 3, 10, 6], [2, 3, 10, 7], [1, 6, 14, 12], [0, 1, 9, 11]]
MP6 = [
    [1, 2, 2, 1, 1, 0, 1],
    [2, 0, 0, 2, 3, 0, 0],
    [0, 1, 1, 1, 2, 7, 3],
    [1, 1, 2, 0, 0, 0, 1],
    [0, 1, 1, 1, 1, 0, 0],
]


def _associar(quadro=None, linhas=DICIONARIO, pedidos=UMA_CONTRA_VARIAS, **opcoes):
    quadro = bancos.para_associar() if quadro is None else quadro
    return associar(
        banco_em_memoria(quadro), ficha_em_memoria(), linhas, pedidos, AGORA, **opcoes
    )


def _par(resultado, variavel_2: str):
    return next(par for par in resultado.pares if par.variavel_2 == variavel_2)


def _tabelas_com_margens(linhas: list[int], colunas: list[int]):
    """Todas as tabelas com estas margens, linha por linha."""
    if len(linhas) == 1:
        yield [list(colunas)]
        return

    def distribuir(total, tetos):
        if len(tetos) == 1:
            if total <= tetos[0]:
                yield [total]
            return
        for x in range(min(total, tetos[0]), -1, -1):
            if total - x <= sum(tetos[1:]):
                for resto in distribuir(total - x, tetos[1:]):
                    yield [x, *resto]

    for primeira in distribuir(linhas[0], colunas):
        restantes = [c - x for c, x in zip(colunas, primeira, strict=True)]
        for outras in _tabelas_com_margens(linhas[1:], restantes):
            yield [primeira, *outras]


def _fisher_forca_bruta(tabela: list[list[int]]) -> float:
    """
    O p do Fisher pela definição, em frações exatas: a soma das probabilidades das
    tabelas com as mesmas margens e probabilidade menor ou igual à observada.
    """
    linhas = [sum(linha) for linha in tabela]
    colunas = [sum(coluna) for coluna in zip(*tabela, strict=True)]
    n = sum(linhas)
    margens = math.prod(math.factorial(x) for x in linhas + colunas)

    def probabilidade(t) -> Fraction:
        celulas = math.prod(math.factorial(x) for linha in t for x in linha)
        return Fraction(margens, math.factorial(n) * celulas)

    observada = probabilidade(tabela)
    total = sum(
        (p for p in map(probabilidade, _tabelas_com_margens(linhas, colunas)) if p <= observada),
        Fraction(0),
    )
    return float(total)


def _tabela_aleatoria(gerador: random.Random, linhas: int, colunas: int, teto: int):
    while True:
        tabela = [[gerador.randint(0, teto) for _ in range(colunas)] for _ in range(linhas)]
        if all(sum(linha) for linha in tabela) and all(sum(c) for c in zip(*tabela)):
            return tabela


# ── As referências publicadas ───────────────────────────────────────────────


class TestReferenciasDoR:
    def test_fisher_job_4x4(self):
        """`fisher.test(Job) # 0.7827` — a linha da documentação do R."""
        assert round(fisher_exato(JOB), 4) == 0.7827

    def test_fisher_mp6_5x7(self):
        """O sexto exemplo de Mehta e Patel, que a documentação do R também roda."""
        assert round(fisher_exato(MP6), 5) == 0.03929

    def test_fisher_2x2_tea_tasting_e_convictions(self):
        assert round(fisher_exato([[3, 1], [1, 3]]), 4) == 0.4857
        assert fisher_exato([[2, 10], [15, 3]]) == pytest.approx(0.0005367, rel=1e-3)

    def test_chisq_test_da_tabela_de_partido_por_sexo(self):
        """`chisq.test(M)`: X-squared = 30.07, df = 2, p-value = 2.954e-07."""
        estatistica, gl, p, yates = qui_quadrado([[762, 327, 468], [484, 239, 477]])
        assert round(estatistica, 2) == 30.07
        assert gl == 2
        assert p == pytest.approx(2.954e-07, rel=1e-3)
        assert not yates


# ── O Fisher exato ──────────────────────────────────────────────────────────


class TestFisherExato:
    def test_2x2_e_o_do_scipy(self):
        gerador = random.Random(42)
        for _ in range(300):
            tabela = _tabela_aleatoria(gerador, 2, 2, 25)
            assert fisher_exato(tabela) == pytest.approx(
                stats.fisher_exact(tabela).pvalue, abs=1e-10
            ), tabela

    @pytest.mark.parametrize("forma", [(2, 3), (3, 2), (3, 3), (2, 4), (3, 4)])
    def test_maior_que_2x2_e_a_forca_bruta(self, forma):
        gerador = random.Random(sum(forma))
        for _ in range(12):
            tabela = _tabela_aleatoria(gerador, *forma, teto=4)
            assert fisher_exato(tabela) == pytest.approx(
                _fisher_forca_bruta(tabela), abs=1e-10
            ), tabela

    def test_a_tabela_empatada_com_a_observada_entra(self):
        """
        Numa tabela simétrica a espelhada tem **exatamente** a mesma probabilidade,
        e em ponto flutuante as duas contas podem diferir na última casa. É para
        isso que existe a folga do R: sem ela, metade do p sumiria.
        """
        for tabela in ([[2, 1, 1], [1, 2, 1]], [[3, 0, 1], [0, 3, 1]], [[2, 2], [2, 2]]):
            assert fisher_exato(tabela) == pytest.approx(_fisher_forca_bruta(tabela), abs=1e-12)

    def test_nem_a_ordem_nem_a_orientacao_mudam_o_p(self):
        tabela = [[3, 1, 4, 0], [2, 6, 1, 3], [1, 1, 2, 5]]
        referencia = fisher_exato(tabela)
        transposta = [list(coluna) for coluna in zip(*tabela, strict=True)]
        invertida = [list(reversed(linha)) for linha in reversed(tabela)]
        assert fisher_exato(transposta) == pytest.approx(referencia, abs=1e-12)
        assert fisher_exato(invertida) == pytest.approx(referencia, abs=1e-12)

    def test_o_p_e_o_mesmo_em_toda_rodada(self):
        """
        O que o `scipy` não garante para tabela maior que 2×2: ele simula, sem
        semente. Aqui não há sorteio nenhum.
        """
        tabela = [[3, 1, 4], [2, 6, 1]]
        assert len({fisher_exato(tabela) for _ in range(5)}) == 1
        assert fisher_exato(tabela) == pytest.approx(_fisher_forca_bruta(tabela), abs=1e-12)

    def test_passar_do_limite_levanta_o_erro_proprio(self):
        with pytest.raises(CalculoExatoGrandeError, match="passou de 1000 operações"):
            fisher_exato(JOB, limite=1000)

    def test_o_limite_padrao_da_conta_das_tabelas_de_referencia(self):
        assert fisher_exato(JOB, limite=LIMITE_DO_CALCULO_EXATO) > 0


# ── O qui-quadrado ──────────────────────────────────────────────────────────


class TestQuiQuadrado:
    def test_yates_so_na_2x2(self):
        assert qui_quadrado([[12, 5], [7, 9]])[3] is True
        assert qui_quadrado([[12, 5, 6], [7, 9, 8]])[3] is False

    def test_2x2_com_yates_e_o_do_scipy(self):
        """O `scipy` corrige como o R desde a 1.7: nunca mais que a diferença."""
        gerador = random.Random(7)
        for _ in range(300):
            tabela = [[gerador.randint(1, 40) for _ in range(2)] for _ in range(2)]
            estatistica, gl, p, _ = qui_quadrado(tabela)
            esperado = stats.chi2_contingency(tabela, correction=True)
            assert estatistica == pytest.approx(esperado.statistic, abs=1e-9)
            assert p == pytest.approx(esperado.pvalue, abs=1e-12)
            assert gl == 1

    def test_maior_que_2x2_e_o_do_scipy(self):
        gerador = random.Random(11)
        for _ in range(100):
            tabela = [[gerador.randint(1, 30) for _ in range(4)] for _ in range(3)]
            estatistica, gl, p, _ = qui_quadrado(tabela)
            esperado = stats.chi2_contingency(tabela)
            assert (estatistica, gl) == (pytest.approx(esperado.statistic), esperado.dof)
            assert p == pytest.approx(esperado.pvalue, abs=1e-12)

    def test_a_correcao_nunca_passa_da_diferenca(self):
        """
        `min(0.5, abs(x - E))`: com o observado a menos de meio caso do esperado,
        a estatística é zero e o p é 1 — e não uma diferença negativa ao quadrado.
        """
        estatistica, _, p, yates = qui_quadrado([[10, 10], [10, 11]])
        assert yates
        assert estatistica == pytest.approx(0.0, abs=1e-12)
        assert p == pytest.approx(1.0)


# ── A regra de Cochran ──────────────────────────────────────────────────────


class TestCochran:
    def test_2x2_com_esperada_abaixo_de_5_vai_para_o_fisher(self):
        par = _par(_associar(), "complicacao")
        assert par.cochran.menor_esperada == pytest.approx(3.0)
        assert (par.cochran.abaixo, par.cochran.caselas) == (2, 4)
        assert par.teste == TESTE_FISHER

    def test_2x2_com_tudo_acima_de_5_fica_no_qui_quadrado_com_yates(self):
        assert _par(_associar(), "desfecho").teste == TESTE_YATES

    def test_exatamente_20_por_cento_ainda_e_qui_quadrado(self):
        """Duas de dez caselas abaixo de 5, nenhuma abaixo de 1: o limite atende."""
        tabela = [[5, 14, 16, 7, 8], [3, 16, 14, 9, 8]]
        cochran = regra_de_cochran(_esperadas(tabela))
        assert (cochran.abaixo, cochran.caselas) == (2, 10)
        assert cochran.atende

    def test_uma_esperada_abaixo_de_1_manda_para_o_fisher_mesmo_abaixo_dos_20(self):
        """Duas de doze caselas (16,7%) abaixo de 5, mas uma delas abaixo de 1."""
        tabela = [[1, 10, 10, 10, 10, 19], [0, 10, 10, 10, 10, 20]]
        cochran = regra_de_cochran(_esperadas(tabela))
        assert cochran.abaixo * 100 / cochran.caselas < 20
        assert cochran.menor_esperada < 1
        assert not cochran.atende

    def test_a_escolha_de_cada_par_esta_escrita_na_nota(self):
        texto = _associar().tabela.texto()
        assert "Grupo × Complicação: 2×2, n = 80; menor esperada 3; 2 de 4 caselas" in texto
        assert "→ exato de Fisher." in texto
        assert "→ qui-quadrado com correção de Yates (X² = " in texto


def _esperadas(tabela):
    linhas = [sum(linha) for linha in tabela]
    colunas = [sum(coluna) for coluna in zip(*tabela, strict=True)]
    n = sum(linhas)
    return [[r * c / n for c in colunas] for r in linhas]


# ── A tabela ────────────────────────────────────────────────────────────────


class TestATabela:
    def test_as_cinco_colunas(self):
        assert _associar().tabela.colunas == (
            "variável 1",
            "variável 2",
            "n",
            "teste",
            "p-valor",
        )

    def test_a_tabela_do_banco_de_referencia(self):
        """
        Linha por linha, com cada p conferido contra uma conta independente feita
        sobre as contagens do `bancos.para_associar()`.
        """
        yates = stats.chi2_contingency([[27, 12], [16, 24]], correction=True).pvalue
        fisher_2x2 = stats.fisher_exact([[39, 1], [35, 5]]).pvalue
        fisher_2x4 = _fisher_forca_bruta([[10, 20, 9, 1], [8, 15, 15, 2]])
        pearson = stats.chi2_contingency([[15, 15, 10], [12, 14, 14]]).pvalue

        assert _associar().tabela.linhas == (
            ("Grupo", "Desfecho", "79", TESTE_YATES, valor_p(yates)),
            ("Grupo", "Complicação", "80", TESTE_FISHER, valor_p(fisher_2x2)),
            ("Grupo", "Escolaridade", "80", TESTE_FISHER, valor_p(fisher_2x4)),
            ("Grupo", "Faixa etária", "80", TESTE_QUI_QUADRADO, valor_p(pearson)),
        )

    def test_a_contingencia_esta_na_ordem_do_dicionario(self):
        tabela = contingencia(bancos.para_associar(), GRUPO, DESFECHO)
        assert tabela.categorias_1 == ("Controle", "Intervenção")
        assert tabela.categorias_2 == ("Não", "Sim")
        assert tabela.contagens == ((27, 12), (16, 24))

    def test_a_variavel_da_frente_tambem_sai_pelo_rotulo(self):
        """
        Na forma `desfecho: [grupo]` o código fica na primeira coluna — e lá também
        o `1.0` da leitura vira `Sim`. O p é o mesmo da ordem inversa: o teste é
        simétrico.
        """
        resultado = _associar(pedidos=(("desfecho", "grupo"),))
        par = resultado.pares[0]
        assert par.contingencia.categorias_1 == ("Não", "Sim")
        assert resultado.tabela.linhas[0][:3] == ("Desfecho", "Grupo", "79")
        assert par.p == pytest.approx(_par(_associar(), "desfecho").p, abs=1e-12)

    def test_n_e_quem_respondeu_as_duas(self):
        """A célula vazia de `desfecho` sai do par dele, e só dele."""
        resultado = _associar()
        assert (_par(resultado, "desfecho").validos, _par(resultado, "desfecho").faltantes) == (
            79,
            1,
        )
        assert _par(resultado, "complicacao").validos == 80

    def test_os_faltantes_sao_por_par(self):
        quadro = bancos.para_associar()
        quadro["renda"] = [None] * 40 + [1000.0] * 40
        linhas = (*DICIONARIO, Linha("renda", "Renda", NUMERICA))
        assert _par(_associar(quadro, linhas), "complicacao").validos == 80

    def test_o_agrupamento_do_dicionario_vale_para_o_teste(self):
        """
        `Superior=Superior ou mais|Pós-graduação=Superior ou mais` junta as duas
        linhas antes de contar — e a tabela 2×4 que ia para o Fisher vira uma 2×3
        com tudo acima de 5, que fica no qui-quadrado.
        """
        agrupada = Linha(
            "escolaridade",
            "Escolaridade",
            CATEGORICA,
            ("Fundamental", "Médio", "Superior", "Pós-graduação"),
            rotulos_das_categorias=(
                ("Superior", "Superior ou mais"),
                ("Pós-graduação", "Superior ou mais"),
            ),
        )
        linhas = (GRUPO, DESFECHO, COMPLICACAO, agrupada, FAIXA, SERVICO)
        par = _par(_associar(linhas=linhas), "escolaridade")
        assert par.contingencia.categorias_2 == ("Fundamental", "Médio", "Superior ou mais")
        assert par.contingencia.contagens == ((10, 20, 10), (8, 15, 17))
        assert par.teste == TESTE_QUI_QUADRADO

    def test_a_contingencia_e_a_mesma_do_cruzamento(self):
        """Uma implementação só: as caselas são as combinações que o cruzamento conta."""
        quadro = bancos.para_associar()
        do_cruzamento = cruzar(
            banco_em_memoria(quadro), ficha_em_memoria(), DICIONARIO, (("grupo", "desfecho"),)
        ).pares[0].combinacoes
        tabela = contingencia(quadro, GRUPO, DESFECHO)
        daqui = {
            (a, b): tabela.contagens[i][j]
            for i, a in enumerate(tabela.categorias_1)
            for j, b in enumerate(tabela.categorias_2)
        }
        assert {(a, b): n for a, b, n in do_cruzamento} == daqui

    def test_o_p_nunca_sai_zero(self):
        quadro = pd.DataFrame({"a": ["x"] * 60 + ["y"] * 60, "b": ["s"] * 60 + ["n"] * 60})
        linhas = (Linha("a", "A", CATEGORICA), Linha("b", "B", CATEGORICA))
        tabela = _associar(quadro, linhas, (("a", "b"),)).tabela
        assert tabela.linhas[0][4] == "< 0,001"

    def test_a_tabela_nao_e_de_uma_variavel(self):
        tabela = _associar().tabela
        assert tabela.variavel == ""
        assert tabela.nome == "associacao.csv"
        assert "# variável:" not in tabela.texto()
        assert "não há correção para comparações múltiplas" in tabela.texto()


# ── Quando não há teste ─────────────────────────────────────────────────────


class TestSemTeste:
    def test_uma_categoria_so(self):
        """
        A linha sai assim mesmo, com o motivo no lugar do teste — como a coluna
        `leitura` da normalidade faz com o impedimento.
        """
        resultado = _associar(pedidos=(("grupo", "servico"),))
        assert resultado.tabela.linhas == (
            ("Grupo", "Serviço", "80", "não testado: uma categoria só em Serviço", "—"),
        )
        assert any("critério de inclusão" in aviso for aviso in resultado.avisos)

    def test_ninguem_respondeu_as_duas(self):
        quadro = pd.DataFrame(
            {"a": ["x", "y", None, None], "b": [None, None, "s", "n"]}
        )
        linhas = (Linha("a", "A", CATEGORICA), Linha("b", "B", CATEGORICA))
        resultado = _associar(quadro, linhas, (("a", "b"),))
        assert resultado.tabela.linhas[0][2:] == (
            "0",
            "não testado: nenhum caso com resposta nas duas variáveis",
            "—",
        )

    def test_o_limite_do_calculo_exato_vira_linha_sem_p_e_aviso(self):
        """
        O ponto em que o R para com `FEXACT error`. Aqui a rodada continua, a linha
        diz que o Fisher foi escolhido e não foi calculado, e o aviso diz o que
        fazer.
        """
        resultado = _associar(limite=10)
        linha = resultado.tabela.linhas[2]
        assert linha[3:] == (f"{TESTE_FISHER} (não calculado)", "—")
        aviso = next(a for a in resultado.avisos if "FEXACT" in a)
        assert "10 operações" in aviso
        assert "1=Sim|2=Sim" in aviso
        # Os outros pares não dependem do limite, e a contagem por teste só conta o
        # que foi calculado — senão o resumo do terminal não somaria.
        assert resultado.tabela.linhas[0][4] != "—"
        assert len(resultado.testados) == 3
        assert resultado.quantos(TESTE_FISHER) == 1


# ── As recusas ──────────────────────────────────────────────────────────────


class TestRecusas:
    def test_sem_pares_recusa_e_ensina_as_duas_formas(self):
        with pytest.raises(SemParesError) as erro:
            _associar(pedidos=())
        mensagem = str(erro.value)
        assert "- [sexo, desfecho]" in mensagem
        assert "- desfecho: [sexo, escolaridade, tabagismo]" in mensagem
        assert "grupo, desfecho, complicacao" in mensagem
        assert "435" in mensagem

    def test_numerica_recusa_e_diz_como_marcar(self):
        linhas = (*DICIONARIO, Linha("idade", "Idade", NUMERICA))
        quadro = bancos.para_associar().assign(idade=30)
        with pytest.raises(ParInvalidoError) as erro:
            _associar(quadro, linhas, (("grupo", "idade"),))
        assert "`idade` está marcada `numerica`" in str(erro.value)
        assert "`categorica`" in str(erro.value)

    def test_a_mesma_variavel_duas_vezes(self):
        with pytest.raises(ParInvalidoError, match="a mesma variável duas vezes"):
            _associar(pedidos=(("grupo", "grupo"),))

    def test_nome_fora_do_dicionario(self):
        with pytest.raises(ParInvalidoError, match="`grpo` não está no dicionario.csv"):
            _associar(pedidos=(("grpo", "desfecho"),))

    def test_o_mesmo_par_em_outra_ordem_ou_em_outra_forma(self):
        """
        `[desfecho, grupo]` depois de `grupo: [desfecho, ...]` é o mesmo teste: a
        tabela sairia com duas linhas com o mesmo p.
        """
        with pytest.raises(ParInvalidoError, match=r"repete \[grupo, desfecho\]"):
            _associar(pedidos=(*UMA_CONTRA_VARIAS, ("desfecho", "grupo")))

    def test_ignorar_e_fora_do_banco(self):
        linhas = (
            *DICIONARIO,
            Linha("prontuario", "Prontuário", IGNORAR),
            Linha("antiga", "Antiga", CATEGORICA, no_banco=False),
        )
        with pytest.raises(ParInvalidoError) as erro:
            _associar(linhas=linhas, pedidos=(("grupo", "prontuario"), ("grupo", "antiga")))
        assert "marcada `ignorar`" in str(erro.value)
        assert "no_banco = nao" in str(erro.value)

    def test_todos_os_problemas_de_uma_vez(self):
        with pytest.raises(ParInvalidoError) as erro:
            _associar(
                pedidos=(("grupo", "grupo"), ("grpo", "desfecho"), ("desfecho", "cor"))
            )
        mensagem = str(erro.value)
        assert "3 par(es)" in mensagem
        assert "[grupo, grupo]" in mensagem
        assert "[grpo, desfecho]" in mensagem
        assert "[desfecho, cor]" in mensagem

    def test_categorica_que_nao_existe_no_banco(self):
        """A recusa da descritiva, pela mesma função."""
        linhas = (*DICIONARIO, Linha("estado_civil", "Estado civil", CATEGORICA))
        with pytest.raises(VariavelIncompativelError, match="não existe no banco"):
            _associar(linhas=linhas, pedidos=(("grupo", "estado_civil"),))


# ── A lista da ficha ────────────────────────────────────────────────────────


class TestFicha:
    def test_sem_a_chave_devolve_vazio(self, projeto_vazio):
        assert pares_da_ficha(projeto_vazio) == ()

    def test_as_duas_formas_na_ordem_em_que_foram_escritas(self, projeto_vazio):
        acrescentar_a_ficha(
            projeto_vazio,
            "associacao:\n"
            "  - [sexo, grupo]\n"
            "  - desfecho: [sexo, escolaridade, tabagismo]\n"
            "  - [idade_cat, grupo]\n",
        )
        assert pares_da_ficha(projeto_vazio) == (
            ("sexo", "grupo"),
            ("desfecho", "sexo"),
            ("desfecho", "escolaridade"),
            ("desfecho", "tabagismo"),
            ("idade_cat", "grupo"),
        )

    def test_uma_contra_varias_em_bloco(self, projeto_vazio):
        """A lista depois dos dois-pontos também pode vir um nome por linha."""
        acrescentar_a_ficha(
            projeto_vazio,
            "associacao:\n  - desfecho:\n      - sexo\n      - escolaridade\n",
        )
        assert pares_da_ficha(projeto_vazio) == (
            ("desfecho", "sexo"),
            ("desfecho", "escolaridade"),
        )

    def test_um_nome_so_depois_dos_dois_pontos(self, projeto_vazio):
        acrescentar_a_ficha(projeto_vazio, "associacao:\n  - desfecho: sexo\n")
        assert pares_da_ficha(projeto_vazio) == (("desfecho", "sexo"),)

    def test_lista_vazia_depois_dos_dois_pontos_recusa(self, projeto_vazio):
        acrescentar_a_ficha(projeto_vazio, "associacao:\n  - desfecho: []\n")
        with pytest.raises(ParInvalidoError, match="pelo menos um nome"):
            pares_da_ficha(projeto_vazio)

    def test_tres_nomes_em_colchetes_recusa_e_mostra_a_outra_forma(self, projeto_vazio):
        acrescentar_a_ficha(projeto_vazio, "associacao:\n  - [desfecho, sexo, escolaridade]\n")
        with pytest.raises(ParInvalidoError) as erro:
            pares_da_ficha(projeto_vazio)
        assert "3 nomes; um par tem dois" in str(erro.value)
        assert "`- desfecho: [sexo, escolaridade]`" in str(erro.value)

    def test_texto_solto_recusa_com_as_duas_formas(self, projeto_vazio):
        acrescentar_a_ficha(projeto_vazio, "associacao:\n  - sexo x desfecho\n")
        with pytest.raises(ParInvalidoError) as erro:
            pares_da_ficha(projeto_vazio)
        assert "1º item: `sexo x desfecho`" in str(erro.value)
        assert "- desfecho: [sexo, escolaridade, tabagismo]" in str(erro.value)

    def test_a_chave_que_nao_e_lista(self, projeto_vazio):
        acrescentar_a_ficha(projeto_vazio, "associacao: sexo\n")
        with pytest.raises(ParInvalidoError, match="deveria ser uma lista"):
            pares_da_ficha(projeto_vazio)


# ── O manifesto ─────────────────────────────────────────────────────────────


class TestManifesto:
    def test_um_item_para_a_analise_inteira(self):
        manifesto = montar_manifesto(_associar(), DICIONARIO)
        assert manifesto.analise == ANALISE_ASSOCIACAO
        assert len(manifesto.itens) == 1
        item = manifesto.itens[0]
        assert (item.variavel, item.rotulo) == ("", "Associação")
        assert item.colunas == (
            "grupo",
            "desfecho",
            "complicacao",
            "escolaridade",
            "faixa_etaria",
        )

    def test_os_detalhes_levam_a_contingencia_e_a_escolha(self):
        detalhes = montar_manifesto(_associar(), DICIONARIO).itens[0].detalhes
        desfecho, complicacao = detalhes["pares"][:2]
        assert desfecho["contagens"] == [[27, 12], [16, 24]]
        assert desfecho["teste"] == TESTE_YATES
        assert desfecho["gl"] == 1 and desfecho["estatistica"] > 0
        assert complicacao["cochran"] is False
        assert complicacao["menor_esperada"] == 3.0
        assert (complicacao["estatistica"], complicacao["gl"]) == (None, None)
        assert (detalhes["qui_quadrado_com_yates"], detalhes["fisher"]) == (1, 2)

    def test_o_ambiente_declara_o_scipy_e_nao_o_matplotlib(self):
        ambiente = montar_manifesto(_associar(), DICIONARIO).ambiente
        assert ambiente["scipy"] == __import__("scipy").__version__
        assert ambiente["matplotlib"] is None

    def test_as_regras_dizem_como_o_r_faz(self):
        regras = montar_manifesto(_associar(), DICIONARIO).regras
        assert "Cochran" in regras["escolha_do_teste"]
        assert "sem simulação" in regras["fisher"]
        assert "chisq.test" in regras["qui_quadrado"]

    def test_fora_lista_quem_nao_esta_em_par(self):
        manifesto = montar_manifesto(_associar(), DICIONARIO)
        fora = {entrada["variavel"]: entrada["motivo"] for entrada in manifesto.fora}
        assert set(fora) == {"servico"}
        assert "nenhum par" in fora["servico"]

    def test_a_ordem_padrao_poe_a_associacao_logo_depois_do_cruzamento(self):
        posicao = ORDEM_PADRAO_DAS_ANALISES.index
        assert posicao(ANALISE_ASSOCIACAO) == posicao(ANALISE_CRUZAMENTO) + 1


# ── No disco ────────────────────────────────────────────────────────────────


@pytest.fixture
def projeto_para_associar(projeto_com_rodada):
    """
    Projeto com banco, dicionário, uma rodada de descritiva e a lista na ficha.
    """

    def montar(bloco: str = BLOCO):
        raiz = projeto_com_rodada()
        acrescentar_a_ficha(raiz, bloco)
        return raiz

    return montar


class TestEscrita:
    def test_preparar_nao_toca_no_disco(self, projeto_para_associar):
        raiz = projeto_para_associar()
        antes = len(linhas_do_historico(raiz))
        preparar_associacao(raiz, agora=AGORA)
        assert not (raiz / PASTA_ANALISES / PASTA_ASSOCIACAO).exists()
        assert len(linhas_do_historico(raiz)) == antes

    def test_executar_escreve_a_tabela_e_o_manifesto(self, projeto_para_associar):
        raiz = projeto_para_associar()
        executar_associacao(preparar_associacao(raiz, agora=AGORA))
        pasta = raiz / PASTA_ANALISES / PASTA_ASSOCIACAO

        assert sorted(p.name for p in pasta.iterdir()) == ["associacao.csv", ARQUIVO_MANIFESTO]
        manifesto = ler_manifesto(pasta)
        assert manifesto.analise == ANALISE_ASSOCIACAO
        assert manifesto.itens[0].colunas == ("sexo", "escolaridade")

    def test_escreve_uma_linha_no_historico(self, projeto_para_associar):
        raiz = projeto_para_associar()
        antes = len(linhas_do_historico(raiz))
        executar_associacao(preparar_associacao(raiz, agora=AGORA))
        linhas = linhas_do_historico(raiz)
        assert len(linhas) == antes + 1
        assert f"flatcap associacao {RECORD_ID}" in linhas[-1]
        assert "1 exato de Fisher" in linhas[-1]

    def test_regerar_arquiva_a_rodada_anterior(self, projeto_para_associar):
        raiz = projeto_para_associar()
        executar_associacao(preparar_associacao(raiz, agora=AGORA))
        resultado = executar_associacao(
            preparar_associacao(raiz, agora=AGORA.replace(hour=16))
        )
        arquivada = raiz / PASTA_ANTIGAS / "associacao_2026-09-09_1630"
        assert resultado.arquivado == (raiz / PASTA_ANALISES / PASTA_ASSOCIACAO, arquivada)
        assert (arquivada / ARQUIVO_MANIFESTO).is_file()

    def test_a_falha_no_meio_devolve_a_rodada_anterior(
        self, projeto_para_associar, monkeypatch
    ):
        import flatcap.associacao as modulo

        raiz = projeto_para_associar()
        executar_associacao(preparar_associacao(raiz, agora=AGORA))
        pasta = raiz / PASTA_ANALISES / PASTA_ASSOCIACAO
        antes = {p.name: p.read_bytes() for p in pasta.iterdir()}

        original = modulo.escrever_atomico

        def falha_no_manifesto(caminho, texto):
            if caminho.name == ARQUIVO_MANIFESTO:
                raise OSError("disco cheio")
            original(caminho, texto)

        monkeypatch.setattr(modulo, "escrever_atomico", falha_no_manifesto)
        plano = preparar_associacao(raiz, agora=AGORA.replace(hour=16))
        with pytest.raises(OSError, match="disco cheio"):
            executar_associacao(plano)

        assert {p.name: p.read_bytes() for p in pasta.iterdir()} == antes
        assert not list((raiz / PASTA_ANTIGAS).glob("associacao_*"))

    def test_a_lista_mal_escrita_recusa_antes_de_abrir_o_banco(
        self, projeto_para_associar, monkeypatch
    ):
        raiz = projeto_para_associar("associacao:\n  - sexo e escolaridade\n")

        def nao_abra(*_a, **_k):
            raise AssertionError("o banco foi aberto antes de a lista ser conferida")

        monkeypatch.setattr("flatcap.associacao.abrir", nao_abra)
        with pytest.raises(ParInvalidoError):
            preparar_associacao(raiz, agora=AGORA)

    def test_a_simulacao_e_a_execucao_dao_o_mesmo_arquivo(self, projeto_para_associar):
        """O texto é o arquivo: o que o `--sim` escreve é o que a simulação mostrou."""
        raiz = projeto_para_associar()
        plano = preparar_associacao(raiz, agora=AGORA)
        executar_associacao(plano)
        escrito = (raiz / PASTA_ANALISES / PASTA_ASSOCIACAO / "associacao.csv").read_text(
            encoding="utf-8"
        )
        assert escrito == plano.tabela.texto()


# ── O relatório, que não muda uma linha ─────────────────────────────────────


class TestRelatorio:
    def test_o_relatorio_encontra_a_rodada_sem_nenhum_alerta(self, projeto_para_associar):
        from flatcap.relatorio import preparar_relatorio

        raiz = projeto_para_associar()
        executar_associacao(preparar_associacao(raiz, agora=AGORA))
        relatorio = preparar_relatorio(raiz, agora=AGORA).relatorio

        assert relatorio.analises == ("descritiva", "associacao")
        assert relatorio.alertas == ()
        secao = next(s for s in relatorio.secoes if s.rotulo == "Associação")
        assert secao.tabelas[0].colunas == ("variável 1", "variável 2", "n", "teste", "p-valor")
        assert secao.tabelas[0].linhas[0][:4] == ("sexo", "escolaridade", "24", TESTE_FISHER)

    def test_sem_ficha_mandando_vem_depois_do_cruzamento(self, projeto_para_associar):
        from flatcap.cruzamento import executar_cruzamento, preparar_cruzamento
        from flatcap.relatorio import preparar_relatorio

        raiz = projeto_para_associar(BLOCO + "cruzamento:\n  - [sexo, escolaridade]\n")
        executar_associacao(preparar_associacao(raiz, agora=AGORA))
        executar_cruzamento(preparar_cruzamento(raiz, agora=AGORA))
        relatorio = preparar_relatorio(raiz, agora=AGORA).relatorio
        assert relatorio.analises == ("descritiva", "cruzamento", "associacao")

    def test_a_ficha_manda_na_ordem(self, projeto_para_associar):
        from flatcap.relatorio import preparar_relatorio

        raiz = projeto_para_associar()
        ficha = raiz / ARQUIVO_PROJETO
        ficha.write_text(
            ficha.read_text(encoding="utf-8").replace(
                "analises: []", "analises:\n  - associacao\n  - descritiva"
            ),
            encoding="utf-8",
        )
        executar_associacao(preparar_associacao(raiz, agora=AGORA))
        relatorio = preparar_relatorio(raiz, agora=AGORA).relatorio
        assert relatorio.analises == ("associacao", "descritiva")
        assert relatorio.secoes[0].rotulo == "Associação"
