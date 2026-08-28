"""
Construção das funções sobre regras ne nomenclaturas de pastas dos `Clientes`, e como reencontrá-las no disco. 
O formato de nomenclatura é: `nº de matrícula - Nome completo`, mantendo o número de matrícula como forma de acesso. 
A ideia é ter uma função `listar` que irá fazer essas verificações.
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
    """
    Não sobrou caracters para nomear a pasta.
    """

def sanitizar(texto: str) -> str:
    """
    Limpar o texto antes de criar o nome da pasta. Ajusta:
    1. remove caracteres de controle; 
    2. remove caracteres proibidos (windows); 
    3. corrige espaços em excesso; 
    4. tira espaços e pontos no início e no final do nome.

    """
    limpo = _CONTROLE.sub("", texto or "")
    limpo = limpo.translate(_TRADUCAO)
    limpo = _ESPACOS.sub(" ", limpo).strip()
    return limpo.rstrip(" .")

def nome_pasta(matricula: str, nome: str) -> str:
    """
    
    """
    matricula_limpa = sanitizar(matricula)
    nome_limpo = sanitizar(nome)

def localizar_pasta(root: Path, matricula: str) -> Path | None:
    """
    
    """
    pass

def _combina(nome_pasta: str, matricula: str) -> bool:
    """
    
    """
    pass
