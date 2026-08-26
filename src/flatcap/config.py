"""
Leitura e validação da configuração do FlatCap.

Este é o único lugar do sistema que lê variáveis de ambiente. Todo o resto recebe um objeto `Config` pronto. 
Consequência prática: nenhum caminho fixo e nenhum `os.environ` espalhado pelo código.
Regra de precedência: variáveis já definidas no ambiente do sistema prevalecem sobre o `.env` (`override=False`). 
Isso permite rodar em outra máquina, em um servidor ou em um teste sem editar arquivo nenhum.
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
    """
    Configuração válida. Imutável de propósito: ninguém altera em trânsito.
    """

    api_url: str
    token: str
    root: str
    origem_env: str | None = None # caminho do .env efetivamente carregado

    @property
    def token_mascarado(self) -> str:
        """
        
        """
        if len(self.token) <= 8:
            return "*" * len(self.token)
        return f"{self.token[:4]}{'*' * (len(self.token) - 8)}{self.token[-4:]}"

def carregar() -> Config: 
    """
    
    """

# Validações individuais 

def _validar_api_url(valor: str) -> str:
    pass
