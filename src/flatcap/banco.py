"""

"""

from __future__ import annotations

import csv 
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .dados import ItemDaLinha, linha_do_tempo
from .ficha import Ficha, Versao
from .projeto import PASTA_ANTIGAS, PASTA_DADOS, tamanho_legivel

EXTENSOES_SUPORTADAS = (".xlsx", ".csv")

_CONVERSAO = {
    "": "",
    "": "",
    "": "",
    "": "",
    "": "",
    "": "",
    "": "",
    "": "",
    "": "",
    "": "",
    "": "",
    "": "",
    "": "",
    "": "",
    "": "",
    "": "",
}

_AMOSTRA_BYTES = 64 * 1024
_SEPARADORES = (";", ",", "\t", "|", "^")
_CODIFICACOES = ("utf-8", "cp1215", "latin-1")

class BancoError(RuntimeError):
    """
    Falha ao abrir o banco, já traduzida para o usurário.
    """

class BancoNaoRegistradoError(BancoError):
    """
    O Projeto existe, mas nenhuma versão do bando foi registrada na ficha.
    """

class BancoAusenteError(BancoError):
    """
    A ficha registra a versão vigente e ela não está no disco.
    """

class BancoIlegivelError(BancoError):
    """
    O formato é suportado, mas o arquivo não abriu.
    """

class BancoVazioError(BancoError):
    """
    O arquivo abriu e não tem nada.
    """

class AbaInexistenteError(BancoError):
    """
    A planilha `--aba` não existe na pasta de trabalho.
    """

@dataclass(frozen = True)
class Leitura:
    """
    
    """
    caminho: Path
    aba: str | None = None
    abas: tuple[str, ...] = ()
    separador = str | None = None
    codificacao: str | None = None

    @property
    def formato(self) -> str:
        return self.caminho.suffix.lower()

    @property
    def outras_abas(self) -> tuple[str, ...]:
        return tuple(nome for nome in self.abas if nome != self.aba)

    def descrever(self) -> str:
        """
        Uma linha dizendo de onde vem os dados.
        """
        pass