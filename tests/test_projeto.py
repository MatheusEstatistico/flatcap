# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
"""
A pasta do projeto — Fase 2.

A decisão central da fase é `preparar`/`executar`, e o teste dela é o mesmo de
todas as outras: **o que a simulação desenha é lido do próprio plano**. Se a
simulação percorresse um caminho de código e a execução percorresse outro, a
rede de proteção seria decorativa.
"""

from __future__ import annotations

import hashlib
import os
import stat
from datetime import date, datetime

import pytest
import yaml

from conftest import AGORA, linhas_do_historico
from flatcap.config import Config
from flatcap.modelo import CAMPO_ANEXO
from flatcap.projeto import (
    ARQUIVO_HISTORICO,
    ARQUIVO_PROJETO,
    PASTA_DADOS,
    PASTA_DESCRITIVA,
    SUBPASTAS,
    ClienteIncompletoError,
    ProjetoExistenteError,
    RegistroNaoEncontradoError,
    anotar,
    executar,
    marcar_somente_leitura,
    nome_do_banco,
    preparar,
    tamanho_legivel,
)
from flatcap.redcap import ArquivoAusenteError, ArquivoRedcap

ANEXO = ArquivoRedcap(nome="banco do cliente.xlsx", conteudo=b"PK\x03\x04dados", tipo_mime="")


@pytest.fixture
def cfg(root) -> Config:
    return Config(api_url="https://x/redcap/api/", token="0" * 32, root=root)


@pytest.fixture
def redcap(monkeypatch):
    """
    Substitui as duas chamadas de rede que o `preparar` faz.
    """

    def instalar(registros, anexo=ANEXO):
        monkeypatch.setattr(
            "flatcap.projeto.exportar_registros", lambda *a, **k: registros
        )

        def exportar(*_a, **_k):
            if anexo is None:
                raise ArquivoAusenteError("sem anexo")
            return anexo

        monkeypatch.setattr("flatcap.projeto.exportar_arquivo", exportar)

    return instalar


REGISTRO = {
    "record_id": "42", "intro": "1", "matricula1": "00742",
    "prof1": "José Antônio de Sá", CAMPO_ANEXO: "banco.xlsx",
}


# ── O desenho da pasta ──────────────────────────────────────────────────────


def test_as_subpastas_sao_tres_e_nao_ha_pasta_de_relatorios():
    """
    Desvio deliberado do apêndice A do roteiro, registrado num comentário do
    `projeto.py` para que a Fase 6 não inventasse a pasta de volta — e ela não
    inventou. O `.docx` fica na raiz, que é onde a mão alcança primeiro.
    """
    assert SUBPASTAS == ("1. Dados originais", "2. Versões antigas", "3. Análises")
    assert not any("Relat" in nome for nome in SUBPASTAS)


def test_a_pasta_da_amostragem_nao_e_das_que_o_novo_cria(tmp_path):
    """
    A quarta pasta nasce no `flatcap amostragem`, que vem depois do `novo`: o `novo` não
    sabe se o pedido é de amostragem, e o projeto que nunca amostra não ganha uma pasta
    vazia.
    """
    from flatcap.projeto import (
        ARQUIVO_DESENHO,
        PASTA_AMOSTRAGEM,
        PASTA_ANTIGAS_DA_AMOSTRAGEM,
        pasta_da_amostragem,
    )

    assert PASTA_AMOSTRAGEM == "4. Amostragem"
    assert PASTA_AMOSTRAGEM not in SUBPASTAS
    assert ARQUIVO_DESENHO == "desenho.yaml"
    assert PASTA_ANTIGAS_DA_AMOSTRAGEM == "Versões antigas"
    assert pasta_da_amostragem(tmp_path) == tmp_path / "4. Amostragem"


def test_a_pasta_da_descritiva_mora_aqui():
    """
    Subiu do `descritiva.py` na Fase 6: o desenho da pasta é assunto deste
    módulo, e o `relatorio.py` precisa saber onde a rodada está sem importar o
    módulo que carrega o `pandas`.
    """
    from flatcap.descritiva import PASTA_DESCRITIVA as reexportado

    assert PASTA_DESCRITIVA == reexportado == "descritiva"


