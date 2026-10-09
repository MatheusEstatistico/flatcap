# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
"""
O `dicionario.csv` — Fase 4.

O arquivo que guarda as decisões da reunião. Três coisas ao mesmo tempo: a
entrada que dirige a descritiva, a documentação do que foi combinado, e o ponto
de ajuste quando o cliente pedir mudança.

Por isso o teste mais importante deste arquivo não é o do formato: é o da
**fusão**. Uma linha perdida aqui é uma decisão tomada com o cliente na frente
que precisa ser tomada de novo.
"""

from __future__ import annotations

import pytest

from flatcap.dicionario import (
    ARQUIVO_DICIONARIO,
    CATEGORICA,
    COLUNAS,
    DATA,
    IGNORAR,
    NUMERICA,
    SEPARADOR_CAMPO,
    SEPARADOR_LISTA,
    DicionarioInvalidoError,
    Linha,
    Sugestao,
    escrever,
    fundir,
    ler,
    ler_arquivo,
    texto_do_dicionario,
)


def _escrever(tmp_path, conteudo: str, nome: str = ARQUIVO_DICIONARIO):
    caminho = tmp_path / nome
    caminho.write_text(conteudo, encoding="utf-8", newline="\n")
    return caminho


CABECALHO = "variavel;rotulo;tipo;categorias_ordem;faixas;no_banco\n"


# ── Formato ─────────────────────────────────────────────────────────────────


