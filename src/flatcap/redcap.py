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
  pass




def exportar_projeto(cfg: Config) -> dict[str, Any]:
  """
  Devolve os metadados do projeto (`content = project`).
  E a chamada mais barata da API e não depende de nenhum registro existir, por isso serve como teste de conexão no `flatcap doctor`. 
  """
  pass