class TestNomeDoBanco:
    def test_o_prefixo_ordena_e_marca_a_versao_intocada(self):
        nome = nome_do_banco(ANEXO, date(2026, 9, 1), "42")
        assert nome.startswith("00_redcap_2026-09-01_")

    def test_o_nome_original_e_sanitizado(self):
        anexo = ArquivoRedcap(nome="base: final*.xlsx", conteudo=b"x", tipo_mime="")
        nome = nome_do_banco(anexo, date(2026, 9, 1), "42")
        assert ":" not in nome and "*" not in nome

    def test_sem_nome_usa_o_record_id(self):
        anexo = ArquivoRedcap(nome="", conteudo=b"x", tipo_mime="")
        assert "banco_42" in nome_do_banco(anexo, date(2026, 9, 1), "42")

    def test_sem_extensao_deduz_do_mime(self):
        anexo = ArquivoRedcap(nome="base", conteudo=b"x", tipo_mime="text/csv")
        assert nome_do_banco(anexo, date(2026, 9, 1), "42").endswith(".csv")

    def test_mime_generico_nao_inventa_extensao(self):
        anexo = ArquivoRedcap(nome="base", conteudo=b"x", tipo_mime="application/octet-stream")
        assert nome_do_banco(anexo, date(2026, 9, 1), "42").endswith("base")


# ── Preparar ────────────────────────────────────────────────────────────────


class TestPreparar:
    def test_o_plano_traz_tudo_resolvido(self, cfg, redcap):
        redcap([REGISTRO])
        plano = preparar(cfg, "42", agora=AGORA)
        assert plano.raiz.name == "Projeto 042"
        assert plano.raiz.parent.name == "00742 - José Antônio de Sá"
        assert len(plano.subpastas) == 3
        assert plano.tem_anexo
        assert plano.projeto_yaml and plano.historico_md

    def test_nao_toca_no_disco(self, cfg, redcap, root):
        redcap([REGISTRO])
        preparar(cfg, "42", agora=AGORA)
        assert list(root.iterdir()) == []

    def test_o_sha_e_calculado_sobre_os_bytes_da_rede(self, cfg, redcap):
        """
        Antecipado da Fase 3 de propósito: calculado agora, o hash é um recibo
        do que foi baixado; calculado depois, seria calculado sobre o que
        estivesse no disco naquele dia — que é o que ele existe para verificar.
        """
        redcap([REGISTRO])
        plano = preparar(cfg, "42", agora=AGORA)
        assert plano.banco.sha256 == hashlib.sha256(ANEXO.conteudo).hexdigest()

    def test_registro_inexistente(self, cfg, redcap):
        redcap([])
        with pytest.raises(RegistroNaoEncontradoError) as erro:
            preparar(cfg, "99", agora=AGORA)
        assert "flatcap listar" in str(erro.value)

    @pytest.mark.parametrize(
        ("campo", "falta"), [("matricula1", "matrícula"), ("prof1", "nome")]
    )
    def test_cadastro_incompleto_recusa_dizendo_o_que_falta(self, cfg, redcap, campo, falta):
        redcap([{**REGISTRO, campo: ""}])
        with pytest.raises(ClienteIncompletoError) as erro:
            preparar(cfg, "42", agora=AGORA)
        assert falta in str(erro.value)
        # REGRESSÃO da 1.13.0: as duas últimas frases saíam coladas.
        assert "rode de novo.\nO `flatcap listar`" in str(erro.value)

    def test_pasta_ja_existente_carrega_o_caminho_no_erro(self, cfg, redcap, root):
        # A pasta do PROJETO. A do cliente, sozinha, é reaproveitada desde a
        # 1.1.0 — é o cliente que voltou com outro trabalho.
        (root / "00742 - José Antônio de Sá" / "Projeto 042").mkdir(parents=True)
        redcap([REGISTRO])
        with pytest.raises(ProjetoExistenteError) as erro:
            preparar(cfg, "42", agora=AGORA)
        assert erro.value.pasta.exists()

    def test_pasta_renomeada_a_mao_tambem_e_encontrada(self, cfg, redcap, root):
        """
        A pasta do cliente é achada pela matrícula e reaproveitada **como está
        no disco**, inclusive renomeada à mão. Até a 1.0.0 achá-la era recusar;
        desde a 1.1.0 é pôr o projeto novo dentro dela.
        """
        renomeada = root / "00742 (em andamento)"
        renomeada.mkdir()
        redcap([REGISTRO])
        plano = preparar(cfg, "42", agora=AGORA)
        assert plano.raiz == renomeada / "Projeto 042"
        assert not plano.cliente_novo

    def test_sem_anexo_a_pasta_e_planejada_assim_mesmo(self, cfg, redcap):
        redcap([REGISTRO], anexo=None)
        plano = preparar(cfg, "42", agora=AGORA)
        assert not plano.tem_anexo
        assert plano.banco is None


