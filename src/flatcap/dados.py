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

ORIGEM_REDCAP = "redcap"
ORIGEM_PADRAO = "cliente_pos_reuniao"

ROTULO_REVISADO = "revisado"

SEQUENCIA_REDCAP = 0
SEQUENCIA_MAXIMA = 99 # prefixo tem 2 digitos

_BLOCO =  1024 * 1024 # 1mb por leitura para calculaar hash


class DadosError(RuntimeError):
    """
    Falha ao versionar um banco, já traduzida para o usuário.
    """

class ArquivoOrigemError(DadosError):
    """
    O arquivo que você mandou registrar não existe ou já está dentro do projeto.
    """

class VersaoDuplicadaError(DadosError):
    """
    O arquivo é byte a byte idêntico a uma versão já registrada.

    Não é erro, é a resposta certa para "ele reenviou o mesmo arquivo". Sai com código 0.
    """

    def __init__(self, mensagem: str, versao: Versao) -> None:
        super().__init__(mensagem)
        self.versao = versao

class DestinoOcupadoError(DadosError):
    """
    O nome calculado para a versão nova já existe no disco.
    """

@dataclass(frozen = True)
class PlanoDados:
    """
    Tudo o que o `dados adicionar` faria, decidido e ainda não escrito.

    Imutável como o `Plano` na Fase2.
    """
    ficha: Ficha
    origem: Path
    destino: Path
    sequencia: int
    sha256: str
    tamanho: int
    rotacaoes: tuple[tuple[Path, Path], ...]
    versao: Versao
    quando: datetime

    @property
    def raiz(self) -> Path:
        return self.ficha.raiz

    @property
    def tamanho_legivel(self) -> str:
        return tamanho_legivel(self.tamanho)

@dataclass(frozen = True)
class ResultadoDados:
    """
    A execução é aqui
    """
    criados: tuple[Path, ...] = ()
    movidos: tuple[tuple[Path, Path], ...] = ()
    avisos: tuple[str, ...] = ()

@dataclass(frozen = True)
class ItemDaLinha:
    """
    Uma versão registrada, confrontada com o que está no disco.
    """
    versao: Versao
    caminho: Path | None
    local: str
    confere: bool | None # None = não conferido ou inexistente

    @property
    def presente(self) -> bool:
        return self.caminho is not None

@dataclass(frozen = True)
class LinhaDoTempo:
    """
    Cronologia das versões.
    """
    ficha: Ficha
    itens: tuple[ItemDaLinha, ...]
    nao_registrados: tuple[Path, ...]
    conferito: bool

    @property
    def ausente(self) -> tuple[ItemDaLinha, ...]:
        return tuple(item for item in self.itens if not item.presente)

    @property
    def alterado(self) -> tuple[ItemDaLinha, ...]:
        return tuple(item for item in self.itens if item.confere is False)

    @property
    def integra(self) -> bool:
        return not (self.ausente or self.alterados or self.nao_registrados)


# Caso de uso: adicionar uma versão

def preparar_adicao(
        root: Path, identificador: str, caminho: Path | str, agora: datetime | None = None, origem_rotulo: str = ORIGEM_PADRAO,
) -> PlanoDados:
    """
    
    """
    quando = agora or datetime.now()
    raiz = localizar_projeto(Path(root), identificador)
    ficha = ler(raiz)

    origem = _conferir_origem(caminho, raiz)
    sha256, tamanho = _hash_e_tamanho(origem)

    _recusar_duplicatas(ficha, sha256)

    sequencia = _proxima_sequencia(ficha, raiz)
    destino = raiz / PASTA_DADOS / _nome_da_versao(sequencia, origem.nome, quando.date())

    if destino.exists():
        raise DestinoOcupadoError(
            f"Já existe um arquivo com esse nome:\n"
            f"  {destino}"
        )
    return PlanoDados(
        ficha = ficha,
        origem = origem,
        destino = destino,
        sequencia = sequencia,
        sha256 = sha256,
        tamanho = tamanho,
        rotacoes = _rotacoes(raiz),
        versao = Versao(
            arquivo = destino.name,
            origem = origem_rotulo,
            sha256 = sha256,
            tamanho_bytes = tamanho,
            data = quando.date(),
        ),
        quando = quando,
    )

def executar_adicao(plano: PlanoDados) -> ResultadoDados:
    """
    
    """
    criados: list[Path] = []
    movidos: list[tuple[Path, Path]] = []
    avisos: list[str] = []
    desfazer: list[Callable[[], None]] = []

    try: 
        pasta_antigas = plano.raiz / PASTA_ANTIGAS
        if not pasta_antigas.exists():
            pasta_antigas.mkdir(parents = True)
            criados.append(pasta_antigas)
            desfazer.append(lambda p = pasta_antigas: p.rmdir())

        # 1. 
        shutil.copy2(plano.origem, plano.destino)
        criados.append(plano.destino)
        desfazer.append(lambda p = plano.destino: p.unlink(missing_ok = True)) 

        # 2. 
        gravado, _ = _hash_e_tamanho(plano.destino)
        if gravado != plano.sha256:
            raise DadosError(
                "A cópia saiu diferente  da original. \n"
                f"  esprando: {plano.sha256}\n"
                f"  no disco: {gravado}\n"
                "nada foi registrado e o arquivo compiado foi removido."
            )

        # 3. 
        for de, para in plano.rotacaoes:
            de.rename(para)
            movidos.append((de, para))
            desfazer.append(lambda d = de, p = para: p.rename(d))

        # 4. 
        acrescentar_versao(plano.raiz, plano.versao)

        # 5. 
        try:
            anotar(plano.raiz, _acao_do_historico(plano), plano.quando)
        except OSError as erro: 
            avisos.append(
                f"A versão foi registrada, mas não consegui escrever no historico.md: {erro}"
            )
    except (OSError, DadosError, FichaError):
        for passo in reversed(desfazer):
            try:
                passo()
            except OSError:
                avisos.append(
                    "Falhei ao desfazer uma etapa.\n"
                    "Confira a pasta do projeto antes de rodar de novo"
                )
        raise
    return ResultadoDados(
        criados = tuple(criados), movidos = tuple(movidos), avisos = tuple(avisos)
    )


# 