class TestLeitura:
    """
    A leitura é tolerante e a escrita é estrita. Um arquivo salvo por outra
    ferramenta continua abrindo; o arquivo que o FlatCap escreve é sempre o
    mesmo.
    """

    def test_le_o_formato_que_o_flatcap_escreve(self, tmp_path):
        caminho = _escrever(
            tmp_path, CABECALHO + "sexo;Sexo;categorica;Feminino|Masculino;;sim\n"
        )
        (linha,) = ler_arquivo(caminho)
        assert linha.variavel == "sexo"
        assert linha.categorias_ordem == ("Feminino", "Masculino")
        assert linha.no_banco is True

    def test_le_o_arquivo_separado_por_virgula(self, tmp_path):
        caminho = _escrever(
            tmp_path,
            "variavel,rotulo,tipo,categorias_ordem,faixas,no_banco\n"
            "sexo,Sexo,categorica,Feminino|Masculino,,sim\n",
        )
        assert ler_arquivo(caminho)[0].categorias_ordem == ("Feminino", "Masculino")

    def test_le_cp1252_como_o_excel_salva(self, tmp_path):
        caminho = tmp_path / ARQUIVO_DICIONARIO
        caminho.write_bytes(
            (CABECALHO + "condicao;Condição;categorica;;;sim\n").encode("cp1252")
        )
        assert ler_arquivo(caminho)[0].rotulo == "Condição"

    @pytest.mark.parametrize("escrito", ["Categórica", "CATEGORICA", "categorica", " Numerica "])
    def test_o_tipo_aceita_acento_caixa_e_espaco(self, tmp_path, escrito):
        caminho = _escrever(tmp_path, CABECALHO + f"v;;{escrito};;;sim\n")
        assert ler_arquivo(caminho)[0].tipo in (CATEGORICA, NUMERICA)

    def test_tipo_fora_da_lista_recusa_dizendo_quais_valem(self, tmp_path):
        caminho = _escrever(tmp_path, CABECALHO + "v;;continua;;;sim\n")
        with pytest.raises(DicionarioInvalidoError) as erro:
            ler_arquivo(caminho)
        assert "ignorar" in str(erro.value)

    def test_tipo_em_branco_vira_categorica(self, tmp_path):
        caminho = _escrever(tmp_path, CABECALHO + "v;;;;;sim\n")
        assert ler_arquivo(caminho)[0].tipo == CATEGORICA

    def test_variavel_repetida_e_ambiguidade_e_recusa(self, tmp_path):
        """
        Duas linhas para a mesma variável: a descritiva não teria como saber
        qual das duas decisões vale.
        """
        caminho = _escrever(tmp_path, CABECALHO + "sexo;;categorica;;;sim\nsexo;;numerica;;;sim\n")
        with pytest.raises(DicionarioInvalidoError) as erro:
            ler_arquivo(caminho)
        assert "duas vezes" in str(erro.value)

    def test_ponto_e_virgula_digitado_dentro_da_lista_tem_mensagem_propria(self, tmp_path):
        """
        O engano previsível. A mensagem mostra a linha e escreve a forma certa,
        em vez de dizer "campos demais".
        """
        caminho = _escrever(
            tmp_path, CABECALHO + "escolaridade;;categorica;Fundamental;Médio;Superior;;sim\n"
        )
        with pytest.raises(DicionarioInvalidoError) as erro:
            ler_arquivo(caminho)
        assert SEPARADOR_LISTA in str(erro.value)

    def test_arquivo_vazio_manda_regerar(self, tmp_path):
        caminho = _escrever(tmp_path, "")
        with pytest.raises(DicionarioInvalidoError) as erro:
            ler_arquivo(caminho)
        assert "flatcap perfil" in str(erro.value)

    def test_sem_a_coluna_variavel_recusa(self, tmp_path):
        caminho = _escrever(tmp_path, "nome;tipo\nsexo;categorica\n")
        with pytest.raises(DicionarioInvalidoError) as erro:
            ler_arquivo(caminho)
        assert "variavel" in str(erro.value)

    def test_projeto_sem_dicionario_devolve_vazio_e_nao_estoura(self, tmp_path):
        assert ler(tmp_path) == ()

    def test_o_cabecalho_do_excel_com_caixa_trocada_e_a_mesma_coluna(self, tmp_path):
        caminho = _escrever(
            tmp_path,
            "Variavel;Rotulo;Tipo;Categorias_Ordem;Faixas;No_Banco\n"
            "sexo;Sexo;categorica;F|M;;sim\n",
        )
        assert ler_arquivo(caminho)[0].rotulo == "Sexo"

    def test_a_mensagem_aponta_a_linha_do_arquivo(self, tmp_path):
        """
        REGRESSÃO da 1.13.0. A linha da mensagem é a que o Excel e o editor
        mostram, contando o cabeçalho explicativo: no arquivo que o FlatCap
        escreve, a primeira variável fica na linha 17, e não na 2.
        """
        texto = texto_do_dicionario(
            (Linha(variavel="sexo", tipo=CATEGORICA), Linha(variavel="idade", tipo=NUMERICA))
        )
        texto += "sexo;;numerica;;;sim\n"
        caminho = _escrever(tmp_path, texto)
        linhas = caminho.read_text(encoding="utf-8-sig").splitlines()
        primeira = linhas.index(next(x for x in linhas if x.startswith("sexo;"))) + 1
        ultima = len(linhas)

        with pytest.raises(DicionarioInvalidoError) as erro:
            ler_arquivo(caminho)

        assert f"linhas {primeira} e {ultima}" in str(erro.value)
        assert primeira > 2, "o cabeçalho explicativo conta"


class TestCerquilhaDepoisDoCabecalho:
    """
    REGRESSÃO da 1.13.0. O `#` só é comentário no cabeçalho explicativo, antes da
    linha com os nomes das colunas. Depois dela, é dado: `#` e `#id` são nomes de
    coluna que existem em banco de verdade, e eram descartados a cada leitura — o
    perfil os acrescentava de novo a cada rodada, e a descritiva recusava o banco.
    """

    @pytest.mark.parametrize("nome", ["#", "#id", "# paciente"])
    def test_a_variavel_comecada_por_cerquilha_sobrevive_a_ida_e_volta(self, tmp_path, nome):
        linhas = (Linha(variavel=nome, tipo=IGNORAR), Linha(variavel="sexo", tipo=CATEGORICA))
        caminho = _escrever(tmp_path, texto_do_dicionario(linhas))

        assert [linha.variavel for linha in ler_arquivo(caminho)] == [nome, "sexo"]

    def test_o_cabecalho_explicativo_continua_fora(self, tmp_path):
        caminho = _escrever(
            tmp_path, "# um comentário\n\n#\n" + CABECALHO + "sexo;;categorica;;;sim\n"
        )
        assert [linha.variavel for linha in ler_arquivo(caminho)] == ["sexo"]


