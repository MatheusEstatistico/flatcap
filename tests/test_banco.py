"""
Abrir o banco — Fase 4.

Um módulo só responde "qual arquivo é o banco deste projeto, agora?", e as três
fases que perguntam recebem a mesma resposta. O teste que importa aqui não é o
do caminho feliz: é o dos arquivos que chegam torto — o `.csv` do Excel em
português, o do R, o de uma coluna só, o `.xlsx` com três abas, o `.xls`
renomeado.
"""

from __future__ import annotations

import pytest

import bancos
from flatcap.banco import (
    EXTENSOES_SUPORTADAS,
    FORMATOS_DATA,
    AbaInexistenteError,
    BancoAusenteError,
    BancoIlegivelError,
    BancoNaoRegistradoError,
    BancoVazioError,
    FormatoNaoSuportadoError,
    abrir,
    abrir_arquivo,
    formato_de_data,
    versao_vigente,
)
from flatcap.ficha import Ficha, Versao
from flatcap.ficha import versao_vigente as vigente_da_ficha
from flatcap.projeto import PASTA_ANTIGAS, PASTA_DADOS

# ── Codificação e separador ─────────────────────────────────────────────────


class TestLeituraDeCsv:
    """
    Um `.csv` do Excel em português vem com `;` e cp1252; um do R vem com `,` e
    UTF-8. Os dois chegam com a mesma extensão e nenhuma marca que os distinga.
    Sem descobrir os dois, metade dos arquivos abre como uma coluna só de texto
    — e produz um perfil perfeitamente formatado e completamente errado.
    """

    def test_csv_do_excel_ptbr(self, tmp_path):
        caminho = bancos.csv_do_excel_ptbr(tmp_path / "b.csv")
        quadro, leitura = abrir_arquivo(caminho)
        assert leitura.separador == ";"
        assert leitura.codificacao == "cp1252"
        assert "sexo" in quadro.columns
        assert "José" not in str(quadro.iloc[0, 0])  # só para provar que decodificou

    def test_csv_do_r(self, tmp_path):
        caminho = bancos.csv_do_r(tmp_path / "b.csv")
        _, leitura = abrir_arquivo(caminho)
        assert leitura.separador == ","
        assert leitura.codificacao == "utf-8"

    def test_utf8_e_tentado_antes_de_latin1(self, tmp_path):
        """
        A ordem importa: UTF-8 é a única que **falha** quando o palpite está
        errado, o que a torna um teste de verdade. `latin-1` decodifica qualquer
        byte sem reclamar — tentada antes, aceitaria um arquivo UTF-8 e
        devolveria "JosÃ©".
        """
        caminho = tmp_path / "b.csv"
        caminho.write_text("nome;cidade\nJosé;São Paulo\n", encoding="utf-8", newline="\n")
        quadro, leitura = abrir_arquivo(caminho)
        assert leitura.codificacao == "utf-8"
        assert str(quadro["cidade"].iloc[0]) == "São Paulo"

    def test_bom_e_reconhecido(self, tmp_path):
        caminho = tmp_path / "b.csv"
        caminho.write_bytes("nome;idade\nAna;30\n".encode("utf-8-sig"))
        quadro, leitura = abrir_arquivo(caminho)
        assert leitura.codificacao == "utf-8-sig"
        assert list(quadro.columns) == ["nome", "idade"]

    def test_arquivo_grande_com_acento_no_corte_da_amostra(self, tmp_path):
        """
        REGRESSÃO — a mojibake silenciosa.

        A codificação é decidida sobre os primeiros 64 KiB do arquivo, e a
        amostra é cortada num byte qualquer. Quando esse byte é o primeiro de um
        caractere de dois bytes, o UTF-8 estrito falha na sequência truncada, o
        palpite cai em cp1252 — e o arquivo **inteiro** é lido em cp1252.

        O que chega à tabela, ao `dicionario.csv` e ao `.docx` é `SÃ£o Paulo`. E
        como a fusão do dicionário nunca reescreve linha existente, a categoria
        corrompida fica lá até alguém editar à mão.

        O conserto é cortar a amostra no último `\\n` antes de decodificar: o
        detector não precisa de um byte que ele não sabe interpretar.
        """
        caminho = bancos.csv_utf8_com_acento_no_corte(tmp_path / "grande.csv")
        quadro, leitura = abrir_arquivo(caminho)
        assert leitura.codificacao.startswith("utf-8")
        assert str(quadro["cidade"].iloc[1]) == "São Paulo"

    def test_csv_de_uma_coluna_nao_e_partido_pela_virgula_decimal(self, tmp_path):
        """
        O defeito herdado que a Fase 5 consertou. O cabeçalho `peso` não tem
        separador; caindo em `,` como padrão, `70,5` virava dois campos e o
        `pandas` promovia a primeira metade a índice. O que chegava à análise
        era `peso` valendo 5, 2, 0 — e nada na saída denunciava.
        """
        caminho = bancos.csv_de_uma_coluna(tmp_path / "peso.csv")
        quadro, _ = abrir_arquivo(caminho)
        assert list(quadro.columns) == ["peso"]
        assert str(quadro["peso"].iloc[0]) == "70,5"

    def test_linha_com_campo_a_mais_nao_desloca_as_colunas(self, tmp_path):
        """
        `index_col=False`: sem isso, uma linha com mais campos do que o
        cabeçalho faz o `pandas` promover a primeira coluna a índice, e a tabela
        inteira anda uma casa para a esquerda sem que nada avise.
        """
        caminho = tmp_path / "b.csv"
        caminho.write_text(
            "nome;cidade\nAna;Belo Horizonte\nJoão;São Paulo;extra\n",
            encoding="utf-8",
            newline="\n",
        )
        quadro, leitura = abrir_arquivo(caminho)
        assert list(quadro.columns) == ["nome", "cidade"]
        assert str(quadro["nome"].iloc[0]) == "Ana"
        assert leitura.avisos, "o campo descartado precisa virar aviso, não silêncio"

    def test_csv_sem_nenhuma_linha_de_dados(self, tmp_path):
        caminho = tmp_path / "b.csv"
        caminho.write_text("nome;idade\n", encoding="utf-8", newline="\n")
        with pytest.raises(BancoVazioError):
            abrir_arquivo(caminho)

    def test_csv_de_zero_bytes(self, tmp_path):
        caminho = tmp_path / "b.csv"
        caminho.write_bytes(b"")
        with pytest.raises(BancoVazioError):
            abrir_arquivo(caminho)


