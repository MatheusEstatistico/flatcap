# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Versionamento dos bancos — Fase 3.

Três regras sustentam a cronologia, e cada uma tem um teste com esse nome: o
`00_redcap_*` nunca se move; o número do prefixo é o índice da versão e nunca se
repete; reenvio idêntico não vira versão.

E uma quarta coisa, que é o critério de pronto da fase: **dá para reconstruir a
cronologia sem depender da sua memória.** Isso não se prova imprimindo a ficha —
prova-se confrontando a ficha com o disco, que é o que a `linha_do_tempo` faz.
"""

from __future__ import annotations

import pytest

import bancos
from conftest import AGORA, linhas_do_historico, sha_e_tamanho
from flatcap.dados import (
    ORIGEM_PADRAO,
    SEQUENCIA_MAXIMA,
    ArquivoOrigemError,
    DadosError,
    VersaoDuplicadaError,
    executar_adicao,
    linha_do_tempo,
    preparar_adicao,
)
from flatcap.ficha import ler as ler_ficha
from flatcap.projeto import PASTA_ANALISES, PASTA_ANTIGAS, PASTA_DADOS


@pytest.fixture
def revisado(tmp_path):
    """
    Um arquivo revisado **fora** da pasta do projeto — o do e-mail, o da pasta
    de downloads, o do pen drive.
    """

    def criar(nome: str = "banco corrigido.csv", quadro=None):
        pasta = tmp_path / "downloads"
        pasta.mkdir(exist_ok=True)
        return bancos.csv_do_r(
            pasta / nome, bancos.completo() if quadro is None else quadro
        )

    return criar


# ── O arquivo de origem ─────────────────────────────────────────────────────


class TestConferirOrigem:
    """
    Quatro recusas, cada uma com o motivo. A última é a menos óbvia e a mais
    provável.
    """

    def test_arquivo_que_nao_existe(self, projeto_com_banco, root, tmp_path):
        projeto_com_banco()
        with pytest.raises(ArquivoOrigemError) as erro:
            preparar_adicao(root, "42", tmp_path / "nao_existe.csv")
        assert "aspas" in str(erro.value)

    def test_pasta_em_vez_de_arquivo(self, projeto_com_banco, root, tmp_path):
        projeto_com_banco()
        with pytest.raises(ArquivoOrigemError) as erro:
            preparar_adicao(root, "42", tmp_path)
        assert "um arquivo por vez" in str(erro.value)

    def test_arquivo_de_zero_bytes(self, projeto_com_banco, root, tmp_path):
        projeto_com_banco()
        vazio = tmp_path / "vazio.csv"
        vazio.write_bytes(b"")
        with pytest.raises(ArquivoOrigemError) as erro:
            preparar_adicao(root, "42", vazio)
        assert "download interrompido" in str(erro.value)

    def test_arquivo_ja_dentro_da_pasta_do_projeto(self, projeto_com_banco, root):
        """
        Registrar um arquivo que já está lá dentro criaria uma cópia dele com
        outro nome e duas entradas para a mesma versão.
        """
        raiz = projeto_com_banco()
        dentro = raiz / PASTA_DADOS / "00_redcap_2026-09-01_banco.csv"
        with pytest.raises(ArquivoOrigemError) as erro:
            preparar_adicao(root, "42", dentro)
        assert "mova-o para fora" in str(erro.value)


# ── As três regras da cronologia ────────────────────────────────────────────


class TestNumeracao:
    def test_a_primeira_revisao_e_01(self, projeto_com_banco, root, revisado):
        projeto_com_banco()
        plano = preparar_adicao(root, "42", revisado(), agora=AGORA)
        assert plano.sequencia == 1
        assert plano.destino.name.startswith("01_revisado_2026-09-09_")

    def test_o_numero_nunca_se_repete(self, projeto_com_banco, root, revisado):
        """
        Desvio deliberado do roteiro, que escrevia `01_revisado_` sempre: com o
        número fixo, duas versões diferentes levariam o mesmo prefixo e a ordem
        passaria a depender da data no nome — que empata quando o cliente
        reenvia duas vezes no mesmo dia.
        """
        projeto_com_banco()
        executar_adicao(preparar_adicao(root, "42", revisado("a.csv"), agora=AGORA))
        segundo = revisado("b.csv", bancos.com_coluna_constante())
        plano = preparar_adicao(root, "42", segundo, agora=AGORA)
        assert plano.sequencia == 2

    def test_um_arquivo_nn_no_disco_sem_registro_ocupa_o_numero(
        self, projeto_com_banco, root, revisado
    ):
        """
        Só na ficha bastaria se nada além do FlatCap tocasse na pasta — e a
        premissa do projeto é a contrária.
        """
        raiz = projeto_com_banco()
        (raiz / PASTA_DADOS / "03_revisado_2026-09-05_b.csv").write_text("x", encoding="utf-8")
        assert preparar_adicao(root, "42", revisado(), agora=AGORA).sequencia == 4

    def test_o_nome_original_e_preservado_e_sanitizado(
        self, projeto_com_banco, root, revisado
    ):
        projeto_com_banco()
        plano = preparar_adicao(root, "42", revisado("banco: revisão*final.csv"), agora=AGORA)
        assert ":" not in plano.destino.name
        assert "*" not in plano.destino.name
        assert "revisão" in plano.destino.name

    def test_o_limite_de_dois_digitos(self, projeto_com_banco, root, revisado):
        raiz = projeto_com_banco()
        (raiz / PASTA_DADOS / f"{SEQUENCIA_MAXIMA}_revisado_x.csv").write_text("x")
        with pytest.raises(DadosError) as erro:
            preparar_adicao(root, "42", revisado(), agora=AGORA)
        assert "por que houve tantas revisões" in str(erro.value)


class TestRotacao:
    def test_o_redcap_nunca_se_move(self, projeto_com_banco, root, revisado):
        raiz = projeto_com_banco()
        executar_adicao(preparar_adicao(root, "42", revisado(), agora=AGORA))
        assert (raiz / PASTA_DADOS / "00_redcap_2026-09-01_banco.csv").is_file()
        assert not (raiz / PASTA_ANTIGAS / "00_redcap_2026-09-01_banco.csv").exists()

    def test_a_versao_de_trabalho_anterior_vai_para_as_antigas(
        self, projeto_com_banco, root, revisado
    ):
        raiz = projeto_com_banco()
        executar_adicao(preparar_adicao(root, "42", revisado("a.csv"), agora=AGORA))
        primeiro = next((raiz / PASTA_DADOS).glob("01_*")).name
        executar_adicao(
            preparar_adicao(
                root, "42", revisado("b.csv", bancos.com_coluna_constante()), agora=AGORA
            )
        )
        assert (raiz / PASTA_ANTIGAS / primeiro).is_file()
        assert not (raiz / PASTA_DADOS / primeiro).exists()

    def test_arquivo_fora_da_convencao_nao_e_movido(self, projeto_com_banco, root, revisado):
        """
        Um `anotacoes.txt` que você deixou na pasta não é versão de banco, e não
        deve ser movido por um comando que você chamou para outra coisa.
        """
        raiz = projeto_com_banco()
        nota = raiz / PASTA_DADOS / "anotacoes.txt"
        nota.write_text("combinado na reunião", encoding="utf-8")
        executar_adicao(preparar_adicao(root, "42", revisado(), agora=AGORA))
        assert nota.is_file()


class TestDuplicata:
    def test_reenvio_identico_nao_vira_versao(self, projeto_com_banco, root, revisado):
        """
        É a resposta certa para "ele reenviou o mesmo arquivo" — comum quando o
        cliente responde ao e-mail antigo em vez de mandar a planilha corrigida.
        """
        projeto_com_banco()
        arquivo = revisado()
        executar_adicao(preparar_adicao(root, "42", arquivo, agora=AGORA))
        with pytest.raises(VersaoDuplicadaError) as erro:
            preparar_adicao(root, "42", arquivo, agora=AGORA)
        assert "byte a byte" in str(erro.value)

    def test_a_comparacao_e_por_conteudo_e_nao_por_nome(
        self, projeto_com_banco, root, revisado, tmp_path
    ):
        projeto_com_banco()
        arquivo = revisado("primeiro.csv")
        executar_adicao(preparar_adicao(root, "42", arquivo, agora=AGORA))
        outro = tmp_path / "downloads" / "com outro nome.csv"
        outro.write_bytes(arquivo.read_bytes())
        with pytest.raises(VersaoDuplicadaError):
            preparar_adicao(root, "42", outro, agora=AGORA)

    def test_o_erro_carrega_a_versao_que_ja_existia(self, projeto_com_banco, root, revisado):
        projeto_com_banco()
        arquivo = revisado()
        executar_adicao(preparar_adicao(root, "42", arquivo, agora=AGORA))
        with pytest.raises(VersaoDuplicadaError) as erro:
            preparar_adicao(root, "42", arquivo, agora=AGORA)
        assert erro.value.versao.arquivo.startswith("01_")


# ── Decidir e escrever ──────────────────────────────────────────────────────


class TestPrepararEExecutar:
    def test_preparar_nao_toca_no_disco(self, projeto_com_banco, root, revisado):
        raiz = projeto_com_banco()
        antes = sorted(p.name for p in (raiz / PASTA_DADOS).iterdir())
        preparar_adicao(root, "42", revisado(), agora=AGORA)
        assert sorted(p.name for p in (raiz / PASTA_DADOS).iterdir()) == antes

    def test_a_origem_e_copiada_e_nao_movida(self, projeto_com_banco, root, revisado):
        """
        O arquivo do cliente continua onde ele estava.
        """
        projeto_com_banco()
        arquivo = revisado()
        executar_adicao(preparar_adicao(root, "42", arquivo, agora=AGORA))
        assert arquivo.is_file()

    def test_a_copia_e_conferida_antes_de_o_sha_ir_para_a_ficha(
        self, projeto_com_banco, root, revisado, monkeypatch
    ):
        """
        Um `sha256` gravado sobre uma cópia truncada seria um recibo falso —
        pior do que recibo nenhum.
        """
        import flatcap.dados as modulo

        raiz = projeto_com_banco()
        original = modulo.shutil.copy2

        def copia_truncada(origem, destino, *args, **kwargs):
            original(origem, destino, *args, **kwargs)
            from pathlib import Path

            Path(destino).write_bytes(Path(destino).read_bytes()[:10])

        monkeypatch.setattr(modulo.shutil, "copy2", copia_truncada)
        with pytest.raises(DadosError) as erro:
            executar_adicao(preparar_adicao(root, "42", revisado(), agora=AGORA))
        assert "A cópia saiu diferente" in str(erro.value)
        assert not list((raiz / PASTA_DADOS).glob("01_*")), "o arquivo ruim ficou no disco"

    def test_a_ficha_ganha_a_entrada_com_os_cinco_campos(
        self, projeto_com_banco, root, revisado
    ):
        raiz = projeto_com_banco()
        arquivo = revisado()
        sha, tamanho = sha_e_tamanho(arquivo)
        executar_adicao(preparar_adicao(root, "42", arquivo, agora=AGORA))
        versao = ler_ficha(raiz).dados[-1]
        assert versao.sha256 == sha
        assert versao.tamanho_bytes == tamanho
        assert versao.origem == ORIGEM_PADRAO
        assert versao.data == AGORA.date()

    def test_escreve_uma_linha_no_historico(self, projeto_com_banco, root, revisado):
        raiz = projeto_com_banco()
        antes = len(linhas_do_historico(raiz))
        executar_adicao(preparar_adicao(root, "42", revisado(), agora=AGORA))
        assert len(linhas_do_historico(raiz)) == antes + 1

    def test_a_falha_no_meio_reverte_o_que_ja_foi_feito(
        self, projeto_com_banco, root, revisado, monkeypatch
    ):
        import flatcap.dados as modulo

        raiz = projeto_com_banco()
        executar_adicao(preparar_adicao(root, "42", revisado("a.csv"), agora=AGORA))
        antes = sorted(p.name for p in (raiz / PASTA_DADOS).iterdir())

        def falhar(*_a, **_k):
            raise OSError("disco cheio (simulado)")

        monkeypatch.setattr(modulo, "acrescentar_versao", falhar)
        with pytest.raises(OSError):
            executar_adicao(
                preparar_adicao(
                    root, "42", revisado("b.csv", bancos.com_coluna_constante()), agora=AGORA
                )
            )
        assert sorted(p.name for p in (raiz / PASTA_DADOS).iterdir()) == antes

    def test_o_comando_nao_fala_com_o_redcap(self, projeto_com_banco, root, revisado, env_valido):
        projeto_com_banco()
        assert preparar_adicao(root, "42", revisado(), agora=AGORA).sequencia == 1

    def test_aceita_matricula_alem_do_record_id(self, projeto_com_banco, root, revisado):
        projeto_com_banco()
        assert preparar_adicao(root, "00742", revisado(), agora=AGORA).sequencia == 1


# ── A linha do tempo ────────────────────────────────────────────────────────


class TestLinhaDoTempo:
    """
    O critério de pronto da fase. Ela não imprime a ficha — **confronta** a ficha
    com o disco. Uma ficha que afirma o que não está mais no disco é pior do que
    nenhuma ficha, porque parece informação.
    """

    def test_projeto_novo_confere(self, projeto_com_banco):
        tempo = linha_do_tempo(projeto_com_banco())
        assert len(tempo.itens) == 1
        assert tempo.integra
        assert tempo.itens[0].confere is True

    def test_ausente(self, projeto_com_banco):
        raiz = projeto_com_banco()
        (raiz / PASTA_DADOS / "00_redcap_2026-09-01_banco.csv").unlink()
        tempo = linha_do_tempo(raiz)
        assert len(tempo.ausentes) == 1
        assert not tempo.integra

    def test_alterado(self, projeto_com_banco):
        """
        O custo específico da escolha de proteger só o `00_redcap_*`: abrir a
        versão vigente no Excel e salvar invalida o `sha256` sem aviso nenhum. A
        releitura do hash é o que transforma "editei sem querer" em algo visível.
        """
        raiz = projeto_com_banco()
        alvo = raiz / PASTA_DADOS / "00_redcap_2026-09-01_banco.csv"
        alvo.write_text(alvo.read_text(encoding="utf-8") + "Ana;30\n", encoding="utf-8")
        tempo = linha_do_tempo(raiz)
        assert len(tempo.alterados) == 1

    def test_nao_registrado_em_dados_originais(self, projeto_com_banco):
        raiz = projeto_com_banco()
        bancos.csv_do_r(raiz / PASTA_DADOS / "mandado_por_email.csv")
        tempo = linha_do_tempo(raiz)
        assert [p.name for p in tempo.nao_registrados] == ["mandado_por_email.csv"]

    def test_rapido_nao_reconfere_o_conteudo(self, projeto_com_banco):
        raiz = projeto_com_banco()
        alvo = raiz / PASTA_DADOS / "00_redcap_2026-09-01_banco.csv"
        alvo.write_text("estragado", encoding="utf-8")
        tempo = linha_do_tempo(raiz, conferir=False)
        assert tempo.conferido is False
        assert tempo.itens[0].confere is None
        assert not tempo.alterados

    def test_o_relatorio_arquivado_nao_e_uma_versao_desconhecida_do_banco(
        self, projeto_com_rodada
    ):
        """
        REGRESSÃO — a Fase 6 quebrou o critério de pronto da Fase 3.

        A varredura pega **qualquer** arquivo de `2. Versões antigas/`, e a Fase
        6 passou a arquivar ali os `Relatorio_*.docx` de rodadas anteriores. Da
        segunda geração de relatório em diante, `flatcap dados listar` acusa o
        `.docx` como "arquivo na pasta que a ficha desconhece" e manda registrá-lo
        com `dados adicionar` — que o recusaria dizendo que documento de texto
        não é banco de dados.

        Dois efeitos, e o segundo é o pior: o conselho está errado, e a linha
        verde "Ficha e disco conferem" deixa de ser alcançável em qualquer
        projeto que já tenha regerado um relatório. Um diagnóstico que acusa
        sempre é um diagnóstico que se aprende a ignorar.

        O conserto reusa a regra que a própria `_rotacoes` já aplica: em
        `2. Versões antigas/`, só é candidato a versão o arquivo cujo nome segue
        a convenção `NN_`.
        """
        from datetime import datetime

        from flatcap.relatorio import executar_relatorio, preparar_relatorio

        raiz = projeto_com_rodada()
        executar_relatorio(preparar_relatorio(raiz, agora=datetime(2026, 9, 9, 10, 0)))
        executar_relatorio(preparar_relatorio(raiz, agora=datetime(2026, 9, 10, 10, 0)))

        tempo = linha_do_tempo(raiz)
        assert [p.name for p in tempo.nao_registrados] == []
        assert tempo.integra

    def test_a_rodada_arquivada_da_descritiva_tambem_nao_conta(self, projeto_com_rodada):
        """
        Esta já passa — a pasta arquivada é um diretório, e a varredura só olha
        arquivos. Fica no arquivo para que o conserto do teste acima não a
        quebre por tabela.
        """
        from datetime import datetime

        from flatcap.descritiva import executar_descritiva, preparar_descritiva

        raiz = projeto_com_rodada()
        executar_descritiva(preparar_descritiva(raiz, agora=datetime(2026, 9, 10, 9, 0)))
        assert (raiz / PASTA_ANTIGAS).is_dir()
        assert (raiz / PASTA_ANALISES).is_dir()
        assert [p.name for p in linha_do_tempo(raiz).nao_registrados] == []
