# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
"""
O painel do `flatcap status` — os projetos que já têm pasta, com o status e o prazo.

Três promessas, e cada uma tem a sua classe:

**O painel é o disco.** Uma linha por pasta `Projeto NNN` com ficha, na ordem do
`record_id`; os `finalizado` saem, e o que não se lê fica de fora com nome e
sobrenome, e não em silêncio.

**O status e o prazo são os que você escreveu.** O status é reconhecido sem
maiúscula nem acento, e o que não é nenhum deles aparece como está. O prazo é a
data final, nas duas formas que se digitam.

**ATRASADO é o prazo que passou sem o projeto estar pronto.** O dia do prazo ainda
não é atraso, e o relógio é o de `agora=`, nunca o da máquina.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import date, datetime

from conftest import MATRICULA, NOME, PASTA, escrever_ficha
from flatcap.painel import LinhaDoPainel, montar_painel
from flatcap.projeto import (
    STATUS_AGUARDANDO_BANCO,
    STATUS_CALCULO_AMOSTRAL,
    STATUS_EM_ANDAMENTO,
    STATUS_NAO_INICIADO,
    STATUS_PRONTO,
)

# Uma quinta-feira, a da semana do prazo dos exemplos.
AGORA = datetime(2026, 10, 29, 14, 30)


def _projeto(root, record_id: str, *, matricula: str = MATRICULA, nome: str = NOME, **ficha):
    """
    `root/<matrícula - nome>/Projeto NNN/projeto.yaml`, com a ficha escrita à mão.

    O nome da pasta é escrito aqui, e não pelo `nomes.nome_do_projeto`, pelo motivo do
    `conftest.PROJETO`: se o formato mudar, é aqui que o teste precisa quebrar.
    """
    raiz = root / f"{matricula} - {nome}" / f"Projeto {int(record_id):03d}"
    raiz.mkdir(parents=True)
    escrever_ficha(raiz, record_id=record_id, matricula=matricula, nome=nome, **ficha)
    return raiz


def _linha(painel, record_id: str) -> LinhaDoPainel:
    (linha,) = [linha for linha in painel.linhas if linha.record_id == record_id]
    return linha


# ── O painel é o disco ──────────────────────────────────────────────────────


class TestQuemEntra:
    def test_uma_linha_por_projeto_na_ordem_do_record_id(self, root):
        """
        Como número, e não como texto: o `6` antes do `41`, e o `137` por último. É a
        ordem do `flatcap listar`.
        """
        for record_id in ("137", "6", "41"):
            _projeto(root, record_id)
        _projeto(root, "23", matricula="12346", nome="Ana Lima")

        painel = montar_painel(root, agora=AGORA)
        assert [linha.record_id for linha in painel.linhas] == ["6", "23", "41", "137"]

    def test_a_linha_traz_a_matricula_o_nome_e_a_pasta_local(self, root):
        raiz = _projeto(root, "6")
        (linha,) = montar_painel(root, agora=AGORA).linhas
        assert linha.matricula == MATRICULA
        assert linha.nome == NOME
        assert linha.pasta == raiz
        assert linha.pasta_local == "Projeto 006"

    def test_o_nome_e_o_da_ficha_e_nao_o_da_pasta(self, root):
        """
        A pasta perde a barra e o dois-pontos, que o Windows recusa; a ficha guarda o
        nome como o REDCap o trouxe — e como você o corrigiu.
        """
        raiz = root / "00742 - Thiago NunesNeto" / "Projeto 006"
        raiz.mkdir(parents=True)
        escrever_ficha(raiz, record_id="6", nome="Thiago Nunes/Neto")
        (linha,) = montar_painel(root, agora=AGORA).linhas
        assert linha.nome == "Thiago Nunes/Neto"

    def test_o_finalizado_sai_do_painel_e_entra_na_contagem(self, root):
        _projeto(root, "6", status="finalizado")
        _projeto(root, "41", status="Finalizado")
        _projeto(root, "137")

        painel = montar_painel(root, agora=AGORA)
        assert [linha.record_id for linha in painel.linhas] == ["137"]
        assert painel.finalizados == 2

    def test_a_ficha_que_nao_abre_fica_fora_e_e_listada(self, root):
        _projeto(root, "6")
        quebrada = root / PASTA / "Projeto 041"
        quebrada.mkdir(parents=True)
        (quebrada / "projeto.yaml").write_text(
            "nome: Fulano: o Segundo\n", encoding="utf-8", newline="\n"
        )

        painel = montar_painel(root, agora=AGORA)
        assert [linha.record_id for linha in painel.linhas] == ["6"]
        assert painel.ilegiveis == (quebrada,)

    def test_a_pasta_no_formato_antigo_fica_fora_e_e_listada(self, root):
        """
        O `projeto.yaml` na pasta do cliente, como antes da 1.1.0. Ela não tem como
        entrar na tabela — não há `Projeto NNN` —, mas também não some.
        """
        antiga = root / "88888 - Antiga"
        antiga.mkdir()
        escrever_ficha(antiga, record_id="88", matricula="88888")

        painel = montar_painel(root, agora=AGORA)
        assert painel.linhas == ()
        assert painel.antigas == (antiga,)

    def test_root_vazio(self, root):
        painel = montar_painel(root, agora=AGORA)
        assert painel.linhas == ()
        assert painel.finalizados == 0

    def test_nao_escreve_nada(self, root):
        raiz = _projeto(root, "6", prazo="2026-10-01")
        antes = {arquivo: arquivo.read_bytes() for arquivo in root.rglob("*") if arquivo.is_file()}
        montar_painel(root, agora=AGORA)
        depois = {arquivo: arquivo.read_bytes() for arquivo in root.rglob("*") if arquivo.is_file()}
        assert antes == depois
        assert sorted(p.name for p in raiz.iterdir()) == ["projeto.yaml"]


def test_o_painel_nao_carrega_pandas():
    """
    O `flatcap status` lê fichas, e só. Em subprocesso porque `sys.modules` é
    global: outro teste já teria importado o `pandas`.
    """
    codigo = (
        "import sys; import flatcap.painel;"
        "print(int('pandas' in sys.modules), int('matplotlib' in sys.modules))"
    )
    saida = subprocess.run(
        [sys.executable, "-c", codigo], capture_output=True, text=True, check=True
    ).stdout.strip()
    assert saida == "0 0"


# ── O status e o prazo são os que você escreveu ─────────────────────────────


class TestStatus:
    def test_os_status_saem_na_grafia_da_lista(self, root):
        _projeto(root, "6", status="Em Andamento")
        _projeto(root, "41", status="nao iniciado")
        _projeto(root, "137", status="AGUARDANDO BANCO DE DADOS")
        _projeto(root, "140", status="calculo amostral")

        painel = montar_painel(root, agora=AGORA)
        assert _linha(painel, "6").status == STATUS_EM_ANDAMENTO
        assert _linha(painel, "41").status == STATUS_NAO_INICIADO
        assert _linha(painel, "137").status == STATUS_AGUARDANDO_BANCO
        assert _linha(painel, "140").status == STATUS_CALCULO_AMOSTRAL
        assert all(linha.status_reconhecido for linha in painel.linhas)

    def test_o_novo_das_fichas_de_antes_e_o_nao_iniciado(self, root):
        """
        Toda ficha criada antes da 1.17.0 diz `status: novo`, e é o `não iniciado`
        de hoje.
        """
        _projeto(root, "6", status="novo")
        assert _linha(montar_painel(root, agora=AGORA), "6").status == STATUS_NAO_INICIADO

    def test_status_fora_da_lista_aparece_como_esta_escrito(self, root):
        """
        `entregue` era sugerido no cabeçalho de antes, e pode ser o `pronto` ou o
        `finalizado`. O painel não adivinha: mostra o que está lá, marcado.
        """
        _projeto(root, "6", status="entregue")
        _projeto(root, "41", status="null")

        painel = montar_painel(root, agora=AGORA)
        assert _linha(painel, "6").status == "entregue"
        assert _linha(painel, "41").status == ""
        assert not any(linha.status_reconhecido for linha in painel.linhas)
        assert len(painel.status_fora_da_lista) == 2


class TestPrazo:
    def test_as_duas_formas_de_escrever_a_data(self, root):
        _projeto(root, "6", prazo="2026-11-04")
        _projeto(root, "41", prazo="04/11/2026")

        painel = montar_painel(root, agora=AGORA)
        assert _linha(painel, "6").prazo == date(2026, 11, 4)
        assert _linha(painel, "41").prazo == date(2026, 11, 4)

    def test_sem_prazo(self, root):
        _projeto(root, "6")
        painel = montar_painel(root, agora=AGORA)
        assert _linha(painel, "6").prazo is None
        assert painel.sem_prazo == painel.linhas

    def test_prazo_que_nao_e_data_fica_como_esta_escrito(self, root):
        """
        Não vira "sem prazo": alguém escreveu alguma coisa ali, e o painel precisa
        mostrar o quê.
        """
        _projeto(root, "6", prazo="semana que vem")
        _projeto(root, "41", prazo="31/02/2026")

        painel = montar_painel(root, agora=AGORA)
        assert _linha(painel, "6").prazo is None
        assert _linha(painel, "6").prazo_escrito == "semana que vem"
        assert _linha(painel, "41").prazo_escrito == "31/02/2026"
        assert painel.sem_prazo == ()
        assert len(painel.prazos_que_nao_sao_data) == 2


# ── ATRASADO ────────────────────────────────────────────────────────────────


class TestAtrasado:
    def test_o_prazo_que_passou_esta_atrasado(self, root):
        _projeto(root, "6", prazo="2026-10-28")
        painel = montar_painel(root, agora=AGORA)
        assert _linha(painel, "6").atrasado
        assert painel.atrasados == painel.linhas

    def test_o_dia_do_prazo_ainda_nao_e_atraso(self, root):
        _projeto(root, "6", prazo="29/10/2026")
        assert not _linha(montar_painel(root, agora=AGORA), "6").atrasado

    def test_o_prazo_que_vem_nao_esta_atrasado(self, root):
        _projeto(root, "6", prazo="2026-11-04")
        assert not _linha(montar_painel(root, agora=AGORA), "6").atrasado

    def test_o_projeto_pronto_nao_esta_atrasado(self, root):
        """
        O prazo é o do relatório, e o projeto pronto já o tem.
        """
        _projeto(root, "6", prazo="2026-10-01", status=STATUS_PRONTO)
        assert not _linha(montar_painel(root, agora=AGORA), "6").atrasado

    def test_qualquer_outro_status_atrasa(self, root):
        for record_id, status in (
            ("6", "não iniciado"),
            ("41", "aguardando banco de dados"),
            ("137", "em andamento"),
            ("140", "entregue"),
            ("152", "cálculo amostral"),
        ):
            _projeto(root, record_id, prazo="2026-10-01", status=status)
        painel = montar_painel(root, agora=AGORA)
        assert len(painel.atrasados) == 5

    def test_prazo_que_nao_e_data_nao_atrasa(self, root):
        _projeto(root, "6", prazo="ontem")
        assert not _linha(montar_painel(root, agora=AGORA), "6").atrasado

    def test_o_relogio_e_o_de_agora(self, root):
        _projeto(root, "6", prazo="2026-10-28")
        assert not _linha(montar_painel(root, agora=datetime(2026, 10, 28, 23, 59)), "6").atrasado
        assert _linha(montar_painel(root, agora=datetime(2026, 10, 29, 0, 1)), "6").atrasado
        assert montar_painel(root, agora=AGORA).hoje == AGORA.date()