# ── Executar ────────────────────────────────────────────────────────────────


class TestExecutar:
    def test_cria_a_pasta_as_subpastas_e_os_dois_arquivos(self, cfg, redcap):
        redcap([REGISTRO])
        plano = preparar(cfg, "42", agora=AGORA)
        executar(plano)
        assert plano.raiz.is_dir()
        for nome in SUBPASTAS:
            assert (plano.raiz / nome).is_dir()
        assert (plano.raiz / ARQUIVO_PROJETO).is_file()
        assert (plano.raiz / ARQUIVO_HISTORICO).is_file()

    def test_o_banco_baixado_vai_para_dados_originais(self, cfg, redcap):
        redcap([REGISTRO])
        plano = preparar(cfg, "42", agora=AGORA)
        executar(plano)
        assert plano.banco.caminho.parent.name == PASTA_DADOS
        assert plano.banco.caminho.read_bytes() == ANEXO.conteudo

    def test_o_texto_do_plano_e_o_arquivo_gravado(self, cfg, redcap):
        redcap([REGISTRO])
        plano = preparar(cfg, "42", agora=AGORA)
        executar(plano)
        assert (plano.raiz / ARQUIVO_PROJETO).read_text(
            encoding="utf-8"
        ) == plano.projeto_yaml

    @pytest.mark.skipif(
        # `os.geteuid` só existe no POSIX: chamado direto, derrubava a coleta do
        # arquivo inteiro no Windows.
        getattr(os, "geteuid", lambda: -1)() == 0,
        reason="o root do POSIX ignora bit de permissão",
    )
    def test_o_redcap_nasce_somente_leitura(self, cfg, redcap):
        redcap([REGISTRO])
        plano = preparar(cfg, "42", agora=AGORA)
        executar(plano)
        modo = plano.banco.caminho.stat().st_mode
        assert not modo & stat.S_IWUSR

    def test_o_modo_e_conferido_mesmo_como_root(self, cfg, redcap):
        redcap([REGISTRO])
        plano = preparar(cfg, "42", agora=AGORA)
        executar(plano)
        assert marcar_somente_leitura(plano.banco.caminho)

    def test_a_pasta_que_apareceu_entre_a_simulacao_e_a_execucao(self, cfg, redcap):
        redcap([REGISTRO])
        plano = preparar(cfg, "42", agora=AGORA)
        plano.raiz.mkdir(parents=True)
        with pytest.raises(ProjetoExistenteError) as erro:
            executar(plano)
        assert "entre a simulação e a execução" in str(erro.value)


