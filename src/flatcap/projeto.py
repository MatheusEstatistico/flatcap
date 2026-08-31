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

_MIMES_GENERICOS = {"", "application/octet-stream", "binary/octet-stream"}

class ProjetoError(RuntimeError):
    """
    Falha ao montar a pasta do projeto, já traduzida para o usuário.

    Erro próprio pelo mesmo motivo de `ConfigError` e `RedcapError`: a CLI captura
    esta classe e transforma em painel; qualquer outra exceção é bug de verdade e
    deve subir com o traceback inteiro.
    """


class RegistroNaoEncontradoError(ProjetoError):
    """
    O REDCap não tem nenhum registro com este `record_id`.
    """


class ClienteIncompletoError(ProjetoError):
    """
    O registro existe, mas não dá para nomear a pasta a partir dele.

    A automação cria pasta apenas para registro bem formado. Quem diagnostica é o
    `flatcap listar`, que já marca esses casos em amarelo; o `novo` apenas se
    recusa a produzir uma pasta que você teria de renomear depois.
    """

class ProjetoExistenteError(ProjetoError):
    """
    
    """

    def __init__(self, mensagem: str, pasta: Path) -> None:
        super().__init__(mensagem)
        self.pasta = pasta

@dataclass(frozen = True)
class ArquivoPlanejado: 
    """
    
    """
    caminho: Path
    conteudo: bytes
    sha256: str

    @property
    def tamanho(self) -> int:
        pass