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
    Já existe pasta para essa matrícula. Nada foi mudado. 

    O caminho fica gravado em `.pasta`, isso previne erros de quando a pasta é criada manualmente. 
    """

    def __init__(self, mensagem: str, pasta: Path) -> None:
        super().__init__(mensagem)
        self.pasta = pasta

@dataclass(frozen = True)
class ArquivoPlanejado: 
    """
    Um arquivo já baixado com destino e o recibo pronto -> ainda na memória. 

    O `sha256` é calculado aqui. É a diferença entre o recibo e uma anotação.  
    """
    caminho: Path
    conteudo: bytes
    sha256: str

    @property
    def tamanho(self) -> int:
        return len(self.conteudo)

    @property
    def tamanho_legivel(self) -> str:
        """
        Tamanho formado para o temrinal e para o `historico.md`.
        """
        return _tamanho_legivel(self.tamanho)

@dataclass(frozen = True)
class Plano:
    """
    Tudo o que será criado, decidido e pronto para escrever.

    Imutável como `Config` e `Cliente`: entre a simulação e a execução ningué, altera um caminho em trânsito. 
    O conteúdo dos dois arquivos de texto já vem montado, para que `executar` não precise tomar nenhuma decisão. 
    """
    cliente: Cliente
    raiz: Path
    subpastas: tuple[Path, ...]
    banco: ArquivoPlanejado | None
    projeto_yaml: str
    historico_md: str
    quando: datetime

    @property
    def tem_anexo(self) -> bool:
        return self.banco is not None

@dataclass(frozen = True)
class Resultado:
    """
    O que `executar` de fato criou, e o que não foi planejado.

    O `avisos` existe para o caso de somente-leitura: em unidades de rede ou pasta sincronizada em nuvem o `chmod` pode não pegar.  
    """
    criados: tuple[Path, ...]
    avisos: tuple[str, ...] = ()


# Casos de uso

def preparar(
        cfg: Config,
        record_id: str,
        agora: datetime | None = None,
) -> Plano:
    """
    
    """
    quando = agora or datetime.now()
    cliente = _buscar_cliente(cfg, record_id)
    _conferir_identificacao(cliente)
    raiz = _destino(cfg, cliente)
    anexo = _baixar_anexo(cfg, cliente)
    return _montar_plano(cliente, raiz, anexo, quando)

def executar(plano: Plano) -> Resultado:
    """
    
    """
    pass

