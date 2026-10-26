# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Configuração — Fase 0.

O único lugar do sistema que lê variáveis de ambiente. Cinco validações, cada
uma contra um engano específico, e o produto principal do módulo são as
**mensagens**: um erro de configuração precisa dizer o que fazer.
"""

from __future__ import annotations

import os
import stat
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

import flatcap.config as config
from flatcap.config import (
    CHAVES,
    TEXTO_DO_ENV,
    Config,
    ConfigError,
    carregar,
    criar_env_da_conta,
)


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
            tmp_path, REDCAP_API_URL="https://redcap.link/exemplo",
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


class TestEnvDaConta:
    """
    O terceiro degrau da procura, desde a 1.13.1: o `.env` de quem instalou o
    FlatCap por um pacote e roda o comando de qualquer pasta. O `ambiente_limpo`
    do `conftest.py` aponta a pasta da conta para dentro do `tmp_path` — e por
    isso ela é chamada pelo módulo, `config.pasta_de_configuracao()`, que é onde
    a troca acontece.
    """

    @staticmethod
    def _completo(root, url="https://conta/redcap/api/") -> str:
        return f"REDCAP_API_URL={url}\nREDCAP_TOKEN={'0' * 32}\nFLATCAP_ROOT={root}\n"

    def test_sem_env_na_pasta_o_da_conta_e_lido(self, root):
        conta = config.pasta_de_configuracao()
        conta.mkdir()
        (conta / ".env").write_text(self._completo(root), encoding="utf-8")

        cfg = carregar()

        assert cfg.origem_env == str(conta / ".env")
        assert cfg.api_url == "https://conta/redcap/api/"

    def test_o_da_pasta_vence_o_da_conta(self, tmp_path, root):
        conta = config.pasta_de_configuracao()
        conta.mkdir()
        (conta / ".env").write_text(self._completo(root), encoding="utf-8")
        _env(
            tmp_path, REDCAP_API_URL="https://local/redcap/api/", REDCAP_TOKEN="0" * 32,
            FLATCAP_ROOT=str(root),
        )

        assert carregar().api_url == "https://local/redcap/api/"

    def test_sem_env_nenhum_a_mensagem_ensina_o_da_conta(self):
        with pytest.raises(ConfigError) as erro:
            carregar()
        texto = str(erro.value)
        assert str(config.pasta_de_configuracao() / ".env") in texto
        assert "flatcap doctor --criar-env" in texto

    def test_criar_escreve_o_modelo_e_nunca_sobrescreve(self):
        caminho = criar_env_da_conta()
        assert caminho == config.pasta_de_configuracao() / ".env"
        assert caminho.read_text(encoding="utf-8") == TEXTO_DO_ENV

        caminho.write_text("o meu", encoding="utf-8")
        assert criar_env_da_conta() is None
        assert caminho.read_text(encoding="utf-8") == "o meu"

    @pytest.mark.skipif(os.name != "posix", reason="no Windows, quem decide é a pasta")
    def test_o_env_da_conta_nasce_so_para_o_dono(self):
        """Ele guarda o token do REDCap, e um token é uma senha."""
        caminho = criar_env_da_conta()
        assert stat.S_IMODE(caminho.stat().st_mode) == 0o600

    def test_o_modelo_em_branco_acusa_as_tres_chaves(self):
        """
        O modelo vem em branco de propósito: copiado sem preencher, ele faz a
        falta ser acusada, e não um `doctor` tentando falar com `<seu-servidor>`.
        """
        criar_env_da_conta()
        with pytest.raises(ConfigError) as erro:
            carregar()
        for chave in CHAVES:
            assert chave in str(erro.value)
        assert "Arquivo .env lido" in str(erro.value)

    def test_o_env_example_do_repositorio_e_o_modelo(self):
        exemplo = Path(__file__).resolve().parents[1] / ".env.example"
        if not exemplo.is_file():
            pytest.skip("fora de um clone do repositório")
        assert exemplo.read_text(encoding="utf-8") == TEXTO_DO_ENV


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
