"""
Os testes do `cruzamento.py`.

O miolo é testado pela função pura `cruzar(banco, ficha, linhas, pares)`, como o
`descrever` da Fase 5 e o `avaliar` da normalidade: um `DataFrame`, uma lista de
`Linha` e os pares entram, e as afirmações são sobre a tabela. O caminho do disco —
a ficha com a lista `cruzamento:`, a rodada escrita, o relatório que a encontra —
usa os fixtures do `conftest.py`.

O banco de referência é o `bancos.para_cruzar()`: o exemplo em que o `cruz()` feito
à mão imprimia `1.0` no lugar de `Feminino`, apagava a menor combinação e perdia
quatro pessoas do total.
"""

from __future__ import annotations

import random

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
from flatcap.cruzamento import (
    LIMITE_COMBINACOES,
    ParInvalidoError,
    SemParesError,
    VariavelIncompativelError,
    cruzar,
    executar_cruzamento,
    montar_manifesto,
    pares_da_ficha,
    preparar_cruzamento,
)
from flatcap.descritiva import descrever
from flatcap.dicionario import CATEGORICA, IGNORAR, NUMERICA, Linha
from flatcap.manifesto import (
    ANALISE_CRUZAMENTO,
    ANALISE_DESCRITIVA,
    ARQUIVO_MANIFESTO,
    ORDEM_PADRAO_DAS_ANALISES,
)
from flatcap.manifesto import ler as ler_manifesto
from flatcap.projeto import ARQUIVO_PROJETO, PASTA_ANALISES, PASTA_ANTIGAS, PASTA_CRUZAMENTO

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
DICIONARIO = (SEXO, ESCOLARIDADE)
PAR = (("sexo", "escolaridade"),)

# O que se escreve na ficha para o banco de referência do `conftest`, que tem
# `sexo` e `escolaridade` em texto — as duas marcadas `categorica` pelo perfil.
BLOCO = "cruzamento:\n  - [sexo, escolaridade]\n"


def _cruzar(quadro=None, linhas=DICIONARIO, pares=PAR):
    quadro = bancos.para_cruzar() if quadro is None else quadro
    return cruzar(banco_em_memoria(quadro), ficha_em_memoria(), linhas, pares, AGORA)


def _tabela(quadro=None, linhas=DICIONARIO, pares=PAR):
    return _cruzar(quadro, linhas, pares).pares[0].tabela


def _combinacoes(tabela) -> list[tuple[str, ...]]:
    """As linhas da tabela menos `(sem informação)` e `Total`."""
    return [linha for linha in tabela.linhas if linha[1]]


# ── A tabela ────────────────────────────────────────────────────────────────


