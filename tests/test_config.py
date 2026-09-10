"""
Configuração — Fase 0.

O único lugar do sistema que lê variáveis de ambiente. Cinco validações, cada
uma contra um engano específico, e o produto principal do módulo são as
**mensagens**: um erro de configuração precisa dizer o que fazer.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from flatcap.config import CHAVES, Config, ConfigError, carregar


def _env(tmp_path, **valores):
    caminho = tmp_path / ".env"
    caminho.write_text(
        "\n".join(f"{chave}={valor}" for chave, valor in valores.items()) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return caminho


class TestChavesAusentes:
    def test_sem_nenhuma_chave_lista_as_tres_e_manda_copiar_o_exemplo(self, tmp_path):
        with pytest.raises(ConfigError) as erro:
            carregar(env_file=None)
        texto = str(erro.value)
        for chave in CHAVES:
            assert chave in texto
        assert ".env.example" in texto

    def test_a_mensagem_diz_por_que_cada_chave_importa(self, tmp_path, root):
        caminho = _env(tmp_path, FLATCAP_ROOT=str(root))
        with pytest.raises(ConfigError) as erro:
            carregar(env_file=caminho)
        texto = str(erro.value)
        assert "API Playground" in texto
        assert "exportar" in texto

    def test_chave_so_com_espaco_conta_como_ausente(self, tmp_path, root):
        caminho = _env(
            tmp_path, REDCAP_API_URL="https://x/redcap/api/", REDCAP_TOKEN="   ",
            FLATCAP_ROOT=str(root),
        )
        with pytest.raises(ConfigError) as erro:
            carregar(env_file=caminho)
        assert "REDCAP_TOKEN" in str(erro.value)


class TestUrlDaApi:
    def test_o_link_do_survey_e_barrado_com_o_formato_certo(self, tmp_path, root):
        caminho = _env(
            tmp_path, REDCAP_API_URL="https://redcap.link/estatistico",
            REDCAP_TOKEN="0" * 32, FLATCAP_ROOT=str(root),
        )
        with pytest.raises(ConfigError) as erro:
            carregar(env_file=caminho)
        assert "/redcap/api/" in str(erro.value)

    def test_sem_esquema_e_barrado(self, tmp_path, root):
        caminho = _env(
            tmp_path, REDCAP_API_URL="servidor.org/redcap/api/",
            REDCAP_TOKEN="0" * 32, FLATCAP_ROOT=str(root),
        )
        with pytest.raises(ConfigError):
            carregar(env_file=caminho)

    def test_a_barra_final_e_acrescentada(self, tmp_path, root):
        """
        Sem ela o servidor responde 301 e o `requests` reenvia como GET — e o
        POST some no caminho.
        """
        caminho = _env(
            tmp_path, REDCAP_API_URL="https://servidor.org/redcap/api",
            REDCAP_TOKEN="0" * 32, FLATCAP_ROOT=str(root),
        )
        assert carregar(env_file=caminho).api_url.endswith("/")


class TestRoot:
    def test_caminho_relativo_e_barrado(self, tmp_path):
        caminho = _env(
            tmp_path, REDCAP_API_URL="https://x/redcap/api/", REDCAP_TOKEN="0" * 32,
            FLATCAP_ROOT="dados",
        )
        with pytest.raises(ConfigError) as erro:
            carregar(env_file=caminho)
        assert "absoluto" in str(erro.value)

    def test_pasta_inexistente_da_erro_e_nao_vira_pasta_vazia(self, tmp_path):
        """
        Um `FLATCAP_ROOT` digitado errado deve dar erro, não virar uma pasta
        vazia silenciosa em lugar nenhum.
        """
        alvo = tmp_path / "nuvem_nao_montada"
        caminho = _env(
            tmp_path, REDCAP_API_URL="https://x/redcap/api/", REDCAP_TOKEN="0" * 32,
            FLATCAP_ROOT=str(alvo),
        )
        with pytest.raises(ConfigError) as erro:
            carregar(env_file=caminho)
        assert "nuvem" in str(erro.value)
        assert not alvo.exists()

    def test_criar_root_cria(self, tmp_path):
        alvo = tmp_path / "nova"
        caminho = _env(
            tmp_path, REDCAP_API_URL="https://x/redcap/api/", REDCAP_TOKEN="0" * 32,
            FLATCAP_ROOT=str(alvo),
        )
        assert carregar(env_file=caminho, criar_root=True).root == alvo.resolve()

    def test_arquivo_no_lugar_de_pasta(self, tmp_path):
        alvo = tmp_path / "arquivo"
        alvo.write_text("x", encoding="utf-8")
        caminho = _env(
            tmp_path, REDCAP_API_URL="https://x/redcap/api/", REDCAP_TOKEN="0" * 32,
            FLATCAP_ROOT=str(alvo),
        )
        with pytest.raises(ConfigError) as erro:
            carregar(env_file=caminho)
        assert "não é uma pasta" in str(erro.value)

    def test_o_til_e_expandido(self, tmp_path, monkeypatch, root):
        monkeypatch.setenv("HOME", str(root.parent))
        caminho = _env(
            tmp_path, REDCAP_API_URL="https://x/redcap/api/", REDCAP_TOKEN="0" * 32,
            FLATCAP_ROOT=f"~/{root.name}",
        )
        assert carregar(env_file=caminho).root == root.resolve()


class TestPrecedenciaEArquivo:
    def test_a_variavel_do_sistema_vence_o_env(self, tmp_path, root, monkeypatch):
        """
        `override=False`: permite rodar em servidor, em outra máquina ou com
        credencial temporária sem editar arquivo nenhum.
        """
        monkeypatch.setenv("REDCAP_TOKEN", "DO_SISTEMA")
        caminho = _env(
            tmp_path, REDCAP_API_URL="https://x/redcap/api/", REDCAP_TOKEN="DO_ARQUIVO",
            FLATCAP_ROOT=str(root),
        )
        assert carregar(env_file=caminho).token == "DO_SISTEMA"

    def test_env_indicado_que_nao_existe_e_barrado(self, tmp_path):
        with pytest.raises(ConfigError) as erro:
            carregar(env_file=tmp_path / "nao_existe.env")
        assert "não existe" in str(erro.value)

    def test_a_origem_do_env_fica_registrada(self, tmp_path, root):
        caminho = _env(
            tmp_path, REDCAP_API_URL="https://x/redcap/api/", REDCAP_TOKEN="0" * 32,
            FLATCAP_ROOT=str(root),
        )
        assert carregar(env_file=caminho).origem_env == str(caminho)


class TestConfig:
    def test_e_imutavel(self, tmp_path, root):
        caminho = _env(
            tmp_path, REDCAP_API_URL="https://x/redcap/api/", REDCAP_TOKEN="0" * 32,
            FLATCAP_ROOT=str(root),
        )
        cfg = carregar(env_file=caminho)
        with pytest.raises(FrozenInstanceError):
            cfg.token = "outro"  # type: ignore[misc]

    @pytest.mark.parametrize(
        ("token", "esperado"),
        [
            ("ABCD" + "X" * 24 + "WXYZ", "ABCD" + "*" * 24 + "WXYZ"),
            ("curto", "*****"),
        ],
    )
    def test_o_token_mascarado_confere_sem_expor(self, tmp_path, token, esperado):
        cfg = Config(api_url="https://x/", token=token, root=tmp_path)
        assert cfg.token_mascarado == esperado
        assert token not in cfg.token_mascarado or len(token) <= 8


class TestQualidadeDasMensagens:
    """
    As mensagens são o produto principal deste módulo. Vale conferi-las com o
    olho de quem as lê no terminal — e conferir que elas não têm erro de
    digitação, porque uma mensagem com "syrvey" e "Preciisa" desautoriza a
    ferramenta que a escreveu.
    """

    @pytest.mark.parametrize(
        "errado",
        ["syrvey", "servey", "Preciisa", "medatados", "exisite", "Fatam", "aquivo", "Raíses"],
    )
    def test_nao_ha_erro_de_digitacao_conhecido(self, errado):
        import inspect

        import flatcap.config as modulo

        assert errado not in inspect.getsource(modulo), (
            f"`{errado}` aparece em config.py — corrija a grafia"
        )