class TestFaixas:
    """
    Conferidas na leitura, e não na Fase 5. O erro é de digitação, e o momento
    de descobrir uma digitação errada é enquanto o arquivo está aberto na sua
    frente — não daqui a duas semanas, no meio da geração das tabelas.
    """

    def test_cortes_validos(self, tmp_path):
        caminho = _escrever(tmp_path, CABECALHO + "idade;;numerica;;0|18|30|60|120;sim\n")
        assert ler_arquivo(caminho)[0].faixas == ("0", "18", "30", "60", "120")

    def test_corte_que_nao_e_numero(self, tmp_path):
        caminho = _escrever(tmp_path, CABECALHO + "idade;;numerica;;0|dezoito|30;sim\n")
        with pytest.raises(DicionarioInvalidoError) as erro:
            ler_arquivo(caminho)
        assert "não é número" in str(erro.value)

    def test_cortes_fora_de_ordem(self, tmp_path):
        caminho = _escrever(tmp_path, CABECALHO + "idade;;numerica;;0|30|18;sim\n")
        with pytest.raises(DicionarioInvalidoError) as erro:
            ler_arquivo(caminho)
        assert "crescente" in str(erro.value)

    def test_corte_repetido_deixaria_uma_faixa_vazia(self, tmp_path):
        caminho = _escrever(tmp_path, CABECALHO + "idade;;numerica;;0|18|18|30;sim\n")
        with pytest.raises(DicionarioInvalidoError):
            ler_arquivo(caminho)

    def test_aceita_virgula_decimal_no_corte(self, tmp_path):
        caminho = _escrever(tmp_path, CABECALHO + "imc;;numerica;;18,5|25|30;sim\n")
        assert ler_arquivo(caminho)[0].faixas == ("18,5", "25", "30")


class TestIdaEVolta:
    """
    O que foi escrito precisa voltar igual. É o arquivo em que a reunião inteira
    é registrada, e uma diferença entre a gravação e a leitura é uma decisão que
    muda sozinha.
    """

    def test_uma_linha_completa_sobrevive(self, tmp_path):
        linha = Linha(
            variavel="escolaridade",
            rotulo="Escolaridade",
            tipo=CATEGORICA,
            categorias_ordem=("Fundamental", "Médio", "Superior"),
            no_banco=True,
        )
        caminho = _escrever(tmp_path, texto_do_dicionario((linha,)))
        assert ler_arquivo(caminho)[0] == linha

    def test_categoria_unica_contendo_ponto_e_virgula(self, tmp_path):
        """
        REGRESSÃO — a decisão da reunião que muda sozinha.

        A leitura aceita `;` como separador de lista, para o arquivo que veio de
        outra ferramenta escrito `Feminino;Masculino`. Com duas categorias ou
        mais, o `|` que junta a lista aparece primeiro e protege o campo. Com
        **uma** categoria só, não há `|` no campo — e `Alta; a pedido` volta da
        leitura como duas categorias, `Alta` e `a pedido`.

        A escrita está certa: o `csv.writer` põe o campo entre aspas e o
        `csv.reader` o devolve inteiro. Quem parte é a tolerância do `;`, depois.

        O conserto que preserva a tolerância documentada: só aceitar `;` como
        separador de lista quando o **separador de campos** do arquivo for `,` —
        num arquivo separado por `;`, um `;` dentro do campo é literal.
        """
        linha = Linha(variavel="desfecho", tipo=CATEGORICA, categorias_ordem=("Alta; a pedido",))
        caminho = _escrever(tmp_path, texto_do_dicionario((linha,)))
        assert ler_arquivo(caminho)[0].categorias_ordem == ("Alta; a pedido",)

    def test_categoria_com_espaco_no_fim_sobrevive(self, tmp_path):
        """
        `"Sim "` e `"Sim"` são categorias diferentes para qualquer contagem — é
        justamente o que o detector `espaco_sobrando` denuncia. Se a leitura
        apara o espaço, a categoria declarada deixa de casar com o valor do
        banco, e a tabela sai com a linha declarada em `n = 0`.
        """
        linha = Linha(variavel="consentiu", tipo=CATEGORICA, categorias_ordem=("Sim ", "Não"))
        caminho = _escrever(tmp_path, texto_do_dicionario((linha,)))
        assert ler_arquivo(caminho)[0].categorias_ordem == ("Sim ", "Não")

    def test_o_arquivo_sai_com_bom_para_o_excel_ptbr(self, tmp_path):
        """
        Sem o BOM, `Condição` vira `CondiÃ§Ã£o` no arquivo que você mais edita à
        mão.
        """
        texto = texto_do_dicionario((Linha(variavel="condicao", rotulo="Condição"),))
        assert texto.startswith("\ufeff")

    def test_duas_gravacoes_identicas_produzem_o_mesmo_texto(self, tmp_path):
        linhas = (Linha(variavel="a"), Linha(variavel="b"))
        assert texto_do_dicionario(linhas) == texto_do_dicionario(linhas)

    def test_a_escrita_e_sempre_com_ponto_e_virgula_e_barra(self, tmp_path):
        texto = texto_do_dicionario(
            (Linha(variavel="v", categorias_ordem=("um", "dois")),)
        )
        corpo = [linha for linha in texto.splitlines() if linha.startswith("v;")][0]
        assert corpo.count(SEPARADOR_CAMPO) == len(COLUNAS) - 1
        assert f"um{SEPARADOR_LISTA}dois" in corpo


