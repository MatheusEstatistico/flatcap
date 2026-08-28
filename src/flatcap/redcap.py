"""
Camada fina sobre a API do REDCap.
A API tem três particularidades que este módulo isola, para que nenhuma delas vaze para o resto do sistema:

    1. tudo é POST com `application/x-www-form-urlencoded` no mesmo endpoint; o que muda e o campo `content` do corpo;
    2. erros vêm como HTTP 400 com um JSON {"error": "..."} — nao como exceção de rede. Sem tratamento, viram um KeyError incompreensível três camadas acima.
    3. `content = file` devolve bytes, não JSON. Por isso a aquisição foi serparada em duas camadas: 
        a) `_requisitar` faz a rede e devolve a resposta crua;
        b) `_post` é a leitura JSON em cima dela.
"""

from __future__ import annotations
import re
import requests
from dataclasses import dataclass
from typing import Any
from .config import Config

TIMEOUT_SEGUNDOS = 30

class RedcapError(RuntimeError):
  """
  Falha na conversa com a API do REDCap, já traduzida.
  """

class ArquvoAusenteError(RedcapError):
    """
    O campo de arquivo existe, mas o registro não tem nada anexado.
    Sublasso do `RedcapError`.
    """

@dataclass(frozen = True)
class ArquivoRedcap:
    """
    O anexo baixad, ainda em memória. 
    `nome` é o nome original do arquivo do jeito que foi nomeado o cliente. 
    """
    nome: str
    conteudo: bytes
    tipo_mime: str

# Camada de rede

def _requisitar(cfg: Config, payload: dict[str,str]) -> requests.Response:
  """
  
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

  if resposta.status_code == 403:
    raise RedcapError("403: Token recusado")
  if resposta.status_code == 404:
    raise RedcapError("404: Endereço não econtrado")

  return resposta



def _post(cfg: Config, payload: dict[str, str]) -> Any:
  """
  Executa uma chamada autenticada e devolve o JSON já codificado. 
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
      f"Falha no certificado SSL de {cfg.api_url}\n"
      f"Detalhe técnico: {erro}"
    ) from erro
  except requests.exceptions.ConnectionError as erro:
    raise RedcapError(
      f"Não consegui acessar {cfg.api_url}\n"
      f"Detalhe técnico: {erro}"
    ) from erro
  except requests.exceptions.Timeout as erro:
    raise RedcapError(
      f"O servidor não respondeu em {TIMEOUT_SEGUNDOS}s: {cfg.api_url}"
    ) from erro

  if resposta.status_code == 403:
    raise RedcapError(
      "403 — token recusado."
    )
  if resposta.status_code == 404:
    raise RedcapError(
      f"404 — endereço não encontrado: {cfg.api_url}"
    )

  try:
    corpo = resposta.json()
  except ValueError as erro:
    trecho = resposta.text[:200].replace("\n", " ")
    raise RedcapError(
      f"A resposta não era JSON (HTTP {resposta.status_code}).\n"
    ) from erro

  """
  O REDCap sinaliza erro de aplicação no corpo, não no `status`.
  """
  if isinstance(corpo, dict) and "error" in corpo:
    raise RedcapError(f"O REDCap recusou a chamada: {corpo['error']}")

  resposta.raise_for_status()
  return corpo




# Chamadas Gerais

def exportar_projeto(cfg: Config) -> dict[str, Any]:
  """
  Devolve os metadados do projeto (`content = project`).
  É a chamada mais barata da API e não depende de nenhum registro existir, por isso serve como teste de conexão no `flatcap doctor`. 
  """
  corpo = _post(cfg, {"content": "project"})
  if not isinstance(corpo, dict):
    raise RedcapError(
      f"Resposta inesperada em content=project: {type(corpo).__name__}"
    )
  return corpo

