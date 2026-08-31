"""

"""

from __future__ import annotations

import hashlib
import mimetypes
import  stat

from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path

import yaml

from .config import Config
from .modelo import CAMPO_ANEXO, CAMPOS_REDCAP, Cliente, normalizar
from .nomes import NomeInvalidoError, localizar_pasta, nome_pasta, sanitizar
from .redcap import ArquivoAusenteError, ArquivoRedcap, exportar_arquivo, exportar_registros

SUBPASTAS: tuple[str, ...] = (
    "1. Dados originais",
    "2. Versões antigas",
    "3. Análises",
)

PASTA_DADOS = SUBPASTAS[0] # o .docx fica na raíz do projeto

PREFIXO = "00_redcap_" # feito dessa forma para manter uma ordem cronológica

STATUS_INICIAL = "novo"

_MIMEE_GENERICOS = {"", "application/octet-stream", "binary/octet-stream"}

class ProjectERror(RuntimeError):
    """
    
    """
    pass