# ── Planilhas ───────────────────────────────────────────────────────────────


class TestLeituraDeXlsx:
    def test_sem_aba_le_a_primeira_e_avisa_quais_ficaram_de_fora(self, tmp_path):
        caminho = bancos.xlsx_com_duas_abas(tmp_path / "b.xlsx")
        _, leitura = abrir_arquivo(caminho)
        assert leitura.aba == "Dados"
        assert leitura.outras_abas == ("Dicionário",)

    def test_com_aba_le_a_pedida(self, tmp_path):
        caminho = bancos.xlsx_com_duas_abas(tmp_path / "b.xlsx")
        _, leitura = abrir_arquivo(caminho, aba="Dicionário")
        assert leitura.aba == "Dicionário"

    def test_aba_inexistente_lista_as_que_existem(self, tmp_path):
        caminho = bancos.xlsx_com_duas_abas(tmp_path / "b.xlsx")
        with pytest.raises(AbaInexistenteError) as erro:
            abrir_arquivo(caminho, aba="Planilha1")
        assert "Dados" in str(erro.value)

    def test_arquivo_corrompido_vira_mensagem_e_nao_traceback(self, tmp_path):
        """
        Um `.csv` renomeado para `.xlsx` estoura em lugares diferentes de duas
        bibliotecas de terceiros. O que interessa a quem acabou de receber o
        arquivo do cliente é sempre a mesma frase.
        """
        caminho = bancos.arquivo_corrompido(tmp_path / "b.xlsx")
        with pytest.raises(BancoIlegivelError) as erro:
            abrir_arquivo(caminho)
        assert "Excel" in str(erro.value)


