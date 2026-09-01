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