# ── A fusão ─────────────────────────────────────────────────────────────────


class TestFusao:
    """
    A regra que manda em tudo: **linha que já existe no arquivo não é tocada.
    Nunca. Nem um campo.**

    O `perfil` roda mais de uma vez no mesmo projeto — antes da reunião, e de
    novo quando o cliente mandar o banco revisado. Entre uma e outra, você
    preencheu o arquivo.
    """

    def test_a_primeira_vez_e_so_a_sugestao(self):
        fusao = fundir((), (Sugestao(variavel="sexo", tipo=CATEGORICA).como_linha(),))
        assert not fusao.existia
        assert fusao.novas == ("sexo",)
        assert fusao.total == 1

    def test_linha_preenchida_vence_a_sugestao_inteira(self):
        existente = Linha(
            variavel="sexo",
            rotulo="Sexo do participante",
            tipo=CATEGORICA,
            categorias_ordem=("Feminino", "Masculino"),
        )
        sugestao = Linha(variavel="sexo", rotulo="sexo", tipo=IGNORAR)
        (linha,) = fundir((existente,), (sugestao,)).linhas
        assert linha.rotulo == "Sexo do participante"
        assert linha.tipo == CATEGORICA
        assert linha.categorias_ordem == ("Feminino", "Masculino")

    def test_variavel_nova_entra_no_fim_com_a_sugestao(self):
        existente = Linha(variavel="sexo", tipo=CATEGORICA)
        fusao = fundir(
            (existente,),
            (Linha(variavel="sexo"), Linha(variavel="idade", tipo=NUMERICA)),
        )
        assert fusao.novas == ("idade",)
        assert [linha.variavel for linha in fusao.linhas] == ["sexo", "idade"]

    def test_variavel_que_sumiu_do_banco_continua_no_arquivo_marcada(self):
        """
        Apagá-la jogaria fora a decisão da reunião — e o cliente que removeu uma
        coluna sem avisar costuma devolvê-la na versão seguinte.
        """
        existente = Linha(variavel="peso_anterior", tipo=NUMERICA)
        fusao = fundir((existente,), (Linha(variavel="sexo"),))
        assert fusao.ausentes == ("peso_anterior",)
        fora = next(linha_ for linha_ in fusao.linhas if linha_.variavel == "peso_anterior")
        assert fora.no_banco is False
        assert fora.tipo == NUMERICA

    def test_variavel_que_voltou_ao_banco_e_remarcada(self):
        existente = Linha(variavel="peso_anterior", tipo=NUMERICA, no_banco=False)
        fusao = fundir((existente,), (Linha(variavel="peso_anterior"),))
        assert fusao.reaparecidas == ("peso_anterior",)
        assert fusao.linhas[0].no_banco is True

    def test_no_banco_e_o_unico_campo_que_o_flatcap_reescreve(self):
        """
        Ela pode ser reescrita porque **não carrega decisão nenhuma** — é um
        fato do banco, não uma escolha sua.
        """
        existente = Linha(variavel="v", rotulo="R", tipo=NUMERICA, no_banco=False)
        (linha,) = fundir((existente,), (Linha(variavel="v"),)).linhas
        assert (linha.rotulo, linha.tipo) == ("R", NUMERICA)
        assert linha.no_banco is True

    def test_a_ordem_de_saida_e_a_das_colunas_do_banco(self):
        """
        Mantém o arquivo lado a lado com a planilha na tela, e junta no rodapé o
        que já não tem correspondência.
        """
        existentes = (Linha(variavel="c"), Linha(variavel="a"), Linha(variavel="z"))
        sugestoes = (Linha(variavel="a"), Linha(variavel="b"), Linha(variavel="c"))
        fusao = fundir(existentes, sugestoes)
        assert [linha_.variavel for linha_ in fusao.linhas] == ["a", "b", "c", "z"]

    def test_coluna_criada_por_voce_e_preservada_na_mesma_posicao(self, tmp_path):
        caminho = _escrever(
            tmp_path,
            "variavel;rotulo;tipo;categorias_ordem;faixas;no_banco;nota\n"
            "sexo;Sexo;categorica;;;sim;combinado em 04/09\n",
        )
        existentes = ler_arquivo(caminho)
        fusao = fundir(existentes, (Linha(variavel="sexo"), Linha(variavel="idade")))
        assert "nota" in fusao.colunas
        texto = texto_do_dicionario(fusao.linhas, fusao.colunas)
        assert "combinado em 04/09" in texto

    def test_fusao_sem_mudanca_nenhuma(self):
        existentes = (Linha(variavel="sexo", tipo=CATEGORICA),)
        fusao = fundir(existentes, (Linha(variavel="sexo"),))
        assert not fusao.mudou

    def test_escrever_grava_o_texto_do_plano(self, tmp_path):
        fusao = fundir((), (Linha(variavel="sexo", tipo=DATA),))
        caminho = escrever(tmp_path, fusao)
        assert caminho.read_text(encoding="utf-8-sig") == texto_do_dicionario(
            fusao.linhas, fusao.colunas
        ).lstrip("\ufeff")