class TestProjetoYaml:
    def _corpo(self, plano) -> dict:
        return yaml.safe_load(plano.projeto_yaml)

    def test_os_campos_do_apendice_c(self, cfg, redcap):
        redcap([REGISTRO])
        corpo = self._corpo(preparar(cfg, "42", agora=AGORA))
        assert set(corpo) >= {
            "record_id", "tipo", "matricula", "nome", "criado_em", "prazo",
            "status", "analises", "dados",
        }

    def test_matricula_e_record_id_saem_entre_aspas(self, cfg, redcap):
        redcap([REGISTRO])
        texto = preparar(cfg, "42", agora=AGORA).projeto_yaml
        assert "matricula: '00742'" in texto
        assert "record_id: '42'" in texto

    def test_o_prazo_nasce_nulo(self, cfg, redcap):
        """
        São 10 dias úteis contados da reunião, e a data da reunião está no
        calendário, não no REDCap.
        """
        redcap([REGISTRO])
        assert self._corpo(preparar(cfg, "42", agora=AGORA))["prazo"] is None

    def test_nao_ha_ancora_nem_alias(self, cfg, redcap):
        """
        `criado_em` e a `data` do banco são o mesmo objeto `date`, e o PyYAML
        deduplica. É YAML válido e volta certo na leitura — mas este arquivo
        existe para ser editado à mão, e apagar a linha que carrega a âncora
        deixaria o alias órfão, quebrando o arquivo **inteiro**.
        """
        redcap([REGISTRO])
        texto = preparar(cfg, "42", agora=AGORA).projeto_yaml
        assert "&id" not in texto
        assert "*id" not in texto

    def test_nome_com_dois_pontos_nao_quebra_o_arquivo(self, cfg, redcap):
        redcap([{**REGISTRO, "prof1": "Fulano: o Segundo"}])
        corpo = self._corpo(preparar(cfg, "42", agora=AGORA))
        assert corpo["nome"] == "Fulano: o Segundo"

    def test_o_cabecalho_explica_os_campos(self, cfg, redcap):
        redcap([REGISTRO])
        texto = preparar(cfg, "42", agora=AGORA).projeto_yaml
        assert "não\n# sobrescreve" in texto or "não sobrescreve" in texto


class TestHistorico:
    def test_a_primeira_linha_ja_nasce_escrita(self, cfg, redcap):
        redcap([REGISTRO])
        plano = preparar(cfg, "42", agora=AGORA)
        executar(plano)
        (linha,) = linhas_do_historico(plano.raiz)
        assert "flatcap novo 42" in linha
        assert plano.banco.caminho.name in linha

    def test_sem_anexo_a_linha_diz_isso(self, cfg, redcap):
        redcap([REGISTRO], anexo=None)
        plano = preparar(cfg, "42", agora=AGORA)
        executar(plano)
        assert "não tem anexo" in linhas_do_historico(plano.raiz)[0]

    def test_anotar_acrescenta_no_fim(self, projeto_vazio):
        antes = len(linhas_do_historico(projeto_vazio))
        anotar(projeto_vazio, "uma ação qualquer", datetime(2026, 9, 9, 15, 0))
        linhas = linhas_do_historico(projeto_vazio)
        assert len(linhas) == antes + 1
        assert "2026-09-09 15:00" in linhas[-1]

    def test_o_formato_da_linha_e_o_mesmo_para_todo_comando(self, projeto_vazio):
        """
        Fixado antes de haver mais de um comando, justamente para que nenhum
        inventasse o próprio.
        """
        anotar(projeto_vazio, "ação", datetime(2026, 9, 9, 15, 0))
        assert linhas_do_historico(projeto_vazio)[-1].startswith("- **2026-09-09 15:00** — ")


class TestTamanhoLegivel:
    @pytest.mark.parametrize(
        ("bytes_", "esperado"),
        [(0, "0 B"), (512, "512 B"), (1024, "1,0 KiB"), (1536, "1,5 KiB"),
         (1048576, "1,0 MiB")],
    )
    def test_com_virgula_decimal(self, bytes_, esperado):
        """
        Pública porque a Fase 3 imprime a mesma coluna: dois formatadores
        diferentes para a mesma grandeza é como um relatório acaba com "1,5 MiB"
        numa tabela e "1572864" na seguinte.
        """
        assert tamanho_legivel(bytes_) == esperado


def test_o_executar_reverte_o_que_ja_criou_quando_falha(cfg, redcap, monkeypatch):
    """
    As Fases 3, 5 e 6 desfazem o que já fizeram quando algo falha no meio; esta
    não desfaz, e a mensagem da CLI admite: "A pasta pode ter ficado pela
    metade". Vale ou implementar a reversão, ou registrar a assimetria como
    deliberada — mas não deixar a diferença sem explicação.
    """
    redcap([REGISTRO])
    plano = preparar(cfg, "42", agora=AGORA)

    original = type(plano.raiz).mkdir
    chamadas = {"n": 0}

    def falhar_na_terceira(self, *args, **kwargs):
        chamadas["n"] += 1
        if chamadas["n"] == 3:
            raise OSError("disco cheio (simulado)")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(type(plano.raiz), "mkdir", falhar_na_terceira)
    with pytest.raises(OSError):
        executar(plano)
    assert not plano.raiz.exists(), "a pasta pela metade ficou no disco"