class TestATabela:
    def test_a_tabela_do_exemplo(self):
        """
        O exemplo do `cruzamento-o-que-construir.md`, célula por célula. É o
        critério de pronto que não pede opinião: a tabela é esta.
        """
        assert _tabela().linhas == (
            ("Feminino", "Superior", "15", "26,8"),
            ("Feminino", "Médio", "12", "21,4"),
            ("Masculino", "Médio", "11", "19,6"),
            ("Masculino", "Superior", "9", "16,1"),
            ("Feminino", "Fundamental", "6", "10,7"),
            ("Masculino", "Fundamental", "3", "5,4"),
            ("(sem informação)", "", "4", "—"),
            ("Total", "", "60", "100,0"),
        )

    def test_as_colunas_sao_os_rotulos_do_dicionario(self):
        """
        O `nomev1`/`nomev2` do `cruz()`: o nome amigável vem da coluna `rotulo` do
        dicionário, e ninguém mais o passa na chamada.
        """
        assert _tabela().colunas == ("Sexo", "Escolaridade", "n", "% dos válidos")

    def test_a_menor_combinacao_nao_some(self):
        """
        A regressão do `cruz()`: o `drop` da última linha, depois de ordenar,
        apagava a menor combinação — e a tabela deixava de somar o próprio total.
        """
        assert ("Masculino", "Fundamental", "3", "5,4") in _tabela().linhas

    @pytest.mark.parametrize(
        "quadro",
        [
            bancos.para_cruzar(),
            bancos.completo(),
            bancos.com_muitos_faltantes(),
            bancos.completo().head(5),
        ],
        ids=["referencia", "completo", "muitos_faltantes", "cinco_linhas"],
    )
    def test_as_combinacoes_somam_o_total_menos_sem_informacao(self, quadro):
        """
        A invariante que o leitor confere de cabeça, em todo cruzamento. Com os
        rótulos do banco de texto, os códigos não se aplicam — o dicionário sem `=`
        atravessa o mesmo caminho.
        """
        linhas = (
            DICIONARIO
            if quadro["sexo"].dtype.kind == "f"
            else (
                Linha("sexo", "Sexo", CATEGORICA),
                Linha("escolaridade", "Escolaridade", CATEGORICA),
            )
        )
        tabela = _tabela(quadro, linhas)
        por_rotulo = {linha[0]: int(linha[2]) for linha in tabela.linhas if not linha[1]}
        combinacoes = sum(int(linha[2]) for linha in _combinacoes(tabela))

        assert combinacoes + por_rotulo["(sem informação)"] == por_rotulo["Total"]
        assert por_rotulo["Total"] == len(quadro)

    def test_as_contagens_sao_as_do_crosstab(self):
        """
        Conferência independente: o `pd.crosstab` do `cruz()`, sobre as linhas
        completas, dá os mesmos números. O que muda é a apresentação, não a conta.
        """
        quadro = bancos.para_cruzar()
        completas = quadro.dropna()
        cruz = pd.crosstab(completas["sexo"], completas["escolaridade"])
        esperadas = {
            ({1.0: "Feminino", 2.0: "Masculino"}[sexo], escolaridade): int(n)
            for sexo, linha in cruz.iterrows()
            for escolaridade, n in linha.items()
            if n
        }

        obtidas = {(a, b): int(n) for a, b, n, _ in _combinacoes(_tabela(quadro))}
        assert obtidas == esperadas

    def test_sem_faltante_os_percentuais_sao_os_do_cruz(self):
        """
        Com as duas colunas completas, `% dos válidos` é o `FR * 100` do `cruz()`,
        arredondado com uma casa.
        """
        quadro = bancos.para_cruzar().dropna().reset_index(drop=True)
        total = len(quadro)
        for _, _, n, percentual in _combinacoes(_tabela(quadro)):
            assert percentual == f"{100 * int(n) / total:.1f}".replace(".", ",")

    def test_a_tabela_nao_e_de_uma_variavel(self):
        tabela = _tabela()
        assert tabela.variavel == ""
        assert "# variável:" not in tabela.texto()
        assert tabela.nome == "cruz_sexo_x_escolaridade.csv"
        assert tabela.titulo == "Cruzamento — Sexo × Escolaridade"


# ── Quem não respondeu ──────────────────────────────────────────────────────


class TestFaltantes:
    def test_quem_nao_respondeu_uma_das_duas_vai_para_sem_informacao(self):
        par = _cruzar().pares[0]
        assert (par.total, par.validos, par.faltantes) == (60, 56, 4)

    def test_o_percentual_e_sobre_quem_respondeu_as_duas(self):
        tabela = _tabela()
        assert sum(int(linha[2]) for linha in _combinacoes(tabela)) == 56
        assert "denominador 56" in tabela.texto()

    def test_os_faltantes_sao_por_par(self):
        """
        O cruzamento de `sexo` com `escolaridade` não depende de quem respondeu
        `renda` — o oposto do descarte por lista completa.
        """
        quadro = bancos.para_cruzar()
        quadro["renda"] = [None] * 30 + [1000.0] * 30
        linhas = (*DICIONARIO, Linha("renda", "Renda", NUMERICA))
        assert _cruzar(quadro, linhas).pares[0].validos == 56

    def test_ninguem_respondeu_as_duas(self):
        """
        A tabela sai assim mesmo, porque o par foi pedido — uma seção que
        simplesmente não aparecesse seria a falta em que ninguém repara. O `Total`
        não diz `100,0` de um denominador que não existe.
        """
        quadro = pd.DataFrame(
            {"sexo": [1.0, 2.0, None, None], "escolaridade": [None, None, "Médio", "Superior"]}
        )
        resultado = _cruzar(quadro)
        assert resultado.pares[0].tabela.linhas == (
            ("(sem informação)", "", "4", "—"),
            ("Total", "", "4", "—"),
        )
        assert any("nenhum caso" in aviso for aviso in resultado.avisos)


