# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
"""
A camada sobre a API — Fase 1.

Quatro particularidades descobertas contra o servidor real, e cada uma tem um
teste com nome próprio. A mais cara delas — a forma indexada `fields[0]` — não é
verificável aqui: ela só aparece quando o `requests` monta o corpo urlencoded de
verdade, e por isso o teste dela vive no `test_e2e.py`, contra o servidor falso.

O que se testa aqui é a **tradução**: falha de rede, erro de aplicação e corpo
inesperado precisam virar `RedcapError` com uma frase, e nunca um traceback do
`urllib3` três camadas acima.
"""

from __future__ import annotations

import pytest
import requests

from flatcap.config import Config
from flatcap.redcap import (
    TIMEOUT_SEGUNDOS,
    ArquivoAusenteError,
    RedcapError,
    exportar_arquivo,
    exportar_metadados,
    exportar_projeto,
    exportar_registros,
    tem_arquivo,
)


@pytest.fixture
def cfg(tmp_path) -> Config:
    return Config(api_url="https://exemplo.org/redcap/api/", token="0" * 32, root=tmp_path)


class RespostaFalsa:
    def __init__(self, corpo=None, conteudo=b"", status=200, tipo="application/json", **cabecalhos):
        import json as _json

        self.status_code = status
        self.content = conteudo or (
            b"" if corpo is None and not conteudo else _json.dumps(corpo).encode()
        )
        if corpo is not None:
            self.content = _json.dumps(corpo).encode()
        self._corpo = corpo
        self.headers = {"Content-Type": tipo, **cabecalhos}
        self.text = self.content.decode("utf-8", errors="replace")

    def json(self):
        import json as _json

        return _json.loads(self.content.decode())

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


@pytest.fixture
def responder(monkeypatch):
    """
    Substitui `requests.post` e guarda o payload enviado.
    """
    enviados: list[dict] = []

    def instalar(resposta):
        def falso_post(url, data=None, timeout=None, **_k):
            enviados.append({"url": url, "data": data, "timeout": timeout})
            if isinstance(resposta, Exception):
                raise resposta
            return resposta

        monkeypatch.setattr("flatcap.redcap.requests.post", falso_post)
        return enviados

    return instalar


# ── Tradução de falhas ──────────────────────────────────────────────────────


class TestFalhasDeRede:
    @pytest.mark.parametrize(
        ("excecao", "pista"),
        [
            (requests.exceptions.SSLError("cert"), "Não foi possível acessar"),
            (requests.exceptions.Timeout("t"), str(TIMEOUT_SEGUNDOS)),
            (requests.exceptions.ConnectionError("c"), "VPN"),
        ],
    )
    def test_viram_mensagem_e_nao_traceback(self, cfg, responder, excecao, pista):
        responder(excecao)
        with pytest.raises(RedcapError) as erro:
            exportar_projeto(cfg)
        assert pista in str(erro.value)

    def test_o_connectionerror_e_tratado_depois_das_subclasses(self, cfg, responder):
        """
        No `requests`, `SSLError` e `ConnectTimeout` são subclasses de
        `ConnectionError`. Sem a ordem certa, máquina sem rede e certificado
        inválido dariam a mesma mensagem — e ela seria a errada.
        """
        responder(requests.exceptions.SSLError("cert"))
        with pytest.raises(RedcapError) as erro:
            exportar_projeto(cfg)
        assert "VPN" not in str(erro.value)

    @pytest.mark.parametrize(("status", "pista"), [(403, "Token"), (404, "Endereço")])
    def test_status_de_autorizacao_e_endereco(self, cfg, responder, status, pista):
        responder(RespostaFalsa(corpo={}, status=status))
        with pytest.raises(RedcapError) as erro:
            exportar_projeto(cfg)
        assert pista in str(erro.value)

    @pytest.mark.parametrize(
        "excecao",
        [
            requests.exceptions.ChunkedEncodingError("a conexão caiu no meio"),
            requests.exceptions.TooManyRedirects("redireciona em círculo"),
            requests.exceptions.InvalidURL("url que o requests não aceita"),
        ],
        ids=["download-interrompido", "redirecionamento", "url-invalida"],
    )
    def test_o_resto_da_familia_do_requests_tambem_vira_mensagem(
        self, cfg, responder, excecao
    ):
        """
        REGRESSÃO da 1.13.0. Só três exceções do `requests` eram traduzidas; a
        conexão que cai no meio do download de um anexo grande subia como
        traceback.
        """
        responder(excecao)
        with pytest.raises(RedcapError) as erro:
            exportar_arquivo(cfg, "40", "database")
        assert type(excecao).__name__ in str(erro.value)


