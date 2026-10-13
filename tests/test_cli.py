# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Os comandos — a fiação.

Esta camada não contém regra de negócio: ela lê argumentos, chama as camadas de
baixo, formata a saída e escolhe o código de saída do processo. O teste aqui é
sobre **essas quatro coisas**, e nada mais — quem testa "quais são as 10 mais
recentes" é o `test_modelo.py`, porque a regra mora lá.

Três invariantes atravessam o arquivo:

**Todo comando que escreve simula por padrão.** Sem `--sim`, nada no
disco muda. É a rede de proteção, e ela é conferida comando a comando.

**Erro previsto vira painel, não traceback.** Toda exceção declarada pelos
módulos é capturada; qualquer outra é bug e deve subir inteira.

**O código de saída é escolhido.** Recusa por juízo sai com 1; "nada para
fazer" sai com 0, para não quebrar script.
"""

from __future__ import annotations

import shutil

import pytest
from typer.testing import CliRunner

import bancos
from conftest import (
    MATRICULA,
    RECORD_ID,
    acrescentar_a_ficha,
    escrever_analises,
    marcar_numericas,
)
from flatcap import __version__
from flatcap.cli import app
from flatcap.projeto import (
    ARQUIVO_PROJETO,
    PASTA_ANALISES,
    PASTA_ANTIGAS,
    PASTA_ASSOCIACAO,
    PASTA_COMPARACAO,
    PASTA_CORRELACAO,
    PASTA_CRUZAMENTO,
    PASTA_DESCRITIVA,
)

runner = CliRunner()


@pytest.fixture
def rodar(env_valido, monkeypatch):
    """
    Roda um comando com o ambiente preenchido — e com token inválido, que é o
    que prova que os comandos das Fases 3 a 6 não tocam a rede.
    """

    def executar(*argumentos: str):
        return runner.invoke(app, list(argumentos), catch_exceptions=False)

    return executar


def _saida(resultado) -> str:
    """
    A saída sem as quebras que o `rich` insere para caber na largura do terminal.
    """
    return " ".join(resultado.output.split())


def _sem_moldura(resultado) -> str:
    """
    A saída sem as quebras **e sem a moldura dos painéis**.

    Uma frase que atravessa a quebra de linha dentro de um painel chega ao `_saida`
    com as duas bordas no meio — `a média de │ │ um código` —, e o teste falharia por
    causa da largura do terminal, e não do que o comando disse.
    """
    return " ".join(resultado.output.replace("│", " ").split())


# ── Opções globais ──────────────────────────────────────────────────────────


class TestGlobais:
    def test_version(self, rodar):
        resultado = rodar("--version")
        assert resultado.exit_code == 0
        assert __version__ in resultado.output

    def test_version_diz_a_licenca(self, rodar):
        """O aviso que a GPL pede, no formato dos programas GNU."""
        saida = _saida(rodar("--version"))
        assert "GPL-3.0-or-later" in saida
        assert "NÃO HÁ GARANTIA" in saida

    def test_sem_argumento_mostra_a_ajuda(self):
        resultado = runner.invoke(app, [])
        assert "doctor" in resultado.output and "relatorio" in resultado.output

    def test_configuracao_incompleta_vira_painel(self, monkeypatch, tmp_path):
        for chave in ("REDCAP_API_URL", "REDCAP_TOKEN", "FLATCAP_ROOT"):
            monkeypatch.delenv(chave, raising=False)
        monkeypatch.chdir(tmp_path)
        resultado = runner.invoke(app, ["listar"])
        assert resultado.exit_code == 1
        assert "Configuração" in resultado.output


# ── doctor ──────────────────────────────────────────────────────────────────


class TestDoctor:
    @pytest.fixture(autouse=True)
    def _sem_rede(self, monkeypatch):
        monkeypatch.setattr(
            "flatcap.cli.exportar_projeto",
            lambda *a, **k: {"project_title": "Assessoria", "project_id": "1234"},
        )

    def test_mostra_o_projeto_e_o_token_mascarado(self, rodar):
        resultado = rodar("doctor")
        assert resultado.exit_code == 0
        assert "Assessoria" in _saida(resultado)
        assert "0" * 32 not in resultado.output

    def test_diz_qual_implementacao_de_yaml_esta_carregada(self, rodar):
        assert "ruamel" in _saida(rodar("doctor")).lower()

    def test_biblioteca_faltando_sai_como_falha_e_nao_como_traceback(
        self, rodar, sem_modulo
    ):
        """
        Este é o comando que existe para responder "o que está errado?". Ele
        não pode morrer no meio do próprio diagnóstico. Escapou dos testes uma
        vez porque a máquina que os roda é a única em que ele nunca falha.
        """
        sem_modulo("matplotlib")
        resultado = rodar("doctor")
        assert resultado.exit_code == 1
        assert "FALHA" in resultado.output
        assert "Instalação incompleta" in _saida(resultado)

    def test_a_tabela_inteira_sai_antes_do_painel(self, rodar, sem_modulo):
        """
        Saber que a rede está de pé faz parte do diagnóstico mesmo quando falta
        biblioteca.
        """
        sem_modulo("matplotlib")
        saida = _saida(rodar("doctor"))
        assert saida.index("Conexão REDCap") < saida.index("Instalação incompleta")

    def test_a_mensagem_diz_o_nome_no_pip_e_nao_o_do_import(self, rodar, sem_modulo):
        """
        `import docx` vem do pacote `python-docx`, e quem lê "falta `docx`" no
        terminal instala outro pacote — que existe, e não é este.
        """
        sem_modulo("docx")
        saida = _saida(rodar("doctor"))
        assert "python-docx" in saida

    def test_a_dica_do_uv_reinstala_da_origem_e_nao_do_pypi(self, rodar, sem_modulo):
        """
        REGRESSÃO — a dica que procurava o FlatCap no PyPI.

        O `uv tool install --reinstall flatcap` resolve o nome no índice, e o FlatCap
        não está lá: numa instalação feita por `git+https://…`, o uv responde que o
        pacote não existe — e, se alguém registrar o nome, instala o pacote dessa
        pessoa. O `uv tool upgrade --reinstall flatcap` reinstala da origem guardada na
        instalação. Os dois foram conferidos com o uv contra um clone.
        """
        sem_modulo("matplotlib")
        saida = _sem_moldura(rodar("doctor"))
        assert "uv tool upgrade --reinstall flatcap" in saida
        assert "uv tool install --reinstall" not in saida

    def test_criar_env_escreve_o_da_conta_e_nao_sobrescreve(self, rodar):
        from flatcap.config import arquivo_env_da_conta

        primeira = rodar("doctor", "--criar-env")
        assert primeira.exit_code == 0
        assert arquivo_env_da_conta().is_file()
        assert ".env criado" in _saida(primeira)

        segunda = rodar("doctor", "--criar-env")
        assert segunda.exit_code == 0
        assert "já existe" in _sem_moldura(segunda)

    def test_falha_de_conexao_vira_painel(self, rodar, monkeypatch):
        from flatcap.redcap import RedcapError

        def falhar(*_a, **_k):
            raise RedcapError("Não foi possível chegar ao servidor")

        monkeypatch.setattr("flatcap.cli.exportar_projeto", falhar)
        resultado = rodar("doctor")
        assert resultado.exit_code == 1
        assert "Conexão com o REDCap" in _saida(resultado)


# ── listar ──────────────────────────────────────────────────────────────────


class TestListar:
    @pytest.fixture
    def com_registros(self, monkeypatch, registros):
        monkeypatch.setattr("flatcap.cli.exportar_registros", lambda *a, **k: registros)
        return registros

    def test_a_tabela_traz_as_seis_colunas(self, rodar, com_registros):
        saida = _saida(rodar("listar"))
        for coluna in ("id", "Tipo", "Matrícula", "Nome", "Anexo", "Pasta local"):
            assert coluna in saida

    def test_o_resumo_conta_o_que_exige_atencao(self, rodar, com_registros):
        saida = _saida(rodar("listar"))
        assert "solicitações" in saida
        assert "sem pasta local" in saida

    def test_a_coluna_de_pasta_local_bate_o_redcap_contra_o_disco(
        self, rodar, com_registros, projeto_vazio
    ):
        saida = _saida(rodar("listar"))
        assert projeto_vazio.name.split(" - ")[0] in saida
        assert "6 sem pasta local" in saida, "a coluna precisa refletir o disco"

    def test_n_corta_pelas_mais_recentes_sem_reordenar(self, rodar, com_registros):
        saida = _saida(rodar("listar", "-n", "2"))
        assert "2 de 7" in saida
        assert "45" in saida

    def test_o_resumo_se_le_numa_linha(self, rodar, com_registros):
        """
        REGRESSÃO da 1.13.0: `7 solicitações. . 6 sem pasta local. . 2 sem
        anexo`, e a dica mandava rodar `-n` para ver todas — que é justamente o
        que corta.
        """
        saida = _saida(rodar("listar", "-n", "2"))
        assert ". ." not in saida
        assert "Rode sem `-n` para ver as 7" in saida

    def test_uma_solicitacao_no_singular(self, rodar, monkeypatch, registros):
        monkeypatch.setattr("flatcap.cli.exportar_registros", lambda *a, **k: registros[:1])
        saida = _saida(rodar("listar"))
        assert "1 solicitação" in saida
        assert "solicitações" not in saida

    def test_n_zero_e_recusado_pelo_typer(self, rodar, com_registros):
        assert rodar("listar", "-n", "0").exit_code != 0

    def test_sem_solicitacao_nenhuma(self, rodar, monkeypatch):
        monkeypatch.setattr("flatcap.cli.exportar_registros", lambda *a, **k: [])
        assert "Nenhuma nova solicitação" in rodar("listar").output

    def test_o_corte_vem_antes_da_conferencia_de_anexos(
        self, rodar, com_registros, monkeypatch
    ):
        """
        A conferência custa um download por registro. Combinar `-n 10` com ela
        num projeto de 200 registros passa de 200 chamadas para 10.
        """
        conferidos: list[str] = []

        def contar(_cfg, record_id, _campo):
            conferidos.append(record_id)
            return False

        monkeypatch.setattr("flatcap.cli.tem_arquivo", contar)
        rodar("listar", "-n", "2", "--conferir-anexos")
        assert len(conferidos) <= 2

    def test_nome_com_colchete_nao_vira_marcacao_do_rich(self, rodar, monkeypatch):
        monkeypatch.setattr(
            "flatcap.cli.exportar_registros",
            lambda *a, **k: [
                {"record_id": "1", "intro": "1", "matricula1": "1", "prof1": "Ana [bold]"}
            ],
        )
        assert "[bold]" in _saida(rodar("listar"))


# ── novo ────────────────────────────────────────────────────────────────────


class TestNovo:
    @pytest.fixture
    def com_redcap(self, monkeypatch, registros):
        from flatcap.redcap import ArquivoRedcap

        monkeypatch.setattr(
            "flatcap.projeto.exportar_registros",
            lambda cfg, fields=None, records=None: [
                r for r in registros if r["record_id"] in (records or [])
            ],
        )
        monkeypatch.setattr(
            "flatcap.projeto.exportar_arquivo",
            lambda *a, **k: ArquivoRedcap("banco.xlsx", b"PK\x03\x04", ""),
        )

    def test_simula_por_padrao(self, rodar, com_redcap, root):
        resultado = rodar("novo", "40")
        assert resultado.exit_code == 0
        assert "Simulação" in _saida(resultado)
        assert list(root.iterdir()) == []

    def test_a_arvore_desenha_o_que_seria_criado(self, rodar, com_redcap):
        saida = _saida(rodar("novo", "40"))
        assert "1. Dados originais" in saida
        assert "00_redcap_" in saida
        assert "somente leitura" in saida

    def test_com_sim_cria(self, rodar, com_redcap, root):
        resultado = rodar("novo", "40", "--sim")
        assert resultado.exit_code == 0
        projeto = root / "00740 - Ana Cláudia Menezes" / "Projeto 040"
        assert (projeto / ARQUIVO_PROJETO).is_file()

    def test_registro_sem_anexo_avisa_e_cria_assim_mesmo(
        self, rodar, com_redcap, monkeypatch, root
    ):
        from flatcap.redcap import ArquivoAusenteError

        def sem_anexo(*_a, **_k):
            raise ArquivoAusenteError("sem anexo")

        monkeypatch.setattr("flatcap.projeto.exportar_arquivo", sem_anexo)
        resultado = rodar("novo", "42", "--sim")
        assert resultado.exit_code == 0
        assert "não tem anexo" in _saida(resultado)

    def test_pasta_ja_existente_sai_com_zero(self, rodar, com_redcap, root):
        """
        Idempotência que serve para script: encadear `novo` sobre a saída do
        `listar` não pode quebrar porque um dos projetos já existe.
        """
        (root / "00740 - Ana Cláudia Menezes" / "Projeto 040").mkdir(parents=True)
        resultado = rodar("novo", "40")
        assert resultado.exit_code == 0
        assert "Nada para fazer" in _saida(resultado)

    def test_cadastro_incompleto_sai_com_um(self, rodar, com_redcap):
        """
        Sem matrícula ou sem nome, a pasta sairia com um nome que você teria de
        corrigir à mão — e o `listar` deixaria de reencontrá-la.
        """
        resultado = rodar("novo", "44")
        assert resultado.exit_code == 1
        assert "Solicitação" in _saida(resultado)

    def test_registro_inexistente_sai_com_um(self, rodar, com_redcap):
        assert rodar("novo", "999").exit_code == 1


# ── dados ───────────────────────────────────────────────────────────────────


class TestDados:
    @pytest.fixture
    def revisado(self, tmp_path):
        pasta = tmp_path / "downloads"
        pasta.mkdir(exist_ok=True)
        return bancos.csv_do_r(pasta / "corrigido.csv", bancos.com_coluna_constante())

    def test_adicionar_simula_por_padrao(self, rodar, projeto_com_banco, revisado):
        raiz = projeto_com_banco()
        antes = sorted(p.name for p in raiz.rglob("*"))
        resultado = rodar("dados", "adicionar", RECORD_ID, str(revisado))
        assert "Simulação" in _saida(resultado)
        assert sorted(p.name for p in raiz.rglob("*")) == antes

    def test_adicionar_com_sim(self, rodar, projeto_com_banco, revisado):
        projeto_com_banco()
        resultado = rodar("dados", "adicionar", MATRICULA, str(revisado), "--sim")
        assert resultado.exit_code == 0
        assert "Versão 01 registrada" in _saida(resultado)

    def test_reenvio_identico_sai_com_zero(self, rodar, projeto_com_banco, revisado):
        projeto_com_banco()
        rodar("dados", "adicionar", RECORD_ID, str(revisado), "--sim")
        resultado = rodar("dados", "adicionar", RECORD_ID, str(revisado))
        assert resultado.exit_code == 0
        assert "Nada para fazer" in _saida(resultado)

    def test_arquivo_inexistente_sai_com_um(self, rodar, projeto_com_banco, tmp_path):
        projeto_com_banco()
        resultado = rodar("dados", "adicionar", RECORD_ID, str(tmp_path / "x.csv"))
        assert resultado.exit_code == 1
        assert "Arquivo de origem" in _saida(resultado)

    def test_listar_mostra_a_cronologia(self, rodar, projeto_com_banco):
        projeto_com_banco()
        saida = _saida(rodar("dados", "listar", RECORD_ID))
        assert "Integridade" in saida
        assert "confere" in saida

    def test_listar_aponta_o_alterado_em_vermelho(self, rodar, projeto_com_banco):
        from flatcap.projeto import PASTA_DADOS

        raiz = projeto_com_banco()
        alvo = raiz / PASTA_DADOS / "00_redcap_2026-09-01_banco.csv"
        alvo.write_text("estragado", encoding="utf-8")
        saida = _saida(rodar("dados", "listar", RECORD_ID))
        assert "ALTERADO" in saida

    def test_rapido_nao_reconfere(self, rodar, projeto_com_banco):
        projeto_com_banco()
        saida = _saida(rodar("dados", "listar", RECORD_ID, "--rapido"))
        assert "não foi conferido" in saida

    def test_projeto_inexistente_sai_com_um(self, rodar, projeto_com_banco):
        projeto_com_banco()
        resultado = rodar("dados", "listar", "99999")
        assert resultado.exit_code == 1
        assert "Projeto" in _saida(resultado)


# ── perfil, descritiva, relatorio, template ─────────────────────────────────


class TestPerfil:
    def test_simula_por_padrao(self, rodar, projeto_com_banco):
        raiz = projeto_com_banco()
        resultado = rodar("perfil", RECORD_ID)
        assert resultado.exit_code == 0
        assert not (raiz / "perfil.md").exists()

    def test_com_sim_escreve_os_dois(self, rodar, projeto_com_banco):
        raiz = projeto_com_banco()
        assert rodar("perfil", RECORD_ID, "--sim").exit_code == 0
        assert (raiz / "perfil.md").is_file()
        assert (raiz / "dicionario.csv").is_file()

    def test_avisa_para_revisar_o_tipo_na_primeira_vez(self, rodar, projeto_com_banco):
        projeto_com_banco()
        assert "Revise a coluna" in _saida(rodar("perfil", RECORD_ID, "--sim"))

    def test_projeto_sem_banco_sai_com_um(self, rodar, projeto_vazio):
        resultado = rodar("perfil", RECORD_ID)
        assert resultado.exit_code == 1
        assert "Banco de dados" in _saida(resultado)

    def test_aba_escolhe_a_planilha(self, rodar, projeto_com_banco, tmp_path):
        raiz = projeto_com_banco()
        from conftest import escrever_ficha, sha_e_tamanho
        from flatcap.projeto import PASTA_DADOS

        alvo = raiz / PASTA_DADOS / "00_redcap_2026-09-01_banco.xlsx"
        bancos.xlsx_com_duas_abas(alvo)
        (raiz / PASTA_DADOS / "00_redcap_2026-09-01_banco.csv").unlink()
        sha, tamanho = sha_e_tamanho(alvo)
        escrever_ficha(
            raiz,
            dados=[
                {"arquivo": alvo.name, "origem": "redcap", "sha256": sha,
                 "tamanho_bytes": tamanho, "data": "2026-09-01"}
            ],
        )
        assert "Dicionário" in _saida(rodar("perfil", RECORD_ID, "--aba", "Dicionário"))


class TestDescritiva:
    def test_simula_por_padrao(self, rodar, projeto_com_banco):
        raiz = projeto_com_banco()
        rodar("perfil", RECORD_ID, "--sim")
        resultado = rodar("descritiva", RECORD_ID)
        assert resultado.exit_code == 0
        assert not (raiz / PASTA_ANALISES / PASTA_DESCRITIVA).exists()

    def test_com_sim_escreve_a_pasta(self, rodar, projeto_com_banco):
        raiz = projeto_com_banco()
        rodar("perfil", RECORD_ID, "--sim")
        assert rodar("descritiva", RECORD_ID, "--sim").exit_code == 0
        assert (raiz / PASTA_ANALISES / PASTA_DESCRITIVA / "manifesto.json").is_file()

    def test_a_tabela_diz_de_qual_variavel_sai_cada_arquivo(self, rodar, projeto_com_banco):
        projeto_com_banco()
        rodar("perfil", RECORD_ID, "--sim")
        saida = _saida(rodar("descritiva", RECORD_ID))
        assert "freq_sexo.csv" in saida

    def test_sem_graficos(self, rodar, projeto_com_banco):
        raiz = projeto_com_banco()
        rodar("perfil", RECORD_ID, "--sim")
        rodar("descritiva", RECORD_ID, "--sem-graficos", "--sim")
        pasta = raiz / PASTA_ANALISES / PASTA_DESCRITIVA
        assert not list(pasta.glob("*.png"))

    def test_numerica_como_texto_sai_com_um(self, rodar, projeto_com_banco):
        projeto_com_banco(bancos.com_virgula_decimal())
        rodar("perfil", RECORD_ID, "--sim")
        # o perfil sugere `numerica` para a coluna de vírgula decimal
        resultado = rodar("descritiva", RECORD_ID)
        assert resultado.exit_code == 1
        assert "Descritiva" in _saida(resultado)

    def test_sem_dicionario_sai_com_um(self, rodar, projeto_com_banco):
        projeto_com_banco()
        resultado = rodar("descritiva", RECORD_ID)
        assert resultado.exit_code == 1
        assert "flatcap perfil" in _saida(resultado)

    def test_regerar_avisa_que_arquivou(self, rodar, projeto_com_banco):
        projeto_com_banco()
        rodar("perfil", RECORD_ID, "--sim")
        rodar("descritiva", RECORD_ID, "--sim")
        saida = _saida(rodar("descritiva", RECORD_ID, "--sim"))
        assert PASTA_ANTIGAS in saida


class TestCruzamento:
    BLOCO = "cruzamento:\n  - [sexo, escolaridade]\n"

    def test_simula_por_padrao_e_mostra_a_tabela(self, rodar, projeto_com_rodada):
        """
        A simulação existe para ler o que vai para o documento antes de escrever:
        a tabela sai inteira no terminal, com as mesmas células do `.csv`.
        """
        raiz = projeto_com_rodada()
        acrescentar_a_ficha(raiz, self.BLOCO)
        resultado = rodar("cruzamento", RECORD_ID)
        assert resultado.exit_code == 0
        assert not (raiz / PASTA_ANALISES / PASTA_CRUZAMENTO).exists()
        saida = _saida(resultado)
        assert "sexo × escolaridade" in saida
        assert "Feminino" in saida and "(sem informação)" in saida
        assert "Simulação" in saida

    def test_com_sim_escreve_a_pasta(self, rodar, projeto_com_rodada):
        raiz = projeto_com_rodada()
        acrescentar_a_ficha(raiz, self.BLOCO)
        assert rodar("cruzamento", RECORD_ID, "--sim").exit_code == 0
        pasta = raiz / PASTA_ANALISES / PASTA_CRUZAMENTO
        assert (pasta / "cruz_sexo_x_escolaridade.csv").is_file()
        assert (pasta / "manifesto.json").is_file()

    def test_sem_a_lista_sai_com_um_e_ensina_a_escrever(self, rodar, projeto_com_rodada):
        """
        O par do exemplo tem colchete, e colchete é marcação para o `rich`. A
        mensagem que ensina a escrever a lista não pode chegar sem ela.
        """
        projeto_com_rodada()
        resultado = rodar("cruzamento", RECORD_ID)
        assert resultado.exit_code == 1
        saida = _saida(resultado)
        assert "Cruzamento" in saida
        assert "- [sexo, escolaridade]" in saida

    def test_par_com_numerica_sai_com_um(self, rodar, projeto_com_rodada):
        raiz = projeto_com_rodada()
        acrescentar_a_ficha(raiz, "cruzamento:\n  - [sexo, idade]\n")
        resultado = rodar("cruzamento", RECORD_ID)
        assert resultado.exit_code == 1
        assert "`idade` está marcada `numerica`" in _saida(resultado)

    def test_rotulo_com_colchete_nao_vira_marcacao_do_rich(self, rodar, projeto_com_rodada):
        raiz = projeto_com_rodada()
        dicionario = raiz / "dicionario.csv"
        dicionario.write_text(
            dicionario.read_text(encoding="utf-8-sig").replace(
                "\nsexo;sexo;", "\nsexo;Sexo [autodeclarado];"
            ),
            encoding="utf-8-sig",
        )
        acrescentar_a_ficha(raiz, self.BLOCO)
        assert "Sexo [autodeclarado] × escolaridade" in _saida(rodar("cruzamento", RECORD_ID))

    def test_regerar_avisa_que_arquivou(self, rodar, projeto_com_rodada):
        raiz = projeto_com_rodada()
        acrescentar_a_ficha(raiz, self.BLOCO)
        rodar("cruzamento", RECORD_ID, "--sim")
        saida = _saida(rodar("cruzamento", RECORD_ID, "--sim"))
        assert PASTA_ANTIGAS in saida


class TestAssociacao:
    BLOCO = "associacao:\n  - [sexo, escolaridade]\n"

    def test_simula_por_padrao_e_mostra_a_tabela_e_a_escolha(self, rodar, projeto_com_rodada):
        """
        A simulação mostra a tabela que vai para o documento **e** por que cada par
        foi para o teste em que foi — é nela que a escolha se confere.
        """
        raiz = projeto_com_rodada()
        acrescentar_a_ficha(raiz, self.BLOCO)
        resultado = rodar("associacao", RECORD_ID)
        assert resultado.exit_code == 0
        assert not (raiz / PASTA_ANALISES / PASTA_ASSOCIACAO).exists()
        saida = _saida(resultado)
        assert "Exato de Fisher" in saida
        assert "V de Cramér" in saida
        assert "Escolha do teste (regra de Cochran)" in saida
        assert "sexo × escolaridade: 2×3, n = 24" in saida
        assert "Simulação" in saida

    def test_com_sim_escreve_a_pasta(self, rodar, projeto_com_rodada):
        raiz = projeto_com_rodada()
        acrescentar_a_ficha(raiz, self.BLOCO)
        assert rodar("associacao", RECORD_ID, "--sim").exit_code == 0
        pasta = raiz / PASTA_ANALISES / PASTA_ASSOCIACAO
        assert (pasta / "associacao.csv").is_file()
        assert (pasta / "manifesto.json").is_file()

    def test_sem_a_lista_sai_com_um_e_ensina_as_duas_formas(self, rodar, projeto_com_rodada):
        projeto_com_rodada()
        resultado = rodar("associacao", RECORD_ID)
        assert resultado.exit_code == 1
        saida = _saida(resultado)
        assert "Associação" in saida
        assert "- [sexo, desfecho]" in saida
        assert "- desfecho: [sexo, escolaridade, tabagismo]" in saida

    def test_o_help_mostra_as_duas_formas(self):
        """O colchete é marcação para o `rich`: sem o escape, o exemplo some."""
        saida = _saida(runner.invoke(app, ["associacao", "--help"]))
        assert "- [sexo, desfecho]" in saida
        assert "- desfecho: [sexo, escolaridade, tabagismo]" in saida

    def test_par_com_numerica_sai_com_um(self, rodar, projeto_com_rodada):
        raiz = projeto_com_rodada()
        acrescentar_a_ficha(raiz, "associacao:\n  - [sexo, idade]\n")
        resultado = rodar("associacao", RECORD_ID)
        assert resultado.exit_code == 1
        assert "`idade` está marcada `numerica`" in _saida(resultado)

    def test_regerar_avisa_que_arquivou(self, rodar, projeto_com_rodada):
        raiz = projeto_com_rodada()
        acrescentar_a_ficha(raiz, self.BLOCO)
        rodar("associacao", RECORD_ID, "--sim")
        saida = _saida(rodar("associacao", RECORD_ID, "--sim"))
        assert PASTA_ANTIGAS in saida


class TestCorrelacao:
    BLOCO = "correlacao:\n  - [idade, imc]\n"

    def test_simula_por_padrao_e_mostra_a_tabela_e_a_escolha(self, rodar, projeto_com_rodada):
        """
        A simulação mostra a tabela que vai para o documento **e** por que cada par
        foi para o método em que foi — é nela que a escolha se confere.
        """
        raiz = projeto_com_rodada()
        acrescentar_a_ficha(raiz, self.BLOCO)
        resultado = rodar("correlacao", RECORD_ID)
        assert resultado.exit_code == 0
        assert not (raiz / PASTA_ANALISES / PASTA_CORRELACAO).exists()
        saida = _saida(resultado)
        assert "Pearson" in saida and "IC 95%" in saida
        assert "Escolha do método (regra dos pressupostos)" in saida
        assert "idade × imc: n = 24; o Shapiro-Wilk não rejeita a normal" in saida
        assert "1 dispersão(ões) .png" in saida
        assert "Simulação" in saida

    def test_com_sim_escreve_a_pasta(self, rodar, projeto_com_rodada):
        raiz = projeto_com_rodada()
        acrescentar_a_ficha(raiz, self.BLOCO)
        assert rodar("correlacao", RECORD_ID, "--sim").exit_code == 0
        pasta = raiz / PASTA_ANALISES / PASTA_CORRELACAO
        assert (pasta / "correlacao.csv").is_file()
        assert (pasta / "disp_idade_x_imc.png").is_file()
        assert (pasta / "manifesto.json").is_file()

    def test_sem_graficos_nao_desenha(self, rodar, projeto_com_rodada):
        raiz = projeto_com_rodada()
        acrescentar_a_ficha(raiz, self.BLOCO)
        assert rodar("correlacao", RECORD_ID, "--sem-graficos", "--sim").exit_code == 0
        assert not list((raiz / PASTA_ANALISES / PASTA_CORRELACAO).glob("*.png"))

    def test_sem_a_lista_sai_com_um_e_ensina_as_tres_formas(self, rodar, projeto_com_rodada):
        projeto_com_rodada()
        resultado = rodar("correlacao", RECORD_ID)
        assert resultado.exit_code == 1
        saida = _saida(resultado)
        assert "Correlação" in saida
        assert "- [idade, imc]" in saida
        assert "- [dor, ansiedade, kendall]" in saida

    def test_o_help_mostra_as_tres_formas(self):
        """O colchete é marcação para o `rich`: sem o escape, o exemplo some."""
        saida = _saida(runner.invoke(app, ["correlacao", "--help"]))
        assert "- [idade, imc]" in saida
        assert "- idade: [pressao, colesterol]" in saida
        assert "- [dor, ansiedade, kendall]" in saida

    def test_categorica_em_texto_sai_com_um(self, rodar, projeto_com_rodada):
        raiz = projeto_com_rodada()
        acrescentar_a_ficha(raiz, "correlacao:\n  - [escolaridade, idade]\n")
        resultado = rodar("correlacao", RECORD_ID)
        assert resultado.exit_code == 1
        saida = _saida(resultado)
        assert "Correlação" in saida
        assert "chegaram em texto" in saida

    def test_o_metodo_contra_a_regra_aparece_na_simulacao(self, rodar, projeto_com_rodada):
        raiz = projeto_com_rodada()
        acrescentar_a_ficha(raiz, "correlacao:\n  - [idade, imc, kendall]\n")
        saida = _saida(rodar("correlacao", RECORD_ID))
        assert "Kendall escrito na ficha" in saida
        assert "contra a regra — ela escolheria Pearson" in saida
        assert "1 com o método escrito na ficha" in saida

    def test_regerar_avisa_que_arquivou(self, rodar, projeto_com_rodada):
        raiz = projeto_com_rodada()
        acrescentar_a_ficha(raiz, self.BLOCO)
        rodar("correlacao", RECORD_ID, "--sem-graficos", "--sim")
        saida = _saida(rodar("correlacao", RECORD_ID, "--sem-graficos", "--sim"))
        assert PASTA_ANTIGAS in saida


class TestComparacao:
    BLOCO = "comparacao:\n  - [imc, 25]\n"

    def test_simula_por_padrao_e_mostra_a_tabela_e_a_escolha(self, rodar, projeto_com_rodada):
        """
        A simulação mostra a tabela que vai para o documento **e** por que cada item
        foi para o teste em que foi — é nela que a escolha se confere.
        """
        raiz = projeto_com_rodada()
        acrescentar_a_ficha(raiz, self.BLOCO)
        resultado = rodar("comparacao", RECORD_ID)
        assert resultado.exit_code == 0
        assert not (raiz / PASTA_ANALISES / PASTA_COMPARACAO).exists()
        saida = _saida(resultado)
        assert "Escolha do teste (regra dos pressupostos)" in saida
        assert "imc: n = 24; o Shapiro-Wilk não rejeita a normal" in saida
        assert "→ t de Student (t =" in saida
        assert "uma_amostra.csv" in saida
        assert "Simulação" in saida

    def test_com_sim_escreve_a_pasta(self, rodar, projeto_com_rodada):
        raiz = projeto_com_rodada()
        acrescentar_a_ficha(raiz, self.BLOCO)
        assert rodar("comparacao", RECORD_ID, "--sim").exit_code == 0
        pasta = raiz / PASTA_ANALISES / PASTA_COMPARACAO
        assert (pasta / "uma_amostra.csv").is_file()
        assert (pasta / "manifesto.json").is_file()

    def test_sem_a_lista_sai_com_um_e_ensina_a_forma(self, rodar, projeto_com_rodada):
        projeto_com_rodada()
        resultado = rodar("comparacao", RECORD_ID)
        assert resultado.exit_code == 1
        saida = _saida(resultado)
        assert "Comparação" in saida
        assert "- [imc, 25]" in saida
        assert "- [pas, 120, t]" in saida

    def test_o_help_mostra_a_forma(self):
        """O colchete é marcação para o `rich`: sem o escape, o exemplo some."""
        saida = _saida(runner.invoke(app, ["comparacao", "--help"]))
        assert "- [imc, 25]" in saida
        assert "- [pas, 120, t]" in saida
        assert "- [imc, sexo]" in saida
        assert "- repetidas: [pas_0, pas_1, pas_2]" in saida

    def test_a_virgula_decimal_sai_com_um_e_ensina_o_numero(self, rodar, projeto_com_rodada):
        raiz = projeto_com_rodada()
        acrescentar_a_ficha(raiz, "comparacao:\n  - [imc, 24,9]\n")
        resultado = rodar("comparacao", RECORD_ID)
        assert resultado.exit_code == 1
        assert "`[imc, 24.9]`" in _saida(resultado)

    def test_categorica_sai_com_um(self, rodar, projeto_com_rodada):
        raiz = projeto_com_rodada()
        acrescentar_a_ficha(raiz, "comparacao:\n  - [sexo, 1]\n")
        resultado = rodar("comparacao", RECORD_ID)
        assert resultado.exit_code == 1
        assert "a média de um código não é uma média" in _sem_moldura(resultado)

    def test_o_wilcoxon_e_o_t_contra_a_regra_aparecem_na_simulacao(
        self, rodar, projeto_com_rodada
    ):
        """
        A renda rejeita a normal: a regra vai para o Wilcoxon, e o t escrito no item
        roda contra ela, com a frase que diz o que ela faria.
        """
        raiz = projeto_com_rodada(bancos.para_comparar())
        acrescentar_a_ficha(raiz, "comparacao:\n  - [renda, 2500]\n  - [renda, 3000, t]\n")
        saida = _saida(rodar("comparacao", RECORD_ID))
        assert (
            "o Shapiro-Wilk rejeita a normal (p < 0,001) → Wilcoxon (V = 1080; p aproximado "
            "pela normal, com correção de continuidade, porque há 50 valores ou mais)."
        ) in saida
        assert "contra a regra — ela escolheria Wilcoxon" in saida
        assert "sem teste" not in saida
        assert "2 testes; 1 com o método escrito na ficha" in saida

    def test_os_testes_de_postos_escritos_entre_grupos(self, rodar, projeto_com_rodada):
        """
        O Mann-Whitney e o Kruskal-Wallis escritos no item: a simulação diz o W e o
        qui-quadrado, e com `--sim` as duas tabelas saem com a mediana e os quartis.
        """
        raiz = projeto_com_rodada()
        acrescentar_a_ficha(
            raiz,
            "comparacao:\n  - [imc, sexo, mannwhitney]\n  - [idade, escolaridade, kruskal]\n",
        )
        saida = _saida(rodar("comparacao", RECORD_ID))
        assert "Mann-Whitney escrito na ficha (W =" in saida
        assert "Kruskal-Wallis escrito na ficha (χ² =" in saida
        assert "2 testes; 2 com o método escrito na ficha" in saida
        assert rodar("comparacao", RECORD_ID, "--sim").exit_code == 0
        pasta = raiz / PASTA_ANALISES / PASTA_COMPARACAO
        for nome in ("dois_grupos.csv", "k_grupos.csv"):
            cabecalho = next(
                linha
                for linha in (pasta / nome).read_text(encoding="utf-8-sig").splitlines()
                if linha and not linha.startswith("#")
            )
            assert ";mediana [Q1 a Q3];" in cabecalho

    def test_o_friedman_pela_regra_e_escrito_nas_repetidas(self, rodar, projeto_com_rodada):
        """
        A dor de 0 a 4 chega do `perfil` como código; marcada `numerica` na reunião,
        ela rejeita a normal e vai para o Friedman pela regra. O peso, em que a ANOVA
        não pode, vai pelo Friedman escrito no item.
        """
        raiz = projeto_com_rodada(bancos.para_comparar_repetidas())
        marcar_numericas(raiz, "dor_0", "dor_1", "dor_2")
        acrescentar_a_ficha(
            raiz,
            "comparacao:\n  - repetidas: [dor_0, dor_1, dor_2]\n"
            "  - repetidas: [peso_0, peso_1, peso_2]\n    metodo: friedman\n",
        )
        saida = _saida(rodar("comparacao", RECORD_ID))
        assert "→ Friedman (χ² = 2,08; 2 gl)." in saida
        assert "Friedman escrito na ficha (χ² = 80; 2 gl)" in saida
        assert rodar("comparacao", RECORD_ID, "--sim").exit_code == 0
        assert (raiz / PASTA_ANALISES / PASTA_COMPARACAO / "repetidas.csv").is_file()

    def test_regerar_avisa_que_arquivou(self, rodar, projeto_com_rodada):
        raiz = projeto_com_rodada()
        acrescentar_a_ficha(raiz, self.BLOCO)
        rodar("comparacao", RECORD_ID, "--sim")
        saida = _saida(rodar("comparacao", RECORD_ID, "--sim"))
        assert PASTA_ANTIGAS in saida

    def test_entre_grupos_a_simulacao_mostra_a_tabela_e_a_escolha(
        self, rodar, projeto_com_rodada
    ):
        """
        A regra escolhe o t de Welch entre os dois sexos, e a simulação mostra por quê
        — e avisa que doze valores por grupo é pouco para o Shapiro-Wilk rejeitar. A
        tabela dos grupos sai com o título, o bloco da comparação e uma linha por
        grupo.
        """
        raiz = projeto_com_rodada()
        acrescentar_a_ficha(raiz, "comparacao:\n  - [imc, 25]\n  - [imc, sexo]\n")
        resultado = rodar("comparacao", RECORD_ID)
        assert resultado.exit_code == 0
        saida = _saida(resultado)
        assert "Comparação entre dois grupos" in saida
        assert "Feminino" in saida and "Masculino" in saida
        assert "dois_grupos.csv" in saida and "uma_amostra.csv" in saida
        assert "não rejeita a normal em nenhum dos dois grupos" in saida
        assert "→ t de Welch (t =" in saida
        assert "t de Welch com 12 valores em Feminino e 12 valores em Masculino" in saida

    def test_tres_grupos_com_a_anova_escrita(self, rodar, projeto_com_rodada):
        raiz = projeto_com_rodada()
        acrescentar_a_ficha(raiz, "comparacao:\n  - [idade, escolaridade, anova]\n")
        resultado = rodar("comparacao", RECORD_ID, "--sim")
        assert resultado.exit_code == 0
        saida = _saida(resultado)
        assert "Comparação entre três grupos ou mais" in saida
        assert "ANOVA escrita na ficha (F =" in saida
        pasta = raiz / PASTA_ANALISES / PASTA_COMPARACAO
        assert (pasta / "k_grupos.csv").is_file()

    def test_tres_grupos_pela_regra_vao_para_a_anova_de_welch(self, rodar, projeto_com_rodada):
        raiz = projeto_com_rodada()
        acrescentar_a_ficha(raiz, "comparacao:\n  - [idade, escolaridade]\n")
        saida = _saida(rodar("comparacao", RECORD_ID))
        assert "não rejeita a normal em nenhum dos 3 grupos" in saida
        assert "→ ANOVA de Welch (F =" in saida

    def test_medidas_repetidas(self, rodar, projeto_com_rodada):
        """
        A tabela das repetidas na simulação, com o ε na frase da escolha, e o `.csv`
        dela com `--sim`.
        """
        raiz = projeto_com_rodada(bancos.para_comparar_repetidas())
        acrescentar_a_ficha(raiz, "comparacao:\n  - repetidas: [pas_0, pas_1, pas_2]\n")
        saida = _saida(rodar("comparacao", RECORD_ID))
        assert "Comparação entre medidas repetidas" in saida
        assert "não rejeita a normal em nenhuma das 3 medidas" in saida
        assert "→ ANOVA de medidas repetidas (F = 37,04; 1,84 e 67,96 gl; ε = 0,918)" in saida
        assert rodar("comparacao", RECORD_ID, "--sim").exit_code == 0
        assert (raiz / PASTA_ANALISES / PASTA_COMPARACAO / "repetidas.csv").is_file()

    def test_duas_medidas_sai_com_um(self, rodar, projeto_com_rodada):
        raiz = projeto_com_rodada(bancos.para_comparar_repetidas())
        acrescentar_a_ficha(raiz, "comparacao:\n  - repetidas: [pas_0, pas_1]\n")
        resultado = rodar("comparacao", RECORD_ID)
        assert resultado.exit_code == 1
        assert "a comparação é o t pareado" in _sem_moldura(resultado)

    def test_entre_grupos_com_sim_escreve_as_duas_tabelas(self, rodar, projeto_com_rodada):
        raiz = projeto_com_rodada()
        acrescentar_a_ficha(raiz, "comparacao:\n  - [imc, 25]\n  - [imc, sexo, student]\n")
        assert rodar("comparacao", RECORD_ID, "--sim").exit_code == 0
        pasta = raiz / PASTA_ANALISES / PASTA_COMPARACAO
        assert (pasta / "uma_amostra.csv").is_file()
        assert (pasta / "dois_grupos.csv").is_file()

    def test_o_metodo_de_dois_grupos_em_tres_sai_com_um(self, rodar, projeto_com_rodada):
        raiz = projeto_com_rodada()
        acrescentar_a_ficha(raiz, "comparacao:\n  - [imc, escolaridade, student]\n")
        resultado = rodar("comparacao", RECORD_ID)
        assert resultado.exit_code == 1
        assert "`student` não se aplica a 3 grupos" in _sem_moldura(resultado)


class TestAnalisar:
    LISTA = "analises: [descritiva, cruzamento, comparacao]"
    # O segundo item da comparação é o que dá aviso — 12 casos por grupo —, e o
    # `--resumo` precisa de um aviso para mostrar.
    BLOCOS = TestCruzamento.BLOCO + "comparacao:\n  - [imc, 25]\n  - [imc, sexo]\n"

    @pytest.fixture
    def projeto_do_lote(self, projeto_com_banco):
        """
        Banco, dicionário, a lista e os blocos — sem rodada nenhuma, para que o lote e
        os comandos um por um partam do mesmo lugar.
        """

        def montar(lista: str | None = None, blocos: str | None = None):
            from flatcap.perfil import executar_perfil, preparar_perfil

            raiz = projeto_com_banco()
            executar_perfil(preparar_perfil(raiz))
            escrever_analises(raiz, lista or self.LISTA)
            acrescentar_a_ficha(raiz, self.BLOCOS if blocos is None else blocos)
            return raiz

        return montar

    def test_simula_por_padrao_e_mostra_cada_analise_e_o_lote(self, rodar, projeto_do_lote):
        raiz = projeto_do_lote()
        resultado = rodar("analisar", RECORD_ID, "--sem-graficos")
        assert resultado.exit_code == 0
        assert not any((raiz / PASTA_ANALISES).iterdir())
        saida = _saida(resultado)
        assert "1/3 descritiva" in saida
        assert "2/3 cruzamento" in saida
        assert "3/3 comparacao" in saida
        assert "sexo × escolaridade" in saida  # a tabela do cruzamento, inteira
        assert "Escolha do teste (regra dos pressupostos)" in saida  # a nota da comparação
        assert "O lote" in saida
        assert "3 análises da lista `analises:` do projeto.yaml" in saida
        assert "Repita com --sim para escrever as 3 análises." in saida

    def test_a_saida_de_cada_analise_e_a_do_comando_dela(self, rodar, projeto_do_lote):
        """
        A escolha da saída foi "tudo, e o resumo no fim": o que o comando de cada
        análise mostraria antes de escrever está dentro da saída do lote, igual.
        """
        projeto_do_lote()
        lote = _saida(rodar("analisar", RECORD_ID, "--sem-graficos"))
        for comando in (
            ("descritiva", RECORD_ID, "--sem-graficos"),
            ("cruzamento", RECORD_ID),
            ("comparacao", RECORD_ID),
        ):
            sozinho = _saida(rodar(*comando)).split(" Simulação. ")[0]
            assert sozinho in lote, comando[0]

    def test_resumo_mostra_so_o_lote_e_os_avisos(self, rodar, projeto_do_lote):
        projeto_do_lote()
        resultado = rodar("analisar", RECORD_ID, "--sem-graficos", "--resumo")
        assert resultado.exit_code == 0
        saida = _saida(resultado)
        assert "1/3" not in saida
        assert "sexo × escolaridade" not in saida
        assert "3 análises da lista `analises:` do projeto.yaml" in saida
        assert "comparacao: `imc` por `sexo`: t de Welch com 12 valores" in saida

    def test_com_sim_escreve_todas(self, rodar, projeto_do_lote):
        raiz = projeto_do_lote()
        resultado = rodar("analisar", RECORD_ID, "--sem-graficos", "--sim")
        assert resultado.exit_code == 0
        for pasta in (PASTA_DESCRITIVA, PASTA_CRUZAMENTO, PASTA_COMPARACAO):
            assert (raiz / PASTA_ANALISES / pasta / "manifesto.json").is_file()
        saida = _saida(resultado)
        assert "Descritiva escrita." in saida
        assert "Cruzamento escrito." in saida
        assert "Comparação escrita." in saida
        assert "Lote escrito. 3 análises da lista em 3. Análises/" in saida
        assert f"flatcap relatorio {RECORD_ID} --sim" in saida

    def test_o_lote_e_a_soma_dos_comandos(
        self, rodar, projeto_do_lote, congelar_relogio, root, tmp_path, monkeypatch
    ):
        """
        O critério de pronto do `analises.py`, pela linha de comando inteira: o mesmo
        `FLATCAP_ROOT` em duas cópias, o lote numa e os três comandos na outra, com o
        relógio parado. `3. Análises/` sai igual byte a byte, e o histórico do lote é o
        dos comandos mais a linha dele.
        """
        from conftest import PASTA, PROJETO, linhas_do_historico

        congelar_relogio()
        raiz = projeto_do_lote()
        outro_root = tmp_path / "OutroRoot"
        shutil.copytree(root, outro_root)
        outra = outro_root / PASTA / PROJETO

        assert rodar("analisar", RECORD_ID, "--sem-graficos", "--sim").exit_code == 0
        monkeypatch.setenv("FLATCAP_ROOT", str(outro_root))
        assert rodar("descritiva", RECORD_ID, "--sem-graficos", "--sim").exit_code == 0
        assert rodar("cruzamento", RECORD_ID, "--sim").exit_code == 0
        assert rodar("comparacao", RECORD_ID, "--sim").exit_code == 0

        def arquivos(pasta):
            return {
                str(caminho.relative_to(pasta)): caminho.read_bytes()
                for caminho in sorted((pasta / PASTA_ANALISES).rglob("*"))
                if caminho.is_file()
            }

        assert arquivos(raiz) == arquivos(outra)
        assert linhas_do_historico(raiz)[:-1] == linhas_do_historico(outra)

    def test_o_historico_ganha_a_linha_de_cada_analise_e_a_do_lote(
        self, rodar, projeto_do_lote
    ):
        from conftest import linhas_do_historico

        raiz = projeto_do_lote()
        antes = len(linhas_do_historico(raiz))
        rodar("analisar", RECORD_ID, "--sem-graficos", "--sim")
        linhas = linhas_do_historico(raiz)
        assert len(linhas) == antes + 4
        assert f"`flatcap analisar {RECORD_ID}`" in linhas[-1]

    def test_lista_vazia_sai_com_um_e_ensina_a_linha(self, rodar, projeto_com_rodada):
        """O colchete da linha pronta é marcação para o `rich`: ela não pode sumir."""
        raiz = projeto_com_rodada()
        acrescentar_a_ficha(raiz, TestCruzamento.BLOCO)
        resultado = rodar("analisar", RECORD_ID)
        assert resultado.exit_code == 1
        saida = _sem_moldura(resultado)
        assert "Análises" in saida
        assert "analises: [descritiva, cruzamento]" in saida

    def test_as_recusas_saem_num_painel_por_analise(self, rodar, projeto_do_lote):
        raiz = projeto_do_lote(
            "analises: [descritiva, correlacao, comparacao]",
            "correlacao:\n  - [idade, peso]\ncomparacao:\n  - [sexo, 25]\n",
        )
        resultado = rodar("analisar", RECORD_ID, "--sem-graficos")
        assert resultado.exit_code == 1
        saida = _sem_moldura(resultado)
        assert "Correlação" in saida and "Comparação" in saida
        assert "`peso` não está no dicionario.csv" in saida
        assert "2 das 3 análises da lista recusaram" in saida
        assert "Nada foi escrito nem arquivado" in saida
        assert not any((raiz / PASTA_ANALISES).iterdir())

    def test_nome_desconhecido_sai_com_um(self, rodar, projeto_do_lote):
        projeto_do_lote("analises: [descritiva, associação]", "")
        resultado = rodar("analisar", RECORD_ID)
        assert resultado.exit_code == 1
        assert "escreva `associacao`, sem acento" in _sem_moldura(resultado)

    def test_o_help_mostra_a_forma_da_lista(self):
        """O colchete é marcação para o `rich`: sem o escape, o exemplo some."""
        saida = _saida(runner.invoke(app, ["analisar", "--help"]))
        assert "analises: [descritiva, normalidade, correlacao, comparacao]" in saida
        assert "--resumo" in saida

    def test_a_falha_de_escrita_vira_painel_e_diz_onde_parou(
        self, rodar, projeto_do_lote, monkeypatch
    ):
        def disco_cheio(_plano):
            raise OSError(28, "No space left on device")

        projeto_do_lote()
        monkeypatch.setattr("flatcap.cruzamento.executar_cruzamento", disco_cheio)
        resultado = rodar("analisar", RECORD_ID, "--sem-graficos", "--sim")
        assert resultado.exit_code == 1
        saida = _sem_moldura(resultado)
        assert "Descritiva escrita." in saida
        assert "Escrita em disco" in saida
        assert "No space left on device" in saida
        assert "Parou na análise `cruzamento`" in saida
        assert "A análise `comparacao` não rodou." in saida

    def test_o_ctrl_c_sai_com_130_e_diz_onde_parou(self, rodar, projeto_do_lote, monkeypatch):
        """
        O `click` diria só «Aborted!». O que sobra para saber depois de um Ctrl+C no
        meio do lote é qual análise ficou escrita e qual pode ter ficado pela metade.
        """

        def interrompe(_plano):
            raise KeyboardInterrupt

        projeto_do_lote()
        monkeypatch.setattr("flatcap.cruzamento.executar_cruzamento", interrompe)
        resultado = rodar("analisar", RECORD_ID, "--sem-graficos", "--sim")
        assert resultado.exit_code == 130
        saida = _sem_moldura(resultado)
        assert "Interrompido" in saida
        assert "pode ter ficado pela metade" in saida

    def test_nao_toca_a_rede(self, rodar, projeto_do_lote, monkeypatch):
        def bomba(*_a, **_k):
            raise AssertionError("o lote tentou falar com a rede")

        monkeypatch.setattr("flatcap.redcap.requests.post", bomba)
        projeto_do_lote()
        assert rodar("analisar", RECORD_ID, "--sem-graficos").exit_code == 0
        assert rodar("analisar", RECORD_ID, "--sem-graficos", "--sim").exit_code == 0

    def test_toda_analise_do_registro_sabe_se_mostrar(self):
        """
        Uma análise que o lote rodasse sem estar no `_NA_TELA` seria uma análise que ele
        não saberia mostrar — o `KeyError` apareceria no meio da simulação.
        """
        from flatcap.analises import REGISTRO
        from flatcap.cli import _NA_TELA

        assert set(_NA_TELA) == {registro.nome for registro in REGISTRO}


class TestRelatorio:
    def test_simula_por_padrao(self, rodar, projeto_com_rodada):
        raiz = projeto_com_rodada()
        resultado = rodar("relatorio", RECORD_ID)
        assert resultado.exit_code == 0
        assert not list(raiz.glob("Relatorio_*.docx"))

    def test_com_sim_escreve(self, rodar, projeto_com_rodada):
        raiz = projeto_com_rodada()
        resultado = rodar("relatorio", RECORD_ID, "--sim")
        assert resultado.exit_code == 0
        assert list(raiz.glob("Relatorio_*.docx"))

    def test_sem_descritiva_sai_com_um(self, rodar, projeto_com_banco):
        projeto_com_banco()
        resultado = rodar("relatorio", RECORD_ID)
        assert resultado.exit_code == 1
        assert "flatcap descritiva" in _saida(resultado)

    def test_o_alerta_aparece_no_terminal_e_avisa_para_ler_antes_de_enviar(
        self, rodar, projeto_com_rodada
    ):
        from flatcap.projeto import PASTA_DADOS

        raiz = projeto_com_rodada()
        alvo = raiz / PASTA_DADOS / "00_redcap_2026-09-01_banco.csv"
        alvo.write_text("estragado", encoding="utf-8")
        saida = _saida(rodar("relatorio", RECORD_ID, "--sim"))
        assert "Vai escrito no documento" in saida
        assert "Leia antes de enviar" in saida

    def test_titulo_troca_o_titulo(self, rodar, projeto_com_rodada):
        raiz = projeto_com_rodada()
        rodar("relatorio", RECORD_ID, "--titulo", "Relatório parcial", "--sim")
        from docx import Document

        documento = Document(str(next(raiz.glob("Relatorio_*.docx"))))
        assert documento.paragraphs[0].text == "Relatório parcial"

    def test_a_simulacao_mostra_o_titulo_que_sera_escrito(self, rodar, projeto_com_rodada):
        """
        A simulação existe para mostrar o que seria gravado. O cabeçalho do
        `relatorio` traz projeto, rodada, banco e modelo — e **não** traz o
        título, então `--titulo` só se confere depois de executar, que é
        exatamente o que a simulação existe para evitar.

        Uma linha em `_cabecalho_do_relatorio` resolve.
        """
        projeto_com_rodada()
        saida = _saida(rodar("relatorio", RECORD_ID, "--titulo", "Relatório parcial"))
        assert "Relatório parcial" in saida

    def test_template_inexistente_sai_com_um(self, rodar, projeto_com_rodada, tmp_path):
        projeto_com_rodada()
        resultado = rodar("relatorio", RECORD_ID, "--template", str(tmp_path / "x.docx"))
        assert resultado.exit_code == 1


class TestTemplate:
    def test_simula_por_padrao(self, rodar, root):
        resultado = rodar("template")
        assert resultado.exit_code == 0
        assert not (root / "template.docx").exists()

    def test_com_sim_escreve_no_root(self, rodar, root):
        assert rodar("template", "--sim").exit_code == 0
        assert (root / "template.docx").is_file()

    def test_avisa_que_vai_substituir(self, rodar, root):
        (root / "template.docx").write_bytes(b"PK")
        assert "seus ajustes no Word se perdem" in _saida(rodar("template"))

    def test_saida_escolhe_o_destino(self, rodar, tmp_path):
        alvo = tmp_path / "meu_modelo.docx"
        rodar("template", "--saida", str(alvo), "--sim")
        assert alvo.is_file()


# ── O que vale para todos ───────────────────────────────────────────────────


class TestInvariantes:
    @pytest.mark.parametrize(
        "comando",
        [
            ("novo", "40"),
            ("dados", "adicionar", RECORD_ID, "ARQUIVO"),
            ("perfil", RECORD_ID),
            ("descritiva", RECORD_ID),
            ("normalidade", RECORD_ID),
            ("cruzamento", RECORD_ID),
            ("associacao", RECORD_ID),
            ("correlacao", RECORD_ID),
            ("comparacao", RECORD_ID),
            ("analisar", RECORD_ID),
            ("relatorio", RECORD_ID),
            ("template",),
        ],
    )
    def test_todo_comando_que_escreve_tem_a_opcao_sim(self, comando):
        caminho = list(comando[:-1]) if len(comando) > 1 else list(comando)
        ajuda = runner.invoke(app, [*caminho, "--help"])
        texto = " ".join(ajuda.output.split())
        assert "--sim" in texto

    def test_nenhum_comando_de_disco_toca_a_rede(self, rodar, projeto_com_rodada, monkeypatch):
        """
        Do `dados adicionar` em diante, nada fala com o REDCap. A prova é
        substituir o `requests.post` por uma bomba.
        """

        def bomba(*_a, **_k):
            raise AssertionError("um comando de disco tentou falar com a rede")

        monkeypatch.setattr("flatcap.redcap.requests.post", bomba)
        acrescentar_a_ficha(
            projeto_com_rodada(),
            TestCruzamento.BLOCO
            + TestAssociacao.BLOCO
            + TestCorrelacao.BLOCO
            + TestComparacao.BLOCO,
        )
        for comando in (
            ("dados", "listar", RECORD_ID),
            ("perfil", RECORD_ID),
            ("descritiva", RECORD_ID),
            ("normalidade", RECORD_ID, "--sem-graficos"),
            ("cruzamento", RECORD_ID),
            ("associacao", RECORD_ID),
            ("correlacao", RECORD_ID, "--sem-graficos"),
            ("comparacao", RECORD_ID),
            ("relatorio", RECORD_ID),
        ):
            assert rodar(*comando).exit_code == 0, comando

    def test_o_historico_ganha_uma_linha_por_comando_que_escreve(
        self, rodar, projeto_com_banco
    ):
        from conftest import linhas_do_historico

        raiz = projeto_com_banco()
        acrescentar_a_ficha(
            raiz,
            TestCruzamento.BLOCO
            + TestAssociacao.BLOCO
            + TestCorrelacao.BLOCO
            + TestComparacao.BLOCO,
        )
        antes = len(linhas_do_historico(raiz))
        rodar("perfil", RECORD_ID, "--sim")
        rodar("descritiva", RECORD_ID, "--sim")
        rodar("normalidade", RECORD_ID, "--sem-graficos", "--sim")
        rodar("cruzamento", RECORD_ID, "--sim")
        rodar("associacao", RECORD_ID, "--sim")
        rodar("correlacao", RECORD_ID, "--sem-graficos", "--sim")
        rodar("comparacao", RECORD_ID, "--sim")
        rodar("relatorio", RECORD_ID, "--sim")
        assert len(linhas_do_historico(raiz)) == antes + 8

    def test_a_cli_nao_tem_regra_de_negocio(self):
        """
        "Quais são as 10 mais recentes" está em `modelo.py`, não aqui, porque dá
        para testá-la sem simular terminal. O guarda: a `cli` não faz conta
        estatística nem abre banco no topo do módulo.
        """
        import ast
        import inspect

        import flatcap.cli as modulo

        arvore = ast.parse(inspect.getsource(modulo))
        topo = {
            alias.name.split(".")[0]
            for no in arvore.body
            if isinstance(no, ast.Import)
            for alias in no.names
        } | {
            no.module.split(".")[0]
            for no in arvore.body
            if isinstance(no, ast.ImportFrom) and no.module
        }
        assert {"pandas", "matplotlib", "docx"}.isdisjoint(topo)
