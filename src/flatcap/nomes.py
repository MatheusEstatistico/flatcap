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
    Monta o nome da pasta do cliente: `123456789 - Matheus Fernandes`

    Raises: 
        NomeInvalidoError: erro para quando não tem número de matrícula válido. 
    """
    matricula_limpa = sanitizar(matricula)
    nome_limpo = sanitizar(nome)

    if not matricula_limpa:
        raise NomeInvalidoError(
            f"Matrícula vazia. Recebido: {matricula!r}"
            "Ver REDCap manualmente..."
        )
    if not nome_limpo:
        """
        Nome vazio não impede o trabalho, apenas a matrícula é indispensável. 
        """
        return matricula_limpa

    return f"{matricula_limpa}{SEPARADOR}{nome_limpo}"

def localizar_pasta(root: Path, matricula: str) -> Path | None:
    """
    Procura a pasta com a matrícula do cliente na pasta `FLATCAP_ROOT`.
    Busca por prefíxo para garantir que não perca quando a pasta foi criada ou renomeada a mão. 
    """
    matricula_limpa = sanitizar(matricula)
    if not matricula_limpa or not root.is_dir():
        return None

    for item in sorted(root.iterdir()):
        if not item.is_dir():
            continue
        if _combina(item.name, matricula_limpa):
            return item
    return None

def _combina(nome_da_pasta: str, matricula: str) -> bool:
    """
    Função que diz o resultado da busca pela pasta usando a matrícula. 
    Busca só a matrícula, então  aceita vários formatos de nomes, para garantir que não quebre com pastas feitas a mão ou com mudanças de configurações em server. 
    """
    if not nome_da_pasta.startswith(matricula):
        return False
    resto = nome_da_pasta[len(matricula): ]
    return not resto or not resto[0].isdigit()