# ── O que se imprime ────────────────────────────────────────────────────────


class TestRotulos:
    def test_codigo_decimal_vira_rotulo_e_nunca_1_0(self):
        """
        A coluna de código com célula vazia chega `float` da leitura do Excel, e o
        `pd.crosstab` imprimia `1.0`. Aqui ela passa pela `serie_de_texto` e pelo
        rótulo do dicionário.
        """
        assert bancos.para_cruzar()["sexo"].dtype.kind == "f"
        categorias = {linha[0] for linha in _combinacoes(_tabela())}
        assert categorias == {"Feminino", "Masculino"}

    def test_sem_rotulo_o_codigo_sai_inteiro(self):
        sem_rotulo = Linha("sexo", "Sexo", CATEGORICA, ("1", "2"))
        tabela = _tabela(linhas=(sem_rotulo, ESCOLARIDADE))
        assert {linha[0] for linha in _combinacoes(tabela)} == {"1", "2"}

    def test_dois_codigos_com_o_mesmo_rotulo_viram_uma_combinacao(self):
        """
        `1=Básico|2=Básico` é o jeito de dizer "some estes dois" — a promessa da
        descritiva, e o cruzamento cumpre a mesma.
        """
        quadro = pd.DataFrame(
            {"sexo": [1, 1, 1, 2, 2, 2], "escolaridade": [1, 2, 3, 1, 2, 3]}
        )
        agrupada = Linha(
            "escolaridade",
            "Escolaridade",
            CATEGORICA,
            ("1", "2", "3"),
            rotulos_das_categorias=(("1", "Básico"), ("2", "Básico"), ("3", "Superior")),
        )
        combinacoes = {(a, b): n for a, b, n, _ in _combinacoes(_tabela(quadro, (SEXO, agrupada)))}
        assert combinacoes == {
            ("Feminino", "Básico"): "2",
            ("Masculino", "Básico"): "2",
            ("Feminino", "Superior"): "1",
            ("Masculino", "Superior"): "1",
        }

    def test_a_categoria_sai_igual_a_da_tabela_de_frequencia(self):
        """
        Uma implementação só: as categorias do cruzamento são, letra por letra, as
        da tabela de frequência da mesma variável na descritiva.
        """
        quadro = bancos.para_cruzar()
        descritiva = descrever(banco_em_memoria(quadro), ficha_em_memoria(), DICIONARIO, AGORA)
        frequencia = next(v for v in descritiva.variaveis if v.variavel == "sexo").tabelas[0]
        da_descritiva = {linha[0] for linha in frequencia.linhas} - {"(sem informação)", "Total"}

        do_cruzamento = {linha[0] for linha in _combinacoes(_tabela(quadro))}
        assert do_cruzamento == da_descritiva


# ── A ordem ─────────────────────────────────────────────────────────────────