class TestFormatoNaoSuportado:
    @pytest.mark.parametrize(
        ("extensao", "pista"),
        [(".xls", "Excel antigo"), (".sav", "SPSS"), (".dta", "Stata"), (".pdf", "PDF")],
    )
    def test_a_mensagem_diz_o_que_fazer(self, tmp_path, extensao, pista):
        """
        "Formato não suportado" sozinho não ajuda ninguém que acabou de receber
        o arquivo do cliente.
        """
        caminho = tmp_path / f"b{extensao}"
        caminho.write_bytes(b"qualquer coisa")
        with pytest.raises(FormatoNaoSuportadoError) as erro:
            abrir_arquivo(caminho)
        assert pista in str(erro.value)

    def test_extensao_desconhecida_tambem_orienta(self, tmp_path):
        caminho = tmp_path / "b.parquet"
        caminho.write_bytes(b"x")
        with pytest.raises(FormatoNaoSuportadoError) as erro:
            abrir_arquivo(caminho)
        assert "dados adicionar" in str(erro.value)

    def test_a_lista_de_suportados_e_a_do_modulo(self):
        assert EXTENSOES_SUPORTADAS == (".xlsx", ".csv")


# ── Qual versão vale ────────────────────────────────────────────────────────


class TestVersaoVigente:
    def test_o_nome_reexportado_e_o_mesmo_objeto_do_ficha(self):
        """
        `versao_vigente` desceu para o `ficha.py` na Fase 6 para que o
        `relatorio.py` a use sem carregar o `pandas`. O `banco.py` reexporta o
        nome, e nenhum chamador mudou — mas só enquanto forem o mesmo objeto.
        """
        assert versao_vigente is vigente_da_ficha

    def test_e_a_de_maior_sequencia_e_nao_a_ultima_da_lista(self, tmp_path):
        """
        A ficha é editada à mão: uma entrada acrescentada fora de ordem faria a
        última da lista deixar de ser a mais nova.
        """
        ficha = Ficha(
            raiz=tmp_path,
            record_id="42",
            matricula="00742",
            nome="Ana",
            tipo="professor",
            status="novo",
            dados=(
                Versao("02_revisado_2026-09-05_b.xlsx", "cliente_pos_reuniao", "b" * 64, 1),
                Versao("00_redcap_2026-09-01_b.xlsx", "redcap", "a" * 64, 1),
            ),
        )
        assert versao_vigente(ficha).arquivo.startswith("02_")

    def test_ficha_sem_dados_devolve_nada(self, tmp_path):
        ficha = Ficha(tmp_path, "42", "00742", "Ana", "professor", "novo", ())
        assert versao_vigente(ficha) is None


