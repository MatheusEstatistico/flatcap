"""

"""

from __future__ import annotations

import hashlib
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from .ficha import (
    Ficha,
    FichaError,
    Versao,
    acrescentar_versao,
    ler,
    localizar_projeto,
    sequencia_do_nome,
)
from .nomes import sanitizar
from .projeto import PASTA_ANTIGAS, PASTA_DADOS, anotar, tamanho_legivel

ORIGEM_REDCAP = "redcap"
ORIGEM_PADRAO = "cliente_pos_reuniao"

ROTULO_REVISADO = "revisado"

SEQUENCIA_REDCAP = 0
SEQUENCIA_MAXIMA = 99 # prefixo tem 2 digitos

_BLOCO =  1024 * 1024 # 1mb por leitura para calculaar hash


class DadosError(RuntimeError):
    """
    Falha ao versionar um banco, já traduzida para o usuário.
    """

class ArquivoOrigemError(DadosError):
    """
    O arquivo que você mandou registrar não existe ou já está dentro do projeto.
    """

class VersaoDuplicadaError(DadosError):
    """
    O arquivo é byte a byte idêntico a uma versão já registrada.

    Não é erro, é a resposta certa para "ele reenviou o mesmo arquivo". Sai com código 0.
    """

    def __init__(self, mensagem: str, versao: Versao) -> None:
        super().__init__(mensagem)
        self.versao = versao

class DestinoOcupadoError(DadosError):
    """
    O nome calculado para a versão nova já existe no disco.
    """

@dataclass(frozen = True)
class PlanoDados:
    """
    Tudo o que o `dados adicionar` faria, decidido e ainda não escrito.

    Imutável como o `Plano` na Fase2.
    """
    ficha: Ficha
    origem: Path
    destino: Path
    sequencia: int
    sha256: str
    tamanho: int
    rotacaoes: tuple[tuple[Path, Path], ...]
    versao: Versao
    quando: datetime

    @property
    def raiz(self) -> Path:
        return self.ficha.raiz

    @property
    def tamanho_legivel(self) -> str:
        return tamanho_legivel(self.tamanho)

@dataclass(frozen = True)
class ResultadoDados:
    """
    
    """
    pass