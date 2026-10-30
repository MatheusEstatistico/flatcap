# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
"""
O painel do `flatcap status`: os projetos que já têm pasta, com o status e o prazo.

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

## O status e o prazo

Os dois saem da ficha, como estão escritos. O status é um dos do `projeto.STATUS`,
reconhecido pelo `ficha.status_reconhecido` sem distinguir maiúscula, acento ou `_`. O
que não é nenhum deles aparece como está escrito, marcado: escondê-lo seria esconder
justamente o projeto que precisa de atenção.

O prazo é a data final, escrita à mão depois da reunião e lida pelo
`ficha.data_escrita`. Quando a data passa e o projeto não está `pronto`, ele está
atrasado: o prazo é o do relatório, e o projeto pronto já o tem. O dia do prazo ainda
não é atraso. A data de hoje vem de `agora=`, como em todo `preparar*`, porque um teste
que lê o relógio quebra à meia-noite.

## O que este módulo não faz

Não escreve nada e não decide status nenhum: quem escreve o `status:` é você, o
`flatcap novo` (`não iniciado`) e o `flatcap relatorio` (`pronto`). E monta dados, e não
texto: o painel é uma lista de `LinhaDoPainel`, com o prazo como data e o atraso como
um sim ou não. A CLI as desenha, e uma interface gráfica pode ordenar, filtrar e abrir
a pasta de cada uma sem ler a tabela do terminal.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from .ficha import data_escrita, status_reconhecido, varrer
from .projeto import STATUS_FINALIZADO, STATUS_PRONTO


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
        status = status_reconhecido(ficha.status)
        if status == STATUS_FINALIZADO:
            finalizados += 1
            continue

        prazo = data_escrita(ficha.prazo)
        linhas.append(
            LinhaDoPainel(
                pasta=ficha.raiz,
                record_id=ficha.record_id,
                matricula=ficha.matricula,
                nome=ficha.nome,
                status=status or ficha.status,
                status_reconhecido=status is not None,
                prazo=prazo,
                prazo_escrito="" if prazo is not None else ficha.prazo,
                atrasado=prazo is not None and prazo < hoje and status != STATUS_PRONTO,
            )
        )

    return Painel(
        hoje=hoje,
        linhas=tuple(sorted(linhas, key=_ordem)),
        finalizados=finalizados,
        ilegiveis=tuple(erro.caminho.parent for erro in varredura.ilegiveis),
        antigas=varredura.antigas,
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


__all__ = [
    "LinhaDoPainel",
    "Painel",
    "montar_painel",
]