class TestAbrir:
    def test_abre_a_versao_vigente_registrada(self, projeto_com_banco):
        raiz = projeto_com_banco()
        banco = abrir(raiz)
        assert banco.linhas == len(bancos.completo())
        assert banco.confere is True

    def test_projeto_sem_versao_registrada(self, projeto_vazio):
        with pytest.raises(BancoNaoRegistradoError) as erro:
            abrir(projeto_vazio)
        assert "dados adicionar" in str(erro.value)

    def test_arquivo_largado_na_pasta_nao_vira_banco(self, projeto_vazio):
        """
        A busca é pela ficha, não pela pasta. Um arquivo copiado à mão em
        `1. Dados originais/` não é uma versão registrada, e o perfil é sempre
        de uma versão registrada — é o que permite escrever no `perfil.md` qual
        arquivo foi lido e com qual `sha256`.
        """
        solto = projeto_vazio / PASTA_DADOS / "banco_do_cliente.csv"
        bancos.csv_do_r(solto)
        with pytest.raises(BancoNaoRegistradoError) as erro:
            abrir(projeto_vazio)
        assert "banco_do_cliente.csv" in str(erro.value)

    def test_versao_registrada_e_ausente_do_disco_recusa(self, projeto_com_banco):
        raiz = projeto_com_banco()
        (raiz / PASTA_DADOS / "00_redcap_2026-09-01_banco.csv").unlink()
        with pytest.raises(BancoAusenteError) as erro:
            abrir(raiz)
        assert "não apague a entrada da ficha" in str(erro.value)

    def test_arquivo_alterado_abre_mas_o_aviso_viaja_junto(self, projeto_com_banco):
        """
        Diagnóstico não bloqueia; mas fica escrito no documento que você leva
        para a reunião que o banco perfilado não é o que a ficha descreve.
        """
        raiz = projeto_com_banco()
        alvo = raiz / PASTA_DADOS / "00_redcap_2026-09-01_banco.csv"
        alvo.write_text(alvo.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        banco = abrir(raiz)
        assert banco.confere is False
        assert any("conteúdo diferente" in aviso for aviso in banco.avisos)

    def test_rapido_nao_confere_e_diz_que_nao_conferiu(self, projeto_com_banco):
        raiz = projeto_com_banco()
        assert abrir(raiz, conferir=False).confere is None

    def test_le_a_versao_de_dentro_de_versoes_antigas_se_for_a_vigente(
        self, projeto_com_banco
    ):
        raiz = projeto_com_banco()
        origem = raiz / PASTA_DADOS / "00_redcap_2026-09-01_banco.csv"
        origem.rename(raiz / PASTA_ANTIGAS / origem.name)
        assert abrir(raiz).linhas == len(bancos.completo())

    def test_o_banco_nao_conserta_nada(self, projeto_com_banco):
        """
        Ninguém passa `decimal=","` aqui: quem lê assim não vê o problema, e o
        problema é justamente o produto da Fase 4.
        """
        raiz = projeto_com_banco(bancos.com_virgula_decimal())
        banco = abrir(raiz)
        assert str(banco.quadro["imc"].iloc[0]) == "22,5"


# ── Formato de data ─────────────────────────────────────────────────────────


class TestFormatoDeData:
    """
    A Fase 4 usa isto para denunciar `data_como_texto`; a Fase 5, para converter.
    Duas listas de formatos seria como um comando lê `03/04` como 3 de abril e o
    outro como 4 de março.
    """

    @pytest.mark.parametrize(
        ("valores", "formato"),
        [
            (["01/02/2026", "15/03/2026", "28/12/2026"], "%d/%m/%Y"),
            (["2026-02-01", "2026-03-15", "2026-12-28"], "%Y-%m-%d"),
            (["01-02-2026", "15-03-2026", "28-12-2026"], "%d-%m-%Y"),
        ],
    )
    def test_reconhece_os_formatos_da_lista(self, valores, formato):
        assert formato_de_data(valores)[0] == formato

    def test_dois_formatos_misturados_e_indecidivel(self):
        """
        Coluna com dois formatos não é convertida por ninguém: é devolvida como
        indecidível, que é o que ela é.
        """
        assert formato_de_data(["01/02/2026", "2026-03-15", "15/04/2026"])[0] is None

    def test_texto_comum_nao_e_data(self):
        assert formato_de_data(["Feminino", "Masculino"])[0] is None

    def test_lista_vazia(self):
        assert formato_de_data([]) == (None, 0)

    def test_o_dia_e_o_mes_nao_se_invertem(self):
        """
        O palpite do `pandas` aceita formatos misturados e inverte dia com mês
        sem avisar. Aqui cada formato é testado explícito, um por vez.
        """
        formato, quantas = formato_de_data(["13/01/2026", "14/01/2026", "15/01/2026"])
        assert formato == "%d/%m/%Y"
        assert quantas == 3

    def test_a_lista_de_formatos_e_publica(self):
        assert "%d/%m/%Y" in FORMATOS_DATA