class TestErroDoServidor:
    """
    REGRESSÃO da 1.13.0. O erro HTTP sem o `{"error": ...}` do REDCap passava pelo
    `raise_for_status()` do `requests`, e o `requests.HTTPError` não é
    `RedcapError`: o `novo` e o `listar --conferir-anexos` caíam com o traceback.
    """

    def test_o_502_do_proxy_no_download_do_anexo(self, cfg, responder):
        responder(
            RespostaFalsa(conteudo=b"<html>502 Bad Gateway</html>", status=502, tipo="text/html")
        )
        with pytest.raises(RedcapError) as erro:
            exportar_arquivo(cfg, "40", "database")
        mensagem = str(erro.value)
        assert "502" in mensagem and "registro 40" in mensagem
        assert "manutenção" in mensagem

    def test_o_500_em_html_nao_e_confundido_com_url_errada(self, cfg, responder):
        """
        A página de erro do servidor também não é JSON, e a mensagem de "URL
        errada" mandaria o usuário mexer no `.env` que está certo.
        """
        responder(
            RespostaFalsa(conteudo=b"<html>Erro interno</html>", status=500, tipo="text/html")
        )
        with pytest.raises(RedcapError) as erro:
            exportar_projeto(cfg)
        assert "500" in str(erro.value)
        assert "endpoint da API" not in str(erro.value)

    def test_o_erro_http_com_json_sem_a_chave_error(self, cfg, responder):
        responder(RespostaFalsa(corpo={"message": "indisponível"}, status=503))
        with pytest.raises(RedcapError) as erro:
            exportar_registros(cfg)
        assert "503" in str(erro.value)

    def test_o_listar_conferindo_anexos_nao_cai(self, cfg, responder):
        responder(RespostaFalsa(conteudo=b"<html>500</html>", status=500, tipo="text/html"))
        with pytest.raises(RedcapError):
            tem_arquivo(cfg, "40", "database")


class TestErroDeAplicacao:
    def test_o_400_com_json_de_erro_vira_mensagem(self, cfg, responder):
        """
        Erro de aplicação vem como HTTP 400 com `{"error": "..."}`, e não como
        exceção de rede. Sem tratamento, vira `KeyError` três camadas acima.
        """
        responder(RespostaFalsa(corpo={"error": "You do not have permission"}, status=400))
        with pytest.raises(RedcapError) as erro:
            exportar_registros(cfg)
        assert "permission" in str(erro.value)

    def test_resposta_que_nao_e_json_sugere_a_url_errada(self, cfg, responder):
        responder(RespostaFalsa(conteudo=b"<html>REDCap</html>", tipo="text/html"))
        with pytest.raises(RedcapError) as erro:
            exportar_projeto(cfg)
        assert "endpoint da API" in str(erro.value)

    def test_corpo_nulo_e_barrado_na_origem(self, cfg, responder):
        """
        `null` é JSON válido: um corpo nulo atravessaria o tratamento de erro
        sem alarme e estouraria três camadas adiante. A mensagem traz o código
        HTTP, o Content-Type e o tamanho.
        """
        responder(RespostaFalsa(corpo=None, conteudo=b"null"))
        with pytest.raises(RedcapError) as erro:
            exportar_projeto(cfg)
        assert "corpo vazio" in str(erro.value)
        assert "permissão" in str(erro.value)

    def test_lista_esperada_e_dicionario_recebido(self, cfg, responder):
        responder(RespostaFalsa(corpo={"project_id": "1"}))
        with pytest.raises(RedcapError) as erro:
            exportar_registros(cfg)
        assert "lista" in str(erro.value)


# ── O payload ───────────────────────────────────────────────────────────────


