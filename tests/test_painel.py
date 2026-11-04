# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
"""
O `flatcap status` — o painel dos projetos que já têm pasta, com o status e o prazo, e a
troca do status de um deles.

Quatro promessas, e cada uma tem a sua classe:

**O painel é o disco.** Uma linha por pasta `Projeto NNN` com ficha, na ordem do
`record_id`; os `finalizado` saem, e o que não se lê fica de fora com nome e
sobrenome, e não em silêncio.

**O status e o prazo são os que você escreveu.** O status é reconhecido sem
maiúscula nem acento, e o que não é nenhum deles aparece como está. O prazo é a
data final, nas duas formas que se digitam.

**ATRASADO é o prazo que passou sem o projeto estar pronto.** O dia do prazo ainda
não é atraso, e o relógio é o de `agora=`, nunca o da máquina.

**A troca escreve a palavra da ficha e a linha do histórico — e só quando muda.** O
resto da ficha fica como você o deixou, e a linha diz de onde para onde, com a data.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import date, datetime

import pytest

from conftest import MATRICULA, NOME, PASTA, escrever_ficha, linhas_do_historico, sem_aspas
from flatcap.ficha import ProjetoNaoEncontradoError
from flatcap.ficha import ler as ler_ficha
from flatcap.painel import (
    LinhaDoPainel,
    executar_troca,
    montar_painel,
    painel_do_projeto,
    preparar_troca,
)
from flatcap.projeto import (
    ARQUIVO_HISTORICO,
    STATUS,
    STATUS_AGUARDANDO_BANCO,
    STATUS_CALCULO_AMOSTRAL,
    STATUS_EM_ANDAMENTO,
    STATUS_FINALIZADO,
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

    @pytest.mark.parametrize("matricula", ["0189", "01928"])
    def test_a_matricula_sai_com_o_zero_da_frente(self, root, matricula):
        """
        REGRESSÃO da 1.18.0: a ficha escrita pelo `flatcap novo` até ali dizia
        `matricula: 0189`, sem aspas, e o painel mostrava 189 — o `listar`, que lê o
        REDCap, mostrava 0189.
        """
        sem_aspas(_projeto(root, "6", matricula=matricula), "matricula", matricula)

        (linha,) = montar_painel(root, agora=AGORA).linhas
        assert linha.matricula == matricula

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


# ── O painel de um projeto só ───────────────────────────────────────────────


class TestPainelDoProjeto:
    """
    O do `flatcap status <id>`: a linha do painel, e o finalizado também.
    """

    def test_a_linha_e_a_do_painel_de_todos(self, root):
        raiz = _projeto(root, "6", prazo="2026-10-01")
        _projeto(root, "41", prazo="2026-11-04")
        um = painel_do_projeto(raiz, agora=AGORA)
        assert um.linhas == (_linha(montar_painel(root, agora=AGORA), "6"),)
        assert um.hoje == AGORA.date()

    def test_o_finalizado_aparece_e_nao_atrasa(self, root):
        """
        "Como está o 6?" tem resposta depois de ele sair do painel. O prazo é o do
        relatório, e o projeto finalizado já o tem.
        """
        raiz = _projeto(root, "6", status="Finalizado", prazo="2026-10-01")
        (linha,) = painel_do_projeto(raiz, agora=AGORA).linhas
        assert linha.status == STATUS_FINALIZADO
        assert linha.status_reconhecido
        assert not linha.atrasado
        assert montar_painel(root, agora=AGORA).linhas == ()

    def test_o_status_fora_da_lista_e_o_prazo_que_nao_e_data_tambem_aparecem(self, root):
        raiz = _projeto(root, "6", status="entregue", prazo="semana que vem")
        painel = painel_do_projeto(raiz, agora=AGORA)
        assert len(painel.status_fora_da_lista) == 1
        assert len(painel.prazos_que_nao_sao_data) == 1

    def test_nao_escreve_nada(self, root):
        raiz = _projeto(root, "6")
        antes = (raiz / "projeto.yaml").read_bytes()
        painel_do_projeto(raiz, agora=AGORA)
        assert (raiz / "projeto.yaml").read_bytes() == antes
        assert sorted(p.name for p in raiz.iterdir()) == ["projeto.yaml"]


# ── A troca de status ───────────────────────────────────────────────────────


class TestTroca:
    """
    `flatcap status <id> --<status>`, sem a CLI: o `preparar_troca` decide, e o
    `executar_troca` escreve a ficha e o histórico.
    """

    def test_escreve_o_status_e_a_linha_do_historico(self, root):
        raiz = _projeto(root, "41")
        troca = preparar_troca(root, "41", STATUS_FINALIZADO, agora=AGORA)
        assert troca.muda

        resultado = executar_troca(troca)
        assert resultado.trocado and resultado.avisos == ()
        assert ler_ficha(raiz).status == STATUS_FINALIZADO
        assert linhas_do_historico(raiz) == [
            "- **2026-10-29 14:30** — `flatcap status 41` — "
            "Status de `em andamento` para `finalizado`."
        ]

    def test_o_resto_da_ficha_fica_como_estava(self, root):
        """
        O comentário ao lado do `status:`, as aspas da matrícula e o prazo à moda
        brasileira: tudo como você deixou — é o `definir_status` do relatório.
        """
        raiz = _projeto(root, "41", prazo="04/11/2026", status="em andamento  # combinado")
        caminho = raiz / "projeto.yaml"
        antes = caminho.read_text(encoding="utf-8").splitlines()

        executar_troca(preparar_troca(root, "41", STATUS_AGUARDANDO_BANCO, agora=AGORA))

        depois = caminho.read_text(encoding="utf-8").splitlines()
        assert len(depois) == len(antes)
        (linha_do_status,) = [linha for linha in depois if linha.startswith("status:")]
        assert linha_do_status.startswith("status: aguardando banco de dados")
        assert linha_do_status.endswith("# combinado")
        assert [linha for linha in depois if not linha.startswith("status:")] == [
            linha for linha in antes if not linha.startswith("status:")
        ]

    def test_pela_matricula_do_cliente_de_um_projeto_so(self, root):
        raiz = _projeto(root, "41")
        executar_troca(preparar_troca(root, MATRICULA, STATUS_PRONTO, agora=AGORA))
        assert ler_ficha(raiz).status == STATUS_PRONTO

    @pytest.mark.parametrize(
        ("escrito", "pedido"),
        [
            ("Em Andamento", STATUS_EM_ANDAMENTO),
            ("novo", STATUS_NAO_INICIADO),
            ("calculo_amostral", STATUS_CALCULO_AMOSTRAL),
        ],
    )
    def test_o_status_em_que_o_projeto_ja_esta_nao_escreve_nada(self, root, escrito, pedido):
        """
        A grafia não importa: `Em Andamento` já é o `em andamento`, e o `novo` das fichas
        de antes já é o `não iniciado`. A ficha não é reescrita, e o histórico não diz que
        algo mudou.
        """
        raiz = _projeto(root, "41", status=escrito)
        antes = (raiz / "projeto.yaml").read_bytes()

        troca = preparar_troca(root, "41", pedido, agora=AGORA)
        assert not troca.muda
        resultado = executar_troca(troca)

        assert not resultado.trocado
        assert (raiz / "projeto.yaml").read_bytes() == antes
        assert not (raiz / ARQUIVO_HISTORICO).exists()

    def test_o_status_fora_da_lista_vai_ao_historico_como_estava_escrito(self, root):
        """
        `entregue` não é um dos seis, e não há opção que o devolva; o histórico guarda o
        que estava lá.
        """
        raiz = _projeto(root, "41", status="entregue")
        troca = preparar_troca(root, "41", STATUS_FINALIZADO, agora=AGORA)
        assert troca.anterior == "entregue"
        assert troca.anterior_reconhecido is None

        executar_troca(troca)
        assert linhas_do_historico(raiz)[-1].endswith(
            "Status de `entregue` para `finalizado`."
        )

    def test_a_ficha_sem_status_ganha_a_chave(self, root):
        raiz = _projeto(root, "41", status="null")
        executar_troca(preparar_troca(root, "41", STATUS_EM_ANDAMENTO, agora=AGORA))
        assert ler_ficha(raiz).status == STATUS_EM_ANDAMENTO
        assert linhas_do_historico(raiz)[-1].endswith("Status para `em andamento`.")

    def test_o_finalizado_sai_do_painel_e_a_volta_o_traz(self, root):
        _projeto(root, "41")
        executar_troca(preparar_troca(root, "41", STATUS_FINALIZADO, agora=AGORA))
        painel = montar_painel(root, agora=AGORA)
        assert (painel.linhas, painel.finalizados) == ((), 1)

        executar_troca(preparar_troca(root, "41", STATUS_EM_ANDAMENTO, agora=AGORA))
        painel = montar_painel(root, agora=AGORA)
        assert [linha.status for linha in painel.linhas] == [STATUS_EM_ANDAMENTO]
        assert painel.finalizados == 0

    def test_cada_troca_e_uma_linha_do_historico(self, root):
        """
        É a linha que a troca à mão não deixa: a data de cada passagem, e de onde para
        onde.
        """
        raiz = _projeto(root, "41", status="não iniciado")
        for status, quando in (
            (STATUS_CALCULO_AMOSTRAL, datetime(2026, 10, 1, 9, 0)),
            (STATUS_EM_ANDAMENTO, datetime(2026, 10, 8, 10, 15)),
            (STATUS_FINALIZADO, datetime(2026, 10, 30, 17, 45)),
        ):
            executar_troca(preparar_troca(root, "41", status, agora=quando))
        assert linhas_do_historico(raiz) == [
            "- **2026-10-01 09:00** — `flatcap status 41` — "
            "Status de `não iniciado` para `cálculo amostral`.",
            "- **2026-10-08 10:15** — `flatcap status 41` — "
            "Status de `cálculo amostral` para `em andamento`.",
            "- **2026-10-30 17:45** — `flatcap status 41` — "
            "Status de `em andamento` para `finalizado`.",
        ]

    def test_status_que_nao_e_da_lista_e_defeito_de_quem_chamou(self, root):
        """
        A CLI só passa os seis, um por opção; um texto qualquer aqui seria o FlatCap
        escrevendo na ficha um status que o painel não reconhece.
        """
        raiz = _projeto(root, "41")
        antes = (raiz / "projeto.yaml").read_bytes()
        with pytest.raises(ValueError, match="status desconhecido"):
            preparar_troca(root, "41", "concluido", agora=AGORA)
        assert (raiz / "projeto.yaml").read_bytes() == antes

    def test_o_projeto_que_nao_existe(self, root):
        _projeto(root, "41")
        with pytest.raises(ProjetoNaoEncontradoError):
            preparar_troca(root, "999", STATUS_FINALIZADO, agora=AGORA)

    def test_a_ficha_que_nao_se_grava_fica_como_estava(self, root, monkeypatch):
        """
        Aberta noutro programa, sem permissão de escrita: o erro sobe, a ficha é a de
        antes, letra por letra, e o histórico não diz que nada mudou.
        """
        raiz = _projeto(root, "41")
        antes = (raiz / "projeto.yaml").read_bytes()

        def falhar(*_a, **_k):
            raise PermissionError("arquivo aberto noutro programa (simulado)")

        monkeypatch.setattr("flatcap.ficha.escrever_atomico", falhar)
        with pytest.raises(PermissionError):
            executar_troca(preparar_troca(root, "41", STATUS_FINALIZADO, agora=AGORA))
        assert (raiz / "projeto.yaml").read_bytes() == antes
        assert not (raiz / ARQUIVO_HISTORICO).exists()

    def test_o_historico_que_nao_se_escreve_vira_aviso_e_a_troca_fica(
        self, root, monkeypatch
    ):
        """
        Como em todo comando que escreve: o recibo que falta não desfaz o que foi pedido.
        """
        raiz = _projeto(root, "41")

        def falhar(*_a, **_k):
            raise OSError("disco cheio (simulado)")

        monkeypatch.setattr("flatcap.painel.anotar", falhar)
        resultado = executar_troca(preparar_troca(root, "41", STATUS_FINALIZADO, agora=AGORA))
        assert resultado.trocado
        assert ler_ficha(raiz).status == STATUS_FINALIZADO
        (aviso,) = resultado.avisos
        assert "historico.md" in aviso and "disco cheio" in aviso

    def test_os_seis_status_se_escrevem(self, root):
        raiz = _projeto(root, "41", status="entregue")
        for status in STATUS:
            executar_troca(preparar_troca(root, "41", status, agora=AGORA))
            assert ler_ficha(raiz).status == status
        assert len(linhas_do_historico(raiz)) == len(STATUS)
