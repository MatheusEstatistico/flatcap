"""
Do questionário para o domínio — Fase 1.

Toda a ramificação do `intro` mora em `normalizar`. Do resto do sistema existe
apenas um `Cliente` com `matricula` e `nome`, sem `if` espalhado — e se amanhã
surgir um `intro = 3` (residente, técnico, externo), há um único ponto a
alterar.

A armadilha desta fase está registrada em um teste com nome próprio: **`prof1`
não tem lógica de ramificação**.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from flatcap.modelo import (
    ALUNO,
    CAMPO_ANEXO,
    CAMPO_FINALIDADE,
    CAMPO_FINALIDADE_OUTROS,
    CAMPO_OBJETIVOS,
    CAMPOS_REDCAP,
    INDEFINIDO,
    PROFESSOR,
    Cliente,
    mais_recentes,
    normalizar,
    normalizar_varios,
)


class TestNormalizar:
    def test_intro_1_e_professor(self):
        cliente = normalizar(
            {"record_id": "40", "intro": "1", "matricula1": "00740", "prof1": "Ana"}
        )
        assert (cliente.tipo, cliente.matricula, cliente.nome) == (PROFESSOR, "00740", "Ana")

    def test_intro_2_e_aluno(self):
        cliente = normalizar(
            {
                "record_id": "41", "intro": "2", "matricula2": "20241234",
                "aluno2": "Bruno", "prof1": "Ana (orientadora)",
            }
        )
        assert (cliente.tipo, cliente.matricula, cliente.nome) == (ALUNO, "20241234", "Bruno")

    def test_prof1_nao_tem_ramificacao_e_por_isso_nao_e_o_discriminante(self, registros):
        """
        No DataDictionary, `matricula1` e `matricula2` só aparecem conforme o
        `intro`, mas `prof1` é obrigatório e vem preenchido em **toda**
        solicitação — inclusive nas de aluno, onde guarda o orientador.

        A regra intuitiva "use o primeiro par com algum conteúdo" classificaria
        todo registro sem `intro` como do professor. A regra correta usa a
        **matrícula** como discriminante: ela tem ramificação, então só uma das
        duas chega preenchida.
        """
        registro = next(r for r in registros if r["record_id"] == "43")
        assert registro["intro"] == ""
        assert registro["prof1"], "o fixture precisa ter prof1 preenchido para provar isto"
        cliente = normalizar(registro)
        assert cliente.matricula == registro["matricula2"]
        assert cliente.nome.startswith("Maria")

    def test_intro_desconhecido_e_indefinido_mas_ainda_identifica(self):
        cliente = normalizar(
            {"record_id": "9", "intro": "7", "matricula1": "00009", "prof1": "Ricardo"}
        )
        assert cliente.tipo == INDEFINIDO
        assert cliente.matricula == "00009"

    def test_sem_matricula_nenhuma_sobra_o_nome(self, registros):
        registro = next(r for r in registros if r["record_id"] == "44")
        cliente = normalizar(registro)
        assert cliente.matricula == ""
        assert cliente.nome
        assert not cliente.identificado

    def test_campos_ausentes_nao_estouram(self):
        cliente = normalizar({})
        assert cliente == Cliente("", INDEFINIDO, "", "", False)

    def test_none_vira_texto_vazio(self):
        assert normalizar({"record_id": None, "prof1": None}).nome == ""

    def test_espacos_sao_aparados(self, registros):
        registro = next(r for r in registros if r["record_id"] == "45")
        cliente = normalizar(registro)
        assert cliente.matricula == "00745"
        assert cliente.nome == "Lúcia Helena D'Ávila"

    def test_tem_anexo_vem_do_campo_database(self):
        assert normalizar({CAMPO_ANEXO: "banco.xlsx"}).tem_anexo is True
        assert normalizar({CAMPO_ANEXO: ""}).tem_anexo is False

    def test_identificado_exige_matricula_e_nome(self):
        assert Cliente("1", PROFESSOR, "00742", "Ana", True).identificado
        assert not Cliente("1", PROFESSOR, "00742", "", True).identificado
        assert not Cliente("1", PROFESSOR, "", "Ana", True).identificado

    def test_o_cliente_e_imutavel(self):
        cliente = normalizar({"record_id": "1"})
        with pytest.raises(FrozenInstanceError):
            cliente.nome = "outro"  # type: ignore[misc]


class TestNormalizarVarios:
    def test_a_ordem_do_redcap_e_mantida(self, registros):
        clientes = normalizar_varios(registros)
        assert [c.record_id for c in clientes] == [r["record_id"] for r in registros]

    def test_todos_os_registros_do_fixture_normalizam(self, registros):
        assert len(normalizar_varios(registros)) == len(registros)


class TestMaisRecentes:
    """
    "Quais são as N mais recentes" é regra de negócio e mora aqui, não na `cli`
    — dá para testá-la sem simular terminal.
    """

    def _clientes(self, ids):
        return [Cliente(i, PROFESSOR, i, f"C{i}", False) for i in ids]

    def test_corta_pelos_maiores_record_id(self):
        escolhidos = mais_recentes(self._clientes(["9", "10", "11", "8"]), 2)
        assert {c.record_id for c in escolhidos} == {"10", "11"}

    def test_a_ordem_da_tabela_nao_muda(self):
        """
        O corte tira as linhas antigas e não reordena o que sobra.
        """
        escolhidos = mais_recentes(self._clientes(["9", "10", "11", "8"]), 2)
        assert [c.record_id for c in escolhidos] == ["10", "11"]

    def test_a_comparacao_e_numerica_e_nao_alfabetica(self):
        """
        Alfabeticamente, "9" > "10". O REDCap numera sequencialmente.
        """
        escolhidos = mais_recentes(self._clientes(["9", "10"]), 1)
        assert escolhidos[0].record_id == "10"

    def test_record_id_nao_numerico_vai_para_o_fim(self):
        escolhidos = mais_recentes(self._clientes(["1", "2", "abc"]), 2)
        assert "abc" not in {c.record_id for c in escolhidos}

    @pytest.mark.parametrize("quantos", [0, -1])
    def test_quantidade_invalida_devolve_tudo(self, quantos):
        clientes = self._clientes(["1", "2"])
        assert mais_recentes(clientes, quantos) == clientes

    def test_pedir_mais_do_que_existe_devolve_tudo(self):
        clientes = self._clientes(["1", "2"])
        assert mais_recentes(clientes, 10) == clientes


def test_os_campos_pedidos_ao_redcap_estao_na_lista():
    """
    Se `database` não for pedido, `tem_anexo` fica permanentemente falso — que é
    uma resposta errada em silêncio. A lista mora em um lugar só.

    São os sete do roteiro mais os três da primeira página do relatório
    (`fin`, `outros1`, `obj1`), que entraram com a finalidade e os objetivos.
    """
    assert set(CAMPOS_REDCAP) == {
        "record_id", "intro", "matricula1", "prof1", "matricula2", "aluno2", CAMPO_ANEXO,
        CAMPO_FINALIDADE, CAMPO_FINALIDADE_OUTROS, CAMPO_OBJETIVOS,
    }
