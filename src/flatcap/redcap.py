# SPDX-FileCopyrightText: 2026 Matheus Fernandes
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Camada fina sobre a API do REDCap.
A API tem três particularidades que este módulo isola, para que nenhuma delas vaze para o resto do
sistema:

    1. tudo é POST com `application/x-www-form-urlencoded` no mesmo endpoint; o que muda é o campo
       `content` do corpo;
    2. erros vêm como HTTP 400 com um JSON {"error": "..."} — não como exceção de rede. Sem
       tratamento, viram um KeyError incompreensível três camadas acima.
    3. `content = file` devolve bytes, não JSON. Por isso a aquisição foi separada em duas camadas:
        a) `_requisitar` faz a rede e devolve a resposta crua;
        b) `_post` é a leitura JSON em cima dela.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import requests

from .config import Config

TIMEOUT_SEGUNDOS = 30

"""
Mensagens com que o REDCap sinaliza "este registro não tem arquivo neste campo".
É ausência esperada, não falha: um cliente pode simplesmente não ter anexado o banco.
Comparação em minúsculas e por trecho, porque o texto exato varia entre versões e idiomas do
servidor.
"""
_SEM_ARQUIVO = (
    "there is no file",
    "no file to download",
    "não há arquivo",
    "nao ha arquivo",
    "nenhum arquivo",
)

class RedcapError(RuntimeError):
    """
    Falha na conversa com a API do REDCap, já traduzida.
    """

class ArquivoAusenteError(RedcapError):
    """
    O campo de arquivo existe, mas o registro não tem nada anexado.
    Subclasse do `RedcapError`.
    """

@dataclass(frozen = True)
class ArquivoRedcap:
    """
    O anexo baixado, ainda em memória.
    `nome` é o nome original do arquivo do jeito que o cliente o nomeou.
    """
    nome: str
    conteudo: bytes
    tipo_mime: str

# Camada de rede

def _requisitar(cfg: Config, payload: dict[str,str]) -> requests.Response:
    """
    Faz a requisição da chamada autenticada e devolve só a resposta.
    Traduz as falhas de rede que não dependem do corpo.
    """
    dados = {
        "token": cfg.token,
        "format": "json",
        "returnFormat": "json",
        **payload,
    }

    try:
        resposta = requests.post(cfg.api_url, data = dados, timeout = TIMEOUT_SEGUNDOS)
    except requests.exceptions.SSLError as erro:
        raise RedcapError(
            f"Não foi possível acessar {cfg.api_url}\n"
            f"Detalhe técnico: {erro}"
        ) from erro
    except requests.exceptions.Timeout as erro:
        raise RedcapError(
            f"O servidor não respondeu em {TIMEOUT_SEGUNDOS}s: {cfg.api_url}"
        ) from erro
    except requests.exceptions.ConnectionError as erro:
        # Precisa vir **depois** do SSLError e do Timeout: no `requests`, o
        # `SSLError` e o `ConnectTimeout` são subclasses desta. Sem esta cláusula,
        # máquina sem rede, VPN caída ou proxy recusando derrubavam o `doctor` com o
        # traceback inteiro do `urllib3` — que é exatamente o oposto do que o
        # `doctor` existe para fazer.
        raise RedcapError(
            f"Não foi possível chegar a {cfg.api_url}\n"
            "A máquina está sem rede, a VPN institucional está fora, ou o endereço da "
            "API está errado.\n"
            f"Detalhe técnico: {type(erro).__name__}: {erro}"
        ) from erro
    except requests.exceptions.RequestException as erro:
        # O resto da família do `requests`: a conexão que cai no meio do download
        # de um anexo grande (`ChunkedEncodingError`), o servidor que redireciona
        # em círculo, a URL que o `requests` não aceita. Por último, porque é a
        # mãe de todas as de cima.
        raise RedcapError(
            f"A conversa com {cfg.api_url} falhou no meio.\n"
            "Rode o comando de novo; se repetir, confira a rede e o REDCAP_API_URL.\n"
            f"Detalhe técnico: {type(erro).__name__}: {erro}"
        ) from erro

    if resposta.status_code == 403:
        raise RedcapError("403: Token recusado")
    if resposta.status_code == 404:
        raise RedcapError("404: Endereço não encontrado")

    return resposta

def _erro_no_corpo(resposta: requests.Response) -> str | None:
    """
    Devolve a mensagem de erro do REDCap, se o corpo for um erro de aplicação.
    """
    tipo = resposta.headers.get("Content-Type", "").lower()
    if "json" not in tipo and not resposta.content[:1] == b"{":
        return None
    try:
        corpo = resposta.json()
    except ValueError:
        return None
    if isinstance(corpo, dict) and "error" in corpo:
        return str(corpo["error"])
    return None

