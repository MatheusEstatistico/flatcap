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
  Faz a requesição da chamada autenditaca e devolve só a resposta. 
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

  if resposta.status_code == 403:
    raise RedcapError("403: Token recusado")
  if resposta.status_code == 404:
    raise RedcapError("404: Endereço não econtrado")

  return resposta

def _erro_no_corpo(resposta: requests.Response) -> str | None: 
  """
  Devolve a mensagem de erro do REDCap, se o corpo form um erro de aplicação. 
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

def _post(cfg: Config, payload: dict[str, str]) -> Any:
  """
  Executa uma chamada autenticada e devolve o JSON já codificado. 
  """
  resposta = _requisitar(cfg, payload)

  erro = _erro_no_corpo(resposta)
  if erro is not None:
    raise RedcapError(f"O REDCap recusou a chamada: {erro}.")

  try:
    corpo = resposta.json()
  except ValueError as causa:
    trecho = resposta.text[:200].replace("\n", " ").strip()
    raise RedcapError(
      f"A resposta não era JSON (HTTP {resposta.status_code}).\n"
    ) from causa

def _lista_de_dicionarios(corpo: Any, rotulo: str) -> list[dict[str, str]]:
  """
  Confere se a resposta do corpo é uma lista.
  """
  if not isinstance(corpo, list):
    raise RedcapError(
      f"Resposta inesperada em {rotulo}. Deveria ser uma lista."
      f"Resposta atual {type(corpo).__name__}."
    )
  return [{str(k): "" if v is None else str (v) for k, v in item.items()} for item in corpo]

def _indexar(nome: str, valores: list[str])-> dict[str, str]:
  """
  Converte ['a', 'b'] em {'nome[0]': 'a', 'nome[1]': 'b'}. 
  O REDCap espera parâmetros em lista. 
  """
  return {f"{nome}[{i}]": valor for i, valor in enumerate(valores)}



# Chamadas Gerais

def exportar_projeto(cfg: Config) -> dict[str, Any]:
  """
  Devolve os metadados do projeto (`content = project`).
  É a chamada mais barata da API e não depende de nenhum registro existir, por isso serve como teste de conexão no `flatcap doctor`. 
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
      fields: campos a trazer. Pedir só o necessário reduz a resposta e evita trafegar campos que o FlatCap não usa.
      records: limita a registros específicos.
  
  Os valores vêm crus (`rawOrLabel = raw`), então `intro` chega como "1"/"2" e não como "Professor/Colaborador".
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
    payload.update(_indexar("fields", fields))
  if records:
    payload.update(_indexar("records", records))

  return _lista_de_dicionarios(_post(cfg, payload), "content=record")

def exportar_metadados(cfg: Config, fields: list[str] | None = None) -> list[dict[str, str]]:
  """
  Devolve o dicionário de variáveis do projeto (`content = metadata`).
  """
  payload: dict[str, str] = {"content": "metadata"}
  if fields:
    payload.update(_indexar("fields", fields))

  return _lista_de_dicionarios(_post(cfg, payload), "content=metadata")

def exportar_arquivo(cfg: Config, record_id: str, campo: str) -> ArquivoRedcap:
  """
  Baixa o anexo de um campo de arquivo (`content = file`, `action = export`).
  Raises:
    ArquivoAusenteError: o registro existe, mas não tem arquivo neste campo.
    RedcapError: qualquer outra falha — token sem permissão de exportar arquivos, registro inexistente, campo que não é do tipo file.
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

  resposta.raise_for_status()

  return ArquivoRedcap(
    nome=_nome_do_anexo(resposta) or f"{record_id}_{campo}",
    conteudo=resposta.content,
    tipo_mime=resposta.headers.get("Content-Type", "").split(";")[0].strip(),
  )


def tem_arquivo(cfg: Config, record_id: str, campo: str) -> bool:
  """
  Responde se existe anexo, sem que quem pergunta precise tratar exceção.
  Custa um download completo: a API do REDCap não oferece uma consulta que responda "existe?" sem trazer o conteúdo. Por isso é usada apenas sob demanda, pela opção `--conferir-anexos` do `flatcap listar`, e não no caminho normal.
  """
  try:
    exportar_arquivo(cfg, record_id, campo)
  except ArquivoAusenteError:
    return False
  return True


