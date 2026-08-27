"""
Camada fina sobre a API do REDCap.

Na Fase 0 existe apenas o mínimo que o `doctor` precisa: o POST autenticado e a chamada `content=project`. 
As funções `exportar_registros`, `exportar_metadados` e `exportar_arquivo` entram na Fase 1, reaproveitando o mesmo `_post`.

A API do REDCap tem duas particularidades que este módulo isola:
    1. tudo é POST com `application/x-www-form-urlencoded` no mesmo endpoint; o que muda e o campo `content` do corpo;
    2. erros vêm como HTTP 400 com um JSON {"error": "..."} — nao como exceção de rede. Sem tratamento, viram um KeyError incompreensível três camadas acima.
"""

from __future__ import annotations
from typing import Any
from .config import Config

import requests

TIMEOUT_SEGUNDOS = 30

class RedcapError(RuntimeError):
  """
  Falha na conversa com a API do REDCap, já traduzida.
  """

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
