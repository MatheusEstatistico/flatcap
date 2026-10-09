# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Nomes de pasta e a busca no disco — Fase 2 (antecipada na Fase 1).

Dois cuidados que só apareceram nos testes e que passariam despercebidos num
teste manual com dados bem-comportados: a **ordem** da limpeza, e a busca por
prefixo que não pode confundir a matrícula 1234 com a 12345.
"""

from __future__ import annotations

import pytest

from flatcap.nomes import (
    PROIBIDOS,
    SEPARADOR,
    NomeInvalidoError,
    localizar_pasta,
    nome_pasta,
    sanitizar,
)


class TestSanitizar:
    @pytest.mark.parametrize("proibido", list(PROIBIDOS))
    def test_todo_caractere_proibido_no_windows_sai(self, proibido):
        assert proibido not in sanitizar(f"Ana{proibido}Maria")

    def test_a_ordem_da_limpeza_nao_gruda_palavras(self):
        """
        Remover a faixa `\\x00-\\x1f` inteira primeiro transformava `Ana\\tMaria`
        em `AnaMaria`. A ordem certa remove só os controles que **não** são
        espaço em branco, depois os proibidos, e só então colapsa.
        """
        assert sanitizar("Ana\tMaria") == "Ana Maria"
        assert sanitizar("Ana\nMaria") == "Ana Maria"

    def test_remover_proibido_deixa_buraco_que_o_colapso_fecha(self):
        assert sanitizar("Ana / Maria") == "Ana Maria"

    def test_espacos_multiplos_viram_um(self):
        assert sanitizar("Ana    Maria") == "Ana Maria"

    def test_espaco_e_ponto_no_fim_saem(self):
        """
        O Windows remove espaços finais em silêncio, o que faz o caminho gravado
        no `projeto.yaml` deixar de bater com o caminho real em disco. É um bug
        difícil de diagnosticar depois.
        """
        assert sanitizar("Ana Maria ") == "Ana Maria"
        assert sanitizar("Ana Maria.") == "Ana Maria"
        assert sanitizar("Ana Maria. . ") == "Ana Maria"

    def test_acento_e_apostrofo_ficam(self):
        assert sanitizar("Lúcia Helena D'Ávila") == "Lúcia Helena D'Ávila"

    @pytest.mark.parametrize("entrada", ["", "   ", None, "///", "..."])
    def test_o_que_nao_sobra_nada_vira_vazio(self, entrada):
        assert sanitizar(entrada) == ""


class TestNomePasta:
    def test_o_formato_e_matricula_separador_nome(self):
        assert nome_pasta("00742", "José Antônio de Sá") == "00742 - José Antônio de Sá"

    def test_a_matricula_e_texto_e_nao_perde_o_zero(self):
        """
        `int("00742")` devolve `742` e a pasta deixa de bater com o registro. O
        valor só serve para nomear e localizar — nunca para conta.
        """
        assert nome_pasta("00742", "Ana").startswith("00742")

    def test_nome_vazio_nao_impede_o_trabalho(self):
        """
        Só a matrícula é indispensável; sem ela a pasta sairia com um nome que
        você teria de corrigir à mão, e o `listar` deixaria de reencontrá-la.
        """
        assert nome_pasta("00742", "") == "00742"

    @pytest.mark.parametrize("matricula", ["", "  ", "///"])
    def test_sem_matricula_recusa(self, matricula):
        with pytest.raises(NomeInvalidoError) as erro:
            nome_pasta(matricula, "Ana")
        # REGRESSÃO da 1.13.0: as duas frases saíam coladas, `''Ver REDCap`.
        assert f"Recebido: {matricula!r}\n" in str(erro.value)

    def test_o_separador_e_o_do_modulo(self):
        assert SEPARADOR in nome_pasta("1", "Ana")


class TestLocalizarPasta:
    """
    A busca é **por matrícula**, e não por igualdade com `nome_pasta`: a pasta
    pode ter sido renomeada à mão, criada antes do FlatCap ou ter a grafia
    corrigida depois. A matrícula é a parte que não muda.
    """

    def test_encontra_a_pasta_completa(self, root):
        (root / "00742 - José Antônio de Sá").mkdir()
        assert localizar_pasta(root, "00742").name.startswith("00742")

    def test_encontra_a_pasta_renomeada_a_mao(self, root):
        (root / "00742 – Jose (URGENTE)").mkdir()
        assert localizar_pasta(root, "00742") is not None

    def test_encontra_a_pasta_so_com_a_matricula(self, root):
        (root / "00742").mkdir()
        assert localizar_pasta(root, "00742") is not None

    def test_a_matricula_1234_nao_reivindica_a_pasta_do_12345(self, root):
        """
        O casamento exige que o caractere seguinte não seja dígito.
        """
        (root / "12345 - Bruno").mkdir()
        assert localizar_pasta(root, "1234") is None

    def test_o_12345_encontra_a_propria(self, root):
        (root / "12345 - Bruno").mkdir()
        (root / "1234 - Ana").mkdir()
        assert localizar_pasta(root, "12345").name.startswith("12345")

    def test_arquivo_solto_com_o_nome_nao_e_pasta(self, root):
        (root / "00742 - Ana.txt").write_text("x", encoding="utf-8")
        assert localizar_pasta(root, "00742") is None

    def test_matricula_vazia_nao_casa_com_tudo(self, root):
        (root / "00742 - Ana").mkdir()
        assert localizar_pasta(root, "") is None

    def test_root_inexistente_nao_estoura(self, tmp_path):
        assert localizar_pasta(tmp_path / "nao_existe", "00742") is None

    def test_a_matricula_com_espaco_e_limpa_antes_de_buscar(self, root):
        (root / "00745 - Lúcia").mkdir()
        assert localizar_pasta(root, " 00745 ") is not None
