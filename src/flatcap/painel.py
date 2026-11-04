# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
"""
O `flatcap status`: o painel dos projetos que já têm pasta, com o status e o prazo — e,
desde a 1.19.0, a troca do status de um deles.

O `flatcap listar` responde "o que chegou?" a partir do REDCap, e procura a pasta de
cada solicitação. Este módulo responde outra pergunta — "como está cada projeto, e qual
passou do prazo?" — e faz o caminho inverso: parte do disco, ficha por ficha, e não
fala com o REDCap. É o que deixa o painel de pé quando o servidor cai ou o token
expira, e o que mantém no painel a pasta cuja matrícula foi corrigida no REDCap depois
de ela existir.

## O que entra

Toda pasta `Projeto NNN` do `FLATCAP_ROOT` com um `projeto.yaml` que abre, menos as
`finalizado`: essas saem do painel e entram só na contagem. A ficha que não abre e a
pasta de cliente no formato anterior à 1.1.0 também ficam de fora, mas não em
silêncio — o painel as lista, para o terminal dizer o que fazer com elas. A ordem é a
do `flatcap listar`, pelo `record_id`.

O `painel_do_projeto` é o painel de um projeto só, o do `flatcap status <id>`, e nele o
`finalizado` aparece: é o jeito de ver um projeto finalizado sem abrir a ficha.

## O status e o prazo

Os dois saem da ficha, como estão escritos. O status é um dos do `projeto.STATUS`,
reconhecido pelo `ficha.status_reconhecido` sem distinguir maiúscula, acento ou `_`. O
que não é nenhum deles aparece como está escrito, marcado: escondê-lo seria esconder
justamente o projeto que precisa de atenção.

O prazo é a data final, escrita à mão depois da reunião e lida pelo
`ficha.data_escrita`. Quando a data passa e o projeto não está `pronto`, ele está
atrasado: o prazo é o do relatório, e o projeto pronto já o tem — o finalizado também.
O dia do prazo ainda não é atraso. A data de hoje vem de `agora=`, como em todo
`preparar*`, porque um teste que lê o relógio quebra à meia-noite.

## A troca de status

`flatcap status 41 --finalizado` escreve o `status:` da ficha pelo `ficha.definir_status`
— o mesmo do relatório, que preserva os comentários, as aspas e a ordem das chaves — e
deixa uma linha no `historico.md`, com a frase do `projeto.frase_do_status`. A linha é o
que a troca feita à mão não deixa: a data. Sem ela, "quantos projetos terminaram em
outubro?" não tem resposta, e o status de um projeto num dia passado também não.

Dos comandos que escrevem na pasta do projeto, é o único que não simula antes. A
simulação existe para mostrar o que seria criado, movido ou arquivado antes de criar,
mover ou arquivar; aqui o que muda é uma palavra da ficha, o histórico guarda a de antes,
e o mesmo comando a desfaz — a CLI diz qual. O `preparar_troca` e o `executar_troca`
continuam separados, como em todo `preparar*`: a troca decidida é o que a CLI mostra, e o
que uma interface pode confirmar antes de gravar.

A troca para o status em que o projeto já está não escreve nada: a ficha que diz
`Pronto` já está `pronto`, e a que diz `novo` já está `não iniciado`.

## O que este módulo não faz

Não decide status nenhum: quem escreve o `status:` é você — à mão, ou pela troca daqui —,
o `flatcap novo` (`não iniciado`) e o `flatcap relatorio` (`pronto`). E o painel monta
dados, e não texto: é uma lista de `LinhaDoPainel`, com o prazo como data e o atraso como
um sim ou não. A CLI as desenha, e uma interface gráfica pode ordenar, filtrar e abrir a
pasta de cada uma sem ler a tabela do terminal.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from .ficha import (
    Ficha,
    data_escrita,
    definir_status,
    ler,
    localizar_projeto,
    status_reconhecido,
    varrer,
)
from .projeto import STATUS, STATUS_FINALIZADO, STATUS_PRONTO, anotar, frase_do_status

# Os status que não atrasam. O prazo é o do relatório: o projeto `pronto` já o tem, e o
# `finalizado` também — este não aparece no painel, mas aparece no de um projeto só.
_SEM_ATRASO = (STATUS_PRONTO, STATUS_FINALIZADO)


@dataclass(frozen=True)
class LinhaDoPainel:
    """
    Um projeto no painel: o que vai para cada coluna, ainda como dado.
    """

    pasta: Path  # a pasta do projeto: `.../00742 - José Antônio de Sá/Projeto 006`
    record_id: str
    matricula: str
    # O nome da ficha, e não o da pasta: o da pasta passou pela limpeza dos caracteres
    # que o Windows recusa, e o da ficha é o que o REDCap trouxe, com a sua correção.
    nome: str
    # Um dos do `projeto.STATUS`, na grafia de lá; ou, quando não é nenhum deles, o
    # que está escrito na ficha — e aí `status_reconhecido` é falso.
    status: str
    status_reconhecido: bool
    prazo: date | None
    # O `prazo:` como está escrito, quando ele não é uma data — `semana que vem`. Vazio
    # quando é uma data, e quando não há prazo nenhum.
    prazo_escrito: str = ""
    atrasado: bool = False

    @property
    def pasta_local(self) -> str:
        """
        `Projeto 006` — a coluna "Pasta local" do `flatcap listar`.
        """
        return self.pasta.name

    @property
    def sem_prazo(self) -> bool:
        return self.prazo is None and not self.prazo_escrito


@dataclass(frozen=True)
class Painel:
    """
    O painel inteiro, decidido. É daqui que sai a tabela do `flatcap status`.
    """

    hoje: date
    linhas: tuple[LinhaDoPainel, ...] = ()
    finalizados: int = 0
    ilegiveis: tuple[Path, ...] = ()  # as pastas de projeto cuja ficha não abre
    antigas: tuple[Path, ...] = ()  # as pastas de cliente no formato anterior à 1.1.0

    @property
    def atrasados(self) -> tuple[LinhaDoPainel, ...]:
        return tuple(linha for linha in self.linhas if linha.atrasado)

    @property
    def sem_prazo(self) -> tuple[LinhaDoPainel, ...]:
        return tuple(linha for linha in self.linhas if linha.sem_prazo)

    @property
    def status_fora_da_lista(self) -> tuple[LinhaDoPainel, ...]:
        return tuple(linha for linha in self.linhas if not linha.status_reconhecido)

    @property
    def prazos_que_nao_sao_data(self) -> tuple[LinhaDoPainel, ...]:
        return tuple(linha for linha in self.linhas if linha.prazo_escrito)


def montar_painel(root: Path, agora: datetime | None = None) -> Painel:
    """
    Lê todas as fichas do `FLATCAP_ROOT` e monta o painel. Não escreve nada.

    Args:
        root: o `FLATCAP_ROOT`.
        agora: relógio injetável — é ele que diz o que está atrasado.
    """
    hoje = (agora or datetime.now()).date()
    varredura = varrer(Path(root))

    linhas: list[LinhaDoPainel] = []
    finalizados = 0
    for ficha in varredura.projetos:
        if status_reconhecido(ficha.status) == STATUS_FINALIZADO:
            finalizados += 1
            continue
        linhas.append(_linha(ficha, hoje))

    return Painel(
        hoje=hoje,
        linhas=tuple(sorted(linhas, key=_ordem)),
        finalizados=finalizados,
        ilegiveis=tuple(erro.caminho.parent for erro in varredura.ilegiveis),
        antigas=varredura.antigas,
    )


def painel_do_projeto(raiz: Path, agora: datetime | None = None) -> Painel:
    """
    O painel de um projeto só — o do `flatcap status <id>` sem opção de status. Não
    escreve nada.

    A linha é a do painel de todos, com uma diferença: aqui o `finalizado` aparece, sem
    ATRASADO. "Como está o 41?" tem resposta mesmo depois de ele sair do painel, e sem
    abrir a ficha. Um `Painel`, e não só a linha, para a CLI desenhar a mesma tabela e os
    mesmos avisos do painel de todos.

    Args:
        raiz: a pasta do projeto (a que tem o `projeto.yaml`).
        agora: relógio injetável, como no `montar_painel`.

    Raises:
        FichaAusenteError, FichaInvalidaError
    """
    hoje = (agora or datetime.now()).date()
    return Painel(hoje=hoje, linhas=(_linha(ler(Path(raiz)), hoje),))


def _linha(ficha: Ficha, hoje: date) -> LinhaDoPainel:
    """
    A linha de um projeto, lida da ficha: o status na grafia da lista, o prazo como data
    e o atraso decidido.
    """
    status = status_reconhecido(ficha.status)
    prazo = data_escrita(ficha.prazo)
    return LinhaDoPainel(
        pasta=ficha.raiz,
        record_id=ficha.record_id,
        matricula=ficha.matricula,
        nome=ficha.nome,
        status=status or ficha.status,
        status_reconhecido=status is not None,
        prazo=prazo,
        prazo_escrito="" if prazo is not None else ficha.prazo,
        atrasado=prazo is not None and prazo < hoje and status not in _SEM_ATRASO,
    )


def _ordem(linha: LinhaDoPainel) -> tuple:
    """
    A ordem do `flatcap listar`: pelo `record_id`, como número — o `6` antes do `41`.

    O `record_id` que não é número (nenhum REDCap comum gera um, mas o campo é texto)
    vai para o fim, em ordem alfabética. A pasta desempata: dois projetos com o mesmo
    `record_id` são pasta duplicada, e saem um embaixo do outro.
    """
    if linha.record_id.isdigit():
        return (0, int(linha.record_id), str(linha.pasta))
    return (1, linha.record_id, str(linha.pasta))


# Caso de uso: trocar o status


@dataclass(frozen=True)
class TrocaDeStatus:
    """
    A troca do `status:` de um projeto, decidida e ainda não escrita.

    Imutável como o plano de todo comando: o que a CLI mostra é o que o `executar_troca`
    escreve.
    """

    ficha: Ficha  # a ficha como estava ao decidir: o status de antes sai dela
    novo: str  # um dos do `projeto.STATUS`, na grafia de lá
    quando: datetime  # a data e a hora da linha do histórico

    @property
    def raiz(self) -> Path:
        return self.ficha.raiz

    @property
    def anterior(self) -> str:
        """
        O status de antes como está escrito na ficha — `Em Andamento`, `novo`,
        `entregue` —, que é o que vai para o histórico.
        """
        return self.ficha.status

    @property
    def anterior_reconhecido(self) -> str | None:
        """
        O status de antes na grafia do `projeto.STATUS`; `None` quando não é nenhum
        deles. É o que a CLI oferece para voltar atrás.
        """
        return status_reconhecido(self.ficha.status)

    @property
    def muda(self) -> bool:
        """
        Falso quando o projeto já está no status pedido — e aí nada se escreve.
        """
        return self.anterior_reconhecido != self.novo


@dataclass(frozen=True)
class ResultadoDaTroca:
    """
    O que a troca de fato escreveu.
    """

    trocado: bool = False  # o `status:` da ficha mudou nesta execução
    avisos: tuple[str, ...] = ()


def preparar_troca(
    root: Path,
    identificador: str,
    status: str,
    agora: datetime | None = None,
) -> TrocaDeStatus:
    """
    Decide a troca de status de um projeto. Não escreve nada.

    Args:
        root: o `FLATCAP_ROOT`.
        identificador: `record_id` ou matrícula, como em todo comando que recebe `<id>`.
        status: um dos do `projeto.STATUS`, na grafia de lá.
        agora: relógio injetável — é a data da linha do histórico.

    Raises:
        ProjetoNaoEncontradoError, ProjetoAmbiguoError, LayoutAntigoError,
        FichaAusenteError, FichaInvalidaError
        ValueError: o status não é um do `projeto.STATUS` — defeito de quem chamou, e não
            do arquivo, como no `ficha.definir_status`.
    """
    if status not in STATUS:
        raise ValueError(f"status desconhecido: {status!r}; os válidos são {STATUS}")
    raiz = localizar_projeto(Path(root), identificador)
    return TrocaDeStatus(ficha=ler(raiz), novo=status, quando=agora or datetime.now())


def executar_troca(troca: TrocaDeStatus) -> ResultadoDaTroca:
    """
    Escreve a troca — o `status:` da ficha e a linha do histórico. Não decide mais nada.

    A ficha vem primeiro, e é gravada inteira ou não é (o `definir_status` grava pelo
    `ficha.escrever_atomico`): uma falha ali sobe sem ter mudado nada, e não há o que
    desfazer. O histórico vem depois, e a falha nele vira aviso, como em todo comando que
    escreve: desfazer o status por causa da linha seria perder a troca que você pediu por
    causa do recibo dela.

    A troca que não muda nada não escreve nada.

    Raises:
        FichaAusenteError, FichaInvalidaError: a ficha deixou de abrir depois do
            `preparar_troca`.
        OSError: a ficha não se deixou gravar — aberta noutro programa, sem permissão de
            escrita.
    """
    if not troca.muda:
        return ResultadoDaTroca()

    definir_status(troca.raiz, troca.novo)
    try:
        anotar(troca.raiz, _acao_do_historico(troca), troca.quando)
    except OSError as erro:
        return ResultadoDaTroca(
            trocado=True,
            avisos=(f"O status foi trocado, mas não consegui escrever no historico.md: {erro}",),
        )
    return ResultadoDaTroca(trocado=True)


def _acao_do_historico(troca: TrocaDeStatus) -> str:
    """
    "`flatcap status 41` — Status de `em andamento` para `finalizado`."

    O comando vai sem a opção, como o de todo comando no histórico: o começo da linha é
    a data, o comando e o `record_id`, e a frase diz o resto.
    """
    return (
        f"`flatcap status {troca.ficha.record_id}` — "
        f"{frase_do_status(troca.anterior, troca.novo)}"
    )


__all__ = [
    "LinhaDoPainel",
    "Painel",
    "ResultadoDaTroca",
    "TrocaDeStatus",
    "executar_troca",
    "montar_painel",
    "painel_do_projeto",
    "preparar_troca",
]
