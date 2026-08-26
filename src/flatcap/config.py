"""
Anotações...

"""

from __future__ import annotations
from dataclasses import dataclass
from dotenv import find_dotenv, load_dotenv
from pathlib import Path

import os

"""
Chaves: 

"""

CHAVES: dict[str, str] = {
    "REDCAP_API_URL": (
        "URL da API do REDCap, no formato https://<servidor>/redcap/api/ "
        "(NÃO É O LINK DO SERVEY). Veja a página 'API Playground' do projeto." 
    ),
    "REDCAP_TOKEN": (
        "Token da API, obtido no meu 'API' do projeto do REDCap. "
        "Preciisa ter permissão de exportar registros medatados e arquivos."
    ),
    "FLATCAP_ROOT": (
        "Caminho absoluto da pasta onde ficam os diretórios "
        "'matrícula - nome completo'. Precisa ficar fora do repositório. "
    ),
}


class ConfigError(RuntimeError):
    """
    Configuração ausente ou inválida!

    Erro próprio (e não ValueERror genérico) para que a CLI possa capturá-lo e transformar em mensagem amigável, sem engolir bugs de verdade.
    """

@dataclass(frozen=True)
class Config:
    pass