def _conferir_status(resposta: requests.Response, contexto: str) -> None:
    """
    Recusa a resposta HTTP de erro que não trouxe o `{"error": ...}` do REDCap.

    Até a 1.13.0 quem fazia isto era o `raise_for_status()` do `requests`, e a
    exceção dele, `requests.HTTPError`, não é `RedcapError`: um 500 do servidor,
    ou o 502 de um proxy institucional em manutenção, derrubava o `novo` e o
    `listar --conferir-anexos` com o traceback inteiro — que é o que esta camada
    existe para impedir. O erro de aplicação, com o JSON, já foi traduzido antes
    de chegar aqui, pelo `_erro_no_corpo`.
    """
    if resposta.status_code < 400:
        return

    motivo = getattr(resposta, "reason", "") or ""
    trecho = resposta.text[:200].replace("\n", " ").strip()
    linhas = [
        f"O servidor respondeu HTTP {resposta.status_code}"
        f"{f' ({motivo})' if motivo else ''} ao pedir {contexto}."
    ]
    if resposta.status_code >= 500:
        linhas.append(
            "É um erro do lado do servidor: o REDCap, ou o proxy na frente dele, pode "
            "estar fora do ar ou em manutenção. Tente de novo em alguns minutos."
        )
    if trecho:
        linhas.append(f"Começo da resposta: {trecho!r}")
    raise RedcapError("\n".join(linhas))


def _post(cfg: Config, payload: dict[str, str]) -> Any:
    """
    Chamada autenticada com resposta JSON, já decodificada.
    """
    resposta = _requisitar(cfg, payload)

    erro = _erro_no_corpo(resposta)
    if erro is not None:
        raise RedcapError(f"O REDCap recusou a chamada: {erro}")

    _conferir_status(resposta, f"content={payload.get('content', '?')}")

    try:
        corpo = resposta.json()
    except ValueError as causa:
        trecho = resposta.text[:200].replace("\n", " ").strip()
        raise RedcapError(
            f"A resposta não era JSON (HTTP {resposta.status_code}).\n"
            "Isso costuma indicar que REDCAP_API_URL aponta para uma página do "
            "REDCap, e não para o endpoint da API.\n"
            f"Começo da resposta: {trecho!r}"
        ) from causa

    if corpo is None:
        raise RedcapError(
            f"O REDCap devolveu um corpo vazio (JSON null) em "
            f"content={payload.get('content', '?')}.\n"
            f"HTTP {resposta.status_code}, Content-Type "
            f"{resposta.headers.get('Content-Type', '(ausente)')}, "
            f"{len(resposta.content)} bytes.\n"
            "Confira no REDCap se o token tem a permissão de exportação correspondente "
            "a esta chamada."
        )

    return corpo


def _lista_de_dicionarios(corpo: Any, rotulo: str) -> list[dict[str, str]]:
    """
    Confere se a resposta do corpo é uma lista.
    """
    if not isinstance(corpo, list):
        raise RedcapError(
            f"Resposta inesperada em {rotulo}. Deveria ser uma lista. "
            f"Resposta atual: {type(corpo).__name__}."
        )
    return [{str(k): "" if v is None else str(v) for k, v in item.items()} for item in corpo]

def _lista(valores: list[str]) -> str:
    """
    Converte ['a', 'b'] na string 'a,b', que é como o REDCap recebe listas.
    """
    return ",".join(valor.strip() for valor in valores if valor and valor.strip())


# Chamadas Gerais

def exportar_projeto(cfg: Config) -> dict[str, Any]:
    """
    Devolve os metadados do projeto (`content = project`).
    É a chamada mais barata da API e não depende de nenhum registro existir, por isso serve como
    teste de conexão no `flatcap doctor`.
    """
    corpo = _post(cfg, {"content": "project"})
    if not isinstance(corpo, dict):
        raise RedcapError(
            f"Resposta inesperada em content = project: {type(corpo).__name__}"
        )
    return corpo

