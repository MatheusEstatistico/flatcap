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

