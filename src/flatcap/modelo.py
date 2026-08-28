"""
Construção das funções sobre regras ne nomenclaturas de pastas dos `Clientes`, e como reencontrá-las no disco.

O formato de nomenclatura é: `nº de matrícula - Nome completo`, mantendo o número de matrícula como forma de acesso.
"""

from __future__ import annotations
from pathlib import Path

import re


PROIBIDOS = r'/\:*?"<>|' # caracteres proibidos para fazer nome de pasta no windows

_TRADUCAO = str.maketrans({caractere: None for caractere in PROIBIDOS})

_CONTROLE = re.compile(r"[\x00-\x08\x0e-\x1f\x7f]") # caracteres de controle 

_ESPACOS = re.compile(r"\s+") # espaços escritos em "formato de sistema"

SEPARADOR = " - " # separador do número de matrícula e do nome completo


class NomeInvalidoError(ValueError):
    pass