class TestPayload:
    def test_o_token_e_o_formato_vao_em_toda_chamada(self, cfg, responder):
        enviados = responder(RespostaFalsa(corpo={"project_id": "1"}))
        exportar_projeto(cfg)
        dados = enviados[0]["data"]
        assert dados["token"] == cfg.token
        assert dados["format"] == "json"
        assert dados["returnFormat"] == "json"

    def test_as_listas_vao_separadas_por_virgula(self, cfg, responder):
        """
        E **não** na forma indexada `fields[0]`, que o API Playground sugere: os
        colchetes viram `%5B0%5D` no corpo urlencoded e chegam do outro lado
        como um único `fields` com os nomes grudados.
        """
        enviados = responder(RespostaFalsa(corpo=[]))
        exportar_registros(cfg, fields=["record_id", "intro"], records=["42", "43"])
        dados = enviados[0]["data"]
        assert dados["fields"] == "record_id,intro"
        assert dados["records"] == "42,43"
        assert not any("[" in chave for chave in dados)

    def test_valores_crus_e_nao_rotulos(self, cfg, responder):
        """
        `intro` chega como "1"/"2". Código é estável; rótulo muda quando alguém
        edita o texto da pergunta no REDCap, e a mudança quebraria o mapa sem
        erro nenhum — todo mundo viraria "indefinido".
        """
        enviados = responder(RespostaFalsa(corpo=[]))
        exportar_registros(cfg)
        assert enviados[0]["data"]["rawOrLabel"] == "raw"
        assert enviados[0]["data"]["rawOrLabelHeaders"] == "raw"

    def test_campos_vazios_nao_entram_na_lista(self, cfg, responder):
        enviados = responder(RespostaFalsa(corpo=[]))
        exportar_registros(cfg, fields=["record_id", "", "  "])
        assert enviados[0]["data"]["fields"] == "record_id"

    def test_o_timeout_e_o_do_modulo(self, cfg, responder):
        enviados = responder(RespostaFalsa(corpo={"project_id": "1"}))
        exportar_projeto(cfg)
        assert enviados[0]["timeout"] == TIMEOUT_SEGUNDOS

    def test_os_valores_voltam_como_texto(self, cfg, responder):
        responder(RespostaFalsa(corpo=[{"record_id": 42, "intro": None}]))
        (registro,) = exportar_registros(cfg)
        assert registro == {"record_id": "42", "intro": ""}

    def test_metadados(self, cfg, responder):
        enviados = responder(RespostaFalsa(corpo=[{"field_name": "sexo"}]))
        assert exportar_metadados(cfg)[0]["field_name"] == "sexo"
        assert enviados[0]["data"]["content"] == "metadata"


# ── Anexos ──────────────────────────────────────────────────────────────────


class TestArquivo:
    def test_o_nome_vem_do_content_type(self, cfg, responder):
        """
        É onde o REDCap o põe, e não no `Content-Disposition` como na maioria
        dos servidores. Os dois são consultados.
        """
        responder(
            RespostaFalsa(
                conteudo=b"PK\x03\x04",
                tipo='application/vnd...sheet; name="banco do cliente.xlsx"',
            )
        )
        assert exportar_arquivo(cfg, "42", "database").nome == "banco do cliente.xlsx"

    def test_o_nome_vem_do_content_disposition_quando_ha(self, cfg, responder):
        responder(
            RespostaFalsa(
                conteudo=b"PK",
                tipo="application/octet-stream",
                **{"Content-Disposition": 'attachment; filename="base.csv"'},
            )
        )
        assert exportar_arquivo(cfg, "42", "database").nome == "base.csv"

    @pytest.mark.parametrize(
        "anunciado", ["../../etc/passwd", "C:\\Windows\\base.xlsx", "/etc/base.xlsx"]
    )
    def test_o_nome_anunciado_nao_monta_caminho(self, cfg, responder, anunciado):
        """
        O nome vem de fora, e o que vem de fora não monta caminho. A limpeza
        descarta qualquer componente antes que ele chegue perto de um `open()`.
        """
        responder(RespostaFalsa(conteudo=b"PK", tipo=f'application/x; name="{anunciado}"'))
        nome = exportar_arquivo(cfg, "42", "database").nome
        assert "/" not in nome and "\\" not in nome and ".." not in nome

    def test_sem_nome_anunciado_usa_registro_e_campo(self, cfg, responder):
        responder(RespostaFalsa(conteudo=b"PK", tipo="application/octet-stream"))
        assert exportar_arquivo(cfg, "42", "database").nome == "42_database"

    @pytest.mark.parametrize(
        "mensagem",
        ["There is no file to download", "no file to download", "Não há arquivo anexado"],
    )
    def test_ausencia_de_anexo_e_erro_proprio(self, cfg, responder, mensagem):
        """
        Cliente sem anexo é caso normal do fluxo, não falha. A separação é o que
        impede confundir "não tem anexo" com "token sem permissão de exportar
        arquivos".
        """
        responder(RespostaFalsa(corpo={"error": mensagem}, status=400))
        with pytest.raises(ArquivoAusenteError):
            exportar_arquivo(cfg, "42", "database")

    def test_outro_erro_nao_vira_ausencia(self, cfg, responder):
        responder(RespostaFalsa(corpo={"error": "You do not have permission"}, status=400))
        with pytest.raises(RedcapError) as erro:
            exportar_arquivo(cfg, "42", "database")
        assert not isinstance(erro.value, ArquivoAusenteError)

    def test_tem_arquivo_responde_sem_exigir_tratar_excecao(self, cfg, responder):
        responder(RespostaFalsa(conteudo=b"PK", tipo="application/x"))
        assert tem_arquivo(cfg, "42", "database") is True

        responder(RespostaFalsa(corpo={"error": "There is no file"}, status=400))
        assert tem_arquivo(cfg, "42", "database") is False

    def test_o_arquivo_ausente_e_subclasse_de_redcap_error(self):
        assert issubclass(ArquivoAusenteError, RedcapError)