class TestOrdem:
    def test_da_mais_frequente_para_a_menos(self):
        contagens = [int(linha[2]) for linha in _combinacoes(_tabela())]
        assert contagens == sorted(contagens, reverse=True)

    def test_o_empate_resolve_pela_ordem_do_dicionario(self):
        """
        Frequência decrescente sozinha deixaria duas combinações de mesmo `n` na
        ordem em que apareceram no banco. Com o desempate, embaralhar as linhas não
        muda o arquivo.
        """
        quadro = pd.DataFrame(
            {
                "sexo": [2, 1, 2, 1] * 3,
                "escolaridade": ["Superior", "Superior", "Fundamental", "Fundamental"] * 3,
            }
        )
        esperada = [
            ("Feminino", "Fundamental"),
            ("Feminino", "Superior"),
            ("Masculino", "Fundamental"),
            ("Masculino", "Superior"),
        ]
        assert [(a, b) for a, b, *_ in _combinacoes(_tabela(quadro))] == esperada

        embaralhado = quadro.sample(frac=1, random_state=random.Random(3).randint(0, 999))
        assert _tabela(embaralhado.reset_index(drop=True)).texto() == _tabela(quadro).texto()

    def test_combinacao_sem_nenhum_caso_nao_aparece(self):
        """
        Uma categoria declarada e sem nenhum caso aparece com `n = 0` na tabela de
        frequência; no cruzamento, a combinação dela não aparece — são dez linhas
        de zero numa tabela de três variáveis de quatro categorias.
        """
        com_pos = Linha(
            "escolaridade",
            "Escolaridade",
            CATEGORICA,
            ("Fundamental", "Médio", "Superior", "Pós-graduação"),
        )
        rotulos = {linha[1] for linha in _combinacoes(_tabela(linhas=(SEXO, com_pos)))}
        assert "Pós-graduação" not in rotulos

    def test_muitas_combinacoes_saem_inteiras_e_com_aviso(self):
        lados = LIMITE_COMBINACOES // 5 + 2
        quadro = pd.DataFrame(
            {
                "a": [f"a{i}" for i in range(lados) for _ in range(6)],
                "b": [f"b{j}" for _ in range(lados) for j in range(6)],
            }
        )
        linhas = (Linha("a", "A", CATEGORICA), Linha("b", "B", CATEGORICA))
        resultado = _cruzar(quadro, linhas, (("a", "b"),))
        assert len(resultado.pares[0].combinacoes) == lados * 6 > LIMITE_COMBINACOES
        assert any("combinações" in aviso for aviso in resultado.avisos)


# ── As recusas ──────────────────────────────────────────────────────────────


class TestRecusas:
    def test_sem_pares_recusa_e_ensina_a_lista(self):
        with pytest.raises(SemParesError) as erro:
            _cruzar(pares=())
        mensagem = str(erro.value)
        assert "- [sexo, escolaridade]" in mensagem
        # A mensagem diz quais categóricas existem, para a lista sair certa.
        assert "sexo, escolaridade." in mensagem
        assert "435" in mensagem

    def test_numerica_recusa_e_diz_como_marcar(self):
        linhas = (*DICIONARIO, Linha("idade", "Idade", NUMERICA))
        quadro = bancos.para_cruzar().assign(idade=30)
        with pytest.raises(ParInvalidoError) as erro:
            _cruzar(quadro, linhas, (("sexo", "idade"),))
        assert "`idade` está marcada `numerica`" in str(erro.value)
        assert "`categorica`" in str(erro.value)

    def test_a_mesma_variavel_duas_vezes(self):
        with pytest.raises(ParInvalidoError, match="a mesma variável duas vezes"):
            _cruzar(pares=(("sexo", "sexo"),))

    def test_nome_fora_do_dicionario(self):
        with pytest.raises(ParInvalidoError, match="`sxo` não está no dicionario.csv"):
            _cruzar(pares=(("sxo", "escolaridade"),))

    def test_o_mesmo_par_na_ordem_inversa(self):
        """
        `[escolaridade, sexo]` troca só qual coluna vem primeiro: seriam duas
        seções com os mesmos números no documento do cliente.
        """
        with pytest.raises(ParInvalidoError, match="o mesmo par do 1º item"):
            _cruzar(pares=(("sexo", "escolaridade"), ("escolaridade", "sexo")))

    def test_ignorar_e_fora_do_banco(self):
        linhas = (
            *DICIONARIO,
            Linha("prontuario", "Prontuário", IGNORAR),
            Linha("antiga", "Antiga", CATEGORICA, no_banco=False),
        )
        with pytest.raises(ParInvalidoError) as erro:
            _cruzar(linhas=linhas, pares=(("sexo", "prontuario"), ("sexo", "antiga")))
        assert "marcada `ignorar`" in str(erro.value)
        assert "no_banco = nao" in str(erro.value)

    def test_todos_os_problemas_de_uma_vez(self):
        """
        Descobrir o segundo depois de corrigir o primeiro é o jeito mais lento de
        arrumar uma lista — a regra da Fase 5 para as colunas incompatíveis.
        """
        with pytest.raises(ParInvalidoError) as erro:
            _cruzar(
                pares=(("sexo", "sexo"), ("sxo", "escolaridade"), ("escolaridade", "cor"))
            )
        mensagem = str(erro.value)
        assert "3 par(es)" in mensagem
        assert "[sexo, sexo]" in mensagem
        assert "[sxo, escolaridade]" in mensagem
        assert "[escolaridade, cor]" in mensagem

    def test_categorica_que_nao_existe_no_banco(self):
        """
        A recusa da descritiva, pela mesma função: o dicionário declara, o banco
        não tem.
        """
        linhas = (*DICIONARIO, Linha("estado_civil", "Estado civil", CATEGORICA))
        with pytest.raises(VariavelIncompativelError, match="não existe no banco"):
            _cruzar(linhas=linhas, pares=(("sexo", "estado_civil"),))


