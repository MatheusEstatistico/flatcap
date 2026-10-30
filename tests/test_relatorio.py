# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
"""
O conteúdo do relatório — Fase 6.

A promessa desta fase é verificável, e é o primeiro teste do arquivo: **o
relatório não abre o banco**. Nem `pandas`, nem `matplotlib`, nem uma média
recalculada. Enquanto ele passar, a decisão de arquitetura nº 3 do roteiro é um
fato e não uma retórica.

O resto do arquivo cobre a outra decisão da fase: **rodada velha gera, com o
aviso dentro**. Quatro conferências, nenhuma delas recusa, e todas viajam para
dentro do `.docx` — porque o terminal você vê agora e o documento é o que sobra
depois de o arquivo ser anexado a um e-mail.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import date, datetime

import pytest

import bancos
from conftest import escrever_ficha, linhas_do_historico
from flatcap.ficha import ler as ler_ficha
from flatcap.manifesto import ARQUIVO_MANIFESTO
from flatcap.metodologia import TITULO as TITULO_DA_METODOLOGIA
from flatcap.metodologia import montar_metodologia
from flatcap.projeto import PASTA_ANTIGAS, PASTA_DADOS
from flatcap.relatorio import (
    TEXTO_PADRAO,
    TITULO_PADRAO,
    DescritivaAusenteError,
    ModeloAusenteError,
    RelatorioError,
    TabelaIlegivelError,
    executar_relatorio,
    ler_tabela,
    montar_abertura,
    nome_do_relatorio,
    preparar_relatorio,
    relatorios_na_pasta,
    tabela_do_texto,
)

QUANDO = datetime(2026, 9, 9, 10, 0)


def _codigos(plano) -> set[str]:
    return {alerta.codigo for alerta in plano.relatorio.alertas}


# ── A promessa da fase ──────────────────────────────────────────────────────


def test_o_relatorio_nao_carrega_pandas_nem_matplotlib():
    """
    Em subprocesso porque `sys.modules` é global: outro teste já teria
    importado o `pandas`, e a asserção passaria por engano.
    """
    codigo = (
        "import sys; import flatcap.relatorio as r;"
        "print(int('pandas' in sys.modules), int('matplotlib' in sys.modules),"
        " int('docx' in sys.modules))"
    )
    saida = subprocess.run(
        [sys.executable, "-c", codigo], capture_output=True, text=True, check=True
    ).stdout.strip()
    assert saida == "0 0 0", "o relatorio.py passou a carregar biblioteca cara"


def test_o_python_docx_so_entra_na_execucao(projeto_com_rodada):
    """
    A simulação não escreve documento nenhum e não deve pagar pela biblioteca.
    """
    codigo = (
        "import sys, pathlib;"
        "from flatcap.relatorio import preparar_relatorio;"
        f"preparar_relatorio(pathlib.Path({str(projeto_com_rodada())!r}));"
        "print(int('docx' in sys.modules))"
    )
    saida = subprocess.run(
        [sys.executable, "-c", codigo], capture_output=True, text=True, check=True
    ).stdout.strip()
    assert saida == "0"


# ── A única recusa ──────────────────────────────────────────────────────────


class TestRecusa:
    def test_sem_manifesto_nao_ha_o_que_montar(self, projeto_com_banco):
        with pytest.raises(DescritivaAusenteError) as erro:
            preparar_relatorio(projeto_com_banco())
        assert "flatcap descritiva" in str(erro.value)

    def test_template_indicado_que_nao_existe(self, projeto_com_rodada, tmp_path):
        with pytest.raises(ModeloAusenteError) as erro:
            preparar_relatorio(projeto_com_rodada(), template=tmp_path / "nao_existe.docx")
        assert "aspas" in str(erro.value)

    def test_csv_da_rodada_ilegivel(self, projeto_com_rodada, pasta_da_rodada):
        raiz = projeto_com_rodada()
        alvo = pasta_da_rodada(raiz) / "freq_sexo.csv"
        alvo.write_text("# só comentário\n", encoding="utf-8", newline="\n")
        with pytest.raises(TabelaIlegivelError) as erro:
            preparar_relatorio(raiz)
        assert "flatcap descritiva" in str(erro.value)


# ── As seções ───────────────────────────────────────────────────────────────


class TestSecoes:
    def test_a_ordem_e_a_do_manifesto(self, projeto_com_rodada):
        plano = preparar_relatorio(projeto_com_rodada(), agora=QUANDO)
        from flatcap.manifesto import ler as ler_manifesto
        from flatcap.projeto import PASTA_ANALISES, PASTA_DESCRITIVA

        manifesto = ler_manifesto(plano.raiz / PASTA_ANALISES / PASTA_DESCRITIVA)
        assert [s.variavel for s in plano.secoes] == [i.variavel for i in manifesto.itens]

    def test_cada_secao_traz_as_tabelas_e_as_figuras_da_variavel(self, projeto_com_rodada):
        plano = preparar_relatorio(projeto_com_rodada(), agora=QUANDO)
        sexo = next(s for s in plano.secoes if s.variavel == "sexo")
        assert [t.especie for t in sexo.tabelas] == ["frequencia"]
        assert [f.especie for f in sexo.figuras] == ["barras"]

    def test_artefato_que_sumiu_vira_alerta_e_nao_interrompe(
        self, projeto_com_rodada, pasta_da_rodada
    ):
        """
        Recusar por causa de um `.png` apagado seria transformar um acidente
        reversível em um comando que não roda.
        """
        raiz = projeto_com_rodada()
        (pasta_da_rodada(raiz) / "graf_sexo.png").unlink()
        plano = preparar_relatorio(raiz, agora=QUANDO)
        assert "artefato_ausente" in _codigos(plano)
        assert plano.secoes

    def test_o_titulo_padrao_e_o_subtitulo(self, projeto_com_rodada):
        plano = preparar_relatorio(projeto_com_rodada(), agora=QUANDO)
        assert plano.relatorio.titulo == TITULO_PADRAO
        assert plano.relatorio.subtitulo == "00742 - José Antônio de Sá"

    def test_o_titulo_pode_ser_trocado_na_linha_de_comando(self, projeto_com_rodada):
        plano = preparar_relatorio(projeto_com_rodada(), agora=QUANDO, titulo="Parcial")
        assert plano.relatorio.titulo == "Parcial"

    def test_o_texto_padrao_entra_como_dado(self, projeto_com_rodada):
        """
        O `documento.py` não lê a constante. No dia em que o texto vier do
        `projeto.yaml`, só a linha que preenche o campo muda.
        """
        plano = preparar_relatorio(projeto_com_rodada(), agora=QUANDO)
        # A `TEXTO_PADRAO` abre a página, e a finalidade e os objetivos da ficha
        # vêm depois dela — os três pedaços que o `montar_abertura` junta.
        assert plano.relatorio.texto == montar_abertura(plano.relatorio.ficha)
        assert plano.relatorio.texto[: len(TEXTO_PADRAO)] == TEXTO_PADRAO


class TestMetodologia:
    """
    O que fecha a primeira página: o subtítulo e o parágrafo. O texto em si é do
    `test_metodologia.py`; aqui, os campos do `Relatorio` e o aviso.
    """

    def test_viaja_fora_do_texto_de_abertura(self, projeto_com_rodada):
        """
        O subtítulo é um título, e não texto corrido: por isso a metodologia tem os
        campos dela, e o `documento.py` sabe o que escrever no estilo de subtítulo.
        """
        plano = preparar_relatorio(projeto_com_rodada(), agora=QUANDO)
        relatorio = plano.relatorio
        metodologia = montar_metodologia(r.manifesto for r in relatorio.rodadas)
        assert relatorio.metodologia == metodologia.paragrafos
        assert relatorio.titulo_da_metodologia == TITULO_DA_METODOLOGIA
        assert not any(TITULO_DA_METODOLOGIA in paragrafo for paragrafo in relatorio.texto)
        assert not set(relatorio.metodologia) & set(relatorio.texto)

    def test_fala_da_rodada_que_esta_na_pasta(self, projeto_com_rodada):
        """O projeto da casa só tem a descritiva: nenhum teste, nenhum alfa."""
        relatorio = preparar_relatorio(projeto_com_rodada(), agora=QUANDO).relatorio
        (metodologia,) = relatorio.metodologia
        assert metodologia.startswith("As variáveis categóricas foram descritas")
        assert "significância" not in metodologia
        assert "usando a linguagem Python versão" in metodologia

    def test_rodada_sem_frase_vira_aviso_de_terminal(self, projeto_com_rodada, pasta_da_rodada):
        """
        Uma rodada cujo manifesto não diz o que rodou não ganha frase inventada: o
        parágrafo sai sem ela, e o aviso fica no terminal, que é quem pode resolver.
        """
        import shutil

        raiz = projeto_com_rodada()
        outra = raiz / "3. Análises" / "regressao"
        shutil.copytree(pasta_da_rodada(raiz), outra)
        manifesto = outra / ARQUIVO_MANIFESTO
        manifesto.write_text(
            manifesto.read_text(encoding="utf-8").replace(
                '"analise": "descritiva"', '"analise": "regressao"'
            ),
            encoding="utf-8",
        )
        plano = preparar_relatorio(raiz, agora=QUANDO)
        assert any(
            "metodologia" in aviso and "`regressao`" in aviso for aviso in plano.relatorio.avisos
        )
        assert "regressao" not in " ".join(plano.relatorio.metodologia)


class TestLerTabela:
    """
    Sem `pandas` de propósito. Não é economia de dependência, é economia de
    conversão: `read_csv` leria `28,7` como texto ou como número dependendo do
    `decimal=`, e das duas uma sairia diferente do que está no arquivo.
    """

    def test_o_texto_das_celulas_atravessa_intacto(self, projeto_com_rodada, pasta_da_rodada):
        raiz = projeto_com_rodada()
        tabela = ler_tabela(pasta_da_rodada(raiz) / "resumo_idade.csv")
        valores = {linha[0]: linha[1] for linha in tabela.linhas}
        assert "," in valores["média"], "a vírgula decimal virou ponto no caminho"

    def test_os_comentarios_viram_notas_e_o_primeiro_vira_titulo(
        self, projeto_com_rodada, pasta_da_rodada
    ):
        raiz = projeto_com_rodada()
        tabela = ler_tabela(pasta_da_rodada(raiz) / "freq_sexo.csv")
        assert tabela.titulo.startswith("Frequência")
        assert any("denominador" in nota for nota in tabela.notas)

    def test_a_linha_variavel_nao_vira_nota(self, projeto_com_rodada, pasta_da_rodada):
        """
        Repetir "variável: escolaridade" embaixo de uma tabela chamada
        "Escolaridade" é ruído em um documento que vai para o cliente.
        """
        raiz = projeto_com_rodada()
        tabela = ler_tabela(pasta_da_rodada(raiz) / "freq_sexo.csv")
        assert not any(nota.lower().startswith("variável:") for nota in tabela.notas)

    def test_o_titulo_do_manifesto_tem_precedencia(self, projeto_com_rodada, pasta_da_rodada):
        raiz = projeto_com_rodada()
        tabela = ler_tabela(pasta_da_rodada(raiz) / "freq_sexo.csv", titulo="Do manifesto")
        assert tabela.titulo == "Do manifesto"

    def test_le_cp1252_alem_de_utf8(self, tmp_path):
        caminho = tmp_path / "t.csv"
        caminho.write_bytes("# Frequência\ncategoria;n\nNão;3\n".encode("cp1252"))
        assert ler_tabela(caminho).linhas[0][0] == "Não"

    def test_a_categoria_comecada_por_cerquilha_fica_na_tabela(self, tmp_path):
        """
        REGRESSÃO da 1.13.0. O `#N/D` que o Excel deixa numa célula com erro de
        fórmula é uma categoria como outra qualquer. Lido como comentário, ele
        saía da tabela do documento e virava nota — quatro linhas no `.csv`, três
        no `.docx`, e um `Total` que não fechava.
        """
        from flatcap.manifesto import Tabela

        escrita = Tabela(
            nome="freq_x.csv",
            especie="frequencia",
            variavel="x",
            titulo="Frequência de x",
            colunas=("x", "n"),
            linhas=(("A", "5"), ("#N/D", "2"), ("B", "3"), ("Total", "10")),
            notas=("denominador: todos os casos",),
        )
        caminho = tmp_path / "freq_x.csv"
        caminho.write_text(escrita.texto(), encoding="utf-8")

        lida = ler_tabela(caminho)

        assert lida.linhas == escrita.linhas
        assert lida.titulo == "Frequência de x"
        assert lida.notas == ("denominador: todos os casos",)


class TestTabelaDoTexto:
    def test_e_o_que_o_ler_tabela_le_do_disco(self, tmp_path):
        """
        A amostragem monta o documento a partir do texto do `.csv` antes de ele ir ao
        disco; lido do texto ou do arquivo, a tabela tem de ser a mesma — com o BOM que o
        `Tabela.texto` escreve e o `utf-8-sig` tira.
        """
        from flatcap.manifesto import Tabela

        escrita = Tabela(
            nome="tamanho.csv",
            especie="tamanho",
            variavel="",
            titulo="Tamanho da amostra",
            colunas=("parâmetro", "valor"),
            linhas=(("População (N)", "1200"), ("Margem de erro", "2,5 pontos percentuais")),
            notas=("fórmula: n = N·z²·V / [(N − 1)·e² + z²·V]",),
        )
        caminho = tmp_path / "tamanho.csv"
        caminho.write_text(escrita.texto(), encoding="utf-8", newline="\n")

        do_texto = tabela_do_texto(escrita.texto(), "tamanho", "", caminho)
        assert do_texto == ler_tabela(caminho, "tamanho")
        assert do_texto.linhas == escrita.linhas
        assert do_texto.titulo == "Tamanho da amostra"

    def test_sem_linha_de_dados_e_ilegivel(self):
        with pytest.raises(TabelaIlegivelError, match="nenhuma linha de dados"):
            tabela_do_texto("# Só o título\n", caminho="vazia.csv")

    def test_os_nomes_publicos_sao_os_de_antes(self):
        """`localizar_template` e `conferir_texto` ficaram públicos com o apelido privado."""
        import flatcap.relatorio as modulo

        assert modulo._localizar_template is modulo.localizar_template
        assert modulo._conferir_texto is modulo.conferir_texto


# ── As quatro conferências ──────────────────────────────────────────────────


class TestAlertas:
    """
    O erro mais provável do fluxo não é técnico: é gerar o documento sobre uma
    rodada que já não descreve o que está na pasta. Nos dois casos o `.docx` sai
    perfeito e errado.
    """

    def test_rodada_atual_nao_gera_alerta_nenhum(self, projeto_com_rodada):
        assert _codigos(preparar_relatorio(projeto_com_rodada(), agora=QUANDO)) == set()

    def test_ficha_sem_finalidade_nem_objetivos_gera_texto_ausente(self, projeto_com_rodada):
        """
        Campo da primeira página em branco não encolhe a página em silêncio:
        vira marcador visível **e** alerta.

        Até o fixture passar a preencher os dois campos, este alerta saía em
        todo relatório da suíte — e por isso nenhum teste o conferia de
        propósito. Com a ficha completa por padrão, ele precisa do teste dele.
        """
        raiz = projeto_com_rodada()
        ficha = ler_ficha(raiz)
        escrever_ficha(
            raiz,
            finalidade=None,
            objetivos=None,
            dados=[
                {
                    "arquivo": versao.arquivo,
                    "origem": versao.origem,
                    "sha256": versao.sha256,
                    "tamanho_bytes": versao.tamanho_bytes,
                    "data": versao.data.isoformat(),
                }
                for versao in ficha.dados
            ],
        )
        plano = preparar_relatorio(raiz, agora=QUANDO)
        assert _codigos(plano) == {"texto_ausente"}
        assert any("«a preencher" in paragrafo for paragrafo in plano.relatorio.texto)

    def test_banco_mudou(self, projeto_com_rodada, projeto_com_banco):
        raiz = projeto_com_rodada()
        from conftest import escrever_ficha, sha_e_tamanho

        novo = raiz / PASTA_DADOS / "01_revisado_2026-09-08_banco.csv"
        bancos.csv_do_r(novo, bancos.com_coluna_constante())
        sha, tamanho = sha_e_tamanho(novo)
        antigo = raiz / PASTA_DADOS / "00_redcap_2026-09-01_banco.csv"
        sha_antigo, tam_antigo = sha_e_tamanho(antigo)
        escrever_ficha(
            raiz,
            dados=[
                {
                    "arquivo": antigo.name, "origem": "redcap", "sha256": sha_antigo,
                    "tamanho_bytes": tam_antigo, "data": "2026-09-01",
                },
                {
                    "arquivo": novo.name, "origem": "cliente_pos_reuniao", "sha256": sha,
                    "tamanho_bytes": tamanho, "data": "2026-09-08",
                },
            ],
        )
        plano = preparar_relatorio(raiz, agora=QUANDO)
        assert "banco_mudou" in _codigos(plano)
        detalhe = next(a for a in plano.relatorio.alertas if a.codigo == "banco_mudou").detalhe
        assert "01_revisado_2026-09-08_banco.csv" in detalhe

    def test_banco_alterado(self, projeto_com_rodada):
        raiz = projeto_com_rodada()
        alvo = raiz / PASTA_DADOS / "00_redcap_2026-09-01_banco.csv"
        alvo.write_text(alvo.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        assert "banco_alterado" in _codigos(preparar_relatorio(raiz, agora=QUANDO))

    def test_rapido_nao_confere_o_sha_e_nao_acusa_alteracao(self, projeto_com_rodada):
        raiz = projeto_com_rodada()
        alvo = raiz / PASTA_DADOS / "00_redcap_2026-09-01_banco.csv"
        alvo.write_text(alvo.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        assert "banco_alterado" not in _codigos(
            preparar_relatorio(raiz, agora=QUANDO, conferir=False)
        )

    def test_dicionario_mudou_de_rotulo(self, projeto_com_rodada):
        raiz = projeto_com_rodada()
        caminho = raiz / "dicionario.csv"
        texto = caminho.read_text(encoding="utf-8-sig").replace(
            "sexo;sexo;categorica", "sexo;Sexo do participante;categorica"
        )
        caminho.write_text(texto, encoding="utf-8", newline="\n")
        plano = preparar_relatorio(raiz, agora=QUANDO)
        assert "dicionario_mudou" in _codigos(plano)
        detalhe = next(
            a for a in plano.relatorio.alertas if a.codigo == "dicionario_mudou"
        ).detalhe
        assert "Sexo do participante" in detalhe

    def test_dicionario_mudou_de_tipo(self, projeto_com_rodada):
        raiz = projeto_com_rodada()
        caminho = raiz / "dicionario.csv"
        texto = caminho.read_text(encoding="utf-8-sig").replace(
            "sexo;sexo;categorica", "sexo;sexo;ignorar"
        )
        caminho.write_text(texto, encoding="utf-8", newline="\n")
        assert "dicionario_mudou" in _codigos(preparar_relatorio(raiz, agora=QUANDO))

    def test_faixas_iguais_nao_acusam_diferenca(self, projeto_com_rodada):
        """
        O dicionário guarda `0|30|120` como texto e o manifesto `[0, 30, 120]`
        como número: comparar sem converter acusaria diferença em todo projeto
        que usa faixas.
        """
        from flatcap.descritiva import executar_descritiva, preparar_descritiva

        raiz = projeto_com_rodada()
        caminho = raiz / "dicionario.csv"
        texto = caminho.read_text(encoding="utf-8-sig").replace(
            "idade;idade;numerica;;;", "idade;idade;numerica;;0|30|60|120;"
        )
        caminho.write_text(texto, encoding="utf-8", newline="\n")
        executar_descritiva(preparar_descritiva(raiz, agora=QUANDO))
        assert "dicionario_mudou" not in _codigos(preparar_relatorio(raiz, agora=QUANDO))

    def test_faixas_acrescentadas_depois_da_rodada(self, projeto_com_rodada):
        raiz = projeto_com_rodada()
        caminho = raiz / "dicionario.csv"
        texto = caminho.read_text(encoding="utf-8-sig").replace(
            "idade;idade;numerica;;;", "idade;idade;numerica;;0|30|60|120;"
        )
        caminho.write_text(texto, encoding="utf-8", newline="\n")
        assert "dicionario_mudou" in _codigos(preparar_relatorio(raiz, agora=QUANDO))

    def test_dicionario_ilegivel_vira_aviso_e_nao_recusa(self, projeto_com_rodada):
        """
        Ele já cumpriu o papel dele quando a rodada foi gerada; travar o
        documento por causa de um arquivo que o documento não usa seria recusa
        sem contrapartida.
        """
        raiz = projeto_com_rodada()
        (raiz / "dicionario.csv").write_text(
            "\ufeffvariavel;tipo\nsexo;continua\n", encoding="utf-8", newline="\n"
        )
        plano = preparar_relatorio(raiz, agora=QUANDO)
        assert plano.relatorio.avisos
        assert plano.secoes

    def test_dicionario_apagado_vira_alerta(self, projeto_com_rodada):
        raiz = projeto_com_rodada()
        (raiz / "dicionario.csv").unlink()
        assert "dicionario_ausente" in _codigos(preparar_relatorio(raiz, agora=QUANDO))

    def test_coluna_vazia_no_dicionario_nao_gera_alerta_falso(self, projeto_com_rodada):
        """
        Variável marcada e sem nenhum valor preenchido sai na lista `fora` da
        rodada, não entre os itens. Confrontar o dicionário com os itens sem
        olhar para `fora` acusaria mudança em todo projeto com coluna vazia.
        """
        raiz = projeto_com_rodada(bancos.com_coluna_vazia())
        assert "dicionario_mudou" not in _codigos(preparar_relatorio(raiz, agora=QUANDO))


# ── Nome, lugar e arquivamento ──────────────────────────────────────────────


class TestNomeELugar:
    def test_o_nome_segue_o_roteiro(self):
        assert nome_do_relatorio("00742", date(2026, 9, 20)) == (
            "Relatorio_00742_2026-09-20.docx"
        )

    def test_a_matricula_passa_pela_sanitizacao(self):
        assert "/" not in nome_do_relatorio("00742/A", date(2026, 9, 20))

    def test_matricula_vazia_nao_produz_nome_torto(self):
        assert nome_do_relatorio("", date(2026, 9, 20)) == (
            "Relatorio_sem_matricula_2026-09-20.docx"
        )

    def test_o_docx_fica_na_raiz_da_pasta_do_projeto(self, projeto_com_rodada):
        plano = preparar_relatorio(projeto_com_rodada(), agora=QUANDO)
        assert plano.destino.parent == plano.raiz

    def test_o_lixo_do_word_nao_conta_como_relatorio(self, projeto_com_rodada):
        raiz = projeto_com_rodada()
        (raiz / "~$Relatorio_00742_2026-09-01.docx").write_bytes(b"lixo")
        assert relatorios_na_pasta(raiz) == ()

    def test_regerar_manda_todos_os_anteriores_para_as_antigas(self, projeto_com_rodada):
        """
        Não só o de hoje. Uma pasta com três `.docx` de datas diferentes é uma
        pasta em que alguém anexa o errado no e-mail.
        """
        raiz = projeto_com_rodada()
        for dia in (1, 5):
            (raiz / f"Relatorio_00742_2026-09-{dia:02d}.docx").write_bytes(b"antigo")
        plano = preparar_relatorio(raiz, agora=QUANDO)
        assert len(plano.arquivamentos) == 2
        executar_relatorio(plano)
        assert relatorios_na_pasta(raiz) == (plano.destino,)
        assert len(list((raiz / PASTA_ANTIGAS).glob("Relatorio_*.docx"))) == 2

    def test_dois_no_mesmo_dia_ganham_sufixo(self, projeto_com_rodada):
        raiz = projeto_com_rodada()
        (raiz / PASTA_ANTIGAS / "Relatorio_00742_2026-09-09.docx").write_bytes(b"ja arquivado")
        (raiz / "Relatorio_00742_2026-09-09.docx").write_bytes(b"na raiz")
        plano = preparar_relatorio(raiz, agora=QUANDO)
        assert plano.arquivamentos[0][1].name == "Relatorio_00742_2026-09-09_2.docx"


class TestTemplate:
    def test_a_ordem_de_busca(self, projeto_com_rodada, tmp_path):
        # Quatro degraus desde a 1.1.0: o indicado, o do projeto, o do cliente
        # (o degrau novo) e o do FLATCAP_ROOT. Com o fixture em dois níveis,
        # `raiz.parent` passou a ser a pasta do cliente, e não mais o root.
        raiz = projeto_com_rodada()
        do_projeto = raiz / "template.docx"
        do_cliente = raiz.parent / "template.docx"
        do_root = raiz.parent.parent / "template.docx"
        indicado = tmp_path / "outro.docx"
        for caminho in (do_root, do_cliente, do_projeto, indicado):
            caminho.write_bytes(b"PK\x03\x04")

        assert preparar_relatorio(raiz, template=indicado, agora=QUANDO).template == indicado
        assert preparar_relatorio(raiz, agora=QUANDO).template == do_projeto
        do_projeto.unlink()
        assert preparar_relatorio(raiz, agora=QUANDO).template == do_cliente
        do_cliente.unlink()
        assert preparar_relatorio(raiz, agora=QUANDO).template == do_root
        do_root.unlink()
        assert preparar_relatorio(raiz, agora=QUANDO).template is None

    def test_o_nome_do_modelo_e_o_mesmo_dos_dois_lados(self):
        """
        O `relatorio.py` procura o modelo por nome e o `documento.py` o escreve
        por nome. Duas constantes para o mesmo arquivo é como uma delas deixa de
        receber a próxima correção — a regra da casa, aplicada a si mesma.
        """
        import re

        import flatcap.relatorio as modulo
        from flatcap.documento import ARQUIVO_TEMPLATE

        fonte = __import__("inspect").getsource(modulo._localizar_template)
        literais = set(re.findall(r'"([^"]*\.docx)"', fonte))
        assert not literais - {ARQUIVO_TEMPLATE} or literais == set(), (
            f"`{literais}` está escrito à mão; use a constante de documento.py"
        )


class TestExecucao:
    def test_escreve_o_docx_e_uma_linha_no_historico(self, projeto_com_rodada):
        from conftest import linhas_do_historico

        raiz = projeto_com_rodada()
        antes = len(linhas_do_historico(raiz))
        resultado = executar_relatorio(preparar_relatorio(raiz, agora=QUANDO))
        assert resultado.caminho.is_file()
        assert len(linhas_do_historico(raiz)) == antes + 1

    def test_preparar_nao_escreve_nada(self, projeto_com_rodada):
        raiz = projeto_com_rodada()
        plano = preparar_relatorio(raiz, agora=QUANDO)
        assert not plano.destino.exists()

    def test_a_falha_devolve_o_relatorio_arquivado_ao_lugar(
        self, projeto_com_rodada, monkeypatch
    ):
        raiz = projeto_com_rodada()
        anterior = raiz / "Relatorio_00742_2026-09-01.docx"
        anterior.write_bytes(b"anterior")

        import flatcap.documento as documento

        def falhar(*_a, **_k):
            raise OSError("disco cheio (simulado)")

        monkeypatch.setattr(documento, "escrever", falhar)
        with pytest.raises(OSError):
            executar_relatorio(preparar_relatorio(raiz, agora=QUANDO))
        assert anterior.is_file()
        assert not list((raiz / PASTA_ANTIGAS).glob("Relatorio_*.docx"))

    def test_a_falha_inesperada_tambem_devolve_o_anterior(
        self, projeto_com_rodada, monkeypatch
    ):
        """
        REGRESSÃO da 1.13.0. O desfazer pegava só `OSError` e `RelatorioError`, e
        o `python-docx` estoura com exceções que não são nenhuma das duas: o
        relatório anterior ficava em `2. Versões antigas/` sem o novo no lugar.
        O erro continua subindo — ele é bug —, mas depois de desfazer.
        """
        raiz = projeto_com_rodada()
        anterior = raiz / "Relatorio_00742_2026-09-01.docx"
        anterior.write_bytes(b"anterior")

        import flatcap.documento as documento

        def falhar(*_a, **_k):
            raise ValueError("falha que ninguém previu (simulada)")

        monkeypatch.setattr(documento, "escrever", falhar)
        with pytest.raises(ValueError):
            executar_relatorio(preparar_relatorio(raiz, agora=QUANDO))
        assert anterior.is_file()
        assert not list((raiz / PASTA_ANTIGAS).glob("Relatorio_*.docx"))

    def test_a_figura_ilegivel_vira_recusa_com_o_nome_do_arquivo(
        self, projeto_com_rodada, pasta_da_rodada
    ):
        """
        REGRESSÃO da 1.13.0. Um `.png` pela metade — a rodada interrompida, a
        nuvem que não terminou de sincronizar — derrubava o comando com o
        `UnrecognizedImageError` do `python-docx` e o relatório anterior fora do
        lugar. Agora é `RelatorioError`, que a CLI mostra num painel.
        """
        raiz = projeto_com_rodada()
        anterior = raiz / "Relatorio_00742_2026-09-01.docx"
        anterior.write_bytes(b"anterior")
        figura = next(pasta_da_rodada(raiz).glob("*.png"))
        figura.write_bytes(b"\x89PNG\r\n\x1a\n")

        with pytest.raises(RelatorioError) as erro:
            executar_relatorio(preparar_relatorio(raiz, agora=QUANDO))
        assert figura.name in str(erro.value)
        assert anterior.is_file()

    def test_a_rodada_arquivada_nao_e_a_que_o_comando_monta(self, projeto_com_rodada):
        """
        O `manifesto.ler` lê qualquer rodada arquivada, mas o caso de uso não
        existe: você relata a rodada vigente.
        """
        from flatcap.descritiva import executar_descritiva, preparar_descritiva

        raiz = projeto_com_rodada()
        executar_descritiva(
            preparar_descritiva(raiz, agora=datetime(2026, 9, 10, 9, 0))
        )
        plano = preparar_relatorio(raiz, agora=datetime(2026, 9, 10, 9, 5))
        assert plano.relatorio.manifesto.gerado_em == datetime(2026, 9, 10, 9, 0)

    def test_o_relatorio_nao_fala_com_o_redcap(self, projeto_com_rodada, env_valido):
        assert preparar_relatorio(projeto_com_rodada(), agora=QUANDO).secoes


# ── O projeto fica pronto ───────────────────────────────────────────────────


class TestStatusPronto:
    """
    Escrito o documento, a ficha passa para `pronto` — é o que o `flatcap status`
    mostra, e o que tira dele o ATRASADO. O documento vem primeiro: o status que não
    se escreve vira aviso, e não desfaz o relatório.
    """

    def test_o_relatorio_passa_o_projeto_para_pronto(self, projeto_com_rodada):
        raiz = projeto_com_rodada()
        resultado = executar_relatorio(preparar_relatorio(raiz, agora=QUANDO))
        assert ler_ficha(raiz).status == "pronto"
        assert resultado.status_trocado
        assert "Status de `em andamento` para `pronto`." in linhas_do_historico(raiz)[-1]

    def test_a_simulacao_decide_e_nao_escreve(self, projeto_com_rodada):
        raiz = projeto_com_rodada()
        antes = (raiz / "projeto.yaml").read_bytes()
        plano = preparar_relatorio(raiz, agora=QUANDO)
        assert plano.muda_o_status
        assert (raiz / "projeto.yaml").read_bytes() == antes

    def test_a_ficha_ja_pronta_nao_e_reescrita(self, projeto_com_rodada):
        """
        `Pronto` é o `pronto` da lista: a ficha não muda, e o histórico não diz que
        mudou.
        """
        raiz = projeto_com_rodada()
        caminho = raiz / "projeto.yaml"
        caminho.write_text(
            caminho.read_text(encoding="utf-8").replace(
                "status: em andamento", "status: Pronto"
            ),
            encoding="utf-8",
            newline="\n",
        )
        antes = caminho.read_bytes()
        plano = preparar_relatorio(raiz, agora=QUANDO)
        assert not plano.muda_o_status
        resultado = executar_relatorio(plano)
        assert caminho.read_bytes() == antes
        assert not resultado.status_trocado
        assert "Status" not in linhas_do_historico(raiz)[-1]

    def test_o_finalizado_volta_para_pronto(self, projeto_com_rodada):
        """
        Um relatório novo é uma entrega nova: o projeto volta ao painel, como
        `pronto`, e o terminal e o histórico dizem que voltou.
        """
        raiz = projeto_com_rodada()
        caminho = raiz / "projeto.yaml"
        caminho.write_text(
            caminho.read_text(encoding="utf-8").replace(
                "status: em andamento", "status: finalizado"
            ),
            encoding="utf-8",
            newline="\n",
        )
        executar_relatorio(preparar_relatorio(raiz, agora=QUANDO))
        assert ler_ficha(raiz).status == "pronto"

    def test_o_status_que_nao_se_escreve_vira_aviso_e_o_relatorio_fica(
        self, projeto_com_rodada, monkeypatch
    ):
        import flatcap.relatorio as relatorio


        def falhar(*_a, **_k):
            raise OSError("arquivo aberto noutro programa (simulado)")

        raiz = projeto_com_rodada()
        monkeypatch.setattr(relatorio, "definir_status", falhar)
        resultado = executar_relatorio(preparar_relatorio(raiz, agora=QUANDO))

        assert resultado.caminho.is_file()
        assert not resultado.status_trocado
        assert ler_ficha(raiz).status == "em andamento"
        (aviso,) = resultado.avisos
        assert "Escreva `status: pronto` à mão" in aviso
        assert "Status" not in linhas_do_historico(raiz)[-1]

    def test_a_falha_depois_do_status_devolve_a_ficha_como_estava(
        self, projeto_com_rodada, monkeypatch
    ):
        """
        Uma falha no meio desfaz o que já foi feito, e a ficha é uma das coisas
        feitas: ela volta ao texto que tinha, letra por letra — até o `\\r\\n` de uma
        ficha editada no Windows.
        """
        import flatcap.relatorio as relatorio

        raiz = projeto_com_rodada()
        caminho = raiz / "projeto.yaml"
        caminho.write_bytes(caminho.read_bytes().replace(b"\n", b"\r\n"))
        antes = caminho.read_bytes()

        def falhar(*_a, **_k):
            raise ValueError("falha que ninguém previu (simulada)")

        monkeypatch.setattr(relatorio, "anotar", falhar)
        with pytest.raises(ValueError):
            executar_relatorio(preparar_relatorio(raiz, agora=QUANDO))
        assert caminho.read_bytes() == antes
        assert not list(raiz.glob("Relatorio_*.docx"))


def test_o_manifesto_e_o_unico_insumo_alem_dos_csv(projeto_com_rodada, pasta_da_rodada):
    """
    Nem o banco, nem o `.xlsx`, nem o `perfil.md`. Apagar o banco do disco não
    impede o relatório de sair — ele só ganha um alerta.
    """
    raiz = projeto_com_rodada()
    (raiz / PASTA_DADOS / "00_redcap_2026-09-01_banco.csv").unlink()
    plano = preparar_relatorio(raiz, agora=QUANDO)
    assert (pasta_da_rodada(raiz) / ARQUIVO_MANIFESTO).is_file()
    assert plano.secoes
    assert "banco_ausente" in _codigos(plano)