class TestLinhaAnalisavel:
    """
    O que entra na descritiva da Fase 5, e o que não entra.
    """

    @pytest.mark.parametrize(
        ("tipo", "no_banco", "entra"),
        [
            (CATEGORICA, True, True),
            (NUMERICA, True, True),
            (DATA, True, True),
            (IGNORAR, True, False),
            (CATEGORICA, False, False),
            (IGNORAR, False, False),
        ],
    )
    def test_analisavel(self, tipo, no_banco, entra):
        assert Linha(variavel="v", tipo=tipo, no_banco=no_banco).analisavel is entra


class TestSemPandas:
    def test_o_dicionario_nao_importa_o_pandas(self):
        """
        O formato do arquivo que guarda as decisões da reunião não depende de
        como o banco foi lido. É a divisão da Fase 4, e ela só vale enquanto for
        verificável.
        """
        import ast
        import inspect

        import flatcap.dicionario as modulo

        arvore = ast.parse(inspect.getsource(modulo))
        importados = {
            no.module.split(".")[0] if isinstance(no, ast.ImportFrom) and no.module else ""
            for no in ast.walk(arvore)
            if isinstance(no, ast.ImportFrom)
        } | {
            alias.name.split(".")[0]
            for no in ast.walk(arvore)
            if isinstance(no, ast.Import)
            for alias in no.names
        }
        assert "pandas" not in importados