# ── A lista da ficha ────────────────────────────────────────────────────────


class TestFicha:
    def test_sem_a_chave_devolve_vazio(self, projeto_vazio):
        """
        Quem recusa a ausência é o `cruzar`, que tem o dicionário na mão para
        escrever na mensagem quais categóricas existem.
        """
        assert pares_da_ficha(projeto_vazio) == ()

    def test_le_os_pares_como_se_digita(self, projeto_vazio):
        acrescentar_a_ficha(
            projeto_vazio, "cruzamento:\n  - [sexo, escolaridade]\n  - [grupo, desfecho]\n"
        )
        assert pares_da_ficha(projeto_vazio) == (
            ("sexo", "escolaridade"),
            ("grupo", "desfecho"),
        )

    def test_o_recuo_do_traco_nao_importa(self, projeto_vazio):
        acrescentar_a_ficha(projeto_vazio, "cruzamento:\n- [sexo, escolaridade]\n")
        assert pares_da_ficha(projeto_vazio) == (("sexo", "escolaridade"),)

    def test_par_sem_colchetes_recusa_com_a_forma_certa(self, projeto_vazio):
        acrescentar_a_ficha(projeto_vazio, "cruzamento:\n  - sexo x escolaridade\n")
        with pytest.raises(ParInvalidoError) as erro:
            pares_da_ficha(projeto_vazio)
        assert "1º item: `sexo x escolaridade`" in str(erro.value)
        assert "- [sexo, escolaridade]" in str(erro.value)

    def test_tres_nomes_recusa(self, projeto_vazio):
        acrescentar_a_ficha(projeto_vazio, "cruzamento:\n  - [sexo, escolaridade, renda]\n")
        with pytest.raises(ParInvalidoError, match="3 nomes; um par tem dois"):
            pares_da_ficha(projeto_vazio)

    def test_a_chave_que_nao_e_lista(self, projeto_vazio):
        acrescentar_a_ficha(projeto_vazio, "cruzamento: sexo\n")
        with pytest.raises(ParInvalidoError, match="deveria ser uma lista de pares"):
            pares_da_ficha(projeto_vazio)


# ── O manifesto ─────────────────────────────────────────────────────────────


