# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
"""
O parágrafo de metodologia da primeira página.

A promessa do módulo é uma frase só: **o parágrafo cita o que rodou, e nada além.**
Um teste que não rodou e aparece no texto vai parar na seção de métodos de um
artigo, e é o primeiro que o parecerista marca. Por isso o grosso do arquivo monta
manifestos com um teste a mais ou a menos e confere a frase que sai.

Duas guardas valem mais do que todas as outras juntas:

* **os nomes são os das análises.** O `metodologia.py` não importa as análises (elas
  trazem o `pandas`), e escreve como texto os nomes que elas gravam no manifesto. O
  primeiro bloco deste arquivo compara esses textos com as constantes de cada
  análise: um teste novo que entre numa análise sem entrar aqui falha aqui;
* **as rodadas de verdade.** O último bloco roda as análises sobre um banco da casa e
  monta o parágrafo dos manifestos que elas escreveram — e não dos que este arquivo
  imagina que elas escrevem.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime

import pytest

from conftest import acrescentar_a_ficha
from flatcap import analises, associacao, comparacao, correlacao
from flatcap.manifesto import (
    ANALISE_ASSOCIACAO,
    ANALISE_COMPARACAO,
    ANALISE_CORRELACAO,
    ANALISE_CRUZAMENTO,
    ANALISE_DESCRITIVA,
    ANALISE_NORMALIDADE,
    ORDEM_PADRAO_DAS_ANALISES,
    ItemDoManifesto,
    Manifesto,
)
from flatcap.manifesto import ler as ler_manifesto
from flatcap.metodologia import (
    COMPARACOES,
    CORRELACOES,
    DELINEAMENTOS,
    ORDEM,
    TITULO,
    montar_metodologia,
)
from flatcap.projeto import PASTA_ANALISES

QUANDO = datetime(2026, 10, 29, 10, 0)

AMBIENTE = {
    "python": "3.13.18",
    "flatcap": "1.16.0",
    "pandas": "3.0.6",
    "openpyxl": "3.1.5",
    "scipy": "1.18.1",
}


def _manifesto(
    analise: str,
    detalhes: dict | None = None,
    regras: dict | None = None,
    ambiente: dict | None = None,
    tipos: tuple[str, ...] = (),
    flatcap: str = "1.16.0",
) -> Manifesto:
    """
    Um manifesto como as análises o escrevem: as que testam têm um item só, com tudo
    dentro dos `detalhes`; a descritiva tem um item por variável, com o tipo dela.
    """
    if tipos:
        itens = tuple(
            ItemDoManifesto(
                variavel=f"v{posicao}", slug=f"v{posicao}", rotulo=f"V{posicao}",
                tipo=tipo, n=10, faltantes=0,
            )
            for posicao, tipo in enumerate(tipos)
        )
    else:
        itens = (
            ItemDoManifesto(
                variavel="", slug=analise, rotulo=analise.title(), tipo=analise,
                n=10, faltantes=0, detalhes=dict(detalhes or {}),
            ),
        )
    ambiente = dict(AMBIENTE if ambiente is None else ambiente)
    ambiente["flatcap"] = flatcap
    return Manifesto(
        flatcap=flatcap,
        gerado_em=QUANDO,
        projeto={},
        banco={},
        dicionario={},
        ambiente=ambiente,
        regras=dict(regras or {}),
        itens=itens,
        analise=analise,
    )


def _texto(*manifestos: Manifesto) -> str:
    return montar_metodologia(manifestos).texto


def _par(teste: str, **resto) -> dict:
    return {"teste": teste, **resto}


def _linha(teste: str | None, escrito: bool = False) -> dict:
    return {"teste": teste, "escrito_na_ficha": escrito}


# ── Os nomes são os das análises ────────────────────────────────────────────


class TestOsNomesSaoOsDasAnalises:
    def test_os_testes_da_comparacao_sao_os_que_ela_calcula(self):
        """
        Um teste que entre no `_CALCULO` da comparação sem entrar aqui sairia do
        parágrafo em silêncio — e o parágrafo diria menos do que o documento mostra.
        """
        calculados: dict[str, set[str]] = {}
        for delineamento, teste in comparacao._CALCULO:
            calculados.setdefault(delineamento, set()).add(teste)
        assert {d: set(nomes) for d, nomes in COMPARACOES.items()} == calculados

    def test_os_delineamentos_sao_os_da_comparacao(self):
        assert set(DELINEAMENTOS) == {
            comparacao.UMA_AMOSTRA,
            comparacao.DOIS_GRUPOS,
            comparacao.K_GRUPOS,
            comparacao.REPETIDAS,
        }
        assert set(DELINEAMENTOS) == set(COMPARACOES)

    def test_os_metodos_da_correlacao(self):
        assert set(CORRELACOES) == set(correlacao.METODOS.values())

    def test_os_testes_da_associacao(self):
        from flatcap import metodologia

        assert metodologia._QUI_QUADRADOS | {metodologia._FISHER} == {
            associacao.TESTE_QUI_QUADRADO,
            associacao.TESTE_YATES,
            associacao.TESTE_FISHER,
        }
        assert metodologia._YATES == associacao.TESTE_YATES

    def test_toda_analise_do_lote_tem_frase(self):
        """
        A ordem das frases é a de uma seção de métodos, e não a do relatório — mas as
        análises são as mesmas. Uma análise nova no lote sem frase aqui ficaria fora
        do parágrafo.
        """
        assert set(ORDEM) == {registro.nome for registro in analises.REGISTRO}
        assert set(ORDEM) == set(ORDEM_PADRAO_DAS_ANALISES)


def test_o_modulo_nao_carrega_pandas_nem_scipy():
    """
    O `relatorio.py` importa este módulo, e o relatório não abre o banco. Em
    subprocesso porque `sys.modules` é global.
    """
    codigo = (
        "import sys; import flatcap.metodologia; "
        "print(int('pandas' in sys.modules), int('scipy' in sys.modules))"
    )
    saida = subprocess.run(
        [sys.executable, "-c", codigo], capture_output=True, text=True, check=True
    )
    assert saida.stdout.split() == ["0", "0"]


# ── O parágrafo ─────────────────────────────────────────────────────────────


class TestParagrafo:
    def test_sem_rodada_nao_ha_paragrafo_nem_subtitulo(self):
        metodologia = montar_metodologia([])
        assert metodologia.paragrafos == ()
        assert metodologia.titulo == ""
        assert metodologia.texto == ""

    def test_um_paragrafo_so_e_o_subtitulo_separado_dele(self):
        """
        O subtítulo não vai colado na frente do parágrafo: é o `documento.py` quem o
        escreve, no estilo de subtítulo.
        """
        metodologia = montar_metodologia([_manifesto(ANALISE_DESCRITIVA, tipos=("numerica",))])
        assert len(metodologia.paragrafos) == 1
        assert metodologia.titulo == TITULO == "Metodologia Estatística (texto padrão)"
        assert metodologia.paragrafos[0].startswith("As variáveis numéricas")
        assert TITULO not in metodologia.texto

    def test_a_ordem_e_a_de_uma_secao_de_metodos_e_nao_a_da_entrada(self):
        texto = _texto(
            _manifesto(ANALISE_COMPARACAO, {"dois_grupos": [_linha("t de Welch")]}),
            _manifesto(ANALISE_DESCRITIVA, tipos=("categorica",)),
        )
        assert texto.index("foram descritas") < texto.index("t de Welch")

    def test_a_frase_do_python_fecha_o_paragrafo(self):
        texto = _texto(_manifesto(ANALISE_DESCRITIVA, tipos=("categorica",)))
        assert texto.endswith(
            "relativas. As análises foram feitas usando a linguagem Python versão 3.13."
        )

    def test_nenhum_campo_por_preencher_escapa(self):
        """Um `{versao}` mal escrito no bloco editável sairia impresso no documento."""
        texto = _texto(
            _manifesto(ANALISE_DESCRITIVA, tipos=("categorica", "numerica", "data")),
            _manifesto(ANALISE_CRUZAMENTO, tipos=("cruzamento",)),
            _manifesto(ANALISE_ASSOCIACAO, {"pares": [_par("Exato de Fisher")]}),
            _manifesto(ANALISE_NORMALIDADE, {"testadas": 2}, {"graficos": True}),
            _manifesto(ANALISE_CORRELACAO, {"pares": [{"metodo": "Kendall"}]}),
            _manifesto(ANALISE_COMPARACAO, {"repetidas": [_linha("Friedman")]}),
        )
        assert "{" not in texto and "}" not in texto
        assert "  " not in texto


class TestDescritiva:
    def test_um_tipo_so(self):
        assert _texto(_manifesto(ANALISE_DESCRITIVA, tipos=("numerica",))).startswith(
            "As variáveis numéricas foram descritas por média e desvio padrão, "
            "mediana e quartis."
        )

    def test_dois_tipos(self):
        assert _texto(
            _manifesto(ANALISE_DESCRITIVA, tipos=("numerica", "categorica"))
        ).startswith(
            "As variáveis categóricas foram descritas por frequências absolutas "
            "e relativas, e as numéricas, por média e desvio padrão, mediana e quartis."
        )

    def test_os_tres_tipos(self):
        texto = _texto(_manifesto(ANALISE_DESCRITIVA, tipos=("data", "numerica", "categorica")))
        assert (
            "relativas; as numéricas, por média e desvio padrão, mediana e quartis; e as "
            "datas, pelo período e pela distribuição no tempo." in texto
        )

    def test_so_datas(self):
        assert _texto(_manifesto(ANALISE_DESCRITIVA, tipos=("data",))).startswith(
            "As datas foram descritas pelo período e pela distribuição no tempo."
        )

    def test_so_a_descritiva_nao_fala_de_significancia(self):
        texto = _texto(_manifesto(ANALISE_DESCRITIVA, tipos=("categorica",)))
        assert "significância" not in texto


class TestAssociacao:
    def test_so_o_qui_quadrado(self):
        texto = _texto(_manifesto(ANALISE_ASSOCIACAO, {"pares": [_par("Qui-quadrado")]}))
        assert "pelo teste qui-quadrado de Pearson, e a sua intensidade" in texto
        assert "Fisher" not in texto
        assert "Yates" not in texto

    def test_o_yates_so_quando_rodou(self):
        texto = _texto(
            _manifesto(
                ANALISE_ASSOCIACAO,
                {"pares": [_par("Qui-quadrado com correção de Yates"), _par("Qui-quadrado")]},
            )
        )
        assert "qui-quadrado de Pearson, com a correção de Yates nas tabelas 2×2" in texto

    def test_so_o_fisher(self):
        texto = _texto(_manifesto(ANALISE_ASSOCIACAO, {"pares": [_par("Exato de Fisher")]}))
        assert "foi avaliada pelo teste exato de Fisher, e a sua intensidade" in texto
        assert "qui-quadrado" not in texto

    def test_os_dois_dizem_quando_foi_cada_um(self):
        texto = _texto(
            _manifesto(
                ANALISE_ASSOCIACAO,
                {"pares": [_par("Qui-quadrado"), _par("Exato de Fisher")]},
            )
        )
        assert (
            "pelo teste qui-quadrado de Pearson ou, quando alguma frequência esperada era "
            "menor que 1 ou mais de 20% delas eram menores que 5, pelo teste exato de "
            "Fisher" in texto
        )

    def test_par_sem_teste_nao_da_frase_e_nao_vira_aviso(self):
        """
        Um par recusado na rodada (uma variável constante) sai do teste com `teste`
        nulo. Sem par testado, não há o que nomear — e o manifesto diz que foi isso.
        """
        metodologia = montar_metodologia(
            [_manifesto(ANALISE_ASSOCIACAO, {"pares": [_par(None)], "testados": 0})]
        )
        assert metodologia.paragrafos == ()
        assert metodologia.sem_frase == ()


class TestNormalidade:
    def test_com_e_sem_o_qq(self):
        com = _texto(_manifesto(ANALISE_NORMALIDADE, {"testadas": 2}, {"graficos": True}))
        sem = _texto(_manifesto(ANALISE_NORMALIDADE, {"testadas": 2}, {"graficos": False}))
        assert "pelo teste de Shapiro-Wilk e pelo gráfico quantil-quantil." in com
        assert "pelo teste de Shapiro-Wilk." in sem

    def test_sem_variavel_testada_nao_ha_frase(self):
        metodologia = montar_metodologia(
            [
                _manifesto(ANALISE_DESCRITIVA, tipos=("categorica",)),
                _manifesto(ANALISE_NORMALIDADE, {"testadas": 0}, {"alfa": 0.05}),
            ]
        )
        assert "Shapiro-Wilk" not in metodologia.texto
        assert "significância" not in metodologia.texto
        assert metodologia.sem_frase == ()

    def test_o_shapiro_nao_conta_como_comparacao_multipla(self):
        texto = _texto(
            _manifesto(
                ANALISE_NORMALIDADE,
                {"testadas": 12},
                {"alfa": 0.05, "comparacoes_multiplas": "nenhuma correção"},
            )
        )
        assert "Adotou-se o nível de significância de 5%." in texto


class TestCorrelacao:
    def _pares(self, *metodos, escrito=False, tipo="numerica"):
        return {
            "pares": [
                {"metodo": metodo, "escrito_na_ficha": escrito, "tipo_1": tipo,
                 "tipo_2": "numerica"}
                for metodo in metodos
            ]
        }

    def test_um_metodo_so_nao_explica_escolha(self):
        texto = _texto(_manifesto(ANALISE_CORRELACAO, self._pares("Spearman", "Spearman")))
        assert (
            "As correlações foram estimadas pelo coeficiente de Spearman, com intervalos "
            "de confiança de 95%." in texto
        )

    def test_dois_pela_regra_dizem_o_porque(self):
        texto = _texto(_manifesto(ANALISE_CORRELACAO, self._pares("Pearson", "Spearman")))
        assert (
            "pelo coeficiente de Pearson ou, quando o teste de Shapiro-Wilk rejeitou a "
            "normalidade de alguma das variáveis, pelo de Spearman, com intervalos" in texto
        )

    def test_spearman_com_categorica_diz_ordinal(self):
        texto = _texto(
            _manifesto(
                ANALISE_CORRELACAO, self._pares("Pearson", "Spearman", tipo="categorica")
            )
        )
        assert "quando uma das variáveis era ordinal ou o teste de Shapiro-Wilk" in texto

    def test_o_kendall_tem_o_porque_dele(self):
        texto = _texto(_manifesto(ANALISE_CORRELACAO, self._pares("Kendall", "Pearson")))
        assert (
            "pelo coeficiente de Pearson ou, quando alguma das variáveis tinha até 10 "
            "valores distintos, pelo tau-b de Kendall" in texto
        )

    def test_metodo_escrito_na_ficha_nao_e_atribuido_a_regra(self):
        texto = _texto(
            _manifesto(ANALISE_CORRELACAO, self._pares("Pearson", "Kendall", escrito=True))
        )
        assert "pelo coeficiente de Pearson e pelo tau-b de Kendall, com intervalos" in texto
        assert "quando" not in texto


class TestComparacao:
    def test_um_delineamento_e_um_teste(self):
        texto = _texto(
            _manifesto(ANALISE_COMPARACAO, {"dois_grupos": [_linha("t de Welch")]})
        )
        assert "Entre dois grupos, usou-se o teste t de Welch." in texto

    def test_so_os_testes_que_rodaram(self):
        """O ponto do módulo: a ANOVA de Welch está na regra e não rodou."""
        texto = _texto(
            _manifesto(
                ANALISE_COMPARACAO,
                {
                    "dois_grupos": [_linha("t de Welch"), _linha("Mann-Whitney")],
                    "k_grupos": [_linha("Kruskal-Wallis")],
                },
            )
        )
        assert (
            "Entre dois grupos, usaram-se o teste t de Welch e o de Mann-Whitney; e entre "
            "três grupos ou mais, o teste de Kruskal-Wallis." in texto
        )
        assert "ANOVA" not in texto
        assert "uma amostra" not in texto

    def test_os_quatro_delineamentos(self):
        texto = _texto(
            _manifesto(
                ANALISE_COMPARACAO,
                {
                    "uma_amostra": [_linha("t de Student")],
                    "dois_grupos": [_linha("Mann-Whitney")],
                    "k_grupos": [_linha("ANOVA de Welch")],
                    "repetidas": [_linha("ANOVA de medidas repetidas")],
                },
            )
        )
        assert (
            "Na comparação com um valor de referência, usou-se o teste t de Student para "
            "uma amostra; entre dois grupos, o teste de Mann-Whitney; entre três grupos ou "
            "mais, a ANOVA de Welch; e entre medidas repetidas, a ANOVA de medidas "
            "repetidas, com a correção de Greenhouse-Geisser." in texto
        )

    def test_linha_nao_testada_nao_entra(self):
        texto = _texto(
            _manifesto(
                ANALISE_COMPARACAO,
                {"repetidas": [_linha(None), _linha("Friedman")], "testadas": 1},
            )
        )
        assert "Entre medidas repetidas, usou-se o teste de Friedman." in texto

    def test_a_regra_sai_quando_ela_escolheu(self):
        texto = _texto(
            _manifesto(ANALISE_COMPARACAO, {"dois_grupos": [_linha("t de Welch")]})
        )
        assert (
            "O teste paramétrico foi usado quando o de Shapiro-Wilk não rejeitou a "
            "normalidade em nenhum grupo ou medida, e o de postos nos demais casos." in texto
        )

    def test_tudo_escrito_na_ficha_nao_fala_de_regra(self):
        texto = _texto(
            _manifesto(
                ANALISE_COMPARACAO,
                {"dois_grupos": [_linha("t de Student", escrito=True)],
                 "k_grupos": [_linha("ANOVA", escrito=True)]},
            )
        )
        assert "Shapiro-Wilk" not in texto
        assert "a ANOVA de um fator" in texto

    def test_parte_escrita_na_ficha_abre_com_a_excecao(self):
        texto = _texto(
            _manifesto(
                ANALISE_COMPARACAO,
                {"dois_grupos": [_linha("t de Student", escrito=True), _linha("t de Welch")]},
            )
        )
        assert (
            "Exceto quando o teste foi definido de antemão, o teste paramétrico foi usado"
            in texto
        )

    def test_nada_testado_nao_da_frase_e_nao_vira_aviso(self):
        metodologia = montar_metodologia(
            [_manifesto(ANALISE_COMPARACAO, {"dois_grupos": [_linha(None)], "testadas": 0})]
        )
        assert metodologia.paragrafos == ()
        assert metodologia.sem_frase == ()

    def test_nada_testado_nao_fala_de_significancia(self):
        """Sem teste nenhum no parágrafo, não há p a ler contra o alfa."""
        texto = _texto(
            _manifesto(ANALISE_DESCRITIVA, tipos=("numerica",)),
            _manifesto(
                ANALISE_COMPARACAO,
                {"dois_grupos": [_linha(None)], "testadas": 0},
                {"alfa": 0.05, "comparacoes_multiplas": "nenhuma correção"},
            ),
        )
        assert "foram descritas" in texto
        assert "significância" not in texto


class TestSignificancia:
    def test_o_alfa_vem_das_regras(self):
        texto = _texto(
            _manifesto(
                ANALISE_COMPARACAO,
                {"dois_grupos": [_linha("t de Welch")], "testadas": 1},
                {"alfa": 0.01},
            )
        )
        assert "Adotou-se o nível de significância de 1%." in texto

    def test_a_associacao_sem_alfa_usa_o_das_outras(self):
        texto = _texto(
            _manifesto(ANALISE_ASSOCIACAO, {"pares": [_par("Qui-quadrado")], "testados": 1})
        )
        assert "Adotou-se o nível de significância de 5%." in texto

    def test_um_teste_so_nao_fala_de_comparacoes_multiplas(self):
        texto = _texto(
            _manifesto(
                ANALISE_ASSOCIACAO,
                {"pares": [_par("Qui-quadrado")], "testados": 1},
                {"comparacoes_multiplas": "nenhuma correção"},
            )
        )
        assert "comparações múltiplas" not in texto

    def test_mais_de_um_teste_diz_que_nao_houve_correcao(self):
        texto = _texto(
            _manifesto(
                ANALISE_ASSOCIACAO,
                {"pares": [_par("Qui-quadrado")], "testados": 1},
                {"comparacoes_multiplas": "nenhuma correção"},
            ),
            _manifesto(
                ANALISE_COMPARACAO,
                {"dois_grupos": [_linha("t de Welch")], "testadas": 1},
                {"alfa": 0.05, "comparacoes_multiplas": "nenhuma correção"},
            ),
        )
        assert (
            "Adotou-se o nível de significância de 5%, sem correção para comparações "
            "múltiplas." in texto
        )


class TestPython:
    def test_so_a_linguagem_e_a_versao_dela(self):
        """
        A frase é só a do Python: nem o FlatCap, nem o endereço, nem as bibliotecas,
        que estão no manifesto de cada rodada.
        """
        texto = _texto(
            _manifesto(ANALISE_COMPARACAO, {"dois_grupos": [_linha("t de Welch")]})
        )
        assert texto.endswith("As análises foram feitas usando a linguagem Python versão 3.13.")
        for fora in ("FlatCap", "github", "pandas", "SciPy", "3.13.18"):
            assert fora not in texto

    def test_o_ultimo_numero_da_versao_nao_entra(self):
        """O 3.11.15 de uma máquina e o 3.11.9 de outra são o mesmo Python."""
        texto = _texto(
            _manifesto(ANALISE_DESCRITIVA, tipos=("categorica",), ambiente={"python": "3.11.15"}),
            _manifesto(
                ANALISE_COMPARACAO,
                {"dois_grupos": [_linha("t de Welch")]},
                ambiente={"python": "3.11.9"},
            ),
        )
        assert texto.endswith("usando a linguagem Python versão 3.11.")

    def test_rodadas_de_pythons_diferentes_dizem_os_dois(self):
        """
        Não é para esconder: duas versões no parágrafo são o sinal de que uma análise
        rodou noutra máquina, e é melhor que o cliente leia isso do que um número só.
        """
        texto = _texto(
            _manifesto(ANALISE_DESCRITIVA, tipos=("categorica",), ambiente={"python": "3.13.1"}),
            _manifesto(
                ANALISE_COMPARACAO,
                {"dois_grupos": [_linha("t de Welch")]},
                ambiente={"python": "3.11.9"},
            ),
        )
        assert texto.endswith("usando a linguagem Python versões 3.11 e 3.13.")

    def test_sem_o_python_no_ambiente_a_frase_sai_sem_versao(self):
        texto = _texto(_manifesto(ANALISE_DESCRITIVA, tipos=("categorica",), ambiente={}))
        assert texto.endswith("As análises foram feitas usando a linguagem Python.")


class TestSemFrase:
    def test_manifesto_que_nao_registra_o_teste_vira_aviso(self):
        metodologia = montar_metodologia(
            [
                _manifesto(ANALISE_DESCRITIVA, tipos=("categorica",)),
                _manifesto(ANALISE_COMPARACAO, {"dois_grupos": [{"variavel": "imc"}]}),
            ]
        )
        assert metodologia.paragrafos
        assert "Entre dois grupos" not in metodologia.texto
        assert metodologia.sem_frase == (ANALISE_COMPARACAO,)

    def test_analise_que_esta_versao_nao_conhece_vira_aviso_e_nao_quebra(self):
        metodologia = montar_metodologia(
            [
                _manifesto(ANALISE_DESCRITIVA, tipos=("categorica",)),
                _manifesto("regressao", {"modelos": []}),
            ]
        )
        assert metodologia.paragrafos
        assert metodologia.sem_frase == ("regressao",)


# ── As rodadas de verdade ───────────────────────────────────────────────────


class TestComAsRodadasDeVerdade:
    """
    As análises rodam sobre o banco da casa e o parágrafo sai dos manifestos que elas
    escreveram. É a guarda contra o teste acima conferir o formato que ele imagina.
    """

    @pytest.fixture
    def rodadas(self, projeto_com_rodada):
        from flatcap.associacao import executar_associacao, preparar_associacao
        from flatcap.comparacao import executar_comparacao, preparar_comparacao
        from flatcap.correlacao import executar_correlacao, preparar_correlacao

        raiz = projeto_com_rodada()
        acrescentar_a_ficha(
            raiz,
            "associacao:\n  - [sexo, escolaridade]\n"
            "correlacao:\n  - [idade, imc]\n"
            "comparacao:\n  - [imc, sexo]\n  - [idade, 40, t]\n",
        )
        executar_associacao(preparar_associacao(raiz, agora=QUANDO))
        executar_correlacao(preparar_correlacao(raiz, com_graficos=False, agora=QUANDO))
        executar_comparacao(preparar_comparacao(raiz, agora=QUANDO))
        pastas = sorted((raiz / PASTA_ANALISES).iterdir())
        return [ler_manifesto(pasta) for pasta in pastas]

    def test_o_paragrafo_nomeia_o_que_os_manifestos_registraram(self, rodadas):
        metodologia = montar_metodologia(rodadas)
        texto = metodologia.texto
        assert metodologia.sem_frase == ()

        por_analise = {manifesto.analise: manifesto for manifesto in rodadas}
        pares = por_analise[ANALISE_ASSOCIACAO].itens[0].detalhes["pares"]
        assert pares[0]["teste"] == "Exato de Fisher"
        assert "pelo teste exato de Fisher" in texto

        metodo = por_analise[ANALISE_CORRELACAO].itens[0].detalhes["pares"][0]["metodo"]
        assert CORRELACOES[metodo] in texto

        detalhes = por_analise[ANALISE_COMPARACAO].itens[0].detalhes
        assert detalhes["uma_amostra"][0]["teste"] == "t de Student"
        assert "Na comparação com um valor de referência, usou-se o teste t de Student" in texto
        assert COMPARACOES["dois_grupos"][detalhes["dois_grupos"][0]["teste"]] in texto
        # O t da uma amostra foi escrito na ficha; o dos dois grupos, não.
        assert "Exceto quando o teste foi definido de antemão" in texto

    def test_a_versao_e_a_do_python_que_rodou(self, rodadas):
        texto = montar_metodologia(rodadas).texto
        python = ".".join(str(parte) for parte in sys.version_info[:2])
        assert texto.endswith(
            f"As análises foram feitas usando a linguagem Python versão {python}."
        )
