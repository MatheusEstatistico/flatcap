# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
"""
A descritiva — Fase 5.

O módulo obedece ao `dicionario.csv` e a mais nada. Não há nenhuma heurística
aqui dentro: o teste que prova isso não é um teste de tipo, é o teste de que
mudar uma célula do dicionário muda a saída, e nada mais muda.

Os dois eixos deste arquivo:

**As recusas.** Elas são o conteúdo da decisão da fase, não uma borda. Uma
descritiva com metade das variáveis sai perfeitamente formatada, e nada nela
denuncia a metade que ficou de fora.

**Os denominadores.** É a razão de a fase existir do jeito que existe. Toda
tabela precisa dizer sobre quantos casos ela fala, e as duas colunas de
percentual precisam ser distinguíveis sem consultar ninguém.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

import bancos
from conftest import AGORA, banco_em_memoria, ficha_em_memoria
from flatcap.descritiva import (
    FAIXAS_DICIONARIO,
    FAIXAS_QUARTIS,
    LIMITE_BARRAS,
    SEMENTE,
    DicionarioAusenteError,
    DicionarioDesatualizadoError,
    NadaParaAnalisarError,
    VariavelIncompativelError,
    descrever,
    executar_descritiva,
    montar_manifesto,
    preparar_descritiva,
)
from flatcap.dicionario import CATEGORICA, DATA, IGNORAR, NUMERICA, Linha
from flatcap.manifesto import ARQUIVO_MANIFESTO
from flatcap.projeto import PASTA_ANALISES, PASTA_ANTIGAS, PASTA_DESCRITIVA


@pytest.fixture
def descrita():
    def executar(quadro, linhas):
        return descrever(banco_em_memoria(quadro), ficha_em_memoria(), linhas, AGORA)

    return executar


def _tabela(descritiva, nome: str):
    return next(t for t in descritiva.tabelas if t.nome == nome)


def _linhas_da_tabela(tabela) -> dict[str, tuple[str, ...]]:
    return {linha[0]: linha for linha in tabela.linhas}


# ── As recusas ──────────────────────────────────────────────────────────────


class TestRecusas:
    def test_numerica_que_chegou_como_texto(self, descrita):
        """
        A decisão central da fase. Converter em silêncio é como uma média sai de
        80% dos casos sem que nada na tabela diga que os outros 20% não entraram.
        """
        linhas = (Linha(variavel="imc", tipo=NUMERICA),)
        with pytest.raises(VariavelIncompativelError) as erro:
            descrita(bancos.com_virgula_decimal(), linhas)
        assert "chegou como texto" in str(erro.value)

    def test_a_mensagem_lista_todas_as_colunas_de_uma_vez(self, descrita):
        """
        Descobrir a segunda depois de corrigir a primeira é o jeito mais lento
        possível de arrumar um banco.
        """
        quadro = bancos.com_virgula_decimal()
        quadro["idade"] = [f"{v}" for v in quadro["idade"]]
        linhas = (Linha(variavel="imc", tipo=NUMERICA), Linha(variavel="idade", tipo=NUMERICA))
        with pytest.raises(VariavelIncompativelError) as erro:
            descrita(quadro, linhas)
        assert "imc" in str(erro.value)
        assert "idade" in str(erro.value)

    def test_a_mensagem_escreve_as_tres_saidas_em_ordem(self, descrita):
        """
        A recusa que só recusa manda o usuário adivinhar, e o que ele vai fazer é
        marcar tudo como texto.
        """
        with pytest.raises(VariavelIncompativelError) as erro:
            descrita(bancos.com_virgula_decimal(), (Linha(variavel="imc", tipo=NUMERICA),))
        texto = str(erro.value)
        assert "dados adicionar" in texto
        assert "`categorica`" in texto
        assert "`ignorar`" in texto

    def test_os_exemplos_sao_valores_distintos_e_nao_os_primeiros(self, descrita):
        """
        Numa coluna com dois formatos de data misturados, os cinco primeiros são
        cinco vezes o mesmo formato — e o exemplo existe para mostrar a mistura.
        """
        with pytest.raises(VariavelIncompativelError) as erro:
            descrita(bancos.com_datas_misturadas(), (Linha(variavel="data_coleta", tipo=DATA),))
        texto = str(erro.value)
        assert "/" in texto and "-" in texto

    def test_coluna_do_banco_que_o_dicionario_desconhece(self, projeto_com_banco):
        raiz = projeto_com_banco()
        (raiz / "dicionario.csv").write_text(
            "\ufeffvariavel;rotulo;tipo;categorias_ordem;faixas;no_banco\n"
            "sexo;Sexo;categorica;;;sim\n",
            encoding="utf-8",
            newline="\n",
        )
        with pytest.raises(DicionarioDesatualizadoError) as erro:
            preparar_descritiva(raiz)
        assert "flatcap perfil --sim" in str(erro.value)

    def test_projeto_sem_dicionario(self, projeto_com_banco):
        with pytest.raises(DicionarioAusenteError) as erro:
            preparar_descritiva(projeto_com_banco())
        assert "flatcap perfil" in str(erro.value)

    def test_nada_a_analisar(self, descrita):
        linhas = tuple(
            Linha(variavel=nome, tipo=IGNORAR) for nome in bancos.completo().columns
        )
        with pytest.raises(NadaParaAnalisarError) as erro:
            descrita(bancos.completo(), linhas)
        assert "reveja a coluna `tipo`" in str(erro.value).lower()


class TestOQueNaoERecusa:
    """
    Variável `ignorar`, variável fora do banco e coluna sem valor nenhum não
    interrompem nada — elas viram registro. "Não está no relatório" e "ninguém
    reparou que ela existia" são coisas diferentes.
    """

    def test_ignorar_sai_na_lista_fora_com_o_motivo(self, descrita):
        linhas = (
            Linha(variavel="sexo", tipo=CATEGORICA),
            Linha(variavel="id_paciente", tipo=IGNORAR),
        )
        descritiva = descrita(bancos.completo(), linhas)
        fora = {f.variavel: f.motivo for f in descritiva.fora}
        assert "ignorar" in fora["id_paciente"]

    def test_no_banco_nao_sai_na_lista_fora(self, descrita):
        linhas = (
            Linha(variavel="sexo", tipo=CATEGORICA),
            Linha(variavel="peso_anterior", tipo=NUMERICA, no_banco=False),
        )
        descritiva = descrita(bancos.completo(), linhas)
        assert any(f.variavel == "peso_anterior" for f in descritiva.fora)

    def test_coluna_sem_valor_nenhum(self, descrita):
        linhas = (
            Linha(variavel="sexo", tipo=CATEGORICA),
            Linha(variavel="peso_anterior", tipo=NUMERICA),
        )
        descritiva = descrita(bancos.com_coluna_vazia(), linhas)
        fora = {f.variavel: f.motivo for f in descritiva.fora}
        assert "sem nenhum valor" in fora["peso_anterior"]


# ── Categóricas ─────────────────────────────────────────────────────────────


class TestCategorica:
    def test_a_ordem_do_dicionario_manda(self, descrita):
        """
        É a decisão da reunião, e é o que faz duas tabelas do mesmo estudo
        apresentarem "Feminino" sempre antes de "Masculino".
        """
        linhas = (
            Linha(variavel="sexo", tipo=CATEGORICA, categorias_ordem=("Masculino", "Feminino")),
        )
        tabela = _tabela(descrita(bancos.completo(), linhas), "freq_sexo.csv")
        assert [linha[0] for linha in tabela.linhas[:2]] == ["Masculino", "Feminino"]

    def test_sem_ordem_declarada_e_frequencia_decrescente(self, descrita):
        quadro = bancos.completo()
        quadro["grupo"] = ["B"] * 12 + ["A"] * 8 + ["C"] * 4
        tabela = _tabela(
            descrita(quadro, (Linha(variavel="grupo", tipo=CATEGORICA),)), "freq_grupo.csv"
        )
        assert [linha[0] for linha in tabela.linhas[:3]] == ["B", "A", "C"]

    def test_categoria_declarada_e_ausente_do_banco_sai_com_n_zero(self, descrita):
        """
        A tabela do relatório precisa ser a mesma antes e depois de o cliente
        mandar a versão em que aquela categoria não apareceu.
        """
        linhas = (
            Linha(
                variavel="sexo",
                tipo=CATEGORICA,
                categorias_ordem=("Feminino", "Masculino", "Intersexo"),
            ),
        )
        descritiva = descrita(bancos.completo(), linhas)
        corpo = _linhas_da_tabela(_tabela(descritiva, "freq_sexo.csv"))
        assert corpo["Intersexo"][1] == "0"
        assert any("sem nenhum caso" in aviso for aviso in descritiva.avisos)

    def test_valor_do_banco_nao_declarado_entra_no_fim_com_aviso(self, descrita):
        """
        É assim que um `"Sim "` com espaço se denuncia sozinho.
        """
        linhas = (Linha(variavel="sexo", tipo=CATEGORICA, categorias_ordem=("Feminino",)),)
        descritiva = descrita(bancos.completo(), linhas)
        corpo = _linhas_da_tabela(_tabela(descritiva, "freq_sexo.csv"))
        assert "Masculino" in corpo
        assert any("fora da ordem declarada" in aviso for aviso in descritiva.avisos)

    def test_os_dois_denominadores_estao_escritos_no_arquivo(self, descrita):
        """
        O que o roteiro pede: quando o cliente lê "45%", ele precisa saber se o
        denominador incluiu os casos sem resposta.
        """
        quadro = bancos.com_muitos_faltantes(0.25)
        tabela = _tabela(
            descrita(quadro, (Linha(variavel="escolaridade", tipo=CATEGORICA),)),
            "freq_escolaridade.csv",
        )
        assert "% dos válidos" in tabela.colunas
        assert "% do total" in tabela.colunas
        notas = " ".join(tabela.notas)
        assert "denominador 18" in notas and "denominador 24" in notas

    def test_a_linha_de_faltantes_nao_entra_no_denominador_dos_validos(self, descrita):
        quadro = bancos.com_muitos_faltantes(0.25)
        corpo = _linhas_da_tabela(
            _tabela(
                descrita(quadro, (Linha(variavel="escolaridade", tipo=CATEGORICA),)),
                "freq_escolaridade.csv",
            )
        )
        assert corpo["(sem informação)"][2] == "—"
        validos = [
            float(linha[2].replace(",", "."))
            for rotulo, linha in corpo.items()
            if rotulo not in {"(sem informação)", "Total"}
        ]
        assert sum(validos) == pytest.approx(100.0, abs=0.2)

    def test_codigo_numerico_vira_texto_sem_o_ponto_zero(self, descrita):
        """
        `1` e `2` num `astype(str)` cru virariam `"1.0"` e `"2.0"` — e código
        como categórica é justamente o que a Fase 4 sugere para essas colunas.
        """
        quadro = bancos.com_codigos_numericos()
        corpo = _linhas_da_tabela(
            _tabela(
                descrita(quadro, (Linha(variavel="sexo_cod", tipo=CATEGORICA),)),
                "freq_sexo_cod.csv",
            )
        )
        assert "1" in corpo and "1.0" not in corpo


# ── Numéricas ───────────────────────────────────────────────────────────────


class TestNumerica:
    def test_o_resumo_traz_as_nove_linhas(self, descrita):
        """
        Média, desvio e mediana estão aqui para impedir a Fase 6 de reabrir o
        banco — que é a porta pela qual o relatório passa a discordar da tabela.
        """
        tabela = _tabela(
            descrita(bancos.completo(), (Linha(variavel="idade", tipo=NUMERICA),)),
            "resumo_idade.csv",
        )
        rotulos = [linha[0] for linha in tabela.linhas]
        assert rotulos == [
            "n válidos", "faltantes", "mínimo", "q1", "mediana", "q3",
            "máximo", "média", "desvio padrão",
        ]

    def test_sem_faixas_no_dicionario_usa_os_quartis(self, descrita):
        descritiva = descrita(bancos.completo(), (Linha(variavel="idade", tipo=NUMERICA),))
        assert descritiva.variaveis[0].detalhes["faixas"]["origem"] == FAIXAS_QUARTIS

    def test_com_faixas_no_dicionario_usa_os_cortes(self, descrita):
        linhas = (Linha(variavel="idade", tipo=NUMERICA, faixas=("0", "18", "30", "60", "120")),)
        descritiva = descrita(bancos.completo(), linhas)
        detalhes = descritiva.variaveis[0].detalhes["faixas"]
        assert detalhes["origem"] == FAIXAS_DICIONARIO
        assert detalhes["cortes"] == [0.0, 18.0, 30.0, 60.0, 120.0]

    def test_o_maximo_nao_cai_fora_da_ultima_faixa(self, descrita):
        """
        A contagem é feita à mão, e não com `pd.cut`, por causa disto: o
        `pd.cut` fecha todos os intervalos do mesmo lado e o máximo cairia fora
        do último. Um caso perdido em silêncio no extremo é o tipo de erro que
        ninguém confere.
        """
        quadro = bancos.completo()
        linhas = (Linha(variavel="idade", tipo=NUMERICA, faixas=("23", "40", "62")),)
        corpo = _linhas_da_tabela(_tabela(descrita(quadro, linhas), "faixas_idade.csv"))
        somados = sum(
            int(linha[3]) for rotulo, linha in corpo.items()
            if rotulo not in {"(sem informação)", "Total"}
        )
        assert somados == len(quadro)

    def test_caso_fora_das_faixas_sai_em_linha_propria_e_avisa(self, descrita):
        linhas = (Linha(variavel="idade", tipo=NUMERICA, faixas=("30", "50")),)
        descritiva = descrita(bancos.completo(), linhas)
        corpo = _linhas_da_tabela(_tabela(descritiva, "faixas_idade.csv"))
        assert "(abaixo da primeira faixa)" in corpo
        assert "(acima da última faixa)" in corpo
        assert any("fora das faixas" in aviso for aviso in descritiva.avisos)

    def test_a_convencao_de_fechamento_esta_escrita_no_arquivo(self, descrita):
        tabela = _tabela(
            descrita(bancos.completo(), (Linha(variavel="idade", tipo=NUMERICA),)),
            "faixas_idade.csv",
        )
        assert any("[a a b)" in nota for nota in tabela.notas)

    def test_quartis_que_coincidem_nao_geram_tabela(self, descrita):
        """
        Em uma variável com poucos valores distintos, Q1, mediana e Q3
        coincidem, e o que sairia seria uma tabela de duas faixas com nome de
        quatro. Uma variável assim é categórica disfarçada, e a decisão de
        tratá-la como tal é sua, no dicionário.
        """
        quadro = bancos.completo()
        quadro["escala"] = [1] * 20 + [2] * 4
        descritiva = descrita(quadro, (Linha(variavel="escala", tipo=NUMERICA),))
        detalhes = descritiva.variaveis[0].detalhes["faixas"]
        assert detalhes["origem"] is None
        assert "categórica disfarçada" in detalhes["motivo"]

    def test_as_classes_do_histograma_nao_sao_as_faixas_da_tabela(self, descrita):
        """
        A tabela responde "quantos em cada grupo que interessa"; o histograma
        mostra a forma da distribuição. Fazer os dois com os mesmos cortes é
        publicar a mesma informação duas vezes.
        """
        linhas = (Linha(variavel="idade", tipo=NUMERICA, faixas=("20", "40", "70")),)
        descritiva = descrita(bancos.completo(), linhas)
        variavel = descritiva.variaveis[0]
        classes = variavel.detalhes["histograma"]["classes"]
        assert classes != len(variavel.detalhes["faixas"]["cortes"]) - 1


# ── Datas ───────────────────────────────────────────────────────────────────


class TestData:
    def test_a_data_como_texto_e_convertida_e_o_formato_fica_registrado(self, descrita):
        """
        A assimetria: a numérica como texto é recusada, a data é convertida. Num
        `.csv` não existe tipo data, e exigir que o cliente "conserte" isso
        recusaria todo projeto que manda `.csv`.
        """
        descritiva = descrita(bancos.completo(), (Linha(variavel="data_coleta", tipo=DATA),))
        assert descritiva.variaveis[0].detalhes["formato"] == "%d/%m/%Y"

    def test_dois_formatos_misturados_sao_recusados_como_as_numericas(self, descrita):
        with pytest.raises(VariavelIncompativelError):
            descrita(bancos.com_datas_misturadas(), (Linha(variavel="data_coleta", tipo=DATA),))

    def test_o_periodo_traz_primeira_ultima_e_amplitude(self, descrita):
        tabela = _tabela(
            descrita(bancos.completo(), (Linha(variavel="data_coleta", tipo=DATA),)),
            "data_data_coleta.csv",
        )
        rotulos = [linha[0] for linha in tabela.linhas]
        assert "primeira data" in rotulos and "amplitude (dias)" in rotulos

    def test_periodo_sem_nenhum_caso_entra_com_zero(self, descrita):
        """
        Três meses sem recrutamento é informação — e uma tabela que pula esses
        meses esconde justamente o que se queria ver.
        """
        quadro = bancos.completo().head(4).copy()
        quadro["data_coleta"] = ["01/01/2026", "02/01/2026", "01/06/2026", "02/06/2026"]
        tabela = _tabela(
            descrita(quadro, (Linha(variavel="data_coleta", tipo=DATA),)),
            "periodo_data_coleta.csv",
        )
        zeros = [linha for linha in tabela.linhas if linha[1] == "0"]
        assert len(zeros) == 4, "fevereiro a maio precisam aparecer com n = 0"

    def test_periodo_curto_e_contado_por_mes_e_longo_por_ano(self, descrita):
        quadro = bancos.completo().head(4).copy()
        quadro["data_coleta"] = ["01/01/2020", "02/01/2021", "01/06/2024", "02/06/2026"]
        descritiva = descrita(quadro, (Linha(variavel="data_coleta", tipo=DATA),))
        assert descritiva.variaveis[0].detalhes["passo"] == "ano"


# ── O manifesto e a escrita ─────────────────────────────────────────────────


class TestManifestoDaRodada:
    def test_a_ordem_dos_itens_e_a_do_dicionario(self, descrita):
        linhas = (
            Linha(variavel="idade", tipo=NUMERICA),
            Linha(variavel="sexo", tipo=CATEGORICA),
        )
        manifesto = montar_manifesto(descrita(bancos.completo(), linhas), linhas, True)
        assert [item.variavel for item in manifesto.itens] == ["idade", "sexo"]

    def test_registra_o_banco_o_ambiente_e_a_semente(self, descrita):
        linhas = (Linha(variavel="sexo", tipo=CATEGORICA),)
        manifesto = montar_manifesto(descrita(bancos.completo(), linhas), linhas, True)
        assert manifesto.banco["sha256"] == "a" * 64
        assert manifesto.ambiente["pandas"] == pd.__version__
        assert manifesto.regras["semente"] == SEMENTE
        assert manifesto.regras["limite_de_barras"] == LIMITE_BARRAS

    def test_sem_graficos_o_matplotlib_nao_e_consultado(self, descrita):
        linhas = (Linha(variavel="sexo", tipo=CATEGORICA),)
        manifesto = montar_manifesto(descrita(bancos.completo(), linhas), linhas, False)
        assert manifesto.ambiente["matplotlib"] is None

    def test_a_especie_e_um_campo_e_nao_a_extensao(self, descrita):
        linhas = (Linha(variavel="idade", tipo=NUMERICA),)
        manifesto = montar_manifesto(descrita(bancos.completo(), linhas), linhas, True)
        especies = {a.especie for a in manifesto.itens[0].artefatos}
        assert {"resumo", "faixas", "histograma"} <= especies


class TestEscrita:
    def test_o_manifesto_e_escrito_por_ultimo(self, projeto_com_rodada, pasta_da_rodada):
        """
        O índice vem depois do que ele descreve: um índice que aponta para
        arquivo inexistente é pior do que índice nenhum.
        """
        raiz = projeto_com_rodada()
        pasta = pasta_da_rodada(raiz)
        corpo = json.loads((pasta / ARQUIVO_MANIFESTO).read_text(encoding="utf-8"))
        for variavel in corpo["variaveis"]:
            for artefato in variavel["artefatos"]:
                assert (pasta / artefato["arquivo"]).is_file()

    def test_regerar_arquiva_a_rodada_anterior_inteira(self, projeto_com_rodada):
        from datetime import datetime

        raiz = projeto_com_rodada()
        executar_descritiva(preparar_descritiva(raiz, agora=datetime(2026, 9, 10, 9, 0)))
        arquivadas = [
            p for p in (raiz / PASTA_ANTIGAS).iterdir()
            if p.is_dir() and p.name.startswith(PASTA_DESCRITIVA)
        ]
        assert len(arquivadas) == 1
        assert (arquivadas[0] / ARQUIVO_MANIFESTO).is_file()

    def test_duas_rodadas_no_mesmo_dia_nao_colidem(self, projeto_com_rodada):
        from datetime import datetime

        raiz = projeto_com_rodada()
        executar_descritiva(preparar_descritiva(raiz, agora=datetime(2026, 9, 9, 15, 0)))
        executar_descritiva(preparar_descritiva(raiz, agora=datetime(2026, 9, 9, 16, 0)))
        arquivadas = [p for p in (raiz / PASTA_ANTIGAS).iterdir() if p.is_dir()]
        assert len(arquivadas) == 2

    def test_preparar_nao_escreve_nada(self, projeto_com_banco):
        from flatcap.perfil import executar_perfil, preparar_perfil

        raiz = projeto_com_banco()
        executar_perfil(preparar_perfil(raiz))
        preparar_descritiva(raiz)
        assert not (raiz / PASTA_ANALISES / PASTA_DESCRITIVA).exists()

    def test_o_texto_do_plano_e_o_arquivo_gravado(self, projeto_com_banco, pasta_da_rodada):
        from flatcap.perfil import executar_perfil, preparar_perfil

        raiz = projeto_com_banco()
        executar_perfil(preparar_perfil(raiz))
        plano = preparar_descritiva(raiz, agora=AGORA)
        executar_descritiva(plano)
        gravado = (pasta_da_rodada(raiz) / ARQUIVO_MANIFESTO).read_text(encoding="utf-8")
        assert gravado == plano.texto_manifesto

    def test_a_falha_no_meio_devolve_a_rodada_arquivada_ao_lugar(
        self, projeto_com_rodada, pasta_da_rodada, monkeypatch
    ):
        """
        Sem isso, a rodada anterior teria sumido em troca de nada.

        Este teste passa no POSIX por acidente do sistema de arquivos: o
        `os.rename` do POSIX aceita substituir um diretório **vazio**, e é
        exatamente isso que a reversão faz — a pasta nova já foi criada pelo
        `mkdir` e não entra na lista de desfazer. No Windows a mesma chamada
        levanta `FileExistsError`, e a reversão falha em silêncio, virando
        apenas o aviso "Falhei ao desfazer uma etapa".

        O conserto é a pasta nova entrar na lista de desfazer, com `rmdir`,
        antes de a arquivada voltar.
        """
        from datetime import datetime

        import flatcap.descritiva as modulo

        raiz = projeto_com_rodada()
        antes = sorted(p.name for p in pasta_da_rodada(raiz).iterdir())

        original = modulo.escrever_atomico
        contador = {"n": 0}

        def falhar(caminho, texto):
            contador["n"] += 1
            if contador["n"] == 3:
                raise OSError("disco cheio (simulado)")
            return original(caminho, texto)

        monkeypatch.setattr(modulo, "escrever_atomico", falhar)
        with pytest.raises(OSError):
            executar_descritiva(preparar_descritiva(raiz, agora=datetime(2026, 9, 10, 9, 0)))

        assert sorted(p.name for p in pasta_da_rodada(raiz).iterdir()) == antes
        assert not [p for p in (raiz / PASTA_ANTIGAS).iterdir() if p.is_dir()]

    def test_os_csv_saem_com_bom_e_ponto_e_virgula(self, projeto_com_rodada, pasta_da_rodada):
        raiz = projeto_com_rodada()
        bruto = (pasta_da_rodada(raiz) / "freq_sexo.csv").read_bytes()
        assert bruto.startswith(b"\xef\xbb\xbf")
        assert b";" in bruto

    def test_o_csv_se_descreve_nas_primeiras_linhas(self, projeto_com_rodada, pasta_da_rodada):
        """
        Para o dia em que alguém abrir `freq_sexo.csv` sozinho, fora de qualquer
        contexto, e precisar saber de qual variável e de qual denominador ele
        fala.
        """
        raiz = projeto_com_rodada()
        texto = (pasta_da_rodada(raiz) / "freq_sexo.csv").read_text(encoding="utf-8-sig")
        comentarios = [linha_ for linha_ in texto.splitlines() if linha_.startswith("#")]
        assert any("variável: sexo" in linha_ for linha_ in comentarios)
        assert any("denominador" in linha_ for linha_ in comentarios)

    def test_sem_separador_de_milhar(self, descrita):
        """
        `1.234,5` numa célula é a forma mais fácil de um número virar texto na
        volta — e estes arquivos existem para serem lidos de volta.
        """
        quadro = bancos.completo()
        quadro["custo"] = [1234.5 + i for i in range(len(quadro))]
        tabela = _tabela(
            descrita(quadro, (Linha(variavel="custo", tipo=NUMERICA),)), "resumo_custo.csv"
        )
        valores = " ".join(linha[1] for linha in tabela.linhas)
        assert "1.234" not in valores
        assert "1234,5" in valores


class TestSlug:
    def test_nomes_que_colidem_ganham_sufixo(self, descrita):
        quadro = bancos.completo()
        quadro["Idade (anos)"] = quadro["idade"]
        quadro = quadro.rename(columns={"idade": "idade_anos"})
        linhas = (
            Linha(variavel="idade_anos", tipo=NUMERICA),
            Linha(variavel="Idade (anos)", tipo=NUMERICA),
        )
        slugs = [v.slug for v in descrita(quadro, linhas).variaveis]
        assert len(set(slugs)) == 2

    def test_acento_e_espaco_nao_entram_no_nome_do_arquivo(self, descrita):
        quadro = bancos.completo().rename(columns={"sexo": "Sexo do participante"})
        linhas = (Linha(variavel="Sexo do participante", tipo=CATEGORICA),)
        nome = descrita(quadro, linhas).tabelas[0].nome
        assert nome == "freq_sexo_do_participante.csv"