class TestManifesto:
    def test_um_item_por_par(self):
        """
        A terceira forma de item: na descritiva é uma variável, na normalidade é a
        análise inteira, aqui é um par — e o `colunas` diz quais duas.
        """
        linhas = (*DICIONARIO, Linha("grupo", "Grupo", CATEGORICA))
        quadro = bancos.para_cruzar().assign(grupo=["A", "B"] * 30)
        resultado = _cruzar(quadro, linhas, (("sexo", "escolaridade"), ("grupo", "sexo")))
        manifesto = montar_manifesto(resultado, linhas)

        assert manifesto.analise == ANALISE_CRUZAMENTO
        assert [item.rotulo for item in manifesto.itens] == [
            "Sexo × Escolaridade",
            "Grupo × Sexo",
        ]
        assert [item.colunas for item in manifesto.itens] == [
            ("sexo", "escolaridade"),
            ("grupo", "sexo"),
        ]
        assert all(item.variavel == "" for item in manifesto.itens)
        assert manifesto.colunas_usadas == ("sexo", "escolaridade", "grupo")

    def test_n_e_faltantes_do_item_sao_os_da_tabela(self):
        item = montar_manifesto(_cruzar(), DICIONARIO).itens[0]
        assert (item.n, item.faltantes) == (60, 4)
        assert item.detalhes["validos"] == 56

    def test_o_ambiente_nao_declara_o_que_nao_usou(self):
        """
        Cada rodada declara o que ela usou: sem gráfico e sem teste, nem
        `matplotlib` nem `scipy` — anunciá-los seria dizer que um destes números
        passou por eles.
        """
        ambiente = montar_manifesto(_cruzar(), DICIONARIO).ambiente
        assert "scipy" not in ambiente
        assert ambiente["matplotlib"] is None
        assert ambiente["pandas"] == pd.__version__

    def test_fora_lista_quem_nao_esta_em_par(self):
        linhas = (*DICIONARIO, Linha("idade", "Idade", NUMERICA))
        quadro = bancos.para_cruzar().assign(idade=30)
        manifesto = montar_manifesto(_cruzar(quadro, linhas), linhas)
        fora = {entrada["variavel"]: entrada["motivo"] for entrada in manifesto.fora}
        assert set(fora) == {"idade"}
        assert "nenhum par" in fora["idade"]

    def test_a_ordem_padrao_poe_o_cruzamento_logo_depois_da_descritiva(self):
        """
        Sem teste, o cruzamento ainda é descrição — e em ordem alfabética ele
        viria antes da descritiva.
        """
        posicao = ORDEM_PADRAO_DAS_ANALISES.index
        assert posicao(ANALISE_CRUZAMENTO) == posicao(ANALISE_DESCRITIVA) + 1


# ── No disco ────────────────────────────────────────────────────────────────


@pytest.fixture
def projeto_para_cruzar(projeto_com_rodada):
    """
    Projeto com banco, dicionário, uma rodada de descritiva e a lista na ficha.
    """

    def montar(bloco: str = BLOCO):
        raiz = projeto_com_rodada()
        acrescentar_a_ficha(raiz, bloco)
        return raiz

    return montar