def exportar_registros(
    cfg: Config,
    fields: list[str] | None = None,
    records: list[str] | None = None,
) -> list[dict[str,str]]:
    """
    Devolve as respostas do questionário (`content = record`).
      Args:
        fields: campos a trazer. Pedir só o necessário reduz a resposta e evita trafegar campos que
        o FlatCap não usa.
        records: limita a registros específicos.

    Os valores vêm crus (`rawOrLabel = raw`), então `intro` chega como "1"/"2" e não como
    "Professor/Colaborador".
    """
    payload: dict[str, str] = {
            "content": "record",
            "type": "flat",
            "rawOrLabel": "raw",
            "rawOrLabelHeaders": "raw",
            "exportCheckboxLabel": "false",
            "exportSurveyFields": "false",
            "exportDataAccessGroups": "false",
        }
    if fields:
        payload["fields"] = _lista(fields)
    if records:
        payload["records"] = _lista(records)

    return _lista_de_dicionarios(_post(cfg, payload), "content=record")

def exportar_metadados(cfg: Config, fields: list[str] | None = None) -> list[dict[str, str]]:
    """
    Devolve o dicionário de variáveis do projeto (`content = metadata`).
    """
    payload: dict[str, str] = {"content": "metadata"}
    if fields:
        payload["fields"] = _lista(fields)

    return _lista_de_dicionarios(_post(cfg, payload), "content=metadata")

def exportar_arquivo(cfg: Config, record_id: str, campo: str) -> ArquivoRedcap:
    """
    Baixa o anexo de um campo de arquivo (`content = file`, `action = export`).
    Raises:
      ArquivoAusenteError: o registro existe, mas não tem arquivo neste campo.
      RedcapError: qualquer outra falha — token sem permissão de exportar arquivos, registro
      inexistente, campo que não é do tipo file.
    """
    resposta = _requisitar(
        cfg,
        {
            "content": "file",
            "action": "export",
            "record": str(record_id),
            "field": campo,
        },
    )

    erro = _erro_no_corpo(resposta)
    if erro is not None:
        if any(marca in erro.lower() for marca in _SEM_ARQUIVO):
            raise ArquivoAusenteError(
                f"O registro {record_id} não tem arquivo no campo '{campo}'."
            )
        raise RedcapError(
            f"Não consegui baixar o campo '{campo}' do registro {record_id}: {erro}"
        )

    _conferir_status(resposta, f"o anexo '{campo}' do registro {record_id}")

    return ArquivoRedcap(
        nome=_nome_do_anexo(resposta) or f"{record_id}_{campo}",
        conteudo=resposta.content,
        tipo_mime=resposta.headers.get("Content-Type", "").split(";")[0].strip(),
    )


def tem_arquivo(cfg: Config, record_id: str, campo: str) -> bool:
    """
    Responde se existe anexo, sem que quem pergunta precise tratar exceção.
    Custa um download completo: a API do REDCap não oferece uma consulta que responda "existe?"
    sem trazer o conteúdo. Por isso é usada apenas sob demanda, pela opção `--conferir-anexos` do
    `flatcap listar`, e não no caminho normal.
    """
    try:
        exportar_arquivo(cfg, record_id, campo)
    except ArquivoAusenteError:
        return False
    return True


# Auxiliares

_PADROES_NOME = (
    # Content-Disposition: attachment; filename="banco.xlsx"
    re.compile(r'filename\*?\s*=\s*"([^"]+)"', re.IGNORECASE),
    re.compile(r"filename\*?\s*=\s*([^;]+)", re.IGNORECASE),

    # Content-Type: application/vnd...; name="banco.xlsx"  (é onde o REDCap põe)
    re.compile(r'name\s*=\s*"([^"]+)"', re.IGNORECASE),
    re.compile(r"name\s*=\s*([^;]+)", re.IGNORECASE),
)

def _nome_do_anexo(resposta: requests.Response) -> str | None:
    """
    Extrai o nome original do arquivo dos cabeçalhos da resposta.
    """
    cabecalhos = " ; ".join(
        filter(
            None,
            (resposta.headers.get("Content-Disposition"), resposta.headers.get("Content-Type")),
        )
    )

    for padrao in _PADROES_NOME:
        achado = padrao.search(cabecalhos)
        if achado:
            nome = _limpar_nome_de_arquivo(achado.group(1))
            if nome:
                return nome
    return None

def _limpar_nome_de_arquivo(bruto: str) -> str:
    """
    Reduz o nome anunciado pelo servidor ao nome de arquivo puro.
    Descarta qualquer componente de caminho (`../`, `C:\\`, `/etc/`) antes que ele chegue perto de
    um `open()`. O nome vem de fora, e o que vem de fora não monta caminho.
    """
    nome = bruto.strip().strip("'\"").strip()
    nome = nome.replace("\\", "/").split("/")[-1]
    nome = nome.replace("\x00", "").strip()
    return "" if nome in {"", ".", ".."} else nome
