"""
Os comandos — a fiação.

Esta camada não contém regra de negócio: ela lê argumentos, chama as camadas de
baixo, formata a saída e escolhe o código de saída do processo. O teste aqui é
sobre **essas quatro coisas**, e nada mais — quem testa "quais são as 10 mais
recentes" é o `test_modelo.py`, porque a regra mora lá.

Três invariantes atravessam o arquivo:

**Os cinco comandos que escrevem simulam por padrão.** Sem `--sim`, nada no
disco muda. É a rede de proteção, e ela é conferida comando a comando.

**Erro previsto vira painel, não traceback.** Toda exceção declarada pelos
módulos é capturada; qualquer outra é bug e deve subir inteira.

**O código de saída é escolhido.** Recusa por juízo sai com 1; "nada para
fazer" sai com 0, para não quebrar script.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

import bancos
from conftest import MATRICULA, RECORD_ID, acrescentar_a_ficha
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

    def test_a_linha_sem_teste_e_o_t_contra_a_regra_aparecem_na_simulacao(
        self, rodar, projeto_com_rodada
    ):
        raiz = projeto_com_rodada(bancos.para_comparar())
        acrescentar_a_ficha(raiz, "comparacao:\n  - [renda, 2500]\n  - [renda, 3000, t]\n")
        saida = _saida(rodar("comparacao", RECORD_ID))
        assert (
            "o Shapiro-Wilk rejeita a normal (p < 0,001) → Wilcoxon, que ainda não está "
            "no FlatCap: a linha sai sem teste."
        ) in saida
        assert "contra a regra — ela escolheria Wilcoxon" in saida
        assert "1 item sem teste" in saida
        assert "1 com o método escrito na ficha" in saida

    def test_regerar_avisa_que_arquivou(self, rodar, projeto_com_rodada):
        raiz = projeto_com_rodada()
        acrescentar_a_ficha(raiz, self.BLOCO)
        rodar("comparacao", RECORD_ID, "--sim")
        saida = _saida(rodar("comparacao", RECORD_ID, "--sim"))
        assert PASTA_ANTIGAS in saida


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