class TestEscrita:
    def test_preparar_nao_toca_no_disco(self, projeto_para_cruzar):
        raiz = projeto_para_cruzar()
        antes = len(linhas_do_historico(raiz))
        preparar_cruzamento(raiz, agora=AGORA)
        assert not (raiz / PASTA_ANALISES / PASTA_CRUZAMENTO).exists()
        assert len(linhas_do_historico(raiz)) == antes

    def test_executar_escreve_as_tabelas_e_o_manifesto(self, projeto_para_cruzar):
        raiz = projeto_para_cruzar()
        executar_cruzamento(preparar_cruzamento(raiz, agora=AGORA))
        pasta = raiz / PASTA_ANALISES / PASTA_CRUZAMENTO

        assert sorted(p.name for p in pasta.iterdir()) == [
            "cruz_sexo_x_escolaridade.csv",
            ARQUIVO_MANIFESTO,
        ]
        manifesto = ler_manifesto(pasta)
        assert manifesto.analise == ANALISE_CRUZAMENTO
        assert manifesto.itens[0].colunas == ("sexo", "escolaridade")

    def test_escreve_uma_linha_no_historico(self, projeto_para_cruzar):
        raiz = projeto_para_cruzar()
        antes = len(linhas_do_historico(raiz))
        executar_cruzamento(preparar_cruzamento(raiz, agora=AGORA))
        linhas = linhas_do_historico(raiz)
        assert len(linhas) == antes + 1
        assert f"flatcap cruzamento {RECORD_ID}" in linhas[-1]

    def test_regerar_arquiva_a_rodada_anterior(self, projeto_para_cruzar):
        raiz = projeto_para_cruzar()
        executar_cruzamento(preparar_cruzamento(raiz, agora=AGORA))
        resultado = executar_cruzamento(
            preparar_cruzamento(raiz, agora=AGORA.replace(hour=16))
        )
        # O nome leva a hora da rodada nova, que é quando o arquivamento acontece —
        # a mesma regra da descritiva e da normalidade.
        arquivada = raiz / PASTA_ANTIGAS / "cruzamento_2026-09-09_1630"
        assert resultado.arquivado == (raiz / PASTA_ANALISES / PASTA_CRUZAMENTO, arquivada)
        assert (arquivada / ARQUIVO_MANIFESTO).is_file()

    def test_a_falha_no_meio_devolve_a_rodada_anterior(self, projeto_para_cruzar, monkeypatch):
        """
        Uma falha na escrita do manifesto — o último arquivo — desfaz tudo, e a
        rodada anterior volta inteira para o lugar, byte a byte.
        """
        import flatcap.cruzamento as modulo

        raiz = projeto_para_cruzar()
        executar_cruzamento(preparar_cruzamento(raiz, agora=AGORA))
        pasta = raiz / PASTA_ANALISES / PASTA_CRUZAMENTO
        antes = {p.name: p.read_bytes() for p in pasta.iterdir()}

        original = modulo.escrever_atomico

        def falha_no_manifesto(caminho, texto):
            if caminho.name == ARQUIVO_MANIFESTO:
                raise OSError("disco cheio")
            original(caminho, texto)

        monkeypatch.setattr(modulo, "escrever_atomico", falha_no_manifesto)
        plano = preparar_cruzamento(raiz, agora=AGORA.replace(hour=16))
        with pytest.raises(OSError, match="disco cheio"):
            executar_cruzamento(plano)

        assert {p.name: p.read_bytes() for p in pasta.iterdir()} == antes
        assert not list((raiz / PASTA_ANTIGAS).glob("cruzamento_*"))

    def test_a_lista_mal_escrita_recusa_antes_de_abrir_o_banco(
        self, projeto_para_cruzar, monkeypatch
    ):
        """
        O engano mais provável deste comando não pode custar a releitura do
        `sha256` de um banco grande.
        """
        raiz = projeto_para_cruzar("cruzamento:\n  - sexo e escolaridade\n")

        def nao_abra(*_a, **_k):
            raise AssertionError("o banco foi aberto antes de a lista ser conferida")

        monkeypatch.setattr("flatcap.cruzamento.abrir", nao_abra)
        with pytest.raises(ParInvalidoError):
            preparar_cruzamento(raiz, agora=AGORA)


# ── O relatório, que não muda uma linha ─────────────────────────────────────


class TestRelatorio:
    def test_o_relatorio_encontra_a_rodada_sem_nenhum_alerta(self, projeto_para_cruzar):
        """
        A promessa da 1.3.1 cobrada pela primeira vez: a terceira análise entra no
        documento sem que o `relatorio.py` saiba que ela existe. E sem alerta — é o
        `colunas` do item que impede o «`` saiu da descritiva» que um par causaria
        na conferência do dicionário.
        """
        from flatcap.relatorio import preparar_relatorio

        raiz = projeto_para_cruzar()
        executar_cruzamento(preparar_cruzamento(raiz, agora=AGORA))
        relatorio = preparar_relatorio(raiz, agora=AGORA).relatorio

        assert relatorio.analises == ("descritiva", "cruzamento")
        assert relatorio.alertas == ()
        secao = next(s for s in relatorio.secoes if s.rotulo == "sexo × escolaridade")
        assert secao.tabelas[0].colunas == ("sexo", "escolaridade", "n", "% dos válidos")
        assert secao.tabelas[0].linhas[-1][0] == "Total"

    def test_a_ficha_manda_na_ordem(self, projeto_para_cruzar):
        from flatcap.relatorio import preparar_relatorio

        raiz = projeto_para_cruzar()
        ficha = raiz / ARQUIVO_PROJETO
        ficha.write_text(
            ficha.read_text(encoding="utf-8").replace(
                "analises: []", "analises:\n  - cruzamento\n  - descritiva"
            ),
            encoding="utf-8",
        )
        executar_cruzamento(preparar_cruzamento(raiz, agora=AGORA))
        relatorio = preparar_relatorio(raiz, agora=AGORA).relatorio
        assert relatorio.analises == ("cruzamento", "descritiva")
        assert relatorio.secoes[0].rotulo == "sexo × escolaridade"
